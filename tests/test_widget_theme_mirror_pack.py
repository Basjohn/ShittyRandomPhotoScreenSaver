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


def test_existing_widget_theme_links_resolve_to_settings_themes() -> None:
    """Pairing is a referential contract, not a frozen authored pack count.

    Standalone theme authoring may legitimately add/remove Settings themes, and
    a slim GODZIP may omit the generated Widget mirrors entirely.
    """
    settings_files = sorted(SETTINGS_THEME_DIR.glob("*.srtheme"))
    widget_files = sorted(WIDGET_THEME_DIR.glob("*.srwtheme"))
    settings_ids = {f"file:{path.name}" for path in settings_files}
    settings_ids.add("builtin:default-dark")
    for widget_path in widget_files:
        payload = _payload(widget_path)
        assert payload["format"] == "srpss.widget-theme"
        assert isinstance(payload["schema_version"], int)
        assert payload["linked_settings_theme_id"] in settings_ids or payload["linked_settings_theme_id"] is None
        assert CORE_WIDGET_ROLES <= set(payload["colors"])


def test_external_widget_themes_link_by_stable_id_not_display_name() -> None:
    # Existing optional Widget-theme files may have arbitrary authored names and IDs.
    for path in WIDGET_THEME_DIR.glob("*.srwtheme"):
        payload = _payload(path)
        assert isinstance(payload["theme_id"], str) and payload["theme_id"]
        link = payload["linked_settings_theme_id"]
        assert link is None or isinstance(link, str) and link.strip()
