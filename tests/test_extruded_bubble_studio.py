"""Extruded Bubble's Studio adapter on the shared Studio framework.

Structural: no preset values or UI wording are pinned (presets are authored and mutable). Truthfulness is proven
against EB's production owners: the presentation path for renderer parameters, the frame runtime for frames, the
production capture for recorded clips and the renderer's physical camera for handles. Nothing shows a window (the
shell renders through QQuickRenderControl; the Settings dialog is never shown).
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import (
    Choice, Colour, Range, SceneCameraPosition, ScenePath, Slider, Toggle, Triangle, require_mode_settings,
)
from ui.studio.extruded_bubble_adapter import (
    PATH_GROUP, ExtrudedBubbleStudioAdapter, ExtrudedBubbleStudioEvaluator, SyntheticInputs, build_frame,
    build_schema, frame_camera, hold_share, path_handles, project, render_parameters,
)
from ui.studio.extruded_bubble_recorded_inputs import frame_digest

MODE = "extruded_bubble"
PREFIX = MODE + "_"


def spec():
    return require_mode_settings(MODE)


def admitted(values):
    out = dict(values)
    for control in spec().controls:
        out[control.key] = control.admit(out[control.key], out[control.key])
    return out


def canonical_section():
    """Test-owned inputs: the code-owned canonical defaults, never an authored preset."""
    return admitted(require_canonical_default("widgets.spotify_visualizer"))


def preset_values(index):
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    return admitted(resolve_visualizer_activation_payload({"mode": MODE, f"preset_{MODE}": index},
                                                          mode=MODE).resolved_config)


def preset_count():
    from core.settings.visualizer_presets import get_custom_preset_index
    return get_custom_preset_index(MODE)


# ------------------------------------------------------------------------------- schema
def test_every_registry_control_is_editable_in_the_studio():
    """Coverage gate: the Studio replaces EB's builder, so no canonical EB control (nor any element of a vector
    control) may be unreachable. Schema-driven: a control added to the registry appears without Studio code
    changes, or this names it."""
    schema = build_schema()
    by_key: dict[str, list] = {}
    for prop in schema.properties:
        by_key.setdefault(prop.path[0], []).append(prop)
    missing = [c.key for c in spec().controls if c.key not in by_key]
    assert missing == [], f"Registry controls unreachable in the Extruded Bubble Studio: {missing}"
    values = canonical_section()
    for control in spec().controls:
        props = by_key[control.key]
        assert all(not p.instrument_only for p in props)
        if isinstance(control, (ScenePath, SceneCameraPosition, Triangle)):
            # Every element of the stored vector is its own row (no element silently fixed).
            assert sorted(p.path[1] for p in props) == list(range(len(values[control.key]))), control.key
        else:
            assert [p.path for p in props] == [(control.key,)], control.key
    groups = {(w.id, g) for w in schema.workspaces for g in w.groups}
    assert all((p.workspace, p.group) in groups for p in schema.properties)
    assert schema.keys <= set(values)


def test_instruments_and_bounds_come_from_the_registry_not_copies():
    schema = build_schema()
    by_id = {p.id: p for p in schema.properties}
    for control in spec().controls:
        label = (control.label.rstrip(":").strip() or (control.text if isinstance(control, Toggle) else "")).strip()
        if isinstance(control, Range):
            prop = by_id[control.key]
            assert prop.instrument == "quiet_peak" and (prop.minimum, prop.maximum) == (control.low, control.high)
            assert prop.integer == control.integer and prop.label == label
        elif isinstance(control, Slider) and control.bucket:
            prop = by_id[control.key]
            assert prop.instrument == "scalar" and (prop.minimum, prop.maximum) == (control.low, control.high)
            assert prop.label == label
        elif isinstance(control, Choice):
            assert by_id[control.key].choices == tuple(control.choices) and by_id[control.key].label == label
        elif isinstance(control, Toggle):
            assert by_id[control.key].instrument == "switch" and by_id[control.key].label == label
        elif isinstance(control, Colour):
            assert by_id[control.key].instrument == "colour"
        elif isinstance(control, Triangle):
            rows = [p for p in schema.properties if p.path[0] == control.key]
            assert all(corner in row.label for corner, row in zip(control.corners, rows))
    # Group titles are the registry's bucket titles (plus the per-path group, the live View and Settings'
    # Technical group, the audio analysis).
    from ui.studio.technical import TECHNICAL_GROUP
    titles = {bucket.title for bucket in spec().buckets}
    assert {g for w in schema.workspaces for g in w.groups} == titles | {PATH_GROUP, "View", TECHNICAL_GROUP}
    # The live view pose is preview-only (saved only through the preset's camera policy).
    view = [p for p in schema.properties if p.group == "View"]
    assert view and all(p.view_pose for p in view)


def test_headline_controls_lead_and_paths_belong_to_their_scene_objects():
    adapter = ExtrudedBubbleStudioAdapter()
    schema = adapter.schema()
    first = schema.workspaces[0]
    assert first.groups[0] == PATH_GROUP and set(first.open_groups) == set(first.groups)
    assert adapter.capabilities().as_map() == {"viewport": True, "camera": True, "handles": True, "objects": True,
                                               "brush": False}

    def first_row(group):
        rows = sorted((p for p in schema.properties if p.group == group), key=lambda p: p.priority)
        return rows[0].id
    titles = {bucket.key: bucket.title for bucket in spec().buckets}
    assert first_row(titles["light"]) == PREFIX + "light_type"
    assert first_row(titles["bubbles"]) == PREFIX + "large_bubbles"
    values = canonical_section()
    objects = adapter.scene_objects(values)
    paths = [c for c in spec().controls if isinstance(c, ScenePath)]
    assert [o.id for o in objects] == [c.key[len(PREFIX):] for c in paths]
    for obj, control in zip(objects, paths):
        rows = [p for p in schema.properties if p.object_scope == obj.id]
        assert {p.path[0] for p in rows} == {control.key} and len(rows) == 6
    # Only a path whose layer has a registry switch can be hidden, and the eye edits that switch.
    for obj in objects:
        edit = adapter.set_object_visible(values, obj.id, False)
        assert (edit is None) == (not obj.toggleable)
        if edit is not None:
            assert edit == (obj.visibility_path, False) and isinstance(spec().control(edit[0][0]), Toggle)


def test_editing_one_collision_share_holds_it_and_the_canonical_admission_still_applies():
    schema = build_schema()
    key = PREFIX + "collision"
    previous = list(canonical_section()[key])
    for index in range(3):
        for share in (0.0, 0.25, 0.8, 1.0):
            candidate = list(previous)
            candidate[index] = share
            out = schema.admit(key, candidate, previous)
            assert out == spec().control(key).admit(out, out)                   # canonical
            assert out[index] == pytest.approx(share, abs=1e-4) and sum(out) == pytest.approx(1.0, abs=1e-3)
            others = [i for i in range(3) if i != index]
            if share < 1.0 and previous[others[0]] + previous[others[1]] > 0:
                ratio = previous[others[0]] / (previous[others[0]] + previous[others[1]])
                assert out[others[0]] / (out[others[0]] + out[others[1]]) == pytest.approx(ratio, abs=2e-3)
    assert hold_share([1, 1, 1], [0.2, 0.3, 0.5]) == [1, 1, 1]               # not one-share edits: untouched


# ----------------------------------------------------------------------- truthful frames
def _production_presentation(values):
    """EB's renderer parameters through the production presentation owner (a configured offline controller)."""
    from widgets.spotify_visualizer import config_applier
    from widgets.spotify_visualizer.feature_replay import ReplayBeatEngine, configure_offline_controller
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    engine = ReplayBeatEngine(32)
    controller = VisualizerRuntimeController(runtime_generation=0, initial_mode=MODE, engine_factory=lambda _: engine)
    controller.engine = engine
    try:
        configure_offline_controller(controller, MODE, settings={**values, "mode": MODE})
        return config_applier.extruded_bubble_parameters(controller.presentation_state, 0.0)
    finally:
        engine.force_stop()


def test_renderer_parameters_equal_the_production_presentation_for_every_preset(qt_app):
    for index in range(preset_count()):
        values = preset_values(index)
        studio = render_parameters(values)
        production = _production_presentation(values)
        assert studio == production, f"preset {index + 1}"


def test_the_renderer_reads_only_parameters_the_studio_supplies():
    import re
    root = Path(__file__).resolve().parents[1]
    sources = [root / "rendering/quick/visualizer/implementations/extruded_bubble.py"]
    names = set()
    for source in sources:
        names |= set(re.findall(r'parameter\(parameters,\s*"([a-z0-9_]+)"\)', source.read_text(encoding="utf-8")))
    assert names and names <= set(render_parameters(canonical_section()))


def _direct(fixture_id, values, times):
    """A fresh production frame runtime driven directly with the fixture's inputs."""
    from widgets.spotify_visualizer.extruded_bubble_frame_runtime import (ExtrudedBubbleFrameRuntime,
                                                                          controls_from_parameters)
    parameters = render_parameters(values)
    controls = controls_from_parameters(parameters)
    runtime = ExtrudedBubbleFrameRuntime()
    out, snapshot = {}, None
    wanted = sorted(times)
    for step in SyntheticInputs(fixture_id).steps(max(wanted)):
        snapshot = runtime.advance(onsets=step.onsets, now_ts=step.now, playing=step.playing,
                                   identity=step.identity, source_identity=step.source_identity, controls=controls,
                                   body_bands=step.body_bands, play_ramping=step.play_ramping)
        for t in wanted:
            if t not in out and step.now >= t - 1e-9:
                out[t] = frame_digest(build_frame(snapshot, parameters))
    return out


@pytest.mark.parametrize("fixture_id", ["mid", "transient", "decay"])
def test_evaluator_frames_equal_the_production_runtime(fixture_id):
    values = canonical_section()
    times = (0.5, 3.0, 6.75)
    expected = _direct(fixture_id, values, times)
    evaluator = ExtrudedBubbleStudioEvaluator()
    evaluator.select(fixture_id)
    for t in times:
        assert frame_digest(evaluator.evaluate(t, values)) == expected[t]
    evaluator.release()


def test_fixtures_vary_the_body_lanes_independently():
    def lanes(fixture_id):
        steps = [s for s in SyntheticInputs(fixture_id).steps(10.0) if s.now >= 0]
        return [sum(s.body_bands[i] for s in steps) / len(steps) for i in range(3)]
    bass, mids, highs = lanes("bass"), lanes("mids"), lanes("highs")
    assert bass.index(max(bass)) == 0 and mids.index(max(mids)) == 1 and highs.index(max(highs)) == 2
    quiet, mid, peak = (sum(lanes(f)) for f in ("quiet", "mid", "peak"))
    assert quiet < mid < peak
    assert any(s.onsets for s in SyntheticInputs("mid").steps(10.0))


def test_render_side_edits_never_step_and_logical_edits_replay_exactly():
    values = canonical_section()
    evaluator = ExtrudedBubbleStudioEvaluator()
    evaluator.select("peak")
    base = evaluator.evaluate(5.0, values)
    steps = evaluator.steps_run
    restyled = evaluator.evaluate(5.0, {**values, PREFIX + "haze": 1.0 - float(values[PREFIX + "haze"])})
    assert evaluator.steps_run == steps                          # the simulation would step identically
    assert restyled.bubbles == base.bubbles and restyled.parameters != base.parameters
    low, high = values[PREFIX + "large_bubbles"]
    changed = {**values, PREFIX + "large_bubbles": [max(0, low - 2), max(0, high - 4)]}
    replayed = evaluator.evaluate(5.0, changed)
    assert evaluator.steps_run > steps
    fresh = ExtrudedBubbleStudioEvaluator()
    fresh.select("peak")
    assert frame_digest(replayed) == frame_digest(fresh.evaluate(5.0, changed))
    # Scrubbing backwards replays deterministically.
    again = ExtrudedBubbleStudioEvaluator()
    again.select("peak")
    assert frame_digest(evaluator.evaluate(2.0, changed)) == frame_digest(again.evaluate(2.0, changed))


def test_live_gesture_republishes_the_instant_without_moving_time():
    values = canonical_section()
    evaluator = ExtrudedBubbleStudioEvaluator()
    evaluator.select("mid")
    evaluator.evaluate(4.0, values)
    steps = evaluator.steps_run
    low, high = values[PREFIX + "stream_speed"]
    live = evaluator.evaluate(4.0, {**values, PREFIX + "stream_speed": [low, min(1.0, high + .3)]}, exact=False)
    assert evaluator.steps_run == steps + 1 and live.time == pytest.approx(evaluator._last.time)
    exact = evaluator.evaluate(4.0, {**values, PREFIX + "stream_speed": [low, min(1.0, high + .3)]})
    assert evaluator.steps_run > steps + 1 and exact.time == pytest.approx(live.time)


def _native_clip():
    """The first shipped Studio clip (always present; the Studios' default recorded source)."""
    from ui.studio.waveform_recorded_inputs import shipped_clips
    clips = shipped_clips()
    return Path(clips[0].description) if clips else None


def test_recorded_clip_replay_matches_the_production_capture_frame_for_frame(qt_app):
    clip = _native_clip()
    if clip is None:
        pytest.skip("No shipped Studio clip (assets/production/studio_clips)")
    from ui.studio.adapter import RECORDED, StudioFixture
    from ui.studio.extruded_bubble_recorded_inputs import extract, to_inputs
    values = preset_values(0)
    data = extract(clip, values, seconds=2.5)
    fixture = StudioFixture("clip:test", "Test Clip", RECORDED, float(data["duration"]), str(clip))
    evaluator = ExtrudedBubbleStudioEvaluator()
    evaluator.add_recorded(to_inputs(data, fixture))
    evaluator.select("clip:test")
    framed = [step for step in data["steps"] if "frame_sha256" in step]
    checked = 0
    for step in framed[:: max(1, len(framed) // 12)]:
        frame = evaluator.evaluate(step["now_ts"] - data["origin"], values)
        assert frame_digest(frame) == step["frame_sha256"]     # bubbles, wakes, drift log, renderer parameters
        checked += 1
    assert checked >= 6


# ----------------------------------------------------------------------------- handles
def _visible_handle_case():
    """A preset (authored, so searched rather than pinned) whose selected path has both handles on screen."""
    adapter = ExtrudedBubbleStudioAdapter()
    size = (1200.0, 675.0)
    for index in range(preset_count()):
        values = preset_values(index)
        frame = build_frame(_empty_snapshot(), render_parameters(values))
        for obj in adapter.scene_objects(values):
            state = path_handles(frame, values, obj.id, size, None, ())
            if len(state["handles"]) == 2:
                return values, frame, obj.id, state, size
    return None


def _empty_snapshot():
    from widgets.spotify_visualizer.extruded_bubble_simulation import ExtrudedBubbleSnapshot
    return ExtrudedBubbleSnapshot()


def test_path_handles_sit_on_the_projected_endpoints_and_track_the_pointer():
    from core.settings.visualizer_paths import world_point
    from ui.studio.session import read_path, write_path
    case = _visible_handle_case()
    if case is None:
        pytest.skip("no authored preset frames both endpoints of a path at this size")
    values, frame, object_id, state, size = case
    schema = build_schema()
    ids = {p.id for p in schema.properties}
    camera = frame_camera(frame.parameters, size, None, ())
    for handle in state["handles"]:
        assert handle["axis"] == "xy" and {handle["property"], handle["propertyY"]} <= ids
        key, index = handle["property"].rsplit(".", 1)
        _key_y, index_y = handle["propertyY"].rsplit(".", 1)
        base = 0 if int(index_y) < 3 else 3
        path = list(values[key])
        here, shown = project(camera, [world_point(path[base:base + 3])], size)
        assert shown[0] and here[0][0] == pytest.approx(handle["x"], abs=.5) and here[0][1] == pytest.approx(
            handle["y"], abs=.5)
        # A 12 px drag right moves the projected endpoint about 12 px right (the gizmo follows the pointer).
        moved = write_path(path, (int(index),), read_path(path, (int(index),)) + 12 * handle["perPixel"])
        there, _ = project(camera, [world_point(moved[base:base + 3])], size)
        assert there[0][0] - here[0][0] == pytest.approx(12.0, abs=1.5)
        moved = write_path(path, (int(index_y),), read_path(path, (int(index_y),)) + 12 * handle["perPixelY"])
        there, _ = project(camera, [world_point(moved[base:base + 3])], size)
        assert there[0][1] - here[0][1] == pytest.approx(12.0, abs=1.5)
    assert len(state["outline"]) >= 2


def test_deep_light_rays_share_and_edit_the_light_source():
    adapter = ExtrudedBubbleStudioAdapter()
    values = canonical_section()
    values[PREFIX + "light_type"] = "Deep Light"
    frame = build_frame(_empty_snapshot(), render_parameters(values))
    for size in ((1200.0, 675.0), (900.0, 900.0)):
        state = path_handles(frame, values, "ray_path", size, None, ())
        source = [h for h in state["handles"] if h["id"] == "source"]
        if source:
            assert source[0]["property"].startswith(PREFIX + "light_direction.")
            return
    pytest.skip("the canonical Deep Light source is off screen at these sizes")


# ----------------------------------------------------------------------- Settings + shell
@pytest.fixture
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="ExtrudedBubbleStudio",
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
            "mode_activation": build_visualizer_mode_activation([MODE, "waveform_ribbon"]),
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


class CountingRenderer:
    def prepare(self, card, frame):
        return True

    def render(self, card, frame):
        pass

    def release(self):
        pass


class LightAdapter(ExtrudedBubbleStudioAdapter):
    def create_renderer(self):
        return CountingRenderer()

    def recorded_clips(self):
        return ()


def _surfaces(store, size=(1100, 640)):
    from ui.studio.surface import OffscreenStudioSurface

    def factory(controller):
        surface = OffscreenStudioSurface(controller, size=size, present_on_show=False)
        store.append(surface)
        return surface
    return factory


def test_custom_body_offers_the_studio_and_builds_no_control(qt_app, dialog_tab, monkeypatch):
    from ui.studio import settings_link
    _dialog, tab = dialog_tab()
    button = getattr(tab, f"_{MODE}_studio_button")
    assert getattr(tab, f"_{MODE}_settings_container").isAncestorOf(button)
    assert tab._get_visualizer_preset_slider(MODE).isAncestorOf(button)     # in the preset row, every slot
    from PySide6.QtWidgets import QWidget
    body = getattr(tab, f"_{MODE}_settings_container")
    calls = []
    monkeypatch.setattr(settings_link, "open_mode_studio", lambda t, m: calls.append((t, m)))
    button.click()
    assert calls == [(tab, MODE)]
    assert body.findChildren(QWidget, f"{MODE}_bucket_") == []          # the launcher builds no EB bucket


def test_studio_edits_save_through_the_eb_settings_owner_and_close_restores(
        qt_app, dialog_tab, settings_manager, no_gl_checks):
    from ui.studio.controller import StudioController
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump(2)
    assert controller.state == "presented"
    assert "scene3d_detail" in controller.session.values                  # the 3D tier the display would use
    assert {m["id"] for m in controller.bridge.modes} >= {MODE}
    bridge = controller.bridge
    haze = PREFIX + "haze"
    target = round(1.0 - float(controller.session.values[haze]), 2)
    bridge.commitValue(haze, 0, target)
    stored = settings_manager.get("widgets")["spotify_visualizer"]
    assert stored[haze] == pytest.approx(target)
    assert getattr(tab, f"_{MODE}_lazy_values")[haze] == pytest.approx(target)     # closed bucket cache follows
    # A path coordinate through its per-object row, and a held collision share.
    bridge.selectObject("stream_direction")
    key = PREFIX + "stream_direction"
    before = list(controller.session.values[key])
    bridge.commitValue(f"{key}.0", 0, round(before[0] * 0.5 + 0.1, 3))
    assert settings_manager.get("widgets")["spotify_visualizer"][key][0] == pytest.approx(before[0] * 0.5 + 0.1,
                                                                                            abs=1e-3)
    bridge.commitValue(PREFIX + "collision.1", 0, 0.5)
    assert settings_manager.get("widgets")["spotify_visualizer"][PREFIX + "collision"][1] == pytest.approx(.5)
    bridge.undo()
    bridge.requestClose()
    assert controller.state == "closed" and StudioController.active() is None


@pytest.mark.parametrize("size", [(960, 600), (1672, 941)])
def test_dashboard_panels_tile_under_the_viewport_and_handles_stay_in_the_scene_workspace(
        qt_app, dialog_tab, no_gl_checks, size):
    """Every EB workspace's panels sit under the viewport without overlapping, inside the window; every shown group
    lands in exactly one panel; path handles/outline show only where paths are edited (the first workspace)."""
    from PySide6.QtCore import QPointF, QRectF
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces, size))
    surface = surfaces[0]

    def walk(item):
        for child in item.childItems():
            yield child
            yield from walk(child)

    def rect(item):
        top_left = item.mapToScene(QPointF(0, 0))
        return QRectF(top_left.x(), top_left.y(), item.width(), item.height())
    root = surface.host.root
    window = QRectF(0, 0, size[0], size[1])
    first = controller.session.schema.workspaces[0].id
    for workspace in [w.id for w in controller.session.schema.workspaces]:
        controller.bridge.setWorkspace(workspace)
        surface.pump(3)
        panels = [rect(i) for i in walk(root) if i.isVisible() and i.objectName() == "dashboardPanel"]
        viewport = rect(next(i for i in walk(root) if i.objectName() == "viewportSlot"))
        assert panels, workspace
        for index, panel in enumerate(panels):
            assert window.adjusted(-0.5, -0.5, 0.5, 0.5).contains(panel), (workspace, panel)
            assert panel.top() >= viewport.bottom() and panel.width() > 150, (workspace, panel)
            for other in panels[index + 1:]:
                assert not panel.adjusted(0.5, 0.5, -0.5, -0.5).intersects(other), (workspace, panel, other)
        shown = [g["group"] for g in controller.bridge.inspector]
        placed = [g["group"] for c in controller.bridge.inspectorColumns for g in c["groups"]]
        assert sorted(placed) == sorted(shown) and shown, workspace
        if workspace != first:
            assert controller.bridge.handles == {"outline": [], "handles": []}, workspace
    controller.close()


def test_real_production_renderer_draws_and_the_ray_card_renders_both_lanes(qt_app, dialog_tab, no_gl_checks):
    import numpy as np
    from ui.studio.settings_link import open_mode_studio

    class NoClips(ExtrudedBubbleStudioAdapter):
        def recorded_clips(self):
            return ()
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=NoClips(), surface_factory=_surfaces(surfaces, (1280, 760)))
    surface = surfaces[0]
    for _ in range(400):
        surface.pump()
        if controller.bridge.viewportStatus != "preparing" and not controller.previews_pending:
            break
    assert controller.bridge.viewportStatus == "live", controller.bridge.viewportError
    from PySide6.QtCore import QPointF
    slot = surface.host.slot
    origin = slot.mapToScene(QPointF(slot.property("frameX"), slot.property("frameY")))
    x, y = int(origin.x()), int(origin.y())
    w, h = int(slot.property("frameWidth")), int(slot.property("frameHeight"))
    pixels = surface.grab()[y + 10:y + h - 10, x + 10:x + w - 10, :3]
    assert pixels.std() > 4.0 and pixels.max() > 60           # a lit underwater scene, not a placeholder
    card = next(c for c in controller.session.schema.cards if c.rendered)
    renders = {}
    for endpoint in (0, 1):
        controller.bridge.setCardEndpoint(card.group, endpoint)
        for _ in range(400):
            surface.pump()
            if not controller.previews_pending:
                break
        renders[endpoint] = controller.bridge.previews.get("card/" + card.group, "")
    assert renders[0].startswith("data:image/png") and renders[1].startswith("data:image/png")
    low, high = controller.session.values[PREFIX + "rays"]
    if not math.isclose(low, high):
        assert renders[0] != renders[1]                     # the quiet and peak ray strengths look different
    controller.close()
