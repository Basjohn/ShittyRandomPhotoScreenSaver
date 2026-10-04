"""Immutable fixture input at the real BeatEngine post-DSP seam."""
from __future__ import annotations
from typing import Any
from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.feature_frame import FeatureFrame
from widgets.spotify_visualizer.transient_bus import (
    MusicalOnset, OnsetEvent, PassageIntensity, TransientEnergyBands, TransientEventScheduler,
)

def _bands(source: Any) -> EnergyBands:
    return EnergyBands(
        bass=float(source.bass),
        mid=float(source.mid),
        high=float(source.high),
        overall=float(source.overall),
    )

class ReplayBeatEngine(_SpotifyBeatEngine):
    """Real beat engine with immutable replay-only post-DSP lane getters."""

    def __init__(self, bar_count: int) -> None:
        super().__init__(bar_count)
        self._replay_pre_agc = EnergyBands()
        self._replay_bubble = EnergyBands()
        self._replay_transient = TransientEnergyBands()
        # Schema 2 real-scale lanes of the current frame, and the production event scheduler fed
        # with each frame's typed events at the replay clock (consumed once, aged as live).
        self._replay_real = None
        self._replay_scheduler = TransientEventScheduler()
        # Passage intensity is derived (not recorded): the production follower fed with each frame's
        # recorded loudness at the frame's own time step.
        self._replay_intensity = PassageIntensity()
        self._replay_last_us: int | None = None
        # Recorded MusicalOnsets, re-published with the replay's own serials (the last 16, as live).
        self._replay_onsets: tuple = ()
        self._replay_onset_serial = 0

    def ensure_started(self) -> None:
        """Keep the external audio producer inert during feature replay."""
        return None

    def accept_feature_frame(self, frame: FeatureFrame) -> bool:
        lanes = frame.energy
        self._replay_pre_agc = _bands(lanes.pre_agc)
        self._replay_bubble = _bands(lanes.bubble)
        transient = lanes.transient
        onset_map = {
            "bass": "kick",
            "mid": "snare",
            "high": "vocal_swell",
            "broadband": "snare",
        }
        self._replay_transient = TransientEnergyBands(
            bass_transient=float(transient.bass),
            mid_transient=float(transient.mid),
            high_transient=float(transient.high),
            onset_detected=bool(transient.onset_detected),
            onset_type=onset_map.get(str(transient.onset_type), "") if transient.onset_detected else "",
            onset_strength=float(transient.onset_strength),
        )
        self._replay_real = frame.real
        if frame.real is not None:
            step = 0.0 if self._replay_last_us is None else (frame.timestamp_us - self._replay_last_us) / 1e6
            self._replay_last_us = frame.timestamp_us
            self._replay_intensity.update(frame.real.musical_level[0], step)
            for onset in frame.real.onsets:
                self._replay_onset_serial += 1
                self._replay_onsets = self._replay_onsets[-15:] + (MusicalOnset(
                    serial=self._replay_onset_serial, timestamp=frame.timestamp_us / 1_000_000.0, kind=onset.kind,
                    strength=onset.strength, magnitude=onset.magnitude, loudness=onset.loudness,
                    presence=onset.presence),)
            for event in frame.real.events:
                self._replay_scheduler.feed(OnsetEvent(
                    timestamp=frame.timestamp_us / 1_000_000.0, event_type=event.kind, strength=event.strength))
        waveform = list(frame.waveform)
        raw_bars = list(frame.raw_bars)
        if len(raw_bars) != self._bar_count:
            source_last = len(raw_bars) - 1
            target_last = self._bar_count - 1
            if target_last <= 0:
                raw_bars = [raw_bars[0]]
            else:
                resampled = []
                for index in range(self._bar_count):
                    source_position = index * source_last / target_last
                    lower = int(source_position)
                    upper = min(source_last, lower + 1)
                    fraction = source_position - lower
                    resampled.append(
                        raw_bars[lower]
                        + (raw_bars[upper] - raw_bars[lower]) * fraction
                    )
                raw_bars = resampled
        # Real audio capture timestamps are wall-clock and therefore always > 0.
        # The fixture's first frame has timestamp_us == 0, which trips the
        # authoritative-live freshness gate (0abc479c) and spuriously suppresses
        # the cold-start oscilloscope/sine waveform. Model real capture by keeping
        # the committed authoritative timestamp strictly positive; frame deltas
        # (and every logical bar metric) are unchanged.
        timestamp_s = max(frame.timestamp_us / 1_000_000.0, 1e-3)
        return self.accept_analysis_frame(
            raw_bars,
            timestamp_s,
            activation_id=self.get_activation_id(),
            waveform=waveform,
            waveform_count=len(waveform),
            energy_override=_bands(lanes.continuous),
        )

    def get_pre_agc_energy_bands(self) -> EnergyBands:
        return self._replay_pre_agc

    def get_bubble_energy_bands(self) -> EnergyBands:
        return self._replay_bubble

    def get_transient_energy_bands(self) -> TransientEnergyBands:
        return self._replay_transient

    def get_live_pre_agc_energy_bands(self) -> EnergyBands:
        real = self._replay_real
        return super().get_live_pre_agc_energy_bands() if real is None else EnergyBands(*real.live)

    def get_musical_level(self) -> tuple[float, float]:
        real = self._replay_real
        return super().get_musical_level() if real is None else tuple(real.musical_level)

    def get_onset_events(self, after_serial: int = 0) -> tuple:
        if self._replay_real is None:
            return super().get_onset_events(after_serial)
        return tuple(onset for onset in self._replay_onsets if onset.serial > after_serial)

    def get_musical_intensity(self) -> float:
        return super().get_musical_intensity() if self._replay_real is None else self._replay_intensity.value

    def get_pre_agc_analysis_spectrum(self) -> tuple[float, ...]:
        real = self._replay_real
        return () if real is None else tuple(real.analysis_spectrum)

    def get_event_scheduler(self):
        # Schema 1: exact onset authority is carried by the immutable transient frame, and no
        # scheduler avoids replaying stale live-worker events. Schema 2 frames carry their typed
        # events, served through the production scheduler.
        return None if self._replay_real is None else self._replay_scheduler
