"""One-shot feed viability probe shared by Settings and the native probation tool.

The probe uses the exact bounded production transport/parser/discovery but never
reads or writes the runtime last-good cache. It is explicit user/operator work,
not a poller and not a prerequisite for saving a syntactically valid CUSTOM URL.
A site address reports the feed the runtime would resolve it to.
"""
from __future__ import annotations

from dataclasses import dataclass
import time

from .discovery import resolve_feed
from .parser import FeedParseError
from .transport import (
    FeedHttpTransport,
    FeedTransportError,
    normalize_feed_address,
    validate_feed_url,
)


@dataclass(frozen=True)
class FeedProbeResult:
    ok: bool
    format: str = ""
    title: str = ""
    item_count: int = 0
    actionable_count: int = 0
    image_count: int = 0
    newest_unix: int | None = None
    final_url: str = ""
    response_bytes: int = 0
    etag_present: bool = False
    last_modified_present: bool = False
    elapsed_ms: float = 0.0
    failure: str = ""
    # The verified feed URL and how it was found ("direct" when the address
    # itself is the feed; otherwise the discovery route).
    feed_url: str = ""
    via: str = ""

    @property
    def discovered(self) -> bool:
        return bool(self.ok and self.via and self.via != "direct")

    @property
    def actionable_coverage(self) -> float:
        return self.actionable_count / self.item_count if self.item_count else 0.0

    @property
    def image_coverage(self) -> float:
        return self.image_count / self.item_count if self.item_count else 0.0


def probe_feed_url(
    url: str,
    *,
    max_items: int = 50,
    transport: FeedHttpTransport | None = None,
) -> FeedProbeResult:
    """Fetch and parse one URL without mutating durable runtime feed state."""

    started = time.perf_counter()
    client = transport
    owns_client = False
    try:
        try:
            target = validate_feed_url(normalize_feed_address(url))
            if client is None:
                client = FeedHttpTransport()
                owns_client = True
            resolution = resolve_feed(
                client.fetch,
                target,
                max_items=max(1, min(200, int(max_items))),
            )
            response = resolution.response
            document = resolution.document
            if document is None:
                raise FeedParseError("feed probe received no document")
        except (FeedTransportError, FeedParseError, ValueError, OSError) as exc:
            status = getattr(exc, "status_code", None)
            return FeedProbeResult(
                ok=False,
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                failure=f"HTTP {status}" if status else type(exc).__name__,
            )

        items = document.items
        if not items:
            return FeedProbeResult(
                ok=False,
                format=document.format,
                title=document.title,
                final_url=response.final_url or target,
                response_bytes=len(response.payload),
                etag_present=bool(response.etag),
                last_modified_present=bool(response.last_modified),
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                failure="no_usable_items",
            )
        return FeedProbeResult(
            ok=True,
            format=document.format,
            title=document.title,
            item_count=len(items),
            actionable_count=sum(1 for item in items if item.action_url),
            image_count=sum(1 for item in items if item.images),
            newest_unix=max((item.published_at or 0 for item in items), default=0) or None,
            final_url=response.final_url or target,
            response_bytes=len(response.payload),
            etag_present=bool(response.etag),
            last_modified_present=bool(response.last_modified),
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            feed_url=resolution.feed_url,
            via=resolution.via,
        )
    finally:
        if owns_client and client is not None:
            client.close()
