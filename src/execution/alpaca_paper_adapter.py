from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from src.config import PAPER_ALPACA_URL, EngineSettings
from src.risk.guard import ValidatedOrderIntent


class BrokerClientProtocol(Protocol):
    def get_order_by_client_order_id(self, client_order_id: str) -> dict[str, Any] | None: ...

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
    ) -> dict[str, Any]: ...


class ExecutionAuditRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    client_order_id: str
    broker_order_id: str | None = None
    ticker: str
    execution_mode: Literal["research", "paper"]
    order_class: Literal["BRACKET"] = "BRACKET"
    qty: int
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    status: Literal[
        "SHADOW_LOGGED",
        "SUBMITTED",
        "ALREADY_EXISTS_IDEMPOTENT",
        "RECONCILED_AFTER_TIMEOUT",
        "FAILED_CLOSED",
    ]
    executed_at: datetime


class AlpacaPaperExecutionRouter:
    """
    Safe Paper Execution Adapter (`AGENTS.md` Section 7 & `.agents/skills/paper-trading-safety`).
    - Default mode is `research` (shadow portfolio only).
    - `live` mode or non-paper URL raises `RuntimeError`.
    - Enforces atomic `OrderClass.BRACKET` (OCO) and idempotent `client_order_id` reconciliation.
    """

    def __init__(
        self,
        settings: EngineSettings,
        broker_client: BrokerClientProtocol | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if settings.execution_mode == "live":
            raise RuntimeError("LIVE execution mode is strictly prohibited.")
        if settings.alpaca_paper_api_url.rstrip("/") != PAPER_ALPACA_URL:
            raise RuntimeError(
                f"Invalid Alpaca endpoint '{settings.alpaca_paper_api_url}'. "
                f"Only '{PAPER_ALPACA_URL}' is permitted."
            )
        self.settings = settings
        self.broker_client = broker_client
        self.clock = clock or (lambda: datetime(2026, 5, 4, 14, 0, 0, tzinfo=UTC))
        self.audit_log: list[ExecutionAuditRecord] = []

    def route_order(self, intent: ValidatedOrderIntent) -> ExecutionAuditRecord:
        intent.verify_guard_token()
        if intent.guard_status != "PASSED" or intent.order_class != "BRACKET":
            raise ValueError(
                "Only ValidatedOrderIntent with guard_status='PASSED' and BRACKET allowed."
            )

        now_ts = self.clock()

        # 1. RESEARCH mode (or submission disabled): record hypothetical shadow trade only
        if self.settings.execution_mode == "research" or not self.settings.enable_order_submission:
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

        if self.broker_client is None:
            raise RuntimeError("Paper broker client is required when execution_mode='paper'.")

        # 2. Pre-submission idempotency lookup by deterministic client_order_id
        existing = self.broker_client.get_order_by_client_order_id(intent.client_order_id)
        if existing is not None:
            idempotent_record = ExecutionAuditRecord(
                client_order_id=intent.client_order_id,
                broker_order_id=str(existing.get("broker_order_id", "")),
                ticker=intent.ticker,
                execution_mode="paper",
                order_class="BRACKET",
                qty=intent.qty,
                entry_price=intent.entry_price,
                stop_loss_price=intent.stop_loss_price,
                take_profit_price=intent.take_profit_price,
                status="ALREADY_EXISTS_IDEMPOTENT",
                executed_at=now_ts,
            )
            self.audit_log.append(idempotent_record)
            return idempotent_record

        # 3. Atomic Bracket Order (OCO) submission with timeout reconciliation
        try:
            resp = self.broker_client.submit_bracket_order(
                symbol=intent.ticker,
                qty=intent.qty,
                side="buy",
                order_class="BRACKET",
                limit_price=intent.entry_price,
                stop_loss_price=intent.stop_loss_price,
                take_profit_price=intent.take_profit_price,
                client_order_id=intent.client_order_id,
            )
            submitted_record = ExecutionAuditRecord(
                client_order_id=intent.client_order_id,
                broker_order_id=str(resp.get("broker_order_id", "")),
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
        except TimeoutError:
            # Never blind-retry on timeout: query broker state by client_order_id first!
            reconciled = self.broker_client.get_order_by_client_order_id(intent.client_order_id)
            if reconciled is not None:
                rec_record = ExecutionAuditRecord(
                    client_order_id=intent.client_order_id,
                    broker_order_id=str(reconciled.get("broker_order_id", "")),
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
