"""A raw-socket client session its owner can interrupt from another thread.

A blocking socket call (``connect``, the TLS handshake, ``recv`` inside a
protocol library such as ``imaplib``) cannot observe a cancellation predicate:
it returns only when the peer answers or the socket timeout expires. A stalled
or slow server therefore pins an IO-lane worker for its whole response time,
and a runtime destruction barrier that waits for the retiring generation's
work waits with it (measured 7 Nov 2026: a Gmail IMAP ``LOGIN`` held the
Settings barrier for 6.2 s).

``SocketInterrupt`` is the session's handle. The worker binds every socket it
opens (the TCP socket while it connects, then the TLS socket); the owner calls
``interrupt()`` at retirement, which shuts the bound socket down and closes it,
so the blocked call fails at once. A socket bound after the interrupt is
closed immediately and the bind raises ``SocketInterrupted``. The interrupt is
event driven: no timer, poll or thread.

Live interrupts are also registered with the process exit fence:
``core.network.bounded_dns.close_network_admission()`` interrupts every session
still in flight, so a stalled server never holds process exit either.

Each blocking step stays bounded by its own socket timeout; the interrupt only
ends the wait early.
"""
from __future__ import annotations

import socket
import threading
import weakref
from typing import Any, Callable

_live_lock = threading.Lock()
_live: "weakref.WeakSet[SocketInterrupt]" = weakref.WeakSet()


class SocketInterrupted(OSError):
    """The session was interrupted by its owner or the process exit fence."""


def _abort(sock: Any) -> None:
    """Wake every call blocked on ``sock`` and release its handle now.

    ``shutdown()`` wakes a blocked ``recv`` on POSIX but not on Windows, and
    ``sock.close()`` is deferred while a ``makefile()`` reader (``imaplib``)
    still holds the socket. Detaching the descriptor and closing it directly
    closes the handle at once, which fails the blocked call (WSAENOTSOCK on
    Windows) and also ends a ``connect()`` still in progress. Safe to repeat.
    """
    try:
        socket.socket.shutdown(sock, socket.SHUT_RDWR)
    except Exception:
        pass
    try:
        fd = socket.socket.detach(sock)
    except Exception:
        fd = -1
    if fd is not None and fd >= 0:
        try:
            socket.close(fd)
        except Exception:
            pass


class SocketInterrupt:
    """Interrupt handle for one client session (one or more sequential sockets)."""

    __slots__ = ("_lock", "_interrupted", "_socket", "__weakref__")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._interrupted = False
        self._socket: Any = None
        with _live_lock:
            _live.add(self)

    @property
    def interrupted(self) -> bool:
        return self._interrupted

    def bind(self, sock: Any) -> Any:
        """Make ``sock`` the session's interruptible socket; returns it."""
        with self._lock:
            if not self._interrupted:
                self._socket = sock
                return sock
        _abort(sock)
        raise SocketInterrupted("network session interrupted")

    def release(self) -> None:
        """The session ended normally; forget its socket."""
        with self._lock:
            self._socket = None
        with _live_lock:
            _live.discard(self)

    def interrupt(self) -> None:
        """End the session now: the blocked call (and every later bind) fails."""
        with self._lock:
            self._interrupted = True
            sock = self._socket
            self._socket = None
        with _live_lock:
            _live.discard(self)
        if sock is not None:
            _abort(sock)

    def raise_if_interrupted(self) -> None:
        if self._interrupted:
            raise SocketInterrupted("network session interrupted")

    def create_connection(
        self,
        host: str,
        port: int,
        timeout: float,
        *,
        should_continue: Callable[[], bool] | None = None,
    ) -> socket.socket:
        """``socket.create_connection`` with a bounded lookup and an interruptible connect."""
        from core.network.bounded_dns import DnsLookupError, resolve_bounded

        def _continue() -> bool:
            if self._interrupted:
                return False
            return should_continue() if should_continue is not None else True

        try:
            infos = resolve_bounded(host, port, should_continue=_continue)
        except DnsLookupError:
            self.raise_if_interrupted()
            raise
        last_error: OSError | None = None
        for family, socktype, proto, _name, address in infos:
            self.raise_if_interrupted()
            sock = socket.socket(family, socktype, proto)
            self.bind(sock)
            try:
                sock.settimeout(timeout)
                sock.connect(address)
                return sock
            except OSError as exc:
                _abort(sock)
                self.raise_if_interrupted()
                last_error = exc
        if last_error is not None:
            raise last_error
        raise OSError(f"no address for {host}:{port}")


def interrupt_all_sessions() -> int:
    """Process exit fence: interrupt every session in flight. Returns the count."""
    with _live_lock:
        live = tuple(_live)
    for session in live:
        session.interrupt()
    return len(live)


def live_session_count() -> int:
    with _live_lock:
        return len(_live)


__all__ = [
    "SocketInterrupt",
    "SocketInterrupted",
    "interrupt_all_sessions",
    "live_session_count",
]
