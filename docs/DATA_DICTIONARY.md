# Contrarian Research Engine — Data Dictionary (`DATA_DICTIONARY.md`)

## 1. Universal Temporal Contract (`PointInTimeBase`)
Every time-sensitive record across PostgreSQL tables, Parquet files, and Pydantic schemas inherits the following mandatory fields:

| Field | Type | Constraint | Definition |
| :--- | :--- | :--- | :--- |
| `record_id` | `UUID` | PK, Not Null | Unique deterministic or UUIDv4 identifier for the record. |
| `published_at` | `datetime (UTC)` | Timezone-aware UTC, Not Null | Exact timestamp when the external source originally released the data (e.g., bar close, wire timestamp, SEC `acceptanceDateTime`). |
| `collected_at` | `datetime (UTC)` | Timezone-aware UTC, Not Null | Exact system clock timestamp when `src/ingestion/` fetched the payload. |
| `available_at` | `datetime (UTC)` | Timezone-aware UTC, Not Null, `>= published_at` | Earliest timestamp when a market participant could legally and practically trade on the information during regular NYSE market hours (`09:30`–`16:00 ET`). |
| `raw_payload_hash` | `str (SHA-256)` | 64 hex chars, Not Null | SHA-256 digest of the immutable raw provider payload stored in `data/raw/`. |

### `available_at` Computation Rules (NYSE Calendar)
- **Daily OHLCV Bar (Session Date $T$):** `published_at` = $T$ at `16:00:00 ET`; `available_at` = $T$ at `16:00:00 ET` for end-of-day batch scanning (for next-session $T+1$ open/limit execution).
- **Intraday News / SEC Filing released before `16:00:00 ET` on Trading Day $T$:** `available_at = published_at`.
- **After-Hours News / SEC Filing released at or after `16:00:00 ET` on Day $T$ (or on a weekend/holiday):** `available_at` = `09:30:00 ET` on the next valid NYSE trading session $T+1$.
- **SEC Periodic Financial Statements (`10-Q`, `10-K`):** `published_at` MUST be the SEC EDGAR `acceptanceDateTime`, **never** the fiscal `period_of_report` date.

---

## 2. Core Domain Entities & Schemas

### 2.1 `NormalizedBar` (PostgreSQL: `market_bars_daily` / Parquet: `data/processed/bars.parquet`)
| Field | Type | Description |
| :--- | :--- | :--- |
| `ticker` | `str` | Uppercase equity symbol (e.g., `"AAPL"`). |
| `session_date` | `date` | NYSE trading session date. |
| `open`, `high`, `low`, `close` | `Decimal / float64` | Split- and dividend-adjusted prices (used for continuous return & indicator calculation). |
| `raw_close` | `Decimal / float64` | Unadjusted close price on `session_date` (used to verify minimum price filter $\ge \$10$). |
| `volume` | `int64` | Adjusted share volume. |
| `dollar_volume` | `float64` | `raw_close * raw_volume`. |
| `split_factor` | `float64` | Cumulative adjustment factor applied as of `available_at`. |
| `published_at`, `collected_at`, `available_at` | `datetime (UTC)` | Mandatory PIT timestamps. |

### 2.2 `FundamentalSnapshot` (PostgreSQL: `fundamental_snapshots`)
| Field | Type | Description |
| :--- | :--- | :--- |
| `ticker` | `str` | Equity symbol. |
| `cik` | `str` | 10-digit zero-padded SEC Central Index Key. |
| `accession_number` | `str` | SEC filing accession number (e.g., `0000320193-25-000106`). |
| `form_type` | `Literal["10-Q", "10-K", "8-K"]` | SEC filing form type. |
| `period_of_report` | `date` | Fiscal period end date (informational only; **never used for PIT gating**). |
| `revenue_ttm` | `float | None` | Trailing 12-month revenue (USD). |
| `operating_income_ttm` | `float | None` | Trailing 12-month operating income (USD). |
| `operating_cash_flow_ttm` | `float | None` | Trailing 12-month operating cash flow (USD). |
| `total_debt` | `float | None` | Short-term + long-term debt (USD). |
| `cash_and_equivalents` | `float | None` | Cash and marketable securities (USD). |
| `next_earnings_date` | `date | None` | Next scheduled or estimated earnings release date. |
| `trading_days_to_earnings` | `int | None` | Number of NYSE trading sessions until `next_earnings_date`. |
| `earnings_blackout` | `bool` | `True` if `trading_days_to_earnings is not None and trading_days_to_earnings <= 3`. |
| `published_at`, `collected_at`, `available_at` | `datetime (UTC)` | `published_at` = SEC `acceptanceDateTime`. |

### 2.3 `NewsCluster` (PostgreSQL: `news_clusters`)
| Field | Type | Description |
| :--- | :--- | :--- |
| `cluster_id` | `UUID` | Unique identifier for the deduplicated news story. |
| `ticker` | `str` | Target equity symbol. |
| `primary_source_id` | `str` | ID of the earliest original wire/article in the cluster. |
| `Duplicate_source_ids` | `list[str]` | IDs of syndicated copies collapsed into this cluster. |
| `independent_source_count` | `int` | Count of genuinely distinct reporting origins (`1` for a single syndicated wire). |
| `headline` | `str` | Sanitized primary headline. |
| `summary_text` | `str` | Sanitized article body/summary. |
| `published_at`, `collected_at`, `available_at` | `datetime (UTC)` | Derived from the earliest article in the cluster. |

### 2.4 `ScannerCandidate` (PostgreSQL: `scanner_candidates`)
| Field | Type | Description |
| :--- | :--- | :--- |
| `candidate_id` | `UUID` | Unique daily candidate ID. |
| `scan_date` | `date` | Trading session date evaluated. |
| `ticker` | `str` | Symbol passing Stage 1 filter. |
| `close_price` | `float` | Latest adjusted close. |
| `addv_20d` | `float` | 20-day average daily dollar volume. |
| `return_3d_pct` | `float` | 3-day cumulative return. |
| `return_5d_pct` | `float` | 5-day cumulative return. |
| `z_score_return_3d` | `float` | 3-day return standardized over trailing 252 trading days. |
| `rsi_2` | `float` | 2-period Wilder RSI (`0.0` to `100.0`). |
| `atr_14` | `float` | 14-period Wilder Average True Range (in USD). |
| `atr_pct` | `float` | `atr_14 / close_price`. |
| `volume_ratio_20d` | `float` | `volume / sma(volume, 20)`. |
| `intraday_recovery_ratio` | `float` | `(close - low) / max(high - low, 1e-6)`. |
| `distance_to_sma50_atr` | `float` | `(close - sma_50) / atr_14`. |
| `distance_to_sma200_atr` | `float` | `(close - sma_200) / atr_14`. |
| `setup_type` | `Literal["OVERSOLD_EXHAUSTION", "STRUCTURAL_PULLBACK"]` | Stage 1 trigger classification. |
| `scanner_rank` | `int` | Rank from `1` to `15` (`<= 15` strictly enforced). |
| `available_at` | `datetime (UTC)` | Timestamp when scan completed and inputs were available. |

### 2.5 `LLMAnalysisOutput` & `LLMExtractionWireSchema` (PostgreSQL: `llm_analyses`)
> Full specification in [`docs/STAGE2_EVENT_INTELLIGENCE_DESIGN.md`](STAGE2_EVENT_INTELLIGENCE_DESIGN.md).

| Field | Type | Description |
| :--- | :--- | :--- |
| `analysis_id` | `UUID` | PK. |
| `ticker` | `str` | Target equity symbol. |
| `model_id` | `str` | e.g., `"gemini-2.5-flash"`. |
| `prompt_version` | `str` | Semantic version of prompt template (e.g., `"v1.1.0"`). |
| `schema_version` | `str` | Semantic version of Pydantic output schema (e.g., `"v1.1.0"`). |
| `input_cache_hash` | `str` | SHA-256 hash of `(model_id, prompt_version, schema_version, sorted_source_hashes)`. |
| `event_classification` | `Literal["EARNINGS_REACTION", "GUIDANCE_CUT", "MACRO_SECTOR_SELLOFF", "REGULATORY_LEGAL", "ANALYST_DOWNGRADE", "MANAGEMENT_CHANGE", "NO_MATERIAL_NEWS", "OTHER"]` | Primary catalyst category. |
| `headline_tone` | `Literal["EXTREME_NEGATIVE", "MODERATE_NEGATIVE", "NEUTRAL", "POSITIVE"]` | Categorical media headline sentiment severity. |
| `verified_facts` | `list[CitedClaim]` | Each item contains `{claim: str, source_id: str, source_tier: SourceTier, is_fact_vs_opinion: str, is_new_information: bool}`. |
| `market_narrative_summary` | `str` | Summary of media/headline tone and severity. |
| `fundamental_impact` | `Literal["NONE", "TEMPORARY_1_2_QUARTERS", "STRUCTURAL_MULTI_YEAR", "UNKNOWN"]` | Assessed duration of fundamental impact. |
| `narrative_vs_filing_divergence` | `float` | Bounded scale `[0.0, 1.0]` measuring sensationalist headline tone vs. primary SEC filing stability. |
| `novelty_score` | `float` | Tier-weighted ratio `[0.0, 1.0]` of newly disclosed facts vs. recycled commentary (`source_id != "unverified"`). |
| `sentiment_inflection_detected` | `bool` | Whether recent sources show stabilization/institutional defense after peak pessimism. |
| `contradicting_evidence` | `list[CitedClaim]` | Mandatory list of facts supporting why the price drop may be rational (anti-confirmation bias). |
| `detected_red_flags` / `red_flags_detected` | `list[Literal["ACCOUNTING_IRREGULARITY", "SEC_DOJ_INVESTIGATION", "GOING_CONCERN_DISTRESS", "ABRUPT_CSUITE_EXIT", "COVENANT_BREACH", "IMMINENT_EARNINGS", "PROMPT_INJECTION_SUSPECTED"]]` | Detected structural or security red flags (synchronized fields). |
| `veto_decision` | `Literal["APPROVE", "VETO"]` | Mandatory `VETO` if `detected_red_flags` is non-empty, `fundamental_impact` is `"STRUCTURAL_MULTI_YEAR"`, or uncertainty is critical. |
| `veto_reason_code` | `str | None` | Deterministic reason code populated whenever `veto_decision == "VETO"`. |
| `confidence_score` | `float` | `0.0` to `1.0` extraction confidence based on source completeness. |
| `missing_information` | `list[str]` | Explicitly noted data gaps. |

### 2.6 `StrategySignal` & `ValidatedOrderIntent` (PostgreSQL: `strategy_signals`, `orders`)
| Field | Type | Description |
| :--- | :--- | :--- |
| `signal_id` | `UUID` | Unique signal identifier. |
| `ticker` | `str` | Equity symbol. |
| `negative_overreaction_score` | `float` | Engine 1 score (`0.0`–`100.0`). |
| `narrative_divergence_score` | `float` | Engine 2 score (`0.0`–`100.0`). |
| `sentiment_inflection_score` | `float` | Engine 3 score (`0.0`–`100.0`). |
| `composite_score` | `float` | Weighted exploratory ranking (`0.0`–`100.0`). |
| `primary_strategy` | `str` | Dominant engine name (`"neg_overreaction"`, `"narrative_div"`, `"sentiment_infl"`). |
| `client_order_id` | `str` | Deterministic ID: `"{ticker}_{YYYYMMDD}_{primary_strategy}"`. |
| `execution_mode` | `Literal["RESEARCH", "PAPER"]` | Active execution mode (`LIVE` is forbidden). |
| `order_class` | `Literal["BRACKET"]` | Must always be atomic OCO Bracket. |
| `qty` | `int` | Whole shares (`>= 1`) computed by `src/risk/`. |
| `entry_limit_price` | `Decimal` | Planned entry price. |
| `stop_loss_price` | `Decimal` | `entry_limit_price - (k_stop * atr_14)`. |
| `take_profit_price` | `Decimal` | `entry_limit_price + (k_tp * atr_14)`. |
| `risk_dollars` | `Decimal` | `(entry_limit_price - stop_loss_price) * qty`. |
| `notional_dollars` | `Decimal` | `entry_limit_price * qty`. |
| `guard_status` | `Literal["PASSED", "REJECTED"]` | Outcome of `OrderValidationGuard`. |
| `rejection_reason` | `str | None` | Populated if `guard_status == "REJECTED"`. |
