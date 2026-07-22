# PROGRAMMER CONTEXT REVIEW — Discrepancies & Feedback

Cross-reference completed against all 8 agent YAMLs, 6 Python files, 3 config YAMLs,
the README, test plan, audit fixes, and the single_agent_demo directory.

---

## DISCREPANCIES FOUND

### D1 — `single_agent_demo/` not documented in File Map

The `single_agent_demo/` directory (containing `agent.yaml` and `agent_loop.py`) exists
on disk but is absent from the File Map section. If it's intentionally kept separate as a
tutorial/onboarding demo, that should be stated. If it's vestigial, it should be removed
or have a deprecation note.

### D2 — `single_agent_demo/agent_loop.py` still has `shell=True`

Line 70 of `single_agent_demo/agent_loop.py` uses `subprocess.run(command, shell=True)`.
The audit fix (Item 1) only touched `team_agent_loop.py`. The README safety table now
claims "shell=True disabled" but this demo file contradicts that. Either apply the same
`shlex.split` fix or add a warning comment explaining why the demo is intentionally
less hardened.

### D3 — KNOWN ISSUES mismatch between programmer_context.md and test_plan.md

The programmer context lists 6 known issues. The test plan lists 4 unsolved issues (U1-U4).
- Context issues #1 (revision chain) = Test plan U1 ✓
- Context issues #2 (RecordSpend race) = Test plan U3 ✓
- Context issues #3 (orchestrator completion) = Test plan U2 ✓
- Context issues #4 (worker polls forever) = Test plan U4 ✓
- Context issues #5 (orchestrator on fresh bus) — NOT in test plan
- Context issues #6 (team.yaml fields not enforced) — NOT in test plan

Two known issues have no corresponding test case. If they're worth listing as "known
issues," they're worth testing for regressions.

### D4 — `search_code` uses `grep`, which doesn't exist on vanilla Windows

The tool implementation calls `["grep", "-rn", ...]`. On Windows without Git Bash or
WSL, this will fail with `FileNotFoundError`. The document mentions Windows in the
start_team.bat entry and the README mentions "contention on Windows," but this
dependency is never called out. Either document it as a prerequisite or add a fallback
using `findstr` or `rg` (ripgrep).

---

## MISSING FROM THE DOCUMENT

### M1 — No guidance on configuring `web_search`

The `web_search` tool is a hardcoded placeholder returning "Web search not configured."
The tool safety table marks it as such, but there is zero guidance on what "external
API setup" means. Which API? What env vars? The researcher agent has this tool in its
whitelist — any team using researcher will hit this dead end silently. The LLM may waste
turns retrying.

Recommendation: add a subsection explaining that `web_search` requires either:
- A Google Custom Search API key + CX
- A Brave Search API key
- A SerpAPI key
And show where to plug it in (the `web_search` function in `team_agent_loop.py`).

### M2 — `vulnerability_researcher` lacks `web_search` tool

The security team's vulnerability researcher is supposed to check dependencies against
CVE databases (its system prompt line 36: "Check imported libraries against known CVE
databases"), but its tool whitelist does not include `web_search`. Compare with the
dev-team researcher which has `web_search`. This is either a deliberate scope limitation
(offline audit only) or an omission. Either way, the document should explain the intent.

### M3 — `coder` has no `team_remember`/`team_recall`

The document states "Team memory is injected into every task prompt" — true. But the
coder cannot write to or query memory. This is likely intentional (coder implements,
doesn't research), but it means the coder can't flag discoveries made during
implementation for other agents. Worth an explicit design note.

### M4 — No mention of `tags` parameter asymmetry across agent YAMLs

The `team_recall` tool parameter `tags` (array) vs `tag` (string) is inconsistent across
agent YAMLs:
- `orchestrator.yaml`: `tags` (array of strings)
- `researcher.yaml`: no `tags` parameter on team_recall (has `keyword`, `limit`)
- `security_orchestrator.yaml`: no `tags` parameter (has `keyword`, `limit`)
- `security_reviewer.yaml`: `tag` (single string)
- `vulnerability_researcher.yaml`: no `tags`/`tag` parameter
- `test_programmer.yaml`: no `tags`/`tag` parameter

The `team_remember` tool also varies: some have `tags` (array), some don't. This
parameter name inconsistency (`tags` vs `tag`) and presence inconsistency could confuse
the LLM when orchestrating cross-agent memory queries.

---

## CROSS-DOCUMENT INCONSISTENCIES

### C1 — README vs code: team.yaml `poll_interval_seconds`

README line 401 says "workers check for tasks every 5 seconds." The document (Known
Issue #6) correctly notes the YAML fields aren't read by code — `WorkerLoop` hardcodes
`time.sleep(5)`. The README should be updated to either (a) mention the YAML field is
decorative or (b) the code should actually read it. Currently the README implies
consistency where none exists.

### C2 — README "Creating a New Team" example directory structure uses `agents/finance_team/`

The README suggests subdirectories under `agents/` for new teams:
```
agents/
  finance_team/
    orchestrator.yaml
```
But the actual project uses flat `agents/*.yaml` with `team:` field for team isolation.
The security team agents live in `agents/` not `agents/security_team/`. The document's
File Map section correctly shows the flat layout. The README example will mislead anyone
trying to create a new team — they'll nest YAMLs and the loop won't find them (since
the agent discovery in `team_agent_loop.py` uses `AgentsDir.glob("*.yaml")`, which is
NOT recursive).

### C3 — README tool table says `run_tests` allowlist is "pytest, npm test, cargo test, go test"

The actual allowlist in `team_agent_loop.py` is:
```python
safe_prefixes = ["pytest", "python -m pytest", "npm test", "cargo test", "go test"]
```
Five entries, not four. `"python -m pytest"` is missing from the README table. Minor,
but a reviewer checking the README might think `python -m pytest` is blocked.

---

## DOCUMENT QUALITY FEEDBACK

### Strengths
- The File Map is comprehensive and accurately traces through the architecture
- The "How the Loop Works" section with Worker/Orchestrator/RunAgent trace is excellent
  onboarding material — matches the code exactly
- The Tool Safety table is clear and correctly reflects the audit-fixed code
- KEY DESIGN DECISIONS section captures the non-obvious architectural rationale well
- CODING CONVENTIONS are accurate and useful

### Improvements
1. Add a "Prerequisites" section: Python version, required packages (`openai`, `pyyaml`),
   and the `grep` dependency for Windows users (Git Bash or WSL).
2. The `--bus-dir` flag is mentioned in the CLI reference but not explained in the File
   Map — add a note that it defaults to `./team_bus` relative to the script directory.
3. Add a cross-reference to the Test Plan at the end of the document so a new programmer
   knows where to look before making changes.
4. The 8 agent YAMLs are well-catalogued but the distinction between "Original Dev Team"
   and "Security Audit Team" is only visible via grouping comments. Consider adding a
   table with columns: agent ID, team, provider, model, max_turns, authority_level.

---

## SUMMARY FOR THE ARCHITECT

| Category | Count |
|---|---|
| Discrepancies (D1-D4) | 4 |
| Missing info (M1-M4) | 4 |
| Cross-document inconsistencies (C1-C3) | 3 |

Highest priority:
- **D2** (`shell=True` in demo) — security risk, contradicts README safety claims
- **C2** (README team directory structure) — will cause runtime failures if followed
- **M2** (vulnerability_researcher missing web_search) — cripples the security team's
  core workflow if CVE lookups are expected
