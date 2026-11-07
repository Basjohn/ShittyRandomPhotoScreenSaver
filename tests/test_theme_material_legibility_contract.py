"""Theme materials and legibility (operator, 8 Nov 2026): Settings themes show Frosted, Mica and Smoked as well as
Glass and Acrylic, a pair keeps one material, light themes get a tinted pale material instead of an opaque shell over
untinted Glass, and every text role holds 4.5:1 small / 3:1 large on its material over any wallpaper.

What the bars protect (themes are authored content: every expectation is derived from the theme files, the canonical
contrast function ``ui.theme_semantics.contrast_ratio`` and the material recipes, never a pinned colour or name):

* every shipped light theme and every theme on Frosted, Mica or Smoked: each Settings text role over its surface
  stack over the theme's material over a black and a white desktop (``tools/theme_legibility.py``: compositing is
  affine in the desktop colour, so those two bound every wallpaper), and each card text role of its Widget mirror on
  the card's own surfaces;
* a light Settings theme names a tinted material (an untinted Glass window over a dark desktop cannot carry dark
  text unless its shell is made opaque, which hides the material: the "no material at all" defect);
* every theme with a material lets it show: its window surface (``window.dialog_glass``) is not the window's base;
* the recipes: Frosted is lighter and denser than its authored tint, Mica denser, Smoked darker and greyer;
* the native mapping: every tinted material is AccentPolicy Acrylic with the material's own tint;
* a stored selection of a pack theme whose material tag changed still resolves to it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
THEMES = ROOT / "themes"
NEW_MATERIALS = ("frosted", "mica", "smoked")


def _pairs():
    from ui.settings_theme_io import load_settings_theme_file
    from ui.widget_theme_io import load_widget_theme_file

    mirrors = {}
    for path in sorted((THEMES / "widgets").glob("*.srwtheme")):
        theme = load_widget_theme_file(path)
        if theme.linked_settings_theme_id:
            mirrors[theme.linked_settings_theme_id] = theme
    return [(path, load_settings_theme_file(path), mirrors.get(f"file:{path.name}"))
            for path in sorted(THEMES.glob("*.srtheme"))]


def _subjects():
    from ui.theme_semantics import settings_theme_is_light

    return [(path, spec, mirror) for path, spec, mirror in _pairs()
            if settings_theme_is_light(spec) or spec.backdrop.mode in NEW_MATERIALS]


def test_light_and_new_material_themes_hold_contrast_on_their_material_over_any_wallpaper() -> None:
    from tools.theme_legibility import settings_theme_legibility, widget_theme_legibility

    subjects = _subjects()
    assert subjects, "the shipped pack has no light or Frosted/Mica/Smoked theme"
    failures = []
    for path, spec, mirror in subjects:
        for result in settings_theme_legibility(spec).values():
            if not result.passes:
                failures.append((path.name, "settings", result.role, result.worst, result.bar, result.where))
        if mirror is not None:
            assert mirror.surface_material == spec.backdrop.mode, path.name     # one material per pair
            for result in widget_theme_legibility(mirror).values():
                if not result.passes:
                    failures.append((path.name, "card", result.role, result.worst, result.bar, result.where))
    assert not failures, failures


def test_the_shipped_pack_uses_every_settings_material() -> None:
    modes = {spec.backdrop.mode for _path, spec, _mirror in _pairs()}
    assert set(NEW_MATERIALS) <= modes


def test_a_light_settings_theme_names_a_tinted_material() -> None:
    from ui.theme_semantics import settings_theme_is_light

    light = [(path, spec) for path, spec, _mirror in _pairs() if settings_theme_is_light(spec)]
    assert light
    for path, spec in light:
        assert spec.backdrop.native_tint() is not None, path.name


def test_a_themes_material_is_the_window_base_not_its_shell() -> None:
    themed = [(path, spec) for path, spec, _mirror in _pairs() if spec.backdrop.mode != "off"]
    assert themed
    for path, spec in themed:
        # Less than half: the material, not window.dialog_glass, decides what the window looks like.
        assert spec.color("window.dialog_glass").a < 128, path.name


@pytest.mark.parametrize("tint", [(248, 241, 246, 40), (20, 30, 60, 90), (120, 200, 40, 200)])
def test_material_recipes_derive_from_the_authored_tint(tint) -> None:
    from ui.settings_theme_spec import NativeBackdropStyle, Rgba
    from ui.theme_semantics import relative_luminance

    authored = Rgba(*tint)
    native = {mode: NativeBackdropStyle(mode=mode, tint=authored).native_tint()
              for mode in ("glass", "off", "acrylic", *NEW_MATERIALS)}
    assert native["glass"] is None and native["off"] is None
    assert native["acrylic"] == authored
    assert relative_luminance(native["frosted"]) >= relative_luminance(authored)
    assert native["frosted"].a >= authored.a
    assert (native["mica"].r, native["mica"].g, native["mica"].b) == (authored.r, authored.g, authored.b)
    assert native["mica"].a >= max(authored.a, native["frosted"].a)
    assert relative_luminance(native["smoked"]) <= relative_luminance(authored)
    spread = lambda c: max(c.r, c.g, c.b) - min(c.r, c.g, c.b)  # noqa: E731
    assert spread(native["smoked"]) <= spread(authored)
    for mode in NEW_MATERIALS:
        with pytest.raises(ValueError):
            NativeBackdropStyle(mode=mode, tint=Rgba(authored.r, authored.g, authored.b, 0))


@pytest.mark.parametrize("mode", ["acrylic", *NEW_MATERIALS])
def test_every_tinted_material_is_native_acrylic_with_its_own_tint(monkeypatch, mode) -> None:
    import core.windows.dwm_blur as dwm
    from ui.settings_theme_spec import NativeBackdropStyle, Rgba

    calls = []
    monkeypatch.setattr(dwm, "enable_acrylic_blur", lambda hwnd, **tint: calls.append((hwnd, tint)) or True)
    monkeypatch.setattr(dwm, "enable_glass_blur", lambda hwnd: pytest.fail("a tinted material went to Glass"))
    backdrop = NativeBackdropStyle(mode=mode, tint=Rgba(30, 60, 90, 70))
    native = backdrop.native_tint()
    assert dwm.apply_backdrop(9, backdrop.mode, native) is True
    assert calls == [(9, {"tint_r": native.r, "tint_g": native.g, "tint_b": native.b, "tint_alpha": native.a})]


def test_a_stored_selection_survives_its_themes_material_tag_change(tmp_path) -> None:
    import shutil

    from ui.settings_theme_catalog import build_settings_theme_catalog, resolve_theme_selection
    from ui.settings_theme_spec import strip_material_tag

    source = next(path for path in sorted(THEMES.glob("*.srtheme")) if strip_material_tag(path.stem) != path.stem)
    base = strip_material_tag(source.stem)
    shutil.copy(source, tmp_path / source.name)
    catalog = build_settings_theme_catalog(tmp_path)
    for old_tag in ("[Glass]", "[Acrylic]", "[Frosted]", "[Mica]", "[Smoked]"):
        requested = f"file:{base} {old_tag}.srtheme"
        resolution = resolve_theme_selection(catalog, requested)
        assert not resolution.used_fallback, requested
        assert resolution.entry.theme_id == f"file:{source.name}"
    # Untagged, unknown or ambiguous names are not bridged.
    assert resolve_theme_selection(catalog, f"file:{base}.srtheme").used_fallback
    assert resolve_theme_selection(catalog, "file:Nothing Like It [Glass].srtheme").used_fallback
    # Two pack themes under one stem: a stored old tag is ambiguous and falls back.
    tags = ["[Glass]", "[Mica]", "[Smoked]"]
    others = [tag for tag in tags if f"{base} {tag}.srtheme" != source.name]
    shutil.copy(source, tmp_path / f"{base} {others[0]}.srtheme")
    catalog = build_settings_theme_catalog(tmp_path)
    assert resolve_theme_selection(catalog, f"file:{base} [Acrylic].srtheme").used_fallback or (
        source.name == f"{base} [Acrylic].srtheme")


@pytest.mark.parametrize("mode", NEW_MATERIALS)
def test_the_non_windows_underlay_applies_the_materials_own_tint(mode) -> None:
    from dataclasses import replace

    from ui.settings_material_underlay import DARK_MATERIAL_NEUTRAL, material_underlay
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NativeBackdropStyle, Rgba
    from ui.theme_semantics import composite_over

    theme = replace(DEFAULT_DARK_SETTINGS_THEME, backdrop=NativeBackdropStyle(mode=mode, tint=Rgba(40, 90, 160, 60)))
    expected = composite_over(theme.backdrop.native_tint(), DARK_MATERIAL_NEUTRAL)
    underlay = material_underlay(theme)
    assert underlay.a == 255
    assert max(abs(underlay.r - expected.r), abs(underlay.g - expected.g), abs(underlay.b - expected.b)) <= 1
