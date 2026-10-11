"""Authored Oscilloscope state advanced by the sole logical clock.

Each capture turns the newest audio into the live trace (``rendering/gl_programs/oscilloscope_program.py``:
trigger, envelope, display), keeps the afterglow traces that fade on the logical clock, takes the new
musical onsets once each into the beam's flare, and eases the beam's drive and the music's tone. The
frame carries everything the renderer needs as plain data (the traces' points as packed float32
bytes), so the renderer keeps no history and no clock. Nothing here touches Qt or GL.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np

from rendering.gl_programs.oscilloscope_program import (
    DRIVE_FALL,
    DRIVE_RISE,
    FLARE_DECAY,
    FLARE_MAX_AGE,
    FLARE_RISE,
    GHOST_CAPACITY,
    GHOST_INTERVAL,
    SAMPLE_RATE,
    TONE_EASE,
    beam_drive_target,
    condition,
    flare_strength,
    flat_points,
    ghost_alpha,
    ghost_lifetime,
    phase_points,
    smoothing_samples,
    spectral_tone,
    trace_points,
    trace_template,
    trigger_start,
)
from widgets.spotify_visualizer.frame_runtime_lifecycle import (
    RetirableFrameRuntime,
    retirement_fenced,
)

_SETTLED = 1.0e-4
_MIN_HISTORY = 256       # fewer captured samples than this: draw the engine's waveform instead


@dataclass(frozen=True, slots=True)
class OscilloscopeResolvedFrame:
    points: bytes                        # float32 x, y: every trace back to back, oldest first
    trace_alphas: tuple[float, ...]      # one per trace; the last is the live trace
    flare: float
    drive: float
    tone: float
    animation_time: float
    changed: bool
    reactive_source_ready: bool


def _ease(current: float, target: float, dt: float, rise: float, fall: float) -> float:
    if dt <= 0.0:
        return current
    tau = rise if target > current else fall
    return current + (target - current) * (1.0 - math.exp(-dt / tau))


class OscilloscopeFrameRuntime(RetirableFrameRuntime):
    """Oscilloscope-only state owner with no Qt/render authority."""

    def __init__(self) -> None:
        super().__init__()
        self.reset()

    def reset(self) -> None:
        self._live: bytes = b""
        self._live_display = ""
        self._live_ts = 0.0
        self._template: np.ndarray | None = None
        self._source_key: object = None
        self._trace_inputs: tuple | None = None
        self._live_ready = False
        self._ghosts: list[tuple[float, bytes]] = []     # (birth, points), oldest first
        self._last_ghost_ts = float("-inf")
        self._flare = 0.0
        self._flare_target = 0.0
        self._drive = 0.0
        self._tone = 0.5
        self._onset_serial = 0
        self._animation_time = 0.0
        self._last_timestamp = 0.0
        self._activation_identity: tuple[int, int, int] | None = None

    @property
    def onset_serial(self) -> int:
        """The last onset serial taken: ask the engine only for the onsets after it."""
        return self._onset_serial

    def _signal(self, history, waveform: Sequence[float], count: int, use_history: bool) -> tuple[object, np.ndarray]:
        if use_history and history is not None and len(history) >= _MIN_HISTORY:
            return history, np.asarray(history)
        samples = tuple(float(v) for v in waveform[:max(0, int(count))])
        return samples, np.asarray(samples, dtype=np.float32)

    def _trace(self, display: str, signal: np.ndarray, span_ms: float, delay_ms: float, rate: int) -> bytes:
        if signal.size < 4 or not np.any(signal):
            self._template = None
            return flat_points(display).tobytes()
        window = min(signal.size, max(16, int(round(span_ms * rate / 1000.0))))
        if display == "Phase":
            self._template = None
            return phase_points(signal, window, int(round(delay_ms * rate / 1000.0))).tobytes()
        start = trigger_start(signal, window, self._template)
        self._template = trace_template(signal, start, window)
        return trace_points(display, signal, start, window).tobytes()

    @retirement_fenced
    def resolve(
        self,
        *,
        history,
        waveform: Sequence[float],
        waveform_count: int,
        now_ts: float,
        runtime_generation: int,
        engine_generation: int,
        activation_id: int,
        source_generation: int,
        source_activation_id: int,
        source_timestamp: float | None,
        playing: bool,
        display: str,
        span_ms: float,
        gain: float,
        delay_ms: float,
        afterglow: float,
        detail: float = 1.0,
        onsets: Sequence[object] = (),
        loudness: float = 0.0,
        presence: float = 0.0,
        intensity: float = 0.0,
        spectrum: Sequence[float] = (),
        sample_rate: int = SAMPLE_RATE,
    ) -> OscilloscopeResolvedFrame | None:
        timestamp = float(now_ts)
        identity = (int(runtime_generation), int(engine_generation), int(activation_id))
        if identity != self._activation_identity:
            self.reset()
            self._activation_identity = identity
        # While playing, a raw capture packet may run ahead of the authoritative analysis frame:
        # it is live source only once the matching authoritative timestamp exists. Paused idle
        # presentation needs no live audio.
        authoritative = not playing or (source_timestamp is not None and float(source_timestamp) > 0.0)
        source_ready = bool(
            0 <= int(source_generation) == int(engine_generation)
            and 0 <= int(source_activation_id) == int(activation_id)
            and authoritative
        )
        dt = 0.0
        if self._last_timestamp > 0.0 and 0.0 < timestamp - self._last_timestamp < 1.0:
            dt = timestamp - self._last_timestamp
        self._last_timestamp = timestamp
        self._animation_time += dt

        previous = (self._live, self._flare, self._drive, self._tone, len(self._ghosts))
        changed = False
        rate = max(8000, int(sample_rate))
        inputs = (display, float(span_ms), float(gain), float(delay_ms), float(detail), rate)
        # A ready source rebuilds the trace when the source, the inputs, or the readiness it was
        # built under change; a stale one keeps the last good trace (only a changed shape, or no
        # trace yet, rebuilds it, flat).
        if source_ready or not self._live or inputs != self._trace_inputs:
            key, signal = self._signal(history, waveform, waveform_count, bool(playing))
            # A new capture history is a new array; the engine's waveform is compared by value.
            same_source = key is self._source_key or (
                isinstance(key, tuple) and isinstance(self._source_key, tuple) and key == self._source_key)
            if (not same_source or inputs != self._trace_inputs or not self._live
                    or source_ready != self._live_ready):
                gained = (condition(signal, gain, smoothing_samples(detail, rate)) if source_ready
                          else np.zeros(0, dtype=np.float32))
                live = self._trace(display, gained, span_ms, delay_ms, rate)
                if live != self._live:
                    if self._live and display == self._live_display and afterglow > 0.0 \
                            and timestamp - self._last_ghost_ts >= GHOST_INTERVAL:
                        self._ghosts.append((self._live_ts, self._live))
                        self._last_ghost_ts = timestamp
                    if display != self._live_display:
                        self._ghosts = []
                    self._live, self._live_display, self._live_ts = live, display, timestamp
                    changed = True
                self._source_key, self._trace_inputs, self._live_ready = key, inputs, source_ready
        lifetime = ghost_lifetime(afterglow)
        self._ghosts = [ghost for ghost in self._ghosts if timestamp - ghost[0] < lifetime] if afterglow > 0.0 else []
        del self._ghosts[:-GHOST_CAPACITY]

        # Reactions: only while playing; silence and pause relax them.
        live_music = bool(playing) and source_ready
        drive_target = beam_drive_target(loudness, presence, intensity) if live_music else 0.0
        self._drive = _ease(self._drive, drive_target, dt, DRIVE_RISE, DRIVE_FALL) if dt > 0.0 else self._drive
        if dt > 0.0:
            self._flare_target *= math.exp(-dt / FLARE_DECAY)
        for onset in onsets:
            serial = int(getattr(onset, "serial", 0))
            if serial <= self._onset_serial:
                continue
            self._onset_serial = serial
            age = max(0.0, timestamp - float(getattr(onset, "timestamp", timestamp)))
            if live_music and age < FLARE_MAX_AGE:
                strength = flare_strength(onset.magnitude, onset.loudness, onset.presence, intensity)
                self._flare_target = max(self._flare_target, strength * math.exp(-age / FLARE_DECAY))
        # Rise quickly toward the hit, then follow its decay.
        if self._flare_target > self._flare:
            if dt > 0.0:          # no time passed (a first frame): no rise yet
                self._flare += (self._flare_target - self._flare) * (1.0 - math.exp(-dt / FLARE_RISE))
        else:
            self._flare = self._flare_target
        if self._flare < 1e-3 and self._flare_target < 1e-3:
            self._flare = self._flare_target = 0.0
        tone = spectral_tone(spectrum) if live_music else None
        if tone is not None and dt > 0.0:
            self._tone = _ease(self._tone, tone, dt, TONE_EASE, TONE_EASE)

        alphas = tuple(ghost_alpha(timestamp - birth, afterglow) for birth, _points in self._ghosts) + (1.0,)
        points = b"".join(points for _birth, points in self._ghosts) + self._live
        changed = changed or bool(self._ghosts) or (
            abs(previous[1] - self._flare) > _SETTLED or abs(previous[2] - self._drive) > _SETTLED
            or abs(previous[3] - self._tone) > _SETTLED or previous[4] != len(self._ghosts))
        return OscilloscopeResolvedFrame(
            points=points,
            trace_alphas=alphas,
            flare=float(self._flare),
            drive=float(self._drive),
            tone=float(self._tone),
            animation_time=float(self._animation_time),
            changed=changed,
            reactive_source_ready=source_ready,
        )


__all__ = ["OscilloscopeFrameRuntime", "OscilloscopeResolvedFrame"]
