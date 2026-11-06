from datetime import date
from typing import Any

from src.config import EngineSettings
from src.execution.alpaca_paper_adapter import AlpacaPaperExecutionRouter, BrokerClientProtocol
from src.risk.guard import (
    OrderValidationGuard,
    PortfolioState,
    ProposedBracketOrder,
    ValidatedOrderIntent,
)


class MockAlpacaPaperClient(BrokerClientProtocol):
    def __init__(self, simulate_timeout_on_first_submit: bool = False) -> None:
        self.orders_by_client_id: dict[str, dict[str, Any]] = {}
        self.submit_calls: int = 0
        self.lookup_calls: int = 0
        self.simulate_timeout_on_first_submit = simulate_timeout_on_first_submit

    def get_order_by_client_order_id(self, client_order_id: str) -> dict[str, Any] | None:
        self.lookup_calls += 1
        return self.orders_by_client_id.get(client_order_id)

    def submit_bracket_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_class: str,
        limit_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        client_order_id: str,
    ) -> dict[str, Any]:
        self.submit_calls += 1
        record = {
            "broker_order_id": f"alpaca_ord_{self.submit_calls}",
            "client_order_id": client_order_id,
            "symbol": symbol,
            "qty": qty,
            "order_class": order_class,
            "limit_price": limit_price,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            "status": "accepted",
        }
        # Even if HTTP response times out on the client side, the broker may have accepted it!
        self.orders_by_client_id[client_order_id] = record
        if self.simulate_timeout_on_first_submit and self.submit_calls == 1:
            raise TimeoutError("ReadTimeout waiting for Alpaca response")
        return record


def _sample_intent() -> ValidatedOrderIntent:
    guard = OrderValidationGuard(settings=EngineSettings())
    proposed = ProposedBracketOrder(
        ticker="AAPL",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        client_order_id="AAPL_20260504_neg_overreaction",
        order_class="BRACKET",
        qty=40,
        entry_price=180.0,
        stop_loss_price=172.0,
        take_profit_price=196.0,
    )
    portfolio = PortfolioState(total_equity=100_000.0, start_of_day_equity=100_000.0)
    return guard.validate_order(order=proposed, portfolio=portfolio, days_to_earnings=10)


def test_research_mode_records_shadow_trade_without_calling_broker() -> None:
    settings = EngineSettings(execution_mode="research", enable_order_submission=False)
    broker = MockAlpacaPaperClient()
    router = AlpacaPaperExecutionRouter(settings=settings, broker_client=broker)

    res = router.route_order(_sample_intent())
    assert res.execution_mode == "research"
    assert res.status == "SHADOW_LOGGED"
    assert broker.submit_calls == 0


def test_paper_mode_submits_atomic_bracket_order() -> None:
    settings = EngineSettings(execution_mode="paper", enable_order_submission=True)
    broker = MockAlpacaPaperClient()
    router = AlpacaPaperExecutionRouter(settings=settings, broker_client=broker)

    res = router.route_order(_sample_intent())
    assert res.execution_mode == "paper"
    assert res.status == "SUBMITTED"
    assert res.order_class == "BRACKET"
    assert broker.submit_calls == 1
    assert broker.lookup_calls == 1


def test_timeout_reconciles_by_client_order_id_without_duplicate_submit() -> None:
    """
    AC-08.1: Never assume a timed-out HTTP request means the order was rejected.
    Query Alpaca order status by `client_order_id` before any retry attempt.
    """
    settings = EngineSettings(execution_mode="paper", enable_order_submission=True)
    broker = MockAlpacaPaperClient(simulate_timeout_on_first_submit=True)
    router = AlpacaPaperExecutionRouter(settings=settings, broker_client=broker)

    res = router.route_order(_sample_intent())
    assert res.status == "RECONCILED_AFTER_TIMEOUT"
    assert res.broker_order_id == "alpaca_ord_1"
    # Critically: submit_bracket_order was called ONLY ONCE (no duplicate order!)
    assert broker.submit_calls == 1
    assert broker.lookup_calls == 2


def test_forged_validated_order_intent_rejected_without_guard() -> None:
    """
    [HIGH-01]: Direct instantiation of ValidatedOrderIntent(..., guard_status="PASSED")
    without passing through OrderValidationGuard.validate_order() must be rejected.
    """
    import pytest

    settings = EngineSettings(execution_mode="paper", enable_order_submission=True)
    broker = MockAlpacaPaperClient()
    router = AlpacaPaperExecutionRouter(settings=settings, broker_client=broker)

    forged_intent = ValidatedOrderIntent(
        ticker="AAPL",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        client_order_id="AAPL_20260504_neg_overreaction",
        order_class="BRACKET",
        qty=40,
        entry_price=180.0,
        stop_loss_price=172.0,
        take_profit_price=196.0,
        risk_dollars=320.0,
        notional_dollars=7200.0,
        guard_status="PASSED",
    )

    with pytest.raises(RuntimeError, match="UNFORGEABLE_GUARD_TOKEN"):
        forged_intent.verify_guard_token()

    with pytest.raises(RuntimeError, match="UNFORGEABLE_GUARD_TOKEN"):
        router.route_order(forged_intent)

    assert broker.submit_calls == 0
