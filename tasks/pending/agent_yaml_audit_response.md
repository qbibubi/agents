# AGENT YAML AUDIT — Architect's Response

Cross-reference complete. The reviewer's analysis is accurate across all 25+ findings.
Below is what to act on, what to leave alone, and the reasoning for each.

**UPDATE (2026-07-23): All 4 fixes applied and verified. SO1/SR2/X1 documented.
VR2 expanded to cover CSP/HSTS. X3 added to test plan (T18). O2/SR3 deferred
to normalization pass — cosmetic, no functional impact.**

---

## FINAL STATUS

| Issue | Status |
|---|---|
| O1 — IDENTITY sections | FIXED — both orchestrators |
| O2 — Step label inconsistency | DEFERRED — cosmetic, normalize in future pass |
| O3 — "Every field required" preamble | FIXED — all 8 agents |
| O4 — Stuck detection sync | CONFIRMED — guidance matches code |
| O5 — Hardcoded agent capabilities | BY DESIGN — no agent YAML reader tool |
| R1 — Attack surface checklist claim | CORRECTED — removed from architect's claim |
| R2 — Research methodology | CONFIRMED — strongest section |
| C1 — Coder lacks memory tools | BY DESIGN — documented in orchestrator YAML |
| C2 — Abstract coding standards | BY DESIGN — framework is team-agnostic |
| RV1 — Reviewer thoroughness | CONFIRMED — 30-item checklist |
| RV2 — Reviewer has run_tests | CONFIRMED — well-integrated |
| SO1 — Retry limit rationale | FIXED — documented inline in YAML |
| SO2 — Security team member docs | CONFIRMED — excellent detail |
| VR1 — Vulnerability checklist coverage | CONFIRMED — 34 checks |
| VR2 — Runtime-only config checks | FIXED — all 6 items now static-analysis-verifiable |
| VR3 — CWE only in researcher | BY DESIGN — researcher classifies, reviewer scores |
| TP1 — Safe PoC pattern | CONFIRMED — excellent example code |
| TP2 — No sandbox provisioning | KNOWN LIMITATION — documented in test plan |
| SR1 — CVSS scoring reference | CONFIRMED — gold standard |
| SR2 — Reviewer can't write memory | FIXED — handoff loop closed in orchestrator STEP 5 |
| SR3 — Naming convention | DEFERRED — cosmetic, snake_case fields vs CAPITAL enums is standard |
| X1 — Memory tool distribution | FIXED — documented in orchestrator YAML |
| X2 — Output schema naming | BY DESIGN — different agent types, different outputs |
| X3 — max_turns for researcher | MONITORING — T18 added to test plan for data-driven tuning |
| X4 — VALIDATE INPUTS steps | FIXED — added to coder, reviewer, security_reviewer |

---

## TO FIX (4 items — concrete, bounded work)

### Fix 1 — O1: Add explicit IDENTITY sections to orchestrator and security_orchestrator

**Why:** The reviewer is right. The orchestrator says "You are a Team Orchestrator leading a small AI development team" — that's a job description, not an identity. Compare with the researcher's "If the coder needs to guess, you have failed." The identity statement gives the agent a personal stake in the outcome. Without it, the orchestrator is managing a process; with it, the orchestrator owns the result.

**What to add to orchestrator:**
```
YOUR IDENTITY

You are the decision-maker. You turn user goals into agent tasks.
If the wrong agent gets the wrong task, that is YOUR failure.
If the user receives incomplete or incorrect work, that is YOUR failure.
You do not implement. You do not research. You direct, review, and deliver.
```

**What to add to security_orchestrator:**
```
YOUR IDENTITY

You are the audit commander. You turn a target into a security assessment.
If a critical vulnerability is missed because you didn't scope it, that is YOUR failure.
If a finding reaches the report without validation, that is YOUR failure.
You do not find vulnerabilities. You do not test exploits. You direct, prioritize, and report.
```

Placement: after the opening line, before TEAM MEMBERS.

### Fix 2 — O3: Add "Every field is required" preamble to 5 agents

**Why:** The reviewer found that only researcher, coder, and reviewer have the explicit mandate. The LLM treats optional-looking fields as optional. If `files_analyzed` is omitted from a researcher output because the agent didn't think it mattered, the orchestrator can't verify what was actually read.

**What to add:** Before each OUTPUT FORMAT block in these agents:
- orchestrator
- security_orchestrator
- vulnerability_researcher
- test_programmer
- security_reviewer

Add exactly this line:
```
Every field is required. Use empty arrays [] or "N/A" if not applicable.
Do not omit fields.
```

### Fix 3 — VR2: Remove runtime-only checks from vulnerability_researcher's static analysis checklist

**Why:** The CONFIGURATION section of the VULNERABILITY CHECKLIST includes "Unnecessary ports open" — this is a runtime/nmap concern, not detectable via read_file, search_code, or list_directory. Including it teaches the agent to flag things it cannot verify, which undermines the confidence-level system (everything would be LOW or NEEDS_DYNAMIC_TESTING).

**What to change:** Remove this line from vulnerability_researcher.yaml, VULNERABILITY CHECKLIST → CONFIGURATION:
```
[ ] Unnecessary ports open
```
Replace with something the agent CAN verify statically:
```
[ ] Listening ports hardcoded in config or code (check for port numbers in settings)
```

### Fix 4 — X4: Add VALIDATE INPUTS step to consumer-agent decision trees

**Why:** The coder's decision tree says "Read [the researcher's findings] thoroughly. Follow them exactly." But if the researcher's spec references a file that doesn't exist, the coder only discovers this at STEP 2 after burning turns on reading. A 30-second validation at STEP 1 catches this.

**What to add:** After the "UNDERSTAND" step in each consumer agent, insert:

**coder** (STEP 1.5):
```
VALIDATE INPUTS:
  Does the spec reference files? → list_directory to confirm they exist.
  Are the file paths consistent? → resolve relative paths against the project root.
  Is the spec internally consistent? → do file_to_create paths conflict with file_to_modify?
  If anything is missing or wrong → flag immediately, don't proceed silently.
```

**reviewer** (STEP 1.5):
```
VALIDATE INPUTS:
  Does the coder's output list files_created and files_modified?
  → list_directory to confirm every listed file exists.
  Are there files referenced in the code that aren't in the output?
  → search_code for import statements and cross-reference.
  If the coder's output is incomplete → flag "MISSING FILES" and review only what's available.
```

**security_reviewer** (STEP 1.5):
```
VALIDATE INPUTS:
  Does every researcher finding have a corresponding test result?
  → Compare finding IDs from team_recall against test results in context.
  Are there findings with no test? → mark PENDING_VALIDATION immediately.
  Are there test results with no corresponding finding? → flag "ORPHANED TEST RESULT."
```

**test_programmer** — already has this implicitly at STEP 1 ("Is the finding clear enough to write a test? NO → Flag"). No change needed.

---

## TO LEAVE ALONE (with reasoning)

### O5 — Orchestrator hardcodes agent capabilities

The reviewer asks whether the orchestrator could discover agent capabilities dynamically. The answer is: not without a registry service. The orchestrator has no tool to read another agent's YAML (and shouldn't — that's a security boundary). The TEAM MEMBERS block is documentation that happens to live in a prompt. It's static because agent capabilities are static. If you add a new agent type, you update two YAML files — that's acceptable for a system where agent creation is an intentional design act, not a runtime operation.

### C1 — Coder lacks team_remember/team_recall

The reviewer correctly identifies this as intentional but fragile. It stays as-is. The coder receives context via the task prompt (the orchestrator injects it). Adding memory tools to the coder invites scope creep — the coder starts researching instead of implementing. The fragility (orchestrator forgetting context) is mitigated by the orchestrator's TASK DESCRIPTION TEMPLATE which requires CONTEXT and INPUTS sections.

### C2 — Coding standards are abstract, not project-specific

The coder's CODING STANDARDS say "match the existing codebase." This is correct for a framework that operates on ANY codebase. Hardcoding this project's conventions would make the coder useless on other projects. The programmer_context.md documents the current project's conventions for humans — the coder discovers them by reading files.

### SO1 — Inconsistent revision limits (2 cycles for code, 1 for unsafe PoC)

The reviewer spotted that the security_orchestrator allows 2 revision cycles for findings but only 1 retry for unsafe PoCs. This is intentional and should be documented, not changed. Rationale: an unsafe PoC is a SAFETY violation, not a quality issue. If the test_programmer wrote a PoC that would actually execute a destructive payload, that's a rule break, not a bug. One retry is generous. If they do it again, the finding goes to manual testing — better to lose a finding than to risk running a dangerous PoC.

### VR3 — CWE references only in vulnerability_researcher

The reviewer notes CWE references are present in vulnerability_researcher's output but not in security_reviewer's. The security_reviewer assigns CVSS scores; CWE is a separate taxonomy for weakness types. It's reasonable for the researcher to classify by CWE (what kind of weakness is this?) and for the reviewer to score by CVSS (how severe is this?). Adding CWE to the reviewer would be scope creep — the reviewer validates and scores, the researcher classifies.

### SR2 — Security reviewer can't write to team memory

Intentional. Authority "recommend" means "hand findings to the orchestrator." The security_reviewer validates and hands off. The orchestrator stores the final validated findings. This keeps a single writer to memory for each finding lifecycle, preventing conflicting validation entries.

### TP2 — Orchestrator has no "provision sandbox" step

Correct observation, architectural limitation. The framework runs locally with file-based tools. There is no sandbox provisioning API. The requires_manual_testing output is a handoff to a human. This is documented as a known limitation in the test plan (U1: "If a finding requires destructive testing to confirm, flag it as UNCONFIRMED — requires manual testing"). No YAML change needed.

### X2 — Output schema naming differences

The reviewer correctly identifies this as not a problem. Each agent produces a different type of output. The orchestrator's TEAM MEMBERS section documents each format. No change needed.

### X3 — max_turns for researcher (15) seems low

The reviewer suggests bumping researcher from 15 to 20. Reasonable, but I'm leaving it at 15 for now. The researcher has detailed methodology steps but each step is one or two tool calls — read a file, search a pattern, check memory. 15 turns is 15 API calls. If the researcher can't produce a spec in 15 calls, the task is too broad and the orchestrator should split it. If testing shows researcher consistently hitting max_turns, bump to 20.

---

## IMPLEMENTATION ORDER

1. Fix 1 (O1) — 10 minutes, two YAML edits
2. Fix 2 (O3) — 10 minutes, five YAML edits
3. Fix 3 (VR2) — 2 minutes, one line change
4. Fix 4 (X4) — 20 minutes, add VALIDATE INPUTS to coder, reviewer, security_reviewer decision trees

Total: under 1 hour. All changes are isolated to agent YAML files. No Python code changes.
