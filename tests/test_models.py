from types import SimpleNamespace as NS

import pytest
from sarvamai.core.api_error import ApiError

from brain import models


def _resp(content, finish, tool_calls=None):
    msg = NS(content=content, tool_calls=tool_calls, reasoning_content=None)
    return NS(
        choices=[NS(message=msg, finish_reason=finish)],
        usage=NS(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


def _client(responses):
    calls = []

    def completions_v2(**kw):
        calls.append(kw)
        return responses.pop(0)

    return NS(chat=NS(completions_v2=completions_v2)), calls


def test_retry_on_starved_reasoning():
    c, calls = _client([_resp(None, "length"), _resp("ok", "stop")])
    r = models.chat_complete(c, model="m", messages=[], max_tokens=50, reasoning_effort="high")
    assert r.choices[0].message.content == "ok"
    assert calls[1]["max_tokens"] == 100 and calls[1]["reasoning_effort"] == "low"


def test_raises_when_still_starved():
    c, _ = _client([_resp(None, "length"), _resp(None, "length")])
    with pytest.raises(models.ReasoningBudgetExceeded):
        models.chat_complete(c, model="m", messages=[], max_tokens=50, reasoning_effort="high")


def test_backoff_does_not_retry_400(monkeypatch):
    n = {"i": 0}

    def f():
        n["i"] += 1
        raise ApiError(status_code=400, body="bad")

    with pytest.raises(ApiError):
        models.with_backoff(f)
    assert n["i"] == 1


def test_backoff_retries_429(monkeypatch):
    monkeypatch.setattr(models.time, "sleep", lambda s: None)
    n = {"i": 0}

    def f():
        n["i"] += 1
        if n["i"] < 3:
            raise ApiError(status_code=429, body="slow")
        return "ok"

    assert models.with_backoff(f) == "ok"
