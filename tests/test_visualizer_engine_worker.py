"""Native core P2 work order 4: the visualizer engine worker (P2a, the tick out of process).

The identity gate: fed the same post-DSP inputs, the engine session produces, through the frame packet ABI, exactly
the frames the production owner's in-process tick produces, for every mode; in a ``WorkerType.VISUALIZER`` process
under ``ProcessSupervisor`` too, which loads no Qt Quick, QML or Widgets."""
import pytest

from core.process.supervisor import ProcessSupervisor
from core.process.types import MessageType, WorkerType
from core.visualizer_engine.engine_worker import EngineSession, visualizer_worker_main
from core.visualizer_engine.packet_mailbox import PacketMailbox


def _modes():
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


GENERATION = 9001


def _in_process_digests(evidence, clip, mode):
    return evidence.owner_replay(clip, mode, generation=GENERATION)["digests"]


@pytest.mark.qt
@pytest.mark.parametrize("mode", _modes())
def test_the_engine_session_ticks_the_owners_frames_through_the_abi(qt_app, mode):
    import tools.expanded_visualizer_evidence as evidence

    clip = evidence.shipped_clip(1.5)
    expected = _in_process_digests(evidence, clip, mode)
    reader = PacketMailbox(role="reader")
    session = EngineSession(mapping=reader.mapping_name, mode=mode, runtime_generation=GENERATION)
    try:
        seen = []
        for feature in clip.frames:
            session.tick(feature)
            seen.append(evidence.frame_digest(reader.take().state))
    finally:
        session.close()
        reader.close()
    assert len(expected) > 30 and seen == expected, mode


@pytest.mark.qt
def test_the_worker_process_ticks_identical_frames_for_every_mode(qt_app):
    import tools.expanded_visualizer_evidence as evidence

    clip = evidence.shipped_clip(1.0)
    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    assert supervisor.start(WorkerType.VISUALIZER)
    try:
        for mode in _modes():
            expected = _in_process_digests(evidence, clip, mode)
            reader = PacketMailbox(role="reader")
            try:
                configured = supervisor.send_request_and_await_response(
                    WorkerType.VISUALIZER, MessageType.VIS_CONFIGURE,
                    {"mapping": reader.mapping_name, "mode": mode, "runtime_generation": GENERATION},
                    timeout_ms=60_000)
                assert configured is not None and configured.success, (mode, configured and configured.error)
                seen = []
                for feature in clip.frames:
                    response = supervisor.send_request_and_await_response(
                        WorkerType.VISUALIZER, MessageType.VIS_INPUT, {"frame": feature}, timeout_ms=30_000)
                    assert response is not None and response.success, (mode, response and response.error)
                    seen.append(evidence.frame_digest(reader.take().state))
                stopped = supervisor.send_request_and_await_response(
                    WorkerType.VISUALIZER, MessageType.VIS_STOP, {}, timeout_ms=30_000)
                assert stopped is not None and stopped.success
            finally:
                reader.close()
            assert len(expected) > 20 and seen == expected, mode
    finally:
        supervisor.shutdown()
    assert not supervisor.is_running(WorkerType.VISUALIZER)


_PROBE = r"""
import json, sys
from core.process.supervisor import ProcessSupervisor
from core.process.types import MessageType, WorkerType
from core.visualizer_engine.engine_worker import visualizer_worker_main
from core.visualizer_engine.packet_mailbox import PacketMailbox
if __name__ == "__main__":
    import tools.expanded_visualizer_evidence as evidence

    frame = evidence.shipped_clip(0.05).frames[0]
    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    supervisor.start(WorkerType.VISUALIZER)
    loaded = {}
    for mode in sys.argv[1:]:
        # P2b's live engine first (its ThreadManager, capture lane, compute pool and recorded capture, one input
        # ticked), then the reply of a plain configure lists every Qt module the process has loaded so far.
        reader = PacketMailbox(role="reader")
        supervisor.send_request_and_await_response(
            WorkerType.VISUALIZER, MessageType.VIS_CONFIGURE,
            {"mapping": reader.mapping_name, "mode": mode, "runtime_generation": 1, "inputs": "live"}, timeout_ms=60000)
        ticked = supervisor.send_request_and_await_response(
            WorkerType.VISUALIZER, MessageType.VIS_INPUT, {"frame": frame}, timeout_ms=60000)
        reader.close()
        if not (ticked and ticked.success):
            loaded[mode] = repr(ticked and ticked.error)
            continue
        reader = PacketMailbox(role="reader")
        response = supervisor.send_request_and_await_response(
            WorkerType.VISUALIZER, MessageType.VIS_CONFIGURE,
            {"mapping": reader.mapping_name, "mode": mode, "runtime_generation": 1}, timeout_ms=60000)
        loaded[mode] = response.payload["qt_modules"] if response and response.success else repr(response and response.error)
        reader.close()
    supervisor.shutdown()
    print(json.dumps(loaded))
"""


def test_the_worker_loads_no_gui_stack_in_a_production_spawn(tmp_path):
    # A fresh interpreter, as the app spawns it: the worker loads QtCore and, for the presentation config the tick
    # still reads, QtGui (QColor), never Quick, QML or Widgets; the live engine (P2b) adds nothing to that. (A child spawned from inside pytest also carries the
    # test environment's imports, so this runs outside it.)
    import json
    import subprocess
    import sys
    from pathlib import Path

    script = tmp_path / "probe.py"
    script.write_text(_PROBE, encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    out = subprocess.run([sys.executable, str(script), *_modes()], cwd=root, capture_output=True, text=True,
                         timeout=300, env={**__import__("os").environ, "PYTHONPATH": str(root)})
    assert out.returncode == 0, out.stderr[-2000:]
    loaded = json.loads(out.stdout.strip().splitlines()[-1])
    assert set(loaded) == set(_modes())
    for mode, modules in loaded.items():
        assert isinstance(modules, list) and set(modules) <= {"PySide6.QtCore", "PySide6.QtGui"}, (mode, modules)


@pytest.mark.qt
def test_sessions_never_reuse_a_drift_family_label(qt_app):
    # Extruded Bubble's drift revisions are the renderer's geometry cache identity: two sessions (a mode switch, a
    # restarted worker) with their own namespaces never share one, so a stale geometry can never be reused.
    import tools.expanded_visualizer_evidence as evidence

    clip = evidence.shipped_clip(1.0)
    seen = {}
    for namespace in (3, 4):
        reader = PacketMailbox(role="reader")
        session = EngineSession(mapping=reader.mapping_name, mode="extruded_bubble", runtime_generation=GENERATION,
                                label_namespace=namespace)
        revisions = set()
        try:
            for feature in clip.frames:
                session.tick(feature)
                frame = reader.take().state
                for family in getattr(frame.mode_state, "drift_families", ()) or ():
                    revisions.add(int(family.revision))
        finally:
            session.close()
            reader.close()
        assert revisions and all(revision >> 32 == namespace for revision in revisions), (namespace, revisions)
        seen[namespace] = revisions
    assert not seen[3] & seen[4]
    with pytest.raises(ValueError):
        EngineSession(mapping="unused", mode="spectrum", runtime_generation=1, label_namespace=-1)


@pytest.mark.qt
def test_the_worker_writer_wakes_the_owner_on_every_publish(qt_app):
    # Across processes the edge cannot be derived from the reader's acknowledgement (it lands only after the decode,
    # so a publish in between was mistaken for "still unread" and no wake was ever sent again: audit C1). One byte per
    # publish; the owner's emitter coalesces them.
    import tools.expanded_visualizer_evidence as evidence

    class Recorder:
        def __init__(self):
            self.sent = 0

        def send_bytes(self, _data):
            self.sent += 1

        def close(self):
            pass

    frames = evidence.shipped_clip(0.3).frames
    reader = PacketMailbox(role="reader")
    sender = Recorder()
    session = EngineSession(mapping=reader.mapping_name, mode="spectrum", runtime_generation=GENERATION)
    session.mailbox._wake_sender = sender                 # the writer end of the owner's wake pipe
    try:
        session.tick(frames[0])
        reader.peek()                                     # the owner has accepted but not yet acknowledged
        session.tick(frames[1])
        reader.take()
        session.tick(frames[2])
        session.tick(frames[3])
        assert sender.sent == 4
    finally:
        session.close()
        reader.close()


def _free_running_writer(mapping, wake, count, words):
    import time

    mailbox = PacketMailbox(role="writer", attach=mapping, wake_sender=wake)
    try:
        for index in range(1, count+1):
            mailbox.publish((index,)*words, generation=1, activation_id=1, now_ts=float(index))
            time.sleep(1/165)
    finally:
        mailbox.close()


def test_a_free_running_writer_never_strands_or_tears_a_frame():
    # Audit C1/C2: a writer in its own process at ~165 Hz, the reader taking on wakes with random 0-20 ms stalls.
    # Every frame taken is whole (its payload repeats its own number), and the newest frame is always taken by a wake.
    import multiprocessing
    import random
    import threading

    count, words = 330, 4096
    reader = PacketMailbox(role="reader")
    receiver, sender = multiprocessing.Pipe(duplex=False)
    woke = threading.Event()
    reader.set_wake_callback(woke.set)
    reader.listen_for_wakes(receiver)
    child = multiprocessing.get_context("spawn").Process(
        target=_free_running_writer, args=(reader.mapping_name, sender, count, words))
    child.start()
    sender.close()
    rng = random.Random(7)
    taken = []
    try:
        while not taken or taken[-1] != count:
            assert woke.wait(5.0), f"stranded after {taken[-1:] or 'nothing'}"   # no poll: only a wake may deliver it
            woke.clear()
            publication = reader.take()
            if publication is not None:
                state = publication.state
                assert len(set(state)) == 1 and len(state) == words, "a torn frame was accepted"
                taken.append(state[0])
            threading.Event().wait(rng.uniform(0.0, 0.02))
        assert taken == sorted(taken) and taken[-1] == count
    finally:
        child.join(30)
        reader.close()


@pytest.mark.qt
def test_a_worker_frame_wakes_the_owner_across_processes(qt_app):
    import multiprocessing
    import threading

    import tools.expanded_visualizer_evidence as evidence

    frames = evidence.shipped_clip(0.3).frames
    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    assert supervisor.start(WorkerType.VISUALIZER)
    reader = PacketMailbox(role="reader")
    receiver, sender = multiprocessing.Pipe(duplex=False)
    taken, woke = [], threading.Event()

    def on_wake():                                        # what the owner's GUI wake does: take the newest frame
        publication = reader.take()
        if publication is not None:
            taken.append(publication.revision)
            woke.set()

    reader.set_wake_callback(on_wake)
    reader.listen_for_wakes(receiver)
    try:
        configured = supervisor.send_request_and_await_response(
            WorkerType.VISUALIZER, MessageType.VIS_CONFIGURE,
            {"mapping": reader.mapping_name, "mode": "spectrum", "runtime_generation": GENERATION, "wake": sender},
            timeout_ms=60_000)
        assert configured is not None and configured.success, configured and configured.error
        sender.close()                                    # the worker holds its own end now
        for index in range(3):
            woke.clear()
            response = supervisor.send_request_and_await_response(
                WorkerType.VISUALIZER, MessageType.VIS_INPUT, {"frame": frames[index]}, timeout_ms=30_000)
            assert response is not None and response.success
            assert woke.wait(10.0), index                 # the frame arrived by a wake, never a poll
        assert taken == [1, 2, 3]
    finally:
        supervisor.shutdown()
        reader.close()


def test_a_writer_attaches_only_to_an_owned_mapping():
    with pytest.raises(ValueError):
        PacketMailbox(role="writer")
    with pytest.raises(ValueError):
        PacketMailbox(role="reader", attach="srpss_viz_x")
