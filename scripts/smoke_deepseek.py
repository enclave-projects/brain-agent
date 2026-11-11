"""Phase 0 smoke test 1: DeepSeek V4.1 Flash via SarvamChatModel + LangGraph ToolNode."""

from __future__ import annotations

import logging
import time
from datetime import datetime

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from brain.config import load_config
from brain.models import (
    ReasoningBudgetExceeded,
    SarvamChatModel,
    chat_complete,
    make_client,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
cfg = load_config()
MODEL = cfg["models"]["planner"]


@tool
def get_time() -> str:
    """Return the current local time as an ISO string."""
    return datetime.now().isoformat(timespec="seconds")


def main() -> None:
    client = make_client()

    print("\n[1] plain chat")
    r = chat_complete(
        client,
        model=MODEL,
        messages=[{"role": "user", "content": "Say hi in 5 words."}],
        max_tokens=cfg["planner"]["max_tokens"],
        reasoning_effort="low",
    )
    print(
        "content:",
        r.choices[0].message.content,
        "| usage:",
        r.usage.prompt_tokens,
        r.usage.completion_tokens,
    )

    print("\n[2] raw reproduction of content=None / finish_reason=length (max_tokens=50, effort=high)")
    raw = client.chat.completions_v2(
        model=MODEL,
        max_tokens=50,
        reasoning_effort="high",
        messages=[
            {
                "role": "user",
                "content": "How many prime numbers are below 200? Think carefully.",
            }
        ],
    )
    m = raw.choices[0]
    print("finish:", m.finish_reason, "| content is None:", m.message.content is None)

    print("\n[3] our wrapper retries that case (max_tokens=50 -> 100, effort low)")
    try:
        r = chat_complete(
            client,
            model=MODEL,
            max_tokens=50,
            reasoning_effort="high",
            messages=[
                {
                    "role": "user",
                    "content": "How many prime numbers are below 200? Think carefully.",
                }
            ],
        )
        print("recovered:", (r.choices[0].message.content or "")[:80])
    except ReasoningBudgetExceeded as e:
        print("raised ReasoningBudgetExceeded (expected if still starved):", e)

    print("\n[4] tool-calling round trip inside a LangGraph graph (ToolNode)")
    llm = SarvamChatModel().bind_tools([get_time])

    def agent(state: MessagesState):
        return {"messages": [llm.invoke(state["messages"])]}

    g = StateGraph(MessagesState)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode([get_time]))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    t0 = time.perf_counter()
    out = g.compile().invoke({"messages": [HumanMessage("What time is it right now? Use the tool.")]})
    for m in out["messages"]:
        print(f"  {m.type}: {m.content!r} {getattr(m, 'tool_calls', '') or ''}")
    print(f"  total {time.perf_counter() - t0:.2f}s")
    assert any(m.type == "tool" for m in out["messages"]), "tool was never called"
    print("PASS")


if __name__ == "__main__":
    main()
