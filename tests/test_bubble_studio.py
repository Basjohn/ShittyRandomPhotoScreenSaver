"""Bubble's Studio adapter on the shared Studio framework.

Structural: no preset values or UI wording are pinned. Truthfulness is proven against Bubble's production owners:
the frames the Studio evaluates are the production live path's frames (offline replay through ``logical_tick``),
byte for byte, and the production renderer draws them identically. Bubble Temporal Fidelity: one production
logical step per input tick, nothing batched or decimated, and the app's random stream untouched. Nothing shows a
window (the shell renders through QQuickRenderControl; the Settings dialog is never shown).
"""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import Choice, Colour, Gradient, Slider, require_mode_settings
from ui.studio.bubble_adapter import (
    STEP, BubbleStudioAdapter, BubbleStudioEvaluator, SyntheticInputs, build_schema, simulation_keys,
)
from ui.studio.bubble_recorded_inputs import extract, frame_digest, to_inputs

MODE = "bubble"
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
    """Registry keys (every spec control, every technical control) with no Studio property, plus elements of a
    vector control (gradient endpoints, a colour's alpha) that no property edits."""
    paths = {tuple(p.path) for p in properties}
    roots = {p.path[0] for p in properties}
    missing = {c.key for c in spec().controls if c.key not in roots} | (technical_keys() - roots)
    for control in spec().controls:
        if isinstance(control, Gradient):
            missing |= {f"{control.key}.{i}" for i in range(4) if (control.key, i) not in paths}
        if isinstance(control, Colour) and control.alpha and (control.key, 3) not in paths:
            missing.add(f"{control.key}.3")
    return missing


def test_every_bubble_control_is_editable_in_the_studio():
    assert _uncovered(build_schema().properties) == set()


def test_coverage_check_detects_a_missing_control_negative_control():
    properties = build_schema().properties
    for dropped in (PREFIX + "big_count", PREFIX + "drift_direction", PREFIX + "transient_mix_bass"):
        assert dropped in _uncovered([p for p in properties if p.path[0] != dropped])
    alpha = next(c.key for c in spec().controls if isinstance(c, Colour) and c.alpha)
    assert f"{alpha}.3" in _uncovered([p for p in properties if tuple(p.path) != (alpha, 3)])


def test_instruments_bounds_choices_and_conditions_come_from_the_registry():
    schema = build_schema()
    for control in spec().controls:
        if isinstance(control, Slider):
            prop = schema.find(control.key)
            assert (prop.minimum, prop.maximum) == (control.low, control.high), control.key
        elif isinstance(control, Choice):
            prop = schema.find(control.key)
            assert tuple(prop.choice_values or prop.choices) == tuple(
                control.choices if not control.indexed else range(len(control.choices))), control.key
        if control.when and control.key in {p.id for p in schema.properties}:
            assert schema.find(control.key).when, control.key
    for key in technical_keys():
        assert schema.find(key).workspace == "reactivity"


def test_admission_is_the_registry_owners():
    schema = build_schema()
    big = spec().control(PREFIX + "big_count")
    assert schema.admit(big.key, big.high * 10, big.low) == big.admit(big.high * 10, big.low)
    assert schema.admit(PREFIX + "transient_mix_bass", 9.0, 0.1) <= 1.0


# ------------------------------------------------------------------- production parity
def _replay(clip, values, seconds, **kwargs):
    from ui.studio.adapter import RECORDED, StudioFixture
    data = extract(clip, values, seconds=seconds, **kwargs)
    fixture = StudioFixture("clip:test", "Test Clip", RECORDED, float(data["duration"]), str(clip))
    evaluator = BubbleStudioEvaluator()
    evaluator.add_recorded(to_inputs(data, fixture))
    evaluator.select("clip:test")
    return data, evaluator


def _schema2_clip():
    """(the shared recordings' smallest schema 2 clip, preferring one with typed events early, has events)."""
    from ui.studio.waveform_adapter import recordings_directory
    directory = recordings_directory()
    clips = sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_size) if directory.is_dir() else []
    found = []
    for clip in clips:
        with open(clip, "rb") as stream:
            head = stream.read(400_000)
        if b'"real":{' in head:
            found.append((b'"events":[{' not in head, clip))
    return (found[0][1], not found[0][0]) if found else (None, False)


@pytest.mark.parametrize("source", ["fixture", "recording"])
def test_studio_frames_equal_the_production_live_path_frame_for_frame(qt_app, source):
    """The production offline replay (``logical_tick`` on a configured controller, deterministic clock) and the
    Studio's evaluator build byte-identical Bubble frames (positions, extras, trails, classes, ambience, timestamps,
    diagnostics, renderer parameters) at every logical tick, including typed-event consumption (schema 2)."""
    clip, events = (REPLAY_FIXTURE, False) if source == "fixture" else _schema2_clip()
    if clip is None:
        pytest.skip("No schema 2 visualizer recording available")
    values = canonical_section()
    data, evaluator = _replay(clip, values, 3.0)
    steps = [s for s in data["steps"] if "frame_sha256" in s]
    assert len(steps) >= 50
    for step in steps:
        frame = evaluator.evaluate(step["now_ts"] - data["origin"], values)
        assert frame_digest(frame) == step["frame_sha256"], step["now_ts"]
    if events:
        assert any(s["events"] for s in data["steps"])          # typed events were served and consumed
    evaluator.release()


def test_parity_check_detects_a_perturbed_input_negative_control(qt_app):
    from dataclasses import replace
    from ui.studio.adapter import RECORDED, StudioFixture
    from ui.studio.bubble_adapter import RecordedInputs
    values = canonical_section()
    data = extract(REPLAY_FIXTURE, values, seconds=1.5)
    inputs = to_inputs(data, StudioFixture("clip:bad", "Bad", RECORDED, float(data["duration"]), ""))
    steps = list(inputs._steps)
    middle = len(steps) // 2
    steps[middle] = replace(steps[middle], bubble=(1.0, 1.0, 1.0, 1.0))
    evaluator = BubbleStudioEvaluator()
    evaluator.add_recorded(RecordedInputs(inputs.fixture, tuple(steps), inputs._origin))
    evaluator.select("clip:bad")
    late = [s for s in data["steps"] if "frame_sha256" in s][middle:]
    mismatched = sum(frame_digest(evaluator.evaluate(s["now_ts"] - data["origin"], values)) != s["frame_sha256"]
                     for s in late[:5])
    assert mismatched >= 1
    evaluator.release()


def test_one_production_step_per_tick_and_the_apps_random_stream_is_untouched(qt_app):
    values = canonical_section()
    evaluator = BubbleStudioEvaluator()
    random.seed(4242)
    before = random.getstate()
    evaluator.evaluate(2.0, values)
    assert random.getstate() == before
    ticks = sum(1 for tick in SyntheticInputs("mid").steps(2.0))
    assert evaluator.steps_run == ticks                          # 90 Hz authored ticks, none batched or skipped
    steps = [t.now for t in SyntheticInputs("mid").steps(1.0)]
    assert all(abs((b - a) - STEP) < 1e-9 for a, b in zip(steps, steps[1:]))
    evaluator.release()


def test_render_side_edits_never_step_and_logical_edits_replay_exactly(qt_app):
    values = canonical_section()
    evaluator = BubbleStudioEvaluator()
    frame = evaluator.evaluate(2.0, values)
    ran = evaluator.steps_run
    styled = dict(values)
    colour = PREFIX + "outline_color"
    styled[colour] = [255 - int(v) for v in values[colour][:3]] + list(values[colour][3:])
    restyled = evaluator.evaluate(2.0, styled)
    assert evaluator.steps_run == ran                            # a colour is not a simulation input
    assert restyled.positions == frame.positions and restyled.parameters != frame.parameters
    assert colour not in simulation_keys()
    edited = dict(values)
    key = PREFIX + "big_bass_pulse"
    edited[key] = spec().control(key).high if values[key] != spec().control(key).high else spec().control(key).low
    replayed = evaluator.evaluate(2.0, edited)
    fresh = BubbleStudioEvaluator().evaluate(2.0, edited)
    assert frame_digest(replayed) == frame_digest(fresh) != frame_digest(frame)
    evaluator.release()


def test_the_card_extent_is_bubbles_logical_domain(qt_app):
    values = canonical_section()
    evaluator = BubbleStudioEvaluator()
    baseline = evaluator.evaluate(1.0, values)
    evaluator.set_viewport_extent((1680.0, 420.0))
    wide = evaluator.evaluate(1.0, values)
    domain = dict(wide.geometry_diagnostics)
    assert domain["domain_w"] > dict(baseline.geometry_diagnostics)["domain_w"]
    evaluator.release()


# -------------------------------------------------------------------- Settings + shell
@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="BubbleStudio",
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


class NoClips(BubbleStudioAdapter):
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


def test_custom_body_offers_the_bubble_studio(qt_app, dialog_tab, monkeypatch):
    from ui.studio import settings_link
    _dialog, tab = dialog_tab()
    button = getattr(tab, f"_{MODE}_studio_button")
    assert getattr(tab, f"_{MODE}_settings_container").isAncestorOf(button)
    calls = []
    monkeypatch.setattr(settings_link, "open_mode_studio", lambda t, m: calls.append((t, m)))
    button.click()
    assert calls == [(tab, MODE)]


def test_edits_save_through_bubbles_settings_owners_and_every_exit_restores_settings(
        qt_app, dialog_tab, settings_manager, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump(2)
    assert controller.state == "presented" and controller.presence.concealed
    bridge = controller.bridge
    stored = lambda: settings_manager.get("widgets")["spotify_visualizer"]      # noqa: E731
    # A slider, the Swirl row's drift direction (a Custom Settings row), a colour's alpha and a technical value.
    count = PREFIX + "big_count"
    control = spec().control(count)
    target = control.low if controller.session.values[count] != control.low else control.high
    bridge.commitValue(count, 0, target)
    assert stored()[count] == target
    drift = spec().control(PREFIX + "drift_direction")
    want = next(v for v in drift.choices if v != controller.session.values[drift.key])
    bridge.commitValue(drift.key, 0, drift.labels[drift.choices.index(want)])
    assert stored()[drift.key] == want
    alpha = next(c.key for c in spec().controls if isinstance(c, Colour) and c.alpha)
    bridge.commitValue(f"{alpha}.3", 0, 100)
    assert stored()[alpha][3] == 100
    mix = PREFIX + "transient_mix_vocal"
    bridge.commitValue(mix, 0, 0.5)
    assert stored()[mix] == pytest.approx(0.5)
    bridge.requestClose()
    assert _settings_restored(controller, dialog)
    # Esc and the window's own close both restore Settings too.
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
    """Opened on Fill: the picture spans the viewport's width. The production renderer draws the Studio's frame and
    the production live path's frame for the same tick to identical pixels."""
    import numpy as np
    from PySide6.QtCore import QCoreApplication
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
    from PySide6.QtCore import QPointF
    slot = surface.host.slot
    origin = slot.mapToScene(QPointF(slot.property("frameX"), slot.property("frameY")))
    x, y = int(origin.x()), int(origin.y())
    w, h = int(slot.property("frameWidth")), int(slot.property("frameHeight"))
    pixels = surface.grab()[y + 10:y + h - 10, x + 10:x + w - 10, :3]
    assert pixels.std() > 4.0                                   # bubbles drawn, not a placeholder

    values = dict(controller.evaluation_values())
    captured: list = []
    data = extract(REPLAY_FIXTURE, values, seconds=1.0, frames_out=captured)
    from ui.studio.adapter import RECORDED, StudioFixture
    evaluator = BubbleStudioEvaluator()
    evaluator.add_recorded(to_inputs(data, StudioFixture("clip:r", "R", RECORDED, data["duration"], "")))
    evaluator.select("clip:r")
    now, live = captured[-1]
    studio = evaluator.evaluate(now - data["origin"], values)
    images = {}

    def ready(key, width, height, raw):
        images[key] = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)
    surface.viewport.snapshotReady.connect(ready)
    extent = controller.presented_extent()
    for key, frame in (("live", live), ("studio", studio)):
        surface.viewport.request_snapshot(key, frame, (480, 320), (480.0, 320.0), extent, ())
    for _ in range(60):
        surface.pump()
        QCoreApplication.processEvents()
        if len(images) == 2:
            break
    assert set(images) == {"live", "studio"}
    assert images["live"][..., :3].std() > 2.0
    assert np.array_equal(images["live"], images["studio"])
    evaluator.release()
    controller.close()
