"""FFT-to-bars DSP pipeline for SpotifyVisualizerAudioWorker.

Extracted from spotify_visualizer_widget.py (M-4 refactor) to reduce monolith size.
Contains the core FFT→bar-heights conversion, noise floor management,
center-out frequency mapping, reactive smoothing, and adaptive normalization.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

from core.logging.logger import (
    get_logger,
    is_verbose_logging,
    is_perf_metrics_enabled,
    is_viz_diagnostics_enabled,
)

if TYPE_CHECKING:
    from widgets.spotify_visualizer_widget import SpotifyVisualizerAudioWorker

logger = get_logger(__name__)


@dataclass
class SpectrumShapeConfig:
    """Audio-influence weights for the lane-aware spectrum model.

    The node-driven profile remains the primary visual shaper, but each bar
    now receives a lane-specific energy mix instead of a single shared scalar.
    Bass/mid/treble energy are routed across the profile with soft crossfades
    so empty lanes can still collapse toward zero when their source energy is
    absent.

    Attributes:
        bass_emphasis: Bass energy contribution weight.  0→minimal, 1→strong.
        vocal_peak_position: Mid/vocal lane center hint.  0.2→closer to bass,
            0.6→closer to treble.
        mid_suppression: Dampens mid-band lane contribution.  0→full, 1→heavy cut.
        wave_amplitude: Overall reactivity scaling.  0→subdued, 1→punchy.
        profile_floor: Minimum bar height multiplier (0.05–0.30).
    """
    bass_emphasis: float = 0.50
    vocal_peak_position: float = 0.40
    mid_suppression: float = 0.50
    wave_amplitude: float = 0.50
    profile_floor: float = 0.12


# Singleton default config — used when the worker has no custom config.
_DEFAULT_SHAPE_CONFIG = SpectrumShapeConfig()


def get_zero_bars(worker: "SpotifyVisualizerAudioWorker") -> List[float]:
    """Return cached zero bars list to avoid per-call allocation."""
    if worker._zero_bars is None or len(worker._zero_bars) != worker._bar_count:
        worker._zero_bars = [0.0] * worker._bar_count
    return worker._zero_bars




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

        # Get raw energy values — band splits driven by notch positions
        _notch_pos = getattr(worker, '_spectrum_notch_positions', None)
        if _notch_pos and len(_notch_pos) >= 3:
            _fracs = sorted(float(n[0]) for n in _notch_pos)
            # Use interior notch boundaries to define bass/mid/treble zones
            _split1 = max(1, min(bands - 2, int(_fracs[1] * bands)))
            _split2 = max(_split1 + 1, min(bands - 1, int(_fracs[-2] * bands)))
        else:
            _split1 = min(4, bands - 1)
            _split2 = min(10, bands - 1)
        raw_bass = float(np.mean(freq_values[:_split1])) if _split1 > 0 else float(freq_values[0])
        raw_mid = float(np.mean(freq_values[_split1:_split2])) if _split2 > _split1 else raw_bass * 0.5
        raw_treble = float(np.mean(freq_values[_split2:])) if _split2 < bands else raw_bass * 0.2
        # Store split indices for dual-stage AGC zone-aware normalization
        worker._agc_bass_split = _split1
        worker._agc_mid_split = _split2
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

        # Pre-AGC energy: post-noise-floor but pre-normalization.
        # Modes that need true dynamic range (bubbles, blob) read these
        # instead of post-AGC bar-derived energy which is near-constant.
        worker._pre_agc_bass = min(1.0, bass_energy)
        worker._pre_agc_mid = min(1.0, mid_energy)
        worker._pre_agc_treble = min(1.0, treble_energy)

        # ── Transient bus (dual-path Approach A) ──────────────────────
        # Feed post-noise-floor, pre-AGC band energies into the fast path.
        _tb = getattr(worker, '_transient_bus', None)
        if _tb is not None:
            _t_snap = _tb.update(
                min(1.0, bass_energy),
                min(1.0, mid_energy),
                min(1.0, treble_energy),
            )
            _g_clamp = getattr(worker, '_transient_clamp', 1.5)
            worker._transient_bass = min(_g_clamp, _t_snap.bass_transient)
            worker._transient_mid = min(_g_clamp, _t_snap.mid_transient)
            worker._transient_high = min(_g_clamp, _t_snap.high_transient)
            worker._onset_detected = _t_snap.onset_detected
            worker._onset_type = _t_snap.onset_type
            worker._onset_strength = _t_snap.onset_strength

        # ── Shape-node driven profile ────────────────────────────────
        # The shape editor remains the visual guide, but lane energy now
        # routes per-bar so a silent band can genuinely collapse instead of
        # inheriting a single shared spectrum-wide scalar.
        shape_cfg = getattr(worker, '_spectrum_shape_config', None) or _DEFAULT_SHAPE_CONFIG
        mirrored = getattr(worker, '_spectrum_mirrored', True)
        shape_nodes = getattr(worker, '_spectrum_shape_nodes', None)

        # Build per-bar profile from user-drawn shape nodes
        from ui.tabs.media.spectrum_shape_editor import (
            interpolate_nodes, interpolate_nodes_mirrored,
        )
        if shape_nodes and len(shape_nodes) >= 1:
            if mirrored:
                profile_list = interpolate_nodes_mirrored(shape_nodes, bands)
            else:
                profile_list = interpolate_nodes(shape_nodes, bands)
        else:
            profile_list = [0.6] * bands

        profile_shape = np.array(profile_list, dtype="float32")
        profile_shape = np.maximum(profile_shape, shape_cfg.profile_floor)

        # ── Lane-aware audio routing ─────────────────────────────────
        # Build soft bar weights so the user-authored shape is still the
        # visual guide, but bass/mid/treble energy can independently drive
        # and collapse their own lanes.
        bass_w = max(0.1, shape_cfg.bass_emphasis * 1.6)   # 0→0.1 .. 1→1.6
        mid_w = max(0.1, 1.0 - shape_cfg.mid_suppression * 0.8)  # 0→1.0 .. 1→0.2
        react_scale = 0.5 + shape_cfg.wave_amplitude  # 0→0.5 .. 1→1.5

        positions = np.linspace(0.0, 1.0, bands, dtype="float32")
        split1_pos = float(_split1) / max(1.0, float(bands - 1))
        split2_pos = float(_split2) / max(1.0, float(bands - 1))
        vocal_center = max(split1_pos, min(split2_pos, float(shape_cfg.vocal_peak_position)))

        blend_width = max(0.06, min(0.22, 0.08 + (split2_pos - split1_pos) * 0.35))

        bass_mask = np.clip((split1_pos + blend_width - positions) / max(blend_width, 1e-6), 0.0, 1.0)
        treble_mask = np.clip((positions - (split2_pos - blend_width)) / max(blend_width, 1e-6), 0.0, 1.0)
        mid_mask = 1.0 - np.maximum(bass_mask, treble_mask)
        mid_peak = np.clip(1.0 - (np.abs(positions - vocal_center) / max(split2_pos - split1_pos, 0.12)), 0.0, 1.0)
        mid_mask = np.maximum(mid_mask, mid_peak * 0.55)

        weight_sum = bass_mask + mid_mask + treble_mask
        np.maximum(weight_sum, 1e-6, out=weight_sum)

        bass_weight_map = (bass_mask / weight_sum) * bass_w
        mid_weight_map = (mid_mask / weight_sum) * mid_w
        treble_weight_map = treble_mask / weight_sum

        per_bar_energy = (
            bass_energy * bass_weight_map
            + mid_energy * mid_weight_map
            + treble_energy * treble_weight_map
        ) * react_scale

        # In mirrored mode the left half already has correct bass→treble
        # routing (low bar index = low freq).  Mirror the right half so
        # both edges get bass energy instead of the right side getting
        # treble energy due to its high linear position.
        if mirrored:
            for _mi in range(center + 1, bands):
                per_bar_energy[_mi] = per_bar_energy[2 * center - _mi]
            # Prevent center bar energy dip: it represents the same
            # high-frequency zone as its immediate neighbors.
            if 0 < center < bands:
                per_bar_energy[center] = per_bar_energy[center - 1]

        arr[:bands] = profile_shape[:bands] * per_bar_energy[:bands]

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

    # BAR GATING (median + hysteresis) then REACTIVE SMOOTHING
    _apply_bar_gate(worker, arr, np)
    _apply_reactive_smoothing(worker, arr, bands, np)

    # ── Kick express lane (Approach A §5) ─────────────────────────────
    # When transient bass exceeds threshold, boost bass-zone bars directly
    # so kicks register within 1 frame instead of waiting for smoothing.
    _t_bass = getattr(worker, '_transient_bass', 0.0)
    if _t_bass > 0.05:
        _kick_gain = getattr(worker, '_kick_lane_gain', 1.0)
        _lane_mix = getattr(worker, '_spectrum_lane_transient_mix', 0.65)
        _bass_end = max(1, getattr(worker, '_agc_bass_split', 4))
        _kick_boost = min(2.0, 1.0 + _t_bass * _kick_gain * _lane_mix)
        for _ki in range(_bass_end):
            if _ki < bands:
                arr[_ki] = min(1.0, arr[_ki] * _kick_boost)
        # Mirror kick boost to right-side bass bars in mirrored mode
        if mirrored:
            for _ki in range(_bass_end):
                _ri = 2 * center - _ki
                if 0 <= _ri < bands:
                    arr[_ri] = min(1.0, arr[_ri] * _kick_boost)

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
    if (
        now <= 0.0
        or (now - last_snapshot) >= min_interval
    ) and is_viz_diagnostics_enabled():
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

        # Keep decay behavior tied to the current configured rates rather than
        # hardcoding one multiplier.  We still enforce a minimum asymmetry that
        # grows when floor signal is elevated vs baseline to prevent ratchet-up.
        configured_ratio = alpha_decay / max(alpha_rise, 1e-6)
        floor_elev = max(0.0, min(2.0, (floor_signal / max(base_noise_floor, 1e-6)) - 1.0))
        min_ratio = 1.6 + floor_elev * 0.9
        decay_ratio = max(configured_ratio, min_ratio)
        alpha_decay = min(1.0, max(alpha_decay, alpha_rise * decay_ratio))

        alpha = alpha_rise if floor_signal >= avg else alpha_decay
        avg = (1.0 - alpha) * avg + alpha * floor_signal
        # Cap avg so floor cannot drift far above what the static
        # analysis (base_noise_floor) considers reasonable.
        avg = min(avg, base_noise_floor * 2.5)
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
        if drop_relief > 0.18:
            target_floor = max(worker._min_floor, target_floor * (1.0 - drop_relief * 0.18))
        elif low_resolution and drop_relief > 0.05:
            target_floor = max(worker._min_floor, target_floor * (1.0 - drop_relief * 0.45))
    else:
        target_floor = max(worker._min_floor, min(worker._max_floor, manual_floor))
        # Compensate expansion when floor is lowered: more signal passes through,
        # so scale down expansion to prevent bar pinning at max height.
        if noise_floor_base > 0.01 and target_floor < noise_floor_base * 0.9:
            floor_ratio = max(0.15, target_floor / noise_floor_base)
            expansion *= max(0.50, floor_ratio ** 0.35)

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


def _apply_bar_gate(worker: "SpotifyVisualizerAudioWorker", arr, np) -> None:
    """Suppress tiny bar oscillations via median filter + hysteresis."""
    if arr.size == 0:
        return

    bands = arr.shape[0]
    current_raw = np.array(arr, copy=True)

    prev1 = getattr(worker, "_bar_gate_prev1", None)
    prev2 = getattr(worker, "_bar_gate_prev2", None)
    prev_out = getattr(worker, "_bar_gate_output", None)

    if (
        prev1 is None or prev2 is None or prev_out is None
        or prev1.shape[0] != bands or prev2.shape[0] != bands or prev_out.shape[0] != bands
    ):
        worker._bar_gate_prev1 = current_raw
        worker._bar_gate_prev2 = current_raw
        worker._bar_gate_output = np.array(arr, copy=True)
        return

    # 3-sample median to kill impulsive spikes
    stack = np.stack((current_raw, prev1, prev2), axis=0)
    median = np.partition(stack, 1, axis=0)[1]

    prev_vals = prev_out
    threshold_base = np.maximum(0.015, prev_vals * 0.08)
    delta = median - prev_vals

    effective_threshold = np.where(delta >= 0.0, threshold_base, threshold_base * 0.7)
    mask = np.abs(delta) >= effective_threshold

    gated = prev_vals.copy()
    gated[mask] = median[mask]

    arr[:] = gated

    worker._bar_gate_prev2 = prev1
    worker._bar_gate_prev1 = current_raw
    worker._bar_gate_output = gated


def _apply_low_resolution_adjustments(
    arr, bands: int, center: int, bass_drop_ratio: float,
    prev_raw_bass: float, raw_bass: float, noise_floor: float,
    drop_accum: float, np,
) -> None:
    """Apply low-resolution audio-reactive adjustments (drop damping only).

    All legacy center-suppression shaping (ridge boosts, center caps,
    target_map ratios, neighbor smoothing) has been removed.
    The node-driven profile is the sole bar-height shaper.
    """
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
        drop_strength = min(0.70, 0.15 + drop_signal * 1.0)
        arr *= max(0.08, 1.0 - drop_strength)


def _apply_reactive_smoothing(worker: "SpotifyVisualizerAudioWorker", arr, bands: int, np) -> None:
    """Apply reactive smoothing with attack/decay dynamics.

    Attack: lerp toward target at 0.65 (smooth rise).
    Decay: lerp toward target (not toward zero) at different rates depending
    on whether the drop is large (snap) or gradual (glide).  This prevents
    the old multiplicative-toward-zero pattern that caused center bars to
    oscillate between snapping up and decaying past the sustained level.
    """
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

    drop_threshold = max(0.08, float(getattr(worker, "_drop_threshold", 0.16) or 0.16))
    hold_frames = max(1, int(getattr(worker, "_drop_hold_frames", 2) or 2))
    drop_speed = max(0.5, min(3.0, float(getattr(worker, "_drop_speed", 1.0) or 1.0)))
    attack_speed = 0.72
    decay_snap_base = max(0.45, float(getattr(worker, "_drop_snap_fraction", 0.58) or 0.58))
    decay_hold_base = 0.28
    decay_glide_base = 0.12
    # drop_speed scales decay rates: >1.0 = snappier drops, <1.0 = stickier bars
    decay_snap = min(0.92, decay_snap_base * drop_speed)
    decay_hold = min(0.65, decay_hold_base * drop_speed)
    decay_glide = min(0.45, decay_glide_base * drop_speed)
    micro_drop_threshold = min(0.045, drop_threshold * 0.28)
    large_drop_threshold = max(drop_threshold, 0.18)

    for i in range(bands):
        target = arr[i]
        current = bar_history[i]
        hold = hold_timers[i]

        if target > current:
            new_val = current + (target - current) * attack_speed
            hold_timers[i] = 0
        else:
            drop = current - target

            if drop <= micro_drop_threshold:
                hold_timers[i] = max(0, hold - 1)
                new_val = current
            elif drop > large_drop_threshold:
                hold_timers[i] = hold_frames
                new_val = current + (target - current) * decay_snap
            elif drop > drop_threshold:
                hold_timers[i] = hold_frames
                new_val = current + (target - current) * 0.34
            elif hold > 0:
                hold_timers[i] = hold - 1
                new_val = current + (target - current) * decay_hold
            else:
                new_val = current + (target - current) * decay_glide

        arr[i] = new_val
        bar_history[i] = new_val


def _apply_adaptive_normalization(
    worker: "SpotifyVisualizerAudioWorker", arr, drop_signal: float,
    low_resolution: bool, np,
) -> None:
    """Dual-stage AGC with bass/mix envelope split (Approach A §4.5.4).

    Maintains TWO independent envelope stacks:
      - **Bass envelopes** (env_bass_short/long): fed only by bass energy.
      - **Mix envelopes** (env_mix_short/long): fed by mid+high energy.

    Each stack has short-term (~300ms, limiter) and long-term (~3s, leveling)
    envelopes.  Normalization decisions (limiter/recovery) are computed
    per-stack so that vocals inflating the mix envelope cannot choke bass
    recovery, and vice-versa.

    Bars in the bass zone get the bass gain, bars in the mid/high zone get
    the mix gain, with a smooth crossfade in the transition region.

    Legacy combined envelopes (_env_short/_env_long) are still updated for
    backward compatibility with any code reading them.
    """
    agc_str = getattr(worker, "_agc_strength", 0.5)
    if agc_str < 0.01:
        return  # AGC disabled — raw output only

    bands = arr.shape[0] if hasattr(arr, 'shape') else len(arr)
    if bands == 0:
        return

    # --- Source energies for split envelopes ---
    bass_e = min(1.3, max(0.0, getattr(worker, "_pre_agc_bass", 0.0)))
    mid_e = min(1.3, max(0.0, getattr(worker, "_pre_agc_mid", 0.0)))
    high_e = min(1.3, max(0.0, getattr(worker, "_pre_agc_treble", 0.0)))
    mix_e = (mid_e * 0.6 + high_e * 0.4)  # weighted mid+high

    max_tracked = 1.30
    rate_scale = 0.5 + agc_str  # 0.5→1.0 at default, 0.5→1.5 at max

    # --- Bass envelopes ---
    eb_s = getattr(worker, "_env_bass_short", 0.5)
    eb_l = getattr(worker, "_env_bass_long", 0.5)
    if bass_e > eb_s:
        eb_s += (bass_e - eb_s) * 0.35 * rate_scale
    else:
        eb_s += (bass_e - eb_s) * 0.20 * rate_scale
    if bass_e > eb_l:
        eb_l += (bass_e - eb_l) * 0.06 * rate_scale
    else:
        eb_l += (bass_e - eb_l) * 0.025 * rate_scale

    # --- Mix envelopes ---
    em_s = getattr(worker, "_env_mix_short", 0.5)
    em_l = getattr(worker, "_env_mix_long", 0.5)
    if mix_e > em_s:
        em_s += (mix_e - em_s) * 0.30 * rate_scale
    else:
        em_s += (mix_e - em_s) * 0.15 * rate_scale
    if mix_e > em_l:
        em_l += (mix_e - em_l) * 0.05 * rate_scale
    else:
        em_l += (mix_e - em_l) * 0.02 * rate_scale

    # --- Drop relief: on bass drops, nudge bass envelopes down faster ---
    drop_relief = max(0.0, float(drop_signal or 0.0))
    if drop_relief > 0.15:
        nudge = max(0.80, 1.0 - drop_relief * 0.22)
        eb_s *= nudge
        eb_l *= max(0.90, nudge)

    # Clamp all envelopes
    eb_s = max(0.08, min(max_tracked, eb_s))
    eb_l = max(0.08, min(max_tracked, eb_l))
    em_s = max(0.08, min(max_tracked, em_s))
    em_l = max(0.08, min(max_tracked, em_l))

    worker._env_bass_short = eb_s
    worker._env_bass_long = eb_l
    worker._env_mix_short = em_s
    worker._env_mix_long = em_l

    # Legacy combined envelopes for backward compat
    combined_short = eb_s * 0.5 + em_s * 0.5
    combined_long = eb_l * 0.5 + em_l * 0.5
    worker._env_short = combined_short
    worker._env_long = combined_long
    worker._running_peak = combined_short

    # --- Per-stack gain computation ---
    limiter_thresh = 1.2 - agc_str * 0.4  # 1.0 at default, 0.8 at max

    def _compute_stack_gain(env_s: float, env_l: float) -> float:
        """Compute gain factor for one envelope stack."""
        # 1) Limiter: short-term exceeds threshold → compress
        if env_s > limiter_thresh:
            raw_gain = limiter_thresh / env_s
            return 1.0 + (raw_gain - 1.0) * agc_str * 2.0
        # 2) Recovery: short << long (quiet after loud) → gentle boost
        if env_l > 0.15 and env_s < env_l * 0.45:
            boost = min(1.35, env_l / max(env_s, 0.08))
            blend = min(0.3, (env_l - env_s) / max(env_l, 0.1))
            return 1.0 + (boost - 1.0) * blend * agc_str * 2.0
        # 3) Sustained: short ≈ long → unity gain (preserve dynamics)
        return 1.0

    bass_gain = _compute_stack_gain(eb_s, eb_l)
    mix_gain = _compute_stack_gain(em_s, em_l)

    # --- Apply zone-aware gain to bars ---
    bass_split = max(1, getattr(worker, "_agc_bass_split", 4))
    mid_split = max(bass_split + 1, getattr(worker, "_agc_mid_split", 10))
    # Transition zone width for smooth crossfade between bass and mix gain
    trans_width = max(1, (mid_split - bass_split))

    if abs(bass_gain - 1.0) < 0.001 and abs(mix_gain - 1.0) < 0.001:
        return  # Both stacks at unity — skip array manipulation

    _agc_mirrored = getattr(worker, '_spectrum_mirrored', False)
    _agc_center = bands // 2
    for i in range(bands):
        # In mirrored mode, map display index to frequency index so
        # right-side bass bars (high index) get bass_gain, not mix_gain.
        ei = (_agc_center - abs(i - _agc_center)) if _agc_mirrored else i
        if ei < bass_split:
            arr[i] *= bass_gain
        elif ei < mid_split:
            # Crossfade zone: blend bass_gain → mix_gain
            t = (ei - bass_split) / trans_width
            arr[i] *= bass_gain * (1.0 - t) + mix_gain * t
        else:
            arr[i] *= mix_gain


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

    if not (is_perf_metrics_enabled() and is_viz_diagnostics_enabled()):
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

        # Pre-FFT input gain (virtual volume): scale PCM exactly like the
        # mixer volume slider would, before peak detection and FFT.
        _input_gain = getattr(worker, "_input_gain", 1.0)
        if abs(_input_gain - 1.0) > 1e-4:
            mono = mono * _input_gain

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

        # Inline FFT processing (single code path — no IPC fallback)
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
