"""Guard rules. The rule table is the floor: model output can only make a decision stricter.

final = max(rule_tier, model_tier). Nothing here ever lowers a tier.
"""

from __future__ import annotations

from dataclasses import dataclass

_STRICT = {"run": 0, "log_run": 1, "approve": 2}
_BY_TIER = {"read": "run", "reversible": "log_run", "irreversible": "approve"}


@dataclass(frozen=True)
class GuardDecision:
    action: str  # run | log_run | approve | block
    reason: str
    tier: str | None


def decide(tier: str | None, risk: float | None, risk_threshold: float) -> GuardDecision:
    if tier not in _BY_TIER:
        return GuardDecision("block", "tool has no valid tier in permissions.yaml", tier)
    action, reason = _BY_TIER[tier], f"tier={tier}"
    if risk is None:
        if tier != "read":  # risk check unavailable: fail closed for anything that changes state
            return GuardDecision("approve", f"tier={tier}; risk check unavailable", tier)
    elif risk > risk_threshold and _STRICT[action] < _STRICT["approve"]:
        action, reason = "approve", f"tier={tier}; Prism risk {risk:.2f} > {risk_threshold}"
    return GuardDecision(action, reason, tier)
