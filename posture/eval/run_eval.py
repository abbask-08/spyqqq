"""Live-Claude regression benchmark for the posture prompt. Run:
    python posture/eval/run_eval.py

Unlike tests/test_posture_grounding.py (pure logic, instant, free), this
actually calls `claude -p` once per fixture in fixtures.json, the same way
make_posture.py does in production, but with the skill-call steps replaced
by pre-computed synthetic numbers instead of live market data. It exists to
catch prompt drift and outright hallucination in the LLM's semantic
parsing of the mapping guidance -- the same thing the paper's 200-instruction
OQL benchmark measures, scaled to this project's one narrow decision.

Costs Pro-subscription turns (one short claude -p call per fixture, no tool
use). Run on demand after editing posture_prompt.md, not on a schedule.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import expected_ceiling, extract_json  # noqa: E402

HERE = Path(__file__).resolve().parent
PROMPT_FILE = HERE.parent / "posture_prompt.md"
FIXTURES_FILE = HERE / "fixtures.json"
MAX_TURNS = "5"
TIMEOUT_S = 180


def load_fixtures() -> list[dict]:
    fixtures = json.loads(FIXTURES_FILE.read_text(encoding="utf-8"))
    for f in fixtures:
        ceiling = expected_ceiling(f["breadth_score"], f["distribution_risk"])
        assert f["expected_posture"] == ceiling, (
            f"fixture {f['name']!r} expects {f['expected_posture']} but "
            f"common.expected_ceiling computes {ceiling} for the same inputs "
            f"-- fixtures.json and common.py have drifted apart"
        )
    return fixtures


def build_prompt(base_prompt: str, fixture: dict) -> str:
    if fixture["breadth_score"] is None:
        breadth_line = "- market-breadth-analyzer result: FAILED -- produced no usable data at all"
    else:
        breadth_line = (
            f'- market-breadth-analyzer result: composite_score={fixture["breadth_score"]}, '
            f'zone="{fixture["breadth_zone"]}"'
        )

    if fixture["distribution_risk"] is None:
        dist_line = "- ibd-distribution-day-monitor result: FAILED -- produced no usable data at all"
    else:
        dist_line = f'- ibd-distribution-day-monitor result: overall_risk_level="{fixture["distribution_risk"]}"'
    if fixture.get("qqq_note"):
        dist_line += f" {fixture['qqq_note']}"

    override = f"""You are being invoked by this repository's own offline regression test for
the prompt below (posture/eval/run_eval.py, run manually by the repo owner
after editing posture_prompt.md). This is a unit test of your instruction-
following on the mapping-guidance logic only -- it is not a live trading
day, no real skills were run, and your answer here will only be diffed
against an expected value in the test harness. It is never written to
posture.json and never reaches the trading bot or any brokerage account.

Because this is an offline test of the mapping logic specifically, you have
no tools available and must not attempt to invoke market-breadth-analyzer or
ibd-distribution-day-monitor -- skip steps 1 and 2 of the prompt below
entirely. Use these test-harness-fabricated numbers as this fixture's inputs
and apply the mapping guidance exactly as written to them:

{breadth_line}
{dist_line}

Output the final JSON object per the output format below, same as a real run.

---

"""
    return override + base_prompt


def run_fixture(claude: str, base_prompt: str, fixture: dict) -> dict:
    import os

    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    prompt = build_prompt(base_prompt, fixture)
    cmd = [claude, "-p", prompt, "--output-format", "json", "--max-turns", MAX_TURNS]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, env=env, timeout=TIMEOUT_S, encoding="utf-8"
        )
    except subprocess.TimeoutExpired:
        return {"error": f"timed out after {TIMEOUT_S}s"}
    if proc.returncode != 0:
        return {"error": f"claude exited {proc.returncode}: {proc.stderr[:500]}"}
    try:
        result_text = json.loads(proc.stdout).get("result", "")
    except json.JSONDecodeError:
        result_text = proc.stdout
    posture = extract_json(result_text)
    if posture is None:
        return {"error": f"no posture JSON in reply: {result_text[-500:]}"}
    return {"posture": posture}


def main() -> int:
    claude = shutil.which("claude")
    if not claude:
        print("ERROR: claude CLI not found on PATH", file=sys.stderr)
        return 1
    base_prompt = PROMPT_FILE.read_text(encoding="utf-8")
    fixtures = load_fixtures()

    failures = 0
    for f in fixtures:
        result = run_fixture(claude, base_prompt, f)
        if "error" in result:
            print(f"ERROR {f['name']}: {result['error']}")
            failures += 1
            continue
        actual = result["posture"].get("posture")
        if actual == f["expected_posture"]:
            print(f"PASS  {f['name']}: got {actual}")
        else:
            print(f"FAIL  {f['name']}: expected {f['expected_posture']}, got {actual} "
                  f"(reasons: {result['posture'].get('reasons')})")
            failures += 1

    print(f"\n{len(fixtures) - failures}/{len(fixtures)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
