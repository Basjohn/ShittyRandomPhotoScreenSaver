"""Permanent contract for the curated Settings -> Widget theme mirror pack.

This file is deliberately stdlib-only so pack/link integrity can be checked on
machines without Qt. Runtime schema loading is covered by the Widget Theme IO /
catalogue tests in a normal PySide6 user environment.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_THEME_DIR = ROOT / "themes"
WIDGET_THEME_DIR = SETTINGS_THEME_DIR / "widgets"
CANONICAL_SETTINGS_DEFAULT = "Default Dark.srtheme"
CANONICAL_WIDGET_DEFAULT = "Default Dark.srwtheme"
CORE_WIDGET_ROLES = {
    "card.background",
    "card.border",
    "card.text",
    "context.menu.surface",
    "context.menu.border",
    "context.menu.text",
    "context.menu.selected_surface",
    "context.menu.disabled_text",
    "context.menu.separator",
    "context.submenu.surface",
    "context.submenu.border",
    "context.submenu.text",
    "context.submenu.selected_surface",
    "context.submenu.checked_text",
    "context.submenu.checked_surface",
}
SHARED_SEMANTIC_ROLES = {
    "header.fill",
    "header.border",
    "header.text",
    "widget.panel",
    "widget.panel.alt",
    "widget.outline",
    "widget.separator",
    "widget.icon",
    "widget.muted",
    "widget.accent",
    "widget.gradient.start",
    "widget.gradient.middle",
    "widget.gradient.end",
}
MATURE_FAMILY_ROLES = {
    "abandonment_issues.accent",
    "media.transport.surface",
    "media.transport.border",
    "media.transport.separator",
    "media.transport.icon",
    "media.mute.surface",
    "media.mute.border",
    "media.mute.inner_border",
    "media.mute.icon",
    "media.mute.muted_icon",
    "media.volume.track",
    "media.volume.fill",
    "media.volume.outline",
    "media.progress.track",
    "media.progress.fill",
    "media.progress.glow",
    "media.progress.shadow",
}


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))



def _widget_filename_for_settings(path: Path) -> str:
    if path.name == CANONICAL_SETTINGS_DEFAULT:
        return CANONICAL_WIDGET_DEFAULT
    stem = path.stem
    stem = stem.removesuffix(" [Glass]").removesuffix(" [Acrylic]")
    return f"{stem}.srwtheme"


def test_every_settings_theme_has_one_stable_widget_mirror() -> None:
    settings_files = sorted(SETTINGS_THEME_DIR.glob("*.srtheme"), key=lambda p: p.name.casefold())
    widget_files = sorted(WIDGET_THEME_DIR.glob("*.srwtheme"), key=lambda p: p.name.casefold())

    assert settings_files, "Settings theme pack unexpectedly empty"
    assert len(widget_files) == len(settings_files)
    assert (WIDGET_THEME_DIR / CANONICAL_WIDGET_DEFAULT).is_file()

    expected_widget_names = {_widget_filename_for_settings(path) for path in settings_files}
    assert {path.name for path in widget_files} == expected_widget_names

    for settings_path in settings_files:
        widget_path = WIDGET_THEME_DIR / _widget_filename_for_settings(settings_path)
        payload = _payload(widget_path)
        assert payload["format"] == "srpss.widget-theme"
        assert payload["schema_version"] == 3
        expected_link = (
            "builtin:default-dark"
            if settings_path.name == CANONICAL_SETTINGS_DEFAULT
            else f"file:{settings_path.name}"
        )
        assert payload["linked_settings_theme_id"] == expected_link
        assert not payload["name"].endswith(" [Glass]")
        assert not payload["name"].endswith(" [Acrylic]")
        assert "default_card_material_mode" not in payload
        assert CORE_WIDGET_ROLES <= set(payload["colors"])
        if settings_path.name != CANONICAL_SETTINGS_DEFAULT:
            assert SHARED_SEMANTIC_ROLES <= set(payload["colors"])
            assert MATURE_FAMILY_ROLES <= set(payload["colors"])


def test_external_mirrors_use_explicit_non_name_matching_identity() -> None:
    for path in WIDGET_THEME_DIR.glob("*.srwtheme"):
        if path.name == CANONICAL_WIDGET_DEFAULT:
            continue
        payload = _payload(path)
        settings_id = payload["linked_settings_theme_id"]
        assert isinstance(settings_id, str) and settings_id.startswith("file:")
        assert payload["theme_id"] == f"mirror:{settings_id}"
        # Widget filenames deliberately omit Settings-window material tags, so
        # runtime pairing can never depend on filename/display-name matching.
        assert not path.stem.endswith(" [Glass]")
        assert not path.stem.endswith(" [Acrylic]")
