"""P2-ANALYSIS-FRESHNESS: one compute in flight, one newest pending source.

Compositor publication-to-paint is already healthy (p50 roughly 3.4-5.9 ms), so
the visualizer feeling late is an upstream problem. The installed runs carried a
recurring authoritative-analysis age class around 90 ms.

The cause was in ``_SpotifyBeatEngine.tick``: it consumed the newest audio frame
and then, if a compute was already active, simply dropped it. Nothing was
pending, so the next analysis could only begin from whatever a LATER tick
happened to consume.

The correction is latest-state freshness, not a queue:

* at most one analysis compute in flight;
* at most one pending source frame, and a newer frame REPLACES it;
* when a compute completes, its DSP/worker state commits and the single newest
  pending frame launches immediately;
* intermediate frames are never replayed.

These bars use a DELAYED persistent compute lane so the overlap case actually happens.
An immediate lane completes each packet inside ``submit``, which is exactly the
shape that hid this defect. The old per-frame Future/task path is forbidden.
"""

from __future__ import annotations

import pytest

from widgets.spotify_visualizer.audio_worker import _AudioFrame


class _Result:
    def __init__(self, value, *, success=True):
        self.success = success
        self.result = value


class _DelayedComputeLane:
    """One serial lane packet held until the test explicitly completes it."""

    def __init__(self, worker, callback, *, category: str):
        self.worker = worker
        self.callback = callback
        self.category = category
        self.jobs: list[object] = []
        self.submits = 0
        self.is_stopped = False

    def submit(self, payload) -> bool:
        if self.is_stopped or self.jobs:
            return False
        self.submits += 1
        self.jobs.append(payload)
        return True

    def cancel_pending(self) -> int:
        # A packet already executing is not cancelable in the production lane;
        # these tests model that one in-flight packet and engine-side newest slot.
        return 0

    def stop(self) -> None:
        self.is_stopped = True
        self.jobs.clear()

    @property
    def in_flight(self) -> int:
        return len(self.jobs)

    def complete_next(self):
        payload = self.jobs.pop(0)
        value = self.worker(payload)
        self.callback(_Result(value), payload=payload)

    def fail_next_task(self):
        payload = self.jobs.pop(0)
        self.callback(_Result(None, success=False), payload=payload)


class _DelayedComputeManager:
    """Creates the required persistent audio-analysis lane; no Future fallback."""

    supports_persistent_compute_lanes = True

    def __init__(self):
        self.lane: _DelayedComputeLane | None = None
        self.general_submits = 0

    def create_compute_lane(self, worker, callback, *, lane_id, category):
        del lane_id
        self.lane = _DelayedComputeLane(worker, callback, category=str(category))
        return self.lane

    def submit_compute_task(self, *_args, **_kwargs):
        self.general_submits += 1
        raise AssertionError("visualizer audio must not submit generic Future tasks")

    @property
    def jobs(self):
        return [] if self.lane is None else self.lane.jobs

    @property
    def submits(self) -> int:
        return 0 if self.lane is None else self.lane.submits

    @property
    def in_flight(self) -> int:
        return 0 if self.lane is None else self.lane.in_flight

    def complete_next(self):
        assert self.lane is not None
        self.lane.complete_next()

    def fail_next_task(self):
        assert self.lane is not None
        self.lane.fail_next_task()


@pytest.fixture
def np_module():
    return pytest.importorskip("numpy")


@pytest.fixture
def engine(qt_app, np_module):
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

    instance = _SpotifyBeatEngine(16)
    instance._is_spotify_playing = True
    instance._audio_worker._np = np_module
    yield instance
    instance.deleteLater()


@pytest.fixture
def manager(engine):
    tm = _DelayedComputeManager()
    engine.set_thread_manager(tm)
    return tm


def _publish(engine, np_module, level: float):
    """Publish one distinguishable capture frame."""
    samples = (np_module.ones(1024, dtype="float32") * float(level))
    engine._audio_buffer.publish(
        _AudioFrame(
            samples=samples,
            activation_id=engine.get_activation_id(),
            capture_ts=1000.0 + level,
        )
    )
    return samples


def _pending_level(engine, np_module) -> float | None:
    samples = engine._pending_analysis_samples
    if samples is None:
        return None
    return float(np_module.asarray(samples).ravel()[0])


# ---------------------------------------------------------------------------
# Capture provenance
# ---------------------------------------------------------------------------


class TestCaptureProvenance:
    def test_audio_frames_carry_a_capture_timestamp(self):
        frame = _AudioFrame(samples=None, activation_id=1, capture_ts=12.5)
        assert frame.capture_ts == 12.5

    def test_capture_timestamp_defaults_to_zero_for_legacy_frames(self):
        assert _AudioFrame(samples=None).capture_ts == 0.0

    def test_tick_ages_audio_from_capture_not_from_the_tick(self, engine, manager, np_module):
        _publish(engine, np_module, 0.5)
        engine.tick()
        assert engine._last_audio_ts == pytest.approx(1000.5)


# ---------------------------------------------------------------------------
# One in flight, one latest pending
# ---------------------------------------------------------------------------


class TestOneInFlightOneLatestPending:
    def test_first_frame_starts_a_compute_with_nothing_pending(self, engine, manager, np_module):
        _publish(engine, np_module, 0.1)
        engine.tick()
        assert manager.in_flight == 1
        assert engine.has_pending_analysis_frame() is False

    def test_later_frames_replace_the_pending_frame(self, engine, manager, np_module):
        """A/B/C/D: A runs, pending must be D only - never a backlog."""
        _publish(engine, np_module, 0.1)
        engine.tick()

        for level in (0.2, 0.3, 0.4):
            _publish(engine, np_module, level)
            engine.tick()

        assert manager.in_flight == 1, "more than one compute was in flight"
        assert manager.submits == 1, "an intermediate frame was scheduled"
        assert _pending_level(engine, np_module) == pytest.approx(0.4)

    def test_completing_the_compute_launches_only_the_newest_pending(
        self, engine, manager, np_module
    ):
        _publish(engine, np_module, 0.1)
        engine.tick()
        for level in (0.2, 0.3, 0.4):
            _publish(engine, np_module, level)
            engine.tick()

        manager.complete_next()

        assert manager.submits == 2, "B and C must never be computed"
        assert manager.in_flight == 1
        assert engine.has_pending_analysis_frame() is False

    def test_the_completed_result_commits_before_the_next_launch(
        self, engine, manager, np_module
    ):
        """A completed analysis carries DSP state the next compute needs."""
        _publish(engine, np_module, 0.1)
        engine.tick()
        _publish(engine, np_module, 0.2)
        engine.tick()

        order: list[str] = []
        original_commit = engine._commit_analysis_frame
        original_schedule = engine._schedule_compute_bars_task

        def _commit(**kwargs):
            order.append("commit")
            return original_commit(**kwargs)

        def _schedule(samples, **kwargs):
            order.append("schedule")
            return original_schedule(samples, **kwargs)

        engine._commit_analysis_frame = _commit
        engine._schedule_compute_bars_task = _schedule

        manager.complete_next()

        assert order == ["commit", "schedule"], (
            "the pending frame launched before the previous DSP state committed"
        )

    def test_a_second_overlap_round_also_keeps_only_the_newest(
        self, engine, manager, np_module
    ):
        _publish(engine, np_module, 0.1)
        engine.tick()
        _publish(engine, np_module, 0.4)
        engine.tick()
        manager.complete_next()  # D launches

        for level in (0.5, 0.6):
            _publish(engine, np_module, level)
            engine.tick()

        assert _pending_level(engine, np_module) == pytest.approx(0.6)
        assert manager.in_flight == 1

    def test_no_backlog_accumulates_over_many_frames(self, engine, manager, np_module):
        _publish(engine, np_module, 0.1)
        engine.tick()
        for i in range(50):
            _publish(engine, np_module, 0.01 * (i + 2))
            engine.tick()
        assert manager.in_flight == 1
        assert manager.submits == 1
        assert engine.has_pending_analysis_frame() is True


class TestFailureAndFencing:
    def test_a_failed_task_releases_the_slot_and_continues(
        self, engine, manager, np_module
    ):
        _publish(engine, np_module, 0.1)
        engine.tick()
        _publish(engine, np_module, 0.4)
        engine.tick()

        manager.fail_next_task()

        assert engine._compute_task_active is True, (
            "the newest pending frame should have claimed the freed slot"
        )
        assert manager.submits == 2, "a failed task must not deadlock the lane"
        assert engine.has_pending_analysis_frame() is False

    def test_activation_replacement_discards_the_pending_source(
        self, engine, manager, np_module
    ):
        _publish(engine, np_module, 0.1)
        engine.tick()
        _publish(engine, np_module, 0.4)
        engine.tick()
        assert engine.has_pending_analysis_frame() is True

        engine.reset_smoothing_state()

        assert engine.has_pending_analysis_frame() is False
        # A serial-lane packet already executing cannot be unsafely preempted.
        # The generation fence keeps its slot asserted until the stale callback
        # returns, then releases it without publication.
        assert engine._compute_task_active is True
        manager.complete_next()
        assert engine._compute_task_active is False

    def test_a_stale_pending_frame_is_never_launched(self, engine, manager, np_module):
        _publish(engine, np_module, 0.1)
        engine.tick()
        _publish(engine, np_module, 0.4)
        engine.tick()

        # Replace the activation WITHOUT clearing the pending slot, to prove the
        # launch path fences its input as well as its output.
        engine._activation_id += 1
        submits_before = manager.submits
        engine._launch_pending_analysis_frame()

        assert manager.submits == submits_before
        assert engine.has_pending_analysis_frame() is False

    def test_a_superseded_result_does_not_claim_the_current_slot(
        self, engine, manager, np_module
    ):
        _publish(engine, np_module, 0.1)
        engine.tick()
        _publish(engine, np_module, 0.4)
        engine.tick()

        # A generation boundary between submit and result.
        engine.cancel_pending_compute_tasks()
        engine._compute_task_active = True  # the new owner holds the slot

        manager.complete_next()

        assert engine._compute_task_active is True, (
            "a stale callback released a slot it no longer owned"
        )

    def test_pending_is_returned_when_the_slot_is_already_claimed(
        self, engine, manager, np_module
    ):
        _publish(engine, np_module, 0.1)
        engine.tick()
        _publish(engine, np_module, 0.4)
        engine.tick()

        engine._compute_task_active = True
        submits_before = manager.submits
        engine._launch_pending_analysis_frame()

        assert manager.submits == submits_before, "two computes were in flight"
        assert _pending_level(engine, np_module) == pytest.approx(0.4)


class TestNoQueueSemantics:
    def test_the_engine_has_no_analysis_backlog_container(self, engine):
        """Latest-state freshness, not a FIFO."""
        import inspect

        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

        source = inspect.getsource(_SpotifyBeatEngine)
        for forbidden in ("deque(", "_analysis_queue", "catch_up", "replay_skipped"):
            assert forbidden not in source, (
                f"{forbidden} suggests a backlog rather than latest-state freshness"
            )

    def test_pending_is_a_single_slot(self, engine):
        assert isinstance(engine._pending_analysis_samples, type(None))
        assert not isinstance(engine._pending_analysis_samples, (list, tuple))

    def test_paused_playback_does_not_accumulate_pending_work(
        self, engine, manager, np_module
    ):
        engine._is_spotify_playing = False
        for level in (0.1, 0.2, 0.3):
            _publish(engine, np_module, level)
            engine.tick()
        assert manager.submits == 0
        assert engine.has_pending_analysis_frame() is False
