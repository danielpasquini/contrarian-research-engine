from datetime import date, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.normalization.calendar import ensure_utc


class PointInTimeRecord(BaseModel):
    """Universal base schema enforcing 3-timestamp UTC integrity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: UUID = Field(default_factory=uuid4)
    published_at: datetime
    collected_at: datetime
    available_at: datetime
    raw_payload_hash: str = Field(min_length=8, max_length=64)

    @field_validator("published_at", "collected_at", "available_at", mode="before")
    @classmethod
    def validate_utc_datetime(cls, v: datetime) -> datetime:
        if not isinstance(v, datetime):
            raise ValueError("Timestamp must be a datetime instance.")
        return ensure_utc(v)

    @model_validator(mode="after")
    def verify_temporal_causality(self) -> "PointInTimeRecord":
        if self.available_at < self.published_at:
            raise ValueError(
                f"Look-ahead violation: available_at ({self.available_at}) "
                f"cannot precede published_at ({self.published_at})."
            )
        return self


class NormalizedBar(PointInTimeRecord):
    """
    Split- and dividend-adjusted daily OHLCV bar with explicit raw dollar OHLC fields
    (`raw_open`, `raw_high`, `raw_low`, `raw_close`) and PIT timestamps (`C-PIT-12`).
    """

    ticker: str = Field(min_length=1, max_length=12)
    session_date: date
    open: float = Field(gt=0.0)
    high: float = Field(gt=0.0)
    low: float = Field(gt=0.0)
    close: float = Field(gt=0.0)
    raw_open: float = Field(gt=0.0)
    raw_high: float = Field(gt=0.0)
    raw_low: float = Field(gt=0.0)
    raw_close: float = Field(gt=0.0)
    volume: int = Field(ge=0)
    dollar_volume: float = Field(ge=0.0)
    split_factor: float = Field(default=1.0, gt=0.0)

    @model_validator(mode="before")
    @classmethod
    def populate_default_raw_ohlc_when_unadjusted(cls, data: object) -> object:
        if isinstance(data, dict):
            patched = dict(data)
            if "raw_open" not in patched and "open" in patched:
                patched["raw_open"] = patched["open"]
            if "raw_high" not in patched and "high" in patched:
                patched["raw_high"] = patched["high"]
            if "raw_low" not in patched and "low" in patched:
                patched["raw_low"] = patched["low"]
            return patched
        return data

    @model_validator(mode="after")
    def validate_bar_bounds(self) -> "NormalizedBar":
        if self.high < self.low:
            raise ValueError(
                f"Invalid bar for {self.ticker}: high ({self.high}) < low ({self.low})."
            )
        if not (self.low <= self.close <= self.high):
            raise ValueError(f"Invalid bar for {self.ticker}: close outside [low, high].")
        if self.raw_high < self.raw_low:
            raise ValueError(
                f"Invalid raw bar for {self.ticker}: "
                f"raw_high ({self.raw_high}) < raw_low ({self.raw_low})."
            )
        if not (self.raw_low <= self.raw_close <= self.raw_high):
            raise ValueError(
                f"Invalid raw bar for {self.ticker}: raw_close outside [raw_low, raw_high]."
            )
        return self
