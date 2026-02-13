"""
RSSParser - Feed type detection and entry parsing.

Responsibilities:
    - Detect feed format (RSS/Atom, Flickr JSON, Reddit JSON)
    - Parse feed entries into a normalised list of dicts with image_url + metadata
    - No network I/O - receives raw response data from RSSDownloader
    - No cache interaction - returns parsed entries for coordinator to process
"""
import re
from datetime import datetime
from typing import List, Optional, Any
from urllib.parse import urlparse, urlunparse

from core.logging.logger import get_logger

logger = get_logger(__name__)


class ParsedEntry:
    """Normalised feed entry ready for download."""
    __slots__ = ("image_url", "title", "description", "author", "created_date", "source_url")

    def __init__(
        self,
        image_url: str,
        title: str = "Untitled",
        description: str = "",
        author: str = "",
        created_date: Optional[datetime] = None,
        source_url: str = "",
    ):
        self.image_url = image_url
        self.title = title
        self.description = description
        self.author = author
        self.created_date = created_date
        self.source_url = source_url


class RSSParser:
    """Stateless feed parser. All methods are classmethod / staticmethod."""

    # ------------------------------------------------------------------
    # Feed mode resolution
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_feed_mode(feed_url: str) -> tuple:
        """Determine whether the URL should be fetched as RSS or JSON.

        Returns (request_url, mode, original_url) where mode is 'rss' or 'json'.
        """
        parsed = urlparse(feed_url)
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc
        path = parsed.path or "/"
        query = parsed.query

        if not netloc and path:
            parts = path.split("/", 1)
            candidate_host = parts[0]
            rest = "/" + parts[1] if len(parts) > 1 else "/"
            if "." in candidate_host:
                netloc = candidate_host
                path = rest or "/"

        rebuilt = urlunparse((scheme, netloc, path, "", query, ""))
        lowered_path = path.lower()
        lowered_query = query.lower()

        if "format=json" in lowered_query:
            return rebuilt, "json", feed_url

        if lowered_path.endswith(".json"):
            return rebuilt, "json", feed_url

        lowered_netloc = (netloc or "").lower()
        if "reddit.com" in lowered_netloc and ".rss" in lowered_path:
            json_path = lowered_path.replace(".rss", ".json")
            json_url = urlunparse((scheme, netloc, json_path, "", query, ""))
            return json_url, "json", feed_url

        return rebuilt, "rss", feed_url

    # ------------------------------------------------------------------
    # RSS / Atom parsing (via feedparser)
    # ------------------------------------------------------------------

    @staticmethod
    def parse_rss(feed_data, feed_url: str, max_entries: int = 10) -> List[ParsedEntry]:
        """Parse a feedparser result into ParsedEntry list.

        Args:
            feed_data: Result of ``feedparser.parse(...)``
            feed_url: The originating URL (used as fallback author)
            max_entries: Maximum entries to return
        """
        entries: List[ParsedEntry] = []
        feed_title = feed_data.feed.get("title", "Unknown Feed")

        for entry in feed_data.entries:
            if len(entries) >= max_entries:
                break
            image_url = RSSParser._extract_image_from_rss_entry(entry)
            if not image_url:
                continue

            created = RSSParser._parse_rss_date(entry)
            entries.append(ParsedEntry(
                image_url=image_url,
                title=entry.get("title", "Untitled"),
                description=(entry.get("summary") or "")[:500],
                author=entry.get("author", feed_title),
                created_date=created,
                source_url=feed_url,
            ))

        logger.info(f"[RSS_PARSER] Feed '{feed_title}': {len(feed_data.entries)} entries, {len(entries)} with images")
        return entries

    # ------------------------------------------------------------------
    # JSON parsing (Flickr / Reddit)
    # ------------------------------------------------------------------

    @staticmethod
    def parse_json(data: Any, original_url: str, max_entries: int = 10) -> List[ParsedEntry]:
        """Parse a JSON response (Flickr or Reddit format).

        Returns up to *max_entries* ParsedEntry objects.
        """
        if not isinstance(data, dict):
            logger.warning("[RSS_PARSER] JSON data is not a dict")
            return []

        # Reddit: {kind: 'Listing', data: {children: [...]}}
        if data.get("kind") == "Listing":
            raw = [c.get("data", {}) for c in data.get("data", {}).get("children", []) if isinstance(c, dict)]
            return RSSParser._parse_reddit_entries(raw, original_url, max_entries)

        # Flickr: {items: [...]}
        if "items" in data:
            return RSSParser._parse_flickr_entries(data.get("items", []), original_url, max_entries)

        logger.warning("[RSS_PARSER] Unrecognised JSON structure")
        return []

    # ------------------------------------------------------------------
    # Flickr entry parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_flickr_entries(items: list, feed_url: str, limit: int) -> List[ParsedEntry]:
        entries: List[ParsedEntry] = []
        for item in items:
            if len(entries) >= limit:
                break
            if not isinstance(item, dict):
                continue

            media = item.get("media", {})
            image_url = media.get("m") if isinstance(media, dict) else None
            if not image_url:
                continue

            # Upgrade _m (medium) → _b (large)
            if "_m.jpg" in image_url:
                image_url = image_url.replace("_m.jpg", "_b.jpg")
            elif "_m.png" in image_url:
                image_url = image_url.replace("_m.png", "_b.png")

            created = None
            published = item.get("published")
            if published:
                try:
                    from dateutil import parser as dp
                    created = dp.parse(published)
                except (ValueError, TypeError, ImportError):
                    logger.debug("[RSS_PARSER] Failed to parse date '%s'", published, exc_info=True)

            entries.append(ParsedEntry(
                image_url=image_url,
                title=item.get("title", "Untitled"),
                description=(item.get("description") or "")[:500],
                author=item.get("author", ""),
                created_date=created,
                source_url=feed_url,
            ))

        logger.info(f"[RSS_PARSER] Flickr JSON: {len(items)} items, {len(entries)} with images")
        return entries

    # ------------------------------------------------------------------
    # Reddit entry parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_reddit_entries(posts: list, feed_url: str, limit: int) -> List[ParsedEntry]:
        entries: List[ParsedEntry] = []
        for post in posts:
            if len(entries) >= limit:
                break
            if not isinstance(post, dict):
                continue

            image_url = post.get("url_overridden_by_dest") or post.get("url")
            if not image_url:
                continue

            # Must be an image URL
            try:
                path_lower = urlparse(image_url).path.lower()
                if not any(path_lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp")):
                    continue
            except (ValueError, TypeError):
                logger.debug("[RSS_PARSER] URL parse failed for entry, skipping", exc_info=True)
                continue

            # Light high-res filter (prefer ≥ 2560 px wide when metadata available)
            try:
                preview = post.get("preview") or {}
                images = preview.get("images") or []
                if images:
                    src = (images[0] or {}).get("source") or {}
                    w = src.get("width")
                    if isinstance(w, (int, float)) and int(w) < 2560:
                        continue
            except (KeyError, IndexError, TypeError):
                logger.debug("[RSS_PARSER] Metadata probe failed", exc_info=True)

            created = None
            ts = post.get("created_utc")
            if isinstance(ts, (int, float)):
                try:
                    created = datetime.utcfromtimestamp(ts)
                except (ValueError, OSError, OverflowError):
                    logger.debug("[RSS_PARSER] Timestamp conversion failed for ts=%s", ts, exc_info=True)

            entries.append(ParsedEntry(
                image_url=image_url,
                title=post.get("title", "Untitled"),
                description=(post.get("selftext") or "")[:500],
                author=post.get("author", ""),
                created_date=created,
                source_url=feed_url,
            ))

        logger.info(f"[RSS_PARSER] Reddit JSON: {len(posts)} posts, {len(entries)} with images")
        return entries

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_image_from_rss_entry(entry) -> Optional[str]:
        """Extract the best image URL from a feedparser entry."""
        # media:content
        if hasattr(entry, "media_content") and entry.media_content:
            for media in entry.media_content:
                if media.get("medium") == "image" or "image" in media.get("type", ""):
                    url = media.get("url")
                    if url:
                        return url

        # enclosures
        if hasattr(entry, "enclosures") and entry.enclosures:
            for enc in entry.enclosures:
                if "image" in enc.get("type", ""):
                    href = enc.get("href")
                    if href:
                        return href

        # content / summary img tags
        content = entry.get("content", [{}])[0].get("value", "") or entry.get("summary", "")
        if content:
            m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
            if m:
                return m.group(1)

        # thumbnail
        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            url = entry.media_thumbnail[0].get("url")
            if url:
                return url

        return None

    @staticmethod
    def _parse_rss_date(entry) -> Optional[datetime]:
        for field in ("published_parsed", "updated_parsed", "created_parsed"):
            ts = getattr(entry, field, None)
            if ts:
                try:
                    return datetime(*ts[:6])
                except (ValueError, TypeError):
                    logger.debug("[RSS_PARSER] _parse_date failed for ts=%s", ts, exc_info=True)
        return None
