"""Guard node: applies brain.guard rules, logs, and routes to run / approve / block."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from brain import decisionlog
from brain.config import load_config
from brain.guard import decide
from brain.nodes.router import _thread
from brain.privacy import redact
from brain.state import AgentState


def make_guard(tiers: dict[str, str]):
    def guard(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        call = state["messages"][-1].tool_calls[0]
        prism = state.get("prism") or {}
        d = decide(tiers.get(call["name"]), prism.get("risk"), load_config()["thresholds"]["risk_noul"])
        decisionlog.log_event(
            "guard",
            _thread(config),
            state.get("step", 0),
            tool=call["name"],
            args=json.loads(redact(json.dumps(call["args"]), {})),
            tier=d.tier,
            action=d.action,
            risk=prism.get("risk"),
            detail=d.reason,
        )
        out: dict[str, Any] = {"guard": {"action": d.action, "tier": d.tier, "reason": d.reason}}
        if d.action == "block":
            out["messages"] = [
                ToolMessage(f"Blocked: {d.reason}", tool_call_id=call["id"], name=call["name"])
            ]
        return out

    return guard


def after_guard(state: AgentState) -> str:
    return {"block": "observe", "approve": "approve"}.get(state["guard"]["action"], "act")


def after_approve(state: AgentState) -> str:
    return "act" if state["guard"].get("approved") else "observe"


__all__ = ["AIMessage", "after_approve", "after_guard", "make_guard"]
