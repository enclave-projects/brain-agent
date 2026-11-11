# Decisions that differ from PLAN.md

- 2026-11-11: `models.planner_interactive` renamed `planner_fast` to match `.claude/rules/sarvam-api.md`.
- 2026-11-11: API key read from `SARVAM_API_KEY` or `SARVAM_AI_API_KEY` (same key, two spellings) in `brain/config.py`.
- 2026-11-11: Python pinned to 3.12 (`.python-version`) per CLAUDE.md.
- 2026-11-11: Retry on starved reasoning uses `max_tokens*2` and effort `low`, per the sarvam-api rule.
