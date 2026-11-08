"""Settings material underlay: the non-Windows stand-in for every native material (Glass, Acrylic, Frosted, Mica,
Smoked), in the Settings dialog and the Studio window that wears the same material.

Themes here are test-owned derivations of the code default, never curated files.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from ui.settings_material_underlay import DARK_MATERIAL_NEUTRAL, LIGHT_MATERIAL_NEUTRAL, material_underlay
from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, NativeBackdropStyle, Rgba


def _theme(mode: str, tint: Rgba = Rgba(0, 0, 0, 0), *, light: bool = False):
    colors = dict(DEFAULT_DARK_SETTINGS_THEME.colors)
    if light:
        colors["text.primary"] = Rgba(20, 20, 24, 255)
        colors["panel.group.surface"] = Rgba(236, 238, 240, 220)
    return replace(DEFAULT_DARK_SETTINGS_THEME, backdrop=NativeBackdropStyle(mode=mode, tint=tint), colors=colors)


def test_glass_is_an_untinted_neutral_matching_palette_polarity() -> None:
    assert material_underlay(_theme("glass", Rgba(250, 0, 0, 0))) == DARK_MATERIAL_NEUTRAL
    assert material_underlay(_theme("glass", light=True)) == LIGHT_MATERIAL_NEUTRAL


def test_acrylic_applies_its_authored_tint_at_its_authored_strength() -> None:
    tint = Rgba(200, 40, 120, 128)
    weight = 128 / 255
    expected = tuple(round(base + (over - base) * weight) for base, over in (
        (DARK_MATERIAL_NEUTRAL.r, 200), (DARK_MATERIAL_NEUTRAL.g, 40), (DARK_MATERIAL_NEUTRAL.b, 120)))
    underlay = material_underlay(_theme("acrylic", tint))
    assert (underlay.r, underlay.g, underlay.b, underlay.a) == (*expected, 255)
    # A stronger tint moves further from the neutral, toward the tint.
    stronger = material_underlay(_theme("acrylic", replace(tint, a=230)))
    assert abs(stronger.r - 200) < abs(underlay.r - 200)


class _DialogStub:
    """Just the state the backdrop owner touches; methods are the production ones."""

    from ui.settings_dialog import SettingsDialog as _Dialog

    _apply_native_backdrop_theme = _Dialog._apply_native_backdrop_theme
    _apply_material_underlay = _Dialog._apply_material_underlay

    def __init__(self) -> None:
        self._backdrop_applied = False
        self._native_backdrop_mode = None
        self._material_underlay = None
        self.updates = 0

    def winId(self) -> int:
        return 4242

    def update(self) -> None:
        self.updates += 1


def _forbid_native(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("native DWM backdrop must not be called off Windows")

    for name in ("enable_acrylic_blur", "enable_glass_blur", "disable_blur"):
        monkeypatch.setattr(f"core.windows.dwm_blur.{name}", forbidden)


@pytest.mark.parametrize("mode", ["frosted", "mica", "smoked"])
def test_the_newer_materials_apply_their_derived_native_tint(mode) -> None:
    """Frosted, Mica and Smoked: the same neutral, under the material's own derived tint (never the authored one)."""
    theme = _theme(mode, Rgba(90, 30, 110, 120))
    tint = theme.backdrop.native_tint()
    assert tint is not None and tint != theme.backdrop.tint
    weight = tint.a / 255
    expected = tuple(round(base + (over - base) * weight) for base, over in (
        (DARK_MATERIAL_NEUTRAL.r, tint.r), (DARK_MATERIAL_NEUTRAL.g, tint.g), (DARK_MATERIAL_NEUTRAL.b, tint.b)))
    underlay = material_underlay(theme)
    assert (underlay.r, underlay.g, underlay.b, underlay.a) == (*expected, 255)
    assert underlay != DARK_MATERIAL_NEUTRAL


@pytest.mark.parametrize("mode", ["glass", "acrylic", "frosted", "mica", "smoked"])
def test_non_windows_paints_the_underlay_and_never_touches_dwm(monkeypatch, mode) -> None:
    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", False)
    _forbid_native(monkeypatch)
    dialog = _DialogStub()
    theme = _theme(mode, Rgba(90, 30, 110, 120))

    assert dialog._apply_native_backdrop_theme(theme) is False
    expected = material_underlay(theme)
    assert dialog._material_underlay.getRgb() == (expected.r, expected.g, expected.b, 255)
    assert dialog._backdrop_applied is True and dialog._native_backdrop_mode == mode
    assert dialog.updates == 1

    # Off removes the substitute; no native call either.
    dialog._apply_native_backdrop_theme(_theme("off"))
    assert dialog._material_underlay is None


# ----------------------------------------------------------------- the Studio window (same material, same underlay)
ALL_MATERIALS = ("glass", "acrylic", "frosted", "mica", "smoked")


def _rgba(text: str) -> tuple[int, int, int, int]:
    """A Studio token (``#rrggbb`` or ``#aarrggbb``) as RGBA."""
    digits = text.lstrip("#")
    if len(digits) == 6:
        return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16), 255
    return int(digits[2:4], 16), int(digits[4:6], 16), int(digits[6:8], 16), int(digits[0:2], 16)


def _window_role(theme) -> Rgba:
    try:
        return theme.color("window.dialog_glass")
    except KeyError:
        return Rgba(60, 60, 60, 20)                 # the Studio theme owner's own fallback


@pytest.mark.parametrize("light", [False, True])
@pytest.mark.parametrize("mode", ALL_MATERIALS)
def test_non_windows_studio_window_surface_is_composed_over_the_underlay(monkeypatch, mode, light) -> None:
    from ui.studio.theme import studio_theme

    theme = _theme(mode, Rgba(90, 30, 110, 120), light=light)
    # Control: on Windows the material shows through the window surface.
    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", True)
    assert _rgba(studio_theme(theme)["windowSurface"])[3] < 255

    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", False)
    tokens = studio_theme(theme)
    assert tokens["backdrop"] == mode
    red, green, blue, alpha = _rgba(tokens["windowSurface"])
    assert alpha == 255                              # nothing beneath the window shows through
    underlay, role = material_underlay(theme), _window_role(theme)
    weight = role.a / 255
    expected = [channel * weight + base * (1 - weight)
                for channel, base in zip((role.r, role.g, role.b), (underlay.r, underlay.g, underlay.b))]
    assert all(abs(got - want) <= 1 for got, want in zip((red, green, blue), expected))


def test_non_windows_studio_off_stays_its_opaque_normal_window(monkeypatch) -> None:
    from ui.studio.theme import studio_theme

    theme = _theme("off")
    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", True)
    windows = studio_theme(theme)["windowSurface"]
    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", False)
    assert studio_theme(theme)["windowSurface"] == windows and _rgba(windows)[3] == 255


def test_non_windows_studio_window_never_calls_the_native_backdrop(monkeypatch) -> None:
    from types import SimpleNamespace

    from ui.studio.surface import StudioWindowSurface

    calls: list[str] = []
    monkeypatch.setattr("core.windows.dwm_blur.apply_backdrop",
                        lambda _hwnd, mode, _tint=None: calls.append(mode) or True)

    def surface(mode: str) -> SimpleNamespace:
        return SimpleNamespace(material=mode, backdrop_applied=False, theme=_theme(mode, Rgba(90, 30, 110, 120)),
                               window=SimpleNamespace(winId=lambda: 4242))

    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", False)
    for mode in ALL_MATERIALS:
        assert StudioWindowSurface.apply_backdrop(surface(mode)) is False
    assert calls == []
    # Control: the same surfaces on Windows reach the shared mapping with each material.
    monkeypatch.setattr("core.platform_paths.IS_WINDOWS", True)
    for mode in ALL_MATERIALS:
        assert StudioWindowSurface.apply_backdrop(surface(mode)) is True
    assert calls == list(ALL_MATERIALS)
