"""Standards-based feed discovery: a site address -> its RSS/Atom feed.

A CUSTOM address may be a feed or an ordinary page such as
``https://arstechnica.com``. Nothing here knows any particular website; every
candidate comes from a published convention, and every candidate is verified by
fetching and parsing it with the production transport/parser before it is
accepted:

1. the address itself, when it already serves a feed;
2. feeds the page advertises: the RFC 8288 ``Link`` header and HTML
   ``<link rel="alternate" type="application/rss+xml|atom+xml">`` (the RSS/Atom
   autodiscovery convention), in document order with comment feeds demoted;
3. feed-shaped ``<a href>`` links on that page;
4. the paths common publishing platforms serve feeds on (``/feed``, ``/rss``,
   ``/feed.xml``, ``/atom.xml``, ``/rss.xml``, ``/index.xml``), relative to the
   page's own directory. This is what resolves a site whose home page sits
   behind a bot wall while its feed does not; bot walls and challenges are
   never bypassed.

One HTML page found on the way (a conventional path that serves a feed index,
for example) may contribute its own advertised links. The walk is bounded by a
fetch count and a wall-clock deadline, and it stops at the first verified feed.

Discovery is transport/parser work only: no Qt, cache, timer or scheduler. The
source runs it off the GUI thread and only when needed (first resolution, or
when a stored resolution has gone), so a steady refresh is still one
conditional request to the resolved feed.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import ipaddress
import re
import time
from typing import Callable
from urllib.parse import urljoin, urlparse, urlunparse

from .models import FeedDocument
from .parser import FeedEmptyError, FeedParseError, parse_feed_bytes
from .transport import FeedHttpResponse, FeedTransportError, validate_feed_url


MAX_DISCOVERY_FETCHES = 8
DISCOVERY_DEADLINE_SECONDS = 20.0
MAX_HTML_PAGES = 2
_MAX_HTML_SCAN_CHARS = 1_500_000
_HTML_CHUNK_CHARS = 64 * 1024
_MAX_ADVERTISED = 8
_MAX_ANCHORS = 8

# Paths common publishing platforms serve feeds on (WordPress, Substack and
# Ghost style ``feed``/``rss``; Jekyll ``feed.xml``; static ``atom.xml`` and
# ``rss.xml``; Hugo ``index.xml``). Platform conventions, not site knowledge.
CONVENTIONAL_FEED_NAMES = ("feed", "rss", "feed.xml", "atom.xml", "rss.xml", "index.xml")

_FEED_TYPES = frozenset({
    "application/rss+xml",
    "application/atom+xml",
    "application/rdf+xml",
    "application/rss",
    "application/atom",
    "application/x-rss+xml",
    "application/x-atom+xml",
    "text/rss+xml",
    "text/atom+xml",
})
_GENERIC_XML_TYPES = frozenset({"application/xml", "text/xml"})
_FEED_WORD_RE = re.compile(r"rss|atom|feed", re.IGNORECASE)
_FEED_PATH_SUFFIXES = (
    ".rss", ".rdf", ".atom", "/feed", "/feed/", "/rss", "/rss/", "/atom", "/atom/",
    "rss.xml", "atom.xml", "feed.xml", "/feeds/posts/default",
)
_FEED_QUERY_RE = re.compile(r"(^|&)(feed|format|type|page)=(rss2?|atom|feed)(&|$)", re.IGNORECASE)
_FEED_HOST_PREFIXES = ("feeds.", "feed.", "rss.")
_LINK_HEADER_RE = re.compile(r"<([^>]*)>((?:\s*;\s*[^;,]+)*)")
_LINK_PARAM_RE = re.compile(r";\s*([a-zA-Z*]+)\s*=\s*(\"[^\"]*\"|[^;,\s]+)")
_HTML_HEAD_RE = re.compile(
    rb"^\s*(?:<\?[^>]*>\s*|<!--.*?-->\s*)*(?:<!doctype\s+html|<html)", re.IGNORECASE | re.DOTALL)
_FEED_HEAD_RE = re.compile(
    rb"^\s*(?:<\?[^>]*>\s*|<!--.*?-->\s*|<!doctype\s+(?:rss|feed)[^>]*>\s*)*<(?:rss|feed|rdf:rdf)[\s>]",
    re.IGNORECASE | re.DOTALL)
_CHARSET_RE = re.compile(r"charset=([\w.:-]+)", re.IGNORECASE)
_UTF8_BOM = bytes((0xEF, 0xBB, 0xBF))


class FeedDiscoveryError(FeedParseError):
    """No verified feed was found for the address."""


@dataclass(frozen=True)
class FeedCandidate:
    url: str
    via: str  # "link_header" | "advertised" | "anchor" | "conventional" | "seed"


@dataclass(frozen=True)
class FeedResolution:
    """A verified feed (or a 304 for the address that was asked first)."""

    response: FeedHttpResponse
    document: FeedDocument | None  # None only for a not-modified primary
    feed_url: str  # the requested URL that served the feed
    via: str  # "direct" when the first address served the feed itself
    attempts: int

    @property
    def discovered(self) -> bool:
        return self.via != "direct"


def _private_literal_host(host: str) -> bool:
    if not host:
        return True
    if host.casefold() == "localhost" or host.casefold().endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return bool(
        address.is_private or address.is_loopback or address.is_link_local
        or address.is_reserved or address.is_multicast or address.is_unspecified
    )


def _candidate_url(value: object, *, base_url: str, page_url: str) -> str:
    """Resolve and admit one discovered URL (HTTP/S only; no private hops)."""
    text = str(value or "").strip()
    if not text or len(text) > 8192:
        return ""
    if text.casefold().startswith("feed:"):
        text = text[5:]
    try:
        resolved = urljoin(base_url, text)
        url = validate_feed_url(resolved)
        parsed = urlparse(url)
        page_host = urlparse(page_url).hostname or ""
    except ValueError:
        return ""
    # A public page must not steer the saver at the user's own network. The
    # user can still type a LAN feed address directly.
    if _private_literal_host(parsed.hostname or "") and not _private_literal_host(page_host):
        return ""
    return urlunparse(parsed._replace(fragment=""))


def _looks_like_feed_link(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.casefold()
    host = (parsed.hostname or "").casefold()
    if "comment" in path:
        return False
    if path.endswith(_FEED_PATH_SUFFIXES):
        return True
    if path.endswith(".xml") and (_FEED_WORD_RE.search(path) or host.startswith(_FEED_HOST_PREFIXES)):
        return True
    if host.startswith(_FEED_HOST_PREFIXES) and path not in {"", "/"}:
        return True
    return bool(_FEED_QUERY_RE.search(parsed.query))


class _FeedLinkCollector(HTMLParser):
    def __init__(self, *, page_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.base_url = page_url
        self._base_seen = False
        self.advertised: list[tuple[bool, str]] = []  # (is_comment_feed, url)
        self.anchors: list[str] = []
        self.head_closed = False

    def _admit(self, value: object) -> str:
        return _candidate_url(value, base_url=self.base_url, page_url=self.page_url)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        kind = tag.casefold()
        mapping = {str(key).casefold(): str(value or "") for key, value in attrs}
        if kind == "base" and not self._base_seen:
            self._base_seen = True
            base = _candidate_url(mapping.get("href"), base_url=self.page_url, page_url=self.page_url)
            if base:
                self.base_url = base
        elif kind == "link":
            self._link(mapping)
        elif kind == "a" and len(self.anchors) < _MAX_ANCHORS:
            url = self._admit(mapping.get("href"))
            if url and _looks_like_feed_link(url) and url not in self.anchors:
                self.anchors.append(url)
        elif kind == "body":
            self.head_closed = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "head":
            self.head_closed = True

    def _link(self, mapping: dict[str, str]) -> None:
        if len(self.advertised) >= _MAX_ADVERTISED:
            return
        rel = set(mapping.get("rel", "").casefold().split())
        media_type = mapping.get("type", "").casefold().split(";", 1)[0].strip()
        title = mapping.get("title", "")
        href = mapping.get("href", "")
        if "oembed" in media_type or "json" in media_type:
            return
        if not rel & {"alternate", "feed"}:
            return
        if media_type in _FEED_TYPES:
            pass
        elif media_type in _GENERIC_XML_TYPES or (not media_type and "feed" in rel):
            if not _FEED_WORD_RE.search(f"{title} {href}") and "feed" not in rel:
                return
        else:
            return
        url = self._admit(href)
        if url and all(url != existing for _, existing in self.advertised):
            comment = "comment" in f"{title} {href}".casefold()
            self.advertised.append((comment, url))


def _decode_html(payload: bytes, content_type: str) -> str:
    charset = "utf-8"
    match = _CHARSET_RE.search(content_type or "")
    if match:
        charset = match.group(1)
    head = payload[:_MAX_HTML_SCAN_CHARS]
    try:
        return head.decode(charset, errors="replace")
    except LookupError:
        return head.decode("utf-8", errors="replace")


def _link_header_candidates(link_header: str, *, page_url: str) -> list[str]:
    urls: list[str] = []
    for target, params in _LINK_HEADER_RE.findall(str(link_header or "")[:4096]):
        values = {key.casefold(): value.strip('"') for key, value in _LINK_PARAM_RE.findall(params)}
        rel = set(values.get("rel", "").casefold().split())
        media_type = values.get("type", "").casefold()
        if "alternate" in rel and media_type in _FEED_TYPES:
            url = _candidate_url(target, base_url=page_url, page_url=page_url)
            if url and url not in urls:
                urls.append(url)
    return urls


def advertised_feed_candidates(
    payload: bytes,
    *,
    page_url: str,
    content_type: str = "",
    link_header: str = "",
) -> tuple[FeedCandidate, ...]:
    """Feeds a page advertises, most authoritative first (pure, bounded)."""
    candidates = [FeedCandidate(url, "link_header")
                  for url in _link_header_candidates(link_header, page_url=page_url)]
    collector = _FeedLinkCollector(page_url=page_url)
    text = _decode_html(bytes(payload or b""), content_type)
    try:
        for start in range(0, len(text), _HTML_CHUNK_CHARS):
            collector.feed(text[start:start + _HTML_CHUNK_CHARS])
            if collector.head_closed and collector.advertised:
                break
            if len(collector.anchors) >= _MAX_ANCHORS and collector.head_closed:
                break
        collector.close()
    except (ValueError, AssertionError):
        pass
    ordered = [url for comment, url in collector.advertised if not comment]
    ordered += [url for comment, url in collector.advertised if comment]
    candidates += [FeedCandidate(url, "advertised") for url in ordered]
    candidates += [FeedCandidate(url, "anchor") for url in collector.anchors]
    seen: set[str] = set()
    unique: list[FeedCandidate] = []
    for candidate in candidates:
        if candidate.url not in seen:
            seen.add(candidate.url)
            unique.append(candidate)
    return tuple(unique)


def conventional_feed_candidates(page_url: str) -> tuple[FeedCandidate, ...]:
    """Platform-convention feed paths within the page's own directory.

    ``https://example.com`` gives ``https://example.com/feed`` and so on;
    ``https://example.com/blog/`` gives ``https://example.com/blog/feed``.
    Never walks up to the site root from a sub-path, so an address on a shared
    platform host cannot resolve to that platform's own site-wide feed.
    """
    try:
        parsed = urlparse(validate_feed_url(page_url))
    except ValueError:
        return ()
    path = parsed.path or "/"
    if not path.endswith("/"):
        leaf = path.rsplit("/", 1)[-1]
        path = path[: len(path) - len(leaf)] if "." in leaf else path + "/"
    base = urlunparse(parsed._replace(path=path, params="", query="", fragment=""))
    return tuple(FeedCandidate(urljoin(base, name), "conventional") for name in CONVENTIONAL_FEED_NAMES)


def _is_html(response: FeedHttpResponse) -> bool:
    head = response.payload[:4096].removeprefix(_UTF8_BOM)
    if _FEED_HEAD_RE.match(head):
        return False
    if _HTML_HEAD_RE.match(head):
        return True
    media_type = response.content_type.casefold().split(";", 1)[0].strip()
    return media_type in {"text/html", "application/xhtml+xml"}


def _feed_document(response: FeedHttpResponse, *, url: str, max_items: int) -> FeedDocument | None:
    """The response's feed, or ``None`` when it is not a feed at all.

    Raises ``FeedEmptyError`` for a real feed with no usable entries. Obvious
    HTML is never handed to the feed parser.
    """
    if _is_html(response):
        return None
    try:
        return parse_feed_bytes(response.payload, source_url=response.final_url or url, max_items=max_items)
    except FeedEmptyError:
        raise
    except FeedParseError:
        return None


def _page_candidates(response: FeedHttpResponse, *, url: str) -> list[FeedCandidate]:
    if not _is_html(response) and b"<html" not in response.payload[:8192].lower():
        return []
    return list(advertised_feed_candidates(
        response.payload,
        page_url=response.final_url or url,
        content_type=response.content_type,
        link_header=response.link_header,
    ))


def _visit_key(url: str) -> str:
    """``https://host`` and ``https://host/`` are one request."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    if parsed.path in {"", "/"}:
        return urlunparse(parsed._replace(path="/", fragment=""))
    return urlunparse(parsed._replace(fragment=""))


def _gone(exc: FeedTransportError) -> bool:
    return exc.status_code in {404, 410}


def _page_error_discoverable(exc: FeedTransportError) -> bool:
    """An answered error for the configured address that discovery may route around.

    A 403/405 bot wall or a 404 still lets platform-convention paths answer.
    Offline/network failure, 408, 429 and 5xx never start extra requests.
    """
    code = exc.status_code
    return code is not None and 400 <= code < 500 and code not in {408, 429}


def resolve_feed(
    fetch: Callable[..., FeedHttpResponse],
    url: str,
    *,
    etag: str = "",
    last_modified: str = "",
    configured_url: str = "",
    home_url: str = "",
    max_items: int = 50,
    max_fetches: int = MAX_DISCOVERY_FETCHES,
    deadline_seconds: float = DISCOVERY_DEADLINE_SECONDS,
    should_continue: Callable[[], bool] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> FeedResolution:
    """Fetch ``url``; when it is not a feed, discover and verify one.

    ``url`` is the address to try first: the configured address, or a stored
    resolution of it (then ``configured_url`` differs and is a discovery seed).
    ``home_url`` (the last-good feed's own site link) is a further seed, so a
    feed that moves can be found again from the site that published it.

    Raises ``FeedTransportError`` when the first address fails in a way that
    must not start discovery (offline, rate limited, server error, or a stored
    resolution that is not gone), ``FeedEmptyError`` for an empty but real
    feed at the first address, and ``FeedDiscoveryError`` when no verified
    feed was found.
    """
    started = clock()
    attempts = 0
    fetched: set[str] = set()
    html_pages = 0
    primary = validate_feed_url(url)
    configured = configured_url or primary
    is_stored_resolution = primary != configured

    def _alive() -> bool:
        return True if should_continue is None else bool(should_continue())

    def _fetch(target: str, **kwargs: str) -> FeedHttpResponse:
        nonlocal attempts
        if not _alive():
            raise FeedTransportError("feed fetch cancelled")
        attempts += 1
        fetched.add(_visit_key(target))
        return fetch(target, **kwargs)

    queue: list[FeedCandidate] = []
    page_url = primary
    try:
        response = _fetch(primary, etag=etag, last_modified=last_modified)
    except FeedTransportError as exc:
        # A bot-walled (403/405) or missing page may still have a feed on a
        # platform-convention path; a stored feed resolution is rediscovered
        # only once it is gone.
        if is_stored_resolution:
            if not _gone(exc):
                raise
        elif not _page_error_discoverable(exc):
            raise
    else:
        if response.status == "not_modified":
            return FeedResolution(response, None, primary, "direct", attempts)
        document = _feed_document(response, url=primary, max_items=max_items)
        if document is not None:
            return FeedResolution(response, document, primary, "direct", attempts)
        html_pages += 1
        page_url = response.final_url or primary
        queue.extend(_page_candidates(response, url=primary))

    # The last-good feed's own site link is the most direct route to a feed
    # that moved, so it precedes any guessing.
    for seed in (configured, home_url):
        try:
            seed_url = validate_feed_url(seed) if seed else ""
        except ValueError:
            continue
        if seed_url and _visit_key(seed_url) not in fetched:
            queue.append(FeedCandidate(seed_url, "seed"))
    if not is_stored_resolution and not home_url:
        # A configured address that never served a feed is a page: guess
        # platform-convention paths within it. (One that did serve a feed is
        # not a directory to guess under; its site link is the seed above.)
        queue.extend(conventional_feed_candidates(page_url))

    limit = max(1, int(max_fetches))
    while queue:
        candidate = queue.pop(0)
        if _visit_key(candidate.url) in fetched:
            continue
        if attempts >= limit or clock() - started > float(deadline_seconds):
            break
        try:
            response = _fetch(candidate.url)
        except FeedTransportError as exc:
            if not _alive():
                raise
            if candidate.via == "seed" and _page_error_discoverable(exc):
                queue.extend(conventional_feed_candidates(candidate.url))
            continue
        if response.status != "ok":
            continue
        try:
            document = _feed_document(response, url=candidate.url, max_items=max_items)
        except FeedEmptyError:
            continue
        if document is not None:
            return FeedResolution(response, document, candidate.url, candidate.via, attempts)
        if candidate.via == "seed":
            queue.extend(conventional_feed_candidates(response.final_url or candidate.url))
        if html_pages < MAX_HTML_PAGES:
            html_pages += 1
            # A page's own advertised feeds outrank the remaining guesses.
            queue[0:0] = [item for item in _page_candidates(response, url=candidate.url)
                          if _visit_key(item.url) not in fetched]

    if not _alive():
        raise FeedTransportError("feed fetch cancelled")
    raise FeedDiscoveryError(f"no feed found after {attempts} fetches")


__all__ = [
    "CONVENTIONAL_FEED_NAMES",
    "FeedCandidate",
    "FeedDiscoveryError",
    "FeedResolution",
    "advertised_feed_candidates",
    "conventional_feed_candidates",
    "resolve_feed",
]
