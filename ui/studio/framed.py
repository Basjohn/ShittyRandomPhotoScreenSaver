"""Shared pieces for framed 3D modes in the Studio (mode-neutral; every name is passed in).

A framed mode is presented exactly as production presents its card: the same presentation resolver and
uniform-scale rule (``framed_aperture_scale``), the live card's extent and chrome, and the shared framed
camera's orbit / lens / dolly / pan settings (``core.settings.framed_camera``). Adapters call these instead
of carrying their own copies.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

from ui.studio.adapter import NavAxis, RenderCard, StudioFraming, StudioNavigation


def presentation(mode_id: str, logical_size, extent, style, *, dpr: float = 1.0):
    """The production presentation of ``extent`` (the live card's world extent) at a Studio frame size.

    The Studio frame is the live card uniformly scaled down, chrome included: the card's border and inset
    (display pixels on the card committed at its extent) scale with the frame. Unscaled, a 4 px border on a
    small frame eats a far larger share of the reference height and inflates the lens aperture (7% more
    world than the live card on the operator's wide TV card)."""
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from widgets.spotify_visualizer.presentation_geometry import (
        CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE, resolve_visualizer_presentation)
    width, height = logical_size
    extent = extent or CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
    style = dict(style or ())
    scale = width / extent[0]
    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(mode_id), display_size=(width, height), dpr=float(dpr),
        viewport_extent=extent, uniform_visual_scale=scale,
        border_width=float(style.get("border_width", 0.0)) * scale, corner_radius=0.0,
        content_inset=float(style.get("content_inset", 0.0)) * scale, background_color=(0, 0, 0, 0),
        border_color=(0, 0, 0, 0), shadow_enabled=False, shadow_color=(0, 0, 0, 0), shadow_blur=0.0,
        shadow_offset=(0.0, 0.0), shadow_spread=0.0, shadow_extensions=(0.0, 0.0, 0.0, 0.0))


def card_framings(card_extent, card_style=None) -> tuple[StudioFraming, ...]:
    """The live card (CUSTOM extent, else the card baseline) and two wider cards at the baseline height,
    following production's edge-resize rule (same height, more world revealed)."""
    from widgets.spotify_visualizer.presentation_geometry import CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
    base_w, base_h = CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
    card = tuple(float(v) for v in (card_extent or (base_w, base_h)))
    return live_card_framings(card, card_style)


def live_card_framings(card, card_style=None) -> tuple[StudioFraming, ...]:
    """Framings derived from the live card so none shows less of the world than the card does (the
    'stuck zoomed in' defect): Fill grows the card to the viewport's shape (production's edge-resize rule:
    more world revealed, same scale), Live Card is the card itself (letterboxed honestly), and 16:9 / 21:9
    are the smallest cards of that shape containing the live card's world."""
    from ui.studio.adapter import fill_extent
    style = tuple(sorted((card_style or {}).items()))
    return (StudioFraming("fill", "Fill", card,
                          "Fill the viewport at the live card's scale: everything the card shows, plus more world "
                          "where the viewport is wider or taller.", style, fill=True),
            StudioFraming("card", f"Live Card {card[0] / card[1]:.2f}:1", card,
                          "The visualizer card exactly as it is laid out (CUSTOM extent, else the card baseline).",
                          style),
            StudioFraming("wide", "16:9", fill_extent(card, 16 / 9),
                          "A 16:9 card containing everything the live card shows.", style),
            StudioFraming("cinema", "21:9", fill_extent(card, 21 / 9),
                          "A 21:9 card containing everything the live card shows.", style))


def camera_navigation(mode_id: str, prefix: str) -> StudioNavigation:
    """Orbit = turn/tilt; wheel = the lens field of view (a saved Camera setting); Shift+wheel = the framed
    camera's dolly (scene_scale); pan = scene pan. Bounds are the registry's. Orbit is saved only with the
    preset's camera policy; the lens on Keep View; dolly and pan stay preview views."""
    from core.settings.visualizer_mode_settings import require_mode_settings
    spec = require_mode_settings(mode_id)

    def axis(field, label, units=""):
        control = spec.control(prefix + field)
        return NavAxis(control.key, (float(control.low), float(control.high)), label, units)
    orbit_h, orbit_v = axis("turn", "Turn"), axis("tilt", "Tilt")
    return StudioNavigation(orbit_h=orbit_h, orbit_v=orbit_v, zoom=axis("camera_fov", "FOV", "°"),
                            zoom_inverts=True, dolly=axis("scene_scale", "Dolly", "×"),
                            pan_x=axis("scene_pan_x", "Pan X"), pan_y=axis("scene_pan_y", "Pan Y"),
                            saved_with_camera_policy=frozenset({orbit_h.key, orbit_v.key}),
                            saved_on_keep=frozenset({prefix + "camera_fov"}))


class QuickModeRenderer:
    """Render-thread adapter around a mode's production Quick renderer (its own scene instance): the frame
    is handed over exactly as the runtime hands it (mode state + resolved presentation + item mapping)."""

    def __init__(self, mode_id: str, factory: Callable[[], Any]) -> None:
        self._mode_id = mode_id
        self._impl = factory()
        self._key = None
        self._presentation = None

    def _resolved(self, card: RenderCard):
        key = (card.logical_size, card.extent, card.style)
        if key != self._key:
            self._presentation = presentation(self._mode_id, card.logical_size, card.extent, card.style)
            self._key = key
        return self._presentation

    def _frame(self, card: RenderCard, state):
        return SimpleNamespace(snapshot=SimpleNamespace(logical=SimpleNamespace(mode_state=state),
                                                        presentation=self._resolved(card)),
                               viewport=card.viewport, logical_size=card.logical_size,
                               matrix_values=card.matrix_values, quad_vao=card.quad_vao,
                               content_rotation_quarters=0)

    def prepare(self, card: RenderCard, frame) -> bool:
        return bool(self._impl.prepare_step(self._frame(card, frame)))

    def render(self, card: RenderCard, frame) -> None:
        self._impl.render(self._frame(card, frame))

    def release(self) -> None:
        self._impl.release_resources()


class ContractModeRenderer(QuickModeRenderer):
    """A mode's production Quick renderer handed the production render-frame contract
    (``QuickVisualizerRenderFrame``): the logical frame (a mode frame alone, or a full ``VisualizerLogicalFrame``
    when the evaluator produces one), the live card's resolved presentation at the target's pixel ratio, and the
    item mapping. A renderer with a prepared reveal compiles through its own ``prepare_step``."""

    def _resolved(self, card: RenderCard):
        dpr = card.viewport[2] / max(1e-6, card.logical_size[0])
        key = (card.logical_size, card.extent, card.style, round(dpr, 4))
        if key != self._key:
            self._presentation = presentation(self._mode_id, card.logical_size, card.extent, card.style, dpr=dpr)
            self._key = key
        return self._presentation

    def _frame(self, card: RenderCard, state):
        from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame
        logical = state if hasattr(state, "mode_state") else SimpleNamespace(mode_state=state)
        snapshot = SimpleNamespace(logical=logical, presentation=self._resolved(card))
        return QuickVisualizerRenderFrame(snapshot=snapshot, viewport=tuple(int(v) for v in card.viewport),
                                          logical_size=tuple(float(v) for v in card.logical_size),
                                          matrix_values=tuple(card.matrix_values), quad_vao=int(card.quad_vao))

    def prepare(self, card: RenderCard, frame) -> bool:
        step = getattr(self._impl, "prepare_step", None)
        return bool(step(self._frame(card, frame))) if callable(step) else True


__all__ = ["ContractModeRenderer", "QuickModeRenderer", "camera_navigation", "card_framings", "presentation"]
