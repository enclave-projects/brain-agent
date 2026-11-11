"""Act node: restore placeholders locally, run the one tool call, wrap the result as untrusted."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from brain import decisionlog
from brain.nodes.router import _thread
from brain.privacy import redact, restore
from brain.state import AgentState


def make_act(tools: list[BaseTool]):
    by_name = {t.name: t for t in tools}

    def act(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        last = state["messages"][-1]
        assert isinstance(last, AIMessage) and last.tool_calls
        pii = state.get("pii_map") or {}
        out = []
        result: dict[str, Any] = {}
        for i, call in enumerate(last.tool_calls):
            if i > 0:  # one tool call per turn
                body = {"ok": False, "error": "only one tool call per turn; call it again next turn"}
            elif call["name"] not in by_name:
                body = {"ok": False, "error": f"unknown tool {call['name']}"}
            else:
                args = json.loads(restore(json.dumps(call["args"]), pii))
                body = by_name[call["name"]].invoke(args)
                result = {"tool": call["name"], "args": call["args"], **body}
                g = state.get("guard") or {}
                decisionlog.log_event(
                    "executed",
                    _thread(config),
                    state.get("step", 0),
                    tool=call["name"],
                    args=json.loads(redact(json.dumps(call["args"]), {})),
                    tier=g.get("tier"),
                    action=g.get("action"),
                    approved=int(bool(g.get("approved"))),
                    ok=int(bool(body.get("ok"))),
                    undo=body.get("undo"),
                )
            text = json.dumps(body, ensure_ascii=False, default=str)
            wrapped = f'<untrusted source="tool:{call["name"]}">\n{text}\n</untrusted>'
            out.append(ToolMessage(content=wrapped, tool_call_id=call["id"], name=call["name"]))
        return {"messages": out, "last_result": result}

    return act
