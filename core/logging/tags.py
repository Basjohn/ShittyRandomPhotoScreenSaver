"""Standard logging tags for consistent log filtering.

These tags are used throughout the codebase to enable log filtering
and routing to appropriate log files.

Usage:
    from core.logging.tags import TAG_PERF, TAG_WORKER
    logger.info(f"{TAG_PERF} Operation took {elapsed:.2f}ms")
"""

from __future__ import annotations

from typing import Iterable


# Reserved structured LogRecord metadata.  A tuple is required because one
# record may intentionally belong to more than one sidecar family (for
# example, a PERF cache summary belongs to both ``perf`` and ``cache``).
LOG_FAMILY_FIELD = "srpss_log_families"

LOG_FAMILY_PERF = "perf"
LOG_FAMILY_WIDGET_PERF = "widget_perf"
LOG_FAMILY_USAGE = "usage"
LOG_FAMILY_VISUALIZER = "visualizer"
LOG_FAMILY_VISUALIZER_VOLUME = "visualizer_volume"
LOG_FAMILY_GEOMETRY = "geometry"
LOG_FAMILY_SETTINGS = "settings"
LOG_FAMILY_LIFECYCLE = "lifecycle"
LOG_FAMILY_CACHE = "cache"
LOG_FAMILY_STEAM = "steam"

KNOWN_LOG_FAMILIES = frozenset(
    {
        LOG_FAMILY_PERF,
        LOG_FAMILY_WIDGET_PERF,
        LOG_FAMILY_USAGE,
        LOG_FAMILY_VISUALIZER,
        LOG_FAMILY_VISUALIZER_VOLUME,
        LOG_FAMILY_GEOMETRY,
        LOG_FAMILY_SETTINGS,
        LOG_FAMILY_LIFECYCLE,
        LOG_FAMILY_CACHE,
        LOG_FAMILY_STEAM,
    }
)


def normalize_log_families(value: object) -> tuple[str, ...]:
    """Return known, lower-case family ids in stable de-duplicated order."""

    if isinstance(value, str):
        values: Iterable[object] = (value,)
    elif isinstance(value, (tuple, list, set, frozenset)):
        values = value
    else:
        return ()

    normalized: list[str] = []
    for item in values:
        family = str(item or "").strip().lower()
        if family in KNOWN_LOG_FAMILIES and family not in normalized:
            normalized.append(family)
    return tuple(normalized)

# =============================================================================
# Performance and Metrics
# =============================================================================

TAG_PERF = "[PERF]"
"""Performance metrics - routed to screensaver_perf.log"""

TAG_WIDGET_PERF = "[PERF_WIDGET]"
"""Per-widget instrumentation metrics routed to perf_widgets.log"""

TAG_ENGINE = "[ENGINE]"
"""Engine lifecycle and state changes."""

TAG_COMPOSITOR = "[GL]"
"""GL compositor operations."""

TAG_TRANSITION = "[TRANSITION]"
"""Transition effects and animations."""

TAG_RENDER = "[RENDER]"
"""Rendering operations."""

TAG_TIMING = "[TIMING]"
"""High-frequency timing measurements (non-routed)."""

# =============================================================================
# Operation Tags
# =============================================================================

TAG_ASYNC = "[ASYNC]"
"""Async operations and callbacks."""

TAG_CACHE = "[CACHE]"
"""Cache operations (get, put, evict)."""

TAG_RSS = "[RSS]"
"""RSS feed operations."""

TAG_IMAGE = "[IMAGE]"
"""Image loading and processing."""

TAG_PREFETCH = "[PREFETCH]"
"""Prefetch operations."""

TAG_WORKER = "[WORKER]"
"""Worker process operations."""

# =============================================================================
# Status Tags
# =============================================================================

TAG_FALLBACK = "[FALLBACK]"
"""Fallback operations when primary path fails."""

TAG_ERROR = "[ERROR]"
"""Error conditions (use with logger.error)."""

TAG_WARNING = "[WARNING]"
"""Warning conditions (use with logger.warning)."""

TAG_LIFECYCLE = "[LIFECYCLE]"
"""Widget/component lifecycle events."""

# =============================================================================
# Module-Specific Tags
# =============================================================================

TAG_SPOTIFY_VIS = "[SPOTIFY_VIS]"
"""Spotify visualizer - routed to screensaver_spotify_vis.log"""

TAG_SPOTIFY_VOL = "[SPOTIFY_VOL]"
"""Spotify volume control - routed to screensaver_spotify_vol.log"""

TAG_MC = "[MC]"
"""Media Center mode operations."""

TAG_SHADOW = "[SHADOW]"
"""Shadow rendering operations."""

TAG_SHADOW_ASYNC = "[SHADOW_ASYNC]"
"""Async shadow rendering."""

# =============================================================================
# GL-Specific Tags
# =============================================================================

TAG_GL_COMPOSITOR = "[GL COMPOSITOR]"
"""GL compositor specific operations."""

TAG_GL_ANIM = "[GL ANIM]"
"""GL animation operations."""

TAG_GL_TEXTURE = "[GL TEXTURE]"
"""GL texture operations."""

TAG_GL_PBO = "[GL PBO]"
"""GL Pixel Buffer Object operations."""

# =============================================================================
# Export all tags
# =============================================================================

__all__ = [
    # Structured record family metadata
    "LOG_FAMILY_FIELD",
    "LOG_FAMILY_PERF",
    "LOG_FAMILY_WIDGET_PERF",
    "LOG_FAMILY_USAGE",
    "LOG_FAMILY_VISUALIZER",
    "LOG_FAMILY_VISUALIZER_VOLUME",
    "LOG_FAMILY_GEOMETRY",
    "LOG_FAMILY_SETTINGS",
    "LOG_FAMILY_LIFECYCLE",
    "LOG_FAMILY_CACHE",
    "LOG_FAMILY_STEAM",
    "KNOWN_LOG_FAMILIES",
    "normalize_log_families",
    # Performance
    "TAG_PERF",
    "TAG_TIMING",
    # Components
    "TAG_WORKER",
    "TAG_ENGINE",
    "TAG_COMPOSITOR",
    "TAG_TRANSITION",
    "TAG_RENDER",
    # Operations
    "TAG_ASYNC",
    "TAG_CACHE",
    "TAG_RSS",
    "TAG_IMAGE",
    "TAG_PREFETCH",
    # Status
    "TAG_FALLBACK",
    "TAG_ERROR",
    "TAG_WARNING",
    "TAG_LIFECYCLE",
    # Module-specific
    "TAG_SPOTIFY_VIS",
    "TAG_SPOTIFY_VOL",
    "TAG_MC",
    "TAG_SHADOW",
    "TAG_SHADOW_ASYNC",
    # GL-specific
    "TAG_GL_COMPOSITOR",
    "TAG_GL_ANIM",
    "TAG_GL_TEXTURE",
    "TAG_GL_PBO",
]
