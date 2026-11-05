"""Offline feature replay at the real BeatEngine post-DSP seam (production-owned).

Recorded feature clips (``widgets.spotify_visualizer.feature_frame``) replay through the real
beat engine, logical tick and mode runtimes with no audio capture, window or worker thread:

* ``ReplayBeatEngine``: the production engine with immutable replay-only post-DSP lane getters.
* ``PcmReanalysis``: recompute production body-band DSP from each frame's recorded native PCM.
* ``deterministic_clock``: process clocks and RNG pinned for byte-reproducible replay.
* ``configure_offline_controller``: configure a ``VisualizerRuntimeController`` for a mode exactly as
  the runtime does, from a curated preset or a complete resolved settings mapping.

The Waveform Studio's recorded fixtures (``ui.studio.waveform_recorded_inputs``) and the operator
analysis tools (``tools/visualizer_replay``) both use this module; production code never imports
``tools``.

PCM reanalysis:
    Explicit hybrid replay: recompute production body-band DSP from recorded PCM tails.

    Ordinary replay serves each frame's recorded post-DSP bands, so a mode's technical
    settings (Dynamic Floor, manual floor, Sensitivity) cannot change them. Inside
    ``reanalyzed_bubble_bands()`` every accepted frame instead feeds its native PCM
    tail through ``compute_bars_from_samples`` with the replay worker's *configured*
    compute state, and Bubble/EB read bands through the production getter. For Bubble/EB recorded
    onsets, loudness and sampled cadence remain unchanged: a controlled hybrid, not a
    live run. EB derives its passage inside its runtime from that recomputed body tuple;
    its passage never reads the retained historical loudness scalar. Other modes keep
    their existing recorded lane ownership. Waveform also reads musical level, passage and typed
    onsets from the same reanalysed production bus, with current-source/config fencing. Auto's negotiated block and skipped native
    callbacks are not recoverable.
"""
from __future__ import annotations

import random
import time
from contextlib import contextmanager
from dataclasses import asdict, replace
from typing import Any

import numpy as np

from core.logging.logger import get_logger
from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_presets import resolve_visualizer_activation_payload
from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
from widgets.spotify_visualizer.config_applier import (
    apply_logical_vis_mode_kwargs, apply_presentation_vis_mode_kwargs,
)
from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.feature_frame import FeatureFrame
from widgets.spotify_visualizer.logical_tick_state import install_default_logical_tick_state
from widgets.spotify_visualizer.presentation_state import install_default_presentation_state
from widgets.spotify_visualizer.quick_technical_config import apply_controller_technical_config
from widgets.spotify_visualizer.source_config_applier import apply_engine_vis_mode_kwargs, resolve_mode_source_config
from widgets.spotify_visualizer.technical_config import build_technical_cache, resolve_technical_config
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
        self._pcm_reanalysis_ready = False
        self._pcm_reanalysis_epoch = None
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
        self._pcm_reanalysis_ready = False
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
        # the cold-start oscilloscope waveform. Model real capture by keeping
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
        # shared feed it historically consumed. PCM reanalysis (``PcmReanalysis`` below,
        # ``reanalyzed_bubble_bands`` in tools/visualizer_replay) exercises the production feed.
        return self._replay_bubble

    def get_transient_energy_bands(self) -> TransientEnergyBands:
        return self._replay_transient

    def _has_current_pcm(self) -> bool:
        return self._pcm_reanalysis_ready and self._pcm_reanalysis_epoch == self._analysis_compute_state_epoch

    def get_waveform_ribbon_body_bands(self) -> EnergyBands:
        if not self._has_current_pcm():
            raise RuntimeError('Waveform replay requires native PCM reanalysis; recorded clipped lanes are insufficient')
        return super().get_waveform_ribbon_body_bands()

    def get_live_pre_agc_energy_bands(self) -> EnergyBands:
        real = self._replay_real
        return super().get_live_pre_agc_energy_bands() if real is None else EnergyBands(*real.live)

    def get_musical_level(self) -> tuple[float, float]:
        if self._audio_worker._raw_musical_signals:
            if not self._has_current_pcm():raise RuntimeError('Raw musical replay requires current PCM reanalysis')
            return super().get_musical_level()
        real = self._replay_real
        if real is None:
            return SCHEMA_1_MUSIC if self._replay_audible else (0.0, 0.0)
        return tuple(real.musical_level)

    def get_onset_events(self, after_serial: int = 0) -> tuple:
        if self._audio_worker._raw_musical_signals:
            if not self._has_current_pcm():raise RuntimeError('Raw musical replay requires current PCM reanalysis')
            return super().get_onset_events(after_serial)
        if self._replay_real is None:
            return super().get_onset_events(after_serial)
        return tuple(onset for onset in self._replay_onsets if onset.serial > after_serial)

    def get_musical_intensity(self) -> float:
        if self._audio_worker._raw_musical_signals:
            if not self._has_current_pcm():raise RuntimeError('Raw musical replay requires current PCM reanalysis')
            return super().get_musical_intensity()
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


class PcmReanalysis:
    """One replay's DSP state; feed every accepted frame once per capture serial."""

    def __init__(self) -> None:
        self.state = None
        self.identity = None
        self.serial = None
        self.frames = 0

    def accept(self, engine, feature) -> None:
        from widgets.spotify_visualizer.bar_computation import compute_bars_from_samples

        history = feature.capture_history
        if history is None:
            raise ValueError("PCM reanalysis requires native capture history on every frame")
        if engine._replay_capture_history is not history:
            raise ValueError("PCM reanalysis must follow acceptance of this exact source frame")
        identity = (engine, engine._analysis_compute_state_epoch)
        if self.identity != identity:
            self.state = None
            self.serial = None
            self.identity = identity
        if self.serial == history.capture_serial:
            engine._pcm_reanalysis_epoch = engine._analysis_compute_state_epoch
            engine._pcm_reanalysis_ready = True
            return
        worker = engine._audio_worker
        if self.state is None:
            # Taken after the replay applied the mode's technical config, so the
            # configured floor/sensitivity drive the recomputed bands.
            self.state = worker.make_compute_snapshot()
            self.state._np = np
        block = int(worker._preferred_block_size or 0) or history.sample_rate // 100
        samples = np.frombuffer(history.pcm_f32le, dtype="<f4")[-block:]
        if compute_bars_from_samples(self.state, samples) is None:
            raise RuntimeError("production PCM analysis failed")
        worker.commit_compute_snapshot(self.state)
        engine._pcm_reanalysis_epoch = engine._analysis_compute_state_epoch
        engine._pcm_reanalysis_ready = True
        self.serial = history.capture_serial
        self.frames += 1


@contextmanager
def deterministic_clock():
    """Pin ``time.time``/``time.monotonic`` to a settable clock and seed ``random`` (restored on exit)."""
    now = [0.0]
    saved_random = random.getstate()
    saved_time, saved_monotonic = time.time, time.monotonic
    random.seed(1729)
    time.time = lambda: now[0]
    time.monotonic = lambda: now[0]
    try:
        yield now
    finally:
        time.time, time.monotonic = saved_time, saved_monotonic
        random.setstate(saved_random)


def configure_offline_controller(controller, mode, preset: int = 0, overrides=None, settings=None):
    """``settings``: a complete resolved settings mapping (or ``mode -> mapping``) used instead of the curated
    ``preset``; tests pass frozen copies so authored presets never decide them (Current_Plan N2)."""
    activation = None
    if settings is None:
        activation = resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": preset})
        resolved = activation.resolved_config
    else:
        resolved = settings(mode) if callable(settings) else settings
    model = SpotifyVisualizerSettings.from_mapping(
        resolved, apply_preset_overlay=False, resolve_preset_indices=False,
    )
    if overrides:
        model = replace(model, **dict(overrides))
    controller.set_mode(mode)
    controller.settings_model = model
    if activation is not None:
        controller.record_resolved_activation(activation)
    state = controller.logical_tick_state
    install_default_logical_tick_state(state, bar_count=controller.bar_count)
    install_default_presentation_state(controller.presentation_state)
    values = resolve_mode_source_config(mode, asdict(model))
    apply_logical_vis_mode_kwargs(state, values)
    apply_presentation_vis_mode_kwargs(controller.presentation_state, values)
    apply_engine_vis_mode_kwargs(controller.engine, values)
    controller.technical_config_cache = build_technical_cache(None, model)
    apply_controller_technical_config(controller, resolve_technical_config(controller.technical_config_cache, mode),
                                      reason="offline_replay")
    controller.enabled = True
    controller.playing = True
    controller.begin_render_activation(
        engine_generation=controller.engine.get_generation_id(),
        activation_id=controller.engine.get_activation_id(),
    )
    state._mode_teardown_block_until_ready = False
    state._mode_transition_ready = True
    state._waiting_for_fresh_engine_frame = False


__all__ = [
    "PRODUCTION_WAVEFORM_BLOCK", "PcmReanalysis", "ReplayBeatEngine", "SCHEMA_1_MUSIC",
    "configure_offline_controller", "deterministic_clock",
]
