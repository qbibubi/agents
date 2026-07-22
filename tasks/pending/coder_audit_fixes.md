# AUDIT FIXES — Step-by-Step

Fix each item in order. After each fix, report: item number, what you changed, which file and lines. Do NOT skip items or reorder them. If an item is unclear, flag it and move to the next.

---

## CRITICAL

### Item 1 — `run_tests` shell injection (CRITICAL)

**File:** `team_agent_loop.py`, lines 103-121

**Problem:** The allowlist checks `command.startswith("pytest")` but `shell=True` means `pytest & del /Q /S something` executes both commands.

**Fix:**
- Remove `shell=True`
- Use `shlex.split(command)` to parse the command into a list
- Pass the list to `subprocess.run` with `shell=False`
- Add `import shlex` at the top of the file
- The allowlist check still runs against the original string before splitting

---

### Item 2 — `check_results` loop detection false-positive (HIGH)

**File:** `team_agent_loop.py`, lines 374-385

**Problem:** The counter increments for EVERY `check_results` call, even ones returning results. The orchestrator polling for completions gets killed after 5 calls regardless.

**Fix:**
- After the tool call executes, check if the result actually contains results (e.g., `result.get("results")` is an empty list or has no entries)
- Only increment `consecutive_empty_checks` when the result is truly empty
- Reset to 0 when results are found
- You'll need to move the empty-check logic AFTER the tool call result comes back, not before it (currently it checks `tc.function.name` before execution)

---

## HIGH

### Item 3 — Budget tracker `SaveState` not atomic (HIGH)

**File:** `budget_tracker.py`, lines 42-43

**Problem:** `SaveState()` uses plain `write_text()`. Under concurrent agent spend updates, writes interleave and spend events get lost.

**Fix:**
- Import `AtomicWriteJson` from `message_bus` (or duplicate the function into this file — your call, but importing is cleaner)
- Replace `self.TrackerFile.write_text(json.dumps(self.State, indent=2), encoding="utf-8")` with `AtomicWriteJson(self.TrackerFile, self.State)`

---

### Item 4 — Orphaned lock files poison tasks (HIGH)

**File:** `message_bus.py`, lines 134-159

**Problem:** `ClaimTask` creates a `.lock` file. If the process crashes after creating the lock but before `finally: unlink()`, the lock persists forever. The task becomes permanently unclaimable.

**Fix:**
- Before attempting to create the lock, check if an existing lock file is older than some threshold (e.g., 5 minutes)
- If it's stale, delete it and proceed
- The threshold should be configurable but default to 300 seconds
- Add a log message when cleaning up a stale lock: `self.Log("bus", f"Cleaned stale lock for {task['task_id']}")`

---

## MEDIUM

### Item 5 — `run_shell` in coder's tool whitelist (MEDIUM)

**File:** `agents/coder.yaml`, lines 139-145

**Problem:** The coder can call `run_shell`, which always returns an error. This wastes turns and is misleading.

**Fix:**
- Remove the entire `run_shell` tool block from coder.yaml (lines 139-145)
- If the coder needs build/lint, it should use `run_tests` which is already in its whitelist

---

### Item 6 — Team memory `Save` not atomic (MEDIUM)

**File:** `team_memory.py`, lines 37-38

**Problem:** `Save()` uses plain `write_text()`. Under concurrent writes from multiple agents, entries get lost.

**Fix:**
- Either import `AtomicWriteJson` from `message_bus` or add an equivalent `AtomicWriteJson` function to this file
- Replace `self.MemoryFile.write_text(json.dumps(self.Entries, indent=2), encoding="utf-8")` with the atomic write

---

### Item 7 — Orchestrator prompt teaches wrong task creation (MEDIUM)

**File:** `agents/orchestrator.yaml`, lines 39-49

**Problem:** The system prompt tells the orchestrator to "Create JSON files in team_bus/tasks/" directly, but it should use the `create_task` tool.

**Fix:**
- Delete the TASK FILE FORMAT block (lines 39-49)
- Replace it with a note: "Use the create_task tool to assign work. Do NOT write task JSON files directly."
- Also update RULE 2 (line 54) which says "agents don't share memory" — this is now false since team memory exists. Change to: "Provide relevant context in each task. Agents also have access to team memory via team_remember and team_recall."

---

## LOW

### Item 8 — Hardcoded `--agent` choices (LOW)

**File:** `team_agent_loop.py`, lines 568-569

**Problem:** `choices=["orchestrator", "researcher", "coder", "reviewer"]` means adding a new agent type requires editing Python code.

**Fix:**
- Remove the `choices` parameter from `add_argument`
- Instead, after parsing args, scan `AgentsDir` for all `.yaml` files and validate that `--agent` matches one of them
- If not found, print available agent names from the directory

---

### Item 9 — Dead imports (LOW)

**Files:** `team_memory.py` line 10, `dashboard.py` line 7

**Problem:** `team_memory.py` imports `time` but never uses it. `dashboard.py` imports `sys` but never uses it.

**Fix:**
- Remove `import time` from `team_memory.py`
- Remove `import sys` from `dashboard.py`

---

### Item 10 — Budget tracker variable shadowing (LOW)

**File:** `budget_tracker.py`, line 184

**Problem:** `team_spend` is re-assigned inside the warn-percent check block, shadowing the earlier assignment from line 131. It works but is a copy-paste artifact.

**Fix:**
- Remove the redundant line 184: `team_spend = self.State["teams"].get(team_id, {"daily": 0.0, "monthly": 0.0})`
- The `team_spend` from line 131 is still in scope and correct

---

## REPORT FORMAT

When done with ALL items, report back with:

```
ITEM 1: [done/skipped/need help]
  What changed: [specific file and lines modified]
  Why: [one sentence]

ITEM 2: [done/skipped/need help]
  What changed: ...
  Why: ...

... (all 10 items)

ANYTHING ELSE YOU NOTICED: [optional — other issues found while fixing]
```
