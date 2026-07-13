"""Read the Claude-generated risk posture with a hard fail-safe.

The bot must never depend on the Claude layer being up: a missing, stale, or
malformed posture.json degrades to the configured default (NEUTRAL), never to
an error and never to more risk.
"""
import json
from datetime import datetime, timezone

from bot.config import repo_path

VALID_POSTURES = ("RISK_ON", "NEUTRAL", "RISK_OFF")


def load_posture(cfg: dict) -> tuple[str, float, str]:
    """Return (posture, max_total_exposure, note)."""
    pcfg = cfg["posture"]
    caps = pcfg["caps"]
    default = pcfg["default"]

    def fallback(why: str) -> tuple[str, float, str]:
        return default, float(caps[default]), f"fallback to {default}: {why}"

    path = repo_path(pcfg["file"])
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback("posture.json missing")
    except (OSError, json.JSONDecodeError) as e:
        return fallback(f"unreadable posture.json ({e})")

    posture = raw.get("posture")
    if posture not in VALID_POSTURES:
        return fallback(f"invalid posture value {posture!r}")

    try:
        generated = datetime.fromisoformat(raw["generated_at"])
    except (KeyError, TypeError, ValueError):
        return fallback("missing/invalid generated_at")
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - generated).total_seconds() / 3600.0
    if age_hours > float(pcfg["stale_hours"]):
        return fallback(f"stale ({age_hours:.1f}h old)")

    cap = float(caps[posture])
    max_exposure = raw.get("max_exposure")
    if isinstance(max_exposure, (int, float)):
        # Claude may only *reduce* risk below the configured cap, never raise it.
        cap = min(cap, max(0.0, float(max_exposure)))
    return posture, cap, f"{posture} (cap {cap:.0%}, {age_hours:.1f}h old)"
