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


def _payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_settings_theme_has_one_stable_widget_mirror() -> None:
    settings_files = sorted(SETTINGS_THEME_DIR.glob("*.srtheme"), key=lambda p: p.name.casefold())
    widget_files = sorted(WIDGET_THEME_DIR.glob("*.srwtheme"), key=lambda p: p.name.casefold())

    assert settings_files, "Settings theme pack unexpectedly empty"
    assert len(widget_files) == len(settings_files)
    assert (WIDGET_THEME_DIR / CANONICAL_WIDGET_DEFAULT).is_file()

    expected_widget_names = {
        (CANONICAL_WIDGET_DEFAULT if path.name == CANONICAL_SETTINGS_DEFAULT else f"{path.stem}.srwtheme")
        for path in settings_files
    }
    assert {path.name for path in widget_files} == expected_widget_names

    for settings_path in settings_files:
        widget_path = WIDGET_THEME_DIR / (
            CANONICAL_WIDGET_DEFAULT
            if settings_path.name == CANONICAL_SETTINGS_DEFAULT
            else f"{settings_path.stem}.srwtheme"
        )
        payload = _payload(widget_path)
        assert payload["format"] == "srpss.widget-theme"
        assert payload["schema_version"] == 2
        expected_link = (
            "builtin:default-dark"
            if settings_path.name == CANONICAL_SETTINGS_DEFAULT
            else f"file:{settings_path.name}"
        )
        assert payload["linked_settings_theme_id"] == expected_link
        assert payload["default_card_material_mode"] in {"normal", "glass", "acrylic"}
        assert CORE_WIDGET_ROLES <= set(payload["colors"])
        if settings_path.name != CANONICAL_SETTINGS_DEFAULT:
            # External mirrors intentionally materialize the mature shared semantic
            # vocabulary. The compiled Default Dark remains sparse so its optional
            # roles inherit the exact accepted family-local pixels.
            assert SHARED_SEMANTIC_ROLES <= set(payload["colors"])


def test_external_mirrors_use_explicit_non_name_matching_identity() -> None:
    for path in WIDGET_THEME_DIR.glob("*.srwtheme"):
        if path.name == CANONICAL_WIDGET_DEFAULT:
            continue
        payload = _payload(path)
        settings_id = f"file:{path.stem}.srtheme"
        assert payload["linked_settings_theme_id"] == settings_id
        assert payload["theme_id"] == f"mirror:{settings_id}"
