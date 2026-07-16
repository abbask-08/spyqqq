"""Append-only CSV journals: every action and daily equity, for postmortems."""
import csv
from datetime import datetime, timezone
from pathlib import Path

TRADE_FIELDS = [
    "timestamp", "symbol", "side", "qty", "price", "reason",
    "posture", "exposure_cap", "pnl", "dry_run",
]
EQUITY_FIELDS = ["date", "equity", "posture", "exposure_cap", "note"]
SIGNAL_FIELDS = ["date", "symbol", "close", "sma", "rsi", "atr", "in_regime", "entry_signal"]


def _append(path: Path, fields: list[str], row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def log_trade(path: Path, **kwargs) -> None:
    row = {k: "" for k in TRADE_FIELDS}
    row["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    row.update({k: v for k, v in kwargs.items() if k in TRADE_FIELDS})
    _append(path, TRADE_FIELDS, row)


def log_equity(path: Path, **kwargs) -> None:
    row = {k: "" for k in EQUITY_FIELDS}
    row.update({k: v for k, v in kwargs.items() if k in EQUITY_FIELDS})
    _append(path, EQUITY_FIELDS, row)


def log_signal(path: Path, **kwargs) -> None:
    """One row per symbol per run: the indicator snapshot behind the day's
    entry/no-signal decision. Exists so the dashboard can chart RSI's
    distance from the entry threshold over time without re-parsing bot.log.
    """
    row = {k: "" for k in SIGNAL_FIELDS}
    row.update({k: v for k, v in kwargs.items() if k in SIGNAL_FIELDS})
    _append(path, SIGNAL_FIELDS, row)
