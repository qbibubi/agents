"""
Team-Aware Agent Loop — Connects to model providers, polls the message
bus for tasks, executes them with budget enforcement, and posts results.

Usage:
  python team_agent_loop.py --agent coder
  python team_agent_loop.py --agent coder --team team_b
  python team_agent_loop.py --agent researcher
  python team_agent_loop.py --agent reviewer
  python team_agent_loop.py --agent orchestrator --task "Build a TODO app"
"""

import json
import os
import sys
import time
import argparse
import shlex
import yaml
import subprocess
import traceback
from pathlib import Path
from openai import OpenAI
from message_bus import MessageBus
from budget_tracker import BudgetTracker
from team_memory import TeamMemory


# ---------------------------------------------------------------------------
# TOOL IMPLEMENTATIONS
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
        p = Path(path)
        if not p.exists():
            return {"status": "error", "message": f"File not found: {path}"}
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > 8000:
            content = content[:8000] + "\n... [TRUNCATED]"
        return {"status": "ok", "content": content}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@register("write_file")
def write_file(path, content):
    try:
        p = Path(path)
        # Prevent path traversal outside project
        resolved = p.resolve()
        cwd = Path.cwd().resolve()
        if not str(resolved).startswith(str(cwd)):
            return {"status": "error", "message": f"Path traversal blocked: {path}"}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"status": "ok", "message": f"Written {len(content)} bytes to {path}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@register("search_code")
def search_code(pattern, path="."):
    try:
        result = subprocess.run(
            ["grep", "-rn", "--include=*.py", "--include=*.cpp", "--include=*.h",
             "--include=*.js", "--include=*.ts", "--include=*.yaml", "--include=*.json",
             pattern, path],
            capture_output=True, text=True, timeout=10, shell=False
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
        p = Path(path)
        if not p.exists():
            return {"status": "error", "message": f"Directory not found: {path}"}
        entries = []
        for e in sorted(p.iterdir()):
            tag = "[DIR]" if e.is_dir() else "[FILE]"
            entries.append(f"{tag} {e.name}")
        return {"status": "ok", "entries": "\n".join(entries[:100])}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@register("run_tests")
def run_tests(command):
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


@register("run_shell")
def run_shell(command):
    # Block entirely — too dangerous for LLM control
    return {"status": "error", "message": "run_shell is disabled for safety. Use specific tools instead."}


@register("web_search")
def web_search(query):
    return {
        "status": "ok",
        "message": f"Web search not configured. Query would be: {query}",
        "results": "Web search requires external API setup."
    }


# --- Bus-specific tools ---

@register("create_task")
def create_task(assigned_to, title, description, priority=3):
    bus = create_task.bus
    task_id = bus.CreateTask(assigned_to, title, description, priority=priority)
    return {"status": "ok", "task_id": task_id, "message": f"Task created for {assigned_to}"}


@register("check_results")
def check_results(task_id=None):
    bus = check_results.bus
    if task_id and task_id != "all":
        result = bus.GetResult(task_id)
        if result:
            return {"status": "ok", "results": [result]}
        return {"status": "ok", "results": [], "message": f"No result for {task_id}"}

    results = bus.ListResults()
    return {"status": "ok", "results": results[-20:]}


@register("send_feedback")
def send_feedback(task_id, feedback):
    bus = send_feedback.bus
    new_id = bus.SendFeedback(task_id, feedback)
    if new_id:
        return {"status": "ok", "new_task_id": new_id, "message": "Feedback sent, revision task created"}
    return {"status": "error", "message": f"Task {task_id} not found"}


@register("list_team")
def list_team():
    bus = list_team.bus
    status = bus.GetTeamStatus()
    return {"status": "ok", "team_status": status}


@register("team_remember")
def team_remember(topic, content, confidence="medium", tags=None):
    """Store a finding in team memory so other agents can access it."""
    memory = team_remember.memory
    agent = team_remember.agent_id
    entry = memory.Add(topic, content, agent, confidence, tags)
    return {"status": "ok", "message": f"Remembered: {topic}", "entry": entry}


@register("team_recall")
def team_recall(keyword=None, tag=None, limit=10):
    """Query team memory for past findings."""
    memory = team_recall.memory
    if keyword or tag:
        results = memory.Query(keyword=keyword, tag=tag, limit=limit)
    else:
        results = memory.GetAll()[:limit]
    return {"status": "ok", "entries": results, "count": len(results)}


# ---------------------------------------------------------------------------
# PROVIDER RESOLUTION
# ---------------------------------------------------------------------------

def LoadProviders(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ResolveProvider(agent_cfg, providers_cfg):
    """
    Given an agent config and the providers registry, return
    (base_url, api_key, model_name, input_price, output_price).
    """
    provider_name = agent_cfg.get("provider") or providers_cfg.get("default_provider", "deepseek")
    model_name = agent_cfg.get("model") or providers_cfg.get("default_model", "deepseek-chat")

    provider = providers_cfg.get("providers", {}).get(provider_name)
    if not provider:
        print(f"  WARNING: Provider '{provider_name}' not found, falling back to deepseek")
        provider = providers_cfg["providers"]["deepseek"]
        provider_name = "deepseek"

    base_url = provider["base_url"]
    api_key_env = provider.get("api_key_env", "DEEPSEEK_API_KEY")
    api_key = os.environ.get(api_key_env, "")

    model_info = provider.get("models", {}).get(model_name)
    if not model_info:
        # Try to find the model in any provider
        for pname, pinfo in providers_cfg.get("providers", {}).items():
            if model_name in pinfo.get("models", {}):
                model_info = pinfo["models"][model_name]
                break

    if not model_info:
        print(f"  WARNING: Model '{model_name}' not found in provider '{provider_name}'")
        model_info = {"input_price": 0.0, "output_price": 0.0}

    input_price = model_info.get("input_price", 0.0)
    output_price = model_info.get("output_price", 0.0)

    return base_url, api_key, model_name, input_price, output_price


# ---------------------------------------------------------------------------
# AGENT LOADING
# ---------------------------------------------------------------------------

def LoadAgent(agent_path):
    with open(agent_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def BuildToolSchemas(agent_cfg):
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


def GetAllowedTools(agent_cfg):
    return set(t["name"] for t in agent_cfg.get("tools", []))


# ---------------------------------------------------------------------------
# MAIN AGENT LOOP (with budget enforcement)
# ---------------------------------------------------------------------------

def RunAgent(agent_cfg, task_description, bus, budget, memory, providers_cfg):
    agent_id = agent_cfg["id"]
    team_id = agent_cfg.get("team", "default")

    # Resolve provider and model
    base_url, api_key, model_name, input_price, output_price = ResolveProvider(agent_cfg, providers_cfg)

    if not api_key and base_url != "http://localhost:11434/v1":
        print(f"  WARNING: No API key found. If using a local model this is fine.")

    client = OpenAI(
        api_key=api_key or "sk-noop",
        base_url=base_url
    )

    tools = BuildToolSchemas(agent_cfg)
    allowed_tools = GetAllowedTools(agent_cfg)
    max_turns = agent_cfg.get("max_turns", 15)

    # Inject team memory context into the task
    mem_context = memory.GetContextForAgent(max_entries=8)
    if mem_context:
        task_description = task_description + "\n\n" + mem_context

    messages = [
        {"role": "system", "content": agent_cfg["system_prompt"]},
        {"role": "user", "content": task_description}
    ]

    total_input_tokens = 0
    total_output_tokens = 0
    session_cost = 0.0
    consecutive_empty_checks = 0

    for turn in range(max_turns):
        # --- BUDGET CHECK BEFORE EVERY API CALL ---
        allowed, reason, fb_provider, fb_model = budget.CheckBudget(agent_id, team_id)

        if not allowed:
            print(f"\n  BUDGET STOP: {reason}")
            bus.Log(agent_id, f"BUDGET STOP: {reason}")
            return f"[BUDGET CAP REACHED] {reason}. Agent halted to prevent overspend."

        if fb_provider:
            # Switch to fallback (local) model
            fb_base_url, fb_api_key, fb_model_name, _, _ = ResolveProvider(
                {"provider": fb_provider, "model": fb_model}, providers_cfg
            )
            client = OpenAI(api_key=fb_api_key or "sk-noop", base_url=fb_base_url)
            model_name = fb_model_name
            input_price = 0.0
            output_price = 0.0
            print(f"  Switched to fallback: {fb_provider}/{fb_model_name}")
            bus.Log(agent_id, f"Switched to fallback: {fb_provider}/{fb_model_name}")

        if reason != "OK":
            print(f"  BUDGET WARNING: {reason}")
            bus.Log(agent_id, f"BUDGET WARNING: {reason}")

        print(f"\n--- [{agent_id}] Turn {turn + 1}/{max_turns} [{model_name}] ---")

        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=tools or None,
                temperature=agent_cfg.get("temperature", 0.3)
            )
        except Exception as e:
            print(f"  API ERROR: {e}")
            bus.Log(agent_id, f"API error on turn {turn + 1}: {e}")
            cost_msg = f"Session cost: ${session_cost:.6f}"
            return f"[API ERROR] {str(e)[:200]}. {cost_msg}"

        choice = resp.choices[0]
        msg = choice.message

        # --- TRACK SPEND ---
        usage = resp.usage
        if usage:
            prompt_tokens = usage.prompt_tokens or 0
            completion_tokens = usage.completion_tokens or 0
            total_input_tokens += prompt_tokens
            total_output_tokens += completion_tokens

            call_cost = (prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000
            session_cost += call_cost
            budget.RecordSpend(agent_id, call_cost, team_id)

        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_name = tc.function.name

                if tool_name not in allowed_tools:
                    result = {"status": "error", "message": f"Tool '{tool_name}' not allowed for {agent_id}"}
                    print(f"  BLOCKED: {tool_name} (not in allowed tools)")
                else:
                    try:
                        tool_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    print(f"  -> {tool_name}({json.dumps(tool_args, default=str)[:120]})")

                    impl = TOOL_IMPLS.get(tool_name)
                    if impl:
                        try:
                            result = impl(**tool_args)
                        except Exception as e:
                            result = {"status": "error", "message": str(e)}
                            traceback.print_exc()
                    else:
                        result = {"status": "error", "message": f"Unknown tool: {tool_name}"}

                # Detect empty check_results loops AFTER execution
                if tool_name == "check_results":
                    results_list = result.get("results", [])
                    if not results_list or len(results_list) == 0:
                        consecutive_empty_checks += 1
                    else:
                        consecutive_empty_checks = 0
                else:
                    consecutive_empty_checks = 0

                if consecutive_empty_checks >= 5:
                    print("  Stopping: 5 consecutive check_results calls with no progress")
                    bus.Log(agent_id, "Stopped: empty check_results loop detected")
                    return "[AGENT STOPPED: too many empty check_results calls — likely waiting with nothing to check]"

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
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result)
                })

            continue

        print(f"\n  Tokens in: {total_input_tokens}, out: {total_output_tokens}")
        print(f"  Session cost: ${session_cost:.6f}")
        print(f"  Budget status: {budget.GetStatus()[:200]}")
        return msg.content

    # max_turns reached
    cost_msg = f"Session cost: ${session_cost:.6f}"
    bus.Log(agent_id, f"Max turns reached. {cost_msg}")
    return f"[AGENT STOPPED: max_turns ({max_turns}) reached] {cost_msg}"


# ---------------------------------------------------------------------------
# POLLING LOOP — Worker agents
# ---------------------------------------------------------------------------

def WorkerLoop(agent_cfg, bus, budget, memory, providers_cfg):
    agent_id = agent_cfg["id"]
    team_id = agent_cfg.get("team", "default")

    print(f"\n{'='*60}")
    print(f"  {agent_id.upper()} [{team_id}] — waiting for tasks...")
    print(f"  Provider: {agent_cfg.get('provider', 'deepseek')}/{agent_cfg.get('model', 'deepseek-chat')}")
    print(f"  Watching: {bus.TaskDir}")
    print(f"  Budget: {budget.GetStatus()[:150]}")
    print(f"{'='*60}\n")

    bus.Log(agent_id, f"Started worker loop [{team_id}]")

    # Inject dependencies into tool functions
    create_task.bus = bus
    check_results.bus = bus
    send_feedback.bus = bus
    list_team.bus = bus
    team_remember.memory = memory
    team_remember.agent_id = agent_id
    team_recall.memory = memory

    try:
        while True:
            # Check budget before even claiming a task
            allowed, reason, _, _ = budget.CheckBudget(agent_id, team_id)
            if not allowed:
                print(f"  BUDGET STOP: {reason}")
                bus.Log(agent_id, f"Worker paused: {reason}")
                time.sleep(30)
                continue

            task = bus.ClaimTask(agent_id)

            if task:
                print(f"\n>>> TASK: {task['title']}")
                print(f"    ID: {task['task_id']}")
                print(f"    Description: {task['description'][:200]}...")

                task_prompt = f"""TASK: {task['title']}

{task['description']}

CONTEXT FROM PREVIOUS STEPS:
{json.dumps(task.get('context', {}), indent=2)}

When you have completed this task, provide your final output in the required format."""

                result = RunAgent(agent_cfg, task_prompt, bus, budget, memory, providers_cfg)

                bus.PostResult(
                    task_id=task["task_id"],
                    agent_id=agent_id,
                    status="complete",
                    data={"output": result},
                    summary=task["title"]
                )

                print(f"\n  TASK COMPLETE: {task['task_id']}")
                print(f"  Waiting for next task...\n")
            else:
                time.sleep(5)

    except KeyboardInterrupt:
        print(f"\n  [{agent_id}] Shutting down...")
        bus.Log(agent_id, "Worker loop stopped by user")


# ---------------------------------------------------------------------------
# ORCHESTRATOR MODE
# ---------------------------------------------------------------------------

def OrchestratorLoop(agent_cfg, goal, bus, budget, memory, providers_cfg):
    agent_id = "orchestrator"
    team_id = agent_cfg.get("team", "team_a")

    create_task.bus = bus
    check_results.bus = bus
    send_feedback.bus = bus
    list_team.bus = bus
    team_remember.memory = memory
    team_remember.agent_id = agent_id
    team_recall.memory = memory

    bus.Log(agent_id, f"Orchestrator started with goal: {goal[:100]}")

    prompt = f"""HIGH-LEVEL GOAL:
{goal}

Your job is to orchestrate the team to accomplish this goal.

Current team status:
{json.dumps(bus.GetTeamStatus(), indent=2)}

Budget status:
{budget.GetStatus()}

Break this down into subtasks and create them using the create_task tool.
Assign each subtask to the right specialist (researcher, coder, reviewer).

After creating tasks, wait for results using check_results, review them,
and if anything needs revision use send_feedback. Use team_remember to
store important findings so other agents can access them.

When all work is done and you're satisfied, provide the FINAL SUMMARY to the user."""

    result = RunAgent(agent_cfg, prompt, bus, budget, memory, providers_cfg)

    print("\n" + "="*60)
    print("  ORCHESTRATOR FINAL OUTPUT")
    print("="*60)
    print(result)

    return result


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Team Agent Loop")
    parser.add_argument("--agent", required=True,
                        help="Which agent role to run as")
    parser.add_argument("--team", default=None,
                        help="Team ID override (default: from agent yaml)")
    parser.add_argument("--task", default=None,
                        help="Task description (required for orchestrator)")
    parser.add_argument("--bus-dir", default="./team_bus",
                        help="Path to the shared message bus directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate without making API calls")

    args = parser.parse_args()

    ScriptDir = Path(__file__).resolve().parent
    BusDir = ScriptDir / args.bus_dir
    AgentsDir = ScriptDir / "agents"

    available_agents = sorted([f.stem for f in AgentsDir.glob("*.yaml")])

    if args.agent not in available_agents:
        print(f"ERROR: Unknown agent '{args.agent}'. Available: {', '.join(available_agents)}")
        sys.exit(1)

    agent_yaml = AgentsDir / f"{args.agent}.yaml"

    agent_cfg = LoadAgent(str(agent_yaml))

    # Override team if specified on command line
    if args.team:
        agent_cfg["team"] = args.team

    team_id = agent_cfg.get("team", "default")

    # Load providers, budget, and initialize services
    providers_cfg = LoadProviders(str(ScriptDir / "providers.yaml"))

    budget_cfg = yaml.safe_load((ScriptDir / "budget.yaml").read_text(encoding="utf-8"))
    tracker_file = budget_cfg.get("budget", {}).get("tracker_file", "./team_bus/budget_tracker.json")
    budget = BudgetTracker(budget_cfg, str(ScriptDir / tracker_file))

    bus = MessageBus(str(BusDir))
    memory = TeamMemory(team_id, str(BusDir / "memory"))

    print(f"\n  Budget status: {budget.GetStatus()}")

    if args.dry_run:
        print("\n  DRY RUN MODE — no API calls will be made")
        print(f"  Agent: {args.agent}")
        print(f"  Team: {team_id}")
        print(f"  Provider: {agent_cfg.get('provider', 'deepseek')}")
        print(f"  Model: {agent_cfg.get('model', 'deepseek-chat')}")
        sys.exit(0)

    if args.agent == "orchestrator":
        if not args.task:
            print("ERROR: --task is required for orchestrator mode")
            print("Example: python team_agent_loop.py --agent orchestrator --task 'Build a TODO app'")
            sys.exit(1)
        OrchestratorLoop(agent_cfg, args.task, bus, budget, memory, providers_cfg)
    else:
        WorkerLoop(agent_cfg, bus, budget, memory, providers_cfg)
