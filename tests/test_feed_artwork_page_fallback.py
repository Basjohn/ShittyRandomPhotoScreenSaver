"""Last-resort article share images and the no-churn failure memo (no Qt, no network)."""
from __future__ import annotations

from io import BytesIO

from PIL import Image

from core.feeds import artwork
from core.feeds.artwork import FeedArtworkCache
from core.feeds.artwork_transport import ArtworkFetchError
from core.feeds.models import FeedImageCandidate, FeedItem
from core.feeds.parser import article_share_image_url


def _item(identity: str, *images: str) -> FeedItem:
    return FeedItem(identity, identity, f"https://news.example.test/{identity}",
                    images=tuple(FeedImageCandidate(url) for url in images))


def _picture(color: str = "white") -> bytes:
    out = BytesIO()
    Image.new("RGB", (120, 80), color).save(out, format="PNG")
    return out.getvalue()


def _head(image: str) -> bytes:
    return (f'<html><head><meta property="og:image" content="{image}">'
            '</head><body><img src="/body.jpg"></body></html>').encode()


def test_share_image_prefers_open_graph_and_resolves_relative_urls() -> None:
    markup = ('<head><meta name="twitter:image" content="https://cdn.example.test/tw.jpg">'
              '<meta property="og:image" content="/art/og.jpg"></head><body>'
              '<meta property="og:image:secure_url" content="https://cdn.example.test/late.jpg">')
    assert article_share_image_url(markup, base_url="https://news.example.test/a") == \
        "https://news.example.test/art/og.jpg"
    assert article_share_image_url("<head><title>x</title></head>") == ""


def test_page_is_read_only_when_the_feed_offers_no_working_image(tmp_path) -> None:
    pages, images = [], []
    colors = iter(["red", "blue", "green"])

    def fetch(url):
        images.append(url)
        if url.endswith("broken.jpg"):
            raise ArtworkFetchError("artwork HTTP status 404")
        return _picture(next(colors))

    def page(url):
        pages.append(url)
        return _head(f"https://cdn.example.test/{url.rsplit('/', 1)[-1]}-share.jpg")

    rows = (_item("fed", "https://cdn.example.test/fed.jpg"),  # the feed's own image works
            _item("broken", "https://cdn.example.test/broken.jpg"),  # the feed's image fails
            _item("bare"))  # the feed offers nothing
    outcome = FeedArtworkCache(tmp_path).warm(rows, fetch_bytes=fetch, still_needed=lambda: True, fetch_page=page)

    assert set(outcome.local_by_item) == {"fed", "broken", "bare"}
    assert pages == ["https://news.example.test/broken", "https://news.example.test/bare"]


def test_a_second_refresh_reads_no_page_and_downloads_nothing(tmp_path) -> None:
    rows = (_item("bare"), _item("broken", "https://cdn.example.test/broken.jpg"))

    def failing(url):
        if url.endswith("broken.jpg"):
            raise ValueError("unusable image payload")
        return _picture("red" if "bare" in url else "blue")

    FeedArtworkCache(tmp_path).warm(rows, fetch_bytes=failing, still_needed=lambda: True,
                                    fetch_page=lambda url: _head(f"{url}-share.jpg"))
    pages, fetches = [], []
    outcome = FeedArtworkCache(tmp_path).warm(
        rows, fetch_bytes=lambda url: fetches.append(url) or _picture(), still_needed=lambda: True,
        fetch_page=lambda url: pages.append(url) or b"")

    assert set(outcome.local_by_item) == {"bare", "broken"}
    assert pages == [] and fetches == []  # the broken feed image is remembered, the pages too


def test_a_page_without_a_share_image_is_remembered(tmp_path) -> None:
    pages = []
    for _ in range(2):
        FeedArtworkCache(tmp_path).warm((_item("bare"),), fetch_bytes=lambda url: _picture(),
                                        still_needed=lambda: True,
                                        fetch_page=lambda url: pages.append(url) or b"<head></head>")
    assert pages == ["https://news.example.test/bare"]


def test_transient_failures_are_retried_after_an_hour_not_every_refresh(tmp_path, monkeypatch) -> None:
    now = [1_000_000.0]
    monkeypatch.setattr(artwork.time, "time", lambda: now[0])
    row = (_item("a", "https://cdn.example.test/a.jpg"),)
    calls = []

    def flaky(url):
        calls.append(url)
        raise ArtworkFetchError("artwork HTTP status 503", retry_seconds=artwork.TRANSIENT_RETRY_SECONDS)

    for _ in range(3):
        FeedArtworkCache(tmp_path).warm(row, fetch_bytes=flaky, still_needed=lambda: True)
    assert len(calls) == 1
    now[0] += artwork.TRANSIENT_RETRY_SECONDS + 1
    FeedArtworkCache(tmp_path).warm(row, fetch_bytes=flaky, still_needed=lambda: True)
    assert len(calls) == 2


def test_a_fetch_that_never_started_is_not_remembered(tmp_path) -> None:
    row = (_item("a", "https://cdn.example.test/a.jpg"),)

    def exhausted(url):
        raise ArtworkFetchError("shared artwork deadline exhausted", retry_seconds=None)

    FeedArtworkCache(tmp_path).warm(row, fetch_bytes=exhausted, still_needed=lambda: True)
    outcome = FeedArtworkCache(tmp_path).warm(row, fetch_bytes=lambda url: _picture(), still_needed=lambda: True)
    assert outcome.local_by_item.keys() == {"a"}


def test_one_generic_share_image_for_every_story_is_chrome_not_art(tmp_path) -> None:
    rows = (_item("a"), _item("b"))
    outcome = FeedArtworkCache(tmp_path).warm(
        rows, fetch_bytes=lambda url: _picture(), still_needed=lambda: True,
        fetch_page=lambda url: _head("https://cdn.example.test/site-logo.png"))
    assert outcome.local_by_item == {}


def test_huge_jpeg_is_decoded_at_reduced_scale() -> None:
    import os

    width, height = 9000, 6000  # 54 MP: over the pixel ceiling unless drafted
    noise = Image.frombytes("RGB", (width // 30, height // 30), os.urandom((width // 30) * (height // 30) * 3))
    buffer = BytesIO()
    noise.resize((width, height)).save(buffer, format="JPEG", quality=70)
    stored = FeedArtworkCache._normalize_image(buffer.getvalue())
    with Image.open(BytesIO(stored)) as image:
        assert max(image.size) <= artwork.MAX_STORED_EDGE
