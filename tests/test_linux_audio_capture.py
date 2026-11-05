"""Linux visualizer capture: default-sink monitor via parec, never the microphone."""
from __future__ import annotations

import io
import threading
import time

import numpy as np
import pytest

from utils import audio_capture, audio_capture_pulse
from utils.audio_capture import AudioCaptureConfig


class _FakeProcess:
    def __init__(self, payload: bytes):
        self.stdout = io.BytesIO(payload)
        self.stderr = io.BytesIO(b"")
        self.terminated = False

    def poll(self):
        return 0 if self.terminated else None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.terminated = True


def test_reader_slices_parec_pcm_into_float32_blocks_from_the_default_monitor(monkeypatch) -> None:
    frames = np.arange(2 * 64 * 2, dtype="<f4").reshape(-1, 2)  # two 64-frame stereo blocks
    commands = []

    def popen(command, **kwargs):
        commands.append(command)
        return _FakeProcess(frames.tobytes())

    monkeypatch.setattr(audio_capture_pulse, "default_monitor_source", lambda: "alsa_output.speakers.monitor")
    monkeypatch.setattr(audio_capture_pulse.subprocess, "Popen", popen)
    backend = audio_capture_pulse.PulseMonitorBackend(AudioCaptureConfig(sample_rate=48000, channels=2, block_size=64))
    received, done = [], threading.Event()

    def on_block(block):
        received.append(block.copy())
        if len(received) == 2:
            done.set()

    assert backend.start(on_block) is True
    assert done.wait(2.0)
    assert "--device=alsa_output.speakers.monitor" in commands[0] and "--format=float32le" in commands[0]
    assert all(block.shape == (64, 2) and block.dtype == np.float32 for block in received)
    np.testing.assert_array_equal(np.concatenate(received), frames)
    deadline = time.monotonic() + 2.0
    while backend.is_running() and time.monotonic() < deadline:  # stdout ended -> loud failure state
        time.sleep(0.01)
    backend.stop()
    assert backend.capture_state() is audio_capture.CaptureState.STOPPED


def test_linux_factory_uses_the_monitor_backend_or_none_loudly(monkeypatch) -> None:
    monkeypatch.setattr(audio_capture.platform, "system", lambda: "Linux")
    monkeypatch.setattr(audio_capture.sys, "platform", "linux")
    monkeypatch.setattr(audio_capture_pulse.shutil, "which", lambda tool: f"/usr/bin/{tool}")
    assert isinstance(audio_capture.create_audio_capture(), audio_capture_pulse.PulseMonitorBackend)

    monkeypatch.setattr(audio_capture_pulse.shutil, "which", lambda tool: None)
    monkeypatch.setattr(audio_capture_pulse, "_UNAVAILABLE_ANNOUNCED", False)
    warnings = []
    monkeypatch.setattr(audio_capture_pulse.logger, "warning", lambda message, *args: warnings.append(message % args))
    assert audio_capture.create_audio_capture() is None
    assert warnings and "[PLATFORM]" in warnings[0] and "pulseaudio-utils" in warnings[0]
