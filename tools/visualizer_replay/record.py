"""Record real music as a schema 2 replay clip: python -m tools.visualizer_replay.record NAME --seconds 60

Play the music first. A private BeatEngine (not the application's shared one) captures the live
loopback audio with the analysis configuration Voxel Sphere activates with on this profile (its
Spectrum-borrowed technical profile and source shaping, read from Settings, never written), is
ticked at the 90 Hz logical cadence with no window, and every tick becomes one ``FeatureFrame``
carrying the normalised lanes plus ``RealScaleLanes`` in production units (uncapped: real music
reads 3-17 on the bus loudness). Typed scheduler events are taken once each, as Sphere takes them.
The clip goes to ``logs/visualizer_recordings/NAME.jsonl`` (refusing to overwrite) with a summary
of the real ranges seen. Recordings are the operator's music: they stay local (``logs/``).
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import statistics
import time

from PySide6.QtCore import QCoreApplication, QTimer, Qt

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "logs" / "visualizer_recordings"
TICK_MS = 11                                    # the logical cadence (~90 Hz)
_ONSET_TYPE = {"kick": "bass", "snare": "mid", "vocal_swell": "high"}
_TYPED_EVENT_AGE_S = 0.25


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
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
    from widgets.spotify_visualizer.quick_technical_config import apply_controller_technical_config
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.source_config_applier import apply_engine_vis_mode_kwargs
    from widgets.spotify_visualizer.technical_config import build_technical_cache, resolve_technical_config

    section = SettingsManager().get("widgets.spotify_visualizer") or {}
    activation = resolve_visualizer_activation_payload(dict(section), mode="sphere")
    model = SpotifyVisualizerSettings.from_mapping(activation.resolved_config, apply_preset_overlay=False,
                                                   resolve_preset_indices=False)
    engines = []

    def factory(count):
        engines.append(_SpotifyBeatEngine(count))
        return engines[-1]

    controller = VisualizerRuntimeController(runtime_generation=0, initial_mode="sphere", engine_factory=factory)
    controller.settings_model = model
    controller.technical_config_cache = build_technical_cache(None, model)
    apply_controller_technical_config(controller, resolve_technical_config(controller.technical_config_cache, "sphere"),
                                      reason="replay_recording")
    engine = controller.ensure_engine()
    apply_engine_vis_mode_kwargs(engine, asdict(model))
    return controller, engine


def _frame(engine, timestamp_us: int, bars, scheduler, onsets=()):
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
    count = max(0, min(len(engine.get_waveform()), int(engine.get_waveform_count())))
    waveform = engine.get_waveform()[:count] or [0.0]
    return FeatureFrame(
        timestamp_us=timestamp_us, energy=lanes,
        raw_bars=tuple(_unit(v) for v in _resample(bars, RAW_BAR_COUNT)),
        waveform=tuple(max(-1.0, min(1.0, float(v))) for v in _resample(waveform, WAVEFORM_COUNT)),
        playing=True, visible=True, mode="sphere", schema_version=REAL_SCALE_SCHEMA_VERSION,
        real=RealScaleLanes(live=(live.bass, live.mid, live.high, live.overall),
                            musical_level=tuple(engine.get_musical_level()), analysis_spectrum=spectrum,
                            events=tuple(events),
                            onsets=tuple(RecordedOnset(o.kind, _unit(o.strength), o.magnitude, o.loudness, o.presence)
                                         for o in onsets if o.kind in TYPED_EVENT_KINDS)),
    )


def _summary(frames) -> str:
    def spread(values):
        values = sorted(values)
        if not values:
            return "n/a"
        pick = lambda q: values[min(len(values) - 1, int(q * len(values)))]
        return f"p10 {pick(0.1):.2f}  median {statistics.median(values):.2f}  p90 {pick(0.9):.2f}  max {values[-1]:.2f}"

    loud = [f.real.musical_level[0] for f in frames]
    presence = [f.real.musical_level[1] for f in frames if f.real.musical_level[0] > 0]
    pinned = sum(1 for f in frames if f.real.live[0] >= 2.5) / max(1, len(frames))
    events = {}
    for frame in frames:
        for event in frame.real.events:
            events[event.kind] = events.get(event.kind, 0) + 1
    onsets = sum(len(frame.real.onsets) for frame in frames)
    return (f"frames {len(frames)} ({len(frames) * TICK_MS / 1000:.1f} s)\n"
            f"loudness  {spread(loud)}\npresence  {spread(presence)}\n"
            f"live bass pinned at 2.5: {pinned:.0%} of frames\ntyped events {events}\nmusical onsets {onsets}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help="clip name (snake_case)")
    parser.add_argument("--seconds", type=float, default=60.0)
    args = parser.parse_args()
    from widgets.spotify_visualizer.feature_frame import FeatureClip

    path = OUTPUT / f"{args.name}.jsonl"
    if path.exists():
        parser.error(f"refusing to overwrite {path}")
    app = QCoreApplication.instance() or QCoreApplication([])
    controller, engine = _configured_engine()
    engine.acquire()
    engine.set_playback_state(True)
    engine.ensure_started()
    frames = []
    last_serial = [0]
    start = time.perf_counter()

    def tick():
        bars = engine.tick() or []
        elapsed = time.perf_counter() - start
        # Looked up every tick, as Sphere's capture does: the inline analysis commits a fresh copy of the
        # worker's DSP state (transient bus and scheduler included) each frame.
        onsets = engine.get_onset_events(last_serial[0])
        if onsets:
            last_serial[0] = onsets[-1].serial
        frames.append(_frame(engine, 1_000_000 + int(elapsed * 1_000_000), bars, engine.get_event_scheduler(),
                             onsets))
        if elapsed >= args.seconds:
            timer.stop()
            app.quit()

    timer = QTimer()
    timer.setTimerType(Qt.TimerType.PreciseTimer)
    timer.timeout.connect(tick)
    timer.start(TICK_MS)
    print(f"recording {args.seconds:.0f} s of live audio ...", flush=True)
    try:
        app.exec()
    finally:
        engine.set_playback_state(False)
        engine.release()
        engine.force_stop()
        controller.close_render_admission()
    clip = FeatureClip(name=args.name, frames=tuple(frames))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as out:
        out.write(clip.to_jsonl_bytes())
    print(f"wrote {path}\n{_summary(frames)}")


if __name__ == "__main__":
    main()
