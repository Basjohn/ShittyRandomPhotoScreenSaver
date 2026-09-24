"""A stalled DNS lookup can neither pin the shared IO lane nor hold process exit.

``socket.getaddrinfo`` ignores socket timeouts and cannot be interrupted. Before
the bounded resolver, one stalled lookup held an IO worker (the lane has four,
shared with Media, Weather, Reddit, Gmail and Steam) for the operating system's
whole retry schedule, blocked the engine's exit wait for its full 5 s and kept
the process alive afterwards (measured: 12.2 s for a 12 s stall), because the
interpreter joins thread-pool workers at exit. Everything here is headless.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from core.network import bounded_dns
from core.network.bounded_dns import DnsLookupError, resolve_bounded
from core.feeds.transport import FeedHttpTransport, FeedTransportError

REPO = Path(__file__).resolve().parents[1]


class _Stall:
    """A getaddrinfo that blocks until released, like an unanswered DNS server."""

    def __init__(self) -> None:
        self.release = threading.Event()
        self.calls: list[tuple[str, int]] = []

    def __call__(self, host, port, family=0, type=0):
        self.calls.append((host, port))
        self.release.wait(30.0)
        return [(2, 1, 6, "", ("192.0.2.1", port))]


def _drain(stall: _Stall) -> None:
    stall.release.set()
    deadline = time.monotonic() + 5.0
    while bounded_dns.lookups_in_progress() and time.monotonic() < deadline:
        time.sleep(0.01)


def test_a_stalled_lookup_returns_at_its_deadline_on_a_daemon_thread():
    stall = _Stall()
    started = time.monotonic()
    with pytest.raises(DnsLookupError, match="timed out"):
        resolve_bounded("feeds.example.test", 443, timeout=0.3, getaddrinfo=stall)
    assert time.monotonic() - started < 1.0
    lookups = [t for t in threading.enumerate() if t.name == "srpss-dns"]
    assert lookups and all(t.daemon for t in lookups)
    _drain(stall)
    assert bounded_dns.lookups_in_progress() == 0


def test_retirement_cancels_a_stalled_lookup_promptly():
    stall = _Stall()
    alive = [True]
    threading.Timer(0.1, lambda: alive.__setitem__(0, False)).start()
    started = time.monotonic()
    with pytest.raises(DnsLookupError, match="cancelled"):
        resolve_bounded("feeds.example.test", 443, timeout=10.0,
                        should_continue=lambda: alive[0], getaddrinfo=stall)
    assert time.monotonic() - started < 0.5
    _drain(stall)


def test_a_dns_outage_cannot_pile_up_lookup_threads():
    stall = _Stall()
    for _ in range(bounded_dns.MAX_LOOKUPS_IN_PROGRESS):
        with pytest.raises(DnsLookupError):
            resolve_bounded("feeds.example.test", 443, timeout=0.05, getaddrinfo=stall)
    started = time.monotonic()
    with pytest.raises(DnsLookupError, match="too many"):
        resolve_bounded("feeds.example.test", 443, timeout=5.0, getaddrinfo=stall)
    assert time.monotonic() - started < 0.1
    assert len(stall.calls) == bounded_dns.MAX_LOOKUPS_IN_PROGRESS
    _drain(stall)
    assert bounded_dns.lookups_in_progress() == 0


def test_answers_errors_and_literal_addresses_pass_through():
    answer = resolve_bounded("ok.example.test", 80, timeout=1.0,
                             getaddrinfo=lambda *a: [(2, 1, 6, "", ("192.0.2.9", 80))])
    assert answer[0][4] == ("192.0.2.9", 80)

    def missing(*_args):
        import socket
        raise socket.gaierror(11001, "host not found")

    import socket
    with pytest.raises(socket.gaierror):
        resolve_bounded("missing.example.test", 80, timeout=1.0, getaddrinfo=missing)
    before = threading.active_count()
    resolve_bounded("192.0.2.4", 80, timeout=1.0, getaddrinfo=lambda *a: [(2, 1, 6, "", ("192.0.2.4", 80))])
    assert threading.active_count() == before


class _Response:
    def __init__(self, status, *, url, location="", body=b"<rss/>"):
        self.status_code = status
        self.url = url
        self.headers = {"Location": location} if location else {}
        self._body = body
        self.closed = False

    def iter_content(self, chunk_size):
        yield self._body

    def close(self):
        self.closed = True


class _Session:
    def __init__(self, responses, proxies=None):
        self.responses = list(responses)
        self.requests: list[tuple[str, dict]] = []
        self.proxies = dict(proxies or {})
        self.trust_env = False

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.responses.pop(0)


def test_every_redirect_hop_is_resolved_under_the_bound_before_connecting():
    resolved: list[tuple[str, int]] = []
    session = _Session([
        _Response(301, url="http://a.example.test/feed", location="https://b.example.test/rss"),
        _Response(200, url="https://b.example.test/rss"),
    ])
    transport = FeedHttpTransport(
        session=session, resolve=lambda host, port, **_k: resolved.append((host, port)))
    result = transport.fetch("http://a.example.test/feed", etag='"v1"')
    assert resolved == [("a.example.test", 80), ("b.example.test", 443)]
    assert [url for url, _ in session.requests] == ["http://a.example.test/feed", "https://b.example.test/rss"]
    assert all(kwargs["allow_redirects"] is False for _, kwargs in session.requests)
    assert session.requests[1][1]["headers"]["If-None-Match"] == '"v1"'
    assert result.final_url == "https://b.example.test/rss"


def test_a_stalled_lookup_never_reaches_the_connection_and_is_offline_class():
    stall = _Stall()
    session = _Session([_Response(200, url="https://slow.example.test/rss")])
    transport = FeedHttpTransport(
        session=session, dns_timeout=0.2,
        resolve=lambda host, port, **k: resolve_bounded(host, port, getaddrinfo=stall, **k))
    started = time.monotonic()
    with pytest.raises(FeedTransportError) as caught:
        transport.fetch("https://slow.example.test/rss")
    assert time.monotonic() - started < 1.0
    assert caught.value.status_code is None  # offline-class: never starts feed discovery
    assert session.requests == []
    _drain(stall)


def test_a_proxy_is_resolved_instead_of_the_feed_host():
    resolved: list[tuple[str, int]] = []
    session = _Session([_Response(200, url="https://feed.example.test/rss")],
                       proxies={"https": "http://proxy.corp.test:8080"})
    FeedHttpTransport(session=session, resolve=lambda h, p, **_k: resolved.append((h, p))).fetch(
        "https://feed.example.test/rss")
    assert resolved == [("proxy.corp.test", 8080)]


@pytest.mark.parametrize("location", ["file:///C:/secret.xml", "javascript:alert(1)"])
def test_redirects_stay_http_and_bounded(location):
    session = _Session([_Response(302, url="https://a.example.test/rss", location=location)])
    transport = FeedHttpTransport(session=session, resolve=lambda *a, **k: None)
    with pytest.raises(FeedTransportError, match="redirect target rejected"):
        transport.fetch("https://a.example.test/rss")

    loop = _Session([_Response(302, url=f"https://a.example.test/{i}", location=f"/{i + 1}")
                     for i in range(10)])
    with pytest.raises(FeedTransportError, match="redirect limit"):
        FeedHttpTransport(session=loop, resolve=lambda *a, **k: None).fetch("https://a.example.test/0")


def test_stalled_feed_lookups_free_the_io_lane_and_never_hold_process_exit():
    """The production shape: the real ThreadManager IO lane and the real transport.

    Four feed fetches (the whole lane) stall in DNS. A fifth IO task (standing
    in for Media/Weather) must still run once the feeds retire, and the
    engine's exit path must neither wait out the stall nor linger after it.
    """
    script = textwrap.dedent(f"""
        import socket, sys, threading, time
        sys.path.insert(0, {str(REPO)!r})
        socket.getaddrinfo = lambda *a, **k: time.sleep(30.0)   # unanswered DNS
        from core.threading.manager import ThreadManager
        from core.resources.manager import ResourceManager
        from core.feeds.transport import FeedHttpTransport, FeedTransportError

        started = time.monotonic()
        manager = ThreadManager(resource_manager=ResourceManager())
        alive = [True]
        def feed():
            transport = FeedHttpTransport(should_continue=lambda: alive[0], dns_timeout=20.0)
            try:
                transport.fetch("https://feeds.example.test/rss")
            except FeedTransportError:
                return "retired"
            finally:
                transport.close()
        for _ in range(4):
            manager.submit_io_task(feed, category="feeds")
        time.sleep(0.4)
        alive[0] = False                     # the feed leases retire
        ran = threading.Event()
        retired_at = time.monotonic()
        manager.submit_io_task(ran.set, category="media")
        assert ran.wait(5.0), "IO lane still pinned by stalled feed lookups"
        print(f"lane_free_s={{time.monotonic() - retired_at:.2f}}", flush=True)
        t0 = time.monotonic()
        manager.shutdown(wait=True, timeout=5.0)  # the engine's exit call
        print(f"shutdown_s={{time.monotonic() - t0:.2f}}", flush=True)
        sys.exit(0)
    """)
    started = time.monotonic()
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
    lifetime = time.monotonic() - started
    assert result.returncode == 0, result.stderr[-2000:]
    facts = dict(line.split("=") for line in result.stdout.split() if "=" in line)
    assert float(facts["lane_free_s"]) < 1.0
    assert float(facts["shutdown_s"]) < 1.0
    # The 30 s lookups are still running on their daemon threads; exit does not wait.
    assert lifetime < 15.0, (lifetime, result.stdout)
