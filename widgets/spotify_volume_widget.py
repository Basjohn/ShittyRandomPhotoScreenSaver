"""Spotify-specific vertical volume widget.

This widget renders a slim vertical volume slider styled to match the
Spotify/media card. It delegates actual volume changes to
:class:`core.media.spotify_volume.SpotifyVolumeController`, which uses
pycaw/Core Audio when available.

The widget itself is non-interactive in Qt hit-testing terms
(``WA_TransparentForMouseEvents``); DisplayWidget is responsible for
routing clicks, drags and wheel events into the public handler methods
so interaction remains gated by Interaction Mode / Ctrl-held modes.
"""
from __future__ import annotations

from typing import Optional

import weakref
import time

from PySide6.QtCore import Qt, QTimer, QPoint, QRect, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QWidget
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_verbose_logging
from core.media.spotify_volume import SpotifyVolumeController
from core.settings.shadow_tuning import VOLUME_SLIDER_SHADOW_TUNING
from core.threading.manager import ThreadManager
from widgets.media.dependent_visibility import sync_anchor_dependent_visibility
from widgets.shadow_utils import ShadowFadeProfile, configure_overlay_widget_attributes, shadow_config_enabled

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

    def __init__(self, parent: Optional[QWidget] = None, provider: str = "spotify") -> None:
        super().__init__(parent)

        self._provider = str(provider or "spotify").strip().lower() or "spotify"
        self._controller = SpotifyVolumeController(provider=provider)
        self._thread_manager: Optional[ThreadManager] = None
        self._shadow_config = None
        self._enabled: bool = False

        self._volume: float = 1.0
        self._dragging: bool = False
        self._pending_volume: Optional[float] = None
        self._flush_timer: Optional[QTimer] = None
        self._has_faded_in: bool = False
        self._anchor_media: Optional[QWidget] = None
        self._last_volume_sync_request_ts: float = 0.0
        self._spotify_secondary_stage_started: bool = False
        self._custom_layout_geometry_reapply_pending: bool = False
        self._painted_frame_shadow_enabled: bool = True
        self._painted_frame_shadow_pixmap: Optional[QPixmap] = None
        self._painted_frame_shadow_cache_key: Optional[tuple] = None
        self._track_shadow_pixmap: Optional[QPixmap] = None
        self._track_shadow_cache_key: Optional[tuple] = None

        try:
            SpotifyVolumeWidget._instances.add(self)
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)

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

    def set_provider_runtime(self, provider: object) -> bool:
        """Retarget the underlying Core Audio session filter without recreating the widget."""

        normalized = str(provider or "spotify").strip().lower() or "spotify"
        if normalized == self._provider:
            return False
        self._provider = normalized
        try:
            self._controller.set_process_filter(normalized)
        except Exception:
            logger.debug("[SPOTIFY_VOL] Failed to retarget provider runtime", exc_info=True)
            return False
        logger.info("[SPOTIFY_VOL] Runtime provider switch applied: %s", normalized)
        self._request_volume_sync(force=True)
        return True

    # ------------------------------------------------------------------
    # Public configuration
    # ------------------------------------------------------------------

    def set_thread_manager(self, thread_manager: Optional[ThreadManager]) -> None:
        self._thread_manager = thread_manager

    def set_shadow_config(self, config) -> None:
        self._shadow_config = config
        self._painted_frame_shadow_enabled = shadow_config_enabled(config, "enabled", True)
        self._invalidate_painted_frame_shadow_cache()
        self.update()

    def set_colors(self, *, track_bg: QColor, track_border: QColor, fill: QColor) -> None:
        """Configure track background, border, and fill colours.

        Called from DisplayWidget using colours derived from the media
        widget's background/border plus an explicit fill colour (typically
        white).
        """

        self._track_bg_color = QColor(track_bg)
        self._track_border_color = QColor(track_border)
        self._fill_color = QColor(fill)

        # Enforce 100% opacity for the border; fill alpha is respected
        # from the user's chosen colour (default [255,255,255,140]).
        try:
            self._track_border_color.setAlpha(255)
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
        try:
            self.update()
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)

    def apply_scale_contract(
        self,
        *,
        width: int,
        height: int,
        track_width: int,
        track_margin: int,
    ) -> None:
        """Apply the authored volume slider scale contract used by CUSTOM resize."""

        next_width = max(24, int(width))
        next_height = max(120, int(height))
        next_track_width = max(10, min(next_width - 8, int(track_width)))
        next_track_margin = max(2, min(24, int(track_margin)))
        custom_rect = self._active_custom_layout_rect()
        if custom_rect is not None:
            next_width = int(custom_rect.width())
            next_height = int(custom_rect.height())

        self._track_width = next_track_width
        self._track_margin = next_track_margin
        self.setMinimumWidth(next_width)
        self.setMinimumHeight(next_height)
        self._invalidate_painted_frame_shadow_cache()
        try:
            self.updateGeometry()
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
        if custom_rect is not None:
            self._schedule_custom_layout_geometry_reapply()
        try:
            self.update()
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)

    def _active_custom_layout_rect(self) -> Optional[QRect]:
        if bool(getattr(self, "_custom_layout_shell_active", False)):
            return None
        custom_rect = getattr(self, "_custom_layout_local_rect", None)
        if not isinstance(custom_rect, QRect):
            return None
        if custom_rect.width() <= 0 or custom_rect.height() <= 0:
            return None
        return QRect(custom_rect)

    def _schedule_custom_layout_geometry_reapply(self) -> None:
        custom_rect = self._active_custom_layout_rect()
        if custom_rect is None:
            return
        if self._custom_layout_geometry_reapply_pending:
            return
        self._custom_layout_geometry_reapply_pending = True

        def _reapply() -> None:
            try:
                try:
                    if Shiboken is not None and not Shiboken.isValid(self):
                        return
                except Exception:
                    return
                try:
                    self.setGeometry(custom_rect)
                except Exception as e:
                    logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
            finally:
                self._custom_layout_geometry_reapply_pending = False

        try:
            ThreadManager.single_shot(0, _reapply)
        except Exception as e:
            self._custom_layout_geometry_reapply_pending = False
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
    
    def set_anchor_media_widget(self, widget: Optional[QWidget]) -> None:
        """Set the anchor media widget for visibility gating."""
        self._anchor_media = widget
        if widget is not None:
            try:
                self.sync_visibility_with_anchor()
            except Exception as e:
                logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
    
    def sync_visibility_with_anchor(self) -> None:
        """Show/hide based on anchor media widget visibility.
        
        Called when the media widget visibility changes to keep the
        volume widget in sync.
        """
        if (
            getattr(self, "_spotify_secondary_stage_registered", False)
            and not self._spotify_secondary_stage_started
        ):
            if (
                self._enabled
                and self._is_anchor_visible()
                and self._is_parent_secondary_stage_ready()
            ):
                self.begin_spotify_secondary_stage()
            return
        if is_verbose_logging():
            logger.debug("[SPOTIFY_VOL] Syncing visibility with anchor")
        was_visible = False
        try:
            was_visible = self.isVisible()
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
        try:
            visible = sync_anchor_dependent_visibility(
                self,
                anchor=self._anchor_media,
                enabled=self._enabled,
                has_faded_in=self._has_faded_in,
                start_fade_in=self._start_widget_fade_in,
                missing_anchor_visible=None,
            )
            if not visible and self._anchor_media is not None and is_verbose_logging():
                logger.debug("[SPOTIFY_VOL] Anchor hidden or widget disabled; volume widget hidden")
            if visible and not was_visible:
                self._request_volume_sync()
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)

    def _is_anchor_visible(self) -> bool:
        anchor = self._anchor_media
        if anchor is None:
            return False
        try:
            return bool(anchor.isVisible())
        except Exception:
            return False

    def _is_parent_secondary_stage_ready(self) -> bool:
        parent = self.parent()
        if parent is None:
            return True
        try:
            overlay_expected = getattr(parent, "_overlay_fade_expected", set()) or set()
        except Exception:
            overlay_expected = set()
        try:
            overlay_started = bool(getattr(parent, "_overlay_fade_started", False))
        except Exception:
            overlay_started = False
        if overlay_expected and not overlay_started:
            return False
        try:
            not_before_ts = float(
                getattr(parent, "_spotify_secondary_not_before_ts", 0.0) or 0.0
            )
        except Exception:
            not_before_ts = 0.0
        if not_before_ts <= 0.0:
            return not overlay_expected
        return time.monotonic() >= not_before_ts

    def begin_spotify_secondary_stage(self) -> None:
        """Join the shared Spotify secondary reveal stage explicitly."""
        if not self._enabled:
            return
        parent = self.parent()
        if parent is not None:
            try:
                if bool(getattr(parent, "_custom_layout_runtime_stabilize_pending", False)):
                    QTimer.singleShot(0, self.begin_spotify_secondary_stage)
                    return
            except Exception as e:
                logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
        anchor = self._anchor_media
        if anchor is not None:
            try:
                if not anchor.isVisible():
                    return
            except Exception as e:
                logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
                return
        self._spotify_secondary_stage_started = True
        if parent is not None and hasattr(parent, "_position_spotify_volume"):
            try:
                parent._position_spotify_volume()
            except Exception as e:
                logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
        self._request_volume_sync(force=True)
        self.sync_visibility_with_anchor()

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
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
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
        self._request_volume_sync(force=True)
        
        logger.debug("[LIFECYCLE] SpotifyVolumeWidget activated")
    
    def _deactivate_impl(self) -> None:
        """Deactivate volume widget (lifecycle hook)."""
        self._reset_flush_state(delete_timer=False)
        logger.debug("[LIFECYCLE] SpotifyVolumeWidget deactivated")
    
    def _cleanup_impl(self) -> None:
        """Clean up volume widget resources (lifecycle hook)."""
        self._deactivate_impl()
        self._reset_flush_state(delete_timer=True)
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
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)

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
            except Exception as e:
                logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
                anchor_visible = True
        
        if not anchor_visible:
            # Media widget not visible - don't show volume widget yet
            if is_verbose_logging():
                logger.debug("[SPOTIFY_VOL] Anchor not visible during start; deferring fade-in")
            return

        # Align visibility with the anchor before we attempt to fade in so any
        # delayed media fade requests have the correct starting state.
        self.sync_visibility_with_anchor()

        self._request_volume_sync(force=True)

        # Participate in coordinated overlay fade sync like other widgets
        def _starter() -> None:
            if not self._enabled:
                return
            self._start_widget_fade_in()

        parent = self.parent()
        if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
            try:
                parent.request_overlay_fade_sync("spotify_volume", _starter)
            except Exception as e:
                logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
                _starter()
        else:
            _starter()

    def stop(self) -> None:
        if not self._enabled:
            return
        self._enabled = False
        self._spotify_secondary_stage_started = False
        self._has_faded_in = False
        self._reset_flush_state(delete_timer=False)
        try:
            self.hide()
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)

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
        self._request_volume_sync()
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

        return self._apply_step_delta(delta_y)

    def handle_step(self, direction: int) -> bool:
        """Adjust volume by one keyboard step using the same wheel contract."""
        if direction == 0:
            return False
        delta_y = 120 if direction > 0 else -120
        return self._apply_step_delta(delta_y)

    def _apply_step_delta(self, delta_y: int) -> bool:
        """Apply a standardized step delta shared by wheel and keyboard paths."""
        step = 0.05
        direction = 1 if delta_y > 0 else -1
        unclamped = self._volume + (step * direction)
        clamped = max(0.0, min(1.0, unclamped))
        self._apply_volume_and_broadcast(clamped)
        self._schedule_set_volume(clamped)
        return True

    # ------------------------------------------------------------------
    # Painted frame shadow
    # ------------------------------------------------------------------

    def uses_outer_frame_shadow(self) -> bool:
        """Return whether the slider should paint a full outer-card shadow.

        The volume widget is visually a single slider track, not a framed card.
        Its track shadow provides the intended depth cue; a second outer-card
        shadow becomes a wide dark box once CUSTOM resize increases the widget
        width. Keep the outer-card path disabled so the resize contract stays
        clean and proportional.
        """

        return False

    def uses_painted_frame_shadow(self) -> bool:
        return bool(self._painted_frame_shadow_enabled)

    def _invalidate_painted_frame_shadow_cache(self) -> None:
        self._painted_frame_shadow_pixmap = None
        self._painted_frame_shadow_cache_key = None
        self._track_shadow_pixmap = None
        self._track_shadow_cache_key = None

    def _painted_frame_shadow_card_rect(self) -> QRectF:
        tuning = VOLUME_SLIDER_SHADOW_TUNING
        return QRectF(
            0.0,
            0.0,
            max(1.0, float(self.width() - int(tuning["card_shrink_right"]))),
            max(1.0, float(self.height() - int(tuning["card_shrink_bottom"]))),
        )

    def _ensure_painted_frame_shadow_pixmap(self) -> Optional[QPixmap]:
        if not self.uses_outer_frame_shadow() or self.width() <= 0 or self.height() <= 0:
            return None
        try:
            dpr = max(1.0, float(self.devicePixelRatioF()))
        except Exception:
            dpr = 1.0
        tuning = VOLUME_SLIDER_SHADOW_TUNING
        key = (
            self.width(),
            self.height(),
            round(dpr, 3),
            tuple(sorted(tuning.items())),
        )
        if (
            self._painted_frame_shadow_pixmap is not None
            and not self._painted_frame_shadow_pixmap.isNull()
            and self._painted_frame_shadow_cache_key == key
        ):
            return self._painted_frame_shadow_pixmap

        pixmap = QPixmap(max(1, int(self.width() * dpr)), max(1, int(self.height() * dpr)))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            card_rect = self._painted_frame_shadow_card_rect().adjusted(1.0, 1.0, -1.0, -1.0)
            radius = max(0.0, float(10 + int(tuning["radius_extra"])))
            offset_x = float(tuning["offset_x"])
            offset_y = float(tuning["offset_y"])
            steps = max(1, int(tuning["blur_steps"]))
            spread = max(0.0, float(tuning["spread"]))
            max_alpha = max(0, min(255, int(tuning["max_alpha"])))

            for layer in range(steps, 0, -1):
                frac = layer / float(steps)
                grow = spread * frac
                alpha = int(max_alpha * (1.0 - (frac * 0.86)))
                if alpha <= 0:
                    continue
                shadow_rect = card_rect.translated(offset_x, offset_y).adjusted(-grow, -grow, grow, grow)
                shadow_path = QPainterPath()
                shadow_path.addRoundedRect(shadow_rect, radius + grow, radius + grow)
                painter.fillPath(shadow_path, QColor(0, 0, 0, alpha))
        finally:
            painter.end()

        self._painted_frame_shadow_pixmap = pixmap
        self._painted_frame_shadow_cache_key = key
        return pixmap

    def _paint_painted_frame_shadow(self) -> None:
        if not self.uses_outer_frame_shadow():
            return
        painter = QPainter(self)
        try:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        finally:
            painter.end()
        pixmap = self._ensure_painted_frame_shadow_pixmap()
        if pixmap is not None and not pixmap.isNull():
            painter = QPainter(self)
            try:
                painter.drawPixmap(0, 0, pixmap)
            finally:
                painter.end()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        self._invalidate_painted_frame_shadow_cache()
        super().resizeEvent(event)

    def _ensure_track_shadow_pixmap(self, track_rect: QRect, radius: float) -> tuple[Optional[QPixmap], int, int]:
        if not self.uses_painted_frame_shadow():
            return None, 0, 0
        if track_rect.width() <= 0 or track_rect.height() <= 0:
            return None, 0, 0
        try:
            dpr = max(1.0, float(self.devicePixelRatioF()))
        except Exception:
            dpr = 1.0
        tuning = VOLUME_SLIDER_SHADOW_TUNING
        offset_x = int(tuning["offset_x"])
        offset_y = int(tuning["offset_y"])
        spread = max(3, int(float(tuning["spread"])))
        alpha = max(0, min(255, int(tuning["max_alpha"]) * 8))
        origin_x = spread + max(0, -offset_x)
        origin_y = spread + max(0, -offset_y)
        shadow_w = track_rect.width() + spread * 2 + abs(offset_x)
        shadow_h = track_rect.height() + spread * 2 + abs(offset_y)
        key = (
            track_rect.width(),
            track_rect.height(),
            round(dpr, 3),
            round(float(radius), 2),
            spread,
            offset_x,
            offset_y,
            alpha,
        )
        if (
            self._track_shadow_pixmap is not None
            and not self._track_shadow_pixmap.isNull()
            and self._track_shadow_cache_key == key
        ):
            return self._track_shadow_pixmap, origin_x, origin_y

        pixmap = QPixmap(max(1, int(shadow_w * dpr)), max(1, int(shadow_h * dpr)))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            base_rect = QRectF(
                origin_x + offset_x,
                origin_y + offset_y,
                track_rect.width(),
                track_rect.height(),
            )
            for layer in range(5, 0, -1):
                frac = layer / 5.0
                grow = spread * frac
                layer_alpha = int(alpha * (1.0 - frac * 0.8))
                if layer_alpha <= 0:
                    continue
                path = QPainterPath()
                path.addRoundedRect(
                    base_rect.adjusted(-grow, -grow, grow, grow),
                    radius + grow,
                    radius + grow,
                )
                painter.fillPath(path, QColor(0, 0, 0, layer_alpha))
        finally:
            painter.end()

        self._track_shadow_pixmap = pixmap
        self._track_shadow_cache_key = key
        return pixmap, origin_x, origin_y

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        if self.uses_outer_frame_shadow():
            self._paint_painted_frame_shadow()
        else:
            super().paintEvent(event)

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)

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

        shadow, origin_x, origin_y = self._ensure_track_shadow_pixmap(track_rect, radius)
        if shadow is not None and not shadow.isNull():
            painter.drawPixmap(track_rect.left() - origin_x, track_rect.top() - origin_y, shadow)

        # Track background and border
        pen = QPen(self._track_border_color)
        try:
            pen.setWidthF(1.5)
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
            pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(self._track_bg_color)
        painter.drawRoundedRect(track_rect, radius, radius)

        # Filled region: volume 1.0 = entire track, and reductions shrink
        # symmetrically from both the top and bottom toward the center so the
        # fill always remains centered vertically.
        vol = max(0.0, min(1.0, float(self._volume)))
        if vol <= 0.0:
            return

        track_height = track_rect.height()
        fill_height = max(2, int(track_height * vol))
        fill_height = min(track_height, fill_height)

        center_y = track_rect.center().y()
        half = fill_height // 2
        fill_top = center_y - half
        fill_bottom = fill_top + fill_height

        # Clamp to track bounds to avoid spilling over rounded corners.
        if fill_top < track_rect.top():
            delta = track_rect.top() - fill_top
            fill_top += delta
            fill_bottom += delta
        if fill_bottom > track_rect.bottom() + 1:
            delta = fill_bottom - (track_rect.bottom() + 1)
            fill_top -= delta
            fill_bottom -= delta

        fill_rect = QRect(
            track_rect.left(),
            fill_top,
            track_rect.width(),
            max(1, fill_bottom - fill_top),
        )

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
        try:
            from core.resources.manager import ResourceManager
            ResourceManager.get_or_create_app_shared().register_qt(
                timer, description="SpotifyVolumeWidget flush debounce timer",
            )
        except Exception:
            pass

    def _request_volume_sync(self, *, force: bool = False) -> None:
        if not self._controller.is_available():
            return
        now = time.monotonic()
        if not force and (now - self._last_volume_sync_request_ts) < 1.25:
            return
        self._last_volume_sync_request_ts = now

        if self._thread_manager is None:
            try:
                current = self._controller.get_volume()
            except Exception:
                logger.debug("[SPOTIFY_VOL] Direct volume sync failed", exc_info=True)
                current = None
            if isinstance(current, float):
                self._apply_volume(current)
            return

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
            except Exception as e:
                logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
                val = None
            ThreadManager.run_on_ui_thread(_apply, val)

        try:
            self._thread_manager.submit_io_task(_do_read, callback=_on_result)
        except Exception:
            logger.debug("[SPOTIFY_VOL] Failed to schedule volume sync", exc_info=True)

    def _reset_flush_state(self, *, delete_timer: bool) -> None:
        """Stop pending flush work and optionally destroy the debounce timer."""
        if self._flush_timer is not None:
            try:
                self._flush_timer.stop()
            except Exception as e:
                logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
            if delete_timer:
                try:
                    self._flush_timer.deleteLater()
                except Exception as e:
                    logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
                self._flush_timer = None
        self._pending_volume = None

    def _apply_volume(self, level: float) -> None:
        if not Shiboken.isValid(self):
            return
        level = float(max(0.0, min(1.0, level)))
        if abs(level - self._volume) < 1e-3:
            return
        self._volume = level
        try:
            self.update()
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)

    def _apply_volume_and_broadcast(self, level: float) -> None:
        """Apply a new volume locally and mirror it to sibling sliders.

        The originating widget is responsible for scheduling the Core Audio
        write; peers only update their visuals to stay in sync.
        """

        self._apply_volume(level)

        cls = self.__class__
        try:
            broadcasting = getattr(cls, "_broadcasting", False)
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
            broadcasting = False
        if broadcasting:
            return

        try:
            cls._broadcasting = True
            try:
                instances = list(getattr(cls, "_instances", []))
            except Exception as e:
                logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
                instances = []
            for other in instances:
                if other is self:
                    continue
                try:
                    other._apply_volume(level)
                except Exception as e:
                    logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
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
            except Exception as e:
                logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)

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

    def _start_widget_fade_in(self, duration_ms: Optional[int] = None) -> None:
        """Fade the widget in using the shared ShadowFadeProfile.

        This mirrors the behaviour of other overlay widgets (media, weather,
        clocks, Reddit, Spotify visualiser) so the volume slider participates in
        the same two-stage card/shadow fade.
        """

        resolved_duration_ms = (
            ShadowFadeProfile.default_duration_ms()
            if duration_ms is None
            else max(0, int(duration_ms))
        )

        if self._has_faded_in and resolved_duration_ms <= 0:
            try:
                self.show()
            except Exception as e:
                logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
            return

        if resolved_duration_ms <= 0:
            try:
                self.show()
            except Exception as e:
                logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
            self._has_faded_in = True
            return

        try:
            ShadowFadeProfile.start_fade_in(
                self,
                self._shadow_config,
                duration_ms=resolved_duration_ms,
                has_background_frame=False,
            )
            self._has_faded_in = True
        except Exception:
            logger.warning(
                "[SPOTIFY_VOL][FALLBACK] Fade-in failed; using direct show",
                exc_info=True,
            )
            try:
                self.show()
            except Exception as e:
                logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
