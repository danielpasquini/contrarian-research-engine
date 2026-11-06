from datetime import UTC, date, datetime

from src.fundamentals.earnings_calendar import EarningsBlackoutStatus
from src.fundamentals.xbrl_parser import FundamentalSnapshot
from src.intelligence.schemas import CitedClaim, LLMAnalysisOutput
from src.scanner.pre_scanner import ScannerCandidate
from src.strategies.engines import evaluate_contrarian_engines


def _make_candidate() -> ScannerCandidate:
    return ScannerCandidate(
        scan_date=date(2026, 5, 4),
        ticker="AAPL",
        close_price=185.0,
        addv_20d=800_000_000.0,
        return_3d_pct=-0.095,
        return_5d_pct=-0.11,
        z_score_return_3d=-3.2,
        rsi_2=4.5,
        atr_14=4.0,
        atr_pct=4.0 / 185.0,
        sma_20=196.0,
        sma_50=186.5,
        sma_200=175.0,
        volume_ratio_20d=1.8,
        intraday_recovery_ratio=0.72,
        distance_to_sma50_atr=-0.375,
        distance_to_sma200_atr=2.5,
        setup_type="OVERSOLD_EXHAUSTION",
        dislocation_score=92.0,
        scanner_rank=1,
        available_at=datetime(2026, 5, 4, 20, 0, 0, tzinfo=UTC),
    )


def _make_fundamentals() -> FundamentalSnapshot:
    ts = datetime(2026, 4, 25, 16, 0, 0, tzinfo=UTC)
    return FundamentalSnapshot(
        ticker="AAPL",
        cik="0000320193",
        accession_number="0000320193-26-000010",
        form_type="10-Q",
        period_of_report=date(2026, 3, 28),
        revenue_ttm=390_000_000_000.0,
        operating_income_ttm=120_000_000_000.0,
        operating_cash_flow_ttm=115_000_000_000.0,
        total_debt=95_000_000_000.0,
        cash_and_equivalents=65_000_000_000.0,
        fundamental_health_score=0.95,
        published_at=ts,
        collected_at=ts,
        available_at=ts,
        raw_payload_hash="f" * 64,
    )


def _make_llm_output(veto: str = "APPROVE") -> LLMAnalysisOutput:
    return LLMAnalysisOutput(
        ticker="AAPL",
        event_classification="GUIDANCE_CUT",
        verified_facts=[
            CitedClaim(
                claim="8-K confirms full-year cash flow guidance unchanged despite Q2 port delay.",
                source_id="sec_8k_1",
                is_new_information=True,
            )
        ],
        market_narrative_summary="Sensationalist headlines exaggerated a 2-week port delay.",
        fundamental_impact="TEMPORARY_1_2_QUARTERS",
        narrative_vs_filing_divergence=0.88,
        sentiment_inflection_detected=True,
        contradicting_evidence=[],
        red_flags_detected=[],
        veto_decision=veto,  # type: ignore[arg-type]
        confidence_score=0.92,
        missing_information=[],
    )


def test_three_engines_score_approved_candidate() -> None:
    cand = _make_candidate()
    fund = _make_fundamentals()
    llm = _make_llm_output("APPROVE")
    blackout = EarningsBlackoutStatus(
        ticker="AAPL",
        as_of_date=date(2026, 5, 4),
        next_earnings_date=date(2026, 7, 30),
        trading_days_to_earnings=60,
        earnings_blackout=False,
    )

    signal = evaluate_contrarian_engines(
        candidate=cand,
        fundamentals=fund,
        llm_analysis=llm,
        earnings_status=blackout,
        independent_source_count=1,
        total_raw_articles=5,
    )

    assert signal.is_actionable is True
    assert signal.negative_overreaction_score > 70.0
    assert signal.narrative_divergence_score > 75.0
    assert signal.sentiment_inflection_score > 75.0
    assert 0.0 < signal.composite_score <= 100.0
    assert signal.primary_strategy in ("neg_overreaction", "narrative_div", "sentiment_infl")


def test_veto_or_earnings_blackout_zeros_scores_and_blocks_signal() -> None:
    cand = _make_candidate()
    fund = _make_fundamentals()
    llm_veto = _make_llm_output("VETO")
    no_blackout = EarningsBlackoutStatus(
        ticker="AAPL",
        as_of_date=date(2026, 5, 4),
        next_earnings_date=date(2026, 7, 30),
        trading_days_to_earnings=60,
        earnings_blackout=False,
    )

    sig_vetoed = evaluate_contrarian_engines(
        candidate=cand,
        fundamentals=fund,
        llm_analysis=llm_veto,
        earnings_status=no_blackout,
    )
    assert sig_vetoed.is_actionable is False
    assert sig_vetoed.composite_score == 0.0

    # Even if LLM approves, an earnings blackout (<= 3 trading sessions) blocks the signal
    llm_ok = _make_llm_output("APPROVE")
    active_blackout = EarningsBlackoutStatus(
        ticker="AAPL",
        as_of_date=date(2026, 5, 4),
        next_earnings_date=date(2026, 5, 6),
        trading_days_to_earnings=2,
        earnings_blackout=True,
    )
    sig_blackout = evaluate_contrarian_engines(
        candidate=cand,
        fundamentals=fund,
        llm_analysis=llm_ok,
        earnings_status=active_blackout,
    )
    assert sig_blackout.is_actionable is False
    assert sig_blackout.composite_score == 0.0


def test_unknown_earnings_date_blocks_strategy_signal() -> None:
    """[CRIT-01]: Ticker without a known future earnings date must be blocked in Stage 2."""
    from src.fundamentals.earnings_calendar import evaluate_earnings_blackout

    cand = _make_candidate()
    fund = _make_fundamentals()
    llm_ok = _make_llm_output("APPROVE")

    unknown_status = evaluate_earnings_blackout(
        ticker="AAPL",
        as_of_date=date(2026, 5, 4),
        next_earnings_date=None,
    )
    sig_unknown = evaluate_contrarian_engines(
        candidate=cand,
        fundamentals=fund,
        llm_analysis=llm_ok,
        earnings_status=unknown_status,
    )
    assert sig_unknown.is_actionable is False
    assert sig_unknown.composite_score == 0.0
    assert sig_unknown.veto_reason == "VETO_EARNINGS_BLACKOUT"

    # Even if a caller manually constructs EarningsBlackoutStatus with next_earnings_date=None
    manual_unverified = EarningsBlackoutStatus(
        ticker="AAPL",
        as_of_date=date(2026, 5, 4),
        next_earnings_date=None,
        trading_days_to_earnings=None,
        earnings_blackout=False,
    )
    sig_manual = evaluate_contrarian_engines(
        candidate=cand,
        fundamentals=fund,
        llm_analysis=llm_ok,
        earnings_status=manual_unverified,
    )
    assert sig_manual.is_actionable is False
    assert sig_manual.composite_score == 0.0
    assert sig_manual.veto_reason == "VETO_EARNINGS_BLACKOUT"
