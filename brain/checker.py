"""Code-only verifiers. Never ask an LLM whether something worked."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from brain.config import ROOT


@dataclass
class Run:
    """What happened in one task run, as seen by the checker."""

    answer: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)  # [{"name", "args", "ok"}]


def path_exists(run: Run, path: str) -> bool:
    return (ROOT / path).exists()


def file_contains(run: Run, path: str, text: str) -> bool:
    p = ROOT / path
    return p.is_file() and text in p.read_text(encoding="utf-8", errors="replace")


def tool_called(run: Run, name: str) -> bool:
    return any(c["name"] == name for c in run.tool_calls)


def answer_contains(run: Run, text: str) -> bool:
    return text.lower() in run.answer.lower()


def answer_not_contains(run: Run, text: str) -> bool:
    return text.lower() not in run.answer.lower()


CHECKS: dict[str, Callable[..., bool]] = {
    "path_exists": path_exists,
    "file_contains": file_contains,
    "tool_called": tool_called,
    "answer_contains": answer_contains,
    "answer_not_contains": answer_not_contains,
}


def verify(run: Run, spec: dict[str, Any]) -> bool:
    kind = spec["check"]
    if kind not in CHECKS:
        raise ValueError(f"unknown check {kind!r}")
    return CHECKS[kind](run, **{k: v for k, v in spec.items() if k != "check"})
