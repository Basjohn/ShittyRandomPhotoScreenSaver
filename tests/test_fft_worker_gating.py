"""Regression tests for FFT worker gating behavior.

These tests verify:
- FFT processing is gated when Spotify is not playing
- FFT processing resumes when Spotify starts playing
- Minimal floor bar is shown when paused (1-segment visibility)
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock


class TestFFTWorkerGating:
    """Tests for FFT worker gating when media is not playing."""

    def test_set_playback_state_updates_flag(self):
        """Verify set_playback_state updates the gating flag."""
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
        
        engine = _SpotifyBeatEngine(bar_count=16)
        
        # Initially should be False
        assert engine._is_spotify_playing is False
        
        # Set to playing
        engine.set_playback_state(True)
        assert engine._is_spotify_playing is True
        
        # Set to paused
        engine.set_playback_state(False)
        assert engine._is_spotify_playing is False

    def test_playback_state_timestamp_updated(self):
        """Verify playback state change updates timestamp."""
        import time
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
        
        engine = _SpotifyBeatEngine(bar_count=16)
        
        before = time.time()
        engine.set_playback_state(True)
        after = time.time()
        
        assert engine._last_playback_state_ts >= before
        assert engine._last_playback_state_ts <= after

    def test_gating_flag_affects_processing(self):
        """Verify gating flag is checked during audio processing."""
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
        
        engine = _SpotifyBeatEngine(bar_count=16)
        engine._latest_bars = None
        
        # When not playing, should return floor bars
        engine.set_playback_state(False)
        
        # Create mock audio buffer that returns a frame with samples
        mock_frame = MagicMock()
        mock_frame.samples = [0.5] * 1024
        engine._audio_buffer = MagicMock()
        engine._audio_buffer.consume_latest.return_value = mock_frame
        
        # Process via tick() - should be gated and return floor
        result = engine.tick()
        
        # Should have created floor bars
        assert result is not None
        assert len(result) == 16
        # First bar should have minimal floor
        assert result[0] == pytest.approx(0.08, abs=0.01)

    def test_minimal_floor_bar_when_paused(self):
        """Verify at least one bar shows minimal floor when paused."""
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
        
        engine = _SpotifyBeatEngine(bar_count=16)
        engine._is_spotify_playing = False
        engine._latest_bars = [0.0] * 16  # All zeros
        
        # Create mock audio buffer
        mock_frame = MagicMock()
        mock_frame.samples = [0.5] * 1024
        engine._audio_buffer = MagicMock()
        engine._audio_buffer.consume_latest.return_value = mock_frame
        
        result = engine.tick()
        
        # First bar should have minimal floor
        assert result[0] > 0.0
        assert result[0] == pytest.approx(0.08, abs=0.01)


class TestFFTWorkerGatingIntegration:
    """Integration tests for FFT gating with beat engine."""

    def test_gating_preserves_bar_count(self):
        """Verify gating returns correct number of bars for different counts."""
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
        
        for bar_count in [8, 16, 32]:
            engine = _SpotifyBeatEngine(bar_count=bar_count)
            engine._is_spotify_playing = False
            engine._latest_bars = None
            
            # Create mock audio buffer
            mock_frame = MagicMock()
            mock_frame.samples = [0.5] * 1024
            engine._audio_buffer = MagicMock()
            engine._audio_buffer.consume_latest.return_value = mock_frame
            
            result = engine.tick()
            
            assert len(result) == bar_count

    def test_gating_returns_existing_bars_if_available(self):
        """Verify gating returns existing bars if they match bar count."""
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
        
        engine = _SpotifyBeatEngine(bar_count=16)
        engine._is_spotify_playing = False
        engine._latest_bars = [0.5] * 16  # Pre-existing bars
        
        # Create mock audio buffer
        mock_frame = MagicMock()
        mock_frame.samples = [0.5] * 1024
        engine._audio_buffer = MagicMock()
        engine._audio_buffer.consume_latest.return_value = mock_frame
        
        result = engine.tick()
        
        # Should return existing bars (with floor applied if all zero)
        assert result is not None
        assert len(result) == 16
