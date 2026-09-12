"""Tests for core.windows.secure_url_launcher."""
from __future__ import annotations

from unittest.mock import patch

from core.steam.links import friend_message_target, store_target


@patch("core.windows.secure_url_launcher.reddit_helper_bridge")
def test_open_url_uses_bridge_when_available(mock_bridge) -> None:
    from core.windows.secure_url_launcher import open_url

    mock_bridge.is_bridge_available.return_value = True
    mock_bridge.enqueue_url.return_value = True

    assert open_url("https://example.com") is True
    mock_bridge.enqueue_url.assert_called_once_with("https://example.com", source="gmail")


@patch("core.windows.secure_url_launcher.reddit_helper_bridge")
@patch("core.windows.secure_url_launcher.QDesktopServices.openUrl", return_value=True)
def test_open_url_prefers_native_direct_launch_for_settings(mock_open, mock_bridge) -> None:
    from core.windows.secure_url_launcher import open_url

    assert open_url("https://example.com", prefer_direct=True, source="steam_settings") is True

    mock_open.assert_called_once()
    mock_bridge.is_bridge_available.assert_not_called()
    mock_bridge.enqueue_url.assert_not_called()


@patch("core.windows.secure_url_launcher.reddit_helper_runtime.ensure_helper_runtime")
@patch("core.windows.secure_url_launcher.reddit_helper_bridge")
@patch("core.windows.secure_url_launcher.QDesktopServices.openUrl", return_value=True)
def test_diagnostic_build_uses_direct_route_without_shared_helper(
    mock_open,
    mock_bridge,
    mock_ensure_helper,
    monkeypatch,
) -> None:
    from core.windows import secure_url_launcher

    monkeypatch.setattr(secure_url_launcher, "is_diagnostic_build", lambda: True)

    assert secure_url_launcher.open_url("https://example.com", source="diagnostic") is True
    mock_open.assert_called_once()
    mock_bridge.is_bridge_available.assert_not_called()
    mock_bridge.enqueue_url.assert_not_called()
    mock_ensure_helper.assert_not_called()


@patch("core.windows.secure_url_launcher.reddit_helper_runtime.ensure_helper_runtime")
@patch("core.windows.secure_url_launcher.reddit_helper_bridge")
@patch("core.windows.secure_url_launcher.QDesktopServices.openUrl", return_value=False)
def test_open_url_uses_and_wakes_secure_handoff_after_direct_failure(
    mock_open,
    mock_bridge,
    mock_ensure_helper,
) -> None:
    from core.windows.secure_url_launcher import open_url

    mock_bridge.is_bridge_available.return_value = True
    mock_bridge.enqueue_url.return_value = True

    assert open_url("https://example.com", prefer_direct=True, source="steam_settings") is True

    mock_open.assert_called_once()
    mock_bridge.enqueue_url.assert_called_once_with("https://example.com", source="steam_settings")
    mock_ensure_helper.assert_called_once_with(
        source="steam_settings_url",
        owner_pid=None,
        idle_exit_seconds=60,
        allow_system=True,
    )


@patch("core.windows.secure_url_launcher.reddit_helper_bridge")
@patch("core.windows.secure_url_launcher.webbrowser.open")
def test_open_url_fallback_to_browser(mock_webbrowser, mock_bridge) -> None:
    from core.windows.secure_url_launcher import open_url

    mock_bridge.is_bridge_available.return_value = False

    assert open_url("https://example.com") is True
    mock_webbrowser.assert_called_once_with("https://example.com", new=1)


@patch("core.windows.secure_url_launcher.reddit_helper_bridge")
@patch("core.windows.secure_url_launcher.webbrowser.open")
def test_open_url_no_fallback_returns_false(mock_webbrowser, mock_bridge) -> None:
    from core.windows.secure_url_launcher import open_url

    mock_bridge.is_bridge_available.return_value = False

    assert open_url("https://example.com", fallback=False) is False
    mock_webbrowser.assert_not_called()


@patch("core.windows.secure_url_launcher.QDesktopServices.openUrl", return_value=True)
def test_steam_target_uses_direct_protocol_for_interactive_build(
    mock_open,
    monkeypatch,
) -> None:
    from core.windows import secure_url_launcher

    monkeypatch.setattr(secure_url_launcher, "is_mc_build", lambda: True)
    target = friend_message_target("76561198000000001")
    assert target is not None

    assert secure_url_launcher.open_steam_target(target, source="friend_pulse") is True
    assert mock_open.call_args.args[0].toString() == target.steam_url


@patch("core.windows.secure_url_launcher.open_url", return_value=True)
@patch("core.windows.secure_url_launcher.QDesktopServices.openUrl")
def test_steam_target_uses_https_helper_route_for_normal_screensaver(
    mock_open,
    mock_browser_route,
    monkeypatch,
) -> None:
    from core.windows import secure_url_launcher

    monkeypatch.setattr(secure_url_launcher, "is_mc_build", lambda: False)
    monkeypatch.setattr(secure_url_launcher, "is_diagnostic_build", lambda: False)
    target = store_target(620)
    assert target is not None

    assert secure_url_launcher.open_steam_target(target, source="steam_store") is True
    mock_open.assert_not_called()
    mock_browser_route.assert_called_once_with(
        target.browser_url,
        fallback=False,
        prefer_direct=False,
        source="steam_store",
    )


@patch("core.windows.secure_url_launcher.open_url", return_value=True)
@patch("core.windows.secure_url_launcher.QDesktopServices.openUrl", return_value=False)
def test_rejected_interactive_steam_target_falls_back_to_https(
    mock_open,
    mock_browser_route,
    monkeypatch,
) -> None:
    from core.windows import secure_url_launcher

    monkeypatch.setattr(secure_url_launcher, "is_mc_build", lambda: True)
    target = store_target(620)
    assert target is not None

    assert secure_url_launcher.open_steam_target(target, source="steam_store") is True
    mock_open.assert_called_once()
    mock_browser_route.assert_called_once_with(
        target.browser_url,
        fallback=True,
        prefer_direct=True,
        source="steam_store",
    )


@patch("core.windows.secure_url_launcher.webbrowser.open")
@patch("core.windows.secure_url_launcher.reddit_helper_bridge")
def test_normal_steam_target_fails_closed_without_secure_helper(
    mock_bridge,
    mock_webbrowser,
    monkeypatch,
) -> None:
    from core.windows import secure_url_launcher

    monkeypatch.setattr(secure_url_launcher, "is_mc_build", lambda: False)
    monkeypatch.setattr(secure_url_launcher, "is_diagnostic_build", lambda: False)
    mock_bridge.is_bridge_available.return_value = False
    target = store_target(620)
    assert target is not None

    assert secure_url_launcher.open_steam_target(target) is False
    mock_webbrowser.assert_not_called()


@patch("core.windows.secure_url_launcher.open_url", return_value=False)
@patch(
    "core.windows.secure_url_launcher.QDesktopServices.openUrl",
    side_effect=RuntimeError("steam://friends/message/76561198000000001"),
)
def test_steam_launch_failure_log_does_not_repeat_private_target(
    _mock_open,
    _mock_browser_route,
    monkeypatch,
    caplog,
) -> None:
    from core.windows import secure_url_launcher

    monkeypatch.setattr(secure_url_launcher, "is_mc_build", lambda: True)
    target = friend_message_target("76561198000000001")
    assert target is not None

    assert secure_url_launcher.open_steam_target(target) is False
    assert target.steam_url not in caplog.text
    assert "76561198000000001" not in caplog.text
