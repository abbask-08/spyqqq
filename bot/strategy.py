"""Pure signal logic, shared verbatim by the live bot and the backtest.

Everything here is a function of price data + parameters. No I/O, no broker,
no clock — that separation is what makes the backtest results transferable.
"""
from dataclasses import dataclass, fields

import pandas as pd


@dataclass(frozen=True)
class StrategyParams:
    sma_period: int = 200
    rsi_period: int = 2
    rsi_buy_below: float = 10.0
    rsi_exit_above: float = 65.0
    max_hold_days: int = 10
    atr_period: int = 14
    atr_stop_mult: float = 3.0

    @classmethod
    def from_config(cls, cfg: dict) -> "StrategyParams":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in cfg.items() if k in names})


def wilder_rsi(close: pd.Series, period: int) -> pd.Series:
    """Classic Wilder-smoothed RSI (the variant Connors' RSI(2) stats use)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rsi = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    # All-gain windows: avg_loss == 0 makes the ratio inf/NaN; RSI is 100 by definition.
    return rsi.mask(avg_loss == 0, 100.0)


def atr(df: pd.DataFrame, period: int) -> pd.Series:
    """Wilder-smoothed Average True Range on columns high/low/close."""
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def compute_indicators(df: pd.DataFrame, p: StrategyParams) -> pd.DataFrame:
    """Add sma / rsi / atr columns to an OHLCV frame (index: dates ascending)."""
    out = df.copy()
    out["sma"] = out["close"].rolling(p.sma_period).mean()
    out["rsi"] = wilder_rsi(out["close"], p.rsi_period)
    out["atr"] = atr(out, p.atr_period)
    return out


def entry_signal(row: pd.Series, p: StrategyParams) -> bool:
    """Buy the pullback: in an uptrend regime and RSI(2) washed out."""
    if pd.isna(row["sma"]) or pd.isna(row["rsi"]) or pd.isna(row["atr"]):
        return False
    return row["close"] > row["sma"] and row["rsi"] < p.rsi_buy_below


def exit_signal(row: pd.Series, days_held: int, p: StrategyParams) -> str | None:
    """Return the exit reason, or None to keep holding."""
    if not pd.isna(row["sma"]) and row["close"] < row["sma"]:
        return "regime_break"
    if not pd.isna(row["rsi"]) and row["rsi"] > p.rsi_exit_above:
        return "rsi_exit"
    if days_held >= p.max_hold_days:
        return "time_exit"
    return None


def stop_price(entry_price: float, entry_atr: float, p: StrategyParams) -> float:
    """Wide catastrophe stop below entry. Caps disasters, not routine noise."""
    return round(entry_price - p.atr_stop_mult * entry_atr, 2)
