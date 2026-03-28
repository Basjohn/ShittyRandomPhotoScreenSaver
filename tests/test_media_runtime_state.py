from __future__ import annotations

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo
from widgets.media.runtime_state import (
    MediaWidgetRuntimeState,
    build_retained_display_info,
    cache_retained_display_info,
    get_alternate_provider,
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
    )

    cache_retained_display_info(state, live_info, now=10.0)
    retained = build_retained_display_info(state)

    assert retained is not None
    assert retained is not live_info
    assert retained.state == MediaPlaybackState.PAUSED
    assert retained.title == "Track"
    assert retained.artwork == b"art"


def test_provider_probe_cooldown_and_alternate_provider() -> None:
    state = MediaWidgetRuntimeState()

    assert should_probe_provider_failover(state, now=1.0) is True
    mark_provider_probe_attempt(state, now=2.0)
    assert should_probe_provider_failover(state, now=3.0) is False
    assert should_probe_provider_failover(state, now=8.5) is True
    assert get_alternate_provider("spotify") == "musicbee"
    assert get_alternate_provider("musicbee") == "spotify"
