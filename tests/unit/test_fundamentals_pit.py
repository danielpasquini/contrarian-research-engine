from datetime import UTC, date, datetime

from src.fundamentals.earnings_calendar import evaluate_earnings_blackout
from src.fundamentals.xbrl_parser import RawXBRLFiling, select_point_in_time_fundamentals


def test_sec_acceptance_timestamp_prevents_period_end_lookahead() -> None:
    """
    AC-04.1: Querying fundamentals as of 2025-10-15 for a Q3 period ending 2025-09-30
    that was filed (accepted by SEC EDGAR) on 2025-11-02 must return Q2 data, never Q3 data.
    """
    filings = [
        RawXBRLFiling(
            ticker="MSFT",
            cik="0000789019",
            accession_number="0000789019-25-000050",
            form_type="10-Q",
            period_of_report=date(2025, 6, 30),  # Q2
            acceptance_datetime=datetime(2025, 7, 30, 16, 15, 0, tzinfo=UTC),
            collected_at=datetime(2025, 7, 30, 16, 20, 0, tzinfo=UTC),
            revenue_ttm=240_000_000_000.0,
            operating_income_ttm=105_000_000_000.0,
            operating_cash_flow_ttm=115_000_000_000.0,
            total_debt=50_000_000_000.0,
            cash_and_equivalents=75_000_000_000.0,
        ),
        RawXBRLFiling(
            ticker="MSFT",
            cik="0000789019",
            accession_number="0000789019-25-000089",
            form_type="10-Q",
            period_of_report=date(2025, 9, 30),  # Q3 period ended Sept 30, but filed Nov 2!
            acceptance_datetime=datetime(2025, 11, 2, 20, 5, 0, tzinfo=UTC),
            collected_at=datetime(2025, 11, 2, 20, 10, 0, tzinfo=UTC),
            revenue_ttm=255_000_000_000.0,
            operating_income_ttm=112_000_000_000.0,
            operating_cash_flow_ttm=122_000_000_000.0,
            total_debt=48_000_000_000.0,
            cash_and_equivalents=80_000_000_000.0,
        ),
    ]

    # Decision on 2025-10-15: Q3 period has ended, but filing is NOT yet accepted!
    decision_oct = datetime(2025, 10, 15, 14, 0, 0, tzinfo=UTC)
    snap_oct = select_point_in_time_fundamentals(filings, decision_timestamp=decision_oct)
    assert snap_oct is not None
    assert snap_oct.accession_number == "0000789019-25-000050"
    assert snap_oct.period_of_report == date(2025, 6, 30)
    assert snap_oct.revenue_ttm == 240_000_000_000.0

    # Decision on 2025-11-04 (after Nov 2 filing became tradable on Monday Nov 3 09:30 ET)
    decision_nov = datetime(2025, 11, 4, 15, 0, 0, tzinfo=UTC)
    snap_nov = select_point_in_time_fundamentals(filings, decision_timestamp=decision_nov)
    assert snap_nov is not None
    assert snap_nov.accession_number == "0000789019-25-000089"
    assert snap_nov.period_of_report == date(2025, 9, 30)
    assert snap_nov.fundamental_health_score > 0.80


def test_earnings_blackout_within_3_trading_days() -> None:
    # Monday May 4, 2026; earnings on Thursday May 7, 2026 -> 3 trading days away -> BLACKOUT True
    status_3d = evaluate_earnings_blackout(
        ticker="AAPL",
        as_of_date=date(2026, 5, 4),
        next_earnings_date=date(2026, 5, 7),
        blackout_trading_days=3,
    )
    assert status_3d.trading_days_to_earnings == 3
    assert status_3d.earnings_blackout is True

    # Monday May 4, 2026; earnings on Monday May 11, 2026 -> 5 trading days away -> BLACKOUT False
    status_5d = evaluate_earnings_blackout(
        ticker="AAPL",
        as_of_date=date(2026, 5, 4),
        next_earnings_date=date(2026, 5, 11),
        blackout_trading_days=3,
    )
    assert status_5d.trading_days_to_earnings == 5
    assert status_5d.earnings_blackout is False


def test_unknown_or_past_earnings_date_fails_closed_blackout() -> None:
    """[CRIT-01]: Unknown (None) or stale past next_earnings_date must fail closed."""
    status_none = evaluate_earnings_blackout(
        ticker="AAPL",
        as_of_date=date(2026, 5, 4),
        next_earnings_date=None,
        blackout_trading_days=3,
    )
    assert status_none.trading_days_to_earnings is None
    assert status_none.earnings_blackout is True

    status_past = evaluate_earnings_blackout(
        ticker="AAPL",
        as_of_date=date(2026, 5, 4),
        next_earnings_date=date(2026, 5, 1),
        blackout_trading_days=3,
    )
    assert status_past.trading_days_to_earnings is None
    assert status_past.earnings_blackout is True
