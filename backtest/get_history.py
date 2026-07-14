"""Download split/dividend-adjusted daily history into data/ for backtesting.

yfinance is fine for one-off research pulls like this; the live bot uses
Alpaca's official API instead.
"""
import sys
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.config import load_config, repo_path  # noqa: E402

# Start early enough that the 200-day SMA is warm before the 2000-01-03
# backtest start. QQQ's inception is 1999-03-10, so its signals begin ~2000.
START = "1998-01-01"


def fetch(symbol: str) -> pd.DataFrame:
    df = yf.download(symbol, start=START, interval="1d", auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise SystemExit(f"yfinance returned no data for {symbol}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    df.index = pd.DatetimeIndex(df.index).normalize()
    df.index.name = "date"
    # If run intraday, today's bar is still forming — a partial bar in the
    # backtest dataset would poison the final day's signals. Keep it only
    # once the session is over (past ~16:15 ET).
    now_et = datetime.now(ZoneInfo("America/New_York"))
    if now_et.time() < time(16, 15):
        df = df[df.index < pd.Timestamp(now_et.date())]
    return df


def main() -> None:
    cfg = load_config()
    out_dir = repo_path(cfg["paths"]["history_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    for symbol in cfg["symbols"]:
        df = fetch(symbol)
        path = out_dir / f"{symbol}.csv"
        df.to_csv(path)
        print(f"{symbol}: {len(df)} rows, {df.index[0].date()} to {df.index[-1].date()} -> {path}")


if __name__ == "__main__":
    main()
