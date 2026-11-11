"""Tool loading with the tier check: a tool without a tier in permissions.yaml fails to load."""

from __future__ import annotations

import yaml
from langchain_core.tools import BaseTool

from brain.config import ROOT

TIERS = {"read", "reversible", "irreversible"}


class MissingTier(RuntimeError):
    pass


def load_tiers() -> dict[str, str]:
    with (ROOT / "config" / "permissions.yaml").open(encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("tools") or {}


def check_tiers(tools: list[BaseTool]) -> dict[str, str]:
    tiers = load_tiers()
    for t in tools:
        if tiers.get(t.name) not in TIERS:
            raise MissingTier(f"tool {t.name!r} has no valid tier in config/permissions.yaml")
    return {t.name: tiers[t.name] for t in tools}


def load_tools(include_test: bool | None = None) -> list[BaseTool]:
    from brain.config import load_config
    from tools.readonly import READ_TOOLS

    tools = list(READ_TOOLS)
    if include_test is None:
        include_test = bool(load_config().get("enable_test_tools"))
    if include_test:
        from tools.testtools import TEST_TOOLS

        tools += TEST_TOOLS
    check_tiers(tools)
    return tools
