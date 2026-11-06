from datetime import date, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from src.normalization.pit_models import NormalizedBar
from src.scanner.indicators import TechnicalSnapshot, compute_ticker_indicators

SetupType = Literal["OVERSOLD_EXHAUSTION", "STRUCTURAL_PULLBACK"]


class ScannerCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: UUID = Field(default_factory=uuid4)
    scan_date: date
    ticker: str
    close_price: float
    addv_20d: float
    return_3d_pct: float
    return_5d_pct: float
    z_score_return_3d: float
    rsi_2: float
    atr_14: float
    atr_pct: float
    sma_20: float
    sma_50: float
    sma_200: float
    volume_ratio_20d: float
    intraday_recovery_ratio: float
    distance_to_sma50_atr: float
    distance_to_sma200_atr: float
    setup_type: SetupType
    dislocation_score: float
    scanner_rank: int = Field(ge=1, le=15)
    available_at: datetime


class Stage1PreScanner:
    """
    Stage 1 Deterministic Python Pre-Scanner ('Filter First, LLM Second').
    Filters ~500 liquid US equities down to at most `max_candidates` (<= 15) per day.
    """

    def __init__(
        self,
        min_share_price: float = 10.0,
        min_addv_20d: float = 20_000_000.0,
        max_candidates: int = 15,
    ) -> None:
        if max_candidates < 1 or max_candidates > 15:
            raise ValueError("Stage 1 max_candidates must be between 1 and 15.")
        self.min_share_price = min_share_price
        self.min_addv_20d = min_addv_20d
        self.max_candidates = max_candidates

    def evaluate_snapshot(self, snap: TechnicalSnapshot) -> tuple[SetupType | None, float]:
        # 1. Baseline Liquidity & Price Floor
        if snap.raw_close_price < self.min_share_price or snap.addv_20d < self.min_addv_20d:
            return None, 0.0

        # 2. Setup A: Short-Term Capitulation & Exhaustion (Preventing Falling Knives)
        has_intraday_demand = snap.intraday_recovery_ratio >= 0.40
        has_climax_exhaustion = (
            snap.prev_volume_ratio_20d >= 2.0
            and snap.volume_contracted_vs_prev
            and snap.low_held_vs_prev_atr
        )
        if (
            snap.z_score_return_3d <= -2.0
            and snap.rsi_2 <= 10.0
            and (has_intraday_demand or has_climax_exhaustion)
        ):
            score = (
                abs(snap.z_score_return_3d) * 20.0
                + (10.0 - snap.rsi_2) * 2.0
                + (snap.intraday_recovery_ratio * 15.0)
            )
            return "OVERSOLD_EXHAUSTION", float(score)

        # 3. Setup B: Structural Uptrend Pullback
        if (
            snap.close_price > snap.sma_200
            and snap.sma_50 > snap.sma_200
            and snap.rsi_2 <= 15.0
            and abs(snap.distance_to_sma50_atr) <= 1.0
            and snap.intraday_recovery_ratio >= 0.30
        ):
            score = (
                (15.0 - snap.rsi_2) * 2.5
                + (1.0 - abs(snap.distance_to_sma50_atr)) * 20.0
                + abs(snap.z_score_return_3d) * 10.0
            )
            return "STRUCTURAL_PULLBACK", float(score)

        return None, 0.0

    def scan_universe(
        self,
        universe_bars: dict[str, list[NormalizedBar]],
        as_of_index: int | None = None,
    ) -> list[ScannerCandidate]:
        qualifying: list[tuple[TechnicalSnapshot, SetupType, float]] = []

        for _ticker, bars in universe_bars.items():
            if len(bars) < 201:
                continue
            snap = compute_ticker_indicators(bars, as_of_index=as_of_index)
            setup_type, score = self.evaluate_snapshot(snap)
            if setup_type is not None:
                qualifying.append((snap, setup_type, score))

        # Sort deterministically by descending dislocation score, then ticker symbol
        qualifying.sort(key=lambda item: (-item[2], item[0].ticker))
        shortlisted = qualifying[: self.max_candidates]

        results: list[ScannerCandidate] = []
        for rank_idx, (snap, setup_type, score) in enumerate(shortlisted, start=1):
            results.append(
                ScannerCandidate(
                    scan_date=snap.session_date,
                    ticker=snap.ticker,
                    close_price=snap.close_price,
                    addv_20d=snap.addv_20d,
                    return_3d_pct=snap.return_3d_pct,
                    return_5d_pct=snap.return_5d_pct,
                    z_score_return_3d=snap.z_score_return_3d,
                    rsi_2=snap.rsi_2,
                    atr_14=snap.atr_14,
                    atr_pct=snap.atr_pct,
                    sma_20=snap.sma_20,
                    sma_50=snap.sma_50,
                    sma_200=snap.sma_200,
                    volume_ratio_20d=snap.volume_ratio_20d,
                    intraday_recovery_ratio=snap.intraday_recovery_ratio,
                    distance_to_sma50_atr=snap.distance_to_sma50_atr,
                    distance_to_sma200_atr=snap.distance_to_sma200_atr,
                    setup_type=setup_type,
                    dislocation_score=round(score, 4),
                    scanner_rank=rank_idx,
                    available_at=snap.available_at,
                )
            )
        return results
