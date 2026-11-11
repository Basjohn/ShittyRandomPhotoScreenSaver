"""Camera Position rows in every framed Studio come from the mode's framed camera, and each offered axis moves the eye.

``core.settings.framed_camera`` admits Camera Position on the actual eye: inside the spec's eye box (``eye_half`` about
``eye_center``, in ``offset_scale`` units), above an optional floor, and, for a grounded orbit, at the orbit's authored
eye height. A Studio row therefore offers an axis only where the eye can move along it, over the box's span in offset
units (``ui.studio.framed.camera_position_axes``). Waveform's Studio offered "Camera Y" at a hard-coded -1..1 although
its grounded orbit keeps the eye at one height: a drag committed once and the save read back 0.0 (the slider snapped).
Ranges are derived from the registry and specs; no value is pinned.
"""
from __future__ import annotations

import pytest

from tests.test_studio_drag_io_churn import opened, settings_manager  # noqa: F401  (fixtures)


def _framed_modes():
    from core.settings.framed_camera import spec_for_mode
    from ui.studio.registry import studio_modes
    return sorted(e.mode_id for e in studio_modes() if spec_for_mode(e.mode_id) is not None)


FRAMED = _framed_modes()


def _rows(schema, mode):
    from core.settings.framed_camera import spec_for_mode
    key = spec_for_mode(mode).key("camera_position")
    return {p.path[1]: p for p in schema.properties if p.path[0] == key and len(p.path) == 2}


@pytest.mark.parametrize("mode", FRAMED)
def test_camera_position_rows_are_the_framed_cameras_axes(mode):
    from ui.studio.framed import camera_position_axes
    from ui.studio.registry import create_adapter
    rows = _rows(create_adapter(mode).schema(), mode)
    axes = {index: (low, high) for index, low, high in camera_position_axes(mode)}
    assert set(rows) == set(axes), f"{mode}: offered axes {sorted(rows)} vs the camera's {sorted(axes)}"
    for index, prop in rows.items():
        assert (prop.minimum, prop.maximum) == pytest.approx(axes[index]), f"{mode}: axis {index}"


def test_the_axes_follow_the_spec():
    """Every axis spans the eye box in offset units; a grounded orbit's height is not an axis."""
    from core.settings.framed_camera import spec_for_mode
    from ui.studio.framed import camera_position_axes
    for mode in FRAMED:
        spec = spec_for_mode(mode)
        axes = {index: (low, high) for index, low, high in camera_position_axes(mode)}
        expected = {i for i in range(3) if not (spec.grounded_orbit is not None and i == 1)}
        assert set(axes) == expected, mode
        for index, (low, high) in axes.items():
            reach = 2.0 * spec.eye_half[index] / spec.offset_scale[index]
            assert (low, high) == pytest.approx((-reach, reach)), (mode, index)


def _drag_rows(controller, surface, rows):
    """{axis: (start, asked, saved)} after one drag per row toward its roomier end."""
    bridge, session = controller.bridge, controller.session
    out = {}
    for index, prop in sorted(rows.items()):
        key = prop.path[0]
        start = float(session.committed_values[key][index])
        step = 0.25 * (prop.maximum - prop.minimum)
        target = start + (step if prop.maximum - start >= start - prop.minimum else -step)
        bridge.beginEdit(prop.id, prop.label)
        for k in (1, 2, 3, 4):
            bridge.previewValue(prop.id, 0, start + (target - start) * k / 4.0)
            surface.pump()
        bridge.endEdit()
        surface.pump(2)
        out[index] = (start, target, float(session.committed_values[key][index]))
    return out


def test_a_grounded_height_row_snaps_back_negative_control(opened):
    """The former Waveform row: Camera Y offered at -1..1 on a grounded orbit. The drag commits, the save reads 0."""
    import dataclasses
    from core.settings.framed_camera import spec_for_mode
    from ui.studio.schema import SCALAR, StudioProperty
    controller, surface, _counter = opened("waveform_ribbon")
    key = spec_for_mode("waveform_ribbon").key("camera_position")
    row = StudioProperty(id=f"{key}.1", path=(key, 1), label="Camera Y", workspace="world", group="Camera",
                         instrument=SCALAR, minimum=-1.0, maximum=1.0, decimals=3)
    schema = dataclasses.replace(controller.session.schema, properties=(*controller.session.schema.properties, row))
    controller.bridge._schema = controller.session._schema = schema
    commits = controller.session.commit_count
    (start, asked, saved), = _drag_rows(controller, surface, {1: row}).values()
    assert controller.session.commit_count == commits + 1 and asked != start and saved == start


@pytest.mark.parametrize("mode", FRAMED)
def test_every_offered_axis_moves_the_saved_eye(opened, mode):
    controller, surface, _counter = opened(mode)
    for index, (start, asked, saved) in _drag_rows(controller, surface, _rows(controller.session.schema, mode)).items():
        assert abs(saved - start) > 1e-3, f"{mode}: Camera axis {index} snapped back to {saved} (asked {asked})"
