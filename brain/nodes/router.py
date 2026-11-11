"""Router node: ONE Prism request per proposal, batching a `choice` (which tool fits the goal) and a
`noul` (could this lose data or contact someone). Prism confirms or vetoes the planner's tool; it never
supplies arguments. Prism only ever sees redacted text.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool

from brain import decisionlog
from brain.config import load_config
from brain.privacy import redact
from brain.state import AgentState

log = logging.getLogger("brain.router")


def _thread(config: RunnableConfig) -> str:
    return (config.get("configurable") or {}).get("thread_id", "-")


def prism_state(goal: str, last: dict[str, Any], proposal: dict[str, Any], pii: dict[str, str]) -> str:
    obs = json.dumps({k: last.get(k) for k in ("tool", "ok", "error")}, default=str) if last else "none"
    return redact(
        f"Goal: {goal}\nLast result: {obs}\nProposed next action: {proposal['name']} "
        f"with arguments {json.dumps(proposal['args'], ensure_ascii=False)}",
        pii,
    )


def make_router(tools: list[BaseTool], decider: Any):
    options = {t.name: (t.description or "").split("\n")[0][:200] for t in tools}

    def route(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        cfg = load_config()
        last = state["messages"][-1]
        assert isinstance(last, AIMessage) and last.tool_calls
        call = last.tool_calls[0]
        proposal = {"name": call["name"], "args": call["args"]}
        pii: dict[str, str] = {}
        prism: dict[str, Any] = {"ok": False}
        verdict, veto_note = "unavailable", None
        try:
            r = decider.ask(
                prism_state(state.get("goal", ""), state.get("last_result") or {}, proposal, pii),
                {
                    "tool": {
                        "type": "choice",
                        "criteria": options,
                        "instructions": "Which tool is the best next step to make progress on the goal?",
                    },
                    "risky": {
                        "type": "noul",
                        "instructions": "Could carrying out the proposed action lose data, change "
                        "settings, or contact someone? Reading or listing is not risky.",
                    },
                },
            )
            a = r.answers["tool"]
            prism = {
                "ok": True,
                "choice": a.choice,
                "confidence": a.confidence,
                "p_top": a.probabilities[a.choice],
                "p_proposed": a.probabilities.get(proposal["name"]),
                "risk": r.answers["risky"].noul,
            }
            if a.choice == proposal["name"]:
                verdict = "confirm"
            elif (
                a.confidence >= cfg["thresholds"]["route_confidence"]
                and state.get("last_veto") != proposal["name"]
            ):
                verdict = "veto"  # a repeat of a vetoed tool means the planner insists: it stands
            else:
                verdict = "defer"
        except Exception as e:  # noqa: BLE001  # Prism down / timeout: planner's choice stands, guard fails closed
            log.warning("prism unavailable: %s", e)
            prism["error"] = f"{type(e).__name__}: {e}"[:200]

        decisionlog.log_event(
            "route",
            _thread(config),
            state.get("step", 0),
            tool=proposal["name"],
            args=json.loads(redact(json.dumps(proposal["args"]), {})),
            prism_choice=prism.get("choice"),
            prism_conf=prism.get("confidence"),
            p_top=prism.get("p_top"),
            p_proposed=prism.get("p_proposed"),
            risk=prism.get("risk"),
            verdict=verdict,
            detail=prism.get("error"),
        )
        out: dict[str, Any] = {"prism": prism, "pii_map": pii, "last_veto": None}
        if verdict == "veto":
            veto_note = (
                f"Router check: '{prism['choice']}' looks like a better fit than '{proposal['name']}' for the "
                f"goal. Reconsider. If you are still sure '{proposal['name']}' is right, call it again."
            )
            out["last_veto"] = proposal["name"]
            out["messages"] = [ToolMessage(veto_note, tool_call_id=call["id"], name=call["name"])]
            out["guard"] = {"action": "veto"}
        return out

    return route


def after_route(state: AgentState) -> str:
    return "observe" if (state.get("guard") or {}).get("action") == "veto" else "guard"
