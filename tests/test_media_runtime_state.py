from __future__ import annotations

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo
from widgets.media.runtime_state import (
    MediaWidgetRuntimeState,
    build_retained_display_info,
    cache_retained_display_info,
    mark_provider_probe_attempt,
    should_probe_provider_failover,
)


def test_retained_display_snapshot_downgrades_to_paused() -> None:
    state = MediaWidgetRuntimeState()
    live_info = MediaTrackInfo(
        title="Track",
        artist="Artist",
        album="Album",
        state=MediaPlaybackState.PLAYING,
        artwork=b"art",
        source_app_user_model_id="firefox.exe",
        position_ms=42_000,
        duration_ms=180_000,
    )

    cache_retained_display_info(state, live_info, now=10.0)
    retained = build_retained_display_info(state)

    assert retained is not None
    assert retained is not live_info
    assert retained.state == MediaPlaybackState.PAUSED
    assert retained.title == "Track"
    assert retained.artwork == b"art"
    assert retained.source_app_user_model_id == "firefox.exe"
    assert retained.position_ms == 42_000
    assert retained.duration_ms == 180_000


def test_provider_probe_cooldown() -> None:
    state = MediaWidgetRuntimeState()

    assert should_probe_provider_failover(state, now=1.0) is True
    mark_provider_probe_attempt(state, now=2.0)
    assert should_probe_provider_failover(state, now=3.0) is False
    assert should_probe_provider_failover(state, now=8.5) is True
