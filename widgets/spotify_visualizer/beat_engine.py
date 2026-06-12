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

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]

from core.logging.logger import (
    get_logger,
    is_verbose_logging,
    is_perf_metrics_enabled,
    is_viz_diagnostics_enabled,
)
from core.threading.manager import ThreadManager
from core.process import ProcessSupervisor
from utils.lockfree import TripleBuffer
from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker, _AudioFrame
from widgets.spotify_visualizer.energy_bands import EnergyBands, extract_energy_bands
from widgets.spotify_visualizer.signal_contract import soft_ceiling
from widgets.spotify_visualizer.transient_bus import TransientEnergyBands, TransientEventScheduler


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
        self._compute_gate_token: int = 0
        self._thread_manager: Optional[ThreadManager] = None
        self._ref_count: int = 0
        self._latest_bars: Optional[List[float]] = None
        self._last_audio_ts: float = 0.0
        self._generation_id: int = 0
        self._activation_id: int = 0
        self._latest_generation_with_frame: int = 0
        self._latest_generation_with_waveform: int = 0

        # Waveform buffer for oscilloscope visualizer (last 256 raw samples)
        self._waveform: List[float] = [0.0] * 256
        self._waveform_count: int = 256

        # Energy bands for blob
        self._energy_bands: EnergyBands = EnergyBands()
        
        # Smoothing state (moved from widget to reduce UI thread work)
        self._smoothed_bars: List[float] = [0.0] * self._bar_count
        self._last_smooth_ts: float = -1.0
        self._smoothing_tau: float = 0.10  # Base smoothing time constant
        
        # Anti-flicker: dead-zone threshold filters micro-oscillations
        self._segment_hysteresis: float = 0.0  # Disabled — was amplifying oscillations
        self._min_change_threshold: float = 0.008  # 0.8% dead-zone — tight enough to let bars reach zero
        
        # Playback state gating for FFT processing
        self._is_spotify_playing: bool = False
        self._last_playback_state_ts: float = 0.0
        self._capture_keepalive_grace: float = 6.0
        self._capture_keepalive_deadline: float = 0.0

        # Reactivity ramp-up: gentle fade-in after play detection to mask
        # AGC warmup (envelopes converging to actual audio levels).
        self._play_ramp_start_ts: float = 0.0
        self._play_ramp_duration: float = 1.5  # seconds
        self._idle_wave_phase: float = 0.0

    def set_thread_manager(self, thread_manager: Optional[ThreadManager]) -> None:
        self._thread_manager = thread_manager
    
    def set_process_supervisor(self, supervisor: Optional[ProcessSupervisor]) -> None:
        """Set the ProcessSupervisor for worker integration."""
        try:
            self._audio_worker.set_process_supervisor(supervisor)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to set process supervisor", exc_info=True)

    def _replace_runtime_buffers(self) -> None:
        """Discard queued audio/result frames at a runtime activation boundary."""
        self._audio_buffer = TripleBuffer()
        self._bars_result_buffer = TripleBuffer()
        self._audio_worker._buffer = self._audio_buffer
        self._audio_worker._activation_id = self._activation_id

    def reconfigure_bar_count(self, bar_count: int) -> None:
        """Rebuild shared runtime state for a new bar count."""
        new_count = max(1, int(bar_count))
        if new_count == self._bar_count:
            return

        self.cancel_pending_compute_tasks()
        self._bar_count = new_count
        self._replace_runtime_buffers()
        self._audio_worker.reconfigure_bar_count(new_count)
        self._latest_bars = [0.0] * new_count
        self._smoothed_bars = [0.0] * new_count
        self._last_smooth_ts = -1.0
        self._last_audio_ts = 0.0
        self._waveform = [0.0] * 256
        self._waveform_count = 0
        self._idle_wave_phase = 0.0
        self._energy_bands = EnergyBands()
        self._generation_id += 1
        self._activation_id += 1
        self._audio_worker._activation_id = self._activation_id
        self._latest_generation_with_frame = self._generation_id - 1
        self._latest_generation_with_waveform = self._generation_id - 1
        logger.debug(
            "[SPOTIFY_VIS] Beat engine bar-count reconfigured -> %d (generation=%d activation=%d)",
            new_count,
            self._generation_id,
            self._activation_id,
        )
    
    def reset_smoothing_state(self) -> None:
        """Reset all smoothing/energy state for a clean mode switch.

        Called when the visualizer mode changes so the new mode starts
        with fresh data instead of inheriting stale smoothed bars and
        energy bands from the previous mode.
        """
        self.cancel_pending_compute_tasks()
        self._replace_runtime_buffers()
        self._smoothed_bars = [0.0] * self._bar_count
        self._last_smooth_ts = -1.0
        self._energy_bands = EnergyBands()
        self._waveform = [0.0] * 256
        self._waveform_count = 0
        self._idle_wave_phase = 0.0
        self._latest_bars = [0.0] * self._bar_count
        self._last_audio_ts = 0.0
        self._audio_worker.reset_processing_caches()
        self._audio_worker.reset_reactivity_state()
        self._generation_id += 1
        self._activation_id += 1
        self._audio_worker._activation_id = self._activation_id
        # Force consumers to wait for the next FFT result produced after
        # this reset instead of reusing the pre-reset generation id.
        self._latest_generation_with_frame = self._generation_id - 1
        self._latest_generation_with_waveform = self._generation_id - 1
        logger.debug(
            "[SPOTIFY_VIS] Beat engine smoothing state reset (generation=%d activation=%d)",
            self._generation_id,
            self._activation_id,
        )

    def reset_floor_state(self) -> None:
        """Reset dynamic/manual floor accumulator state."""
        try:
            aw = self._audio_worker
            aw.reset_reactivity_state()
            aw._last_floor_config = (aw._use_dynamic_floor, aw._manual_floor)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to reset floor state", exc_info=True)

    def cancel_pending_compute_tasks(self) -> None:
        """Invalidate outstanding compute callbacks before restarting."""
        self._compute_gate_token += 1
        self._compute_task_active = False

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

    def set_curved_profile(self, enabled: bool) -> None:
        """Toggle curved vs legacy spectrum bar profile on the audio worker."""
        try:
            self._audio_worker.set_curved_profile(enabled)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to apply curved profile config", exc_info=True)

    def set_drop_speed(self, speed: float) -> None:
        """Forward drop speed multiplier to the audio worker DSP pipeline."""
        try:
            self._audio_worker.set_drop_speed(speed)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to apply drop speed config", exc_info=True)

    def set_notch_positions(self, positions: list) -> None:
        """Forward frequency-zone notch positions to the audio worker."""
        try:
            self._audio_worker.set_notch_positions(positions)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to apply notch positions config", exc_info=True)

    def set_spectrum_shape_config(self, config) -> None:
        """Forward SpectrumShapeConfig to the audio worker DSP pipeline."""
        try:
            self._audio_worker.set_spectrum_shape_config(config)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to apply spectrum shape config", exc_info=True)

    def set_spectrum_mirrored(self, mirrored: bool) -> None:
        """Forward mirrored layout toggle to the audio worker."""
        try:
            self._audio_worker.set_spectrum_mirrored(mirrored)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to apply spectrum mirrored config", exc_info=True)

    def set_spectrum_shape_nodes(self, nodes: list) -> None:
        """Forward shape editor nodes to the audio worker."""
        try:
            self._audio_worker.set_spectrum_shape_nodes(nodes)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to apply spectrum shape nodes", exc_info=True)

    def set_energy_boost(self, boost: float) -> None:
        """Forward energy boost scaling to the audio worker."""
        try:
            self._audio_worker.set_energy_boost(boost)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to apply energy boost config", exc_info=True)

    def set_input_gain(self, gain: float) -> None:
        """Forward pre-FFT input gain (virtual volume) to the audio worker."""
        try:
            self._audio_worker.set_input_gain(gain)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to apply input gain config", exc_info=True)

    def set_agc_strength(self, strength: float) -> None:
        """Forward AGC strength to the audio worker."""
        try:
            self._audio_worker.set_agc_strength(strength)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to apply agc strength config", exc_info=True)

    def set_playback_state(self, is_playing: bool) -> None:
        """Set Spotify playback state for FFT processing gating."""
        was_playing = self._is_spotify_playing
        self._is_spotify_playing = bool(is_playing)
        self._last_playback_state_ts = time.time()
        warm_resume = self._capture_keepalive_deadline > 0.0
        if self._is_spotify_playing:
            self._capture_keepalive_deadline = 0.0

        # Start reactivity ramp-up on pause→play transition so the first
        # few FFT frames (where AGC envelopes are still converging) get
        # gently faded in instead of producing erratic bar heights.
        if self._is_spotify_playing and not was_playing:
            if self._ref_count > 0:
                self.ensure_started()
            if warm_resume:
                self._play_ramp_start_ts = 0.0
                logger.debug("[SPOTIFY_VIS] Play resumed while capture stayed warm")
            else:
                self._play_ramp_start_ts = time.time()
                logger.debug("[SPOTIFY_VIS] Play detected — starting %.1fs reactivity ramp-up", self._play_ramp_duration)
        elif (not self._is_spotify_playing) and was_playing:
            self._play_ramp_start_ts = 0.0
            self._schedule_worker_stop_after_grace()
        
        if is_verbose_logging():
            logger.debug(
                "[SPOTIFY_VIS] Beat engine playback state: playing=%s (ts=%.3f)",
                self._is_spotify_playing,
                self._last_playback_state_ts
            )

    def _get_play_ramp_factor(self) -> float:
        """Return 0.0→1.0 fade factor during AGC warmup after play detection."""
        if self._play_ramp_start_ts <= 0.0:
            return 1.0
        elapsed = time.time() - self._play_ramp_start_ts
        if elapsed >= self._play_ramp_duration:
            self._play_ramp_start_ts = 0.0  # ramp complete
            return 1.0
        # Smooth ease-in curve (quadratic)
        t = elapsed / self._play_ramp_duration
        return t * t

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
        tau_decay = base_tau * 1.5
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
            self._capture_keepalive_deadline = 0.0
            self._stop_worker()

    def ensure_started(self) -> None:
        try:
            if not self._audio_worker.is_running():
                self._audio_worker.start()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to start audio worker in shared engine", exc_info=True)

    def force_stop(self) -> None:
        """Unconditionally stop the audio worker regardless of ref count.
        
        Called during application shutdown to ensure audio capture threads
        are terminated and the process can exit cleanly.
        """
        self.cancel_pending_compute_tasks()
        self._replace_runtime_buffers()
        self._latest_bars = [0.0] * self._bar_count
        self._smoothed_bars = [0.0] * self._bar_count
        self._last_audio_ts = 0.0
        self._waveform = [0.0] * 256
        self._waveform_count = 0
        self._idle_wave_phase = 0.0
        self._ref_count = 0
        self._capture_keepalive_deadline = 0.0
        self._stop_worker()

    def _stop_worker(self) -> None:
        try:
            self._audio_worker.stop()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to stop audio worker in shared engine", exc_info=True)

    def _schedule_worker_stop_after_grace(self) -> None:
        grace = max(0.0, float(self._capture_keepalive_grace))
        if self._ref_count <= 0 or grace <= 0.0:
            self._capture_keepalive_deadline = 0.0
            self._stop_worker()
            return
        self._capture_keepalive_deadline = time.time() + grace
        logger.debug(
            "[SPOTIFY_VIS] Keeping audio capture warm for %.1fs after playback pause",
            grace,
        )

    def _expire_capture_keepalive_if_needed(self, now_ts: float) -> None:
        deadline = float(self._capture_keepalive_deadline or 0.0)
        if deadline <= 0.0 or self._is_spotify_playing:
            return
        if now_ts < deadline:
            return
        self._capture_keepalive_deadline = 0.0
        logger.debug("[SPOTIFY_VIS] Warm capture grace expired; stopping audio worker")
        self._stop_worker()

    def _schedule_compute_bars_task(self, samples: object) -> None:
        tm = self._thread_manager
        if tm is None:
            return

        self._compute_task_active = True
        token = self._compute_gate_token
        activation_id = self._activation_id
        
        smoothed_copy = list(self._smoothed_bars)
        last_smooth_ts = self._last_smooth_ts
        smoothing_tau = self._smoothing_tau
        bar_count = self._bar_count
        hysteresis = self._segment_hysteresis
        min_change = self._min_change_threshold

        def _job(local_samples=samples):
            """FFT + smoothing on COMPUTE pool - keeps UI thread free."""
            try:
                worker_state = self._audio_worker.make_compute_snapshot()
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to snapshot audio worker for compute", exc_info=True)
                return None
            from widgets.spotify_visualizer.bar_computation import compute_bars_from_samples

            raw_bars = compute_bars_from_samples(worker_state, local_samples)
            if not isinstance(raw_bars, list):
                return None
            
            now_ts = time.time()
            dt = max(0.0, now_ts - last_smooth_ts) if last_smooth_ts >= 0.0 else 0.0
            
            if dt > 2.0 or dt <= 0.0:
                return {
                    'raw': raw_bars,
                    'smoothed': list(raw_bars),
                    'ts': now_ts,
                    'reset': True,
                    'energy': extract_energy_bands(raw_bars),
                    'worker_state': worker_state,
                    'activation_id': activation_id,
                }
            
            base_tau = smoothing_tau
            tau_rise = base_tau * 0.35
            tau_decay = base_tau * 1.5
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
            
            # Extract energy bands from smoothed bars
            energy = extract_energy_bands(smoothed)
            return {
                'raw': raw_bars,
                'smoothed': smoothed,
                'ts': now_ts,
                'energy': energy,
                'worker_state': worker_state,
                'activation_id': activation_id,
            }

        def _on_result(result) -> None:
            try:
                if token != self._compute_gate_token or activation_id != self._activation_id:
                    return
                self._compute_task_active = False
                success = getattr(result, "success", True)
                data = getattr(result, "result", None)
                if not success or data is None:
                    return
                if data.get('activation_id') != self._activation_id:
                    return
                raw_bars = data.get('raw')
                smoothed_bars = data.get('smoothed')
                ts = data.get('ts', time.time())
                worker_state = data.get('worker_state')
                if worker_state is not None:
                    try:
                        self._audio_worker.commit_compute_snapshot(worker_state)
                    except Exception:
                        logger.debug("[SPOTIFY_VIS] Failed to commit audio worker compute state", exc_info=True)
                if isinstance(raw_bars, list):
                    self._bars_result_buffer.publish(raw_bars)
                    self._latest_bars = raw_bars
                if isinstance(smoothed_bars, list):
                    self._smoothed_bars = smoothed_bars
                    self._last_smooth_ts = ts
                    self._latest_generation_with_frame = self._generation_id
                energy = data.get('energy')
                if isinstance(energy, EnergyBands):
                    self._energy_bands = energy
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
            if token == self._compute_gate_token:
                self._compute_task_active = False

    def get_generation_id(self) -> int:
        return self._generation_id

    def get_activation_id(self) -> int:
        return self._activation_id

    def get_latest_generation_with_frame(self) -> int:
        return self._latest_generation_with_frame

    def get_latest_generation_with_waveform(self) -> int:
        return self._latest_generation_with_waveform

    def tick(self) -> Optional[List[float]]:
        tm = self._thread_manager

        now_ts = time.time()
        self._expire_capture_keepalive_if_needed(now_ts)
        # While paused, visuals stay on the idle path even if the capture worker
        # is still inside its short warm-grace window.
        if not self._is_spotify_playing:
            self._update_idle_waveform(now_ts)
            self._prime_idle_bars(now_ts)
        frame = self._audio_buffer.consume_latest()
        if frame is not None:
            frame_activation = getattr(frame, "activation_id", None)
            if isinstance(frame_activation, int) and frame_activation != self._activation_id:
                logger.debug(
                    "[SPOTIFY_VIS] Dropped stale audio frame activation=%s current=%s",
                    frame_activation,
                    self._activation_id,
                )
                frame = None

        if frame is not None:
            samples = getattr(frame, "samples", None)
            if samples is not None:
                try:
                    self._last_audio_ts = now_ts
                except Exception as e:
                    logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

                # Extract waveform for oscilloscope (last 256 samples)
                try:
                    if np is not None and hasattr(samples, '__len__'):
                        arr = np.asarray(samples, dtype='float32').ravel()
                        n = len(arr)
                        if n >= 256:
                            self._waveform = arr[-256:].tolist()
                            self._waveform_count = 256
                        elif n > 0:
                            pad = [0.0] * (256 - n)
                            self._waveform = arr.tolist() + pad
                            self._waveform_count = n
                        if n > 0:
                            self._latest_generation_with_waveform = self._generation_id
                except Exception:
                    pass
            
                if not self._is_spotify_playing:
                    if self._latest_bars is None or len(self._latest_bars) != self._bar_count:
                        self._prime_idle_bars(now_ts)
                    return self._latest_bars
                
                if tm is not None:
                    if not self._compute_task_active:
                        self._schedule_compute_bars_task(samples)
                else:
                    worker_state = self._audio_worker.make_compute_snapshot()
                    from widgets.spotify_visualizer.bar_computation import compute_bars_from_samples

                    bars_inline = compute_bars_from_samples(worker_state, samples)
                    if isinstance(bars_inline, list):
                        self._audio_worker.commit_compute_snapshot(worker_state)
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
        if self._is_spotify_playing and last_ts > 0.0:
            try:
                silence_elapsed = now_ts - last_ts
                if silence_elapsed >= 0.3:
                    # Gradually decay bars toward zero during silence
                    decay_alpha = min(1.0, silence_elapsed * 2.5)  # full zero by ~0.7s
                    if isinstance(self._latest_bars, list) and self._bar_count > 0:
                        for i in range(len(self._latest_bars)):
                            if self._latest_bars[i] > 0.0:
                                self._latest_bars[i] *= max(0.0, 1.0 - decay_alpha)
                                if self._latest_bars[i] < 0.005:
                                    self._latest_bars[i] = 0.0
                    # Also decay smoothed bars so the UI actually sees the drop
                    if isinstance(self._smoothed_bars, list):
                        for i in range(len(self._smoothed_bars)):
                            if self._smoothed_bars[i] > 0.0:
                                self._smoothed_bars[i] *= max(0.0, 1.0 - decay_alpha)
                                if self._smoothed_bars[i] < 0.005:
                                    self._smoothed_bars[i] = 0.0
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

        return self._latest_bars

    def _update_idle_waveform(self, now_ts: float) -> None:
        """Generate a subtle synthetic waveform for paused idle rendering."""
        count = 256
        phase = now_ts * 0.62
        out: list[float] = [0.0] * count
        for i in range(count):
            x = float(i) / float(max(1, count - 1))
            slow = math.sin((x * 2.0 * math.pi * 1.2) + phase)
            mid = math.sin((x * 2.0 * math.pi * 2.7) - (phase * 0.8))
            fine = math.sin((x * 2.0 * math.pi * 5.1) + (phase * 1.4))
            out[i] = float((slow * 0.035) + (mid * 0.022) + (fine * 0.010))
        self._waveform = out
        self._waveform_count = count
        self._latest_generation_with_waveform = self._generation_id

    def _prime_idle_bars(self, now_ts: float) -> None:
        """Generate a low-energy multi-bar idle presentation while paused."""
        count = max(1, int(self._bar_count))
        phase = now_ts * 0.43
        bars: list[float] = [0.0] * count
        denom = float(max(1, count - 1))
        for i in range(count):
            x = float(i) / denom
            center_env = 1.0 - abs((x * 2.0) - 1.0)
            center_env = max(0.0, center_env)
            wave_a = 0.5 + 0.5 * math.sin((x * math.tau * 1.4) + phase)
            wave_b = 0.5 + 0.5 * math.sin((x * math.tau * 2.2) - (phase * 0.7))
            bars[i] = 0.010 + center_env * 0.012 + wave_a * 0.008 + wave_b * 0.004

        if count == 1:
            bars[0] = max(bars[0], 0.028)

        self._latest_bars = list(bars)
        self._smoothed_bars = list(bars)
        self._energy_bands = extract_energy_bands(bars)
    
    def get_smoothed_bars(self) -> List[float]:
        """Get pre-smoothed bars for UI display.

        During the reactivity ramp-up window after play detection, bars are
        scaled by a gentle ease-in factor to mask AGC warmup artifacts.
        """
        ramp = self._get_play_ramp_factor()
        if ramp >= 1.0:
            return list(self._smoothed_bars)
        return [v * ramp for v in self._smoothed_bars]

    def get_waveform(self) -> List[float]:
        """Get the last 256 raw waveform samples for oscilloscope."""
        return list(self._waveform)

    def get_waveform_count(self) -> int:
        """Get the valid sample count in the waveform buffer."""
        try:
            return max(0, min(256, int(self._waveform_count)))
        except Exception:
            return 0

    def get_energy_bands(self) -> EnergyBands:
        """Get the latest frequency-band energy snapshot.

        Scaled by the reactivity ramp factor during AGC warmup.
        """
        ramp = self._get_play_ramp_factor()
        if ramp >= 1.0:
            return self._energy_bands
        eb = self._energy_bands
        return EnergyBands(
            bass=eb.bass * ramp, mid=eb.mid * ramp,
            high=eb.high * ramp, overall=eb.overall * ramp,
        )

    def get_raw_energy_bands(self) -> EnergyBands:
        """Get energy bands from the latest RAW (unsmoothed) bars.

        Unlike get_energy_bands() which uses smoothed bars, this uses
        _latest_bars directly so bass transients from kicks/drums are sharp.
        """
        raw = self._latest_bars
        if raw:
            return extract_energy_bands(raw)
        return self._energy_bands

    def get_pre_agc_energy_bands(self) -> EnergyBands:
        """Get energy bands computed BEFORE AGC normalization.

        Post-noise-floor, pre-normalization values that preserve full dynamic
        range.  Modes that need true loudness variance should
        use these instead of post-AGC bar-derived energy.

        Scaled by the reactivity ramp factor during AGC warmup.
        """
        w = self._audio_worker
        ramp = self._get_play_ramp_factor()
        bass = getattr(w, '_pre_agc_control_bass', getattr(w, '_pre_agc_bass', 0.0)) * ramp
        mid = getattr(w, '_pre_agc_control_mid', getattr(w, '_pre_agc_mid', 0.0)) * ramp
        high = getattr(w, '_pre_agc_control_treble', getattr(w, '_pre_agc_treble', 0.0)) * ramp
        bass = max(0.0, min(1.0, float(bass)))
        mid = max(0.0, min(1.0, float(mid)))
        high = max(0.0, min(1.0, float(high)))
        overall = max(0.0, min(1.0, (bass * 0.5 + mid * 0.3 + high * 0.2)))
        return EnergyBands(bass=bass, mid=mid, high=high, overall=overall)

    def get_bubble_energy_bands(self) -> EnergyBands:
        """Return Bubble's support-aware continuous energy feed.

        Bubble's live motion contract is more sensitive to flattened control
        lanes than other modes. It still consumes a bounded 0..1 signal, but
        that signal must be derived primarily from the raw band authority that
        survives gate-floor subtraction, with only a light stabilizing blend
        from the shared control lane.
        """
        w = self._audio_worker
        ramp = self._get_play_ramp_factor()
        floor_snapshot = self.get_floor_snapshot()
        dynamic_enabled = bool(floor_snapshot.get("dynamic_enabled", True))
        support_pressure = max(0.0, min(1.0, float(floor_snapshot.get("support_pressure", 0.0) or 0.0)))

        try:
            raw_bass_avg = max(0.10, float(getattr(w, "_raw_bass_avg", 0.10) or 0.10))
        except Exception:
            raw_bass_avg = 0.10

        def _raw(name: str, fallback_name: str) -> float:
            return max(0.0, float(getattr(w, name, getattr(w, fallback_name, 0.0)) or 0.0))

        def _control(name: str) -> float:
            return max(0.0, min(1.0, float(getattr(w, name, 0.0) or 0.0)))

        def _clamp01(value: float) -> float:
            return max(0.0, min(1.0, float(value)))

        def _hot_phase(raw_value: float) -> float:
            return _clamp01((raw_value - 0.85) / 0.40)

        def _hot_lift(raw_value: float) -> float:
            return soft_ceiling(
                max(0.0, raw_value - 0.85),
                knee=0.0,
                ceiling=0.56,
                max_input=1.80,
                curve=0.96,
            )

        def _shape(raw_value: float, control_value: float, *, denom: float, knee: float, ceiling: float) -> float:
            raw_mix = 0.72
            if dynamic_enabled:
                raw_mix += support_pressure * 0.14
            raw_mix = max(0.72, min(0.88, raw_mix))
            normalized = max(0.0, raw_value / max(0.10, denom))
            shaped = soft_ceiling(
                normalized,
                knee=knee,
                ceiling=ceiling,
                max_input=2.80,
                curve=1.10,
            )
            blended = control_value * (1.0 - raw_mix) + shaped * raw_mix
            if dynamic_enabled and support_pressure > 0.0:
                blended += support_pressure * 0.06
            return max(0.0, min(1.0, blended * ramp))

        raw_bass = _raw("_last_raw_bass", "_pre_agc_live_bass")
        control_bass = _control("_pre_agc_control_bass")
        raw_mid = _raw("_last_raw_mid", "_pre_agc_live_mid")
        control_mid = _control("_pre_agc_control_mid")
        raw_high = _raw("_last_raw_treble", "_pre_agc_live_treble")
        control_high = _control("_pre_agc_control_treble")
        hot_phase = _hot_phase(raw_bass)
        hot_lift = _hot_lift(raw_bass)
        support_carry = min(0.04, support_pressure * max(0.008, 0.04 - hot_phase * 0.032))
        raw_presence = soft_ceiling(
            raw_mid / max(0.24, raw_bass_avg * 1.65),
            knee=0.08,
            ceiling=0.10,
            max_input=1.50,
            curve=1.00,
        )
        presence_carry = min(
            0.16,
            raw_presence
            + control_mid * 0.06
            + control_high * 0.025,
        )
        if dynamic_enabled:
            body = soft_ceiling(
                raw_bass / max(0.26, raw_bass_avg * 2.10),
                knee=0.12,
                ceiling=0.20,
                max_input=1.40,
                curve=1.00,
            )
            warm_support = soft_ceiling(
                raw_bass / max(0.24, raw_bass_avg * 1.30),
                knee=0.10,
                ceiling=0.16,
                max_input=2.20,
                curve=1.02,
            ) * (1.0 - hot_phase * 0.78)
            bass = (
                body * 0.42
                + warm_support * 0.18
                + hot_lift
                + presence_carry * 0.16
                + min(0.045, control_bass * 0.06)
                + support_carry
            )
            bass = _clamp01(bass * ramp)
        else:
            # Manual-floor Bubble should read loud sections from absolute bass
            # authority, not from a moving average that can flatten the hero
            # branch back into the same bucket as soft passages.
            absolute_body = soft_ceiling(
                raw_bass / 2.70,
                knee=0.14,
                ceiling=0.22,
                max_input=1.10,
                curve=0.98,
            )
            normalized_support = soft_ceiling(
                raw_bass / max(0.22, raw_bass_avg * 2.40),
                knee=0.10,
                ceiling=0.12,
                max_input=1.80,
                curve=1.00,
            ) * (1.0 - hot_phase * 0.72)
            control_support = min(0.035, control_bass * 0.06)
            bass = (
                absolute_body * 0.56
                + normalized_support * 0.18
                + hot_lift * 1.02
                + presence_carry * 0.22
                + control_support
            )
            bass = _clamp01(bass * ramp)
        mid = _shape(
            raw_mid,
            control_mid,
            denom=raw_bass_avg * 1.48,
            knee=0.20,
            ceiling=0.96,
        )
        high = _shape(
            raw_high,
            control_high,
            denom=raw_bass_avg * 1.98,
            knee=0.16,
            ceiling=0.92,
        )
        mid_presence = min(0.12, presence_carry * (0.26 + hot_phase * 0.44) + support_carry * 0.40)
        high_presence = min(0.07, presence_carry * (0.10 + hot_phase * 0.22) + support_carry * 0.18)
        mid = max(mid, mid_presence * ramp)
        high = max(high, high_presence * ramp)
        overall = _clamp01(
            bass * 0.44
            + mid * 0.34
            + high * 0.22
            + hot_phase * presence_carry * 0.10
        )
        return EnergyBands(bass=bass, mid=mid, high=high, overall=overall)

    def get_floor_snapshot(self) -> dict:
        """Return the latest shared floor state for consumers that need context.

        The continuous energy bands remain the source of truth; this snapshot is
        just the shaping context that produced them. Modes like Blob can use it
        to distinguish real sustained support from temporarily elevated floor
        pressure without inventing their own settings path.
        """
        w = self._audio_worker
        try:
            dynamic_enabled = bool(getattr(w, '_use_dynamic_floor', True))
        except Exception:
            dynamic_enabled = True
        try:
            manual_floor = float(getattr(w, '_manual_floor', 0.12) or 0.12)
        except Exception:
            manual_floor = 0.12
        try:
            gate_floor = float(getattr(w, '_gate_floor', getattr(w, '_applied_noise_floor', manual_floor)) or manual_floor)
        except Exception:
            gate_floor = manual_floor
        try:
            last_noise_floor = float(getattr(w, '_last_noise_floor', gate_floor) or gate_floor)
        except Exception:
            last_noise_floor = gate_floor
        try:
            support_pressure = float(getattr(w, '_support_pressure', 0.0) or 0.0)
        except Exception:
            support_pressure = 0.0

        manual_floor = max(0.0, min(1.0, manual_floor))
        gate_floor = max(0.0, min(1.0, gate_floor))
        last_noise_floor = max(0.0, min(1.0, last_noise_floor))
        return {
            'dynamic_enabled': dynamic_enabled,
            'manual_floor': manual_floor,
            'gate_floor': gate_floor,
            'last_noise_floor': last_noise_floor,
            'support_pressure': max(0.0, min(1.0, support_pressure if dynamic_enabled else 0.0)),
        }

    def get_transient_energy_bands(self) -> TransientEnergyBands:
        """Get the latest transient bus snapshot (fast-path, 1-frame latency).

        Returns per-band transient energy and onset detection state.
        Used by modes that need immediate beat response (Spectrum kick lane,
        Bubble pulse, Blob deform) without waiting for smoothing/AGC.
        """
        w = self._audio_worker
        return TransientEnergyBands(
            bass_transient=getattr(w, '_transient_bass', 0.0),
            mid_transient=getattr(w, '_transient_mid', 0.0),
            high_transient=getattr(w, '_transient_high', 0.0),
            onset_detected=getattr(w, '_onset_detected', False),
            onset_type=getattr(w, '_onset_type', ''),
            onset_strength=getattr(w, '_onset_strength', 0.0),
        )

    def get_event_scheduler(self) -> "TransientEventScheduler | None":
        """Return the event micro-scheduler (§2.4) if the transient bus exists.

        The scheduler is lazily created on the transient bus; calling this
        ensures it is initialized.  Returns None only if the audio worker
        has no transient bus (shouldn't happen in normal operation).
        """
        _tb = getattr(self._audio_worker, '_transient_bus', None)
        if _tb is not None:
            return _tb.get_scheduler()
        return None

    def wake(self) -> None:
        """Force wake after pause detection - restart audio capture if unhealthy."""
        logger.debug("[SPOTIFY_VIS] Beat engine wake triggered")
        try:
            # Check audio capture health via audio worker
            if hasattr(self._audio_worker, 'is_capture_healthy'):
                if not self._audio_worker.is_capture_healthy():
                    logger.info("[SPOTIFY_VIS] Audio capture unhealthy, restarting...")
                    self._audio_worker.restart_capture()
            
            # Reset smoothing timestamp to prevent dt>2.0 jump
            self._last_smooth_ts = time.time()
            
            # Ensure worker is running
            self.ensure_started()
            
        except Exception:
            logger.debug("[SPOTIFY_VIS] Wake failed", exc_info=True)


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
        self._engine: Optional[_SpotifyBeatEngine] = None
    
    @classmethod
    def get_instance(cls) -> "BeatEngineRegistry":
        """Get singleton registry instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def get_engine(self, bar_count: int) -> _SpotifyBeatEngine:
        """Get the shared engine, rebuilding bar-count-dependent state if needed."""
        bar_count = max(1, int(bar_count))
        if self._engine is None:
            self._engine = _SpotifyBeatEngine(bar_count)
        else:
            self._engine.reconfigure_bar_count(bar_count)
        return self._engine

    def set_engine(self, bar_count: int, engine: _SpotifyBeatEngine) -> None:
        """Inject a custom engine (for testing)."""
        try:
            engine.reconfigure_bar_count(bar_count)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Injected engine could not reconfigure to requested bar count", exc_info=True)
        self._engine = engine

    def clear(self) -> None:
        """Clear all engines (for testing)."""
        if self._engine is not None:
            try:
                self._engine.force_stop()
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to stop shared beat engine during registry clear", exc_info=True)
        self._engine = None


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
    _global_beat_engine = engine
    return engine
