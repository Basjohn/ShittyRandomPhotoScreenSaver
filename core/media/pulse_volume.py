"""Linux volume owners over PulseAudio/PipeWire (``pactl``), mirroring the Windows pycaw ones.

* ``PulseSystemVolumeProbe`` has the ``CoreAudioCallbackProbe`` contract used by
  ``CoreAudioEventSession`` (system volume/mute OSD and the mute button): one
  ``pactl subscribe`` sidecar reports default-sink and server changes from its
  reader thread; ``snapshot()`` returns the cached latest value, so the GUI thread
  never spawns a process to read; only an explicit user set runs ``pactl``.
* ``PulseAppVolumeController`` has the ``SpotifyVolumeController`` contract for the
  media widget's app slider: the provider's process identities (``spotify.exe`` ->
  ``spotify``) select a sink input by ``application.process.binary``.

All ``pactl`` children run with ``LC_ALL=C`` so their text output is parseable
(a child-process locale, not SRPSS configuration). Requires ``pulseaudio-utils``
(PipeWire serves the same commands through pipewire-pulse).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from typing import Callable, Optional

from core.logging.logger import get_logger
from core.media.provider_registry import (
    get_provider_process_exe_name_for_source,
    get_provider_process_exe_names,
    normalize_provider_id,
)

logger = get_logger(__name__)

PA_VOLUME_NORM = 65536
_RAW_VOLUME = re.compile(r"(\d+)\s*/\s*\d+%")
# Linux process names of the registry's Windows executables, where they differ.
_PROCESS_ALIASES = {
    "chrome": ("chrome", "chromium", "chromium-browser", "google-chrome"),
    "msedge": ("msedge", "microsoft-edge"),
}


def _child_env() -> dict[str, str]:
    return {**os.environ, "LC_ALL": "C"}


def pactl(*args: str, timeout: float = 3.0) -> Optional[str]:
    """Run one ``pactl`` command; return stdout, or None on failure (logged at DEBUG)."""

    try:
        result = subprocess.run(["pactl", *args], capture_output=True, text=True, timeout=timeout, env=_child_env())
    except Exception:
        logger.debug("[PULSE] pactl %s failed", " ".join(args), exc_info=True)
        return None
    if result.returncode != 0:
        logger.debug("[PULSE] pactl %s exited %s: %s", " ".join(args), result.returncode, result.stderr.strip())
        return None
    return result.stdout


def parse_volume_fraction(text: str) -> Optional[float]:
    """Average channel volume from ``pactl`` volume text, as a [0, 1] fraction."""

    raw = [int(value) for value in _RAW_VOLUME.findall(text or "")]
    if not raw:
        return None
    return max(0.0, min(1.0, sum(raw) / len(raw) / PA_VOLUME_NORM))


def pactl_available() -> bool:
    return shutil.which("pactl") is not None


def _default_sink_state() -> Optional[tuple[str, float, bool]]:
    sink = (pactl("get-default-sink") or "").strip()
    volume = parse_volume_fraction(pactl("get-sink-volume", "@DEFAULT_SINK@") or "")
    mute = (pactl("get-sink-mute", "@DEFAULT_SINK@") or "").strip().casefold()
    if not sink or volume is None or not mute.startswith("mute:"):
        return None
    return sink, volume, mute.endswith("yes")


class PulseSystemVolumeProbe:
    """``CoreAudioCallbackProbe`` contract on PulseAudio/PipeWire."""

    def __init__(self, *, on_volume: Callable[[float, bool], None], on_default_device: Callable[[], None]) -> None:
        self._thread = threading.get_ident()
        self._on_volume = on_volume
        self._on_device = on_default_device
        self._process: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._state: Optional[tuple[str, float, bool]] = None
        self._lock = threading.Lock()
        self._active = False

    def _assert_owner(self) -> None:
        if threading.get_ident() != self._thread:
            raise RuntimeError("Pulse volume registration/teardown require the owning thread")

    def start(self) -> bool:
        self._assert_owner()
        if self._process is not None:
            return True
        if not pactl_available():
            return False
        state = _default_sink_state()
        if state is None:
            return False
        try:
            process = subprocess.Popen(["pactl", "subscribe"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                       text=True, env=_child_env())
        except Exception:
            logger.debug("[PULSE] pactl subscribe could not start", exc_info=True)
            return False
        with self._lock:
            self._state = state
        self._process, self._active = process, True
        self._reader = threading.Thread(target=self._read, args=(process,), name="srpss-pactl-subscribe", daemon=True)
        self._reader.start()
        return True

    def _read(self, process: subprocess.Popen) -> None:
        for line in process.stdout or ():
            if not self._active:
                break
            if " on sink #" not in line and " on server" not in line:
                continue
            state = _default_sink_state()
            if state is None or not self._active:
                continue
            with self._lock:
                previous, self._state = self._state, state
            try:
                if previous is not None and previous[0] != state[0]:
                    self._on_device()
                elif previous is None or previous[1:] != state[1:]:
                    self._on_volume(state[1], state[2])
            except Exception:
                pass  # Like the COM callback: nothing escapes into the transport thread.

    def snapshot(self) -> tuple[float, bool] | None:
        self._assert_owner()
        with self._lock:
            state = self._state
        return None if state is None else (state[1], state[2])

    def set_mute(self, muted: bool) -> bool:
        self._assert_owner()
        if not self._active or pactl("set-sink-mute", "@DEFAULT_SINK@", "1" if muted else "0") is None:
            return False
        with self._lock:
            if self._state is not None:
                self._state = (self._state[0], self._state[1], bool(muted))
        return True

    def set_volume(self, level: float) -> bool:
        self._assert_owner()
        target = float(level)
        if not 0.0 <= target <= 1.0:
            raise ValueError("master volume must be in [0.0, 1.0]")
        if not self._active or pactl("set-sink-volume", "@DEFAULT_SINK@", str(round(target * PA_VOLUME_NORM))) is None:
            return False
        with self._lock:
            if self._state is not None:
                self._state = (self._state[0], target, self._state[2])
        return True

    def rebind(self) -> bool:
        self._assert_owner()
        self.stop()
        return self.start()

    def stop(self) -> None:
        self._assert_owner()
        self._active = False
        process, reader = self._process, self._reader
        self._process = self._reader = None
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
            if process.stdout is not None:
                process.stdout.close()
        if reader is not None:
            reader.join(timeout=3)


def _sink_inputs() -> list[tuple[int, str, Optional[float]]]:
    """Return (index, process binary, volume fraction) for each playing stream."""

    text = pactl("list", "sink-inputs") or ""
    inputs = []
    for block in text.split("Sink Input #")[1:]:
        index = int(block.split(None, 1)[0])
        binary = re.search(r'application\.process\.binary = "([^"]*)"', block)
        volume_line = re.search(r"^\s*Volume:(.*)$", block, re.MULTILINE)
        inputs.append((index, (binary.group(1) if binary else "").casefold(),
                       parse_volume_fraction(volume_line.group(1)) if volume_line else None))
    return inputs


class PulseAppVolumeController:
    """``SpotifyVolumeController`` contract on PulseAudio/PipeWire sink inputs."""

    def __init__(self, provider: str = "spotify") -> None:
        self._available = pactl_available()
        self._provider = ""
        self._process_targets: tuple[str, ...] = ()
        self.configure_volume_target(provider)
        if not self._available:
            logger.info("[SPOTIFY_VOL] pactl not available; app volume control disabled (provider=%s)", provider)

    @property
    def process_targets(self) -> tuple[str, ...]:
        return self._process_targets

    def is_available(self) -> bool:
        return self._available

    def configure_volume_target(self, provider: object, source_app_user_model_id: object = "") -> bool:
        provider_id = normalize_provider_id(provider)
        targets: tuple[str, ...] = ()
        if provider_id == "spotify_browser":
            browser = get_provider_process_exe_name_for_source(provider_id, source_app_user_model_id)
            if browser is not None:
                targets = ("spotify.exe", browser)
        elif provider_id is not None:
            targets = tuple(get_provider_process_exe_names(provider_id))
        names: list[str] = []
        for target in targets:
            base = target.strip().casefold().removesuffix(".exe")
            names.extend(_PROCESS_ALIASES.get(base, (base,)))
        self._provider = provider_id or str(provider or "").strip()
        self._process_targets = tuple(dict.fromkeys(name for name in names if name))
        return bool(self._process_targets)

    def _target_input(self) -> Optional[tuple[int, Optional[float]]]:
        if not self._available or not self._process_targets:
            return None
        inputs = _sink_inputs()
        for target in self._process_targets:  # target priority is authoritative
            for index, binary, volume in inputs:
                if binary == target:
                    return index, volume
        return None

    def get_volume(self) -> Optional[float]:
        found = self._target_input()
        return None if found is None else found[1]

    def set_volume(self, level: float) -> bool:
        found = self._target_input()
        if found is None:
            return False
        clamped = max(0.0, min(1.0, float(level)))
        return pactl("set-sink-input-volume", str(found[0]), str(round(clamped * PA_VOLUME_NORM))) is not None


__all__ = ["PulseAppVolumeController", "PulseSystemVolumeProbe", "pactl", "parse_volume_fraction"]
