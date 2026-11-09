"""M2: one cold configure timeout per run, using the existing disable/fallback owner."""
import pytest


@pytest.mark.qt
def test_timeout_disables_later_owners_until_a_new_run_and_fences_late_events(qt_app, monkeypatch):
    from core.process.types import MessageType, WorkerResponse
    from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor, _pump
    from tests.test_visualizer_owner_engine_worker_liveness import _HungSupervisor
    from tools.visualizer_replay import owner_worker_gate as gate
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module
    import numpy as np

    engine_worker_link.reset_run_state_for_testing()
    monkeypatch.setattr(gate.OwnerRig, 'settle', lambda self: None)
    monkeypatch.setattr(owner_module.QuickDisplayVisualizerOwner, '_arm_first_configure_deadline', lambda *a: None)
    hung, normal = _HungSupervisor(), _InProcessSupervisor()
    rigs = []
    try:
        with engine_worker_link.recorded_capture_for_testing(pcm=np.zeros(512, dtype=np.float32), pcm_rate=48000):
            first = gate.OwnerRig('spectrum', worker=True, supervisor=hung, playing=False)
            rigs.append(first)
            owner = first.build()
            link = owner._worker
            namespace = link.label_namespace
            pending = list(hung.callbacks.values())
            owner._on_first_configure_deadline(namespace)
            assert engine_worker_link.worker_disabled_for_run()
            assert owner._worker is None and owner.controller.engine is not None
            for callback in pending:
                callback(WorkerResponse(MessageType.VIS_CONFIGURE, 1, 'late', True,
                                        payload={'engine_generation': 0, 'activation_id': 0}))
            _pump(first, .02)
            assert owner._worker is None
            first.close()
            sent = len(hung.sent)
            second = gate.OwnerRig('spectrum', worker=True, supervisor=hung, playing=False)
            rigs.append(second)
            with pytest.raises(RuntimeError, match='fell back in process'):
                second.build()
            assert len(hung.sent) == sent and second.owner.controller.engine is not None
            second.close()
            engine_worker_link.reset_run_state_for_testing()
            third = gate.OwnerRig('spectrum', worker=True, supervisor=normal, playing=False)
            rigs.append(third)
            fresh = third.build()
            assert fresh._worker is not None
            fresh._on_first_configure_deadline(namespace)  # stale earlier owner's namespace
            assert not engine_worker_link.worker_disabled_for_run()
            _pump(third, .05)
            assert fresh._worker.configured
            fresh._on_first_configure_deadline(fresh._worker.label_namespace)  # normal reply already won
            assert not engine_worker_link.worker_disabled_for_run()
    finally:
        for rig in reversed(rigs):
            rig.close()
        normal.close()
        hung.close()
        engine_worker_link.reset_run_state_for_testing()
