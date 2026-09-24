"""
Wallpaper feeds (image RSS): a wallpaper pool acquired through the shared feed core.

Modules:
    constants    - curated default feeds, pool bounds, rotation and politeness
    cache        - RSSCache: the on-disk pool, its size index, retirement, rejections
    image_fetch  - one vetted image stream per wallpaper, judged by its real pixels
    json_listing - generic JSON image listings read by shape (a FeedSource adapter)
    coordinator  - RSSCoordinator: acquisition passes and session rotation
"""
from sources.rss.constants import DEFAULT_RSS_FEEDS
from sources.rss.coordinator import RSSCoordinator, RSSState

__all__ = [
    "DEFAULT_RSS_FEEDS",
    "RSSCoordinator",
    "RSSState",
]
