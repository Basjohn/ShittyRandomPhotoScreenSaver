"""The lossless engine snapshot: P2a's live input (native core P2, work order 4).

In process, the logical tick steps the beat engine (``engine.tick()``: the newest audio frame into DSP) and then
reads its getters. With the tick in the engine worker, the main process keeps the beat engine and its DSP: at each
tick time it steps the engine and captures, unchanged and unresampled, every value the tick can read
(``tools/visualizer_replay/engine_read_audit.py`` measures that surface; ``tests/test_visualizer_engine_snapshot.py``
pins it), plus, in order, what was fed to the engine's event scheduler since the previous snapshot. The worker's
``SnapshotBeatEngine`` answers the tick's reads from the newest snapshot and replays those feeds into its own
scheduler (the scheduler's debounce depends only on what it was fed, so the worker's accepts the same events and the
tick consumes them from it, consume-once, as it would in process).

Reads are side-effect free at capture: the ramp latch is a pure read of the ramp's clock, and the analysis spectrum
is peeked. The tick's writes to the engine: the waveform history and idle waveform demands are a rule of the mode
(``mode_capabilities.consumes_waveform_samples``) the tick declares before stepping, so the main process declares
them itself before each step (the worker's declarations must agree, or the tick fails); the one write that depends
on the tick, a request for the next analysis spectrum, travels back as ``EngineDemands`` and is applied before the
next step.

``FeatureFrame`` stays the replay contract: it clamps and resamples, so it cannot carry a live tick losslessly.
"""
from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from typing import Any

#: The no-argument getters the tick reads, captured after every step (the audit's surface; a test pins it).
CAPTURED_GETTERS: tuple[str, ...] = (
    "get_generation_id", "get_activation_id", "get_energy_bands", "get_smoothed_bars",
    "get_transient_energy_bands", "get_floor_snapshot", "get_waveform_count", "get_latest_authoritative_frame",
    "get_latest_generation_with_frame", "get_latest_generation_with_waveform", "get_pre_agc_energy_bands",
    "get_bubble_energy_bands", "get_extruded_bubble_body_bands", "get_waveform_ribbon_body_bands",
    "get_live_pre_agc_energy_bands", "get_musical_level", "get_musical_intensity", "get_waveform",
    "is_reactivity_play_ramping", "get_waveform_history", "get_waveform_history_rate",
)

#: Reads answered by ``SnapshotBeatEngine``'s own methods (they take arguments or carry demand).
SPECIAL_READS: tuple[str, ...] = ("get_onset_events", "get_event_scheduler", "get_pre_agc_analysis_spectrum")

_FEED, _RESET = "feed", "reset"


@dataclass(frozen=True)
class EngineSnapshot:
    """What the tick reads from the beat engine at one tick, after the engine has stepped."""

    timestamp: float
    playing: bool
    draws_samples: bool              # the waveform demands the main process declared for the mode before stepping
    values: tuple[tuple[str, Any], ...]
    onsets: tuple                    # every published onset (``get_onset_events(0)``); the reader filters by serial
    analysis_spectrum: tuple         # the published spectrum, peeked (requesting it is the tick's demand)
    has_scheduler: bool
    scheduler_ops: tuple             # ((op, event), ...) fed to / reset on the engine's scheduler since the last one


@dataclass(frozen=True)
class EngineDemands:
    """The tick's writes to the engine during one tick that only the tick can know."""

    analysis_spectrum: bool = False


class EngineSnapshotSource:
    """Main side: steps the beat engine once per tick of ``mode`` and captures its snapshot."""

    def __init__(self, engine: Any, mode: str) -> None:
        from widgets.spotify_visualizer.mode_capabilities import consumes_waveform_samples

        self._engine = engine
        self._draws_samples = bool(consumes_waveform_samples(mode))
        self._lock = threading.Lock()
        self._ops: list = []
        self._tapped: Any = None

    def _tap_scheduler(self) -> Any:
        """Forward what the DSP feeds the scheduler (from the compute pool) and its resets, in order."""
        scheduler = self._engine.get_event_scheduler()
        if scheduler is None or scheduler is self._tapped:
            return scheduler
        feed, reset = scheduler.feed, scheduler.reset

        def tapped_feed(event: Any) -> bool:
            with self._lock:
                self._ops.append((_FEED, copy.copy(event)))
            return feed(event)

        def tapped_reset() -> None:
            with self._lock:
                self._ops.append((_RESET, None))
            reset()

        scheduler.feed, scheduler.reset = tapped_feed, tapped_reset
        if self._tapped is not None:
            with self._lock:                         # a new scheduler starts empty: the worker's starts over too
                self._ops.append((_RESET, None))
        self._tapped = scheduler
        return scheduler

    def apply_demands(self, demands: EngineDemands) -> None:
        """The tick's writes, applied before the next step (as they land between ticks in process)."""
        if demands.analysis_spectrum:
            request = getattr(self._engine, "request_pre_agc_analysis_spectrum", None)
            if request is not None:                  # a replay engine's spectrum needs no request
                request()

    def capture(self, timestamp: float, *, playing: bool, step: bool = True) -> EngineSnapshot:
        """Step the engine (``engine.tick()``, as the tick does first) and capture what the tick reads."""
        engine = self._engine
        scheduler = self._tap_scheduler()
        if step:
            # What the tick declares before stepping (tick_pipeline), from the same mode rule.
            engine.set_idle_waveform_demand(self._draws_samples)
            engine.set_waveform_history_demand(self._draws_samples)
            engine.tick()
        values = tuple((name, copy.deepcopy(getattr(engine, name)())) for name in CAPTURED_GETTERS)
        with self._lock:
            ops, self._ops = tuple(self._ops), []
        return EngineSnapshot(
            timestamp=float(timestamp), playing=bool(playing), draws_samples=self._draws_samples, values=values,
            onsets=tuple(engine.get_onset_events(0)), analysis_spectrum=tuple(engine.peek_pre_agc_analysis_spectrum()),
            has_scheduler=scheduler is not None, scheduler_ops=ops,
        )


class _DspConfigSink:
    """The audio worker's DSP configuration setters (``quick_technical_config`` applies some through it): the main
    process's engine is configured; the worker's has no DSP to configure."""

    def __getattr__(self, name: str) -> Any:
        if name.startswith("set_"):
            return lambda *_args, **_kwargs: None
        raise AttributeError(name)


class SnapshotBeatEngine:
    """Worker side: the beat engine the tick reads, answering from the newest snapshot.

    ``tick()`` is a no-op (the main process stepped the real engine). DSP configuration setters are accepted and
    ignored (DSP is configured in the main process); the tick's spectrum request is collected as ``EngineDemands``,
    and its waveform declarations must equal the main process's. A read no snapshot carries fails loudly rather than
    reading as an absent capability.
    """

    def __init__(self, initial: EngineSnapshot) -> None:
        from widgets.spotify_visualizer.transient_bus import TransientEventScheduler

        self._scheduler = TransientEventScheduler()
        self._audio_worker = _DspConfigSink()
        self._snapshot = initial
        self._values: dict[str, Any] = {}
        self._spectrum_requested = False
        self.accept_snapshot(initial)

    def accept_snapshot(self, snapshot: EngineSnapshot) -> None:
        self._snapshot = snapshot
        self._values = dict(snapshot.values)
        scheduler = self._scheduler
        for op, event in snapshot.scheduler_ops:
            if op == _FEED:
                scheduler.feed(event)
            else:
                scheduler.reset()

    def take_demands(self) -> EngineDemands:
        demands = EngineDemands(analysis_spectrum=self._spectrum_requested)
        self._spectrum_requested = False
        return demands

    def _declared(self, demand: str, demanded: bool) -> None:
        if bool(demanded) != self._snapshot.draws_samples:
            raise RuntimeError(f"the tick declared {demand}={bool(demanded)} but the main process stepped the "
                               f"engine with {self._snapshot.draws_samples} (another mode's rule)")

    def tick(self) -> None:
        return None

    def get_onset_events(self, after_serial: int = 0) -> tuple:
        return tuple(event for event in self._snapshot.onsets if event.serial > after_serial)

    def get_event_scheduler(self) -> Any:
        return self._scheduler if self._snapshot.has_scheduler else None

    def get_pre_agc_analysis_spectrum(self) -> tuple:
        self._spectrum_requested = True
        return self._snapshot.analysis_spectrum

    def set_waveform_history_demand(self, demanded: bool) -> None:
        self._declared("waveform history", demanded)

    def set_idle_waveform_demand(self, demanded: bool) -> None:
        self._declared("idle waveform", demanded)

    def __getattr__(self, name: str) -> Any:
        values = self.__dict__.get("_values")
        if values is not None and name in values:
            value = values[name]
            return lambda: copy.deepcopy(value)
        # DSP configuration and lifecycle: the main process's engine already did it (the snapshot carries the result,
        # e.g. the generation a bar-count change advanced).
        if name.startswith(("set_", "reconfigure_")) or name in ("ensure_started", "wake", "reset_smoothing_state"):
            return lambda *_args, **_kwargs: None
        if name.startswith(("get_", "is_", "peek_")):
            raise RuntimeError(f"no engine snapshot carries {name}: add it to CAPTURED_GETTERS")
        raise AttributeError(name)
