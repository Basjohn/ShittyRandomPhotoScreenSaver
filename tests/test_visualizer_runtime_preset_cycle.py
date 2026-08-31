"""H8 detached preset-cycle and Custom-cache contracts."""

from __future__ import annotations

from copy import deepcopy

import pytest

from core.settings.defaults import get_default_settings
from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    get_preset_key,
)
from core.settings.visualizer_presets import (
    build_normalized_custom_snapshot,
    get_custom_preset_index,
    get_preset_count,
    get_preset_settings,
    normalize_visualizer_custom_snapshot_cache,
)
from core.settings.visualizer_runtime_preset_cycle import (
    resolve_next_visualizer_runtime_preset,
)


def _default_visualizer_config() -> dict:
    return deepcopy(
        get_default_settings("Screensaver")["widgets"]["spotify_visualizer"]
    )


def test_flat_shipped_custom_cache_migrates_and_nested_snapshot_wins() -> None:
    cache = {
        "bubble.bubble_growth": 4.25,
        "bubble.mode": "bubble",
        "bubble": {"mode": "bubble", "bubble_growth": 7.5},
        "devcurve.devcurve_growth": 2.0,
    }

    normalized = normalize_visualizer_custom_snapshot_cache(cache)

    assert normalized == {
        "bubble": {"mode": "bubble", "bubble_growth": 7.5},
        "devcurve": {"devcurve_growth": 2.0},
    }
    assert cache["bubble.bubble_growth"] == 4.25


@pytest.mark.parametrize("mode", VISUALIZER_MODE_IDS)
def test_every_active_mode_wraps_from_custom_without_changing_mode(mode: str) -> None:
    config = _default_visualizer_config()
    custom_index = get_custom_preset_index(mode)
    config["mode"] = mode
    config[get_preset_key(mode)] = custom_index
    cache = {mode: build_normalized_custom_snapshot(mode, config)}
    before_config = deepcopy(config)
    before_cache = deepcopy(cache)

    target = resolve_next_visualizer_runtime_preset(config, cache, mode=mode)

    assert target.mode == mode
    assert target.source_index == custom_index
    assert target.target_index == 0
    assert target.visualizer_config["mode"] == mode
    assert target.visualizer_config[get_preset_key(mode)] == 0
    assert config == before_config
    assert cache == before_cache


def test_custom_roundtrip_is_lossless_and_curated_target_replaces_values() -> None:
    mode = "spectrum"
    config = _default_visualizer_config()
    custom_index = get_custom_preset_index(mode)
    config.update(
        {
            "mode": mode,
            get_preset_key(mode): custom_index,
            "spectrum_growth": 9.75,
            "spectrum_glow_intensity": 0.17,
        }
    )
    original_custom = build_normalized_custom_snapshot(mode, config)
    cache: dict = {}

    target = resolve_next_visualizer_runtime_preset(config, cache, mode=mode)
    curated = get_preset_settings(mode, 0)
    assert target.visualizer_config["spectrum_growth"] == pytest.approx(
        curated["spectrum_growth"]
    )
    assert target.visualizer_config["spectrum_growth"] != pytest.approx(9.75)

    for _ in range(get_preset_count(mode) - 1):
        target = resolve_next_visualizer_runtime_preset(
            target.visualizer_config,
            target.custom_presets,
            mode=mode,
        )

    assert target.target_index == custom_index
    assert build_normalized_custom_snapshot(
        mode,
        target.visualizer_config,
    ) == original_custom


def test_missing_mode_cache_seeds_from_raw_section_before_first_mutation() -> None:
    mode = "devcurve"
    config = _default_visualizer_config()
    config.update(
        {
            "mode": mode,
            get_preset_key(mode): 0,
            "devcurve_growth": 8.125,
        }
    )
    expected = build_normalized_custom_snapshot(mode, config)

    target = resolve_next_visualizer_runtime_preset(config, {}, mode=mode)

    assert target.custom_presets[mode] == expected
    assert target.custom_presets_changed is True


def test_malformed_custom_cache_is_rejected_before_activation() -> None:
    config = _default_visualizer_config()
    config["mode"] = "bubble"

    with pytest.raises(ValueError, match="invalid entries"):
        resolve_next_visualizer_runtime_preset(
            config,
            {"not-a-mode": {"bubble_growth": 3.0}},
            mode="bubble",
        )
