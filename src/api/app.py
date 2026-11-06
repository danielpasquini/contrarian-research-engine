import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from dashboard.app import (
    build_command_center_html,
    get_command_center_state,
    get_dashboard_banner,
)
from src.config import EngineSettings
from src.orchestrator import DailyPipelineOrchestrator, PipelineScanResult

app = FastAPI(
    title="Contrarian Engine",
    version="0.1.0",
    description="Two-stage quantitative contrarian research and paper-trading engine.",
)


def _locate_asset(filename: str) -> Path | None:
    """Locates static icon/asset files in PyInstaller _MEIPASS or source repository."""
    roots = [
        Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent)),
        Path(__file__).resolve().parent.parent.parent,
        Path.cwd(),
    ]
    for root in roots:
        for rel in (filename, f"dashboard/{filename}"):
            candidate = root / rel
            if candidate.exists():
                return candidate
    return None


@app.get("/favicon.ico", include_in_schema=False)
def get_favicon_ico() -> Response:
    asset = _locate_asset("favicon.ico")
    if asset is not None:
        return FileResponse(asset, media_type="image/x-icon")
    return Response(status_code=204)


@app.get("/favicon.png", include_in_schema=False)
def get_favicon_png() -> Response:
    asset = _locate_asset("favicon.png")
    if asset is not None:
        return FileResponse(asset, media_type="image/png")
    return Response(status_code=204)

_cached_latest_scan: PipelineScanResult | None = None


class ManualOrderSubmitRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ticker: str = Field(min_length=1, max_length=12)
    entry_price: float = Field(gt=0.0)
    atr_14: float = Field(gt=0.0)
    strategy_name: str = Field(default="manual_contrarian", min_length=1, max_length=32)
    direction: Literal["LONG", "SHORT"] = "LONG"


@app.get("/health")
def get_health() -> dict[str, object]:
    settings = EngineSettings()
    return {
        "status": "ok",
        "execution_mode": settings.execution_mode,
        "allow_averaging_down": settings.allow_averaging_down,
        "require_bracket_order": settings.require_bracket_order,
        "max_daily_llm_candidates": settings.max_daily_llm_candidates,
        "earnings_blackout_days": settings.earnings_blackout_days,
    }


@app.get("/api/v1/command-center")
def get_command_center() -> dict[str, object]:
    return {
        "status": "ok",
        "banner": get_dashboard_banner(),
        "state": get_command_center_state(),
    }


@app.get("/api/v1/account")
def get_account_status() -> dict[str, object]:
    settings = EngineSettings()
    orchestrator = DailyPipelineOrchestrator(
        settings=settings,
        clock=lambda: datetime.now(UTC),
    )
    acct = orchestrator.get_live_account_overview()
    return {
        "status": "ok",
        "account": acct,
        "capital_desk": orchestrator.build_capital_desk_summary(acct),
    }


@app.post("/api/v1/scan/run")
def trigger_daily_scan() -> dict[str, object]:
    global _cached_latest_scan
    settings = EngineSettings()
    orchestrator = DailyPipelineOrchestrator(
        settings=settings,
        clock=lambda: datetime.now(UTC),
    )
    try:
        if settings.alpaca_api_key and settings.alpaca_secret_key:
            _cached_latest_scan = orchestrator.run_live_alpaca_scan()
        else:
            _cached_latest_scan = orchestrator.run_daily_scan(account_equity=100_000.0)
    except Exception:
        _cached_latest_scan = orchestrator.run_daily_scan(account_equity=100_000.0)
    return {
        "status": "ok",
        "result": _cached_latest_scan.model_dump(mode="json"),
    }


@app.get("/api/v1/scan/latest")
def get_latest_scan() -> dict[str, object]:
    orchestrator = DailyPipelineOrchestrator(
        settings=EngineSettings(),
        clock=lambda: datetime.now(UTC),
    )
    acct = orchestrator.get_live_account_overview()
    return {
        "status": "ok",
        "result": _cached_latest_scan.model_dump(mode="json") if _cached_latest_scan else None,
        "account": acct,
        "capital_desk": orchestrator.build_capital_desk_summary(acct),
    }


@app.post("/api/v1/orders/submit")
def submit_manual_order(req: ManualOrderSubmitRequest) -> dict[str, object]:
    settings = EngineSettings()
    orchestrator = DailyPipelineOrchestrator(
        settings=settings,
        clock=lambda: datetime.now(UTC),
    )
    try:
        audit = orchestrator.submit_manual_paper_bracket_order(
            ticker=req.ticker,
            entry_price=req.entry_price,
            atr_14=req.atr_14,
            strategy_name=req.strategy_name,
            direction=req.direction,
        )
        return {"status": "ok", "order": audit}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@app.get("/", response_class=HTMLResponse)
def get_command_center_ui() -> HTMLResponse:
    return HTMLResponse(content=build_command_center_html())
