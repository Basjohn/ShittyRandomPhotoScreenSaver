"""Direct-socket TLS shares one verified context.

``urllib`` builds a system-trust context per connection unless it is handed
one; on Windows each build enumerates the certificate stores with the GIL held
(~22 ms, a 36 ms stall of another Python thread on the 2026-09-25 probe).
``imaplib.IMAP4_SSL`` without a context is unverified. These bars drive the
real ``urllib``/``http.client`` and the real Gmail connect path.
"""
from __future__ import annotations

import socket
import ssl
import threading
import urllib.error

import pytest

import core.network.tls as tls
from core.network.http import bounded_urlopen


def test_one_verified_context_is_built_once_for_all_threads(monkeypatch):
    monkeypatch.setattr(tls, "_CONTEXT", None)
    builds: list[int] = []
    real = ssl.create_default_context
    monkeypatch.setattr(tls.ssl, "create_default_context", lambda: builds.append(1) or real())
    results: list[ssl.SSLContext] = []
    threads = [
        threading.Thread(target=lambda: results.append(tls.verified_client_context()))
        for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert builds == [1]
    assert len({id(context) for context in results}) == 1
    assert results[0].verify_mode == ssl.CERT_REQUIRED
    assert results[0].check_hostname is True


def test_urllib_requests_load_no_trust_store_per_connection(monkeypatch):
    tls.verified_client_context()  # the process's one build
    loads: list[int] = []
    real_load = ssl.SSLContext.load_default_certs

    def counting_load(self, *args, **kwargs):
        loads.append(1)
        return real_load(self, *args, **kwargs)

    monkeypatch.setattr(ssl.SSLContext, "load_default_certs", counting_load)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    monkeypatch.setenv("NO_PROXY", "*")
    with socket.socket() as probe:  # a closed local port: refused before any handshake
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    for _ in range(3):
        with pytest.raises(urllib.error.URLError):
            bounded_urlopen(f"https://127.0.0.1:{port}/", 2.0)

    assert loads == []


def test_gmail_imap_connects_with_the_verified_context(monkeypatch):
    import core.gmail.gmail_imap as gmail_imap
    import core.network.bounded_dns as bounded_dns

    seen: dict[str, object] = {}

    class _Stop(Exception):
        pass

    def fake_imap(host, port, **kwargs):
        seen.update(kwargs)
        raise _Stop()

    monkeypatch.setattr(bounded_dns, "resolve_bounded", lambda *_a, **_k: [])
    monkeypatch.setattr(gmail_imap.imaplib, "IMAP4_SSL", fake_imap)

    with pytest.raises(_Stop):
        gmail_imap.GmailImapClient("user@example.com", "app-password")._connect()

    context = seen.get("ssl_context")
    assert context is tls.verified_client_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
