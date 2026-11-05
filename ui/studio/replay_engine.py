"""The engine side of a Studio evaluator that drives a mode's unchanged production logical path (mode-neutral).

A Studio never re-implements a mode's simulation, timing or capture. It configures a production
``VisualizerRuntimeController`` the way the production offline replay does and serves the production step one
*engine tick* at a time: what the beat engine would answer the mode's step at that instant (post-DSP lanes, typed
events, the authoritative source frame). ``FixtureBeatEngine`` is the production replay engine (no capture, no
worker thread) with those getters answered from the tick; its event scheduler is the production scheduler with the
fixture's clock in place of the process clock (the offline replay pins the process clock instead; a Studio runs
inside the app and must not).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EngineTick:
    """One authored tick's engine answers. ``None`` fields fall through to the production replay engine."""

    now: float
    playing: bool
    bubble: tuple | None = None                          # get_bubble_energy_bands: bass, mid, high, overall
    transient: tuple = (0.0, 0.0, 0.0, False, "", 0.0)   # get_transient_energy_bands fields, in order
    events: tuple = ()                                   # typed events fed this tick: (timestamp, kind, strength)
    authoritative: float = 0.0                           # latest authoritative source frame time (0: none)
    fresh: bool = True                                   # that frame belongs to the engine's current activation
    scheduler: bool = True                               # the engine serves its event scheduler (schema 2)
    energy: tuple | None = None                          # get_energy_bands
    live: tuple | None = None                            # get_live_pre_agc_energy_bands
    musical_level: tuple | None = None                   # get_musical_level: (loudness, presence)
    musical_intensity: float | None = None               # get_musical_intensity
    spectrum: tuple | None = None                        # get_pre_agc_analysis_spectrum


def clocked_scheduler():
    """The production event scheduler with its clock set to fixture time (consume-once, ages as live)."""
    from widgets.spotify_visualizer.transient_bus import OnsetEvent, TransientEventScheduler

    class ClockedEventScheduler(TransientEventScheduler):
        now = 0.0

        def consume_next(self, event_type: str, max_age_s: float = 0.5):
            # TransientEventScheduler.consume_next with ``time.time()`` replaced by the fixture clock.
            cutoff = self.now - max_age_s
            best = None
            for entry in self._ring:
                if (not entry.consumed and entry.event.event_type == event_type
                        and entry.event.timestamp > cutoff):
                    if best is None or entry.event.timestamp < best.event.timestamp:
                        best = entry
            if best is not None:
                best.consumed = True
                return OnsetEvent(timestamp=best.event.timestamp, event_type=best.event.event_type,
                                  strength=best.event.strength)
            return None
    return ClockedEventScheduler()


def fixture_engine_type():
    from widgets.spotify_visualizer.energy_bands import EnergyBands
    from widgets.spotify_visualizer.feature_replay import ReplayBeatEngine
    from widgets.spotify_visualizer.transient_bus import OnsetEvent, TransientEnergyBands

    def bands(values):
        return EnergyBands(*(float(v) for v in values))

    class FixtureBeatEngine(ReplayBeatEngine):
        """The production replay engine (no capture, no worker thread) serving one fixture tick."""

        def __init__(self, bar_count: int) -> None:
            super().__init__(bar_count)
            self.reset_ticks()

        def reset_ticks(self) -> None:
            self._tick: Any = None
            self._fixture_scheduler = clocked_scheduler()

        def serve(self, tick) -> None:
            self._tick = tick
            self._fixture_scheduler.now = float(tick.now)
            for timestamp, kind, strength in tick.events:
                self._fixture_scheduler.feed(OnsetEvent(timestamp=float(timestamp), event_type=str(kind),
                                                        strength=float(strength)))

        def _field(self, name):
            return None if self._tick is None else getattr(self._tick, name, None)

        def get_bubble_energy_bands(self):
            value = self._field("bubble")
            return bands(value) if value is not None else EnergyBands()

        def get_energy_bands(self):
            value = self._field("energy")
            return bands(value) if value is not None else super().get_energy_bands()

        def get_live_pre_agc_energy_bands(self):
            value = self._field("live")
            return bands(value) if value is not None else EnergyBands()

        def get_musical_level(self):
            value = self._field("musical_level")
            return tuple(float(v) for v in value) if value is not None else (0.0, 0.0)

        def get_musical_intensity(self):
            value = self._field("musical_intensity")
            return float(value) if value is not None else 0.0

        def get_pre_agc_analysis_spectrum(self):
            value = self._field("spectrum")
            return tuple(float(v) for v in value) if value is not None else ()

        def get_transient_energy_bands(self):
            if self._tick is None:
                return TransientEnergyBands()
            bass, mid, high, detected, kind, strength = self._tick.transient
            return TransientEnergyBands(bass_transient=float(bass), mid_transient=float(mid),
                                        high_transient=float(high), onset_detected=bool(detected),
                                        onset_type=str(kind), onset_strength=float(strength))

        def get_event_scheduler(self):
            return self._fixture_scheduler if self._tick is not None and self._tick.scheduler else None

        def get_latest_authoritative_frame(self):
            tick = self._tick
            if tick is None or tick.authoritative <= 0.0:
                return 0.0, -1, -1
            if not tick.fresh:
                return float(tick.authoritative), -1, -1
            return float(tick.authoritative), self.get_generation_id(), self.get_activation_id()
    return FixtureBeatEngine


def offline_controller(engine, mode_id: str, settings):
    """A production runtime controller for ``mode_id`` configured exactly as the production offline replay
    configures one (``feature_replay.configure_offline_controller``), on ``engine``."""
    from widgets.spotify_visualizer.feature_replay import configure_offline_controller
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    controller = VisualizerRuntimeController(runtime_generation=0, initial_mode=mode_id,
                                             engine_factory=lambda _bars: engine)
    controller.engine = engine
    configure_offline_controller(controller, mode_id, settings=settings)
    return controller


def recorded_answers(engine, feature) -> dict:
    """What the production replay engine answers after accepting ``feature`` (for the recorded-clip workers)."""
    def four(value):
        return [float(value.bass), float(value.mid), float(value.high), float(value.overall)]
    transient = engine.get_transient_energy_bands()
    ts, generation, activation = engine.get_latest_authoritative_frame()
    real = feature.real
    return {
        "playing": bool(feature.playing),
        "bubble": four(engine.get_bubble_energy_bands()),
        "energy": four(engine.get_energy_bands()),
        "live": four(engine.get_live_pre_agc_energy_bands()),
        "musical_level": [float(v) for v in engine.get_musical_level()],
        "musical_intensity": float(engine.get_musical_intensity()),
        "spectrum": [float(v) for v in engine.get_pre_agc_analysis_spectrum()],
        "transient": [float(transient.bass_transient), float(transient.mid_transient),
                      float(transient.high_transient), bool(transient.onset_detected),
                      str(transient.onset_type), float(transient.onset_strength)],
        "events": ([[feature.timestamp_us / 1e6, e.kind, float(e.strength)] for e in real.events]
                   if real is not None else []),
        "authoritative": float(ts),
        "fresh": bool(generation == engine.get_generation_id() and activation == engine.get_activation_id()),
        "scheduler": engine.get_event_scheduler() is not None,
    }


__all__ = ["EngineTick", "clocked_scheduler", "fixture_engine_type", "offline_controller", "recorded_answers"]
