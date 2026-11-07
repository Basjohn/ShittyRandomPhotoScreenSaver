"""AC-17: a theme pair's card material has one owner, so a "[Glass]" theme gives Glass cards.

Operator (7 Nov 2026): "[Glass]" and "[Acrylic]" themes give Glass and Acrylic cards. The
Settings theme's ``backdrop.mode`` is projected once, by ``widget_counterpart_for_settings_theme``,
into its linked Widget mirror's ``surface_material``; the runtime reads only the mirror
(Docs/Architecture/Card_Surface_Materials.md section 4).

What these bars protect:
- every linked pair in the shipped catalogue: the counterpart authority and the shipped mirror
  file both carry the projection of that Settings theme's own ``backdrop.mode``;
- the fill that put it there adds that one key and nothing else (authored colour roles in the
  hand-edited mirrors survive), leaves the unlinked material themes alone, and is idempotent;
- end to end on the binder: a linked pair resolved under Keep Synced, made active, gives a card
  on Theme/Inherit that material; Style Overrides still beat it.

Themes are authored content: expected materials are derived from each Settings theme file,
never pinned. The only fixed table is the operator's projection rule itself.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
THEMES = ROOT / "themes"
WIDGETS = THEMES / "widgets"
BUILTIN = "builtin:default-dark"

# The operator's rule (7 Nov 2026), not authored theme content.
_PAIR_MATERIAL = {"glass": "glass", "acrylic": "acrylic", "off": None}


def _settings_themes() -> dict[str, object]:
    from ui.settings_theme_io import load_settings_theme_file

    return {f"file:{path.name}": load_settings_theme_file(path)
            for path in sorted(THEMES.glob("*.srtheme")) if path.name != "Default Dark.srtheme"}


def _linked_mirrors() -> dict[str, tuple[Path, object]]:
    from ui.widget_theme_io import load_widget_theme_file

    mirrors = {}
    for path in sorted(WIDGETS.glob("*.srwtheme")):
        theme = load_widget_theme_file(path)
        if theme.linked_settings_theme_id is not None:
            mirrors[theme.linked_settings_theme_id] = (path, theme)
    return mirrors


def _first_pair_with_mode(mode: str) -> str:
    for settings_id, spec in _settings_themes().items():
        if spec.backdrop.mode == mode:
            return settings_id
    pytest.skip(f"the shipped catalogue has no {mode} Settings theme")


def test_every_linked_pair_carries_its_settings_themes_material_in_authority_and_file() -> None:
    from tools.generate_widget_theme_mirrors import widget_counterpart_for_settings_theme

    if not WIDGETS.is_dir():
        pytest.skip("optional generated mirrors are absent from this source bundle")
    settings = _settings_themes()
    mirrors = _linked_mirrors()
    seen = set()
    for settings_id, spec in settings.items():
        if settings_id not in mirrors:
            continue
        expected = _PAIR_MATERIAL[spec.backdrop.mode]
        path, mirror = mirrors[settings_id]
        counterpart = widget_counterpart_for_settings_theme(spec, settings_theme_id=settings_id)
        assert counterpart.surface_material == expected, (settings_id, "authority")
        assert mirror.surface_material == expected, (path.name, "shipped mirror")
        seen.add(spec.backdrop.mode)
    # Non-vacuous: both card materials are exercised by the shipped pack.
    assert {"glass", "acrylic"} <= seen


def test_the_builtin_pair_stays_the_compiled_normal_fallback() -> None:
    """The compiled Default Dark Widget theme is the runtime fallback and the initial active
    theme; it names no material so the error path and every un-themed start stay Normal."""

    from tools.generate_widget_theme_mirrors import widget_counterpart_for_settings_theme
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME
    from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME

    counterpart = widget_counterpart_for_settings_theme(DEFAULT_DARK_SETTINGS_THEME, settings_theme_id=BUILTIN)
    assert counterpart == DEFAULT_DARK_WIDGET_THEME
    assert counterpart.surface_material is None


def test_the_fill_adds_one_key_keeps_authored_roles_and_skips_unlinked_themes(tmp_path) -> None:
    import json

    from tools.generate_widget_theme_mirrors import fill_widget_theme_mirror_materials

    if not WIDGETS.is_dir():
        pytest.skip("optional generated mirrors are absent from this source bundle")
    root = tmp_path / "themes"
    shutil.copytree(THEMES, root)
    # Undo the fill on the copy: strip the key from every linked mirror.
    shipped = {path.name: path.read_text(encoding="utf-8") for path in WIDGETS.glob("*.srwtheme")}
    stripped = []
    for path in (root / "widgets").glob("*.srwtheme"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("linked_settings_theme_id") is not None and "surface_material" in payload:
            del payload["surface_material"]
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            stripped.append(path.name)
    assert stripped

    changed = fill_widget_theme_mirror_materials(root)

    assert sorted(path.name for path in changed) == sorted(stripped)
    for name, text in shipped.items():
        # Byte-identical to the shipped pack: authored colours, names, ids and the
        # unlinked material themes are untouched; only the one key came back.
        assert (root / "widgets" / name).read_text(encoding="utf-8") == text, name
    assert fill_widget_theme_mirror_materials(root) == ()          # idempotent


def _clock_card_material(qt_app, widgets_config: dict) -> str:
    from core.settings.default_contract import require_canonical_default
    from rendering.quick.widgets.family_binder import ClockFamilyAdapter

    adapter = ClockFamilyAdapter()
    model = adapter.presentation_model(
        widget_id="clock", widgets_config=widgets_config,
        shadow_values=require_canonical_default("widgets.shadows"),
        display_identity="screen:a", runtime_generation=1701,
    )
    try:
        return adapter.presentation_card_style(model).surface_material
    finally:
        if hasattr(model, "retire"):
            model.retire()
        qt_app.processEvents()


@pytest.mark.parametrize("pair", ["canonical default", "glass", "acrylic"])
def test_a_synced_pair_gives_the_card_its_material_through_the_binder(qt_app, pair) -> None:
    from core.settings.default_contract import require_canonical_default
    from ui.widget_theme_active import reset_active_widget_theme, set_active_widget_theme
    from ui.widget_theme_catalog import build_widget_theme_catalog
    from ui.widget_theme_runtime import WidgetThemeState
    from ui.widget_theme_selection import resolve_widget_theme_state
    from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME_ID

    if not WIDGETS.is_dir():
        pytest.skip("optional generated mirrors are absent from this source bundle")
    settings_id = (str(require_canonical_default("ui.settings_theme_selection"))
                   if pair == "canonical default" else _first_pair_with_mode(pair))
    settings_spec = _settings_themes()[settings_id]
    expected = _PAIR_MATERIAL[settings_spec.backdrop.mode]
    if expected is None:
        pytest.skip(f"{settings_id} names no backdrop material")

    # Keep Synced on, with a stored selection that is NOT the mirror: the link decides.
    state = WidgetThemeState(selected_id=DEFAULT_DARK_WIDGET_THEME_ID, keep_synced=True, custom_payload=None)
    resolved = resolve_widget_theme_state(
        state, catalog=build_widget_theme_catalog(WIDGETS), settings_theme_id=settings_id,
    )
    assert resolved.theme.linked_settings_theme_id == settings_id and not resolved.used_fallback
    set_active_widget_theme(resolved.theme)
    try:
        on_theme = {"global": {"surface_material": "theme"}, "clock": {"surface_material": "inherit"}}
        assert _clock_card_material(qt_app, on_theme) == expected
        # Style Overrides still win over the theme when not set to Theme.
        overrides = [material for material in ("normal", "smoked") if material != expected]
        assert _clock_card_material(qt_app, {"global": {"surface_material": overrides[0]},
                                             "clock": {"surface_material": "inherit"}}) == overrides[0]
        assert _clock_card_material(qt_app, {"global": {"surface_material": "theme"},
                                             "clock": {"surface_material": overrides[-1]}}) == overrides[-1]
    finally:
        reset_active_widget_theme()


def test_the_themes_tab_shows_a_widget_themes_material_on_its_label(qt_app, tmp_path, monkeypatch) -> None:
    from dataclasses import replace

    from PySide6.QtCore import Qt

    from core.settings import SettingsManager
    from rendering.quick.widgets.surface_material import SURFACE_MATERIAL_LABELS
    from ui.settings_theme_catalog import (
        BUILTIN_DEFAULT_THEME_ID, SettingsThemeCatalog, SettingsThemeCatalogEntry,
    )
    from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME
    from ui.tabs.themes_tab import ThemesTab
    from ui.widget_theme_catalog import WidgetThemeCatalog, WidgetThemeCatalogEntry
    from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME

    settings_catalog = SettingsThemeCatalog((SettingsThemeCatalogEntry(
        BUILTIN_DEFAULT_THEME_ID, "Default", DEFAULT_DARK_SETTINGS_THEME, None, is_builtin=True),), ())
    themes = {"plain": None, "tinted": "glass"}
    widget_catalog = WidgetThemeCatalog((
        WidgetThemeCatalogEntry(DEFAULT_DARK_WIDGET_THEME.theme_id, "Default", DEFAULT_DARK_WIDGET_THEME, None,
                                is_builtin=True),
        *(WidgetThemeCatalogEntry(identity, identity.title(),
                                  replace(DEFAULT_DARK_WIDGET_THEME, theme_id=identity, name=identity.title(),
                                          surface_material=material), None, is_builtin=False)
          for identity, material in themes.items()),
    ), ())
    monkeypatch.setattr("ui.tabs.themes_tab.get_current_widget_theme_catalog", lambda: widget_catalog)
    manager = SettingsManager(application="ThemePairMaterialTest", storage_base_dir=tmp_path / "profile")
    manager.set("ui.settings_theme_selection", BUILTIN_DEFAULT_THEME_ID)
    page = ThemesTab(manager, catalog=settings_catalog)
    try:
        view = page.widget_theme_list
        labels = {view.item(row).data(Qt.ItemDataRole.UserRole): view.item(row).text() for row in range(view.count())}
        assert labels["plain"] == "Plain"
        assert labels["tinted"].startswith("Tinted") and SURFACE_MATERIAL_LABELS["glass"] in labels["tinted"]
    finally:
        page.deleteLater()
        assert manager.flush(timeout=5)


def test_unlinked_material_themes_keep_their_own_material_independently() -> None:
    from ui.widget_theme_catalog import build_widget_theme_catalog
    from ui.widget_theme_io import load_widget_theme_file
    from ui.widget_theme_runtime import WidgetThemeState
    from ui.widget_theme_selection import resolve_widget_theme_state

    if not WIDGETS.is_dir():
        pytest.skip("optional generated mirrors are absent from this source bundle")
    catalog = build_widget_theme_catalog(WIDGETS)
    unlinked = [theme for theme in (load_widget_theme_file(path) for path in sorted(WIDGETS.glob("*.srwtheme")))
                if theme.linked_settings_theme_id is None and theme.surface_material is not None]
    assert unlinked
    settings_id = next(iter(_settings_themes()))
    for theme in unlinked:
        independent = resolve_widget_theme_state(
            WidgetThemeState(selected_id=theme.theme_id, keep_synced=False, custom_payload=None),
            catalog=catalog, settings_theme_id=settings_id,
        )
        assert independent.theme == theme
        assert independent.theme.surface_material == theme.surface_material
