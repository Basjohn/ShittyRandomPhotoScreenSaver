"""IndieWeb h-feed pages (microformats2) -> JF2 -> the shared feed model.

An IndieWeb site can publish its posts as ordinary HTML marked up with
microformats2 (``h-feed`` / ``h-entry``) instead of, or besides, RSS/Atom. This
module reads that markup into a JF2 feed, which ``core.feeds.json_feed`` maps
into ``FeedDocument`` exactly like a JSON JF2 document.

Only the microformats2 subset a feed needs is implemented: ``h-entry`` roots,
``p-``/``u-``/``dt-``/``e-`` properties (nested microformats keep their own
properties and give an entry property their name), ``<base href>``, and the
implied ``url`` of a linked entry. Legacy mf1 ``hentry`` is deliberately not
read: many themes carry it on ordinary article markup, and those sites
advertise RSS anyway. The build is bounded in characters and elements.
"""
from __future__ import annotations

from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import urljoin

from .models import FeedDocument
from .normalization import normalized_action_url

_MAX_HTML_CHARS = 1_500_000
_MAX_ELEMENTS = 60_000
_MAX_TEXT = 8000
_VOID = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "param", "source", "track", "wbr",
})
_OPAQUE = frozenset({"script", "style", "template"})
_ROOT_RE = re.compile(r"^h-(?:[a-z0-9]+-)?[a-z]+(?:-[a-z]+)*$")
_PROPERTY_RE = re.compile(r"^(p|u|dt|e)-((?:[a-z0-9]+-)?[a-z]+(?:-[a-z]+)*)$")
_WS_RE = re.compile(r"\s+")
_CHARSET_RE = re.compile(r"charset=([\w.:-]+)", re.IGNORECASE)


class _Element:
    __slots__ = ("tag", "attrs", "classes", "children")

    def __init__(self, tag: str, attrs: dict[str, str]) -> None:
        self.tag = tag
        self.attrs = attrs
        self.classes = attrs.get("class", "").split()
        self.children: list[_Element | str] = []

    @property
    def is_root(self) -> bool:
        return any(_ROOT_RE.match(name) for name in self.classes)

    def properties(self) -> list[tuple[str, str]]:
        return [match.groups() for match in map(_PROPERTY_RE.match, self.classes) if match]  # type: ignore[misc]

    def elements(self) -> list["_Element"]:
        return [child for child in self.children if isinstance(child, _Element)]

    def text(self) -> str:
        chunks: list[str] = []
        stack: list[_Element | str] = [self]
        total = 0
        while stack and total < _MAX_TEXT:
            node = stack.pop()
            if isinstance(node, str):
                chunks.append(node)
                total += len(node)
            elif node.tag == "img":
                chunks.append(" " + node.attrs.get("alt", "") + " ")
            elif node.tag not in _OPAQUE:
                if node.tag in {"p", "br", "li", "div"}:
                    chunks.append(" ")
                stack.extend(reversed(node.children))
        return _WS_RE.sub(" ", "".join(chunks)).strip()[:_MAX_TEXT]


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.document = _Element("#document", {})
        self.stack = [self.document]
        self.count = 0
        self.opaque = 0
        self.base_href = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        kind = tag.casefold()
        mapping = {str(key).casefold(): str(value or "") for key, value in attrs}
        if kind == "base" and not self.base_href:
            self.base_href = mapping.get("href", "")
        if self.opaque or self.count >= _MAX_ELEMENTS:
            if kind in _OPAQUE and kind not in _VOID:
                self.opaque += 1
            return
        self.count += 1
        element = _Element(kind, mapping)
        self.stack[-1].children.append(element)
        if kind in _OPAQUE:
            self.opaque += 1
        if kind not in _VOID:
            self.stack.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        depth = len(self.stack)
        self.handle_starttag(tag, attrs)
        if len(self.stack) > depth:
            self.stack.pop()
            if tag.casefold() in _OPAQUE and self.opaque:
                self.opaque -= 1

    def handle_endtag(self, tag: str) -> None:
        kind = tag.casefold()
        if kind in _OPAQUE and self.opaque:
            self.opaque -= 1
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == kind:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if not self.opaque and data:
            self.stack[-1].children.append(data)


def _url(value: str, base_url: str) -> str:
    try:
        return urljoin(base_url, value.strip()) if value.strip() else ""
    except ValueError:
        return ""


def _root_name(element: _Element) -> str:
    value = _first(_collect(element), "name", base_url="")
    return value if isinstance(value, str) and value else element.text()


_VCP_DATE_RE = re.compile(r"^\d{4}-(?:\d{2}-\d{2}|\d{3})$")
_VCP_TIME_RE = re.compile(r"^\d{1,2}(?::\d{2}){0,2}(?:\.\d+)?(?:[aApP]\.?[mM]\.?)?\s*(?:Z|[+-]\d{2}:?\d{2})?$")
_VCP_ZONE_RE = re.compile(r"^(?:Z|[+-]\d{2}:?\d{2})$")


def _value_class_date(element: _Element) -> str:
    """The microformats value-class pattern: a date split across ``.value`` children."""
    parts: list[str] = []
    stack = list(reversed(element.elements()))
    while stack and len(parts) < 6:
        node = stack.pop()
        if "value" in node.classes or "value-title" in node.classes:
            attrs = node.attrs
            if "value-title" in node.classes:
                parts.append(attrs.get("title", "").strip())
            elif node.tag in {"time", "ins", "del"} and attrs.get("datetime"):
                parts.append(attrs["datetime"].strip())
            elif node.tag == "abbr" and attrs.get("title"):
                parts.append(attrs["title"].strip())
            elif node.tag in {"data", "input"} and attrs.get("value"):
                parts.append(attrs["value"].strip())
            else:
                parts.append(node.text())
        elif not node.is_root:
            stack.extend(reversed(node.elements()))
    date = next((part for part in parts if _VCP_DATE_RE.match(part)), "")
    clock = next((part for part in parts if _VCP_TIME_RE.match(part)), "")
    zone = next((part for part in parts if _VCP_ZONE_RE.match(part)), "")
    if not date:
        return next((part for part in parts if part[:4].isdigit()), "")
    if not clock:
        return date
    if zone and zone not in clock:
        clock += zone
    return f"{date}T{clock}"


def _value(prefix: str, element: _Element, base_url: str) -> Any:
    attrs = element.attrs
    if prefix == "e":
        return element
    if prefix == "p" and element.is_root:
        return _root_name(element)
    if prefix == "u":
        for tags, attr in (({"a", "area", "link"}, "href"),
                           ({"img", "audio", "video", "source", "iframe"}, "src"),
                           ({"object"}, "data")):
            if element.tag in tags and attrs.get(attr):
                return _url(attrs[attr], base_url)
        if element.tag == "img" and attrs.get("srcset"):
            return _url(attrs["srcset"].split(",")[0].split()[0], base_url)
    if prefix == "dt":
        split = _value_class_date(element)
        if split:
            return split
        for tags, attr in (({"time", "ins", "del"}, "datetime"), ({"abbr"}, "title"),
                           ({"data", "input"}, "value")):
            if element.tag in tags and attrs.get(attr):
                return attrs[attr].strip()
    if prefix == "p":
        for tags, attr in (({"abbr", "link"}, "title"), ({"data", "input"}, "value"),
                           ({"img", "area"}, "alt")):
            if element.tag in tags and attrs.get(attr):
                return attrs[attr].strip()
    text = element.text()
    return _url(text, base_url) if prefix == "u" and text else text


_Found = dict[str, list[tuple[str, _Element]]]


def _collect(root: _Element) -> _Found:
    """A microformat's own properties (nested microformats keep theirs)."""
    found: _Found = {}
    stack = list(reversed(root.elements()))
    while stack:
        element = stack.pop()
        for prefix, name in element.properties():
            found.setdefault(name, []).append((prefix, element))
        if not element.is_root:
            stack.extend(reversed(element.elements()))
    return found


def _first(found: _Found, name: str, *, base_url: str) -> Any:
    rows = found.get(name) or []
    return _value(*rows[0], base_url) if rows else ""


def _all(found: _Found, name: str, *, base_url: str) -> list[Any]:
    return [_value(prefix, element, base_url) for prefix, element in (found.get(name) or [])[:8]]


def _person(found: _Found, name: str, *, base_url: str) -> str:
    """An author's display name: a nested h-card's name, never its URL."""
    rows = found.get(name) or []
    if not rows:
        return ""
    prefix, element = rows[0]
    if element.is_root:
        return _root_name(element)
    value = _value(prefix, element, base_url)
    return value if isinstance(value, str) and "://" not in value else ""


def _content_images(element: _Element, base_url: str) -> list[str]:
    urls: list[str] = []
    stack: list[_Element] = [element]
    while stack and len(urls) < 8:
        node = stack.pop()
        if node.tag == "img":
            src = node.attrs.get("src") or node.attrs.get("data-src") or ""
            url = _url(src, base_url)
            if url and url not in urls:
                urls.append(url)
        stack.extend(reversed(node.elements()))
    return urls


def _entry(root: _Element, *, base_url: str) -> dict[str, Any]:
    found = _collect(root)

    def first(name: str) -> Any:
        return _first(found, name, base_url=base_url)

    def text(value: Any) -> str:
        return value.text() if isinstance(value, _Element) else str(value or "")

    content = first("content")
    content_text = text(content)
    name = text(first("name"))
    # A note repeats its content as its name (explicit ``p-name e-content`` or
    # the implied name); it has no authored title.
    squashed = _WS_RE.sub(" ", name).strip()
    if squashed and content_text and (content_text.startswith(squashed) or squashed.startswith(content_text[:200])):
        name = ""
    url = text(first("url"))
    if not url:
        if root.tag in {"a", "area"} and root.attrs.get("href"):
            url = _url(root.attrs["href"], base_url)
        else:
            links = [child for child in root.elements() if child.tag in {"a", "area"} and not child.is_root]
            if len(links) == 1 and links[0].attrs.get("href"):
                url = _url(links[0].attrs["href"], base_url)
    photos = [value for key in ("featured", "photo")
              for value in _all(found, key, base_url=base_url) if isinstance(value, str)]
    if isinstance(content, _Element):
        photos += _content_images(content, base_url)
    return {
        "type": "entry",
        "name": name,
        "url": url,
        "uid": text(first("uid")),
        "published": text(first("published")),
        "updated": text(first("updated")),
        "summary": text(first("summary")),
        "content": {"text": content_text},
        "photo": photos,
        "author": _person(found, "author", base_url=base_url),
    }


def _find(element: _Element, class_name: str, *, limit: int) -> list[_Element]:
    """Outermost elements carrying ``class_name`` (an h-entry inside an h-entry is its reply)."""
    result: list[_Element] = []
    stack = [element]
    while stack and len(result) < limit:
        node = stack.pop()
        if class_name in node.classes:
            result.append(node)
            continue
        stack.extend(reversed(node.elements()))
    return result


def _page_title(document: _Element) -> str:
    stack = [document]
    while stack:
        node = stack.pop()
        if node.tag == "title":
            return node.text()
        if node.tag == "body":
            continue
        stack.extend(reversed(node.elements()))
    return ""


def page_has_entries(payload: bytes) -> bool:
    """Cheap pre-check: only a page naming ``h-entry`` is worth building a tree for."""
    return b"h-entry" in payload[: _MAX_HTML_CHARS]


def hfeed_document(payload: bytes, *, page_url: str, content_type: str = "", max_items: int = 50) -> FeedDocument | None:
    """The page's h-feed as a ``FeedDocument``, or ``None`` when it has no h-entries."""
    from .json_feed import jf2_feed_document
    from .parser import FeedParseError

    if not page_has_entries(payload):
        return None
    charset = "utf-8"
    match = _CHARSET_RE.search(content_type or "")
    if match:
        charset = match.group(1)
    try:
        text = bytes(payload[:_MAX_HTML_CHARS]).decode(charset, errors="replace")
    except LookupError:
        text = bytes(payload[:_MAX_HTML_CHARS]).decode("utf-8", errors="replace")
    builder = _TreeBuilder()
    try:
        builder.feed(text)
        builder.close()
    except (ValueError, AssertionError):
        return None
    document = builder.document
    base_url = _url(builder.base_href, page_url) if builder.base_href else page_url
    limit = max(1, min(200, int(max_items)))
    feeds = _find(document, "h-feed", limit=1)
    scope = feeds[0] if feeds else document
    entries = _find(scope, "h-entry", limit=limit)
    if not entries:
        return None
    feed_props = _collect(feeds[0]) if feeds else {}
    feed_name = _first(feed_props, "name", base_url=base_url)
    jf2 = {
        "type": "feed",
        "name": (feed_name if isinstance(feed_name, str) else "") or _page_title(document),
        "url": normalized_action_url(page_url),
        "author": _person(feed_props, "author", base_url=base_url),
        "children": [_entry(entry, base_url=base_url) for entry in entries],
    }
    try:
        return jf2_feed_document(jf2, source_url=page_url, max_items=limit, fmt="h-feed")
    except FeedParseError:
        return None


__all__ = ["hfeed_document", "page_has_entries"]
