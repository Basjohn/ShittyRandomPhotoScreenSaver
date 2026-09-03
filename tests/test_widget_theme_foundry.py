from __future__ import annotations

from pathlib import Path

import pytest

from tools.widget_theme_foundry_model import (
    WidgetThemeDraft,
    all_widget_theme_roles,
    default_seed_color,
    exact_color_matches,
    most_used_colors,
    replace_exact_color_matches,
    role_group,
    theme_id_for_save_as,
)
from ui.settings_theme_spec import Rgba
from ui.widget_theme_io import load_widget_theme_file, save_widget_theme_file
from ui.widget_theme_spec import (
    DEFAULT_DARK_WIDGET_THEME,
    WIDGET_THEME_CORE_COLOR_ROLES,
)
from ui.widget_visual_roles import (
    WIDGET_THEME_OPTIONAL_COLOR_ROLES,
    WIDGET_VISUAL_ROLE_PARENTS,
)


def test_role_universe_is_derived_from_production_schema() -> None:
    assert set(all_widget_theme_roles()) == set(WIDGET_THEME_CORE_COLOR_ROLES) | set(WIDGET_THEME_OPTIONAL_COLOR_ROLES)
    assert role_group("media.volume.fill") == "Media"
    assert role_group("steam.artwork.border") == "Steam"
    assert role_group("card.background") == "Shared Card"


def test_sparse_optional_role_inherits_without_becoming_serialized() -> None:
    draft = WidgetThemeDraft.from_spec(DEFAULT_DARK_WIDGET_THEME)
    assert "media.volume.fill" not in draft.colors
    resolved = draft.resolve_role("media.volume.fill")
    # Default Dark does not author widget.accent, so this correctly terminates at
    # the family-local semantic seam rather than inventing a serialized value.
    assert resolved.kind == "local"
    assert "media.volume.fill" not in draft.to_spec().colors

    explicit = Rgba(20, 40, 60, 170)
    draft.set_role("media.volume.fill", explicit)
    resolved = draft.resolve_role("media.volume.fill")
    assert resolved.kind == "explicit"
    assert resolved.color == explicit
    assert draft.remove_optional_override("media.volume.fill") is True
    assert "media.volume.fill" not in draft.colors


def test_core_roles_cannot_be_removed() -> None:
    draft = WidgetThemeDraft.from_spec(DEFAULT_DARK_WIDGET_THEME)
    with pytest.raises(ValueError, match="Core Widget Theme role"):
        draft.remove_optional_override("card.background")


def test_exact_match_tools_are_rgba_exact_and_deterministic() -> None:
    a = Rgba(1, 2, 3, 4)
    b = Rgba(9, 8, 7, 6)
    colors = {"a": a, "b": a, "c": b}
    assert exact_color_matches(colors, a) == ("a", "b")
    assert most_used_colors(colors, limit=1) == ((a, ("a", "b")),)
    changed = replace_exact_color_matches(colors, a, b)
    assert changed == ("a", "b")
    assert colors == {"a": b, "b": b, "c": b}


def test_strict_widget_theme_save_reload_survives_foundry_draft(tmp_path: Path) -> None:
    draft = WidgetThemeDraft.from_spec(DEFAULT_DARK_WIDGET_THEME)
    draft.theme_id = "widget:test-foundry"
    draft.name = "Foundry Test"
    draft.linked_settings_theme_id = None
    draft.set_role("media.volume.fill", Rgba(11, 22, 33, 144))
    path = tmp_path / "Foundry Test.srwtheme"
    save_widget_theme_file(draft.to_spec(), path)
    assert load_widget_theme_file(path) == draft.to_spec()


def test_save_as_identity_is_path_independent_and_link_safe_in_ui_source() -> None:
    assert theme_id_for_save_as(Path(r"C:\\whatever\\Blue.srwtheme")).endswith("Blue.srwtheme")
    source = (Path(__file__).parents[1] / "tools" / "widget_theme_foundry.py").read_text(encoding="utf-8")
    assert '"SRPSSTheme.ico"' in source
    assert "linked_settings_theme_id=None" in source
    assert "save_widget_theme_file" in source
    assert "load_widget_theme_file" in source
    assert "WIDGET_THEME_CORE_COLOR_ROLES" in source
    assert "all_widget_theme_roles" in source
    assert "WIDGET_THEME_OPTIONAL_COLOR_ROLES =" not in source


def test_local_inheritance_seed_is_editor_only() -> None:
    draft = WidgetThemeDraft.from_spec(DEFAULT_DARK_WIDGET_THEME)
    before = dict(draft.colors)
    color = default_seed_color("media.volume.fill", draft)
    assert isinstance(color, Rgba)
    assert draft.colors == before
