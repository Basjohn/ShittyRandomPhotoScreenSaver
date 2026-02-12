"""
FFT Worker for audio processing and visualizer bar generation.

Runs in a separate process to handle loopback audio capture and FFT
computation without blocking the UI thread.

Key responsibilities:
- FFT computation from audio samples
- Bar height generation with preserved mathematical operations
- Smoothing with exact tau values from VISUALIZER_DEBUG.md
- Ghost envelope generation for peak indicators

CRITICAL: All mathematical operations must exactly match the current
implementation to preserve visualizer fidelity.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from multiprocessing import Queue
from typing import List, Optional

from core.process.types import (
    MessageType,
    WorkerMessage,
    WorkerResponse,
    WorkerType,
)
from core.process.workers.base import BaseWorker

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


@dataclass
class FFTConfig:
    """Configuration for FFT processing - preserves exact values from implementation."""
    bar_count: int = 16
    smoothing_tau_rise_factor: float = 0.35   # tau_rise = base_tau * 0.35
    smoothing_tau_decay_factor: float = 3.0   # tau_decay = base_tau * 3.0
    base_tau_ms: float = 100.0                # Base smoothing tau
    ghost_enabled: bool = True
    ghost_decay: float = 0.85
    decay_rate: float = 0.35                  # Fast fall for visible drops
    attack_speed: float = 0.85                # 85% toward target per frame
    
    # Noise floor settings
    min_floor: float = 0.12
    max_floor: float = 4.0
    dynamic_floor_ratio: float = 0.462
    floor_mid_weight: float = 0.18
    
    # Profile template for center-out mapping (15 elements)
    # Index:  0     1     2     3     4     5     6     7     8     9    10    11    12    13    14
    # Role:  edge  edge  edge slope PEAK slope shld  CTR  shld slope PEAK slope edge  edge  edge
    profile_template: List[float] = field(default_factory=lambda: [
        0.10, 0.15, 0.25, 0.50, 1.0, 0.45, 0.25, 0.08, 0.25, 0.45, 1.0, 0.50, 0.25, 0.15, 0.10
    ])
    
    # Dual-curve profile (mirrored per half):
    #   Edge(bass peak) → decay → dip → vocal peak → taper → calm center
    #   Per-half from edge: 1.0, 0.82(-18%), 0.70(-15%), 0.61(-12%),
    #   0.55(-10% dip), 0.80(vocal peak, 2nd/3rd highest), 0.68(-15%), 0.45(center)
    # Index:  0     1     2     3     4     5     6     7     8     9    10    11    12    13    14
    # Role:  BASS  bass  bass  bass  dip  VOCAL vocal  CTR  vocal VOCAL  dip  bass  bass  bass  BASS
    use_curved_profile: bool = False
    curved_profile_template: List[float] = field(default_factory=lambda: [
        1.0, 0.72, 0.50, 0.38, 0.28, 0.58, 0.40, 0.22, 0.40, 0.58, 0.28, 0.38, 0.50, 0.72, 1.0
    ])
    
    # Convolution kernel for smoothing
    smooth_kernel: List[float] = field(default_factory=lambda: [0.25, 0.5, 0.25])


@dataclass
class FFTState:
    """State maintained across FFT frames."""
    bars: List[float] = field(default_factory=list)
    peaks: List[float] = field(default_factory=list)
    bar_history: List[float] = field(default_factory=list)
    raw_bass_avg: float = 2.1
    applied_noise_floor: float = 2.1
    prev_raw_bass: float = 0.0
    bass_drop_accum: float = 0.0
    last_fft_ts: float = 0.0
    band_cache_key: Optional[tuple] = None
    band_edges: Optional[List[int]] = None


class FFTWorker(BaseWorker):
    """
    Worker for FFT processing and bar generation.
    
    Handles:
    - FFT_CONFIG: Update FFT configuration
    - FFT_FRAME: Process audio samples and return bar heights
    
    Preserves all mathematical operations from the original implementation
    to maintain visualizer fidelity.
    """
    
    def __init__(self, request_queue: Queue, response_queue: Queue):
        super().__init__(request_queue, response_queue)
        self._config = FFTConfig()
        self._state = FFTState()
        self._frames_processed = 0
        self._init_state()
    
    def _init_state(self) -> None:
        """Initialize state arrays."""
        bar_count = self._config.bar_count
        self._state.bars = [0.0] * bar_count
        self._state.peaks = [0.0] * bar_count
        self._state.bar_history = [0.0] * bar_count
    
    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.FFT
    
    def handle_message(self, msg: WorkerMessage) -> Optional[WorkerResponse]:
        """Handle FFT processing messages."""
        if msg.msg_type == MessageType.FFT_CONFIG:
            return self._handle_config(msg)
        elif msg.msg_type == MessageType.FFT_FRAME:
            return self._handle_frame(msg)
        elif msg.msg_type == MessageType.CONFIG_UPDATE:
            return self._handle_config(msg)
        else:
            return WorkerResponse(
                msg_type=MessageType.ERROR,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"Unknown message type: {msg.msg_type}",
            )
    
    def _handle_config(self, msg: WorkerMessage) -> WorkerResponse:
        """Update FFT configuration."""
        payload = msg.payload
        
        if "bar_count" in payload:
            new_count = int(payload["bar_count"])
            if new_count != self._config.bar_count:
                self._config.bar_count = new_count
                self._init_state()
        
        # Update other config values
        if "use_curved_profile" in payload:
            self._config.use_curved_profile = bool(payload["use_curved_profile"])
        
        for key in ["smoothing_tau_rise_factor", "smoothing_tau_decay_factor",
                    "base_tau_ms", "ghost_enabled", "ghost_decay",
                    "decay_rate", "attack_speed", "min_floor", "max_floor",
                    "dynamic_floor_ratio", "floor_mid_weight"]:
            if key in payload:
                setattr(self._config, key, payload[key])
        
        return WorkerResponse(
            msg_type=MessageType.FFT_CONFIG,
            seq_no=msg.seq_no,
            correlation_id=msg.correlation_id,
            success=True,
            payload={"bar_count": self._config.bar_count},
        )
    
    def _handle_frame(self, msg: WorkerMessage) -> WorkerResponse:
        """Process audio samples and generate bar heights."""
        if not NUMPY_AVAILABLE:
            return WorkerResponse(
                msg_type=MessageType.ERROR,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error="NumPy is required for FFT processing",
            )
        
        samples = msg.payload.get("samples")
        # sample_rate available for future use
        _ = msg.payload.get("sample_rate", 44100)
        sensitivity = msg.payload.get("sensitivity", 1.0)
        use_dynamic_floor = msg.payload.get("use_dynamic_floor", True)
        
        if samples is None:
            return WorkerResponse(
                msg_type=MessageType.FFT_BARS,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=True,
                payload={
                    "bars": self._state.bars,
                    "peaks": self._state.peaks,
                },
            )
        
        start = time.time()
        try:
            # Convert samples to numpy array
            if not isinstance(samples, np.ndarray):
                samples = np.array(samples, dtype=np.float32)
            
            # Compute FFT
            fft = np.fft.rfft(samples)
            mag = np.abs(fft[1:])  # Skip DC component
            
            if mag.size == 0:
                return WorkerResponse(
                    msg_type=MessageType.FFT_BARS,
                    seq_no=msg.seq_no,
                    correlation_id=msg.correlation_id,
                    success=True,
                    payload={
                        "bars": self._state.bars,
                        "peaks": self._state.peaks,
                    },
                )
            
            # Process FFT to bars - preserving exact math
            bars = self._fft_to_bars(mag, sensitivity, use_dynamic_floor)
            
            # Apply smoothing
            self._apply_smoothing(bars)
            
            # Update peaks (ghosting)
            if self._config.ghost_enabled:
                self._update_peaks()
            
            self._frames_processed += 1
            
            return WorkerResponse(
                msg_type=MessageType.FFT_BARS,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=True,
                payload={
                    "bars": list(self._state.bars),
                    "peaks": list(self._state.peaks),
                    "frame_count": self._frames_processed,
                },
                processing_time_ms=(time.time() - start) * 1000,
            )
            
        except Exception as e:
            if self._logger:
                self._logger.exception("FFT processing failed: %s", e)
            return WorkerResponse(
                msg_type=MessageType.ERROR,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"FFT processing failed: {e}",
            )
    
    def _fft_to_bars(
        self,
        mag: "np.ndarray",
        sensitivity: float,
        use_dynamic_floor: bool,
    ) -> List[float]:
        """
        Convert FFT magnitudes to bar heights.
        
        Preserves exact mathematical operations from VISUALIZER_DEBUG.md:
        - log1p + power(1.2) normalization
        - Convolution with [0.25, 0.5, 0.25] kernel
        - Center-out frequency mapping
        - Adaptive sensitivity with resolution boost
        """
        bands = self._config.bar_count
        n = int(mag.size)
        
        # Resolution boost calculation
        resolution_boost = max(0.5, min(3.0, 1024.0 / max(256.0, float(n))))
        # low_resolution used for future enhancements
        _ = resolution_boost > 1.05
        
        # In-place log1p and power - EXACT match
        mag = mag.astype(np.float32)
        np.log1p(mag, out=mag)
        np.power(mag, 1.2, out=mag)
        
        # Convolution smoothing - EXACT kernel
        if n > 4:
            kernel = np.array(self._config.smooth_kernel, dtype=np.float32)
            mag = np.convolve(mag, kernel, mode="same")
        
        # Logarithmic band edges
        cache_key = (n, bands)
        if self._state.band_cache_key != cache_key:
            min_freq_idx = 1
            max_freq_idx = n
            log_edges = np.logspace(
                np.log10(min_freq_idx),
                np.log10(max_freq_idx),
                bands + 1,
            ).astype(np.int32)
            self._state.band_cache_key = cache_key
            self._state.band_edges = log_edges.tolist()
        
        edges = self._state.band_edges
        
        # Compute RMS for each frequency band
        freq_values = []
        for b in range(bands):
            start = edges[b]
            end = edges[b + 1]
            if end <= start:
                end = start + 1
            if start < n and end <= n:
                band_slice = mag[start:end]
                if band_slice.size > 0:
                    freq_values.append(float(np.sqrt(np.mean(band_slice ** 2))))
                else:
                    freq_values.append(0.0)
            else:
                freq_values.append(0.0)
        
        # Raw energy values
        raw_bass = float(np.mean(freq_values[:4])) if bands >= 4 else freq_values[0] if freq_values else 0.0
        raw_mid = float(np.mean(freq_values[4:10])) if bands >= 10 else raw_bass * 0.5
        raw_treble = float(np.mean(freq_values[10:])) if bands > 10 else raw_bass * 0.2
        
        # Noise floor calculation
        noise_floor_base = max(0.8, 1.5 / (resolution_boost ** 0.35))
        expansion_base = 3.6 * (resolution_boost ** 0.4)
        
        sensitivity = max(0.25, min(2.5, sensitivity))
        base_noise_floor = max(
            self._config.min_floor,
            min(self._config.max_floor, noise_floor_base / sensitivity)
        )
        expansion = expansion_base * (sensitivity ** 0.35)
        
        # Dynamic floor
        noise_floor = base_noise_floor
        if use_dynamic_floor:
            avg = self._state.raw_bass_avg
            floor_mid_weight = self._config.floor_mid_weight
            floor_signal = raw_bass * (1.0 - floor_mid_weight) + raw_mid * floor_mid_weight
            alpha = 0.15 if floor_signal >= avg else 0.4
            avg = (1.0 - alpha) * avg + alpha * floor_signal
            self._state.raw_bass_avg = avg
            
            dyn_candidate = max(
                self._config.min_floor,
                min(self._config.max_floor, avg * self._config.dynamic_floor_ratio)
            )
            noise_floor = max(self._config.min_floor, min(base_noise_floor, dyn_candidate))
        
        # Energy calculation
        bass_energy = max(0.0, (raw_bass - noise_floor) * expansion)
        mid_energy = max(0.0, (raw_mid - noise_floor * 0.4) * expansion)
        treble_energy = max(0.0, (raw_treble - noise_floor * 0.2) * expansion)
        
        # Profile computation (curved cosine-bell or legacy template)
        use_curved = self._config.use_curved_profile
        
        # Overall energy
        overall_energy = bass_energy * 0.9 + mid_energy * 0.6 + treble_energy * 0.35
        overall_energy = max(0.0, min(1.8, overall_energy))
        
        # CENTER-OUT mapping
        center = bands // 2
        half = bands // 2

        if use_curved:
            # Smooth sinusoidal wave curve (matches bar_computation.py)
            frac_arr = np.abs(np.arange(bands, dtype=np.float32) - center) / max(1.0, float(half))
            wave = np.sin(frac_arr * np.pi * 1.5 + np.pi * 0.5)
            profile_shape = wave * 0.35 + 0.50
            edge_boost = np.exp(-((frac_arr - 1.0) ** 2) / 0.08) * 0.20
            profile_shape = profile_shape + edge_boost
            profile_shape = np.maximum(profile_shape, 0.12)
        else:
            src = self._config.profile_template
            template = np.array(src, dtype=np.float32)
            if bands != len(template):
                xp = np.linspace(0.0, 1.0, len(template))
                x = np.linspace(0.0, 1.0, bands)
                profile_shape = np.interp(x, xp, template)
            else:
                profile_shape = template.copy()

        bars = []
        for i in range(bands):
            offset = abs(i - center)
            
            if use_curved:
                # Smooth cosine zone blending (matches bar_computation.py)
                frac = offset / max(1.0, float(half))
                def _cp(t): return math.cos(math.pi * t)
                w_bass = max(0.0, 0.5 * (1.0 + _cp(min(1.0, max(-1.0, (frac - 0.80) / 0.25)))))
                w_vocal = max(0.0, 0.5 * (1.0 + _cp(min(1.0, max(-1.0, (frac - 0.42) / 0.22)))))
                w_center = max(0.0, 0.5 * (1.0 + _cp(min(1.0, max(-1.0, frac / 0.25)))))
                w_total = w_bass + w_vocal + w_center + 0.001
                e_bass = bass_energy * 0.78 + mid_energy * 0.04 + treble_energy * 0.04
                e_vocal = bass_energy * 0.05 + mid_energy * 0.82 + treble_energy * 0.08
                e_center = bass_energy * 0.05 + mid_energy * 0.18 + treble_energy * 0.08
                zone_energy = (w_bass * e_bass + w_vocal * e_vocal + w_center * e_center) / w_total
                base = profile_shape[i] * zone_energy
            else:
                base = profile_shape[i] * overall_energy
                # Ridge peak boost
                if offset == 3:
                    base = base * 1.05 + bass_energy * 0.15
                elif offset == 4:
                    base = base * 0.82
                
                # Center reactivity
                if offset == 0:
                    vocal_drive = mid_energy * 4.0
                    base = vocal_drive * 0.90 + base * 0.10
                
                # Shoulder taper
                if offset == 1:
                    base = base * 0.52 + mid_energy * 0.22
                if offset == 2:
                    base = base * 0.58 + bass_energy * 0.12
                
                # Edge treble
                if offset >= 5:
                    base = base * 0.65 + treble_energy * 0.4 * (offset - 4)
            
            bars.append(max(0.0, min(1.0, base)))
        
        return bars
    
    def _apply_smoothing(self, target_bars: List[float]) -> None:
        """Apply attack/decay smoothing to bars."""
        decay_rate = self._config.decay_rate
        attack_speed = self._config.attack_speed
        
        # Check for pause/resume gap
        now_ts = time.time()
        dt = now_ts - self._state.last_fft_ts if self._state.last_fft_ts > 0 else 0.0
        self._state.last_fft_ts = now_ts
        
        if dt > 2.0:
            # Reset after long pause
            self._state.bar_history = [0.0] * len(target_bars)
        
        for i in range(min(len(target_bars), len(self._state.bars))):
            target = target_bars[i]
            current = self._state.bar_history[i] if i < len(self._state.bar_history) else 0.0
            
            if target > current:
                # Attack: rise quickly
                new_val = current + (target - current) * attack_speed
            else:
                # Decay: fall with decay rate
                new_val = current * decay_rate + target * (1 - decay_rate)
            
            self._state.bars[i] = max(0.0, min(1.0, new_val))
            if i < len(self._state.bar_history):
                self._state.bar_history[i] = new_val
    
    def _update_peaks(self) -> None:
        """Update peak values for ghosting effect."""
        ghost_decay = self._config.ghost_decay
        
        for i in range(len(self._state.bars)):
            bar_val = self._state.bars[i]
            peak_val = self._state.peaks[i] if i < len(self._state.peaks) else 0.0
            
            if bar_val > peak_val:
                self._state.peaks[i] = bar_val
            else:
                self._state.peaks[i] = peak_val * ghost_decay
    
    def _cleanup(self) -> None:
        """Log final statistics."""
        if self._logger:
            self._logger.info(
                "FFT stats: %d frames processed",
                self._frames_processed,
            )


def fft_worker_main(request_queue: Queue, response_queue: Queue) -> None:
    """Entry point for FFT worker process."""
    import sys
    
    # Pre-import logging to stderr (before any imports that might fail)
    sys.stderr.write("=== FFT Worker: Process started ===\n")
    sys.stderr.flush()
    
    try:
        sys.stderr.write("FFT Worker: Importing traceback...\n")
        sys.stderr.flush()
        import traceback
        
        sys.stderr.write("FFT Worker: Importing logger...\n")
        sys.stderr.flush()
        from core.logging.logger import get_logger
        logger = get_logger(__name__)
        
        sys.stderr.write("FFT Worker: Checking NumPy availability...\n")
        sys.stderr.flush()
        if not NUMPY_AVAILABLE:
            sys.stderr.write("FFT Worker FATAL: NumPy is NOT available\n")
            sys.stderr.flush()
            logger.error("FFT Worker FATAL: NumPy is not available")
            raise RuntimeError("NumPy is required for FFTWorker")
        
        sys.stderr.write("FFT Worker: NumPy is available, creating worker instance...\n")
        sys.stderr.flush()
        logger.info("FFT Worker starting...")
        
        worker = FFTWorker(request_queue, response_queue)
        
        sys.stderr.write("FFT Worker: Starting main loop...\n")
        sys.stderr.flush()
        worker.run()
        
        sys.stderr.write("FFT Worker: Exiting normally\n")
        sys.stderr.flush()
        logger.info("FFT Worker exiting normally")
    except Exception as e:
        sys.stderr.write(f"FFT Worker CRASHED: {e}\n")
        sys.stderr.write(f"FFT Worker crash traceback:\n{''.join(traceback.format_exception(*sys.exc_info()))}\n")
        sys.stderr.flush()
        try:
            logger.exception(f"FFT Worker CRASHED: {e}")
        except Exception:
            pass
        raise
