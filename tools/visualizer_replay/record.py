"""Record real music as a schema 2 replay clip: python -m tools.visualizer_replay.record NAME --seconds 60

Play the music first. A private BeatEngine (not the application's shared one) captures the live
loopback audio with the analysis configuration Voxel Sphere activates with on this profile (its
Spectrum-borrowed technical profile and analysis-only source, read from Settings, never written), is
ticked at the 90 Hz logical cadence with no window, and every tick becomes one ``FeatureFrame``
carrying full native capture history, the normalised lanes and ``RealScaleLanes`` in production units (uncapped: real music
reads 3-17 on the bus loudness). Typed scheduler events are taken once each, as Sphere takes them.
The clip goes to ``logs/visualizer_recordings/NAME.jsonl`` (refusing to overwrite) with frame/event
counts. For the friendly UI, run ``python tools/music_recorder.py``. Recordings are the operator's
music: they stay local (``logs/``).
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import math
import os
from pathlib import Path
import re
import tempfile
import time
import unicodedata

from PySide6.QtCore import QCoreApplication, QTimer, Qt

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "logs" / "visualizer_recordings"
TICK_MS = 11                                    # the logical cadence (~90 Hz)
_ONSET_TYPE = {"kick": "bass", "snare": "mid", "vocal_swell": "high"}
_TYPED_EVENT_AGE_S = 0.25


def recorded_clips():
    """The current recordings, oldest name first: archived takes (``*_noevents``, ``*_v1``, ...) are
    kept on disk for reference but skipped."""
    from widgets.spotify_visualizer.feature_frame import load_jsonl

    return [load_jsonl(path) for path in sorted(OUTPUT.glob("*.jsonl"))
            if not re.search(r"_(noevents|v\d+)$", path.stem)]


def _unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _resample(values, count: int) -> tuple[float, ...]:
    values = [float(v) for v in values] or [0.0]
    if len(values) == count:
        return tuple(values)
    last = len(values) - 1
    out = []
    for index in range(count):
        position = index * last / max(1, count - 1)
        lower = int(position)
        upper = min(last, lower + 1)
        out.append(values[lower] + (values[upper] - values[lower]) * (position - lower))
    return tuple(out)


def _configured_engine():
    """A private engine configured as Sphere's activation configures the shared one."""
    from core.settings.models import SpotifyVisualizerSettings
    from core.settings.settings_manager import SettingsManager
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from core.threading.manager import ThreadManager
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
    from widgets.spotify_visualizer.quick_technical_config import apply_controller_technical_config
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.source_config_applier import apply_engine_vis_mode_kwargs, resolve_mode_source_config
    from widgets.spotify_visualizer.technical_config import build_technical_cache, resolve_technical_config

    section = SettingsManager().get("widgets.spotify_visualizer") or {}
    activation = resolve_visualizer_activation_payload(dict(section), mode="sphere")
    model = SpotifyVisualizerSettings.from_mapping(activation.resolved_config, apply_preset_overlay=False,
                                                   resolve_preset_indices=False)
    thread_manager = ThreadManager.create_helper_manager()

    def factory(count):
        engine = _SpotifyBeatEngine(count)
        engine.set_thread_manager(thread_manager)
        return engine

    controller = None
    try:
        controller = VisualizerRuntimeController(runtime_generation=0, initial_mode="sphere", engine_factory=factory)
        controller.thread_manager = thread_manager
        controller.settings_model = model
        controller.technical_config_cache = build_technical_cache(None, model)
        apply_controller_technical_config(controller, resolve_technical_config(controller.technical_config_cache, "sphere"),
                                          reason="replay_recording")
        engine = controller.ensure_engine()
        apply_engine_vis_mode_kwargs(engine, resolve_mode_source_config("sphere", asdict(model)))
        engine.set_waveform_history_demand(True)
        engine.get_pre_agc_analysis_spectrum()  # Request publication before the first analysis.
        return controller, engine
    except Exception:
        if controller is not None and controller.engine is not None:
            _close_configured_engine(controller, controller.engine)
        elif not thread_manager.shutdown(wait=True, timeout=5.0):
            raise RuntimeError("recorder ThreadManager did not drain after configuration failure")
        raise


def _close_configured_engine(controller, engine) -> None:
    """Close private recording admission and join its canonical worker owners."""
    try:
        engine.set_playback_state(False)
    finally:
        try:
            engine.release()
        finally:
            try:
                engine.force_stop()
            finally:
                try:
                    controller.close_render_admission()
                finally:
                    if not controller.thread_manager.shutdown(wait=True, timeout=5.0):
                        raise RuntimeError("recorder audio capture or analysis ownership did not drain")


def _frame(engine, timestamp_us: int, bars, scheduler, onsets=(), *, capture_history=None):
    from widgets.spotify_visualizer.feature_frame import (
        RAW_BAR_COUNT, REAL_SCALE_SCHEMA_VERSION, TYPED_EVENT_KINDS, WAVEFORM_COUNT, BandEnergy, EnergyLanes,
        FeatureFrame, RealScaleLanes, RecordedOnset, TransientEnergy, TypedEvent,
    )

    def band(source):
        return BandEnergy(bass=_unit(source.bass), mid=_unit(source.mid), high=_unit(source.high),
                          overall=_unit(source.overall))

    transient = engine.get_transient_energy_bands()
    onset = bool(transient.onset_detected) and transient.onset_type in _ONSET_TYPE and transient.onset_strength > 0
    lanes = EnergyLanes(
        continuous=band(engine.get_energy_bands()), pre_agc=band(engine.get_pre_agc_energy_bands()),
        bubble=band(engine.get_bubble_energy_bands()),
        transient=TransientEnergy(
            bass=_unit(transient.bass_transient), mid=_unit(transient.mid_transient),
            high=_unit(transient.high_transient), overall=_unit(max(transient.bass_transient, transient.mid_transient,
                                                                    transient.high_transient)),
            onset_detected=onset, onset_type=_ONSET_TYPE[transient.onset_type] if onset else "",
            onset_strength=_unit(transient.onset_strength) if onset else 0.0),
    )
    events = []
    if scheduler is not None:
        for kind in ("kick", "snare", "vocal_swell"):
            event = scheduler.consume_next(kind, max_age_s=_TYPED_EVENT_AGE_S)
            if event is not None and event.strength > 0.0:
                events.append(TypedEvent(kind, _unit(event.strength)))
    live = engine.get_live_pre_agc_energy_bands()
    spectrum = tuple(engine.get_pre_agc_analysis_spectrum())
    if len(spectrum) > 1024:
        spectrum = _resample(spectrum, 1024)
    if spectrum and len(spectrum) < 8:
        spectrum = ()
    # Only the first ``get_waveform_count`` samples are the latest block; the rest is zero padding.
    waveform = engine.get_waveform()
    count = max(0, min(len(waveform), int(engine.get_waveform_count())))
    waveform = waveform[:count] or [0.0]
    return FeatureFrame(
        timestamp_us=timestamp_us, energy=lanes,
        raw_bars=tuple(_unit(v) for v in _resample(bars, RAW_BAR_COUNT)),
        waveform=tuple(max(-1.0, min(1.0, float(v))) for v in _resample(waveform, WAVEFORM_COUNT)),
        playing=True, visible=True, mode="sphere", schema_version=REAL_SCALE_SCHEMA_VERSION,
        capture_history=capture_history,
        real=RealScaleLanes(live=(live.bass, live.mid, live.high, live.overall),
                            musical_level=tuple(engine.get_musical_level()), analysis_spectrum=spectrum,
                            events=tuple(events),
                            onsets=tuple(RecordedOnset(o.kind, _unit(o.strength), o.magnitude, o.loudness, o.presence)
                                         for o in onsets if o.kind in TYPED_EVENT_KINDS)),
    )


def clip_name(text: str) -> str:
    """Turn a friendly title into a safe, discoverable local clip filename."""
    name = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
    if not name or len(name) > 100:
        raise ValueError("Use a clip name with 1–100 letters, numbers or spaces.")
    if name.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)),
                        *(f"LPT{i}" for i in range(10))}:
        raise ValueError("That name is reserved by Windows; please choose another.")
    if re.search(r"_(noevents|v\d+)$", name):
        raise ValueError("Names ending in _noevents or _vNUMBER are reserved for archived clips.")
    return name


class RecorderSession:
    """One bounded recording; no timer, engine or worker remains active after completion.

    JSONL streams to a private partial file instead of retaining a minute of PCM in RAM.
    Only a complete, successfully retired recording is published under its final name.
    CLI and GUI share this capture/cleanup owner.
    """

    def __init__(self, name, *, seconds=60.0, on_progress=None, on_finished=None):
        self.name = clip_name(name)
        self.seconds = float(seconds)
        if not math.isfinite(self.seconds) or not 0 < self.seconds <= 600:
            raise ValueError("Recording length must be greater than 0 and at most 600 seconds.")
        self.path = OUTPUT / f"{self.name}.jsonl"
        self.on_progress = on_progress
        self.on_finished = on_finished
        self.timer = QTimer()
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._tick)
        self.controller = self.engine = None
        self.error = None
        self.saved = False
        self.active = False
        self._used = False
        self._file = self._partial = None
        self._started = None
        self._history_source = self._history = None
        self._capture_serial = self._last_onset = 0
        self._last_us = 999_999
        self._last_progress = -1.0
        self.frame_count = self.event_count = self.onset_count = 0
        self.max_gap_s = 0.0
        self._last_elapsed = 0.0

    def start(self):
        if self._used:
            raise RuntimeError("RecorderSession is single-use; create a new session for another clip")
        if self.path.exists():
            raise FileExistsError(f"A clip named {self.path.name} already exists. Choose a new name.")
        self._used = True
        self.active = True
        self._opening = time.perf_counter()
        try:
            self.controller, self.engine = _configured_engine()
            self.engine.acquire()
            self.engine.set_playback_state(True)
            self.engine.ensure_started()
            self.timer.start(TICK_MS)
        except Exception as exc:
            self._finish(error=exc)
            raise

    def _tick(self):
        if not self.active:
            return
        try:
            self._capture_tick()
        except Exception as exc:
            self._finish(error=exc)

    def _capture_tick(self):
        from widgets.spotify_visualizer.feature_frame import CaptureHistory, canonical_json

        now = time.perf_counter()
        worker = self.engine._audio_worker
        healthy = worker.is_capture_healthy()
        if not healthy:
            if self._started is not None or not worker.is_capture_starting() or now - self._opening >= 5.0:
                raise RuntimeError("recording rejected: audio capture failed or stopped delivering samples")
            return
        bars = self.engine.tick() or []
        source = self.engine.get_waveform_history()
        if source is None or len(source) == 0:
            if now - self._opening >= 5.0:
                raise RuntimeError("recording rejected: capture did not publish waveform history")
            return
        if source is not self._history_source:
            self._capture_serial += 1
            self._history_source = source
            self._history = CaptureHistory.from_samples(
                source, capture_serial=self._capture_serial, sample_rate=worker._backend.sample_rate)
        if self._started is None:
            self._started = now  # A full minute AFTER native capture is ready.
            OUTPUT.mkdir(parents=True, exist_ok=True)
            descriptor, filename = tempfile.mkstemp(prefix=f".{self.name}_", suffix=".partial", dir=OUTPUT)
            self._partial = Path(filename)
            self._file = os.fdopen(descriptor, "wb", buffering=1024 * 1024)
        elapsed = now - self._started
        timestamp_us = max(self._last_us + 1, 1_000_000 + int(elapsed * 1_000_000))
        onsets = self.engine.get_onset_events(self._last_onset)
        if onsets:
            self._last_onset = onsets[-1].serial
        frame = _frame(self.engine, timestamp_us, bars, self.engine.get_event_scheduler(), onsets,
                       capture_history=self._history)
        self._file.write(canonical_json(frame.to_dict()) + b"\n")
        self._last_us = timestamp_us
        self.frame_count += 1
        self.event_count += len(frame.real.events)
        self.onset_count += len(frame.real.onsets)
        self.max_gap_s = max(self.max_gap_s, elapsed - self._last_elapsed)
        self._last_elapsed = elapsed
        if self.on_progress and elapsed - self._last_progress >= 0.1:
            self._last_progress = elapsed
            self.on_progress(elapsed, source, self)
        if elapsed >= self.seconds:
            self._finish(save=True)

    def cancel(self):
        if self.active:
            self._finish()

    def _finish(self, *, save=False, error=None):
        self.timer.stop()
        self.error = error
        try:
            if self.engine is not None:
                _close_configured_engine(self.controller, self.engine)
        except Exception as exc:
            self.error = exc
        finally:
            self.engine = self.controller = None
        try:
            if self._file is not None:
                self._file.close()
                self._file = None
            if save and self.error is None:
                # Windows rename refuses an existing destination; POSIX link provides that
                # same atomic no-clobber contract (POSIX rename would overwrite it).
                if os.name == "nt":
                    self._partial.rename(self.path)
                else:
                    os.link(self._partial, self.path)
                self.saved = True
        except Exception as exc:
            self.error = exc
        finally:
            if self._partial is not None:
                try:
                    self._partial.unlink(missing_ok=True)
                except OSError as exc:
                    self.error = exc
                self._partial = None
            self._history_source = self._history = None
            self.active = False
        if self.on_finished:
            self.on_finished(self)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help="clip name (spaces are converted to underscores)")
    parser.add_argument("--seconds", type=float, default=60.0)
    args = parser.parse_args()
    app = QCoreApplication.instance() or QCoreApplication([])
    try:
        session = RecorderSession(args.name, seconds=args.seconds, on_finished=lambda _: app.quit())
    except ValueError as exc:
        parser.error(str(exc))
    try:
        session.start()
        print(f"recording {args.seconds:g} s of live audio with full capture history ...", flush=True)
        app.exec()
    finally:
        session.cancel()
    if session.error:
        raise session.error
    if not session.saved:
        raise RuntimeError("recording cancelled; no clip saved")
    print(f"wrote {session.path}\n{session.frame_count} frames; {session.event_count} typed events; "
          f"{session.onset_count} musical onsets; longest frame gap {session.max_gap_s * 1000:.1f} ms")


if __name__ == "__main__":
    main()
