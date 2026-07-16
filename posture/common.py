"""Shared helpers for the posture generator and its eval harness.

expected_ceiling() is a deterministic re-encoding of the mapping guidance in
posture_prompt.md. It exists so make_posture.py can check Claude's stated
posture against the actual skill numbers instead of trusting the LLM's own
arithmetic — the same "LLM proposes, deterministic code validates against
real data" split used to keep an LLM from freely writing trade parameters.
Claude may always be *more* conservative than this ceiling (that's a
legitimate judgment call); it may never be less conservative.
"""
import json

VALID_POSTURES = ("RISK_OFF", "NEUTRAL", "RISK_ON")
RISK_RANK = {p: i for i, p in enumerate(VALID_POSTURES)}
POSTURE_CAPS = {"RISK_ON": 0.9, "NEUTRAL": 0.5, "RISK_OFF": 0.0}


def extract_json(text: str) -> dict | None:
    """Find the last valid JSON object in the reply that has a posture key."""
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for i in reversed(starts):
        depth = 0
        for j in range(i, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[i : j + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict) and "posture" in obj:
                        return obj
                    break
    return None


def risk_rank(posture: str) -> int:
    return RISK_RANK[posture]


def _degrade_one_notch(posture: str) -> str:
    return VALID_POSTURES[max(0, risk_rank(posture) - 1)]


def expected_ceiling(breadth_score: float | None, distribution_risk: str | None) -> str:
    """The most aggressive posture the documented mapping rules justify.

    breadth_score: composite.composite_score from market-breadth-analyzer, or
        None if that skill produced no usable artifact this run.
    distribution_risk: market_distribution_state.overall_risk_level from
        ibd-distribution-day-monitor (already reflects a SPY-only result when
        QQQ 402s — that degradation, or lack of it, is baked into this
        string), or None if the skill produced no usable artifact this run.
    """
    if breadth_score is None and distribution_risk is None:
        return "RISK_OFF"  # both skills failed
    if distribution_risk in ("HIGH", "SEVERE"):
        return "RISK_OFF"  # distribution risk overrides breadth regardless
    if distribution_risk is None:
        # Distribution skill yielded nothing usable at all (not the known
        # QQQ-only limitation, which still produces a usable SPY result) —
        # degrade one notch from what breadth alone would imply.
        if breadth_score is not None and breadth_score < 40:
            base = "RISK_OFF"
        else:
            base = "NEUTRAL"  # never RISK_ON without a distribution reading
        return _degrade_one_notch(base)
    if breadth_score is None:
        # Breadth skill yielded nothing usable; degrade one notch from what
        # distribution alone would imply.
        base = "RISK_ON" if distribution_risk == "NORMAL" else "NEUTRAL"
        return _degrade_one_notch(base)
    if breadth_score < 40:
        return "RISK_OFF"
    if breadth_score >= 60 and distribution_risk == "NORMAL":
        return "RISK_ON"
    return "NEUTRAL"
