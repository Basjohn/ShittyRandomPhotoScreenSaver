"""No Studio drag writes anything while it moves; its release commits once (1B.3, operator 11 Nov: "check any studio
sliders for churn, if any of them make I/O saves every movement of the slider").

Every registered Studio is opened from its real Settings body (a never-shown ``VisualizersTab`` over a real
``SettingsManager`` on a temporary profile, on Custom so a commit saves) through Settings' own open path, on the hidden
offscreen surface. Every drag-capable property the schema exposes (sliders, Quiet/Peak lanes and lifecycle grips, the
response tuner's gain/curve cells, XY handles, view-pose sliders, colour pickers, gradient nodes) is dragged through the
bridge slots the shell's drag instruments call, with a frame between moves; so are the camera (orbit, pan, wheel zoom),
the transport scrub and, where the mode has one, the terrain brush and its tool sliders.

During the moves nothing may reach the settings store (its state revision, any ``SettingsManager`` mutation, a save
or a flush), the tab's save, a file opened for writing or replaced (settings JSON, preset files, sidecars), an INFO+
log line, or an engine re-analysis. The release commits exactly when the value changed: one session commit and one tab
save. The property list is derived from the registry and schemas; no preset value or UI wording is read. A negative
control drives a save per move and the counters see it.
"""
from __future__ import annotations

import builtins
import io
import json
import logging
import os

import pytest

from ui.studio.registry import studio_modes

MODES = sorted(entry.mode_id for entry in studio_modes())
_MANAGER_WRITES = ("set", "set_many", "set_section", "set_widgets_map", "save", "flush", "remove",
                   "replace_visualizer_runtime_preset_state")


class _QuietRenderer:
    def prepare(self, card, frame):
        return True

    def render(self, card, frame):
        pass

    def release(self):
        pass


class _NoJob:
    def cancel(self):
        pass


def _adapter(mode: str, jobs: list):
    """The registered adapter without recorded clips or GL drawing; an engine-answer mode's worker is a counted
    stand-in (each start is one re-analysis)."""
    from ui.studio.engine_answers import EngineAnswerEvaluator
    from ui.studio.registry import create_adapter
    adapter = create_adapter(mode)
    adapter.recorded_clips = lambda: ()
    adapter.create_renderer = _QuietRenderer
    probe = adapter.create_evaluator()
    probe.release()
    if isinstance(probe, EngineAnswerEvaluator):
        def loader(*args):
            jobs.append(args)
            return _NoJob()
        adapter.create_evaluator = lambda: type(probe)(loader=loader)
    return adapter


class _IO:
    """Counts every write-shaped call while armed: settings mutations, saves, flushes, file writes, INFO+ logs."""

    def __init__(self, monkeypatch, manager, tab, jobs):
        self.manager, self.jobs = manager, jobs
        self.armed = False
        self.counts: dict[str, int] = {}
        for name in _MANAGER_WRITES:
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
        io_counter = self

        class _Logs(logging.Handler):
            def emit(self, record):
                if record.levelno >= logging.INFO:
                    io_counter._note(f"log.{record.name}: {str(record.msg)[:48]}")
        self._handler = _Logs(level=logging.DEBUG)
        root = logging.getLogger()
        self._root_level = root.level
        root.addHandler(self._handler)
        root.setLevel(logging.DEBUG)

    def close(self):
        root = logging.getLogger()
        root.removeHandler(self._handler)
        root.setLevel(self._root_level)

    def _note(self, name):
        if self.armed:
            self.counts[name] = self.counts.get(name, 0) + 1

    def _wrap(self, name, original):
        def wrapper(*args, **kwargs):
            self._note(name)
            return original(*args, **kwargs)
        return wrapper

    def measure(self, action):
        """Counts during ``action`` (store revision and engine analyses included)."""
        revision = self.manager.persistence_snapshot()["state_revision"]
        jobs = len(self.jobs)
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
def settings_manager(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    manager = SettingsManager(organization="SRPSSFocusedTests", application="StudioDragIOChurn",
                              storage_base_dir=tmp_path / "profile")
    yield manager
    assert manager.flush(timeout=5.)


@pytest.fixture
def opened(qt_app, settings_manager, monkeypatch):
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.studio.controller import StudioController
    from ui.studio.settings_link import open_mode_studio
    from ui.studio.surface import OffscreenStudioSurface
    from ui.tabs.visualizers_tab import VisualizersTab
    disable_per_call_gl_error_checking()
    made = []

    def build(mode):
        settings_manager.set("widgets", {"spotify_visualizer": {
            "enabled": True, "visualizers_enabled": True, "mode": mode,
            "mode_activation": build_visualizer_mode_activation([mode]),
            f"preset_{mode}": get_custom_preset_index(mode)}})
        dialog = QDialog()                                     # never shown
        QVBoxLayout(dialog).addWidget(tab := VisualizersTab(settings_manager))
        tab._select_mode_page(mode)
        jobs: list = []
        surfaces = []

        def factory(controller):
            surfaces.append(OffscreenStudioSurface(controller, size=(1280, 760), present_on_show=False))
            return surfaces[-1]
        controller = open_mode_studio(tab, mode, adapter=_adapter(mode, jobs), surface_factory=factory)
        surface = surfaces[0]
        surface.pump(3)
        assert controller.state == "presented"
        counter = _IO(monkeypatch, settings_manager, tab, jobs)
        made.append((dialog, controller, counter))
        return controller, surface, counter
    yield build
    for dialog, controller, counter in made:
        counter.close()
        if StudioController.active() is controller:
            controller.close()
        dialog.deleteLater()
    qt_app.processEvents()


# ------------------------------------------------------------------------------------------------ drag plans
def _drags(controller):
    """(name, begin, moves, release, changed) for every drag-capable property of the schema: each ``moves`` item is one
    pointer move (a frame follows it); ``changed`` says whether the release holds another value than before."""
    from ui.studio.schema import COLOUR, GRADIENT, QUIET_PEAK, SCALAR
    from ui.studio.session import read_path
    bridge, session = controller.bridge, controller.session
    plans = []
    for prop in session.schema.properties:
        try:
            current = read_path(controller.evaluation_values(), prop.path)
        except (KeyError, IndexError, TypeError):
            continue                                  # an unused optional element (hidden; nothing to drag)
        if prop.instrument in (SCALAR, QUIET_PEAK):
            for endpoint in ((0, 1) if prop.instrument == QUIET_PEAK else (0,)):
                start = float(current[endpoint] if prop.instrument == QUIET_PEAK else current)
                end = prop.minimum if start - prop.minimum > prop.maximum - start else prop.maximum
                steps = [start + (end - start) * k / 4.0 for k in (1, 2, 3, 4)]
                plans.append((f"{prop.id}[{endpoint}]", prop,
                              lambda p=prop: bridge.beginEdit(p.id, p.label),
                              [lambda p=prop, e=endpoint, v=v: bridge.previewValue(p.id, e, v) for v in steps],
                              bridge.endEdit))
        elif prop.instrument == COLOUR:
            hexes = ["#%02x%02x%02x" % (40 * k, 200 - 30 * k, 90 + 20 * k) for k in (1, 2, 3, 4)]
            plans.append((prop.id, prop, lambda: None,
                          [lambda p=prop, h=h: bridge.previewColour(p.id, h) for h in hexes], bridge.endEdit))
        elif prop.instrument == GRADIENT:
            nodes = bridge.values[prop.id]
            payloads = []
            for k in (1, 2, 3, 4):
                payloads.append(json.dumps([{"pos": float(n["pos"]) if i in (0, len(nodes) - 1)
                                             else min(1.0, max(0.0, float(n["pos"]) + 0.02 * k)),
                                             "hex": n["hex"], "from": i} for i, n in enumerate(nodes)]))
            last = payloads[-1]
            plans.append((prop.id, prop, lambda: None,
                          [lambda p=prop, n=n: bridge.previewGradient(p.id, n) for n in payloads],
                          lambda p=prop, n=last: bridge.commitGradient(p.id, n)))
    for shape in session.schema.shapes:
        plans += _shape_drags(controller, session.schema.find(shape.property))
    return plans


def _shape_drags(controller, prop):
    """The SHAPE instrument's drags (``ui/studio/shape.py``) through the slots its canvas calls: a curve node, a lane
    boundary (its tag) and a lane's strength marker, each a press, held moves and one release."""
    from ui.studio.session import read_path
    bridge, values = controller.bridge, controller.session.values
    layout = bridge.shapes.instrument(prop.id).layout(values)
    nodes = [list(node) for node in read_path(values, prop.path)]
    notches = [list(notch) for notch in read_path(values, layout.notches)]
    strengths = dict(read_path(values, layout.lanes))
    node = nodes[-1]
    rise = -0.05 if node[1] > 0.5 else 0.05
    lane = len(notches) - 1
    room = notches[lane][0] - notches[lane - 1][0]
    strength = strengths[notches[lane][1]]
    step = -0.05 if strength > 0.5 else 0.05
    gestures = (("node", len(nodes) - 1, [(node[0], node[1] + rise * k) for k in (1, 2, 3, 4)]),
                ("lane", lane, [(notches[lane][0] - room * 0.1 * k, 0.0) for k in (1, 2, 3, 4)]),
                ("strength", lane, [(0.0, strength + step * k) for k in (1, 2, 3, 4)]))
    return [(f"{prop.id}.shape.{part}", prop,
             lambda p=prop, part=part, index=index: bridge.shapePress(p.id, part, index),
             [lambda p=prop, x=x, y=y: bridge.shapeDrag(p.id, x, y) for x, y in moves],
             bridge.shapeRelease)
            for part, index, moves in gestures]


def _per_move(counts, moves: int):
    """What a drag's moves did that a drag may not: any write, store change or analysis, and log lines that keep pace
    with the moves. Event-edge lines are not per move (the sidecar's "replay after" / "preview gap" records, one per
    event: the previous change's replay landing, a slow frame; the reveal watch expiring)."""
    logs = sum(n for name, n in counts.items() if name.startswith("log."))
    churn = {name: n for name, n in counts.items() if not name.startswith("log.")}
    if logs >= moves:
        churn.update({name: n for name, n in counts.items() if name.startswith("log.")})
    return churn


def _drive(controller, surface, counter, begin, moves, release):
    before = (controller.session.commit_count, dict(controller.session.committed_values))

    def during():
        begin()
        for move in moves:
            move()
            surface.pump()
    moving = _per_move(counter.measure(during), len(moves))
    # The release's replay is logged once when it completes (one line per commit, a frame or two later).
    # The settings writer persists on its own thread: the release's file write lands within its flush.
    released = counter.measure(lambda: (release(), surface.pump(3), counter.manager.flush(timeout=5.)))
    commits = controller.session.commit_count - before[0]
    changed = controller.session.committed_values != before[1]
    return moving, released, commits, changed


@pytest.mark.parametrize("mode", MODES)
def test_no_drag_instrument_writes_while_moving_and_each_release_commits_once(opened, mode):
    controller, surface, counter = opened(mode)
    plans = _drags(controller)
    assert plans, f"{mode}: the schema exposes no drag instrument"
    names = {name for name, *_rest in plans}
    for shape in controller.session.schema.shapes:          # every registered shape: node, lane and strength drags
        assert {f"{shape.property}.shape.{part}" for part in ("node", "lane", "strength")} <= names, mode
    churn, release_faults = {}, {}
    for name, prop, begin, moves, release in plans:
        held = controller.session.committed_values[prop.path[0]]
        moving, released, commits, changed = _drive(controller, surface, counter, begin, moves, release)
        released = {**released, "value": (held, controller.session.committed_values[prop.path[0]])}
        if moving:
            churn[name] = moving
        saves = released.get("tab.save", 0)
        # At most one commit, through the tab's one save; a lasting change always committed. (A commit the canonical
        # save normalizes back, or a preview view the camera policy keeps unsaved, is allowed: whether a value holds
        # is its owner's contract, not this test's.)
        ok = commits <= 1 and saves == commits and (not changed or (commits == 1 and released.get("settings.revision")))
        if not ok:
            release_faults[name] = (commits, changed, released)
    assert churn == {}, f"{mode}: writes while dragging: {churn}"
    assert release_faults == {}, f"{mode}: release did not commit exactly once: {release_faults}"


def _camera_and_transport(controller, surface):
    """(name, begin, moves, release) of the viewport and transport drags the mode offers."""
    bridge = controller.bridge
    plans = [("transport.scrub", lambda: None,
              [lambda f=f: bridge.seek(f * max(bridge.duration, 1.0)) for f in (0.2, 0.4, 0.6, 0.8)], lambda: None)]
    if controller.navigation() is not None:
        plans += [
            ("camera.orbit", lambda: None, [lambda: bridge.orbitBy(18.0, -9.0)] * 4, bridge.endOrbit),
            ("camera.pan", lambda: None, [lambda: bridge.panBy(12.0, 7.0, 1280.0, 760.0)] * 4, bridge.endOrbit),
            ("camera.zoom", lambda: None, [lambda: bridge.zoomBy(0.5, False)] * 4, lambda: None),
            ("camera.dolly", lambda: None, [lambda: bridge.zoomBy(0.5, True)] * 4, lambda: None),
        ]
    if bridge.brush is not None:
        width, height = controller.presented_geometry()[0]
        points = [(width * (0.35 + 0.08 * k), height * 0.72) for k in range(5)]
        plans += [
            ("brush.tool_sliders", lambda: None,
             [lambda v=v: bridge.setBrushValue("radius", v) for v in (0.05, 0.08, 0.11, 0.14)], lambda: None),
            ("brush.stroke", lambda: (bridge.setBrushActive(True), bridge.brushPress(*points[0])),
             [lambda p=p: bridge.brushMove(*p) for p in points[1:]],
             lambda: (bridge.brushRelease(), bridge.setBrushActive(False))),
        ]
    return plans


@pytest.mark.parametrize("mode", MODES)
def test_camera_transport_and_brush_drags_write_nothing_while_moving(opened, mode):
    controller, surface, counter = opened(mode)
    churn, strokes = {}, {}
    for name, begin, moves, release in _camera_and_transport(controller, surface):
        moving, released, commits, changed = _drive(controller, surface, counter, begin, moves, release)
        if moving:
            churn[name] = moving
        if name == "brush.stroke":
            strokes[name] = (commits, released.get("tab.save", 0), changed)
        elif name.startswith("camera.") or name.startswith("transport."):
            assert commits <= 1 and released.get("tab.save", 0) == commits, (mode, name, released)
    assert churn == {}, f"{mode}: writes while dragging: {churn}"
    for name, (commits, saves, changed) in strokes.items():
        assert changed and (commits, saves) == (1, 1), f"{mode}: {name} should save once on release"


def _orbit_rebuilds(controller, surface, *, per_move_rebuild=False):
    """valuesChanged emissions (a whole values-map rebuild re-binds the inspector) for 12 orbit moves in one frame."""
    bridge = controller.bridge
    emitted = []
    bridge.valuesChanged.connect(lambda: emitted.append(1))
    for _ in range(12):
        bridge.orbitBy(3.0, -1.0)
        if per_move_rebuild:
            bridge.on_session_changed("pose")              # the former per-move path
    during = len(emitted)
    surface.pump()
    at_frame, readout = len(emitted) - during, bridge.viewModified
    bridge.endOrbit()
    return during, at_frame, readout


def test_an_orbit_drag_rebuilds_the_inspector_once_per_frame_not_per_move(opened):
    controller, surface, _counter = opened("shockwave_grid")
    during, at_frame, modified = _orbit_rebuilds(controller, surface)
    assert (during, at_frame) == (0, 1) and modified


def test_a_rebuild_per_orbit_move_fails_the_once_per_frame_check_negative_control(opened):
    controller, surface, _counter = opened("shockwave_grid")
    during, _at_frame, _modified = _orbit_rebuilds(controller, surface, per_move_rebuild=True)
    assert during == 12


def test_a_save_per_move_is_seen_by_the_counters_negative_control(opened):
    """The former shape of a churning slider: each move commits (one save and one settings write per move)."""
    from ui.studio.schema import SCALAR
    controller, surface, counter = opened("spectrum")
    bridge = controller.bridge
    prop = next(p for p in controller.session.schema.properties
                if p.instrument == SCALAR and len(p.path) == 1 and not p.view_pose
                and p.path[0] not in controller.release_only_keys)
    start = float(controller.session.values[prop.path[0]])
    end = prop.minimum if start - prop.minimum > prop.maximum - start else prop.maximum
    moves = [lambda v=start + (end - start) * k / 4.0: bridge.commitValue(prop.id, 0, v) for k in (1, 2, 3, 4)]
    moving, _released, _commits, _changed = _drive(controller, surface, counter, lambda: None, moves, lambda: None)
    assert moving.get("tab.save", 0) == 4 and moving.get("settings.set_widgets_map", 0) >= 4
    assert moving.get("settings.revision")


def test_a_shape_commit_per_move_is_seen_by_the_counters_negative_control(opened):
    """A churning shape instrument: each move commits (its exact entry commits per call), and the plan check sees it."""
    controller, surface, counter = opened("spectrum")
    bridge = controller.bridge
    prop_id = controller.session.schema.shapes[0].property
    from ui.studio.session import read_path
    height = read_path(controller.session.values, controller.session.schema.find(prop_id).path)[0][1]
    step = -0.05 if height > 0.5 else 0.05
    moves = [lambda k=k: bridge.shapeCommitText(prop_id, "node", 0, 1, f"{height + step * k:.3f}") for k in (1, 2, 3, 4)]
    moving, _released, _commits, _changed = _drive(controller, surface, counter, lambda: None, moves, lambda: None)
    assert moving.get("tab.save", 0) == 4 and moving.get("settings.revision")


def test_a_file_written_per_move_is_seen_by_the_counters_negative_control(opened, tmp_path):
    controller, surface, counter = opened("waveform_ribbon")
    target = tmp_path / "sidecar.json"
    moves = [lambda k=k: target.write_text(json.dumps({"k": k}), encoding="utf-8") for k in range(3)]
    moving, _released, _commits, _changed = _drive(controller, surface, counter, lambda: None, moves, lambda: None)
    assert moving.get("file.write: sidecar.json") == 3
    logger = logging.getLogger("ui.studio.controller")
    moving, *_rest = _drive(controller, surface, counter, lambda: None, [lambda: logger.info("per move")] * 2,
                            lambda: None)
    assert moving.get("log.ui.studio.controller: per move") == 2
