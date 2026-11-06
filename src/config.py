import sys
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PAPER_ALPACA_URL = "https://paper-api.alpaca.markets"


def _resolve_env_files() -> tuple[str, ...]:
    """Resolves .env file paths across source mode, dist/ folder, and PyInstaller _MEIPASS."""
    candidates: list[Path] = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        meipass = Path(getattr(sys, "_MEIPASS", exe_dir))
        candidates.extend([
            exe_dir / ".env",
            exe_dir.parent / ".env",
            meipass / ".env",
        ])
    found = [str(p) for p in candidates if p.exists()]
    return tuple(dict.fromkeys(found)) if found else (".env",)


class EngineSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_resolve_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    # Application
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    timezone: str = Field(default="America/Sao_Paulo", alias="TIMEZONE")

    # Database
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/contrarian",
        alias="DATABASE_URL",
    )

    # LLM Provider
    llm_provider: str = Field(default="google", alias="LLM_PROVIDER")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    gemini_temperature: float = Field(default=0.0, alias="GEMINI_TEMPERATURE")
    gemini_max_daily_calls: int = Field(default=150, alias="GEMINI_MAX_DAILY_CALLS")
    max_llm_calls_per_candidate: int = Field(default=10, alias="MAX_LLM_CALLS_PER_CANDIDATE")

    # SEC EDGAR
    sec_user_agent: str = Field(
        default="ContrarianResearchEngine research@example.com",
        alias="SEC_USER_AGENT",
    )

    # Alpaca Market Data & Paper Trading
    alpaca_api_key: str = Field(default="", alias="ALPACA_API_KEY")
    alpaca_secret_key: str = Field(default="", alias="ALPACA_SECRET_KEY")
    alpaca_data_feed: str = Field(default="iex", alias="ALPACA_DATA_FEED")
    alpaca_paper: bool = Field(default=True, alias="ALPACA_PAPER")
    alpaca_paper_api_url: str = Field(
        default=PAPER_ALPACA_URL,
        alias="ALPACA_PAPER_API_URL",
    )

    # Execution Safety & Volatility Risk Engine
    execution_mode: str = Field(default="research", alias="EXECUTION_MODE")
    enable_order_submission: bool = Field(default=False, alias="ENABLE_ORDER_SUBMISSION")
    allow_averaging_down: bool = Field(default=False, alias="ALLOW_AVERAGING_DOWN")
    require_bracket_order: bool = Field(default=True, alias="REQUIRE_BRACKET_ORDER")
    earnings_blackout_days: int = Field(default=3, alias="EARNINGS_BLACKOUT_DAYS")
    atr_period: int = Field(default=14, alias="ATR_PERIOD")
    atr_stop_multiplier: float = Field(default=2.0, alias="ATR_STOP_MULTIPLIER")
    min_reward_risk_ratio: float = Field(default=2.0, alias="MIN_REWARD_RISK_RATIO")
    max_risk_per_trade_pct: float = Field(default=0.005, alias="MAX_RISK_PER_TRADE_PCT")
    max_position_pct: float = Field(default=0.08, alias="MAX_POSITION_PCT")
    max_portfolio_exposure: float = Field(default=0.40, alias="MAX_PORTFOLIO_EXPOSURE")
    max_daily_loss_pct: float = Field(default=0.015, alias="MAX_DAILY_LOSS_PCT")
    max_open_positions: int = Field(default=6, alias="MAX_OPEN_POSITIONS")
    max_daily_orders: int = Field(default=2, alias="MAX_DAILY_ORDERS")

    # Pre-Filter Scanner
    universe_size: int = Field(default=500, alias="UNIVERSE_SIZE")
    max_daily_llm_candidates: int = Field(default=15, alias="MAX_DAILY_LLM_CANDIDATES")
    min_average_dollar_volume: float = Field(
        default=20_000_000.0, alias="MIN_AVERAGE_DOLLAR_VOLUME"
    )
    min_share_price: float = Field(default=10.0, alias="MIN_SHARE_PRICE")

    @field_validator("execution_mode", mode="before")
    @classmethod
    def validate_execution_mode(cls, v: str) -> Literal["research", "paper"]:
        normalized = str(v).strip().lower()
        if normalized == "live":
            raise RuntimeError("LIVE trading mode is strictly prohibited.")
        if normalized not in ("research", "paper"):
            raise ValueError(f"Invalid execution_mode: {v}. Allowed: 'research', 'paper'.")
        return normalized  # type: ignore[return-value]

    @field_validator("allow_averaging_down")
    @classmethod
    def enforce_no_averaging_down(cls, v: bool) -> bool:
        if v is not False:
            raise ValueError("ALLOW_AVERAGING_DOWN is immutable and must remain False.")
        return False

    @field_validator("require_bracket_order")
    @classmethod
    def enforce_bracket_order(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("REQUIRE_BRACKET_ORDER is immutable and must remain True.")
        return True

    @field_validator("alpaca_paper")
    @classmethod
    def enforce_alpaca_paper_flag(cls, v: bool) -> bool:
        if v is not True:
            raise RuntimeError(
                "ALPACA_PAPER must be True. Live brokerage connections are forbidden."
            )
        return True

    @field_validator("alpaca_paper_api_url")
    @classmethod
    def enforce_paper_endpoint_url(cls, v: str) -> str:
        clean = v.strip().rstrip("/")
        if clean != PAPER_ALPACA_URL:
            raise RuntimeError(
                f"Non-paper Alpaca endpoint '{v}' is forbidden. Must equal '{PAPER_ALPACA_URL}'."
            )
        return clean

    @field_validator("gemini_temperature")
    @classmethod
    def enforce_zero_temperature(cls, v: float) -> float:
        if v != 0.0:
            raise ValueError("GEMINI_TEMPERATURE must be 0.0 for deterministic extraction.")
        return 0.0

    @field_validator("max_daily_llm_candidates")
    @classmethod
    def enforce_shortlist_cap(cls, v: int) -> int:
        if v < 1 or v > 15:
            raise ValueError("MAX_DAILY_LLM_CANDIDATES must be between 1 and 15.")
        return v

    @field_validator("max_risk_per_trade_pct")
    @classmethod
    def enforce_max_risk_cap(cls, v: float) -> float:
        if v <= 0.0 or v > 0.005:
            raise ValueError("MAX_RISK_PER_TRADE_PCT must be in the range (0.0, 0.005].")
        return v

    @field_validator("max_llm_calls_per_candidate")
    @classmethod
    def enforce_max_llm_calls_per_candidate(cls, v: int) -> int:
        if v < 1:
            raise ValueError("MAX_LLM_CALLS_PER_CANDIDATE must be >= 1.")
        return v
