"""Native close failure must retain handles and reach capture-lane accounting."""

from __future__ import annotations

import pytest
import sys
from types import SimpleNamespace
import gc
import threading
import weakref

from core.threading.manager import ThreadManager
from utils.audio_capture import AudioCaptureConfig, CaptureState, PyAudioWPatchBackend, SounddeviceBackend
from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker
from widgets.spotify_visualizer.beat_engine import BeatEngineRegistry


class _Stream:
    def __init__(self, failure=None):
        self.failure = failure
        self.stop_calls = 0
        self.close_calls = 0

    def stop(self):
        self.stop_calls += 1
        if self.failure == "stop":
            raise RuntimeError("injected native stop failure")

    stop_stream = stop

    def start_stream(self):
        raise RuntimeError("injected partial stream open failure")

    def close(self):
        self.close_calls += 1
        if self.failure == "close":
            raise RuntimeError("injected native close failure")


class _PyAudio:
    def __init__(self, failure=None):
        self.failure = failure
        self.terminate_calls = 0

    def terminate(self):
        self.terminate_calls += 1
        if self.failure == "terminate":
            raise RuntimeError("injected native terminate failure")


def _native_handles(backend, failure):
    stream = _Stream(failure)
    pa = _PyAudio(failure)
    backend._stream = stream
    if isinstance(backend, PyAudioWPatchBackend):
        backend._pa = pa
    backend._running = True
    backend._negotiated_block_size = 512
    backend._note_capture_starting()
    return stream, pa


@pytest.mark.parametrize("backend_type,failure", [
    (PyAudioWPatchBackend, "stop"), (PyAudioWPatchBackend, "close"),
    (PyAudioWPatchBackend, "terminate"),
    (SounddeviceBackend, "stop"), (SounddeviceBackend, "close"),
])
def test_native_release_failure_is_loud_retains_handles_and_never_retries(backend_type, failure, caplog):
    backend = backend_type(AudioCaptureConfig())
    stream, pa = _native_handles(backend, failure)
    with pytest.raises(RuntimeError, match="injected native"):
        backend.stop()
    assert backend.capture_state() is CaptureState.FAILED
    assert backend._stream is (None if failure == "terminate" else stream)
    if isinstance(backend, PyAudioWPatchBackend):
        assert backend._pa is pa
    assert any(record.levelname == "ERROR" and "handles are retained" in record.message for record in caplog.records)
    counts = stream.stop_calls, stream.close_calls, pa.terminate_calls
    for action in (backend.stop, backend.restart, lambda: backend.start(lambda _: None)):
        with pytest.raises(RuntimeError, match="native release previously failed"):
            action()
    assert (stream.stop_calls, stream.close_calls, pa.terminate_calls) == counts


@pytest.mark.parametrize("backend_type", [PyAudioWPatchBackend, SounddeviceBackend])
def test_successful_native_release_clears_handles_once(backend_type):
    backend = backend_type(AudioCaptureConfig())
    stream, pa = _native_handles(backend, None)
    backend.stop()
    backend.stop()
    assert backend._stream is None
    assert stream.stop_calls == 1
    assert stream.close_calls == 1
    if isinstance(backend, PyAudioWPatchBackend):
        assert backend._pa is None
        assert pa.terminate_calls == 1
    assert backend.capture_state() is CaptureState.STOPPED
    assert backend._negotiated_block_size == 0


@pytest.mark.parametrize("failure", ["stop", "close", "terminate"])
def test_actual_windows_failed_open_cleanup_retains_debt_without_another_open(monkeypatch, failure):
    stream = _Stream(failure)
    pa = _PyAudio(failure)
    opens = []

    def open_stream(**kwargs):
        opens.append(kwargs)
        return stream

    pa.open = open_stream
    monkeypatch.setitem(sys.modules, "pyaudiowpatch", SimpleNamespace(PyAudio=lambda: pa, paFloat32=1))
    monkeypatch.setattr("utils.audio_capture.platform.system", lambda: "Windows")
    backend = PyAudioWPatchBackend(AudioCaptureConfig(block_size=512))
    monkeypatch.setattr(backend, "_find_loopback_device", lambda _: {
        "maxInputChannels": 2, "defaultSampleRate": 48000, "index": 1,
    })
    with pytest.raises(RuntimeError, match="injected native"):
        backend.start(lambda _: None)
    assert len(opens) == 1
    assert backend.capture_state() is CaptureState.FAILED
    assert backend._stream is (None if failure == "terminate" else stream)
    assert backend._pa is pa
    counts = stream.stop_calls, stream.close_calls, pa.terminate_calls
    with pytest.raises(RuntimeError, match="native release previously failed"):
        backend.stop()
    assert (stream.stop_calls, stream.close_calls, pa.terminate_calls) == counts


@pytest.mark.parametrize("operation", ["stop", "restart"])
@pytest.mark.parametrize("failure", ["stop", "close", "terminate"])
def test_windows_native_release_failure_reaches_worker_and_manager_without_retry(
    monkeypatch, operation, failure
):
    backend = PyAudioWPatchBackend(AudioCaptureConfig())
    handles = []

    def start_stream(callback):
        backend._callback = callback
        handles.append(_native_handles(backend, failure))
        return True

    monkeypatch.setattr(backend, "_start_stream", start_stream)
    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", lambda _: backend)
    manager = ThreadManager()
    lane = manager.create_affinity_lane(
        lane_id="test.capture.native_release", category="visualizer.audio_capture", worker="audio_capture_test",
    )
    worker = SpotifyVisualizerAudioWorker(4)
    worker.set_capture_lane(lane)
    worker.set_audio_block_size(1024)
    worker.start()
    lane.call(lambda: None, timeout=1.0)
    if operation == "stop":
        worker.stop()
    else:
        assert worker.restart_capture() is True
    assert lane.stop(wait=True, timeout=1.0) is False
    assert manager.shutdown(wait=True, timeout=1.0) is False
    assert lane.diagnostic_snapshot()["resource_held"] is True
    assert worker._backend is backend
    assert worker.has_capture_owner_work() is True
    assert backend.capture_state() is CaptureState.FAILED
    assert len(handles) == 1
    stream, pa = handles[0]
    assert stream.stop_calls == 1

    assert stream.close_calls == (0 if failure == "stop" else 1)
    assert pa.terminate_calls == (1 if failure == "terminate" else 0)
    assert backend._pa is pa
    assert backend._stream is (None if failure == "terminate" else stream)
    with pytest.raises(RuntimeError, match="admission is closed"):
        worker.start()
    assert manager.shutdown(wait=True, timeout=1.0) is False
    assert stream.stop_calls == 1


@pytest.mark.parametrize("failure", [None, "close"])
def test_registry_retains_actual_native_owner_born_after_terminal_stop(monkeypatch, failure):
    entered = threading.Event()
    release = threading.Event()
    backend = PyAudioWPatchBackend(AudioCaptureConfig())
    handles = []

    def start_stream(callback):
        entered.set()
        assert release.wait(2.0)
        # The native handles become real after terminal clear already fenced
        # admission. The existing capture drain must close or retain them.
        backend._callback = callback
        handles.append(_native_handles(backend, failure))
        return True

    monkeypatch.setattr(backend, "_start_stream", start_stream)
    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", lambda _: backend)
    registry = BeatEngineRegistry()
    manager = ThreadManager()
    engine = registry.get_engine(4)
    engine._audio_worker.set_audio_block_size(1024)
    engine.set_thread_manager(manager)
    engine.ensure_started()
    assert entered.wait(1.0)
    lane = engine._capture_lane
    engine_ref = weakref.ref(engine)
    worker_ref = weakref.ref(engine._audio_worker)
    try:
        assert registry.clear() is False
        del engine
        gc.collect()
        assert engine_ref() is registry._engine
        assert worker_ref() is not None
        release.set()
        assert lane.stop(wait=True, timeout=1.0) is (failure is None)
        assert registry.clear() is (failure is None)
        assert manager.shutdown(wait=True, timeout=1.0) is (failure is None)
        if failure is not None:
            gc.collect()
            assert registry.get_engine(4) is engine_ref()
            assert worker_ref()._backend is backend
            assert backend._stream is handles[0][0]
            assert handles[0][0].close_calls == 1
        else:
            assert registry._engine is None
            assert backend._stream is None
            assert backend._pa is None
    finally:
        release.set()
        manager.shutdown(wait=True, timeout=2.0)
