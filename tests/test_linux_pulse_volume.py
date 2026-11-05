"""Linux volume owners (pactl) and their platform selection, without a sound server."""
from __future__ import annotations

import io

import pytest

from core.media import pulse_volume

SINK_INPUTS = """Sink Input #7
\tDriver: protocol-native.c
\tVolume: front-left: 32768 /  50% / -18.06 dB,   front-right: 32768 /  50% / -18.06 dB
\tProperties:
\t\tapplication.name = "Spotify"
\t\tapplication.process.binary = "spotify"
Sink Input #9
\tVolume: mono: 65536 / 100% / 0.00 dB
\tProperties:
\t\tapplication.process.binary = "chromium"
"""


def test_volume_text_parses_to_the_channel_average() -> None:
    assert pulse_volume.parse_volume_fraction("Volume: front-left: 32768 /  50% / -18 dB,   front-right: 65536 / 100%") == 0.75
    assert pulse_volume.parse_volume_fraction("Volume: mono: 131072 / 200%") == 1.0
    assert pulse_volume.parse_volume_fraction("garbage") is None


def test_app_controller_targets_registry_processes_and_sets_the_matching_input(monkeypatch) -> None:
    calls = []

    def fake_pactl(*args, timeout=3.0):
        calls.append(args)
        return SINK_INPUTS if args == ("list", "sink-inputs") else ""

    monkeypatch.setattr(pulse_volume, "pactl", fake_pactl)
    monkeypatch.setattr(pulse_volume, "pactl_available", lambda: True)
    spotify = pulse_volume.PulseAppVolumeController("spotify")
    assert spotify.process_targets == ("spotify",)
    assert spotify.get_volume() == 0.5
    assert spotify.set_volume(0.25) is True
    assert calls[-1] == ("set-sink-input-volume", "7", str(round(0.25 * 65536)))

    browser = pulse_volume.PulseAppVolumeController("spotify_browser")
    assert browser.process_targets == ()  # inert until the media source names its host
    assert browser.configure_volume_target("spotify_browser", "chrome")
    assert browser.process_targets[0] == "spotify" and "chromium" in browser.process_targets
    assert browser.get_volume() == 0.5  # desktop Spotify keeps target priority over the browser
    without_desktop = SINK_INPUTS.replace('binary = "spotify"', 'binary = "other"')
    monkeypatch.setattr(pulse_volume, "pactl", lambda *a, **k: without_desktop)
    assert browser.get_volume() == 1.0  # then the named browser host
    monkeypatch.setattr(pulse_volume, "pactl", lambda *a, **k: without_desktop.replace("chromium", "firefox"))
    assert browser.get_volume() is None  # never another browser


class _Lines:
    def __init__(self, lines):
        self.stdout = io.StringIO("".join(lines))


def test_system_probe_reports_volume_and_default_device_changes_from_subscribe(monkeypatch) -> None:
    states = iter([("sink-b", 0.5, False), ("sink-b", 0.5, True), ("sink-c", 0.5, True)])
    known_sinks = []
    monkeypatch.setattr(pulse_volume, "_default_sink_state", lambda sink=None: known_sinks.append(sink) or next(states))
    volumes, devices = [], []
    probe = pulse_volume.PulseSystemVolumeProbe(on_volume=lambda v, m: volumes.append((v, m)),
                                                on_default_device=lambda: devices.append(True))
    probe._state, probe._active = ("sink-b", 0.4, False), True
    probe._read(_Lines([
        "Event 'change' on sink #3\n",
        "Event 'new' on sink-input #12\n",  # app streams never re-query the endpoint
        "Event 'change' on sink #3\n",
        "Event 'change' on server #-1\n",
    ]))
    assert volumes == [(0.5, False), (0.5, True)]
    assert devices == [True]
    assert known_sinks == ["sink-b", "sink-b", None]  # only the server event re-resolves the default sink
    assert probe.snapshot() == (0.5, True)
    with pytest.raises(ValueError):
        probe.set_volume(1.5)




def test_session_listener_follows_only_the_selected_stream_and_its_removal(monkeypatch, app_shared_thread_manager) -> None:
    import threading as _threading

    pushed = []

    class Mailbox:
        endpoint_token = 3

        def push_volume(self, token, volume, muted):
            pushed.append(("volume", token, volume, muted))

        def push_device_change(self):
            pushed.append(("device",))

    class Bridge:
        def __init__(self, consume):
            self.mailbox = Mailbox()

        def close(self):
            pushed.append(("closed",))

    lines = ["Event 'change' on sink-input #9\n", "Event 'change' on sink-input #7\n",
             "Event 'remove' on sink-input #7\n", "Event 'change' on sink-input #7\n"]

    class Process(_Lines):
        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(pulse_volume, "pactl_available", lambda: True)
    monkeypatch.setattr(pulse_volume, "_sink_input_details",
                        lambda: [(7, "spotify", 0.5, False), (9, "chromium", 1.0, False)])
    monkeypatch.setattr(pulse_volume.subprocess, "Popen", lambda *a, **k: Process(lines))
    listener = pulse_volume.PulseSessionVolumeListener(on_volume=lambda v, m: None, on_disconnected=lambda: None,
                                                       bridge_factory=Bridge)
    assert listener.start(("spotify", "chromium")) is True
    listener._reader.stop(wait=True, timeout=2.0)  # the fake stdout ends; wait for the reader
    # Stream 9 is not the selected one; stream 7 changes once, then its removal ends observation.
    assert pushed == [("volume", 3, 0.5, False), ("device",)]
    listener.close()
    assert not listener.active


def test_volume_owners_are_pactl_off_windows(monkeypatch) -> None:
    from core.media import audio_event_session
    from widgets import media_volume_runtime

    callbacks = {"on_volume": lambda v, m: None, "on_default_device": lambda: None}
    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", False)
    assert isinstance(audio_event_session._platform_probe(**callbacks), pulse_volume.PulseSystemVolumeProbe)
    assert isinstance(media_volume_runtime._create_volume_controller("spotify"), pulse_volume.PulseAppVolumeController)


def test_subscriptions_refuse_to_start_without_a_thread_manager_worker(monkeypatch) -> None:
    from core.threading.manager import ThreadManager

    monkeypatch.setattr(ThreadManager, "get_app_shared", classmethod(lambda cls: None))
    monkeypatch.setattr(pulse_volume, "pactl_available", lambda: True)
    monkeypatch.setattr(pulse_volume, "_default_sink_state", lambda sink=None: ("sink", 0.5, False))
    terminated = []

    class Process(_Lines):
        def terminate(self):
            terminated.append(True)

    monkeypatch.setattr(pulse_volume.subprocess, "Popen", lambda *a, **k: Process([]))
    probe = pulse_volume.PulseSystemVolumeProbe(on_volume=lambda v, m: None, on_default_device=lambda: None)
    assert probe.start() is False and terminated == [True]  # no raw-thread fallback; sidecar ended
