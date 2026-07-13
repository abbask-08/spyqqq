"""Daily bars for the live bot.

Primary source: Alpaca market data (free IEX feed) when API keys are present.
The last row is today's *provisional* daily bar taken from the snapshot
endpoint, so a 3:45 PM run sees today's price action.

Fallback: yfinance (research-grade, unofficial) so `--paper-dry` works before
the user has created Alpaca keys.
"""
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

COLUMNS = ["open", "high", "low", "close", "volume"]


def have_alpaca_keys() -> bool:
    return bool(os.getenv("ALPACA_API_KEY")) and bool(os.getenv("ALPACA_SECRET_KEY"))


def get_daily_bars(symbol: str, lookback_days: int = 400) -> pd.DataFrame:
    """OHLCV frame indexed by naive ET dates, oldest first, today last."""
    if have_alpaca_keys():
        return _alpaca_bars(symbol, lookback_days)
    return _yfinance_bars(symbol, lookback_days)


def _normalize_index_to_et_dates(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    return idx.normalize()


def _alpaca_bars(symbol: str, lookback_days: int) -> pd.DataFrame:
    from alpaca.data.enums import DataFeed
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest
    from alpaca.data.timeframe import TimeFrame

    client = StockHistoricalDataClient(
        os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"]
    )
    start = datetime.now(timezone.utc) - timedelta(days=int(lookback_days * 1.6))
    req = StockBarsRequest(
        symbol_or_symbols=symbol, timeframe=TimeFrame.Day, start=start, feed=DataFeed.IEX
    )
    raw = client.get_stock_bars(req).df
    if isinstance(raw.index, pd.MultiIndex):
        raw = raw.xs(symbol, level="symbol")
    df = raw[COLUMNS].copy()
    df.index = _normalize_index_to_et_dates(pd.DatetimeIndex(df.index))
    df.index.name = "date"

    # Overlay today's in-progress daily bar so intraday runs see current prices.
    snap = client.get_stock_snapshot(
        StockSnapshotRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
    )[symbol]
    daily = snap.daily_bar
    if daily is not None:
        d = pd.Timestamp(daily.timestamp)
        d = _normalize_index_to_et_dates(pd.DatetimeIndex([d]))[0]
        df.loc[d, COLUMNS] = [daily.open, daily.high, daily.low, daily.close, daily.volume]

    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.tail(lookback_days)


def _yfinance_bars(symbol: str, lookback_days: int) -> pd.DataFrame:
    import yfinance as yf

    start = (datetime.now(timezone.utc) - timedelta(days=int(lookback_days * 1.6))).date()
    df = yf.download(
        symbol,
        start=str(start),
        interval="1d",
        auto_adjust=True,
        progress=False,
    )
    if df is None or df.empty:
        raise RuntimeError(f"yfinance returned no data for {symbol}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[COLUMNS]
    df.index = _normalize_index_to_et_dates(pd.DatetimeIndex(df.index))
    df.index.name = "date"
    return df.tail(lookback_days)
