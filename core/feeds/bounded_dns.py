"""Name resolution with a deadline and cancellation, for the feed transports.

``socket.getaddrinfo`` cannot be interrupted and no socket timeout covers it: a
stalled DNS server holds it for the operating system's whole retry schedule
(seconds to tens of seconds on Windows). Feed work runs on the shared IO lane
(four workers, shared with Media, Weather, Reddit, Gmail and Steam), so an
unbounded lookup would pin a worker, ignore retirement and, at exit, keep the
process alive, because the interpreter joins thread-pool workers.

Here the lookup runs on a short-lived daemon thread while the caller waits in
short slices for the answer, its deadline or cancellation. An abandoned lookup
finishes on its own and its answer is dropped; a daemon thread never holds
process exit. Lookups in progress are capped, so a persistent DNS outage cannot
pile up threads: at the cap a new lookup fails at once as a transient network
failure. A successful lookup also leaves the answer in the operating system's
resolver cache for the connection that follows it.
"""
from __future__ import annotations

import ipaddress
import socket
import threading
import time
from typing import Any, Callable

MAX_LOOKUPS_IN_PROGRESS = 8
_WAIT_SLICE_SECONDS = 0.05

_lock = threading.Lock()
_in_progress = 0


class DnsLookupError(OSError):
    """A bounded lookup timed out, was cancelled or could not start."""


def lookups_in_progress() -> int:
    with _lock:
        return _in_progress


def resolve_bounded(
    host: str,
    port: int,
    *,
    timeout: float,
    should_continue: Callable[[], bool] | None = None,
    getaddrinfo: Callable[..., Any] | None = None,
    family: int = 0,
    type: int = socket.SOCK_STREAM,
) -> Any:
    """``getaddrinfo(host, port)`` answered within ``timeout`` seconds, or ``DnsLookupError``.

    A literal IP address needs no DNS and is answered directly. Resolution
    errors (``socket.gaierror``) propagate unchanged.
    """
    global _in_progress
    getaddrinfo = getaddrinfo or socket.getaddrinfo
    try:
        ipaddress.ip_address(str(host).strip("[]"))
    except ValueError:
        pass
    else:
        return getaddrinfo(host, port, family, type)

    with _lock:
        if _in_progress >= MAX_LOOKUPS_IN_PROGRESS:
            raise DnsLookupError("too many DNS lookups in progress")
        _in_progress += 1
    done = threading.Event()
    outcome: dict[str, Any] = {}

    def _lookup() -> None:
        global _in_progress
        try:
            outcome["answer"] = getaddrinfo(host, port, family, type)
        except BaseException as exc:  # handed to the waiting caller, if any
            outcome["error"] = exc
        finally:
            with _lock:
                _in_progress -= 1
            done.set()

    try:
        threading.Thread(target=_lookup, name="srpss-dns", daemon=True).start()
    except RuntimeError as exc:
        with _lock:
            _in_progress -= 1
        raise DnsLookupError("DNS lookup could not start") from exc

    deadline = time.monotonic() + max(0.05, float(timeout))
    while True:
        remaining = deadline - time.monotonic()
        if done.wait(max(0.0, min(_WAIT_SLICE_SECONDS, remaining))):
            break
        if should_continue is not None and not should_continue():
            raise DnsLookupError("DNS lookup cancelled")
        if time.monotonic() >= deadline:
            raise DnsLookupError(f"DNS lookup timed out after {float(timeout):.1f}s")
    error = outcome.get("error")
    if error is not None:
        raise error
    return outcome["answer"]


__all__ = ["DnsLookupError", "MAX_LOOKUPS_IN_PROGRESS", "lookups_in_progress", "resolve_bounded"]
