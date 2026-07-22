"""
Single-agent loop: reads agent.yaml, connects to DeepSeek API,
and runs the agent with tool access until it produces a final answer
or hits max_turns.
"""

import json
import os
import shlex
import yaml
from openai import OpenAI

# ---------------------------------------------------------------------------
# TOOL IMPLEMENTATIONS
# These are the actual functions the LLM can call. Each maps 1:1 to a tool
# defined in agent.yaml. The framework matches by name.
# ---------------------------------------------------------------------------

TOOL_IMPLS = {}

def register(name):
    def deco(fn):
        TOOL_IMPLS[name] = fn
        return fn
    return deco

@register("read_file")
def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > 8000:
            content = content[:8000] + "\n... [TRUNCATED]"
        return {"status": "ok", "content": content}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@register("search_code")
def search_code(pattern, path="."):
    import subprocess
    try:
        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", "--include=*.cpp", "--include=*.h",
             "--include=*.js", "--include=*.ts", pattern, path],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout.strip() or "No matches found."
        if len(output) > 4000:
            output = output[:4000] + "\n... [TRUNCATED]"
        return {"status": "ok", "matches": output}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@register("list_directory")
def list_directory(path):
    try:
        entries = os.listdir(path)
        result = []
        for e in entries:
            full = os.path.join(path, e)
            tag = "[DIR]" if os.path.isdir(full) else "[FILE]"
            result.append(f"{tag} {e}")
        return {"status": "ok", "entries": "\n".join(result[:100])}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@register("run_tests")
def run_tests(command):
    import subprocess
    try:
        # Allowlist: only permit known safe commands
        safe_prefixes = ["pytest", "python -m pytest", "npm test", "cargo test", "go test"]
        is_safe = any(command.strip().startswith(p) for p in safe_prefixes)
        if not is_safe:
            return {"status": "error", "message": f"Command not in allowlist: {command[:80]}"}

        parsed = shlex.split(command)
        result = subprocess.run(parsed, shell=False, capture_output=True,
                                text=True, timeout=30, cwd=".")
        return {
            "status": "ok",
            "stdout": result.stdout[-3000:],
            "stderr": result.stderr[-2000:],
            "exit_code": result.returncode
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ---------------------------------------------------------------------------
# AGENT LOOP
# ---------------------------------------------------------------------------

def load_agent(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def build_tool_schemas(agent_cfg):
    """Convert agent.yaml tool definitions to OpenAI function-calling format."""
    schemas = []
    for tool in agent_cfg.get("tools", []):
        props = {}
        required = []
        for param_name, param_def in tool.get("parameters", {}).items():
            props[param_name] = {
                "type": param_def.get("type", "string"),
                "description": param_def.get("description", "")
            }
            if param_def.get("required"):
                required.append(param_name)
        schemas.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required
                }
            }
        })
    return schemas

def run_agent(agent_path, task, api_key=None):
    agent = load_agent(agent_path)
    client = OpenAI(
        api_key=api_key or os.environ.get("DEEPSEEK_API_KEY", "sk-placeholder"),
        base_url="https://api.deepseek.com/v1"
    )

    tools = build_tool_schemas(agent)
    max_turns = agent.get("max_turns", 10)

    messages = [
        {"role": "system", "content": agent["system_prompt"]},
        {"role": "user", "content": task}
    ]

    total_input_tokens = 0
    total_output_tokens = 0

    for turn in range(max_turns):
        print(f"\n--- Turn {turn + 1}/{max_turns} ---")

        resp = client.chat.completions.create(
            model=agent.get("model", "deepseek-chat"),
            messages=messages,
            tools=tools or None,
            temperature=agent.get("temperature", 0.3)
        )

        choice = resp.choices[0]
        msg = choice.message

        # Track token usage
        usage = resp.usage
        total_input_tokens += usage.prompt_tokens
        total_output_tokens += usage.completion_tokens

        # If the model wants to call a tool
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments)

                print(f"  -> Calling tool: {tool_name}({tool_args})")

                impl = TOOL_IMPLS.get(tool_name)
                if impl:
                    result = impl(**tool_args)
                else:
                    result = {"status": "error", "message": f"Unknown tool: {tool_name}"}

                # Append assistant message with tool call
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [{
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }]
                })
                # Append tool result
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result)
                })

            continue  # back to top of loop, model processes tool result

        # No tool call = final answer
        print(f"\n  Total input tokens:  {total_input_tokens}")
        print(f"  Total output tokens: {total_output_tokens}")
        print(f"  Est. cost:           ${(total_input_tokens * 0.14 + total_output_tokens * 0.28) / 1_000_000:.6f}\n")
        return msg.content

    return "[AGENT STOPPED: max_turns reached with no final answer]"

# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python agent_loop.py <task>")
        print("Example: python agent_loop.py 'Review the code in ./src for security issues'")
        sys.exit(1)

    task = sys.argv[1]
    agent_yaml = os.path.join(os.path.dirname(__file__), "agent.yaml")

    result = run_agent(agent_yaml, task)
    print("\n===== FINAL OUTPUT =====")
    print(result)
