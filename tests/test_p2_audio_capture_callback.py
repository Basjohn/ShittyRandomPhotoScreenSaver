"""P2-R1: the REAL capture callback registered by the audio worker must publish.

The installed run recorded tens of thousands of

    [SPOTIFY_VIS] Exception suppressed: name 'time' is not defined

from ``widgets.spotify_visualizer.audio_worker``. The callback reached
``capture_ts=time.time()``, raised ``NameError``, was swallowed by the broad
handler, and published nothing. The worker still reported itself started, so the
visualizer animated idly and never became live.

The whole suite passed anyway, because every existing bar constructs
``_AudioFrame`` directly and never executes the callback that
``SpotifyVisualizerAudioWorker.start()`` actually registers with the backend.

These bars close that seam: a fake backend accepts the real callback, calls it
with a representative numpy block, and the publication is asserted on the real
worker's buffer. Nothing here builds an ``_AudioFrame`` by hand.
"""

from __future__ import annotations

import logging

import pytest

from utils.audio_capture import AudioCaptureBackend
from utils.lockfree import TripleBuffer
from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker


@pytest.fixture
def np_module():
    return pytest.importorskip("numpy")


class _RecordingHandler(logging.Handler):
    """Counts records on the audio-worker logger only."""

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def worker_errors():
    """Capture ERROR records from the worker logger, isolated from other suites."""
    from widgets.spotify_visualizer import audio_worker as module

    handler = _RecordingHandler()
    module.logger.addHandler(handler)
    try:
        yield handler.records
    finally:
        module.logger.removeHandler(handler)


class _FakeBackend(AudioCaptureBackend):
    """A capture backend that hands the worker's own callback back to the test.

    It deliberately implements the real ``AudioCaptureBackend`` contract, so the
    shared capture-health state machine and the worker's start path behave
    exactly as they do in production.
    """

    def __init__(self, config=None):
        self._config = config
        self._callback = None
        self._negotiated_block_size = 512
        self.start_calls = 0

    # -- production contract -------------------------------------------
    def start(self, callback):
        self.start_calls += 1
        self._callback = callback
        self._note_capture_starting()
        return True

    def stop(self):
        self._callback = None
        self._note_capture_stopped()

    def is_running(self):
        return self._callback is not None

    @property
    def sample_rate(self):
        return 48000

    @property
    def channels(self):
        return 2

    def restart(self):
        callback = self._callback
        self.stop()
        return self.start(callback) if callback is not None else False

    # -- test drive ----------------------------------------------------
    def deliver(self, samples):
        """Invoke the callback the worker registered, exactly as WASAPI would."""
        assert self._callback is not None, "the worker never registered a callback"
        self._note_capture_callback()
        self._callback(samples)


@pytest.fixture
def worker(qt_app, np_module, monkeypatch):
    """A real worker whose only fake is the capture backend."""
    backends: list[_FakeBackend] = []

    def _create(config=None):
        backend = _FakeBackend(config)
        backends.append(backend)
        return backend

    monkeypatch.setattr(
        "widgets.spotify_visualizer.audio_worker.create_audio_capture", _create
    )
    buffer = TripleBuffer()
    instance = SpotifyVisualizerAudioWorker(16, buffer)
    instance._activation_id = 7
    instance.start()
    assert backends, "the worker did not create a capture backend"
    yield instance, backends[-1], buffer
    instance.stop()
    instance.deleteLater()


def _block(np_module, *, frames=1024, channels=2, level=0.25):
    return (np_module.ones((frames, channels), dtype="float32") * level)


class TestRealCallbackPublishes:
    def test_the_worker_registered_a_callback(self, worker):
        _instance, backend, _buffer = worker
        assert backend.start_calls == 1
        assert backend.is_running() is True

    def test_one_delivered_block_publishes_one_frame(self, worker, np_module):
        _instance, backend, buffer = worker
        assert buffer.consume_latest() is None

        backend.deliver(_block(np_module))

        frame = buffer.consume_latest()
        assert frame is not None, (
            "the real capture callback published nothing - this is exactly the "
            "installed failure"
        )
        assert frame.samples is not None
        assert len(frame.samples) > 0

    def test_the_published_frame_carries_a_capture_timestamp(self, worker, np_module):
        _instance, backend, buffer = worker
        backend.deliver(_block(np_module))
        frame = buffer.consume_latest()
        assert frame is not None
        assert frame.capture_ts > 0.0, "capture provenance was never stamped"

    def test_capture_timestamps_advance_across_blocks(self, worker, np_module):
        _instance, backend, buffer = worker
        backend.deliver(_block(np_module))
        first = buffer.consume_latest().capture_ts
        backend.deliver(_block(np_module))
        second = buffer.consume_latest().capture_ts
        assert second >= first

    def test_activation_identity_is_preserved(self, worker, np_module):
        instance, backend, buffer = worker
        backend.deliver(_block(np_module))
        assert buffer.consume_latest().activation_id == 7

        instance._activation_id = 9
        backend.deliver(_block(np_module))
        assert buffer.consume_latest().activation_id == 9

    def test_the_callback_raises_nothing_and_records_no_failure(self, worker, np_module):
        instance, backend, _buffer = worker
        backend.deliver(_block(np_module))
        assert instance._capture_callback_failures == 0

    def test_no_error_is_logged_for_a_healthy_callback(self, worker, np_module, worker_errors):
        _instance, backend, _buffer = worker
        backend.deliver(_block(np_module))
        assert worker_errors == []

    def test_mono_input_publishes_too(self, worker, np_module):
        _instance, backend, buffer = worker
        backend.deliver(np_module.ones(1024, dtype="float32") * 0.4)
        assert buffer.consume_latest() is not None

    def test_multichannel_input_publishes_too(self, worker, np_module):
        _instance, backend, buffer = worker
        backend.deliver(_block(np_module, channels=6))
        assert buffer.consume_latest() is not None

    def test_latest_wins_across_a_burst(self, worker, np_module):
        """The buffer is latest-state, not a backlog."""
        _instance, backend, buffer = worker
        for level in (0.1, 0.2, 0.3):
            backend.deliver(_block(np_module, level=level))
        frame = buffer.consume_latest()
        assert frame is not None
        assert float(np_module.asarray(frame.samples).ravel()[0]) == pytest.approx(0.3)
        assert buffer.consume_latest() is None


class TestReintroducingTheDefectFailsThisBar:
    def test_removing_the_time_module_breaks_publication(
        self, worker, np_module, monkeypatch
    ):
        """The negative control the previous round did not have.

        With ``time`` unavailable the callback raises before publishing, exactly
        as it did in the installed run.
        """
        instance, backend, buffer = worker
        monkeypatch.delattr(
            "widgets.spotify_visualizer.audio_worker.time", raising=True
        )

        backend.deliver(_block(np_module))

        assert buffer.consume_latest() is None
        assert instance._capture_callback_failures == 1


class TestCallbackFailureIsLoudAndBounded:
    def test_the_first_failure_is_an_error_not_a_debug_line(
        self, worker, np_module, monkeypatch, worker_errors
    ):
        """End to end: a dead callback must not stay DEBUG-only."""
        _instance, backend, _buffer = worker
        monkeypatch.delattr(
            "widgets.spotify_visualizer.audio_worker.time", raising=True
        )
        backend.deliver(_block(np_module))
        assert worker_errors, "a silently dead audio path must not stay DEBUG-only"

    def test_repeated_failures_do_not_log_per_frame(self, worker, worker_errors):
        instance, _backend, _buffer = worker
        before = len(worker_errors)

        for _ in range(200):
            instance._report_capture_callback_failure(RuntimeError("boom"))

        assert len(worker_errors) - before == 1, "the failure report flooded the log"
        assert instance._capture_callback_failures == 200

    def test_a_sampled_report_appears_for_a_long_failure_run(self, worker, worker_errors):
        instance, _backend, _buffer = worker
        before = len(worker_errors)
        interval = instance._CAPTURE_FAILURE_LOG_INTERVAL

        for _ in range(interval):
            instance._report_capture_callback_failure(RuntimeError("boom"))

        assert len(worker_errors) - before == 2, (
            "a persistent failure must stay visible, boundedly"
        )

    def test_recovery_re_arms_the_loud_report(
        self, worker, np_module, monkeypatch
    ):
        instance, backend, buffer = worker
        monkeypatch.delattr(
            "widgets.spotify_visualizer.audio_worker.time", raising=True
        )
        backend.deliver(_block(np_module))
        assert instance._capture_callback_failures == 1

        monkeypatch.undo()
        backend.deliver(_block(np_module))
        assert buffer.consume_latest() is not None
        assert instance._capture_callback_failures == 0

    def test_no_restart_loop_is_used_as_a_substitute(self, worker, np_module, monkeypatch):
        """Observability only: a broken callback must not bounce the stream."""
        _instance, backend, _buffer = worker
        monkeypatch.delattr(
            "widgets.spotify_visualizer.audio_worker.time", raising=True
        )
        for _ in range(50):
            backend.deliver(_block(np_module))
        assert backend.start_calls == 1, "the failure path restarted capture"
