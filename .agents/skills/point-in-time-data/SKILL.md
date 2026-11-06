---
name: point-in-time-data
description: Designs, ingests, validates, and audits historical financial datasets for point-in-time correctness. Use when working with market prices, SEC filings, earnings, fundamentals, historical universes, or backtesting.
---

# Point-in-Time Financial Data

## Objective
Ensure that historical research, feature engineering, and backtests only use information genuinely available to a market participant at the exact simulated decision timestamp (`available_at`).

## Workflow
1. Identify the source and original publication timestamp (`published_at`).
2. Compute the realistic tradable availability timestamp (`available_at`), ensuring after-hours releases (after 16:00 ET) are only available on the next trading session.
3. Verify historical revisions and restated financial statements (use SEC filing `acceptanceDateTime`, never fiscal period end date!).
4. Verify corporate-action treatment (splits and dividends).
5. Detect and group syndicated/duplicate news sources.
6. Audit historical universe membership and explicitly classify whether the dataset is Survivorship-Bias-Free (requires delisted data) or a Static Present-Day Universe (requires explicit warning labels).
7. Validate the dataset with automated look-ahead unit tests.

## Mandatory Checks
- Look-ahead bias (e.g., using Q3 earnings on Sept 30 instead of the November filing date).
- Target leakage in rolling normalizations (z-scores must use expanding/rolling past windows only).
- Timestamp timezone conversion errors (ET vs. UTC).
- Restated fundamentals overwriting initial releases.
- Split and dividend adjustment consistency between entry prices and ATR calculations.
- Data availability delays.

## Rules
- A dataset is NEVER point-in-time merely because rows have a `date` column.
- For SEC filings, `available_at` must be derived from the SEC EDGAR filing acceptance timestamp, never the `period_of_report` date.
- If free data providers (Alpaca/EDGAR) do not include delisted historical equities, do not fabricate survivorship checks: log an explicit `SURVIVORSHIP_BIAS_WARNING` in all backtest reports and restrict backtests to recent 2-3 year windows where delisting distortion in top 500 liquid stocks is documented.
- Never silently forward-fill missing fundamentals with future or current values.

## Completion Criteria
Produce an automated data-quality report with verified point-in-time properties, automated look-ahead tests passing, and explicit documentation of provider limitations.