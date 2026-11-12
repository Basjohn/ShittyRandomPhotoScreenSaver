"""N0.4 in the worker, box 2: the logical side builds the renderer's camera from the exact framed view.

For Waveform Ribbon and Extruded Bubble, the camera the worker builds (``widgets.spotify_visualizer.framed_view_camera``)
from the framed view its session received in ``VIS_SET_VIEW`` equals, bit for bit, the camera the renderer builds for
the same frame inputs (its parameters and zoom) from the card it draws: the matrices, the eye and the tangent pair.
Waveform's travelling-pulse span (``card_span``) is the renderer's frustum's. The oracle is each renderer's own
expression on the render node's frame (``tests.test_framed_view_record.render_frame``); the negative control is the
camera the worker built before N0.4, from the layout extent (``card_span``'s former approximation: the extent's
aspect and its height over the canonical card's), on cards where it differs.
"""
from __future__ import annotations

import pytest

from tests.test_framed_view_record import (  # noqa: F401  (pcm is a fixture)
    DPRS, _cards, _send_through_the_link, pcm, render_frame, todays_view)

# Cards where the layout extent misses the drawn card (edge-resized CUSTOM stages, a quarter-turn, Expanded) and
# two where it may not (the canonical card, a uniformly scaled one).
CARDS = ("canonical", "scaled", "custom_edge_tall", "custom_edge_both_scaled", "custom_quarter_turn", "expanded")
DISCRIMINATING = ("custom_edge_tall", "custom_edge_both_scaled", "custom_quarter_turn", "expanded")


def _bits(value) -> list[str]:
    """Every float in a (nested) camera result, as its exact bits, in order."""
    import numpy as np

    if isinstance(value, np.ndarray):
        return [value.dtype.str, *(float(v).hex() for v in value.ravel())]
    if isinstance(value, (tuple, list)):
        return [bit for item in value for bit in _bits(item)]
    return [float(value).hex()]


def _defaults(mode: str, keys) -> dict:
    from core.settings.default_contract import require_canonical_default

    values = {key: require_canonical_default("widgets.spotify_visualizer." + key) for key in keys}
    return {key: tuple(value) if isinstance(value, list) else value for key, value in values.items()}


def _inside(key: str, share: float) -> float:
    from widgets.spotify_visualizer.config_applier import presentation_setting_range

    low, high = presentation_setting_range(key)
    return low + share * (high - low)


def _waveform_parameter_sets() -> list[dict]:
    from core.settings.visualizer_mode_settings import require_mode_settings
    from widgets.spotify_visualizer.waveform_ribbon_capture import _reads

    _reads_, _configuration, camera_keys = _reads(require_mode_settings("waveform_ribbon"))
    base = _defaults("waveform_ribbon", camera_keys)
    orbit = {**base, "waveform_ribbon_turn": _inside("waveform_ribbon_turn", 0.37),
             "waveform_ribbon_tilt": _inside("waveform_ribbon_tilt", 0.61)}
    return [base, orbit]


def _extruded_bubble_parameter_sets() -> list[dict]:
    from core.settings.visualizer_mode_settings import require_mode_settings
    from rendering.gl_programs.extruded_bubble_scene import _LIGHT_TYPES

    base = _defaults("extruded_bubble", [entry.key for entry in require_mode_settings("extruded_bubble").entries
                                         if entry.key.startswith("extruded_bubble_")])
    sets = []
    for light_type in _LIGHT_TYPES:                   # the surface-bound eye and the free one
        sets.append({**base, "extruded_bubble_light_type": light_type,
                     "extruded_bubble_turn": _inside("extruded_bubble_turn", 0.29),
                     "extruded_bubble_tilt": _inside("extruded_bubble_tilt", 0.58),
                     "extruded_bubble_scene_pan_x": _inside("extruded_bubble_scene_pan_x", 0.66)})
    return sets


def _renderer_waveform(frame, parameters, zoom):
    """``QuickWaveformRibbonRenderer._draw``'s camera for this frame and state."""
    from core.waveform_ribbon_view import physical_view
    from rendering.quick.scene3d.frame import item_pixel_rect
    from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale

    _x, _y, width, height = item_pixel_rect(frame)
    return physical_view(parameters, width / height, framed_aperture_scale(frame.snapshot.presentation, content=True),
                         zoom=zoom)


def _renderer_extruded_bubble(frame, parameters):
    """The Extruded Bubble renderer's camera for this frame, as ``render`` built it inline before N0.4."""
    from rendering.gl_programs.extruded_bubble_scene import physical_camera, scene_knobs
    from rendering.quick.scene3d.frame import item_pixel_rect
    from rendering.quick.visualizer.implementation_values import parameter
    from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale

    _x, _y, width, height = item_pixel_rect(frame)
    aperture_scale = framed_aperture_scale(frame.snapshot.presentation)
    pose = (float(parameter(parameters, "extruded_bubble_turn")), float(parameter(parameters, "extruded_bubble_tilt")))
    return physical_camera(
        *pose, width / height, float(parameter(parameters, "extruded_bubble_scene_scale")),
        pan_x=float(parameter(parameters, "extruded_bubble_scene_pan_x")),
        pan_y=float(parameter(parameters, "extruded_bubble_scene_pan_y")),
        position_offset=tuple(parameter(parameters, "extruded_bubble_camera_position")),
        fov_y_degrees=float(parameter(parameters, "extruded_bubble_camera_fov")),
        surface_bound=scene_knobs(parameters)["mode"] == "surface", aperture_scale=aperture_scale)


@pytest.mark.qt
@pytest.mark.parametrize("dpr", DPRS)
def test_the_worker_builds_waveform_ribbons_camera_bit_for_bit(qt_app, dpr):
    from core.waveform_ribbon_view import card_span, visible_span, visible_top
    from rendering.quick.scene3d.frame import item_pixel_rect
    from rendering.quick.visualizer.framed_view import resolve_framed_view
    from widgets.spotify_visualizer.framed_view_camera import waveform_ribbon_camera
    from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale

    missed = set()
    for label, card, worker_extent in _cards("waveform_ribbon", dpr):
        if label not in CARDS:
            continue
        frame = render_frame(card)
        received = _send_through_the_link(qt_app, resolve_framed_view(card))
        old = todays_view(worker_extent)
        for parameters in _waveform_parameter_sets():
            for zoom in (1.0, 1.17):
                expected = _bits(_renderer_waveform(frame, parameters, zoom))
                assert _bits(waveform_ribbon_camera(parameters, received, zoom=zoom)) == expected, label
                if _bits(waveform_ribbon_camera(parameters, old, zoom=zoom)) != expected:
                    missed.add(label)
            # The travelling pulse's span is the renderer's frustum's, through the card's top edge.
            _x, _y, width, height = item_pixel_rect(frame)
            aperture = framed_aperture_scale(frame.snapshot.presentation, content=True)
            top = visible_top(parameters, width / height, aperture)
            span = visible_span(parameters, width / height, aperture) + (() if top is None else (top,))
            assert card_span(parameters, received) == span, label
        assert card_span(_waveform_parameter_sets()[0], None) is None
    # Negative control: the camera the worker built from the layout extent differs on these cards.
    assert set(DISCRIMINATING) <= missed, missed


@pytest.mark.qt
def test_the_sessions_waveform_capture_spans_the_drawn_cards_frustum(qt_app, pcm, monkeypatch):
    # End to end on the real owner (the session in this process behind the supervisor stand-in), on the display-wide
    # card: every tick's travelling-pulse span is ``card_span`` of the framed view the session received, which is the
    # renderer's view of the card the scene draws. Before N0.4 it was the layout extent (the ordinary card's, here).
    from tests.test_framed_view_record import _drawn, renderer_view
    from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor, _pump
    from tools.visualizer_replay import owner_worker_gate as gate
    from widgets.spotify_visualizer import engine_worker_link, waveform_ribbon_capture

    spans = []
    span = waveform_ribbon_capture.card_span
    monkeypatch.setattr(waveform_ribbon_capture, "card_span",
                        lambda camera, view: spans.append((dict(camera), view)) or span(camera, view))
    engine_worker_link.reset_run_state_for_testing()
    stand_in = _InProcessSupervisor()
    rig = gate.OwnerRig("waveform_ribbon", worker=True, supervisor=stand_in, cadence="thread")
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
        _pump(rig, 0.4, until=lambda: _drawn(owner) is not None)
        assert owner.set_expanded_display(True)
        _pump(rig, 0.3)
        rig.settle()
        before = len(spans)
        _pump(rig, 0.5)
        _x, _y, width, height = owner.presentation_runtime.display_identity.geometry
        dpr = float(_drawn(owner).dpr)
        expected = renderer_view(_drawn(owner), (round(width * dpr), round(height * dpr)))
        ticks = spans[before:]
        assert len(ticks) > 10
        assert all(view == expected for _camera, view in ticks), (ticks[-1][1], expected)
        assert expected[0] != owner.controller.presentation_viewport_extent[0] / \
            owner.controller.presentation_viewport_extent[1]          # the extent would have missed it
    finally:
        rig.close()
        stand_in.close()
        engine_worker_link.reset_run_state_for_testing()


@pytest.mark.qt
@pytest.mark.parametrize("dpr", DPRS)
def test_the_worker_builds_extruded_bubbles_camera_bit_for_bit(qt_app, dpr):
    from rendering.quick.visualizer.framed_view import resolve_framed_view
    from widgets.spotify_visualizer.framed_view_camera import extruded_bubble_camera

    missed = set()
    for label, card, worker_extent in _cards("extruded_bubble", dpr):
        if label not in CARDS:
            continue
        frame = render_frame(card)
        received = _send_through_the_link(qt_app, resolve_framed_view(card))
        old = todays_view(worker_extent)
        for parameters in _extruded_bubble_parameter_sets():
            expected = _bits(_renderer_extruded_bubble(frame, parameters))
            assert _bits(extruded_bubble_camera(parameters, received)) == expected, label
            if _bits(extruded_bubble_camera(parameters, old)) != expected:
                missed.add(label)
    # Negative control: the extent-built camera misses the drawn card's aspect on these cards at every DPR (Extruded
    # Bubble's aperture is the extent's, so only the pixel aspect can differ: a card whose device pixels hold the
    # extent's aspect exactly, as a quarter-turned whole-pixel card at DPR 1, matches it).
    assert {"custom_edge_both_scaled", "expanded"} <= missed, missed
