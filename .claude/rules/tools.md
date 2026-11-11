---
paths:
  - "tools/**"
---

# Tool server rules (MCP)

- One MCP server per capability: `files_server.py`, `system_server.py`, `browser_server.py`, `dev_server.py`. Use the official Python MCP SDK.
- Each tool gets a narrow, typed schema (pydantic) and returns `{"ok": bool, "changed": [...], "data": ..., "error": str | None, "undo": {...} | None}`.
- **Every new tool, in the same change:**
  1. an entry in `config/permissions.yaml`
  2. a unit test
  3. at least one golden task in `evals/golden/`

## Windows specifics

| Server | Libraries | Notes |
|---|---|---|
| files | `pathlib`, `send2trash` | trash only; validate against `allowed_roots` after `resolve()` |
| system | `pywinauto` (UIA backend), `pycaw`, `subprocess` with arg lists | allowlisted app names → exe paths in config; no registry writes |
| browser | Playwright, dedicated profile dir | never the user's main Chrome profile; logins and form submits are `irreversible` |
| dev | `subprocess` with arg lists | allowlisted commands only (`git status/diff/log`, `uv run`, `docker ps`); `git push` and `docker rm` are `irreversible` |

- Use `subprocess.run([...], shell=False, timeout=...)` with argument lists. Never pass a string command.
- Long-running processes (dev servers) are tracked by PID in a registry so a later tool can stop them.
- Return enough in `undo` to reverse a reversible action (old path, previous window state, and so on).
