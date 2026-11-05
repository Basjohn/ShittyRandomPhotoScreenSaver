"""Linux MPRIS media controller against a fake session bus (no D-Bus needed)."""
from __future__ import annotations

import threading

import pytest

from core.media.media_controller import MediaPlaybackState, media_track_identity
from core.media.mpris_controller import LinuxMprisMediaController, mpris_source_id


class FakeBus:
    def __init__(self, players: dict[str, dict]):
        self.players = players
        self.calls: list[tuple[str, str, str | None, tuple]] = []
        self.interrupted = threading.Event()

    def available(self) -> bool:
        return True

    def list_players(self) -> list[str]:
        return sorted(self.players)

    def player_properties(self, bus_name: str) -> dict:
        return self.players[bus_name]

    def call_player(self, bus_name, method, signature=None, args=()) -> bool:
        self.calls.append((bus_name, method, signature, args))
        return True

    def listen_for_changes(self, on_change, stop: threading.Event) -> None:
        on_change("mpris_properties")
        self.interrupted.wait(2.0)

    def interrupt_listen(self) -> None:
        self.interrupted.set()


def _player(status="Playing", title="Song", artists=("A", "B"), length=180_000_000, art=""):
    return {
        "PlaybackStatus": status,
        "Position": 42_000_000,
        "CanPlay": True, "CanPause": True, "CanGoNext": True, "CanGoPrevious": False, "CanSeek": True,
        "Metadata": {
            "mpris:trackid": "/track/1", "xesam:title": title, "xesam:artist": list(artists),
            "xesam:album": "Album", "xesam:albumArtist": ["AA"], "mpris:length": length, "mpris:artUrl": art,
        },
    }


@pytest.mark.parametrize(("bus_name", "expected"), [
    ("org.mpris.MediaPlayer2.spotify", "spotify"),
    ("org.mpris.MediaPlayer2.firefox.instance_1_42", "firefox"),
    ("org.mpris.MediaPlayer2.chromium.instance9921", "chrome"),
    ("org.mpris.MediaPlayer2.vlc", "vlc"),
])
def test_bus_names_map_to_registry_identities(bus_name, expected) -> None:
    assert mpris_source_id(bus_name) == expected


def test_provider_matching_prefers_a_playing_player_and_maps_track_fields() -> None:
    bus = FakeBus({
        "org.mpris.MediaPlayer2.firefox.instance_1_2": _player(title="Tab"),
        "org.mpris.MediaPlayer2.spotify": _player(status="Paused", title="Paused Song"),
        "org.mpris.MediaPlayer2.spotify.instance7": _player(title="Playing Song"),
    })
    controller = LinuxMprisMediaController(app_filter="spotify", bus=bus)

    provider, info = controller.get_current_track_from_io_worker(())
    assert provider == "spotify" and info.title == "Playing Song"
    assert info.state == MediaPlaybackState.PLAYING
    assert (info.artist, info.album_artist, info.position_ms, info.duration_ms) == ("A, B", "AA", 42_000, 180_000)
    assert info.can_play_pause and info.can_next and not info.can_previous and info.can_seek
    # A browser tab is never the Spotify provider; the browser provider is a fallback.
    only_browser = LinuxMprisMediaController(app_filter="spotify", bus=FakeBus({
        "org.mpris.MediaPlayer2.firefox.instance_1_2": _player(title="Tab")}))
    assert only_browser.get_current_track() is None
    assert only_browser.get_current_track_from_io_worker(("spotify_browser",))[0] == "spotify_browser"


def test_unknown_length_disables_seek() -> None:
    controller = LinuxMprisMediaController(bus=FakeBus({"org.mpris.MediaPlayer2.spotify": _player(length=0)}))
    info = controller.get_current_track()
    assert not info.can_seek and info.duration_ms is None
    assert controller.seek_fraction(0.5) is False


def test_file_artwork_is_read_once_and_skipped_for_the_same_track(tmp_path) -> None:
    art = tmp_path / "cover.png"
    art.write_bytes(b"png-bytes")
    bus = FakeBus({"org.mpris.MediaPlayer2.spotify": _player(art=art.as_uri())})
    controller = LinuxMprisMediaController(bus=bus)

    first = controller.get_current_track()
    assert first.artwork == b"png-bytes"
    _provider, reused = controller.get_current_track_from_io_worker((), reuse_artwork_identity=media_track_identity(first))
    assert reused.artwork is None


def test_commands_report_results_dedupe_inflight_and_seek_by_track_position() -> None:
    bus = FakeBus({"org.mpris.MediaPlayer2.spotify": _player()})
    controller = LinuxMprisMediaController(bus=bus)
    queued, results = [], []
    controller.set_work_executor(lambda job: queued.append(job) or True)
    controller.set_command_result_handler(results.append)
    controller.get_current_track()

    assert controller.play_pause(MediaPlaybackState.PAUSED) is True
    assert controller.next() is False  # a command is already inflight
    queued.pop()()
    assert controller.seek_fraction(0.5) is True
    queued.pop()()

    assert [call[1:] for call in bus.calls] == [("Pause", None, ()), ("SetPosition", "ox", ("/track/1", 90_000_000))]
    assert [(r.operation, r.succeeded) for r in results] == [("pause", True), ("seek", True)]


def test_retired_controller_admits_nothing() -> None:
    controller = LinuxMprisMediaController(bus=FakeBus({"org.mpris.MediaPlayer2.spotify": _player()}))
    controller.set_work_executor(lambda job: True)
    controller.retire()
    assert controller.get_current_track() is None
    assert controller.play_pause() is False


def test_factory_selects_mpris_off_windows_and_is_loud_without_a_bus(monkeypatch) -> None:
    from core.media import media_controller, mpris_controller

    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", False)
    monkeypatch.setattr(mpris_controller, "JeepneySessionBus", lambda: FakeBus({}))
    assert isinstance(media_controller.create_media_controller(), LinuxMprisMediaController)

    class NoBus(FakeBus):
        def available(self) -> bool:
            return False

    monkeypatch.setattr(mpris_controller, "JeepneySessionBus", lambda: NoBus({}))
    monkeypatch.setattr(mpris_controller, "_UNAVAILABLE_ANNOUNCED", False)
    warnings = []
    monkeypatch.setattr(mpris_controller.logger, "warning", lambda message, *args: warnings.append(message % args))
    assert isinstance(media_controller.create_media_controller(), media_controller.NoOpMediaController)
    assert warnings and "[PLATFORM]" in warnings[0] and "no D-Bus session bus" in warnings[0]




def test_observation_stop_interrupts_the_blocking_listener() -> None:
    from core.threading.manager import ThreadManager

    bus = FakeBus({"org.mpris.MediaPlayer2.spotify": _player()})
    manager = ThreadManager()
    try:
        controller = LinuxMprisMediaController(thread_manager=manager, bus=bus)
        dirty, established = [], threading.Event()
        assert controller.start_event_observation(dirty.append, lambda ok, detail: established.set())
        assert established.wait(2.0)
        controller.stop_event_observation()
        assert bus.interrupted.is_set() and not controller.is_event_observation_active()
        assert dirty == ["mpris_properties"]
    finally:
        manager.shutdown()
