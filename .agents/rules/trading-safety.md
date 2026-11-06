---
trigger: always_on
description: Travas imutáveis de risco operacional, ordens Bracket e bloqueio de preço médio.
---
# Trading Safety
- Default execution mode is `RESEARCH`.
- `PAPER` mode requires explicit configuration and must verify `paper-api.alpaca.markets`.
- `LIVE` mode is strictly prohibited and must raise a `RuntimeError` if attempted.
- LLMs cannot submit orders, calculate share quantities, or override risk limits; LLMs have VETO power only.
- Every order must pass deterministic Python risk validation (`OrderValidationGuard`).
- **No Averaging Down:** Reject any buy order for a ticker currently held at an unrealized loss.
- **Bracket Orders Only:** Every entry order must be submitted as an atomic Bracket Order (OCO) with both `stop_loss` and `take_profit` defined.
- **Earnings Blackout:** Reject swing entries if an earnings release is scheduled within 3 trading sessions.
- Do not retry timed-out order submissions without querying broker status and enforcing deterministic `client_order_id` idempotency.