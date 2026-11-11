"""The Studio's shared shape instrument (``ui/studio/shape.py``, the shell's ``ShapeRow``): a node curve and its
frequency lanes edited on one canvas, for Spectrum, Extruded Spectrum and Neon Lake (its Frequency Response shape and
its Terrain Reaction shaper).

Every check runs the real Studio controller, bridge and mode adapter (schema, admission, structural edits); only the
background analysis worker and the scene renderer are stood in for, since no check here looks at the scene. Inputs
are the code-owned canonical defaults, expectations are derived from the session's own values and the schema's
``ShapeSpec``: no preset value, default value or wording is pinned. The pointer checks send real mouse events to the
real shell on the hidden ``OffscreenStudioSurface``; nothing shows a window. Each behaviour has a negative control.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from ui.studio.registry import create_adapter, studio_modes
from ui.studio.schema import SHAPE, SHAPE_BANDS
from ui.studio.session import read_path

FAMILY = ("spectrum", "extruded_spectrum", "shockwave_grid")


def _instruments() -> list[tuple[str, str]]:
    """(mode, SHAPE row id) of every registered Studio that declares a shape instrument."""
    return [(entry.mode_id, shape.property) for entry in studio_modes()
            for shape in create_adapter(entry.mode_id).schema().shapes]


INSTRUMENTS = _instruments()


# ------------------------------------------------------------------------------------------- coverage helper
def shape_uncovered(properties, shapes, elements) -> set:
    """The ``elements`` (paths of stored values or of their parts) nothing edits: no ordinary property addresses
    the element or an ancestor of it, and no shape instrument (a SHAPE row with its spec) does either. A SHAPE
    property without its instrument only carries a value: it covers nothing."""
    rows = {spec.property: spec for spec in shapes}
    owners = []
    for prop in properties:
        if prop.instrument != SHAPE:
            owners.append(tuple(prop.path))
        elif prop.id in rows and not prop.instrument_only:
            owners.append(tuple(prop.path))
            owners.extend(tuple(path) for path in rows[prop.id].paths)
    return {tuple(element) for element in elements
            if not any(tuple(element)[:len(owner)] == owner for owner in owners)}


# ------------------------------------------------------------------------------------------------ the Studio
class Store:
    """An in-memory canonical store on the code-owned defaults, with every condition of the mode's shape rows met
    (test-owned inputs, never an authored preset)."""

    def __init__(self, mode: str, schema) -> None:
        from core.settings.default_contract import require_canonical_default
        from core.settings.visualizer_mode_settings import mode_settings
        values = deepcopy(dict(require_canonical_default("widgets.spotify_visualizer")))
        values.update({c.key: c.admit(values[c.key], values[c.key]) for c in mode_settings(mode).controls
                       if c.key in values})
        for shape in schema.shapes:
            for key, accepted in schema.find(shape.property).when:
                values[key] = accepted[0]
        self.values = values
        self.commits = 0

    def snapshot(self):
        return deepcopy(self.values)

    def commit(self, values, changed):
        self.commits += 1
        self.values.update(deepcopy(dict(values)))
        return deepcopy(self.values)

    def preset_label(self):
        return "Test"


class _Presence:
    concealed = False

    def conceal(self):
        pass

    def reveal(self):
        pass


class _QuietRenderer:
    def prepare(self, card, frame):
        return True

    def render(self, card, frame):
        pass

    def release(self):
        pass


class _NeverLands:
    """An analysis that never finishes: the Studio keeps its resting scene and starts no worker process."""

    def __call__(self, fixture, values, finished):
        return self

    def cancel(self):
        pass


@pytest.fixture
def studio(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.studio.controller import StudioController
    from ui.studio.surface import OffscreenStudioSurface
    from ui.studio.theme import studio_theme
    disable_per_call_gl_error_checking()
    opened = []

    def open_mode(mode: str, size=(1600, 900)):
        adapter = create_adapter(mode)
        real_evaluator = adapter.create_evaluator

        def evaluator():
            made = real_evaluator()
            made._loader = _NeverLands()
            return made
        adapter.create_evaluator = evaluator
        adapter.create_renderer = _QuietRenderer
        adapter.recorded_clips = lambda: ()
        surfaces = []

        def factory(controller):
            surfaces.append(OffscreenStudioSurface(controller, size=size, present_on_show=False))
            return surfaces[0]
        store = Store(mode, adapter.schema())
        controller = StudioController(adapter, store, _Presence(), factory, theme_provider=studio_theme)
        assert controller.open()
        opened.append(controller)
        surfaces[0].pump(3)
        return controller, surfaces[0], store
    yield open_mode
    for controller in opened:
        controller.close()
    assert StudioController.active() is None


def _spec(controller, prop_id):
    return controller.session.schema.shape(prop_id)


def _nodes(controller, prop_id):
    schema = controller.session.schema
    return [list(node) for node in read_path(controller.session.values, schema.find(prop_id).path)]


def _layout(controller, prop_id):
    return controller.bridge.shapes.instrument(prop_id).layout(controller.session.values)


def _notches(controller, prop_id):
    return [list(n) for n in read_path(controller.session.values, _layout(controller, prop_id).notches)]


def _strengths(controller, prop_id):
    return dict(read_path(controller.session.values, _layout(controller, prop_id).lanes))


def _stored_nodes(store, controller, prop_id):
    return [list(node) for node in read_path(store.values, controller.session.schema.find(prop_id).path)]


def _thin(controller, prop_id, count):
    """Remove nodes (through the mode's own structural edit) until ``count`` are left."""
    spec = _spec(controller, prop_id)
    while len(_nodes(controller, prop_id)) > count:
        controller.bridge.runAction(f"{spec.remove}0")


# --------------------------------------------------------------------------------------------------- schema
def test_spectrum_and_neon_lake_edit_their_shapes_with_the_one_instrument():
    by_mode: dict[str, list[str]] = {}
    for mode, prop_id in INSTRUMENTS:
        by_mode.setdefault(mode, []).append(prop_id)
    assert set(FAMILY) <= set(by_mode)
    assert len(by_mode["shockwave_grid"]) == 2                 # the Frequency Response shape and the terrain shaper
    for mode, prop_id in INSTRUMENTS:
        schema = create_adapter(mode).schema()
        spec, prop = schema.shape(prop_id), schema.find(prop_id)
        assert prop.instrument == SHAPE and not prop.instrument_only
        # No slider row is left beside the instrument: nothing else in the schema addresses a value it edits.
        owned = {tuple(prop.path), *(tuple(path) for path in spec.paths)}
        others = [p for p in schema.properties if p.id != prop_id and not p.instrument_only]
        assert not any(tuple(p.path)[:len(owner)] == owner for p in others for owner in owned), (mode, prop_id)
        # The values it edits are carried by the session, so they are saved, undone and hydrated like any other.
        assert {path[0] for path in owned} <= schema.keys
        if spec.layout_switch is not None:
            switch = next(p for p in schema.properties if tuple(p.path) == tuple(spec.layout_switch))
            assert switch.instrument_only and len(spec.layouts) == 2


def test_a_shape_row_without_its_spec_is_refused_negative_control():
    from dataclasses import replace
    schema = create_adapter("spectrum").schema()
    with pytest.raises(ValueError):
        replace(schema, shapes=())
    spec = schema.shapes[0]
    with pytest.raises(ValueError):
        replace(schema, shapes=(replace(spec, property="no_such_row"),))
    with pytest.raises(ValueError):                              # a lane value no property carries
        replace(schema, shapes=(replace(spec, reads=("no_such_key",)),))


# ------------------------------------------------------------------------------- what the canvas is given
@pytest.mark.parametrize("mode,prop_id", INSTRUMENTS)
def test_the_canvas_draws_the_production_curve_and_the_stored_shape(studio, mode, prop_id):
    from utils.curve_nodes import interpolate_nodes
    controller, _surface, _store = studio(mode)
    view = controller.bridge.values[prop_id]
    nodes = _nodes(controller, prop_id)
    assert view["nodes"] == nodes
    # The drawn curve is the production interpolation's own samples (what the engine and the terrain baker sample).
    assert view["curve"] == pytest.approx(interpolate_nodes(nodes, len(view["curve"])), abs=1e-5)
    assert [(lane["x"], lane["label"]) for lane in view["lanes"]] == [tuple(n) for n in _notches(controller, prop_id)]
    strengths = _strengths(controller, prop_id)
    assert all(lane["strength"] == pytest.approx(strengths[lane["label"]]) for lane in view["lanes"])
    low, high = _spec(controller, prop_id).node_limits
    assert (view["minNodes"], view["maxNodes"]) == (low, high)
    assert view["canAdd"] == (len(nodes) < high) and view["canRemove"] == (len(nodes) > low)


@pytest.mark.parametrize("mode", [m for m in FAMILY])
def test_the_preview_under_the_curve_is_the_engines_own_bar_shaping(studio, mode):
    """Spectrum family: per bar, the silhouette and the silhouette at its lane's strength, from the engine's own
    functions (the ones ``fft_to_bars`` shapes the bars with), for both layouts."""
    import numpy as np
    from utils.curve_nodes import interpolate_nodes, interpolate_nodes_mirrored
    from widgets.spotify_visualizer.bar_computation import _build_lane_energy_profile
    controller, surface, _store = studio(mode)
    prefix = mode + "_"
    prop_id = prefix + "shape_nodes"
    switch = controller.bridge.values[prop_id]["layoutSwitch"]
    for _ in range(2):
        values = controller.session.values
        view = controller.bridge.values[prop_id]
        mirrored = bool(values[switch])
        assert view["mirrored"] is mirrored
        bands = int(values[prefix + "bar_count"])
        nodes, floor = values[prop_id], float(values[prefix + "profile_floor"])
        shape = np.maximum(np.array(interpolate_nodes_mirrored(nodes, bands) if mirrored
                                    else interpolate_nodes(nodes, bands), dtype="float32"), floor)
        centre = (bands - 1.0) * 0.5
        positions = (np.abs(np.arange(bands, dtype="float32") - centre) / max(centre, 1.0) if mirrored
                     else np.linspace(0.0, 1.0, bands, dtype="float32"))
        notches = _notches(controller, prop_id)
        weights = _build_lane_energy_profile(np, positions, notches, _strengths(controller, prop_id), 1.0, 1.0, 1.0)
        assert len(view["bars"]) == bands
        assert [b[0] for b in view["bars"]] == pytest.approx(list(shape), abs=1e-4)
        assert [b[1] for b in view["bars"]] == pytest.approx(list(shape * weights), abs=1e-4)
        # The lane strength line: the engine's routing at the lanes' own positions and the two ends of the axis.
        xs = [x for x, _w in view["laneProfile"]]
        assert xs == sorted(xs) and xs[0] == 0.0 and xs[-1] == 1.0 and {round(n[0], 5) for n in notches} <= set(xs)
        line = _build_lane_energy_profile(np, np.asarray(xs, dtype="float32"), notches,
                                          _strengths(controller, prop_id), 1.0, 1.0, 1.0)
        assert [w for _x, w in view["laneProfile"]] == pytest.approx(list(line), abs=1e-4)
        controller.bridge.commitValue(switch, 0, not mirrored)          # the other layout
        surface.pump()


def test_the_engine_shapes_its_bars_with_the_functions_the_preview_uses(monkeypatch):
    """``fft_to_bars`` (the engine's bar shaping) calls the helpers the instrument's preview is built from, with the
    worker's own shape, so the preview cannot drift from the engine. With the silhouette helper replaced by a flat
    zero, the engine's own bars fall with it (the negative control: the engine really takes its shape from it)."""
    import numpy as np
    from tests.test_spectrum_shaping_current import TestLaneAwareSpectrumEnergy as Engine
    from widgets.spotify_visualizer import bar_computation
    fft = Engine._make_fft(np, low=10.0, mid=10.0, high=10.0)
    seen: dict[str, list] = {"shape": [], "positions": []}
    real_shape, real_positions = bar_computation.shape_bar_profile, bar_computation.lane_sample_positions

    def shape(np_module, nodes, bands, mirrored, floor):
        seen["shape"].append((nodes, bands, mirrored, floor))
        return real_shape(np_module, nodes, bands, mirrored, floor)

    def positions(np_module, bands, mirrored):
        seen["positions"].append((bands, mirrored))
        return real_positions(np_module, bands, mirrored)
    monkeypatch.setattr(bar_computation, "shape_bar_profile", shape)
    monkeypatch.setattr(bar_computation, "lane_sample_positions", positions)
    worker = Engine._make_worker(np)
    bars = worker._fft_to_bars(fft)
    bands = int(worker._bar_count)
    assert seen["shape"] == [(worker._spectrum_shape_nodes, bands, worker._spectrum_mirrored,
                              worker._spectrum_shape_config.profile_floor)]
    assert seen["positions"] == [(bands, worker._spectrum_mirrored)]
    shaped = sum(bars) / len(bars)
    assert shaped > 0.0
    monkeypatch.setattr(bar_computation, "shape_bar_profile",
                        lambda np_module, nodes, bands, mirrored, floor: np_module.zeros(bands, dtype="float32"))
    flat = Engine._make_worker(np)._fft_to_bars(fft)
    assert sum(flat) / len(flat) < shaped * 0.5


def test_the_terrain_shapers_preview_is_the_baked_tables(studio):
    """Neon Lake's shaper: the bars are the baked elevation tables the height shader reads, and the lane line gives
    every baked sample the strength of the lane the bake assigned it."""
    from rendering.gl_programs.neon_terrain_reaction import REACTION_LANES, bake_terrain_shaper
    from ui.studio.shockwave_grid_adapter import SHAPER
    controller, _surface, _store = studio("shockwave_grid")
    assert _spec(controller, SHAPER).lane_mode == SHAPE_BANDS
    view = controller.bridge.values[SHAPER]
    shaper = controller.session.values[SHAPER]
    baked = bake_terrain_shaper(shaper)
    assert [b[0] for b in view["bars"]] == pytest.approx(list(baked["bias"]), abs=1e-5)
    assert [b[1] for b in view["bars"]] == pytest.approx(list(baked["weight"]), abs=1e-5)
    spans = [(view["laneProfile"][i][0], view["laneProfile"][i + 1][0], view["laneProfile"][i][1])
             for i in range(0, len(view["laneProfile"]), 2)]
    samples = len(baked["lane"])
    for index, lane in enumerate(baked["lane"]):
        height = index / (samples - 1)
        strength = shaper["lanes"][REACTION_LANES[int(lane)]]
        owner = [s for a, b, s in spans if a <= height + 1e-9 and (height + 1e-9 < b or b == 1.0)]
        assert owner and owner[-1] == pytest.approx(strength), index
    assert view["lanes"][0]["pinned"] and not any(lane["pinned"] for lane in view["lanes"][1:])


# ---------------------------------------------------------------------------------------- gestures (bridge)
@pytest.mark.parametrize("mode,prop_id", INSTRUMENTS)
def test_a_node_drag_previews_once_per_frame_and_commits_once_on_release(studio, mode, prop_id):
    controller, surface, store = studio(mode)
    bridge, session = controller.bridge, controller.session
    before = _nodes(controller, prop_id)
    index = len(before) - 1
    left = before[index - 1][0] if index else 0.0
    target = [round((left + before[index][0]) / 2.0, 3), round(1.0 - before[index][1], 3)]   # inside its own gap
    applied, undo_before = bridge.shapes.previews, session.undo_label
    bridge.shapePress(prop_id, "node", index)
    for step in range(1, 13):                                        # many moves between two frames
        bridge.shapeDrag(prop_id, before[index][0] + (target[0] - before[index][0]) * step / 12.0,
                         before[index][1] + (target[1] - before[index][1]) * step / 12.0)
    assert _nodes(controller, prop_id) == before                     # nothing applied before the frame
    surface.pump()
    assert bridge.shapes.previews == applied + 1                     # one preview for the twelve moves
    assert _nodes(controller, prop_id)[index] == pytest.approx(target)
    assert bridge.values[prop_id]["nodes"][index] == pytest.approx(target)     # the canvas shows the admitted value
    assert bridge.values[prop_id]["active"] == {"part": "node", "index": index}
    assert store.commits == 0 and _stored_nodes(store, controller, prop_id) == before   # nothing saved while held
    bridge.shapeRelease()
    assert store.commits == 1 and session.undo_label and session.undo_label != undo_before
    assert _stored_nodes(store, controller, prop_id)[index] == pytest.approx(target)
    assert "active" not in bridge.values[prop_id]
    bridge.undo()
    assert _nodes(controller, prop_id) == before and _stored_nodes(store, controller, prop_id) == before
    bridge.redo()
    assert _nodes(controller, prop_id)[index] == pytest.approx(target)


def test_per_move_previews_fail_the_one_per_frame_check_negative_control(studio):
    mode, prop_id = INSTRUMENTS[0]
    controller, surface, store = studio(mode)
    bridge = controller.bridge
    node = _nodes(controller, prop_id)[0]
    applied = bridge.shapes.previews
    bridge.shapePress(prop_id, "node", 0)
    for step in range(1, 13):
        bridge.shapeDrag(prop_id, node[0], max(0.0, min(1.0, node[1] + 0.01 * step)))
        bridge.apply_pending_previews()                              # the per-move path the instrument avoids
    surface.pump()
    assert bridge.shapes.previews - applied == 12
    bridge.shapeCancel()
    assert store.commits == 0 and _nodes(controller, prop_id)[0] == node          # Escape: nothing saved, restored


@pytest.mark.parametrize("mode,prop_id", INSTRUMENTS)
def test_a_dragged_node_passes_its_neighbour_and_the_curve_stays_in_order(studio, mode, prop_id):
    """Settings' shape editor rule: the dragged node goes where the pointer is and the list is kept in x order; the
    gesture follows the node to its new index."""
    controller, surface, _store = studio(mode)
    bridge = controller.bridge
    before = _nodes(controller, prop_id)
    if len(before) < 2:
        _thin(controller, prop_id, 1)
        pytest.skip("one node: nothing to pass")
    last = len(before) - 1
    target_x = round(before[0][0] / 2.0, 4) if before[0][0] > 0.01 else 0.0     # before the first node
    bridge.shapePress(prop_id, "node", last)
    bridge.shapeDrag(prop_id, target_x, 0.5)
    surface.pump()
    after = _nodes(controller, prop_id)
    xs = [x for x, _y in after]
    assert xs == sorted(xs) and len(after) == len(before)
    moved = bridge.values[prop_id]["active"]["index"]
    assert after[moved] == pytest.approx([target_x, 0.5]) and moved < last
    assert sorted(map(tuple, after[:moved] + after[moved + 1:])) == sorted(map(tuple, before[:last]))
    bridge.shapeRelease()
    assert controller.session.commit_count == 1


@pytest.mark.parametrize("mode,prop_id", INSTRUMENTS)
def test_click_adds_a_node_within_the_limit_and_removal_stops_at_the_minimum(studio, mode, prop_id):
    controller, surface, store = studio(mode)
    bridge, session = controller.bridge, controller.session
    low, high = _spec(controller, prop_id).node_limits
    _thin(controller, prop_id, low)
    assert len(_nodes(controller, prop_id)) == low
    commits = store.commits
    bridge.runAction(f"{_spec(controller, prop_id).remove}0")        # at the minimum: refused, nothing saved
    assert len(_nodes(controller, prop_id)) == low and store.commits == commits
    assert bridge.values[prop_id]["canRemove"] is False
    # A press on empty space adds a node there and holds it: it follows the pointer until release (one commit).
    while len(_nodes(controller, prop_id)) < high:
        count = len(_nodes(controller, prop_id))
        commits = store.commits
        spot = [round(0.07 + 0.17 * count, 4), round(0.2 + 0.1 * count, 4)]
        bridge.shapePress(prop_id, "add", -1)
        bridge.shapeDrag(prop_id, spot[0] + 0.01, spot[1])
        surface.pump()
        assert len(_nodes(controller, prop_id)) == count + 1 and store.commits == commits
        bridge.shapeDrag(prop_id, spot[0], spot[1])                  # still held: the new node moves
        surface.pump()
        nodes = _nodes(controller, prop_id)
        assert len(nodes) == count + 1 and any(node == pytest.approx(spot) for node in nodes)
        assert [x for x, _y in nodes] == sorted(x for x, _y in nodes)
        bridge.shapeRelease()
        assert store.commits == commits + 1 and len(_stored_nodes(store, controller, prop_id)) == count + 1
    # At the maximum the canvas offers no add and a press on empty space changes nothing.
    assert bridge.values[prop_id]["canAdd"] is False
    full, commits = _nodes(controller, prop_id), store.commits
    bridge.shapePress(prop_id, "add", -1)
    bridge.shapeDrag(prop_id, 0.5, 0.5)
    surface.pump()
    bridge.shapeRelease()
    assert _nodes(controller, prop_id) == full and store.commits == commits
    bridge.undo()                                                    # the last add is one undoable step
    assert len(_nodes(controller, prop_id)) == high - 1 and session.redo_label


@pytest.mark.parametrize("mode,prop_id", INSTRUMENTS)
def test_lane_moves_and_strengths_are_single_commits_and_keep_the_lane_set(studio, mode, prop_id):
    controller, surface, store = studio(mode)
    bridge = controller.bridge
    spec = _spec(controller, prop_id)
    notches, strengths = _notches(controller, prop_id), _strengths(controller, prop_id)
    index = len(notches) - 1
    label = notches[index][1]
    floor = notches[index - 1][0]
    target = round((floor + notches[index][0]) / 2.0, 3) if notches[index][0] - floor > 0.02 else notches[index][0]
    # Position: the lane's tag moves along the axis; strengths and the other lanes stay.
    bridge.shapePress(prop_id, "lane", index)
    for step in range(1, 9):
        bridge.shapeDrag(prop_id, notches[index][0] + (target - notches[index][0]) * step / 8.0, 0.9)
    surface.pump()
    assert _notches(controller, prop_id)[index] == [pytest.approx(target), label]
    assert _strengths(controller, prop_id) == strengths and store.commits == 0
    bridge.shapeRelease()
    assert store.commits == (1 if target != notches[index][0] else 0)
    # Past its neighbour: the lanes change order (Settings' rule), the set of lanes and their strengths never do.
    commits = store.commits
    bridge.shapePress(prop_id, "lane", index)
    bridge.shapeDrag(prop_id, max(0.0, round(floor / 2.0, 3)) if spec.pinned_lanes == 0 else round(floor / 2.0, 3), 0.0)
    surface.pump()
    moved = _notches(controller, prop_id)
    assert sorted(n[1] for n in moved) == sorted(n[1] for n in notches)
    assert [n[0] for n in moved] == sorted(n[0] for n in moved)
    assert bridge.values[prop_id]["active"]["index"] == next(i for i, n in enumerate(moved) if n[1] == label)
    assert bridge.values[prop_id]["active"]["index"] < index
    bridge.shapeRelease()
    assert store.commits == commits + 1 and _strengths(controller, prop_id) == strengths
    bridge.undo()
    # Strength: the lane's marker moves up and down; positions stay.
    positions = _notches(controller, prop_id)
    wanted = round(0.25 if strengths[label] > 0.5 else 0.75, 3)
    commits = store.commits
    at = next(i for i, n in enumerate(positions) if n[1] == label)
    bridge.shapePress(prop_id, "strength", at)
    for step in range(1, 9):
        bridge.shapeDrag(prop_id, 0.0, strengths[label] + (wanted - strengths[label]) * step / 8.0)
    surface.pump()
    assert _strengths(controller, prop_id)[label] == pytest.approx(wanted) and store.commits == commits
    bridge.shapeRelease()
    assert store.commits == commits + 1 and _notches(controller, prop_id) == positions
    assert {k: v for k, v in _strengths(controller, prop_id).items() if k != label} == {
        k: v for k, v in strengths.items() if k != label}
    assert bridge.values[prop_id]["laneProfile"] != [] and controller.session.undo_label


def test_a_pinned_lane_keeps_its_place_and_nothing_passes_it(studio):
    """Neon Lake's shaper pins its first boundary at the shoreline (the canonical shaper rule): its tag takes no
    drag, another lane dragged to it stays above it, and its strength is still editable."""
    from ui.studio.shockwave_grid_adapter import SHAPER
    controller, surface, store = studio("shockwave_grid")
    bridge = controller.bridge
    assert _spec(controller, SHAPER).pinned_lanes == 1
    notches = _notches(controller, SHAPER)
    bridge.shapePress(SHAPER, "lane", 0)
    bridge.shapeDrag(SHAPER, 0.5, 0.0)
    surface.pump()
    bridge.shapeRelease()
    assert _notches(controller, SHAPER) == notches and store.commits == 0
    bridge.shapePress(SHAPER, "lane", 2)
    bridge.shapeDrag(SHAPER, 0.0, 0.0)
    surface.pump()
    bridge.shapeRelease()
    moved = _notches(controller, SHAPER)
    assert moved[0] == notches[0] and store.commits == 1
    assert sorted(n[1] for n in moved) == sorted(n[1] for n in notches)
    pinned = notches[0][1]
    bridge.shapePress(SHAPER, "strength", 0)
    bridge.shapeDrag(SHAPER, 0.0, 0.11)
    surface.pump()
    bridge.shapeRelease()
    assert _strengths(controller, SHAPER)[pinned] == pytest.approx(0.11) and store.commits == 2


@pytest.mark.parametrize("mode", [m for m in FAMILY])
def test_each_layout_keeps_its_own_lanes_and_the_canvas_follows_the_switch(studio, mode):
    controller, surface, _store = studio(mode)
    bridge, session = controller.bridge, controller.session
    prop_id = mode + "_shape_nodes"
    spec = _spec(controller, prop_id)
    view = bridge.values[prop_id]
    switch = view["layoutSwitch"]
    assert switch and len(view["layouts"]) == 2
    mirrored = bool(session.values[switch])
    other = spec.layouts[0 if mirrored else 1]
    other_notches = deepcopy(read_path(session.values, other.notches))
    other_lanes = deepcopy(read_path(session.values, other.lanes))
    bridge.shapePress(prop_id, "strength", 0)
    bridge.shapeDrag(prop_id, 0.0, 0.07)
    surface.pump()
    bridge.shapeRelease()
    assert read_path(session.values, other.notches) == other_notches       # the other layout's lanes are untouched
    assert read_path(session.values, other.lanes) == other_lanes
    bridge.commitValue(switch, 0, not mirrored)
    after = bridge.values[prop_id]
    assert after["mirrored"] is (not mirrored)
    assert [(lane["x"], lane["label"]) for lane in after["lanes"]] == [tuple(n) for n in other_notches]
    assert after["nodes"] == view["nodes"]                               # one curve under both layouts
    bridge.undo()
    assert bridge.values[prop_id]["mirrored"] is mirrored


@pytest.mark.parametrize("mode,prop_id", INSTRUMENTS)
def test_exact_entry_and_keyboard_steps_commit_one_edit_each(studio, mode, prop_id):
    from ui.studio.shape import STEP
    controller, _surface, store = studio(mode)
    bridge = controller.bridge
    selected = []
    bridge.shapeSelected.connect(lambda *args: selected.append(args))
    node = _nodes(controller, prop_id)[0]
    typed = round(1.0 - node[1], 3)
    bridge.shapeCommitText(prop_id, "node", 0, 1, f"{typed}")
    assert _nodes(controller, prop_id)[0] == [node[0], pytest.approx(typed)] and store.commits == 1
    bridge.shapeCommitText(prop_id, "node", 0, 1, "not a number")       # refused: a notice, nothing saved
    assert store.commits == 1 and bridge.message
    bridge.shapeStep(prop_id, "node", 0, 0, 1 if typed < 0.5 else -1)
    assert _nodes(controller, prop_id)[0][1] == pytest.approx(typed + (STEP if typed < 0.5 else -STEP))
    assert store.commits == 2
    lane = _notches(controller, prop_id)[-1][1]
    index = len(_notches(controller, prop_id)) - 1
    bridge.shapeCommitText(prop_id, "lane", index, 1, "0.5")
    assert _strengths(controller, prop_id)[lane] == pytest.approx(0.5) and store.commits == 3
    # A typed position past a neighbour carries the element along: the shell is told its new index.
    nodes = _nodes(controller, prop_id)
    if len(nodes) > 1:
        last = len(nodes) - 1
        typed_x = round(max(0.0, nodes[0][0] / 2.0), 4)
        bridge.shapeCommitText(prop_id, "node", last, 0, f"{typed_x:.4f}")
        after = _nodes(controller, prop_id)
        landed = [i for i, node in enumerate(after) if node == pytest.approx([typed_x, nodes[last][1]])]
        assert landed and landed[0] < last and selected and selected[-1] == (prop_id, "node", landed[0])
    bridge.undo()
    assert store.commits >= 4


# ------------------------------------------------------------------------------------- the real shell (pointer)
def _row(surface, controller, prop_id):
    from tools.studio_shape_capture import _named, _shown, reveal, settle
    controller.bridge.setWorkspace(controller.session.schema.find(prop_id).workspace)
    surface.pump(3)
    row = next(item for item in _named(surface.host.root, "shapeRow")
               if _shown(item) and item.property("row")["id"] == prop_id)
    reveal(row)
    settle(surface, 0.05)
    return row, _named(row, "shapeWell")[0]


@pytest.mark.parametrize("mode,prop_id", INSTRUMENTS)
def test_the_pointer_drags_adds_and_removes_nodes_on_the_real_canvas(studio, mode, prop_id):
    from PySide6.QtCore import Qt
    from tools.studio_shape_capture import Pointer, _named, node_point, settle
    controller, surface, store = studio(mode)
    bridge = controller.bridge
    low, high = _spec(controller, prop_id).node_limits
    _thin(controller, prop_id, max(low, min(high - 1, 3)))
    commits = store.commits
    row, well = _row(surface, controller, prop_id)
    pointer = Pointer(surface, well)
    before = _nodes(controller, prop_id)
    assert len(_named(row, "shapeNode")) == len(before)             # one handle per stored node
    index = len(before) - 1
    x, y = node_point(row, index)
    width, top, height = row.property("plotW"), row.property("plotT"), row.property("plotH")
    goal = (x + (0.12 * width if x < well.width() / 2 else -0.12 * width), top + height * (0.35 if y > top + height / 2 else 0.7))
    applied = bridge.shapes.previews
    pointer.press(x, y)
    for step in range(1, 11):                                        # ten moves, with a wobble, inside one frame
        pointer.move(x + (goal[0] - x) * step / 10.0, y + (goal[1] - y) * step / 10.0 + (3 if step % 2 else -3))
    pointer.move(*goal)
    surface.pump()
    assert bridge.shapes.previews == applied + 1 and store.commits == commits
    assert row.property("dragPart") == "node" and controller.session.gesture_active
    held = bridge.values[prop_id]["active"]["index"]
    hx, hy = node_point(row, held)
    assert (hx, hy) == pytest.approx(goal, abs=1.0)                  # the handle is under the pointer
    pointer.release(*goal)
    surface.pump()
    assert store.commits == commits + 1 and row.property("dragPart") == ""
    assert _nodes(controller, prop_id) != before and len(_nodes(controller, prop_id)) == len(before)
    # A click on empty space adds a node there; a right-click on it removes it again.
    count = len(_nodes(controller, prop_id))
    handles = [node_point(row, i) for i in range(count)] + [
        (m.x() + m.width() / 2, m.y() + m.height() / 2) for m in _named(row, "shapeLaneMarker")]
    span = width * (0.5 if row.property("mirrored") else 1.0)           # the editable part of the plot
    spots = [(row.property("plotL") + span * fx / 12.0, top + height * fy / 8.0)
             for fx in range(1, 12) for fy in range(1, 8)]
    spot = max(spots, key=lambda p: min((p[0] - hx) ** 2 + (p[1] - hy) ** 2 for hx, hy in handles))
    assert min((spot[0] - hx) ** 2 + (spot[1] - hy) ** 2 for hx, hy in handles) > 16 ** 2     # clear of every handle
    pointer.press(*spot)
    surface.pump()
    pointer.release(*spot)
    settle(surface, 0.05)
    assert len(_nodes(controller, prop_id)) == count + 1 and store.commits == commits + 2
    added = min(range(count + 1), key=lambda i: (node_point(row, i)[0] - spot[0]) ** 2 + (node_point(row, i)[1] - spot[1]) ** 2)
    assert node_point(row, added) == pytest.approx(spot, abs=1.0)
    pointer.press(*node_point(row, added), button=Qt.MouseButton.RightButton)
    pointer.release(*spot, button=Qt.MouseButton.RightButton)
    settle(surface, 0.05)
    assert len(_nodes(controller, prop_id)) == count and store.commits == commits + 3
    # At the minimum a right-click removes nothing (negative control for the removal above).
    _thin(controller, prop_id, low)
    settle(surface, 0.05)
    commits = store.commits
    spot = node_point(row, 0)
    pointer.press(*spot, button=Qt.MouseButton.RightButton)
    pointer.release(*spot, button=Qt.MouseButton.RightButton)
    settle(surface, 0.05)
    assert len(_nodes(controller, prop_id)) == low and store.commits == commits


@pytest.mark.parametrize("mode,prop_id", INSTRUMENTS)
def test_a_strength_diamond_exactly_under_a_node_and_the_node_both_take_a_press(studio, mode, prop_id):
    """1B.4 side defect: nodes were hit first, so a lane's strength diamond under a curve node could not be grabbed.
    The nearer element takes the press; where they overlap the pointer's half decides (below the diamond's centre:
    the strength marker; above or on it: the node)."""
    from tools.studio_shape_capture import Pointer, _named, node_point, settle
    controller, surface, _store = studio(mode)
    bridge = controller.bridge
    row, well = _row(surface, controller, prop_id)
    lanes = row.property("lanes")
    lane = next(i for i in range(len(lanes) - 1, -1, -1) if not lanes[i].get("pinned"))
    target = (float(lanes[lane]["x"]), float(lanes[lane]["strength"]))
    nodes = _nodes(controller, prop_id)
    nearest = min(range(len(nodes)), key=lambda i: abs(nodes[i][0] - target[0]))
    bridge.shapeCommitText(prop_id, "node", nearest, 0, f"{target[0]:.6f}")
    moved = min(range(len(_nodes(controller, prop_id))),
                key=lambda i: abs(_nodes(controller, prop_id)[i][0] - target[0]))
    bridge.shapeCommitText(prop_id, "node", moved, 1, f"{target[1]:.6f}")
    settle(surface, 0.3)
    marker = _named(row, "shapeLaneMarker")[lane]
    centre = (marker.x() + marker.width() / 2.0, marker.y() + marker.height() / 2.0)
    under = [i for i in range(len(_nodes(controller, prop_id)))
             if abs(node_point(row, i)[0] - centre[0]) < 0.5 and abs(node_point(row, i)[1] - centre[1]) < 0.5]
    assert under, "the test could not place a node over the diamond"
    pointer = Pointer(surface, well)
    for offset, part in ((3.0, "strength"), (-3.0, "node"), (0.0, "node")):
        pointer.press(centre[0], centre[1] + offset)
        assert row.property("dragPart") == part, (offset, row.property("dragPart"))
        pointer.release(centre[0], centre[1] + offset)
        surface.pump()
    # Apart, the nearer element wins: just beside the diamond on the side away from the node, the diamond.
    bridge.shapeCommitText(prop_id, "node", under[0], 1, f"{min(1.0, target[1] + 0.25):.6f}"
                           if target[1] < 0.75 else f"{target[1] - 0.25:.6f}")
    settle(surface, 0.3)
    node_y = node_point(row, under[0])[1]
    away = centre[1] + (4.0 if node_y < centre[1] else -4.0)
    pointer.press(centre[0], away)
    assert row.property("dragPart") == "strength"
    pointer.release(centre[0], away)
    surface.pump()


def test_nothing_pops_a_layout_change_fades_through_and_nodes_fade_in_and_out(studio):
    """Fade, never vanish: on the frame after a layout change the canvas is not yet showing the new layout at full
    strength; a node added by the button eases in and a removed one leaves a fading mark where it was."""
    from tools.studio_shape_capture import _named, settle
    mode, prop_id = next((m, p) for m, p in INSTRUMENTS if create_adapter(m).schema().shape(p).layout_switch)
    controller, surface, _store = studio(mode)
    bridge = controller.bridge
    row, _well = _row(surface, controller, prop_id)
    settle(surface, 0.4)
    assert row.property("contentOpacity") == 1.0
    mirrored = bool(row.property("mirrored"))
    assert bridge.values[prop_id]["mirrored"] is mirrored
    bridge.commitValue(bridge.values[prop_id]["layoutSwitch"], 0, not mirrored)
    surface.pump()
    assert bool(row.property("mirrored")) is mirrored or row.property("contentOpacity") < 1.0   # not popped in
    settle(surface, 0.6)
    assert bool(row.property("mirrored")) is (not mirrored) and row.property("contentOpacity") == 1.0
    # A node removed by the mode's action: a mark fades out where it was; added again: its handle eases in.
    spec = _spec(controller, prop_id)
    _thin(controller, prop_id, spec.node_limits[1] - 1)
    settle(surface, 0.5)
    ghost = _named(row, "shapeVanished")[0]
    assert ghost.opacity() == 0.0
    count = len(_named(row, "shapeNode"))
    bridge.runAction(f"{spec.remove}0")
    surface.pump()
    assert len(_named(row, "shapeNode")) == count - 1 and ghost.opacity() > 0.0
    settle(surface, 0.5)
    assert ghost.opacity() == 0.0
    bridge.runAction(spec.add)
    surface.pump()
    handles = _named(row, "shapeNode")
    assert len(handles) == count and min(item.opacity() for item in handles) < 1.0
    settle(surface, 0.5)
    assert all(item.opacity() == 1.0 for item in _named(row, "shapeNode"))


def test_the_canvas_is_painted_and_follows_the_studio_theme_tokens(studio):
    """The well shows the curve and its preview in the Studio theme's well inks, and repaints in a changed theme
    (a canvas that kept its own colours, or whose paint failed, would not show the new ink). Before the theme
    changes that ink is nowhere in the well (negative control)."""
    import numpy as np
    from PySide6.QtCore import QPointF
    mode, prop_id = INSTRUMENTS[0]
    controller, surface, _store = studio(mode)
    _row_item, well = _row(surface, controller, prop_id)
    surface.pump(3)
    origin = well.mapToScene(QPointF(0.0, 0.0))
    x, y = int(origin.x()) + 8, int(origin.y()) + 8

    def region():
        return surface.grab()[y:y + int(well.height()) - 16, x:x + int(well.width()) - 16, :3].astype(int)

    def inked(pixels, hex_colour) -> int:
        ink = np.array([int(hex_colour[i:i + 2], 16) for i in (1, 3, 5)])
        return int((np.abs(pixels - ink).sum(axis=2) <= 12).sum())

    tokens = dict(controller.bridge.theme)
    assert tokens["wellTrace1"] and tokens["wellTrace3"]
    marker = "#ff00c8"                                              # an ink no shipped theme derives
    first = region()
    assert len(np.unique(first.reshape(-1, 3), axis=0)) > 40        # a drawn plot, not a bare well
    assert inked(first, marker) == 0
    controller.bridge.set_theme({**tokens, "wellTrace1": marker})
    surface.pump(3)
    assert inked(region(), marker) > 60                             # the curve and the node rims took the new ink


def test_the_keyboard_walks_steps_and_removes_the_selected_element(studio):
    """Real key events on the focused canvas: Ctrl+Right walks the elements (nodes, then lanes), an arrow steps the
    selected one as one committed edit, Delete removes a node, Esc drops the selection. Without a selection an Up
    arrow changes nothing (negative control)."""
    from PySide6.QtCore import QCoreApplication, QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from tools.studio_shape_capture import settle
    from ui.studio.shape import STEP
    mode, prop_id = INSTRUMENTS[0]
    controller, surface, store = studio(mode)
    low, high = _spec(controller, prop_id).node_limits
    _thin(controller, prop_id, max(low + 1, min(high, 3)))
    commits = store.commits
    row, well = _row(surface, controller, prop_id)
    well.forceActiveFocus()

    def key(code, modifiers=Qt.KeyboardModifier.NoModifier):
        for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            QCoreApplication.sendEvent(surface.window, QKeyEvent(kind, code, modifiers))
        settle(surface, 0.03)

    nodes = _nodes(controller, prop_id)
    key(Qt.Key.Key_Up)
    assert row.property("selPart") == "" and _nodes(controller, prop_id) == nodes and store.commits == commits
    key(Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)
    assert (row.property("selPart"), row.property("selIndex")) == ("node", 0)
    for _ in range(len(nodes)):
        key(Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)
    assert (row.property("selPart"), row.property("selIndex")) == ("lane", 0)       # past the last node: the lanes
    key(Qt.Key.Key_Left, Qt.KeyboardModifier.ControlModifier)
    assert (row.property("selPart"), row.property("selIndex")) == ("node", len(nodes) - 1)
    last = nodes[-1]
    down = last[1] > 0.5
    key(Qt.Key.Key_Down if down else Qt.Key.Key_Up)
    assert _nodes(controller, prop_id)[-1] == [last[0], pytest.approx(last[1] + (-STEP if down else STEP))]
    assert store.commits == commits + 1
    key(Qt.Key.Key_Delete)
    assert len(_nodes(controller, prop_id)) == len(nodes) - 1 and store.commits == commits + 2
    assert row.property("selPart") == ""
    key(Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)
    assert row.property("selPart") == "node"
    key(Qt.Key.Key_Escape)
    assert row.property("selPart") == "" and controller.state == "presented"        # Esc took the selection only


# ------------------------------------------------------------- no I/O while a shape drag moves (plan 1B.3's rule)
_MANAGER_WRITES = ("set", "set_many", "set_section", "set_widgets_map", "save", "flush", "remove",
                   "replace_visualizer_runtime_preset_state")


class _Writes:
    """Counts every write-shaped call while armed: Settings mutations, the tab's save, files opened for writing or
    replaced, INFO+ log lines and engine analyses started (the counters of ``tests/test_studio_drag_io_churn.py``,
    which drives every other drag instrument the same way)."""

    def __init__(self, monkeypatch, manager, tab, jobs) -> None:
        import builtins
        import io
        import logging
        import os
        self.manager, self.jobs, self.armed, self.counts = manager, jobs, False, {}
        for name in _MANAGER_WRITES:
            if hasattr(manager, name):
                monkeypatch.setattr(manager, name, self._wrap(f"settings.{name}", getattr(manager, name)))
        monkeypatch.setattr(tab, "_save_settings_now", self._wrap("tab.save", tab._save_settings_now))
        opener = builtins.open

        def counting_open(file, mode="r", *args, **kwargs):
            if any(flag in str(mode) for flag in "wax+"):
                self._note(f"file.write: {os.path.basename(str(file))}")
            return opener(file, mode, *args, **kwargs)
        monkeypatch.setattr(builtins, "open", counting_open)
        monkeypatch.setattr(io, "open", counting_open)
        monkeypatch.setattr(os, "replace", self._wrap("file.replace", os.replace))
        counter = self

        class _Logs(logging.Handler):
            def emit(self, record):
                if record.levelno >= logging.INFO:
                    counter._note(f"log.{record.name}")
        self._handler, self._root = _Logs(level=logging.DEBUG), logging.getLogger()
        self._level = self._root.level
        self._root.addHandler(self._handler)
        self._root.setLevel(logging.DEBUG)

    def close(self) -> None:
        self._root.removeHandler(self._handler)
        self._root.setLevel(self._level)

    def _note(self, name) -> None:
        if self.armed:
            self.counts[name] = self.counts.get(name, 0) + 1

    def _wrap(self, name, original):
        def wrapper(*args, **kwargs):
            self._note(name)
            return original(*args, **kwargs)
        return wrapper

    def measure(self, action) -> dict:
        revision, jobs = self.manager.persistence_snapshot()["state_revision"], len(self.jobs)
        self.counts, self.armed = {}, True
        try:
            action()
        finally:
            self.armed = False
        counts = dict(self.counts)
        if self.manager.persistence_snapshot()["state_revision"] != revision:
            counts["settings.revision"] = 1
        if len(self.jobs) != jobs:
            counts["engine.analysis"] = len(self.jobs) - jobs
        return counts


@pytest.fixture
def settings_studio(qt_app, tmp_path, monkeypatch):
    """The mode's Studio opened from its real Settings body (a never-shown ``VisualizersTab`` over a real
    ``SettingsManager`` on a temporary profile, on Custom so a commit saves), with the write counters."""
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    from core.settings.settings_manager import SettingsManager
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.studio.controller import StudioController
    from ui.studio.settings_link import open_mode_studio
    from ui.studio.surface import OffscreenStudioSurface
    from ui.tabs.visualizers_tab import VisualizersTab
    disable_per_call_gl_error_checking()
    manager = SettingsManager(organization="SRPSSFocusedTests", application="StudioShapeInstrument",
                              storage_base_dir=tmp_path / "profile")
    made = []

    def build(mode):
        manager.set("widgets", {"spotify_visualizer": {
            "enabled": True, "visualizers_enabled": True, "mode": mode,
            "mode_activation": build_visualizer_mode_activation([mode]),
            f"preset_{mode}": get_custom_preset_index(mode)}})
        dialog = QDialog()                                     # never shown
        QVBoxLayout(dialog).addWidget(tab := VisualizersTab(manager))
        tab._select_mode_page(mode)
        jobs: list = []
        adapter = create_adapter(mode)
        adapter.recorded_clips = lambda: ()
        adapter.create_renderer = _QuietRenderer
        real_evaluator = adapter.create_evaluator

        class _Counted:
            def __call__(self, *args):
                jobs.append(args)                              # each start is one engine re-analysis
                return self

            def cancel(self):
                pass

        def evaluator():
            made_evaluator = real_evaluator()
            made_evaluator._loader = _Counted()
            return made_evaluator
        adapter.create_evaluator = evaluator
        surfaces = []

        def factory(controller):
            surfaces.append(OffscreenStudioSurface(controller, size=(1280, 760), present_on_show=False))
            return surfaces[-1]
        controller = open_mode_studio(tab, mode, adapter=adapter, surface_factory=factory)
        surfaces[0].pump(3)
        assert controller.state == "presented"
        counter = _Writes(monkeypatch, manager, tab, jobs)
        made.append((dialog, controller, counter))
        return controller, surfaces[0], counter
    yield build
    for dialog, controller, counter in made:
        counter.close()
        if StudioController.active() is controller:
            controller.close()
        dialog.deleteLater()
    qt_app.processEvents()
    assert manager.flush(timeout=5.)


def _shape_drags(controller, prop_id):
    """(name, part, index, moves) for one drag of each kind the instrument has: a node, a lane's tag, a lane's
    strength marker and a press on empty space (when the curve has room). Each move is one pointer position."""
    nodes, notches = _nodes(controller, prop_id), _notches(controller, prop_id)
    strengths, spec = _strengths(controller, prop_id), _spec(controller, prop_id)
    node = nodes[-1]
    rise = -0.05 if node[1] > 0.5 else 0.05
    plans = [("node", "node", len(nodes) - 1, [(node[0], node[1] + rise * k) for k in (1, 2, 3, 4)])]
    lane = len(notches) - 1
    room = notches[lane][0] - notches[lane - 1][0]
    plans.append(("lane", "lane", lane, [(notches[lane][0] - room * 0.1 * k, 0.0) for k in (1, 2, 3, 4)]))
    strength = strengths[notches[lane][1]]
    step = -0.05 if strength > 0.5 else 0.05
    plans.append(("strength", "strength", lane, [(0.0, strength + step * k) for k in (1, 2, 3, 4)]))
    if len(nodes) < spec.node_limits[1]:
        plans.append(("add", "add", -1, [(0.5 + 0.01 * k, 0.5) for k in (1, 2, 3, 4)]))
    return plans


def _per_move(counts: dict, moves: int) -> dict:
    """What a drag's moves did that they may not: any write, store change or analysis, and log lines that keep pace
    with the moves (an event-edge line, such as an earlier change's replay landing, is not per move)."""
    logs = sum(n for name, n in counts.items() if name.startswith("log."))
    churn = {name: n for name, n in counts.items() if not name.startswith("log.")}
    if logs >= moves:
        churn.update({name: n for name, n in counts.items() if name.startswith("log.")})
    return churn


@pytest.mark.parametrize("mode,prop_id", INSTRUMENTS)
def test_a_shape_drag_writes_nothing_while_it_moves_and_saves_once_on_release(settings_studio, mode, prop_id):
    """Through Settings' own owners: while the pointer is held nothing reaches the settings store, the tab's save, a
    file, the log or the engine's analysis; the release is one session commit and one tab save."""
    controller, surface, counter = settings_studio(mode)
    bridge, session = controller.bridge, controller.session
    _thin(controller, prop_id, _spec(controller, prop_id).node_limits[1] - 1)       # room for the add gesture
    surface.pump(3)
    counter.manager.flush(timeout=5.)
    churn, faults = {}, {}
    for name, part, index, moves in _shape_drags(controller, prop_id):
        commits = session.commit_count

        def during():
            bridge.shapePress(prop_id, part, index)
            for x, y in moves:
                bridge.shapeDrag(prop_id, x, y)
                surface.pump()
        moving = _per_move(counter.measure(during), len(moves))
        assert session.gesture_active and session.commit_count == commits, name
        released = counter.measure(lambda: (bridge.shapeRelease(), surface.pump(3), counter.manager.flush(timeout=5.)))
        if moving:
            churn[name] = moving
        if not (session.commit_count == commits + 1 and released.get("tab.save", 0) == 1
                and released.get("settings.revision")):
            faults[name] = (session.commit_count - commits, released)
        bridge.undo()
        surface.pump(2)
        counter.manager.flush(timeout=5.)
    assert churn == {}, f"{mode} {prop_id}: writes while dragging: {churn}"
    assert faults == {}, f"{mode} {prop_id}: release did not save exactly once: {faults}"


def test_a_commit_per_move_is_seen_by_the_counters_negative_control(settings_studio):
    """The shape of a churning instrument: each move commits (here the exact entry, which commits per call)."""
    mode, prop_id = INSTRUMENTS[0]
    controller, surface, counter = settings_studio(mode)
    bridge = controller.bridge
    height = _nodes(controller, prop_id)[0][1]
    step = -0.05 if height > 0.5 else 0.05

    def during():
        for k in (1, 2, 3, 4):
            bridge.shapeCommitText(prop_id, "node", 0, 1, f"{height + step * k:.3f}")
            surface.pump()
    moving = _per_move(counter.measure(during), 4)
    assert moving.get("tab.save", 0) == 4 and moving.get("settings.revision")
