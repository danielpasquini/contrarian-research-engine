from datetime import UTC, date, datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo

ET: tzinfo = ZoneInfo("America/New_York")
MARKET_OPEN_ET = time(9, 30, 0)
MARKET_CLOSE_ET = time(16, 0, 0)

# Fixed/observed NYSE Holidays for 2024-2027 to ensure deterministic offline PIT gating
NYSE_HOLIDAYS: set[date] = {
    # 2024
    date(2024, 1, 1),
    date(2024, 1, 15),
    date(2024, 2, 19),
    date(2024, 3, 29),
    date(2024, 5, 27),
    date(2024, 6, 19),
    date(2024, 7, 4),
    date(2024, 9, 2),
    date(2024, 11, 28),
    date(2024, 12, 25),
    # 2025
    date(2025, 1, 1),
    date(2025, 1, 9),
    date(2025, 1, 20),
    date(2025, 2, 17),
    date(2025, 4, 18),
    date(2025, 5, 26),
    date(2025, 6, 19),
    date(2025, 7, 4),
    date(2025, 9, 1),
    date(2025, 11, 27),
    date(2025, 12, 25),
    # 2026
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
    # 2027
    date(2027, 1, 1),
    date(2027, 1, 18),
    date(2027, 2, 15),
    date(2027, 3, 26),
    date(2027, 5, 31),
    date(2027, 6, 18),
    date(2027, 7, 5),
    date(2027, 9, 6),
    date(2027, 11, 25),
    date(2027, 12, 24),
}


def ensure_utc(dt: datetime) -> datetime:
    """Validate that a datetime is timezone-aware and convert it to UTC."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError(f"Naive datetime '{dt}' is prohibited; timezone-aware UTC required.")
    return dt.astimezone(UTC)


def is_nyse_trading_day(d: date) -> bool:
    """Return True if date `d` is a weekday and not an observed NYSE holiday."""
    return d.weekday() < 5 and d not in NYSE_HOLIDAYS


def next_nyse_trading_day(d: date) -> date:
    """Return the strictly next NYSE trading session after date `d`."""
    candidate = d + timedelta(days=1)
    while not is_nyse_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate


def compute_available_at(published_at: datetime) -> datetime:
    """
    Compute the realistic point-in-time tradable availability timestamp (in UTC):
    - If published during regular NYSE hours [09:30:00 ET, 16:00:00 ET) on a trading day:
      available immediately at `published_at`.
    - If published pre-market (< 09:30:00 ET) on a trading day:
      available at 09:30:00 ET on the same trading day.
    - If published at or after 16:00:00 ET (after-hours) or on a weekend/NYSE holiday:
      available at 09:30:00 ET on the next valid NYSE trading session.
    """
    pub_utc = ensure_utc(published_at)
    pub_et = pub_utc.astimezone(ET)
    pub_date = pub_et.date()
    pub_time = pub_et.timetz().replace(tzinfo=None)

    if is_nyse_trading_day(pub_date):
        if pub_time < MARKET_OPEN_ET:
            open_et = datetime.combine(pub_date, MARKET_OPEN_ET, tzinfo=ET)
            return open_et.astimezone(UTC)
        if pub_time < MARKET_CLOSE_ET:
            return pub_utc

    next_session = next_nyse_trading_day(pub_date)
    next_open_et = datetime.combine(next_session, MARKET_OPEN_ET, tzinfo=ET)
    return next_open_et.astimezone(UTC)


def count_trading_days_between(start_date: date, end_date: date) -> int:
    """
    Count the number of NYSE trading sessions strictly after `start_date` up to and
    including `end_date`. Returns a negative count if `end_date < start_date`.
    """
    if end_date == start_date:
        return 0
    step = 1 if end_date > start_date else -1
    cur = start_date
    count = 0
    while cur != end_date:
        cur += timedelta(days=step)
        if is_nyse_trading_day(cur):
            count += step
    return count
