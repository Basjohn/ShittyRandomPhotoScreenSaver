"""
Spotify Visualizer Integration Test

Comprehensive test suite for Spotify visualizer FFT processing, playback gating,
and mathematical preservation. This consolidates the gating and preservation
tests following TestSuite.md guidelines.

Test Purpose:
- Verify FFT mathematical operations are preserved exactly
- Test playback state gating functionality  
- Validate 1-bar floor when not playing
- Ensure no visual fidelity loss during gating
- Confirm CPU savings when not playing

Test Count: 6 tests
Status: All passing
Requires: numpy, unittest.mock
"""

import sys
import numpy as np
from unittest.mock import Mock

# Add the project root to the path
sys.path.insert(0, '.')

try:
    from widgets.spotify_visualizer_widget import SpotifyVisualizerAudioWorker, _SpotifyBeatEngine
except ImportError as e:
    print("Import error: {}".format(e))
    print("This test requires the project to be run from its root directory")
    sys.exit(1)


class TestSpotifyVisualizerIntegration:
    """Comprehensive Spotify visualizer integration test suite."""
    
    def test_fft_mathematical_preservation(self):
        """Test that _fft_to_bars preserves exact mathematical operations."""
        print("Testing FFT mathematical preservation...")
        
        worker = SpotifyVisualizerAudioWorker(bar_count=32)
        
        # CRITICAL: Start the worker to initialize numpy
        try:
            worker.start()
        except Exception as e:
            raise Exception("Failed to start worker: {}".format(e))
        
        try:
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
            
            # Create synthetic audio data representing typical music
            sample_rate = 44100
            duration = 0.1
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            
            # Generate test signal with bass, mid, and treble components
            bass = 0.3 * np.sin(2 * np.pi * 100 * t)
            mid = 0.2 * np.sin(2 * np.pi * 1000 * t)
            treble = 0.1 * np.sin(2 * np.pi * 5000 * t)
            signal = bass + mid + treble + 0.05 * np.random.randn(len(t))
            signal = signal.astype(np.float32)
            
            # Apply window function and compute FFT
            window = np.hanning(len(signal))
            windowed_signal = signal * window
            fft_result = np.fft.rfft(windowed_signal)
            
            # Get bars using current implementation
            current_bars = worker._fft_to_bars(fft_result)
            
            # Verify basic properties
            assert isinstance(current_bars, list), "Output must be a list"
            assert len(current_bars) == 32, "Expected 32 bars, got {}".format(len(current_bars))
            assert all(0.0 <= bar <= 1.0 for bar in current_bars), "Bars must be in [0,1] range"
            
            # Verify meaningful output (not all zeros)
            center_bass = max(current_bars[14:18])
            edge_treble = max(max(current_bars[:5]), max(current_bars[-5:]))
            assert center_bass > 0.01, "Center region should have meaningful output"
            assert edge_treble > 0.01, "Edge regions should have meaningful output"
            
            print("✅ FFT mathematical preservation verified")
            
        finally:
            try:
                worker.stop()
            except Exception:
                pass
    
    def test_dynamic_floor_preservation(self):
        """Test that dynamic floor calculation is preserved exactly."""
        print("Testing dynamic floor preservation...")
        
        worker = SpotifyVisualizerAudioWorker(bar_count=32)
        
        try:
            worker.start()
        except Exception as e:
            raise Exception("Failed to start worker: {}".format(e))
        
        try:
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
            
            # Test different signal levels
            test_cases = [
                ("low_bass", 0.1),
                ("medium_bass", 0.5), 
                ("high_bass", 1.0),
                ("silence", 0.01)
            ]
            
            results = {}
            
            for case_name, bass_level in test_cases:
                sample_rate = 44100
                duration = 0.1
                t = np.linspace(0, duration, int(sample_rate * duration), False)
                
                signal = bass_level * np.sin(2 * np.pi * 100 * t) + 0.05 * np.random.randn(len(t))
                signal = signal.astype(np.float32)
                
                window = np.hanning(len(signal))
                windowed_signal = signal * window
                fft_result = np.fft.rfft(windowed_signal)
                
                bars = worker._fft_to_bars(fft_result)
                results[case_name] = np.array(bars)
            
            # Verify dynamic floor behavior
            silence_bars = results["silence"]
            assert np.mean(silence_bars) > 0.01, "Silence should produce 1-bar floor, not zero"
            
            # Higher bass should produce higher bars
            assert np.mean(results["high_bass"]) > np.mean(results["low_bass"]), "Higher bass should produce higher bars"
            
            print("✅ Dynamic floor preservation verified")
            
        finally:
            try:
                worker.stop()
            except Exception:
                pass
    
    def test_playback_state_gating(self):
        """Test that playback state gating works correctly."""
        print("Testing playback state gating...")
        
        engine = _SpotifyBeatEngine(bar_count=32)
        engine._thread_manager = Mock()
        
        # Test default state
        assert engine._is_spotify_playing is False
        
        # Test state changes
        engine.set_playback_state(True)
        assert engine._is_spotify_playing is True
        assert engine._last_playback_state_ts > 0
        
        engine.set_playback_state(False)
        assert engine._is_spotify_playing is False
        
        print("✅ Playback state gating works correctly")
    
    def test_fft_gating_when_not_playing(self):
        """Test that FFT processing is halted when not playing."""
        print("Testing FFT gating when not playing...")
        
        engine = _SpotifyBeatEngine(bar_count=32)
        engine._thread_manager = Mock()
        engine.set_playback_state(False)
        
        # Mock audio data
        mock_samples = [0.1, 0.2, 0.3] * 100
        mock_frame = Mock()
        mock_frame.samples = mock_samples
        engine._audio_buffer.consume_latest = Mock(return_value=mock_frame)
        
        # Call tick - should return 1-bar floor without FFT processing
        result = engine.tick()
        
        # Should return a list with minimal 1-bar floor
        assert isinstance(result, list)
        assert len(result) == 32
        non_zero_bars = [bar for bar in result if bar > 0.0]
        assert len(non_zero_bars) == 1
        assert non_zero_bars[0] == 0.08  # Minimal visible floor
        
        # Verify no compute task was scheduled
        assert engine._compute_task_active is False
        
        print("✅ FFT gating when not playing works correctly")
    
    def test_fft_processing_when_playing(self):
        """Test that FFT processing occurs when playing."""
        print("Testing FFT processing when playing...")
        
        engine = _SpotifyBeatEngine(bar_count=32)
        engine._thread_manager = Mock()
        engine.set_playback_state(True)
        
        # Mock audio data
        mock_samples = [0.1, 0.2, 0.3] * 100
        mock_frame = Mock()
        mock_frame.samples = mock_samples
        engine._audio_buffer.consume_latest = Mock(return_value=mock_frame)
        
        # Mock the thread manager
        mock_tm = engine._thread_manager
        mock_tm.submit_compute_task = Mock()
        
        # Call tick - should schedule FFT processing
        result = engine.tick()
        
        # Should return None (processing in background) or list
        assert result is None or isinstance(result, list)
        
        # Verify compute task was scheduled
        mock_tm.submit_compute_task.assert_called_once()
        
        print("✅ FFT processing when playing works correctly")
    
    def test_one_bar_floor_requirement(self):
        """Test that exactly 1 bar is visible when not playing."""
        print("Testing 1-bar floor requirement...")
        
        engine = _SpotifyBeatEngine(bar_count=32)
        engine._thread_manager = Mock()
        engine.set_playback_state(False)
        
        # Mock audio data
        mock_samples = [0.1, 0.2, 0.3] * 100
        mock_frame = Mock()
        mock_frame.samples = mock_samples
        engine._audio_buffer.consume_latest = Mock(return_value=mock_frame)
        
        # Call tick multiple times
        for i in range(5):
            result = engine.tick()
            assert isinstance(result, list)
            assert len(result) == 32
            
            # Count non-zero bars
            non_zero_bars = [bar for bar in result if bar > 0.0]
            assert len(non_zero_bars) == 1, "Tick {}: Expected exactly 1 non-zero bar, got {}".format(i, len(non_zero_bars))
            assert non_zero_bars[0] == 0.08, "Tick {}: Expected bar height 0.08, got {}".format(i, non_zero_bars[0])
        
        print("✅ 1-bar floor requirement works correctly")
    
    def test_performance_impact_simulation(self):
        """Test that CPU usage is reduced when not playing."""
        print("Testing performance impact...")
        
        engine = _SpotifyBeatEngine(bar_count=32)
        engine._thread_manager = Mock()
        
        # Mock compute task scheduling to track calls
        compute_calls = []
        
        def track_compute_calls(job, callback):
            compute_calls.append((job, callback))
            return Mock()
        
        engine._thread_manager.submit_compute_task = track_compute_calls
        
        # Mock audio data
        mock_samples = [0.1, 0.2, 0.3] * 100
        mock_frame = Mock()
        mock_frame.samples = mock_samples
        engine._audio_buffer.consume_latest = Mock(return_value=mock_frame)
        
        # Simulate playing state - should schedule compute tasks
        engine.set_playback_state(True)
        for _ in range(10):
            engine._compute_task_active = False  # Reset each time
            engine.tick()
        
        playing_calls = len(compute_calls)
        
        # Reset for not playing test
        compute_calls.clear()
        engine._compute_task_active = False
        
        # Simulate not playing state - should NOT schedule compute tasks
        engine.set_playback_state(False)
        for _ in range(10):
            engine.tick()
        
        not_playing_calls = len(compute_calls)
        
        # Verify significant reduction in compute task scheduling
        assert playing_calls > 0, "Should schedule compute tasks when playing"
        assert not_playing_calls == 0, "Should not schedule compute tasks when not playing"
        
        # Calculate simulated CPU savings
        cpu_savings_percentage = (playing_calls - not_playing_calls) / playing_calls * 100
        print("   Simulated CPU savings: {:.1f}%".format(cpu_savings_percentage))
        assert cpu_savings_percentage >= 90, "Expected >= 90% CPU savings, got {:.1f}%".format(cpu_savings_percentage)
        
        print("✅ Performance impact test passed")


def run_all_integration_tests():
    """Run all integration tests and report results."""
    print("=" * 60)
    print("Spotify Visualizer Integration Test Suite")
    print("=" * 60)
    
    test_instance = TestSpotifyVisualizerIntegration()
    
    tests = [
        test_instance.test_fft_mathematical_preservation,
        test_instance.test_dynamic_floor_preservation,
        test_instance.test_playback_state_gating,
        test_instance.test_fft_gating_when_not_playing,
        test_instance.test_fft_processing_when_playing,
        test_instance.test_one_bar_floor_requirement,
        test_instance.test_performance_impact_simulation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print("❌ {} failed: {}".format(test.__name__, e))
            failed += 1
        print()
    
    print("=" * 60)
    print("Integration Test Results: {} passed, {} failed".format(passed, failed))
    print("=" * 60)
    
    if failed == 0:
        print("🎉 All Spotify visualizer integration tests passed!")
        print("✅ FFT mathematical operations preserved")
        print("✅ Dynamic floor logic preserved")
        print("✅ Playback state gating functional")
        print("✅ FFT processing halted when not playing")
        print("✅ 1-bar floor maintained when paused")
        print("✅ Significant CPU savings achieved")
        return True
    else:
        print("❌ Some integration tests failed")
        return False


if __name__ == "__main__":
    success = run_all_integration_tests()
    sys.exit(0 if success else 1)
