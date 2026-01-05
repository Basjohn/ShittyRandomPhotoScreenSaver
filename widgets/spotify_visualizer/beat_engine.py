"""Spotify Beat Engine - Shared beat engine with integrated smoothing.

This module contains the _SpotifyBeatEngine class which handles:
- Shared audio buffer management
- FFT computation scheduling on compute pool
- Pre-smoothing of bar heights to reduce UI thread work
- Playback state gating for FFT processing
"""

from __future__ import annotations

from typing import List, Optional
import time
import math

from PySide6.QtCore import QObject

from core.logging.logger import get_logger, is_verbose_logging
from core.threading.manager import ThreadManager
from core.process import ProcessSupervisor
from utils.lockfree import TripleBuffer
from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker, _AudioFrame


logger = get_logger(__name__)


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
        
        # Anti-flicker: Solution 1+2 ONLY (stronger intensity, NO temporal stability)
        self._segment_hysteresis: float = 0.08  # 8% buffer - strong boundary resistance
        self._min_change_threshold: float = 0.05  # 5% threshold - filters noise
        
        # Playback state gating for FFT processing
        self._is_spotify_playing: bool = False
        self._last_playback_state_ts: float = 0.0

    def set_thread_manager(self, thread_manager: Optional[ThreadManager]) -> None:
        self._thread_manager = thread_manager
    
    def set_process_supervisor(self, supervisor: Optional[ProcessSupervisor]) -> None:
        """Set the ProcessSupervisor for FFTWorker integration."""
        try:
            self._audio_worker.set_process_supervisor(supervisor)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Failed to set process supervisor", exc_info=True)
    
    def set_smoothing(self, tau: float) -> None:
        """Set the base smoothing time constant."""
        self._smoothing_tau = max(0.05, float(tau))
    
    def set_sensitivity_config(self, recommended: bool, sensitivity: float) -> None:
        try:
            self._audio_worker.set_sensitivity_config(recommended, sensitivity)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Failed to apply sensitivity config", exc_info=True)
    
    def set_floor_config(self, dynamic_enabled: bool, manual_floor: float) -> None:
        try:
            self._audio_worker.set_floor_config(dynamic_enabled, manual_floor)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Failed to apply floor config", exc_info=True)

    def set_playback_state(self, is_playing: bool) -> None:
        """Set Spotify playback state for FFT processing gating."""
        self._is_spotify_playing = bool(is_playing)
        self._last_playback_state_ts = time.time()
        
        if is_verbose_logging():
            logger.debug(
                "[SPOTIFY_VIS] Beat engine playback state: playing=%s (ts=%.3f)",
                self._is_spotify_playing,
                self._last_playback_state_ts
            )

    def _apply_smoothing(self, target_bars: List[float]) -> List[float]:
        """Apply time-based exponential smoothing with anti-flicker (Solution 1+2)."""
        now_ts = time.time()
        last_ts = self._last_smooth_ts
        dt = max(0.0, now_ts - last_ts) if last_ts >= 0.0 else 0.0
        
        if dt > 2.0 or dt <= 0.0:
            self._smoothed_bars = list(target_bars)
            return self._smoothed_bars
        
        base_tau = self._smoothing_tau
        tau_rise = base_tau * 0.35
        tau_decay = base_tau * 3.0
        alpha_rise = 1.0 - math.exp(-dt / tau_rise)
        alpha_decay = 1.0 - math.exp(-dt / tau_decay)
        alpha_rise = max(0.0, min(1.0, alpha_rise))
        alpha_decay = max(0.0, min(1.0, alpha_decay))
        
        bar_count = self._bar_count
        smoothed = self._smoothed_bars
        hysteresis = self._segment_hysteresis
        min_change = self._min_change_threshold
        
        for i in range(bar_count):
            cur = smoothed[i] if i < len(smoothed) else 0.0
            tgt = target_bars[i] if i < len(target_bars) else 0.0
            
            # Solution 2: Minimum change threshold - filter micro-oscillations
            delta = abs(tgt - cur)
            if delta < min_change:
                smoothed[i] = cur
                continue
            
            # Solution 1: Segment hysteresis - prevent boundary oscillation
            if tgt > cur:
                tgt_adjusted = tgt + hysteresis
            elif tgt < cur:
                tgt_adjusted = tgt - hysteresis
            else:
                tgt_adjusted = tgt
            
            tgt_adjusted = max(0.0, min(1.0, tgt_adjusted))
            
            alpha = alpha_rise if tgt_adjusted >= cur else alpha_decay
            nxt = cur + (tgt_adjusted - cur) * alpha
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
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Failed to start audio worker in shared engine", exc_info=True)

    def _stop_worker(self) -> None:
        try:
            self._audio_worker.stop()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Failed to stop audio worker in shared engine", exc_info=True)

    def _schedule_compute_bars_task(self, samples: object) -> None:
        tm = self._thread_manager
        if tm is None:
            return

        self._compute_task_active = True
        
        smoothed_copy = list(self._smoothed_bars)
        last_smooth_ts = self._last_smooth_ts
        smoothing_tau = self._smoothing_tau
        bar_count = self._bar_count
        hysteresis = self._segment_hysteresis
        min_change = self._min_change_threshold

        def _job(local_samples=samples):
            """FFT + smoothing on COMPUTE pool - keeps UI thread free."""
            raw_bars = self._audio_worker.compute_bars_from_samples(local_samples)
            if not isinstance(raw_bars, list):
                return None
            
            now_ts = time.time()
            dt = max(0.0, now_ts - last_smooth_ts) if last_smooth_ts >= 0.0 else 0.0
            
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
                
                # Solution 2: Minimum change threshold
                delta = abs(tgt - cur)
                if delta < min_change:
                    smoothed.append(cur)
                    continue
                
                # Solution 1: Segment hysteresis
                if tgt > cur:
                    tgt_adjusted = tgt + hysteresis
                elif tgt < cur:
                    tgt_adjusted = tgt - hysteresis
                else:
                    tgt_adjusted = tgt
                
                tgt_adjusted = max(0.0, min(1.0, tgt_adjusted))
                
                alpha = alpha_rise if tgt_adjusted >= cur else alpha_decay
                nxt = cur + (tgt_adjusted - cur) * alpha
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
            except Exception as e:
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
                
                if not self._is_spotify_playing:
                    if self._latest_bars is None or len(self._latest_bars) != self._bar_count:
                        self._latest_bars = [0.0] * self._bar_count
                    if all(bar == 0.0 for bar in self._latest_bars):
                        self._latest_bars[0] = 0.08
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
        """Get pre-smoothed bars for UI display."""
        return list(self._smoothed_bars)


class BeatEngineRegistry:
    """Registry for beat engine instances - supports dependency injection.
    
    This replaces the module-level singleton with a registry pattern that:
    1. Allows DI by passing engine instances to widgets
    2. Maintains backward compatibility via get_shared_spotify_beat_engine()
    3. Supports testing by allowing engine replacement
    """
    _instance: Optional["BeatEngineRegistry"] = None
    _lock = __import__("threading").Lock()
    
    def __init__(self):
        self._engines: dict[int, _SpotifyBeatEngine] = {}  # bar_count -> engine
        self._default_engine: Optional[_SpotifyBeatEngine] = None
    
    @classmethod
    def get_instance(cls) -> "BeatEngineRegistry":
        """Get singleton registry instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def get_engine(self, bar_count: int) -> _SpotifyBeatEngine:
        """Get or create engine for given bar count."""
        bar_count = max(1, int(bar_count))
        if bar_count not in self._engines:
            self._engines[bar_count] = _SpotifyBeatEngine(bar_count)
            if self._default_engine is None:
                self._default_engine = self._engines[bar_count]
        return self._engines[bar_count]
    
    def set_engine(self, bar_count: int, engine: _SpotifyBeatEngine) -> None:
        """Inject a custom engine (for testing)."""
        self._engines[bar_count] = engine
    
    def clear(self) -> None:
        """Clear all engines (for testing)."""
        self._engines.clear()
        self._default_engine = None


# Backward compatibility: module-level singleton via registry
_global_beat_engine: Optional[_SpotifyBeatEngine] = None


def get_shared_spotify_beat_engine(bar_count: int) -> _SpotifyBeatEngine:
    """Get or create the shared Spotify beat engine.
    
    This function maintains backward compatibility while using the registry
    internally. For new code, prefer using BeatEngineRegistry directly.
    """
    global _global_beat_engine
    registry = BeatEngineRegistry.get_instance()
    engine = registry.get_engine(bar_count)
    
    # Update module-level reference for backward compatibility
    if _global_beat_engine is None:
        _global_beat_engine = engine
    elif _global_beat_engine._bar_count != bar_count:
        logger.debug(
            "[SPOTIFY_VIS] Shared beat engine bar_count mismatch: existing=%d, requested=%d",
            _global_beat_engine._bar_count,
            bar_count,
        )
    
    return engine
