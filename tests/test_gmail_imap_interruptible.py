"""A retiring Gmail runtime interrupts its IMAP session instead of waiting for the server.

Found 7 Nov 2026 by the live check's Settings round trip: the display
destruction barrier (reason ``settings``) waited 6183 ms for the Gmail
runtime's in-flight IMAP ``LOGIN``, which then returned ``[UNAVAILABLE]
Temporary System Error``. A blocking socket read cannot observe the owner's
``should_cancel`` predicate, so the fetch held the retiring generation's IO
work (and with it the barrier) for the server's whole response time.

The contract (Docs/Contracts.md -> Network transports): every socket an IMAP
session opens is bound to a ``SocketInterrupt``; ``stop()``/``retire()``
interrupts the owner's sessions, which closes the socket so the blocked step
returns at once and the fetch settles as a cancellation, not an error.

Only loopback sockets are used: the fake server accepts and then never answers
``LOGIN`` (or never answers the TLS handshake). No real mail server is reached.
"""
from __future__ import annotations

import shutil
import socket
import ssl
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.network.tls as tls
from core.gmail import gmail_imap
from core.gmail.gmail_imap import GmailImapClient

# Generous against a 6 s+ server stall, tight against "waits for the server".
_SETTLE_BOUND_S = 1.0
_SERVER_HOLD_S = 8.0


class _StallingImapServer:
    """Loopback IMAP server: greets, answers CAPABILITY, then holds LOGIN unanswered.

    ``speak=False`` accepts the TCP connection and never sends a byte, which
    stalls a client in its TLS handshake.
    """

    def __init__(self, *, speak: bool = True) -> None:
        self._speak = speak
        self._listener = socket.create_server(("127.0.0.1", 0))
        self._listener.settimeout(_SERVER_HOLD_S)
        self.port = self._listener.getsockname()[1]
        self.login_seen = threading.Event()
        self.connected = threading.Event()
        self._release = threading.Event()
        self._thread = threading.Thread(target=self._serve, name="fake-imap", daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        try:
            conn, _addr = self._listener.accept()
        except OSError:
            return
        self.connected.set()
        with conn:
            conn.settimeout(_SERVER_HOLD_S)
            try:
                if not self._speak:
                    self._release.wait(_SERVER_HOLD_S)
                    return
                conn.sendall(b"* OK [CAPABILITY IMAP4rev1] fake ready\r\n")
                buffer = b""
                while not self._release.is_set():
                    chunk = conn.recv(4096)
                    if not chunk:
                        return
                    buffer += chunk
                    while b"\r\n" in buffer:
                        line, buffer = buffer.split(b"\r\n", 1)
                        parts = line.split(b" ")
                        tag = parts[0]
                        command = parts[1].upper() if len(parts) > 1 else b""
                        if command == b"CAPABILITY":
                            conn.sendall(
                                b"* CAPABILITY IMAP4rev1\r\n" + tag + b" OK done\r\n"
                            )
                        elif command == b"LOGIN":
                            self.login_seen.set()
                            # Never answer: hold until released or timed out.
                            self._release.wait(_SERVER_HOLD_S)
                            return
            except OSError:
                return

    def close(self) -> None:
        self._release.set()
        try:
            self._listener.close()
        except OSError:
            pass
        self._thread.join(_SERVER_HOLD_S + 2.0)


class _PlainSocket(socket.socket):
    """A socket standing in for the TLS layer, so the fake server can speak IMAP."""

    def do_handshake(self) -> None:
        return None


class _PlainObject:
    """``SSLObject`` stand-in: passes bytes straight through the memory BIOs."""

    def __init__(self, incoming, outgoing):
        self._incoming, self._outgoing = incoming, outgoing

    def do_handshake(self):
        return None

    def read(self, size):
        data = self._incoming.read(size)
        if not data and not self._incoming.eof:
            raise ssl.SSLWantReadError()
        return data

    def write(self, data):
        return self._outgoing.write(bytes(data))


class _PlainContext:
    """Test-only stand-in for the verified context: no TLS on the loopback link (the IMAP exchange is what
    the tests hold up; the real context's TLS is covered by the handshake and bad-hostname tests)."""

    def wrap_bio(self, incoming, outgoing, server_hostname=None, **_kw):
        return _PlainObject(incoming, outgoing)

    def wrap_socket(self, sock, server_hostname=None, do_handshake_on_connect=True, **_kw):
        # The pre-fix transport (``imaplib.IMAP4_SSL``) wraps the socket; kept so the controls run on main.
        timeout = sock.gettimeout()
        plain = _PlainSocket(sock.family, sock.type, sock.proto, fileno=sock.detach())
        plain.settimeout(timeout)
        return plain


@pytest.fixture
def ui_inline(monkeypatch):
    monkeypatch.setattr(
        "widgets.gmail_runtime.ThreadManager.run_on_ui_thread",
        staticmethod(lambda func, *a, **k: func(*a, **k) or True),
    )


def _point_client_at(monkeypatch, server: _StallingImapServer, *, plain: bool) -> None:
    monkeypatch.setattr(gmail_imap, "IMAP_HOST", "127.0.0.1")
    monkeypatch.setattr(gmail_imap, "IMAP_PORT", server.port)
    if plain:
        monkeypatch.setattr(tls, "verified_client_context", lambda: _PlainContext())


class _Submitter:
    """IO lane stand-in: each submitted task runs on its own thread."""

    def __init__(self) -> None:
        self.threads: list[threading.Thread] = []

    def submit_io_task(self, func, *args, callback=None, category=None, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        self.threads.append(thread)
        thread.start()
        return len(self.threads)


def _owner(client, submitter=None):
    from widgets.gmail_runtime import GmailRuntimeConfig, _SharedGmailRuntimeOwner

    backend = SimpleNamespace(is_initialized=True, is_authenticated=True, client=client)
    owner = _SharedGmailRuntimeOwner(
        config=GmailRuntimeConfig(),
        thread_manager=submitter if submitter is not None else SimpleNamespace(),
        runtime_generation=None,
        backend=backend,
    )
    owner._running = True
    owner._owner_generation = 1
    owner._fetch_request_id = 1
    owner._fetch_in_progress = True
    errors: list[str] = []
    original_error = owner._commit_fetch_error

    def _error(generation, request_id, message):
        errors.append(message)
        original_error(generation, request_id, message)

    owner._commit_fetch_error = _error
    return owner, errors


def _start_fetch(owner, client) -> threading.Thread:
    worker = threading.Thread(
        target=owner._fetch_emails_async, args=(client, 1, 1), daemon=True,
    )
    worker.start()
    return worker


def _retire_and_time(owner, worker: threading.Thread) -> float:
    started = time.monotonic()
    owner.retire()
    worker.join(_SETTLE_BOUND_S)
    return time.monotonic() - started


def test_retiring_the_runtime_ends_an_unanswered_login_promptly(monkeypatch, ui_inline):
    server = _StallingImapServer()
    _point_client_at(monkeypatch, server, plain=True)
    client = GmailImapClient("user@example.com", "app-password")
    owner, errors = _owner(client)
    worker = _start_fetch(owner, client)
    try:
        assert server.login_seen.wait(5.0), "the fake server never saw LOGIN"
        elapsed = _retire_and_time(owner, worker)
        assert not worker.is_alive(), (
            f"the fetch was still blocked in LOGIN {elapsed:.2f}s after retirement "
            "(the barrier waits for the server)"
        )
        assert elapsed < _SETTLE_BOUND_S
        assert errors == [], "an interrupted fetch is a cancellation, not an error"
        assert owner._session_interrupts == set()
        assert owner._fetch_in_progress is False
    finally:
        server.close()
        worker.join(_SERVER_HOLD_S + 5.0)


def test_retiring_the_runtime_ends_a_stalled_tls_handshake_promptly(monkeypatch, ui_inline):
    # The real verified context: the server never answers the ClientHello.
    server = _StallingImapServer(speak=False)
    _point_client_at(monkeypatch, server, plain=False)
    client = GmailImapClient("user@example.com", "app-password")
    owner, errors = _owner(client)
    worker = _start_fetch(owner, client)
    try:
        assert server.connected.wait(5.0), "the client never connected"
        time.sleep(0.2)  # let the client enter the handshake read
        elapsed = _retire_and_time(owner, worker)
        assert not worker.is_alive(), (
            f"the fetch was still in its TLS handshake {elapsed:.2f}s after retirement"
        )
        assert errors == []
    finally:
        server.close()
        worker.join(_SERVER_HOLD_S + 5.0)


def test_retiring_the_runtime_ends_an_action_blocked_in_login(monkeypatch, ui_inline):
    server = _StallingImapServer()
    _point_client_at(monkeypatch, server, plain=True)
    client = GmailImapClient("user@example.com", "app-password")
    submitter = _Submitter()
    owner, _errors = _owner(client, submitter)
    assert owner.dispatch_action("mark_read", "42") is True
    worker = submitter.threads[0]
    try:
        assert server.login_seen.wait(5.0), "the fake server never saw LOGIN"
        elapsed = _retire_and_time(owner, worker)
        assert not worker.is_alive(), (
            f"the action was still blocked in LOGIN {elapsed:.2f}s after retirement"
        )
        assert owner._session_interrupts == set()
    finally:
        server.close()
        worker.join(_SERVER_HOLD_S + 5.0)


def test_the_process_exit_fence_interrupts_a_session_in_flight(monkeypatch):
    import core.network.bounded_dns as bounded_dns

    # A private fence, so closing it cannot leak into later tests.
    monkeypatch.setattr(bounded_dns, "_admission_closed", threading.Event())
    server = _StallingImapServer()
    _point_client_at(monkeypatch, server, plain=True)
    client = GmailImapClient("user@example.com", "app-password")
    outcome: dict[str, BaseException] = {}

    def _fetch() -> None:
        try:
            client.list_messages(max_results=1)
        except BaseException as exc:  # recorded for the assertion
            outcome["error"] = exc

    worker = threading.Thread(target=_fetch, daemon=True)
    worker.start()
    try:
        assert server.login_seen.wait(5.0), "the fake server never saw LOGIN"
        started = time.monotonic()
        bounded_dns.close_network_admission()
        worker.join(_SETTLE_BOUND_S)
        elapsed = time.monotonic() - started
        assert not worker.is_alive(), (
            f"the session was still blocked {elapsed:.2f}s after the exit fence closed"
        )
        from core.gmail.gmail_client import GmailFetchCancelled

        assert isinstance(outcome.get("error"), GmailFetchCancelled)
    finally:
        server.close()
        worker.join(_SERVER_HOLD_S + 5.0)


def test_the_interrupting_thread_never_closes_the_session_socket(monkeypatch, ui_inline):
    """``interrupt()`` only signals: the socket stays open until the worker thread closes it itself.

    Closing a descriptor another thread is reading lets a new socket reuse its handle number while OpenSSL
    still reads the old one, so the retiring reader could consume another connection's bytes.
    """
    server = _StallingImapServer()
    _point_client_at(monkeypatch, server, plain=True)
    client = GmailImapClient("user@example.com", "app-password")
    owner, _errors = _owner(client)
    worker = _start_fetch(owner, client)
    gate = threading.Event()
    closers: list[int] = []
    try:
        assert server.login_seen.wait(5.0), "the fake server never saw LOGIN"
        (session,) = tuple(owner._session_interrupts)
        target = session._socket
        assert target is not None and target.fileno() != -1
        real_close = socket.socket.close

        def watched_close(sock):
            if sock is target:
                closers.append(threading.get_ident())
                if threading.get_ident() == worker.ident:
                    gate.wait(5.0)          # hold the worker so the open socket can be observed
            return real_close(sock)

        monkeypatch.setattr(socket.socket, "close", watched_close)
        owner.retire()                      # interrupt() runs on this thread and returns
        assert target.fileno() != -1, "the interrupting thread closed the session's socket"
        assert threading.get_ident() not in closers
        gate.set()
        worker.join(_SETTLE_BOUND_S)
        assert not worker.is_alive()
        assert target.fileno() == -1, "the worker never closed its socket"
        assert closers and set(closers) == {worker.ident}
    finally:
        gate.set()
        server.close()
        worker.join(_SERVER_HOLD_S + 5.0)


def _openssl() -> str | None:
    found = shutil.which("openssl")
    for candidate in (found, r"C:\Program Files\Git\usr\bin\openssl.exe",
                      r"C:\Program Files\Git\mingw64\bin\openssl.exe"):
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def test_a_certificate_for_another_host_still_fails_verification(tmp_path):
    """The interruptible TLS path keeps the context's hostname check (a cert for another name is refused)."""
    from core.network.interruptible_socket import SocketInterrupt

    openssl = _openssl()
    if openssl is None:
        pytest.skip("openssl is not available to make a throwaway loopback certificate")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    made = subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key),
                           "-out", str(cert), "-days", "2", "-subj", "/CN=wrong.example",
                           "-addext", "subjectAltName=DNS:wrong.example"], capture_output=True, timeout=60)
    if made.returncode != 0:
        pytest.skip("openssl could not make a certificate here")
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(cert, key)
    listener = socket.create_server(("127.0.0.1", 0))
    listener.settimeout(10.0)
    port = listener.getsockname()[1]

    def serve():
        try:
            conn, _ = listener.accept()
            with server_context.wrap_socket(conn, server_side=True):
                pass
        except (OSError, ssl.SSLError):
            pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    client_context = ssl.create_default_context(cafile=str(cert))       # trusts the cert, checks the name
    session = SocketInterrupt()
    try:
        with pytest.raises(ssl.SSLCertVerificationError):
            session.open_tls("127.0.0.1", port, 5.0, client_context)
    finally:
        session.release()
        listener.close()
        thread.join(10.0)


# -- A whole successful session through the real TLS stream --------------------------------------------------

_MESSAGES = {
    1: ("Ada Lovelace <ada@example.com>", "=?utf-8?q?Caf=C3=A9_report?=", "Café report"),
    # An encoded display name decodes with a doubled space (side defect, Current_Plan.md §3); plain here.
    2: ("Bjorn <bjorn@example.com>", "Plain subject", "Plain subject"),
    3: ("Grace <grace@example.com>", "=?utf-8?q?Launch_=E2=9C=93?=", "Launch ✓"),
}
_PADDING = 70 * 1024          # each FETCH literal spans several 16 KB TLS records


def _make_cert(tmp_path, names: str):
    openssl = _openssl()
    if openssl is None:
        pytest.skip("openssl is not available to make a throwaway loopback certificate")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    made = subprocess.run([openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key),
                           "-out", str(cert), "-days", "2", "-subj", "/CN=localhost",
                           "-addext", f"subjectAltName={names}"], capture_output=True, timeout=60)
    if made.returncode != 0:
        pytest.skip("openssl could not make a certificate here")
    return cert, key


class _TlsImapServer:
    """Loopback TLS IMAP server: serves ``sessions`` connections one after another, then stops."""

    def __init__(self, cert, key, sessions: int) -> None:
        self._context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self._context.load_cert_chain(cert, key)
        self._listener = socket.create_server(("127.0.0.1", 0))
        self._listener.settimeout(20.0)
        self.port = self._listener.getsockname()[1]
        self.commands: list[str] = []
        self.errors: list[BaseException] = []
        self._thread = threading.Thread(target=self._serve, args=(sessions,), daemon=True)
        self._thread.start()

    def _serve(self, sessions: int) -> None:
        try:
            for _ in range(sessions):
                conn, _addr = self._listener.accept()
                conn.settimeout(20.0)
                with self._context.wrap_socket(conn, server_side=True) as tls_conn:
                    self._session(tls_conn)
        except BaseException as exc:  # surfaced by the test
            self.errors.append(exc)

    def _session(self, conn) -> None:
        reader = conn.makefile("rb")
        conn.sendall(b"* OK [CAPABILITY IMAP4rev1] loopback ready\r\n")
        while True:
            line = reader.readline()
            if not line:
                return
            tag, _, rest = line.rstrip(b"\r\n").partition(b" ")
            words = rest.split(b" ")
            command = words[0].upper()
            if command == b"UID":
                command = b"UID " + words[1].upper()
            self.commands.append(command.decode())
            if command == b"CAPABILITY":
                conn.sendall(b"* CAPABILITY IMAP4rev1\r\n" + tag + b" OK done\r\n")
            elif command == b"LOGIN":
                conn.sendall(tag + b" OK LOGIN completed\r\n")
            elif command in (b"SELECT", b"EXAMINE"):
                mode = b"READ-ONLY" if command == b"EXAMINE" else b"READ-WRITE"
                conn.sendall(b"* 3 EXISTS\r\n* FLAGS (\\Seen)\r\n" + tag + b" OK [" + mode + b"] done\r\n")
            elif command == b"UID SEARCH":
                conn.sendall(b"* SEARCH 1 2 3\r\n" + tag + b" OK SEARCH done\r\n")
            elif command == b"UID FETCH":
                uid = int(words[2])
                sender, subject, _decoded = _MESSAGES[uid]
                literal = (f"From: {sender}\r\nSubject: {subject}\r\nDate: Sat, 07 Nov 2026 10:0{uid}:00 +0000\r\n"
                           f"Message-ID: <m{uid}@example.com>\r\n\r\n").encode() + b"x" * _PADDING
                flags = b"(\\Seen)" if uid == 1 else b"()"
                head = (b"* %d FETCH (UID %d FLAGS %s BODY[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)] {%d}\r\n"
                        % (uid, uid, flags, len(literal)))
                conn.sendall(head + literal + b")\r\n" + tag + b" OK FETCH done\r\n")
            elif command == b"UID STORE":
                conn.sendall(b"* 2 FETCH (UID 2 FLAGS (\\Seen))\r\n" + tag + b" OK STORE done\r\n")
            elif command == b"LOGOUT":
                conn.sendall(b"* BYE logging out\r\n" + tag + b" OK LOGOUT done\r\n")
                try:
                    conn.unwrap()                  # TLS close_notify
                except (OSError, ssl.SSLError):
                    pass
                return
            else:
                conn.sendall(tag + b" BAD unexpected\r\n")

    def close(self) -> None:
        self._listener.close()
        self._thread.join(30.0)


def test_a_whole_session_runs_through_the_real_tls_stream(monkeypatch, tmp_path):
    """Greeting, LOGIN, EXAMINE, SEARCH, multi-record FETCH literals, STORE and LOGOUT/close_notify over real
    TLS with a verifying context that trusts only the test certificate."""
    from core.network import interruptible_socket

    cert, key = _make_cert(tmp_path, "IP:127.0.0.1,DNS:localhost")
    server = _TlsImapServer(cert, key, sessions=2)
    verifying = ssl.create_default_context(cafile=str(cert))
    assert verifying.check_hostname and verifying.verify_mode == ssl.CERT_REQUIRED
    monkeypatch.setattr(tls, "verified_client_context", lambda: verifying)
    monkeypatch.setattr(gmail_imap, "IMAP_HOST", "127.0.0.1")
    monkeypatch.setattr(gmail_imap, "IMAP_PORT", server.port)
    sessions: list = []

    class _Recorded(interruptible_socket.SocketInterrupt):
        def __init__(self):
            super().__init__()
            sessions.append(self)

    monkeypatch.setattr(gmail_imap, "SocketInterrupt", _Recorded)
    before = interruptible_socket.live_session_count()
    client = GmailImapClient("user@example.com", "app-password")
    try:
        emails = client.list_messages(max_results=3, should_cancel=lambda: False)
        assert [(e.subject, e.sender) for e in emails] == [
            (_MESSAGES[uid][2], sender) for uid, sender in
            ((3, "Grace <grace@example.com>"), (2, "Bjorn <bjorn@example.com>"),
             (1, "Ada Lovelace <ada@example.com>"))]
        assert [e.is_unread for e in emails] == [True, True, False]
        assert client.mark_as_read("2") is True
    finally:
        server.close()
    assert server.errors == [], server.errors
    assert "UID FETCH" in server.commands and "UID STORE" in server.commands
    assert server.commands.count("LOGOUT") == 2
    assert len(sessions) == 2
    for session in sessions:
        assert session._socket is not None and session._socket.fileno() == -1, "the session socket stayed open"
        assert session._wake_r is None and session._wake_w is None, "the wake pair stayed open"
    assert interruptible_socket.live_session_count() == before
