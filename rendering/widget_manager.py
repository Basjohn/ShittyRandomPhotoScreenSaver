"""
Widget Manager - Extracted from DisplayWidget for better separation of concerns.

Manages overlay widget lifecycle, positioning, visibility, and Z-order.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING, Mapping

from PySide6.QtCore import QPoint, QRect, QTimer
from PySide6.QtWidgets import QWidget

from core.logging.logger import (
    get_logger,
    is_geometry_logging_enabled,
    is_verbose_logging,
    is_perf_metrics_enabled,
)
from core.resources.manager import ResourceManager
from core.settings.settings_manager import SettingsManager
from rendering.overlay_startup_policy import get_overlay_startup_fade_policy
from rendering.widget_descriptors import (
    get_live_refresh_handlers,
    get_live_refresh_handlers_for_settings_key,
    get_widget_runtime_descriptor_by_attr_name,
    is_custom_position_selected_for_widget,
)
from rendering.multi_monitor_coordinator import get_coordinator
from rendering.widget_setup import parse_color_to_qcolor, compute_expected_overlays
from rendering.fade_coordinator import FadeCoordinator
from widgets.media_widget import MediaWidget
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
from core.settings.models import SpotifyVisualizerSettings, MediaWidgetSettings, RedditWidgetSettings
from core.settings.visualizer_presets import (
    apply_preset_to_config,
    build_normalized_custom_snapshot,
    get_custom_preset_index,
    get_preset_count,
    resolve_visualizer_activation_payload,
    restore_visualizer_snapshot,
    resolve_preset_index_from_mapping,
    VISUALIZER_CUSTOM_STORAGE_KEY,
)
from core.settings.visualizer_mode_registry import get_preset_key
from core.settings.visualizer_settings_contract import strip_legacy_global_technical_keys
from core.threading.manager import ThreadManager
from widgets.spotify_volume_widget import SpotifyVolumeWidget
from rendering.widget_positioner import WidgetPositioner, PositionAnchor
from rendering.widget_stacking import (
    StackObstacle,
    StackParticipant,
    build_stack_plan,
    get_stack_band,
    get_stack_lane,
)
from rendering.widget_factories import WidgetFactoryRegistry
from widgets.base_overlay_widget import BaseOverlayWidget

if TYPE_CHECKING:
    from rendering.display_widget import DisplayWidget
    from core.threading.manager import ThreadManager

logger = get_logger(__name__)


_STACK_RESERVED_MEDIA_VISUALIZER_KEY = "__reserved_spotify_media_visualizer"


class WidgetManager:
    """
    Manages overlay widgets for a DisplayWidget.
    
    Responsibilities:
    - Widget creation and destruction
    - Widget positioning and sizing
    - Widget visibility and Z-order
    - Fade coordination via ShadowFadeProfile
    - Rate-limited raise operations
    - Effect invalidation (Phase E: cache corruption mitigation)
    
    Phase E Context:
        This class centralizes QGraphicsEffect lifecycle management to make
        ordering deterministic during context menu open/close and focus/activation
        cascades. By owning effect invalidation, we can prevent the cache corruption
        that occurs when effects are manipulated from multiple call sites with
        inconsistent ordering.
    """
    
    # Rate limit for raise operations (ms)
    RAISE_RATE_LIMIT_MS = 100
    PRESET_PERSIST_DELAY_MS = 120
    
    def __init__(self, parent: "DisplayWidget", resource_manager: Optional[ResourceManager] = None):
        """
        Initialize the WidgetManager.
        
        Args:
            parent: The DisplayWidget that owns these widgets
            resource_manager: Optional ResourceManager for lifecycle tracking
        """
        self._parent = parent
        self._resource_manager = resource_manager
        
        # Widget references
        self._widgets: Dict[str, QWidget] = {}
        
        # Rate limiting for raise operations
        self._last_raise_time: float = 0.0
        self._pending_raise: bool = False
        self._raise_timer: Optional[QTimer] = None
        
        # Fade callbacks
        self._fade_callbacks: Dict[str, Callable] = {}
        
        # Fade coordination - centralized via FadeCoordinator
        self._fade_coordinator: FadeCoordinator = FadeCoordinator(
            screen_index=getattr(parent, "screen_index", 0)
        )
        self._expected_overlays: set[str] = set()
        self._spotify_secondary_fade_starters: list[Callable[[], None]] = []
        self._spotify_overlay_prewarm_attempted: bool = False
        self._spotify_overlay_prewarmed: bool = False

        # Wait for compositor first frame before starting widget fades
        self._compositor_ready: bool = False
        self._connect_compositor_ready_signal()
        
        # Widget positioning (Dec 2025)
        self._positioner = WidgetPositioner()
        
        # Widget factory registry (Dec 2025) - for simplified widget creation
        self._factory_registry: Optional[WidgetFactoryRegistry] = None

        # Settings manager wiring for live updates (Spotify VIS etc.)
        self._settings_manager: Optional[SettingsManager] = None
        
        # Spotify visibility sync state
        self._pending_spotify_visibility_sync: bool = False
        self._visualizer_preset_save_token: int = 0
        
        logger.debug("[WIDGET_MANAGER] Initialized")

    def _mirror_parent_overlay_state(self) -> None:
        parent = self._parent
        if parent is None:
            return
        try:
            parent._overlay_fade_expected = set(self._expected_overlays)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

    def _mark_parent_spotify_secondary_not_before(self, delay_ms: int) -> None:
        parent = self._parent
        if parent is None:
            return
        try:
            parent._spotify_secondary_not_before_ts = time.monotonic() + (
                max(0, int(delay_ms)) / 1000.0
            )
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

    def _get_overlay_startup_policy(self):
        """Return the canonical overlay startup timing policy."""

        return get_overlay_startup_fade_policy()

    def _prewarm_spotify_visualizer_overlay(self) -> bool:
        """Prewarm the Spotify visualizer GL overlay before hot-start reveal."""

        if self._spotify_overlay_prewarmed:
            return self._spotify_overlay_prewarmed

        parent = self._parent
        if parent is None:
            return False

        vis = getattr(parent, "spotify_visualizer_widget", None)
        if vis is None:
            return False

        try:
            from rendering.display_image_ops import prewarm_spotify_visualizer_overlay

            self._spotify_overlay_prewarmed = bool(
                prewarm_spotify_visualizer_overlay(parent)
            )
        except Exception:
            logger.debug(
                "[SPOTIFY_SECONDARY] Failed to prewarm Spotify visualizer overlay",
                exc_info=True,
            )
            self._spotify_overlay_prewarmed = False
        else:
            self._spotify_overlay_prewarm_attempted = self._spotify_overlay_prewarmed

        logger.debug(
            "[SPOTIFY_SECONDARY] visualizer overlay prewarm result=%s",
            self._spotify_overlay_prewarmed,
        )
        return self._spotify_overlay_prewarmed

    def _schedule_spotify_secondary_fades(self, delay_ms: int) -> None:
        queued = list(self._spotify_secondary_fade_starters)
        self._spotify_secondary_fade_starters = []
        self._prewarm_spotify_visualizer_overlay()
        self._mark_parent_spotify_secondary_not_before(delay_ms)
        logger.debug(
            "[SPOTIFY_SECONDARY] scheduling %d queued starters (delay_ms=%s, compositor_ready=%s, expected=%s)",
            len(queued),
            int(delay_ms),
            self._compositor_ready,
            sorted(self._expected_overlays),
        )

        for starter in queued:
            try:
                if delay_ms <= 0:
                    starter()
                else:
                    QTimer.singleShot(delay_ms, starter)
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
                try:
                    starter()
                except Exception as inner:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", inner)

    def _bind_parent_attribute(self, attr_name: str, widget: Optional[QWidget]) -> None:
        """Expose newly created widgets on the parent DisplayWidget immediately."""
        parent = self._parent
        logger.debug("[WIDGET_MANAGER] Binding %s to parent=%s widget=%s", attr_name, parent, widget)
        if parent is None:
            logger.debug("[WIDGET_MANAGER] Cannot bind %s - parent is None", attr_name)
            return
        try:
            setattr(parent, attr_name, widget)
            logger.debug("[WIDGET_MANAGER] Successfully bound %s to parent", attr_name)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Failed to bind %s on parent: %s", attr_name, e)
    
    def _connect_compositor_ready_signal(self) -> None:
        """Connect to parent's image_displayed signal to know when compositor is ready."""
        if self._parent is None:
            self._compositor_ready = True  # No parent, assume ready
            return
        
        try:
            # Check if parent already has rendered first frame
            if getattr(self._parent, "_has_rendered_first_frame", False):
                self._compositor_ready = True
                try:
                    self._fade_coordinator.signal_compositor_ready()
                except Exception:
                    logger.debug(
                        "[WIDGET_MANAGER] Failed to prime fade coordinator for already-ready compositor",
                        exc_info=True,
                    )
                return
            
            # Connect to image_displayed signal
            if hasattr(self._parent, "image_displayed"):
                self._parent.image_displayed.connect(self._on_compositor_ready)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Failed to connect compositor ready signal: %s", e)
            self._compositor_ready = True  # Assume ready on failure
    
    def _on_compositor_ready(self, image_path: str) -> None:
        """Called when compositor displays first image."""
        screen_idx = getattr(self._parent, "screen_index", "?")
        if self._compositor_ready:
            logger.debug("[FADE_SYNC] Compositor already ready on screen=%s, ignoring duplicate signal", screen_idx)
            return  # Already marked ready
        
        self._compositor_ready = True
        # Signal FadeCoordinator that compositor is ready
        self._fade_coordinator.signal_compositor_ready()
        try:
            self._parent._overlay_fade_started = True
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        if self._expected_overlays:
            try:
                policy = self._get_overlay_startup_policy()
                logger.debug(
                    "[SPOTIFY_SECONDARY] compositor ready; using startup secondary delay=%sms",
                    int(policy.spotify_secondary_startup_delay_ms),
                )

                self._schedule_spotify_secondary_fades(
                    int(policy.spotify_secondary_startup_delay_ms),
                )
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        
        logger.info("[FADE_SYNC] Compositor ready on screen=%s (first image: %s)", screen_idx, image_path)
        
        # Disconnect signal to avoid repeated calls
        try:
            if self._parent is not None and hasattr(self._parent, "image_displayed"):
                self._parent.image_displayed.disconnect(self._on_compositor_ready)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
    
    def set_factory_registry(
        self, 
        settings: SettingsManager, 
        thread_manager: Optional["ThreadManager"] = None
    ) -> None:
        """
        Initialize the widget factory registry.
        
        Args:
            settings: SettingsManager for widget configuration
            thread_manager: Optional ThreadManager for background operations
        """
        self._factory_registry = WidgetFactoryRegistry(settings, thread_manager)
        logger.debug("[WIDGET_MANAGER] Factory registry initialized")
    
    def set_process_supervisor(self, supervisor) -> None:
        """Set the ProcessSupervisor on the factory registry.
        
        This enables worker integration for widgets that need process supervision.
        """
        if self._factory_registry is not None:
            self._factory_registry.set_process_supervisor(supervisor)
            logger.debug("[WIDGET_MANAGER] ProcessSupervisor set on factory registry")
    
    def create_widget_from_factory(
        self,
        widget_type: str,
        config: Dict[str, Any],
    ) -> Optional[QWidget]:
        """
        Create a widget using the factory registry.
        
        This is a simplified creation method that delegates to the factory.
        For complex widget creation with full settings resolution, use the
        specific create_*_widget methods.
        
        Args:
            widget_type: Type of widget ('clock', 'weather', 'media', 'reddit', etc.)
            config: Widget configuration dict
            
        Returns:
            Created widget or None if creation failed
        """
        if self._factory_registry is None:
            logger.warning("[WIDGET_MANAGER] Factory registry not initialized")
            return None
        
        widget = self._factory_registry.create_widget(widget_type, self._parent, config)
        if widget:
            self.register_widget(widget_type, widget)
        return widget
    
    def register_widget(self, name: str, widget: QWidget) -> None:
        """
        Register a widget for management.
        
        Args:
            name: Unique name for the widget
            widget: The widget to manage
        """
        self._widgets[name] = widget
        if widget is not None:
            if hasattr(widget, "set_widget_manager"):
                try:
                    widget.set_widget_manager(self)
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

            # Ensure widgets inherit the ThreadManager from the display if they expose a setter
            parent_tm = getattr(self._parent, "_thread_manager", None)
            if parent_tm is not None and hasattr(widget, "set_thread_manager"):
                try:
                    current_tm = getattr(widget, "_thread_manager", None)
                except Exception:
                    current_tm = None
                if current_tm is None:
                    try:
                        widget.set_thread_manager(parent_tm)
                    except Exception as e:
                        logger.debug("[WIDGET_MANAGER] Failed to inject ThreadManager into %s: %s", name, e)
        if self._resource_manager:
            try:
                self._resource_manager.register_qt(widget, description=f"Widget: {name}")
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        logger.debug(f"[WIDGET_MANAGER] Registered widget: {name}")

    def configure_expected_overlays(self, widgets_config: Dict[str, Any]) -> None:
        """Compute and store the overlays expected to participate in fade sync."""
        if widgets_config is None:
            widgets_config = {}
        try:
            expected = compute_expected_overlays(self._parent, widgets_config)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            expected = set()
        self.set_expected_overlays(expected)
    
    def unregister_widget(self, name: str) -> Optional[QWidget]:
        """
        Unregister a widget.
        
        Args:
            name: Name of the widget to unregister
            
        Returns:
            The unregistered widget or None
        """
        widget = self._widgets.pop(name, None)
        if widget:
            logger.debug(f"[WIDGET_MANAGER] Unregistered widget: {name}")
        return widget
    
    def get_widget(self, name: str) -> Optional[QWidget]:
        """Get a widget by name."""
        return self._widgets.get(name)
    
    def get_all_widgets(self) -> List[QWidget]:
        """Get all managed widgets."""
        return list(self._widgets.values())
    
    def dispatch_double_click(self, global_pos: QPoint) -> bool:
        """Find the topmost interactive widget under *global_pos* and delegate.

        Iterates registered widgets in reverse-insertion order (topmost first),
        maps the global position to widget-local coordinates, and calls
        ``handle_double_click(local_point)`` if the widget exposes it and the
        point lands inside the widget geometry.

        Returns True if a widget consumed the event, False otherwise (so the
        caller can fall back to the default next-image behaviour).

        This method performs only event-driven geometry checks — no periodic
        scans or timers.
        """
        for name in reversed(list(self._widgets)):
            widget = self._widgets.get(name)
            if widget is None or not widget.isVisible():
                continue
            try:
                local_pt = widget.mapFromGlobal(global_pos)
                if not widget.rect().contains(local_pt):
                    continue
                handler = getattr(widget, "handle_double_click", None)
                if handler is not None and callable(handler):
                    consumed = handler(local_pt)
                    if consumed:
                        logger.debug("[WIDGET_MANAGER] Double-click consumed by %s", name)
                        return True
            except Exception:
                logger.debug("[WIDGET_MANAGER] Double-click dispatch error for %s", name, exc_info=True)
        return False

    def cycle_visualizer_preset(self, mode_key: str, direction: int) -> bool:
        """Cycle a visualizer preset at runtime via SettingsManager.

        This is the non-UI entry point used by overlay widgets/input routing.
        Returns True when a new preset index is committed.
        """
        if not direction:
            return False
        settings = self._settings_manager
        if settings is None:
            return False

        mode = str(mode_key or "").strip()
        if not mode:
            return False

        try:
            preset_count = int(get_preset_count(mode))
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to read preset count for %s", mode, exc_info=True)
            return False
        if preset_count <= 0:
            return False

        widgets_cfg = settings.get('widgets', {}) or {}
        if not isinstance(widgets_cfg, Mapping):
            widgets_cfg = {}
        spotify_vis_config = widgets_cfg.get('spotify_visualizer', {})
        if not isinstance(spotify_vis_config, Mapping):
            spotify_vis_config = {}

        vis_config = strip_legacy_global_technical_keys(spotify_vis_config)
        preset_key = get_preset_key(mode)
        current_idx = resolve_preset_index_from_mapping(mode, vis_config, prefix="widgets.spotify_visualizer")
        current_idx = max(0, min(preset_count - 1, current_idx))
        custom_index = get_custom_preset_index(mode)

        step = 1 if direction > 0 else -1
        next_idx = (current_idx + step) % preset_count
        if next_idx == current_idx:
            return False

        working_config = dict(vis_config)
        working_config['mode'] = mode
        if current_idx == custom_index:
            cache = settings.get(VISUALIZER_CUSTOM_STORAGE_KEY, {})
            if not isinstance(cache, dict):
                cache = {}
            cache[mode] = build_normalized_custom_snapshot(mode, working_config)
            settings.set(VISUALIZER_CUSTOM_STORAGE_KEY, cache)

        applied = apply_preset_to_config(mode, next_idx, working_config)
        # Use REPLACE semantics, not merge — .update() would leave stale
        # custom mode-specific keys (e.g. blob_shaper_enabled) that the
        # preset didn't include, causing settings to "stick" across presets.
        restore_visualizer_snapshot(mode, vis_config, applied)
        vis_config[preset_key] = next_idx

        if next_idx == custom_index:
            cache = settings.get(VISUALIZER_CUSTOM_STORAGE_KEY, {})
            if isinstance(cache, dict):
                payload = cache.get(mode)
                if isinstance(payload, Mapping):
                    restore_visualizer_snapshot(mode, vis_config, payload)

        full_widgets = dict(widgets_cfg)
        full_widgets['spotify_visualizer'] = vis_config
        settings.set('widgets', full_widgets)
        self._schedule_visualizer_preset_save()
        # Immediately push the refreshed config to the live widget so mode-specific
        # colors (fill/border) and other visual properties take effect without
        # waiting for the async settings-changed bridge.
        try:
            self._refresh_spotify_visualizer_config(
                full_widgets,
                force_runtime_reset=True,
                reset_reason="preset_cycle",
            )
        except Exception:
            logger.debug(
                "[WIDGET_MANAGER] Failed to refresh Spotify visualizer after preset cycle",
                exc_info=True,
            )
        logger.debug(
            "[WIDGET_MANAGER] Cycled visualizer preset mode=%s %s->%s",
            mode,
            current_idx,
            next_idx,
        )
        return True

    def force_visualizer_mode_preset(
        self, target_mode: str, preset_index: int, *, reason: str = "fallback"
    ) -> bool:
        """Switch to a specific mode + preset via the normal settings pipeline.

        Used by the shader-fallback path so the application performs a real
        mode switch (config ⟶ model ⟶ widget refresh) identical to what the
        UI or preset-cycle code would do.
        """
        settings = self._settings_manager
        if settings is None:
            return False

        mode = str(target_mode or '').strip()
        if not mode:
            return False

        widgets_cfg = settings.get('widgets', {}) or {}
        if not isinstance(widgets_cfg, Mapping):
            widgets_cfg = {}
        vis_config = strip_legacy_global_technical_keys(widgets_cfg.get('spotify_visualizer', {}) or {})

        vis_config['mode'] = mode
        preset_key = get_preset_key(mode)
        applied = apply_preset_to_config(mode, preset_index, vis_config)
        restore_visualizer_snapshot(mode, vis_config, applied)
        vis_config[preset_key] = preset_index

        full_widgets = dict(widgets_cfg)
        full_widgets['spotify_visualizer'] = vis_config
        settings.set('widgets', full_widgets)
        self._schedule_visualizer_preset_save()

        try:
            self._refresh_spotify_visualizer_config(
                full_widgets,
                force_runtime_reset=True,
                reset_reason=f"force_preset:{reason}",
            )
        except Exception:
            logger.debug(
                "[WIDGET_MANAGER] Failed to refresh visualizer after forced switch",
                exc_info=True,
            )

        logger.info(
            "[SPOTIFY_VIS] Forced mode switch: mode=%s preset=%d reason=%s",
            mode, preset_index, reason,
        )
        return True

    def _schedule_visualizer_preset_save(self) -> None:
        """Coalesce runtime preset-cycle persistence so repeated taps do not stall rendering."""
        settings = self._settings_manager
        if settings is None:
            return

        self._visualizer_preset_save_token += 1
        token = self._visualizer_preset_save_token
        try:
            ThreadManager.single_shot(
                self.PRESET_PERSIST_DELAY_MS,
                self._flush_visualizer_preset_save,
                token,
            )
        except Exception:
            logger.debug(
                "[WIDGET_MANAGER] Failed to schedule deferred visualizer preset save; saving immediately",
                exc_info=True,
            )
            try:
                settings.save()
            except Exception:
                logger.debug(
                    "[WIDGET_MANAGER] Immediate visualizer preset save failed",
                    exc_info=True,
                )

    def _flush_visualizer_preset_save(self, token: int) -> None:
        """Persist the latest runtime preset-cycle state if no newer cycle superseded it."""
        if token != self._visualizer_preset_save_token:
            return
        settings = self._settings_manager
        if settings is None:
            return
        try:
            settings.save()
        except Exception:
            logger.debug(
                "[WIDGET_MANAGER] Deferred visualizer preset save failed",
                exc_info=True,
            )

    def raise_all(self, force: bool = False) -> None:
        """
        Raise all widgets above the compositor.
        
        Rate-limited to avoid expensive operations on every frame.
        
        Args:
            force: If True, bypass rate limiting
        """
        now = time.time()
        elapsed_ms = (now - self._last_raise_time) * 1000.0
        
        if not force and elapsed_ms < self.RAISE_RATE_LIMIT_MS:
            # Schedule a deferred raise if not already pending
            if not self._pending_raise:
                self._pending_raise = True
                remaining_ms = int(self.RAISE_RATE_LIMIT_MS - elapsed_ms) + 1
                if self._raise_timer is None:
                    self._raise_timer = QTimer()
                    self._raise_timer.setSingleShot(True)
                    self._raise_timer.timeout.connect(self._do_deferred_raise)
                    if self._resource_manager:
                        try:
                            self._resource_manager.register_qt(
                                self._raise_timer,
                                description="WidgetManager raise rate-limit timer",
                            )
                        except Exception:
                            pass
                self._raise_timer.start(remaining_ms)
            return
        
        self._do_raise_all()
    
    def _do_deferred_raise(self) -> None:
        """Execute a deferred raise operation."""
        self._pending_raise = False
        self._do_raise_all()
    
    def _do_raise_all(self) -> None:
        """Actually raise all widgets."""
        self._last_raise_time = time.time()
        
        for name, widget in self._widgets.items():
            try:
                if widget is not None and widget.isVisible():
                    widget.raise_()
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
                if is_verbose_logging():
                    logger.debug(f"[WIDGET_MANAGER] Failed to raise {name}", exc_info=True)
    
    def raise_widget(self, name: str) -> bool:
        """
        Raise a specific widget.
        
        Args:
            name: Name of the widget to raise
            
        Returns:
            True if widget was raised
        """
        widget = self._widgets.get(name)
        if widget is not None:
            try:
                widget.raise_()
                return True
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        return False

    # =========================================================================
    # Settings integration
    # =========================================================================

    def _attach_settings_manager(self, settings_manager: SettingsManager) -> None:
        """Subscribe to settings changes for live widget updates."""
        if settings_manager is None:
            return
        if self._settings_manager is settings_manager:
            return
        self._detach_settings_manager()
        self._settings_manager = settings_manager
        try:
            settings_manager.settings_changed.connect(self._handle_settings_changed)
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to connect settings_changed signal", exc_info=True)

    def _detach_settings_manager(self) -> None:
        """Disconnect previously attached settings manager, if any."""
        if self._settings_manager is None:
            return
        try:
            self._settings_manager.settings_changed.disconnect(self._handle_settings_changed)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        finally:
            self._settings_manager = None

    def _handle_settings_changed(self, key: str, value: object) -> None:
        """React to settings changes for live widget updates."""
        try:
            setting_key = str(key) if key is not None else ""
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            setting_key = ""
        if not setting_key:
            return

        try:
            logger.debug("[WIDGET_MANAGER][SETTINGS] key=%s payload_type=%s", setting_key, type(value).__name__)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        if setting_key == 'widgets':
            widgets_payload: Optional[Mapping[str, Any]] = value if isinstance(value, Mapping) else None
            for handler_name in get_live_refresh_handlers():
                handler = getattr(self, handler_name, None)
                if callable(handler):
                    handler(widgets_payload)
            parent = self._parent
            if parent is not None:
                try:
                    parent._apply_saved_custom_layouts()
                except Exception:
                    logger.debug("[WIDGET_MANAGER] Failed to reapply saved custom layouts", exc_info=True)
            return

        for handler_name in get_live_refresh_handlers_for_settings_key(setting_key):
            handler = getattr(self, handler_name, None)
            if callable(handler):
                handler()
        parent = self._parent
        if parent is not None and setting_key.startswith("widgets."):
            try:
                parent._apply_saved_custom_layouts()
            except Exception:
                logger.debug("[WIDGET_MANAGER] Failed to reapply saved custom layouts", exc_info=True)

    def _log_spotify_vis_config(
        self,
        context: str,
        cfg: Mapping[str, Any],
        *,
        model: Optional[SpotifyVisualizerSettings] = None,
        activation_payload: Optional[object] = None,
    ) -> None:
        """Emit a single structured log line for resolved Spotify VIS technical config."""
        try:
            resolved_model = model
            if resolved_model is None:
                resolved_model = SpotifyVisualizerSettings.from_mapping(cfg)
            mode_key = str(getattr(resolved_model, "mode", cfg.get("mode", "spectrum")) or "spectrum")
            preset_index = getattr(activation_payload, "preset_index", None)
            preset_kind = "custom" if getattr(activation_payload, "is_custom", False) else "curated"
            preset_name = getattr(activation_payload, "preset_name", None)
            preset_path = getattr(activation_payload, "preset_path", None)
            logger.info(
                (
                    "[SPOTIFY_VIS][CFG] %s adaptive=%s sensitivity=%.3f dynamic=%s manual=%.3f "
                    "mode=%s bars=%s block=%s input_gain=%.3f agc=%.3f density=%s displacement=%s heartbeat=%s "
                    "vshift=%s preset_index=%s preset_kind=%s preset_name=%s preset_path=%s"
                ),
                context,
                resolved_model.resolve_adaptive_sensitivity(mode_key),
                float(resolved_model.resolve_sensitivity(mode_key)),
                resolved_model.resolve_dynamic_floor(mode_key),
                float(resolved_model.resolve_manual_floor(mode_key)),
                mode_key,
                int(resolved_model.resolve_bar_count(mode_key)),
                int(resolved_model.resolve_audio_block_size(mode_key)),
                float(resolved_model.resolve_input_gain(mode_key)),
                float(resolved_model.resolve_agc_strength(mode_key)),
                getattr(resolved_model, 'sine_density', cfg.get('sine_density')),
                getattr(resolved_model, 'sine_displacement', cfg.get('sine_displacement')),
                getattr(resolved_model, 'sine_heartbeat', cfg.get('sine_heartbeat')),
                getattr(resolved_model, 'sine_vertical_shift', cfg.get('sine_vertical_shift')),
                preset_index,
                preset_kind,
                preset_name,
                preset_path,
            )
        except Exception:
            logger.debug("[SPOTIFY_VIS][CFG] %s %s", context, cfg, exc_info=True)

    def _apply_media_card_style_to_visualizer(
        self,
        vis_widget: Optional["SpotifyVisualizerWidget"],
        media_settings: Optional[Mapping[str, Any]],
    ) -> None:
        """Apply media widget card styling to the Spotify visualizer card."""
        if vis_widget is None:
            return

        settings_map = media_settings if isinstance(media_settings, Mapping) else {}

        bg_color_data = settings_map.get("bg_color") or settings_map.get("background_color") or [64, 64, 64, 255]
        bg_qcolor = parse_color_to_qcolor(bg_color_data)

        try:
            bg_opacity = float(settings_map.get("bg_opacity", settings_map.get("background_opacity", 0.9)))
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            bg_opacity = 0.9

        border_color_data = settings_map.get("border_color", [128, 128, 128, 255])
        try:
            border_opacity = float(settings_map.get("border_opacity", 0.8))
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            border_opacity = 0.8
        border_qcolor = parse_color_to_qcolor(border_color_data, opacity_override=border_opacity)

        show_background = SettingsManager.to_bool(settings_map.get("show_background", True), True)
        border_width = BaseOverlayWidget.get_global_border_width()

        try:
            vis_widget.set_bar_style(
                bg_color=bg_qcolor or parse_color_to_qcolor([64, 64, 64, 255]),
                bg_opacity=bg_opacity,
                border_color=border_qcolor or parse_color_to_qcolor([128, 128, 128, 255]),
                border_width=border_width,
                show_background=show_background,
            )
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to apply media card style to visualizer", exc_info=True)

    def _refresh_spotify_visualizer_config(
        self,
        widgets_config: Optional[Mapping[str, Any]] = None,
        *,
        force_runtime_reset: bool = False,
        reset_reason: str = "settings_refresh",
    ) -> None:
        """Apply latest Spotify visualizer configuration to the live widget."""
        vis = self._widgets.get('spotify_visualizer') or self._widgets.get('spotify_visualizer_widget')
        if vis is None or not hasattr(vis, 'set_settings_model'):
            return

        cfg = widgets_config
        if cfg is None:
            if self._settings_manager is None:
                return
            cfg = self._settings_manager.get('widgets', {}) or {}
        if not isinstance(cfg, Mapping):
            return

        spotify_cfg = cfg.get('spotify_visualizer', {})
        if not isinstance(spotify_cfg, Mapping):
            return

        activation_payload = resolve_visualizer_activation_payload(spotify_cfg)
        model = SpotifyVisualizerSettings.from_mapping(
            activation_payload.resolved_config,
            apply_preset_overlay=False,
            resolve_preset_indices=False,
        )
        self._log_spotify_vis_config(
            "refresh",
            activation_payload.resolved_config,
            model=model,
            activation_payload=activation_payload,
        )
        try:
            logger.info(
                (
                    "[SPOTIFY_VIS][REFRESH] mode=%s density=%.3f displacement=%.3f "
                    "heartbeat=%.3f vertical_shift=%d line_count=%d"
                ),
                model.mode,
                float(model.sine_density),
                float(model.sine_displacement),
                float(model.sine_heartbeat),
                int(model.sine_vertical_shift),
                int(model.sine_line_count),
            )
        except Exception:
            logger.debug("[SPOTIFY_VIS][REFRESH] Failed to log model snapshot", exc_info=True)

        if hasattr(vis, "apply_resolved_activation_payload"):
            try:
                vis.apply_resolved_activation_payload(
                    model,
                    activation_payload,
                    reason=reset_reason,
                    force_runtime_reset=force_runtime_reset,
                )
            except Exception:
                logger.debug("[WIDGET_MANAGER] Failed to apply resolved Spotify activation payload", exc_info=True)
        else:
            try:
                vis.set_settings_model(model)
            except Exception:
                logger.debug("[WIDGET_MANAGER] Failed to push Spotify model to widget", exc_info=True)

            try:
                from rendering.spotify_widget_creators import apply_spotify_vis_model_config
                apply_spotify_vis_model_config(vis, model)
            except ImportError:
                logger.debug("[WIDGET_MANAGER] Spotify visualizer config helper unavailable", exc_info=True)
            except Exception:
                logger.debug("[WIDGET_MANAGER] Failed to reapply full vis mode config", exc_info=True)

            if force_runtime_reset:
                try:
                    reset_runtime = getattr(vis, "reset_runtime_activation_state", None)
                    if callable(reset_runtime):
                        reset_runtime(reason=reset_reason)
                except Exception:
                    logger.debug(
                        "[WIDGET_MANAGER] Failed to reset visualizer runtime state after config refresh",
                        exc_info=True,
                    )

        media_cfg = cfg.get('media', {}) if isinstance(cfg, Mapping) else {}
        self._apply_media_card_style_to_visualizer(vis, media_cfg)

    def _refresh_media_config(self, widgets_config: Optional[Mapping[str, Any]] = None) -> None:
        """Apply latest media settings to the live media widget (colors/volume flag)."""
        media_widget = self._widgets.get('media_widget') or self._widgets.get('media')
        if media_widget is None:
            return

        cfg = widgets_config
        if cfg is None:
            if self._settings_manager is None:
                return
            cfg = self._settings_manager.get('widgets', {}) or {}
        if not isinstance(cfg, Mapping):
            return

        media_cfg = cfg.get('media', {})
        if not isinstance(media_cfg, Mapping):
            return

        model = MediaWidgetSettings.from_mapping(media_cfg)
        self._sync_media_provider_runtime(model.provider)

        try:
            if hasattr(media_widget, 'set_font_family'):
                media_widget.set_font_family(str(model.font_family))
            if hasattr(media_widget, 'set_font_size'):
                media_widget.set_font_size(int(model.font_size))
            if hasattr(media_widget, 'set_artwork_size'):
                media_widget.set_artwork_size(int(model.artwork_size))
            if hasattr(media_widget, 'set_rounded_artwork_border'):
                media_widget.set_rounded_artwork_border(SettingsManager.to_bool(model.rounded_artwork_border, True))
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to reapply media typography/artwork", exc_info=True)

        try:
            if hasattr(media_widget, 'set_text_color'):
                media_widget.set_text_color(parse_color_to_qcolor(model.color))
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to reapply media text color", exc_info=True)

        try:
            if hasattr(media_widget, 'set_background_color'):
                media_widget.set_background_color(parse_color_to_qcolor(model.bg_color))
            if hasattr(media_widget, 'set_background_opacity'):
                media_widget.set_background_opacity(float(model.background_opacity))
            if hasattr(media_widget, 'set_background_border'):
                border_qcolor = parse_color_to_qcolor(model.border_color, opacity_override=model.border_opacity)
                if border_qcolor:
                    current_width = getattr(media_widget, '_bg_border_width', None)
                    media_widget.set_background_border(current_width if current_width is not None else media_widget.get_global_border_width(), border_qcolor)
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to reapply media background/border", exc_info=True)

        try:
            if hasattr(media_widget, 'set_show_controls'):
                media_widget.set_show_controls(SettingsManager.to_bool(model.show_controls, True))
            if hasattr(media_widget, 'set_show_header_frame'):
                media_widget.set_show_header_frame(SettingsManager.to_bool(model.show_header_frame, True))
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to reapply media controls/header", exc_info=True)

        vis_widget = self._widgets.get('spotify_visualizer') or self._widgets.get('spotify_visualizer_widget')
        if vis_widget is not None:
            self._apply_media_card_style_to_visualizer(vis_widget, media_cfg)

    def _sync_media_provider_runtime(self, provider: object) -> None:
        """Rebind live media dependents to the active provider setting/runtime choice."""

        normalized = str(provider or "spotify").strip().lower() or "spotify"

        media_widget = self._widgets.get('media_widget') or self._widgets.get('media')
        if media_widget is not None and hasattr(media_widget, 'set_provider_runtime'):
            try:
                media_widget.set_provider_runtime(normalized)
            except Exception:
                logger.debug("[WIDGET_MANAGER] Failed to sync media provider runtime", exc_info=True)

        volume_widget = self._widgets.get('spotify_volume') or self._widgets.get('spotify_volume_widget')
        if volume_widget is not None and hasattr(volume_widget, 'set_provider_runtime'):
            try:
                volume_widget.set_provider_runtime(normalized)
            except Exception:
                logger.debug("[WIDGET_MANAGER] Failed to sync volume provider runtime", exc_info=True)

    def handle_media_provider_failover(self, provider: object, *, source: str = "runtime") -> None:
        """Persist a runtime media-provider auto-fallback through the shared settings path."""

        normalized = str(provider or "spotify").strip().lower() or "spotify"
        self._sync_media_provider_runtime(normalized)

        settings = self._settings_manager
        if settings is None:
            return

        widgets_cfg = settings.get('widgets', {}) or {}
        if not isinstance(widgets_cfg, Mapping):
            widgets_cfg = {}
        media_cfg = widgets_cfg.get('media', {}) or {}
        if not isinstance(media_cfg, Mapping):
            media_cfg = {}

        current = str(media_cfg.get('provider', 'spotify') or 'spotify').strip().lower() or 'spotify'
        if current == normalized:
            return

        updated_media_cfg = dict(media_cfg)
        updated_media_cfg['provider'] = normalized
        updated_widgets_cfg = dict(widgets_cfg)
        updated_widgets_cfg['media'] = updated_media_cfg

        logger.info(
            "[WIDGET_MANAGER] Persisting runtime media provider failover: %s -> %s (source=%s)",
            current,
            normalized,
            source,
        )
        settings.set('widgets', updated_widgets_cfg)
        settings.save()

    def _refresh_reddit_configs(self, widgets_config: Optional[Mapping[str, Any]] = None) -> None:
        """Apply latest reddit settings to live reddit widgets (reddit, reddit2)."""
        targets = [('reddit', self._widgets.get('reddit_widget')), ('reddit2', self._widgets.get('reddit2_widget'))]
        if all(w is None for _, w in targets):
            return

        cfg = widgets_config
        if cfg is None:
            if self._settings_manager is None:
                return
            cfg = self._settings_manager.get('widgets', {}) or {}
        if not isinstance(cfg, Mapping):
            return

        base_reddit_cfg = cfg.get('reddit', {}) if isinstance(cfg.get('reddit', {}), Mapping) else cfg.get('reddit', {})

        for key, widget in targets:
            if widget is None:
                continue
            reddit_cfg = cfg.get(key, {})
            if not isinstance(reddit_cfg, Mapping):
                continue
            model = RedditWidgetSettings.from_mapping(reddit_cfg, prefix=f"widgets.{key}")

            style_fallback = base_reddit_cfg if (key == 'reddit2' and isinstance(base_reddit_cfg, Mapping)) else None

            def inherit_style(field: str, default: Any) -> Any:
                if field in reddit_cfg:
                    return reddit_cfg.get(field)
                if isinstance(style_fallback, Mapping) and field in style_fallback:
                    return style_fallback.get(field)
                return default

            try:
                font_family = inherit_style('font_family', model.font_family)
                font_size = inherit_style('font_size', model.font_size)
                margin = inherit_style('margin', model.margin)
                header_logo_px_adjust = inherit_style('header_logo_px_adjust', model.header_logo_px_adjust)
                text_color = inherit_style('color', [255, 255, 255, 230])
                show_background = SettingsManager.to_bool(inherit_style('show_background', model.show_background), True)
                show_separators = SettingsManager.to_bool(inherit_style('show_separators', model.show_separators), True)
                show_refresh_spiral = SettingsManager.to_bool(
                    inherit_style('show_refresh_spiral', model.show_refresh_spiral),
                    True,
                )
                bg_color_value = inherit_style('bg_color', inherit_style('background_color', [35, 35, 35, 255]))
                bg_opacity_value = inherit_style('bg_opacity', model.background_opacity)
                border_color_value = inherit_style('border_color', [255, 255, 255, 255])
                border_opacity_value = inherit_style('border_opacity', model.border_opacity)

                if hasattr(widget, 'set_font_family'):
                    widget.set_font_family(font_family)
                if hasattr(widget, 'set_font_size'):
                    widget.set_font_size(int(font_size))
                if hasattr(widget, 'set_text_color'):
                    widget.set_text_color(parse_color_to_qcolor(text_color))
                if hasattr(widget, 'set_show_background'):
                    widget.set_show_background(show_background)
                if hasattr(widget, 'set_show_separators'):
                    widget.set_show_separators(show_separators)
                if hasattr(widget, 'set_show_refresh_spiral'):
                    widget.set_show_refresh_spiral(show_refresh_spiral)
                if hasattr(widget, 'set_background_color'):
                    widget.set_background_color(parse_color_to_qcolor(bg_color_value))
                if hasattr(widget, 'set_background_opacity'):
                    widget.set_background_opacity(float(bg_opacity_value))
                if hasattr(widget, 'set_background_border'):
                    border_qcolor = parse_color_to_qcolor(border_color_value, opacity_override=border_opacity_value)
                    if border_qcolor:
                        current_width = getattr(widget, '_bg_border_width', None)
                        widget.set_background_border(current_width if current_width is not None else widget.get_global_border_width(), border_qcolor)
                if hasattr(widget, 'set_margin'):
                    widget.set_margin(int(margin))
                if hasattr(widget, 'set_header_logo_px_adjust'):
                    widget.set_header_logo_px_adjust(int(header_logo_px_adjust))
            except Exception:
                logger.debug("[WIDGET_MANAGER] Failed to reapply reddit config for %s", key, exc_info=True)
    
    def show_widget(self, name: str) -> bool:
        """
        Show a specific widget.
        
        Args:
            name: Name of the widget to show
            
        Returns:
            True if widget was shown
        """
        widget = self._widgets.get(name)
        if widget is not None:
            try:
                widget.show()
                return True
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        return False
    
    def hide_widget(self, name: str) -> bool:
        """
        Hide a specific widget.
        
        Args:
            name: Name of the widget to hide
            
        Returns:
            True if widget was hidden
        """
        widget = self._widgets.get(name)
        if widget is not None:
            try:
                widget.hide()
                return True
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        return False
    
    def set_widget_geometry(self, name: str, x: int, y: int, width: int, height: int) -> bool:
        """
        Set widget geometry.
        
        Args:
            name: Widget name
            x, y: Position
            width, height: Size
            
        Returns:
            True if geometry was set
        """
        widget = self._widgets.get(name)
        if widget is not None:
            try:
                widget.setGeometry(x, y, width, height)
                return True
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        return False
    
    def register_fade_callback(self, name: str, callback: Callable) -> None:
        """
        Register a fade callback for a widget.
        
        Args:
            name: Widget name
            callback: Callback to invoke during fade
        """
        self._fade_callbacks[name] = callback
    
    def invoke_fade_callbacks(self, progress: float) -> None:
        """
        Invoke all registered fade callbacks.
        
        Args:
            progress: Fade progress (0.0 to 1.0)
        """
        for name, callback in self._fade_callbacks.items():
            try:
                callback(progress)
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
                if is_verbose_logging():
                    logger.debug(f"[WIDGET_MANAGER] Fade callback failed for {name}", exc_info=True)
    
    def raise_all_widgets(self) -> None:
        """Raise all registered widgets above the compositor.
        
        CRITICAL: Must be called SYNCHRONOUSLY after transition.start() returns,
        NOT via QTimer.singleShot(0, ...). Deferred raises allow the compositor
        to render frames before widgets are raised above it.
        """
        for name, widget in self._widgets.items():
            if widget is not None:
                try:
                    widget.raise_()
                    # Handle clock timezone labels
                    if hasattr(widget, '_tz_label') and widget._tz_label:
                        widget._tz_label.raise_()
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

    def position_spotify_visualizer(self, vis_widget, media_widget, parent_width: int, parent_height: int) -> None:
        """Position Spotify visualizer relative to media widget."""
        if vis_widget is None:
            return
        try:
            widgets_config: Mapping[str, Any] | None = None
            if self._settings_manager is not None:
                candidate = self._settings_manager.get('widgets', {}) or {}
                if isinstance(candidate, Mapping):
                    widgets_config = candidate

            custom_rect = getattr(vis_widget, "_custom_layout_local_rect", None)
            if (
                isinstance(custom_rect, QRect)
                and custom_rect.width() > 0
                and custom_rect.height() > 0
                and is_custom_position_selected_for_widget("spotify_visualizer", widgets_config)
            ):
                from widgets.spotify_visualizer.card_geometry import (
                    build_growth_map_from_widget,
                    resolve_custom_card_rect,
                    resolve_custom_card_size,
                )

                payload = getattr(vis_widget, "_custom_layout_visualizer_scale_payload", None)
                if not isinstance(payload, Mapping):
                    payload = {}
                resolved_size = None
                try:
                    anchor_media = getattr(vis_widget, "_anchor_media", None)
                    media_width = max(
                        10,
                        int(
                            anchor_media.geometry().width()
                            if anchor_media is not None
                            else custom_rect.width()
                        ),
                    )
                    resolved_size = resolve_custom_card_size(
                        mode_id=str(getattr(vis_widget, "_vis_mode_str", "spectrum") or "spectrum"),
                        media_width=media_width,
                        base_height=int(getattr(vis_widget, "_base_height", 80)),
                        growth_by_mode=build_growth_map_from_widget(vis_widget),
                        blob_width=float(getattr(vis_widget, "_blob_width", 1.0)),
                        width_scale=float(payload.get("width_scale", 1.0)),
                        height_scale=float(payload.get("height_scale", 1.0)),
                        maximum_envelope=False,
                    )
                except Exception:
                    logger.debug("[WIDGET_MANAGER] Failed to resolve adaptive custom visualizer size", exc_info=True)
                    resolved_size = None

                resolved_custom_rect = resolve_custom_card_rect(
                    custom_rect,
                    parent_width=parent_width,
                    parent_height=parent_height,
                    size=resolved_size,
                )
                if resolved_custom_rect.isEmpty():
                    return
                vis_widget.setGeometry(resolved_custom_rect)
                vis_widget.raise_()
                return

            if media_widget is None:
                return

            resolved_rect = self._resolve_spotify_visualizer_authored_rect(
                vis_widget,
                media_widget,
                parent_width=parent_width,
                parent_height=parent_height,
                widgets_config=widgets_config,
            )
            if resolved_rect is None or resolved_rect.isEmpty():
                return

            vis_widget.setGeometry(
                resolved_rect.x(),
                resolved_rect.y(),
                resolved_rect.width(),
                resolved_rect.height(),
            )
            vis_widget.raise_()
            if is_perf_metrics_enabled():
                logger.info(
                    "[SPOTIFY_VIS] Positioned visualizer widget geom=(%d,%d,%d,%d)",
                    resolved_rect.x(),
                    resolved_rect.y(),
                    resolved_rect.width(),
                    resolved_rect.height(),
                )
            
            # NOTE: The visualizer card and its GL overlay are intentionally
            # NOT registered with PixelShiftManager.  The card is positioned
            # relative to the media widget (which handles pixel shift via
            # BaseOverlayWidget), so it inherits the shift automatically.
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

    def position_spotify_volume(self, vol_widget, media_widget, parent_width: int, parent_height: int) -> None:
        """Position Spotify volume slider beside media widget."""
        if vol_widget is None:
            return
        try:
            def _resolve_authored_size() -> tuple[int, int]:
                width = max(vol_widget.minimumWidth(), 32)
                if media_widget is None:
                    height = max(vol_widget.minimumHeight(), vol_widget.height())
                    return width, height
                media_geom = media_widget.geometry()
                card_height = media_geom.height()
                height = max(vol_widget.minimumHeight(), card_height - 8)
                height = min(height, card_height)
                return width, height

            widgets_config: Mapping[str, Any] | None = None
            if self._settings_manager is not None:
                candidate = self._settings_manager.get('widgets', {}) or {}
                if isinstance(candidate, Mapping):
                    widgets_config = candidate

            custom_rect = getattr(vol_widget, "_custom_layout_local_rect", None)
            if (
                isinstance(custom_rect, QRect)
                and custom_rect.width() > 0
                and custom_rect.height() > 0
                and is_custom_position_selected_for_widget("spotify_volume", widgets_config)
            ):
                width = max(24, int(custom_rect.width()))
                height = max(120, int(custom_rect.height()))
                x = max(0, min(int(custom_rect.x()), max(0, parent_width - width)))
                y = max(0, min(int(custom_rect.y()), max(0, parent_height - height)))
                vol_widget.setGeometry(x, y, width, height)
                if vol_widget.isVisible():
                    vol_widget.raise_()
                return

            if media_widget is None:
                return

            media_geom = media_widget.geometry()
            if media_geom.width() <= 0 or media_geom.height() <= 0:
                return
            
            gap = 16
            width, height = _resolve_authored_size()
            card_height = media_geom.height()
            
            space_left = max(0, media_geom.left())
            space_right = max(0, parent_width - media_geom.right())
            
            if space_right >= space_left:
                x = media_geom.right() + gap
                if x + width > parent_width:
                    x = max(0, parent_width - width)
            else:
                x = media_geom.left() - gap - width
                x = max(0, x)
            
            y = media_geom.top() + max(0, (card_height - height) // 2)
            y = max(0, min(y, max(0, parent_height - height)))
            
            vol_widget.setGeometry(x, y, width, height)
            if vol_widget.isVisible():
                vol_widget.raise_()
            if is_perf_metrics_enabled():
                logger.info(
                    "[SPOTIFY_VOL] Positioned volume widget geom=(%d,%d,%d,%d)",
                    x,
                    y,
                    width,
                    height,
                )
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

    def apply_widget_stacking(self, widget_list: list, widgets_config: Optional[Mapping[str, Any]] = None) -> None:
        """Apply authored stacking offsets across shared left/center/right columns."""
        from PySide6.QtCore import QPoint

        global_cfg = {}
        if isinstance(widgets_config, Mapping):
            candidate = widgets_config.get("global", {})
            if isinstance(candidate, Mapping):
                global_cfg = candidate
        stacking_enabled = SettingsManager.to_bool(
            global_cfg.get("stacking_enabled", False),
            False,
        )
        if not stacking_enabled:
            for widget, _attr_name in widget_list:
                if widget is not None and hasattr(widget, "set_stack_offset"):
                    widget.set_stack_offset(QPoint(0, 0))
            if is_geometry_logging_enabled():
                logger.info(
                    "[STACK] screen=%s stacking disabled; clearing offsets for %d widgets",
                    getattr(self._parent, "screen_index", "?"),
                    len(widget_list),
                )
            return

        reserved_obstacle = self._build_reserved_media_visualizer_stack_obstacle(
            widgets_config,
        )
        participants: list[tuple[Any, str, StackParticipant]] = []
        for i, (widget, attr_name) in enumerate(widget_list):
            if widget is None:
                continue
            if (
                reserved_obstacle is not None
                and attr_name == "media_widget"
                and self._get_widget_position_key(widget)
                and get_stack_lane(self._get_widget_position_key(widget)) == reserved_obstacle.lane
            ):
                if hasattr(widget, 'set_stack_offset'):
                    widget.set_stack_offset(QPoint(0, 0))
                continue
            descriptor = get_widget_runtime_descriptor_by_attr_name(attr_name)
            if (
                descriptor is not None
                and descriptor.supports_custom_position_slot
                and is_custom_position_selected_for_widget(descriptor.widget_id, widgets_config)
            ):
                if hasattr(widget, 'set_stack_offset'):
                    widget.set_stack_offset(QPoint(0, 0))
                continue
            pos_key = self._get_widget_position_key(widget)
            if not pos_key:
                continue
            lane = get_stack_lane(pos_key)
            band = get_stack_band(pos_key)
            if lane is None or band is None:
                continue
            base_y = self._get_widget_stack_base_y(widget)
            participants.append(
                (
                    widget,
                    attr_name,
                    StackParticipant(
                        key=attr_name,
                        lane=lane,
                        band=band,
                        base_y=base_y,
                        height=self._get_widget_stack_height(widget),
                        order=i,
                    ),
                )
            )

        if not participants:
            return

        spacing = 10
        try:
            container_height = int(self._parent.height()) if self._parent is not None else 1080
        except Exception:
            container_height = 1080
        plan = build_stack_plan(
            [participant for _widget, _attr_name, participant in participants],
            obstacles=[reserved_obstacle] if reserved_obstacle is not None else None,
            container_height=container_height,
            spacing=spacing,
        )

        lane_reports: dict[str, list[str]] = {}
        for widget, attr_name, participant in participants:
            placement = plan.placements.get(attr_name)
            offset_y = placement.offset_y if placement is not None else 0
            desired_y = placement.desired_y if placement is not None else participant.base_y
            if widget is not None and hasattr(widget, 'set_stack_offset'):
                widget.set_stack_offset(QPoint(0, offset_y))
            if is_geometry_logging_enabled():
                lane_reports.setdefault(participant.lane, []).append(
                    f"{attr_name}:base={participant.base_y}:desired={desired_y}:h={participant.height}:off={offset_y}"
                )

        if is_geometry_logging_enabled():
            for lane, report in lane_reports.items():
                if reserved_obstacle is not None and reserved_obstacle.lane == lane:
                    report.append(
                        f"{reserved_obstacle.key}:fixed={reserved_obstacle.top_y}:h={reserved_obstacle.height}"
                    )
                logger.info(
                    "[STACK] screen=%s lane=%s fits=%s spacing=%s widgets=%s",
                    getattr(self._parent, "screen_index", "?"),
                    lane,
                    plan.lane_fit.get(lane, True),
                    plan.lane_spacing.get(lane, spacing),
                    ", ".join(report),
                )

    def _get_widget_position_key(self, widget) -> str:
        """Get normalized position key from widget."""
        try:
            if hasattr(widget, '_position'):
                pos = widget._position
                if hasattr(pos, 'name'):
                    return pos.name.lower()
                return str(pos).lower().replace(' ', '_')
            if hasattr(widget, 'get_position'):
                pos = widget.get_position()
                if hasattr(pos, 'name'):
                    return pos.name.lower()
                return str(pos).lower().replace(' ', '_')
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        return ""

    def _get_widget_stack_base_y(self, widget) -> int:
        """Return canonical authored/base Y for the widget's current anchor/size."""
        position_key = self._get_widget_position_key(widget)
        if position_key and self._parent is not None:
            try:
                parent_height = int(self._parent.height())
            except Exception:
                parent_height = 0
            if parent_height > 0:
                margin = 20
                try:
                    if hasattr(widget, "get_margin") and callable(widget.get_margin):
                        margin = int(widget.get_margin())
                    elif hasattr(widget, "_margin"):
                        margin = int(getattr(widget, "_margin"))
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
                height = self._get_widget_stack_height(widget)
                try:
                    visual_offset_y = 0
                    visual_offset = getattr(widget, "_compute_visual_offset", None)
                    if callable(visual_offset):
                        offset = visual_offset()
                        if hasattr(offset, "y"):
                            visual_offset_y = int(offset.y())
                    if "top" in position_key:
                        base_y = margin
                    elif "bottom" in position_key:
                        base_y = parent_height - height - margin
                    else:
                        base_y = (parent_height - height) // 2
                    base_y += visual_offset_y

                    min_visible = 10
                    max_y = parent_height - min_visible
                    min_y = min_visible - height
                    return max(min_y, min(base_y, max_y))
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        # Fallback for widgets that cannot resolve canonical authored anchors.
        try:
            base_y = int(widget.y())
        except Exception:
            base_y = 0
        try:
            stack_offset = getattr(widget, "_stack_offset", None)
            if stack_offset is not None and hasattr(stack_offset, "y"):
                base_y -= int(stack_offset.y())
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        try:
            pixel_shift = getattr(widget, "_pixel_shift_offset", None)
            if pixel_shift is not None and hasattr(pixel_shift, "y"):
                base_y -= int(pixel_shift.y())
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        return base_y

    def _get_widget_stack_height(self, widget) -> int:
        """Get widget height for stacking calculations."""
        try:
            measured_heights: list[int] = []
            if hasattr(widget, 'get_stacking_footprint_size'):
                try:
                    footprint = widget.get_stacking_footprint_size()
                    if footprint is not None and hasattr(footprint, "height"):
                        footprint_height = int(footprint.height())
                        if footprint_height > 0:
                            measured_heights.append(footprint_height)
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            actual_height = int(widget.height()) if widget.height() > 0 else 0
            if actual_height > 0:
                measured_heights.append(actual_height)
            hint = widget.sizeHint()
            if hint.isValid() and hint.height() > 0:
                measured_heights.append(int(hint.height()))
            try:
                min_height = int(widget.minimumHeight())
                if min_height > 0:
                    measured_heights.append(min_height)
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            if not measured_heights and hasattr(widget, 'get_bounding_size'):
                try:
                    bounding_height = int(widget.get_bounding_size().height())
                    if bounding_height > 0:
                        measured_heights.append(bounding_height)
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            if measured_heights:
                resolved = measured_heights[0]
                if is_geometry_logging_enabled():
                    logger.info(
                        "[STACK] measure widget=%s heights=%s resolved=%s",
                        getattr(widget, "_overlay_name", widget.__class__.__name__),
                        measured_heights,
                        resolved,
                    )
                return resolved
            return 100
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            return 100

    def _resolve_spotify_visualizer_authored_rect(
        self,
        vis_widget,
        media_widget,
        *,
        parent_width: int,
        parent_height: int,
        widgets_config: Mapping[str, Any] | None,
    ) -> Optional[QRect]:
        """Resolve the non-CUSTOM authored runtime rect for the visualizer."""
        if vis_widget is None or media_widget is None:
            return None
        if is_custom_position_selected_for_widget("spotify_visualizer", widgets_config):
            return None
        if is_custom_position_selected_for_widget("media", widgets_config):
            return None
        try:
            from widgets.spotify_visualizer.card_geometry import (
                build_growth_map_from_widget,
                resolve_card_metrics,
                resolve_relative_card_placement,
            )

            media_geom = media_widget.geometry()
            if media_geom.width() <= 0 or media_geom.height() <= 0:
                return None

            vis_mode = getattr(vis_widget, '_vis_mode_str', 'spectrum')
            metrics = resolve_card_metrics(
                vis_mode,
                int(getattr(vis_widget, "_base_height", 80)),
                build_growth_map_from_widget(vis_widget),
            )

            position_name = ""
            if hasattr(media_widget, "_position"):
                pos = media_widget._position
                if hasattr(pos, "name"):
                    position_name = pos.name.upper()
                else:
                    position_name = str(pos).upper()

            placement = resolve_relative_card_placement(
                media_rect=media_geom,
                parent_width=parent_width,
                parent_height=parent_height,
                mode_id=vis_mode,
                card_height=metrics.preferred_height,
                position_name=position_name,
                blob_width=float(getattr(vis_widget, "_blob_width", 1.0)),
            )
            return QRect(
                int(placement.x),
                int(placement.y),
                int(placement.width),
                int(placement.height),
            )
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to resolve visualizer authored rect", exc_info=True)
            return None

    def _build_reserved_media_visualizer_stack_obstacle(
        self,
        widgets_config: Mapping[str, Any] | None,
    ) -> Optional[StackObstacle]:
        """Return fixed authored-lane occupancy for the follow-media visualizer + media block."""
        if self._parent is None:
            return None
        try:
            vis_widget = getattr(self._parent, "spotify_visualizer_widget", None)
            media_widget = getattr(self._parent, "media_widget", None)
            if vis_widget is None or media_widget is None:
                return None
            parent_width = int(self._parent.width())
            parent_height = int(self._parent.height())
            if parent_width <= 0 or parent_height <= 0:
                return None
            rect = self._resolve_spotify_visualizer_authored_rect(
                vis_widget,
                media_widget,
                parent_width=parent_width,
                parent_height=parent_height,
                widgets_config=widgets_config,
            )
            if rect is None or rect.isEmpty():
                return None

            media_pos_key = self._get_widget_position_key(media_widget)
            lane = get_stack_lane(media_pos_key)
            if lane is None:
                return None
            media_geom = media_widget.geometry()
            if media_geom.width() <= 0 or media_geom.height() <= 0:
                return None
            top = min(int(rect.top()), int(media_geom.top()))
            bottom = max(int(rect.bottom()), int(media_geom.bottom()))
            height = max(0, bottom - top + 1)
            return StackObstacle(
                key=_STACK_RESERVED_MEDIA_VISUALIZER_KEY,
                lane=lane,
                top_y=top,
                height=height,
            )
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to build reserved media/visualizer stack obstacle", exc_info=True)
            return None
    
    def cleanup(self) -> None:
        """Clean up all managed widgets."""
        self.prepare_for_runtime_pause()
        
        # Use lifecycle cleanup for widgets that support it
        for name, widget in list(self._widgets.items()):
            if widget is not None:
                try:
                    if hasattr(widget, 'cleanup') and callable(widget.cleanup):
                        widget.cleanup()
                except Exception:
                    logger.debug("[WIDGET_MANAGER] Failed to cleanup %s", name, exc_info=True)
        
        self._widgets.clear()
        self._fade_callbacks.clear()
        logger.debug("[WIDGET_MANAGER] Cleanup complete")

    def prepare_for_runtime_pause(self) -> None:
        """Suppress late runtime work before displays/compositor are paused or torn down.

        This intentionally does not invoke the dormant activate/deactivate lifecycle
        system. It only detaches live settings updates, stops deferred raise work,
        and asks widgets with explicit stop hooks to cease producing runtime work.
        """
        self._detach_settings_manager()
        self._pending_spotify_visibility_sync = False
        self._spotify_secondary_fade_starters = []
        self._pending_raise = False

        if self._raise_timer is not None:
            try:
                self._raise_timer.stop()
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            self._raise_timer = None

        for name, widget in list(self._widgets.items()):
            if widget is None:
                continue
            try:
                stopper = getattr(widget, "stop", None)
                if callable(stopper):
                    stopper()
            except Exception:
                logger.debug("[WIDGET_MANAGER] Failed to stop %s during runtime pause prep", name, exc_info=True)

    # =========================================================================
    # Lifecycle Integration (Dec 2025)
    # =========================================================================

    def initialize_widget(self, name: str) -> bool:
        """Initialize a widget using the new lifecycle system.
        
        Args:
            name: Name of the widget to initialize
            
        Returns:
            True if widget was initialized successfully
        """
        widget = self._widgets.get(name)
        if widget is None:
            return False
        
        try:
            if hasattr(widget, 'initialize') and callable(widget.initialize):
                widget.initialize()
                logger.debug("[LIFECYCLE] Widget %s initialized via WidgetManager", name)
                return True
        except Exception:
            logger.debug("[LIFECYCLE] Failed to initialize %s", name, exc_info=True)
        return False

    def activate_widget(self, name: str) -> bool:
        """Activate a widget using the new lifecycle system.
        
        Args:
            name: Name of the widget to activate
            
        Returns:
            True if widget was activated successfully
        """
        widget = self._widgets.get(name)
        if widget is None:
            return False
        
        try:
            if hasattr(widget, 'activate') and callable(widget.activate):
                widget.activate()
                logger.debug("[LIFECYCLE] Widget %s activated via WidgetManager", name)
                return True
        except Exception:
            logger.debug("[LIFECYCLE] Failed to activate %s", name, exc_info=True)
        return False

    def deactivate_widget(self, name: str) -> bool:
        """Deactivate a widget using the new lifecycle system.
        
        Args:
            name: Name of the widget to deactivate
            
        Returns:
            True if widget was deactivated successfully
        """
        widget = self._widgets.get(name)
        if widget is None:
            return False
        
        try:
            if hasattr(widget, 'deactivate') and callable(widget.deactivate):
                widget.deactivate()
                logger.debug("[LIFECYCLE] Widget %s deactivated via WidgetManager", name)
                return True
        except Exception:
            logger.debug("[LIFECYCLE] Failed to deactivate %s", name, exc_info=True)
        return False

    def cleanup_widget(self, name: str) -> bool:
        """Cleanup a widget using the new lifecycle system.
        
        Args:
            name: Name of the widget to cleanup
            
        Returns:
            True if widget was cleaned up successfully
        """
        widget = self._widgets.get(name)
        if widget is None:
            return False
        
        try:
            if hasattr(widget, 'cleanup') and callable(widget.cleanup):
                widget.cleanup()
                logger.debug("[LIFECYCLE] Widget %s cleaned up via WidgetManager", name)
                return True
        except Exception:
            logger.debug("[LIFECYCLE] Failed to cleanup %s", name, exc_info=True)
        return False

    def initialize_all_widgets(self) -> int:
        """Initialize all managed widgets using the new lifecycle system.
        
        Returns:
            Number of widgets successfully initialized
        """
        count = 0
        for name in list(self._widgets.keys()):
            if self.initialize_widget(name):
                count += 1
        logger.debug("[LIFECYCLE] Initialized %d widgets", count)
        return count

    def activate_all_widgets(self) -> int:
        """Activate all managed widgets using the new lifecycle system.
        
        NOTE: This method is DORMANT as of Jan 2026. The legacy start() system
        is used instead (see setup_all_widgets). Lifecycle methods exist in all
        widgets but are not called. This is intentional - the lifecycle system
        is complete but kept dormant to reduce regression risk. Migration to
        lifecycle activation is planned for v1.3 after stabilization.
        
        Returns:
            Number of widgets successfully activated
        """
        count = 0
        for name in list(self._widgets.keys()):
            if self.activate_widget(name):
                count += 1
        logger.debug("[LIFECYCLE] Activated %d widgets", count)
        return count

    def deactivate_all_widgets(self) -> int:
        """Deactivate all managed widgets using the new lifecycle system.
        
        Returns:
            Number of widgets successfully deactivated
        """
        count = 0
        for name in list(self._widgets.keys()):
            if self.deactivate_widget(name):
                count += 1
        logger.debug("[LIFECYCLE] Deactivated %d widgets", count)
        return count

    def get_widget_lifecycle_state(self, name: str) -> Optional[str]:
        """Get the lifecycle state of a widget.
        
        Args:
            name: Name of the widget
            
        Returns:
            Lifecycle state name or None if widget not found or doesn't support lifecycle
        """
        widget = self._widgets.get(name)
        if widget is None:
            return None
        
        try:
            if hasattr(widget, '_lifecycle_state'):
                state = widget._lifecycle_state
                if hasattr(state, 'name'):
                    return state.name
                return str(state)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        return None

    def get_all_lifecycle_states(self) -> Dict[str, str]:
        """Get lifecycle states of all managed widgets.
        
        Returns:
            Dict mapping widget name to lifecycle state name
        """
        states = {}
        for name in self._widgets.keys():
            state = self.get_widget_lifecycle_state(name)
            if state is not None:
                states[name] = state
        return states

    # =========================================================================
    # Widget Positioning (Dec 2025)
    # =========================================================================

    def set_container_size(self, width: int, height: int) -> None:
        """Set the container size for widget positioning.
        
        Args:
            width: Container width in pixels
            height: Container height in pixels
        """
        from PySide6.QtCore import QSize
        self._positioner.set_container_size(QSize(width, height))

    def get_positioner(self) -> WidgetPositioner:
        """Get the widget positioner for advanced positioning operations."""
        return self._positioner

    def position_widget_by_anchor(self, name: str, anchor: PositionAnchor, margin: int = 20) -> bool:
        """Position a widget using the centralized positioner.
        
        Args:
            name: Name of the widget to position
            anchor: Position anchor (e.g., TOP_LEFT, BOTTOM_RIGHT)
            margin: Margin from screen edge
            
        Returns:
            True if widget was positioned successfully
        """
        widget = self._widgets.get(name)
        if widget is None:
            return False
        
        try:
            self._positioner.position_widget(widget, anchor, margin_x=margin, margin_y=margin)
            return True
        except Exception:
            logger.debug("[POSITIONER] Failed to position %s", name, exc_info=True)
        return False

    # =========================================================================
    # Transient Opacity-Effect Refresh
    # =========================================================================

    def invalidate_overlay_effects(self, reason: str) -> None:
        """Delegates to rendering.widget_effects."""
        from rendering.widget_effects import invalidate_overlay_effects
        invalidate_overlay_effects(self, reason)

    # =========================================================================
    # Overlay Fade Coordination
    # =========================================================================

    def reset_fade_coordination(self) -> None:
        """Reset fade coordination state for a new widget setup cycle."""
        if hasattr(self, '_fade_coordinator') and self._fade_coordinator is not None:
            self._fade_coordinator.reset(clear_participants=True)
        self._expected_overlays = set()
        self._spotify_secondary_fade_starters = []
        self._spotify_overlay_prewarm_attempted = False
        self._spotify_overlay_prewarmed = False
        self._mirror_parent_overlay_state()
        parent = self._parent
        if parent is not None:
            try:
                parent._overlay_fade_started = bool(self._compositor_ready)
                parent._spotify_secondary_not_before_ts = 0.0
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        if self._compositor_ready and hasattr(self, '_fade_coordinator') and self._fade_coordinator is not None:
            try:
                self._fade_coordinator.signal_compositor_ready()
            except Exception:
                logger.debug("[WIDGET_MANAGER] Failed to re-prime fade coordinator for ready compositor", exc_info=True)

    def set_expected_overlays(self, expected: Set[str]) -> None:
        """Set the overlays expected to participate in coordinated fade.
        
        Args:
            expected: Set of overlay names (e.g., {"weather", "media", "reddit"})
        """
        self._expected_overlays = set(expected)
        self._mirror_parent_overlay_state()
        for name in expected:
            self._fade_coordinator.register_participant(name)

    def add_expected_overlay(self, name: str) -> None:
        """Add an overlay to the expected set."""
        self._expected_overlays.add(name)
        self._mirror_parent_overlay_state()
        self._fade_coordinator.register_participant(name)

    def request_overlay_fade_sync(self, overlay_name: str, starter: Callable[[], None]) -> None:
        """Register an overlay's initial fade so all widgets can fade together.

        Args:
            overlay_name: Name of the overlay requesting fade
            starter: Callback to start the fade animation
        """
        request_ts = time.monotonic()
        screen_idx = getattr(self._parent, "screen_index", "?")
        compositor_ready = bool(self._compositor_ready)

        parent_pending = None
        if self._parent is not None:
            try:
                parent_pending = getattr(self._parent, "_overlay_fade_pending", None)
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
                parent_pending = None

        def _starter_wrapper() -> None:
            reveal_delay_ms = max(0.0, (time.monotonic() - request_ts) * 1000.0)
            first_frame_delay_ms = None
            if self._parent is not None:
                try:
                    committed_ts = getattr(self._parent, "_first_frame_committed_ts", None)
                    if isinstance(committed_ts, (int, float)) and committed_ts > 0:
                        first_frame_delay_ms = max(
                            0.0,
                            (time.monotonic() - float(committed_ts)) * 1000.0,
                        )
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

            if isinstance(parent_pending, dict):
                try:
                    parent_pending.pop(overlay_name, None)
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

            logger.info(
                "[LIFECYCLE] Overlay reveal starter running "
                "(screen=%s, overlay=%s, queued_ms=%.2f, since_first_frame_ms=%s, compositor_ready=%s)",
                screen_idx,
                overlay_name,
                reveal_delay_ms,
                f"{first_frame_delay_ms:.2f}" if first_frame_delay_ms is not None else "N/A",
                self._compositor_ready,
            )
            starter()

        if isinstance(parent_pending, dict):
            try:
                parent_pending[overlay_name] = _starter_wrapper
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        logger.info(
            "[LIFECYCLE] Overlay ready-for-display requested "
            "(screen=%s, overlay=%s, compositor_ready=%s, expected=%s, pending_before=%d)",
            screen_idx,
            overlay_name,
            compositor_ready,
            sorted(self._expected_overlays),
            len(self._fade_coordinator.describe().get("pending", [])),
        )

        started_immediately = self._fade_coordinator.request_fade(overlay_name, _starter_wrapper)
        logger.debug(
            "[FADE_COORD] %s fade request registered (started_immediately=%s)",
            overlay_name,
            started_immediately,
        )

    def register_spotify_secondary_fade(self, starter: Callable[[], None]) -> None:
        """Register a Spotify second-wave fade to run after primary overlays."""
        try:
            policy = self._get_overlay_startup_policy()
            direct_delay_ms = int(policy.spotify_secondary_direct_delay_ms)
        except Exception:
            direct_delay_ms = 1200

        if not self._expected_overlays:
            self._prewarm_spotify_visualizer_overlay()
            self._mark_parent_spotify_secondary_not_before(
                direct_delay_ms,
            )
            logger.debug(
                "[SPOTIFY_SECONDARY] no primary overlays registered; using direct delay=%sms",
                direct_delay_ms,
            )
            try:
                QTimer.singleShot(direct_delay_ms, starter)
            except Exception as e:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
                try:
                    starter()
                except Exception as inner:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", inner)
            return

        if not self._compositor_ready:
            self._spotify_secondary_fade_starters.append(starter)
            logger.debug(
                "[SPOTIFY_SECONDARY] queued starter until compositor ready (expected=%s, queued=%d)",
                sorted(self._expected_overlays),
                len(self._spotify_secondary_fade_starters),
            )
            return

        self._prewarm_spotify_visualizer_overlay()
        self._mark_parent_spotify_secondary_not_before(
            direct_delay_ms,
        )
        logger.debug(
            "[SPOTIFY_SECONDARY] compositor already ready; using direct delay=%sms",
            direct_delay_ms,
        )
        try:
            QTimer.singleShot(direct_delay_ms, starter)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            try:
                starter()
            except Exception as inner:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", inner)

    def _queue_spotify_visibility_sync(self, media_widget: Optional[MediaWidget]) -> None:
        if not media_widget or self._pending_spotify_visibility_sync:
            return

        notify = getattr(media_widget, "_notify_spotify_widgets_visibility", None)
        if not callable(notify):
            return

        self._pending_spotify_visibility_sync = True

        def _run() -> None:
            try:
                logger.debug(
                    "[SPOTIFY_DIAG] running media visibility sync (visible=%s)",
                    media_widget.isVisible(),
                )
                notify()
            except Exception as exc:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", exc)
            finally:
                self._pending_spotify_visibility_sync = False

        try:
            QTimer.singleShot(0, _run)
        except Exception:
            _run()

    def sync_spotify_dependents_for_media_widget(self, media_widget: Optional[MediaWidget]) -> None:
        """Sync all Spotify dependents anchored to *media_widget* across displays."""

        if media_widget is None:
            return

        try:
            instances = get_coordinator().get_all_instances()
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to enumerate displays for Spotify dependent sync", exc_info=True)
            instances = []

        if self._parent is not None and self._parent not in instances:
            instances.append(self._parent)

        seen: set[int] = set()
        for instance in instances:
            for attr_name in ("spotify_visualizer_widget", "spotify_volume_widget", "mute_button_widget"):
                widget = getattr(instance, attr_name, None)
                if widget is None or id(widget) in seen:
                    continue
                seen.add(id(widget))
                if getattr(widget, "_anchor_media", None) is not media_widget:
                    continue
                sync = getattr(widget, "sync_visibility_with_anchor", None)
                if not callable(sync):
                    continue
                try:
                    sync()
                except Exception:
                    logger.debug("[WIDGET_MANAGER] Failed to sync %s with media anchor", attr_name, exc_info=True)

    def _register_spotify_secondary_fade(self, widget: Optional[QWidget]) -> None:
        if widget is None:
            return
        try:
            setattr(widget, "_spotify_secondary_stage_registered", True)
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to mark widget as secondary-stage registered", exc_info=True)

        anchor = getattr(widget, "_anchor_media", None)
        max_deferrals = 20

        def _run_sync() -> None:
            try:
                widget.objectName()
            except RuntimeError:
                return
            try:
                begin_secondary = getattr(widget, "begin_spotify_secondary_stage", None)
                if callable(begin_secondary):
                    begin_secondary()
                    return
                sync = getattr(widget, "sync_visibility_with_anchor", None)
                if callable(sync):
                    sync()
            except Exception as exc:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", exc)

        def _starter(attempt: int = 0) -> None:
            # Guard: widget may have been destroyed during settings restart
            try:
                widget.objectName()
            except RuntimeError:
                return
            try:
                anchor_visible = True
                if anchor is not None and hasattr(anchor, "isVisible"):
                    anchor_visible = bool(anchor.isVisible())
            except Exception as exc:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", exc)
                anchor_visible = True

            if not anchor_visible and attempt < max_deferrals:
                delay_ms = min(1000, 200 + attempt * 100)
                if is_perf_metrics_enabled():
                    logger.debug(
                        "[SPOTIFY_DIAG] deferring secondary fade for %s (anchor hidden, attempt=%s, delay=%sms)",
                        widget.objectName() or type(widget).__name__,
                        attempt + 1,
                        delay_ms,
                    )
                QTimer.singleShot(delay_ms, lambda: _starter(attempt + 1))
                return

            if not anchor_visible and is_perf_metrics_enabled():
                logger.debug(
                    "[SPOTIFY_DIAG] anchor still hidden after deferrals, forcing fade for %s",
                    widget.objectName() or type(widget).__name__,
                )

            if is_perf_metrics_enabled():
                logger.debug(
                    "[SPOTIFY_DIAG] secondary fade starter running for %s",
                    widget.objectName() or type(widget).__name__,
                )
            _run_sync()

        if is_perf_metrics_enabled():
            logger.debug(
                "[SPOTIFY_DIAG] registering secondary fade for %s (screen=%s)",
                widget.objectName() or type(widget).__name__,
                getattr(self._parent, "screen_index", "?"),
            )
        self.register_spotify_secondary_fade(_starter)

    # =========================================================================
    # Widget Factory Methods (Phase 2 - Jan 2026)
    # Legacy create_*_widget methods removed - now using WidgetFactoryRegistry
    # See rendering/widget_factories.py for ClockWidgetFactory, WeatherWidgetFactory,
    # MediaWidgetFactory, RedditWidgetFactory implementations
    # =========================================================================

    # NOTE: create_clock_widget, create_weather_widget, create_media_widget,
    # create_reddit_widget have been removed. setup_all_widgets() now uses
    # the WidgetFactoryRegistry for these widgets. Spotify widgets still use
    # direct methods below due to complex media widget anchoring logic.

    def setup_all_widgets(
        self,
        settings_manager: SettingsManager,
        screen_index: int,
        thread_manager: Optional["ThreadManager"] = None,
    ) -> dict:
        """Delegates to rendering.widget_setup_all."""
        from rendering.widget_setup_all import setup_all_widgets
        return setup_all_widgets(self, settings_manager, screen_index, thread_manager)

    def create_spotify_volume_widget(
        self,
        widgets_config: dict,
        shadows_config: dict,
        screen_index: int,
        thread_manager: Optional["ThreadManager"] = None,
        media_widget: Optional[MediaWidget] = None,
    ) -> Optional[SpotifyVolumeWidget]:
        """Delegates to rendering.spotify_widget_creators."""
        from rendering.spotify_widget_creators import create_spotify_volume_widget
        return create_spotify_volume_widget(
            self, widgets_config, shadows_config, screen_index, thread_manager, media_widget,
        )

    def create_spotify_visualizer_widget(
        self,
        widgets_config: dict,
        shadows_config: dict,
        screen_index: int,
        thread_manager: Optional["ThreadManager"] = None,
        media_widget: Optional[MediaWidget] = None,
    ) -> Optional[SpotifyVisualizerWidget]:
        """Delegates to rendering.spotify_widget_creators."""
        from rendering.spotify_widget_creators import create_spotify_visualizer_widget
        return create_spotify_visualizer_widget(
            self, widgets_config, shadows_config, screen_index, thread_manager, media_widget,
        )

    def create_mute_button_widget(
        self,
        widgets_config: dict,
        screen_index: int,
        thread_manager: Optional["ThreadManager"] = None,
        media_widget: Optional[MediaWidget] = None,
    ):
        """Delegates to rendering.spotify_widget_creators."""
        from rendering.spotify_widget_creators import create_mute_button_widget
        return create_mute_button_widget(
            self, widgets_config, screen_index, thread_manager, media_widget,
        )
