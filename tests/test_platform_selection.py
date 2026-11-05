"""Every owner with a Linux counterpart still selects its Windows implementation on Windows.

Runs on every OS (the Windows branch is forced); the Linux branches are covered by
``tests/test_linux_*.py``, which never run off Linux (Docs/Guardrails/Linux_Compatibility.md §7).
"""
from __future__ import annotations

from dataclasses import replace

import pytest


def test_display_power_selects_the_console_display_notifier(monkeypatch) -> None:
    import sys

    from core import display_power
    from core.windows import display_power_notifier

    built = []

    class FakeNotifier:
        def __init__(self, deliver):
            built.append(deliver)

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(display_power_notifier, "WindowsDisplayPowerNotifier", FakeNotifier)
    monkeypatch.setattr(display_power, "LinuxMutterDisplayPowerWatcher", lambda *_: pytest.fail("Mutter on Windows"))
    deliver = lambda _state: None  # noqa: E731
    assert isinstance(display_power.create_display_power_backend(deliver, lambda _on: None), FakeNotifier)
    assert built == [deliver]


def test_media_factory_builds_gsmtc_and_never_mpris(monkeypatch, windows_platform) -> None:
    from core.media import media_controller, mpris_controller

    monkeypatch.setattr(mpris_controller, "create_mpris_controller", lambda **_: pytest.fail("MPRIS on Windows"))
    built = []

    class FakeWindowsController:
        _available = True

        def __init__(self, **kwargs):
            built.append(kwargs)

    monkeypatch.setattr(media_controller, "WindowsGlobalMediaController", FakeWindowsController)
    assert isinstance(media_controller.create_media_controller(app_filter="spotify"), FakeWindowsController)
    assert built and built[0]["app_filter"] == "spotify"


def test_audio_capture_factory_keeps_wasapi_loopback(monkeypatch) -> None:
    from utils import audio_capture, audio_capture_pulse

    monkeypatch.setattr(audio_capture.platform, "system", lambda: "Windows")
    monkeypatch.setattr(audio_capture_pulse, "create_pulse_monitor_backend",
                        lambda *_: pytest.fail("monitor backend on Windows"))
    assert isinstance(audio_capture.create_audio_capture(), audio_capture.PyAudioWPatchBackend)


def test_volume_owners_are_core_audio(monkeypatch, windows_platform) -> None:
    from core.media import audio_event_session
    from core.media.core_audio_callback_probe import CoreAudioCallbackProbe
    from core.media.spotify_volume import SpotifyVolumeController
    from widgets import media_volume_runtime

    callbacks = {"on_volume": lambda v, m: None, "on_default_device": lambda: None}
    assert isinstance(audio_event_session._platform_probe(**callbacks), CoreAudioCallbackProbe)
    assert isinstance(media_volume_runtime._create_volume_controller("spotify"), SpotifyVolumeController)


def test_orbit_capture_is_native_confinement(monkeypatch, windows_platform) -> None:
    from rendering.quick import pointer_capture

    built = []
    monkeypatch.setattr(pointer_capture, "NativeOrbitCapture", lambda window: built.append(window) or "native")
    window = object()
    assert pointer_capture.new_orbit_capture(window) == "native" and built == [window]


def test_settings_backdrop_is_native_dwm_without_an_underlay(monkeypatch, windows_platform) -> None:
    from ui.settings_dialog import SettingsDialog
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NativeBackdropStyle, Rgba

    class DialogStub:
        _apply_native_backdrop_theme = SettingsDialog._apply_native_backdrop_theme
        _apply_material_underlay = SettingsDialog._apply_material_underlay

        def __init__(self) -> None:
            self._backdrop_applied = False
            self._native_backdrop_mode = None
            self._material_underlay = None
            self.updates = 0

        def winId(self) -> int:
            return 4242

        def update(self) -> None:
            self.updates += 1

    calls = []
    monkeypatch.setattr("core.windows.dwm_blur.enable_glass_blur", lambda hwnd: calls.append(hwnd) or True)
    theme = replace(DEFAULT_DARK_SETTINGS_THEME, backdrop=NativeBackdropStyle(mode="glass", tint=Rgba(0, 0, 0, 0)))
    dialog = DialogStub()

    assert dialog._apply_native_backdrop_theme(theme) is True
    assert calls == [4242]
    assert dialog._material_underlay is None and dialog.updates == 0

