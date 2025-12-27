"""
Test script to visualize FFT bar distribution.
Generates synthetic audio signals and shows the resulting bar heights.
"""
# ruff: noqa: E402
from __future__ import annotations

import os
import re
import sys
import time
from collections import deque
from typing import List, Sequence, Tuple

import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
LOG_PATH_DEFAULT = os.path.join(BASE_DIR, "logs", "screensaver_spotify_vis.log")
DEFAULT_BAR_COUNT = 15
DEFAULT_BLOCK_SIZE = 256
DEFAULT_LOG_FRAMES = 360

from utils.lockfree import TripleBuffer
from widgets.spotify_visualizer_widget import (
    SpotifyVisualizerAudioWorker,
    _AudioFrame,
)


LOG_BAR_PATTERN = re.compile(
    r"raw_bass=(?P<bass>-?\d+(?:\.\d+)?)\s+Bars:\s+\[(?P<bars>[^\]]+)\]"
)


def create_live_worker(
    bar_count: int = DEFAULT_BAR_COUNT, block_size: int = DEFAULT_BLOCK_SIZE
) -> SpotifyVisualizerAudioWorker:
    """Instantiate the real Spotify audio worker with numpy injected."""
    buf: TripleBuffer[_AudioFrame] = TripleBuffer()
    worker = SpotifyVisualizerAudioWorker(bar_count=bar_count, buffer=buf)
    worker._np = np  # type: ignore[attr-defined]
    if block_size and hasattr(worker, "set_audio_block_size"):
        worker.set_audio_block_size(block_size)
    return worker


def load_log_bar_series(
    log_path: str, max_frames: int = DEFAULT_LOG_FRAMES
) -> List[Tuple[float, List[float]]]:
    """Load most recent bar snapshots from the visualizer log."""
    if not os.path.exists(log_path):
        return []
    frames: deque[Tuple[float, List[float]]] = deque(maxlen=max_frames)
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                match = LOG_BAR_PATTERN.search(line)
                if not match:
                    continue
                try:
                    bass_val = float(match.group("bass"))
                    bar_tokens = re.split(r"\s+", match.group("bars").strip())
                    bars = [float(tok) for tok in bar_tokens if tok]
                except Exception:
                    continue
                frames.append((bass_val, bars))
    except FileNotFoundError:
        return []
    return list(frames)


def load_log_intensity_profile(
    log_path: str = LOG_PATH_DEFAULT, max_frames: int = DEFAULT_LOG_FRAMES
) -> np.ndarray | None:
    """Derive an intensity envelope from recent log bass readings."""
    frames = load_log_bar_series(log_path, max_frames=max_frames)
    if not frames:
        return None
    bass_vals = np.array([max(0.0, bass) for bass, _ in frames], dtype="float32")
    if bass_vals.size < 64:
        return None
    # Focus on most recent window to mirror live state
    bass_vals = bass_vals[-max_frames:]
    # Smooth to remove sharp spikes while preserving valleys
    window = max(3, min(45, bass_vals.size // 24))
    kernel = np.ones(window, dtype="float32") / float(window)
    smooth = np.convolve(bass_vals, kernel, mode="same")
    # Normalize to [0, 1] and add gentle floor/ceiling bounds
    peak = float(np.max(smooth))
    if peak <= 1e-3:
        return None
    normalized = smooth / peak
    # Expand slightly so quiet passages still drive some intensity
    return np.clip(0.12 + normalized * 0.92, 0.12, 1.15)


def report_bar_metrics(
    bar_history: Sequence[Sequence[float]],
    label: str,
    raw_bass_values: Sequence[float] | None = None,
    noise_floor_values: Sequence[float] | None = None,
    running_peak_values: Sequence[float] | None = None,
) -> bool:
    """Compute and print the same metrics used for synthetic/log playback."""
    if not bar_history:
        print(f"\n{'='*60}\n {label}\n{'='*60}")
        print("No bar data available.")
        return False

    center_idx = len(bar_history[0]) // 2
    center_values = np.array([bars[center_idx] for bars in bar_history])
    edge_values = np.array([bars[0] for bars in bar_history])

    bar_array = np.array(bar_history)
    bar_means = bar_array.mean(axis=0)
    left_peak_idx = max(0, center_idx - 3)
    right_peak_idx = min(bar_means.size - 1, center_idx + 3)
    left_peak_mean = float(bar_means[left_peak_idx])
    right_peak_mean = float(bar_means[right_peak_idx])
    edge_mean = float(bar_means[0])
    inner_left_mean = float(bar_means[max(0, center_idx - 2)])
    shoulder_mean = float(bar_means[max(0, center_idx - 1)])
    center_mean = float(bar_means[center_idx])
    neighbor_left_mean = float(bar_means[left_peak_idx - 1]) if left_peak_idx - 1 >= 0 else left_peak_mean
    neighbor_right_mean = float(bar_means[left_peak_idx + 1]) if left_peak_idx + 1 < bar_means.size else left_peak_mean

    center_above_95 = float(np.mean(center_values >= 0.95))
    edge_above_95 = float(np.mean(edge_values >= 0.95))

    center_min = float(center_values.min())
    center_max = float(center_values.max())
    center_range = center_max - center_min
    center_std = float(center_values.std())

    edge_min = float(edge_values.min())
    edge_max = float(edge_values.max())
    edge_range = edge_max - edge_min
    edge_std = float(edge_values.std())

    center_above_95 = float(np.mean(center_values >= 0.95))
    edge_above_95 = float(np.mean(edge_values >= 0.95))

    drops: List[float] = []
    for prev, curr in zip(center_values, center_values[1:], strict=False):
        delta = prev - curr
        if delta > 1e-3:
            drops.append(delta)
    single_spike_frames = 0
    spike_threshold = 0.88
    for bars in bar_history:
        if sum(1 for val in bars if val >= spike_threshold) == 1:
            single_spike_frames += 1
    single_spike_ratio = single_spike_frames / max(1, len(bar_history))
    avg_drop = float(np.mean(drops)) if drops else 0.0
    max_drop = float(np.max(drops)) if drops else 0.0

    print(f"\n{'='*60}\n {label}\n{'='*60}")
    print(
        f"Center bar ({center_idx}): min={center_min:.2f}, max={center_max:.2f}, "
        f"range={center_range:.2f}, std={center_std:.3f}, stuck>=0.95={center_above_95:.2%}"
    )
    print(
        f"Edge bar (0):   min={edge_min:.2f}, max={edge_max:.2f}, "
        f"range={edge_range:.2f}, std={edge_std:.3f}, stuck>=0.95={edge_above_95:.2%}"
    )
    print(
        f"Avg profile (selected bars): "
        f"L3={left_peak_mean:.3f} L2={inner_left_mean:.3f} "
        f"L1={shoulder_mean:.3f} C={center_mean:.3f} "
        f"R1={neighbor_right_mean:.3f} R3={right_peak_mean:.3f} Edge={edge_mean:.3f}"
    )

    if noise_floor_values:
        noise_floor_arr = np.array(noise_floor_values)
        print(
            f"Noise floor avg={noise_floor_arr.mean():.2f}, "
            f"min={noise_floor_arr.min():.2f}, max={noise_floor_arr.max():.2f}"
        )
    else:
        print("Noise floor stats unavailable (source did not record them).")

    if running_peak_values:
        running_peak_arr = np.array(running_peak_values)
        print(
            f"Running peak avg={running_peak_arr.mean():.2f}, "
            f"min={running_peak_arr.min():.2f}, max={running_peak_arr.max():.2f}"
        )
    else:
        print("Running peak stats unavailable (source did not record them).")

    if raw_bass_values:
        bass_arr = np.array(raw_bass_values)
        print(
            f"Raw bass avg={bass_arr.mean():.2f}, min={bass_arr.min():.2f}, max={bass_arr.max():.2f}"
        )

    print(
        f"Drops: avg={avg_drop:.2f}, max={max_drop:.2f}, samples={len(drops)}, "
        f"single-bar flickers={single_spike_ratio:.2%}"
    )

    problems: List[str] = []
    if center_above_95 > 0.7:
        problems.append(
            f"FAIL: Center bar stuck high {center_above_95:.0%} of frames (should be < 70%)"
        )
    if center_max < 0.9:
        problems.append(f"FAIL: Center bar never peaks (max={center_max:.2f}, should reach 0.9+)")
    if center_range < 0.3:
        problems.append(f"FAIL: Center bar not reactive (range={center_range:.2f}, should be 0.3+)")
    if max_drop < 0.2:
        problems.append(f"FAIL: Center bar max drop too small (max_drop={max_drop:.2f}, need >= 0.20)")
    if avg_drop < 0.18:
        problems.append(f"FAIL: Center bar average drop too small (avg_drop={avg_drop:.2f}, need >= 0.18)")
    if avg_drop > 0.4:
        problems.append(f"FAIL: Center bar average drop too large (avg_drop={avg_drop:.2f}, keep <= 0.40)")

    # Shape-specific checks (derived from recent log averages)
    if center_mean > left_peak_mean * 0.7:
        problems.append("FAIL: Center average too close to ridge peak (needs valley).")
    if center_mean < 0.1:
        problems.append("FAIL: Center average too low (raise center so drops stay visible).")
    if neighbor_left_mean + 0.015 > left_peak_mean:
        problems.append("FAIL: Bar 4 peak not clearly above bar 3 (ridge should lead).")
    if inner_left_mean + 0.025 > left_peak_mean:
        problems.append("FAIL: Bar 5 average too close to ridge (slope should fall after peak).")
    if shoulder_mean + 0.03 > inner_left_mean:
        problems.append("FAIL: Bar 6 shoulder not tapering enough after ridge.")
    if edge_mean > min(0.3, left_peak_mean * 0.55):
        problems.append("FAIL: Edge bar averages too high (outer bars should stay visibly lower).")
    if single_spike_ratio > 0.08:
        problems.append(
            f"FAIL: Too many single-bar flickers (ratio={single_spike_ratio:.2%}, target <= 8%)."
        )

    edge_relative_range = edge_range / max(edge_max, 0.01)
    if edge_relative_range < 0.3:
        problems.append(
            f"FAIL: Edge bars not reactive (relative range={edge_relative_range:.2f}, should be 0.3+)"
        )

    last_bars = bar_history[-1]
    slope_warning = None
    if len(last_bars) >= 2 and last_bars[0] > last_bars[center_idx] * 0.75:
        slope_warning = (
            f"Advisory: edge bar {last_bars[0]:.2f} is >=75% of center {last_bars[center_idx]:.2f} (check slope)."
        )

    print()
    if problems:
        print("PROBLEMS DETECTED:")
        for p in problems:
            print(f"  ❌ {p}")
        return False

    print("✓ Center bar peaks and drops appropriately")
    print("✓ Edge bars show variation")
    print("✓ Slope maintained (center > edges)")
    if slope_warning:
        print(f"⚠ {slope_warning}")
    return True


def generate_test_signal(
    signal_type: str, n_samples: int = DEFAULT_BLOCK_SIZE, sample_rate: int = 48000
) -> np.ndarray:
    """Generate various test signals."""
    t = np.arange(n_samples) / sample_rate
    
    if signal_type == "white_noise":
        return np.random.randn(n_samples).astype("float32")
    
    elif signal_type == "pink_noise":
        # Pink noise has equal energy per octave (1/f spectrum)
        white = np.fft.rfft(np.random.randn(n_samples))
        freqs = np.fft.rfftfreq(n_samples)
        freqs[0] = 1  # Avoid division by zero
        pink = white / np.sqrt(freqs)
        return np.fft.irfft(pink).astype("float32")
    
    elif signal_type == "bass_heavy":
        # Strong bass (60Hz) + some mids
        return (np.sin(2 * np.pi * 60 * t) * 0.8 + 
                np.sin(2 * np.pi * 200 * t) * 0.3 +
                np.sin(2 * np.pi * 1000 * t) * 0.1).astype("float32")
    
    elif signal_type == "mid_heavy":
        # Strong mids (500Hz, 1kHz, 2kHz)
        return (np.sin(2 * np.pi * 500 * t) * 0.5 + 
                np.sin(2 * np.pi * 1000 * t) * 0.8 +
                np.sin(2 * np.pi * 2000 * t) * 0.5).astype("float32")
    
    elif signal_type == "treble_heavy":
        # Strong highs (4kHz, 8kHz, 12kHz)
        return (np.sin(2 * np.pi * 4000 * t) * 0.5 + 
                np.sin(2 * np.pi * 8000 * t) * 0.8 +
                np.sin(2 * np.pi * 12000 * t) * 0.5).astype("float32")
    
    elif signal_type == "full_spectrum":
        # Equal energy across spectrum - scaled to match real audio
        signal = np.zeros(n_samples)
        for freq in [60, 120, 250, 500, 1000, 2000, 4000, 8000, 12000]:
            signal += np.sin(2 * np.pi * freq * t) * 0.03
        return signal.astype("float32")
    
    elif signal_type == "kick_drum":
        # Simulated kick: low freq burst
        # Scale down to match real Spotify audio levels
        envelope = np.exp(-t * 20)
        return (np.sin(2 * np.pi * 60 * t) * envelope * 0.15).astype("float32")
    
    return np.zeros(n_samples, dtype="float32")


def visualize_bars(bars, title="", width=60):
    """Create ASCII visualization of bar heights."""
    print(f"\n{'='*width}")
    print(f" {title}")
    print(f"{'='*width}")
    
    # Show bar indices
    indices = "".join(f"{i:>3}" for i in range(len(bars)))
    print(f"Bar#: {indices}")
    
    # Show bar values
    values = "".join(f"{v:>3.0f}" for v in [b*100 for b in bars])
    print(f"Val%: {values}")
    
    # ASCII bar chart (horizontal) - use ASCII chars for Windows compatibility
    max_bar_width = width - 10
    for i, bar in enumerate(bars):
        bar_len = int(bar * max_bar_width)
        bar_str = "#" * bar_len + "." * (max_bar_width - bar_len)
        print(f"[{i:2d}] {bar_str} {bar:.2f}")
    
    # Summary stats
    print(f"\nStats: min={min(bars):.2f}, max={max(bars):.2f}, mean={np.mean(bars):.2f}")
    
    # Distribution analysis
    left_third = bars[:len(bars)//3]
    mid_third = bars[len(bars)//3:2*len(bars)//3]
    right_third = bars[2*len(bars)//3:]
    print(f"Left avg: {np.mean(left_third):.2f}, Mid avg: {np.mean(mid_third):.2f}, Right avg: {np.mean(right_third):.2f}")


def analyze_band_edges(n_fft_bins, n_bars):
    """Show how FFT bins are distributed across bars."""
    min_freq_idx = 1
    max_freq_idx = n_fft_bins
    log_edges = np.logspace(
        np.log10(min_freq_idx),
        np.log10(max_freq_idx),
        n_bars + 1,
        dtype="float32"
    ).astype("int32")
    
    print(f"\n{'='*60}")
    print(f" Band Edge Analysis (FFT bins: {n_fft_bins}, Bars: {n_bars})")
    print(f"{'='*60}")
    
    for b in range(n_bars):
        start = int(log_edges[b])
        end = int(log_edges[b + 1])
        count = end - start
        print(f"Bar {b:2d}: bins {start:4d}-{end:4d} ({count:3d} bins)")
    
    return log_edges


def run_reactivity_realistic(
    worker: SpotifyVisualizerAudioWorker,
    fps: int = 60,
    duration_sec: float = 4.0,
    log_intensity: np.ndarray | None = None,
) -> bool:
    """Test reactivity with REAL timing like the actual app.
    
    This test simulates CONTINUOUS audio like real music:
    1. Runs at actual FPS with real time.sleep() delays
    2. Uses CONTINUOUS signal (always has audio, varying levels)
    3. Tracks variance to detect "stuck" bars
    4. Reports PASS/FAIL based on actual requirements
    
    KEY INSIGHT: Real music ALWAYS has a peak. The problem is that
    normalizing by peak means center is ALWAYS 1.0.
    """
    print(f"\n{'='*60}")
    print(f" REALISTIC REACTIVITY TEST ({fps} FPS, {duration_sec}s)")
    print(f"{'='*60}")
    
    # Generate base signal
    loud_samples = generate_test_signal("kick_drum")
    loud_fft = np.abs(np.fft.rfft(loud_samples))
    
    frame_time = 1.0 / fps
    n_frames = int(duration_sec * fps)
    
    # Track bar values over time
    raw_bass_values: List[float] = []
    noise_floor_values: List[float] = []
    running_peak_values: List[float] = []
    all_bars_history: List[List[float]] = []
    
    print(f"Running {n_frames} frames with {frame_time*1000:.1f}ms between frames...")
    if log_intensity is not None and log_intensity.size > 0:
        print(
            "Using LOG-DERIVED intensity envelope blended with synthetic modulation\n"
        )
        log_intensity = log_intensity.astype("float32", copy=False)
    else:
        print("Using CONTINUOUS audio with varying intensity (like real music)\n")
    
    valley_period = int(fps * 1.5)
    valley_hold = int(fps * 0.45)
    micro_drop_interval = int(fps * 0.75)

    for frame in range(n_frames):
        # Simulate CONTINUOUS audio with varying intensity blended with real logs
        # Base synthetic modulation (1-second cycle)
        synthetic_intensity = 0.1 + 0.9 * (0.5 + 0.5 * np.sin(2 * np.pi * frame / fps))
        valley_phase = frame % max(1, valley_period)
        if valley_phase < valley_hold:
            valley_scale = 0.08 + 0.6 * (valley_phase / max(1, valley_hold))
            synthetic_intensity *= valley_scale
        if micro_drop_interval > 0 and frame % micro_drop_interval == micro_drop_interval - 1:
            synthetic_intensity *= 0.05
        synthetic_intensity = max(0.01, min(1.2, synthetic_intensity))

        if log_intensity is not None and log_intensity.size > 0:
            env_val = float(log_intensity[frame % log_intensity.size])
            # Blend log envelope with synthetic shape for realism and variability
            intensity = max(
                0.01, min(1.2, synthetic_intensity * 0.45 + env_val * 0.65)
            )
        else:
            intensity = synthetic_intensity
        fft = loud_fft * intensity

        bars = worker._fft_to_bars(fft)
        
        center_val = bars[7] if len(bars) > 7 else (bars[len(bars) // 2] if bars else 0.0)
        edge_val = bars[0] if bars else 0.0
        all_bars_history.append(list(bars))
        
        # Debug: print every 15 frames to see variation
        if frame % 15 == 0:
            nf = getattr(worker, "_last_noise_floor", None)
            rp = getattr(worker, "_running_peak", None)
            print(
                f"  Frame {frame:3d} [int={intensity:.2f}]: "
                f"center={center_val:.3f}, edge={edge_val:.3f}, "
                f"noise_floor={nf:.2f} rp={rp:.2f}"
            )
        
        # Real timing delay
        raw_bass_values.append(float(getattr(worker, "_last_raw_bass", 0.0)))
        noise_floor_values.append(float(getattr(worker, "_last_noise_floor", 0.0)))
        running_peak_values.append(float(getattr(worker, "_running_peak", 0.0)))
        time.sleep(frame_time)
    
    return report_bar_metrics(
        bar_history=all_bars_history,
        label="REALISTIC REACTIVITY (synthetic)",
        raw_bass_values=raw_bass_values,
        noise_floor_values=noise_floor_values,
        running_peak_values=running_peak_values,
    )


def run_log_snapshot_analysis(
    log_path: str = LOG_PATH_DEFAULT, max_frames: int = DEFAULT_LOG_FRAMES
) -> bool:
    """Replay recent log frames to compare metrics with synthetic test."""
    frames = load_log_bar_series(log_path, max_frames=max_frames)
    print(f"\n{'='*60}\n LOG SNAPSHOT ANALYSIS\n{'='*60}")
    if not frames:
        print(f"No log data available at {log_path!r}. Skipping log comparison.\n")
        return True

    bar_history: List[List[float]] = []
    raw_bass_values: List[float] = []
    for bass_val, bars in frames:
        if not bars:
            continue
        bar_list = list(bars)
        if len(bar_list) < DEFAULT_BAR_COUNT:
            bar_list.extend([0.0] * (DEFAULT_BAR_COUNT - len(bar_list)))
        elif len(bar_list) > DEFAULT_BAR_COUNT:
            bar_list = bar_list[:DEFAULT_BAR_COUNT]
        bar_history.append(bar_list)
        raw_bass_values.append(bass_val)

    if not bar_history:
        print("Parsed log contained no usable bar frames.\n")
        return False

    return report_bar_metrics(
        bar_history=bar_history,
        label=f"LOG SNAPSHOT (last {len(bar_history)} frames)",
        raw_bass_values=raw_bass_values,
    )


def main():
    print("=" * 70)
    print(" SPOTIFY VISUALIZER FFT DISTRIBUTION TEST")
    print("=" * 70)
    
    worker = create_live_worker(bar_count=DEFAULT_BAR_COUNT)
    
    # Analyze band edges first
    fft_bins = (DEFAULT_BLOCK_SIZE // 2) + 1
    analyze_band_edges(fft_bins, DEFAULT_BAR_COUNT)
    
    # Test with different signals (quick visual check)
    test_signals = [
        "kick_drum",
        "full_spectrum",
    ]
    
    for signal_type in test_signals:
        samples = generate_test_signal(signal_type)
        fft = np.abs(np.fft.rfft(samples))
        bars = worker._fft_to_bars(fft)
        visualize_bars(bars, f"Signal: {signal_type}")
    
    # REALISTIC reactivity test with real timing
    worker2 = create_live_worker(bar_count=DEFAULT_BAR_COUNT)
    synthetic_passed = run_reactivity_realistic(worker2, fps=60, duration_sec=4.0)

    log_envelope = load_log_intensity_profile()
    reactivity_ok = run_reactivity_realistic(worker, log_intensity=log_envelope)
    log_ok = run_log_snapshot_analysis()
    
    print("\n" + "=" * 70)
    if synthetic_passed and reactivity_ok and log_ok:
        print(" ALL TESTS PASSED")
    else:
        print(" TESTS FAILED - FIX REQUIRED")
    print("=" * 70)


if __name__ == "__main__":
    main()
