from __future__ import annotations

import threading
import time
from types import MethodType

from core.threading.manager import ThreadManager, ThreadPoolType
from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine


def test_audio_analysis_uses_generation_owned_lane_without_executor_tasks(
    monkeypatch,
):
    manager = ThreadManager(
        config={ThreadPoolType.IO: 1, ThreadPoolType.COMPUTE: 1}
    )
    engine = _SpotifyBeatEngine(bar_count=4)
    committed = threading.Event()
    commit_payloads: list[dict] = []

    def _compute(self, packet):
        return {
            "raw": [0.1, 0.2, 0.3, 0.4],
            "smoothed": [0.1, 0.2, 0.3, 0.4],
            "ts": time.time(),
            "reset": False,
            "energy": None,
            "worker_state": None,
            "activation_id": packet["activation_id"],
        }

    def _commit(**kwargs):
        commit_payloads.append(kwargs)
        committed.set()
        return True

    monkeypatch.setattr(
        engine,
        "_compute_analysis_packet",
        MethodType(_compute, engine),
    )
    monkeypatch.setattr(engine, "_commit_analysis_frame", _commit)

    try:
        engine.set_thread_manager(manager)
        engine.set_runtime_generation(77)
        engine._schedule_compute_bars_task(object())

        assert committed.wait(1.0)
        deadline = time.monotonic() + 1.0
        while engine._compute_task_active:
            assert time.monotonic() < deadline
            time.sleep(0.001)

        assert len(commit_payloads) == 1
        assert commit_payloads[0]["activation_id"] == engine._activation_id
        assert "visualizer.audio_analysis" not in manager.get_task_category_stats()

        lane_diag = engine.get_analysis_lane_diagnostics()
        assert lane_diag["executor_task_submissions"] == 0
        assert lane_diag["logical_steps_completed"] == 1
        assert lane_diag["logical_steps_published"] == 1
        assert any(
            item.get("kind") == "compute_lane"
            and item.get("runtime_generation") == 77
            for item in manager.get_lifecycle_ownership_snapshot()["active_tasks"]
        )

        engine.cancel_pending_compute_tasks()
        assert not any(
            item.get("runtime_generation") == 77
            for item in manager.get_lifecycle_ownership_snapshot()["active_tasks"]
        )
    finally:
        engine.force_stop()
        manager.shutdown(wait=True, timeout=1.0)
