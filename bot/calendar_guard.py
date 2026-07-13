"""NYSE session guard.

Task Scheduler fires on weekdays in local time; it knows nothing about NYSE
holidays, half-days, or DST edge weeks. This module is the source of truth:
the bot only acts when the market is actually open.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

ET = ZoneInfo("America/New_York")
_cal = None


def _calendar():
    global _cal
    if _cal is None:
        _cal = xcals.get_calendar("XNYS")
    return _cal


def now_et() -> datetime:
    return datetime.now(ET)


def is_trading_day(d) -> bool:
    return _calendar().is_session(pd.Timestamp(d).normalize())


def trading_days_between(start, end) -> int:
    """Whole sessions strictly after `start` through `end` — i.e. days held."""
    cal = _calendar()
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    if end <= start:
        return 0
    sessions = cal.sessions_in_range(start, end)
    return max(0, len(sessions) - 1)


def market_guard(now: datetime | None = None) -> tuple[bool, float, str]:
    """Return (open_now, minutes_to_close, reason)."""
    now = now or now_et()
    today = pd.Timestamp(now.date())
    cal = _calendar()
    if not cal.is_session(today):
        return False, 0.0, f"{today.date()} is not an NYSE session (weekend/holiday)"
    open_ts = cal.session_open(today).tz_convert(ET)
    close_ts = cal.session_close(today).tz_convert(ET)
    now_ts = pd.Timestamp(now)
    if now_ts < open_ts:
        return False, 0.0, f"market opens at {open_ts.strftime('%H:%M')} ET"
    if now_ts >= close_ts:
        return False, 0.0, f"market closed at {close_ts.strftime('%H:%M')} ET"
    minutes_left = (close_ts - now_ts).total_seconds() / 60.0
    return True, minutes_left, f"market open, {minutes_left:.0f} min to close"
