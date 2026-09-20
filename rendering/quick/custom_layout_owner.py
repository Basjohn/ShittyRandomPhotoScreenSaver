"""Single destination owner for retained Quick CUSTOM layout editing.

The owner is generation-scoped at ``DisplayManager``.  It assembles one global
presentation-neutral :class:`CustomLayoutSession` from the already-admitted
retained Quick presentations, binds each display's existing overlay, and owns
the exact Save/Cancel/reset persistence boundary.  It does not construct a
second presentation, service, visualizer, input router, or cadence owner.
"""

from __future__ import annotations

import math
from copy import deepcopy
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize

from core.logging.logger import get_logger, is_geometry_logging_enabled
from core.settings.default_contract import require_canonical_default
from rendering.quick.column_rails import (
    COLUMN_RAILS_PAYLOAD_KEY, COLUMN_RAIL_IDS, normalize_column_rails, swap_column_rails,
)
from rendering.custom_child_geometry import (
    CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY,
    CustomChildSize,
    clamp_child_geometry,
    flip_child_alignment,
    normalize_child_geometry,
    resolve_child_move_geometry,
    resolve_child_resize_geometry,
    set_child_semantic_anchor,
    update_child_geometry_payload,
)
# The experimental repeated-feed editor was operator-rejected. Retire only
# these known transient role ids at normal CUSTOM admission; never strip
# unknown/future roles and never write Settings during hydration.
_RETIRED_CHILD_ROLE_IDS: dict[str, frozenset[str]] = {
    "reddit": frozenset(("post_rows", "post_time", "post_titles", "post_separators")),
    "reddit2": frozenset(("post_rows", "post_time", "post_titles", "post_separators")),
    "gmail": frozenset(("message_rows", "envelopes", "timestamps", "senders",
                         "subjects", "message_actions", "message_separators",
                         "boundary_separators")),
    # The independent numeral editor was operator-rejected. Face/markers/
    # numerals/hands now use a single center-owned analogue size contract.
    "clock": frozenset(("numerals",)),
    "clock2": frozenset(("numerals",)),
    "clock3": frozenset(("numerals",)),
}


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
    resolve_resize_edge_snap,
    resolve_snap_local_rect_for_edit,
    resolve_uniform_scale_snap,
    set_screen_layout_entry,
    should_transfer_rect_to_screen,
    write_custom_layout_map,
    SnapResolution,
)
from rendering.custom_layout_session import (
    CustomLayoutKey,
    CustomLayoutSession,
    CustomLayoutSessionItem,
    normalize_viewport_extent,
)
from rendering.quick.lifecycle_errors import RetainedRuntimeIncoherenceError
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
    quick_custom_content_extent_minimum_size,
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
from widgets.spotify_visualizer.presentation_orientation import (
    CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY,
    CONTENT_ROTATION_QUARTERS_PAYLOAD_KEY,
    normalize_content_rotation_by_mode,
    resolve_content_rotation_for_mode,
    rotate_quarters_clockwise,
    set_content_rotation_for_mode,
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


def _parse_content_extent(raw: Any) -> tuple[float, float] | None:
    """Parse a persisted ``[width, height]`` content-extent box, or ``None``."""

    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        return None
    try:
        width = float(raw[0])
        height = float(raw[1])
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(width) and math.isfinite(height)):
        return None
    if width <= 0.0 or height <= 0.0:
        return None
    return (width, height)


@dataclass(frozen=True, slots=True)
class _ResizeOrigin:
    rect: QRect
    cursor: QPoint
    scale: float
    viewport_extent: tuple[float, float] | None
    visualizer_uniform_scale: float | None


@dataclass(frozen=True, slots=True)
class _ChildResizeOrigin:
    role_id: str
    handle: str
    cursor: QPoint
    visible_width: float
    visible_height: float
    normalization_width: float
    normalization_height: float
    size: CustomChildSize


@dataclass(frozen=True, slots=True)
class _ChildMoveOrigin:
    role_id: str
    cursor: QPoint
    normalization_width: float
    normalization_height: float
    placement_compensation_x: float
    placement_compensation_y: float
    geometry: CustomChildSize


@dataclass(frozen=True, slots=True)
class _EditUndoSnapshot:
    """One pre-action value of the EXISTING shared session item, not another owner.

    Captured at editor action boundaries, never from QML/render/pointer samples.
    The edit session remains the only mutable geometry/payload authority.
    """

    item: CustomLayoutSessionItem
    display_identity: str
    monitor_route: str
    rect: QRect
    size_payload: dict[str, Any]
    resize_scale: float
    viewport_extent: tuple[float, float] | None
    content_extent: tuple[float, float] | None
    child_sizes: dict[str, CustomChildSize]
    child_requirement: tuple[float, float] | None
    enabled: bool
    removed: bool
    visualizer_pixels_per_world: float | None


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
        live_config_commit: Callable[[Mapping[str, object]], None] | None = None,
        visualizer_presence_commit: Callable[[bool], bool] | None = None,
    ) -> None:
        self._settings_manager = settings_manager
        self._participants_provider = participants_provider
        self._visualizer_provider = visualizer_provider
        self._reload_request = reload_request
        self._visualizer_unit_transfer = visualizer_unit_transfer
        self._live_config_commit = live_config_commit
        self._visualizer_presence_commit = visualizer_presence_commit
        self._session: CustomLayoutSession | None = None
        self._coordinator: QuickCustomLayoutSceneCoordinator | None = None
        self._bindings: dict[str, _DisplayBinding] = {}
        self._descriptors: dict[CustomLayoutKey, WidgetRuntimeDescriptor] = {}
        self._resize_origins: dict[CustomLayoutKey, _ResizeOrigin] = {}
        self._child_resize_origins: dict[CustomLayoutKey, _ChildResizeOrigin] = {}
        self._child_move_origins: dict[CustomLayoutKey, _ChildMoveOrigin] = {}
        # Stable object identity of the globally selected child-edit parent.
        # Selection changes are the authoritative retirement boundary for
        # transient child gestures/containment; QML destruction remains a
        # defensive fallback rather than the sole cleanup owner.
        self._selected_child_edit_item: CustomLayoutSessionItem | None = None
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
        # Bounded three-action Edit-only undo. Snapshot only at action edges;
        # pointer samples, retained QML updates and Settings remain untouched.
        self._undo_history: list[_EditUndoSnapshot] = []
        self._undo_pending: tuple[str, _EditUndoSnapshot] | None = None
        self._active = False
        self._retired = False
        self._settings_change_signal = getattr(settings_manager, "settings_changed", None)
        if self._settings_change_signal is not None and hasattr(
            self._settings_change_signal, "connect"
        ):
            self._settings_change_signal.connect(self._on_settings_changed)

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def is_retired(self) -> bool:
        return self._retired

    @property
    def session(self) -> CustomLayoutSession | None:
        return self._session

    def _capture_undo(self, item: CustomLayoutSessionItem) -> _EditUndoSnapshot:
        return _EditUndoSnapshot(
            item=item,
            display_identity=item.current_display_identity,
            monitor_route=item.current_monitor_route,
            rect=QRect(item.current_global_rect),
            size_payload=deepcopy(item.current_size_payload),
            resize_scale=float(item.resize_scale),
            viewport_extent=item.current_viewport_extent,
            content_extent=item.current_content_extent,
            child_sizes=dict(item.current_child_sizes),
            child_requirement=item.child_content_requirement,
            enabled=item.current_enabled,
            removed=item.removed,
            visualizer_pixels_per_world=self._visualizer_pixels_per_world.get(item.source_key),
        )

    def _undo_state_changed(self, before: _EditUndoSnapshot) -> bool:
        return self._capture_undo(before.item) != before

    def _begin_undo_gesture(self, item: CustomLayoutSessionItem, kind: str) -> None:
        pending = self._undo_pending
        if pending is not None and pending[0] == kind and pending[1].item is item:
            return
        self._finish_undo_gesture()
        self._undo_pending = (kind, self._capture_undo(item))

    def _record_undo(self, before: _EditUndoSnapshot) -> None:
        """Retain at most three completed, state-changing Edit actions."""
        if not self._undo_state_changed(before):
            return
        if len(self._undo_history) == 3:
            del self._undo_history[0]
        self._undo_history.append(before)

    def _finish_undo_gesture(self, kind: str | None = None) -> None:
        pending = self._undo_pending
        if pending is None or (kind is not None and pending[0] != kind):
            return
        self._undo_pending = None
        before = pending[1]
        self._record_undo(before)

    def _commit_discrete_undo(self, before: _EditUndoSnapshot) -> None:
        self._finish_undo_gesture()
        self._record_undo(before)

    def undo_last_change(self) -> bool:
        """Consume one of the last three completed Edit actions; never write Settings.

        No undo during an active pointer gesture: a later release must not be
        permitted to replay the held cursor against restored geometry.
        """
        session = self._session
        if not self._active or session is None:
            return False
        if (self._undo_pending is not None or self._resize_origins
                or self._child_resize_origins or self._child_move_origins):
            return False
        self._finish_undo_gesture()
        if not self._undo_history:
            return False
        before = self._undo_history[-1]
        if not any(entry is before.item for entry in session.items()):
            # A stale item cannot be restored; do not replay older snapshots
            # through a broken session ownership boundary.
            self._undo_history.clear()
            return False
        item = before.item
        self._undo_history.pop()
        self._visualizer_move_transfer_latch.clear()
        self._clear_all_guides()
        item.set_current_display(before.display_identity, monitor_route=before.monitor_route)
        item.set_geometry(before.rect)
        item.current_size_payload = deepcopy(before.size_payload)
        item.resize_scale = before.resize_scale
        item.current_viewport_extent = before.viewport_extent
        item.current_content_extent = before.content_extent
        item.current_child_sizes = dict(before.child_sizes)
        item.child_content_requirement = before.child_requirement
        item.current_enabled = before.enabled
        item.removed = before.removed
        if before.visualizer_pixels_per_world is not None:
            self._visualizer_pixels_per_world[item.source_key] = before.visualizer_pixels_per_world
        session.refresh_duplicate_state()
        session.notify_all_items_changed()
        logger.info("[CUSTOM_LAYOUT] Undo Edit action widget=%s remaining=%d",
                    item.model_identity, len(self._undo_history))
        return True

    def close_item(self, item: CustomLayoutSessionItem) -> None:
        """Keep edit-mode close inside the existing session mutation seam."""
        before = self._capture_undo(item)
        item.apply_remove_action()
        self._commit_discrete_undo(before)

    @staticmethod
    def _resolve_child_collision_enabled(
        widgets: Mapping[str, Any],
        descriptor: WidgetRuntimeDescriptor,
    ) -> bool:
        """Resolve the one global child/child collision preference.

        Families with only one editable child have no peer collision to resolve,
        so they stay trivially enabled. Multi-role families all consume the same
        ``widgets.global.child_collision_enabled`` preference. Keeping the switch
        global prevents rollout slices from growing family-local shadow settings.
        """

        if len(descriptor.custom_child_roles) <= 1:
            return True
        default = bool(
            require_canonical_default("widgets.global.child_collision_enabled")
        )
        global_config = widgets.get("global", {})
        if not isinstance(global_config, Mapping):
            return default
        return bool(global_config.get("child_collision_enabled", default))

    def _on_settings_changed(self, key: str, value: object) -> None:
        """Live-refresh the global Edit-only peer collision preference.

        WidgetsTab writes the structured ``widgets`` root. Updating an active
        CUSTOM session here is event-driven and mutates only the session flag;
        no geometry or CUSTOM payload is rewritten, and nothing runs on render
        cadence or outside a Settings change event.
        """

        if key != "widgets" or not self._active or self._session is None:
            return
        widgets = value if isinstance(value, Mapping) else self._settings_manager.get_widgets_map()
        for item in self._session.items():
            descriptor = self._descriptors.get(item.source_key)
            if descriptor is None or len(descriptor.custom_child_roles) <= 1:
                continue
            enabled = self._resolve_child_collision_enabled(
                widgets,
                descriptor,
            )
            if item.child_collision_enabled == enabled:
                continue
            item.child_collision_enabled = enabled
            self._session.notify_item_changed(item)

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
                    size_reset_handler=self.restore_item_size,
                    content_rotation_handler=self.rotate_visualizer_content,
                    child_resize_begin_handler=self.begin_child_resize,
                    child_resize_preview_handler=self.preview_child_resize,
                    child_resize_update_handler=self.update_child_resize,
                    child_move_begin_handler=self.begin_child_move,
                    child_move_update_handler=self.update_child_move,
                    child_alignment_flip_handler=self.flip_child_alignment,
                    column_rail_swap_handler=self.swap_column_rail_roles,
                    close_item_handler=self.close_item,
                    child_semantic_anchor_handler=self.set_child_semantic_anchor,
                    child_gesture_cancel_handler=self.cancel_child_gesture,
                    child_content_extent_handler=self.ensure_child_content_extent,
                    child_content_extent_clear_handler=self.clear_child_content_extent,
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
        self._selected_child_edit_item = None
        session.subscribe_selection(self._on_child_edit_selection_changed)
        self._active = True
        logger.info(
            "[CUSTOM_LAYOUT] Started one Quick session displays=%d items=%d",
            len(bindings),
            len(session.items()),
        )
        return True


    def _on_child_edit_selection_changed(
        self,
        selected: CustomLayoutSessionItem | None,
    ) -> None:
        """Retire transient child-edit state at the stable selection boundary.

        QML loaders/delegates are presentation details and may be destroyed after
        model rows have already been rebuilt.  Relying on an old row index during
        ``Component.onDestruction`` can therefore target the wrong session item.
        The session's selected object identity is stable, so make it the primary
        cleanup authority: the previous parent loses pointer origins and its
        selected-Edit-only containment floor immediately when focus moves away.

        This callback is event-owned and exists only for an active CUSTOM edit
        session.  It adds no runtime cadence outside Edit.
        """

        previous = self._selected_child_edit_item
        if previous is selected:
            return
        if previous is not None:
            self._resize_origins.pop(previous.source_key, None)
            self.cancel_child_gesture(previous)
            self.clear_child_content_extent(previous)
        self._selected_child_edit_item = selected

    def cancel(self) -> bool:
        if not self._active or self._session is None:
            return False
        restore_error: Exception | None = None
        try:
            self._session.restore_baseline()
        except Exception as exc:
            # Baseline state lives in settings/session primitives; a dead retained
            # Quick object must not strand one display in Edit. Close the shared
            # session below and explicitly reconstruct from committed truth.
            restore_error = exc
            logger.exception(
                "[CUSTOM_LAYOUT] Baseline projection failed during Cancel; "
                "closing session and reconciling retained runtime"
            )
        cleanup_corruption = self._finish()
        if restore_error is not None or cleanup_corruption:
            logger.error(
                "[CUSTOM_LAYOUT] Cancel requires retained-runtime reconciliation "
                "restore_error=%s corruption=%s",
                None if restore_error is None else type(restore_error).__name__,
                cleanup_corruption,
            )
            self._reload_request("cancel_corrupt_retained_runtime")
        logger.info("[CUSTOM_LAYOUT] Cancelled Quick session")
        return True

    def _log_selected_child_geometry_boundary(
        self, phase: str, item: CustomLayoutSessionItem | None,
    ) -> None:
        """Event-only --geo snapshot; never a layout/readback authority.

        Sample the selected retained targets only at Save/Restore boundaries,
        not at pointer/render/parent-geometry cadence. This exposes a target
        whose mapped rectangle differs before/after retained Save while keeping
        all provider text, artwork URLs and user data out of the sidecar.
        Geometry observation must not alter persistence or Edit failure policy.
        """
        if not is_geometry_logging_enabled() or item is None:
            return
        carrier = item.current_size_payload.get(CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY)
        logger.info(
            "[CUSTOM_LAYOUT] [GEO_CHILD] %s widget=%s parent=%s scale=%.5f "
            "extent=%s roles=%s carrier_roles=%s",
            phase, item.source_key.widget_id,
            item.current_global_rect.getRect(), item.resize_scale,
            item.current_content_extent, tuple(sorted(item.current_child_sizes)),
            tuple(sorted(carrier)) if isinstance(carrier, dict) else (),
        )
        binding = self._bindings.get(item.current_display_identity)
        if binding is None or item.model_identity == "spotify_visualizer":
            return
        presenter = getattr(binding.unit, "presenter", None)
        family_lookup = getattr(presenter, "presentation_for_widget_id", None)
        if not callable(family_lookup):
            return
        presentation = family_lookup(item.model_identity)
        root = getattr(presentation, "item", None)
        if root is None:
            return
        # These are existing family-declared target references; never walk a
        # scene subtree or construct a new list of role identities at runtime.
        try:
            role_models = root.property("customEditableChildRoles")
            if hasattr(role_models, "toVariant"):
                role_models = role_models.toVariant()
        except (AttributeError, RuntimeError, TypeError):
            return
        if not isinstance(role_models, (list, tuple)):
            return
        for entry in role_models:
            if not isinstance(entry, dict):
                continue
            role_id = str(entry.get("roleId", ""))
            if not role_id:
                continue
            target = entry.get("target")
            if target is None:
                continue
            try:
                mapped = target.mapRectToItem(root, target.boundingRect())
                logger.info(
                    "[CUSTOM_LAYOUT] [GEO_CHILD] %s_target widget=%s role=%s "
                    "root_rect=(%.2f,%.2f,%.2f,%.2f) visible=%s",
                    phase, item.source_key.widget_id, role_id,
                    mapped.x(), mapped.y(), mapped.width(), mapped.height(),
                    bool(target.isVisible()),
                )
            except (AttributeError, RuntimeError, TypeError):
                # A target may retire at a Save/Restore boundary. Diagnostic
                # observation must never turn a healthy Save into a fault.
                logger.info(
                    "[CUSTOM_LAYOUT] [GEO_CHILD] %s_target_retired widget=%s role=%s",
                    phase, item.source_key.widget_id, role_id,
                )

    def save(self, *, defer_topology_reconciliation: bool = False) -> bool:
        if not self._active or self._session is None:
            return False
        # Observe the SAME session item and retained QML target on either side
        # of the existing Save promotion; do not initiate a layout publication.
        selected_geo_item = self._session.selected_item() if is_geometry_logging_enabled() else None
        self._log_selected_child_geometry_boundary("save_before", selected_geo_item)
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
        # A cross-display gesture has already moved the retained pixels.
        # Visualizer ownership moves atomically during the gesture; ordinary
        # family/binding/service records are promoted below before Edit closes.
        # Slot transactions retain their explicit deferred replacement contract.
        live_committing = topology_reason is None
        if (
            not live_committing
            and topology_reason == "display_transfer"
            and not defer_topology_reconciliation
            and self._cross_display_transfer_is_coherent()
        ):
            live_committing = True
            logger.info(
                "[CUSTOM_LAYOUT] Save live-committed cross-display "
                "transfer without generation reconciliation"
            )
        promotion_error: RetainedRuntimeIncoherenceError | None = None
        if live_committing:
            try:
                self._promote_live_geometry_commit(widgets)
            except RetainedRuntimeIncoherenceError as exc:
                # Persistence has already committed. A deliberately classified
                # retained-owner/liveness failure may rebuild from that persisted
                # state after the shared edit session is terminalized.
                promotion_error = exc
                logger.error(
                    "[CUSTOM_LAYOUT] Live geometry promotion found retained-runtime "
                    "incoherence; closing session and reconciling runtime: %s",
                    exc,
                )
            except Exception:
                # Do not turn programming defects (TypeError, AttributeError, bad
                # call contracts, etc.) into a seemingly legitimate generation
                # replacement. That exact anti-pattern previously hid the broken
                # _promote_live_geometry_commit call signature and caused every
                # healthy Edit Save to tear down. Terminalize the edit overlay,
                # then surface the defect loudly to its caller.
                cleanup_corruption = self._finish()
                if cleanup_corruption:
                    logger.error(
                        "[CUSTOM_LAYOUT] Unexpected live-promotion defect also "
                        "encountered cleanup corruption=%s",
                        cleanup_corruption,
                    )
                logger.exception(
                    "[CUSTOM_LAYOUT] Unexpected live geometry promotion defect; "
                    "NOT converting programming error into runtime reconstruction"
                )
                raise
        else:
            logger.info(
                "[CUSTOM_LAYOUT] Save retains generation reconciliation reason=%s",
                topology_reason,
            )
        self._log_selected_child_geometry_boundary("save_after_commit_attempt", selected_geo_item)
        cleanup_corruption = self._finish()
        # Geometry-only / coherent live commits remain in this retained
        # generation. A layout-slot transaction can explicitly defer topology
        # replacement until its slot attempt completes; no caller gets an ignored
        # compatibility flag. Proven retained-object corruption is different: the
        # saved primitives are authoritative, so request one explicit reconstruction
        # rather than continuing with dead wrappers.
        if promotion_error is not None or cleanup_corruption:
            logger.error(
                "[CUSTOM_LAYOUT] Save requires retained-runtime reconciliation "
                "promotion_error=%s corruption=%s",
                None if promotion_error is None else type(promotion_error).__name__,
                cleanup_corruption,
            )
            self._reload_request("save_corrupt_retained_runtime")
        elif not live_committing:
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
        cleanup_corruption = self._finish()
        if cleanup_corruption:
            logger.error(
                "[CUSTOM_LAYOUT] Reset closed over corrupt retained objects: %s",
                cleanup_corruption,
            )
        self._reload_request("reset_authored")
        logger.info("[CUSTOM_LAYOUT] Restored authored Quick layout")
        return True

    def retire(self) -> bool:
        if self._retired:
            return False
        if self._active:
            try:
                if self._session is not None:
                    self._session.restore_baseline()
            except Exception:
                logger.exception(
                    "[CUSTOM_LAYOUT] Terminal retire could not project CUSTOM baseline"
                )
            self._finish()
        self._retired = True
        signal = self._settings_change_signal
        self._settings_change_signal = None
        if signal is not None and hasattr(signal, "disconnect"):
            try:
                signal.disconnect(self._on_settings_changed)
            except (RuntimeError, TypeError):
                pass
        self._participants_provider = lambda: ()
        self._visualizer_provider = lambda: (None, None)
        return True

    def resolve_move(
        self,
        item: CustomLayoutSessionItem,
        proposed: QRect,
        cursor: QPoint,
    ) -> QRect:
        self._begin_undo_gesture(item, "parent_move")
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

        self._finish_undo_gesture("parent_move")
        self._visualizer_move_transfer_latch.clear()
        self._clear_all_guides()

    def _clear_all_guides(self) -> None:
        """Clear transient alignment guides on every bound display."""

        for binding in tuple(self._bindings.values()):
            try:
                binding.unit.runtime.scene_controller.set_custom_layout_guides()
            except (RuntimeError, AttributeError):
                logger.debug(
                    "[CUSTOM_LAYOUT] Failed clearing transient guides display=%s",
                    binding.identity,
                    exc_info=True,
                )

    def _snap_resize_edges(
        self,
        item: CustomLayoutSessionItem,
        binding: _DisplayBinding,
        rect: QRect,
        *,
        horizontal_edge: str | None,
        vertical_edge: str | None,
        min_size: Any,
    ) -> QRect:
        """Snap the moving edge(s) of a resize rect to peers and publish guides.

        The opposite edges stay anchored (the incoming rect already anchors them),
        so this only nudges the dragged edge onto an alignment line when close.
        Guides are the same peer/centre lines the move gesture renders.
        """

        local = QRect(
            rect.x() - binding.geometry.x(),
            rect.y() - binding.geometry.y(),
            rect.width(),
            rect.height(),
        )
        resolution = resolve_resize_edge_snap(
            local,
            binding.geometry.size(),
            horizontal_edge=horizontal_edge,
            vertical_edge=vertical_edge,
            peer_rects=self._peer_local_rects(item, binding),
            min_size=min_size,
        )
        self._publish_move_guides(item.current_display_identity, resolution)
        snapped = resolution.rect
        return QRect(
            binding.geometry.x() + snapped.x(),
            binding.geometry.y() + snapped.y(),
            snapped.width(),
            snapped.height(),
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
        before_undo = self._capture_undo(item)
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
        self._commit_discrete_undo(before_undo)
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
            try:
                scene = binding.unit.runtime.scene_controller
                if identity == target_identity:
                    scene.set_custom_layout_guides(
                        vertical=vertical,
                        horizontal=horizontal,
                    )
                else:
                    scene.set_custom_layout_guides()
            except (RuntimeError, AttributeError):
                # Guide projection is a transient edit-only side effect; a display
                # whose scene is not (or no longer) wired must never fail the
                # geometry gesture that triggered it.
                logger.debug(
                    "[CUSTOM_LAYOUT] Failed publishing transient guides display=%s",
                    identity,
                    exc_info=True,
                )

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
        content_corner_handles = {
            "content_top_left",
            "content_top_right",
            "content_bottom_left",
            "content_bottom_right",
        }
        is_viewport_handle = (
            item.viewport_resize_capable and handle_id in viewport_handles
        )
        if handle_id in {"left", "right", "top", "bottom"}:
            axis = "horizontal" if handle_id in {"left", "right"} else "vertical"
            if not (
                item.viewport_resize_capable
                or axis in item.content_extent_axes
            ):
                return False
        elif handle_id in content_corner_handles:
            if (
                not item.resize_capable
                or item.viewport_resize_capable
                or not {"horizontal", "vertical"}.issubset(item.content_extent_axes)
            ):
                return False
        elif not item.resize_capable:
            return False

        # A family may explicitly expose real painted leading clearance for a
        # reversed CUSTOM content card. Sample it ONCE at the gesture boundary,
        # never on pointer motion or normal rendering. The authored dimensions
        # remain the independent Restore Size reference; this lowers only the
        # selected session's *horizontal* content minimum, not its Y floor or
        # collision policy. No opt-in property means the existing safe minimum.
        if handle_id == "left" and not item.viewport_resize_capable:
            descriptor = self._descriptors.get(item.source_key)
            if descriptor is not None and descriptor.content_extent_floor_at_authored_size:
                binding = self._bindings.get(item.current_display_identity)
                presenter = getattr(getattr(binding, "unit", None), "presenter", None)
                lookup = getattr(presenter, "presentation_for_widget_id", None)
                presentation = lookup(item.model_identity) if callable(lookup) else None
                root = getattr(presentation, "item", None)
                # A retired QQuickItem is never a licence to shrink the card.
                # Use the ordinary authored floor if the retained family cannot
                # provide its measured Edit-only paint clearance at this boundary.
                try:
                    raw_allowance = (
                        root.property("customLeadingTrimAllowance") if root is not None else None
                    )
                    allowance = float(raw_allowance)
                except (TypeError, ValueError, OverflowError, RuntimeError):
                    allowance = 0.0
                configured_width, configured_height = descriptor.content_extent_minimum_size or (1, 1)
                authored_width, authored_height = item.authored_reference_size or (1, 1)
                if not math.isfinite(allowance) or allowance <= 0.0:
                    allowance = 0.0
                # Never invent more clearance than the retained family reported;
                # keep the card usable even if a stale QML item returns nonsense.
                allowance = min(allowance, max(0.0, float(authored_width) - 48.0))
                item.content_extent_minimum_size = (
                    max(int(configured_width) if allowance == 0 else 1,
                        int(math.ceil(float(authored_width) - allowance))),
                    max(int(configured_height), int(authored_height)),
                )

        # One item has one active geometry gesture owner. If a child pointer
        # stream was interrupted and a parent handle takes over, retire only the
        # transient child origin before capturing the parent resize origin.
        self.cancel_child_gesture(item)

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
        self._begin_undo_gesture(item, "parent_resize")
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
            if item.viewport_resize_capable:
                changed = self._resize_viewport_edge(item, origin, handle_id, cursor)
            else:
                changed = self._resize_content_edge(item, origin, handle_id, cursor)
        elif handle_id.startswith("content_"):
            changed = self._resize_content_corner(item, origin, handle_id, cursor)
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
            self._finish_undo_gesture("parent_resize")
            # Release ends the gesture: retire the transient alignment guides the
            # live resize samples published (same boundary as move's finishMove).
            self._clear_all_guides()
        return changed

    def begin_child_resize(
        self,
        item: CustomLayoutSessionItem,
        role_id: str,
        handle: str,
        cursor: QPoint,
        visible_width: float,
        visible_height: float,
        normalization_width: float,
        normalization_height: float,
    ) -> bool:
        """Begin one descriptor-gated child-size gesture.

        QML reports only the currently rendered child dimensions so pointer
        deltas remain correct through outer uniform transforms. Python owns the
        normalized factor math and persistence.
        """

        role = item.child_role(role_id)
        handle_id = str(handle or "")
        if role is None or not role.admits_resize_handle(handle_id):
            return False
        try:
            width = float(visible_width)
            height = float(visible_height)
            norm_width = float(normalization_width)
            norm_height = float(normalization_height)
        except (TypeError, ValueError):
            return False
        if not (
            math.isfinite(width)
            and math.isfinite(height)
            and math.isfinite(norm_width)
            and math.isfinite(norm_height)
            and width > 1.0
            and height > 1.0
            and norm_width > 1.0e-6
            and norm_height > 1.0e-6
        ):
            return False
        # A new child gesture owns this item exclusively. Retire any stale
        # parent/move origin left by an interrupted pointer stream rather than
        # allowing one prior gesture to leak into a repeat adjustment.
        self._resize_origins.pop(item.source_key, None)
        self._child_move_origins.pop(item.source_key, None)
        self._child_resize_origins[item.source_key] = _ChildResizeOrigin(
            role_id=role.role_id,
            handle=handle_id,
            cursor=QPoint(cursor),
            visible_width=width,
            visible_height=height,
            normalization_width=norm_width,
            normalization_height=norm_height,
            size=item.child_size(role.role_id),
        )
        self._begin_undo_gesture(item, "child_resize")
        return True

    def update_child_resize(
        self,
        item: CustomLayoutSessionItem,
        role_id: str,
        handle: str,
        cursor: QPoint,
        finalize: bool,
    ) -> bool:
        origin = self._child_resize_origins.get(item.source_key)
        role = item.child_role(role_id)
        handle_id = str(handle or "")
        if (
            origin is None
            or role is None
            or origin.role_id != role.role_id
            or origin.handle != handle_id
            or not role.admits_resize_handle(handle_id)
        ):
            if finalize:
                self._child_resize_origins.pop(item.source_key, None)
            return False

        resolved = resolve_child_resize_geometry(
            role,
            origin.size,
            handle=handle_id,
            raw_dx=float(cursor.x() - origin.cursor.x()),
            raw_dy=float(cursor.y() - origin.cursor.y()),
            visible_width=origin.visible_width,
            visible_height=origin.visible_height,
            normalization_width=origin.normalization_width,
            normalization_height=origin.normalization_height,
            outer_scale=float(item.resize_scale),
        )
        next_size = resolved.geometry
        changed = item.set_child_size(role.role_id, next_size)
        if changed:
            item.current_size_payload = update_child_geometry_payload(
                item.current_size_payload,
                item.custom_child_roles,
                item.current_child_sizes,
            )
        if finalize:
            self._child_resize_origins.pop(item.source_key, None)
            self._finish_undo_gesture("child_resize")
        return changed

    def preview_child_resize(
        self,
        item: CustomLayoutSessionItem,
        role_id: str,
        handle: str,
        cursor: QPoint,
    ) -> QPoint | None:
        """Return the descriptor-bounded pointer equivalent without mutation.

        QML collision/containment needs a live rectangle before committing a
        resize sample.  Feeding it the raw pointer used to let an extreme drag
        grow the parent beyond a child's descriptor maximum and leave permanent
        empty space.  Preview and commit now share the exact same resolver.
        """

        origin = self._child_resize_origins.get(item.source_key)
        role = item.child_role(role_id)
        handle_id = str(handle or "")
        if (
            origin is None
            or role is None
            or origin.role_id != role.role_id
            or origin.handle != handle_id
            or not role.admits_resize_handle(handle_id)
        ):
            return None
        resolved = resolve_child_resize_geometry(
            role,
            origin.size,
            handle=handle_id,
            raw_dx=float(cursor.x() - origin.cursor.x()),
            raw_dy=float(cursor.y() - origin.cursor.y()),
            visible_width=origin.visible_width,
            visible_height=origin.visible_height,
            normalization_width=origin.normalization_width,
            normalization_height=origin.normalization_height,
            outer_scale=float(item.resize_scale),
        )
        width_delta = resolved.visible_width - origin.visible_width
        height_delta = resolved.visible_height - origin.visible_height
        if role.centered_resize:
            width_delta *= 0.5
            height_delta *= 0.5
        return QPoint(
            origin.cursor.x()
            + int(round(-width_delta if handle_id.endswith("left") else width_delta)),
            origin.cursor.y()
            + int(round(-height_delta if (handle_id == "top" or handle_id.startswith("top_")) else height_delta)),
        )

    def begin_child_move(
        self,
        item: CustomLayoutSessionItem,
        role_id: str,
        cursor: QPoint,
        normalization_width: float,
        normalization_height: float,
        placement_compensation_x: float = 0.0,
        placement_compensation_y: float = 0.0,
    ) -> bool:
        """Begin one authored-relative child placement gesture.

        The retained overlay reports pointer coordinates and the role's stable
        authored normalization box. Python owns the persisted normalized offset;
        QML remains only the live presentation/collision admission surface.
        """

        role = item.child_role(role_id)
        if role is None or not role.movable:
            return False
        try:
            norm_width = float(normalization_width)
            norm_height = float(normalization_height)
            compensation_x = float(placement_compensation_x)
            compensation_y = float(placement_compensation_y)
        except (TypeError, ValueError):
            return False
        if not (
            math.isfinite(norm_width)
            and math.isfinite(norm_height)
            and math.isfinite(compensation_x)
            and math.isfinite(compensation_y)
            and norm_width > 1.0e-6
            and norm_height > 1.0e-6
        ):
            return False
        self._resize_origins.pop(item.source_key, None)
        self._child_resize_origins.pop(item.source_key, None)
        self._child_move_origins[item.source_key] = _ChildMoveOrigin(
            role_id=role.role_id,
            cursor=QPoint(cursor),
            normalization_width=norm_width,
            normalization_height=norm_height,
            placement_compensation_x=compensation_x,
            placement_compensation_y=compensation_y,
            geometry=item.child_size(role.role_id),
        )
        self._begin_undo_gesture(item, "child_move")
        # --geo is an opt-in, event-boundary diagnostic. Do not log pointer
        # samples, render frames, provider content or mutable user data.
        if is_geometry_logging_enabled():
            starting = item.child_size(role.role_id)
            logger.info(
                "[CUSTOM_LAYOUT] [GEO_CHILD] begin widget=%s role=%s "
                "parent=%s cursor=(%s,%s) offset=(%.6f,%.6f) "
                "compensation=(%.2f,%.2f) norm=(%.1f,%.1f) scale=%.4f",
                item.source_key.widget_id, role.role_id,
                item.current_global_rect.getRect(), cursor.x(), cursor.y(),
                starting.x_offset, starting.y_offset, compensation_x,
                compensation_y, norm_width, norm_height, item.resize_scale,
            )
        return True

    def update_child_move(
        self,
        item: CustomLayoutSessionItem,
        role_id: str,
        cursor: QPoint,
        finalize: bool,
    ) -> bool:
        origin = self._child_move_origins.get(item.source_key)
        role = item.child_role(role_id)
        if (
            origin is None
            or role is None
            or not role.movable
            or origin.role_id != role.role_id
        ):
            if finalize:
                self._child_move_origins.pop(item.source_key, None)
            return False

        next_geometry = resolve_child_move_geometry(
            role,
            origin.geometry,
            raw_dx=float(cursor.x() - origin.cursor.x()),
            raw_dy=float(cursor.y() - origin.cursor.y()),
            normalization_width=origin.normalization_width,
            normalization_height=origin.normalization_height,
            outer_scale=float(item.resize_scale),
            placement_compensation_x=origin.placement_compensation_x,
            placement_compensation_y=origin.placement_compensation_y,
        )
        changed = item.set_child_size(role.role_id, next_geometry)
        if changed:
            item.current_size_payload = update_child_geometry_payload(
                item.current_size_payload,
                item.custom_child_roles,
                item.current_child_sizes,
            )
        if finalize:
            self._child_move_origins.pop(item.source_key, None)
            self._finish_undo_gesture("child_move")
            if is_geometry_logging_enabled():
                logger.info(
                    "[CUSTOM_LAYOUT] [GEO_CHILD] end widget=%s role=%s "
                    "parent=%s cursor_delta=(%s,%s) offset=(%.6f,%.6f) "
                    "compensation=(%.2f,%.2f) changed=%s",
                    item.source_key.widget_id, role.role_id,
                    item.current_global_rect.getRect(),
                    cursor.x() - origin.cursor.x(),
                    cursor.y() - origin.cursor.y(),
                    next_geometry.x_offset, next_geometry.y_offset,
                    origin.placement_compensation_x,
                    origin.placement_compensation_y, changed,
                )
        return changed

    def swap_column_rail_roles(
        self, item: CustomLayoutSessionItem, source: str, target: str
    ) -> bool:
        """Reorder a whole list column once on release; no per-row edits or I/O."""
        family = item.source_key.widget_id
        authored = COLUMN_RAIL_IDS.get(family)
        if authored is None or not self._active or self._session is None:
            return False
        current = normalize_column_rails(
            family, item.current_size_payload.get(COLUMN_RAILS_PAYLOAD_KEY)
        )
        if current is None:
            flipped = item.child_size("header").alignment == "right"
            if family in ("reddit", "reddit2"):
                current = ("title", "age", "ago") if flipped else authored
            else:
                current = ("sender", "subject", "timestamp") if flipped else authored
        updated = swap_column_rails(family, current, source, target)
        if updated is None:
            return False
        before = self._capture_undo(item)
        payload = dict(item.current_size_payload)
        payload[COLUMN_RAILS_PAYLOAD_KEY] = list(updated)
        item.current_size_payload = payload
        self._commit_discrete_undo(before)
        return True

    def flip_child_alignment(
        self, item: CustomLayoutSessionItem, role_id: str
    ) -> bool:
        """Toggle one descriptor-admitted role alignment in the shared payload.

        This is an explicit Edit-mode click transaction, not pointer cadence. The
        role stays inside the existing ``child_geometry`` carrier so Save/Cancel/
        Restore/slots keep one authority and family rendering only projects it.
        """

        role = item.child_role(role_id)
        if role is None or not role.alignment_flip:
            return False
        before_undo = self._capture_undo(item)
        next_geometry = flip_child_alignment(role, item.child_size(role.role_id))
        changed = item.set_child_size(role.role_id, next_geometry)
        if changed:
            self._commit_discrete_undo(before_undo)
            item.current_size_payload = update_child_geometry_payload(
                item.current_size_payload,
                item.custom_child_roles,
                item.current_child_sizes,
            )
            if is_geometry_logging_enabled():
                logger.info(
                    "[CUSTOM_LAYOUT] [GEO_CHILD] flip widget=%s role=%s "
                    "alignment=%s parent=%s",
                    item.source_key.widget_id, role.role_id,
                    next_geometry.alignment, item.current_global_rect.getRect(),
                )
        return changed

    def set_child_semantic_anchor(
        self,
        item: CustomLayoutSessionItem,
        role_id: str,
        anchor: str | None,
    ) -> bool:
        """Commit one descriptor-admitted semantic corner anchor."""

        role = item.child_role(role_id)
        if role is None or not role.semantic_corner_anchor:
            return False
        before_undo = self._capture_undo(item)
        next_geometry = set_child_semantic_anchor(
            role, item.child_size(role.role_id), anchor
        )
        changed = item.set_child_size(role.role_id, next_geometry)
        if changed:
            item.current_size_payload = update_child_geometry_payload(
                item.current_size_payload,
                item.custom_child_roles,
                item.current_child_sizes,
            )
            self._commit_discrete_undo(before_undo)
        return changed

    def cancel_child_gesture(self, item: CustomLayoutSessionItem) -> None:
        """Retire transient child pointer origins without mutating committed state."""

        self._child_resize_origins.pop(item.source_key, None)
        self._child_move_origins.pop(item.source_key, None)
        if self._undo_pending is not None and self._undo_pending[1].item is item:
            self._finish_undo_gesture()

    def clear_child_content_extent(self, item: CustomLayoutSessionItem) -> bool:
        """Retire selected-Edit-only containment without changing outer geometry."""

        if item.child_content_requirement is None:
            return False
        item.child_content_requirement = None
        return True

    def ensure_child_content_extent(
        self,
        item: CustomLayoutSessionItem,
        required_width: float,
        required_height: float,
    ) -> bool:
        """Never enlarge an outer widget in response to a child edit.

        This defensive boundary also rejects stale QML or external callers
        trying to publish an obsolete growth demand. The selected child editor
        clamps painted occupancy to its containing surface, while outer handles
        remain the only source of parent size changes.
        """
        return False

    def resize_wheel(
        self,
        item: CustomLayoutSessionItem,
        angle_delta_y: int,
    ) -> bool:
        if not item.resize_capable:
            return False
        before_undo = self._capture_undo(item)
        steps = int(angle_delta_y / 120) if angle_delta_y else 0
        if steps == 0:
            steps = 1 if angle_delta_y > 0 else -1
        changed = self._apply_uniform_scale(
            item,
            max(
                CUSTOM_LAYOUT_MIN_RESIZE_SCALE,
                float(item.resize_scale) + 0.05 * steps,
            ),
            QRect(item.current_global_rect),
        )
        self._commit_discrete_undo(before_undo)
        # Wheel resize is intentionally free of magnetic snapping, but nearby peer
        # alignment is still useful visual feedback.  Resolve the same peer-line
        # metadata against the already-applied free geometry and publish only its
        # guides; never feed the resolver's suggested scale back into geometry.
        self._publish_uniform_wheel_guides(item)
        return changed

    def _publish_uniform_wheel_guides(
        self, item: CustomLayoutSessionItem
    ) -> None:
        binding = self._bindings.get(item.current_display_identity)
        if binding is None:
            self._clear_all_guides()
            return
        rect = QRect(item.current_global_rect)
        snap = resolve_uniform_scale_snap(
            float(item.resize_scale),
            center_x=(
                float(rect.x()) + float(rect.width()) / 2.0
                - float(binding.geometry.x())
            ),
            top=float(rect.y()) - float(binding.geometry.y()),
            free_width=float(rect.width()),
            free_height=float(rect.height()),
            display_size=binding.geometry.size(),
            peer_rects=self._peer_local_rects(item, binding),
        )
        self._publish_move_guides(
            item.current_display_identity,
            SnapResolution(
                rect=QRect(rect),
                vertical_guides=snap.vertical_guides,
                horizontal_guides=snap.horizontal_guides,
            ),
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
            enabled_default = bool(
                require_canonical_default(f"widgets.{widget_id}.enabled")
            )
            enabled = (
                bool(section.get("enabled", enabled_default))
                if isinstance(section, Mapping)
                else enabled_default
            )
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

            # A previously-saved content-extent box (a side-drag reflow) is the
            # authoritative reference for this family's edit envelope. Using the
            # committed box rather than the live preferred size keeps the H9
            # canonicalization below a no-op instead of collapsing the reflowed
            # axis back to the authored aspect.
            content_axes = frozenset(descriptor.content_extent_axes)
            committed_content_extent: tuple[float, float] | None = None
            if content_axes and committed_entry is not None:
                committed_content_extent = _parse_content_extent(
                    committed_entry.size_payload.get("content_extent")
                )

            committed_child_sizes: dict[str, CustomChildSize] = {}
            if descriptor.custom_child_roles and committed_entry is not None:
                raw_child_geometry = committed_entry.size_payload.get(
                    CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY
                )
                committed_child_sizes = normalize_child_geometry(
                    raw_child_geometry, descriptor.custom_child_roles
                )
                if isinstance(raw_child_geometry, Mapping):
                    # Preserve future/unknown role records exactly, but drop the
                    # explicitly rejected feed experiment in the in-memory edit
                    # transaction. Only a normal Save/slot commit persists it.
                    retired = _RETIRED_CHILD_ROLE_IDS.get(widget_id, frozenset())
                    admitted = {
                        role_id: value for role_id, value in raw_child_geometry.items()
                        if str(role_id) not in retired
                    }
                    if widget_id in {"clock", "clock2", "clock3"}:
                        # The face is now center-fixed. Retire only its old
                        # experimental placement keys on normal CUSTOM admission;
                        # preserve its authored-relative scale and every unknown
                        # future field until the existing Save/slot transaction.
                        face = admitted.get("clock_face")
                        if isinstance(face, Mapping):
                            centered_face = dict(face)
                            centered_face.pop("x_offset", None)
                            centered_face.pop("y_offset", None)
                            admitted["clock_face"] = centered_face
                    payload = dict(payload)
                    if admitted:
                        payload[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY] = admitted
                    else:
                        payload.pop(CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY, None)

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
                    if committed_content_extent is not None:
                        preferred_width = float(committed_content_extent[0])
                        preferred_height = float(committed_content_extent[1])
                    else:
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

            # Carry a committed content-extent box into the session payload so
            # entering edit mode keeps the reflow (the edit overlay republishes
            # current_size_payload through apply_custom_layout_size_payload). No
            # committed box means the family stays uniform until its first side
            # drag establishes one.
            if content_axes and committed_content_extent is not None:
                payload = dict(payload)
                payload["content_extent"] = [
                    committed_content_extent[0],
                    committed_content_extent[1],
                ]

            # One widget-wide list order is part of the committed CUSTOM carrier.
            # It must survive a new Edit session and a different display generation,
            # but never leak into authored mode or unrelated widget families.
            if committed_entry is not None and widget_id in COLUMN_RAIL_IDS:
                committed_order = normalize_column_rails(
                    widget_id,
                    committed_entry.size_payload.get(COLUMN_RAILS_PAYLOAD_KEY),
                )
                if committed_order is not None:
                    payload[COLUMN_RAILS_PAYLOAD_KEY] = list(committed_order)

            # Per-widget Restore Size has a different authority from the edit
            # admission baseline.  The display presenter retains the current
            # *unstacked authored* rectangle even when the live retained item is
            # replaying a committed CUSTOM shape.  Capture only its dimensions:
            # Restore Size must never own authored X/Y or display routing.
            authored_geometry = binding.unit.presenter.authored_geometry_for(widget_id)
            if authored_geometry is not None:
                authored_width = max(1, int(round(authored_geometry.width)))
                authored_height = max(1, int(round(authored_geometry.height)))
            else:
                # Defensive fallback for a family without a base-geometry
                # record.  Undo the admitted absolute CUSTOM scale so this is
                # still a size reference rather than a second position source.
                authored_width = max(
                    1,
                    int(round(float(global_rect.width()) / max(1.0e-6, baseline_resize_scale))),
                )
                authored_height = max(
                    1,
                    int(round(float(global_rect.height()) / max(1.0e-6, baseline_resize_scale))),
                )
            authored_rect = QRect(0, 0, authored_width, authored_height)
            authored_payload = capture_quick_size_payload(
                descriptor,
                presentation,
                authored_rect,
            )
            authored_payload.pop("content_extent", None)

            content_extent_minimum_size = descriptor.content_extent_minimum_size
            if descriptor.content_extent_floor_at_authored_size:
                configured_min_width, configured_min_height = (
                    content_extent_minimum_size or (1, 1)
                )
                content_extent_minimum_size = (
                    max(int(configured_min_width), authored_width),
                    max(int(configured_min_height), authored_height),
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
                content_extent_axes=content_axes,
                content_extent_minimum_size=content_extent_minimum_size,
                baseline_content_extent=committed_content_extent,
                custom_child_roles=descriptor.custom_child_roles,
                child_collision_enabled=self._resolve_child_collision_enabled(
                    widgets,
                    descriptor,
                ),
                baseline_child_sizes=committed_child_sizes,
                current_child_sizes=committed_child_sizes,
                size_reset_capable=descriptor.requires_size_reset_affordance,
                authored_reference_size=(authored_width, authored_height),
                authored_size_payload=authored_payload,
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
        # Preserve all carded-mode orientations even when the currently selected
        # experimental mode (Sphere) does not consume or expose them. Sphere
        # therefore renders at 0° without erasing dormant per-mode layout state.
        rotations = normalize_content_rotation_by_mode(
            owner.controller.committed_content_rotations
        )
        if rotations:
            payload[CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY] = rotations
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
            content_rotation_capable=bool(
                owner.controller.presentation_policy.content_rotation_capable
            ),
            size_reset_capable=descriptor.requires_size_reset_affordance,
            authored_reference_size=(
                float(CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[0])
                * float(presentation.uniform_visual_scale),
                float(CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[1])
                * float(presentation.uniform_visual_scale),
            ),
            authored_size_payload={},
            authored_viewport_extent=(
                float(CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[0]),
                float(CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[1]),
            ),
        )
        session.add_item(item)
        descriptors[key] = descriptor
        self._visualizer_pixels_per_world[key] = (
            self._pixels_per_world_from_geometry(global_rect, extent)
        )

    def rotate_visualizer_content(self, item: CustomLayoutSessionItem) -> bool:
        """Advance one eligible Visualizer CUSTOM content orientation by 90°."""

        if (
            not self._active
            or self._session is None
            or item.model_identity != "spotify_visualizer"
            or not item.content_rotation_capable
        ):
            return False
        owner, _unit = self._visualizer_provider()
        if owner is None:
            return False
        # The session role is an admission snapshot. Re-check the live mode
        # capability at the action boundary so an unusual mode switch while
        # Edit is open can never route a stale rotate click into Sphere.
        if not owner.controller.presentation_policy.content_rotation_capable:
            return False
        before_undo = self._capture_undo(item)
        mode_id = owner.controller.mode_id
        rotations = normalize_content_rotation_by_mode(
            item.current_size_payload.get(CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY, {})
        )
        current = resolve_content_rotation_for_mode(
            rotations,
            mode_id,
            legacy_value=item.current_size_payload.get(
                CONTENT_ROTATION_QUARTERS_PAYLOAD_KEY, 0
            ),
        )
        next_rotation = rotate_quarters_clockwise(current)
        rotations = set_content_rotation_for_mode(rotations, mode_id, next_rotation)
        payload = dict(item.current_size_payload)
        payload.pop(CONTENT_ROTATION_QUARTERS_PAYLOAD_KEY, None)
        if rotations:
            payload[CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY] = rotations
        else:
            payload.pop(CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY, None)
        item.current_size_payload = payload
        self._commit_discrete_undo(before_undo)
        self._session.notify_item_changed(item)
        return True

    def restore_item_size(self, item: CustomLayoutSessionItem) -> bool:
        """Restore one item to authored size/shape while remaining in CUSTOM.

        This is intentionally not ``restore_baseline`` and intentionally never
        enters authored stacking/fit.  Current display ownership and exact X/Y
        are preserved.  Only when the authored rectangle itself exceeds the
        owning display is a uniform emergency reduction admitted.
        """

        if (
            not self._active
            or self._session is None
            or not item.size_reset_capable
            or item.authored_reference_size is None
            or item.current_display_identity not in self._bindings
        ):
            return False
        # Reset is a transaction boundary. Kill any partially-owned child or
        # parent pointer origin before replacing geometry so a later release cannot
        # replay deltas against the newly-authored state.
        self.cancel_child_gesture(item)
        self._resize_origins.pop(item.source_key, None)
        binding = self._bindings[item.current_display_identity]
        authored_width = max(1.0, float(item.authored_reference_size[0]))
        authored_height = max(1.0, float(item.authored_reference_size[1]))
        display_width = max(1.0, float(binding.geometry.width()))
        display_height = max(1.0, float(binding.geometry.height()))
        fit_scale = min(
            1.0,
            display_width / authored_width,
            display_height / authored_height,
        )
        width = max(1, int(round(authored_width * fit_scale)))
        height = max(1, int(round(authored_height * fit_scale)))
        current = item.current_global_rect
        rect = QRect(current.x(), current.y(), width, height)
        descriptor = self._descriptors.get(item.source_key)
        if descriptor is None:
            return False
        before_undo = self._capture_undo(item)

        if descriptor.custom_layout_resize_mode == "visualizer_rect":
            viewport = (
                item.authored_viewport_extent
                or CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
            )
            payload: dict[str, Any] = {
                "width": width,
                "height": height,
            }
            rotations = normalize_content_rotation_by_mode(
                item.current_size_payload.get(
                    CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY, {}
                )
            )
            if rotations:
                payload[CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY] = rotations
            item.restore_authored_size(
                rect,
                size_payload=payload,
                resize_scale=fit_scale,
                viewport_extent=viewport,
            )
            self._visualizer_pixels_per_world[item.source_key] = min(
                float(width) / max(1.0, float(viewport[0])),
                float(height) / max(1.0, float(viewport[1])),
            )
        else:
            payload = scale_quick_size_payload(
                descriptor,
                item.authored_size_payload,
                fit_scale,
            )
            payload.pop("content_extent", None)
            if item.child_geometry_capable:
                # One session method owns the authored child reset transaction:
                # working cache + persisted carrier + transient containment floor
                # are cleared together. Position/display remain untouched by the
                # outer Restore Size contract.
                payload = item.restore_authored_child_geometry(payload)
            item.restore_authored_size(
                rect,
                size_payload=payload,
                resize_scale=fit_scale,
            )

        self._session.notify_item_changed(item)
        self._commit_discrete_undo(before_undo)
        self._log_selected_child_geometry_boundary("restore_projected", item)
        if is_geometry_logging_enabled():
            logger.info(
                "[CUSTOM_LAYOUT] [GEO_CHILD] restore widget=%s parent=%s "
                "child_roles=%s extent=%s fit=%.4f",
                item.source_key.widget_id, rect.getRect(),
                tuple(sorted(item.current_child_sizes)), item.current_content_extent,
                fit_scale,
            )
        logger.info(
            "[CUSTOM_LAYOUT] Restored widget authored size widget=%s display=%s "
            "size=%sx%s emergency_fit=%.4f position_preserved=(%s,%s)",
            item.model_identity,
            item.current_display_identity,
            width,
            height,
            fit_scale,
            current.x(),
            current.y(),
        )
        return True

    def _apply_uniform_scale(
        self,
        item: CustomLayoutSessionItem,
        requested_scale: float,
        anchor_rect: QRect,
    ) -> bool:
        binding = self._bindings[item.current_display_identity]
        if (
            item.content_extent_capable
            and not item.viewport_resize_capable
            and item.current_content_extent is not None
        ):
            # Corners/wheel stay uniform enlarge/shrink for content-extent widgets,
            # but scale the user's current logical content box (which a side drag
            # may have given a non-authored aspect) rather than the authored
            # reference, so a taller/wider box keeps its reflowed content.
            return self._apply_content_extent_uniform_scale(
                item, requested_scale, anchor_rect, binding
            )
        descriptor = self._descriptors[item.source_key]
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
        # The uniform-size baseline is not a source for *discrete* edit state.
        # In particular Restore Size removes a rail override; a subsequent
        # wheel gesture must not resurrect it from a previously saved baseline.
        payload.pop(COLUMN_RAILS_PAYLOAD_KEY, None)
        if item.source_key.widget_id in COLUMN_RAIL_IDS:
            order = normalize_column_rails(
                item.source_key.widget_id,
                item.current_size_payload.get(COLUMN_RAILS_PAYLOAD_KEY),
            )
            if order is not None:
                payload[COLUMN_RAILS_PAYLOAD_KEY] = list(order)
        if item.child_geometry_capable:
            # Baseline payloads are an absolute *size* reference, never a
            # snapshot of the currently edited children. A wheel/corner gesture
            # must project the live child records into the very same payload
            # transaction, including an unsaved Header orientation flip. Do not
            # mutate those records or add a second orientation owner here.
            payload = update_child_geometry_payload(
                payload, item.custom_child_roles, item.current_child_sizes
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
        changed = self._apply_uniform_scale(
            item,
            origin.scale * target / base,
            origin.rect,
        )
        # Aspect-locked corners/drag stay "enlarge/shrink"; snapping only chooses
        # a scale that lands one edge on a nearby peer line, then shows that line.
        return self._apply_uniform_resize_snap(item, origin) or changed

    def _apply_uniform_resize_snap(
        self,
        item: CustomLayoutSessionItem,
        origin: _ResizeOrigin,
    ) -> bool:
        """Snap the just-applied uniform scale to a peer alignment line.

        The uniform apply anchors ``center_x`` at the gesture-start centre and the
        top at the gesture-start top, so a single scale lands one edge on a peer
        line while preserving aspect. Guides are published (or cleared) every
        sample; ``update_resize`` clears them again at release.
        """

        binding = self._bindings[item.current_display_identity]
        free_rect = item.current_global_rect
        center_x_local = (
            float(origin.rect.x())
            + float(origin.rect.width()) / 2.0
            - float(binding.geometry.x())
        )
        top_local = float(origin.rect.y()) - float(binding.geometry.y())
        snap = resolve_uniform_scale_snap(
            float(item.resize_scale),
            center_x=center_x_local,
            top=top_local,
            free_width=float(free_rect.width()),
            free_height=float(free_rect.height()),
            display_size=binding.geometry.size(),
            peer_rects=self._peer_local_rects(item, binding),
        )
        changed = False
        if abs(float(snap.scale) - float(item.resize_scale)) > 1e-6:
            changed = self._apply_uniform_scale(item, float(snap.scale), origin.rect)
        self._publish_move_guides(
            item.current_display_identity,
            SnapResolution(
                rect=QRect(item.current_global_rect),
                vertical_guides=snap.vertical_guides,
                horizontal_guides=snap.horizontal_guides,
            ),
        )
        return changed

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
        # A saturated edge can generate indefinitely many pointer samples with
        # exactly the same admitted rect and viewport. Compare the complete
        # projected state, NOT cursor positions or rounded world extents alone:
        # any genuine geometry/payload change must reach the retained scene.
        # The cached gesture scalar is still maintained on a no-op sample.
        self._visualizer_pixels_per_world[item.source_key] = pixels_per_world
        if (
            rect == item.current_global_rect
            and item.current_viewport_extent == next_extent
            and item.current_size_payload == payload
        ):
            return False
        item.set_geometry(
            rect,
            size_payload=payload,
            viewport_extent=next_extent,
        )
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
        rect = self._snap_resize_edges(
            item,
            binding,
            rect,
            horizontal_edge=edge if edge in {"left", "right"} else None,
            vertical_edge=edge if edge in {"top", "bottom"} else None,
            min_size=minimum,
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
        rect = self._snap_resize_edges(
            item,
            binding,
            rect,
            horizontal_edge=horizontal_edge,
            vertical_edge=vertical_edge,
            min_size=minimum,
        )
        return self._commit_viewport_resize_geometry(
            item,
            origin,
            rect,
            change_width=True,
            change_height=True,
        )

    def _commit_content_extent_resize_geometry(
        self,
        item: CustomLayoutSessionItem,
        origin: _ResizeOrigin,
        rect: QRect,
        *,
        change_width: bool,
        change_height: bool,
    ) -> bool:
        """Commit an ordinary logical content-box resize at constant scale."""

        scale = max(1.0e-6, float(origin.scale))
        box = item.current_content_extent
        if box is None:
            box = (float(rect.width()) / scale, float(rect.height()) / scale)
        next_box = (
            float(rect.width()) / scale if change_width else float(box[0]),
            float(rect.height()) / scale if change_height else float(box[1]),
        )
        payload = dict(item.current_size_payload)
        payload.update(
            width=rect.width(),
            height=rect.height(),
            content_extent=[next_box[0], next_box[1]],
        )
        # Once the moving edge reaches its physical bound, repeated cursor
        # samples must not republish the same outer rect and content payload.
        # Retain the existing gesture origin and let release clear its guides;
        # neither the child minimum nor a display-limited drag adds a cadence.
        if (
            rect == item.current_global_rect
            and item.current_content_extent == next_box
            and item.current_size_payload == payload
        ):
            return False
        item.set_geometry(rect, size_payload=payload, content_extent=next_box)
        return True

    def _resize_content_edge(
        self,
        item: CustomLayoutSessionItem,
        origin: _ResizeOrigin,
        edge: str,
        cursor: QPoint,
    ) -> bool:
        """Resize one axis of an ordinary widget's logical content box.

        A side handle changes the outer rect on its axis at constant uniform
        scale; the new logical box dimension is ``outer_axis / scale`` and the
        untouched axis is preserved exactly. The widget consumes the box to
        reflow (more rows / grid columns / less truncation) rather than
        letterboxing. Python owns all geometry; QML only emitted the edge id.
        """

        binding = self._bindings[item.current_display_identity]
        minimum = quick_custom_content_extent_minimum_size(item)
        rect = self._viewport_resize_rect(
            origin,
            binding,
            minimum,
            cursor,
            horizontal_edge=edge if edge in {"left", "right"} else None,
            vertical_edge=edge if edge in {"top", "bottom"} else None,
        )
        rect = self._snap_resize_edges(
            item,
            binding,
            rect,
            horizontal_edge=edge if edge in {"left", "right"} else None,
            vertical_edge=edge if edge in {"top", "bottom"} else None,
            min_size=minimum,
        )
        return self._commit_content_extent_resize_geometry(
            item,
            origin,
            rect,
            change_width=edge in {"left", "right"},
            change_height=edge in {"top", "bottom"},
        )

    def _resize_content_corner(
        self,
        item: CustomLayoutSessionItem,
        origin: _ResizeOrigin,
        handle: str,
        cursor: QPoint,
    ) -> bool:
        """Reflow both ordinary content axes through a distinct diagonal handle.

        Existing square corner handles intentionally retain uniform whole-widget
        scale.  ``content_*`` handles move the corresponding two outer edges at
        constant scale and therefore adjust the logical content width + height
        together without creating a second sizing authority.
        """

        corner = str(handle).removeprefix("content_")
        horizontal_edge = "left" if corner.endswith("left") else "right"
        vertical_edge = "top" if corner.startswith("top_") else "bottom"
        binding = self._bindings[item.current_display_identity]
        minimum = quick_custom_content_extent_minimum_size(item)
        rect = self._viewport_resize_rect(
            origin,
            binding,
            minimum,
            cursor,
            horizontal_edge=horizontal_edge,
            vertical_edge=vertical_edge,
        )
        rect = self._snap_resize_edges(
            item,
            binding,
            rect,
            horizontal_edge=horizontal_edge,
            vertical_edge=vertical_edge,
            min_size=minimum,
        )
        return self._commit_content_extent_resize_geometry(
            item,
            origin,
            rect,
            change_width=True,
            change_height=True,
        )

    def _apply_content_extent_uniform_scale(
        self,
        item: CustomLayoutSessionItem,
        requested_scale: float,
        anchor_rect: QRect,
        binding: _DisplayBinding,
    ) -> bool:
        """Uniform corner/wheel scale for a content-extent widget.

        Scale is absolute against the current logical content box, so the box's
        reflowed aspect is preserved and only overall size changes. The box value
        itself is carried through unchanged in geometry + payload.
        """

        box = item.current_content_extent
        assert box is not None
        reference_width = max(1.0, float(box[0]))
        reference_height = max(1.0, float(box[1]))
        minimum = quick_custom_minimum_size(item)
        max_scale = min(
            float(binding.geometry.width()) / reference_width,
            float(binding.geometry.height()) / reference_height,
        )
        floor_scale = max(
            CUSTOM_LAYOUT_MIN_RESIZE_SCALE,
            float(minimum.width()) / reference_width,
            float(minimum.height()) / reference_height,
        )
        scale = min(max_scale, max(floor_scale, float(requested_scale)))
        if abs(scale - float(item.resize_scale)) < 1e-6:
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
        geometry = QRect(
            binding.geometry.x() + local.x(),
            binding.geometry.y() + local.y(),
            local.width(),
            local.height(),
        )
        payload = dict(item.current_size_payload)
        payload.update(
            width=local.width(),
            height=local.height(),
            content_extent=[box[0], box[1]],
        )
        item.set_geometry(
            geometry,
            size_payload=payload,
            resize_scale=scale,
            content_extent=box,
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
            rotations = normalize_content_rotation_by_mode(
                payload.get(CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY, {})
            )
            payload.pop(CONTENT_ROTATION_QUARTERS_PAYLOAD_KEY, None)
            if rotations:
                payload[CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY] = rotations
            else:
                payload.pop(CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY, None)
        # Persist the content-extent box only once a side drag has established
        # one (current_content_extent is None until then), so a uniform-only edit
        # never pins a box and the family keeps its config-derived authored size.
        if item.content_extent_capable and item.current_content_extent is not None:
            box = item.current_content_extent
            payload["content_extent"] = [box[0], box[1]]
        else:
            payload.pop("content_extent", None)
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
        """Return the explicit reason a Save must retain replacement semantics.

        Disabling an already-retained *ordinary* widget is not generation
        topology: the retained presenter and neutral service owner can retire that
        exact family in place. New admissions, Visualizer presence changes, or a
        disable combined with routing changes still use the fenced replacement
        path because those require construction/owner transfer rather than simple
        retirement.
        """

        session = self._session
        if session is None:
            raise RuntimeError("CUSTOM live-commit admission requires a session")
        items = session.items()
        presence_changed = any(
            item.removed or not item.current_enabled or not item.baseline_enabled
            for item in items
        )
        if presence_changed and not self._presence_change_live_commit_is_coherent():
            return "family_presence_changed"
        for item in items:
            if item.current_display_identity != item.source_key.display_identity:
                return "display_transfer"
            if item.current_monitor_route != item.source_monitor_route:
                return "monitor_route_changed"
        return None

    def _presence_change_live_commit_is_coherent(self) -> bool:
        """Return whether this Save can reconcile removals in-generation.

        Edit-mode removal is a retirement edge, not generation topology. Ordinary
        retained families retire through their binder/service owner; the single
        Visualizer retires through the existing manager-owned Visualizer lifecycle
        seam. New admissions remain outside this narrow path and may still require
        an explicit construction/reconciliation owner.
        """

        session = self._session
        if session is None:
            return False
        changed = False
        for item in session.items():
            presence_changed = (
                item.removed
                or not item.current_enabled
                or not item.baseline_enabled
            )
            if not presence_changed:
                # An unrelated retained item may have completed its own coherent
                # display/route transfer in the same Edit transaction.  Presence
                # retirement coherence is scoped to the family being retired; the
                # transfer is validated independently by the normal topology pass.
                continue
            if item.current_display_identity != item.source_key.display_identity:
                return False
            if item.current_monitor_route != item.source_monitor_route:
                return False
            changed = True
            # This retained-edit seam owns retirements only. A previously absent
            # family needs its normal construction/admission authority instead.
            if not item.baseline_enabled:
                return False
            if item.current_enabled and not item.removed:
                return False
            if item.model_identity == "spotify_visualizer":
                if self._visualizer_presence_commit is None:
                    return False
        return changed

    def _ordinary_disable_only_live_commit_is_coherent(self) -> bool:
        """Return whether presence changes are retire-only ordinary families.

        The runtime already owns exact mid-generation retirement for ordinary
        retained families. Keep this deliberately narrower than generic topology
        reconciliation: no new admissions, no Visualizer presence mutation, and
        no simultaneous display/monitor-route changes.
        """

        session = self._session
        if session is None:
            return False
        changed = False
        for item in session.items():
            if item.current_display_identity != item.source_key.display_identity:
                return False
            if item.current_monitor_route != item.source_monitor_route:
                return False
            presence_changed = (
                item.removed
                or not item.current_enabled
                or not item.baseline_enabled
            )
            if not presence_changed:
                continue
            changed = True
            if not item.baseline_enabled:
                return False
            if item.model_identity == "spotify_visualizer":
                return False
            if item.current_enabled and not item.removed:
                return False
        return changed

    def _cross_display_transfer_is_coherent(self) -> bool:
        """Validate exact moved item identity before committing its target owners.

        The Visualizer requires its runtime/unit transfer already complete.
        Ordinary items require the source family and target retained root to be
        the same object; promotion moves their existing binding/service records.
        """

        session = self._session
        if session is None:
            return False
        owner, unit = self._visualizer_provider()
        for item in session.items():
            if item.current_display_identity == item.source_key.display_identity:
                continue
            if item.model_identity != "spotify_visualizer":
                source = self._bindings.get(item.source_key.display_identity)
                target = self._bindings.get(item.current_display_identity)
                if source is None or target is None:
                    return False
                family = source.unit.presenter.presentation_for_widget_id(item.model_identity)
                retained = target.unit.runtime.scene_controller.ordinary_widget_host.presentation_for_model_identity(item.model_identity)
                if family is None or retained is None or family.item is not retained.item:
                    return False
                continue
            if owner is None or unit is None:
                return False
            target_binding = self._bindings.get(item.current_display_identity)
            if target_binding is None or target_binding.unit is not unit:
                return False
        return True

    def _promote_live_geometry_commit(
        self,
        widgets: Mapping[str, object] | None = None,
    ) -> None:
        """Promote retained CUSTOM state before the edit overlay is cleared.

        ``widgets`` is the just-persisted widget map.  When supplied, the
        manager-owned retained configuration snapshot is advanced only after
        every live geometry/presence mutation succeeded.  This keeps the
        retained generation coherent without requiring a replacement.
        """

        session = self._session
        if session is None:
            raise RetainedRuntimeIncoherenceError("CUSTOM live geometry promotion requires a session")
        owner, visualizer_unit = self._visualizer_provider()
        for item in session.items():
            if item.removed or not item.current_enabled:
                if item.model_identity == "spotify_visualizer":
                    reconcile = self._visualizer_presence_commit
                    if reconcile is None or not bool(reconcile(False)):
                        raise RetainedRuntimeIncoherenceError(
                            "CUSTOM live Visualizer retirement was not confirmed"
                        )
                    logger.info(
                        "[CUSTOM_LAYOUT] Save live-retired Visualizer owner "
                        "without generation reconciliation"
                    )
                    continue
                source = self._bindings.get(item.source_key.display_identity)
                if source is None:
                    raise RetainedRuntimeIncoherenceError(
                        "CUSTOM live retirement has no source display binding: "
                        f"{item.source_key.display_identity!r}"
                    )
                if not source.unit.presenter.retire_live_custom_layout_item(
                    item.model_identity
                ):
                    raise RetainedRuntimeIncoherenceError(
                        "CUSTOM live retirement lost retained family: "
                        f"{item.model_identity!r}"
                    )
                logger.info(
                    "[CUSTOM_LAYOUT] Save live-retired disabled ordinary family "
                    "widget=%s display=%s without generation reconciliation",
                    item.model_identity,
                    item.source_key.display_identity,
                )
                continue

            binding = self._bindings.get(item.current_display_identity)
            if binding is None:
                raise RetainedRuntimeIncoherenceError(
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
                    raise RetainedRuntimeIncoherenceError("CUSTOM live geometry has no visualizer owner")
                extent = item.current_viewport_extent
                if extent is None:
                    raise RetainedRuntimeIncoherenceError("CUSTOM live visualizer geometry has no viewport extent")
                owner.commit_live_custom_layout(
                    local_rect=(local.x, local.y, local.width, local.height),
                    viewport_extent=extent,
                    content_rotation_by_mode=item.current_size_payload.get(
                        CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY, {}
                    ),
                )
                continue
            if item.current_display_identity != item.source_key.display_identity:
                source = self._bindings[item.source_key.display_identity]
                source.unit.presenter.transfer_live_custom_layout_item_to(
                    item.model_identity, binding.unit.presenter,
                )
            binding.unit.presenter.commit_live_custom_layout_item(
                item.model_identity,
                local,
                item.current_size_payload,
            )

        if widgets is not None:
            commit = self._live_config_commit
            if commit is None:
                raise RetainedRuntimeIncoherenceError(
                    "CUSTOM live commit has no retained config snapshot owner"
                )
            commit(widgets)

    def _finish(self) -> tuple[str, ...]:
        """Close one shared CUSTOM session on every display, even if one is corrupt."""

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
        corruption: list[str] = []
        bindings = tuple(self._bindings.values())
        coordinator = self._coordinator
        # Retire the cross-display listener before clearing per-scene edit state.
        # Cleanup must never generate another transfer while displays are closing.
        self._coordinator = None
        if coordinator is not None:
            try:
                coordinator.retire()
            except Exception as exc:
                corruption.append(f"coordinator:{type(exc).__name__}")
                logger.exception("[CUSTOM_LAYOUT] Coordinator retirement failed")
        try:
            for binding in bindings:
                try:
                    damaged = binding.unit.runtime.scene_controller.clear_custom_layout_session()
                    corruption.extend(
                        f"{binding.identity}:{entry}" for entry in tuple(damaged or ())
                    )
                except Exception as exc:
                    corruption.append(f"{binding.identity}:scene_cleanup:{type(exc).__name__}")
                    logger.exception(
                        "[CUSTOM_LAYOUT] Display cleanup failed identity=%s; "
                        "continuing shared session retirement",
                        binding.identity,
                    )
        finally:
            # Selection owns transient child-edit retirement by stable object
            # identity. Close that state before dropping the session/listener so
            # no stale floor or interrupted pointer origin can survive teardown.
            session = self._session
            if session is not None:
                self._on_child_edit_selection_changed(None)
                session.unsubscribe_selection(self._on_child_edit_selection_changed)
            # Shared Python ownership must close exactly once even when one display's
            # retained C++ graph is already damaged. This prevents the half-Edit
            # state observed when display 0 threw before display 1 was cleared.
            self._session = None
            self._bindings = {}
            self._descriptors = {}
            self._resize_origins = {}
            self._child_resize_origins = {}
            self._child_move_origins = {}
            self._undo_history.clear()
            self._undo_pending = None
            self._selected_child_edit_item = None
            self._visualizer_pixels_per_world.clear()
            self._visualizer_move_transfer_latch.clear()
            self._active = False
        return tuple(dict.fromkeys(corruption))

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
