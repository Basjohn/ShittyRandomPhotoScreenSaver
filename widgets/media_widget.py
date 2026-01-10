"""Media/Now Playing widget for screensaver overlay.

This widget displays the current media playback state (track title,
artist, album) using the centralized media controller abstraction.

Transport controls (play/pause, previous/next) are exposed but are
strictly gated behind explicit user intent (Ctrl-held or hard-exit
interaction modes) as routed by DisplayWidget; normal screensaver
mode remains non-interactive.
"""
from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Qt, Signal, QVariantAnimation, QRect
from PySide6.QtGui import QFont, QColor, QPixmap, QPainter, QPainterPath, QFontMetrics
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
from widgets.shadow_utils import apply_widget_shadow, ShadowFadeProfile, draw_rounded_rect_with_shadow
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle
from utils.text_utils import smart_title_case

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

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        position: MediaPosition = MediaPosition.BOTTOM_LEFT,
        controller: Optional[BaseMediaController] = None,
    ) -> None:
        # Convert MediaPosition to OverlayPosition for base class
        overlay_pos = OverlayPosition(position.value)
        super().__init__(parent, position=overlay_pos, overlay_name="media")
        
        # Defer visibility until fade sync triggers
        self._defer_visibility_for_fade_sync = True

        self._media_position = position  # Keep original enum for compatibility
        self._controller: BaseMediaController = controller or create_media_controller()
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

        # Widget-level fade state for the first time it becomes visible.
        # Subsequent track changes update in-place so the card and controls
        # remain perfectly stable.

        # Shared shadow configuration, passed in from DisplayWidget so we
        # can re-attach the global drop shadow after each fade.
        self._shadow_config = None

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
        if not self._ensure_thread_manager("MediaWidget._activate_impl"):
            raise RuntimeError("ThreadManager not available")
        
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
        self._thread_manager = thread_manager
        if is_verbose_logging():
            logger.debug("[MEDIA_WIDGET] ThreadManager injected: %s", type(thread_manager).__name__ if thread_manager else None)

    def set_widget_manager(self, widget_manager: "WidgetManager") -> None:
        self._widget_manager = widget_manager
    
    def set_shadow_config(self, config) -> None:
        """Store shared shadow configuration for post-fade drop shadows."""

        self._shadow_config = config

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

    # ------------------------------------------------------------------
    # Position & layout
    # ------------------------------------------------------------------
    def _ensure_timer(self) -> None:
        if self._update_timer_handle is not None:
            return
        if not self._ensure_thread_manager("MediaWidget._ensure_timer"):
            return
        # Adaptive polling: start at 1000ms, progress to 2000ms, then 2500ms
        interval = self._poll_intervals[self._current_poll_stage]
        handle = create_overlay_timer(self, interval, self._refresh, description="MediaWidget smart poll")
        self._update_timer_handle = handle
        try:
            self._update_timer = getattr(handle, "_timer", None)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            self._update_timer = None
        if is_perf_metrics_enabled():
            logger.debug("[PERF] Media widget timer started at %dms (stage %d)", interval, self._current_poll_stage)
    
    def _advance_poll_stage(self) -> None:
        """Advance to next (slower) poll interval if not at max."""
        if self._current_poll_stage >= len(self._poll_intervals) - 1:
            return  # Already at slowest
        
        self._current_poll_stage += 1
        self._polls_at_current_stage = 0
        new_interval = self._poll_intervals[self._current_poll_stage]
        
        # Recreate timer with new interval
        self._stop_timer()
        self._ensure_timer()
        
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
        self._stop_timer()
        self._ensure_timer()
        
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
        """Update widget position using centralized base class logic.
        
        Delegates to BaseOverlayWidget._update_position() which handles:
        - Margin-based positioning for all 9 anchor positions
        - Visual padding offsets (when background is disabled)
        - Pixel shift and stack offset application
        - Bounds clamping to prevent off-screen drift
        
        This ensures consistent margin alignment across all overlay widgets.
        """
        # Guard against positioning before widget has valid size
        if self.width() <= 0 or self.height() <= 0:
            QTimer.singleShot(16, self._update_position)
            return
        
        # Sync MediaPosition to OverlayPosition for base class
        position_map = {
            MediaPosition.TOP_LEFT: OverlayPosition.TOP_LEFT,
            MediaPosition.TOP_CENTER: OverlayPosition.TOP_CENTER,
            MediaPosition.TOP_RIGHT: OverlayPosition.TOP_RIGHT,
            MediaPosition.MIDDLE_LEFT: OverlayPosition.MIDDLE_LEFT,
            MediaPosition.CENTER: OverlayPosition.CENTER,
            MediaPosition.MIDDLE_RIGHT: OverlayPosition.MIDDLE_RIGHT,
            MediaPosition.BOTTOM_LEFT: OverlayPosition.BOTTOM_LEFT,
            MediaPosition.BOTTOM_CENTER: OverlayPosition.BOTTOM_CENTER,
            MediaPosition.BOTTOM_RIGHT: OverlayPosition.BOTTOM_RIGHT,
        }
        
        # Update base class position
        self._position = position_map.get(self._media_position, OverlayPosition.BOTTOM_LEFT)
        
        # Delegate to base class for centralized margin/positioning logic
        super()._update_position()

        # Keep Spotify-related overlays anchored to the card
        parent = self.parent()
        if parent is not None:
            if hasattr(parent, "_position_spotify_visualizer"):
                try:
                    parent._position_spotify_visualizer()
                except Exception as e:
                    logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            if hasattr(parent, "_position_spotify_volume"):
                try:
                    parent._position_spotify_volume()
                except Exception as e:
                    logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
    
    def _notify_spotify_widgets_visibility(self) -> None:
        """Notify Spotify-related widgets to sync their visibility with this widget.
        
        Called when the media widget shows or hides so the visualizer and
        volume widgets can show/hide accordingly. Also gates the FFT worker
        to save compute when Spotify is not active.
        """
        parent = self.parent()
        if parent is None:
            return
        
        # Gate FFT worker based on media widget visibility
        self._gate_fft_worker(self.isVisible())
        
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
                self.update()

    def set_rounded_artwork_border(self, rounded: bool) -> None:
        """Enable or disable rounded borders around the album artwork."""

        self._rounded_artwork_border = bool(rounded)
        self.update()

    def set_show_header_frame(self, show: bool) -> None:
        """Enable or disable the header subcontainer frame around logo+title."""

        self._show_header_frame = bool(show)
        self.update()

    def set_show_controls(self, show: bool) -> None:
        """Show or hide the transport controls row."""

        self._show_controls = bool(show)
        if self._last_info is not None:
            try:
                self._update_display(self._last_info)
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                self.update()

    # ------------------------------------------------------------------
    # Transport controls (delegated to controller)
    # ------------------------------------------------------------------
    def play_pause(self) -> None:
        """Toggle play/pause when supported.

        This is best-effort and never raises; failures are logged by the
        underlying controller. It is safe to call even when no media is
        currently playing.
        """

        try:
            self._controller.play_pause()
        except Exception:
            logger.debug("[MEDIA] play_pause delegation failed", exc_info=True)
            return

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
                self._update_display(optimistic)
            except Exception:
                logger.debug("[MEDIA] play_pause optimistic update failed", exc_info=True)
            try:
                if new_state is not None:
                    self._apply_pending_state_override(new_state)
            except Exception:
                logger.debug("[MEDIA] play_pause optimistic override failed", exc_info=True)

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
            self.update()
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
            try:
                self.update()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

        timer.timeout.connect(_on_timeout)
        self._pending_state_timer = timer
        timer.start()

    def next_track(self) -> None:
        """Skip to next track when supported (best-effort)."""

        try:
            self._controller.next()
        except Exception:
            logger.debug("[MEDIA] next delegation failed", exc_info=True)
            return

        try:
            if self._enabled:
                if self._thread_manager is not None:
                    self._refresh_async()
                else:
                    self._refresh()
        except Exception:
            logger.debug("[MEDIA] next post-refresh failed", exc_info=True)

    def previous_track(self) -> None:
        """Skip to previous track when supported (best-effort)."""

        try:
            self._controller.previous()
        except Exception:
            logger.debug("[MEDIA] previous delegation failed", exc_info=True)
            return

        try:
            if self._enabled:
                if self._thread_manager is not None:
                    self._refresh_async()
                else:
                    self._refresh()
        except Exception:
            logger.debug("[MEDIA] previous post-refresh failed", exc_info=True)

    # ------------------------------------------------------------------
    # Polling and display
    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        if not self._enabled:
            return
        
        # Smart polling: skip refresh if in idle mode (Spotify closed)
        if self._is_idle:
            if is_perf_metrics_enabled():
                logger.debug("[PERF] Media widget poll skipped (idle mode)")
            return
        
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
        if self._refresh_in_flight:
            return
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

        def _on_result(task_result) -> None:
            def _apply(info) -> None:
                self._refresh_in_flight = False
                try:
                    if info is None:
                        if is_verbose_logging():
                            logger.debug("[MEDIA_WIDGET] No track info in async result; hiding")
                    else:
                        try:
                            state = getattr(info, "state", None)
                            state_val = state.value if hasattr(state, "value") else str(state)
                        except Exception as e:
                            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                            state_val = "?"
                        if is_verbose_logging():
                            logger.debug(
                                "[MEDIA_WIDGET] Applying track: state=%s, title=%r, artist=%r, album=%r",
                                state_val,
                                getattr(info, "title", None),
                                getattr(info, "artist", None),
                                getattr(info, "album", None),
                            )
                except Exception:
                    logger.debug("[MEDIA_WIDGET] Failed to log async apply", exc_info=True)
                self._update_display(info)

            info = None
            if getattr(task_result, "success", False):
                info = getattr(task_result, "result", None)
            ThreadManager.run_on_ui_thread(_apply, info)

        try:
            tm.submit_io_task(_do_query, callback=_on_result)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            self._refresh_in_flight = False

    def _update_display(self, info: Optional[MediaTrackInfo]) -> None:
        # Lifetime guard: async callbacks may fire after the widget has been
        # destroyed. Bail out early and stop timers/handles if the underlying
        # Qt object is no longer valid.
        try:
            if not Shiboken.isValid(self):
                if getattr(self, "_update_timer_handle", None) is not None:
                    try:
                        self._update_timer_handle.stop()  # type: ignore[union-attr]
                    except Exception as e:
                        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                    self._update_timer_handle = None  # type: ignore[assignment]

                if getattr(self, "_update_timer", None) is not None:
                    try:
                        self._update_timer.stop()  # type: ignore[union-attr]
                        self._update_timer.deleteLater()  # type: ignore[union-attr]
                    except Exception as e:
                        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                    self._update_timer = None  # type: ignore[assignment]

                self._enabled = False
                self._refresh_in_flight = False
                return
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            return

        # Cache last track snapshot for diagnostics/interaction
        prev_info = self._last_info
        self._last_info = info
        
        # Smart polling: diff gating - compute track identity
        if info is not None:
            current_identity = self._compute_track_identity(info)
            
            # Reset idle counter when we get valid track info
            if self._consecutive_none_count > 0 or self._is_idle:
                if is_perf_metrics_enabled():
                    logger.debug("[PERF] Media widget exiting idle (track detected)")
                self._consecutive_none_count = 0
                was_idle = self._is_idle
                self._is_idle = False
                # Reset to fast polling when resuming from idle
                if was_idle:
                    self._reset_poll_stage()
            
            # Adaptive polling: advance to slower interval after 2 successful polls
            self._polls_at_current_stage += 1
            if self._polls_at_current_stage >= 2:
                self._advance_poll_stage()
            
            # Diff gating: skip update if track identity unchanged
            # Always process first track (when _last_track_identity is None)
            # Also process if we haven't completed fade-in yet (need 2 updates for fade-in)
            if (current_identity == self._last_track_identity and 
                self._last_track_identity is not None and 
                self._fade_in_completed):
                if is_perf_metrics_enabled():
                    logger.debug("[PERF] Media widget update skipped (diff gating - no change)")
                return
            
            # Track changed - update identity and proceed
            self._last_track_identity = current_identity
            if is_perf_metrics_enabled():
                logger.debug("[PERF] Media widget update applied (track changed)")

        if info is None:
            # Smart polling: idle detection - track consecutive None results
            self._consecutive_none_count += 1
            
            # Enter idle mode after threshold consecutive None results (~30s)
            if self._consecutive_none_count >= self._idle_threshold and not self._is_idle:
                self._is_idle = True
                self._last_track_identity = None  # Reset identity for next track
                if is_perf_metrics_enabled():
                    logger.debug("[PERF] Media widget entering idle mode (Spotify closed)")
                else:
                    logger.info("[MEDIA_WIDGET] Entering idle mode after %d consecutive empty polls", 
                               self._consecutive_none_count)
            
            # No active media session (e.g. Spotify not playing) – hide widget
            last_vis = self._telemetry_last_visibility
            if last_vis or last_vis is None:
                logger.info("[MEDIA_WIDGET] No active media session; hiding media card")
            self._artwork_pixmap = None
            self._scaled_artwork_cache = None
            self._scaled_artwork_cache_key = None
            try:
                self.hide()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            # Notify parent to hide Spotify-related widgets
            self._notify_spotify_widgets_visibility()
            self._telemetry_last_visibility = False
            return

        # Metadata: title and artist on separate lines; album is intentionally
        # omitted to keep the block compact. Apply Title Case for readability.
        title = smart_title_case((info.title or "").strip())
        artist = smart_title_case((info.artist or "").strip())

        # Snapshot of current visibility, used at the end of the update to
        # decide whether to run a one-shot fade-in or just keep the card
        # visible. Track changes themselves no longer trigger extra fades.
        was_visible = self.isVisible()

        # Typography: header is slightly larger than the base font, the song
        # title is emphasised, and the artist is a touch smaller but still
        # strong enough to read at a glance.
        base_font = max(6, self._font_size)
        header_font = max(6, int(base_font * 1.2))

        # Start from comfortable defaults and then downscale when titles get
        # very long so they do not wrap so aggressively that they collide
        # with the controls row. Artist text follows the title but with a
        # smaller adjustment so hierarchy between the two is preserved.
        title_font_base = max(6, base_font + 3)
        artist_font_base = max(6, base_font - 2)

        title_len = len(title)
        scale_title = 1.0
        if title_len > 40:
            scale_title = 0.86
        if title_len > 55:
            scale_title = 0.76
        if title_len > 70:
            scale_title = 0.66

        # Artist font tracks part of the title scaling so that very long
        # track names compress the whole metadata block slightly without
        # making the artist look disproportionately small.
        scale_artist = 1.0 - (1.0 - scale_title) * 0.4

        title_font = max(6, int(title_font_base * scale_title))
        artist_font = max(6, int(artist_font_base * scale_artist))

        header_weight = 750  # a bit heavier than standard bold
        title_weight = 700
        artist_weight = 600

        # Store logo metrics so paintEvent can size/position the glyph
        # relative to the SPOTIFY text. The logo is kept slightly larger than
        # the SPOTIFY word and the header text is indented accordingly.
        self._header_font_pt = header_font
        self._header_logo_size = max(12, int(header_font * 1.3))
        self._header_logo_margin = self._header_logo_size

        # Build metadata lines with per-line font sizes/weights.
        if not title and not artist:
            body_html = (
                f"<div style='font-size:{base_font}pt; font-weight:500;'>(no metadata)</div>"
            )
        else:
            body_lines_html = []
            if title:
                body_lines_html.append(
                    f"<div style='font-size:{title_font}pt; font-weight:{title_weight};'>{title}</div>"
                )
            if artist:
                body_lines_html.append(
                    f"<div style='margin-top:4px; font-size:{artist_font}pt; font-weight:{artist_weight}; opacity:0.95;'>{artist}</div>"
                )
            body_html = "".join(body_lines_html)

        header_html = (
            f"<div style='font-size:{header_font}pt; font-weight:{header_weight}; "
            f"letter-spacing:1px; margin-left:{self._header_logo_margin + 5}px; "
            f"color:rgba(255,255,255,255);'>SPOTIFY</div>"
        )
        # Outer wrapper just establishes spacing; individual lines carry
        # their own font sizes/weights.
        body_wrapper = f"<div style='margin-top:8px;'>{body_html}</div>"

        html_parts = ["<div style='line-height:1.25'>", header_html, body_wrapper]
        html_parts.append("</div>")
        html = "".join(html_parts)

        self.setTextFormat(Qt.TextFormat.RichText)
        self.setText(html)

        # Lock the card height after the first track so that layout changes
        # (for example when titles wrap to multiple lines) do not cause the
        # widget to move vertically on screen. The height cap is allowed to
        # grow when a later track needs more space, but never shrinks.
        try:
            hint_h = self.sizeHint().height()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            hint_h = 0
        base_min = self.minimumHeight()
        fixed_candidate = max(220, base_min, hint_h)
        if self._fixed_card_height is None or fixed_candidate > self._fixed_card_height:
            self._fixed_card_height = fixed_candidate

        if self._fixed_card_height is not None:
            self.setMinimumHeight(self._fixed_card_height)
            self.setMaximumHeight(self._fixed_card_height)

        # CRITICAL: Decode artwork BEFORE the first-track early return so that
        # artwork is captured on the very first poll. Without this, the first
        # update returns early and artwork is never decoded, causing blank
        # artwork on startup.
        artwork_bytes = getattr(info, "artwork", None)
        if isinstance(artwork_bytes, (bytes, bytearray)) and artwork_bytes:
            try:
                pm = QPixmap()
                if pm.loadFromData(bytes(artwork_bytes)) and not pm.isNull():
                    self._artwork_pixmap = pm
                    logger.debug("[MEDIA_WIDGET] Artwork decoded: %dx%d", pm.width(), pm.height())
            except Exception:
                logger.debug("[MEDIA] Failed to decode artwork pixmap", exc_info=True)

        # CRITICAL: Set content margins BEFORE the first-track early return so
        # that the text layout accounts for artwork space. Without this, the
        # text wraps as if there's no artwork, causing overlap on startup.
        right_margin = max(self._artwork_size + 40, 60)
        self.setContentsMargins(29, 12, right_margin, 40)

        # On the very first non-empty track update we use this call purely
        # to establish a stable layout and fixed height, but keep the widget
        # hidden. The next update with the same track will then perform the
        # actual fade-in so you never see the intermediate size.
        if not self._has_seen_first_track:
            self._has_seen_first_track = True
            try:
                self.hide()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            if not self._telemetry_logged_fade_request:
                logger.info("[MEDIA_WIDGET] First track snapshot captured; waiting for coordinated fade-in")
            # Even though we keep the widget hidden for the very first
            # snapshot to establish layout, we still need to seed the fade
            # machinery so a second update with the same track can actually
            # show the card. If no coordinator exists, schedule a one-shot
            # fade immediately so we do not remain hidden forever.
            parent = self.parent()
            def _starter() -> None:
                if not Shiboken.isValid(self):
                    return
                self._start_widget_fade_in(1500)
                self._notify_spotify_widgets_visibility()
                self._telemetry_last_visibility = True
                # Mark fade-in as completed so future updates can be diff-gated
                self._fade_in_completed = True
            if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
                try:
                    parent.request_overlay_fade_sync("media", _starter)
                except Exception as e:
                    logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                    _starter()
            else:
                _starter()
            return

        try:
            payload = asdict(info)
            payload["state"] = info.state.value
            self.media_updated.emit(payload)
        except Exception:
            # Failing to emit rich diagnostics should not break the widget.
            pass

        # Decode optional artwork bytes (for subsequent updates after first track)
        prev_pm = self._artwork_pixmap
        had_artwork_before = prev_pm is not None and not prev_pm.isNull()
        self._artwork_pixmap = None
        artwork_bytes = getattr(info, "artwork", None)
        if isinstance(artwork_bytes, (bytes, bytearray)) and artwork_bytes:
            try:
                pm = QPixmap()
                if pm.loadFromData(bytes(artwork_bytes)) and not pm.isNull():
                    self._artwork_pixmap = pm

                    # Fade in the artwork whenever it appears for the first
                    # time or when the logical track metadata changes. This
                    # keeps the card, header and controls perfectly stable
                    # while giving album art a gentle dissolve on updates.
                    should_fade_artwork = False
                    if not had_artwork_before:
                        should_fade_artwork = True
                    else:
                        try:
                            if prev_info is None:
                                should_fade_artwork = True
                            else:
                                def _norm(s: Optional[str]) -> str:
                                    return (s or "").strip()

                                if (
                                    _norm(getattr(prev_info, "title", None))
                                    != _norm(getattr(info, "title", None))
                                    or _norm(getattr(prev_info, "artist", None))
                                    != _norm(getattr(info, "artist", None))
                                    or _norm(getattr(prev_info, "album", None))
                                    != _norm(getattr(info, "album", None))
                                ):
                                    should_fade_artwork = True
                        except Exception as e:
                            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                            should_fade_artwork = False

                    if should_fade_artwork:
                        self._start_artwork_fade_in()
            except Exception:
                logger.debug("[MEDIA] Failed to decode artwork pixmap", exc_info=True)

        # Reserve space for artwork plus breathing room on the right even
        # when artwork is missing so the widget size stays stable. Text stays
        # anchored on the left side.
        right_margin = max(self._artwork_size + 40, 60)
        # Extra bottom margin so the painted controls row has breathing
        # room above the card edge while keeping text clear of the glyphs.
        self.setContentsMargins(29, 12, right_margin, 40)

        # After adjusting margins, recompute the widget's anchored position
        # once so we do not "jump" after the fade completes.
        if self.parent():
            self._update_position()

        # For the very first time the widget becomes visible we use a
        # simple fade-in coordinated with other overlays (weather/Reddit)
        # via the DisplayWidget so they appear together. Subsequent track
        # changes update in-place so the card and controls do not move.
        if not was_visible:
            parent = self.parent()

            def _starter() -> None:
                # Guard against widget being deleted before deferred callback runs
                if not Shiboken.isValid(self):
                    return
                self._start_widget_fade_in(1500)
                # Notify Spotify widgets to show now that media is visible
                self._notify_spotify_widgets_visibility()
                self._telemetry_last_visibility = True

            if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
                try:
                    if is_verbose_logging() or not self._telemetry_logged_fade_request:
                        logger.info("[MEDIA_WIDGET] Requesting coordinated fade sync")
                        self._telemetry_logged_fade_request = True
                    parent.request_overlay_fade_sync("media", _starter)
                except Exception as e:
                    logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                    _starter()
            else:
                _starter()
        else:
            try:
                self.show()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            # Notify Spotify widgets in case they need to sync visibility
            self._notify_spotify_widgets_visibility()
            self._telemetry_last_visibility = True
    
    def _gate_fft_worker(self, should_run: bool) -> None:
        """Start or stop the FFT worker based on media widget visibility.
        
        This saves compute when Spotify is not active by stopping the FFT
        worker process entirely rather than just gating FFT processing.
        """
        parent = self.parent()
        if parent is None:
            return
        
        # Get ProcessSupervisor from parent chain
        supervisor = None
        try:
            # Try display widget first
            supervisor = getattr(parent, "_process_supervisor", None)
            if supervisor is None:
                # Try via widget manager
                wm = getattr(parent, "_widget_manager", None)
                if wm is not None:
                    supervisor = getattr(wm, "_process_supervisor", None)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        
        if supervisor is None:
            return
        
        try:
            from core.process import WorkerType
            
            is_running = supervisor.is_running(WorkerType.FFT)
            
            if should_run and not is_running:
                # Media visible - start FFT worker
                if is_perf_metrics_enabled():
                    logger.debug("[PERF] Starting FFT worker (media widget visible)")
                supervisor.start(WorkerType.FFT)
            elif not should_run and is_running:
                # Media hidden - stop FFT worker to save compute
                if is_perf_metrics_enabled():
                    logger.debug("[PERF] Stopping FFT worker (media widget hidden)")
                supervisor.stop(WorkerType.FFT)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] FFT worker gating failed: %s", e)

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
        """Internal paint implementation."""
        super().paintEvent(event)

        try:
            painter = QPainter(self)
            try:
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

            # Optional header frame on the left side around logo + SPOTIFY.
            self._paint_header_frame(painter)

            pm = self._artwork_pixmap
            if pm is not None and not pm.isNull():
                # Artwork should be the dominant visual element but must
                # respect padding so it never clips. We clamp by height and
                # the requested logical size, avoiding overly conservative
                # width-based caps.
                max_by_height = max(24, self.height() - 60)  # 30px top/bottom padding
                size = max(48, min(self._artwork_size, max_by_height))
                if size > 0:
                    # Scale in device pixels but compute the border in logical
                    # coordinates so the frame fits tightly even on high-DPI
                    # displays.
                    try:
                        dpr = float(self.devicePixelRatioF())
                    except Exception as e:
                        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                        dpr = 1.0
                    scale_dpr = max(1.0, dpr)

                    # Base square frame for album artwork.
                    frame_w = size
                    frame_h = size

                    # For clearly non-square artwork (e.g. Spotify video
                    # thumbnails), widen the frame towards the source aspect
                    # ratio while still using the existing cover-style
                    # scaling. This keeps album covers square but allows
                    # video-shaped frames to feel less distorted without
                    # introducing letterboxing.
                    try:
                        src_w = float(pm.width())
                        src_h = float(pm.height())
                        aspect = src_w / src_h if (src_w > 0.0 and src_h > 0.0) else 1.0
                    except Exception as e:
                        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                        aspect = 1.0

                    if aspect > 0.0:
                        # Treat anything significantly wider than tall as a
                        # "video"-ish frame. We keep the existing square
                        # behaviour for near-1:1 artwork so album covers are
                        # untouched.
                        if aspect >= 1.4:
                            # Grow width up to a reasonable multiple of the
                            # base size, but clamp to the card width so we
                            # never bleed past the left text column.
                            natural_w = int(size * min(aspect, 2.4))
                            max_card_w = max(48, self.width() - 80)
                            frame_w = max(48, min(natural_w, max_card_w))
                            frame_h = size
                        elif aspect <= 0.7:
                            # Very tall artwork (rare in practice) – invert
                            # the logic so we extend height while keeping the
                            # base width.
                            natural_h = int(size * min(1.0 / max(aspect, 0.1), 2.4))
                            max_card_h = max(48, self.height() - 80)
                            frame_h = max(48, min(natural_h, max_card_h))

                    # Scale-to-fill inside the frame while preserving aspect
                    # ratio (object-fit: cover). We scale with
                    # KeepAspectRatioByExpanding and then centre the pixmap
                    # behind the frame, letting the clip path define the
                    # visible region.
                    #
                    # PERF: Cache scaled artwork to avoid expensive SmoothTransformation
                    # on every paint. Cache key includes pixmap identity, frame size, and DPR.
                    cache_key = (id(pm), frame_w, frame_h, scale_dpr)
                    if self._scaled_artwork_cache_key == cache_key and self._scaled_artwork_cache is not None:
                        scaled = self._scaled_artwork_cache
                    else:
                        target_w_px = int(frame_w * scale_dpr)
                        target_h_px = int(frame_h * scale_dpr)
                        scaled = pm.scaled(
                            target_w_px,
                            target_h_px,
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        try:
                            scaled.setDevicePixelRatio(scale_dpr)
                        except Exception as e:
                            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                        self._scaled_artwork_cache = scaled
                        self._scaled_artwork_cache_key = cache_key

                    scaled_logical_w = max(1, int(round(scaled.width() / scale_dpr)))
                    scaled_logical_h = max(1, int(round(scaled.height() / scale_dpr)))

                    # Keep a fixed inset from the top/right card borders so the
                    # artwork and its border never touch the outer frame.
                    pad = 20
                    x = max(pad, self.width() - pad - frame_w)
                    y = pad
                    painter.save()
                    try:
                        if self._artwork_opacity != 1.0:
                            painter.setOpacity(max(0.0, min(1.0, float(self._artwork_opacity))))

                        border_rect = QRect(x, y, frame_w, frame_h).adjusted(-1, -1, 1, 1)

                        # Draw a soft drop shadow behind the artwork frame
                        # using multiple passes with increasing offset/blur
                        painter.save()
                        painter.setPen(Qt.PenStyle.NoPen)
                        # Multi-pass shadow for softer feathering
                        shadow_passes = [
                            (2, 25),   # inner shadow layer
                            (4, 35),   # mid shadow layer
                            (6, 45),   # outer shadow layer
                            (8, 30),   # furthest, faintest layer
                        ]
                        for offset, alpha in shadow_passes:
                            shadow_rect = border_rect.adjusted(offset, offset, offset, offset)
                            shadow_path = QPainterPath()
                            if self._rounded_artwork_border:
                                radius = min(shadow_rect.width(), shadow_rect.height()) / 8.0
                                shadow_path.addRoundedRect(shadow_rect, radius, radius)
                            else:
                                shadow_path.addRect(shadow_rect)
                            painter.setBrush(QColor(0, 0, 0, alpha))
                            painter.drawPath(shadow_path)
                        painter.restore()

                        # Clip the artwork to the same rounded/square frame so
                        # pixels never bleed out past the border corners.
                        path = QPainterPath()
                        if self._rounded_artwork_border:
                            radius = min(border_rect.width(), border_rect.height()) / 8.0
                            path.addRoundedRect(border_rect, radius, radius)
                        else:
                            path.addRect(border_rect)
                        painter.setClipPath(path)

                        # Centre the scaled artwork inside the frame; because
                        # we used KeepAspectRatioByExpanding above, the
                        # pixmap will completely cover the frame in at least
                        # one dimension and any overflow is clipped by the
                        # border path.
                        cx = x + frame_w // 2
                        cy = y + frame_h // 2
                        offset_x = int(round(cx - scaled_logical_w / 2))
                        offset_y = int(round(cy - scaled_logical_h / 2))

                        painter.drawPixmap(offset_x, offset_y, scaled)

                        # Artwork border matching the widget frame colour/opacity.
                        if self._bg_border_width > 0 and self._bg_border_color.alpha() > 0:
                            pen = painter.pen()
                            pen.setColor(self._bg_border_color)
                            # A bit thicker than the card frame so the
                            # artwork reads as a strong focal element.
                            pen.setWidth(max(1, self._bg_border_width + 2))
                            painter.setPen(pen)
                            painter.setBrush(Qt.BrushStyle.NoBrush)
                            if self._rounded_artwork_border:
                                painter.drawPath(path)
                            else:
                                painter.drawRect(border_rect)
                    finally:
                        painter.restore()
            # Paint the Spotify logo for the header using high-DPI aware
            # scaling so it stays crisp and properly aligned with the SPOTIFY
            # word rendered by QLabel's rich text.
            self._paint_header_logo(painter)

            # Finally, paint the transport controls row as a static stripe
            # along the bottom of the text column so its position never
            # drifts between tracks.
            self._paint_controls_row(painter)
        except Exception:
            logger.debug("[MEDIA] Failed to paint artwork pixmap", exc_info=True)

    def _load_brand_pixmap(self) -> Optional[QPixmap]:
        """Best-effort load of a Spotify logo from the shared images folder.

        We prefer the high-resolution primary logo asset when present so that
        the glyph remains sharp even when scaled up on high-DPI displays.
        """

        try:
            images_dir = Path(__file__).resolve().parent.parent / "images"
            candidates = [
                "Spotify_Primary_Logo_RGB_Black.png",
                "spotify_logo.png",
                "SpotifyLogo.png",
                "spotify.png",
            ]
            for name in candidates:
                candidate = images_dir / name
                if candidate.exists() and candidate.is_file():
                    pm = QPixmap(str(candidate))
                    if not pm.isNull():
                        return pm
        except Exception:
            logger.debug("[MEDIA] Failed to load Spotify logo", exc_info=True)
        return None

    def _paint_header_frame(self, painter: QPainter) -> None:
        """Paint a rounded sub-frame around the logo + SPOTIFY header.

        The frame inherits the media widget's background and border colours
        and opacities so it feels like a lighter inner container instead of a
        separate widget. It is confined to the left text column and never
        overlaps the artwork on the right.
        """

        if not self._show_header_frame:
            return
        if not self._show_background:
            # When the main card background is disabled, keep the header frame
            # off as well so styling stays consistent.
            return
        if self._bg_border_width <= 0 or self._bg_border_color.alpha() <= 0:
            return

        margins = self.contentsMargins()
        # Slightly offset the frame so the logo+SPOTIFY group reads more
        # visually centred within it. Moving the frame left and down has the
        # effect of the header content appearing ~5px right and ~3px up
        # relative to the border without disturbing their mutual alignment.
        left = margins.left() - 5
        top = margins.top() + 3

        # Use the same font metrics as the SPOTIFY header so the frame height
        # comfortably contains both the wordmark and the logo glyph.
        try:
            header_font_pt = int(self._header_font_pt) if self._header_font_pt > 0 else self._font_size
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            header_font_pt = self._font_size

        font = QFont(self._font_family, header_font_pt, QFont.Weight.Bold)
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance("SPOTIFY")
        text_h = fm.height()

        logo_size = max(1, int(self._header_logo_size))
        # Gap between logo and text mirrors the HTML margin.
        gap = max(6, self._header_logo_margin - logo_size)

        pad_x = 10
        pad_y = 6

        inner_w = logo_size + gap + text_w
        row_h = max(text_h, logo_size)

        extra_right_pad = 24
        width = int(inner_w + pad_x * 2 + extra_right_pad)
        height = int(row_h + pad_y * 2)

        # Constrain the frame so it stays entirely within the text column on
        # the left, leaving space for the artwork and its padding on the right.
        max_width = max(0, self.width() - margins.right() - left - 10)
        if max_width and width > max_width:
            width = max_width

        if width <= 0 or height <= 0:
            return

        rect = QRect(left, top, width, height)
        radius = min(rect.width(), rect.height()) / 2.5

        # Use shadow helper for border with drop shadow
        draw_rounded_rect_with_shadow(
            painter,
            rect,
            radius,
            self._bg_border_color,
            max(1, self._bg_border_width),
        )

    def _paint_header_logo(self, painter: QPainter) -> None:
        """Paint the Spotify logo glyph next to the SPOTIFY header text.

        This is drawn separately from the rich-text header so that we can
        control DPI scaling and alignment precisely while keeping the
        markup simple on the QLabel side.
        """

        pm = self._brand_pixmap
        size = self._header_logo_size
        if pm is None or pm.isNull() or size <= 0:
            return

        try:
            dpr = float(self.devicePixelRatioF())
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            dpr = 1.0

        target_px = int(size * max(1.0, dpr))
        if target_px <= 0:
            return

        scaled = pm.scaled(
            target_px,
            target_px,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        try:
            scaled.setDevicePixelRatio(max(1.0, dpr))
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

        margins = self.contentsMargins()
        x = margins.left() + 7

        # Align the logo vertically with the SPOTIFY text by centring the
        # glyph within the first header line's text metrics instead of
        # simply pinning it to the top margin.
        try:
            header_font_pt = int(self._header_font_pt) if self._header_font_pt > 0 else self._font_size
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            header_font_pt = self._font_size

        font = QFont(self._font_family, header_font_pt, QFont.Weight.Bold)
        fm = QFontMetrics(font)
        line_height = fm.height()
        # Nudge the visual centre a bit lower than the strict mid-line so the
        # SPOTIFY word and glyph feel horizontally balanced. We then add a
        # small fixed offset so the glyph does not touch the header frame.
        line_centre = margins.top() + (line_height * 0.6)
        icon_half = float(self._header_logo_size) / 2.0
        y = int(line_centre - icon_half) + 4
        if y < margins.top() + 4:
            y = margins.top() + 4

        painter.save()
        try:
            painter.drawPixmap(x, y, scaled)
        finally:
            painter.restore()

    def _paint_controls_row(self, painter: QPainter) -> None:
        """Paint a static transport controls row along the bottom.

        The controls are always aligned to the thirds of the text content
        width (between contentsMargins.left/right) so they visually match
        the click routing implemented in DisplayWidget.mousePressEvent.
        """

        if not self._show_controls:
            return

        info = self._last_info
        if info is None and self._pending_state_override is None:
            return

        try:
            base_state = info.state if info is not None else MediaPlaybackState.UNKNOWN
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            base_state = MediaPlaybackState.UNKNOWN

        state = self._pending_state_override or base_state

        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return

        margins = self.contentsMargins()
        content_left = margins.left()
        content_right = width - margins.right()
        if content_right <= content_left:
            return

        content_width = content_right - content_left
        third = content_width / 3.0

        controls_font = max(6, self._font_size - 3)
        font = QFont(self._font_family, controls_font, QFont.Weight.Medium)

        painter.save()
        try:
            painter.setFont(font)
            fm = QFontMetrics(font)

            row_height = fm.height() + 4

            # Previous anchoring kept the row just above the text bottom
            # margin. To free up more vertical space for long titles while
            # keeping the widget's geometry unchanged, we move the controls
            # down by roughly one SPOTIFY header height and then clamp the
            # result inside the card bounds.
            prev_row_top = height - margins.bottom() - row_height - 4

            try:
                header_font_pt = int(self._header_font_pt) if self._header_font_pt > 0 else self._font_size
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                header_font_pt = self._font_size

            header_fm = QFontMetrics(QFont(self._font_family, header_font_pt, QFont.Weight.Bold))
            header_h = header_fm.height()

            # Target position: one header height lower than the previous
            # value, but never so low that the glyphs touch the card edge.
            bottom_pad = 8
            bottom_limit = height - row_height - bottom_pad
            target_row_top = prev_row_top + header_h
            row_top = max(margins.top(), min(bottom_limit, target_row_top))

            from PySide6.QtCore import QRect as _QRect

            left_rect = _QRect(
                int(content_left),
                int(row_top),
                int(third),
                int(row_height),
            )
            centre_rect = _QRect(
                int(content_left + third),
                int(row_top),
                int(third),
                int(row_height),
            )
            right_rect = _QRect(
                int(content_left + 2 * third),
                int(row_top),
                int(third),
                int(row_height),
            )

            prev_sym = "\u2190"  # LEFTWARDS ARROW
            next_sym = "\u2192"  # RIGHTWARDS ARROW
            if state == MediaPlaybackState.PLAYING:
                centre_sym = "||"  # pause
            else:
                centre_sym = "\u25b6"  # play

            inactive_color = QColor(200, 200, 200, 230)
            active_color = QColor(255, 255, 255, 255)

            # Side arrows
            pen = painter.pen()
            pen.setColor(inactive_color)
            painter.setPen(pen)
            painter.drawText(left_rect, Qt.AlignmentFlag.AlignCenter, prev_sym)
            painter.drawText(right_rect, Qt.AlignmentFlag.AlignCenter, next_sym)

            # Centre play/pause gets a slightly heavier weight and full white
            # to stand out just enough without drifting in position.
            # Use smaller font for pause "||" since it's two characters vs one for play
            pause_font_size = controls_font - 2 if centre_sym == "||" else controls_font
            font_centre = QFont(self._font_family, pause_font_size, QFont.Weight.Bold)
            painter.setFont(font_centre)
            pen.setColor(active_color)
            painter.setPen(pen)
            painter.drawText(centre_rect, Qt.AlignmentFlag.AlignCenter, centre_sym)
        finally:
            painter.restore()

    def _start_widget_fade_in(self, duration_ms: int = 1500) -> None:
        """Fade the entire widget in, then attach the global drop shadow."""
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
            return

        try:
            ShadowFadeProfile.start_fade_in(
                self,
                self._shadow_config,
                has_background_frame=self._show_background,
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
            if self._shadow_config is not None:
                try:
                    apply_widget_shadow(
                        self,
                        self._shadow_config,
                        has_background_frame=self._show_background,
                    )
                except Exception:
                    logger.debug(
                        "[MEDIA] Failed to apply widget shadow in fallback path",
                        exc_info=True,
                    )

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
                    self.update()
                except Exception as e:
                    logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            
            def _on_finished() -> None:
                self._artwork_anim = None
                self._artwork_opacity = 1.0
                self.update()
            
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
            self.update()
