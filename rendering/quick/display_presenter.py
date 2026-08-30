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
        self._bound_once = False
        self._retired = False

    @property
    def is_retired(self) -> bool:
        return self._retired

    @property
    def bound_widget_ids(self) -> tuple[str, ...]:
        return tuple(widget_id for widget_id, _binding in self._geometry_bindings)

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

    def presentation_for_widget_id(self, widget_id: str) -> object | None:
        """Return one retained family presentation without exposing the host."""

        binder = self._binder
        if binder is None or self._retired:
            return None
        return binder.presentation_for_widget_id(widget_id)

    def set_family_fade_opacity(self, opacity: float) -> tuple[str, ...]:
        """Project one coordinated startup opacity onto every retained family.

        This is intentionally a presentation-only fan-out.  It owns no timing
        and creates no per-widget animation; the generation-scoped startup
        reveal coordinator supplies the single scalar.
        """

        if self._retired:
            return ()
        changed: list[str] = []
        for widget_id in self.bound_widget_ids:
            presentation = self.presentation_for_widget_id(widget_id)
            setter = getattr(presentation, "set_fade_opacity", None)
            if not callable(setter):
                continue
            try:
                setter(float(opacity))
            except (RuntimeError, TypeError, ValueError):
                logger.warning(
                    "[STARTUP_REVEAL] Failed to set family opacity widget=%s",
                    widget_id,
                    exc_info=True,
                )
                continue
            changed.append(widget_id)
        return tuple(changed)

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
        resolve_committed = committed_rect_resolver or (lambda _widget_id: None)
        resolve_variant_state = committed_variant_state_resolver or (
            lambda _widget_id, _variant: None
        )
        host = self._runtime.scene_controller.ordinary_widget_host
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
            binding = OverlayGeometryBinding(
                policy=policy,
                display_bounds=display_bounds,
                geometry_sink=geometry_sink,
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

            # For an active committed CUSTOM Clock, dynamic mode switching must
            # replace this binding's committed rect as well as the pixels. That
            # keeps later preferred-size publication from replaying the stale
            # prior-mode rect. Anchored/non-CUSTOM families keep normal policy.
            set_commit_handler = getattr(
                presentation, "set_geometry_commit_handler", None
            )
            if callable(set_commit_handler) and policy.has_committed_rect:
                set_commit_handler(binding.set_committed_rect)

            # QML reports size only; Python resolves + assigns the outer rect. A
            # committed rect (CUSTOM / Clock per-variant) wins and suppresses this.
            connect_overlay_preferred_size(overlay.item, binding)
            self._geometry_bindings.append((widget_id, binding))

        return built

    def set_display_bounds(self, display_bounds: OverlayWidgetGeometry) -> None:
        """Re-anchor every content-anchored family for a new display rectangle.

        A committed-rect family is unaffected (its geometry is authoritative).
        """

        if self._retired:
            return
        self._display_bounds = display_bounds
        for _widget_id, binding in self._geometry_bindings:
            binding.set_display_bounds(display_bounds)

    def retire(self) -> None:
        """Retire every placed family exactly once (terminal for this generation)."""

        if self._retired:
            return
        self._retired = True
        for _widget_id, binding in self._geometry_bindings:
            binding.retire()
        self._geometry_bindings = []
        binder = self._binder
        self._binder = None
        if binder is not None:
            binder.retire_all()


__all__ = ["QuickDisplayPresenter"]
