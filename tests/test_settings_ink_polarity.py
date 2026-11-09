"""Regression: impossible Glass desktop poles must not grey out authored ink.

Tests the actual Settings projection rather than the immutable theme catalogue.
Surface/blur calibration and feasible text corrections remain unchanged.
"""
from pathlib import Path

import pytest

from ui.settings_surface_composition import _correct_ink, project_settings_composition
from ui.settings_theme_io import load_settings_theme_file
from ui.settings_theme_spec import Rgba
from ui.theme_semantics import composite_over, contrast_ratio


@pytest.mark.parametrize("foreground", [
    Rgba(255, 255, 255, 255),
    Rgba(204, 204, 204, 255),
    Rgba(35, 45, 55, 170),
    Rgba(215, 225, 235, 120),
])
def test_competing_desktop_extremes_preserve_authored_polarity(foreground):
    extremes = [(Rgba(0, 0, 0), 4.5), (Rgba(255, 255, 255), 4.5)]
    result = _correct_ink(foreground, extremes)
    assert result == Rgba(foreground.r, foreground.g, foreground.b, 255)


@pytest.mark.parametrize("adjustment", [-0.75, 0.0, 0.65])
def test_default_dark_glass_projection_keeps_active_labels_readable(adjustment):
    path = Path(__file__).resolve().parents[1] / "themes" / "Default Dark [Single] [Glass].srtheme"
    theme = load_settings_theme_file(path)
    assert theme.backdrop.mode == "glass"
    projected, native = project_settings_composition(theme, adjustment)
    assert native is None

    # These tokens feed page and group headings, inactive sidebar labels, and
    # small explanatory copy. The Nov 9 fallback made these grey on Glass.
    for token in ("text.primary", "text.secondary", "navigation.tab.text"):
        authored = theme.colors[token]
        derived = projected[token]
        # A denser/clearer override may legitimately brighten readable ink,
        # but must not invert this dark theme's light foreground to dark grey.
        assert min(derived.r, derived.g, derived.b) >= min(authored.r, authored.g, authored.b) - 12, (adjustment, token)
        assert derived.a == 255, (adjustment, token)
        if adjustment == 0.0:
            assert derived == authored, token

    # The fix never changes theme-authored data or controls' structural backdrop.
    assert theme.colors["text.primary"] == Rgba(255, 255, 255, 255)
    assert projected["window.dialog_glass"].r == theme.colors["window.dialog_glass"].r


def test_feasible_alpha_and_dark_ink_corrections_still_work():
    dim_background = Rgba(23, 33, 43)
    translucent_ink = Rgba(196, 212, 228, 105)
    corrected = _correct_ink(translucent_ink, [(dim_background, 4.5)])
    assert corrected.as_tuple()[:3] == translucent_ink.as_tuple()[:3]
    assert translucent_ink.a < corrected.a <= 255
    assert contrast_ratio(composite_over(corrected, dim_background), dim_background) >= 4.5

    pale_background = Rgba(235, 237, 239)
    midtone_ink = Rgba(149, 151, 153)
    corrected = _correct_ink(midtone_ink, [(pale_background, 4.5)])
    assert all(a < b for a, b in zip(corrected.as_tuple()[:3], midtone_ink.as_tuple()[:3]))
    assert contrast_ratio(corrected, pale_background) >= 4.5
