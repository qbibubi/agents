# AI Agentic Team Framework

A file-based multi-agent collaboration system where specialized AI agents communicate through a shared message bus, with budget enforcement, multi-provider model routing, and team memory.

## Architecture

```
C:/dev/agents/
├── team_agent_loop.py      # Main runtime — every agent session runs this
├── message_bus.py           # File-based task/result communication layer
├── budget_tracker.py        # Spending enforcement across agents and teams
├── team_memory.py           # Per-team shared knowledge store
├── dashboard.py             # Real-time team status monitor
├── start_team.bat           # Windows launcher for all agents
│
├── providers.yaml           # Model provider registry with pricing
├── budget.yaml              # Spending limits configuration
├── team.yaml                # Team manifest and workflow definition
│
├── agents/                  # Agent definitions (one YAML per role)
│   ├── orchestrator.yaml
│   ├── researcher.yaml
│   ├── coder.yaml
│   └── reviewer.yaml
│
└── team_bus/                # Shared communication directory (created at runtime)
    ├── tasks/               # Task JSON files — agents claim work here
    ├── results/             # Result JSON files — agents post output here
    ├── logs/                # Per-agent log files
    ├── memory/              # Per-team knowledge store JSON files
    └── budget_tracker.json  # Persistent spend tracking state
```

## How It Works

### Communication Model

Agents communicate exclusively through the file-based message bus. There is no direct inter-process communication.

1. **Orchestrator** receives a high-level goal, breaks it into subtasks, and writes task JSON files to `team_bus/tasks/`
2. **Worker agents** poll `team_bus/tasks/` every 5 seconds, claim the highest-priority task assigned to them, execute it via the LLM, and post results to `team_bus/results/`
3. **Orchestrator** polls `team_bus/results/`, reviews output, sends feedback if needed (creates a revision task), and synthesizes the final answer

### Task Lifecycle

```
pending → claimed (in_progress) → completed
                                      ↓ (if rejected)
                                  revision task (priority 1)
```

A task JSON looks like:

```json
{
  "task_id": "task_a1b2c3d4e5f6",
  "assigned_to": "coder",
  "priority": 2,
  "status": "pending",
  "title": "Implement user authentication",
  "description": "Detailed instructions with context from previous steps...",
  "context": { "spec": "...", "files_to_create": ["auth.py"] },
  "output_format": "json",
  "parent_task_id": null,
  "created_at": "2026-07-21T22:00:00Z",
  "claimed_at": null,
  "completed_at": null
}
```

### Agent YAML Structure

Every agent is defined by a YAML file. This is the only thing that changes between teams. The framework (loop, bus, budget, memory) is team-agnostic.

```yaml
id: "agent-name"                # Unique ID, used for task assignment
provider: "deepseek"            # References providers.yaml
model: "deepseek-chat"          # Model name within that provider
team: "team_a"                  # Team ID for budget and memory isolation
temperature: 0.3
max_turns: 15                   # Safety: hard stop after N LLM calls per task

position:                       # Metadata about the role (not enforced by code)
  title: "Title"
  reports_to: "orchestrator"
  can_delegate_to: []
  authority_level: "recommend"  # "execute" | "recommend" | "observe_only"

system_prompt: |                # Injected as system message on every LLM call
  You are a...
  YOUR RULES:
  1. ...
  OUTPUT FORMAT:
  When done, output a JSON block...

tools:                          # Whitelist of tools this agent can call
  - name: tool_name
    description: "What it does"
    parameters:
      param_name:
        type: string
        description: "..."
        required: true
```

Key points:
- `id` is the task routing key — tasks with `assigned_to: "coder"` go to the agent with `id: "coder"`
- `max_turns` caps LLM calls per task, not per session. A worker processes unlimited tasks until interrupted
- `system_prompt` defines the agent's entire personality, rules, and output format. Make it detailed
- `tools` is a whitelist. The agent physically cannot call tools not listed here, even if the LLM tries
- `provider` and `model` can differ per agent — researcher uses GPT-4o while reviewer uses local Llama

## Provider and Model Configuration

`providers.yaml` registers every available model provider with their base URLs, API key environment variables, and per-million-token pricing.

```yaml
providers:
  deepseek:
    base_url: "https://api.deepseek.com/v1"
    api_key_env: "DEEPSEEK_API_KEY"
    models:
      deepseek-chat:
        input_price: 0.14      # USD per 1M input tokens
        output_price: 0.28     # USD per 1M output tokens
```

### Adding a New Provider

1. Add a block under `providers:` with `base_url`, `api_key_env`, and at least one model
2. Set the `DEEPSEEK_API_KEY` (or equivalent) environment variable
3. Reference it in an agent YAML: `provider: "your-provider"`, `model: "your-model"`

### Supported Providers Out of the Box

| Provider | Base URL | Pricing |
|---|---|---|
| DeepSeek | api.deepseek.com | Paid per token |
| OpenAI | api.openai.com | Paid per token |
| Anthropic | api.anthropic.com | Paid per token |
| Local (Ollama) | localhost:11434 | Free |
| OpenRouter | openrouter.ai | Paid per token, multi-provider |

### Local Models (Free)

Install Ollama, pull a model, and use:

```yaml
provider: "local"
model: "llama3-8b"
```

All local models have `input_price: 0.0, output_price: 0.0` — they don't count against budgets.

## Budget System

### Configuration (`budget.yaml`)

```yaml
budget:
  global_daily_cap: 5.00       # Hard stop for ALL agents combined
  global_monthly_cap: 50.00

  team_caps:                    # Per-team sub-limits
    team_a:
      daily: 2.00
      monthly: 20.00

  agent_caps:
    default:                    # Applied to any agent without an override
      daily: 1.00
      monthly: 10.00
    overrides:                  # Per-agent overrides (optional)
      orchestrator:
        daily: 1.50
      reviewer:
        daily: 0.50

  overage_policy: "block"      # "block" | "warn" | "local"
  fallback_provider: "local"   # Used when overage_policy is "local"
  fallback_model: "llama3-8b"
  warn_at_percent: 80          # Log warning when spend hits this % of cap
```

### Enforcement Rules

1. **Before every API call**, the budget tracker checks agent cap, then team cap, then global cap — in that order
2. **First cap hit wins** — if agent cap is at limit, it blocks even if team/global have room
3. **`block` policy**: agent halts and waits 30 seconds before rechecking (caps reset daily/monthly)
4. **`local` policy**: agent automatically switches to the fallback local model and continues with zero cost
5. **`warn` policy**: logs a warning but allows the call (dangerous — not recommended)
6. **Warnings at 80%**: when any cap reaches 80%, the agent prints and logs a warning but continues

### Spend Tracking

Spend is persisted to `team_bus/budget_tracker.json`:

```json
{
  "global": { "daily": 0.0234, "monthly": 1.2456 },
  "teams": {
    "team_a": { "daily": 0.0234, "monthly": 1.2456 }
  },
  "agents": {
    "coder": { "daily": 0.0120, "monthly": 0.8900 }
  },
  "daily_reset_at": "2026-07-21",
  "monthly_reset_at": "2026-07"
}
```

Resets happen automatically:
- **Daily**: when `daily_reset_at` doesn't match the current UTC date
- **Monthly**: when `monthly_reset_at` doesn't match the current UTC month

To reset all spend immediately: delete `team_bus/budget_tracker.json`.

### Cost Calculation

After each API call, cost is calculated as:

```
cost = (prompt_tokens × input_price + completion_tokens × output_price) / 1,000,000
```

Prices come from `providers.yaml` for the model being used. If the model isn't found in the registry, price defaults to $0.0 (free) — this is a safety default, not an error.

### Caps for 9-12 Agents

With 3-4 teams of 3-4 agents each, reasonable starting caps:

```yaml
budget:
  global_daily_cap: 10.00
  team_caps:
    team_a: { daily: 3.00 }
    team_b: { daily: 3.00 }
    team_c: { daily: 3.00 }
    team_d: { daily: 3.00 }
  agent_caps:
    default: { daily: 1.00 }
```

This gives each agent $1/day, each team $3/day, and $10/day total. Adjust based on observed spend from test runs.

## Team Memory

Each team has an isolated knowledge store at `team_bus/memory/{team_id}.json`. Agents use two tools:

- `team_remember(topic, content, confidence, tags)` — store a finding. Deduplicates by topic name.
- `team_recall(keyword, tag, limit)` — query past findings by keyword, tag, or get recent entries.

Memory context is automatically injected into every task prompt, so agents see what their team already knows before they start working. This prevents the researcher and coder from independently discovering the same information.

Memory is team-isolated: Team A cannot read Team B's memory.

## Running the System

### Prerequisites

```bash
pip install openai pyyaml
```

**Windows users**: the `search_code` tool uses `grep`, which is not included with
vanilla Windows. Install Git Bash (which includes grep) or install ripgrep
(`choco install ripgrep` / `winget install BurntSushi.ripgrep.MSVC`) and update
the command in `team_agent_loop.py` line 76 if using ripgrep.

Set API keys as environment variables:

```bash
set DEEPSEEK_API_KEY=sk-your-key-here
set OPENAI_API_KEY=sk-your-key-here   # if using OpenAI models
```

### Starting a Team

Open 4 terminal windows:

```bash
# Window 1 — Orchestrator (gets the goal, creates tasks)
python team_agent_loop.py --agent orchestrator --task "Build a user auth system"

# Window 2 — Researcher (polls for research tasks)
python team_agent_loop.py --agent researcher

# Window 3 — Coder (polls for coding tasks)
python team_agent_loop.py --agent coder

# Window 4 — Reviewer (polls for review tasks)
python team_agent_loop.py --agent reviewer
```

Or use the launcher: `start_team.bat "Build a user auth system"`

### Monitoring

```bash
python dashboard.py
```

Shows live task counts, agent status, recent activity, and recent results. Refreshes every 5 seconds.

### Dry Run (No API Calls)

```bash
python team_agent_loop.py --agent coder --dry-run
```

Prints configuration and exits without calling any LLM. Use this to verify setup.

### Multi-Team Usage

```bash
# Team A
python team_agent_loop.py --agent coder --team team_a

# Team B (different terminal, isolated memory and budget)
python team_agent_loop.py --agent coder --team team_b
```

Each team needs its own agent YAMLs with matching `team:` fields. Budget and memory isolate by team ID.

### Using Different Models Per Agent

Edit the agent YAML:

```yaml
# agents/coder.yaml — expensive model for critical work
provider: "openai"
model: "gpt-4o"

# agents/reviewer.yaml — free local model for high-volume reviews
provider: "local"
model: "llama3-8b"
```

## Creating a New Team (Non-Coding Domain)

To create a finance research team, only agent YAMLs are needed:

```
agents/
  orchestrator.yaml          # id: orchestrator, team: finance_team
  analyst.yaml               # id: analyst, tools: web_search, team_recall, team_remember
  risk_assessor.yaml         # id: risk_assessor, tools: web_search
  report_writer.yaml         # id: report_writer, tools: write_file, read_file
```

Agent YAMLs live flat under `agents/`, NOT in subdirectories. The agent
loop scans `agents/*.yaml` (non-recursive). Team isolation comes from the
`team:` field in each YAML, not from directory nesting.

Each YAML defines:
- Its own `system_prompt` with domain-specific rules and output format
- Its own `tools` whitelist (no code tools needed)
- Its own `max_turns`, `temperature`, `provider`, and `model`

The framework (loop, bus, budget, memory) is reused with zero changes.

Run it:

```bash
python team_agent_loop.py --agent analyst --team finance_team
```

## Single Agent Demo

The `single_agent_demo/` directory contains a standalone, self-contained example
of the agent loop without team coordination, budget tracking, or the message bus.
It's useful for learning the core agent loop concept before adding multi-agent
complexity. Run it with:

```bash
cd single_agent_demo
python agent_loop.py "Review the code in ./src for security issues"
```

Note: the demo has the same safety fixes as the main framework (shell=False,
shlex.split, allowlist on run_tests).

## Tool Reference

### Available Tool Implementations

| Tool | Description | Safety |
|---|---|---|
| `read_file` | Read file contents (truncated at 8000 chars) | Safe |
| `write_file` | Create/overwrite a file | Blocks path traversal outside CWD |
| `search_code` | grep with file type filtering | Safe (read-only) |
| `list_directory` | List files and subdirectories | Safe (read-only) |
| `run_tests` | Execute test commands | Allowlist: pytest, python -m pytest, npm test, cargo test, go test only |
| `run_shell` | Execute arbitrary shell commands | **DISABLED** — returns error always |
| `web_search` | Search the web | Placeholder, requires external API setup (see Web Search Setup below) |
| `create_task` | Create a task for another agent | Safe |
| `check_results` | Check for completed task results | Has loop detection (5 empty checks = stop) |
| `send_feedback` | Send revision request to an agent | Safe |
| `list_team` | Get team task status | Safe |
| `team_remember` | Store finding in team memory | Safe |
| `team_recall` | Query team memory | Safe |

### Adding a New Tool

1. Implement the function in `team_agent_loop.py` with the `@register("tool_name")` decorator
2. Add the tool definition to each agent YAML that should have access
3. If the tool needs the bus or memory, inject it before the worker loop starts (see existing patterns for `create_task.bus = bus`)

## Safety Features

| Feature | What It Prevents |
|---|---|
| Budget caps (agent/team/global) | Unlimited API spend |
| `max_turns` per task | Runaway loops burning tokens per task |
| `check_results` loop detection | Polling burning tokens with no progress |
| `shell=True` disabled | LLM executing destructive commands |
| `run_tests` allowlist | LLM running arbitrary shell commands through tests |
| `write_file` path traversal block | LLM writing outside project directory |
| Tool whitelist per agent | Agent using tools it shouldn't have |
| 30-second budget recheck | Agent pausing instead of tight-looping when capped |

## Web Search Setup

The `web_search` tool is a placeholder by default — it returns a "not configured"
message. To enable it, edit the `web_search` function in `team_agent_loop.py` to
call one of these APIs:

- **Brave Search**: Get an API key at https://brave.com/search/api/ and set
  `BRAVE_SEARCH_API_KEY` env var. Call `https://api.search.brave.com/res/v1/web/search`.
- **SerpAPI**: Get a key at https://serpapi.com/ and set `SERPAPI_API_KEY`.
  Call `https://serpapi.com/search?q=...&api_key=...`.
- **Google Custom Search**: Requires a Google Cloud API key + Custom Search Engine CX.

If web_search is not configured, agents that have it in their whitelist will
receive the placeholder response and should work with local files only.

## Limitations

- **Polling latency**: workers check for tasks every 5 seconds, adding up to 5s delay per handoff. Note: the `poll_interval_seconds` field in `team.yaml` is currently decorative — the actual interval is hardcoded in `WorkerLoop`.
- **File I/O under load**: 9-12 agents reading/writing JSON in the same directory can cause contention on Windows
- **No push notifications**: agents don't wake each other up; the polling model is inherently latent
- **No cross-team communication**: teams are fully isolated by design. For cross-team contracts, you'd need a shared contracts directory
- **Task context bloat**: `SendFeedback` embeds full prior task and result, growing context on each revision
- **Local models require Ollama setup**: not zero-config for free tier

## Configuration Quick Reference

| File | Purpose | Required? |
|---|---|---|
| `providers.yaml` | Model registry | Yes |
| `budget.yaml` | Spending limits | Yes |
| `team.yaml` | Team manifest | No (informational) |
| `agents/*.yaml` | Agent definitions | Yes (one per agent role) |

Environment variables needed:
- `DEEPSEEK_API_KEY` — for DeepSeek models
- `OPENAI_API_KEY` — for OpenAI models
- `ANTHROPIC_API_KEY` — for Anthropic models
- `LOCAL_LLM_KEY` — can be any value for local models (not validated)
- `OPENROUTER_API_KEY` — for OpenRouter models
