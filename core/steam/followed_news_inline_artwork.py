"""Bounded Steam-news inline images; no arbitrary provider URLs or render-time IO.

Steam's {STEAM_CLAN_IMAGE}/group/hash.png macro is public image content, not
article link authority. Store only validated relative image references in news
snapshots; construct allowlisted CDN URLs only inside the source worker.
"""
from __future__ import annotations

import re
from pathlib import Path

# Bounded path is persisted, not a provider-controlled URL or arbitrary HTML.
_IMAGE_PATH = r"[1-9][0-9]{0,11}/[A-Za-z0-9_-]{8,128}\.(?:png|jpe?g|webp)"
_IMAGE_REF = re.compile(rf"\A{_IMAGE_PATH}\Z", re.I)
_CLAN_IMAGE = re.compile(rf"\{{STEAM_CLAN_IMAGE\}}\s*/({_IMAGE_PATH})(?:\?[^\s\]<]{{0,128}})?", re.I)
# Some Steam news articles supply a complete image URL, rather than the macro.
_ABSOLUTE_CLAN_IMAGE = re.compile(
    rf"https://clan\.(?:akamai|cloudflare)\.steamstatic\.com/images/({_IMAGE_PATH})(?:\?[^\s\]<]{{0,128}})?", re.I
)
# Steam announcements sometimes append subsequent clan-image paths without
# repeating {STEAM_CLAN_IMAGE}; accept only a standalone slash-prefixed path.
_STANDALONE_IMAGE = re.compile(rf"(?<!\S)/({_IMAGE_PATH})(?:\?[^\s\]<]{{0,128}})?", re.I)
MAX_INLINE_IMAGES_PER_STORY = 3
MAX_INLINE_IMAGE_FETCHES_PER_REFRESH = 3
INLINE_IMAGE_CACHE_MAX_FILES = 96
INLINE_IMAGE_CACHE_MAX_BYTES = 64 * 1024 * 1024


def validated_inline_ref(value: object) -> str:
    """Safe, URL-free cache representation. No traversal, query or credentials."""
    return value if type(value) is str and _IMAGE_REF.fullmatch(value) else ""


def news_inline_refs(contents: object) -> tuple[str, ...]:
    if type(contents) is not str or not contents:
        return ()
    text = contents[:8192]
    matches = sorted((*_CLAN_IMAGE.finditer(text), *_ABSOLUTE_CLAN_IMAGE.finditer(text),
                      *_STANDALONE_IMAGE.finditer(text)),
                     key=lambda match: match.start())
    refs: list[str] = []
    for match in matches:
        ref = validated_inline_ref(match.group(1))
        if ref and ref not in refs:
            refs.append(ref)
            if len(refs) == MAX_INLINE_IMAGES_PER_STORY:
                break
    return tuple(refs)


def inline_image_url(ref: str) -> str:
    return f"https://clan.akamai.steamstatic.com/images/{ref}" if validated_inline_ref(ref) else ""


def prune_inline_image_cache(cache_dir: Path, *, protected: frozenset[Path] = frozenset(),
                             max_files: int = INLINE_IMAGE_CACHE_MAX_FILES,
                             max_bytes: int = INLINE_IMAGE_CACHE_MAX_BYTES) -> int:
    """Worker-only eviction on a successful new image, never on card/resize/read.

    Protect images of the latest source generation. If they alone exceed the
    bound, retain them until the next generation instead of breaking live tiles.
    """
    if not cache_dir.is_dir():
        return 0
    candidates: list[tuple[float, Path, int]] = []
    for path in cache_dir.iterdir():
        if not path.is_file() or path.is_symlink() or path.suffix.lower() not in {'.png', '.jpg', '.webp'}:
            continue
        try:
            st = path.stat()
            candidates.append((st.st_mtime, path, st.st_size))
        except OSError:
            continue
    count, total, removed = len(candidates), sum(item[2] for item in candidates), 0
    for _, path, size in sorted(candidates):
        if count <= max_files and total <= max_bytes:
            break
        if path in protected:
            continue
        try:
            path.unlink()
            count -= 1
            total -= size
            removed += 1
        except OSError:
            continue
    return removed
