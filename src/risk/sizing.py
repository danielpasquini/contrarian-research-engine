import math
from datetime import date

from src.config import EngineSettings
from src.risk.guard import ProposedBracketOrder, format_client_order_id


def build_volatility_sized_bracket_order(
    ticker: str,
    signal_date: date,
    strategy_name: str,
    entry_price: float,
    atr_14: float,
    total_equity: float,
    settings: EngineSettings,
) -> ProposedBracketOrder:
    """
    Pure deterministic Python ATR volatility position sizer.
    - Stop Loss = Entry - (ATR_STOP_MULTIPLIER * ATR_14)
    - Take Profit = Entry + (MIN_REWARD_RISK_RATIO * (Entry - Stop Loss))
    - Qty = floor(min(max_risk_dollars / risk_per_share, max_position_dollars / entry_price))
    """
    if (
        math.isnan(entry_price)
        or entry_price <= 0.0
        or math.isnan(atr_14)
        or atr_14 <= 0.0
        or math.isnan(total_equity)
        or total_equity <= 0.0
    ):
        raise ValueError("entry_price, atr_14, and total_equity must be strictly positive.")

    stop_distance = settings.atr_stop_multiplier * atr_14
    stop_loss_price = round(entry_price - stop_distance, 2)
    if stop_loss_price <= 0.0 or stop_loss_price >= entry_price:
        raise ValueError(f"Invalid computed stop_loss_price ({stop_loss_price}) for {ticker}.")

    actual_risk_per_share = entry_price - stop_loss_price
    take_profit_distance = settings.min_reward_risk_ratio * actual_risk_per_share
    take_profit_price = round(entry_price + take_profit_distance, 2)

    max_risk_dollars = total_equity * settings.max_risk_per_trade_pct
    max_position_dollars = total_equity * settings.max_position_pct

    qty_by_risk = math.floor(max_risk_dollars / actual_risk_per_share)
    qty_by_notional = math.floor(max_position_dollars / entry_price)
    qty = int(min(qty_by_risk, qty_by_notional))

    if qty < 1:
        raise ValueError(f"Computed share quantity ({qty}) < 1 for {ticker}.")

    client_id = format_client_order_id(ticker, signal_date, strategy_name)

    return ProposedBracketOrder(
        ticker=ticker,
        signal_date=signal_date,
        strategy_name=strategy_name,
        client_order_id=client_id,
        order_class="BRACKET",
        side="buy",
        qty=qty,
        entry_price=round(entry_price, 2),
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
    )


def build_forensic_short_bracket_order(
    ticker: str,
    signal_date: date,
    strategy_name: str,
    entry_price: float,
    atr_14: float,
    total_equity: float,
    settings: EngineSettings,
) -> ProposedBracketOrder:
    """
    Conservative Forensic Short ATR position sizer:
    - Tighter Stop Loss ABOVE entry: Entry + (1.5 * ATR_14)
    - Take Profit BELOW entry: Entry - (MIN_REWARD_RISK_RATIO * (Stop Loss - Entry))
    - Stricter risk cap: 0.25% of total equity (half of Long risk cap)
    - Stricter position cap: 4.0% of total equity (half of Long position cap)
    """
    if (
        math.isnan(entry_price)
        or entry_price <= 0.0
        or math.isnan(atr_14)
        or atr_14 <= 0.0
        or math.isnan(total_equity)
        or total_equity <= 0.0
    ):
        raise ValueError("entry_price, atr_14, and total_equity must be strictly positive.")

    short_stop_mult = min(1.5, settings.atr_stop_multiplier)
    stop_distance = short_stop_mult * atr_14
    stop_loss_price = round(entry_price + stop_distance, 2)
    actual_risk_per_share = stop_loss_price - entry_price
    if actual_risk_per_share <= 0.0:
        raise ValueError(f"Invalid short stop_loss_price ({stop_loss_price}) for {ticker}.")

    take_profit_distance = settings.min_reward_risk_ratio * actual_risk_per_share
    take_profit_price = round(entry_price - take_profit_distance, 2)
    if take_profit_price <= 0.0 or take_profit_price >= entry_price:
        raise ValueError(f"Invalid short take_profit_price ({take_profit_price}) for {ticker}.")

    short_risk_pct = min(0.0025, settings.max_risk_per_trade_pct)
    short_pos_pct = min(0.04, settings.max_position_pct)
    max_risk_dollars = total_equity * short_risk_pct
    max_position_dollars = total_equity * short_pos_pct

    qty_by_risk = math.floor(max_risk_dollars / actual_risk_per_share)
    qty_by_notional = math.floor(max_position_dollars / entry_price)
    qty = int(min(qty_by_risk, qty_by_notional))
    if qty < 1:
        raise ValueError(f"Computed short share quantity ({qty}) < 1 for {ticker}.")

    client_id = format_client_order_id(ticker, signal_date, strategy_name)
    return ProposedBracketOrder(
        ticker=ticker,
        signal_date=signal_date,
        strategy_name=strategy_name,
        client_order_id=client_id,
        order_class="BRACKET",
        side="sell",
        qty=qty,
        entry_price=round(entry_price, 2),
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
    )


def build_defined_risk_put_proxy(
    ticker: str,
    entry_price: float,
    atr_14: float,
    total_equity: float,
) -> dict[str, str | float | int]:
    """
    Computes an educational Defined-Risk Long Put Option proxy (30-45 DTE ATM Put)
    as a safe alternative to shorting shares (100% capped loss, zero borrow/squeeze risk).
    """
    step = 5.0 if entry_price >= 100.0 else 2.5
    strike = round(round(entry_price / step) * step, 2)
    est_option_price = round(max(0.85, atr_14 * 1.35), 2)
    contract_cost = round(est_option_price * 100.0, 2)
    max_budget = total_equity * 0.0025
    contracts = max(1, int(max_budget // contract_cost)) if contract_cost > 0 else 1
    total_premium = round(contracts * contract_cost, 2)
    return {
        "instrument": f"{ticker} 35d ${strike:.0f} PUT",
        "strike": strike,
        "est_premium_per_share": est_option_price,
        "contracts": contracts,
        "max_loss_usd": total_premium,
        "breakeven_price": round(strike - est_option_price, 2),
    }
