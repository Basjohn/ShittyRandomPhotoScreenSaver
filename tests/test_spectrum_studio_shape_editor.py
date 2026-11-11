"""The Spectrum Studio's shape structural edits (Add Node, Remove Node, lane swaps).

The Studio is the only Spectrum shape editor since 6 Nov (Settings' body is the preset row and the launcher). Before
that, this file drove every capability of Settings' own shape editor and proved the Studio reached exactly what it
saved (commit 2f44e510); what remains is the Studio's own rule: each structural edit is one undoable, admitted edit
within the node limits. The shape instrument runs these same actions (its Add Node button, right-click / Delete, its
lane swap buttons); its gestures are covered by ``tests/test_studio_shape_instrument.py``. Nothing shows a window.
"""
from __future__ import annotations

from ui.studio.spectrum_adapter import ADD_NODE, LANE_NEXT, NOTCHES, REMOVE_NODE, SHAPE_NODES
from tests.test_spectrum_studio import (  # noqa: F401  (fixtures)
    LightAdapter, _surfaces, dialog_tab, no_gl_checks, settings_manager,
)

MODE = "spectrum"
MIRRORED = "spectrum_mirrored"


def test_structural_edits_are_single_undoable_admitted_edits(qt_app, dialog_tab, settings_manager, no_gl_checks):
    from ui.studio.settings_link import open_mode_studio
    from ui.studio.spectrum_shape import MAX_NODES as _MAX_NODES, MIN_NODES as _MIN_NODES
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
    # A lane swap keeps the boundaries and the lane set, and the shape instrument's canvas follows it.
    key = NOTCHES[bool(session.values[MIRRORED])]
    before = [list(n) for n in session.values[key]]
    bridge.setWorkspace("shape")
    bridge.runAction(f"{LANE_NEXT}{'1' if session.values[MIRRORED] else '0'}.0")
    after = session.values[key]
    assert [x for x, _l in after] == [x for x, _l in before]
    assert (after[0][1], after[1][1]) == (before[1][1], before[0][1])
    assert [lane["label"] for lane in bridge.values[SHAPE_NODES]["lanes"]] == [label for _x, label in after]
    controller.close()
