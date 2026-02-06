"""
RSS Feed Image Source - Modular Architecture

Modules:
    constants   - Feed URLs, priorities, rate limit constants
    cache       - RSSCache: disk cache with ResourceManager integration
    parser      - RSSParser: feed type detection and entry parsing
    downloader  - RSSDownloader: shutdown-aware network I/O with domain rate limiting
    coordinator - RSSCoordinator: state machine, dynamic limits, orchestration
"""
from sources.rss.constants import DEFAULT_RSS_FEEDS, SOURCE_PRIORITY
from sources.rss.coordinator import RSSCoordinator, RSSState

__all__ = [
    "DEFAULT_RSS_FEEDS",
    "SOURCE_PRIORITY",
    "RSSCoordinator",
    "RSSState",
]
