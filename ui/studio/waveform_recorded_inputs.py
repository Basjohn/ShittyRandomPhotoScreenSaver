"""Recorded clip -> the exact Waveform frame-runtime inputs, via the production replay analysis.

Runs in a *separate process* (``python -m ui.studio.waveform_recorded_inputs``): the
production replay patches process clocks/RNG deterministically and builds its own
runtime controller and ``ReplayBeatEngine`` (inert, no audio capture). Doing that
inside the running app could disturb a live visualizer, so the Studio never does.

The production logical mode is driven through the production-owned offline replay
(``widgets.spotify_visualizer.feature_replay``: ``ReplayBeatEngine`` + ``PcmReanalysis``
+ ``logical_tick``, as ``tools/visualizer_replay/waveform_ribbon_motion_audit.py`` drives
it; production never imports ``tools``); every keyword input the mode's capture passes to
``WaveformRibbonFrameRuntime.advance`` is recorded, together with the packet hash
the production path produced, so the Studio's own evaluator can be proven to
reproduce it byte for byte.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[2]
# The Studio analyses the opening of a recording (original timestamps and pre-roll kept): a full
# multi-minute replay through the production analysis takes minutes.
CLIP_SECONDS = 30.0


# The shipped clips (``tools/build_studio_clips.py``): short compact windows of three recordings, read only
# when a Studio lists or loads its recorded music, never by Settings.
SHIPPED_CLIPS = ROOT / "assets" / "production" / "studio_clips"
_shipped_cache: dict = {}


def shipped_clips(directory: Path | None = None) -> tuple:
    """The shipped recorded-music fixtures (manifest order), as ``StudioFixture``s whose description is the path."""
    from ui.studio.adapter import RECORDED, StudioFixture
    folder = Path(directory) if directory is not None else SHIPPED_CLIPS
    key = str(folder)
    if key not in _shipped_cache:
        try:
            manifest = json.loads((folder / "clips.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifest = {"clips": []}
        _shipped_cache[key] = tuple(
            StudioFixture("clip:" + entry["id"], entry["label"], RECORDED, 0.0, str(folder / entry["file"]))
            for entry in manifest.get("clips", ()) if (folder / entry["file"]).is_file())
    return _shipped_cache[key]


def studio_clips(recordings: Path | None = None) -> tuple:
    """Every Studio's recorded-music list: the shipped clips first (the default source, identical in a frozen
    build and a checkout), then a source checkout's own native-PCM recordings, if it has any."""
    from ui.studio.adapter import RECORDED, StudioFixture
    clips = shipped_clips()
    if recordings is None or frozen_build() or not Path(recordings).is_dir():
        return clips
    return clips + tuple(StudioFixture("clip:" + path.stem, path.stem.replace("_", " ").title(), RECORDED, 0.0,
                                       str(path)) for path in sorted(Path(recordings).glob("*.jsonl"))
                         if has_native_history(path))


def has_native_history(path: str | Path) -> bool:
    """Waveform replay needs native PCM history on every frame; older recordings carry none (compact clips
    always do)."""
    if Path(path).suffix.lower() == ".srclip":
        return Path(path).is_file()
    try:
        with open(path, "rb") as stream:
            return b'"capture_history":{' in stream.read(4096)
    except OSError:
        return False


def extract(clip_path: str | Path, settings: Mapping[str, Any], *, seconds: float | None = None) -> dict:
    from PySide6.QtGui import QGuiApplication
    from widgets.spotify_visualizer.compact_clip import load_feature_clip
    from widgets.spotify_visualizer.feature_replay import (
        PcmReanalysis, ReplayBeatEngine, configure_offline_controller, deterministic_clock,
    )
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.tick_pipeline import logical_tick
    from widgets.spotify_visualizer.waveform_ribbon_frame_runtime import WaveformRibbonFrameRuntime

    if QGuiApplication.instance() is None:
        # Never create the process's application as a side effect: a QGuiApplication made here would
        # become the only application, and a later QWidget (Settings) then aborts the process.
        raise RuntimeError("extract() needs an existing QGuiApplication (main() creates one)")
    clip = load_feature_clip(clip_path)
    origin_us = clip.frames[0].timestamp_us
    frames = [f for f in clip.frames if seconds is None or (f.timestamp_us - origin_us) / 1e6 <= seconds]
    from ui.studio import clip_loop
    frames, start = clip_loop.primed(clip.frames, frames, clip_path)    # a loop: its end replayed first
    records: list[dict] = []
    original = WaveformRibbonFrameRuntime.advance

    def recording(self, **kwargs):
        snapshot = original(self, **kwargs)
        if snapshot is not None:
            entry = {key: value for key, value in kwargs.items() if key != "controls"}
            entry["onsets"] = [asdict(onset) for onset in kwargs["onsets"]]
            entry["body_bands"] = [float(v) for v in kwargs["body_bands"]]
            entry["identity"] = [int(v) for v in kwargs["identity"]]
            entry["source_identity"] = [int(v) for v in kwargs["source_identity"]]
            entry["ready"] = bool(snapshot.ready)
            entry["packet_sha256"] = hashlib.sha256(snapshot.packet.payload).hexdigest()
            records.append(entry)
        return snapshot

    resolved = dict(settings)
    resolved["mode"] = "waveform_ribbon"
    # The analysis worker process records every advance (restored afterwards; nothing else runs here).
    WaveformRibbonFrameRuntime.advance = recording
    try:
        with deterministic_clock() as clock:
            engine = ReplayBeatEngine(32)
            controller = VisualizerRuntimeController(runtime_generation=0, initial_mode="waveform_ribbon",
                                                     engine_factory=lambda _: engine)
            controller.engine = engine
            configure_offline_controller(controller, "waveform_ribbon", settings=resolved)
            reanalysis = PcmReanalysis()
            try:
                for feature in frames:
                    clock[0] = feature.timestamp_us / 1e6
                    controller.playing = feature.playing
                    engine.set_playback_state(feature.playing)
                    engine.accept_feature_frame(feature)
                    reanalysis.accept(engine, feature)
                    logical_tick(controller.logical_tick_state)
            finally:
                engine.force_stop()
    finally:
        WaveformRibbonFrameRuntime.advance = original
    ready = [r for r in records if r["ready"]]
    if not ready:
        raise RuntimeError("The clip never produced a primed waveform frame")
    # A loop's lead-in ticks stay in the record (before the origin): the Studio's frame runtime primes on them.
    return clip_loop.mark_loop({"clip": str(clip_path), "origin": float(ready[0]["now_ts"] if start is None else start),
                                "duration": float(records[-1]["now_ts"] - ready[0]["now_ts"]), "steps": records},
                               clip_path, start)


def to_inputs(data: Mapping[str, Any], fixture) -> "RecordedInputs":
    from widgets.spotify_visualizer.transient_bus import MusicalOnset
    from ui.studio.clip_loop import looped_fixture
    from ui.studio.waveform_adapter import AdvanceInput, RecordedInputs
    steps = tuple(AdvanceInput(now=float(s["now_ts"]), playing=bool(s["playing"]),
                               onsets=tuple(MusicalOnset(**o) for o in s["onsets"]),
                               body_bands=tuple(s["body_bands"]), intensity=float(s["intensity"]),
                               loudness=float(s["loudness"]), presence=float(s["presence"]),
                               identity=tuple(s["identity"]), source_identity=tuple(s["source_identity"]))
                  for s in data["steps"])
    return RecordedInputs(looped_fixture(fixture, data), steps, float(data["origin"]),
                          float(data.get("loop_period", 0.0)))


def frozen_build() -> bool:
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


# A frozen build has no ``python -m``: the app executable runs the worker when its first argument is this flag
# (``main.main`` -> ``run_frozen_worker``). Only the Studios' recorded-input workers can be named.
WORKER_FLAG = "--studio-clip-worker"


def worker_command(module: str, arguments: list[str]) -> tuple[str, list[str]]:
    if frozen_build():
        return sys.executable, [WORKER_FLAG, module, *arguments]
    return sys.executable, ["-m", module, *arguments]


def run_frozen_worker(argv: list[str]) -> int | None:
    """``argv`` = ``[exe, WORKER_FLAG, module, clip, settings, output, seconds, ...]`` -> the worker's exit code,
    or None when this process is not a Studio clip worker. Trailing arguments (an entry point's injected mode
    switch) are ignored."""
    if len(argv) < 7 or argv[1] != WORKER_FLAG:
        return None
    module = str(argv[2])
    if not (module.startswith("ui.studio.") and module.endswith("_recorded_inputs")
            and module.replace(".", "").replace("_", "").isalnum()):
        return 2
    import importlib
    return int(importlib.import_module(module).main(list(argv[3:7])))


_CANCELLED: set = set()
# Workers this process started (a count only: tests check nothing outlives them when it moved).
STARTED = [0]


def worker_tag(pid: int | None = None) -> str:
    """The prefix of a worker's temporary folder, naming the process that started it: it appears in the worker's
    command line, so a leaked worker can be traced to its parent after that parent is gone."""
    return f"srpss_studio_clip_{os.getpid() if pid is None else int(pid)}_"


class ClipLoadJob:
    """One out-of-process extraction, event driven (QProcess.finished); ``cancel`` kills it.

    Mode-neutral: ``module`` is the worker (``python -m <module> clip settings output seconds``) and ``convert``
    turns its JSON into the mode's recorded inputs (default: this module's Waveform worker and ``to_inputs``).
    The worker and everything it starts never outlive this job or this process (``worker_lifetime.WorkerTree``):
    a cancel ends the whole tree, and the OS ends it when this process exits or crashes."""

    def __init__(self, clip, settings: Mapping[str, Any], finished: Callable[..., None], *,
                 module: str = __name__, convert: Callable[..., Any] | None = None) -> None:
        import tempfile
        from PySide6.QtCore import QProcess
        from dataclasses import replace
        self._finished = finished
        from ui.studio.worker_lifetime import WorkerTree
        self._directory = tempfile.TemporaryDirectory(prefix=worker_tag())
        folder = Path(self._directory.name)
        self._settings_path = folder / "settings.json"
        self._output_path = folder / "inputs.json"
        self._settings_path.write_text(json.dumps(dict(settings)), encoding="utf-8")
        self._clip = clip
        self._cancelled = False
        process = QProcess()
        process.setWorkingDirectory(str(ROOT))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)
        self._process = process
        self._convert = convert or to_inputs
        self._replace = replace
        self._tree = WorkerTree()
        process.start(*worker_command(module, [clip.description, str(self._settings_path),
                                               str(self._output_path), str(CLIP_SECONDS)]))
        STARTED[0] += 1
        pid = int(process.processId() or 0)
        if pid:
            self._tree.adopt(pid)

    def _complete(self, result=None, error: str = "") -> None:
        from PySide6.QtCore import QTimer
        # Runs inside the QProcess's own finished/error signal. Hold this job (and so its
        # QProcess) until the next event-loop turn: dropping the last reference here deletes
        # the QProcess mid-emission, and on Linux its pipe notifiers then fire into freed memory.
        _CANCELLED.add(self)
        self._tree.close()
        callback, self._finished = self._finished, None
        if callback is not None and not self._cancelled:
            callback(result, error)
        try:
            self._directory.cleanup()
        except OSError:
            pass
        QTimer.singleShot(0, self._forget)

    def _on_error(self, _error) -> None:
        import shiboken6
        if not shiboken6.isValid(self._process):            # the QProcess went with the app (quit)
            self._tree.close()
            return
        if self._process.state() == self._process.ProcessState.NotRunning:
            self._complete(None, self._process.errorString() or "analysis process failed")

    def _on_finished(self, code: int, _status) -> None:
        if self._cancelled:
            self._complete()
            return
        if code != 0 or not self._output_path.is_file():
            tail = bytes(self._process.readAll()).decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
            self._complete(None, f"exit {code}: {tail[0]}")
            return
        try:
            data = json.loads(self._output_path.read_text(encoding="utf-8"))
            fixture = self._replace(self._clip, duration=float(data["duration"]))   # ``to_inputs`` marks a loop
            self._complete(self._convert(data, fixture))
        except Exception as exc:
            self._complete(None, f"{type(exc).__name__}: {exc}")

    def cancel(self) -> None:
        """Kill without waiting: the GUI thread never blocks on the worker (QProcess.finished cleans up)."""
        self._cancelled = True
        self._tree.terminate()                   # the worker and anything it started (a venv launcher's child)
        if self._process.state() != self._process.ProcessState.NotRunning:
            _CANCELLED.add(self)                 # keep the QProcess alive until its finished signal
            self._process.kill()

    def _forget(self) -> None:
        _CANCELLED.discard(self)


def main(argv: list[str]) -> int:
    clip, settings_path, output_path, *rest = argv
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from ui.studio.worker_lifetime import die_with_parent
    die_with_parent()
    settings = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    from PySide6.QtGui import QGuiApplication
    _app = QGuiApplication.instance() or QGuiApplication([])     # this process is the analysis worker
    data = extract(clip, settings, seconds=float(rest[0]) if rest else CLIP_SECONDS)
    Path(output_path).write_text(json.dumps(data), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
