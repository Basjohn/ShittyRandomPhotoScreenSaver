"""The Studio names the orbit's real save route, one rule from the mode's capabilities (1B.3 side defect).

Before, every orbit notice said the orbit "saves only with the preset's camera checkbox", but Sphere and Extruded
Spectrum have no such checkbox and save through Save Camera. The rule (``ui/studio/framed.py:orbit_save_route``) is
checked against the real Settings preset row for every Studio mode; the notices are checked to carry the route's
hint, never fixed wording.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ui.studio import framed
from ui.studio.controller import StudioController
from ui.studio.registry import studio_modes

MODES = [entry.mode_id for entry in studio_modes()]
ROUTES = (framed.CAMERA_CHOICE, framed.SAVE_CAMERA, framed.PREVIEW_ONLY)


@pytest.mark.parametrize("mode", MODES)
def test_the_route_is_the_camera_choice_exactly_when_the_preset_row_offers_it(qt_app, mode):
    from ui.tabs.media.preset_slider import VisualizerPresetSlider
    slider = VisualizerPresetSlider(mode)
    try:
        offers_choice = slider._include_starting_view is not None
    finally:
        slider.deleteLater()
    route = framed.orbit_save_route(mode, can_save_camera=True)
    assert (route == framed.CAMERA_CHOICE) == offers_choice
    if not offers_choice:
        assert framed.orbit_save_route(mode, can_save_camera=False) == framed.PREVIEW_ONLY


def test_both_routes_occur_among_the_studio_modes():
    routes = {framed.orbit_save_route(mode, can_save_camera=True) for mode in MODES}
    assert {framed.CAMERA_CHOICE, framed.SAVE_CAMERA} <= routes      # otherwise the rule above proves nothing


def test_the_route_hints_are_distinct():
    assert len({framed.orbit_save_hint(route) for route in ROUTES}) == len(ROUTES)


def _stand_in(mode, notes, *, save_camera=True):
    store = SimpleNamespace(camera_commit_allowed=lambda: False)
    if save_camera:
        store.save_camera = lambda values: ""
    stand_in = SimpleNamespace(
        adapter=SimpleNamespace(mode_id=mode), store=store, _pose={"pose_key": 0.5},
        refresh_preset_previews=lambda: None,
        navigation=lambda: SimpleNamespace(saved_with_camera_policy=frozenset({"pose_key"}),
                                           saved_on_keep=frozenset()),
        bridge=SimpleNamespace(notify=notes.append))
    stand_in.orbit_save_route = lambda: StudioController.orbit_save_route(stand_in)
    stand_in.orbit_save_hint = lambda: StudioController.orbit_save_hint(stand_in)
    return stand_in


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("save_camera", [True, False])
def test_the_orbit_and_keep_view_notices_name_the_modes_route(mode, save_camera):
    route = framed.orbit_save_route(mode, can_save_camera=save_camera)
    for action in (StudioController.end_orbit, StudioController.keep_view):
        notes = []
        action(_stand_in(mode, notes, save_camera=save_camera))
        assert len(notes) == 1
        assert framed.orbit_save_hint(route) in notes[0]
        for other in ROUTES:                      # negative control: no other route is named
            if other != route:
                assert framed.orbit_save_hint(other) not in notes[0]
