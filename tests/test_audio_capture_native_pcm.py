"""Selected native capture rejects malformed metadata/PCM without substitution."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np
import pytest

from core.threading.manager import ThreadManager
from utils.audio_capture import AudioCaptureConfig, CaptureState, PyAudioWPatchBackend, SounddeviceBackend
from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker


def _selected_backend(monkeypatch, backend_type, *, metadata=None, early_pcm=None):
    opens = []
    callbacks = []
    released = []
    if metadata is None:
        metadata = (
            {"maxInputChannels": 2, "defaultSampleRate": 48000, "index": 1}
            if backend_type is PyAudioWPatchBackend else
            {"max_input_channels": 2, "default_samplerate": 48000, "index": 1}
        )
    stream = SimpleNamespace(
        start_stream=lambda: None, start=lambda: None,
        stop_stream=lambda: released.append("stop"), stop=lambda: released.append("stop"),
        close=lambda: released.append("close"),
    )

    def open_stream(**kwargs):
        opens.append(kwargs)
        callback = kwargs.get("stream_callback", kwargs.get("callback"))
        callbacks.append(callback)
        if early_pcm is not None:
            callback(early_pcm, 2, None, None)
        return stream

    if backend_type is PyAudioWPatchBackend:
        pa = SimpleNamespace(open=open_stream, terminate=lambda: released.append("terminate"))
        monkeypatch.setitem(sys.modules, "pyaudiowpatch", SimpleNamespace(
            PyAudio=lambda: pa, paFloat32=1, paContinue=0,
        ))
        monkeypatch.setattr("utils.audio_capture.platform.system", lambda: "Windows")
        backend = backend_type(AudioCaptureConfig())
        monkeypatch.setattr(backend, "_find_loopback_device", lambda _: metadata)
    else:
        monkeypatch.setitem(sys.modules, "sounddevice", SimpleNamespace(InputStream=open_stream))
        backend = backend_type(AudioCaptureConfig())
        monkeypatch.setattr(backend, "_find_wasapi_loopback_device", lambda: metadata)
    return backend, opens, callbacks, released


@pytest.mark.parametrize("backend_type", [PyAudioWPatchBackend, SounddeviceBackend])
@pytest.mark.parametrize("field,value", [
    ("channels", 0), ("channels", -1), ("channels", "invalid"),
    ("sample_rate", 0), ("sample_rate", None), ("sample_rate", "missing"),
])
def test_selected_invalid_metadata_is_loud_and_never_opens_assumed_format(
    monkeypatch, caplog, backend_type, field, value
):
    channel_key, rate_key = (
        ("maxInputChannels", "defaultSampleRate") if backend_type is PyAudioWPatchBackend
        else ("max_input_channels", "default_samplerate")
    )
    metadata = {channel_key: 2, rate_key: 48000, "index": 1}
    key = channel_key if field == "channels" else rate_key
    if value == "missing":
        del metadata[key]
    else:
        metadata[key] = value
    backend, opens, _callbacks, released = _selected_backend(
        monkeypatch, backend_type, metadata=metadata
    )
    assert backend.start(lambda _: pytest.fail("invalid device delivered PCM")) is False
    assert not opens
    assert backend.capture_state() is CaptureState.FAILED
    assert any(record.levelname == "ERROR" and "metadata" in record.message for record in caplog.records)
    assert released == (["terminate"] if backend_type is PyAudioWPatchBackend else [])


@pytest.mark.parametrize("backend_type", [PyAudioWPatchBackend, SounddeviceBackend])
def test_native_bad_packets_are_bounded_rejected_before_health_and_valid_pcm_recovers(
    monkeypatch, caplog, backend_type
):
    backend, _opens, callbacks, _released = _selected_backend(monkeypatch, backend_type)
    received = []
    assert backend.start(received.append) is True
    invalid = b"bad" if backend_type is PyAudioWPatchBackend else np.ones((2, 2), dtype="int16")
    for _ in range(50):
        callbacks[0](invalid, 2, None, None)
    assert received == []
    assert backend._last_callback_ts == 0.0
    assert backend._native_callback_failures == 50
    assert backend.is_healthy() is False
    errors = [record for record in caplog.records if record.levelname == "ERROR"]
    assert len(errors) == 1
    valid = np.asarray([[0.25, -0.25], [0.5, -0.5]], dtype="float32")
    callbacks[0](valid.tobytes() if backend_type is PyAudioWPatchBackend else valid, 2, None, None)
    assert backend.is_healthy() is True
    assert backend._native_callback_failures == 0
    assert len(received) == 1
    np.testing.assert_array_equal(received[0], valid)
    callbacks[0](invalid, 2, None, None)
    assert len([record for record in caplog.records if record.levelname == "ERROR"]) == 2
    backend.stop()


@pytest.mark.parametrize("backend_type", [PyAudioWPatchBackend, SounddeviceBackend])
def test_callback_during_native_open_keeps_first_valid_health_observation(monkeypatch, backend_type):
    pcm = np.ones((2, 2), dtype="float32")
    backend, _opens, _callbacks, _released = _selected_backend(
        monkeypatch, backend_type,
        early_pcm=pcm.tobytes() if backend_type is PyAudioWPatchBackend else pcm,
    )
    received = []
    assert backend.start(received.append) is True
    assert backend.is_healthy() is True
    assert backend.is_capture_starting() is False
    assert len(received) == 1
    backend.stop()


@pytest.mark.parametrize("advisory_frame_count", [1, 2, 4, 4096])
def test_pyaudio_valid_float32_payload_uses_actual_channel_framing_not_advisory_frame_count(
    monkeypatch, advisory_frame_count
):
    """R-108: callback metadata must never become a second PCM-shape authority.

    The native packet contains three stereo frames.  Deliberately lie in both
    directions through PortAudio's advisory frame_count and prove the exact
    delivered float32 payload still crosses the native boundary unchanged.
    """
    backend, _opens, callbacks, _released = _selected_backend(monkeypatch, PyAudioWPatchBackend)
    received = []
    assert backend.start(received.append) is True
    pcm = np.arange(6, dtype="float32").reshape(3, 2)
    callbacks[0](pcm.tobytes(), advisory_frame_count, None, None)
    assert len(received) == 1
    np.testing.assert_array_equal(received[0], pcm)
    assert backend.is_healthy() is True
    assert backend._native_callback_failures == 0
    backend.stop()


def test_sounddevice_native_shape_mismatch_never_flattens_or_changes_channel_meaning(monkeypatch):
    backend, _opens, callbacks, _released = _selected_backend(monkeypatch, SounddeviceBackend)
    received = []
    assert backend.start(received.append) is True
    pcm = np.ones((2, 3), dtype="float32")
    callbacks[0](pcm, 2, None, None)
    assert received == []
    assert backend._last_callback_ts == 0.0
    assert backend._native_callback_failures == 1
    backend.stop()


def test_actual_windows_native_pcm_rejection_and_recovery_cross_worker_publication(monkeypatch):
    backend, _opens, callbacks, _released = _selected_backend(monkeypatch, PyAudioWPatchBackend)
    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", lambda _: backend)
    manager = ThreadManager()
    lane = manager.create_affinity_lane(
        lane_id="test.capture.native_pcm", category="visualizer.audio_capture", worker="audio_capture_test",
    )
    worker = SpotifyVisualizerAudioWorker(4)
    worker.set_capture_lane(lane)
    worker.set_audio_block_size(1024)
    try:
        worker.start()
        lane.call(lambda: None, timeout=1.0)
        callbacks[0](np.ones(3, dtype="float32").tobytes(), 2, None, None)
        assert worker._buffer.consume_latest() is None
        assert worker.is_capture_healthy() is False
        valid = np.asarray([[0.2, 0.4], [0.3, 0.5]], dtype="float32")
        callbacks[0](valid.tobytes(), 2, None, None)
        frame = worker._buffer.consume_latest()
        assert frame is not None
        np.testing.assert_allclose(frame.samples, [0.3, 0.4])
        assert worker.is_capture_healthy() is True
        assert backend._native_callback_failures == 0
    finally:
        worker.stop()
        assert lane.stop(wait=True, timeout=1.0) is True
        assert manager.shutdown(wait=True, timeout=1.0) is True


@pytest.mark.parametrize("matched", [False, True])
def test_selected_default_output_never_substitutes_first_unrelated_loopback(monkeypatch, caplog, matched):
    opens = []
    released = []
    unrelated = {"name": "Unrelated Output [Loopback]", "index": 20,
                 "maxInputChannels": 2, "defaultSampleRate": 44100}
    selected = {"name": "Default Speakers [Loopback]", "index": 30,
                "maxInputChannels": 2, "defaultSampleRate": 48000}
    default_output = {"name": "Default Speakers", "index": 10}
    stream = SimpleNamespace(
        start_stream=lambda: None, stop_stream=lambda: released.append("stop"),
        close=lambda: released.append("close"),
    )
    pa = SimpleNamespace(
        get_host_api_info_by_type=lambda _: {"defaultOutputDevice": 10},
        get_device_info_by_index=lambda _: default_output,
        get_loopback_device_info_generator=lambda: iter([unrelated, selected] if matched else [unrelated]),
        open=lambda **kwargs: opens.append(kwargs) or stream,
        terminate=lambda: released.append("terminate"),
    )
    monkeypatch.setitem(sys.modules, "pyaudiowpatch", SimpleNamespace(
        PyAudio=lambda: pa, paFloat32=1, paContinue=0, paWASAPI=13,
    ))
    monkeypatch.setattr("utils.audio_capture.platform.system", lambda: "Windows")
    backend = PyAudioWPatchBackend(AudioCaptureConfig(block_size=512))
    assert backend.start(lambda _: None) is matched
    if matched:
        assert len(opens) == 1
        assert opens[0]["input_device_index"] == 30
        assert opens[0]["rate"] == 48000
        backend.stop()
        assert released == ["stop", "close", "terminate"]
    else:
        assert opens == []
        assert backend._stream is None
        assert backend._pa is None
        assert backend.capture_state() is CaptureState.FAILED
        assert released == ["terminate"]
        assert any(record.levelname == "ERROR" and "No WASAPI loopback matches" in record.message for record in caplog.records)
