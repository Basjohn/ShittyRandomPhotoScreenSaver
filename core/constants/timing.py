"""Timing constants for the screensaver.

All timing values are in milliseconds unless otherwise noted.
These constants replace magic numbers throughout the codebase for better
maintainability and easier performance tuning.
"""

# =============================================================================
# Worker Timeouts
# =============================================================================

WORKER_IMAGE_TIMEOUT_MS = 1500
"""Maximum time for image decode/scale operations in ImageWorker."""

WORKER_HEARTBEAT_INTERVAL_MS = 3000
"""Interval between worker health check heartbeats."""

WORKER_RESPONSE_POLL_INTERVAL_MS = 1
"""Polling interval when waiting for worker responses."""

# =============================================================================
# Retry and Backoff
# =============================================================================

RETRY_BASE_DELAY_MS = 1000
"""Base delay for exponential backoff on worker restarts."""

RETRY_MAX_DELAY_MS = 30000
"""Maximum backoff delay (30 seconds) before giving up."""

RETRY_MAX_ATTEMPTS = 5
"""Maximum restart attempts before disabling a worker."""

# =============================================================================
# UI Timing
# =============================================================================

TRANSITION_DEFAULT_DURATION_MS = 5000
"""Default transition animation length."""

TRANSITION_MIN_DURATION_MS = 1000
"""Minimum transition duration."""

TRANSITION_MAX_DURATION_MS = 30000
"""Maximum transition duration."""

OVERLAY_FADE_DURATION_MS = 300
"""Overlay widget fade in/out time."""

TOOLTIP_DELAY_MS = 500
"""Delay before showing tooltips."""

CONTEXT_MENU_DELAY_MS = 150
"""Delay before showing context menus."""

# =============================================================================
# Cache Timing
# =============================================================================

CACHE_MAX_AGE_MS = 60000
"""Maximum age for stale cache entries (1 minute)."""

PREFETCH_STAGGER_MS = 100
"""Delay between prefetch operations to avoid overwhelming I/O."""

DISPLAY_INIT_STAGGER_MS = 100
"""Delay between display widget creations to spread GL init load (increased from 50ms)."""

TRANSITION_STAGGER_MS = 200
"""Delay between transition starts on multiple displays (increased from 100ms to 200ms for better desync)."""

SETTINGS_CACHE_TTL_MS = 5000
"""Time-to-live for in-memory settings cache entries."""

# =============================================================================
# Visualizer Timing
# =============================================================================

VISUALIZER_TICK_INTERVAL_MS = 16
"""Base tick interval for Spotify visualizer (~60 FPS)."""

VISUALIZER_BASE_MAX_FPS = 90.0
"""Maximum FPS for visualizer when idle."""

VISUALIZER_TRANSITION_MAX_FPS = 60.0
"""Maximum FPS for visualizer during transitions."""

VISUALIZER_SMOOTHING_TAU_S = 0.12
"""Base smoothing time constant in seconds for bar heights."""

AUDIO_SILENCE_TIMEOUT_MS = 400
"""Time without audio before treating as silence."""

# =============================================================================
# Performance Thresholds
# =============================================================================

PERF_SLOW_OPERATION_THRESHOLD_MS = 20.0
"""Threshold for logging slow operations."""

PERF_SPIKE_THRESHOLD_MS = 42.0
"""Threshold for logging dt spikes."""

PERF_SPIKE_LOG_COOLDOWN_S = 0.75
"""Cooldown between spike log messages."""

PERF_SNAPSHOT_INTERVAL_S = 5.0
"""Interval between periodic PERF snapshots."""

# =============================================================================
# Thread and Process Management
# =============================================================================

THREAD_JOIN_TIMEOUT_S = 1.0
"""Timeout in seconds for thread.join() operations."""

PROCESS_GRACEFUL_SHUTDOWN_TIMEOUT_S = 5.0
"""Timeout for graceful process shutdown before termination."""

PROCESS_TERMINATE_TIMEOUT_S = 1.0
"""Timeout after terminate() before kill()."""

# =============================================================================
# Export all constants
# =============================================================================

__all__ = [
    # Worker timeouts
    "WORKER_IMAGE_TIMEOUT_MS",
    "WORKER_HEARTBEAT_INTERVAL_MS",
    "WORKER_RESPONSE_POLL_INTERVAL_MS",
    # Retry/backoff
    "RETRY_BASE_DELAY_MS",
    "RETRY_MAX_DELAY_MS",
    "RETRY_MAX_ATTEMPTS",
    # UI timing
    "TRANSITION_DEFAULT_DURATION_MS",
    "TRANSITION_MIN_DURATION_MS",
    "TRANSITION_MAX_DURATION_MS",
    "OVERLAY_FADE_DURATION_MS",
    "TOOLTIP_DELAY_MS",
    "CONTEXT_MENU_DELAY_MS",
    # Cache timing
    "CACHE_MAX_AGE_MS",
    "PREFETCH_STAGGER_MS",
    "DISPLAY_INIT_STAGGER_MS",
    "TRANSITION_STAGGER_MS",
    "SETTINGS_CACHE_TTL_MS",
    # Visualizer timing
    "VISUALIZER_TICK_INTERVAL_MS",
    "VISUALIZER_BASE_MAX_FPS",
    "VISUALIZER_TRANSITION_MAX_FPS",
    "VISUALIZER_SMOOTHING_TAU_S",
    "AUDIO_SILENCE_TIMEOUT_MS",
    # Performance thresholds
    "PERF_SLOW_OPERATION_THRESHOLD_MS",
    "PERF_SPIKE_THRESHOLD_MS",
    "PERF_SPIKE_LOG_COOLDOWN_S",
    "PERF_SNAPSHOT_INTERVAL_S",
    # Thread/process management
    "THREAD_JOIN_TIMEOUT_S",
    "PROCESS_GRACEFUL_SHUTDOWN_TIMEOUT_S",
    "PROCESS_TERMINATE_TIMEOUT_S",
]
