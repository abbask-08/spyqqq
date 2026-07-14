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
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPT_FILE = HERE / "posture_prompt.md"
OUT_FILE = HERE / "posture.json"
VALID_POSTURES = {"RISK_ON", "NEUTRAL", "RISK_OFF"}
MAX_TURNS = "30"
TIMEOUT_S = 1200


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

    doc = {
        "posture": posture["posture"],
        "max_exposure": min(0.9, max(0.0, exposure)),
        "reasons": [str(r) for r in posture.get("reasons", [])][:4],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    OUT_FILE.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"wrote {OUT_FILE.name}: {doc['posture']} cap={doc['max_exposure']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
