"""Spotify Visualizer Audio Worker - Audio capture and FFT processing.

This module contains the SpotifyVisualizerAudioWorker class which handles:
- Audio capture via loopback
- FFT processing for visualizer bars
- Integration with FFTWorker process for offloaded processing
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
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

try:
    _DEBUG_CONST_BARS = float(os.environ.get("SRPSS_SPOTIFY_VIS_DEBUG_CONST", "0.0"))
except Exception as e:
    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
    _DEBUG_CONST_BARS = 0.0


class VisualizerMode(Enum):
    """Visualization display modes for the Spotify visualizer."""
    SPECTRUM = auto()       # Classic segmented bar analyzer
    OSCILLOSCOPE = auto()   # Audio waveform spline with glow
    STARFIELD = auto()      # Audio-reactive traveling starfield
    BLOB = auto()           # Organic reactive metaball
    HELIX = auto()          # DNA / double-helix spiral
    SINE_WAVE = auto()      # Pure sine wave with audio-reactive amplitude


@dataclass
class _AudioFrame:
    samples: object


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
        # Running peak tracker for normalization
        self._running_peak = 1.0
        # Timestamp of last FFT processing - used to detect pause/resume gaps
        self._last_fft_ts: float = 0.0
        # Output scaling to keep FFT peaks controlled while allowing safe boosts
        self._base_output_scale: float = 0.5
        self._energy_boost: float = 0.85
        # Floor control configuration (dynamic/manual)
        self._use_dynamic_floor: bool = True
        self._manual_floor: float = 2.1
        self._min_floor: float = 0.12
        self._max_floor: float = 4.0
        self._raw_bass_avg: float = 2.1
        # Slightly higher dynamic floor baseline (10% harder to peak).
        self._dynamic_floor_ratio: float = 0.462
        self._dynamic_floor_alpha: float = 0.15
        self._dynamic_floor_decay_alpha: float = 0.4
        self._applied_noise_floor: float = 2.1
        self._floor_response: float = 0.12
        self._floor_mid_weight: float = 0.18
        self._floor_headroom: float = 0.18
        self._silence_floor_threshold: float = 0.05
        self._floor_min_ratio: float = 0.22
        self._last_bass_drop_ratio: float = 0.0
        self._bass_drop_accum: float = 0.0
        # Drop handling configuration
        self._drop_hold_frames: int = 3
        self._drop_threshold: float = 0.18
        self._drop_decay_fast: float = 0.6
        self._drop_snap_fraction: float = 0.45
        self._preferred_block_size: int = 0

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
        # Recommended-mode tuning uses a fixed manual-equivalent sensitivity multiplier.
        self._recommended_sensitivity_multiplier: float = 0.285
        
        # Last config for replay
        self._last_sensitivity_config = (True, 1.0)
        self._last_floor_config = (True, 2.1)
        
        # Spectrum profile variant (curved vs legacy)
        self._use_curved_profile: bool = False

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
            floor = 2.1

        floor = max(self._min_floor, min(self._max_floor, floor))

        with self._cfg_lock:
            self._use_dynamic_floor = dyn
            self._manual_floor = floor
        self._last_floor_config = (dyn, floor)
        if not dyn:
            self._raw_bass_avg = floor

    def set_audio_block_size(self, block_size: int) -> None:
        try:
            value = int(block_size)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            value = 0
        if value < 0:
            value = 0
        self._preferred_block_size = value

    def set_curved_profile(self, enabled: bool) -> None:
        """Toggle between curved and legacy spectrum bar profile."""
        self._use_curved_profile = bool(enabled)

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
                
                self._buffer.publish(_AudioFrame(samples=mono.copy()))
                
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
            logger.info(
                "[SPOTIFY_VIS] Audio worker started (%s, %dHz, %d channels)",
                self._backend.__class__.__name__,
                self._backend.sample_rate,
                self._backend.channels,
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
            return self._backend.restart()
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

    def compute_bars_from_samples(self, samples) -> Optional[List[float]]:
        """Delegates to widgets.spotify_visualizer.bar_computation."""
        from widgets.spotify_visualizer.bar_computation import compute_bars_from_samples
        return compute_bars_from_samples(self, samples)
