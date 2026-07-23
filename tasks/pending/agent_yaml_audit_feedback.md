# AGENT YAML ARCHITECT REVIEW — Feedback & Analysis

Cross-reference of the architect's claims against the actual state of all 8 agent YAMLs.

---

## CLAIMS VERIFIED — What's Present in Every Agent

### IDENTITY SECTION

| Agent | Present | Quality |
|---|---|---|
| orchestrator | Implicit in system_prompt ("You are a Team Orchestrator...") but no explicit IDENTITY heading with failure-mode statement | PARTIAL — missing explicit "YOUR IDENTITY" header and failure-mode language the other agents have |
| researcher | YES — "You investigate. You do NOT implement... If the coder needs to guess, you have failed." | EXCELLENT |
| coder | YES — "You are the implementer. You turn specifications into working code..." | EXCELLENT |
| reviewer | YES — "You are the quality gate... If you approve broken code, that is YOUR failure." | EXCELLENT |
| security_orchestrator | Implicit via TEAM MEMBERS section — no explicit "YOUR IDENTITY" section | PARTIAL — missing explicit identity header |
| vulnerability_researcher | YES — "You are the first line of a security audit... A vulnerability you miss is a vulnerability nobody finds." | EXCELLENT |
| test_programmer | YES — "You are the validator... A PoC that executes a destructive payload is a FAILURE." | EXCELLENT |
| security_reviewer | YES — "You are the final quality gate... If a false positive reaches the report, that is YOUR failure." | EXCELLENT |

**Finding O1:** orchestrator and security_orchestrator lack the explicit `YOUR IDENTITY` section header and failure-mode language. The orchestrator's opening "You are a Team Orchestrator leading a small AI development team" is generic compared to the researcher's "If the coder needs to guess, you have failed." Consider adding an explicit identity statement: "You are the decision-maker. If the wrong agent gets the wrong task, that is YOUR failure. If the user receives incomplete work, that is YOUR failure."

---

### DECISION TREE

| Agent | Present | Steps |
|---|---|---|
| orchestrator | YES — WORKFLOW DECISION TREE | 5 steps (CLASSIFY → RESEARCH → IMPLEMENT → REVIEW → DELIVER) |
| researcher | YES — DECISION TREE | 5 steps (UNDERSTAND → CHECK MEMORY → READ INPUTS → INVESTIGATE → PRODUCE) |
| coder | YES — DECISION TREE | 5 steps (UNDERSTAND SPEC → READ CODEBASE → IMPLEMENT → VERIFY → PRODUCE) |
| reviewer | YES — DECISION TREE | 4 steps (IDENTIFY → READ → AUDIT → PRODUCE VERDICT) |
| security_orchestrator | YES — WORKFLOW DECISION TREE | 6 steps (SCOPING → RESEARCH → TEST → VALIDATE → HANDLE RESULTS → DELIVER) |
| vulnerability_researcher | YES — DECISION TREE | 6 steps (UNDERSTAND TARGET → ATTACK SURFACE → VULNERABILITY SCANNING → DEPENDENCY ANALYSIS → THREAT MODEL → OUTPUT) |
| test_programmer | YES — DECISION TREE | 5 steps (UNDERSTAND FINDING → DESIGN TEST → WRITE → RUN/VERIFY → OUTPUT) |
| security_reviewer | YES — DECISION TREE | 5 steps (GATHER → VALIDATE → SCORE → CROSS-REFERENCE → PRODUCE) |

All present and well-structured. No issues.

**Finding O2 (minor):** The decision trees have slightly inconsistent naming patterns — "STEP 1" vs "STEP 1 —" vs "STEP 1:". The researcher and security_orchestrator use "STEP 1 —" (em dash), coder uses "STEP 1 —" consistently, but some vary in whitespace after the step label. Not a functional issue, but worth normalizing in a future pass.

---

### ANTI-PATTERNS

| Agent | Present | Format | Quality |
|---|---|---|---|
| orchestrator | YES — "ANTI-PATTERNS — what you must NEVER do" | BAD/GOOD pairs | EXCELLENT — 6 anti-patterns covering wrong agent assignment, vague descriptions, skipping research, looping, user decisions, priority misuse |
| researcher | YES — "ANTI-PATTERNS — what you must NEVER do" | BAD/GOOD pairs | EXCELLENT — 5 anti-patterns covering answering without reading, writing code, vague recommendations, false confidence, ignoring recall |
| coder | YES — "ANTI-PATTERNS — what you must NEVER do" | BAD/GOOD pairs | EXCELLENT — 6 anti-patterns covering writing without reading, new patterns, debug code, modifying tests, silent errors, guessing spec |
| reviewer | YES — "ANTI-PATTERNS — what you must NEVER do" | BAD/GOOD pairs | EXCELLENT — 6 anti-patterns covering unreviewed code, writing implementation, misclassified severity, approving broken code, rejecting without explanation, re-reviewing same issue |
| security_orchestrator | YES — "ANTI-PATTERNS" | BAD/GOOD pairs | EXCELLENT — 4 anti-patterns covering undefined scope, skipping research, destructive testing, excessive revision loops |
| vulnerability_researcher | YES — "ANTI-PATTERNS" | BAD/GOOD pairs | EXCELLENT — 4 anti-patterns covering reporting without evidence, exploit code, skipping dependencies, duplicate findings |
| test_programmer | YES — "ANTI-PATTERNS" | BAD/GOOD pairs | EXCELLENT — 4 anti-patterns covering real exploits, dangerous imports, writing outside tests/, untested findings |
| security_reviewer | YES — "ANTI-PATTERNS" | BAD/GOOD pairs | EXCELLENT — 5 anti-patterns covering unreviewed findings, severity without CVSS, unexplained false positives, unmerged duplicates, undocumented merges |

---

### STRICT OUTPUT SCHEMAS

| Agent | All fields required? | Empty arrays mandated? | Quality |
|---|---|---|---|
| orchestrator | YES — "Do not add, remove, or rename fields" | Implicit in structure | GOOD — 6 top-level fields all required |
| researcher | YES — "Every field is required. Use empty arrays [] or N/A if not applicable." | Explicit | EXCELLENT |
| coder | YES — "Every field is required. Use empty arrays [] or N/A if not applicable." | Explicit | EXCELLENT |
| reviewer | YES — "Every field is required. Use empty arrays [] or N/A if not applicable." | Explicit | EXCELLENT |
| security_orchestrator | Implicit — fields present but no "every field required" warning | Implicit | GOOD |
| vulnerability_researcher | Implicit — fields present but no explicit requirement statement | Implicit | GOOD |
| test_programmer | Implicit — fields present but no explicit requirement statement | Implicit | GOOD |
| security_reviewer | Implicit — fields present but no explicit requirement statement | Implicit | GOOD |

**Finding O3:** Only 3 of 8 agents (researcher, coder, reviewer) have the explicit "Every field is required. Use empty arrays [] or N/A if not applicable." preamble. The other 5 agents (orchestrator, security_orchestrator, vulnerability_researcher, test_programmer, security_reviewer) have complete schemas but lack this explicit mandate. Without it, the LLM may omit fields it considers optional.

---

### TOOL DESCRIPTIONS REWRITTEN

**Before pattern:** `"path: file path"` or `"content: file content"`

| Agent | Rewritten? | Examples |
|---|---|---|
| orchestrator | YES | `"Short, specific title. Include the key deliverable..."`, `"Full task description following the TASK DESCRIPTION TEMPLATE. Must include OBJECTIVE, SCOPE..."` |
| researcher | YES | `"Always read before making claims about code."`, `"Consistent topic label: 'finding:F-001', 'api:stripe'..."` |
| coder | YES | `"Always read a file before modifying it."`, `"Complete file content"` (still minimal) |
| reviewer | YES | `"Read EVERY file the coder created or modified."`, `"Use to find usages of unsafe functions (eval, exec, shell=True, pickle)."` |
| security_orchestrator | YES | `"Use the TASK DESCRIPTION TEMPLATE."`, `"Specific title: 'Research auth module for injection flaws' not 'Check auth'"` |
| vulnerability_researcher | YES | `"Always read before making claims."`, `"Specific: 'CVE database flask 2.3.0' or 'owasp python safety'"` |
| test_programmer | YES | `"Read target code before writing tests."`, `"Must be under tests/security/"` |
| security_reviewer | YES | `"Read target code before validating."`, `"Use before validating to get complete picture."` |

All rewrites present. Quality varies — the coder's `write_file` content parameter still just says `"Complete file content"` without guidance, but the path parameter now has `"must be within project directory"`.

---

## AGENT-SPECIFIC CLAIMS — Detailed Verification

### ORCHESTRATOR

| Claim | Status | Notes |
|---|---|---|
| Task description template with 7 mandatory sections | YES — 7 sections: OBJECTIVE, SCOPE, CONTEXT, INPUTS, ACCEPTANCE CRITERIA, OUTPUT REQUIRED, PREVIOUS ATTEMPTS | PASS |
| Full workflow decision tree with 5 steps | YES — CLASSIFY, RESEARCH, IMPLEMENT, REVIEW, DELIVER | PASS |
| Coordination protocols (parallel vs sequential) | YES — PARALLEL VS SEQUENTIAL section | PASS |
| Context passing guidance | YES — CONTEXT PASSING section with team_remember usage | PASS |
| Revision limits | YES — REVISION LIMITS: max 3 cycles | PASS |
| Stuck detection guidance | YES — STUCK DETECTION section | PASS |

**Finding O4:** The orchestrator's stuck detection guidance references "If you call check_results more than 5 times with no new results, you will be automatically stopped" — this correctly reflects the code's loop detection. However, it recommends "After creating tasks, call check_results ONCE per cycle." but the code has the 5-consecutive-empty detection — the guidance and the implementation are in sync, which is good.

**Finding O5:** The TEAM MEMBERS section in the orchestrator YAML hardcodes agent capabilities ("WHAT THEY DO", "WHAT THEY CANNOT DO", "TOOLS", "OUTPUT"). This means adding a new agent type requires updating TWO places — the new agent's YAML AND the orchestrator's TEAM MEMBERS block. Consider whether the orchestrator could discover this from list_team or team memory instead.

---

### RESEARCHER

| Claim | Status | Notes |
|---|---|---|
| Four research methodologies by task type | YES — CODEBASE EXPLORATION, API/LIBRARY RESEARCH, DEPENDENCY ANALYSIS, BUG INVESTIGATION | PASS |
| Attack surface checklist | NO — this agent has no attack surface checklist. That's in vulnerability_researcher. | MISMATCH — the architect's claim says "Attack surface checklist" for researcher but it belongs to vulnerability_researcher. This is correct architecture — the dev-team researcher researches code/APIs, not attack surfaces. |
| Confidence level definitions tied to evidence | YES — HIGH/MEDIUM/LOW with clear criteria | PASS |
| Anti-pattern: never answer without reading first | YES — first anti-pattern | PASS |

**Finding R1:** The architect's claim mentions "Attack surface checklist" for the dev-team researcher. This is incorrect — the attack surface checklist is in vulnerability_researcher.yaml (which makes sense — it's a security artifact). The dev-team researcher correctly has 4 methodologies for code exploration, API research, dependency analysis, and bug investigation. The architect should update their description.

**Finding R2 (positive):** The RESEARCH METHODOLOGY section is outstanding — each methodology has a numbered, sequential workflow that guides the LLM through exactly what to do. This is the strongest methodological guidance in any of the 8 agents.

---

### CODER

| Claim | Status | Notes |
|---|---|---|
| Coding standards with explicit security rules | YES — CODING STANDARDS section with SECURITY, CORRECTNESS, STYLE subsections | PASS |
| Decision tree: understand spec → read codebase → implement → verify → output | YES — 5 steps matching exactly | PASS |
| Anti-pattern: never introduce new patterns that contradict the codebase | YES — second anti-pattern | PASS |
| Safety: if you violate any security rule, you have failed | YES — "if you violate any of these, you have failed" | PASS |

**Finding C1:** The coder is the only agent that cannot write to or query team memory. The orchestrator's TEAM MEMBERS section lists coder's tools as `read_file, write_file, search_code, list_directory, run_tests` — no team_remember/team_recall. This is a deliberate choice (coder receives injected context, implements, doesn't research). But the coder's DECISION TREE says "Use INPUTS from the task to identify files to read" — if the task's context doesn't include everything, the coder has no way to pull additional context from memory. The orchestrator is responsible for full context passing. This is consistent but fragile — if the orchestrator forgets context, the coder is blind.

**Finding C2:** The CODING STANDARDS say "Match the existing codebase. If the project uses 2-space indent, you use 2-space indent." The actual project uses `\{` on new lines and CapitalCase globals. The coder will follow whatever it reads, which is correct, but worth noting that the standards section is abstract and doesn't encode the project's actual conventions from `programmer_context.md`.

---

### REVIEWER

| Claim | Status | Notes |
|---|---|---|
| Full review checklist with 5 categories | YES — SECURITY (8 items), CORRECTNESS (8 items), PERFORMANCE (4 items), STYLE (6 items), TESTING (4 items) | PASS |
| Each category with checkbox items | YES — [ ] format | PASS |
| Severity definitions | YES — CRITICAL/WARNING/INFO with exact criteria | PASS |
| Verdict definitions with exact criteria | YES — APPROVED/CHANGES_REQUESTED/REJECTED | PASS |
| Anti-pattern: never approve code with unresolved CRITICAL or WARNING | YES — fourth anti-pattern | PASS |

**Finding RV1 (positive):** The reviewer YAML is the most thorough of all 8 agents. The checklist has 30 specific items, the severity definitions include concrete examples, the verdict definitions have exact thresholds. The ANTI-PATTERNS section is particularly strong — the BAD/GOOD pairs are detailed and instructional.

**Finding RV2:** The reviewer has `run_tests` in its tool whitelist (line 308-314), which is correct — it can re-run the coder's tests to verify results. But the SECURITY checklist says "Is shell=True used?" — the reviewer can verify this by reading code and using search_code for `shell=True`, which is exactly what the tool descriptions now guide it to do. Well-integrated.

---

### SECURITY ORCHESTRATOR

| Claim | Status | Notes |
|---|---|---|
| Task template adapted for security audits (TARGET with files/boundaries/context) | YES — TASK DESCRIPTION TEMPLATE with TARGET (FILES, SYSTEM BOUNDARIES, DEPLOYMENT CONTEXT) | PASS |
| Decision tree: scoping → research → test → validate → handle results → deliver | YES — 6 steps | PASS |
| Severity-based task prioritization | YES — Priority 1-4 with specific criteria (auth/authz/data handling first) | PASS |

**Finding SO1:** The security_orchestrator's WORKFLOW DECISION TREE STEP 5 says "UNSAFE_POC → Flag to test_programmer for rewrite (max 1 retry)." But STEP 3 says "CRITICAL findings get individual test tasks." Combined with the ANTI-PATTERNS saying "NEVER loop on a finding more than 2 revision cycles" — there's a potential inconsistency: 2 revision cycles for implementation, but only 1 retry for UNSAFE_POC. If a PoC is unsafe and the rewrite is also unsafe, the finding falls through to the report as unverified. This is probably intentional (safety-first), but it's not documented why unsafe PoCs get fewer retries.

**Finding SO2 (positive):** The TEAM MEMBERS section for the security_orchestrator is excellent — it mirrors the dev-team orchestrator's pattern but is adapted for security roles. Each agent entry includes WHAT THEY DO, WHAT THEY CANNOT DO, TOOLS (listed explicitly), and OUTPUT (field names). This is substantially more detailed than the dev-team orchestrator's TEAM MEMBERS section which only has WHAT THEY DO/CANNOT DO/TOOLS/OUTPUT without specific output field names.

---

### VULNERABILITY RESEARCHER

| Claim | Status | Notes |
|---|---|---|
| Attack surface checklist (8 entry point types) | YES — ENTRY POINTS has 8 types: HTTP endpoints, CLI commands, file upload handlers, WebSocket connections, message queue consumers, API endpoints, config file readers, env var readers | PASS |
| Attack surface checklist (8 input vector types) | YES — INPUT VECTORS has 8 types: query params, request bodies, HTTP headers, cookie values, file contents, database results, env vars, CLI arguments | PASS |
| Vulnerability checklist (7 categories, 30+ specific checks) | YES — 7 categories: INJECTION (5 items), AUTHENTICATION (6 items), AUTHORIZATION (4 items), DATA EXPOSURE (6 items), INPUT VALIDATION (5 items), RACE CONDITIONS (2 items), CONFIGURATION (6 items) = 34 checks total | PASS |
| Dependency depth rule | YES — "Check direct AND transitive dependencies" | PASS |
| Anti-pattern: never report without evidence | YES — first anti-pattern | PASS |

**Finding VR1 (positive):** The vulnerability_researcher has the most comprehensive checklists of any agent — 8 entry point types × 8 input vector types + 34 vulnerability checks = a very thorough coverage matrix. This is excellent for guiding an LLM through methodical security review.

**Finding VR2:** The VULNERABILITY CHECKLIST's CONFIGURATION section includes "Unnecessary ports open" — this is a runtime concern, not detectable through static code analysis. The researcher only has `read_file`, `search_code`, `list_directory`, `web_search` — it cannot port-scan. This item should be marked as "requires runtime testing" or removed from static analysis scope.

**Finding VR3:** The OUTPUT FORMAT includes `cwe_reference: "CWE-89 or N/A"` which is a nice addition — none of the other security agents reference CWE. Consider adding CWE references to the security_reviewer's output as well for consistency.

---

### TEST PROGRAMMER

| Claim | Status | Notes |
|---|---|---|
| Safe PoC pattern with example code | YES — SAFE PoC PATTERN section with Python code example | PASS |
| Safety rules as non-negotiable with zero exceptions | YES — "non-negotiable, zero exceptions" + 8 MUST rules + 7 forbidden imports | PASS |
| Clear output format requirement | YES — OUTPUT FORMAT with tests_written, requires_manual_testing, tests_not_written | PASS |
| Decision tree | YES — 5 steps | PASS |
| Anti-pattern: never import dangerous modules | YES — second anti-pattern with explicit BAD/GOOD | PASS |

**Finding TP1 (positive):** The SAFE PoC PATTERN with inline code example is excellent. The LLM has a concrete template to follow, reducing the chance it invents an unsafe pattern. The safety rules explicitly listing forbidden imports (`os, subprocess, socket, requests, urllib`) is much stronger than a generic "don't be destructive" rule.

**Finding TP2:** The safety rules say "Never import os, subprocess, socket, requests, urllib" but the OUTPUT FORMAT includes `requires_manual_testing.required_environment: "sandbox, isolated VM, etc."` — the test_programmer can't test in a sandbox itself (it can only write files under tests/security/), so this is consistent. However, the gap between "describe the environment needed" and "orchestrator receives this information" is not closed — the orchestrator's workflow doesn't have a "provision sandbox" step. This is a known architectural limitation, not a YAML issue.

---

### SECURITY REVIEWER

| Claim | Status | Notes |
|---|---|---|
| CVSS v3.1 scoring reference with examples | YES — CRITICAL/HIGH/MEDIUM/LOW/INFO with CVSS vector strings and examples | PASS |
| Validation checklist for each finding | YES — 5 items: REPRODUCIBILITY, SEVERITY ACCURACY, NO FALSE POSITIVES, EXPLOITABILITY, IMPACT | PASS |
| Merge and chain documentation requirements | YES — merged_findings[] and chained_vulnerabilities[] in output format | PASS |
| Anti-pattern: never change severity without CVSS vector string | YES — second anti-pattern with detailed BAD/GOOD | PASS |

**Finding SR1 (positive):** The CVSS v3.1 SCORING REFERENCE is exceptional — each severity level has example scenarios and a full CVSS vector string. The anti-pattern example shows a complete vector breakdown explaining each metric value. This is the gold standard for teaching an LLM to do structured security scoring.

**Finding SR2:** The security_reviewer's tool list includes `team_recall` but NOT `team_remember`. This means the security_reviewer can read findings but cannot store its validated results back to memory. The orchestrator would need to read the reviewer's output and store it. This is consistent with the authority_level "recommend" (hand findings to orchestrator), but it means the orchestrator must do memory housekeeping. Worth documenting this handoff explicitly.

**Finding SR3:** The statistics object has `pending_validation: 0` but the validation_result enum includes `PENDING_VALIDATION`. The statistics field name uses snake_case while the validation_result uses SCREAMING_SNAKE_CASE. This is a minor naming convention inconsistency — not a functional issue but worth noting for schema consistency.

---

## CROSS-AGENT ISSUES

### Issue X1: Tool whitelist inconsistency — `team_remember`

| Agent | Has team_remember | Has team_recall |
|---|---|---|
| orchestrator | YES | YES |
| researcher | YES | YES |
| coder | NO | NO |
| reviewer | NO | NO |
| security_orchestrator | YES | YES |
| vulnerability_researcher | YES | YES |
| test_programmer | YES | YES |
| security_reviewer | NO | YES |

**Pattern:** Agents with authority "recommend" that produce findings (researcher, vulnerability_researcher, test_programmer) have both memory tools. Agents that consume findings (reviewer, security_reviewer) have only team_recall. The coder has neither. This is a well-reasoned design — but the security_reviewer is the only "recommend" agent with recall but not remember. If it validates a finding, it can't store the validation — the orchestrator must relay it.

### Issue X2: Output schema naming inconsistency

Agents use different field name conventions for the same concept:
- `status: "complete"` — all 8 agents (consistent)
- `findings` vs `validated_findings` vs `tests_written` — different agents, different names for their primary output
- `summary` — all 8 agents (consistent, good)

**This is correct and not a problem** — each agent has a different output type. But the orchestrator needs to know how to parse each one. The orchestrator YAML's TEAM MEMBERS section documents the OUTPUT format for each agent, which bridges this gap.

### Issue X3: max_turns allocation

| Agent | max_turns |
|---|---|
| orchestrator | 20 |
| researcher | 15 |
| coder | 25 |
| reviewer | 15 |
| security_orchestrator | 25 |
| vulnerability_researcher | 20 |
| test_programmer | 25 |
| security_reviewer | 20 |

The coder and test_programmer get the most turns (25) — correct, they write code which requires iterative reading/writing. The reviewer gets the fewest (15) — correct, reading is faster than writing. But the researcher also gets 15, which seems low given the RESEARCH METHODOLOGY section expects it to read multiple files, search code, check dependencies, and produce detailed specs. Consider bumping researcher to 20.

### Issue X4: Missing cross-agent validation in decision trees

Each agent's DECISION TREE is self-contained — it describes what THAT agent does. But no agent's tree has an explicit step for "check if the previous agent's output is valid before using it."

Example: The coder's STEP 1 says "Are there findings from the researcher in the CONTEXT section? YES → Read them thoroughly... Follow them exactly." But there's no check like "Are the findings internally consistent? Does the spec reference files that exist?" The coder would only discover this during STEP 2 (READ THE CODEBASE), wasting turns.

Recommendation: Add a "VALIDATE INPUTS" step to every agent's decision tree that consumes another agent's output.

---

## SUMMARY

| Category | Count |
|---|---|
| Claims verified and passing | All core claims confirmed |
| Issues found (O1-O5) | 5 orchestrator issues |
| Issues found (R1-R2) | 2 researcher notes |
| Issues found (C1-C2) | 2 coder notes |
| Issues found (RV1-RV2) | 2 reviewer notes (both positive) |
| Issues found (SO1-SO2) | 2 security orchestrator notes |
| Issues found (VR1-VR3) | 3 vulnerability researcher notes |
| Issues found (TP1-TP2) | 2 test programmer notes |
| Issues found (SR1-SR3) | 3 security reviewer notes |
| Cross-agent issues (X1-X4) | 4 |

**Overall assessment:** The architect's changes are thorough, consistent, and well-reasoned. The IDENTITY/DECISION TREE/ANTI-PATTERNS pattern is applied to all 8 agents with high quality. The primary areas for improvement are:

1. **O1** — Add explicit IDENTITY sections with failure-mode language to orchestrator and security_orchestrator
2. **O3** — Add "Every field is required" preamble to the 5 agents that lack it
3. **VR2** — Remove runtime-only checks ("Unnecessary ports open") from vulnerability_researcher's static analysis checklist
4. **X4** — Add "VALIDATE INPUTS" step to decision trees that consume other agents' output
5. **Issue X1** — Document the intentional asymmetry of team_remember/team_recall in programmer_context.md
