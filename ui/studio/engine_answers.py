"""Recorded engine answers for an engine-processed mode (the Spectrum family), mode-neutral.

A Spectrum-family mode's step reads the beat engine's *own processing*: every logical tick ``consume_engine_bars``
ticks the engine and reads its smoothed, shape-processed bars, and the shape editor (curve nodes, frequency
boundaries, lane strengths), the Audio / Response sliders and the technical analysis configure that processing,
which runs on the process clock (smoothing, play ramps and playback timestamps read ``time.time()``). Only an
out-of-process replay may pin that clock, so each such mode has a worker module
(``python -m ui.studio.<mode>_recorded_inputs``, or the frozen app's ``--studio-clip-worker`` path) run through the
shared event-driven ``ClipLoadJob``. Every piece here takes the mode id; the worker modules and adapters are thin.

* **Worker.** ``extract`` drives the production offline replay (``ReplayBeatEngine`` +
  ``configure_offline_controller`` + ``logical_tick`` under ``deterministic_clock``) and, for every tick, stands an
  ``EngineAnswerRecorder`` in for the engine during the production step: everything the engine answered the mode's
  step is recorded, with a digest of the logical frame the production tick published.
* **Studio.** ``EngineAnswerEvaluator`` configures a ``VisualizerRuntimeController`` exactly as the offline replay
  does and, per recorded tick, runs the production step itself (``consume_engine_bars``, the mode's logical tick
  hook when it has one, as DevCurve's, then ``capture_visualizer_logical_frame``: the calls ``logical_tick`` makes)
  with ``RecordedEngineAnswers`` standing in for the engine. A mode-owned edit replays exactly and at once; an
  engine-owned edit changes the answers' key and re-runs the worker, the previous answers (with their own engine
  values) staying on screen meanwhile.
* **The split.** ``EngineAnswerMode.owned_keys``: the keys the engine never reads, from the production projection
  itself (``source_config_applier``: the mode's keys projected onto ``SPECTRUM_SOURCE_CONFIG_KEYS`` and its
  technical keys configure the engine; everything else the mode stores is read by its own step, capture or
  renderer). Each adapter's tests prove the split in both directions on the production replay.

Sources: a recorded clip (the shipped compact clips or a checkout's native-PCM recordings), or ``synthetic:<id>``,
generated audio (kicks, snares, hats, a bass line and a vocal pad at a held Quiet / Mid / Peak level or a scripted
passage) cut into native capture histories at the production logical cadence, so engine-owned edits shape real audio
through the production DSP for those fixtures too.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from ui.studio.adapter import RECORDED, REFERENCE, SYNTHETIC as SYNTHETIC_KIND, StudioFixture

ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_PREFIX = "synthetic:"
STEP = 1.0 / 90.0                # the production logical cadence (and the recorder's ~11 ms frames)
RATE = 48000
HISTORY = 1024                   # native samples per frame: the largest analysis block Settings offers
PREROLL = 2.0                    # synthetic audio before t = 0 so AGC, floors and smoothing have settled
DURATION = 10.0
START = 1.0                      # first synthetic frame time (production capture timestamps are never 0)
SEED = 1729
LABEL_MODE = "spectrum"          # the synthetic audio's feature-frame label (the audio, not the mode drawing it)
# Presentation context the store resolves for the display (not a mode key): a change re-presents, never re-analyses.
CONTEXT_KEYS = ("scene3d_detail",)


def frame_digest(frame) -> str:
    """Every field of a ``VisualizerLogicalFrame`` (common state, mode frame and its parameters)."""
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


LOUDNESS_SCALE = 24.0            # synthetic overall -> the real-music loudness scale (PassageIntensity)
LOUDNESS_MAX = 17.0
PRESENCE_EASE = 1.0 - math.exp(-STEP / 6.0)     # the bus's LOUDNESS_REFERENCE_SECONDS follower per tick
PRESENCE_MAX = 2.0
ANALYSIS_BANDS = 35              # the recorded clips' analysis-spectrum length (the recorder engine's bar count)


def analysis_spectrum(samples, bands: int = ANALYSIS_BANDS) -> tuple[float, ...]:
    """The pre-AGC analysis spectrum the live engine publishes for a capture block
    (``get_pre_agc_analysis_spectrum``: ``bar_computation.fft_to_bars``' per-band RMS of the log-compressed, lightly
    smoothed FFT magnitudes over logarithmic band edges, after ``compute_bars_from_samples``' peak gain), so a
    synthetic fixture carries what a recording carries (Neon Lake's Terrain Reaction reads it)."""
    import numpy as np
    mono = np.asarray(samples, dtype=np.float32)[-2048:]
    peak = float(np.abs(mono).max()) if mono.size else 0.0
    if peak < 1e-3:
        return (0.0,) * bands
    if 0.05 <= peak <= 5.0:
        mono = mono * min(2.8, max(1.0, 1.6 / peak))
    magnitude = np.abs(np.fft.rfft(mono))[1:].astype(np.float32)
    magnitude = np.power(np.log1p(magnitude), 1.2)
    if magnitude.size > 4:
        magnitude = np.convolve(magnitude, np.array([0.25, 0.5, 0.25], dtype=np.float32), mode="same")
    n = int(magnitude.size)
    edges = np.logspace(0.0, np.log10(n), bands + 1, dtype="float32").astype("int32")
    out = []
    for b in range(bands):
        start, end = int(edges[b]), int(edges[b + 1])
        end = max(end, start + 1)
        piece = magnitude[start:end] if start < n and end <= n else magnitude[:0]
        out.append(round(float(np.sqrt(np.mean(piece ** 2))), 6) if piece.size else 0.0)
    return tuple(out)


def synthetic_features(fixture_id: str):
    """The synthetic fixture as production feature frames: one per logical tick, each carrying the native capture
    history ending at its time (new audio every tick), lanes following the score, the analysis spectrum of the
    tick's audio and the score's hits as the transient bus's onsets (what a recording carries on each frame)."""
    import numpy as np
    from widgets.spotify_visualizer.feature_frame import (
        REAL_SCALE_SCHEMA_VERSION, BandEnergy, CaptureHistory, EnergyLanes, FeatureFrame, RealScaleLanes,
        RecordedOnset, TransientEnergy, TypedEvent,
    )
    pcm, events = synthetic_score(fixture_id)
    frames = []
    count = int(round((PREROLL + DURATION) / STEP)) + 1
    previous_rms = (0.0, 0.0, 0.0)
    reference = 0.0                  # the running loudness presence compares with (the bus's 6 s level)
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
        # The real-music loudness scale (``PassageIntensity``: ordinary music about 6.8..10.7, median 8.5), and
        # presence as the bus measures it: the level over its running level (about 1 in steady music).
        loudness = min(LOUDNESS_MAX, LOUDNESS_SCALE * overall)
        if loudness > 0.0:
            reference = loudness if reference <= 0.0 else reference + (loudness - reference) * PRESENCE_EASE
        presence = min(PRESENCE_MAX, loudness / reference) if reference > 0.0 else 0.0
        onsets = tuple(RecordedOnset(kind, strength, strength, loudness, presence) for kind, strength in due)
        frames.append(FeatureFrame(
            timestamp_us=int(round(now * 1e6)),
            energy=EnergyLanes(continuous=band, pre_agc=band, bubble=band, transient=transient),
            raw_bars=(0.0,) * 32, waveform=tuple(float(v) for v in np.clip(tail, -1.0, 1.0)), playing=True,
            visible=True, mode=LABEL_MODE, schema_version=REAL_SCALE_SCHEMA_VERSION,
            real=RealScaleLanes(live=tuple(min(2.5, 2.5 * v) for v in (*lanes, overall)),
                                musical_level=(loudness, presence), analysis_spectrum=analysis_spectrum(history),
                                events=tuple(TypedEvent(kind, strength) for kind, strength in sorted(kinds.items())),
                                onsets=onsets),
            capture_history=CaptureHistory(history.astype("<f4").tobytes(), capture_serial=k + 1, sample_rate=RATE),
        ))
    return frames


def load_source(source: str | Path):
    """(feature frames, fixture origin time) of a clip path or a ``synthetic:<id>`` source."""
    text = str(source)
    if text.startswith(SYNTHETIC_PREFIX):
        return synthetic_features(text[len(SYNTHETIC_PREFIX):]), START + PREROLL
    from widgets.spotify_visualizer.compact_clip import load_feature_clip
    frames = load_feature_clip(source).frames
    return frames, None


def synthetic_fixtures() -> tuple[StudioFixture, ...]:
    kinds = {"reference": REFERENCE, "synthetic": SYNTHETIC_KIND}
    return tuple(StudioFixture(fixture_id, label, kinds[kind], DURATION, description)
                 for fixture_id, (label, kind, description) in SYNTHETIC.items())


def source_of(fixture: StudioFixture) -> str:
    """What the worker analyses for ``fixture``: a recorded clip's path, else ``synthetic:<id>``."""
    return fixture.description if fixture.kind == RECORDED else SYNTHETIC_PREFIX + fixture.id


# ------------------------------------------------------------------------------------ the mode
@cache
def _owned_keys(mode_id: str) -> frozenset[str]:
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    from core.settings.visualizer_mode_settings import Custom, require_mode_settings
    from ui.tabs.media.technical_controls import _control_defs_for_mode, _storage_key
    from widgets.spotify_visualizer.source_config_applier import SPECTRUM_SOURCE_SUFFIXES
    spec = require_mode_settings(mode_id)
    stored = ({c.key for c in spec.controls}
              | {key for entry in spec.entries if isinstance(entry, Custom) for key in entry.keys})
    for family in ("shared_bar", "rainbow"):
        stored |= set(get_owned_mode_setting_keys(mode_id, family).values())
    engine = ({f"{mode_id}_{suffix}" for suffix in SPECTRUM_SOURCE_SUFFIXES}
              | {_storage_key(mode_id, d) for d in _control_defs_for_mode(mode_id)})
    return frozenset(stored - engine)


@dataclass(frozen=True)
class EngineAnswerMode:
    """One engine-processed mode as the worker and the Studio see it: everything follows from its id.

    ``conditional_reads``: engine getters (no arguments) the mode's step reads only under some mode-owned setting
    (Neon Lake's Terrain Reaction reads the musical level and the analysis spectrum only while it is on). The worker
    records them every tick, so turning that setting on in the Studio stays a mode-owned edit served from the
    record instead of an unrecorded read."""

    mode_id: str
    conditional_reads: tuple[str, ...] = ()

    @property
    def worker(self) -> str:
        return f"ui.studio.{self.mode_id}_recorded_inputs"

    def owned_keys(self) -> frozenset[str]:
        """Mode-owned settings (instant, exact): every stored key of the mode (spec controls, Custom rows, its
        shared bar and rainbow families) except those the production source projection hands the engine (the
        Spectrum source keys and the technical analysis). Proven per mode on the production replay."""
        return _owned_keys(self.mode_id)

    def engine_values(self, values: Mapping[str, Any]) -> dict:
        """The engine-owned subset of ``values``: the mode's stored keys (its descriptor prefixes) its own step
        does not read."""
        from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
        prefixes = tuple(get_visualizer_mode_descriptor(self.mode_id).setting_prefixes)
        owned = self.owned_keys()
        return {key: values[key] for key in sorted(values) if key.startswith(prefixes) and key not in owned}

    def engine_key(self, values: Mapping[str, Any]) -> str:
        return json.dumps(self.engine_values(values), sort_keys=True, default=repr)

    def own_signature(self, values: Mapping[str, Any]):
        return tuple(repr(values.get(key)) for key in sorted(self.owned_keys() | set(CONTEXT_KEYS)))

    def resolved_settings(self, values: Mapping[str, Any]) -> dict:
        out = dict(values)
        out["mode"] = self.mode_id
        return out

    def mode_kwargs(self, values: Mapping[str, Any]) -> dict:
        """The per-mode kwargs the production configuration applies (``configure_offline_controller``'s own steps),
        plus the 3D Detail tier the display hands the presentation (``scene3d_detail``) when the values carry it."""
        from dataclasses import asdict
        from core.settings.models import SpotifyVisualizerSettings
        from widgets.spotify_visualizer.source_config_applier import resolve_mode_source_config
        model = SpotifyVisualizerSettings.from_mapping(self.resolved_settings(values), apply_preset_overlay=False,
                                                       resolve_preset_indices=False)
        out = resolve_mode_source_config(self.mode_id, asdict(model))
        out.update(self.context(values))
        return out

    @staticmethod
    def context(values: Mapping[str, Any]) -> dict:
        return {key: values[key] for key in CONTEXT_KEYS if values.get(key) is not None}

    def configure(self, engine, values: Mapping[str, Any], *, environment=None):
        """A production runtime controller configured exactly as the offline replay configures one, then handed
        the display context production gives the presentation: the 3D Detail tier and, while the mode reflects,
        the photograph's backdrop (``ui.studio.environment.refresh_backdrop``)."""
        from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
        from ui.studio.replay_engine import offline_controller
        controller = offline_controller(engine, self.mode_id, self.resolved_settings(values))
        context = self.context(values)
        if context:
            apply_presentation_vis_mode_kwargs(controller.presentation_state, context)
        self.reflect(controller, environment)
        return controller

    def reflect(self, controller, environment) -> None:
        from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
        if get_visualizer_mode_descriptor(self.mode_id).backdrop_setting:
            from ui.studio.environment import refresh_backdrop
            refresh_backdrop(controller.presentation_state, self.mode_id, environment)


# ------------------------------------------------------------------------------------- extraction
def extract(mode: EngineAnswerMode, source: str | Path, settings: Mapping[str, Any], *,
            seconds: float | None = None, features=None, frames_out: list | None = None,
            environment=None) -> dict:
    """Replay ``source`` (a clip path or ``synthetic:<id>``) through the production offline replay under ``settings``
    and record, per tick, what the engine answered the mode's step and the digest of the frame that tick published.
    ``features``: already-loaded frames instead of ``source`` (tests); ``frames_out`` collects ``(now, frame)`` of
    the production ticks and ``environment`` is the photograph a reflecting mode mirrors (in-process callers only;
    the engine answers never depend on either)."""
    from PySide6.QtGui import QGuiApplication
    from widgets.spotify_visualizer.feature_replay import ReplayBeatEngine, deterministic_clock
    from widgets.spotify_visualizer.tick_pipeline import logical_tick
    from ui.studio.replay_engine import EngineAnswerRecorder

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
        controller = mode.configure(engine, settings, environment=environment)
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
                    for name in mode.conditional_reads:      # the same tick's answer, whether or not it was read
                        getattr(recorder, name)()
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
        raise RuntimeError(f"The source never published a {mode.mode_id} frame")
    start = float(records[0]["now_ts"]) if origin is None else float(origin)
    return {"source": str(source), "origin": start, "duration": float(records[-1]["now_ts"] - start),
            "engine_values": mode.engine_values(settings), "steps": records}


def to_inputs(data: Mapping[str, Any], fixture) -> "RecordedInputs":
    steps = tuple(ServedTick(now=float(s["now_ts"]), playing=bool(s["playing"]), answers=s["answers"])
                  for s in data["steps"])
    return RecordedInputs(fixture, steps, float(data["origin"]), source=str(data["source"]),
                          engine_values=dict(data["engine_values"]))


def worker_main(mode: EngineAnswerMode, argv: list[str]) -> int:
    """``<mode>_recorded_inputs.main``: ``source settings.json output.json [seconds]``."""
    source, settings_path, output_path, *rest = argv
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from ui.studio.waveform_recorded_inputs import CLIP_SECONDS
    settings = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    from PySide6.QtGui import QGuiApplication
    _app = QGuiApplication.instance() or QGuiApplication([])     # this process is the analysis worker
    data = extract(mode, source, settings, seconds=float(rest[0]) if rest else CLIP_SECONDS)
    Path(output_path).write_text(json.dumps(data), encoding="utf-8")
    return 0


# ----------------------------------------------------------------------------------------- inputs
@dataclass(frozen=True)
class ServedTick:
    """One production tick: its time, the playback flag and what the engine answered the step (encoded)."""

    now: float
    playing: bool
    answers: Mapping[str, Any]


class RecordedInputs:
    """Engine answers for one source under one set of engine-owned values (the mode's worker)."""

    def __init__(self, fixture: StudioFixture, steps: tuple[ServedTick, ...], origin: float, *, source: str,
                 engine_values: Mapping[str, Any]) -> None:
        self.fixture = fixture
        self._steps = steps
        self._origin = origin
        self.source = source
        self.engine_values = dict(engine_values)
        self.key = (source, json.dumps(self.engine_values, sort_keys=True, default=repr))
        self._levels: list[float] | None = None

    def steps(self, until: float) -> Iterable[ServedTick]:
        limit = self._origin + until + 1e-9
        for step in self._steps:
            if step.now > limit:
                return
            yield step

    def levels(self) -> list[tuple[float, float]]:
        """(fixture time, mean engine bar) per tick, for the transport's overview."""
        if self._levels is None:
            from ui.studio.replay_engine import decode_answer
            out = []
            for step in self._steps:
                bars = decode_answer(step.answers.get("get_smoothed_bars", {"list": []})) or [0.0]
                out.append((step.now - self._origin, sum(bars) / len(bars)))
            self._levels = out
        return self._levels


class RestInputs:
    """No answers yet (the first analysis is running): the mode's paused, sourceless resting scene, which is what
    the card shows with no audio. Every getter then answers from the freshly configured engine."""

    def __init__(self, fixture: StudioFixture) -> None:
        self.fixture = fixture
        self._origin = 0.0
        self.source = ""
        self.engine_values: dict = {}
        self.key = ("", "")

    def steps(self, until: float) -> Iterable[ServedTick]:
        yield ServedTick(now=0.0, playing=False, answers={})

    def levels(self) -> list:
        return []


# Analysed answers for this process, per mode, keyed by (source, engine-owned values), newest last.
_ANALYSED: dict[str, dict] = {}
ANALYSED_LIMIT = 24


def analysed_cache(mode_id: str) -> dict:
    return _ANALYSED.setdefault(mode_id, {})


def remember(mode_id: str, inputs: RecordedInputs) -> None:
    store = analysed_cache(mode_id)
    store.pop(inputs.key, None)
    store[inputs.key] = inputs
    while len(store) > ANALYSED_LIMIT:
        store.pop(next(iter(store)))


def analysed(mode_id: str, key) -> RecordedInputs | None:
    return analysed_cache(mode_id).get(key)


def worker_loader(mode: EngineAnswerMode):
    """``loader(fixture, values, finished)``: analyse ``fixture``'s source out of process (``ClipLoadJob`` passes the
    description as the source)."""
    def load(fixture: StudioFixture, values: Mapping[str, Any], finished: Callable[..., None]):
        from dataclasses import replace
        from ui.studio.waveform_recorded_inputs import ClipLoadJob
        return ClipLoadJob(replace(fixture, description=source_of(fixture)), values, finished, module=mode.worker,
                           convert=to_inputs)
    return load


def start_clip_load(mode: EngineAnswerMode, clip: StudioFixture, values: Mapping[str, Any], finished):
    """An adapter's ``start_clip_load``: ``clip`` analysed under ``values``' engine-owned settings out of process
    (cached per engine values); None when the cached result already finished."""
    cached = analysed(mode.mode_id, (source_of(clip), mode.engine_key(values)))
    if cached is not None:
        finished(cached, "")
        return None

    def remembered(result, error=""):
        if result is not None and not error:
            remember(mode.mode_id, result)
        finished(result, error)
    return worker_loader(mode)(clip, values, remembered)


# -------------------------------------------------------------------------------------- evaluator
class EngineAnswerEvaluator:
    """A mode's production step and capture, run in process from recorded engine answers.

    ``loader(fixture, values, finished)`` starts one analysis (default: the out-of-process worker) and returns a
    cancellable job, or None when it already called ``finished(inputs, error)``."""

    def __init__(self, mode: EngineAnswerMode, loader: Callable | None = None) -> None:
        self.mode = mode
        self._loader = loader or worker_loader(mode)
        self._builtin = synthetic_fixtures()
        self._clips: dict[str, StudioFixture] = {}
        self._fixture = next(f for f in self._builtin if f.id == "mid")
        self._inputs = None            # the inputs the current history replays
        self._controller = None
        self._engine = None
        self._view = None
        self._extent: tuple[float, float] | None = None
        self._environment = None
        self._invalidate: Callable[[], None] | None = None
        self._job = None
        self._job_key = None
        self.errors: dict = {}
        self._last_wanted = None
        self.steps_run = 0
        self.replays = 0
        self.rewinds = 0
        self._budget: float | None = None
        self._kwargs_cache: dict = {}
        self._shown = None                 # the frame the last evaluation returned (shown while converging)
        self._reset_history()

    # fixtures ---------------------------------------------------------------
    def fixtures(self) -> tuple[StudioFixture, ...]:
        return self._builtin + tuple(self._clips.values())

    @property
    def fixture(self) -> StudioFixture:
        return self._fixture

    def add_recorded(self, inputs: RecordedInputs) -> None:
        """A recorded clip analysed through the controller's clip loader (``start_clip_load``)."""
        self._clips[inputs.fixture.id] = inputs.fixture
        remember(self.mode.mode_id, inputs)

    def select(self, fixture_id: str) -> StudioFixture:
        fixture = next((f for f in self.fixtures() if f.id == fixture_id), None)
        if fixture is None:
            raise KeyError(fixture_id)
        self._fixture = fixture
        self._retire()
        self._shown = None
        return fixture

    def set_viewport_extent(self, extent) -> None:
        """The capture reads the card's presented height (segment count, height scale): a new extent replays the
        history at it. The engine answers do not depend on it."""
        extent = None if extent is None else (float(extent[0]), float(extent[1]))
        if extent != self._extent:
            self._extent = extent
            self._retire()

    def set_environment(self, image) -> None:
        """The photograph a reflecting mode mirrors (``ui.studio.environment``); a change replays. A mode with no
        backdrop setting never holds one."""
        from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
        if not get_visualizer_mode_descriptor(self.mode.mode_id).backdrop_setting:
            return
        self._environment = image
        self._retire()

    def set_invalidate(self, callback: Callable[[], None] | None) -> None:
        """The Studio's re-evaluate request, called when a background analysis lands."""
        self._invalidate = callback

    @property
    def analysing(self) -> bool:
        return self._job is not None

    @property
    def analysis_failure(self) -> str:
        """Why the analysis the current values need failed ("" when it did not); the previous answers stay on
        screen meanwhile (``_choose_inputs``) and nothing re-runs it until ``retry_analysis``."""
        return str(self.errors.get(self._last_wanted, "")) if self._last_wanted is not None else ""

    def retry_analysis(self) -> None:
        """Forget the failure of the analysis the current values need: the next evaluation starts it again."""
        self.errors.pop(self._last_wanted, None)

    # analysis ----------------------------------------------------------------
    def _wanted(self, values: Mapping[str, Any]):
        return (source_of(self._fixture), self.mode.engine_key(values))

    def _analyse(self, values: Mapping[str, Any], wanted) -> None:
        if self._job_key == wanted or wanted in self.errors:
            return
        self._cancel_job()
        fixture = self._fixture
        self._job_key = wanted

        def finished(result, error: str = "") -> None:
            if self._job_key != wanted:
                return
            self._job, self._job_key = None, None
            if error or result is None:
                self.errors[wanted] = error or "analysis failed"
                from core.logging.logger import get_logger
                get_logger(__name__).error("[STUDIO] %s analysis of %s failed: %s", self.mode.mode_id, wanted[0],
                                           self.errors[wanted])
            else:
                remember(self.mode.mode_id, result)
            if self._invalidate is not None:
                self._invalidate()
        job = self._loader(fixture, dict(values), finished)
        if self._job_key == wanted:          # still running (a synchronous loader already finished)
            self._job = job

    def _cancel_job(self) -> None:
        job, self._job, self._job_key = self._job, None, None
        if job is not None:
            job.cancel()

    def _choose_inputs(self, values: Mapping[str, Any], exact: bool):
        mode_id = self.mode.mode_id
        wanted = self._wanted(values)
        self._last_wanted = wanted
        inputs = analysed(mode_id, wanted)
        if inputs is None and (exact or self._inputs is None):
            self._analyse(values, wanted)
            inputs = analysed(mode_id, wanted)
        if inputs is None:
            current = self._inputs
            if current is not None and current.source == wanted[0]:
                return current
            latest = [i for k, i in analysed_cache(mode_id).items() if k[0] == wanted[0]]
            return latest[-1] if latest else RestInputs(self._fixture)
        return inputs

    # lifecycle --------------------------------------------------------------
    def set_frame_budget(self, seconds: float | None) -> None:
        """The GUI-thread time one evaluation may spend replaying (the Studio sets it; None: replay at once).
        With a budget an exact replay that does not fit continues on the next frames (``converging``) while the
        live-applied frame stays on screen; the replay it converges to is the same exact replay."""
        self._budget = None if seconds is None else max(0.0, float(seconds))

    @property
    def converging(self) -> bool:
        """An exact replay is still catching up with the requested instant (the Studio asks for another frame)."""
        return self._converging

    def _reset_history(self) -> None:
        self._ticks: tuple = ()
        self._index = 0                    # the next tick to step
        self._time = -math.inf             # the fixture time the history has been stepped to
        self._last = None
        self._last_tick: ServedTick | None = None
        self._signature = None
        self._approximate = False
        self._pristine = None              # the step state right after configuration (``StepState``)
        self._pristine_signature = None
        self._checkpoints: dict = {}       # mode-owned signature -> {tick index: checkpoint}
        self._converging = False

    def _retire(self) -> None:
        controller, self._controller = self._controller, None
        if controller is not None:
            runtime = controller.peek_logical_mode_state(self.mode.mode_id)
            retire = getattr(runtime, "retire", None)
            if callable(retire):
                retire()
        self._reset_history()

    def _effective(self, values: Mapping[str, Any], inputs) -> dict:
        """``values`` with the engine-owned values the answers were recorded under (an analysis still running
        keeps the previous answers *and* their configuration, so bar count and shape stay consistent)."""
        out = dict(values)
        out.update(inputs.engine_values)
        return out

    def _start(self, values: Mapping[str, Any], inputs) -> None:
        """A production controller configured for ``inputs`` (lifecycle: a new fixture, answers, extent or
        photograph)."""
        from widgets.spotify_visualizer.feature_replay import ReplayBeatEngine
        from ui.studio.replay_engine import RecordedEngineAnswers, StepState
        self._retire()
        if self._engine is None:
            self._engine = ReplayBeatEngine(32)
        controller = self.mode.configure(self._engine, self._effective(values, inputs), environment=self._environment)
        if self._extent is not None:
            controller.hydrate_committed_layout_metrics(self._extent, 0)
        self._view = RecordedEngineAnswers(self._engine)
        controller.engine = self._view
        self._controller = controller
        self._inputs = inputs
        self._ticks = tuple(inputs.steps(self.fixture.duration))
        self._signature = self._pristine_signature = self.mode.own_signature(values)
        self._pristine = StepState(controller, keep=(self._engine, self._view))
        self.replays += 1

    def _step(self, tick: ServedTick) -> None:
        """One production tick: what ``tick_pipeline.logical_tick`` runs (``consume_engine_bars``, the teardown
        readiness query, the mode's logical tick hook when it has one, the publication capture) at the tick's
        time."""
        from widgets.spotify_visualizer.logical_frame_capture import capture_visualizer_logical_frame
        from widgets.spotify_visualizer.tick_pipeline import consume_engine_bars
        controller = self._controller
        controller.playing = tick.playing
        self._view.serve(tick.answers)
        state = controller.logical_tick_state
        now = float(tick.now)
        changed, _any = consume_engine_bars(state, now)
        ready = bool(state._check_mode_teardown_ready(state._engine, now))
        if state._waiting_for_fresh_engine_frame or (state._mode_teardown_block_until_ready
                                                     and not state._mode_transition_ready):
            raise RuntimeError("The Studio step reached a fresh-frame fence the offline replay never arms")
        hook = controller.active_logical_tick_hook
        if hook is not None:
            hook(state, now)                       # a mode's own logical step (DevCurve's dispatch_devcurve_field)
        frame = capture_visualizer_logical_frame(state, now_ts=now, changed=changed, mode_reveal_ready=ready)
        self.steps_run += 1
        self._last_tick = tick
        if frame is not None:
            self._last = frame

    def _mode_kwargs_for(self, values: Mapping[str, Any], signature) -> dict:
        """The production mode kwargs for ``values`` under the current answers, computed once per signature
        (``EngineAnswerMode.mode_kwargs`` builds the settings model, about 10 ms)."""
        key = (self._inputs.key, signature)
        cache = self._kwargs_cache
        if key not in cache:
            cache[key] = self.mode.mode_kwargs(self._effective(values, self._inputs))
            while len(cache) > 6:
                cache.pop(next(iter(cache)))
        return cache[key]

    def _restyle(self, values: Mapping[str, Any], signature=None) -> None:
        from widgets.spotify_visualizer.config_applier import (
            apply_logical_vis_mode_kwargs, apply_presentation_vis_mode_kwargs,
        )
        signature = self.mode.own_signature(values) if signature is None else signature
        kwargs = self._mode_kwargs_for(values, signature)
        apply_logical_vis_mode_kwargs(self._controller.logical_tick_state, kwargs)
        apply_presentation_vis_mode_kwargs(self._controller.presentation_state, kwargs)
        self.mode.reflect(self._controller, self._environment)
        self._signature = signature

    # exact history: rewinds and checkpoints ------------------------------------
    CHECKPOINT_TICKS = 90                  # one checkpoint per second of fixture time (production cadence 90 Hz)

    def _rewind(self, values: Mapping[str, Any], signature, time: float) -> None:
        """Put the exact history of ``signature`` at the latest checkpoint at or before ``time`` (else at the
        pristine configuration, restyled to ``values``): the replay from there is the replay from the start."""
        best = None
        for checkpoint in self._checkpoints.get(signature, {}).values():
            if checkpoint[1] <= time + 1e-9 and (best is None or checkpoint[0] > best[0]):
                best = checkpoint
        if best is not None:
            index, at, state, last, last_tick = best
            state.restore()
            self._index, self._time, self._last, self._last_tick = index, at, last, last_tick
            self._signature = signature
        else:
            self._pristine.restore()
            self._index, self._time, self._last, self._last_tick = 0, -math.inf, None, None
            self._signature = self._pristine_signature
            if signature != self._pristine_signature:
                self._restyle(values, signature)
        self._approximate = False
        self.rewinds += 1

    def _checkpoint(self) -> None:
        from ui.studio.replay_engine import StepState
        checkpoints = self._checkpoints
        if self._signature not in checkpoints:
            checkpoints[self._signature] = {}
            while len(checkpoints) > 3:    # the current values and the last two (undo / redo stay instant)
                checkpoints.pop(next(iter(checkpoints)))
        at = self._ticks[self._index - 1].now - self._inputs._origin
        checkpoints[self._signature][self._index] = (
            self._index, at, StepState(self._controller, keep=(self._engine, self._view)), self._last,
            self._last_tick)

    def _advance(self, time: float, deadline: float | None) -> tuple[bool, int]:
        """Step the production ticks up to ``time`` (the first tick always), or until ``deadline``.
        Returns (reached, ticks stepped)."""
        import time as clock
        origin = self._inputs._origin
        ticks = self._ticks
        stepped = 0
        while self._index < len(ticks):
            tick = ticks[self._index]
            if tick.now - origin > time + 1e-9 and self._last is not None:
                break
            if deadline is not None and stepped and clock.perf_counter() > deadline:
                self._time = ticks[self._index - 1].now - origin
                return False, stepped
            self._step(tick)
            self._index += 1
            stepped += 1
            if not self._approximate and self._index % self.CHECKPOINT_TICKS == 0:
                self._checkpoint()
        self._time = time
        return True, stepped

    def evaluate(self, time: float, values: Mapping[str, Any], *, exact: bool = True, revision: Any = None):
        """The logical frame ``time`` seconds into the fixture under ``values``: the mode's production step replayed
        from the fixture start over the engine answers for these engine-owned values (equal fixture, values, extent
        and time give equal frames). A mode-owned change replays exactly from the pristine configuration (or a
        checkpoint of the same values); an engine-owned change starts its analysis and shows the previous answers
        until it lands. ``exact=False`` (a live gesture) applies a mode-owned change to the running history from
        the current tick; the gesture end replays exactly. With a frame budget the exact replay may take several
        evaluations (``converging``), showing the live-applied frame meanwhile."""
        del revision
        import time as clock
        deadline = None if self._budget is None else clock.perf_counter() + self._budget
        time = max(0.0, min(float(time), self.fixture.duration))
        inputs = self._choose_inputs(values, exact)
        signature = self.mode.own_signature(values)
        if self._controller is None or inputs is not self._inputs:
            self._start(values, inputs)
        if not exact:
            if time < self._time:
                self._rewind(values, signature, time)
            restyled = signature != self._signature
            if restyled:
                self._restyle(values, signature)
                self._approximate = True
            _reached, stepped = self._advance(time, None)
            if restyled and not stepped and self._last_tick is not None:
                self._step(self._last_tick)            # show the change on this instant (approximate)
            self._converging = False
            self._shown = self._last
            return self._last
        if signature != self._signature or self._approximate or time < self._time:
            if deadline is not None and signature != self._signature:
                # A change nothing has shown yet (a click, a typed value): this frame shows it live-applied on
                # the running history; the exact replay starts on the next frame.
                self._restyle(values, signature)
                self._approximate = True
                if self._last_tick is not None:
                    self._step(self._last_tick)
                self._converging = True
                self._shown = self._last
                return self._shown
            self._rewind(values, signature, time)
        reached, _stepped = self._advance(time, deadline)
        self._converging = not reached
        if reached or self._shown is None:
            self._shown = self._last
        if self._shown is None:
            raise RuntimeError("Fixture produced no logical frame")
        return self._shown

    @property
    def unrecorded_reads(self) -> int:
        """Engine reads the record lacked in this history (``RecordedEngineAnswers.unrecorded``)."""
        return 0 if self._view is None else int(self._view.unrecorded)

    def _overview(self):
        """The answers the transport's overview shows: those wanted for the current values once they landed."""
        wanted = self._last_wanted
        inputs = (analysed(self.mode.mode_id, wanted)
                  if wanted is not None and wanted[0] == source_of(self._fixture) else None)
        current = self._inputs
        if inputs is None and current is not None and current.source == source_of(self._fixture):
            inputs = current
        return inputs

    @property
    def timeline_revision(self):
        overview = self._overview()
        return None if overview is None else overview.key

    def timeline(self, samples: int = 240) -> list[float]:
        duration = max(1e-6, self.fixture.duration)
        levels = [0.0] * samples
        source = self._overview()
        for t, level in (source.levels() if source is not None else ()):
            if 0.0 <= t <= duration:
                index = min(samples - 1, int(t / duration * samples))
                levels[index] = max(levels[index], level)
        peak = max(levels) or 1.0
        return [round(v / peak, 4) for v in levels]

    def measurements(self) -> dict[str, dict[str, float]]:
        frame = self._last
        if frame is None:
            return {"sources": {}, "targets": {}, "signals": {}}
        bars = frame.common.bars or (0.0,)
        peaks = frame.mode_state.peaks or (0.0,)
        ghosts = frame.mode_state.ghost_bars or (0.0,)
        return {"sources": {}, "targets": {}, "signals": {
            "Level": sum(bars) / len(bars), "Peak": max(peaks), "Ghost": sum(ghosts) / len(ghosts)}}

    def release(self) -> None:
        self._cancel_job()
        self._retire()
        self._invalidate = None
        engine, self._engine = self._engine, None
        if engine is not None:
            try:
                engine.force_stop()
            except Exception:
                pass
            engine.deleteLater()


__all__ = [
    "CONTEXT_KEYS", "DURATION", "EngineAnswerEvaluator", "EngineAnswerMode", "RecordedInputs", "RestInputs",
    "SYNTHETIC", "SYNTHETIC_PREFIX", "ServedTick", "analysed", "analysed_cache", "extract", "frame_digest",
    "load_source", "remember", "source_of", "start_clip_load", "synthetic_features", "synthetic_fixtures",
    "synthetic_score", "to_inputs", "worker_loader", "worker_main",
]
