"""Voxel Sphere's Studio adapter on the shared Studio framework.

Structural: no preset counts, preset values or UI wording are pinned (presets are authored, mutable content).
Truthfulness is proven against Sphere's production owners: the logical frames the Studio evaluates are the
production live path's (offline replay through ``logical_tick``, whose capture resolves the Sphere runtime), byte for
byte, and the production renderer draws them identically. Settings' Finish coupling and Frequency Zones rules carry
over. Nothing shows a window.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import Choice, Colour, Slider, require_mode_settings
from ui.studio.sphere_adapter import (
    NOTCH_KEY, STEP, SphereStudioAdapter, SphereStudioEvaluator, SyntheticInputs, build_schema, finish_presets,
)
from ui.studio.sphere_recorded_inputs import extract, frame_digest, to_inputs

MODE = "sphere"
PREFIX = MODE + "_"
ROOT = Path(__file__).resolve().parents[1]
REPLAY_FIXTURE = ROOT / "tests" / "fixtures" / "visualizer_replay" / "v1" / "beats_120_bpm.jsonl"


def spec():
    return require_mode_settings(MODE)


def canonical_section():
    """Test-owned inputs: the code-owned canonical defaults, never an authored preset."""
    out = dict(require_canonical_default("widgets.spotify_visualizer"))
    for control in spec().controls:
        out[control.key] = control.admit(out[control.key], out[control.key])
    return out


def technical_keys():
    from ui.tabs.media.technical_controls import _control_defs_for_mode, _storage_key
    return {_storage_key(MODE, d) for d in _control_defs_for_mode(MODE)}


# ------------------------------------------------------------------------------- schema
def _uncovered(properties) -> set[str]:
    """Registry keys (every spec control, every Custom row's own keys, every technical control) with no Studio
    property, plus vector elements no property edits (a colour's alpha, the two zone boundaries)."""
    from core.settings.visualizer_mode_settings import Custom
    paths = {tuple(p.path) for p in properties}
    roots = {p.path[0] for p in properties}
    custom_keys = {key for e in spec().entries if isinstance(e, Custom) for key in e.keys}
    missing = {c.key for c in spec().controls if c.key not in roots} | ((technical_keys() | custom_keys) - roots)
    for control in spec().controls:
        if isinstance(control, Colour) and control.alpha and (control.key, 3) not in paths:
            missing.add(f"{control.key}.3")
    missing |= {f"{NOTCH_KEY}.{i}" for i in (1, 2) if (NOTCH_KEY, i, 0) not in paths}
    return missing


def test_every_sphere_control_is_editable_in_the_studio():
    assert _uncovered(build_schema().properties) == set()


def test_coverage_check_detects_a_missing_control_negative_control():
    properties = build_schema().properties
    for dropped in (PREFIX + "finish", PREFIX + "turn", NOTCH_KEY, PREFIX + "transient_clamp"):
        assert _uncovered([p for p in properties if p.path[0] != dropped]), dropped
    assert f"{NOTCH_KEY}.2" in _uncovered([p for p in properties if tuple(p.path) != (NOTCH_KEY, 2, 0)])


def test_instruments_bounds_and_choices_come_from_the_registry():
    schema = build_schema()
    for control in spec().controls:
        prop = schema.find(control.key)
        if isinstance(control, Slider):
            assert (prop.minimum, prop.maximum) == (control.low, control.high), control.key
        elif isinstance(control, Choice):
            assert tuple(prop.choice_values or prop.choices) == tuple(control.choices), control.key


def test_finish_writes_gloss_and_specular_and_a_manual_axis_edit_marks_it_custom():
    """Settings' Finish bundle (sphere_builder) in the Studio session: one undoable edit each way."""
    from ui.studio.session import StudioEditSession

    class Store:
        def __init__(self):
            self.values = canonical_section()

        def snapshot(self):
            return dict(self.values)

        def commit(self, values, changed):
            self.values.update(values)
            return dict(self.values)

        def preset_label(self):
            return "Custom"
    session = StudioEditSession(build_schema(), Store())
    finish, gloss, specular = PREFIX + "finish", PREFIX + "gloss", PREFIX + "specular"
    name, (g, s) = next(item for item in finish_presets().items() if item[0] != session.values[finish])
    before = (session.values[gloss], session.values[specular])
    session.set((finish,), name, "Finish")
    assert session.values[finish] == name
    assert (session.values[gloss], session.values[specular]) == pytest.approx((g, s))
    session.set((gloss,), 0.5 if abs(g - 0.5) > 1e-3 else 0.4, "Gloss")
    assert session.values[finish] == "Custom"
    session.undo()
    assert session.values[finish] == name
    session.undo()
    assert (session.values[gloss], session.values[specular]) == pytest.approx(before)


def test_zone_boundaries_follow_settings_rule_and_the_canonical_normalizer():
    schema = build_schema()
    notches = canonical_section()[NOTCH_KEY]
    high = notches[2][0]
    moved = [list(r) for r in notches]
    moved[1][0] = min(1.0, high + 0.2)                       # past the other boundary: stops at it
    admitted = schema.admit(NOTCH_KEY, moved, notches)
    assert admitted[1][0] == pytest.approx(high) and admitted[2][0] == pytest.approx(high)
    assert admitted[0][0] == 0.0 and admitted[-1][0] == 1.0 and len(admitted) == 4


# ------------------------------------------------------------------- production parity
def _shipped_clip():
    from ui.studio.waveform_adapter import recordings_directory
    from ui.studio.waveform_recorded_inputs import studio_clips
    clips = studio_clips(recordings_directory())
    return clips[0].description if clips else None


def _replay(clip, values, seconds, **kwargs):
    from ui.studio.adapter import RECORDED, StudioFixture
    data = extract(clip, values, seconds=seconds, **kwargs)
    fixture = StudioFixture("clip:test", "Test Clip", RECORDED, float(data["duration"]), str(clip))
    evaluator = SphereStudioEvaluator()
    evaluator.add_recorded(to_inputs(data, fixture))
    evaluator.select("clip:test")
    return data, evaluator


@pytest.mark.parametrize("source", ["fixture", "shipped_clip"])
def test_studio_frames_equal_the_production_live_path_frame_for_frame(qt_app, source):
    """The production offline replay and the Studio's evaluator build byte-identical Sphere frames (every resolved
    drive, phase, section, cohort and renderer parameter) at every capture, typed events included."""
    clip = REPLAY_FIXTURE if source == "fixture" else _shipped_clip()
    if clip is None:
        pytest.skip("No shipped Studio clip in this checkout")
    values = canonical_section()
    data, evaluator = _replay(clip, values, 3.0)
    steps = [s for s in data["steps"] if "frame_sha256" in s]
    assert len(steps) >= 50
    for step in steps:
        frame = evaluator.evaluate(step["now_ts"] - data["origin"], values)
        assert frame_digest(frame.mode_state) == step["frame_sha256"], step["now_ts"]
    if source == "shipped_clip":
        assert any(s["events"] for s in data["steps"])          # typed events were served and consumed
    evaluator.release()


def test_parity_check_detects_a_perturbed_input_negative_control(qt_app):
    from dataclasses import replace
    from ui.studio.adapter import RECORDED, StudioFixture
    from ui.studio.sphere_adapter import RecordedInputs
    values = canonical_section()
    data = extract(REPLAY_FIXTURE, values, seconds=1.5)
    inputs = to_inputs(data, StudioFixture("clip:bad", "Bad", RECORDED, float(data["duration"]), ""))
    steps = list(inputs._steps)
    middle = len(steps) // 2
    steps[middle] = replace(steps[middle], energy=(1.0, 1.0, 1.0, 1.0), live=(2.5, 2.5, 2.5, 2.5))
    evaluator = SphereStudioEvaluator()
    evaluator.add_recorded(RecordedInputs(inputs.fixture, tuple(steps), inputs._origin))
    evaluator.select("clip:bad")
    late = [s for s in data["steps"] if "frame_sha256" in s][middle:]
    mismatched = sum(frame_digest(evaluator.evaluate(s["now_ts"] - data["origin"], values).mode_state)
                     != s["frame_sha256"] for s in late[:5])
    assert mismatched >= 1
    evaluator.release()


def test_one_production_capture_per_tick_and_exact_replay(qt_app):
    values = canonical_section()
    evaluator = SphereStudioEvaluator()
    frame = evaluator.evaluate(2.0, values)
    assert evaluator.steps_run == sum(1 for _ in SyntheticInputs("mid").steps(2.0))
    steps = [t.now for t in SyntheticInputs("mid").steps(1.0)]
    assert all(abs((b - a) - STEP) < 1e-9 for a, b in zip(steps, steps[1:]))
    edited = dict(values)
    key = PREFIX + "fragment_strength"
    control = spec().control(key)
    edited[key] = control.high if values[key] != control.high else control.low
    replayed = evaluator.evaluate(2.0, edited)
    fresh = SphereStudioEvaluator().evaluate(2.0, edited)
    assert frame_digest(replayed.mode_state) == frame_digest(fresh.mode_state) != frame_digest(frame.mode_state)
    evaluator.release()


# -------------------------------------------------------------------- Settings + shell
@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="SphereStudio",
                              storage_base_dir=tmp_path / "profile")
    yield manager
    assert manager.flush(timeout=5.)


@pytest.fixture
def no_gl_checks():
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()


@pytest.fixture(autouse=True)
def _no_open_studio():
    from ui.studio.controller import StudioController
    yield
    active = StudioController.active()
    if active is not None:
        active.close()
    assert StudioController.active() is None


@pytest.fixture
def dialog_tab(qt_app, settings_manager):
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.visualizers_tab import VisualizersTab
    built = []

    def build():
        settings_manager.set("widgets", {"spotify_visualizer": {
            "enabled": True, "visualizers_enabled": True, "mode": MODE,
            "mode_activation": build_visualizer_mode_activation([MODE]),
            f"preset_{MODE}": get_custom_preset_index(MODE)}})
        dialog = QDialog()
        QVBoxLayout(dialog).addWidget(tab := VisualizersTab(settings_manager))
        tab._select_mode_page(MODE)
        built.append(dialog)
        return dialog, tab
    yield build
    for dialog in built:
        dialog.deleteLater()
    qt_app.processEvents()


class NoClips(SphereStudioAdapter):
    def recorded_clips(self):
        return ()


class QuietRenderer:
    def prepare(self, card, frame):
        return True

    def render(self, card, frame):
        pass

    def release(self):
        pass


class LightAdapter(NoClips):
    def create_renderer(self):
        return QuietRenderer()


def _surfaces(store, size=(1280, 760)):
    from ui.studio.surface import OffscreenStudioSurface

    def factory(controller):
        surface = OffscreenStudioSurface(controller, size=size, present_on_show=False)
        store.append(surface)
        return surface
    return factory


def _settings_restored(controller, dialog) -> bool:
    from ui.studio.controller import StudioController
    presence = controller.presence
    return (controller.state == "closed" and StudioController.active() is None and not presence.concealed
            and presence.widget is dialog and dialog.isEnabled())


def test_custom_body_offers_the_sphere_studio(qt_app, dialog_tab, monkeypatch):
    from ui.studio import settings_link
    _dialog, tab = dialog_tab()
    button = getattr(tab, f"_{MODE}_studio_button")
    assert getattr(tab, f"_{MODE}_settings_container").isAncestorOf(button)
    calls = []
    monkeypatch.setattr(settings_link, "open_mode_studio", lambda t, m: calls.append((t, m)))
    button.click()
    assert calls == [(tab, MODE)]


def test_edits_save_through_spheres_settings_owners_and_every_exit_restores_settings(
        qt_app, dialog_tab, settings_manager, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump(2)
    assert controller.state == "presented" and controller.presence.concealed
    bridge = controller.bridge
    stored = lambda: settings_manager.get("widgets")["spotify_visualizer"]      # noqa: E731
    # A Finish (a Custom row that writes two sliders), a zone boundary, a colour's alpha and a technical value.
    finish = PREFIX + "finish"
    name, (gloss, specular) = next(item for item in finish_presets().items()
                                   if item[0] != controller.session.values[finish])
    bridge.commitValue(finish, 0, name)
    assert stored()[finish] == name
    assert (stored()[PREFIX + "gloss"], stored()[PREFIX + "specular"]) == pytest.approx((gloss, specular))
    low = controller.session.values[NOTCH_KEY][1][0]
    bridge.commitValue(f"{NOTCH_KEY}.1", 0, round(low * 0.5, 3))
    assert stored()[NOTCH_KEY][1][0] == pytest.approx(round(low * 0.5, 3))
    bridge.commitValue(PREFIX + "fill_color.3", 0, 120)
    assert stored()[PREFIX + "fill_color"][3] == 120
    bridge.commitValue(PREFIX + "transient_clamp", 0, 0.5)
    assert stored()[PREFIX + "transient_clamp"] == pytest.approx(0.5)
    bridge.requestClose()
    assert _settings_restored(controller, dialog)
    for path in ("escape", "window"):
        surfaces.clear()
        controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
        surfaces[0].pump(2)
        if path == "escape":
            from PySide6.QtCore import QCoreApplication, QEvent, Qt
            from PySide6.QtGui import QKeyEvent
            surfaces[0].host.root.forceActiveFocus()
            for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                QCoreApplication.sendEvent(surfaces[0].window, QKeyEvent(kind, Qt.Key.Key_Escape,
                                                                         Qt.KeyboardModifier.NoModifier))
            for _ in range(5):
                QCoreApplication.processEvents()
        else:
            surfaces[0].closeRequested.emit()
        assert _settings_restored(controller, dialog), path


def test_restore_check_detects_a_concealed_settings_negative_control(qt_app, dialog_tab, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump(2)
    assert not _settings_restored(controller, dialog)
    controller.close()
    assert _settings_restored(controller, dialog)


def test_the_production_renderer_fills_the_viewport_and_draws_the_live_paths_frame_identically(
        qt_app, dialog_tab, no_gl_checks):
    import numpy as np
    from PySide6.QtCore import QCoreApplication, QPointF
    from ui.studio.adapter import RECORDED, StudioFixture
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=NoClips(), surface_factory=_surfaces(surfaces))
    surface = surfaces[0]
    for _ in range(400):
        surface.pump()
        if controller.bridge.viewportStatus != "preparing":
            break
    assert controller.bridge.viewportStatus == "live", controller.bridge.viewportError
    assert controller.bridge.framingId == "fill"
    assert surface.viewport.width() == pytest.approx(surface.host.slot.width())
    slot = surface.host.slot
    origin = slot.mapToScene(QPointF(slot.property("frameX"), slot.property("frameY")))
    x, y = int(origin.x()), int(origin.y())
    w, h = int(slot.property("frameWidth")), int(slot.property("frameHeight"))
    assert surface.grab()[y + 10:y + h - 10, x + 10:x + w - 10, :3].std() > 4.0     # voxels drawn

    values = dict(controller.evaluation_values())
    captured: list = []
    data = extract(REPLAY_FIXTURE, values, seconds=1.0, frames_out=captured)
    evaluator = SphereStudioEvaluator()
    evaluator.add_recorded(to_inputs(data, StudioFixture("clip:r", "R", RECORDED, data["duration"], "")))
    evaluator.select("clip:r")
    now, live = captured[-1]
    studio = evaluator.evaluate(now - data["origin"], values)
    assert frame_digest(studio.mode_state) == frame_digest(live.mode_state)
    images = {}

    def ready(key, width, height, raw):
        images[key] = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)
    surface.viewport.snapshotReady.connect(ready)
    extent = controller.presented_extent()
    for key, frame in (("live", live), ("studio", studio)):
        surface.viewport.request_snapshot(key, frame, (480, 320), (480.0, 320.0), extent, ())
    for _ in range(80):
        surface.pump()
        QCoreApplication.processEvents()
        if len(images) == 2:
            break
    assert set(images) == {"live", "studio"}
    assert images["live"][..., :3].std() > 2.0
    assert np.array_equal(images["live"], images["studio"])
    evaluator.release()
    controller.close()
