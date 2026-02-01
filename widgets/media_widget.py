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
from pathlib import Path
from typing import Optional, TYPE_CHECKING, ClassVar

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Qt, Signal, QVariantAnimation, QRect, QRectF, QPoint
from PySide6.QtGui import (
    QFont,
    QColor,
    QPixmap,
    QPainter,
    QPainterPath,
    QFontMetrics,
    QLinearGradient,
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
from widgets.shadow_utils import ShadowFadeProfile, draw_rounded_rect_with_shadow
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
        self._slab_effect_enabled: bool = False  # Slab Effect - Experimental
        self._last_display_update_ts: float = 0.0
        self._skipped_identity_updates: int = 0
        self._max_identity_skip: int = 4
        
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

    def set_slab_effect_enabled(self, enabled: bool) -> None:
        """Enable or disable the 3D slab effect on the controls row."""
        self._slab_effect_enabled = bool(enabled)
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
        
        # Update shared cache when we have valid info
        if info is not None:
            cls = type(self)
            cls._shared_last_valid_info = info
            cls._shared_last_valid_info_ts = time.monotonic()
        
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
                    # Update timer interval from idle (5s) to fast (1s)
                    self._ensure_timer(force=True)
            
            # Adaptive polling: advance to slower interval after 2 successful polls
            self._polls_at_current_stage += 1
            if self._polls_at_current_stage >= 2:
                self._advance_poll_stage()
            
            # Diff gating: skip update if track identity unchanged
            # Always process first track (when _last_track_identity is None)
            # Also process if we haven't completed fade-in yet (need 2 updates for fade-in)
            if (
                current_identity == self._last_track_identity
                and self._last_track_identity is not None
                and self._fade_in_completed
            ):
                self._skipped_identity_updates += 1
                if self._skipped_identity_updates <= self._max_identity_skip:
                    if is_perf_metrics_enabled():
                        logger.debug(
                            "[PERF] Media widget update skipped (diff gating - %d/%d)",
                            self._skipped_identity_updates,
                            self._max_identity_skip,
                        )
                    return
                if is_perf_metrics_enabled():
                    logger.debug("[PERF] Forcing metadata refresh after repeated skips")

            # Track changed - update identity and proceed
            self._last_track_identity = current_identity
            self._skipped_identity_updates = 0
            self._last_display_update_ts = time.monotonic()
            if is_perf_metrics_enabled():
                logger.debug("[PERF] Media widget update applied (track changed)")

        if info is None:
            # MULTI-DISPLAY FIX: Check if other widgets have valid info
            cls = type(self)
            shared_info = cls._get_shared_valid_info()
            if shared_info is not None:
                logger.debug("[MEDIA_WIDGET] Using shared info from another display")
                info = shared_info
                self._last_info = info
                # Don't count this as None - fall through to display shared info
            else:
                # No shared info - proceed with normal None handling
                pass
        
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
                # Update timer interval from active (2.5s) to idle (5s)
                self._ensure_timer(force=True)
            
            # No active media session (e.g. Spotify not playing) – hide widget with graceful fade
            last_vis = self._telemetry_last_visibility
            if last_vis or last_vis is None:
                logger.info("[MEDIA_WIDGET] No active media session; hiding media card")
            self._artwork_pixmap = None
            self._scaled_artwork_cache = None
            self._scaled_artwork_cache_key = None
            
            # Graceful fade out instead of instant hide
            if self.isVisible():
                try:
                    from widgets.shadow_utils import ShadowFadeProfile
                    ShadowFadeProfile.start_fade_out(
                        self,
                        duration_ms=800,
                        on_complete=lambda: self._complete_hide_sequence()
                    )
                except Exception as e:
                    logger.debug("[MEDIA_WIDGET] Fade out failed, hiding instantly: %s", e)
                    self._complete_hide_sequence()
            else:
                self._complete_hide_sequence()
            
            self._telemetry_last_visibility = False
            return

        # Metadata: title and artist on separate lines; album is intentionally
        # omitted to keep the block compact. Apply Title Case for readability.
        title = smart_title_case((info.title or "").strip())
        artist = smart_title_case((info.artist or "").strip())

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
            metadata_complexity = 0
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
            metadata_complexity = len(title.strip()) + len(artist.strip())

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
        
        # Adjust artwork vertical bias so shorter metadata keeps the frame closer to center.
        if metadata_complexity <= 0:
            self._artwork_vertical_bias = 0.58
        elif metadata_complexity <= 40:
            self._artwork_vertical_bias = 0.55
        elif metadata_complexity <= 80:
            self._artwork_vertical_bias = 0.45
        else:
            self._artwork_vertical_bias = 0.32

        # Lock the card height after the first track so that layout changes
        # (for example when titles wrap to multiple lines) do not cause the
        # widget to move vertically on screen. The height NEVER grows after first track.
        # Text eliding handles overflow instead of resizing.
        if self._fixed_card_height is None:
            try:
                hint_h = self.sizeHint().height()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                hint_h = 0
            base_min = self.minimumHeight()
            control_padding = self._controls_row_min_height()
            self._fixed_card_height = max(220, base_min, hint_h + control_padding)

        # Lock height permanently - never grow
        self.setMinimumHeight(self._fixed_card_height)
        self.setMaximumHeight(self._fixed_card_height)

        # CRITICAL: Decode artwork BEFORE the first-track early return so that
        # artwork is captured on the very first poll. Without this, the first
        # update returns early and artwork is never decoded, causing blank
        # artwork on startup.
        artwork_pm = self._decode_artwork_pixmap(getattr(info, "artwork", None))
        if artwork_pm is not None:
            self._artwork_pixmap = artwork_pm
            if is_verbose_logging():
                logger.debug("[MEDIA_WIDGET] Artwork decoded: %dx%d", artwork_pm.width(), artwork_pm.height())

        # CRITICAL: Set content margins BEFORE the first-track early return so
        # that the text layout accounts for artwork space. Without this, the
        # text wraps as if there's no artwork, causing overlap on startup.
        right_margin = max(self._artwork_size + 40, 60)
        # Reduce bottom margin so controls sit closer to the card edge.
        self.setContentsMargins(29, 12, right_margin, self._controls_row_margin())

        # On the very first non-empty track update we use this call to
        # establish a stable layout (card stays hidden until fade sync), but we
        # still need to propagate media state to dependent widgets so they can
        # react immediately (visualizer wake-up, volume visibility, etc.).
        if not self._has_seen_first_track:
            self._has_seen_first_track = True
            self._emit_media_update(info)
            try:
                self.hide()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            if not self._telemetry_logged_fade_request:
                logger.info("[MEDIA_WIDGET] First track snapshot captured; waiting for coordinated fade-in")
            parent = self.parent()

            def _starter() -> None:
                if not Shiboken.isValid(self):
                    return
                self._start_widget_fade_in(1500)
                self._notify_spotify_widgets_visibility()
                self._telemetry_last_visibility = True

            if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
                try:
                    parent.request_overlay_fade_sync("media", _starter)
                except Exception as e:
                    logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                    _starter()
            else:
                _starter()
            return

        self._emit_media_update(info)

        # Decode optional artwork bytes (for subsequent updates after first track)
        prev_pm = self._artwork_pixmap
        had_artwork_before = prev_pm is not None and not prev_pm.isNull()
        self._artwork_pixmap = None
        artwork_pm = self._decode_artwork_pixmap(getattr(info, "artwork", None))
        if artwork_pm is not None:
            self._artwork_pixmap = artwork_pm

            # Fade in artwork whenever it appears for the first time or when metadata changes.
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
        """Compute geometry for the transport controls row."""
        if not self._show_controls:
            self._controls_layout_cache = None
            return None

        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            self._controls_layout_cache = None
            return None

        margins = self.contentsMargins()
        content_left = margins.left()
        content_right = width - margins.right()
        content_width = content_right - content_left
        if content_width <= 60:
            self._controls_layout_cache = None
            return None

        controls_font_pt = max(8, int((self._font_size - 2) * 0.9))
        font = QFont(self._font_family, controls_font_pt, QFont.Weight.Medium)
        fm = QFontMetrics(font)
        row_height = max(self._controls_row_min_height(), int((fm.height() + 10) * 0.85))

        try:
            header_font_pt = int(self._header_font_pt) if self._header_font_pt > 0 else self._font_size
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            header_font_pt = self._font_size

        cache_key = (
            width,
            height,
            margins.left(),
            margins.top(),
            margins.right(),
            margins.bottom(),
            controls_font_pt,
            header_font_pt,
        )
        cached = self._controls_layout_cache
        if cached is not None and cached.get("_cache_key") == cache_key:
            return cached

        header_metrics = QFontMetrics(QFont(self._font_family, header_font_pt, QFont.Weight.Bold))
        header_height = header_metrics.height()

        base_row_top = height - margins.bottom() - row_height - 5  # Shift up 5px for 3D depth effect
        min_row_top = margins.top() + header_height + 6
        row_top = max(min_row_top, base_row_top)
        if row_top + row_height > height - margins.bottom():
            row_top = max(margins.top(), height - margins.bottom() - row_height)
        if row_top < margins.top():
            row_top = margins.top()

        row_rect = QRect(
            int(content_left),
            int(row_top),
            int(content_width),
            int(row_height),
        )

        slot_width = content_width / 3.0
        inner_pad_x = max(5.0, slot_width * 0.07)
        inner_pad_y = max(2.0, row_height * 0.16)
        hit_slop = max(8, int(row_height * 0.28))

        button_rects = {}
        hit_rects = {}
        for index, key in enumerate(("prev", "play", "next")):
            slot_left = content_left + slot_width * index
            rect = QRect(
                int(slot_left + inner_pad_x),
                int(row_top + inner_pad_y),
                int(slot_width - inner_pad_x * 2),
                int(row_height - inner_pad_y * 2),
            )
            button_rects[key] = rect
            hit_rects[key] = rect.adjusted(-hit_slop, -hit_slop, hit_slop, hit_slop)

        layout = {
            "font": font,
            "row_rect": row_rect,
            "button_rects": button_rects,
            "hit_rects": hit_rects,
        }
        layout["_cache_key"] = cache_key
        self._controls_layout_cache = layout
        return layout

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
    
    def _paint_controls_row(self, painter: QPainter) -> None:
        """Paint transport controls aligned with the click hit regions."""
        layout = self._compute_controls_layout()
        if layout is None:
            return

        font: QFont = layout["font"]
        row_rect: QRect = layout["row_rect"]
        button_rects: dict = layout["button_rects"]

        painter.save()
        try:
            base_color = QColor(self._bg_color)
            matte_top = QColor(base_color)
            matte_bottom = QColor(base_color)
            matte_top.setAlpha(min(255, int(base_color.alpha() * 0.95) + 30))
            matte_bottom.setAlpha(min(255, int(base_color.alpha() * 0.85)))

            # 3D slab effect: filled darker border 4px right/4px down, with light shadow
            if self._slab_effect_enabled:
                shadow_offset_x = 4
                shadow_offset_y = 4
                slab_rect = row_rect.adjusted(shadow_offset_x, shadow_offset_y, shadow_offset_x, shadow_offset_y)
                
                # Slab fill: same gradient as control bar but darker
                slab_matte_top = QColor(matte_top).darker(115)
                slab_matte_bottom = QColor(matte_bottom).darker(115)
                
                # Light shadow around the slab (drawn first, behind slab)
                shadow_color = QColor(0, 0, 0, 40)  # Very light shadow
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(shadow_color)
                shadow_rect = slab_rect.adjusted(-2, -2, 2, 2)
                painter.drawRoundedRect(shadow_rect, self._controls_row_radius + 1, self._controls_row_radius + 1)
                
                # Draw the filled slab underneath with matching gradient
                slab_gradient = QLinearGradient(slab_rect.topLeft(), slab_rect.bottomLeft())
                slab_gradient.setColorAt(0.0, slab_matte_top)
                slab_gradient.setColorAt(1.0, slab_matte_bottom)
                painter.setBrush(slab_gradient)
                painter.drawRoundedRect(slab_rect, self._controls_row_radius, self._controls_row_radius)
                
                # Slab outline: white 10% darker than control bar outline
                slab_outline = QColor(255, 255, 255, self._controls_row_outline_alpha).darker(110)
                painter.setPen(slab_outline)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(slab_rect, self._controls_row_radius, self._controls_row_radius)

            # Main gradient fill (drawn on top of shadow)
            gradient = QLinearGradient(row_rect.topLeft(), row_rect.bottomLeft())
            gradient.setColorAt(0.0, matte_top)
            gradient.setColorAt(1.0, matte_bottom)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(row_rect, self._controls_row_radius, self._controls_row_radius)

            # Inner matte outline (2px thicker outer border)
            outline = QColor(255, 255, 255, self._controls_row_outline_alpha)
            # Outer shadow edge (bottom/right of row rect)
            painter.setPen(QColor(0, 0, 0, self._controls_row_shadow_alpha))
            painter.drawRoundedRect(
                row_rect.adjusted(2, 2, -2, -2),
                self._controls_row_radius - 1,
                self._controls_row_radius - 1,
            )
            # Inner highlight edge (top/left of row rect)
            painter.setPen(outline)
            painter.drawRoundedRect(
                row_rect.adjusted(0, 0, 0, 0),
                self._controls_row_radius,
                self._controls_row_radius,
            )

            # Divider lines (relative to row_rect)
            divider_color = QColor(255, 255, 255, 55)
            painter.setPen(divider_color)
            top_divider = row_rect.top() + int(row_rect.height() * 0.15)
            bottom_divider = row_rect.bottom() - int(row_rect.height() * 0.15)
            for i in range(1, 3):
                x = row_rect.left() + int(row_rect.width() * i / 3.0)
                painter.drawLine(x, top_divider, x, bottom_divider)

            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255, 225))
            for key, rect in button_rects.items():
                self._draw_control_icon(painter, rect, key)

            # Click feedback overlay
            if self._controls_feedback:
                painter.setPen(Qt.PenStyle.NoPen)
                for key, rect in button_rects.items():
                    intensity = max(0.0, min(1.0, self._controls_feedback_progress.get(key, 0.0)))
                    if intensity <= 0.0:
                        continue

                    base_rect = QRectF(rect)
                    scale = 1.0 + self._controls_feedback_scale_boost * intensity
                    if scale > 1.0:
                        delta_w = base_rect.width() * (scale - 1.0) * 0.5
                        delta_h = base_rect.height() * (scale - 1.0) * 0.5
                        highlight_rect = base_rect.adjusted(-delta_w, -delta_h, delta_w, delta_h)
                    else:
                        highlight_rect = base_rect

                    radius = max(4.0, min(highlight_rect.width(), highlight_rect.height()) * 0.3)
                    glow_expand = max(2.0, min(highlight_rect.width(), highlight_rect.height()) * 0.12)

                    # Soft outer glow
                    glow_rect = highlight_rect.adjusted(-glow_expand, -glow_expand, glow_expand, glow_expand)
                    glow_color = QColor(255, 255, 255, int(90 * intensity))
                    painter.setBrush(glow_color)
                    painter.drawRoundedRect(glow_rect, radius + glow_expand, radius + glow_expand)

                    # Bright gradient core
                    gradient = QLinearGradient(
                        highlight_rect.topLeft(), highlight_rect.bottomLeft()
                    )
                    gradient.setColorAt(0.0, QColor(255, 255, 255, int(255 * intensity)))
                    gradient.setColorAt(0.6, QColor(255, 255, 255, int(215 * intensity)))
                    gradient.setColorAt(1.0, QColor(255, 255, 255, int(170 * intensity)))
                    painter.setBrush(gradient)
                    painter.drawRoundedRect(highlight_rect, radius, radius)
        finally:
            painter.restore()
    
    def _draw_control_icon(self, painter: QPainter, rect: QRect, key: str) -> None:
        """Draw a single control icon (prev/play/next)."""
        state = MediaPlaybackState.UNKNOWN
        if self._last_info:
            state = self._last_info.state

        prev_sym = "\u2190"  # LEFTWARDS ARROW
        next_sym = "\u2192"  # RIGHTWARDS ARROW
        if state == MediaPlaybackState.PLAYING:
            centre_sym = "||"  # pause
        else:
            centre_sym = "\u25b6"  # play

        inactive_color = QColor(200, 200, 200, 230)
        active_color = QColor(255, 255, 255, 255)

        if key == "prev":
            painter.setPen(inactive_color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, prev_sym)
        elif key == "next":
            painter.setPen(inactive_color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, next_sym)
        elif key == "play":
            # Centre play/pause gets heavier weight
            pause_font_size = self._font_size - 4 if centre_sym == "||" else self._font_size - 2
            font_centre = QFont(self._font_family, pause_font_size, QFont.Weight.Bold)
            painter.setFont(font_centre)
            painter.setPen(active_color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, centre_sym)
    
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
    
    def _start_widget_fade_in(self, duration_ms: int = 1500) -> None:
        """Fade the entire widget in."""
        try:
            from widgets.shadow_utils import ShadowFadeProfile
            ShadowFadeProfile.start_fade_in(
                self,
                duration_ms=duration_ms,
                on_complete=lambda: self._handle_fade_in_complete()
            )
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Fade in failed, showing instantly: %s", e)
            self.show()
            self._handle_fade_in_complete()
    
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
    # Shared Feedback System (Class Methods)
    # ------------------------------------------------------------------
    
    @classmethod
    def _ensure_shared_feedback_timer(cls) -> None:
        """Ensure shared feedback timer is running."""
        timer = cls._shared_feedback_timer
        if timer is None:
            timer = QTimer()
            timer.setTimerType(Qt.TimerType.PreciseTimer)
            timer.setInterval(cls._shared_feedback_timer_interval_ms)
            timer.timeout.connect(cls._on_shared_feedback_tick)
            cls._shared_feedback_timer = timer
        if not timer.isActive():
            timer.start()
            if is_perf_metrics_enabled():
                logger.debug("[PERF] Started shared feedback timer")
    
    @classmethod
    def _maybe_stop_shared_feedback_timer(cls) -> None:
        """Stop timer if no active feedback (FIXED VERSION)."""
        timer = cls._shared_feedback_timer
        if timer is None or not timer.isActive():
            return
        
        # Check if ANY instance has active feedback
        has_feedback = False
        for instance in list(cls._instances):
            try:
                if not Shiboken.isValid(instance):
                    continue
            except Exception:
                continue
            # Check both local feedback AND shared events
            if instance._controls_feedback:
                has_feedback = True
                break
        
        # Also check shared events dict
        if not has_feedback and cls._shared_feedback_events:
            has_feedback = True
        
        # Stop timer only if NO feedback anywhere
        if not has_feedback:
            timer.stop()
            if is_perf_metrics_enabled():
                logger.debug("[PERF] Stopped shared feedback timer (no active feedback)")
    
    @classmethod
    def _on_shared_feedback_tick(cls) -> None:
        """Process feedback tick for all instances."""
        now = time.monotonic()
        
        # Process each instance
        for instance in list(cls._instances):
            try:
                if not Shiboken.isValid(instance):
                    continue
            except Exception:
                continue
            instance._process_feedback_tick(now)
        
        # Expire old shared events
        expired_ids = []
        for event_id, meta in list(cls._shared_feedback_events.items()):
            duration = meta.get("duration", 0.0) or 0.0
            timestamp = meta.get("timestamp", now)
            if (now - timestamp) >= duration:
                expired_ids.append(event_id)
        for event_id in expired_ids:
            cls._shared_feedback_events.pop(event_id, None)
        
        # Stop timer if no more feedback
        cls._maybe_stop_shared_feedback_timer()
    
    # ------------------------------------------------------------------
    # Instance Feedback Methods
    # ------------------------------------------------------------------
    
    def _process_feedback_tick(self, now: float) -> bool:
        """Process feedback for this instance. Returns True if active."""
        expired_keys: list[str] = []
        for key, deadline in list(self._feedback_deadlines.items()):
            if now >= deadline:
                expired_keys.append(key)

        for key in expired_keys:
            self._feedback_deadlines.pop(key, None)
            self._finalize_feedback_key(key)

        return bool(self._controls_feedback)
    
    def _trigger_controls_feedback(self, key: str, source: str = "manual") -> None:
        """Trigger control feedback animation."""
        if key not in ("prev", "play", "next"):
            logger.debug("[MEDIA_WIDGET][FEEDBACK] Invalid feedback key: %s", key)
            return
        
        logger.debug("[MEDIA_WIDGET][FEEDBACK] Starting feedback animation for %s", key)
        
        cls = type(self)
        now = time.monotonic()
        event_id = f"{key}_{int(now * 1000)}"
        
        # Expire all existing feedback
        self._expire_all_feedback()
        
        # Start new feedback
        self._controls_feedback[key] = (now, event_id)
        self._feedback_deadlines[key] = now + self._controls_feedback_duration
        self._active_feedback_events[key] = event_id
        self._start_feedback_animation(key)
        
        # Register in shared events
        cls._shared_feedback_events[event_id] = {
            "key": key,
            "timestamp": now,
            "source": source,
            "duration": self._controls_feedback_duration,
        }
        
        # Ensure timer is running
        cls._ensure_shared_feedback_timer()
        self._safe_update()
        logger.debug("[MEDIA_WIDGET][FEEDBACK] Feedback animation started for %s", key)

    def _log_feedback_metric(self, *, phase: str, key: str, source: str, event_id: str) -> None:
        """Emit structured logs for control feedback when diagnostics enabled."""
        if not (is_perf_metrics_enabled() or is_verbose_logging()):
            return

        overlay = getattr(self, "_overlay_name", "media")
        message = (
            "[MEDIA_WIDGET][FEEDBACK] overlay=%s phase=%s key=%s source=%s event=%s"
            % (overlay, phase, key, source, event_id)
        )

        if is_perf_metrics_enabled():
            logger.info(message)
        else:
            logger.debug(message)
    
    def _start_feedback_animation(self, key: str) -> None:
        """Start fade animation for feedback."""
        try:
            from core.animation.animator import AnimationManager
            from core.animation.types import EasingCurve
            
            if self._feedback_anim_mgr is None:
                self._feedback_anim_mgr = AnimationManager()
            
            mgr = self._feedback_anim_mgr
            self._controls_feedback_progress[key] = 1.0
            
            def _on_update(progress: float) -> None:
                eased = max(0.0, 1.0 - progress)
                value = eased * eased
                self._controls_feedback_progress[key] = value
                self._safe_update()
            
            def _on_complete() -> None:
                self._finalize_feedback_key(key)
            
            anim_id = mgr.animate_custom(
                duration=max(0.01, self._controls_feedback_duration),
                update_callback=_on_update,
                easing=EasingCurve.CUBIC_OUT,
                on_complete=_on_complete,
            )
            self._controls_feedback_anim_ids[key] = anim_id
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Feedback animation failed: %s", e)
            # Fallback: just set progress and let timer expire it
            self._controls_feedback_progress[key] = 1.0
    
    def _expire_all_feedback(self) -> None:
        """Expire all active feedback."""
        for key in list(self._controls_feedback.keys()):
            self._finalize_feedback_key(key)

    def _finalize_feedback_key(self, key: str) -> None:
        """Clean up feedback for a key."""
        anim_id = self._controls_feedback_anim_ids.pop(key, None)
        if anim_id and self._feedback_anim_mgr:
            try:
                self._feedback_anim_mgr.cancel_animation(anim_id)
            except Exception:
                pass

        self._controls_feedback_progress.pop(key, None)
        entry = self._controls_feedback.pop(key, None)
        if entry:
            _, event_id = entry
            type(self)._shared_feedback_events.pop(event_id, None)

        self._feedback_deadlines.pop(key, None)
        active_id = self._active_feedback_events.pop(key, None)
        if active_id and is_perf_metrics_enabled():
            self._log_feedback_metric(
                phase="expire",
                key=key,
                source="local",
                event_id=active_id,
            )

        # Stop timer if no more feedback
        if not self._controls_feedback and not self._feedback_deadlines:
            type(self)._maybe_stop_shared_feedback_timer()

        self._safe_update()
    
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
