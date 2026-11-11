"""LangGraph wiring: plan -> act -> observe -> plan, until the planner answers or the step limit hits."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from brain.config import ROOT, load_config
from brain.nodes.act import make_act
from brain.nodes.observe import observe
from brain.nodes.planner import make_planner
from brain.registry import load_tools
from brain.state import AgentState

STEP_LIMIT_MSG = "Stopped: step limit reached. Tell me how to continue."


def _after_plan(state: AgentState) -> str:
    last = state["messages"][-1]
    return "act" if isinstance(last, AIMessage) and last.tool_calls else END


def _after_observe(state: AgentState) -> str:
    return "limit" if state.get("step", 0) >= load_config()["step_limit"] else "plan"


def _limit(state: AgentState) -> dict:
    return {"messages": [AIMessage(STEP_LIMIT_MSG)]}


def build_graph(llm: BaseChatModel | None = None, checkpointer=None):
    tools = load_tools()
    if llm is None:
        from brain.models import SarvamChatModel

        llm = SarvamChatModel()
    g = StateGraph(AgentState)
    g.add_node("plan", make_planner(llm.bind_tools(tools)))
    g.add_node("act", make_act(tools))
    g.add_node("observe", observe)
    g.add_node("limit", _limit)
    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", _after_plan, {"act": "act", END: END})
    g.add_edge("act", "observe")
    g.add_conditional_edges("observe", _after_observe, {"plan": "plan", "limit": "limit"})
    g.add_edge("limit", END)
    return g.compile(checkpointer=checkpointer)


def sqlite_checkpointer() -> SqliteSaver:
    d = Path(load_config()["data_dir"])
    d = d if d.is_absolute() else ROOT / d
    d.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(d / "checkpoints.sqlite", check_same_thread=False))
