import itertools
from datetime import date
import pytest

from src.config import EngineSettings
from src.risk.guard import (
    HeldPosition,
    OrderValidationGuard,
    PortfolioState,
    ProposedBracketOrder,
    format_client_order_id,
)
from src.risk.sizing import build_volatility_sized_bracket_order


def test_sizing_invariants_across_grid() -> None:
    settings = EngineSettings()
    signal_date = date(2026, 3, 30)

    entry_prices = [10.0, 15.25, 50.0, 100.0, 250.75, 500.0, 1200.0]
    atr_fractions = [0.015, 0.03, 0.05, 0.08, 0.12]
    equities = [25_000.0, 50_000.0, 100_000.0, 500_000.0, 1_000_000.0]

    for entry_price, atr_fraction, total_equity in itertools.product(
        entry_prices, atr_fractions, equities
    ):
        atr_14 = entry_price * atr_fraction
        try:
            order = build_volatility_sized_bracket_order(
                ticker="AAPL",
                signal_date=signal_date,
                strategy_name="neg_overreaction",
                entry_price=entry_price,
                atr_14=atr_14,
                total_equity=total_equity,
                settings=settings,
            )
        except ValueError:
            continue

        # Invariant 1: Strictly positive integer shares
        assert isinstance(order.qty, int)
        assert order.qty >= 1

        # Invariant 2: Ordered bracket prices
        assert 0.0 < order.stop_loss_price < order.entry_price < order.take_profit_price

        # Invariant 3: Dollar risk within cap (+0.01 tick tolerance)
        risk_dollars = (order.entry_price - order.stop_loss_price) * order.qty
        max_risk_allowed = total_equity * settings.max_risk_per_trade_pct
        assert risk_dollars <= max_risk_allowed + 0.01

        # Invariant 4: Notional within position cap (+0.01 tick tolerance)
        notional = order.entry_price * order.qty
        max_notional_allowed = total_equity * settings.max_position_pct
        assert notional <= max_notional_allowed + 0.01

        # Invariant 5: Minimum reward:risk ratio preserved
        reward_risk = (order.take_profit_price - order.entry_price) / (
            order.entry_price - order.stop_loss_price
        )
        assert reward_risk >= settings.min_reward_risk_ratio - 1e-4


def test_guard_never_averages_down_across_grid() -> None:
    settings = EngineSettings()
    guard = OrderValidationGuard(settings=settings)
    signal_date = date(2026, 3, 30)

    loss_percentages = [0.001, 0.01, 0.05, 0.15, 0.40]
    avg_prices = [15.0, 45.0, 120.0, 300.0]

    for loss_pct, avg_price in itertools.product(loss_percentages, avg_prices):
        current_price = round(avg_price * (1.0 - loss_pct), 2)
        portfolio = PortfolioState(
            total_equity=100_000.0,
            start_of_day_equity=100_000.0,
            open_positions={
                "XYZ": HeldPosition(
                    ticker="XYZ",
                    qty=100,
                    avg_entry_price=avg_price,
                    current_price=current_price,
                )
            },
        )

        order = ProposedBracketOrder(
            client_order_id=format_client_order_id("XYZ", signal_date, "neg_overreaction"),
            ticker="XYZ",
            signal_date=signal_date,
            strategy_name="neg_overreaction",
            qty=10,
            entry_price=current_price,
            stop_loss_price=round(current_price * 0.95, 2),
            take_profit_price=round(current_price * 1.10, 2),
        )

        with pytest.raises(ValueError, match="is currently held at an unrealized loss"):
            guard.validate_order(
                order=order,
                portfolio=portfolio,
                days_to_earnings=10,
            )
