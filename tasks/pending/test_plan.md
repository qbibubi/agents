# TEST PLAN — Bottlenecks, Infinite Loops, and Logic Errors

Test each item before spending real API money. Use `--dry-run` for config validation, then single-agent tests with `max_turns: 3` and `budget.global_daily_cap: 0.05` for live tests.

---

## PHASE 1 — STATIC / NO-API TESTS (zero cost)

### T1: Agent YAML validation
**What:** Run `--dry-run` for every agent.
**Command:**
```
python team_agent_loop.py --agent orchestrator --task "test" --dry-run
python team_agent_loop.py --agent vulnerability_researcher --dry-run
python team_agent_loop.py --agent security_reviewer --dry-run
python team_agent_loop.py --agent test_programmer --dry-run
python team_agent_loop.py --agent coder --dry-run
python team_agent_loop.py --agent researcher --dry-run
python team_agent_loop.py --agent reviewer --dry-run
```
**Expected:** Each prints agent/team/provider/model and exits 0. No tracebacks.
**Failure mode:** Unknown agent error, YAML parse error, missing field crash.

### T2: Budget tracker file race simulation
**What:** Run two agent dry-runs simultaneously and verify budget_tracker.json isn't corrupted.
**Command (two terminals):**
```
# Terminal 1
python team_agent_loop.py --agent coder --dry-run
# Terminal 2 (same time)
python team_agent_loop.py --agent researcher --dry-run
```
**Expected:** Both complete. budget_tracker.json is valid JSON with no missing keys.
**Failure mode:** Corrupted JSON, missing state keys, one agent overwrites the other's spend.

### T3: Task lock orphan recovery
**What:** Create a .lock file manually, then run a worker and verify it cleans the stale lock.
**Steps:**
1. Create a dummy task file in team_bus/tasks/test_task.json with status="pending", assigned_to="coder"
2. Create team_bus/tasks/test_task.lock with some content
3. Wait 5 minutes (or temporarily change the 300-second threshold to 1 second in message_bus.py line 141)
4. Run: `python team_agent_loop.py --agent coder`
5. Check that the coder claims the task (stale lock cleaned)
**Expected:** Coder claims the task. Bus log shows "Cleaned stale lock for test_task".
**Failure mode:** Coder hangs, lock file persists, task never claimed.

### T4: Path traversal rejection
**What:** Write a malicious task description that asks the agent to write_file to `../../outside.txt`.
**Steps:**
1. Manually create a task JSON assigning to coder, description: "write_file to ../../outside.txt with content 'test'"
2. Run coder with max_turns=2
3. Check result
**Expected:** Agent returns error "Path traversal blocked: ../../outside.txt". No file created outside CWD.
**Failure mode:** File written outside project directory.

### T5: Disabled run_shell rejection
**What:** Agent attempts to call run_shell.
**Steps:**
1. Create a task assigning to any agent that does NOT have run_shell in its whitelist
2. Description asks: "try calling run_shell with command dir"
3. Run agent
**Expected:** Tool blocked message. If the coder YAML still had run_shell (Item 5 fix), verify it's now removed.
**Failure mode:** Shell command executes.

---

## PHASE 2 — SINGLE-AGENT LIVE TESTS (budget: $0.05 total)

Set budget.yaml: `global_daily_cap: 0.05` before these tests.
Set each agent's max_turns to 3 for these tests.

### T6: Single agent completes a trivial task
**What:** Run coder with a task that requires one read_file and one response.
**Steps:**
1. Create a task JSON: assigned_to="coder", description="Read the file agents/coder.yaml and tell me what tools are listed."
2. Run coder with max_turns=3
**Expected:** Agent reads file, lists tools, posts result. Cost < $0.01.
**Failure mode:** Agent loops through all 3 turns without answering, API error, budget tracker crashes.

### T7: Budget cap enforced mid-session
**What:** Set agent cap to $0.001 and verify it blocks.
**Steps:**
1. Set coder daily cap to 0.001 in budget.yaml
2. Run coder on a task that requires multiple turns
3. Watch for BUDGET STOP message
**Expected:** After first API call (~$0.0003), second call triggers cap. Agent halts with clear message.
**Failure mode:** Cap ignored, agent continues spending.

### T8: check_results loop detection
**What:** Create a scenario where the orchestrator calls check_results 5 times with no results.
**Steps:**
1. Run orchestrator with a task "Test: just call check_results repeatedly"
2. Set max_turns=10
3. No workers running, so no results will ever appear
**Expected:** After 5 empty check_results calls, agent stops with "too many empty check_results calls".
**Failure mode:** Agent burns all 10 turns calling check_results, costs ~$0.01+ in empty polling.

### T9: max_turns hard stop
**What:** Give an agent an impossible task and verify it stops at max_turns.
**Steps:**
1. Set max_turns=2 for coder
2. Create task: "Count to 100, one number per turn" (LLM will likely tool-call)
3. Run coder
**Expected:** Stops at turn 2 with "AGENT STOPPED: max_turns (2) reached". Cost printed.
**Failure mode:** Agent exceeds max_turns, loop condition broken.

---

## PHASE 3 — TWO-AGENT INTERACTION TESTS (budget: $0.10 total)

### T10: Orchestrator creates task, worker claims it
**What:** Run orchestrator + one worker. Orchestrator creates a task, worker picks it up.
**Steps:**
1. Terminal 1: `python team_agent_loop.py --agent researcher` (worker)
2. Terminal 2: `python team_agent_loop.py --agent orchestrator --task "Research what tools are available in this codebase by reading team_agent_loop.py"`
3. Watch both terminals
**Expected:**
- Orchestrator creates a task assigned to "researcher"
- Researcher claims it within 5 seconds
- Researcher reads file, posts result
- Orchestrator finds result, prints FINAL SUMMARY
**Failure mode:** Task created but never claimed (assignment mismatch), orchestrator loops on check_results (empty check detection kills it), result posted but orchestrator never finds it.

### T11: Revision loop terminates
**What:** Orchestrator creates task, reviewer rejects it, coder revises, reviewer approves.
**Steps:**
1. Run orchestrator + coder + reviewer
2. Task: "Create a file called test.txt with content 'hello'"
3. Set max_turns=5 for all agents
**Expected:** Flow completes or terminates with a clear reason. Does NOT loop infinitely on revisions.
**Failure mode:** Feedback→revision→feedback→revision infinite loop. This is the highest-risk cost scenario.

### T12: Budget shared correctly across agents
**What:** Three agents share a team cap, verify aggregate enforcement.
**Steps:**
1. Set team_a daily cap: 0.02
2. Run coder + researcher + reviewer on a complex task
3. Watch budget status across all agents
**Expected:** When combined spend hits $0.02, all agents pause. Individual agents don't exceed team cap independently.
**Failure mode:** Agents spend past team cap, team cap only checked per-agent not aggregate.

---

## PHASE 4 — EDGE CASES

### T13: Empty bus directory on startup
**What:** Delete team_bus/ entirely, then run an agent.
**Expected:** Agent recreates directories, starts normally. No crash.
**Failure mode:** FileNotFoundError, mkdir race.

### T14: Corrupted task JSON
**What:** Manually create a task file with invalid JSON (missing brace).
**Expected:** Agent skips it gracefully, logs the error, continues polling.
**Failure mode:** Agent crashes, stops polling permanently.

### T15: Two workers of same type claim different tasks
**What:** Run two coder processes simultaneously with two pending coder tasks.
**Expected:** Each claims a DIFFERENT task. Lockfile prevents double-claim.
**Failure mode:** Both claim same task (TOCTOU race), or one starves.

### T16: Provider fallback on missing model
**What:** Set coder model to "nonexistent-model" in coder.yaml.
**Expected:** Warning printed, price defaults to $0.0, but agent still runs (uses deepseek base URL). Cost tracks at $0.
**Failure mode:** Crash, or cost silently unaccounted.

### T17: Memory survives agent restart
**What:** Run researcher, it stores to team memory. Kill it. Run it again.
**Expected:** Second run sees entries from first run via team_recall.
**Failure mode:** Memory file corrupted, entries lost, team_recall returns empty.

### T18: Track max_turns hits for agent tuning
**What:** After each test run, check whether any agent hit max_turns. This data informs whether agent YAML turn limits need adjustment (e.g., researcher at 15 vs 20).
**Steps:**
1. After any test run, grep agent logs for "AGENT STOPPED: max_turns"
   ```bash
   grep -r "AGENT STOPPED: max_turns" team_bus/logs/
   ```
2. If any agent consistently hits max_turns across multiple tasks, bump its limit by 5.
3. If any agent never exceeds 50% of its max_turns, consider lowering it.
**Expected:** Infrequent max_turns hits during normal operation. Frequent hits indicate a task-scoping or turn-limit problem.

---

## KNOWN UNSOLVED ISSUES (documented, not fixed yet)

### U1: Revision chain depth unbounded
`SendFeedback` has no `revision_count` or `max_revisions`. A 10-deep revision chain is 10 full agent task cycles. Mitigation: keep max_turns low during testing, watch for "REVISION:" task titles in logs.

### U2: Orchestrator can't programmatically detect completion
No signal injected into orchestrator prompt like "ALL TASKS COMPLETE" vs "NO TASKS CREATED YET". Mitigation: the orchestrator prompt tells it to synthesize when satisfied; test T11 validates this doesn't loop.

### U3: Budget RecordSpend race on concurrent agents
`ResetIfNeeded()` reads state, then `RecordSpend` modifies and writes. Between read and write, another agent can update the same counters. This is a real race but low-impact (sub-cent precision loss). Fix would require a lockfile around the full read-modify-write.

### U4: Worker polls forever after orchestrator exits
Workers have no "orchestrator disconnected" detection. Mitigation: Ctrl+C to stop workers after orchestrator finishes.

---

## TEST SEQUENCE (run in this order)

1. T1 (dry-run all agents) — 0 cost, catches config errors
2. T13 (empty bus dir) — 0 cost
3. T14 (corrupted JSON) — 0 cost, manual setup
4. T5 (disabled shell) — 0 cost, manual setup
5. T4 (path traversal) — 0 cost, manual setup
6. T6 (single agent trivial) — first API spend, ~$0.003
7. T9 (max_turns stop) — validates safety net, ~$0.003
8. T7 (budget cap) — validates budget enforcement, ~$0.002
9. T8 (empty check loop) — validates polling guard, ~$0.005
10. T10 (two-agent interaction) — validates bus, ~$0.02
11. T12 (shared budget) — validates team cap, ~$0.03
12. T11 (revision loop) — highest-risk cost test, ~$0.05
13. T15 (concurrent workers) — validates lock, ~$0.02
14. T16 (missing model fallback) — validates provider resolution, ~$0.005
15. T17 (memory persistence) — validates team memory, ~$0.01

Total estimated API cost for all tests: ~$0.15
