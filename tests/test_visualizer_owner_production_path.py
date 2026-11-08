"""The production owner's own configure-and-start path, on both process paths (checkpoint audit 6, A6-L5; the engine
worker the default since 8 Nov).

``owner_replay`` (the reference every engine-worker identity gate compares against) configures with the offline
replays' ``configure_offline_controller``; the product configures through the host binding's ``construct`` (the
activation resolved from Settings, the owner's ``configure`` with it, bind, Media's play edge, ``start`` and its
cadence).

- **In process (the fallback, stated):** ``tools/visualizer_replay/owner_production_replay.py`` replays a shipped clip
  through that real path on the in-process path (the recorded engine, the owner's installed cadence step run once per
  frame, no thread, no window shown). For every mode its frames equal the offline replay's, once both build the engine
  at the mode's bar count (the binding's construction): so the engine-worker identity gates, which compare against the
  offline replay, compare against the product's frames. The same replay at ``32f28d4f^`` (before the configure
  refactor) gave identical digests for every mode (A6-L5 record in ``Docs/Future_Work/Native_Core_P2_Engine_Design.md``).
- **The default (the engine worker on Windows):** the same binding path with no path stated builds an owner on a real
  ``WorkerType.VISUALIZER`` process (no fallback), and its frames equal the same owner's in process (stated), frame for
  frame through ``owner_worker_gate``'s identity script (play, a warm pause, a park, a mode switch); the worker side's
  capture is the shipped clip's PCM through the link's test control, never a device.
"""
import sys

import pytest


def _modes():
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


@pytest.mark.qt
@pytest.mark.parametrize("mode", _modes())
def test_the_in_process_production_owner_path_ticks_the_offline_replays_frames(qt_app, mode):
    import tools.expanded_visualizer_evidence as evidence
    from tools.visualizer_replay.owner_production_replay import production_owner_replay
    from widgets.spotify_visualizer.feature_replay import offline_activation_request

    clip = evidence.shipped_clip(1.5)
    bar_count = offline_activation_request(mode)["settings_model"].resolve_bar_count(mode)
    production = production_owner_replay(clip, mode)
    offline = evidence.owner_replay(clip, mode, generation=9001, bar_count=bar_count)["digests"]
    assert len(production) == len(clip.frames) > 30
    assert production == offline, (mode, next(i for i, (a, b) in enumerate(zip(production, offline)) if a != b))


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


@pytest.fixture
def default_path(monkeypatch):
    """The product's default path: no path chosen (the process admission cleared), the device refused."""
    from core.diagnostics import experiment_flags
    from core.visualizer_engine.engine_worker import EngineSession
    from widgets.spotify_visualizer import engine_worker_link

    def _device(_config=None):
        raise AssertionError("a test opened an audio device")

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", _device)
    monkeypatch.setattr(EngineSession, "LIVE_EDGE_TIMEOUT_S", 10.0)
    saved = experiment_flags.active_experiment_flags()
    experiment_flags.override_active_flags_for_testing(None)
    engine_worker_link.reset_run_state_for_testing()
    try:
        yield
    finally:
        engine_worker_link.reset_run_state_for_testing()
        experiment_flags.override_active_flags_for_testing(saved)


@pytest.mark.qt
@pytest.mark.skipif(sys.platform != "win32", reason="the engine worker is the default on Windows only")
@pytest.mark.parametrize("mode", _modes())
def test_the_default_production_owner_runs_on_the_engine_worker_with_the_in_process_frames(
        qt_app, supervisor, default_path, mode):
    import tools.expanded_visualizer_evidence as evidence
    from tools.visualizer_replay import owner_worker_gate as gate

    verdict = gate.identity_gate(mode, evidence.shipped_clip(5.5).frames, supervisor, default_path=True)
    assert verdict["stayed_on_worker"], verdict
    assert verdict["identical"], verdict
