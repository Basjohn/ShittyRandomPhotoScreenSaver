"""No-network tests for pinned, redirect-vetted, worker-only feed-image transport."""
from __future__ import annotations

import socket
from types import SimpleNamespace

import pytest

from core.feeds.artwork import ArtworkCancelled
from core.feeds import artwork_transport as transport


class _Response:
    def __init__(self, code=200, body=b"image data", headers=None):
        self.status = code
        self.body = body
        self.headers = headers or {}

    def getheader(self, key, default=None):
        return self.headers.get(key, default)

    def read(self, size):
        part, self.body = self.body[:size], self.body[size:]
        return part


class _Connection:
    responses = []
    requests = []
    closes = 0

    def __init__(self, host, port, *, timeout, context=None):
        self.host, self.port, self.timeout, self.context = host, port, timeout, context
        self.sock = SimpleNamespace(settimeout=lambda _: None)

    def request(self, method, target, *, headers):
        # Exercise the exact pinned-socket callable installed by the real
        # transport.  A real HTTPSConnection retains self.host for TLS SNI.
        self._create_connection((self.host, self.port), self.timeout, None)
        self.requests.append((self.host, self.port, method, target, headers))

    def getresponse(self):
        return self.responses.pop(0)

    def close(self):
        type(self).closes += 1


@pytest.fixture
def network(monkeypatch):
    _Connection.responses = []
    _Connection.requests = []
    _Connection.closes = 0
    connections = []
    monkeypatch.setattr(transport.http.client, "HTTPSConnection", _Connection)
    monkeypatch.setattr(transport.http.client, "HTTPConnection", _Connection)
    monkeypatch.setattr(transport.ssl, "create_default_context", lambda: object())
    monkeypatch.setattr(transport.socket, "create_connection",
                        lambda addr, timeout, source_address: connections.append(addr))
    def resolve(host, port, *, type):
        assert type == socket.SOCK_STREAM
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", port))]
    return resolve, connections


def test_dns_is_pinned_for_tls_and_cache_fetch_does_not_delegate_redirects(network):
    resolve, connections = network
    _Connection.responses = [_Response(302, headers={"Location": "/new.png"}), _Response(body=b"raw bytes")]
    data = transport.fetch_artwork_bytes("https://cdn.example.test/photo.png?secret=never-logged",
                                         still_needed=lambda: True, resolve=resolve)
    assert data == b"raw bytes"
    assert connections == [("8.8.8.8", 443), ("8.8.8.8", 443)]
    assert [row[3] for row in _Connection.requests] == ["/photo.png?secret=never-logged", "/new.png"]
    assert all(row[4]["Accept-Encoding"] == "identity" for row in _Connection.requests)
    assert _Connection.closes == 2


def test_redirect_to_private_host_is_rejected_before_follow_up_socket(network):
    resolve, connections = network
    _Connection.responses = [_Response(302, headers={"Location": "http://127.0.0.1/admin"})]
    with pytest.raises(transport.ArtworkFetchError):
        transport.fetch_artwork_bytes("https://cdn.example.test/p.png", still_needed=lambda: True,
                                      resolve=resolve)
    assert connections == [("8.8.8.8", 443)]
    assert _Connection.closes == 1


def test_mixed_public_private_dns_is_rejected_without_connection(network):
    _, connections = network
    def mixed(host, port, *, type):
        return [(socket.AF_INET, type, 0, "", ("8.8.8.8", port)),
                (socket.AF_INET, type, 0, "", ("127.0.0.1", port))]
    with pytest.raises(transport.ArtworkFetchError):
        transport.fetch_artwork_bytes("https://cdn.example.test/p.png",
                                      still_needed=lambda: True, resolve=mixed)
    assert connections == []


def test_truncation_budget_and_cancel_never_accept_partial_image(network):
    resolve, _ = network
    _Connection.responses = [_Response(body=b"x" * 32)]
    with pytest.raises(transport.ArtworkFetchError):
        transport.fetch_artwork_bytes("https://cdn.example.test/a.png", still_needed=lambda: True,
                                      resolve=resolve, max_bytes=16)
    _Connection.responses = [_Response(body=b"complete")]
    calls = [0]
    def only_before_read():
        calls[0] += 1
        return calls[0] < 3
    with pytest.raises(ArtworkCancelled):
        transport.fetch_artwork_bytes("https://cdn.example.test/a.png", still_needed=only_before_read,
                                      resolve=resolve)


def test_source_rejects_nondefault_ports_and_unbounded_redirect_loops(network):
    resolve, connections = network
    with pytest.raises(transport.ArtworkFetchError):
        transport.fetch_artwork_bytes("https://cdn.example.test:80/a.png", still_needed=lambda: True,
                                      resolve=resolve)
    assert connections == []
    _Connection.responses = [_Response(302, headers={"Location": "/next"}) for _ in range(4)]
    with pytest.raises(transport.ArtworkFetchError):
        transport.fetch_artwork_bytes("https://cdn.example.test/a.png", still_needed=lambda: True,
                                      resolve=resolve)
    assert _Connection.closes == 4


def test_declared_payload_must_be_complete_and_compression_is_not_accepted(network):
    resolve, _ = network
    _Connection.responses = [_Response(body=b"short", headers={"Content-Length": "12"})]
    with pytest.raises(transport.ArtworkFetchError, match="truncated"):
        transport.fetch_artwork_bytes("https://cdn.example.test/a.png", still_needed=lambda: True,
                                      resolve=resolve)
    _Connection.responses = [_Response(body=b"compressed", headers={"Content-Encoding": "gzip"})]
    with pytest.raises(transport.ArtworkFetchError, match="compressed"):
        transport.fetch_artwork_bytes("https://cdn.example.test/a.png", still_needed=lambda: True,
                                      resolve=resolve)


def test_existing_worker_warmer_can_use_vetted_fetch_without_own_schedule(network, tmp_path):
    """Integration seam: one admitted source job, no independent image owner."""
    from io import BytesIO
    from PIL import Image
    from core.feeds.artwork import FeedArtworkCache
    from core.feeds.models import FeedImageCandidate, FeedItem

    resolve, connections = network
    buffer = BytesIO()
    Image.new("RGB", (30, 20), "white").save(buffer, "PNG")
    _Connection.responses = [_Response(body=buffer.getvalue())]
    image_url = "https://cdn.example.test/cover.png"
    item = FeedItem("entry", "Story", images=(FeedImageCandidate(image_url),))
    cache = FeedArtworkCache(tmp_path)
    alive = lambda: True
    batch = cache.warm(
        (item,),
        fetch_bytes=lambda image: transport.fetch_artwork_bytes(
            image, still_needed=alive, resolve=resolve),
        still_needed=alive,
    )
    assert batch.attempts == batch.newly_cached == 1
    assert batch.local_by_item["entry"].startswith("file:")
    assert connections == [("8.8.8.8", 443)]
    again = cache.warm((item,), fetch_bytes=lambda _: (_ for _ in ()).throw(
        AssertionError("cache hit must not construct a transport")), still_needed=alive)
    assert again.attempts == again.newly_cached == 0
    assert again.local_by_item == batch.local_by_item
