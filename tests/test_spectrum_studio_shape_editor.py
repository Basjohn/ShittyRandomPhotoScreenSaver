"""The Spectrum Studio covers everything Settings' Spectrum shape editor does (the last part of its builder).

Settings' shape editor (``SpectrumShapeEditor``) offers, by mouse: add a node (left-click, up to the maximum), remove
a node (right-click, down to the minimum), drag a node (re-sorted past a neighbour), drag a frequency boundary (a
drag past a neighbour reorders the lanes), drag a lane's strength arrow, plus the Mirrored Layout toggle. Each
capability is driven on the *real* Settings widget and saved by Settings; then, from the same starting values, the
Studio reaches exactly the same stored values using only what its shell offers (row values, Add Node, Remove Node,
lane swaps), saved through its canonical store. A seeded mixed sequence of Settings gestures is reached too, and a
Studio without the structural edits cannot reach a node-count change (negative control). Every key Settings' shape
builder collects is a Studio key. Values are test-owned (canonical defaults, never presets). Nothing shows a window.
"""
from __future__ import annotations

import random

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from ui.studio.spectrum_adapter import (
    ADD_NODE, LANE_NEXT, LANE_PREVIOUS, NOTCHES, REMOVE_NODE, SHAPE_NODES, build_schema,
)
from tests.test_spectrum_studio import (  # noqa: F401  (fixtures)
    LightAdapter, _surfaces, dialog_tab, no_gl_checks, settings_manager,
)

MODE = "spectrum"
MIRRORED = "spectrum_mirrored"


def _shape_keys(tab) -> tuple[str, ...]:
    from ui.tabs.media.spectrum_settings_binding import collect_spectrum_shape
    return tuple(sorted(collect_spectrum_shape(tab)))


def _stored(settings_manager, keys) -> dict:
    section = settings_manager.get("widgets")["spotify_visualizer"]
    return {key: section[key] for key in keys}


# ------------------------------------------------------------------------------ Settings' own gestures
class SettingsShaper:
    """Mouse gestures on the real Settings shape editor (sized, never shown), saved by Settings."""

    def __init__(self, tab):
        self.tab = tab
        self.editor = tab.spectrum_shape_editor
        self.editor.resize(640, 220)

    def _send(self, kind, x, y, button, buttons):
        event = QMouseEvent(kind, QPointF(x, y), QPointF(x, y), button, buttons, Qt.KeyboardModifier.NoModifier)
        {QEvent.Type.MouseButtonPress: self.editor.mousePressEvent,
         QEvent.Type.MouseMove: self.editor.mouseMoveEvent,
         QEvent.Type.MouseButtonRelease: self.editor.mouseReleaseEvent}[kind](event)

    def drag(self, start, end, button=Qt.MouseButton.LeftButton):
        none = Qt.MouseButton.NoButton
        self._send(QEvent.Type.MouseButtonPress, *start, button, button)
        if end != start:
            self._send(QEvent.Type.MouseMove, *end, none, button)
        self._send(QEvent.Type.MouseButtonRelease, *end, button, none)
        self.tab._save_settings_now()

    def node_pixel(self, nx, ny):
        point = self.editor._node_to_pixel(nx, ny)
        return point.x(), point.y()

    def boundary_pixel(self, frac):
        rect = self.editor._plot_rect()
        return self.editor._lane_anchor_x(frac), rect.bottom() + 10.0

    # capabilities --------------------------------------------------------------------------
    def add_node(self, nx, ny):
        self.drag(self.node_pixel(nx, ny), self.node_pixel(nx, ny))

    def remove_node(self, index):
        x, y = self.node_pixel(*self.editor.get_nodes()[index])
        self.drag((x, y), (x, y), Qt.MouseButton.RightButton)

    def move_node(self, index, nx, ny):
        self.drag(self.node_pixel(*self.editor.get_nodes()[index]), self.node_pixel(nx, ny))

    def move_boundary(self, index, frac):
        self.drag(self.boundary_pixel(self.editor.get_notch_positions()[index][0]), self.boundary_pixel(frac))

    def lane_strength(self, index, level):
        frac = self.editor.get_notch_positions()[index][0]
        top, bottom = self.editor._arrow_bounds()
        point = (self.editor._lane_anchor_x(frac), bottom - level * (bottom - top))
        self.drag(point, point)

    def toggle_mirrored(self):
        self.tab.spectrum_mirrored.setChecked(not self.tab.spectrum_mirrored.isChecked())
        self.tab._save_settings_now()


# ------------------------------------------------------------------------------- the Studio's own edits
class StudioShaper:
    """Reaches target shape values with only the Studio shell's edits (bridge calls the QML makes)."""

    def __init__(self, controller):
        self.c = controller
        self.bridge = controller.bridge

    @property
    def values(self):
        return self.c.session.values

    def _enabled(self, action_id) -> bool:
        rows = [row for group in self.bridge.inspector for row in group["rows"]]
        actions = [a for row in rows for a in row["actions"]]
        actions += [a for group in self.bridge.inspector for a in group.get("actions", [])]
        return any(a["id"] == action_id and a["enabled"] for a in actions)

    def _set_axis(self, prop_of, current, target):
        """Commit one axis of a sorted list so each element stops at its neighbours: leftward moves left to right,
        rightward moves right to left, repeated until settled."""
        for _ in range(len(target) + 1):
            for order in (range(len(target)), reversed(range(len(target)))):
                for index in order:
                    if current()[index] != target[index]:
                        self.bridge.commitValue(prop_of(index), 0, target[index])
            if current() == target:
                return

    def reach(self, target: dict) -> None:
        if self.values[MIRRORED] != target[MIRRORED]:
            self.bridge.commitValue(MIRRORED, 0, target[MIRRORED])
        self.bridge.setWorkspace("shape")
        # Node count: Add Node / the rows' Remove Node (the shell enables each only when admissible).
        nodes = target[SHAPE_NODES]
        while len(self.values[SHAPE_NODES]) < len(nodes) and self._enabled(ADD_NODE):
            self.bridge.runAction(ADD_NODE)
        while len(self.values[SHAPE_NODES]) > len(nodes):
            action = f"{REMOVE_NODE}{len(self.values[SHAPE_NODES]) - 1}"
            if not self._enabled(action):
                break
            self.bridge.runAction(action)
        if len(self.values[SHAPE_NODES]) == len(nodes):
            self._set_axis(lambda i: f"{SHAPE_NODES}.{i}.0", lambda: [n[0] for n in self.values[SHAPE_NODES]],
                           [n[0] for n in nodes])
            for index, (_x, y) in enumerate(nodes):
                if self.values[SHAPE_NODES][index][1] != y:
                    self.bridge.commitValue(f"{SHAPE_NODES}.{index}.1", 0, y)
        # Boundaries of both layouts: lane order by neighbour swaps, then positions. Lane strengths.
        for mirrored in (True, False):
            key, flag = NOTCHES[mirrored], "1" if mirrored else "0"
            if self.values[MIRRORED] != mirrored:
                self.bridge.commitValue(MIRRORED, 0, mirrored)        # the layout's rows show while it is active
            labels = [label for _x, label in target[key]]
            for _ in range(len(labels) ** 2):
                current = [label for _x, label in self.values[key]]
                wrong = next((i for i, label in enumerate(current) if label != labels[i]), None)
                if wrong is None:
                    break
                source = current.index(labels[wrong])
                self.bridge.runAction(f"{LANE_PREVIOUS}{flag}.{source}")
            self._set_axis(lambda i: f"{key}.{i}", lambda: [x for x, _l in self.values[key]],
                           [x for x, _l in target[key]])
            lanes = "spectrum_lane_strengths_" + ("mirrored" if mirrored else "linear")
            for lane, strength in target[lanes].items():
                if self.values[lanes][lane] != strength:
                    self.bridge.commitValue(f"{lanes}.{lane}", 0, strength)
        if self.values[MIRRORED] != target[MIRRORED]:
            self.bridge.commitValue(MIRRORED, 0, target[MIRRORED])


def _studio_reaches(dialog_tab, settings_manager, target, adapter=None) -> dict:
    from ui.studio.settings_link import open_mode_studio
    _dialog, tab = dialog_tab()                       # fresh: the stored values are the canonical start again
    keys = tuple(sorted(target))
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=adapter or LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump(2)
    StudioShaper(controller).reach(target)
    controller.close()
    return _stored(settings_manager, keys)


def _settings_result(dialog_tab, settings_manager, gestures, with_start=False):
    _dialog, tab = dialog_tab()
    tab._save_settings_now()
    start = _stored(settings_manager, _shape_keys(tab))
    shaper = SettingsShaper(tab)
    for gesture in gestures:
        gesture(shaper)
    result = _stored(settings_manager, _shape_keys(tab))
    assert result != start, "the Settings gesture changed nothing"
    return (start, result) if with_start else result


def _lanes(values, mirrored):
    return [label for _x, label in values[NOTCHES[mirrored]]]


# Every capability of Settings' shape editor, as gestures on the real widget.
CAPABILITIES = {
    "add a node": [lambda s: s.add_node(0.5, 0.9)],
    "add nodes up to the maximum": [lambda s: s.add_node(0.2, 0.9), lambda s: s.add_node(0.85, 0.15),
                                    lambda s: s.add_node(0.5, 0.95)],
    "remove a node": [lambda s: s.remove_node(1)],
    "remove nodes down to the minimum": [lambda s: s.remove_node(0), lambda s: s.remove_node(0),
                                         lambda s: s.remove_node(0), lambda s: s.remove_node(0)],
    "drag a node": [lambda s: s.move_node(1, 0.42, 0.2)],
    "drag a node past its neighbour": [lambda s: s.move_node(1, 0.8, 0.95)],
    "drag a boundary": [lambda s: s.move_boundary(1, 0.2)],
    "drag a boundary past its neighbours (reorder lanes)": [lambda s: s.move_boundary(0, 0.8)],
    "drag a lane strength": [lambda s: s.lane_strength(2, 0.25)],
    "toggle the mirrored layout and edit the linear one": [lambda s: s.toggle_mirrored(),
                                                          lambda s: s.move_boundary(3, 0.1),
                                                          lambda s: s.lane_strength(0, 0.9)],
}


def test_every_key_settings_shape_builder_collects_is_a_studio_key(qt_app, dialog_tab):
    _dialog, tab = dialog_tab()
    assert set(_shape_keys(tab)) <= build_schema().keys


# What each Settings gesture must have done (so the parity below is about the named capability).
EXPECT = {
    "add a node": lambda a, b: len(b[SHAPE_NODES]) == len(a[SHAPE_NODES]) + 1,
    "add nodes up to the maximum": lambda a, b: len(b[SHAPE_NODES]) == _max_nodes(),
    "remove a node": lambda a, b: len(b[SHAPE_NODES]) == len(a[SHAPE_NODES]) - 1,
    "remove nodes down to the minimum": lambda a, b: len(b[SHAPE_NODES]) == _min_nodes(),
    "drag a node": lambda a, b: len(b[SHAPE_NODES]) == len(a[SHAPE_NODES]) and b[SHAPE_NODES] != a[SHAPE_NODES],
    "drag a node past its neighbour": lambda a, b: b[SHAPE_NODES][-2][1] == pytest.approx(0.95, abs=0.02),
    "drag a boundary": lambda a, b: _lanes(a, True) == _lanes(b, True) and b != a,
    "drag a boundary past its neighbours (reorder lanes)": lambda a, b: _lanes(a, True) != _lanes(b, True),
    "drag a lane strength": lambda a, b: b["spectrum_lane_strengths_mirrored"] != a["spectrum_lane_strengths_mirrored"],
    "toggle the mirrored layout and edit the linear one": lambda a, b: (
        b[MIRRORED] != a[MIRRORED] and b["spectrum_lane_strengths_linear"] != a["spectrum_lane_strengths_linear"]),
}


def _max_nodes():
    from ui.tabs.media.spectrum_shape_editor import _MAX_NODES
    return _MAX_NODES


def _min_nodes():
    from ui.tabs.media.spectrum_shape_editor import _MIN_NODES
    return _MIN_NODES


@pytest.mark.parametrize("capability", sorted(CAPABILITIES))
def test_the_studio_reaches_what_each_settings_shape_capability_saves(qt_app, dialog_tab, settings_manager,
                                                                      no_gl_checks, capability):
    assert set(EXPECT) == set(CAPABILITIES)
    start, target = _settings_result(dialog_tab, settings_manager, CAPABILITIES[capability], with_start=True)
    assert EXPECT[capability](start, target), (capability, start, target)
    assert _studio_reaches(dialog_tab, settings_manager, target) == target


def test_the_studio_reaches_a_mixed_settings_session(qt_app, dialog_tab, settings_manager, no_gl_checks):
    rng = random.Random(1105)
    ops = []
    for _ in range(14):
        kind = rng.choice(("add", "remove", "node", "boundary", "lane", "mirror"))
        a, b = rng.random(), rng.random()
        if kind == "add":
            ops.append(lambda s, a=a, b=b: s.add_node(a, 0.6 + 0.4 * b)
                       if len(s.editor.get_nodes()) < 5 else s.move_node(0, a, b))
        elif kind == "remove":
            ops.append(lambda s, a=a: s.remove_node(int(a * len(s.editor.get_nodes()))))
        elif kind == "node":
            ops.append(lambda s, a=a, b=b: s.move_node(int(a * len(s.editor.get_nodes())), b, a))
        elif kind == "boundary":
            ops.append(lambda s, a=a, b=b: s.move_boundary(int(a * len(s.editor.get_notch_positions())), b))
        elif kind == "lane":
            ops.append(lambda s, a=a, b=b: s.lane_strength(int(a * len(s.editor.get_notch_positions())), b))
        else:
            ops.append(lambda s: s.toggle_mirrored())
    target = _settings_result(dialog_tab, settings_manager, ops)
    assert _studio_reaches(dialog_tab, settings_manager, target) == target


class NoStructureAdapter(LightAdapter):
    def structure_edit(self, action_id, values):
        return None


def test_without_structural_edits_the_studio_cannot_reach_a_node_change_negative_control(
        qt_app, dialog_tab, settings_manager, no_gl_checks):
    for capability in ("add a node", "remove a node", "drag a boundary past its neighbours (reorder lanes)"):
        target = _settings_result(dialog_tab, settings_manager, CAPABILITIES[capability])
        reached = _studio_reaches(dialog_tab, settings_manager, target, adapter=NoStructureAdapter())
        assert reached != target, capability


def test_structural_edits_are_single_undoable_admitted_edits(qt_app, dialog_tab, settings_manager, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    from ui.tabs.media.spectrum_shape_editor import _MAX_NODES, _MIN_NODES
    _dialog, tab = dialog_tab()
    surfaces = []
    controller = open_mode_studio(tab, MODE, adapter=LightAdapter(), surface_factory=_surfaces(surfaces))
    surfaces[0].pump(2)
    session, bridge = controller.session, controller.bridge
    start = [list(n) for n in session.values[SHAPE_NODES]]
    commits = session.commit_count
    bridge.runAction(ADD_NODE)
    assert len(session.values[SHAPE_NODES]) == len(start) + 1 and session.commit_count == commits + 1
    assert session.undo_label and settings_manager.get("widgets")["spotify_visualizer"][SHAPE_NODES] == \
        session.values[SHAPE_NODES]
    bridge.undo()
    assert session.values[SHAPE_NODES] == start
    while len(session.values[SHAPE_NODES]) < _MAX_NODES:
        bridge.runAction(ADD_NODE)
    xs = [x for x, _y in session.values[SHAPE_NODES]]
    assert xs == sorted(xs)
    commits = session.commit_count
    bridge.runAction(ADD_NODE)                                       # at the maximum: refused, nothing saved
    assert len(session.values[SHAPE_NODES]) == _MAX_NODES and session.commit_count == commits
    while len(session.values[SHAPE_NODES]) > _MIN_NODES:
        bridge.runAction(f"{REMOVE_NODE}0")
    bridge.runAction(f"{REMOVE_NODE}0")                              # at the minimum: refused
    assert len(session.values[SHAPE_NODES]) == _MIN_NODES
    # A lane swap keeps the boundaries and the lane set, and the boundary row follows its lane.
    key = NOTCHES[bool(session.values[MIRRORED])]
    before = [list(n) for n in session.values[key]]
    bridge.setWorkspace("shape")
    bridge.runAction(f"{LANE_NEXT}{'1' if session.values[MIRRORED] else '0'}.0")
    after = session.values[key]
    assert [x for x, _l in after] == [x for x, _l in before]
    assert (after[0][1], after[1][1]) == (before[1][1], before[0][1])
    row = next(r for g in bridge.inspector for r in g["rows"] if r["id"] == f"{key}.0")
    assert row["label"].startswith(after[0][1])
    controller.close()
