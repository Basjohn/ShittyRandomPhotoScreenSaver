"""
Widget Manager - Extracted from DisplayWidget for better separation of concerns.

Manages overlay widget lifecycle, positioning, visibility, and Z-order.
"""
from __future__ import annotations

from contextlib import nullcontext
from functools import partial
import time
from typing import Any, Callable, Dict, List, Optional, Set, TYPE_CHECKING, Mapping
import weakref

from PySide6.QtCore import QPoint, QRect, QSize, QTimer
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
    get_layout_edit_runtime_descriptors,
    is_custom_position_selected_for_widget,
)
from core.media.provider_registry import normalize_provider_id, preserve_provider_setting
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
from rendering.widget_runtime_manager import WidgetRuntimeManager
from widgets.base_overlay_widget import BaseOverlayWidget

if TYPE_CHECKING:
    from rendering.display_widget import DisplayWidget
    from core.threading.manager import ThreadManager

logger = get_logger(__name__)


_STACK_RESERVED_MEDIA_VISUALIZER_KEY = "__reserved_spotify_media_visualizer"
_CRITICAL_GL_STARTUP_HOLD = "critical_gl_startup"
_CUSTOM_LAYOUT_REAPPLY_SUFFIXES: tuple[str, ...] = (
    ".position",
    ".position2",
    ".monitor",
    ".monitor_index",
    ".monitor_combo",
    ".custom_position",
)


def _dispatch_spotify_secondary_attempt(
    manager_ref: "weakref.ReferenceType[WidgetManager]",
    widget_ref: "weakref.ReferenceType[QWidget]",
    anchor_ref: "weakref.ReferenceType[QWidget] | None",
    registration_generation: int,
    manager_id: int,
    attempt: int,
) -> None:
    """Resolve weak runtime owners and deliver one secondary-stage attempt."""

    manager = manager_ref()
    widget = widget_ref()
    if manager is None or widget is None:
        return
    manager._run_spotify_secondary_fade_attempt(
        widget,
        anchor_ref,
        registration_generation=registration_generation,
        manager_id=manager_id,
        attempt=attempt,
    )


def _dispatch_widget_manager_callback(
    manager_ref: "weakref.ReferenceType[WidgetManager]",
    method_name: str,
    *args,
    **kwargs,
):
    """Invoke a WidgetManager signal callback without a strong manager edge."""

    manager = manager_ref()
    if manager is None:
        return None
    callback = getattr(manager, method_name, None)
    if not callable(callback):
        return None
    return callback(*args, **kwargs)


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
        self._runtime_generation = getattr(parent, "_runtime_generation", None)
        self._resource_manager = resource_manager
        
        # Widget references
        self._widgets: Dict[str, QWidget] = {}

        # Phase-E1 presentation-neutral runtime owner. Owns capability admission
        # (dependency-aware) and lifecycle routing; this manager delegates to it
        # and keeps thin wrappers for its public API. Constructed after the
        # widget registry so the owner can route over it.
        self._runtime_manager: Optional[WidgetRuntimeManager] = WidgetRuntimeManager(self)

        # Rate limiting for raise operations
        self._last_raise_time: float = 0.0
        self._pending_raise: bool = False
        self._raise_timer: Optional[QTimer] = None
        
        # Fade callbacks
        self._fade_callbacks: Dict[str, Callable] = {}
        
        # Fade coordination - centralized via FadeCoordinator
        self._fade_coordinator: Optional[FadeCoordinator] = FadeCoordinator(
            screen_index=getattr(parent, "screen_index", 0)
        )
        self._fade_coordinator.add_startup_hold(_CRITICAL_GL_STARTUP_HOLD)
        self._fade_coordinator.add_completion_callback(
            self._on_startup_fades_complete
        )
        self._expected_overlays: set[str] = set()
        self._spotify_secondary_fade_starters: list[Callable[[], None]] = []
        self._spotify_secondary_registration_generation: int = 0
        self._spotify_overlay_prewarm_attempted: bool = False
        self._spotify_overlay_prewarmed: bool = False
        self._startup_completion_published: bool = False

        # Wait for compositor first frame before starting widget fades
        self._compositor_ready: bool = False

        # PySide signal connections must not own Nuitka ``compiled_method``
        # wrappers for this plain-Python manager. Keep stable partial objects
        # whose only manager edge is weak; the same object is reused for
        # connect/disconnect, and a stale Qt connection cannot retain ``self``.
        manager_ref = weakref.ref(self)
        self._compositor_ready_callback: Optional[Callable] = partial(
            _dispatch_widget_manager_callback,
            manager_ref,
            "_on_compositor_ready",
        )
        self._settings_changed_callback: Optional[Callable] = partial(
            _dispatch_widget_manager_callback,
            manager_ref,
            "_handle_settings_changed",
        )

        # ``image_displayed`` is a one-shot connection owned by this manager.
        # Keep explicit ownership rather than attempting a best-effort
        # disconnect during terminal cleanup: PySide warns when there is no
        # matching connection left after the first-frame handler has already
        # disconnected it.
        self._compositor_ready_signal_connected: bool = False
        self._connect_compositor_ready_signal()
        
        # Widget positioning (Dec 2025)
        self._positioner = WidgetPositioner()
        
        # Widget factory registry (Dec 2025) - for simplified widget creation
        self._factory_registry: Optional[WidgetFactoryRegistry] = None

        # Settings manager wiring for live updates (Spotify VIS etc.)
        self._settings_manager: Optional[SettingsManager] = None
        
        # Spotify visibility sync state
        self._pending_spotify_visibility_sync: bool = False
        self._perf_spotify_sync_request_count: int = 0
        self._perf_spotify_sync_widget_count: int = 0
        self._perf_spotify_sync_last_log_ts: float = time.monotonic()
        self._visualizer_preset_save_token: int = 0
        
        logger.debug("[WIDGET_MANAGER] Initialized")

    def _own_runtime_callback(self, callback: Callable) -> Callable:
        """Attach retiring-generation ownership to a manager closure.

        ``ThreadManager.single_shot`` can infer bound-method owners, but local
        closures otherwise look process-scoped.  These callbacks already close
        over this manager; explicit metadata lets teardown cancel and release
        them before the Python-owner destruction barrier is evaluated.
        """

        try:
            callback._srpss_timer_owner = self
            callback._srpss_runtime_generation = self._runtime_generation
        except (AttributeError, TypeError):
            pass
        return callback

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

    def _schedule_spotify_secondary_fades(
        self,
        delay_ms: int,
        *,
        prewarm: bool = True,
    ) -> None:
        queued = list(self._spotify_secondary_fade_starters)
        self._spotify_secondary_fade_starters = []
        if prewarm:
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
                    ThreadManager.single_shot(delay_ms, starter)
            except Exception as e:
                logger.warning("[SPOTIFY_SECONDARY][FALLBACK] Failed to schedule queued starter", exc_info=True)
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
            self._fade_coordinator.signal_compositor_ready()
            self._release_critical_gl_startup_hold()
            return
        
        try:
            # Check if parent already has rendered first frame
            if getattr(self._parent, "_has_rendered_first_frame", False):
                self._compositor_ready = True
                try:
                    self._fade_coordinator.signal_compositor_ready()
                    self._prewarm_spotify_visualizer_overlay()
                    self._release_critical_gl_startup_hold()
                except Exception:
                    logger.debug(
                        "[WIDGET_MANAGER] Failed to prime fade coordinator for already-ready compositor",
                        exc_info=True,
                    )
                return
            
            # Connect to image_displayed signal. A malformed/testing parent
            # must settle the critical hold instead of leaving overlays and
            # optional warmup permanently blocked.
            signal = getattr(self._parent, "image_displayed", None)
            connector = getattr(signal, "connect", None)
            callback = self._compositor_ready_callback
            if callable(connector) and callback is not None:
                connector(callback)
                self._compositor_ready_signal_connected = True
                return

            logger.warning(
                "[FADE_SYNC][FALLBACK] Parent has no image_displayed signal; "
                "settling startup coordination without it"
            )
            self._compositor_ready = True
            self._fade_coordinator.signal_compositor_ready()
            self._release_critical_gl_startup_hold()
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Failed to connect compositor ready signal: %s", e)
            self._compositor_ready = True  # Assume ready on failure
            self._fade_coordinator.signal_compositor_ready()
            self._release_critical_gl_startup_hold()

    def _disconnect_compositor_ready_signal(self) -> None:
        """Release this manager's one-shot compositor-ready connection once."""

        if not self._compositor_ready_signal_connected:
            return

        # Clear the ownership bit before touching Qt so a failing/disposed
        # sender cannot cause a second disconnect attempt from cleanup.
        self._compositor_ready_signal_connected = False
        parent = self._parent
        signal = getattr(parent, "image_displayed", None) if parent is not None else None
        disconnect = getattr(signal, "disconnect", None)
        callback = self._compositor_ready_callback
        if not callable(disconnect) or callback is None:
            return
        try:
            disconnect(callback)
        except (RuntimeError, TypeError):
            # Sender disposal can race terminal cleanup.  The ownership bit is
            # already clear, which is the important lifetime boundary here.
            logger.debug(
                "[WIDGET_MANAGER] Compositor-ready sender was unavailable during disconnect",
                exc_info=True,
            )
        except Exception:
            logger.debug(
                "[WIDGET_MANAGER] Compositor-ready disconnect failed after ownership release",
                exc_info=True,
            )
    
    def _on_compositor_ready(self, image_path: str) -> None:
        """Called when compositor displays first image."""
        # Disconnect before running readiness work.  This makes the slot truly
        # one-shot even if a nested event is emitted during fade preparation.
        self._disconnect_compositor_ready_signal()
        screen_idx = getattr(self._parent, "screen_index", "?")
        if self._compositor_ready:
            logger.debug("[FADE_SYNC] Compositor already ready on screen=%s, ignoring duplicate signal", screen_idx)
            return  # Already marked ready
        
        self._compositor_ready = True
        # Publish first-frame readiness while the critical resource hold is
        # still active. Base image/compositor resources are already committed
        # at this seam; only the active Spotify overlay's existing prewarm
        # remains before primary reveals may begin.
        self._fade_coordinator.signal_compositor_ready()
        try:
            self._parent._overlay_fade_started = True
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

        try:
            self._prewarm_spotify_visualizer_overlay()
            if self._expected_overlays:
                policy = self._get_overlay_startup_policy()
                logger.debug(
                    "[SPOTIFY_SECONDARY] compositor ready; using startup secondary delay=%sms",
                    int(policy.spotify_secondary_startup_delay_ms),
                )

                self._schedule_spotify_secondary_fades(
                    int(policy.spotify_secondary_startup_delay_ms),
                    prewarm=False,
                )
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        finally:
            # Optional prewarm failure is terminal for this startup attempt; a
            # best-effort resource must never strand overlays behind the hold.
            self._release_critical_gl_startup_hold()
        
        logger.info("[FADE_SYNC] Compositor ready on screen=%s (first image: %s)", screen_idx, image_path)
        
    def _release_critical_gl_startup_hold(self) -> None:
        self._fade_coordinator.release_startup_hold(_CRITICAL_GL_STARTUP_HOLD)
        if not self._fade_coordinator.describe().get("participants"):
            self._on_startup_fades_complete()

    def _on_startup_fades_complete(self) -> None:
        """Resume optional compositor warmup after the real overlay fade."""

        parent = self._parent
        compositor = getattr(parent, "_gl_compositor", None) if parent is not None else None
        if compositor is None:
            return
        try:
            from rendering.gl_compositor_pkg.gl_lifecycle import (
                resume_deferred_transition_warmup,
            )

            resume_deferred_transition_warmup(compositor)
        except Exception:
            logger.debug(
                "[WIDGET_MANAGER] Failed to resume deferred GL warmup",
                exc_info=True,
            )
        if self._startup_completion_published:
            return
        self._startup_completion_published = True
        try:
            parent._startup_reveal_completed = True
            parent.startup_reveal_completed.emit()
        except (AttributeError, RuntimeError):
            logger.debug(
                "[WIDGET_MANAGER] Startup reveal completion publication skipped",
                exc_info=True,
            )
    
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
        # Use REPLACE semantics so target presets cannot inherit stale keys
        # from the mode payload they replace.
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
        settings.set('widgets.spotify_visualizer', vis_config)
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
        settings.set('widgets.spotify_visualizer', vis_config)
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
                    self._raise_timer = QTimer(self._parent)
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
            name: Name of widget
            
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
        callback = self._settings_changed_callback
        if callback is None:
            callback = partial(
                _dispatch_widget_manager_callback,
                weakref.ref(self),
                "_handle_settings_changed",
            )
            self._settings_changed_callback = callback
        try:
            settings_manager.settings_changed.connect(callback)
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to connect settings_changed signal", exc_info=True)

    def _detach_settings_manager(self) -> None:
        """Disconnect previously attached settings manager, if any."""
        if self._settings_manager is None:
            return
        callback = self._settings_changed_callback
        try:
            if callback is not None:
                self._settings_manager.settings_changed.disconnect(callback)
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

        parent = self._parent
        runtime_reload_pending = False
        if parent is not None:
            try:
                pending_value = getattr(parent, "_custom_layout_runtime_reload_pending", False)
                runtime_reload_pending = pending_value if isinstance(pending_value, bool) else False
            except Exception:
                runtime_reload_pending = False
        if (
            parent is not None
            and setting_key.startswith("widgets")
            and runtime_reload_pending
        ):
            logger.debug(
                "[WIDGET_MANAGER][SETTINGS] suppressing live refresh during custom layout runtime reload key=%s",
                setting_key,
            )
            return

        # E2.7 canonical capability-deactivation boundary: a widgets/family
        # activation change may make the Visualizer capability ineffective (Media
        # OFF or Visualizers OFF). Retire the GLOBAL Visualizer failover lifecycle
        # here — not just block creation — so a pending grace/generation cannot
        # stay stuck and a later reactivation can arm a fresh grace.
        if setting_key == 'widgets' or setting_key.startswith('widgets.family_activation'):
            if self._runtime_manager is not None:
                self._runtime_manager.handle_capability_change(self._settings_manager)

        if setting_key == 'widgets':
            widgets_payload: Optional[Mapping[str, Any]] = value if isinstance(value, Mapping) else None
            for handler_name in get_live_refresh_handlers():
                handler = getattr(self, handler_name, None)
                if callable(handler):
                    handler(widgets_payload)
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
        if (
            parent is not None
            and setting_key.startswith("widgets.")
            and self._settings_key_requires_custom_layout_reapply(setting_key)
        ):
            try:
                parent._apply_saved_custom_layouts()
            except Exception:
                logger.debug("[WIDGET_MANAGER] Failed to reapply saved custom layouts", exc_info=True)

    def _settings_key_requires_custom_layout_reapply(self, setting_key: str) -> bool:
        """Return whether a settings change should replay committed CUSTOM layout.

        CUSTOM replay is geometry authority, not a generic follow-up step for
        every widget config mutation. Only route/monitor/custom-layout changes
        should trigger a full reapply here; mode/content changes must stay local
        to their owning widget paths.
        """
        if not setting_key.startswith("widgets."):
            return False
        if setting_key.startswith("widgets.custom_layout"):
            return True
        return setting_key.endswith(_CUSTOM_LAYOUT_REAPPLY_SUFFIXES)

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
                    "vshift=%s bubble_group_drift=%s bubble_drift_direction=%s "
                    "preset_index=%s preset_kind=%s preset_name=%s preset_path=%s"
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
                getattr(resolved_model, 'bubble_group_drift', cfg.get('bubble_group_drift')),
                getattr(resolved_model, 'bubble_drift_direction', cfg.get('bubble_drift_direction')),
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
            batch_factory = getattr(media_widget, 'painted_frame_shadow_update_batch', None)
            batch = batch_factory() if callable(batch_factory) else nullcontext()
            with batch:
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
            if hasattr(media_widget, 'set_playback_progress_config'):
                progress_fill = parse_color_to_qcolor(model.playback_progress_fill_color)
                progress_glow = parse_color_to_qcolor(model.playback_progress_glow_color)
                media_widget.set_playback_progress_config(
                    enabled=SettingsManager.to_bool(model.playback_progress_enabled, False),
                    height=int(model.playback_progress_height),
                    fill_color=progress_fill or parse_color_to_qcolor([255, 255, 255, 230]),
                    shadow_enabled=SettingsManager.to_bool(model.playback_progress_shadow_enabled, False),
                    glow_enabled=SettingsManager.to_bool(model.playback_progress_glow_enabled, False),
                    glow_color=progress_glow or parse_color_to_qcolor([255, 255, 255, 180]),
                )
            if hasattr(media_widget, 'set_show_header_frame'):
                media_widget.set_show_header_frame(SettingsManager.to_bool(model.show_header_frame, True))
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to reapply media controls/header", exc_info=True)

        vis_widget = self._widgets.get('spotify_visualizer') or self._widgets.get('spotify_visualizer_widget')
        if vis_widget is not None:
            self._apply_media_card_style_to_visualizer(vis_widget, media_cfg)

    def _sync_media_provider_runtime(self, provider: object) -> None:
        """Rebind live media dependents to the active provider setting/runtime choice."""

        normalized = preserve_provider_setting(provider)

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

    def sync_media_volume_runtime_target(
        self,
        provider: object,
        source_app_user_model_id: object,
    ) -> None:
        """Route one accepted GSMTC source to the volume widget without persistence."""

        volume_widget = self._widgets.get('spotify_volume') or self._widgets.get(
            'spotify_volume_widget'
        )
        if volume_widget is None or not hasattr(volume_widget, 'set_runtime_volume_source'):
            return
        try:
            volume_widget.set_runtime_volume_source(
                provider,
                source_app_user_model_id,
            )
        except Exception:
            logger.debug(
                "[WIDGET_MANAGER] Failed to sync media volume runtime target",
                exc_info=True,
            )

    def handle_media_provider_failover(self, provider: object, *, source: str = "runtime") -> None:
        """Persist a runtime media-provider auto-fallback through the shared settings path."""

        normalized = normalize_provider_id(provider)
        if normalized is None:
            logger.warning(
                "[WIDGET_MANAGER] Ignoring invalid media-provider failover target: %r",
                provider,
            )
            return
        settings = self._settings_manager
        if settings is None:
            self._sync_media_provider_runtime(normalized)
            return

        widgets_cfg = settings.get('widgets', {}) or {}
        if not isinstance(widgets_cfg, Mapping):
            widgets_cfg = {}
        media_cfg = widgets_cfg.get('media', {}) or {}
        if not isinstance(media_cfg, Mapping):
            media_cfg = {}

        current = preserve_provider_setting(media_cfg.get('provider', 'spotify'))
        if normalize_provider_id(current) is None:
            logger.warning(
                "[WIDGET_MANAGER] Preserving unsupported configured media provider: %r",
                current,
            )
            return
        self._sync_media_provider_runtime(normalized)
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
                batch_factory = getattr(widget, 'painted_frame_shadow_update_batch', None)
                batch = batch_factory() if callable(batch_factory) else nullcontext()
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

                with batch:
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
                    raise_auxiliary = getattr(widget, 'raise_auxiliary_labels', None)
                    if callable(raise_auxiliary):
                        raise_auxiliary()
                except Exception as e:
                    logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)

    def position_spotify_visualizer(self, vis_widget, media_widget, parent_width: int, parent_height: int) -> None:
        """Position Spotify visualizer relative to media widget."""
        if vis_widget is None:
            return
        try:
            widgets_config: Mapping[str, Any] | None = None
            if self._settings_manager is not None:
                candidate = self._settings_manager.get_widgets_map() or {}
                if isinstance(candidate, Mapping):
                    widgets_config = candidate

            custom_rect = getattr(vis_widget, "_custom_layout_local_rect", None)
            if (
                isinstance(custom_rect, QRect)
                and custom_rect.width() > 0
                and custom_rect.height() > 0
            ):
                try:
                    apply_constraints = getattr(vis_widget, "_apply_custom_layout_size_constraints_if_active", None)
                    if callable(apply_constraints):
                        apply_constraints()
                except Exception:
                    logger.debug("[WIDGET_MANAGER] Failed to lock visualizer custom constraints", exc_info=True)
                from widgets.spotify_visualizer.card_geometry import (
                    resolve_custom_card_rect,
                )
                resolved_custom_rect = resolve_custom_card_rect(
                    custom_rect,
                    parent_width=parent_width,
                    parent_height=parent_height,
                    size=custom_rect.size(),
                )
                if resolved_custom_rect.isEmpty():
                    return
                vis_widget.setGeometry(resolved_custom_rect)
                try:
                    from rendering.display_image_ops import sync_spotify_visualizer_overlay_geometry

                    sync_spotify_visualizer_overlay_geometry(self._parent)
                except Exception:
                    logger.debug("[WIDGET_MANAGER] Failed to sync visualizer overlay geometry after custom rect apply", exc_info=True)
                vis_widget.raise_()
                return

            if is_custom_position_selected_for_widget("spotify_visualizer", widgets_config):
                logger.debug(
                    "[WIDGET_MANAGER] Deferring authored visualizer positioning because CUSTOM routing is selected but committed rect is not yet attached"
                )
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
            try:
                from rendering.display_image_ops import sync_spotify_visualizer_overlay_geometry

                sync_spotify_visualizer_overlay_geometry(self._parent)
            except Exception:
                logger.debug("[WIDGET_MANAGER] Failed to sync visualizer overlay geometry after authored apply", exc_info=True)
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
                candidate = self._settings_manager.get_widgets_map() or {}
                if isinstance(candidate, Mapping):
                    widgets_config = candidate

            custom_rect = getattr(vol_widget, "_custom_layout_local_rect", None)
            if (
                isinstance(custom_rect, QRect)
                and custom_rect.width() > 0
                and custom_rect.height() > 0
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

    def _widget_has_active_custom_layout_rect(self, widget: Any) -> bool:
        """Return whether a widget currently has a saved CUSTOM rect in force.

        Shared authored stacking must never reflow widgets whose outer geometry
        is already being explicitly controlled by the saved CUSTOM layout.
        """
        try:
            if bool(getattr(widget, "_custom_layout_shell_active", False)):
                return True
            custom_rect = getattr(widget, "_custom_layout_local_rect", None)
            return (
                isinstance(custom_rect, QRect)
                and custom_rect.width() > 0
                and custom_rect.height() > 0
            )
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            return False

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
        custom_layout_edit_active = getattr(self._parent, "_custom_layout_edit_active", False)
        if not isinstance(custom_layout_edit_active, bool):
            custom_layout_edit_active = False
        custom_layout_mode_active = self._custom_layout_mode_disables_stacking(
            widget_list,
            widgets_config,
        )
        if not stacking_enabled or custom_layout_edit_active or custom_layout_mode_active:
            for widget, _attr_name in widget_list:
                if widget is not None and hasattr(widget, "set_stack_offset"):
                    widget.set_stack_offset(QPoint(0, 0))
            if is_geometry_logging_enabled():
                logger.info(
                    "[STACK] screen=%s stacking disabled (enabled=%s custom_edit=%s custom_mode=%s); clearing offsets for %d widgets",
                    getattr(self._parent, "screen_index", "?"),
                    stacking_enabled,
                    custom_layout_edit_active,
                    custom_layout_mode_active,
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
                and (
                    self._widget_has_active_custom_layout_rect(widget)
                    or (
                        descriptor.supports_custom_position_slot
                        and is_custom_position_selected_for_widget(descriptor.widget_id, widgets_config)
                    )
                )
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

    def _custom_layout_mode_disables_stacking(
        self,
        widget_list: list,
        widgets_config: Optional[Mapping[str, Any]],
    ) -> bool:
        """Return True when any live or configured widget family is in CUSTOM mode."""

        for widget, _attr_name in widget_list:
            if widget is not None and self._widget_has_active_custom_layout_rect(widget):
                return True

        if not isinstance(widgets_config, Mapping):
            return False

        for descriptor in get_layout_edit_runtime_descriptors():
            if is_custom_position_selected_for_widget(descriptor.widget_id, widgets_config):
                return True
        return False

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

        self._disconnect_compositor_ready_signal()

        # DisplayWidget mirrors not-yet-started reveal callbacks so the
        # compositor-ready path can release them together.  Each wrapper closes
        # over this manager.  If teardown happens before first-frame readiness,
        # leaving that mirror populated retains the retired WidgetManager even
        # after every widget and the FadeCoordinator have been cleaned.
        parent = self._parent
        if parent is not None:
            try:
                pending_reveals = getattr(parent, "_overlay_fade_pending", None)
                if isinstance(pending_reveals, dict):
                    pending_reveals.clear()
            except RuntimeError:
                pass
        
        # Use lifecycle cleanup for widgets that support it
        for name, widget in list(self._widgets.items()):
            if widget is not None:
                try:
                    if hasattr(widget, 'cleanup') and callable(widget.cleanup):
                        widget.cleanup()
                except Exception:
                    logger.debug("[WIDGET_MANAGER] Failed to cleanup %s", name, exc_info=True)
                finally:
                    # Several managed overlays keep a back-reference for
                    # runtime routing.  Cleanup is terminal for this manager;
                    # leaving any of those edges intact retains the complete
                    # retired manager graph until cyclic GC.
                    try:
                        if getattr(widget, "_widget_manager", None) is self:
                            widget._widget_manager = None
                    except (AttributeError, RuntimeError):
                        pass
        
        self._widgets.clear()
        self._fade_callbacks.clear()
        self._expected_overlays.clear()
        self._spotify_secondary_fade_starters.clear()
        self._pending_spotify_visibility_sync = False
        self._factory_registry = None
        self._settings_manager = None
        if self._fade_coordinator is not None:
            self._fade_coordinator.cleanup()
        self._fade_coordinator = None

        # WidgetManager is a plain Python owner held by DisplayWidget.  Keeping
        # this back-reference after terminal runtime cleanup forms a complete
        # DisplayWidget -> WidgetManager -> DisplayWidget cycle, while the fade
        # coordinator's bound completion callback can retain the same graph.
        # Runtime teardown is terminal for this manager, so release the owner
        # edge explicitly rather than relying on cyclic GC.
        self._compositor_ready_callback = None
        self._settings_changed_callback = None
        self._resource_manager = None
        if self._runtime_manager is not None:
            self._runtime_manager.cleanup()
            self._runtime_manager = None
        self._parent = None
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
        self._spotify_secondary_registration_generation += 1
        self._pending_raise = False

        if self._raise_timer is not None:
            try:
                self._raise_timer.stop()
                self._raise_timer.deleteLater()
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

    # Runtime lifecycle routing is owned by WidgetRuntimeManager (Phase E1).
    # These thin wrappers preserve the public API used by callers and tests, plus
    # the E2.7 confirmed-retirement contract (``cleanup_widget`` returns an
    # explicit bool). A missing owner (post-cleanup) fails closed.
    def initialize_widget(self, name: str) -> bool:
        """Initialize a widget using the lifecycle system (delegated)."""
        if self._runtime_manager is None:
            return False
        return self._runtime_manager.initialize_widget(name)

    def activate_widget(self, name: str) -> bool:
        """Activate a widget using the lifecycle system (delegated)."""
        if self._runtime_manager is None:
            return False
        return self._runtime_manager.activate_widget(name)

    def deactivate_widget(self, name: str) -> bool:
        """Deactivate a widget using the lifecycle system (delegated)."""
        if self._runtime_manager is None:
            return False
        return self._runtime_manager.deactivate_widget(name)

    def cleanup_widget(self, name: str) -> bool:
        """Cleanup a widget using the lifecycle system (delegated).

        Returns an explicit success bool; the E2.7 confirmed-retirement contract
        relies on it.
        """
        if self._runtime_manager is None:
            return False
        return self._runtime_manager.cleanup_widget(name)

    def initialize_all_widgets(self) -> int:
        """Initialize all managed widgets (delegated)."""
        if self._runtime_manager is None:
            return 0
        return self._runtime_manager.initialize_all_widgets()

    def activate_all_widgets(self) -> int:
        """Activate all managed widgets (delegated).

        DORMANT as of Jan 2026: the legacy start() system is used instead (see
        setup_all_widgets).
        """
        if self._runtime_manager is None:
            return 0
        return self._runtime_manager.activate_all_widgets()

    def deactivate_all_widgets(self) -> int:
        """Deactivate all managed widgets (delegated)."""
        if self._runtime_manager is None:
            return 0
        return self._runtime_manager.deactivate_all_widgets()

    def get_widget_lifecycle_state(self, name: str) -> Optional[str]:
        """Get the lifecycle state of a widget (delegated)."""
        if self._runtime_manager is None:
            return None
        return self._runtime_manager.get_widget_lifecycle_state(name)

    def get_all_lifecycle_states(self) -> Dict[str, str]:
        """Get lifecycle states of all managed widgets (delegated)."""
        if self._runtime_manager is None:
            return {}
        return self._runtime_manager.get_all_lifecycle_states()

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
            self._fade_coordinator.add_startup_hold(_CRITICAL_GL_STARTUP_HOLD)
            self._fade_coordinator.add_completion_callback(
                self._on_startup_fades_complete
            )
        self._expected_overlays = set()
        self._spotify_secondary_fade_starters = []
        self._spotify_secondary_registration_generation += 1
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
                self._prewarm_spotify_visualizer_overlay()
                self._release_critical_gl_startup_hold()
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
        fade_generation = self._fade_coordinator.get_generation()

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
            self._track_overlay_fade_completion(
                overlay_name,
                generation=fade_generation,
            )

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

        self._prepare_overlay_frame_shadow_before_reveal(overlay_name)
        started_immediately = self._fade_coordinator.request_fade(overlay_name, _starter_wrapper)
        logger.debug(
            "[FADE_COORD] %s fade request registered (started_immediately=%s)",
            overlay_name,
            started_immediately,
        )

    def _prepare_overlay_frame_shadow_before_reveal(self, overlay_name: str) -> None:
        """Build the overlay's painted frame while it is still hidden.

        ``BaseOverlayWidget`` coalesces frame-shadow invalidation while a widget
        is hidden - ``_commit_painted_frame_shadow_cache()`` returns early unless
        ``isVisible()`` - and rebuilds once in ``showEvent``. The reveal starter
        is what calls ``show()``, so that rebuild lands inside the fade window
        alongside every other participant's.

        This point is the widget declaring itself ready for display: geometry,
        DPR and background style are already final, and the cache key does not
        depend on visibility. Preparing here produces the identical cache-keyed
        pixmap and leaves the later ``showEvent`` a cache hit.

        Same pixels, same cache identity, same GUI owner; no timer, thread,
        queue or second cache is introduced. A widget that does not use the
        shared painted frame is untouched, because the prepare resolves no cache
        key and returns.
        """

        widget = self._resolve_overlay_fade_widget(overlay_name)
        if widget is None:
            return
        prepare = getattr(widget, "_prepare_painted_frame_shadow_pixmap", None)
        if not callable(prepare):
            return
        try:
            prepare()
        except Exception:
            logger.debug(
                "[WIDGET_MANAGER] Pre-reveal frame preparation failed (overlay=%s)",
                overlay_name,
                exc_info=True,
            )

    def _resolve_overlay_fade_widget(self, overlay_name: str) -> Optional[QWidget]:
        candidates = (
            self._widgets.get(overlay_name),
            self._widgets.get(f"{overlay_name}_widget"),
            getattr(self._parent, f"{overlay_name}_widget", None)
            if self._parent is not None
            else None,
            getattr(self._parent, overlay_name, None)
            if self._parent is not None
            else None,
        )
        for candidate in candidates:
            if isinstance(candidate, QWidget):
                return candidate
        return None

    def _track_overlay_fade_completion(
        self,
        overlay_name: str,
        *,
        generation: int,
    ) -> None:
        """Connect coordinator completion to the real shadow-fade animation."""

        widget = self._resolve_overlay_fade_widget(overlay_name)
        if widget is None:
            self._fade_coordinator.mark_fade_complete(
                overlay_name,
                generation=generation,
            )
            return

        if bool(getattr(widget, "_shadowfade_completed", False)):
            self._fade_coordinator.mark_fade_complete(
                overlay_name,
                generation=generation,
            )
            return

        animation = getattr(widget, "_shadowfade_anim", None)
        finished_signal = getattr(animation, "finished", None)
        connector = getattr(finished_signal, "connect", None)
        if not callable(connector):
            self._fade_coordinator.mark_fade_complete(
                overlay_name,
                generation=generation,
            )
            return

        completed = False
        coordinator_ref = weakref.ref(self._fade_coordinator)

        def _complete(*_args) -> None:
            nonlocal completed
            if completed:
                return
            completed = True
            coordinator = coordinator_ref()
            if coordinator is None:
                return
            coordinator.mark_fade_complete(
                overlay_name,
                generation=generation,
            )

        try:
            connector(_complete)
            destroyed = getattr(widget, "destroyed", None)
            destroyed_connect = getattr(destroyed, "connect", None)
            if callable(destroyed_connect):
                destroyed_connect(_complete)
        except Exception:
            logger.debug(
                "[FADE_COORD] Failed to track real fade completion for %s",
                overlay_name,
                exc_info=True,
            )
            _complete()

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
                ThreadManager.single_shot(direct_delay_ms, starter)
            except Exception as e:
                logger.warning("[SPOTIFY_SECONDARY][FALLBACK] Failed to schedule direct starter", exc_info=True)
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
            ThreadManager.single_shot(direct_delay_ms, starter)
        except Exception as e:
            logger.warning("[SPOTIFY_SECONDARY][FALLBACK] Failed to schedule compositor-ready starter", exc_info=True)
            try:
                starter()
            except Exception as inner:
                logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", inner)

    def register_spotify_secondary_stage_widget(self, widget: Optional[QWidget]) -> None:
        """Register a Spotify dependent widget through the manager-owned startup seam."""
        self._register_spotify_secondary_fade(widget)

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

        self._own_runtime_callback(_run)

        try:
            ThreadManager.single_shot(0, _run)
        except Exception:
            _run()

    def sync_spotify_dependents_for_media_widget(self, media_widget: Optional[MediaWidget]) -> None:
        """Sync all Spotify dependents anchored to *media_widget* across displays."""

        if media_widget is None:
            return
        self._perf_spotify_sync_request_count += 1

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
                    self._perf_spotify_sync_widget_count += 1
                except Exception:
                    logger.debug("[WIDGET_MANAGER] Failed to sync %s with media anchor", attr_name, exc_info=True)
        self._maybe_log_spotify_sync_perf()

    def _maybe_log_spotify_sync_perf(self) -> None:
        if not is_perf_metrics_enabled():
            return
        now = time.monotonic()
        elapsed = now - self._perf_spotify_sync_last_log_ts
        if elapsed < 10.0:
            return
        screen = getattr(self._parent, "_screen_index", getattr(self._parent, "screen_index", None))
        try:
            screen_repr = int(screen) if screen is not None else "<unknown>"
        except Exception:
            screen_repr = "<unknown>"
        logger.info(
            "[PERF][SPOTIFY_VIS][VIS_SYNC] manager_screen=%s elapsed_ms=%.1f "
            "requests=%d widgets_synced=%d pending=%s",
            screen_repr,
            elapsed * 1000.0,
            self._perf_spotify_sync_request_count,
            self._perf_spotify_sync_widget_count,
            self._pending_spotify_visibility_sync,
        )
        self._perf_spotify_sync_request_count = 0
        self._perf_spotify_sync_widget_count = 0
        self._perf_spotify_sync_last_log_ts = now

    def _register_spotify_secondary_fade(self, widget: Optional[QWidget]) -> None:
        if widget is None:
            return
        generation = self._spotify_secondary_registration_generation
        manager_id = id(self)
        try:
            setattr(widget, "_spotify_secondary_stage_registered", True)
            setattr(widget, "_spotify_secondary_stage_generation", generation)
            setattr(widget, "_spotify_secondary_stage_manager_id", manager_id)
        except Exception:
            logger.debug("[WIDGET_MANAGER] Failed to mark widget as secondary-stage registered", exc_info=True)

        anchor = getattr(widget, "_anchor_media", None)
        starter = self._make_spotify_secondary_fade_starter(
            widget,
            anchor,
            registration_generation=generation,
            manager_id=manager_id,
            attempt=0,
        )

        if is_perf_metrics_enabled():
            logger.debug(
                "[SPOTIFY_DIAG] registering secondary fade for %s (screen=%s)",
                widget.objectName() or type(widget).__name__,
                getattr(self._parent, "screen_index", "?"),
            )
        self.register_spotify_secondary_fade(starter)

    def _make_spotify_secondary_fade_starter(
        self,
        widget: QWidget,
        anchor: Optional[QWidget],
        *,
        registration_generation: int,
        manager_id: int,
        attempt: int,
    ) -> Callable[[], None]:
        """Build a generation-owned callback without a runtime-owner cycle."""

        callback = partial(
            _dispatch_spotify_secondary_attempt,
            weakref.ref(self),
            weakref.ref(widget),
            weakref.ref(anchor) if anchor is not None else None,
            int(registration_generation),
            int(manager_id),
            int(attempt),
        )
        callback._srpss_runtime_generation = self._runtime_generation
        return callback

    def _run_spotify_secondary_fade_attempt(
        self,
        widget: QWidget,
        anchor_ref: "weakref.ReferenceType[QWidget] | None",
        *,
        registration_generation: int,
        manager_id: int,
        attempt: int,
    ) -> None:
        """Run or reschedule one Spotify secondary-stage visibility attempt."""

        try:
            widget.objectName()
            registration_current = (
                bool(getattr(widget, "_spotify_secondary_stage_registered", False))
                and getattr(widget, "_spotify_secondary_stage_generation", None)
                == registration_generation
                and getattr(widget, "_spotify_secondary_stage_manager_id", None)
                == manager_id
                and registration_generation
                == self._spotify_secondary_registration_generation
            )
        except (RuntimeError, TypeError):
            registration_current = False
        except Exception as exc:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", exc)
            registration_current = False

        if not registration_current:
            if is_perf_metrics_enabled():
                logger.warning(
                    "[SPOTIFY_VIS][STARTUP] Skipping stale secondary-stage starter "
                    "widget=%s generation=%s current_generation=%s screen=%s",
                    type(widget).__name__,
                    registration_generation,
                    self._spotify_secondary_registration_generation,
                    getattr(self._parent, "screen_index", "?"),
                )
            return

        anchor = anchor_ref() if anchor_ref is not None else None
        try:
            anchor_visible = not (
                anchor is not None
                and hasattr(anchor, "isVisible")
                and not bool(anchor.isVisible())
            )
        except (RuntimeError, TypeError):
            anchor_visible = True
        except Exception as exc:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", exc)
            anchor_visible = True

        max_deferrals = 20
        if not anchor_visible and attempt < max_deferrals:
            delay_ms = min(1000, 200 + attempt * 100)
            if is_perf_metrics_enabled():
                logger.debug(
                    "[SPOTIFY_DIAG] deferring secondary fade for %s (anchor hidden, attempt=%s, delay=%sms)",
                    widget.objectName() or type(widget).__name__,
                    attempt + 1,
                    delay_ms,
                )
            ThreadManager.single_shot(
                delay_ms,
                self._make_spotify_secondary_fade_starter(
                    widget,
                    anchor,
                    registration_generation=registration_generation,
                    manager_id=manager_id,
                    attempt=attempt + 1,
                ),
            )
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
