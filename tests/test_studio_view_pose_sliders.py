"""A mode's live view pose (its descriptor's ``view_orbit_settings``: turn, tilt) is edited the same way in every Studio.

The rule (``Docs/Reference/Visualizer_Studio.md``, Navigation and camera saving): turn/tilt are the live orbit, a view
and not artwork. Their sliders are view-pose rows: a drag previews the view; the release saves it only when the store's
camera policy allows (Settings' "Include current camera view" choice), and otherwise the preview view holds for the
session (never snapping back). Saved, it survives the commit and a reopen from Settings.

Sphere's View Turn / View Tilt were plain committed rows: the release saved, the canonical save (which leaves view
keys to the camera owner) read the old view back, and the slider snapped back to it.
"""
from __future__ import annotations

import pytest

from tests.test_studio_drag_io_churn import opened, settings_manager  # noqa: F401  (fixtures)


def _orbit_modes():
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    from ui.studio.registry import studio_modes
    return sorted(e.mode_id for e in studio_modes() if get_visualizer_mode_descriptor(e.mode_id).view_orbit_settings)


ORBIT_MODES = _orbit_modes()


def _view_props(controller, mode):
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    keys = get_visualizer_mode_descriptor(mode).view_orbit_settings
    props = [p for p in controller.session.schema.properties if p.path == (p.path[0],) and p.path[0] in keys]
    assert {p.path[0] for p in props} == set(keys), f"{mode}: the view pose has no Studio rows"
    return props


def _target(prop, current):
    span = prop.maximum - prop.minimum
    return round(prop.minimum + 0.8 * span if current < prop.minimum + 0.5 * span else prop.minimum + 0.2 * span, 3)


def _drag(controller, surface, prop, target):
    bridge = controller.bridge
    start = float(controller.evaluation_values()[prop.path[0]])
    bridge.beginEdit(prop.id, prop.label)
    for k in (1, 2, 3, 4):
        bridge.previewValue(prop.id, 0, start + (target - start) * k / 4.0)
        surface.pump()
    bridge.endEdit()
    surface.pump(2)


@pytest.mark.parametrize("mode", ORBIT_MODES)
def test_the_view_pose_rows_are_view_pose_rows_with_navigation(opened, mode):
    controller, _surface, _counter = opened(mode)
    for prop in _view_props(controller, mode):
        assert prop.view_pose, f"{mode}: {prop.id} is a plain committed row"
    nav = controller.navigation()
    assert nav is not None and {nav.orbit_h.key, nav.orbit_v.key} == {p.path[0] for p in _view_props(controller, mode)}


@pytest.mark.parametrize("mode", ORBIT_MODES)
def test_without_the_camera_policy_a_dragged_view_holds_for_the_session(opened, mode):
    controller, surface, _counter = opened(mode)
    controller.store.set_include_view(False)
    for prop in _view_props(controller, mode):
        key = prop.path[0]
        saved, commits = controller.session.committed_values[key], controller.session.commit_count
        target = _target(prop, float(controller.evaluation_values()[key]))
        _drag(controller, surface, prop, target)
        assert controller.evaluation_values()[key] == pytest.approx(target), f"{mode}: {key} snapped back"
        assert controller.bridge.values[prop.id] == pytest.approx(target)
        assert controller.session.commit_count == commits and controller.session.committed_values[key] == saved


@pytest.mark.parametrize("mode", ORBIT_MODES)
def test_save_camera_keeps_a_dragged_view_and_it_reopens(opened, mode):
    """Every orbit mode's explicit save: the held preview view is saved and Settings reopens on it."""
    from ui.studio.settings_link import VisualizerSettingsStore
    controller, surface, _counter = opened(mode)
    controller.store.set_include_view(False)
    targets = {}
    for prop in _view_props(controller, mode):
        targets[prop.path[0]] = _target(prop, float(controller.evaluation_values()[prop.path[0]]))
        _drag(controller, surface, prop, targets[prop.path[0]])
    controller.bridge.saveCamera()
    surface.pump(2)
    reopened = VisualizerSettingsStore(controller.store._tab, mode).snapshot()
    for key, target in targets.items():
        assert controller.session.committed_values[key] == pytest.approx(target), f"{mode}: {key} not kept"
        assert controller.evaluation_values()[key] == pytest.approx(target)
        assert reopened[key] == pytest.approx(target), f"{mode}: {key} lost on reopen"


def _policy_modes():
    """Modes whose preset row offers the camera choice ("Include current camera view")."""
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    return [m for m in ORBIT_MODES if get_visualizer_mode_descriptor(m).scene_transform_settings]


@pytest.mark.parametrize("mode", _policy_modes())
def test_with_the_camera_policy_a_dragged_view_is_saved_and_reopens(opened, mode):
    from ui.studio.settings_link import VisualizerSettingsStore
    controller, surface, _counter = opened(mode)
    controller.store.set_include_view(True)
    assert controller.store.camera_commit_allowed()
    for prop in _view_props(controller, mode):
        key = prop.path[0]
        commits = controller.session.commit_count
        target = _target(prop, float(controller.evaluation_values()[key]))
        _drag(controller, surface, prop, target)
        assert controller.session.commit_count == commits + 1, f"{mode}: {key} was not saved"
        assert controller.session.committed_values[key] == pytest.approx(target), f"{mode}: {key} read back"
        assert controller.evaluation_values()[key] == pytest.approx(target)
        tab = controller.store._tab
        assert VisualizerSettingsStore(tab, mode).snapshot()[key] == pytest.approx(target), f"{mode}: reopen"


def test_a_plain_committed_view_row_snaps_back_negative_control(opened):
    """The former Sphere row: an ordinary committed edit of the view key, which the canonical save reads back."""
    import dataclasses
    controller, surface, _counter = opened("sphere")
    controller.store.set_include_view(False)
    schema = controller.session.schema
    prop = _view_props(controller, "sphere")[0]
    plain = dataclasses.replace(prop, view_pose=False)
    controller.bridge._schema = schema = dataclasses.replace(
        schema, properties=tuple(plain if p.id == prop.id else p for p in schema.properties))
    controller.session._schema = schema
    key = prop.path[0]
    saved = controller.session.committed_values[key]
    target = _target(prop, float(saved))
    _drag(controller, surface, plain, target)
    assert controller.evaluation_values()[key] == pytest.approx(saved) != pytest.approx(target)
