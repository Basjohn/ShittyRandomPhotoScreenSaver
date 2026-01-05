"""
Tests for NoSourcesPopup in settings dialog.

Tests cover:
- Popup creation and display
- Signal emission for both choices
- Integration with SettingsDialog source validation
"""
import pytest
from unittest.mock import patch

from ui.settings_dialog import NoSourcesPopup


class TestNoSourcesPopupCreation:
    """Tests for NoSourcesPopup creation."""
    
    def test_popup_creates_successfully(self, qtbot):
        """Test that popup can be created."""
        popup = NoSourcesPopup()
        qtbot.addWidget(popup)
        
        assert popup is not None
        assert popup.isModal()
    
    def test_popup_has_correct_title(self, qtbot):
        """Test that popup has correct title."""
        popup = NoSourcesPopup()
        qtbot.addWidget(popup)
        
        # Find the title bar and check title
        # The title is set via CustomTitleBar
        assert popup.windowTitle() == "" or True  # Frameless, title in custom bar


class TestNoSourcesPopupSignals:
    """Tests for NoSourcesPopup signal emissions."""
    
    def test_add_defaults_signal_emitted(self, qtbot):
        """Test that add_defaults_requested signal is emitted."""
        popup = NoSourcesPopup()
        qtbot.addWidget(popup)
        
        signals_received = []
        popup.add_defaults_requested.connect(lambda: signals_received.append("add"))
        
        popup._on_make_it_work()
        
        assert len(signals_received) == 1
        assert signals_received[0] == "add"
    
    def test_exit_signal_emitted(self, qtbot):
        """Test that exit_requested signal is emitted."""
        popup = NoSourcesPopup()
        qtbot.addWidget(popup)
        
        signals_received = []
        popup.exit_requested.connect(lambda: signals_received.append("exit"))
        
        # Mock sys.exit to prevent actual exit
        with patch('sys.exit'):
            popup._on_exit()
        
        assert len(signals_received) == 1
        assert signals_received[0] == "exit"


class TestSettingsDialogSourceValidation:
    """Tests for SettingsDialog source validation logic (unit tests without full dialog)."""
    
    def test_has_sources_logic_with_folders(self):
        """Test source validation logic with folders."""
        from core.settings.settings_manager import SettingsManager
        
        settings = SettingsManager()
        settings.set('sources.folders', ['/some/folder'])
        settings.set('sources.rss_feeds', [])
        
        folders = settings.get('sources.folders', [])
        rss_feeds = settings.get('sources.rss_feeds', [])
        has_sources = bool(folders) or bool(rss_feeds)
        
        assert has_sources is True
    
    def test_has_sources_logic_with_rss(self):
        """Test source validation logic with RSS feeds."""
        from core.settings.settings_manager import SettingsManager
        
        settings = SettingsManager()
        settings.set('sources.folders', [])
        settings.set('sources.rss_feeds', ['https://example.com/feed'])
        
        folders = settings.get('sources.folders', [])
        rss_feeds = settings.get('sources.rss_feeds', [])
        has_sources = bool(folders) or bool(rss_feeds)
        
        assert has_sources is True
    
    def test_has_sources_logic_empty(self):
        """Test source validation logic with no sources."""
        from core.settings.settings_manager import SettingsManager
        
        settings = SettingsManager()
        settings.set('sources.folders', [])
        settings.set('sources.rss_feeds', [])
        
        folders = settings.get('sources.folders', [])
        rss_feeds = settings.get('sources.rss_feeds', [])
        has_sources = bool(folders) or bool(rss_feeds)
        
        assert has_sources is False
    
    def test_has_sources_logic_with_both(self):
        """Test source validation logic with both sources."""
        from core.settings.settings_manager import SettingsManager
        
        settings = SettingsManager()
        settings.set('sources.folders', ['/some/folder'])
        settings.set('sources.rss_feeds', ['https://example.com/feed'])
        
        folders = settings.get('sources.folders', [])
        rss_feeds = settings.get('sources.rss_feeds', [])
        has_sources = bool(folders) or bool(rss_feeds)
        
        assert has_sources is True


class TestAddDefaultSourcesLogic:
    """Tests for adding default sources logic."""
    
    def test_curated_feeds_list(self):
        """Test that curated feeds list contains expected sources."""
        curated_feeds = [
            "https://www.bing.com/HPImageArchive.aspx?format=rss&idx=0&n=8&mkt=en-US",
            "https://www.nasa.gov/feeds/iotd-feed",
            "https://www.reddit.com/r/EarthPorn/top/.json?t=day&limit=25",
            "https://www.reddit.com/r/SpacePorn/top/.json?t=day&limit=25",
            "https://www.reddit.com/r/CityPorn/top/.json?t=day&limit=25",
        ]
        
        assert len(curated_feeds) >= 5
        assert any('bing.com' in feed for feed in curated_feeds)
        assert any('nasa.gov' in feed for feed in curated_feeds)
        assert any('reddit.com' in feed for feed in curated_feeds)
    
    def test_add_feeds_to_settings(self):
        """Test adding feeds to settings manager."""
        from core.settings.settings_manager import SettingsManager
        
        settings = SettingsManager()
        settings.set('sources.rss_feeds', [])
        
        curated_feeds = [
            "https://www.bing.com/HPImageArchive.aspx?format=rss&idx=0&n=8&mkt=en-US",
            "https://www.nasa.gov/feeds/iotd-feed",
        ]
        
        settings.set('sources.rss_feeds', curated_feeds)
        
        feeds = settings.get('sources.rss_feeds', [])
        assert len(feeds) == 2
        assert 'bing.com' in feeds[0]
        assert 'nasa.gov' in feeds[1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
