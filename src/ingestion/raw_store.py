import hashlib
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from src.database.validators import validate_pit_timestamps


class StoredRawPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sha256: str
    provider: str
    source_type: str
    ticker: str | None
    published_at: datetime
    collected_at: datetime
    available_at: datetime
    file_path: Path


class RawPayloadStore:
    """
    Immutable Write-Once Raw Payload Storage (`C-PIT-13`).
    Under `data/raw/`, files are keyed strictly by SHA-256 and never rewritten.
    """

    def __init__(self, base_dir: Path | str = "data/raw") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _hash_content(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _get_target_path(self, sha256_hash: str) -> Path:
        prefix = sha256_hash[:2]
        dir_path = self.base_dir / prefix
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path / f"{sha256_hash}.bin"

    def write_direct_raw_file(self, sha256_hash: str, content: bytes) -> Path:
        target = self._get_target_path(sha256_hash)
        if target.exists():
            existing_content = target.read_bytes()
            if existing_content != content:
                raise FileExistsError(
                    f"Immutable raw payload violation: {target} already exists with different data."
                )
            return target
        target.write_bytes(content)
        return target

    def store_payload(
        self,
        content: bytes,
        provider: str,
        source_type: str,
        published_at: datetime,
        collected_at: datetime,
        available_at: datetime,
        ticker: str | None = None,
    ) -> StoredRawPayload:
        validate_pit_timestamps(
            published_at=published_at,
            collected_at=collected_at,
            available_at=available_at,
        )

        sha256_hash = self._hash_content(content)
        file_path = self.write_direct_raw_file(sha256_hash, content)

        return StoredRawPayload(
            sha256=sha256_hash,
            provider=provider,
            source_type=source_type,
            ticker=ticker,
            published_at=published_at,
            collected_at=collected_at,
            available_at=available_at,
            file_path=file_path,
        )

    def read_payload(self, sha256_hash: str) -> bytes:
        target = self._get_target_path(sha256_hash)
        if not target.exists():
            raise FileNotFoundError(f"Raw payload {sha256_hash} not found in store.")
        content = target.read_bytes()
        actual_hash = self._hash_content(content)
        if actual_hash != sha256_hash:
            raise ValueError(
                f"Payload checksum mismatch: expected {sha256_hash}, found {actual_hash}."
            )
        return content
