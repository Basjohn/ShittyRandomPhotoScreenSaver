"""Wallpaper image fetch: vetted stream, real pixel size read early, no partial files.

No network: ``http.client`` connections and DNS are faked exactly like the
FEEDS artwork transport tests, so the pinned-address path runs for real.
"""
from __future__ import annotations

from io import BytesIO
import socket
from types import SimpleNamespace

import pytest
from PIL import Image

from core.feeds import artwork_transport as transport
from core.feeds.artwork import ArtworkCancelled
from core.feeds.artwork_transport import ArtworkFetchError
from sources.rss.image_fetch import WallpaperRejected, fetch_wallpaper, fills_displays

pytestmark = pytest.mark.usefixtures("qt_app")
REQUIRED = (3840, 2160)   # the operator's 2560x1440 + 3840x2160 pair, fill mode


def _image(size, fmt="JPEG", padding=0) -> bytes:
    out = BytesIO()
    Image.new("RGB", size, "navy").save(out, format=fmt)
    return out.getvalue() + b"\0" * padding


class _Response:
    def __init__(self, body: bytes, status=200, headers=None):
        self.status = status
        self.body = body
        self.served = 0
        self.headers = headers or {}

    def getheader(self, key, default=None):
        return self.headers.get(key, default)

    def read(self, size):
        part, self.body = self.body[:size], self.body[size:]
        self.served += len(part)
        return part


class _Connection:
    responses: list = []

    def __init__(self, host, port, *, timeout, context=None):
        self.host, self.port = host, port
        self.sock = SimpleNamespace(settimeout=lambda _: None)

    def request(self, method, target, *, headers):
        self.headers = headers

    def getresponse(self):
        return self.responses.pop(0)

    def close(self):
        pass


@pytest.fixture
def network(monkeypatch):
    _Connection.responses = []
    monkeypatch.setattr(transport.http.client, "HTTPSConnection", _Connection)
    monkeypatch.setattr(transport.http.client, "HTTPConnection", _Connection)
    monkeypatch.setattr(transport.ssl, "create_default_context", lambda: object())

    def resolve(host, port, *, type):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", port))]

    return resolve


def _fetch(tmp_path, resolve, **kwargs):
    return fetch_wallpaper("https://images.example.test/w.jpg", tmp_path, file_stem="abc123",
                           still_needed=kwargs.pop("still_needed", lambda: True),
                           required=kwargs.pop("required", REQUIRED), resolve=resolve, **kwargs)


def test_an_image_that_fills_every_display_is_kept_under_its_real_format(tmp_path, network):
    # Larger than the displays is always fine, whatever the aspect.
    _Connection.responses = [_Response(_image((4000, 5000), "PNG"))]
    result = _fetch(tmp_path, network)
    assert (result.width, result.height) == (4000, 5000)
    assert result.path == tmp_path / "abc123.png"   # detected PNG, not the URL's .jpg
    assert [p.name for p in tmp_path.iterdir()] == ["abc123.png"]


def test_a_too_small_image_is_rejected_from_its_header_without_downloading_the_rest(tmp_path, network):
    response = _Response(_image((1024, 683), padding=6 * 1024 * 1024))
    _Connection.responses = [response]
    with pytest.raises(WallpaperRejected) as caught:
        _fetch(tmp_path, network)
    assert caught.value.size == (1024, 683)
    assert response.served <= 64 * 1024   # the first header checkpoint, not 6 MB
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("body, reason", [
    (b"<!doctype html><html><body>blocked</body></html>" * 100, "not a readable image"),
    (_image((4000, 3000), "GIF"), "unsupported format"),
])
def test_non_images_and_unsupported_formats_leave_nothing_behind(tmp_path, network, body, reason):
    _Connection.responses = [_Response(body)]
    with pytest.raises(WallpaperRejected, match=reason):
        _fetch(tmp_path, network)
    assert list(tmp_path.iterdir()) == []


def test_byte_cap_and_cancellation_leave_no_partial_file(tmp_path, network):
    _Connection.responses = [_Response(_image((4000, 3000), padding=512 * 1024))]
    with pytest.raises(ArtworkFetchError, match="exceeds bound"):
        _fetch(tmp_path, network, max_bytes=256 * 1024)
    assert list(tmp_path.iterdir()) == []

    reads = [0]

    def alive():
        reads[0] += 1
        return reads[0] < 8

    _Connection.responses = [_Response(_image((4000, 3000), padding=4 * 1024 * 1024))]
    with pytest.raises(ArtworkCancelled):
        _fetch(tmp_path, network, still_needed=alive)
    assert list(tmp_path.iterdir()) == []


def test_a_far_larger_image_is_stored_right_sized_once(tmp_path, network):
    # Requirement 400x300: a 1600x1600 source is 4x more than a 1.25x-headroom cover needs.
    _Connection.responses = [_Response(_image((1600, 1600)))]
    result = _fetch(tmp_path, network, required=(400, 300))
    assert (result.width, result.height) == (500, 500)   # still covers 400x300 with headroom
    assert result.path.suffix == ".jpg"
    from PIL import Image
    with Image.open(result.path) as stored:
        assert stored.size == (500, 500)

    # A panorama limited by its height is left exactly as it is.
    _Connection.responses = [_Response(_image((4000, 380), "PNG"))]
    kept = fetch_wallpaper("https://images.example.test/p.png", tmp_path, file_stem="pano",
                           still_needed=lambda: True, required=(400, 300), resolve=network)
    assert (kept.width, kept.height, kept.path.suffix) == (4000, 380, ".png")


def test_fill_rule_is_every_display_without_upscaling():
    assert fills_displays(3840, 2160, REQUIRED) and fills_displays(8999, 9011, REQUIRED)
    assert not fills_displays(1920, 1080, REQUIRED)
    assert not fills_displays(5000, 1848, REQUIRED)   # wide panorama short of 4K height
    assert fills_displays(1920, 1080, (1920, 1080))    # a 1080p setup admits Bing
