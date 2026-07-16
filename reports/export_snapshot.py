"""Export a consolidated JSON snapshot for the Next.js site (web/). Run
standalone:
    python reports/export_snapshot.py
Also called automatically at the end of every run_bot.py run, alongside the
local HTML dashboard (best-effort -- a snapshot failure must never affect
trading).
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.config import load_config, repo_path  # noqa: E402
from reports.data_sources import (  # noqa: E402
    POSTURE_JSON, STATE_JSON, compute_current_status, read_equity_curve,
    read_json, read_posture_history, read_signals, read_trades,
)

OUT_FILE = repo_path("web/public/data/snapshot.json")

BOOL_FIELDS = {"in_regime", "entry_signal", "dry_run"}
NUMERIC_FIELDS = {"equity", "exposure_cap", "close", "sma", "rsi", "atr", "qty", "price", "pnl"}


def _coerce(row: dict) -> dict:
    """csv.DictReader hands back strings for everything -- give the JSON
    consumer real numbers/booleans instead of making the JS side re-parse
    every field, and treat a blank ('') numeric field as null, not 0."""
    out = dict(row)
    for k, v in row.items():
        if k in BOOL_FIELDS and v != "":
            out[k] = v == "True"
        elif k in NUMERIC_FIELDS:
            out[k] = float(v) if v != "" else None
    return out


def build_snapshot() -> dict:
    cfg = load_config()
    equity_rows = [_coerce(r) for r in read_equity_curve()]
    current_posture = read_json(POSTURE_JSON)
    state = read_json(STATE_JSON)
    signals = {sym: [_coerce(r) for r in rows] for sym, rows in read_signals().items()}
    trades = [_coerce(r) for r in read_trades()]

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "current": compute_current_status(equity_rows, current_posture, state),
        "equity_curve": equity_rows,
        "signals": signals,
        "posture_history": read_posture_history(),
        "trades": trades,
        "config": {
            "symbols": cfg["symbols"],
            "rsi_buy_below": cfg["strategy"]["rsi_buy_below"],
            "rsi_exit_above": cfg["strategy"]["rsi_exit_above"],
            "sma_period": cfg["strategy"]["sma_period"],
            "max_hold_days": cfg["strategy"]["max_hold_days"],
        },
    }


def main() -> int:
    snapshot = build_snapshot()
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"wrote {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
