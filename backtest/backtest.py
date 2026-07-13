"""Portfolio backtest that replays bot/strategy.py over daily history.

Fills model costs the Alpaca paper simulator ignores: configurable slippage
per side plus half the bid/ask spread. Entries fill at the close (the live
bot runs minutes before the close); stops fill intraday at the stop price,
or at the open when price gaps through the stop.

Usage:
  python backtest/backtest.py            # full run + in/out-of-sample split
  python backtest/backtest.py --sweep    # parameter robustness grid
"""
import argparse
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.config import load_config, repo_path  # noqa: E402
from bot.strategy import (  # noqa: E402
    StrategyParams, compute_indicators, entry_signal, exit_signal, stop_price,
)


@dataclass
class OpenPosition:
    qty: int
    entry_price: float
    entry_date: pd.Timestamp
    stop: float
    days_held: int = 0


def load_history(cfg: dict) -> dict[str, pd.DataFrame]:
    out = {}
    for symbol in cfg["symbols"]:
        path = repo_path(cfg["paths"]["history_dir"]) / f"{symbol}.csv"
        if not path.exists():
            raise SystemExit(f"{path} missing — run: python backtest/get_history.py")
        out[symbol] = pd.read_csv(path, index_col="date", parse_dates=True)
    return out


def simulate(
    history: dict[str, pd.DataFrame],
    params: StrategyParams,
    cfg: dict,
    start: str,
    end: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (trades, equity_curve). Indicators are computed on full history
    (no warmup loss), then the simulation is restricted to [start, end]."""
    bt = cfg["backtest"]
    slip = float(bt["slippage_bps"]) / 1e4
    half_spread = float(bt["spread_cents"]) / 200.0
    weight = float(cfg["risk"]["weight_per_symbol"])

    ind = {s: compute_indicators(df, params) for s, df in history.items()}
    window = {
        s: df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end or "2100-01-01"))]
        for s, df in ind.items()
    }
    all_dates = sorted(set().union(*[set(df.index) for df in window.values()]))

    cash = float(bt["initial_cash"])
    open_pos: dict[str, OpenPosition] = {}
    trades: list[dict] = []
    equity_rows: list[dict] = []

    def buy_fill(price: float) -> float:
        return price * (1 + slip) + half_spread

    def sell_fill(price: float) -> float:
        return price * (1 - slip) - half_spread

    def close_trade(symbol: str, pos: OpenPosition, raw_price: float, d, reason: str):
        nonlocal cash
        fill = sell_fill(raw_price)
        cash += pos.qty * fill
        trades.append({
            "symbol": symbol, "entry_date": pos.entry_date, "exit_date": d,
            "entry_price": pos.entry_price, "exit_price": fill, "qty": pos.qty,
            "days_held": pos.days_held, "reason": reason,
            "pnl": (fill - pos.entry_price) * pos.qty,
            "ret": fill / pos.entry_price - 1.0,
        })
        del open_pos[symbol]

    for d in all_dates:
        # -- manage existing positions: stops intraday, then close-based exits
        for symbol in list(open_pos):
            df = window[symbol]
            if d not in df.index:
                continue
            row = df.loc[d]
            pos = open_pos[symbol]
            if d > pos.entry_date:
                pos.days_held += 1
                if row["low"] <= pos.stop:
                    # gap through the stop fills at the open, not the stop price
                    raw = min(float(row["open"]), pos.stop)
                    close_trade(symbol, pos, raw, d, "stop")
                    continue
            reason = exit_signal(row, pos.days_held, params)
            if reason:
                close_trade(symbol, pos, float(row["close"]), d, reason)

        # -- mark to market before sizing entries
        equity = cash + sum(
            pos.qty * float(window[s].loc[d, "close"])
            for s, pos in open_pos.items()
            if d in window[s].index
        )

        # -- entries at the close
        for symbol, df in window.items():
            if symbol in open_pos or d not in df.index:
                continue
            row = df.loc[d]
            if not entry_signal(row, params):
                continue
            fill = buy_fill(float(row["close"]))
            qty = int(min(equity * weight, cash) // fill)
            if qty < 1:
                continue
            cash -= qty * fill
            open_pos[symbol] = OpenPosition(
                qty=qty, entry_price=fill, entry_date=d,
                stop=stop_price(float(row["close"]), float(row["atr"]), params),
            )

        equity = cash + sum(
            pos.qty * float(window[s].loc[d, "close"])
            for s, pos in open_pos.items()
            if d in window[s].index
        )
        equity_rows.append({"date": d, "equity": equity})

    return pd.DataFrame(trades), pd.DataFrame(equity_rows).set_index("date")


def metrics(trades: pd.DataFrame, curve: pd.DataFrame, initial_cash: float) -> dict:
    if curve.empty:
        return {}
    equity = curve["equity"]
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1e-9)
    cagr = (equity.iloc[-1] / initial_cash) ** (1 / years) - 1
    max_dd = (equity / equity.cummax() - 1.0).min()
    out = {
        "final_equity": equity.iloc[-1], "CAGR": cagr, "max_drawdown": max_dd,
        "trades": len(trades),
    }
    if not trades.empty:
        wins = trades[trades["pnl"] > 0]
        losses = trades[trades["pnl"] <= 0]
        gross_win = wins["pnl"].sum()
        gross_loss = -losses["pnl"].sum()
        out.update({
            "win_rate": len(wins) / len(trades),
            "profit_factor": gross_win / gross_loss if gross_loss > 0 else float("inf"),
            "expectancy_$": trades["pnl"].mean(),
            "expectancy_%": trades["ret"].mean(),
            "avg_win_%": wins["ret"].mean() if len(wins) else 0.0,
            "avg_loss_%": losses["ret"].mean() if len(losses) else 0.0,
            "worst_trade_%": trades["ret"].min(),
        })
    return out


def buy_and_hold(history: dict, cfg: dict, start: str, end: str | None = None) -> dict:
    df = history["SPY"] if "SPY" in history else next(iter(history.values()))
    close = df.loc[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end or "2100-01-01")), "close"]
    years = max((close.index[-1] - close.index[0]).days / 365.25, 1e-9)
    return {
        "CAGR": (close.iloc[-1] / close.iloc[0]) ** (1 / years) - 1,
        "max_drawdown": (close / close.cummax() - 1.0).min(),
    }


def fmt(m: dict) -> str:
    if not m:
        return "  (no data)"
    parts = []
    for k, v in m.items():
        if isinstance(v, float):
            parts.append(f"{k}={v:.2%}" if any(t in k for t in ("CAGR", "rate", "%", "drawdown")) else f"{k}={v:,.2f}")
        else:
            parts.append(f"{k}={v}")
    return "  " + " | ".join(parts)


def report(history, params, cfg) -> None:
    bt = cfg["backtest"]
    spans = [
        ("FULL PERIOD", bt["start"], None),
        ("IN-SAMPLE", bt["start"], bt["in_sample_end"]),
        ("OUT-OF-SAMPLE", str(pd.Timestamp(bt["in_sample_end"]) + pd.Timedelta(days=1))[:10], None),
    ]
    for name, start, end in spans:
        trades, curve = simulate(history, params, cfg, start, end)
        bh = buy_and_hold(history, cfg, start, end)
        print(f"\n=== {name} ({start} to {end or 'today'}) ===")
        print(fmt(metrics(trades, curve, float(bt["initial_cash"]))))
        print(f"  buy&hold SPY: CAGR={bh['CAGR']:.2%} | max_drawdown={bh['max_drawdown']:.2%}")
        if name == "FULL PERIOD":
            repo_path("logs").mkdir(parents=True, exist_ok=True)
            curve.to_csv(repo_path("logs/backtest_equity.csv"))
            trades.to_csv(repo_path("logs/backtest_trades.csv"), index=False)
            by_reason = trades.groupby("reason")["pnl"].agg(["count", "sum", "mean"])
            print("  exits by reason:")
            for line in by_reason.to_string().splitlines():
                print(f"    {line}")


def sweep(history, base: StrategyParams, cfg) -> None:
    bt = cfg["backtest"]
    print("\n=== ROBUSTNESS SWEEP (full period; look for a plateau, not a spike) ===")
    print(f"{'rsi_buy':>8} {'sma':>5} {'trades':>7} {'win%':>7} {'PF':>6} {'CAGR':>8} {'maxDD':>8}")
    combos = 0
    for rsi_buy in (5.0, 7.5, 10.0, 12.5, 15.0):
        for sma in (150, 175, 200, 225, 250):
            combos += 1
            p = replace(base, rsi_buy_below=rsi_buy, sma_period=sma)
            trades, curve = simulate(history, p, cfg, bt["start"])
            m = metrics(trades, curve, float(bt["initial_cash"]))
            if not m or "win_rate" not in m:
                print(f"{rsi_buy:>8} {sma:>5} {'—':>7}")
                continue
            print(
                f"{rsi_buy:>8} {sma:>5} {m['trades']:>7} {m['win_rate']:>7.1%} "
                f"{m['profit_factor']:>6.2f} {m['CAGR']:>8.2%} {m['max_drawdown']:>8.2%}"
            )
    print(f"  ({combos} configurations tested - report this number; every extra config "
          f"you try inflates the best result)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep", action="store_true", help="parameter robustness grid")
    args = parser.parse_args()
    cfg = load_config()
    params = StrategyParams.from_config(cfg["strategy"])
    history = load_history(cfg)
    report(history, params, cfg)
    if args.sweep:
        sweep(history, params, cfg)


if __name__ == "__main__":
    main()
