from datetime import date, datetime

import numpy as np
from pydantic import BaseModel, ConfigDict

from src.normalization.pit_models import NormalizedBar


class TechnicalSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    session_date: date
    close_price: float
    raw_close_price: float
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
    prev_volume_ratio_20d: float
    volume_contracted_vs_prev: bool
    low_held_vs_prev_atr: bool
    intraday_recovery_ratio: float
    distance_to_sma50_atr: float
    distance_to_sma200_atr: float
    available_at: datetime


def _wilder_rsi(closes: np.ndarray, period: int = 2) -> float:
    """Compute Wilder's RSI at the final element of `closes` strictly without look-ahead."""
    deltas = np.diff(closes)
    if len(deltas) < period:
        return 50.0
    gains = np.where(deltas > 0.0, deltas, 0.0)
    losses = np.where(deltas < 0.0, -deltas, 0.0)

    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))

    alpha = 1.0 / period
    for i in range(period, len(deltas)):
        avg_gain = (1.0 - alpha) * avg_gain + alpha * float(gains[i])
        avg_loss = (1.0 - alpha) * avg_loss + alpha * float(losses[i])

    if avg_loss <= 1e-12:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def _wilder_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    """Compute Wilder's Average True Range at the final element strictly without look-ahead."""
    n = len(closes)
    if n < 2:
        return float(max(highs[-1] - lows[-1], 1e-6))

    prev_closes = closes[:-1]
    tr = np.maximum(
        highs[1:] - lows[1:],
        np.maximum(np.abs(highs[1:] - prev_closes), np.abs(lows[1:] - prev_closes)),
    )
    if len(tr) < period:
        return float(np.mean(tr))

    atr = float(np.mean(tr[:period]))
    alpha = 1.0 / period
    for i in range(period, len(tr)):
        atr = (1.0 - alpha) * atr + alpha * float(tr[i])
    return float(max(atr, 1e-6))


def compute_ticker_indicators(
    bars: list[NormalizedBar],
    as_of_index: int | None = None,
) -> TechnicalSnapshot:
    """
    Compute point-in-time technical indicators up to `as_of_index` (inclusive).
    Slices input `bars[:as_of_index + 1]` upfront so future bars cannot leak.
    """
    if not bars:
        raise ValueError("Cannot compute indicators on empty bar list.")

    end_idx = (len(bars) - 1) if as_of_index is None else as_of_index
    if end_idx < 200:
        raise ValueError(f"Insufficient history ({end_idx + 1} bars); minimum 201 required.")

    window_bars = bars[: end_idx + 1]
    latest = window_bars[-1]
    prev = window_bars[-2]

    closes = np.array([b.close for b in window_bars], dtype=np.float64)
    raw_highs = np.array([b.raw_high for b in window_bars], dtype=np.float64)
    raw_lows = np.array([b.raw_low for b in window_bars], dtype=np.float64)
    raw_closes = np.array([b.raw_close for b in window_bars], dtype=np.float64)
    volumes = np.array([b.volume for b in window_bars], dtype=np.float64)
    dollar_vols = np.array([b.dollar_volume for b in window_bars], dtype=np.float64)

    ret_3d = float((closes[-1] / closes[-4]) - 1.0)
    ret_5d = float((closes[-1] / closes[-6]) - 1.0)

    # Trailing 3-day log returns over up to the past 252 sessions ending at `end_idx`
    lookback = min(252, len(closes) - 3)
    log_closes = np.log(closes)
    rolling_3d_log_rets = log_closes[3:] - log_closes[:-3]
    trailing_window = rolling_3d_log_rets[-lookback:]
    mean_3d = float(np.mean(trailing_window))
    std_3d = float(np.std(trailing_window, ddof=1)) if len(trailing_window) > 1 else 1e-6
    current_log_ret_3d = float(rolling_3d_log_rets[-1])
    z_score_3d = (current_log_ret_3d - mean_3d) / max(std_3d, 1e-8)

    rsi_2 = _wilder_rsi(closes, period=2)
    # C-PIT-12 & C-RISK-04: Compute Wilder's ATR_14 strictly on raw dollar prices
    atr_14 = _wilder_atr(raw_highs, raw_lows, raw_closes, period=14)

    sma_20 = float(np.mean(closes[-20:]))
    sma_50 = float(np.mean(closes[-50:]))
    sma_200 = float(np.mean(closes[-200:]))
    addv_20d = float(np.mean(dollar_vols[-20:]))

    vol_sma_20 = float(np.mean(volumes[-20:]))
    prev_vol_sma_20 = float(np.mean(volumes[-21:-1]))
    vol_ratio_20d = float(volumes[-1] / max(vol_sma_20, 1.0))
    prev_vol_ratio_20d = float(volumes[-2] / max(prev_vol_sma_20, 1.0))

    bar_range = max(latest.raw_high - latest.raw_low, 1e-8)
    intraday_recovery = float((latest.raw_close - latest.raw_low) / bar_range)

    dist_sma50_atr = float((latest.close - sma_50) / atr_14)
    dist_sma200_atr = float((latest.close - sma_200) / atr_14)

    return TechnicalSnapshot(
        ticker=latest.ticker,
        session_date=latest.session_date,
        close_price=latest.close,
        raw_close_price=latest.raw_close,
        addv_20d=addv_20d,
        return_3d_pct=ret_3d,
        return_5d_pct=ret_5d,
        z_score_return_3d=z_score_3d,
        rsi_2=rsi_2,
        atr_14=atr_14,
        atr_pct=float(atr_14 / latest.raw_close),
        sma_20=sma_20,
        sma_50=sma_50,
        sma_200=sma_200,
        volume_ratio_20d=vol_ratio_20d,
        prev_volume_ratio_20d=prev_vol_ratio_20d,
        volume_contracted_vs_prev=bool(volumes[-1] < volumes[-2]),
        low_held_vs_prev_atr=bool(latest.raw_low >= (prev.raw_low - 0.25 * atr_14)),
        intraday_recovery_ratio=intraday_recovery,
        distance_to_sma50_atr=dist_sma50_atr,
        distance_to_sma200_atr=dist_sma200_atr,
        available_at=latest.available_at,
    )
