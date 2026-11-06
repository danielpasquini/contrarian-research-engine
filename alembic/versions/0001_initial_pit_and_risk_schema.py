"""Initial PIT and risk schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-05 14:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_bars_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("adjustment_basis", sa.String(length=16), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("raw_close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("dollar_volume", sa.Float(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint("available_at >= published_at", name="ck_market_bars_daily_pit_order"),
        sa.PrimaryKeyConstraint("id", name="pk_market_bars_daily"),
        sa.UniqueConstraint(
            "ticker",
            "session_date",
            "adjustment_basis",
            name="uq_market_bars_daily_ticker_session_basis",
        ),
    )
    op.create_table(
        "raw_payloads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("ticker", sa.String(length=12), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("available_at >= published_at", name="ck_raw_payloads_pit_order"),
        sa.PrimaryKeyConstraint("id", name="pk_raw_payloads"),
        sa.UniqueConstraint("sha256", name="uq_raw_payloads_sha256"),
    )
    op.create_table(
        "llm_analysis_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("model_id", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("veto_decision", sa.String(length=16), nullable=False),
        sa.Column("raw_response_json", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("available_at >= published_at", name="ck_llm_analysis_cache_pit_order"),
        sa.PrimaryKeyConstraint("id", name="pk_llm_analysis_cache"),
        sa.UniqueConstraint("cache_key", name="uq_llm_analysis_cache_key"),
    )
    op.create_table(
        "orders_audit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_order_id", sa.String(length=64), nullable=False),
        sa.Column("broker_order_id", sa.String(length=64), nullable=True),
        sa.Column("ticker", sa.String(length=12), nullable=False),
        sa.Column("execution_mode", sa.String(length=16), nullable=False),
        sa.Column("order_class", sa.String(length=16), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_loss_price", sa.Float(), nullable=False),
        sa.Column("take_profit_price", sa.Float(), nullable=False),
        sa.Column("guard_passed", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_orders_audit_qty_positive"),
        sa.CheckConstraint("order_class = 'BRACKET'", name="ck_orders_audit_bracket_only"),
        sa.CheckConstraint(
            "execution_mode IN ('research', 'paper')",
            name="ck_orders_audit_execution_mode_no_live",
        ),
        sa.CheckConstraint(
            "stop_loss_price > 0 AND stop_loss_price < entry_price "
            "AND entry_price < take_profit_price",
            name="ck_orders_audit_price_bracket_order",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_orders_audit"),
        sa.UniqueConstraint("client_order_id", name="uq_orders_audit_client_order_id"),
    )


def downgrade() -> None:
    op.drop_table("orders_audit")
    op.drop_table("llm_analysis_cache")
    op.drop_table("raw_payloads")
    op.drop_table("market_bars_daily")
