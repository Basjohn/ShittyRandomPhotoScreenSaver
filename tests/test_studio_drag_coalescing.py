"""Studio drags are batched: one preview per rendered frame, one commit on release (every drag instrument).

A drag hands its newest value to the bridge; the controller applies it at the next frame start, latest wins, so
however many mouse moves arrive between two frames the session previews once. Each applied preview re-shows only
the dragged property (the value map notifies per key; ``valuesChanged`` is not emitted during the gesture). The
release commits once (one save, one undo entry); Escape restores; keyboard steps still commit per step. An
engine-owned key of an engine-answer Studio starts no analysis during the drag and one on release. Each check has a
negative control that drives the old per-move path and fails it. Real mouse events reach the real shell through the
hidden ``OffscreenStudioSurface``; nothing shows a window.
"""
from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent


class _Store:
    def __init__(self, mode):
        from core.settings.visualizer_mode_settings import mode_settings
        from core.settings.visualizer_presets import resolve_visualizer_activation_payload
        self.values = dict(resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": 0},
                                                                 mode=mode).resolved_config)
        spec = mode_settings(mode)
        if mode != "waveform_ribbon" and spec is not None:
            self.values.update({c.key: c.admit(self.values[c.key], self.values[c.key])
                                for c in spec.controls if c.key in self.values})
        self.commits = 0

    def snapshot(self):
        return dict(self.values)

    def commit(self, values, changed):
        self.commits += 1
        self.values.update(values)
        return dict(self.values)

    def preset_label(self):
        return "Preset"


class _Presence:
    concealed = False

    def conceal(self):
        pass

    def reveal(self):
        pass


def _named(root, name):
    found, stack = [], [root]
    while stack:
        item = stack.pop()
        if item.objectName() == name:
            found.append(item)
        stack.extend(item.childItems())
    return found


def _visible(item) -> bool:
    while item is not None:
        if not item.isVisible():
            return False
        item = item.parentItem()
    return True


@pytest.fixture
def studio(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.studio.controller import StudioController
    from ui.studio.registry import create_adapter
    from ui.studio.surface import OffscreenStudioSurface
    disable_per_call_gl_error_checking()
    opened = []

    def open_mode(mode):
        adapter = create_adapter(mode)
        adapter.recorded_clips = lambda: ()
        surfaces = []

        def factory(controller):
            surfaces.append(OffscreenStudioSurface(controller, size=(1600, 900), present_on_show=False))
            return surfaces[0]
        store = _Store(mode)
        controller = StudioController(adapter, store, _Presence(), factory)
        assert controller.open()
        opened.append(controller)
        surface = surfaces[0]
        evaluator = controller.evaluator
        for _ in range(3000):
            surface.pump()
            if controller.bridge.viewportStatus != "preparing" and not getattr(evaluator, "analysing", False) \
                    and not getattr(evaluator, "converging", False):
                break
            time.sleep(0.005)
        assert controller.bridge.viewportStatus == "live", controller.bridge.viewportError
        return controller, surface, store
    yield open_mode
    for controller in opened:
        controller.close()


class _Mouse:
    """Real mouse events on one slider of the hidden window (timestamps advance like a real pointer's)."""

    def __init__(self, surface, slider):
        self.window = surface.window
        self.slider = slider
        self.clock = 1000

    def _send(self, kind, fraction):
        pos = self.slider.mapToScene(QPointF(self.slider.width() * fraction, self.slider.height() / 2.0))
        button = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else Qt.MouseButton.LeftButton
        buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
        event = QMouseEvent(kind, pos, pos, pos, button, buttons, Qt.KeyboardModifier.NoModifier)
        self.clock += 4
        event.setTimestamp(self.clock)
        QCoreApplication.sendEvent(self.window, event)

    def press(self, fraction):
        self._send(QEvent.Type.MouseButtonPress, fraction)

    def move(self, fraction):
        self._send(QEvent.Type.MouseMove, fraction)

    def release(self, fraction):
        self._send(QEvent.Type.MouseButtonRelease, fraction)


def _slider(controller, surface, key=None):
    if key is not None:
        controller.bridge.revealProperty(key, 0)
        surface.pump(3)
    sliders = [s for s in _named(surface.host.root, "valueSlider")
               if _visible(s) and (key is None or s.property("propId") == key)
               and 0 <= s.mapToScene(QPointF(0, 0)).y() <= 870]          # inside the hidden window
    assert sliders, key
    return min(sliders, key=lambda s: (s.mapToScene(QPointF(0, 0)).y(), s.mapToScene(QPointF(0, 0)).x()))


class _Counter:
    def __init__(self, session):
        self.previews = 0
        original = session.preview

        def counting(*args, **kwargs):
            self.previews += 1
            return original(*args, **kwargs)
        session.preview = counting


def _readout(slider):
    """The NumberField beside a slider (its row sibling with a ``display``)."""
    for sibling in slider.parentItem().childItems():
        if sibling is not slider and sibling.property("display") is not None and sibling.property("propId") is not None:
            return sibling
    raise AssertionError("no readout beside the slider")


def _drag_one_frame(controller, surface, moves, *, per_move_flush=False):
    """Press, ``moves`` moves before a frame, then the frame: how many previews the session applied."""
    slider = _slider(controller, surface)
    counter = _Counter(controller.session)
    mouse = _Mouse(surface, slider)
    mouse.press(0.3)
    for index in range(moves):
        mouse.move(0.3 + 0.4 * (index + 1) / moves)
        if per_move_flush:
            controller.bridge.apply_pending_previews()      # the old per-move path
    surface.pump()
    return counter.previews, slider, mouse


def test_many_moves_within_one_frame_apply_one_preview(studio):
    controller, surface, _store = studio("waveform_ribbon")
    previews, slider, mouse = _drag_one_frame(controller, surface, 12)
    assert previews == 1
    # The slider and its readout already show the newest position (the scene follows at the frame).
    assert slider.property("dragging")
    shown = slider.property("dragValue")
    assert _readout(slider).property("display") == f"{shown:.2f}"
    mouse.release(0.7)


def test_per_move_previews_fail_the_one_per_frame_check_negative_control(studio):
    controller, surface, _store = studio("waveform_ribbon")
    previews, _slider_item, mouse = _drag_one_frame(controller, surface, 12, per_move_flush=True)
    assert previews != 1 and previews >= 12
    mouse.release(0.7)


def _drag_and_release(controller, surface, store, frames=6, moves=4, *, per_move_commit=False):
    slider = _slider(controller, surface)
    key = slider.property("propId")
    session = controller.session
    undo_before, commits_before = len(session._undo), store.commits
    emitted = []
    controller.bridge.valuesChanged.connect(lambda: emitted.append(1))
    notified = []
    shown = controller.bridge.values
    insert = shown.insert

    def recording_insert(name, value):            # each insert notifies that key's bindings only
        notified.append(name)
        return insert(name, value)
    shown.insert = recording_insert
    mouse = _Mouse(surface, slider)
    mouse.press(0.3)
    total = frames * moves
    for index in range(total):
        fraction = 0.3 + 0.4 * (index + 1) / total
        mouse.move(fraction)
        if per_move_commit:
            controller.bridge.commitValue(key, 0, slider.property("dragValue"))    # a save per move
        if (index + 1) % moves == 0:
            surface.pump()
    during = (len(emitted), set(notified))
    mouse.release(0.7)
    surface.pump(2)
    return key, len(session._undo) - undo_before, store.commits - commits_before, during


def test_release_commits_once_with_one_undo_entry(studio):
    controller, surface, store = studio("waveform_ribbon")
    key, undo_entries, commits, (values_changed, notified) = _drag_and_release(controller, surface, store)
    assert (undo_entries, commits) == (1, 1)
    # During the gesture only the dragged property re-showed; nothing re-bound the whole inspector.
    assert values_changed == 0
    assert notified == {key}
    assert controller.session.undo_label


def test_a_save_per_move_fails_the_single_commit_check_negative_control(studio):
    controller, surface, store = studio("waveform_ribbon")
    _key, undo_entries, commits, (values_changed, _notified) = _drag_and_release(controller, surface, store,
                                                                                 per_move_commit=True)
    assert undo_entries > 1 and commits > 1 and values_changed > 0


def test_escape_restores_and_a_held_value_is_never_applied_after_cancel(studio):
    controller, surface, store = studio("waveform_ribbon")
    slider = _slider(controller, surface)
    key = slider.property("propId")
    before = controller.bridge.values[key]
    mouse = _Mouse(surface, slider)
    mouse.press(0.2)
    surface.pump()
    mouse.move(0.9)                   # held for the next frame
    slider.forceActiveFocus()
    QCoreApplication.sendEvent(surface.window, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                                                         Qt.KeyboardModifier.NoModifier))
    surface.pump(2)
    assert not controller.session.gesture_active
    assert controller.bridge.values[key] == before
    assert store.commits == 0
    mouse.release(0.9)
    surface.pump()
    assert store.commits == 0


def test_a_held_value_kept_after_cancel_would_resume_the_edit_negative_control(studio):
    controller, surface, _store = studio("waveform_ribbon")
    slider = _slider(controller, surface)
    key = slider.property("propId")
    before = controller.bridge.values[key]
    bridge = controller.bridge
    bridge.drop_pending_previews = lambda: None          # the cancel forgets to drop the held value
    bridge.beginEdit(key, "Drag")
    bridge.previewValue(key, 0, float(slider.property("to")))
    bridge.cancelEdit()
    surface.pump()
    assert controller.session.gesture_active and controller.bridge.values[key] != before


def test_keyboard_steps_still_commit_per_step(studio):
    controller, surface, store = studio("waveform_ribbon")
    slider = _slider(controller, surface)
    slider.forceActiveFocus()
    for _ in range(2):
        QCoreApplication.sendEvent(surface.window, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right,
                                                             Qt.KeyboardModifier.NoModifier))
        surface.pump()
    assert store.commits == 2 and len(controller.session._undo) == 2


@pytest.mark.parametrize("kind", ["value", "colour", "gradient"])
def test_every_drag_instrument_slot_is_coalesced(studio, kind):
    """Lifecycle grips, curve and XY handles call previewValue; pickers previewColour; gradient nodes
    previewGradient. N calls between two frames apply one preview, the newest."""
    import json
    from ui.studio.schema import COLOUR, GRADIENT, SCALAR
    from ui.studio.session import read_path
    controller, surface, _store = studio("waveform_ribbon")
    bridge = controller.bridge
    instrument = {"value": SCALAR, "colour": COLOUR, "gradient": GRADIENT}[kind]
    values = dict(controller.session.values)
    prop = next(p for p in controller.session.schema.properties if p.instrument == instrument
                and p.id in bridge.values and not p.view_pose)
    counter = _Counter(controller.session)
    bridge.beginEdit(prop.id, prop.label)
    payloads = []
    for step in range(8):
        if kind == "value":
            payloads.append(prop.minimum + (prop.maximum - prop.minimum) * (step + 1) / 9.0)
            bridge.previewValue(prop.id, 0, payloads[-1])
        elif kind == "colour":
            payloads.append("#%02x%02x%02x" % (20 * step, 100, 200))
            bridge.previewColour(prop.id, payloads[-1])
        else:
            nodes = bridge.values[prop.id]
            shifted = [{"pos": min(1.0, max(0.0, float(n["pos"]) + 0.01 * step * (i > 0))), "hex": n["hex"], "from": i}
                       for i, n in enumerate(nodes)]
            payloads.append(json.dumps(shifted))
            bridge.previewGradient(prop.id, payloads[-1])
    assert counter.previews == 0                       # nothing applied between frames
    surface.pump()
    assert counter.previews == 1
    shown = bridge.values[prop.id]
    if kind == "value":
        assert shown == pytest.approx(float(controller.session.values[prop.path[0]] if len(prop.path) == 1
                                            else read_path(controller.session.values, prop.path)))
        assert shown == pytest.approx(min(prop.maximum, payloads[-1]), abs=1.0 if prop.integer else 1e-6)
    elif kind == "colour":
        assert shown.lower() == payloads[-1]
    bridge.endEdit()
    assert controller.session.undo_label and not controller.session.gesture_active
    assert controller.session.values[prop.path[0]] != values[prop.path[0]]


def _engine_owned_drag(controller, surface, *, exact_during_drag=False):
    evaluator = controller.evaluator
    prop = next(p for p in controller.session.schema.properties
                if p.path[0] in controller.release_only_keys and p.instrument == "scalar" and len(p.path) == 1)
    started = []
    original = evaluator._analyse

    def counting(values, wanted):
        if evaluator._job_key != wanted and wanted not in evaluator.errors:
            started.append(wanted)
        return original(values, wanted)
    evaluator._analyse = counting
    if exact_during_drag:
        original_evaluate = evaluator.evaluate
        evaluator.evaluate = lambda t, v, *, exact=True, revision=None: original_evaluate(t, v, exact=True,
                                                                                            revision=revision)
    bridge = controller.bridge
    bridge.beginEdit(prop.id, prop.label)
    for step in range(10):
        bridge.previewValue(prop.id, 0, prop.minimum + (prop.maximum - prop.minimum) * (step + 1) / 11.0)
        if step % 2:
            surface.pump()
    during = len(started)
    bridge.endEdit()
    surface.pump(2)
    return prop, during, len(started) - during


def test_an_engine_owned_key_analyses_once_on_release(studio):
    controller, surface, _store = studio("spectrum")
    assert controller.release_only_keys
    prop, during, after = _engine_owned_drag(controller, surface)
    assert (during, after) == (0, 1)
    assert controller.bridge._row(prop)["releaseOnly"] is True    # its slider says so while dragged
    mode_owned = next(p for p in controller.session.schema.properties if p.path[0] not in controller.release_only_keys)
    assert controller.bridge._row(mode_owned)["releaseOnly"] is False


def test_an_exact_evaluation_per_frame_starts_the_worker_mid_drag_negative_control(studio):
    controller, surface, _store = studio("spectrum")
    _prop, during, _after = _engine_owned_drag(controller, surface, exact_during_drag=True)
    assert during >= 1
