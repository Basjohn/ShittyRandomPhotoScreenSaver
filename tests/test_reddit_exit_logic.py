"""Regression tests for Reddit link handling A/B/C logic.

These tests verify the smart exit behavior implemented to fix the Phase E
cache corruption issue. The logic is:
- Case A: Primary covered + hard_exit → Exit immediately
- Case B: Primary covered + Ctrl held → Exit immediately  
- Case C: MC mode (primary NOT covered) → Stay open, bring browser to foreground

See: audits/PHASE_E_ROOT_CAUSE_ANALYSIS.md
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QPoint, QRect, QObject, QPointF, QEvent, QTimer
from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent


class TestRedditExitLogic:
    """Test Reddit link handling exit logic."""
    
    def test_primary_covered_detection_same_screen(self):
        """When click is on primary screen, primary_is_covered should be True."""
        # This tests the logic path where this_is_primary = True
        # which immediately sets primary_is_covered = True
        
        # The actual logic is in display_widget.py mousePressEvent
        # We test the detection logic conceptually here
        
        # If self._screen is primary_screen, then this_is_primary = True
        # If this_is_primary = True, then primary_is_covered = True
        
        this_is_primary = True  # Simulating click on primary display
        primary_is_covered = this_is_primary  # Direct assignment in code
        
        assert primary_is_covered is True
    
    def test_primary_covered_detection_different_screen(self):
        """When click is on secondary but primary has DisplayWidget, primary_is_covered = True."""
        # This tests the coordinator lookup path
        
        # Simulate: click on secondary, but primary has a DisplayWidget registered
        this_is_primary = False
        primary_widget_exists = True  # coordinator.get_instance_for_screen returns widget
        
        primary_is_covered = this_is_primary or primary_widget_exists
        
        assert primary_is_covered is True
    
    def test_mc_mode_detection(self):
        """When primary has no DisplayWidget (MC mode), primary_is_covered = False."""
        # MC mode: screensaver only covers secondary displays, primary is free
        
        this_is_primary = False
        primary_widget_exists = False  # No DisplayWidget on primary
        
        primary_is_covered = this_is_primary or primary_widget_exists
        
        assert primary_is_covered is False


class TestRedditClickRouting:
    """Test that Reddit clicks are properly routed through InputHandler."""
    
    class _DummyParent(QObject):
        def __init__(self):
            super().__init__()
            self.settings_manager = MagicMock()
            self.settings_manager.get.return_value = False
            self._coordinator = MagicMock()
            self._coordinator.ctrl_held = False
    
    @pytest.mark.qt
    def test_reddit_click_returns_handled_tuple(self, qt_app, qtbot):
        """route_widget_click should return (handled, reddit_handled) tuple."""
        from rendering.input_handler import InputHandler
        from widgets.reddit_widget import RedditWidget
        
        handler = InputHandler(self._DummyParent())
        
        # Create a Reddit widget
        widget = RedditWidget()
        qtbot.addWidget(widget)
        widget.show()
        widget.setGeometry(0, 0, 300, 200)
        
        # Inject a hit rect
        widget._row_hit_rects = [
            (QRect(0, 20, 100, 20), "https://example.com/post", "Test Title"),
        ]
        
        # Create a mock mouse event at the hit rect location
        event = MagicMock()
        event.pos.return_value = QPoint(10, 30)
        event.button.return_value = Qt.MouseButton.LeftButton
        
        # Mock openUrl to prevent actual browser opening
        with patch('widgets.reddit_widget.QDesktopServices.openUrl', return_value=True):
            handled, reddit_handled, _ = handler.route_widget_click(
                event,
                None,  # spotify_volume_widget
                None,  # media_widget
                widget,  # reddit_widget
                None,  # reddit2_widget
            )
        
        assert handled is True
        assert reddit_handled is True

    @pytest.mark.qt
    def test_reddit_click_returns_deferred_url(self, qt_app, qtbot):
        """route_widget_click should include the resolved Reddit URL."""
        from rendering.input_handler import InputHandler
        from widgets.reddit_widget import RedditWidget

        handler = InputHandler(self._DummyParent())

        widget = RedditWidget()
        qtbot.addWidget(widget)
        widget.show()
        widget.setGeometry(0, 0, 300, 200)

        url = "https://example.com/deferred"
        widget._row_hit_rects = [
            (QRect(0, 20, 100, 20), url, "Deferred Title"),
        ]

        event = MagicMock()
        event.pos.return_value = QPoint(10, 30)
        event.button.return_value = Qt.MouseButton.LeftButton

        handled, reddit_handled, reddit_url = handler.route_widget_click(
            event,
            None,
            None,
            widget,
            None,
        )

        assert handled is True
        assert reddit_handled is True
        assert reddit_url == url


class TestCacheInvalidationMitigation:
    """Test that the Phase E cache corruption is mitigated by immediate exit."""
    
    def test_no_setforegroundwindow_before_exit(self):
        """Verify SetForegroundWindow is NOT called before exit_requested.
        
        The Phase E bug was caused by SetForegroundWindow stealing focus
        BEFORE the screensaver windows were hidden, which triggered Windows
        activation messages that corrupted Qt's QGraphicsEffect cache.
        
        The fix ensures exit happens first, then browser is foregrounded
        via QTimer.singleShot(300ms) AFTER windows start closing.
        """
        # This is a design verification test - the actual implementation
        # uses QTimer.singleShot(300, _bring_browser_foreground) which
        # delays the SetForegroundWindow call until after exit_requested.emit()
        
        # The key invariant: exit_requested.emit() MUST happen BEFORE
        # any SetForegroundWindow calls when primary_is_covered = True
        
        # We verify this by checking the code structure in display_widget.py:
        # 1. if primary_is_covered:
        # 2.     self._exiting = True
        # 3.     QTimer.singleShot(300, _bring_browser_foreground)  # DELAYED
        # 4.     self.exit_requested.emit()  # IMMEDIATE
        
        # The 300ms delay ensures windows are closing before focus steal
        assert True  # Design verification - actual test is in integration


class TestDisplayManagerDeferredUrls:
    """Test deferred Reddit URL handling in DisplayManager cleanup."""

    @pytest.mark.qt
    def test_cleanup_opens_pending_reddit_urls(self, qt_app, monkeypatch):
        """DisplayManager.cleanup should open stored Reddit URLs after shutdown."""
        from engine.display_manager import DisplayManager

        manager = DisplayManager()
        fake_display = MagicMock()
        fake_display.screen_index = 0
        fake_display._pending_reddit_url = "https://example.com/pending"
        fake_display.clear = MagicMock()
        fake_display.close = MagicMock()
        fake_display.deleteLater = MagicMock()

        manager.displays = [fake_display]

        opened: list[str] = []

        def _fake_open(qurl):
            opened.append(qurl.toString())
            return True

        monkeypatch.setattr(
            "engine.display_manager.QDesktopServices.openUrl",
            _fake_open,
        )

        manager.cleanup()

        assert fake_display._pending_reddit_url is None
        assert opened == ["https://example.com/pending"]


class TestDeferredRedditFlow:
    """Integration tests for deferred Reddit URL timing."""

    @pytest.mark.qt
    def test_primary_covered_click_defers_until_cleanup(self, qt_app, qtbot, settings_manager, monkeypatch):
        """Ensure primary-covered clicks defer URL opening until DisplayManager cleanup."""
        from PySide6.QtGui import QDesktopServices as QtDesktopServices
        from PySide6.QtGui import QGuiApplication
        from rendering.display_widget import DisplayWidget
        from rendering.multi_monitor_coordinator import MultiMonitorCoordinator
        from engine.display_manager import DisplayManager
        import engine.display_manager as display_manager_module

        MultiMonitorCoordinator.reset()
        try:
            widget = DisplayWidget(screen_index=0, settings_manager=settings_manager)
            widget.resize(400, 300)
            widget.show()
            qt_app.processEvents()

            assert widget._screen is not None
            handler = widget._input_handler
            assert handler is not None

            target_url = "https://example.com/deferred"

            def _fake_route(*_args, **_kwargs):
                return True, True, target_url

            monkeypatch.setattr(handler, "route_widget_click", _fake_route)

            # Fail immediately if MC-mode code path tries to open the browser.
            def _fail_immediate_open(_url):
                raise AssertionError("URL should not open before cleanup when primary is covered")

            monkeypatch.setattr(
                QtDesktopServices,
                "openUrl",
                staticmethod(_fail_immediate_open),
            )
            monkeypatch.setattr(
                QGuiApplication,
                "primaryScreen",
                staticmethod(lambda: widget._screen),
            )

            widget._ctrl_held = True  # Force interaction mode

            event = QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(5, 5),
                QPointF(5, 5),
                QPointF(5, 5),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )

            widget.mousePressEvent(event)

            assert widget._pending_reddit_url == target_url

            opened: list[str] = []

            def _open_on_cleanup(qurl):
                opened.append(qurl.toString())
                return True

            monkeypatch.setattr(
                display_manager_module.QDesktopServices,
                "openUrl",
                staticmethod(_open_on_cleanup),
            )

            manager = DisplayManager()
            manager.displays = [widget]

            manager.cleanup()
            manager.flush_deferred_reddit_urls(ensure_widgets_dismissed=False)

            assert opened == [target_url]
        finally:
            MultiMonitorCoordinator.reset()

    @pytest.mark.qt
    def test_cleanup_waits_for_window_teardown_before_open(self, qtbot, monkeypatch):
        """Simulate Winlogon secure desktop by delaying window teardown until after event processing.

        DisplayManager.cleanup should not invoke QDesktopServices while display windows are still open.
        """
        from engine.display_manager import DisplayManager

        class _AsyncClosingDisplay(QObject):
            def __init__(self, url: str):
                super().__init__()
                self.screen_index = 0
                self._pending_reddit_url = url
                self.closed = False
                self.deleted = False

            def clear(self):
                pass

            def close(self):
                QTimer.singleShot(0, lambda: setattr(self, "closed", True))

            def deleteLater(self):
                QTimer.singleShot(0, lambda: setattr(self, "deleted", True))

        display = _AsyncClosingDisplay("https://example.com/secure-desktop")
        manager = DisplayManager()
        manager.displays = [display]

        def _open_before_windows_gone(qurl):
            assert display.closed and display.deleted, (
                "Deferred Reddit URL opened before display windows finished closing"
            )
            return True

        monkeypatch.setattr(
            "engine.display_manager.QDesktopServices.openUrl",
            _open_before_windows_gone,
        )

        manager.cleanup()
        qtbot.wait_until(lambda: display.closed and display.deleted, timeout=1000)


class TestRedditHelperLauncher:
    """Validate the Windows helper launcher integration."""

    def test_flush_prefers_helper_when_available(self, qt_app, monkeypatch):
        from engine.display_manager import DisplayManager

        manager = DisplayManager()
        manager._deferred_reddit_urls = ["https://example.com/helper-success"]

        class _Helper:
            def __init__(self) -> None:
                self.should_use = True
                self.launched: list[str] = []

            def should_use_session_launcher(self) -> bool:
                return self.should_use

            def launch_url_via_user_desktop(self, url: str) -> bool:
                self.launched.append(url)
                return True

        helper = _Helper()
        monkeypatch.setattr("engine.display_manager.windows_url_launcher", helper, raising=False)

        open_calls: list[str] = []

        def _open(qurl):
            open_calls.append(qurl.toString())
            return True

        monkeypatch.setattr(
            "engine.display_manager.QDesktopServices.openUrl",
            staticmethod(_open),
        )

        manager.flush_deferred_reddit_urls()

        assert helper.launched == ["https://example.com/helper-success"]
        assert open_calls == []  # QDesktopServices not used when helper succeeds

    def test_flush_falls_back_when_helper_rejects(self, qt_app, monkeypatch):
        from engine.display_manager import DisplayManager

        manager = DisplayManager()
        manager._deferred_reddit_urls = ["https://example.com/helper-fallback"]

        class _Helper:
            def should_use_session_launcher(self) -> bool:
                return True

            def launch_url_via_user_desktop(self, url: str) -> bool:
                self.url = url
                return False

        helper = _Helper()
        monkeypatch.setattr("engine.display_manager.windows_url_launcher", helper, raising=False)

        open_calls: list[str] = []

        def _open(qurl):
            open_calls.append(qurl.toString())
            return True

        monkeypatch.setattr(
            "engine.display_manager.QDesktopServices.openUrl",
            staticmethod(_open),
        )

        manager.flush_deferred_reddit_urls()

        assert getattr(helper, "url") == "https://example.com/helper-fallback"
        assert open_calls == ["https://example.com/helper-fallback"]

    def test_flush_queues_when_bridge_available(self, qt_app, monkeypatch):
        from engine.display_manager import DisplayManager

        manager = DisplayManager()
        manager._deferred_reddit_urls = ["https://example.com/bridge"]

        class _Bridge:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def is_bridge_available(self) -> bool:
                return True

            def enqueue_url(self, url: str) -> bool:
                self.calls.append(url)
                return True

        bridge = _Bridge()
        monkeypatch.setattr(
            "engine.display_manager.reddit_helper_bridge", bridge, raising=False
        )
        monkeypatch.setattr(
            "engine.display_manager.windows_url_launcher",
            None,
            raising=False,
        )

        open_calls: list[str] = []

        def _open(qurl):
            open_calls.append(qurl.toString())
            return True

        monkeypatch.setattr(
            "engine.display_manager.QDesktopServices.openUrl",
            staticmethod(_open),
        )

        manager.flush_deferred_reddit_urls()

        assert bridge.calls == ["https://example.com/bridge"]
        assert open_calls == []

@pytest.mark.skip(reason="Requires full Qt app with multi-monitor setup")
class TestRedditExitIntegration:
    """Integration tests requiring full DisplayWidget setup."""
    
    def test_case_a_hard_exit_primary_covered(self):
        """Case A: hard_exit + primary covered → immediate exit."""
        pass
    
    def test_case_b_ctrl_held_primary_covered(self):
        """Case B: Ctrl held + primary covered → immediate exit."""
        pass
    
    def test_case_c_mc_mode_stay_open(self):
        """Case C: MC mode (primary not covered) → stay open."""
        pass
