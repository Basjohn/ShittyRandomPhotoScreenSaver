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
from typing import Any

from core.logging.logger import get_logger
from rendering.widget_descriptors import is_global_custom_layout_mode_selected
from rendering.widget_stacking import (
    DisplayStackObstacle,
    DisplayStackParticipant,
    build_display_stack_plan,
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
        self._stacking_enabled = bool(global_config.get("stacking_enabled", False))
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

            # QML reports size only; Python resolves + assigns the outer rect. A
            # committed rect (CUSTOM / Clock per-variant) wins and suppresses this.
            connect_overlay_preferred_size(overlay.item, binding)
            self._geometry_bindings.append((widget_id, binding))

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
            values = self._widgets_config.get(widget_id, {})
            if not isinstance(values, Mapping):
                values = {}
            binding = next(
                (bound for bound_id, bound in self._geometry_bindings if bound_id == widget_id),
                None,
            )
            margin = 30
            if binding is not None:
                margin = int(round(float(binding.policy.margin)))
            participants.append(
                DisplayStackParticipant(
                    key=widget_id,
                    position_key=str(
                        values.get(
                            "position",
                            binding.policy.anchor.value if binding is not None else "top_right",
                        )
                    ),
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
        plan = build_display_stack_plan(
            participants,
            obstacles=self._external_stack_obstacles,
            container_width=max(1, int(round(self._display_bounds.width))),
            container_height=max(1, int(round(self._display_bounds.height))),
            spacing=10,
        )
        self._layout_reflow_active = True
        try:
            for participant in participants:
                base = self._base_geometries.get(participant.key)
                sink = self._geometry_sinks.get(participant.key)
                placement = plan.placements.get(participant.key)
                if base is None or sink is None or placement is None:
                    continue
                sink(
                    OverlayWidgetGeometry(
                        self._display_bounds.x + float(placement.desired_x),
                        self._display_bounds.y + float(placement.desired_y),
                        base.width,
                        base.height,
                    )
                )
        finally:
            self._layout_reflow_active = False
        if not plan.all_fit:
            logger.warning(
                "[WIDGET_STACKING] Display is overfull; unresolved=%s",
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
