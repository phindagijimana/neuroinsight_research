"""Shared local-port resolution.

App-bound services (the Pennsieve Agent, dev servers, SSH brokers) sometimes
collide with ports that other local software already owns -- the most common
case is the Pennsieve Agent's historical default of ``9000``, which is also
MinIO's default. Rather than hard-coding a single port per service and failing
on a conflict, callers resolve a port from a *preferred* base and step by a
fixed amount (default ``+50``) until they find a candidate that is either

* already served by the service they want (``verify_owner`` returns ``True``), or
* free to bind (nothing is listening and we can claim it).

This keeps port choices predictable (preferred, preferred+50, preferred+100, ...)
instead of a dense +1 scan, so a resolved port stays stable across restarts and
is easy to reason about when several services coexist on one machine.

The module depends only on the standard library so it is safe to import from
connectors, the app entrypoint, or standalone scripts.
"""

from __future__ import annotations

import socket
from typing import Callable, Optional, Tuple

__all__ = [
    "DEFAULT_STEP",
    "DEFAULT_ATTEMPTS",
    "is_bindable",
    "is_tcp_reachable",
    "http_banner",
    "looks_like_minio",
    "resolve_port",
]

DEFAULT_STEP = 50
DEFAULT_ATTEMPTS = 5

# Status values returned alongside a resolved port.
STATUS_OWNED = "owned"  # the desired service is already listening here
STATUS_FREE = "free"    # nothing is listening; the port can be claimed


def is_bindable(port: int, host: str = "127.0.0.1") -> bool:
    """Return True if we can bind ``host:port`` right now (i.e. it is free)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def is_tcp_reachable(host: str, port: int, timeout: float = 0.75) -> bool:
    """Return True if something accepts a TCP connection at ``host:port``."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_banner(host: str, port: int, timeout: float = 1.0) -> str:
    """Best-effort HTTP probe. Returns the first bytes of the response, or ""."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
            return sock.recv(512).decode("latin-1", errors="ignore")
    except OSError:
        return ""


def looks_like_minio(host: str, port: int, timeout: float = 1.0) -> bool:
    """True if the listener at ``host:port`` responds like a MinIO server.

    MinIO advertises itself in the ``Server`` header, so a foreign listener on
    the Pennsieve Agent's port can be identified and stepped past.
    """
    banner = http_banner(host, port, timeout=timeout)
    return "MinIO" in banner


def resolve_port(
    preferred: int,
    *,
    step: int = DEFAULT_STEP,
    attempts: int = DEFAULT_ATTEMPTS,
    host: str = "127.0.0.1",
    verify_owner: Optional[Callable[[str, int], bool]] = None,
) -> Tuple[Optional[int], Optional[str]]:
    """Resolve a usable port starting at ``preferred``, stepping by ``step``.

    Candidates are ``preferred, preferred + step, preferred + 2*step, ...`` up to
    ``attempts`` values. For each candidate:

    * If ``verify_owner`` is given and ``verify_owner(host, port)`` is True, the
      desired service is already running there -> return ``(port, "owned")``.
    * Otherwise, if the port is free to bind -> return ``(port, "free")``.
    * Otherwise the port is occupied by something else -> try the next candidate.

    Returns ``(None, None)`` if no candidate qualifies within ``attempts``.

    When ``verify_owner`` is ``None`` this degenerates to "find the first free
    port from ``preferred`` in ``+step`` increments" -- the common case for a
    server that just needs a port to bind.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    for i in range(attempts):
        port = preferred + i * step
        if port > 65535:
            break
        if verify_owner is not None:
            try:
                if verify_owner(host, port):
                    return port, STATUS_OWNED
            except Exception:
                # A failing owner check must not abort resolution.
                pass
        if is_bindable(port, host):
            return port, STATUS_FREE
    return None, None
