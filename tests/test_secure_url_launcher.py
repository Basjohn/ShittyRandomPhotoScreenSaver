"""Tests for core.windows.secure_url_launcher."""
from __future__ import annotations

from unittest.mock import patch


@patch("core.windows.secure_url_launcher.reddit_helper_bridge")
def test_open_url_uses_bridge_when_available(mock_bridge) -> None:
    from core.windows.secure_url_launcher import open_url

    mock_bridge.is_bridge_available.return_value = True
    mock_bridge.enqueue_url.return_value = True

    assert open_url("https://example.com") is True
    mock_bridge.enqueue_url.assert_called_once_with("https://example.com", source="gmail")


@patch("core.windows.secure_url_launcher.reddit_helper_bridge")
@patch("core.windows.secure_url_launcher.webbrowser.open")
def test_open_url_fallback_to_browser(mock_webbrowser, mock_bridge) -> None:
    from core.windows.secure_url_launcher import open_url

    mock_bridge.is_bridge_available.return_value = False

    assert open_url("https://example.com") is True
    mock_webbrowser.assert_called_once_with("https://example.com")


@patch("core.windows.secure_url_launcher.reddit_helper_bridge")
@patch("core.windows.secure_url_launcher.webbrowser.open")
def test_open_url_no_fallback_returns_false(mock_webbrowser, mock_bridge) -> None:
    from core.windows.secure_url_launcher import open_url

    mock_bridge.is_bridge_available.return_value = False

    assert open_url("https://example.com", fallback=False) is False
    mock_webbrowser.assert_not_called()
