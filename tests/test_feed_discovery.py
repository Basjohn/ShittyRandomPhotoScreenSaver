"""Feed discovery: a website address resolves to its feed without site rules.

Fixtures reproduce the real patterns observed on live sites (2026-09-24): an
advertised relative ``<link rel=alternate>``, a WordPress comments feed, a
feed only linked from an anchor, a home page behind a bot wall whose feed path
is open, and a feed index page one hop away.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.feeds.cache import FeedCacheStore
from core.feeds.config import CustomFeedConfig
from core.feeds.discovery import (
    MAX_DISCOVERY_FETCHES,
    FeedDiscoveryError,
    advertised_feed_candidates,
    conventional_feed_candidates,
    resolve_feed,
)
from core.feeds.models import FeedSourceSpec
from core.feeds.parser import FeedEmptyError
from core.feeds.probe import probe_feed_url
from core.feeds.source import FeedSource
from core.feeds.transport import FeedHttpResponse, FeedTransportError, normalize_feed_address


RSS = b'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Site News</title><link>https://site.test/</link>
 <item><guid>one</guid><title>First story</title><link>https://site.test/one</link></item>
</channel></rss>'''

MOVED_RSS = b'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Site News</title><link>https://site.test/</link>
 <item><guid>two</guid><title>Story from the new feed</title><link>https://site.test/two</link></item>
</channel></rss>'''

EMPTY_RSS = b'<?xml version="1.0"?><rss version="2.0"><channel><title>Empty</title></channel></rss>'


def _page(head: str = "", body: str = "") -> bytes:
    return f"<!DOCTYPE html><html><head><title>Site</title>{head}</head><body>{body}</body></html>".encode()


def _html(url: str, payload: bytes, **kwargs) -> FeedHttpResponse:
    return FeedHttpResponse("ok", payload, url, content_type="text/html; charset=utf-8", **kwargs)


def _feed(url: str, payload: bytes = RSS, etag: str = "") -> FeedHttpResponse:
    return FeedHttpResponse("ok", payload, url, etag=etag, content_type="application/rss+xml")


class _Web:
    """URL -> response or exception; anything unlisted is an HTTP 404."""

    def __init__(self, routes: dict[str, object]) -> None:
        self.routes = dict(routes)
        self.calls: list[tuple[str, dict]] = []

    def fetch(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        answer = self.routes.get(url, FeedTransportError("HTTP 404", status_code=404))
        if isinstance(answer, Exception):
            raise answer
        return answer

    @property
    def urls(self) -> list[str]:
        return [url for url, _ in self.calls]


def test_advertised_feeds_resolve_relative_links_and_demote_comment_feeds():
    page = _page(
        '<link rel="alternate" type="application/rss+xml" title="Site &raquo; Comments Feed" href="/comments/feed/">'
        '<link rel="alternate" title="oEmbed (XML)" type="text/xml+oembed" href="/oembed?format=xml">'
        '<link rel="alternate" type="application/json" href="/wp-json/">'
        '<link rel="alternate" type="application/rss+xml" title="Site" href="/rss/index.xml" data-next-head="">'
        '<link rel="stylesheet" href="/style.css">'
    )
    candidates = advertised_feed_candidates(page, page_url="https://site.test/news")
    assert [(c.url, c.via) for c in candidates] == [
        ("https://site.test/rss/index.xml", "advertised"),
        ("https://site.test/comments/feed/", "advertised"),
    ]


def test_link_header_base_href_and_unsafe_targets():
    page = _page(
        '<base href="https://cdn.site.test/app/">'
        '<link rel="alternate" type="application/atom+xml" href="atom.xml">'
        '<link rel="alternate" type="application/rss+xml" href="javascript:alert(1)">'
        '<link rel="alternate" type="application/rss+xml" href="http://192.168.1.1/rss">'
    )
    candidates = advertised_feed_candidates(
        page,
        page_url="https://site.test/",
        link_header='<https://site.test/wp-json/>; rel="https://api.w.org/", '
                    '</feed.atom>; rel="alternate"; type="application/atom+xml"',
    )
    # A public page cannot steer the saver at the user's own network, and
    # only HTTP/S candidates exist at all.
    assert [(c.url, c.via) for c in candidates] == [
        ("https://site.test/feed.atom", "link_header"),
        ("https://cdn.site.test/app/atom.xml", "advertised"),
    ]


def test_feed_shaped_anchors_are_candidates_when_nothing_is_advertised():
    page = _page(body=(
        '<a href="/story/1">A story</a>'
        '<a href="/comments/feed/">Comments</a>'
        '<a href="https://www.site.test/feed/">RSS</a>'
        '<a href="https://rss.site.test/services/xml/rss/HomePage.xml">Home</a>'
        '<a href="/about.xml">About</a>'
    ))
    candidates = advertised_feed_candidates(page, page_url="https://www.site.test/")
    assert [(c.url, c.via) for c in candidates] == [
        ("https://www.site.test/feed/", "anchor"),
        ("https://rss.site.test/services/xml/rss/HomePage.xml", "anchor"),
    ]


def test_conventional_paths_stay_inside_the_address_directory():
    root = [c.url for c in conventional_feed_candidates("https://site.test")]
    assert root[:2] == ["https://site.test/feed", "https://site.test/rss"]
    assert all(c.via == "conventional" for c in conventional_feed_candidates("https://site.test"))
    # A sub-path never walks up to a shared host's site-wide feed.
    blog = [c.url for c in conventional_feed_candidates("https://host.test/@writer?tab=posts")]
    assert blog[0] == "https://host.test/@writer/feed"
    assert all(url.startswith("https://host.test/@writer/") for url in blog)
    assert conventional_feed_candidates("https://site.test/blog/index.html")[0].url == "https://site.test/blog/feed"


def test_address_that_is_already_a_feed_needs_one_fetch():
    web = _Web({"https://site.test/rss": _feed("https://site.test/rss")})
    resolution = resolve_feed(web.fetch, "https://site.test/rss")
    assert (resolution.feed_url, resolution.via, resolution.attempts) == ("https://site.test/rss", "direct", 1)
    assert resolution.discovered is False


def test_misconfigured_feed_served_as_html_is_still_a_feed():
    served = FeedHttpResponse("ok", RSS, "https://site.test/rss", content_type="text/html")
    web = _Web({"https://site.test/rss": served})
    assert resolve_feed(web.fetch, "https://site.test/rss").via == "direct"


def test_site_page_resolves_to_its_advertised_feed_skipping_a_dead_one():
    page = _page(
        '<link rel="alternate" type="application/rss+xml" href="/old.xml">'
        '<link rel="alternate" type="application/atom+xml" href="/atom.xml">'
    )
    web = _Web({
        "https://site.test": _html("https://site.test/", page),
        "https://site.test/atom.xml": _feed("https://site.test/atom.xml"),
    })
    resolution = resolve_feed(web.fetch, "https://site.test")
    assert (resolution.feed_url, resolution.via) == ("https://site.test/atom.xml", "advertised")
    assert web.urls == ["https://site.test", "https://site.test/old.xml", "https://site.test/atom.xml"]
    assert resolution.document is not None and resolution.document.items[0].title == "First story"


def test_bot_walled_home_page_resolves_through_a_platform_path_without_bypassing_it():
    web = _Web({
        "https://site.test": FeedTransportError("HTTP 405", status_code=405),
        "https://site.test/feed": _feed("https://site.test/feed/"),
    })
    resolution = resolve_feed(web.fetch, "https://site.test")
    assert (resolution.feed_url, resolution.via) == ("https://site.test/feed", "conventional")
    assert web.urls == ["https://site.test", "https://site.test/feed"]


def test_feed_index_page_one_hop_away_contributes_its_links():
    index = _page(body='<a href="https://rss.site.test/xml/HomePage.xml">Home Page</a>')
    web = _Web({
        "https://www.site.test": FeedTransportError("HTTP 403", status_code=403),
        "https://www.site.test/feed": FeedTransportError("HTTP 403", status_code=403),
        "https://www.site.test/rss": _html("https://www.site.test/rss", index),
        "https://rss.site.test/xml/HomePage.xml": _feed("https://rss.site.test/xml/HomePage.xml"),
    })
    resolution = resolve_feed(web.fetch, "https://www.site.test")
    assert (resolution.feed_url, resolution.via) == ("https://rss.site.test/xml/HomePage.xml", "anchor")
    assert resolution.attempts == 4


@pytest.mark.parametrize("failure", [
    FeedTransportError("ConnectTimeout"),
    FeedTransportError("HTTP 429", status_code=429),
    FeedTransportError("HTTP 503", status_code=503),
])
def test_offline_rate_limited_or_failing_server_starts_no_extra_requests(failure):
    web = _Web({"https://site.test": failure})
    with pytest.raises(FeedTransportError):
        resolve_feed(web.fetch, "https://site.test")
    assert web.urls == ["https://site.test"]


def test_empty_real_feed_is_a_source_failure_not_a_reason_to_discover():
    web = _Web({"https://site.test/rss": _feed("https://site.test/rss", EMPTY_RSS)})
    with pytest.raises(FeedEmptyError):
        resolve_feed(web.fetch, "https://site.test/rss")
    assert len(web.calls) == 1


def test_discovery_is_bounded_by_fetch_count_and_deadline():
    web = _Web({"https://site.test": _html("https://site.test/", _page())})
    with pytest.raises(FeedDiscoveryError):
        resolve_feed(web.fetch, "https://site.test")
    assert len(web.calls) <= MAX_DISCOVERY_FETCHES

    ticks = iter(range(0, 1000, 15))
    slow = _Web({"https://site.test": _html("https://site.test/", _page())})
    with pytest.raises(FeedDiscoveryError):
        resolve_feed(slow.fetch, "https://site.test", deadline_seconds=20, clock=lambda: next(ticks))
    assert len(slow.calls) == 2


def test_cancellation_stops_discovery_between_candidates():
    alive = [True]
    web = _Web({"https://site.test": FeedTransportError("HTTP 405", status_code=405)})

    def fetch(url, **kwargs):
        alive[0] = False
        return web.fetch(url, **kwargs)

    with pytest.raises(FeedTransportError, match="cancelled"):
        resolve_feed(fetch, "https://site.test", should_continue=lambda: alive[0])
    assert web.urls == ["https://site.test"]


def _site_source(tmp_path: Path, web: _Web, *, url: str = "https://site.test", clock=None) -> FeedSource:
    ticks = clock or iter(float(n) for n in range(1000, 100000, 100))
    return FeedSource(
        FeedSourceSpec("custom:site", url, "custom_site"),
        transport=web, cache=FeedCacheStore(tmp_path), now=lambda: next(ticks),
    )


def test_site_address_resolves_once_then_refreshes_the_feed_with_one_conditional_request(tmp_path: Path):
    page = _page('<link rel="alternate" type="application/rss+xml" href="/feed/">')
    web = _Web({
        "https://site.test": _html("https://site.test/", page),
        "https://site.test/feed/": _feed("https://site.test/feed/", etag='"v1"'),
    })
    source = _site_source(tmp_path, web)
    first = source.refresh()
    assert first.status == "available"
    stored = FeedCacheStore(tmp_path).read("custom_site")
    assert stored is not None and stored.resolved_url == "https://site.test/feed/"
    assert stored.etag == '"v1"'

    web.calls.clear()
    web.routes["https://site.test/feed/"] = FeedHttpResponse("not_modified", b"", "https://site.test/feed/")
    second = source.refresh(force=True)
    assert second.status == "not_modified"
    assert second.snapshot == first.snapshot
    # Steady state is exactly today's cost: one conditional request to the
    # feed, never the site page again.
    assert web.calls == [("https://site.test/feed/", {"etag": '"v1"', "last_modified": ""})]


def test_moved_feed_is_rediscovered_and_old_validators_stay_with_the_old_url(tmp_path: Path):
    page = _page('<link rel="alternate" type="application/rss+xml" href="/feed/">')
    web = _Web({
        "https://site.test": _html("https://site.test/", page),
        "https://site.test/feed/": _feed("https://site.test/feed/", etag='"old"'),
    })
    source = _site_source(tmp_path, web)
    source.refresh()

    web.calls.clear()
    web.routes["https://site.test/feed/"] = FeedTransportError("HTTP 410", status_code=410)
    web.routes["https://site.test"] = _html(
        "https://site.test/", _page('<link rel="alternate" type="application/atom+xml" href="/atom.xml">'))
    web.routes["https://site.test/atom.xml"] = _feed("https://site.test/atom.xml", MOVED_RSS, etag='"new"')
    moved = source.refresh(force=True)
    assert moved.status == "available" and moved.changed is True
    assert moved.snapshot.document.items[0].title == "Story from the new feed"
    assert web.urls == ["https://site.test/feed/", "https://site.test", "https://site.test/atom.xml"]
    assert web.calls[2][1] == {}
    stored = FeedCacheStore(tmp_path).read("custom_site")
    assert (stored.resolved_url, stored.etag) == ("https://site.test/atom.xml", '"new"')


def test_transient_failure_of_a_resolved_feed_keeps_last_good_without_rediscovery(tmp_path: Path):
    page = _page('<link rel="alternate" type="application/rss+xml" href="/feed/">')
    web = _Web({
        "https://site.test": _html("https://site.test/", page),
        "https://site.test/feed/": _feed("https://site.test/feed/"),
    })
    source = _site_source(tmp_path, web)
    first = source.refresh()

    web.calls.clear()
    web.routes["https://site.test/feed/"] = FeedTransportError("HTTP 503", status_code=503)
    failed = source.refresh(force=True)
    assert failed.status == "stale_cache"
    assert failed.snapshot == first.snapshot
    assert web.urls == ["https://site.test/feed/"]
    stored = FeedCacheStore(tmp_path).read("custom_site")
    assert stored.resolved_url == "https://site.test/feed/"
    assert stored.health.consecutive_failures == 1


def test_dead_direct_feed_is_found_again_from_its_own_site_link(tmp_path: Path):
    web = _Web({"https://site.test/old.rss": _feed("https://site.test/old.rss")})
    source = _site_source(tmp_path, web, url="https://site.test/old.rss")
    source.refresh()
    assert FeedCacheStore(tmp_path).read("custom_site").resolved_url == ""

    web.calls.clear()
    web.routes["https://site.test/old.rss"] = FeedTransportError("HTTP 404", status_code=404)
    web.routes["https://site.test/"] = _html(
        "https://site.test/", _page('<link rel="alternate" type="application/rss+xml" href="/feed/">'))
    web.routes["https://site.test/feed/"] = _feed("https://site.test/feed/", MOVED_RSS)
    moved = source.refresh(force=True)
    assert moved.status == "available"
    # The feed's own <link> (its site) is tried before any path guessing.
    assert web.urls == ["https://site.test/old.rss", "https://site.test/", "https://site.test/feed/"]
    assert FeedCacheStore(tmp_path).read("custom_site").resolved_url == "https://site.test/feed/"


def test_dead_feed_on_a_bot_walled_site_is_guessed_at_the_site_not_under_the_feed(tmp_path: Path):
    web = _Web({"https://site.test/feed": _feed("https://site.test/feed")})
    source = _site_source(tmp_path, web, url="https://site.test/feed")
    source.refresh()

    web.calls.clear()
    web.routes["https://site.test/feed"] = FeedTransportError("HTTP 404", status_code=404)
    web.routes["https://site.test/"] = FeedTransportError("HTTP 405", status_code=405)
    web.routes["https://site.test/rss"] = _feed("https://site.test/rss", MOVED_RSS)
    moved = source.refresh(force=True)
    # A dead feed is not a directory: ``/feed/feed`` style guesses would spend
    # the whole fetch budget before the site's own conventional paths.
    assert moved.status == "available"
    assert web.urls == ["https://site.test/feed", "https://site.test/", "https://site.test/rss"]


def test_site_without_any_feed_fails_under_normal_backoff(tmp_path: Path):
    web = _Web({"https://site.test": _html("https://site.test/", _page())})
    source = _site_source(tmp_path, web, clock=iter((1000.0, 1010.0)))
    first = source.refresh()
    assert first.status == "unavailable" and first.failure == "FeedDiscoveryError"
    calls = len(web.calls)
    assert source.refresh().status == "unavailable"
    assert len(web.calls) == calls


def test_stored_resolution_round_trips_and_a_bad_one_is_dropped_not_fatal(tmp_path: Path):
    page = _page('<link rel="alternate" type="application/rss+xml" href="/feed/">')
    web = _Web({
        "https://site.test": _html("https://site.test/", page),
        "https://site.test/feed/": _feed("https://site.test/feed/"),
    })
    _site_source(tmp_path, web).refresh()
    path = FeedCacheStore(tmp_path).path_for("custom_site")
    text = path.read_text(encoding="utf-8")
    assert '"resolved_url":"https://site.test/feed/"' in text
    path.write_text(text.replace('"https://site.test/feed/"', '"file:///C:/secret"'), encoding="utf-8")
    record = FeedCacheStore(tmp_path).read("custom_site")
    assert record is not None and record.snapshot is not None
    assert record.resolved_url == ""


def test_bare_host_addresses_normalise_to_https_and_nothing_else_widens():
    assert normalize_feed_address(" arstechnica.com ") == "https://arstechnica.com"
    assert normalize_feed_address("example.com/blog/") == "https://example.com/blog/"
    assert normalize_feed_address("localhost:8080/feed") == "https://localhost:8080/feed"
    assert normalize_feed_address("//cdn.example.com/rss") == "https://cdn.example.com/rss"
    assert normalize_feed_address("feed://example.com/rss") == "https://example.com/rss"
    assert normalize_feed_address("feed:https://example.com/rss") == "https://example.com/rss"
    assert normalize_feed_address("http://example.com/rss") == "http://example.com/rss"
    for rejected in ("magnet:?xt=urn:btih:abc", "javascript:alert(1)", "file:///C:/feed.xml", "not a url"):
        assert normalize_feed_address(rejected) == rejected
    config = CustomFeedConfig.from_mapping("feeds_custom_1", {"feed_url": "arstechnica.com", "enabled": True})
    assert config.configured and config.source_spec().url == "https://arstechnica.com"


def test_probe_reports_the_feed_a_site_address_resolves_to():
    page = _page('<link rel="alternate" type="application/rss+xml" href="/feed/">')
    web = _Web({
        "https://site.test": _html("https://site.test/", page),
        "https://site.test/feed/": _feed("https://site.test/feed/"),
    })
    result = probe_feed_url("site.test", transport=web)
    assert result.ok and result.discovered
    assert (result.feed_url, result.via, result.item_count) == ("https://site.test/feed/", "advertised", 1)

    missing = probe_feed_url("https://nothing.test", transport=_Web({
        "https://nothing.test": _html("https://nothing.test/", _page()),
    }))
    assert (missing.ok, missing.failure) == (False, "FeedDiscoveryError")
