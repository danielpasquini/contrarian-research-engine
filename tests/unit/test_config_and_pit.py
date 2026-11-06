from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from src.config import EngineSettings
from src.normalization.calendar import (
    ET,
    compute_available_at,
    count_trading_days_between,
    is_nyse_trading_day,
)
from src.normalization.news_dedup import RawNewsArticle, deduplicate_news_articles
from src.normalization.pit_models import PointInTimeRecord


def test_engine_settings_defaults_and_live_mode_prohibition() -> None:
    settings = EngineSettings()
    assert settings.execution_mode == "research"
    assert settings.allow_averaging_down is False
    assert settings.require_bracket_order is True
    assert settings.max_daily_llm_candidates <= 15

    # Attempting LIVE mode must raise a RuntimeError or ValidationError
    with pytest.raises((RuntimeError, ValidationError)):
        EngineSettings(execution_mode="live")

    # Attempting to enable averaging down must fail
    with pytest.raises((ValueError, ValidationError)):
        EngineSettings(allow_averaging_down=True)

    # Attempting to disable bracket orders must fail
    with pytest.raises((ValueError, ValidationError)):
        EngineSettings(require_bracket_order=False)

    # Attempting to use a non-paper Alpaca URL must fail
    with pytest.raises((RuntimeError, ValidationError)):
        EngineSettings(alpaca_paper_api_url="https://api.alpaca.markets")


def test_llm_candidate_cap_bounds() -> None:
    # Bounds: 1 <= max_daily_llm_candidates <= 15
    assert EngineSettings(max_daily_llm_candidates=1).max_daily_llm_candidates == 1
    assert EngineSettings(max_daily_llm_candidates=15).max_daily_llm_candidates == 15

    with pytest.raises((ValueError, ValidationError)):
        EngineSettings(max_daily_llm_candidates=0)

    with pytest.raises((ValueError, ValidationError)):
        EngineSettings(max_daily_llm_candidates=16)


def test_max_risk_per_trade_upper_bound() -> None:
    # Bounds: 0.0 < max_risk_per_trade_pct <= 0.005 (C-RISK-05, D-01)
    assert EngineSettings(max_risk_per_trade_pct=0.005).max_risk_per_trade_pct == 0.005
    assert EngineSettings(max_risk_per_trade_pct=0.002).max_risk_per_trade_pct == 0.002

    with pytest.raises((ValueError, ValidationError)):
        EngineSettings(max_risk_per_trade_pct=0.0051)

    with pytest.raises((ValueError, ValidationError)):
        EngineSettings(max_risk_per_trade_pct=0.0)

    with pytest.raises((ValueError, ValidationError)):
        EngineSettings(max_risk_per_trade_pct=-0.001)


def test_max_llm_calls_per_candidate_setting() -> None:
    # D-08 / C-QUOTA-07: MAX_LLM_CALLS_PER_CANDIDATE default 10, >= 1
    settings = EngineSettings()
    assert hasattr(settings, "max_llm_calls_per_candidate")
    assert settings.max_llm_calls_per_candidate == 10

    with pytest.raises((ValueError, ValidationError)):
        EngineSettings(max_llm_calls_per_candidate=0)


def test_pit_record_rejects_naive_timestamps_and_invalid_order() -> None:
    naive_dt = datetime(2026, 5, 4, 14, 0, 0)  # noqa: DTZ001
    utc_dt = datetime(2026, 5, 4, 14, 0, 0, tzinfo=UTC)

    with pytest.raises(ValidationError):
        PointInTimeRecord(
            published_at=naive_dt,
            collected_at=utc_dt,
            available_at=utc_dt,
            raw_payload_hash="a" * 64,
        )

    # available_at < published_at must fail
    earlier_utc = datetime(2026, 5, 4, 13, 0, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        PointInTimeRecord(
            published_at=utc_dt,
            collected_at=utc_dt,
            available_at=earlier_utc,
            raw_payload_hash="a" * 64,
        )


def test_nyse_1600_et_cutoff_and_weekend_gating() -> None:
    # Monday 2026-05-04 at 14:30 ET (intraday) -> available immediately at 14:30 ET (18:30 UTC)
    intraday_et = datetime(2026, 5, 4, 14, 30, 0, tzinfo=ET)
    avail_intraday = compute_available_at(intraday_et)
    assert avail_intraday == datetime(2026, 5, 4, 18, 30, 0, tzinfo=UTC)

    # Monday 2026-05-04 at 16:05 ET (after market close) -> Tuesday 2026-05-05 09:30 ET (13:30 UTC)
    after_hours_et = datetime(2026, 5, 4, 16, 5, 0, tzinfo=ET)
    avail_after_hours = compute_available_at(after_hours_et)
    assert avail_after_hours == datetime(2026, 5, 5, 13, 30, 0, tzinfo=UTC)

    # Friday 2026-05-08 at 16:00 ET -> Monday 2026-05-11 09:30 ET (13:30 UTC)
    friday_close_et = datetime(2026, 5, 8, 16, 0, 0, tzinfo=ET)
    avail_monday = compute_available_at(friday_close_et)
    assert avail_monday == datetime(2026, 5, 11, 13, 30, 0, tzinfo=UTC)

    # Pre-market Monday 2026-05-04 at 08:00 ET -> Monday 2026-05-04 09:30 ET (13:30 UTC)
    pre_market_et = datetime(2026, 5, 4, 8, 0, 0, tzinfo=ET)
    avail_open = compute_available_at(pre_market_et)
    assert avail_open == datetime(2026, 5, 4, 13, 30, 0, tzinfo=UTC)


def test_trading_days_counter() -> None:
    assert is_nyse_trading_day(date(2026, 5, 4)) is True  # Monday
    assert is_nyse_trading_day(date(2026, 5, 9)) is False  # Saturday
    # Friday May 8 to Tuesday May 12 = 2 trading sessions (Mon May 11, Tue May 12)
    assert count_trading_days_between(date(2026, 5, 8), date(2026, 5, 12)) == 2


def test_syndicated_news_deduplication() -> None:
    base_time = datetime(2026, 5, 4, 13, 0, 0, tzinfo=UTC)
    articles = [
        RawNewsArticle(
            source_id="reuters_001",
            publisher="Reuters",
            ticker="AAPL",
            headline="Apple reports temporary supply chain delay in Q2 assembly",
            summary="Apple Inc said on Monday a temporary component delay will shift shipments.",
            published_at=base_time,
            collected_at=base_time,
        ),
        RawNewsArticle(
            source_id="yahoo_002",
            publisher="Yahoo Finance",
            ticker="AAPL",
            headline="Apple reports temporary supply chain delay in Q2 assembly!",
            summary="Apple Inc said on Monday a temporary component delay will shift shipments.",
            published_at=base_time.replace(minute=5),
            collected_at=base_time.replace(minute=6),
        ),
        RawNewsArticle(
            source_id="msn_003",
            publisher="MSN Money",
            ticker="AAPL",
            headline="Apple reports temporary supply chain delay in Q2 assembly",
            summary="Syndicated copy from Reuters wire regarding Q2 component delay.",
            published_at=base_time.replace(minute=12),
            collected_at=base_time.replace(minute=15),
        ),
        RawNewsArticle(
            source_id="wsj_004",
            publisher="WSJ",
            ticker="AAPL",
            headline="Analysts maintain overweight rating on Apple despite supplier hiccup",
            summary="Institutional desks view the assembly bottleneck as fully resolved by June.",
            published_at=base_time.replace(hour=15),
            collected_at=base_time.replace(hour=15, minute=1),
        ),
    ]

    clusters = deduplicate_news_articles(articles)
    assert len(clusters) == 2

    first_cluster = clusters[0]
    assert first_cluster.primary_source_id == "reuters_001"
    assert first_cluster.independent_source_count == 1
    assert set(first_cluster.duplicate_source_ids) == {"yahoo_002", "msn_003"}
