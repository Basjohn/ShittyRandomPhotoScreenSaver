"""Media/Now Playing widget for screensaver overlay.

This widget displays the current media playback state (track title,
artist, album) using the centralized media controller abstraction.

Transport controls (play/pause, previous/next) are exposed but are
strictly gated behind explicit user intent (Ctrl-held or Interaction Mode
interaction modes) as routed by DisplayWidget; normal screensaver
mode remains non-interactive.
"""
from __future__ import annotations

import hashlib
import time
import weakref
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Optional, TYPE_CHECKING, ClassVar, Any

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QBuffer, QByteArray, QTimer, Qt, Signal, QPoint
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QImageReader,
    QPixmap,
)
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from core.performance import widget_paint_sample
from core.media.media_controller import (
    BaseMediaController,
    MediaPlaybackState,
    MediaTrackInfo,
    create_media_controller,
)
from core.media.provider_registry import (
    get_media_provider_header_name,
    get_provider_failover_candidates,
    normalize_provider_id,
    preserve_provider_setting,
)
from core.threading.manager import ThreadManager
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.media.runtime_state import (
    MediaWidgetRuntimeState,
    build_retained_display_info,
    cache_retained_display_info,
    clear_missing_session,
    mark_provider_probe_attempt,
    note_missing_session,
    should_probe_provider_failover,
)
from widgets.shadow_utils import ShadowFadeProfile
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle
from utils.text_utils import smart_title_case

if TYPE_CHECKING:
    from rendering.widget_manager import WidgetManager

logger = get_logger(__name__)


@dataclass(frozen=True)
class PreparedArtwork:
    """Worker-owned artwork decode result awaiting a UI-thread pixmap handoff."""

    key: tuple[int, str]
    image: QImage | None
    decode_ms: float


class MediaPosition(Enum):
    """Media widget position on screen."""

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


class MediaWidget(BaseOverlayWidget):
    """Media widget for displaying current playback information.

    Extends BaseOverlayWidget for common styling/positioning functionality.

    Features:
    - Polls a centralized media controller for current track info
    - Shows playback state (playing/paused), title, artist, album
    - Configurable position, font, colors, and background frame
    - Non-interactive (transparent to mouse) for screensaver safety
    """

    media_updated = Signal(dict)  # Emits dict(MediaTrackInfo) when refreshed
    
    # Override defaults for media widget
    DEFAULT_FONT_SIZE = 20
    # A confirmation refresh is requested after 300 ms.  Keep the optimistic
    # command expectation alive long enough for that query to traverse the
    # controller's 2.5 s hard-timeout path, but release it promptly and
    # deterministically if the backend never confirms the command.
    _PLAYBACK_CONFIRMATION_REFRESH_DELAY_MS = 300
    _PLAYBACK_CONFIRMATION_TIMEOUT_SEC = 3.0
    
    # Class-level shared state for feedback synchronization
    _instances: ClassVar[weakref.WeakSet] = weakref.WeakSet()
    _shared_feedback_events: ClassVar[dict] = {}
    _shared_feedback_timer: ClassVar[Optional[QTimer]] = None
    # AnimationManager owns smooth feedback frames.  This timer is only the
    # deadline/fallback sweeper, so it must not add a second 60 Hz GUI stream.
    _shared_feedback_timer_interval_ms: ClassVar[int] = 100
    
    # Shared media info cache - prevents multi-display desync
    _shared_last_valid_info: ClassVar[Optional[MediaTrackInfo]] = None
    _shared_last_valid_info_ts: ClassVar[float] = 0.0
    _shared_info_max_age_sec: ClassVar[float] = 5.0

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        position: MediaPosition = MediaPosition.BOTTOM_LEFT,
        controller: Optional[BaseMediaController] = None,
        thread_manager: Optional[ThreadManager] = None,
        provider: str = "spotify",
    ) -> None:
        # Convert MediaPosition to OverlayPosition for base class
        overlay_pos = OverlayPosition(position.value)
        super().__init__(parent, position=overlay_pos, overlay_name="media")
        
        # Defer visibility until fade sync triggers
        self._defer_visibility_for_fade_sync = True

        self._media_position = position  # Keep original enum for compatibility
        
        # Registered provider id drives GSMTC session ownership and branding.
        self._provider: str = self._validate_provider(provider)
        self._provider_generation: int = 0
        self._perf_media_emit_count: int = 0
        self._perf_media_emit_total: int = 0
        self._perf_media_update_request_total: int = 0
        self._perf_media_display_total: int = 0
        self._perf_media_last_log_ts: float = time.monotonic()

        self._pending_controller_tm: Optional[ThreadManager] = None
        if thread_manager is not None:
            self.set_thread_manager(thread_manager)
        controller_tm = thread_manager or self._thread_manager or self._pending_controller_tm
        self._controller: BaseMediaController = controller or create_media_controller(
            thread_manager=controller_tm, app_filter=self._provider
        )
        if controller_tm is not None:
            try:
                self._controller.set_thread_manager(controller_tm)
            except Exception as exc:
                logger.debug("[MEDIA_WIDGET] Exception suppressing controller TM injection: %s", exc)
        else:
            self._pending_controller_tm = None
        try:
            logger.info("[MEDIA_WIDGET] Using controller: %s (provider=%s)", type(self._controller).__name__, self._provider)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

        self._widget_manager: Optional["WidgetManager"] = None
        self._update_timer: Optional[QTimer] = None
        self._update_timer_handle: Optional[OverlayTimerHandle] = None
        self._update_timer_interval_ms: Optional[int] = None
        self._refresh_in_flight = False
        self._refresh_in_flight_generation: int = 0
        # Playback-state freshness epoch. Each accepted optimistic transport edge
        # advances it; an async GSMTC refresh captures the epoch it started under,
        # so a refresh that began BEFORE the command cannot reverse the optimistic
        # post-command state. A same-epoch contradiction is also held until the
        # backend confirms the expected state or this bounded deadline expires.
        self._playback_epoch: int = 0
        self._expected_playback_state: Optional[MediaPlaybackState] = None
        self._expected_playback_epoch: Optional[int] = None
        self._playback_confirmation_deadline_monotonic: float = 0.0
        self._playback_confirmation_refresh_timer: Optional[QTimer] = None
        self._pending_keyboard_alias_command: Optional[tuple[str, float]] = None
        self._pending_keyboard_alias_timer: Optional[QTimer] = None
        self._last_external_transport_feedback: Optional[tuple[str, float]] = None

        # Override base class font size default
        self._font_size = 20

        # Album artwork state (optional)
        self._artwork_pixmap: Optional[QPixmap] = None
        self._applied_artwork_key: tuple[int, str] | None = None
        self._pending_artwork: PreparedArtwork | None = None
        self._pending_artwork_generation: int = 0
        self._pending_artwork_deferred: bool = False
        self._artwork_update_generation: int = 0
        self._artwork_coalesced_count: int = 0
        # Cached scaled artwork to avoid expensive SmoothTransformation on every paint
        self._scaled_artwork_cache: Optional[QPixmap] = None
        self._scaled_artwork_cache_key: Optional[tuple] = None  # (pm_id, frame_w, frame_h, dpr)
        # Default artwork size (logical pixels); overridable via settings.
        self._artwork_size: int = 200
        self._artwork_opacity: float = 1.0
        self._artwork_anim: Optional[object] = None

        # Artwork border behaviour
        self._rounded_artwork_border: bool = True

        # Optional header frame around the Spotify logo + title row.
        self._show_header_frame: bool = True

        # Layout/controls behaviour
        self._show_controls: bool = True
        self._playback_progress_enabled: bool = False
        self._playback_progress_height: int = 6
        self._playback_progress_fill_color = QColor(255, 255, 255, 230)
        self._playback_progress_shadow_enabled: bool = False
        self._playback_progress_glow_enabled: bool = False
        self._playback_progress_glow_color = QColor(255, 255, 255, 180)
        self._playback_progress_visible: bool = False
        self._playback_progress_fill_width: int = 0
        self._playback_progress_paint_key: Optional[tuple] = None
        self._metadata_paint_bottom: int = 0

        # Optional Spotify-style brand logo used when album artwork is absent.
        self._brand_pixmap: Optional[QPixmap] = self._load_brand_pixmap()
        self._header_logo_scaled_cache: Optional[QPixmap] = None
        self._header_logo_scaled_cache_key: Optional[tuple] = None

        # Painter-owned metadata layout used by widgets.media.painting.  This
        # keeps existing dynamic font scaling but avoids QLabel rich-text
        # shadow duplication.
        self._metadata_paint: dict[str, object] = {
            "provider": "",
            "title": "",
            "artist": "",
            "base_font": self._font_size,
            "header_font": 0,
            "title_font": self._font_size + 3,
            "artist_font": max(6, self._font_size - 2),
            "header_weight": 750,
            "title_weight": 700,
            "artist_weight": 600,
            "line_spacing": 4,
            "body_top_gap": 8,
        }

        # Cached header logo metrics so paintEvent can align the Spotify glyph
        # with the painter-owned SPOTIFY header.
        self._header_font_pt: int = max(6, int(self._font_size * 1.2))
        self._header_logo_size: int = max(12, int(self._header_font_pt * 1.3))
        self._header_logo_margin: int = self._header_logo_size
        self._context_menu_active: bool = False
        self._context_menu_prewarmed: bool = False
        self._pending_effect_invalidation: bool = False

        # Central ResourceManager wiring
        self._last_info: Optional[MediaTrackInfo] = None
        self._runtime_state = MediaWidgetRuntimeState()
        
        # Smart polling: diff gating to skip unnecessary updates
        self._last_track_identity: Optional[tuple] = None  # (title, artist, album, state)
        self._last_metadata_identity: Optional[tuple] = None
        
        # Smart polling: idle detection to stop polling when Spotify is closed
        self._consecutive_none_count: int = 0
        self._idle_threshold: int = 12  # ~30s at 2500ms interval before entering idle
        self._is_idle: bool = False
        self._idle_poll_interval: int = 5000  # Poll every 5s when idle (app running, no media)
        self._deep_idle_poll_interval: int = 30000  # Poll every 30s when app process not found
        self._app_process_running: bool = False  # Last known process existence state
        
        # Adaptive poll interval: 1000ms → 2000ms → 2500ms
        # Faster initial detection, then slow down for efficiency
        self._poll_intervals: list[int] = [1000, 2000, 2500]
        self._current_poll_stage: int = 0  # Index into _poll_intervals
        self._polls_at_current_stage: int = 0  # Polls completed at current interval

        # Fixed widget height once we have seen the first track so that
        # changes in wrapped text do not move the card on screen.
        self._fixed_card_height: Optional[int] = None

        # One-shot guard so we can perform an initial layout pass using the
        # first track's metadata, then only fade the widget in on the
        # *second* update once geometry has settled. This avoids the card
        # jumping size mid-fade or a second after it appears.
        self._has_seen_first_track: bool = False
        self._fade_in_completed: bool = False

        # One-shot flag so we only log the first paintEvent geometry.
        self._paint_debug_logged = False
        self._telemetry_logged_missing_tm = False
        self._telemetry_last_visibility: Optional[bool] = None
        self._telemetry_logged_fade_request = False
        
        # Desync: Cache GSMTC results for 500ms to reduce IO contention
        self._gsmtc_cache_ms = 500
        self._gsmtc_cached_result: Optional[Any] = None
        self._gsmtc_cached_prepared_artwork: PreparedArtwork | None = None
        self._gsmtc_cached_artwork_generation: int = 0
        self._gsmtc_cache_ts: float = 0.0
        
        # Artwork vertical bias for dynamic positioning
        self._artwork_vertical_bias: float = 0.4
        
        # Control feedback state (for visual feedback on button press)
        self._controls_feedback: dict = {}
        self._controls_feedback_progress: dict = {}
        self._controls_feedback_anim_ids: dict = {}
        self._feedback_anim_mgr: Optional[object] = None  # AnimationManager
        self._controls_feedback_duration: float = 1.35
        self._feedback_deadlines: dict[str, float] = {}
        self._active_feedback_events: dict[str, str] = {}
        self._last_manual_control: Optional[tuple[str, float, str]] = None
        self._controls_feedback_scale_boost: float = 0.12
        self._controls_row_radius: float = 12.0
        self._controls_row_shadow_alpha: int = 60
        self._controls_row_outline_alpha: int = 65
        self._controls_layout_cache: Optional[dict[str, object]] = None
        self._controls_shadow_cache: Optional[object] = None
        self._controls_shadow_cache_key: Optional[tuple] = None
        self._last_display_update_ts: float = 0.0
        self._skipped_identity_updates: int = 0
        self._max_identity_skip: int = 4
        self._unchanged_refresh_diag_pending: bool = False
        
        # Widget state tracking for lifecycle management
        self._activation_time: float = 0.0
        self._post_activation_grace_sec: float = 5.0  # Grace period after activation

        # Register this instance for shared feedback
        type(self)._instances.add(self)

        self._setup_ui()

        logger.debug("MediaWidget created (position=%s)", position.value)

    # ------------------------------------------------------------------
    # Provider helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_provider(raw: object) -> str:
        """Normalize registered ids while leaving unknown settings inert."""

        provider = preserve_provider_setting(raw)
        if normalize_provider_id(provider) is None:
            logger.warning(
                "[MEDIA_WIDGET] Unsupported provider %r; media integration is inert",
                provider,
            )
        return provider

    @property
    def provider(self) -> str:
        """Current registered media-provider id."""
        return self._provider

    @property
    def provider_display_name(self) -> str:
        """Human-readable provider name for the header text."""

        return get_media_provider_header_name(self._provider) or "MEDIA"

    def cache_retained_display_info(self, info: MediaTrackInfo) -> None:
        """Remember the latest valid metadata/artwork snapshot for retained display."""

        cache_retained_display_info(self._runtime_state, info)

    def get_retained_display_info(self) -> Optional[MediaTrackInfo]:
        """Return a retained snapshot downgraded to a non-reactive playback state."""

        return build_retained_display_info(self._runtime_state)

    def note_missing_session(self) -> None:
        """Record that live session acquisition temporarily disappeared."""

        note_missing_session(self._runtime_state)

    def clear_missing_session(self) -> None:
        """Clear the current missing-session marker."""

        clear_missing_session(self._runtime_state)

    def should_probe_provider_failover(self) -> bool:
        """Return True when runtime auto-fallback is allowed to probe again."""

        return should_probe_provider_failover(self._runtime_state)

    def mark_provider_probe_attempt(self) -> None:
        """Record a runtime provider auto-fallback probe attempt."""

        mark_provider_probe_attempt(self._runtime_state)

    def set_provider_runtime(self, provider: object) -> bool:
        """Retarget controller/branding to a new provider without recreating the widget."""

        normalized = self._validate_provider(provider)
        if normalized == self._provider and getattr(self, "_controller", None) is not None:
            return False

        controller_tm = self._thread_manager or self._pending_controller_tm
        controller = create_media_controller(thread_manager=controller_tm, app_filter=normalized)
        if controller_tm is not None:
            try:
                controller.set_thread_manager(controller_tm)
            except Exception as exc:
                logger.debug("[MEDIA_WIDGET] Exception suppressing controller TM injection: %s", exc)

        old_provider = self._provider
        self._reset_playback_confirmation(delete_timer=True)
        self._retire_refresh_generation()
        self._provider_generation += 1
        self._provider = normalized
        self._controller = controller
        self._runtime_state = MediaWidgetRuntimeState()
        self._last_info = None
        self._last_track_identity = None
        self._last_metadata_identity = None
        self._gsmtc_cached_result = None
        self._gsmtc_cached_prepared_artwork = None
        self._gsmtc_cache_ts = 0.0
        self._artwork_pixmap = None
        self._scaled_artwork_cache = None
        self._scaled_artwork_cache_key = None
        self._applied_artwork_key = None
        self._pending_artwork = None
        self._pending_artwork_deferred = False
        type(self)._shared_last_valid_info = None
        type(self)._shared_last_valid_info_ts = 0.0
        self._brand_pixmap = self._load_brand_pixmap()
        self._header_logo_scaled_cache = None
        self._header_logo_scaled_cache_key = None
        self._safe_update()
        logger.info("[MEDIA_WIDGET] Runtime provider switch: %s -> %s", old_provider, normalized)
        return True

    def _apply_provider_failover(self, provider: str) -> None:
        """UI-side provider switch and canonical settings persistence."""

        self.set_provider_runtime(provider)
        manager = self._widget_manager
        if manager is not None and hasattr(manager, "handle_media_provider_failover"):
            try:
                manager.handle_media_provider_failover(
                    provider,
                    source="media_runtime_autofallback",
                )
            except Exception:
                logger.debug(
                    "[MEDIA_WIDGET] Failed to persist provider failover",
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        # Use base class styling setup
        self._apply_base_styling()
        
        # Align content to the top-left so the header/logo sit close to the
        # top edge rather than vertically centered in the card.
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        try:
            # Non-interactive by default; screensaver interaction is gated elsewhere.
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)
        self.setWordWrap(True)

        # Base contents margins; _update_display() will tighten these once we
        # know the artwork size, but start with a modest frame.
        self.setContentsMargins(29, 12, 12, 12)

        # Ensure a reasonable default footprint before artwork/metadata arrive.
        self.setMinimumWidth(BaseOverlayWidget.DEFAULT_CARD_MIN_WIDTH)
        # Tie the default minimum height to the configured artwork size so
        # the widget does not "jump" in height once artwork is decoded.
        self.setMinimumHeight(max(220, self._artwork_size + 60))
    
    def _update_content(self) -> None:
        """Required by BaseOverlayWidget - refresh media display."""
        self._refresh()

    # -------------------------------------------------------------------------
    # Lifecycle Implementation Hooks
    # -------------------------------------------------------------------------
    
    def _initialize_impl(self) -> None:
        """Initialize media resources (lifecycle hook)."""
        logger.debug("[LIFECYCLE] MediaWidget initialized")
    
    def _activate_impl(self) -> None:
        """Activate media widget - start polling (lifecycle hook)."""
        self._reset_playback_confirmation(delete_timer=True)
        invalidate = getattr(self, "_invalidate_controls_layout", None)
        if callable(invalidate):
            invalidate()
        if not self._ensure_thread_manager("MediaWidget._activate_impl"):
            # Fall back to a best-effort synchronous refresh so metadata at least appears once.
            logger.error("[MEDIA_WIDGET] ThreadManager missing during activation; performing synchronous refresh")
            self._refresh()
            return
        
        # Record activation time for grace period
        self._activation_time = time.monotonic()
        
        self._refresh()
        self._ensure_timer()
        if self._thread_manager is not None:
            self._refresh_async()
        
        logger.debug("[LIFECYCLE] MediaWidget activated")
    
    def _deactivate_impl(self) -> None:
        """Deactivate media widget - stop polling (lifecycle hook)."""
        self._stop_update_timers(delete_qtimer=True)
        self._reset_playback_confirmation(delete_timer=True)
        self._retire_refresh_generation()
        
        logger.debug("[LIFECYCLE] MediaWidget deactivated")
    
    def _cleanup_impl(self) -> None:
        """Clean up media resources (lifecycle hook)."""
        self._deactivate_impl()
        self._discard_pending_artwork()
        self._artwork_pixmap = None
        self._applied_artwork_key = None
        self._scaled_artwork_cache = None
        self._scaled_artwork_cache_key = None
        self._header_logo_scaled_cache = None
        self._header_logo_scaled_cache_key = None
        self._last_info = None
        logger.debug("[LIFECYCLE] MediaWidget cleaned up")
    
    # -------------------------------------------------------------------------
    # Legacy Start/Stop Methods (for backward compatibility)
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Begin polling media controller and showing widget."""

        if self._enabled:
            logger.warning("Media widget already running")
            return
        if not self._ensure_thread_manager("MediaWidget.start"):
            return

        self._reset_playback_confirmation(delete_timer=True)
        self._enabled = True
        try:
            self.hide()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        
        # Force initial refresh to load artwork on boot
        # This ensures the widget shows current track immediately
        self._ensure_timer()
        if self._thread_manager is not None:
            self._refresh_async()
        else:
            self._refresh()
        logger.info("Media widget started")

    def stop(self) -> None:
        """Stop polling and hide widget."""

        if not self._enabled:
            return

        self._enabled = False
        self._stop_update_timers(delete_qtimer=True)
        self._reset_playback_confirmation(delete_timer=True)
        self._retire_refresh_generation()

        self.hide()
        logger.debug("Media widget stopped")

    def is_running(self) -> bool:
        return self._enabled

    def cleanup(self) -> None:
        """Clean up resources (called from DisplayWidget)."""

        logger.debug("Cleaning up media widget")
        self._cancel_painted_frame_shadow_preparation()
        self._discard_pending_artwork()
        self.stop()

    def _reset_update_timer_state(self, *, delete_qtimer: bool) -> None:
        """Stop smart-poll timer state and optionally destroy the backing QTimer."""
        if self._update_timer_handle is not None:
            try:
                self._update_timer_handle.stop()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            self._update_timer_handle = None

        if self._update_timer is not None:
            try:
                self._update_timer.stop()
                if delete_qtimer:
                    self._update_timer.deleteLater()
            except RuntimeError:
                pass
            self._update_timer = None
        self._update_timer_interval_ms = None

    def _stop_update_timers(self, *, delete_qtimer: bool) -> None:
        self._reset_update_timer_state(delete_qtimer=delete_qtimer)

    def _retire_refresh_generation(self) -> None:
        """Fence results from a retired provider/runtime refresh generation."""
        self._artwork_update_generation = (
            int(getattr(self, "_artwork_update_generation", 0)) + 1
        )
        self._refresh_in_flight = False
        self._refresh_in_flight_generation = self._artwork_update_generation
        self._gsmtc_cached_result = None
        self._gsmtc_cached_prepared_artwork = None
        self._gsmtc_cached_artwork_generation = 0
        self._gsmtc_cache_ts = 0.0

    def _reset_playback_confirmation(self, *, delete_timer: bool) -> None:
        """Clear bounded playback confirmation ownership and its refresh timer."""
        timer = self._playback_confirmation_refresh_timer
        if timer is not None:
            try:
                timer.stop()
                if delete_timer:
                    timer.deleteLater()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        self._playback_confirmation_refresh_timer = None
        self._expected_playback_state = None
        self._expected_playback_epoch = None
        self._playback_confirmation_deadline_monotonic = 0.0

    def set_thread_manager(self, thread_manager) -> None:
        super().set_thread_manager(thread_manager)
        controller_tm = thread_manager or self._thread_manager
        if hasattr(self, "_controller") and self._controller is not None and controller_tm is not None:
            try:
                self._controller.set_thread_manager(controller_tm)
            except Exception as exc:
                logger.debug("[MEDIA_WIDGET] Unable to inject ThreadManager into media controller: %s", exc)
        else:
            self._pending_controller_tm = controller_tm
        invalidate = getattr(self, "_invalidate_controls_layout", None)
        if callable(invalidate):
            invalidate()
        if self._enabled and thread_manager is not None:
            self._ensure_timer(force=True)
            self._refresh_async()
        if is_verbose_logging():
            logger.debug("[MEDIA_WIDGET] ThreadManager injected: %s", type(thread_manager).__name__ if thread_manager else None)

    def set_widget_manager(self, widget_manager: "WidgetManager") -> None:
        self._widget_manager = widget_manager

    def _safe_update(self) -> None:
        """Best-effort call to QWidget.update() that tolerates deleted objects."""
        if Shiboken is not None:
            try:
                if not Shiboken.isValid(self):
                    return
            except Exception:
                pass
        try:
            self.update()
            self._perf_media_update_request_total += 1
        except RuntimeError:
            pass
        except Exception as exc:
            logger.debug("[MEDIA_WIDGET] update() suppressed: %s", exc)
    
    # ------------------------------------------------------------------
    # Smart Polling Helpers
    # ------------------------------------------------------------------
    
    def wake_from_idle(self) -> None:
        """Wake the media widget from idle mode to resume polling.
        
        Called when user interaction or external event suggests Spotify
        may have been reopened.
        """
        if self._is_idle:
            self._is_idle = False
            self._consecutive_none_count = 0
            if is_perf_metrics_enabled():
                logger.debug("[PERF] Media widget woken from idle")
            # Trigger immediate refresh
            if self._enabled and self._thread_manager is not None:
                self._refresh_async()

    def _update_position(self) -> None:
        """Delegates to widgets.media_layout."""
        from widgets.media_layout import update_position
        update_position(self)

    def _notify_spotify_widgets_visibility(self) -> None:
        """Notify Spotify-related widgets to sync their visibility with this widget.
        
        Called when the media widget shows or hides so the visualizer and
        volume widgets can show/hide accordingly.
        """
        manager = getattr(self, "_widget_manager", None)
        if manager is not None and hasattr(manager, "sync_spotify_dependents_for_media_widget"):
            try:
                manager.sync_spotify_dependents_for_media_widget(self)
                return
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

        parent = self.parent()
        if parent is None:
            return
        
        # Notify visualizer
        vis = getattr(parent, "spotify_visualizer_widget", None)
        if vis is not None:
            try:
                if hasattr(vis, "sync_visibility_with_anchor"):
                    vis.sync_visibility_with_anchor()
                elif hasattr(vis, "handle_media_update"):
                    # Legacy fallback for widgets without explicit sync helper
                    state = "playing" if self.isVisible() else "stopped"
                    vis.handle_media_update({"state": state})
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        
        # Notify volume widget
        vol = getattr(parent, "spotify_volume_widget", None)
        if vol is not None:
            try:
                if hasattr(vol, "sync_visibility_with_anchor"):
                    vol.sync_visibility_with_anchor()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

        # Notify mute button widget
        mute_btn = getattr(parent, "mute_button_widget", None)
        if mute_btn is not None:
            try:
                if hasattr(mute_btn, "sync_visibility_with_anchor"):
                    mute_btn.sync_visibility_with_anchor()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def _update_stylesheet(self) -> None:
        selector = f"#{self.objectName()}" if self.objectName() else "QLabel"
        if self.uses_painted_frame_shadow():
            self.setStyleSheet(
                f"""
                {selector} {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()},
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: transparent;
                    border: {self._bg_border_width}px solid transparent;
                    border-radius: 8px;
                }}
                """
            )
        elif self._show_background:
            self.setStyleSheet(
                f"""
                {selector} {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()},
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: rgba({self._bg_color.red()}, {self._bg_color.green()},
                                          {self._bg_color.blue()}, {self._bg_color.alpha()});
                    border: {self._bg_border_width}px solid rgba({self._bg_border_color.red()},
                                                                 {self._bg_border_color.green()},
                                                                 {self._bg_border_color.blue()},
                                                                 {self._bg_border_color.alpha()});
                    border-radius: 8px;
                }}
                """
            )
        else:
            self.setStyleSheet(
                f"""
                {selector} {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()},
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: transparent;
                }}
                """
            )

    def set_position(self, position: MediaPosition) -> None:
        """Set widget position using MediaPosition enum."""
        self._media_position = position
        # Update base class position
        overlay_pos = OverlayPosition(position.value)
        super().set_position(overlay_pos)

    def _invalidate_metadata_layout(self) -> None:
        """Force the next media display refresh to rebuild painter-owned text layout."""

        self._metadata_paint = {}
        self._metadata_paint_bottom = 0
        self._last_metadata_identity = None

    def _refresh_metadata_paint_boundary(self) -> None:
        """Prepare the scalar text boundary outside paint-time layout lookup."""

        if not bool(getattr(self, "_playback_progress_enabled", False)):
            self._metadata_paint_bottom = 0
            return
        try:
            from widgets.media.painting import metadata_paint_bottom

            self._metadata_paint_bottom = max(0, int(metadata_paint_bottom(self)))
        except Exception as exc:
            logger.debug("[MEDIA_WIDGET] Failed to prepare metadata paint boundary: %s", exc)
            self._metadata_paint_bottom = 0
        self._invalidate_controls_layout()

    def _refresh_playback_progress_snapshot(self) -> bool:
        """Re-quantize progress from the accepted snapshot without publication work."""

        info = self._last_info
        if info is None:
            try:
                info = self.get_retained_display_info()
            except Exception as exc:
                logger.debug("[MEDIA_WIDGET] Failed to read retained progress snapshot: %s", exc)
                info = None
        try:
            from widgets.media.display_update import _update_progress_paint_state

            return bool(_update_progress_paint_state(self, info))
        except Exception as exc:
            logger.debug("[MEDIA_WIDGET] Failed to refresh progress paint state: %s", exc)
            return True

    def _refresh_current_display_layout(self) -> None:
        """Rebuild the live or retained media card layout after geometry-affecting setting changes."""

        info = self._last_info
        if info is None:
            try:
                info = self.get_retained_display_info()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                info = None
        if info is not None:
            try:
                self._update_display(info)
                return
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        self._safe_update()

    def set_font_size(self, size: int) -> None:  # type: ignore[override]
        """Set the font size and invalidate any cached media text layout."""

        if int(size) == int(getattr(self, "_font_size", -1)):
            # Same reasoning as `set_artwork_size`: an unchanged size must not
            # rebuild the live card.
            return
        super().set_font_size(size)
        self._invalidate_metadata_layout()
        invalidate = getattr(self, "_invalidate_controls_layout", None)
        if callable(invalidate):
            invalidate()
        self._refresh_current_display_layout()

    def set_artwork_size(self, size: int) -> None:
        """Set preferred artwork size in pixels and refresh layout."""

        if size <= 0:
            return
        if int(size) == int(self._artwork_size):
            # Re-applying the current footprint cannot change the authored card,
            # but the rebuild below reconstructs the display from `_last_info`
            # and would drop live artwork/metadata when that is unavailable.
            return
        self._artwork_size = int(size)
        self._invalidate_metadata_layout()
        invalidate = getattr(self, "_invalidate_controls_layout", None)
        if callable(invalidate):
            invalidate()
        target_min_height = max(220, self._artwork_size + 60)
        # Keep the card's minimum height in sync with the configured artwork
        # footprint so resizing via settings does not cause unexpected jumps
        # at runtime.
        self.setMinimumHeight(self._resolve_custom_locked_height(target_min_height))
        if self._active_custom_layout_rect() is not None:
            try:
                self.updateGeometry()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            self._schedule_custom_layout_geometry_reapply()
        self._refresh_current_display_layout()

    def set_rounded_artwork_border(self, rounded: bool) -> None:
        """Enable or disable rounded borders around the album artwork."""

        self._rounded_artwork_border = bool(rounded)
        self._safe_update()

    def set_show_header_frame(self, show: bool) -> None:
        """Enable or disable the header subcontainer frame around logo+title."""

        self._show_header_frame = bool(show)
        self._safe_update()

    def set_show_controls(self, show: bool) -> None:
        """Show or hide the transport controls row."""

        show = bool(show)
        if show == self._show_controls:
            return
        old_reserved = self._controls_reserved_height()
        self._show_controls = show
        self._apply_controls_reserved_height_delta(
            old_reserved,
            self._controls_reserved_height(),
        )
        self._refresh_metadata_paint_boundary()
        invalidate = getattr(self, "_invalidate_controls_layout", None)
        if callable(invalidate):
            invalidate()
        self._refresh_current_display_layout()

    def set_playback_progress_config(
        self,
        *,
        enabled: bool,
        height: int,
        fill_color: QColor,
        shadow_enabled: bool,
        glow_enabled: bool,
        glow_color: QColor,
    ) -> None:
        """Apply the paint-only playback progress presentation settings."""

        normalized_height = max(3, min(18, int(height)))
        try:
            normalized_fill = QColor(fill_color)
        except (TypeError, ValueError):
            normalized_fill = QColor()
        if not normalized_fill.isValid():
            normalized_fill = QColor(255, 255, 255, 230)
        try:
            normalized_glow = QColor(glow_color)
        except (TypeError, ValueError):
            normalized_glow = QColor()
        if not normalized_glow.isValid():
            normalized_glow = QColor(255, 255, 255, 180)
        normalized = (
            bool(enabled),
            normalized_height,
            normalized_fill.rgba(),
            bool(shadow_enabled),
            bool(glow_enabled),
            normalized_glow.rgba(),
        )
        current = (
            self._playback_progress_enabled,
            self._playback_progress_height,
            self._playback_progress_fill_color.rgba(),
            self._playback_progress_shadow_enabled,
            self._playback_progress_glow_enabled,
            self._playback_progress_glow_color.rgba(),
        )
        if normalized == current:
            return

        old_reserved = self._controls_reserved_height()
        self._playback_progress_enabled = normalized[0]
        self._playback_progress_height = normalized[1]
        self._playback_progress_fill_color = normalized_fill
        self._playback_progress_shadow_enabled = normalized[3]
        self._playback_progress_glow_enabled = normalized[4]
        self._playback_progress_glow_color = normalized_glow
        new_reserved = self._controls_reserved_height()
        self._apply_controls_reserved_height_delta(old_reserved, new_reserved)
        self._refresh_metadata_paint_boundary()
        self._invalidate_controls_layout()
        progress_changed = self._refresh_playback_progress_snapshot()
        if progress_changed or old_reserved != new_reserved:
            self._safe_update()


    def _invalidate_controls_layout(self) -> None:
        """Clear cached transport controls geometry."""
        self._controls_layout_cache = None
        self._controls_shadow_cache = None
        self._controls_shadow_cache_key = None

    # ------------------------------------------------------------------
    # Transport controls (delegated to controller)
    # ------------------------------------------------------------------
    def play_pause(self, source: str = "manual", execute: bool = True) -> None:
        """Toggle play/pause when supported.

        This is best-effort and never raises; failures are logged by the
        underlying controller. It is safe to call even when no media is
        currently playing.
        """
        if execute and self._should_defer_keyboard_alias_command(source, "play"):
            return

        control_executed = not execute
        refresh_requested = False
        if execute:
            try:
                self._controller.play_pause()
                control_executed = True
            except Exception:
                logger.debug("[MEDIA] play_pause delegation failed", exc_info=True)
        else:
            # Media keys already executed the command; still mirror optimistic UI
            control_executed = True

        if control_executed:
            # Optimistically flip the last known playback state so the controls
            # row and any listeners (e.g. the Spotify visualizer) respond
            # immediately while the GSMTC query catches up.
            optimistic = None
            new_state = None
            try:
                info = self._last_info
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                info = None
            if isinstance(info, MediaTrackInfo):
                try:
                    current_state = info.state
                except Exception as e:
                    logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                    current_state = MediaPlaybackState.UNKNOWN
                if current_state in (MediaPlaybackState.PLAYING, MediaPlaybackState.PAUSED):
                    new_state = (
                        MediaPlaybackState.PAUSED
                        if current_state == MediaPlaybackState.PLAYING
                        else MediaPlaybackState.PLAYING
                    )
                    try:
                        optimistic = MediaTrackInfo(
                            title=info.title,
                            artist=info.artist,
                            album=info.album,
                            album_artist=info.album_artist,
                            state=new_state,
                            can_play_pause=info.can_play_pause,
                            can_next=info.can_next,
                            can_previous=info.can_previous,
                            artwork=info.artwork,
                            source_app_user_model_id=info.source_app_user_model_id,
                            position_ms=info.position_ms,
                            duration_ms=info.duration_ms,
                        )
                    except Exception as e:
                        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                        optimistic = None
            if optimistic is not None:
                try:
                    # CRITICAL: Force update even if diff gating would skip
                    # Update _last_info first so _draw_control_icon sees new state
                    self._last_info = optimistic
                    # Update track identity to prevent diff gating from skipping next poll
                    self._last_track_identity = self._compute_track_identity(optimistic)
                    # Emit media update for visualizer and other listeners
                    self._emit_media_update(optimistic)
                    # Only refresh controls if they're visible and state changed.
                    # Use update() so the optimistic feedback coalesces with the
                    # normal event loop rather than forcing an immediate paint.
                    if self._show_controls and self.isVisible():
                        self._invalidate_controls_layout()
                        self.update()
                    logger.info("[MEDIA_WIDGET] Optimistic play/pause applied: state=%s", optimistic.state)
                except Exception:
                    logger.debug("[MEDIA] play_pause optimistic update failed", exc_info=True)
                try:
                    if new_state is not None:
                        self._begin_playback_confirmation(new_state)
                        refresh_requested = True
                except Exception:
                    logger.debug("[MEDIA] play_pause optimistic override failed", exc_info=True)
            else:
                refresh_requested = self._request_refresh_after_control()

        self._handle_control_feedback("play", source, force_refresh=not refresh_requested)

    def _begin_playback_confirmation(self, state: MediaPlaybackState) -> None:
        """Own one optimistic transport expectation until confirmation or expiry."""
        self._reset_playback_confirmation(delete_timer=True)
        # An accepted optimistic transport edge: advance the freshness epoch so a
        # refresh already in flight cannot later reverse this state.
        self._playback_epoch = int(getattr(self, "_playback_epoch", 0)) + 1
        self._expected_playback_state = state
        self._expected_playback_epoch = self._playback_epoch
        self._playback_confirmation_deadline_monotonic = (
            time.monotonic() + self._PLAYBACK_CONFIRMATION_TIMEOUT_SEC
        )
        # Drop any pre-command cached GSMTC result so the next refresh cannot
        # serve stale pre-command state from the 500 ms cache path.
        self._gsmtc_cached_result = None

        try:
            self._safe_update()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

        if not self._enabled:
            return

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(self._PLAYBACK_CONFIRMATION_REFRESH_DELAY_MS)

        def _on_timeout() -> None:
            if self._playback_confirmation_refresh_timer is not timer:
                return
            self._playback_confirmation_refresh_timer = None
            try:
                if self._enabled:
                    if self._thread_manager is not None:
                        self._refresh_async()
                    else:
                        self._refresh()
            except Exception:
                logger.debug("[MEDIA] pending state refresh failed", exc_info=True)
            self._safe_update()

        timer.timeout.connect(_on_timeout)
        self._playback_confirmation_refresh_timer = timer
        self._register_resource(timer, "playback confirmation refresh timer")
        timer.start()

    def next_track(self, source: str = "manual", execute: bool = True) -> None:
        """Skip to next track when supported (best-effort)."""

        control_executed = not execute
        if execute:
            try:
                self._controller.next()
                control_executed = True
            except Exception:
                logger.debug("[MEDIA] next delegation failed", exc_info=True)

        refresh_requested = False
        if control_executed:
            refresh_requested = self._request_refresh_after_control()

        self._handle_control_feedback(
            "next",
            source,
            force_refresh=not refresh_requested,
        )

    def previous_track(self, source: str = "manual", execute: bool = True) -> None:
        """Go to previous track when supported (best-effort)."""

        control_executed = not execute
        if execute:
            try:
                self._controller.previous()
                control_executed = True
            except Exception:
                logger.debug("[MEDIA] previous delegation failed", exc_info=True)

        refresh_requested = False
        if control_executed:
            refresh_requested = self._request_refresh_after_control()

        self._handle_control_feedback(
            "prev",
            source,
            force_refresh=not refresh_requested,
        )

    def handle_transport_command(
        self,
        key: str,
        *,
        source: str = "manual",
        execute: bool = True,
    ) -> bool:
        """Normalize and dispatch a transport command.

        Args:
            key: One of ("prev", "previous", "play", "pause", "next").
            source: Diagnostic identifier for logging/metrics.
            execute: When False, skips controller calls but still triggers
                feedback + refresh. Used for external hardware keys that the
                OS already handled.
        Returns:
            True when the command was recognized, False otherwise.
        """

        normalized = self._normalize_control_key(key)
        if normalized is None:
            return False

        if not execute:
            self._consume_matching_keyboard_alias(normalized)
            if self._should_suppress_duplicate_external_transport_feedback(normalized):
                logger.debug(
                    "[MEDIA_WIDGET] Suppressed duplicate external transport feedback: key=%s source=%s",
                    normalized,
                    source,
                )
                return True

        if normalized == "play":
            self.play_pause(source=source, execute=execute)
        elif normalized == "next":
            self.next_track(source=source, execute=execute)
        else:
            self.previous_track(source=source, execute=execute)
        return True

    @staticmethod
    def _normalize_control_key(key: str | None) -> Optional[str]:
        if not key:
            return None
        key_lower = key.lower()
        if key_lower in ("prev", "previous", "back"):
            return "prev"
        if key_lower in ("play", "pause", "toggle", "play_pause"):
            return "play"
        if key_lower in ("next", "forward"):
            return "next"
        return None

    def _handle_control_feedback(self, key: str, source: str, *, force_refresh: bool) -> None:
        if key not in ("prev", "play", "next"):
            logger.debug("[MEDIA_WIDGET][FEEDBACK] Invalid key: %s", key)
            return
        self._last_manual_control = (key, time.monotonic(), source)
        logger.debug("[MEDIA_WIDGET][FEEDBACK] Triggering feedback for %s from %s", key, source)
        self._trigger_controls_feedback(key, source=source)
        if force_refresh:
            self._request_refresh_after_control()

    def _should_defer_keyboard_alias_command(self, source: str, key: str) -> bool:
        """Delay selected keyboard aliases briefly to avoid duplicate OS/global toggles."""
        if source != "keyboard_home":
            return False
        self._arm_keyboard_alias_command(key)
        logger.debug("[MEDIA_WIDGET] Deferred keyboard alias command: source=%s key=%s", source, key)
        return True

    def _arm_keyboard_alias_command(self, key: str) -> None:
        self._clear_pending_keyboard_alias_timer()
        self._pending_keyboard_alias_command = (key, time.monotonic())
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(140)

        def _on_timeout() -> None:
            pending = self._pending_keyboard_alias_command
            self._pending_keyboard_alias_timer = None
            self._pending_keyboard_alias_command = None
            if pending is None:
                return
            pending_key, _pending_started = pending
            logger.debug("[MEDIA_WIDGET] Executing deferred keyboard alias command: key=%s", pending_key)
            self.handle_transport_command(
                pending_key,
                source="keyboard_home_deferred",
                execute=True,
            )

        timer.timeout.connect(_on_timeout)
        self._pending_keyboard_alias_timer = timer
        timer.start()

    def _consume_matching_keyboard_alias(self, key: str) -> None:
        pending = self._pending_keyboard_alias_command
        if pending is None:
            return
        pending_key, pending_started = pending
        if pending_key != key:
            return
        age_ms = (time.monotonic() - pending_started) * 1000.0
        self._clear_pending_keyboard_alias_timer()
        self._pending_keyboard_alias_command = None
        logger.info(
            "[MEDIA_WIDGET] Consumed deferred keyboard alias via external transport ownership: key=%s age_ms=%.1f",
            key,
            age_ms,
        )

    def _clear_pending_keyboard_alias_timer(self) -> None:
        timer = self._pending_keyboard_alias_timer
        self._pending_keyboard_alias_timer = None
        if timer is None:
            return
        try:
            timer.stop()
        except Exception:
            logger.debug("[MEDIA_WIDGET] Failed to stop deferred keyboard alias timer", exc_info=True)
        try:
            timer.deleteLater()
        except Exception:
            logger.debug("[MEDIA_WIDGET] Failed to delete deferred keyboard alias timer", exc_info=True)

    def _should_suppress_duplicate_external_transport_feedback(self, key: str) -> bool:
        """Collapse duplicate execute=False media command bursts from OS/native routes.

        A single physical media-key event can surface through multiple Windows/Qt
        paths (`WM_APPCOMMAND`, media QKeyEvent, raw-input feedback). Those routes
        are all external ownership signals, so the media widget must treat the
        first one as authoritative and ignore immediate duplicates rather than
        toggling PLAYING -> PAUSED -> PLAYING locally.
        """
        now = time.monotonic()
        last_feedback = self._last_external_transport_feedback
        self._last_external_transport_feedback = (key, now)
        if last_feedback is None:
            return False
        last_key, last_ts = last_feedback
        if last_key != key:
            return False
        return (now - last_ts) <= 0.18

    def handle_double_click(self, local_pos) -> bool:
        """Called by WidgetManager dispatch. Refreshes artwork/track info."""
        if not self._enabled:
            return False
        try:
            # Bust GSMTC cache so we actually re-query the controller
            self._gsmtc_cached_result = None
            self._gsmtc_cached_prepared_artwork = None
            self._gsmtc_cached_artwork_generation = 0
            self._gsmtc_cache_ts = 0.0
            # Reset diff gating so update_display doesn't skip the refresh
            self._last_track_identity = None
            self._skipped_identity_updates = 0
            # Keep an existing worker authoritative. Bypassing this guard can
            # invalidate its generation after decode but before UI ownership,
            # causing the same artwork bytes to be decoded again.
            if self._thread_manager is not None:
                self._refresh_async()
            else:
                self._refresh()
            logger.info("[MEDIA_WIDGET] Double-click triggered artwork refresh")
            return True
        except Exception:
            logger.debug("[MEDIA_WIDGET] Double-click refresh failed", exc_info=True)
            return False

    def _request_refresh_after_control(self) -> bool:
        if not self._enabled:
            return False
        try:
            if self._thread_manager is not None:
                self._refresh_async()
            else:
                self._refresh()
            return True
        except Exception:
            logger.debug("[MEDIA] post-control refresh failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Polling and display
    # ------------------------------------------------------------------
    def refresh_playback_state(self) -> None:
        """Public entry point to force a playback state refresh.

        Called externally (e.g. on WM_DISPLAYCHANGE wake) to ensure the
        widget re-evaluates Spotify state and doesn't stay faded out.
        """
        if not self._enabled:
            return
        self._is_idle = False
        self._reset_poll_stage()
        # A wake/display-change refresh must not overlap an existing query.
        # The in-flight result already reconciles playback state and artwork.
        if self._thread_manager is not None:
            self._refresh_async()

    def _refresh(self) -> None:
        if not self._enabled:
            return
        
        # Smart polling: when idle, still poll but at slower rate to detect Spotify opening
        # This allows the widget to spawn when Spotify opens
        if self._is_idle:
            if is_perf_metrics_enabled():
                logger.debug("[PERF] Media widget idle poll (detecting Spotify open)")
        
        if self._thread_manager is not None:
            if is_perf_metrics_enabled():
                interval = self._poll_intervals[self._current_poll_stage]
                logger.debug("[PERF] Media widget poll triggered (%dms interval)", interval)
            elif is_verbose_logging():
                logger.debug("[MEDIA_WIDGET] Scheduling async refresh via ThreadManager")
            self._refresh_async()
            return

        # PERFORMANCE FIX: When ThreadManager is unavailable, skip the blocking
        # get_current_track() call entirely. The WinRT/GSMTC API uses
        # asyncio.run_until_complete() which can block the UI thread for up to
        # 2 seconds. Better to show stale/no data than to freeze the UI.
        if not self._telemetry_logged_missing_tm:
            logger.warning("[MEDIA_WIDGET] ThreadManager unavailable; skipping blocking refresh (widget hidden)")
            self._telemetry_logged_missing_tm = True
        elif is_verbose_logging():
            logger.debug("[MEDIA_WIDGET] No ThreadManager available, skipping blocking refresh")
        # Don't call get_current_track() synchronously - it blocks!

    def _reconcile_refresh_playback_epoch(
        self,
        info: Optional[MediaTrackInfo],
        refresh_epoch: int,
    ) -> Optional[MediaTrackInfo]:
        """Reconcile one backend snapshot with bounded command-state ownership.

        A refresh that STARTED before a transport command reflects pre-command
        reality. If a command advanced the playback epoch while the query was in
        flight, that result's playback state is stale and must not reverse the
        optimistic post-command state. A refresh started after the command may
        confirm immediately, but a contradictory same-epoch state is pinned until
        the confirmation deadline expires. Non-state fields still apply while a
        playback state is pinned.
        """
        if info is None:
            return info
        try:
            result_epoch = int(refresh_epoch)
            current_epoch = int(getattr(self, "_playback_epoch", 0))
        except Exception:
            return info

        expected_state = getattr(self, "_expected_playback_state", None)
        expected_epoch = getattr(self, "_expected_playback_epoch", None)

        if result_epoch == current_epoch:
            if expected_state is None or expected_epoch != current_epoch:
                return info
            try:
                if info.state == expected_state:
                    self._reset_playback_confirmation(delete_timer=True)
                    logger.debug(
                        "[MEDIA_WIDGET] Playback state confirmed: state=%s epoch=%s",
                        getattr(info.state, "value", info.state),
                        current_epoch,
                    )
                    return info
            except Exception:
                return info

            deadline = float(
                getattr(self, "_playback_confirmation_deadline_monotonic", 0.0) or 0.0
            )
            if time.monotonic() >= deadline:
                self._reset_playback_confirmation(delete_timer=True)
                logger.debug(
                    "[MEDIA_WIDGET] Playback confirmation expired; accepting state=%s epoch=%s",
                    getattr(info.state, "value", info.state),
                    current_epoch,
                )
                return info
            pin_reason = "unconfirmed same-epoch"
            state_to_preserve = expected_state
        else:
            # An older query can never confirm or reverse a later command. Prefer
            # the live expectation; after it is released, preserve the current
            # accepted playback state while still taking metadata from the result.
            current = (
                getattr(self._last_info, "state", None)
                if self._last_info is not None
                else None
            )
            state_to_preserve = expected_state if expected_state is not None else current
            if state_to_preserve is None:
                return info
            pin_reason = "stale pre-command"

        try:
            if info.state == state_to_preserve:
                return info
            from dataclasses import replace
            pinned = replace(info, state=state_to_preserve)
        except Exception:
            logger.debug("[MEDIA_WIDGET] Failed to pin stale playback state", exc_info=True)
            return info
        logger.debug(
            "[MEDIA_WIDGET] Rejected %s playback state %s; pinned to %s "
            "(refresh_epoch=%s current_epoch=%s)",
            pin_reason,
            getattr(info.state, "value", info.state),
            getattr(state_to_preserve, "value", state_to_preserve),
            refresh_epoch,
            current_epoch,
        )
        return pinned

    def _refresh_async(self) -> None:
        # Desync: Check GSMTC cache first to reduce IO contention
        now = time.time()
        refresh_started_monotonic = time.monotonic()
        # Capture the freshness epoch this refresh begins under, so a transport
        # command that lands while the query is in flight can reject this result's
        # stale pre-command playback state.
        refresh_playback_epoch = int(getattr(self, "_playback_epoch", 0))
        if self._gsmtc_cached_result is not None:
            elapsed_ms = (now - self._gsmtc_cache_ts) * 1000
            if elapsed_ms < self._gsmtc_cache_ms:
                if is_perf_metrics_enabled():
                    logger.debug("[PERF] MediaWidget: using cached GSMTC result (age=%.0fms)", elapsed_ms)
                self._update_display(
                    self._gsmtc_cached_result,
                    self._gsmtc_cached_prepared_artwork,
                    self._gsmtc_cached_artwork_generation,
                )
                return
        
        if self._refresh_in_flight:
            return
        tm = self._thread_manager
        if tm is None:
            try:
                self._inherit_thread_manager_from_parent(self.parent())
            except Exception as exc:
                logger.debug("[MEDIA_WIDGET] Failed to inherit ThreadManager: %s", exc)
            tm = self._thread_manager
            if tm is None:
                return

        fallback_info = None
        try:
            fallback_info = type(self)._get_shared_valid_info()
        except Exception:
            fallback_info = None
        if fallback_info is None:
            try:
                fallback_info = self.get_retained_display_info()
            except Exception:
                fallback_info = None
        if fallback_info is None:
            fallback_info = self._last_info
        fallback_artwork = (
            getattr(fallback_info, "artwork", None)
            if fallback_info is not None
            else None
        )

        self._artwork_update_generation += 1
        artwork_generation = self._artwork_update_generation
        pending_artwork = self._pending_artwork
        known_artwork_keys = frozenset(
            key
            for key in (
                self._applied_artwork_key,
                pending_artwork.key if pending_artwork is not None else None,
            )
            if key is not None
        )
        self._refresh_in_flight = True
        self._refresh_in_flight_generation = artwork_generation
        artwork_owner_id = f"{id(self):x}"
        artwork_provider = self._provider
        provider_generation = self._provider_generation
        query_controller = self._controller
        if is_verbose_logging():
            logger.debug("[MEDIA_WIDGET] Async refresh started")

        def _do_query():
            worker_started_monotonic = time.monotonic()
            failover_candidates = get_provider_failover_candidates(artwork_provider)
            allow_failover = bool(failover_candidates) and (
                self.should_probe_provider_failover()
                and not type(self)._has_fresh_shared_info_cache()
            )
            selected_provider = None
            try:
                worker_query = getattr(
                    query_controller,
                    "get_current_track_from_io_worker",
                    None,
                )
                if callable(worker_query):
                    selected_provider, info = worker_query(
                        failover_candidates if allow_failover else (),
                    )
                else:
                    info = query_controller.get_current_track()
                    if info is not None:
                        selected_provider = artwork_provider
            except Exception:
                logger.debug("[MEDIA] get_current_track failed", exc_info=True)
                if is_verbose_logging():
                    logger.debug("[MEDIA] get_current_track failed", exc_info=True)
                info = None

            selected_provider = normalize_provider_id(selected_provider)
            if allow_failover and selected_provider != artwork_provider:
                self.mark_provider_probe_attempt()
            failover_provider = (
                selected_provider
                if selected_provider is not None and selected_provider != artwork_provider
                else None
            )

            artwork_payload = (
                getattr(info, "artwork", None)
                if info is not None
                else fallback_artwork
            )
            artwork_key = type(self)._compute_artwork_payload_key(artwork_payload)
            prepared = type(self)._prepare_artwork_payload(
                artwork_payload,
                artwork_key,
                known_artwork_keys=(
                    frozenset()
                    if failover_provider is not None
                    else known_artwork_keys
                ),
            )
            if (
                is_perf_metrics_enabled()
                and artwork_key != (0, "")
                and artwork_key not in known_artwork_keys
            ):
                logger.info(
                    "[PERF][MEDIA_ARTWORK] event=decoded owner_id=%s provider=%s "
                    "key_id=%s generation=%d payload_bytes=%d decode_ms=%.2f "
                    "decode_ok=%s",
                    artwork_owner_id,
                    artwork_provider,
                    type(self)._artwork_key_log_id(artwork_key),
                    artwork_generation,
                    int(artwork_key[0]),
                    float(prepared.decode_ms),
                    prepared.image is not None and not prepared.image.isNull(),
                )
            return (
                info,
                prepared,
                artwork_generation,
                worker_started_monotonic,
                time.monotonic(),
                failover_provider,
                provider_generation,
            )

        def _handle_result(task_result):
            callback_received_monotonic = time.monotonic()

            def _consume_result() -> None:
                try:
                    if not Shiboken.isValid(self):
                        return
                    if not self._enabled:
                        return
                    result_payload = task_result.result if getattr(task_result, "success", False) else None
                    if isinstance(result_payload, tuple) and len(result_payload) == 7:
                        (
                            info,
                            prepared_artwork,
                            result_generation,
                            worker_started,
                            worker_finished,
                            failover_provider,
                            result_provider_generation,
                        ) = result_payload
                    else:
                        info = result_payload
                        prepared_artwork = PreparedArtwork((0, ""), None, 0.0)
                        result_generation = artwork_generation
                        worker_started = refresh_started_monotonic
                        worker_finished = callback_received_monotonic
                        failover_provider = None
                        result_provider_generation = self._provider_generation
                    if int(result_generation) != self._artwork_update_generation:
                        return
                    if int(result_provider_generation) != self._provider_generation:
                        return
                    # Reject a stale pre-command playback state before it can
                    # reverse an optimistic transport edge that landed while this
                    # query was in flight.
                    info = self._reconcile_refresh_playback_epoch(
                        info, refresh_playback_epoch
                    )
                    if failover_provider is not None:
                        self._apply_provider_failover(failover_provider)
                    runtime_provider = failover_provider or artwork_provider
                    manager = self._widget_manager
                    if manager is not None and hasattr(
                        manager,
                        "sync_media_volume_runtime_target",
                    ):
                        try:
                            manager.sync_media_volume_runtime_target(
                                runtime_provider,
                                getattr(info, "source_app_user_model_id", "")
                                if info is not None
                                else "",
                            )
                        except Exception:
                            logger.debug(
                                "[MEDIA_WIDGET] Failed to sync accepted volume target",
                                exc_info=True,
                            )
                    # Desync: Cache the result for 500ms
                    self._gsmtc_cached_result = info
                    self._gsmtc_cached_prepared_artwork = prepared_artwork
                    self._gsmtc_cached_artwork_generation = int(result_generation)
                    self._gsmtc_cache_ts = time.time()
                    self._update_display(info, prepared_artwork, int(result_generation))
                    if is_perf_metrics_enabled():
                        consumed_monotonic = time.monotonic()
                        worker_ms = max(0.0, (worker_finished - worker_started) * 1000.0)
                        callback_ms = max(0.0, (callback_received_monotonic - worker_finished) * 1000.0)
                        ui_delay_ms = max(0.0, (consumed_monotonic - callback_received_monotonic) * 1000.0)
                        total_ms = max(0.0, (consumed_monotonic - refresh_started_monotonic) * 1000.0)
                        if total_ms >= 1000.0 or worker_ms >= 1000.0 or ui_delay_ms >= 250.0:
                            state = getattr(info, "state", None)
                            state_value = getattr(state, "value", str(state))
                            logger.warning(
                                "[PERF][MEDIA_WIDGET][REFRESH] slow async refresh "
                                "total_ms=%.1f worker_ms=%.1f callback_ms=%.1f "
                                "ui_delay_ms=%.1f in_flight=%s state=%s",
                                total_ms,
                                worker_ms,
                                callback_ms,
                                ui_delay_ms,
                                self._refresh_in_flight,
                                state_value,
                            )
                except Exception as exc:
                    logger.debug("[MEDIA_WIDGET] Exception during async refresh consume: %s", exc)
                finally:
                    if self._refresh_in_flight_generation == artwork_generation:
                        self._refresh_in_flight = False

            try:
                ThreadManager.run_on_ui_thread(_consume_result)
            except Exception as exc:
                logger.debug("[MEDIA_WIDGET] Failed to marshal async refresh to UI thread: %s", exc)
                if self._refresh_in_flight_generation == artwork_generation:
                    self._refresh_in_flight = False

        try:
            tm.submit_io_task(_do_query, callback=_handle_result)
        except Exception as exc:
            logger.debug("[MEDIA_WIDGET] Failed to submit async refresh: %s", exc)
            if self._refresh_in_flight_generation == artwork_generation:
                self._refresh_in_flight = False

    def _emit_media_update(self, info: MediaTrackInfo) -> None:
        """Emit the current media metadata/state to interested observers."""
        try:
            self._perf_media_emit_count += 1
            self._perf_media_emit_total += 1
            payload = asdict(info)
            payload["state"] = info.state.value
            self.media_updated.emit(payload)
            self._maybe_log_media_perf_emit(info)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Failed to emit media update: %s", e)

    def _maybe_log_media_perf_emit(self, info: MediaTrackInfo) -> None:
        if not is_perf_metrics_enabled():
            return
        now = time.monotonic()
        elapsed = now - self._perf_media_last_log_ts
        if elapsed < 10.0:
            return
        parent = self.parent()
        screen = getattr(parent, "_screen_index", None)
        try:
            screen_repr = int(screen) if screen is not None else "<unknown>"
        except Exception:
            screen_repr = "<unknown>"
        state = getattr(info, "state", None)
        state_value = getattr(state, "value", str(state))
        logger.info(
            "[PERF][MEDIA_WIDGET] emit_media_update screen=%s provider=%s state=%s "
            "elapsed_ms=%.1f emits=%d visible=%s",
            screen_repr,
            self._provider,
            state_value,
            elapsed * 1000.0,
            self._perf_media_emit_count,
            self.isVisible(),
        )
        self._perf_media_emit_count = 0
        self._perf_media_last_log_ts = now

    def _update_display(
        self,
        info: Optional[MediaTrackInfo],
        prepared_artwork: PreparedArtwork | None = None,
        artwork_generation: int | None = None,
    ) -> None:
        """Delegates to widgets.media.display_update."""
        from widgets.media.display_update import update_display
        update_display(
            self,
            info,
            prepared_artwork=prepared_artwork,
            artwork_generation=artwork_generation,
        )

    @staticmethod
    def _decode_artwork_image(artwork: Optional[bytes]) -> QImage | None:
        """Decode artwork into a worker-safe QImage without touching GUI state."""
        if not artwork:
            return None
        try:
            data = bytes(artwork)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Invalid artwork payload: %s", e)
            return None

        # Log payload diagnostics for debugging artwork decode issues
        header_hex = data[:16].hex() if len(data) >= 16 else data.hex()
        logger.debug(
            "[MEDIA_WIDGET] Artwork decode: %d bytes, header=%s",
            len(data), header_hex,
        )

        try:
            byte_array = QByteArray(data)
            buffer = QBuffer(byte_array)
            if not buffer.open(QBuffer.OpenModeFlag.ReadOnly):
                logger.debug("[MEDIA_WIDGET] Failed to open artwork buffer (%d bytes)", len(data))
                return None

            reader = QImageReader(buffer)
            reader.setAutoTransform(True)
            image = reader.read()
            buffer.close()
            if image is None or image.isNull():
                logger.debug("[MEDIA_WIDGET] QImageReader returned null image (%d bytes)", len(data))
                return None
        except MemoryError:
            logger.error("[MEDIA_WIDGET] Out of memory decoding artwork", exc_info=True)
            return None
        except Exception:
            logger.debug("[MEDIA_WIDGET] Failed to decode artwork pixmap", exc_info=True)
            return None

        if image.width() <= 0 or image.height() <= 0:
            logger.debug(
                "[MEDIA_WIDGET] Decoded image has zero dimensions: %dx%d",
                image.width(),
                image.height(),
            )
            return None
        return image

    @staticmethod
    def _prepare_artwork_payload(
        artwork: Optional[bytes],
        key: tuple[int, str],
        *,
        known_artwork_keys: frozenset[tuple[int, str]],
    ) -> PreparedArtwork:
        """Decode a changed artwork key once inside the media query worker."""

        if key in known_artwork_keys or key == (0, ""):
            return PreparedArtwork(key=key, image=None, decode_ms=0.0)

        decode_started = time.monotonic()
        image = MediaWidget._decode_artwork_image(artwork)
        decode_ms = max(0.0, (time.monotonic() - decode_started) * 1000.0)
        return PreparedArtwork(key=key, image=image, decode_ms=decode_ms)

    def _decode_artwork_pixmap(self, artwork: Optional[bytes]) -> Optional[QPixmap]:
        """Emergency/test fallback; normal refreshes decode QImage in the worker."""

        image = MediaWidget._decode_artwork_image(artwork)
        if image is None or image.isNull():
            return None
        pm = QPixmap.fromImage(image)
        if pm.isNull():
            logger.debug("[MEDIA_WIDGET] Decoded pixmap is null")
            return None
        if pm.width() <= 0 or pm.height() <= 0:
            logger.debug("[MEDIA_WIDGET] Decoded pixmap has zero dimensions: %dx%d", pm.width(), pm.height())
            return None
        try:
            pm.setDevicePixelRatio(1.0)
        except Exception:
            logger.debug("[MEDIA_WIDGET] Failed to normalize artwork DPR", exc_info=True)
        logger.debug("[MEDIA_WIDGET] Artwork decoded OK: %dx%d", pm.width(), pm.height())
        return pm

    @staticmethod
    def _create_artwork_pixmap(image: QImage) -> QPixmap | None:
        """Create the sole GUI-owned representation for a prepared image."""

        pm = QPixmap.fromImage(image)
        if pm.isNull() or pm.width() <= 0 or pm.height() <= 0:
            return None
        pm.setDevicePixelRatio(1.0)
        return pm

    @classmethod
    def _has_transition_work_on_any_display(cls) -> bool:
        """Return whether any live display is preparing or running a transition."""

        try:
            from rendering.display_widget import DisplayWidget

            displays = list(DisplayWidget.get_all_instances())
        except Exception:
            logger.debug(
                "[MEDIA_WIDGET] Failed to inspect displays before artwork apply",
                exc_info=True,
            )
            return False

        for display in displays:
            try:
                if not Shiboken.isValid(display):
                    continue
                checker = getattr(display, "has_transition_work_pending", None)
                if callable(checker) and bool(checker()):
                    return True
            except RuntimeError:
                continue
            except Exception:
                logger.debug(
                    "[MEDIA_WIDGET] Failed to inspect display transition state",
                    exc_info=True,
                )
        return False

    @staticmethod
    def _artwork_key_log_id(key: tuple[int, str] | None) -> str:
        if key is None:
            return "none"
        digest = str(key[1] or "")
        return digest[:12] if digest else "empty"

    def _log_artwork_lifecycle_event(
        self,
        event: str,
        *,
        reason: str,
        prepared: PreparedArtwork | None = None,
        generation: int | None = None,
        replaced_key: tuple[int, str] | None = None,
    ) -> None:
        """Emit one bounded, key-stable record for a material artwork event."""

        if not is_perf_metrics_enabled():
            return
        current = prepared or self._pending_artwork
        key = current.key if current is not None else None
        logger.info(
            "[PERF][MEDIA_ARTWORK] event=%s reason=%s key_id=%s "
            "payload_bytes=%d generation=%d current_generation=%d "
            "replaced_key_id=%s decode_ms=%.2f coalesced_count=%d",
            event,
            reason,
            self._artwork_key_log_id(key),
            int(key[0]) if key is not None else 0,
            int(generation or 0),
            int(self._artwork_update_generation),
            self._artwork_key_log_id(replaced_key),
            float(current.decode_ms) if current is not None else 0.0,
            int(self._artwork_coalesced_count),
        )

    def _queue_pending_artwork(
        self,
        prepared: PreparedArtwork,
        generation: int,
    ) -> None:
        existing = self._pending_artwork
        if existing is not None:
            if existing.key == prepared.key:
                # Same-key metadata churn is not a coalesced artwork change.
                # Preserve an already decoded image when the worker correctly
                # skipped another decode, while promoting the track generation.
                if prepared.image is not None:
                    self._pending_artwork = prepared
                self._pending_artwork_generation = generation
                self._pending_artwork_deferred = True
                return
            self._artwork_coalesced_count += 1
            self._log_artwork_lifecycle_event(
                "replaced",
                reason="newer_transition_key",
                prepared=prepared,
                generation=generation,
                replaced_key=existing.key,
            )
        else:
            self._log_artwork_lifecycle_event(
                "queued",
                reason="transition_active",
                prepared=prepared,
                generation=generation,
            )

        self._pending_artwork = prepared
        self._pending_artwork_generation = generation
        self._pending_artwork_deferred = True

    def _accept_prepared_artwork(
        self,
        prepared: PreparedArtwork | None,
        generation: int | None,
        *,
        refresh_layout_after_apply: bool,
    ) -> bool:
        """Apply a current result now or retain only its newest transition-safe form."""

        if prepared is None or generation is None:
            return False
        generation = int(generation)
        if generation != self._artwork_update_generation:
            self._log_artwork_lifecycle_event(
                "discarded",
                reason="stale_accept_generation",
                prepared=prepared,
                generation=generation,
            )
            return False

        if prepared.key == self._applied_artwork_key:
            pending = self._pending_artwork
            if pending is not None:
                reverted_to_applied_key = pending.key != prepared.key
                if reverted_to_applied_key:
                    self._artwork_coalesced_count += 1
                    self._log_artwork_lifecycle_event(
                        "discarded",
                        reason="reverted_to_applied_key",
                        prepared=pending,
                        generation=self._pending_artwork_generation,
                        replaced_key=pending.key,
                    )
                self._pending_artwork = None
                self._pending_artwork_generation = 0
                self._pending_artwork_deferred = False
                self._artwork_coalesced_count = 0
            return False

        pending = self._pending_artwork
        was_deferred = False
        if pending is not None and pending.key == prepared.key:
            was_deferred = bool(self._pending_artwork_deferred)
            if prepared.image is None:
                prepared = pending

        if type(self)._has_transition_work_on_any_display():
            self._queue_pending_artwork(prepared, generation)
            return False

        return self._apply_prepared_artwork_now(
            prepared,
            generation,
            deferred_for_transition=was_deferred,
            refresh_layout_after_apply=refresh_layout_after_apply,
        )

    def _apply_prepared_artwork_now(
        self,
        prepared: PreparedArtwork,
        generation: int,
        *,
        deferred_for_transition: bool,
        refresh_layout_after_apply: bool,
    ) -> bool:
        """Perform the one permitted UI-thread QImage -> QPixmap handoff."""

        if generation != self._artwork_update_generation:
            self._log_artwork_lifecycle_event(
                "discarded",
                reason="stale_apply_generation",
                prepared=prepared,
                generation=generation,
            )
            return False
        key_changed = prepared.key != self._applied_artwork_key
        if not key_changed:
            return False

        ui_started = time.monotonic()
        pixmap: QPixmap | None = None
        if prepared.key != (0, "") and prepared.image is not None and not prepared.image.isNull():
            try:
                pixmap = self._create_artwork_pixmap(prepared.image)
            except Exception:
                logger.debug(
                    "[MEDIA_WIDGET] Failed to create UI artwork pixmap",
                    exc_info=True,
                )
                pixmap = None
        ui_pixmap_ms = max(0.0, (time.monotonic() - ui_started) * 1000.0)

        self._artwork_pixmap = pixmap
        self._applied_artwork_key = prepared.key
        self._scaled_artwork_cache = None
        self._scaled_artwork_cache_key = None

        if self._pending_artwork is not None:
            if self._pending_artwork.key != prepared.key:
                self._artwork_coalesced_count += 1
                self._log_artwork_lifecycle_event(
                    "discarded",
                    reason="superseded_by_applied_key",
                    prepared=self._pending_artwork,
                    generation=self._pending_artwork_generation,
                    replaced_key=self._pending_artwork.key,
                )
            self._pending_artwork = None
            self._pending_artwork_generation = 0
            self._pending_artwork_deferred = False

        fade_started = False
        if pixmap is not None:
            # The card owns startup visibility.  Artwork prepared before the
            # coordinated card reveal must remain hidden until that reveal
            # completes, then receive its own authored fade.
            self._artwork_opacity = 0.0
            fade_started = self._start_artwork_fade_if_ready(
                reason="artwork_apply",
            )
        else:
            self._artwork_opacity = 1.0

        if refresh_layout_after_apply:
            try:
                from widgets.media.display_update import refresh_artwork_layout

                refresh_artwork_layout(self)
            except Exception:
                logger.debug(
                    "[MEDIA_WIDGET] Failed to refresh deferred artwork layout",
                    exc_info=True,
                )
                self._safe_update()

        if is_perf_metrics_enabled():
            logger.info(
                "[PERF][MEDIA_ARTWORK] event=applied key_changed=%s key_id=%s "
                "generation=%d payload_bytes=%d "
                "decode_ms=%.2f ui_pixmap_ms=%.2f deferred_for_transition=%s "
                "coalesced_count=%d pixmap_ready=%s fade_started=%s",
                key_changed,
                self._artwork_key_log_id(prepared.key),
                generation,
                int(prepared.key[0]),
                float(prepared.decode_ms),
                ui_pixmap_ms,
                bool(deferred_for_transition),
                int(self._artwork_coalesced_count),
                pixmap is not None,
                fade_started,
            )
        self._artwork_coalesced_count = 0
        self._safe_update()
        return True

    @classmethod
    def _flush_pending_artwork_when_all_displays_idle(cls) -> None:
        """Flush newest-only artwork for every display once all transitions are idle."""

        if cls._has_transition_work_on_any_display():
            return

        for widget in list(cls._instances):
            try:
                if not Shiboken.isValid(widget):
                    prepared = getattr(widget, "_pending_artwork", None)
                    if prepared is not None:
                        widget._log_artwork_lifecycle_event(
                            "discarded",
                            reason="widget_destroyed",
                            prepared=prepared,
                            generation=widget._pending_artwork_generation,
                        )
                    widget._pending_artwork = None
                    widget._pending_artwork_generation = 0
                    widget._pending_artwork_deferred = False
                    cls._instances.discard(widget)
                    continue
            except Exception:
                continue

            prepared = widget._pending_artwork
            generation = int(widget._pending_artwork_generation)
            if prepared is None:
                # Artwork may already be GUI-owned but still hidden behind the
                # coordinated card reveal.  If a transition overlapped reveal
                # completion, transition idle is the remaining handoff.
                widget._start_artwork_fade_if_ready(reason="all_displays_idle")
                continue
            if generation != widget._artwork_update_generation:
                current_generation_in_flight = bool(
                    widget._refresh_in_flight
                    and widget._refresh_in_flight_generation
                    == widget._artwork_update_generation
                )
                if current_generation_in_flight:
                    # The current query deliberately skipped decoding this
                    # pending key. Keep its sole decoded QImage until that
                    # query identifies whether the key is still authoritative;
                    # its UI consumer will then promote or replace it.
                    widget._log_artwork_lifecycle_event(
                        "retained",
                        reason="awaiting_current_generation",
                        prepared=prepared,
                        generation=generation,
                    )
                    continue
                widget._log_artwork_lifecycle_event(
                    "discarded",
                    reason="stale_idle_flush_generation",
                    prepared=prepared,
                    generation=generation,
                )
                widget._pending_artwork = None
                widget._pending_artwork_generation = 0
                widget._pending_artwork_deferred = False
                continue
            if cls._has_transition_work_on_any_display():
                return
            widget._log_artwork_lifecycle_event(
                "flushing",
                reason="all_displays_idle",
                prepared=prepared,
                generation=generation,
            )
            widget._apply_prepared_artwork_now(
                prepared,
                generation,
                deferred_for_transition=True,
                refresh_layout_after_apply=True,
            )

    def on_parent_transition_work_pending(self, pending: bool) -> None:
        if pending:
            return
        type(self)._flush_pending_artwork_when_all_displays_idle()

    def _discard_pending_artwork(self) -> None:
        """Invalidate worker generations and release any unconsumed QImage."""

        if self._pending_artwork is not None:
            self._log_artwork_lifecycle_event(
                "discarded",
                reason="widget_lifecycle_cleanup",
                generation=self._pending_artwork_generation,
            )
        self._artwork_update_generation += 1
        self._pending_artwork = None
        self._pending_artwork_generation = 0
        self._pending_artwork_deferred = False
        self._artwork_coalesced_count = 0
        self._gsmtc_cached_prepared_artwork = None
        self._gsmtc_cached_artwork_generation = 0
        self._refresh_in_flight = False

    def _clear_artwork_for_missing_media(self) -> None:
        """Clear artwork exactly once when the retained media card is abandoned."""

        self._accept_prepared_artwork(
            PreparedArtwork((0, ""), None, 0.0),
            self._artwork_update_generation,
            refresh_layout_after_apply=False,
        )
    
    def _controls_row_min_height(self) -> int:
        """Return the minimum vertical footprint required for the controls row."""
        from widgets.media_layout import _controls_compact_scale

        compact_scale = _controls_compact_scale(self)
        controls_font_pt = max(8, int((self._font_size - 2) * 0.9 * compact_scale))
        font = QFont(self._font_family, controls_font_pt, QFont.Weight.Medium)
        fm = QFontMetrics(font)
        # Inner padding mirrors _compute_controls_layout to keep visuals consistent.
        min_height = max(22, fm.height() + 10)
        return max(20, int(min_height * 0.82))
    
    def _controls_row_margin(self) -> int:
        """Bottom margin that keeps controls breathing room above the card edge."""
        return max(10, int(self._controls_row_min_height() * 0.35))

    def _playback_progress_lane_height(self) -> int:
        """Return the reserved lane above controls for the optional pill bar."""

        if not (self._show_controls and self._playback_progress_enabled):
            return 0
        return self._playback_progress_height + max(10, self._playback_progress_height // 2 + 6)

    def _controls_reserved_height(self) -> int:
        """Return the full fixed-card footprint owned by transport presentation."""

        if not self._show_controls:
            return 0
        return self._controls_row_min_height() + self._playback_progress_lane_height()

    def _apply_controls_reserved_height_delta(self, old_height: int, new_height: int) -> None:
        """Resize an established anchored card without mutating CUSTOM geometry."""

        delta = int(new_height) - int(old_height)
        if delta == 0 or self._fixed_card_height is None:
            return
        if self._active_custom_layout_rect() is not None:
            return
        self._fixed_card_height = max(220, int(self._fixed_card_height) + delta)
        try:
            self.setMinimumHeight(int(self._fixed_card_height))
            self.setMaximumHeight(int(self._fixed_card_height))
            self.updateGeometry()
        except Exception as exc:
            logger.debug("[MEDIA_WIDGET] Failed to apply controls height delta: %s", exc)
    
    def _compute_controls_layout(self):
        """Delegates to widgets.media_layout."""
        from widgets.media_layout import compute_controls_layout
        return compute_controls_layout(self)

    def resolve_control_hit(self, point: QPoint) -> Optional[str]:
        """Return the control key for a local point, if any."""

        layout = self._compute_controls_layout()
        if layout is None:
            return None
        hit_rects = layout.get("hit_rects") or {}
        for key, rect in hit_rects.items():
            if rect.contains(point):
                return key
        return None
    
    def _paint_controls_row(self, painter) -> None:
        """Delegates to widgets.media.painting."""
        from widgets.media.painting import paint_controls_row
        paint_controls_row(self, painter)

    def _draw_control_icon(self, painter, rect, key: str) -> None:
        """Delegates to widgets.media.painting."""
        from widgets.media.painting import draw_control_icon
        draw_control_icon(self, painter, rect, key)
    
    def _compute_track_identity(self, info: MediaTrackInfo) -> tuple:
        """Compute track identity for diff gating."""
        return (
            (info.title or "").strip().lower(),
            (info.artist or "").strip().lower(),
            (info.album or "").strip().lower(),
            getattr(info.state, "value", info.state),
            self._compute_artwork_key(info),
        )

    def _compute_metadata_identity(self, info: MediaTrackInfo) -> tuple:
        """Compute the visible text/layout identity for media metadata.

        Album, playback state, and artwork churn must not cause a relayout when
        the user-visible title/artist/provider presentation is unchanged.
        """
        return (
            smart_title_case((info.title or "").strip()).lower(),
            smart_title_case((info.artist or "").strip()).lower(),
            int(self._font_size),
            str(self.provider_display_name or "").strip().lower(),
        )

    @staticmethod
    def _compute_artwork_payload_key(payload: Optional[bytes]) -> tuple[int, str]:
        if not payload:
            return (0, "")
        try:
            data = bytes(payload)
            length = len(data)
            sample = data[:4096]
            digest = hashlib.sha1(sample).hexdigest()
            return (length, digest)
        except Exception as exc:
            logger.debug("[MEDIA_WIDGET] Failed to compute artwork key: %s", exc)
            return (0, "")

    def _compute_artwork_key(self, info: MediaTrackInfo) -> tuple[int, str]:
        return self._compute_artwork_payload_key(getattr(info, "artwork", None))
    
    def _reset_poll_stage(self) -> None:
        """Reset polling to fastest interval."""
        if self._current_poll_stage == 0:
            return
        self._current_poll_stage = 0
        self._polls_at_current_stage = 0
        self._ensure_timer(force=True)
        if is_perf_metrics_enabled():
            logger.debug("[PERF] Media widget reset to fast poll (%dms)", self._poll_intervals[0])
    
    def _advance_poll_stage(self) -> None:
        """Advance to next slower polling interval."""
        if self._current_poll_stage >= len(self._poll_intervals) - 1:
            return
        self._current_poll_stage += 1
        self._polls_at_current_stage = 0
        self._ensure_timer(force=True)
        if is_perf_metrics_enabled():
            interval = self._poll_intervals[self._current_poll_stage]
            logger.debug("[PERF] Media widget advanced to %dms poll interval", interval)
    
    def _stop_timer(self) -> None:
        """Stop the update timer."""
        self._reset_update_timer_state(delete_qtimer=False)

    def _ensure_timer(self, *, force: bool = False) -> None:
        """Ensure update timer is running at correct interval."""
        if self._is_idle:
            interval = self._deep_idle_poll_interval if not self._app_process_running else self._idle_poll_interval
        else:
            interval = self._poll_intervals[self._current_poll_stage]

        timer = self._update_timer
        if self._update_timer_handle is not None and timer is not None:
            try:
                if timer.isActive():
                    if not force and self._update_timer_interval_ms == interval:
                        return
                    timer.setInterval(max(1, int(interval)))
                    timer.start()
                    self._update_timer_interval_ms = interval
                    if is_perf_metrics_enabled():
                        logger.debug(
                            "[PERF] Media widget timer retuned in place to %dms (stage %d)",
                            interval,
                            self._current_poll_stage,
                        )
                    return
            except RuntimeError:
                timer = None
            except Exception as exc:
                logger.debug("[MEDIA_WIDGET][TIMER] In-place retune failed; recreating timer: %s", exc)

        if force:
            self._stop_timer()

        if not self._ensure_thread_manager("MediaWidget._ensure_timer"):
            if not self._telemetry_logged_missing_tm:
                logger.warning("[MEDIA_WIDGET][TIMER] ThreadManager unavailable; media polling paused")
                self._telemetry_logged_missing_tm = True
            return

        self._telemetry_logged_missing_tm = False
        try:
            handle = create_overlay_timer(self, interval, self._refresh, description="MediaWidget smart poll")
        except RuntimeError as exc:
            logger.warning("[MEDIA_WIDGET][TIMER] Failed to schedule poll timer: %s", exc)
            return
        self._update_timer_handle = handle
        try:
            self._update_timer = getattr(handle, "_timer", None)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            self._update_timer = None
        self._update_timer_interval_ms = interval
        if is_perf_metrics_enabled():
            logger.debug("[PERF] Media widget timer started/restarted at %dms (stage %d)", interval, self._current_poll_stage)
    
    @classmethod
    def _get_shared_valid_info(cls) -> Optional[MediaTrackInfo]:
        """Get shared media info if another widget has valid data.
        
        Prevents multi-display desync where one widget gets None from GSMTC
        while another still has valid media info.
        """
        now = time.monotonic()
        
        # Check shared cache first
        if cls._shared_last_valid_info is not None:
            age = now - cls._shared_last_valid_info_ts
            if age < cls._shared_info_max_age_sec:
                return cls._shared_last_valid_info
        
        # Fallback: check other widget instances
        for instance in list(cls._instances):
            try:
                if not Shiboken.isValid(instance):
                    continue
                if instance._last_info is not None and instance.isVisible():
                    cls._shared_last_valid_info = instance._last_info
                    cls._shared_last_valid_info_ts = now
                    return instance._last_info
            except Exception:
                continue
        
        return None

    @classmethod
    def _has_fresh_shared_info_cache(cls) -> bool:
        """Worker-safe check that avoids a redundant cross-provider probe."""

        info = cls._shared_last_valid_info
        if info is None:
            return False
        return (time.monotonic() - cls._shared_last_valid_info_ts) < cls._shared_info_max_age_sec
    
    # ------------------------------------------------------------------
    # Shared Feedback System — delegates to widgets.media.feedback
    # ------------------------------------------------------------------

    @classmethod
    def _ensure_shared_feedback_timer(cls) -> None:
        from widgets.media.feedback import ensure_shared_feedback_timer
        ensure_shared_feedback_timer(cls)

    @classmethod
    def _maybe_stop_shared_feedback_timer(cls) -> None:
        from widgets.media.feedback import maybe_stop_shared_feedback_timer
        maybe_stop_shared_feedback_timer(cls)

    @classmethod
    def _on_shared_feedback_tick(cls) -> None:
        from widgets.media.feedback import on_shared_feedback_tick
        on_shared_feedback_tick(cls)

    def _process_feedback_tick(self, now: float) -> bool:
        from widgets.media.feedback import process_feedback_tick
        return process_feedback_tick(self, now)

    def _trigger_controls_feedback(self, key: str, source: str = "manual") -> None:
        from widgets.media.feedback import trigger_controls_feedback
        trigger_controls_feedback(self, key, source)

    def _log_feedback_metric(self, *, phase: str, key: str, source: str, event_id: str) -> None:
        from widgets.media.feedback import log_feedback_metric
        log_feedback_metric(self, phase=phase, key=key, source=source, event_id=event_id)

    def _start_feedback_animation(self, key: str) -> None:
        from widgets.media.feedback import start_feedback_animation
        start_feedback_animation(self, key)

    def _expire_all_feedback(self) -> None:
        from widgets.media.feedback import expire_all_feedback
        expire_all_feedback(self)

    def _finalize_feedback_key(self, key: str) -> None:
        from widgets.media.feedback import finalize_feedback_key
        finalize_feedback_key(self, key)
    
    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        try:
            width_changed = event.oldSize().width() != event.size().width()
        except Exception:
            width_changed = True
        if width_changed and bool(getattr(self, "_playback_progress_enabled", False)):
            self._refresh_metadata_paint_boundary()
            if self._refresh_playback_progress_snapshot():
                self._safe_update()

    def paintEvent(self, event):  # type: ignore[override]
        """Paint the media card through the painter-owned runtime path.

        Artwork is drawn to the right side inside the widget's margins so
        that the text content remains legible. All failures are ignored so
        that paint never raises.
        """
        with widget_paint_sample(self, "media.paint"):
            self._paint_contents(event)

    def _paint_contents(self, event) -> None:
        """Internal paint implementation. Delegates to widgets.media.painting."""
        from widgets.media.painting import paint_contents
        paint_contents(self, event)

    def _load_brand_pixmap(self) -> Optional[QPixmap]:
        """Delegates to widgets.media.painting."""
        from widgets.media.painting import load_brand_pixmap
        return load_brand_pixmap(provider=self._provider)

    def _start_widget_fade_in(self, duration_ms: Optional[int] = None) -> None:
        """Fade the entire widget in; shadows are painter-owned."""
        resolved_duration_ms = (
            ShadowFadeProfile.default_duration_ms()
            if duration_ms is None
            else max(0, int(duration_ms))
        )
        # Reset fade completion flag so re-entrancy (wake from idle) refreshes painted shadows.
        self._fade_in_completed = False
        # CRITICAL: Position the widget BEFORE showing to prevent teleport flash
        # The widget starts at (0,0) and must be moved to its correct position
        # before becoming visible to avoid a brief flash in the wrong location.
        try:
            self._update_position()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        
        if resolved_duration_ms <= 0:
            try:
                self.show()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            try:
                ShadowFadeProfile.attach_shadow(
                    self,
                    self._shadow_config,
                    has_background_frame=self._show_background,
                )
            except Exception:
                logger.debug(
                    "[MEDIA] Failed to refresh shadow in no-fade path",
                    exc_info=True,
                )
            self._handle_fade_in_complete()
            return

        try:
            ShadowFadeProfile.start_fade_in(
                self,
                self._shadow_config,
                duration_ms=resolved_duration_ms,
                has_background_frame=self._show_background,
                on_finished=self._handle_fade_in_complete,
            )
        except Exception:
            logger.warning(
                "[MEDIA][FALLBACK] _start_widget_fade_in fallback path triggered",
                exc_info=True,
            )
            try:
                self.show()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            self._handle_fade_in_complete()

    def _handle_fade_in_complete(self) -> None:
        """Mark fade-in complete and refresh painter-owned shadows."""
        if self._fade_in_completed:
            return
        self._fade_in_completed = True
        if is_perf_metrics_enabled():
            has_config = bool(self._shadow_config)
            logger.info(
                "[PERF][MEDIA_WIDGET] Fade-in complete (shadow_config=%s, show_background=%s)",
                "yes" if has_config else "no",
                self._show_background,
            )
        try:
            self.on_fade_complete()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        self._start_artwork_fade_if_ready(reason="widget_reveal_complete")

    def _start_artwork_fade_if_ready(self, *, reason: str) -> bool:
        """Start one pending artwork fade after card reveal and transition idle."""

        pixmap = self._artwork_pixmap
        if pixmap is None or self._artwork_opacity >= 1.0:
            return False
        try:
            if pixmap.isNull():
                return False
        except Exception:
            return False
        if (
            not self._fade_in_completed
            or not self._has_seen_first_track
            or self._artwork_anim is not None
            or type(self)._has_transition_work_on_any_display()
        ):
            return False

        self._start_artwork_fade_in()
        if is_perf_metrics_enabled():
            logger.info(
                "[PERF][MEDIA_ARTWORK] event=fade_started reason=%s "
                "key_id=%s generation=%d",
                reason,
                self._artwork_key_log_id(self._applied_artwork_key),
                int(self._artwork_update_generation),
            )
        return True

    def _start_artwork_fade_in(self) -> None:
        if self._artwork_anim is not None:
            try:
                self._artwork_anim.stop()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            self._artwork_anim = None

        self._artwork_opacity = 0.0
        
        # Use AnimationManager instead of QPropertyAnimation to avoid per-frame update() calls
        # This reduces paint calls from ~10Hz to only when needed
        try:
            from core.animation.animator import AnimationManager
            from core.animation.types import EasingCurve
            
            anim_mgr = AnimationManager.get_or_create_app_shared()
            
            def _on_tick(progress: float) -> None:
                try:
                    self._artwork_opacity = float(progress)
                    self._safe_update()
                except Exception as e:
                    logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            
            def _on_finished() -> None:
                self._artwork_anim = None
                self._artwork_opacity = 1.0
                self._safe_update()
            
            # AnimationManager uses seconds, not milliseconds
            anim_id = anim_mgr.animate_custom(
                duration=0.85,  # 850ms
                update_callback=_on_tick,
                on_complete=_on_finished,
                easing=EasingCurve.CUBIC_IN_OUT
            )
            self._artwork_anim = anim_id
        except Exception:
            logger.debug("[MEDIA] Failed to start artwork fade via AnimationManager", exc_info=True)
            # Fallback: just set opacity to 1.0 immediately
            self._artwork_opacity = 1.0
            self._safe_update()
