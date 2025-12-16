"""
Test script to visualize FFT bar distribution.
Generates synthetic audio signals and shows the resulting bar heights.
"""
import numpy as np
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_test_engine(bar_count=15):
    """Create a minimal beat engine for testing."""
    class MockEngine:
        def __init__(self, bar_count):
            self._bar_count = bar_count
            self._np = np
            self._smooth_kernel = None
            self._band_cache_key = None
            self._band_edges = None
            self._work_bars = None
            self._zero_bars = None
            # Per-bar history for decay
            self._bar_history = np.zeros(bar_count, dtype="float32")
        
        def _get_zero_bars(self):
            if self._zero_bars is None or len(self._zero_bars) != self._bar_count:
                self._zero_bars = [0.0] * self._bar_count
            return self._zero_bars
        
        def _fft_to_bars(self, fft):
            """Current implementation from spotify_visualizer_widget.py"""
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
            except Exception:
                return self._get_zero_bars()

            n = int(mag.size)
            if n <= 0:
                return self._get_zero_bars()

            try:
                np.log1p(mag, out=mag)
                np.power(mag, 1.2, out=mag)

                if n > 4:
                    if self._smooth_kernel is None:
                        self._smooth_kernel = np.array([0.25, 0.5, 0.25], dtype="float32")
                    mag = np.convolve(mag, self._smooth_kernel, mode="same")
            except Exception:
                return self._get_zero_bars()

            # Logarithmic frequency binning - standard spectrum analyzer
            cache_key = (n, bands)
            try:
                if self._band_cache_key != cache_key:
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
                
                edges = self._band_edges
                arr = self._work_bars
                arr.fill(0.0)
                
                # Compute RMS for each frequency band (standard left-to-right)
                freq_values = np.zeros(bands, dtype="float32")
                for b in range(bands):
                    start = int(edges[b])
                    end = int(edges[b + 1])
                    if end <= start:
                        end = start + 1
                    if start < n and end <= n:
                        band_slice = mag[start:end]
                        if band_slice.size > 0:
                            freq_values[b] = np.sqrt(np.mean(band_slice ** 2))
                
                # CENTER-OUT mapping with noise floor subtraction
                # TUNED PARAMETERS - DO NOT CHANGE WITHOUT TESTING
                center = bands // 2
                raw_bass = float(np.mean(freq_values[:4])) if bands >= 4 else float(freq_values[0])
                raw_mid = float(np.mean(freq_values[4:10])) if bands >= 10 else raw_bass * 0.5
                raw_treble = float(np.mean(freq_values[10:])) if bands > 10 else raw_bass * 0.2
                
                noise_floor = 2.1
                expansion = 2.8
                
                bass_energy = max(0.0, (raw_bass - noise_floor) * expansion)
                mid_energy = max(0.0, (raw_mid - noise_floor * 0.4) * expansion)
                treble_energy = max(0.0, (raw_treble - noise_floor * 0.2) * expansion)
                
                for i in range(bands):
                    dist = abs(i - center) / float(center) if center > 0 else 0.0
                    gradient = (1.0 - dist) ** 2 * 0.85 + 0.15
                    base = bass_energy * gradient
                    mid_contrib = mid_energy * (1.0 - abs(dist - 0.5) * 2) * 0.3
                    treble_contrib = treble_energy * dist * 0.2
                    arr[i] = base + mid_contrib + treble_contrib
                
            except Exception:
                return self._get_zero_bars()

            # V1.2 STYLE SMOOTHING
            smoothing = 0.3
            decay_rate = 0.7
            
            for i in range(bands):
                cur = self._bar_history[i]
                tgt = arr[i]
                if tgt > cur:
                    new_val = cur + (tgt - cur) * (1.0 - smoothing * 0.5)
                else:
                    new_val = cur * decay_rate
                    if new_val < tgt:
                        new_val = tgt
                arr[i] = new_val
                self._bar_history[i] = new_val
            
            arr *= 0.8
            np.clip(arr, 0.0, 1.0, out=arr)
            return arr.tolist()
    
    return MockEngine(bar_count)


def generate_test_signal(signal_type, n_samples=2048, sample_rate=48000):
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


def run_reactivity_realistic(engine, fps=60, duration_sec=2.0):
    """Test reactivity with REAL timing like the actual app.
    
    This test simulates CONTINUOUS audio like real music:
    1. Runs at actual FPS with real time.sleep() delays
    2. Uses CONTINUOUS signal (always has audio, varying levels)
    3. Tracks variance to detect "stuck" bars
    4. Reports PASS/FAIL based on actual requirements
    
    KEY INSIGHT: Real music ALWAYS has a peak. The problem is that
    normalizing by peak means center is ALWAYS 1.0.
    """
    import time
    
    print(f"\n{'='*60}")
    print(f" REALISTIC REACTIVITY TEST ({fps} FPS, {duration_sec}s)")
    print(f"{'='*60}")
    
    # Generate base signal
    loud_samples = generate_test_signal("kick_drum")
    loud_fft = np.abs(np.fft.rfft(loud_samples))
    
    frame_time = 1.0 / fps
    n_frames = int(duration_sec * fps)
    
    # Track bar values over time
    center_values = []
    edge_values = []
    all_bars_history = []
    
    print(f"Running {n_frames} frames with {frame_time*1000:.1f}ms between frames...")
    print("Using CONTINUOUS audio with varying intensity (like real music)\n")
    
    for frame in range(n_frames):
        # Simulate CONTINUOUS audio with varying intensity
        # Use sine wave with period of 1 second, ranging from 0.1 to 1.0
        # This creates dramatic drops that should be visible
        intensity = 0.1 + 0.9 * (0.5 + 0.5 * np.sin(2 * np.pi * frame / fps))
        fft = loud_fft * intensity
        
        bars = engine._fft_to_bars(fft)
        
        center_val = bars[7] if len(bars) > 7 else 0
        edge_val = bars[0] if len(bars) > 0 else 0
        center_values.append(center_val)
        edge_values.append(edge_val)
        all_bars_history.append(list(bars))
        
        # Debug: print every 15 frames to see variation
        if frame % 15 == 0:
            print(f"  Frame {frame:3d} [int={intensity:.2f}]: center={center_val:.3f}, edge={edge_val:.3f}")
        
        # Real timing delay
        time.sleep(frame_time)
    
    # Analyze results
    center_arr = np.array(center_values)
    edge_arr = np.array(edge_values)
    
    center_min = float(center_arr.min())
    center_max = float(center_arr.max())
    center_range = center_max - center_min
    center_std = float(center_arr.std())
    
    edge_min = float(edge_arr.min())
    edge_max = float(edge_arr.max())
    edge_range = edge_max - edge_min
    edge_std = float(edge_arr.std())
    
    print("=" * 60)
    print(" RESULTS")
    print("=" * 60)
    print(f"Center bar (7): min={center_min:.2f}, max={center_max:.2f}, range={center_range:.2f}, std={center_std:.3f}")
    print(f"Edge bar (0):   min={edge_min:.2f}, max={edge_max:.2f}, range={edge_range:.2f}, std={edge_std:.3f}")
    
    # Check for problems
    problems = []
    
    # Problem 1: Center always at 1.0 (stuck)
    if center_min > 0.95:
        problems.append(f"FAIL: Center bar STUCK at max (min={center_min:.2f}, should drop below 0.5)")
    
    # Problem 2: Center never reaches 1.0
    if center_max < 0.9:
        problems.append(f"FAIL: Center bar never peaks (max={center_max:.2f}, should reach 0.9+)")
    
    # Problem 3: Not enough variation (bars don't move)
    if center_range < 0.3:
        problems.append(f"FAIL: Center bar not reactive (range={center_range:.2f}, should be 0.3+)")
    
    # Problem 4: Edge bars don't move (relative to their max value)
    # Edge bars are naturally lower, so check relative variation
    edge_relative_range = edge_range / max(edge_max, 0.01)
    if edge_relative_range < 0.3:  # 30% relative variation
        problems.append(f"FAIL: Edge bars not reactive (relative range={edge_relative_range:.2f}, should be 0.3+)")
    
    # Problem 5: Slope broken (edge higher than expected)
    last_bars = all_bars_history[-1]
    if len(last_bars) >= 15:
        if last_bars[0] > last_bars[7] * 0.5:
            problems.append(f"FAIL: Slope broken (edge={last_bars[0]:.2f} > 50% of center={last_bars[7]:.2f})")
    
    print()
    if problems:
        print("PROBLEMS DETECTED:")
        for p in problems:
            print(f"  ❌ {p}")
        print(f"\n>>> TEST FAILED ({len(problems)} issues) <<<")
        return False
    else:
        print("✓ Center bar peaks and drops appropriately")
        print("✓ Edge bars show variation")
        print("✓ Slope maintained (center > edges)")
        print("\n>>> TEST PASSED <<<")
        return True


def main():
    print("=" * 70)
    print(" SPOTIFY VISUALIZER FFT DISTRIBUTION TEST")
    print("=" * 70)
    
    engine = create_test_engine(bar_count=15)
    
    # Analyze band edges first
    analyze_band_edges(1024, 15)
    
    # Test with different signals (quick visual check)
    test_signals = [
        "kick_drum",
        "full_spectrum",
    ]
    
    for signal_type in test_signals:
        samples = generate_test_signal(signal_type)
        fft = np.abs(np.fft.rfft(samples))
        bars = engine._fft_to_bars(fft)
        visualize_bars(bars, f"Signal: {signal_type}")
    
    # REALISTIC reactivity test with real timing
    engine2 = create_test_engine(bar_count=15)
    passed = run_reactivity_realistic(engine2, fps=60, duration_sec=2.0)
    
    print("\n" + "=" * 70)
    if passed:
        print(" ALL TESTS PASSED")
    else:
        print(" TESTS FAILED - FIX REQUIRED")
    print("=" * 70)


if __name__ == "__main__":
    main()
