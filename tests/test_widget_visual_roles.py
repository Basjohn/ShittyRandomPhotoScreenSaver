from __future__ import annotations

from ui.settings_theme_spec import Rgba
from ui.widget_theme_io import widget_theme_from_payload, widget_theme_to_payload
from ui.widget_theme_spec import (
    DEFAULT_DARK_WIDGET_THEME,
    WIDGET_THEME_CORE_COLOR_ROLES,
    WIDGET_THEME_SCHEMA_VERSION,
    WidgetThemeSpec,
)
from ui.widget_theme_runtime import WidgetThemeState, begin_theme_owned_edit, with_color
from ui.widget_visual_roles import resolve_widget_visual_color


def _theme(**colors: Rgba) -> WidgetThemeSpec:
    merged = dict(DEFAULT_DARK_WIDGET_THEME.colors)
    merged.update(colors)
    return WidgetThemeSpec(
        theme_id="test",
        name="Test",
        colors=merged,
    )


def test_media_role_inherits_local_surface_when_theme_does_not_specify_it() -> None:
    local = Rgba(35, 35, 35, 176)
    resolved = resolve_widget_visual_color(
        DEFAULT_DARK_WIDGET_THEME,
        "media.transport.surface",
        local_roles={"local.surface": local},
        fallback=Rgba(1, 2, 3, 4),
    )
    assert resolved.color == local
    assert resolved.source_kind == "local"


def test_theme_specific_role_wins_without_touching_family_settings() -> None:
    accent = Rgba(10, 20, 30, 140)
    theme = _theme(**{"media.transport.surface": accent})
    resolved = resolve_widget_visual_color(
        theme,
        "media.transport.surface",
        local_roles={"local.surface": Rgba(35, 35, 35, 176)},
        fallback=Rgba(1, 2, 3, 4),
    )
    assert resolved.color == accent
    assert resolved.source_role == "media.transport.surface"


def test_generic_parent_role_can_style_specialized_media_role() -> None:
    panel = Rgba(44, 55, 66, 177)
    theme = _theme(**{"widget.panel": panel})
    resolved = resolve_widget_visual_color(
        theme,
        "media.transport.surface",
        local_roles={"local.surface": Rgba(35, 35, 35, 176)},
        fallback=Rgba(1, 2, 3, 4),
    )
    assert resolved.color == panel
    assert resolved.source_role == "widget.panel"


def test_explicit_family_override_beats_theme() -> None:
    theme = _theme(**{"header.text": Rgba(1, 2, 3, 255)})
    explicit = Rgba(200, 201, 202, 203)
    resolved = resolve_widget_visual_color(
        theme,
        "gmail.header.text",
        local_roles={"local.header.text": Rgba(255, 255, 255, 230)},
        fallback=Rgba(255, 255, 255, 230),
        explicit=explicit,
    )
    assert resolved.color == explicit
    assert resolved.source_kind == "explicit"


def test_schema_v2_allows_sparse_known_optional_roles() -> None:
    payload = widget_theme_to_payload(DEFAULT_DARK_WIDGET_THEME)
    payload["theme_id"] = "sparse"
    payload["name"] = "Sparse"
    payload["colors"]["widget.separator"] = [90, 91, 92, 93]
    loaded = widget_theme_from_payload(payload)
    assert loaded.schema_version == WIDGET_THEME_SCHEMA_VERSION
    assert loaded.colors["widget.separator"] == Rgba(90, 91, 92, 93)


def test_schema_v1_core_theme_migrates_to_current_schema() -> None:
    payload = widget_theme_to_payload(DEFAULT_DARK_WIDGET_THEME)
    payload["schema_version"] = 1
    payload["colors"] = {
        role: payload["colors"][role]
        for role in WIDGET_THEME_CORE_COLOR_ROLES
    }
    loaded = widget_theme_from_payload(payload)
    assert loaded.schema_version == WIDGET_THEME_SCHEMA_VERSION
    assert set(loaded.colors) == set(WIDGET_THEME_CORE_COLOR_ROLES)


def test_default_dark_context_roles_preserve_accepted_retained_pixels() -> None:
    colors = DEFAULT_DARK_WIDGET_THEME.colors
    assert colors["context.menu.surface"] == Rgba(27, 29, 36, 242)
    assert colors["context.menu.border"] == Rgba(216, 243, 255, 255)
    assert colors["context.menu.text"] == Rgba(246, 248, 255, 255)
    assert colors["context.menu.selected_surface"] == Rgba(119, 185, 232, 79)
    assert colors["context.menu.separator"] == Rgba(89, 119, 138, 255)
    assert colors["context.menu.indicator.border"] == Rgba(185, 234, 255, 255)
    assert colors["context.menu.indicator.fill"] == Rgba(130, 205, 255, 255)
    assert colors["context.submenu.checked_surface"] == Rgba(78, 113, 139, 51)


def test_custom_edit_can_add_known_optional_role() -> None:
    edited = with_color(DEFAULT_DARK_WIDGET_THEME, "media.mute.icon", Rgba(3, 4, 5, 6))
    assert edited.colors["media.mute.icon"] == Rgba(3, 4, 5, 6)


def test_custom_snapshot_can_freeze_current_sparse_optional_role() -> None:
    current = Rgba(35, 35, 35, 176)
    custom, state = begin_theme_owned_edit(
        WidgetThemeState(),
        DEFAULT_DARK_WIDGET_THEME,
        "media.transport.border",
        Rgba(9, 8, 7, 6),
        resolved_optional_colors={"media.transport.surface": current},
    )
    assert custom.colors["media.transport.surface"] == current
    assert custom.colors["media.transport.border"] == Rgba(9, 8, 7, 6)
    assert state.selected_id == "custom"
    assert state.keep_synced is False


def test_custom_snapshot_freezes_resolved_optional_context_detail_not_default_dark() -> None:
    inherited_indicator = Rgba(8, 18, 28, 238)
    sparse_colors = {
        role: DEFAULT_DARK_WIDGET_THEME.colors[role]
        for role in WIDGET_THEME_CORE_COLOR_ROLES
    }
    sparse_colors["context.menu.border"] = inherited_indicator
    sparse = WidgetThemeSpec(
        theme_id="sparse_context_custom",
        name="Sparse Context Custom",
        colors=sparse_colors,
    )
    custom, _state = begin_theme_owned_edit(
        WidgetThemeState(),
        sparse,
        "media.transport.border",
        Rgba(9, 8, 7, 6),
        resolved_optional_colors={
            "context.menu.indicator.border": inherited_indicator,
        },
    )
    assert custom.colors["context.menu.indicator.border"] == inherited_indicator
    assert custom.colors["context.menu.indicator.border"] != (
        DEFAULT_DARK_WIDGET_THEME.colors["context.menu.indicator.border"]
    )


def test_reddit2_roles_inherit_shared_reddit_header_parent() -> None:
    parent = Rgba(12, 13, 14, 200)
    theme = _theme(**{"reddit.header.fill": parent})
    resolved = resolve_widget_visual_color(
        theme,
        "reddit2.header.fill",
        local_roles={"local.header.fill": Rgba(0, 0, 0, 0)},
        fallback=Rgba(1, 2, 3, 4),
    )
    assert resolved.color == parent
    assert resolved.source_role == "reddit.header.fill"


def test_sparse_theme_context_indicator_inherits_menu_border() -> None:
    colors = {
        role: DEFAULT_DARK_WIDGET_THEME.colors[role]
        for role in WIDGET_THEME_CORE_COLOR_ROLES
    }
    colors["context.menu.border"] = Rgba(8, 18, 28, 238)
    theme = WidgetThemeSpec(theme_id="sparse_context", name="Sparse Context", colors=colors)
    resolved = resolve_widget_visual_color(
        theme,
        "context.menu.indicator.border",
        fallback=Rgba(185, 234, 255, 255),
    )
    assert resolved.color == Rgba(8, 18, 28, 238)
    assert resolved.source_role == "context.menu.border"


def test_local_roles_are_not_serialized_theme_tokens() -> None:
    from ui.widget_visual_roles import WIDGET_THEME_OPTIONAL_COLOR_ROLES

    assert all(not role.startswith("local.") for role in WIDGET_THEME_OPTIONAL_COLOR_ROLES)


def test_specialized_volume_fill_keeps_its_local_default_instead_of_progress_accent() -> None:
    volume_fill = Rgba(79, 79, 79, 150)
    progress_fill = Rgba(255, 255, 255, 230)
    resolved = resolve_widget_visual_color(
        DEFAULT_DARK_WIDGET_THEME,
        "media.volume.fill",
        local_roles={"local.accent": volume_fill},
        fallback=progress_fill,
    )
    assert resolved.color == volume_fill
    assert resolved.source_kind == "local"


def test_generic_widget_accent_theme_can_still_override_volume_fill() -> None:
    themed_accent = Rgba(25, 125, 225, 180)
    theme = _theme(**{"widget.accent": themed_accent})
    resolved = resolve_widget_visual_color(
        theme,
        "media.volume.fill",
        local_roles={"local.accent": Rgba(79, 79, 79, 150)},
        fallback=Rgba(79, 79, 79, 150),
    )
    assert resolved.color == themed_accent
    assert resolved.source_role == "widget.accent"
