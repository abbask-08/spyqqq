"""Position sizing, kill switches, and persistent bot state.

State lives in logs/bot_state.json:
  peak_equity          highest equity seen (for the drawdown halt)
  halted / halt_reason set by a kill switch; cleared only by --resume
  consecutive_losses   losing closes in a row
  positions            symbol -> {qty, entry_price, entry_date, stop}
"""
import json
import math
from pathlib import Path


def default_state() -> dict:
    return {
        "peak_equity": None,
        "halted": False,
        "halt_reason": "",
        "consecutive_losses": 0,
        "positions": {},
        "last_run_date": None,
    }


def load_state(path: Path) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return default_state()
    merged = default_state()
    merged.update(state)
    return merged


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)


def check_kill_switches(state: dict, equity: float, cfg: dict) -> tuple[bool, str]:
    """Update peak equity, trip halts. Returns (halted, reason)."""
    rcfg = cfg["risk"]
    if state["peak_equity"] is None or equity > state["peak_equity"]:
        state["peak_equity"] = equity
    drawdown = 1.0 - equity / state["peak_equity"] if state["peak_equity"] else 0.0
    if drawdown > float(rcfg["max_drawdown_halt"]):
        state["halted"] = True
        state["halt_reason"] = f"drawdown {drawdown:.1%} exceeds {rcfg['max_drawdown_halt']:.0%} halt"
    if state["consecutive_losses"] >= int(rcfg["max_consecutive_losses"]):
        state["halted"] = True
        state["halt_reason"] = (
            f"{state['consecutive_losses']} consecutive losing trades "
            f"(limit {rcfg['max_consecutive_losses']})"
        )
    return state["halted"], state["halt_reason"]


def record_closed_trade(state: dict, pnl: float) -> None:
    if pnl < 0:
        state["consecutive_losses"] += 1
    else:
        state["consecutive_losses"] = 0


def target_qty(equity: float, price: float, cfg: dict, exposure_cap: float) -> int:
    """Whole shares (Alpaca bracket/OTO orders reject fractional quantities)."""
    n_symbols = len(cfg["symbols"])
    weight = min(float(cfg["risk"]["weight_per_symbol"]), exposure_cap / n_symbols)
    if weight <= 0 or price <= 0:
        return 0
    return int(math.floor(equity * weight / price))
