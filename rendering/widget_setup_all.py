"""Main widget setup orchestration for WidgetManager.

Extracted from widget_manager.py (M-7 refactor) to reduce monolith size.
Contains the setup_all_widgets method that creates, configures, and starts
all overlay widgets based on settings.
"""
from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.settings.settings_manager import SettingsManager
from rendering.widget_descriptors import get_factory_widget_descriptors
from widgets.base_overlay_widget import BaseOverlayWidget

if TYPE_CHECKING:
    from rendering.widget_manager import WidgetManager
    from core.threading.manager import ThreadManager

logger = get_logger(__name__)


def setup_all_widgets(
    mgr: "WidgetManager",
    settings_manager: SettingsManager,
    screen_index: int,
    thread_manager: Optional["ThreadManager"] = None,
) -> dict:
    """Set up all overlay widgets based on settings using the factory registry.

    This is the main entry point for widget creation, replacing the
    monolithic _setup_widgets method in DisplayWidget.

    Args:
        mgr: The WidgetManager instance
        settings_manager: SettingsManager instance
        screen_index: Screen index for monitor selection
        thread_manager: Optional ThreadManager for async operations

    Returns:
        Dict of created widgets keyed by name
    """
    if not settings_manager:
        logger.warning("No settings_manager provided - widgets will not be created")
        return {}

    mgr._attach_settings_manager(settings_manager)

    # Initialize factory registry if not already done
    if mgr._factory_registry is None:
        mgr.set_factory_registry(settings_manager, thread_manager)
    else:
        try:
            mgr._factory_registry.set_thread_manager(thread_manager)
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Failed to update factory registry thread manager: %s", e)

    logger.debug("Setting up overlay widgets for screen %d via factory registry", screen_index)

    widgets_config = settings_manager.get('widgets', {})
    if not isinstance(widgets_config, dict):
        widgets_config = {}

    def _resolve_card_border_width(config: dict) -> int:
        try:
            global_cfg = config.get('global', {}) if isinstance(config, dict) else {}
            value = int(global_cfg.get('card_border_width_px', BaseOverlayWidget.get_global_border_width()))
            return max(0, min(12, value))
        except Exception:
            return BaseOverlayWidget.get_global_border_width()

    border_width = _resolve_card_border_width(widgets_config)
    BaseOverlayWidget.set_global_border_width(border_width)

    shadows_config = widgets_config.get('shadows', {}) if isinstance(widgets_config, dict) else {}

    # Reset fade coordination
    mgr.reset_fade_coordination()

    created: Dict[str, QWidget] = {}

    # Helper to check monitor selection
    def _show_on_this_monitor(monitor_sel) -> bool:
        try:
            return (monitor_sel == 'ALL') or (int(monitor_sel) == (screen_index + 1))
        except Exception as e:
            logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
            return True

    # Helper to (re)register widgets created in prior sessions
    def _reuse_existing_widget(attr_name: str, registry_name: str) -> Optional[QWidget]:
        parent = mgr._parent
        if parent is None:
            return None

        try:
            existing = getattr(parent, attr_name, None)
        except Exception as exc:
            logger.debug("[WIDGET_MANAGER] Failed to read %s for reuse: %s", attr_name, exc)
            existing = None

        if existing is None:
            return None

        logger.debug("[WIDGET_MANAGER] Reusing existing %s for %s", attr_name, registry_name)
        mgr.register_widget(registry_name, existing)
        mgr._bind_parent_attribute(attr_name, existing)
        created[attr_name] = existing
        return existing

    def _ensure_thread_manager(widget: QWidget, widget_name: str) -> None:
        """Ensure widget has ThreadManager injected."""
        if widget is None or not hasattr(widget, "set_thread_manager"):
            return
        parent_tm = getattr(mgr._parent, "_thread_manager", None)
        if parent_tm is None:
            logger.debug("[WIDGET_MANAGER] No parent ThreadManager available for %s", widget_name)
            return
        try:
            current = getattr(widget, "_thread_manager", None)
        except Exception:
            current = None
        if current is parent_tm and current is not None:
            logger.debug("[WIDGET_MANAGER] %s already has correct ThreadManager", widget_name)
            return
        try:
            widget.set_thread_manager(parent_tm)
            logger.info("[WIDGET_MANAGER] ThreadManager injected into %s (was: %s)", widget_name, current)
        except Exception as exc:
            logger.warning("[WIDGET_MANAGER] Failed to inject ThreadManager into %s: %s", widget_name, exc)

    for descriptor in get_factory_widget_descriptors():
        if not descriptor.is_enabled_in_environment():
            continue

        widget_settings = widgets_config.get(descriptor.settings_key, {})
        monitor_sel = widget_settings.get('monitor', 'ALL')
        show_on_this = _show_on_this_monitor(monitor_sel)
        logger.debug(
            "[WIDGET_MANAGER] Descriptor %s: monitor_sel=%s, screen_index=%s, show_on_this=%s",
            descriptor.settings_key,
            monitor_sel,
            screen_index,
            show_on_this,
        )
        if not show_on_this:
            continue

        if SettingsManager.to_bool(widget_settings.get('enabled', False), False):
            mgr.add_expected_overlay(descriptor.settings_key)

        widget = _reuse_existing_widget(descriptor.attr_name, descriptor.settings_key)
        if widget is None:
            factory = mgr._factory_registry.get_factory(descriptor.factory_name)
            if factory:
                factory_config = descriptor.build_widget_config(
                    widget_settings,
                    shadows_config=shadows_config,
                )
                factory_kwargs = descriptor.build_factory_kwargs(
                    widgets_config=widgets_config,
                    shadows_config=shadows_config,
                )
                widget = factory.create(mgr._parent, factory_config, **factory_kwargs)
                if widget:
                    mgr.register_widget(descriptor.settings_key, widget)
                    created[descriptor.attr_name] = widget
                    mgr._bind_parent_attribute(descriptor.attr_name, widget)

        if widget is not None:
            _ensure_thread_manager(widget, descriptor.settings_key)

    # Create Spotify widgets (require media widget) - still use direct methods
    # as they have complex media widget anchoring logic
    media_widget = created.get('media_widget')
    if media_widget:
        vol_widget = mgr.create_spotify_volume_widget(
            widgets_config, shadows_config, screen_index, thread_manager, media_widget,
        )
        if vol_widget:
            created['spotify_volume_widget'] = vol_widget
            mgr._register_spotify_secondary_fade(vol_widget)

        vis_widget = mgr.create_spotify_visualizer_widget(
            widgets_config, shadows_config, screen_index, thread_manager, media_widget,
        )
        if vis_widget:
            created['spotify_visualizer_widget'] = vis_widget
            mgr._register_spotify_secondary_fade(vis_widget)

        mute_btn = mgr.create_mute_button_widget(
            widgets_config, screen_index, thread_manager, media_widget,
        )
        if mute_btn:
            created['mute_button_widget'] = mute_btn
            mgr._register_spotify_secondary_fade(mute_btn)

        mgr._queue_spotify_visibility_sync(media_widget)

    # NOW start all widgets - ensures fade sync has complete expected overlay set
    state = mgr._fade_coordinator.describe()
    logger.debug("[FADE_SYNC] Starting %d widgets with expected overlays: %s",
                 len(created), sorted(state['participants']))

    _start_widgets(created)

    # CRITICAL: Raise widgets AFTER start() so fade coordination completes first
    for attr_name, widget in created.items():
        if widget is not None:
            try:
                widget.raise_()
                if hasattr(widget, '_tz_label') and widget._tz_label:
                    widget._tz_label.raise_()
            except Exception as e:
                logger.debug("Failed to raise %s: %s", attr_name, e)

    logger.info(f"Widget setup complete: {len(created)} widgets created and started via factories for screen {screen_index}")
    return created


def _start_widgets(created: Dict[str, QWidget]) -> None:
    """Initialize and activate all created widgets."""
    for attr_name, widget in created.items():
        if widget is None:
            continue

        started = False
        is_already_active = (
            hasattr(widget, "is_lifecycle_active") and
            callable(getattr(widget, "is_lifecycle_active")) and
            widget.is_lifecycle_active()
        )
        is_already_initialized = (
            hasattr(widget, "is_lifecycle_initialized") and
            callable(getattr(widget, "is_lifecycle_initialized")) and
            widget.is_lifecycle_initialized()
        )

        if is_already_active:
            logger.debug("[LIFECYCLE] %s already active, skipping init/activate", attr_name)
            started = True
        elif is_already_initialized:
            logger.debug("[LIFECYCLE] %s already initialized, skipping init", attr_name)
            if hasattr(widget, "activate") and callable(getattr(widget, "activate")):
                try:
                    activated = widget.activate()
                    started = started or bool(activated)
                    logger.debug(f"[LIFECYCLE] {attr_name} activate() returned {activated}")
                except Exception as e:
                    logger.debug("[LIFECYCLE] Failed to activate %s: %s", attr_name, e)
        else:
            if hasattr(widget, "initialize") and callable(getattr(widget, "initialize")):
                try:
                    # Double-check state to avoid warnings from reused widgets
                    if hasattr(widget, "is_lifecycle_active") and callable(getattr(widget, "is_lifecycle_active")):
                        if widget.is_lifecycle_active():
                            logger.debug("[LIFECYCLE] %s already active (late check), skipping init/activate", attr_name)
                            started = True
                            continue
                    if hasattr(widget, "is_lifecycle_initialized") and callable(getattr(widget, "is_lifecycle_initialized")):
                        if widget.is_lifecycle_initialized():
                            logger.debug("[LIFECYCLE] %s already initialized (late check), skipping init", attr_name)
                            if hasattr(widget, "activate") and callable(getattr(widget, "activate")):
                                try:
                                    activated = widget.activate()
                                    started = started or bool(activated)
                                    logger.debug(f"[LIFECYCLE] {attr_name} activate() returned {activated}")
                                except Exception as e:
                                    logger.debug("[LIFECYCLE] Failed to activate %s: %s", attr_name, e)
                            continue
                    initialized = widget.initialize()
                    logger.debug(f"[LIFECYCLE] {attr_name} initialize() returned {initialized}")
                    if initialized and hasattr(widget, "activate") and callable(getattr(widget, "activate")):
                        activated = widget.activate()
                        started = started or bool(activated)
                        logger.debug(f"[LIFECYCLE] {attr_name} activate() returned {activated}")
                except Exception as e:
                    logger.debug("[LIFECYCLE] Failed to init/activate %s: %s", attr_name, e)

        if not started and hasattr(widget, 'start') and callable(getattr(widget, 'start')):
            try:
                widget.start()
            except Exception as e:
                logger.debug("Failed to start %s: %s", attr_name, e)
