"""Wallpaper-feed constants: curated defaults, pool bounds, rotation, politeness.

No per-site rules live here. Feeds are ordinary RSS/Atom/JSON Feed documents or
JSON image listings read by shape; images are judged by their real pixels
against the connected displays (fill mode, no upscaling).
"""

# ---------------------------------------------------------------------------
# Curated defaults (added through Settings / first-run onboarding)
# ---------------------------------------------------------------------------
# Chosen 2026-09-24 by measured image size: each advertises images well beyond
# 1080p (NASA 2000-9000 px, JPL 5000-11780 px, Wallhaven full-size originals).
# Bing's archive is 1920x1080: admitted on 1080p setups, skipped from its header
# on larger displays at a cost of a few kilobytes. Flickr's public feeds (at
# most 1024 px in every format) and Wikimedia are deliberately absent.
DEFAULT_RSS_FEEDS = {
    "NASA Image of the Day": "https://www.nasa.gov/feeds/iotd-feed",
    "NASA JPL Photojournal": "https://photojournal.jpl.nasa.gov/rss/new",
    "Wallhaven SFW Wallpapers": "https://wallhaven.cc/api/v1/search?categories=110&purity=100",
    "Bing Image of the Day": "https://www.bing.com/HPImageArchive.aspx?format=rss&idx=0&n=8&mkt=en-US",
}

# ---------------------------------------------------------------------------
# Pool
# ---------------------------------------------------------------------------
TARGET_TOTAL_IMAGES = 50          # Pool target when the engine gives none
MAX_CACHED_IMAGES_TO_LOAD = 35    # Startup load ceiling (newest first)
MIN_CACHE_BEFORE_CLEANUP = 20     # Eviction never goes below this
DEFAULT_MAX_CACHE_SIZE_MB = 500   # On-disk pool byte cap

# ---------------------------------------------------------------------------
# Session rotation: a full pool still refreshes
# ---------------------------------------------------------------------------
STALE_AFTER_HOURS = 72            # Older pool images are eligible for replacement
SESSION_REPLACE_FRACTION = 3      # At most 1/3 of the pool target per process session

# ---------------------------------------------------------------------------
# Work bounds and politeness (per pass)
# ---------------------------------------------------------------------------
MAX_IMAGE_ATTEMPTS_PER_PASS = 40  # Image fetch attempts (including early rejections)
HOST_MIN_INTERVAL_SECONDS = 1.0   # Between two image requests to the same host
MAX_REJECTED_URLS = 4000          # Remembered too-small / non-image URLs
REJECTED_URL_TTL_DAYS = 30        # Re-judge after this (displays may change)
FEED_MAX_ITEMS = 50               # Entries read per feed document

# ---------------------------------------------------------------------------
# Stored size: an image far larger than the displays is kept right-sized once
# at acquisition (still covering the largest display with this headroom), so
# every later display decodes a fraction of the pixels.
# ---------------------------------------------------------------------------
STORED_COVER_HEADROOM = 1.25
RIGHT_SIZE_BELOW_SCALE = 0.8      # Only when that saves at least a fifth per side

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT_SECONDS = 30
