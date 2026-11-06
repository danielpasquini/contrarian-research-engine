import hashlib
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from src.normalization.calendar import compute_available_at, ensure_utc
from src.normalization.pit_models import PointInTimeRecord


class RawXBRLFiling(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    cik: str
    accession_number: str
    form_type: Literal["10-Q", "10-K", "8-K"]
    period_of_report: date
    acceptance_datetime: datetime
    collected_at: datetime
    revenue_ttm: float | None = None
    operating_income_ttm: float | None = None
    operating_cash_flow_ttm: float | None = None
    total_debt: float | None = None
    cash_and_equivalents: float | None = None

    @field_validator("acceptance_datetime", "collected_at", mode="before")
    @classmethod
    def ensure_utc_dt(cls, v: datetime) -> datetime:
        return ensure_utc(v)


class FundamentalSnapshot(PointInTimeRecord):
    """
    Point-in-time fundamental snapshot gated strictly by SEC `acceptance_datetime`
    (mapped to `published_at` -> `available_at`), never by `period_of_report`.
    """

    ticker: str
    cik: str
    accession_number: str
    form_type: Literal["10-Q", "10-K", "8-K"]
    period_of_report: date
    revenue_ttm: float | None = None
    operating_income_ttm: float | None = None
    operating_cash_flow_ttm: float | None = None
    total_debt: float | None = None
    cash_and_equivalents: float | None = None
    fundamental_health_score: float


def compute_fundamental_health_score(
    operating_cash_flow_ttm: float | None,
    operating_income_ttm: float | None,
    total_debt: float | None,
    cash_and_equivalents: float | None,
) -> float:
    """
    Deterministic balance-sheet and cash-flow solvency score in [0.0, 1.0].
    Missing critical metrics return 0.0 (never silently imputed).
    """
    if operating_cash_flow_ttm is None or total_debt is None or cash_and_equivalents is None:
        return 0.0

    score = 0.0
    if operating_cash_flow_ttm > 0:
        score += 0.45
    if operating_income_ttm is not None and operating_income_ttm > 0:
        score += 0.25

    net_debt = total_debt - cash_and_equivalents
    if net_debt <= 0:
        score += 0.30
    elif operating_cash_flow_ttm > 0:
        leverage_ratio = net_debt / operating_cash_flow_ttm
        if leverage_ratio < 2.0:
            score += 0.25
        elif leverage_ratio < 4.0:
            score += 0.15

    return round(min(1.0, max(0.0, score)), 4)


def select_point_in_time_fundamentals(
    filings: list[RawXBRLFiling],
    decision_timestamp: datetime,
) -> FundamentalSnapshot | None:
    """
    Filter SEC XBRL filings strictly by `available_at <= decision_timestamp`
    (derived from SEC `acceptance_datetime`), ignoring `period_of_report` for gating.
    Returns the most recently accepted filing available at `decision_timestamp`.
    """
    decision_utc = ensure_utc(decision_timestamp)
    eligible: list[tuple[datetime, RawXBRLFiling]] = []

    for f in filings:
        avail_at = compute_available_at(f.acceptance_datetime)
        if avail_at <= decision_utc:
            eligible.append((avail_at, f))

    if not eligible:
        return None

    # Sort by acceptance_datetime descending, then accession_number
    eligible.sort(
        key=lambda item: (item[1].acceptance_datetime, item[1].accession_number), reverse=True
    )
    best_avail, best = eligible[0]

    health = compute_fundamental_health_score(
        operating_cash_flow_ttm=best.operating_cash_flow_ttm,
        operating_income_ttm=best.operating_income_ttm,
        total_debt=best.total_debt,
        cash_and_equivalents=best.cash_and_equivalents,
    )
    payload_hash = hashlib.sha256(
        f"{best.cik}:{best.accession_number}:{best.acceptance_datetime.isoformat()}".encode()
    ).hexdigest()

    return FundamentalSnapshot(
        ticker=best.ticker,
        cik=best.cik,
        accession_number=best.accession_number,
        form_type=best.form_type,
        period_of_report=best.period_of_report,
        revenue_ttm=best.revenue_ttm,
        operating_income_ttm=best.operating_income_ttm,
        operating_cash_flow_ttm=best.operating_cash_flow_ttm,
        total_debt=best.total_debt,
        cash_and_equivalents=best.cash_and_equivalents,
        fundamental_health_score=health,
        published_at=best.acceptance_datetime,
        collected_at=best.collected_at,
        available_at=best_avail,
        raw_payload_hash=payload_hash,
    )
