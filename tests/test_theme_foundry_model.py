from __future__ import annotations

from tools.theme_foundry_model import (
    ThemeDraft,
    matching_color_tokens,
    replace_matching_color_roles,
)
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


def test_matching_color_tokens_use_exact_rgba() -> None:
    colors = {
        "a": Rgba(10, 20, 30, 40),
        "b": Rgba(10, 20, 30, 40),
        "c": Rgba(10, 20, 30, 41),
    }
    assert matching_color_tokens(colors, Rgba(10, 20, 30, 40)) == ("a", "b")


def test_replace_matching_color_roles_changes_only_exact_matches() -> None:
    old = Rgba(10, 20, 30, 40)
    new = Rgba(80, 90, 100, 110)
    colors = {
        "a": old,
        "b": old,
        "c": Rgba(10, 20, 30, 41),
    }
    changed = replace_matching_color_roles(colors, old, new)
    assert changed == ("a", "b")
    assert colors == {
        "a": new,
        "b": new,
        "c": Rgba(10, 20, 30, 41),
    }
