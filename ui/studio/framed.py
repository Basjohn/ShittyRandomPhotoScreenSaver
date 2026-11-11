"""Shared pieces for framed 3D modes in the Studio (mode-neutral; every name is passed in).

A framed mode is presented exactly as production presents its card: the same presentation resolver and
uniform-scale rule (``framed_aperture_scale``), the live card's extent and chrome, and the shared framed
camera's orbit / lens / dolly / pan settings (``core.settings.framed_camera``). Adapters call these instead
of carrying their own copies.
"""
from __future__ import annotations

from types import SimpleNamespace
from dataclasses import dataclass
from typing import Any, Callable

from ui.studio.adapter import NavAxis, RenderCard, StudioFraming, StudioNavigation


def presentation(mode_id: str, logical_size, extent, style, *, dpr: float = 1.0, content_rotation_quarters: int = 0):
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
        content_rotation_quarters=content_rotation_quarters,
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


def camera_position_axes(mode_id: str) -> tuple[tuple[int, float, float], ...]:
    """Camera Position's editable axes ``(index, low, high)`` from the mode's framed camera spec (the one owner of
    where the eye may go). Each axis spans the admitted eye box in offset units (``2 * eye_half / offset_scale``
    either way: from any orbit pose the eye may reach the whole box; the box and floor bound the eye itself). An
    axis the spec fixes is not offered: a grounded orbit keeps its authored eye height, so its height offset always
    resolves to 0 (Waveform's Studio offered it, and every drag snapped back)."""
    from core.settings.framed_camera import spec_for_mode
    spec = spec_for_mode(mode_id)
    axes = []
    for index, (half, scale) in enumerate(zip(spec.eye_half, spec.offset_scale)):
        if index == 1 and spec.grounded_orbit is not None:
            continue
        reach = 2.0 * float(half) / float(scale)
        axes.append((index, -reach, reach))
    return tuple(axes)


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


def orbit_navigation(mode_id: str) -> StudioNavigation:
    """A free-orbit mode's navigation (no lens, dolly or pan of its own): drag orbits the descriptor's declared
    live view pose (``view_orbit_settings``: turn, tilt), bounded by the registry. The orbit is a live view, saved
    only when the store's camera policy allows it (otherwise a preview view)."""
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    from core.settings.visualizer_mode_settings import require_mode_settings
    turn, tilt = get_visualizer_mode_descriptor(mode_id).view_orbit_settings
    spec = require_mode_settings(mode_id)

    def axis(key, label):
        control = spec.control(key)
        return NavAxis(control.key, (float(control.low), float(control.high)), label)
    orbit_h, orbit_v = axis(turn, "Turn"), axis(tilt, "Tilt")
    return StudioNavigation(orbit_h=orbit_h, orbit_v=orbit_v,
                            saved_with_camera_policy=frozenset({orbit_h.key, orbit_v.key}))


@dataclass(frozen=True)
class StudioRenderSnapshot:
    """Studio evaluators supply their own immutable frame; presentation remains replaceable by Scene3D."""
    logical: Any
    presentation: Any


def render_frame(card: RenderCard, state, resolved):
    """The same production frame contract for every Studio renderer."""
    from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame
    from widgets.spotify_visualizer.render_state import VisualizerLogicalFrame, VisualizerRenderSnapshot
    if isinstance(state, VisualizerLogicalFrame):
        snapshot = VisualizerRenderSnapshot(logical_revision=1, logical=state, presentation=resolved)
    else:
        snapshot = StudioRenderSnapshot(logical=SimpleNamespace(mode_state=state), presentation=resolved)
    return QuickVisualizerRenderFrame(snapshot=snapshot, viewport=tuple(int(v) for v in card.viewport),
                                      logical_size=tuple(float(v) for v in card.logical_size),
                                      matrix_values=tuple(card.matrix_values), quad_vao=int(card.quad_vao))


class QuickModeRenderer:
    """Render-thread adapter around a mode's production Quick renderer (its own scene instance): the frame
    is handed over exactly as the runtime hands it (mode state + resolved presentation + item mapping)."""

    def __init__(self, mode_id: str, factory: Callable[[], Any]) -> None:
        self._mode_id = mode_id
        self._impl = factory()
        self._key = None
        self._presentation = None

    def _resolved(self, card: RenderCard):
        key = (card.logical_size, card.extent, card.style, card.content_rotation_quarters)
        if key != self._key:
            self._presentation = presentation(self._mode_id, card.logical_size, card.extent, card.style,
                                               content_rotation_quarters=card.content_rotation_quarters)
            self._key = key
        return self._presentation

    def _frame(self, card: RenderCard, state):
        return render_frame(card, state, self._resolved(card))

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

    @staticmethod
    def pixel_ratio(card: RenderCard) -> float:
        """Target pixels per item unit, from the item mapping itself: the live viewport draws into the whole window
        target (wider than a letterboxed item), a snapshot into a target of exactly the item's pixel size."""
        scale = abs(float(card.matrix_values[0])) * 0.5 * float(card.viewport[2])
        return scale if scale > 0.0 else card.viewport[2] / max(1e-6, card.logical_size[0])

    def _resolved(self, card: RenderCard):
        dpr = self.pixel_ratio(card)
        key = (card.logical_size, card.extent, card.style, round(dpr, 4), card.content_rotation_quarters)
        if key != self._key:
            self._presentation = presentation(self._mode_id, card.logical_size, card.extent, card.style, dpr=dpr,
                                               content_rotation_quarters=card.content_rotation_quarters)
            self._key = key
        return self._presentation

    def prepare(self, card: RenderCard, frame) -> bool:
        step = getattr(self._impl, "prepare_step", None)
        return bool(step(self._frame(card, frame))) if callable(step) else True


__all__ = ["ContractModeRenderer", "QuickModeRenderer", "camera_navigation", "camera_position_axes", "card_framings",
           "orbit_navigation",
           "presentation"]
