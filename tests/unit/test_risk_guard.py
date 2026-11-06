from datetime import date

import pytest

from src.config import EngineSettings
from src.risk.guard import HeldPosition, OrderValidationGuard, PortfolioState, ProposedBracketOrder
from src.risk.sizing import build_volatility_sized_bracket_order


def _default_portfolio(
    equity: float = 100_000.0,
    start_of_day_equity: float = 100_000.0,
    positions: dict[str, HeldPosition] | None = None,
    orders_submitted_today: int = 0,
    existing_client_order_ids: set[str] | None = None,
) -> PortfolioState:
    return PortfolioState(
        total_equity=equity,
        start_of_day_equity=start_of_day_equity,
        open_positions=positions or {},
        orders_submitted_today=orders_submitted_today,
        existing_client_order_ids=existing_client_order_ids or set(),
    )


def test_volatility_adjusted_bracket_sizing() -> None:
    settings = EngineSettings()
    # Equity = $100,000, max_risk_pct = 0.005 ($500), max_position_pct = 0.08 ($8,000)
    # Entry = $100, ATR_14 = $2.50, stop_mult = 2.0 -> Stop Loss = $95.00 ($5.00 risk/share)
    # Risk-based qty = $500 / $5.00 = 100 shares ($10,000 notional)
    # Position-cap qty = $8,000 / $100 = 80 shares ($8,000 notional) -> min(100, 80) = 80 shares!
    order = build_volatility_sized_bracket_order(
        ticker="AAPL",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        entry_price=100.0,
        atr_14=2.50,
        total_equity=100_000.0,
        settings=settings,
    )

    assert order.order_class == "BRACKET"
    assert order.stop_loss_price == 95.0
    assert order.take_profit_price == 110.0  # 2.0 reward:risk -> +$10.00
    assert order.qty == 80
    assert order.notional_dollars == 8_000.0
    assert order.risk_dollars == 400.0
    assert order.client_order_id == "AAPL_20260504_neg_overreaction"

    # Edge cases in sizing: invalid inputs, ATR stop below 0, and qty < 1
    with pytest.raises(ValueError, match="strictly positive"):
        build_volatility_sized_bracket_order(
            "AAPL", date(2026, 5, 4), "neg", 0.0, 2.0, 100_000.0, settings
        )

    with pytest.raises(ValueError, match="Invalid computed stop_loss_price"):
        build_volatility_sized_bracket_order(
            "AAPL", date(2026, 5, 4), "neg", 10.0, 6.0, 100_000.0, settings
        )

    with pytest.raises(ValueError, match="Computed share quantity"):
        build_volatility_sized_bracket_order(
            "BRK.A", date(2026, 5, 4), "neg", 50_000.0, 100.0, 10_000.0, settings
        )


def test_guard_approves_valid_bracket_order() -> None:
    settings = EngineSettings()
    guard = OrderValidationGuard(settings)
    portfolio = _default_portfolio()
    order = build_volatility_sized_bracket_order(
        ticker="MSFT",
        signal_date=date(2026, 5, 4),
        strategy_name="narrative_div",
        entry_price=200.0,
        atr_14=4.0,
        total_equity=100_000.0,
        settings=settings,
    )

    validated = guard.validate_order(order, portfolio, days_to_earnings=15, llm_veto="APPROVE")
    assert validated.guard_status == "PASSED"
    assert validated.qty == order.qty


def test_guard_rejects_averaging_down_with_value_error() -> None:
    """
    AGENTS.md Section 7.1: Never add to an existing losing position.
    If a ticker is already in the portfolio below its average entry price,
    any new buy order for that ticker must raise a ValueError.
    """
    settings = EngineSettings()
    guard = OrderValidationGuard(settings)
    losing_pos = HeldPosition(
        ticker="NVDA",
        qty=20,
        avg_entry_price=120.0,
        current_price=110.0,  # Below avg_entry_price -> unrealized loss!
    )
    portfolio = _default_portfolio(positions={"NVDA": losing_pos})
    order = build_volatility_sized_bracket_order(
        ticker="NVDA",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        entry_price=110.0,
        atr_14=3.0,
        total_equity=100_000.0,
        settings=settings,
    )

    with pytest.raises(ValueError, match="AVERAGING_DOWN_PROHIBITED"):
        guard.validate_order(order, portfolio, days_to_earnings=20, llm_veto="APPROVE")


def test_guard_rejects_non_bracket_or_invalid_stops_or_low_rr() -> None:
    settings = EngineSettings()
    guard = OrderValidationGuard(settings)
    portfolio = _default_portfolio()

    # 1. Non-bracket order class
    naked_order = ProposedBracketOrder(
        ticker="AMD",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        client_order_id="AMD_20260504_neg_overreaction",
        order_class="SIMPLE",
        qty=10,
        entry_price=100.0,
        stop_loss_price=95.0,
        take_profit_price=115.0,
    )
    with pytest.raises(ValueError, match="BRACKET_ORDER_REQUIRED"):
        guard.validate_order(naked_order, portfolio, days_to_earnings=10, llm_veto="APPROVE")

    # 2. Invalid stop loss (>= entry)
    bad_stop = ProposedBracketOrder(
        ticker="AMD",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        client_order_id="AMD_20260504_neg_overreaction",
        order_class="BRACKET",
        qty=10,
        entry_price=100.0,
        stop_loss_price=101.0,
        take_profit_price=115.0,
    )
    with pytest.raises(ValueError, match="INVALID_BRACKET_PRICES"):
        guard.validate_order(bad_stop, portfolio, days_to_earnings=10, llm_veto="APPROVE")

    # 3. Insufficient Reward:Risk ratio (< 2.0)
    low_rr = ProposedBracketOrder(
        ticker="AMD",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        client_order_id="AMD_20260504_neg_overreaction",
        order_class="BRACKET",
        qty=10,
        entry_price=100.0,
        stop_loss_price=95.0,
        take_profit_price=104.0,  # +4 vs -5 -> R:R = 0.8 < 2.0
    )
    with pytest.raises(ValueError, match="INSUFFICIENT_REWARD_RISK_RATIO"):
        guard.validate_order(low_rr, portfolio, days_to_earnings=10, llm_veto="APPROVE")


def test_guard_rejects_earnings_blackout_and_llm_veto_and_kill_switch() -> None:
    settings = EngineSettings()
    guard = OrderValidationGuard(settings)
    order = build_volatility_sized_bracket_order(
        ticker="META",
        signal_date=date(2026, 5, 4),
        strategy_name="sentiment_infl",
        entry_price=100.0,
        atr_14=2.0,
        total_equity=100_000.0,
        settings=settings,
    )

    # 1. LLM Veto
    with pytest.raises(ValueError, match="LLM_VETO_ACTIVE"):
        guard.validate_order(order, _default_portfolio(), days_to_earnings=10, llm_veto="VETO")

    # 2. Earnings Blackout (<= 3 days)
    with pytest.raises(ValueError, match="EARNINGS_BLACKOUT"):
        guard.validate_order(order, _default_portfolio(), days_to_earnings=3, llm_veto="APPROVE")

    # 3. Daily Loss Kill Switch (drawdown >= 1.5%)
    drawdown_portfolio = _default_portfolio(equity=98_000.0, start_of_day_equity=100_000.0)
    with pytest.raises(ValueError, match="KILL_SWITCH_DAILY_LOSS_EXCEEDED"):
        guard.validate_order(order, drawdown_portfolio, days_to_earnings=10, llm_veto="APPROVE")


def test_guard_rejects_position_portfolio_and_frequency_caps() -> None:
    settings = EngineSettings()
    guard = OrderValidationGuard(settings)

    # 1. Max risk per trade exceeded
    oversized_risk = ProposedBracketOrder(
        ticker="TSLA",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        client_order_id="TSLA_20260504_neg_overreaction",
        order_class="BRACKET",
        qty=70,  # 70 * $10 risk = $700 > $500 (0.5% of $100k)
        entry_price=100.0,
        stop_loss_price=90.0,
        take_profit_price=125.0,
    )
    with pytest.raises(ValueError, match="MAX_RISK_PER_TRADE_EXCEEDED"):
        guard.validate_order(
            oversized_risk, _default_portfolio(), days_to_earnings=10, llm_veto="APPROVE"
        )

    # 2. Max position notional exceeded
    oversized_notional = ProposedBracketOrder(
        ticker="TSLA",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        client_order_id="TSLA_20260504_neg_overreaction",
        order_class="BRACKET",
        qty=90,  # 90 * $100 = $9,000 > $8,000 (8% of $100k), risk = 90 * $1 = $90 <= $500
        entry_price=100.0,
        stop_loss_price=99.0,
        take_profit_price=105.0,
    )
    with pytest.raises(ValueError, match="MAX_POSITION_PCT_EXCEEDED"):
        guard.validate_order(
            oversized_notional, _default_portfolio(), days_to_earnings=10, llm_veto="APPROVE"
        )

    # 3. Max open positions cap (6)
    six_positions = {
        f"SYM{i}": HeldPosition(ticker=f"SYM{i}", qty=10, avg_entry_price=50.0, current_price=55.0)
        for i in range(6)
    }
    valid_order = build_volatility_sized_bracket_order(
        ticker="GOOG",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        entry_price=100.0,
        atr_14=2.5,
        total_equity=100_000.0,
        settings=settings,
    )
    with pytest.raises(ValueError, match="MAX_OPEN_POSITIONS_EXCEEDED"):
        guard.validate_order(
            valid_order,
            _default_portfolio(positions=six_positions),
            days_to_earnings=10,
            llm_veto="APPROVE",
        )

    # 4. Max portfolio exposure cap (40% = $40,000)
    heavy_positions = {
        "SYM1": HeldPosition(ticker="SYM1", qty=350, avg_entry_price=100.0, current_price=100.0)
    }
    with pytest.raises(ValueError, match="MAX_PORTFOLIO_EXPOSURE_EXCEEDED"):
        guard.validate_order(
            valid_order,  # adds $8,000 to $35,000 = $43,000 > $40,000
            _default_portfolio(positions=heavy_positions),
            days_to_earnings=10,
            llm_veto="APPROVE",
        )

    # 5. Max daily orders cap (2)
    with pytest.raises(ValueError, match="MAX_DAILY_ORDERS_EXCEEDED"):
        guard.validate_order(
            valid_order,
            _default_portfolio(orders_submitted_today=2),
            days_to_earnings=10,
            llm_veto="APPROVE",
        )

    # 6. Duplicate client_order_id idempotency block
    with pytest.raises(ValueError, match="DUPLICATE_CLIENT_ORDER_ID"):
        guard.validate_order(
            valid_order,
            _default_portfolio(existing_client_order_ids={valid_order.client_order_id}),
            days_to_earnings=10,
            llm_veto="APPROVE",
        )

    # 7. Malformed client_order_id
    bad_id_order = ProposedBracketOrder(
        ticker="GOOG",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        client_order_id="wrong_format_id",
        order_class="BRACKET",
        qty=20,
        entry_price=100.0,
        stop_loss_price=95.0,
        take_profit_price=110.0,
    )
    with pytest.raises(ValueError, match="INVALID_CLIENT_ORDER_ID"):
        guard.validate_order(
            bad_id_order, _default_portfolio(), days_to_earnings=10, llm_veto="APPROVE"
        )

    # 8. Valid pattern but mismatched ticker/date in client_order_id
    mismatched_id_order = ProposedBracketOrder(
        ticker="GOOG",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        client_order_id="MSFT_20260504_neg_overreaction",
        order_class="BRACKET",
        qty=20,
        entry_price=100.0,
        stop_loss_price=95.0,
        take_profit_price=110.0,
    )
    with pytest.raises(ValueError, match="Expected 'GOOG_20260504_neg_overreaction'"):
        guard.validate_order(
            mismatched_id_order, _default_portfolio(), days_to_earnings=10, llm_veto="APPROVE"
        )


def test_rejects_when_open_entry_order_exists() -> None:
    settings = EngineSettings()
    guard = OrderValidationGuard(settings)
    valid_order = build_volatility_sized_bracket_order(
        ticker="AAPL",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        entry_price=100.0,
        atr_14=2.5,
        total_equity=100_000.0,
        settings=settings,
    )
    portfolio = _default_portfolio()
    object.__setattr__(portfolio, "open_entry_order_tickers", {"AAPL"})

    with pytest.raises(ValueError, match="OPEN_ENTRY_ORDER_EXISTS"):
        guard.validate_order(valid_order, portfolio, days_to_earnings=10, llm_veto="APPROVE")


def test_rejects_held_ticker_with_stale_or_invalid_price() -> None:
    with pytest.raises(ValueError, match="greater than 0"):
        HeldPosition(ticker="AAPL", qty=10, avg_entry_price=100.0, current_price=-5.0)


def test_invalid_or_insufficient_atr_rejects() -> None:
    settings = EngineSettings()
    with pytest.raises(ValueError, match="strictly positive"):
        build_volatility_sized_bracket_order(
            ticker="AAPL",
            signal_date=date(2026, 5, 4),
            strategy_name="neg_overreaction",
            entry_price=100.0,
            atr_14=float("nan"),
            total_equity=100_000.0,
            settings=settings,
        )

    with pytest.raises(ValueError, match="strictly positive"):
        build_volatility_sized_bracket_order(
            ticker="AAPL",
            signal_date=date(2026, 5, 4),
            strategy_name="neg_overreaction",
            entry_price=100.0,
            atr_14=0.0,
            total_equity=100_000.0,
            settings=settings,
        )


def test_unknown_earnings_date_rejects() -> None:
    # C-RISK-07 / D-04: Unknown or missing earnings date must reject (fail closed)
    settings = EngineSettings()
    guard = OrderValidationGuard(settings)
    valid_order = build_volatility_sized_bracket_order(
        ticker="AAPL",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        entry_price=100.0,
        atr_14=2.5,
        total_equity=100_000.0,
        settings=settings,
    )
    with pytest.raises(ValueError, match="EARNINGS_BLACKOUT"):
        guard.validate_order(
            valid_order, _default_portfolio(), days_to_earnings=None, llm_veto="APPROVE"
        )


def test_blackout_boundary_sessions_3_and_4() -> None:
    settings = EngineSettings()
    guard = OrderValidationGuard(settings)
    valid_order = build_volatility_sized_bracket_order(
        ticker="AAPL",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        entry_price=100.0,
        atr_14=2.5,
        total_equity=100_000.0,
        settings=settings,
    )
    # Session 3 is inside blackout -> must reject
    with pytest.raises(ValueError, match="EARNINGS_BLACKOUT"):
        guard.validate_order(
            valid_order, _default_portfolio(), days_to_earnings=3, llm_veto="APPROVE"
        )

    # Session 4 is outside blackout -> must pass
    validated = guard.validate_order(
        valid_order, _default_portfolio(), days_to_earnings=4, llm_veto="APPROVE"
    )
    assert validated.guard_status == "PASSED"


def test_client_order_id_format_and_strategy_tokens() -> None:
    settings = EngineSettings()
    guard = OrderValidationGuard(settings)

    # Allowed strategy tokens: neg_overreaction, narrative_div, sentiment_infl, contagion (D-07)
    for strat in ("neg_overreaction", "narrative_div", "sentiment_infl", "contagion"):
        order = build_volatility_sized_bracket_order(
            ticker="AAPL",
            signal_date=date(2026, 5, 4),
            strategy_name=strat,
            entry_price=100.0,
            atr_14=2.5,
            total_equity=100_000.0,
            settings=settings,
        )
        validated = guard.validate_order(
            order, _default_portfolio(), days_to_earnings=10, llm_veto="APPROVE"
        )
        assert validated.strategy_name == strat

    invalid_strat_order = ProposedBracketOrder(
        ticker="AAPL",
        signal_date=date(2026, 5, 4),
        strategy_name="random_strategy",
        client_order_id="AAPL_20260504_random_strategy",
        order_class="BRACKET",
        qty=10,
        entry_price=100.0,
        stop_loss_price=95.0,
        take_profit_price=110.0,
    )
    # Invalid strategy token must reject
    with pytest.raises(ValueError, match="INVALID_CLIENT_ORDER_ID"):
        guard.validate_order(
            invalid_strat_order, _default_portfolio(), days_to_earnings=10, llm_veto="APPROVE"
        )


def test_kill_switch_latches_for_session() -> None:
    # C-RISK-10 / D-05: Once daily loss limit reached or kill_switch_latched=True, stays latched
    settings = EngineSettings()
    guard = OrderValidationGuard(settings)
    valid_order = build_volatility_sized_bracket_order(
        ticker="AAPL",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        entry_price=100.0,
        atr_14=2.5,
        total_equity=100_000.0,
        settings=settings,
    )
    portfolio = _default_portfolio()
    object.__setattr__(portfolio, "kill_switch_latched", True)

    with pytest.raises(ValueError, match="KILL_SWITCH_ENGAGED"):
        guard.validate_order(valid_order, portfolio, days_to_earnings=10, llm_veto="APPROVE")


def test_missing_equity_blocks() -> None:
    # C-RISK-10: Missing or non-positive equity blocks orders
    with pytest.raises((ValueError, Exception)):
        PortfolioState(total_equity=0.0, start_of_day_equity=100_000.0)
    with pytest.raises((ValueError, Exception)):
        PortfolioState(total_equity=-1000.0, start_of_day_equity=100_000.0)

