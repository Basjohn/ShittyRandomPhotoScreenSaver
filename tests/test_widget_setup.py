from __future__ import annotations

from types import SimpleNamespace

from rendering import display_overlays
from rendering.widget_setup import compute_expected_overlays
from widgets.shadow_utils import ShadowFadeProfile


def test_compute_expected_overlays_excludes_visualizer_from_primary_wave():
    display = SimpleNamespace(screen_index=0)
    widgets_config = {
        "media": {
            "enabled": True,
            "monitor": "ALL",
            "spotify_volume_enabled": True,
        },
        "spotify_visualizer": {
            "enabled": True,
            "visualizers_enabled": True,
            "monitor": "ALL",
        },
    }

    expected = compute_expected_overlays(display, widgets_config)

    assert "media" in expected
    assert "spotify_volume" in expected
    assert "spotify_visualizer" not in expected


def test_start_overlay_fades_uses_deliberate_primary_and_secondary_startup_delays():
    primary_calls: list[str] = []
    secondary_delays: list[int] = []

    widget = SimpleNamespace(
        _overlay_fade_started=False,
        _overlay_fade_timeout=None,
        _overlay_fade_pending={
            "clock": lambda: primary_calls.append("clock"),
            "weather": lambda: primary_calls.append("weather"),
        },
        _run_spotify_secondary_fades=lambda *, base_delay_ms=0: secondary_delays.append(base_delay_ms),
    )

    scheduled: list[int] = []
    original_single_shot = display_overlays.QTimer.singleShot

    def _fake_single_shot(delay_ms, starter):
        scheduled.append(int(delay_ms))

    display_overlays.QTimer.singleShot = staticmethod(_fake_single_shot)
    try:
        display_overlays.start_overlay_fades(widget)
    finally:
        display_overlays.QTimer.singleShot = original_single_shot

    expected_secondary_delay = display_overlays.SPOTIFY_SECONDARY_STARTUP_DELAY_MS

    assert primary_calls == ["clock", "weather"]
    assert scheduled == []
    assert secondary_delays == [expected_secondary_delay]
    assert widget._spotify_secondary_not_before_ts > 0.0
    assert display_overlays.SPOTIFY_SECONDARY_STARTUP_DELAY_MS == (
        ShadowFadeProfile.DURATION_MS + display_overlays.PRIMARY_OVERLAY_POST_FADE_BUFFER_MS
    )
    assert display_overlays.SPOTIFY_SECONDARY_DIRECT_DELAY_MS >= 1200


def test_start_overlay_fades_does_not_insert_primary_startup_dead_air():
    primary_calls: list[str] = []
    secondary_delays: list[int] = []

    widget = SimpleNamespace(
        _overlay_fade_started=False,
        _overlay_fade_timeout=None,
        _overlay_fade_pending={
            "clock": lambda: primary_calls.append("clock"),
        },
        _run_spotify_secondary_fades=lambda *, base_delay_ms=0: secondary_delays.append(base_delay_ms),
    )

    display_overlays.start_overlay_fades(widget)

    assert primary_calls == ["clock"]
    assert secondary_delays == [display_overlays.SPOTIFY_SECONDARY_STARTUP_DELAY_MS]
