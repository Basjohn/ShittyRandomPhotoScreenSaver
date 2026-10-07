"""The authored block request reaches the actual native backend once."""

import sys
from types import SimpleNamespace

import pytest

from utils.audio_capture import AudioCaptureConfig, PyAudioWPatchBackend


@pytest.mark.parametrize("requested", [0, 128, 256, 512, 1024])
def test_actual_native_open_uses_exact_authored_or_driver_auto_size(monkeypatch, requested):
    opens = []
    stream = SimpleNamespace(start_stream=lambda: None)
    pa = SimpleNamespace(open=lambda **kwargs: opens.append(kwargs) or stream)
    monkeypatch.setitem(sys.modules, "pyaudiowpatch", SimpleNamespace(PyAudio=lambda: pa, paFloat32=1))
    monkeypatch.setattr("utils.audio_capture.platform.system", lambda: "Windows")
    backend = PyAudioWPatchBackend(AudioCaptureConfig(block_size=requested))
    monkeypatch.setattr(backend, "_find_loopback_device", lambda _: {
        "maxInputChannels": 2, "defaultSampleRate": 48000, "index": 1,
    })
    assert backend.start(lambda _: None) is True
    assert len(opens) == 1
    assert opens[0]["frames_per_buffer"] == requested
    assert backend._negotiated_block_size == requested


def test_failed_requested_native_open_is_loud_and_does_not_try_another_size(monkeypatch, caplog):
    opens = []
    terminated = []

    def fail_open(**kwargs):
        opens.append(kwargs)
        raise RuntimeError("requested native block unsupported")

    pa = SimpleNamespace(open=fail_open, terminate=lambda: terminated.append(True))
    monkeypatch.setitem(sys.modules, "pyaudiowpatch", SimpleNamespace(PyAudio=lambda: pa, paFloat32=1))
    monkeypatch.setattr("utils.audio_capture.platform.system", lambda: "Windows")
    backend = PyAudioWPatchBackend(AudioCaptureConfig(block_size=512))
    monkeypatch.setattr(backend, "_find_loopback_device", lambda _: {
        "maxInputChannels": 2, "defaultSampleRate": 48000, "index": 1,
    })
    assert backend.start(lambda _: None) is False
    assert len(opens) == 1
    assert opens[0]["frames_per_buffer"] == 512
    assert terminated == [True]
    assert backend._stream is None
    assert backend._pa is None
    assert any(record.levelname == "ERROR" and "stream open failed" in record.message for record in caplog.records)
