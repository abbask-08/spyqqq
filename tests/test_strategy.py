"""Sanity checks for the pure strategy logic. Run: python tests/test_strategy.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.strategy import (  # noqa: E402
    StrategyParams, compute_indicators, entry_signal, exit_signal, stop_price, wilder_rsi,
)

P = StrategyParams(sma_period=50, rsi_period=2, rsi_buy_below=10.0,
                   rsi_exit_above=65.0, max_hold_days=10, atr_period=3, atr_stop_mult=3.0)


def frame(closes):
    arr = np.asarray(closes, dtype=float)  # ndarray: no index alignment surprises
    return pd.DataFrame({
        "open": arr, "high": arr * 1.01, "low": arr * 0.99,
        "close": arr, "volume": 1_000_000,
    }, index=pd.bdate_range("2024-01-01", periods=len(arr)))


def test_rsi_bounds_and_direction():
    up = wilder_rsi(pd.Series(np.linspace(100, 130, 40)), 2)
    down = wilder_rsi(pd.Series(np.linspace(130, 100, 40)), 2)
    assert up.dropna().between(0, 100).all() and down.dropna().between(0, 100).all()
    assert up.iloc[-1] == 100.0, "monotonic rally must pin RSI at 100"
    assert down.iloc[-1] < 1.0, "monotonic slide must pin RSI near 0"


def test_entry_only_on_in_regime_pullback():
    # Long rally (close > SMA50) then a two-day dip: RSI(2) crashes, regime holds.
    closes = list(np.linspace(100, 140, 60)) + [137, 133]
    ind = compute_indicators(frame(closes), P)
    last = ind.iloc[-1]
    assert last["close"] > last["sma"] and last["rsi"] < 10, \
        f"close={last['close']:.1f} sma={last['sma']:.1f} rsi={last['rsi']:.1f}"
    assert entry_signal(last, P)

    # Same dip shape inside a downtrend (below SMA): regime filter must veto.
    closes = list(np.linspace(140, 100, 60)) + [96, 92]
    ind = compute_indicators(frame(closes), P)
    assert not entry_signal(ind.iloc[-1], P)


def test_exit_reasons():
    closes = list(np.linspace(100, 140, 60))
    ind = compute_indicators(frame(closes), P)
    last = ind.iloc[-1]  # rally: RSI pinned at 100
    assert exit_signal(last, 1, P) == "rsi_exit"
    assert exit_signal(last.copy(), P.max_hold_days, P) in ("rsi_exit", "time_exit")

    mid = ind.iloc[-1].copy()
    mid["rsi"], mid["close"] = 50.0, float(mid["sma"]) - 1.0  # below SMA
    assert exit_signal(mid, 1, P) == "regime_break"

    mid["close"] = float(mid["sma"]) + 1.0
    assert exit_signal(mid, 1, P) is None
    assert exit_signal(mid, P.max_hold_days, P) == "time_exit"


def test_stop_below_entry():
    assert stop_price(100.0, 2.0, P) == 94.0
    assert stop_price(100.0, 2.0, P) < 100.0


def test_nan_warmup_never_signals():
    ind = compute_indicators(frame([100, 101, 102]), P)  # too short for SMA/ATR
    assert not entry_signal(ind.iloc[-1], P)


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted({k: v for k, v in globals().items() if k.startswith("test_")}.items()):
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {name}: {e}")
    sys.exit(1 if failures else 0)
