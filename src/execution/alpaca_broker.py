from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)

from src.config import PAPER_ALPACA_URL, EngineSettings
from src.execution.alpaca_paper_adapter import ExecutionAuditRecord
from src.risk.guard import (
    HeldPosition,
    OrderValidationGuard,
    PortfolioState,
    ProposedBracketOrder,
    ValidatedOrderIntent,
)
from src.risk.sizing import (
    build_forensic_short_bracket_order,
    build_volatility_sized_bracket_order,
)

NY_TZ = ZoneInfo("America/New_York")


class AlpacaTradingClientProtocol(Protocol):
    _base_url: object

    def get_account(self) -> object: ...
    def get_all_positions(self) -> Sequence[object]: ...
    def get_orders(self, filter: GetOrdersRequest | None = None) -> Sequence[object]: ...
    def get_order_by_client_id(self, client_order_id: str) -> object: ...
    def submit_order(self, order_data: LimitOrderRequest) -> object: ...


class AlpacaPaperBrokerAdapter:
    """
    Production-hardened Alpaca Paper Trading Adapter (`src/execution/alpaca_broker.py`).
    Connects `alpaca-py` (`TradingClient(paper=True)`) to `OrderValidationGuard` (`src/risk/`).

    Safety Invariants:
    1. `paper=True` is hardcoded; `LIVE` mode or any URL != `https://paper-api.alpaca.markets`
       raises `RuntimeError`.
    2. Default mode is `RESEARCH` (shadow log only); requires `execution_mode == 'paper'` AND
       `enable_order_submission == True` to transmit orders.
    3. Synchronizes current broker equity, open positions, and today's orders before every check.
    4. Enforces all deterministic Python risk controls via `OrderValidationGuard`:
       No Averaging Down, `OrderClass.BRACKET` OCO with `stop_loss` & `take_profit`,
       volatility risk/notional caps, portfolio/position/daily caps, and daily loss kill switch.
    5. Enforces deterministic `client_order_id` idempotency before submission and reconciles status
       on network timeout without duplicate order transmission.
    """

    def __init__(
        self,
        settings: EngineSettings,
        trading_client: AlpacaTradingClientProtocol | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if settings.execution_mode == "live":
            raise RuntimeError("LIVE execution mode is strictly prohibited.")

        clean_configured_url = settings.alpaca_paper_api_url.rstrip("/")
        if clean_configured_url != PAPER_ALPACA_URL:
            raise RuntimeError(
                f"Invalid Alpaca endpoint '{settings.alpaca_paper_api_url}'. "
                f"Only '{PAPER_ALPACA_URL}' is permitted."
            )

        self.settings = settings
        self.clock = clock or (lambda: datetime(2026, 5, 4, 14, 0, 0, tzinfo=UTC))
        self.guard = OrderValidationGuard(settings=settings)
        self.kill_switch_latched: bool = False
        self.audit_log: list[ExecutionAuditRecord] = []

        if trading_client is not None:
            self.trading_client: AlpacaTradingClientProtocol = trading_client
        else:
            # Hardcode paper=True and url_override=PAPER_ALPACA_URL
            self.trading_client = TradingClient(
                api_key=settings.alpaca_api_key or "PAPER_PLACEHOLDER_KEY",
                secret_key=settings.alpaca_secret_key or "PAPER_PLACEHOLDER_SECRET",
                paper=True,
                url_override=PAPER_ALPACA_URL,
            )

        self._assert_client_paper_url()

    def _assert_client_paper_url(self) -> None:
        raw_base = getattr(self.trading_client, "_base_url", None)
        base_url_str = str(getattr(raw_base, "value", raw_base or "")).rstrip("/")
        if base_url_str != PAPER_ALPACA_URL:
            raise RuntimeError(
                f"TradingClient base URL '{base_url_str}' does not match mandatory "
                f"paper endpoint '{PAPER_ALPACA_URL}'."
            )

    def sync_portfolio_state(self, session_date: date | None = None) -> PortfolioState:
        """
        Fetch live account equity, open positions, and today's orders from Alpaca Paper
        to construct an authoritative point-in-time `PortfolioState`.
        """
        self._assert_client_paper_url()
        target_date = session_date or self.clock().astimezone(NY_TZ).date()

        account = self.trading_client.get_account()
        total_equity = float(getattr(account, "equity", 0.0) or 0.0)
        start_of_day_equity = float(getattr(account, "last_equity", 0.0) or 0.0)
        if total_equity <= 0.0 or start_of_day_equity <= 0.0:
            raise ValueError(
                f"INVALID_ACCOUNT_EQUITY: equity={total_equity}, last_equity={start_of_day_equity}"
            )

        raw_positions = self.trading_client.get_all_positions() or []
        open_positions: dict[str, HeldPosition] = {}
        for pos in raw_positions:
            sym = str(getattr(pos, "symbol", "")).upper()
            qty = abs(int(float(getattr(pos, "qty", 0))))
            avg_entry = float(getattr(pos, "avg_entry_price", 0.0) or 0.0)
            curr_price = float(getattr(pos, "current_price", 0.0) or 0.0)
            open_positions[sym] = HeldPosition(
                ticker=sym,
                qty=qty,
                avg_entry_price=avg_entry,
                current_price=curr_price,
            )

        orders_req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500)
        raw_orders = self.trading_client.get_orders(filter=orders_req) or []

        open_entry_tickers: set[str] = set()
        existing_client_ids: set[str] = set()
        orders_submitted_today = 0

        open_statuses = {
            "new",
            "accepted",
            "partially_filled",
            "pending_new",
            "accepted_for_bidding",
            "held",
        }
        date_token = target_date.strftime("%Y%m%d")

        for ord_obj in raw_orders:
            c_id = str(getattr(ord_obj, "client_order_id", "") or "")
            existing_client_ids.add(c_id)

            sym = str(getattr(ord_obj, "symbol", "") or "").upper()
            side = str(getattr(ord_obj, "side", "") or "").lower()
            status = str(getattr(ord_obj, "status", "") or "").lower()
            parent_id = getattr(ord_obj, "parent_order_id", None)

            is_buy = "buy" in side
            if is_buy and status in open_statuses:
                open_entry_tickers.add(sym)

            # Count root entry orders submitted on target NY session date
            submitted_at = getattr(ord_obj, "submitted_at", None)
            if isinstance(submitted_at, datetime):
                submitted_today = submitted_at.astimezone(NY_TZ).date() == target_date
            else:
                submitted_today = f"_{date_token}_" in c_id

            if is_buy and parent_id is None and submitted_today and status != "canceled":
                orders_submitted_today += 1

        state = PortfolioState(
            total_equity=total_equity,
            start_of_day_equity=start_of_day_equity,
            open_positions=open_positions,
            open_entry_order_tickers=open_entry_tickers,
            kill_switch_latched=self.kill_switch_latched,
            orders_submitted_today=orders_submitted_today,
            existing_client_order_ids=existing_client_ids,
        )

        if state.daily_drawdown_pct >= self.settings.max_daily_loss_pct:
            self.kill_switch_latched = True

        return state

    def _lookup_existing_order_by_client_id(self, client_order_id: str) -> object | None:
        try:
            return self.trading_client.get_order_by_client_id(client_order_id=client_order_id)
        except Exception:
            return None

    def validate_and_submit_order(
        self,
        proposed_order: ProposedBracketOrder,
        days_to_earnings: int | None,
        llm_veto: Literal["APPROVE", "VETO"] = "APPROVE",
    ) -> ExecutionAuditRecord:
        """
        Synchronize broker state, run deterministic `OrderValidationGuard`, and submit
        an atomic `OrderClass.BRACKET` order (or record a shadow trade in `RESEARCH` mode).
        """
        self._assert_client_paper_url()
        now_ts = self.clock()

        # 1. Pre-check existing order at broker by deterministic client_order_id (idempotency)
        if self.settings.execution_mode == "paper" and self.settings.enable_order_submission:
            existing_order = self._lookup_existing_order_by_client_id(
                proposed_order.client_order_id
            )
            if existing_order is not None:
                idem_record = ExecutionAuditRecord(
                    client_order_id=proposed_order.client_order_id,
                    broker_order_id=str(getattr(existing_order, "id", "")),
                    ticker=proposed_order.ticker,
                    execution_mode="paper",
                    order_class="BRACKET",
                    qty=proposed_order.qty,
                    entry_price=proposed_order.entry_price,
                    stop_loss_price=proposed_order.stop_loss_price,
                    take_profit_price=proposed_order.take_profit_price,
                    status="ALREADY_EXISTS_IDEMPOTENT",
                    executed_at=now_ts,
                )
                self.audit_log.append(idem_record)
                return idem_record

        # 2. Synchronize current broker portfolio state
        portfolio_state = self.sync_portfolio_state(session_date=proposed_order.signal_date)

        # 3. Run deterministic Python OrderValidationGuard (raises ValueError on any violation)
        intent: ValidatedOrderIntent = self.guard.validate_order(
            order=proposed_order,
            portfolio=portfolio_state,
            days_to_earnings=days_to_earnings,
            llm_veto=llm_veto,
        )
        intent.verify_guard_token()

        # 4. RESEARCH mode or submission disabled -> log shadow trade without calling submit_order
        if (
            self.settings.execution_mode == "research"
            or not self.settings.enable_order_submission
        ):
            shadow_record = ExecutionAuditRecord(
                client_order_id=intent.client_order_id,
                broker_order_id=None,
                ticker=intent.ticker,
                execution_mode="research",
                order_class="BRACKET",
                qty=intent.qty,
                entry_price=intent.entry_price,
                stop_loss_price=intent.stop_loss_price,
                take_profit_price=intent.take_profit_price,
                status="SHADOW_LOGGED",
                executed_at=now_ts,
            )
            self.audit_log.append(shadow_record)
            return shadow_record

        # 5. Construct atomic OrderClass.BRACKET (OCO) request via alpaca-py
        alpaca_side = OrderSide.SELL if intent.side == "sell" else OrderSide.BUY
        bracket_request = LimitOrderRequest(
            symbol=intent.ticker,
            qty=intent.qty,
            side=alpaca_side,
            type="limit",
            time_in_force=TimeInForce.DAY,
            limit_price=intent.entry_price,
            order_class=OrderClass.BRACKET,
            client_order_id=intent.client_order_id,
            take_profit=TakeProfitRequest(limit_price=intent.take_profit_price),
            stop_loss=StopLossRequest(stop_price=intent.stop_loss_price),
        )

        try:
            broker_resp = self.trading_client.submit_order(order_data=bracket_request)
            submitted_record = ExecutionAuditRecord(
                client_order_id=intent.client_order_id,
                broker_order_id=str(getattr(broker_resp, "id", "")),
                ticker=intent.ticker,
                execution_mode="paper",
                order_class="BRACKET",
                qty=intent.qty,
                entry_price=intent.entry_price,
                stop_loss_price=intent.stop_loss_price,
                take_profit_price=intent.take_profit_price,
                status="SUBMITTED",
                executed_at=now_ts,
            )
            self.audit_log.append(submitted_record)
            return submitted_record
        except Exception as exc:
            is_timeout = (
                isinstance(exc, TimeoutError)
                or "timeout" in type(exc).__name__.lower()
                or "timeout" in str(exc).lower()
                or "timed out" in str(exc).lower()
            )
            if not is_timeout:
                raise
            # Never blind-retry on timeout: query broker by client_order_id first!
            reconciled = self._lookup_existing_order_by_client_id(intent.client_order_id)
            if reconciled is not None:
                rec_record = ExecutionAuditRecord(
                    client_order_id=intent.client_order_id,
                    broker_order_id=str(getattr(reconciled, "id", "")),
                    ticker=intent.ticker,
                    execution_mode="paper",
                    order_class="BRACKET",
                    qty=intent.qty,
                    entry_price=intent.entry_price,
                    stop_loss_price=intent.stop_loss_price,
                    take_profit_price=intent.take_profit_price,
                    status="RECONCILED_AFTER_TIMEOUT",
                    executed_at=now_ts,
                )
                self.audit_log.append(rec_record)
                return rec_record

            failed_record = ExecutionAuditRecord(
                client_order_id=intent.client_order_id,
                broker_order_id=None,
                ticker=intent.ticker,
                execution_mode="paper",
                order_class="BRACKET",
                qty=intent.qty,
                entry_price=intent.entry_price,
                stop_loss_price=intent.stop_loss_price,
                take_profit_price=intent.take_profit_price,
                status="FAILED_CLOSED",
                executed_at=now_ts,
            )
            self.audit_log.append(failed_record)
            return failed_record

    def size_validate_and_submit(
        self,
        ticker: str,
        signal_date: date,
        strategy_name: str,
        entry_price: float,
        atr_14: float,
        days_to_earnings: int | None,
        llm_veto: Literal["APPROVE", "VETO"] = "APPROVE",
        direction: Literal["LONG", "SHORT"] = "LONG",
    ) -> ExecutionAuditRecord:
        """
        Synchronize equity, compute volatility-adjusted ATR Bracket order size in pure Python,
        validate against all `OrderValidationGuard` rules, and route to Alpaca Paper.
        """
        portfolio_state = self.sync_portfolio_state(session_date=signal_date)
        sizer = (
            build_forensic_short_bracket_order
            if direction == "SHORT"
            else build_volatility_sized_bracket_order
        )
        proposed_order = sizer(
            ticker=ticker,
            signal_date=signal_date,
            strategy_name=strategy_name,
            entry_price=entry_price,
            atr_14=atr_14,
            total_equity=portfolio_state.total_equity,
            settings=self.settings,
        )
        return self.validate_and_submit_order(
            proposed_order=proposed_order,
            days_to_earnings=days_to_earnings,
            llm_veto=llm_veto,
        )
