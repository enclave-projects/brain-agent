import json

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage

from brain import registry
from brain.graph import STEP_LIMIT_MSG, build_graph
from brain.paths import PathNotAllowed, resolve_allowed
from brain.privacy import redact, restore
from tools.readonly import READ_TOOLS, list_dir, read_file, search_files


@pytest.fixture
def dl(tmp_path, monkeypatch):
    import brain.paths as bp

    (tmp_path / "sandbox" / "Downloads").mkdir(parents=True)
    (tmp_path / "sandbox" / "Downloads" / "big.bin").write_bytes(b"0" * 5000)
    (tmp_path / "sandbox" / "Downloads" / "a.txt").write_text("hello")
    (tmp_path / "secret.txt").write_text("nope")
    monkeypatch.setattr(bp, "ROOT", tmp_path)
    return tmp_path


def test_paths_block_escape(dl):
    for bad in ["/etc/passwd", "sandbox/../secret.txt", str(dl / "secret.txt")]:
        with pytest.raises(PathNotAllowed):
            resolve_allowed(bad)
    assert resolve_allowed("sandbox/Downloads/a.txt").name == "a.txt"


def test_symlink_escape_blocked(dl):
    (dl / "sandbox" / "link").symlink_to(dl / "secret.txt")
    with pytest.raises(PathNotAllowed):
        resolve_allowed("sandbox/link")


def test_tools_refuse_outside(dl):
    r = read_file.invoke({"path": "sandbox/../secret.txt"})
    assert not r["ok"] and "allowed_roots" in r["error"]
    assert not search_files.invoke({"root": "/", "pattern": "*"})["ok"]


def test_list_dir_sorted_by_size(dl):
    r = list_dir.invoke({"path": "sandbox/Downloads"})
    assert r["ok"] and r["data"]["entries"][0]["name"] == "big.bin"


def test_read_file_cap(dl, monkeypatch):
    import tools.readonly as ro

    monkeypatch.setattr(ro, "load_config", lambda: {"read_max_bytes": 10})
    r = read_file.invoke({"path": "sandbox/Downloads/big.bin"})
    assert r["data"]["truncated"] and len(r["data"]["text"]) == 10


def test_redact_roundtrip():
    m = {}
    s = "mail a.b@x.com call +91 9876543210 aadhaar 1234 5678 9012 pan ABCDE1234F"
    r = redact(s, m)
    assert "a.b@x.com" not in r and "9876543210" not in r and "ABCDE1234F" not in r and "5678" not in r
    assert redact(r, {}) == r  # idempotent
    assert restore(r, m) == s


def test_missing_tier_fails(monkeypatch):
    monkeypatch.setattr(registry, "load_tiers", lambda: {"list_dir": "read"})
    with pytest.raises(registry.MissingTier):
        registry.check_tiers(READ_TOOLS)


def test_all_tools_have_tiers():
    assert set(registry.check_tiers(READ_TOOLS).values()) == {"read"}


class _Fake(GenericFakeChatModel):
    def bind_tools(self, tools, **kw):
        return self


def _call(name, args, i=0):
    return AIMessage("", tool_calls=[{"id": f"c{i}", "name": name, "args": args, "type": "tool_call"}])


def test_graph_round_trip_and_redaction(dl):
    seen = []

    class Spy(_Fake):
        def _generate(self, messages, *a, **k):
            seen.append(" ".join(str(m.content) for m in messages))
            return super()._generate(messages, *a, **k)

    llm = Spy(messages=iter([_call("list_dir", {"path": "sandbox/Downloads"}), AIMessage("done")]))
    out = build_graph(llm).invoke({"messages": [HumanMessage("x@y.com: what's in Downloads?")], "step": 0})
    assert out["messages"][-1].content == "done" and out["step"] == 1
    tool_msg = out["messages"][2]
    assert tool_msg.content.startswith('<untrusted source="tool:list_dir">')
    assert all("x@y.com" not in s for s in seen)


def test_placeholder_restored_before_tool(dl):
    (dl / "sandbox" / "Downloads" / "9876543210.txt").write_text("phone-named file")
    tag = redact("9876543210", m := {})
    llm = _Fake(
        messages=iter([_call("read_file", {"path": f"sandbox/Downloads/{tag}.txt"}), AIMessage("ok")])
    )
    out = build_graph(llm).invoke({"messages": [HumanMessage("read 9876543210.txt")], "step": 0})
    body = json.loads(out["messages"][2].content.split("\n", 1)[1].rsplit("\n", 1)[0])
    assert body["ok"] and body["data"]["text"] == "phone-named file"
    assert m


def test_step_limit(dl, monkeypatch):
    import brain.graph as g

    monkeypatch.setattr(g, "load_config", lambda: {"step_limit": 3})
    llm = _Fake(messages=iter([_call("system_info", {}, i) for i in range(10)]))
    out = build_graph(llm).invoke({"messages": [HumanMessage("loop")], "step": 0})
    assert out["step"] == 3 and out["messages"][-1].content == STEP_LIMIT_MSG


def test_person_names_redacted(monkeypatch):
    import brain.privacy as pv

    cfg = {**pv.load_config(), "privacy": {**pv.load_config()["privacy"], "always_redact": ["Pranjal"]}}
    monkeypatch.setattr(pv, "load_config", lambda: cfg)
    m = {}
    s = "Pranjal says: send it to Rahul Sharma. Read sandbox/Downloads/Anjali_Gupta_invoice.pdf in my Downloads"
    r = redact(s, m)
    for name in ["Pranjal", "Rahul Sharma", "Anjali", "Gupta"]:
        assert name not in r
    assert "Downloads" in r and "sandbox" in r
    assert restore(r, m) == s
    assert redact(r, {}) == r


def test_outside_symlink_not_leaked(dl):
    (dl / "sandbox" / "Downloads" / "shortcut.txt").symlink_to(dl / "secret.txt")
    entries = {e["name"]: e for e in list_dir.invoke({"path": "sandbox/Downloads"})["data"]["entries"]}
    assert entries["shortcut.txt"] == {
        "name": "shortcut.txt",
        "type": "link-outside-allowed-roots",
        "bytes": 0,
    }
    hits = search_files.invoke({"root": "sandbox", "pattern": "*.txt"})["data"]["matches"]
    assert [h["path"] for h in hits] == ["sandbox/Downloads/a.txt"]
