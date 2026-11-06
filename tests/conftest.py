import ipaddress
import socket
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

import pytest

from src.config import EngineSettings

# Store original socket.connect
_ORIGINAL_CONNECT = socket.socket.connect


def _is_loopback_address(host: str) -> bool:
    if host in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def block_external_sockets(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """
    Autouse fixture enforcing C-TEST-03: Blocks non-loopback outbound socket connections
    unless the test has the 'network' or 'paper_gate' marker.
    """
    allow_network = bool(
        request.node.get_closest_marker("network") or request.node.get_closest_marker("paper_gate")
    )

    if allow_network:
        yield
        return

    def guarded_connect(self: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) and len(address) > 0 else str(address)
        if not _is_loopback_address(str(host)):
            raise RuntimeError(
                f"Outbound network access to '{host}' blocked by offline socket guard (C-TEST-03). "
                "Unit tests must use fakes/fixtures and run 100% offline."
            )
        return _ORIGINAL_CONNECT(self, address)

    socket.socket.connect = guarded_connect  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = _ORIGINAL_CONNECT  # type: ignore[assignment]


@pytest.fixture
def frozen_clock() -> datetime:
    """Deterministic frozen UTC timestamp for tests."""
    return datetime(2026, 5, 4, 14, 0, 0, tzinfo=UTC)


@pytest.fixture
def test_settings() -> EngineSettings:
    """Default EngineSettings instance for tests."""
    return EngineSettings()
