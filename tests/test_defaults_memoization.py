"""Canonical defaults are resolved once per profile and handed out as private copies (LC-06)."""

from __future__ import annotations

from pathlib import Path

import pytest

import core.settings.defaults as defaults_module
from core.settings.default_contract import MC_PROFILE, get_canonical_default
from core.settings.defaults import get_default_setting, get_default_settings

ROOT = Path(__file__).resolve().parents[1]


def test_resolved_defaults_are_built_once_per_profile(monkeypatch) -> None:
    calls: list[str] = []
    real = defaults_module.normalize_visualizer_section_mapping

    def _counting(*args, **kwargs):
        calls.append(kwargs.get("prefix", ""))
        return real(*args, **kwargs)

    monkeypatch.setattr(defaults_module, "normalize_visualizer_section_mapping", _counting)
    defaults_module._resolved_defaults_readonly.cache_clear()
    try:
        for _ in range(3):
            get_default_settings()
            get_default_settings(MC_PROFILE)
            get_default_setting("transitions")
            get_default_setting("widgets.spotify_visualizer")
        assert len(calls) == 2
    finally:
        defaults_module._resolved_defaults_readonly.cache_clear()


def test_callers_receive_private_copies() -> None:
    first = get_default_settings()
    first["widgets"]["spotify_visualizer"]["poison"] = True
    first["transitions"]["type"] = "poison"

    second = get_default_settings()
    assert "poison" not in second["widgets"]["spotify_visualizer"]
    assert second["transitions"]["type"] != "poison"

    section = get_default_setting("transitions")
    section["type"] = "poison"
    assert get_default_setting("transitions.type") != "poison"


def test_resolved_lookup_matches_full_tree_and_profiles() -> None:
    full = get_default_settings()
    assert get_default_setting("widgets.spotify_visualizer") == full["widgets"]["spotify_visualizer"]
    assert get_default_setting("widgets.global") == full["widgets"]["global"]
    assert get_default_setting("display.hw_accel") == full["display"]["hw_accel"]
    # Non-visualizer sections are identical to the raw editable authority.
    assert get_default_setting("transitions") == get_canonical_default("transitions")
    mc = get_default_settings(MC_PROFILE)
    assert get_default_setting("widgets", MC_PROFILE) == mc["widgets"]

    assert get_default_setting("widgets.no_such_widget", missing=None) is None
    with pytest.raises(KeyError):
        get_default_setting("widgets.no_such_widget")


@pytest.mark.parametrize(
    "relative_path",
    [
        "engine/display_manager.py",
        "rendering/quick/transitions/request_resolution.py",
        "rendering/widget_descriptors.py",
    ],
)
def test_runtime_hot_paths_read_sections_not_the_whole_tree(relative_path: str) -> None:
    """Context menu, transition batches and widget routing copy only what they read."""

    source = (ROOT / relative_path).read_text(encoding="utf-8")
    assert "get_default_settings(" not in source
