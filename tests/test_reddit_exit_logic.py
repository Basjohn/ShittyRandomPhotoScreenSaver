"""Current Reddit URL handoff and click-through regression contracts."""

from unittest.mock import MagicMock

import pytest

import engine.display_manager as display_manager_module


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
