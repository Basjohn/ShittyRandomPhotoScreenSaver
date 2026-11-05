"""Settings material underlay: the non-Windows stand-in for native Glass/Acrylic.

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


@pytest.mark.parametrize("mode", ["glass", "acrylic"])
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
