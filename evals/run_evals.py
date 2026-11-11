"""Golden suite runner: each task 3x, pass^3 headline. Reports to evals/reports/<date>.{md,json}.

uv run python evals/run_evals.py             # golden set (excludes frozen/)
uv run python evals/run_evals.py --frozen    # held-out set only, never tune on it
uv run python evals/run_evals.py -k read-file   # only task ids containing this
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from brain import decisionlog
from brain.checker import Run, verify
from brain.config import ROOT, load_config
from brain.graph import build_graph
from brain.privacy import restore
from brain.registry import load_tools
from scripts import make_fixture

GOLDEN = ROOT / "evals" / "golden"
SETUPS = {"downloads": make_fixture.main}


def load_tasks(frozen: bool, k: str | None) -> list[dict]:
    files = sorted((GOLDEN / "frozen").glob("*.yaml")) if frozen else sorted(GOLDEN.glob("*.yaml"))
    tasks = [yaml.safe_load(f.read_text(encoding="utf-8")) for f in files]
    return [t for t in tasks if not k or k in t["id"]]


def run_once(graph, task: dict) -> dict:
    for step in task.get("setup") or []:
        SETUPS[step["fixture"]]()
    t0 = time.perf_counter()
    cfg = {"configurable": {"thread_id": f"eval-{task['id']}-{time.time_ns()}"}}
    out = graph.invoke(
        {"goal": task["instruction"], "step": 0, "messages": [HumanMessage(task["instruction"])]}, cfg
    )
    approvals = 0
    while "__interrupt__" in out:  # the runner is not a human: every approval request is denied
        approvals += 1
        out = graph.invoke(Command(resume=False), cfg)
    latency = time.perf_counter() - t0
    msgs = out["messages"]
    results = {m.tool_call_id: m.content for m in msgs if isinstance(m, ToolMessage)}
    calls, tin, tout = [], 0, 0
    for m in msgs:
        if isinstance(m, AIMessage):
            u = m.usage_metadata or {}
            tin += u.get("input_tokens", 0)
            tout += u.get("output_tokens", 0)
            for c in m.tool_calls:
                calls.append(
                    {"name": c["name"], "args": c["args"], "ok": '"ok": true' in results.get(c["id"], "")}
                )
    run = Run(answer=restore(msgs[-1].content or "", out.get("pii_map") or {}), tool_calls=calls)
    checks = [{**c, "pass": verify(run, c)} for c in task["checks"]]
    over = out.get("step", 0) > task.get("max_steps", 99)
    return {
        "pass": all(c["pass"] for c in checks)
        and not over
        and (approvals > 0 if task.get("expects_approval") else approvals == 0),
        "checks": checks,
        "steps": out.get("step", 0),
        "approval_requests": approvals,
        "unsafe_actions": decisionlog.unsafe_count(cfg["configurable"]["thread_id"]),
        "approval_ok": approvals > 0 if task.get("expects_approval") else approvals == 0,
        "over_max_steps": over,
        "latency_s": round(latency, 2),
        "tokens_in": tin,
        "tokens_out": tout,
        "tools": [c["name"] for c in calls],
        "answer": run.answer[:300],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frozen", action="store_true")
    ap.add_argument("-k", help="only task ids containing this")
    ap.add_argument("-n", type=int, default=3, help="runs per task")
    a = ap.parse_args()
    cfg = load_config()
    price = cfg["pricing_inr_per_1m"][cfg["models"]["planner"]]
    graph = build_graph(checkpointer=MemorySaver(), tools=load_tools(include_test=True))
    tasks = load_tasks(a.frozen, a.k)
    rows = []
    for t in tasks:
        runs = [run_once(graph, t) for _ in range(a.n)]
        tin = sum(r["tokens_in"] for r in runs)
        tout = sum(r["tokens_out"] for r in runs)
        row = {
            "id": t["id"],
            "pass_all": all(r["pass"] for r in runs),
            "passes": sum(r["pass"] for r in runs),
            "avg_latency_s": round(sum(r["latency_s"] for r in runs) / a.n, 2),
            "avg_steps": round(sum(r["steps"] for r in runs) / a.n, 1),
            "cost_inr": round((tin * price["input"] + tout * price["output"]) / 1e6, 4),
            "runs": runs,
        }
        rows.append(row)
        print(f"{'PASS' if row['pass_all'] else 'FAIL'}  {row['passes']}/{a.n}  {t['id']}")
    summary = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "set": "frozen" if a.frozen else "golden",
        "runs_per_task": a.n,
        "tasks": len(rows),
        "pass_hat_n": round(sum(r["pass_all"] for r in rows) / max(len(rows), 1), 3),
        "interventions": sum(r["approval_requests"] for row in rows for r in row["runs"]),
        "intervention_rate": round(
            sum(r["approval_requests"] > 0 for row in rows for r in row["runs"]) / max(len(rows) * a.n, 1), 3
        ),
        "unsafe_actions": sum(r["unsafe_actions"] for row in rows for r in row["runs"]),
        "total_cost_inr": round(sum(r["cost_inr"] for r in rows), 4),
    }
    out_dir = ROOT / "evals" / "reports"
    out_dir.mkdir(exist_ok=True)
    stem = out_dir / f"{datetime.now():%Y-%m-%d_%H%M}{'_frozen' if a.frozen else ''}"
    stem.with_suffix(".json").write_text(
        json.dumps({"summary": summary, "tasks": rows}, indent=2), encoding="utf-8"
    )
    md = [
        f"# Eval report {summary['date']} ({summary['set']})",
        "",
        (
            f"**pass^{a.n}: {summary['pass_hat_n']:.0%}** over {len(rows)} tasks · "
            f"interventions: {summary['interventions']} · unsafe actions: {summary['unsafe_actions']} · cost: ₹{summary['total_cost_inr']}"
        ),
        "",
        "| task | pass | avg steps | avg latency | ₹ | failing checks |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        fails = sorted(
            {
                f"{c['check']}:{c.get('text') or c.get('name') or c.get('path')}"
                for run in r["runs"]
                for c in run["checks"]
                if not c["pass"]
            }
        )
        md.append(
            f"| {r['id']} | {r['passes']}/{a.n} | {r['avg_steps']} | {r['avg_latency_s']}s | "
            f"{r['cost_inr']} | {', '.join(fails) or '-'} |"
        )
    stem.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\npass^{a.n} = {summary['pass_hat_n']:.0%}  ->  {stem}.md")


if __name__ == "__main__":
    main()
