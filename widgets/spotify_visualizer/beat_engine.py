"""Spotify Beat Engine - Shared beat engine with integrated smoothing.

This module contains the _SpotifyBeatEngine class which handles:
- Shared audio buffer management
- FFT computation scheduling on compute pool
- Pre-smoothing of bar heights to reduce UI thread work
- Playback state gating for FFT processing
"""

from __future__ import annotations

from typing import List, Optional, Sequence
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


def _smooth_analysis_bars(
    raw_bars: Sequence[float],
    previous_bars: Sequence[float],
    prior_timestamp: float,
    current_timestamp: float,
    *,
    bar_count: int,
    smoothing_tau: float,
    segment_hysteresis: float,
    min_change_threshold: float,
) -> tuple[List[float], bool, EnergyBands]:
    """Return the deterministic smoothing result for one analysis frame."""
    dt = (
        max(0.0, current_timestamp - prior_timestamp)
        if prior_timestamp >= 0.0
        else 0.0
    )
    if dt > 2.0 or dt <= 0.0:
        smoothed = list(raw_bars)
        return smoothed, True, extract_energy_bands(raw_bars)

    tau_rise = smoothing_tau * 0.35
    tau_decay = smoothing_tau * 1.5
    alpha_rise = 1.0 - math.exp(-dt / tau_rise)
    alpha_decay = 1.0 - math.exp(-dt / tau_decay)
    alpha_rise = max(0.0, min(1.0, alpha_rise))
    alpha_decay = max(0.0, min(1.0, alpha_decay))

    smoothed: List[float] = []
    for i in range(bar_count):
        cur = previous_bars[i] if i < len(previous_bars) else 0.0
        tgt = raw_bars[i] if i < len(raw_bars) else 0.0

        delta = abs(tgt - cur)
        if delta < min_change_threshold:
            smoothed.append(cur)
            continue

        if tgt > cur:
            tgt_adjusted = tgt + segment_hysteresis
        elif tgt < cur:
            tgt_adjusted = tgt - segment_hysteresis
        else:
            tgt_adjusted = tgt

        tgt_adjusted = max(0.0, min(1.0, tgt_adjusted))
        alpha = alpha_rise if tgt_adjusted >= cur else alpha_decay
        nxt = cur + (tgt_adjusted - cur) * alpha
        if abs(nxt) < 1e-3:
            nxt = 0.0
        smoothed.append(nxt)

    return smoothed, False, extract_energy_bands(smoothed)


_PLAY_RAMP_DURATION_S = 1.0


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
        # Latest-state freshness under a one-in-flight compute contract.
        #
        # A tick that consumed the newest audio frame while a compute was
        # already running used to simply drop it, so the next analysis could
        # only start from whatever a LATER tick happened to consume. That is
        # the upstream source age the operator perceives as lateness.
        #
        # At most one source frame may wait, and a newer frame REPLACES it.
        # This is not a queue: intermediate frames are never replayed.
        self._pending_analysis_samples: object = None
        self._pending_analysis_activation: int = -1
        self._pending_analysis_capture_ts: float = 0.0
        self._thread_manager: Optional[ThreadManager] = None
        self._ref_count: int = 0
        self._latest_bars: Optional[List[float]] = None
        self._last_audio_ts: float = 0.0
        self._generation_id: int = 0
        self._activation_id: int = 0
        # One target activation may need several preparation steps (bar-count
        # resize, smoothing reset, floor/waveform reset, technical config).
        # While a transaction is open they all defer their generation bump to
        # one final commit, so a single mode/preset activation produces exactly
        # one authoritative generation that consumers can gate a fresh frame on.
        self._activation_txn_depth: int = 0
        self._activation_txn_pending: bool = False
        self._latest_generation_with_frame: int = 0
        self._latest_generation_with_waveform: int = 0
        # Diagnostic provenance for the latest committed analysis frame.
        # ``_last_smooth_ts`` is also adjusted by wake/idle protection, so it
        # is not authoritative enough for latency accounting on its own.
        self._latest_authoritative_frame_ts: float = 0.0
        self._latest_authoritative_frame_generation: int = -1
        self._latest_authoritative_frame_activation: int = -1

        # Waveform buffer for oscilloscope visualizer (last 256 raw samples)
        self._waveform: List[float] = [0.0] * 256
        self._waveform_count: int = 256

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
        self._play_ramp_duration: float = _PLAY_RAMP_DURATION_S  # fresh-source fencing owns staleness safety
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

    # ------------------------------------------------------------------
    # Activation transaction
    # ------------------------------------------------------------------

    def begin_activation_transaction(self) -> None:
        """Open a target-activation transaction.

        Every preparation step performed until the matching
        ``end_activation_transaction`` records that a new generation is owed
        instead of advancing one itself. Nested opens are counted, so a helper
        that opens its own transaction inside an outer one cannot commit early.
        """
        self._activation_txn_depth += 1

    def end_activation_transaction(self, *, reason: str = "activation") -> int:
        """Close the transaction and commit at most ONE generation.

        Returns the current activation id. A transaction that prepared nothing
        commits nothing, so an inert apply cannot churn the generation.
        """
        if self._activation_txn_depth > 0:
            self._activation_txn_depth -= 1
        if self._activation_txn_depth > 0:
            return self._activation_id
        if self._activation_txn_pending:
            self._activation_txn_pending = False
            self._commit_activation_generation(reason=reason)
        return self._activation_id

    def in_activation_transaction(self) -> bool:
        return self._activation_txn_depth > 0

    def _advance_activation_generation(self, *, reason: str) -> None:
        """Advance now, or record that the open transaction owes a commit."""
        if self._activation_txn_depth > 0:
            self._activation_txn_pending = True
            return
        self._commit_activation_generation(reason=reason)

    def _commit_activation_generation(self, *, reason: str) -> None:
        """The single place a runtime generation/activation boundary exists.

        Consumers gate their first fresh frame on this identity, so there must
        be no intermediate target generation capable of publishing or revealing.
        """
        self._generation_id += 1
        self._activation_id += 1
        self._audio_worker._activation_id = self._activation_id
        # Force consumers to wait for the next result produced AFTER this
        # boundary instead of reusing the pre-boundary generation id.
        self._latest_generation_with_frame = self._generation_id - 1
        self._latest_generation_with_waveform = self._generation_id - 1
        self._latest_authoritative_frame_ts = 0.0
        self._latest_authoritative_frame_generation = -1
        self._latest_authoritative_frame_activation = -1
        logger.debug(
            "[SPOTIFY_VIS] Beat engine activation committed reason=%s "
            "(generation=%d activation=%d bars=%d)",
            reason,
            self._generation_id,
            self._activation_id,
            self._bar_count,
        )

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
        self._advance_activation_generation(reason="bar_count=%d" % new_count)
    
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
        self._advance_activation_generation(reason="smoothing_reset")

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
        # A pending source frame belongs to the activation that consumed it.
        self._discard_pending_analysis_frame()

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
        smoothed, _reset, _energy = _smooth_analysis_bars(
            target_bars,
            self._smoothed_bars,
            self._last_smooth_ts,
            now_ts,
            bar_count=self._bar_count,
            smoothing_tau=self._smoothing_tau,
            segment_hysteresis=self._segment_hysteresis,
            min_change_threshold=self._min_change_threshold,
        )
        self._smoothed_bars = smoothed
        return self._smoothed_bars
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

    def _replace_pending_analysis_frame(
        self, samples: object, *, capture_ts: float
    ) -> None:
        """Keep only the NEWEST source frame while a compute is in flight.

        Replacement, never append. A backlog would make the visualizer render
        progressively older audio, and catch-up replay of the intermediate
        frames is explicitly forbidden.
        """
        self._pending_analysis_samples = samples
        self._pending_analysis_activation = self._activation_id
        self._pending_analysis_capture_ts = float(capture_ts or 0.0)

    def _discard_pending_analysis_frame(self) -> None:
        self._pending_analysis_samples = None
        self._pending_analysis_activation = -1
        self._pending_analysis_capture_ts = 0.0

    def has_pending_analysis_frame(self) -> bool:
        return self._pending_analysis_samples is not None

    def _launch_pending_analysis_frame(self) -> None:
        """Start the single newest still-valid pending frame, if any.

        Called once a compute result has finished committing its DSP/worker
        state, so the next analysis continues from correct state rather than
        from a snapshot taken before the previous result landed.

        A pending frame from a superseded activation is discarded, not run:
        generation/activation replacement fences the input as well as the
        output.
        """
        samples = self._pending_analysis_samples
        if samples is None:
            return
        activation = self._pending_analysis_activation
        capture_ts = self._pending_analysis_capture_ts
        self._discard_pending_analysis_frame()
        if activation != self._activation_id:
            logger.debug(
                "[SPOTIFY_VIS] Dropped pending analysis frame activation=%s current=%s",
                activation,
                self._activation_id,
            )
            return
        if self._compute_task_active:
            # Something already claimed the single in-flight slot; put the
            # frame back rather than running two computes.
            self._replace_pending_analysis_frame(samples, capture_ts=capture_ts)
            return
        if self._thread_manager is None:
            return
        self._schedule_compute_bars_task(samples, capture_ts=capture_ts)

    def _schedule_compute_bars_task(
        self, samples: object, *, capture_ts: float = 0.0
    ) -> None:
        tm = self._thread_manager
        if tm is None:
            return

        self._compute_task_active = True
        token = self._compute_gate_token
        activation_id = self._activation_id
        source_capture_ts = float(capture_ts or 0.0)
        
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
            smoothed, reset, energy = _smooth_analysis_bars(
                raw_bars,
                smoothed_copy,
                last_smooth_ts,
                now_ts,
                bar_count=bar_count,
                smoothing_tau=smoothing_tau,
                segment_hysteresis=hysteresis,
                min_change_threshold=min_change,
            )
            return {
                'raw': raw_bars,
                'smoothed': smoothed,
                'ts': now_ts,
                'reset': reset,
                'energy': energy,
                'worker_state': worker_state,
                'activation_id': activation_id,
                'capture_ts': source_capture_ts,
            }

        def _on_result(result) -> None:
            try:
                if token != self._compute_gate_token or activation_id != self._activation_id:
                    # Superseded generation/activation: the in-flight slot and
                    # any pending source belong to the current owner now.
                    return
                self._compute_task_active = False
                try:
                    success = getattr(result, "success", True)
                    data = getattr(result, "result", None)
                    if not success or data is None:
                        return
                    if data.get('activation_id') != self._activation_id:
                        return
                    self._commit_analysis_frame(
                        raw_bars=data.get('raw'),
                        smoothed_bars=data.get('smoothed'),
                        timestamp=data.get('ts', time.time()),
                        activation_id=data.get('activation_id'),
                        worker_state=data.get('worker_state'),
                        energy=data.get('energy'),
                    )
                finally:
                    # The required DSP/worker state has committed (or this
                    # result failed and committed nothing). Either way the
                    # slot is free, so the newest pending source frame starts
                    # immediately instead of waiting for the next tick.
                    self._launch_pending_analysis_frame()
            except Exception:
                logger.debug("[SPOTIFY_VIS] compute task callback failed", exc_info=True)

        try:
            tm.submit_compute_task(
                _job,
                callback=_on_result,
                category="visualizer.audio_analysis",
            )
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            if token == self._compute_gate_token:
                self._compute_task_active = False

    def _commit_analysis_frame(
        self,
        *,
        raw_bars: object,
        smoothed_bars: object,
        timestamp: object,
        activation_id: object,
        worker_state: object = None,
        energy: object = None,
        waveform: Optional[List[float]] = None,
        waveform_count: Optional[int] = None,
        audio_timestamp: Optional[float] = None,
    ) -> bool:
        """Publish one verified live or replay analysis frame."""
        if activation_id != self._activation_id:
            return False

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
            self._last_smooth_ts = float(timestamp)
            self._latest_generation_with_frame = self._generation_id
            self._latest_authoritative_frame_ts = float(timestamp)
            self._latest_authoritative_frame_generation = self._generation_id
            self._latest_authoritative_frame_activation = self._activation_id
        if isinstance(energy, EnergyBands):
            self._energy_bands = energy
        if waveform is not None:
            self._waveform = waveform
            self._waveform_count = int(waveform_count or 0)
            self._latest_generation_with_waveform = self._generation_id
        try:
            self._last_audio_ts = (
                time.time() if audio_timestamp is None else float(audio_timestamp)
            )
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        return True

    def accept_analysis_frame(
        self,
        raw_bars: object,
        timestamp: object,
        *,
        activation_id: object,
        waveform: object = None,
        waveform_count: object = None,
        worker_state: object = None,
        energy_override: object = None,
    ) -> bool:
        """Synchronously accept one timestamped analysis frame for replay."""
        if (
            not isinstance(activation_id, int)
            or isinstance(activation_id, bool)
            or activation_id != self._activation_id
        ):
            return False
        if not isinstance(raw_bars, list) or len(raw_bars) != self._bar_count:
            return False
        if (
            not isinstance(timestamp, (int, float))
            or isinstance(timestamp, bool)
            or not math.isfinite(float(timestamp))
            or float(timestamp) < 0.0
        ):
            return False
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0.0
            or float(value) > 1.0
            for value in raw_bars
        ):
            return False
        if energy_override is not None:
            if not isinstance(energy_override, EnergyBands):
                return False
            if any(
                not math.isfinite(float(value)) or value < 0.0 or value > 1.0
                for value in (
                    energy_override.bass,
                    energy_override.mid,
                    energy_override.high,
                    energy_override.overall,
                )
            ):
                return False

        normalized_waveform: Optional[List[float]] = None
        normalized_waveform_count: Optional[int] = None
        if waveform is not None:
            if not isinstance(waveform, (list, tuple)):
                return False
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in waveform
            ):
                return False
            waveform_values = [float(value) for value in waveform]
            sample_count = len(waveform_values)
            if waveform_count is None:
                normalized_waveform_count = min(256, sample_count)
            elif (
                not isinstance(waveform_count, int)
                or isinstance(waveform_count, bool)
                or waveform_count < 0
                or waveform_count > min(256, sample_count)
            ):
                return False
            else:
                normalized_waveform_count = waveform_count
            if sample_count >= 256:
                normalized_waveform = waveform_values[-256:]
            else:
                normalized_waveform = waveform_values + [0.0] * (256 - sample_count)
        elif waveform_count is not None:
            return False

        smoothed, _reset, energy = _smooth_analysis_bars(
            raw_bars,
            self._smoothed_bars,
            self._last_smooth_ts,
            float(timestamp),
            bar_count=self._bar_count,
            smoothing_tau=self._smoothing_tau,
            segment_hysteresis=self._segment_hysteresis,
            min_change_threshold=self._min_change_threshold,
        )
        return self._commit_analysis_frame(
            raw_bars=list(raw_bars),
            smoothed_bars=smoothed,
            timestamp=float(timestamp),
            activation_id=activation_id,
            worker_state=worker_state,
            energy=energy if energy_override is None else energy_override,
            waveform=normalized_waveform,
            waveform_count=normalized_waveform_count,
            audio_timestamp=float(timestamp),
        )

    def get_generation_id(self) -> int:
        return self._generation_id

    def get_activation_id(self) -> int:
        return self._activation_id

    def get_latest_generation_with_frame(self) -> int:
        return self._latest_generation_with_frame

    def get_latest_authoritative_frame(self) -> tuple[float, int, int]:
        """Return timestamp, generation and activation of the last committed frame."""
        return (
            self._latest_authoritative_frame_ts,
            self._latest_authoritative_frame_generation,
            self._latest_authoritative_frame_activation,
        )

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
            try:
                # Drain one warm-grace frame without accepting it as visual
                # waveform authority; otherwise paused oscilloscope can render
                # stale live PCM until the capture stream dries up.
                self._audio_buffer.consume_latest()
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            return self._latest_bars
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
            try:
                frame_capture_ts = float(getattr(frame, "capture_ts", 0.0) or 0.0)
            except Exception:
                frame_capture_ts = 0.0
            if frame_capture_ts <= 0.0:
                frame_capture_ts = now_ts
            if samples is not None:
                try:
                    # Age is measured from capture, not from the tick that
                    # happened to consume the frame.
                    self._last_audio_ts = frame_capture_ts
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
                        self._schedule_compute_bars_task(
                            samples, capture_ts=frame_capture_ts
                        )
                    else:
                        # One compute in flight, one newest source frame
                        # waiting. Replacing rather than dropping is what
                        # keeps the next analysis on the freshest audio.
                        self._replace_pending_analysis_frame(
                            samples, capture_ts=frame_capture_ts
                        )
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
        try:
            prev_raw_bass = max(0.0, float(getattr(w, "_prev_raw_bass", 0.0) or 0.0))
        except Exception:
            prev_raw_bass = 0.0

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
        raw_rise = max(0.0, raw_bass - prev_raw_bass)
        hot_crest_lift = soft_ceiling(
            max(0.0, raw_rise - (0.05 if dynamic_enabled else 0.035)),
            knee=0.0,
            ceiling=0.11 if dynamic_enabled else 0.14,
            max_input=0.30,
            curve=1.0,
        ) * (0.30 + hot_phase * 0.70)
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
                + hot_crest_lift
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
                + hot_crest_lift * 1.18
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
        just the shaping context that produced them. Consumers can use it to
        distinguish real sustained support from temporarily elevated floor
        pressure without inventing another settings path.
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
        Bubble pulse) without waiting for smoothing/AGC.
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
        """Force wake after pause detection - restart audio capture only if stale."""
        logger.debug("[SPOTIFY_VIS] Beat engine wake triggered")
        try:
            # Only a capture that ran (or exceeded its first-callback allowance)
            # and then went quiet may be restarted. A stream that was just
            # started has no callback yet and must not be bounced by an
            # immediate wake.
            if hasattr(self._audio_worker, 'is_capture_stale'):
                if self._audio_worker.is_capture_stale():
                    logger.info("[SPOTIFY_VIS] Audio capture stale, restarting...")
                    self._audio_worker.restart_capture()
            elif hasattr(self._audio_worker, 'is_capture_healthy'):
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
