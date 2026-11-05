"""Studio direct editors: colour/gradient round trips, scene handles, material starting points,
lifecycle timelines and schematic cards.

Structural only: no preset values or UI wording are pinned. Nothing shows a window (the shell renders
through QQuickRenderControl).
"""
from __future__ import annotations

import itertools

import pytest

from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
from core.settings.visualizer_presets import get_custom_preset_index
from ui.studio.colour import display_hex, linear_from_hex
from ui.studio.waveform_adapter import WaveformStudioAdapter, build_schema

MODE = "waveform_ribbon"


# ------------------------------------------------------------------ pure colour contracts
def test_display_hex_round_trip_never_drifts():
    """Every display colour on a dense grid survives display -> linear -> display exactly."""
    steps = list(range(0, 256, 5)) + [1, 2, 3, 254]
    for r, g, b in itertools.product(steps, repeat=3):
        text = "#%02x%02x%02x" % (r, g, b)
        assert display_hex(linear_from_hex(text)) == text


def _gradient_prop():
    schema = build_schema()
    props = [p for p in schema.properties if p.instrument == "gradient"]
    assert props, "the Waveform schema exposes its palettes as gradient instruments"
    return props


def test_gradient_value_keeps_unchanged_nodes_exact_and_converts_only_edited_ones():
    from ui.studio.controller import _gradient_display, _gradient_value
    for prop in _gradient_prop():
        stored = [[0.0, [0.0123, 0.4567, 0.8899]], [0.5, [0.3333, 0.1111, 0.0007]], [1.0, [0.9, 0.2, 0.05]]]
        display = _gradient_display(prop, stored)
        payload = [{"pos": n["pos"], "hex": n["hex"], "from": i} for i, n in enumerate(display)]
        same = _gradient_value(prop, payload, stored)
        assert same == [[p, list(c)] for p, c in stored], "an untouched palette must stay bit-identical"
        payload[1]["hex"] = "#ff8000"
        edited = _gradient_value(prop, payload, stored)
        assert edited[0] == stored[0] and edited[2] == stored[2]
        assert display_hex(edited[1][1]) == "#ff8000"
        # moving a node keeps its colour exact and the list sorted by position
        payload[1]["hex"] = display[1]["hex"]
        payload[0]["pos"] = 0.75
        moved = _gradient_value(prop, payload, stored)
        assert [p for p, _ in moved] == sorted(p for p, _ in moved)
        assert [0.0123, 0.4567, 0.8899] in [c for _, c in moved]


def test_gradient_node_count_stays_within_the_canonical_contract():
    from ui.studio.controller import _gradient_value
    for prop in _gradient_prop():
        lo, hi = int(prop.minimum), int(prop.maximum)
        assert 1 <= lo <= hi
        for count in (lo, hi):
            nodes = [{"pos": i / max(1, count - 1), "hex": "#336699", "from": -1} for i in range(count)]
            assert len(_gradient_value(prop, nodes, [])) == count
        for count in (lo - 1, hi + 1):
            if count < 0:
                continue
            nodes = [{"pos": i / max(1, count), "hex": "#336699", "from": -1} for i in range(count)]
            with pytest.raises(ValueError):
                _gradient_value(prop, nodes, [])


def test_lifecycles_and_cards_reference_real_properties_in_their_group():
    schema = build_schema()
    for spec in schema.lifecycles:
        for prop_id in filter(None, (spec.total, spec.fade_share, spec.peel)):
            assert schema.find(prop_id).group == spec.group
    for card in schema.cards:
        assert card.kind in {"falloff", "reflection", "exposure", "particles", "strands"}
        assert any(card.group in w.groups for w in schema.workspaces)
        for _role, prop_id in card.roles:
            schema.find(prop_id)                       # every role is a real, edited property
    for group, presets in schema.group_presets:
        assert presets and any(group in w.groups for w in schema.workspaces)


# ------------------------------------------------------------------ Studio harness
class CountingRenderer:
    def prepare(self, card, frame):
        return True

    def render(self, card, frame):
        pass

    def release(self):
        pass


class LightAdapter(WaveformStudioAdapter):
    def create_renderer(self):
        return CountingRenderer()

    def recorded_clips(self):
        return ()


@pytest.fixture
def studio(qt_app, tmp_path):
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    from core.settings.settings_manager import SettingsManager
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.studio.controller import StudioController
    from ui.studio.settings_link import open_mode_studio
    from ui.studio.surface import OffscreenStudioSurface
    from ui.tabs.visualizers_tab import VisualizersTab
    disable_per_call_gl_error_checking()
    manager = SettingsManager(organization="SRPSSFocusedTests", application="WaveformStudioEditors",
                              storage_base_dir=tmp_path / "profile")
    manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": MODE,
        "mode_activation": build_visualizer_mode_activation([MODE]),
        f"preset_{MODE}": get_custom_preset_index(MODE)}})
    dialog = QDialog()
    QVBoxLayout(dialog).addWidget(tab := VisualizersTab(manager))
    tab._select_mode_page(MODE)
    surfaces = []

    def factory(controller):
        surface = OffscreenStudioSurface(controller, size=(1280, 760), present_on_show=False)
        surfaces.append(surface)
        return surface

    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=factory)
    surfaces[0].pump(3)
    yield controller, surfaces[0]
    if StudioController.active() is not None:
        StudioController.active().close()
    dialog.deleteLater()
    qt_app.processEvents()
    assert manager.flush(timeout=5.)


def _walk(item):
    for child in item.childItems():
        yield child
        yield from _walk(child)


def _named(surface, name):
    return [i for i in _walk(surface.host.root) if i.objectName() == name and i.isVisible()]


def _settle_handles(controller, surface, frames=6):
    for _ in range(frames):
        surface.pump()
    return controller.bridge.handles


def test_scene_handles_follow_the_selected_ribbon_and_edit_real_values(studio):
    controller, surface = studio
    bridge = controller.bridge
    bridge.setWorkspace(controller.session.schema.workspaces[0].id)
    bridge.selectObject("ribbon0")
    state = _settle_handles(controller, surface)
    handles = {h["id"]: h for h in state["handles"]}
    assert {"height", "width", "phase"} <= set(handles)
    assert len(state["outline"]) > 8
    w, h = controller.viewport.width(), controller.viewport.height()
    for handle in handles.values():
        assert 0 <= handle["x"] <= w and 0 <= handle["y"] <= h and handle["perPixel"] != 0
    assert len(_named(surface, "sceneHandle")) == len(handles)

    # Drag the height handle 24 px up through the same bridge calls the QML handle makes.
    height = handles["height"]
    prop = controller.session.schema.find(height["property"])
    from ui.studio.session import read_path
    start = read_path(controller.session.values, prop.path)
    start = start[height["endpoint"]] if isinstance(start, (list, tuple)) else start
    bridge.beginEdit(height["property"], height["label"])
    bridge.previewValue(height["property"], height["endpoint"], start + (-24.0) * height["perPixel"])
    bridge.endEdit()
    after = read_path(controller.session.values, prop.path)
    after = after[height["endpoint"]] if isinstance(after, (list, tuple)) else after
    assert after > start, "dragging the height handle up raises the ribbon"
    assert controller.session.undo_label

    moved = {h_["id"]: h_ for h_ in _settle_handles(controller, surface)["handles"]}
    rise = height["y"] - moved["height"]["y"]
    assert rise > 0 and abs(rise - 24.0) < 24.0 * .5, ("handle tracks the projected crest", rise)

    controller.session.undo()
    restored = read_path(controller.session.values, prop.path)
    restored = restored[height["endpoint"]] if isinstance(restored, (list, tuple)) else restored
    assert restored == pytest.approx(start)

    # Handles exist only while composing.
    bridge.setWorkspace("appearance")
    assert _settle_handles(controller, surface, 2)["handles"] == []


def test_material_starting_points_are_one_undoable_edit_and_report_the_active_tile(studio):
    controller, surface = studio
    bridge = controller.bridge
    schema = controller.session.schema
    group, presets = schema.group_presets[0]
    original = dict(controller.session.values)
    baseline_id = next(p.id for p in presets
                       if not controller.adapter.apply_preset(group, p.id, controller.session.baseline_values,
                                                              controller.session.values))
    assert bridge.activePresets[group] == baseline_id
    other = next(p for p in presets
                 if controller.adapter.apply_preset(group, p.id, controller.session.baseline_values,
                                                    controller.session.values))
    bridge.applyPreset(group, other.id)
    assert bridge.activePresets[group] == other.id
    assert controller.session.values != original
    controller.session.undo()
    assert controller.session.values == original
    surface.pump(2)
    assert bridge.activePresets[group] == baseline_id


def test_gradient_commit_of_an_untouched_strip_is_bit_identical(studio):
    import json
    controller, surface = studio
    bridge = controller.bridge
    from ui.studio.session import read_path
    for prop in (p for p in controller.session.schema.properties if p.instrument == "gradient"):
        stored = read_path(controller.session.values, prop.path)
        display = bridge.values[prop.id]
        payload = json.dumps([{"pos": n["pos"], "hex": n["hex"], "from": i} for i, n in enumerate(display)])
        bridge.commitGradient(prop.id, payload)
        assert read_path(controller.session.values, prop.path) == stored
        # Re-typing a colour's own display hex is not an edit either.
    for prop in (p for p in controller.session.schema.properties if p.instrument == "colour"):
        stored = read_path(controller.session.values, prop.path)
        bridge.commitText(prop.id, 0, bridge.values[prop.id])
        assert read_path(controller.session.values, prop.path) == stored
    assert not controller.session.dirty


def test_lifecycle_timelines_cards_and_tiles_render_in_their_groups(studio):
    import dataclasses
    controller, surface = studio
    bridge = controller.bridge
    schema = controller.session.schema
    wanted = {spec.group for spec in schema.lifecycles} | {c.group for c in schema.cards} \
        | {g for g, _ in schema.group_presets}
    bridge._schema = dataclasses.replace(bridge._schema, workspaces=tuple(
        dataclasses.replace(w, open_groups=tuple(g for g in w.groups if g in wanted) or w.open_groups)
        for w in bridge._schema.workspaces))
    seen = {"lifecycleLane": 0, "lifecycleGrip": 0}
    for workspace in ("appearance", "world"):
        bridge.setWorkspace(workspace)
        surface.pump(3)
        for name in seen:
            seen[name] += len(_named(surface, name))
        for lane in _named(surface, "lifecycleLane"):
            assert lane.width() > 100
            for grip in (g for g in lane.childItems() if g.objectName() == "lifecycleGrip" and g.isVisible()):
                assert -6 <= grip.x() <= lane.width() + 6
    assert seen["lifecycleLane"] == len(schema.lifecycles)
    assert seen["lifecycleGrip"] >= len(schema.lifecycles)


def test_response_editor_collapses_to_keep_the_viewport_large(studio):
    controller, surface = studio
    controller.bridge.setWorkspace("reactivity")
    surface.pump(3)
    dock = next(i for i in _walk(surface.host.root) if i.objectName() == "responseDock")
    slot = surface.host.slot
    assert dock.isVisible() and dock.property("expanded") is False
    collapsed = slot.height()
    dock.setProperty("expanded", True)
    surface.pump(3)
    assert dock.height() > 120 and slot.height() < collapsed - 100
    dock.setProperty("expanded", False)
    surface.pump(3)
    assert slot.height() == pytest.approx(collapsed)


def test_preset_tiles_render_once_per_starting_point_and_stay_idle(studio, monkeypatch):
    controller, surface = studio
    requests = []
    original = controller.viewport.request_snapshot

    def counted(key, *args, **kwargs):
        if not key.startswith("card/"):                 # rendered world cards are covered separately
            requests.append(key)
        return original(key, *args, **kwargs)
    monkeypatch.setattr(controller.viewport, "request_snapshot", counted)
    group, presets = controller.session.schema.group_presets[0]
    controller.bridge.setWorkspace("composition")
    surface.pump(3)
    assert requests == []                               # tiles off screen: nothing is rendered
    controller.bridge.setWorkspace("appearance")
    for _ in range(200):
        if not controller.previews_pending:
            break
        surface.pump()
    assert not controller.previews_pending
    assert len(requests) == len(presets)
    previews = controller.bridge.presetPreviews
    assert {f"{group}/{p.id}" for p in presets} <= set(previews)
    assert all(previews[f"{group}/{p.id}"].startswith("data:image/png;base64,") for p in presets)
    assert len([i for i in _walk(surface.host.root) if i.objectName() == "presetPreview" and i.isVisible()]) \
        == len(presets)
    # Idle: more frames and workspace round trips render nothing new.
    surface.pump(10)
    controller.bridge.setWorkspace("world")
    controller.bridge.setWorkspace("appearance")
    surface.pump(10)
    assert len(requests) == len(presets)
    # A live drag renders no tiles; its commit re-renders each tile once.
    prop = next(p for p in controller.session.schema.properties if p.group == group and p.instrument == "quiet_peak")
    controller.bridge.beginEdit(prop.id, prop.label)
    controller.bridge.previewValue(prop.id, 1, prop.maximum)
    surface.pump(5)
    assert len(requests) == len(presets)
    controller.bridge.endEdit()
    for _ in range(200):
        if not controller.previews_pending:
            break
        surface.pump()
    assert len(requests) == 2 * len(presets)


def test_combined_move_gizmo_edits_both_axes_as_one_step(studio):
    controller, surface = studio
    bridge = controller.bridge
    bridge.setWorkspace("composition")
    bridge.selectObject("ribbon0")
    handles = {h["id"]: h for h in _settle_handles(controller, surface)["handles"]}
    move = handles["move"]
    assert move["axis"] == "xy" and move["propertyY"] and move["perPixelY"] and move["perPixel"]
    from ui.studio.session import read_path
    session = controller.session

    def value(prop_id):
        v = read_path(session.values, session.schema.find(prop_id).path)
        return v[0] if isinstance(v, (list, tuple)) else v
    x0, y0 = value(move["property"]), value(move["propertyY"])
    bridge.beginEdit(move["property"], move["label"])
    bridge.previewValue(move["property"], 0, x0 + 30 * move["perPixel"])
    bridge.previewValue(move["propertyY"], 0, y0 + (-20) * move["perPixelY"])
    bridge.endEdit()
    assert value(move["property"]) != pytest.approx(x0) and value(move["propertyY"]) > y0
    session.undo()                                       # one step reverts both axes
    assert value(move["property"]) == pytest.approx(x0) and value(move["propertyY"]) == pytest.approx(y0)


def test_hint_texts_stay_inside_their_container(studio):
    from PySide6.QtCore import QPointF
    controller, surface = studio
    for workspace in ("appearance", "reactivity"):
        controller.bridge.setWorkspace(workspace)
        surface.pump(3)
        for dock in (i for i in _walk(surface.host.root) if i.objectName() == "responseDock"):
            dock.setProperty("expanded", workspace == "reactivity")
        surface.pump(2)
        hints = _named(surface, "hintText")
        assert hints
        for hint in hints:
            panel = hint.parentItem()
            while panel is not None and panel.objectName() not in ("inspectorScroll", "responseDock"):
                panel = panel.parentItem()
            assert panel is not None
            right = hint.mapToScene(QPointF(hint.width(), 0)).x()
            panel_right = panel.mapToScene(QPointF(panel.width(), 0)).x()
            assert right <= panel_right + 1.0, (workspace, hint.property("text"), right, panel_right)


def test_help_overlay_lists_workspaces_and_the_modes_gestures(studio):
    controller, surface = studio
    root = surface.host.root
    overlay = next(i for i in _walk(root) if i.objectName() == "helpOverlay")
    assert not overlay.isVisible()
    overlay.setProperty("open", True)
    surface.pump(2)
    assert overlay.isVisible()
    gestures = [i for i in _walk(overlay) if i.objectName() == "helpGesture"]
    caps = controller.bridge.capabilities
    assert caps["camera"] and caps["handles"]
    assert len(gestures) == len(overlay.property("gestures").toVariant()) >= 6
    assert all(w["help"] for w in controller.bridge.workspaces)
    overlay.setProperty("open", False)


def test_preset_tiles_are_drawn_by_the_production_renderer_and_differ(qt_app, tmp_path):
    """Real renderer: each starting point's tile is a non-empty render, and they are not all the same."""
    import base64
    import io
    import numpy as np
    from PIL import Image
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from ui.studio.controller import StudioController
    from ui.studio.surface import OffscreenStudioSurface
    disable_per_call_gl_error_checking()

    class Store:
        def __init__(self):
            self.values = dict(resolve_visualizer_activation_payload(
                {"mode": MODE, f"preset_{MODE}": 0}, mode=MODE).resolved_config)

        def snapshot(self):
            return dict(self.values)

        def commit(self, values, changed):
            self.values.update(values)
            return dict(self.values)

        def preset_label(self):
            return "Test"

    class Presence:
        def conceal(self):
            pass

        def reveal(self):
            pass

    class RealAdapter(WaveformStudioAdapter):
        def recorded_clips(self):
            return ()

    surfaces = []
    controller = StudioController(RealAdapter(), Store(), Presence(), lambda c: (
        surfaces.append(OffscreenStudioSurface(c, size=(1100, 700), present_on_show=False)) or surfaces[-1]))
    assert controller.open()
    surface = surfaces[0]
    try:
        controller.bridge.setWorkspace("appearance")
        for _ in range(300):
            surface.pump()
            if controller.bridge.viewportStatus == "live" and not controller.previews_pending:
                break
        group, presets = controller.session.schema.group_presets[0]
        images = []
        for preset in presets:
            url = controller.bridge.presetPreviews[f"{group}/{preset.id}"]
            images.append(np.asarray(Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB"),
                                     dtype=float))
        assert all(image.mean() > 8.0 for image in images)          # a lit scene, not a cleared target
        spread = max(np.abs(a - images[0]).mean() for a in images[1:])
        assert spread > 1.0                                          # the starting points look different
    finally:
        controller.close()
        qt_app.processEvents()


def test_material_tiles_show_only_the_selected_ribbon_close_up():
    adapter = WaveformStudioAdapter()
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    values = dict(resolve_visualizer_activation_payload({"mode": MODE, f"preset_{MODE}": 0}, mode=MODE).resolved_config)
    cards = values[f"{MODE}_ribbons"]
    view = adapter.tile_values(values, "ribbon2")
    assert view[f"{MODE}_count"] == 1 and view[f"{MODE}_ribbons"][0] == cards[2]
    assert sorted(map(repr, view[f"{MODE}_ribbons"])) == sorted(map(repr, cards))     # the set stays complete
    for key in ("sparks_enabled", "strands_enabled", "mist_enabled"):
        if f"{MODE}_{key}" in values:
            assert view[f"{MODE}_{key}"] is False
    assert values[f"{MODE}_ribbons"] == cards                                          # input untouched


def _settle_previews(controller, surface, limit=300):
    for _ in range(limit):
        if not controller.previews_pending:
            return
        surface.pump()
    raise AssertionError("previews did not settle")


def test_world_cards_render_per_commit_follow_the_edited_lane_and_rest_idle(studio, monkeypatch):
    controller, surface = studio
    bridge = controller.bridge
    schema = controller.session.schema
    rendered = [card.group for card in schema.cards if card.rendered]
    assert {"Mist", "Floor"} <= set(rendered)
    requests = []
    original = controller.viewport.request_snapshot

    def counted(key, *args, **kwargs):
        requests.append(key.split("|")[0])
        return original(key, *args, **kwargs)
    monkeypatch.setattr(controller.viewport, "request_snapshot", counted)
    controller.select_fixture("peak")
    controller.seek(4.0)
    surface.pump(4)
    bridge.setWorkspace("world")
    _settle_previews(controller, surface)
    assert sorted(requests) == sorted(f"card/{g}" for g in rendered)
    assert all(bridge.previews[f"card/{g}"].startswith("data:image/png;base64,") for g in rendered)
    surface.pump(2)
    shown = [i for i in _walk(surface.host.root) if i.objectName() == "cardRender"]
    assert len([i for i in shown if i.isVisible()]) == len(rendered)
    surface.pump(10)                                        # at rest: nothing new
    assert len(requests) == len(rendered)
    # Editing the Quiet lane of a Mist value moves the Mist card to that lane; the commit re-renders once.
    density = next(p for p in schema.properties if p.group == "Mist" and p.instrument == "quiet_peak")
    bridge.beginEdit(density.id, density.label)
    bridge.previewValue(density.id, 0, density.maximum)
    surface.pump(4)
    assert len(requests) == len(rendered)                   # no renders during the drag
    assert bridge.cardEndpoints["Mist"] == 0
    bridge.endEdit()
    _settle_previews(controller, surface)
    assert requests.count("card/Mist") == 2
    bridge.setCardEndpoint("Mist", 1)
    _settle_previews(controller, surface)
    assert requests.count("card/Mist") == 3
    bridge.setWorkspace("composition")
    bridge.commitValue(density.id, 1, density.minimum)
    surface.pump(10)
    assert requests.count("card/Mist") == 3                 # off screen: nothing renders


def test_floor_card_render_is_the_production_floor_and_tracks_floor_values(qt_app):
    """Real renderer: the Floor card is a lit render and a Floor commit changes it."""
    import base64
    import io
    import numpy as np
    from PIL import Image
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from ui.studio.controller import StudioController
    from ui.studio.surface import OffscreenStudioSurface
    disable_per_call_gl_error_checking()

    class Store:
        def __init__(self):
            self.values = dict(resolve_visualizer_activation_payload(
                {"mode": MODE, f"preset_{MODE}": 0}, mode=MODE).resolved_config)

        def snapshot(self):
            return dict(self.values)

        def commit(self, values, changed):
            self.values.update(values)
            return dict(self.values)

        def preset_label(self):
            return "Test"

    class Presence:
        def conceal(self):
            pass

        def reveal(self):
            pass

    class RealAdapter(WaveformStudioAdapter):
        def recorded_clips(self):
            return ()

    surfaces = []
    controller = StudioController(RealAdapter(), Store(), Presence(), lambda c: (
        surfaces.append(OffscreenStudioSurface(c, size=(1100, 700), present_on_show=False)) or surfaces[-1]))
    assert controller.open()
    surface = surfaces[0]

    def floor_image():
        url = controller.bridge.previews["card/Floor"]
        return np.asarray(Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB"), dtype=float)
    try:
        controller.select_fixture("peak")
        controller.seek(4.0)
        for _ in range(300):
            surface.pump()
            if controller.bridge.viewportStatus == "live":
                break
        controller.bridge.setWorkspace("world")
        _settle_previews(controller, surface)
        before = floor_image()
        assert before.mean() > 8.0
        prop = controller.session.schema.find(f"{MODE}_floor_brightness")
        controller.bridge.commitValue(prop.id, 1, prop.minimum)
        controller.bridge.commitValue(prop.id, 0, prop.minimum)
        _settle_previews(controller, surface)
        after = floor_image()
        assert after.shape == before.shape and np.abs(after - before).mean() > 0.5
    finally:
        controller.close()
        qt_app.processEvents()


def test_preview_only_layer_omission_is_unreachable_from_production():
    """The scene's preview-only omission defaults off and only the Studio sets it (never settings or runtime)."""
    import ast
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    from rendering.quick.scene3d.waveform import WaveformScene
    assert WaveformScene.__init__.__code__.co_names.count("preview_hidden") >= 1
    writers = []
    for base in ("core", "engine", "rendering", "ui", "widgets"):
        for path in (root / base).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "preview_hidden" not in text:
                continue
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, (ast.Assign, ast.AugAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    if any(isinstance(t, ast.Attribute) and t.attr == "preview_hidden" for t in targets):
                        writers.append(path.relative_to(root).as_posix())
    assert sorted(set(writers)) == ["rendering/quick/scene3d/waveform.py", "ui/studio/waveform_adapter.py"]


def test_preview_layer_omission_changes_only_flagged_renders(qt_app):
    """Real renderer: the same frame drawn through the Studio snapshot path with no flag equals a second
    unflagged draw (the production path is deterministic and untouched), while hiding the actors changes it."""
    import numpy as np
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from ui.studio.controller import StudioController
    from ui.studio.surface import OffscreenStudioSurface
    disable_per_call_gl_error_checking()

    class Store:
        def __init__(self):
            self.values = dict(resolve_visualizer_activation_payload(
                {"mode": MODE, f"preset_{MODE}": 0}, mode=MODE).resolved_config)

        def snapshot(self):
            return dict(self.values)

        def commit(self, values, changed):
            self.values.update(values)
            return dict(self.values)

        def preset_label(self):
            return "Test"

    class Presence:
        def conceal(self):
            pass

        def reveal(self):
            pass

    class RealAdapter(WaveformStudioAdapter):
        def recorded_clips(self):
            return ()

    surfaces = []
    controller = StudioController(RealAdapter(), Store(), Presence(), lambda c: (
        surfaces.append(OffscreenStudioSurface(c, size=(900, 600), present_on_show=False)) or surfaces[-1]))
    assert controller.open()
    surface = surfaces[0]
    shots = {}
    controller.viewport.snapshotReady.connect(
        lambda key, w, h, pixels: shots.__setitem__(key, np.frombuffer(pixels, np.uint8).reshape(h, w, 4).astype(float)))
    try:
        controller.select_fixture("peak")
        controller.seek(4.0)
        for _ in range(300):
            surface.pump()
            if controller.bridge.viewportStatus == "live":
                break
        frame = controller.last_frame
        extent = controller.framings[0].extent
        for key, style in (("plain_a", ()), ("plain_b", ()),
                           ("haze", (("preview_hidden", ("actors", "reflected_actors")),))):
            controller.viewport.request_snapshot(key, frame, (240, 160), (120.0, 80.0), extent, style)
        for _ in range(200):
            surface.pump()
            qt_app.processEvents()
            if len(shots) == 3:
                break
        assert set(shots) == {"plain_a", "plain_b", "haze"}
        assert np.array_equal(shots["plain_a"], shots["plain_b"])
        assert shots["plain_a"].mean() > 8.0
        assert np.abs(shots["haze"] - shots["plain_a"]).mean() > 2.0
        # The live viewport kept drawing with the actors (its style never carries the flag).
        assert not dict(controller.framings[0].style).get("preview_hidden")
    finally:
        controller.close()
        qt_app.processEvents()
