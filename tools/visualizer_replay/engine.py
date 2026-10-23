"""Immutable fixture input at the real BeatEngine post-DSP seam."""
from __future__ import annotations
from typing import Any
from core.logging.logger import get_logger
from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.feature_frame import FeatureFrame
from widgets.spotify_visualizer.transient_bus import (
    MusicalOnset, OnsetEvent, PassageIntensity, TransientEnergyBands, TransientEventScheduler,
)

# Production publishes the newest 256 capture samples (a loopback block is longer), so a
# waveform consumer sees a full block, never a short one padded with zeros.
PRODUCTION_WAVEFORM_BLOCK = 256


# Schema 1 fixtures are synthetic and predate the musical level: an audible frame is authored as
# ordinary music in a full passage (how every schema 1 floor was measured), silence as silence.
# Real-scale behaviour is judged on schema 2 recordings, which carry the measured level.
SCHEMA_1_MUSIC = (9.0, 1.2)
logger = get_logger(__name__)


def _waveform_block(samples) -> list[float]:
    """The recorded samples (decimated to 64 by the recorder) as a full production block:
    linear interpolation keeps the amplitude and shape; only detail above the recorded rate is lost."""
    values = [float(v) for v in samples] or [0.0]
    last = len(values) - 1
    out = []
    for index in range(PRODUCTION_WAVEFORM_BLOCK):
        position = index * last / (PRODUCTION_WAVEFORM_BLOCK - 1)
        lower = int(position)
        upper = min(last, lower + 1)
        out.append(values[lower] + (values[upper] - values[lower]) * (position - lower))
    return out


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
        self._replay_audible = False
        self._replay_capture_history = None
        self._replay_history_array = None
        self._replay_history_demanded = False
        self._replay_missing_history_warned = False
        # Spectrum-shaped bars computed from a recorded capture history (see _replay_shaped_bars).
        self._replay_compute_state = None
        self._replay_compute_epoch: int | None = None
        self._replay_shaped: list[float] | None = None

    def ensure_started(self) -> None:
        """Keep the external audio producer inert during feature replay."""
        return None

    def accept_feature_frame(self, frame: FeatureFrame) -> bool:
        history = frame.capture_history
        if history is not None:
            # The recording keeps the device's true rate and the Oscilloscope converts its time
            # spans at that rate (get_waveform_history_rate), so any rate replays faithfully.
            previous = self._replay_capture_history
            if previous is not None and history.capture_serial <= previous.capture_serial:
                if history.capture_serial < previous.capture_serial or history != previous:
                    raise ValueError("capture history serial must advance for each changed native source")
            new_audio = previous is None or history.capture_serial != previous.capture_serial
            if new_audio:
                import numpy as np

                # Bytes-backed array is immutable. Repeated source serials keep this exact
                # object, as production held logical ticks keep the native history array.
                self._replay_history_array = np.frombuffer(history.pcm_f32le, dtype="<f4")
            self._replay_capture_history = history
            if new_audio:
                self._replay_shaped = self._replay_shaped_bars(history.sample_rate)
        else:
            self._replay_capture_history = None
            self._replay_history_array = None
            self._replay_shaped = None
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
        self._replay_audible = any(value > 0.0 for value in frame.raw_bars)
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
        if history is not None:
            waveform = self._replay_history_array[-PRODUCTION_WAVEFORM_BLOCK:].tolist()
        else:
            waveform = _waveform_block(frame.waveform)
        raw_bars = list(frame.raw_bars) if self._replay_shaped is None else list(self._replay_shaped)
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
            # Production derives the continuous lane from the smoothed bars, so a real recording
            # replays it from its raw bars through the replayed mode's own smoothing (more faithful
            # than the recorder's Sphere-configured lane, and the only source for takes recorded
            # while the recorder's engine published raw bars alone). Synthetic schema 1 fixtures
            # author the lane directly.
            energy_override=None if frame.real is not None else _bands(lanes.continuous),
        )

    def _replay_shaped_bars(self, sample_rate: int) -> list[float] | None:
        """The replayed mode's own Spectrum-shaped bars from the recorded audio, or None.

        Shaped bars belong to the mode that draws them (R160: only the Spectrum family shapes;
        every other mode's analysis publishes zero bars), so a recording's bars are only the
        recorder's own. A clip that carries the capture history replays the real audio
        instead: the newest capture block, the input production analyzes on a tick, through
        this mode's configured DSP state (rebuilt at each configuration boundary, as the
        production analysis lane rebuilds it). The capture block is the mode's configured
        size; an unspecified size is the host's usual 10 ms period.
        """
        from widgets.spotify_visualizer.bar_computation import compute_bars_from_samples

        worker = self._audio_worker
        if not worker._spectrum_shaping_enabled:
            return None
        epoch = self._analysis_compute_state_epoch
        if self._replay_compute_state is None or self._replay_compute_epoch != epoch:
            import numpy as np

            self._replay_compute_state = worker.make_compute_snapshot()
            # Production imports NumPy into the worker when native capture starts; replay starts none.
            self._replay_compute_state._np = np
            self._replay_compute_epoch = epoch
        block = int(worker._preferred_block_size or 0) or max(1, int(sample_rate) // 100)
        bars = compute_bars_from_samples(self._replay_compute_state, self._replay_history_array[-block:])
        return list(bars) if isinstance(bars, list) else None

    def get_pre_agc_energy_bands(self) -> EnergyBands:
        return self._replay_pre_agc

    def set_waveform_history_demand(self, demanded: bool) -> None:
        """Replay reads only recorded history; its external capture worker stays dormant."""
        self._replay_history_demanded = bool(demanded)

    def get_waveform_history_rate(self) -> int:
        history = self._replay_capture_history
        return history.sample_rate if history is not None else 48000

    def get_waveform_history(self):
        if not self._replay_history_demanded:
            return None
        if self._replay_history_array is None and not self._replay_missing_history_warned:
            logger.warning("[VISUALIZER_REPLAY] Clip has no native capture history; waveform replay is limited to its recorded 64-point preview and cannot validate full Oscilloscope fidelity. Re-record the clip.")
            self._replay_missing_history_warned = True
        return self._replay_history_array

    def get_bubble_energy_bands(self) -> EnergyBands:
        return self._replay_bubble

    def get_extruded_bubble_body_bands(self) -> EnergyBands:
        # Recordings carry no raw lanes, so ordinary replay serves EB the recorded
        # shared feed it historically consumed. PCM reanalysis
        # (tools/visualizer_replay/pcm_reanalysis.py) exercises the production feed.
        return self._replay_bubble

    def get_transient_energy_bands(self) -> TransientEnergyBands:
        return self._replay_transient

    def get_live_pre_agc_energy_bands(self) -> EnergyBands:
        real = self._replay_real
        return super().get_live_pre_agc_energy_bands() if real is None else EnergyBands(*real.live)

    def get_musical_level(self) -> tuple[float, float]:
        real = self._replay_real
        if real is None:
            return SCHEMA_1_MUSIC if self._replay_audible else (0.0, 0.0)
        return tuple(real.musical_level)

    def get_onset_events(self, after_serial: int = 0) -> tuple:
        if self._replay_real is None:
            return super().get_onset_events(after_serial)
        return tuple(onset for onset in self._replay_onsets if onset.serial > after_serial)

    def get_musical_intensity(self) -> float:
        if self._replay_real is None:
            return 1.0 if self._replay_audible else 0.0
        return self._replay_intensity.value

    def get_pre_agc_analysis_spectrum(self) -> tuple[float, ...]:
        real = self._replay_real
        return () if real is None else tuple(real.analysis_spectrum)

    def get_event_scheduler(self):
        # Schema 1: exact onset authority is carried by the immutable transient frame, and no
        # scheduler avoids replaying stale live-worker events. Schema 2 frames carry their typed
        # events, served through the production scheduler.
        return None if self._replay_real is None else self._replay_scheduler
