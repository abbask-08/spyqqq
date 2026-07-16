"""Shared readers for the accumulated bot logs -- used by both the local
HTML dashboard (build_dashboard.py) and the JSON snapshot exporter
(export_snapshot.py) that feeds the Next.js site, so the two never disagree
about what a "live equity row" or "posture history entry" means.
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.config import repo_path  # noqa: E402

POSTURE_HISTORY = repo_path("posture/posture_history.jsonl")
POSTURE_JSON = repo_path("posture/posture.json")
STATE_JSON = repo_path("logs/bot_state.json")


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_equity_curve() -> list[dict]:
    """Live rows only (dry-run rows use a fake $100k account and would blow
    out the scale), deduped to the last row per date."""
    rows = [r for r in read_csv_rows(repo_path("logs/equity_curve.csv")) if r.get("note") != "dry"]
    by_date = {}
    for r in rows:
        by_date[r["date"]] = r  # last write for a given date wins
    return [by_date[d] for d in sorted(by_date)]


def read_signals() -> dict:
    rows = read_csv_rows(repo_path("logs/signals.csv"))
    by_symbol = {}
    for r in rows:
        if r.get("rsi") in (None, ""):
            continue
        by_symbol.setdefault(r["symbol"], []).append(r)
    for sym in by_symbol:
        by_symbol[sym] = sorted(by_symbol[sym], key=lambda r: r["date"])
    return by_symbol


def read_posture_history() -> list[dict]:
    if not POSTURE_HISTORY.exists():
        return []
    out = []
    for line in POSTURE_HISTORY.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def read_trades() -> list[dict]:
    from bot.config import load_config

    return read_csv_rows(repo_path(load_config()["paths"]["trades_csv"]))


def compute_current_status(equity_rows: list[dict], current_posture: dict, state: dict) -> dict:
    """The header/stat-tile numbers, computed once so the local dashboard and
    the JSON snapshot never drift apart on the gate-date math."""
    from datetime import date, datetime, timedelta

    equity = float(equity_rows[-1]["equity"]) if equity_rows else None
    first_day = equity_rows[0]["date"] if equity_rows else None
    days_elapsed = None
    gate_date = None
    if first_day:
        start = datetime.strptime(first_day, "%Y-%m-%d").date()
        days_elapsed = (date.today() - start).days
        gate_date = (start + timedelta(days=30)).isoformat()

    return {
        "equity": equity,
        "posture": current_posture.get("posture", "unknown"),
        "max_exposure": current_posture.get("max_exposure"),
        "grounding": current_posture.get("grounding", {}),
        "positions": state.get("positions", {}),
        "halted": state.get("halted", False),
        "halt_reason": state.get("halt_reason", ""),
        "first_trading_day": first_day,
        "days_elapsed": days_elapsed,
        "real_money_gate_date": gate_date,
    }
