"""Studio chrome is derived from SRPSS Settings-theme semantics and keeps contrast in every shipped theme."""
from __future__ import annotations

from pathlib import Path

import pytest

from ui.studio.theme import contrast, studio_theme

THEMES = sorted((Path(__file__).resolve().parents[1] / "themes").glob("*.srtheme"))


def _rgb(text):
    text = text.lstrip("#")[-6:]
    return tuple(int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))


@pytest.mark.parametrize("path", THEMES, ids=lambda p: p.stem[:40])
def test_every_theme_yields_readable_studio_chrome(path):
    from ui.settings_theme_io import load_settings_theme_file
    skin = studio_theme(load_settings_theme_file(path))
    panel = _rgb(skin["panel"])
    assert contrast(_rgb(skin["text"]), panel) >= 4.5
    assert contrast(_rgb(skin["accent"]), panel) >= 3.0
    assert contrast(_rgb(skin["focus"]), panel) >= 3.0
    assert contrast(_rgb(skin["accentText"]), _rgb(skin["accentSoft"])) >= 4.5


def test_chrome_follows_the_theme_not_hard_coded_colours():
    from ui.settings_theme_io import load_settings_theme_file
    if len(THEMES) < 2:
        pytest.skip("needs two theme files")
    skins = [studio_theme(load_settings_theme_file(path)) for path in THEMES[:6]]
    for key in ("bg", "panel", "accent"):
        assert len({skin[key] for skin in skins}) > 1, key


def test_a_theme_change_reskins_subscribers(qt_app):
    from ui.settings_theme_io import load_settings_theme_file
    from ui.settings_theme_runtime import get_active_settings_theme, set_active_settings_theme
    from ui.studio.theme import subscribe_studio_theme
    if not THEMES:
        pytest.skip("no theme files")
    seen = []
    unsubscribe = subscribe_studio_theme(seen.append)
    original = get_active_settings_theme()
    try:
        set_active_settings_theme(load_settings_theme_file(THEMES[0]))
        assert seen and seen[-1] == studio_theme(load_settings_theme_file(THEMES[0]))
    finally:
        set_active_settings_theme(original)
        unsubscribe()
