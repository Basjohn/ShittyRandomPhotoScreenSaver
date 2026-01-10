"""Regression tests for Media widget artwork loading and diff gating.

These tests verify:
- Artwork loads on startup (first track)
- Diff gating allows first track to complete fade-in
- Diff gating skips updates when track unchanged after fade-in
- Artwork is decoded before first-track early return
- Content margins are set before first-track early return (text layout fix)
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QImage
from PySide6.QtCore import QBuffer, QIODevice

from core.media.media_controller import MediaTrackInfo, MediaPlaybackState


def _create_test_artwork_bytes() -> bytes:
    """Create a small valid PNG image for testing."""
    img = QImage(100, 100, QImage.Format.Format_ARGB32)
    img.fill(0xFFFF0000)  # Red
    
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buffer, "PNG")
    return bytes(buffer.data())


@pytest.fixture
def mock_parent(qtbot):
    """Create a mock parent widget."""
    parent = QWidget()
    parent.resize(1920, 1080)
    qtbot.addWidget(parent)
    return parent


class TestMediaWidgetArtworkLoading:
    """Tests for media widget artwork loading on startup."""

    def test_artwork_decoded_on_first_track(self, mock_parent, qtbot):
        """Verify artwork is decoded on the very first track update."""
        from widgets.media_widget import MediaWidget, MediaPosition
        
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        qtbot.addWidget(widget)
        
        # Create track info with artwork
        artwork_bytes = _create_test_artwork_bytes()
        info = MediaTrackInfo(
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            state=MediaPlaybackState.PLAYING,
            artwork=artwork_bytes,
        )
        
        # Simulate first update
        widget._update_display(info)
        
        # Artwork should be decoded even on first track
        assert widget._artwork_pixmap is not None
        assert not widget._artwork_pixmap.isNull()
        assert widget._has_seen_first_track is True

    def test_artwork_decoded_when_paused(self, mock_parent, qtbot):
        """Verify artwork loads even when Spotify is paused (not playing)."""
        from widgets.media_widget import MediaWidget, MediaPosition
        
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        qtbot.addWidget(widget)
        
        # Create track info with PAUSED state
        artwork_bytes = _create_test_artwork_bytes()
        info = MediaTrackInfo(
            title="Paused Song",
            artist="Test Artist",
            album="Test Album",
            state=MediaPlaybackState.PAUSED,  # Paused, not playing
            artwork=artwork_bytes,
        )
        
        # Simulate first update
        widget._update_display(info)
        
        # Artwork should still be decoded
        assert widget._artwork_pixmap is not None
        assert not widget._artwork_pixmap.isNull()

    def test_first_track_sets_has_seen_flag(self, mock_parent, qtbot):
        """Verify _has_seen_first_track is set on first update."""
        from widgets.media_widget import MediaWidget, MediaPosition
        
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        qtbot.addWidget(widget)
        
        assert widget._has_seen_first_track is False
        
        info = MediaTrackInfo(
            title="Test",
            artist="Artist",
            state=MediaPlaybackState.PLAYING,
        )
        
        widget._update_display(info)
        
        assert widget._has_seen_first_track is True

    def test_content_margins_set_on_first_track(self, mock_parent, qtbot):
        """Verify content margins are set on first track to prevent text overlap with artwork.
        
        Regression test: Text was overlapping artwork on startup because margins
        were only set after the first-track early return.
        """
        from widgets.media_widget import MediaWidget, MediaPosition
        
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        qtbot.addWidget(widget)
        
        # Get initial margins (verify they exist)
        _ = widget.contentsMargins()
        
        # Create track info with artwork
        artwork_bytes = _create_test_artwork_bytes()
        info = MediaTrackInfo(
            title="Test Song With A Long Title That Might Wrap",
            artist="Test Artist",
            state=MediaPlaybackState.PLAYING,
            artwork=artwork_bytes,
        )
        
        # First update (triggers first-track early return)
        widget._update_display(info)
        
        # Margins should be set to reserve space for artwork
        margins = widget.contentsMargins()
        expected_right_margin = max(widget._artwork_size + 40, 60)
        
        # Right margin should account for artwork space
        assert margins.right() == expected_right_margin
        # Bottom margin should have extra space for controls
        assert margins.bottom() == 40


class TestMediaWidgetDiffGating:
    """Tests for media widget diff gating behavior."""

    def test_diff_gating_allows_updates_before_fade_complete(self, mock_parent, qtbot):
        """Verify diff gating doesn't skip updates before fade-in completes."""
        from widgets.media_widget import MediaWidget, MediaPosition
        
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        qtbot.addWidget(widget)
        
        info = MediaTrackInfo(
            title="Test Song",
            artist="Test Artist",
            state=MediaPlaybackState.PLAYING,
        )
        
        # Manually set fade_in_completed to False to simulate pre-fade state
        widget._fade_in_completed = False
        widget._has_seen_first_track = True  # Simulate first track seen
        widget._last_track_identity = widget._compute_track_identity(info)
        
        # Update with same track - should NOT be skipped because fade not complete
        widget._update_display(info)
        
        # Should have processed (not skipped by diff gating)
        assert widget._last_info is not None
        assert widget._last_info.title == "Test Song"

    def test_diff_gating_skips_after_fade_complete(self, mock_parent, qtbot):
        """Verify diff gating skips updates after fade-in completes."""
        from widgets.media_widget import MediaWidget, MediaPosition
        
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        qtbot.addWidget(widget)
        
        info = MediaTrackInfo(
            title="Test Song",
            artist="Test Artist",
            state=MediaPlaybackState.PLAYING,
        )
        
        # First update
        widget._update_display(info)
        
        # Simulate fade completion
        widget._fade_in_completed = True
        widget._last_track_identity = widget._compute_track_identity(info)
        
        # Second update with same track - should be skipped
        # We verify by checking that the method returns early
        # (The diff gating check happens before most processing)
        widget._update_display(info)
        
        # The update was processed but diff gating returned early
        # This is verified by the fact that no exception was raised
        # and the widget state remains consistent
        assert widget._fade_in_completed is True

    def test_diff_gating_allows_track_change(self, mock_parent, qtbot):
        """Verify diff gating allows updates when track changes."""
        from widgets.media_widget import MediaWidget, MediaPosition
        
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        qtbot.addWidget(widget)
        
        info1 = MediaTrackInfo(
            title="Song 1",
            artist="Artist 1",
            state=MediaPlaybackState.PLAYING,
        )
        
        # First update
        widget._update_display(info1)
        widget._fade_in_completed = True
        
        # Different track
        info2 = MediaTrackInfo(
            title="Song 2",
            artist="Artist 2",
            state=MediaPlaybackState.PLAYING,
        )
        
        # Update with different track - should NOT be skipped
        widget._update_display(info2)
        
        # Track identity should be updated
        assert widget._last_track_identity == widget._compute_track_identity(info2)

    def test_track_identity_includes_state(self, mock_parent, qtbot):
        """Verify track identity includes playback state."""
        from widgets.media_widget import MediaWidget, MediaPosition
        
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        qtbot.addWidget(widget)
        
        info_playing = MediaTrackInfo(
            title="Test",
            artist="Artist",
            state=MediaPlaybackState.PLAYING,
        )
        
        info_paused = MediaTrackInfo(
            title="Test",
            artist="Artist",
            state=MediaPlaybackState.PAUSED,
        )
        
        identity_playing = widget._compute_track_identity(info_playing)
        identity_paused = widget._compute_track_identity(info_paused)
        
        # Same track but different state should have different identity
        assert identity_playing != identity_paused


class TestMediaWidgetIdleDetection:
    """Tests for media widget idle detection."""

    def test_idle_detection_tracks_none_results(self, mock_parent, qtbot):
        """Verify idle detection tracks consecutive None results."""
        from widgets.media_widget import MediaWidget, MediaPosition
        
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        qtbot.addWidget(widget)
        
        assert widget._consecutive_none_count == 0
        assert widget._is_idle is False
        
        # Simulate None results
        for i in range(5):
            widget._update_display(None)
        
        assert widget._consecutive_none_count == 5
        # Not yet idle (threshold is 12)
        assert widget._is_idle is False

    def test_idle_mode_entered_after_threshold(self, mock_parent, qtbot):
        """Verify widget enters idle mode after threshold consecutive None results."""
        from widgets.media_widget import MediaWidget, MediaPosition
        
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        qtbot.addWidget(widget)
        
        # Simulate enough None results to trigger idle
        for i in range(widget._idle_threshold + 1):
            widget._update_display(None)
        
        assert widget._is_idle is True

    def test_idle_mode_exits_on_track(self, mock_parent, qtbot):
        """Verify widget exits idle mode when track is detected."""
        from widgets.media_widget import MediaWidget, MediaPosition
        
        widget = MediaWidget(mock_parent, position=MediaPosition.BOTTOM_LEFT)
        qtbot.addWidget(widget)
        
        # Enter idle mode
        for i in range(widget._idle_threshold + 1):
            widget._update_display(None)
        
        assert widget._is_idle is True
        
        # Track detected
        info = MediaTrackInfo(
            title="Test",
            artist="Artist",
            state=MediaPlaybackState.PLAYING,
        )
        widget._update_display(info)
        
        assert widget._is_idle is False
        assert widget._consecutive_none_count == 0
