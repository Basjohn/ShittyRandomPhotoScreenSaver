from __future__ import annotations

from types import SimpleNamespace

from core.media import spotify_volume
from core.media.spotify_volume import SpotifyVolumeController


class _FakeVolume:
    def __init__(self) -> None:
        self.set_calls: list[float] = []

    def GetMasterVolume(self) -> float:
        return 0.5

    def SetMasterVolume(self, level: float, _context) -> None:
        self.set_calls.append(float(level))


class _FakeControl:
    def __init__(self, volume: _FakeVolume | None) -> None:
        self._volume = volume

    def QueryInterface(self, _interface):
        if self._volume is None:
            raise RuntimeError("unwritable test session")
        return self._volume


class _FakeSession:
    def __init__(self, process_name: str, volume: _FakeVolume | None) -> None:
        self.Process = SimpleNamespace(name=lambda: process_name)
        self._ctl = _FakeControl(volume)


def _controller(monkeypatch, sessions: list[_FakeSession]):
    reads = {"count": 0}

    def _get_all_sessions():
        reads["count"] += 1
        return sessions

    monkeypatch.setattr(
        spotify_volume,
        "AudioUtilities",
        SimpleNamespace(GetAllSessions=_get_all_sessions),
    )
    monkeypatch.setattr(spotify_volume, "ISimpleAudioVolume", object())
    controller = SpotifyVolumeController.__new__(SpotifyVolumeController)
    controller._available = True
    controller._last_pid = None
    controller._provider = ""
    controller._process_targets = ()
    return controller, reads


def test_browser_volume_prefers_exact_desktop_spotify_session(monkeypatch) -> None:
    browser_volume = _FakeVolume()
    spotify_session_volume = _FakeVolume()
    controller, _reads = _controller(
        monkeypatch,
        [
            _FakeSession("firefox.exe", browser_volume),
            _FakeSession("Spotify.exe", spotify_session_volume),
        ],
    )

    assert controller.configure_volume_target("spotify_browser", "firefox.exe") is True
    assert controller.set_volume(0.4) is True
    assert spotify_session_volume.set_calls == [0.4]
    assert browser_volume.set_calls == []


def test_browser_volume_falls_back_only_to_selected_exact_browser(monkeypatch) -> None:
    firefox_volume = _FakeVolume()
    chrome_volume = _FakeVolume()
    controller, _reads = _controller(
        monkeypatch,
        [
            _FakeSession("spotify.exe", None),
            _FakeSession("chrome.exe", chrome_volume),
            _FakeSession("firefox.exe", firefox_volume),
        ],
    )

    assert controller.configure_volume_target("spotify_browser", "firefox") is True
    assert controller.set_volume(0.3) is True
    assert firefox_volume.set_calls == [0.3]
    assert chrome_volume.set_calls == []


def test_unknown_browser_identity_leaves_core_audio_untouched(monkeypatch) -> None:
    chrome_volume = _FakeVolume()
    controller, reads = _controller(
        monkeypatch,
        [_FakeSession("chrome.exe", chrome_volume)],
    )

    assert controller.configure_volume_target("spotify_browser", "chromium.exe") is False
    assert controller.set_volume(0.2) is False
    assert reads["count"] == 0
    assert chrome_volume.set_calls == []


def test_browser_volume_rejects_near_match_process_names(monkeypatch) -> None:
    near_match_volume = _FakeVolume()
    unrelated_volume = _FakeVolume()
    controller, _reads = _controller(
        monkeypatch,
        [
            _FakeSession("myfirefox.exe", near_match_volume),
            _FakeSession("chrome.exe", unrelated_volume),
        ],
    )

    assert controller.configure_volume_target("spotify_browser", "firefox.exe") is True
    assert controller.set_volume(0.6) is False
    assert near_match_volume.set_calls == []
    assert unrelated_volume.set_calls == []
