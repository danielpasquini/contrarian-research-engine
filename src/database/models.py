from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

POSTGRES_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_`%(constraint_name)s`",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=POSTGRES_NAMING_CONVENTION)


class MarketBarDailyORM(Base):
    __tablename__ = "market_bars_daily"
    __table_args__ = (
        CheckConstraint("available_at >= published_at", name="ck_market_bars_daily_pit_order"),
        UniqueConstraint(
            "ticker",
            "session_date",
            "adjustment_basis",
            name="uq_market_bars_daily_ticker_session_basis",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(12), index=True, nullable=False)
    session_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    adjustment_basis: Mapped[str] = mapped_column(String(16), default="RAW", nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    raw_close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    dollar_volume: Mapped[float] = mapped_column(Float, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    raw_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class RawPayloadORM(Base):
    __tablename__ = "raw_payloads"
    __table_args__ = (
        UniqueConstraint("sha256", name="uq_raw_payloads_sha256"),
        CheckConstraint("available_at >= published_at", name="ck_raw_payloads_pit_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(12), index=True, nullable=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )


class LLMAnalysisCacheORM(Base):
    __tablename__ = "llm_analysis_cache"
    __table_args__ = (
        UniqueConstraint("cache_key", name="uq_llm_analysis_cache_key"),
        CheckConstraint("available_at >= published_at", name="ck_llm_analysis_cache_pit_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    ticker: Mapped[str] = mapped_column(String(12), index=True, nullable=False)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    veto_decision: Mapped[str] = mapped_column(String(16), nullable=False)
    raw_response_json: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )


class OrderAuditORM(Base):
    __tablename__ = "orders_audit"
    __table_args__ = (
        UniqueConstraint("client_order_id", name="uq_orders_audit_client_order_id"),
        CheckConstraint("qty > 0", name="ck_orders_audit_qty_positive"),
        CheckConstraint("order_class = 'BRACKET'", name="ck_orders_audit_bracket_only"),
        CheckConstraint(
            "execution_mode IN ('research', 'paper')",
            name="ck_orders_audit_execution_mode_no_live",
        ),
        CheckConstraint(
            "stop_loss_price > 0 AND stop_loss_price < entry_price "
            "AND entry_price < take_profit_price",
            name="ck_orders_audit_price_bracket_order",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_order_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ticker: Mapped[str] = mapped_column(String(12), index=True, nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    order_class: Mapped[str] = mapped_column(String(16), default="BRACKET", nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss_price: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_price: Mapped[float] = mapped_column(Float, nullable=False)
    guard_passed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
