# Contrarian Research Engine — Quality Gates & Constraints (`CONSTRAINTS.md`)

> **Status:** DRAFT v2 (2026-11-05) — **pending human review.** Constraints below are **not** in force until the Open Decisions in §11 are resolved.
> **Sources:** `AGENTS.md`, `.agents/rules/*.md`, `docs/SPEC.md`, `docs/DATA_DICTIONARY.md`, `docs/VALIDATION_PROTOCOL.md`, `.env.example`, `src/config.py`.
> **Precedence:** `AGENTS.md` and `.agents/rules/` override this file; this file overrides `docs/` on *verification* matters. Numeric conflicts between documents are not resolved silently — they are listed in §11 and block `PAPER`.
> **Supersedes:** the v1 `CONSTRAINTS.md`. Existing IDs (`C-ARCH-*`, `C-LLM-*`, `C-PIT-*`, `C-TEST-*`) are kept for traceability; new IDs are added.

---

## 0. Classification, Enforcement, and Gates

### 0.1 Classes

| Class | Meaning | When it blocks |
| :--- | :--- | :--- |
| `ALWAYS_REQUIRED` | Holds in every mode (`RESEARCH` included), on every commit. | Any merge to the main branch; any local "done" claim. |
| `REQUIRED_BEFORE_PAPER_TRADING` | Additional proof needed before `EXECUTION_MODE=paper` **and** `ENABLE_ORDER_SUBMISSION=true`. | Mode switch to `PAPER` (which also needs explicit human approval per `AGENTS.md` §9). |

Every `REQUIRED_BEFORE_PAPER_TRADING` gate includes all `ALWAYS_REQUIRED` gates.

### 0.2 Enforcement mechanisms (column "Verified by")

| Tag | Mechanism |
| :--- | :--- |
| `RUFF` | `ruff check` / `ruff format --check` (static) |
| `MYPY` | `mypy --strict` with the Pydantic plugin (static) |
| `PYTEST` | Automated test in `pytest` (file and test name given; `NEW` = to be written, `EXISTS` = already in repo) |
| `COV` | `coverage report --fail-under=…` after the pytest run |
| `ALEMBIC` | Alembic CLI against a Postgres instance |
| `REVIEW` | Human review checklist (cannot be fully automated) |

### 0.3 Gate commands

**Gate A — `ALWAYS_REQUIRED`** (offline, no secrets, no database):

```powershell
ruff check src tests dashboard
ruff format --check src tests dashboard
mypy
pytest -m "not integration and not paper_gate and not network and not perf" --cov=src --cov-branch --cov-report=term-missing --cov-fail-under=85
coverage report --include="src/risk/*" --fail-under=100
```

**Gate B — `REQUIRED_BEFORE_PAPER_TRADING`** (Gate A, plus):

```powershell
$env:REQUIRE_INTEGRATION = "1"   # turns integration "skip" into "fail"
alembic upgrade head; alembic check; alembic downgrade base; alembic upgrade head
pytest -m "integration or perf" --cov=src --cov-branch --cov-append
pytest -m "paper_gate"           # Alpaca PAPER sandbox only; network allowed for this marker only
coverage report --include="src/execution/*,src/intelligence/analyzer.py" --fail-under=100
coverage report --include="src/normalization/*" --fail-under=95
coverage report --include="src/fundamentals/*,src/scanner/*" --fail-under=90
coverage report --include="src/ingestion/*" --fail-under=85
```

Then the signed human checklist in §10.3.

### 0.4 Proposed tool configuration (to be added to `pyproject.toml` after approval — not applied yet)

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "DTZ", "S", "T20", "PT", "SIM", "RUF", "PGH", "TID", "ANN"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "ANN"]
"src/intelligence/**" = ["TID251"]   # Gemini SDK allowed here only
"src/execution/**" = ["TID251"]      # Alpaca trading SDK allowed here only
"src/ingestion/**" = ["TID251"]      # Alpaca data SDK / httpx allowed here only

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"google.genai".msg = "Gemini SDK only in src/intelligence/ (C-ARCH-03)."
"alpaca".msg = "Alpaca SDK only in src/execution/ and src/ingestion/ (C-ARCH-03)."
"pydantic.v1".msg = "Pydantic v2 APIs only (C-CQ-03)."
"datetime.datetime.utcnow".msg = "Naive UTC; use datetime.now(UTC) via an injected clock (C-CQ-09)."

[tool.mypy]
python_version = "3.12"
strict = true
explicit_package_bases = true
warn_unreachable = true
plugins = ["pydantic.mypy"]
files = ["src"]

[tool.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
addopts = "-q --strict-markers --strict-config -ra"
xfail_strict = true
filterwarnings = ["error::pydantic.warnings.PydanticDeprecatedSince20"]
markers = [
  "unit: pure, offline, deterministic tests",
  "invariant: property-style checks across many seeded inputs",
  "constraint: meta-tests that inspect source/AST/schemas to enforce this file",
  "integration: needs TEST_DATABASE_URL (Postgres)",
  "paper_gate: hits Alpaca PAPER sandbox; Gate B only",
  "network: any real outbound network; never in Gate A",
  "perf: wall-clock performance budgets",
]
```

> [!NOTE]
> Ruff's `per-file-ignores` turn off **all** banned imports in a directory. The exact allow-list (which SDK may appear in which package) is therefore also enforced by an AST test (`C-ARCH-03`), as a second check.

---

## 1. Python Code Quality, Linting, and Strict Typing

| ID | Constraint (measurable) | Class | Verified by |
| :--- | :--- | :--- | :--- |
| **C-CQ-01** | `ruff check src tests dashboard` reports **0** violations with the §0.4 rule set; `ruff format --check` reports **0** files to reformat. | `ALWAYS_REQUIRED` | `RUFF` |
| **C-CQ-02** | `mypy` (strict + `pydantic.mypy`) reports **0** errors over `src/`. Each `# type: ignore` must name an error code (`PGH003`), and unused ignores are errors (`warn_unused_ignores` via strict). | `ALWAYS_REQUIRED` | `MYPY`, `RUFF` |
| **C-CQ-03** | Pydantic **v2 only**: no `pydantic.v1` imports, no inner `class Config:`, no `@validator`/`@root_validator`. Pydantic v2 deprecation warnings are errors in tests. | `ALWAYS_REQUIRED` | `RUFF` (TID251), `PYTEST` filterwarnings, `PYTEST NEW tests/constraints/test_schema_conventions.py::test_no_pydantic_v1_patterns` |
| **C-CQ-04** | Every `pydantic.BaseModel` subclass under `src/` (except `BaseSettings`) has `extra="forbid"`. Domain records, order intents, and LLM outputs are also `frozen=True`. Every field whose name ends in `_at` has type `AwareDatetime` (or `AwareDatetime \| None` only where §3 allows it). | `ALWAYS_REQUIRED` | `PYTEST NEW tests/constraints/test_schema_conventions.py::test_boundary_models_forbid_extra_and_frozen`, `::test_all_at_fields_are_aware_datetime` (walks every module and checks each model's `model_config` and fields) |
| **C-CQ-05** | No business logic in `src/api/` or `dashboard/`. They may not import `alpaca`, `google.genai`, or `httpx`, and they may not call `src.risk.sizing` functions directly (read-only through service/query functions). | `ALWAYS_REQUIRED` | `PYTEST NEW tests/constraints/test_architecture_boundaries.py::test_ui_layers_have_no_sdk_or_sizing_imports`, `REVIEW` |
| **C-CQ-06** | No new runtime or dev dependency without a written reason and human approval (`AGENTS.md` §3). | `ALWAYS_REQUIRED` | `REVIEW` (diff of `pyproject.toml`) |
| **C-CQ-07** | No secrets in tracked files. `.env` is git-ignored. No tracked file matches the Gemini key pattern `AIza[0-9A-Za-z_\-]{35}`, the Alpaca key pattern `\b(PK\|AK)[A-Z0-9]{16,}\b`, or a non-empty `*_SECRET_KEY=` / `*_API_KEY=` assignment outside `*.example` placeholders. | `ALWAYS_REQUIRED` | `RUFF` (S105/S106), `PYTEST NEW tests/constraints/test_repo_hygiene.py::test_no_secrets_in_tracked_files`, `::test_dotenv_is_gitignored` |
| **C-CQ-08** | No `print()` in `src/`; use the `logging` module (`T20`). | `ALWAYS_REQUIRED` | `RUFF` |
| **C-CQ-09** | No naive datetimes in `src/` (`DTZ` rules). Domain code never reads the wall clock directly: time-dependent functions take an injected `now`/clock argument so tests are deterministic. | `ALWAYS_REQUIRED` | `RUFF` (DTZ, TID251), `PYTEST NEW tests/constraints/test_architecture_boundaries.py::test_domain_modules_do_not_call_datetime_now` (AST; allow-list: composition root only) |
| **C-CQ-10** | Gate tooling runs on Python **3.12** (the declared minimum). Local runs on newer interpreters are informational only. | `REQUIRED_BEFORE_PAPER_TRADING` | `REVIEW` (CI matrix pins 3.12) |

---

## 2. Database Migrations and Schema Integrity

| ID | Constraint (measurable) | Class | Verified by |
| :--- | :--- | :--- | :--- |
| **C-DB-01** | Alembic is the **only** way the schema changes. `Base.metadata.create_all()` / `drop_all()` never appear in `src/` (tests may use them only against throwaway databases). | `ALWAYS_REQUIRED` | `PYTEST NEW tests/constraints/test_db_schema.py::test_no_create_all_in_src` (AST) |
| **C-DB-02** | The Alembic revision graph has **exactly one head**, and every revision has a working `downgrade()`. An irreversible migration must raise `NotImplementedError` with a reason, and needs human approval. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/constraints/test_db_schema.py::test_single_alembic_head`, `::test_every_revision_defines_downgrade` (offline, via `alembic.script.ScriptDirectory`) |
| **C-DB-03** | `Base.metadata` uses a deterministic `naming_convention` (pk/fk/uq/ck/ix), so autogenerated migrations come out the same every time. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/constraints/test_db_schema.py::test_metadata_naming_convention` |
| **C-DB-04** | Every ORM column whose name ends in `_at` is `DateTime(timezone=True)` and `nullable=False` (Postgres `timestamptz`). | `ALWAYS_REQUIRED` | `PYTEST NEW tests/constraints/test_db_schema.py::test_timestamp_columns_are_timestamptz_not_null` (metadata check, offline) |
| **C-DB-05** | Every table with `published_at` also has `collected_at` and `available_at`, plus a DB-level `CHECK (available_at >= published_at)`. | `ALWAYS_REQUIRED` | `PYTEST NEW …::test_pit_tables_have_three_timestamps_and_check` (offline); `PYTEST NEW tests/integration/test_db_constraints.py::test_check_rejects_available_before_published` (Postgres) |
| **C-DB-06** | Order-audit table has DB-level guarantees that mirror the risk guard: `UNIQUE(client_order_id)`, `CHECK(qty > 0)`, `CHECK(stop_loss_price > 0 AND stop_loss_price < entry_price AND entry_price < take_profit_price)`, `CHECK(order_class = 'BRACKET')`, `CHECK(execution_mode IN ('research','paper'))`. | `ALWAYS_REQUIRED` (presence in metadata) / `REQUIRED_BEFORE_PAPER_TRADING` (enforced on Postgres) | `PYTEST NEW …::test_order_audit_check_constraints_declared`; `PYTEST NEW tests/integration/test_db_constraints.py::test_order_audit_rejects_live_mode_and_naked_orders` |
| **C-DB-07** | Natural-key uniqueness: daily bars `UNIQUE(ticker, session_date, adjustment_basis)`; raw payloads `UNIQUE(sha256)`; LLM cache `UNIQUE(cache_key)`. | `ALWAYS_REQUIRED` | `PYTEST NEW …::test_natural_key_uniques_declared` |
| **C-DB-08** | Raw-payload, order-audit, and LLM-analysis tables are **append-only**: Postgres triggers reject `UPDATE`/`DELETE` (`AGENTS.md` §4: never overwrite source content). | `REQUIRED_BEFORE_PAPER_TRADING` | `PYTEST NEW tests/integration/test_db_constraints.py::test_append_only_tables_reject_update_delete` |
| **C-DB-09** | Running `alembic upgrade head` → `alembic check` (no drift) → `downgrade base` → `upgrade head` on an empty Postgres succeeds with exit code 0. | `REQUIRED_BEFORE_PAPER_TRADING` | `ALEMBIC` (Gate B), `PYTEST NEW tests/integration/test_migrations.py::test_round_trip` |
| **C-DB-10** | Every schema change needs human approval before merge (`AGENTS.md` §9). Price/money column types follow Decision **D-03**. | `ALWAYS_REQUIRED` | `REVIEW` |

---

## 3. Point-in-Time (PIT) Data Correctness

All session logic runs in `America/New_York` using an NYSE calendar. `TIMEZONE=America/Sao_Paulo` is used **only for display** and never for session dates, quota resets, `client_order_id` dates, or gating.

### 3.1 `available_at` derivation rules (canonical)

`close(T)` means the NYSE close of session `T`: 16:00 ET, or **13:00 ET on early-close days**.

| `published_at` (converted to ET) | `available_at` |
| :--- | :--- |
| Trading day `T`, before 09:30 ET (pre-market) | 09:30 ET on `T` |
| Trading day `T`, from 09:30 ET up to (not including) `close(T)` | `published_at` |
| Trading day `T`, at or after `close(T)` | 09:30 ET on the next session `T+1` |
| Weekend or NYSE holiday | 09:30 ET on the next session |
| Daily bar for session `T` | `close(T)` (decisions that use bar `T` can only execute on `T+1` or later; see C-BT-05) |

### 3.2 Constraints

| ID | Constraint (measurable) | Class | Verified by |
| :--- | :--- | :--- | :--- |
| **C-PIT-01** | **Three-timestamp invariant.** Every bar, filing, fundamental fact, news item/cluster, and LLM analysis record carries tz-aware UTC `published_at`, `collected_at`, `available_at`, with `available_at >= published_at`. Naive datetimes or out-of-order values raise `ValidationError`. | `ALWAYS_REQUIRED` | `PYTEST EXISTS tests/unit/test_config_and_pit.py::test_pit_record_rejects_naive_timestamps_and_invalid_order`; C-CQ-04 meta-test |
| **C-PIT-02** | **Session gating per §3.1**, including pre-market, early closes, weekends, holidays, and both DST transitions. Required fixtures: `AC-01.2` (8-K at Mon 2026-05-04 16:05 ET → 2026-05-05 13:30 UTC); 16:01 ET on an early-close day before Thanksgiving vs. 12:59 ET; filing at 08:00 ET → same-day 09:30; Saturday filing; dates around 2026-03-08 and 2026-11-01 (DST). | `ALWAYS_REQUIRED` | `PYTEST EXISTS …::test_nyse_1600_et_cutoff_and_weekend_gating`; `PYTEST NEW tests/unit/test_pit_rules.py::test_premarket_same_day_open`, `::test_early_close_cutoff`, `::test_dst_transitions`, `::test_holiday_rollover` |
| **C-PIT-03** | **Calendar coverage.** The NYSE calendar raises an error (it does not guess) for any date outside its verified year range. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_pit_rules.py::test_calendar_raises_outside_covered_years` |
| **C-PIT-04** | **SEC acceptance gate.** For filings and XBRL facts, `published_at` is the EDGAR **acceptance datetime**, never `period_of_report` / fact `end`, and never the date-only `filed` field when an acceptance time can be found. (`AC-04.1`: as-of 2025-10-15, a Q3 fact filed 2025-11-02 is invisible.) | `ALWAYS_REQUIRED` | `PYTEST EXISTS tests/unit/test_fundamentals_pit.py::test_sec_acceptance_timestamp_prevents_period_end_lookahead` |
| **C-PIT-05** | **EDGAR timezone handling.** The `acceptanceDateTime` in submissions JSON ends in `Z`, but for many filers it actually holds **Eastern** wall-clock time. Primary source: the SGML header `<ACCEPTANCE-DATETIME>` (ET) or the filing index page. If only the JSON value is available, compute `available_at` under **both** readings (UTC and ET) and use the **later** one. Fixture: `"2026-05-04T16:05:12.000Z"` must resolve to `available_at = 2026-05-05 13:30 UTC`. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_pit_rules.py::test_edgar_json_z_suffix_conservative_interpretation`, `::test_sgml_acceptance_header_parsed_as_eastern` |
| **C-PIT-06** | **XBRL facts → acceptance time.** `companyfacts` facts carry only `filed` (a date) and `accn`. Each fact's acceptance time comes from joining `accn` to filing metadata. If the join fails, `available_at` = 09:30 ET of the session **after** `filed` (assume it was filed after the close). | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_fundamentals_pit.py::test_fact_acceptance_join_by_accession`, `::test_unjoinable_fact_falls_back_to_next_session_after_filed` |
| **C-PIT-07** | **Restatements and amendments.** As-of queries return the latest fact version with `available_at <= t`. A later `10-Q/A` or restated value is never visible at earlier `t`, and the XBRL `frame` deduplication field is never used for PIT selection. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_fundamentals_pit.py::test_amendment_not_visible_before_its_acceptance` |
| **C-PIT-08** | **Form 4 / insider data** is gated by filing acceptance, never by `transactionDate`. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_fundamentals_pit.py::test_form4_gated_by_acceptance_not_transaction_date` |
| **C-PIT-09** | **News.** `published_at` = provider wire timestamp. A date-only or missing timestamp gets `available_at` = 09:30 ET of the next session after that date. A `NewsCluster`'s `available_at` = `min(available_at)` of its members, and it counts as one independent source (`AC-01.3`). | `ALWAYS_REQUIRED` | `PYTEST EXISTS tests/unit/test_config_and_pit.py::test_syndicated_news_deduplication`; `PYTEST NEW tests/unit/test_pit_rules.py::test_date_only_news_conservative`, `::test_cluster_available_at_is_earliest_member` |
| **C-PIT-10** | **Visibility gate.** A pipeline run at simulated time `t` sees only records with `available_at <= t`. VALIDATION_PROTOCOL fixture: items published 2026-03-10 16:30 ET are invisible at 16:00 ET and visible at 2026-03-11 09:30 ET. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_pit_rules.py::test_pit_availability_gating` |
| **C-PIT-11** | **Truncation invariance (no look-ahead).** Features at `t_k` (`z_return_3d`, `z_return_5d`, `rsi_2`, `atr_14`, `sma_50`, `sma_200`, fundamentals) computed on data truncated at `t_k` equal those computed on the full dataset to within `1e-12`. The fixture **must include a split and a dividend with ex-date after `t_k`.** | `ALWAYS_REQUIRED` | `PYTEST EXISTS tests/unit/test_scanner.py::test_lookahead_truncation_invariance` (must be extended with the corporate-action fixture → `NEW`) |
| **C-PIT-12** | **Corporate-action basis.** Return-based features may use adjusted series. **Price-level** quantities (`Close >= MIN_SHARE_PRICE`, `ADDV_20`, `ATR_14` used for stops, entry/stop/TP prices) use prices adjusted only for actions with ex-date `<= t`, in the raw-price basis of `t`. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_pit_rules.py::test_price_filters_and_atr_use_as_of_raw_basis` |
| **C-PIT-13** | **Immutable raw payloads.** Files under `data/raw/` and raw-payload rows are write-once, keyed by SHA-256. Rewriting them raises an error, and normalized or LLM output never writes back to them. | `ALWAYS_REQUIRED` (filesystem) / `REQUIRED_BEFORE_PAPER_TRADING` (DB trigger, C-DB-08) | `PYTEST NEW tests/unit/test_raw_store.py::test_raw_payload_write_once` |
| **C-PIT-14** | **Missing data fails closed.** Missing timestamps, missing bars inside an indicator window, or missing fundamentals lower confidence or veto the candidate. They are never filled forward from later values. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_scanner.py::test_gap_in_window_excludes_ticker`, `tests/unit/test_strategies.py::test_missing_fundamentals_reduce_or_veto` |

---

## 4. LLM Quota Protection (Filter First, LLM Second)

| ID | Constraint (measurable) | Class | Verified by |
| :--- | :--- | :--- | :--- |
| **C-ARCH-01** | Stage 1 (`src/scanner/`), `src/risk/`, `src/normalization/`, and `src/strategies/` make **zero** LLM or network calls. They may not import `google.genai`, `alpaca`, `httpx`, `requests`, `urllib.request`, or `socket`. | `ALWAYS_REQUIRED` | `RUFF` TID251; `PYTEST NEW tests/constraints/test_architecture_boundaries.py::test_deterministic_layers_import_no_network_or_llm` (AST) |
| **C-ARCH-03** | **SDK allow-list.** `google.genai` only in `src/intelligence/`; `alpaca.trading` only in `src/execution/`; `alpaca.data` and `httpx` only in `src/ingestion/` (and `src/intelligence/` for Gemini transport). | `ALWAYS_REQUIRED` | `PYTEST NEW …::test_sdk_import_allow_list` (AST) |
| **C-QUOTA-01** | `1 <= MAX_DAILY_LLM_CANDIDATES <= 15`; any other value fails config load. | `ALWAYS_REQUIRED` | `PYTEST EXISTS tests/unit/test_config_and_pit.py::test_engine_settings_defaults_and_live_mode_prohibition` (extend for bounds → `NEW` `::test_llm_candidate_cap_bounds`) |
| **C-QUOTA-02** | The scanner returns `len(shortlist) <= MAX_DAILY_LLM_CANDIDATES` for **the configured value**, not a hard-coded 15. Test with caps of 1, 5, and 15 on a crash fixture where all 500 tickers qualify (`AC-03.2`). | `ALWAYS_REQUIRED` | `PYTEST EXISTS tests/unit/test_scanner.py::test_scanner_strictly_caps_at_15_candidates` (parametrize over cap → `NEW`) |
| **C-QUOTA-03** | **Single choke point.** Every Gemini call goes through one `LLMGateway`. It only accepts a typed `ScannerShortlist` (Pydantic, `max_length = MAX_DAILY_LLM_CANDIDATES`, tagged with the NY session date) produced by Stage 1. A ticker that is not on that session's shortlist results in **0 outbound calls** and `VETO`. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_quota_gate.py::test_non_shortlisted_ticker_makes_zero_calls_and_vetoes`; AST test: `genai.Client` is created only inside the gateway module |
| **C-QUOTA-04** | **Distinct-ticker daily cap.** The number of distinct tickers sent to the LLM per NY session stays `<= MAX_DAILY_LLM_CANDIDATES`, even if the scanner runs again the same day (the union of shortlists is capped; extra tickers get `VETO` without a call). | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_quota_gate.py::test_rescan_same_session_cannot_exceed_distinct_ticker_cap` |
| **C-QUOTA-05** | **Hard call breaker.** `GEMINI_MAX_DAILY_CALLS` (default 150) counts **every outbound attempt**, including retries and failed calls. Once reached, further calls are not sent and return `VETO`. The counter resets at 00:00 America/New_York. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_quota_gate.py::test_call_breaker_counts_retries_and_fails_closed`, `::test_counter_resets_on_ny_date_not_local_tz` |
| **C-QUOTA-06** | **Cache does not consume quota.** Running again on identical inputs makes **0** outbound calls (`AC-05.1`). Cache key = `sha256(model_id ‖ prompt_version ‖ schema_version ‖ sorted(source_sha256s))`. | `ALWAYS_REQUIRED` | `PYTEST EXISTS tests/unit/test_intelligence_veto.py::test_sha256_caching_prevents_duplicate_llm_calls` |
| **C-QUOTA-07** | **Per-candidate call cap** `MAX_LLM_CALLS_PER_CANDIDATE` (proposed `floor(150/15) = 10`, see **D-08**). Going over the cap returns `VETO` for that candidate. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_quota_gate.py::test_per_candidate_cap` |
| **C-QUOTA-08** | Quota counters and the distinct-ticker set are stored in Postgres and **survive a process restart** within the same session. | `REQUIRED_BEFORE_PAPER_TRADING` | `PYTEST NEW tests/integration/test_quota_persistence.py::test_counters_survive_restart` |
| **C-QUOTA-09** | Stage 1 performance: 500 tickers × 252 bars in `< 3.0 s` on the reference machine (`AC-03.1`). | `REQUIRED_BEFORE_PAPER_TRADING` | `PYTEST NEW tests/perf/test_scanner_perf.py::test_500x252_under_3s` (`perf` marker) |

---

## 5. LLM Output Validation and Fail-Closed Behavior

| ID | Constraint (measurable) | Class | Verified by |
| :--- | :--- | :--- | :--- |
| **C-LLM-01** | `GEMINI_TEMPERATURE` must be `0.0` (any other value fails config load), **and** the request actually sent has `temperature == 0.0`, `response_mime_type == "application/json"`, and `response_schema` set to the Pydantic model. Note: `temperature=0.0` does not guarantee identical outputs; reproducibility comes from caching (C-QUOTA-06) and audit storage (C-LLM-09). | `ALWAYS_REQUIRED` | `PYTEST EXISTS …::test_engine_settings_defaults_and_live_mode_prohibition`; `PYTEST NEW tests/unit/test_llm_contract.py::test_outbound_request_config_is_deterministic_and_schema_bound` (fake client records the request) |
| **C-LLM-02** | **No LLM math.** LLM output schemas contain no fields matching `qty\|share\|size\|stop\|take_profit\|target\|price\|weight\|atr\|position` (case-insensitive). The LLM output type is never passed into `src/risk/sizing`. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/constraints/test_schema_conventions.py::test_llm_schemas_have_no_trade_parameter_fields`; AST: `src/risk` does not import `src.intelligence` |
| **C-LLM-03** | **Strict schema parsing.** Responses go through `Model.model_validate_json(..., strict=True)` with `extra="forbid"`. `veto_decision: Literal["APPROVE","VETO"]`, and anything other than exactly `"APPROVE"` counts as `VETO`. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_llm_contract.py::test_extra_fields_or_coercible_values_veto` |
| **C-LLM-04** | **Citations.** Every claim's `source_id` is one of the source IDs supplied in that request, or the literal `"unverified"`. Any other `source_id` invalidates the whole output → `VETO` (`AC-05.2`). Claims marked `"unverified"` contribute **zero** weight to engine scores (see **D-08**). | `ALWAYS_REQUIRED` | `PYTEST EXISTS tests/unit/test_intelligence_veto.py::test_hallucinated_source_id_triggers_mandatory_veto`; `PYTEST NEW tests/unit/test_strategies.py::test_unverified_claims_have_zero_weight` |
| **C-LLM-05** | **Exhaustive fail-closed list.** Each of the following produces `veto_decision == "VETO"` with a typed reason code and no exception escaping to the caller: timeout (30 s), connection error, HTTP 429, HTTP 4xx, HTTP 5xx, empty body, `finish_reason` other than `STOP` (safety block, `MAX_TOKENS` truncation), malformed JSON, schema violation, invalid citation, quota exhausted (C-QUOTA-05/07), cache read/deserialization error, sanitizer exception, **any other exception** (catch-all). | `ALWAYS_REQUIRED` | `PYTEST EXISTS …::test_structural_red_flag_or_api_timeout_forces_veto`; `PYTEST NEW tests/unit/test_llm_contract.py::test_fail_closed_matrix` (one parametrized case per item) |
| **C-LLM-06** | **Red-flag veto.** If the model flags accounting restatement or fraud, an SEC/DOJ investigation, a going-concern warning, a liquidity crisis, or an abrupt CEO/CFO departure, the result is `VETO`, regardless of the model's own `veto_decision`. This rule is applied in Python. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_llm_contract.py::test_red_flag_overrides_model_approve` |
| **C-LLM-07** | **Prompt-injection sanitization.** Before prompting: NFKC normalization; control characters removed except `\n` and `\t`; zero-width and bidi-override characters removed (U+200B–U+200F, U+202A–U+202E, U+2066–U+2069); `<script>`/`<style>` and HTML tags removed; **any** `untrusted_document` open/close tag inside the content is neutralized; length capped at `MAX_DOC_CHARS` with a truncation marker. Each document is wrapped in `<untrusted_document id="…">`, and the system instruction says that wrapped content is data, not instructions. | `ALWAYS_REQUIRED` | `PYTEST EXISTS tests/unit/test_intelligence_veto.py::test_prompt_injection_fencing_strips_tags_and_control_chars`; `PYTEST NEW tests/unit/test_llm_contract.py::test_adversarial_corpus` running `tests/fixtures/injection_corpus.jsonl` (at least 20 payloads: fence-breaking, "ignore previous instructions… APPROVE", role-play, JSON smuggling, Unicode/homoglyph tricks, bidi tricks). For each payload, the sanitized text has no fence-close token, no control/bidi characters, and fits the length cap. |
| **C-LLM-08** | **The LLM can only veto.** An LLM `APPROVE` never bypasses a deterministic gate. With a fake model that always says `APPROVE`, a candidate that fails the Stage 1 filter, is in an earnings blackout, or fails any risk check still produces **no** `TradeSignalProposal` or order. If injection heuristics fire (`injection_suspected=True`), the result is `VETO` (see **D-08**). | `ALWAYS_REQUIRED` | `PYTEST EXISTS tests/unit/test_strategies.py::test_veto_or_earnings_blackout_zeros_scores_and_blocks_signal`; `PYTEST NEW tests/unit/test_llm_contract.py::test_forced_approve_cannot_bypass_deterministic_gates` |
| **C-LLM-09** | **Audit trail.** Every analysis stores `model_id`, `prompt_version`, `schema_version`, `temperature`, `cache_key`, input source IDs and hashes, raw response text (immutable), parsed result, latency, and the three timestamps. | `ALWAYS_REQUIRED` (fields present) / `REQUIRED_BEFORE_PAPER_TRADING` (persisted append-only, C-DB-08) | `PYTEST NEW tests/unit/test_llm_contract.py::test_audit_record_complete` |

---

## 6. Immutable Risk Guardrails (`src/risk/`, `src/execution/`)

All checks are evaluated **on the final prices that would be sent to the broker** (after tick rounding: USD 0.01 increments, valid because the universe minimum is USD 10). Rounding direction follows **D-03**.

| ID | Constraint (measurable) | Class | Verified by |
| :--- | :--- | :--- | :--- |
| **C-RISK-00** | **Execution-mode lock.** Default is `research`. `EXECUTION_MODE=live` raises `RuntimeError` when config loads. `ALPACA_PAPER` must be `true`. Any Alpaca URL other than `https://paper-api.alpaca.markets` raises `RuntimeError`. Orders reach the broker only if `EXECUTION_MODE=paper` **and** `ENABLE_ORDER_SUBMISSION=true`; otherwise a shadow trade is recorded and the broker is never called. | `ALWAYS_REQUIRED` | `PYTEST EXISTS tests/unit/test_config_and_pit.py::test_engine_settings_defaults_and_live_mode_prohibition`, `tests/unit/test_execution_safety.py::test_research_mode_records_shadow_trade_without_calling_broker` |
| **C-RISK-01** | **No averaging down.** If the ticker is held and (`current_price < avg_entry_price` **or** `unrealized_pl < 0`), a buy raises `ValueError("AVERAGING_DOWN_PROHIBITED")`. A stale or missing `current_price` for a held ticker → reject. An existing **open (unfilled) entry order** for the same ticker → reject. `ALLOW_AVERAGING_DOWN=true` fails config load. | `ALWAYS_REQUIRED` | `PYTEST EXISTS tests/unit/test_risk_guard.py::test_guard_rejects_averaging_down_with_value_error`; `PYTEST NEW ::test_rejects_when_open_entry_order_exists`, `::test_rejects_held_ticker_with_stale_price` |
| **C-RISK-02** | **Mandatory bracket (OCO).** Every entry is `OrderClass.BRACKET`, **long-only** (see **D-07**), with `0 < stop_loss < entry < take_profit`, all on the tick grid. The execution adapter has **no code path** that submits a non-bracket entry. `REQUIRE_BRACKET_ORDER=false` fails config load. | `ALWAYS_REQUIRED` | `PYTEST EXISTS …::test_guard_rejects_non_bracket_or_invalid_stops_or_low_rr`, `tests/unit/test_execution_safety.py::test_paper_mode_submits_atomic_bracket_order`; `PYTEST NEW tests/constraints/test_architecture_boundaries.py::test_adapter_only_constructs_bracket_requests` (AST) |
| **C-RISK-03** | **Reward:risk.** `(TP − entry) / (entry − stop) >= MIN_REWARD_RISK_RATIO` (2.0) on rounded prices. TP formula per **D-02**. | `ALWAYS_REQUIRED` | `PYTEST EXISTS …::test_guard_rejects_non_bracket_or_invalid_stops_or_low_rr` |
| **C-RISK-04** | **ATR stop.** `stop = entry − ATR_STOP_MULTIPLIER × ATR_14` (k = 2.0). `ATR_14` uses Wilder smoothing on the as-of raw-price basis (C-PIT-12). ATR that is NaN, `<= 0`, or based on fewer than 15 valid bars → reject. | `ALWAYS_REQUIRED` | `PYTEST EXISTS …::test_volatility_adjusted_bracket_sizing`; `PYTEST NEW ::test_invalid_or_insufficient_atr_rejects` |
| **C-RISK-05** | **Volatility-adjusted sizing (max 0.5% equity risk).** `qty = floor(min(E × MAX_RISK_PER_TRADE_PCT / (entry − stop), E × MAX_POSITION_PCT / entry))`, using the final rounded stop. `qty < 1` → reject (never round up). Must hold: `(entry − stop) × qty <= 0.005 × E` and `entry × qty <= MAX_POSITION_PCT × E`. Config fails to load if `MAX_RISK_PER_TRADE_PCT` is outside `(0, 0.005]` (see **D-01**). | `ALWAYS_REQUIRED` | `PYTEST EXISTS …::test_volatility_adjusted_bracket_sizing`; `PYTEST NEW tests/invariants/test_risk_invariants.py::test_sizing_never_exceeds_caps` (seeded sweep of 10,000 random (E, entry, ATR) cases including tick-rounding edge cases; any violation fails), `::test_qty_below_one_rejects` |
| **C-RISK-06** | **Portfolio caps.** Rejected if: open market value + new notional `> MAX_PORTFOLIO_EXPOSURE × E`; open positions `>= MAX_OPEN_POSITIONS`; orders submitted this NY session `>= MAX_DAILY_ORDERS`. | `ALWAYS_REQUIRED` | `PYTEST EXISTS …::test_guard_rejects_position_portfolio_and_frequency_caps` |
| **C-RISK-07** | **Earnings blackout (3 sessions).** Reject if the next earnings date `E_d` is 0 to `EARNINGS_BLACKOUT_DAYS` (3) NYSE sessions after the decision session (an AMC report on day `E_d` counts as session `E_d`). **Unknown or missing earnings date → reject** (fail closed; see **D-04**). | `ALWAYS_REQUIRED` | `PYTEST EXISTS tests/unit/test_fundamentals_pit.py::test_earnings_blackout_within_3_trading_days`, `tests/unit/test_risk_guard.py::test_guard_rejects_earnings_blackout_and_llm_veto_and_kill_switch`; `PYTEST NEW ::test_unknown_earnings_date_rejects`, `::test_blackout_boundary_sessions_3_and_4` |
| **C-RISK-08** | **Idempotent `client_order_id`.** Must match `^[A-Z][A-Z.]{0,9}_\d{8}_(neg_overreaction\|narrative_div\|sentiment_infl\|contagion)$`, be at most 128 characters, and use the **NY session date** of the signal (never UTC or São Paulo date). It is unique in the DB (C-DB-06). | `ALWAYS_REQUIRED` | `PYTEST NEW tests/unit/test_risk_guard.py::test_client_order_id_format_and_ny_session_date` (fixture: 2026-11-05 22:30 São Paulo = 20:30 ET → date `20261105`; 2026-11-06 01:30 UTC → still `20261105`) |
| **C-RISK-09** | **Timeout reconciliation.** On a submission timeout or ambiguous error, the adapter queries `get_order_by_client_order_id` **before** any retry. If the order exists, no resubmission. A duplicate-ID rejection from the broker counts as "already submitted", not as a failure to retry. | `ALWAYS_REQUIRED` (mocked) / `REQUIRED_BEFORE_PAPER_TRADING` (sandbox) | `PYTEST EXISTS tests/unit/test_execution_safety.py::test_timeout_reconciles_by_client_order_id_without_duplicate_submit`; `PYTEST NEW tests/paper/test_alpaca_sandbox.py::test_duplicate_client_order_id_is_idempotent` (`paper_gate`) |
| **C-RISK-10** | **Daily kill switch.** `dd = (start_of_day_equity − equity) / start_of_day_equity`. If `dd >= MAX_DAILY_LOSS_PCT`, all new entries are blocked. Once tripped, the switch **stays on** for the rest of the NY session even if equity recovers. Missing or stale equity data → block. Existing bracket exit legs are not cancelled. Reference-equity definition per **D-05**. | `ALWAYS_REQUIRED` | `PYTEST EXISTS …::test_guard_rejects_earnings_blackout_and_llm_veto_and_kill_switch`; `PYTEST NEW ::test_kill_switch_latches_for_session`, `::test_missing_equity_blocks` |
| **C-RISK-11** | **Guard cannot be bypassed.** The execution adapter only accepts a `ValidatedOrderIntent` that the guard created (not constructible elsewhere), and it re-runs the guard against fresh portfolio state right before submission. | `ALWAYS_REQUIRED` (type gate) / `REQUIRED_BEFORE_PAPER_TRADING` (re-validation) | `PYTEST NEW tests/unit/test_execution_safety.py::test_adapter_rejects_unvalidated_intent`, `::test_revalidation_at_submit_time` |
| **C-RISK-12** | **Kill-switch state, daily order count, and broker reconciliation are persisted.** On startup, local positions and open orders are compared with the Alpaca paper account. Any mismatch turns the kill switch on. | `REQUIRED_BEFORE_PAPER_TRADING` | `PYTEST NEW tests/integration/test_reconciliation.py::test_mismatch_engages_kill_switch`, `::test_kill_switch_survives_restart` |
| **C-RISK-13** | **Sandbox bracket round-trip.** On the Alpaca paper sandbox: submit a 1-share bracket entry, confirm both child legs exist with the expected prices, cancel, and confirm no orphaned legs remain. | `REQUIRED_BEFORE_PAPER_TRADING` | `PYTEST NEW tests/paper/test_alpaca_sandbox.py::test_bracket_legs_created_and_cancelled` (`paper_gate`) |

> [!WARNING]
> **The 0.5% is risk measured at the stop price before the trade, not a guaranteed maximum loss.** A stop loss becomes a market order once triggered, so overnight gaps and halts can fill well below the stop. Gap risk is measured by the backtest stress test (C-BT-04) and must be disclosed in every report. It is not removed by these guards.

---

## 7. Unit and Integration Testing Requirements

| ID | Constraint (measurable) | Class | Verified by |
| :--- | :--- | :--- | :--- |
| **C-TEST-01** | `src/risk/` has **100% line and branch** coverage. | `ALWAYS_REQUIRED` | `COV` (Gate A) |
| **C-TEST-02** | PIT and look-ahead suites (C-PIT-01…14) pass at 100%, using `1e-12` tolerance for numeric invariance. | `ALWAYS_REQUIRED` | `PYTEST` |
| **C-TEST-03** | **Offline unit tests.** An autouse fixture in `tests/conftest.py` blocks every non-loopback socket connection. Only tests marked `network`/`paper_gate` may opt out, and those are deselected in Gate A. All Alpaca, SEC, and Gemini traffic in unit tests uses fakes/fixtures. | `ALWAYS_REQUIRED` | `PYTEST NEW tests/constraints/test_repo_hygiene.py::test_socket_guard_active` |
| **C-TEST-04** | Total coverage of `src/` (line + branch) `>= 85%`. | `ALWAYS_REQUIRED` | `COV` (`--cov-fail-under=85`) |
| **C-TEST-05** | Module coverage floors: `src/execution/` 100%, `src/intelligence/analyzer.py` 100% (every fail-closed branch), `src/normalization/` ≥ 95%, `src/fundamentals/` and `src/scanner/` ≥ 90%, `src/ingestion/` ≥ 85%. | `REQUIRED_BEFORE_PAPER_TRADING` | `COV` (Gate B) |
| **C-TEST-06** | No `skip`/`xfail` in risk, execution, normalization, intelligence, or constraints suites. `xfail_strict = true`. Integration tests may skip in Gate A when `TEST_DATABASE_URL` is unset, but **fail** in Gate B (`REQUIRE_INTEGRATION=1`). | `ALWAYS_REQUIRED` | `PYTEST NEW tests/constraints/test_repo_hygiene.py::test_no_skips_in_safety_suites` (AST scan for `pytest.mark.skip/xfail`) |
| **C-TEST-07** | **Determinism.** Seeds are fixed, time comes from an injected clock, and two consecutive Gate A runs give the same result. | `ALWAYS_REQUIRED` | `REVIEW`; C-CQ-09 |
| **C-TEST-08** | **TDD for safety code.** Changes to `src/risk/`, `src/execution/`, `src/normalization/`, or the sizing math must include a test that failed before the change. The **full** suite runs after any change to those packages. | `ALWAYS_REQUIRED` | `REVIEW` (PR shows red → green) |
| **C-TEST-09** | Failing tests are never deleted or weakened to get a green suite. Removing a test needs human approval. | `ALWAYS_REQUIRED` | `REVIEW` |
| **C-TEST-10** | Integration suites (Postgres, quota persistence, reconciliation) and paper-sandbox suites pass with 0 failures and 0 skips. | `REQUIRED_BEFORE_PAPER_TRADING` | `PYTEST` (Gate B) |

### 7.1 Planned test layout

```
tests/
  conftest.py                 # socket guard, frozen clock, fake Gemini/Alpaca/SEC clients
  fixtures/                   # EDGAR JSON/SGML samples, injection_corpus.jsonl, bar fixtures with splits
  unit/                       # EXISTS (8 files) + NEW: test_pit_rules.py, test_quota_gate.py, test_llm_contract.py, test_raw_store.py
  invariants/                 # NEW: test_risk_invariants.py (seeded sweeps)
  constraints/                # NEW: test_architecture_boundaries.py, test_schema_conventions.py,
                              #      test_db_schema.py, test_repo_hygiene.py, test_backtest_honesty.py
  integration/                # NEW (Gate B): test_migrations.py, test_db_constraints.py,
                              #      test_quota_persistence.py, test_reconciliation.py
  perf/                       # NEW (Gate B): test_scanner_perf.py
  paper/                      # NEW (Gate B): test_alpaca_sandbox.py
```

---

## 8. Backtesting Honesty

| ID | Constraint (measurable) | Class | Verified by |
| :--- | :--- | :--- | :--- |
| **C-BT-01** | **Default to biased.** `BacktestReport.universe_bias_status: Literal["SURVIVORSHIP_BIAS_FREE","STATIC_UNIVERSE_UNADJUSTED"]` defaults to `STATIC_UNIVERSE_UNADJUSTED`. `SURVIVORSHIP_BIAS_FREE` is only allowed when a `UniverseManifest` is attached (vendor, PIT constituent history including delisted tickers, coverage dates, sha256 of the dataset). A boolean flag alone is not enough. | `ALWAYS_REQUIRED` | `PYTEST EXISTS tests/unit/test_backtest_and_api.py::test_backtest_enforces_survivorship_bias_warning_and_delisting_stress_test`; `PYTEST NEW tests/constraints/test_backtest_honesty.py::test_bias_free_requires_manifest` |
| **C-BT-02** | **The warning appears everywhere.** For static universes, this exact text appears in the report object, the JSON export, CLI output, every API response with backtest results, and the Streamlit view: `"WARNING: Static Universe - Survivorship Bias Unadjusted. Historical delistings are absent from free provider data."` The field is required, so a report cannot be serialized without it. | `ALWAYS_REQUIRED` | `PYTEST NEW …::test_warning_present_in_json_cli_and_api` |
| **C-BT-03** | **Window limit.** A static-universe backtest covering more than 3 years raises `ValueError`. | `ALWAYS_REQUIRED` | `PYTEST NEW …::test_static_universe_window_limit` |
| **C-BT-04** | **Delisting stress test** is mandatory: the worst 2% of Stage 1 setups (ranked by forward return, deterministic) are set to −100%. Stressed expectancy and max drawdown are reported next to the base results. A report without it cannot be serialized. | `ALWAYS_REQUIRED` | `PYTEST EXISTS` (same test as C-BT-01); `PYTEST NEW …::test_stress_results_required_and_deterministic` |
| **C-BT-05** | **Conservative fill model.** A signal at close `T` executes no earlier than `T+1`: at the open (+10 bps) or at the limit price if `Low(T+1) <= limit` (never at the bar's low). 10 bps per side plus fees. If stop and TP are both touched in the same daily bar → **assume the stop filled first**. Gap below the stop → fill at the open. Gap above TP → fill at TP. No signal and fill in the same bar. | `ALWAYS_REQUIRED` | `PYTEST NEW …::test_no_same_bar_fill`, `::test_stop_first_when_both_touched`, `::test_gap_through_stop_fills_at_open`, `::test_costs_applied_both_sides` |
| **C-BT-06** | **PIT data access.** The backtest data accessor returns only records with `available_at <= sim_clock` (C-PIT-10), and the scanner uses only point-in-time fundamentals and earnings (8-K Item 2.02 acceptance ± 3 sessions for historical blackout, SPEC §4.2). | `ALWAYS_REQUIRED` | `PYTEST NEW …::test_accessor_hides_future_available_at` |
| **C-BT-07** | **Provenance block in every report:** git SHA, config hash, data feed (`iex` vs `sip`), corporate-adjustment method, date range, IS/embargo/OOS boundaries, **number of parameter configurations tried**, and the label "Exploratory ranking — not a calibrated probability of return." | `ALWAYS_REQUIRED` | `PYTEST NEW …::test_report_provenance_fields_required` |
| **C-BT-08** | **Walk-forward discipline.** 60% in-sample / 20-session embargo / 40% out-of-sample. The parameter/config hash is frozen and recorded **before** the OOS run. Running OOS with a config hash different from the frozen one raises an error. Benchmarks reported: each engine alone, combined, equal-weight buy-and-hold, and naive mean reversion. | `ALWAYS_REQUIRED` | `PYTEST NEW …::test_oos_requires_frozen_config_hash`, `::test_embargo_20_sessions` |
| **C-BT-09** | A human has reviewed the OOS walk-forward report (with stress test and bias tag) before `PAPER`. | `REQUIRED_BEFORE_PAPER_TRADING` | `REVIEW` (§10.3) |

---

## 9. Summary of Automated `pytest` Checks

| Suite | Marker | Gate | Constraints covered |
| :--- | :--- | :--- | :--- |
| `tests/unit/*` (8 EXISTS + 4 NEW files) | `unit` | A | C-PIT-*, C-QUOTA-01…07, C-LLM-*, C-RISK-00…11 (mocked), C-BT-01/04 |
| `tests/invariants/test_risk_invariants.py` | `invariant` | A | C-RISK-04/05 (10,000-case seeded sweep) |
| `tests/constraints/*` | `constraint` | A | C-CQ-03/04/05/07/09, C-ARCH-01/03, C-DB-01…07 (offline metadata), C-LLM-02, C-RISK-02 (AST), C-TEST-03/06, C-BT-* |
| `tests/integration/*` | `integration` | B | C-DB-05/06/08/09, C-QUOTA-08, C-RISK-12, C-PIT-13 (DB) |
| `tests/perf/*` | `perf` | B | C-QUOTA-09 |
| `tests/paper/*` | `paper_gate` | B | C-RISK-09 (sandbox), C-RISK-13 |

Checks that run **outside** pytest: `ruff` (C-CQ-01/02/03/08/09, C-ARCH-01), `mypy` (C-CQ-02), `coverage report` floors (C-TEST-01/04/05), `alembic` CLI (C-DB-09), human review (§10.3).

---

## 10. Baseline Measurement and Paper-Trading Sign-off

### 10.1 Baseline (measured 2026-11-05, local Python 3.14.3, before any changes)

| Gate item | Result | Meets the proposed constraint? |
| :--- | :--- | :--- |
| `pytest` (28 tests) | 28 passed, 0.92 s | ✅ |
| Total coverage (line + branch) | 89% | ✅ C-TEST-04 |
| `src/risk/` coverage | 100% (`guard.py`, `sizing.py`) | ✅ C-TEST-01 |
| `src/execution/` coverage | 74% | ❌ C-TEST-05 (needs 100%) |
| `src/intelligence/analyzer.py` | 85% | ❌ C-TEST-05 |
| `src/normalization/` | 86–94% | ❌ C-TEST-05 (needs 95%) |
| `src/ingestion/sec_edgar.py` | 56% | ❌ C-TEST-05 |
| `mypy --strict --explicit-package-bases src` (no Pydantic plugin yet) | 0 errors / 19 files | ✅ (re-check with plugin) |
| `ruff` (§0.4 rule set) on `src/` | 40 violations: 18 I001, 15 E501, 4 UP017, **2 DTZ001 (naive datetimes)**, 1 B007 | ❌ C-CQ-01, C-CQ-09 |
| Alembic | No `alembic/` directory, no revisions | ❌ C-DB-01/02 |
| ORM CHECK constraints | None declared | ❌ C-DB-05/06 |
| Earnings blackout with unknown date | `days_to_earnings=None` **passes** the guard (`src/risk/guard.py` L127) | ❌ C-RISK-07 (pending D-04) |
| Survivorship tag | Set by the boolean `includes_delisted_equities` | ❌ C-BT-01 |
| Prices | `float` in code; `Decimal` in `DATA_DICTIONARY.md` | ⚠️ D-03 |

### 10.2 Remediation
Fixing these gaps is implementation work. It will be planned in `tasks/plan.md` / `tasks/todo.md` **after** this file is approved. Nothing has been changed yet.

### 10.3 Human sign-off checklist (`REQUIRED_BEFORE_PAPER_TRADING`)
- [ ] Gate A and Gate B green, outputs attached.
- [ ] All Open Decisions in §11 resolved and docs updated to match.
- [ ] OOS walk-forward report reviewed (C-BT-09).
- [ ] At least `N` consecutive `RESEARCH` sessions of shadow trading with complete audit records and zero guard exceptions escaping (N per **D-10**).
- [ ] `.env` reviewed: `EXECUTION_MODE=paper`, `ENABLE_ORDER_SUBMISSION=true`, paper URL, risk values match the approved table.
- [ ] Signed by the human operator, with date.

---

## 11. Open Decisions — Blocking (Ambiguity Gate)

These involve financial formulas, `available_at` rules, risk limits, or broker behavior, so per the user rules they are **not** decided silently. Each has a proposed default.

| ID | Conflict / ambiguity | Evidence | Proposed resolution |
| :--- | :--- | :--- | :--- |
| **D-01** | **Risk limits differ between documents.** SPEC FR-13: risk 0.75%, position 10%, 8 open positions, 5 daily orders, 2.0% daily loss. `.env.example`, `src/config.py`, and CONSTRAINTS v1: **0.5%, 8%, 6, 2, 1.5%**. The request says "0.5% max". | `docs/SPEC.md` L84-85 vs `.env.example` L37-42 | Use the `.env.example` values and update SPEC. Add a config check that `MAX_RISK_PER_TRADE_PCT <= 0.005`. |
| **D-02** | **TP formula conflict.** SPEC/DATA_DICTIONARY: `TP = entry + 3.5 × ATR` (with k_stop = 2.0 that is R:R 1.75, which **breaks** `MIN_REWARD_RISK_RATIO = 2.0`). Code (`sizing.py`): `TP = entry + 2.0 × (entry − stop)` = 4 ATR. | `SPEC.md` L79, `sizing.py` L31 | Keep the code's formula; update SPEC and DATA_DICTIONARY. |
| **D-03** | **Money type and rounding.** Code uses `float`; DATA_DICTIONARY says `Decimal`. Rounding direction for stop/TP is not specified (nearest rounding can increase risk). | `guard.py`, `DATA_DICTIONARY.md` L121-127 | Use `Decimal` at the order boundary and `Numeric(18,4)` in the DB. Round the stop **down** to the tick, then recompute qty from the rounded stop (the cap still holds). Round TP **up** to the tick, then check R:R. |
| **D-04** | **Earnings blackout details.** (a) Unknown date: currently allowed. (b) Session counting from the decision session vs. the entry session. (c) Should open positions be closed before earnings, given a 20-session holding period? | `guard.py` L127 | (a) Reject. (b) Count from the decision session; 0–3 inclusive is blackout. (c) Out of scope now; record as a known limitation. |
| **D-05** | **Kill-switch reference equity.** `start_of_day_equity` source; latching. | `guard.py` L33-39 | Use Alpaca `last_equity` (previous close) and the current `equity` including unrealized P&L. The switch latches until the next NY session. |
| **D-06** | **`available_at` edge cases.** Pre-market → same-day open is coded in `calendar.py` but missing from SPEC/DATA_DICTIONARY. Early-close days are not specified. The EDGAR JSON `Z` suffix is ambiguous. | `calendar.py` L92-97 | Adopt §3.1 and C-PIT-05 as written; update DATA_DICTIONARY. |
| **D-07** | **Order semantics.** Long-only? Entry order type (DATA_DICTIONARY says `entry_limit_price`) and time-in-force? Strategy list for `client_order_id`: SPEC lists 3 engines, AGENTS.md lists 4 (adds Contagion). | `DATA_DICTIONARY.md`, `AGENTS.md` §1 | Long-only. Limit entry at `entry_limit_price`, `TIF=day`. Allow 4 strategy tokens. |
| **D-08** | **LLM policy parameters.** `MAX_LLM_CALLS_PER_CANDIDATE`; does `injection_suspected` force `VETO`? Do `unverified` claims get zero score weight? | new | 10 calls; yes; yes. |
| **D-09** | **Backtest naming and rules.** SPEC uses `universe_classification = "STATIC_PRESENT_DAY_UNIVERSE"`; code and VALIDATION_PROTOCOL use `universe_bias_status = "STATIC_UNIVERSE_UNADJUSTED"`. Same-bar stop/TP ordering is unspecified. The stress test says "randomly" but also "worst 2%". | `SPEC.md` L110, `engine.py` L25 | Use `universe_bias_status` as the canonical name. Stop fills first. Deterministic worst 2%. |
| **D-10** | **Paper gate operations.** How many shadow sessions `N`? Postgres for tests: `TEST_DATABASE_URL` (no new dependency) or `testcontainers` (new dependency)? | new | `N = 20` sessions; `TEST_DATABASE_URL`. |
| **D-11** | **Coverage floors** in C-TEST-04/05. | §10.1 | As written. |

---

## 12. Change Control
- Any change to a `C-RISK-*`, `C-PIT-*`, `C-LLM-*`, or `C-QUOTA-*` constraint, or to the §11 decisions, needs explicit human approval and a dated entry below.
- Changing a constraint's class from `REQUIRED_BEFORE_PAPER_TRADING` to `ALWAYS_REQUIRED` (stricter) is always allowed. The reverse needs approval.

| Date | Change | Approved by |
| :--- | :--- | :--- |
| 2026-11-05 | v2 draft: classes, gates, measurable checks, baseline, open decisions | *pending* |
