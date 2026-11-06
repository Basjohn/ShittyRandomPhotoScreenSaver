"""Seamless loops for the Visualizer Studios' shipped clips: choose the loop points, bake the seam, measure it.

    from tools.studio_clip_loop import choose_loop, bake_loop, seam_report

A Studio clip is a window of a native recording that the Studio's transport plays over and over. A clip that simply
restarts jumps at the wrap: its audio (the capture stream every mode's analysis reads), its lanes and the picture
all start over. A loop clip is built so that the *wrap is not an event*:

* **Loop points** (``choose_loop``): the window start ``s`` and the period ``P = e - s`` are searched so the music
  before ``e`` resembles the music before ``s`` (onset-envelope correlation, level and spectrum), which for a steady
  groove means ``P`` is a whole number of beats. The search honours the span the clip is for.
* **Baked seam** (``bake_loop``): the last ``fade`` seconds of the loop are an equal-power crossfade of the source
  just before ``e`` into the source just *before* ``s``, so the sample after the last one is the source's own next
  sample, ``src[s]``. The capture stream is periodic with period ``N`` samples (every frame's history, the first
  frames' included, is read from that periodic stream); the per-frame lanes are mixed with the same weights (power
  complementary) and the discrete onsets / events follow whichever source is louder in the mix.
* **Measured** (``seam_report``): the sample step at the seam against the music's own steps, RMS and spectral-flux
  continuity across it, and the beat grid across it (onset peaks' phase against the clip's beat period).

Pure NumPy; no Qt. The shipped-clip builder (``tools/build_studio_clips.py``) is the caller.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

SAMPLE_RATE = 48000
HOP = 480                      # 10 ms analysis hop
WINDOW = 2048


# ---------------------------------------------------------------------------------------- analysis
def onset_envelope(samples: np.ndarray, hop: int = HOP, window: int = WINDOW):
    """(spectral flux, rms, log band energies) at one value per ``hop`` samples: the half-wave rectified change of a
    24-band log spectrum (an onset-strength curve), the window RMS and the log spectrum itself."""
    x = np.asarray(samples, dtype=np.float64)
    count = (len(x) - window) // hop
    if count < 2:
        raise ValueError("too few samples to analyse")
    index = np.arange(window)[None, :] + hop * np.arange(count)[:, None]
    frames = x[index]
    magnitudes = np.abs(np.fft.rfft(frames * np.hanning(window), axis=1))
    edges = np.unique(np.geomspace(2, magnitudes.shape[1] - 1, 25).astype(int))
    bands = np.stack([magnitudes[:, a:b].sum(1) for a, b in zip(edges[:-1], edges[1:])], 1)
    log_bands = np.log1p(bands * 10.0)
    flux = np.maximum(0.0, np.diff(log_bands, axis=0, prepend=log_bands[:1])).sum(1)
    rms = np.sqrt((frames ** 2).mean(1))
    return flux, rms, log_bands


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    d = math.sqrt(float((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / d) if d > 0.0 else 0.0


def beat_period(flux: np.ndarray, lo: float = 0.25, hi: float = 1.0) -> tuple[float, float]:
    """(seconds, strength) of the strongest periodicity of an onset curve between ``lo`` and ``hi`` seconds per
    beat (autocorrelation, parabolic peak), strength 0..1."""
    f = flux - flux.mean()
    ac = np.correlate(f, f, "full")[len(f) - 1:]
    ac = ac / ac[0]
    a, b = int(lo * SAMPLE_RATE / HOP), int(hi * SAMPLE_RATE / HOP)
    lag = int(np.argmax(ac[a:b])) + a
    if 0 < lag < len(ac) - 1:
        y0, y1, y2 = ac[lag - 1], ac[lag], ac[lag + 1]
        denominator = y0 - 2.0 * y1 + y2
        shift = 0.5 * (y0 - y2) / denominator if denominator else 0.0
    else:
        shift = 0.0
    return (lag + shift) * HOP / SAMPLE_RATE, float(ac[lag])


def refine_beat(flux: np.ndarray, tempo: float, reach: float = 0.01, steps: int = 81) -> tuple[float, float]:
    """``tempo`` refined (within +-``reach``, relative) to the period whose comb over the whole onset curve is most
    coherent: a loop is judged on beat phases tens of beats apart, which a 0.2 % error in the period would skew
    by tens of milliseconds. Returns (seconds, whole-curve coherence)."""
    seconds = (np.arange(len(flux)) * HOP + WINDOW / 2) / SAMPLE_RATE
    total = max(float(flux.sum()), 1e-12)
    best = (0.0, tempo)
    for candidate in tempo * (1.0 + np.linspace(-reach, reach, steps)):
        coherence = abs((flux * np.exp(2j * math.pi * seconds / candidate)).sum()) / total
        best = max(best, (float(coherence), float(candidate)))
    return best[1], best[0]


def running_grid(flux: np.ndarray, tempo: float, width: int) -> tuple[np.ndarray, np.ndarray]:
    """Per hop ``i``: (beat phase in ms, coherence) of the grid over ``flux[i - width:i]`` (the music up to there)."""
    seconds = (np.arange(len(flux)) * HOP + WINDOW / 2) / SAMPLE_RATE
    rotated = np.concatenate([[0j], np.cumsum(flux * np.exp(2j * math.pi * seconds / tempo))])
    weight = np.concatenate([[0.0], np.cumsum(flux)])
    index = np.arange(len(flux) + 1)
    low = np.maximum(0, index - width)
    vector = (rotated[index] - rotated[low]) / np.maximum(weight[index] - weight[low], 1e-12)
    return np.angle(vector) / (2 * math.pi) * tempo * 1000.0, np.abs(vector)


# ------------------------------------------------------------------------------------- source frames
@dataclass(frozen=True)
class Source:
    """A recording's frames with its continuous capture stream and each frame's history end in that stream."""

    frames: tuple
    stream: np.ndarray            # float32 mono, gapless
    starts: np.ndarray            # per frame: history start in ``stream``
    ends: np.ndarray              # per frame: history end in ``stream``
    seconds: np.ndarray           # per frame: timestamp, seconds from the first frame

    @classmethod
    def of(cls, frames) -> "Source":
        from widgets.spotify_visualizer.compact_clip import _history_stream
        frames = tuple(frames)
        stream, slices = _history_stream(frames)
        first = frames[0].timestamp_us
        return cls(frames, stream, np.array([s for s, _ in slices], dtype=np.int64),
                   np.array([e for _, e in slices], dtype=np.int64),
                   np.array([(f.timestamp_us - first) / 1e6 for f in frames]))

    def index_at(self, seconds: float) -> int:
        return int(np.searchsorted(self.seconds, seconds))


@dataclass(frozen=True)
class LoopChoice:
    first: int                    # source frame index of the loop's first frame (``s``)
    after: int                    # source frame index of the frame that restarts the loop (``e``)
    fade_s: float                 # crossfade length
    shift: int = 0                # samples added to the period (a sample-level phase alignment of the seam)
    score: float = 0.0
    detail: tuple = ()


def _fade_samples(fade_s: float) -> int:
    return int(round(fade_s * SAMPLE_RATE))


# --------------------------------------------------------------------------------------- the search
def choose_loop(source: Source, *, span: tuple[float, float] | None, period: tuple[float, float], fade_s: float,
                align: int = 96, top: int = 1, grid_limit_ms: float | None = 15.0):
    """The loop points whose seam resembles the music before the start best.

    ``span``: seconds of the recording the loop must contain (the passage the clip is for). ``period``: the loop
    length range in seconds. The score is the onset-envelope correlation of the ``fade_s`` before ``e`` with the
    ``fade_s`` before ``s`` (the two sources the crossfade blends), less the level difference (dB) and the mean
    log-spectrum difference of the two. ``align`` samples either way are then searched for the waveform
    correlation peak (so the blended sources add in phase)."""
    flux, rms, log_bands = onset_envelope(source.stream)
    groove, strength = beat_period(flux)
    groove, strength = refine_beat(flux, groove)
    width = int(2.0 * SAMPLE_RATE / HOP)
    phase, coherence = running_grid(flux, groove, width)
    per_frame = np.maximum(1, int(round(fade_s * SAMPLE_RATE / HOP)))
    seconds_per_hop = HOP / SAMPLE_RATE
    # hop index of a frame = its history end (the audio the loop is blended from) in 10 ms hops
    hop_of = lambda frame: int((source.ends[frame] - WINDOW // 2) // HOP)   # noqa: E731
    ranked: list = []
    lo, hi = (source.index_at(span[0]), source.index_at(span[1])) if span else (len(source.frames) - 1, 0)
    for first in range(max(0, source.index_at(fade_s + 0.25)), lo + 1):
        for after in range(max(hi, first + 1), len(source.frames)):
            length = source.seconds[after] - source.seconds[first]
            if length < period[0]:
                continue
            if length > period[1]:
                break
            s, e = hop_of(first), hop_of(after)
            if s - per_frame < 0 or e + 1 > len(flux):
                continue
            a, b = slice(s - per_frame, s), slice(e - per_frame, e)
            correlation = _ncc(flux[a], flux[b])
            level = abs(20.0 * math.log10(rms[a].mean() + 1e-9) - 20.0 * math.log10(rms[b].mean() + 1e-9))
            spectrum = float(np.abs(log_bands[a].mean(0) - log_bands[b].mean(0)).mean())
            offset = abs(((phase[s] - phase[e] + groove * 500.0) % (groove * 1000.0)) - groove * 500.0)
            reliable = min(1.0, min(coherence[s], coherence[e]) / max(strength, 0.05))
            grid = offset / (groove * 500.0) * reliable                  # 0 (in phase) .. 1 (half a beat out)
            if s + width < len(phase):                                   # the groove must also carry on past s
                natural = abs(((phase[s + width] - phase[s] + groove * 500.0) % (groove * 1000.0)) - groove * 500.0)
                grid += natural / (groove * 500.0) * min(1.0, min(coherence[s], coherence[s + width])
                                                           / max(strength, 0.05))
            if grid_limit_ms is not None and reliable >= 0.5 and offset > grid_limit_ms:
                continue                  # a groove that is there must line up: the blend would double its beats
            score = correlation - 0.05 * level - 0.5 * spectrum - 2.0 * grid
            ranked.append((score, first, after, (correlation, level, spectrum, offset)))
    if not ranked:
        raise ValueError("no loop in the requested span and period")
    ranked.sort(key=lambda item: -item[0])
    chosen, taken = [], []
    for score, first, after, detail in ranked:        # distinct loops: not within 1 s of a better one
        if any(abs(source.seconds[first] - source.seconds[f]) < 1.0 and abs(source.seconds[after] - source.seconds[a]) < 1.0
               for f, a in taken):
            continue
        taken.append((first, after))
        shift = align_seam(source, first, after, fade_s, align) if align else 0
        chosen.append(LoopChoice(first, after, fade_s, shift, float(score), tuple(detail)))
        if len(chosen) >= top:
            break
    return chosen[0] if top == 1 else chosen


def align_seam(source: Source, first: int, after: int, fade_s: float, reach: int) -> int:
    """Samples (|shift| <= ``reach``) to add to the loop period so the waveform before ``e`` lines up with the
    waveform before ``s`` (low-passed, so a bass line's phase decides, not the hiss)."""
    length = _fade_samples(fade_s)
    r0 = int(source.ends[first])
    r1 = int(source.ends[after])
    if r0 - length - reach < 0 or r1 + reach > len(source.stream):
        return 0
    x = source.stream.astype(np.float64)
    kernel = np.ones(24) / 24.0                                      # ~2 kHz low-pass (box, enough for phase)
    lowpassed = np.convolve(x, kernel, mode="same")
    reference = lowpassed[r0 - length:r0]
    reference = reference - reference.mean()
    scores = []
    for shift in range(-reach, reach + 1):
        candidate = lowpassed[r1 - length + shift:r1 + shift]
        candidate = candidate - candidate.mean()
        d = math.sqrt(float((reference ** 2).sum() * (candidate ** 2).sum()))
        scores.append((float((reference * candidate).sum() / d) if d else -1.0, -abs(shift), shift))
    return int(max(scores)[2])


# ---------------------------------------------------------------------------------------- the bake
def _mix(a, b, wa, wb):
    return a * wa + b * wb


def _level_match(mixed: np.ndarray, tail: np.ndarray, lead: np.ndarray, theta: np.ndarray) -> np.ndarray:
    """The smooth gain that gives the crossfade the level an equal-power blend of its two sources would have.

    Equal-power weights keep the level of *uncorrelated* sources; sources that are alike (which the loop points are
    chosen for) add up to 3 dB louder in the middle of the blend. The gain is the ratio of the equal-power target
    (the two sources' 50 ms RMS under the cos / sin weights) to the mix's own 50 ms RMS, interpolated between window
    centres, clipped, and brought to exactly 1 over the first and last 5 ms so the blend joins both sides sample for
    sample."""
    window, hop = 2400, 480
    count = len(mixed)

    def rms(x, start):
        return math.sqrt(float(np.mean(x[start:start + window] ** 2)) + 1e-18)
    starts = np.arange(0, max(1, count - window + 1), hop)
    centres = starts + window / 2.0
    gains = []
    for start in starts:
        weight = float(theta[min(count - 1, start + window // 2)])
        target = math.sqrt(math.cos(weight) ** 2 * rms(tail, start) ** 2 + math.sin(weight) ** 2 * rms(lead, start) ** 2)
        gains.append(min(1.5, max(0.5, target / rms(mixed, start))))
    gain = np.interp(np.arange(count), centres, gains)
    edge = np.minimum(1.0, np.minimum(np.arange(count) + 1, count - np.arange(count)) / 240.0)
    return 1.0 + (gain - 1.0) * edge


def bake_loop(source: Source, choice: LoopChoice):
    """The loop's frames (``choice.first`` .. ``choice.after - 1``) with the baked seam, and the loop's period.

    Returns ``(frames, period_us, info)``. The stream is periodic in ``N`` samples: ``body[k] = src[r0 + k]``,
    except the last ``fade`` samples, where ``body[k] = cos(t) * src[r0 + k] + sin(t) * src[r0 + k - N]`` as ``t``
    runs 0 -> pi / 2, so ``body[N]`` (= ``body[0]`` of the next pass) is ``src[r0]``, the sample that follows
    ``src[r0 - 1]`` in the music."""
    from widgets.spotify_visualizer.compact_clip import _preview
    from widgets.spotify_visualizer.feature_frame import (
        BandEnergy, CaptureHistory, EnergyLanes, FeatureFrame, RealScaleLanes, TransientEnergy,
    )
    first, after = choice.first, choice.after
    r0 = int(source.ends[first])
    period = int(source.ends[after] - r0) + int(choice.shift)
    length = _fade_samples(choice.fade_s)
    if r0 - length < 0 or period <= 2 * length:
        raise ValueError("the loop is too short for its crossfade")
    stream = source.stream.astype(np.float64)
    body = stream[r0:r0 + period].copy()
    if len(body) < period:
        raise ValueError("the source ends before the loop does")
    theta = (np.arange(length) + 0.5) / length * (math.pi / 2.0)
    tail, lead = body[period - length:].copy(), stream[r0 - length:r0]
    mixed = np.cos(theta) * tail + np.sin(theta) * lead
    body[period - length:] = mixed * _level_match(mixed, tail, lead, theta)
    body = body.astype(np.float32)
    count = after - first
    base = source.frames[first]
    out = []
    max_history = 4096
    for j in range(count):
        frame = source.frames[first + j]
        position = int(source.ends[first + j] - r0)            # the frame's history end, in loop samples
        size = int(source.ends[first + j] - source.starts[first + j])
        fade = (position - (period - length)) / length          # 0..1 across the crossfade
        weight_in = 0.0 if fade <= 0.0 else min(1.0, fade)
        wa, wb = math.cos(weight_in * math.pi / 2.0) ** 2, math.sin(weight_in * math.pi / 2.0) ** 2
        other = source.frames[first + j - count] if first + j - count >= 0 else frame
        dominant = other if wb > wa else frame
        indices = (np.arange(position - size, position) % period)
        history = body[indices]
        energy, twin = frame.energy, other.energy

        def band(name):
            x, y = getattr(energy, name), getattr(twin, name)
            return BandEnergy(*(min(1.0, max(0.0, _mix(getattr(x, k), getattr(y, k), wa, wb)))
                                for k in ("bass", "mid", "high", "overall")))
        t = dominant.energy.transient
        mixed_t = TransientEnergy(
            *(min(1.0, max(0.0, _mix(getattr(energy.transient, k), getattr(twin.transient, k), wa, wb)))
              for k in ("bass", "mid", "high", "overall")),
            onset_detected=t.onset_detected, onset_type=t.onset_type, onset_strength=t.onset_strength)
        lanes = EnergyLanes(continuous=band("continuous"), pre_agc=band("pre_agc"), bubble=band("bubble"),
                            transient=mixed_t)
        real, real_twin = frame.real, other.real
        spectrum = tuple(_mix(a, b, wa, wb) for a, b in zip(real.analysis_spectrum, real_twin.analysis_spectrum)) \
            if len(real.analysis_spectrum) == len(real_twin.analysis_spectrum) else real.analysis_spectrum
        mixed_real = RealScaleLanes(
            live=tuple(min(2.5, max(0.0, _mix(a, b, wa, wb))) for a, b in zip(real.live, real_twin.live)),
            musical_level=tuple(_mix(a, b, wa, wb) for a, b in zip(real.musical_level, real_twin.musical_level)),
            analysis_spectrum=spectrum, events=dominant.real.events, onsets=dominant.real.onsets)
        raw_bars = tuple(_mix(a, b, wa, wb) for a, b in zip(frame.raw_bars, other.raw_bars))
        history_bytes = history.astype("<f4").tobytes()
        out.append(replace(
            frame, energy=lanes, raw_bars=raw_bars, real=mixed_real,
            waveform=_preview(history.astype(np.float64)), control_event=dominant.control_event,
            capture_history=CaptureHistory(history_bytes, capture_serial=frame.capture_history.capture_serial,
                                           sample_rate=frame.capture_history.sample_rate)))
    period_us = int(source.frames[after].timestamp_us - base.timestamp_us
                    + round(choice.shift / SAMPLE_RATE * 1e6))
    info = {"frames": count, "period_samples": period, "period_s": period_us / 1e6,
            "crossfade_s": choice.fade_s, "first_source_s": float(source.seconds[first]),
            "after_source_s": float(source.seconds[after]), "shift_samples": int(choice.shift),
            "first_frame": int(first), "after_frame": int(after)}
    info["measured"] = _measure_bake(body, stream, r0, period, length, tail, lead, choice.detail)
    return out, period_us, info


def _measure_bake(body, stream, r0, period, length, tail, lead, detail) -> dict:
    """What the bake did, in numbers a rebuild must reproduce (and the tests hold it to):

    * ``join_error_db``: the last 5 ms of the loop against the 5 ms of source it has become by then (0 dB would be a
      different signal; the more negative, the closer the join is to the source's own continuation);
    * ``step_loop`` / ``step_source``: the sample step from the loop's last sample to its first against the
      source's own step from ``src[s - 1]`` to ``src[s]`` (equal when the join is the source's continuation);
    * ``level_deviation_db``: the crossfade's 50 ms-scale level against the equal-power target of its two sources,
      worst of eight stretches (after the level match);
    * ``blend``: how alike the two blended sources are (onset-envelope correlation, level difference in dB, mean
      log-spectrum difference, beat-grid offset in ms)."""
    edge = int(0.005 * SAMPLE_RATE)
    last = np.asarray(body[period - edge:period], dtype=np.float64)
    source_last = np.asarray(stream[r0 - edge:r0], dtype=np.float64)
    error = math.sqrt(float(np.mean((last - source_last) ** 2)) + 1e-30)
    scale = math.sqrt(float(np.mean(source_last ** 2)) + 1e-30)
    mixed = np.asarray(body[period - length:period], dtype=np.float64)
    deviations = []
    for k in range(8):
        piece = slice(k * length // 8, (k + 1) * length // 8)
        angle = (k + 0.5) / 8 * math.pi / 2
        target = math.sqrt(math.cos(angle) ** 2 * float(np.mean(tail[piece] ** 2))
                           + math.sin(angle) ** 2 * float(np.mean(lead[piece] ** 2)))
        deviations.append(20.0 * math.log10(math.sqrt(float(np.mean(mixed[piece] ** 2))) / max(target, 1e-12)))
    return {"join_error_db": round(20.0 * math.log10(error / scale), 2),
            "step_loop": round(float(abs(float(body[0]) - float(body[period - 1]))), 6),
            "step_source": round(float(abs(float(stream[r0]) - float(stream[r0 - 1]))), 6),
            "level_deviation_db": round(max(abs(v) for v in deviations), 2),
            "blend": ({"onset_correlation": round(float(detail[0]), 3), "level_db": round(float(detail[1]), 2),
                       "spectrum": round(float(detail[2]), 3), "beat_offset_ms": round(float(detail[3]), 1)}
                      if len(detail) >= 4 else {})}


# --------------------------------------------------------------------------------- the seam report
def tiled(stream: np.ndarray, period: int, passes: int = 4) -> np.ndarray:
    """``passes`` loop periods back to back (the stream's first ``period`` samples, after any lead)."""
    return np.tile(np.asarray(stream[:period], dtype=np.float64), passes)


def loop_stream(frames, period_samples: int) -> np.ndarray:
    """The loop's periodic capture stream (``period_samples`` samples, position 0 = the end of frame 0's history),
    read from the frames' histories.

    The stored stream holds the first frame's history (the loop's last samples, which precede position 0), then the
    samples up to the last frame's end; the few positions after that are the end of the first frame's history."""
    from widgets.spotify_visualizer.compact_clip import _history_stream
    stream, slices = _history_stream(frames)
    start = slices[0][1]
    block = np.asarray(stream[start:start + period_samples], dtype=np.float64)
    missing = period_samples - len(block)
    if missing > 0:
        head = np.asarray(stream[:start], dtype=np.float64)
        block = np.concatenate([block, head[len(head) - missing:]])
    return block


def histories_follow_the_loop(frames, period_samples: int) -> bool:
    """Whether every frame's capture history is the periodic loop stream read up to the frame's position (the
    first frame's included: its history is the loop's last samples). True for a baked loop, false for a clip cut
    short of its period."""
    from widgets.spotify_visualizer.compact_clip import _history_stream
    block = loop_stream(frames, period_samples)
    _stream, slices = _history_stream(frames)
    origin = slices[0][1]
    for frame, (start, end) in zip(frames, slices):
        history = np.frombuffer(frame.capture_history.pcm_f32le, dtype="<f4").astype(np.float64)
        where = (np.arange(end - start) + (end - origin) - (end - start)) % period_samples
        if not np.array_equal(block[where], history):
            return False
    return True


def _grid(flux: np.ndarray, start: int, stop: int, tempo: float) -> tuple[float, float]:
    """(phase in ms, coherence 0..1) of the beat grid of period ``tempo`` seconds in ``flux[start:stop]``: the
    flux-weighted mean direction of the beat phase (comb filter), so a steady groove has coherence near its
    strength and a grid that breaks inside the window lowers it."""
    segment = flux[start:stop]
    seconds = (np.arange(start, stop) * HOP + WINDOW / 2) / SAMPLE_RATE
    vector = (segment * np.exp(2j * math.pi * seconds / tempo)).sum() / max(float(segment.sum()), 1e-12)
    return float(np.angle(vector) / (2 * math.pi) * tempo * 1000.0), float(abs(vector))


def seam_report(stream: np.ndarray, period: int, *, beat: tuple[float, float] | None = None, passes: int = 4) -> dict:
    """The seam of a periodic stream measured four ways, on ``passes`` loop periods played back to back.

    * ``step``: the sample step across the seam against every sample step of the stream (``percentile`` of the
      seam's |step|; a click would sit at 100 and far above the 99.9th percentile).
    * ``rms``: the dB change of the 20 ms RMS across the seam against the same change at every other position
      (``within`` = no more than the 95th percentile).
    * ``flux``: the spectral flux in the 100 ms after the seam against the distribution elsewhere (percentile).
    * ``beat`` (given the groove ``(seconds, strength)``): the beat grid's phase over the 3 s before and the 3 s
      after the seam, the jump between them (ms, signed, within half a beat) against the same jump at every
      other position (``interior_p95_ms``), and the grid's coherence over the 6 s centred on the seam against the
      6 s windows elsewhere. A grid that continues has a jump as small as the music's own and a coherence as
      high as elsewhere.
    """
    x = tiled(stream, period, passes)
    seam = period * (passes // 2)
    delta = np.diff(x)
    steps = np.abs(delta)
    local = float(steps[seam - 1])
    report = {"step": {"seam": local, "percentile": float((steps < local).mean() * 100.0),
                       "p999": float(np.percentile(steps, 99.9)), "rms_step": float(np.sqrt(np.mean(delta ** 2)))}}
    window = 960                                          # 20 ms
    def rms_db(p):
        return 20.0 * math.log10(float(np.sqrt(np.mean(x[p:p + window] ** 2))) + 1e-9)
    positions = np.arange(window, len(x) - 2 * window, 240)
    deltas = np.array([abs(rms_db(int(p) + window) - rms_db(int(p))) for p in positions])
    here = abs(rms_db(seam) - rms_db(seam - window))
    report["rms"] = {"seam_db": float(here), "p95_db": float(np.percentile(deltas, 95)),
                     "median_db": float(np.median(deltas)), "within": bool(here <= np.percentile(deltas, 95))}
    flux, _rms, _bands = onset_envelope(x)
    h = seam // HOP
    after = float(flux[h:h + 10].mean())
    around = np.array([flux[i:i + 10].mean() for i in range(2, len(flux) - 12)])
    report["flux"] = {"after_seam": after, "median": float(np.median(around)), "p95": float(np.percentile(around, 95)),
                      "percentile": float((around < after).mean() * 100.0)}
    if beat is not None:
        tempo = float(beat[0])
        half = int(3.0 * SAMPLE_RATE / HOP)

        def jump(c):
            a, b = _grid(flux, c - half, c, tempo), _grid(flux, c, c + half, tempo)
            return ((b[0] - a[0] + tempo * 500.0) % (tempo * 1000.0)) - tempo * 500.0, a, b
        centres = [c for c in range(half, len(flux) - half, 25)]
        inside = [c for c in centres if all(abs(c - k * period / HOP) > half for k in range(1, passes))]
        interior = np.array([abs(jump(c)[0]) for c in inside])
        wide = lambda c: _grid(flux, c - half, c + half, tempo)[1]      # noqa: E731
        seam_jump, before_grid, after_grid = jump(h)
        report["beat"] = {
            "period_s": tempo, "strength": float(beat[1]), "phase_before_ms": before_grid[0],
            "phase_after_ms": after_grid[0], "jump_ms": float(seam_jump), "interior_median_ms": float(np.median(interior)),
            "interior_p95_ms": float(np.percentile(interior, 95)), "coherence_seam": float(wide(h)),
            "coherence_interior_median": float(np.median([wide(c) for c in inside])),
            "coherence_interior_p05": float(np.percentile([wide(c) for c in inside], 5))}
    return report


__all__ = ["LoopChoice", "Source", "bake_loop", "beat_period", "choose_loop", "histories_follow_the_loop",
           "loop_stream", "onset_envelope", "refine_beat", "running_grid", "seam_report", "tiled"]
