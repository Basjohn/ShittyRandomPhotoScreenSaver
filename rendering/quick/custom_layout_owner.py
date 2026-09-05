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
from rendering.quick.widgets.host import OverlayWidgetGeometry
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
    visualizer_uniform_scale: float | None


class QuickCustomLayoutOwner:
    """Own one global retained CUSTOM edit transaction for a Quick generation."""

    def __init__(
        self,
        *,
        settings_manager: Any,
        participants_provider: Callable[[], Sequence[Any]],
        visualizer_provider: Callable[[], tuple[Any | None, Any | None]],
        reload_request: Callable[[str], None],
        visualizer_unit_transfer: Callable[[Any], bool] | None = None,
    ) -> None:
        self._settings_manager = settings_manager
        self._participants_provider = participants_provider
        self._visualizer_provider = visualizer_provider
        self._reload_request = reload_request
        self._visualizer_unit_transfer = visualizer_unit_transfer
        self._session: CustomLayoutSession | None = None
        self._coordinator: QuickCustomLayoutSceneCoordinator | None = None
        self._bindings: dict[str, _DisplayBinding] = {}
        self._descriptors: dict[CustomLayoutKey, WidgetRuntimeDescriptor] = {}
        self._resize_origins: dict[CustomLayoutKey, _ResizeOrigin] = {}
        # One Edit session owns one stable pixels-per-world authority for the
        # Visualizer viewport. Retained presentation publications may refresh
        # style/content while editing, but may not silently replace this geometry
        # scalar between side/corner gestures. Wheel scaling and a successful
        # fit-to-target display transfer are the only operations allowed to move
        # it, and both update it transactionally.
        self._visualizer_pixels_per_world: dict[CustomLayoutKey, float] = {}
        # One visualizer may cross one display seam per pointer move gesture.
        # Without this latch a cursor hovering around the seam can ping-pong the
        # retained GL admission between scenes while QML is still processing the
        # same drag, producing duplicate/dead target admissions. Release clears it.
        self._visualizer_move_transfer_latch: set[CustomLayoutKey] = set()
        self._deferred_topology_reconciliation_reason: str | None = None
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
        self._visualizer_pixels_per_world.clear()
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

        coordinator = QuickCustomLayoutSceneCoordinator(
            session,
            visualizer_transfer_handler=self._transfer_visualizer_display_transaction,
        )
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
                    move_finished_handler=self.clear_move_guides,
                    display_transfer_capability=(
                        lambda item, direction, available=bindings:
                        self._adjacent_display_binding(item, direction, available) is not None
                    ),
                    display_transfer_handler=self.transfer_display,
                )
        except Exception:
            for binding in bindings.values():
                try:
                    binding.unit.runtime.scene_controller.clear_custom_layout_session()
                except Exception:
                    logger.debug("[CUSTOM_LAYOUT] Partial Quick bind cleanup failed", exc_info=True)
            coordinator.retire()
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

    def save(self, *, defer_topology_reconciliation: bool = False) -> bool:
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
        topology_reason = self._live_commit_topology_reason()
        # Interactive Edit Save may now live-commit a cross-display Visualizer
        # move. The drag already transferred the retained scene AND the
        # runtime/pacer/manager-unit/retirement to the target as one atomic
        # transaction (`_transfer_visualizer_display_transaction`), so a coherent
        # transfer leaves the generation already reconciled and needs no rebuild.
        # This is deliberately limited: only the interactive path (never a
        # layout-slot save, which defers), only when the sole topology change is a
        # `display_transfer`, and only when the transfer graph is fully
        # target-owned. Any other change (family presence, monitor route,
        # incoherent transfer) or a layout-slot save still reconciles.
        live_committing = topology_reason is None
        if (
            not live_committing
            and topology_reason == "display_transfer"
            and not defer_topology_reconciliation
            and self._cross_display_transfer_is_coherent()
        ):
            live_committing = True
            logger.info(
                "[CUSTOM_LAYOUT] Save live-committed cross-display Visualizer "
                "transfer without generation reconciliation"
            )
        if live_committing:
            self._promote_live_geometry_commit()
        else:
            logger.info(
                "[CUSTOM_LAYOUT] Save retains generation reconciliation reason=%s",
                topology_reason,
            )
        self._finish()
        # Geometry-only / coherent live commits remain in this retained
        # generation. A layout-slot transaction can explicitly defer topology
        # replacement until its slot attempt completes; no caller gets an ignored
        # compatibility flag.
        if not live_committing:
            if defer_topology_reconciliation:
                self._deferred_topology_reconciliation_reason = topology_reason
                logger.info(
                    "[CUSTOM_LAYOUT] Deferred topology reconciliation reason=%s",
                    topology_reason,
                )
            else:
                self._reload_request("save_continue")
        logger.info("[CUSTOM_LAYOUT] Saved one Quick session")
        return True

    def take_deferred_topology_reconciliation(self) -> str | None:
        """Consume one layout-slot topology replacement reason after persistence."""

        reason = self._deferred_topology_reconciliation_reason
        self._deferred_topology_reconciliation_reason = None
        return reason

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
        target = binding
        transfer_latched = (
            item.model_identity == "spotify_visualizer"
            and item.source_key in self._visualizer_move_transfer_latch
        )
        if not transfer_latched:
            candidate = choose_best_screen_for_global_rect(
                proposed,
                cursor_global=cursor,
                screens=[entry.screen for entry in self._bindings.values()],
            )
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
        resolution = resolve_snap_local_rect_for_edit(
            local,
            target.geometry.size(),
            peer_rects=peers,
            min_size=quick_custom_minimum_size(item),
        )
        self._publish_move_guides(target.identity, resolution)
        resolved = resolution.rect
        if target.identity != item.current_display_identity:
            if item.model_identity == "spotify_visualizer":
                # Latch before the session notification can transfer the retained
                # scene. A failed transfer is likewise not hammered hundreds of
                # times in the same native drag; releasing starts a clean attempt.
                self._visualizer_move_transfer_latch.add(item.source_key)
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

    def clear_move_guides(self) -> None:
        """Clear transient alignment guides and end the current move gesture."""

        self._visualizer_move_transfer_latch.clear()
        for binding in tuple(self._bindings.values()):
            try:
                binding.unit.runtime.scene_controller.set_custom_layout_guides()
            except (RuntimeError, AttributeError):
                logger.debug(
                    "[CUSTOM_LAYOUT] Failed clearing transient guides display=%s",
                    binding.identity,
                    exc_info=True,
                )

    def _adjacent_display_binding(
        self,
        item: CustomLayoutSessionItem,
        direction: str,
        bindings: Mapping[str, _DisplayBinding] | None = None,
    ) -> _DisplayBinding | None:
        """Return the nearest horizontal display for a discrete Visualizer hop."""

        if item.model_identity != "spotify_visualizer":
            return None
        direction = str(direction or "").strip().lower()
        if direction not in {"left", "right"}:
            return None
        available = self._bindings if bindings is None else bindings
        source = available.get(item.current_display_identity)
        if source is None:
            return None
        source_center_x = source.geometry.x() + source.geometry.width() / 2.0
        source_center_y = source.geometry.y() + source.geometry.height() / 2.0
        candidates: list[tuple[float, float, _DisplayBinding]] = []
        for candidate in available.values():
            if candidate.identity == source.identity:
                continue
            center_x = candidate.geometry.x() + candidate.geometry.width() / 2.0
            delta_x = center_x - source_center_x
            if direction == "left" and delta_x >= 0.0:
                continue
            if direction == "right" and delta_x <= 0.0:
                continue
            center_y = candidate.geometry.y() + candidate.geometry.height() / 2.0
            candidates.append((abs(delta_x), abs(center_y - source_center_y), candidate))
        if not candidates:
            return None
        candidates.sort(key=lambda entry: (entry[0], entry[1], entry[2].identity))
        return candidates[0][2]

    def transfer_display(
        self,
        item: CustomLayoutSessionItem,
        direction: str,
    ) -> bool:
        """Project one Visualizer working rect onto an adjacent retained display.

        This is the button-driven companion to pointer transfer. It preserves
        shape/size when the target can contain them, keeps approximately the same
        relative screen position, and lets the existing session notification own
        the actual retained-scene/GL admission transfer. No fade or new cadence is
        introduced here.
        """

        target = self._adjacent_display_binding(item, direction)
        source = self._bindings.get(item.current_display_identity)
        if target is None or source is None:
            return False
        rect = QRect(item.current_global_rect)
        source_width = max(1.0, float(source.geometry.width()))
        source_height = max(1.0, float(source.geometry.height()))
        # QRect.center() is integer-valued and biases even-sized rectangles by
        # one pixel toward top/left.  A discrete hop then subtracts width/2 and
        # manufactures a deterministic 1px drift on every round-trip.  Project
        # the true geometric centre instead; pointer transfer has always used
        # continuous geometry and does not share this seam.
        rel_center_x = (
            float(rect.x()) + float(rect.width()) * 0.5 - float(source.geometry.x())
        ) / source_width
        rel_center_y = (
            float(rect.y()) + float(rect.height()) * 0.5 - float(source.geometry.y())
        ) / source_height

        scale = min(
            1.0,
            float(target.geometry.width()) / max(1.0, float(rect.width())),
            float(target.geometry.height()) / max(1.0, float(rect.height())),
        )
        width = max(1, int(round(float(rect.width()) * scale)))
        height = max(1, int(round(float(rect.height()) * scale)))
        target_center_x = float(target.geometry.x()) + rel_center_x * float(target.geometry.width())
        target_center_y = float(target.geometry.y()) + rel_center_y * float(target.geometry.height())
        local = QRect(
            int(round(target_center_x - width / 2.0)) - target.geometry.x(),
            int(round(target_center_y - height / 2.0)) - target.geometry.y(),
            width,
            height,
        )
        local = clamp_local_rect_to_bounds(
            local,
            target.geometry.size(),
            min_size=quick_custom_minimum_size(item),
        )
        projected = QRect(
            target.geometry.x() + local.x(),
            target.geometry.y() + local.y(),
            local.width(),
            local.height(),
        )
        self._visualizer_move_transfer_latch.clear()
        item.set_current_display(target.identity, monitor_route=target.monitor_route)
        item.set_geometry(projected)
        logger.info(
            "[CUSTOM_LAYOUT] Visualizer display hop direction=%s source=%s target=%s rect=%s",
            direction,
            source.identity,
            target.identity,
            projected.getRect(),
        )
        return True

    def _publish_move_guides(self, display_identity: str, resolution: Any) -> None:
        """Publish only peer-edge/centering assists for the active move sample."""

        allowed_kinds = {"peer", "peer_center", "display_center"}

        def _collect(primary: object, assists: object) -> tuple[tuple[int, str], ...]:
            result: list[tuple[int, str]] = []
            seen: set[tuple[int, str]] = set()
            for guide in tuple(primary or ()) + tuple(assists or ()):
                kind = str(getattr(guide, "kind", "") or "")
                if kind not in allowed_kinds:
                    continue
                entry = (int(getattr(guide, "position", 0)), kind)
                if entry in seen:
                    continue
                seen.add(entry)
                result.append(entry)
            return tuple(result)

        vertical = _collect(
            getattr(resolution, "vertical_guides", ()),
            getattr(resolution, "vertical_assists", ()),
        )
        horizontal = _collect(
            getattr(resolution, "horizontal_guides", ()),
            getattr(resolution, "horizontal_assists", ()),
        )
        target_identity = str(display_identity or "")
        for identity, binding in tuple(self._bindings.items()):
            scene = binding.unit.runtime.scene_controller
            if identity == target_identity:
                scene.set_custom_layout_guides(
                    vertical=vertical,
                    horizontal=horizontal,
                )
            else:
                scene.set_custom_layout_guides()

    def begin_resize(
        self,
        item: CustomLayoutSessionItem,
        handle: str,
        cursor: QPoint,
    ) -> bool:
        handle_id = str(handle or "")
        viewport_handles = {
            "left", "right", "top", "bottom",
            "top_left", "top_right", "bottom_left", "bottom_right",
        }
        is_viewport_handle = (
            item.viewport_resize_capable and handle_id in viewport_handles
        )
        if handle_id in {"left", "right", "top", "bottom"}:
            if not item.viewport_resize_capable:
                return False
        elif not item.resize_capable:
            return False

        uniform_scale = None
        if is_viewport_handle:
            uniform_scale = self._visualizer_pixels_per_world.get(item.source_key)
            if (
                uniform_scale is None
                or not math.isfinite(float(uniform_scale))
                or float(uniform_scale) <= 0.0
            ):
                raise RuntimeError(
                    "CUSTOM visualizer resize has no stable pixels-per-world authority"
                )
            uniform_scale = float(uniform_scale)
        self._resize_origins[item.source_key] = _ResizeOrigin(
            rect=QRect(item.current_global_rect),
            cursor=QPoint(cursor),
            scale=float(item.resize_scale),
            viewport_extent=item.current_viewport_extent,
            visualizer_uniform_scale=uniform_scale,
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
        handle_id = str(handle or "")
        if handle_id in {"left", "right", "top", "bottom"}:
            changed = self._resize_viewport_edge(item, origin, handle_id, cursor)
        elif (
            item.viewport_resize_capable
            and handle_id in {
                "top_left", "top_right", "bottom_left", "bottom_right"
            }
        ):
            changed = self._resize_viewport_corner(item, origin, handle_id, cursor)
        else:
            changed = self._resize_uniform_drag(item, origin, handle_id, cursor)
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
        self._visualizer_pixels_per_world[key] = (
            self._pixels_per_world_from_geometry(global_rect, extent)
        )

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
        viewport_extent = item.current_viewport_extent
        visualizer_world = item.viewport_resize_capable and viewport_extent is not None
        visualizer_pixels_per_world = None
        if visualizer_world:
            visualizer_pixels_per_world = self._visualizer_pixels_per_world.get(
                item.source_key
            )
            if (
                visualizer_pixels_per_world is None
                or not math.isfinite(float(visualizer_pixels_per_world))
                or float(visualizer_pixels_per_world) <= 0.0
            ):
                raise RuntimeError(
                    "CUSTOM visualizer wheel has no stable pixels-per-world authority"
                )
            visualizer_pixels_per_world = float(visualizer_pixels_per_world)
            current_width = max(
                1.0, float(viewport_extent[0]) * visualizer_pixels_per_world
            )
            current_height = max(
                1.0, float(viewport_extent[1]) * visualizer_pixels_per_world
            )
            current_resize_scale = max(1.0e-6, float(item.resize_scale))
            max_scale = current_resize_scale * min(
                float(binding.geometry.width()) / current_width,
                float(binding.geometry.height()) / current_height,
            )
            minimum = quick_custom_minimum_size(item)
            floor_scale = max(
                floor_scale,
                current_resize_scale * max(
                    float(minimum.width()) / current_width,
                    float(minimum.height()) / current_height,
                ),
            )
        scale = min(max_scale, max(floor_scale, float(requested_scale)))
        if abs(scale - item.resize_scale) < 1e-6:
            return False
        relative_to_current = scale / max(1.0e-6, float(item.resize_scale))
        if visualizer_world:
            assert viewport_extent is not None
            assert visualizer_pixels_per_world is not None
            next_pixels_per_world = visualizer_pixels_per_world * relative_to_current
            width = max(
                1, int(round(float(viewport_extent[0]) * next_pixels_per_world))
            )
            height = max(
                1, int(round(float(viewport_extent[1]) * next_pixels_per_world))
            )
        else:
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
        if visualizer_world:
            payload.update(
                width=local.width(),
                height=local.height(),
                viewport_extent=[viewport_extent[0], viewport_extent[1]],
            )
        geometry = QRect(
            binding.geometry.x() + local.x(),
            binding.geometry.y() + local.y(),
            local.width(),
            local.height(),
        )
        if visualizer_world:
            item.set_geometry(
                geometry,
                size_payload=payload,
                resize_scale=scale,
                viewport_extent=viewport_extent,
            )
            self._visualizer_pixels_per_world[item.source_key] = (
                self._pixels_per_world_from_geometry(geometry, viewport_extent)
            )
        else:
            item.set_geometry(
                geometry,
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

    @staticmethod
    def _pixels_per_world_from_geometry(
        rect: QRect,
        viewport_extent: tuple[float, float] | None,
    ) -> float:
        if viewport_extent is None:
            raise RuntimeError("CUSTOM visualizer geometry has no viewport extent")
        extent_width = float(viewport_extent[0])
        extent_height = float(viewport_extent[1])
        width = float(rect.width())
        height = float(rect.height())
        if min(extent_width, extent_height, width, height) <= 0.0:
            raise RuntimeError("CUSTOM visualizer geometry must be positive")
        horizontal = (
            max(0.0, (width - 0.5) / extent_width),
            (width + 0.5) / extent_width,
        )
        vertical = (
            max(0.0, (height - 0.5) / extent_height),
            (height + 0.5) / extent_height,
        )
        lower = max(horizontal[0], vertical[0])
        upper = min(horizontal[1], vertical[1])
        if lower > upper:
            raise RuntimeError(
                "CUSTOM visualizer geometry does not encode one pixels-per-world scale"
            )
        return max(1.0e-6, (lower + upper) * 0.5)

    @staticmethod
    def _viewport_resize_rect(
        origin: _ResizeOrigin,
        binding: _DisplayBinding,
        minimum: Any,
        cursor: QPoint,
        *,
        horizontal_edge: str | None = None,
        vertical_edge: str | None = None,
    ) -> QRect:
        """Resize selected viewport edges while anchoring the opposite edges.

        The cursor delta is measured from gesture start so grabbing anywhere in
        the visible handle never produces a jump. Bounds are applied to the edge
        being moved rather than by a later generic clamp, which preserves the
        opposite-corner anchor for the new two-axis Visualizer corner gesture.
        """

        rect = QRect(origin.rect)
        dx = int(cursor.x() - origin.cursor.x())
        dy = int(cursor.y() - origin.cursor.y())
        bounds = binding.geometry
        min_width = max(1, int(minimum.width()))
        min_height = max(1, int(minimum.height()))

        if horizontal_edge == "left":
            fixed_right = origin.rect.x() + origin.rect.width()
            left = max(
                bounds.x(),
                min(origin.rect.x() + dx, fixed_right - min_width),
            )
            rect.setX(left)
            rect.setWidth(fixed_right - left)
        elif horizontal_edge == "right":
            fixed_left = origin.rect.x()
            right = min(
                bounds.x() + bounds.width(),
                max(fixed_left + min_width, fixed_left + origin.rect.width() + dx),
            )
            rect.setX(fixed_left)
            rect.setWidth(right - fixed_left)

        if vertical_edge == "top":
            fixed_bottom = origin.rect.y() + origin.rect.height()
            top = max(
                bounds.y(),
                min(origin.rect.y() + dy, fixed_bottom - min_height),
            )
            rect.setY(top)
            rect.setHeight(fixed_bottom - top)
        elif vertical_edge == "bottom":
            fixed_top = origin.rect.y()
            bottom = min(
                bounds.y() + bounds.height(),
                max(fixed_top + min_height, fixed_top + origin.rect.height() + dy),
            )
            rect.setY(fixed_top)
            rect.setHeight(bottom - fixed_top)

        return rect

    def _commit_viewport_resize_geometry(
        self,
        item: CustomLayoutSessionItem,
        origin: _ResizeOrigin,
        rect: QRect,
        *,
        change_width: bool,
        change_height: bool,
    ) -> bool:
        if origin.visualizer_uniform_scale is None:
            raise RuntimeError("CUSTOM visualizer viewport resize has no retained scale")
        pixels_per_world = max(1.0e-6, float(origin.visualizer_uniform_scale))
        extent = item.current_viewport_extent
        if extent is None:
            extent = (
                float(CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[0]),
                float(CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[1]),
            )
        # Side handles are semantically one-axis operations. Preserve the untouched
        # logical extent exactly instead of letting integer QRect rounding nudge it
        # by a fraction on every orthogonal gesture. Corners opt into both axes.
        next_extent = (
            float(rect.width()) / pixels_per_world
            if change_width else float(extent[0]),
            float(rect.height()) / pixels_per_world
            if change_height else float(extent[1]),
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
        # The gesture consumed the cached scalar; keep it exact for the next
        # side/corner gesture rather than reading a later presentation refresh.
        self._visualizer_pixels_per_world[item.source_key] = pixels_per_world
        return True

    def _resize_viewport_edge(
        self,
        item: CustomLayoutSessionItem,
        origin: _ResizeOrigin,
        edge: str,
        cursor: QPoint,
    ) -> bool:
        binding = self._bindings[item.current_display_identity]
        minimum = quick_custom_minimum_size(item)
        rect = self._viewport_resize_rect(
            origin,
            binding,
            minimum,
            cursor,
            horizontal_edge=edge if edge in {"left", "right"} else None,
            vertical_edge=edge if edge in {"top", "bottom"} else None,
        )
        return self._commit_viewport_resize_geometry(
            item,
            origin,
            rect,
            change_width=edge in {"left", "right"},
            change_height=edge in {"top", "bottom"},
        )

    def _resize_viewport_corner(
        self,
        item: CustomLayoutSessionItem,
        origin: _ResizeOrigin,
        corner: str,
        cursor: QPoint,
    ) -> bool:
        binding = self._bindings[item.current_display_identity]
        minimum = quick_custom_minimum_size(item)
        horizontal_edge = "left" if str(corner).endswith("left") else "right"
        vertical_edge = "top" if str(corner).startswith("top_") else "bottom"
        rect = self._viewport_resize_rect(
            origin,
            binding,
            minimum,
            cursor,
            horizontal_edge=horizontal_edge,
            vertical_edge=vertical_edge,
        )
        return self._commit_viewport_resize_geometry(
            item,
            origin,
            rect,
            change_width=True,
            change_height=True,
        )

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

    def _live_commit_topology_reason(self) -> str | None:
        """Return the explicit reason a Save must retain replacement semantics."""

        session = self._session
        if session is None:
            raise RuntimeError("CUSTOM live-commit admission requires a session")
        for item in session.items():
            if item.removed or not item.current_enabled or not item.baseline_enabled:
                return "family_presence_changed"
            if item.current_display_identity != item.source_key.display_identity:
                return "display_transfer"
            if item.current_monitor_route != item.source_monitor_route:
                return "monitor_route_changed"
        return None

    def _cross_display_transfer_is_coherent(self) -> bool:
        """Return whether an already-live cross-display Visualizer transfer left a
        fully target-owned graph, so an interactive Save can promote in place
        instead of reinitialising the generation.

        Fail-safe: any cross-display item that is not the Visualizer, or a
        Visualizer whose current owner/unit is not the transfer target, forces the
        normal generation reconciliation. This never promotes a partially moved
        graph (the exact split that produced the historic retained-scene-admission
        warning storm and shutdown barrier timeout).
        """

        session = self._session
        if session is None:
            return False
        owner, unit = self._visualizer_provider()
        for item in session.items():
            if item.current_display_identity == item.source_key.display_identity:
                continue
            if item.model_identity != "spotify_visualizer":
                return False
            if owner is None or unit is None:
                return False
            target_binding = self._bindings.get(item.current_display_identity)
            if target_binding is None or target_binding.unit is not unit:
                return False
        return True

    def _promote_live_geometry_commit(self) -> None:
        """Promote all already-retained geometry before CUSTOM clears it."""

        session = self._session
        if session is None:
            raise RuntimeError("CUSTOM live geometry promotion requires a session")
        owner, visualizer_unit = self._visualizer_provider()
        for item in session.items():
            binding = self._bindings.get(item.current_display_identity)
            if binding is None:
                raise RuntimeError(
                    f"CUSTOM live geometry has no display binding: {item.current_display_identity!r}"
                )
            rect = item.current_global_rect
            local = OverlayWidgetGeometry(
                float(rect.x() - binding.geometry.x()),
                float(rect.y() - binding.geometry.y()),
                float(rect.width()),
                float(rect.height()),
            )
            if item.model_identity == "spotify_visualizer":
                if owner is None or visualizer_unit is None:
                    raise RuntimeError("CUSTOM live geometry has no visualizer owner")
                extent = item.current_viewport_extent
                if extent is None:
                    raise RuntimeError("CUSTOM live visualizer geometry has no viewport extent")
                owner.commit_live_custom_layout(
                    local_rect=(local.x, local.y, local.width, local.height),
                    viewport_extent=extent,
                )
                continue
            binding.unit.presenter.commit_live_custom_layout_item(
                item.model_identity,
                local,
                item.current_size_payload,
            )

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
        self._visualizer_pixels_per_world.clear()
        self._visualizer_move_transfer_latch.clear()
        self._active = False

    def _transfer_visualizer_display_transaction(
        self,
        source_scene: Any,
        target_scene: Any,
    ) -> None:
        """Move retained pixels and display-retirement authority as one transaction.

        ``CustomLayoutSession`` has synchronous listeners.  Splitting the retained
        scene move and the manager/unit lifecycle move across two listeners allowed
        the first listener to succeed and the second to fail, leaving pixels on one
        display while the old unit still owned teardown.  Keep both sides inside one
        coordinator callback so a lifecycle failure moves the retained scene back
        before the session item itself is restored.
        """

        source_binding = next(
            (
                binding
                for binding in self._bindings.values()
                if binding.unit.runtime.scene_controller is source_scene
            ),
            None,
        )
        target_binding = next(
            (
                binding
                for binding in self._bindings.values()
                if binding.unit.runtime.scene_controller is target_scene
            ),
            None,
        )
        if source_binding is None or target_binding is None:
            raise RuntimeError(
                "CUSTOM visualizer transfer has no exact display binding"
            )

        owner, current_unit = self._visualizer_provider()
        if owner is None or current_unit is None:
            raise RuntimeError("CUSTOM visualizer transfer has no admitted owner")
        if current_unit is not source_binding.unit:
            raise RuntimeError(
                "CUSTOM visualizer lifecycle owner disagrees with retained scene source"
            )
        if getattr(source_binding.unit, "visualizer_owner", None) is not owner:
            raise RuntimeError(
                "CUSTOM visualizer source unit lost lifecycle retirement ownership"
            )
        transfer_unit = self._visualizer_unit_transfer
        if transfer_unit is None:
            raise RuntimeError(
                "CUSTOM visualizer display transfer has no manager ownership seam"
            )

        target_owner = getattr(target_binding.unit, "visualizer_owner", None)
        if target_owner is not None:
            if target_owner is owner:
                raise RuntimeError(
                    "CUSTOM visualizer target already owns lifecycle authority"
                )
            raise RuntimeError(
                "CUSTOM visualizer target owns another visualizer lifecycle"
            )

        stale_target_identity = getattr(
            target_scene, "visualizer_render_identity", None
        )
        if stale_target_identity is not None:
            # Product-level manager authority proves this target unit owns no
            # Visualizer. Its retained identity is therefore an orphaned shell,
            # not a second legitimate runtime. Retire only the scene-local
            # admission before moving the one live source; do not recreate or
            # tear down the logical owner.
            discard_stale = getattr(
                target_scene, "discard_unowned_visualizer_admission", None
            )
            if not callable(discard_stale):
                raise RuntimeError(
                    "CUSTOM visualizer target cannot retire an orphaned admission"
                )
            discarded = discard_stale()
            if discarded is None:
                raise RuntimeError(
                    "CUSTOM visualizer stale target admission could not be discarded"
                )
            logger.warning(
                "[CUSTOM_LAYOUT] Discarded orphaned Visualizer target admission "
                "target=%s identity=%s",
                target_binding.identity,
                discarded,
            )

        source_scene.transfer_visualizer_to(target_scene)
        try:
            if not transfer_unit(target_binding.unit):
                raise RuntimeError(
                    "CUSTOM visualizer display ownership transfer rejected"
                )
            # In a real active Edit session the item geometry has already been
            # projected onto the target before this synchronous notification.
            # Refresh the one pixels-per-world authority from that final QRect so
            # a target-fit hop is the only non-wheel operation allowed to change
            # scale. Standalone unit tests may exercise this transaction without
            # an active session; they intentionally skip this session-only cache.
            if self._active:
                session = self._session
                if session is None:
                    raise RuntimeError("CUSTOM visualizer transfer lost its edit session")
                visualizer_item = next(
                    (
                        item
                        for item in session.items()
                        if item.model_identity == "spotify_visualizer"
                    ),
                    None,
                )
                if visualizer_item is None:
                    raise RuntimeError("CUSTOM visualizer transfer lost its session item")
                self._visualizer_pixels_per_world[visualizer_item.source_key] = (
                    self._pixels_per_world_from_geometry(
                        visualizer_item.current_global_rect,
                        visualizer_item.current_viewport_extent,
                    )
                )
        except Exception as lifecycle_error:
            try:
                target_scene.transfer_visualizer_to(source_scene)
            except Exception as rollback_error:
                raise RuntimeError(
                    "CUSTOM visualizer transfer failed and retained-scene rollback failed"
                ) from rollback_error
            raise lifecycle_error

    @staticmethod
    def _is_all(value: object) -> bool:
        return str(value or "ALL").strip().upper() == "ALL"


__all__ = [
    "QuickCustomLayoutOwner",
]
