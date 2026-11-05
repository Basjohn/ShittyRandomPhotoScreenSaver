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
        assert card.kind in {"falloff", "reflection", "exposure"}
        for _role, prop_id in card.roles:
            assert schema.find(prop_id).group == card.group
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
