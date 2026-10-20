"""Activation-fenced authored state for Extruded Bubble: its own simulation, advanced in the mode's logical capture.

Each capture passes the logical time, the activation and source identities, the passage intensity and the onsets the engine published since ``onset_serial`` (each ``MusicalOnset`` is taken exactly once, by
serial, however the analysis and logical cadences relate). dt is the logical time since the previous capture; a new
activation, a source that is not ready, or a clock that goes back starts the simulation over or holds it silent.
Nothing here touches Qt or GL.
"""
from __future__ import annotations

import math

from core.settings.visualizer_paths import admit_path, direction_of
from widgets.spotify_visualizer.extruded_bubble_simulation import (
    ExtrudedBubbleControls,
    ExtrudedBubbleSimulation,
    ExtrudedBubbleSnapshot,
    MusicInput,
)
from widgets.spotify_visualizer.frame_runtime_lifecycle import RetirableFrameRuntime, retirement_fenced
from widgets.spotify_visualizer.transient_bus import musical_weight

# The largest step one capture may take (a stalled clock never leaps the population).
MAX_STEP_SECONDS = 0.1
# Settings units -> simulation units: speed (authored normalized length/s; simulation converts once to physical world units); breathing/pulse are authored reaction strengths.
# Full-dynamic musical body bands are read from the existing 2D Bubble engine, not a new floor/DSP.
STREAM_SPEED_FULL = 0.25
_SCOPES = {"All": "all", "Big": "big", "Small": "small", "Off": "off"}


def controls_from_parameters(parameters) -> ExtrudedBubbleControls:
    """The simulation's controls from the mode's Settings values (``extruded_bubble_*``, as the spec admits them)."""
    def pair(key, scale=1.0):
        low, high = parameters[key]
        return float(low) * scale, float(high) * scale

    stream_path = admit_path(parameters["extruded_bubble_stream_direction"], [0., 0.], "stream")
    vector = direction_of(stream_path)
    stream_angles = (math.degrees(math.atan2(vector[0], vector[1])),
                     math.degrees(math.atan2(-vector[2], math.hypot(vector[0], vector[1]))))
    return ExtrudedBubbleControls(
        large_count=pair("extruded_bubble_large_bubbles"),
        mid_count=pair("extruded_bubble_mid_bubbles"),
        large_size=float(parameters.get("extruded_bubble_large_size", 1.0)),
        small_size=float(parameters.get("extruded_bubble_small_size", 1.0)),
        size_variety=float(parameters["extruded_bubble_size_variety"]),
        columns=float(parameters["extruded_bubble_columns"]),
        stream_direction=stream_angles,
        stream_path=stream_path,
        stream_speed=pair("extruded_bubble_stream_speed", STREAM_SPEED_FULL),
        drift=pair("extruded_bubble_drift"),
        sway=float(parameters["extruded_bubble_sway"]),
        emission=pair("extruded_bubble_particles"),
        idle=float(parameters["extruded_bubble_idle"]),
        breathing=pair("extruded_bubble_breathing"),
        small_pulse=pair("extruded_bubble_small_pulse"),
        sustained=float(parameters["extruded_bubble_sustained"]),
        smoothing=float(parameters["extruded_bubble_smoothing"]),
        collision=tuple(float(v) for v in parameters["extruded_bubble_collision"]),
        collision_scope=_SCOPES[str(parameters["extruded_bubble_collision_scope"])],
    )


def onset_weight(onset) -> float:
    """How much an onset moves the bubbles, 0..1: its musical weight (near-silent passages barely count) times how far
    it stood above threshold (``magnitude`` 0..3: a big hit from a medium one)."""
    return musical_weight(float(onset.loudness), float(onset.presence)) * min(1.0, float(onset.magnitude) / 1.5)


class ExtrudedBubbleFrameRuntime(RetirableFrameRuntime):
    def __init__(self, seed: int = 0x5EB0) -> None:
        super().__init__()
        self._simulation = ExtrudedBubbleSimulation(seed)
        self._onset_serial = 0
        self._identity: tuple | None = None
        self._last_ts: float | None = None
        self._latest = ExtrudedBubbleSnapshot()

    def reset(self) -> None:
        self._simulation.reset()
        self._identity = None
        self._last_ts = None
        self._latest = ExtrudedBubbleSnapshot()

    @property
    def onset_serial(self) -> int:
        """The last onset serial taken: ask the engine only for the onsets after it."""
        return self._onset_serial

    @property
    def latest(self) -> ExtrudedBubbleSnapshot:
        return self._latest

    @retirement_fenced
    def advance(self, *, onsets, now_ts: float, playing: bool, intensity: float,
                identity: tuple[int, int, int], source_identity: tuple[int, int],
                controls: ExtrudedBubbleControls,
                body_bands: tuple[float, float, float],
                play_ramping: bool = False) -> ExtrudedBubbleSnapshot | None:
        now = float(now_ts)
        if not math.isfinite(now):
            raise ValueError("Extruded Bubble capture time must be finite")
        token = (tuple(identity), tuple(source_identity))
        if token != self._identity or (self._last_ts is not None and now < self._last_ts):
            self._simulation.reset()
            self._identity = token
            self._last_ts = None
        source_ready = tuple(source_identity) == tuple(identity)[1:] and all(v >= 0 for v in identity)
        taken = []
        for onset in onsets:
            if onset.serial <= self._onset_serial:
                continue
            self._onset_serial = onset.serial
            weight = onset_weight(onset)
            if weight > 0.0:
                taken.append((str(onset.kind), weight))
        live = bool(playing) and source_ready
        dt = 0.0 if self._last_ts is None else min(MAX_STEP_SECONDS, max(0.0, now - self._last_ts))
        self._last_ts = now
        music = MusicInput(dt, live, float(intensity) if live else 0.0, tuple(taken) if live else (),
                           tuple(body_bands) if live else (0.0, 0.0, 0.0),
                           bool(play_ramping) if live else False)
        self._latest = self._simulation.advance(music, controls)
        return self._latest


__all__ = ["ExtrudedBubbleFrameRuntime", "MAX_STEP_SECONDS", "controls_from_parameters", "onset_weight"]
