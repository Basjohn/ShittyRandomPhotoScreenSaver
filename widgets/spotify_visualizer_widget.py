from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Dict, Any
import os
import time
import math
import threading
import logging
import random

from PySide6.QtCore import QObject, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from core.threading.manager import ThreadManager
from core.process import ProcessSupervisor, WorkerType, MessageType
from utils.lockfree import TripleBuffer
from utils.audio_capture import create_audio_capture, AudioCaptureConfig
from widgets.shadow_utils import apply_widget_shadow, ShadowFadeProfile, configure_overlay_widget_attributes


from utils.profiler import profile


class VisualizerMode(Enum):
    """Visualization display modes for the Spotify visualizer.

    Only SPECTRUM is currently implemented. Other modes are planned for future releases:
    - WAVEFORM_RIBBON: Morphing waveform that mirrors in place (TimArt/3DAudioVisualizers)
    - DNA_HELIX: Dual helices twisting with amplitude (ShaderToy dtl3Dr)
    - RADIAL_BLOOM: Polar coordinate FFT display (GLava radial module)
    - SPECTROGRAM: Scrolling history of FFT frames (Stanford CCRMA)
    - PHASOR_SWARM: Particle emitters on bar positions (PAV Phasor)
    """
    SPECTRUM = auto()        # Classic bar spectrum analyzer - FUNCTIONAL
    WAVEFORM_RIBBON = auto() # Morphing waveform ribbon - NOT IMPLEMENTED
    DNA_HELIX = auto()       # Dual helices with amplitude - NOT IMPLEMENTED
    RADIAL_BLOOM = auto()    # Polar coordinate FFT display - NOT IMPLEMENTED
    SPECTROGRAM = auto()     # Scrolling history ribbon - NOT IMPLEMENTED
    PHASOR_SWARM = auto()    # Particle emitters on bar positions - NOT IMPLEMENTED

logger = get_logger(__name__)

try:
    _DEBUG_CONST_BARS = float(os.environ.get("SRPSS_SPOTIFY_VIS_DEBUG_CONST", "0.0"))
except Exception as e:
    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
    _DEBUG_CONST_BARS = 0.0


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
        # ProcessSupervisor for FFTWorker integration
        self._process_supervisor = process_supervisor
        self._fft_worker_available: bool = False
        self._fft_worker_failed_count: int = 0
        self._fft_worker_max_failures: int = 5  # Disable after 5 consecutive failures
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
        # "Recommended" uses the v1.4 baseline constants. Manual mode lets
        # the user scale sensitivity relative to that baseline.
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
        self._recommended_sensitivity_multiplier: float = 0.285  # ~manual 0.28x for deeper drops

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
            # Snap running average to manual value so we don't jump if user re-enables dynamic.
            self._raw_bass_avg = floor
        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
            if engine is not None:
                engine.set_floor_config(dyn, floor)
                self._last_floor_config = (dyn, floor)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to propagate floor config to shared engine", exc_info=True)

    def set_audio_block_size(self, block_size: int) -> None:
        try:
            value = int(block_size)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            value = 0
        if value < 0:
            value = 0
        self._preferred_block_size = value

    def set_energy_boost(self, boost: float) -> None:
        """Adjust post-FFT energy boost factor (used for future tuning hooks)."""
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

    def set_process_supervisor(self, supervisor: Optional[ProcessSupervisor]) -> None:
        """Set the ProcessSupervisor for FFTWorker integration.
        
        When set and FFTWorker is running, FFT processing is offloaded to a
        separate process for better performance (avoids GIL contention).
        """
        self._process_supervisor = supervisor
        self._fft_worker_available = False
        self._fft_worker_failed_count = 0
        
        if supervisor is not None:
            try:
                self._fft_worker_available = supervisor.is_running(WorkerType.FFT)
                if self._fft_worker_available:
                    logger.info("[SPOTIFY_VIS] FFTWorker available for audio processing")
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                self._fft_worker_available = False

    def _process_via_fft_worker(self, samples) -> Optional[List[float]]:
        """Process audio samples using FFTWorker in separate process.
        
        Returns bar heights if successful, None if worker unavailable or failed.
        Falls back to local processing on failure.
        """
        if not self._process_supervisor or not self._fft_worker_available:
            return None
        
        if self._fft_worker_failed_count >= self._fft_worker_max_failures:
            return None
        
        try:
            # Check if worker is still running
            if not self._process_supervisor.is_running(WorkerType.FFT):
                self._fft_worker_available = False
                return None
            
            # Convert samples to list for serialization
            samples_list = samples.tolist() if hasattr(samples, 'tolist') else list(samples)
            
            # Get current sensitivity config
            with self._cfg_lock:
                use_recommended = bool(self._use_recommended)
                user_sens = float(self._user_sensitivity)
                use_dynamic_floor = bool(self._use_dynamic_floor)
            
            sensitivity = user_sens if not use_recommended else 1.0
            
            # Send FFT_FRAME message to worker
            correlation_id = self._process_supervisor.send_message(
                WorkerType.FFT,
                MessageType.FFT_FRAME,
                payload={
                    "samples": samples_list,
                    "sample_rate": 48000,
                    "sensitivity": sensitivity,
                    "use_dynamic_floor": use_dynamic_floor,
                },
            )
            
            if not correlation_id:
                self._fft_worker_failed_count += 1
                return None
            
            # Poll for response with short timeout (audio is real-time)
            start_time = time.time()
            timeout_s = 0.015  # 15ms max for real-time audio
            
            while (time.time() - start_time) < timeout_s:
                responses = self._process_supervisor.poll_responses(WorkerType.FFT, max_count=5)
                
                for response in responses:
                    if response.correlation_id == correlation_id:
                        if response.success:
                            bars = response.payload.get("bars", [])
                            if bars and len(bars) > 0:
                                self._fft_worker_failed_count = 0  # Reset on success
                                return bars
                        else:
                            self._fft_worker_failed_count += 1
                            return None
                
                time.sleep(0.001)  # 1ms poll interval
            
            # Timeout - don't count as failure (worker may be busy)
            return None
            
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] FFTWorker processing error: %s", e)
            self._fft_worker_failed_count += 1
            return None

    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start audio capture using centralized audio_capture module."""
        if self._running:
            return

        # NumPy is required for FFT
        try:
            import numpy as np
        except ImportError as exc:
            logger.info("[SPOTIFY_VIS] numpy not available: %s", exc)
            return
        self._np = np

        # Create audio capture backend
        block_size = self._preferred_block_size if self._preferred_block_size > 0 else 0
        config = AudioCaptureConfig(sample_rate=48000, channels=2, block_size=block_size)
        self._backend = create_audio_capture(config)
        
        if self._backend is None:
            logger.info("[SPOTIFY_VIS] No audio capture backend available")
            return

        # Define callback to process audio samples
        def _on_audio_samples(samples) -> None:
            """Process incoming audio samples."""
            try:
                np_mod = self._np
                if samples is None or len(samples) == 0:
                    return
                
                # Convert to mono float32 if needed
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
                
                # Normalize if int16
                if mono.dtype == np_mod.int16:
                    mono = mono.astype(np_mod.float32) / 32768.0
                
                # Limit buffer size
                if mono.size > 2048:
                    mono = mono[-2048:]
                
                # Publish to triple buffer
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

        # Start capture
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

    # ------------------------------------------------------------------
    # FFT Processing
    # ------------------------------------------------------------------

    def _get_zero_bars(self) -> List[float]:
        """Return cached zero bars list to avoid per-call allocation."""
        if self._zero_bars is None or len(self._zero_bars) != self._bar_count:
            self._zero_bars = [0.0] * self._bar_count
        return self._zero_bars

    def _fft_to_bars(self, fft) -> List[float]:
        """Convert FFT magnitudes to visualizer bar heights.
        
        Optimized to minimize per-frame allocations for reduced GC pressure.
        Uses pre-allocated buffers and in-place operations where possible.
        """
        np = self._np
        if fft is None:
            return self._get_zero_bars()

        bands = int(self._bar_count)
        if bands <= 0:
            return []

        try:
            mag = fft[1:]
            if mag.size == 0:
                return self._get_zero_bars()
            if np.iscomplexobj(mag):
                mag = np.abs(mag)
            mag = mag.astype("float32", copy=False)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            return self._get_zero_bars()

        n = int(mag.size)
        if n <= 0:
            return self._get_zero_bars()
        resolution_boost = max(0.5, min(3.0, 1024.0 / max(256.0, float(n))))
        low_resolution = resolution_boost > 1.05

        try:
            # In-place log1p and power operations where possible
            np.log1p(mag, out=mag)
            np.power(mag, 1.2, out=mag)

            if n > 4:
                try:
                    # Use cached kernel to avoid per-frame allocation
                    if self._smooth_kernel is None:
                        self._smooth_kernel = np.array([0.25, 0.5, 0.25], dtype="float32")
                    # convolve always allocates, but kernel is cached
                    mag = np.convolve(mag, self._smooth_kernel, mode="same")
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            return self._get_zero_bars()

        # Center-out frequency mapping with logarithmic binning
        # Bass in center, treble at edges - reactive with attack/decay dynamics
        cache_key = (n, bands)
        prev_raw_bass = getattr(self, "_prev_raw_bass", 0.0)
        bass_drop_ratio = 0.0
        drop_accum = getattr(self, "_bass_drop_accum", 0.0)
        drop_signal = 0.0
        center = bands // 2
        try:
            if getattr(self, "_band_cache_key", None) != cache_key:
                min_freq_idx = 1
                max_freq_idx = n
                
                log_edges = np.logspace(
                    np.log10(min_freq_idx),
                    np.log10(max_freq_idx),
                    bands + 1,
                    dtype="float32"
                ).astype("int32")
                
                self._band_cache_key = cache_key
                self._band_edges = log_edges
                self._work_bars = np.zeros(bands, dtype="float32")
                self._freq_values = np.zeros(bands, dtype="float32")
                self._bar_history = np.zeros(bands, dtype="float32")
                self._bar_hold_timers = np.zeros(bands, dtype="int32")
            
            edges = self._band_edges
            if edges is None:
                return self._get_zero_bars()
            
            arr = self._work_bars
            arr.fill(0.0)
            freq_values = self._freq_values
            freq_values.fill(0.0)
            
            # Compute RMS for each frequency band (standard left-to-right)
            for b in range(bands):
                start = int(edges[b])
                end = int(edges[b + 1])
                if end <= start:
                    end = start + 1
                if start < n and end <= n:
                    band_slice = mag[start:end]
                    if band_slice.size > 0:
                        freq_values[b] = np.sqrt(np.mean(band_slice ** 2))
            
            # CENTER-OUT mapping: bass in center, treble at edges
            
            # Get raw energy values
            raw_bass = float(np.mean(freq_values[:4])) if bands >= 4 else float(freq_values[0])
            raw_mid = float(np.mean(freq_values[4:10])) if bands >= 10 else raw_bass * 0.5
            raw_treble = float(np.mean(freq_values[10:])) if bands > 10 else raw_bass * 0.2
            self._last_raw_bass = raw_bass
            self._last_raw_mid = raw_mid
            self._last_raw_treble = raw_treble
            self._prev_raw_bass = raw_bass
            if low_resolution and prev_raw_bass > 1e-3:
                bass_drop_ratio = max(0.0, (prev_raw_bass - raw_bass) / prev_raw_bass)
            
            # Subtract noise floor and expand dynamic range
            # Adapt noise floor/expansion when FFT resolution drops (smaller block size).
            noise_floor_base = max(0.8, 1.5 / (resolution_boost ** 0.35))
            expansion_base = 3.6 * (resolution_boost ** 0.4)

            try:
                with self._cfg_lock:
                    use_recommended = bool(self._use_recommended)
                    user_sens = float(self._user_sensitivity)
                    use_dynamic_floor = bool(self._use_dynamic_floor)
                    manual_floor = float(self._manual_floor)
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                use_recommended = True
                user_sens = 1.0
                use_dynamic_floor = True
                manual_floor = noise_floor_base

            if user_sens < 0.25:
                user_sens = 0.25
            if user_sens > 2.5:
                user_sens = 2.5

            if use_recommended:
                auto_multiplier = float(getattr(self, "_recommended_sensitivity_multiplier", 0.38))
                auto_multiplier = max(0.25, min(2.5, auto_multiplier))
                if resolution_boost > 1.0:
                    damp = min(0.4, (resolution_boost - 1.0) * 0.55)
                    auto_multiplier = max(0.25, auto_multiplier * (1.0 - damp))
                else:
                    boost = min(0.25, (1.0 - resolution_boost) * 0.4)
                    auto_multiplier = min(2.5, auto_multiplier * (1.0 + boost))
                base_noise_floor = max(
                    self._min_floor,
                    min(self._max_floor, noise_floor_base / auto_multiplier),
                )
                exp_factor = max(0.55, auto_multiplier ** 0.35)
                expansion = expansion_base * exp_factor
            else:
                base_noise_floor = max(self._min_floor, min(self._max_floor, noise_floor_base / user_sens))
                try:
                    expansion = expansion_base * (user_sens ** 0.35)
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                    expansion = expansion_base

            noise_floor = base_noise_floor
            target_floor = base_noise_floor
            mode = "dynamic" if use_dynamic_floor else "manual"
            if use_dynamic_floor:
                avg = getattr(self, "_raw_bass_avg", base_noise_floor)
                try:
                    floor_mid_weight = float(self._floor_mid_weight)
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                    floor_mid_weight = 0.5
                floor_mid_weight = max(0.0, min(1.0, floor_mid_weight))
                if low_resolution:
                    floor_mid_weight = min(0.65, floor_mid_weight + 0.12 * (resolution_boost - 1.0))
                floor_signal = (raw_bass * (1.0 - floor_mid_weight)) + (raw_mid * floor_mid_weight)
                try:
                    silence_threshold = float(self._silence_floor_threshold)
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                    silence_threshold = 0.0
                silence_threshold = max(0.0, silence_threshold)
                if floor_signal < silence_threshold:
                    # Treat near-silence as bass-only to prevent spurious boosts.
                    floor_signal = raw_bass
                try:
                    alpha_rise = float(self._dynamic_floor_alpha)
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                    alpha_rise = 0.05
                try:
                    alpha_decay = float(self._dynamic_floor_decay_alpha)
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                    alpha_decay = alpha_rise
                alpha_rise = max(0.0, min(1.0, alpha_rise))
                alpha_decay = max(0.0, min(1.0, alpha_decay))
                alpha = alpha_rise if floor_signal >= avg else alpha_decay
                avg = (1.0 - alpha) * avg + alpha * floor_signal
                self._raw_bass_avg = avg
                dyn_ratio = getattr(self, "_dynamic_floor_ratio", 0.42)
                if low_resolution:
                    dyn_ratio = min(0.75, dyn_ratio * (1.0 + 0.35 * (resolution_boost - 1.0)))
                dyn_candidate = max(
                    self._min_floor,
                    min(self._max_floor, avg * dyn_ratio),
                )
                base_target = max(self._min_floor, min(base_noise_floor, dyn_candidate))
                target_floor = base_target
                try:
                    headroom = float(self._floor_headroom)
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                    headroom = 0.0
                if headroom > 0.0:
                    headroom = min(1.0, headroom)
                    blended = (floor_signal * (1.0 - headroom)) + (base_target * headroom)
                    target_floor = max(self._min_floor, min(base_noise_floor, blended))
                drop_relief = getattr(self, "_last_bass_drop_ratio", 0.0)
                if low_resolution and drop_relief > 0.05:
                    target_floor = max(self._min_floor, target_floor * (1.0 - drop_relief * 0.45))
            else:
                target_floor = max(self._min_floor, min(self._max_floor, manual_floor))

            try:
                applied_floor = getattr(self, "_applied_noise_floor", target_floor)
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                applied_floor = target_floor
            response = self._floor_response
            if response < 0.05:
                response = 0.05
            elif response > 1.0:
                response = 1.0

            applied_floor = applied_floor + (target_floor - applied_floor) * response
            self._applied_noise_floor = applied_floor
            noise_floor = applied_floor
            self._last_noise_floor = noise_floor
            self._maybe_log_floor_state(
                mode=mode,
                applied_floor=noise_floor,
                manual_floor=manual_floor,
                raw_bass=raw_bass,
                raw_mid=raw_mid,
                raw_treble=raw_treble,
                expansion=expansion,
            )

            bass_energy = max(0.0, (raw_bass - noise_floor) * expansion)
            mid_energy = max(0.0, (raw_mid - noise_floor * 0.4) * expansion)
            treble_energy = max(0.0, (raw_treble - noise_floor * 0.2) * expansion)

            # CENTER-OUT MIRRORED LAYOUT:
            # - Ridge peaks at offset ±3 from center (bar 4 and 10 for 15 bars) = BASS
            # - Center (bar 7) = VOCALS - most reactive, dips low with no vocals  
            # - Edges (bars 0,1,14,13) = KICKS/DRUMS/PERCUSSION
            #
            # Shape template defines the static ridge shape:
            # Index:  0     1     2     3     4     5     6     7     8     9    10    11    12    13    14
            # Offset: 7     6     5     4     3     2     1     0     1     2     3     4     5     6     7
            # Role:  edge  edge  edge slope PEAK slope shld  CTR  shld slope PEAK slope edge  edge  edge
            # Bar 4 (index 4, offset 3) = PEAK, Bar 3 (index 3, offset 4) = slope below peak
            profile_template = np.array(
                [0.10, 0.15, 0.25, 0.50, 1.0, 0.45, 0.25, 0.08, 0.25, 0.45, 1.0, 0.50, 0.25, 0.15, 0.10],
                dtype="float32",
            )
            if bands != profile_template.size:
                xp = np.linspace(0.0, 1.0, profile_template.size)
                x = np.linspace(0.0, 1.0, bands)
                profile_shape = np.interp(x, xp, profile_template)
            else:
                profile_shape = profile_template.copy()
            
            # Compute overall energy level from FFT
            # Balance: bass drives ridge but with headroom, mids drive center
            overall_energy = (bass_energy * 0.9 + mid_energy * 0.6 + treble_energy * 0.35)
            overall_energy = max(0.0, min(1.8, overall_energy))
            
            # Apply shape template scaled by overall energy
            for i in range(bands):
                offset = abs(i - center)
                
                # Base value from shape template - this defines the ridge shape
                base = profile_shape[i] * overall_energy
                
                # Ridge peak (offset 3) gets bass boost - moderate to allow dips
                if offset == 3:
                    base = base * 1.15 + bass_energy * 0.35
                # Offset 4 is the slope BELOW the peak
                elif offset == 4:
                    base = base * 0.82
                
                # Center bar (offset 0) is MOST REACTIVE to vocals
                # High sensitivity for both peaks AND dips
                if offset == 0:
                    vocal_drive = mid_energy * 4.0  # Very high multiplier for reactivity
                    base = vocal_drive * 0.90 + base * 0.10
                
                # Shoulder bars (offset 1-2) taper toward center
                if offset == 1:
                    base = base * 0.52 + mid_energy * 0.22
                if offset == 2:
                    base = base * 0.58 + bass_energy * 0.12
                
                # Edge bars (offset 5+) get percussion/treble - allow higher peaks
                if offset >= 5:
                    base = base * 0.65 + treble_energy * 0.4 * (offset - 4)
                
                arr[i] = base

            if low_resolution:
                # bias peaks toward bars around +/-3 from center, soften center slightly
                for i in range(bands):
                    offset = abs(i - center)
                    ridge_boost = 1.0
                    if offset == 3:
                        ridge_boost = 1.35
                    elif offset == 2 or offset == 4:
                        ridge_boost = 1.2
                    elif offset == 1:
                        ridge_boost = 1.05
                    elif offset == 0:
                        ridge_boost = 0.78
                    arr[i] *= ridge_boost

            drop_signal = bass_drop_ratio
            if low_resolution:
                valley_signal = 0.0
                if prev_raw_bass > 1e-3:
                    valley_signal = max(valley_signal, max(0.0, (prev_raw_bass - raw_bass) / prev_raw_bass))
                bass_floor_ref = max(noise_floor * 1.05, 1e-3)
                if raw_bass < bass_floor_ref:
                    valley_signal = max(
                        valley_signal,
                        min(0.9, (bass_floor_ref - raw_bass) / bass_floor_ref),
                    )
                drop_accum = drop_accum * 0.88 + valley_signal * 0.55
                if valley_signal < 0.02:
                    drop_accum *= 0.92
                drop_accum = max(0.0, min(1.0, drop_accum))
                drop_signal = max(drop_signal, drop_accum)
            self._bass_drop_accum = drop_accum
            if low_resolution and drop_signal > 0.05:
                drop_strength = min(0.92, 0.22 + drop_signal * 1.45)
                band_span = max(1, center)
                for i in range(bands):
                    dist = abs(i - center) / float(band_span)
                    emphasis = max(0.25, 1.0 - dist * 1.35)
                    arr[i] *= max(0.0, 1.0 - drop_strength * emphasis)
            if low_resolution:
                peak_left_idx = max(0, center - 3)
                peak_right_idx = min(bands - 1, center + 3)
                peak_val = max(arr[peak_left_idx], arr[peak_right_idx], 1e-3)
                drop_soften = max(0.0, 0.6 - drop_signal)
                center_cap_ratio = max(0.95, min(1.1, 0.97 + drop_soften * 0.18))
                center_cap = peak_val * center_cap_ratio
                center_val = arr[center]
                if center_val > center_cap:
                    arr[center] = center_cap
                    center_val = center_cap
                neighbor_ratio_outer = max(0.6, center_cap_ratio - 0.06)
                neighbor_ratio_inner = max(0.52, center_cap_ratio - 0.12)
                left_neighbor = max(0, center - 1)
                right_neighbor = min(bands - 1, center + 1)
                peak_neighbor_val_outer = peak_val * neighbor_ratio_outer
                if arr[left_neighbor] > peak_neighbor_val_outer:
                    arr[left_neighbor] = peak_neighbor_val_outer
                if arr[right_neighbor] > peak_neighbor_val_outer:
                    arr[right_neighbor] = peak_neighbor_val_outer
                left_outer = max(0, center - 2)
                right_outer = min(bands - 1, center + 2)
                outer_cap = peak_val * neighbor_ratio_inner
                if arr[left_outer] > outer_cap:
                    arr[left_outer] = outer_cap
                if arr[right_outer] > outer_cap:
                    arr[right_outer] = outer_cap
                if drop_signal > 0.02:
                    damp = min(0.38, 0.06 + drop_signal * 0.4)
                    center_scale = max(0.45, 1.0 - damp)
                    arr[center] *= center_scale
                    for offset in (1, 2):
                        left_idx = max(0, center - offset)
                        right_idx = min(bands - 1, center + offset)
                        neighbor_scale = max(0.55, 1.0 - damp * (0.36 if offset == 1 else 0.22))
                        arr[left_idx] *= neighbor_scale
                        arr[right_idx] *= neighbor_scale
                ridge_avg = 0.5 * (arr[peak_left_idx] + arr[peak_right_idx])
                center_floor = ridge_avg * (0.08 + drop_signal * 0.05) + 0.025
                center_cap_soft = ridge_avg * (0.28 + drop_signal * 0.1) + 0.05
                arr[center] = min(max(arr[center], center_floor), max(center_cap_soft, center_floor))
                target_map = {
                    0: 0.25 + drop_signal * 0.1,
                    1: 0.53 + drop_signal * 0.07,
                    2: 0.7,
                    3: 1.08,
                    4: 0.6,
                    5: 0.36,
                }
                max_offset = min(6, center + 1, bands - center)
                ridge_anchor = max(ridge_avg, 1e-3)
                for offset in range(max_offset):
                    ratio = target_map.get(offset, max(0.15, 0.5 - offset * 0.07))
                    desired_val = ridge_anchor * ratio
                    left_idx = center - offset
                    right_idx = center + offset
                    if left_idx >= 0:
                        arr[left_idx] = arr[left_idx] * 0.55 + desired_val * 0.45
                    if right_idx < bands:
                        arr[right_idx] = arr[right_idx] * 0.55 + desired_val * 0.45
                if bands > 2:
                    tmp = arr.copy()
                    arr[1:-1] = tmp[1:-1] * 0.46 + (tmp[:-2] + tmp[2:]) * 0.27
                    arr[0] = tmp[0] * 0.64 + tmp[1] * 0.36
                    arr[-1] = tmp[-1] * 0.64 + tmp[-2] * 0.36
            self._last_bass_drop_ratio = drop_signal
            
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            return self._get_zero_bars()

        # REACTIVE SMOOTHING: Fast attack, very aggressive decay for visible drops
        decay_rate = 0.35  # Much lower = much faster fall, makes drops very visible
        
        # CRITICAL: Detect pause/resume gaps (e.g., after settings dialog)
        # If more than 2 seconds have passed, reset bar_history to avoid
        # erratic smoothing behavior from stale state
        now_ts = time.time()
        dt = now_ts - self._last_fft_ts if self._last_fft_ts > 0 else 0.0
        self._last_fft_ts = now_ts
        
        bar_history = self._bar_history
        hold_timers = self._bar_hold_timers
        if hold_timers is None or hold_timers.shape[0] != bands:
            hold_timers = np.zeros(bands, dtype="int32")
            self._bar_hold_timers = hold_timers
        if dt > 2.0:
            # Reset bar history to current raw values after a long pause
            bar_history.fill(0.0)
            hold_timers.fill(0)
        
        # Drop detection parameters - work for ALL resolutions
        drop_threshold = 0.01  # Very low threshold = detect all drops
        drop_decay = 0.25  # Very fast decay during hold period
        hold_frames = 2  # Short hold to allow quick recovery
        snap_fraction = 0.15  # Snap down very aggressively on big drops

        for i in range(bands):
            target = arr[i]
            current = bar_history[i]
            hold = hold_timers[i]
            
            if target > current:
                # ATTACK: Rise quickly toward target
                attack_speed = 0.85  # 85% of the way to target per frame
                new_val = current + (target - current) * attack_speed
                hold_timers[i] = 0
            else:
                # DECAY: Fall toward target with smooth decay
                drop = current - target
                
                if drop > drop_threshold:
                    # Big drop detected - snap down faster
                    hold_timers[i] = hold_frames
                    new_val = current * snap_fraction + target * (1.0 - snap_fraction)
                elif hold > 0:
                    # In hold period after big drop - continue decaying
                    hold_timers[i] = hold - 1
                    new_val = current * drop_decay
                    if new_val < target:
                        new_val = target
                else:
                    # Normal decay toward target
                    new_val = current * decay_rate
                    if new_val < target:
                        new_val = target
            
            arr[i] = new_val
            bar_history[i] = new_val
        
        # Scale to get peaks near 1.0 while allowing configurable boosts
        scale = (self._base_output_scale or 0.8) * (self._energy_boost or 1.0)
        if scale < 0.1:
            scale = 0.1
        elif scale > 1.25:
            scale = 1.25
        arr *= scale

        # Adaptive normalization: keep long-term peaks from pinning at 1.0.
        try:
            peak_val = float(arr.max())
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            peak_val = 0.0
        max_tracked_peak = 1.35
        if peak_val > max_tracked_peak:
            peak_val = max_tracked_peak
        running_peak = getattr(self, "_running_peak", 0.5)
        try:
            floor_baseline = float(self._applied_noise_floor)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            floor_baseline = 2.0
        base_headroom = 0.45 + 0.1 * max(0.0, min(4.0, floor_baseline))
        _ = max(0.7, min(1.0, base_headroom))  # headroom_scale kept for future tuning
        if peak_val > running_peak:
            running_peak += (peak_val - running_peak) * 0.32
        else:
            fast_decay = 0.9 if peak_val < running_peak * 0.5 else 0.965
            running_peak = running_peak * fast_decay + peak_val * (1.0 - fast_decay)
        drop_relief = drop_signal if low_resolution else 0.0
        if low_resolution and drop_relief > 0.35:
            running_peak *= max(0.95, 1.0 - drop_relief * 0.08)
        running_peak = max(0.18, min(1.35, running_peak))
        self._running_peak = running_peak
        # Target peak of 1.0 allows full range for reactivity
        target_peak = 1.0
        if running_peak > target_peak * 1.1 and peak_val > 0.0:
            # Only normalize if significantly over target
            normalization = target_peak / max(running_peak, 1e-3)
            arr *= normalization

        np.clip(arr, 0.0, 1.0, out=arr)
        
        # Dedicated Spotify log snapshot (sparse, routed to screensaver_spotify_vis.log)
        try:
            now = time.time()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            now = 0.0
        last_snapshot = getattr(self, "_bars_log_last_ts", 0.0)
        min_interval = max(1.0, float(getattr(self, "_bars_log_interval", 5.0) or 5.0))
        if now <= 0.0 or (now - last_snapshot) >= min_interval:
            bar_str = " ".join(f"{v:.2f}" for v in arr)
            logger.info("[SPOTIFY_VIS][BARS] raw_bass=%.3f Bars=[%s]", float(raw_bass), bar_str)
            try:
                self._bars_log_last_ts = now
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        
        # tolist() still allocates, but this is unavoidable for the return type
        return arr.tolist()

    def _maybe_log_floor_state(
        self,
        *,
        mode: str,
        applied_floor: float,
        manual_floor: float,
        raw_bass: float,
        raw_mid: float,
        raw_treble: float,
        expansion: float,
    ) -> None:
        """Throttled logging for noise-floor diagnostics."""
        try:
            now = time.time()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            return

        last_ts = getattr(self, "_floor_log_last_ts", 0.0) or 0.0
        last_mode = getattr(self, "_floor_log_last_mode", None)
        last_applied = getattr(self, "_floor_log_last_applied", -1.0)
        last_manual = getattr(self, "_floor_log_last_manual", -1.0)

        def _changed(a: float, b: float, threshold: float = 0.05) -> bool:
            try:
                return abs(float(a) - float(b)) > threshold
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                return True

        state_changed = (
            last_mode != mode
            or _changed(applied_floor, last_applied)
            or _changed(manual_floor, last_manual)
        )

        throttle = 5.0
        if not state_changed and last_ts and (now - last_ts) < throttle:
            return

        try:
            logger.info(
                "[SPOTIFY_VIS][FLOOR] mode=%s applied=%.3f manual=%.3f bass=%.3f mid=%.3f treble=%.3f expansion=%.3f",
                mode,
                float(applied_floor),
                float(manual_floor),
                float(raw_bass),
                float(raw_mid),
                float(raw_treble),
                float(expansion),
            )
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            return
        finally:
            try:
                self._floor_log_last_ts = now
                self._floor_log_last_mode = mode
                self._floor_log_last_applied = applied_floor
                self._floor_log_last_manual = manual_floor
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

    def compute_bars_from_samples(self, samples) -> Optional[List[float]]:
        """Compute visualizer bars from audio samples.
        
        Optimized to minimize allocations - uses cached zero bars and
        avoids unnecessary list comprehensions.
        """
        np_mod = self._np
        if np_mod is None or samples is None:
            return None
        try:
            mono = samples
            if hasattr(mono, "ndim") and mono.ndim > 1:
                try:
                    mono = mono.reshape(-1)
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                    return None
            try:
                mono = mono.astype("float32", copy=False)
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

            # Measure peak once (used for both silence detection and optional gain).
            try:
                peak_raw = float(np_mod.abs(mono).max()) if getattr(mono, "size", 0) > 0 else 0.0
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                peak_raw = 0.0

            # Input gain calibration (cheap): some loopback backends provide
            # normalized float samples in [-1..1]. v1.4 tuning expects a higher
            # RMS range (raw_bass ~ 1.8-3.1) so we lift low-amplitude inputs,
            # but cap gain to avoid pinning bars at 1.0.
            # NOTE: Keep this conservative so synthetic test signals and quiet
            # audio don't become permanently clipped.
            if 0.05 <= peak_raw <= 5.0:
                try:
                    target_peak = 1.6
                    gain = target_peak / max(peak_raw, 1e-6)
                    if gain < 1.0:
                        gain = 1.0
                    if gain > 2.8:
                        gain = 2.8
                    if gain != 1.0:
                        mono = mono * gain
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            size = getattr(mono, "size", 0)
            if size <= 0:
                return None
            if size > 2048:
                mono = mono[-2048:]
            # Treat very low overall amplitude as silence and return zeros so
            # we don't amplify numerical noise into full-height bars when
            # audio stops.
            if peak_raw < 1e-3:
                return self._get_zero_bars()

            # Try FFTWorker first (separate process, avoids GIL contention)
            bars = None
            if self._fft_worker_available and self._fft_worker_failed_count < self._fft_worker_max_failures:
                bars = self._process_via_fft_worker(mono)
                if bars is not None:
                    # FFTWorker succeeded - adjust to target bar count if needed
                    target = int(self._bar_count)
                    if len(bars) != target:
                        if len(bars) < target:
                            bars = bars + [0.0] * (target - len(bars))
                        else:
                            bars = bars[:target]
                    return bars
            
            # Fallback to local FFT processing
            fft = np_mod.fft.rfft(mono)
            np_mod.abs(fft, out=fft)  # In-place abs
            bars = self._fft_to_bars(fft)
            if not isinstance(bars, list):
                return None
            target = int(self._bar_count)
            if target <= 0:
                return None
            if len(bars) != target:
                if len(bars) < target:
                    bars = bars + [0.0] * (target - len(bars))
                else:
                    bars = bars[:target]
            # bars already clamped in _fft_to_bars, no need for extra list comprehension
            return bars
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            if is_verbose_logging():
                logger.debug("[SPOTIFY_VIS] compute_bars_from_samples failed", exc_info=True)
            return None


class _SpotifyBeatEngine(QObject):
    """Shared beat engine with integrated smoothing.
    
    Smoothing is performed here (on COMPUTE pool callback) rather than in the
    UI thread tick, reducing UI thread load significantly.
    """
    
    def __init__(self, bar_count: int) -> None:
        super().__init__()
        self._bar_count = max(1, int(bar_count))
        self._audio_buffer: TripleBuffer[_AudioFrame] = TripleBuffer()
        self._audio_worker = SpotifyVisualizerAudioWorker(self._bar_count, self._audio_buffer, parent=self)
        self._bars_result_buffer: TripleBuffer[List[float]] = TripleBuffer()
        self._compute_task_active: bool = False
        self._thread_manager: Optional[ThreadManager] = None
        self._ref_count: int = 0
        self._latest_bars: Optional[List[float]] = None
        self._last_audio_ts: float = 0.0
        
        # Smoothing state (moved from widget to reduce UI thread work)
        self._smoothed_bars: List[float] = [0.0] * self._bar_count
        self._last_smooth_ts: float = -1.0
        self._smoothing_tau: float = 0.12  # Base smoothing time constant
        
        # Playback state gating for FFT processing
        self._is_spotify_playing: bool = False
        self._last_playback_state_ts: float = 0.0

    def set_thread_manager(self, thread_manager: Optional[ThreadManager]) -> None:
        self._thread_manager = thread_manager
    
    def set_process_supervisor(self, supervisor: Optional[ProcessSupervisor]) -> None:
        """Set the ProcessSupervisor for FFTWorker integration."""
        try:
            self._audio_worker.set_process_supervisor(supervisor)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to set process supervisor", exc_info=True)
    
    def set_smoothing(self, tau: float) -> None:
        """Set the base smoothing time constant."""
        self._smoothing_tau = max(0.05, float(tau))
    
    def set_sensitivity_config(self, recommended: bool, sensitivity: float) -> None:
        try:
            self._audio_worker.set_sensitivity_config(recommended, sensitivity)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to apply sensitivity config", exc_info=True)
    
    def set_floor_config(self, dynamic_enabled: bool, manual_floor: float) -> None:
        try:
            self._audio_worker.set_floor_config(dynamic_enabled, manual_floor)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to apply floor config", exc_info=True)

    def set_playback_state(self, is_playing: bool) -> None:
        """Set Spotify playback state for FFT processing gating.
        
        When False, FFT processing is halted and only 1-bar floor is shown.
        When True, normal FFT processing resumes.
        
        Args:
            is_playing: Whether Spotify is currently playing
        """
        self._is_spotify_playing = bool(is_playing)
        self._last_playback_state_ts = time.time()
        
        if is_verbose_logging():
            logger.debug(
                "[SPOTIFY_VIS] Beat engine playback state: playing=%s (ts=%.3f)",
                self._is_spotify_playing,
                self._last_playback_state_ts
            )

    def _apply_smoothing(self, target_bars: List[float]) -> List[float]:
        """Apply time-based exponential smoothing to bars.
        
        This is called from the COMPUTE pool callback, not the UI thread.
        """
        now_ts = time.time()
        last_ts = self._last_smooth_ts
        dt = max(0.0, now_ts - last_ts) if last_ts >= 0.0 else 0.0
        
        # CRITICAL: Reset smoothing state after a long pause (e.g., settings dialog)
        # A gap > 2 seconds indicates a pause/resume scenario.
        if dt > 2.0 or dt <= 0.0:
            # First frame, no time elapsed, or long pause - just copy raw values
            self._smoothed_bars = list(target_bars)
            return self._smoothed_bars
        
        base_tau = self._smoothing_tau
        tau_rise = base_tau * 0.35  # Fast attack
        tau_decay = base_tau * 3.0  # Slow decay
        alpha_rise = 1.0 - math.exp(-dt / tau_rise)
        alpha_decay = 1.0 - math.exp(-dt / tau_decay)
        alpha_rise = max(0.0, min(1.0, alpha_rise))
        alpha_decay = max(0.0, min(1.0, alpha_decay))
        
        bar_count = self._bar_count
        smoothed = self._smoothed_bars
        
        for i in range(bar_count):
            cur = smoothed[i] if i < len(smoothed) else 0.0
            tgt = target_bars[i] if i < len(target_bars) else 0.0
            alpha = alpha_rise if tgt >= cur else alpha_decay
            nxt = cur + (tgt - cur) * alpha
            if abs(nxt) < 1e-3:
                nxt = 0.0
            smoothed[i] = nxt
        
        return smoothed

    def acquire(self) -> None:
        self._ref_count += 1

    def release(self) -> None:
        if self._ref_count > 0:
            self._ref_count -= 1
        if self._ref_count == 0:
            self._stop_worker()

    def ensure_started(self) -> None:
        try:
            if not self._audio_worker.is_running():
                self._audio_worker.start()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to start audio worker in shared engine", exc_info=True)

    def _stop_worker(self) -> None:
        try:
            self._audio_worker.stop()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to stop audio worker in shared engine", exc_info=True)

    def _schedule_compute_bars_task(self, samples: object) -> None:
        tm = self._thread_manager
        if tm is None:
            return

        self._compute_task_active = True
        
        # Capture smoothing state for the job (thread-safe copy)
        smoothed_copy = list(self._smoothed_bars)
        last_smooth_ts = self._last_smooth_ts
        smoothing_tau = self._smoothing_tau
        bar_count = self._bar_count

        def _job(local_samples=samples):
            """FFT + smoothing on COMPUTE pool - keeps UI thread free."""
            raw_bars = self._audio_worker.compute_bars_from_samples(local_samples)
            if not isinstance(raw_bars, list):
                return None
            
            # Apply smoothing here on COMPUTE thread
            now_ts = time.time()
            dt = max(0.0, now_ts - last_smooth_ts) if last_smooth_ts >= 0.0 else 0.0
            
            # CRITICAL: If dt is too large (e.g., after settings dialog),
            # reset smoothing state to avoid erratic behavior from huge alpha values.
            # A gap > 2 seconds indicates a pause/resume scenario.
            if dt > 2.0 or dt <= 0.0:
                return {'raw': raw_bars, 'smoothed': list(raw_bars), 'ts': now_ts, 'reset': True}
            
            base_tau = smoothing_tau
            tau_rise = base_tau * 0.35
            tau_decay = base_tau * 3.0
            alpha_rise = 1.0 - math.exp(-dt / tau_rise)
            alpha_decay = 1.0 - math.exp(-dt / tau_decay)
            alpha_rise = max(0.0, min(1.0, alpha_rise))
            alpha_decay = max(0.0, min(1.0, alpha_decay))
            
            smoothed = []
            for i in range(bar_count):
                cur = smoothed_copy[i] if i < len(smoothed_copy) else 0.0
                tgt = raw_bars[i] if i < len(raw_bars) else 0.0
                alpha = alpha_rise if tgt >= cur else alpha_decay
                nxt = cur + (tgt - cur) * alpha
                if abs(nxt) < 1e-3:
                    nxt = 0.0
                smoothed.append(nxt)
            
            return {'raw': raw_bars, 'smoothed': smoothed, 'ts': now_ts}

        def _on_result(result) -> None:
            try:
                self._compute_task_active = False
                success = getattr(result, "success", True)
                data = getattr(result, "result", None)
                if not success or data is None:
                    return
                raw_bars = data.get('raw')
                smoothed_bars = data.get('smoothed')
                ts = data.get('ts', time.time())
                if isinstance(raw_bars, list):
                    self._bars_result_buffer.publish(raw_bars)
                    self._latest_bars = raw_bars
                if isinstance(smoothed_bars, list):
                    self._smoothed_bars = smoothed_bars
                    self._last_smooth_ts = ts
                try:
                    self._last_audio_ts = time.time()
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            except Exception:
                logger.debug("[SPOTIFY_VIS] compute task callback failed", exc_info=True)

        try:
            tm.submit_compute_task(_job, callback=_on_result)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            self._compute_task_active = False

    def tick(self) -> Optional[List[float]]:
        tm = self._thread_manager

        now_ts = time.time()
        frame = self._audio_buffer.consume_latest()
        if frame is not None:
            samples = getattr(frame, "samples", None)
            if samples is not None:
                try:
                    self._last_audio_ts = now_ts
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                
                # CRITICAL: Gate FFT processing when Spotify is not playing
                # This prevents wasteful FFT calculations when music is paused/stopped
                if not self._is_spotify_playing:
                    # When not playing, ensure we show minimal 1-bar floor instead of full processing
                    if self._latest_bars is None or len(self._latest_bars) != self._bar_count:
                        self._latest_bars = [0.0] * self._bar_count
                    # Ensure at least 1 bar is visible (1-segment floor requirement)
                    if all(bar == 0.0 for bar in self._latest_bars):
                        self._latest_bars[0] = 0.08  # Minimal visible floor
                    return self._latest_bars
                
                if tm is not None:
                    if not self._compute_task_active:
                        self._schedule_compute_bars_task(samples)
                else:
                    bars_inline = self._audio_worker.compute_bars_from_samples(samples)
                    if isinstance(bars_inline, list):
                        try:
                            self._bars_result_buffer.publish(bars_inline)
                        except Exception as e:
                            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                        self._latest_bars = bars_inline

        # If we have not seen any audio for a short window, treat this as
        # silence and force the shared bars to zero so all widgets decay
        # together instead of holding stale peaks.
        try:
            last_ts = float(self._last_audio_ts)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            last_ts = 0.0
        if last_ts > 0.0:
            try:
                silence_timeout = 0.4
                if (now_ts - last_ts) >= silence_timeout:
                    if isinstance(self._latest_bars, list) and self._bar_count > 0:
                        if any(b > 0.0 for b in self._latest_bars):
                            self._latest_bars = [0.0] * self._bar_count
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

        return self._latest_bars
    
    def get_smoothed_bars(self) -> List[float]:
        """Get pre-smoothed bars for UI display.
        
        This returns bars that have already been smoothed on the COMPUTE pool,
        so the UI thread doesn't need to do any smoothing calculations.
        """
        return list(self._smoothed_bars)


# Import the singleton from the beat_engine module instead of duplicating it here
from widgets.spotify_visualizer.beat_engine import get_shared_spotify_beat_engine


class SpotifyVisualizerWidget(QWidget):
    """Thin bar visualizer card paired with the Spotify media widget.

    The widget draws a rounded-rect card that inherits Spotify/Media
    styling from DisplayWidget and renders a row of vertical bars whose
    heights are driven by FFT magnitudes published by
    SpotifyVisualizerAudioWorker.
    """

    def __init__(self, parent: Optional[QWidget] = None, bar_count: int = 32) -> None:
        super().__init__(parent)

        self._bar_count = max(1, int(bar_count))
        self._display_bars: List[float] = [0.0] * self._bar_count
        self._target_bars: List[float] = [0.0] * self._bar_count
        self._per_bar_energy: List[float] = [0.0] * self._bar_count
        self._visual_bars: List[float] = [0.0] * self._bar_count
        self._visual_smoothing_tau: float = 0.055
        self._last_visual_smooth_ts: float = 0.0
        # Base smoothing time constant in seconds; actual per-tick blend
        # factor is derived from this and the real dt between ticks so that
        # behaviour stays consistent even if tick rate changes. Slightly
        # reduced from earlier values to make bar attacks feel less "late"
        # without removing the pleasant decay tail.
        self._smoothing: float = 0.18

        self._thread_manager: Optional[ThreadManager] = None
        self._bars_timer = None
        self._shadow_config = None
        self._show_background: bool = True
        self._animation_manager = None
        self._anim_listener_id: Optional[int] = None

        # Card style (mirrors Spotify/Media widget)
        self._bg_color = QColor(16, 16, 16, 255)
        self._bg_opacity: float = 0.7
        self._card_border_color = QColor(255, 255, 255, 230)
        self._border_width: int = 2

        # Bar styling
        self._bar_fill_color = QColor(200, 200, 200, 230)
        self._bar_border_color = QColor(255, 255, 255, 255)
        self._bar_segments: int = 18
        self._ghosting_enabled: bool = True
        self._ghost_alpha: float = 0.4
        self._ghost_decay_rate: float = 0.4

        # Visualization mode (Spectrum, Waveform, Abstract)
        self._vis_mode: VisualizerMode = VisualizerMode.SPECTRUM

        # Behavioural gating
        self._spotify_playing: bool = False
        self._anchor_media: Optional[QWidget] = None
        self._has_seen_media: bool = False
        # Legacy Spotify gating state (still tracked for telemetry/UI toggles)
        self._last_media_state_ts: float = 0.0
        self._media_state_logged: bool = False

        # Shared beat engine (single audio worker per process). We keep
        # aliases for _audio_worker/_bars_buffer/_bars_result_buffer so
        # existing tests and diagnostics continue to function, but all
        # heavy work is centralised in the engine.
        self._engine: Optional[_SpotifyBeatEngine] = get_shared_spotify_beat_engine(self._bar_count)
        self._last_floor_config = (True, 2.1)
        self._last_sensitivity_config = (True, 1.0)
        try:
            engine = self._engine
            if engine is not None:
                # Canonical bar_count is driven by the shared engine.
                try:
                    engine_bar_count = int(getattr(engine, "_bar_count", self._bar_count))
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                    engine_bar_count = self._bar_count
                if engine_bar_count > 0 and engine_bar_count != self._bar_count:
                    self._bar_count = engine_bar_count
                    self._display_bars = [0.0] * self._bar_count
                    self._target_bars = [0.0] * self._bar_count
                    self._per_bar_energy = [0.0] * self._bar_count
                    self._visual_bars = [0.0] * self._bar_count
                # Test/diagnostic aliases – these reference shared state.
                self._bars_buffer = engine._audio_buffer  # type: ignore[attr-defined]
                self._audio_worker = engine._audio_worker  # type: ignore[attr-defined]
                self._bars_result_buffer = engine._bars_result_buffer  # type: ignore[attr-defined]
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to attach shared beat engine", exc_info=True)

        self._enabled: bool = False
        self._paint_debug_logged: bool = False

        # Lightweight PERF profiling state for widget activity so we can
        # correlate Spotify playing state with Transition/FPS behaviour.
        self._perf_tick_start_ts: Optional[float] = None
        self._perf_tick_last_ts: Optional[float] = None
        self._perf_tick_frame_count: int = 0
        self._perf_tick_min_dt: float = 0.0
        self._perf_tick_max_dt: float = 0.0

        self._perf_paint_start_ts: Optional[float] = None
        self._perf_paint_last_ts: Optional[float] = None
        self._perf_paint_frame_count: int = 0
        self._perf_paint_min_dt: float = 0.0
        self._perf_paint_max_dt: float = 0.0

        # Lightweight view of capture→bars latency derived from the shared
        # beat engine's last-audio timestamp. Logged alongside Tick/Paint
        # metrics but kept in a separate line so existing schemas remain
        # stable for tools.
        self._perf_audio_lag_last_ms: float = 0.0
        self._perf_audio_lag_min_ms: float = 0.0
        self._perf_audio_lag_max_ms: float = 0.0

        # Last time we emitted a PERF snapshot while running. This allows us
        # to log Spotify visualiser activity periodically even if the widget
        # is never explicitly stopped/cleaned up (for example, if the
        # screensaver exits abruptly), so logs still capture its effective
        # update/paint rate alongside compositor and animation metrics.
        self._perf_last_log_ts: Optional[float] = None
        self._dt_spike_threshold_ms: float = 42.0
        self._dt_spike_log_cooldown: float = 0.75
        self._last_tick_spike_log_ts: float = 0.0

        # Geometry cache for paintEvent to avoid per-frame recomputation of
        # bar/segment layout. Rebuilt on resize or when bar_count/segments
        # change.
        self._geom_cache_rect: Optional[QRect] = None
        self._geom_cache_bar_count: int = self._bar_count
        self._geom_cache_segments: int = self._bar_segments
        self._geom_bar_x: List[int] = []
        self._geom_seg_y: List[int] = []
        self._geom_bar_width: int = 0
        self._geom_seg_height: int = 0

        # Last time a visual update (GPU frame push or QWidget repaint)
        # was issued. Initialised to a negative sentinel so the first
        # tick always triggers an update and subsequent ticks are
        # throttled purely by the configured FPS caps.
        self._last_update_ts: float = -1.0
        self._last_smooth_ts: float = 0.0
        self._has_pushed_first_frame: bool = False
        # Base paint FPS caps for the visualiser; slightly higher than
        # before now that compositor/GL transitions are cheaper, while
        # still low enough that the visualiser cannot dominate the UI
        # event loop.
        self._base_max_fps: float = 90.0
        self._transition_max_fps: float = 60.0
        self._transition_hot_start_fps: float = 50.0
        self._transition_spinup_window: float = 2.0
        self._idle_fps_boost_delay: float = 5.0
        self._idle_max_fps: float = 100.0
        self._current_timer_interval_ms: int = 16
        self._last_gpu_fade_sent: float = -1.0
        self._last_gpu_geom: Optional[QRect] = None

        # When GPU overlay rendering is available, we disable the
        # widget's own bar drawing and instead push frames up to the
        # DisplayWidget, which owns a small QOpenGLWidget overlay.
        self._cpu_bars_enabled: bool = True
        # User-configurable switch controlling whether the legacy software
        # visualiser is allowed to draw bars when GPU rendering is
        # unavailable or disabled. Defaults to False so the GPU overlay
        # remains the primary path in OpenGL mode.
        self._software_visualizer_enabled: bool = False

        # Tick source coordination
        self._using_animation_ticks: bool = False

        self._setup_ui()

    def _replay_engine_config(self, engine: Optional[_SpotifyBeatEngine]) -> None:
        """Ensure the shared engine reflects the last applied widget config."""
        if engine is None:
            return
        try:
            floor_dyn, floor_value = self._last_floor_config
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            floor_dyn, floor_value = True, 2.1
        try:
            sens_rec, sens_value = self._last_sensitivity_config
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            sens_rec, sens_value = True, 1.0

        try:
            engine.set_floor_config(floor_dyn, floor_value)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to replay floor config", exc_info=True)
        try:
            engine.set_sensitivity_config(sens_rec, sens_value)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to replay sensitivity config", exc_info=True)

    # ------------------------------------------------------------------
    # Public configuration
    # ------------------------------------------------------------------

    def set_thread_manager(self, thread_manager: ThreadManager) -> None:
        self._thread_manager = thread_manager
        try:
            engine = get_shared_spotify_beat_engine(self._bar_count)
            self._engine = engine
            engine.set_thread_manager(thread_manager)
            self._replay_engine_config(engine)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to propagate ThreadManager to shared beat engine", exc_info=True)

    def set_process_supervisor(self, supervisor: Optional[ProcessSupervisor]) -> None:
        """Set the ProcessSupervisor for FFTWorker integration.
        
        When set and FFTWorker is running, FFT processing is offloaded to a
        separate process for better performance (avoids GIL contention).
        """
        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
            if engine is not None:
                engine.set_process_supervisor(supervisor)
                logger.debug("[SPOTIFY_VIS] ProcessSupervisor set on beat engine")
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to set ProcessSupervisor on beat engine", exc_info=True)
        if self._enabled:
            self._ensure_tick_source()

    def apply_floor_config(self, dynamic_enabled: bool, manual_floor: float) -> None:
        """Public hook for tests/UI to set floor config on the widget."""
        self._last_floor_config = (bool(dynamic_enabled), float(manual_floor))
        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            engine = None
        if engine is not None:
            try:
                engine.set_floor_config(dynamic_enabled, manual_floor)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to push floor config via apply_floor_config", exc_info=True)

    # Backwards-compat alias for legacy callers/tests
    def set_floor_config(self, dynamic_enabled: bool, manual_floor: float) -> None:
        self.apply_floor_config(dynamic_enabled, manual_floor)

    def apply_sensitivity_config(self, recommended: bool, sensitivity: float) -> None:
        """Public hook for tests/UI to set sensitivity config on the widget."""
        self._last_sensitivity_config = (bool(recommended), float(sensitivity))
        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            engine = None
        if engine is not None:
            try:
                engine.set_sensitivity_config(recommended, sensitivity)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to push sensitivity config via apply_sensitivity_config", exc_info=True)

    def set_sensitivity_config(self, recommended: bool, sensitivity: float) -> None:
        self.apply_sensitivity_config(recommended, sensitivity)

    def set_software_visualizer_enabled(self, enabled: bool) -> None:
        """Enable or disable the QWidget-based software visualiser path.

        When ``enabled`` is True, the widget is allowed to render bars via
        its own ``paintEvent`` when GPU rendering is unavailable (for
        example in software renderer mode). When False, the widget only
        exposes smoothed bar data to the GPU overlay and does not draw
        bars itself unless explicitly re-enabled.
        """

        try:
            self._software_visualizer_enabled = bool(enabled)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            self._software_visualizer_enabled = bool(enabled)

    def attach_to_animation_manager(self, animation_manager) -> None:
        # Detach from any previous manager first to avoid stacking listeners.
        if self._animation_manager is not None and self._anim_listener_id is not None:
            try:
                if hasattr(self._animation_manager, "remove_tick_listener"):
                    self._animation_manager.remove_tick_listener(self._anim_listener_id)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to remove previous AnimationManager listener", exc_info=True)

        self._animation_manager = animation_manager
        self._anim_listener_id = None

        # NOTE: We keep the dedicated _bars_timer running even when attached to
        # AnimationManager. The AnimationManager only ticks during active transitions,
        # so the dedicated timer ensures continuous visualizer updates between transitions.
        # The _on_tick method's FPS cap via _last_update_ts handles deduplication of
        # the actual GPU push, so double-ticking is not a performance issue.

        try:
            def _tick_listener(dt: float) -> None:
                if not self._enabled:
                    return
                self._on_tick()

            listener_id = animation_manager.add_tick_listener(_tick_listener)
            self._anim_listener_id = listener_id
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to attach to AnimationManager", exc_info=True)
        finally:
            self._ensure_tick_source()

    def detach_from_animation_manager(self) -> None:
        am = self._animation_manager
        listener_id = self._anim_listener_id
        if am is not None and listener_id is not None and hasattr(am, "remove_tick_listener"):
            try:
                am.remove_tick_listener(listener_id)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to detach from AnimationManager", exc_info=True)
        self._animation_manager = None
        self._anim_listener_id = None
        self._ensure_tick_source()

    def _ensure_tick_source(self) -> None:
        """Ensure the visualizer has a tick source for continuous updates.
        
        This method ensures the dedicated _bars_timer is running when the
        visualizer is enabled and no AnimationManager tick listener is active.
        The timer provides continuous 60Hz updates between transitions.
        """
        if not self._enabled:
            return
        
        # If we have an AnimationManager listener, we're covered during transitions
        # but still need the dedicated timer for between-transition updates
        if self._thread_manager is not None and self._bars_timer is None:
            try:
                self._bars_timer = self._thread_manager.schedule_recurring(16, self._on_tick)
                self._current_timer_interval_ms = 16
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to create tick source timer", exc_info=True)
                self._bars_timer = None

    def set_shadow_config(self, config) -> None:
        self._shadow_config = config

    def _update_card_style(self) -> None:
        if self._show_background:
            bg = QColor(self._bg_color)
            alpha = int(255 * max(0.0, min(1.0, self._bg_opacity)))
            bg.setAlpha(alpha)
            self.setStyleSheet(
                f"""
                QWidget {{
                    background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {bg.alpha()});
                    border: {self._border_width}px solid rgba({self._card_border_color.red()}, {self._card_border_color.green()}, {self._card_border_color.blue()}, {self._card_border_color.alpha()});
                    border-radius: 8px;
                }}
                """
            )
        else:
            self.setStyleSheet(
                """
                QWidget {
                    background-color: transparent;
                    border: 0px solid transparent;
                    border-radius: 8px;
                }
                """
            )

    def set_bar_style(self, *, bg_color: QColor, bg_opacity: float, border_color: QColor, border_width: int = 2,
                      show_background: bool = True) -> None:
        self._bg_color = QColor(bg_color)
        self._bg_opacity = max(0.0, min(1.0, float(bg_opacity)))
        self._card_border_color = QColor(border_color)
        self._border_width = max(0, int(border_width))
        self._show_background = bool(show_background)
        self._update_card_style()
        self.update()

    def set_bar_colors(self, fill_color: QColor, border_color: QColor) -> None:
        # Fill colour is applied per-bar; border colour controls the bar
        # outline tint. Card border remains driven by set_bar_style.
        self._bar_fill_color = QColor(fill_color)
        self._bar_border_color = QColor(border_color)
        self.update()

    def set_ghost_config(self, enabled: bool, alpha: float, decay: float) -> None:
        """Configure ghost trailing behaviour for the GPU bar overlay.

        ``enabled`` toggles whether ghost bars are drawn at all. ``alpha``
        controls their base opacity relative to the main bar border colour,
        and ``decay`` feeds into the overlay's peak-envelope decay so that
        higher values shorten the trail while lower values keep it visible
        for longer.
        """

        try:
            self._ghosting_enabled = bool(enabled)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            self._ghosting_enabled = True

        try:
            ga = float(alpha)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            ga = 0.4
        if ga < 0.0:
            ga = 0.0
        if ga > 1.0:
            ga = 1.0
        self._ghost_alpha = ga

        try:
            gd = float(decay)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            gd = 0.4
        if gd < 0.0:
            gd = 0.0
        self._ghost_decay_rate = gd

    def set_anchor_media_widget(self, widget: QWidget) -> None:
        self._anchor_media = widget

    def handle_media_update(self, payload: dict) -> None:
        """Receive Spotify media state from MediaWidget.

        Expects payload from MediaWidget.media_updated with a ``state``
        field of "playing"/"paused"/"stopped". When not playing, the
        visualizer decays to idle even if other apps are producing audio.
        """

        try:
            state = str(payload.get("state", "")).lower()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            state = ""
        prev = self._spotify_playing
        self._spotify_playing = state == "playing"
        self._last_media_state_ts = time.time()
        self._fallback_logged = False

        # CRITICAL: Pass playback state to beat engine for FFT processing gating
        try:
            if self._engine is not None:
                self._engine.set_playback_state(self._spotify_playing)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to set beat engine playback state", exc_info=True)

        if logger.isEnabledFor(logging.INFO):
            try:
                track = payload.get("track_name") or payload.get("title") or ""
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                track = ""
            logger.info(
                "[SPOTIFY_VIS] media_update state=%s -> playing=%s (prev=%s) track=%s",
                state or "<unset>",
                self._spotify_playing,
                prev,
                track,
            )

        first_media = not self._has_seen_media
        if first_media:
            # Track that we have seen at least one Spotify media state update
            # so later calls can focus purely on bar gating.
            self._has_seen_media = True

        if is_verbose_logging():
            try:
                logger.debug(
                    "[SPOTIFY_VIS] handle_media_update: state=%r (prev_playing=%s, now_playing=%s)",
                    state,
                    prev,
                    self._spotify_playing,
                )
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        
        self.sync_visibility_with_anchor()

    def sync_visibility_with_anchor(self) -> None:
        """Show/hide based on anchor media widget visibility."""
        anchor = self._anchor_media
        if anchor is not None:
            try:
                anchor_visible = anchor.isVisible()
                if anchor_visible and not self.isVisible():
                    # Media widget became visible - show visualizer
                    self._start_widget_fade_in(1500)
                elif not anchor_visible and self.isVisible():
                    # Media widget hidden - hide visualizer and clear GL overlay
                    self.hide()
                    self._clear_gl_overlay()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
    
    def _clear_gl_overlay(self) -> None:
        """Clear the GL bars overlay when visualizer hides."""
        parent = self.parent()
        if parent is not None:
            # Clear the SpotifyBarsGLOverlay by pushing an invisible state
            overlay = getattr(parent, "_spotify_bars_overlay", None)
            if overlay is not None and hasattr(overlay, "set_state"):
                try:
                    from PySide6.QtCore import QRect
                    from PySide6.QtGui import QColor
                    overlay.set_state(
                        QRect(0, 0, 0, 0),
                        [],
                        0,
                        0,
                        QColor(0, 0, 0, 0),
                        QColor(0, 0, 0, 0),
                        0.0,
                        False,
                        visible=False,
                    )
                    # Force overlay to repaint to clear any artifacts
                    if hasattr(overlay, 'update'):
                        overlay.update()
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            
            # Request parent repaint to ensure artifacts are cleared
            if hasattr(parent, 'update'):
                parent.update()
        
    def _is_media_state_stale(self) -> bool:
        """Return True if Spotify state has not updated within fallback timeout."""
        last = getattr(self, "_last_media_state_ts", 0.0)
        if last <= 0.0:
            return True
        try:
            timeout = float(self._media_fallback_timeout)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            timeout = 8.0
        return (time.time() - last) >= max(1.0, timeout)

    def _has_audio_activity(
        self,
        bars: List[float],
        raw_bars: Optional[List[float]] = None,
    ) -> bool:
        """Heuristic to detect meaningful audio energy on the loopback feed."""
        candidates = raw_bars if isinstance(raw_bars, list) and raw_bars else bars
        if not isinstance(candidates, list) or not candidates:
            return False
        threshold = 0.01
        try:
            return max(candidates) >= threshold
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            return any((b or 0.0) >= threshold for b in candidates)

    def _is_fallback_forced(self) -> bool:
        return time.time() <= getattr(self, "_fallback_forced_until", 0.0)

    def _update_fallback_force_state(self, audio_active: bool) -> None:
        now = time.time()
        if self._spotify_playing:
            self._fallback_mismatch_start = 0.0
            self._fallback_forced_until = 0.0
            return

        if audio_active:
            if self._fallback_mismatch_start <= 0.0:
                self._fallback_mismatch_start = now
            elif (now - self._fallback_mismatch_start) >= 3.0:
                if not self._is_fallback_forced():
                    self._fallback_forced_until = now + 20.0
                    logger.info(
                        "[SPOTIFY_VIS] Forcing audio fallback for 20s (bridge reports paused but audio active)",
                    )
        else:
            self._fallback_mismatch_start = 0.0

    # ------------------------------------------------------------------
    # Lifecycle Implementation Hooks
    # ------------------------------------------------------------------
    
    def _initialize_impl(self) -> None:
        """Initialize visualizer resources (lifecycle hook)."""
        logger.debug("[LIFECYCLE] SpotifyVisualizerWidget initialized")
    
    def _activate_impl(self) -> None:
        """Activate visualizer - start audio capture (lifecycle hook)."""
        # Start audio capture via the shared beat engine
        try:
            engine = get_shared_spotify_beat_engine(self._bar_count)
            self._engine = engine
            if self._thread_manager is not None:
                engine.set_thread_manager(self._thread_manager)
            engine.acquire()
            self._replay_engine_config(engine)
            engine.ensure_started()
        except Exception:
            logger.debug("[LIFECYCLE] Failed to start shared beat engine", exc_info=True)
        
        # Start dedicated timer for continuous visualizer updates
        if self._thread_manager is not None and self._bars_timer is None:
            try:
                self._bars_timer = self._thread_manager.schedule_recurring(16, self._on_tick)
                self._current_timer_interval_ms = 16
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                self._bars_timer = None
        
        logger.debug("[LIFECYCLE] SpotifyVisualizerWidget activated")
    
    def _deactivate_impl(self) -> None:
        """Deactivate visualizer - stop audio capture (lifecycle hook)."""
        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            engine = None
        if engine is not None:
            try:
                engine.release()
            except Exception:
                logger.debug("[LIFECYCLE] Failed to release shared beat engine", exc_info=True)
        
        try:
            self.detach_from_animation_manager()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        
        if self._bars_timer is not None:
            try:
                self._bars_timer.stop()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            self._bars_timer = None
        self._using_animation_ticks = False
        
        self._log_perf_snapshot(reset=True)
        logger.debug("[LIFECYCLE] SpotifyVisualizerWidget deactivated")
    
    def _cleanup_impl(self) -> None:
        """Clean up visualizer resources (lifecycle hook)."""
        self._deactivate_impl()
        self._engine = None
        logger.debug("[LIFECYCLE] SpotifyVisualizerWidget cleaned up")

    # ------------------------------------------------------------------
    # Legacy Lifecycle Methods (for backward compatibility)
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._enabled:
            return
        self._enabled = True

        try:
            self.hide()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

        # Start audio capture via the shared beat engine so the buffer can
        # begin filling. Each widget acquires a reference so the engine can
        # stop cleanly once the last visualiser stops.
        try:
            engine = get_shared_spotify_beat_engine(self._bar_count)
            self._engine = engine
            if self._thread_manager is not None:
                engine.set_thread_manager(self._thread_manager)
            engine.acquire()
            self._replay_engine_config(engine)
            
            # CRITICAL: Initialize beat engine with current playback state
            # This ensures FFT gating is active from startup
            engine.set_playback_state(self._spotify_playing)
            
            engine.ensure_started()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to start shared beat engine", exc_info=True)

        # Always start the dedicated timer for continuous visualizer updates.
        # AnimationManager only ticks during active transitions, so we need
        # the dedicated timer to keep the visualizer running between transitions.
        # The _on_tick method handles deduplication via _last_update_ts.
        if self._thread_manager is not None and self._bars_timer is None:
            try:
                self._bars_timer = self._thread_manager.schedule_recurring(16, self._on_tick)
                self._current_timer_interval_ms = 16
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                self._bars_timer = None
        elif self._animation_manager is not None and self._anim_listener_id is not None:
            self._using_animation_ticks = True

        # Coordinate the visualiser card fade-in with the primary overlay
        # group so it joins the main wave on this display. Only show if the
        # anchor media widget is visible (Spotify is active).
        parent = self.parent()

        def _starter() -> None:
            # Guard against widget being deleted before deferred callback runs
            if not Shiboken.isValid(self):
                return
            # Only show if anchor media widget is visible (Spotify is playing)
            anchor = self._anchor_media
            if anchor is not None:
                try:
                    if not anchor.isVisible():
                        # Media widget not visible - don't show visualizer yet
                        return
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            
            try:
                self._start_widget_fade_in(1500)
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                try:
                    self.show()
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

        if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
            try:
                parent.request_overlay_fade_sync("spotify_visualizer", _starter)
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                _starter()
        else:
            _starter()

    def stop(self) -> None:
        if not self._enabled:
            return
        self._enabled = False

        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            engine = None
        if engine is not None:
            try:
                engine.release()
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to release shared beat engine", exc_info=True)

        try:
            self.detach_from_animation_manager()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to detach from AnimationManager on stop", exc_info=True)

        try:
            if self._bars_timer is not None:
                self._bars_timer.stop()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        self._bars_timer = None
        self._using_animation_ticks = False

        # Emit a concise PERF summary for this widget's activity during the
        # last enabled period so we can see its effective update/paint rate
        # and dt jitter alongside compositor and animation metrics.
        self._log_perf_snapshot(reset=True)

        try:
            self.hide()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

    def cleanup(self) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # UI and painting
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        # Configure attributes to prevent flicker with GL compositor
        configure_overlay_widget_attributes(self)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        # Slightly taller default so bars and card border have breathing
        # room and match the visual weight of other widgets.
        self.setMinimumHeight(88)
        self._update_card_style()

    def _start_widget_fade_in(self, duration_ms: int = 1500) -> None:
        if duration_ms <= 0:
            try:
                self.show()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            try:
                ShadowFadeProfile.attach_shadow(
                    self,
                    self._shadow_config,
                    has_background_frame=self._show_background,
                )
            except Exception:
                logger.debug(
                    "[SPOTIFY_VIS] Failed to attach shadow in no-fade path",
                    exc_info=True,
                )
            return

        try:
            ShadowFadeProfile.start_fade_in(
                self,
                self._shadow_config,
                has_background_frame=self._show_background,
            )
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] _start_widget_fade_in fallback path triggered",
                exc_info=True,
            )
            try:
                self.show()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            if self._shadow_config is not None:
                try:
                    apply_widget_shadow(
                        self,
                        self._shadow_config,
                        has_background_frame=self._show_background,
                    )
                except Exception:
                    logger.debug(
                        "[SPOTIFY_VIS] Failed to apply widget shadow in fallback path",
                        exc_info=True,
                    )

    def _get_gpu_fade_factor(self, now_ts: float) -> float:
        """Return fade factor for GPU bars based on ShadowFadeProfile.

        We prefer the shared ShadowFadeProfile progress when available so that
        the GL overlay tracks the exact same curve. When no progress is
        present we fall back to 1.0 while the widget is visible.
        """

        try:
            prog = getattr(self, "_shadowfade_progress", None)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            prog = None

        if isinstance(prog, (float, int)):
            p = float(prog)
            if p <= 0.0:
                return 0.0
            if p >= 1.0:
                return 1.0

            # Clamp first, then apply a stronger delay so bars fade in well
            # after the card/shadow begin fading. This keeps practical sync
            # with ShadowFadeProfile while ensuring the bars clearly read as a
            # second wave rather than appearing fully formed too early.
            p = max(0.0, min(1.0, p))
            delay = 0.65
            if p <= delay:
                return 0.0
            t = (p - delay) / (1.0 - delay)
            # Slower cubic ease-in so the bar opacity builds gradually and
            # avoids a sudden pop once the delay has elapsed.
            t = t * t * t
            return max(0.0, min(1.0, t))

        # Fallback: when ShadowFadeProfile progress is unavailable, check if
        # the fade animation has completed (progress reached 1.0 at some point).
        # We track this via _shadowfade_completed flag to avoid returning 1.0
        # prematurely at startup before the fade animation begins.
        try:
            completed = getattr(self, "_shadowfade_completed", False)
            if completed and self.isVisible():
                return 1.0
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        return 0.0

    def _rebuild_geometry_cache(self, rect: QRect) -> None:
        """Recompute cached bar/segment layout for the current geometry."""

        count = self._bar_count
        segments = max(1, getattr(self, "_bar_segments", 16))
        if rect.width() <= 0 or rect.height() <= 0 or count <= 0:
            self._geom_cache_rect = QRect()
            self._geom_cache_bar_count = count
            self._geom_cache_segments = segments
            self._geom_bar_x = []
            self._geom_seg_y = []
            self._geom_bar_width = 0
            self._geom_seg_height = 0
            return

        margin_x = 8
        margin_y = 6
        inner = rect.adjusted(margin_x, margin_y, -margin_x, -margin_y)
        if inner.width() <= 0 or inner.height() <= 0:
            self._geom_cache_rect = inner
            self._geom_cache_bar_count = count
            self._geom_cache_segments = segments
            self._geom_bar_x = []
            self._geom_seg_y = []
            self._geom_bar_width = 0
            self._geom_seg_height = 0
            return

        gap = 2
        total_gap = gap * (count - 1) if count > 1 else 0
        bars_inset = 5
        bar_region_width = inner.width() - (bars_inset * 2)
        if bar_region_width <= 0:
            self._geom_cache_rect = inner
            self._geom_cache_bar_count = count
            self._geom_cache_segments = segments
            self._geom_bar_x = []
            self._geom_seg_y = []
            self._geom_bar_width = 0
            self._geom_seg_height = 0
            return

        usable_width = max(0, bar_region_width - total_gap)
        bar_width = max(1, int(usable_width / max(1, count)))
        span = bar_width * count + total_gap
        remaining = max(0, bar_region_width - span)
        # Center the bar field horizontally within the usable region so rounding
        # differences never bias to the right.
        x0 = inner.left() + bars_inset + (remaining // 2)
        bar_x = [x0 + i * (bar_width + gap) for i in range(count)]

        seg_gap = 1
        total_seg_gap = seg_gap * max(0, segments - 1)
        seg_height = max(1, int((inner.height() - total_seg_gap) / max(1, segments)))
        base_bottom = inner.bottom()
        seg_y = [base_bottom - s * (seg_height + seg_gap) - seg_height + 1 for s in range(segments)]

        self._geom_cache_rect = inner
        self._geom_cache_bar_count = count
        self._geom_cache_segments = segments
        self._geom_bar_x = bar_x
        self._geom_seg_y = seg_y
        self._geom_bar_width = bar_width
        self._geom_seg_height = seg_height

    def _apply_visual_smoothing(self, target_bars: List[float], now_ts: float) -> bool:
        """Lightweight post-bar smoothing to calm jitter without hurting response."""
        changed = False
        visual = self._visual_bars
        count = self._bar_count
        last_ts = self._last_visual_smooth_ts

        if last_ts <= 0.0 or (now_ts - last_ts) > 0.4:
            for i in range(count):
                val = target_bars[i] if i < len(target_bars) else 0.0
                if i < len(visual):
                    if abs(visual[i] - val) > 1e-4:
                        changed = True
                    visual[i] = val
                else:
                    visual.append(val)
                    changed = True
            self._visual_bars = visual[:count]
            self._last_visual_smooth_ts = now_ts
            return changed

        dt = max(1e-4, now_ts - last_ts)
        tau_rise = self._visual_smoothing_tau
        tau_decay = tau_rise * 2.6
        alpha_rise = 1.0 - math.exp(-dt / tau_rise)
        alpha_decay = 1.0 - math.exp(-dt / tau_decay)
        alpha_rise = max(0.0, min(1.0, alpha_rise))
        alpha_decay = max(0.0, min(1.0, alpha_decay))

        for i in range(count):
            cur = visual[i] if i < len(visual) else 0.0
            tgt = target_bars[i] if i < len(target_bars) else 0.0
            alpha = alpha_rise if tgt >= cur else alpha_decay
            nxt = cur + (tgt - cur) * alpha
            if abs(nxt) < 1e-4:
                nxt = 0.0
            if abs(nxt - cur) > 1e-4:
                changed = True
            if i < len(visual):
                visual[i] = nxt
            else:
                visual.append(nxt)

        if len(visual) > count:
            del visual[count:]

        self._visual_bars = visual
        self._last_visual_smooth_ts = now_ts
        return changed

    def _get_transition_context(self, parent: Optional[QWidget]) -> Dict[str, Any]:
        """Return lightweight transition metrics from the parent DisplayWidget."""
        ctx: Dict[str, Any] = {
            "running": False,
            "name": None,
            "elapsed": None,
            "first_run": False,
            "idle_age": None,
        }
        if parent is None:
            return ctx
        snapshot = None
        if hasattr(parent, "get_transition_snapshot"):
            try:
                snapshot = parent.get_transition_snapshot()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                snapshot = None
        if isinstance(snapshot, dict):
            ctx.update(snapshot)
        elif hasattr(parent, "has_running_transition") and parent.has_running_transition():
            ctx["running"] = True
            ctx["name"] = None
            ctx["elapsed"] = None
        return ctx

    def _resolve_max_fps(self, transition_ctx: Dict[str, Any]) -> float:
        """Determine the FPS cap based on transition activity."""
        max_fps = self._base_max_fps
        if transition_ctx.get("running"):
            elapsed = float(transition_ctx.get("elapsed") or 0.0)
            if elapsed <= self._transition_spinup_window:
                max_fps = self._transition_hot_start_fps
            else:
                max_fps = self._transition_max_fps
        else:
            idle_age = transition_ctx.get("idle_age")
            if idle_age is not None and idle_age >= self._idle_fps_boost_delay:
                max_fps = min(self._idle_max_fps, self._base_max_fps + 10.0)
        return max(15.0, float(max_fps))

    def _update_timer_interval(self, max_fps: float) -> None:
        """Retune the ThreadManager recurring timer interval if needed."""
        interval_ms = max(4, int(round(1000.0 / max_fps)))
        if interval_ms == self._current_timer_interval_ms:
            return
        self._current_timer_interval_ms = interval_ms
        # Add a tiny jitter so we don't align perfectly with compositor vsync.
        jitter = random.randint(0, 2) if interval_ms >= 8 else 0
        new_interval = interval_ms + jitter
        timer = self._bars_timer
        if timer is not None:
            try:
                timer.setInterval(new_interval)
                self._current_timer_interval_ms = new_interval
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
    
    def _pause_timer_during_transition(self, is_transition_active: bool) -> None:
        """Pause dedicated timer during transitions to avoid contention.
        
        PERFORMANCE FIX: When AnimationManager is active during transitions,
        it provides tick callbacks. Running BOTH the dedicated timer AND
        AnimationManager causes timer contention and 50-100ms dt spikes.
        
        Pause the dedicated timer during transitions, resume when idle.
        """
        timer = self._bars_timer
        if timer is None:
            return
        
        try:
            if is_transition_active and self._using_animation_ticks:
                # Transition active with AnimationManager - pause dedicated timer
                if timer.isActive():
                    timer.stop()
            else:
                # No transition or no AnimationManager - ensure timer is running
                if not timer.isActive() and self._enabled:
                    timer.start()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

    def _log_tick_spike(self, dt: float, transition_ctx: Dict[str, Any]) -> None:
        """Log dt spikes with surrounding transition context."""
        now = time.time()
        if (now - self._last_tick_spike_log_ts) < self._dt_spike_log_cooldown:
            return
        self._last_tick_spike_log_ts = now
        running = transition_ctx.get("running")
        name = transition_ctx.get("name")
        elapsed = transition_ctx.get("elapsed")
        idle_age = transition_ctx.get("idle_age")
        logger.warning(
            "[PERF] [SPOTIFY_VIS] Tick dt spike %.2fms (running=%s name=%s elapsed=%s idle_age=%s)",
            dt * 1000.0,
            running,
            name or "<none>",
            f"{elapsed:.2f}" if isinstance(elapsed, (int, float)) else "<n/a>",
            f"{idle_age:.2f}" if isinstance(idle_age, (int, float)) else "<n/a>",
        )

    def _on_tick(self) -> None:
        """Periodic UI tick - PERFORMANCE OPTIMIZED.

        Consumes the latest bar frame from the TripleBuffer and smoothly
        interpolates towards it for visual stability.
        
        FPS CAP: This method is called by both _bars_timer (60Hz) and
        AnimationManager tick listener (60-165Hz). We apply the FPS cap
        at the START to avoid doing any work when rate-limited.
        """
        _tick_entry_ts = time.time()
        
        # PERFORMANCE: Fast validity check without nested try/except
        if not Shiboken.isValid(self):
            if self._bars_timer is not None:
                self._bars_timer.stop()
                self._bars_timer = None
            self._enabled = False
            return

        if not self._enabled:
            return

        now_ts = time.time()
        parent = self.parent()
        transition_ctx = self._get_transition_context(parent)
        is_transition_active = transition_ctx.get("running", False)
        
        # PERFORMANCE: Pause dedicated timer during transitions when AnimationManager is active
        # This prevents timer contention that causes 50-100ms dt spikes
        self._pause_timer_during_transition(is_transition_active)
        
        max_fps = self._resolve_max_fps(transition_ctx)
        self._update_timer_interval(max_fps)

        min_dt = 1.0 / max_fps if max_fps > 0.0 else 0.0
        last = self._last_update_ts
        dt_since_last = 0.0
        if last >= 0.0:
            dt_since_last = now_ts - last
        if last >= 0.0 and dt_since_last < min_dt:
            # Rate limited - skip this tick entirely
            return
        self._last_update_ts = now_ts
        if dt_since_last * 1000.0 >= self._dt_spike_threshold_ms:
            self._log_tick_spike(dt_since_last, transition_ctx)

        # PERFORMANCE: Inline PERF metrics with gap filtering
        if is_perf_metrics_enabled():
            if self._perf_tick_last_ts is not None:
                dt = now_ts - self._perf_tick_last_ts
                # Skip metrics for gaps >100ms (startup, widget paused/hidden).
                # Reset measurement window to avoid polluting duration/avg_fps
                # with startup spikes that aren't representative of runtime perf.
                if dt > 0.1:
                    self._perf_tick_start_ts = now_ts
                    self._perf_tick_min_dt = 0.0
                    self._perf_tick_max_dt = 0.0
                    self._perf_tick_frame_count = 0
                elif dt > 0.0:
                    if self._perf_tick_min_dt == 0.0 or dt < self._perf_tick_min_dt:
                        self._perf_tick_min_dt = dt
                    if dt > self._perf_tick_max_dt:
                        self._perf_tick_max_dt = dt
                    self._perf_tick_frame_count += 1
            else:
                self._perf_tick_start_ts = now_ts
            self._perf_tick_last_ts = now_ts

            # Periodic PERF snapshot
            if self._perf_last_log_ts is None or (now_ts - self._perf_last_log_ts) >= 5.0:
                self._log_perf_snapshot(reset=False)
                self._perf_last_log_ts = now_ts

        # PERFORMANCE: Get pre-smoothed bars from engine
        # Smoothing is now done on COMPUTE pool, not UI thread
        engine = self._engine
        if engine is None:
            engine = get_shared_spotify_beat_engine(self._bar_count)
            self._engine = engine
            # Sync smoothing settings to engine
            engine.set_smoothing(self._smoothing)
        
        changed = False
        if engine is not None:
            # Trigger engine tick (schedules FFT + smoothing on COMPUTE pool)
            _engine_tick_start = time.time()
            engine.tick()
            _engine_tick_elapsed = (time.time() - _engine_tick_start) * 1000.0
            if _engine_tick_elapsed > 20.0 and is_perf_metrics_enabled():
                logger.warning("[PERF] [SPOTIFY_VIS] Slow engine.tick(): %.2fms", _engine_tick_elapsed)
            
            # Track audio lag for PERF logs
            if is_perf_metrics_enabled():
                last_audio_ts = getattr(engine, "_last_audio_ts", 0.0)
                if last_audio_ts > 0.0:
                    lag_ms = (now_ts - last_audio_ts) * 1000.0
                    self._perf_audio_lag_last_ms = lag_ms
                    if self._perf_audio_lag_min_ms == 0.0 or lag_ms < self._perf_audio_lag_min_ms:
                        self._perf_audio_lag_min_ms = lag_ms
                    if lag_ms > self._perf_audio_lag_max_ms:
                        self._perf_audio_lag_max_ms = lag_ms
            
            # Get pre-smoothed bars (no computation on UI thread!)
            # The engine handles decay naturally via exponential smoothing -
            # when audio stops, raw bars go to zero and smoothed bars decay.
            smoothed = engine.get_smoothed_bars()

            # Always drive the bars from audio to avoid Spotify bridge flakiness.
            self._fallback_logged = False

            # Debug constant-bar mode
            if _DEBUG_CONST_BARS > 0.0:
                const_val = max(0.0, min(1.0, _DEBUG_CONST_BARS))
                smoothed = [const_val] * self._bar_count
            
            # Check if bars changed
            bar_count = self._bar_count
            display_bars = self._display_bars
            any_nonzero = False
            for i in range(bar_count):
                new_val = smoothed[i] if i < len(smoothed) else 0.0
                old_val = display_bars[i] if i < len(display_bars) else 0.0
                if abs(new_val - old_val) > 1e-4:
                    changed = True
                if new_val > 0.0:
                    any_nonzero = True
                display_bars[i] = new_val
            
            # Apply visual smoothing (UI/local) for calmer motion
            if self._apply_visual_smoothing(display_bars, now_ts):
                changed = True
            
            # Force update during decay (when bars are non-zero but Spotify stopped)
            if any_nonzero and not self._spotify_playing:
                changed = True

        # Always push at least one frame so the visualiser baseline is
        # visible as soon as the widget fades in, even before audio arrives.
        first_frame = not self._has_pushed_first_frame

        used_gpu = False
        need_card_update = False
        fade_changed = False
        fade = 1.0
        # When DisplayWidget exposes a GPU overlay path, prefer
        # that and disable CPU bar drawing once it succeeds.
        if parent is not None and hasattr(parent, "push_spotify_visualizer_frame"):
            try:
                current_geom = self.geometry()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                current_geom = None
            last_geom = self._last_gpu_geom
            geom_changed = last_geom is None or (current_geom is not None and current_geom != last_geom)

            fade = self._get_gpu_fade_factor(now_ts)
            prev_fade = self._last_gpu_fade_sent
            self._last_gpu_fade_sent = fade
            if prev_fade < 0.0 or abs(fade - prev_fade) >= 0.01:
                fade_changed = True
                need_card_update = True

            should_push = changed or fade_changed or first_frame or geom_changed
            if should_push:
                _gpu_push_start = time.time()
                # Only spectrum mode is supported
                mode_str = 'spectrum'
                
                used_gpu = parent.push_spotify_visualizer_frame(
                    bars=list(self._display_bars),
                    bar_count=self._bar_count,
                    segments=self._bar_segments,
                    fill_color=self._bar_fill_color,
                    border_color=self._bar_border_color,
                    fade=fade,
                    playing=self._spotify_playing,
                    ghosting_enabled=self._ghosting_enabled,
                    ghost_alpha=self._ghost_alpha,
                    ghost_decay=self._ghost_decay_rate,
                    vis_mode=mode_str,
                )
                _gpu_push_elapsed = (time.time() - _gpu_push_start) * 1000.0
                if _gpu_push_elapsed > 20.0 and is_perf_metrics_enabled():
                    logger.warning("[PERF] [SPOTIFY_VIS] Slow GPU push: %.2fms", _gpu_push_elapsed)

            if used_gpu:
                self._has_pushed_first_frame = True
                self._cpu_bars_enabled = False
                try:
                    if current_geom is None:
                        current_geom = self.geometry()
                    self._last_gpu_geom = QRect(current_geom)
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
                    self._last_gpu_geom = None
                # Card/background/shadow still repaint via stylesheet
                # Only request QWidget repaint when fade changes
                if need_card_update:
                    self.update()
            else:
                # Fallback: when there is no DisplayWidget/GPU bridge
                has_gpu_parent = parent is not None and hasattr(parent, "push_spotify_visualizer_frame")
                if not has_gpu_parent or self._software_visualizer_enabled:
                    self._cpu_bars_enabled = True
                    self.update()
                    self._has_pushed_first_frame = True

        # PERF: Log slow ticks to identify blocking operations
        _tick_elapsed = (time.time() - _tick_entry_ts) * 1000.0
        if _tick_elapsed > 50.0 and is_perf_metrics_enabled():
            logger.warning("[PERF] [SPOTIFY_VIS] Slow _on_tick: %.2fms", _tick_elapsed)

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        super().paintEvent(event)

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

        rect = self.rect()
        if is_verbose_logging() and not getattr(self, "_paint_debug_logged", False):
            try:
                anchor = self._anchor_media
                anchor_geom_ok = bool(anchor and anchor.width() > 0 and anchor.height() > 0)
                logger.debug(
                    "[SPOTIFY_VIS] paintEvent: geom=(%s,%s,%s,%s) rect=(%s,%s,%s,%s) enabled=%s visible=%s spotify_playing=%s show_bg=%s anchor_geom_ok=%s",
                    self.x(),
                    self.y(),
                    self.width(),
                    self.height(),
                    rect.x(),
                    rect.y(),
                    rect.width(),
                    rect.height(),
                    self._enabled,
                    self.isVisible(),
                    self._spotify_playing,
                    self._show_background,
                    anchor_geom_ok,
                )
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            try:
                self._paint_debug_logged = True
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        if rect.width() <= 0 or rect.height() <= 0:
            painter.end()
            return

        # When GPU overlay rendering is active for this widget instance, the
        # card/fade/shadow are still drawn via stylesheets and
        # ShadowFadeProfile, but the bar geometry itself is rendered by the
        # GL overlay. In that mode we skip the CPU bar drawing entirely.
        if not getattr(self, "_cpu_bars_enabled", True):
            painter.end()
            return

        if is_perf_metrics_enabled():
            try:
                now = time.time()
                if self._perf_paint_last_ts is not None:
                    dt = now - self._perf_paint_last_ts
                    # Skip metrics for gaps >1s (widget was likely occluded during GL transition).
                    # Also reset the measurement window to avoid polluting duration/avg_fps.
                    if dt > 1.0:
                        # Large gap detected - reset measurement window
                        self._perf_paint_start_ts = now
                        self._perf_paint_min_dt = 0.0
                        self._perf_paint_max_dt = 0.0
                        self._perf_paint_frame_count = 0
                    elif dt > 0.0:
                        # Normal frame - record metrics
                        if self._perf_paint_min_dt == 0.0 or dt < self._perf_paint_min_dt:
                            self._perf_paint_min_dt = dt
                        if dt > self._perf_paint_max_dt:
                            self._perf_paint_max_dt = dt
                        self._perf_paint_frame_count += 1
                else:
                    # First paint event
                    self._perf_paint_start_ts = now
                self._perf_paint_last_ts = now
            except Exception:
                logger.debug("[SPOTIFY_VIS] Paint PERF accounting failed", exc_info=True)

        # Note: paintEvent itself does not trigger PERF snapshots; these are
        # driven from the tick path so that tick/paint metrics share a common
        # time window and appear as a paired summary in logs.

        with profile("SPOTIFY_VIS_PAINT", threshold_ms=5.0, log_level="DEBUG"):
            # Card background is handled by the stylesheet; painting focuses on
            # the bar geometry only. Use a cached layout to avoid recomputing
            # per-frame integer geometry.

            segments = max(1, getattr(self, "_bar_segments", 16))
            if (
                self._geom_cache_rect is None
                or self._geom_cache_rect.width() != rect.width()
                or self._geom_cache_rect.height() != rect.height()
                or self._geom_cache_bar_count != self._bar_count
                or self._geom_cache_segments != segments
            ):
                self._rebuild_geometry_cache(rect)

            inner = self._geom_cache_rect
            bar_x = self._geom_bar_x
            seg_y = self._geom_seg_y
            bar_width = self._geom_bar_width
            seg_height = self._geom_seg_height
            if (
                inner is None
                or inner.width() <= 0
                or inner.height() <= 0
                or not bar_x
                or not seg_y
                or bar_width <= 0
                or seg_height <= 0
            ):
                painter.end()
                return

            count = self._bar_count
            count = min(count, len(bar_x))

            fill = QColor(self._bar_fill_color)
            border = QColor(self._bar_border_color)
            max_segments = min(segments, len(seg_y))

            painter.setBrush(fill)
            painter.setPen(border)

            # SPECTRUM mode - classic bar visualization
            for i in range(count):
                    x = bar_x[i]
                    value = max(0.0, min(1.0, self._display_bars[i]))
                    if value <= 0.0:
                        continue
                    boosted = value * 1.2
                    if boosted > 1.0:
                        boosted = 1.0
                    active = int(round(boosted * segments))
                    if active <= 0:
                        if self._spotify_playing and value > 0.0:
                            active = 1
                        else:
                            continue
                    active = min(active, max_segments)
                    for s in range(active):
                        y = seg_y[s]
                        bar_rect = QRect(x, y, bar_width, seg_height)
                        painter.drawRect(bar_rect)

            painter.end()

    def set_visualization_mode(self, mode: VisualizerMode) -> None:
        """Set the visualization display mode.
        
        Args:
            mode: VisualizerMode.SPECTRUM (only supported mode)
        """
        if mode != self._vis_mode:
            self._vis_mode = mode
            logger.info("[SPOTIFY_VIS] Visualization mode changed to %s", mode.name)

    def get_visualization_mode(self) -> VisualizerMode:
        """Get the current visualization display mode."""
        return self._vis_mode

    def cycle_visualization_mode(self) -> VisualizerMode:
        """Cycle to the next visualization mode and return it."""
        modes = list(VisualizerMode)
        current_idx = modes.index(self._vis_mode)
        next_idx = (current_idx + 1) % len(modes)
        self.set_visualization_mode(modes[next_idx])
        return self._vis_mode

    def _log_perf_snapshot(self, reset: bool = False) -> None:
        """Emit a PERF metrics snapshot for the current tick/paint window.

        When ``reset`` is True, internal counters are cleared afterwards so
        subsequent snapshots start a fresh window (used on widget stop).
        When ``reset`` is False, counters are left intact so that periodic
        logging during runtime does not disturb the measurement window.
        """

        if not is_perf_metrics_enabled():
            return

        try:
            if (
                self._perf_tick_start_ts is not None
                and self._perf_tick_last_ts is not None
                and self._perf_tick_frame_count > 0
            ):
                elapsed = max(0.0, self._perf_tick_last_ts - self._perf_tick_start_ts)
                if elapsed > 0.0:
                    duration_ms = elapsed * 1000.0
                    avg_fps = self._perf_tick_frame_count / elapsed
                    min_dt_ms = self._perf_tick_min_dt * 1000.0 if self._perf_tick_min_dt > 0.0 else 0.0
                    max_dt_ms = self._perf_tick_max_dt * 1000.0 if self._perf_tick_max_dt > 0.0 else 0.0
                    logger.info(
                        "[PERF] [SPOTIFY_VIS] Tick metrics: duration=%.1fms, frames=%d, avg_fps=%.1f, "
                        "dt_min=%.2fms, dt_max=%.2fms, bar_count=%d",
                        duration_ms,
                        self._perf_tick_frame_count,
                        avg_fps,
                        min_dt_ms,
                        max_dt_ms,
                        self._bar_count,
                    )

            if (
                self._perf_paint_start_ts is not None
                and self._perf_paint_last_ts is not None
                and self._perf_paint_frame_count > 0
            ):
                elapsed_p = max(0.0, self._perf_paint_last_ts - self._perf_paint_start_ts)
                if elapsed_p > 0.0:
                    duration_ms_p = elapsed_p * 1000.0
                    avg_fps_p = self._perf_paint_frame_count / elapsed_p
                    min_dt_ms_p = self._perf_paint_min_dt * 1000.0 if self._perf_paint_min_dt > 0.0 else 0.0
                    max_dt_ms_p = self._perf_paint_max_dt * 1000.0 if self._perf_paint_max_dt > 0.0 else 0.0
                    logger.info(
                        "[PERF] [SPOTIFY_VIS] Paint metrics: duration=%.1fms, frames=%d, avg_fps=%.1f, "
                        "dt_min=%.2fms, dt_max=%.2fms, bar_count=%d",
                        duration_ms_p,
                        self._perf_paint_frame_count,
                        avg_fps_p,
                        min_dt_ms_p,
                        max_dt_ms_p,
                        self._bar_count,
                    )
            # Emit a separate AudioLag metrics line so tools that parse
            # Tick/Paint summaries remain compatible.
            try:
                if self._perf_audio_lag_last_ms > 0.0:
                    logger.info(
                        "[PERF] [SPOTIFY_VIS] AudioLag metrics: last=%.2fms, min=%.2fms, max=%.2fms",
                        self._perf_audio_lag_last_ms,
                        self._perf_audio_lag_min_ms,
                        self._perf_audio_lag_max_ms,
                    )
            except Exception:
                logger.debug("[SPOTIFY_VIS] AudioLag PERF metrics logging failed", exc_info=True)
        except Exception:
            logger.debug("[SPOTIFY_VIS] PERF metrics logging failed", exc_info=True)
        finally:
            if reset:
                self._perf_tick_start_ts = None
                self._perf_tick_last_ts = None
                self._perf_tick_frame_count = 0
                self._perf_tick_min_dt = 0.0
                self._perf_tick_max_dt = 0.0
                self._perf_paint_start_ts = None
                self._perf_paint_last_ts = None
                self._perf_paint_frame_count = 0
                self._perf_paint_min_dt = 0.0
                self._perf_paint_max_dt = 0.0
                self._perf_audio_lag_last_ms = 0.0
                self._perf_audio_lag_min_ms = 0.0
                self._perf_audio_lag_max_ms = 0.0

