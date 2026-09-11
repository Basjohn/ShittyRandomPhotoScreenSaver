from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from core.about_art_theme import recolor_liquid_rgba

ROOT = Path(__file__).resolve().parents[1]


def _asset(name: str) -> np.ndarray:
    return np.asarray(Image.open(ROOT / "images" / name).convert("RGBA"), dtype=np.uint8)


def _mask(name: str) -> np.ndarray:
    return np.asarray(Image.open(ROOT / "images" / name).convert("L"), dtype=np.uint8)


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


def test_every_shipped_settings_theme_seeds_about_liquid_from_primary_accent() -> None:
    theme_paths = sorted((ROOT / "themes").glob("*.srtheme"))
    assert theme_paths
    for path in theme_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 6, path.name
        color = payload["colors"]["about.art.liquid"]
        primary = payload["colors"]["chrome.outer_border"]
        assert color[:3] == primary[:3], path.name
        assert color[3] == 255, path.name


def test_nocturne_about_liquid_uses_its_pink_red_primary_accent() -> None:
    payload = json.loads(
        (ROOT / "themes" / "Nocturne Split [Three-Tone] [Glass].srtheme").read_text(encoding="utf-8")
    )
    assert payload["colors"]["chrome.outer_border"] == [221, 151, 144, 255]
    assert payload["colors"]["about.art.liquid"] == [221, 151, 144, 255]


def test_settings_shell_minimum_is_1280_by_760() -> None:
    source = (ROOT / "ui" / "settings_dialog.py").read_text(encoding="utf-8")
    assert "self.setMinimumSize(1280, 760)" in source
    assert "h_saved = int(geometry.get('height', 760))" in source


def test_about_tab_consumes_explicit_masks_and_theme_semantic() -> None:
    source = (ROOT / "ui" / "settings_about_tab.py").read_text(encoding="utf-8")
    assert 'color("about.art.liquid")' in source
    assert '"Logo_LiquidMask.png"' in source
    assert '"Shoogle300W_LiquidMask.png"' in source
