"""Temporary QWidget anchor for Phase-F4 Media controls.

This QWidget presents the accepted state from a neutral Media runtime lease.
Controller/provider lifetime, polling, shared playback state and source artwork
decode live outside the presenter. Retained Quick owns the Media core pixels;
this class temporarily owns controls, progress, input feedback and their anchor
geometry until Phase F4 retires them.

Transport controls (play/pause, previous/next) are exposed but are
strictly gated behind explicit user intent (Ctrl-held or Interaction Mode
interaction modes) as routed by DisplayWidget; normal screensaver
mode remains non-interactive.
"""
from __future__ import annotations

import time
import weakref
from dataclasses import asdict
from enum import Enum
from typing import Optional, TYPE_CHECKING, ClassVar

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Qt, Signal, QPoint
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
)
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from core.performance import widget_paint_sample
from core.media.media_controller import (
    BaseMediaController,
    MediaTrackInfo,
)
from core.media.provider_registry import (
    normalize_provider_id,
    preserve_provider_setting,
)
from core.threading.manager import ThreadManager
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.media_runtime import (
    MediaRuntimeService,
    MediaRuntimeSnapshot,
)
from widgets.shadow_utils import ShadowFadeProfile

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
    - Projects accepted playback state into temporary F4 controls/progress state
    - Delegates transport commands to the shared runtime owner
    - Remains non-interactive unless the existing interaction gate admits input
    """

    media_updated = Signal(dict)  # Emits dict(MediaTrackInfo) when refreshed
    
    # Override defaults for media widget
    DEFAULT_FONT_SIZE = 20
    # Class-level shared state for feedback synchronization
    _instances: ClassVar[weakref.WeakSet] = weakref.WeakSet()
    _shared_feedback_events: ClassVar[dict] = {}
    _shared_feedback_timer: ClassVar[Optional[QTimer]] = None
    # AnimationManager owns smooth feedback frames.  This timer is only the
    # deadline/fallback sweeper, so it must not add a second 60 Hz GUI stream.
    _shared_feedback_timer_interval_ms: ClassVar[int] = 100
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        position: MediaPosition = MediaPosition.BOTTOM_LEFT,
        controller: Optional[BaseMediaController] = None,
        thread_manager: Optional[ThreadManager] = None,
        provider: str = "spotify",
        build_default_runtime: bool = True,
    ) -> None:
        # Convert MediaPosition to OverlayPosition for base class
        overlay_pos = OverlayPosition(position.value)
        super().__init__(parent, position=overlay_pos, overlay_name="media")
        
        # Defer visibility until fade sync triggers
        self._defer_visibility_for_fade_sync = True

        self._media_position = position  # Keep original enum for compatibility
        
        # Registered provider id drives GSMTC session ownership and branding.
        self._provider: str = self._validate_provider(provider)
        self._perf_media_emit_count: int = 0
        self._perf_media_emit_total: int = 0
        self._perf_media_update_request_total: int = 0
        self._perf_media_display_total: int = 0
        self._perf_media_last_log_ts: float = time.monotonic()

        self._runtime_service: Optional[MediaRuntimeService] = None
        self._standalone_runtime_service: Optional[MediaRuntimeService] = None
        self._last_runtime_revision: int = 0
        self._pending_runtime_thread_manager: Optional[ThreadManager] = None
        if thread_manager is not None:
            self.set_thread_manager(thread_manager)
        if controller is not None and not build_default_runtime:
            raise ValueError("controller injection requires standalone Media runtime ownership")

        self._widget_manager: Optional["WidgetManager"] = None
        self._pending_keyboard_alias_command: Optional[tuple[str, float]] = None
        self._pending_keyboard_alias_timer: Optional[QTimer] = None
        self._last_external_transport_feedback: Optional[tuple[str, float]] = None

        # Override base class font size default
        self._font_size = 20

        # Temporary anchor geometry still follows the Media artwork-size setting
        # so F4 controls and CUSTOM editing share the retained card footprint.
        self._artwork_size: int = 200

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
        self._context_menu_active: bool = False
        self._context_menu_prewarmed: bool = False
        self._pending_effect_invalidation: bool = False

        # Central ResourceManager wiring
        self._last_info: Optional[MediaTrackInfo] = None
        
        # Smart polling: diff gating to skip unnecessary updates
        self._last_track_identity: Optional[tuple] = None
        
        # Established anchor height used when F4 controls/progress reserve space.
        self._fixed_card_height: Optional[int] = None

        # First accepted state is published before the temporary F4 anchor's
        # coordinated reveal.
        self._has_seen_first_track: bool = False
        self._fade_in_completed: bool = False

        self._telemetry_last_visibility: Optional[bool] = None
        
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

        # Register this instance for shared feedback
        type(self)._instances.add(self)

        self._setup_ui()

        if build_default_runtime:
            standalone_service = MediaRuntimeService(
                provider=self._provider,
                shared=False,
                controller=controller,
                runtime_generation=getattr(self, "_runtime_generation", None),
            )
            self._standalone_runtime_service = standalone_service
            self.set_runtime_service(standalone_service)

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

    def get_retained_display_info(self) -> Optional[MediaTrackInfo]:
        """Transitional presenter read of the shared owner's accepted snapshot."""

        service = self._runtime_service
        if service is not None:
            return service.current_info()
        return self._last_info

    def current_media_info(self) -> Optional[MediaTrackInfo]:
        """Return the accepted neutral snapshot for presenter/Visualizer seeding."""

        return self.get_retained_display_info()

    def set_runtime_service(self, service: MediaRuntimeService) -> None:
        """Attach this presenter to its per-display neutral Media lease."""

        if service is None:
            raise ValueError("Media runtime service is required")
        current = self._runtime_service
        if current is service:
            thread_manager = self._thread_manager or self._pending_runtime_thread_manager
            if thread_manager is not None:
                service.set_thread_manager(thread_manager)
            return

        was_running = bool(self._enabled)
        if current is not None:
            current.stop()
            current.detach_consumer(self)
            if current is self._standalone_runtime_service:
                current.retire()
                self._standalone_runtime_service = None

        self._runtime_service = service
        self._last_runtime_revision = 0
        thread_manager = self._thread_manager or self._pending_runtime_thread_manager
        if thread_manager is not None:
            service.set_thread_manager(thread_manager)
        try:
            service.attach_consumer(self)
        except Exception:
            self._runtime_service = None
            raise
        self._provider = self._validate_provider(service.provider)
        if was_running and not service.start():
            raise RuntimeError("Media runtime service could not resume active presenter")

    def is_media_consumer_alive(self) -> bool:
        """Return whether service delivery may still target this presenter."""

        try:
            if not Shiboken.isValid(self):
                return False
        except Exception:
            return False
        return getattr(getattr(self, "_lifecycle_state", None), "name", "") != "DESTROYED"

    def on_media_runtime_snapshot(self, snapshot: MediaRuntimeSnapshot) -> None:
        """Project one shared neutral snapshot into this display's QWidget state."""

        if not isinstance(snapshot, MediaRuntimeSnapshot) or not self.is_media_consumer_alive():
            return
        revision = int(snapshot.revision)
        if revision < self._last_runtime_revision:
            return
        if snapshot.provider != self._provider:
            self.on_media_runtime_provider_changed(
                self._provider,
                snapshot.provider,
                source="runtime_replay",
                persist=False,
            )
        self._last_runtime_revision = revision
        self._update_display(snapshot.info)

    def on_media_runtime_provider_changed(
        self,
        old_provider: str,
        provider: str,
        *,
        source: str,
        persist: bool,
    ) -> None:
        """Reset only presenter caches after the neutral owner changes provider."""

        normalized = self._validate_provider(provider)
        self._provider = normalized
        self._last_runtime_revision = 0
        self._last_info = None
        self._last_track_identity = None
        self._safe_update()
        if persist:
            manager = self._widget_manager
            if manager is not None and hasattr(manager, "handle_media_provider_failover"):
                try:
                    manager.handle_media_provider_failover(normalized, source=source)
                except Exception:
                    logger.debug(
                        "[MEDIA_WIDGET] Failed to persist provider failover",
                        exc_info=True,
                    )
        logger.info(
            "[MEDIA_WIDGET] Presenter provider projection: %s -> %s (source=%s)",
            old_provider,
            normalized,
            source,
        )

    def on_media_runtime_volume_target(self, provider: str, source_id: str) -> None:
        """Forward the accepted target to this display's existing volume presenter."""

        manager = self._widget_manager
        if manager is None or not hasattr(manager, "sync_media_volume_runtime_target"):
            return
        try:
            manager.sync_media_volume_runtime_target(provider, source_id)
        except Exception:
            logger.debug(
                "[MEDIA_WIDGET] Failed to sync accepted volume target",
                exc_info=True,
            )

    def set_provider_runtime(self, provider: object) -> bool:
        """Transitional UI entry point; provider ownership remains in the service."""

        normalized = self._validate_provider(provider)
        service = self._runtime_service
        if service is None:
            changed = normalized != self._provider
            self._provider = normalized
            return changed
        changed = service.set_provider_runtime(normalized, source="settings")
        runtime_provider = getattr(service, "provider", normalized)
        running_getter = getattr(service, "is_running", None)
        service_running = bool(running_getter()) if callable(running_getter) else False
        if runtime_provider != self._provider and not service_running:
            self.on_media_runtime_provider_changed(
                self._provider,
                runtime_provider,
                source="settings",
                persist=False,
            )
        return changed

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        # Use base class styling setup
        self._apply_base_styling()
        
        # Keep the temporary control surface aligned with the retained card.
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        try:
            # Non-interactive by default; screensaver interaction is gated elsewhere.
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)
        self.setWordWrap(True)

        # Base margins shared by the temporary controls/progress surface.
        self.setContentsMargins(29, 12, 12, 12)

        # Preserve the configured Media card footprint for F4/CUSTOM geometry.
        self.setMinimumWidth(BaseOverlayWidget.DEFAULT_CARD_MIN_WIDTH)
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
        """Activate this presenter lease; the shared owner starts on first use."""
        invalidate = getattr(self, "_invalidate_controls_layout", None)
        if callable(invalidate):
            invalidate()
        if not self._ensure_thread_manager("MediaWidget._activate_impl"):
            raise RuntimeError("Media presenter activation requires ThreadManager")
        service = self._runtime_service
        if service is not None and service.provider != self._provider:
            self.on_media_runtime_provider_changed(
                self._provider,
                service.provider,
                source="runtime_reactivate",
                persist=False,
            )
        if service is None or not service.start():
            raise RuntimeError("Media presenter has no startable runtime service")
        logger.debug("[LIFECYCLE] MediaWidget activated")
    
    def _deactivate_impl(self) -> None:
        """Release this active lease without disturbing other displays."""
        service = self._runtime_service
        if service is not None:
            service.stop()
        self._clear_pending_keyboard_alias_timer()
        self._pending_keyboard_alias_command = None
        logger.debug("[LIFECYCLE] MediaWidget deactivated")
    
    def _cleanup_impl(self) -> None:
        """Clean up media resources (lifecycle hook)."""
        self._deactivate_impl()
        self._expire_all_feedback()
        type(self)._instances.discard(self)
        self._last_info = None
        service = self._runtime_service
        self._runtime_service = None
        if service is not None:
            service.detach_consumer(self)
            if service is self._standalone_runtime_service:
                service.retire()
        self._standalone_runtime_service = None
        logger.debug("[LIFECYCLE] MediaWidget cleaned up")
    
    # -------------------------------------------------------------------------
    # Legacy Start/Stop Methods (for backward compatibility)
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Activate this display's lease on the shared Media owner."""

        if self._enabled:
            logger.warning("Media widget already running")
            return
        if not self._ensure_thread_manager("MediaWidget.start"):
            return
        service = self._runtime_service
        if service is None:
            logger.error("[MEDIA_WIDGET] Cannot start without runtime service")
            return
        if service.provider != self._provider:
            self.on_media_runtime_provider_changed(
                self._provider,
                service.provider,
                source="runtime_reactivate",
                persist=False,
            )
        try:
            self.hide()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        if not service.start():
            logger.error("[MEDIA_WIDGET] Runtime service refused start")
            return
        self._enabled = True
        logger.info("Media widget started")

    def stop(self) -> None:
        """Release this display's active lease and hide the presenter."""

        if not self._enabled:
            return

        service = self._runtime_service
        if service is not None:
            service.stop()
        self._enabled = False
        self._clear_pending_keyboard_alias_timer()
        self._pending_keyboard_alias_command = None
        self.hide()
        logger.debug("Media widget stopped")

    def is_running(self) -> bool:
        service = self._runtime_service
        return bool(self._enabled and service is not None and service.is_running())

    def cleanup(self) -> None:
        """Clean up resources (called from DisplayWidget)."""

        logger.debug("Cleaning up media widget")
        super().cleanup()

    def set_thread_manager(self, thread_manager) -> None:
        super().set_thread_manager(thread_manager)
        runtime_tm = thread_manager or self._thread_manager
        self._pending_runtime_thread_manager = runtime_tm
        service = self._runtime_service
        if service is not None and runtime_tm is not None:
            service.set_thread_manager(runtime_tm)
        invalidate = getattr(self, "_invalidate_controls_layout", None)
        if callable(invalidate):
            invalidate()
        if self._enabled and service is not None and runtime_tm is not None:
            service.refresh(bust_cache=True)
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
        """Transitional wake entry point forwarded to the neutral owner."""

        service = self._runtime_service
        if self._enabled and service is not None:
            service.wake_from_idle()

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
        if self._show_background:
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

    def set_font_size(self, size: int) -> None:  # type: ignore[override]
        """Set the temporary transport-control font size."""

        if int(size) == int(getattr(self, "_font_size", -1)):
            return
        super().set_font_size(size)
        self._invalidate_controls_layout()
        self._refresh_playback_progress_snapshot()
        self._safe_update()

    def set_artwork_size(self, size: int) -> None:
        """Keep the F4/CUSTOM anchor geometry aligned to retained artwork size."""

        if size <= 0:
            return
        if int(size) == int(self._artwork_size):
            return
        self._artwork_size = int(size)
        self._invalidate_controls_layout()
        target_min_height = max(220, self._artwork_size + 60)
        self.setMinimumHeight(self._resolve_custom_locked_height(target_min_height))
        if self._active_custom_layout_rect() is not None:
            try:
                self.updateGeometry()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            self._schedule_custom_layout_geometry_reapply()
        self._refresh_playback_progress_snapshot()
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
        self._invalidate_controls_layout()
        self._refresh_playback_progress_snapshot()
        self._safe_update()

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
        self._invalidate_controls_layout()
        progress_changed = self._refresh_playback_progress_snapshot()
        if progress_changed or old_reserved != new_reserved:
            self._safe_update()


    def _invalidate_controls_layout(self) -> None:
        """Clear cached transport controls geometry."""
        self._controls_layout_cache = None

    # ------------------------------------------------------------------
    # Transport controls (delegated to the neutral shared owner)
    # ------------------------------------------------------------------
    def play_pause(self, source: str = "manual", execute: bool = True) -> None:
        """Toggle play/pause when supported.

        This is best-effort and never raises; failures are logged by the
        underlying controller. It is safe to call even when no media is
        currently playing.
        """
        if execute and self._should_defer_keyboard_alias_command(source, "play"):
            return

        service = self._runtime_service
        control_executed = bool(
            service is not None and service.play_pause(execute=execute)
        )
        self._handle_control_feedback(
            "play",
            source,
            force_refresh=not control_executed,
        )

    def next_track(self, source: str = "manual", execute: bool = True) -> None:
        """Skip to next track when supported (best-effort)."""

        service = self._runtime_service
        control_executed = bool(
            service is not None and service.next_track(execute=execute)
        )
        self._handle_control_feedback(
            "next",
            source,
            force_refresh=not control_executed,
        )

    def previous_track(self, source: str = "manual", execute: bool = True) -> None:
        """Go to previous track when supported (best-effort)."""

        service = self._runtime_service
        control_executed = bool(
            service is not None and service.previous_track(execute=execute)
        )
        self._handle_control_feedback(
            "prev",
            source,
            force_refresh=not control_executed,
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
            self._last_track_identity = None
            service = self._runtime_service
            if service is None or not service.refresh(bust_cache=True):
                return False
            logger.info("[MEDIA_WIDGET] Double-click triggered media refresh")
            return True
        except Exception:
            logger.debug("[MEDIA_WIDGET] Double-click refresh failed", exc_info=True)
            return False

    def _request_refresh_after_control(self) -> bool:
        if not self._enabled:
            return False
        try:
            service = self._runtime_service
            return bool(service is not None and service.refresh(bust_cache=True))
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
        service = self._runtime_service
        if service is not None:
            service.wake_from_idle()

    def _refresh(self) -> None:
        if not self._enabled:
            return
        service = self._runtime_service
        if service is not None:
            service.refresh()


    def _refresh_async(self) -> None:
        """Transitional private refresh alias forwarded to the shared owner."""

        service = self._runtime_service
        if self._enabled and service is not None:
            service.refresh()

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
    ) -> None:
        """Project accepted state into the temporary F4 controls bridge."""

        from widgets.media.display_update import update_display

        update_display(self, info)
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
        """Compute the state identity still consumed by F4 controls."""

        return (
            (info.title or "").strip().lower(),
            (info.artist or "").strip().lower(),
            (info.album or "").strip().lower(),
            getattr(info.state, "value", info.state),
            bool(info.can_play_pause),
            bool(info.can_previous),
            bool(info.can_next),
        )
    
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
            self._invalidate_controls_layout()
            if self._refresh_playback_progress_snapshot():
                self._safe_update()

    def paintEvent(self, event):  # type: ignore[override]
        """Paint the temporary F4 controls/progress compatibility surface."""
        with widget_paint_sample(self, "media.paint"):
            self._paint_contents(event)

    def _paint_contents(self, event) -> None:
        """Internal paint implementation. Delegates to widgets.media.painting."""
        from widgets.media.painting import paint_contents
        paint_contents(self, event)

    def _start_widget_fade_in(self, duration_ms: Optional[int] = None) -> None:
        """Fade the temporary F4 anchor in."""
        resolved_duration_ms = (
            ShadowFadeProfile.default_duration_ms()
            if duration_ms is None
            else max(0, int(duration_ms))
        )
        # Reset completion so re-entrancy can restore the temporary anchor.
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
        """Mark the temporary anchor fade-in complete."""
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
