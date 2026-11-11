"""Text REPL. No agent logic here: it feeds input to the graph and prints each step."""

from __future__ import annotations

import argparse
import json

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from brain.graph import build_graph, sqlite_checkpointer
from brain.privacy import restore
from brain.registry import load_tools


def _summary(body: dict, n: int = 160) -> str:
    if not body:
        return ""
    if not body.get("ok", True):
        return f"ERROR {body.get('error')}"
    s = json.dumps(body.get("data"), default=str)
    return s if len(s) <= n else s[:n] + "..."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--thread", default="default", help="conversation id (persists between runs)")
    ap.add_argument("-q", "--query", help="run one query and exit")
    ap.add_argument("--test-tools", action="store_true", help="load Phase 2 stub tools (they change nothing)")
    args = ap.parse_args()
    graph = build_graph(
        checkpointer=sqlite_checkpointer(), tools=load_tools(include_test=True) if args.test_tools else None
    )
    cfg = {"configurable": {"thread_id": args.thread}}

    def ask_human(req: dict) -> bool:
        """Approval is a typed confirmation at the keyboard. Never the model, a file or a transcript."""
        print("\n  APPROVAL NEEDED")
        print(f"  tool:    {req['tool']}  (tier: {req['tier']})")
        print(f"  args:    {json.dumps(req['args'], ensure_ascii=False)}")
        if req["affects"]:
            print(f"  affects: {', '.join(req['affects'])}")
        print(f"  why:     {req['why']}  (Prism risk: {req['prism_risk']})")
        try:
            return input("  type 'yes' to approve, anything else denies: ").strip().lower() == "yes"
        except EOFError:
            return False

    def drive(inp) -> None:
        """Stream one graph run; if it pauses for approval, ask and resume until it finishes."""
        while True:
            pending = None
            for update in graph.stream(inp, cfg, stream_mode="updates"):
                for node, val in update.items():
                    if node == "__interrupt__":
                        pending = val[0].value
                    elif node == "route" and (val.get("prism") or {}).get("choice"):
                        p = val["prism"]
                        print(
                            f"  [prism] choice={p['choice']} conf={p['confidence']:.2f} risk={p['risk']:.2f}"
                        )
                    elif node == "guard":
                        print(f"  [guard] {val['guard']['action']} ({val['guard'].get('reason')})")
                    elif node == "act":
                        r = val.get("last_result") or {}
                        print(f"  [step] {r.get('tool')}({r.get('args')}) -> {_summary(r)}")
                    elif node in ("plan", "limit"):
                        m = val["messages"][-1]
                        if isinstance(m, AIMessage) and not m.tool_calls:
                            pii = graph.get_state(cfg).values.get("pii_map") or {}
                            print(f"\nagent> {restore(m.content, pii)}\n")  # local display only
            if pending is None:
                return
            inp = Command(resume=ask_human(pending))

    def run(text: str) -> None:
        drive({"goal": text, "step": 0, "messages": [HumanMessage(text)]})

    if args.query:
        run(args.query)
        return
    print(
        f"brain-agent (thread={args.thread}). Irreversible actions need your typed approval. Ctrl+C to quit."
    )
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text:
            run(text)


if __name__ == "__main__":
    main()
