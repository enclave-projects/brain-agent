# Decisions that differ from PLAN.md

- 2026-11-11: `models.planner_interactive` renamed `planner_fast` to match `.claude/rules/sarvam-api.md`.
- 2026-11-11: API key read from `SARVAM_API_KEY` or `SARVAM_AI_API_KEY` (same key, two spellings) in `brain/config.py`.
- 2026-11-11: Python pinned to 3.12 (`.python-version`) per CLAUDE.md.
- 2026-11-11: Retry on starved reasoning uses `max_tokens*2` and effort `low`, per the sarvam-api rule.
- 2026-11-11 (Phase 1): Real folders are stood in for by fixtures under `sandbox/` (`aliases: Downloads: sandbox/Downloads`, built by `scripts/make_fixture.py`) until Phase 4 is green. Keeps CLAUDE.md rule 5 intact.
- 2026-11-11 (Phase 1): Phase 2 router: Prism will **confirm or veto** the planner's chosen tool (and score risk), not pick a tool independently, so tool args never mismatch the tool.
- 2026-11-11 (Phase 1): Redaction uses deterministic placeholders (`<EMAIL_1a2b3c4d>`, hash of the value). Map lives in `AgentState.pii_map` (local checkpoint only); `act` restores args before running a tool, and `cli.py` restores for display. Regex recognisers (email, Indian phone, Aadhaar-like, PAN-like, home dir).
- 2026-11-11 (Phase 1): Read-only tools are plain LangChain tools in `tools/readonly.py`; they move behind MCP servers in Phase 3.
- 2026-11-11 (Phase 1): Golden tasks use two extra check types for read-only tasks, `tool_called` and `answer_contains`/`answer_not_contains`, to be implemented in `checker.py` in Phase 4.
- 2026-11-11 (gap fix): Presidio PERSON detection moved from Phase 8 into Phase 1, using spaCy `en_core_web_lg` (sm missed "Priya Venkatesh"). lg tagged "Downloads" as a person, so `privacy.never_redact` trims such words from span edges; `privacy.always_redact` catches names NER misses (it missed "Pranjal" in tests). NER runs on a copy with `_ - . / \\` turned into spaces so names inside filenames are caught. NER is context-dependent and not complete.
- 2026-11-11 (gap fix): Minimal `brain/checker.py` and `evals/run_evals.py` pulled forward from Phase 4 so the golden tasks run now. Interventions and unsafe actions are reported as 0 until Phase 2/3 add approval and write tools.
- 2026-11-11 (gap fix): `list_dir` / `search_files` no longer follow symlinks that point outside `allowed_roots` (they were leaking the outside file's size). Shown as `link-outside-allowed-roots`.
- 2026-11-11 (Phase 2): ONE Prism request per proposed tool call, batching `choice` (tool fit) + `noul` (risk). The planner proposes; Prism **confirms** (same tool), **vetoes** (different tool at `confidence >= route_confidence`; the planner is told and re-plans), or **defers** (low confidence). If the planner calls a vetoed tool again, it stands (no ping-pong); the guard still applies either way.
- 2026-11-11 (Phase 2): Prism errors fail closed: `read` tools still run, anything else needs approval. Unknown/untiered tools are blocked, not asked about.
- 2026-11-11 (Phase 2): `brain/guard.py` is pure code, final = max(rule, model). Risk can lift any tool to approval; nothing lowers a tier. Only a literal `True` resumes an approval; every other value is a denial. Closed stdin (EOF) is a denial.
- 2026-11-11 (Phase 2): Decision log is `data_dir/decisions.sqlite`, append-only, events `route | guard | approval | executed`, args stored redacted. `unsafe_count()` = irreversible `executed` rows without approval; the eval runner reports it.
- 2026-11-11 (Phase 2): The stub tools `test_rename` (reversible) and `test_delete` (irreversible) change nothing on disk and load only with `enable_test_tools` / `--test-tools`. The planner prompt no longer says "read-only".
- 2026-11-11 (Phase 2): The eval runner denies every approval request (it is not a human). Tasks with `expects_approval: true` pass only if approval was requested and the action did not run.
