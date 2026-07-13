"""SPY/QQQ daily swing bot — Job B entrypoint (run near the close, ~3:45 PM ET).

Order of operations each run:
  1. NYSE calendar guard (holidays, half-days, market actually open)
  2. Load posture (Claude's daily risk gate; NEUTRAL fail-safe)
  3. Reconcile broker positions with local state
  4. Exits first (regime break / RSI / time), then entries clamped by
     posture cap and kill switches
  5. Journal everything

Flags:
  --paper-dry   compute and log intended orders, submit nothing
                (works without Alpaca keys, via yfinance data)
  --force       skip the market-hours guard (guard still logs a warning)
  --resume      clear a kill-switch halt
"""
import argparse
import logging
import sys

from dotenv import load_dotenv

from bot import calendar_guard, data, journal, risk
from bot.broker import DuplicateOrder  # no alpaca import until PaperBroker()
from bot.config import load_config, repo_path
from bot.posture import load_posture
from bot.strategy import (
    StrategyParams, compute_indicators, entry_signal, exit_signal, stop_price,
)

log = logging.getLogger("spyqqq")


class DryBroker:
    """Stands in for PaperBroker in --paper-dry mode (no keys required)."""

    def __init__(self, assumed_equity: float):
        self._equity = assumed_equity

    def equity(self) -> float:
        return self._equity

    def position(self, symbol: str) -> tuple[int, float]:
        return 0, 0.0

    def submit_entry(self, symbol, qty, stop):
        log.info("[dry] would BUY %s x%d with stop %.2f", symbol, qty, stop)

    def exit_position(self, symbol):
        log.info("[dry] would SELL %s (close position, cancel stop)", symbol)


def reconcile(broker, state: dict, symbols: list[str], trades_csv, dry: bool) -> None:
    """Make local state agree with the broker (the broker is the truth)."""
    if dry:
        return
    for symbol in symbols:
        qty, avg_price = broker.position(symbol)
        tracked = state["positions"].get(symbol)
        if qty > 0 and tracked is None:
            log.warning("%s: broker holds %d shares unknown to state — adopting", symbol, qty)
            state["positions"][symbol] = {
                "qty": qty,
                "entry_price": avg_price,
                "entry_date": calendar_guard.now_et().date().isoformat(),
                "stop": None,
            }
        elif qty == 0 and tracked is not None:
            # Stop order filled (or manual close) since the last run.
            exit_px = tracked.get("stop") or tracked["entry_price"]
            pnl = (exit_px - tracked["entry_price"]) * tracked["qty"]
            log.warning("%s: position gone from broker (stop filled?) pnl~%.2f", symbol, pnl)
            risk.record_closed_trade(state, pnl)
            journal.log_trade(
                trades_csv, symbol=symbol, side="SELL", qty=tracked["qty"],
                price=exit_px, reason="stop_filled_or_manual", pnl=round(pnl, 2),
                dry_run=False,
            )
            del state["positions"][symbol]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-dry", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout
    )
    load_dotenv(repo_path(".env"))
    cfg = load_config()
    params = StrategyParams.from_config(cfg["strategy"])
    trades_csv = repo_path(cfg["paths"]["trades_csv"])
    state_path = repo_path(cfg["paths"]["state_file"])
    today = calendar_guard.now_et().date().isoformat()

    open_now, minutes_left, guard_note = calendar_guard.market_guard()
    log.info("calendar: %s", guard_note)
    if not open_now and not (args.force or args.paper_dry):
        log.info("exiting: outside market hours (use --force to override)")
        return 0
    if open_now and minutes_left > 90:
        log.warning("running %d min before the close - signals are provisional", minutes_left)

    live = not args.paper_dry
    if live and not data.have_alpaca_keys():
        log.error(
            "No Alpaca keys in .env. Sign up free at https://alpaca.markets, switch the "
            "dashboard to Paper Trading, create keys, then fill in .env (see .env.example). "
            "Until then, use --paper-dry."
        )
        return 0

    state = risk.load_state(state_path)
    if args.resume and state["halted"]:
        log.info("--resume: clearing halt (%s)", state["halt_reason"])
        state["halted"] = False
        state["halt_reason"] = ""
        state["consecutive_losses"] = 0

    if live:
        from bot.broker import PaperBroker

        broker = PaperBroker()
    else:
        broker = DryBroker(assumed_equity=float(cfg["backtest"]["initial_cash"]))

    reconcile(broker, state, cfg["symbols"], trades_csv, dry=args.paper_dry)
    equity = broker.equity()
    posture_name, cap, posture_note = load_posture(cfg)
    log.info("equity %.2f | posture %s", equity, posture_note)

    halted, halt_reason = risk.check_kill_switches(state, equity, cfg)
    if halted:
        log.warning("KILL SWITCH ACTIVE: %s — exits still processed, no new entries. "
                    "Run with --resume after reviewing.", halt_reason)

    for symbol in cfg["symbols"]:
        try:
            bars = data.get_daily_bars(symbol, lookback_days=max(400, params.sma_period + 60))
        except Exception as e:  # one symbol failing must not strand the other
            log.error("%s: data fetch failed: %s", symbol, e)
            continue
        ind = compute_indicators(bars, params)
        row = ind.iloc[-1]
        log.info(
            "%s close=%.2f sma=%.2f rsi=%.1f atr=%.2f",
            symbol, row["close"], row["sma"], row["rsi"], row["atr"],
        )

        tracked = state["positions"].get(symbol)
        if tracked:
            days_held = calendar_guard.trading_days_between(tracked["entry_date"], row.name)
            reason = exit_signal(row, days_held, params)
            if reason:
                pnl = (row["close"] - tracked["entry_price"]) * tracked["qty"]
                log.info("%s: EXIT (%s) after %d days, pnl~%.2f", symbol, reason, days_held, pnl)
                try:
                    broker.exit_position(symbol)
                except Exception as e:
                    log.error("%s: exit failed, will retry next run: %s", symbol, e)
                    continue
                if live:
                    risk.record_closed_trade(state, pnl)
                    del state["positions"][symbol]
                journal.log_trade(
                    trades_csv, symbol=symbol, side="SELL", qty=tracked["qty"],
                    price=round(float(row["close"]), 2), reason=reason,
                    posture=posture_name, exposure_cap=cap, pnl=round(pnl, 2),
                    dry_run=args.paper_dry,
                )
            else:
                log.info("%s: holding (%d days)", symbol, days_held)
            continue

        if halted or cap <= 0:
            if entry_signal(row, params):
                log.info("%s: entry signal suppressed (%s)", symbol,
                         halt_reason if halted else "posture RISK_OFF")
            continue
        if entry_signal(row, params):
            qty = risk.target_qty(equity, float(row["close"]), cfg, cap)
            if qty < 1:
                log.info("%s: entry signal but sized to 0 shares under cap %.0f%%", symbol, cap * 100)
                continue
            stop = stop_price(float(row["close"]), float(row["atr"]), params)
            log.info("%s: ENTER %d shares ~%.2f, stop %.2f", symbol, qty, row["close"], stop)
            try:
                broker.submit_entry(symbol, qty, stop)
            except DuplicateOrder:
                log.info("%s: entry already submitted today (idempotency guard)", symbol)
                continue
            except Exception as e:
                log.error("%s: entry failed: %s", symbol, e)
                continue
            if live:
                state["positions"][symbol] = {
                    "qty": qty,
                    "entry_price": float(row["close"]),
                    "entry_date": str(row.name.date()),
                    "stop": stop,
                }
            journal.log_trade(
                trades_csv, symbol=symbol, side="BUY", qty=qty,
                price=round(float(row["close"]), 2), reason="rsi_pullback",
                posture=posture_name, exposure_cap=cap, dry_run=args.paper_dry,
            )
        else:
            log.info("%s: no signal", symbol)

    journal.log_equity(
        repo_path(cfg["paths"]["equity_csv"]),
        date=today, equity=round(equity, 2), posture=posture_name,
        exposure_cap=cap, note="dry" if args.paper_dry else "",
    )
    if live:
        state["last_run_date"] = today
        risk.save_state(state_path, state)
    log.info("run complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
