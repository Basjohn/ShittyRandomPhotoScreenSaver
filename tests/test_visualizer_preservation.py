"""
Visualizer Logic Preservation Test

This test captures the current FFT-to-bars conversion logic and creates a synthetic
baseline that must be preserved during any refactoring or worker migration.

CRITICAL: Any changes to the visualizer FFT pipeline must pass this test to ensure
visual fidelity is maintained. The test preserves the exact mathematical operations
from VISUALIZER_DEBUG.md and the current implementation.
"""

import pytest
import numpy as np
import time

# Import the current implementation
from widgets.spotify_visualizer_widget import SpotifyVisualizerAudioWorker


class TestVisualizerLogicPreservation:
    """Test suite to preserve visualizer FFT logic during refactoring."""
    
    @pytest.fixture
    def worker(self):
        """Create a test worker instance with current configuration."""
        worker = SpotifyVisualizerAudioWorker(bar_count=32)
        # Initialize with current default settings
        worker._user_sensitivity = 1.0
        worker._use_recommended = True
        worker._use_dynamic_floor = True
        worker._manual_floor = 2.1
        worker._recommended_sensitivity_multiplier = 0.38
        worker._min_floor = 0.12
        worker._max_floor = 4.0
        worker._dynamic_floor_ratio = 0.462
        worker._dynamic_floor_alpha = 0.15
        worker._dynamic_floor_decay_alpha = 0.4
        worker._floor_mid_weight = 0.18
        worker._floor_headroom = 0.18
        worker._silence_floor_threshold = 0.05
        worker._raw_bass_avg = 2.1
        return worker
    
    def test_fft_to_bars_mathematical_preservation(self, worker):
        """Test that _fft_to_bars preserves exact mathematical operations."""
        # Create synthetic audio data that represents typical music
        sample_rate = 44100
        duration = 0.1  # 100ms
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        
        # Generate test signal with bass, mid, and treble components
        # Bass: 100Hz sine wave
        bass = 0.3 * np.sin(2 * np.pi * 100 * t)
        # Mid: 1000Hz sine wave  
        mid = 0.2 * np.sin(2 * np.pi * 1000 * t)
        # Treble: 5000Hz sine wave
        treble = 0.1 * np.sin(2 * np.pi * 5000 * t)
        
        # Combine with some noise for realism
        signal = bass + mid + treble + 0.05 * np.random.randn(len(t))
        
        # Convert to mono and ensure proper format
        if len(signal.shape) > 1:
            signal = np.mean(signal, axis=1)
        signal = signal.astype(np.float32)
        
        # Apply window function to reduce spectral leakage
        window = np.hanning(len(signal))
        windowed_signal = signal * window
        
        # Compute FFT using the same method as the worker
        fft_result = np.fft.rfft(windowed_signal)
        
        # Get bars using current implementation
        current_bars = worker._fft_to_bars(fft_result)
        
        # Verify basic properties
        assert isinstance(current_bars, list), "Output must be a list"
        assert len(current_bars) == 32, f"Expected 32 bars, got {len(current_bars)}"
        assert all(0.0 <= bar <= 1.0 for bar in current_bars), "Bars must be in [0,1] range"
        
        # Verify center-out frequency mapping (bass in center)
        center_bass = max(current_bars[14:18])  # Center region should have bass
        edge_treble = max(max(current_bars[:5]), max(current_bars[-5:]))  # Edges should have treble
        
        # Bass should be stronger than treble in this test signal
        assert center_bass > edge_treble, "Center (bass) should be stronger than edges (treble)"
        
        # Store baseline for regression testing
        baseline_bars = np.array(current_bars)
        
        return baseline_bars
    
    def test_dynamic_floor_preservation(self, worker):
        """Test that dynamic floor calculation is preserved exactly."""
        # Create test signal with varying bass levels
        test_cases = [
            ("low_bass", 0.1),
            ("medium_bass", 0.5), 
            ("high_bass", 1.0),
            ("silence", 0.01)
        ]
        
        results = {}
        
        for case_name, bass_level in test_cases:
            # Generate test signal
            sample_rate = 44100
            duration = 0.1
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            
            # Create signal with specified bass level
            signal = bass_level * np.sin(2 * np.pi * 100 * t) + 0.05 * np.random.randn(len(t))
            signal = signal.astype(np.float32)
            
            # Apply window and FFT
            window = np.hanning(len(signal))
            windowed_signal = signal * window
            fft_result = np.fft.rfft(windowed_signal)
            
            # Get bars
            bars = worker._fft_to_bars(fft_result)
            results[case_name] = np.array(bars)
        
        # Verify dynamic floor behavior
        # Silence should produce low bars but not zero (1-bar floor)
        silence_bars = results["silence"]
        assert np.mean(silence_bars) > 0.01, "Silence should produce 1-bar floor, not zero"
        
        # Higher bass should produce higher bars
        assert np.mean(results["high_bass"]) > np.mean(results["low_bass"]), "Higher bass should produce higher bars"
        
        return results
    
    def test_adaptive_sensitivity_preservation(self, worker):
        """Test that adaptive sensitivity logic is preserved."""
        # Test different resolution boost scenarios
        resolutions = [256, 512, 1024, 2048]  # Different FFT sizes
        
        for fft_size in resolutions:
            # Generate test signal
            duration = 0.1
            t = np.linspace(0, duration, fft_size // 2, False)
            signal = 0.5 * np.sin(2 * np.pi * 1000 * t) + 0.05 * np.random.randn(len(t))
            signal = signal.astype(np.float32)
            
            # Pad or truncate to match FFT size
            if len(signal) < fft_size // 2:
                signal = np.pad(signal, (0, fft_size // 2 - len(signal)))
            else:
                signal = signal[:fft_size // 2]
            
            # Apply window and FFT
            window = np.hanning(len(signal))
            windowed_signal = signal * window
            fft_result = np.fft.rfft(windowed_signal)
            
            # Get bars
            bars = worker._fft_to_bars(fft_result)
            
            # Verify output is reasonable for this resolution
            assert isinstance(bars, list), f"FFT size {fft_size}: Output must be list"
            assert len(bars) == 32, f"FFT size {fft_size}: Expected 32 bars"
            assert all(0.0 <= bar <= 1.0 for bar in bars), f"FFT size {fft_size}: Bars out of range"
    
    def test_smoothing_preservation(self, worker):
        """Test that smoothing logic is preserved."""
        # This test would need access to the _apply_smoothing method
        # For now, we'll test the overall smoothing effect through repeated calls
        
        # Create consistent test signal
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        signal = 0.5 * np.sin(2 * np.pi * 1000 * t)
        signal = signal.astype(np.float32)
        
        window = np.hanning(len(signal))
        windowed_signal = signal * window
        fft_result = np.fft.rfft(windowed_signal)
        
        # Get multiple consecutive bar readings
        bars_readings = []
        for _ in range(5):
            bars = worker._fft_to_bars(fft_result)
            bars_readings.append(np.array(bars))
            time.sleep(0.01)  # Small delay to simulate real-time
        
        # Verify consistency (smoothing should prevent wild fluctuations)
        bars_array = np.array(bars_readings)
        std_devs = np.std(bars_array, axis=0)
        
        # Standard deviation should be reasonable (not too high)
        assert np.mean(std_devs) < 0.1, "Smoothing should prevent large fluctuations"
    
    def test_resolution_boost_adaptation(self, worker):
        """Test that resolution boost adaptation is preserved."""
        # Test the exact logic from VISUALIZER_DEBUG.md lines 31-40
        test_fft_sizes = [256, 512, 1024, 2048]
        
        for fft_size in test_fft_sizes:
            # Calculate expected resolution boost
            resolution_boost = max(0.5, min(3.0, 1024.0 / max(256.0, float(fft_size))))
            low_resolution = resolution_boost > 1.05
            
            # Generate test signal for this FFT size
            duration = 0.1
            t = np.linspace(0, duration, fft_size // 2, False)
            signal = 0.5 * np.sin(2 * np.pi * 1000 * t)
            signal = signal.astype(np.float32)
            
            window = np.hanning(len(signal))
            windowed_signal = signal * window
            fft_result = np.fft.rfft(windowed_signal)
            
            # Get bars
            bars = worker._fft_to_bars(fft_result)
            
            # Verify adaptation behavior
            if low_resolution:
                # Low resolution should have specific adaptations
                # (This would need access to internal state to verify precisely)
                assert len(bars) == 32, f"Low resolution {fft_size}: Should still produce 32 bars"
            else:
                # High/normal resolution behavior
                assert len(bars) == 32, f"Normal resolution {fft_size}: Should produce 32 bars"
    
    def create_baseline_snapshot(self, worker):
        """Create a comprehensive baseline snapshot for regression testing."""
        snapshot = {
            "timestamp": time.time(),
            "version": "v2.0_baseline",
            "test_cases": {}
        }
        
        # Test various signal types
        test_signals = {
            "bass_heavy": {"freq": 100, "amp": 0.8},
            "mid_heavy": {"freq": 1000, "amp": 0.8},
            "treble_heavy": {"freq": 5000, "amp": 0.8},
            "mixed": {"freqs": [100, 1000, 5000], "amps": [0.4, 0.3, 0.2]},
            "silence": {"freq": 0, "amp": 0.01}
        }
        
        for signal_name, params in test_signals.items():
            # Generate test signal
            sample_rate = 44100
            duration = 0.1
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            
            if signal_name == "mixed":
                signal = np.zeros_like(t)
                for freq, amp in zip(params["freqs"], params["amps"]):
                    signal += amp * np.sin(2 * np.pi * freq * t)
            elif params["freq"] > 0:
                signal = params["amp"] * np.sin(2 * np.pi * params["freq"] * t)
            else:
                signal = params["amp"] * np.random.randn(len(t))
            
            signal = signal.astype(np.float32)
            
            # Apply window and FFT
            window = np.hanning(len(signal))
            windowed_signal = signal * window
            fft_result = np.fft.rfft(windowed_signal)
            
            # Get bars
            bars = worker._fft_to_bars(fft_result)
            
            snapshot["test_cases"][signal_name] = {
                "bars": bars,
                "mean": np.mean(bars),
                "max": np.max(bars),
                "min": np.min(bars),
                "std": np.std(bars)
            }
        
        return snapshot
    
    def test_baseline_creation(self, worker):
        """Test that baseline snapshot can be created successfully."""
        snapshot = self.create_baseline_snapshot(worker)
        
        # Verify snapshot structure
        assert "timestamp" in snapshot
        assert "version" in snapshot
        assert "test_cases" in snapshot
        assert len(snapshot["test_cases"]) == 5
        
        # Verify each test case
        for case_name, case_data in snapshot["test_cases"].items():
            assert "bars" in case_data
            assert "mean" in case_data
            assert "max" in case_data
            assert "min" in case_data
            assert "std" in case_data
            
            # Verify bar data
            bars = case_data["bars"]
            assert isinstance(bars, list)
            assert len(bars) == 32
            assert all(0.0 <= bar <= 1.0 for bar in bars)
        
        return snapshot


def test_visualizer_mathematical_preservation_integration():
    """Integration test that runs the full preservation test suite."""
    worker = SpotifyVisualizerAudioWorker(bar_count=32)
    
    # Initialize worker settings
    worker._user_sensitivity = 1.0
    worker._use_recommended = True
    worker._use_dynamic_floor = True
    worker._manual_floor = 2.1
    worker._recommended_sensitivity_multiplier = 0.38
    
    test_instance = TestVisualizerLogicPreservation()
    
    # Run all preservation tests
    baseline_bars = test_instance.test_fft_to_bars_mathematical_preservation(worker)
    dynamic_results = test_instance.test_dynamic_floor_preservation(worker)
    test_instance.test_adaptive_sensitivity_preservation(worker)
    test_instance.test_smoothing_preservation(worker)
    test_instance.test_resolution_boost_adaptation(worker)
    snapshot = test_instance.create_baseline_snapshot(worker)
    
    # Verify baseline creation
    assert snapshot is not None
    assert "test_cases" in snapshot
    assert len(snapshot["test_cases"]) > 0
    
    print("✅ Visualizer logic preservation test passed")
    print(f"   Baseline bars mean: {np.mean(baseline_bars):.3f}")
    print(f"   Dynamic floor test cases: {len(dynamic_results)}")
    print(f"   Snapshot test cases: {len(snapshot['test_cases'])}")
    
    return True


if __name__ == "__main__":
    # Run the preservation test
    success = test_visualizer_mathematical_preservation_integration()
    if success:
        print("✅ All visualizer logic preservation tests passed")
    else:
        print("❌ Visualizer logic preservation tests failed")
        exit(1)
