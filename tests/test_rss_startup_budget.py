"""The engine's wallpaper-pool target follows the real runtime queue caps.

Acquisition, rotation and pool behaviour live in tests/test_wallpaper_coordinator.py.
"""
from __future__ import annotations

from types import SimpleNamespace

from engine.engine_rss import get_rss_startup_target_total


def test_rss_startup_target_uses_real_runtime_caps() -> None:
    engine = SimpleNamespace(
        settings_manager=SimpleNamespace(
            get=lambda key, default=None: {
                "sources.rss_background_cap": 30,
                "sources.rss_rotating_cache_size": 20,
            }.get(key, default)
        )
    )

    assert get_rss_startup_target_total(engine) == 30
