from __future__ import annotations

from tools.theme_foundry_model import ThemeDraft
from ui.settings_theme_io import settings_theme_from_json, settings_theme_to_json
from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, Rgba


def test_theme_draft_round_trips_current_schema() -> None:
    draft = ThemeDraft.from_spec(DEFAULT_DARK_SETTINGS_THEME)
    assert draft.to_spec() == DEFAULT_DARK_SETTINGS_THEME


def test_theme_draft_authors_glass_as_schema_v5_backdrop() -> None:
    draft = ThemeDraft.from_spec(DEFAULT_DARK_SETTINGS_THEME)
    draft.name = "Foundry Glass Test"
    draft.backdrop_mode = "glass"
    draft.backdrop_tint = Rgba(24, 24, 24, 0)

    spec = draft.to_spec()
    assert spec.backdrop.mode == "glass"
    assert spec.backdrop.tint == Rgba(24, 24, 24, 0)
    assert settings_theme_from_json(settings_theme_to_json(spec)) == spec


def test_theme_draft_authors_nonzero_acrylic_tint() -> None:
    draft = ThemeDraft.from_spec(DEFAULT_DARK_SETTINGS_THEME)
    draft.backdrop_mode = "acrylic"
    draft.backdrop_tint = Rgba(42, 44, 50, 68)

    spec = draft.to_spec()
    assert spec.backdrop.mode == "acrylic"
    assert spec.backdrop.tint.a == 68
