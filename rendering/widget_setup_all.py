"""Main widget setup orchestration for WidgetManager.

Extracted from widget_manager.py (M-7 refactor) to reduce monolith size.
Contains the setup_all_widgets method that creates, configures, and starts
all overlay widgets based on settings.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Dict, Optional, TYPE_CHECKING
import weakref

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.settings.settings_manager import SettingsManager
from core.threading.manager import ThreadManager
from rendering.multi_monitor_coordinator import get_coordinator
from rendering.widget_descriptors import (
    get_effective_monitor_value_for_widget,
    get_factory_widget_descriptors,
    is_custom_position_selected_for_widget,
)
from core.settings.capability_activation import (
    is_widget_family_effective,
)
from rendering.spotify_display_participation import describe_visualizer_spawn_display
from widgets.base_overlay_widget import BaseOverlayWidget

if TYPE_CHECKING:
    from rendering.widget_manager import WidgetManager
    from core.threading.manager import ThreadManager

logger = get_logger(__name__)

# E2.7: human-scale one-shot grace before a *temporary* fallback owner is
# created for a configured CUSTOM monitor that is momentarily unavailable. This
# tolerates real monitor HDMI/DP wake, staggered Windows/Qt participation, and a
# person physically turning the configured display on. It is a single
# token-fenced deadline, NEVER a recurring poll; event-driven reclaim (see
# reclaim_remote_custom_visualizer_owner) returns ownership to the configured
# display whenever it comes back, even long after this grace has elapsed.
REMOTE_CUSTOM_VISUALIZER_FALLBACK_GRACE_MS = 30000
SPOTIFY_CUSTOM_LAYOUT_STABILIZE_VERIFY_MS = 250
SPOTIFY_CUSTOM_LAYOUT_STABILIZE_CONFIRM_MS = 750


def _visualizer_capability_admitted_now(settings_manager) -> bool:
    """Return whether the visualizers capability is CURRENTLY admitted.

    Reads the live canonical ``widgets`` config through the settings authority
    (not a copy captured when a delayed callback was scheduled) and requires the
    ``visualizers`` family to be effective — i.e. activated AND its ``media``
    dependency activated. FAILS CLOSED: if the settings manager is missing or the
    current capability state cannot be read for any reason, returns False so a
    stale/delayed callback never creates or reuses a Visualizer after Media or
    Visualizers was deactivated (a stale Media QWidget cannot re-open the gate).
    """
    if settings_manager is None:
        return False
    try:
        current_widgets = settings_manager.get('widgets', {})
    except Exception:
        logger.debug("[SPOTIFY_VIS] capability recheck failed closed (settings read)", exc_info=True)
        return False
    if not isinstance(current_widgets, dict):
        return False
    try:
        return bool(is_widget_family_effective(current_widgets, "visualizers"))
    except Exception:
        logger.debug("[SPOTIFY_VIS] capability recheck failed closed (evaluation)", exc_info=True)
        return False


def _passive_ref(value):
    try:
        return weakref.ref(value)
    except TypeError:
        # Test doubles and immutable sentinels may not support weakrefs.  Real
        # runtime owners here are WidgetManager/QWidget instances.
        return lambda: value


def _schedule_weak_runtime_callback(
    delay_ms: int,
    owner,
    callback,
    *args,
    **kwargs,
) -> None:
    """Schedule runtime work without retaining its retiring owner."""

    owner_ref = _passive_ref(owner)
    runtime_generation = getattr(owner, "_runtime_generation", None)

    def _run() -> None:
        current_owner = owner_ref()
        if current_owner is None:
            return
        if (
            runtime_generation is not None
            and getattr(current_owner, "_runtime_generation", None)
            != runtime_generation
        ):
            return
        callback(current_owner, *args, **kwargs)

    _run._srpss_runtime_generation = runtime_generation
    ThreadManager.single_shot(max(0, int(delay_ms)), _run)


@dataclass
class _WidgetSetupContext:
    """Shared setup context for one display/widget-manager setup run."""

    mgr: "WidgetManager"
    created: Dict[str, QWidget]
    widgets_config: dict
    shadows_config: dict
    screen_index: int
    thread_manager: Optional["ThreadManager"]

    @property
    def media_widget(self) -> Optional[QWidget]:
        return self.created.get("media_widget")


def _resolve_widgets_config(settings_manager: SettingsManager) -> dict:
    widgets_config = settings_manager.get_widgets_map()
    if not isinstance(widgets_config, dict):
        return {}
    return widgets_config


def _resolve_card_border_width(config: dict) -> int:
    try:
        global_cfg = config.get('global', {}) if isinstance(config, dict) else {}
        value = int(global_cfg.get('card_border_width_px', BaseOverlayWidget.get_global_border_width()))
        return max(0, min(12, value))
    except Exception:
        return BaseOverlayWidget.get_global_border_width()


def _show_on_this_monitor(screen_index: int, monitor_sel) -> bool:
    try:
        return (monitor_sel == 'ALL') or (int(monitor_sel) == (screen_index + 1))
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Exception suppressed: %s", e)
        return True


def _ensure_factory_registry(
    mgr: "WidgetManager",
    settings_manager: SettingsManager,
    thread_manager: Optional["ThreadManager"],
) -> None:
    if mgr._factory_registry is None:
        mgr.set_factory_registry(settings_manager, thread_manager)
        return
    try:
        mgr._factory_registry.set_thread_manager(thread_manager)
    except Exception as e:
        logger.debug("[WIDGET_MANAGER] Failed to update factory registry thread manager: %s", e)


def _reuse_existing_widget(
    mgr: "WidgetManager",
    created: Dict[str, QWidget],
    attr_name: str,
    registry_name: str,
) -> Optional[QWidget]:
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


def _ensure_thread_manager(mgr: "WidgetManager", widget: QWidget, widget_name: str) -> None:
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


def _reuse_existing_secondary(
    mgr: "WidgetManager",
    created: Dict[str, QWidget],
    attr_name: str,
    registry_name: str,
) -> Optional[QWidget]:
    existing = _reuse_existing_widget(mgr, created, attr_name, registry_name)
    if existing is not None:
        _ensure_thread_manager(mgr, existing, registry_name)
    return existing


def _start_secondary_widget(widget: Optional[QWidget], attr_name: str) -> None:
    if widget is None:
        return
    _start_widgets({attr_name: widget})
    try:
        widget.raise_()
    except Exception:
        logger.debug("[WIDGET_SETUP] Failed to raise %s after deferred create", attr_name, exc_info=True)


def _capture_spotify_visualizer_custom_layout_snapshot(parent: Optional[QWidget]) -> dict[str, QRect | None] | None:
    if parent is None:
        return None

    vis = getattr(parent, "spotify_visualizer_widget", None)
    if vis is None:
        return None

    target_rect = None
    try:
        resolve_target_rect = getattr(vis, "_resolve_runtime_custom_layout_rect", None)
        if callable(resolve_target_rect):
            candidate = resolve_target_rect()
            if isinstance(candidate, QRect) and candidate.width() > 0 and candidate.height() > 0:
                target_rect = QRect(candidate)
    except Exception:
        logger.debug("[WIDGET_SETUP] Failed to resolve visualizer custom-layout target rect", exc_info=True)

    if target_rect is None:
        return None

    try:
        live_rect = QRect(vis.geometry())
    except Exception:
        logger.debug("[WIDGET_SETUP] Failed to read visualizer live geometry during startup stabilization", exc_info=True)
        live_rect = None

    overlay_rect = None
    overlay = getattr(parent, "_spotify_bars_overlay", None)
    if overlay is not None:
        try:
            overlay_rect = QRect(overlay.geometry())
        except Exception:
            logger.debug("[WIDGET_SETUP] Failed to read visualizer overlay geometry during startup stabilization", exc_info=True)
            overlay_rect = None

    return {
        "target": target_rect,
        "live": live_rect,
        "overlay": overlay_rect,
    }


def _spotify_visualizer_custom_layout_snapshot_needs_stabilization(
    snapshot: dict[str, QRect | None] | None,
) -> bool:
    if not isinstance(snapshot, dict):
        return False
    target_rect = snapshot.get("target")
    if not isinstance(target_rect, QRect):
        return False
    live_rect = snapshot.get("live")
    if not isinstance(live_rect, QRect) or live_rect != target_rect:
        return True
    overlay_rect = snapshot.get("overlay")
    if isinstance(overlay_rect, QRect) and overlay_rect != target_rect:
        return True
    return False


def _verify_saved_custom_layouts_after_startup(
    parent: Optional[QWidget],
    *,
    log_prefix: str,
    token: int,
    confirmed: bool,
) -> None:
    if parent is None:
        return

    try:
        active_token = int(getattr(parent, "_spotify_custom_layout_stabilize_token", 0))
    except Exception:
        active_token = 0
    if active_token != int(token):
        return

    snapshot = _capture_spotify_visualizer_custom_layout_snapshot(parent)
    if not _spotify_visualizer_custom_layout_snapshot_needs_stabilization(snapshot):
        if confirmed:
            try:
                setattr(parent, "_custom_layout_runtime_stabilize_pending", False)
            except Exception:
                logger.debug("[WIDGET_SETUP] Failed to clear custom-layout stabilize pending flag", exc_info=True)
        return

    if not confirmed:
        try:
            setattr(parent, "_custom_layout_runtime_stabilize_pending", True)
        except Exception:
            logger.debug("[WIDGET_SETUP] Failed to set custom-layout stabilize pending flag", exc_info=True)
        _schedule_weak_runtime_callback(
            SPOTIFY_CUSTOM_LAYOUT_STABILIZE_CONFIRM_MS,
            parent,
            _verify_saved_custom_layouts_after_startup,
            log_prefix=log_prefix,
            token=token,
            confirmed=True,
        )
        return

    try:
        setattr(parent, "_custom_layout_runtime_stabilize_pending", False)
    except Exception:
        logger.debug("[WIDGET_SETUP] Failed to clear custom-layout stabilize pending flag", exc_info=True)

    before_live = snapshot.get("live") if isinstance(snapshot, dict) else None
    before_overlay = snapshot.get("overlay") if isinstance(snapshot, dict) else None
    target_rect = snapshot.get("target") if isinstance(snapshot, dict) else None

    try:
        parent._apply_saved_custom_layouts()
    except Exception:
        logger.debug("%s Failed delayed visualizer custom-layout stabilization", log_prefix, exc_info=True)
        return

    after_snapshot = _capture_spotify_visualizer_custom_layout_snapshot(parent)
    after_live = after_snapshot.get("live") if isinstance(after_snapshot, dict) else None
    after_overlay = after_snapshot.get("overlay") if isinstance(after_snapshot, dict) else None

    if (
        isinstance(target_rect, QRect)
        and (
            before_live != after_live
            or before_overlay != after_overlay
        )
    ):
        logger.warning(
            "%s [SPOTIFY_VIS][FALLBACK] Delayed startup stabilization restored visualizer custom rect "
            "target=(%d,%d,%d,%d) live_before=%s overlay_before=%s live_after=%s overlay_after=%s",
            log_prefix,
            target_rect.x(),
            target_rect.y(),
            target_rect.width(),
            target_rect.height(),
            tuple(before_live.getRect()) if isinstance(before_live, QRect) else None,
            tuple(before_overlay.getRect()) if isinstance(before_overlay, QRect) else None,
            tuple(after_live.getRect()) if isinstance(after_live, QRect) else None,
            tuple(after_overlay.getRect()) if isinstance(after_overlay, QRect) else None,
        )


def _reapply_saved_custom_layouts_after_startup(parent: Optional[QWidget], *, log_prefix: str) -> None:
    if parent is None:
        return

    vis = getattr(parent, "spotify_visualizer_widget", None)
    before_geom = None
    if vis is not None:
        try:
            before_geom = vis.geometry()
        except Exception:
            before_geom = None

    try:
        parent._apply_saved_custom_layouts()
    except Exception:
        logger.debug("%s Failed to apply saved custom layouts after startup", log_prefix, exc_info=True)

    after_geom = None
    if vis is not None:
        try:
            after_geom = vis.geometry()
        except Exception:
            after_geom = None
    if before_geom is not None and after_geom is not None and before_geom != after_geom:
        logger.warning(
            "%s [SPOTIFY_VIS][FALLBACK] Immediate post-startup saved-layout reapply changed visualizer geometry "
            "from (%d,%d,%d,%d) to (%d,%d,%d,%d)",
            log_prefix,
            before_geom.x(),
            before_geom.y(),
            before_geom.width(),
            before_geom.height(),
            after_geom.x(),
            after_geom.y(),
            after_geom.width(),
            after_geom.height(),
        )

    try:
        setattr(parent, "_custom_layout_runtime_stabilize_pending", False)
        token = int(getattr(parent, "_spotify_custom_layout_stabilize_token", 0)) + 1
        setattr(parent, "_spotify_custom_layout_stabilize_token", token)
        _schedule_weak_runtime_callback(
            SPOTIFY_CUSTOM_LAYOUT_STABILIZE_VERIFY_MS,
            parent,
            _verify_saved_custom_layouts_after_startup,
            log_prefix=log_prefix,
            token=token,
            confirmed=False,
        )
    except Exception:
        logger.debug("%s Failed to schedule saved custom layout stabilization", log_prefix, exc_info=True)


def _create_factory_widgets(
    mgr: "WidgetManager",
    created: Dict[str, QWidget],
    widgets_config: dict,
    shadows_config: dict,
    screen_index: int,
) -> None:
    for descriptor in get_factory_widget_descriptors():
        if not descriptor.is_enabled_in_environment():
            continue

        # Application-level capability gate: a deactivated widget family owns no
        # runtime widget/model/provider. Distinct from the per-instance 'enabled'
        # checkbox below; inert while every family is activated by default.
        # Admission authority is owned by WidgetRuntimeManager (Phase E1); the
        # family id is resolved through it for the diagnostic below.
        runtime_owner = mgr._runtime_manager
        if not runtime_owner.admits_widget_family(descriptor.settings_key, widgets_config):
            logger.debug(
                "[WIDGET_MANAGER] Descriptor %s skipped by deactivated family=%s",
                descriptor.settings_key,
                runtime_owner.family_for_widget(descriptor.settings_key),
            )
            continue

        if descriptor.base_enabled_gate and descriptor.base_settings_key:
            family_settings = widgets_config.get(descriptor.base_settings_key, {})
            family_enabled = (
                SettingsManager.to_bool(family_settings.get("enabled", True), True)
                if isinstance(family_settings, dict)
                else True
            )
            if not family_enabled:
                logger.debug(
                    "[WIDGET_MANAGER] Descriptor %s skipped by disabled family=%s",
                    descriptor.settings_key,
                    descriptor.base_settings_key,
                )
                continue

        widget_settings = widgets_config.get(descriptor.settings_key, {})
        monitor_sel = widget_settings.get('monitor', 'ALL')
        show_on_this = _show_on_this_monitor(screen_index, monitor_sel)
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

        widget = _reuse_existing_widget(mgr, created, descriptor.attr_name, descriptor.settings_key)
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
                    # E1: the neutral owner builds/owns this widget's
                    # presentation-neutral runtime service (provider/model) and
                    # injects it, so the provider lifetime is not owned merely
                    # because a QWidget exists. Synchronous and pre-start so the
                    # widget uses the configured service from its first fetch.
                    mgr._runtime_manager.ensure_widget_service(
                        descriptor.settings_key, widget, widgets_config
                    )

        if widget is not None:
            _ensure_thread_manager(mgr, widget, descriptor.settings_key)


def _setup_media_owned_spotify_dependents(
    mgr: "WidgetManager",
    created: Dict[str, QWidget],
    widgets_config: dict,
    shadows_config: dict,
    screen_index: int,
    thread_manager: Optional["ThreadManager"],
    media_widget: Optional[QWidget],
) -> None:
    if media_widget is None:
        return

    vol_widget = _reuse_existing_secondary(mgr, created, "spotify_volume_widget", "spotify_volume")
    if vol_widget is None:
        vol_widget = mgr.create_spotify_volume_widget(
            widgets_config, shadows_config, screen_index, thread_manager, media_widget,
        )
    if vol_widget:
        created['spotify_volume_widget'] = vol_widget
        mgr._register_spotify_secondary_fade(vol_widget)

    mute_btn = _reuse_existing_secondary(mgr, created, "mute_button_widget", "mute_button")
    if mute_btn is None:
        mute_btn = mgr.create_mute_button_widget(
            widgets_config, screen_index, thread_manager, media_widget,
        )
    if mute_btn:
        created['mute_button_widget'] = mute_btn
        mgr._register_spotify_secondary_fade(mute_btn)

    mgr._queue_spotify_visibility_sync(media_widget)


def _setup_spotify_visualizer(
    mgr: "WidgetManager",
    created: Dict[str, QWidget],
    widgets_config: dict,
    shadows_config: dict,
    screen_index: int,
    thread_manager: Optional["ThreadManager"],
    media_widget: Optional[QWidget],
) -> Optional[QWidget]:
    # Application-level capability admission (E2): the visualizer requires BOTH
    # the visualizers capability AND its Media dependency to be activated. A
    # stale/reused Media object must not bypass this canonical gate.
    if not is_widget_family_effective(widgets_config, "visualizers"):
        return None
    vis_widget = _reuse_existing_secondary(mgr, created, "spotify_visualizer_widget", "spotify_visualizer")
    if vis_widget is None:
        vis_widget = mgr.create_spotify_visualizer_widget(
            widgets_config, shadows_config, screen_index, thread_manager, media_widget,
        )
    if vis_widget:
        created['spotify_visualizer_widget'] = vis_widget
        mgr._register_spotify_secondary_fade(vis_widget)
    return vis_widget


def _reconcile_remote_custom_visualizer(
    mgr: "WidgetManager",
    widgets_config: dict,
    shadows_config: dict,
    screen_index: int,
    thread_manager: Optional["ThreadManager"],
    media_widget: Optional[QWidget],
) -> None:
    # Same canonical capability admission for the remote CUSTOM reconcile path.
    if not is_widget_family_effective(widgets_config, "visualizers"):
        return
    if media_widget is None:
        return
    if not is_custom_position_selected_for_widget("spotify_visualizer", widgets_config):
        return
    monitor_value = get_effective_monitor_value_for_widget("spotify_visualizer", widgets_config, default="ALL")
    try:
        target_screen_index = int(monitor_value) - 1
    except Exception:
        return
    current_display = getattr(mgr, "_parent", None)
    if target_screen_index == screen_index:
        return
    resolution = describe_visualizer_spawn_display(
        target_screen_index,
        current_display=current_display,
    )
    if resolution.requested_is_participating and resolution.requested_display is not None:
        # Configured CUSTOM display is available now -> create on it immediately.
        _create_remote_custom_visualizer_on_target(
            resolution.requested_display,
            widgets_config,
            shadows_config,
            target_screen_index,
            thread_manager,
            origin_manager=mgr,
        )
        return
    # Configured target is not participating yet. E2.7 §2: give the SAME 30 s
    # one-shot grace whether the target is runtime-known-but-not-participating OR
    # completely absent from runtime (startup/wake). No immediate fallback — a
    # temporary owner is only created at the deadline if it is still unavailable,
    # and an event-driven reclaim restores it sooner if it returns first.
    _schedule_remote_custom_visualizer_fallback_recheck(
        mgr,
        widgets_config,
        shadows_config,
        screen_index,
        thread_manager,
        media_widget,
        target_screen_index=target_screen_index,
    )


def _create_remote_custom_visualizer_on_target(
    target: object,
    widgets_config: dict,
    shadows_config: dict,
    target_screen_index: int,
    thread_manager: Optional["ThreadManager"],
    origin_manager: object = None,
) -> bool:
    """Create/reuse the CUSTOM visualizer on ``target``; return True on success.

    Single creation/reuse boundary for the immediate reconcile, the delayed
    fallback recheck, and reclaim. Records/clears the coordinator failover state:
    a host that is NOT the configured monitor is a temporary fallback (recorded);
    the configured monitor owning the visualizer clears the record.
    """
    if getattr(target, "spotify_visualizer_widget", None) is not None:
        return False
    target_manager = getattr(target, "_widget_manager", None)
    if target_manager is None:
        return False
    # Final capability admission (E2 §2): re-read CURRENT canonical capability
    # state here so a stale/delayed callback (scheduled while the capability was
    # active) can never create a Visualizer after Media or Visualizers was
    # deactivated. Fails closed.
    if not _visualizer_capability_admitted_now(getattr(target_manager, "_settings_manager", None)):
        logger.debug(
            "[SPOTIFY_VIS] remote CUSTOM create skipped: visualizer capability "
            "no longer admitted at final creation boundary"
        )
        return False
    vis = target_manager.create_spotify_visualizer_widget(
        widgets_config,
        shadows_config,
        target_screen_index,
        thread_manager,
        getattr(target, "media_widget", None),
    )
    if vis is None:
        return False
    target_manager._register_spotify_secondary_fade(vis)
    try:
        target._apply_saved_custom_layouts()
    except Exception:
        logger.debug("[WIDGET_SETUP] Failed to apply saved custom layouts on remote visualizer reconcile", exc_info=True)
    _start_secondary_widget(vis, "spotify_visualizer_widget")
    _reapply_saved_custom_layouts_after_startup(
        target,
        log_prefix="[WIDGET_SETUP]",
    )
    # E2.7: record whether this is a *temporary* fallback owner (host display is
    # NOT the configured/intended monitor) or the canonical owner (host IS the
    # configured monitor). Runtime-only bookkeeping so an event-driven reclaim can
    # later hand ownership back; never persists the fallback monitor/geometry.
    try:
        host_index = getattr(target, "screen_index", None)
        coordinator = get_coordinator()
        if host_index is not None and int(host_index) != int(target_screen_index):
            coordinator.set_visualizer_fallback_owner(
                intended_index=target_screen_index,
                host=target,
                origin_manager=(origin_manager or target_manager),
            )
        else:
            # Configured monitor now owns the visualizer -> outage over; clearing
            # invalidates the failover generation, retiring any old grace callback.
            coordinator.clear_visualizer_failover()
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to update visualizer failover record", exc_info=True)
    return True


def _schedule_remote_custom_visualizer_fallback_recheck(
    mgr: "WidgetManager",
    widgets_config: dict,
    shadows_config: dict,
    screen_index: int,
    thread_manager: Optional["ThreadManager"],
    media_widget: Optional[QWidget],
    *,
    target_screen_index: int,
) -> None:
    # E2.7 (global grace authority): arm ONE grace for the single Visualizer
    # outage. If a grace/fallback is already active (another DisplayWidget armed
    # it during this same outage), arm returns None and we do NOT start or reset a
    # second 30 s deadline. The returned generation is the global authority every
    # delayed callback validates — a straggler from another display cannot act
    # after reclaim or a new outage.
    generation = get_coordinator().arm_visualizer_grace(
        intended_index=target_screen_index,
        origin_manager=mgr,
    )
    if generation is None:
        logger.debug(
            "[SPOTIFY_VIS][FALLBACK] grace already active for this outage; not arming another"
        )
        return
    token = int(getattr(mgr, "_remote_custom_visualizer_reconcile_token", 0)) + 1
    setattr(mgr, "_remote_custom_visualizer_reconcile_token", token)
    logger.warning(
        "[SPOTIFY_VIS][FALLBACK] Requested CUSTOM monitor %s not participating; "
        "arming %sms one-shot grace (gen=%s) before any temporary fallback",
        target_screen_index,
        REMOTE_CUSTOM_VISUALIZER_FALLBACK_GRACE_MS,
        generation,
    )
    media_widget_ref = _passive_ref(media_widget) if media_widget is not None else None
    _schedule_weak_runtime_callback(
        REMOTE_CUSTOM_VISUALIZER_FALLBACK_GRACE_MS,
        mgr,
        _run_remote_custom_visualizer_fallback_recheck_owned,
        copy.deepcopy(widgets_config),
        copy.deepcopy(shadows_config),
        screen_index,
        thread_manager,
        media_widget_ref,
        target_screen_index,
        token,
        generation,
    )


def _run_remote_custom_visualizer_fallback_recheck_owned(
    mgr: "WidgetManager",
    widgets_config: dict,
    shadows_config: dict,
    screen_index: int,
    thread_manager: Optional["ThreadManager"],
    media_widget_ref: "weakref.ReferenceType[QWidget] | None",
    target_screen_index: int,
    token: int,
    generation: int,
) -> None:
    media_widget = media_widget_ref() if media_widget_ref is not None else None
    _run_remote_custom_visualizer_fallback_recheck(
        mgr,
        widgets_config,
        shadows_config,
        screen_index,
        thread_manager,
        media_widget,
        target_screen_index,
        token,
        generation,
    )


def _run_remote_custom_visualizer_fallback_recheck(
    mgr: "WidgetManager",
    widgets_config: dict,
    shadows_config: dict,
    screen_index: int,
    thread_manager: Optional["ThreadManager"],
    media_widget: Optional[QWidget],
    target_screen_index: int,
    token: int,
    generation: int = 0,
) -> None:
    # Global authority (E2.7): the delayed grace callback is valid only while its
    # coordinator generation is the currently-active outage generation. Reclaim,
    # a target return, or a new outage all invalidate the old generation, so a
    # straggler from ANY DisplayWidget aborts here regardless of its local token.
    if not get_coordinator().is_visualizer_failover_generation_current(generation):
        return
    if token != int(getattr(mgr, "_remote_custom_visualizer_reconcile_token", 0)):
        return  # secondary fence: local manager token superseded
    current_display = getattr(mgr, "_parent", None)
    if current_display is None or bool(getattr(current_display, "_exiting", False)):
        return
    settings_manager = getattr(mgr, "_settings_manager", None)
    # Re-read CURRENT canonical capability state (a Media/Visualizers deactivation
    # during the grace must be honoured). Fails closed.
    if not _visualizer_capability_admitted_now(settings_manager):
        logger.debug(
            "[SPOTIFY_VIS][FALLBACK] delayed recheck skipped: visualizer "
            "capability no longer admitted"
        )
        return
    # E2.7 §gap-3: re-resolve the CURRENT canonical CUSTOM monitor/config from live
    # Settings rather than trusting the copy captured when the grace was armed, so
    # a Settings change during the grace supersedes the old pending target.
    live_widgets = None
    try:
        live_widgets = settings_manager.get("widgets", {}) if settings_manager is not None else None
    except Exception:
        logger.debug("[SPOTIFY_VIS][FALLBACK] delayed recheck failed to read live widgets", exc_info=True)
        return
    if not isinstance(live_widgets, dict):
        return
    if not is_custom_position_selected_for_widget("spotify_visualizer", live_widgets):
        # Visualizer no longer CUSTOM-routed -> pending grace superseded.
        get_coordinator().clear_visualizer_failover()
        return
    monitor_value = get_effective_monitor_value_for_widget(
        "spotify_visualizer", live_widgets, default="ALL"
    )
    try:
        current_index = int(monitor_value) - 1
    except Exception:
        return
    live_shadows = live_widgets.get("shadows", {}) if isinstance(live_widgets, dict) else {}
    live_thread_manager = getattr(current_display, "_thread_manager", None) or thread_manager
    get_coordinator().update_visualizer_failover_intended(current_index)

    resolution = describe_visualizer_spawn_display(
        current_index,
        current_display=current_display,
    )
    requested_display = resolution.requested_display
    if getattr(requested_display, "spotify_visualizer_widget", None) is not None:
        return
    if resolution.requested_is_participating and requested_display is not None:
        target = requested_display
    else:
        target = resolution.fallback_display
        if target is None:
            # No participating display at the deadline -> fail closed; do not
            # invent one. Leave the pending grace so a later display/topology
            # event can still reclaim without any polling timer.
            logger.info(
                "[SPOTIFY_VIS][FALLBACK] deadline for CUSTOM monitor %s: no participating "
                "display; failing closed (grace retained for event-driven reclaim)",
                current_index,
            )
            return
        logger.warning(
            "[SPOTIFY_VIS][FALLBACK] CUSTOM monitor %s still not participating after %sms; "
            "creating temporary fallback on participating display screen_index=%s",
            current_index,
            REMOTE_CUSTOM_VISUALIZER_FALLBACK_GRACE_MS,
            getattr(target, "screen_index", "?"),
        )
    _create_remote_custom_visualizer_on_target(
        target,
        live_widgets,
        live_shadows,
        current_index,
        live_thread_manager,
        origin_manager=mgr,
    )


def _retire_visualizer_owner(host_display: object) -> bool:
    """Retire a temporary fallback visualizer owner on ``host_display``.

    Tears down the hosted visualizer and clears the display's owner attribute so
    exactly one live owner remains after reclaim. Returns True only when the host
    is confirmed to no longer own a visualizer (E2.7: reclaim must not create the
    configured owner unless retirement is confirmed). Best-effort and idempotent.
    """
    if host_display is None:
        return True
    host_manager = getattr(host_display, "_widget_manager", None)
    existing = getattr(host_display, "spotify_visualizer_widget", None)
    if existing is None and host_manager is None:
        return True
    if host_manager is not None:
        # Fence any pending delayed fallback work owned by the host so a stale
        # callback cannot resurrect the retired fallback owner.
        try:
            token = int(getattr(host_manager, "_remote_custom_visualizer_reconcile_token", 0)) + 1
            setattr(host_manager, "_remote_custom_visualizer_reconcile_token", token)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to bump host reconcile token during retire", exc_info=True)
        # gap-4: honor cleanup_widget's explicit success/failure. If teardown of a
        # live widget fails, DO NOT unbind the attribute (that would orphan a live
        # widget and mask the failure) — fail closed so reclaim does not create a
        # second owner.
        cleanup_ok = True
        try:
            result = host_manager.cleanup_widget("spotify_visualizer")
            cleanup_ok = bool(result) or existing is None
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to cleanup temporary fallback visualizer", exc_info=True)
            cleanup_ok = False
        if not cleanup_ok:
            logger.warning(
                "[SPOTIFY_VIS] Temporary fallback visualizer cleanup failed on screen_index=%s; "
                "retirement NOT confirmed (failing closed)",
                getattr(host_display, "screen_index", "?"),
            )
            return False
        try:
            unregister = getattr(host_manager, "unregister_widget", None)
            if callable(unregister):
                unregister("spotify_visualizer")
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to unregister temporary fallback visualizer", exc_info=True)
        try:
            host_manager._bind_parent_attribute("spotify_visualizer_widget", None)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to unbind temporary fallback visualizer", exc_info=True)
    else:
        try:
            setattr(host_display, "spotify_visualizer_widget", None)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to clear fallback visualizer attribute", exc_info=True)
    # Confirm the host no longer owns a visualizer.
    confirmed = getattr(host_display, "spotify_visualizer_widget", None) is None
    if not confirmed:
        logger.warning(
            "[SPOTIFY_VIS] Temporary fallback owner retirement NOT confirmed on screen_index=%s",
            getattr(host_display, "screen_index", "?"),
        )
    return confirmed


def _resolve_live_settings_manager(coordinator, preferred: object) -> object:
    """Return a live SettingsManager: the preferred one, else any participant's."""
    settings_manager = getattr(preferred, "_settings_manager", None)
    if settings_manager is not None:
        return settings_manager
    try:
        for inst in coordinator.get_all_instances():
            mgr = getattr(inst, "_widget_manager", None)
            sm = getattr(mgr, "_settings_manager", None)
            if sm is not None:
                return sm
    except Exception:
        logger.debug("[SPOTIFY_VIS][RECLAIM] failed to resolve a live settings manager", exc_info=True)
    return None


def reclaim_remote_custom_visualizer_owner() -> None:
    """Event-driven reclaim of the configured CUSTOM visualizer display (E2.7).

    Invoked from the existing display/topology event machinery (Windows
    ``WM_DISPLAYCHANGE`` re-anchor), never a recurring poll. Handles BOTH a
    pending grace (no temporary owner yet) and a live temporary fallback: when the
    CURRENT configured CUSTOM display (re-resolved from live Settings) is
    participating again — seconds, minutes, or hours later — this hands ownership
    back to it as one reconciliation transaction.

    Contract properties:

    - **Idempotent:** no failover record -> no-op; safe under repeated events.
    - **Pending grace visible:** a runtime-known target returning before the
      deadline is restored immediately and the stale pending callback is fenced.
    - **Current config wins (gap-3):** the configured monitor is re-resolved from
      live Settings, so a Settings monitor change supersedes any old target.
    - **Retire-confirmed create (gap-4):** the configured owner is created only
      after the temporary owner's retirement is confirmed; otherwise it defers.
    - **One owner / capability current / never persists:** as E2.7 requires.
    """
    coordinator = get_coordinator()
    record = coordinator.get_visualizer_failover()
    if record is None:
        return  # no pending grace or fallback -> nothing to reclaim (idempotent)

    host = record["host"]
    origin_manager = record["origin_manager"]

    settings_manager = _resolve_live_settings_manager(coordinator, origin_manager)
    if settings_manager is None:
        return  # cannot resolve current config -> keep record for a later event

    if not _visualizer_capability_admitted_now(settings_manager):
        # Capability deactivated: a topology event must not recreate/reclaim a
        # visualizer. Leave the record; fail closed.
        logger.debug("[SPOTIFY_VIS][RECLAIM] capability not admitted; not reclaiming")
        return

    try:
        widgets_config = settings_manager.get("widgets", {})
    except Exception:
        logger.debug("[SPOTIFY_VIS][RECLAIM] failed to read live widgets config", exc_info=True)
        return
    if not isinstance(widgets_config, dict):
        return

    # gap-3: re-resolve the CURRENT configured CUSTOM monitor from live Settings.
    if not is_custom_position_selected_for_widget("spotify_visualizer", widgets_config):
        # No longer CUSTOM-routed -> failover superseded. Retire any stray owner
        # first; only declare the failover normalized if retirement is CONFIRMED
        # (blocker-2). If it is not, retain the record so a later event retries —
        # never clear while an old Visualizer may still be alive.
        if host is not None and not _retire_visualizer_owner(host):
            logger.warning(
                "[SPOTIFY_VIS][RECLAIM] not clearing failover: stray owner retirement unconfirmed "
                "(no-longer-CUSTOM branch)"
            )
            return
        coordinator.clear_visualizer_failover()
        return
    monitor_value = get_effective_monitor_value_for_widget(
        "spotify_visualizer", widgets_config, default="ALL"
    )
    try:
        current_index = int(monitor_value) - 1
    except Exception:
        return
    coordinator.update_visualizer_failover_intended(current_index)

    resolution = describe_visualizer_spawn_display(current_index, current_display=None)
    configured = resolution.requested_display
    if configured is None or not resolution.requested_is_participating:
        return  # configured display still not back -> keep the grace/fallback

    if getattr(configured, "spotify_visualizer_widget", None) is not None:
        # Configured display already owns the visualizer; retire any stray
        # temporary owner and normalize the record to a single owner. Only clear
        # if the stray owner's retirement is CONFIRMED (blocker-2); otherwise
        # retain the record so a later event retries rather than declaring
        # ownership normalized while an old Visualizer may still be alive.
        if host is not None and host is not configured:
            if not _retire_visualizer_owner(host):
                logger.warning(
                    "[SPOTIFY_VIS][RECLAIM] not clearing failover: stray owner retirement "
                    "unconfirmed (configured-already-owns branch)"
                )
                return
        coordinator.clear_visualizer_failover()
        return

    # gap-4: only create the configured owner once the temporary owner's
    # retirement is CONFIRMED; otherwise defer (never two live owners).
    if host is not None and host is not configured:
        if not _retire_visualizer_owner(host):
            logger.warning(
                "[SPOTIFY_VIS][RECLAIM] deferring reclaim: temporary owner not retired"
            )
            return

    shadows_config = widgets_config.get("shadows", {}) if isinstance(widgets_config, dict) else {}
    thread_manager = getattr(configured, "_thread_manager", None)
    logger.info(
        "[SPOTIFY_VIS][RECLAIM] CUSTOM monitor %s available; restoring visualizer to it",
        current_index,
    )
    # A successful create on the configured display clears the failover, which
    # invalidates the whole outage generation — so any still-pending delayed
    # callback (from THIS or any other DisplayWidget) aborts its generation check.
    created = _create_remote_custom_visualizer_on_target(
        configured,
        widgets_config,
        shadows_config,
        current_index,
        thread_manager,
        origin_manager=origin_manager,
    )
    if not created:
        # Creation failed (e.g. capability dropped mid-transaction). The temporary
        # owner is already retired, so leave a PENDING grace (never a dangling
        # fallback host), preserving the generation so a later event can retry.
        coordinator.repend_visualizer_failover(
            intended_index=current_index,
            origin_manager=origin_manager,
        )


def retire_visualizer_failover_on_capability_change(settings_manager) -> None:
    """Retire the GLOBAL Visualizer failover lifecycle when capability is off.

    Canonical capability-deactivation reaction (E2.7): when Media or Visualizers
    becomes ineffective, an in-flight failover (pending grace or live temporary
    fallback) must be RETIRED — not merely blocked from creating — so it cannot
    stay stuck:

    - capability still effective -> no-op (this only retires on deactivation);
    - a live temporary fallback owner is retired, and its failover record is
      discarded only when retirement is CONFIRMED (a failed retirement retains
      the record so a later event retries — never lose a live-owner record);
    - a pending grace (no owner) has its record + global generation invalidated,
      so stale delayed callbacks from the retired generation remain fenced;
    - a later explicit reactivation therefore arms a genuinely fresh generation
      and a full new 30 s grace (arm no longer refuses because the stale record is
      gone).

    Covers both Visualizers-off and Media-off effective deactivation (the
    capability check requires both the visualizers family and its media
    dependency to be active).
    """
    coordinator = get_coordinator()
    record = coordinator.get_visualizer_failover()
    if record is None:
        return  # no in-flight failover -> nothing to retire (idempotent)
    if _visualizer_capability_admitted_now(settings_manager):
        return  # still effective -> not a deactivation; leave the failover intact
    host = record.get("host")
    if host is not None:
        # Live temporary fallback owner: retire it and only discard the record
        # when retirement is CONFIRMED (never lose a live-owner record).
        if not _retire_visualizer_owner(host):
            logger.warning(
                "[SPOTIFY_VIS][DEACTIVATE] not clearing failover: temporary owner "
                "retirement unconfirmed; retaining record for retry"
            )
            return
    coordinator.clear_visualizer_failover()
    logger.info(
        "[SPOTIFY_VIS][DEACTIVATE] visualizer failover lifecycle retired (capability off); "
        "generation invalidated"
    )


def _finalize_widget_startup(mgr: "WidgetManager", created: Dict[str, QWidget]) -> None:
    parent = mgr._parent
    if parent is not None:
        try:
            parent._apply_saved_custom_layouts()
        except Exception:
            logger.debug("[WIDGET_SETUP] Failed to apply saved custom layouts before startup", exc_info=True)

    state = mgr._fade_coordinator.describe()
    logger.debug(
        "[FADE_SYNC] Starting %d widgets with expected overlays: %s",
        len(created),
        sorted(state['participants']),
    )

    _start_widgets(created)

    _reapply_saved_custom_layouts_after_startup(
        parent,
        log_prefix="[WIDGET_SETUP]",
    )

    for attr_name, widget in created.items():
        if widget is not None:
            try:
                widget.raise_()
                if hasattr(widget, '_tz_label') and widget._tz_label:
                    widget._tz_label.raise_()
            except Exception as e:
                logger.debug("Failed to raise %s: %s", attr_name, e)


def _run_spotify_setup_phases(context: _WidgetSetupContext) -> None:
    """Run the explicit Spotify-dependent setup phases in contract order."""

    _setup_media_owned_spotify_dependents(
        context.mgr,
        context.created,
        context.widgets_config,
        context.shadows_config,
        context.screen_index,
        context.thread_manager,
        context.media_widget,
    )
    _setup_spotify_visualizer(
        context.mgr,
        context.created,
        context.widgets_config,
        context.shadows_config,
        context.screen_index,
        context.thread_manager,
        context.media_widget,
    )
    _reconcile_remote_custom_visualizer(
        context.mgr,
        context.widgets_config,
        context.shadows_config,
        context.screen_index,
        context.thread_manager,
        context.media_widget,
    )


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
    _ensure_factory_registry(mgr, settings_manager, thread_manager)

    logger.debug("Setting up overlay widgets for screen %d via factory registry", screen_index)

    widgets_config = _resolve_widgets_config(settings_manager)
    border_width = _resolve_card_border_width(widgets_config)
    BaseOverlayWidget.set_global_border_width(border_width)

    shadows_config = widgets_config.get('shadows', {}) if isinstance(widgets_config, dict) else {}

    # Reset fade coordination
    mgr.reset_fade_coordination()

    created: Dict[str, QWidget] = {}
    _create_factory_widgets(mgr, created, widgets_config, shadows_config, screen_index)
    context = _WidgetSetupContext(
        mgr=mgr,
        created=created,
        widgets_config=widgets_config,
        shadows_config=shadows_config,
        screen_index=screen_index,
        thread_manager=thread_manager,
    )

    # Spotify-dependent setup remains explicit and phased:
    # 1. media-owned dependents (volume/mute)
    # 2. local visualizer
    # 3. remote Custom visualizer reconcile
    _run_spotify_setup_phases(context)
    _finalize_widget_startup(mgr, created)

    logger.info(f"Widget setup complete: {len(created)} widgets created and started via factories for screen {screen_index}")
    return created


def _start_widgets(created: Dict[str, QWidget]) -> None:
    """Initialize and activate all created widgets."""
    for attr_name, widget in created.items():
        if widget is None:
            continue

        started = False
        lifecycle_attempted = False
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
                    lifecycle_attempted = True
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
                                    lifecycle_attempted = True
                                    activated = widget.activate()
                                    started = started or bool(activated)
                                    logger.debug(f"[LIFECYCLE] {attr_name} activate() returned {activated}")
                                except Exception as e:
                                    logger.debug("[LIFECYCLE] Failed to activate %s: %s", attr_name, e)
                            continue
                    lifecycle_attempted = True
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
                if lifecycle_attempted:
                    logger.warning(
                        "[LIFECYCLE][FALLBACK] %s lifecycle startup did not activate; falling back to legacy start()",
                        attr_name,
                    )
                widget.start()
            except Exception as e:
                logger.debug("Failed to start %s: %s", attr_name, e)
