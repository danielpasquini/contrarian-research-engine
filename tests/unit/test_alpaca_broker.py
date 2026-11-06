from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.config import EngineSettings
from src.execution.alpaca_broker import AlpacaPaperBrokerAdapter
from src.risk.guard import ProposedBracketOrder, format_client_order_id


def _make_mock_trading_client(
    equity: float = 100_000.0,
    last_equity: float = 100_000.0,
    positions: list[SimpleNamespace] | None = None,
    orders: list[SimpleNamespace] | None = None,
    base_url: str = "https://paper-api.alpaca.markets",
) -> MagicMock:
    client = MagicMock()
    client._base_url = SimpleNamespace(value=base_url)
    client.get_account.return_value = SimpleNamespace(
        equity=str(equity),
        last_equity=str(last_equity),
        status="ACTIVE",
    )
    client.get_all_positions.return_value = positions or []
    client.get_orders.return_value = orders or []
    client.get_order_by_client_id.side_effect = Exception("Order not found")
    client.submit_order.return_value = SimpleNamespace(
        id="alpaca_broker_uuid_123",
        client_order_id="AAPL_20260504_neg_overreaction",
        status="accepted",
    )
    return client


def _valid_proposed_order(
    ticker: str = "AAPL",
    signal_date: date = date(2026, 5, 4),
    strategy: str = "neg_overreaction",
    qty: int = 40,
    entry_price: float = 180.0,
    stop_loss_price: float = 172.0,
    take_profit_price: float = 196.0,  # 16 / 8 = 2.0R
) -> ProposedBracketOrder:
    return ProposedBracketOrder(
        ticker=ticker,
        signal_date=signal_date,
        strategy_name=strategy,
        client_order_id=format_client_order_id(ticker, signal_date, strategy),
        order_class="BRACKET",
        qty=qty,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
    )


def test_hardcoded_paper_true_and_rejects_live_mode_or_non_paper_url() -> None:
    # 1. Attempting live mode in EngineSettings or adapter raises RuntimeError
    bad_settings = EngineSettings.model_construct(
        execution_mode="live",
        enable_order_submission=True,
        alpaca_paper_api_url="https://paper-api.alpaca.markets",
    )
    with pytest.raises(RuntimeError, match="LIVE execution mode is strictly prohibited"):
        AlpacaPaperBrokerAdapter(settings=bad_settings, trading_client=_make_mock_trading_client())

    # 2. Attempting live Alpaca URL in settings raises RuntimeError
    live_url_settings = EngineSettings.model_construct(
        execution_mode="paper",
        enable_order_submission=True,
        alpaca_paper_api_url="https://api.alpaca.markets",
    )
    with pytest.raises(
        RuntimeError, match=r"Only 'https://paper-api\.alpaca\.markets' is permitted"
    ):
        AlpacaPaperBrokerAdapter(
            settings=live_url_settings, trading_client=_make_mock_trading_client()
        )

    # 3. Attempting to inject a TradingClient pointing to live URL raises RuntimeError
    paper_settings = EngineSettings(execution_mode="paper", enable_order_submission=True)
    live_client = _make_mock_trading_client(base_url="https://api.alpaca.markets")
    with pytest.raises(RuntimeError, match="TradingClient base URL"):
        AlpacaPaperBrokerAdapter(settings=paper_settings, trading_client=live_client)

    # 4. Default SDK client construction enforces paper=True and https://paper-api.alpaca.markets
    default_settings = EngineSettings(execution_mode="research")
    adapter = AlpacaPaperBrokerAdapter(settings=default_settings)
    raw_base = adapter.trading_client._base_url
    base_url_val = str(getattr(raw_base, "value", raw_base))
    assert base_url_val.rstrip("/") == "https://paper-api.alpaca.markets"


def test_research_mode_and_disabled_submission_do_not_transmit_orders() -> None:
    client = _make_mock_trading_client()
    research_settings = EngineSettings(execution_mode="research", enable_order_submission=False)
    adapter = AlpacaPaperBrokerAdapter(settings=research_settings, trading_client=client)

    result = adapter.validate_and_submit_order(
        proposed_order=_valid_proposed_order(),
        days_to_earnings=10,
        llm_veto="APPROVE",
    )
    assert result.status == "SHADOW_LOGGED"
    assert result.execution_mode == "research"
    client.submit_order.assert_not_called()

    # Even if execution_mode="paper", if enable_order_submission=False -> shadow only
    paper_disabled = EngineSettings(execution_mode="paper", enable_order_submission=False)
    adapter2 = AlpacaPaperBrokerAdapter(settings=paper_disabled, trading_client=client)
    result2 = adapter2.validate_and_submit_order(
        proposed_order=_valid_proposed_order(),
        days_to_earnings=10,
        llm_veto="APPROVE",
    )
    assert result2.status == "SHADOW_LOGGED"
    client.submit_order.assert_not_called()


def test_sync_portfolio_state_and_submit_valid_atomic_bracket_order() -> None:
    client = _make_mock_trading_client(equity=100_000.0, last_equity=100_000.0)
    settings = EngineSettings(execution_mode="paper", enable_order_submission=True)
    adapter = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client)

    order = _valid_proposed_order(
        ticker="AAPL",
        qty=40,
        entry_price=180.0,
        stop_loss_price=172.0,
        take_profit_price=196.0,  # +16 / -8 = 2.0R
    )
    audit = adapter.validate_and_submit_order(
        proposed_order=order,
        days_to_earnings=15,
        llm_veto="APPROVE",
    )

    assert audit.status == "SUBMITTED"
    assert audit.broker_order_id == "alpaca_broker_uuid_123"
    assert audit.client_order_id == "AAPL_20260504_neg_overreaction"
    client.get_account.assert_called_once()
    client.get_all_positions.assert_called_once()
    client.get_orders.assert_called_once()
    client.submit_order.assert_called_once()

    submitted_req = client.submit_order.call_args.kwargs["order_data"]
    assert submitted_req.symbol == "AAPL"
    assert submitted_req.qty == 40
    assert str(submitted_req.side.value) == "buy"
    assert str(submitted_req.order_class.value) == "bracket"
    assert str(submitted_req.time_in_force.value) == "day"
    assert submitted_req.limit_price == 180.0
    assert submitted_req.stop_loss.stop_price == 172.0
    assert submitted_req.take_profit.limit_price == 196.0
    assert submitted_req.client_order_id == "AAPL_20260504_neg_overreaction"


def test_size_and_submit_from_atr_signal_end_to_end() -> None:
    client = _make_mock_trading_client(equity=100_000.0, last_equity=100_000.0)
    settings = EngineSettings(
        execution_mode="paper",
        enable_order_submission=True,
        min_reward_risk_ratio=2.0,
    )
    adapter = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client)

    audit = adapter.size_validate_and_submit(
        ticker="MSFT",
        signal_date=date(2026, 5, 4),
        strategy_name="narrative_div",
        entry_price=400.0,
        atr_14=5.0,  # stop = 390.0 (-10), tp = 420.0 (+20 = 2.0R)
        days_to_earnings=12,
        llm_veto="APPROVE",
    )
    assert audit.status == "SUBMITTED"
    assert audit.stop_loss_price == 390.0
    assert audit.take_profit_price == 420.0
    assert audit.qty == 20
    client.submit_order.assert_called_once()


def test_blocks_averaging_down_on_losing_position() -> None:
    losing_position = SimpleNamespace(
        symbol="AAPL",
        qty="20",
        avg_entry_price="190.00",
        current_price="180.00",  # Unrealized loss!
    )
    client = _make_mock_trading_client(positions=[losing_position])
    settings = EngineSettings(execution_mode="paper", enable_order_submission=True)
    adapter = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client)

    with pytest.raises(ValueError, match="AVERAGING_DOWN_PROHIBITED"):
        adapter.validate_and_submit_order(
            proposed_order=_valid_proposed_order(ticker="AAPL"),
            days_to_earnings=10,
        )
    client.submit_order.assert_not_called()


def test_blocks_naked_order_or_reward_risk_violation() -> None:
    client = _make_mock_trading_client()
    settings = EngineSettings(
        execution_mode="paper",
        enable_order_submission=True,
        min_reward_risk_ratio=2.0,
    )
    adapter = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client)

    # 1. Non-bracket order class rejected
    naked_order = ProposedBracketOrder(
        ticker="AAPL",
        signal_date=date(2026, 5, 4),
        strategy_name="neg_overreaction",
        client_order_id="AAPL_20260504_neg_overreaction",
        order_class="SIMPLE",
        qty=40,
        entry_price=180.0,
        stop_loss_price=172.0,
        take_profit_price=196.0,
    )
    with pytest.raises(ValueError, match="BRACKET_ORDER_REQUIRED"):
        adapter.validate_and_submit_order(proposed_order=naked_order, days_to_earnings=10)

    # 2. Reward:Risk < 2.0R rejected
    low_rr_order = _valid_proposed_order(
        entry_price=180.0,
        stop_loss_price=172.0,  # risk = 8
        take_profit_price=190.0,  # reward = 10 -> 1.25R < 2.0R
    )
    with pytest.raises(ValueError, match="INSUFFICIENT_REWARD_RISK_RATIO"):
        adapter.validate_and_submit_order(proposed_order=low_rr_order, days_to_earnings=10)

    client.submit_order.assert_not_called()


def test_blocks_risk_per_trade_and_position_notional_violations() -> None:
    client = _make_mock_trading_client(equity=100_000.0, last_equity=100_000.0)
    settings = EngineSettings(execution_mode="paper", enable_order_submission=True)
    adapter = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client)

    # 1. Risk per trade > 0.5% ($500): 40 shares * $15 stop distance = $600 > $500
    excess_risk_order = _valid_proposed_order(
        qty=40,
        entry_price=180.0,
        stop_loss_price=165.0,  # $15 risk * 40 = $600 > $500
        take_profit_price=210.0,
    )
    with pytest.raises(ValueError, match="MAX_RISK_PER_TRADE_EXCEEDED"):
        adapter.validate_and_submit_order(proposed_order=excess_risk_order, days_to_earnings=10)

    # 2. Notional > 8% ($8,000): 50 shares * $180 = $9,000 > $8,000 (with tight stop so risk < $500)
    excess_notional_order = _valid_proposed_order(
        qty=50,
        entry_price=180.0,
        stop_loss_price=175.0,  # $5 risk * 50 = $250 <= $500
        take_profit_price=190.0,
    )
    with pytest.raises(ValueError, match="MAX_POSITION_PCT_EXCEEDED"):
        adapter.validate_and_submit_order(proposed_order=excess_notional_order, days_to_earnings=10)

    client.submit_order.assert_not_called()


def test_blocks_portfolio_exposure_max_positions_and_daily_order_cap() -> None:
    settings = EngineSettings(execution_mode="paper", enable_order_submission=True)

    # 1. Max Portfolio Exposure (80% of $100k = $80k): holding $75k + new $7.2k = $82.2k > $80k
    big_positions = [
        SimpleNamespace(
            symbol=f"SYM{i}",
            qty="150",
            avg_entry_price="90.0",
            current_price="100.0",  # $15,000 each * 5 = $75,000
        )
        for i in range(5)
    ]
    client_exp = _make_mock_trading_client(positions=big_positions)
    adapter_exp = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client_exp)
    with pytest.raises(ValueError, match="MAX_PORTFOLIO_EXPOSURE_EXCEEDED"):
        adapter_exp.validate_and_submit_order(
            proposed_order=_valid_proposed_order(ticker="AAPL"),  # notional = $7,200
            days_to_earnings=10,
        )
    client_exp.submit_order.assert_not_called()

    # 2. Max Open Positions (10): currently holding 10 positions
    ten_positions = [
        SimpleNamespace(
            symbol=f"TKR{i}",
            qty="10",
            avg_entry_price="45.0",
            current_price="50.0",
        )
        for i in range(10)
    ]
    client_pos = _make_mock_trading_client(positions=ten_positions)
    adapter_pos = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client_pos)
    with pytest.raises(ValueError, match="MAX_OPEN_POSITIONS_EXCEEDED"):
        adapter_pos.validate_and_submit_order(
            proposed_order=_valid_proposed_order(ticker="NEW"),
            days_to_earnings=10,
        )
    client_pos.submit_order.assert_not_called()

    # 3. Max Daily Orders (3): 3 buy orders already submitted today (plus 1 sell leg ignored)
    todays_orders = [
        SimpleNamespace(
            id=f"ord_{i}",
            client_order_id=f"SYM{i}_20260504_neg_overreaction",
            symbol=f"SYM{i}",
            side="buy",
            status="filled",
            parent_order_id=None,
            submitted_at=datetime(2026, 5, 4, 14, 0, tzinfo=UTC),
        )
        for i in range(3)
    ] + [
        SimpleNamespace(
            id="ord_sell_leg",
            client_order_id="SELL_LEG_1",
            symbol="SYM0",
            side="sell",
            status="new",
            parent_order_id="ord_0",
            submitted_at=None,
        )
    ]
    client_freq = _make_mock_trading_client(orders=todays_orders)
    adapter_freq = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client_freq)
    with pytest.raises(ValueError, match="MAX_DAILY_ORDERS_EXCEEDED"):
        adapter_freq.validate_and_submit_order(
            proposed_order=_valid_proposed_order(ticker="AAPL"),
            days_to_earnings=10,
        )
    client_freq.submit_order.assert_not_called()


def test_blocks_open_entry_order_and_invalid_account_equity() -> None:
    settings = EngineSettings(execution_mode="paper", enable_order_submission=True)

    # 1. Open entry order exists for AAPL -> rejected
    open_orders = [
        SimpleNamespace(
            id="ord_open_1",
            client_order_id="OTHER_20260503_neg_overreaction",
            symbol="AAPL",
            side="buy",
            status="accepted",
            parent_order_id=None,
            submitted_at=None,
        )
    ]
    client_open = _make_mock_trading_client(orders=open_orders)
    adapter_open = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client_open)
    with pytest.raises(ValueError, match="OPEN_ENTRY_ORDER_EXISTS"):
        adapter_open.validate_and_submit_order(
            proposed_order=_valid_proposed_order(ticker="AAPL"),
            days_to_earnings=10,
        )
    client_open.submit_order.assert_not_called()

    # 2. Invalid/zero equity from broker -> rejected fail-closed
    client_zero_eq = _make_mock_trading_client(equity=0.0, last_equity=100_000.0)
    adapter_zero_eq = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client_zero_eq)
    with pytest.raises(ValueError, match="INVALID_ACCOUNT_EQUITY"):
        adapter_zero_eq.validate_and_submit_order(
            proposed_order=_valid_proposed_order(ticker="AAPL"),
            days_to_earnings=10,
        )
    client_zero_eq.submit_order.assert_not_called()


def test_blocks_daily_drawdown_kill_switch_and_latches_session() -> None:
    # Start of day equity = $100,000; current equity = $97,800 (-2.2% drawdown >= 2.0% limit)
    client = _make_mock_trading_client(equity=97_800.0, last_equity=100_000.0)
    settings = EngineSettings(execution_mode="paper", enable_order_submission=True)
    adapter = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client)

    with pytest.raises(ValueError, match="KILL_SWITCH_DAILY_LOSS_EXCEEDED"):
        adapter.validate_and_submit_order(
            proposed_order=_valid_proposed_order(),
            days_to_earnings=10,
        )
    assert adapter.kill_switch_latched is True
    client.submit_order.assert_not_called()

    # Even if equity rebounds later in the same session to $99,500, kill switch remains latched!
    client.get_account.return_value = SimpleNamespace(
        equity="99500.0", last_equity="100000.0", status="ACTIVE"
    )
    with pytest.raises(ValueError, match="KILL_SWITCH_ENGAGED"):
        adapter.validate_and_submit_order(
            proposed_order=_valid_proposed_order(),
            days_to_earnings=10,
        )
    client.submit_order.assert_not_called()


def test_blocks_earnings_blackout_and_llm_veto() -> None:
    client = _make_mock_trading_client()
    settings = EngineSettings(execution_mode="paper", enable_order_submission=True)
    adapter = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client)

    # 1. Earnings in 3 sessions -> rejected
    with pytest.raises(ValueError, match="EARNINGS_BLACKOUT"):
        adapter.validate_and_submit_order(
            proposed_order=_valid_proposed_order(),
            days_to_earnings=3,
            llm_veto="APPROVE",
        )

    # 2. Unknown earnings (None) -> rejected fail-closed
    with pytest.raises(ValueError, match="EARNINGS_BLACKOUT"):
        adapter.validate_and_submit_order(
            proposed_order=_valid_proposed_order(),
            days_to_earnings=None,
            llm_veto="APPROVE",
        )

    # 3. LLM Veto == "VETO" -> rejected
    with pytest.raises(ValueError, match="LLM_VETO_ACTIVE"):
        adapter.validate_and_submit_order(
            proposed_order=_valid_proposed_order(),
            days_to_earnings=10,
            llm_veto="VETO",
        )

    client.submit_order.assert_not_called()


def test_idempotency_precheck_and_timeout_reconciliation_never_duplicates() -> None:
    settings = EngineSettings(execution_mode="paper", enable_order_submission=True)

    # Case 1: Order already exists at broker when queried by client_order_id -> no duplicate submit
    client_existing = _make_mock_trading_client()
    client_existing.get_order_by_client_id.side_effect = None
    client_existing.get_order_by_client_id.return_value = SimpleNamespace(
        id="existing_alpaca_id_999",
        client_order_id="AAPL_20260504_neg_overreaction",
        status="accepted",
    )
    adapter_existing = AlpacaPaperBrokerAdapter(
        settings=settings, trading_client=client_existing
    )
    res_existing = adapter_existing.validate_and_submit_order(
        proposed_order=_valid_proposed_order(),
        days_to_earnings=10,
    )
    assert res_existing.status == "ALREADY_EXISTS_IDEMPOTENT"
    assert res_existing.broker_order_id == "existing_alpaca_id_999"
    client_existing.submit_order.assert_not_called()

    # Case 2: Network TimeoutError on submit_order -> reconciles via get_order_by_client_id
    client_timeout = _make_mock_trading_client()
    client_timeout.submit_order.side_effect = TimeoutError("Socket read timed out")
    client_timeout.get_order_by_client_id.side_effect = [
        Exception("Not found before submit"),
        SimpleNamespace(
            id="reconciled_alpaca_id_777",
            client_order_id="AAPL_20260504_neg_overreaction",
            status="accepted",
        ),
    ]
    adapter_timeout = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client_timeout)
    res_timeout = adapter_timeout.validate_and_submit_order(
        proposed_order=_valid_proposed_order(),
        days_to_earnings=10,
    )
    assert res_timeout.status == "RECONCILED_AFTER_TIMEOUT"
    assert res_timeout.broker_order_id == "reconciled_alpaca_id_777"
    assert client_timeout.submit_order.call_count == 1
    assert client_timeout.get_order_by_client_id.call_count == 2

    # Case 3: Network TimeoutError on submit_order AND order not found -> FAILED_CLOSED
    client_fail_closed = _make_mock_trading_client()
    client_fail_closed.submit_order.side_effect = TimeoutError("Socket read timed out")
    client_fail_closed.get_order_by_client_id.side_effect = Exception("Still not found")
    adapter_fail_closed = AlpacaPaperBrokerAdapter(
        settings=settings, trading_client=client_fail_closed
    )
    res_fail_closed = adapter_fail_closed.validate_and_submit_order(
        proposed_order=_valid_proposed_order(),
        days_to_earnings=10,
    )
    assert res_fail_closed.status == "FAILED_CLOSED"
    assert res_fail_closed.broker_order_id is None
    assert client_fail_closed.submit_order.call_count == 1


def test_custom_library_timeout_exceptions_trigger_reconciliation() -> None:
    """
    [HIGH-02]: Exceptions from requests/httpx with 'timeout' in class name or message
    (even when not inheriting from builtins.TimeoutError) must trigger reconciliation.
    """
    settings = EngineSettings(execution_mode="paper", enable_order_submission=True)

    class CustomReadTimeoutException(Exception):
        pass

    # 1. Exception with 'Timeout' in class name
    client_cls_to = _make_mock_trading_client()
    client_cls_to.submit_order.side_effect = CustomReadTimeoutException("Connection stalled")
    client_cls_to.get_order_by_client_id.side_effect = [
        Exception("Not found before submit"),
        SimpleNamespace(
            id="reconciled_from_cls_timeout",
            client_order_id="AAPL_20260504_neg_overreaction",
            status="accepted",
        ),
    ]
    adapter_cls_to = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client_cls_to)
    res_cls = adapter_cls_to.validate_and_submit_order(
        proposed_order=_valid_proposed_order(),
        days_to_earnings=10,
    )
    assert res_cls.status == "RECONCILED_AFTER_TIMEOUT"
    assert res_cls.broker_order_id == "reconciled_from_cls_timeout"

    # 2. Exception with 'timeout' / 'timed out' in message string
    client_msg_to = _make_mock_trading_client()
    client_msg_to.submit_order.side_effect = RuntimeError(
        "HTTPSConnectionPool: request timeout waiting for response"
    )
    client_msg_to.get_order_by_client_id.side_effect = [
        Exception("Not found before submit"),
        SimpleNamespace(
            id="reconciled_from_msg_timeout",
            client_order_id="AAPL_20260504_neg_overreaction",
            status="accepted",
        ),
    ]
    adapter_msg_to = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client_msg_to)
    res_msg = adapter_msg_to.validate_and_submit_order(
        proposed_order=_valid_proposed_order(),
        days_to_earnings=10,
    )
    assert res_msg.status == "RECONCILED_AFTER_TIMEOUT"
    assert res_msg.broker_order_id == "reconciled_from_msg_timeout"

    # 3. Non-timeout exception must still propagate
    client_other = _make_mock_trading_client()
    client_other.submit_order.side_effect = RuntimeError("401 Unauthorized API Key")
    adapter_other = AlpacaPaperBrokerAdapter(settings=settings, trading_client=client_other)
    with pytest.raises(RuntimeError, match="401 Unauthorized API Key"):
        adapter_other.validate_and_submit_order(
            proposed_order=_valid_proposed_order(),
            days_to_earnings=10,
        )
