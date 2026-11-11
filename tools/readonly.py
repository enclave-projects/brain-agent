"""Phase 1 read-only tools. Plain functions now; moved behind MCP servers in Phase 3.

Every tool returns {"ok", "changed", "data", "error", "undo"}.
"""

from __future__ import annotations

import fnmatch
import os
import platform
from pathlib import Path
from typing import Any

import psutil
from langchain_core.tools import tool

from brain.config import load_config
from brain.paths import PathNotAllowed, allowed_roots, rel, resolve_allowed


def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "changed": [], "data": data, "error": None, "undo": None}


def _err(msg: str) -> dict[str, Any]:
    return {"ok": False, "changed": [], "data": None, "error": msg, "undo": None}


def _size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    total = 0
    for dirpath, _, files in os.walk(p):
        for f in files:
            try:
                total += (Path(dirpath) / f).stat().st_size
            except OSError:
                pass
    return total


@tool
def list_dir(path: str) -> dict[str, Any]:
    """List a folder's entries with type and size in bytes (folders: total recursive size), largest first."""
    try:
        p = resolve_allowed(path)
        if not p.is_dir():
            return _err(f"{path} is not a folder")
        entries = [
            {"name": c.name, "type": "dir" if c.is_dir() else "file", "bytes": _size(c)} for c in p.iterdir()
        ]
        entries.sort(key=lambda e: e["bytes"], reverse=True)
        return _ok(
            {"path": rel(p), "total_bytes": sum(e["bytes"] for e in entries), "entries": entries[:500]}
        )
    except (PathNotAllowed, OSError) as e:
        return _err(str(e))


@tool
def read_file(path: str) -> dict[str, Any]:
    """Read a text file (first read_max_bytes bytes only)."""
    try:
        p = resolve_allowed(path)
        if not p.is_file():
            return _err(f"{path} is not a file")
        limit = load_config()["read_max_bytes"]
        with p.open("rb") as f:
            raw = f.read(limit + 1)
        return _ok(
            {
                "path": rel(p),
                "text": raw[:limit].decode("utf-8", errors="replace"),
                "truncated": len(raw) > limit,
            }
        )
    except (PathNotAllowed, OSError) as e:
        return _err(str(e))


@tool
def search_files(root: str, pattern: str) -> dict[str, Any]:
    """Find files under `root` whose name matches a glob pattern like '*.pdf'. Max 200 results."""
    try:
        base = resolve_allowed(root)
        hits = []
        for dirpath, _, files in os.walk(base):
            for f in files:
                if fnmatch.fnmatch(f.lower(), pattern.lower()):
                    fp = Path(dirpath) / f
                    hits.append({"path": rel(fp), "bytes": fp.stat().st_size})
                    if len(hits) >= 200:
                        return _ok({"matches": hits, "truncated": True})
        return _ok({"matches": hits, "truncated": False})
    except (PathNotAllowed, OSError) as e:
        return _err(str(e))


@tool
def list_processes(top: int = 15) -> dict[str, Any]:
    """List the top running processes by memory use."""
    procs = []
    for pr in psutil.process_iter(["pid", "name", "memory_info"]):
        mi = pr.info.get("memory_info")
        if mi:
            procs.append({"pid": pr.info["pid"], "name": pr.info["name"], "rss_mb": round(mi.rss / 2**20, 1)})
    procs.sort(key=lambda x: x["rss_mb"], reverse=True)
    return _ok(procs[: max(1, min(top, 50))])


@tool
def system_info() -> dict[str, Any]:
    """OS, CPU count and load, RAM, and free disk space for the allowed folders."""
    vm = psutil.virtual_memory()
    disks = [
        {"root": rel(r), "free_gb": round(psutil.disk_usage(str(r)).free / 2**30, 1)}
        for r in allowed_roots()
        if r.exists()
    ]
    return _ok(
        {
            "os": f"{platform.system()} {platform.release()}",
            "cpus": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=0.2),
            "ram_total_gb": round(vm.total / 2**30, 1),
            "ram_used_percent": vm.percent,
            "disks": disks,
        }
    )


READ_TOOLS = [list_dir, read_file, search_files, list_processes, system_info]
