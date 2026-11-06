from datetime import date

import pytest

from src.api.app import app, get_health
from src.backtesting.engine import SimulatedTrade, run_pit_backtest_evaluation
from src.ingestion.sec_edgar import SecEdgarClient


def test_sec_edgar_requires_valid_user_agent() -> None:
    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        SecEdgarClient(user_agent="")

    client = SecEdgarClient(user_agent="ContrarianResearchEngine quant@example.com")
    headers = client.build_headers()
    assert "ContrarianResearchEngine quant@example.com" in headers["User-Agent"]
    assert client.max_requests_per_second <= 10.0


def test_backtest_enforces_survivorship_bias_warning_and_delisting_stress_test() -> None:
    trades = [
        SimulatedTrade(
            ticker=f"SYM{i}",
            entry_date=date(2025, 3, 10),
            exit_date=date(2025, 3, 20),
            gross_return_pct=0.04 if i % 3 != 0 else -0.02,
        )
        for i in range(50)
    ]

    report = run_pit_backtest_evaluation(
        trades=trades,
        includes_delisted_equities=False,
        one_way_slippage_bps=10.0,
        delisting_tail_fraction=0.02,
    )

    assert report.universe_bias_status == "STATIC_UNIVERSE_UNADJUSTED"
    assert "Static Universe - Survivorship Bias Unadjusted" in report.survivorship_bias_warning
    # Net return deducts 20 bps (2 * 10 bps) round-trip slippage per trade
    assert report.net_mean_return_pct < report.gross_mean_return_pct
    # Stressed expectancy overrides worst 2% (1 trade out of 50) to -100% total loss
    assert report.stressed_delisting_mean_return_pct < report.net_mean_return_pct


def test_fastapi_health_and_safety_status_endpoints() -> None:
    routes = {getattr(r, "path", None) for r in app.routes}
    assert "/health" in routes

    data = get_health()
    assert data["status"] == "ok"
    assert data["execution_mode"] == "research"
    assert data["allow_averaging_down"] is False
    assert data["require_bracket_order"] is True
    assert int(data["max_daily_llm_candidates"]) <= 15  # type: ignore[arg-type]


def test_dark_mode_react_bits_command_center_ui_and_glassmorphism() -> None:
    from dashboard.app import (
        build_glass_metric_card_html,
        build_react_bits_background_html,
        get_command_center_state,
        get_dashboard_banner,
    )
    from src.api.app import get_command_center

    banner = get_dashboard_banner()
    assert "Static Universe - Survivorship Bias Unadjusted" in banner["bias_notice"]
    assert banner["mode"] in ("RESEARCH", "PAPER")

    state = get_command_center_state()
    assert state["survivorship_bias_warning"] == banner["bias_notice"]
    guardrails = state["immutable_guardrails"]
    assert isinstance(guardrails, dict)
    assert guardrails["no_averaging_down"] is True
    assert guardrails["mandatory_bracket_oco"] is True
    assert guardrails["max_position_pct"] == 0.08
    assert guardrails["daily_kill_switch_pct"] == 0.015
    assert guardrails["earnings_blackout_sessions"] == 3

    bg_html = build_react_bits_background_html()
    assert "react-bits-aurora-canvas" in bg_html
    assert "backdrop-filter: blur" in bg_html

    card_html = build_glass_metric_card_html(
        title="STAGE 1 SHORTLIST",
        value="12 / 15",
        subtitle="ATR(14) Raw Dollar & 15m PM Absorption",
        badge_tone="emerald",
    )
    assert "glass-metric-card" in card_html
    assert "STAGE 1 SHORTLIST" in card_html
    assert "12 / 15" in card_html

    api_payload = get_command_center()
    assert api_payload["status"] == "ok"
    assert api_payload["banner"] == banner


def test_standalone_exe_packaging_and_pyinstaller_configuration() -> None:
    from pathlib import Path

    import app as root_launcher
    from scripts.build_exe import PYINSTALLER_CLI_LINE, get_pyinstaller_command

    repo_root = Path(__file__).resolve().parent.parent.parent
    icon_path = repo_root / "favicon.ico"
    ps1_path = repo_root / "scripts" / "build_exe.ps1"

    assert icon_path.exists()
    assert icon_path.stat().st_size > 0
    assert ps1_path.exists()

    expected_cli = (
        'pyinstaller --noconsole --onefile --name="Contrarian Engine" '
        '--icon="favicon.ico" app.py'
    )
    assert expected_cli in PYINSTALLER_CLI_LINE
    assert '--name="Contrarian Engine"' in ps1_path.read_text(encoding="utf-8")

    cmd = get_pyinstaller_command()
    assert cmd[0] == "pyinstaller"
    assert "--noconsole" in cmd
    assert "--onefile" in cmd
    assert "--name=Contrarian Engine" in cmd
    assert "--icon=favicon.ico" in cmd
    assert cmd[-1] == "app.py"

    meta = root_launcher.build_runtime_metadata()
    assert meta["app_name"] == "Contrarian Engine"
    assert meta["execution_mode"] == "research"
    assert meta["paper_endpoint_verified"] is True
    resolved_dashboard = root_launcher.resolve_bundle_path("dashboard/app.py")
    assert resolved_dashboard.exists()

    # Verify Windows GUI --noconsole fallback when sys.stdout/stderr are None
    import sys
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    try:
        sys.stdout = None
        sys.stderr = None
        root_launcher._ensure_stdio_streams()
        assert sys.stdout is not None
        assert sys.stderr is not None
        assert sys.stdout.isatty() is False
        assert sys.stderr.isatty() is False
    finally:
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr

