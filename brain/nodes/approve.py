"""Approval node. interrupt() pauses the graph; ONLY a human key press in cli.py resumes it.

On resume LangGraph re-runs this node from the top, so everything before interrupt() is a pure read.
Logging happens after the interrupt returns.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from brain import decisionlog
from brain.nodes.router import _thread
from brain.privacy import redact, restore
from brain.state import AgentState

_PATH_KEYS = ("path", "root", "src", "dst", "source", "destination", "url")


def approval_request(state: AgentState) -> dict[str, Any]:
    call = state["messages"][-1].tool_calls[0]
    pii = state.get("pii_map") or {}
    args = json.loads(restore(json.dumps(call["args"]), pii))  # show the REAL values to the human
    return {
        "tool": call["name"],
        "args": args,
        "affects": [str(v) for k, v in args.items() if k in _PATH_KEYS],
        "tier": state["guard"].get("tier"),
        "why": state["guard"].get("reason"),
        "prism_risk": (state.get("prism") or {}).get("risk"),
    }


def approve(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    call = state["messages"][-1].tool_calls[0]
    decision = interrupt(approval_request(state))
    approved = decision is True  # anything other than a literal True is a denial
    decisionlog.log_event(
        "approval",
        _thread(config),
        state.get("step", 0),
        tool=call["name"],
        args=json.loads(redact(json.dumps(call["args"]), {})),
        tier=state["guard"].get("tier"),
        approved=int(approved),
    )
    out: dict[str, Any] = {"guard": {**state["guard"], "approved": approved}}
    if not approved:
        out["messages"] = [
            ToolMessage(
                "Denied by the user. Do not retry this action unless the user asks again; "
                "offer an alternative or ask what they want.",
                tool_call_id=call["id"],
                name=call["name"],
            )
        ]
    return out
