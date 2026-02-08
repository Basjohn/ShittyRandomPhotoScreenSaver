"""Size and capacity constants for the screensaver.

These constants define cache sizes, queue capacities, and memory thresholds
used throughout the codebase.
"""

# =============================================================================
# Cache Sizes
# =============================================================================

MAX_IMAGE_CACHE_ITEMS = 24
"""Maximum number of images to keep in the image cache."""

MAX_IMAGE_CACHE_MB = 1024
"""Maximum memory for image cache in megabytes."""

MAX_SHADOW_CACHE_SIZE = 50
"""Maximum number of shadow pixmaps to cache."""

MAX_TEXTURE_CACHE_SIZE = 12
"""Maximum number of GL textures to cache."""

# =============================================================================
# Queue Sizes
# =============================================================================

WORKER_REQUEST_QUEUE_SIZE = 64
"""Maximum pending requests in worker queues."""

WORKER_RESPONSE_QUEUE_SIZE = 64
"""Maximum pending responses in worker queues."""

TRIPLE_BUFFER_DEFAULT_SIZE = 3
"""Default size for triple buffers (lock-free)."""

# =============================================================================
# Memory Thresholds
# =============================================================================

SHARED_MEMORY_THRESHOLD_MB = 2
"""Use shared memory for images above this size (megabytes)."""

SHARED_MEMORY_MAX_SIZE_MB = 64
"""Maximum size for shared memory blocks."""

WORKER_MEMORY_WARNING_MB = 512
"""Log warning when worker memory exceeds this threshold."""

WORKER_MEMORY_RESTART_MB = 1024
"""Restart worker when memory exceeds this threshold."""

# =============================================================================
# Image Processing
# =============================================================================

MAX_IMAGE_DIMENSION = 8192
"""Maximum image dimension (width or height) to process."""

MIN_IMAGE_DIMENSION = 16
"""Minimum image dimension to process."""

MIN_WALLPAPER_WIDTH = 1920
"""Minimum acceptable wallpaper width for ingestion."""

MIN_WALLPAPER_HEIGHT = 1080
"""Minimum acceptable wallpaper height for ingestion."""

THUMBNAIL_SIZE = 256
"""Default thumbnail size for previews."""

# =============================================================================
# Audio Processing
# =============================================================================

FFT_SAMPLE_SIZE = 2048
"""Number of samples for FFT processing."""

FFT_BAR_COUNT_DEFAULT = 32
"""Default number of bars for visualizer."""

FFT_BAR_COUNT_MIN = 8
"""Minimum number of visualizer bars."""

FFT_BAR_COUNT_MAX = 64
"""Maximum number of visualizer bars."""

AUDIO_SAMPLE_RATE = 48000
"""Audio sample rate in Hz."""

# =============================================================================
# UI Sizes
# =============================================================================

OVERLAY_MIN_HEIGHT = 88
"""Minimum height for overlay widgets."""

CONTEXT_MENU_MIN_WIDTH = 150
"""Minimum width for context menus."""

BORDER_WIDTH_DEFAULT = 2
"""Default border width for widgets."""

CORNER_RADIUS_DEFAULT = 8
"""Default corner radius for rounded widgets."""

# =============================================================================
# Export all constants
# =============================================================================

__all__ = [
    # Cache sizes
    "MAX_IMAGE_CACHE_ITEMS",
    "MAX_IMAGE_CACHE_MB",
    "MAX_SHADOW_CACHE_SIZE",
    "MAX_TEXTURE_CACHE_SIZE",
    # Queue sizes
    "WORKER_REQUEST_QUEUE_SIZE",
    "WORKER_RESPONSE_QUEUE_SIZE",
    "TRIPLE_BUFFER_DEFAULT_SIZE",
    # Memory thresholds
    "SHARED_MEMORY_THRESHOLD_MB",
    "SHARED_MEMORY_MAX_SIZE_MB",
    "WORKER_MEMORY_WARNING_MB",
    "WORKER_MEMORY_RESTART_MB",
    # Image processing
    "MAX_IMAGE_DIMENSION",
    "MIN_IMAGE_DIMENSION",
    "MIN_WALLPAPER_WIDTH",
    "MIN_WALLPAPER_HEIGHT",
    "THUMBNAIL_SIZE",
    # Audio processing
    "FFT_SAMPLE_SIZE",
    "FFT_BAR_COUNT_DEFAULT",
    "FFT_BAR_COUNT_MIN",
    "FFT_BAR_COUNT_MAX",
    "AUDIO_SAMPLE_RATE",
    # UI sizes
    "OVERLAY_MIN_HEIGHT",
    "CONTEXT_MENU_MIN_WIDTH",
    "BORDER_WIDTH_DEFAULT",
    "CORNER_RADIUS_DEFAULT",
]
