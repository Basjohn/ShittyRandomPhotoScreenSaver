"""The one magnet-link admission rule (stdlib only; the secure helper shares it).

A magnet link opens through the operating system's registered handler (the
user's torrent client), which receives it inside a quoted command line. So only
a real BitTorrent magnet is admitted: a v1 (``urn:btih:``, 40 hex or 32 base32)
or v2 (``urn:btmh:1220`` + 64 hex) info hash, plain RFC 3986 characters with
well-formed ``%XX`` escapes and nothing else (no spaces, quotes, angle brackets,
backslashes, carets, backticks, braces or pipes), at most 4096 characters.

This is a single anchored regex match plus one query split. Presentation runs
it once per published row, never on hover; the product action and the helper
repeat it once per click.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlsplit

MAX_MAGNET_LENGTH = 4096

_URI_TEXT = re.compile(r"magnet:\?(?:[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=]|%[0-9A-Fa-f]{2})+\Z", re.IGNORECASE)
_INFO_HASH = re.compile(
    r"urn:(?:btih:(?:[0-9a-f]{40}|[a-z2-7]{32})|btmh:1220[0-9a-f]{64})\Z",
    re.IGNORECASE,
)


def admitted_magnet_uri(value: object) -> str:
    """``value`` when it is an admissible BitTorrent magnet link, else ``""``."""

    text = str(value or "").strip()
    if not text or len(text) > MAX_MAGNET_LENGTH or not _URI_TEXT.match(text):
        return ""
    parts = urlsplit(text)
    if parts.netloc or parts.path or parts.fragment:
        return ""
    try:
        params = parse_qsl(parts.query, keep_blank_values=True, max_num_fields=200)
    except ValueError:
        return ""
    has_info_hash = any(
        (key == "xt" or key.startswith("xt.")) and _INFO_HASH.match(value)
        for key, value in params
    )
    return text if has_info_hash else ""


__all__ = ["MAX_MAGNET_LENGTH", "admitted_magnet_uri"]
