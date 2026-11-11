# Decisions that differ from PLAN.md

- 2026-11-11: `models.planner_interactive` renamed `planner_fast` to match `.claude/rules/sarvam-api.md`.
- 2026-11-11: API key read from `SARVAM_API_KEY` or `SARVAM_AI_API_KEY` (same key, two spellings) in `brain/config.py`.
- 2026-11-11: Python pinned to 3.12 (`.python-version`) per CLAUDE.md.
- 2026-11-11: Retry on starved reasoning uses `max_tokens*2` and effort `low`, per the sarvam-api rule.
- 2026-11-11 (Phase 1): Real folders are stood in for by fixtures under `sandbox/` (`aliases: Downloads: sandbox/Downloads`, built by `scripts/make_fixture.py`) until Phase 4 is green. Keeps CLAUDE.md rule 5 intact.
- 2026-11-11 (Phase 1): Phase 2 router: Prism will **confirm or veto** the planner's chosen tool (and score risk), not pick a tool independently, so tool args never mismatch the tool.
- 2026-11-11 (Phase 1): Redaction uses deterministic placeholders (`<EMAIL_1a2b3c4d>`, hash of the value). Map lives in `AgentState.pii_map` (local checkpoint only); `act` restores args before running a tool, and `cli.py` restores for display. Regex recognisers only (email, Indian phone, Aadhaar-like, PAN-like, home dir). Presidio person-name NER deferred to Phase 8: names in file content currently DO reach Sarvam.
- 2026-11-11 (Phase 1): Read-only tools are plain LangChain tools in `tools/readonly.py`; they move behind MCP servers in Phase 3.
- 2026-11-11 (Phase 1): Golden tasks use two extra check types for read-only tasks, `tool_called` and `answer_contains`/`answer_not_contains`, to be implemented in `checker.py` in Phase 4.
