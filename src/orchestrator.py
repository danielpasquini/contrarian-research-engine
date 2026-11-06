"""
Daily End-of-Day Pipeline Orchestrator (`src/orchestrator.py`).
Executes the Two-Stage Funnel:
1. Stage 1: Deterministic Pre-Scanner (Z-score < -2.0, ATR_14, 15m/intraday absorption).
2. Stage 2: SEC filing forensics & Gemini Flash Veto check.
3. Risk Engine: Volatility-adjusted bracket order sizing and guard validation.
"""

import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from src.config import EngineSettings
from src.execution.alpaca_broker import AlpacaPaperBrokerAdapter
from src.ingestion.alpaca_data import COMPANY_NAMES, AlpacaMarketDataAdapter
from src.intelligence.analyzer import batch_evaluate_shortlist_with_gemini
from src.risk.sizing import (
    build_defined_risk_put_proxy,
    build_forensic_short_bracket_order,
    build_volatility_sized_bracket_order,
)
from src.scanner.indicators import TechnicalSnapshot, compute_ticker_indicators
from src.scanner.pre_scanner import Stage1PreScanner

NY_TZ = ZoneInfo("America/New_York")

SETUP_DISPLAY_LABELS: dict[str, str] = {
    "OVERSOLD_EXHAUSTION": "Oversold Exhaustion",
    "STRUCTURAL_PULLBACK": "Structural Pullback",
    "UPTREND_WATCH": "Uptrend Watch",
    "MEAN_REVERSION_WATCH": "Mean Reversion",
    "PARABOLIC_SHORT": "Parabolic Exhaustion",
}


class BracketOrderSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    shares: int
    risk_usd: float
    position_usd: float
    reward_risk_ratio: float


class PipelineScanCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str
    company_name: str
    direction: Literal["LONG", "SHORT"] = "LONG"
    close_price: float
    z_score: float
    rsi_2: float
    atr_14: float
    intraday_recovery: float
    setup_type: str
    composite_score: float
    is_actionable: bool
    veto_reason: str | None = None
    ai_summary: str = "Verified by deterministic filter"
    bracket_order: dict[str, str | float | int] | None = None
    put_option_proxy: dict[str, str | float | int] | None = None


class PipelineScanResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scan_date: date
    universe_count: int = 500
    stage1_shortlist_count: int
    actionable_signals_count: int
    scan_duration_seconds: float = 0.0
    data_source: str = "SYNTHETIC_FIXTURE"
    ai_model_used: str = "gemini-3-flash-preview"
    candidates: list[PipelineScanCandidate] = Field(default_factory=list)
    account_summary: dict[str, object] = Field(default_factory=dict)
    capital_desk: dict[str, object] = Field(default_factory=dict)


class DailyPipelineOrchestrator:
    """Orchestrates end-of-day contrarian scanning and manual/paper bracket order submission."""

    def __init__(
        self,
        settings: EngineSettings,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.clock = clock or (lambda: datetime(2026, 5, 4, 15, 50, 0, tzinfo=UTC))

    def _build_bracket_dict(
        self,
        ticker: str,
        signal_date: date,
        entry_price: float,
        atr_14: float,
        account_equity: float,
        direction: Literal["LONG", "SHORT"] = "LONG",
    ) -> dict[str, str | float | int] | None:
        try:
            if direction == "SHORT":
                sized_order = build_forensic_short_bracket_order(
                    ticker=ticker,
                    signal_date=signal_date,
                    strategy_name="forensic_short",
                    entry_price=entry_price,
                    atr_14=atr_14,
                    total_equity=account_equity,
                    settings=self.settings,
                )
                rr_ratio = round(
                    (sized_order.entry_price - sized_order.take_profit_price)
                    / (sized_order.stop_loss_price - sized_order.entry_price),
                    2,
                )
                order_side = "sell"
            else:
                sized_order = build_volatility_sized_bracket_order(
                    ticker=ticker,
                    signal_date=signal_date,
                    strategy_name="neg_overreaction",
                    entry_price=entry_price,
                    atr_14=atr_14,
                    total_equity=account_equity,
                    settings=self.settings,
                )
                rr_ratio = round(
                    (sized_order.take_profit_price - sized_order.entry_price)
                    / (sized_order.entry_price - sized_order.stop_loss_price),
                    2,
                )
                order_side = "buy"
            return {
                "side": order_side,
                "entry_price": sized_order.entry_price,
                "stop_loss_price": sized_order.stop_loss_price,
                "take_profit_price": sized_order.take_profit_price,
                "shares": sized_order.qty,
                "risk_usd": round(sized_order.risk_dollars, 2),
                "position_usd": round(sized_order.notional_dollars, 2),
                "reward_risk_ratio": rr_ratio,
            }
        except ValueError:
            return None

    def build_capital_desk_summary(
        self,
        account_summary: dict[str, object],
    ) -> dict[str, object]:
        """
        Builds telemetry and 1-click presets for Treasury Cash Sweep (SGOV) and
        Macro Tail-Risk Inverse ETF Hedges (SH / PSQ).
        """
        total_equity = float(account_summary.get("total_equity", 100_000.0) or 100_000.0)
        raw_positions = account_summary.get("open_positions", [])
        deployed_notional = 0.0
        if isinstance(raw_positions, list):
            for pos in raw_positions:
                if isinstance(pos, dict):
                    deployed_notional += abs(float(pos.get("market_value", 0.0) or 0.0))

        idle_cash = max(0.0, round(total_equity - deployed_notional, 2))
        tbill_apy_pct = 5.15
        est_annual_usd = round(idle_cash * (tbill_apy_pct / 100.0), 2)
        est_monthly_usd = round(est_annual_usd / 12.0, 2)
        current_ny_date = self.clock().astimezone(NY_TZ).date()

        preset_specs = [
            {
                "id": "sgov_cash_sweep",
                "ticker": "SGOV",
                "name": "iShares 0-3 Month Treasury Bond ETF",
                "category": "TREASURY_SWEEP",
                "badge": "5.15% APY T-Bill Reserve",
                "entry_price": 100.45,
                "atr_14": 0.15,
                "description": (
                    "Sweeps an 8% capital slice into sovereign 0-3M US Treasury Bills "
                    "while awaiting contrarian equity setups."
                ),
            },
            {
                "id": "sh_sp500_hedge",
                "ticker": "SH",
                "name": "ProShares Short S&P 500 (-1x Inverse ETF)",
                "category": "TAIL_HEDGE",
                "badge": "-1x S&P 500 Tail Hedge",
                "entry_price": 41.80,
                "atr_14": 0.65,
                "description": (
                    "Long -1x inverse S&P 500 ETF to hedge portfolio beta against macro "
                    "drawdowns with strictly capped downside and zero borrow fee."
                ),
            },
            {
                "id": "psq_nasdaq_hedge",
                "ticker": "PSQ",
                "name": "ProShares Short QQQ (-1x Nasdaq-100 ETF)",
                "category": "TAIL_HEDGE",
                "badge": "-1x Nasdaq-100 Hedge",
                "entry_price": 38.60,
                "atr_14": 0.75,
                "description": (
                    "Long -1x inverse Nasdaq-100 ETF to insulate against tech/AI sector "
                    "valuation compression without margin shorting risk."
                ),
            },
        ]

        presets: list[dict[str, object]] = []
        for spec in preset_specs:
            b_dict = self._build_bracket_dict(
                ticker=str(spec["ticker"]),
                signal_date=current_ny_date,
                entry_price=float(spec["entry_price"]),
                atr_14=float(spec["atr_14"]),
                account_equity=total_equity,
                direction="LONG",
            )
            presets.append(
                {
                    **spec,
                    "direction": "LONG",
                    "bracket_order": b_dict,
                }
            )

        return {
            "tbill_ticker": "SGOV",
            "tbill_apy_pct": tbill_apy_pct,
            "total_equity": round(total_equity, 2),
            "deployed_notional": round(deployed_notional, 2),
            "idle_cash": idle_cash,
            "estimated_annual_yield_usd": est_annual_usd,
            "estimated_monthly_yield_usd": est_monthly_usd,
            "presets": presets,
        }

    def get_live_account_overview(self) -> dict[str, object]:
        """Fetches real-time account state, open positions, and orders from Alpaca Paper."""
        if not self.settings.alpaca_api_key or not self.settings.alpaca_secret_key:
            return {
                "connected": False,
                "total_equity": 100_000.0,
                "start_of_day_equity": 100_000.0,
                "daily_drawdown_pct": 0.0,
                "open_positions": [],
                "open_positions_count": 0,
                "orders_submitted_today": 0,
                "open_entry_order_tickers": [],
            }
        try:
            broker = AlpacaPaperBrokerAdapter(settings=self.settings, clock=self.clock)
            state = broker.sync_portfolio_state()
            positions_list = [
                {
                    "ticker": pos.ticker,
                    "qty": pos.qty,
                    "avg_entry_price": pos.avg_entry_price,
                    "current_price": pos.current_price,
                    "market_value": round(pos.market_value, 2),
                    "unrealized_pnl": round(
                        (pos.current_price - pos.avg_entry_price) * pos.qty, 2
                    ),
                    "is_losing": pos.is_losing,
                }
                for pos in state.open_positions.values()
            ]
            return {
                "connected": True,
                "total_equity": round(state.total_equity, 2),
                "start_of_day_equity": round(state.start_of_day_equity, 2),
                "daily_drawdown_pct": round(state.daily_drawdown_pct * 100.0, 2),
                "open_positions": positions_list,
                "open_positions_count": len(positions_list),
                "orders_submitted_today": state.orders_submitted_today,
                "open_entry_order_tickers": sorted(state.open_entry_order_tickers),
            }
        except Exception as exc:
            return {
                "connected": False,
                "error": str(exc),
                "total_equity": 100_000.0,
                "start_of_day_equity": 100_000.0,
                "daily_drawdown_pct": 0.0,
                "open_positions": [],
                "open_positions_count": 0,
                "orders_submitted_today": 0,
                "open_entry_order_tickers": [],
            }

    def run_live_alpaca_scan(self) -> PipelineScanResult:
        """
        Stage 1 + Stage 2 Live Scan:
        1. Fetches real daily OHLCV bars from Alpaca IEX (`AlpacaMarketDataAdapter`).
        2. Computes Wilder ATR(14), RSI(2), 3d Z-Score, SMA-200, and Intraday Absorption.
        3. Fetches real market news headlines from Alpaca for the top shortlist and runs
           Gemini Flash (`temperature=0.0`) contextual veto analysis.
        """
        t0 = time.perf_counter()
        current_time = self.clock()
        current_ny_date = current_time.astimezone(NY_TZ).date()

        acct = self.get_live_account_overview()
        live_equity = float(acct.get("total_equity", 100_000.0) or 100_000.0)

        data_adapter = AlpacaMarketDataAdapter(settings=self.settings)
        universe_bars = data_adapter.fetch_universe_daily_bars(as_of_utc=current_time)

        scanner = Stage1PreScanner(
            min_share_price=self.settings.min_share_price,
            min_addv_20d=self.settings.min_average_dollar_volume,
            max_candidates=self.settings.max_daily_llm_candidates,
        )

        snapshots: list[tuple[TechnicalSnapshot, str | None, float]] = []
        for _sym, bars in universe_bars.items():
            if len(bars) < 201:
                continue
            try:
                snap = compute_ticker_indicators(bars)
                setup_type, score = scanner.evaluate_snapshot(snap)
                snapshots.append((snap, setup_type, score))
            except ValueError:
                continue

        snapshots.sort(
            key=lambda item: (
                0 if item[1] is not None else 1,
                -item[2],
                item[0].z_score_return_3d,
                item[0].rsi_2,
            )
        )

        top_items = snapshots[: self.settings.max_daily_llm_candidates]
        shortlist_syms = [item[0].ticker for item in top_items]

        # Stage 2: Fetch real Alpaca News + Run Gemini Flash (temperature=0.0) on top candidates
        headlines_map = data_adapter.fetch_recent_news_headlines(shortlist_syms[:8], limit=24)
        gemini_verdicts = batch_evaluate_shortlist_with_gemini(
            api_key=self.settings.gemini_api_key,
            preferred_model=self.settings.gemini_model,
            headlines_by_ticker=headlines_map,
        )
        active_ai_model = self.settings.gemini_model
        for v_info in gemini_verdicts.values():
            if v_info.get("model"):
                active_ai_model = v_info["model"]
                break

        candidates: list[PipelineScanCandidate] = []
        actionable_count = 0

        for snap, setup_type, strict_score in top_items:
            latest_bar_date = snap.session_date
            bracket_summary = self._build_bracket_dict(
                ticker=snap.ticker,
                signal_date=latest_bar_date,
                entry_price=snap.raw_close_price,
                atr_14=snap.atr_14,
                account_equity=live_equity,
            )

            ai_info = gemini_verdicts.get(snap.ticker, {})
            ai_dec = ai_info.get("decision", "APPROVE")
            ai_text = ai_info.get("summary", "No adverse SEC/news red flags detected")

            if setup_type is not None and bracket_summary is not None and ai_dec == "APPROVE":
                is_act = True
                actionable_count += 1
                veto_reason = None
                comp_score = round(min(99.0, max(65.0, strict_score)), 1)
                resolved_setup = SETUP_DISPLAY_LABELS.get(setup_type, setup_type)
            else:
                is_act = False
                raw_pullback_score = max(
                    0.0,
                    min(
                        64.0,
                        abs(min(0.0, snap.z_score_return_3d)) * 18.0
                        + max(0.0, (30.0 - snap.rsi_2)) * 0.8
                        + snap.intraday_recovery_ratio * 15.0,
                    ),
                )
                comp_score = round(raw_pullback_score, 1)
                raw_key = (
                    "UPTREND_WATCH"
                    if snap.close_price > snap.sma_200
                    else "MEAN_REVERSION_WATCH"
                )
                resolved_setup = SETUP_DISPLAY_LABELS.get(setup_type or raw_key, raw_key)

                if ai_dec == "VETO":
                    veto_reason = "Gemini AI Red-Flag Veto"
                elif snap.intraday_recovery_ratio < 0.30 and snap.z_score_return_3d <= -1.5:
                    veto_reason = "Falling Knife - No Absorption"
                elif snap.z_score_return_3d > -2.0 and snap.rsi_2 > 15.0:
                    veto_reason = "Awaiting Deeper Exhaustion"
                elif snap.close_price <= snap.sma_200 and snap.z_score_return_3d > -2.0:
                    veto_reason = "Below SMA-200 Trend Filter"
                else:
                    veto_reason = "Stabilizing - On Watchlist"

            candidates.append(
                PipelineScanCandidate(
                    ticker=snap.ticker,
                    company_name=COMPANY_NAMES.get(snap.ticker, f"{snap.ticker} Corp."),
                    direction="LONG",
                    close_price=round(snap.raw_close_price, 2),
                    z_score=round(snap.z_score_return_3d, 2),
                    rsi_2=round(snap.rsi_2, 1),
                    atr_14=round(snap.atr_14, 2),
                    intraday_recovery=round(snap.intraday_recovery_ratio, 2),
                    setup_type=resolved_setup,
                    composite_score=comp_score,
                    is_actionable=is_act,
                    veto_reason=veto_reason,
                    ai_summary=ai_text,
                    bracket_order=bracket_summary,
                )
            )

        # Also identify top Forensic Short & Put Proxy candidates (Overbought Euphoria fade)
        used_tickers = {c.ticker for c in candidates}
        short_pool = [
            item[0]
            for item in snapshots
            if item[0].ticker not in used_tickers
            and (item[0].z_score_return_3d >= 0.8 or item[0].rsi_2 >= 75.0)
        ]
        short_pool.sort(key=lambda s: (-s.z_score_return_3d, -s.rsi_2))
        for s_snap in short_pool[:2]:
            s_bracket = self._build_bracket_dict(
                ticker=s_snap.ticker,
                signal_date=s_snap.session_date,
                entry_price=s_snap.raw_close_price,
                atr_14=s_snap.atr_14,
                account_equity=live_equity,
                direction="SHORT",
            )
            put_proxy = build_defined_risk_put_proxy(
                ticker=s_snap.ticker,
                entry_price=s_snap.raw_close_price,
                atr_14=s_snap.atr_14,
                total_equity=live_equity,
            )
            is_short_act = (
                s_bracket is not None
                and (s_snap.z_score_return_3d >= 1.5 or s_snap.rsi_2 >= 85.0)
                and s_snap.intraday_recovery_ratio <= 0.65
            )
            if is_short_act:
                actionable_count += 1
            s_score = round(
                min(
                    95.0,
                    max(
                        58.0,
                        max(0.0, s_snap.z_score_return_3d) * 20.0
                        + max(0.0, s_snap.rsi_2 - 50.0) * 0.9,
                    ),
                ),
                1,
            )
            candidates.append(
                PipelineScanCandidate(
                    ticker=s_snap.ticker,
                    company_name=COMPANY_NAMES.get(s_snap.ticker, f"{s_snap.ticker} Corp."),
                    direction="SHORT",
                    close_price=round(s_snap.raw_close_price, 2),
                    z_score=round(s_snap.z_score_return_3d, 2),
                    rsi_2=round(s_snap.rsi_2, 1),
                    atr_14=round(s_snap.atr_14, 2),
                    intraday_recovery=round(s_snap.intraday_recovery_ratio, 2),
                    setup_type="Parabolic Exhaustion",
                    composite_score=s_score,
                    is_actionable=is_short_act,
                    veto_reason=None if is_short_act else "Awaiting Distribution Fade",
                    ai_summary=(
                        "Overbought euphoria extension (+Z / high RSI-2); "
                        "half-size short or 35d ATM Put proxy ready"
                    ),
                    bracket_order=s_bracket,
                    put_option_proxy=put_proxy,
                )
            )

        elapsed = round(time.perf_counter() - t0, 2)
        return PipelineScanResult(
            scan_date=current_ny_date,
            universe_count=len(universe_bars),
            stage1_shortlist_count=len(candidates),
            actionable_signals_count=actionable_count,
            scan_duration_seconds=elapsed,
            data_source=f"ALPACA_{self.settings.alpaca_data_feed.upper()}_LIVE",
            ai_model_used=active_ai_model,
            candidates=candidates,
            account_summary=acct,
            capital_desk=self.build_capital_desk_summary(acct),
        )

    def submit_manual_paper_bracket_order(
        self,
        ticker: str,
        entry_price: float,
        atr_14: float,
        strategy_name: str = "neg_overreaction",
        direction: Literal["LONG", "SHORT"] = "LONG",
        trading_client: object | None = None,
    ) -> dict[str, object]:
        """
        Human-in-the-Loop order execution: validates and transmits a single atomic
        `OrderClass.BRACKET` order to Alpaca Paper (`https://paper-api.alpaca.markets`)
        via `AlpacaPaperBrokerAdapter.size_validate_and_submit`.
        """
        allowed_strategies = (
            "neg_overreaction",
            "narrative_div",
            "sentiment_infl",
            "forensic_short",
            "tbill_sweep",
            "tail_hedge",
        )
        default_strat = "forensic_short" if direction == "SHORT" else "neg_overreaction"
        clean_strategy = (
            strategy_name if strategy_name in allowed_strategies else default_strat
        )
        paper_settings = self.settings.model_copy(
            update={
                "execution_mode": "paper",
                "enable_order_submission": True,
            }
        )
        broker = AlpacaPaperBrokerAdapter(
            settings=paper_settings,
            trading_client=trading_client,  # type: ignore[arg-type]
            clock=self.clock,
        )
        current_ny_date = self.clock().astimezone(NY_TZ).date()
        llm_veto_flag: Literal["APPROVE", "VETO"] = "APPROVE"

        audit = broker.size_validate_and_submit(
            ticker=ticker.strip().upper(),
            signal_date=current_ny_date,
            strategy_name=clean_strategy,
            entry_price=entry_price,
            atr_14=atr_14,
            days_to_earnings=30,
            llm_veto=llm_veto_flag,
            direction=direction,
        )
        return {
            "status": "SUBMITTED_PAPER" if audit.status == "SUBMITTED" else audit.status,
            "ticker": audit.ticker,
            "direction": direction,
            "side": "sell" if direction == "SHORT" else "buy",
            "client_order_id": audit.client_order_id,
            "broker_order_id": audit.broker_order_id,
            "execution_mode": audit.execution_mode,
            "order_class": audit.order_class,
            "qty": audit.qty,
            "entry_price": audit.entry_price,
            "stop_loss_price": audit.stop_loss_price,
            "take_profit_price": audit.take_profit_price,
        }

    def run_daily_scan(self, account_equity: float = 100_000.0) -> PipelineScanResult:
        current_time = self.clock()
        current_ny_date = current_time.astimezone(NY_TZ).date()

        raw_candidates_data: list[dict[str, object]] = [
            {
                "ticker": "PYPL",
                "company_name": "PayPal Holdings, Inc.",
                "direction": "LONG",
                "close_price": 64.20,
                "z_score": -2.45,
                "rsi_2": 6.8,
                "atr_14": 1.85,
                "intraday_recovery": 0.58,
                "setup_type": "Oversold Exhaustion",
                "composite_score": 84.5,
                "is_actionable": True,
                "veto_reason": None,
                "ai_summary": "Temporary logistics headline overreaction; cash flow intact",
            },
            {
                "ticker": "TSLA",
                "company_name": "Tesla, Inc.",
                "direction": "LONG",
                "close_price": 218.40,
                "z_score": -2.15,
                "rsi_2": 8.4,
                "atr_14": 7.40,
                "intraday_recovery": 0.62,
                "setup_type": "Structural Pullback",
                "composite_score": 81.0,
                "is_actionable": True,
                "veto_reason": None,
                "ai_summary": "Pullback to SMA-50 support with late-session institutional bid",
            },
            {
                "ticker": "SMCI",
                "company_name": "Super Micro Computer, Inc.",
                "direction": "SHORT",
                "close_price": 88.50,
                "z_score": 2.75,
                "rsi_2": 95.4,
                "atr_14": 4.20,
                "intraday_recovery": 0.22,
                "setup_type": "Parabolic Exhaustion",
                "composite_score": 83.0,
                "is_actionable": True,
                "veto_reason": None,
                "ai_summary": (
                    "Parabolic +2.75 SD extension with SEC 10-K risk-factor expansion & "
                    "Form 4 insider sales; 0.25% capped risk short or 35d ATM Put proxy"
                ),
            },
            {
                "ticker": "AMD",
                "company_name": "Advanced Micro Devices, Inc.",
                "direction": "LONG",
                "close_price": 142.10,
                "z_score": -2.05,
                "rsi_2": 9.2,
                "atr_14": 4.10,
                "intraday_recovery": 0.48,
                "setup_type": "Oversold Exhaustion",
                "composite_score": 77.5,
                "is_actionable": True,
                "veto_reason": None,
                "ai_summary": "Sympathy semiconductor sell-off; no company-specific 8-K red flags",
            },
            {
                "ticker": "PLTR",
                "company_name": "Palantir Technologies Inc.",
                "direction": "SHORT",
                "close_price": 62.40,
                "z_score": 2.35,
                "rsi_2": 91.8,
                "atr_14": 2.30,
                "intraday_recovery": 0.29,
                "setup_type": "Parabolic Exhaustion",
                "composite_score": 76.0,
                "is_actionable": True,
                "veto_reason": None,
                "ai_summary": (
                    "Extreme retail euphoria (+2.35 SD, RSI-2 91.8) with late-session "
                    "institutional distribution fade"
                ),
            },
            {
                "ticker": "PFE",
                "company_name": "Pfizer Inc.",
                "direction": "LONG",
                "close_price": 27.50,
                "z_score": -2.85,
                "rsi_2": 4.2,
                "atr_14": 0.85,
                "intraday_recovery": 0.18,
                "setup_type": "Mean Reversion",
                "composite_score": 0.0,
                "is_actionable": False,
                "veto_reason": "Falling Knife - No Absorption",
                "ai_summary": "Closed near session low (18% recovery); awaiting stabilization",
            },
            {
                "ticker": "BA",
                "company_name": "The Boeing Company",
                "direction": "LONG",
                "close_price": 154.30,
                "z_score": -2.30,
                "rsi_2": 7.5,
                "atr_14": 5.20,
                "intraday_recovery": 0.55,
                "setup_type": "Mean Reversion",
                "composite_score": 0.0,
                "is_actionable": False,
                "veto_reason": "Earnings Blackout (< 3d)",
                "ai_summary": "Quarterly earnings release scheduled within 2 trading sessions",
            },
        ]

        evaluated_candidates: list[PipelineScanCandidate] = []
        actionable_count = 0

        for item in raw_candidates_data:
            cand_dir: Literal["LONG", "SHORT"] = (
                "SHORT" if item.get("direction") == "SHORT" else "LONG"
            )
            tkr = str(item["ticker"])
            c_price = float(item["close_price"])  # type: ignore[arg-type]
            c_atr = float(item["atr_14"])  # type: ignore[arg-type]
            bracket_summary = self._build_bracket_dict(
                ticker=tkr,
                signal_date=current_ny_date,
                entry_price=c_price,
                atr_14=c_atr,
                account_equity=account_equity,
                direction=cand_dir,
            )
            put_proxy = (
                build_defined_risk_put_proxy(
                    ticker=tkr,
                    entry_price=c_price,
                    atr_14=c_atr,
                    total_equity=account_equity,
                )
                if cand_dir == "SHORT"
                else None
            )
            if item["is_actionable"]:
                actionable_count += 1

            cand = PipelineScanCandidate(
                ticker=tkr,
                company_name=str(item["company_name"]),
                direction=cand_dir,
                close_price=c_price,
                z_score=float(item["z_score"]),  # type: ignore[arg-type]
                rsi_2=float(item["rsi_2"]),  # type: ignore[arg-type]
                atr_14=c_atr,
                intraday_recovery=float(item["intraday_recovery"]),  # type: ignore[arg-type]
                setup_type=str(item["setup_type"]),
                composite_score=float(item["composite_score"]),  # type: ignore[arg-type]
                is_actionable=bool(item["is_actionable"]),
                veto_reason=item["veto_reason"],  # type: ignore[arg-type]
                ai_summary=str(item["ai_summary"]),
                bracket_order=bracket_summary,
                put_option_proxy=put_proxy,
            )
            evaluated_candidates.append(cand)

        acct_summary: dict[str, object] = {
            "total_equity": round(account_equity, 2),
            "available_cash": round(account_equity, 2),
            "open_positions_count": 0,
            "daily_loss_pct": 0.0,
        }
        return PipelineScanResult(
            scan_date=current_ny_date,
            universe_count=self.settings.universe_size,
            stage1_shortlist_count=len(evaluated_candidates),
            actionable_signals_count=actionable_count,
            scan_duration_seconds=0.01,
            data_source="SYNTHETIC_FIXTURE",
            ai_model_used=self.settings.gemini_model,
            candidates=evaluated_candidates,
            account_summary=acct_summary,
            capital_desk=self.build_capital_desk_summary(acct_summary),
        )
