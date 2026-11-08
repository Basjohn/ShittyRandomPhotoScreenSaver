"""A Studio edit never moves the preview camera (operator, 8 Nov: "studios reset the camera every slider change").

Every registered Studio whose adapter declares a camera is opened from its real Settings body, on a curated preset
(the edit is held as an unsaved draft) and on Custom, with the preset's "Include current camera view" choice on (the
default: the orbit is committed) and off (the orbit stays a preview view). The preview camera is orbited and, where the
mode has them, zoomed, dollied and panned; then an unrelated slider is dragged and an unrelated switch is flipped. Every
camera axis the evaluator is handed after each edit is the one the operator set, and the canonical store still holds a
committed orbit. A camera setting edited itself applies exactly that value and leaves the other axes alone.

The cause was the store's commit: it loads the whole value map into Settings, which re-hydrates the framed camera
editor's pose as if those values were saved and clears its aim, so on a curated preset (whose draft is never saved)
the draft read the preset's own view back after every edit. Negative control: that former rule (an orbit held only by
the commit that moved it) resets the camera. Hidden offscreen surfaces only; nothing is shown.
"""
from __future__ import annotations

import pytest

from ui.studio.registry import create_adapter, studio_modes
from tests.test_studio_exit_every_mode import light_adapter

CAMERA_MODES = sorted(entry.mode_id for entry in studio_modes() if create_adapter(entry.mode_id).capabilities().camera)
AXES = ("orbit_h", "orbit_v", "zoom", "dolly", "pan_x", "pan_y")


def _framed_camera_modes() -> list[str]:
    from core.settings.framed_camera import spec_for_mode
    return [mode for mode in CAMERA_MODES if spec_for_mode(mode) is not None]


@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="StudioCamera",
                              storage_base_dir=tmp_path / "profile")
    yield manager
    assert manager.flush(timeout=5.)


@pytest.fixture
def mode_dialog(qt_app, settings_manager):
    """A never-shown dialog around the real Visualizers tab, with ``mode`` on the preset slot ``slot``."""
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.visualizers_tab import VisualizersTab
    built = []

    def build(mode, slot):
        custom = get_custom_preset_index(mode)
        if slot == "curated" and custom < 1:
            pytest.skip(f"{mode} has no curated preset")
        settings_manager.set("widgets", {"spotify_visualizer": {
            "enabled": True, "visualizers_enabled": True, "mode": mode,
            "mode_activation": build_visualizer_mode_activation([mode]),
            f"preset_{mode}": 0 if slot == "curated" else custom}})
        dialog = QDialog()
        QVBoxLayout(dialog).addWidget(tab := VisualizersTab(settings_manager))
        tab._select_mode_page(mode)
        built.append(dialog)
        return tab
    yield build
    for dialog in built:
        dialog.deleteLater()
    qt_app.processEvents()


@pytest.fixture(autouse=True)
def _no_open_studio():
    from ui.studio.controller import StudioController
    yield
    active = StudioController.active()
    if active is not None:
        active.close()


@pytest.fixture
def no_gl_checks():
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()


class Session:
    """One Studio on the hidden offscreen surface, recording the values its evaluator is handed."""

    def __init__(self, tab, mode: str) -> None:
        from ui.studio.settings_link import open_mode_studio
        from ui.studio.surface import OffscreenStudioSurface
        surfaces = []

        def factory(controller):
            surfaces.append(OffscreenStudioSurface(controller, size=(1280, 760), present_on_show=False))
            return surfaces[-1]
        self.controller = open_mode_studio(tab, mode, adapter=light_adapter(mode), surface_factory=factory)
        self.surface = surfaces[0]
        self.surface.pump(3)
        assert self.controller.state == "presented"
        self.handed: list[dict] = []
        evaluator = self.controller.evaluator
        evaluate = evaluator.evaluate

        def recording(time, values, **kwargs):
            self.handed.append(dict(values))
            return evaluate(time, values, **kwargs)
        evaluator.evaluate = recording
        self.nav = self.controller.navigation()
        assert self.nav is not None, f"{mode} declares a camera but offers no navigation"
        self.axes = {name: getattr(self.nav, name) for name in AXES if getattr(self.nav, name) is not None}

    def view(self) -> dict[str, float]:
        """The camera the controller hands the evaluator now (preview pose over the committed values)."""
        values = self.controller.evaluation_values()
        return {axis.key: float(values[axis.key]) for axis in self.axes.values()}

    def evaluated_view(self) -> dict[str, float]:
        """The camera of the next frame's evaluation."""
        self.handed.clear()
        self.controller._invalidate()
        self.surface.pump(2)
        assert self.handed, "no frame was evaluated"
        return {axis.key: float(self.handed[-1][axis.key]) for axis in self.axes.values()}

    def move_camera(self) -> dict[str, float]:
        """Orbit, and zoom, dolly and pan where the mode has them; then the navigation ends (as on release)."""
        controller = self.controller
        before = self.view()
        controller.orbit_by(120.0, 40.0)
        if "zoom" in self.axes:
            controller.zoom_by(2.0)
        if "dolly" in self.axes:
            controller.zoom_by(1.0, dolly=True)
        if "pan_x" in self.axes:
            controller.pan_by(30.0, 20.0, 600.0, 400.0)
        controller.end_orbit()
        moved = self.view()
        assert moved[self.axes["orbit_h"].key] != before[self.axes["orbit_h"].key], "the orbit did not move"
        return moved

    def _unrelated(self, instrument: str):
        """The first shown plain property of ``instrument`` that is no camera axis and no engine-owned value."""
        session, bridge = self.controller.session, self.controller.bridge
        camera = {axis.key for axis in self.axes.values()}
        hidden = bridge.conditionHidden
        for prop in session.schema.properties:
            if (prop.instrument == instrument and len(prop.path) == 1 and not prop.view_pose
                    and prop.path[0] not in camera and not hidden.get(prop.id)
                    and prop.path[0] not in self.controller.release_only_keys):
                return prop
        raise AssertionError(f"no unrelated {instrument} to edit")

    def drag_unrelated_slider(self) -> None:
        """A slider drag: previews on the frame edge, one commit on release."""
        from ui.studio.schema import SCALAR
        prop = self._unrelated(SCALAR)
        session, bridge = self.controller.session, self.controller.bridge
        value = float(session.values[prop.path[0]])
        target = prop.minimum if abs(value - prop.minimum) > abs(prop.maximum - value) else prop.maximum
        saves = session.commit_count
        bridge.beginEdit(prop.id, prop.label)
        for step in (0.25, 0.6, 1.0):
            bridge.previewValue(prop.id, 0, value + (target - value) * step)
            self.surface.pump()
        bridge.endEdit()
        assert session.commit_count == saves + 1, f"{prop.id} was not committed"

    def flip_unrelated_switch(self) -> None:
        from ui.studio.schema import SWITCH
        prop = self._unrelated(SWITCH)
        session = self.controller.session
        saves = session.commit_count
        self.controller.bridge.commitValue(prop.id, 0, not bool(session.values[prop.path[0]]))
        assert session.commit_count == saves + 1, f"{prop.id} was not committed"

    def commit_camera_value(self, axis_name: str) -> tuple[str, float]:
        """A camera setting edited in the inspector: its own row, moved toward the far end of its range."""
        axis = self.axes[axis_name]
        prop = next(p for p in self.controller.session.schema.properties if p.path == (axis.key,))
        value = self.view()[axis.key]
        low, high = axis.bounds
        target = round(value + ((low if value - low > high - value else high) - value) * 0.5, 3)
        self.controller.bridge.commitValue(prop.id, 0, target)
        return axis.key, target


def _committed_orbit(session: Session) -> dict[str, float]:
    snapshot = session.controller.store.snapshot()
    return {session.axes[name].key: float(snapshot[session.axes[name].key]) for name in ("orbit_h", "orbit_v")}


def _assert_same_view(actual: dict, expected: dict, what: str) -> None:
    assert actual == pytest.approx(expected), f"{what}: the camera moved"


@pytest.mark.parametrize("slot", ["curated", "custom"])
@pytest.mark.parametrize("mode", CAMERA_MODES)
def test_unrelated_edits_keep_the_preview_camera(qt_app, mode_dialog, no_gl_checks, mode, slot):
    session = Session(mode_dialog(mode, slot), mode)
    controller = session.controller
    for include in (True, False):
        controller.reset_camera()
        controller.store.set_include_view(include)
        moved = session.move_camera()
        committed = bool(controller.store.camera_commit_allowed())
        if committed:
            _assert_same_view(_committed_orbit(session), {k: moved[k] for k in _committed_orbit(session)},
                              f"{mode} {slot}: the orbit commit")
        for edit in (session.drag_unrelated_slider, session.flip_unrelated_switch):
            edit()
            what = f"{mode} {slot} include_view={include} after {edit.__name__}"
            _assert_same_view(session.view(), moved, what)
            _assert_same_view(session.evaluated_view(), moved, what + " (evaluated frame)")
            if committed:
                _assert_same_view(_committed_orbit(session), {k: moved[k] for k in _committed_orbit(session)},
                                  what + " (stored orbit)")


@pytest.mark.parametrize("mode", CAMERA_MODES)
def test_a_camera_setting_applies_only_that_value(qt_app, mode_dialog, no_gl_checks, mode):
    """Editing a camera axis in the inspector sets that axis and nothing else of the operator's view."""
    session = Session(mode_dialog(mode, "curated"), mode)
    names = [name for name in ("zoom", "orbit_h") if name in session.axes]
    for name in names:
        moved = session.move_camera()
        key, target = session.commit_camera_value(name)
        applied = session.view()[key]                         # as the row admits it (an integer lens stays whole)
        assert applied == pytest.approx(target, abs=0.5) and applied != pytest.approx(moved[key]), key
        expected = dict(moved, **{key: applied})
        _assert_same_view(session.view(), expected, f"{mode} after editing {key}")
        _assert_same_view(session.evaluated_view(), expected, f"{mode} after editing {key} (evaluated frame)")


@pytest.mark.parametrize("mode", _framed_camera_modes())
def test_the_former_aim_rule_resets_the_camera_negative_control(qt_app, mode_dialog, no_gl_checks, monkeypatch,
                                                                mode):
    """With the store's former rule (the orbit is aimed only by the commit that moved it), an unrelated edit on a
    curated preset reads the preset's view back: the check above sees the camera reset."""
    from ui.tabs.media import framed_camera_editor as fce
    original = fce.hold_aim

    def former(tab, mode_id, values, *, aimed=False):
        return original(tab, mode_id, values, aimed=True) if aimed else False
    monkeypatch.setattr(fce, "hold_aim", former)
    session = Session(mode_dialog(mode, "curated"), mode)
    session.controller.store.set_include_view(True)
    assert session.controller.store.camera_commit_allowed()
    moved = session.move_camera()
    session.drag_unrelated_slider()
    orbit = {key: moved[key] for key in _committed_orbit(session)}
    with pytest.raises(AssertionError, match="the camera moved"):
        _assert_same_view(session.view(), moved, f"{mode} under the former rule")
    assert _committed_orbit(session) != pytest.approx(orbit)
