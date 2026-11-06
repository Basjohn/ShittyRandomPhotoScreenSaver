"""Widget Themes carry an optional card surface material (Card_Surface_Materials.md section 4).

What these bars protect:
- a ``.srwtheme`` may name one of the materials; it round-trips through the spec, the
  strict loader/writer and the Foundry draft, and a theme that names none writes no key
  (so every older file round-trips unchanged);
- Style Overrides' baseline defaults to ``theme``: the active theme's material, Normal when
  it names none; an explicit baseline, and a per-widget value, beat it;
- the Style Overrides combo offers Theme first and saves it;
- every shipped theme parses with a valid material or none (structure only: themes are
  authored content, their values are not pinned).
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _theme(material=None):
    from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME

    return replace(DEFAULT_DARK_WIDGET_THEME, theme_id="widget:test", name="Test", surface_material=material)


def test_a_theme_material_round_trips_and_a_theme_without_one_writes_no_key() -> None:
    from ui.widget_theme_io import widget_theme_from_json, widget_theme_to_json, widget_theme_to_payload

    glass = _theme("Glass")
    assert glass.surface_material == "glass"
    payload = widget_theme_to_payload(glass)
    assert payload["surface_material"] == "glass"
    assert widget_theme_from_json(widget_theme_to_json(glass)) == glass
    plain = _theme()
    assert "surface_material" not in widget_theme_to_payload(plain)
    assert widget_theme_from_json(widget_theme_to_json(plain)).surface_material is None


@pytest.mark.parametrize("value", ["theme", "inherit", "chrome", 3])
def test_a_theme_file_rejects_anything_but_a_real_material(value) -> None:
    from ui.widget_theme_io import WidgetThemeFileError, widget_theme_from_payload, widget_theme_to_payload

    payload = widget_theme_to_payload(_theme())
    payload["surface_material"] = value
    with pytest.raises(WidgetThemeFileError):
        widget_theme_from_payload(payload)
    with pytest.raises(ValueError):
        _theme(value if isinstance(value, str) else "x")


def test_the_foundry_draft_carries_the_material() -> None:
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    from widget_theme_foundry_model import WidgetThemeDraft

    draft = WidgetThemeDraft.from_spec(_theme("mica"))
    assert draft.surface_material == "mica"
    draft.surface_material = "smoked"
    assert draft.to_spec().surface_material == "smoked"


def test_the_baseline_follows_the_active_theme_and_explicit_values_beat_it() -> None:
    from rendering.quick.widgets.surface_material import (
        resolve_global_surface_material, resolve_surface_material,
    )
    from ui.widget_theme_active import reset_active_widget_theme, set_active_widget_theme

    set_active_widget_theme(_theme("frosted"))
    try:
        assert resolve_global_surface_material({"global": {"surface_material": "theme"}}) == "frosted"
        assert resolve_global_surface_material({}) == "frosted"
        assert resolve_global_surface_material({"global": {"surface_material": "normal"}}) == "normal"
        assert resolve_global_surface_material({"global": {"surface_material": "smoked"}}) == "smoked"
        assert resolve_global_surface_material({"global": {"surface_material": "bogus"}}) == "normal"
        widgets = {"global": {"surface_material": "theme"}, "weather": {"surface_material": "inherit"},
                   "reddit": {"surface_material": "glass"}}
        assert resolve_surface_material(widgets, "weather") == "frosted"
        assert resolve_surface_material(widgets, "reddit") == "glass"
        set_active_widget_theme(_theme(None))
        assert resolve_surface_material(widgets, "weather") == "normal"
    finally:
        reset_active_widget_theme()


def test_style_overrides_offers_theme_first_and_saves_it(qt_app, settings_manager) -> None:
    from ui.tabs.widgets_tab import WidgetsTab

    tab = WidgetsTab(settings_manager, lazy_sections=True, initial_view_state={"subtab_id": "defaults"})
    try:
        combo = getattr(tab, "surface_material_combo", None)
        if combo is None:
            pytest.skip("the General page was not built by this view state")
        assert combo.itemData(0) == "theme"
        assert combo.currentData() == "theme"          # the canonical default
        combo.setCurrentIndex(combo.findData("glass"))
        tab.flush_pending_changes()
        assert settings_manager.get("widgets")["global"]["surface_material"] == "glass"
        combo.setCurrentIndex(combo.findData("theme"))
        tab.flush_pending_changes()
        assert settings_manager.get("widgets")["global"]["surface_material"] == "theme"
    finally:
        tab.deleteLater()
        qt_app.processEvents()


def test_every_shipped_theme_parses_with_a_valid_material_or_none() -> None:
    from rendering.quick.widgets.surface_material import SURFACE_MATERIALS
    from ui.widget_theme_io import load_widget_theme_file

    paths = sorted((ROOT / "themes" / "widgets").glob("*.srwtheme"))
    assert paths
    for path in paths:
        theme = load_widget_theme_file(path)
        assert theme.surface_material in (None, *SURFACE_MATERIALS), path.name
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert ("surface_material" in raw) == (theme.surface_material is not None), path.name
