import pytest

from brain.checker import Run, verify


def test_checks():
    r = Run(answer="The biggest file is Movie.mp4", tool_calls=[{"name": "list_dir", "args": {}, "ok": True}])
    assert verify(r, {"check": "tool_called", "name": "list_dir"})
    assert not verify(r, {"check": "tool_called", "name": "read_file"})
    assert verify(r, {"check": "answer_contains", "text": "movie.mp4"})
    assert verify(r, {"check": "answer_not_contains", "text": "requires-python"})
    assert verify(r, {"check": "path_exists", "path": "pyproject.toml"})
    assert verify(r, {"check": "file_contains", "path": "pyproject.toml", "text": "brain-agent"})


def test_unknown_check():
    with pytest.raises(ValueError):
        verify(Run(), {"check": "llm_says_ok"})


def test_golden_tasks_use_known_checks():
    from pathlib import Path

    import yaml

    from brain.checker import CHECKS

    for f in Path("evals/golden").glob("*.yaml"):
        t = yaml.safe_load(f.read_text())
        assert t["id"] == f.stem
        assert all(c["check"] in CHECKS for c in t["checks"])
