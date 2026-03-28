"""Shared runtime-state helpers for retained media display behavior.

This module keeps the "retain display snapshot" rules out of the main
MediaWidget class so session loss, provider probing, and playback-state
downgrades are driven by one small contract.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo

PROVIDER_FAILOVER_COOLDOWN_SEC = 5.0


@dataclass
class MediaWidgetRuntimeState:
    """Runtime-only media widget state that should not live in settings."""

    retained_display_info: Optional[MediaTrackInfo] = None
    retained_display_info_ts: float = 0.0
    missing_session_since: float = 0.0
    provider_probe_ts: float = 0.0


def clone_track_info(
    info: MediaTrackInfo,
    *,
    state: Optional[MediaPlaybackState] = None,
) -> MediaTrackInfo:
    """Return a defensive copy of MediaTrackInfo with an optional state override."""

    return MediaTrackInfo(
        title=info.title,
        artist=info.artist,
        album=info.album,
        album_artist=info.album_artist,
        state=state if state is not None else info.state,
        can_play_pause=info.can_play_pause,
        can_next=info.can_next,
        can_previous=info.can_previous,
        artwork=bytes(info.artwork) if info.artwork is not None else None,
    )


def cache_retained_display_info(
    runtime_state: MediaWidgetRuntimeState,
    info: MediaTrackInfo,
    *,
    now: Optional[float] = None,
) -> None:
    """Cache the latest good display snapshot for retained-display mode."""

    runtime_state.retained_display_info = clone_track_info(info)
    runtime_state.retained_display_info_ts = time.monotonic() if now is None else float(now)
    clear_missing_session(runtime_state)


def build_retained_display_info(
    runtime_state: MediaWidgetRuntimeState,
) -> Optional[MediaTrackInfo]:
    """Return a retained display snapshot downgraded to a non-reactive state."""

    retained = runtime_state.retained_display_info
    if retained is None:
        return None

    state = retained.state
    if state in (MediaPlaybackState.STOPPED, MediaPlaybackState.PAUSED):
        downgraded = state
    else:
        downgraded = MediaPlaybackState.PAUSED
    return clone_track_info(retained, state=downgraded)


def note_missing_session(
    runtime_state: MediaWidgetRuntimeState,
    *,
    now: Optional[float] = None,
) -> None:
    """Record that live session acquisition is currently missing."""

    if runtime_state.missing_session_since > 0.0:
        return
    runtime_state.missing_session_since = time.monotonic() if now is None else float(now)


def clear_missing_session(runtime_state: MediaWidgetRuntimeState) -> None:
    """Clear the current missing-session marker."""

    runtime_state.missing_session_since = 0.0


def should_probe_provider_failover(
    runtime_state: MediaWidgetRuntimeState,
    *,
    now: Optional[float] = None,
    cooldown_sec: float = PROVIDER_FAILOVER_COOLDOWN_SEC,
) -> bool:
    """Return True when an alternate-provider probe is allowed again."""

    probe_now = time.monotonic() if now is None else float(now)
    last_probe = float(runtime_state.provider_probe_ts or 0.0)
    return last_probe <= 0.0 or (probe_now - last_probe) >= max(0.1, float(cooldown_sec))


def mark_provider_probe_attempt(
    runtime_state: MediaWidgetRuntimeState,
    *,
    now: Optional[float] = None,
) -> None:
    """Record the time of the latest alternate-provider probe attempt."""

    runtime_state.provider_probe_ts = time.monotonic() if now is None else float(now)


def get_alternate_provider(provider: str) -> str:
    """Return the canonical alternate media provider."""

    current = str(provider or "").strip().lower()
    return "musicbee" if current == "spotify" else "spotify"
