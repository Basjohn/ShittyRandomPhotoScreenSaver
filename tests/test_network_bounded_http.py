"""Shared bounded-DNS HTTP entry points (core/network/http.py), with real libraries.

A local HTTP server exercises real ``requests``/``urllib`` redirect handling;
the resolver is observed, not faked, except where a stall is the point. The
process exit fence is one-way, so it is only exercised in a subprocess.
Everything is headless.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
import urllib.error
import urllib.request

import pytest
import requests

import core.network.http as network_http
from core.network import bounded_dns
from core.network.http import (bounded_request, bounded_urlopen,
                               requests_connection_host, urllib_connection_host)

REPO = Path(__file__).resolve().parents[1]


class _Handler(BaseHTTPRequestHandler):
    seen: list[tuple[str, str]] = []

    def _reply(self) -> None:
        _Handler.seen.append((self.command, self.path))
        port = self.server.server_address[1]
        if self.path.startswith("/start"):
            self.send_response(303 if self.command == "POST" else 302)
            self.send_header("Location", f"http://localhost:{port}/final")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = b"final"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = _reply

    def log_message(self, *_args) -> None:
        pass


class _DualStackServer(ThreadingHTTPServer):
    """Answers on ::1 and 127.0.0.1, so ``localhost`` connects at once on Windows."""

    address_family = socket.AF_INET6

    def server_bind(self) -> None:
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


@pytest.fixture()
def server():
    httpd = _DualStackServer(("::", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    _Handler.seen = []
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture()
def resolved(monkeypatch):
    hosts: list[tuple[str, int]] = []
    real = network_http.resolve_bounded

    def record(host, port, **kwargs):
        hosts.append((host, port))
        return real(host, port, **kwargs)

    monkeypatch.setattr(network_http, "resolve_bounded", record)
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.setenv("NO_PROXY", "*")
    return hosts


def test_requests_redirects_resolve_every_hop_with_requests_semantics(server, resolved):
    response = bounded_request("POST", f"http://127.0.0.1:{server}/start", data=b"x", timeout=5)
    assert response.status_code == 200 and response.text == "final"
    assert resolved == [("127.0.0.1", server), ("localhost", server)]
    # 303 after POST becomes GET, exactly as requests itself would do.
    assert _Handler.seen == [("POST", "/start"), ("GET", "/final")]

    unfollowed = bounded_request("GET", f"http://127.0.0.1:{server}/start", allow_redirects=False, timeout=5)
    assert unfollowed.status_code == 302


def test_urllib_redirects_resolve_every_hop(server, resolved):
    with bounded_urlopen(urllib.request.Request(f"http://127.0.0.1:{server}/start"), 5.0) as response:
        assert response.read() == b"final"
    assert resolved == [("127.0.0.1", server), ("localhost", server)]


class _Stall:
    def __init__(self) -> None:
        self.release = threading.Event()

    def __call__(self, *_args, **_kwargs):
        self.release.wait(30.0)
        return []


def test_a_stalled_lookup_is_each_librarys_own_connection_error(monkeypatch):
    stall = _Stall()
    monkeypatch.setattr(bounded_dns.socket, "getaddrinfo", stall)
    started = time.monotonic()
    with pytest.raises(requests.ConnectionError):
        bounded_request("GET", "https://stalled.example.test/", dns_timeout=0.2, timeout=5)
    with pytest.raises(urllib.error.URLError):
        bounded_urlopen("https://stalled.example.test/", 5.0, dns_timeout=0.2)
    alive = [True]
    threading.Timer(0.1, lambda: alive.__setitem__(0, False)).start()
    with pytest.raises(requests.ConnectionError):
        bounded_request("GET", "https://stalled.example.test/", dns_timeout=10.0,
                        should_continue=lambda: alive[0], timeout=5)
    assert time.monotonic() - started < 2.0
    stall.release.set()


def test_the_proxy_host_is_resolved_when_a_proxy_applies(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.corp.test:8080")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    assert requests_connection_host("https://api.example.test/v1") == ("proxy.corp.test", 8080)
    assert urllib_connection_host("https://api.example.test/v1") == ("proxy.corp.test", 8080)
    session = requests.Session()
    session.trust_env = False
    session.proxies = {"https": "http://other.corp.test:3128"}
    assert requests_connection_host("https://api.example.test/v1", session=session) == ("other.corp.test", 3128)
    session.close()


def test_the_exit_fence_releases_lookups_in_progress_at_once():
    script = textwrap.dedent(f"""
        import json, socket, sys, threading, time
        sys.path.insert(0, {str(REPO)!r})
        socket.getaddrinfo = lambda *a, **k: time.sleep(30.0)
        from core.network.bounded_dns import DnsLookupError, close_network_admission, resolve_bounded
        outcome = {{}}
        def lookup():
            started = time.monotonic()
            try:
                resolve_bounded("stalled.example.test", 443, timeout=20.0)
            except DnsLookupError as exc:
                outcome["error"] = str(exc)
            outcome["seconds"] = time.monotonic() - started
        worker = threading.Thread(target=lookup)
        worker.start()
        time.sleep(0.3)
        close_network_admission()
        worker.join(5.0)
        try:
            resolve_bounded("next.example.test", 443, timeout=20.0)
        except DnsLookupError as exc:
            outcome["refused"] = str(exc)
        print(json.dumps(outcome), flush=True)
    """)
    started = time.monotonic()
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr[-2000:]
    outcome = json.loads(result.stdout.strip())
    assert "exit" in outcome["error"] and outcome["seconds"] < 1.0
    assert "exit" in outcome["refused"]
    assert time.monotonic() - started < 15.0
