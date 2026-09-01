"""Single destination owner for retained Quick CUSTOM layout editing.

The owner is generation-scoped at ``DisplayManager``.  It assembles one global
presentation-neutral :class:`CustomLayoutSession` from the already-admitted
retained Quick presentations, binds each display's existing overlay, and owns
the exact Save/Cancel/reset persistence boundary.  It does not construct a
second presentation, service, visualizer, input router, or cadence owner.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPoint, QRect

from core.logging.logger import get_logger
from rendering.custom_layout_contract import (
    CustomLayoutEntry,
    canonicalize_screen_layout_bucket,
    choose_best_screen_for_global_rect,
    clamp_local_rect_to_bounds,
    get_screen_signature,
    get_screen_signature_aliases,
    load_custom_layout_map,
    normalize_local_rect,
    remove_screen_layout_entry,
    resolve_snap_local_rect_for_edit,
    set_screen_layout_entry,
    should_transfer_rect_to_screen,
    write_custom_layout_map,
)
from rendering.custom_layout_session import (
    CustomLayoutKey,
    CustomLayoutSession,
    CustomLayoutSessionItem,
    normalize_viewport_extent,
)
from rendering.quick.custom_layout_hydration import (
    geometry_variant_for_presentation,
    resolve_quick_custom_entry,
)
from rendering.quick.custom_layout_scene import QuickCustomLayoutSceneCoordinator
from rendering.quick.custom_layout_size import (
    CUSTOM_LAYOUT_MIN_RESIZE_SCALE,
    CUSTOM_LAYOUT_RESIZE_SCALE_PAYLOAD_KEY,
    capture_quick_size_payload,
    is_uniform_transform_resize_mode,
    quick_custom_minimum_size,
    quick_custom_payload_minimum_scale,
    scale_quick_size_payload,
)
from rendering.widget_descriptors import (
    WidgetRuntimeDescriptor,
    get_custom_persistence_monitor_settings_key_for_widget,
    get_custom_persistence_position_settings_key_for_widget,
    get_effective_monitor_value_for_widget,
    get_widget_runtime_descriptor,
    restore_widget_family_to_authored_layout,
    sync_custom_layout_restore_routes,
    widget_writes_custom_monitor_key,
    widget_writes_custom_position_key,
)
from widgets.spotify_visualizer.render_state import (
    CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
)


logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class _DisplayBinding:
    identity: str
    monitor_route: str
    unit: Any
    screen: Any
    geometry: QRect


@dataclass(frozen=True, slots=True)
class _ResizeOrigin:
    rect: QRect
    cursor: QPoint
    scale: float
    viewport_extent: tuple[float, float] | None


class QuickCustomLayoutOwner:
    """Own one global retained CUSTOM edit transaction for a Quick generation."""

    def __init__(
        self,
        *,
        settings_manager: Any,
        participants_provider: Callable[[], Sequence[Any]],
        visualizer_provider: Callable[[], tuple[Any | None, Any | None]],
        reload_request: Callable[[str], None],
    ) -> None:
        self._settings_manager = settings_manager
        self._participants_provider = participants_provider
        self._visualizer_provider = visualizer_provider
        self._reload_request = reload_request
        self._session: CustomLayoutSession | None = None
        self._coordinator: QuickCustomLayoutSceneCoordinator | None = None
        self._bindings: dict[str, _DisplayBinding] = {}
        self._descriptors: dict[CustomLayoutKey, WidgetRuntimeDescriptor] = {}
        self._resize_origins: dict[CustomLayoutKey, _ResizeOrigin] = {}
        self._active = False
        self._retired = False

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def is_retired(self) -> bool:
        return self._retired

    @property
    def session(self) -> CustomLayoutSession | None:
        return self._session

    def can_start(self) -> bool:
        if self._retired or self._settings_manager is None:
            return False
        return any(
            not getattr(unit, "is_retired", False)
            and bool(getattr(unit.presenter, "bound_widget_ids", ()))
            for unit in self._participants_provider()
        ) or self._visualizer_provider()[0] is not None

    def start(self) -> bool:
        if self._retired:
            return False
        if self._active:
            return True
        widgets = self._settings_manager.get_widgets_map()
        bindings = self._live_display_bindings()
        if not bindings:
            return False
        session = CustomLayoutSession()
        descriptors: dict[CustomLayoutKey, WidgetRuntimeDescriptor] = {}
        for binding in bindings.values():
            self._admit_ordinary_items(
                session,
                descriptors,
                binding,
                widgets,
            )
        self._admit_visualizer_item(session, descriptors, bindings, widgets)
        if not session.items():
            return False

        coordinator = QuickCustomLayoutSceneCoordinator(session)
        session.subscribe_changes(self._sync_visualizer_presentation_runtime)
        try:
            for binding in bindings.values():
                scene = binding.unit.runtime.scene_controller
                coordinator.register_scene(binding.identity, scene)
                scene.bind_custom_layout_session(
                    session,
                    display_identity=binding.identity,
                    display_origin=binding.geometry.topLeft(),
                    geometry_resolver=self.resolve_move,
                    resize_begin_handler=self.begin_resize,
                    resize_update_handler=self.update_resize,
                    resize_wheel_handler=self.resize_wheel,
                )
        except Exception:
            for binding in bindings.values():
                try:
                    binding.unit.runtime.scene_controller.clear_custom_layout_session()
                except Exception:
                    logger.debug("[CUSTOM_LAYOUT] Partial Quick bind cleanup failed", exc_info=True)
            coordinator.retire()
            session.unsubscribe_changes(self._sync_visualizer_presentation_runtime)
            raise

        self._bindings = bindings
        self._descriptors = descriptors
        self._session = session
        self._coordinator = coordinator
        self._active = True
        logger.info(
            "[CUSTOM_LAYOUT] Started one Quick session displays=%d items=%d",
            len(bindings),
            len(session.items()),
        )
        return True

    def cancel(self) -> bool:
        if not self._active or self._session is None:
            return False
        self._session.restore_baseline()
        self._finish()
        logger.info("[CUSTOM_LAYOUT] Cancelled Quick session")
        return True

    def save(self, *, request_reload: bool = True) -> bool:
        if not self._active or self._session is None:
            return False
        widgets = self._settings_manager.get_widgets_map()
        sync_custom_layout_restore_routes(widgets)
        custom_map = load_custom_layout_map(widgets)
        grouped: dict[str, list[CustomLayoutSessionItem]] = {}
        for item in self._session.items():
            grouped.setdefault(item.model_identity, []).append(item)

        for widget_id, items in grouped.items():
            section = widgets.get(widget_id, {})
            if not isinstance(section, dict):
                section = {}
                widgets[widget_id] = section
            section["enabled"] = any(
                item.current_enabled and not item.removed for item in items
            )
            survivors = [item for item in items if not item.removed]
            for removed in (item for item in items if item.removed):
                source = self._bindings.get(removed.source_key.display_identity)
                if source is None:
                    continue
                for alias in get_screen_signature_aliases(source.screen):
                    remove_screen_layout_entry(
                        custom_map,
                        alias,
                        widget_id,
                        removed.source_key.geometry_variant,
                    )
            source_had_duplicates = len(items) > 1
            for item in survivors:
                monitor = item.current_monitor_route
                if (
                    widget_id == "spotify_visualizer"
                    or item.current_display_identity != item.source_key.display_identity
                    or (
                        source_had_duplicates
                        and len(survivors) == 1
                        and self._is_all(item.source_monitor_route)
                    )
                ):
                    monitor = self._bindings[item.current_display_identity].monitor_route
                self._write_item(
                    widgets,
                    custom_map,
                    item,
                    self._descriptors[item.source_key],
                    monitor,
                )

        write_custom_layout_map(widgets, custom_map)
        self._settings_manager.set_widgets_map(widgets, emit_change=False)
        self._settings_manager.save()
        self._promote_visualizer_commit()
        self._finish()
        if request_reload:
            self._reload_request("save_continue")
        logger.info("[CUSTOM_LAYOUT] Saved one Quick session")
        return True

    def reset_to_authored(self) -> bool:
        if not self._active or self._session is None:
            return False
        widgets = self._settings_manager.get_widgets_map()
        changed = False
        for widget_id in {item.model_identity for item in self._session.items()}:
            changed = restore_widget_family_to_authored_layout(widgets, widget_id) or changed
        if not changed:
            return False
        self._settings_manager.set_widgets_map(widgets, emit_change=False)
        self._settings_manager.save()
        self._finish()
        self._reload_request("reset_authored")
        logger.info("[CUSTOM_LAYOUT] Restored authored Quick layout")
        return True

    def retire(self) -> bool:
        if self._retired:
            return False
        if self._active:
            self.cancel()
        self._retired = True
        self._participants_provider = lambda: ()
        self._visualizer_provider = lambda: (None, None)
        return True

    def resolve_move(
        self,
        item: CustomLayoutSessionItem,
        proposed: QRect,
        cursor: QPoint,
    ) -> QRect:
        binding = self._bindings[item.current_display_identity]
        candidate = choose_best_screen_for_global_rect(
            proposed,
            cursor_global=cursor,
            screens=[entry.screen for entry in self._bindings.values()],
        )
        target = binding
        if candidate is not None and candidate is not binding.screen:
            if should_transfer_rect_to_screen(
                proposed,
                current_screen=binding.screen,
                candidate_screen=candidate,
                cursor_global=cursor,
            ):
                target = next(
                    entry
                    for entry in self._bindings.values()
                    if entry.screen is candidate
                )
        local = QRect(
            proposed.x() - target.geometry.x(),
            proposed.y() - target.geometry.y(),
            proposed.width(),
            proposed.height(),
        )
        peers = self._peer_local_rects(item, target)
        resolved = resolve_snap_local_rect_for_edit(
            local,
            target.geometry.size(),
            peer_rects=peers,
            min_size=quick_custom_minimum_size(item),
        ).rect
        if target.identity != item.current_display_identity:
            item.set_current_display(
                target.identity,
                monitor_route=target.monitor_route,
            )
        return QRect(
            target.geometry.x() + resolved.x(),
            target.geometry.y() + resolved.y(),
            resolved.width(),
            resolved.height(),
        )

    def begin_resize(
        self,
        item: CustomLayoutSessionItem,
        handle: str,
        cursor: QPoint,
    ) -> bool:
        edge = str(handle or "")
        if edge in {"left", "right", "top", "bottom"}:
            if not item.viewport_resize_capable:
                return False
        elif not item.resize_capable:
            return False
        self._resize_origins[item.source_key] = _ResizeOrigin(
            rect=QRect(item.current_global_rect),
            cursor=QPoint(cursor),
            scale=float(item.resize_scale),
            viewport_extent=item.current_viewport_extent,
        )
        return True

    def update_resize(
        self,
        item: CustomLayoutSessionItem,
        handle: str,
        cursor: QPoint,
        finalize: bool,
    ) -> bool:
        origin = self._resize_origins.get(item.source_key)
        if origin is None:
            return False
        edge = str(handle or "")
        if edge in {"left", "right", "top", "bottom"}:
            changed = self._resize_viewport_edge(item, origin, edge, cursor)
        else:
            changed = self._resize_uniform_drag(item, origin, edge, cursor)
        if finalize:
            self._resize_origins.pop(item.source_key, None)
        return changed

    def resize_wheel(
        self,
        item: CustomLayoutSessionItem,
        angle_delta_y: int,
    ) -> bool:
        if not item.resize_capable:
            return False
        steps = int(angle_delta_y / 120) if angle_delta_y else 0
        if steps == 0:
            steps = 1 if angle_delta_y > 0 else -1
        return self._apply_uniform_scale(
            item,
            max(
                CUSTOM_LAYOUT_MIN_RESIZE_SCALE,
                float(item.resize_scale) + 0.05 * steps,
            ),
            QRect(item.current_global_rect),
        )

    def _live_display_bindings(self) -> dict[str, _DisplayBinding]:
        result: dict[str, _DisplayBinding] = {}
        for unit in self._participants_provider():
            if getattr(unit, "is_retired", False):
                continue
            screen = unit.runtime.window.screen()
            if screen is None:
                continue
            identity = get_screen_signature(screen)
            result[identity] = _DisplayBinding(
                identity=identity,
                monitor_route=str(int(unit.screen_index) + 1),
                unit=unit,
                screen=screen,
                geometry=QRect(screen.geometry()),
            )
        return result

    def _admit_ordinary_items(
        self,
        session: CustomLayoutSession,
        descriptors: dict[CustomLayoutKey, WidgetRuntimeDescriptor],
        binding: _DisplayBinding,
        widgets: Mapping[str, Any],
    ) -> None:
        for widget_id in binding.unit.presenter.bound_widget_ids:
            descriptor = get_widget_runtime_descriptor(widget_id)
            if descriptor is None or not descriptor.supports_layout_edit_mode:
                continue
            geometry = binding.unit.presenter.geometry_for(widget_id)
            presentation = binding.unit.presenter.presentation_for_widget_id(widget_id)
            if geometry is None or presentation is None:
                continue
            global_rect = QRect(
                binding.geometry.x() + int(round(geometry.x)),
                binding.geometry.y() + int(round(geometry.y)),
                max(1, int(round(geometry.width))),
                max(1, int(round(geometry.height))),
            )
            payload = capture_quick_size_payload(descriptor, presentation, global_rect)
            section = widgets.get(widget_id, {})
            enabled = bool(section.get("enabled", True)) if isinstance(section, Mapping) else True
            geometry_variant = geometry_variant_for_presentation(
                widget_id, presentation, widgets
            )
            key = CustomLayoutKey(
                widget_id,
                binding.identity,
                geometry_variant,
            )

            # CUSTOM resize scale is absolute against the authored/reference
            # presentation, not relative to whichever shrunken rectangle was
            # saved last time.  Persisting the scalar prevents 40% -> 16% ->
            # 6.4% compounding across Save/recreation cycles.
            baseline_resize_scale = 1.0
            committed_entry = resolve_quick_custom_entry(
                widgets,
                binding.screen,
                widget_id,
                geometry_variant=geometry_variant,
            )
            if committed_entry is not None:
                raw_scale = committed_entry.size_payload.get(
                    CUSTOM_LAYOUT_RESIZE_SCALE_PAYLOAD_KEY
                )
                try:
                    parsed_scale = float(raw_scale)
                except (TypeError, ValueError):
                    parsed_scale = 0.0
                if math.isfinite(parsed_scale) and parsed_scale > 0.0:
                    baseline_resize_scale = parsed_scale

            # For retained uniform-transform families, the QML preferred size
            # is the exact authored reference on every admission. Derive the
            # current absolute scale from committed geometry even when metadata
            # exists so a display/layout change cannot leave stale scalar truth.
            # This also migrates H9 geometry-only entries and Gmail cleanly.
            if is_uniform_transform_resize_mode(
                descriptor.custom_layout_resize_mode
            ):
                qml_item = getattr(presentation, "item", None)
                if qml_item is not None:
                    try:
                        preferred_width = float(
                            qml_item.property("preferredContentWidth") or 0.0
                        )
                        preferred_height = float(
                            qml_item.property("preferredContentHeight") or 0.0
                        )
                    except (TypeError, ValueError, RuntimeError):
                        preferred_width = 0.0
                        preferred_height = 0.0
                    if preferred_width > 0.0 and preferred_height > 0.0:
                        inferred_scale = min(
                            float(global_rect.width()) / preferred_width,
                            float(global_rect.height()) / preferred_height,
                        )
                        if math.isfinite(inferred_scale) and inferred_scale > 0.0:
                            baseline_resize_scale = inferred_scale

                            # H9 whole-card scaling letterboxes whenever a stale
                            # committed rectangle has a different aspect ratio
                            # from the authored preferred card. The card pixels are
                            # centred inside that dead outer area, while CUSTOM's
                            # frame historically outlined the dead rectangle. That
                            # is the source of the bizarre over-tall Reddit edit
                            # bars after older vertical-content geometry commits.
                            # Canonicalize only the edit/session envelope to the
                            # *actual visible retained card bounds*. Pixel output
                            # is unchanged; Save merely retires the invisible dead
                            # axis from persisted geometry, and Cancel keeps the
                            # same visible card centre/scale.
                            visible_width = max(
                                1, int(round(preferred_width * inferred_scale))
                            )
                            visible_height = max(
                                1, int(round(preferred_height * inferred_scale))
                            )
                            if (
                                visible_width != global_rect.width()
                                or visible_height != global_rect.height()
                            ):
                                original = QRect(global_rect)
                                global_rect = QRect(
                                    int(
                                        round(
                                            float(original.x())
                                            + (original.width() - visible_width) / 2.0
                                        )
                                    ),
                                    int(
                                        round(
                                            float(original.y())
                                            + (original.height() - visible_height) / 2.0
                                        )
                                    ),
                                    visible_width,
                                    visible_height,
                                )
                                logger.info(
                                    "[CUSTOM_LAYOUT] Canonicalized uniform edit "
                                    "envelope widget=%s assigned=%s visible=%s "
                                    "scale=%.4f",
                                    widget_id,
                                    original.getRect(),
                                    global_rect.getRect(),
                                    inferred_scale,
                                )

            item = CustomLayoutSessionItem(
                source_key=key,
                model_identity=widget_id,
                baseline_global_rect=global_rect,
                current_global_rect=global_rect,
                baseline_size_payload=payload,
                current_size_payload=payload,
                baseline_enabled=enabled,
                current_enabled=enabled,
                resize_capable=descriptor.supports_layout_resize_edit,
                baseline_resize_scale=baseline_resize_scale,
                resize_scale=baseline_resize_scale,
                source_monitor_route=get_effective_monitor_value_for_widget(
                    widget_id, widgets
                ),
            )
            session.add_item(item)
            descriptors[key] = descriptor

    def _admit_visualizer_item(
        self,
        session: CustomLayoutSession,
        descriptors: dict[CustomLayoutKey, WidgetRuntimeDescriptor],
        bindings: Mapping[str, _DisplayBinding],
        widgets: Mapping[str, Any],
    ) -> None:
        owner, unit = self._visualizer_provider()
        descriptor = get_widget_runtime_descriptor("spotify_visualizer")
        if owner is None or unit is None or descriptor is None:
            return
        binding = next(
            (entry for entry in bindings.values() if entry.unit is unit),
            None,
        )
        if binding is None:
            return
        render_item = unit.runtime.scene_controller.visualizer_item
        presentation = None if render_item is None else render_item.presentation
        if presentation is None:
            return
        x, y, width, height = presentation.outer_rect
        global_rect = QRect(
            binding.geometry.x() + int(round(x)),
            binding.geometry.y() + int(round(y)),
            max(1, int(round(width))),
            max(1, int(round(height))),
        )
        extent = normalize_viewport_extent(presentation.viewport_extent)
        payload: dict[str, Any] = {
            "width": global_rect.width(),
            "height": global_rect.height(),
        }
        if extent is not None:
            payload["viewport_extent"] = [extent[0], extent[1]]
        key = CustomLayoutKey("spotify_visualizer", binding.identity)
        item = CustomLayoutSessionItem(
            source_key=key,
            model_identity="spotify_visualizer",
            baseline_global_rect=global_rect,
            current_global_rect=global_rect,
            baseline_size_payload=payload,
            current_size_payload=payload,
            baseline_enabled=True,
            current_enabled=True,
            resize_capable=True,
            source_monitor_route=get_effective_monitor_value_for_widget(
                "spotify_visualizer", widgets
            ),
            viewport_resize_capable=True,
            baseline_viewport_extent=extent,
        )
        session.add_item(item)
        descriptors[key] = descriptor

    def _apply_uniform_scale(
        self,
        item: CustomLayoutSessionItem,
        requested_scale: float,
        anchor_rect: QRect,
    ) -> bool:
        descriptor = self._descriptors[item.source_key]
        binding = self._bindings[item.current_display_identity]
        baseline = item.baseline_global_rect
        admitted_scale = max(1.0e-6, float(item.baseline_resize_scale))
        reference_width = max(1.0, float(baseline.width()) / admitted_scale)
        reference_height = max(1.0, float(baseline.height()) / admitted_scale)
        max_scale = min(
            float(binding.geometry.width()) / reference_width,
            float(binding.geometry.height()) / reference_height,
        )
        minimum = quick_custom_minimum_size(item)
        minimum_scale = max(
            float(minimum.width()) / reference_width,
            float(minimum.height()) / reference_height,
        )
        legacy_payload_floor = (
            admitted_scale
            * quick_custom_payload_minimum_scale(
                descriptor, item.baseline_size_payload
            )
        )
        floor_scale = max(
            CUSTOM_LAYOUT_MIN_RESIZE_SCALE,
            minimum_scale,
            legacy_payload_floor,
        )
        scale = min(max_scale, max(floor_scale, float(requested_scale)))
        if abs(scale - item.resize_scale) < 1e-6:
            return False
        width = max(1, int(round(reference_width * scale)))
        height = max(1, int(round(reference_height * scale)))
        center_x = float(anchor_rect.x()) + float(anchor_rect.width()) / 2.0
        local = QRect(
            int(round(center_x - width / 2.0)) - binding.geometry.x(),
            anchor_rect.y() - binding.geometry.y(),
            width,
            height,
        )
        local = clamp_local_rect_to_bounds(
            local,
            binding.geometry.size(),
            min_size=minimum,
        )
        # Legacy payload-based families scale from their admitted payload by
        # the *delta* from the persisted absolute scale. Uniform-transform
        # families carry no authored size payload, but use the same arithmetic.
        payload_scale = scale / admitted_scale
        payload = scale_quick_size_payload(
            descriptor,
            item.baseline_size_payload,
            payload_scale,
        )
        item.set_geometry(
            QRect(
                binding.geometry.x() + local.x(),
                binding.geometry.y() + local.y(),
                local.width(),
                local.height(),
            ),
            size_payload=payload,
            resize_scale=scale,
        )
        return True

    def _resize_uniform_drag(
        self,
        item: CustomLayoutSessionItem,
        origin: _ResizeOrigin,
        handle: str,
        cursor: QPoint,
    ) -> bool:
        horizontal = -1.0 if str(handle).endswith("left") else 1.0
        vertical = -1.0 if str(handle).startswith("top_") else 1.0
        half_width = max(1.0, origin.rect.width() / 2.0)
        height = max(1.0, float(origin.rect.height()))
        base = max(1.0, math.hypot(half_width, height))
        target = math.hypot(
            max(1.0, half_width + (cursor.x() - origin.cursor.x()) * horizontal),
            max(1.0, height + (cursor.y() - origin.cursor.y()) * vertical),
        )
        return self._apply_uniform_scale(
            item,
            origin.scale * target / base,
            origin.rect,
        )

    def _resize_viewport_edge(
        self,
        item: CustomLayoutSessionItem,
        origin: _ResizeOrigin,
        edge: str,
        cursor: QPoint,
    ) -> bool:
        extent = origin.viewport_extent
        if extent is None:
            extent = (
                float(CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[0]),
                float(CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[1]),
            )
        pixels_per_world = max(1e-6, float(origin.rect.width()) / float(extent[0]))
        rect = QRect(origin.rect)
        dx = cursor.x() - origin.cursor.x()
        dy = cursor.y() - origin.cursor.y()
        minimum = quick_custom_minimum_size(item)
        if edge == "left":
            right = origin.rect.x() + origin.rect.width()
            rect.setX(min(cursor.x(), right - minimum.width()))
            rect.setWidth(right - rect.x())
        elif edge == "right":
            rect.setWidth(max(minimum.width(), origin.rect.width() + dx))
        elif edge == "top":
            bottom = origin.rect.y() + origin.rect.height()
            rect.setY(min(cursor.y(), bottom - minimum.height()))
            rect.setHeight(bottom - rect.y())
        else:
            rect.setHeight(max(minimum.height(), origin.rect.height() + dy))
        binding = self._bindings[item.current_display_identity]
        local = clamp_local_rect_to_bounds(
            QRect(
                rect.x() - binding.geometry.x(),
                rect.y() - binding.geometry.y(),
                rect.width(),
                rect.height(),
            ),
            binding.geometry.size(),
            min_size=minimum,
        )
        rect = QRect(
            binding.geometry.x() + local.x(),
            binding.geometry.y() + local.y(),
            local.width(),
            local.height(),
        )
        next_extent = (
            float(rect.width()) / pixels_per_world,
            float(rect.height()) / pixels_per_world,
        )
        payload = dict(item.current_size_payload)
        payload.update(
            width=rect.width(),
            height=rect.height(),
            viewport_extent=[next_extent[0], next_extent[1]],
        )
        item.set_geometry(
            rect,
            size_payload=payload,
            viewport_extent=next_extent,
        )
        return True

    def _peer_local_rects(
        self,
        item: CustomLayoutSessionItem,
        binding: _DisplayBinding,
    ) -> list[QRect]:
        if self._session is None:
            return []
        return [
            QRect(
                peer.current_global_rect.x() - binding.geometry.x(),
                peer.current_global_rect.y() - binding.geometry.y(),
                peer.current_global_rect.width(),
                peer.current_global_rect.height(),
            )
            for peer in self._session.active_items()
            if peer is not item
            and peer.current_display_identity == binding.identity
            and peer.current_enabled
        ]

    def _write_item(
        self,
        widgets: dict[str, Any],
        custom_map: dict[str, Any],
        item: CustomLayoutSessionItem,
        descriptor: WidgetRuntimeDescriptor,
        monitor_route: str,
    ) -> None:
        binding = self._bindings[item.current_display_identity]
        signature = canonicalize_screen_layout_bucket(custom_map, binding.screen)
        if not signature:
            signature = binding.identity
        if self._is_all(monitor_route):
            for alias in get_screen_signature_aliases(binding.screen):
                remove_screen_layout_entry(
                    custom_map,
                    alias,
                    item.model_identity,
                    item.source_key.geometry_variant,
                )
        else:
            displays = custom_map.get("displays", {})
            if isinstance(displays, dict):
                for other in tuple(displays):
                    if other != signature:
                        remove_screen_layout_entry(
                            custom_map,
                            str(other),
                            item.model_identity,
                            item.source_key.geometry_variant,
                        )
        local = clamp_local_rect_to_bounds(
            QRect(
                item.current_global_rect.x() - binding.geometry.x(),
                item.current_global_rect.y() - binding.geometry.y(),
                item.current_global_rect.width(),
                item.current_global_rect.height(),
            ),
            binding.geometry.size(),
            min_size=quick_custom_minimum_size(item),
        )
        payload = dict(item.current_size_payload)
        if descriptor.custom_layout_resize_mode != "visualizer_rect":
            payload[CUSTOM_LAYOUT_RESIZE_SCALE_PAYLOAD_KEY] = float(
                item.resize_scale
            )
        if descriptor.custom_layout_resize_mode == "clock_font":
            payload.pop("display_mode", None)
        if descriptor.custom_layout_resize_mode == "visualizer_rect":
            extent = item.current_viewport_extent
            canonical = CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
            if extent is not None and (
                abs(extent[0] - canonical[0]) >= 0.5
                or abs(extent[1] - canonical[1]) >= 0.5
            ):
                payload["viewport_extent"] = [extent[0], extent[1]]
            else:
                payload.pop("viewport_extent", None)
        set_screen_layout_entry(
            custom_map,
            signature,
            item.model_identity,
            CustomLayoutEntry(
                widget_id=item.model_identity,
                geometry_variant=item.source_key.geometry_variant,
                rect=normalize_local_rect(local, binding.geometry.size()),
                size_payload=payload,
                resize_mode=descriptor.custom_layout_resize_mode,
            ),
        )
        if widget_writes_custom_position_key(item.model_identity):
            key = get_custom_persistence_position_settings_key_for_widget(
                item.model_identity
            )
            section = widgets.get(key, {})
            if not isinstance(section, dict):
                section = {}
                widgets[key] = section
            section["position"] = "Custom"
        if widget_writes_custom_monitor_key(item.model_identity):
            key = get_custom_persistence_monitor_settings_key_for_widget(
                item.model_identity
            )
            section = widgets.get(key, {})
            if not isinstance(section, dict):
                section = {}
                widgets[key] = section
            section["monitor"] = str(monitor_route or "ALL")

    def _promote_visualizer_commit(self) -> None:
        owner, unit = self._visualizer_provider()
        if owner is None or unit is None:
            return
        runtime = getattr(owner, "presentation_runtime", unit.runtime)
        render_item = runtime.scene_controller.visualizer_item
        presentation = None if render_item is None else render_item.presentation
        if presentation is not None:
            owner.controller.commit_presentation_metrics(presentation)

    def _finish(self) -> None:
        # Closing the retained edit overlay can leave the release/click that
        # activated Save/Cancel in the same native input burst as the underlying
        # screensaver. Arm the existing replacement guard *before* removing the
        # overlay so no retained family action can inherit that gesture. This is
        # event-bound only; it adds no pointer-motion/render cadence.
        from rendering.runtime_input import suppress_runtime_pointer_input

        suppress_runtime_pointer_input(
            700,
            reason="custom_layout_overlay_close",
        )
        session = self._session
        if session is not None:
            session.unsubscribe_changes(self._sync_visualizer_presentation_runtime)
        for binding in tuple(self._bindings.values()):
            binding.unit.runtime.scene_controller.clear_custom_layout_session()
        coordinator = self._coordinator
        self._coordinator = None
        if coordinator is not None:
            coordinator.retire()
        self._session = None
        self._bindings = {}
        self._descriptors = {}
        self._resize_origins = {}
        self._active = False

    def _sync_visualizer_presentation_runtime(
        self,
        item: CustomLayoutSessionItem,
    ) -> None:
        if item.model_identity != "spotify_visualizer":
            return
        binding = self._bindings.get(item.current_display_identity)
        if binding is None:
            return
        owner, _unit = self._visualizer_provider()
        if owner is not None:
            owner.set_presentation_runtime(binding.unit.runtime)

    @staticmethod
    def _is_all(value: object) -> bool:
        return str(value or "ALL").strip().upper() == "ALL"


__all__ = [
    "QuickCustomLayoutOwner",
]
