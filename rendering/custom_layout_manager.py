"""CUSTOM widget layout edit-mode session manager."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional

from PySide6.QtCore import QPoint, QRect, QSize, QTimer, QObject, QEvent, Qt
from PySide6.QtGui import QCursor, QGuiApplication, QPainter, QPixmap, QKeyEvent

from core.logging.logger import get_logger
from rendering.custom_layout_contract import (
    CUSTOM_LAYOUT_GRID_STEP_PX,
    CUSTOM_LAYOUT_MIN_WIDGET_SIZE,
    CUSTOM_LAYOUT_SNAP_GUTTER_PX,
    CUSTOM_LAYOUT_TRANSFER_THRESHOLD_PX,
    canonicalize_screen_layout_bucket,
    CustomLayoutEntry,
    choose_best_screen_for_global_rect,
    clamp_global_rect_to_screen,
    clamp_local_rect_to_bounds,
    denormalize_local_rect,
    deserialize_custom_layout_entry,
    get_screen_layout_entries_for_screen,
    get_screen_signature,
    get_screen_signature_aliases,
    get_custom_layout_restore_entry,
    load_custom_layout_map,
    load_custom_layout_restore_map,
    normalize_local_rect,
    remove_screen_layout_entry,
    resolve_snap_local_rect_for_edit,
    set_screen_layout_entry,
    should_transfer_rect_to_screen,
    write_custom_layout_map,
)
from rendering.widget_descriptors import (
    get_custom_persistence_monitor_settings_key_for_widget,
    get_custom_persistence_position_settings_key_for_widget,
    WidgetRuntimeDescriptor,
    get_effective_monitor_settings_key_for_widget,
    get_effective_position_settings_key_for_widget,
    get_layout_edit_runtime_descriptors,
    is_custom_position_selected_for_widget,
    restore_widget_family_to_authored_layout,
    sync_custom_layout_restore_routes,
    widget_writes_custom_monitor_key,
    widget_writes_custom_position_key,
)
from rendering.multi_monitor_coordinator import get_coordinator
from widgets.edit_grid_overlay_widget import EditGridOverlayWidget
from widgets.edit_shell_widget import EditShellWidget

logger = get_logger(__name__)
_MIN_CUSTOM_WIDGET_WIDTH = int(CUSTOM_LAYOUT_MIN_WIDGET_SIZE.width())
_MIN_CUSTOM_WIDGET_HEIGHT = int(CUSTOM_LAYOUT_MIN_WIDGET_SIZE.height())


class _CustomLayoutSessionKeyFilter(QObject):
    """Global key filter for the active CUSTOM edit session."""

    def eventFilter(self, watched: QObject | None, event: QEvent) -> bool:  # type: ignore[override]
        if event.type() != QEvent.Type.KeyPress:
            return False
        if not isinstance(event, QKeyEvent):
            return False
        if event.isAutoRepeat():
            return False
        active_manager = CustomLayoutManager.active_manager()
        if active_manager is None or not active_manager.is_active():
            return False
        if event.key() == Qt.Key.Key_Escape:
            active_manager.cancel_session()
            return True
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            active_manager.save_session()
            return True
        return False


@dataclass
class _ShellState:
    descriptor: WidgetRuntimeDescriptor
    widget: Any
    shell: EditShellWidget
    baseline_global_rect: QRect
    current_global_rect: QRect
    baseline_size_payload: dict[str, Any]
    current_size_payload: dict[str, Any]
    resize_scale: float
    was_visible: bool
    source_screen: Any
    source_screen_signature: str
    source_monitor_value: str
    current_screen: Any
    current_screen_signature: str
    current_monitor_value: str
    last_drag_axis: str = "both"
    removed: bool = False
    resize_origin_rect: QRect | None = None
    resize_origin_cursor: QPoint | None = None
    resize_origin_scale: float = 1.0
    resize_origin_payload: dict[str, Any] | None = None
    resize_corner: str | None = None


class CustomLayoutManager:
    """Owns one display participant in the global CUSTOM layout edit session."""

    _active_managers: list["CustomLayoutManager"] = []
    _key_filter: _CustomLayoutSessionKeyFilter | None = None
    _geo_session_counter: int = 0
    _EDIT_MODE_MIN_DIM_OPACITY = 0.5
    _restack_scheduled: bool = False
    _menu_interaction_depth: int = 0
    _restack_pending_during_menu: bool = False

    def __init__(self, display_widget) -> None:
        self._display = display_widget
        self._screen = getattr(display_widget, "_screen", None)
        self._screen_signature = get_screen_signature(self._screen)
        self._shell_states: dict[str, _ShellState] = {}
        self._special_hidden: list[tuple[Any, bool]] = []
        self._paused_visualizer: tuple[Any, bool, Any | None, bool] | None = None
        self._active = False
        self._grid_overlay: EditGridOverlayWidget | None = None
        self._deferred_processed_image: tuple[QPixmap, QPixmap, str] | None = None
        self._suppress_live_feedback_widget_ids: set[str] = set()
        self._edit_mode_dimming_restore: tuple[bool, float] | None = None
        self._display_cursor_restore_shape: Qt.CursorShape | None = None
        self._geo_session_id: str | None = None

    @classmethod
    def _next_geo_session_id(cls) -> str:
        cls._geo_session_counter += 1
        return f"geo-{cls._geo_session_counter:04d}"

    @staticmethod
    def _format_rect(rect: QRect | None) -> str:
        if not isinstance(rect, QRect):
            return "-"
        return f"({rect.x()},{rect.y()},{rect.width()},{rect.height()})"

    @staticmethod
    def _format_payload(payload: dict[str, Any] | None) -> str:
        if not payload:
            return "{}"
        parts = [f"{key}={payload[key]!r}" for key in sorted(payload.keys(), key=str)]
        return "{" + ",".join(parts) + "}"

    def _log_geo_audit(
        self,
        widget_id: str,
        phase: str,
        *,
        local_rect: QRect | None = None,
        global_rect: QRect | None = None,
        payload: dict[str, Any] | None = None,
        source: str,
        extra: str | None = None,
    ) -> None:
        session_id = self._geo_session_id or "geo-inactive"
        message = (
            "[GEO_AUDIT] session=%s widget=%s phase=%s local=%s global=%s payload=%s source=%s"
            % (
                session_id,
                widget_id,
                phase,
                self._format_rect(local_rect),
                self._format_rect(global_rect),
                self._format_payload(payload),
                source,
            )
        )
        if extra:
            message = f"{message} {extra}"
        logger.info(message)

    @staticmethod
    def _top_center_anchor_for_rect(rect: QRect) -> tuple[float, int]:
        return (float(rect.x()) + (float(rect.width()) / 2.0), int(rect.y()))

    @staticmethod
    def _rect_from_top_center(anchor_x: float, top_y: int, width: int, height: int) -> QRect:
        left = int(round(anchor_x - (float(width) / 2.0)))
        return QRect(left, int(top_y), int(width), int(height))

    def _get_available_screens(self) -> list[Any]:
        instances = self._get_global_display_instances()
        screens = [getattr(instance, "_screen", None) for instance in instances]
        screens = [screen for screen in screens if screen is not None]
        if screens:
            return screens
        return list(QGuiApplication.screens())

    def _get_global_display_instances(self) -> list[Any]:
        instances: list[Any] = []
        try:
            instances = get_coordinator().get_all_instances()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to enumerate global display instances", exc_info=True)
            instances = []
        if self._display not in instances:
            instances.append(self._display)
        instances.sort(key=lambda instance: int(getattr(instance, "screen_index", 0)))
        return instances

    def _sync_display_screen_binding(self) -> tuple[Any, str]:
        screen = getattr(self._display, "_screen", None)
        if screen is None:
            try:
                screens = self._get_available_screens()
                screen_index = int(getattr(self._display, "screen_index", 0))
                if 0 <= screen_index < len(screens):
                    screen = screens[screen_index]
                elif screens:
                    screen = screens[0]
            except Exception:
                screen = None
        self._screen = screen
        self._screen_signature = get_screen_signature(screen)
        return self._screen, self._screen_signature

    def _get_cursor_global_pos(self) -> QPoint:
        return QCursor.pos()

    def _get_display_instance_for_screen(self, screen: Any) -> Any:
        try:
            return get_coordinator().get_instance_for_screen(screen)
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to resolve display instance for screen", exc_info=True)
            return None

    @classmethod
    def active_manager(cls) -> Optional["CustomLayoutManager"]:
        return cls._active_managers[0] if cls._active_managers else None

    @classmethod
    def active_managers(cls) -> tuple["CustomLayoutManager", ...]:
        return tuple(cls._active_managers)

    @classmethod
    def is_any_session_active(cls) -> bool:
        return bool(cls._active_managers)

    @classmethod
    def _uninstall_global_key_filter(cls) -> None:
        app = QGuiApplication.instance()
        if app is None:
            cls._key_filter = None
            return
        if cls._key_filter is not None:
            try:
                app.removeEventFilter(cls._key_filter)
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to remove global key filter", exc_info=True)
        cls._key_filter = None

    def _install_global_key_filter(self) -> None:
        app = QGuiApplication.instance()
        if app is None:
            return
        CustomLayoutManager._uninstall_global_key_filter()
        try:
            key_filter = _CustomLayoutSessionKeyFilter()
            app.installEventFilter(key_filter)
            CustomLayoutManager._key_filter = key_filter
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to install global key filter", exc_info=True)
            CustomLayoutManager._key_filter = None

    @classmethod
    def raise_all_active_shells(cls) -> None:
        managers = list(cls._active_managers)
        for manager in managers:
            manager._raise_all_shells()

    @classmethod
    def schedule_raise_all_active_shells(cls, delay_ms: int = 0) -> None:
        if cls.is_menu_interaction_active():
            cls._restack_pending_during_menu = True
            return
        if cls._restack_scheduled:
            return
        cls._restack_scheduled = True

        def _run() -> None:
            cls._restack_scheduled = False
            if not cls.is_any_session_active():
                return
            cls.raise_all_active_shells()

        QTimer.singleShot(max(0, int(delay_ms)), _run)

    @classmethod
    def begin_menu_interaction(cls) -> None:
        cls._menu_interaction_depth += 1
        logger.debug("[ZORDER] begin_menu_interaction depth=%s", cls._menu_interaction_depth)

    @classmethod
    def end_menu_interaction(cls) -> None:
        if cls._menu_interaction_depth > 0:
            cls._menu_interaction_depth -= 1
        logger.debug("[ZORDER] end_menu_interaction depth=%s", cls._menu_interaction_depth)
        if cls._menu_interaction_depth == 0 and cls._restack_pending_during_menu:
            cls._restack_pending_during_menu = False
            cls.schedule_raise_all_active_shells()

    @classmethod
    def is_menu_interaction_active(cls) -> bool:
        return cls._menu_interaction_depth > 0

    @classmethod
    def has_cross_display_shells(cls) -> bool:
        for manager in cls._active_managers:
            manager_signature = str(getattr(manager, "_screen_signature", "") or "")
            for state in getattr(manager, "_shell_states", {}).values():
                if getattr(state, "removed", False):
                    continue
                if str(getattr(state, "current_screen_signature", "") or "") != manager_signature:
                    return True
        return False

    def is_active(self) -> bool:
        return bool(self._active)

    def should_defer_runtime_updates(self) -> bool:
        return bool(self._active)

    def defer_processed_image(
        self,
        processed_pixmap: QPixmap,
        original_pixmap: QPixmap,
        image_path: str,
    ) -> None:
        self._deferred_processed_image = (processed_pixmap, original_pixmap, image_path)

    def flush_deferred_processed_image(self) -> None:
        if self._deferred_processed_image is None:
            return
        payload = self._deferred_processed_image
        self._deferred_processed_image = None
        try:
            self._display.set_processed_image(*payload)
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to flush deferred image update", exc_info=True)

    def start_session(self) -> bool:
        if self._active:
            return True
        if CustomLayoutManager._active_managers:
            return self in CustomLayoutManager._active_managers

        managers: list[CustomLayoutManager] = []
        seen_ids: set[int] = set()
        for instance in self._get_global_display_instances():
            manager = getattr(instance, "_custom_layout_manager", None)
            if not isinstance(manager, CustomLayoutManager):
                continue
            if id(manager) in seen_ids:
                continue
            seen_ids.add(id(manager))
            managers.append(manager)
        session_id = CustomLayoutManager._next_geo_session_id()
        for manager in managers:
            manager._geo_session_id = session_id
        started: list[CustomLayoutManager] = []
        for manager in managers:
            if manager._start_session_local():
                started.append(manager)
        if not started:
            for manager in managers:
                manager._geo_session_id = None
            return False
        CustomLayoutManager._active_managers = started
        started[0]._refresh_duplicate_shell_remove_affordances_global()
        started[0]._install_global_key_filter()
        return True

    def save_session(self) -> bool:
        if not self._active:
            return False

        settings_manager = getattr(self._display, "settings_manager", None)
        if settings_manager is None:
            self.cancel_session()
            return False

        widgets_map = settings_manager.get_widgets_map()
        sync_custom_layout_restore_routes(widgets_map)
        custom_layout_map = load_custom_layout_map(widgets_map)

        active_managers = list(CustomLayoutManager._active_managers)
        grouped_states: dict[str, list[tuple["CustomLayoutManager", _ShellState]]] = {}
        for manager in active_managers:
            for widget_id, state in manager._shell_states.items():
                grouped_states.setdefault(widget_id, []).append((manager, state))

        for widget_id, entries in grouped_states.items():
            survivors = [(manager, state) for manager, state in entries if not state.removed]
            if not survivors:
                continue
            source_had_duplicates = len(entries) > 1
            if (
                widget_id == "spotify_visualizer"
                and len(survivors) > 1
                and any(manager._monitor_value_is_all(state.source_monitor_value) for manager, state in survivors)
            ):
                logger.warning(
                    "[CUSTOM_LAYOUT] Refusing to persist spotify_visualizer as Custom with multiple ALL-routed survivors; "
                    "leave Follow Media active until one survivor display is chosen"
                )
                continue
            for manager, state in survivors:
                monitor_value = state.current_monitor_value
                if source_had_duplicates and len(survivors) == 1 and manager._monitor_value_is_all(state.source_monitor_value):
                    monitor_value = manager._monitor_value_for_screen(state.current_screen)
                elif state.current_screen_signature != state.source_screen_signature:
                    monitor_value = manager._monitor_value_for_screen(state.current_screen)
                elif widget_id == "spotify_visualizer" and manager._monitor_value_is_all(monitor_value):
                    monitor_value = manager._monitor_value_for_screen(state.current_screen)
                manager._write_widget_custom_layout(
                    widgets_map,
                    custom_layout_map,
                    widget_id,
                    state,
                    monitor_value,
                )

        write_custom_layout_map(widgets_map, custom_layout_map)
        self._set_runtime_reload_pending_for_managers(active_managers, True)
        try:
            settings_manager.set_widgets_map(widgets_map)
            settings_manager.save()

            for manager in active_managers:
                manager._finish_session(
                    restore_live_visibility=False,
                    restore_special_widgets=False,
                )
            if not self._request_runtime_reload():
                self._reload_widgets_across_instances()
            return True
        finally:
            self._set_runtime_reload_pending_for_managers(active_managers, False)

    def reset_to_authored_layout(self) -> bool:
        """Restore the last known non-CUSTOM authored routes and exit edit mode.

        This is intentionally a commit-style action rather than a purely visual
        shell preview. It clears CUSTOM geometry, restores the saved authored
        position/monitor contract, and then performs a clean widget rebuild.
        """

        if not self._active:
            return False

        settings_manager = getattr(self._display, "settings_manager", None)
        if settings_manager is None:
            self.cancel_session()
            return False

        widgets_map = settings_manager.get_widgets_map()
        restored_any = False

        active_managers = list(CustomLayoutManager._active_managers)
        widget_ids = {
            widget_id
            for manager in active_managers
            for widget_id in manager._shell_states.keys()
        }
        for widget_id in widget_ids:
            restored_any = restore_widget_family_to_authored_layout(widgets_map, widget_id) or restored_any

        if not restored_any:
            return False

        self._set_runtime_reload_pending_for_managers(active_managers, True)
        try:
            settings_manager.set_widgets_map(widgets_map)
            settings_manager.save()

            for manager in active_managers:
                manager._finish_session(
                    restore_live_visibility=False,
                    restore_special_widgets=False,
                )
            if not self._request_runtime_reload():
                self._reload_widgets_across_instances()
            return True
        finally:
            self._set_runtime_reload_pending_for_managers(active_managers, False)

    def _start_session_local(self) -> bool:
        if self._active:
            return True

        self._sync_display_screen_binding()
        targets = self._collect_targets()
        if not targets:
            logger.debug("[CUSTOM_LAYOUT] No eligible widgets found for edit session on screen %s", self._screen_signature)
            return False

        self._active = True
        setattr(self._display, "_custom_layout_edit_active", True)
        self._suspend_interaction_cursor_state()
        self._apply_edit_cursor_policy()
        self._apply_edit_mode_dimming()
        target_widget_ids = {descriptor.widget_id for descriptor, _widget in targets}
        self._hide_special_widgets(target_widget_ids)
        self._show_grid_overlay()

        for descriptor, widget in targets:
            state = self._create_shell_state(descriptor, widget)
            if state is None:
                continue
            self._set_shell_session_flag(widget, True)
            self._shell_states[descriptor.widget_id] = state
            state.shell.show()
            if descriptor.widget_id == "spotify_visualizer":
                self._pause_visualizer_for_edit_mode(widget)
            if state.was_visible:
                try:
                    widget.hide()
                except Exception:
                    logger.debug("[CUSTOM_LAYOUT] Failed to hide %s during edit session", descriptor.widget_id, exc_info=True)

        if self._shell_states:
            self._normalize_session_stack()
            return True

        self._finish_session()
        return False

    def _request_runtime_reload(self) -> bool:
        requester = getattr(self._display, "_request_custom_layout_runtime_reload", None)
        if not callable(requester):
            return False
        try:
            requester()
            return True
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to request runtime reload; falling back to local rebuild", exc_info=True)
            return False

    @staticmethod
    def _set_runtime_reload_pending_for_managers(
        managers: list["CustomLayoutManager"],
        active: bool,
    ) -> None:
        for manager in managers:
            try:
                setattr(manager._display, "_custom_layout_runtime_reload_pending", bool(active))
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to set runtime reload pending flag", exc_info=True)

    def _write_widget_custom_layout(
        self,
        widgets_map: dict[str, Any],
        custom_layout_map: dict[str, Any],
        widget_id: str,
        state: _ShellState,
        monitor_value: str,
    ) -> None:
        target_screen = state.current_screen or self._screen
        if target_screen is None:
            target_screen, _ = self._sync_display_screen_binding()
        if target_screen is None:
            return
        target_signature = canonicalize_screen_layout_bucket(custom_layout_map, target_screen)
        if not target_signature:
            target_signature = get_screen_signature(target_screen)
        target_geom = target_screen.geometry()

        if self._monitor_value_is_all(monitor_value):
            for alias in get_screen_signature_aliases(state.current_screen or state.source_screen or target_screen):
                remove_screen_layout_entry(custom_layout_map, alias, widget_id)
        else:
            self._remove_widget_entries_from_other_displays(
                custom_layout_map,
                widget_id,
                exclude_signature=target_signature,
            )

        global_rect = QRect(state.current_global_rect)
        local_rect = QRect(
            global_rect.x() - target_geom.x(),
            global_rect.y() - target_geom.y(),
            global_rect.width(),
            global_rect.height(),
        )
        if not state.descriptor.supports_layout_resize_edit:
            local_rect.setSize(state.baseline_global_rect.size())
        local_rect = clamp_local_rect_to_bounds(
            local_rect,
            target_geom.size(),
            min_size=self._min_size_for_state(state),
        )
        size_payload = dict(state.current_size_payload)
        if state.descriptor.custom_layout_resize_mode == "clock_font":
            size_payload.setdefault(
                "display_mode",
                str(getattr(state.widget, "_display_mode", "digital") or "digital"),
            )
        entry = CustomLayoutEntry(
            widget_id=widget_id,
            rect=normalize_local_rect(local_rect, target_geom.size()),
            size_payload=size_payload,
            resize_mode=state.descriptor.custom_layout_resize_mode,
        )
        set_screen_layout_entry(custom_layout_map, target_signature, widget_id, entry)
        self._log_geo_audit(
            widget_id,
            "save_scene",
            local_rect=local_rect,
            global_rect=global_rect,
            payload=entry.size_payload,
            source="_write_widget_custom_layout",
            extra=(
                f"resize_mode={entry.resize_mode} monitor={monitor_value} "
                f"force_custom_position={str(widget_writes_custom_position_key(widget_id)).lower()}"
            ),
        )

        if widget_writes_custom_position_key(widget_id):
            position_settings_key = get_custom_persistence_position_settings_key_for_widget(widget_id)
            position_section = widgets_map.get(position_settings_key, {})
            if not isinstance(position_section, dict) or position_settings_key not in widgets_map:
                position_section = {}
                widgets_map[position_settings_key] = position_section
            position_section["position"] = "Custom"

        if widget_writes_custom_monitor_key(widget_id):
            monitor_settings_key = get_custom_persistence_monitor_settings_key_for_widget(widget_id)
            monitor_section = widgets_map.get(monitor_settings_key, {})
            if not isinstance(monitor_section, dict) or monitor_settings_key not in widgets_map:
                monitor_section = {}
                widgets_map[monitor_settings_key] = monitor_section
            monitor_section["monitor"] = monitor_value

    def _remove_widget_entries_from_other_displays(
        self,
        custom_layout_map: dict[str, Any],
        widget_id: str,
        *,
        exclude_signature: str,
    ) -> None:
        displays = custom_layout_map.get("displays", {})
        if not isinstance(displays, dict):
            return
        for screen_signature in tuple(displays.keys()):
            if screen_signature == exclude_signature:
                continue
            remove_screen_layout_entry(custom_layout_map, screen_signature, widget_id)

    def _reload_widgets_across_instances(self) -> None:
        instances: list[Any] = []
        try:
            instances = get_coordinator().get_all_instances()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to enumerate display instances for widget reload", exc_info=True)
            instances = []
        if self._display not in instances:
            instances.append(self._display)
        for instance in instances:
            try:
                self._teardown_display_widgets(instance)
                instance._setup_widgets()
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to rebuild widgets after custom layout save", exc_info=True)
                try:
                    instance._apply_saved_custom_layouts()
                except Exception:
                    logger.debug("[CUSTOM_LAYOUT] Failed to apply saved custom layouts after rebuild fallback", exc_info=True)

    def _reapply_saved_layouts_across_instances(self) -> None:
        instances: list[Any] = []
        try:
            instances = get_coordinator().get_all_instances()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to enumerate display instances for layout reapply", exc_info=True)
            instances = []
        if self._display not in instances:
            instances.append(self._display)
        for instance in instances:
            try:
                instance._apply_saved_custom_layouts()
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to reapply saved custom layouts across instances", exc_info=True)

    def _show_grid_overlay(self) -> None:
        if self._screen is None:
            self._sync_display_screen_binding()
        if self._screen is None:
            return
        try:
            global_rect = QRect(self._screen.geometry())
            overlay = EditGridOverlayWidget(
                global_rect=global_rect,
                grid_step_px=CUSTOM_LAYOUT_GRID_STEP_PX,
                gutter_px=CUSTOM_LAYOUT_SNAP_GUTTER_PX,
                parent=self._display,
            )
            overlay.show()
            self._grid_overlay = overlay
            self._raise_all_shells_globally()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to create edit grid overlay", exc_info=True)
            self._grid_overlay = None

    def _destroy_grid_overlay(self) -> None:
        overlay = self._grid_overlay
        self._grid_overlay = None
        if overlay is None:
            return
        try:
            overlay.hide()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to hide edit grid overlay", exc_info=True)
        try:
            overlay.deleteLater()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to delete edit grid overlay", exc_info=True)

    def _teardown_display_widgets(self, instance: Any) -> None:
        widget_manager = getattr(instance, "_widget_manager", None)
        if widget_manager is not None:
            try:
                widget_manager.cleanup()
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to cleanup WidgetManager before rebuild", exc_info=True)

        for attr_name in (
            "clock_widget",
            "clock2_widget",
            "clock3_widget",
            "weather_widget",
            "media_widget",
            "reddit_widget",
            "reddit2_widget",
            "gmail_widget",
            "imgur_widget",
            "spotify_volume_widget",
            "spotify_visualizer_widget",
            "mute_button_widget",
        ):
            child = getattr(instance, attr_name, None)
            if child is None:
                continue
            try:
                hide = getattr(child, "hide", None)
                if callable(hide):
                    hide()
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to hide %s during rebuild teardown", attr_name, exc_info=True)
            try:
                child.setParent(None)
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to detach %s during rebuild teardown", attr_name, exc_info=True)
            try:
                child.deleteLater()
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to deleteLater %s during rebuild teardown", attr_name, exc_info=True)
            try:
                setattr(instance, attr_name, None)
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to clear %s during rebuild teardown", attr_name, exc_info=True)

    def _monitor_value_is_all(self, monitor_value: object) -> bool:
        return str(monitor_value or "ALL").strip().upper() == "ALL"

    def _monitor_value_for_screen(self, screen: Any) -> str:
        if screen is None:
            return "ALL"
        for display in get_coordinator().get_all_instances():
            if getattr(display, "_screen", None) is screen:
                return str(int(getattr(display, "screen_index", 0)) + 1)
        for index, candidate in enumerate(self._get_available_screens()):
            if candidate is screen:
                return str(index + 1)
        return "ALL"

    def cancel_session(self) -> bool:
        if not self._active:
            return False
        active_managers = list(CustomLayoutManager._active_managers)
        for manager in active_managers:
            manager._finish_session()
        for instance in self._get_global_display_instances():
            try:
                instance._apply_saved_custom_layouts()
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to reapply saved layouts after cancel", exc_info=True)
        return True

    def apply_saved_layouts_to_display(self) -> None:
        if self._active:
            return
        settings_manager = getattr(self._display, "settings_manager", None)
        if settings_manager is None:
            return
        screen, fallback_signature = self._sync_display_screen_binding()
        widgets_map = settings_manager.get_widgets_map()
        custom_layout_map = load_custom_layout_map(widgets_map)
        matched_signature, entries = get_screen_layout_entries_for_screen(custom_layout_map, screen)
        self._screen_signature = matched_signature or fallback_signature

        for descriptor in get_layout_edit_runtime_descriptors():
            widget = getattr(self._display, descriptor.attr_name, None)
            if widget is None:
                continue
            if not is_custom_position_selected_for_widget(descriptor.widget_id, widgets_map):
                self._clear_widget_custom_layout(widget)
                continue
            payload = entries.get(descriptor.widget_id, {})
            entry = deserialize_custom_layout_entry(descriptor.widget_id, payload)
            if entry is None:
                self._clear_widget_custom_layout(widget)
                continue
            self._apply_entry_to_widget(widget, descriptor, entry)

    def _finish_session(
        self,
        *,
        restore_live_visibility: bool = True,
        restore_special_widgets: bool = True,
    ) -> None:
        for state in list(self._shell_states.values()):
            try:
                state.shell.hide()
                state.shell.deleteLater()
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to destroy edit shell", exc_info=True)
            self._set_shell_session_flag(state.widget, False)
            if restore_live_visibility and state.was_visible:
                try:
                    state.widget.show()
                except Exception:
                    logger.debug("[CUSTOM_LAYOUT] Failed to restore %s visibility", state.descriptor.widget_id, exc_info=True)
        self._shell_states.clear()
        self._destroy_grid_overlay()
        self._restore_edit_mode_dimming()
        self._restore_display_cursor_policy()

        if restore_special_widgets:
            self._restore_special_widgets()
        else:
            self._special_hidden.clear()
            self._paused_visualizer = None

        self._active = False
        if self in CustomLayoutManager._active_managers:
            CustomLayoutManager._active_managers = [
                manager for manager in CustomLayoutManager._active_managers if manager is not self
            ]
        if not CustomLayoutManager._active_managers:
            CustomLayoutManager._uninstall_global_key_filter()
        setattr(self._display, "_custom_layout_edit_active", False)
        self._geo_session_id = None
        self.flush_deferred_processed_image()

    def _suspend_interaction_cursor_state(self) -> None:
        coordinator = get_coordinator()
        try:
            coordinator.set_ctrl_held(False)
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to clear coordinator Ctrl state for edit mode", exc_info=True)
        try:
            coordinator.clear_halo_owner()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to clear halo owner for edit mode", exc_info=True)

        for instance in self._get_global_display_instances():
            try:
                setattr(instance, "_ctrl_held", False)
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to clear local Ctrl state for edit mode", exc_info=True)
            try:
                input_handler = getattr(instance, "_input_handler", None)
                if input_handler is not None:
                    input_handler.set_ctrl_held(False)
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to clear input-handler Ctrl state for edit mode", exc_info=True)
            try:
                hint = getattr(instance, "_ctrl_cursor_hint", None)
                if hint is not None:
                    try:
                        hint.cancel_animation()
                    except Exception:
                        logger.debug("[CUSTOM_LAYOUT] Failed to cancel halo animation for edit mode", exc_info=True)
                    hint.hide()
                    try:
                        hint.setOpacity(0.0)
                    except Exception:
                        logger.debug("[CUSTOM_LAYOUT] Failed to reset halo opacity for edit mode", exc_info=True)
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to hide halo for edit mode", exc_info=True)

    def _apply_edit_cursor_policy(self) -> None:
        try:
            self._display_cursor_restore_shape = self._display.cursor().shape()
        except Exception:
            self._display_cursor_restore_shape = None
        try:
            self._display.setCursor(Qt.CursorShape.ArrowCursor)
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to apply edit-mode cursor policy", exc_info=True)

    def _restore_display_cursor_policy(self) -> None:
        cursor_shape = self._display_cursor_restore_shape
        self._display_cursor_restore_shape = None
        try:
            self._display.setCursor(cursor_shape or Qt.CursorShape.BlankCursor)
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to restore display cursor policy", exc_info=True)

    def _apply_edit_mode_dimming(self) -> None:
        comp = getattr(self._display, "_gl_compositor", None)
        if comp is None or not hasattr(comp, "set_dimming"):
            self._edit_mode_dimming_restore = None
            return

        prior_enabled = bool(getattr(self._display, "_dimming_enabled", False))
        prior_opacity = float(getattr(self._display, "_dimming_opacity", 0.0) or 0.0)
        self._edit_mode_dimming_restore = (prior_enabled, prior_opacity)

        target_enabled = True
        target_opacity = max(prior_opacity, self._EDIT_MODE_MIN_DIM_OPACITY)
        try:
            self._display._dimming_enabled = target_enabled
            self._display._dimming_opacity = target_opacity
            comp.set_dimming(target_enabled, target_opacity)
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to apply edit-mode dimming", exc_info=True)

    def _restore_edit_mode_dimming(self) -> None:
        restore = self._edit_mode_dimming_restore
        self._edit_mode_dimming_restore = None
        if restore is None:
            return
        comp = getattr(self._display, "_gl_compositor", None)
        if comp is None or not hasattr(comp, "set_dimming"):
            return
        enabled, opacity = restore
        try:
            self._display._dimming_enabled = bool(enabled)
            self._display._dimming_opacity = float(opacity)
            comp.set_dimming(bool(enabled), float(opacity))
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to restore dimming after edit mode", exc_info=True)

    def _collect_targets(self) -> list[tuple[WidgetRuntimeDescriptor, Any]]:
        targets: list[tuple[WidgetRuntimeDescriptor, Any]] = []
        for descriptor in get_layout_edit_runtime_descriptors():
            widget = getattr(self._display, descriptor.attr_name, None)
            if widget is None:
                continue
            targets.append((descriptor, widget))
        return targets

    def _hide_special_widgets(self, target_widget_ids: set[str]) -> None:
        for attr_name in ("mute_button_widget",):
            widget = getattr(self._display, attr_name, None)
            if widget is None:
                continue
            was_visible = bool(getattr(widget, "isVisible", lambda: False)())
            self._special_hidden.append((widget, was_visible))
            if was_visible:
                try:
                    widget.hide()
                except Exception:
                    logger.debug("[CUSTOM_LAYOUT] Failed to hide %s", attr_name, exc_info=True)

        if "spotify_visualizer" not in target_widget_ids:
            vis = getattr(self._display, "spotify_visualizer_widget", None)
            if vis is not None:
                self._pause_visualizer_for_edit_mode(vis)

    def _pause_visualizer_for_edit_mode(self, vis: Any) -> None:
        if self._paused_visualizer is not None:
            return
        try:
            overlay = getattr(self._display, "_spotify_bars_overlay", None)
        except Exception:
            overlay = None
        was_visible = bool(getattr(vis, "isVisible", lambda: False)())
        overlay_visible = bool(getattr(overlay, "isVisible", lambda: False)()) if overlay is not None else False
        self._paused_visualizer = (vis, was_visible, overlay, overlay_visible)
        try:
            if was_visible and hasattr(vis, "stop"):
                vis.stop()
            vis.hide()
            if overlay is not None:
                overlay.hide()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to pause visualizer for edit mode", exc_info=True)

    def _restore_special_widgets(self) -> None:
        for widget, was_visible in self._special_hidden:
            if not was_visible:
                continue
            try:
                widget.show()
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to restore special widget visibility", exc_info=True)
        self._special_hidden.clear()

        if self._paused_visualizer is not None:
            vis, was_visible, overlay, overlay_visible = self._paused_visualizer
            try:
                if was_visible and hasattr(vis, "start"):
                    vis.start()
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to resume visualizer after edit mode", exc_info=True)
            try:
                if was_visible:
                    vis.show()
                if overlay is not None and overlay_visible:
                    overlay.show()
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to restore visualizer visibility after edit mode", exc_info=True)
            self._paused_visualizer = None

    def _create_shell_state(
        self,
        descriptor: WidgetRuntimeDescriptor,
        widget: Any,
    ) -> _ShellState | None:
        screen, screen_signature = self._sync_display_screen_binding()
        prior_custom_rect = getattr(widget, "_custom_layout_local_rect", None)
        try:
            local_rect = widget.geometry()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to read geometry for %s", descriptor.widget_id, exc_info=True)
            return None
        if (
            descriptor.widget_id == "spotify_visualizer"
            and isinstance(prior_custom_rect, QRect)
            and prior_custom_rect.width() > 0
            and prior_custom_rect.height() > 0
        ):
            local_rect = QRect(prior_custom_rect)

        baseline_payload = self._capture_size_payload(descriptor, widget)
        shell_local_rect = QRect(local_rect)
        if descriptor.custom_layout_resize_mode == "visualizer_rect":
            shell_local_rect.setSize(
                self._resolve_visualizer_shell_preview_size(
                    widget,
                    baseline_payload,
                    authoritative_size=local_rect.size(),
                )
            )
        try:
            if descriptor.widget_id == "spotify_visualizer":
                snapshot = self._capture_visualizer_shell_snapshot(
                    widget,
                    local_rect,
                    canvas_size=shell_local_rect.size(),
                )
            else:
                snapshot = widget.grab()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to snapshot %s", descriptor.widget_id, exc_info=True)
            return None

        global_top_left = self._display.mapToGlobal(local_rect.topLeft())
        global_rect = QRect(global_top_left, shell_local_rect.size())
        current_monitor_value = self._read_monitor_value_for_widget(descriptor)
        has_qol_envelope = shell_local_rect.size() != local_rect.size()
        shell = EditShellWidget(
            widget_id=descriptor.widget_id,
            snapshot=snapshot,
            initial_global_rect=global_rect,
            resizable=descriptor.supports_layout_resize_edit,
            live_geometry_resolver=lambda rect, cursor, _widget_id=descriptor.widget_id: self._resolve_shell_geometry_for_widget_id(
                _widget_id,
                rect,
                cursor_global=cursor,
                snap_to_grid=False,
            ),
            live_geometry_applier=lambda rect, _widget_id=descriptor.widget_id: self._apply_live_shell_geometry_for_widget_id(
                _widget_id,
                rect,
            ),
            parent=self._display,
        )
        shell.geometry_live_changed.connect(self._on_shell_geometry_live_changed)
        shell.drag_finished.connect(self._on_shell_drag_finished)
        shell.resize_wheel_requested.connect(self._on_shell_resize_wheel_requested)
        shell.resize_drag_started.connect(self._on_shell_resize_drag_started)
        shell.resize_drag_live_changed.connect(self._on_shell_resize_drag_live_changed)
        shell.resize_drag_finished.connect(self._on_shell_resize_drag_finished)
        shell.reset_size_requested.connect(self._on_shell_reset_size_requested)
        shell.reset_position_requested.connect(self._on_shell_reset_position_requested)
        shell.remove_requested.connect(self._on_shell_remove_requested)
        shell.context_menu_requested.connect(self._on_shell_context_menu_requested)
        shell.set_reset_size_enabled(False)
        shell.set_reset_position_enabled(False)
        shell.set_remove_enabled(False)
        self._log_geo_audit(
            descriptor.widget_id,
            "edit_shell_create",
            local_rect=shell_local_rect,
            global_rect=global_rect,
            payload=baseline_payload,
            source="_create_shell_state",
            extra=(
                f"preview={'live' if descriptor.custom_layout_resize_mode in {'volume_scale', 'visualizer_rect'} else 'snapshot'} "
                f"qol_envelope={str(has_qol_envelope).lower()} "
                f"had_prior_custom={str(isinstance(prior_custom_rect, QRect)).lower()}"
            ),
        )
        return _ShellState(
            descriptor=descriptor,
            widget=widget,
            shell=shell,
            baseline_global_rect=QRect(global_rect),
            current_global_rect=QRect(global_rect),
            baseline_size_payload=baseline_payload,
            current_size_payload=dict(baseline_payload),
            resize_scale=1.0,
            was_visible=bool(getattr(widget, "isVisible", lambda: False)()),
            source_screen=screen,
            source_screen_signature=screen_signature,
            source_monitor_value=current_monitor_value,
            current_screen=screen,
            current_screen_signature=screen_signature,
            current_monitor_value=current_monitor_value,
            last_drag_axis="both",
        )

    def _capture_visualizer_shell_snapshot(
        self,
        widget: Any,
        local_rect: QRect,
        canvas_size: QSize | None = None,
    ) -> QPixmap:
        capture_size = QSize(canvas_size) if isinstance(canvas_size, QSize) and not canvas_size.isEmpty() else local_rect.size()
        snapshot = QPixmap(max(1, capture_size.width()), max(1, capture_size.height()))
        snapshot.fill(Qt.GlobalColor.transparent)
        widget_snapshot = widget.grab()
        if not widget_snapshot.isNull():
            painter = QPainter(snapshot)
            try:
                painter.drawPixmap(0, 0, widget_snapshot)
            finally:
                painter.end()

        overlay = getattr(self._display, "_spotify_bars_overlay", None)
        if overlay is None:
            return snapshot

        try:
            overlay_geom = overlay.geometry()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to read visualizer overlay geometry", exc_info=True)
            return snapshot

        if overlay_geom.width() <= 0 or overlay_geom.height() <= 0:
            return snapshot

        try:
            overlay_image = overlay.grabFramebuffer()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to capture visualizer overlay framebuffer", exc_info=True)
            return snapshot

        if overlay_image.isNull():
            return snapshot

        painter = QPainter(snapshot)
        try:
            overlay_pixmap = QPixmap.fromImage(overlay_image)
            overlay_offset = overlay_geom.topLeft() - local_rect.topLeft()
            painter.drawPixmap(overlay_offset, overlay_pixmap)
        finally:
            painter.end()
        return snapshot

    def _read_monitor_value_for_widget(self, descriptor: WidgetRuntimeDescriptor) -> str:
        settings_manager = getattr(self._display, "settings_manager", None)
        if settings_manager is None:
            return "ALL"
        widgets_map = settings_manager.get_widgets_map()
        settings_key = get_effective_monitor_settings_key_for_widget(
            descriptor.widget_id,
            widgets_map,
        )
        section = widgets_map.get(settings_key, {})
        if not isinstance(section, dict):
            return "ALL"
        return str(section.get("monitor", "ALL") or "ALL")

    def _can_transfer_shell_between_displays(self, state: _ShellState) -> tuple[bool, str]:
        if self._monitor_value_is_all(state.current_monitor_value):
            return False, "Locked to ALL displays"
        return True, ""

    def _on_shell_context_menu_requested(self, global_pos: QPoint) -> None:
        try:
            self._display._show_context_menu(global_pos)
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to open context menu from shell", exc_info=True)

    def _normalize_session_stack(self) -> None:
        self._raise_all_shells_globally()

    def _raise_all_shells(self) -> None:
        for state in self._shell_states.values():
            if state.removed:
                continue
            try:
                if state.shell.isVisible():
                    state.shell.raise_()
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to raise edit shell", exc_info=True)

    def _raise_all_shells_globally(self) -> None:
        CustomLayoutManager.raise_all_active_shells()

    @classmethod
    def restore_shells_for_display(cls, display_widget: Any) -> None:
        manager = getattr(display_widget, "_custom_layout_manager", None)
        if not isinstance(manager, CustomLayoutManager):
            return
        if not cls.is_any_session_active():
            return
        manager._restore_shells_for_current_display()

    def _restore_shells_for_current_display(self) -> None:
        self._sync_display_screen_binding()
        current_signature = str(self._screen_signature or "")
        restored = 0
        for manager in list(CustomLayoutManager._active_managers):
            for state in manager._shell_states.values():
                if state.removed:
                    continue
                if str(getattr(state, "current_screen_signature", "") or "") != current_signature:
                    continue
                try:
                    manager._sync_shell_parent_to_state(state)
                    if state.shell.isVisible():
                        state.shell.raise_()
                        restored += 1
                except Exception:
                    logger.debug("[CUSTOM_LAYOUT] Failed to restore shell for current display", exc_info=True)
        logger.debug(
            "[ZORDER] restore_shells_for_display screen=%s restored=%s",
            current_signature,
            restored,
        )

    def _sync_shell_parent_to_state(self, state: _ShellState) -> None:
        self._apply_shell_global_rect_to_shell(state, state.current_global_rect, suppress_feedback=True)

    def _apply_shell_global_rect_to_shell(
        self,
        state: _ShellState,
        global_rect: QRect,
        *,
        suppress_feedback: bool,
    ) -> None:
        widget_id = state.descriptor.widget_id
        if suppress_feedback:
            self._suppress_live_feedback_widget_ids.add(widget_id)
        try:
            self._reparent_shell_to_target_display_if_needed(state)
            state.shell.set_shell_geometry(global_rect)
        finally:
            if suppress_feedback:
                self._suppress_live_feedback_widget_ids.discard(widget_id)

    def _reparent_shell_to_target_display_if_needed(self, state: _ShellState) -> None:
        target_screen = state.current_screen or self._screen
        if target_screen is None:
            return
        target_display = self._get_display_instance_for_screen(target_screen)
        if target_display is None:
            return
        if state.shell.parentWidget() is target_display:
            return
        try:
            was_visible = state.shell.isVisible()
            state.shell.setParent(target_display)
            if was_visible:
                state.shell.show()
            refresh_grab = getattr(state.shell, "_refresh_active_pointer_grab", None)
            if callable(refresh_grab):
                refresh_grab()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to reparent shell to target display", exc_info=True)

    def _resolve_shell_geometry_for_widget_id(
        self,
        widget_id: str,
        global_rect: QRect,
        *,
        cursor_global: QPoint | None,
        snap_to_grid: bool,
    ) -> QRect:
        state = self._shell_states.get(widget_id)
        if state is None:
            return QRect(global_rect)
        resolved = self._resolve_shell_global_rect(
            state,
            global_rect,
            snap_to_grid=snap_to_grid,
            cursor_global=cursor_global,
        )
        self._reparent_shell_to_target_display_if_needed(state)
        return resolved

    def _apply_live_shell_geometry_for_widget_id(self, widget_id: str, global_rect: QRect) -> None:
        state = self._shell_states.get(widget_id)
        if state is None:
            return
        dx = abs(global_rect.x() - state.current_global_rect.x())
        dy = abs(global_rect.y() - state.current_global_rect.y())
        if dx > dy:
            state.last_drag_axis = "x"
        elif dy > dx:
            state.last_drag_axis = "y"
        else:
            state.last_drag_axis = "both"
        state.current_global_rect = QRect(global_rect)
        self._apply_shell_global_rect_to_shell(state, global_rect, suppress_feedback=True)
        self._update_shell_reset_affordances(state)

    def _on_shell_geometry_live_changed(self, widget_id: str, global_rect: QRect) -> None:
        state = self._shell_states.get(widget_id)
        if state is None:
            return
        dx = abs(global_rect.x() - state.current_global_rect.x())
        dy = abs(global_rect.y() - state.current_global_rect.y())
        if dx > dy:
            state.last_drag_axis = "x"
        elif dy > dx:
            state.last_drag_axis = "y"
        else:
            state.last_drag_axis = "both"
        if widget_id in self._suppress_live_feedback_widget_ids:
            state.current_global_rect = QRect(global_rect)
            return
        resolved = self._resolve_shell_global_rect(
            state,
            global_rect,
            snap_to_grid=False,
            cursor_global=self._get_cursor_global_pos(),
        )
        state.current_global_rect = QRect(resolved)
        self._sync_shell_parent_to_state(state)
        self._update_shell_reset_affordances(state)
        if resolved != global_rect:
            self._set_shell_geometry_silently(state, resolved)

    def _on_shell_drag_finished(self, widget_id: str, global_rect: QRect, cursor_global: QPoint) -> None:
        state = self._shell_states.get(widget_id)
        if state is None:
            return
        state.last_drag_axis = "both"
        committed = self._resolve_shell_global_rect(
            state,
            global_rect,
            snap_to_grid=True,
            cursor_global=cursor_global,
        )
        state.current_global_rect = QRect(committed)
        self._sync_shell_parent_to_state(state)
        self._update_shell_reset_affordances(state)
        self._set_shell_geometry_silently(state, committed)

    def _on_shell_resize_drag_started(
        self,
        widget_id: str,
        corner: str,
        global_rect: QRect,
        cursor_global: QPoint,
    ) -> None:
        state = self._shell_states.get(widget_id)
        if state is None or not state.descriptor.supports_layout_resize_edit:
            return
        state.resize_origin_rect = QRect(global_rect)
        state.resize_origin_cursor = QPoint(cursor_global)
        state.resize_origin_scale = float(state.resize_scale)
        state.resize_origin_payload = dict(state.current_size_payload)
        state.resize_corner = str(corner or "")

    def _on_shell_resize_drag_live_changed(
        self,
        widget_id: str,
        corner: str,
        global_rect: QRect,
        cursor_global: QPoint,
    ) -> None:
        self._apply_resize_drag(widget_id, corner, global_rect, cursor_global=cursor_global, finalize=False)

    def _on_shell_resize_drag_finished(
        self,
        widget_id: str,
        corner: str,
        global_rect: QRect,
        cursor_global: QPoint,
    ) -> None:
        self._apply_resize_drag(widget_id, corner, global_rect, cursor_global=cursor_global, finalize=True)

    def _on_shell_resize_wheel_requested(self, widget_id: str, angle_delta_y: int) -> None:
        state = self._shell_states.get(widget_id)
        if state is None or not state.descriptor.supports_layout_resize_edit:
            return
        step_count = int(angle_delta_y / 120) if angle_delta_y else 0
        if step_count == 0:
            step_count = 1 if angle_delta_y > 0 else -1
        target_screen = state.current_screen or self._screen
        min_scale, max_scale = self._resize_scale_bounds_for_state(
            state,
            state.current_global_rect,
            screen=target_screen,
        )
        next_scale = max(min_scale, min(max_scale, state.resize_scale + (0.05 * step_count)))
        if abs(next_scale - state.resize_scale) < 1e-6:
            return
        state.resize_scale = next_scale
        state.current_size_payload = self._scale_size_payload(
            state.descriptor,
            state.baseline_size_payload,
            next_scale,
        )
        self._update_shell_reset_affordances(state)
        next_rect = self._scaled_rect_from_baseline(state)
        if target_screen is not None:
            next_rect = clamp_global_rect_to_screen(
                next_rect,
                target_screen,
                min_size=self._min_size_for_state(state),
            )
        state.current_global_rect = QRect(next_rect)
        anchor_x, anchor_y = self._top_center_anchor_for_rect(state.current_global_rect)
        self._log_geo_audit(
            widget_id,
            "resize_wheel",
            global_rect=next_rect,
            payload=state.current_size_payload,
            source="_on_shell_resize_wheel_requested",
            extra=(
                f"scale={state.resize_scale:.4f} min_scale={min_scale:.4f} max_scale={max_scale:.4f} "
                f"anchor=({anchor_x:.2f},{anchor_y})"
            ),
        )
        self._refresh_shell_snapshot_for_resize_preview(state, next_rect.size())
        self._set_shell_geometry_silently(state, next_rect)

    def _apply_resize_drag(
        self,
        widget_id: str,
        corner: str,
        global_rect: QRect,
        *,
        cursor_global: QPoint,
        finalize: bool,
    ) -> None:
        state = self._shell_states.get(widget_id)
        if state is None or not state.descriptor.supports_layout_resize_edit:
            return
        origin_rect = state.resize_origin_rect or QRect(state.current_global_rect)
        resolved_corner = str(corner or state.resize_corner or "")
        if not resolved_corner:
            return
        raw_scale = self._resolve_resize_drag_scale_for_corner(
            state,
            origin_rect,
            resolved_corner,
            cursor_global,
            state.resize_origin_cursor,
        )
        target_screen = state.current_screen or self._screen
        min_scale, max_scale = self._resize_scale_bounds_for_state(
            state,
            origin_rect,
            screen=target_screen,
        )
        state.resize_scale = max(min_scale, min(max_scale, raw_scale))
        state.current_size_payload = self._scale_size_payload(
            state.descriptor,
            state.baseline_size_payload,
            state.resize_scale,
        )
        next_rect = self._scaled_rect_from_anchor(
            state,
            origin_rect,
            resolved_corner,
            next_scale=state.resize_scale,
        )
        next_rect = self._resolve_resize_drag_rect_on_fixed_screen(
            state,
            next_rect,
            snap_to_grid=finalize,
        )
        state.current_global_rect = QRect(next_rect)
        self._update_shell_reset_affordances(state)
        anchor_x, anchor_y = self._top_center_anchor_for_rect(origin_rect)
        self._log_geo_audit(
            widget_id,
            "resize_drag_final" if finalize else "resize_drag_live",
            global_rect=next_rect,
            payload=state.current_size_payload,
            source="_apply_resize_drag",
            extra=(
                f"corner={resolved_corner} raw_scale={raw_scale:.4f} scale={state.resize_scale:.4f} "
                f"min_scale={min_scale:.4f} max_scale={max_scale:.4f} anchor=({anchor_x:.2f},{anchor_y})"
            ),
        )
        self._refresh_shell_snapshot_for_resize_preview(state, next_rect.size())
        self._set_shell_geometry_silently(state, next_rect)
        if finalize:
            state.resize_origin_rect = None
            state.resize_origin_cursor = None
            state.resize_origin_payload = None
            state.resize_origin_scale = state.resize_scale
            state.resize_corner = None

    def _on_shell_reset_size_requested(self, widget_id: str) -> None:
        state = self._shell_states.get(widget_id)
        if state is None:
            return
        state.resize_scale = 1.0
        state.current_size_payload = dict(state.baseline_size_payload)
        self._update_shell_reset_affordances(state)
        current = QRect(state.current_global_rect)
        baseline = QRect(state.baseline_global_rect)
        anchor_x, top_y = self._top_center_anchor_for_rect(current)
        baseline = self._rect_from_top_center(anchor_x, top_y, baseline.width(), baseline.height())
        target_screen = state.current_screen or self._screen
        if target_screen is not None:
            baseline = clamp_global_rect_to_screen(
                baseline,
                target_screen,
                min_size=self._min_size_for_state(state),
            )
        state.current_global_rect = QRect(baseline)
        self._set_shell_geometry_silently(state, baseline)

    def _on_shell_reset_position_requested(self, widget_id: str) -> None:
        state = self._shell_states.get(widget_id)
        if state is None:
            return
        source_screen = state.source_screen or self._screen
        state.current_screen = source_screen
        state.current_screen_signature = state.source_screen_signature
        state.current_monitor_value = state.source_monitor_value
        baseline_top_left = state.baseline_global_rect.topLeft()
        current_rect = QRect(state.current_global_rect)
        reset_rect = QRect(baseline_top_left, current_rect.size())
        if source_screen is not None:
            reset_rect = clamp_global_rect_to_screen(
                reset_rect,
                source_screen,
                min_size=self._min_size_for_state(state),
            )
        state.current_global_rect = QRect(reset_rect)
        state.shell.set_transfer_blocked(False, "")
        self._set_shell_geometry_silently(state, reset_rect)
        self._update_shell_reset_affordances(state)

    def _on_shell_remove_requested(self, widget_id: str) -> None:
        state = self._shell_states.get(widget_id)
        if state is None or state.removed:
            return
        state.removed = True
        try:
            state.shell.hide()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to hide removed duplicate shell", exc_info=True)
        self._refresh_duplicate_shell_remove_affordances_global()
        self._raise_all_shells_globally()

    def _set_shell_geometry_silently(self, state: _ShellState, global_rect: QRect) -> None:
        self._apply_shell_global_rect_to_shell(state, global_rect, suppress_feedback=True)
        self._update_shell_reset_affordances(state)

    def _min_size_for_descriptor(self, descriptor: WidgetRuntimeDescriptor, widget: Any | None = None) -> QSize:
        if descriptor.custom_layout_resize_mode == "volume_scale":
            return QSize(24, 120)
        if descriptor.supports_layout_resize_edit:
            if widget is not None:
                try:
                    geom = widget.geometry()
                    return QSize(
                        max(1, int(round(geom.width() * 0.5))),
                        max(1, int(round(geom.height() * 0.5))),
                    )
                except Exception:
                    logger.debug("[CUSTOM_LAYOUT] Failed to read baseline size for custom minimum", exc_info=True)
            return QSize(
                max(1, int(round(CUSTOM_LAYOUT_MIN_WIDGET_SIZE.width() * 0.5))),
                max(1, int(round(CUSTOM_LAYOUT_MIN_WIDGET_SIZE.height() * 0.5))),
            )
        if widget is not None:
            try:
                geom = widget.geometry()
                return QSize(max(1, int(geom.width())), max(1, int(geom.height())))
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to read authored size for move-only widget", exc_info=True)
        return QSize(1, 1)

    def _update_shell_reset_affordances(self, state: _ShellState) -> None:
        if state.removed:
            state.shell.set_reset_size_enabled(False)
            state.shell.set_reset_position_enabled(False)
            state.shell.set_remove_enabled(False)
            return
        size_changed = abs(state.resize_scale - 1.0) > 1e-6
        position_changed = (
            state.current_screen_signature != state.source_screen_signature
            or state.current_global_rect.topLeft() != state.baseline_global_rect.topLeft()
        )
        state.shell.set_reset_size_enabled(size_changed)
        state.shell.set_reset_position_enabled(position_changed)

    def _refresh_duplicate_shell_remove_affordances_global(self) -> None:
        grouped: dict[str, list[_ShellState]] = {}
        for manager in CustomLayoutManager._active_managers:
            for widget_id, state in manager._shell_states.items():
                grouped.setdefault(widget_id, []).append(state)
        for manager in CustomLayoutManager._active_managers:
            for widget_id, state in manager._shell_states.items():
                descriptor = state.descriptor
                survivors = [entry for entry in grouped.get(widget_id, ()) if not entry.removed]
                removable = bool(
                    widget_writes_custom_monitor_key(widget_id)
                    and len(survivors) > 1
                    and not state.removed
                )
                state.shell.set_remove_enabled(removable)

    def _refresh_shell_snapshot_for_resize_preview(self, state: _ShellState, shell_size: QSize) -> None:
        del shell_size
        # Do not mutate the live widget during preview capture. The shell's
        # existing snapshot scales with shell geometry and is intentionally only
        # a shell-shape hint, not a second live runtime layout pass.
        return

    def _collect_peer_local_rects(self, exclude_widget_id: str, screen: Any) -> list[QRect]:
        if screen is None:
            return []
        geom = screen.geometry()
        peers: list[QRect] = []
        for widget_id, state in self._shell_states.items():
            if widget_id == exclude_widget_id:
                continue
            if state.removed:
                continue
            if state.current_screen_signature != get_screen_signature(screen):
                continue
            current = state.current_global_rect
            peers.append(
                QRect(
                    current.x() - geom.x(),
                    current.y() - geom.y(),
                    current.width(),
                    current.height(),
                )
            )
        display = self._get_display_instance_for_screen(screen)
        if display is not None:
            for descriptor in get_layout_edit_runtime_descriptors():
                if descriptor.widget_id == exclude_widget_id:
                    continue
                if descriptor.widget_id in self._shell_states:
                    continue
                widget = getattr(display, descriptor.attr_name, None)
                if widget is None:
                    continue
                try:
                    peers.append(QRect(widget.geometry()))
                except Exception:
                    logger.debug("[CUSTOM_LAYOUT] Failed to inspect peer widget geometry", exc_info=True)
        return peers

    def _resolve_shell_global_rect(
        self,
        state: _ShellState,
        global_rect: QRect,
        *,
        snap_to_grid: bool,
        cursor_global: QPoint | None,
    ) -> QRect:
        target_screen = self._resolve_target_screen_for_rect(
            state,
            global_rect,
            cursor_global=cursor_global,
            transfer_threshold_px=8 if not snap_to_grid else None,
        )
        if target_screen is None:
            return QRect(global_rect)
        target_signature = get_screen_signature(target_screen)
        geom = target_screen.geometry()
        local_rect = QRect(
            global_rect.x() - geom.x(),
            global_rect.y() - geom.y(),
            global_rect.width(),
            global_rect.height(),
        )
        local_rect = clamp_local_rect_to_bounds(
            local_rect,
            geom.size(),
            min_size=self._min_size_for_state(state),
        )
        snap_resolution = resolve_snap_local_rect_for_edit(
            local_rect,
            geom.size(),
            peer_rects=self._collect_peer_local_rects(state.descriptor.widget_id, target_screen),
            threshold_px=8 if not snap_to_grid else 24,
            min_size=self._min_size_for_state(state),
        )
        if snap_to_grid:
            local_rect = snap_resolution.rect
        state.current_screen = target_screen
        state.current_screen_signature = target_signature
        self._update_grid_guides(state, target_screen, snap_resolution)
        return QRect(
            geom.x() + local_rect.x(),
            geom.y() + local_rect.y(),
            local_rect.width(),
            local_rect.height(),
        )

    def _update_grid_guides(self, state: _ShellState, target_screen: Any, snap_resolution) -> None:
        vertical_assists = snap_resolution.vertical_assists
        horizontal_assists = snap_resolution.horizontal_assists

        state.shell.set_alignment_guides(
            vertical=[(guide.position, guide.kind) for guide in snap_resolution.vertical_guides],
            horizontal=[(guide.position, guide.kind) for guide in snap_resolution.horizontal_guides],
            vertical_assists=[(guide.position, guide.kind) for guide in vertical_assists],
            horizontal_assists=[(guide.position, guide.kind) for guide in horizontal_assists],
        )
        for manager in CustomLayoutManager._active_managers:
            overlay = getattr(manager, "_grid_overlay", None)
            if overlay is None:
                continue
            if getattr(manager, "_screen", None) is target_screen:
                overlay.set_active_guides(
                    vertical=[(guide.position, guide.kind) for guide in snap_resolution.vertical_guides],
                    horizontal=[(guide.position, guide.kind) for guide in snap_resolution.horizontal_guides],
                    vertical_assists=[(guide.position, guide.kind) for guide in vertical_assists],
                    horizontal_assists=[(guide.position, guide.kind) for guide in horizontal_assists],
                )
            else:
                overlay.set_active_guides(vertical=(), horizontal=(), vertical_assists=(), horizontal_assists=())

    def _resolve_target_screen_for_rect(
        self,
        state: _ShellState,
        global_rect: QRect,
        *,
        cursor_global: QPoint | None,
        transfer_threshold_px: int | None = None,
    ) -> Any:
        screens = self._get_available_screens()
        if not screens:
            return state.current_screen or self._screen

        candidate = choose_best_screen_for_global_rect(
            global_rect,
            cursor_global=cursor_global,
            screens=screens,
        )
        if candidate is None:
            return state.current_screen or self._screen
        current_screen = state.current_screen or self._screen
        if current_screen is None or get_screen_signature(candidate) == get_screen_signature(current_screen):
            state.shell.set_transfer_blocked(False, "")
            return current_screen or candidate

        if not should_transfer_rect_to_screen(
            global_rect,
            current_screen=current_screen,
            candidate_screen=candidate,
            cursor_global=cursor_global,
            threshold_px=transfer_threshold_px if transfer_threshold_px is not None else CUSTOM_LAYOUT_TRANSFER_THRESHOLD_PX,
        ):
            state.shell.set_transfer_blocked(False, "")
            return current_screen

        can_transfer, reason = self._can_transfer_shell_between_displays(state)
        if can_transfer:
            state.shell.set_transfer_blocked(False, "")
            return candidate

        state.shell.set_transfer_blocked(True, reason)
        return current_screen

    def _scaled_rect_from_baseline(self, state: _ShellState) -> QRect:
        current = state.current_global_rect
        anchor_x, top_y = self._top_center_anchor_for_rect(current)
        return self._scaled_rect_from_top_center(
            state,
            anchor_x=anchor_x,
            top_y=top_y,
            next_scale=state.resize_scale,
            fallback_rect=current,
        )

    def _scaled_rect_from_top_center(
        self,
        state: _ShellState,
        *,
        anchor_x: float,
        top_y: int,
        next_scale: float,
        fallback_rect: QRect,
    ) -> QRect:
        next_payload = self._scale_size_payload(
            state.descriptor,
            state.baseline_size_payload,
            next_scale,
        )
        if state.descriptor.custom_layout_resize_mode == "volume_scale":
            width = max(24, int(next_payload.get("width", fallback_rect.width())))
            height = max(120, int(next_payload.get("height", fallback_rect.height())))
        elif state.descriptor.custom_layout_resize_mode == "visualizer_rect":
            width = max(48, int(next_payload.get("width", fallback_rect.width())))
            height = max(32, int(next_payload.get("height", fallback_rect.height())))
        else:
            width = max(48, int(round(state.baseline_global_rect.width() * next_scale)))
            height = max(32, int(round(state.baseline_global_rect.height() * next_scale)))
        return self._rect_from_top_center(anchor_x, top_y, width, height)

    def _resize_scale_bounds_for_state(
        self,
        state: _ShellState,
        anchor_rect: QRect,
        *,
        screen: Any | None,
    ) -> tuple[float, float]:
        min_scale = 0.5
        if screen is None:
            return min_scale, max(min_scale, 0.5)
        anchor_x, top_y = self._top_center_anchor_for_rect(anchor_rect)

        def _fits(scale: float) -> bool:
            rect = self._scaled_rect_from_top_center(
                state,
                anchor_x=anchor_x,
                top_y=top_y,
                next_scale=scale,
                fallback_rect=anchor_rect,
            )
            clamped = clamp_global_rect_to_screen(
                rect,
                screen,
                min_size=self._min_size_for_state(state),
            )
            return clamped.size() == rect.size()

        if not _fits(min_scale):
            return min_scale, min_scale

        low = min_scale
        high = max(1.0, low)
        while high < 64.0 and _fits(high):
            low = high
            high *= 2.0
        high = min(high, 64.0)
        for _ in range(28):
            mid = (low + high) / 2.0
            if _fits(mid):
                low = mid
            else:
                high = mid
        return min_scale, max(min_scale, low)

    def _resolve_resize_drag_scale_for_corner(
        self,
        state: _ShellState,
        origin_rect: QRect,
        corner: str,
        cursor_global: QPoint,
        origin_cursor: QPoint | None,
    ) -> float:
        screen = state.current_screen or self._screen
        if screen is None:
            return state.resize_scale
        min_size = self._min_size_for_state(state)
        base_half_width = max(1.0, float(origin_rect.width()) / 2.0)
        base_height = max(1.0, float(origin_rect.height()))
        base_diag = max(1.0, math.hypot(base_half_width, base_height))

        _corner = str(corner or "")
        if origin_cursor is None:
            if _corner == "top_left":
                origin_cursor = origin_rect.topLeft()
            elif _corner == "top_right":
                origin_cursor = origin_rect.topRight()
            elif _corner == "bottom_left":
                origin_cursor = origin_rect.bottomLeft()
            else:
                origin_cursor = origin_rect.bottomRight()

        delta_x = float(cursor_global.x() - origin_cursor.x())
        delta_y = float(cursor_global.y() - origin_cursor.y())
        horizontal_sign = -1.0 if _corner.endswith("left") else 1.0
        vertical_sign = -1.0 if _corner.startswith("top_") else 1.0

        target_half_width = max(
            float(min_size.width()) / 2.0,
            base_half_width + (delta_x * horizontal_sign),
        )
        target_height = max(
            float(min_size.height()),
            base_height + (delta_y * vertical_sign),
        )
        target_diag = max(1.0, math.hypot(target_half_width, target_height))
        return max(0.5, state.resize_origin_scale * (target_diag / base_diag))

    def _resolve_resize_drag_rect_on_fixed_screen(
        self,
        state: _ShellState,
        global_rect: QRect,
        *,
        snap_to_grid: bool,
    ) -> QRect:
        target_screen = state.current_screen or self._screen
        if target_screen is None:
            return QRect(global_rect)
        target_signature = get_screen_signature(target_screen)
        geom = target_screen.geometry()
        local_rect = QRect(
            global_rect.x() - geom.x(),
            global_rect.y() - geom.y(),
            global_rect.width(),
            global_rect.height(),
        )
        local_rect = clamp_local_rect_to_bounds(
            local_rect,
            geom.size(),
            min_size=self._min_size_for_state(state),
        )
        snap_resolution = resolve_snap_local_rect_for_edit(
            local_rect,
            geom.size(),
            peer_rects=self._collect_peer_local_rects(state.descriptor.widget_id, target_screen),
            threshold_px=6 if not snap_to_grid else 10,
            min_size=self._min_size_for_state(state),
        )
        if snap_to_grid:
            local_rect = snap_resolution.rect
        state.current_screen = target_screen
        state.current_screen_signature = target_signature
        self._update_grid_guides(state, target_screen, snap_resolution)
        return QRect(
            geom.x() + local_rect.x(),
            geom.y() + local_rect.y(),
            local_rect.width(),
            local_rect.height(),
        )

    def _scaled_rect_from_anchor(
        self,
        state: _ShellState,
        origin_rect: QRect,
        corner: str,
        *,
        next_scale: float,
    ) -> QRect:
        del corner
        anchor_x, top_y = self._top_center_anchor_for_rect(origin_rect)
        return self._scaled_rect_from_top_center(
            state,
            anchor_x=anchor_x,
            top_y=top_y,
            next_scale=next_scale,
            fallback_rect=origin_rect,
        )

    def _capture_size_payload(
        self,
        descriptor: WidgetRuntimeDescriptor,
        widget: Any,
    ) -> dict[str, Any]:
        mode = descriptor.custom_layout_resize_mode
        if mode == "clock_font":
            return {
                "font_size": int(getattr(widget, "_font_size", 48)),
                "display_mode": str(getattr(widget, "_display_mode", "digital") or "digital"),
            }
        if mode == "weather_scale":
            return {
                "font_size": int(getattr(widget, "_font_size", 18)),
                "icon_size": int(getattr(widget, "_icon_size", 32)),
                "detail_icon_size": int(getattr(widget, "_detail_icon_size", 16)),
            }
        if mode == "media_scale":
            return {
                "font_size": int(getattr(widget, "_font_size", 14)),
                "artwork_size": int(getattr(widget, "_artwork_size", 80)),
            }
        if mode == "reddit_font":
            return {"font_size": int(getattr(widget, "_font_size", 18))}
        if mode == "gmail_font":
            return {
                "font_size": int(getattr(widget, "_font_size", 13)),
                "sender_column_width": int(getattr(widget, "_sender_column_width", 180)),
            }
        if mode == "imgur_scale":
            return {
                "header_font_size": int(getattr(widget, "_header_font_size", 14)),
                "image_spacing": int(getattr(widget, "_image_spacing", 4)),
                "cell_base_width": int(getattr(widget, "_cell_base_width", 120)),
                "image_border_width": int(getattr(widget, "_image_border_width", 2)),
            }
        if mode == "volume_scale":
            return {
                "width": int(widget.width()),
                "height": int(widget.height()),
                "track_width": int(getattr(widget, "_track_width", 18)),
                "track_margin": int(getattr(widget, "_track_margin", 6)),
            }
        if mode == "visualizer_rect":
            committed_rect = getattr(widget, "_custom_layout_local_rect", None)
            if isinstance(committed_rect, QRect) and committed_rect.width() > 0 and committed_rect.height() > 0:
                return {
                    "width": int(committed_rect.width()),
                    "height": int(committed_rect.height()),
                }
            try:
                live_rect = QRect(widget.geometry())
            except Exception:
                live_rect = QRect()
            return {
                "width": max(10, int(live_rect.width() or 100)),
                "height": max(_MIN_CUSTOM_WIDGET_HEIGHT, int(live_rect.height() or 80)),
            }
        return {}

    def _scale_size_payload(
        self,
        descriptor: WidgetRuntimeDescriptor,
        baseline_payload: dict[str, Any],
        scale: float,
    ) -> dict[str, Any]:
        mode = descriptor.custom_layout_resize_mode
        if mode == "clock_font":
            base = int(baseline_payload.get("font_size", 48))
            return {
                "font_size": max(12, int(round(base * scale))),
                "display_mode": str(baseline_payload.get("display_mode", "digital") or "digital"),
            }
        if mode == "weather_scale":
            font_size = max(10, int(round(int(baseline_payload.get("font_size", 18)) * scale)))
            icon_size = max(12, int(round(int(baseline_payload.get("icon_size", 32)) * scale)))
            detail_size = max(8, int(round(int(baseline_payload.get("detail_icon_size", 16)) * scale)))
            return {
                "font_size": font_size,
                "icon_size": icon_size,
                "detail_icon_size": detail_size,
            }
        if mode == "media_scale":
            font_size = max(10, int(round(int(baseline_payload.get("font_size", 14)) * scale)))
            artwork_size = max(48, int(round(int(baseline_payload.get("artwork_size", 80)) * scale)))
            return {
                "font_size": font_size,
                "artwork_size": artwork_size,
            }
        if mode == "reddit_font":
            base = int(baseline_payload.get("font_size", 18))
            return {"font_size": max(8, int(round(base * scale)))}
        if mode == "gmail_font":
            base = int(baseline_payload.get("font_size", 13))
            sender_column_width = int(baseline_payload.get("sender_column_width", 180))
            return {
                "font_size": max(8, int(round(base * scale))),
                "sender_column_width": max(40, int(round(sender_column_width * scale))),
            }
        if mode == "imgur_scale":
            return {
                "header_font_size": max(10, int(round(int(baseline_payload.get("header_font_size", 14)) * scale))),
                "image_spacing": max(0, min(20, int(round(int(baseline_payload.get("image_spacing", 4)) * scale)))),
                "cell_base_width": max(80, int(round(int(baseline_payload.get("cell_base_width", 120)) * scale))),
                "image_border_width": max(0, min(5, int(round(int(baseline_payload.get("image_border_width", 2)) * scale)))),
            }
        if mode == "volume_scale":
            effective_scale = float(scale)
            if effective_scale < 1.0:
                # Shrunk volume sliders need a little extra contraction so the
                # live lane stays balanced beside smaller media cards.
                effective_scale *= 0.9
            return {
                "width": max(24, int(round(int(baseline_payload.get("width", 32)) * effective_scale))),
                "height": max(120, int(round(int(baseline_payload.get("height", 180)) * effective_scale))),
                "track_width": max(10, int(round(int(baseline_payload.get("track_width", 18)) * effective_scale))),
                "track_margin": max(2, int(round(int(baseline_payload.get("track_margin", 6)) * effective_scale))),
            }
        if mode == "visualizer_rect":
            base_width = max(10, int(baseline_payload.get("width", 100)))
            base_height = max(_MIN_CUSTOM_WIDGET_HEIGHT, int(baseline_payload.get("height", 80)))
            return {
                "width": max(10, int(round(base_width * scale))),
                "height": max(_MIN_CUSTOM_WIDGET_HEIGHT, int(round(base_height * scale))),
            }
        return dict(baseline_payload)

    def _apply_size_payload(self, descriptor: WidgetRuntimeDescriptor, widget: Any, payload: dict[str, Any]) -> None:
        mode = descriptor.custom_layout_resize_mode
        try:
            if mode == "clock_font":
                if hasattr(widget, "set_display_mode"):
                    widget.set_display_mode(str(payload.get("display_mode", getattr(widget, "_display_mode", "digital"))))
                widget.set_font_size(int(payload.get("font_size", getattr(widget, "_font_size", 48))))
                return
            if mode == "weather_scale":
                widget.set_font_size(int(payload.get("font_size", getattr(widget, "_font_size", 18))))
                widget.set_icon_size(int(payload.get("icon_size", getattr(widget, "_icon_size", 32))))
                widget.set_detail_icon_size(int(payload.get("detail_icon_size", getattr(widget, "_detail_icon_size", 16))))
                return
            if mode == "media_scale":
                widget.set_font_size(int(payload.get("font_size", getattr(widget, "_font_size", 14))))
                widget.set_artwork_size(int(payload.get("artwork_size", getattr(widget, "_artwork_size", 80))))
                return
            if mode == "reddit_font":
                widget.set_font_size(int(payload.get("font_size", getattr(widget, "_font_size", 18))))
                return
            if mode == "gmail_font":
                widget.set_font_size(int(payload.get("font_size", getattr(widget, "_font_size", 13))))
                widget.set_sender_column_width(
                    int(payload.get("sender_column_width", getattr(widget, "_sender_column_width", 180)))
                )
                return
            if mode == "imgur_scale":
                widget.set_header_font_size(int(payload.get("header_font_size", getattr(widget, "_header_font_size", 14))))
                widget.set_image_spacing(int(payload.get("image_spacing", getattr(widget, "_image_spacing", 4))))
                widget.set_cell_base_width(int(payload.get("cell_base_width", getattr(widget, "_cell_base_width", 120))))
                widget.set_image_border_width(int(payload.get("image_border_width", getattr(widget, "_image_border_width", 2))))
                return
            if mode == "volume_scale":
                widget.apply_scale_contract(
                    width=int(payload.get("width", widget.width())),
                    height=int(payload.get("height", widget.height())),
                    track_width=int(payload.get("track_width", getattr(widget, "_track_width", 18))),
                    track_margin=int(payload.get("track_margin", getattr(widget, "_track_margin", 6))),
                )
                return
            if mode == "visualizer_rect":
                return
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to apply size payload for %s", descriptor.widget_id, exc_info=True)

    def _clear_widget_custom_layout(self, widget: Any) -> None:
        try:
            if hasattr(widget, "_custom_layout_local_rect"):
                delattr(widget, "_custom_layout_local_rect")
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to clear custom rect", exc_info=True)
        try:
            restore_constraints = getattr(widget, "_restore_custom_layout_size_constraints", None)
            if callable(restore_constraints):
                restore_constraints()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to restore authored size constraints after clearing custom layout", exc_info=True)
        try:
            update_position = getattr(widget, "_update_position", None)
            if callable(update_position):
                update_position()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to restore default position after clearing custom layout", exc_info=True)

    def _resolve_visualizer_shell_preview_size(
        self,
        widget: Any,
        payload: dict[str, Any],
        *,
        authoritative_size: QSize,
    ) -> QSize:
        fallback_size = QSize(
            max(1, authoritative_size.width()),
            max(1, authoritative_size.height()),
        )
        envelope_size = self._resolve_visualizer_custom_size(
            widget,
            payload,
            maximum_envelope=True,
            fallback_size=fallback_size,
        )
        # Visualizer QoL shell previews may grow vertically to show the
        # maximum authored envelope, but committed CUSTOM width remains
        # authoritative and must never narrow or widen here.
        return QSize(
            fallback_size.width(),
            max(fallback_size.height(), envelope_size.height()),
        )

    def _resolve_visualizer_custom_size(
        self,
        widget: Any,
        payload: dict[str, Any],
        *,
        maximum_envelope: bool,
        fallback_size: QSize,
    ) -> QSize:
        from widgets.spotify_visualizer.card_geometry import (
            build_growth_map_from_widget,
            resolve_custom_card_size,
        )

        try:
            anchor = getattr(widget, "_anchor_media", None)
            if anchor is not None:
                media_width = max(10, int(anchor.geometry().width()))
            else:
                media_width = max(10, int(fallback_size.width()))
        except Exception:
            media_width = max(10, int(fallback_size.width()))

        try:
            mode_id = str(getattr(widget, "_vis_mode_str", "spectrum") or "spectrum")
            growth_map = build_growth_map_from_widget(widget)
            base_height = int(getattr(widget, "_base_height", max(40, fallback_size.height())))
            blob_width = float(getattr(widget, "_blob_width", 1.0))
            authored_current_size = resolve_custom_card_size(
                mode_id=mode_id,
                media_width=media_width,
                base_height=base_height,
                growth_by_mode=growth_map,
                blob_width=blob_width,
                width_scale=1.0,
                height_scale=1.0,
                maximum_envelope=False,
            )
            if maximum_envelope:
                envelope_size = resolve_custom_card_size(
                    mode_id=mode_id,
                    media_width=media_width,
                    base_height=base_height,
                    growth_by_mode=growth_map,
                    blob_width=blob_width,
                    width_scale=1.0,
                    height_scale=1.0,
                    maximum_envelope=True,
                )
                authored_height = max(_MIN_CUSTOM_WIDGET_HEIGHT, int(authored_current_size.height()))
                current_height = max(_MIN_CUSTOM_WIDGET_HEIGHT, int(fallback_size.height()))
                height_scale = max(0.4, min(1.0, float(current_height) / float(authored_height)))
                return QSize(
                    max(10, int(fallback_size.width())),
                    max(_MIN_CUSTOM_WIDGET_HEIGHT, int(round(envelope_size.height() * height_scale))),
                )

            if "width" in payload or "height" in payload:
                return QSize(
                    max(10, int(payload.get("width", fallback_size.width()))),
                    max(_MIN_CUSTOM_WIDGET_HEIGHT, int(payload.get("height", fallback_size.height()))),
                )

            return resolve_custom_card_size(
                mode_id=mode_id,
                media_width=media_width,
                base_height=base_height,
                growth_by_mode=growth_map,
                blob_width=blob_width,
                width_scale=float(payload.get("width_scale", 1.0)),
                height_scale=float(payload.get("height_scale", 1.0)),
                maximum_envelope=False,
            )
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to resolve adaptive visualizer custom size", exc_info=True)
            return QSize(max(1, fallback_size.width()), max(1, fallback_size.height()))

    def _apply_entry_to_widget(
        self,
        widget: Any,
        descriptor: WidgetRuntimeDescriptor,
        entry: CustomLayoutEntry,
    ) -> None:
        if self._screen is None:
            self._sync_display_screen_binding()
        if self._screen is None:
            return
        local_rect = denormalize_local_rect(entry.rect, self._screen.geometry().size())
        if not descriptor.supports_layout_resize_edit:
            try:
                local_rect.setSize(widget.geometry().size())
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to reuse authored size for move-only widget", exc_info=True)
        min_size = QSize(1, 1) if descriptor.supports_layout_resize_edit else self._min_size_for_descriptor(descriptor, widget)
        local_rect = clamp_local_rect_to_bounds(
            local_rect,
            self._screen.geometry().size(),
            min_size=min_size,
        )
        try:
            pre_widget_rect = QRect(widget.geometry())
        except Exception:
            pre_widget_rect = None
        self._log_geo_audit(
            descriptor.widget_id,
            "replay_start",
            local_rect=local_rect,
            global_rect=pre_widget_rect,
            payload=entry.size_payload,
            source="_apply_entry_to_widget",
            extra=f"resize_mode={entry.resize_mode}",
        )
        setattr(widget, "_custom_layout_local_rect", QRect(local_rect))
        try:
            # Prime the real committed rect before any min/max constraint lock
            # can resize the widget in-place at a stale authored/startup origin.
            widget.setGeometry(local_rect)
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to prime committed custom rect for %s", descriptor.widget_id, exc_info=True)
        try:
            apply_constraints = getattr(widget, "_apply_custom_layout_size_constraints_if_active", None)
            if callable(apply_constraints):
                apply_constraints()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to lock custom size constraints for %s", descriptor.widget_id, exc_info=True)
        self._apply_size_payload(descriptor, widget, entry.size_payload)
        try:
            self._log_geo_audit(
                descriptor.widget_id,
                "replay_after_payload",
                local_rect=QRect(widget.geometry()),
                global_rect=QRect(widget.geometry()),
                payload=entry.size_payload,
                source="_apply_entry_to_widget",
            )
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to log replay_after_payload geometry", exc_info=True)
        try:
            set_stack_offset = getattr(widget, "set_stack_offset", None)
            if callable(set_stack_offset):
                set_stack_offset(QPoint(0, 0))
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to clear stack offset for custom layout", exc_info=True)
        try:
            update_position = getattr(widget, "_update_position", None)
            if callable(update_position):
                update_position()
            else:
                widget.setGeometry(local_rect)
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to apply custom rect to %s", descriptor.widget_id, exc_info=True)
        try:
            self._log_geo_audit(
                descriptor.widget_id,
                "replay_after_update_position",
                local_rect=QRect(widget.geometry()),
                global_rect=QRect(widget.geometry()),
                payload=entry.size_payload,
                source="_apply_entry_to_widget",
            )
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to log replay_after_update_position geometry", exc_info=True)
        try:
            widget.setGeometry(local_rect)
        except Exception:
            logger.debug(
                "[CUSTOM_LAYOUT] Failed to reassert committed custom rect for %s after size payload apply",
                descriptor.widget_id,
                exc_info=True,
            )
        try:
            self._log_geo_audit(
                descriptor.widget_id,
                "replay_final",
                local_rect=QRect(widget.geometry()),
                global_rect=QRect(widget.geometry()),
                payload=entry.size_payload,
                source="_apply_entry_to_widget",
            )
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to log replay_final geometry", exc_info=True)
        if descriptor.widget_id == "spotify_visualizer":
            try:
                from rendering.display_image_ops import sync_spotify_visualizer_overlay_geometry

                sync_spotify_visualizer_overlay_geometry(self._display)
            except Exception:
                logger.debug("[CUSTOM_LAYOUT] Failed to sync visualizer overlay geometry after custom replay", exc_info=True)
        try:
            if bool(getattr(widget, "isVisible", lambda: False)()):
                widget.raise_()
            tz_label = getattr(widget, "_tz_label", None)
            if tz_label is not None:
                tz_label.raise_()
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to finalize widget layering after custom apply", exc_info=True)

    def _set_shell_session_flag(self, widget: Any, active: bool) -> None:
        try:
            setattr(widget, "_custom_layout_shell_active", bool(active))
        except Exception:
            logger.debug("[CUSTOM_LAYOUT] Failed to set shell-active flag", exc_info=True)

    def _min_size_for_state(self, state: _ShellState) -> QSize:
        if state.descriptor.custom_layout_resize_mode == "volume_scale":
            return QSize(24, 120)
        if state.descriptor.custom_layout_resize_mode == "visualizer_rect":
            baseline_width = max(1, int(state.baseline_size_payload.get("width", state.baseline_global_rect.width())))
            baseline_height = max(
                1,
                int(state.baseline_size_payload.get("height", state.baseline_global_rect.height())),
            )
            return QSize(
                max(1, int(round(baseline_width * 0.5))),
                max(1, int(round(baseline_height * 0.5))),
            )
        if state.descriptor.supports_layout_resize_edit:
            return QSize(
                max(1, int(round(state.baseline_global_rect.width() * 0.5))),
                max(1, int(round(state.baseline_global_rect.height() * 0.5))),
            )
        return QSize(
            max(1, state.baseline_global_rect.width()),
            max(1, state.baseline_global_rect.height()),
        )
