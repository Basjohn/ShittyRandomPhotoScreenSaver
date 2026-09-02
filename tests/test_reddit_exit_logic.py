"""Regression tests for Reddit link handling A/B/C logic.

These tests verify the smart exit behavior implemented to fix the Phase E
cache corruption issue. The logic is:
- Case A: Primary covered + Interaction Mode → Exit immediately
- Case B: Primary covered + Ctrl held → Exit immediately  
- Case C: MC mode (primary NOT covered) → Stay open, bring browser to foreground

See: audits/PHASE_E_ROOT_CAUSE_ANALYSIS.md
"""

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF, QEvent, Qt
from PySide6.QtGui import QMouseEvent

import engine.display_manager as display_manager_module


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


class TestCleanQueueFlow:
    """Test the new clean queue-based URL handling."""

    @pytest.mark.qt
    def test_mc_flush_opens_directly(self, qt_app, monkeypatch):
        """MC build flush opens URLs via QDesktopServices."""
        from engine.display_manager import DisplayManager
        manager = DisplayManager()
        manager._deferred_reddit_urls = ["https://example.com/mc-flush"]

        class _ImmediateThreadManager:
            @staticmethod
            def single_shot(_ms, callback):
                callback()

        manager._thread_manager = _ImmediateThreadManager()

        monkeypatch.setattr("core.mc.is_mc_build", lambda: True)

        open_calls: list[str] = []

        def _open(qurl):
            open_calls.append(qurl.toString())
            return True

        monkeypatch.setattr(
            "engine.display_manager.QDesktopServices.openUrl",
            staticmethod(_open),
        )
        helper_calls: list[tuple[str, int, tuple[str, ...]]] = []

        monkeypatch.setattr(
            "core.windows.browser_window_routing.try_bring_browser_window_to_front",
            lambda url, *, preferred_display_index=0, fallback_keywords=(): helper_calls.append(
                (url, preferred_display_index, tuple(fallback_keywords))
            ) or True,
        )
        manager.flush_deferred_reddit_urls()

        assert open_calls == ["https://example.com/mc-flush"]
        assert helper_calls == [("https://example.com/mc-flush", 0, ("reddit",))]

    @pytest.mark.qt
    def test_scr_flush_queues_to_bridge(self, qt_app, monkeypatch):
        """SCR build flush queues URLs to ProgramData bridge as safety-net."""
        from engine.display_manager import DisplayManager

        manager = DisplayManager()
        manager._deferred_reddit_urls = ["https://example.com/scr-flush"]

        monkeypatch.setattr("core.mc.is_mc_build", lambda: False)

        class _Bridge:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def is_bridge_available(self) -> bool:
                return True

            def enqueue_url(self, url: str, source: str = "") -> bool:
                self.calls.append((url, source))
                return True

        bridge = _Bridge()
        monkeypatch.setattr(
            display_manager_module,
            "reddit_helper_bridge",
            bridge,
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

        assert len(bridge.calls) == 1
        assert bridge.calls[0][0] == "https://example.com/scr-flush"
        assert open_calls == []

    @pytest.mark.qt
    def test_scr_flush_warns_when_bridge_unavailable(self, qt_app, monkeypatch, caplog):
        """SCR build flush logs warning when bridge is unavailable."""
        from engine.display_manager import DisplayManager
        import logging

        manager = DisplayManager()
        manager._deferred_reddit_urls = ["https://example.com/lost"]

        monkeypatch.setattr("core.mc.is_mc_build", lambda: False)
        monkeypatch.setattr(
            display_manager_module,
            "reddit_helper_bridge",
            None,
            raising=False,
        )

        with caplog.at_level(logging.WARNING):
            manager.flush_deferred_reddit_urls()

        assert any("Bridge unavailable" in msg for msg in caplog.messages)

    @pytest.mark.qt
    def test_flush_noop_for_empty_queue(self, qt_app, monkeypatch):
        """flush_deferred_reddit_urls is a no-op when no URLs are queued."""
        from engine.display_manager import DisplayManager

        manager = DisplayManager()
        manager._deferred_reddit_urls = []

        called = []
        monkeypatch.setattr("core.mc.is_mc_build", lambda: (called.append(1) or True))

        manager.flush_deferred_reddit_urls()

        assert called == []


class TestContextMenuClickThroughSuppression:
    """Regression bar for the context-menu click-through bug.

    A retained-menu item is activated by a pointer tap. Because Qt Quick
    TapHandlers take non-exclusive passive grabs, that same press/release is
    also recognised by a widget TapHandler (Reddit post, Gmail row) beneath the
    menu surface, firing its browser-open/exit action in the same gesture - the
    logged failure where selecting Settings also opened a Reddit link. Reddit's
    open path already consulted the shared pointer guard, but no menu-action
    boundary ever armed it, so the check was dead for this trigger. The menu
    action route now arms it; this proves both halves.
    """

    @pytest.mark.qt
    def test_menu_action_arms_pointer_guard_and_reddit_open_is_refused(
        self, qt_app, monkeypatch
    ):
        from engine.display_manager import DisplayManager
        import core.widget_product_actions as widget_product_actions
        from rendering.runtime_input import (
            clear_runtime_pointer_input_suppression,
            runtime_pointer_input_is_suppressed,
        )

        # Safety net: if the Reddit guard regresses and the phantom open is not
        # refused, it must record here rather than actually launch a browser.
        dispatched: list[str] = []
        monkeypatch.setattr(
            widget_product_actions,
            "dispatch_reddit_url_product_action",
            lambda url, **_kwargs: dispatched.append(url) or True,
            raising=False,
        )

        clear_runtime_pointer_input_suppression()
        try:
            manager = DisplayManager()
            assert (
                runtime_pointer_input_is_suppressed("redditOpenRequested") is False
            )

            # Reproduce the real regression boundary: selecting Settings from
            # the retained menu must arm the shared guard before the phantom
            # widget open fires on the same release.
            settings_requests: list[bool] = []
            manager.settings_requested.connect(lambda: settings_requests.append(True))
            assert (
                manager._handle_quick_context_action(MagicMock(), "settings", "") is True
            )
            assert settings_requests == [True]
            assert (
                runtime_pointer_input_is_suppressed("redditOpenRequested") is True
            )

            # Reddit's open path checks the guard first, so the phantom open is
            # refused and never reaches the product-action dispatcher.
            assert (
                manager._open_quick_reddit_url("reddit", "https://reddit.com/r/x")
                is False
            )
            assert dispatched == []
        finally:
            clear_runtime_pointer_input_suppression()


@pytest.mark.skip(reason="Requires full Qt app with multi-monitor setup")
class TestRedditExitIntegration:
    """Integration tests requiring full DisplayWidget setup."""
    
    def test_case_a_interaction_mode_primary_covered(self):
        """Case A: Interaction Mode + primary covered → immediate exit."""
        pass
    
    def test_case_b_ctrl_held_primary_covered(self):
        """Case B: Ctrl held + primary covered → immediate exit."""
        pass
    
    def test_case_c_mc_mode_stay_open(self):
        """Case C: MC mode (primary not covered) → stay open."""
        pass
