---
trigger: always_on
description: Invariantes de integridade temporal (Point-in-Time) e rastreabilidade de dados financeiros.
---
# Financial Data Integrity
- Preserve original source data and raw payloads without mutation.
- Preserve three UTC timestamps on every record: `published_at`, `collected_at`, and `available_at`.
- Use `available_at` (never `published_at` alone) to gate information in historical simulations.
- Never use future information in feature engineering (strict anti-look-ahead bias).
- Account for stock splits and dividends explicitly in price series.
- Distinguish independent primary sources (SEC filings) from syndicated news copies.
- Every model-generated factual claim must link to a source record ID.
- Missing data must reduce confidence or veto the signal, never be silently imputed with current values.