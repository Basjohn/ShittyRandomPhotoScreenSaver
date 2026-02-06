"""FFT-to-bars DSP pipeline for SpotifyVisualizerAudioWorker.

Extracted from spotify_visualizer_widget.py (M-4 refactor) to reduce monolith size.
Contains the core FFT→bar-heights conversion, noise floor management,
center-out frequency mapping, reactive smoothing, and adaptive normalization.
"""
from __future__ import annotations

import time
from typing import List, Optional, TYPE_CHECKING

from core.logging.logger import get_logger, is_verbose_logging
from core.process import WorkerType, MessageType

if TYPE_CHECKING:
    from widgets.spotify_visualizer_widget import SpotifyVisualizerAudioWorker

logger = get_logger(__name__)


def get_zero_bars(worker: "SpotifyVisualizerAudioWorker") -> List[float]:
    """Return cached zero bars list to avoid per-call allocation."""
    if worker._zero_bars is None or len(worker._zero_bars) != worker._bar_count:
        worker._zero_bars = [0.0] * worker._bar_count
    return worker._zero_bars


def process_via_fft_worker(
    worker: "SpotifyVisualizerAudioWorker", samples
) -> Optional[List[float]]:
    """Process audio samples using FFTWorker in separate process.

    Returns bar heights if successful, None if worker unavailable or failed.
    """
    if not worker._process_supervisor or not worker._fft_worker_available:
        return None

    if worker._fft_worker_failed_count >= worker._fft_worker_max_failures:
        return None

    try:
        if not worker._process_supervisor.is_running(WorkerType.FFT):
            worker._fft_worker_available = False
            return None

        samples_list = samples.tolist() if hasattr(samples, 'tolist') else list(samples)

        with worker._cfg_lock:
            use_recommended = bool(worker._use_recommended)
            user_sens = float(worker._user_sensitivity)
            use_dynamic_floor = bool(worker._use_dynamic_floor)

        sensitivity = user_sens if not use_recommended else 1.0

        correlation_id = worker._process_supervisor.send_message(
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
            worker._fft_worker_failed_count += 1
            return None

        start_time = time.time()
        timeout_s = 0.015

        while (time.time() - start_time) < timeout_s:
            responses = worker._process_supervisor.poll_responses(WorkerType.FFT, max_count=5)

            for response in responses:
                if response.correlation_id == correlation_id:
                    if response.success:
                        bars = response.payload.get("bars", [])
                        if bars and len(bars) > 0:
                            worker._fft_worker_failed_count = 0
                            return bars
                    else:
                        worker._fft_worker_failed_count += 1
                        return None

            time.sleep(0.001)

        return None

    except Exception as e:
        logger.debug("[SPOTIFY_VIS] FFTWorker processing error: %s", e)
        worker._fft_worker_failed_count += 1
        return None


def fft_to_bars(worker: "SpotifyVisualizerAudioWorker", fft) -> List[float]:
    """Convert FFT magnitudes to visualizer bar heights.

    Optimized to minimize per-frame allocations for reduced GC pressure.
    Uses pre-allocated buffers and in-place operations where possible.
    """
    np = worker._np
    if fft is None:
        return get_zero_bars(worker)

    bands = int(worker._bar_count)
    if bands <= 0:
        return []

    try:
        mag = fft[1:]
        if mag.size == 0:
            return get_zero_bars(worker)
        if np.iscomplexobj(mag):
            mag = np.abs(mag)
        mag = mag.astype("float32", copy=False)
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        return get_zero_bars(worker)

    n = int(mag.size)
    if n <= 0:
        return get_zero_bars(worker)
    resolution_boost = max(0.5, min(3.0, 1024.0 / max(256.0, float(n))))
    low_resolution = resolution_boost > 1.05

    try:
        np.log1p(mag, out=mag)
        np.power(mag, 1.2, out=mag)

        if n > 4:
            try:
                if worker._smooth_kernel is None:
                    worker._smooth_kernel = np.array([0.25, 0.5, 0.25], dtype="float32")
                mag = np.convolve(mag, worker._smooth_kernel, mode="same")
            except Exception as e:
                logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        return get_zero_bars(worker)

    # Center-out frequency mapping with logarithmic binning
    cache_key = (n, bands)
    prev_raw_bass = getattr(worker, "_prev_raw_bass", 0.0)
    bass_drop_ratio = 0.0
    drop_accum = getattr(worker, "_bass_drop_accum", 0.0)
    drop_signal = 0.0
    center = bands // 2
    try:
        if getattr(worker, "_band_cache_key", None) != cache_key:
            min_freq_idx = 1
            max_freq_idx = n

            log_edges = np.logspace(
                np.log10(min_freq_idx),
                np.log10(max_freq_idx),
                bands + 1,
                dtype="float32"
            ).astype("int32")

            worker._band_cache_key = cache_key
            worker._band_edges = log_edges
            worker._work_bars = np.zeros(bands, dtype="float32")
            worker._freq_values = np.zeros(bands, dtype="float32")
            worker._bar_history = np.zeros(bands, dtype="float32")
            worker._bar_hold_timers = np.zeros(bands, dtype="int32")

        edges = worker._band_edges
        if edges is None:
            return get_zero_bars(worker)

        arr = worker._work_bars
        arr.fill(0.0)
        freq_values = worker._freq_values
        freq_values.fill(0.0)

        # Compute RMS for each frequency band
        for b in range(bands):
            start = int(edges[b])
            end = int(edges[b + 1])
            if end <= start:
                end = start + 1
            if start < n and end <= n:
                band_slice = mag[start:end]
                if band_slice.size > 0:
                    freq_values[b] = np.sqrt(np.mean(band_slice ** 2))

        # Get raw energy values
        raw_bass = float(np.mean(freq_values[:4])) if bands >= 4 else float(freq_values[0])
        raw_mid = float(np.mean(freq_values[4:10])) if bands >= 10 else raw_bass * 0.5
        raw_treble = float(np.mean(freq_values[10:])) if bands > 10 else raw_bass * 0.2
        worker._last_raw_bass = raw_bass
        worker._last_raw_mid = raw_mid
        worker._last_raw_treble = raw_treble
        worker._prev_raw_bass = raw_bass
        if low_resolution and prev_raw_bass > 1e-3:
            bass_drop_ratio = max(0.0, (prev_raw_bass - raw_bass) / prev_raw_bass)

        # --- Noise floor and expansion computation ---
        noise_floor, expansion = _compute_noise_floor(
            worker, np, raw_bass, raw_mid, raw_treble,
            resolution_boost, low_resolution, drop_signal,
        )

        bass_energy = max(0.0, (raw_bass - noise_floor) * expansion)
        mid_energy = max(0.0, (raw_mid - noise_floor * 0.4) * expansion)
        treble_energy = max(0.0, (raw_treble - noise_floor * 0.2) * expansion)

        # CENTER-OUT MIRRORED LAYOUT
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

        overall_energy = (bass_energy * 0.9 + mid_energy * 0.6 + treble_energy * 0.35)
        overall_energy = max(0.0, min(1.8, overall_energy))

        # Apply shape template scaled by overall energy
        for i in range(bands):
            offset = abs(i - center)
            base = profile_shape[i] * overall_energy

            if offset == 3:
                base = base * 1.05 + bass_energy * 0.15
            elif offset == 4:
                base = base * 0.82

            if offset == 0:
                vocal_drive = mid_energy * 4.0
                base = vocal_drive * 0.90 + base * 0.10

            if offset == 1:
                base = base * 0.52 + mid_energy * 0.22
            if offset == 2:
                base = base * 0.58 + bass_energy * 0.12

            if offset >= 5:
                base = base * 0.65 + treble_energy * 0.4 * (offset - 4)

            arr[i] = base

        if low_resolution:
            _apply_low_resolution_adjustments(
                arr, bands, center, bass_drop_ratio, prev_raw_bass,
                raw_bass, noise_floor, drop_accum, np,
            )
            drop_signal = max(bass_drop_ratio, getattr(worker, "_bass_drop_accum", 0.0))
        else:
            drop_signal = bass_drop_ratio

        worker._bass_drop_accum = drop_accum if not low_resolution else getattr(worker, "_bass_drop_accum", 0.0)
        worker._last_bass_drop_ratio = drop_signal

    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        return get_zero_bars(worker)

    # REACTIVE SMOOTHING
    _apply_reactive_smoothing(worker, arr, bands, np)

    # Scale
    scale = (worker._base_output_scale or 0.8) * (worker._energy_boost or 1.0)
    if scale < 0.1:
        scale = 0.1
    elif scale > 1.25:
        scale = 1.25
    arr *= scale

    # Adaptive normalization
    _apply_adaptive_normalization(worker, arr, drop_signal, low_resolution, np)

    np.clip(arr, 0.0, 1.0, out=arr)

    # Sparse logging
    try:
        now = time.time()
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        now = 0.0
    last_snapshot = getattr(worker, "_bars_log_last_ts", 0.0)
    min_interval = max(1.0, float(getattr(worker, "_bars_log_interval", 5.0) or 5.0))
    if now <= 0.0 or (now - last_snapshot) >= min_interval:
        bar_str = " ".join(f"{v:.2f}" for v in arr)
        logger.info("[SPOTIFY_VIS][BARS] raw_bass=%.3f Bars=[%s]", float(raw_bass), bar_str)
        try:
            worker._bars_log_last_ts = now
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)

    return arr.tolist()


def _compute_noise_floor(
    worker: "SpotifyVisualizerAudioWorker",
    np,
    raw_bass: float,
    raw_mid: float,
    raw_treble: float,
    resolution_boost: float,
    low_resolution: bool,
    drop_signal: float,
) -> tuple:
    """Compute noise floor and expansion factor. Returns (noise_floor, expansion)."""
    noise_floor_base = max(0.8, 1.5 / (resolution_boost ** 0.35))
    expansion_base = 3.6 * (resolution_boost ** 0.4)

    try:
        with worker._cfg_lock:
            use_recommended = bool(worker._use_recommended)
            user_sens = float(worker._user_sensitivity)
            use_dynamic_floor = bool(worker._use_dynamic_floor)
            manual_floor = float(worker._manual_floor)
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
        auto_multiplier = float(getattr(worker, "_recommended_sensitivity_multiplier", 0.38))
        auto_multiplier = max(0.25, min(2.5, auto_multiplier))
        if resolution_boost > 1.0:
            damp = min(0.4, (resolution_boost - 1.0) * 0.55)
            auto_multiplier = max(0.25, auto_multiplier * (1.0 - damp))
        else:
            boost = min(0.25, (1.0 - resolution_boost) * 0.4)
            auto_multiplier = min(2.5, auto_multiplier * (1.0 + boost))
        base_noise_floor = max(
            worker._min_floor,
            min(worker._max_floor, noise_floor_base / auto_multiplier),
        )
        exp_factor = max(0.55, auto_multiplier ** 0.35)
        expansion = expansion_base * exp_factor
    else:
        base_noise_floor = max(worker._min_floor, min(worker._max_floor, noise_floor_base / user_sens))
        try:
            expansion = expansion_base * (user_sens ** 0.35)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            expansion = expansion_base

    target_floor = base_noise_floor
    mode = "dynamic" if use_dynamic_floor else "manual"
    if use_dynamic_floor:
        avg = getattr(worker, "_raw_bass_avg", base_noise_floor)
        try:
            floor_mid_weight = float(worker._floor_mid_weight)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            floor_mid_weight = 0.5
        floor_mid_weight = max(0.0, min(1.0, floor_mid_weight))
        if low_resolution:
            floor_mid_weight = min(0.65, floor_mid_weight + 0.12 * (resolution_boost - 1.0))
        floor_signal = (raw_bass * (1.0 - floor_mid_weight)) + (raw_mid * floor_mid_weight)
        try:
            silence_threshold = float(worker._silence_floor_threshold)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            silence_threshold = 0.0
        silence_threshold = max(0.0, silence_threshold)
        if floor_signal < silence_threshold:
            floor_signal = raw_bass
        try:
            alpha_rise = float(worker._dynamic_floor_alpha)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            alpha_rise = 0.05
        try:
            alpha_decay = float(worker._dynamic_floor_decay_alpha)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            alpha_decay = alpha_rise
        alpha_rise = max(0.0, min(1.0, alpha_rise))
        alpha_decay = max(0.0, min(1.0, alpha_decay))
        alpha = alpha_rise if floor_signal >= avg else alpha_decay
        avg = (1.0 - alpha) * avg + alpha * floor_signal
        worker._raw_bass_avg = avg
        dyn_ratio = getattr(worker, "_dynamic_floor_ratio", 0.42)
        if low_resolution:
            dyn_ratio = min(0.75, dyn_ratio * (1.0 + 0.35 * (resolution_boost - 1.0)))
        dyn_candidate = max(
            worker._min_floor,
            min(worker._max_floor, avg * dyn_ratio),
        )
        base_target = max(worker._min_floor, min(base_noise_floor, dyn_candidate))
        target_floor = base_target
        try:
            headroom = float(worker._floor_headroom)
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            headroom = 0.0
        if headroom > 0.0:
            headroom = min(1.0, headroom)
            blended = (floor_signal * (1.0 - headroom)) + (base_target * headroom)
            target_floor = max(worker._min_floor, min(base_noise_floor, blended))
        drop_relief = getattr(worker, "_last_bass_drop_ratio", 0.0)
        if low_resolution and drop_relief > 0.05:
            target_floor = max(worker._min_floor, target_floor * (1.0 - drop_relief * 0.45))
    else:
        target_floor = max(worker._min_floor, min(worker._max_floor, manual_floor))

    try:
        applied_floor = getattr(worker, "_applied_noise_floor", target_floor)
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        applied_floor = target_floor
    response = worker._floor_response
    if response < 0.05:
        response = 0.05
    elif response > 1.0:
        response = 1.0

    applied_floor = applied_floor + (target_floor - applied_floor) * response
    worker._applied_noise_floor = applied_floor
    noise_floor = applied_floor
    worker._last_noise_floor = noise_floor
    maybe_log_floor_state(
        worker,
        mode=mode,
        applied_floor=noise_floor,
        manual_floor=manual_floor,
        raw_bass=raw_bass,
        raw_mid=raw_mid,
        raw_treble=raw_treble,
        expansion=expansion,
    )

    return noise_floor, expansion


def _apply_low_resolution_adjustments(
    arr, bands: int, center: int, bass_drop_ratio: float,
    prev_raw_bass: float, raw_bass: float, noise_floor: float,
    drop_accum: float, np,
) -> None:
    """Apply low-resolution specific adjustments (ridge boost, drop damping, etc.)."""
    # Ridge boost
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

    if drop_signal > 0.05:
        drop_strength = min(0.92, 0.22 + drop_signal * 1.45)
        band_span = max(1, center)
        for i in range(bands):
            dist = abs(i - center) / float(band_span)
            emphasis = max(0.25, 1.0 - dist * 1.35)
            arr[i] *= max(0.0, 1.0 - drop_strength * emphasis)

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


def _apply_reactive_smoothing(worker: "SpotifyVisualizerAudioWorker", arr, bands: int, np) -> None:
    """Apply reactive smoothing with attack/decay dynamics."""
    decay_rate = 0.35

    now_ts = time.time()
    dt = now_ts - worker._last_fft_ts if worker._last_fft_ts > 0 else 0.0
    worker._last_fft_ts = now_ts

    bar_history = worker._bar_history
    hold_timers = worker._bar_hold_timers
    if hold_timers is None or hold_timers.shape[0] != bands:
        hold_timers = np.zeros(bands, dtype="int32")
        worker._bar_hold_timers = hold_timers
    if dt > 2.0:
        bar_history.fill(0.0)
        hold_timers.fill(0)

    drop_threshold = 0.01
    drop_decay = 0.25
    hold_frames = 2
    snap_fraction = 0.15

    for i in range(bands):
        target = arr[i]
        current = bar_history[i]
        hold = hold_timers[i]

        if target > current:
            attack_speed = 0.85
            new_val = current + (target - current) * attack_speed
            hold_timers[i] = 0
        else:
            drop = current - target

            if drop > drop_threshold:
                hold_timers[i] = hold_frames
                new_val = current * snap_fraction + target * (1.0 - snap_fraction)
            elif hold > 0:
                hold_timers[i] = hold - 1
                new_val = current * drop_decay
                if new_val < target:
                    new_val = target
            else:
                new_val = current * decay_rate
                if new_val < target:
                    new_val = target

        arr[i] = new_val
        bar_history[i] = new_val


def _apply_adaptive_normalization(
    worker: "SpotifyVisualizerAudioWorker", arr, drop_signal: float,
    low_resolution: bool, np,
) -> None:
    """Adaptive normalization to keep peaks near 1.0."""
    try:
        peak_val = float(arr.max())
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        peak_val = 0.0
    max_tracked_peak = 1.35
    if peak_val > max_tracked_peak:
        peak_val = max_tracked_peak
    running_peak = getattr(worker, "_running_peak", 0.5)
    try:
        floor_baseline = float(worker._applied_noise_floor)
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        floor_baseline = 2.0
    base_headroom = 0.45 + 0.1 * max(0.0, min(4.0, floor_baseline))
    _ = max(0.7, min(1.0, base_headroom))
    if peak_val > running_peak:
        running_peak += (peak_val - running_peak) * 0.32
    else:
        fast_decay = 0.9 if peak_val < running_peak * 0.5 else 0.965
        running_peak = running_peak * fast_decay + peak_val * (1.0 - fast_decay)
    drop_relief = drop_signal if low_resolution else 0.0
    if low_resolution and drop_relief > 0.35:
        running_peak *= max(0.95, 1.0 - drop_relief * 0.08)
    running_peak = max(0.18, min(1.35, running_peak))
    worker._running_peak = running_peak
    target_peak = 1.0
    if running_peak > target_peak * 1.1 and peak_val > 0.0:
        normalization = target_peak / max(running_peak, 1e-3)
        arr *= normalization


def maybe_log_floor_state(
    worker: "SpotifyVisualizerAudioWorker",
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

    last_ts = getattr(worker, "_floor_log_last_ts", 0.0) or 0.0
    last_mode = getattr(worker, "_floor_log_last_mode", None)
    last_applied = getattr(worker, "_floor_log_last_applied", -1.0)
    last_manual = getattr(worker, "_floor_log_last_manual", -1.0)

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
            worker._floor_log_last_ts = now
            worker._floor_log_last_mode = mode
            worker._floor_log_last_applied = applied_floor
            worker._floor_log_last_manual = manual_floor
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)


def compute_bars_from_samples(
    worker: "SpotifyVisualizerAudioWorker", samples
) -> Optional[List[float]]:
    """Compute visualizer bars from audio samples."""
    np_mod = worker._np
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

        try:
            peak_raw = float(np_mod.abs(mono).max()) if getattr(mono, "size", 0) > 0 else 0.0
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            peak_raw = 0.0

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
        if peak_raw < 1e-3:
            return get_zero_bars(worker)

        # Try FFTWorker first
        bars = None
        if worker._fft_worker_available and worker._fft_worker_failed_count < worker._fft_worker_max_failures:
            bars = process_via_fft_worker(worker, mono)
            if bars is not None:
                target = int(worker._bar_count)
                if len(bars) != target:
                    if len(bars) < target:
                        bars = bars + [0.0] * (target - len(bars))
                    else:
                        bars = bars[:target]
                return bars

        # Fallback to local FFT processing
        fft = np_mod.fft.rfft(mono)
        np_mod.abs(fft, out=fft)
        bars = fft_to_bars(worker, fft)
        if not isinstance(bars, list):
            return None
        target = int(worker._bar_count)
        if target <= 0:
            return None
        if len(bars) != target:
            if len(bars) < target:
                bars = bars + [0.0] * (target - len(bars))
            else:
                bars = bars[:target]
        return bars
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        if is_verbose_logging():
            logger.debug("[SPOTIFY_VIS] compute_bars_from_samples failed", exc_info=True)
        return None
