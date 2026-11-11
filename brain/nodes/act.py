"""Act node: restore placeholders locally, run the one tool call, wrap the result as untrusted."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from brain.privacy import restore
from brain.state import AgentState


def make_act(tools: list[BaseTool]):
    by_name = {t.name: t for t in tools}

    def act(state: AgentState) -> dict[str, Any]:
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
            text = json.dumps(body, ensure_ascii=False, default=str)
            wrapped = f'<untrusted source="tool:{call["name"]}">\n{text}\n</untrusted>'
            out.append(ToolMessage(content=wrapped, tool_call_id=call["id"], name=call["name"]))
        return {"messages": out, "last_result": result}

    return act
