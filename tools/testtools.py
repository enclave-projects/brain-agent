"""Phase 2 stub tools to exercise the guard. They never touch the filesystem."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from brain.paths import PathNotAllowed, rel, resolve_allowed


@tool
def test_rename(path: str, new_name: str) -> dict[str, Any]:
    """TEST STUB (reversible): pretend to rename a file. Changes nothing."""
    try:
        p = resolve_allowed(path)
    except PathNotAllowed as e:
        return {"ok": False, "changed": [], "data": None, "error": str(e), "undo": None}
    return {
        "ok": True,
        "changed": [],
        "data": f"would rename {rel(p)} to {new_name}",
        "error": None,
        "undo": {"tool": "test_rename", "path": new_name, "new_name": p.name},
    }


@tool
def test_delete(path: str) -> dict[str, Any]:
    """TEST STUB (irreversible): pretend to permanently delete a file. Changes nothing."""
    try:
        p = resolve_allowed(path)
    except PathNotAllowed as e:
        return {"ok": False, "changed": [], "data": None, "error": str(e), "undo": None}
    return {"ok": True, "changed": [], "data": f"would delete {rel(p)}", "error": None, "undo": None}


TEST_TOOLS = [test_rename, test_delete]
