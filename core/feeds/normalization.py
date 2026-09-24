"""Pure feed text, URL and identity normalization helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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


_ORDINAL_DATE_RE = re.compile(r"^(\d{4})-(\d{3})(?!\d)(.*)$")
_SENTENCE_END_RE = re.compile(r"[.!?…](?=\s|$)")
_DERIVED_TITLE_LIMIT = 140


def title_from_text(text: str, *, limit: int = _DERIVED_TITLE_LIMIT) -> tuple[str, str]:
    """A title-less post's title from its own text, and the text left over.

    Whole sentences while they fit (so a very short opener is not a title on
    its own); a first sentence that is too long is cut at a word boundary with
    an ellipsis and the remainder continues from the cut. Presentation shows
    title then summary, so the two never repeat each other.
    """
    clean = _WS_RE.sub(" ", str(text or "")).strip()
    if not clean:
        return "", ""
    end = 0
    for match in _SENTENCE_END_RE.finditer(clean):
        if match.end() > limit:
            break
        end = match.end()
        if end >= 24:
            break
    if end:
        return clean[:end].strip(), clean[end:].strip()
    if len(clean) <= limit:
        return clean, ""
    cut = clean[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-") or clean[:limit]
    return cut + "…", "…" + clean[len(cut):].strip()


def entry_title_and_summary(raw_title: object, *, summary: str, action_url: str) -> tuple[str, str]:
    """An entry's display title and summary, whatever the feed format.

    An authored title always wins. A title-less entry (Mastodon, Bluesky,
    micro.blog and IndieWeb notes; JSON Feed ``content_text`` posts) takes its
    title from its own text; a magnet's ``dn=`` name still comes first, and a
    URL-derived title is the last resort.
    """
    title = plain_text(raw_title, limit=300)
    if title:
        return title, summary
    if summary and urlparse(action_url or "").scheme.casefold() != "magnet":
        derived, rest = title_from_text(summary)
        if derived:
            return derived, rest
    return display_title(None, fallback_url=action_url), summary


def iso_timestamp(value: object) -> int | None:
    """RFC 3339 / ISO 8601 (or a stray RFC 822) date -> UTC epoch seconds."""
    text = str(value or "").strip()
    if not text or len(text) > 64:
        return None
    parsed: datetime | None = None
    candidate = text[:-1] + "+00:00" if text[-1:] in {"Z", "z"} else text
    ordinal = _ORDINAL_DATE_RE.match(candidate)
    if ordinal:
        # ISO 8601 ordinal dates (``2026-263``) are valid microformats dates.
        try:
            day = datetime.strptime(ordinal.group(1) + ordinal.group(2), "%Y%j").date()
        except ValueError:
            return None
        candidate = day.isoformat() + ordinal.group(3)
    if " " in candidate and "T" not in candidate:
        candidate = candidate.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError):
            return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        result = int(parsed.timestamp())
    except (OverflowError, OSError, ValueError):
        return None
    return result if 0 < result < 4_102_444_800 else None


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
