"""Run a headless Claude Code session (billed to the Pro subscription, not API
credits) and distill its reply into posture/posture.json.

Deliberate hardening:
- ANTHROPIC_API_KEY is stripped from the environment: in -p mode an API key
  silently outranks subscription auth and would bill credits the user
  doesn't have.
- No --bare flag: bare mode skips subscription OAuth entirely.
- On any failure this script exits non-zero WITHOUT touching posture.json;
  the bot then falls back via its staleness check. Claude being down can
  never break the trading run.
- Grounding check: Claude's stated posture is verified against the actual
  skill-output artifacts from this same run (see common.expected_ceiling).
  A posture riskier than the numbers support is rejected outright, same as
  any other failure — never written, bot falls back via staleness.
"""
import glob
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    POSTURE_CAPS, VALID_POSTURES, expected_ceiling, extract_json, risk_rank,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PROMPT_FILE = HERE / "posture_prompt.md"
OUT_FILE = HERE / "posture.json"
MAX_TURNS = "30"
TIMEOUT_S = 1200
ARTIFACT_FRESHNESS = timedelta(hours=2)  # must be written during this run, not a stale leftover


def _freshest(pattern: str) -> Path | None:
    candidates = [Path(p) for p in glob.glob(pattern)]
    if not candidates:
        return None
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    age = datetime.now() - datetime.fromtimestamp(newest.stat().st_mtime)
    return newest if age <= ARTIFACT_FRESHNESS else None


def ground_truth() -> tuple[float | None, str | None, list[str]]:
    """Pull breadth composite + distribution risk from this run's own skill
    artifacts. Returns (breadth_score, distribution_risk, notes)."""
    notes = []
    breadth_score = None
    breadth_file = _freshest(str(REPO / "market_breadth_*.json"))
    if breadth_file is None:
        notes.append("no fresh market-breadth-analyzer artifact found")
    else:
        try:
            breadth_score = float(
                json.loads(breadth_file.read_text(encoding="utf-8"))["composite"]["composite_score"]
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
            notes.append(f"unreadable breadth artifact {breadth_file.name}: {e}")

    distribution_risk = None
    dist_file = _freshest(str(REPO / "reports" / "ibd_distribution_day_monitor_*.json"))
    if dist_file is None:
        notes.append("no fresh ibd-distribution-day-monitor artifact found")
    else:
        try:
            distribution_risk = json.loads(dist_file.read_text(encoding="utf-8"))[
                "market_distribution_state"
            ]["overall_risk_level"]
        except (KeyError, TypeError, json.JSONDecodeError) as e:
            notes.append(f"unreadable distribution artifact {dist_file.name}: {e}")

    return breadth_score, distribution_risk, notes


def main() -> int:
    # Task Scheduler redirects output through a cp1252 console; without this,
    # a unicode character in an error path crashes the error handler itself.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    claude = shutil.which("claude")
    if not claude:
        print("ERROR: claude CLI not found on PATH", file=sys.stderr)
        return 1
    prompt = PROMPT_FILE.read_text(encoding="utf-8")

    import os

    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)

    cmd = [
        claude, "-p", prompt,
        "--output-format", "json",
        "--max-turns", MAX_TURNS,
        "--allowedTools", "Skill", "Bash", "Read", "Glob", "Grep",
        "WebFetch", "WebSearch", "ToolSearch",
    ]
    print(f"{datetime.now().isoformat(timespec='seconds')} running headless posture analysis...")
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, env=env, timeout=TIMEOUT_S, encoding="utf-8"
        )
    except subprocess.TimeoutExpired:
        print(f"ERROR: claude run exceeded {TIMEOUT_S}s", file=sys.stderr)
        return 1
    if proc.returncode != 0:
        print(f"ERROR: claude exited {proc.returncode}: {proc.stderr[:2000]}", file=sys.stderr)
        return 1

    try:
        envelope = json.loads(proc.stdout)
        result_text = envelope.get("result", "")
    except json.JSONDecodeError:
        result_text = proc.stdout  # older CLIs / plain text fallback

    posture = extract_json(result_text)
    if posture is None:
        print(f"ERROR: no posture JSON found in reply:\n{result_text[-2000:]}", file=sys.stderr)
        return 1
    if posture.get("posture") not in VALID_POSTURES:
        print(f"ERROR: invalid posture {posture.get('posture')!r}", file=sys.stderr)
        return 1
    try:
        exposure = float(posture.get("max_exposure"))
    except (TypeError, ValueError):
        print(f"ERROR: invalid max_exposure {posture.get('max_exposure')!r}", file=sys.stderr)
        return 1

    breadth_score, distribution_risk, notes = ground_truth()
    for n in notes:
        print(f"grounding: {n}")
    ceiling = expected_ceiling(breadth_score, distribution_risk)
    claimed = posture["posture"]
    if risk_rank(claimed) > risk_rank(ceiling):
        print(
            f"ERROR: grounding check failed — Claude claimed {claimed} but the actual skill "
            f"artifacts (breadth={breadth_score}, distribution_risk={distribution_risk!r}) "
            f"only justify up to {ceiling}. Refusing to write a posture riskier than the data "
            f"supports.", file=sys.stderr,
        )
        return 1
    exposure = min(exposure, POSTURE_CAPS[claimed])

    doc = {
        "posture": claimed,
        "max_exposure": min(0.9, max(0.0, exposure)),
        "reasons": [str(r) for r in posture.get("reasons", [])][:4],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "grounding": {
            "breadth_score": breadth_score,
            "distribution_risk": distribution_risk,
            "ceiling": ceiling,
        },
    }
    OUT_FILE.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"wrote {OUT_FILE.name}: {doc['posture']} cap={doc['max_exposure']} (ceiling {ceiling})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
