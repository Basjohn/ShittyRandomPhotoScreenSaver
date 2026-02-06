"""
RSS system constants - feeds, priorities, rate limits, cache settings.

Centralised here so every sub-module imports from one place.
"""

# ---------------------------------------------------------------------------
# Default feeds (no Reddit - cross-process rate limit issues)
# ---------------------------------------------------------------------------
DEFAULT_RSS_FEEDS = {
    # NASA - High quality space/science imagery
    "NASA Image of the Day": "https://www.nasa.gov/feeds/iotd-feed",

    # Wikimedia Commons - Curated high-quality images
    "Wikimedia Picture of the Day": "https://commons.wikimedia.org/w/api.php?action=featuredfeed&feed=potd&feedformat=rss&language=en",
    "Wikimedia Media of the Day": "https://commons.wikimedia.org/w/api.php?action=featuredfeed&feed=motd&feedformat=rss&language=en",

    # Bing - Daily wallpapers, consistently high quality
    "Bing Image of the Day": "https://www.bing.com/HPImageArchive.aspx?format=rss&idx=0&n=8&mkt=en-US",

    # Flickr - No rate limits on public RSS feeds, diverse content
    "Flickr Explore": "https://www.flickr.com/services/feeds/photos_public.gne?format=json&nojsoncallback=1",
    "Flickr Landscape": "https://www.flickr.com/services/feeds/photos_public.gne?tags=landscape,nature&format=json&nojsoncallback=1",
    "Flickr Mountains": "https://www.flickr.com/services/feeds/photos_public.gne?tags=mountains,peaks&format=json&nojsoncallback=1",
    "Flickr Ocean": "https://www.flickr.com/services/feeds/photos_public.gne?tags=ocean,sea&format=json&nojsoncallback=1",
    "Flickr Space": "https://www.flickr.com/services/feeds/photos_public.gne?tags=space,astronomy,nebula&format=json&nojsoncallback=1",
    "Flickr Cityscapes": "https://www.flickr.com/services/feeds/photos_public.gne?tags=cityscape,urban,skyline&format=json&nojsoncallback=1",
    "Flickr Night Photography": "https://www.flickr.com/services/feeds/photos_public.gne?tags=night,nightscape,longexposure&format=json&nojsoncallback=1",
}

# ---------------------------------------------------------------------------
# Source priority weights - higher = processed earlier
# ---------------------------------------------------------------------------
SOURCE_PRIORITY = {
    "bing.com": 95,
    "flickr.com": 90,
    "wikimedia.org": 85,
    "nasa.gov": 75,
    "reddit.com": 10,
}


def get_source_priority(url: str) -> int:
    """Return priority for a feed URL based on domain."""
    url_lower = url.lower()
    for domain, priority in SOURCE_PRIORITY.items():
        if domain in url_lower:
            return priority
    return 50


# ---------------------------------------------------------------------------
# Download budget
# ---------------------------------------------------------------------------
TARGET_TOTAL_IMAGES = 50          # Cache + new downloads ceiling
MAX_PER_FEED_DOWNLOAD = 3        # Never download more than 3 per feed per pass
MIN_PER_FEED_DOWNLOAD = 1        # At least 1 per feed when downloads are needed

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
MAX_CACHED_IMAGES_TO_LOAD = 35   # Startup cache ceiling
MIN_CACHE_BEFORE_CLEANUP = 20    # Don't evict until we have at least 20
DEFAULT_MAX_CACHE_SIZE_MB = 500  # On-disk cache size cap

# ---------------------------------------------------------------------------
# Domain-based rate limiting (applies to all domains)
# ---------------------------------------------------------------------------
DOMAIN_RATE_LIMIT_PER_MINUTE = 15
DOMAIN_RATE_LIMIT_WINDOW = 60.0  # seconds

# ---------------------------------------------------------------------------
# Feed health / backoff
# ---------------------------------------------------------------------------
MAX_CONSECUTIVE_FAILURES = 3
FAILURE_BACKOFF_BASE_SECONDS = 60
FEED_HEALTH_RESET_HOURS = 24

# ---------------------------------------------------------------------------
# Reddit-specific
# ---------------------------------------------------------------------------
MAX_REDDIT_FEEDS_PER_STARTUP = 2
REDDIT_TOTAL_IMAGE_LIMIT = 10

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT_SECONDS = 30
