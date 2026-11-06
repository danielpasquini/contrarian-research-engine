from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.ingestion.raw_store import RawPayloadStore, StoredRawPayload


def test_raw_payload_write_once(tmp_path: Path) -> None:
    store = RawPayloadStore(base_dir=tmp_path)
    sample_content = b'{"status": "OK", "articles": [{"title": "Test Wire"}]}'
    pub_at = datetime(2026, 3, 10, 14, 0, 0, tzinfo=UTC)
    col_at = datetime(2026, 3, 10, 14, 5, 0, tzinfo=UTC)
    avail_at = datetime(2026, 3, 10, 14, 30, 0, tzinfo=UTC)

    # 1. First write must succeed and return metadata
    stored: StoredRawPayload = store.store_payload(
        content=sample_content,
        provider="alpaca",
        source_type="news",
        ticker="AAPL",
        published_at=pub_at,
        collected_at=col_at,
        available_at=avail_at,
    )

    assert stored.provider == "alpaca"
    assert stored.source_type == "news"
    assert stored.ticker == "AAPL"
    assert len(stored.sha256) == 64
    assert stored.file_path.exists()
    assert stored.file_path.read_bytes() == sample_content

    # 2. Keyed by SHA-256: idempotently re-storing identical content returns stored record
    stored_again = store.store_payload(
        content=sample_content,
        provider="alpaca",
        source_type="news",
        ticker="AAPL",
        published_at=pub_at,
        collected_at=col_at,
        available_at=avail_at,
    )
    assert stored_again.sha256 == stored.sha256
    assert stored_again.file_path == stored.file_path

    # 3. Read payload verifies content hash
    content_read = store.read_payload(stored.sha256)
    assert content_read == sample_content

    # 4. Attempting to overwrite existing file with different content raises FileExistsError
    with pytest.raises(FileExistsError, match="Immutable raw payload"):
        store.write_direct_raw_file(stored.sha256, b"tampered content")
