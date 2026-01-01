"""
Beat Engine - Extracted from SpotifyVisualizerWidget for better separation.

Handles FFT processing, beat detection, and bar smoothing on the COMPUTE pool.
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Tuple

from core.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BeatEngineConfig:
    """Configuration for the beat engine."""
    bar_count: int = 16
    segments: int = 16
    smoothing_factor: float = 0.15
    decay_rate: float = 0.92
    idle_floor: float = 0.08
    ghost_enabled: bool = True
    ghost_alpha: float = 0.4
    ghost_decay: float = 0.85
    frequency_boost: float = 2.5  # High-frequency compensation


@dataclass
class BeatEngineState:
    """Current state of the beat engine."""
    bars: List[float] = field(default_factory=list)
    peaks: List[float] = field(default_factory=list)
    target_bars: List[float] = field(default_factory=list)
    is_playing: bool = False
    last_update_time: float = 0.0


class BeatEngine:
    """
    Processes audio data into visualizer bar heights.
    
    All heavy computation (FFT, smoothing) runs on the COMPUTE pool.
    The engine maintains thread-safe state that can be read from the UI thread.
    """
    
    def __init__(self, config: Optional[BeatEngineConfig] = None):
        """
        Initialize the beat engine.
        
        Args:
            config: Engine configuration
        """
        self._config = config or BeatEngineConfig()
        self._state = BeatEngineState()
        self._state.bars = [0.0] * self._config.bar_count
        self._state.peaks = [0.0] * self._config.bar_count
        self._state.target_bars = [0.0] * self._config.bar_count
        
        self._lock = threading.Lock()
        self._on_update: Optional[Callable[[List[float], List[float]], None]] = None
        
        # FFT state
        self._fft_buffer: List[float] = []
        self._sample_rate: int = 44100
        
        logger.debug("[BEAT_ENGINE] Initialized with %d bars", self._config.bar_count)
    
    @property
    def config(self) -> BeatEngineConfig:
        """Get current configuration."""
        return self._config
    
    def set_config(self, config: BeatEngineConfig) -> None:
        """Update configuration."""
        with self._lock:
            old_count = self._config.bar_count
            self._config = config
            if config.bar_count != old_count:
                self._state.bars = [0.0] * config.bar_count
                self._state.peaks = [0.0] * config.bar_count
                self._state.target_bars = [0.0] * config.bar_count
    
    def set_on_update(self, callback: Callable[[List[float], List[float]], None]) -> None:
        """Set callback for when bars are updated. Args: (bars, peaks)"""
        self._on_update = callback
    
    def get_state(self) -> Tuple[List[float], List[float], bool]:
        """
        Get current state (thread-safe).
        
        Returns:
            Tuple of (bars, peaks, is_playing)
        """
        with self._lock:
            return (
                list(self._state.bars),
                list(self._state.peaks),
                self._state.is_playing
            )
    
    def set_playing(self, playing: bool) -> None:
        """Set playing state."""
        with self._lock:
            self._state.is_playing = playing
    
    def process_audio_data(self, samples: List[float], sample_rate: int = 44100) -> None:
        """
        Process raw audio samples into bar heights.
        
        This should be called from the COMPUTE pool.
        
        Args:
            samples: Raw audio samples
            sample_rate: Sample rate in Hz
        """
        if not samples:
            return
        
        self._sample_rate = sample_rate
        bar_count = self._config.bar_count
        
        # Simple FFT-like frequency analysis
        # For real FFT, use numpy.fft - this is a simplified version
        target_bars = self._compute_frequency_bars(samples, bar_count)
        
        # Apply frequency compensation (boost high frequencies)
        for i in range(bar_count):
            t = i / max(1, bar_count - 1)  # 0..1
            boost = 1.0 + self._config.frequency_boost * (t ** 1.5)
            target_bars[i] = min(1.0, target_bars[i] * boost)
        
        # Apply smoothing and update state
        self._apply_smoothing(target_bars)
    
    def _compute_frequency_bars(self, samples: List[float], bar_count: int) -> List[float]:
        """
        Compute frequency bars from audio samples.
        
        This is a simplified frequency analysis. For production use,
        consider using numpy.fft.rfft for proper FFT.
        """
        if not samples:
            return [0.0] * bar_count
        
        # Simple energy-based analysis (not true FFT)
        # Divide samples into bar_count segments and compute RMS
        segment_size = max(1, len(samples) // bar_count)
        bars = []
        
        for i in range(bar_count):
            start = i * segment_size
            end = min(start + segment_size, len(samples))
            segment = samples[start:end]
            
            if segment:
                # RMS energy
                rms = math.sqrt(sum(s * s for s in segment) / len(segment))
                # Normalize to 0..1 range (assuming samples are -1..1)
                bars.append(min(1.0, rms * 2.0))
            else:
                bars.append(0.0)
        
        return bars
    
    def _apply_smoothing(self, target_bars: List[float]) -> None:
        """Apply smoothing and decay to bars."""
        with self._lock:
            bar_count = len(self._state.bars)
            smoothing = self._config.smoothing_factor
            decay = self._config.decay_rate
            idle_floor = self._config.idle_floor
            ghost_decay = self._config.ghost_decay
            
            for i in range(min(bar_count, len(target_bars))):
                target = target_bars[i]
                current = self._state.bars[i]
                
                # Smooth towards target
                if target > current:
                    # Rise quickly
                    new_val = current + (target - current) * (1.0 - smoothing * 0.5)
                else:
                    # Fall with decay
                    new_val = current * decay
                    if new_val < target:
                        new_val = target
                
                # Apply idle floor
                if self._state.is_playing and new_val < idle_floor:
                    new_val = idle_floor
                
                self._state.bars[i] = new_val
                
                # Update peaks (ghosting)
                if new_val > self._state.peaks[i]:
                    self._state.peaks[i] = new_val
                else:
                    self._state.peaks[i] *= ghost_decay
            
            self._state.target_bars = list(target_bars)
            self._state.last_update_time = time.time()
        
        # Notify listener
        if self._on_update:
            try:
                bars, peaks, _ = self.get_state()
                self._on_update(bars, peaks)
            except Exception:
                pass
    
    def tick(self, dt: float) -> None:
        """
        Update engine state for one frame.
        
        Call this from the animation loop to apply decay when no audio data.
        
        Args:
            dt: Time delta in seconds
        """
        with self._lock:
            if not self._state.is_playing:
                # Decay all bars when not playing
                decay = self._config.decay_rate ** (dt * 60)  # Normalize to 60fps
                for i in range(len(self._state.bars)):
                    self._state.bars[i] *= decay
                    self._state.peaks[i] *= self._config.ghost_decay ** (dt * 60)
    
    def reset(self) -> None:
        """Reset all bars to zero."""
        with self._lock:
            for i in range(len(self._state.bars)):
                self._state.bars[i] = 0.0
                self._state.peaks[i] = 0.0
                self._state.target_bars[i] = 0.0
