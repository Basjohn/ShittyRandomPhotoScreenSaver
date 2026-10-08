"""Actual accepted bar geometry and native Edit controls, not allocation chrome."""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt

from rendering.quick.visualizer.edit_content_envelope import resolve_edit_content_envelope
from tests.test_qtquick_extruded_spectrum import _snapshot, target
from tests.test_visualizer_edit_native_input import edit_scene, _mouse
from tests.test_qtquick_edit_pointer_delivery import _one


@pytest.mark.qt
@pytest.mark.parametrize("turn,tilt,reflection,ghost,shadow", [
    (0.0, 0.0, 0.0, False, False), (0.08, 0.16, 0.45, False, False),
    (0.35, 0.8, 0.7, True, True), (-0.4, 0.6, 0.0, True, False),
])
def test_actual_production_pixels_fit_accepted_footprint(target, turn, tilt, reflection, ghost, shadow):
    from tests.test_qtquick_extruded_spectrum import _with_shadow_style

    capture, host = target
    snapshot = _with_shadow_style(_snapshot(
        extruded_spectrum_turn=turn, extruded_spectrum_tilt=tilt,
        extruded_spectrum_reflection=reflection, spectrum_ghosting_enabled=ghost,
        spectrum_ghost_alpha=0.4, extruded_spectrum_shadow_enabled=shadow,
        extruded_spectrum_face_mirror=0.0, extruded_spectrum_allow_overflow=True,
    ), offset=(2.0, 1.0))
    count = snapshot.logical.common.bar_count
    bars = tuple(0.12 + 0.15 * np.sin(index / max(1, count - 1) * np.pi) for index in range(count))
    common = dataclasses.replace(snapshot.logical.common, bars=bars)
    state = dataclasses.replace(snapshot.logical.mode_state, peaks=tuple(value + 0.13 for value in bars))
    snapshot = dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, common=common, mode_state=state))
    parameters = dict(state.parameters)
    envelope = resolve_edit_content_envelope("extruded_spectrum", snapshot.presentation, parameters, logical=snapshot.logical)
    pixels = capture.render(host, snapshot)
    # Transparent target reveals precisely where the real shader drew. At most
    # two pixels of MSAA coverage may extend beyond projected corner bounds.
    ys, xs = np.nonzero(pixels[..., 3] > 8)
    assert len(xs) > 100
    assert xs.min() >= envelope["left"] - 2
    assert xs.max() <= envelope["right"] + 2
    assert ys.min() >= envelope["top"] - 2
    assert ys.max() <= envelope["bottom"] + 2
    if turn == tilt == reflection == 0.0:
        assert envelope["right"] - envelope["left"] > 5 * (envelope["bottom"] - envelope["top"])


@pytest.mark.qt
def test_orbit_glyph_delivers_native_drag_from_fixed_restore_adjacent_slot(edit_scene):
    from widgets.spotify_visualizer.view_orbit import view_orbit_values

    edit = edit_scene
    glyph = _one(edit.scene.scene_root, "customLayoutOrbit-spotify_visualizer")
    primary = _one(edit.scene.scene_root, "customLayoutContentEnvelope-spotify_visualizer")
    reset = _one(edit.scene.scene_root, "customLayoutRestoreSize-spotify_visualizer")
    assert glyph.isVisible()
    assert glyph.x() == pytest.approx(reset.x() + reset.width() + 6.0)
    assert glyph.y() == pytest.approx(reset.y())
    point = glyph.mapToItem(edit.window.contentItem(), glyph.width() / 2.0, glyph.height() / 2.0)
    before = view_orbit_values(edit.visualizer.controller.presentation_state, "extruded_spectrum")
    stage = edit.item.current_global_rect
    _mouse(edit, QEvent.MouseButtonPress, point, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    frozen = (glyph.x(), glyph.y(), edit.frame.property("orbitRect"))
    before_paint = (primary.x(), primary.y(), primary.width(), primary.height())
    edit.scene.set_visualizer_edit_content_envelope({
        "admitted": True, "orbit_admitted": True, "mode": "extruded_spectrum", "left": -60., "top": 5.,
        "right": 200., "bottom": 60., "pivot_x": 80., "pivot_y": 30.,
    })
    edit.qt_app.processEvents()
    assert (glyph.x(), glyph.y(), edit.frame.property("orbitRect")) == frozen
    # The fixed parent glyph stays beside Restore while the derived graphite
    # frame follows the new projected item. Restoring orbitRect as paint geometry
    # fails this native bar.
    assert (primary.x(), primary.y(), primary.width(), primary.height()) != before_paint
    live = edit.frame.property("liveOrbitRect")
    assert (primary.x(), primary.y(), primary.width(), primary.height()) == (
        live.x(), live.y(), live.width(), live.height())
    _mouse(edit, QEvent.MouseMove, point + QPointF(24, 12), Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
    _mouse(edit, QEvent.MouseButtonRelease, point + QPointF(24, 12), Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
    assert view_orbit_values(edit.visualizer.controller.presentation_state, "extruded_spectrum") != before
    assert edit.item.current_global_rect == stage
    assert not edit.frame.property("contentOrbitDragging")
    assert edit.window.mouseGrabberItem() is None
    assert edit.settings.save_calls == 0


@pytest.mark.qt
def test_alt_left_over_overflow_content_orbits_without_stage_move(edit_scene):
    from widgets.spotify_visualizer.view_orbit import view_orbit_values

    edit = edit_scene
    edit.scene.set_visualizer_edit_content_envelope({
        "admitted": True, "orbit_admitted": True, "mode": "extruded_spectrum", "left": -80., "top": 20.,
        "right": 400., "bottom": 220., "pivot_x": 160., "pivot_y": 100.,
    })
    edit.qt_app.processEvents()
    point = edit.frame.mapToItem(edit.window.contentItem(), -40., 130.)
    before = view_orbit_values(edit.visualizer.controller.presentation_state, "extruded_spectrum")
    stage = edit.item.current_global_rect
    _mouse(edit, QEvent.MouseButtonPress, point, Qt.LeftButton, Qt.LeftButton)
    _mouse(edit, QEvent.MouseMove, point + QPointF(24, 12), Qt.NoButton, Qt.LeftButton)
    _mouse(edit, QEvent.MouseButtonRelease, point + QPointF(24, 12), Qt.LeftButton, Qt.NoButton)
    assert view_orbit_values(edit.visualizer.controller.presentation_state, "extruded_spectrum") != before
    assert edit.item.current_global_rect == stage
    assert not edit.frame.property("contentOrbitDragging")
    assert edit.window.mouseGrabberItem() is None


@pytest.mark.qt
def test_stage_alt_drag_freezes_overflow_hit_rect_while_fixed_orbit_glyph_stays_put(edit_scene):
    edit = edit_scene
    glyph = _one(edit.scene.scene_root, "customLayoutOrbit-spotify_visualizer")
    point = edit.frame.mapToItem(edit.window.contentItem(), 180.0, 130.0)
    before = (glyph.x(), glyph.y(), edit.frame.property("orbitRect"))
    _mouse(edit, QEvent.MouseButtonPress, point, Qt.LeftButton, Qt.LeftButton)
    assert edit.frame.property("orbitHitFrozen")
    edit.scene.set_visualizer_edit_content_envelope({
        "admitted": True, "orbit_admitted": True, "mode": "extruded_spectrum", "left": 30., "top": 5.,
        "right": 250., "bottom": 80., "pivot_x": 80., "pivot_y": 30.,
    })
    edit.qt_app.processEvents()
    assert (glyph.x(), glyph.y(), edit.frame.property("orbitRect")) == before
    _mouse(edit, QEvent.MouseButtonRelease, point, Qt.LeftButton, Qt.NoButton)
    assert not edit.frame.property("orbitHitFrozen")


@pytest.mark.qt
def test_retained_input_accessor_is_fenced_and_does_not_copy_or_create_node(qt_app):
    from rendering.quick.visualizer.item import VisualizerRenderItem
    from widgets.spotify_visualizer.render_bridge import VisualizerRenderIdentity

    snapshot = _snapshot()
    frame = snapshot.logical
    identity = VisualizerRenderIdentity(frame.runtime_generation, frame.engine_generation,
                                       frame.activation_id, frame.mode_id)
    item = VisualizerRenderItem()
    item._identity = identity
    item.set_presentation(snapshot.presentation)
    assert item.retained_snapshot(identity) is None
    assert item._retirement._node is None
    # A focused immutable input seam, no GL host/renderer is constructed.
    item._retirement._node = SimpleNamespace(snapshot=snapshot)
    assert item.retained_snapshot(identity) is snapshot
    stale = dataclasses.replace(identity, activation_id=identity.activation_id + 1)
    assert item.retained_snapshot(stale) is None
    item._identity = stale
    assert item.retained_snapshot(stale) is None
    item.clear_render_source()
    assert item.retained_snapshot(identity) is None
    item._retirement._node = None


def test_fully_transparent_body_has_no_footprint_but_independent_passes_are_real():
    snapshot = _snapshot(extruded_spectrum_colouring="Bar Colours", extruded_spectrum_body_alpha=1.0,
        extruded_spectrum_reflection=0.0, spectrum_ghosting_enabled=False,
        extruded_spectrum_shadow_enabled=False)
    style = snapshot.logical.common.style.as_dict()
    style.update(fill_color=(0, 0, 0, 0), border_color=(0, 0, 0, 0))
    logical = dataclasses.replace(snapshot.logical,
        common=dataclasses.replace(snapshot.logical.common, style=style))
    parameters = dict(logical.mode_state.parameters)
    assert resolve_edit_content_envelope("extruded_spectrum", snapshot.presentation, parameters, logical=logical) is None
    parameters["extruded_spectrum_colouring"] = "Spectral Edges"
    assert resolve_edit_content_envelope("extruded_spectrum", snapshot.presentation, parameters, logical=logical) is not None
    parameters["extruded_spectrum_colouring"] = "Bar Colours"
    parameters["extruded_spectrum_reflection"] = 0.4
    assert resolve_edit_content_envelope("extruded_spectrum", snapshot.presentation, parameters, logical=logical) is not None


@pytest.mark.qt
def test_empty_scene_has_semantically_admitted_orbit_without_fabricated_frame(edit_scene):
    from widgets.spotify_visualizer.view_orbit import view_orbit_values
    edit = edit_scene
    edit.scene.set_visualizer_edit_content_envelope({
        "admitted": False, "orbit_admitted": True, "mode": "extruded_spectrum",
    })
    edit.qt_app.processEvents()
    frame = _one(edit.scene.scene_root, "customLayoutContentEnvelope-spotify_visualizer")
    glyph = _one(edit.scene.scene_root, "customLayoutOrbit-spotify_visualizer")
    assert not frame.isVisible()
    assert glyph.isVisible()
    before = view_orbit_values(edit.visualizer.controller.presentation_state, "extruded_spectrum")
    stage = edit.item.current_global_rect
    point = glyph.mapToItem(edit.window.contentItem(), 30.0, 13.0)
    _mouse(edit, QEvent.MouseButtonPress, point, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    _mouse(edit, QEvent.MouseMove, point + QPointF(24, 12), Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
    _mouse(edit, QEvent.MouseButtonRelease, point + QPointF(24, 12), Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
    assert view_orbit_values(edit.visualizer.controller.presentation_state, "extruded_spectrum") != before
    assert edit.item.current_global_rect == stage
    assert edit.settings.save_calls == 0
