"""FEEDS root-cause guards: parse isolation and durable warm-start artwork.

These tests are ordinary product contracts.  They do not depend on Diagnostic
profiles, frozen builds, long soaks, timers or external network access.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from core.feeds.artwork import FeedArtworkCache
from core.feeds.cache import FeedCacheStore
from core.feeds.models import (
    FeedCacheRecord,
    FeedDocument,
    FeedHealth,
    FeedImageCandidate,
    FeedItem,
    FeedRefreshResult,
    FeedSnapshot,
    FeedSourceSpec,
)
from core.feeds.normalization import endpoint_fingerprint
from core.feeds.source import FeedSource
from core.feeds.transport import FeedHttpResponse


RSS = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Isolated</title>
<item><guid>one</guid><title>One</title><link>https://example.test/one</link></item>
</channel></rss>'''


def _document(*, with_image: bool = True) -> FeedDocument:
    images = (
        FeedImageCandidate("https://cdn.example.test/one.png", relation="content"),
    ) if with_image else ()
    return FeedDocument(
        title="Durable Feed",
        home_url="https://example.test/",
        format="rss",
        items=(FeedItem(
            "one", "One", "https://example.test/one", images=images,
        ),),
    )


def _png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (32, 20), "white").save(output, format="PNG")
    return output.getvalue()


def _record(document: FeedDocument, *, fetched_at: float = 1000.0, artwork=()) -> FeedCacheRecord:
    return FeedCacheRecord(
        source_id="source",
        endpoint_fingerprint=endpoint_fingerprint("https://example.test/feed"),
        snapshot=FeedSnapshot(document, fetched_at=fetched_at),
        health=FeedHealth(last_checked_at=fetched_at, last_success_at=fetched_at),
        artwork_files_by_item=tuple(artwork),
    )


def _seed_artwork(cache_root: Path, document: FeedDocument):
    artwork = FeedArtworkCache(cache_root / "artwork")
    warm = artwork.warm(
        document.items,
        fetch_bytes=lambda _url: _png(),
        still_needed=lambda: True,
    )
    assert warm.local_by_item.keys() == {"one"}
    assert warm.files_by_item.keys() == {"one"}
    return warm


def test_warm_start_restores_cached_rows_with_cached_artwork_before_network(tmp_path: Path):
    """First cache publication already contains yesterday's validated image."""
    cache_root = tmp_path / "feeds"
    store = FeedCacheStore(cache_root)
    document = _document()
    warm = _seed_artwork(cache_root, document)
    store.write("source", _record(document, artwork=warm.files_by_item.items()))

    constructed = []
    source = FeedSource(
        FeedSourceSpec("source", "https://example.test/feed", "source"),
        cache=store,
        transport_factory=lambda: constructed.append(True) or (_ for _ in ()).throw(
            AssertionError("cache-first warm start must not construct network transport")
        ),
    )

    result = source.load_cached()
    assert result.snapshot is not None
    assert dict(result.local_artwork_by_item) == dict(warm.local_by_item)
    assert dict(result.artwork_files_by_item) == dict(warm.files_by_item)
    assert constructed == []


def test_missing_cached_artwork_drops_only_image_not_last_good_feed(tmp_path: Path):
    cache_root = tmp_path / "feeds"
    store = FeedCacheStore(cache_root)
    document = _document()
    warm = _seed_artwork(cache_root, document)
    store.write("source", _record(document, artwork=warm.files_by_item.items()))
    for path in (cache_root / "artwork").glob("*.png"):
        path.unlink()

    result = FeedSource(
        FeedSourceSpec("source", "https://example.test/feed", "source"),
        cache=store,
    ).load_cached()

    assert result.snapshot is not None
    assert result.snapshot.document == document
    assert result.local_artwork_by_item == ()
    assert result.artwork_files_by_item == ()
    # A missing optional image is not cache corruption.
    assert store.read("source") is not None
    assert not store.path_for("source").with_suffix(".json.corrupt").exists()


def test_artwork_followon_persists_binding_for_next_process_lifetime(tmp_path: Path):
    cache_root = tmp_path / "feeds"
    store = FeedCacheStore(cache_root)
    document = _document()
    record = _record(document)
    store.write("source", record)
    warm = _seed_artwork(cache_root, document)

    source = FeedSource(
        FeedSourceSpec("source", "https://example.test/feed", "source"),
        cache=store,
    )
    accepted = FeedRefreshResult(
        "available", record.snapshot, record.health,
        local_artwork_by_item=tuple(warm.local_by_item.items()),
        artwork_files_by_item=tuple(warm.files_by_item.items()),
    )
    persisted = source.persist_artwork_bindings(accepted)
    assert dict(persisted.local_artwork_by_item) == dict(warm.local_by_item)

    # New source object simulates the next application lifetime.
    restored = FeedSource(
        FeedSourceSpec("source", "https://example.test/feed", "source"),
        cache=FeedCacheStore(cache_root),
    ).load_cached()
    assert dict(restored.local_artwork_by_item) == dict(warm.local_by_item)
    assert dict(restored.artwork_files_by_item) == dict(warm.files_by_item)


def test_feed_source_uses_injected_document_parser_for_remote_feed(tmp_path: Path):
    document = _document(with_image=False)
    calls = []

    class Transport:
        def fetch(self, _url, **_kwargs):
            return FeedHttpResponse(
                "ok", RSS, "https://example.test/feed",
                content_type="application/rss+xml",
            )

    def parser(payload: bytes, source_url: str, max_items: int):
        calls.append((payload, source_url, max_items))
        return document

    source = FeedSource(
        FeedSourceSpec("source", "https://example.test/feed", "source", max_items=12),
        transport=Transport(),
        cache=FeedCacheStore(tmp_path),
        now=lambda: 1000.0,
        document_parser=parser,
    )
    result = source.refresh(force=True)
    assert result.snapshot is not None
    assert result.snapshot.document == document
    assert len(calls) == 1
    assert calls[0][0] == RSS
    assert calls[0][2] == 12



def test_feed_source_prefers_isolated_response_examiner_for_remote_documents(tmp_path: Path):
    document = _document(with_image=False)
    calls = []

    class Transport:
        def fetch(self, _url, **_kwargs):
            return FeedHttpResponse(
                "ok", RSS, "https://example.test/feed",
                content_type="application/rss+xml",
            )

    def examiner(response, request_url: str, max_items: int):
        calls.append((response.payload, request_url, max_items))
        return document, ()

    source = FeedSource(
        FeedSourceSpec("source", "https://example.test/feed", "source", max_items=12),
        transport=Transport(),
        cache=FeedCacheStore(tmp_path),
        now=lambda: 1000.0,
        document_parser=lambda *_args: (_ for _ in ()).throw(
            AssertionError("response examiner should own FEEDS document parsing")
        ),
        response_examiner=examiner,
    )
    result = source.refresh(force=True)
    assert result.snapshot is not None
    assert result.snapshot.document == document
    assert calls == [(RSS, "https://example.test/feed", 12)]


def test_isolated_parser_failure_retains_last_good_rows_and_artwork(tmp_path: Path):
    cache_root = tmp_path / "feeds"
    store = FeedCacheStore(cache_root)
    document = _document()
    warm = _seed_artwork(cache_root, document)
    record = _record(document, artwork=warm.files_by_item.items())
    store.write("source", record)

    class Transport:
        def fetch(self, _url, **_kwargs):
            return FeedHttpResponse(
                "ok", RSS, "https://example.test/feed",
                content_type="application/rss+xml",
            )

    source = FeedSource(
        FeedSourceSpec("source", "https://example.test/feed", "source"),
        transport=Transport(),
        cache=store,
        now=lambda: 2000.0,
        response_examiner=lambda *_args: (_ for _ in ()).throw(
            ValueError("parser child unavailable")
        ),
    )
    result = source.refresh(force=True)
    assert result.status == "stale_cache"
    assert result.snapshot is not None and result.snapshot.document == document
    assert dict(result.local_artwork_by_item) == dict(warm.local_by_item)
    assert store.read("source") is not None

def test_isolated_parse_process_does_not_execute_parent_parser(monkeypatch):
    """A real spawn child, not another ThreadPool job sharing Qt's GIL."""
    from core.feeds import process_parser

    def parent_must_not_run(*_args, **_kwargs):
        raise AssertionError("parser executed in parent process")

    monkeypatch.setattr(process_parser, "parse_feed_bytes", parent_must_not_run)
    # Prove the monkeypatch would catch an accidental direct call.
    with pytest.raises(AssertionError, match="parent process"):
        process_parser._parse_job(RSS, "https://example.test/feed", 12)

    parser = process_parser.FeedParseProcess()
    try:
        document = parser.parse(RSS, source_url="https://example.test/feed", max_items=12)
        assert len(document.items) == 1
        item = document.items[0]
        assert item.title == "One"
        assert item.action_url == "https://example.test/one"
        assert item.item_id
    finally:
        parser.close()
