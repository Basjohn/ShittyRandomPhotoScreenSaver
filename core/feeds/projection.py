"""Pure feed snapshot -> presentation projection.

This module owns *presentation policy*, not acquisition.  In particular, it
never downloads artwork and it never exposes remote image URLs as QML image
sources.  Callers may provide already-validated local artwork by item id.

Grid generations are deliberately all-or-none for imagery: if one visible row
lacks a validated local source, the whole generation falls back to the coherent
text-grid presentation.  List mode may use sparse thumbnails because its row
geometry is authored to tolerate them; Compact is text-only by contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from core.presentation_image_coherence import coherent_image_sources

from .models import FeedEnclosure, FeedItem, FeedSnapshot, FeedViewMode


FeedImageMode = Literal["none", "sparse", "complete"]


@dataclass(frozen=True)
class FeedDisplayRow:
    item_id: str
    title: str
    summary: str
    author: str
    action_url: str
    published_at: int | None
    image_source: str = ""
    image_candidate_url: str = ""
    enclosures: tuple[FeedEnclosure, ...] = ()


@dataclass(frozen=True)
class FeedDisplay:
    title: str
    home_url: str
    format: str
    view_mode: FeedViewMode
    rows: tuple[FeedDisplayRow, ...]
    image_mode: FeedImageMode
    omitted_count: int = 0

    @property
    def has_complete_imagery(self) -> bool:
        return bool(self.rows) and self.image_mode == "complete"


def preferred_image_candidate(item: FeedItem) -> str:
    """Return the best feed-advertised image URL for later cache warming.

    Declared dimensions are preferred when available, then richer Media RSS /
    content relations over generic HTML discovery.  This is only candidate
    selection: presentation still requires a validated *local* artwork source.
    """
    if not item.images:
        return ""
    relation_rank = {
        "media": 5,
        "content": 4,
        "enclosure": 3,
        "thumbnail": 2,
        "html": 1,
        "feed": 0,
    }

    def key(candidate):
        width = candidate.width or 0
        height = candidate.height or 0
        pixels = width * height
        # Avoid preferring declared tracking-pixel-sized assets merely because
        # they happened to appear before a usable image.
        usable_declared = int(width >= 120 and height >= 80)
        return (
            usable_declared,
            pixels,
            relation_rank.get(candidate.relation, 0),
        )

    return max(item.images, key=key).url


def project_feed(
    snapshot: FeedSnapshot,
    *,
    view_mode: FeedViewMode,
    item_limit: int,
    show_images: bool = True,
    local_artwork_by_item: Mapping[str, str] | None = None,
) -> FeedDisplay:
    """Project one immutable feed snapshot without mutating source state."""
    if view_mode not in {"list", "grid", "compact"}:
        raise ValueError(f"unsupported feed view mode: {view_mode!r}")
    limit = max(1, min(100, int(item_limit)))
    visible = snapshot.document.items[:limit]
    local = local_artwork_by_item or {}

    candidates = tuple(preferred_image_candidate(item) for item in visible)
    requested_local = tuple(str(local.get(item.item_id, "") or "").strip() for item in visible)

    if not show_images or view_mode == "compact":
        image_sources = ("",) * len(visible)
        image_mode: FeedImageMode = "none"
    elif view_mode == "grid":
        image_sources = coherent_image_sources(requested_local, enabled=True)
        image_mode = "complete" if image_sources and all(image_sources) else "none"
    else:
        # List rows are independently authored and do not leave empty image
        # holes when a thumbnail is absent, so sparse local thumbnails are OK.
        image_sources = requested_local
        if image_sources and all(image_sources):
            image_mode = "complete"
        elif any(image_sources):
            image_mode = "sparse"
        else:
            image_mode = "none"

    rows = tuple(
        FeedDisplayRow(
            item_id=item.item_id,
            title=item.title,
            summary=item.summary,
            author=item.author,
            action_url=item.action_url,
            published_at=item.published_at,
            image_source=image_sources[index],
            image_candidate_url=candidates[index],
            enclosures=item.enclosures,
        )
        for index, item in enumerate(visible)
    )
    return FeedDisplay(
        title=snapshot.document.title,
        home_url=snapshot.document.home_url,
        format=snapshot.document.format,
        view_mode=view_mode,
        rows=rows,
        image_mode=image_mode,
        omitted_count=max(0, len(snapshot.document.items) - len(visible)),
    )
