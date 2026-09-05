"""Widget Theme — semantic/serialization/resolver contract (colour-only v3).

Covers the guaranteed Default Dark fallback, whole-or-reject `.srwtheme` I/O, the
catalogue, the Keep Synced identity rule, Custom snapshot resolution, and the
theme-owned-edit ownership transition. No Qt runtime, no render cost — this is the
data/state-machine layer.

The abandoned Glass/Acrylic card-material dimension was removed with the runtime
rollback; the schema is colour-only schema-v3. The source-level guard that material
does not creep back lives in ``test_widget_theme_no_material_contract.py``; this
module owns the surviving behavioural contracts.
"""

from __future__ import annotations

import json

import pytest

from ui.settings_theme_spec import Rgba
from ui.widget_theme_spec import (
    DEFAULT_DARK_WIDGET_THEME,
    WIDGET_THEME_SCHEMA_VERSION,
    WidgetThemeSpec,
)
from ui.widget_theme_io import (
    WIDGET_THEME_FILE_EXTENSION,
    WidgetThemeFileError,
    load_widget_theme_or_default,
    save_widget_theme_file,
    widget_theme_from_json,
    widget_theme_to_json,
    widget_theme_to_payload,
)
from ui.widget_theme_catalog import (
    build_widget_theme_catalog,
    resolve_widget_theme_selection,
)
from ui.widget_theme_runtime import (
    CUSTOM_WIDGET_THEME_ID,
    WidgetThemeState,
    begin_theme_owned_edit,
    resolve_widget_theme,
)


# -- default validity ------------------------------------------------------- #


def test_default_dark_is_colour_only_v3_and_valid():
    assert DEFAULT_DARK_WIDGET_THEME.theme_id == "default_dark"
    assert DEFAULT_DARK_WIDGET_THEME.schema_version == WIDGET_THEME_SCHEMA_VERSION
    # Core card roles are complete on the compiled default.
    assert "card.background" in DEFAULT_DARK_WIDGET_THEME.colors
    assert "card.border" in DEFAULT_DARK_WIDGET_THEME.colors


# -- whole-or-reject I/O ---------------------------------------------------- #


def test_json_round_trip_is_identity():
    assert (
        widget_theme_from_json(widget_theme_to_json(DEFAULT_DARK_WIDGET_THEME))
        == DEFAULT_DARK_WIDGET_THEME
    )


def test_missing_semantic_role_rejects_whole_theme():
    payload = widget_theme_to_payload(DEFAULT_DARK_WIDGET_THEME)
    payload["colors"].pop("card.background")
    with pytest.raises(WidgetThemeFileError):
        widget_theme_from_json(json.dumps(payload))


def test_unknown_semantic_role_rejects_whole_theme():
    payload = widget_theme_to_payload(DEFAULT_DARK_WIDGET_THEME)
    payload["colors"]["card.made_up"] = [1, 2, 3, 4]
    with pytest.raises(WidgetThemeFileError):
        widget_theme_from_json(json.dumps(payload))


def test_wrong_format_or_schema_rejects_whole_theme():
    payload = widget_theme_to_payload(DEFAULT_DARK_WIDGET_THEME)
    payload["format"] = "srpss.settings-theme"
    with pytest.raises(WidgetThemeFileError):
        widget_theme_from_json(json.dumps(payload))


def test_safe_loader_falls_back_to_default_dark(tmp_path):
    # None means no override requested.
    assert load_widget_theme_or_default(None).theme == DEFAULT_DARK_WIDGET_THEME
    assert load_widget_theme_or_default(None).used_fallback is True
    # An invalid file falls back rather than raising.
    bad = tmp_path / "broken.srwtheme"
    bad.write_text("{ not json", encoding="utf-8")
    result = load_widget_theme_or_default(bad)
    assert result.theme == DEFAULT_DARK_WIDGET_THEME
    assert result.used_fallback is True
    assert result.error


def test_save_round_trips_a_real_file(tmp_path):
    edited = WidgetThemeSpec(
        theme_id="ocean",
        name="Ocean",
        linked_settings_theme_id="ocean_settings",
        colors=dict(DEFAULT_DARK_WIDGET_THEME.colors),
    )
    path = tmp_path / f"Ocean{WIDGET_THEME_FILE_EXTENSION}"
    save_widget_theme_file(edited, path)
    assert load_widget_theme_or_default(path).theme == edited


# -- catalogue -------------------------------------------------------------- #


def test_catalogue_always_has_builtin_default_first(tmp_path):
    catalog = build_widget_theme_catalog(tmp_path)  # empty dir
    assert catalog.builtin_default.theme == DEFAULT_DARK_WIDGET_THEME
    assert catalog.entry_by_id("default_dark") is not None


def test_catalogue_discovers_valid_files_and_reports_issues(tmp_path):
    good = WidgetThemeSpec(
        theme_id="ocean",
        name="Ocean",
        colors=dict(DEFAULT_DARK_WIDGET_THEME.colors),
    )
    save_widget_theme_file(good, tmp_path / "Ocean.srwtheme")
    (tmp_path / "Broken.srwtheme").write_text("nonsense", encoding="utf-8")

    catalog = build_widget_theme_catalog(tmp_path)
    assert catalog.entry_by_id("ocean") is not None
    assert any(issue.error for issue in catalog.issues)


def test_selection_resolution_falls_back_for_unknown_id(tmp_path):
    catalog = build_widget_theme_catalog(tmp_path)
    resolution = resolve_widget_theme_selection(catalog, "does_not_exist")
    assert resolution.used_fallback is True
    assert resolution.entry.theme == DEFAULT_DARK_WIDGET_THEME


# -- resolver + Keep Synced + Custom --------------------------------------- #


def test_resolve_defaults_to_dark(tmp_path):
    catalog = build_widget_theme_catalog(tmp_path)
    resolved = resolve_widget_theme(WidgetThemeState(), catalog)
    assert resolved.theme == DEFAULT_DARK_WIDGET_THEME
    assert resolved.is_custom is False


def test_keep_synced_uses_linked_id_when_on_and_stored_selection_when_off(tmp_path):
    ocean = WidgetThemeSpec(
        theme_id="ocean",
        name="Ocean",
        colors=dict(DEFAULT_DARK_WIDGET_THEME.colors),
    )
    save_widget_theme_file(ocean, tmp_path / "Ocean.srwtheme")
    catalog = build_widget_theme_catalog(tmp_path)

    # Sync ON: the linked (mirrored) widget theme id wins over the stored selection.
    state = WidgetThemeState(selected_id="default_dark", keep_synced=True)
    resolved = resolve_widget_theme(state, catalog, synced_widget_theme_id="ocean")
    assert resolved.theme.theme_id == "ocean"

    # Sync OFF: the explicit selection wins, sync id ignored.
    state_off = WidgetThemeState(selected_id="default_dark", keep_synced=False)
    resolved_off = resolve_widget_theme(
        state_off, catalog, synced_widget_theme_id="ocean"
    )
    assert resolved_off.theme.theme_id == "default_dark"


def test_corrupt_custom_snapshot_falls_back_to_default_dark(tmp_path):
    catalog = build_widget_theme_catalog(tmp_path)
    state = WidgetThemeState(
        selected_id=CUSTOM_WIDGET_THEME_ID,
        custom_payload={"format": "wrong"},
    )
    resolved = resolve_widget_theme(state, catalog)
    assert resolved.theme == DEFAULT_DARK_WIDGET_THEME
    assert resolved.used_fallback is True
    assert resolved.error


def test_theme_owned_edit_snapshots_to_custom_and_unsyncs(tmp_path):
    catalog = build_widget_theme_catalog(tmp_path)
    active = DEFAULT_DARK_WIDGET_THEME
    new_border = Rgba(10, 120, 200, 255)

    snapshot, state = begin_theme_owned_edit(
        WidgetThemeState(keep_synced=True),
        active,
        "card.border",
        new_border,
    )

    # The edit lands on Custom; identity becomes Custom; sync turns OFF.
    assert snapshot.theme_id == CUSTOM_WIDGET_THEME_ID
    assert snapshot.color("card.border") == new_border
    assert state.selected_id == CUSTOM_WIDGET_THEME_ID
    assert state.keep_synced is False
    # The shipped theme is never mutated; unedited roles survive exactly.
    assert active.color("card.border") == DEFAULT_DARK_WIDGET_THEME.color("card.border")
    assert snapshot.color("card.background") == active.color("card.background")

    # The persisted Custom resolves back to the edited snapshot.
    resolved = resolve_widget_theme(state, catalog)
    assert resolved.is_custom is True
    assert resolved.theme.color("card.border") == new_border
