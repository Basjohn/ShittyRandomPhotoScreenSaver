"""Spectrum's engine answers, per production tick, recorded through the production replay (out of process).

Spectrum's input is the engine's *own processing*: every logical tick ``consume_engine_bars`` ticks the beat engine
and reads its smoothed, shape-processed bars, and the shape editor (curve nodes, frequency boundaries, lane
strengths), the Audio sliders and the technical analysis configure that processing, which runs on the process clock
(smoothing, play ramps and playback timestamps read ``time.time()``). Only an out-of-process replay may pin that
clock, so this module runs as a *separate process* (``python -m ui.studio.spectrum_recorded_inputs``, or the frozen
app's ``--studio-clip-worker`` path) through the shared event-driven ``ClipLoadJob``.

The worker drives the production offline replay (``feature_replay``: ``ReplayBeatEngine`` +
``configure_offline_controller`` + ``logical_tick`` under ``deterministic_clock``) and, for every tick, stands an
``EngineAnswerRecorder`` in for the engine during the production step: everything the engine answered Spectrum's
step (smoothed bars, generation / activation / commit identities, the authoritative source frame, energy, transient,
floor snapshot, waveform counts) is recorded, with a digest of the logical frame the production tick published.
The Studio then runs Spectrum's own production step and capture in process from those answers, so every
Spectrum-owned control is exact and instant; an engine-owned edit changes the answers and re-runs this worker.

Sources: a recorded clip (the shipped compact clips or a checkout's native-PCM recordings), or ``synthetic:<id>``,
generated audio (kicks, snares, hats, a bass line and a vocal pad at a held Quiet / Mid / Peak level or a scripted
passage) cut into native capture histories at the production logical cadence, so the shape editor shapes real
audio through the production DSP for those fixtures too. The authored lanes of a synthetic frame (pre-AGC, Bubble,
transient, typed events, musical level) follow the same score; Spectrum's step reads only the transient lane of
them, and its renderer none.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
MODE = "spectrum"
SYNTHETIC_PREFIX = "synthetic:"
STEP = 1.0 / 90.0                # the production logical cadence (and the recorder's ~11 ms frames)
RATE = 48000
HISTORY = 1024                   # native samples per frame: the largest analysis block Settings offers
PREROLL = 2.0                    # synthetic audio before t = 0 so AGC, floors and smoothing have settled
DURATION = 10.0
START = 1.0                      # first synthetic frame time (production capture timestamps are never 0)
SEED = 1729


def frame_digest(frame) -> str:
    """Every field of a ``VisualizerLogicalFrame`` (common state, Spectrum frame and its parameters)."""
    return hashlib.sha256(repr(frame).encode()).hexdigest()


# ------------------------------------------------------------------------------- synthetic audio
# (label, kind, description) per synthetic fixture; the kinds are ``ui.studio.adapter``'s.
SYNTHETIC = {
    "quiet": ("Quiet", "reference", "A soft passage: light kicks, a quiet bass line and a low vocal pad."),
    "mid": ("Mid", "reference", "An ordinary passage at 120 BPM: kicks, snares, hats, bass and a vocal pad."),
    "peak": ("Peak", "reference", "A hot, dense passage: hard kicks and snares, sixteenth hats, a loud vocal."),
    "bass": ("Bass Pulses", "synthetic", "Kicks and the bass line alone: only the low lanes move."),
    "transient": ("Hit Over Loud Bed", "synthetic", "A loud held vocal bed with two isolated hits."),
    "decay": ("Decay To Silence", "synthetic", "A hot groove that releases to silence after two seconds."),
}
# Per passage: (kick, snare, hats, bass, pad) amplitude and hat subdivision.
_LEVELS = {
    "quiet": ((.22, .0, .03, .12, .06), 2),
    "mid": ((.45, .28, .07, .22, .12), 2),
    "peak": ((.8, .55, .14, .38, .26), 4),
    "bass": ((.6, .0, .0, .32, .0), 2),
    "transient": ((.9, .7, .0, .0, .34), 2),
    "decay": ((.8, .55, .14, .38, .26), 4),
}
_BASS_NOTES = (55.0, 55.0, 65.41, 73.42, 55.0, 82.41, 73.42, 65.41)      # one per beat (A1 C2 D2 E2)
_PAD_CHORDS = ((220.0, 277.18, 329.63), (196.0, 246.94, 293.66), (174.61, 220.0, 261.63), (196.0, 246.94, 293.66))


def _band_noise(rng, count: int, low: float, high: float):
    import numpy as np
    spectrum = np.fft.rfft(rng.standard_normal(count))
    freqs = np.fft.rfftfreq(count, 1.0 / RATE)
    spectrum[(freqs < low) | (freqs > high)] = 0.0
    noise = np.fft.irfft(spectrum, count)
    return noise / max(1e-9, float(np.max(np.abs(noise))))


def _hits(times, span: int, total: int, shape):
    """Sum of ``shape(t)`` (t seconds since the hit, ``span`` samples long) started at each of ``times``."""
    import numpy as np
    out = np.zeros(total)
    local = np.arange(span) / RATE
    for when, gain in times:
        start = int(round(when * RATE))
        if start >= total or start + span <= 0:
            continue
        piece = gain * shape(local)
        lo, hi = max(0, start), min(total, start + span)
        out[lo:hi] += piece[lo - start:hi - start]
    return out


def synthetic_score(fixture_id: str):
    """(mono PCM float32 at ``RATE`` from absolute time 0, typed events [(time, kind, strength)]) for one synthetic
    fixture. Deterministic (seeded)."""
    import numpy as np
    if fixture_id not in SYNTHETIC:
        raise KeyError(fixture_id)
    (kick_a, snare_a, hat_a, bass_a, pad_a), hats_per_beat = _LEVELS[fixture_id]
    rng = np.random.default_rng(SEED)
    first = START
    total_s = START + PREROLL + DURATION + 0.05
    total = int(total_s * RATE)
    t = np.arange(total) / RATE
    beat = 0.5
    beats = [first + i * beat for i in range(int((total_s - first) / beat) + 1)]
    if fixture_id == "transient":
        kicks = [(first + PREROLL + 3.0, 1.0)]
        snares = [(first + PREROLL + 6.5, 1.0)]
    else:
        kicks = [(b, (1.0, .7, .9, .65)[i % 4]) for i, b in enumerate(beats)] if kick_a else []
        snares = [(b, (1.0, .85)[(i // 2) % 2]) for i, b in enumerate(beats) if i % 2 == 1] if snare_a else []
    kick = kick_a * _hits(kicks, int(.35 * RATE), total, lambda x: np.sin(2 * np.pi * (48 * x + 9 * (1 - np.exp(-x / .03))))
                          * np.exp(-x / .16))
    snare_noise = _band_noise(rng, int(.25 * RATE), 900.0, 6000.0)
    snare = snare_a * _hits(snares, int(.25 * RATE), total,
                            lambda x: (snare_noise[:len(x)] * .8 + .4 * np.sin(2 * np.pi * 190 * x)) * np.exp(-x / .07))
    hat_noise = _band_noise(rng, int(.06 * RATE), 7000.0, 15000.0)
    hat_times = [(first + i * beat / hats_per_beat, (.9, .5)[i % 2]) for i in range(int((total_s - first) / (beat / hats_per_beat)))]
    hats = hat_a * _hits(hat_times, int(.06 * RATE), total, lambda x: hat_noise[:len(x)] * np.exp(-x / .018)) if hat_a else 0.0
    bass = np.zeros(total)
    if bass_a:
        for i, b in enumerate(beats):
            start, stop = int(b * RATE), min(total, int((b + beat) * RATE))
            if start >= total:
                break
            local = (np.arange(start, stop) - start) / RATE
            freq = _BASS_NOTES[i % len(_BASS_NOTES)]
            tone = np.sin(2 * np.pi * freq * local) + .35 * np.sin(4 * np.pi * freq * local)
            bass[start:stop] = bass_a * tone * np.minimum(1.0, local / .01) * np.exp(-local / .6)
    pad = np.zeros(total)
    swells = []
    if pad_a:
        bar = 4 * beat
        for i in range(int((total_s - first) / bar) + 1):
            start, stop = int((first + i * bar) * RATE), min(total, int((first + (i + 1) * bar) * RATE))
            if start >= total:
                break
            local = (np.arange(start, stop) - start) / RATE
            vibrato = 1.0 + .004 * np.sin(2 * np.pi * 5.2 * local)
            voice = sum(sum(np.sin(2 * np.pi * f * h * vibrato * local) / h for h in (1, 2, 3, 4))
                        for f in _PAD_CHORDS[i % len(_PAD_CHORDS)])
            swell = np.minimum(1.0, local / .4) * (0.75 + .25 * np.sin(np.pi * local / bar))
            pad[start:stop] = pad_a * voice / 6.0 * swell
            swells.append((first + i * bar + .4, .8))
    mix = kick + snare + hats + bass + pad
    if fixture_id == "decay":
        release = first + PREROLL + 2.0
        mix = mix * np.where(t < release, 1.0, np.exp(-(t - release) / 1.5))
    mix = np.clip(mix, -1.0, 1.0).astype(np.float32)
    events = sorted([(w, "kick", min(1.0, g * kick_a / .8)) for w, g in kicks]
                    + [(w, "snare", min(1.0, g * max(snare_a, .5) / .55)) for w, g in snares]
                    + [(w, "vocal_swell", g) for w, g in swells])
    return mix, events


def synthetic_features(fixture_id: str):
    """The synthetic fixture as production feature frames: one per logical tick, each carrying the native capture
    history ending at its time (new audio every tick) and lanes following the score."""
    import numpy as np
    from widgets.spotify_visualizer.feature_frame import (
        REAL_SCALE_SCHEMA_VERSION, BandEnergy, CaptureHistory, EnergyLanes, FeatureFrame, RealScaleLanes,
        TransientEnergy, TypedEvent,
    )
    pcm, events = synthetic_score(fixture_id)
    frames = []
    count = int(round((PREROLL + DURATION) / STEP)) + 1
    previous_rms = (0.0, 0.0, 0.0)
    for k in range(count):
        now = START + k * STEP
        end = int(round(now * RATE))
        history = pcm[max(0, end - HISTORY):end]
        block = history.astype(np.float64)
        spectrum = np.abs(np.fft.rfft(block * np.hanning(len(block)))) / max(1, len(block)) * 4.0
        freqs = np.fft.rfftfreq(len(block), 1.0 / RATE)
        lanes = tuple(min(1.0, float(np.sqrt(np.mean(spectrum[(freqs >= lo) & (freqs < hi)] ** 2) or 0.0)) * 6.0)
                      for lo, hi in ((20, 250), (250, 4000), (4000, 16000)))
        overall = min(1.0, lanes[0] * .46 + lanes[1] * .34 + lanes[2] * .2)
        rise = tuple(max(0.0, a - b) for a, b in zip(lanes, previous_rms))
        previous_rms = lanes
        due = [(kind, strength) for when, kind, strength in events if now - STEP < when <= now]
        kinds = {}
        for kind, strength in due:
            kinds[kind] = max(kinds.get(kind, 0.0), strength)
        onset = max(kinds.items(), key=lambda item: item[1]) if kinds else None
        onset_type = {"kick": "bass", "snare": "mid", "vocal_swell": "high"}[onset[0]] if onset else ""
        transient = TransientEnergy(*(min(1.0, 3.0 * r) for r in rise), min(1.0, sum(rise)),
                                    onset_detected=onset is not None, onset_type=onset_type,
                                    onset_strength=max(1e-3, onset[1]) if onset else 0.0)
        band = BandEnergy(*lanes, overall)
        tail = history[-64:] if len(history) >= 64 else np.pad(history, (64 - len(history), 0))
        loudness = 17.0 * overall
        frames.append(FeatureFrame(
            timestamp_us=int(round(now * 1e6)),
            energy=EnergyLanes(continuous=band, pre_agc=band, bubble=band, transient=transient),
            raw_bars=(0.0,) * 32, waveform=tuple(float(v) for v in np.clip(tail, -1.0, 1.0)), playing=True,
            visible=True, mode=MODE, schema_version=REAL_SCALE_SCHEMA_VERSION,
            real=RealScaleLanes(live=tuple(min(2.5, 2.5 * v) for v in (*lanes, overall)),
                                musical_level=(loudness, min(1.6, .4 + 1.2 * overall)), analysis_spectrum=(),
                                events=tuple(TypedEvent(kind, strength) for kind, strength in sorted(kinds.items()))),
            capture_history=CaptureHistory(history.astype("<f4").tobytes(), capture_serial=k + 1, sample_rate=RATE),
        ))
    return frames


# ----------------------------------------------------------------------------------- extraction
def load_source(source: str | Path):
    """(feature frames, fixture origin time) of a clip path or a ``synthetic:<id>`` source."""
    text = str(source)
    if text.startswith(SYNTHETIC_PREFIX):
        return synthetic_features(text[len(SYNTHETIC_PREFIX):]), START + PREROLL
    from widgets.spotify_visualizer.compact_clip import load_feature_clip
    frames = load_feature_clip(source).frames
    return frames, None


def extract(source: str | Path, settings: Mapping[str, Any], *, seconds: float | None = None,
            features=None, frames_out: list | None = None) -> dict:
    """Replay ``source`` (a clip path or ``synthetic:<id>``) through the production offline replay under ``settings``
    and record, per tick, what the engine answered Spectrum's step and the digest of the frame that tick published.
    ``features``: already-loaded frames instead of ``source`` (tests); ``frames_out`` collects ``(now, frame)`` of
    the production ticks (in-process callers only)."""
    from PySide6.QtGui import QGuiApplication
    from widgets.spotify_visualizer.feature_replay import ReplayBeatEngine, deterministic_clock
    from widgets.spotify_visualizer.tick_pipeline import logical_tick
    from ui.studio.replay_engine import EngineAnswerRecorder, offline_controller
    from ui.studio.spectrum_adapter import engine_values, resolved_settings

    if QGuiApplication.instance() is None:
        raise RuntimeError("extract() needs an existing QGuiApplication (main() creates one)")
    origin = None
    if features is None:
        features, origin = load_source(source)
    first_us = features[0].timestamp_us
    if seconds is not None and origin is None:
        features = [f for f in features if (f.timestamp_us - first_us) / 1e6 <= seconds]
    records: list[dict] = []
    with deterministic_clock() as clock:
        engine = ReplayBeatEngine(32)
        controller = offline_controller(engine, MODE, resolved_settings(settings))
        state = controller.logical_tick_state
        recorder = EngineAnswerRecorder(engine)
        try:
            for feature in features:
                now = feature.timestamp_us / 1e6
                clock[0] = now
                controller.playing = feature.playing
                engine.set_playback_state(feature.playing)
                engine.accept_feature_frame(feature)
                recorder.begin()
                controller.engine = recorder
                try:
                    payload = logical_tick(state)
                finally:
                    controller.engine = engine
                records.append({"now_ts": now, "playing": bool(feature.playing), "answers": recorder.answers,
                                "commands": list(recorder.commands),
                                "frame_sha256": None if payload is None else frame_digest(payload)})
                if frames_out is not None and payload is not None:
                    frames_out.append((now, payload))
        finally:
            engine.force_stop()
    if not any(r["frame_sha256"] for r in records):
        raise RuntimeError("The source never published a Spectrum frame")
    start = float(records[0]["now_ts"]) if origin is None else float(origin)
    return {"source": str(source), "origin": start, "duration": float(records[-1]["now_ts"] - start),
            "engine_values": engine_values(settings), "steps": records}


def to_inputs(data: Mapping[str, Any], fixture):
    from ui.studio.spectrum_adapter import RecordedInputs, ServedTick
    steps = tuple(ServedTick(now=float(s["now_ts"]), playing=bool(s["playing"]), answers=s["answers"])
                  for s in data["steps"])
    return RecordedInputs(fixture, steps, float(data["origin"]), source=str(data["source"]),
                          engine_values=dict(data["engine_values"]))


def main(argv: list[str]) -> int:
    source, settings_path, output_path, *rest = argv
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from ui.studio.waveform_recorded_inputs import CLIP_SECONDS
    settings = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    from PySide6.QtGui import QGuiApplication
    _app = QGuiApplication.instance() or QGuiApplication([])     # this process is the analysis worker
    data = extract(source, settings, seconds=float(rest[0]) if rest else CLIP_SECONDS)
    Path(output_path).write_text(json.dumps(data), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
