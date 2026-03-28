from __future__ import annotations

from rendering.overlay_startup_policy import get_overlay_startup_fade_policy
from widgets.shadow_utils import ShadowFadeProfile


def test_overlay_startup_policy_derives_from_shared_fade_profile(monkeypatch):
    monkeypatch.setattr(ShadowFadeProfile, "DURATION_MS", 2000)

    policy = get_overlay_startup_fade_policy()

    assert policy.primary_warmup_ms == 0
    assert policy.primary_post_fade_buffer_ms == 1000
    assert policy.spotify_secondary_startup_delay_ms == 3000
    assert policy.spotify_secondary_direct_delay_ms == 1600


def test_overlay_startup_policy_keeps_direct_delay_floor(monkeypatch):
    monkeypatch.setattr(ShadowFadeProfile, "DURATION_MS", 1000)

    policy = get_overlay_startup_fade_policy()

    assert policy.spotify_secondary_direct_delay_ms == 1200
