from datetime import UTC, date, datetime
from types import SimpleNamespace

from src.config import PAPER_ALPACA_URL, EngineSettings
from src.orchestrator import DailyPipelineOrchestrator


class _DummyTradingClient:
    _base_url = PAPER_ALPACA_URL

    def get_account(self) -> object:
        return SimpleNamespace(equity="100000.00", last_equity="100000.00")

    def get_all_positions(self) -> list[object]:
        return []

    def get_orders(self, filter: object = None) -> list[object]:
        return []

    def get_order_by_client_id(self, client_order_id: str) -> object:
        raise ValueError("not found")

    def submit_order(self, order_data: object) -> object:
        return SimpleNamespace(id="broker-order-999", status="accepted")


def test_orchestrator_initialization_and_mock_scan() -> None:
    settings = EngineSettings()
    orchestrator = DailyPipelineOrchestrator(
        settings=settings,
        clock=lambda: datetime(2026, 5, 4, 15, 50, 0, tzinfo=UTC),
    )
    result = orchestrator.run_daily_scan(account_equity=100_000.0)

    assert result.scan_date == date(2026, 5, 4)
    assert result.universe_count == 500
    assert result.stage1_shortlist_count <= settings.max_daily_llm_candidates
    assert len(result.candidates) > 0

    veto_labels = {c.veto_reason for c in result.candidates if c.veto_reason}
    assert "Falling Knife - No Absorption" in veto_labels

    for cand in result.candidates:
        assert cand.ticker
        assert cand.close_price >= settings.min_share_price
        assert cand.atr_14 > 0.0
        assert cand.composite_score >= 0.0
        if cand.is_actionable and cand.bracket_order:
            bo = cand.bracket_order
            assert bo["risk_usd"] <= 100_000.0 * settings.max_risk_per_trade_pct + 0.05
            assert bo["position_usd"] <= 100_000.0 * settings.max_position_pct + 0.05
            assert bo["reward_risk_ratio"] >= settings.min_reward_risk_ratio


def test_orchestrator_submit_manual_paper_bracket_order() -> None:
    settings = EngineSettings()
    orchestrator = DailyPipelineOrchestrator(
        settings=settings,
        clock=lambda: datetime(2026, 5, 4, 15, 50, 0, tzinfo=UTC),
    )
    order_res = orchestrator.submit_manual_paper_bracket_order(
        ticker="XOM",
        entry_price=168.81,
        atr_14=4.51,
        trading_client=_DummyTradingClient(),
    )
    assert order_res["status"] == "SUBMITTED_PAPER"
    assert order_res["ticker"] == "XOM"
    assert order_res["broker_order_id"] == "broker-order-999"
    assert order_res["order_class"] == "BRACKET"
    assert int(order_res["qty"]) > 0  # type: ignore[arg-type]


def test_orchestrator_forensic_short_put_proxy_and_capital_desk() -> None:
    settings = EngineSettings()
    orchestrator = DailyPipelineOrchestrator(
        settings=settings,
        clock=lambda: datetime(2026, 5, 4, 15, 50, 0, tzinfo=UTC),
    )
    result = orchestrator.run_daily_scan(account_equity=100_000.0)

    directions = {c.direction for c in result.candidates}
    assert "LONG" in directions
    assert "SHORT" in directions

    short_cands = [c for c in result.candidates if c.direction == "SHORT"]
    assert len(short_cands) >= 1
    sc = short_cands[0]
    assert sc.bracket_order is not None
    assert float(sc.bracket_order["stop_loss_price"]) > float(sc.bracket_order["entry_price"])
    assert float(sc.bracket_order["take_profit_price"]) < float(sc.bracket_order["entry_price"])
    assert float(sc.bracket_order["risk_usd"]) <= 100_000.0 * 0.0025 + 0.05
    assert float(sc.bracket_order["position_usd"]) <= 100_000.0 * 0.04 + 0.05
    assert sc.put_option_proxy is not None
    assert int(sc.put_option_proxy["contracts"]) >= 1

    desk = result.capital_desk
    assert desk["tbill_ticker"] == "SGOV"
    assert float(desk["tbill_apy_pct"]) > 4.0  # type: ignore[arg-type]
    assert float(desk["estimated_annual_yield_usd"]) > 0.0  # type: ignore[arg-type]
    presets = desk["presets"]
    assert isinstance(presets, list)
    preset_tickers = {p["ticker"] for p in presets}
    assert {"SGOV", "SH", "PSQ"}.issubset(preset_tickers)

    short_order_res = orchestrator.submit_manual_paper_bracket_order(
        ticker="PLTR",
        entry_price=118.50,
        atr_14=4.20,
        direction="SHORT",
        trading_client=_DummyTradingClient(),
    )
    assert short_order_res["status"] == "SUBMITTED_PAPER"
    assert short_order_res["side"] == "sell"
    assert float(short_order_res["stop_loss_price"]) > float(short_order_res["entry_price"])  # type: ignore[arg-type]
    assert float(short_order_res["take_profit_price"]) < float(short_order_res["entry_price"])  # type: ignore[arg-type]

