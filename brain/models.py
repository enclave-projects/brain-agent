"""Sarvam wrappers: SarvamChatModel (DeepSeek via completions_v2) and PrismDecider.

No prompts or business rules here. Facts come from docs/API_NOTES.md and the SDK types.
"""

from __future__ import annotations

import json
import logging
import random
import time
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, ConfigDict
from sarvamai import SarvamAI
from sarvamai.core.api_error import ApiError

from brain.config import get_api_key, load_config

log = logging.getLogger("brain.models")


class ReasoningBudgetExceeded(RuntimeError):
    """content is None and finish_reason == 'length' even after a retry."""


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)
    option: str
    confidence: float
    probs: dict[str, float]


def make_client() -> SarvamAI:
    return SarvamAI(api_subscription_key=get_api_key())


def with_backoff(fn: Callable[[], Any], retries: int = 3) -> Any:
    """Retry 429/503 with exponential backoff + jitter. 400/402/403/404 are not retried."""
    for attempt in range(retries + 1):
        try:
            return fn()
        except ApiError as e:
            if e.status_code not in (429, 503) or attempt == retries:
                raise
            delay = (2**attempt) + random.random()
            log.warning("HTTP %s, retrying in %.1fs", e.status_code, delay)
            time.sleep(delay)


def chat_complete(
    client: SarvamAI,
    *,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    reasoning_effort: str,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any = None,
) -> Any:
    """One DeepSeek call. Retries once on the reasoning-ate-the-budget case."""
    kwargs: dict[str, Any] = {}
    if tools:
        kwargs["tools"] = tools
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice

    def call(mt: int, effort: str) -> Any:
        t0 = time.perf_counter()
        r = with_backoff(
            lambda: client.chat.completions_v2(
                model=model,
                messages=messages,
                max_tokens=mt,
                reasoning_effort=effort,
                **kwargs,
            )
        )
        u = r.usage
        log.info(
            "model=%s latency=%.2fs in=%s out=%s finish=%s",
            model,
            time.perf_counter() - t0,
            u.prompt_tokens if u else None,
            u.completion_tokens if u else None,
            r.choices[0].finish_reason,
        )
        return r

    def starved(r: Any) -> bool:
        m = r.choices[0].message
        return m.content is None and not m.tool_calls and r.choices[0].finish_reason == "length"

    r = call(max_tokens, reasoning_effort)
    if starved(r):
        r = call(max_tokens * 2, "low" if reasoning_effort != "none" else "none")
        if starved(r):
            raise ReasoningBudgetExceeded(f"{model}: no content after retry")
    return r


def _to_wire(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.type == "system":
            out.append({"role": "system", "content": m.content})
        elif m.type == "human":
            out.append({"role": "user", "content": m.content})
        elif m.type == "ai":
            d: dict[str, Any] = {"role": "assistant", "content": m.content or ""}
            calls = getattr(m, "tool_calls", None) or []
            if calls:
                d["tool_calls"] = [
                    {
                        "id": c["id"],
                        "type": "function",
                        "function": {
                            "name": c["name"],
                            "arguments": json.dumps(c["args"]),
                        },
                    }
                    for c in calls
                ]
            out.append(d)
        elif m.type == "tool":
            out.append({"role": "tool", "content": m.content, "tool_call_id": m.tool_call_id})
        else:
            raise ValueError(f"unsupported message type {m.type}")
    return out


class SarvamChatModel(BaseChatModel):
    """LangChain chat model over SarvamAI.chat.completions_v2 (DeepSeek V4.1 Flash)."""

    model_name: str = ""
    max_tokens: int = 0
    reasoning_effort: str = ""
    bound_tools: list[dict[str, Any]] | None = None
    bound_tool_choice: Any = None
    _client: Any = None

    def __init__(self, **kw: Any) -> None:
        cfg = load_config()
        kw.setdefault("model_name", cfg["models"]["planner"])
        kw.setdefault("max_tokens", cfg["planner"]["max_tokens"])
        kw.setdefault("reasoning_effort", cfg["planner"]["reasoning_effort"])
        super().__init__(**kw)
        self._client = make_client()

    @property
    def _llm_type(self) -> str:
        return "sarvam-v2-chat"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable | BaseTool],
        *,
        tool_choice: Any = None,
        **kwargs: Any,
    ) -> SarvamChatModel:
        clone = self.model_copy(
            update={
                "bound_tools": [convert_to_openai_tool(t) for t in tools],
                "bound_tool_choice": tool_choice,
            }
        )
        clone._client = self._client
        return clone

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kw: Any,
    ) -> ChatResult:
        r = chat_complete(
            self._client,
            model=self.model_name,
            messages=_to_wire(messages),
            max_tokens=kw.get("max_tokens", self.max_tokens),
            reasoning_effort=kw.get("reasoning_effort", self.reasoning_effort),
            tools=self.bound_tools,
            tool_choice=self.bound_tool_choice,
        )
        msg = r.choices[0].message
        calls = [
            {
                "id": c.id,
                "name": c.function.name,
                "args": json.loads(c.function.arguments or "{}"),
                "type": "tool_call",
            }
            for c in (msg.tool_calls or [])
        ]
        u = r.usage
        ai = AIMessage(
            content=msg.content or "",
            tool_calls=calls,
            usage_metadata={
                "input_tokens": u.prompt_tokens,
                "output_tokens": u.completion_tokens,
                "total_tokens": u.total_tokens,
            }
            if u
            else None,
            # reasoning_content kept for traces only; never surfaced to users or memory
            additional_kwargs={"reasoning_content": msg.reasoning_content} if msg.reasoning_content else {},
        )
        return ChatResult(generations=[ChatGeneration(message=ai)])


class PrismDecider:
    """Thin wrapper over client.decisions.create. Batch all questions in one request."""

    def __init__(self, client: SarvamAI | None = None) -> None:
        self._client = client or make_client()
        self.model = load_config()["models"]["decider"]

    def ask(self, state: Any, questions: dict[str, dict[str, Any]]) -> Any:
        t0 = time.perf_counter()
        r = with_backoff(
            lambda: self._client.decisions.create(model=self.model, state=state, questions=questions)
        )
        log.info(
            "prism latency=%.2fs in_tokens=%s",
            time.perf_counter() - t0,
            r.usage.input_tokens,
        )
        return r

    def choice(
        self,
        state: Any,
        options: dict[str, str | None],
        instructions: str | None = None,
    ) -> Decision | None:
        """Returns None below thresholds.route_confidence so the caller defers to the planner."""
        q: dict[str, Any] = {"type": "choice", "criteria": options}
        if instructions:
            q["instructions"] = instructions
        a = self.ask(state, {"q": q}).answers["q"]
        d = Decision(option=a.choice, confidence=a.confidence, probs=a.probabilities)
        return d if d.confidence >= load_config()["thresholds"]["route_confidence"] else None
