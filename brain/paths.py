"""allowed_roots enforcement. Resolve symlinks and '..' before checking."""

from __future__ import annotations

from pathlib import Path

from brain.config import ROOT, load_config


class PathNotAllowed(PermissionError):
    pass


def allowed_roots() -> list[Path]:
    return [(ROOT / r).resolve() for r in load_config()["allowed_roots"]]


def resolve_allowed(p: str) -> Path:
    raw = Path(p).expanduser()
    full = (raw if raw.is_absolute() else ROOT / raw).resolve()
    if not any(full == r or full.is_relative_to(r) for r in allowed_roots()):
        raise PathNotAllowed(f"{p} is outside allowed_roots")
    return full


def rel(p: Path) -> str:
    """Report paths relative to the repo root so absolute home paths never leave the PC."""
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.name


def is_inside(p: Path) -> bool:
    """True if p (after following symlinks) stays inside allowed_roots."""
    try:
        resolve_allowed(str(p))
        return True
    except PathNotAllowed:
        return False
