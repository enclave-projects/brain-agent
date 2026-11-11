import pytest
from conftest import FakeDecider
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from brain import decisionlog
from brain.graph import build_graph
from brain.guard import decide
from brain.registry import load_tools


class Fake(GenericFakeChatModel):
    def bind_tools(self, tools, **kw):
        return self


def call(name, args, i=0):
    return AIMessage("", tool_calls=[{"id": f"c{i}", "name": name, "args": args, "type": "tool_call"}])


@pytest.fixture
def g(tmp_path, monkeypatch):
    import brain.paths as bp

    (tmp_path / "sandbox" / "Downloads").mkdir(parents=True)
    (tmp_path / "sandbox" / "Downloads" / "a.txt").write_text("hi")
    monkeypatch.setattr(bp, "ROOT", tmp_path)

    def make(msgs, decider=None):
        llm = Fake(messages=iter(msgs))
        return build_graph(
            llm, checkpointer=MemorySaver(), decider=decider or FakeDecider(), tools=load_tools(True)
        )

    return make


CFG = {"configurable": {"thread_id": "t"}}


def start(graph, text="go"):
    return graph.invoke({"goal": text, "step": 0, "messages": [HumanMessage(text)]}, CFG)


# ---- pure guard rules
def test_guard_tiers():
    assert decide("read", 0.05, 0.3).action == "run"
    assert decide("reversible", 0.05, 0.3).action == "log_run"
    assert decide("irreversible", 0.0, 0.3).action == "approve"


def test_guard_only_stricter():
    assert decide("read", 0.9, 0.3).action == "approve"  # risky read lifted
    assert decide("reversible", 0.31, 0.3).action == "approve"
    assert decide("irreversible", 0.0, 0.3).action == "approve"  # low risk never lowers it


def test_guard_fail_closed_and_unknown():
    assert decide("read", None, 0.3).action == "run"
    assert decide("reversible", None, 0.3).action == "approve"
    assert decide(None, 0.0, 0.3).action == "block"
    assert decide("bogus", 0.0, 0.3).action == "block"


# ---- graph flows
def test_read_runs_without_asking(g):
    graph = g([call("list_dir", {"path": "sandbox/Downloads"}), AIMessage("done")])
    out = start(graph)
    assert "__interrupt__" not in out and out["messages"][-1].content == "done"
    assert [r["action"] for r in decisionlog.rows("t") if r["event"] == "guard"] == ["run"]


def test_irreversible_always_pauses_even_at_zero_risk(g):
    graph = g(
        [call("test_delete", {"path": "sandbox/Downloads/a.txt"}), AIMessage("done")], FakeDecider(risk=0.0)
    )
    out = start(graph)
    req = out["__interrupt__"][0].value
    assert req["tool"] == "test_delete" and req["args"] == {"path": "sandbox/Downloads/a.txt"}
    assert req["affects"] == ["sandbox/Downloads/a.txt"]
    assert not [r for r in decisionlog.rows("t") if r["event"] == "executed"]  # nothing ran yet


def test_approve_runs_and_deny_blocks(g):
    graph = g([call("test_delete", {"path": "sandbox/Downloads/a.txt"}), AIMessage("done")])
    start(graph)
    out = graph.invoke(Command(resume=True), CFG)
    assert out["messages"][-1].content == "done"
    ex = [r for r in decisionlog.rows("t") if r["event"] == "executed"]
    assert len(ex) == 1 and ex[0]["approved"] == 1 and decisionlog.unsafe_count("t") == 0


def test_denied_never_executes_and_planner_is_told(g):
    graph = g([call("test_delete", {"path": "sandbox/Downloads/a.txt"}), AIMessage("ok, not deleting")])
    start(graph)
    out = graph.invoke(Command(resume=False), CFG)
    assert not [r for r in decisionlog.rows("t") if r["event"] == "executed"]
    assert any("Denied by the user" in str(m.content) for m in out["messages"])


@pytest.mark.parametrize("answer", ["yes", "true", 1, "approve", False])
def test_only_literal_true_approves(g, answer):
    graph = g([call("test_delete", {"path": "sandbox/Downloads/a.txt"}), AIMessage("done")])
    start(graph)
    graph.invoke(Command(resume=answer), CFG)
    assert not [r for r in decisionlog.rows("t") if r["event"] == "executed"]


def test_interrupt_rerun_does_not_duplicate_log(g):
    graph = g([call("test_delete", {"path": "sandbox/Downloads/a.txt"}), AIMessage("done")])
    start(graph)
    graph.invoke(Command(resume=True), CFG)
    ev = [r["event"] for r in decisionlog.rows("t")]
    assert ev.count("route") == 1 and ev.count("guard") == 1 and ev.count("approval") == 1


def test_reversible_runs_and_logs_undo(g):
    graph = g(
        [call("test_rename", {"path": "sandbox/Downloads/a.txt", "new_name": "b.txt"}), AIMessage("done")]
    )
    out = start(graph)
    assert "__interrupt__" not in out
    ex = next(r for r in decisionlog.rows("t") if r["event"] == "executed")
    assert ex["undo"] and "test_rename" in ex["undo"]


def test_high_prism_risk_lifts_reversible_to_approval(g):
    graph = g(
        [call("test_rename", {"path": "sandbox/Downloads/a.txt", "new_name": "b"}), AIMessage("x")],
        FakeDecider(risk=0.6),
    )
    assert "__interrupt__" in start(graph)


def test_prism_down_fails_closed_for_writes_but_reads_run(g):
    graph = g(
        [call("test_rename", {"path": "sandbox/Downloads/a.txt", "new_name": "b"}), AIMessage("x")],
        FakeDecider(fail=True),
    )
    assert "__interrupt__" in start(graph)
    graph2 = g([call("system_info", {}), AIMessage("x")], FakeDecider(fail=True))
    CFG2 = {"configurable": {"thread_id": "t2"}}
    out = graph2.invoke({"goal": "x", "step": 0, "messages": [HumanMessage("x")]}, CFG2)
    assert "__interrupt__" not in out


def test_veto_sends_planner_back_then_planner_can_insist(g):
    d = FakeDecider(choice="list_dir", confidence=0.95)
    graph = g(
        [call("system_info", {}, 0), call("system_info", {}, 1), AIMessage("done")],
        d,
    )
    out = start(graph)
    verdicts = [r["verdict"] for r in decisionlog.rows("t") if r["event"] == "route"]
    assert verdicts == ["veto", "defer"]  # second time the planner insists, so it stands
    assert any("Router check" in str(m.content) for m in out["messages"])
    assert out["messages"][-1].content == "done"


def test_low_confidence_defers_to_planner(g):
    graph = g([call("system_info", {}), AIMessage("done")], FakeDecider(choice="list_dir", confidence=0.4))
    start(graph)
    assert [r["verdict"] for r in decisionlog.rows("t") if r["event"] == "route"] == ["defer"]


def test_prism_never_sees_pii_and_decisions_logged_with_confidence(g):
    d = FakeDecider()
    graph = g([call("read_file", {"path": "sandbox/Downloads/a.txt"}), AIMessage("done")], d)
    graph.invoke({"goal": "mail me at a.b@x.com", "step": 0, "messages": [HumanMessage("x")]}, CFG)
    assert all("a.b@x.com" not in s for s, _ in d.calls)
    r = next(r for r in decisionlog.rows("t") if r["event"] == "route")
    assert r["prism_conf"] == 0.9 and r["risk"] == 0.05 and r["verdict"] == "confirm"


def test_logged_args_are_redacted(g):
    graph = g([call("search_files", {"root": "sandbox", "pattern": "a.b@x.com"}), AIMessage("done")])
    start(graph)
    assert all("a.b@x.com" not in str(r["args"]) for r in decisionlog.rows("t") if r["args"])


def test_unknown_tool_is_blocked(g):
    graph = g(
        [call("rm_rf", {"path": "/"}), AIMessage("done")], FakeDecider(confidence=0.4)
    )  # defer -> guard
    out = start(graph)
    assert any("Blocked" in str(m.content) for m in out["messages"])
    assert not [r for r in decisionlog.rows("t") if r["event"] == "executed"]
