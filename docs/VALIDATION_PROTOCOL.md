# Contrarian Research Engine — Adversarial Validation & Backtesting Protocol (`VALIDATION_PROTOCOL.md`)

> **Epistemic Mandate (`AGENTS.md` §4–§5, `.agents/skills/point-in-time-data`, `CONSTRAINTS.md` §3 & §8):**
> Assume every backtest is contaminated by look-ahead bias, survivorship bias, corporate-action distortion, or optimistic fill assumptions until proven otherwise by deterministic automated falsification tests. Strategy scores are **exploratory rankings — not calibrated probabilities of positive return**.

---

## 1. Primary Falsification Hypotheses & Benchmark Hierarchy

The backtesting engine (`src/backtesting/`) exists to attempt to **falsify** the claim that the combined multi-stage Contrarian Research Engine generates superior net risk-adjusted returns after realistic transaction costs, slippage, and tail-delisting stress compared to passive and naive baselines.

### 1.1 Mandatory Benchmarks (`C-BT-08`)
Every Out-of-Sample (OOS) evaluation must compute identical risk-adjusted metrics across seven distinct strategy configurations over the exact same calendar window `[T_start, T_end]`:

| ID | Strategy / Benchmark Configuration | Description & Purpose |
| :--- | :--- | :--- |
| **`B1_SPY_BUY_HOLD`** | **Buy-and-Hold `SPY`** | 100% capital allocated to `SPY` (total-return basis including reinvested cash dividends, net of entry/exit slippage). Tests whether active swing trading beats passive US equity beta. |
| **`B2_UNIVERSE_EW`** | **Equal-Weight Universe Buy-and-Hold** | Equal-weighted buy-and-hold of the active 500-stock universe rebalanced quarterly. Isolates stock-selection alpha from small/mid-cap tilt or static-universe drift. |
| **`B3_NAIVE_MEAN_REV`** | **Pure Price-Only Naive Mean Reversion ("Falling Knife Baseline")** | Buys every liquid stock ($\text{Price} \ge \$10, \text{ADDV}_{20} \ge \$20\text{M}$) with $Z(\text{Ret}_{3d}) \le -2.0$ using the same ATR Bracket sizing, **without** Stage 1B 15m institutional absorption, **without** Stage 2 fundamental/forensic engines, and **without** LLM Red-Flag/Earnings Veto. Tests whether filtering falling knives adds measurable value. |
| **`A1_STAGE1_ONLY`** | **Stage 1 Technical + 15m Absorption Only (No Stage 2)** | Trades all candidates passing Stage 1A (daily shock + stabilization) and Stage 1B (15m PM vs. AM institutional absorption $\text{SMAR} \ge 50$) plus deterministic Earnings Blackout, but **without** Stage 2 LLM/Forensic scoring or Red-Flag Veto. |
| **`A2_SINGLE_ENGINES`** | **Individual Engine Ablations (`E1_Only`, `E2_Only`, `E3_Only`)** | Runs Stage 1 + Stage 2 LLM Veto Gate with only one engine active at a time: (a) `Negative Overreaction` only, (b) `Narrative & Contagion Divergence` only, (c) `Sentiment & Form 4 Insider Conviction` only. |
| **`A3_NO_VETO_GATE`** | **Combined Engines WITHOUT LLM Red-Flag Veto** | Runs Stage 1 + all three Stage 2 engines, but disables `veto_decision == "VETO"` (allowing fraud/distress/guidance-cut red flags through). Directly quantifies the drawdown avoided by the Stage 2 Veto Gate. |
| **`S_COMBINED_FULL`** | **Full Contrarian Research Engine** | Complete pipeline: Stage 1A + Stage 1B (15m absorption) + Stage 2 Three Engines + Orthogonal Ensemble ($\ge 65.0$) + LLM `VETO` Gate + `OrderValidationGuard` Bracket sizing. |

---

## 2. Exact Risk-Adjusted Performance Metrics & Mathematical Definitions

Let $t \in \{1, \dots, N_{\text{days}}\}$ index trading sessions in the evaluation period (with $252$ trading sessions per year). Let $E_t$ denote end-of-day total portfolio equity (marked-to-market including open positions and cash), $R^{\text{port}}_t = \frac{E_t - E_{t-1}}{E_{t-1}}$ denote the net daily portfolio return after all slippage and fees, and $r_{f, t}$ denote the daily risk-free rate (default $r_{f, t} = 0.0$ for conservative excess-return comparison, or annualized 3-month Treasury bill rate $/ 252$). Let $\{r^{\text{net}}_1, r^{\text{net}}_2, \dots, r^{\text{net}}_K\}$ denote the net percentage returns of the $K$ closed trades, and $\{\Delta \$_1, \dots, \Delta \$_K\}$ denote their net dollar PnLs.

1. **Annualized Sharpe Ratio ($\text{Sharpe}_{\text{ann}}$):**
   $$\mu_d = \frac{1}{N_{\text{days}}} \sum_{t=1}^{N_{\text{days}}} \left(R^{\text{port}}_t - r_{f, t}\right), \qquad \sigma_d = \sqrt{\frac{1}{N_{\text{days}} - 1} \sum_{t=1}^{N_{\text{days}}} \left(R^{\text{port}}_t - r_{f, t} - \mu_d\right)^2}$$
   $$\text{Sharpe}_{\text{ann}} = \begin{cases} 0.0 & \text{if } \sigma_d \le 10^{-12} \text{ or } N_{\text{days}} < 20 \\ \sqrt{252} \cdot \frac{\mu_d}{\sigma_d} & \text{otherwise} \end{cases}$$

2. **Annualized Sortino Ratio ($\text{Sortino}_{\text{ann}}$):**
   Penalizes only downside semi-deviation below target return $\tau = r_{f, t}$:
   $$\sigma_{\text{down}, d} = \sqrt{\frac{1}{N_{\text{days}}} \sum_{t=1}^{N_{\text{days}}} \left[\min\!\left(0.0, \; R^{\text{port}}_t - r_{f, t}\right)\right]^2}$$
   $$\text{Sortino}_{\text{ann}} = \begin{cases} 0.0 & \text{if } \sigma_{\text{down}, d} \le 10^{-12} \text{ or } N_{\text{days}} < 20 \\ \sqrt{252} \cdot \frac{\mu_d}{\sigma_{\text{down}, d}} & \text{otherwise} \end{cases}$$

3. **Maximum Peak-to-Trough Equity Drawdown ($\text{MaxDD} \in [0, 1]$):**
   $$H_t = \max_{\tau \in \{0, \dots, t\}} E_{\tau}, \qquad \text{DD}_t = \frac{H_t - E_t}{H_t}, \qquad \text{MaxDD} = \max_{t \in \{1, \dots, N_{\text{days}}\}} \text{DD}_t$$

4. **Net Win Rate ($\text{WinRate} \in [0, 1]$):**
   $$\text{WinRate} = \frac{1}{K} \sum_{k=1}^{K} \mathbb{I}\!\left(r^{\text{net}}_k > 0.0\right)$$

5. **Profit Factor ($\text{PF}$):**
   Ratio of gross winning trade dollars to gross losing trade dollars (net of transaction costs):
   $$\text{PF} = \frac{\sum_{k : \Delta \$_k > 0} \Delta \$_k}{\max\!\left(\sum_{k : \Delta \$_k < 0} \left|\Delta \$_k\right|, \; 10^{-8}\right)}$$
   *(If a strategy has zero losing trades and $\ge 1$ winning trade, cap reported $\text{PF} = 99.99$; if $K = 0$, $\text{PF} = 0.0$).*

6. **Per-Trade Net Expectancy ($\mathbb{E}[r^{\text{net}}]$) & Tail-Stressed Delisting Expectancy ($\mathbb{E}_{\text{stressed}}[r^{\text{net}}]$):**
   $$\mathbb{E}[r^{\text{net}}] = \frac{1}{K} \sum_{k=1}^{K} r^{\text{net}}_k$$
   Let $r^{\text{net}}_{(1)} \le r^{\text{net}}_{(2)} \le \dots \le r^{\text{net}}_{(K)}$ be the order statistics of net trade returns, and let $m = \max(1, \lceil 0.02 \cdot K \rceil)$ be the worst $2\%$ tail count (`C-BT-04`). Override $r^{\text{stressed}}_{(j)} = -1.00$ ($-100\%$ total wipeout bypassing stop-loss) for $j \in \{1, \dots, m\}$ and $r^{\text{stressed}}_{(j)} = r^{\text{net}}_{(j)}$ for $j > m$:
   $$\mathbb{E}_{\text{stressed}}[r^{\text{net}}] = \frac{1}{K} \sum_{j=1}^{K} r^{\text{stressed}}_{(j)}$$

---

## 3. Point-in-Time (`available_at`) & Anti-Look-Ahead Controls (`C-PIT-01`..`C-PIT-14`, `C-BT-06`)

Every historical simulation step at simulated clock $T_{\text{sim}}$ is governed by a strict `PITDataAccessor` (`src/backtesting/`):

1. **Hard Visibility Invariant (`C-PIT-10`, `C-BT-06`):**
   - For any table or dataset $\mathcal{D}$ (daily bars, 15m intraday bars, SEC 8-K/10-Q/10-K filings, XBRL companyfacts, Form 4 XML transactions, news clusters, earnings calendars), the accessor executes:
     $$\mathcal{D}_{\text{visible}}(T_{\text{sim}}) = \left\{ d \in \mathcal{D} \;\middle|\; d.\text{available\_at} \le T_{\text{sim}} \right\}$$
   - **Query-Level Guard:** Attempting to query without an explicit timezone-aware UTC `as_of: datetime` parameter raises `ValueError("PIT_ACCESS_VIOLATION: as_of timestamp is mandatory")`.
2. **Timestamp Gating Rules by Data Source (`C-PIT-02`..`C-PIT-09`):**
   - **Daily Market Bars:** A session $t$'s daily OHLCV bar has `available_at = 16:00:00 ET` on session $t$ (`13:00:00 ET` on NYSE early-close sessions).
   - **15-Minute Intraday Bars:** Each 15m bar $[t_{\text{open}}, t_{\text{close}}]$ has `available_at = t_close`. The full Step 1B `15:00–16:00 ET` accumulation window is available at `16:00:00 ET` (or at `15:45:00 ET` for the first 3 afternoon bars if evaluating a `15:50 ET` decision clock; see §5.1).
   - **SEC Filings & XBRL Facts (`C-PIT-04`..`C-PIT-07`):**
     - `published_at` is the SEC EDGAR **acceptance timestamp** (`<ACCEPTANCE-DATETIME>` in ET from the SGML header; if only JSON `acceptanceDateTime` with ambiguous `Z` suffix is present, compute `available_at` under both UTC and ET interpretations and take the **later** timestamp per `C-PIT-05`).
     - **Never** gate fundamentals by `period_of_report` (`end` date) or use XBRL `frame` tags (which retroactively collapse restatements).
     - Any filing accepted after `16:00:00 ET` on session $t$ receives `available_at = 09:30:00 ET` on session $t+1$.
   - **SEC Form 4 Insider Purchases (`C-PIT-08`):**
     - Strictly gated by EDGAR filing acceptance timestamp `available_at`, **never** by `transactionDate` (since executives have up to 2 business days to file Form 4 after execution).
   - **Historical Earnings Blackout Reconstruction (`C-BT-06`):**
     - In historical backtests, the $\le 3$ trading-session earnings blackout (`C-RISK-05`) is enforced using point-in-time earnings calendar announcements (`available_at <= T_sim`) or 8-K Item 2.02 filing acceptance dates (blocking new entries in sessions $[t_{\text{earn}} - 3, t_{\text{earn}}]$).
3. **Truncation Invariance Test (`C-PIT-11`):**
   - Computing Stage 1 indicators (`z_return_3d`, `z_return_5d`, `rsi_2`, `atr_14`, `sma_50`, `sma_200`, `smar_15m`) and Stage 2 engine scores at $T_{\text{sim}} = t_k$ on dataset truncated at $t_k$ vs. full dataset $[t_0, t_N]$ (including a stock split and dividend at $t_k + 5$) must yield identical floating-point values within $\le 10^{-12}$.

---

## 4. Corporate Actions: Splits & Dividends Control (`C-PIT-12`)

Historical vendor series that come pre-adjusted for all splits up to the present day leak future split ratios into the past. The backtester enforces **As-Of Dual-Basis Accounting**:

1. **As-Of Split/Dividend Factor Construction:**
   For ticker $i$ with historical split events $\{(t_{\text{split}, m}, s_m)\}$ (where a $2\text{-for-}1$ split has $s_m = 2.0$) and cash dividends $\{(t_{\text{div}, d}, D_d)\}$, when evaluated at simulated decision date $t$, only events with **ex-date $\tau_{\text{ex}} \le t$** are visible:
   $$F^{\text{split}}_{i, \tau \mid t} = \prod_{\substack{m : \tau < t_{\text{split}, m} \le t}} s_m, \qquad P^{\text{adj}}_{i, \tau \mid t} = \frac{P^{\text{raw}}_{i, \tau}}{F^{\text{split}}_{i, \tau \mid t}} \cdot F^{\text{div}}_{i, \tau \mid t} \quad (\tau \le t)$$
   - At $\tau = t$, $F^{\text{split}}_{i, t \mid t} = 1.0$, so $P^{\text{adj}}_{i, t \mid t} \equiv P^{\text{raw}}_{i, t}$.
   - Any future split at $t_{\text{split}} > t$ is **completely excluded** at decision time $t$.
2. **Strict Separation of Price Bases:**
   - **Return & Oscillator Indicators ($r_{1d}, r_{3d}, r_{5d}, Z^{\text{rel}}, \text{RSI}_2, \text{SMA}_{50/200}$):** Computed on $P^{\text{adj}}_{i, \tau \mid t}$ ($\tau \le t$) so splits occurring inside the trailing lookback window $[t-252, t]$ do not create artificial $-50\%$ price drops.
   - **Price Floor, Dollar Volume, ATR Stop Distance & Order Sizing:** Evaluated in day-$t$'s actual trading basis $P^{\text{raw}}_{i, t}$ ($\text{Close}^{\text{raw}}_{i, t} \ge \$10.00$, $\text{ADDV}_{20, i, t} \ge \$20\text{M}$, and $\text{ATR}_{14, i, t}$ in day-$t$ dollars).
3. **Open Position Split & Dividend Adjustment During Holding Period:**
   - If a held position in ticker $i$ (entered at session $t_{\text{entry}}$ with quantity $Q$, entry $P_{\text{entry}}$, stop $P_{\text{stop}}$, and target $P_{\text{tp}}$) experiences an overnight stock split of ratio $s$ on ex-date $t_{\text{ex}} \in (t_{\text{entry}}, t_{\text{exit}}]$:
     $$Q' = Q \cdot s, \qquad P'_{\text{entry}} = \frac{P_{\text{entry}}}{s}, \qquad P'_{\text{stop}} = \text{round}\!\left(\frac{P_{\text{stop}}}{s}, 2\right), \qquad P'_{\text{tp}} = \text{round}\!\left(\frac{P_{\text{tp}}}{s}, 2\right)$$
   - If a cash dividend $D$ goes ex-dividend on $t_{\text{ex}} \in (t_{\text{entry}}, t_{\text{exit}}]$, cash balance increases by $Q \cdot D$ on $t_{\text{ex}}$.

---

## 5. Realistic Execution, Slippage & Simulated Bracket Order Protocol (`C-BT-05`)

### 5.1 Supported Execution Timing Modes (Zero Same-Bar Fill Bias)
A signal computed using session $T$'s `16:00:00 ET` close bar **can never fill at session $T$'s close** (`C-BT-05`). The backtester supports two explicit, realistic execution modes configured prior to the run:

1. **Mode 1 (Default): Next-Session Open Execution (`T+1_OPEN`):**
   - Decision clock $T_{\text{dec}} = \text{Session } T \text{ at } 16:05:00\text{ ET}$ (using full session $T$ daily bar, all 26 fifteen-minute bars `09:30–16:00 ET`, and filings accepted up to `16:00:00 ET`).
   - Order is submitted for execution at **Session $T+1$ Regular Open (`09:30:00 ET`)**.
   - **Gap-Guard Entry Limit Rule:** If Session $T+1$'s raw open price gaps above the planned entry by more than $0.50 \cdot \text{ATR}_{14, i, T}$ ($O^{\text{raw}}_{i, T+1} > C^{\text{raw}}_{i, T} + 0.50\,\text{ATR}_{14, i, T}$) or gaps below the planned stop-loss ($O^{\text{raw}}_{i, T+1} \le P_{\text{stop}, i, T}$), the entry order is **canceled (unfilled)** rather than chasing a runaway open or buying into an immediate stop-out.
   - Otherwise, the entry fills at:
     $$P^{\text{fill}}_{\text{entry}, i, T+1} = O^{\text{raw}}_{i, T+1} \cdot \left(1 + c_{\text{slip}}\right)$$
     and Bracket legs $(P_{\text{stop}}, P_{\text{tp}})$ are anchored to the actual fill price $O^{\text{raw}}_{i, T+1}$ (verified through `OrderValidationGuard` before fill).

2. **Mode 2 (Optional): Late-Session `15:50 ET` Decision & `16:00 ET` MOC/LOC Execution (`T_1550_CLOSE`):**
   - Decision clock $T_{\text{dec}} = \text{Session } T \text{ at } 15:50:00\text{ ET}$.
   - Uses provisional daily bar up to `15:45:00 ET` (bars $b \in \{1, \dots, 25\}$, where the PM accumulation window uses the three completed 15m bars `15:00–15:45 ET`: $b \in \{23, 24, 25\}$) and only filings/news with `available_at <= 15:50:00 ET`.
   - Executes at Session $T$'s `16:00:00 ET` closing auction price $C^{\text{raw}}_{i, T} \cdot (1 + c_{\text{slip}})$.
   - **Strict Isolation Rule:** Mode 2 is **forbidden** from reading bar $b=26$ (`15:45–16:00 ET`) or session $T$'s `16:00 ET` close during signal generation.

### 5.2 Slippage, Spread & Regulatory Fee Model (`C-BT-05`)
Every simulated entry and exit deducts explicit friction:
- **Base One-Way Slippage + Half-Spread ($c_{\text{slip}}$):** Default **$10\text{ bps}$ ($0.0010$)** per side ($20\text{ bps}$ round-trip) for liquid tickers with $\text{ADDV}_{20} \ge \$50\text{M}$, and **$15\text{ bps}$ ($0.0015$)** per side ($30\text{ bps}$ round-trip) for tickers with $\$20\text{M} \le \text{ADDV}_{20} < \$50\text{M}$.
- **Regulatory Fees (Sell Side Only):** SEC Section 31 fee + FINRA TAF modeled conservatively at **$0.5\text{ bps}$ ($0.00005$)** of exit notional.
- **Effective Fill Prices:**
  $$P^{\text{exec}}_{\text{buy}} = P^{\text{raw}}_{\text{trigger, buy}} \cdot \left(1 + c_{\text{slip}}\right), \qquad P^{\text{exec}}_{\text{sell}} = P^{\text{raw}}_{\text{trigger, sell}} \cdot \left(1 - c_{\text{slip}} - 0.00005\right)$$

### 5.3 Pessimistic Simulated Bracket Order (OCO) Resolution (`C-BT-05`)
For every active position held during session $\tau \ge t_{\text{entry}}$ with stop-loss $P_{\text{stop}}$ and take-profit $P_{\text{tp}}$, daily/15m bar evaluation follows strict **Worst-Case Precedence Rules**:

1. **Rule 1 — Overnight Gap Through Stop-Loss (`Gap-Below-Stop`):**
   If $O^{\text{raw}}_{i, \tau} \le P_{\text{stop}}$:
   - Stop-loss orders become market orders once triggered; they **do not** guarantee execution at $P_{\text{stop}}$ across an overnight gap.
   - The position exits immediately at the open with slippage:
     $$P^{\text{exec}}_{\text{exit}} = O^{\text{raw}}_{i, \tau} \cdot \left(1 - c_{\text{slip}} - 0.00005\right)$$
     (`exit_reason = "STOP_LOSS_GAP"`).

2. **Rule 2 — Overnight Gap Above Take-Profit (`Gap-Above-TP`):**
   If $O^{\text{raw}}_{i, \tau} \ge P_{\text{tp}}$:
   - A resting limit sell order at $P_{\text{tp}}$ triggered by an opening gap above $P_{\text{tp}}$ fills conservatively at $P_{\text{tp}}$ (or $O^{\text{raw}}_{i,\tau}$ minus slippage; per `C-BT-05` conservative rule, we cap at $P_{\text{tp}} \cdot (1 - c_{\text{slip}} - 0.00005)$ so overnight upside windfalls are never overstated) (`exit_reason = "TAKE_PROFIT"`).

3. **Rule 3 — Same-Bar Dual Touch (`Stop-First Precedence`, `C-BT-05`):**
   If both the stop-loss and take-profit lie inside session $\tau$'s range ($L^{\text{raw}}_{i, \tau} \le P_{\text{stop}}$ **AND** $H^{\text{raw}}_{i, \tau} \ge P_{\text{tp}}$):
   - Unless 15-minute bars for session $\tau$ unambiguously prove that $H_b \ge P_{\text{tp}}$ occurred in an earlier 15m bar $b_1 < b_2$ before $L_{b_2} \le P_{\text{stop}}$ (with zero overlap in the same 15m bar), the simulator **must assume the stop-loss was hit first**:
     $$P^{\text{exec}}_{\text{exit}} = P_{\text{stop}} \cdot \left(1 - c_{\text{slip}} - 0.00005\right), \qquad \text{exit\_reason} = \text{"STOP\_LOSS\_SAME\_BAR\_CONSERVATIVE"}$$

4. **Rule 4 — Standard Intraday Stop-Loss or Take-Profit Touch:**
   - If $L^{\text{raw}}_{i, \tau} \le P_{\text{stop}}$ (and $H^{\text{raw}}_{i, \tau} < P_{\text{tp}}$): exit at $P_{\text{stop}} \cdot (1 - c_{\text{slip}} - 0.00005)$ (`exit_reason = "STOP_LOSS"`).
   - If $H^{\text{raw}}_{i, \tau} \ge P_{\text{tp}}$ (and $L^{\text{raw}}_{i, \tau} > P_{\text{stop}}$): exit at $P_{\text{tp}} \cdot (1 - c_{\text{slip}} - 0.00005)$ (`exit_reason = "TAKE_PROFIT"`).

5. **Rule 5 — Time-Stop Expiration (`15 Trading Sessions`):**
   - If neither $P_{\text{stop}}$ nor $P_{\text{tp}}$ is hit after $\Delta \tau = 15$ full trading sessions (configurable up to max $20$ sessions per `AGENTS.md` §1), exit at Session $t_{\text{entry}} + 15$'s close $C^{\text{raw}}_{i, t_{\text{entry}}+15} \cdot (1 - c_{\text{slip}} - 0.00005)$ (`exit_reason = "TIME_STOP"`).

6. **Portfolio-Level Constraints During Simulation:**
   - Every simulated entry must pass `OrderValidationGuard` (`src/risk/guard.py`): max 10 concurrent positions (`MAX_OPEN_POSITIONS`), max $0.5\%$ equity risk per trade (`MAX_RISK_PER_TRADE_PCT`), max $10\%$ notional per position (`MAX_POSITION_PCT`), max 3 new orders per day (`MAX_ORDERS_PER_DAY`), No Averaging Down on losing positions, and the $2.0\%$ daily drawdown Kill Switch.

---

## 6. Walk-Forward Chronological Validation & Overfitting Controls (`C-BT-07`, `C-BT-08`)

1. **Strict Chronological Partition (60% IS / 20-Session Embargo / 40% OOS):**
   Given total historical trading sessions $N_{\text{total}}$ (with $N_{\text{total}} \le 756$ sessions / 3 years for static universes per `C-BT-03`):
   - **In-Sample (IS) Calibration Window:** Sessions $[1, \; N_{\text{IS}}]$ where $N_{\text{IS}} = \lfloor 0.60 \cdot (N_{\text{total}} - 20) \rfloor$.
   - **Purged Embargo Buffer (`20 Trading Sessions`):** Sessions $[N_{\text{IS}} + 1, \; N_{\text{IS}} + 20]$. Any open position remaining at $N_{\text{IS}}$ is force-closed before the embargo ends so zero holding-period returns bleed across the IS/OOS boundary.
   - **Out-of-Sample (OOS) Validation Window:** Sessions $[N_{\text{IS}} + 21, \; N_{\text{total}}]$.
2. **Frozen Configuration Hash Lock (`C-BT-08`):**
   - Before running the OOS window, the backtester computes `frozen_config_sha256` over all strategy thresholds (`RSI_2` cutoffs, z-score thresholds, `SMAR` threshold, engine weights, ATR stop/TP multipliers).
   - `run_walk_forward_backtest()` verifies `current_config_sha256 == frozen_config_sha256` before executing OOS; any mismatch raises `RuntimeError("OOS_CONFIG_TAMPERED: Cannot run OOS with modified parameters")`.
   - Every parameter trial run during IS development increments a persistent counter `n_parameter_trials_tested` stored in the report provenance (`C-BT-07`) to expose multiple-testing / p-hacking risk.

---

## 7. Honest Survivorship Bias Handling (`C-BT-01`..`C-BT-04`)

### 7.1 What Free Alpaca & SEC EDGAR Datasets Can and Cannot Prove
- **What Free Data CANNOT Prove:**
  - Free market data APIs (Alpaca Basic/SIP current ticker queries) and current SEC `company_tickers.json` lists reflect **today's surviving companies**. Companies that went bankrupt, were delisted for financial distress (e.g., Chapter 11 wipeouts), or were acquired at distressed valuations between $T_{\text{start}}$ and today are missing from a present-day top-500 liquidity screen.
  - For a **contrarian** strategy that explicitly buys sharp multi-day sell-offs ($Z \le -2.0$), ignoring delisted equities introduces severe optimistic survivorship bias because historic terminal falling knives have vanished from the candidate pool.
- **What Free Data CAN Prove (and How We Bound the Bias):**
  1. **Short-Horizon Universe Restriction (`C-BT-03`):** Restricting static-universe runs to $\le 3$ calendar years ($\le 756$ sessions) on large-cap liquid equities ($\text{Price} \ge \$10, \text{ADDV}_{20} \ge \$20\text{M}$) limits constituent delisting turnover compared to 10-year small-cap backtests, though it does not eliminate it.
  2. **Deterministic $2\%$ Tail-Wipeout Stress Test (`C-BT-04`):** By deterministically overriding the worst $2\%$ of all Stage 1 setups (`ceil(0.02 * N_trades)`) to a `-100%` total loss (bypassing the $2.0\,\text{ATR}_{14}$ stop-loss completely, simulating overnight fraud/bankruptcy trading halts), we test whether the strategy's positive expectancy survives catastrophic tail events.
  3. **Known Historical Bankruptcy / Distress Replay Fixtures:** Including explicit historical SEC 8-K/10-Q fixtures of known delisted/distressed companies in `tests/fixtures/` verifies that the Stage 2 LLM Red-Flag Veto (`C-LLM-05`) and Engine 1/2 solvency guards ($F_{\text{health}} < 30$) reject terminal collapses pre-entry.

### 7.2 Mandatory `UniverseManifest` & Warning Banner Enforcement (`C-BT-01`, `C-BT-02`)
1. **Default Biased Classification:**
   - `BacktestReport.universe_bias_status` defaults to `"STATIC_UNIVERSE_UNADJUSTED"`.
   - Setting `universe_bias_status = "SURVIVORSHIP_BIAS_FREE"` is **strictly forbidden** by a Pydantic `@model_validator` unless a non-null `UniverseManifest` object is attached containing:
     - `vendor_name: str` (e.g., `"CRSP"`, `"Norgate_Platinum"`, `"Polygon_Delisted_PIT"`)
     - `includes_delisted_tickers: Literal[True]`
     - `delisted_ticker_count: int = Field(ge=1)`
     - `pit_constituent_snapshot_count: int = Field(ge=1)`
     - `dataset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")`
2. **Ubiquitous Warning Banner (`C-BT-02`):**
   Whenever `universe_bias_status == "STATIC_UNIVERSE_UNADJUSTED"`, the exact string:
   ```text
   WARNING: Static Universe - Survivorship Bias Unadjusted. Historical delistings are absent from free provider data.
   ```
   **must** be populated in `BacktestReport.survivorship_bias_warning` and rendered prominently at the top of:
   - JSON/Parquet serialized reports,
   - CLI summary tables,
   - FastAPI backtest endpoints, and
   - Streamlit dashboard views (`st.warning(...)`).
3. **3-Year Static Window Hard Cap (`C-BT-03`):**
   If `universe_bias_status == "STATIC_UNIVERSE_UNADJUSTED"` and `(end_date - start_date).days > 1096` (3 years), the backtester must raise `ValueError("STATIC_UNIVERSE_WINDOW_EXCEEDED: Static unadjusted universe backtests cannot exceed 3 years (1096 days).")`.

---

## 8. Quantitative Acceptance Criteria for Strategy Promotion (`RESEARCH` $\to$ `PAPER` Gate)

To consider the Contrarian Research Engine quantitatively validated in Out-of-Sample walk-forward testing (a prerequisite for human review under `C-BT-09` before enabling `PAPER` execution), the **Out-of-Sample (`40%` window)** report for `S_COMBINED_FULL` must satisfy all six criteria:

| Criterion ID | Metric / Comparison | Mandatory OOS Acceptance Threshold |
| :--- | :--- | :--- |
| **`AC-VAL-01`** | **Zero Look-Ahead & PIT Integrity (`C-PIT-01`..`14`)** | `100%` pass rate on truncation invariance ($\le 10^{-12}$), `available_at` gating, and as-of split adjustment tests. |
| **`AC-VAL-02`** | **Superiority vs. Buy-and-Hold `SPY` (`B1_SPY_BUY_HOLD`)** | $\text{Sharpe}_{\text{ann}}(\text{Combined}) > \text{Sharpe}_{\text{ann}}(\text{SPY})$ **OR** $\left(\text{Sortino}_{\text{ann}}(\text{Combined}) > \text{Sortino}_{\text{ann}}(\text{SPY}) \;\land\; \text{MaxDD}(\text{Combined}) < \text{MaxDD}(\text{SPY})\right)$. |
| **`AC-VAL-03`** | **Superiority vs. Pure Price-Only Mean Reversion (`B3_NAIVE_MEAN_REV`)** | $\text{Sharpe}_{\text{ann}}(\text{Combined}) \ge \text{Sharpe}_{\text{ann}}(\text{Naive}) + 0.25$ **AND** $\text{MaxDD}(\text{Combined}) \le 0.80 \cdot \text{MaxDD}}(\text{Naive})$ **AND** $\text{PF}(\text{Combined}) > \text{PF}(\text{Naive})$. |
| **`AC-VAL-04`** | **Positive Value-Add of Stage 1B (15m Absorption) & Stage 2 Veto (`A1`, `A3`)** | `S_COMBINED_FULL` achieves lower $\text{MaxDD}$ and higher $\text{Profit Factor}$ than `A3_NO_VETO_GATE` (proving the LLM Red-Flag Veto blocks real tail losses) and higher $\mathbb{E}[r^{\text{net}}]$ than `A1_STAGE1_ONLY`. |
| **`AC-VAL-05`** | **Absolute Net Profitability & Risk Bounds** | Net $\text{Profit Factor} \ge 1.30$, Net Expectancy $\mathbb{E}[r^{\text{net}}] > +0.35\%$ per trade after $20\text{–}30\text{ bps}$ round-trip slippage, and OOS $\text{MaxDD} \le 12.0\%$. |
| **`AC-VAL-06`** | **Survivorship Delisting Stress Survival (`C-BT-04`)** | Under the $2\%$ `-100%` tail-delisting stress test, stressed net expectancy remains non-negative ($\mathbb{E}_{\text{stressed}}[r^{\text{net}}] \ge 0.0\%$) or stressed Profit Factor $\ge 1.05$. |

---

## 9. Automated Verification Test Cases (`tests/unit/test_backtest_and_api.py` & `tests/constraints/test_backtest_honesty.py`)

| Test ID | Test Function | Scenario & Inputs | Expected Deterministic Output |
| :--- | :--- | :--- | :--- |
| `T-BT-01` | `test_bias_free_requires_manifest` | Attempt to instantiate `BacktestReport(universe_bias_status="SURVIVORSHIP_BIAS_FREE", universe_manifest=None, ...)`. | Raises `ValidationError` (`C-BT-01`). |
| `T-BT-02` | `test_static_universe_warning_banner_mandatory` | Instantiate or run backtest with `STATIC_UNIVERSE_UNADJUSTED`. Attempt to alter or omit the warning string. | Raises `ValidationError` if warning string does not match the exact `C-BT-02` text. |
| `T-BT-03` | `test_static_universe_window_limit_exceeded` | Run static-universe backtest with `start_date = 2021-01-01`, `end_date = 2025-06-01` ($> 1096$ days). | Raises `ValueError("STATIC_UNIVERSE_WINDOW_EXCEEDED...")` (`C-BT-03`). |
| `T-BT-04` | `test_delisting_stress_test_overrides_worst_2_pct` | Feed 50 trades into `run_pit_backtest_evaluation`. | Worst $\lceil 0.02 \times 50 \rceil = 1$ trade is overridden to `-1.0` (`-100%`); `stressed_delisting_mean_return_pct` and `stressed_max_drawdown` are deterministically computed (`C-BT-04`). |
| `T-BT-05` | `test_no_same_bar_fill_and_round_trip_slippage` | Signal generated at Day $T$ close (`16:00 ET`). | Entry occurs no earlier than Day $T+1$ open with $+10\text{ bps}$ slippage (`P_open * 1.001`); exit deducts $-10.5\text{ bps}$ (`C-BT-05`). |
| `T-BT-06` | `test_bracket_same_bar_dual_touch_executes_stop_first` | Held position has $P_{\text{entry}} = \$100, P_{\text{stop}} = \$95, P_{\text{tp}} = \$110$. Day $\tau$ daily bar has $O = \$100, H = \$112, L = \$94, C = \$105$. | Simulator resolves to `STOP_LOSS_SAME_BAR_CONSERVATIVE` at $\$95 \times (1 - c_{\text{slip}} - 0.00005)$, never taking the $\$110$ profit (`C-BT-05`). |
| `T-BT-07` | `test_bracket_overnight_gap_below_stop_fills_at_open` | Held position has $P_{\text{stop}} = \$95$, but Day $\tau$ opens at $O = \$88$ ($< \$95$). | Position fills at $\$88 \times (1 - c_{\text{slip}} - 0.00005)$, not at $\$95$ (`C-BT-05`). |
| `T-BT-08` | `test_pit_accessor_blocks_future_available_at` | Query `PITDataAccessor` at $T_{\text{sim}} = \text{2026-03-10 16:00 ET}$ when an 8-K and Form 4 have `published_at = 16:05 ET` (`available_at = 2026-03-11 09:30 ET`). | Both records are excluded at `16:00 ET` and returned at `2026-03-11 09:30 ET` (`C-BT-06`). |
| `T-BT-09` | `test_walk_forward_embargo_and_frozen_config_lock` | 100-session dataset split into 60% IS, 20-session embargo, 40% OOS. Modify a parameter hash before OOS call. | Raises `RuntimeError("OOS_CONFIG_TAMPERED...")` (`C-BT-08`). |
| `T-BT-10` | `test_ablation_and_benchmark_comparison_metrics` | Run walk-forward comparator against `B1_SPY_BUY_HOLD` and `B3_NAIVE_MEAN_REV`. | Outputs complete `Sharpe`, `Sortino`, `MaxDD`, `WinRate`, `ProfitFactor`, and `ProvenanceBlock` for all benchmarks and ablations (`C-BT-07`, `C-BT-08`). |
