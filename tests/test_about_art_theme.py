from __future__ import annotations

import json
from pathlib import Path
from io import BytesIO

import numpy as np
from PIL import Image

from core.about_art_theme import recolor_liquid_rgba
from ui.resources.assets import resource_bytes

ROOT = Path(__file__).resolve().parents[1]


def _asset(name: str) -> np.ndarray:
    return np.asarray(
        Image.open(BytesIO(resource_bytes(f"branding/about/{name}"))).convert("RGBA"),
        dtype=np.uint8,
    )


def _mask(name: str) -> np.ndarray:
    return np.asarray(
        Image.open(BytesIO(resource_bytes(f"branding/about/{name}"))).convert("L"),
        dtype=np.uint8,
    )


def test_about_liquid_recolour_preserves_unmasked_art() -> None:
    source = _asset("Logo.png")
    mask = _mask("Logo_LiquidMask.png")
    themed = recolor_liquid_rgba(source, mask, (221, 151, 144))
    assert np.array_equal(themed[..., 3], source[..., 3])
    assert np.array_equal(themed[mask == 0], source[mask == 0])
    assert np.count_nonzero(np.any(themed[..., :3] != source[..., :3], axis=2)) > 100_000

def test_about_liquid_mask_preserves_unmasked_artwork_and_source_alpha() -> None:
    source = _asset("Shoogle300W.png")
    mask = _mask("Shoogle300W_LiquidMask.png")
    themed = recolor_liquid_rgba(source, mask, (97, 198, 255))

    assert np.array_equal(themed[..., 3], source[..., 3])
    assert np.array_equal(themed[mask == 0], source[mask == 0])
    assert np.count_nonzero(np.any(themed[..., :3] != source[..., :3], axis=2)) > 100_000


def test_shipped_about_masks_match_source_dimensions() -> None:
    for source_name, mask_name in (
        ("Logo.png", "Logo_LiquidMask.png"),
        ("Shoogle300W.png", "Shoogle300W_LiquidMask.png"),
    ):
        source = _asset(source_name)
        mask = _mask(mask_name)
        assert mask.shape == source.shape[:2]
        # The mask is substantial but cannot cover the monochrome foreground.
        coverage = np.count_nonzero(mask) / mask.size
        assert 0.35 < coverage < 0.85


def test_shipped_settings_themes_have_valid_about_art_colour_roles() -> None:
    """An author's accent/branding colours are not golden test expectations."""
    from ui.settings_theme_io import load_settings_theme_file
    from ui.settings_theme_spec import Rgba

    for path in sorted((ROOT / "themes").glob("*.srtheme")):
        theme = load_settings_theme_file(path)
        assert isinstance(theme.color("about.art.liquid"), Rgba)
        assert isinstance(theme.color("chrome.outer_border"), Rgba)


def test_settings_shell_minimum_is_1280_by_760() -> None:
    source = (ROOT / "ui" / "settings_dialog.py").read_text(encoding="utf-8")
    assert "self.setMinimumSize(1280, 760)" in source
    assert "h_saved = int(geometry.get('height', 760))" in source


def test_about_tab_consumes_explicit_masks_and_theme_semantic() -> None:
    source = (ROOT / "ui" / "settings_about_tab.py").read_text(encoding="utf-8")
    assert 'color("about.art.liquid")' in source
    assert '"branding/about/Logo_LiquidMask.png"' in source
    assert '"branding/about/Shoogle300W_LiquidMask.png"' in source
