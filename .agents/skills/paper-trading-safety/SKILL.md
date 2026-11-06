---
name: paper-trading-safety
description: Implements and audits safe paper-trading execution through Alpaca. Use when designing order submission, portfolio risk controls, Bracket OCO orders, execution reconciliation, or paper-trading workflows.
---

# Paper Trading Safety

## Objective
Enable controlled simulated trading on Alpaca Paper Trading with deterministic Python risk guardrails and zero possibility of live order execution or runaway loss loops.

## Workflow
1. Verify that `EXECUTION_MODE` is `research` or `paper` (abort immediately if `live`).
2. Verify paper-only credentials and assert that the endpoint URL equals `https://paper-api.alpaca.markets`.
3. Synchronize current broker positions, open orders, and daily equity drawdown before evaluating new signals.
4. Calculate proposed position size, ATR-based `stop_loss`, and `take_profit` in pure deterministic Python (`src/risk/`).
5. Run `OrderValidationGuard` to enforce all portfolio, position, and anti-averaging-down limits.
6. Verify market hours, liquidity thresholds, and earnings blackout windows.
7. Generate a deterministic `client_order_id` (`{ticker}_{YYYYMMDD}_{strategy}`) and check for existing orders today.
8. Submit exclusively as an atomic `OrderClass.BRACKET` (OCO) order through the Alpaca paper adapter.
9. Persist the broker response, reconcile fills/positions, and write an immutable audit log entry.

## Mandatory Controls
- `RESEARCH` is the default mode; `LIVE` mode must raise `RuntimeError`.
- No LLM may submit orders, modify risk limits, or compute share quantities.
- **No Averaging Down:** Block buys on any ticker currently held at an unrealized loss.
- **Mandatory Bracket Order (OCO):** Every entry must include server-side `stop_loss` and `take_profit` legs.
- **Max Risk Per Trade:** `(entry - stop_loss) * qty <= MAX_RISK_PER_TRADE_PCT * equity`.
- **Max Position Exposure:** `entry * qty <= MAX_POSITION_PCT * equity`.
- **Max Portfolio Exposure & Open Positions:** Hard caps enforced prior to submission.
- **Daily Loss Kill Switch:** Block all new entries if daily equity drop exceeds `MAX_DAILY_LOSS_PCT`.
- **Daily Order Frequency Cap:** Maximum `MAX_DAILY_ORDERS` per day to prevent infinite loop bugs.

## Failure Handling
- Never assume a timed-out HTTP request means the order was rejected.
- Always query Alpaca order status by `client_order_id` before any retry attempt.
- If the risk engine, database, or LLM veto check fails, fail closed (do not submit the order).

## Completion Criteria
Demonstrate 100% test coverage on all risk rejection paths using mocked `alpaca-py` clients before requesting user approval to connect to a real Alpaca Paper Trading account.