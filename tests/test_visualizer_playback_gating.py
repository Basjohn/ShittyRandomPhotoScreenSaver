"""
Visualizer Playback Gating Test

Tests that the FFT processing is properly gated when Spotify is not playing,
ensuring significant CPU savings while maintaining visual fidelity.
"""

import pytest
import time
from unittest.mock import Mock
from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine


class _GatingLane:
    def __init__(self, callback) -> None:
        self.callback = callback
        self.submits = 0
        self.is_stopped = False

    def submit(self, payload) -> bool:
        if self.is_stopped:
            return False
        self.submits += 1
        # Playback-gating tests only care whether analysis work is admitted.
        # Complete with a failed result so the engine releases its in-flight slot
        # without invoking FFT/DSP in this unit test.
        self.callback(Mock(success=False, result=None), payload=payload)
        return True

    def cancel_pending(self) -> int:
        return 0

    def stop(self) -> None:
        self.is_stopped = True


class _GatingThreadManager:
    supports_persistent_compute_lanes = True

    def __init__(self) -> None:
        self.lane: _GatingLane | None = None
        self.general_submits = 0

    def create_compute_lane(self, _worker, callback, *, lane_id, category):
        assert str(lane_id).startswith("spotify_visualizer.audio_analysis:")
        assert category == "visualizer.audio_analysis"
        self.lane = _GatingLane(callback)
        return self.lane

    def submit_compute_task(self, *_args, **_kwargs):
        self.general_submits += 1
        raise AssertionError("audio analysis must not use generic Future tasks")


class TestVisualizerPlaybackGating:
    """Test suite for visualizer playback gating functionality."""
    
    @pytest.fixture
    def beat_engine(self):
        """Create a beat engine with the destination persistent analysis lane."""
        engine = _SpotifyBeatEngine(bar_count=32)
        manager = _GatingThreadManager()
        engine.set_thread_manager(manager)
        engine._test_thread_manager = manager
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
        
        # Call tick - should return a subtle idle seed without FFT processing
        result = beat_engine.tick()
        
        # Should return a list with low-energy idle presentation
        assert isinstance(result, list)
        assert len(result) == 32
        non_zero_bars = [bar for bar in result if bar > 0.0]
        assert len(non_zero_bars) > 8
        assert max(non_zero_bars) < 0.05
        
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
        
        manager = beat_engine._test_thread_manager
        assert manager.lane is not None
        before = manager.lane.submits

        # Call tick - playing state should admit one packet to the persistent lane.
        result = beat_engine.tick()

        assert result is None or isinstance(result, list)
        assert manager.lane.submits == before + 1
        assert manager.general_submits == 0
    
    def test_state_transition_handling(self, beat_engine):
        """Test that state transitions are handled correctly."""
        # Start with playing state
        beat_engine.set_playback_state(True)
        
        # Mock some audio data
        mock_samples = [0.1, 0.2, 0.3] * 100
        mock_frame = Mock()
        mock_frame.samples = mock_samples
        beat_engine._audio_buffer.consume_latest = Mock(return_value=mock_frame)
        
        manager = beat_engine._test_thread_manager
        assert manager.lane is not None

        # Process while playing: one lane packet is admitted. The unit lane
        # completes immediately with a failed result, so no active slot lingers.
        before = manager.lane.submits
        beat_engine.tick()
        assert manager.lane.submits == before + 1
        assert beat_engine._compute_task_active is False

        # Transition to not playing. Idle presentation must not admit analysis.
        beat_engine.set_playback_state(False)
        result = beat_engine.tick()
        assert isinstance(result, list)
        assert len([bar for bar in result if bar > 0.0]) > 8
        assert manager.lane.submits == before + 1
        assert beat_engine._compute_task_active is False
    
    def test_idle_seed_requirement(self, beat_engine):
        """Test that paused idle presentation stays visible but low-energy."""
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
            
            non_zero_bars = [bar for bar in result if bar > 0.0]
            assert len(non_zero_bars) > 8, f"Expected broad idle seed, got {len(non_zero_bars)} bars"
            assert max(non_zero_bars) < 0.05, f"Expected low-energy idle seed, got peak {max(non_zero_bars)}"

    def test_paused_idle_seed_survives_post_pause_silence_decay(self, beat_engine):
        """Paused idle bars must not be zeroed by the playing-only silence decay path."""
        beat_engine.set_playback_state(False)
        beat_engine._audio_buffer.consume_latest = Mock(return_value=None)
        beat_engine._last_audio_ts = time.time() - 1.0

        result = beat_engine.tick()

        assert isinstance(result, list)
        assert len(result) == 32
        assert max(result) > 0.0
        assert max(beat_engine._smoothed_bars) > 0.0

    def test_paused_idle_seed_survives_worker_stop_after_warm_grace(self, beat_engine):
        """Idle presentation must persist even when warm capture grace expires."""
        beat_engine.set_playback_state(False)
        beat_engine._audio_buffer.consume_latest = Mock(return_value=None)
        beat_engine._last_audio_ts = time.time() - 1.0
        beat_engine._capture_keepalive_deadline = time.time() - 0.1
        beat_engine._audio_worker.stop = Mock()

        result = beat_engine.tick()

        beat_engine._audio_worker.stop.assert_called_once()
        assert isinstance(result, list)
        assert max(result) > 0.0

    def test_paused_warm_audio_frame_does_not_overwrite_idle_waveform(self, beat_engine):
        """Warm capture frames after pause must not poison the idle waveform."""
        beat_engine.set_playback_state(False)
        mock_frame = Mock()
        mock_frame.samples = [1.0] * 300
        beat_engine._audio_buffer.consume_latest = Mock(return_value=mock_frame)

        result = beat_engine.tick()
        waveform = beat_engine.get_waveform()

        assert isinstance(result, list)
        beat_engine._audio_buffer.consume_latest.assert_called_once()
        assert max(abs(value) for value in waveform) < 0.08
        assert max(result) < 0.05
    
    def test_performance_impact_simulation(self, beat_engine):
        """Paused playback admits no audio-analysis lane work."""
        manager = beat_engine._test_thread_manager
        assert manager.lane is not None

        mock_samples = [0.1, 0.2, 0.3] * 100
        mock_frame = Mock()
        mock_frame.samples = mock_samples
        beat_engine._audio_buffer.consume_latest = Mock(return_value=mock_frame)

        beat_engine.set_playback_state(True)
        before = manager.lane.submits
        for _ in range(10):
            beat_engine.tick()
        playing_calls = manager.lane.submits - before

        beat_engine.set_playback_state(False)
        before_paused = manager.lane.submits
        for _ in range(10):
            beat_engine.tick()
        not_playing_calls = manager.lane.submits - before_paused

        assert playing_calls > 0, "playing state must admit analysis packets"
        assert not_playing_calls == 0, "paused state must not admit analysis packets"
        assert manager.general_submits == 0

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
    
    # Test idle seed requirement
    test_instance.test_idle_seed_requirement(engine)
    
    # Test performance impact
    test_instance.test_performance_impact_simulation(engine)
    
    # Test sparse polling
    test_instance.test_sparse_polling_simulation(engine)
    
    print("✅ All visualizer playback gating tests passed")


if __name__ == "__main__":
    test_visualizer_gating_integration()
    print("✅ Visualizer playback gating implementation verified")
