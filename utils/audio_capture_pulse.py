"""Linux system-audio capture: the default sink's monitor through a ``parec`` sidecar.

The visualizer needs what the system is *playing*, the counterpart of Windows
WASAPI loopback. On Linux that is the PulseAudio/PipeWire monitor source of the
default output sink (``<sink>.monitor``). PortAudio cannot address monitor sources,
so its default input would be the microphone; this backend never falls back to it.

Sidecar: ``parec`` (``pulseaudio-utils``; PipeWire serves it through pipewire-pulse)
streams raw float32 PCM from the monitor on stdout; a reader thread owned by the
backend slices it into ``block_size`` frames and hands ``(frames, channels)`` float32
arrays to the callback, exactly like the sounddevice backend. The sink is resolved
with ``pactl get-default-sink`` at each (re)start, so a restart follows a changed
output device. Missing tools make the factory return ``None`` with one loud
``[PLATFORM]`` warning naming the package.
"""
from __future__ import annotations

import shutil
import subprocess
import threading
from typing import Any, Callable, Optional

from core.logging.logger import get_logger
from utils.audio_capture import AudioCaptureBackend, AudioCaptureConfig

logger = get_logger(__name__)

_TOOLS = ("parec", "pactl")


def default_monitor_source() -> str:
    """Return ``<default sink>.monitor`` as reported by the sound server."""

    result = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True, timeout=5)
    sink = result.stdout.strip()
    if result.returncode != 0 or not sink:
        raise RuntimeError(f"pactl get-default-sink failed: {result.stderr.strip() or result.returncode}")
    return f"{sink}.monitor"


class PulseMonitorBackend(AudioCaptureBackend):
    """Default-sink monitor capture through a ``parec`` child process."""

    def __init__(self, config: AudioCaptureConfig | None = None):
        self._config = config or AudioCaptureConfig()
        self._sample_rate = int(self._config.sample_rate)
        self._channels = int(self._config.channels)
        self._process: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._running = False
        self._callback: Optional[Callable[[Any], None]] = None
        self._source = ""

    def start(self, callback: Callable[[Any], None]) -> bool:
        self._check_native_release_failure()
        if self._running:
            return True
        self._callback = callback
        started = self._start_process(callback)
        if not started:
            self._note_capture_failed()
        return started

    def _start_process(self, callback: Callable[[Any], None]) -> bool:
        import numpy as np

        try:
            self._source = default_monitor_source()
        except Exception:
            logger.exception("[AUDIO] Default sink monitor could not be resolved; capture start rejected")
            return False
        frame_bytes = 4 * self._channels
        block = max(64, int(self._config.block_size or 512))
        command = [
            "parec", f"--device={self._source}", "--raw", "--format=float32le",
            f"--rate={self._sample_rate}", f"--channels={self._channels}",
            f"--latency={block * frame_bytes}",
        ]
        try:
            self._note_capture_starting()
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        except Exception:
            logger.exception("[AUDIO] parec could not be started")
            return False
        self._process = process
        self._running = True
        chunk = block * frame_bytes

        def _read() -> None:
            stream = process.stdout
            pending = b""
            while self._running:
                data = stream.read(chunk - len(pending)) if stream is not None else b""
                if not data:
                    break
                pending += data
                if len(pending) < chunk:
                    continue
                try:
                    frames = np.frombuffer(pending, dtype="<f4").reshape(-1, self._channels).astype(np.float32, copy=False)
                    callback(frames)
                    self._note_capture_callback()
                    self._note_native_callback_recovered()
                except Exception:
                    self._report_native_callback_failure()
                pending = b""
            if self._running:
                error = process.stderr.read().decode(errors="replace").strip() if process.stderr else ""
                logger.error("[AUDIO] parec stopped unexpectedly (code=%s) %s", process.poll(), error[:300])
                self._running = False
                self._note_capture_failed()

        self._reader = threading.Thread(target=_read, name="srpss-parec-reader", daemon=True)
        self._reader.start()
        logger.info(
            "[AUDIO] Linux monitor capture started (source=%s, block=%d, rate=%dHz, channels=%d)",
            self._source, block, self._sample_rate, self._channels,
        )
        return True

    def stop(self) -> None:
        self._running = False
        self._check_native_release_failure()
        process, reader = self._process, self._reader
        self._process = self._reader = None
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            for pipe in (process.stdout, process.stderr):
                if pipe is not None:
                    pipe.close()
        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=3)
        self._note_capture_stopped()

    def is_running(self) -> bool:
        return self._running

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def channels(self) -> int:
        return self._channels

    def restart(self) -> bool:
        self.stop()
        if self._callback is not None:
            return self.start(self._callback)
        return False


_UNAVAILABLE_ANNOUNCED = False


def create_pulse_monitor_backend(config: AudioCaptureConfig | None = None) -> PulseMonitorBackend | None:
    missing = [tool for tool in _TOOLS if shutil.which(tool) is None]
    if not missing:
        return PulseMonitorBackend(config)
    global _UNAVAILABLE_ANNOUNCED
    if not _UNAVAILABLE_ANNOUNCED:
        _UNAVAILABLE_ANNOUNCED = True
        logger.warning(
            "[PLATFORM] Visualizer audio capture needs %s (package pulseaudio-utils; works with PipeWire); "
            "no system audio will be captured",
            " and ".join(missing),
        )
    return None


__all__ = ["PulseMonitorBackend", "create_pulse_monitor_backend", "default_monitor_source"]
