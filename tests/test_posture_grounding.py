"""Sanity checks for the posture grounding ceiling. Run: python tests/test_posture_grounding.py

No Claude calls here — this only exercises the deterministic re-encoding of
the mapping guidance in posture_prompt.md. See posture/eval/run_eval.py for
the live-Claude benchmark that checks the LLM actually follows those rules.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "posture"))
from common import expected_ceiling, risk_rank  # noqa: E402


def test_healthy_breadth_and_normal_distribution_allows_risk_on():
    assert expected_ceiling(75.0, "NORMAL") == "RISK_ON"
    assert expected_ceiling(60.0, "NORMAL") == "RISK_ON"  # boundary: >= 60


def test_breadth_just_under_60_caps_at_neutral():
    assert expected_ceiling(59.0, "NORMAL") == "NEUTRAL"


def test_breadth_under_40_forces_risk_off_regardless_of_distribution():
    assert expected_ceiling(35.0, "NORMAL") == "RISK_OFF"
    assert expected_ceiling(39.9, "NORMAL") == "RISK_OFF"
    assert expected_ceiling(40.0, "NORMAL") == "NEUTRAL"  # boundary: not < 40


def test_high_or_severe_distribution_overrides_strong_breadth():
    assert expected_ceiling(90.0, "HIGH") == "RISK_OFF"
    assert expected_ceiling(90.0, "SEVERE") == "RISK_OFF"


def test_caution_distribution_caps_at_neutral_even_with_healthy_breadth():
    assert expected_ceiling(70.0, "CAUTION") == "NEUTRAL"


def test_qqq_only_limitation_does_not_force_extra_degradation():
    # overall_risk_level already reflects a SPY-only computation when QQQ
    # 402s — the ceiling function has no separate knowledge of that and
    # shouldn't need any: a clean SPY-only NORMAL reading still allows RISK_ON.
    assert expected_ceiling(65.0, "NORMAL") == "RISK_ON"


def test_both_skills_failed_forces_risk_off():
    assert expected_ceiling(None, None) == "RISK_OFF"


def test_distribution_skill_failed_degrades_one_notch_from_breadth_only():
    # RISK_ON requires *confirmed* NORMAL distribution; with no distribution
    # reading at all that condition can never be satisfied, so even healthy
    # breadth (75) only reaches a NEUTRAL base — which then degrades one
    # notch further (total data loss, not just the known QQQ leg) to RISK_OFF.
    assert expected_ceiling(75.0, None) == "RISK_OFF"
    assert expected_ceiling(30.0, None) == "RISK_OFF"  # already RISK_OFF: can't degrade further


def test_breadth_skill_failed_degrades_one_notch_from_distribution_only():
    assert expected_ceiling(None, "NORMAL") == "NEUTRAL"
    assert expected_ceiling(None, "CAUTION") == "RISK_OFF"


def test_risk_rank_orders_postures_from_off_to_on():
    assert risk_rank("RISK_OFF") < risk_rank("NEUTRAL") < risk_rank("RISK_ON")


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted({k: v for k, v in globals().items() if k.startswith("test_")}.items()):
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {name}: {e}")
    sys.exit(1 if failures else 0)
