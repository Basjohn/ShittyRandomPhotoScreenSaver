"""Focused contracts for truthful freeform-3D CUSTOM Edit framing."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from core.settings.default_contract import get_raw_default_settings
from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from rendering.quick.visualizer.edit_content_envelope import (
    resolve_edit_content_envelope,
)
from tests._visualizer_presentation import resolve_presentation


def _presentation(mode: str, *, extent=(420.0, 280.0)):
    return resolve_presentation(
        policy=get_visualizer_presentation_policy(mode),
        display_size=(1920.0, 1080.0),
        outer_origin=(137.0, 83.0),
        viewport_extent=extent,
    )


def _parameters() -> dict[str, object]:
    return dict(get_raw_default_settings()["widgets"]["spotify_visualizer"])


def _logical(count=24):
    return SimpleNamespace(mode_id="extruded_spectrum",
                           common=SimpleNamespace(bar_count=count, bars=(0.35,) * count,
                               style={"fill_color": (255, 255, 255, 255), "border_color": (255, 255, 255, 255)}),
                           mode_state=SimpleNamespace(peaks=(0.4,) * count))


@pytest.mark.parametrize("mode", ("extruded_spectrum", "shockwave_grid"))
def test_envelope_is_read_only_content_not_stage_geometry(mode: str) -> None:
    presentation = _presentation(mode)
    parameters = _parameters()
    parameters["bar_count"] = 24
    before = deepcopy(presentation)

    envelope = resolve_edit_content_envelope(mode, presentation, parameters, logical=_logical())

    assert envelope is not None and envelope["admitted"] is True
    assert envelope["mode"] == mode
    assert envelope["right"] > envelope["left"]
    assert envelope["bottom"] > envelope["top"]
    # Reach can leave the stage when the authored 3D scene allows overflow,
    # but deriving it cannot mutate the only persisted stage authority.
    assert presentation == before
    assert presentation.outer_rect == before.outer_rect
    assert presentation.viewport_extent == before.viewport_extent


@pytest.mark.parametrize(
    ("mode", "turn_key", "tilt_key"),
    (
        ("extruded_spectrum", "extruded_spectrum_turn", "extruded_spectrum_tilt"),
        ("shockwave_grid", "shockwave_grid_turn", "shockwave_grid_tilt"),
    ),
)
def test_orbit_changes_only_the_derived_envelope(mode: str, turn_key: str, tilt_key: str) -> None:
    presentation = _presentation(mode, extent=(620.0, 280.0))
    front = _parameters()
    front["bar_count"] = 32
    edge = dict(front)
    edge[turn_key] = 0.5
    edge[tilt_key] = 0.78

    front_envelope = resolve_edit_content_envelope(mode, presentation, front, logical=_logical(32))
    edge_envelope = resolve_edit_content_envelope(mode, presentation, edge, logical=_logical(32))

    assert front_envelope is not None and edge_envelope is not None
    assert front_envelope != edge_envelope
    assert presentation.outer_rect == _presentation(mode, extent=(620.0, 280.0)).outer_rect
    assert presentation.viewport_extent == (620.0, 280.0)


def test_sphere_uses_its_own_reach_and_pivot_not_a_generic_3d_circle() -> None:
    presentation = _presentation("sphere", extent=(480.0, 320.0))
    envelope = resolve_edit_content_envelope("sphere", presentation, _parameters())

    assert envelope is not None
    assert envelope["mode"] == "sphere"
    # Sphere's renderer chooses its own centre/reach; the generic 3D path has
    # no permission to replace that shape with Extruded/Shockwave maths.
    assert envelope["pivot_x"] == pytest.approx(presentation.content_rect[0] - presentation.outer_rect[0]
                                                  + presentation.content_rect[2] * 0.5)
    assert envelope["pivot_y"] == pytest.approx(presentation.content_rect[1] - presentation.outer_rect[1]
                                                  + presentation.content_rect[3] * 0.5)


def test_planar_mode_has_no_edit_content_envelope() -> None:
    presentation = _presentation("spectrum")
    assert resolve_edit_content_envelope("spectrum", presentation, _parameters()) is None


def test_missing_or_silent_extruded_source_has_no_fake_maximum_height_item() -> None:
    presentation = _presentation("extruded_spectrum")
    assert resolve_edit_content_envelope("extruded_spectrum", presentation, _parameters()) is None
    logical = _logical()
    logical.common.bars = (0.0,) * 24
    logical.mode_state.peaks = (0.0,) * 24
    assert resolve_edit_content_envelope("extruded_spectrum", presentation, _parameters(), logical=logical) is None


def test_accepted_shallow_bars_are_not_ceiling_allocation_bounds() -> None:
    presentation = _presentation("extruded_spectrum", extent=(620.0, 400.0))
    parameters = _parameters()
    parameters.update(extruded_spectrum_tilt=0.0, extruded_spectrum_turn=0.0,
                      extruded_spectrum_reflection=0.0, spectrum_ghosting_enabled=False)
    shallow = resolve_edit_content_envelope("extruded_spectrum", presentation, parameters, logical=_logical())
    loud = _logical()
    loud.common.bars = (2.0,) * 24
    tall = resolve_edit_content_envelope("extruded_spectrum", presentation, parameters, logical=loud)
    assert shallow["right"] - shallow["left"] == pytest.approx(tall["right"] - tall["left"])
    assert shallow["bottom"] - shallow["top"] < 0.4 * (tall["bottom"] - tall["top"])
