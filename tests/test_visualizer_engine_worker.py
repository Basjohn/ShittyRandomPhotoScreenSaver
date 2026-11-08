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
    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    supervisor.start(WorkerType.VISUALIZER)
    loaded = {}
    for mode in sys.argv[1:]:
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
    # still reads, QtGui (QColor), never Quick, QML or Widgets. (A child spawned from inside pytest also carries the
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


def test_a_writer_attaches_only_to_an_owned_mapping():
    with pytest.raises(ValueError):
        PacketMailbox(role="writer")
    with pytest.raises(ValueError):
        PacketMailbox(role="reader", attach="srpss_viz_x")
