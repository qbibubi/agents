# PROGRAMMER AGENT — Full Project Context

This document contains everything you need to understand, maintain, and extend this codebase. Read it fully before making any changes.

---

## WHAT THIS PROJECT IS

An AI agent team framework where multiple LLM-powered agents collaborate through a shared file-based message bus. Each agent has a specialized role (researcher, coder, reviewer, etc.), tools it's allowed to use, a budget cap, and a system prompt that defines its behavior. Agents communicate by writing task JSON files and reading result JSON files — no direct IPC.

The framework is team-agnostic: the same loop, bus, budget tracker, and memory system work for a code dev team, a security audit team, a finance research team, or any other domain. The domain-specific behavior lives entirely in YAML files under `agents/`.

---

## FILE MAP

### Core Runtime (Python)

**`team_agent_loop.py`** — Main entry point. Contains:
- Tool implementations (read_file, write_file, search_code, list_directory, run_tests, web_search, create_task, check_results, send_feedback, list_team, team_remember, team_recall)
- Provider resolution logic (maps agent YAML's provider/model to base_url, API key, pricing)
- `RunAgent()` — the core loop: system prompt + task → LLM call → tool call handling → spend tracking → repeat until final answer or max_turns
- `WorkerLoop()` — polling loop for worker agents: wait for task, claim it, run agent, post result, repeat
- `OrchestratorLoop()` — one-shot mode: gets a high-level goal, creates subtasks, waits for results, produces final summary
- CLI argument parsing (--agent, --team, --task, --bus-dir, --dry-run)
- Dynamic agent discovery from agents/ directory (no hardcoded choices)

**`message_bus.py`** — File-based communication layer. Contains:
- `AtomicWriteJson()` — write-temp-then-rename pattern, atomic on Windows and POSIX
- `ReadJsonRetry()` — retry with backoff for concurrent rename edge cases
- `MessageBus` class with all task CRUD, result CRUD, feedback/revision, logging, and status
- `ClaimTask()` with lockfile (O_CREAT | O_EXCL) + stale lock detection (300s threshold)
- `SendFeedback()` with context truncation (2000 chars) to prevent revision bloat

**`budget_tracker.py`** — Spending enforcement. Contains:
- `BudgetTracker` class — loads budget.yaml, tracks spend per agent/team/global
- `CheckBudget()` — agent cap → team cap → global cap, first-cap-wins, with block/local/warn policies
- `RecordSpend()` — updates counters after each API call (has known read-modify-write race under concurrency, sub-cent impact)
- Auto-reset at midnight UTC (daily) and 1st of month (monthly)
- 80% warning threshold
- Imports `AtomicWriteJson` from message_bus

**`team_memory.py`** — Per-team shared knowledge store. Contains:
- `TeamMemory` class — append-only with deduplication by topic name
- `Add()` — stores a finding, updates if same topic exists
- `Query()` — keyword, tag, and source_agent filtering
- `GetContextForAgent()` — produces a condensed string injected into task prompts
- Imports `AtomicWriteJson` from message_bus

**`dashboard.py`** — Real-time terminal dashboard. Polls the bus every 5 seconds, shows task counts by status and agent, recent activity from logs, recent results.

### Configuration (YAML)

**`providers.yaml`** — Model provider registry. 5 providers defined:
- deepseek (api.deepseek.com): deepseek-chat ($0.14/$0.28), deepseek-reasoner ($0.55/$2.19)
- openai (api.openai.com): gpt-4o, gpt-4o-mini, gpt-3.5-turbo
- anthropic (api.anthropic.com): claude-3-5-sonnet, claude-3-haiku
- local (localhost:11434): llama3-70b, llama3-8b, mistral, codellama — all free
- openrouter (openrouter.ai): multi-provider access
- Default: deepseek/deepseek-chat

**`budget.yaml`** — Spending limits:
- Global: $5/day, $50/month
- Per-team: team_a/b/c each $2/day, $20/month
- Per-agent: default $1/day, overrides for orchestrator ($1.50), coder ($1.00), researcher ($0.75), reviewer ($0.50)
- Overage policy: "block" (also supports "warn" and "local" fallback)
- Warn at 80%

**`team.yaml`** — Team manifest (informational, not enforced by code):
- Defines workflow: researcher→coder→reviewer→orchestrator
- Lists members and their YAML file paths
- Declares polling interval (5s) and task timeout (30min) — these are currently decorative, not enforced

### Agent Definitions (YAML)

**Original Dev Team** (`agents/`):
- `orchestrator.yaml` — Team lead, breaks down goals, assigns tasks, synthesizes results. Max 20 turns.
- `researcher.yaml` — Investigates APIs/docs/codebase, produces specs. Authority: recommend. Max 15 turns.
- `coder.yaml` — Implements features, writes code. Authority: execute. Max 25 turns. Note: run_shell was removed from its tools (see audit fix Item 5).
- `reviewer.yaml` — Reviews code for bugs/security/style. Authority: recommend. Max 15 turns.

**Security Audit Team** (`agents/`):
- `security_orchestrator.yaml` — Audit lead, prioritizes attack surface. Max 25 turns. Safety rule: never authorize destructive testing.
- `vulnerability_researcher.yaml` — Maps attack surfaces, finds CVEs, traces trust boundaries. Authority: recommend. Max 20 turns.
- `test_programmer.yaml` — Writes safe PoC code. ALL PoCs must be read-only demonstrations. Authority: execute. Max 25 turns.
- `security_reviewer.yaml` — Validates findings, assigns CVSS scores, eliminates false positives. Authority: recommend. Max 20 turns.

### Supporting Files

- `start_team.bat` — Windows launcher, opens 3 worker windows + orchestrator
- `README.md` — Full documentation: architecture, task lifecycle, agent YAML structure, provider config, budget system, team memory, multi-team usage, tool reference, safety features, limitations
- `tasks/pending/coder_audit_fixes.md` — 10 audit items (all fixed now, kept for reference)
- `tasks/pending/test_plan.md` — 17 test cases across 4 phases, estimated $0.15 total cost

---

## HOW THE LOOP WORKS (trace through)

### Worker Agent Startup
1. CLI parses `--agent vulnerability_researcher`
2. Scans `agents/` for `vulnerability_researcher.yaml`
3. Loads agent config, providers, budget, initializes bus + memory
4. If `--dry-run`: prints config, exits
5. Otherwise: enters `WorkerLoop()`

### Worker Loop (polling)
1. Check budget (agent→team→global). If blocked, sleep 30s, recheck.
2. `ClaimTask("vulnerability_researcher")` — lists pending tasks, sorts by priority+time, attempts lockfile claim
3. If no task: sleep 5s, goto 1
4. If task claimed: build task prompt with context, call `RunAgent()`
5. Post result, goto 1

### RunAgent (per-task execution)
1. Resolve provider → base_url, api_key, model name, pricing
2. Create OpenAI client
3. Build tool schemas from YAML (only whitelisted tools)
4. Inject team memory context into task prompt
5. Build messages: [system_prompt, user_task]
6. For each turn up to max_turns:
   a. Check budget before API call (may switch to local fallback if overage policy is "local")
   b. Call LLM with messages + tools
   c. Track spend (prompt_tokens × input_price + completion_tokens × output_price) / 1M
   d. If no tool calls: return final answer
   e. If tool calls: execute each tool (block disallowed tools), append assistant+tool messages
   f. Detect empty check_results loop (5 consecutive empty → stop)
7. If max_turns reached: return stop message with cost

### Orchestrator (one-shot)
1. Same as worker but calls `OrchestratorLoop()` instead of `WorkerLoop()`
2. Gets goal from --task argument
3. Prompt includes goal + team status + budget status
4. LLM creates tasks via create_task tool, waits via check_results, revises via send_feedback
5. When LLM decides work is done, it outputs FINAL SUMMARY
6. Exits (does not poll for more work)

---

## TOOL SAFETY NOTES

| Tool | Safety Mechanism |
|---|---|
| read_file | Truncated at 8000 chars, read-only |
| write_file | Blocks path traversal (resolved path must start with CWD) |
| search_code | shell=False, hardcoded grep command |
| list_directory | Read-only, capped at 100 entries |
| run_tests | Allowlist: pytest, npm test, cargo test, go test only. shell=False, shlex.split |
| run_shell | DISABLED — always returns error |
| web_search | Placeholder, no actual network call |
| create_task | Writes to bus only |
| check_results | Read-only. Has loop detection (5 empty calls = stop) |
| send_feedback | Creates revision task (potential revision chain, but context truncated) |

---

## KEY DESIGN DECISIONS

1. **YAML is the domain layer.** Adding a new agent or team means adding YAML files. The Python code should never need changes for new agent types.
2. **Atomic writes everywhere.** Every JSON write uses write-temp-then-rename. This was a critical audit finding.
3. **Budget checked before every API call, not just at task start.** An agent that's over cap mid-task halts immediately.
4. **Tools are whitelisted per agent.** The LLM sees only the tool schemas for tools in the agent's YAML. The dispatcher also blocks any tool not in the whitelist (defense in depth).
5. **Team memory is injected into every task prompt.** Agents always see what their team already knows before starting work.
6. **Revision loops have context truncation.** SendFeedback caps prior output at 2000 chars to prevent 3× growth per revision cycle.

---

## KNOWN ISSUES (do not fix unless asked)

1. **Revision chain depth unbounded.** SendFeedback has no max_revisions. A 10-deep revision chain creates 10 full agent task cycles. Mitigated by max_turns.
2. **Budget RecordSpend race.** ResetIfNeeded() reads state, then RecordSpend modifies and writes. Two concurrent agents can lose sub-cent precision. Would need a lockfile around the full read-modify-write.
3. **Orchestrator completion detection.** No programmatic "all tasks done" signal injected into the prompt. The LLM decides when work is complete.
4. **Worker polls forever.** After orchestrator exits, workers keep polling. No "orchestrator disconnected" detection.
5. **Orchestrator on fresh bus.** GetTeamStatus returns 0/0/0 for both "no tasks created yet" and "all tasks complete". The orchestrator could misinterpret.
6. **team.yaml poll_interval_seconds and task_timeout_minutes** are defined in YAML but not read by any code. The actual poll interval is hardcoded at 5 seconds in WorkerLoop.

---

## CODING CONVENTIONS

- `{` on new line, always used (even one-liners)
- CapitalCase for globals and struct members: `BusDir`, `TaskDir`, `AtomicWriteJson`
- lower_case for params and locals: `agent_id`, `task_path`
- No `g_` or `s_` prefixes
- No std, crt, or stl — use the project's own string.h, math.h, containers.h equivalents (but this is Python, so standard library is fine)
- Blank lines between struct/class definitions and logical blocks
- No comments describing WHAT code does (identifiers should do that). Comments only for WHY (non-obvious constraints, bug workarounds)

---

## QUICK REFERENCE: Running the System

```bash
# Dry-run (no cost)
python team_agent_loop.py --agent coder --dry-run

# Single worker
python team_agent_loop.py --agent researcher

# Orchestrator with goal
python team_agent_loop.py --agent orchestrator --task "Audit message_bus.py"

# Security team
python team_agent_loop.py --agent security_orchestrator --team security_team --task "Audit the framework"
python team_agent_loop.py --agent vulnerability_researcher --team security_team
python team_agent_loop.py --agent test_programmer --team security_team
python team_agent_loop.py --agent security_reviewer --team security_team

# Dashboard
python dashboard.py
```
