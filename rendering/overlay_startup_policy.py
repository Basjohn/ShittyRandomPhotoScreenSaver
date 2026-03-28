from __future__ import annotations

from dataclasses import dataclass

from widgets.shadow_utils import ShadowFadeProfile


@dataclass(frozen=True)
class OverlayStartupFadePolicy:
    """Canonical startup timing for the primary overlay wave and Spotify second wave."""

    primary_warmup_ms: int
    primary_post_fade_buffer_ms: int
    spotify_secondary_startup_delay_ms: int
    spotify_secondary_direct_delay_ms: int

    @classmethod
    def from_shared_fade_profile(cls) -> "OverlayStartupFadePolicy":
        fade_ms = ShadowFadeProfile.default_duration_ms()
        primary_warmup_ms = 0
        primary_post_fade_buffer_ms = 1000
        return cls(
            primary_warmup_ms=primary_warmup_ms,
            primary_post_fade_buffer_ms=primary_post_fade_buffer_ms,
            spotify_secondary_startup_delay_ms=fade_ms + primary_post_fade_buffer_ms,
            spotify_secondary_direct_delay_ms=max(1200, int(fade_ms * 0.8)),
        )


def get_overlay_startup_fade_policy() -> OverlayStartupFadePolicy:
    """Return the current overlay startup policy derived from the shared fade profile."""

    return OverlayStartupFadePolicy.from_shared_fade_profile()
