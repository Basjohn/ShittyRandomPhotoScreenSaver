"""Pure feed text, URL and identity normalization helpers."""
from __future__ import annotations

import hashlib
import html
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, unquote_plus, urljoin, urlparse


_ALLOWED_ACTION_SCHEMES = frozenset({"http", "https", "magnet"})
_ALLOWED_MEDIA_SCHEMES = frozenset({"http", "https"})
_WS_RE = re.compile(r"\s+")
_MACHINE_SEPARATORS = re.compile(r"[._]+")


class _PlainText(HTMLParser):
    def __init__(self, limit: int) -> None:
        super().__init__(convert_charrefs=True)
        self.limit = max(0, int(limit))
        self.parts: list[str] = []
        self.length = 0
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.casefold()
        if lowered in {"script", "style", "iframe", "svg"}:
            self.hidden += 1
        elif not self.hidden and lowered in {"p", "br", "li", "div", "h1", "h2", "h3"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.casefold()
        if lowered in {"script", "style", "iframe", "svg"} and self.hidden:
            self.hidden -= 1
        elif not self.hidden and lowered in {"p", "br", "li", "div", "h1", "h2", "h3"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self.hidden or self.length >= self.limit:
            return
        fragment = str(data)[: self.limit - self.length]
        self.parts.append(fragment)
        self.length += len(fragment)


def plain_text(value: object, *, limit: int = 1200) -> str:
    text = str(value or "")
    if not text:
        return ""
    parser = _PlainText(limit)
    try:
        parser.feed(text[: max(limit * 8, 4096)])
        result = _WS_RE.sub(" ", html.unescape("".join(parser.parts))).strip()
    except (ValueError, AssertionError):
        result = _WS_RE.sub(" ", re.sub(r"<[^>]+>", " ", html.unescape(text))).strip()
    return "".join(ch for ch in result[:limit] if ch.isprintable()).strip()


def normalized_action_url(value: object, *, base_url: str = "") -> str:
    text = str(value or "").strip()
    if not text or len(text) > 8192:
        return ""
    if base_url:
        try:
            text = urljoin(str(base_url), text)
        except ValueError:
            return ""
    try:
        parsed = urlparse(text)
    except ValueError:
        return ""
    scheme = parsed.scheme.casefold()
    if scheme not in _ALLOWED_ACTION_SCHEMES:
        return ""
    if scheme in {"http", "https"} and not parsed.hostname:
        return ""
    return text


def normalized_media_url(value: object, *, base_url: str = "") -> str:
    text = str(value or "").strip()
    if not text or len(text) > 4096:
        return ""
    if base_url:
        try:
            text = urljoin(str(base_url), text)
        except ValueError:
            return ""
    try:
        parsed = urlparse(text)
    except ValueError:
        return ""
    if parsed.scheme.casefold() not in _ALLOWED_MEDIA_SCHEMES or not parsed.hostname:
        return ""
    return text


def endpoint_fingerprint(url: str) -> str:
    normalized = str(url or "").strip()
    return hashlib.sha256(normalized.encode("utf-8", errors="strict")).hexdigest()


def safe_cache_fragment(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip()).strip("._")
    if not text:
        raise ValueError("cache key is empty")
    return text[:96]


def _derived_title_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme.casefold() == "magnet":
        try:
            display_names = parse_qs(parsed.query, keep_blank_values=False).get("dn", ())
        except ValueError:
            display_names = ()
        candidate = str(display_names[0]) if display_names else ""
    else:
        candidate = unquote_plus(parsed.path.rsplit("/", 1)[-1]) or (parsed.hostname or "")
    if candidate:
        candidate = unquote(candidate)
        machineish = candidate.count(".") + candidate.count("_") >= 2
        if machineish:
            candidate = _MACHINE_SEPARATORS.sub(" ", candidate)
        candidate = _WS_RE.sub(" ", candidate).strip(" -_")
    return candidate[:300]


def display_title(value: object, *, fallback_url: str = "") -> str:
    title = plain_text(value, limit=300)
    if title:
        return title
    url = normalized_action_url(fallback_url)
    if not url:
        return "Untitled"
    return _derived_title_from_url(url) or "Untitled"


def stable_item_id(*, explicit_id: object, action_url: str, title: str, published_at: int | None) -> str:
    explicit = str(explicit_id or "").strip()
    if explicit and len(explicit) <= 2048:
        basis = f"id\0{explicit}"
    elif action_url:
        basis = f"url\0{action_url}"
    else:
        basis = f"fallback\0{title}\0{published_at or 0}"
    return hashlib.sha256(basis.encode("utf-8", errors="replace")).hexdigest()


def redacted_url_for_log(url: str) -> str:
    """Return scheme/host/path only so tokenized feed query strings never hit logs."""
    try:
        parsed = urlparse(str(url or ""))
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        return f"{parsed.scheme}://{host}{port}{parsed.path or '/'}"
    except (ValueError, TypeError):
        return "<invalid-feed-url>"
