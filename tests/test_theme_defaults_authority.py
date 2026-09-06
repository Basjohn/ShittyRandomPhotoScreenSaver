from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _canonical_defaults() -> dict:
    parsed = ast.parse(_text("core/settings/default_settings.py"))
    for node in parsed.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "DEFAULT_SETTINGS"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            assert isinstance(value, dict)
            return value
    raise AssertionError("DEFAULT_SETTINGS literal not found")


def test_settings_theme_selection_is_canonical_and_snapshotted() -> None:
    defaults = _canonical_defaults()
    ui_defaults = defaults.get("ui")
    assert isinstance(ui_defaults, dict)

    theme_id = ui_defaults.get("settings_theme_selection")
    assert isinstance(theme_id, str)
    assert theme_id.strip()

    snapshot = json.loads(_text("core/settings/defaults_snapshot.json"))
    assert snapshot["ui"]["settings_theme_selection"] == theme_id


def test_settings_theme_missing_value_reads_canonical_default() -> None:
    source = _text("ui/settings_theme_catalog.py")
    assert "def _canonical_default_theme_id()" in source
    assert 'ui_defaults.get("settings_theme_selection")' in source
    assert "_canonical_default_theme_id()," in source


def test_widget_theme_missing_values_read_canonical_defaults() -> None:
    defaults = _canonical_defaults()
    widget_defaults = defaults.get("widget_theme")
    assert isinstance(widget_defaults, dict)
    assert isinstance(widget_defaults.get("selected_id"), str)
    assert isinstance(widget_defaults.get("keep_synced"), bool)
    assert widget_defaults.get("custom") is None or isinstance(
        widget_defaults.get("custom"), dict
    )

    source = _text("ui/widget_theme_selection.py")
    assert "def _canonical_widget_theme_defaults()" in source
    assert 'DEFAULT_SETTINGS.get("widget_theme")' in source
    assert 'values.get("selected_id", default_selected)' in source
    assert 'values.get("keep_synced"), default_keep_synced' in source
    assert 'values.get("custom", default_custom)' in source
