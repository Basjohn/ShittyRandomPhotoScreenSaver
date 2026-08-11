"""Focused contracts for registered GSMTC media-provider identities."""
from __future__ import annotations

from types import SimpleNamespace

from core.media.media_controller import MediaPlaybackState, WindowsGlobalMediaController
from core.media.provider_registry import (
    get_media_provider_display_name,
    get_provider_failover_candidates,
    get_provider_process_exe_name_for_source,
    get_provider_process_exe_names,
    normalize_provider_id,
    preserve_provider_setting,
    provider_matches_source_app_user_model_id,
    provider_supports_app_volume,
)
from core.settings.models import MediaWidgetSettings


def test_spotify_browser_provider_uses_explicit_browser_host_identities() -> None:
    assert normalize_provider_id(" Spotify_Browser ") == "spotify_browser"
    assert get_media_provider_display_name("spotify_browser") == "Spotify Browser (GSMTC)"
    assert provider_matches_source_app_user_model_id("spotify_browser", "Chrome.exe")
    assert provider_matches_source_app_user_model_id("spotify_browser", "MSEdge")
    assert provider_matches_source_app_user_model_id(
        "spotify_browser", r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
    )
    assert not provider_matches_source_app_user_model_id("spotify_browser", "chromium.exe")
    assert not provider_matches_source_app_user_model_id("spotify_browser", "mychrome.exe")
    assert not provider_matches_source_app_user_model_id("spotify", "chrome.exe")
    assert provider_supports_app_volume("spotify_browser") is False
    assert get_provider_process_exe_name_for_source("spotify_browser", "firefox") == "firefox.exe"
    assert (
        get_provider_process_exe_name_for_source(
            "spotify_browser",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        )
        == "chrome.exe"
    )
    assert get_provider_process_exe_name_for_source("spotify_browser", "chromium.exe") is None
    assert get_provider_process_exe_name_for_source("spotify_browser", "mychrome.exe") is None


def test_registry_has_stable_process_and_failover_identities() -> None:
    assert get_provider_process_exe_names("spotify") == ("spotify.exe",)
    assert get_provider_process_exe_names("spotify_browser") == (
        "brave.exe",
        "chrome.exe",
        "firefox.exe",
        "msedge.exe",
        "opera.exe",
        "vivaldi.exe",
    )
    assert get_provider_failover_candidates("spotify") == ("spotify_browser", "musicbee")
    assert get_provider_failover_candidates("spotify_browser") == ("spotify", "musicbee")
    assert get_provider_failover_candidates("retired_alias") == ()
    assert normalize_provider_id("spotify-browser") is None
    assert preserve_provider_setting(None) == "spotify"
    assert preserve_provider_setting("retired_alias") == "retired_alias"
    assert MediaWidgetSettings.from_mapping({"provider": "spotify_browser"}).provider == "spotify_browser"
    assert MediaWidgetSettings.from_mapping({"provider": "retired_alias"}).provider == "retired_alias"


class _PlaybackStatus:
    PLAYING = 1
    PAUSED = 2
    STOPPED = 3


class _Session:
    def __init__(self, source_id: str, status: int = _PlaybackStatus.PAUSED) -> None:
        self.source_app_user_model_id = source_id
        self._status = status

    def get_playback_info(self):
        return SimpleNamespace(playback_status=self._status)


class _Manager:
    def __init__(self, sessions, current=None) -> None:
        self._sessions = list(sessions)
        self._current = current

    def get_sessions(self):
        return self._sessions

    def get_current_session(self):
        return self._current


def _controller(provider: str) -> WindowsGlobalMediaController:
    controller = WindowsGlobalMediaController.__new__(WindowsGlobalMediaController)
    controller._provider_id = provider
    controller._app_filter = provider
    controller._PlaybackStatus = _PlaybackStatus
    return controller


def test_session_selection_prefers_current_matching_session_then_playing_then_source_id() -> None:
    chrome_paused = _Session("chrome.exe", _PlaybackStatus.PAUSED)
    edge_playing = _Session("msedge.exe", _PlaybackStatus.PLAYING)
    brave_playing = _Session("brave.exe", _PlaybackStatus.PLAYING)
    unrelated_current = _Session("Spotify.exe", _PlaybackStatus.PLAYING)
    controller = _controller("spotify_browser")

    manager = _Manager([chrome_paused, edge_playing, brave_playing], edge_playing)
    assert controller._select_media_session(manager) is edge_playing

    manager = _Manager([chrome_paused, edge_playing, brave_playing], unrelated_current)
    assert controller._select_media_session(manager) is brave_playing


def test_session_selection_accepts_matching_current_browser_when_enumeration_is_empty() -> None:
    controller = _controller("spotify_browser")

    for source_id in ("firefox.exe", "chrome.exe"):
        current = _Session(source_id, _PlaybackStatus.PLAYING)
        assert controller._select_media_session(_Manager([], current)) is current


def test_session_source_diagnostics_are_bounded() -> None:
    sessions = [_Session(f"browser-{index}.exe") for index in range(20)]

    values = WindowsGlobalMediaController._session_source_ids_for_log(sessions)

    assert len(values) == 17
    assert values[-1] == "<4 more>"


def test_provider_failover_uses_one_session_snapshot_in_registry_order() -> None:
    spotify = _Session("Spotify.exe", _PlaybackStatus.PAUSED)
    browser = _Session("msedge.exe", _PlaybackStatus.PLAYING)
    manager = _Manager([browser, spotify], browser)
    manager.session_reads = 0
    original_get_sessions = manager.get_sessions

    def _get_sessions_once():
        manager.session_reads += 1
        return original_get_sessions()

    manager.get_sessions = _get_sessions_once
    controller = _controller("spotify")

    provider, session = controller._select_media_session_for_providers(
        manager,
        ("spotify", "spotify_browser", "musicbee"),
    )

    assert (provider, session) == ("spotify", spotify)
    assert manager.session_reads == 1


def test_io_worker_failover_runs_one_inline_gsmtc_query_without_nested_submit() -> None:
    class _Properties:
        title = "Browser Track"
        artist = "Artist"
        album_title = "Album"
        album_artist = ""
        thumbnail = None

    class _BrowserSession(_Session):
        async def try_get_media_properties_async(self):
            return _Properties()

        def get_playback_info(self):
            controls = SimpleNamespace(
                is_play_pause_enabled=True,
                is_next_enabled=True,
                is_previous_enabled=True,
            )
            return SimpleNamespace(playback_status=self._status, controls=controls)

    browser = _BrowserSession("msedge.exe", _PlaybackStatus.PLAYING)
    manager = _Manager([browser], browser)

    class _MediaManager:
        requests = 0

        @classmethod
        async def request_async(cls):
            cls.requests += 1
            return manager

    class _NoNestedSubmit:
        def submit_io_task(self, *_args, **_kwargs):
            raise AssertionError("IO-worker query must not submit into the IO pool")

    controller = _controller("spotify")
    controller._available = True
    controller._MediaManager = _MediaManager
    controller._thread_manager = _NoNestedSubmit()
    controller._gsmc_inflight = False
    controller._last_valid_info = None
    controller._last_valid_info_ts = 0.0
    controller._timeout_cache_ttl = 30.0

    provider, info = controller.get_current_track_from_io_worker(
        ("spotify_browser", "musicbee")
    )

    assert provider == "spotify_browser"
    assert info is not None and info.title == "Browser Track"
    assert info.source_app_user_model_id == "msedge.exe"
    assert _MediaManager.requests == 1


def test_session_selection_rejects_unrelated_and_false_positive_sources() -> None:
    controller = _controller("spotify_browser")
    unrelated = _Session("Spotify.exe", _PlaybackStatus.PLAYING)
    near_match = _Session("mychrome.exe", _PlaybackStatus.PLAYING)

    assert controller._select_media_session(_Manager([unrelated, near_match], unrelated)) is None


def test_browser_process_detection_checks_registered_host_identities(monkeypatch) -> None:
    controller = _controller("spotify_browser")
    checked: list[tuple[str, ...]] = []

    def _exists(exe_names) -> bool:
        checked.append(tuple(exe_names))
        return "msedge.exe" in exe_names

    monkeypatch.setattr("core.media.media_controller._win_any_process_exists", _exists)

    assert controller.is_app_process_running() is True
    assert checked == [
        (
            "brave.exe",
            "chrome.exe",
            "firefox.exe",
            "msedge.exe",
            "opera.exe",
            "vivaldi.exe",
        )
    ]
