"""Tests for the shared local-port resolution helper."""

import socket

import pytest

from backend.core import ports


def _bind(port: int) -> socket.socket:
    """Occupy a local port and return the listening socket (caller closes it)."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", port))
    srv.listen()
    return srv


def _free_base() -> int:
    """Pick a high base port that (with +50 steps) is currently free."""
    for base in range(21000, 40000, 1000):
        if all(ports.is_bindable(base + i * ports.DEFAULT_STEP) for i in range(3)):
            return base
    raise RuntimeError("no free port block for test")


def test_is_bindable_true_for_free_port():
    base = _free_base()
    assert ports.is_bindable(base) is True


def test_is_bindable_false_when_occupied():
    base = _free_base()
    srv = _bind(base)
    try:
        assert ports.is_bindable(base) is False
    finally:
        srv.close()


def test_is_tcp_reachable_true_when_listening():
    base = _free_base()
    srv = _bind(base)
    try:
        assert ports.is_tcp_reachable("127.0.0.1", base) is True
    finally:
        srv.close()


def test_is_tcp_reachable_false_when_nothing_there():
    base = _free_base()
    assert ports.is_tcp_reachable("127.0.0.1", base) is False


def test_resolve_returns_preferred_when_free():
    base = _free_base()
    port, status = ports.resolve_port(base, verify_owner=None)
    assert port == base
    assert status == ports.STATUS_FREE


def test_resolve_steps_by_50_when_preferred_taken():
    base = _free_base()
    srv = _bind(base)
    try:
        port, status = ports.resolve_port(base, verify_owner=None)
        assert port == base + ports.DEFAULT_STEP
        assert status == ports.STATUS_FREE
    finally:
        srv.close()


def test_resolve_steps_past_multiple_conflicts():
    base = _free_base()
    s1 = _bind(base)
    s2 = _bind(base + ports.DEFAULT_STEP)
    try:
        port, status = ports.resolve_port(base, verify_owner=None)
        assert port == base + 2 * ports.DEFAULT_STEP
        assert status == ports.STATUS_FREE
    finally:
        s1.close()
        s2.close()


def test_resolve_returns_owned_when_owner_present():
    base = _free_base()
    srv = _bind(base)
    try:
        # A "reachable" listener is treated as the owner we want.
        port, status = ports.resolve_port(
            base,
            verify_owner=lambda h, p: ports.is_tcp_reachable(h, p),
        )
        assert port == base
        assert status == ports.STATUS_OWNED
    finally:
        srv.close()


def test_resolve_prefers_free_over_foreign_listener():
    """A reachable-but-not-owned listener (e.g. MinIO) is stepped past."""
    base = _free_base()
    srv = _bind(base)  # foreign service on the preferred port
    try:
        port, status = ports.resolve_port(
            base,
            verify_owner=lambda h, p: False,  # never our owner
        )
        assert port == base + ports.DEFAULT_STEP
        assert status == ports.STATUS_FREE
    finally:
        srv.close()


def test_resolve_gives_up_after_attempts():
    base = _free_base()
    socks = [_bind(base + i * ports.DEFAULT_STEP) for i in range(ports.DEFAULT_ATTEMPTS)]
    try:
        port, status = ports.resolve_port(base, verify_owner=None)
        assert port is None
        assert status is None
    finally:
        for s in socks:
            s.close()


def test_resolve_rejects_bad_attempts():
    with pytest.raises(ValueError):
        ports.resolve_port(20000, attempts=0)


def test_resolve_stops_at_port_ceiling():
    # Near the 16-bit ceiling, stepping must not return an invalid port.
    port, status = ports.resolve_port(65500, step=100, attempts=5, verify_owner=None)
    assert port is None or port <= 65535
