from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.feeds.cache import FeedCacheStore
from core.feeds.config import CUSTOM_FEED_WIDGET_IDS, CustomFeedConfig
from core.feeds.models import FeedCacheRecord, FeedHealth, FeedSourceSpec
from core.feeds.normalization import endpoint_fingerprint, redacted_url_for_log
from core.feeds.parser import FeedParseError, parse_feed_bytes
from core.feeds.source import FeedSource
from core.feeds.transport import FeedHttpResponse, FeedHttpTransport, FeedTransportError


RSS = b'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
 <channel><title>Goblin News</title><link>https://example.test/</link>
  <item><guid>plain-1</guid><title>Plain story survives</title>
   <link>https://example.test/plain</link><description><![CDATA[<p>No picture here.</p>]]></description>
   <pubDate>Sun, 20 Sep 2026 12:00:00 GMT</pubDate></item>
  <item><guid>image-2</guid><title>Picture story</title>
   <link>https://example.test/image</link><media:thumbnail url="https://cdn.example.test/thumb.jpg" width="640" height="360"/>
   <description><![CDATA[<img src="https://cdn.example.test/body.jpg"><b>With image</b>]]></description></item>
 </channel>
</rss>'''

ATOM = b'''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom Works</title>
 <link href="https://atom.example/"/><entry><id>tag:atom.example,2026:1</id>
 <title>Atom Item</title><link href="https://atom.example/item"/>
 <updated>2026-09-20T12:30:00Z</updated><summary>Atom summary</summary></entry></feed>'''

MAGNET = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Tracker</title>
 <item><guid>x</guid><title>Release.Name.2026.1080p</title>
 <link>magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&amp;dn=Release.Name</link></item>
</channel></rss>'''

RELATIVE = b'''<?xml version="1.0"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel><title>Relative</title><link>/home</link>
 <item><guid>relative</guid><title>Relative Item</title><link>/story/1</link>
 <media:thumbnail url="/media/hero.jpg"/></item>
</channel></rss>'''

MAGNET_DN = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Tracker</title>
 <item><guid>derived</guid><link>magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&amp;dn=Release.Name.2026.1080p</link></item>
</channel></rss>'''


EMPTY_RSS = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Empty</title></channel></rss>'''


def test_feed_parser_keeps_valid_items_without_images_and_reports_coverage():
    document = parse_feed_bytes(RSS, source_url="https://example.test/feed")
    assert len(document.items) == 2
    assert document.items[0].title == "Plain story survives"
    assert document.items[0].images == ()
    assert document.items[1].images[0].url == "https://cdn.example.test/thumb.jpg"
    assert document.image_item_count == 1
    assert document.image_coverage == pytest.approx(0.5)


def test_feed_parser_handles_atom_from_bytes_without_network():
    document = parse_feed_bytes(ATOM, source_url="https://atom.example/feed")
    assert document.format.startswith("atom")
    assert document.items[0].action_url == "https://atom.example/item"
    assert document.items[0].published_at is not None


def test_feed_parser_preserves_magnet_as_action_but_not_media():
    document = parse_feed_bytes(MAGNET, source_url="https://tracker.example/rss")
    item = document.items[0]
    assert item.action_url.startswith("magnet:?xt=urn:btih:")
    assert item.images == ()


def test_feed_parser_resolves_relative_links_and_media_against_final_feed_url():
    document = parse_feed_bytes(RELATIVE, source_url="https://example.test/feeds/current.xml")
    assert document.home_url == "https://example.test/home"
    assert document.items[0].action_url == "https://example.test/story/1"
    assert document.items[0].images[0].url == "https://example.test/media/hero.jpg"


def test_feed_parser_derives_readable_title_from_magnet_display_name_when_missing():
    document = parse_feed_bytes(MAGNET_DN, source_url="https://tracker.example/rss")
    assert document.items[0].title == "Release Name 2026 1080p"


def test_feed_parser_rejects_empty_or_non_feed_payload():
    with pytest.raises(FeedParseError):
        parse_feed_bytes(b"not an rss document", source_url="https://example.test/feed")


def test_redacted_url_never_logs_private_query_tokens():
    redacted = redacted_url_for_log("https://example.test/feed?token=supersecret&x=1")
    assert redacted == "https://example.test/feed"
    assert "supersecret" not in redacted


class _FakeResponse:
    def __init__(self, *, status=200, chunks=(RSS,), headers=None, url="https://example.test/final"):
        self.status_code = status
        self._chunks = tuple(chunks)
        self.headers = dict(headers or {})
        self.url = url
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests import HTTPError
            raise HTTPError(str(self.status_code))

    def iter_content(self, chunk_size):
        yield from self._chunks

    def close(self):
        self.closed = True


class _FakeSession:
    def __init__(self, response):
        self.response = response
        self.max_redirects = None
        self.kwargs = None

    def get(self, url, **kwargs):
        self.kwargs = {"url": url, **kwargs}
        return self.response


def test_transport_sends_conditional_headers_and_bounds_decompressed_bytes():
    response = _FakeResponse(headers={"ETag": '"abc"'})
    session = _FakeSession(response)
    transport = FeedHttpTransport(session=session, max_bytes=64 * 1024)
    result = transport.fetch("https://example.test/feed", etag='"old"', last_modified="date")
    assert result.payload == RSS
    assert session.kwargs["headers"]["If-None-Match"] == '"old"'
    assert session.kwargs["headers"]["If-Modified-Since"] == "date"
    assert response.closed is True

    too_large = _FakeResponse(chunks=(b"x" * 40000, b"y" * 40000))
    with pytest.raises(FeedTransportError):
        FeedHttpTransport(session=_FakeSession(too_large), max_bytes=64 * 1024).fetch("https://example.test/feed")
    assert too_large.closed is True


def test_transport_304_never_requires_or_parses_a_body():
    response = _FakeResponse(status=304, chunks=(), headers={"ETag": '"new"'})
    result = FeedHttpTransport(session=_FakeSession(response)).fetch("https://example.test/feed", etag='"old"')
    assert result.status == "not_modified"
    assert result.payload == b""
    assert result.etag == '"new"'


def test_cache_round_trip_and_corruption_quarantine(tmp_path: Path):
    store = FeedCacheStore(tmp_path)
    document = parse_feed_bytes(RSS, source_url="https://example.test/feed")
    from core.feeds.models import FeedSnapshot
    record = FeedCacheRecord(
        source_id="source",
        endpoint_fingerprint=endpoint_fingerprint("https://example.test/feed"),
        snapshot=FeedSnapshot(document=document, fetched_at=123.0),
        health=FeedHealth(last_checked_at=123.0, last_success_at=123.0),
        etag='"abc"',
    )
    path = store.write("source", record)
    assert store.read("source") == record
    path.write_text("{broken", encoding="utf-8")
    assert store.read("source") is None
    assert path.with_suffix(".json.corrupt").exists()


class _SequenceTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def fetch(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _ok(payload=RSS, etag='"one"'):
    return FeedHttpResponse("ok", payload, "https://example.test/feed", etag=etag)


def test_source_failure_never_replaces_last_good_snapshot(tmp_path: Path):
    clock = iter((1000.0, 1100.0))
    transport = _SequenceTransport(_ok(), FeedTransportError("offline"))
    spec = FeedSourceSpec("source", "https://example.test/feed", "source")
    source = FeedSource(spec, transport=transport, cache=FeedCacheStore(tmp_path), now=lambda: next(clock))
    first = source.refresh()
    assert first.status == "available"
    second = source.refresh(force=True)
    assert second.status == "stale_cache"
    assert second.snapshot == first.snapshot
    retained = FeedCacheStore(tmp_path).read("source")
    assert retained is not None and retained.snapshot == first.snapshot
    assert retained.health.consecutive_failures == 1


def test_source_304_retains_exact_snapshot_and_refreshes_health(tmp_path: Path):
    clock = iter((1000.0, 2000.0))
    transport = _SequenceTransport(
        _ok(),
        FeedHttpResponse("not_modified", b"", "https://example.test/feed", etag='"one"'),
    )
    source = FeedSource(
        FeedSourceSpec("source", "https://example.test/feed", "source"),
        transport=transport, cache=FeedCacheStore(tmp_path), now=lambda: next(clock),
    )
    first = source.refresh()
    second = source.refresh()
    assert second.status == "not_modified"
    assert second.snapshot == first.snapshot
    assert second.changed is False
    assert transport.calls[1][1]["etag"] == '"one"'


def test_source_persistent_backoff_prevents_retry_churn(tmp_path: Path):
    transport = _SequenceTransport(FeedTransportError("offline"))
    source = FeedSource(
        FeedSourceSpec("source", "https://example.test/feed", "source"),
        transport=transport, cache=FeedCacheStore(tmp_path), now=lambda: 1000.0,
    )
    first = source.refresh()
    assert first.status == "unavailable"
    second = source.refresh()
    assert second.status == "unavailable"
    assert second.failure == "FeedTransportError"
    assert len(transport.calls) == 1


def test_custom_slots_are_bounded_and_url_identity_is_cache_isolated():
    assert CUSTOM_FEED_WIDGET_IDS == (
        "feeds_custom_1", "feeds_custom_2", "feeds_custom_3", "feeds_custom_4"
    )
    a = CustomFeedConfig.from_mapping("feeds_custom_1", {"feed_url": "https://a.example/rss", "name": "Nyaa"})
    b = CustomFeedConfig.from_mapping("feeds_custom_1", {"feed_url": "https://b.example/rss", "name": "Nyaa"})
    assert a.configured and b.configured
    assert a.source_spec().cache_key != b.source_spec().cache_key
    assert a.source_spec().source_id != b.source_spec().source_id
    assert a.name == "Nyaa"


def test_builtin_provider_can_preserve_last_good_across_official_endpoint_migration(tmp_path: Path):
    store = FeedCacheStore(tmp_path)
    clock = iter((1000.0, 1100.0))
    first = FeedSource(
        FeedSourceSpec("provider:cbs_world", "https://old.example/rss", "provider_cbs_world", allow_endpoint_migration=True),
        transport=_SequenceTransport(_ok()), cache=store, now=lambda: next(clock),
    ).refresh()
    assert first.snapshot is not None

    failing = _SequenceTransport(FeedTransportError("new endpoint temporarily down"))
    second = FeedSource(
        FeedSourceSpec("provider:cbs_world", "https://new.example/rss", "provider_cbs_world", allow_endpoint_migration=True),
        transport=failing, cache=store, now=lambda: next(clock),
    ).refresh(force=True)
    assert second.status == "stale_cache"
    assert second.snapshot == first.snapshot
    # Old ETag is never sent to a different official endpoint.
    assert failing.calls[0][1]["etag"] == ""
    assert failing.calls[0][1]["last_modified"] == ""


class _FailingCacheStore(FeedCacheStore):
    def write(self, cache_key, record):
        raise OSError("disk unavailable")


def test_successful_feed_generation_survives_cache_write_failure(tmp_path: Path):
    source = FeedSource(
        FeedSourceSpec("source", "https://example.test/feed", "source"),
        transport=_SequenceTransport(_ok()), cache=_FailingCacheStore(tmp_path), now=lambda: 1000.0,
    )
    result = source.refresh()
    assert result.status == "available"
    assert result.snapshot is not None
    assert result.snapshot.document.items[0].title == "Plain story survives"


def test_custom_config_boolean_strings_do_not_turn_false_into_true():
    config = CustomFeedConfig.from_mapping(
        "feeds_custom_1",
        {"enabled": "false", "show_images": "false", "feed_url": "https://example.test/rss"},
    )
    assert config.enabled is False
    assert config.show_images is False


def test_empty_success_response_never_replaces_last_good_snapshot(tmp_path: Path):
    clock = iter((1000.0, 1100.0))
    transport = _SequenceTransport(_ok(), _ok(payload=EMPTY_RSS, etag='"two"'))
    spec = FeedSourceSpec("source", "https://example.test/feed", "source")
    source = FeedSource(spec, transport=transport, cache=FeedCacheStore(tmp_path), now=lambda: next(clock))
    first = source.refresh()
    assert first.status == "available"
    second = source.refresh(force=True)
    assert second.status == "stale_cache"
    assert second.snapshot == first.snapshot
    retained = FeedCacheStore(tmp_path).read("source")
    assert retained is not None and retained.snapshot == first.snapshot
    assert retained.health.consecutive_failures == 1


def test_custom_slots_sharing_one_endpoint_share_acquisition_identity():
    first = CustomFeedConfig.from_mapping(
        "feeds_custom_1", {"feed_url": "https://same.example/rss", "name": "One"}
    ).source_spec()
    second = CustomFeedConfig.from_mapping(
        "feeds_custom_2", {"feed_url": "https://same.example/rss", "name": "Two"}
    ).source_spec()
    assert first.cache_key == second.cache_key
    assert first.source_id == second.source_id
    assert first.url == second.url
    assert first.display_name != second.display_name
