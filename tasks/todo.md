# Contrarian Research Engine — Task Checklist (`tasks/todo.md`)

> **Execution Order:** Strictly follows the 14 risk-prioritized vertical slices defined in [`tasks/plan.md`](plan.md).
> **Status:** Planned — awaiting human approval before implementation begins.

---

## Pre-Implementation Gate: Human Approval & Ambiguity Resolution
- [ ] Review and approve [`tasks/plan.md`](plan.md) and [`CONSTRAINTS.md`](../CONSTRAINTS.md)
- [ ] Confirm or override Open Decisions `D-01` through `D-11` (`CONSTRAINTS.md` §11)

---

## Slice 1: Repository Structure, `.env` Config Loader, and `pytest` Setup
- [ ] **Objective:** Lock down package structure, `pyproject.toml` (`ruff`, `mypy --strict` + `pydantic.mypy`, `pytest` markers), autouse offline socket guard (`tests/conftest.py`), and `EngineSettings` (`src/config.py`).
- [ ] **Dependencies:** None.
- [ ] **Expected files:** `pyproject.toml`, `.gitignore`, `src/__init__.py`, `src/config.py`, `tests/conftest.py`, `tests/unit/test_config_and_pit.py`, `tests/constraints/test_repo_hygiene.py`, `tests/constraints/test_architecture_boundaries.py`, `tests/constraints/test_schema_conventions.py`.
- [ ] **TDD Step 1 (Red):** Write failing tests in `tests/unit/test_config_and_pit.py` (`test_llm_candidate_cap_bounds`, `test_max_risk_per_trade_upper_bound`) and `tests/constraints/` (`test_repo_hygiene.py`, `test_architecture_boundaries.py`, `test_schema_conventions.py`).
- [ ] **TDD Step 2 (Green):** Update `pyproject.toml`, `src/config.py`, `tests/conftest.py`, and boundary models to satisfy `C-CQ-01`..`C-CQ-09`, `C-RISK-00`, `C-QUOTA-01`, `C-TEST-03`, `C-TEST-06`.
- [ ] **Verification:** `pytest tests/unit/test_config_and_pit.py tests/constraints/test_repo_hygiene.py tests/constraints/test_architecture_boundaries.py tests/constraints/test_schema_conventions.py && ruff check src tests dashboard && mypy`

---

## Slice 2: Deterministic Risk Engine & `OrderValidationGuard` (`src/risk/`)
- [ ] **Objective:** Harden pure-Python volatility sizing (`src/risk/sizing.py`) and `OrderValidationGuard` (`src/risk/guard.py`) with `$0.01` tick rounding (`D-03`), unforgeable `ValidatedOrderIntent` token (`C-RISK-11`), fail-closed unknown earnings blackout (`D-04`), latched daily kill switch (`D-05`), and 100% branch coverage.
- [ ] **Dependencies:** Slice 1.
- [ ] **Expected files:** `src/risk/__init__.py`, `src/risk/sizing.py`, `src/risk/guard.py`, `tests/unit/test_risk_guard.py`, `tests/invariants/test_risk_invariants.py`.
- [ ] **TDD Step 1 (Red):** Write failing unit tests in `tests/unit/test_risk_guard.py` (open entry order rejection, stale held price, invalid ATR, unknown earnings date rejection, session 3 vs 4 boundary, NY session date `client_order_id`, latched kill switch, missing equity) and 10,000-case invariant sweep in `tests/invariants/test_risk_invariants.py`.
- [ ] **TDD Step 2 (Green):** Implement tick-rounded sizing and guard checks in `src/risk/sizing.py` and `src/risk/guard.py`.
- [ ] **Verification:** `pytest tests/unit/test_risk_guard.py tests/invariants/test_risk_invariants.py --cov=src/risk --cov-branch --cov-report=term-missing --cov-fail-under=100`

---

## Slice 3: Database Models, PostgreSQL Setup, and Point-in-Time Timestamp Validators (`src/database/`)
- [ ] **Objective:** Implement SQLAlchemy 2.0 ORM models (`src/database/models.py`), session factory (`src/database/session.py`), PIT validators (`src/database/validators.py`), and Alembic migrations (`alembic/`) enforcing `C-DB-01`..`C-DB-10`.
- [ ] **Dependencies:** Slice 1, Slice 2.
- [ ] **Expected files:** `src/database/__init__.py`, `src/database/models.py`, `src/database/session.py`, `src/database/validators.py`, `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_initial_pit_and_risk_schema.py`, `tests/constraints/test_db_schema.py`, `tests/integration/test_migrations.py`, `tests/integration/test_db_constraints.py`.
- [ ] **TDD Step 1 (Red):** Write failing metadata and Alembic revision tests in `tests/constraints/test_db_schema.py` and Postgres integration tests in `tests/integration/test_migrations.py` & `tests/integration/test_db_constraints.py`.
- [ ] **TDD Step 2 (Green):** Implement SQLAlchemy models with `naming_convention`, `timestamptz` columns, `CHECK` and `UNIQUE` constraints, session helpers, and Alembic migration `0001`.
- [ ] **Verification:** `pytest tests/constraints/test_db_schema.py`

---

## Slice 4: Alpaca Market Data & SEC EDGAR Ingestion Adapters (`src/ingestion/`)
- [ ] **Objective:** Build write-once raw payload storage (`src/ingestion/raw_store.py`), batched Alpaca market/corporate-action/news adapter (`src/ingestion/alpaca_data.py`), and 8 req/sec rate-limited SEC EDGAR adapter (`src/ingestion/sec_edgar.py`).
- [ ] **Dependencies:** Slice 1, Slice 3.
- [ ] **Expected files:** `src/ingestion/__init__.py`, `src/ingestion/raw_store.py`, `src/ingestion/alpaca_data.py`, `src/ingestion/sec_edgar.py`, `tests/unit/test_raw_store.py`, `tests/unit/test_ingestion_adapters.py`.
- [ ] **TDD Step 1 (Red):** Write failing tests in `tests/unit/test_raw_store.py` (`test_raw_payload_write_once`) and `tests/unit/test_ingestion_adapters.py` (SEC User-Agent & throttling, SGML acceptance header parsing, Alpaca batching).
- [ ] **TDD Step 2 (Green):** Implement `raw_store.py`, `alpaca_data.py`, and expand `sec_edgar.py`.
- [ ] **Verification:** `pytest tests/unit/test_raw_store.py tests/unit/test_ingestion_adapters.py --cov=src/ingestion --cov-branch --cov-report=term-missing --cov-fail-under=85`

---

## Slice 5: Data Normalization, Deduplication, and `available_at` Gating (`src/normalization/`)
- [ ] **Objective:** Implement NYSE calendar edge cases (early closes at `13:00 ET`, holidays, weekends, DST transitions, covered-year bounds check), conservative SEC `Z`-suffix disambiguation, as-of corporate-action adjustment (`C-PIT-12`), and syndicated news deduplication (`C-PIT-09`).
- [ ] **Dependencies:** Slice 3, Slice 4.
- [ ] **Expected files:** `src/normalization/__init__.py`, `src/normalization/calendar.py`, `src/normalization/pit_models.py`, `src/normalization/news_dedup.py`, `tests/unit/test_config_and_pit.py`, `tests/unit/test_pit_rules.py`.
- [ ] **TDD Step 1 (Red):** Write failing tests in `tests/unit/test_pit_rules.py` covering `C-PIT-02`, `C-PIT-03`, `C-PIT-05`, `C-PIT-09`, `C-PIT-10`, `C-PIT-12`.
- [ ] **TDD Step 2 (Green):** Update `calendar.py`, `pit_models.py`, and `news_dedup.py`.
- [ ] **Verification:** `pytest tests/unit/test_config_and_pit.py tests/unit/test_pit_rules.py --cov=src/normalization --cov-branch --cov-report=term-missing --cov-fail-under=95`

---

## Slice 6: Stage 1 Deterministic Technical & Overreaction Pre-Scanner (`src/scanner/`)
- [ ] **Objective:** Implement vectorized indicators (`src/scanner/indicators.py`) and Stage 1 pre-scanner (`src/scanner/pre_scanner.py`) outputting a typed `ScannerShortlist` (`<= MAX_DAILY_LLM_CANDIDATES`) in `< 3.0s` with truncation invariance (`1e-12`) across splits/dividends and missing-bar exclusion.
- [ ] **Dependencies:** Slice 5.
- [ ] **Expected files:** `src/scanner/__init__.py`, `src/scanner/indicators.py`, `src/scanner/pre_scanner.py`, `tests/unit/test_scanner.py`, `tests/perf/test_scanner_perf.py`.
- [ ] **TDD Step 1 (Red):** Update `tests/unit/test_scanner.py` (post-$t_k$ split/dividend truncation invariance `C-PIT-11`, parametrized shortlist cap `1, 5, 15` `C-QUOTA-02`, missing-bar gap exclusion `C-PIT-14`) and create `tests/perf/test_scanner_perf.py`.
- [ ] **TDD Step 2 (Green):** Update `indicators.py` and `pre_scanner.py` with `ScannerShortlist` and dual price-basis calculations (`C-PIT-12`).
- [ ] **Verification:** `pytest tests/unit/test_scanner.py tests/perf/test_scanner_perf.py --cov=src/scanner --cov-branch --cov-report=term-missing --cov-fail-under=90`

---

## Slice 7: Gemini Flash API Client with Caching, Rate-Limiting, and Fail-Closed `VETO` Fallback (`src/intelligence/`)
- [ ] **Objective:** Implement the single `LLMGateway` choke point (`src/intelligence/gateway.py`) and schemas (`src/intelligence/schemas.py`) enforcing `ScannerShortlist` gating, NY-session distinct-ticker and call caps, SHA-256 caching, Postgres quota persistence, and the exhaustive fail-closed `VETO` matrix (`C-LLM-05`).
- [ ] **Dependencies:** Slice 1, Slice 3, Slice 6.
- [ ] **Expected files:** `src/intelligence/__init__.py`, `src/intelligence/schemas.py`, `src/intelligence/gateway.py`, `tests/unit/test_quota_gate.py`, `tests/unit/test_llm_contract.py`, `tests/integration/test_quota_persistence.py`.
- [ ] **TDD Step 1 (Red):** Write failing quota tests in `tests/unit/test_quota_gate.py`, contract/fail-closed matrix tests in `tests/unit/test_llm_contract.py`, and persistence tests in `tests/integration/test_quota_persistence.py`.
- [ ] **TDD Step 2 (Green):** Implement `src/intelligence/gateway.py` and update `src/intelligence/schemas.py`.
- [ ] **Verification:** `pytest tests/unit/test_quota_gate.py tests/unit/test_llm_contract.py tests/constraints/test_schema_conventions.py`

---

## Slice 8: Financial Event & News Intelligence Pipeline (`src/intelligence/`)
- [ ] **Objective:** Harden untrusted text sanitization (`src/intelligence/sanitizer.py`) against prompt injection (`>= 20` adversarial payloads) and wire `ContextualIntelligenceAnalyzer` (`src/intelligence/analyzer.py`) with citation verification, Python red-flag override, and 100% coverage.
- [ ] **Dependencies:** Slice 5, Slice 7.
- [ ] **Expected files:** `src/intelligence/sanitizer.py`, `src/intelligence/analyzer.py`, `tests/fixtures/injection_corpus.jsonl`, `tests/unit/test_intelligence_veto.py`, `tests/unit/test_llm_contract.py`.
- [ ] **TDD Step 1 (Red):** Create `tests/fixtures/injection_corpus.jsonl` and write failing tests `test_adversarial_corpus` and `test_red_flag_overrides_model_approve` in `tests/unit/test_llm_contract.py` & `tests/unit/test_intelligence_veto.py`.
- [ ] **TDD Step 2 (Green):** Implement NFKC/bidi/HTML/fence sanitization in `sanitizer.py` and integrate `LLMGateway` + red-flag/citation rules in `analyzer.py`.
- [ ] **Verification:** `pytest tests/unit/test_intelligence_veto.py tests/unit/test_llm_contract.py --cov=src/intelligence --cov-branch --cov-report=term-missing --cov-fail-under=100`

---

## Slice 9: Fundamental Analysis & SEC Filing Metrics (`src/fundamentals/`)
- [ ] **Objective:** Implement PIT XBRL fact-to-acceptance joining (`C-PIT-06`), amendment/restatement isolation (`C-PIT-07`), Form 4 acceptance gating (`C-PIT-08`), `F_health` solvency scoring, and fail-closed 3-session `EarningsBlackout` (`src/fundamentals/`).
- [ ] **Dependencies:** Slice 4, Slice 5.
- [ ] **Expected files:** `src/fundamentals/__init__.py`, `src/fundamentals/xbrl_parser.py`, `src/fundamentals/earnings_calendar.py`, `tests/unit/test_fundamentals_pit.py`.
- [ ] **TDD Step 1 (Red):** Write failing tests in `tests/unit/test_fundamentals_pit.py` (`test_fact_acceptance_join_by_accession`, `test_unjoinable_fact_falls_back_to_next_session_after_filed`, `test_amendment_not_visible_before_its_acceptance`, `test_form4_gated_by_acceptance_not_transaction_date`).
- [ ] **TDD Step 2 (Green):** Update `src/fundamentals/xbrl_parser.py` and `src/fundamentals/earnings_calendar.py`.
- [ ] **Verification:** `pytest tests/unit/test_fundamentals_pit.py --cov=src/fundamentals --cov-branch --cov-report=term-missing --cov-fail-under=90`

---

## Slice 10: The Three Contrarian Signal Engines & Ensemble Ranker (`src/strategies/`)
- [ ] **Objective:** Implement the three contrarian scoring engines and composite ranker (`src/strategies/engines.py`) enforcing zero weight for `"unverified"` claims (`C-LLM-04`), missing-data penalties/vetoes (`C-PIT-14`), and deterministic gate precedence over LLM `APPROVE` (`C-LLM-08`).
- [ ] **Dependencies:** Slice 6, Slice 8, Slice 9.
- [ ] **Expected files:** `src/strategies/__init__.py`, `src/strategies/engines.py`, `tests/unit/test_strategies.py`, `tests/unit/test_llm_contract.py`.
- [ ] **TDD Step 1 (Red):** Write failing tests `test_unverified_claims_have_zero_weight`, `test_missing_fundamentals_reduce_or_veto`, and `test_forced_approve_cannot_bypass_deterministic_gates`.
- [ ] **TDD Step 2 (Green):** Update `src/strategies/engines.py`.
- [ ] **Verification:** `pytest tests/unit/test_strategies.py tests/unit/test_llm_contract.py --cov=src/strategies --cov-branch --cov-report=term-missing --cov-fail-under=95`

---

## Slice 11: Historical Event Dataset & Walk-Forward Backtester (`src/backtesting/`)
- [ ] **Objective:** Implement `HistoricalDataAccessor` (`src/backtesting/dataset.py`) and the walk-forward backtester (`src/backtesting/engine.py`) enforcing `C-BT-01`..`C-BT-08` (manifest check, ubiquitous `SURVIVORSHIP_BIAS_WARNING`, 3-year static window limit, worst-2% `-100%` delisting stress test, conservative next-bar fills with stop-first rule, 60/20-session/40 walk-forward split with frozen config hash).
- [ ] **Dependencies:** Slice 2, Slice 6, Slice 9, Slice 10.
- [ ] **Expected files:** `src/backtesting/__init__.py`, `src/backtesting/dataset.py`, `src/backtesting/engine.py`, `tests/unit/test_backtest_and_api.py`, `tests/constraints/test_backtest_honesty.py`.
- [ ] **TDD Step 1 (Red):** Write all 12 failing backtest honesty tests in `tests/constraints/test_backtest_honesty.py`.
- [ ] **TDD Step 2 (Green):** Implement `src/backtesting/dataset.py` and expand `src/backtesting/engine.py`.
- [ ] **Verification:** `pytest tests/unit/test_backtest_and_api.py tests/constraints/test_backtest_honesty.py --cov=src/backtesting --cov-branch --cov-report=term-missing --cov-fail-under=90`

---

## Slice 12: Alpaca Paper Trading Bracket Order Adapter & Reconciliation (`src/execution/`)
- [ ] **Objective:** Complete `AlpacaPaperExecutionRouter` (`src/execution/alpaca_paper_adapter.py`) with injected clock, submit-time guard re-validation (`C-RISK-11`), startup broker reconciliation (`C-RISK-12`), atomic `OrderClass.BRACKET` construction (`C-RISK-02`), timeout/duplicate-ID reconciliation (`C-RISK-09`), and 100% test coverage.
- [ ] **Dependencies:** Slice 2, Slice 3.
- [ ] **Expected files:** `src/execution/__init__.py`, `src/execution/alpaca_paper_adapter.py`, `tests/unit/test_execution_safety.py`, `tests/constraints/test_architecture_boundaries.py`, `tests/integration/test_reconciliation.py`, `tests/paper/test_alpaca_sandbox.py`.
- [ ] **TDD Step 1 (Red):** Write failing tests in `tests/unit/test_execution_safety.py`, `tests/integration/test_reconciliation.py`, and `tests/paper/test_alpaca_sandbox.py`.
- [ ] **TDD Step 2 (Green):** Update `src/execution/alpaca_paper_adapter.py`.
- [ ] **Verification:** `pytest tests/unit/test_execution_safety.py tests/constraints/test_architecture_boundaries.py --cov=src/execution --cov-branch --cov-report=term-missing --cov-fail-under=100`

---

## Slice 13: Daily End-of-Day Orchestrator & Shadow Trading Runner (`scripts/`)
- [ ] **Objective:** Implement `DailyPipelineOrchestrator` (`src/orchestrator.py`) and CLI runners (`scripts/run_daily_pipeline.py`, `scripts/run_backtest.py`) executing the Two-Stage Funnel end-to-end in `RESEARCH` shadow mode by default.
- [ ] **Dependencies:** Slices 1–12.
- [ ] **Expected files:** `src/orchestrator.py`, `scripts/run_daily_pipeline.py`, `scripts/run_backtest.py`, `tests/unit/test_orchestrator.py`.
- [ ] **TDD Step 1 (Red):** Write failing end-to-end pipeline unit tests in `tests/unit/test_orchestrator.py`.
- [ ] **TDD Step 2 (Green):** Implement `src/orchestrator.py`, `scripts/run_daily_pipeline.py`, and `scripts/run_backtest.py`.
- [ ] **Verification:** `pytest tests/unit/test_orchestrator.py tests/constraints/test_backtest_honesty.py`

---

## Slice 14: Streamlit Research & Audit Dashboard (`dashboard/` & `src/api/`)
- [ ] **Objective:** Implement read-only FastAPI endpoints (`src/api/app.py`) and Streamlit research & audit views (`dashboard/app.py`) with zero embedded business/sizing logic (`C-CQ-05`) and mandatory survivorship-bias warning banners (`C-BT-02`).
- [ ] **Dependencies:** Slices 1–13.
- [ ] **Expected files:** `src/api/__init__.py`, `src/api/app.py`, `dashboard/app.py`, `tests/unit/test_backtest_and_api.py`.
- [ ] **TDD Step 1 (Red):** Write failing API/dashboard view tests in `tests/unit/test_backtest_and_api.py`.
- [ ] **TDD Step 2 (Green):** Update `src/api/app.py` and `dashboard/app.py`, then run full Gate A verification.
- [ ] **Verification:** `ruff check src tests dashboard && ruff format --check src tests dashboard && mypy && pytest -m "not integration and not paper_gate and not network and not perf" --cov=src --cov-branch --cov-report=term-missing --cov-fail-under=85`
