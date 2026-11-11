from types import SimpleNamespace as NS

import pytest


class FakeDecider:
    """Stands in for PrismDecider. Echoes the proposed tool by default (confirm), fixed risk."""

    def __init__(self, choice=None, confidence=0.9, risk=0.05, fail=False):
        self.choice, self.confidence, self.risk, self.fail = choice, confidence, risk, fail
        self.calls = []

    def ask(self, state, questions):
        self.calls.append((state, questions))
        if self.fail:
            raise RuntimeError("prism down")
        options = list(questions["tool"]["criteria"])
        choice = self.choice or next((o for o in options if f"action: {o} " in state), options[0])
        probs = {o: (0.9 if o == choice else 0.1 / (len(options) - 1)) for o in options}
        return NS(
            answers={
                "tool": NS(choice=choice, confidence=self.confidence, probabilities=probs),
                "risky": NS(noul=self.risk),
            },
            usage=NS(input_tokens=1),
        )


@pytest.fixture
def decider():
    return FakeDecider()


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path, monkeypatch):
    """Keep checkpoints and decision logs out of the real data dir."""
    import brain.config as bc

    cfg = {**bc.load_config(), "data_dir": str(tmp_path / "data")}
    monkeypatch.setattr(bc, "load_config", lambda: cfg)
    for mod in (
        "brain.decisionlog",
        "brain.nodes.router",
        "brain.nodes.guard",
        "brain.graph",
        "brain.privacy",
    ):
        monkeypatch.setattr(f"{mod}.load_config", lambda: cfg, raising=False)
    return cfg
