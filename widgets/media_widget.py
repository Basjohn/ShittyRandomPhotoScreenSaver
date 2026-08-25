"""Temporary non-painting Media runtime and Visualizer anchor.

This QWidget presents the accepted state from a neutral Media runtime lease.
Controller/provider lifetime, polling, shared playback state and source artwork
decode live outside this anchor. Retained Quick owns every Media pixel and
pointer action. This class survives only until the physical retained host lands
because the current Visualizer still consumes its signal, visibility and
geometry relationship.

Neutral transport and system-audio methods remain for keyboard/native ingress.
Retained Quick owns pointer admission and semantic pointer actions; normal
screensaver mode remains non-interactive.
"""
from __future__ import annotations

import time
from dataclasses import asdict
from enum import Enum
from typing import Optional, TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Qt, Signal
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
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

if TYPE_CHECKING:
    from rendering.widget_manager import WidgetManager
    from widgets.media_volume_runtime import (
        MediaVolumeRuntimeService,
        MediaVolumeRuntimeSnapshot,
    )
    from widgets.system_mute_runtime import (
        SystemMuteRuntimeService,
        SystemMuteRuntimeSnapshot,
    )

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
    """Non-painting compatibility anchor for neutral Media runtime state."""

    media_updated = Signal(dict)  # Emits dict(MediaTrackInfo) when refreshed
    
    DEFAULT_FONT_SIZE = 20
    
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
        self._perf_media_last_log_ts: float = time.monotonic()

        self._runtime_service: Optional[MediaRuntimeService] = None
        self._standalone_runtime_service: Optional[MediaRuntimeService] = None
        self._volume_runtime_service: Optional["MediaVolumeRuntimeService"] = None
        self._system_mute_runtime_service: Optional["SystemMuteRuntimeService"] = None
        self._volume_runtime_attached = False
        self._system_mute_runtime_attached = False
        self._last_volume_runtime_revision = 0
        self._last_system_mute_runtime_revision = 0
        self._app_volume_supported = False
        self._app_volume_available = False
        self._app_volume_level = 1.0
        self._system_mute_available = False
        self._system_muted = False
        self._last_runtime_revision: int = 0
        self._pending_runtime_thread_manager: Optional[ThreadManager] = None
        if thread_manager is not None:
            self.set_thread_manager(thread_manager)
        if controller is not None and not build_default_runtime:
            raise ValueError("controller injection requires standalone Media runtime ownership")

        self._widget_manager: Optional["WidgetManager"] = None
        self._pending_keyboard_alias_command: Optional[tuple[str, float]] = None
        self._pending_keyboard_alias_timer: Optional[QTimer] = None
        self._last_external_transport_event: Optional[tuple[str, float]] = None

        # The Visualizer relationship still follows the Media card footprint.
        self._artwork_size: int = 200

        # Central ResourceManager wiring
        self._last_info: Optional[MediaTrackInfo] = None
        
        # Smart polling: diff gating to skip unnecessary updates
        self._last_track_identity: Optional[tuple] = None
        
        # First accepted state is published before the anchor becomes visible.
        self._has_seen_first_track: bool = False

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
        """Read the shared owner's accepted snapshot for the Visualizer bridge."""

        service = self._runtime_service
        if service is not None:
            return service.current_info()
        return self._last_info

    def current_media_info(self) -> Optional[MediaTrackInfo]:
        """Return the accepted neutral snapshot for Visualizer seeding."""

        return self.get_retained_display_info()

    def set_runtime_service(self, service: MediaRuntimeService) -> None:
        """Attach this anchor to its per-display neutral Media lease."""

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
            raise RuntimeError("Media runtime service could not resume active anchor")

    def set_volume_runtime_service(self, service: "MediaVolumeRuntimeService") -> None:
        """Inject the existing presentation-neutral app-volume lease."""

        if service is None:
            raise ValueError("Media volume runtime service is required")
        current = self._volume_runtime_service
        if current is service:
            self._forward_thread_manager(service)
            return
        self._detach_volume_runtime()
        self._volume_runtime_service = service
        self._last_volume_runtime_revision = 0
        self._forward_thread_manager(service)
        if self._enabled:
            self._start_auxiliary_runtimes()

    def set_system_mute_runtime_service(
        self, service: "SystemMuteRuntimeService"
    ) -> None:
        """Inject the existing presentation-neutral system-audio lease."""

        if service is None:
            raise ValueError("System mute runtime service is required")
        current = self._system_mute_runtime_service
        if current is service:
            self._forward_thread_manager(service)
            return
        self._detach_system_mute_runtime()
        self._system_mute_runtime_service = service
        self._last_system_mute_runtime_revision = 0
        self._forward_thread_manager(service)
        if self._enabled:
            self._start_auxiliary_runtimes()

    def clear_volume_runtime_service(self) -> None:
        self._detach_volume_runtime()

    def clear_system_mute_runtime_service(self) -> None:
        self._detach_system_mute_runtime()

    def _forward_thread_manager(self, service: object) -> None:
        thread_manager = self._thread_manager or self._pending_runtime_thread_manager
        setter = getattr(service, "set_thread_manager", None)
        if thread_manager is not None and callable(setter):
            setter(thread_manager)

    def is_media_consumer_alive(self) -> bool:
        """Return whether service delivery may still target this anchor."""

        try:
            if not Shiboken.isValid(self):
                return False
        except Exception:
            return False
        return getattr(getattr(self, "_lifecycle_state", None), "name", "") != "DESTROYED"

    def is_media_volume_consumer_alive(self) -> bool:
        return self.is_media_consumer_alive()

    def is_system_mute_consumer_alive(self) -> bool:
        return self.is_media_consumer_alive()

    def on_media_volume_runtime_snapshot(
        self, snapshot: "MediaVolumeRuntimeSnapshot"
    ) -> None:
        """Accept one app-volume revision for semantic keyboard actions."""

        if not self.is_media_consumer_alive():
            return
        try:
            revision = int(snapshot.revision)
            level = max(0.0, min(1.0, float(snapshot.level)))
        except (AttributeError, TypeError, ValueError):
            return
        if revision <= self._last_volume_runtime_revision:
            return
        self._last_volume_runtime_revision = revision
        self._app_volume_supported = bool(snapshot.supported)
        self._app_volume_available = bool(snapshot.available)
        self._app_volume_level = level

    def on_system_mute_runtime_snapshot(
        self, snapshot: "SystemMuteRuntimeSnapshot"
    ) -> None:
        """Accept one endpoint revision for semantic system-audio actions."""

        if not self.is_media_consumer_alive():
            return
        try:
            revision = int(snapshot.revision)
        except (AttributeError, TypeError, ValueError):
            return
        if revision <= self._last_system_mute_runtime_revision:
            return
        self._last_system_mute_runtime_revision = revision
        self._system_mute_available = bool(snapshot.available)
        self._system_muted = bool(snapshot.muted)

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
        """Reset only anchor state after the neutral owner changes provider."""

        normalized = self._validate_provider(provider)
        self._provider = normalized
        self._last_runtime_revision = 0
        self._last_info = None
        self._last_track_identity = None
        volume_service = self._volume_runtime_service
        if volume_service is not None:
            try:
                volume_service.set_provider_runtime(normalized)
            except Exception:
                logger.debug(
                    "[MEDIA_WIDGET] Failed to project provider to volume runtime",
                    exc_info=True,
                )
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
        """Forward the accepted target directly to the neutral volume owner."""

        service = self._volume_runtime_service
        if service is None:
            return
        try:
            service.set_runtime_volume_source(provider, source_id)
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
        # This compatibility object is geometry/state only and must never paint.
        self.setStyleSheet("background: transparent; border: none;")
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        try:
            # Non-interactive by default; screensaver interaction is gated elsewhere.
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

        self.setContentsMargins(0, 0, 0, 0)

        # Preserve the retained Media card footprint for Visualizer/CUSTOM geometry.
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
        """Activate this anchor lease; the shared owner starts on first use."""
        if not self._ensure_thread_manager("MediaWidget._activate_impl"):
            raise RuntimeError("Media anchor activation requires ThreadManager")
        service = self._runtime_service
        if service is not None and service.provider != self._provider:
            self.on_media_runtime_provider_changed(
                self._provider,
                service.provider,
                source="runtime_reactivate",
                persist=False,
            )
        if service is None or not service.start():
            raise RuntimeError("Media anchor has no startable runtime service")
        self._start_auxiliary_runtimes()
        logger.debug("[LIFECYCLE] MediaWidget activated")
    
    def _deactivate_impl(self) -> None:
        """Release this active lease without disturbing other displays."""
        service = self._runtime_service
        if service is not None:
            service.stop()
        self._stop_auxiliary_runtimes()
        self._clear_pending_keyboard_alias_timer()
        self._pending_keyboard_alias_command = None
        logger.debug("[LIFECYCLE] MediaWidget deactivated")
    
    def _cleanup_impl(self) -> None:
        """Clean up media resources (lifecycle hook)."""
        self._deactivate_impl()
        self._last_info = None
        self._detach_system_mute_runtime()
        self._detach_volume_runtime()
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
        self._start_auxiliary_runtimes()
        logger.info("Media widget started")

    def stop(self) -> None:
        """Release this display's active lease and hide the anchor."""

        if not self._enabled:
            return

        service = self._runtime_service
        if service is not None:
            service.stop()
        self._stop_auxiliary_runtimes()
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
        for auxiliary in (
            self._volume_runtime_service,
            self._system_mute_runtime_service,
        ):
            if auxiliary is not None and runtime_tm is not None:
                auxiliary.set_thread_manager(runtime_tm)
        if self._enabled and service is not None and runtime_tm is not None:
            service.refresh(bust_cache=True)
        if is_verbose_logging():
            logger.debug("[MEDIA_WIDGET] ThreadManager injected: %s", type(thread_manager).__name__ if thread_manager else None)

    def _start_auxiliary_runtimes(self) -> None:
        """Attach/start optional action owners without creating pixel widgets."""

        for service, attached_name, label in (
            (self._volume_runtime_service, "_volume_runtime_attached", "app volume"),
            (
                self._system_mute_runtime_service,
                "_system_mute_runtime_attached",
                "system mute",
            ),
        ):
            if service is None:
                continue
            try:
                self._forward_thread_manager(service)
                if not bool(getattr(self, attached_name)):
                    service.attach_consumer(self)
                    setattr(self, attached_name, True)
                if not service.is_running() and not service.start():
                    raise RuntimeError(f"{label} runtime refused start")
            except Exception:
                logger.error(
                    "[MEDIA_WIDGET] Failed to start neutral %s owner",
                    label,
                    exc_info=True,
                )
                try:
                    service.detach_consumer(self)
                except Exception:
                    logger.debug(
                        "[MEDIA_WIDGET] Failed to detach rejected %s owner",
                        label,
                        exc_info=True,
                    )
                setattr(self, attached_name, False)

    def _stop_auxiliary_runtimes(self) -> None:
        for service in (
            self._system_mute_runtime_service,
            self._volume_runtime_service,
        ):
            if service is not None:
                service.stop()

    def _detach_volume_runtime(self) -> None:
        service = self._volume_runtime_service
        if service is not None:
            service.stop()
            if self._volume_runtime_attached:
                service.detach_consumer(self)
        self._volume_runtime_attached = False
        self._volume_runtime_service = None

    def _detach_system_mute_runtime(self) -> None:
        service = self._system_mute_runtime_service
        if service is not None:
            service.stop()
            if self._system_mute_runtime_attached:
                service.detach_consumer(self)
        self._system_mute_runtime_attached = False
        self._system_mute_runtime_service = None

    def set_widget_manager(self, widget_manager: "WidgetManager") -> None:
        self._widget_manager = widget_manager

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
        
        Called when the Media anchor shows or hides so the Visualizer can sync.
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
        
    def _update_stylesheet(self) -> None:
        """Keep the compatibility anchor pixel-transparent."""

        self.setStyleSheet("background: transparent; border: none;")

    def set_position(self, position: MediaPosition) -> None:
        """Set widget position using MediaPosition enum."""
        self._media_position = position
        # Update base class position
        overlay_pos = OverlayPosition(position.value)
        super().set_position(overlay_pos)

    def set_artwork_size(self, size: int) -> None:
        """Keep Visualizer/CUSTOM anchor geometry aligned to Media card size."""

        if size <= 0:
            return
        if int(size) == int(self._artwork_size):
            return
        self._artwork_size = int(size)
        target_min_height = max(220, self._artwork_size + 60)
        self.setMinimumHeight(self._resolve_custom_locked_height(target_min_height))
        if self._active_custom_layout_rect() is not None:
            try:
                self.updateGeometry()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            self._schedule_custom_layout_geometry_reapply()

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
        if not control_executed:
            self._request_refresh_after_control()

    def next_track(self, source: str = "manual", execute: bool = True) -> None:
        """Skip to next track when supported (best-effort)."""

        service = self._runtime_service
        control_executed = bool(
            service is not None and service.next_track(execute=execute)
        )
        if not control_executed:
            self._request_refresh_after_control()

    def previous_track(self, source: str = "manual", execute: bool = True) -> None:
        """Go to previous track when supported (best-effort)."""

        service = self._runtime_service
        control_executed = bool(
            service is not None and service.previous_track(execute=execute)
        )
        if not control_executed:
            self._request_refresh_after_control()

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
            execute: When False, skips controller calls and refreshes accepted
                state. Used for external hardware keys that the OS handled.
        Returns:
            True when the command was recognized, False otherwise.
        """

        normalized = self._normalize_control_key(key)
        if normalized is None:
            return False

        if not execute:
            self._consume_matching_keyboard_alias(normalized)
            if self._should_suppress_duplicate_external_transport_event(normalized):
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

    def request_app_volume_step(self, direction: int) -> bool:
        """Route one admitted app-volume step through the neutral owner."""

        service = self._volume_runtime_service
        if (
            direction == 0
            or service is None
            or not service.is_running()
            or not self._app_volume_supported
            or not self._app_volume_available
        ):
            return False
        delta = 0.05 if direction > 0 else -0.05
        level = max(0.0, min(1.0, self._app_volume_level + delta))
        return bool(service.set_volume_optimistic(level))

    def has_live_system_mute_runtime(self) -> bool:
        service = self._system_mute_runtime_service
        return bool(
            service is not None
            and service.is_running()
            and self._system_mute_available
        )

    def request_system_mute_toggle(self) -> bool:
        service = self._system_mute_runtime_service
        return bool(
            self.has_live_system_mute_runtime()
            and service is not None
            and service.toggle_mute()
        )

    def request_system_volume_step(self, delta: float) -> float | None:
        service = self._system_mute_runtime_service
        if not self.has_live_system_mute_runtime() or service is None:
            return None
        return service.step_system_volume(float(delta))

    def request_system_mute_refresh(
        self, *, force: bool = False, source: str = "refresh"
    ) -> bool:
        service = self._system_mute_runtime_service
        if service is None or not service.is_running():
            return False
        return bool(service.request_refresh(force=force, source=source))

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

    def _should_suppress_duplicate_external_transport_event(self, key: str) -> bool:
        """Collapse duplicate execute=False media command bursts from OS/native routes.

        A single physical media-key event can surface through multiple Windows/Qt
        paths (`WM_APPCOMMAND`, media QKeyEvent, raw-input feedback). Those routes
        are all external ownership signals, so the media widget must treat the
        first one as authoritative and ignore immediate duplicates rather than
        toggling PLAYING -> PAUSED -> PLAYING locally.
        """
        now = time.monotonic()
        last_event = self._last_external_transport_event
        self._last_external_transport_event = (key, now)
        if last_event is None:
            return False
        last_key, last_ts = last_event
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
        """Project accepted state into the Visualizer anchor bridge."""

        from widgets.media.display_update import update_display

        update_display(self, info)
    def _compute_track_identity(self, info: MediaTrackInfo) -> tuple:
        """Compute the accepted state identity consumed by the Visualizer."""

        return (
            (info.title or "").strip().lower(),
            (info.artist or "").strip().lower(),
            (info.album or "").strip().lower(),
            getattr(info.state, "value", info.state),
            bool(info.can_play_pause),
            bool(info.can_previous),
            bool(info.can_next),
        )
    
    def paintEvent(self, event):  # type: ignore[override]
        """Intentionally paint nothing; retained Quick owns every Media pixel."""

        event.accept()
