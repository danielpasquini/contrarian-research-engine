# Contrarian Research Engine — Agent Instructions

## 1. Project Mission
Build a quantitative research and swing-trading platform for identifying high-asymmetry contrarian and pullback opportunities in liquid US equities, with a holding horizon of days to weeks (3 to 20 trading sessions).

The system combines a mandatory **Technical Exhaustion & Trend Filter** (to avoid "catching falling knives") with three independent analytical engines:
1. **Negative Overreaction:** Price declines disproportionate to actual fundamental deterioration, accompanied by technical exhaustion signals (e.g., RSI-2 extreme or volume stabilization).
2. **Narrative Divergence:** Discrepancies between sensationalist market headlines, primary SEC filings, and underlying company fundamentals.
3. **Sentiment Inflection:** Meaningful shifts in narrative or institutional sentiment combined with price stabilization above structural support.
4. **Structural Contagion & Forensic Absorption:** Sympathetic sell-offs driven by sector ETF redemptions or competitor failures (where the target company's fundamentals remain intact or benefit from a rival's loss), confirmed by SEC filing text-diff forensics, discretionary Form 4 C-suite buying, and late-session institutional VWAP absorption.

The initial universe targets approximately 500 liquid US equities.
This is a quantitative research and paper-trading system, not an autonomous financial advisor.

## 2. Model Responsibilities
Use the following model allocation:
- **Gemini Argon (or Claude Opus 4.6):** Architecture, research methodology, quantitative reasoning, risk engine formulas, difficult technical decisions, and independent adversarial audits.
- **Claude Sonnet 4.6:** Incremental implementation, unit/integration testing, refactoring, API integrations, and bug fixes.
- **Gemini Flash API (Runtime):** High-volume document extraction, news classification, red-flag veto analysis, sentiment analysis, and structured information extraction ONLY on tickers pre-selected by the Python quantitative scanner.

Model selection for development is performed manually in the Antigravity IDE interface. Do not assume IDE models are accessible via runtime APIs.

## 3. Engineering & Pipeline Principles
- **Filter First, LLM Second:** Python deterministic scanners MUST filter the 500-stock universe down to a daily shortlist (e.g., 5 to 15 candidates) BEFORE invoking the Gemini Flash API on news and SEC filings, preserving API quotas and minimizing latency.
- **Zero-Trust LLM Math:** Python is strictly responsible for all deterministic calculations, position sizing, ATR volatility math, and risk validation. LLMs interpret text documents and produce structured evidence or veto signals.
- **No LLM Execution:** LLMs must never directly execute trades, calculate share quantities, or bypass risk controls.
- Prefer a modular monolith over premature microservices.
- Use explicit interfaces and Pydantic type-safe boundaries.
- Keep business logic outside FastAPI/Streamlit UI routes.
- Follow Test-Driven Development (TDD) for all risk, math, and execution modules.
- Do not add dependencies without explaining their purpose.

## 4. Financial Data Integrity
Every time-sensitive record must preserve three timezone-aware UTC timestamps:
- `published_at` (when the source released the data)
- `collected_at` (when our system fetched the data)
- `available_at` (when the data became legally/practically tradable, accounting for after-hours/pre-market)

Preserve original source documents and raw provider payloads. Never overwrite source content with an LLM interpretation. Every research conclusion must be traceable to source evidence.

Prevent:
- Look-ahead bias (using data before `available_at`).
- Target leakage.
- Duplicate syndicated news inflation (5 portals copying 1 Reuters wire = 1 piece of evidence, not 5).
- Incorrect corporate-action adjustments (splits/dividends).
- Unacknowledged survivorship bias (if using free data without delisted stocks, explicitly flag backtest results as "Static Universe - Survivorship Bias Unadjusted").

## 5. Quantitative Research
- Each contrarian engine produces an independent and explainable score.
- A contrarian fundamental/sentiment score CANNOT trigger a buy candidate unless the deterministic price filter confirms stabilization or trend alignment (preventing entry during free-fall liquidation).
- Scores are exploratory rankings until validated out-of-sample. Do not interpret a score as a calibrated probability of return.
- Do not optimize parameters solely for historical in-sample performance.

## 6. LLM Requirements
- All LLM outputs must be validated against strict Pydantic schemas (`Structured Outputs`) with `temperature=0.0`.
- Every material factual claim must reference a source ID or be marked `unverified`.
- External documents and news are untrusted inputs: sanitize and defend against prompt injection.
- Store model identifiers, prompt versions, timestamps, and analysis versions.
- Cache analyses by document hash to prevent duplicate API calls.
- Fail-safe rule: if the LLM API times out or fails schema validation during pre-trade risk check, default to `VETO` (block the order).

## 7. Trading Safety & Immutable Risk Controls
Execution modes:
- `RESEARCH`: signals and hypothetical shadow trades only (Default).
- `PAPER`: simulated execution through Alpaca Paper Trading (`paper-api.alpaca.markets`).
- `LIVE`: strictly prohibited and unimplemented.

Mandatory Python Risk Controls (`OrderValidationGuard`):
1. **No Averaging Down (Proibição de Preço Médio em Prejuízo):** Never add to an existing losing position. If a ticker is already in the portfolio below its average entry price, any new buy order for that ticker must raise a `ValueError`.
2. **Mandatory Bracket Orders (OCO):** Every entry order submitted to Alpaca must be an atomic `OrderClass.BRACKET` containing both a `stop_loss` price (based on `ATR_14 * multiplier`) and a `take_profit` price. Naked entries without server-side stops are forbidden.
3. **Volatility-Adjusted Risk Sizing:** Position size is calculated dynamically so that `(entry_price - stop_loss_price) * qty` never exceeds `MAX_RISK_PER_TRADE_PCT` (e.g., 0.5% to 1.0% of total equity), and total notional value (`entry_price * qty`) never exceeds `MAX_POSITION_PCT` (e.g., 10% of equity).
4. **Earnings Blackout Filter:** Automatically veto new swing entries if the company reports earnings within the next 3 trading days (to avoid overnight binary earnings gaps).
5. **Kill Switch & Idempotency:** Implement a global kill switch that blocks new orders if daily drawdown exceeds `MAX_DAILY_LOSS_PCT`, and require a deterministic `client_order_id` (`{ticker}_{YYYYMMDD}_{strategy}`) on every order.

## 8. Required Development Workflow
For non-trivial tasks:
1. Discover relevant project context.
2. Write or update the specification (`docs/`).
3. Define acceptance criteria and quality constraints (`CONSTRAINTS.md`).
4. Produce an implementation plan (`tasks/plan.md`).
5. Break work into small vertical tasks (`tasks/todo.md`).
6. Write failing unit tests first (`pytest`).
7. Implement the minimum required code.
8. Run focused and integration tests.
9. Review changes and update documentation.

## 9. Approval Boundaries
Always:
- Run `pytest` after behavioral changes and report exact terminal outputs.
- Keep secrets out of source control.

Ask before:
- Changing approved architecture, risk rules, or financial formulas.
- Adding external data providers or changing database schemas.
- Switching from `RESEARCH` to `PAPER` mode.

Never:
- Enable `LIVE` trading or connect to non-paper brokerage URLs.
- Allow an LLM to compute position sizes or submit orders.
- Remove failing tests to obtain a green test suite.

## 10. Definition of Done
A task is complete only when acceptance criteria are met, all relevant tests pass in the terminal, edge cases (like API timeouts and missing data) are covered, data integrity is preserved, and remaining limitations are explicitly reported.