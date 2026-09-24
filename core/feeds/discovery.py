"""Standards-based feed discovery: a site address -> its RSS/Atom feed.

A CUSTOM address may be a feed or an ordinary page such as
``https://arstechnica.com``. Nothing here knows any particular website; every
candidate comes from a published convention, and every candidate is verified by
fetching and parsing it with the production transport/parser before it is
accepted:

1. the address itself, when it already serves a feed (RSS, Atom, JSON Feed or
   JF2), or when it is an IndieWeb h-feed page that advertises no other feed;
2. feeds the page advertises: the RFC 8288 ``Link`` header and HTML
   ``<link rel="alternate">`` of an RSS, Atom, JSON Feed, JF2 or h-feed type
   (the autodiscovery convention), in document order with comment feeds demoted;
3. feed-shaped ``<a href>`` links on that page;
4. platform conventions: the page URL with ``.rss``/``.atom`` appended
   (Reddit, Mastodon, Discourse, Lobsters, GitHub) and the paths publishing
   platforms serve feeds on (``feed``, ``rss``, ``feed.xml``, ``atom.xml``,
   ``rss.xml``, ``index.xml``, ``feed.json``) inside the page's own directory.
   This is what resolves a site whose home page sits behind a bot wall while
   its feed does not; bot walls and challenges are never bypassed.

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

from .hfeed import hfeed_document
from .models import FeedDocument
from .parser import FeedEmptyError, FeedParseError, parse_feed_bytes
from .transport import FeedHttpResponse, FeedTransportError, validate_feed_url


MAX_DISCOVERY_FETCHES = 10
DISCOVERY_DEADLINE_SECONDS = 20.0
MAX_HTML_PAGES = 2
_MAX_HTML_SCAN_CHARS = 1_500_000
_HTML_CHUNK_CHARS = 64 * 1024
_MAX_ADVERTISED = 8
_MAX_ANCHORS = 8

# Paths common publishing platforms serve feeds on (WordPress, Substack and
# Ghost style ``feed``/``rss``; Jekyll ``feed.xml``; static ``atom.xml`` and
# ``rss.xml``; Hugo ``index.xml``; JSON Feed ``feed.json``), and the suffixes
# platforms append to a page URL for its feed. Conventions, not site knowledge.
CONVENTIONAL_FEED_NAMES = ("feed", "rss", "feed.xml", "atom.xml", "rss.xml", "index.xml", "feed.json")
CONVENTIONAL_FEED_SUFFIXES = (".rss", ".atom")
# A final path segment with one of these extensions is a document, not a
# directory (``@tim.oreilly`` or ``v2.0`` are directories).
_DOCUMENT_EXTENSIONS = frozenset({
    "html", "htm", "xhtml", "shtml", "php", "asp", "aspx", "jsp", "cgi",
    "xml", "rss", "atom", "rdf", "json",
})

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
    "application/feed+json",
    "application/jf2feed+json",
    "text/mf2+html",
})
# Types that are sometimes a feed: accepted when the title/href says so (JSON
# Feed 1.0 was advertised as ``application/json`` titled "JSON Feed").
_GENERIC_TYPES = frozenset({"application/xml", "text/xml", "application/json"})
_FEED_WORD_RE = re.compile(r"rss|atom|feed", re.IGNORECASE)
_FEED_PATH_SUFFIXES = (
    ".rss", ".rdf", ".atom", "/feed", "/feed/", "/rss", "/rss/", "/atom", "/atom/",
    "rss.xml", "atom.xml", "feed.xml", "feed.json", "/feeds/posts/default",
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


def _path_key(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    return (parsed.hostname or "").casefold(), parsed.path.rstrip("/").casefold()


def _looks_like_feed_link(url: str, *, page_url: str = "") -> bool:
    parsed = urlparse(url)
    path = parsed.path.casefold()
    host = (parsed.hostname or "").casefold()
    if "comment" in path:
        return False
    if page_url and _path_key(url) == _path_key(page_url):
        # A link back to this page (another language, sort or page number) is
        # the page, not a feed, however feed-like the page's own path is; only
        # an explicit feed query (``?format=rss``) makes it one.
        return bool(_FEED_QUERY_RE.search(parsed.query))
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
            if (url and _looks_like_feed_link(url, page_url=self.page_url)
                    and all(_path_key(url) != _path_key(existing) for existing in self.anchors)):
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
        if "oembed" in media_type:
            return
        if not rel & {"alternate", "feed"}:
            return
        if media_type in _FEED_TYPES:
            pass
        elif media_type in _GENERIC_TYPES or (not media_type and "feed" in rel):
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


def _under_page(url: str, page_url: str) -> bool:
    """``url``'s path continues a non-root page path (``/notes`` -> ``/notes/rss``, ``/@a.rss``)."""
    page_path = urlparse(page_url).path.rstrip("/").casefold()
    if not page_path:
        return False
    path = urlparse(url).path.casefold()
    return path.startswith(page_path) and path[len(page_path):len(page_path) + 1] in {"/", "."}


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
    # A section page's own feed (``/notes`` -> ``/notes/rss``, a category's
    # ``/category/x/feed/``) outranks the site-wide feed advertised first;
    # otherwise document order. Comment feeds always go last.
    ordered = [url for comment, url in collector.advertised if not comment and _under_page(url, page_url)]
    ordered += [url for comment, url in collector.advertised if not comment and url not in ordered]
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
    """Platform-convention feed URLs for a page, most specific first.

    ``https://example.com/r/news`` gives ``/r/news.rss`` and ``/r/news.atom``
    (the page-suffix convention), then ``/r/news/feed`` and the other names
    inside that directory. ``https://example.com`` gives ``/feed`` and so on.
    Never walks up to the site root from a sub-path, so an address on a shared
    platform host cannot resolve to that platform's own site-wide feed.
    """
    try:
        parsed = urlparse(validate_feed_url(page_url))
    except ValueError:
        return ()
    path = parsed.path or "/"
    document = False
    if not path.endswith("/"):
        leaf = path.rsplit("/", 1)[-1]
        document = "." in leaf and leaf.rsplit(".", 1)[-1].casefold() in _DOCUMENT_EXTENSIONS
        path = path[: len(path) - len(leaf)] if document else path + "/"
    candidates: list[FeedCandidate] = []
    stem = path.rstrip("/")
    if stem and not document:
        candidates += [
            FeedCandidate(
                urlunparse(parsed._replace(path=stem + suffix, params="", query="", fragment="")),
                "conventional",
            )
            for suffix in CONVENTIONAL_FEED_SUFFIXES
        ]
    base = urlunparse(parsed._replace(path=path, params="", query="", fragment=""))
    candidates += [FeedCandidate(urljoin(base, name), "conventional") for name in CONVENTIONAL_FEED_NAMES]
    return tuple(candidates)


def _is_html(response: FeedHttpResponse) -> bool:
    head = response.payload[:4096].removeprefix(_UTF8_BOM)
    if _FEED_HEAD_RE.match(head):
        return False
    if _HTML_HEAD_RE.match(head):
        return True
    media_type = response.content_type.casefold().split(";", 1)[0].strip()
    return media_type in {"text/html", "application/xhtml+xml"}


DocumentAdapter = Callable[[bytes, str, int], "FeedDocument | None"]


def _examine(
    response: FeedHttpResponse, *, url: str, max_items: int,
    document_adapter: DocumentAdapter | None = None,
) -> tuple[FeedDocument | None, list[FeedCandidate]]:
    """What a fetched response offers: a feed, or the candidates a page points at.

    A feed document (RSS, Atom, JSON Feed, JF2) is parsed; ``FeedEmptyError``
    propagates for a real but empty feed. A page yields its advertised and
    linked candidates; a page that declares no feed but marks its own posts up
    as an IndieWeb h-feed is itself the feed. Obvious HTML is never handed to
    the feed parser. A caller's ``document_adapter`` may read a structured
    payload that is not a feed (an image-listing JSON API, for example); it
    returns ``None`` when the payload is not for it.
    """
    if not _is_html(response):
        try:
            document = parse_feed_bytes(
                response.payload, source_url=response.final_url or url, max_items=max_items)
            return document, []
        except FeedEmptyError:
            raise
        except FeedParseError:
            if document_adapter is not None:
                adapted = document_adapter(response.payload, response.final_url or url, max_items)
                if adapted is not None:
                    return adapted, []
            if b"<html" not in response.payload[:8192].lower():
                return None, []
    page_url = response.final_url or url
    candidates = list(advertised_feed_candidates(
        response.payload, page_url=page_url,
        content_type=response.content_type, link_header=response.link_header,
    ))
    if not any(candidate.via in {"link_header", "advertised"} for candidate in candidates):
        document = hfeed_document(response.payload, page_url=page_url,
                                  content_type=response.content_type, max_items=max_items)
        if document is not None:
            return document, []
    return None, candidates


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
    document_adapter: DocumentAdapter | None = None,
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
        document, found = _examine(response, url=primary, max_items=max_items,
                                   document_adapter=document_adapter)
        if document is not None:
            return FeedResolution(response, document, primary, "direct", attempts)
        html_pages += 1
        page_url = response.final_url or primary
        queue.extend(found)

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
            document, found = _examine(response, url=candidate.url, max_items=max_items,
                                       document_adapter=document_adapter)
        except FeedEmptyError:
            continue
        if document is not None:
            return FeedResolution(response, document, candidate.url, candidate.via, attempts)
        if candidate.via == "seed":
            queue.extend(conventional_feed_candidates(response.final_url or candidate.url))
        if found and html_pages < MAX_HTML_PAGES:
            html_pages += 1
            # A page's own advertised feeds outrank the remaining guesses.
            queue[0:0] = [item for item in found if _visit_key(item.url) not in fetched]

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
