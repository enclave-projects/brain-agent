from __future__ import annotations

from typing import Any

from brain.state import AgentState


def observe(state: AgentState) -> dict[str, Any]:
    return {"step": state.get("step", 0) + 1}
