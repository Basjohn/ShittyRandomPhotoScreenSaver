"""Media/Now Playing widget for screensaver overlay.

This widget displays the current media playback state (track title,
artist, album) using the centralized media controller abstraction.

Transport controls (play/pause, previous/next) are exposed but are
strictly gated behind explicit user intent (Ctrl-held or hard-exit
interaction modes) as routed by DisplayWidget; normal screensaver
mode remains non-interactive.
"""
from __future__ import annotations

import hashlib
import time
import weakref
from dataclasses import asdict
from enum import Enum
from typing import Optional, TYPE_CHECKING, ClassVar, Any

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Qt, Signal, QVariantAnimation, QPoint
from PySide6.QtGui import (
    QFont,
    QPixmap,
    QFontMetrics,
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
from core.threading.manager import ThreadManager
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.shadow_utils import ShadowFadeProfile
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle

if TYPE_CHECKING:
    from rendering.widget_manager import WidgetManager

logger = get_logger(__name__)


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
    
    # Class-level shared state for feedback synchronization
    _instances: ClassVar[weakref.WeakSet] = weakref.WeakSet()
    _shared_feedback_events: ClassVar[dict] = {}
    _shared_feedback_timer: ClassVar[Optional[QTimer]] = None
    _shared_feedback_timer_interval_ms: ClassVar[int] = 16
    
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
    ) -> None:
        # Convert MediaPosition to OverlayPosition for base class
        overlay_pos = OverlayPosition(position.value)
        super().__init__(parent, position=overlay_pos, overlay_name="media")
        
        # Defer visibility until fade sync triggers
        self._defer_visibility_for_fade_sync = True

        self._media_position = position  # Keep original enum for compatibility
        self._pending_controller_tm: Optional[ThreadManager] = None
        if thread_manager is not None:
            self.set_thread_manager(thread_manager)
        controller_tm = thread_manager or self._thread_manager or self._pending_controller_tm
        self._controller: BaseMediaController = controller or create_media_controller(thread_manager=controller_tm)
        if controller_tm is not None:
            try:
                self._controller.set_thread_manager(controller_tm)
            except Exception as exc:
                logger.debug("[MEDIA_WIDGET] Exception suppressing controller TM injection: %s", exc)
        else:
            self._pending_controller_tm = None
        try:
            logger.info("[MEDIA_WIDGET] Using controller: %s", type(self._controller).__name__)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

        self._widget_manager: Optional["WidgetManager"] = None
        self._update_timer: Optional[QTimer] = None
        self._update_timer_handle: Optional[OverlayTimerHandle] = None
        self._refresh_in_flight = False
        self._pending_state_override: Optional[MediaPlaybackState] = None
        self._pending_state_timer: Optional[QTimer] = None

        # Override base class font size default
        self._font_size = 20

        # Album artwork state (optional)
        self._artwork_pixmap: Optional[QPixmap] = None
        # Cached scaled artwork to avoid expensive SmoothTransformation on every paint
        self._scaled_artwork_cache: Optional[QPixmap] = None
        self._scaled_artwork_cache_key: Optional[tuple] = None  # (pm_id, frame_w, frame_h, dpr)
        # Default artwork size (logical pixels); overridable via settings.
        self._artwork_size: int = 200
        self._artwork_opacity: float = 1.0
        self._artwork_anim: Optional[QVariantAnimation] = None

        # Artwork border behaviour
        self._rounded_artwork_border: bool = True

        # Optional header frame around the Spotify logo + title row.
        self._show_header_frame: bool = True

        # Layout/controls behaviour
        self._show_controls: bool = True

        # Optional Spotify-style brand logo used when album artwork is absent.
        self._brand_pixmap: Optional[QPixmap] = self._load_brand_pixmap()

        # Cached header logo metrics so paintEvent can align the Spotify glyph
        # with the rich-text SPOTIFY header.
        self._context_menu_active: bool = False
        self._context_menu_prewarmed: bool = False
        self._pending_effect_invalidation: bool = False

        # Central ResourceManager wiring
        self._last_info: Optional[MediaTrackInfo] = None
        
        # Smart polling: diff gating to skip unnecessary updates
        self._last_track_identity: Optional[tuple] = None  # (title, artist, album, state)
        
        # Smart polling: idle detection to stop polling when Spotify is closed
        self._consecutive_none_count: int = 0
        self._idle_threshold: int = 12  # ~30s at 2500ms interval before entering idle
        self._is_idle: bool = False
        self._idle_poll_interval: int = 5000  # Poll every 5s when idle to detect Spotify opening
        
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
        self._last_display_update_ts: float = 0.0
        self._skipped_identity_updates: int = 0
        self._max_identity_skip: int = 4
        
        # Widget state tracking for lifecycle management
        self._activation_time: float = 0.0
        self._post_activation_grace_sec: float = 5.0  # Grace period after activation

        # Register this instance for shared feedback
        type(self)._instances.add(self)

        self._setup_ui()

        logger.debug("MediaWidget created (position=%s)", position.value)

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
        self.setMinimumWidth(600)
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
        if self._update_timer_handle is not None:
            try:
                self._update_timer_handle.stop()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            self._update_timer_handle = None
        
        if self._update_timer is not None:
            try:
                self._update_timer.stop()
                self._update_timer.deleteLater()
            except RuntimeError:
                pass
            self._update_timer = None
        
        logger.debug("[LIFECYCLE] MediaWidget deactivated")
    
    def _cleanup_impl(self) -> None:
        """Clean up media resources (lifecycle hook)."""
        self._deactivate_impl()
        self._artwork_pixmap = None
        self._scaled_artwork_cache = None
        self._scaled_artwork_cache_key = None
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
        if self._update_timer_handle is not None:
            try:
                self._update_timer_handle.stop()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            self._update_timer_handle = None

        if self._update_timer is not None:
            try:
                self._update_timer.stop()
                self._update_timer.deleteLater()
            except RuntimeError:
                pass
            self._update_timer = None

        self.hide()
        logger.debug("Media widget stopped")

    def is_running(self) -> bool:
        return self._enabled

    def cleanup(self) -> None:
        """Clean up resources (called from DisplayWidget)."""

        logger.debug("Cleaning up media widget")
        self.stop()

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
        except RuntimeError:
            pass
        except Exception as exc:
            logger.debug("[MEDIA_WIDGET] update() suppressed: %s", exc)
    
    # ------------------------------------------------------------------
    # Smart Polling Helpers
    # ------------------------------------------------------------------
    
    def _compute_track_identity(self, info: MediaTrackInfo) -> tuple:
        """Compute a tuple representing the track's identity for diff gating.
        
        Returns a tuple of (title, artist, album, state) that uniquely identifies
        the current track state. Used to skip unnecessary _update_display() calls
        when the track hasn't changed.
        """
        try:
            title = (getattr(info, 'title', None) or '').strip().lower()
            artist = (getattr(info, 'artist', None) or '').strip().lower()
            album = (getattr(info, 'album', None) or '').strip().lower()
            state = getattr(info, 'state', None)
            state_val = state.value if hasattr(state, 'value') else str(state)
            return (title, artist, album, state_val)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception in _compute_track_identity: %s", e)
            # Return a unique tuple on error to force update
            return (id(info), None, None, None)
    
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

    def _advance_poll_stage(self) -> None:
        """Advance to next (slower) poll interval if not at max."""
        if self._current_poll_stage >= len(self._poll_intervals) - 1:
            return  # Already at slowest
        
        self._current_poll_stage += 1
        self._polls_at_current_stage = 0
        new_interval = self._poll_intervals[self._current_poll_stage]
        
        # Recreate timer with new interval
        self._ensure_timer(force=True)
        
        if is_perf_metrics_enabled():
            logger.debug("[PERF] Media widget advanced to poll stage %d (%dms)", 
                        self._current_poll_stage, new_interval)
    
    def _reset_poll_stage(self) -> None:
        """Reset to fastest poll interval (used when resuming from idle)."""
        if self._current_poll_stage == 0:
            return  # Already at fastest
        
        self._current_poll_stage = 0
        self._polls_at_current_stage = 0
        
        # Recreate timer with fast interval
        self._ensure_timer(force=True)
        
        if is_perf_metrics_enabled():
            logger.debug("[PERF] Media widget reset to fast poll (1000ms)")
    
    def _stop_timer(self) -> None:
        """Stop the current poll timer."""
        if self._update_timer_handle is not None:
            try:
                self._update_timer_handle.stop()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        self._update_timer_handle = None
        self._update_timer = None

    def _update_position(self) -> None:
        """Delegates to widgets.media_layout."""
        from widgets.media_layout import update_position
        update_position(self)

    def _complete_hide_sequence(self) -> None:
        """Complete the hide sequence after fade out animation.
        
        Called as callback after fade out completes to hide widget and
        notify Spotify-related widgets.
        """
        try:
            self.hide()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        # Notify parent to hide Spotify-related widgets
        self._notify_spotify_widgets_visibility()
    
    def _notify_spotify_widgets_visibility(self) -> None:
        """Notify Spotify-related widgets to sync their visibility with this widget.
        
        Called when the media widget shows or hides so the visualizer and
        volume widgets can show/hide accordingly.
        """
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
        if self._show_background:
            self.setStyleSheet(
                f"""
                QLabel {{
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
                QLabel {{
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

    def set_artwork_size(self, size: int) -> None:
        """Set preferred artwork size in pixels and refresh layout."""

        if size <= 0:
            return
        self._artwork_size = int(size)
        # Keep the card's minimum height in sync with the configured artwork
        # footprint so resizing via settings does not cause unexpected jumps
        # at runtime.
        self.setMinimumHeight(max(220, self._artwork_size + 60))
        if self._last_info is not None:
            try:
                self._update_display(self._last_info)
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                self._safe_update()

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

        self._show_controls = bool(show)
        invalidate = getattr(self, "_invalidate_controls_layout", None)
        if callable(invalidate):
            invalidate()
        if self._last_info is not None:
            try:
                self._update_display(self._last_info)
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                self._safe_update()


    def _invalidate_controls_layout(self) -> None:
        """Clear cached transport controls geometry."""
        self._controls_layout_cache = None

    # ------------------------------------------------------------------
    # Transport controls (delegated to controller)
    # ------------------------------------------------------------------
    def play_pause(self, source: str = "manual", execute: bool = True) -> None:
        """Toggle play/pause when supported.

        This is best-effort and never raises; failures are logged by the
        underlying controller. It is safe to call even when no media is
        currently playing.
        """

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
                    # Only repaint controls if they're visible and state changed
                    if self._show_controls and self.isVisible():
                        self._invalidate_controls_layout()
                        # Use repaint() for immediate feedback on media key (rare event)
                        self.repaint()
                    logger.info("[MEDIA_WIDGET] Optimistic play/pause applied: state=%s", optimistic.state)
                except Exception:
                    logger.debug("[MEDIA] play_pause optimistic update failed", exc_info=True)
                try:
                    if new_state is not None:
                        self._apply_pending_state_override(new_state)
                        refresh_requested = True
                except Exception:
                    logger.debug("[MEDIA] play_pause optimistic override failed", exc_info=True)
            else:
                refresh_requested = self._request_refresh_after_control()

        self._handle_control_feedback("play", source, force_refresh=not refresh_requested)

    def _apply_pending_state_override(self, state: MediaPlaybackState) -> None:
        timer = self._pending_state_timer
        if timer is not None:
            try:
                timer.stop()
                timer.deleteLater()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            self._pending_state_timer = None

        self._pending_state_override = state

        try:
            self._safe_update()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

        if not self._enabled:
            return

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(300)

        def _on_timeout() -> None:
            self._pending_state_timer = None
            self._pending_state_override = None
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
        self._pending_state_timer = timer
        self._register_resource(timer, "pending state debounce timer")
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

    def handle_double_click(self, local_pos) -> bool:
        """Called by WidgetManager dispatch. Refreshes artwork/track info."""
        if not self._enabled:
            return False
        try:
            # Bust GSMTC cache so we actually re-query the controller
            self._gsmtc_cached_result = None
            self._gsmtc_cache_ts = 0.0
            # Clear scaled artwork cache so new artwork is rendered fresh
            self._scaled_artwork_cache = None
            self._scaled_artwork_cache_key = None
            # Reset diff gating so update_display doesn't skip the refresh
            self._last_track_identity = None
            self._skipped_identity_updates = 0
            # Force clear in-flight guard so the refresh actually runs
            self._refresh_in_flight = False
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
        self._refresh_in_flight = False
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

    def _refresh_async(self) -> None:
        # Desync: Check GSMTC cache first to reduce IO contention
        now = time.time()
        if self._gsmtc_cached_result is not None:
            elapsed_ms = (now - self._gsmtc_cache_ts) * 1000
            if elapsed_ms < self._gsmtc_cache_ms:
                if is_perf_metrics_enabled():
                    logger.debug("[PERF] MediaWidget: using cached GSMTC result (age=%.0fms)", elapsed_ms)
                self._update_display(self._gsmtc_cached_result)
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

        self._refresh_in_flight = True
        if is_verbose_logging():
            logger.debug("[MEDIA_WIDGET] Async refresh started")

        def _do_query():
            try:
                return self._controller.get_current_track()
            except Exception:
                logger.debug("[MEDIA] get_current_track failed", exc_info=True)
                if is_verbose_logging():
                    logger.debug("[MEDIA] get_current_track failed", exc_info=True)
                return None

        def _handle_result(task_result):
            def _consume_result() -> None:
                try:
                    if not Shiboken.isValid(self):
                        return
                    info = task_result.result if getattr(task_result, "success", False) else None
                    # Desync: Cache the result for 500ms
                    self._gsmtc_cached_result = info
                    self._gsmtc_cache_ts = time.time()
                    self._update_display(info)
                except Exception as exc:
                    logger.debug("[MEDIA_WIDGET] Exception during async refresh consume: %s", exc)
                finally:
                    self._refresh_in_flight = False

            try:
                ThreadManager.run_on_ui_thread(_consume_result)
            except Exception as exc:
                logger.debug("[MEDIA_WIDGET] Failed to marshal async refresh to UI thread: %s", exc)
                self._refresh_in_flight = False

        try:
            tm.submit_io_task(_do_query, callback=_handle_result)
        except Exception as exc:
            logger.debug("[MEDIA_WIDGET] Failed to submit async refresh: %s", exc)
            self._refresh_in_flight = False

    def _emit_media_update(self, info: MediaTrackInfo) -> None:
        """Emit the current media metadata/state to interested observers."""
        try:
            payload = asdict(info)
            payload["state"] = info.state.value
            self.media_updated.emit(payload)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Failed to emit media update: %s", e)

    def _update_display(self, info: Optional[MediaTrackInfo]) -> None:
        """Delegates to widgets.media.display_update."""
        from widgets.media.display_update import update_display
        update_display(self, info)

    def _decode_artwork_pixmap(self, artwork: Optional[bytes]) -> Optional[QPixmap]:
        """Decode artwork bytes into a pixmap, ensuring non-zero dimensions."""
        if not artwork:
            return None
        try:
            data = bytes(artwork)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Invalid artwork payload: %s", e)
            return None

        pm = QPixmap()
        try:
            if not pm.loadFromData(data):
                return None
        except MemoryError:
            logger.error("[MEDIA_WIDGET] Out of memory decoding artwork", exc_info=True)
            return None
        except Exception:
            logger.debug("[MEDIA_WIDGET] Failed to decode artwork pixmap", exc_info=True)
            return None

        if pm.isNull():
            return None
        if pm.width() <= 0 or pm.height() <= 0:
            return None
        return pm
    
    def _controls_row_min_height(self) -> int:
        """Return the minimum vertical footprint required for the controls row."""
        controls_font_pt = max(8, int((self._font_size - 2) * 0.9))
        font = QFont(self._font_family, controls_font_pt, QFont.Weight.Medium)
        fm = QFontMetrics(font)
        # Inner padding mirrors _compute_controls_layout to keep visuals consistent.
        min_height = max(24, fm.height() + 12)
        return max(20, int(min_height * 0.82))
    
    def _controls_row_margin(self) -> int:
        """Bottom margin that keeps controls breathing room above the card edge."""
        return max(10, int(self._controls_row_min_height() * 0.35))
    
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
    
    def _complete_hide_sequence(self) -> None:
        """Complete the hide sequence after fade out."""
        try:
            self.hide()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        # Clear artwork to free memory
        self._artwork_pixmap = None
        self._scaled_artwork_cache = None
        self._scaled_artwork_cache_key = None
        # Notify Spotify widgets
        self._notify_spotify_widgets_visibility()
    
    def _handle_fade_in_complete(self) -> None:
        """Mark fade-in complete."""
        self._fade_in_completed = True
    
    def _start_artwork_fade_in(self) -> None:
        """Fade in artwork with animation."""
        # Cancel any existing artwork animation
        if self._artwork_anim is not None:
            try:
                self._artwork_anim.stop()
                self._artwork_anim.deleteLater()
            except Exception:
                pass
            self._artwork_anim = None
        
        self._artwork_opacity = 0.0
        
        # Simple fade using QVariantAnimation
        try:
            anim = QVariantAnimation(self)
            anim.setDuration(850)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.valueChanged.connect(lambda val: self._on_artwork_fade_tick(val))
            anim.finished.connect(lambda: self._on_artwork_fade_complete())
            self._artwork_anim = anim
            anim.start()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Artwork fade failed: %s", e)
            # Fallback: just set progress and let timer expire it
            self._artwork_opacity = 1.0
            self._safe_update()
    
    def _on_artwork_fade_tick(self, value: float) -> None:
        """Update artwork opacity during fade."""
        self._artwork_opacity = float(value)
        self._safe_update()
    
    def _on_artwork_fade_complete(self) -> None:
        """Clean up after artwork fade."""
        self._artwork_anim = None
        self._artwork_opacity = 1.0
        self._safe_update()
    
    def _compute_track_identity(self, info: MediaTrackInfo) -> tuple:
        """Compute track identity for diff gating."""
        return (
            (info.title or "").strip(),
            (info.artist or "").strip(),
            (info.album or "").strip(),
            info.state,
            self._compute_artwork_key(info),
        )

    def _compute_artwork_key(self, info: MediaTrackInfo) -> tuple:
        payload = getattr(info, "artwork", None)
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
    
    def _reset_poll_stage(self) -> None:
        """Reset polling to fastest interval."""
        self._current_poll_stage = 0
        self._polls_at_current_stage = 0
    
    def _advance_poll_stage(self) -> None:
        """Advance to next slower polling interval."""
        if self._current_poll_stage < len(self._poll_intervals) - 1:
            self._current_poll_stage += 1
            self._polls_at_current_stage = 0
            if is_perf_metrics_enabled():
                interval = self._poll_intervals[self._current_poll_stage]
                logger.debug("[PERF] Media widget advanced to %dms poll interval", interval)
    
    def _stop_timer(self) -> None:
        """Stop the update timer."""
        if self._update_timer_handle is not None:
            try:
                self._update_timer_handle.stop()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        self._update_timer_handle = None
        self._update_timer = None

    def _ensure_timer(self, *, force: bool = False) -> None:
        """Ensure update timer is running at correct interval."""
        if self._update_timer_handle is not None and not force:
            timer = getattr(self._update_timer_handle, "_timer", None)
            try:
                if timer is not None and timer.isActive():
                    return
            except Exception:
                force = True
        if force:
            self._stop_timer()

        if not self._ensure_thread_manager("MediaWidget._ensure_timer"):
            if not self._telemetry_logged_missing_tm:
                logger.warning("[MEDIA_WIDGET][TIMER] ThreadManager unavailable; media polling paused")
                self._telemetry_logged_missing_tm = True
            return

        self._telemetry_logged_missing_tm = False
        interval = self._idle_poll_interval if self._is_idle else self._poll_intervals[self._current_poll_stage]
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
    def paintEvent(self, event):  # type: ignore[override]
        """Paint text via QLabel then overlay optional artwork icon.

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
        return load_brand_pixmap()

    def _start_widget_fade_in(self, duration_ms: int = 1500) -> None:
        """Fade the entire widget in, then attach the global drop shadow."""
        # Reset fade completion flag so re-entrancy (wake from idle) reapplies the shadow.
        self._fade_in_completed = False
        # CRITICAL: Position the widget BEFORE showing to prevent teleport flash
        # The widget starts at (0,0) and must be moved to its correct position
        # before becoming visible to avoid a brief flash in the wrong location.
        try:
            self._update_position()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        
        if duration_ms <= 0:
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
                    "[MEDIA] Failed to attach shadow in no-fade path",
                    exc_info=True,
                )
            self._handle_fade_in_complete()
            return

        try:
            ShadowFadeProfile.start_fade_in(
                self,
                self._shadow_config,
                has_background_frame=self._show_background,
                on_finished=self._handle_fade_in_complete,
            )
        except Exception:
            logger.debug(
                "[MEDIA] _start_widget_fade_in fallback path triggered",
                exc_info=True,
            )
            try:
                self.show()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            self._handle_fade_in_complete()

    def _handle_fade_in_complete(self) -> None:
        """Mark fade-in complete and apply shared drop shadow."""
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
            
            anim_mgr = AnimationManager()
            
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
