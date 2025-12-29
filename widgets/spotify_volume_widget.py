"""Spotify-specific vertical volume widget.

This widget renders a slim vertical volume slider styled to match the
Spotify/media card. It delegates actual volume changes to
:class:`core.media.spotify_volume.SpotifyVolumeController`, which uses
pycaw/Core Audio when available.

The widget itself is non-interactive in Qt hit-testing terms
(``WA_TransparentForMouseEvents``); DisplayWidget is responsible for
routing clicks, drags and wheel events into the public handler methods
so interaction remains gated by hard-exit / Ctrl-held modes.
"""
from __future__ import annotations

from typing import Optional

import weakref

from PySide6.QtCore import Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger, is_verbose_logging
from core.media.spotify_volume import SpotifyVolumeController
from core.threading.manager import ThreadManager
from widgets.shadow_utils import apply_widget_shadow, ShadowFadeProfile, configure_overlay_widget_attributes

logger = get_logger(__name__)


class SpotifyVolumeWidget(QWidget):
    """Slim vertical Spotify volume slider.

    This widget is designed to be placed alongside the Spotify media card.
    It exposes handler methods (:meth:`handle_press`, :meth:`handle_drag`,
    :meth:`handle_release`, :meth:`handle_wheel`) which are called from the
    owning :class:`rendering.display_widget.DisplayWidget` when
    interaction mode is active.
    """

    _instances = weakref.WeakSet()
    _broadcasting: bool = False

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._controller = SpotifyVolumeController()
        self._thread_manager: Optional[ThreadManager] = None
        self._shadow_config = None
        self._enabled: bool = False

        self._volume: float = 1.0
        self._dragging: bool = False
        self._pending_volume: Optional[float] = None
        self._flush_timer: Optional[QTimer] = None
        self._has_faded_in: bool = False
        self._anchor_media: Optional[QWidget] = None

        try:
            SpotifyVolumeWidget._instances.add(self)
        except Exception:
            pass

        # Geometry constants (logical pixels)
        self._track_margin: int = 6
        self._track_width: int = 18

        # Visual styling; these are configured from the parent media widget so
        # the slider inherits the Spotify card's look while keeping an
        # independent fill colour.
        self._track_bg_color: QColor = QColor(200, 200, 200, 90)
        self._track_border_color: QColor = QColor(255, 255, 255, 230)
        self._fill_color: QColor = QColor(255, 255, 255, 230)

        self._setup_ui()

    # ------------------------------------------------------------------
    # Public configuration
    # ------------------------------------------------------------------

    def set_thread_manager(self, thread_manager: Optional[ThreadManager]) -> None:
        self._thread_manager = thread_manager

    def set_shadow_config(self, config) -> None:
        self._shadow_config = config
        try:
            apply_widget_shadow(self, config, has_background_frame=False)
        except Exception:
            logger.debug("[SPOTIFY_VOL] Failed to apply widget shadow", exc_info=True)

    def set_colors(self, *, track_bg: QColor, track_border: QColor, fill: QColor) -> None:
        """Configure track background, border, and fill colours.

        Called from DisplayWidget using colours derived from the media
        widget's background/border plus an explicit fill colour (typically
        white).
        """

        self._track_bg_color = QColor(track_bg)
        self._track_border_color = QColor(track_border)
        self._fill_color = QColor(fill)

        # Enforce 100% opacity for the border and a slightly translucent
        # (~55%) fill, regardless of the incoming colours.
        try:
            self._track_border_color.setAlpha(255)
            fill_alpha = int(0.55 * 255)
            self._fill_color.setAlpha(fill_alpha)
        except Exception:
            pass
        try:
            self.update()
        except Exception:
            pass
    
    def set_anchor_media_widget(self, widget: Optional[QWidget]) -> None:
        """Set the anchor media widget for visibility gating."""
        self._anchor_media = widget
    
    def sync_visibility_with_anchor(self) -> None:
        """Show/hide based on anchor media widget visibility.
        
        Called when the media widget visibility changes to keep the
        volume widget in sync.
        """
        anchor = self._anchor_media
        if anchor is None:
            return
        
        try:
            anchor_visible = anchor.isVisible()
            if anchor_visible and not self.isVisible() and self._enabled:
                # Media widget became visible - show volume widget
                self._start_widget_fade_in(1500)
            elif not anchor_visible and self.isVisible():
                # Media widget hidden - hide volume widget
                self.hide()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        # Configure attributes to prevent flicker with GL compositor
        configure_overlay_widget_attributes(self)
        
        self.setMinimumWidth(32)
        self.setMinimumHeight(180)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        except Exception:
            pass
        self.hide()

    # ------------------------------------------------------------------
    # Lifecycle Implementation Hooks
    # ------------------------------------------------------------------
    
    def _initialize_impl(self) -> None:
        """Initialize volume widget resources (lifecycle hook)."""
        logger.debug("[LIFECYCLE] SpotifyVolumeWidget initialized")
    
    def _activate_impl(self) -> None:
        """Activate volume widget (lifecycle hook)."""
        if not self._controller.is_available():
            logger.debug("[LIFECYCLE] SpotifyVolumeWidget controller unavailable")
            return
        
        self._ensure_flush_timer()
        
        # Read initial volume
        if self._thread_manager is not None:
            def _do_read():
                return self._controller.get_volume()
            
            def _on_result(result):
                val = None
                try:
                    if getattr(result, "success", False):
                        val = getattr(result, "result", None)
                except Exception:
                    pass
                if isinstance(val, float):
                    ThreadManager.run_on_ui_thread(self._apply_volume, val)
            
            try:
                self._thread_manager.submit_io_task(_do_read, callback=_on_result)
            except Exception:
                pass
        else:
            try:
                current = self._controller.get_volume()
                if isinstance(current, float):
                    self._apply_volume(current)
            except Exception:
                pass
        
        logger.debug("[LIFECYCLE] SpotifyVolumeWidget activated")
    
    def _deactivate_impl(self) -> None:
        """Deactivate volume widget (lifecycle hook)."""
        if self._flush_timer is not None:
            try:
                self._flush_timer.stop()
            except Exception:
                pass
        self._pending_volume = None
        logger.debug("[LIFECYCLE] SpotifyVolumeWidget deactivated")
    
    def _cleanup_impl(self) -> None:
        """Clean up volume widget resources (lifecycle hook)."""
        self._deactivate_impl()
        if self._flush_timer is not None:
            try:
                self._flush_timer.deleteLater()
            except Exception:
                pass
            self._flush_timer = None
        logger.debug("[LIFECYCLE] SpotifyVolumeWidget cleaned up")

    # ------------------------------------------------------------------
    # Legacy Lifecycle Methods (for backward compatibility)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialise volume from the controller when available."""

        if self._enabled:
            return
        self._enabled = True

        try:
            self.hide()
        except Exception:
            pass

        if not self._controller.is_available():
            if is_verbose_logging():
                logger.info("[SPOTIFY_VOL] Controller unavailable; widget will remain hidden")
            return

        self._ensure_flush_timer()
        
        # Only show if anchor media widget is visible (Spotify is active)
        anchor = self._anchor_media
        anchor_visible = True
        if anchor is not None:
            try:
                anchor_visible = anchor.isVisible()
            except Exception:
                anchor_visible = True
        
        if not anchor_visible:
            # Media widget not visible - don't show volume widget yet
            return

        if self._thread_manager is None:
            try:
                current = self._controller.get_volume()
            except Exception:
                current = None
            if isinstance(current, float):
                self._apply_volume(current)
        else:
            def _do_read() -> Optional[float]:
                return self._controller.get_volume()

            def _on_result(result) -> None:
                def _apply(val: Optional[float]) -> None:
                    if isinstance(val, float):
                        self._apply_volume(val)

                val: Optional[float] = None
                try:
                    if getattr(result, "success", False):
                        val = getattr(result, "result", None)
                except Exception:
                    val = None
                ThreadManager.run_on_ui_thread(_apply, val)

            try:
                self._thread_manager.submit_io_task(_do_read, callback=_on_result)
            except Exception:
                logger.debug("[SPOTIFY_VOL] Failed to schedule initial volume read", exc_info=True)

        # Participate in coordinated overlay fade sync like other widgets
        def _starter() -> None:
            if not self._enabled:
                return
            self._start_widget_fade_in(1500)

        parent = self.parent()
        if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
            try:
                parent.request_overlay_fade_sync("spotify_volume", _starter)
            except Exception:
                _starter()
        else:
            _starter()

    def stop(self) -> None:
        if not self._enabled:
            return
        self._enabled = False
        try:
            if self._flush_timer is not None:
                self._flush_timer.stop()
        except Exception:
            pass
        self._pending_volume = None
        try:
            self.hide()
        except Exception:
            pass

    def cleanup(self) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Interaction handlers (called from DisplayWidget)
    # ------------------------------------------------------------------

    def handle_press(self, local_pos: QPoint, button: Qt.MouseButton) -> bool:
        if button != Qt.MouseButton.LeftButton:
            return False
        if not self.isVisible():
            return False
        self._dragging = True
        self._set_volume_from_pos(local_pos)
        return True

    def handle_drag(self, local_pos: QPoint) -> bool:
        if not self._dragging:
            return False
        if not self.isVisible():
            return False
        self._set_volume_from_pos(local_pos)
        return True

    def handle_release(self) -> None:
        """End drag interaction."""
        self._dragging = False

    def handle_wheel(self, local_pos: QPoint, delta_y: int) -> bool:
        """Adjust volume from a wheel delta routed by DisplayWidget."""
        if not self.isVisible():
            return False

        if delta_y == 0:
            return False

        step = 0.05
        direction = 1 if delta_y > 0 else -1
        unclamped = self._volume + (step * direction)
        clamped = max(0.0, min(1.0, unclamped))
        self._apply_volume_and_broadcast(clamped)
        self._schedule_set_volume(clamped)
        return True

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        super().paintEvent(event)

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        except Exception:
            pass

        rect = self.rect().adjusted(
            self._track_margin,
            self._track_margin,
            -self._track_margin,
            -self._track_margin,
        )
        if rect.width() <= 0 or rect.height() <= 0:
            return

        cx = rect.center().x()
        track_half = max(4, int(self._track_width / 2))
        track_rect = QRect(cx - track_half, rect.top(), track_half * 2, rect.height())
        radius = float(track_half)

        # Track background and border
        pen = QPen(self._track_border_color)
        try:
            pen.setWidthF(1.5)
        except Exception:
            pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(self._track_bg_color)
        painter.drawRoundedRect(track_rect, radius, radius)

        # Filled region: volume 0.0 at bottom, 1.0 at top. The filled area
        # grows upwards from the bottom of the track rather than acting as a
        # small thumb, matching the mockup.
        vol = max(0.0, min(1.0, float(self._volume)))
        if vol <= 0.0:
            return

        fill_height = max(2, int(track_rect.height() * vol))
        fill_top = track_rect.bottom() - fill_height + 1
        fill_rect = QRect(track_rect.left(), fill_top, track_rect.width(), fill_height)

        painter.setBrush(self._fill_color)
        painter.drawRoundedRect(fill_rect, radius, radius)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_flush_timer(self) -> None:
        if self._flush_timer is not None:
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(80)

        def _on_timeout() -> None:
            level = self._pending_volume
            self._pending_volume = None
            if level is None:
                return
            self._submit_volume_set(level)

        timer.timeout.connect(_on_timeout)
        self._flush_timer = timer

    def _apply_volume(self, level: float) -> None:
        level = float(max(0.0, min(1.0, level)))
        if abs(level - self._volume) < 1e-3:
            return
        self._volume = level
        try:
            self.update()
        except Exception:
            pass

    def _apply_volume_and_broadcast(self, level: float) -> None:
        """Apply a new volume locally and mirror it to sibling sliders.

        The originating widget is responsible for scheduling the Core Audio
        write; peers only update their visuals to stay in sync.
        """

        self._apply_volume(level)

        cls = self.__class__
        try:
            broadcasting = getattr(cls, "_broadcasting", False)
        except Exception:
            broadcasting = False
        if broadcasting:
            return

        try:
            cls._broadcasting = True
            try:
                instances = list(getattr(cls, "_instances", []))
            except Exception:
                instances = []
            for other in instances:
                if other is self:
                    continue
                try:
                    other._apply_volume(level)
                except Exception:
                    continue
        finally:
            cls._broadcasting = False

    def _set_volume_from_pos(self, local_pos: QPoint) -> None:
        rect = self.rect().adjusted(
            self._track_margin,
            self._track_margin,
            -self._track_margin,
            -self._track_margin,
        )
        if rect.height() <= 0:
            return

        y = max(rect.top(), min(rect.bottom(), local_pos.y()))
        # 0.0 at bottom, 1.0 at top
        ratio = 0.0
        if rect.height() > 0:
            ratio = float(rect.bottom() - y) / float(rect.height())
        self._apply_volume_and_broadcast(ratio)
        self._schedule_set_volume(ratio)

    def _schedule_set_volume(self, level: float) -> None:
        self._pending_volume = float(max(0.0, min(1.0, level)))
        self._ensure_flush_timer()
        if self._flush_timer is not None:
            try:
                self._flush_timer.start()
            except Exception:
                pass

    def _submit_volume_set(self, level: float) -> None:
        if not self._controller.is_available():
            logger.debug("[SPOTIFY_VOL] Controller not available, cannot set volume")
            return

        clamped = float(max(0.0, min(1.0, level)))

        if self._thread_manager is None:
            try:
                result = self._controller.set_volume(clamped)
                if is_verbose_logging():
                    logger.debug("[SPOTIFY_VOL] set_volume direct: %.2f -> %s", clamped, result)
            except Exception:
                logger.debug("[SPOTIFY_VOL] set_volume direct call failed", exc_info=True)
            return

        def _do_set(target: float) -> None:
            try:
                result = self._controller.set_volume(target)
                if is_verbose_logging():
                    logger.debug("[SPOTIFY_VOL] set_volume async: %.2f -> %s", target, result)
            except Exception:
                logger.debug("[SPOTIFY_VOL] set_volume task failed", exc_info=True)

        try:
            self._thread_manager.submit_io_task(_do_set, clamped)
        except Exception:
            logger.debug("[SPOTIFY_VOL] Failed to submit set_volume task", exc_info=True)

    def _start_widget_fade_in(self, duration_ms: int = 1500) -> None:
        """Fade the widget in using the shared ShadowFadeProfile.

        This mirrors the behaviour of other overlay widgets (media, weather,
        clocks, Reddit, Spotify visualiser) so the volume slider participates in
        the same two-stage card/shadow fade.
        """

        if self._has_faded_in and duration_ms <= 0:
            try:
                self.show()
            except Exception:
                pass
            return

        if duration_ms <= 0:
            try:
                self.show()
            except Exception:
                pass
            if self._shadow_config is not None:
                try:
                    apply_widget_shadow(self, self._shadow_config, has_background_frame=False)
                except Exception:
                    logger.debug("[SPOTIFY_VOL] Failed to attach shadow in no-fade path", exc_info=True)
            self._has_faded_in = True
            return

        try:
            ShadowFadeProfile.start_fade_in(
                self,
                self._shadow_config,
                has_background_frame=False,
            )
            self._has_faded_in = True
        except Exception:
            logger.debug("[SPOTIFY_VOL] _start_widget_fade_in fallback path triggered", exc_info=True)
            try:
                self.show()
            except Exception:
                pass
            if self._shadow_config is not None:
                try:
                    apply_widget_shadow(self, self._shadow_config, has_background_frame=False)
                except Exception:
                    logger.debug("[SPOTIFY_VOL] Failed to apply widget shadow in fallback path", exc_info=True)
