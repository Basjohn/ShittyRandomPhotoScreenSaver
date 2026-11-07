"""A raw-socket client session its owner can interrupt from another thread.

A blocking socket call (``connect``, the TLS handshake, ``recv`` inside a
protocol library such as ``imaplib``) cannot observe a cancellation predicate:
it returns only when the peer answers or the socket timeout expires. A stalled
or slow server therefore pins an IO-lane worker for its whole response time,
and a runtime destruction barrier that waits for the retiring generation's
work waits with it (measured 7 Nov 2026: a Gmail IMAP ``LOGIN`` held the
Settings barrier for 6.2 s).

``SocketInterrupt`` is the session's handle. The worker thread owns every
socket: it connects non-blocking and runs TLS through an ``SSLObject`` over
memory BIOs (``SSLContext.wrap_bio``), so every wait is its own ``select`` on
the socket AND the session's wake socket. ``interrupt()`` only sets a flag and
writes one byte to the wake socket; the waiting worker sees it, raises
``SocketInterrupted`` and closes its own sockets. The interrupting thread
never closes or detaches a descriptor another thread may be using (a closed
handle number is reused at once, and OpenSSL would keep reading the old
number). No timer, poll or helper thread.

Each blocking step (connect, one handshake, one read, one write) is bounded by
the step timeout; the interrupt only ends the wait early. Live sessions are
registered with the process exit fence:
``core.network.bounded_dns.close_network_admission()`` signals every session
still in flight.
"""
from __future__ import annotations

import errno
import select
import socket
import ssl
import threading
import time
import weakref
from typing import Callable

_live_lock = threading.Lock()
_live: "weakref.WeakSet[SocketInterrupt]" = weakref.WeakSet()
_RECV_CHUNK = 65536
# connect_ex results meaning "in progress" (WSAEWOULDBLOCK is 10035 on Windows).
_IN_PROGRESS = {errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EAGAIN, 10035}


class SocketInterrupted(OSError):
    """The session was interrupted by its owner or the process exit fence."""


class SocketInterrupt:
    """Interrupt handle for one client session; its sockets belong to the worker thread."""

    __slots__ = ("_lock", "_interrupted", "_wake_r", "_wake_w", "_socket", "__weakref__")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._interrupted = False
        self._wake_r, self._wake_w = socket.socketpair()
        self._wake_r.setblocking(False)
        self._wake_w.setblocking(False)
        self._socket: socket.socket | None = None     # the session's TCP socket (worker-owned)
        with _live_lock:
            _live.add(self)

    @property
    def interrupted(self) -> bool:
        return self._interrupted

    def interrupt(self) -> None:
        """Signal the session to end (any thread). Closes nothing."""
        with self._lock:
            if self._interrupted:
                return
            self._interrupted = True
            if self._wake_w is not None:
                try:
                    self._wake_w.send(b"\0")
                except OSError:
                    pass                                   # wake buffer full: already signalled
        with _live_lock:
            _live.discard(self)

    def release(self) -> None:
        """Worker thread, session over: close the wake pair (the session's sockets are closed already)."""
        with self._lock:
            wake_r, wake_w = self._wake_r, self._wake_w
            self._wake_r = self._wake_w = None
        for sock in (wake_r, wake_w):
            if sock is not None:
                sock.close()
        with _live_lock:
            _live.discard(self)

    def raise_if_interrupted(self) -> None:
        if self._interrupted:
            raise SocketInterrupted("network session interrupted")

    def wait(self, sock: socket.socket, *, write: bool, deadline: float, error: bool = False) -> None:
        """Wait until ``sock`` is readable (or writable), the interrupt fires, or the step deadline passes."""
        while True:
            self.raise_if_interrupted()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("network step timed out")
            wake = self._wake_r
            readers = [wake] if write else [sock, wake]
            readable, writable, failed = select.select(
                [r for r in readers if r is not None], [sock] if write else [], [sock] if error else [], remaining)
            self.raise_if_interrupted()
            if readable or writable or failed:
                return

    def create_connection(
        self,
        host: str,
        port: int,
        timeout: float,
        *,
        should_continue: Callable[[], bool] | None = None,
    ) -> socket.socket:
        """A connected non-blocking TCP socket: bounded lookup, interruptible bounded connect (worker thread)."""
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
            try:
                sock.setblocking(False)
                code = sock.connect_ex(address)
                if code != 0 and code not in _IN_PROGRESS:
                    raise OSError(code, f"connect to {address} failed")
                if code != 0:
                    self.wait(sock, write=True, error=True, deadline=time.monotonic() + timeout)
                    code = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                    if code:
                        raise OSError(code, f"connect to {address} failed")
                self._socket = sock
                return sock
            except BaseException as exc:
                sock.close()                               # this (the worker) thread owns it
                if isinstance(exc, SocketInterrupted) or not isinstance(exc, OSError):
                    raise
                last_error = exc
        if last_error is not None:
            raise last_error
        raise OSError(f"no address for {host}:{port}")

    def open_tls(
        self,
        host: str,
        port: int,
        timeout: float,
        context: ssl.SSLContext,
        *,
        should_continue: Callable[[], bool] | None = None,
    ) -> "InterruptibleTLSStream":
        """Connect and complete the TLS handshake (certificate and hostname checked by ``context``)."""
        sock = self.create_connection(host, port, timeout, should_continue=should_continue)
        try:
            stream = InterruptibleTLSStream(self, sock, context, host, timeout)
            stream.handshake()
        except BaseException:
            sock.close()
            raise
        return stream


class _NoFile:
    """``imaplib`` keeps ``sock.makefile('rb')`` only to close it; it reads through ``recv``."""

    def close(self) -> None:
        return None


class InterruptibleTLSStream:
    """TLS over a non-blocking socket via memory BIOs; every wait also watches the session's wake socket.

    Offers what ``imaplib.IMAP4`` uses of its socket: ``recv``, ``sendall``, ``makefile``, ``shutdown``,
    ``close``, ``settimeout`` and ``gettimeout``. Used only by the thread that owns the session.
    """

    def __init__(self, interrupt: SocketInterrupt, sock: socket.socket, context: ssl.SSLContext,
                 host: str, timeout: float) -> None:
        self._interrupt = interrupt
        self._sock = sock
        self._timeout = float(timeout)
        self._incoming = ssl.MemoryBIO()
        self._outgoing = ssl.MemoryBIO()
        self._tls = context.wrap_bio(self._incoming, self._outgoing, server_hostname=host)

    # -- the pump -------------------------------------------------------------------------------------------
    def _flush(self, deadline: float) -> None:
        pending = self._outgoing.read()
        view = memoryview(pending)
        while view:
            try:
                sent = self._sock.send(view)
                view = view[sent:]
            except (BlockingIOError, InterruptedError):
                self._interrupt.wait(self._sock, write=True, deadline=deadline)

    def _fill(self, deadline: float) -> None:
        while True:
            try:
                data = self._sock.recv(_RECV_CHUNK)
            except (BlockingIOError, InterruptedError):
                self._interrupt.wait(self._sock, write=False, deadline=deadline)
                continue
            if data:
                self._incoming.write(data)
            else:
                self._incoming.write_eof()
            return

    def _run(self, operation):
        deadline = time.monotonic() + self._timeout       # one bounded step
        while True:
            self._interrupt.raise_if_interrupted()
            try:
                result = operation()
            except ssl.SSLWantReadError:
                self._flush(deadline)
                self._fill(deadline)
                continue
            except ssl.SSLWantWriteError:
                self._flush(deadline)
                continue
            self._flush(deadline)
            return result

    # -- the socket surface imaplib uses ----------------------------------------------------------------------
    def handshake(self) -> None:
        self._run(self._tls.do_handshake)

    def recv(self, size: int) -> bytes:
        try:
            return self._run(lambda: self._tls.read(size))
        except (ssl.SSLZeroReturnError, ssl.SSLEOFError):
            return b""

    def sendall(self, data: bytes) -> None:
        view = memoryview(data)
        while view:
            written = self._run(lambda: self._tls.write(view))
            view = view[written:]

    def makefile(self, mode: str = "rb") -> _NoFile:
        return _NoFile()

    def settimeout(self, timeout: float | None) -> None:
        if timeout:
            self._timeout = float(timeout)

    def gettimeout(self) -> float:
        return self._timeout

    def shutdown(self, how: int = socket.SHUT_RDWR) -> None:
        try:
            self._sock.shutdown(how)
        except OSError:
            pass

    def close(self) -> None:
        """Owner (worker) thread only."""
        self._sock.close()


def interrupt_all_sessions() -> int:
    """Process exit fence: signal every session in flight. Returns the count."""
    with _live_lock:
        live = tuple(_live)
    for session in live:
        session.interrupt()
    return len(live)


def live_session_count() -> int:
    with _live_lock:
        return len(_live)


__all__ = [
    "InterruptibleTLSStream",
    "SocketInterrupt",
    "SocketInterrupted",
    "interrupt_all_sessions",
    "live_session_count",
]
