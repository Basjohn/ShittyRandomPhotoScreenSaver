"""Spotify Visualizer Audio Worker - Audio capture and inline FFT processing.

This module contains the SpotifyVisualizerAudioWorker class which handles:
- Audio capture via loopback
- Inline FFT processing for visualizer bars
"""

from __future__ import annotations

import copy
from contextlib import nullcontext
from dataclasses import dataclass
from enum import Enum, auto
from types import SimpleNamespace
from typing import List, Optional
import threading
import time

from PySide6.QtCore import QObject

from core.logging.logger import get_logger, is_verbose_logging
from core.process import ProcessSupervisor
from utils.lockfree import TripleBuffer
from utils.audio_capture import (
    CAPTURE_FIRST_CALLBACK_GRACE_S,
    CAPTURE_STALE_AFTER_S,
    AudioCaptureConfig,
    create_audio_capture,
)


logger = get_logger(__name__)


_COMPUTE_SNAPSHOT_ATTRS = (
    "_activation_id",
    "_np",
    "_bar_count",
    "_band_cache_key",
    "_band_log_idx",
    "_band_bins",
    "_weight_bands",
    "_weight_factors",
    "_smooth_kernel",
    "_work_bars",
    "_zero_bars",
    "_band_edges",
    "_freq_values",
    "_bar_history",
    "_bar_hold_timers",
    "_running_peak",
    "_env_short",
    "_env_long",
    "_env_bass_short",
    "_env_bass_long",
    "_env_mix_short",
    "_env_mix_long",
    "_agc_bass_split",
    "_agc_mid_split",
    "_last_fft_ts",
    "_base_output_scale",
    "_energy_boost",
    "_input_gain",
    "_use_dynamic_floor",
    "_manual_floor",
    "_min_floor",
    "_max_floor",
    "_raw_bass_avg",
    "_dynamic_floor_ratio",
    "_dynamic_floor_alpha",
    "_dynamic_floor_decay_alpha",
    "_applied_noise_floor",
    "_last_noise_floor",
    "_gate_floor",
    "_support_pressure",
    "_support_signal_avg",
    "_support_pressure_alpha",
    "_support_pressure_decay_alpha",
    "_floor_response",
    "_floor_mid_weight",
    "_floor_headroom",
    "_silence_floor_threshold",
    "_floor_min_ratio",
    "_last_bass_drop_ratio",
    "_bass_drop_accum",
    "_drop_hold_frames",
    "_drop_threshold",
    "_drop_decay_fast",
    "_drop_snap_fraction",
    "_drop_speed",
    "_agc_strength",
    "_spectrum_notch_positions",
    "_transient_bus",
    "_kick_lane_gain",
    "_spectrum_lane_transient_mix",
    "_transient_clamp",
    "_transient_bass",
    "_transient_mid",
    "_transient_high",
    "_onset_detected",
    "_onset_type",
    "_onset_strength",
    "_onset_events",
    "_pre_agc_control_norm",
    "_pre_agc_control_bass",
    "_pre_agc_control_mid",
    "_pre_agc_control_treble",
    "_pre_agc_live_bass",
    "_pre_agc_live_mid",
    "_pre_agc_live_treble",
    "_pre_agc_bass",
    "_pre_agc_mid",
    "_pre_agc_treble",
    "_use_recommended",
    "_user_sensitivity",
    "_bars_log_last_ts",
    "_bars_log_interval",
    "_floor_log_last_ts",
    "_floor_log_last_mode",
    "_floor_log_last_applied",
    "_floor_log_last_manual",
    "_floor_log_last_applied_bucket",
    "_recommended_sensitivity_multiplier",
    "_last_sensitivity_config",
    "_last_floor_config",
    "_spectrum_shape_config",
    "_spectrum_mirrored",
    "_spectrum_shape_nodes",
    "_bar_gate_prev1",
    "_bar_gate_prev2",
    "_bar_gate_output",
    "_last_raw_bass",
    "_last_raw_mid",
    "_last_raw_treble",
    "_prev_raw_bass",
)

class VisualizerMode(Enum):
    """Visualization display modes for the Spotify visualizer."""
    SPECTRUM = auto()       # Classic segmented bar analyzer
    OSCILLOSCOPE = auto()   # Audio waveform spline with glow
    SINE_WAVE = auto()      # Pure sine wave with audio-reactive amplitude
    BUBBLE = auto()         # Sound-reactive bubble/water tank flow
    DEVCURVE = auto()            # Reactive liquid pool (dev-gated)


@dataclass
class _AudioFrame:
    samples: object
    activation_id: Optional[int] = None
    # Wall-clock time at capture publication. Analysis age must be measured
    # from when the audio actually arrived, not from the tick that happened
    # to consume it.
    capture_ts: float = 0.0


class SpotifyVisualizerAudioWorker(QObject):
    """Background audio worker for Spotify Beat Visualizer.

    Captures loopback audio using the centralized audio_capture module and
    publishes raw mono samples into a lock-free TripleBuffer for UI consumption.
    """

    def __init__(
        self,
        bar_count: int = 32,
        buffer: Optional[TripleBuffer[_AudioFrame]] = None,
        parent: Optional[QObject] = None,
        process_supervisor: Optional[ProcessSupervisor] = None,
    ) -> None:
        super().__init__(parent)
        self._bar_count = max(1, int(bar_count))
        self._buffer = buffer if buffer is not None else TripleBuffer[_AudioFrame]()
        self._running: bool = False
        self._backend = None  # AudioCaptureBackend instance
        self._activation_id: int = 0
        self._np = None
        # FFT band caching
        self._band_cache_key = None
        self._band_log_idx = None
        self._band_bins = None
        self._weight_bands = None
        self._weight_factors = None
        # Pre-allocated buffers to reduce GC pressure (avoid per-frame allocation)
        self._smooth_kernel = None
        self._work_bars = None  # output bars buffer
        self._zero_bars = None  # cached zero bars list
        self._band_edges = None  # logarithmic band edges
        self._freq_values = None  # temp buffer for frequency band values
        # Per-bar history for attack/decay dynamics
        self._bar_history = None
        self._bar_hold_timers = None
        # Dual-window envelope normalizer (replaces single _running_peak)
        self._running_peak = 1.0          # kept for compat reads
        self._env_short = 0.5             # short-term RMS envelope (~300ms)
        self._env_long = 0.5              # long-term average envelope (~3s)
        # Split envelopes for bass vs mix (Approach A dual-stage AGC)
        self._env_bass_short: float = 0.5
        self._env_bass_long: float = 0.5
        self._env_mix_short: float = 0.5
        self._env_mix_long: float = 0.5
        # Bar zone split indices (set by fft_to_bars, read by AGC)
        self._agc_bass_split: int = 4
        self._agc_mid_split: int = 10
        # Timestamp of last FFT processing - used to detect pause/resume gaps
        self._last_fft_ts: float = 0.0
        # Output scaling to keep FFT peaks controlled while allowing safe boosts
        self._base_output_scale: float = 0.5
        self._energy_boost: Optional[float] = None
        self._input_gain: Optional[float] = None
        # Floor control configuration (dynamic/manual)
        self._use_dynamic_floor: Optional[bool] = None
        self._manual_floor: Optional[float] = None
        self._min_floor: float = 0.0
        self._max_floor: float = 1.0
        self._raw_bass_avg: float = 0.12
        # Slightly higher dynamic floor baseline (10% harder to peak).
        self._dynamic_floor_ratio: float = 0.44
        self._dynamic_floor_alpha: float = 0.08
        self._dynamic_floor_decay_alpha: float = 0.12
        self._applied_noise_floor: float = 0.12
        self._last_noise_floor: float = 0.12
        self._gate_floor: float = 0.12
        self._support_pressure: float = 0.0
        self._support_signal_avg: float = 0.12
        self._support_pressure_alpha: float = 0.14
        self._support_pressure_decay_alpha: float = 0.18
        self._floor_response: float = 0.08
        self._floor_mid_weight: float = 0.18
        self._floor_headroom: float = 0.18
        self._silence_floor_threshold: float = 0.05
        self._floor_min_ratio: float = 0.22
        self._last_bass_drop_ratio: float = 0.0
        self._bass_drop_accum: float = 0.0
        # Drop handling configuration
        self._drop_hold_frames: int = 2
        self._drop_threshold: float = 0.16
        self._drop_decay_fast: float = 0.72
        self._drop_snap_fraction: float = 0.58
        self._drop_speed: Optional[float] = None
        self._agc_strength: Optional[float] = None
        self._spectrum_notch_positions: Optional[list] = None
        self._preferred_block_size: Optional[int] = None

        # Transient bus (dual-path Approach A)
        from widgets.spotify_visualizer.transient_bus import TransientBus
        self._transient_bus: TransientBus = TransientBus()
        self._kick_lane_gain: Optional[float] = None
        self._spectrum_lane_transient_mix: Optional[float] = None
        self._transient_clamp: Optional[float] = None
        # Latest transient snapshot fields (written by bar_computation, read by beat_engine)
        self._transient_bass: float = 0.0
        self._transient_mid: float = 0.0
        self._transient_high: float = 0.0
        self._onset_detected: bool = False
        self._onset_type: str = ""
        self._onset_strength: float = 0.0
        self._onset_events: tuple = ()      # the bus's published MusicalOnsets
        # Shared control-lane energies (pre-AGC, dynamically normalised).
        # These are separate from the AGC source fields so we can keep
        # visualizer control dynamics expressive under hot passages without
        # perturbing spectrum AGC internals.
        self._pre_agc_control_norm: float = 1.0
        self._pre_agc_control_bass: float = 0.0
        self._pre_agc_control_mid: float = 0.0
        self._pre_agc_control_treble: float = 0.0
        self._pre_agc_live_bass: float = 0.0
        self._pre_agc_live_mid: float = 0.0
        self._pre_agc_live_treble: float = 0.0
        # Every attribute in _COMPUTE_SNAPSHOT_ATTRS must be initialised here.
        # make_compute_snapshot() deep-copies each one via getattr with no default,
        # and it can be requested before the first processed frame (the retained
        # compute lane rebuilds on gate/activation/config boundaries). If any is
        # assigned only lazily during processing, the snapshot raises AttributeError
        # every frame -> the beat engine produces zero frames (engine=0/0) -> the
        # visualizer shows only idle motion even while audio is playing. These are
        # transient DSP state, not settings defaults; seed them to their first-use
        # values (see the reset block near _fft_to_bars).
        self._pre_agc_bass: float = 0.0
        self._pre_agc_mid: float = 0.0
        self._pre_agc_treble: float = 0.0
        self._last_raw_bass: float = 0.0
        self._last_raw_mid: float = 0.0
        self._last_raw_treble: float = 0.0
        self._prev_raw_bass: float = 0.0
        self._bar_gate_prev1 = None
        self._bar_gate_prev2 = None
        self._bar_gate_output = None

        # Sensitivity configuration (driven from Settings UI).
        self._cfg_lock = threading.Lock()
        self._use_recommended: Optional[bool] = None
        self._user_sensitivity: Optional[float] = None
        self._frame_debug_counter: int = 0
        self._bars_log_last_ts: float = 0.0
        self._bars_log_interval: float = 5.0
        # Logging throttling for floor diagnostics
        self._floor_log_last_ts: float = 0.0
        self._floor_log_last_mode: Optional[str] = None
        self._floor_log_last_applied: float = -1.0
        self._floor_log_last_manual: float = -1.0
        self._floor_log_last_applied_bucket: float = -1.0
        # Recommended-mode tuning uses a fixed manual-equivalent sensitivity multiplier.
        self._recommended_sensitivity_multiplier: float = 0.285
        
        # Last config for replay
        self._last_sensitivity_config = None
        self._last_floor_config = None
        
        # Spectrum shape config (pushed from UI/presets, consumed by fft_to_bars)
        self._spectrum_shape_config = None
        self._spectrum_mirrored: Optional[bool] = None
        self._spectrum_shape_nodes: Optional[list] = None
        self._effective_block_size: int = 0
        self._capture_callback_failures: int = 0
        # Native loopback backends create and release COM/audio resources.  The
        # BeatEngine injects one ThreadManager affinity lane before the worker
        # can admit capture.  Do not create a thread or run a synchronous
        # compatibility path here: the lane is the sole native-capture owner.
        self._capture_lane = None
        self._capture_lock = threading.RLock()
        self._capture_generation: int = 0
        self._capture_start_pending = False
        self._capture_restart_pending = False
        self._capture_stop_pending = False
        self._capture_owner_scheduled = False
        self._capture_desired_running = False
        self._backend_generation = 0
        self._capture_release_failed = False
        self._capture_config_epoch = 0
        self._capture_applied_config_epoch = 0
        self._capture_started_monotonic = 0.0
        self._capture_last_callback_monotonic = 0.0

    def set_capture_lane(self, lane) -> None:
        """Install the one engine-owned serial native-capture lane.

        This must happen before a capture start.  Replacing a live owner would
        allow two native streams to overlap, so it is deliberately rejected.
        """
        with self._capture_lock:
            if lane is self._capture_lane:
                return
            if (
                self._running
                or self._capture_start_pending
                or self._capture_stop_pending
                or self._capture_owner_scheduled
                or self._backend is not None
            ):
                raise RuntimeError("cannot replace an active audio capture owner")
            self._capture_lane = lane

    def has_capture_owner_work(self) -> bool:
        """Whether native capture still owns or is retiring a lane transaction."""
        with self._capture_lock:
            return bool(
                self._running
                or self._backend is not None
                or self._capture_start_pending
                or self._capture_restart_pending
                or self._capture_stop_pending
                or self._capture_owner_scheduled
            )

    def set_sensitivity_config(self, recommended: bool, sensitivity: float) -> None:
        rec = bool(recommended)
        sens = max(0.25, min(2.5, float(sensitivity)))
        with self._cfg_lock:
            self._use_recommended = rec
            self._user_sensitivity = sens
        self._last_sensitivity_config = (rec, sens)

    def set_floor_config(self, dynamic_enabled: bool, manual_floor: float) -> None:
        dyn = bool(dynamic_enabled)
        floor = max(self._min_floor, min(self._max_floor, float(manual_floor)))

        with self._cfg_lock:
            self._use_dynamic_floor = dyn
            self._manual_floor = floor
            self._raw_bass_avg = floor
            self._applied_noise_floor = floor
            self._last_noise_floor = floor
            self._gate_floor = floor
            self._support_pressure = 0.0
            self._support_signal_avg = floor
            self._running_peak = 0.5
        self._last_floor_config = (dyn, floor)

    def set_audio_block_size(self, block_size: int) -> None:
        value = max(0, int(block_size))
        with self._capture_lock:
            previous = self._preferred_block_size
            if value == previous:
                return
            self._preferred_block_size = value
            self._capture_config_epoch += 1
            running = self._running and self._capture_desired_running
            admitted = True
            if running:
                # Mutate the desired configuration and admit its drain together;
                # a fast owner must not complete it before an extra GUI restart
                # request is submitted for the same configuration.
                self._capture_restart_pending = True
                admitted = self._schedule_capture_owner_locked()
                if not admitted:
                    self._capture_restart_pending = False

        if not running:
            return

        logger.info(
            "[SPOTIFY_VIS] Audio block size changed while running (%s -> %d); restarting capture",
            previous,
            value,
        )
        if not admitted:
            logger.warning(
                "[SPOTIFY_VIS] Audio capture restart was not admitted after block size change (preferred=%d)",
                value,
            )

    def set_drop_speed(self, speed: float) -> None:
        """Set the spectrum drop speed multiplier (0.5–3.0)."""
        self._drop_speed = max(0.5, min(3.0, float(speed)))

    def set_notch_positions(self, positions: list) -> None:
        """Set resolved frequency-zone notch positions for band boundaries."""
        if not isinstance(positions, list) or len(positions) < 2:
            raise ValueError("Spectrum notch positions must contain at least two entries")
        self._spectrum_notch_positions = positions

    def set_spectrum_shape_config(self, config) -> None:
        """Push one fully-resolved SpectrumShapeConfig to the DSP pipeline."""
        from widgets.spotify_visualizer.bar_computation import SpectrumShapeConfig

        if not isinstance(config, SpectrumShapeConfig):
            raise TypeError("Spectrum shape config must be SpectrumShapeConfig")
        self._spectrum_shape_config = config

    def set_spectrum_mirrored(self, mirrored: bool) -> None:
        self._spectrum_mirrored = bool(mirrored)

    def set_spectrum_shape_nodes(self, nodes: list) -> None:
        if not isinstance(nodes, list) or not nodes:
            raise ValueError("Spectrum shape nodes must be a non-empty list")
        self._spectrum_shape_nodes = nodes

    def set_agc_strength(self, strength: float) -> None:
        self._agc_strength = max(0.0, min(1.0, float(strength)))

    def set_input_gain(self, gain: float) -> None:
        self._input_gain = max(0.05, min(2.0, float(gain)))

    def set_transient_lane_config(
        self,
        kick_lane_gain: float,
        spectrum_lane_transient_mix: float,
        transient_clamp: float,
    ) -> None:
        """Set resolved transient express-lane controls consumed by FFT."""
        self._kick_lane_gain = max(0.0, min(2.0, float(kick_lane_gain)))
        self._spectrum_lane_transient_mix = max(
            0.0, min(1.0, float(spectrum_lane_transient_mix))
        )
        self._transient_clamp = max(0.0, min(3.0, float(transient_clamp)))

    def set_energy_boost(self, boost: float) -> None:
        self._energy_boost = max(0.5, min(1.8, float(boost)))

    def reset_reactivity_state(self) -> None:
        """Clear adaptive DSP state that must not bleed across modes."""

        if self._manual_floor is None:
            raise RuntimeError("visualizer floor configuration is unresolved")
        floor = float(self._manual_floor)
        with self._cfg_lock:
            self._raw_bass_avg = floor
            self._applied_noise_floor = floor
            self._last_noise_floor = floor
            self._gate_floor = floor
            self._support_pressure = 0.0
            self._support_signal_avg = floor
            self._running_peak = 0.5
            self._env_short = 0.5
            self._env_long = 0.5
            self._env_bass_short = 0.5
            self._env_bass_long = 0.5
            self._env_mix_short = 0.5
            self._env_mix_long = 0.5
            self._agc_bass_split = 4
            self._agc_mid_split = 10
            self._last_raw_bass = 0.0
            self._last_raw_mid = 0.0
            self._last_raw_treble = 0.0
            self._prev_raw_bass = 0.0
            self._last_bass_drop_ratio = 0.0
            self._bass_drop_accum = 0.0
            self._bar_gate_prev1 = None
            self._bar_gate_prev2 = None
            self._bar_gate_output = None
            self._bar_history = None
            self._bar_hold_timers = None
            self._last_fft_ts = 0.0
            self._transient_bass = 0.0
            self._transient_mid = 0.0
            self._transient_high = 0.0
            self._onset_detected = False
            self._onset_type = ""
            self._onset_strength = 0.0
            self._onset_events = ()
            self._pre_agc_bass = 0.0
            self._pre_agc_mid = 0.0
            self._pre_agc_treble = 0.0
            self._pre_agc_control_norm = 1.0
            self._pre_agc_control_bass = 0.0
            self._pre_agc_control_mid = 0.0
            self._pre_agc_control_treble = 0.0
            self._pre_agc_live_bass = 0.0
            self._pre_agc_live_mid = 0.0
            self._pre_agc_live_treble = 0.0
        # Replace rather than mutate the bus in place. The serial analysis
        # lane may still be finishing a fenced packet against the previous
        # detached state; replacing the live reset authority avoids mutating a
        # bus that packet can still reference.
        try:
            from widgets.spotify_visualizer.transient_bus import TransientBus
            fresh = TransientBus()
            fresh.adopt_musical_context(self._transient_bus)
            self._transient_bus = fresh
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to replace transient bus", exc_info=True)

    def reset_processing_caches(self) -> None:
        """Discard bar-shaping/banding caches at a runtime activation boundary."""

        self._band_cache_key = None
        self._band_log_idx = None
        self._band_bins = None
        self._weight_bands = None
        self._weight_factors = None
        self._smooth_kernel = None
        self._work_bars = None
        self._zero_bars = None
        self._band_edges = None
        self._freq_values = None

    def reconfigure_bar_count(self, bar_count: int) -> None:
        """Rebuild bar-count-dependent runtime state using the startup contract."""
        new_count = max(1, int(bar_count))
        if new_count == self._bar_count:
            return

        self._bar_count = new_count
        self.reset_processing_caches()
        self.reset_reactivity_state()

    def is_running(self) -> bool:
        with self._capture_lock:
            return self._running

    # Bounded reporting for a capture callback that is running but cannot
    # publish. The installed run proved why this matters: a NameError in the
    # callback silenced every audio frame for the whole session while the
    # worker still reported itself started, and the only evidence was a DEBUG
    # line. Loud on the first failure, sampled after that, never per-frame.
    _CAPTURE_FAILURE_LOG_INTERVAL = 1000

    def _report_capture_callback_failure(self, exc: BaseException) -> None:
        """Report a capture callback failure loudly once, then boundedly."""
        try:
            self._capture_callback_failures += 1
            count = self._capture_callback_failures
        except Exception:
            count = 1
        if count == 1:
            logger.error(
                "[SPOTIFY_VIS] Audio capture callback failed; no frames are being "
                "published while the worker reports running",
                exc_info=True,
            )
            return
        if count % self._CAPTURE_FAILURE_LOG_INTERVAL == 0:
            logger.error(
                "[SPOTIFY_VIS] Audio capture callback still failing "
                "(failures=%d, last=%s: %s)",
                count,
                type(exc).__name__,
                exc,
            )

    def _note_capture_callback_recovered(self) -> None:
        """One publication succeeded again; re-arm the loud first report."""
        failures = self._capture_callback_failures
        self._capture_callback_failures = 0
        logger.info(
            "[SPOTIFY_VIS] Audio capture callback recovered after %d failed frames",
            failures,
        )

    def start(self) -> None:
        """Queue a native-capture start on the engine-owned affinity lane."""
        with self._capture_lock:
            if self._capture_release_failed:
                raise RuntimeError("audio capture admission is closed after native release failure")
            if self._capture_desired_running:
                return
            if self._preferred_block_size is None:
                raise RuntimeError("visualizer audio block-size configuration is unresolved")
            lane = self._capture_lane
            if lane is None or bool(getattr(lane, "is_stopped", False)):
                raise RuntimeError("visualizer audio capture requires its affinity lane")
            self._capture_generation += 1
            self._capture_desired_running = True
            self._capture_start_pending = True
            self._capture_started_monotonic = 0.0
            self._capture_last_callback_monotonic = 0.0
            if not self._schedule_capture_owner_locked():
                self._capture_desired_running = False
                self._capture_start_pending = False
                raise RuntimeError("visualizer audio capture affinity lane rejected start")

    def _schedule_capture_owner_locked(self) -> bool:
        """Admit one drain packet; later requests replace its desired state.

        Admission and desired-state mutation share the lock, so concurrent
        stop/start cannot invert submissions. Native work never holds it.
        """
        if self._capture_owner_scheduled:
            return True
        lane = self._capture_lane
        if lane is None or bool(getattr(lane, "is_stopped", False)):
            return False
        self._capture_owner_scheduled = True
        try:
            accepted = bool(lane.submit(self._drain_capture_on_owner))
        except Exception:
            self._capture_owner_scheduled = False
            logger.exception("[SPOTIFY_VIS] Audio capture affinity lane submission failed")
            raise
        if not accepted:
            self._capture_owner_scheduled = False
        return accepted

    def _on_audio_samples(self, generation: int, samples) -> None:
        """Process a backend callback only while its owner generation is live."""
        try:
            with self._capture_lock:
                if generation != self._capture_generation or not (
                    self._running or self._capture_start_pending
                ):
                    return
                activation_id = getattr(self, "_activation_id", None)
                buffer = self._buffer
            np_mod = self._np
            if samples is None or len(samples) == 0:
                return
            callback_ts = time.monotonic()
            capture_ts = time.time()

            if hasattr(samples, "ndim") and samples.ndim > 1:
                arr = np_mod.asarray(samples, dtype=np_mod.float32)
                channel_count = arr.shape[1] if arr.ndim > 1 else 1
                if channel_count <= 1:
                    mono = arr.reshape(-1)
                else:
                    selected = arr
                    if channel_count > 2:
                        energy = np_mod.sum(arr * arr, axis=0)
                        top_k = min(2, channel_count)
                        top_idx = np_mod.argsort(energy)[-top_k:]
                        selected = arr[:, top_idx]
                    mono = np_mod.mean(selected, axis=1, dtype=np_mod.float32)
            else:
                mono = np_mod.asarray(samples, dtype=np_mod.float32)

            # Both selected native backends deliver normalized float32 PCM.
            # Integer conversion is not a second supported capture format.
            if mono.size > 2048:
                mono = mono[-2048:]

            frame = _AudioFrame(
                samples=mono.copy(),
                activation_id=activation_id,
                capture_ts=capture_ts,
            )
            with self._capture_lock:
                if generation != self._capture_generation or not (
                    self._running or self._capture_start_pending
                ):
                    return
                if activation_id != getattr(self, "_activation_id", None) or buffer is not self._buffer:
                    return
                # Only the tiny final publication is atomic with stop admission;
                # channel selection/conversion/copy must not block the GUI lock.
                buffer.publish(frame)
                self._capture_last_callback_monotonic = callback_ts
            if self._capture_callback_failures:
                self._note_capture_callback_recovered()

            if is_verbose_logging():
                peak = float(np_mod.max(np_mod.abs(mono))) if mono.size else 0.0
                self._frame_debug_counter += 1
                if self._frame_debug_counter % 60 == 1:
                    logger.debug("[SPOTIFY_VIS][VERBOSE] loopback frame: samples=%d peak=%.4f", mono.size, peak)
        except Exception as exc:
            self._report_capture_callback_failure(exc)

    def _release_capture_backend_on_owner(self, backend) -> None:
        try:
            backend.stop()
            self._capture_lane.set_resource_held(False)
        except Exception:
            logger.exception("[SPOTIFY_VIS] Audio capture stop failed on owner lane")
            with self._capture_lock:
                # Retain a backend whose close failed even if its open was
                # rejected. Losing the local reference would hide native debt
                # and allow another stream to overlap unresolved resources.
                self._backend = backend
                self._backend_generation = -1
                self._capture_generation += 1
                self._capture_desired_running = False
                self._running = False
                self._capture_start_pending = False
                self._capture_restart_pending = False
                self._capture_stop_pending = True
                self._capture_owner_scheduled = False
                self._capture_release_failed = True
            raise

    def _drain_capture_on_owner(self) -> None:
        """Reconcile one native backend with the newest admitted lifecycle state.

        There is one executing/queued transaction and one overwriteable desired
        state, never a FIFO of start/stop closures. Retired resources close before
        any replacement opens, including when a driver blocks during start.
        """
        while True:
            with self._capture_lock:
                backend = self._backend
                generation = self._capture_generation
                desired = self._capture_desired_running
                if backend is not None and (
                    not desired or self._backend_generation != generation
                ):
                    action = "stop"
                elif not desired:
                    self._capture_stop_pending = False
                    self._capture_owner_scheduled = False
                    return
                elif backend is None:
                    action = "start"
                elif (
                    self._capture_restart_pending
                    or self._capture_applied_config_epoch != self._capture_config_epoch
                ):
                    action = "restart"
                    self._capture_restart_pending = True
                    self._capture_started_monotonic = 0.0
                    self._capture_last_callback_monotonic = 0.0
                else:
                    self._capture_owner_scheduled = False
                    return
                config_epoch = self._capture_config_epoch
                preferred = int(self._preferred_block_size or 0)

            if action == "stop":
                # Keep the pointer until release succeeds. A failed native close
                # must remain visible and cannot admit an overlapping backend.
                self._release_capture_backend_on_owner(backend)
                with self._capture_lock:
                    self._backend = None
                continue

            if action == "start":
                backend = None
                try:
                    # A first NumPy import is part of cold capture preparation,
                    # so it belongs off the GUI thread with native construction.
                    import numpy as np
                    self._np = np
                    config = AudioCaptureConfig(
                        sample_rate=48000, channels=2, block_size=preferred
                    )
                    backend = create_audio_capture(config)
                    if backend is None:
                        logger.error("[SPOTIFY_VIS] No audio capture backend available")
                        succeeded = False
                    else:
                        self._capture_lane.set_resource_held(True)
                        succeeded = bool(backend.start(
                            lambda samples, epoch=generation: self._on_audio_samples(epoch, samples)
                        ))
                        if not succeeded:
                            logger.error("[SPOTIFY_VIS] Audio capture backend rejected start")
                except Exception:
                    logger.exception("[SPOTIFY_VIS] Audio capture start failed on owner lane")
                    succeeded = False
            else:
                try:
                    backend_cfg = getattr(backend, "_config", None)
                    if backend_cfg is not None:
                        backend_cfg.block_size = preferred
                    logger.info("[SPOTIFY_VIS] Restarting audio capture on its owner lane")
                    succeeded = bool(backend.restart())
                    if not succeeded:
                        logger.error("[SPOTIFY_VIS] Audio capture restart failed")
                except Exception:
                    logger.exception("[SPOTIFY_VIS] Audio capture restart failed on owner lane")
                    succeeded = False

            with self._capture_lock:
                current = (
                    generation == self._capture_generation
                    and self._capture_desired_running
                )
                adopted = current and succeeded
                if adopted:
                    self._backend = backend
                    self._backend_generation = generation
                    self._running = True
                    self._capture_start_pending = False
                    self._capture_stop_pending = False
                    # The grace starts at native success, not GUI admission.
                    # A callback from inside start/restart already proved health;
                    # adoption must preserve that observation.
                    self._capture_started_monotonic = time.monotonic()
                    self._capture_applied_config_epoch = config_epoch
                    self._capture_restart_pending = False
                    self._effective_block_size = int(
                        getattr(backend, "_negotiated_block_size", 0) or 0
                    )
                elif current:
                    # A failed operation is terminal until another explicit
                    # start/wake. Never spin a native retry/fallback loop.
                    self._capture_desired_running = False
                    self._running = False
                    self._capture_start_pending = False
                    self._capture_restart_pending = False
                    self._capture_started_monotonic = 0.0
                    self._capture_last_callback_monotonic = 0.0
                    self._effective_block_size = 0

            if not adopted and backend is not None:
                self._release_capture_backend_on_owner(backend)
                with self._capture_lock:
                    if self._backend is backend:
                        self._backend = None
            if adopted:
                logger.info(
                    "[SPOTIFY_VIS] Audio capture %s on owner lane (%s, effective_block=%d, preferred=%d)",
                    "started" if action == "start" else "restarted",
                    backend.__class__.__name__,
                    self._effective_block_size,
                    preferred,
                )
            # Requests arriving during native work are read once more here.
            # A stop fences callbacks immediately and this drain releases the
            # old backend exactly once before processing the newest start.

    def stop(self) -> None:
        """Fence capture immediately; its admitted drain releases native state."""
        with self._capture_lock:
            if not (
                self._capture_desired_running or self._backend is not None
                or self._capture_owner_scheduled
            ):
                return
            self._capture_generation += 1
            self._capture_desired_running = False
            self._running = False
            self._capture_start_pending = False
            self._capture_restart_pending = False
            self._effective_block_size = 0
            self._capture_started_monotonic = 0.0
            self._capture_last_callback_monotonic = 0.0
            self._capture_stop_pending = True
            if not self._schedule_capture_owner_locked():
                raise RuntimeError("visualizer audio capture affinity lane rejected stop")

    def is_capture_healthy(self) -> bool:
        """Check if audio capture is receiving data (callback firing)."""
        with self._capture_lock:
            if not self._running or self._capture_last_callback_monotonic <= 0.0:
                return False
            return (time.monotonic() - self._capture_last_callback_monotonic) < CAPTURE_STALE_AFTER_S

    def is_capture_starting(self) -> bool:
        """True while a started stream is still waiting for its first callback."""
        with self._capture_lock:
            if self._capture_start_pending:
                return True
            if not self._running or self._capture_last_callback_monotonic > 0.0:
                return False
            return (time.monotonic() - self._capture_started_monotonic) < CAPTURE_FIRST_CALLBACK_GRACE_S

    def is_capture_stale(self) -> bool:
        """True only for a capture that ran (or should have) and then went quiet.

        This is the only condition that authorizes a wake-driven restart; a
        just-started capture is deliberately not stale.
        """
        with self._capture_lock:
            if self._capture_start_pending or not self._running:
                return False
            observed = self._capture_last_callback_monotonic or self._capture_started_monotonic
            if observed <= 0.0:
                return False
            threshold = (
                CAPTURE_STALE_AFTER_S
                if self._capture_last_callback_monotonic > 0.0
                else CAPTURE_FIRST_CALLBACK_GRACE_S
            )
            return (time.monotonic() - observed) >= threshold

    def restart_capture(self) -> bool:
        """Return admission/coalescing success, not asynchronous native outcome."""
        with self._capture_lock:
            if not self._capture_desired_running:
                return False
            if self._capture_start_pending or self._capture_restart_pending:
                return True
            if not self._running or self._backend is None:
                return False
            self._capture_restart_pending = True
            if self._schedule_capture_owner_locked():
                return True
            self._capture_restart_pending = False
            logger.error("[SPOTIFY_VIS] Audio capture affinity lane rejected restart")
            return False

    # ------------------------------------------------------------------
    # FFT Processing
    # ------------------------------------------------------------------

    def _get_zero_bars(self) -> List[float]:
        """Delegates to widgets.spotify_visualizer.bar_computation."""
        from widgets.spotify_visualizer.bar_computation import get_zero_bars
        return get_zero_bars(self)

    def _fft_to_bars(self, fft) -> List[float]:
        """Delegates to widgets.spotify_visualizer.bar_computation."""
        from widgets.spotify_visualizer.bar_computation import fft_to_bars
        return fft_to_bars(self, fft)

    def _maybe_log_floor_state(self, **kwargs) -> None:
        """Delegates to widgets.spotify_visualizer.bar_computation."""
        from widgets.spotify_visualizer.bar_computation import maybe_log_floor_state
        maybe_log_floor_state(self, **kwargs)

    def make_compute_snapshot(self) -> SimpleNamespace:
        """Return detached DSP state for one serial-lane admission epoch.

        The retained compute lane reuses this object across ordinary audio
        frames and rebuilds it only after a gate/activation/config boundary.
        That preserves stale-result isolation without deep-copying NumPy and
        history state on every FFT step. The synchronous no-lane diagnostic
        path may still use it as a one-shot snapshot.
        """

        state = SimpleNamespace()
        for name in _COMPUTE_SNAPSHOT_ATTRS:
            value = getattr(self, name)
            if name == "_np":
                setattr(state, name, value)
                continue
            try:
                setattr(state, name, copy.deepcopy(value))
            except Exception:
                try:
                    setattr(state, name, copy.copy(value))
                except Exception:
                    setattr(state, name, value)
        state._cfg_lock = nullcontext()
        return state

    def commit_compute_snapshot(self, state: object) -> None:
        """Commit mutable DSP state produced by a verified compute job."""

        runtime_attrs = (
            "_band_cache_key",
            "_band_log_idx",
            "_band_bins",
            "_weight_bands",
            "_weight_factors",
            "_smooth_kernel",
            "_work_bars",
            "_zero_bars",
            "_band_edges",
            "_freq_values",
            "_bar_history",
            "_bar_hold_timers",
            "_running_peak",
            "_env_short",
            "_env_long",
            "_env_bass_short",
            "_env_bass_long",
            "_env_mix_short",
            "_env_mix_long",
            "_agc_bass_split",
            "_agc_mid_split",
            "_last_fft_ts",
            "_raw_bass_avg",
            "_applied_noise_floor",
            "_last_noise_floor",
            "_gate_floor",
            "_support_pressure",
            "_support_signal_avg",
            "_last_bass_drop_ratio",
            "_bass_drop_accum",
            "_transient_bus",
            "_transient_bass",
            "_transient_mid",
            "_transient_high",
            "_onset_detected",
            "_onset_type",
            "_onset_strength",
            "_onset_events",
            "_pre_agc_control_norm",
            "_pre_agc_control_bass",
            "_pre_agc_control_mid",
            "_pre_agc_control_treble",
            "_pre_agc_live_bass",
            "_pre_agc_live_mid",
            "_pre_agc_live_treble",
            "_pre_agc_bass",
            "_pre_agc_mid",
            "_pre_agc_treble",
            "_bar_gate_prev1",
            "_bar_gate_prev2",
            "_bar_gate_output",
            "_last_raw_bass",
            "_last_raw_mid",
            "_last_raw_treble",
            "_prev_raw_bass",
            "_floor_log_last_ts",
            "_floor_log_last_mode",
            "_floor_log_last_applied",
            "_floor_log_last_manual",
            "_floor_log_last_applied_bucket",
            "_bars_log_last_ts",
        )
        for name in runtime_attrs:
            if hasattr(state, name):
                setattr(self, name, getattr(state, name))

    def compute_bars_from_samples(self, samples) -> Optional[List[float]]:
        """Delegates to widgets.spotify_visualizer.bar_computation."""
        from widgets.spotify_visualizer.bar_computation import compute_bars_from_samples
        return compute_bars_from_samples(self, samples)
