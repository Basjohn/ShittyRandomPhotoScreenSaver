"""Native core P2b, work order 5 slice 5.4 (inputs and settings) and checkpoint audit 7's visible items: what the
presentation side owns reaches the frames drawn from the engine worker.

The REAL owner built by the host binding on an unshown runtime (``tools/visualizer_replay/owner_worker_gate.py``'s rig;
no window is shown, no device is opened). The view gate compares the owner on a real ``WorkerType.VISUALIZER`` process
with the same owner in process, frame for frame, with the inputs actually exercised (a reflecting photograph, a
held-key orbit, a preset's Auto Rotate); the edge tests run the same ``VisualizerEngineWorker`` in this process behind
the supervisor stand-in.
"""
from __future__ import annotations

import pytest

from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor, _pump
from tools.visualizer_replay import owner_worker_gate as gate


@pytest.fixture(autouse=True)
def _no_device_and_a_fresh_run(monkeypatch):
    from core.visualizer_engine.engine_worker import EngineSession
    from widgets.spotify_visualizer import engine_worker_link

    def _device(_config=None):
        raise AssertionError("a test opened an audio device")

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", _device)
    monkeypatch.setattr(EngineSession, "LIVE_EDGE_TIMEOUT_S", 10.0)
    engine_worker_link.reset_run_state_for_testing()
    yield
    engine_worker_link.reset_run_state_for_testing()


@pytest.fixture(scope="module")
def supervisor():
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import WorkerType
    from core.visualizer_engine.engine_worker import visualizer_worker_main

    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    assert supervisor.start(WorkerType.VISUALIZER)
    yield supervisor
    supervisor.shutdown()


@pytest.fixture(scope="module")
def pcm():
    from tools.visualizer_replay.live_engine_gate import paced_pcm

    return paced_pcm(3.0)


def _stand_in_rig(pcm, mode: str, **kwargs):
    from widgets.spotify_visualizer import engine_worker_link

    stand_in = _InProcessSupervisor()
    rig = gate.OwnerRig(mode, worker=True, supervisor=stand_in, cadence="thread", **kwargs)
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm[0], pcm_rate=pcm[1]):
            owner = rig.build()
    except BaseException:
        rig.close()
        stand_in.close()
        raise
    return stand_in, rig, owner


# --------------------------------------------------------------------------------------- the view gate (real process)


@pytest.mark.qt
@pytest.mark.parametrize("mode", gate.VIEW_MODES)
def test_the_presentation_inputs_reach_the_worker_frames_as_in_process(qt_app, supervisor, mode):
    # A7-M1 / A7-M2 / 5.4: with a reflecting photograph (Sphere, Extruded Spectrum), a held-key orbit, a preset's
    # immediate Auto Rotate and a second orbit, the owner on the worker publishes exactly the frames it publishes in
    # process. Before 5.4 the worker's capture read its own presentation state: no wallpaper, the settings' pose.
    import tools.expanded_visualizer_evidence as evidence

    script = gate.identity_script_view(evidence.shipped_clip(4.6).frames, mode)
    worker = gate.identity_run(mode, script, worker=True, supervisor=supervisor)
    in_process = gate.identity_run(mode, script, worker=False, namespace=worker["namespace"])
    a, b = worker["digests"], in_process["digests"]
    first = next((index for index, (x, y) in enumerate(zip(a, b)) if x != y), None)
    assert worker["on_worker"] and len(a) == len(b) and first is None, (len(a), len(b), first)


# ------------------------------------------------------------------------------------- edges (in-process stand-in)


@pytest.mark.qt
@pytest.mark.parametrize("completed", (True, False))
def test_the_reflected_wallpaper_completes_the_worker_frames(qt_app, pcm, monkeypatch, completed):
    # A7-M1: the wallpaper is presentation data and stays on the main side; each frame taken from the worker carries
    # the owner's own (the renderer reads it from the frame's parameters, as in process). Negative control: frames as
    # decoded carry none (the worker never has a photograph).
    from widgets.spotify_visualizer import backdrop

    if not completed:
        monkeypatch.setattr(backdrop, "complete_frame_backdrop", lambda state, _presentation: state)
    stand_in, rig, owner = _stand_in_rig(pcm, "sphere")
    try:
        if not completed:
            owner._worker.mailbox.set_frame_completion(None)
        rig.reflect()
        owner.forward_presentation_inputs()
        _pump(rig, 0.6)
        wallpaper = owner.controller.presentation_state._backdrop
        recent = rig.published[-10:]
        assert wallpaper is not None and recent
        carried = [logical.mode_state.parameters["backdrop"] for logical in recent]
        identities = [None if value is None else value["identity"] for value in carried]
        assert all(identity == wallpaper.identity for identity in identities) is completed, identities
    finally:
        rig.close()
        stand_in.close()


@pytest.mark.qt
@pytest.mark.parametrize("forwarded", (True, False))
def test_a_presentation_setting_step_reaches_the_session_without_a_rebuild(qt_app, pcm, monkeypatch, forwarded):
    # 5.4: a presentation-only setting written on the main side (Edit's turn here; Home and live tweaks write the same
    # state) reaches the session as a delta between two steps: no VIS_SET_MODE, no rebuild, the mode's runtime (its
    # state) the same object, and the frames drawn with the new value. Negative control: without the forwarded
    # inputs the session keeps the old value.
    from core.process.types import MessageType
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs, presentation_setting_range

    if not forwarded:
        send = engine_worker_link.EngineWorkerLink._send

        def without_presentation(self, message, payload, **kwargs):
            if message == MessageType.VIS_SET_VIEW:
                payload = {key: value for key, value in payload.items() if key != "presentation"}
            return send(self, message, payload, **kwargs)

        monkeypatch.setattr(engine_worker_link.EngineWorkerLink, "_send", without_presentation)
    stand_in, rig, owner = _stand_in_rig(pcm, "sphere")
    try:
        _pump(rig, 0.4)
        session = stand_in.worker._session
        runtime = session._controller.peek_logical_mode_state("sphere")
        sent_before = len(stand_in.sent)
        low, high = presentation_setting_range("sphere_turn")
        turn = low + 0.37 * (high - low)                   # inside the setting's range, not the value it holds
        assert owner.controller.presentation_state._sphere_turn != turn
        apply_presentation_vis_mode_kwargs(owner.controller.presentation_state, {"sphere_turn": turn})
        _pump(rig, 0.5)
        modes = [msg for msg, _payload in stand_in.sent[sent_before:] if msg == MessageType.VIS_SET_MODE]
        assert not modes and stand_in.worker._session is session
        assert session._controller.peek_logical_mode_state("sphere") is runtime
        reached = session._controller.presentation_state._sphere_turn == turn
        drawn = rig.published[-1].mode_state.parameters["sphere_turn"] == turn
        assert reached is forwarded and drawn is forwarded
    finally:
        rig.close()
        stand_in.close()


@pytest.mark.qt
@pytest.mark.parametrize("pre_fix", (False, True))
def test_fullscreen_edit_envelopes_on_the_worker(qt_app, pcm, monkeypatch, pre_fix):
    # A7-M2: Sphere's Fullscreen Edit envelope reads its resolved parameters (the newest frame's on the worker, where
    # the main tick state never ticks), and a switch into Extruded Spectrum leaves the main controller's bar count the
    # session's (its technical config). Negative control: the pre-fix reads (the main tick state only; the bar count
    # never updated after the first configure) give no Sphere envelope and a stale bar count.
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from rendering.quick.visualizer.edit_content_envelope import resolve_owner_edit_content_envelope
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module

    stand_in, rig, owner = _stand_in_rig(pcm, "sphere", extra_modes=("extruded_spectrum",))
    try:
        _pump(rig, 0.6)
        if pre_fix:
            committed = owner_module.QuickDisplayVisualizerOwner._on_worker_committed

            def stale(self, commit, identity, *records):
                count = self._controller.bar_count
                committed(self, commit, identity, *records)
                self._controller.bar_count = count

            monkeypatch.setattr(owner_module.QuickDisplayVisualizerOwner, "_on_worker_committed", stale)
            with monkeypatch.context() as patch:
                patch.setattr(PacketMailbox, "last_taken", property(lambda self: None))
                envelope = resolve_owner_edit_content_envelope(owner, owner._resolve_current_presentation())
        else:
            envelope = resolve_owner_edit_content_envelope(owner, owner._resolve_current_presentation())
        assert (envelope is None) is pre_fix
        before = owner.controller.bar_count
        assert owner.request_mode_change("extruded_spectrum",
                                         **gate.activation_inputs(rig.widgets, "extruded_spectrum"))
        _pump(rig, 3.0, until=lambda: owner._mode_transition_phase == "idle"
              and owner.controller.mode_id == "extruded_spectrum")
        session_count = stand_in.worker._session.bar_count
        assert session_count != before, before            # the switch changes it (else the check proves nothing)
        assert (owner.controller.bar_count == session_count) is not pre_fix
    finally:
        rig.close()
        stand_in.close()


@pytest.mark.qt
@pytest.mark.parametrize("pre_fix", (False, True))
def test_a_presets_auto_rotate_is_armed_once_by_the_session(qt_app, pcm, monkeypatch, pre_fix):
    # Checkpoint audit 8, A8-L2: a same-mode preset with Auto Rotate on. The session's commit arms it once (as the
    # in-process commit does); the main side adopts that record and sends nothing back, so the session's swivel keeps
    # the start its commit gave it. Negative control (the pre-fix main side, arming again at the reply): two immediate
    # armings, and the main side's later record replaces the session's, stepping the turn back by the reply's latency.
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module
    from widgets.spotify_visualizer import view_orbit
    from widgets.spotify_visualizer.config_applier import presentation_setting_range

    mode = "shockwave_grid"
    armed: list = []
    arm = view_orbit.arm_view_auto_rotate

    def recording(host, mode_id, now, *, immediate):
        record = arm(host, mode_id, now, immediate=immediate)
        if immediate and record is not None:
            armed.append(record)
        return record

    monkeypatch.setattr(view_orbit, "arm_view_auto_rotate", recording)
    if pre_fix:
        committed = owner_module.QuickDisplayVisualizerOwner._on_worker_committed

        def arm_again_at_the_reply(self, commit, identity, *records):
            committed(self, commit, identity, *records)
            if commit["kind"] == "preset":
                now = float(self._transition_clock())
                view_orbit.rebase_view_orbit_motion(self._controller.presentation_state, now)
                view_orbit.arm_view_auto_rotate(self._controller.presentation_state, commit["target"], now,
                                                immediate=True)

        monkeypatch.setattr(owner_module.QuickDisplayVisualizerOwner, "_on_worker_committed", arm_again_at_the_reply)
    enable, after_key, speed_key = get_visualizer_mode_descriptor(mode).view_auto_rotate_settings
    stand_in, rig, owner = _stand_in_rig(pcm, mode)
    try:
        _pump(rig, 0.4)
        inputs = gate.activation_inputs(rig.widgets, mode)
        kwargs = dict(inputs["presentation_kwargs"])
        kwargs[enable] = True                                  # Auto Rotate on for this preset (a test-owned input)
        for key in (after_key, speed_key):
            if not float(kwargs.get(key) or 0.0) > 0.0:
                low, high = presentation_setting_range(key)
                kwargs[key] = low + 0.5 * (high - low)
        inputs["presentation_kwargs"] = kwargs
        assert owner.request_preset_change(mode, **inputs)
        _pump(rig, 3.0, until=lambda: owner._mode_transition_phase == "idle" and not owner._worker.busy)
        _pump(rig, 0.3)
        session = stand_in.worker._session._controller.presentation_state._view_orbit_auto_rotate
        main = owner.controller.presentation_state._view_orbit_auto_rotate
        assert len(armed) == (2 if pre_fix else 1), armed
        assert session is not None and main == session
        assert (session == armed[0]) is not pre_fix, (session, armed)
    finally:
        rig.close()
        stand_in.close()


@pytest.mark.qt
@pytest.mark.parametrize("pre_fix", (False, True))
def test_an_in_place_edit_of_a_nested_presentation_input_is_forwarded(qt_app, monkeypatch, pre_fix):
    # Checkpoint audit 8, A8-L6: the presentation inputs are compared with the last send by value. Waveform Ribbon's
    # palette (a dict of lists) edited in place on the main side differs from what the session holds, so it is
    # forwarded, as a copy that shares nothing mutable with the state. Negative control (values held by reference, as
    # the pre-fix snapshot held the palette): the edited value compares equal to "sent" and never leaves.
    import types

    from core.process.types import WorkerResponse
    from tests.test_visualizer_owner_engine_worker_liveness import _ManualSupervisor
    from widgets.spotify_visualizer import logical_edges
    from widgets.spotify_visualizer.engine_worker_link import EngineWorkerLink

    if pre_fix:
        monkeypatch.setattr(logical_edges, "detach_presentation_value", lambda value: value)
    state = types.SimpleNamespace(_waveform_ribbon_palette={"strand": [10, 20, 30, 255], "rim": [1, 2, 3, 4]})
    supervisor = _ManualSupervisor()
    link = EngineWorkerLink(supervisor, on_lost=lambda _link, _reason: None)

    def answer() -> None:
        message, correlation = supervisor.sent[-1]
        supervisor.callbacks[correlation](WorkerResponse(msg_type=message, seq_no=0, correlation_id=correlation,
                                                         success=True))
        gate._event_loop_for(qt_app, 5.0, until=lambda: not link.busy)

    try:
        link.set_view_source(lambda: (((640.0, 360.0), {}, None, None),
                                      logical_edges.presentation_inputs_snapshot(state, "waveform_ribbon")))
        assert link.send_view()
        answer()
        state._waveform_ribbon_palette["strand"][0] = 99                     # edited in place
        forwarded = link.send_view()
        assert forwarded is not pre_fix
        if forwarded:
            palette = supervisor.payloads[-1]["presentation"]["_waveform_ribbon_palette"]
            assert palette == state._waveform_ribbon_palette
            assert palette is not state._waveform_ribbon_palette
            assert palette["strand"] is not state._waveform_ribbon_palette["strand"]
    finally:
        link.close()


def test_the_qt_free_presentation_colours_freeze_as_qcolor_did():
    # 5.4 (QtCore-only worker): the presentation config's colours are the tuples a QColor froze to in the frame
    # (``render_state.freeze_render_value``: ``getRgb()``), the border opacity included (Qt rounds it through a 16-bit
    # channel), so frames are unchanged. Every 8-bit colour channel value and 20,001 opacities.
    from PySide6.QtGui import QColor

    from widgets.spotify_visualizer.config_applier import _color_or_none, _with_alpha_f
    from widgets.spotify_visualizer.render_state import freeze_render_value

    for channel in range(256):
        for value in ([channel, 255 - channel, channel // 2], [channel, 7, 255 - channel, channel]):
            assert _color_or_none(value) == freeze_render_value(QColor(*value)), value
    for step in range(20_001):
        opacity = step / 20_000
        color = QColor(12, 200, 99, 77)
        color.setAlphaF(opacity)
        assert _with_alpha_f((12, 200, 99, 77), opacity) == freeze_render_value(color), opacity
