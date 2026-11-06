import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from src.config import EngineSettings

_GUARD_CAPABILITY_TOKEN = object()

ALLOWED_STRATEGY_NAMES = {"neg_overreaction", "narrative_div", "sentiment_infl", "contagion"}
CLIENT_ORDER_ID_PATTERN = re.compile(
    r"^[A-Z][A-Z.]{0,9}_\d{8}_(neg_overreaction|narrative_div|sentiment_infl|contagion)$"
)


def format_client_order_id(ticker: str, signal_date: date, strategy_name: str) -> str:
    clean_ticker = ticker.upper()
    return f"{clean_ticker}_{signal_date.strftime('%Y%m%d')}_{strategy_name}"


class HeldPosition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    qty: int = Field(gt=0)
    avg_entry_price: float = Field(gt=0.0)
    current_price: float = Field(gt=0.0)

    @property
    def market_value(self) -> float:
        return self.qty * self.current_price

    @property
    def is_losing(self) -> bool:
        return self.current_price < self.avg_entry_price


class PortfolioState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total_equity: float = Field(gt=0.0)
    start_of_day_equity: float = Field(gt=0.0)
    open_positions: dict[str, HeldPosition] = Field(default_factory=dict)
    open_entry_order_tickers: set[str] = Field(default_factory=set)
    kill_switch_latched: bool = Field(default=False)
    orders_submitted_today: int = Field(default=0, ge=0)
    existing_client_order_ids: set[str] = Field(default_factory=set)

    @property
    def daily_drawdown_pct(self) -> float:
        return max(0.0, (self.start_of_day_equity - self.total_equity) / self.start_of_day_equity)

    @property
    def current_portfolio_notional(self) -> float:
        return sum(pos.market_value for pos in self.open_positions.values())


class ProposedBracketOrder(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    signal_date: date
    strategy_name: str
    client_order_id: str
    order_class: str = "BRACKET"
    side: Literal["buy", "sell"] = "buy"
    qty: int = Field(gt=0)
    entry_price: float = Field(gt=0.0)
    stop_loss_price: float = Field(gt=0.0)
    take_profit_price: float = Field(gt=0.0)

    @property
    def risk_per_share(self) -> float:
        if self.side == "sell":
            return self.stop_loss_price - self.entry_price
        return self.entry_price - self.stop_loss_price

    @property
    def reward_per_share(self) -> float:
        if self.side == "sell":
            return self.entry_price - self.take_profit_price
        return self.take_profit_price - self.entry_price

    @property
    def risk_dollars(self) -> float:
        return round(self.risk_per_share * self.qty, 4)

    @property
    def notional_dollars(self) -> float:
        return round(self.entry_price * self.qty, 4)


class ValidatedOrderIntent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    signal_date: date
    strategy_name: str
    client_order_id: str
    order_class: Literal["BRACKET"] = "BRACKET"
    side: Literal["buy", "sell"] = "buy"
    qty: int
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    risk_dollars: float
    notional_dollars: float
    guard_status: Literal["PASSED"] = "PASSED"
    _guard_token: object = PrivateAttr(default=None)

    def verify_guard_token(self) -> None:
        if self._guard_token is not _GUARD_CAPABILITY_TOKEN:
            raise RuntimeError(
                "UNFORGEABLE_GUARD_TOKEN_MISSING: ValidatedOrderIntent must be "
                "issued exclusively by OrderValidationGuard.validate_order()."
            )


class OrderValidationGuard:
    """
    Immutable Deterministic Python Risk Gate (`AGENTS.md` Section 7).
    Enforces:
    1. No Averaging Down (raises ValueError if held position is below avg_entry_price).
    2. Mandatory Bracket Orders (OCO) with valid stop_loss, take_profit, and reward:risk ratio.
    3. Volatility-Adjusted Risk Sizing & Exposure Caps.
    4. Earnings Blackout Filter (<= 3 trading days).
    5. Global Daily Loss Kill Switch, Frequency Caps, and Client Order ID Idempotency.
    """

    def __init__(self, settings: EngineSettings) -> None:
        self.settings = settings

    def validate_order(
        self,
        order: ProposedBracketOrder,
        portfolio: PortfolioState,
        days_to_earnings: int | None,
        llm_veto: Literal["APPROVE", "VETO"] = "APPROVE",
    ) -> ValidatedOrderIntent:
        # 0. Fail-Closed LLM Veto Check
        if llm_veto != "APPROVE":
            raise ValueError(f"LLM_VETO_ACTIVE: Order for {order.ticker} blocked by Stage 2 Veto.")

        # 1. Global Daily Loss Kill Switch
        if portfolio.kill_switch_latched:
            raise ValueError("KILL_SWITCH_ENGAGED: Kill switch is latched for this session.")
        if portfolio.daily_drawdown_pct >= self.settings.max_daily_loss_pct:
            raise ValueError(
                f"KILL_SWITCH_DAILY_LOSS_EXCEEDED: Drawdown {portfolio.daily_drawdown_pct:.4f} "
                f">= limit {self.settings.max_daily_loss_pct:.4f}."
            )

        # 2. Earnings Blackout Filter (<= 3 trading sessions or unknown)
        if days_to_earnings is None:
            raise ValueError(
                f"EARNINGS_BLACKOUT: {order.ticker} has unknown earnings date (fail-closed)."
            )
        if 0 <= days_to_earnings <= self.settings.earnings_blackout_days:
            raise ValueError(
                f"EARNINGS_BLACKOUT: {order.ticker} reports earnings in {days_to_earnings} "
                f"trading sessions (limit > {self.settings.earnings_blackout_days})."
            )

        # 3. Open Unfilled Entry Order Check
        if order.ticker in portfolio.open_entry_order_tickers:
            raise ValueError(
                f"OPEN_ENTRY_ORDER_EXISTS: Open entry order already exists for {order.ticker}."
            )

        # 4. Strict Anti-Averaging-Down Rule (Proibição de Preço Médio em Prejuízo)
        existing_pos = portfolio.open_positions.get(order.ticker)
        if existing_pos is not None and existing_pos.is_losing:
            raise ValueError(
                f"AVERAGING_DOWN_PROHIBITED: {order.ticker} is currently held at an unrealized "
                f"loss (current={existing_pos.current_price} < "
                f"entry={existing_pos.avg_entry_price})."
            )

        # 5. Mandatory Atomic Bracket Order (OCO) & Price Geometry
        if order.order_class != "BRACKET":
            raise ValueError(f"BRACKET_ORDER_REQUIRED: Received '{order.order_class}'.")

        if order.side == "sell":
            if (
                order.stop_loss_price <= order.entry_price
                or order.take_profit_price >= order.entry_price
            ):
                raise ValueError(
                    f"INVALID_BRACKET_PRICES: short take_profit ({order.take_profit_price}) "
                    f"must be < entry ({order.entry_price}) < stop_loss ({order.stop_loss_price})."
                )
        elif (
            order.stop_loss_price >= order.entry_price
            or order.take_profit_price <= order.entry_price
        ):
            raise ValueError(
                f"INVALID_BRACKET_PRICES: stop_loss ({order.stop_loss_price}) must be < "
                f"entry ({order.entry_price}) < take_profit ({order.take_profit_price})."
            )

        rr_ratio = order.reward_per_share / order.risk_per_share
        if rr_ratio + 1e-9 < self.settings.min_reward_risk_ratio:
            raise ValueError(
                f"INSUFFICIENT_REWARD_RISK_RATIO: {rr_ratio:.2f} < "
                f"{self.settings.min_reward_risk_ratio:.2f}."
            )

        # 6. Deterministic Client Order ID & Idempotency Check
        if order.strategy_name not in ALLOWED_STRATEGY_NAMES:
            raise ValueError(
                f"INVALID_CLIENT_ORDER_ID: strategy '{order.strategy_name}' not in allowed set."
            )
        if not CLIENT_ORDER_ID_PATTERN.match(order.client_order_id):
            raise ValueError(
                f"INVALID_CLIENT_ORDER_ID: '{order.client_order_id}' does not match pattern."
            )
        expected_id = format_client_order_id(order.ticker, order.signal_date, order.strategy_name)
        if order.client_order_id != expected_id:
            raise ValueError(
                f"INVALID_CLIENT_ORDER_ID: Expected '{expected_id}', got '{order.client_order_id}'."
            )
        if order.client_order_id in portfolio.existing_client_order_ids:
            raise ValueError(
                f"DUPLICATE_CLIENT_ORDER_ID: '{order.client_order_id}' already submitted."
            )

        # 7. Risk Per Trade & Single-Position Exposure Caps
        max_risk_allowed = portfolio.total_equity * self.settings.max_risk_per_trade_pct
        if order.risk_dollars > max_risk_allowed + 1e-6:
            raise ValueError(
                f"MAX_RISK_PER_TRADE_EXCEEDED: Order risk ${order.risk_dollars:.2f} > "
                f"limit ${max_risk_allowed:.2f}."
            )

        existing_ticker_notional = existing_pos.market_value if existing_pos is not None else 0.0
        max_pos_allowed = portfolio.total_equity * self.settings.max_position_pct
        combined_notional = existing_ticker_notional + order.notional_dollars
        if combined_notional > max_pos_allowed + 1e-6:
            raise ValueError(
                f"MAX_POSITION_PCT_EXCEEDED: Position notional ${combined_notional:.2f} "
                f"> limit ${max_pos_allowed:.2f}."
            )

        # 7. Portfolio-Wide Open Positions, Total Exposure & Daily Order Frequency Caps
        if (
            existing_pos is None
            and len(portfolio.open_positions) >= self.settings.max_open_positions
        ):
            raise ValueError(
                f"MAX_OPEN_POSITIONS_EXCEEDED: Currently holding {len(portfolio.open_positions)} "
                f"positions (limit {self.settings.max_open_positions})."
            )

        max_portfolio_allowed = portfolio.total_equity * self.settings.max_portfolio_exposure
        if (
            portfolio.current_portfolio_notional + order.notional_dollars
        ) > max_portfolio_allowed + 1e-6:
            raise ValueError(
                f"MAX_PORTFOLIO_EXPOSURE_EXCEEDED: Total exposure "
                f"${portfolio.current_portfolio_notional + order.notional_dollars:.2f} > "
                f"limit ${max_portfolio_allowed:.2f}."
            )

        if portfolio.orders_submitted_today >= self.settings.max_daily_orders:
            raise ValueError(
                f"MAX_DAILY_ORDERS_EXCEEDED: {portfolio.orders_submitted_today} orders already "
                f"submitted today (limit {self.settings.max_daily_orders})."
            )

        intent = ValidatedOrderIntent(
            ticker=order.ticker,
            signal_date=order.signal_date,
            strategy_name=order.strategy_name,
            client_order_id=order.client_order_id,
            order_class="BRACKET",
            side=order.side,
            qty=order.qty,
            entry_price=order.entry_price,
            stop_loss_price=order.stop_loss_price,
            take_profit_price=order.take_profit_price,
            risk_dollars=order.risk_dollars,
            notional_dollars=order.notional_dollars,
            guard_status="PASSED",
        )
        intent._guard_token = _GUARD_CAPABILITY_TOKEN
        return intent
