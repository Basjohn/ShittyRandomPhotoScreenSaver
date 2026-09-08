"""Thin per-display Quick presenter: family + geometry assembly (H).

This is the small destination-side assembly that binds one display generation's
ordinary families into the retained scene and places them under the accepted
content-driven geometry model (option A). It is deliberately thin: it owns no
provider/model/cadence lifetime (that stays with the display's single
``WidgetRuntimeManager`` and the family modules) and no window/scene lifecycle
(that stays with :class:`~rendering.quick.runtime.QuickDisplayRuntime`).

It connects the already-built pieces:

- the seven-family :class:`~rendering.quick.widgets.family_binder.OrdinaryFamilyPresentationBinder`
  builds the retained ``Retained*Presentation`` items into the runtime's host and
  owns their neutral services through the one manager;
- an :class:`~rendering.quick.widgets.geometry_resolver.OverlayGeometryBinding`
  per built family drives its outer rectangle from the family's declared
  preferred content size (QML reports size only; Python owns anchor/clamp/outer
  rect). Content anchoring is the **default placement only**: a CUSTOM committed
  rect or a family-owned per-variant committed rect, supplied through
  ``committed_rect_resolver``, overrides the binding completely and suppresses
  re-anchoring.

Image, transition and visualizer routing stay on the runtime's own narrow APIs
and are driven by the display orchestrator (DisplayManager), not duplicated here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from time import perf_counter
from typing import Any

from core.logging.logger import get_logger
from core.settings.default_contract import require_canonical_default
from rendering.widget_descriptors import (
    is_global_custom_layout_mode_selected,
    get_widget_runtime_descriptor,
)
from rendering.quick.custom_layout_size import is_uniform_transform_resize_mode
from rendering.widget_stacking import (
    DisplayStackObstacle,
    DisplayStackParticipant,
    build_display_auto_scale_plan,
)

from .widgets.family_binder import (
    OrdinaryFamilyAdapter,
    OrdinaryFamilyPresentationBinder,
)
from .widgets.geometry_resolver import (
    OverlayGeometryBinding,
    connect_overlay_preferred_size,
    resolve_overlay_geometry_policy,
)
from .widgets.host import OverlayWidgetGeometry

logger = get_logger(__name__)


class QuickDisplayPresenter:
    """Bind + place one display generation's ordinary families under option A."""

    def __init__(
        self,
        runtime: Any,
        *,
        adapters: Sequence[OrdinaryFamilyAdapter] | None = None,
    ) -> None:
        self._runtime = runtime
        self._adapters = adapters
        self._binder: OrdinaryFamilyPresentationBinder | None = None
        self._geometry_bindings: list[tuple[str, OverlayGeometryBinding]] = []
        self._display_bounds: OverlayWidgetGeometry | None = None
        self._widgets_config: Mapping[str, object] = {}
        self._stacking_enabled = False
        self._authored_layout_enabled = True
        self._stack_order: list[str] = []
        self._base_geometries: dict[str, OverlayWidgetGeometry] = {}
        self._geometry_sinks: dict[str, Callable[[OverlayWidgetGeometry], None]] = {}
        self._custom_widget_ids: set[str] = set()
        self._external_stack_obstacles: tuple[DisplayStackObstacle, ...] = ()
        self._fixed_stack_widget_ids: set[str] = set()
        self._layout_observer: Callable[[str, OverlayWidgetGeometry], None] | None = None
        self._layout_suspended = 0
        self._layout_reflow_active = False
        self._last_stack_inputs = None
        self._last_stack_result = None
        self._bound_once = False
        self._retired = False

    @property
    def is_retired(self) -> bool:
        return self._retired

    @property
    def bound_widget_ids(self) -> tuple[str, ...]:
        return tuple(widget_id for widget_id, _binding in self._geometry_bindings)

    @property
    def authored_layout_enabled(self) -> bool:
        """Whether ordinary authored stacking/adjacency may currently project."""

        return bool(self._authored_layout_enabled and not self._retired)

    def geometry_for(self, widget_id: str) -> OverlayWidgetGeometry | None:
        """Return the current Python-authored retained outer rectangle.

        Family-owned dynamic geometry (Clock mode variants) can legitimately
        advance after the initial preferred-size binding.  Read the retained
        presentation's explicit geometry when it exposes one, then fall back to
        the binding cache for ordinary static families.
        """

        presentation = self.presentation_for_widget_id(widget_id)
        geometry = getattr(presentation, "geometry", None)
        if isinstance(geometry, OverlayWidgetGeometry):
            return geometry
        item = getattr(presentation, "item", None)
        if item is not None:
            # Binding geometry is the authored baseline. Stacking/auto-scale
            # project through the retained sink, so Edit must capture that
            # actual outer footprint rather than restoring the binding cache.
            return OverlayWidgetGeometry(item.x(), item.y(), item.width(), item.height())
        for bound_id, binding in self._geometry_bindings:
            if bound_id == widget_id:
                return binding.current_geometry
        return None

    def authored_geometry_for(self, widget_id: str) -> OverlayWidgetGeometry | None:
        """Return the unstacked authored rectangle for one ordinary widget."""

        return self._base_geometries.get(str(widget_id))

    def presentation_for_widget_id(self, widget_id: str) -> object | None:
        """Return one retained family presentation without exposing the host."""

        binder = self._binder
        if binder is None or self._retired:
            return None
        return binder.presentation_for_widget_id(widget_id)

    def set_startup_reveal_opacity(self, opacity: float) -> tuple[str, ...]:
        """Project/store the independent startup gate at the retained host boundary.

        Family lifecycle fades continue to own ``fadeOpacity``. The host stores
        ``startupRevealOpacity`` so both existing roots and any root constructed
        later in this generation inherit the same gate before entering the scene.
        """

        if self._retired:
            return ()
        host = self._runtime.scene_controller.ordinary_widget_host
        try:
            return host.set_startup_reveal_opacity(float(opacity))
        except (RuntimeError, TypeError, ValueError):
            logger.warning(
                "[STARTUP_REVEAL] Failed to project ordinary startup gate",
                exc_info=True,
            )
            return ()

    def bind_families(
        self,
        *,
        widgets_config: Mapping[str, object] | None,
        display_bounds: OverlayWidgetGeometry,
        shadow_values: Mapping[str, object] | None = None,
        thread_manager: Any | None = None,
        committed_rect_resolver: Callable[[str], OverlayWidgetGeometry | None]
        | None = None,
        committed_variant_state_resolver: Callable[
            [str, str], tuple[OverlayWidgetGeometry, Mapping[str, object]] | None
        ]
        | None = None,
    ) -> tuple[str, ...]:
        """Build and place every admitted family for this display generation."""

        if self._retired:
            raise RuntimeError("cannot bind a retired display presenter")
        if self._bound_once:
            raise RuntimeError("display presenter already bound this generation")
        self._bound_once = True
        self._display_bounds = display_bounds

        config: Mapping[str, object] = (
            widgets_config if isinstance(widgets_config, Mapping) else {}
        )
        self._widgets_config = config
        global_config = config.get("global", {})
        if not isinstance(global_config, Mapping):
            global_config = {}
        stacking_default = bool(
            require_canonical_default("widgets.global.stacking_enabled")
        )
        self._stacking_enabled = bool(
            global_config.get("stacking_enabled", stacking_default)
        )
        self._authored_layout_enabled = not is_global_custom_layout_mode_selected(
            config
        )
        resolve_committed = committed_rect_resolver or (lambda _widget_id: None)
        resolve_variant_state = committed_variant_state_resolver or (
            lambda _widget_id, _variant: None
        )
        scene_controller = self._runtime.scene_controller
        host = scene_controller.ordinary_widget_host
        manager = self._runtime.widget_runtime_manager
        display_signature = str(self._runtime.display_identity.screen_key)

        # Cache each widget's resolved policy so the initial geometry passed to
        # the family constructor and the live binding share one policy (and one
        # committed-rect decision) per widget.
        policies = {}

        def initial_geometry(widget_id: str) -> OverlayWidgetGeometry:
            policy = resolve_overlay_geometry_policy(
                widget_id, config, committed_rect=resolve_committed(widget_id)
            )
            policies[widget_id] = policy
            if policy.has_committed_rect:
                return policy.committed_rect  # type: ignore[return-value]
            # Provisional; the content-size binding corrects it immediately from
            # the family's real declared preferred size on connection below.
            return policy.resolve((100.0, 100.0), display_bounds)

        self._binder = OrdinaryFamilyPresentationBinder(
            host=host,
            runtime_manager=manager,
            geometry_resolver=initial_geometry,
            display_bounds=display_bounds,
            display_identity=display_signature,
            screen_index=self._runtime.screen_index,
            shadow_values=shadow_values,
            thread_manager=thread_manager,
            runtime_generation=self._runtime.runtime_generation,
            adapters=self._adapters,
        )
        built = self._binder.bind(config)

        for widget_id in built:
            overlay = host.presentation_for_model_identity(widget_id)
            if overlay is None:
                logger.debug(
                    "[DISPLAY_PRESENTER] No retained overlay for %s; no geometry binding",
                    widget_id,
                )
                continue
            policy = policies.get(widget_id)
            if policy is None:
                policy = resolve_overlay_geometry_policy(
                    widget_id, config, committed_rect=resolve_committed(widget_id)
                )
            presentation = self.presentation_for_widget_id(widget_id)
            family_geometry_sink = getattr(presentation, "set_geometry", None)
            geometry_sink = (
                family_geometry_sink
                if callable(family_geometry_sink)
                else overlay.set_geometry
            )
            self._geometry_sinks[widget_id] = geometry_sink
            self._stack_order.append(widget_id)

            values = config.get(widget_id, {})
            if not isinstance(values, Mapping):
                values = {}
            is_custom = str(values.get("position", "")).strip().lower() == "custom"
            if is_custom or policy.has_committed_rect:
                self._custom_widget_ids.add(widget_id)

            binding = OverlayGeometryBinding(
                policy=policy,
                display_bounds=display_bounds,
                geometry_sink=lambda geometry, wid=widget_id: self._apply_binding_geometry(
                    wid, geometry
                ),
            )

            # Clock keeps independent committed analogue/digital rect + font-scale
            # states. Seed both before interaction so switching mode restores an
            # already-authored target variant instead of deriving over it.
            seed_variant = getattr(presentation, "seed_geometry_variant", None)
            if callable(seed_variant):
                for variant in ("digital", "analog"):
                    state = resolve_variant_state(widget_id, variant)
                    if state is None:
                        continue
                    variant_geometry, size_payload = state
                    seed_variant(variant, variant_geometry, size_payload)

            # An already committed Clock needs its variant switch to update the
            # retained binding. Authored clocks retain their anchor policy until
            # CUSTOM is explicitly promoted at Save.
            set_commit_handler = getattr(
                presentation, "set_geometry_commit_handler", None
            )
            if callable(set_commit_handler) and policy.has_committed_rect:
                set_commit_handler(binding.set_committed_rect)

            # Register the binding BEFORE connecting the preferred-size signal.
            # connect_overlay_preferred_size drives an initial content-size update
            # synchronously, and on a retained-runtime recreation the QML item
            # already has a size -- so the geometry sink runs immediately and, for a
            # stacking widget, triggers _reflow_non_custom_layout. If the binding
            # were appended afterwards, that reflow would see this stack participant
            # with a base geometry but no resolved binding and raise. The final
            # reflow below still runs once with the complete participant set.
            self._geometry_bindings.append((widget_id, binding))

            # QML reports size only; Python resolves + assigns the outer rect. A
            # committed rect (CUSTOM / Clock per-variant) wins and suppresses this.
            connect_overlay_preferred_size(overlay.item, binding)

        if self._stacking_enabled and self._authored_layout_enabled:
            self._reflow_non_custom_layout()
        return built

    def set_authored_layout_enabled(
        self,
        enabled: bool,
        *,
        restore_base: bool = True,
        reflow: bool = True,
    ) -> bool:
        """Enable/disable the whole authored-layout subsystem at an event edge.

        CUSTOM is global.  Entering the retained edit transaction disables both
        stacking and ordinary relationship callbacks for this presenter, and a
        persisted/effective CUSTOM route starts the generation disabled.  No
        timer or cadence owner is involved.

        When disabling from authored mode, optionally restore each retained
        ordinary family to its unstacked base rectangle before CUSTOM captures
        the working session.  Re-enabling after Cancel performs one bounded
        deterministic reflow.
        """

        if self._retired:
            return False
        target = bool(enabled)
        changed = target != self._authored_layout_enabled
        self._authored_layout_enabled = target

        if not target:
            if restore_base:
                self._layout_suspended += 1
                try:
                    for widget_id in self._stack_order:
                        geometry = self._base_geometries.get(widget_id)
                        sink = self._geometry_sinks.get(widget_id)
                        if geometry is not None and sink is not None:
                            sink(geometry)
                finally:
                    self._layout_suspended = max(0, self._layout_suspended - 1)
            return changed

        if reflow and self._stacking_enabled:
            self._reflow_non_custom_layout()
        return changed

    def transfer_live_custom_layout_item_to(self, widget_id: str, target: "QuickDisplayPresenter") -> None:
        """Complete an already-rendered ordinary transfer without rebuilding providers.

        The Edit coordinator moved the retained root/shadow during the gesture.
        Save moves the family/binding/service records before promoting target geometry.
        Cancel before Save never enters this path.
        """
        if self._retired or target._retired or self._binder is None or target._binder is None:
            raise RuntimeError("ordinary transfer requires two live presenters")
        family = self.presentation_for_widget_id(widget_id)
        target_host = target._runtime.scene_controller.ordinary_widget_host
        retained = target_host.presentation_for_model_identity(widget_id)
        binding = next((bound for key, bound in self._geometry_bindings if key == widget_id), None)
        if family is None or binding is None or widget_id not in self._geometry_sinks:
            raise RuntimeError(f"ordinary transfer source is incomplete: {widget_id}")
        if retained is None or retained.item is not family.item:
            raise RuntimeError(f"ordinary transfer lost exact retained item: {widget_id}")
        if target.presentation_for_widget_id(widget_id) is not None or widget_id in target._geometry_sinks:
            raise RuntimeError(f"ordinary transfer target already owns binding: {widget_id}")
        if target._display_bounds is None:
            raise RuntimeError("ordinary transfer target lacks bounds")
        self._binder.transfer_presentation_to(widget_id, target._binder)
        self._geometry_bindings.remove((widget_id, binding))
        target._geometry_bindings.append((widget_id, binding))
        target._geometry_sinks[widget_id] = self._geometry_sinks.pop(widget_id)
        self._stack_order.remove(widget_id)
        target._stack_order.append(widget_id)
        base = self._base_geometries.pop(widget_id, None)
        if base is not None:
            target._base_geometries[widget_id] = base
        self._custom_widget_ids.discard(widget_id)
        target._custom_widget_ids.add(widget_id)
        binding.retarget(target._display_bounds,
            lambda geometry: target._apply_binding_geometry(widget_id, geometry))
        set_context = getattr(family, "set_display_context", None)
        if callable(set_context):
            set_context(str(target._runtime.display_identity.screen_key), target._display_bounds)
        self._last_stack_inputs = target._last_stack_inputs = None
        self._last_stack_result = target._last_stack_result = None

    def commit_live_custom_layout_item(
        self,
        widget_id: str,
        geometry: OverlayWidgetGeometry,
        size_payload: Mapping[str, object],
    ) -> None:
        """Promote one retained geometry-only CUSTOM edit into its binding.

        The edit overlay applies pixels directly while active.  Its existing
        preferred-size binding must receive the same committed rectangle before
        CUSTOM ends, otherwise a later QML size signal can replay the pre-edit
        policy rectangle over the retained item.
        """

        if self._retired:
            raise RuntimeError("cannot commit CUSTOM layout on a retired presenter")
        identity = str(widget_id or "").strip()
        binding = next(
            (
                candidate
                for candidate_id, candidate in self._geometry_bindings
                if candidate_id == identity
            ),
            None,
        )
        if binding is None:
            raise RuntimeError(f"CUSTOM layout has no retained binding: {identity!r}")
        retained = self._runtime.scene_controller.ordinary_widget_host.presentation_for_model_identity(
            identity
        )
        apply_payload = (
            None
            if retained is None
            else retained.apply_custom_layout_size_payload
        )
        if not callable(apply_payload):
            raise RuntimeError(f"CUSTOM layout has no retained payload owner: {identity!r}")
        family = self.presentation_for_widget_id(identity)
        set_commit_handler = getattr(family, "set_geometry_commit_handler", None)
        if callable(set_commit_handler):
            set_commit_handler(binding.set_committed_rect)
        apply_payload(dict(size_payload))
        self._custom_widget_ids.add(identity)
        binding.set_committed_rect(geometry)

    def set_layout_observer(
        self, observer: Callable[[str, OverlayWidgetGeometry], None] | None
    ) -> None:
        """Install one generation-local event observer for authored geometry changes."""

        self._layout_observer = observer if callable(observer) else None

    def set_external_stack_obstacles(
        self,
        obstacles: Sequence[DisplayStackObstacle] | None,
        *,
        fixed_widget_ids: Sequence[str] | None = None,
        reflow: bool = True,
    ) -> None:
        """Replace fixed ordinary-layout obstacles and reflow once.

        This is a presentation-only seam for stronger ordinary relationships
        such as the non-CUSTOM Media+Visualizer block. CUSTOM items are never
        represented here. There is no timer/poller; callers update the snapshot
        only when the authored layout relationship itself changes.
        """

        if self._retired:
            return
        self._external_stack_obstacles = tuple(obstacles or ())
        self._fixed_stack_widget_ids = {str(value) for value in (fixed_widget_ids or ())}
        if not reflow or not self._authored_layout_enabled:
            return
        for widget_id in self._fixed_stack_widget_ids:
            if widget_id in self._custom_widget_ids:
                continue
            base = self._base_geometries.get(widget_id)
            sink = self._geometry_sinks.get(widget_id)
            if base is not None and sink is not None:
                sink(base)
        if self._stacking_enabled:
            self._reflow_non_custom_layout()

    def _apply_binding_geometry(
        self, widget_id: str, geometry: OverlayWidgetGeometry
    ) -> None:
        """Record one binding's authored rect, then project ordinary stacking."""

        if self._retired:
            return
        self._base_geometries[widget_id] = geometry
        observer = self._layout_observer if self._authored_layout_enabled else None
        if observer is not None:
            try:
                observer(widget_id, geometry)
            except Exception:
                logger.warning(
                    "[DISPLAY_PRESENTER] Authored-layout observer failed for %s",
                    widget_id,
                    exc_info=True,
                )
        sink = self._geometry_sinks.get(widget_id)
        if sink is None:
            return
        if (
            widget_id in self._custom_widget_ids
            or widget_id in self._fixed_stack_widget_ids
            or not self._stacking_enabled
            or not self._authored_layout_enabled
        ):
            sink(geometry)
            if (
                self._authored_layout_enabled
                and self._stacking_enabled
                and widget_id in self._fixed_stack_widget_ids
                and self._layout_suspended == 0
            ):
                self._reflow_non_custom_layout()
            return
        if self._layout_suspended > 0 or self._layout_reflow_active:
            return
        self._reflow_non_custom_layout()

    def _reflow_non_custom_layout(self) -> None:
        """Run one deterministic display-wide ordinary collision pass.

        CUSTOM widgets are deliberately absent from both participants and
        obstacles. The pass is event-driven by preferred-size/topology/layout
        relationship changes and owns no cadence.
        """

        if (
            self._retired
            or not self._stacking_enabled
            or not self._authored_layout_enabled
            or self._display_bounds is None
            or self._layout_reflow_active
        ):
            return
        participants: list[DisplayStackParticipant] = []
        for order, widget_id in enumerate(self._stack_order):
            if (
                widget_id in self._custom_widget_ids
                or widget_id in self._fixed_stack_widget_ids
            ):
                continue
            geometry = self._base_geometries.get(widget_id)
            if geometry is None:
                continue
            binding = next(
                (bound for bound_id, bound in self._geometry_bindings if bound_id == widget_id),
                None,
            )
            if binding is None:
                raise RuntimeError(
                    f"stack participant lacks resolved geometry policy: {widget_id}"
                )
            margin = int(round(float(binding.policy.margin)))
            participants.append(
                DisplayStackParticipant(
                    key=widget_id,
                    position_key=binding.policy.anchor.value,
                    base_x=int(round(geometry.x - self._display_bounds.x)),
                    base_y=int(round(geometry.y - self._display_bounds.y)),
                    width=max(1, int(round(geometry.width))),
                    height=max(1, int(round(geometry.height))),
                    order=order,
                    margin=max(0, margin),
                )
            )

        if not participants:
            return
        eligible = []
        for participant in participants:
            descriptor = get_widget_runtime_descriptor(participant.key)
            if descriptor is not None and is_uniform_transform_resize_mode(
                descriptor.custom_layout_resize_mode
            ):
                eligible.append(participant.key)
        width = max(1, int(round(self._display_bounds.width)))
        height = max(1, int(round(self._display_bounds.height)))
        inputs = (tuple(participants), tuple(eligible), self._external_stack_obstacles, width, height)
        changed = inputs != self._last_stack_inputs
        if changed:
            started = perf_counter()
            result = build_display_auto_scale_plan(
                participants, eligible_keys=eligible, obstacles=self._external_stack_obstacles,
                container_width=width, container_height=height, spacing=10,
            )
            self._last_stack_inputs, self._last_stack_result = inputs, result
            logger.debug(
                "[WIDGET_STACKING] Solve bounds=%sx%s elapsed_ms=%.2f participants=%s obstacles=%s",
                width, height, (perf_counter() - started) * 1000.0,
                participants, self._external_stack_obstacles,
            )
        plan, scales = self._last_stack_result
        self._layout_reflow_active = True
        try:
            for participant in participants:
                base = self._base_geometries.get(participant.key)
                sink = self._geometry_sinks.get(participant.key)
                placement = plan.placements.get(participant.key)
                if base is None or sink is None or placement is None:
                    continue
                scale = scales[participant.key]
                width = base.width if scale == 1.0 else float(max(1, round(participant.width * scale)))
                height = base.height if scale == 1.0 else float(max(1, round(participant.height * scale)))
                geometry = OverlayWidgetGeometry(
                    self._display_bounds.x + float(placement.desired_x),
                    self._display_bounds.y + float(placement.desired_y), width, height,
                )
                if geometry != self.geometry_for(participant.key):
                    sink(geometry)
        finally:
            self._layout_reflow_active = False
        if changed and any(scale < 1.0 for scale in scales.values()):
            logger.debug("[WIDGET_STACKING] Auto-fit accepted scales=%s", scales)
        if changed and not plan.all_fit:
            logger.warning(
                "[WIDGET_STACKING] Display has no complete fit at or above the whole-card floor; unresolved=%s",
                ",".join(plan.unresolved),
            )

    def set_display_bounds(self, display_bounds: OverlayWidgetGeometry) -> None:
        """Re-anchor every content-anchored family for a new display rectangle.

        A committed-rect family is unaffected (its geometry is authoritative).
        """

        if self._retired:
            return
        self._display_bounds = display_bounds
        self._layout_suspended += 1
        try:
            for _widget_id, binding in self._geometry_bindings:
                binding.set_display_bounds(display_bounds)
        finally:
            self._layout_suspended = max(0, self._layout_suspended - 1)
        if self._stacking_enabled and self._authored_layout_enabled:
            self._reflow_non_custom_layout()

    def retire(self) -> None:
        """Retire every placed family exactly once (terminal for this generation)."""

        if self._retired:
            return
        self._retired = True
        for _widget_id, binding in self._geometry_bindings:
            binding.retire()
        self._geometry_bindings = []
        self._widgets_config = {}
        self._authored_layout_enabled = False
        self._stack_order = []
        self._base_geometries = {}
        self._last_stack_inputs = None
        self._last_stack_result = None
        self._geometry_sinks = {}
        self._custom_widget_ids = set()
        self._external_stack_obstacles = ()
        self._fixed_stack_widget_ids = set()
        self._layout_observer = None
        binder = self._binder
        self._binder = None
        if binder is not None:
            binder.retire_all()


__all__ = ["QuickDisplayPresenter"]
