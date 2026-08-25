"""Spotify-specific vertical volume widget.

This widget renders a slim vertical volume slider styled to match the
Spotify/media card. It delegates accepted state and Core Audio work to the
presentation-neutral Media volume runtime service.

The widget itself is non-interactive in Qt hit-testing terms
(``WA_TransparentForMouseEvents``); DisplayWidget is responsible for
routing clicks, drags and wheel events into the public handler methods
so interaction remains gated by Interaction Mode / Ctrl-held modes.
"""
from __future__ import annotations

from typing import Optional

import time

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_verbose_logging
from core.media.provider_registry import (
    preserve_provider_setting,
    provider_supports_app_volume,
)
from core.threading.manager import ThreadManager
from widgets.media.dependent_visibility import sync_anchor_dependent_visibility
from widgets.media_volume_runtime import (
    MediaVolumeRuntimeService,
    MediaVolumeRuntimeSnapshot,
)
from widgets.shadow_utils import ShadowFadeProfile, configure_overlay_widget_attributes

logger = get_logger(__name__)

class SpotifyVolumeWidget(QWidget):
    """Slim vertical Spotify volume slider.

    This widget is designed to be placed alongside the Spotify media card.
    It exposes handler methods (:meth:`handle_press`, :meth:`handle_drag`,
    :meth:`handle_release`, :meth:`handle_wheel`) which are called from the
    owning :class:`rendering.display_widget.DisplayWidget` when
    interaction mode is active.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        provider: str = "spotify",
        *,
        build_default_runtime: bool = True,
    ) -> None:
        super().__init__(parent)

        self._provider = preserve_provider_setting(provider)
        self._provider_volume_supported = provider_supports_app_volume(self._provider)
        self._browser_volume_process: Optional[str] = None
        self._runtime_available: bool = False
        self._thread_manager: Optional[ThreadManager] = None
        self._runtime_service: MediaVolumeRuntimeService | None = None
        self._owns_runtime_service = False
        self._shadow_config = None
        self._enabled: bool = False

        self._volume: float = 1.0
        self._dragging: bool = False
        self._has_faded_in: bool = False
        self._anchor_media: Optional[QWidget] = None
        self._spotify_secondary_stage_started: bool = False
        self._custom_layout_geometry_reapply_pending: bool = False

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

        if build_default_runtime:
            service = MediaVolumeRuntimeService(provider=self._provider, shared=False)
            self._install_runtime_service(service, owns_service=True)

    def set_provider_runtime(self, provider: object) -> bool:
        """Retarget the underlying Core Audio session filter without recreating the widget."""

        service = self._runtime_service
        if service is None:
            return False
        changed = bool(service.set_provider_runtime(provider))
        if not changed:
            return False
        self._sync_runtime_snapshot()
        if not self._provider_volume_supported or not self._runtime_available:
            self.hide()
            logger.info(
                "[SPOTIFY_VOL] Volume target unavailable for provider=%s; widget hidden",
                self._provider,
            )
            return True
        logger.info("[SPOTIFY_VOL] Runtime provider switch applied: %s", self._provider)
        if self._enabled:
            self.sync_visibility_with_anchor()
        return True

    def set_runtime_volume_source(
        self,
        provider: object,
        source_app_user_model_id: object,
    ) -> bool:
        """Apply the generation-accepted GSMTC host as a runtime-only target."""

        service = self._runtime_service
        if service is None:
            return False
        changed = bool(
            service.set_runtime_volume_source(provider, source_app_user_model_id)
        )
        if not changed:
            return False
        self._sync_runtime_snapshot()
        if not self._provider_volume_supported or not self._runtime_available:
            self.hide()
            logger.debug(
                "[SPOTIFY_VOL] Browser volume disabled; no exact accepted GSMTC host"
            )
            return True

        logger.info(
            "[SPOTIFY_VOL] Browser volume target accepted: spotify.exe -> %s fallback",
            self._browser_volume_process,
        )
        if self._enabled:
            self.sync_visibility_with_anchor()
        return True

    # ------------------------------------------------------------------
    # Public configuration
    # ------------------------------------------------------------------

    def set_thread_manager(self, thread_manager: Optional[ThreadManager]) -> None:
        self._thread_manager = thread_manager
        service = self._runtime_service
        if service is not None:
            service.set_thread_manager(thread_manager)

    def set_runtime_service(self, service: MediaVolumeRuntimeService) -> None:
        """Attach the registry-owned neutral service before presentation start."""

        self._install_runtime_service(service, owns_service=False)

    def _install_runtime_service(
        self,
        service: MediaVolumeRuntimeService,
        *,
        owns_service: bool,
    ) -> None:
        if service is self._runtime_service:
            return
        prior = self._runtime_service
        prior_owned = self._owns_runtime_service
        if prior is not None:
            prior.stop()
            prior.detach_consumer(self)
            if prior_owned:
                prior.retire()
        self._runtime_service = service
        self._owns_runtime_service = bool(owns_service)
        if self._thread_manager is not None:
            service.set_thread_manager(self._thread_manager)
        service.attach_consumer(self)
        self._sync_runtime_snapshot()

    def _sync_runtime_snapshot(self) -> None:
        service = self._runtime_service
        snapshot = service.current_snapshot() if service is not None else None
        if snapshot is not None:
            self._apply_runtime_snapshot(snapshot)

    def is_media_volume_consumer_alive(self) -> bool:
        try:
            return bool(Shiboken.isValid(self))
        except Exception:
            return False

    def on_media_volume_runtime_snapshot(
        self, snapshot: MediaVolumeRuntimeSnapshot
    ) -> None:
        self._apply_runtime_snapshot(snapshot)

    def _apply_runtime_snapshot(self, snapshot: MediaVolumeRuntimeSnapshot) -> None:
        self._provider = snapshot.provider
        self._browser_volume_process = snapshot.browser_process
        self._provider_volume_supported = bool(snapshot.supported)
        self._runtime_available = bool(snapshot.available)
        self._apply_volume(snapshot.level)
        if not self._provider_volume_supported or not self._runtime_available:
            try:
                self.hide()
            except Exception:
                pass

    def is_lifecycle_active(self) -> bool:
        return bool(self._enabled)

    def set_shadow_config(self, config) -> None:
        self._shadow_config = config
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

        _reapply._srpss_runtime_generation = getattr(
            self,
            "_runtime_generation",
            getattr(self.parent(), "_runtime_generation", None),
        )

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
                and self._provider_volume_supported
                and self._runtime_available
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
                enabled=(
                    self._enabled
                    and self._provider_volume_supported
                    and self._runtime_available
                ),
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
        if (
            not self._enabled
            or not self._provider_volume_supported
            or not self._runtime_available
        ):
            return
        parent = self.parent()
        if parent is not None:
            try:
                if bool(getattr(parent, "_custom_layout_runtime_stabilize_pending", False)):
                    ThreadManager.single_shot(0, self.begin_spotify_secondary_stage)
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
        self.start()
        logger.debug("[LIFECYCLE] SpotifyVolumeWidget activated")
    
    def _deactivate_impl(self) -> None:
        """Deactivate volume widget (lifecycle hook)."""
        self.stop()
        logger.debug("[LIFECYCLE] SpotifyVolumeWidget deactivated")
    
    def _cleanup_impl(self) -> None:
        """Clean up volume widget resources (lifecycle hook)."""
        self.cleanup()
        logger.debug("[LIFECYCLE] SpotifyVolumeWidget cleaned up")

    # ------------------------------------------------------------------
    # Legacy Lifecycle Methods (for backward compatibility)
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Activate the neutral volume lease and begin local presentation."""

        if self._enabled:
            return True
        service = self._runtime_service
        if service is None:
            logger.error(
                "[SPOTIFY_VOL] Missing required runtime service; activation failed closed"
            )
            return False
        self._enabled = True
        if not service.start():
            self._enabled = False
            logger.error("[SPOTIFY_VOL] Runtime service start failed closed")
            return False
        self._sync_runtime_snapshot()

        try:
            self.hide()
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)

        if not self._provider_volume_supported or not self._runtime_available:
            if is_verbose_logging():
                logger.info("[SPOTIFY_VOL] Controller unavailable; widget will remain hidden")
            return True

        # Only show if anchor media widget is visible (Spotify is active).
        anchor = self._anchor_media
        anchor_visible = True
        if anchor is not None:
            try:
                anchor_visible = anchor.isVisible()
            except Exception as e:
                logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)
                anchor_visible = True

        if not anchor_visible:
            if is_verbose_logging():
                logger.debug("[SPOTIFY_VOL] Anchor not visible during start; deferring fade-in")
            return True

        self.sync_visibility_with_anchor()

        def _starter() -> None:
            if (
                not self._enabled
                or not self._provider_volume_supported
                or not self._runtime_available
            ):
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
        return True

    def stop(self) -> None:
        if not self._enabled:
            return
        self._enabled = False
        self._spotify_secondary_stage_started = False
        self._has_faded_in = False
        service = self._runtime_service
        if service is not None:
            service.stop()
        try:
            self.hide()
        except Exception as e:
            logger.debug("[SPOTIFY_VOL] Exception suppressed: %s", e)

    def cleanup(self) -> None:
        self.stop()
        service = self._runtime_service
        owns_service = self._owns_runtime_service
        if service is not None:
            service.detach_consumer(self)
            if owns_service:
                service.retire()
        self._runtime_service = None
        self._owns_runtime_service = False

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
        self._set_runtime_volume(clamped)
        return True

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
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

    def _request_volume_sync(self, *, force: bool = False) -> None:
        service = self._runtime_service
        if service is not None:
            service.request_sync(force=force)

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
        self._set_runtime_volume(ratio)

    def _set_runtime_volume(self, level: float) -> None:
        clamped = float(max(0.0, min(1.0, level)))
        service = self._runtime_service
        if service is not None and service.set_volume_optimistic(clamped):
            return
        # Preserve local standalone/input feedback if the optional Core Audio
        # backend is unavailable. Production wiring still fails closed before a
        # service-less presenter can be registered or started.
        self._apply_volume(clamped)

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
