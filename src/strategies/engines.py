from datetime import date, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from src.fundamentals.earnings_calendar import EarningsBlackoutStatus
from src.fundamentals.xbrl_parser import FundamentalSnapshot
from src.intelligence.schemas import LLMAnalysisOutput
from src.scanner.pre_scanner import ScannerCandidate

StrategyName = Literal["neg_overreaction", "narrative_div", "sentiment_infl"]


class StrategySignal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    signal_id: UUID = Field(default_factory=uuid4)
    signal_date: date
    ticker: str
    negative_overreaction_score: float = Field(ge=0.0, le=100.0)
    narrative_divergence_score: float = Field(ge=0.0, le=100.0)
    sentiment_inflection_score: float = Field(ge=0.0, le=100.0)
    composite_score: float = Field(ge=0.0, le=100.0)
    primary_strategy: StrategyName
    is_actionable: bool
    veto_reason: str | None = None
    entry_reference_price: float
    atr_14: float
    available_at: datetime


def _clamp_01(val: float) -> float:
    return max(0.0, min(1.0, val))


def evaluate_contrarian_engines(
    candidate: ScannerCandidate,
    fundamentals: FundamentalSnapshot | None,
    llm_analysis: LLMAnalysisOutput,
    earnings_status: EarningsBlackoutStatus,
    independent_source_count: int = 1,
    total_raw_articles: int = 1,
    min_actionable_score: float = 60.0,
) -> StrategySignal:
    """
    Compute the three independent contrarian scores defined in `docs/STRATEGY_HYPOTHESES.md`.
    All scores are forced to 0.0 and `is_actionable = False` if:
    - Stage 2 `llm_analysis.veto_decision == "VETO"`
    - `earnings_status.earnings_blackout is True`
    - `fundamentals is None` or `llm_analysis.confidence_score < 0.60`
    """
    if (
        earnings_status.earnings_blackout
        or earnings_status.next_earnings_date is None
        or earnings_status.trading_days_to_earnings is None
        or earnings_status.next_earnings_date < candidate.scan_date
    ):
        return StrategySignal(
            signal_date=candidate.scan_date,
            ticker=candidate.ticker,
            negative_overreaction_score=0.0,
            narrative_divergence_score=0.0,
            sentiment_inflection_score=0.0,
            composite_score=0.0,
            primary_strategy="neg_overreaction",
            is_actionable=False,
            veto_reason="VETO_EARNINGS_BLACKOUT",
            entry_reference_price=candidate.close_price,
            atr_14=candidate.atr_14,
            available_at=candidate.available_at,
        )

    if (
        llm_analysis.veto_decision == "VETO"
        or fundamentals is None
        or llm_analysis.confidence_score < 0.60
    ):
        reason = (
            "VETO_MISSING_FUNDAMENTALS"
            if fundamentals is None
            else "VETO_LLM_RED_FLAG_OR_LOW_CONFIDENCE"
        )
        return StrategySignal(
            signal_date=candidate.scan_date,
            ticker=candidate.ticker,
            negative_overreaction_score=0.0,
            narrative_divergence_score=0.0,
            sentiment_inflection_score=0.0,
            composite_score=0.0,
            primary_strategy="neg_overreaction",
            is_actionable=False,
            veto_reason=reason,
            entry_reference_price=candidate.close_price,
            atr_14=candidate.atr_14,
            available_at=candidate.available_at,
        )

    f_health = _clamp_01(fundamentals.fundamental_health_score)
    t_stab = _clamp_01(candidate.intraday_recovery_ratio)

    # Engine 1: Negative Overreaction
    t_mag = _clamp_01((abs(candidate.z_score_return_3d) - 1.5) / 3.0)
    impact_map = {
        "NONE": 1.0,
        "TEMPORARY_1_2_QUARTERS": 0.75,
        "UNKNOWN": 0.0,
        "STRUCTURAL_MULTI_YEAR": 0.0,
    }
    i_temp = impact_map.get(llm_analysis.fundamental_impact, 0.0)
    s_overreaction = round(
        100.0 * (0.35 * t_mag + 0.25 * t_stab + 0.25 * f_health + 0.15 * i_temp), 2
    )

    # Engine 2: Narrative Divergence
    d_filing = _clamp_01(llm_analysis.narrative_vs_filing_divergence)
    raw_count = max(1, total_raw_articles)
    ind_count = max(1, min(independent_source_count, raw_count))
    s_synd = _clamp_01(1.0 - (ind_count / raw_count)) if raw_count > 1 else 0.5
    s_divergence = round(
        100.0 * (0.40 * d_filing + 0.20 * s_synd + 0.20 * f_health + 0.20 * t_stab), 2
    )

    # Engine 3: Sentiment Inflection
    above_sma200 = 1.0 if candidate.close_price > candidate.sma_200 else 0.3
    prox_sma50 = _clamp_01(1.0 - min(abs(candidate.distance_to_sma50_atr), 2.0) / 2.0)
    t_trend = _clamp_01(0.6 * above_sma200 + 0.4 * prox_sma50)
    i_inflect = 1.0 if llm_analysis.sentiment_inflection_detected else 0.0
    t_vol = _clamp_01(0.5 * t_stab + 0.5 * _clamp_01(candidate.volume_ratio_20d / 2.5))
    s_inflection = round(
        100.0 * (0.35 * t_trend + 0.30 * i_inflect + 0.20 * t_vol + 0.15 * f_health), 2
    )

    scores: dict[StrategyName, float] = {
        "neg_overreaction": s_overreaction,
        "narrative_div": s_divergence,
        "sentiment_infl": s_inflection,
    }
    primary_strat = max(scores.items(), key=lambda kv: kv[1])[0]
    max_s = max(scores.values())
    mean_s = sum(scores.values()) / 3.0
    composite = round(min(100.0, max_s + 0.15 * mean_s), 2)

    return StrategySignal(
        signal_date=candidate.scan_date,
        ticker=candidate.ticker,
        negative_overreaction_score=s_overreaction,
        narrative_divergence_score=s_divergence,
        sentiment_inflection_score=s_inflection,
        composite_score=composite,
        primary_strategy=primary_strat,
        is_actionable=bool(composite >= min_actionable_score),
        veto_reason=None,
        entry_reference_price=candidate.close_price,
        atr_14=candidate.atr_14,
        available_at=candidate.available_at,
    )
