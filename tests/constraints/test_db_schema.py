import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.types import DateTime

from src.config import EngineSettings
from src.database.models import Base
from src.database.session import create_db_engine_and_session_factory
from src.database.validators import validate_pit_timestamps


def test_no_create_all_in_src() -> None:
    src_dir = Path("src")
    violations = []
    for py_file in src_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"create_all", "drop_all"}:
                violations.append(f"{py_file}:{node.lineno} uses {node.attr}")
    assert not violations, f"Base.metadata.create_all/drop_all found in src/: {violations}"


def test_single_alembic_head() -> None:
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 Alembic head, found {heads}"


def test_every_revision_defines_downgrade() -> None:
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    revisions = list(script.walk_revisions())
    assert len(revisions) >= 1, "Expected at least 1 Alembic migration revision"
    for rev in revisions:
        downgrade_fn = getattr(rev.module, "downgrade", None)
        assert callable(downgrade_fn), f"Revision {rev.revision} missing callable downgrade()"


def test_metadata_naming_convention() -> None:
    convention = Base.metadata.naming_convention
    assert convention is not None, "Base.metadata must define a deterministic naming_convention"
    for key in ("ix", "uq", "ck", "fk", "pk"):
        assert key in convention, f"naming_convention missing key: {key}"


def test_timestamp_columns_are_timestamptz_not_null() -> None:
    for table_name, table in Base.metadata.tables.items():
        for column in table.columns:
            if column.name.endswith("_at"):
                assert not column.nullable, (
                    f"Column {table_name}.{column.name} ends in _at and must be nullable=False"
                )
                assert isinstance(column.type, DateTime), (
                    f"Column {table_name}.{column.name} must be DateTime"
                )
                assert column.type.timezone is True, (
                    f"Column {table_name}.{column.name} must have timezone=True (timestamptz)"
                )


def test_pit_tables_have_three_timestamps_and_check() -> None:
    pit_tables = {"market_bars_daily", "raw_payloads", "llm_analysis_cache"}
    for table_name in pit_tables:
        table = Base.metadata.tables.get(table_name)
        assert table is not None, f"Expected table {table_name} in metadata"
        for ts in ("published_at", "collected_at", "available_at"):
            assert ts in table.columns, f"{table_name} missing required PIT timestamp: {ts}"

        check_constraints = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        has_pit_check = any(
            "available_at >= published_at" in str(c.sqltext)
            or ("available_at" in str(c.sqltext) and "published_at" in str(c.sqltext))
            for c in check_constraints
        )
        assert has_pit_check, f"{table_name} missing CHECK (available_at >= published_at)"


def test_order_audit_check_constraints_declared() -> None:
    table = Base.metadata.tables.get("orders_audit")
    assert table is not None, "orders_audit table missing from metadata"

    unique_cols = {
        tuple(col.name for col in c.columns)
        for c in table.constraints
        if isinstance(c, UniqueConstraint)
    }
    has_client_order_id_unique = ("client_order_id",) in unique_cols or table.columns[
        "client_order_id"
    ].unique
    assert has_client_order_id_unique, "orders_audit missing UNIQUE(client_order_id)"

    check_constraints = [c for c in table.constraints if isinstance(c, CheckConstraint)]
    check_texts = [str(c.sqltext) for c in check_constraints]

    assert any("qty > 0" in text for text in check_texts), "Missing CHECK (qty > 0)"
    assert any("order_class" in text and "BRACKET" in text for text in check_texts), (
        "Missing CHECK (order_class = 'BRACKET')"
    )
    assert any(
        "execution_mode" in text and "research" in text and "paper" in text for text in check_texts
    ), "Missing CHECK (execution_mode IN ('research', 'paper'))"
    assert any(
        "stop_loss_price < entry_price" in text or "stop_loss_price" in text
        for text in check_texts
    ), "Missing price ordering CHECK"


def test_natural_key_uniques_declared() -> None:
    market_bars = Base.metadata.tables.get("market_bars_daily")
    assert market_bars is not None
    mb_uniques = {
        tuple(col.name for col in c.columns)
        for c in market_bars.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert ("ticker", "session_date", "adjustment_basis") in mb_uniques

    raw_payloads = Base.metadata.tables.get("raw_payloads")
    assert raw_payloads is not None
    rp_uniques = {
        tuple(col.name for col in c.columns)
        for c in raw_payloads.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert ("sha256",) in rp_uniques or raw_payloads.columns["sha256"].unique

    llm_cache = Base.metadata.tables.get("llm_analysis_cache")
    assert llm_cache is not None
    llm_uniques = {
        tuple(col.name for col in c.columns)
        for c in llm_cache.constraints
        if isinstance(c, UniqueConstraint)
    }
    assert ("cache_key",) in llm_uniques or llm_cache.columns["cache_key"].unique


def test_database_validators_and_session_factory() -> None:
    t1 = datetime(2026, 3, 10, 14, 0, tzinfo=UTC)
    t2 = datetime(2026, 3, 10, 14, 5, tzinfo=UTC)
    t3 = datetime(2026, 3, 10, 14, 30, tzinfo=UTC)
    validate_pit_timestamps(published_at=t1, collected_at=t2, available_at=t3)

    # Naive timestamp rejected
    with pytest.raises(ValueError, match="timezone-aware"):
        validate_pit_timestamps(
            published_at=datetime(2026, 3, 10, 14, 0),  # noqa: DTZ001
            collected_at=t2,
            available_at=t3,
        )

    # Out-of-order available_at < published_at rejected
    with pytest.raises(ValueError, match="available_at"):
        validate_pit_timestamps(published_at=t3, collected_at=t2, available_at=t1)

    engine, session_factory = create_db_engine_and_session_factory(
        EngineSettings(database_url="sqlite+pysqlite:///:memory:")
    )
    assert engine is not None
    assert callable(session_factory)
