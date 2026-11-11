from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


def merge_dict(a: dict[str, str] | None, b: dict[str, str] | None) -> dict[str, str]:
    return {**(a or {}), **(b or {})}


class AgentState(TypedDict, total=False):
    goal: str
    messages: Annotated[list[AnyMessage], add_messages]
    plan: str
    last_result: dict[str, Any]
    step: int
    pii_map: Annotated[dict[str, str], merge_dict]  # local only, never sent
