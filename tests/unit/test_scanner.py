from datetime import UTC, date, datetime, timedelta

import numpy as np

from src.normalization.pit_models import NormalizedBar
from src.scanner.indicators import compute_ticker_indicators
from src.scanner.pre_scanner import Stage1PreScanner


def _make_bar_series(
    ticker: str,
    n_days: int = 260,
    base_price: float = 100.0,
    base_volume: int = 1_000_000,
    drop_last_3d: tuple[float, float, float] | None = None,
    last_bar_recovery: float = 0.60,
    climax_volume_day2: bool = False,
    uptrend_pullback: bool = False,
) -> list[NormalizedBar]:
    bars: list[NormalizedBar] = []
    start_dt = date(2025, 1, 2)
    cur_date = start_dt
    price = base_price

    rng = np.random.default_rng(abs(hash(ticker)) % (2**32))

    for i in range(n_days):
        while cur_date.weekday() >= 5:
            cur_date += timedelta(days=1)

        vol = base_volume
        if uptrend_pullback:
            # Steady uptrend so SMA_50 > SMA_200 and Close > SMA_200, then mild 3-day pullback to SMA_50
            if i < n_days - 3:
                price = price * 1.0025
                open_p = price * 0.998
                high_p = price * 1.005
                low_p = price * 0.995
                close_p = price
            else:
                price = price * 0.988
                open_p = price * 1.008
                high_p = price * 1.010
                low_p = price * 0.990
                close_p = low_p + 0.50 * (high_p - low_p)
        elif drop_last_3d is not None and i >= n_days - 3:
            idx = i - (n_days - 3)
            ret = drop_last_3d[idx]
            price = price * (1.0 + ret)
            if idx == 1 and climax_volume_day2:
                vol = int(base_volume * 2.5)
            elif idx == 2 and climax_volume_day2:
                vol = int(base_volume * 1.4)

            low_p = price * 0.97
            high_p = price * 1.03
            if idx == 2:
                close_p = low_p + last_bar_recovery * (high_p - low_p)
            else:
                close_p = price
            open_p = (low_p + high_p) / 2.0
        else:
            noise = float(rng.normal(0.0002, 0.004))
            price = price * (1.0 + noise)
            low_p = price * 0.992
            high_p = price * 1.008
            close_p = price
            open_p = price

        pub_ts = datetime(cur_date.year, cur_date.month, cur_date.day, 20, 0, 0, tzinfo=UTC)
        bars.append(
            NormalizedBar(
                ticker=ticker,
                session_date=cur_date,
                open=round(open_p, 4),
                high=round(high_p, 4),
                low=round(low_p, 4),
                close=round(close_p, 4),
                raw_close=round(close_p, 4),
                volume=vol,
                dollar_volume=round(close_p * vol, 2),
                published_at=pub_ts,
                collected_at=pub_ts,
                available_at=pub_ts,
                raw_payload_hash="a" * 64,
            )
        )
        cur_date += timedelta(days=1)

    return bars


def test_lookahead_truncation_invariance() -> None:
    """
    Future-Truncation Invariance Test (VALIDATION_PROTOCOL.md Section 1.1):
    Indicators computed at index k on truncated series D[0:k+1] must match
    indicators computed at index k on full series D[0:N] to within 1e-12.
    """
    full_bars = _make_bar_series("AAPL", n_days=260, drop_last_3d=(-0.03, -0.04, -0.03))
    cutoff_idx = 220
    truncated_bars = full_bars[: cutoff_idx + 1]

    snap_truncated = compute_ticker_indicators(truncated_bars)
    snap_from_full = compute_ticker_indicators(full_bars, as_of_index=cutoff_idx)

    assert snap_truncated.session_date == snap_from_full.session_date
    assert abs(snap_truncated.rsi_2 - snap_from_full.rsi_2) <= 1e-12
    assert abs(snap_truncated.atr_14 - snap_from_full.atr_14) <= 1e-12
    assert abs(snap_truncated.z_score_return_3d - snap_from_full.z_score_return_3d) <= 1e-12
    assert abs(snap_truncated.sma_50 - snap_from_full.sma_50) <= 1e-12
    assert abs(snap_truncated.sma_200 - snap_from_full.sma_200) <= 1e-12


def test_falling_knife_rejected_vs_exhaustion_accepted() -> None:
    scanner = Stage1PreScanner(max_candidates=15)

    # 1. Free-fall knife: closes at very bottom of daily range (recovery=0.02), no volume contraction, below SMA_200
    knife_bars = _make_bar_series(
        "KNIFE",
        n_days=260,
        drop_last_3d=(-0.04, -0.05, -0.06),
        last_bar_recovery=0.02,
        climax_volume_day2=False,
    )

    # 2. Oversold Exhaustion candidate: sharp 3d drop (z <= -2.0, RSI_2 <= 10) + strong intraday recovery (0.65 >= 0.40)
    exhaust_bars = _make_bar_series(
        "EXHAUST",
        n_days=260,
        drop_last_3d=(-0.04, -0.05, -0.04),
        last_bar_recovery=0.65,
        climax_volume_day2=True,
    )

    # 3. Structural Pullback candidate: strong uptrend pulling back to SMA_50 with RSI_2 <= 15
    pullback_bars = _make_bar_series(
        "PULLBACK",
        n_days=260,
        uptrend_pullback=True,
    )

    # 4. Illiquid / penny stock rejected
    penny_bars = _make_bar_series(
        "PENNY",
        n_days=260,
        base_price=4.50,
        base_volume=100_000,
        drop_last_3d=(-0.04, -0.05, -0.04),
        last_bar_recovery=0.70,
    )

    candidates = scanner.scan_universe(
        {
            "KNIFE": knife_bars,
            "EXHAUST": exhaust_bars,
            "PULLBACK": pullback_bars,
            "PENNY": penny_bars,
        }
    )

    selected_tickers = [c.ticker for c in candidates]
    assert "KNIFE" not in selected_tickers
    assert "PENNY" not in selected_tickers
    assert "EXHAUST" in selected_tickers
    assert "PULLBACK" in selected_tickers


def test_scanner_strictly_caps_at_15_candidates() -> None:
    scanner = Stage1PreScanner(max_candidates=15)
    universe = {
        f"SYM{i:03d}": _make_bar_series(
            f"SYM{i:03d}",
            n_days=260,
            drop_last_3d=(-0.035 - (i * 0.0005), -0.04, -0.03),
            last_bar_recovery=0.60,
            climax_volume_day2=True,
        )
        for i in range(25)
    }

    shortlist = scanner.scan_universe(universe)
    assert len(shortlist) == 15
    assert [c.scanner_rank for c in shortlist] == list(range(1, 16))


def test_atr_14_computed_strictly_on_raw_dollar_basis_not_adjusted() -> None:
    """
    [CRIT-02]: NormalizedBar must expose raw_open, raw_high, raw_low, raw_close,
    and Wilder's ATR_14 must be computed strictly on raw dollar prices,
    never on split/dividend-adjusted prices.
    """
    bars: list[NormalizedBar] = []
    cur_date = date(2025, 1, 2)
    for _ in range(210):
        while cur_date.weekday() >= 5:
            cur_date += timedelta(days=1)
        pub_ts = datetime(cur_date.year, cur_date.month, cur_date.day, 20, 0, 0, tzinfo=UTC)
        # Adjusted prices are scaled by 0.5x (range = 50.5 - 49.5 = $1.00)
        # Raw prices are in unadjusted trading dollars (range = 102.0 - 98.0 = $4.00)
        bars.append(
            NormalizedBar(
                ticker="SPLIT",
                session_date=cur_date,
                open=50.0,
                high=50.5,
                low=49.5,
                close=50.0,
                raw_open=100.0,
                raw_high=102.0,
                raw_low=98.0,
                raw_close=100.0,
                volume=1_000_000,
                dollar_volume=100_000_000.0,
                published_at=pub_ts,
                collected_at=pub_ts,
                available_at=pub_ts,
                raw_payload_hash="b" * 64,
            )
        )
        cur_date += timedelta(days=1)

    assert bars[-1].raw_open == 100.0
    assert bars[-1].raw_high == 102.0
    assert bars[-1].raw_low == 98.0
    assert bars[-1].raw_close == 100.0

    snap = compute_ticker_indicators(bars)
    # True Range on raw basis is 102.0 - 98.0 = $4.00 (NOT $1.00 from adjusted prices!)
    assert abs(snap.atr_14 - 4.0) <= 1e-6
