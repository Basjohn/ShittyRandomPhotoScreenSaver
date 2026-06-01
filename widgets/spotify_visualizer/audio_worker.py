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
import os
import threading

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger, is_verbose_logging
from core.process import ProcessSupervisor
from utils.lockfree import TripleBuffer
from utils.audio_capture import create_audio_capture, AudioCaptureConfig


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
    "_transient_bass",
    "_transient_mid",
    "_transient_high",
    "_onset_detected",
    "_onset_type",
    "_onset_strength",
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

try:
    _DEBUG_CONST_BARS = float(os.environ.get("SRPSS_SPOTIFY_VIS_DEBUG_CONST", "0.0"))
except Exception as e:
    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
    _DEBUG_CONST_BARS = 0.0


class VisualizerMode(Enum):
    """Visualization display modes for the Spotify visualizer."""
    SPECTRUM = auto()       # Classic segmented bar analyzer
    OSCILLOSCOPE = auto()   # Audio waveform spline with glow
    BLOB = auto()           # Organic reactive metaball
    SINE_WAVE = auto()      # Pure sine wave with audio-reactive amplitude
    BUBBLE = auto()         # Sound-reactive bubble/water tank flow
    DEVCURVE = auto()            # Reactive liquid pool (dev-gated)


@dataclass
class _AudioFrame:
    samples: object
    activation_id: Optional[int] = None


class SpotifyVisualizerAudioWorker(QObject):
    """Background audio worker for Spotify Beat Visualizer.

    Captures loopback audio using the centralized audio_capture module and
    publishes raw mono samples into a lock-free TripleBuffer for UI consumption.
    """

    def __init__(
        self,
        bar_count: int = 32,
        buffer: Optional[TripleBuffer[_AudioFrame]] = None,
        parent: Optional[QWidget] = None,
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
        self._energy_boost: float = 0.85
        self._input_gain: float = 1.0
        # Floor control configuration (dynamic/manual)
        self._use_dynamic_floor: bool = True
        self._manual_floor: float = 0.12
        self._min_floor: float = 0.0
        self._max_floor: float = 1.0
        self._raw_bass_avg: float = 0.12
        # Slightly higher dynamic floor baseline (10% harder to peak).
        self._dynamic_floor_ratio: float = 0.44
        self._dynamic_floor_alpha: float = 0.08
        self._dynamic_floor_decay_alpha: float = 0.12
        self._applied_noise_floor: float = 0.12
        self._last_noise_floor: float = 0.12
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
        self._drop_speed: float = 1.0
        self._agc_strength: float = 0.5
        self._spectrum_notch_positions: Optional[list] = None
        self._preferred_block_size: int = 0

        # Transient bus (dual-path Approach A)
        from widgets.spotify_visualizer.transient_bus import TransientBus
        self._transient_bus: TransientBus = TransientBus()
        self._kick_lane_gain: float = 1.0  # Spectrum kick express lane gain (0-2)
        # Latest transient snapshot fields (written by bar_computation, read by beat_engine)
        self._transient_bass: float = 0.0
        self._transient_mid: float = 0.0
        self._transient_high: float = 0.0
        self._onset_detected: bool = False
        self._onset_type: str = ""
        self._onset_strength: float = 0.0
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

        # Sensitivity configuration (driven from Settings UI).
        self._cfg_lock = threading.Lock()
        self._use_recommended: bool = True
        self._user_sensitivity: float = 1.0
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
        self._last_sensitivity_config = (True, 1.0)
        self._last_floor_config = (True, 2.1)
        
        # Spectrum shape config (pushed from UI/presets, consumed by fft_to_bars)
        self._spectrum_shape_config = None  # SpectrumShapeConfig or None → uses defaults
        self._spectrum_mirrored: bool = True  # center-out mirrored layout
        self._spectrum_shape_nodes: list = [[0.0, 0.40], [0.35, 0.75], [0.65, 0.55], [1.0, 0.80]]
        self._effective_block_size: int = 0

    def set_sensitivity_config(self, recommended: bool, sensitivity: float) -> None:
        try:
            rec = bool(recommended)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            rec = True

        try:
            sens = float(sensitivity)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            sens = 1.0
        if sens < 0.25:
            sens = 0.25
        if sens > 2.5:
            sens = 2.5

        with self._cfg_lock:
            self._use_recommended = rec
            self._user_sensitivity = sens
        self._last_sensitivity_config = (rec, sens)

    def set_floor_config(self, dynamic_enabled: bool, manual_floor: float) -> None:
        try:
            dyn = bool(dynamic_enabled)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            dyn = True

        try:
            floor = float(manual_floor)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            floor = self._manual_floor

        floor = max(self._min_floor, min(self._max_floor, floor))

        with self._cfg_lock:
            self._use_dynamic_floor = dyn
            self._manual_floor = floor
            self._raw_bass_avg = floor
            self._applied_noise_floor = floor
            self._last_noise_floor = floor
            self._running_peak = 0.5
        self._last_floor_config = (dyn, floor)

    def set_audio_block_size(self, block_size: int) -> None:
        try:
            value = int(block_size)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            value = 0
        if value < 0:
            value = 0
        previous = self._preferred_block_size
        if value == previous:
            return
        self._preferred_block_size = value
        if not self._running or self._backend is None:
            return

        backend_cfg = getattr(self._backend, "_config", None)
        if backend_cfg is not None:
            try:
                backend_cfg.block_size = value
            except Exception:
                logger.debug(
                    "[SPOTIFY_VIS] Failed to update backend block-size config before restart",
                    exc_info=True,
                )

        logger.info(
            "[SPOTIFY_VIS] Audio block size changed while running (%d -> %d); restarting capture",
            previous,
            value,
        )
        restarted = self.restart_capture()
        if restarted:
            logger.info(
                "[SPOTIFY_VIS] Audio capture restarted for block size change (preferred=%d effective=%d)",
                value,
                self._effective_block_size,
            )
        else:
            logger.warning(
                "[SPOTIFY_VIS] Audio capture restart failed after block size change (preferred=%d)",
                value,
            )

    def set_curved_profile(self, enabled: bool) -> None:
        """Deprecated — curved profile is now always active. Kept as no-op for compat."""
        pass

    def set_drop_speed(self, speed: float) -> None:
        """Set the spectrum drop speed multiplier (0.5–3.0).

        Thread-safe: single float assignment is atomic on CPython.
        Read by _apply_reactive_smoothing in bar_computation.py.
        """
        self._drop_speed = max(0.5, min(3.0, float(speed)))

    def set_notch_positions(self, positions: list) -> None:
        """Set frequency-zone notch positions for dynamic band boundaries.

        Thread-safe: list reference assignment is atomic on CPython.
        Read by fft_to_bars in bar_computation.py.
        """
        if isinstance(positions, list) and len(positions) >= 2:
            self._spectrum_notch_positions = positions

    def set_spectrum_shape_config(self, config) -> None:
        """Push a SpectrumShapeConfig to the DSP pipeline.

        Thread-safe: the config dataclass is immutable once created and is
        read atomically by fft_to_bars on the audio thread.
        """
        self._spectrum_shape_config = config

    def set_spectrum_mirrored(self, mirrored: bool) -> None:
        """Toggle center-out mirrored layout vs left-to-right linear."""
        self._spectrum_mirrored = bool(mirrored)

    def set_spectrum_shape_nodes(self, nodes: list) -> None:
        """Push shape editor nodes to the DSP pipeline (read by fft_to_bars)."""
        if isinstance(nodes, list) and len(nodes) >= 1:
            self._spectrum_shape_nodes = nodes

    def set_agc_strength(self, strength: float) -> None:
        """Set AGC normalization strength (0.0=off, 0.5=default, 1.0=aggressive)."""
        try:
            val = float(strength)
        except Exception:
            val = 0.5
        if val < 0.0:
            val = 0.0
        if val > 1.0:
            val = 1.0
        self._agc_strength = val

    def set_input_gain(self, gain: float) -> None:
        """Adjust pre-FFT input gain (virtual volume). Scales PCM before FFT."""
        try:
            val = float(gain)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            val = 1.0
        if val < 0.05:
            val = 0.05
        if val > 2.0:
            val = 2.0
        self._input_gain = val

    def set_energy_boost(self, boost: float) -> None:
        """Adjust post-FFT energy boost factor."""
        try:
            val = float(boost)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            val = 1.0
        if val < 0.5:
            val = 0.5
        if val > 1.8:
            val = 1.8
        self._energy_boost = val

    def reset_reactivity_state(self) -> None:
        """Clear adaptive DSP state that must not bleed across modes."""

        try:
            floor = float(self._manual_floor)
        except Exception:
            floor = 0.12
        with self._cfg_lock:
            self._raw_bass_avg = floor
            self._applied_noise_floor = floor
            self._last_noise_floor = floor
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
        try:
            self._transient_bus.reset()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to reset transient bus", exc_info=True)

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
        return self._running

    def start(self) -> None:
        """Start audio capture using centralized audio_capture module."""
        if self._running:
            return

        try:
            import numpy as np
        except ImportError as exc:
            logger.info("[SPOTIFY_VIS] numpy not available: %s", exc)
            return
        self._np = np

        block_size = self._preferred_block_size if self._preferred_block_size > 0 else 0
        config = AudioCaptureConfig(sample_rate=48000, channels=2, block_size=block_size)
        self._backend = create_audio_capture(config)
        
        if self._backend is None:
            logger.info("[SPOTIFY_VIS] No audio capture backend available")
            return

        def _on_audio_samples(samples) -> None:
            """Process incoming audio samples."""
            try:
                np_mod = self._np
                if samples is None or len(samples) == 0:
                    return
                
                if hasattr(samples, "ndim") and samples.ndim > 1:
                    arr = np_mod.asarray(samples, dtype=np_mod.float32)
                    channel_count = arr.shape[1] if arr.ndim > 1 else 1
                    if channel_count <= 1:
                        mono = arr.reshape(-1)
                    else:
                        selected = arr
                        if channel_count > 2:
                            try:
                                energy = np_mod.sum(arr * arr, axis=0)
                                top_k = min(2, channel_count)
                                top_idx = np_mod.argsort(energy)[-top_k:]
                                selected = arr[:, top_idx]
                            except Exception as e:
                                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                                selected = arr[:, :2]
                        mono = np_mod.mean(selected, axis=1, dtype=np_mod.float32)
                else:
                    mono = np_mod.asarray(samples, dtype=np_mod.float32)
                
                if mono.dtype == np_mod.int16:
                    mono = mono.astype(np_mod.float32) / 32768.0
                
                if mono.size > 2048:
                    mono = mono[-2048:]
                
                self._buffer.publish(_AudioFrame(
                    samples=mono.copy(),
                    activation_id=getattr(self, "_activation_id", None),
                ))
                
                if is_verbose_logging():
                    peak = float(np_mod.max(np_mod.abs(mono))) if mono.size else 0.0
                    self._frame_debug_counter += 1
                    if self._frame_debug_counter % 60 == 1:
                        logger.debug("[SPOTIFY_VIS][VERBOSE] loopback frame: samples=%d peak=%.4f", mono.size, peak)
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                if is_verbose_logging():
                    logger.debug("[SPOTIFY_VIS] Audio callback failed", exc_info=True)

        if self._backend.start(_on_audio_samples):
            self._running = True
            self._effective_block_size = int(getattr(self._backend, "_negotiated_block_size", 0) or 0)
            logger.info(
                "[SPOTIFY_VIS] Audio worker started (%s, %dHz, %d channels, effective_block=%d, preferred=%d)",
                self._backend.__class__.__name__,
                self._backend.sample_rate,
                self._backend.channels,
                self._effective_block_size,
                self._preferred_block_size,
            )
        else:
            logger.info("[SPOTIFY_VIS] Failed to start audio capture")
            self._backend = None

    def stop(self) -> None:
        """Stop audio capture."""
        if not self._running:
            return
        self._running = False
        if self._backend is not None:
            try:
                self._backend.stop()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            self._backend = None
        self._effective_block_size = 0
        logger.info("[SPOTIFY_VIS] Audio worker stopped")

    def is_capture_healthy(self) -> bool:
        """Check if audio capture is receiving data (callback firing)."""
        if self._backend is None:
            return False
        try:
            return self._backend.is_healthy()
        except Exception:
            return False

    def restart_capture(self) -> bool:
        """Restart the audio capture stream."""
        if self._backend is None:
            return False
        try:
            logger.info("[SPOTIFY_VIS] Restarting audio capture...")
            restarted = self._backend.restart()
            if restarted:
                self._effective_block_size = int(getattr(self._backend, "_negotiated_block_size", 0) or 0)
            return restarted
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Failed to restart capture: %s", e)
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
        """Return a detached DSP state object for one FFT compute job.

        Background compute tasks must not mutate the live worker until the
        owning beat-engine callback verifies the current activation token.
        The bar computation module intentionally writes its intermediate
        floor/AGC/transient/bar-history state into the object it receives, so
        we give it a plain snapshot and commit only after the token check.
        """

        state = SimpleNamespace()
        for name in _COMPUTE_SNAPSHOT_ATTRS:
            if not hasattr(self, name):
                continue
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
            "_last_bass_drop_ratio",
            "_bass_drop_accum",
            "_transient_bus",
            "_transient_bass",
            "_transient_mid",
            "_transient_high",
            "_onset_detected",
            "_onset_type",
            "_onset_strength",
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

