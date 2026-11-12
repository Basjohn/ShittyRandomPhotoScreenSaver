"""A retired shell's bridge cannot reach the session the controller holds after it (plan 1D.0, after R-200).

R-200 keeps a retiring shell's ``StudioBridge`` alive until that shell's engine is destroyed, because its bindings still
read ``studio``. Until then the shell can still call its slots (Close, Esc, a late commit, a key release on focus loss,
the window chrome). Those calls reached the controller through ``self._c`` and acted on whatever it held then: the next
mode's session after a switch. At retirement the controller cuts the old bridge off: no close request reaches it and no
slot acts. Its properties still read, so a retiring binding never sees null.
"""
from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QMetaMethod

from tests.test_waveform_studio_second_mode import Presence, ToyAdapter, ToyStore


class OtherToy(ToyAdapter):
    mode_id = "toy_other"
    title = "Other Toy"


def _switched_studio():
    from ui.studio.controller import StudioController
    from ui.studio.surface import OffscreenStudioSurface
    stores = {"toy_mode": ToyStore(), "toy_other": ToyStore()}
    surfaces: list = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(800, 500), present_on_show=False))
        return surfaces[-1]
    adapters = {"toy_mode": ToyAdapter, "toy_other": OtherToy}
    controller = StudioController(ToyAdapter(), stores["toy_mode"], Presence(), factory,
                                  mode_switcher=lambda mode: (adapters[mode](), stores[mode]),
                                  modes=lambda: (("toy_mode", "Toy"), ("toy_other", "Other Toy")))
    assert controller.open()
    surfaces[-1].pump()
    old = controller.bridge
    controller.request_mode_switch("toy_other")
    surfaces[-1].pump()
    assert controller.bridge is not old and controller.adapter.mode_id == "toy_other"
    assert controller.state == "presented"
    return controller, old, stores, surfaces


def _new_session_state(controller, stores):
    session = controller.session
    return {"mode": controller.adapter.mode_id, "state": controller.state, "active": type(controller).active(),
            "values": dict(session.values), "undo": session.undo_label, "redo": session.redo_label,
            "dirty": session.dirty, "gesture": session.gesture_active, "commits": list(stores["toy_other"].commits),
            "playing": controller.transport.playing, "time": controller.transport.time,
            "fixture": controller.evaluator.fixture.id, "pose": dict(controller._pose),
            "surface": controller.surface, "bridge": controller.bridge,
            "workspace": controller.bridge.workspace, "message": controller.bridge.message}


def test_every_kind_of_slot_on_a_retired_bridge_leaves_the_next_session_alone(qt_app):
    controller, old, stores, surfaces = _switched_studio()
    try:
        # Give the next session something an inert call could disturb: one edit to undo and one to redo.
        controller.bridge.commitValue("toy_gain", 0, 0.75)
        controller.bridge.commitValue("toy_gain", 0, 0.25)
        controller.bridge.undo()
        before = _new_session_state(controller, stores)
        assert before["undo"] and before["redo"]
        # Each kind of entry point the retiring shell still has: edits and gestures, history, presets and saves,
        # transport, camera, selection, notices, window chrome, close and mode switch.
        old.commitValue("toy_gain", 0, 1.5)
        old.commitText("toy_gain", 0, "1.25")
        old.beginEdit("toy_gain", "Gain")
        old.previewValue("toy_gain", 0, 1.9)
        old.endEdit()
        old.resetProperty("toy_gain")
        old.undo()
        old.redo()
        old.revertAll()
        old.saveCurrent()
        old.selectPreset(0)
        old.togglePlay()
        old.seek(2.0)
        old.selectFixture("pulse")
        old.orbitBy(30.0, 10.0)
        old.resetCamera()
        old.navigationKey(87, True, False)
        old.releaseNavigationKeys()
        old.setWorkspace("look")
        old.selectObject("orb")
        old.rotateContent()
        old.copyFrame()
        old.dismissMessage()
        old.toggleMaximize()
        old.requestClose()
        old.requestCloseFrom("escape")
        old.closeRequested.emit()                  # the signal itself no longer reaches the controller's close
        old.switchMode("toy_mode")
        QCoreApplication.processEvents()
        surfaces[-1].pump()
        after = _new_session_state(controller, stores)
        assert after == before
        assert not stores["toy_mode"].commits, "the retired mode's store is not written either"
        # The retired bridge still reads (its shell's bindings may re-evaluate until its engine is gone).
        assert old.detached and isinstance(old.presetLabel, str) and isinstance(old.modes, list)
    finally:
        controller.close()


def test_the_active_bridge_still_acts(qt_app):
    """Positive control: the same calls on the controller's own bridge do reach its session."""
    controller, _old, stores, surfaces = _switched_studio()
    try:
        bridge = controller.bridge
        assert not bridge.detached
        bridge.commitValue("toy_gain", 0, 1.5)
        assert stores["toy_other"].commits == [frozenset({"toy_gain"})]
        bridge.requestCloseFrom("escape")
        assert controller.state == "closed"
    finally:
        if controller.state != "closed":
            controller.close()


def test_every_bridge_slot_is_gated_at_retirement(qt_app):
    """Structure: every QML entry point of the bridge carries the retirement gate, so a new slot cannot skip it."""
    from ui.studio.controller import StudioBridge
    meta = StudioBridge.staticMetaObject
    names = {bytes(meta.method(i).name()).decode() for i in range(meta.methodOffset(), meta.methodCount())
             if meta.method(i).methodType() == QMetaMethod.MethodType.Slot}
    assert names, "the bridge declares slots"
    ungated = sorted(name for name in names if not getattr(getattr(StudioBridge, name), "studio_attached", False))
    assert ungated == [], ungated
