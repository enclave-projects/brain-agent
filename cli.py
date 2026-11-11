"""Text REPL. No agent logic here: it feeds input to the graph and prints each step."""

from __future__ import annotations

import argparse
import json

from langchain_core.messages import AIMessage, HumanMessage

from brain.graph import build_graph, sqlite_checkpointer
from brain.privacy import restore


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
    args = ap.parse_args()
    graph = build_graph(checkpointer=sqlite_checkpointer())
    cfg = {"configurable": {"thread_id": args.thread}}

    def run(text: str) -> None:
        inp = {"goal": text, "step": 0, "messages": [HumanMessage(text)]}
        for update in graph.stream(inp, cfg, stream_mode="updates"):
            for node, val in update.items():
                if node == "act":
                    r = val.get("last_result") or {}
                    print(f"  [step] {r.get('tool')}({r.get('args')}) -> {_summary(r)}")
                elif node in ("plan", "limit"):
                    m = val["messages"][-1]
                    if isinstance(m, AIMessage) and not m.tool_calls:
                        pii = graph.get_state(cfg).values.get("pii_map") or {}
                        print(f"\nagent> {restore(m.content, pii)}\n")  # local display only

    if args.query:
        run(args.query)
        return
    print(f"brain-agent (thread={args.thread}). Read-only. Ctrl+C to quit.")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text:
            run(text)


if __name__ == "__main__":
    main()
