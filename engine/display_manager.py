"""
Display manager for multi-monitor support.

Owns one authoritative Quick display unit for each selected screen.
"""
import os
import time
import weakref
from copy import deepcopy
from dataclasses import asdict
from types import MappingProxyType, SimpleNamespace
from typing import Any, List, Dict, Optional, Set, Mapping
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtGui import QGuiApplication, QScreen, QPixmap, QDesktopServices

from core.logging.logger import (
    get_logger,
    is_perf_metrics_enabled,
    is_viz_diagnostics_enabled,
)
from core.resources.manager import ResourceManager
from core.settings.capability_activation import (
    apply_transition_menu_selection,
    get_activated_transition_names,
    get_effective_random_pool,
    is_widget_family_effective,
)
from core.settings.defaults import get_default_settings
from rendering.display_modes import DisplayMode
from rendering.transition_registry import (
    canonicalize_transition_name,
    is_transition_available_for_hw,
)
from rendering.quick.context_menu import (
    build_quick_context_menu_entries,
    enforce_single_visible_context_menu,
)
from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
from rendering.quick.custom_layout_hydration import (
    apply_quick_committed_payloads,
    resolve_quick_committed_geometry,
    resolve_quick_committed_variant_state,
    resolve_quick_custom_entry,
)
from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
from rendering.quick.display_unit import QuickDisplayUnit, create_quick_display_unit
from rendering.quick.display_processing import DisplayProcessingDescriptor
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.startup_reveal import (
    QUICK_STARTUP_DESKTOP_CROSSFADE_DURATION_MS,
    QuickStartupRevealCoordinator,
)
from rendering.quick.state import (
    QuickSceneReadiness,
    QuickWindowPolicy,
    QuickWindowRole,
)
from rendering.quick.transitions.request_resolution import (
    ResolvedQuickTransitionSpec,
    resolve_quick_transition_spec,
)
from utils.lockfree.spsc_queue import SPSCQueue

logger = get_logger(__name__)
REDDIT_FLUSH_LOGGING = True  # Set to False to silence deferred Reddit flush diagnostics once stable.
MONITOR_RECONCILE_DELAY_MS = 250

try:  # Windows-only bridge for ProgramData queue
    from core.windows import reddit_helper_bridge
except Exception:  # pragma: no cover - non-Windows or optional import failure
    reddit_helper_bridge = None


class DisplayManager(QObject):
    """
    Manage authoritative Quick display units across multiple monitors.
    
    Features:
    - Multi-monitor detection
    - Quick display-unit creation per selected monitor
    - Monitor hotplug handling
    - Same/different image modes
    - Coordinated exit
    
    Signals:
    - exit_requested: Emitted when any display requests exit
    - monitors_changed: Emitted when monitor configuration changes
    """
    
    exit_requested = Signal()
    monitors_changed = Signal(int)  # new monitor count
    displays_ready = Signal(int)  # startup generation ready for image replay
    authoritative_first_frames_ready = Signal(int)  # runtime generation
    startup_reveal_completed = Signal(int)  # runtime generation
    transition_completed = Signal(int)  # screen index
    previous_requested = Signal()  # Z key - go to previous image
    next_requested = Signal()  # X key - go to next image
    cycle_transition_requested = Signal()  # C key - cycle transition mode
    settings_requested = Signal()  # S key - open settings
    # The exact DisplayManager identity is a pointer-width Python integer.
    custom_layout_reload_requested = Signal(str, int, object)
    
    def __init__(
        self,
        display_mode: DisplayMode = DisplayMode.FILL,
        same_image_mode: bool = True,
        settings_manager=None,
        resource_manager: ResourceManager | None = None,
        thread_manager=None,
        runtime_generation: int | None = None,
        image_accounting_publisher=None,
        desktop_startup_crossfade_enabled: bool = False,
    ):
        """
        Initialize display manager.
        
        Args:
            display_mode: Display mode for all screens
            same_image_mode: True = same image on all screens, False = different images
            settings_manager: SettingsManager for widget configuration
        """
        super().__init__()

        self._runtime_generation = (
            int(runtime_generation) if runtime_generation is not None else None
        )
        # Application/session ownership lives above DisplayManager.  The engine
        # enables desktop staging only for the cold runtime generation; later
        # Settings/runtime replacements still use the flash-proof widget reveal
        # gate but must not replay the desktop -> wallpaper startup ceremony.
        self._desktop_startup_crossfade_enabled = bool(
            desktop_startup_crossfade_enabled
        )
        self._retired = False
        
        self.display_mode = display_mode
        self.same_image_mode = same_image_mode
        self.settings_manager = settings_manager
        self._resource_manager: ResourceManager | None = (
            resource_manager or ResourceManager.get_or_create_app_shared()
        )
        self._thread_manager = thread_manager
        self._process_supervisor = None
        self._image_accounting_publisher_ref = None
        if image_accounting_publisher is not None:
            try:
                self._image_accounting_publisher_ref = weakref.WeakMethod(
                    image_accounting_publisher
                )
            except TypeError:
                try:
                    self._image_accounting_publisher_ref = weakref.ref(
                        image_accounting_publisher
                    )
                except TypeError:
                    self._image_accounting_publisher_ref = None
        self._display_image_accounting_by_id: dict[int, Any] = {}
        self._display_image_accounting_snapshot = MappingProxyType(
            {
                "generation": self._runtime_generation,
                "total_tracked_bytes": 0,
                "resource_count": 0,
                "resources": (),
            }
        )
        self._runtime_signal_connections: list[tuple[str, Any]] = []
        self.displays: list[QuickDisplayUnit] = []
        self._quick_scene_factory: QuickSceneFactory | None = None
        self._quick_ctrl_coordinator = SharedCtrlCoordinator()
        self._quick_readiness_by_screen: dict[int, QuickSceneReadiness] = {}
        self._quick_visualizer_owner: Any | None = None
        self._quick_visualizer_unit: QuickDisplayUnit | None = None
        self._quick_visualizer_media_model: Any | None = None
        # Secondary fence for the CUSTOM failover grace deadline (bumped on a
        # temporary-owner retirement so a stale deadline cannot resurrect it).
        self._quick_visualizer_failover_token: int = 0
        self._quick_visualizer_construct_result = "not_attempted"
        self._quick_visualizer_construct_reject_reason: str | None = None
        self._quick_visualizer_routing_trace_emitted = False
        self._quick_custom_layout_owner = QuickCustomLayoutOwner(
            settings_manager=settings_manager,
            participants_provider=lambda: tuple(self.displays),
            visualizer_provider=lambda: (
                self._quick_visualizer_owner,
                self._quick_visualizer_unit,
            ),
            reload_request=self._request_custom_layout_runtime_reload,
        )
        self._retiring_quick_units: dict[int, QuickDisplayUnit] = {}
        self._retire_manager_when_quick_complete = False
        self._widgets_config_snapshot: dict[str, Any] = {}
        self._shadow_values_snapshot: dict[str, Any] = {}
        self.current_images: Dict[int, str] = {}  # screen_index -> image_path
        self._deferred_reddit_urls: list[str] = []
        self._display_startup_generation = 0
        self._display_startup_ready_expected: Set[int] = set()
        self._display_startup_ready_seen: Set[int] = set()
        self._display_startup_ready_emitted_generation: int = -1
        self._authoritative_first_frame_screens: Set[int] = set()
        self._authoritative_first_frame_emitted = False
        # Screens whose retained base image is a one-session desktop snapshot.
        # This staging source makes the first authored wallpaper a real crossfade
        # without pretending the snapshot is queue/history/current-image truth.
        self._startup_desktop_seed_screens: Set[int] = set()
        self._startup_reveal_screens: Set[int] = set()
        self._startup_reveal_started = False
        self._startup_reveal_emitted = False
        self._quick_startup_reveal: QuickStartupRevealCoordinator | None = None
        
        # Phase 3: Multi-display synchronization (lock-free)
        self._transition_ready_queue: Optional[SPSCQueue] = None
        self._sync_enabled = False
        self._transition_work_pending = False
        self._quick_transition_batch_spec: ResolvedQuickTransitionSpec | None = None
        self._quick_transition_spec_resolved = False
        self._quick_transition_paths: dict[int, str] = {}
        self._quick_batch_expected_screens: set[int] = set()
        self._quick_batch_published_screens: set[int] = set()
        self._monitor_detection_app = None
        self._monitor_detection_connected = False
        self._monitor_reconcile_pending = False
        self._screen_signature: tuple[tuple[object, ...], ...] = ()
        
        # Monitor hotplug detection
        self.screen_count = 0
        self._setup_monitor_detection()
        
        logger.info("DisplayManager initialized (mode=%s, same_image=%s)" % (display_mode, same_image_mode))

        self._publish_display_image_accounting()

    def _publish_display_image_accounting(self) -> None:
        """Publish one immutable, display-deduplicated GUI capture."""

        from rendering.quick.image_accounting import (
            aggregate_presentation_image_accounting,
        )

        self._display_image_accounting_snapshot = aggregate_presentation_image_accounting(
            self._display_image_accounting_by_id.values(),
            generation=self._runtime_generation,
        )
        publisher_ref = self._image_accounting_publisher_ref
        publisher = publisher_ref() if publisher_ref is not None else None
        if publisher is not None:
            publisher(self._display_image_accounting_snapshot)

    def _record_display_image_accounting(self, display: object, snapshot: Any) -> None:
        if self._retired:
            return
        self._display_image_accounting_by_id[id(display)] = snapshot
        self._publish_display_image_accounting()

    def get_image_accounting_snapshot(self):
        """Return the latest GUI-captured aggregate without touching widgets."""

        return self._display_image_accounting_snapshot

    def track_runtime_signal_connection(
        self,
        signal_name: str,
        callback: Any,
    ) -> None:
        """Record one engine-owned outgoing connection for exact retirement."""

        self._runtime_signal_connections.append((str(signal_name), callback))

    def disconnect_runtime_signal_connections(self) -> None:
        """Disconnect each tracked outgoing route exactly once."""

        connections, self._runtime_signal_connections = (
            self._runtime_signal_connections,
            [],
        )
        for signal_name, callback in reversed(connections):
            signal = getattr(self, signal_name, None)
            disconnect = getattr(signal, "disconnect", None)
            if not callable(disconnect):
                continue
            try:
                disconnect(callback)
            except (RuntimeError, TypeError):
                logger.debug(
                    "[DISPLAY_MANAGER] Runtime signal unavailable during retirement signal=%s",
                    signal_name,
                    exc_info=True,
                )
    
    def _setup_monitor_detection(self) -> None:
        """Setup monitor hotplug detection."""
        app = QGuiApplication.instance()
        if app:
            # Connect to screen change signals
            app.screenAdded.connect(self._on_screen_added)
            app.screenRemoved.connect(self._on_screen_removed)
            self._monitor_detection_app = app
            self._monitor_detection_connected = True
            
            # Store initial screen count
            self._screen_signature = self._current_screen_signature()
            self.screen_count = len(self._screen_signature)
            logger.info("Monitor detection enabled (%d screens)" % self.screen_count)

    def disconnect_monitor_detection(self) -> None:
        """Detach this manager from application monitor signals before replacement."""
        app = self._monitor_detection_app
        if app is None or not self._monitor_detection_connected:
            return
        try:
            app.screenAdded.disconnect(self._on_screen_added)
        except Exception:
            logger.debug("[DISPLAY_MANAGER] screenAdded disconnect skipped", exc_info=True)
        try:
            app.screenRemoved.disconnect(self._on_screen_removed)
        except Exception:
            logger.debug("[DISPLAY_MANAGER] screenRemoved disconnect skipped", exc_info=True)
        self._monitor_detection_connected = False
        self._monitor_detection_app = None

    @staticmethod
    def _call_screen_attr(obj: object, name: str, default: object = None) -> object:
        try:
            attr = getattr(obj, name)
        except Exception:
            return default
        try:
            return attr() if callable(attr) else attr
        except Exception:
            return default

    def _screen_signature_part(self, index: int, screen: QScreen) -> tuple[object, ...]:
        geometry = self._call_screen_attr(screen, "geometry")
        available = self._call_screen_attr(screen, "availableGeometry")

        def _geom_part(rect: object) -> tuple[int, int, int, int]:
            if rect is None:
                return (0, 0, 0, 0)
            return (
                int(self._call_screen_attr(rect, "x", 0) or 0),
                int(self._call_screen_attr(rect, "y", 0) or 0),
                int(self._call_screen_attr(rect, "width", 0) or 0),
                int(self._call_screen_attr(rect, "height", 0) or 0),
            )

        dpr = self._call_screen_attr(screen, "devicePixelRatio", 1.0)
        try:
            dpr = round(float(dpr), 3)
        except Exception:
            dpr = 1.0
        return (
            index,
            str(self._call_screen_attr(screen, "name", "")),
            str(self._call_screen_attr(screen, "manufacturer", "")),
            str(self._call_screen_attr(screen, "model", "")),
            str(self._call_screen_attr(screen, "serialNumber", "")),
            _geom_part(geometry),
            _geom_part(available),
            dpr,
        )

    def _current_screen_signature(self) -> tuple[tuple[object, ...], ...]:
        try:
            screens = QGuiApplication.screens()
        except Exception:
            logger.debug("[DISPLAY_MANAGER] Failed to read screen signature", exc_info=True)
            return ()
        return tuple(self._screen_signature_part(index, screen) for index, screen in enumerate(screens))

    def _schedule_monitor_reconcile(self, reason: str) -> None:
        """Coalesce Qt screen churn into one settled topology reconcile.

        Windows display wake can emit screenAdded/screenRemoved while
        QGuiApplication.screens() still reports a stale count.  Rechecking a
        short moment later by full screen signature avoids both missed rebuilds
        and per-event rebuild storms.
        """

        if not self._monitor_detection_connected:
            return
        if self._monitor_reconcile_pending:
            logger.debug("[DISPLAY_MANAGER] Monitor reconcile already pending reason=%s", reason)
            return
        self._monitor_reconcile_pending = True

        manager_ref = weakref.ref(self)

        def _run() -> None:
            manager = manager_ref()
            if manager is None or manager._retired:
                return
            manager._monitor_reconcile_pending = False
            manager._reconcile_monitor_topology(reason)

        _run._srpss_runtime_generation = self._runtime_generation

        if self._thread_manager is None or not hasattr(self._thread_manager, "single_shot"):
            self._monitor_reconcile_pending = False
            logger.warning(
                "[DISPLAY_MANAGER][FALLBACK] Monitor topology reconcile skipped: "
                "ThreadManager single_shot unavailable"
            )
            return

        try:
            self._thread_manager.single_shot(MONITOR_RECONCILE_DELAY_MS, _run)
        except Exception:
            self._monitor_reconcile_pending = False
            logger.warning(
                "[DISPLAY_MANAGER][FALLBACK] Monitor topology reconcile scheduling failed; "
                "ThreadManager single_shot rejected the request",
                exc_info=True,
            )

    def _reconcile_monitor_topology(self, reason: str) -> None:
        if not self._monitor_detection_connected:
            logger.debug("[DISPLAY_MANAGER] Ignoring monitor reconcile after manager disconnect reason=%s", reason)
            return

        old_count = self.screen_count
        old_signature = self._screen_signature
        new_signature = self._current_screen_signature()
        new_count = len(new_signature)
        if new_count == old_count and new_signature == old_signature:
            logger.debug("[DISPLAY_MANAGER] Monitor reconcile no-op reason=%s count=%d", reason, new_count)
            return

        self.screen_count = new_count
        self._screen_signature = new_signature
        logger.info(
            "[DISPLAY_MANAGER] Monitor topology reconciled reason=%s old_count=%d new_count=%d old_signature=%s new_signature=%s",
            reason,
            old_count,
            new_count,
            old_signature,
            new_signature,
        )
        self.monitors_changed.emit(new_count)

    def _get_allowed_screen_indices(self, screen_count: int) -> set[int]:
        """Resolve which screen indices should create Quick display units.

        Uses the canonical display.show_on_monitors setting:
        - 'ALL' (default) means all screens.
        - A list/tuple/set of 1-based monitor indices (e.g. [1, 2]) selects
          specific screens. Values outside the available range are ignored.
        """

        indices: set[int] = set(range(screen_count))
        if self.settings_manager is None:
            return indices

        try:
            raw = self.settings_manager.get('display.show_on_monitors', 'ALL')
        except Exception as e:
            logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
            raw = 'ALL'

        # Default: all screens
        if isinstance(raw, str):
            if raw.upper() == 'ALL':
                return indices
            if raw.upper() == 'NONE':
                return set()
            # Attempt to parse a stringified list such as "[1, 2]"
            try:
                import ast
                parsed = ast.literal_eval(raw)
                if not isinstance(parsed, (list, tuple, set)):
                    return indices
                values = {int(x) for x in parsed}
            except Exception:
                logger.debug("[DISPLAY] Failed to parse show_on_monitors=%r; defaulting to ALL", raw)
                return indices
        elif isinstance(raw, (list, tuple, set)):
            try:
                values = {int(x) for x in raw}
            except Exception:
                logger.debug("[DISPLAY] Invalid show_on_monitors=%r; defaulting to ALL", raw)
                return indices
        else:
            return indices

        # Convert 1-based monitor numbers to 0-based indices and clamp to range
        allowed = {m - 1 for m in values if 1 <= int(m) <= screen_count}
        if not allowed:
            logger.debug("[DISPLAY] Resolved empty show_on_monitors from %r; defaulting to ALL", raw)
            return indices
        logger.info("[DISPLAY] show_on_monitors=%r → allowed screen indices=%s", raw, sorted(allowed))
        return allowed
    
    def _on_screen_added(self, screen: QScreen) -> None:
        """Handle screen added event."""
        logger.info("Screen added: %s (%dx%d)" % (screen.name(), screen.geometry().width(), screen.geometry().height()))
        self._schedule_monitor_reconcile("screenAdded")
    
    def _on_screen_removed(self, screen: QScreen) -> None:
        """Handle screen removed event."""
        logger.info("Screen removed: %s" % screen.name())
        self._schedule_monitor_reconcile("screenRemoved")

    def _quick_window_policy(self) -> QuickWindowPolicy:
        """Resolve the production top-level role without importing QWidget policy."""

        from core.mc import is_mc_build

        if not is_mc_build():
            return QuickWindowPolicy()
        use_splash = (
            os.environ.get("SRPSS_MC_WINDOW_FLAGS", "").strip().lower()
            == "splash"
        )
        always_on_top = True
        if self.settings_manager is not None:
            from core.settings.settings_manager import SettingsManager

            always_on_top = SettingsManager.to_bool(
                self.settings_manager.get("mc.always_on_top", True),
                True,
            )
        return QuickWindowPolicy(
            role=(
                QuickWindowRole.MEDIA_CENTER_SPLASH
                if use_splash
                else QuickWindowRole.MEDIA_CENTER_TOOL
            ),
            always_on_top=always_on_top,
        )

    def _interaction_mode_enabled(self) -> bool:
        from core.mc import is_mc_build

        if is_mc_build():
            return True
        if self.settings_manager is None:
            return False
        from core.settings.settings_manager import SettingsManager

        return SettingsManager.to_bool(
            self.settings_manager.get("input.interaction_mode", False),
            False,
        )

    def _set_quick_interaction_mode_enabled(self, enabled: bool) -> None:
        """Push one Settings/context-menu interaction change to live Quick inputs."""

        normalized = bool(enabled)
        for display in tuple(self.displays):
            if not isinstance(display, QuickDisplayUnit) or display.is_retired:
                continue
            try:
                display.runtime.input_controller.set_interaction_mode_enabled(
                    normalized
                )
            except RuntimeError:
                # A replacement generation can retire between snapshot and push.
                continue

    def _quick_custom_layout_active(self) -> bool:
        return bool(self._quick_custom_layout_owner.is_active)

    def _configure_quick_auxiliary(self, unit: QuickDisplayUnit) -> None:
        """Apply canonical generation-scoped auxiliary state once before show."""

        settings = self.settings_manager
        if settings is None:
            return
        from core.settings.settings_manager import SettingsManager

        auxiliary = unit.runtime.auxiliary_controller
        dimming_enabled = SettingsManager.to_bool(
            settings.get("accessibility.dimming.enabled", False),
            False,
        )
        try:
            dimming_opacity = max(
                10,
                min(90, int(settings.get("accessibility.dimming.opacity", 30))),
            )
        except (TypeError, ValueError):
            dimming_opacity = 30
        auxiliary.set_dimming(dimming_enabled, dimming_opacity / 100.0)
        pixel_shift_enabled = SettingsManager.to_bool(
            settings.get("accessibility.pixel_shift.enabled", False),
            False,
        )
        try:
            pixel_shift_rate = int(
                settings.get("accessibility.pixel_shift.rate", 1)
            )
        except (TypeError, ValueError):
            pixel_shift_rate = 1
        auxiliary.configure_pixel_shift(pixel_shift_enabled, pixel_shift_rate)
        auxiliary.set_halo_shape(settings.get("input.halo_shape", "cursor_light"))

        from core.settings.models import InputSettings
        from ui.widget_glow_style import resolve_widget_glow_color

        input_options = InputSettings.from_settings(settings)
        unit.runtime.input_controller.configure_widget_glow(
            on_hover=input_options.widget_glow_on_hover,
            on_click=input_options.widget_glow_on_click,
            color=resolve_widget_glow_color(input_options.widget_glow_color),
        )

        # The retained context menu is a runtime-scene overlay, so its shadow
        # follows the canonical widget Card shadow contract for this generation.
        # This is one owner-time projection, not a menu-open poll/settings read.
        from rendering.quick.context_menu import (
            project_quick_context_menu_palette,
            project_quick_context_menu_shadow,
        )

        unit.runtime.scene_controller.apply_context_menu_shadow_style(
            project_quick_context_menu_shadow(self._shadow_values_snapshot)
        )
        # Context Menu has no family swatches; consume the active Widget Theme
        # directly once per display generation, alongside the shadow snapshot.
        unit.runtime.scene_controller.apply_context_menu_palette_style(
            project_quick_context_menu_palette()
        )

    def _quick_context_transition_state(
        self,
    ) -> tuple[dict[str, Any], str, bool, bool]:
        """Resolve current transition rows from canonical Settings state."""

        from core.settings.settings_manager import SettingsManager

        defaults = get_default_settings().get("transitions", {})
        transitions = (
            self.settings_manager.get("transitions", {})
            if self.settings_manager is not None
            else defaults
        )
        if not isinstance(transitions, dict):
            transitions = dict(defaults) if isinstance(defaults, dict) else {}
        current = canonicalize_transition_name(
            transitions.get("type"),
            fallback="Crossfade",
        )
        random_enabled = SettingsManager.to_bool(
            transitions.get("random_always", False),
            False,
        )
        hw_enabled = SettingsManager.to_bool(
            self.settings_manager.get("display.hw_accel", False)
            if self.settings_manager is not None
            else False,
            False,
        )
        random_selectable = any(
            is_transition_available_for_hw(name, hw_enabled)
            for name in get_effective_random_pool(transitions)
        )
        return transitions, current, random_enabled, random_selectable

    def _refresh_quick_context_menu(self, unit: QuickDisplayUnit) -> None:
        """Refresh one retained menu from current product authorities."""

        from core.mc import is_mc_build
        from core.settings.settings_manager import SettingsManager

        transitions, current, random_enabled, random_selectable = (
            self._quick_context_transition_state()
        )
        settings = self.settings_manager
        visualizer = self._quick_visualizer_owner
        visualizer_available = bool(
            visualizer is not None
            and visualizer.is_started
            and not visualizer.is_retired
        )
        if visualizer_available:
            from core.settings.visualizer_mode_registry import (
                get_visualizer_mode_descriptor,
                resolve_effective_enabled_modes,
            )

            # V3: the context menu lists only the effective enabled modes, so a
            # disabled mode is not reachable through direct menu selection. With
            # every mode enabled (today's default) this is the full canonical set.
            _vis_model = getattr(visualizer.controller, "settings_model", None)
            _enabled_ids = resolve_effective_enabled_modes(
                getattr(_vis_model, "enabled_modes", None)
            )
            visualizer_modes = tuple(
                (mode_id, get_visualizer_mode_descriptor(mode_id).display_name)
                for mode_id in _enabled_ids
            )
            current_visualizer = str(visualizer.controller.mode_id)
        else:
            visualizer_modes = ()
            current_visualizer = "spectrum"
        dimming_enabled = SettingsManager.to_bool(
            settings.get("accessibility.dimming.enabled", False)
            if settings is not None
            else False,
            False,
        )
        entries = build_quick_context_menu_entries(
            transition_names=get_activated_transition_names(transitions),
            current_transition=current,
            random_enabled=random_enabled,
            random_selectable=random_selectable,
            visualizer_modes=visualizer_modes,
            current_visualizer=current_visualizer,
            visualizer_available=visualizer_available,
            dimming_enabled=dimming_enabled,
            interaction_mode_enabled=self._interaction_mode_enabled(),
            interaction_mode_locked=is_mc_build(),
            edit_mode_active=self._quick_custom_layout_owner.is_active,
            layout_actions_available=self._quick_custom_layout_owner.can_start(),
        )
        unit.configure_context_menu(
            entries,
            action_handler=lambda action_id, payload, display=unit: (
                self._handle_quick_context_action(display, action_id, payload)
            ),
        )

    def _refresh_all_quick_context_menus(self) -> None:
        for display in tuple(self.displays):
            if isinstance(display, QuickDisplayUnit) and not display.is_retired:
                self._refresh_quick_context_menu(display)

    def _enforce_single_quick_context_menu(
        self, opening_unit: QuickDisplayUnit
    ) -> None:
        """Keep exactly one retained context menu visible across all displays.

        Fired when one display's menu becomes visible. Every other live display's
        menu is dismissed so a second display cannot leave a stale menu on screen.
        Only the opening display keeps its menu; retired/absent units are skipped.
        """

        try:
            opened_model = opening_unit.runtime.context_menu_model
        except RuntimeError:
            return
        models = []
        for display in tuple(self.displays):
            if not isinstance(display, QuickDisplayUnit) or display.is_retired:
                continue
            try:
                models.append(display.runtime.context_menu_model)
            except RuntimeError:
                continue
        enforce_single_visible_context_menu(models, opened_model)

    @staticmethod
    def _context_toggle_value(payload: str) -> bool | None:
        normalized = str(payload or "").strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
        return None

    def _handle_quick_context_action(
        self,
        unit: QuickDisplayUnit,
        action_id: str,
        payload: str,
    ) -> bool:
        """Route one admitted retained-menu action to existing product owners."""

        # A retained-menu item is activated by a pointer tap. Because Qt Quick
        # TapHandlers take non-exclusive passive grabs, that same press/release
        # is also recognised by any widget TapHandler (Reddit post, Gmail row)
        # sitting beneath the menu surface - firing its browser-open/exit action
        # in the same gesture. Arm the shared pointer-input guard here, before
        # the action routes and before the menu dismisses, so the phantom widget
        # open that fires microseconds later on the same release is refused. This
        # is the arming site the Reddit open path already checks but that no
        # menu-action boundary previously supplied; the Gmail open path checks it
        # too. It is a passive monotonic-deadline flag, not a timer.
        from rendering.runtime_input import suppress_runtime_pointer_input

        suppress_runtime_pointer_input(700, reason="context_menu_action")

        action = str(action_id or "").strip()
        if action == "previous":
            self.previous_requested.emit()
            return True
        if action == "next":
            self.next_requested.emit()
            return True
        if action == "settings":
            if self._quick_custom_layout_owner.is_active:
                self.cancel_custom_layout_session()
            self.settings_requested.emit()
            return True
        if action == "exit":
            self._on_exit_requested()
            return True

        settings = self.settings_manager
        if settings is None:
            return False
        try:
            if action == "transition":
                transitions = settings.get("transitions", {})
                if not isinstance(transitions, dict):
                    return False
                if not apply_transition_menu_selection(transitions, payload):
                    return False
                settings.set("transitions", transitions)
                settings.save()
                logger.info(
                    "Context menu: transition selection=%s screen=%s",
                    payload,
                    unit.screen_index,
                )
                self._refresh_all_quick_context_menus()
                return True
            if action == "visualizer":
                return self._request_quick_visualizer_mode(payload)
            if action == "edit_layout":
                return self._start_quick_custom_layout_session()
            if action == "save_layout":
                saved = self._quick_custom_layout_owner.save()
                if saved:
                    self._refresh_all_quick_context_menus()
                return saved
            if action == "cancel_layout":
                return self.cancel_custom_layout_session()
            if action == "reset_layout":
                reset = self._quick_custom_layout_owner.reset_to_authored()
                if reset:
                    self._refresh_all_quick_context_menus()
                return reset

            enabled = self._context_toggle_value(payload)
            if enabled is None:
                return False
            if action == "toggle_dimming":
                settings.set("accessibility.dimming.enabled", enabled)
                settings.save()
                try:
                    opacity = max(
                        10,
                        min(
                            90,
                            int(settings.get("accessibility.dimming.opacity", 30)),
                        ),
                    ) / 100.0
                except (TypeError, ValueError):
                    opacity = 0.3
                self.set_dimming_all_displays(enabled, opacity)
                self._refresh_all_quick_context_menus()
                return True
            if action == "toggle_interaction":
                from core.mc import is_mc_build

                persisted = True if is_mc_build() else enabled
                settings.set("input.interaction_mode", persisted)
                settings.save()
                self._set_quick_interaction_mode_enabled(persisted)
                self._refresh_all_quick_context_menus()
                return True
        except Exception:
            logger.error(
                "[CONTEXT_MENU] Quick action failed action=%s screen=%s",
                action,
                unit.screen_index,
                exc_info=True,
            )
            return False

        return False

    def _request_quick_visualizer_mode(self, mode_id: str) -> bool:
        """Resolve and request one canonical activation on the admitted owner."""

        owner = self._quick_visualizer_owner
        settings = self.settings_manager
        if owner is None or settings is None or owner.is_retired:
            return False
        from core.settings.models import SpotifyVisualizerSettings
        from core.settings.visualizer_mode_registry import (
            coerce_visualizer_mode_id,
            is_mode_active,
            resolve_effective_enabled_modes,
        )
        from core.settings.visualizer_presets import (
            resolve_visualizer_activation_payload,
        )
        from widgets.spotify_visualizer.technical_config import build_technical_cache

        target = str(mode_id or "").strip().lower()
        if coerce_visualizer_mode_id(target) != target or not is_mode_active(target):
            return False
        section = settings.get("widgets.spotify_visualizer", {})
        if not isinstance(section, dict):
            return False
        # Deepest request-admission gate (pre-V5/V6): a normal runtime/UI request
        # must never silently route to, or re-enable, a mode outside the effective
        # enabled set — that would create a second enable authority. Startup/stale
        # persisted selection substitutes at the startup resolver with an explicit
        # log; this seam rejects instead. With every mode enabled (today's
        # default) this never rejects.
        enabled_modes = resolve_effective_enabled_modes(section.get("enabled_modes"))
        if target not in enabled_modes:
            logger.info(
                "[VISUALIZER] Rejected runtime request for disabled mode=%s "
                "(enabled=%s)",
                target,
                ",".join(enabled_modes),
            )
            return False
        candidate = dict(section)
        candidate["mode"] = target
        activation = resolve_visualizer_activation_payload(candidate)
        model = SpotifyVisualizerSettings.from_mapping(
            activation.resolved_config,
            apply_preset_overlay=False,
            resolve_preset_indices=False,
        )
        technical_cache = build_technical_cache(None, model)
        return bool(
            owner.request_mode_change(
                target,
                settings_model=model,
                resolved_activation=activation,
                technical_cache=technical_cache,
                logical_kwargs=asdict(model),
                presentation_kwargs=asdict(model),
                on_complete=self._complete_quick_visualizer_mode_change,
            )
        )

    def _cycle_quick_visualizer_mode(self) -> None:
        owner = self._quick_visualizer_owner
        if owner is None or owner.is_retired:
            return
        from rendering.quick.visualizer.double_click_admission import (
            next_visualizer_mode_id,
        )

        # Cycle only the effective enabled modes (V3): a disabled mode must never
        # be reachable by double-click/context-menu cycling.
        model = getattr(owner.controller, "settings_model", None)
        enabled_modes = getattr(model, "enabled_modes", None)
        self._request_quick_visualizer_mode(
            next_visualizer_mode_id(owner.controller.mode_id, enabled_modes)
        )

    def _request_quick_visualizer_preset_change(self) -> bool:
        """Resolve one detached same-mode preset target on the admitted owner."""

        owner = self._quick_visualizer_owner
        settings = self.settings_manager
        if owner is None or settings is None or owner.is_retired:
            return False

        from core.settings.models import SpotifyVisualizerSettings
        from core.settings.visualizer_presets import (
            VISUALIZER_CUSTOM_STORAGE_KEY,
            resolve_visualizer_activation_payload,
        )
        from core.settings.visualizer_runtime_preset_cycle import (
            resolve_next_visualizer_runtime_preset,
        )
        from widgets.spotify_visualizer.technical_config import build_technical_cache

        section = settings.get("widgets.spotify_visualizer", {})
        custom_presets = settings.get(VISUALIZER_CUSTOM_STORAGE_KEY, {})
        if not isinstance(section, Mapping) or not isinstance(custom_presets, Mapping):
            logger.warning(
                "[VIS_PRESETS] Quick preset cycle rejected malformed settings roots"
            )
            return False
        try:
            target = resolve_next_visualizer_runtime_preset(
                section,
                custom_presets,
                mode=owner.controller.mode_id,
            )
            activation = resolve_visualizer_activation_payload(
                target.visualizer_config,
                mode=target.mode,
            )
            model = SpotifyVisualizerSettings.from_mapping(
                activation.resolved_config,
                apply_preset_overlay=False,
                resolve_preset_indices=False,
            )
            technical_cache = build_technical_cache(None, model)
        except (TypeError, ValueError):
            logger.warning(
                "[VIS_PRESETS] Quick preset cycle resolution failed mode=%s",
                owner.controller.mode_id,
                exc_info=True,
            )
            return False

        return bool(
            owner.request_preset_change(
                target.mode,
                settings_model=model,
                resolved_activation=activation,
                technical_cache=technical_cache,
                logical_kwargs=asdict(model),
                presentation_kwargs=asdict(model),
                on_complete=(
                    lambda completed_mode, expected_owner=owner, resolved=target:
                    self._complete_quick_visualizer_preset_change(
                        completed_mode,
                        expected_owner=expected_owner,
                        target=resolved,
                    )
                ),
            )
        )

    def _cycle_quick_visualizer_preset(self) -> None:
        self._request_quick_visualizer_preset_change()

    def _complete_quick_visualizer_mode_change(self, mode_id: str) -> None:
        """Persist one fully presented target activation and refresh menu truth."""

        settings = self.settings_manager
        if settings is None:
            raise RuntimeError("visualizer mode completion has no Settings authority")
        settings.set("widgets.spotify_visualizer.mode", str(mode_id))
        settings.save()
        section = self._widgets_config_snapshot.get("spotify_visualizer")
        if isinstance(section, dict):
            section["mode"] = str(mode_id)
        self._refresh_all_quick_context_menus()
        logger.info("[SPOTIFY_VIS] Persisted Quick visualizer mode=%s", mode_id)

    def _complete_quick_visualizer_preset_change(
        self,
        mode_id: str,
        *,
        expected_owner: Any,
        target: Any,
    ) -> None:
        """Persist only a fresh, fully visible same-owner preset activation."""

        owner = self._quick_visualizer_owner
        if (
            owner is not expected_owner
            or owner is None
            or owner.is_retired
            or str(mode_id) != str(target.mode)
            or owner.controller.mode_id != str(target.mode)
        ):
            logger.warning(
                "[VIS_PRESETS] Dropped stale Quick preset completion mode=%s target=%s",
                mode_id,
                getattr(target, "mode", None),
            )
            return
        settings = self.settings_manager
        if settings is None:
            raise RuntimeError("visualizer preset completion has no Settings authority")
        persist = getattr(
            settings,
            "replace_visualizer_runtime_preset_state",
            None,
        )
        if not callable(persist):
            raise RuntimeError(
                "Settings authority has no atomic visualizer preset persistence"
            )
        persist(target.visualizer_config, target.custom_presets)
        self._widgets_config_snapshot["spotify_visualizer"] = deepcopy(
            target.visualizer_config
        )
        self._refresh_all_quick_context_menus()
        logger.info(
            "[VIS_PRESETS] Persisted Quick preset mode=%s source=%s target=%s custom_cache_changed=%s",
            target.mode,
            target.source_index,
            target.target_index,
            target.custom_presets_changed,
        )

    def _connect_quick_runtime(
        self,
        unit: QuickDisplayUnit,
        *,
        startup_generation: int,
    ) -> None:
        """Connect one unit's explicit runtime events to product orchestration."""

        runtime = unit.runtime
        screen_index = int(unit.screen_index)
        runtime.exit_requested.connect(self._on_exit_requested)
        runtime.previous_requested.connect(self.previous_requested.emit)
        runtime.next_requested.connect(self.next_requested.emit)
        runtime.cycle_transition_requested.connect(
            self.cycle_transition_requested.emit
        )
        runtime.settings_requested.connect(self.settings_requested.emit)
        runtime.context_menu_requested.connect(
            lambda _position, display=unit: self._refresh_quick_context_menu(
                display
            )
        )
        # Exactly one product context menu globally: when this display's retained
        # menu becomes visible, retire any menu still open on another display.
        runtime.context_menu_model.visibilityChanged.connect(
            lambda visible, opening=unit: self._enforce_single_quick_context_menu(
                opening
            )
            if visible
            else None
        )
        runtime.play_pause_requested.connect(
            lambda display=unit: display.request_media_transport("play")
        )
        runtime.home_play_pause_requested.connect(
            lambda display=unit: display.request_media_transport("play")
        )
        runtime.previous_track_requested.connect(
            lambda display=unit: display.request_media_transport("prev")
        )
        runtime.next_track_requested.connect(
            lambda display=unit: display.request_media_transport("next")
        )
        runtime.slider_volume_up_requested.connect(
            lambda display=unit: display.request_app_volume_step(+1)
        )
        runtime.slider_volume_down_requested.connect(
            lambda display=unit: display.request_app_volume_step(-1)
        )
        runtime.global_volume_up_requested.connect(
            lambda display=unit: display.request_system_volume_step(+0.05)
        )
        runtime.global_volume_down_requested.connect(
            lambda display=unit: display.request_system_volume_step(-0.05)
        )
        runtime.global_mute_toggle_requested.connect(
            lambda display=unit: display.request_system_mute_toggle()
        )
        runtime.layout_slot_load_requested.connect(self._load_layout_slot)
        runtime.layout_slot_save_requested.connect(self._save_layout_slot)
        runtime.custom_layout_save_requested.connect(
            self._save_quick_custom_layout
        )
        runtime.custom_layout_cancel_requested.connect(
            self.cancel_custom_layout_session
        )
        runtime.transition_finalized.connect(
            lambda completion, display=unit: self._on_quick_transition_finalized(
                display,
                completion,
            )
        )
        runtime.readiness_changed.connect(
            lambda readiness, display=unit, generation=startup_generation: self._on_quick_readiness_changed(
                display,
                readiness,
                generation,
            )
        )
        runtime.display_identity_changed.connect(
            lambda _identity, display=unit: display.reanchor_for_current_bounds()
        )
        runtime.topology_loss_detected.connect(
            lambda _loss: self._schedule_monitor_reconcile("quick_binding_loss")
        )
        runtime.retirement_completed.connect(
            lambda _generation, idx=screen_index: self._on_quick_runtime_retired(idx)
        )
        self._quick_readiness_by_screen[screen_index] = runtime.scene_readiness

    def _request_custom_layout_runtime_reload(self, request_kind: str) -> None:
        """Publish one manager-identity-fenced runtime layout reload request."""

        generation = self._runtime_generation
        self.custom_layout_reload_requested.emit(
            str(request_kind),
            int(generation) if generation is not None else -1,
            int(id(self)),
        )

    def _set_quick_authored_layout_enabled(
        self,
        enabled: bool,
        *,
        restore_base: bool = True,
    ) -> None:
        """Switch the authored stacking/adjacency subsystem at an event edge.

        CUSTOM is global. This is the single manager-level switch used by the
        live edit transaction and layout-slot reload path; persisted/effective
        CUSTOM is also enforced independently by each presenter's construction
        snapshot. There is no timer, polling loop or render-cadence owner here.
        """

        target = bool(enabled)
        visualizer_unit = self._quick_visualizer_unit
        for unit in tuple(self.displays):
            if not isinstance(unit, QuickDisplayUnit) or unit.is_retired:
                continue
            if not target:
                # Make dormant mean dormant: detach the stronger ordinary
                # relationship snapshot as well as disabling generic packing.
                # Cancel/recreation reinstalls it from current retained state.
                unit.presenter.set_layout_observer(None)
                unit.presenter.set_external_stack_obstacles(None, reflow=False)
            # On re-enable, defer the chosen Visualizer display's reflow until
            # its stronger Media+Visualizer obstacle snapshot is restored.
            unit.presenter.set_authored_layout_enabled(
                target,
                restore_base=restore_base,
                reflow=target and unit is not visualizer_unit,
            )

        if not target:
            # Adjacency is not merely paused: project the Visualizer back onto
            # its plain authored Media slot so CUSTOM starts from overlap-legal
            # authored geometry rather than carrying an ordinary adjacency
            # displacement into the global CUSTOM mode. Committed Visualizer
            # CUSTOM geometry rejects this projection inside its owner.
            self._project_quick_visualizer_base_authored_origin()
            return

        owner = self._quick_visualizer_owner
        chosen = self._quick_visualizer_unit
        if owner is None or chosen is None or chosen.is_retired:
            return
        if not self._install_quick_visualizer_authored_layout(
            chosen,
            owner,
            install_observer=True,
        ):
            # No ordinary adjacency applies (for example persisted CUSTOM). If
            # the presenter is otherwise eligible, allow its generic pack once.
            chosen.presenter.set_authored_layout_enabled(
                True,
                restore_base=False,
                reflow=True,
            )

    def _authored_layout_allowed_by_settings(self) -> bool:
        """Return whether the persisted/effective widgets map is non-CUSTOM."""

        settings = self.settings_manager
        if settings is None:
            return True
        try:
            widgets = settings.get_widgets_map()
        except Exception:
            logger.warning(
                "[CUSTOM_LAYOUT] Failed to inspect persisted layout mode",
                exc_info=True,
            )
            return False
        from rendering.widget_descriptors import is_global_custom_layout_mode_selected

        return not is_global_custom_layout_mode_selected(widgets)

    def _start_quick_custom_layout_session(self) -> bool:
        """Enter global CUSTOM edit mode with authored layout fully dormant."""

        if self._quick_custom_layout_owner.is_active:
            return True
        # Disable before the owner captures session geometry. This removes any
        # generic stack projection and prevents Media preferred-size callbacks
        # from reasserting ordinary adjacency under the edit transaction.
        self._set_quick_authored_layout_enabled(False, restore_base=True)
        try:
            started = self._quick_custom_layout_owner.start()
        except Exception:
            if self._authored_layout_allowed_by_settings():
                self._set_quick_authored_layout_enabled(True, restore_base=False)
            raise
        if not started:
            if self._authored_layout_allowed_by_settings():
                self._set_quick_authored_layout_enabled(True, restore_base=False)
            return False
        self._refresh_all_quick_context_menus()
        return True

    def _save_quick_custom_layout(self) -> bool:
        saved = self._quick_custom_layout_owner.save()
        if saved:
            # Save requests a generation-fenced rebuild. Keep authored layout
            # dormant in the retiring generation; the replacement generation
            # derives its own global CUSTOM state from persisted settings.
            self._refresh_all_quick_context_menus()
        return saved

    def cancel_custom_layout_session(self) -> bool:
        """Cancel CUSTOM and restore authored layout only when globally eligible."""

        cancelled = self._quick_custom_layout_owner.cancel()
        if cancelled:
            if self._authored_layout_allowed_by_settings():
                self._set_quick_authored_layout_enabled(True, restore_base=False)
            self._refresh_all_quick_context_menus()
        return cancelled

    def _save_layout_slot(self, slot_id: str) -> bool:
        """Persist one source-free layout slot through SettingsManager."""

        settings = self.settings_manager
        if settings is None:
            return False
        custom_save_completed = False
        try:
            if self._quick_custom_layout_owner.is_active:
                if not self._quick_custom_layout_owner.save(
                    defer_topology_reconciliation=True
                ):
                    return False
                custom_save_completed = True
            from core.settings.layout_slots import save_layout_slot

            widgets_map = settings.get_widgets_map()
            if not save_layout_slot(widgets_map, slot_id):
                logger.info(
                    "[LAYOUT_SLOT] Ignored invalid Quick layout slot save: %s",
                    slot_id,
                )
                return False
            settings.set_widgets_map(widgets_map, emit_change=False)
            settings.save()
            logger.info("[LAYOUT_SLOT] Saved Quick layout slot %s", slot_id)
            return True
        except Exception:
            logger.error(
                "[LAYOUT_SLOT] Quick layout slot save failed: %s",
                slot_id,
                exc_info=True,
            )
            return False
        finally:
            if custom_save_completed:
                topology_reason = (
                    self._quick_custom_layout_owner.take_deferred_topology_reconciliation()
                )
                if topology_reason is not None:
                    logger.info(
                        "[LAYOUT_SLOT] Reconcile persisted CUSTOM topology after slot attempt reason=%s",
                        topology_reason,
                    )
                    self._request_custom_layout_runtime_reload("save_continue")

    def _load_layout_slot(self, slot_id: str) -> bool:
        """Apply one saved layout slot and request a fenced runtime rebuild."""

        settings = self.settings_manager
        if settings is None:
            return False
        try:
            from core.settings.layout_slots import apply_layout_slot

            widgets_map = settings.get_widgets_map()
            if not apply_layout_slot(widgets_map, slot_id):
                logger.info(
                    "[LAYOUT_SLOT] Empty or invalid Quick layout slot load: %s",
                    slot_id,
                )
                return False

            # Number-key slot loading is a third CUSTOM entry path. Quiesce the
            # authored subsystem before ending any live edit transaction and
            # before the fenced runtime rebuild, regardless of whether this
            # particular slot resolves to authored or CUSTOM. The replacement
            # generation derives the exact target mode from the applied map.
            self._set_quick_authored_layout_enabled(False, restore_base=True)
            if self._quick_custom_layout_owner.is_active:
                self._quick_custom_layout_owner.cancel()
            settings.set_widgets_map(widgets_map, emit_change=False)
            settings.save()
            logger.info("[LAYOUT_SLOT] Loaded Quick layout slot %s", slot_id)
            self._request_custom_layout_runtime_reload("slot_load")
            return True
        except Exception:
            logger.error(
                "[LAYOUT_SLOT] Quick layout slot load failed: %s",
                slot_id,
                exc_info=True,
            )
            return False

    def _on_quick_readiness_changed(
        self,
        unit: QuickDisplayUnit,
        readiness: object,
        startup_generation: int,
    ) -> None:
        if not isinstance(readiness, QuickSceneReadiness):
            raise TypeError("Quick runtime emitted invalid readiness state")
        if (
            startup_generation != self._display_startup_generation
            or unit not in self.displays
            or readiness.runtime_generation != self._runtime_generation
            or readiness.screen_index != unit.screen_index
        ):
            return
        self._quick_readiness_by_screen[unit.screen_index] = readiness
        if readiness.error is not None or readiness.scene_graph_invalidated:
            logger.error(
                "[DISPLAY] Quick readiness failed screen=%s state=%s",
                unit.screen_index,
                readiness.as_dict(),
            )
            return
        if readiness.qml_root_created and readiness.admission_open:
            self._mark_display_startup_ready(unit, startup_generation)
        if (
            readiness.ready_for_reveal
            and unit.screen_index in self._authoritative_first_frame_screens
        ):
            self._mark_startup_reveal_ready(unit.screen_index)

    def _on_quick_runtime_retired(self, screen_index: int) -> None:
        self._retiring_quick_units.pop(int(screen_index), None)
        if self._retiring_quick_units:
            return
        self._quick_ctrl_coordinator.reset()
        if self._retire_manager_when_quick_complete:
            self.deleteLater()

    def _begin_quick_unit_retirement(self, unit: QuickDisplayUnit) -> bool:
        """Retain one unit until its asynchronous runtime retirement completes."""

        screen_index = int(unit.screen_index)
        existing = self._retiring_quick_units.get(screen_index)
        if existing is not None and existing is not unit:
            raise RuntimeError(
                f"screen {screen_index} already has a retiring Quick display unit"
            )
        self._retiring_quick_units[screen_index] = unit
        try:
            started = unit.retire()
        except Exception:
            if not unit.is_retired:
                self._retiring_quick_units.pop(screen_index, None)
            raise
        if not started and not unit.is_retired:
            self._retiring_quick_units.pop(screen_index, None)
            raise RuntimeError(
                f"Quick display unit retirement did not start for screen {screen_index}"
            )
        return started
    
    def initialize_displays(self) -> int:
        """
        Create and show the one authoritative Quick unit for each selected monitor.
        
        Returns:
            Number of displays created
        """
        screens = QGuiApplication.screens()
        screen_count = len(screens)
        
        logger.info("Initializing displays for %d screens" % screen_count)
        
        if (
            self.displays
            or self._retiring_quick_units
            or self._quick_scene_factory is not None
        ):
            raise RuntimeError(
                "Quick display replacement requires a retired manager/destruction barrier"
            )
        self._display_startup_generation += 1
        startup_generation = self._display_startup_generation

        self._quick_scene_factory = QuickSceneFactory(parent=self)
        self._quick_ctrl_coordinator.reset()
        self._quick_readiness_by_screen.clear()
        if self.settings_manager is not None:
            self._widgets_config_snapshot = self.settings_manager.get_widgets_map()
            from core.settings.models import ShadowSettings
            from core.settings.shadow_direction import get_shadow_direction

            self._shadow_values_snapshot = asdict(
                ShadowSettings.from_settings(self.settings_manager)
            )
            self._shadow_values_snapshot["direction"] = get_shadow_direction(
                self.settings_manager
            ).value
        else:
            self._widgets_config_snapshot = {}
            self._shadow_values_snapshot = {}

        # Resolve which screens should actually create one Quick display unit.
        allowed_indices = self._get_allowed_screen_indices(screen_count)
        
        # Instantiate the full active display set before the first display runs
        # widget setup. Visualizer CUSTOM owner selection is participation-based,
        # so screen 0 must be able to see later requested displays as pending
        # startup instead of misclassifying them as absent.
        pending_displays: list[QuickDisplayUnit] = []
        for i in range(screen_count):
            if i in allowed_indices:
                display = self._create_display_for_screen(i, show_immediately=False)
                if display is not None:
                    pending_displays.append(display)
            else:
                logger.info(
                    "[DISPLAY] Skipping display for screen %d due to show_on_monitors",
                    i,
                )

        self._display_startup_ready_expected = {id(display) for display in pending_displays}
        self._display_startup_ready_seen = set()
        self._display_startup_ready_emitted_generation = -1

        self._admit_quick_visualizer(pending_displays)
        self._prime_quick_startup_desktop_sources(pending_displays)
        self._prepare_quick_startup_reveal(pending_displays)

        # Preserve staggered show behavior without processEvents() re-entry.
        # Display registration happens before this loop, so visualizer owner
        # selection sees the full active set while the expensive show/GL startup
        # work is still spread across UI turns. The generation guard prevents a
        # delayed show from firing after settings/edit cleanup has replaced the
        # display set.
        stagger_ms = 100
        for idx, display in enumerate(pending_displays):
            delay_ms = idx * stagger_ms
            if delay_ms <= 0:
                self._show_display_widget(display, startup_generation=startup_generation)
                continue

            manager_ref = weakref.ref(self)
            display_ref = weakref.ref(display)

            def _show_if_current(
                generation: int = startup_generation,
            ) -> None:
                manager = manager_ref()
                disp = display_ref()
                if manager is None or disp is None or manager._retired:
                    return
                if generation != manager._display_startup_generation:
                    logger.debug(
                        "[DISPLAY] Suppressed stale staggered show for screen %s",
                        getattr(disp, "screen_index", "?"),
                    )
                    return
                if disp not in manager.displays:
                    logger.debug(
                        "[DISPLAY] Suppressed staggered show for removed screen %s",
                        getattr(disp, "screen_index", "?"),
                    )
                    return
                manager._show_display_widget(disp, startup_generation=generation)

            _show_if_current._srpss_runtime_generation = self._runtime_generation

            try:
                from core.threading.manager import ThreadManager

                scheduler = self._thread_manager or ThreadManager
                scheduler.single_shot(delay_ms, _show_if_current)
            except Exception:
                logger.warning(
                    "[DISPLAY][FALLBACK] Stagger scheduler unavailable; showing screen %s immediately",
                    getattr(display, "screen_index", "?"),
                    exc_info=True,
                )
                self._show_display_widget(display, startup_generation=startup_generation)
        
        logger.info("Created %d Quick display units" % len(self.displays))
        return len(self.displays)

    @staticmethod
    def _requested_visualizer_screen_index(monitor: object) -> int:
        """Resolve the 1-based persisted monitor route; ALL means first live."""

        normalized = str(monitor or "ALL").strip().upper()
        if normalized == "ALL":
            return -1
        try:
            monitor_number = int(normalized)
        except (TypeError, ValueError):
            logger.warning(
                "[SPOTIFY_VIS] Invalid Quick monitor route %r; using first participant",
                monitor,
            )
            return -1
        if monitor_number < 1:
            logger.warning(
                "[SPOTIFY_VIS] Invalid Quick monitor route %r; using first participant",
                monitor,
            )
            return -1
        return monitor_number - 1

    @classmethod
    def _resolve_visualizer_requested_screen_index(cls, widgets: object) -> int:
        """Resolve the visualizer's canonical effective monitor route.

        Delegates to the descriptor/effective-routing authority so the product
        contract is honoured without duplicating it here: outside CUSTOM the
        ``spotify_visualizer`` edge follows Media's effective monitor route, while
        CUSTOM ownership makes the visualizer's own persisted monitor route
        authoritative. The resolved ``ALL``/1-based value is normalised to a
        zero-based requested screen index (``ALL`` -> first participant).
        """

        from rendering.widget_descriptors import (
            get_effective_monitor_value_for_widget,
        )

        effective_monitor = get_effective_monitor_value_for_widget(
            "spotify_visualizer",
            widgets if isinstance(widgets, dict) else {},
            default="ALL",
        )
        return cls._requested_visualizer_screen_index(effective_monitor)

    def _set_quick_visualizer_construct_outcome(
        self,
        result: str,
        reject_reason: str | None = None,
    ) -> None:
        """Retain one bounded construction outcome for the generation trace."""

        self._quick_visualizer_construct_result = str(result)
        self._quick_visualizer_construct_reject_reason = (
            None if reject_reason is None else str(reject_reason)
        )

    def _log_quick_visualizer_routing_trace(
        self,
        participants: list[QuickDisplayUnit],
        *,
        chosen: QuickDisplayUnit | None,
        construct_result: str,
        reject_reason: str | None,
    ) -> None:
        """Emit one bounded, generation-level Visualizer routing record."""

        if getattr(self, "_quick_visualizer_routing_trace_emitted", False):
            return
        self._quick_visualizer_routing_trace_emitted = True

        from rendering.quick.visualizer_failover import (
            get_visualizer_failover_state,
        )
        from rendering.widget_descriptors import (
            get_effective_monitor_value_for_widget,
            is_custom_position_selected_for_widget,
        )

        widgets = (
            self._widgets_config_snapshot
            if isinstance(self._widgets_config_snapshot, dict)
            else {}
        )
        section = widgets.get("spotify_visualizer", {})
        if not isinstance(section, Mapping):
            section = {}
        media = widgets.get("media", {})
        if not isinstance(media, Mapping):
            media = {}
        effective_monitor = get_effective_monitor_value_for_widget(
            "spotify_visualizer",
            widgets,
            default="ALL",
        )
        requested = self._requested_visualizer_screen_index(effective_monitor)
        custom = bool(
            is_custom_position_selected_for_widget("spotify_visualizer", widgets)
        )

        participant_state: list[dict[str, object]] = []
        for unit in participants:
            probe = getattr(unit, "is_visualizer_participant", None)
            try:
                participating = bool(probe()) if callable(probe) else False
            except Exception:
                participating = False
            runtime = getattr(unit, "runtime", None)
            binding_loss = getattr(runtime, "binding_loss", None)
            if binding_loss is None:
                binding_loss_state = None
            else:
                as_dict = getattr(binding_loss, "as_dict", None)
                try:
                    binding_loss_state = (
                        as_dict() if callable(as_dict) else type(binding_loss).__name__
                    )
                except Exception:
                    binding_loss_state = type(binding_loss).__name__
            participant_state.append(
                {
                    "screen": getattr(unit, "screen_index", None),
                    "participating": participating,
                    "binding_loss": binding_loss_state,
                }
            )

        failover_record = get_visualizer_failover_state().get_visualizer_failover()
        if failover_record is None:
            failover_state = None
        else:
            failover_host = failover_record.get("host")
            failover_state = {
                "target": failover_record.get("intended_index"),
                "pending": bool(failover_record.get("pending", False)),
                "generation": failover_record.get("generation"),
                "fallback": getattr(failover_host, "screen_index", None),
            }

        selected = chosen if chosen is not None else self._quick_visualizer_unit
        logger.info(
            "[VIS_ROUTING] runtime_generation=%s spotify_enabled=%r "
            "spotify_visualizers_enabled=%r spotify_position=%r spotify_monitor=%r "
            "media_enabled=%r media_position=%r media_monitor=%r custom=%s "
            "effective_monitor=%r requested_screen=%s participants=%s failover=%s "
            "chosen_screen=%s construct_result=%s reject_reason=%s",
            self._runtime_generation,
            section.get("enabled"),
            section.get("visualizers_enabled"),
            section.get("position"),
            section.get("monitor"),
            media.get("enabled"),
            media.get("position"),
            media.get("monitor"),
            custom,
            effective_monitor,
            requested,
            participant_state,
            failover_state,
            getattr(selected, "screen_index", None),
            construct_result,
            reject_reason,
        )

    def _admit_quick_visualizer(
        self,
        participants: list[QuickDisplayUnit],
    ) -> bool:
        """Admit the one Quick visualizer owner, honouring CUSTOM failover.

        Non-CUSTOM routing (and CUSTOM ``ALL``) admits immediately on the
        canonical effective monitor route. A CUSTOM route to a SPECIFIC monitor
        engages the durable failover/reclaim lifecycle: admit immediately when
        that monitor participates, otherwise arm ONE 30 s grace (never an
        immediate fallback) before a single temporary fallback owner. Topology
        returns rebuild the generation and re-admit, which is the reclaim point.
        """

        if self._quick_visualizer_owner is not None:
            raise RuntimeError("Quick visualizer owner already admitted")
        self._set_quick_visualizer_construct_outcome("not_attempted")

        def _finish(
            admitted: bool,
            *,
            chosen: QuickDisplayUnit | None = None,
            result: str | None = None,
            reason: str | None = None,
        ) -> bool:
            resolved_result = result or self._quick_visualizer_construct_result
            if admitted:
                resolved_result = "admitted"
                reason = None
            elif reason is None:
                reason = self._quick_visualizer_construct_reject_reason
            self._log_quick_visualizer_routing_trace(
                participants,
                chosen=chosen,
                construct_result=resolved_result,
                reject_reason=reason,
            )
            return admitted

        widgets = self._widgets_config_snapshot
        section = widgets.get("spotify_visualizer", {})
        if not isinstance(section, dict):
            return _finish(
                False,
                result="rejected",
                reason="invalid_visualizer_section",
            )
        if not is_widget_family_effective(widgets, "visualizers"):
            return _finish(
                False,
                result="rejected",
                reason="visualizer_capability_not_effective",
            )

        from rendering.widget_descriptors import (
            is_custom_position_selected_for_widget,
        )

        requested = self._resolve_visualizer_requested_screen_index(widgets)
        custom = bool(
            is_custom_position_selected_for_widget("spotify_visualizer", widgets)
        )

        if custom and requested >= 0:
            # Durable CUSTOM failover/reclaim (E2.7): drive the presentation-neutral
            # lifecycle over the Quick ownership topology. Start each generation
            # from a clean failover record so a fresh outage arms a fresh grace
            # generation.
            from rendering.quick.visualizer_failover import (
                get_visualizer_failover_state,
            )
            from rendering.quick.visualizer_failover_lifecycle import (
                reconcile_custom_visualizer,
            )

            get_visualizer_failover_state().clear_visualizer_failover()
            self._quick_visualizer_failover_token = 0
            try:
                reconcile_custom_visualizer(
                    _QuickVisualizerFailoverTopology(self, participants)
                )
            except Exception as exc:
                if self._quick_visualizer_construct_result != "exception":
                    self._set_quick_visualizer_construct_outcome(
                        "exception",
                        f"custom_reconcile_raised_{type(exc).__name__}",
                    )
                _finish(False)
                raise
            admitted = self._quick_visualizer_owner is not None
            if admitted:
                return _finish(True, chosen=self._quick_visualizer_unit)
            failover_record = (
                get_visualizer_failover_state().get_visualizer_failover()
            )
            if failover_record is not None and bool(
                failover_record.get("pending", False)
            ):
                return _finish(
                    False,
                    result="pending_grace",
                    reason="requested_custom_display_not_participating",
                )
            return _finish(False)

        from rendering.quick.visualizer_admission import (
            resolve_quick_visualizer_owner_unit,
        )

        chosen = resolve_quick_visualizer_owner_unit(requested, participants)
        if chosen is None:
            logger.warning(
                "[SPOTIFY_VIS] No participating Quick display admits the visualizer"
            )
            return _finish(
                False,
                result="rejected",
                reason="no_participating_quick_display",
            )
        try:
            admitted = self._construct_quick_visualizer_owner_on(chosen)
        except Exception as exc:
            if self._quick_visualizer_construct_result != "exception":
                self._set_quick_visualizer_construct_outcome(
                    "exception",
                    f"construct_raised_{type(exc).__name__}",
                )
            _finish(False, chosen=chosen)
            raise
        return _finish(admitted, chosen=chosen)

    def _resolve_quick_visualizer_base_authored_origin(
        self,
        chosen: QuickDisplayUnit,
        owner: Any,
    ) -> tuple[float, float] | None:
        """Resolve the Visualizer's plain authored anchor without adjacency.

        This is the CUSTOM-safe baseline: the Visualizer still follows Media's
        effective authored position/monitor route, but no stacking or
        Media-relative displacement is applied. A committed Visualizer CUSTOM
        rect remains authoritative inside the owner and rejects this projection.
        """

        bounds = chosen.display_bounds()
        try:
            vis_width, vis_height = owner.resolved_outer_size()
        except Exception:
            logger.warning(
                "[SPOTIFY_VIS] Failed to resolve base authored visualizer size",
                exc_info=True,
            )
            return None
        vis_width = max(1.0, min(float(vis_width), float(bounds.width)))
        vis_height = max(1.0, min(float(vis_height), float(bounds.height)))

        from rendering.quick.widgets.geometry_resolver import (
            resolve_overlay_geometry_policy,
        )

        base = resolve_overlay_geometry_policy(
            "media",
            self._widgets_config_snapshot,
        ).resolve((vis_width, vis_height), bounds)
        return (float(base.x - bounds.x), float(base.y - bounds.y))

    def _project_quick_visualizer_base_authored_origin(self) -> bool:
        """Project the plain authored Visualizer origin once, if admitted."""

        owner = self._quick_visualizer_owner
        chosen = self._quick_visualizer_unit
        if owner is None or chosen is None or chosen.is_retired:
            return False
        origin = self._resolve_quick_visualizer_base_authored_origin(chosen, owner)
        if origin is None:
            return False
        return bool(owner.set_authored_outer_origin(origin[0], origin[1]))

    def _resolve_quick_visualizer_authored_layout(
        self,
        chosen: QuickDisplayUnit,
        owner: Any,
        *,
        media_geometry: Any | None = None,
    ) -> tuple[float, float, float, float, Any] | None:
        """Resolve the ordinary Media-relative Visualizer rectangle once.

        CUSTOM is a hard boundary and returns ``None``. Ordinary placement uses
        the Media card's unstacked authored geometry, preferring the vertical
        side with more usable space (top Media -> below, bottom Media -> above).
        Horizontal adjacency is only a fallback when neither vertical side can
        fit. No timer/poller/cadence owner is involved.
        """

        from rendering.widget_descriptors import is_global_custom_layout_mode_selected

        widgets = self._widgets_config_snapshot
        if (
            not chosen.presenter.authored_layout_enabled
            or is_global_custom_layout_mode_selected(widgets)
        ):
            return None
        bounds = chosen.display_bounds()
        try:
            vis_width, vis_height = owner.resolved_outer_size()
        except Exception:
            logger.warning(
                "[SPOTIFY_VIS] Failed to resolve ordinary visualizer size for adjacency",
                exc_info=True,
            )
            return None
        vis_width = max(1.0, min(float(vis_width), float(bounds.width)))
        vis_height = max(1.0, min(float(vis_height), float(bounds.height)))

        media_rect = media_geometry or chosen.presenter.authored_geometry_for("media")
        if media_rect is None:
            # Visualizer routing follows Media's authored route even when the
            # Media *card* itself is disabled and therefore has no retained
            # preferred-size rectangle. Resolve the Visualizer at that same
            # authored anchor using its own current outer size. This is still
            # ordinary/non-CUSTOM placement and owns no cadence.
            from rendering.quick.widgets.geometry_resolver import (
                resolve_overlay_geometry_policy,
            )

            fallback = resolve_overlay_geometry_policy("media", widgets).resolve(
                (vis_width, vis_height), bounds
            )
            return (
                float(fallback.x - bounds.x),
                float(fallback.y - bounds.y),
                vis_width,
                vis_height,
                None,
            )

        gap = 20.0
        media_x = float(media_rect.x - bounds.x)
        media_y = float(media_rect.y - bounds.y)
        media_width = float(media_rect.width)
        media_height = float(media_rect.height)
        below_space = float(bounds.height) - (media_y + media_height)
        above_space = media_y

        x = max(0.0, min(media_x, float(bounds.width) - vis_width))
        below_y = media_y + media_height + gap
        above_y = media_y - gap - vis_height
        below_fits = below_y + vis_height <= float(bounds.height)
        above_fits = above_y >= 0.0
        if below_fits or above_fits:
            if below_fits and (not above_fits or below_space >= above_space):
                y = below_y
            else:
                y = above_y
        else:
            # Exceptional very-tall pair: keep adjacency by trying horizontal
            # free space before conceding that the display is genuinely overfull.
            right_x = media_x + media_width + gap
            left_x = media_x - gap - vis_width
            right_space = float(bounds.width) - (media_x + media_width)
            left_space = media_x
            y = max(0.0, min(media_y, float(bounds.height) - vis_height))
            if right_x + vis_width <= float(bounds.width) or left_x >= 0.0:
                if right_x + vis_width <= float(bounds.width) and (
                    left_x < 0.0 or right_space >= left_space
                ):
                    x = right_x
                else:
                    x = left_x
            else:
                # No side can contain the pair. Preserve the stronger relation
                # on the larger vertical side and clamp, then report the overfill.
                y = (
                    max(0.0, min(below_y, float(bounds.height) - vis_height))
                    if below_space >= above_space
                    else max(0.0, min(above_y, float(bounds.height) - vis_height))
                )
                logger.warning(
                    "[SPOTIFY_VIS] Media+Visualizer ordinary pair exceeds available adjacent space"
                )

        return (x, y, vis_width, vis_height, media_rect)

    def _install_quick_visualizer_authored_layout(
        self,
        chosen: QuickDisplayUnit,
        owner: Any,
        *,
        install_observer: bool,
        media_geometry: Any | None = None,
        defer_presenter_reflow: bool = False,
    ) -> bool:
        """Project ordinary Visualizer adjacency and optional stacking reservation."""

        resolved = self._resolve_quick_visualizer_authored_layout(
            chosen, owner, media_geometry=media_geometry
        )
        if resolved is None:
            return False
        x, y, width, height, media_rect = resolved
        owner.set_authored_outer_origin(x, y)

        from rendering.widget_stacking import DisplayStackObstacle

        visualizer_obstacle = DisplayStackObstacle(
            key="spotify_visualizer",
            x=int(round(x)),
            y=int(round(y)),
            width=max(1, int(round(width))),
            height=max(1, int(round(height))),
        )
        if media_rect is None:
            # Media may be disabled while the Visualizer remains ordinary. It
            # still occupies real screen space, so authored stacking should
            # route other ordinary cards around it when stacking is enabled.
            chosen.presenter.set_external_stack_obstacles(
                (visualizer_obstacle,),
                reflow=not defer_presenter_reflow,
            )
            if install_observer:
                chosen.presenter.set_layout_observer(None)
            return True

        bounds = chosen.display_bounds()
        media_local_x = int(round(float(media_rect.x - bounds.x)))
        media_local_y = int(round(float(media_rect.y - bounds.y)))
        chosen.presenter.set_external_stack_obstacles(
            (
                DisplayStackObstacle(
                    key="media",
                    x=media_local_x,
                    y=media_local_y,
                    width=max(1, int(round(float(media_rect.width)))),
                    height=max(1, int(round(float(media_rect.height)))),
                ),
                visualizer_obstacle,
            ),
            fixed_widget_ids=("media",),
            reflow=not defer_presenter_reflow,
        )

        if install_observer:
            manager_ref = weakref.ref(self)

            def _on_authored_geometry(widget_id: str, geometry: Any) -> None:
                if widget_id != "media":
                    return
                manager = manager_ref()
                if (
                    manager is None
                    or manager._retired
                    or manager._quick_visualizer_owner is not owner
                    or manager._quick_visualizer_unit is not chosen
                ):
                    return
                manager._install_quick_visualizer_authored_layout(
                    chosen,
                    owner,
                    install_observer=False,
                    media_geometry=geometry,
                    defer_presenter_reflow=True,
                )

            chosen.presenter.set_layout_observer(_on_authored_geometry)
        return True

    def _construct_quick_visualizer_owner_on(
        self,
        chosen: QuickDisplayUnit,
    ) -> bool:
        """Construct, bind and start the single visualizer owner on ``chosen``.

        Shared final-create boundary for immediate admission, the CUSTOM grace
        deadline and reclaim. Re-resolves the live model/config so a delayed
        create honours current settings, and fails closed when the visualizers
        capability is no longer effective or the instance is disabled. Returns
        True only when the single owner is admitted.
        """

        if self._quick_visualizer_owner is not None:
            self._set_quick_visualizer_construct_outcome(
                "rejected",
                "owner_already_admitted",
            )
            return False
        widgets = self._widgets_config_snapshot
        section = widgets.get("spotify_visualizer", {})
        if not isinstance(section, dict):
            self._set_quick_visualizer_construct_outcome(
                "rejected",
                "invalid_visualizer_section",
            )
            return False
        if not is_widget_family_effective(widgets, "visualizers"):
            self._set_quick_visualizer_construct_outcome(
                "rejected",
                "visualizer_capability_not_effective",
            )
            return False

        from core.settings.models import SpotifyVisualizerSettings
        from core.settings.settings_manager import SettingsManager
        from core.settings.visualizer_mode_registry import (
            resolve_effective_visualizer_section,
        )
        from core.settings.visualizer_presets import (
            resolve_visualizer_activation_payload,
        )

        # Resolve a disabled/stale persisted mode to an enabled one BEFORE the
        # activation/model payload is resolved (pre-V5/V6 startup-substitution
        # ordering gate): re-enter the canonical resolver for the substitute so
        # mode-A activation/preset state is never field-patched onto mode B. With
        # every mode enabled (today's default) this is a no-op.
        section, mode_substituted, requested_mode, effective_mode = (
            resolve_effective_visualizer_section(section)
        )
        if mode_substituted:
            logger.info(
                "[SPOTIFY_VIS] Persisted visualizer mode %r is not enabled; "
                "starting enabled mode %r instead",
                requested_mode,
                effective_mode,
            )

        activation = resolve_visualizer_activation_payload(section)
        model = SpotifyVisualizerSettings.from_mapping(
            activation.resolved_config,
            apply_preset_overlay=False,
            resolve_preset_indices=False,
        )
        if not SettingsManager.to_bool(model.enabled, False):
            self._set_quick_visualizer_construct_outcome(
                "rejected",
                "visualizer_instance_disabled",
            )
            return False
        if not SettingsManager.to_bool(model.visualizers_enabled, True):
            self._set_quick_visualizer_construct_outcome(
                "rejected",
                "visualizers_disabled",
            )
            return False

        from widgets.spotify_visualizer.quick_display_visualizer_owner import (
            QuickDisplayVisualizerOwner,
        )
        from widgets.spotify_visualizer.technical_config import (
            build_technical_cache,
        )

        mode = str(model.mode)
        technical_cache = build_technical_cache(None, model)
        shadows = widgets.get("shadows", {})
        if not isinstance(shadows, dict):
            shadows = {}
        from core.settings.shadow_direction import (
            resolve_directional_extensions,
            resolve_signed_offset,
        )
        from rendering.quick.widgets.host import ORDINARY_CARD_SHADOW_BASE

        direction = shadows.get("direction", "SE")
        try:
            frame_extra = max(0.0, min(40.0, float(shadows.get("frame_extra_offset", 0.0))))
        except (TypeError, ValueError):
            frame_extra = 0.0
        try:
            frame_opacity = max(0.0, min(1.0, float(shadows.get("frame_opacity", 0.77))))
        except (TypeError, ValueError):
            frame_opacity = 0.77
        try:
            shadow_blur = max(0.0, min(80.0, float(shadows.get("blur_radius", 18.0))))
        except (TypeError, ValueError):
            shadow_blur = 18.0
        raw_shadow_color = shadows.get("color", (0, 0, 0, 255))
        try:
            channels = [int(value) for value in raw_shadow_color]
        except (TypeError, ValueError):
            channels = [0, 0, 0, 255]
        if len(channels) == 3:
            channels.append(255)
        if len(channels) != 4:
            channels = [0, 0, 0, 255]
        channels = [max(0, min(255, value)) for value in channels]
        channels[3] = max(0, min(255, int(round(channels[3] * frame_opacity))))

        from ui.widget_theme_active import get_active_widget_theme

        widget_theme = get_active_widget_theme()
        global_widgets = widgets.get("global", {})
        if not isinstance(global_widgets, dict):
            global_widgets = {}
        try:
            visualizer_border_width = max(
                0.0, min(12.0, float(global_widgets.get("card_border_width_px", 4)))
            )
        except (TypeError, ValueError):
            visualizer_border_width = 3.0
        card_shadow_kwargs = {
            "background_color": widget_theme.color("card.background").as_tuple(),
            "border_color": widget_theme.color("card.border").as_tuple(),
            "border_width": visualizer_border_width,
            "shadow_enabled": SettingsManager.to_bool(shadows.get("enabled", True), True),
            "shadow_color": tuple(channels),
            "shadow_blur": shadow_blur,
            "shadow_offset": resolve_signed_offset(direction, *ORDINARY_CARD_SHADOW_BASE),
            "shadow_extensions": resolve_directional_extensions(direction, frame_extra),
        }
        owner = QuickDisplayVisualizerOwner(
            chosen.runtime,
            bar_count=model.resolve_bar_count(mode),
            initial_mode=mode,
            card_shadow_kwargs=card_shadow_kwargs,
        )
        try:
            owner.controller.settings_model = model
            owner.controller.record_resolved_activation(activation)
            owner.controller.technical_config_cache = technical_cache
            owner.configure(
                logical_kwargs=asdict(model),
                presentation_kwargs=asdict(model),
                technical_config=technical_cache.get(mode),
                thread_manager=self._thread_manager,
                process_supervisor=self._process_supervisor,
                playing=False,
            )
            custom_entry = resolve_quick_custom_entry(
                widgets,
                chosen.runtime.window.screen(),
                "spotify_visualizer",
            )
            if custom_entry is not None:
                from rendering.custom_layout_contract import (
                    clamp_local_rect_to_bounds,
                    denormalize_local_rect,
                )
                from rendering.custom_layout_session import normalize_viewport_extent

                screen_size = chosen.runtime.window.screen().geometry().size()
                local_rect = clamp_local_rect_to_bounds(
                    denormalize_local_rect(custom_entry.rect, screen_size),
                    screen_size,
                )
                owner.configure_committed_layout(
                    local_rect=(
                        float(local_rect.x()),
                        float(local_rect.y()),
                        float(local_rect.width()),
                        float(local_rect.height()),
                    ),
                    viewport_extent=normalize_viewport_extent(
                        custom_entry.size_payload.get("viewport_extent")
                    ),
                )
            # Ordinary placement is resolved before start so the first retained
            # Visualizer presentation never appears at the old (0, 0) default.
            # CUSTOM rejects this path completely. Stacking reservation/observer
            # are installed only after successful single-owner admission below.
            ordinary_layout = self._resolve_quick_visualizer_authored_layout(
                chosen, owner
            )
            if ordinary_layout is not None:
                owner.set_authored_outer_origin(ordinary_layout[0], ordinary_layout[1])
            else:
                # Global CUSTOM disables adjacency, not authored anchoring. Keep
                # an uncommitted Visualizer on Media's authored slot instead of
                # leaking the owner's internal (0, 0) construction default.
                base_origin = self._resolve_quick_visualizer_base_authored_origin(
                    chosen, owner
                )
                if base_origin is not None:
                    owner.set_authored_outer_origin(base_origin[0], base_origin[1])

            engine = owner.controller.engine
            generation = int(engine.get_generation_id())
            activation_id = int(engine.get_activation_id())
            owner.bind(
                engine_generation=generation,
                activation_id=activation_id,
            )
            media_model = self._resolve_quick_visualizer_media_model(chosen)
            if media_model is not None:
                owner.set_playing(
                    str(getattr(media_model, "playbackState", "unknown")).lower()
                    == "playing"
                )
            owner.start()
            self._quick_visualizer_owner = owner
            self._quick_visualizer_unit = chosen
            if media_model is not None:
                self._bind_quick_visualizer_media(media_model)
            chosen.attach_visualizer_owner(owner)
            self._install_quick_visualizer_authored_layout(
                chosen, owner, install_observer=True
            )
            from rendering.quick.visualizer.double_click_admission import (
                QuickVisualizerDoubleClickAdmission,
            )
            from rendering.quick.visualizer.middle_click_admission import (
                QuickVisualizerMiddleClickAdmission,
            )

            def _visualizer_region_contains(
                scene_position: Any,
                admitted: Any = owner,
            ) -> bool:
                return bool(
                    admitted.presentation_runtime.scene_controller
                    .visualizer_contains_scene_position(scene_position)
                )

            chosen.runtime.scene_controller.set_visualizer_double_click_admission(
                QuickVisualizerDoubleClickAdmission(
                    region_contains=_visualizer_region_contains,
                    is_active=lambda admitted=owner: (
                        admitted.is_started and not admitted.is_retired
                    ),
                    cycle_mode=self._cycle_quick_visualizer_mode,
                )
            )
            chosen.runtime.scene_controller.set_visualizer_middle_click_admission(
                QuickVisualizerMiddleClickAdmission(
                    region_contains=_visualizer_region_contains,
                    is_active=lambda admitted=owner: (
                        admitted.is_started and not admitted.is_retired
                    ),
                    cycle_preset=self._cycle_quick_visualizer_preset,
                )
            )
            chosen.runtime.scene_controller.set_visualizer_volume_wheel_handler(
                self._request_quick_app_volume_step_from_visualizer
            )
            self._refresh_all_quick_context_menus()
        except Exception:
            self._set_quick_visualizer_construct_outcome(
                "exception",
                "owner_configuration_failed",
            )
            if self._quick_visualizer_owner is owner:
                self._release_quick_visualizer_routes()
            if not owner.is_retired:
                owner.retire()
            raise

        logger.info(
            "[SPOTIFY_VIS] Admitted one Quick owner screen=%s mode=%s generation=%s activation=%s",
            chosen.screen_index,
            mode,
            generation,
            activation_id,
        )
        self._set_quick_visualizer_construct_outcome("admitted")
        return True

    def _request_quick_app_volume_step_from_visualizer(self, direction: int) -> bool:
        """Route Visualizer wheel input through an already-admitted Media owner.

        The Visualizer may be CUSTOM-routed to a different display from Media, so
        same-unit assumptions are invalid. This is a bounded event dispatch only:
        prefer the current Visualizer unit, then search the remaining live units;
        never construct/mirror Media and never add a cadence owner.
        """

        step = 1 if int(direction) > 0 else -1 if int(direction) < 0 else 0
        if step == 0:
            return False
        preferred = self._quick_visualizer_unit
        units: list[QuickDisplayUnit] = []
        if preferred is not None and not preferred.is_retired:
            units.append(preferred)
        units.extend(
            unit
            for unit in self.displays
            if isinstance(unit, QuickDisplayUnit)
            and not unit.is_retired
            and unit is not preferred
        )
        for unit in units:
            if unit.request_app_volume_step(step):
                return True
        return False

    def _resolve_quick_visualizer_media_model(
        self,
        preferred_unit: QuickDisplayUnit,
    ) -> Any | None:
        """Resolve one retained Media model without requiring local presentation.

        Same-display Media remains preferred so ordinary/non-CUSTOM and ``ALL``
        routes retain their existing identity.  A CUSTOM Visualizer may live on
        another display, so the remaining active units are then searched in
        their stable manager order.  This only discovers an already-admitted
        presentation; it never constructs or mirrors a Media card.
        """

        units = [preferred_unit]
        units.extend(
            unit for unit in self.displays if unit is not preferred_unit
        )
        for unit in units:
            presentation = unit.presenter.presentation_for_widget_id("media")
            if presentation is None:
                continue
            model = getattr(presentation, "model", None)
            if model is None:
                raise RuntimeError("Quick Media presentation has no model authority")
            return model
        return None

    def _bind_quick_visualizer_media(self, model: Any) -> None:
        """Bind canonical retained Media playback state to the sole owner."""

        changed = getattr(model, "stateChanged", None)
        if changed is None or not hasattr(changed, "connect"):
            raise RuntimeError("Quick Media model has no state-change authority")
        changed.connect(self._sync_quick_visualizer_playback)
        self._quick_visualizer_media_model = model
        self._sync_quick_visualizer_playback()

    def _sync_quick_visualizer_playback(self) -> None:
        owner = self._quick_visualizer_owner
        model = self._quick_visualizer_media_model
        if owner is None or model is None:
            return
        playing = (
            str(getattr(model, "playbackState", "unknown")).lower()
            == "playing"
        )
        observed_ts = time.time()
        if is_viz_diagnostics_enabled():
            previous = getattr(self, "_quick_visualizer_diag_last_playing", None)
            if previous is None or bool(previous) != playing:
                logger.debug(
                    "[VIS_PLAYBACK_EDGE] stage=T0 mode=%s playing=%s ts=%.6f",
                    owner.controller.mode_id,
                    playing,
                    observed_ts,
                )
            self._quick_visualizer_diag_last_playing = playing
        owner.set_playing(playing, observed_ts=observed_ts)

    def _disconnect_quick_visualizer_media_route(self) -> None:
        """Detach the sole retained Media -> visualizer playback action route."""

        model = self._quick_visualizer_media_model
        if model is not None:
            changed = getattr(model, "stateChanged", None)
            if changed is not None and hasattr(changed, "disconnect"):
                try:
                    changed.disconnect(self._sync_quick_visualizer_playback)
                except (RuntimeError, TypeError):
                    logger.debug(
                        "[SPOTIFY_VIS] Media route already detached during retirement"
                    )
        self._quick_visualizer_media_model = None

    def _release_quick_visualizer_routes(
        self,
        unit: QuickDisplayUnit | None = None,
    ) -> bool:
        """Drop manager routing references; the chosen unit owns retirement."""

        if unit is not None and unit is not self._quick_visualizer_unit:
            return False
        self._disconnect_quick_visualizer_media_route()
        chosen = self._quick_visualizer_unit
        if chosen is not None:
            chosen.presenter.set_layout_observer(None)
            chosen.presenter.set_external_stack_obstacles(None)
            chosen.runtime.scene_controller.set_visualizer_double_click_admission(None)
            chosen.runtime.scene_controller.set_visualizer_middle_click_admission(None)
        self._quick_visualizer_owner = None
        self._quick_visualizer_unit = None
        return True

    def _schedule_visualizer_failover_deadline(
        self,
        delay_ms: int,
        *,
        target_screen_index: int,
        token: int,
        generation: int,
    ) -> None:
        """Schedule ONE generation-fenced CUSTOM failover grace deadline.

        A single token/generation-fenced single-shot, never a recurring poll. The
        deadline re-resolves the live topology and creates at most one temporary
        fallback owner if the configured monitor is still absent.
        """

        manager_ref = weakref.ref(self)
        runtime_generation = self._runtime_generation

        def _run() -> None:
            manager = manager_ref()
            if manager is None or manager._retired:
                return
            if manager._runtime_generation != runtime_generation:
                return
            from rendering.quick.visualizer_failover_lifecycle import (
                run_fallback_recheck,
            )

            run_fallback_recheck(
                _QuickVisualizerFailoverTopology(manager, list(manager.displays)),
                target_screen_index=target_screen_index,
                token=token,
                generation=generation,
            )

        _run._srpss_runtime_generation = runtime_generation

        scheduler = self._thread_manager
        if scheduler is None or not hasattr(scheduler, "single_shot"):
            from core.threading.manager import ThreadManager

            scheduler = ThreadManager
        try:
            scheduler.single_shot(max(0, int(delay_ms)), _run)
        except Exception:
            logger.warning(
                "[SPOTIFY_VIS][FALLBACK] Failed to schedule CUSTOM grace deadline",
                exc_info=True,
            )

    def _quick_ordinary_family_adapters(self):
        """Build one generation's family adapters with weak product-action routes.

        Retained presentations emit semantic actions only. DisplayManager owns the
        product persistence/URL consequences, but adapters must not keep a strong
        manager reference alive through display -> presenter -> binder ownership.
        """

        from rendering.quick.widgets.family_binder import (
            default_ordinary_family_adapters,
        )

        manager_ref = weakref.ref(self)
        generation = self._runtime_generation

        def _persist_clock_mode(
            widget_id: str,
            display_identity: str,
            mode: str,
            geometry: object,
            size_payload: Mapping[str, object],
        ) -> None:
            manager = manager_ref()
            if (
                manager is None
                or manager._retired
                or manager._runtime_generation != generation
            ):
                return
            manager._persist_quick_clock_mode_override(
                widget_id,
                display_identity,
                mode,
                geometry=geometry,
                size_payload=size_payload,
            )

        def _open_reddit(widget_id: str, url: str) -> bool:
            manager = manager_ref()
            if (
                manager is None
                or manager._retired
                or manager._runtime_generation != generation
            ):
                return False
            return manager._open_quick_reddit_url(widget_id, url)

        return default_ordinary_family_adapters(
            clock_mode_toggle=_persist_clock_mode,
            reddit_open_requested=_open_reddit,
        )

    def _persist_quick_clock_mode_override(
        self,
        widget_id: str,
        display_identity: str,
        mode: str,
        *,
        geometry: object | None = None,
        size_payload: Mapping[str, object] | None = None,
    ) -> None:
        """Persist one retained Clock's per-display mode and CUSTOM variant.

        The shared ``display_mode`` setting remains the authored baseline. Runtime
        double-click writes only the matching screen override. If this Clock is
        CUSTOM-positioned, the exact target mode rect + resize-derived font scale
        are committed under that mode's independent geometry variant as well.
        Behavior never leaks into the geometry payload.
        """

        if self._retired:
            return
        settings = self.settings_manager
        normalized_widget_id = str(widget_id or "")
        identity = str(display_identity or "").strip()
        if (
            settings is None
            or normalized_widget_id not in {"clock", "clock2", "clock3"}
            or not identity
        ):
            return

        from PySide6.QtCore import QRect

        from core.widget_product_actions import update_clock_display_mode_override
        from rendering.custom_layout_contract import (
            CustomLayoutEntry,
            canonicalize_screen_layout_bucket,
            clamp_local_rect_to_bounds,
            get_screen_signature,
            load_custom_layout_map,
            normalize_local_rect,
            set_screen_layout_entry,
            write_custom_layout_map,
        )
        from rendering.quick.widgets.clock import normalize_clock_display_mode
        from rendering.widget_descriptors import is_custom_position_selected_for_widget

        normalized_mode = normalize_clock_display_mode(mode)
        widgets, mode_changed = update_clock_display_mode_override(
            settings.get_widgets_map(),
            widget_id=normalized_widget_id,
            display_identity=identity,
            normalized_mode=normalized_mode,
        )

        geometry_changed = False
        if (
            geometry is not None
            and is_custom_position_selected_for_widget(normalized_widget_id, widgets)
        ):
            # CUSTOM's edit transaction owns working geometry. The edit overlay
            # normally consumes Clock double-clicks; if one leaks through, do not
            # bypass Save/Cancel by mutating committed geometry behind the session.
            if self._quick_custom_layout_owner.is_active:
                logger.debug(
                    "[CLOCK] Deferred CUSTOM variant persistence during active edit "
                    "widget=%s display=%s mode=%s",
                    normalized_widget_id,
                    identity,
                    normalized_mode,
                )
            else:
                live_screen = next(
                    (
                        screen
                        for screen in QGuiApplication.screens()
                        if get_screen_signature(screen) == identity
                    ),
                    None,
                )
                if live_screen is None:
                    logger.warning(
                        "[CLOCK] Could not resolve display for CUSTOM variant "
                        "widget=%s display=%s mode=%s",
                        normalized_widget_id,
                        identity,
                        normalized_mode,
                    )
                else:
                    try:
                        local = clamp_local_rect_to_bounds(
                            QRect(
                                int(round(float(getattr(geometry, "x")))),
                                int(round(float(getattr(geometry, "y")))),
                                max(1, int(round(float(getattr(geometry, "width"))))),
                                max(1, int(round(float(getattr(geometry, "height"))))),
                            ),
                            live_screen.geometry().size(),
                        )
                    except (TypeError, ValueError, AttributeError):
                        logger.warning(
                            "[CLOCK] Invalid CUSTOM target geometry "
                            "widget=%s display=%s mode=%s geometry=%r",
                            normalized_widget_id,
                            identity,
                            normalized_mode,
                            geometry,
                        )
                    else:
                        custom_map = load_custom_layout_map(widgets)
                        signature = canonicalize_screen_layout_bucket(
                            custom_map, live_screen
                        ) or identity
                        payload = (
                            dict(size_payload)
                            if isinstance(size_payload, Mapping)
                            else {}
                        )
                        payload.pop("display_mode", None)
                        payload.pop("geometry_variant", None)
                        if "font_size" in payload:
                            try:
                                payload["font_size"] = max(
                                    8, int(payload["font_size"])
                                )
                            except (TypeError, ValueError):
                                payload.pop("font_size", None)
                        set_screen_layout_entry(
                            custom_map,
                            signature,
                            normalized_widget_id,
                            CustomLayoutEntry(
                                widget_id=normalized_widget_id,
                                geometry_variant=normalized_mode,
                                rect=normalize_local_rect(
                                    local, live_screen.geometry().size()
                                ),
                                size_payload=payload,
                                resize_mode="clock_font",
                            ),
                        )
                        write_custom_layout_map(widgets, custom_map)
                        geometry_changed = True

        if not mode_changed and not geometry_changed:
            return

        settings.set_widgets_map(widgets, emit_change=False)
        settings.save()

        # Keep this generation's detached routing/config snapshot coherent so a
        # later owner-local operation cannot re-publish stale Clock state before
        # the next full Settings snapshot is taken.
        self._widgets_config_snapshot = dict(widgets)
        logger.info(
            "[CLOCK] Persisted Quick per-display mode%s "
            "widget=%s display=%s mode=%s",
            " + CUSTOM variant" if geometry_changed else "",
            normalized_widget_id,
            identity,
            normalized_mode,
        )

    def _open_quick_reddit_url(self, widget_id: str, url: str) -> bool:
        """Route one admitted Reddit URL through the existing product authority.

        MC/diagnostic builds remain interactive and open directly. The ordinary
        saver uses the existing secure URL launcher, then exits normally after a
        successful handoff; helper readiness never gates saver teardown.
        """

        if self._retired:
            return False
        from rendering.runtime_input import runtime_pointer_input_is_suppressed

        if runtime_pointer_input_is_suppressed(
            "redditOpenRequested",
            screen_index="?",
        ):
            logger.info(
                "[REDDIT] Quick URL action suppressed across runtime/edit boundary "
                "widget=%s",
                str(widget_id or "reddit"),
            )
            return False
        normalized_url = str(url or "").strip()
        if not normalized_url:
            return False

        from core.build_profile import is_diagnostic_build
        from core.mc import is_mc_build
        from core.windows.secure_url_launcher import open_url

        from core.widget_product_actions import (
            dispatch_reddit_url_product_action,
        )

        interactive = bool(is_mc_build() or is_diagnostic_build())

        def _open(target: str) -> bool:
            return bool(
                open_url(
                    target,
                    prefer_direct=interactive,
                    source=f"reddit:{str(widget_id or 'reddit')}",
                )
            )

        opened = dispatch_reddit_url_product_action(
            normalized_url,
            opener=_open,
            request_saver_exit=self._on_exit_requested,
            interactive_build=interactive,
        )
        if opened:
            logger.info(
                "[REDDIT] Quick URL action admitted widget=%s route=%s",
                str(widget_id or "reddit"),
                "interactive" if interactive else "screensaver-handoff",
            )
        return bool(opened)

    def _create_display_for_screen(
        self,
        screen_index: int,
        *,
        show_immediately: bool = True,
    ) -> Optional[QuickDisplayUnit]:
        """
        Create the authoritative Quick display unit for a specific screen.
        
        Args:
            screen_index: Screen index
        """
        try:
            screens = QGuiApplication.screens()
            if not 0 <= int(screen_index) < len(screens):
                raise IndexError(f"screen index out of range: {screen_index}")
            factory = self._quick_scene_factory
            if factory is None:
                raise RuntimeError("Quick scene factory is unavailable")
            display = create_quick_display_unit(
                screen=screens[int(screen_index)],
                screen_index=int(screen_index),
                runtime_generation=int(self._runtime_generation or 0),
                scene_factory=factory,
                window_policy=self._quick_window_policy(),
                ctrl_coordinator=self._quick_ctrl_coordinator,
                interaction_mode_enabled=self._interaction_mode_enabled(),
                custom_layout_active_provider=self._quick_custom_layout_active,
                adapters=self._quick_ordinary_family_adapters(),
            )
            self._connect_quick_runtime(display, startup_generation=self._display_startup_generation)
            screen = screens[int(screen_index)]
            display.bind_families(
                widgets_config=self._widgets_config_snapshot,
                shadow_values=self._shadow_values_snapshot,
                thread_manager=self._thread_manager,
                committed_rect_resolver=lambda widget_id, live_screen=screen: (
                    resolve_quick_committed_geometry(
                        self._widgets_config_snapshot,
                        live_screen,
                        widget_id,
                    )
                ),
                committed_variant_state_resolver=(
                    lambda widget_id, variant, live_screen=screen: (
                        resolve_quick_committed_variant_state(
                            self._widgets_config_snapshot,
                            live_screen,
                            widget_id,
                            geometry_variant=variant,
                        )
                        if widget_id in {"clock", "clock2", "clock3"}
                        else None
                    )
                ),
            )
            apply_quick_committed_payloads(
                display,
                self._widgets_config_snapshot,
            )
            self._configure_quick_auxiliary(display)
            self._refresh_quick_context_menu(display)
            self.displays.append(display)
            logger.info("Quick display unit created for screen %d" % screen_index)
            if show_immediately:
                self._show_display_widget(display)
            return display
        except Exception as e:
            logger.error("Failed to create display for screen %d: %s" % (screen_index, e), exc_info=True)
            return None

    def _show_display_widget(self, display: QuickDisplayUnit, *, startup_generation: int | None = None) -> bool:
        """Show a fully-bound authoritative Quick display unit."""
        try:
            display.show_on_screen()
            if startup_generation is not None:
                self._mark_display_startup_ready(display, startup_generation)
            return True
        except Exception as e:
            screen_index = getattr(display, "screen_index", "?")
            logger.error(
                "Failed to show display for screen %s: %s",
                screen_index,
                e,
                exc_info=True,
            )
            try:
                self._disconnect_quick_visualizer_media_route()
                self._begin_quick_unit_retirement(display)
            except Exception:
                logger.error(
                    "[DISPLAY_MANAGER] Failed to retire display after show failure",
                    exc_info=True,
                )
            else:
                self._release_quick_visualizer_routes(display)
                if display in self.displays:
                    self.displays.remove(display)
            if startup_generation is not None and startup_generation == self._display_startup_generation:
                self._display_startup_ready_expected.discard(id(display))
                self._emit_display_startup_ready_if_complete(startup_generation)
            return False

    def _mark_display_startup_ready(self, display: QuickDisplayUnit, generation: int) -> None:
        """Record that one display finished generation-scoped startup setup."""

        if generation != self._display_startup_generation:
            logger.debug(
                "[DISPLAY] Ignoring stale startup-ready signal screen=%s generation=%s current=%s",
                getattr(display, "screen_index", "?"),
                generation,
                self._display_startup_generation,
            )
            return
        if display not in self.displays:
            logger.debug(
                "[DISPLAY] Ignoring startup-ready for removed display screen=%s generation=%s",
                getattr(display, "screen_index", "?"),
                generation,
            )
            return

        key = id(display)
        self._display_startup_ready_seen.add(key)
        expected = self._display_startup_ready_expected
        readiness = display.runtime.scene_readiness
        logger.info(
            "[DISPLAY] Quick startup display ready screen=%s generation=%s qml_root=%s admission=%s ready=%d/%d",
            getattr(display, "screen_index", "?"),
            generation,
            readiness.qml_root_created,
            readiness.admission_open,
            len(self._display_startup_ready_seen.intersection(expected)),
            len(expected),
        )

        self._emit_display_startup_ready_if_complete(generation)

    def _emit_display_startup_ready_if_complete(self, generation: int) -> None:
        expected = self._display_startup_ready_expected
        if not expected:
            return
        if self._display_startup_ready_emitted_generation == generation:
            return
        if not expected.issubset(self._display_startup_ready_seen):
            return

        self._display_startup_ready_emitted_generation = generation
        logger.info("[DISPLAY] Startup generation ready for image replay generation=%s", generation)
        self.displays_ready.emit(generation)

    def _cleanup_excess_displays(self) -> None:
        """Clean up displays for screens that no longer exist."""
        screen_count = len(QGuiApplication.screens())
        
        while len(self.displays) > screen_count:
            display = self.displays.pop()
            if not isinstance(display, QuickDisplayUnit):
                raise RuntimeError("display collection member is not a Quick display unit")
            self._disconnect_quick_visualizer_media_route()
            self._begin_quick_unit_retirement(display)
            self._release_quick_visualizer_routes(display)
            logger.info("Removed excess display runtime")
    
    def _on_exit_requested(self) -> None:
        """Handle exit request from any display."""
        logger.info("Exit requested from display widget")
        self.exit_requested.emit()

    def _selected_destination_screen_indices(self) -> set[int]:
        """Return screen identities owned by the destination collection."""

        return {
            int(getattr(display, "screen_index", position))
            for position, display in enumerate(self.displays)
        }

    def _reset_quick_transition_batch(self) -> None:
        self._quick_transition_batch_spec = None
        self._quick_transition_spec_resolved = False
        self._quick_transition_paths.clear()
        self._quick_batch_expected_screens.clear()
        self._quick_batch_published_screens.clear()

    def _begin_quick_transition_batch(
        self,
        expected_screens: Set[int] | None = None,
    ) -> None:
        """Open one accepted destination-image batch exactly once."""

        if self._transition_work_pending:
            if expected_screens:
                self._quick_batch_expected_screens.update(
                    int(screen) for screen in expected_screens
                )
            return
        if self._quick_transition_paths or self.has_running_transition():
            raise RuntimeError(
                "cannot admit a new image batch while a Quick transition is active"
            )
        self._reset_quick_transition_batch()
        self._quick_batch_expected_screens = {
            int(screen)
            for screen in (
                expected_screens
                if expected_screens is not None
                else self._selected_destination_screen_indices()
            )
        }
        self._transition_work_pending = True

    def _finish_quick_transition_batch_if_complete(self) -> bool:
        """Close the batch after every admitted destination is authoritative."""

        if not self._transition_work_pending:
            return False
        if self._quick_transition_paths or self.has_running_transition():
            return False
        if not self._quick_batch_expected_screens.issubset(
            self._quick_batch_published_screens
        ):
            return False
        self._transition_work_pending = False
        self._reset_quick_transition_batch()
        return True

    def _resolve_quick_transition_batch_spec(
        self,
    ) -> ResolvedQuickTransitionSpec | None:
        """Resolve Settings intent once, then share it across this batch."""

        if not self._quick_transition_spec_resolved:
            self._quick_transition_batch_spec = resolve_quick_transition_spec(
                self.settings_manager
            )
            self._quick_transition_spec_resolved = True
        return self._quick_transition_batch_spec

    def has_admissible_transition_for_open_batch(self) -> bool:
        """Validate transition availability before producer queue mutation.

        The initial base frame legitimately has no source and therefore needs no
        transition.  Once any selected display owns image state, the already-open
        image batch must resolve one concrete transition spec before the engine is
        allowed to advance queue/history truth.
        """

        if not self._transition_work_pending:
            return False
        if not self.has_presented_image():
            return True
        try:
            return self._resolve_quick_transition_batch_spec() is not None
        except Exception:
            logger.exception(
                "[TRANSITION] Open image batch failed transition preflight"
            )
            return False

    def _present_quick_image(
        self,
        display: object,
        pixmap: QPixmap,
        image_path: str,
        *,
        implicit_expected_screens: Set[int] | None = None,
    ) -> str:
        """Publish or transition one processed image through a destination unit."""

        screen_index = int(getattr(display, "screen_index"))

        capture = getattr(display, "capture_image", None)
        current_image = getattr(display, "current_image", None)
        publish = getattr(display, "present_captured_image", None)
        start_transition = getattr(display, "start_transition", None)
        if not all(
            callable(operation)
            for operation in (capture, current_image, publish, start_transition)
        ):
            raise TypeError("display unit has no Quick image/transition contract")

        # Image-change admission is transactional at the engine/manager seam.
        # Reaching publication while this display still owns an active transition
        # is therefore an invariant failure: never cancel/snap that run merely to
        # make room for a newer image.  The active destination must finish intact;
        # the newer request is rejected before queue mutation by the batch owner.
        if bool(getattr(display, "has_running_transition")()):
            raise RuntimeError(
                f"screen {screen_index} still owns an active Quick transition "
                "during admitted image publication"
            )

        if not self._transition_work_pending:
            self._begin_quick_transition_batch(
                implicit_expected_screens or {screen_index}
            )

        destination = capture(pixmap, image_path=image_path)
        source = current_image()
        if source is None:
            publish(destination)
            self._quick_batch_published_screens.add(screen_index)
            # Close the final first-frame batch before publishing authoritative
            # readiness.  Replacement-runtime reseeding runs synchronously from
            # that readiness signal and must observe genuinely idle batch state;
            # otherwise a direct first frame would wait forever for a transition
            # completion event that cannot exist.
            self._finish_quick_transition_batch_if_complete()
            self._on_image_displayed(screen_index, image_path)
            return "base_published"

        startup_desktop_transition = (
            screen_index in self._startup_desktop_seed_screens
            and screen_index not in self.current_images
        )
        spec = (
            self._startup_desktop_crossfade_spec()
            if startup_desktop_transition
            else self._resolve_quick_transition_batch_spec()
        )
        if spec is None:
            # Once a source image exists, a missing/invalid transition is not
            # permission to flash the destination directly.  Keep the current
            # image authoritative and fail the batch loudly; startup with no
            # source remains the only legitimate direct-publication path above.
            logger.error(
                "[TRANSITION] Image batch has no admissible transition; "
                "destination withheld screen=%s image=%s",
                screen_index,
                image_path,
            )
            raise RuntimeError(
                f"screen {screen_index} image batch has no admissible transition"
            )

        request = spec.build_request(
            runtime_generation=int(self._runtime_generation or 0),
            source_image=source,
            destination_image=destination,
        )
        start_transition(request)
        if startup_desktop_transition:
            logger.info(
                "[STARTUP_DESKTOP] Crossfade admitted screen=%s duration_ms=%s",
                screen_index,
                spec.duration_ms,
            )
        self._quick_transition_paths[screen_index] = str(image_path or "")
        self._quick_batch_published_screens.add(screen_index)
        return "transition_started"

    def _on_quick_transition_finalized(
        self,
        display: QuickDisplayUnit,
        completion: object,
    ) -> None:
        """Commit image/accounting truth only after destination finalization."""

        screen_index = int(display.screen_index)
        image_path = self._quick_transition_paths.pop(screen_index, None)
        current = display.current_image()
        destination_identity = str(
            getattr(completion, "destination_image_identity", "") or ""
        )
        if (
            image_path is not None
            and current is not None
            and current.identity == destination_identity
        ):
            self._on_image_displayed(screen_index, image_path)
        elif image_path is not None and not self._retired:
            logger.error(
                "[TRANSITION] Finalized destination was not installed "
                "screen=%s expected=%s current=%s",
                screen_index,
                destination_identity,
                getattr(current, "identity", None),
            )
        # Reconcile whole-batch ownership before notifying downstream readiness
        # consumers.  The final display completion is the event that makes
        # transition work genuinely idle, allowing prefetch to resume without a
        # 100 ms polling loop.
        self._finish_quick_transition_batch_if_complete()
        self.transition_completed.emit(screen_index)
    
    def _on_image_displayed(self, screen_index: int, image_path: str) -> None:
        """Handle one authoritative authored image becoming fully displayed."""
        self._startup_desktop_seed_screens.discard(int(screen_index))
        self.current_images[screen_index] = image_path
        self._authoritative_first_frame_screens.add(int(screen_index))
        logger.debug(f"Image displayed on screen {screen_index}: {image_path}")
        expected = {
            int(getattr(display, "screen_index", -1))
            for display in self.displays
        }
        if (
            not self._authoritative_first_frame_emitted
            and expected
            and expected.issubset(self._authoritative_first_frame_screens)
        ):
            self._authoritative_first_frame_emitted = True
            self.authoritative_first_frames_ready.emit(
                int(self._runtime_generation or 0)
            )
        readiness = self._quick_readiness_by_screen.get(int(screen_index))
        if readiness is not None and readiness.ready_for_reveal:
            self._mark_startup_reveal_ready(int(screen_index))

    def _prime_quick_startup_desktop_sources(
        self,
        pending_displays: list[QuickDisplayUnit],
    ) -> None:
        """Capture the visible desktop once and seed each hidden Quick scene.

        The windows are still hidden at this boundary, so ``QScreen.grabWindow(0)``
        captures what the operator is actually looking at rather than recursively
        capturing SRPSS. The seed is presentation-only and is explicitly excluded
        from queue/history/current-image authority. No timer or steady-state owner
        is introduced; the immutable capture is released by the first transition.
        """

        self._startup_desktop_seed_screens.clear()
        if not self._desktop_startup_crossfade_enabled:
            logger.debug(
                "[STARTUP_DESKTOP] Desktop staging skipped for replacement runtime "
                "generation=%s",
                self._runtime_generation,
            )
            return

        for display in pending_displays:
            if display.is_retired:
                continue
            screen = display.runtime.window.screen()
            if screen is None:
                logger.error(
                    "[STARTUP_DESKTOP] No QScreen available for startup capture "
                    "screen=%s; first image will use the explicit no-seed path",
                    display.screen_index,
                )
                continue
            try:
                desktop = screen.grabWindow(0)
            except Exception:
                logger.error(
                    "[STARTUP_DESKTOP] Desktop capture raised screen=%s; "
                    "first image will use the explicit no-seed path",
                    display.screen_index,
                    exc_info=True,
                )
                continue
            if desktop.isNull() or desktop.width() <= 0 or desktop.height() <= 0:
                logger.error(
                    "[STARTUP_DESKTOP] Desktop capture was null screen=%s; "
                    "first image will use the explicit no-seed path",
                    display.screen_index,
                )
                continue
            seed = display.capture_image(
                desktop,
                image_path=f"__startup_desktop_screen_{display.screen_index}__",
            )
            display.present_captured_image(seed)
            self._startup_desktop_seed_screens.add(int(display.screen_index))
            logger.info(
                "[STARTUP_DESKTOP] Seeded hidden Quick scene screen=%s "
                "pixels=%sx%s dpr=%.3f",
                display.screen_index,
                desktop.width(),
                desktop.height(),
                float(desktop.devicePixelRatio()),
            )

    @staticmethod
    def _startup_desktop_crossfade_spec() -> ResolvedQuickTransitionSpec:
        """Return the fixed one-session desktop -> first-wallpaper transition."""

        return ResolvedQuickTransitionSpec(
            transition_id="crossfade",
            requested_name="Crossfade",
            selected_from_random=False,
            duration_ms=QUICK_STARTUP_DESKTOP_CROSSFADE_DURATION_MS,
            direction=None,
            parameters=(),
        )

    def _apply_quick_startup_reveal_opacity(self, opacity: float) -> int:
        """Apply one shared startup gate without rewriting family-authored fades."""

        affected = 0
        for display in tuple(self.displays):
            if display.is_retired:
                continue
            affected += len(display.presenter.set_startup_reveal_opacity(opacity))
            try:
                if display.runtime.scene_controller.set_visualizer_startup_reveal_opacity(
                    opacity
                ):
                    affected += 1
            except (RuntimeError, TypeError, ValueError):
                logger.warning(
                    "[STARTUP_REVEAL] Failed visualizer startup gate screen=%s",
                    display.screen_index,
                    exc_info=True,
                )
        return affected

    def _prepare_quick_startup_reveal(
        self,
        pending_displays: list[QuickDisplayUnit],
    ) -> None:
        """Prime all admitted retained widgets at opacity zero before first show."""

        self._cancel_quick_startup_reveal()
        generation = int(self._runtime_generation or 0)
        manager_ref = weakref.ref(self)

        def _opacity_sink(opacity: float) -> int:
            manager = manager_ref()
            if (
                manager is None
                or manager._retired
                or int(manager._runtime_generation or 0) != generation
            ):
                return 0
            return manager._apply_quick_startup_reveal_opacity(opacity)

        coordinator = QuickStartupRevealCoordinator(
            runtime_generation=generation,
            opacity_sink=_opacity_sink,
            parent=self,
        )
        coordinator.completed.connect(self._on_quick_startup_reveal_finished)
        self._quick_startup_reveal = coordinator
        target_count = coordinator.prime()
        logger.info(
            "[STARTUP_REVEAL] Primed coordinated retained reveal "
            "generation=%s displays=%d families=%d",
            generation,
            len(pending_displays),
            target_count,
        )

    def _mark_startup_reveal_ready(self, screen_index: int) -> None:
        """Start the coordinated reveal once every selected display is ready."""

        self._startup_reveal_screens.add(int(screen_index))
        expected = {
            int(getattr(display, "screen_index", -1))
            for display in self.displays
        }
        if (
            self._startup_reveal_emitted
            or self._startup_reveal_started
            or not expected
            or not expected.issubset(self._startup_reveal_screens)
        ):
            return

        self._startup_reveal_started = True
        coordinator = self._quick_startup_reveal
        if coordinator is None:
            # Defensive no-animation shape: completion must still reflect the
            # actual readiness gate rather than being emitted per display.
            self._on_quick_startup_reveal_finished(
                int(self._runtime_generation or 0)
            )
            return

        logger.info(
            "[STARTUP_REVEAL] Starting coordinated retained reveal "
            "generation=%s displays=%d families=%d",
            int(self._runtime_generation or 0),
            len(expected),
            coordinator.target_count,
        )
        coordinator.start()

    def _on_quick_startup_reveal_finished(self, generation: int) -> None:
        """Publish lifecycle completion only after the shared fade actually ends."""

        if (
            self._retired
            or self._startup_reveal_emitted
            or int(generation) != int(self._runtime_generation or 0)
        ):
            return
        self._startup_reveal_emitted = True
        logger.info(
            "[STARTUP_REVEAL] Coordinated retained reveal complete generation=%s",
            generation,
        )
        self.startup_reveal_completed.emit(int(generation))

    def _cancel_quick_startup_reveal(self) -> None:
        """Retire the generation's shared reveal without false completion."""

        coordinator = self._quick_startup_reveal
        self._quick_startup_reveal = None
        if coordinator is None:
            return
        try:
            coordinator.completed.disconnect(self._on_quick_startup_reveal_finished)
        except (RuntimeError, TypeError):
            pass
        coordinator.cancel()
        coordinator.deleteLater()
    
    def set_process_supervisor(self, supervisor) -> None:
        """Retain the process owner used by admitted generation services."""

        self._process_supervisor = supervisor
        owner = self._quick_visualizer_owner
        if owner is not None:
            owner.controller.process_supervisor = supervisor
    
    def show_image(self, pixmap: QPixmap, image_path: str = "", 
                   screen_index: Optional[int] = None) -> None:
        """
        Show image on display(s).
        
        Args:
            pixmap: Image to display
            image_path: Path to image (for logging)
            screen_index: Specific screen index, or None for all screens (same_image_mode)
        """
        if not self.displays:
            logger.warning("[FALLBACK] No displays available")
            return
        
        if screen_index is not None:
            # Show on specific screen
            display = self._display_for_screen_index(screen_index)
            if display is None:
                logger.warning(f"[FALLBACK] Invalid screen index: {screen_index}")
            else:
                self._present_quick_image(
                    display,
                    pixmap,
                    image_path,
                    implicit_expected_screens={int(screen_index)},
                )
        else:
            # Show on all screens (same image mode)
            if self.same_image_mode:
                quick_screens = self._selected_destination_screen_indices()
                if quick_screens and not self._transition_work_pending:
                    self._begin_quick_transition_batch(quick_screens)
                for display in self.displays:
                    self._present_quick_image(
                        display,
                        pixmap,
                        image_path,
                        implicit_expected_screens=quick_screens,
                    )
                logger.debug(f"Image shown on all {len(self.displays)} displays")
    
    def show_image_on_screen(self, screen_index: int, pixmap: QPixmap, image_path: str = "") -> None:
        """
        Show image on specific screen.
        
        Args:
            screen_index: Screen index
            pixmap: Image to display
            image_path: Path to image
        """
        self.show_image(pixmap, image_path, screen_index)

    def _display_for_screen_index(self, screen_index: int) -> object | None:
        for position, display in enumerate(self.displays):
            if int(getattr(display, "screen_index", position)) == int(screen_index):
                return display
        return None

    def present_processed_image(
        self,
        screen_index: int,
        processed_pixmap: QPixmap,
        original_pixmap: QPixmap,
        image_path: str,
    ) -> str:
        """Publish one GUI-materialized image through the selected display unit."""

        display = self._display_for_screen_index(screen_index)
        if display is None:
            raise IndexError(f"no selected display for screen index {screen_index}")
        return self._present_quick_image(display, processed_pixmap, image_path)
    
    def show_error(self, message: str, screen_index: Optional[int] = None) -> None:
        """
        Show error message on display(s).
        
        Args:
            message: Error message
            screen_index: Specific screen, or None for all screens
        """
        if screen_index is not None:
            display = self._display_for_screen_index(screen_index)
            if display is not None:
                logger.error(
                    "[DISPLAY] Runtime error for screen %s: %s",
                    screen_index,
                    message,
                )
        else:
            for display in self.displays:
                logger.error(
                    "[DISPLAY] Runtime error for screen %s: %s",
                    getattr(display, "screen_index", "?"),
                    message,
                )
    
    def clear_all(self) -> None:
        """Clear all displays (removes image but keeps windows visible)."""
        for display in self.displays:
            display.clear()
        self.current_images.clear()
        self._startup_desktop_seed_screens.clear()
        self._transition_work_pending = False
        self._reset_quick_transition_batch()
        logger.info("All displays cleared")

    def quiesce_all(self) -> None:
        """Suppress late display/widget work before clear/hide/cleanup proceeds."""
        for display in self.displays:
            display.quiesce()
        logger.info("All displays quiesced")
    
    def hide_all(self) -> None:
        """Hide all display widgets (for showing dialogs on top)."""
        for display in self.displays:
            display.hide()
        logger.info("All displays hidden")
    
    def show_all(self) -> None:
        """Show all Quick display windows after dialogs close."""
        for display in self.displays:
            display.show_on_screen()
        logger.info("All displays shown")
    
    def set_display_mode(self, mode: DisplayMode) -> None:
        """
        Change display mode for all screens.
        
        Args:
            mode: New display mode
        """
        self.display_mode = mode
        logger.info(f"Display mode changed to {mode} for all screens")
    
    def set_same_image_mode(self, enabled: bool) -> None:
        """
        Enable/disable same image mode.
        
        Args:
            enabled: True = same image on all screens, False = different images
        """
        self.same_image_mode = enabled
        logger.info(f"Same image mode: {enabled}")
    
    def set_dimming_all_displays(self, enabled: bool, opacity: float) -> None:
        """
        Update dimming on ALL displays.
        
        Called when dimming is toggled via context menu to ensure all displays
        stay synchronized.
        
        Args:
            enabled: True to enable dimming, False to disable
            opacity: Dimming opacity 0.0-1.0
        """
        for display in self.displays:
            try:
                display.runtime.auxiliary_controller.set_dimming(enabled, opacity)
            except Exception as e:
                logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
        logger.debug("Dimming updated on all %d displays: enabled=%s, opacity=%.0f%%",
                     len(self.displays), enabled, opacity * 100)
    
    def get_display_count(self) -> int:
        """Get number of active displays."""
        return len(self.displays)

    def snapshot_processing_descriptors(
        self,
    ) -> tuple[DisplayProcessingDescriptor, ...]:
        """Return immutable per-display inputs without exposing presenter objects."""

        targets: list[DisplayProcessingDescriptor] = []
        for display in self.displays:
            snapshot = getattr(display, "processing_descriptor", None)
            if not callable(snapshot):
                raise TypeError(
                    "display collection member has no processing-target contract"
                )
            target = snapshot(self.display_mode)
            if not isinstance(target, DisplayProcessingDescriptor):
                raise TypeError(
                    "display unit returned an invalid processing-target snapshot"
                )
            targets.append(target)
        return tuple(targets)

    def has_presented_image(self) -> bool:
        """Return whether any selected display has accepted current image state."""

        if self.current_images:
            return True
        for display in self.displays:
            screen_index = int(getattr(display, "screen_index", -1))
            if screen_index in self._startup_desktop_seed_screens:
                continue
            runtime = getattr(display, "runtime", None)
            scene = getattr(runtime, "scene_controller", None)
            if scene is not None and getattr(scene, "presentation_image", None) is not None:
                return True
        return False

    def wake_media_runtime(self) -> int:
        """Wake every owned neutral Media runtime service from idle."""

        awakened = 0
        for display in self.displays:
            runtime = getattr(display, "runtime", None)
            runtime_manager = getattr(runtime, "widget_runtime_manager", None)
            service_getter = getattr(runtime_manager, "get_widget_service", None)
            service = service_getter("media") if callable(service_getter) else None
            wake = getattr(service, "wake_from_idle", None)
            if callable(wake):
                wake()
                awakened += 1
        return awakened

    def describe_display_states(self) -> tuple[dict[str, Any], ...]:
        """Return bounded runtime diagnostics without exposing display owners."""

        states: list[dict[str, Any]] = []
        for display in self.displays:
            describe = getattr(display, "describe_runtime_state", None)
            if callable(describe):
                state = describe()
            else:
                runtime = getattr(display, "runtime", None)
                runtime_describe = getattr(runtime, "describe_runtime_state", None)
                state = runtime_describe() if callable(runtime_describe) else None
            if isinstance(state, dict):
                states.append(state)
        return tuple(states)

    def describe_resource_ownership(self) -> dict[str, Any]:
        """Aggregate Quick-native display ownership for lifecycle sidecars."""

        count_fields = (
            "display_units",
            "quick_runtimes",
            "quick_windows",
            "runtime_managers",
            "family_presentations",
            "visualizer_owners",
            "first_frames_ready",
        )
        by_generation: dict[str, dict[str, Any]] = {}
        for display in self.displays:
            snapshot = display.resource_ownership_snapshot(
                first_frame_ready=(
                    display.screen_index in self._authoritative_first_frame_screens
                )
            )
            generation_key = str(snapshot["runtime_generation"])
            counts = by_generation.setdefault(
                generation_key,
                {
                    **{field: 0 for field in count_fields},
                    "visualizer_identities": [],
                },
            )
            for field in count_fields:
                counts[field] += int(snapshot[field])
            identities = snapshot["visualizer_identities"]
            if isinstance(identities, list):
                counts["visualizer_identities"].extend(
                    identities[: 8 - len(counts["visualizer_identities"])]
                )

        return {
            "display_manager_id": id(self),
            "by_generation": by_generation,
        }

    def collect_runtime_retirement_roots(
        self,
    ) -> tuple[list[QObject], list[object]]:
        """Collect exact Quick-generation roots for the replacement barrier."""

        qobjects: list[QObject] = []
        python_owners: list[object] = []

        def _append_unique(values: list[object], candidate: object | None) -> None:
            if candidate is None:
                return
            candidate_id = id(candidate)
            if any(id(value) == candidate_id for value in values):
                return
            values.append(candidate)

        def _append_qobject_tree(candidate: object | None) -> None:
            if not isinstance(candidate, QObject):
                return
            _append_unique(qobjects, candidate)
            try:
                for child in candidate.findChildren(QObject):
                    _append_unique(qobjects, child)
            except (RuntimeError, TypeError):
                logger.debug(
                    "[LIFECYCLE_BARRIER] Could not enumerate children for %s",
                    type(candidate).__name__,
                    exc_info=True,
                )

        _append_qobject_tree(self)
        for display in self.displays:
            roots = getattr(display, "runtime_retirement_roots", None)
            if not callable(roots):
                raise TypeError(
                    "display collection member has no retirement-root contract"
                )
            display_qobjects, display_python_owners = roots()
            for root in display_qobjects:
                _append_qobject_tree(root)
            for owner in display_python_owners:
                _append_unique(python_owners, owner)

        return qobjects, python_owners
    
    def get_screen_count(self) -> int:
        """Get number of detected screens."""
        return len(QGuiApplication.screens())
    
    def get_display_info(self) -> List[dict]:
        """
        Get information about all displays.
        
        Returns:
            List of display info dicts
        """
        result: list[dict] = []
        for display in self.displays:
            runtime = getattr(display, "runtime", None)
            identity = getattr(runtime, "display_identity", None)
            as_dict = getattr(identity, "as_dict", None)
            if callable(as_dict):
                result.append(as_dict())
        return result
    
    def has_running_transition(self) -> bool:
        """Return True if any display currently has a running transition."""
        try:
            for display in self.displays:
                try:
                    if hasattr(display, "has_running_transition") and display.has_running_transition():
                        return True
                except Exception as e:
                    logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
                    continue
        except Exception as e:
            logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
            return False
        return False

    def set_transition_work_pending(
        self,
        pending: bool,
        *,
        screen_index: int | None = None,
    ) -> None:
        """Open/reconcile one accepted image batch before transition start."""

        destination_screens = self._selected_destination_screen_indices()
        if pending and destination_screens:
            expected = (
                destination_screens
                if screen_index is None
                else {int(screen_index)}
            )
            self._begin_quick_transition_batch(expected)
        elif not pending and destination_screens:
            if screen_index is not None:
                missing_screen = int(screen_index)
                self._quick_batch_expected_screens.discard(missing_screen)
                self._quick_batch_published_screens.discard(missing_screen)
            else:
                # The producer has no more displays to publish for this batch.
                # Preserve every already-started/direct destination, but do not
                # let a failed/omitted screen pin accepted-work truth forever.
                self._quick_batch_expected_screens.intersection_update(
                    self._quick_batch_published_screens
                )
            self._finish_quick_transition_batch_if_complete()
        elif not destination_screens:
            self._transition_work_pending = bool(pending)

    def has_transition_work_pending(self) -> bool:
        """Return True if image-change work is pending or any transition is running."""
        if self._transition_work_pending:
            return True
        try:
            for display in self.displays:
                try:
                    has_pending = getattr(display, "has_transition_work_pending", None)
                    if callable(has_pending) and has_pending():
                        return True
                except Exception as e:
                    logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
                    continue
        except Exception as e:
            logger.debug("[DISPLAY_MANAGER] Exception suppressed: %s", e)
            return False
        return False
    
    # --- Phase 3: Multi-Display Synchronization (Lock-Free) ---
    
    def enable_transition_sync(self, enabled: bool = True) -> None:
        """
        Enable synchronized transitions across displays using lock-free SPSC queue.
        
        Args:
            enabled: True to enable sync, False to disable
        """
        self._sync_enabled = enabled
        if enabled and len(self.displays) > 1:
            # Create SPSC queue for transition ready signals (capacity 20 pending signals)
            self._transition_ready_queue = SPSCQueue(capacity=20)
            logger.info(f"[SYNC] Multi-display transition synchronization enabled for {len(self.displays)} displays")
        else:
            self._transition_ready_queue = None
            if enabled:
                logger.debug("[SYNC] Sync requested but only 1 display, disabling")
            else:
                logger.debug("[SYNC] Multi-display transition synchronization disabled")
    
    def _on_display_transition_ready(self, display_index: int) -> None:
        """
        Called when a display's transition overlay is ready.
        
        Producer method for SPSC queue (called from display widgets).
        
        Args:
            display_index: Index of display that's ready
        """
        if self._transition_ready_queue is not None:
            success = self._transition_ready_queue.try_push(display_index)
            if success:
                logger.debug(f"[SYNC] Display {display_index} transition ready signal queued")
            else:
                logger.warning(f"[SYNC] Failed to queue ready signal for display {display_index} (queue full)")
    
    def wait_for_all_displays_ready(self, timeout_sec: float = 1.0) -> bool:
        """
        Wait for all displays to signal transition ready (consumer method).
        
        Uses lock-free SPSC queue to collect ready signals from each display.
        Returns early if all displays signal ready before timeout.
        
        Args:
            timeout_sec: Maximum time to wait in seconds
        
        Returns:
            True if all displays ready, False if timeout or sync disabled
        """
        if not self._sync_enabled or self._transition_ready_queue is None:
            return True  # Sync disabled, proceed immediately
        
        if len(self.displays) <= 1:
            return True  # Single display, no sync needed
        
        expected_count = len(self.displays)
        ready_set: Set[int] = set()
        start_time = time.time()
        
        logger.debug(f"[SYNC] Waiting for {expected_count} displays to be ready (timeout={timeout_sec:.2f}s)")
        
        while len(ready_set) < expected_count:
            # Try to pop ready signal from queue
            success, display_idx = self._transition_ready_queue.try_pop()
            
            if success and display_idx is not None:
                ready_set.add(display_idx)
                logger.debug(f"[SYNC] Display {display_idx} ready ({len(ready_set)}/{expected_count})")
            else:
                # Queue empty, check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout_sec:
                    logger.warning(f"[SYNC] Timeout waiting for displays: {len(ready_set)}/{expected_count} ready after {elapsed:.2f}s")
                    return False
                
                # Do not pump arbitrary Qt events here; synchronized transition
                # readiness must not become a UI-pressure escape hatch.
                time.sleep(0.001)
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"[SYNC] All {expected_count} displays ready in {elapsed_ms:.1f}ms")
        return True
    
    def show_image_synchronized(self, pixmap: QPixmap, image_path: str = "") -> None:
        """
        Show image on all displays with synchronized transitions.
        
        If sync is enabled, waits for all displays to signal transition ready
        before starting animations. Uses lock-free SPSC queue.
        
        Args:
            pixmap: Image to display
            image_path: Path to image file
        """
        if not self.displays:
            logger.warning("[FALLBACK] No displays available")
            return
        
        # If sync disabled or single display, use standard method
        if not self._sync_enabled or len(self.displays) <= 1:
            self.show_image(pixmap, image_path)
            return
        
        # Clear ready queue before starting
        if self._transition_ready_queue:
            while self._transition_ready_queue.try_pop()[0]:
                pass
        
        # Start transitions on all displays
        logger.debug(f"[SYNC] Starting synchronized transition on {len(self.displays)} displays")
        quick_screens = self._selected_destination_screen_indices()
        if quick_screens and not self._transition_work_pending:
            self._begin_quick_transition_batch(quick_screens)
        for display in self.displays:
            self._present_quick_image(
                display,
                pixmap,
                image_path,
                implicit_expected_screens=quick_screens,
            )
        
        # Wait for all to be ready (with timeout)
        all_ready = self.wait_for_all_displays_ready(timeout_sec=1.0)
        
        if not all_ready:
            logger.warning("[SYNC] Not all displays ready, transitions may desync")
        else:
            logger.debug("[SYNC] Synchronized transition started successfully")
    
    def cleanup(self) -> None:
        """Retire every display generation through its authoritative owner."""
        self._cancel_quick_startup_reveal()
        self._display_startup_generation += 1
        self._display_startup_ready_expected = set()
        self._display_startup_ready_seen = set()
        self._display_startup_ready_emitted_generation = -1
        self._authoritative_first_frame_screens.clear()
        self._authoritative_first_frame_emitted = False
        self._startup_desktop_seed_screens.clear()
        self._startup_reveal_screens.clear()
        self._startup_reveal_started = False
        self._startup_reveal_emitted = False
        count = len(self.displays)
        logger.info("Cleaning up %d display runtimes", count)

        if any(not isinstance(display, QuickDisplayUnit) for display in self.displays):
            raise RuntimeError(
                "display collection contains a non-Quick production presenter"
            )

        failed_units: list[QuickDisplayUnit] = []
        cleanup_errors: list[str] = []
        self._quick_custom_layout_owner.retire()
        self._disconnect_quick_visualizer_media_route()
        for unit in tuple(self.displays):
            screen_index = int(unit.screen_index)
            try:
                if is_perf_metrics_enabled():
                    logger.info(
                        "[PERF][DISPLAY_MANAGER] cleanup_display screen=%s state=%s",
                        screen_index,
                        unit.runtime.describe_runtime_state(),
                    )
                unit.quiesce()
                unit.clear()
                self._begin_quick_unit_retirement(unit)
                self._release_quick_visualizer_routes(unit)
            except Exception as exc:
                failed_units.append(unit)
                cleanup_errors.append(
                    f"screen={screen_index} type={type(exc).__name__} error={exc}"
                )
                logger.error(
                    "Quick display retirement failed (screen_index=%s): %s",
                    screen_index,
                    exc,
                    exc_info=True,
                )

        self.displays = failed_units
        self.current_images.clear()
        self._startup_desktop_seed_screens.clear()
        self._transition_work_pending = False
        self._reset_quick_transition_batch()
        self._quick_readiness_by_screen.clear()
        self._display_image_accounting_by_id.clear()
        self._publish_display_image_accounting()
        if cleanup_errors:
            raise RuntimeError(
                "Quick display retirement incomplete: "
                + " | ".join(cleanup_errors)
            )
        logger.info(
            "Display manager began asynchronous retirement for %d Quick units",
            count,
        )

    def retire_runtime(self) -> None:
        """Detach process-level routes and queue this retired manager for deletion.

        This terminal method is called only when the engine is replacing or
        shutting down the entire runtime generation. A Quick manager and its
        scene factory remain alive until every top-level window/runtime reports
        retirement; replacement is admitted only by the destruction barrier.
        """

        if self._retired:
            return
        self._retired = True
        self._cancel_quick_startup_reveal()
        # Retire the process-scoped CUSTOM failover record with this generation so
        # a stale grace/fallback cannot leak into a replacement generation and a
        # fresh outage arms a fresh grace generation.
        from rendering.quick.visualizer_failover import get_visualizer_failover_state

        get_visualizer_failover_state().clear_visualizer_failover()
        self.disconnect_monitor_detection()
        self.disconnect_runtime_signal_connections()
        self._display_startup_generation += 1
        self._display_startup_ready_expected.clear()
        self._display_startup_ready_seen.clear()
        self._startup_desktop_seed_screens.clear()
        self._monitor_reconcile_pending = False
        self._transition_work_pending = False
        self._reset_quick_transition_batch()
        self._transition_ready_queue = None
        self._display_image_accounting_by_id.clear()
        self._publish_display_image_accounting()
        self._image_accounting_publisher_ref = None

        self._quick_custom_layout_owner.retire()
        self.settings_manager = None
        self._thread_manager = None
        self._resource_manager = None
        self._retire_manager_when_quick_complete = True
        if self._retiring_quick_units:
            return
        if self.displays:
            raise RuntimeError(
                "DisplayManager.retire_runtime() requires cleanup() to retire displays first"
            )
        self.deleteLater()

    def take_deferred_reddit_urls(self) -> list[str]:
        """Retrieve and clear deferred Reddit URLs collected during cleanup."""
        urls, self._deferred_reddit_urls = self._deferred_reddit_urls, []
        return urls

    def flush_deferred_reddit_urls(self, *, ensure_widgets_dismissed: bool = False) -> None:
        """Open any deferred Reddit URLs collected during the last cleanup.

        Build-aware behaviour:
        - **MC builds**: open directly via ``QDesktopServices.openUrl()``.
        - **SCR builds**: URLs were pre-queued to ProgramData at click time.
          This flush acts as a safety-net for any URLs collected during
          cleanup that weren't pre-queued (e.g. edge-case race).
        """
        urls = self.take_deferred_reddit_urls()
        if not urls:
            return

        if ensure_widgets_dismissed:
            logger.debug("[REDDIT] Deferred flush requested after widget dismissal; no UI event pump required")

        logger.info("[REDDIT] Deferred URL flush started (count=%d)", len(urls))

        from core.mc import is_mc_build
        if is_mc_build():
            for url in urls:
                try:
                    opened = QDesktopServices.openUrl(QUrl(url))
                    if opened:
                        logger.info("[REDDIT] MC flush opened: %s", url)
                        try:
                            from core.windows.browser_window_routing import try_bring_browser_window_to_front
                            if self._thread_manager is None or not hasattr(self._thread_manager, "single_shot"):
                                logger.warning(
                                    "[REDDIT][FALLBACK] MC flush foreground preference skipped: "
                                    "ThreadManager single_shot unavailable"
                                )
                            else:
                                self._thread_manager.single_shot(
                                    800,
                                    lambda target=url: try_bring_browser_window_to_front(
                                        target,
                                        preferred_display_index=0,
                                        fallback_keywords=("reddit",),
                                    ),
                                )
                        except Exception:
                            logger.warning(
                                "[REDDIT][FALLBACK] MC flush foreground preference setup failed",
                                exc_info=True,
                            )
                    else:
                        logger.warning("[REDDIT] MC flush rejected: %s", url)
                except Exception:
                    logger.warning("[REDDIT] MC flush failed: %s", url, exc_info=True)
        else:
            # SCR build: URLs should have been pre-queued at click time.
            # Safety-net: queue any that weren't (collected during cleanup).
            helper_bridge = reddit_helper_bridge
            if helper_bridge is not None and helper_bridge.is_bridge_available():
                for url in urls:
                    try:
                        helper_bridge.enqueue_url(url, source="flush_safety_net")
                        logger.info("[REDDIT] Safety-net queued: %s", url)
                    except Exception:
                        logger.warning("[REDDIT] Safety-net queue failed: %s", url, exc_info=True)
            else:
                logger.warning("[REDDIT] Bridge unavailable; %d URLs will be lost", len(urls))


class _QuickVisualizerFailoverTopology:
    """DisplayManager-bound adapter for the neutral CUSTOM failover lifecycle.

    Presentation-neutral policy lives in
    ``rendering/quick/visualizer_failover_lifecycle``; this adapter only supplies
    the Quick mechanism: live canonical routing/capability, participant
    resolution over the current display units, and construction/retirement of the
    SINGLE manager-owned visualizer owner. It never creates a second owner and
    never persists the temporary fallback monitor/geometry.
    """

    def __init__(self, manager: "DisplayManager", participants) -> None:
        self._manager = manager
        self._participants = list(participants)

    def capability_admitted(self) -> bool:
        widgets = self._manager._widgets_config_snapshot
        if not isinstance(widgets, dict):
            return False
        try:
            return bool(is_widget_family_effective(widgets, "visualizers"))
        except Exception:
            return False

    def live_widgets(self):
        return self._manager._widgets_config_snapshot

    def is_custom_selected(self, widgets) -> bool:
        from rendering.widget_descriptors import (
            is_custom_position_selected_for_widget,
        )

        return bool(
            is_custom_position_selected_for_widget("spotify_visualizer", widgets)
        )

    def effective_monitor_index(self, widgets):
        idx = self._manager._resolve_visualizer_requested_screen_index(widgets)
        return idx if idx >= 0 else None

    def resolve(self, intended_index):
        from rendering.quick.visualizer_admission import (
            resolve_quick_visualizer_admission,
        )

        admission = resolve_quick_visualizer_admission(
            intended_index, self._participants
        )
        return SimpleNamespace(
            requested_display=admission.requested,
            requested_is_participating=admission.requested_is_participating,
            fallback_display=admission.fallback,
        )

    def owner_present_on(self, display) -> bool:
        manager = self._manager
        return (
            display is not None
            and manager._quick_visualizer_unit is display
            and manager._quick_visualizer_owner is not None
        )

    def screen_index_of(self, display):
        return getattr(display, "screen_index", None)

    def create_owner(self, display, intended_index) -> bool:
        return self._manager._construct_quick_visualizer_owner_on(display)

    def cleanup_owner(self, display) -> bool:
        manager = self._manager
        owner = manager._quick_visualizer_owner
        if manager._quick_visualizer_unit is not display or owner is None:
            return True
        manager._release_quick_visualizer_routes(display)
        if not owner.is_retired:
            owner.retire()
        return bool(owner.is_retired)

    def detach_owner(self, display) -> None:
        # _release_quick_visualizer_routes already cleared the single-owner slot.
        return None

    def current_token(self) -> int:
        return int(self._manager._quick_visualizer_failover_token)

    def bump_token(self) -> int:
        self._manager._quick_visualizer_failover_token += 1
        return int(self._manager._quick_visualizer_failover_token)

    def schedule(self, delay_ms, *, target_screen_index, token, generation) -> None:
        self._manager._schedule_visualizer_failover_deadline(
            delay_ms,
            target_screen_index=target_screen_index,
            token=token,
            generation=generation,
        )
