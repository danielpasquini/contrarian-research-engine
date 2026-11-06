import math
from datetime import date
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict


class SimulatedTrade(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    entry_date: date
    exit_date: date
    gross_return_pct: float


class BacktestReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total_trades: int
    win_rate: float
    gross_mean_return_pct: float
    net_mean_return_pct: float
    stressed_delisting_mean_return_pct: float
    universe_bias_status: Literal["SURVIVORSHIP_BIAS_FREE", "STATIC_UNIVERSE_UNADJUSTED"]
    survivorship_bias_warning: str


def run_pit_backtest_evaluation(
    trades: list[SimulatedTrade],
    includes_delisted_equities: bool = False,
    one_way_slippage_bps: float = 10.0,
    delisting_tail_fraction: float = 0.02,
) -> BacktestReport:
    """
    Evaluate historical simulated trades under `VALIDATION_PROTOCOL.md`:
    - Deducts round-trip slippage (`2 * one_way_slippage_bps`).
    - Explicitly flags static present-day universes with `SURVIVORSHIP_BIAS_WARNING`.
    - Performs a synthetic delisting stress test overriding the worst `delisting_tail_fraction`
      of trades to `-100%` total loss (-1.0).
    """
    bias_status: Literal["SURVIVORSHIP_BIAS_FREE", "STATIC_UNIVERSE_UNADJUSTED"] = (
        "SURVIVORSHIP_BIAS_FREE" if includes_delisted_equities else "STATIC_UNIVERSE_UNADJUSTED"
    )
    warning_msg = (
        "Verified survivorship-bias-free universe including historical delistings."
        if includes_delisted_equities
        else (
            "WARNING: Static Universe - Survivorship Bias Unadjusted. "
            "Historical delistings are absent from free provider data."
        )
    )

    if not trades:
        return BacktestReport(
            total_trades=0,
            win_rate=0.0,
            gross_mean_return_pct=0.0,
            net_mean_return_pct=0.0,
            stressed_delisting_mean_return_pct=0.0,
            universe_bias_status=bias_status,
            survivorship_bias_warning=warning_msg,
        )

    round_trip_cost = (2.0 * one_way_slippage_bps) / 10_000.0
    gross_rets = np.array([t.gross_return_pct for t in trades], dtype=np.float64)
    net_rets = gross_rets - round_trip_cost

    wins = int(np.sum(net_rets > 0.0))
    win_rate = float(wins / len(trades))
    gross_mean = float(np.mean(gross_rets))
    net_mean = float(np.mean(net_rets))

    # Synthetic tail-risk delisting stress test
    stressed_rets = np.sort(net_rets.copy())
    n_delist = max(1, math.ceil(len(stressed_rets) * delisting_tail_fraction))
    stressed_rets[:n_delist] = -1.0
    stressed_mean = float(np.mean(stressed_rets))

    return BacktestReport(
        total_trades=len(trades),
        win_rate=round(win_rate, 4),
        gross_mean_return_pct=round(gross_mean, 6),
        net_mean_return_pct=round(net_mean, 6),
        stressed_delisting_mean_return_pct=round(stressed_mean, 6),
        universe_bias_status=bias_status,
        survivorship_bias_warning=warning_msg,
    )
