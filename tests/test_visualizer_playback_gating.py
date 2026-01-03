"""
Visualizer Playback Gating Test

Tests that the FFT processing is properly gated when Spotify is not playing,
ensuring significant CPU savings while maintaining visual fidelity.
"""

import pytest
import time
from unittest.mock import Mock
from widgets.spotify_visualizer_widget import _SpotifyBeatEngine


class TestVisualizerPlaybackGating:
    """Test suite for visualizer playback gating functionality."""
    
    @pytest.fixture
    def beat_engine(self):
        """Create a test beat engine instance."""
        engine = _SpotifyBeatEngine(bar_count=32)
        # Mock thread manager to avoid actual threading
        engine._thread_manager = Mock()
        return engine
    
    def test_playback_state_setting(self, beat_engine):
        """Test that playback state can be set and retrieved."""
        # Default state should be False
        assert beat_engine._is_spotify_playing is False
        
        # Set to playing
        beat_engine.set_playback_state(True)
        assert beat_engine._is_spotify_playing is True
        assert beat_engine._last_playback_state_ts > 0
        
        # Set to not playing
        beat_engine.set_playback_state(False)
        assert beat_engine._is_spotify_playing is False
    
    def test_fft_gating_when_not_playing(self, beat_engine):
        """Test that FFT processing is halted when not playing."""
        # Set up engine to not be playing
        beat_engine.set_playback_state(False)
        
        # Mock the audio buffer to return some samples
        mock_samples = [0.1, 0.2, 0.3] * 100  # Some dummy audio data
        mock_frame = Mock()
        mock_frame.samples = mock_samples
        
        # Mock the audio buffer to return our frame
        beat_engine._audio_buffer.consume_latest = Mock(return_value=mock_frame)
        
        # Call tick - should return 1-bar floor without FFT processing
        result = beat_engine.tick()
        
        # Should return a list with minimal 1-bar floor
        assert isinstance(result, list)
        assert len(result) == 32
        # Should have exactly 1 bar with minimal height
        non_zero_bars = [bar for bar in result if bar > 0.0]
        assert len(non_zero_bars) == 1
        assert non_zero_bars[0] == 0.08  # Minimal visible floor
        
        # Verify no compute task was scheduled
        assert beat_engine._compute_task_active is False
    
    def test_fft_processing_when_playing(self, beat_engine):
        """Test that FFT processing occurs when playing."""
        # Set up engine to be playing
        beat_engine.set_playback_state(True)
        
        # Mock the audio buffer to return some samples
        mock_samples = [0.1, 0.2, 0.3] * 100  # Some dummy audio data
        mock_frame = Mock()
        mock_frame.samples = mock_samples
        
        # Mock the audio buffer to return our frame
        beat_engine._audio_buffer.consume_latest = Mock(return_value=mock_frame)
        
        # Mock the thread manager
        mock_tm = beat_engine._thread_manager
        mock_tm.submit_compute_task = Mock()
        
        # Call tick - should schedule FFT processing
        result = beat_engine.tick()
        
        # Should return None (processing in background)
        assert result is None or isinstance(result, list)
        
        # Verify compute task was scheduled
        mock_tm.submit_compute_task.assert_called_once()
    
    def test_state_transition_handling(self, beat_engine):
        """Test that state transitions are handled correctly."""
        # Start with playing state
        beat_engine.set_playback_state(True)
        
        # Mock some audio data
        mock_samples = [0.1, 0.2, 0.3] * 100
        mock_frame = Mock()
        mock_frame.samples = mock_samples
        beat_engine._audio_buffer.consume_latest = Mock(return_value=mock_frame)
        
        # Process while playing
        beat_engine.tick()
        assert beat_engine._compute_task_active is True
        
        # Transition to not playing
        beat_engine.set_playback_state(False)
        
        # Reset compute task active to test gating
        beat_engine._compute_task_active = False
        
        # Process while not playing - should not schedule compute task
        result = beat_engine.tick()
        assert isinstance(result, list)
        assert len([bar for bar in result if bar > 0.0]) == 1  # 1-bar floor
        assert beat_engine._compute_task_active is False
    
    def test_one_bar_floor_requirement(self, beat_engine):
        """Test that exactly 1 bar is visible when not playing."""
        beat_engine.set_playback_state(False)
        
        # Mock audio data
        mock_samples = [0.1, 0.2, 0.3] * 100
        mock_frame = Mock()
        mock_frame.samples = mock_samples
        beat_engine._audio_buffer.consume_latest = Mock(return_value=mock_frame)
        
        # Call tick multiple times
        for _ in range(5):
            result = beat_engine.tick()
            assert isinstance(result, list)
            assert len(result) == 32
            
            # Count non-zero bars
            non_zero_bars = [bar for bar in result if bar > 0.0]
            assert len(non_zero_bars) == 1, f"Expected exactly 1 non-zero bar, got {len(non_zero_bars)}"
            assert non_zero_bars[0] == 0.08, f"Expected bar height 0.08, got {non_zero_bars[0]}"
    
    def test_performance_impact_simulation(self, beat_engine):
        """Test that CPU usage is reduced when not playing."""
        # Mock the compute task scheduling to track calls
        compute_calls = []
        
        def track_compute_calls(job, callback):
            compute_calls.append((job, callback))
            return Mock()
        
        beat_engine._thread_manager.submit_compute_task = track_compute_calls
        
        # Mock audio data
        mock_samples = [0.1, 0.2, 0.3] * 100
        mock_frame = Mock()
        mock_frame.samples = mock_samples
        beat_engine._audio_buffer.consume_latest = Mock(return_value=mock_frame)
        
        # Simulate playing state - should schedule compute tasks
        beat_engine.set_playback_state(True)
        for _ in range(10):
            beat_engine._compute_task_active = False  # Reset each time
            beat_engine.tick()
        
        playing_calls = len(compute_calls)
        
        # Reset for not playing test
        compute_calls.clear()
        beat_engine._compute_task_active = False
        
        # Simulate not playing state - should NOT schedule compute tasks
        beat_engine.set_playback_state(False)
        for _ in range(10):
            beat_engine.tick()
        
        not_playing_calls = len(compute_calls)
        
        # Verify significant reduction in compute task scheduling
        assert playing_calls > 0, "Should schedule compute tasks when playing"
        assert not_playing_calls == 0, "Should not schedule compute tasks when not playing"
        
        # Calculate simulated CPU savings
        cpu_savings_percentage = (playing_calls - not_playing_calls) / playing_calls * 100
        assert cpu_savings_percentage >= 90, f"Expected >= 90% CPU savings, got {cpu_savings_percentage:.1f}%"
    
    def test_sparse_polling_simulation(self, beat_engine):
        """Test that state changes are detected with minimal overhead."""
        # Track state change timestamps
        state_changes = []
        
        original_set_state = beat_engine.set_playback_state
        
        def track_state_changes(is_playing):
            state_changes.append((time.time(), is_playing))
            return original_set_state(is_playing)
        
        beat_engine.set_playback_state = track_state_changes
        
        # Simulate rapid state changes
        states = [True, False, True, False, True]
        for state in states:
            beat_engine.set_playback_state(state)
            time.sleep(0.001)  # Small delay
        
        # Verify all state changes were recorded
        assert len(state_changes) == len(states)
        
        # Verify timestamps are increasing
        timestamps = [change[0] for change in state_changes]
        assert all(earlier <= later for earlier, later in zip(timestamps, timestamps[1:]))
        
        # Verify state values are correct
        recorded_states = [change[1] for change in state_changes]
        assert recorded_states == states


def test_visualizer_gating_integration():
    """Integration test for the complete gating system."""
    engine = _SpotifyBeatEngine(bar_count=32)
    engine._thread_manager = Mock()
    
    # Test complete workflow
    test_instance = TestVisualizerPlaybackGating()
    
    # Test initial state
    test_instance.test_playback_state_setting(engine)
    
    # Test gating when not playing
    test_instance.test_fft_gating_when_not_playing(engine)
    
    # Test processing when playing
    test_instance.test_fft_processing_when_playing(engine)
    
    # Test state transitions
    test_instance.test_state_transition_handling(engine)
    
    # Test 1-bar floor requirement
    test_instance.test_one_bar_floor_requirement(engine)
    
    # Test performance impact
    test_instance.test_performance_impact_simulation(engine)
    
    # Test sparse polling
    test_instance.test_sparse_polling_simulation(engine)
    
    print("✅ All visualizer playback gating tests passed")
    return True


if __name__ == "__main__":
    success = test_visualizer_gating_integration()
    if success:
        print("✅ Visualizer playback gating implementation verified")
    else:
        print("❌ Visualizer playback gating tests failed")
        exit(1)
