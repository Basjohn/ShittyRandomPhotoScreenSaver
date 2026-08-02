from __future__ import annotations

from types import SimpleNamespace

from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine


class _ImmediateManager:
    supports_persistent_compute_lanes = True

    def __init__(self) -> None:
        self.submissions: list[str] = []
        self.create_lane_calls = 0

    def create_compute_lane(self, *_args, **_kwargs):
        self.create_lane_calls += 1
        raise AssertionError("Audio recovery path must not create a persistent lane")

    def submit_compute_task(
        self,
        worker,
        *args,
        callback=None,
        category="uncategorized",
        **kwargs,
    ):
        self.submissions.append(str(category))
        try:
            value = worker(*args, **kwargs)
            result = SimpleNamespace(success=True, result=value, error=None)
        except Exception as exc:
            result = SimpleNamespace(success=False, result=None, error=exc)
        if callback is not None:
            callback(result)
        return "audio-analysis-test"


def test_audio_analysis_uses_approved_general_executor_path(monkeypatch):
    manager = _ImmediateManager()
    engine = _SpotifyBeatEngine(bar_count=4)
    committed: list[dict] = []
    worker_state = object()

    monkeypatch.setattr(
        engine._audio_worker,
        "make_compute_snapshot",
        lambda: worker_state,
    )

    from widgets.spotify_visualizer import bar_computation

    monkeypatch.setattr(
        bar_computation,
        "compute_bars_from_samples",
        lambda state, _samples: [0.1, 0.2, 0.3, 0.4]
        if state is worker_state
        else None,
    )
    monkeypatch.setattr(
        engine,
        "_commit_analysis_frame",
        lambda **kwargs: committed.append(kwargs) or True,
    )

    engine.set_thread_manager(manager)
    engine._schedule_compute_bars_task(object())

    assert manager.create_lane_calls == 0
    assert manager.submissions == ["visualizer.audio_analysis"]
    assert not engine._compute_task_active
    assert len(committed) == 1
    assert committed[0]["raw_bars"] == [0.1, 0.2, 0.3, 0.4]
    assert committed[0]["worker_state"] is worker_state
    assert committed[0]["activation_id"] == engine._activation_id
