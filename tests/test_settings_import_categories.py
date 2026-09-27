"""Import Settings by category: only the chosen parts change; credentials never travel."""
from __future__ import annotations

import json

import pytest

from core.settings.sst_io import IMPORT_CATEGORIES, available_snapshot_categories, filter_snapshot_categories


def _snapshot(tmp_path, settings_manager):
    """Export the current store, then change one value in every category."""
    path = tmp_path / "other_pc.sst"
    assert settings_manager.export_to_sst(str(path))
    payload = json.loads(path.read_text(encoding="utf-8"))
    snap = payload["snapshot"]
    snap["display"]["sharpen_downscale"] = not settings_manager.get("display.sharpen_downscale")
    snap["widgets"]["clock"]["font_size"] = 111
    snap["widgets"]["clock"]["position"] = "Bottom Left"
    snap["widgets"]["layout_slots"] = {"version": 1, "slots": {"3": {"clock": {"position": "Center"}}}}
    snap["transitions"]["duration_ms"] = 4321
    snap["widget_theme"]["keep_synced"] = not settings_manager.get("widget_theme.keep_synced")
    snap["sources"]["folders"] = ["D:/Imported"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _state(settings_manager):
    return {
        "display": settings_manager.get("display.sharpen_downscale"),
        "font": settings_manager.get("widgets.clock.font_size"),
        "position": settings_manager.get("widgets.clock.position"),
        "slots": settings_manager.get("widgets.layout_slots"),
        "transition": settings_manager.get("transitions.duration_ms"),
        "theme": settings_manager.get("widget_theme.keep_synced"),
        "folders": settings_manager.get("sources.folders"),
    }


def test_snapshot_lists_the_categories_it_contains(tmp_path, settings_manager):
    path = _snapshot(tmp_path, settings_manager)
    assert set(available_snapshot_categories(str(path))) == {key for key, _ in IMPORT_CATEGORIES}


@pytest.mark.parametrize("category,changes", [
    ("display", {"display"}),
    ("widgets", {"font"}),
    ("transitions", {"transition"}),
    ("theme", {"theme"}),
    ("geometry", {"position", "slots"}),
    ("misc", {"folders"}),
])
def test_importing_one_category_changes_only_that_category(tmp_path, settings_manager, category, changes):
    path = _snapshot(tmp_path, settings_manager)
    before = _state(settings_manager)
    assert settings_manager.import_from_sst(str(path), merge=True, categories=(category,))
    after = _state(settings_manager)
    changed = {key for key in before if before[key] != after[key]}
    assert changed == changes


def test_all_categories_equal_a_full_import(tmp_path, settings_manager):
    path = _snapshot(tmp_path, settings_manager)
    root = json.loads(path.read_text(encoding="utf-8"))["snapshot"]
    from core.settings.sst_io import normalize_sst_snapshot
    normalized = normalize_sst_snapshot(root)
    assert filter_snapshot_categories(normalized, [key for key, _ in IMPORT_CATEGORIES]) == normalized
    with pytest.raises(ValueError):
        filter_snapshot_categories(normalized, ["passwords"])


def test_credentials_never_travel_in_a_category_import(tmp_path, settings_manager):
    path = _snapshot(tmp_path, settings_manager)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["snapshot"]["widgets"]["steam"]["api_key"] = "SECRET-KEY"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert settings_manager.import_from_sst(str(path), merge=True, categories=("widgets",))
    assert "api_key" not in (settings_manager.get("widgets.steam") or {})


def test_chooser_all_settings_toggles_every_available_category(qapp):
    from ui.settings_import import ImportCategoryChooser
    chooser = ImportCategoryChooser(("display", "widgets", "misc"))
    try:
        assert chooser.everything() and set(chooser.chosen()) == {"display", "widgets", "misc"}
        assert not chooser.boxes["theme"].isEnabled()  # nothing of that kind in the file
        chooser.boxes["widgets"].setChecked(False)
        assert not chooser.everything() and set(chooser.chosen()) == {"display", "misc"}
        chooser.all.setChecked(True)
        assert set(chooser.chosen()) == {"display", "widgets", "misc"}
        chooser.all.setChecked(False)
        assert chooser.chosen() == ()
    finally:
        chooser.deleteLater()


def test_welcome_import_finishes_guided_setup_without_saving_the_draft(qapp, monkeypatch):
    from copy import deepcopy
    from core.settings.defaults import get_default_settings
    import ui.settings_import as importing
    from ui.onboarding.wizard import GuidedSetupPanel

    class Store:
        def __init__(self):
            self.values = deepcopy(get_default_settings()); self.writes = []
        def get(self, key, default=None):
            value = self.values
            for part in key.split("."):
                if not isinstance(value, dict) or part not in value:
                    return default
                value = value[part]
            return deepcopy(value)
        def set(self, key, value):
            self.writes.append(key)
        def save(self): pass

    store = Store()
    received = []
    monkeypatch.setattr(importing, "run_settings_import", lambda parent, settings: received.append(settings) or True)
    wizard = GuidedSetupPanel(store)
    finished = []
    wizard.finished.connect(finished.append)
    try:
        wizard.settings.set("input.interaction_mode", True)  # an unsaved wizard choice
        wizard.pages["welcome"][0].import_button.click()
        assert received == [store]  # the import targets the real store, not the draft
        assert finished == [True]
        assert store.writes == []  # the draft was dropped, not committed over the import
    finally:
        wizard.deleteLater()


def test_import_flow_uses_the_chosen_categories_and_applies_an_imported_theme(qapp, tmp_path, settings_manager, monkeypatch):
    import ui.settings_import as importing
    from ui.styled_popup import StyledPopup
    path = _snapshot(tmp_path, settings_manager)
    calls = []
    real_import = settings_manager.import_from_sst
    monkeypatch.setattr(settings_manager, "import_from_sst",
                        lambda p, merge=True, categories=None: calls.append(categories) or real_import(p, merge, categories))
    monkeypatch.setattr(importing, "_activate_imported_theme", lambda settings: calls.append("theme-applied"))
    monkeypatch.setattr(StyledPopup, "show_success", staticmethod(lambda *a, **k: None))

    def choose_only_geometry(popup):
        chooser = popup._content
        chooser.all.setChecked(False)
        chooser.boxes["geometry"].setChecked(True)
        popup._result_value = "import"
    monkeypatch.setattr(StyledPopup, "exec", choose_only_geometry)
    assert importing.run_settings_import(None, settings_manager, str(path))
    assert calls == [("geometry",)]  # partial import; theme untouched so not re-applied

    calls.clear()
    monkeypatch.setattr(StyledPopup, "exec", lambda popup: setattr(popup, "_result_value", "import"))
    assert importing.run_settings_import(None, settings_manager, str(path))
    assert calls == [None, "theme-applied"]  # ALL SETTINGS: full import, theme applied live

    calls.clear()
    monkeypatch.setattr(StyledPopup, "exec", lambda popup: setattr(popup, "_result_value", "cancel"))
    assert not importing.run_settings_import(None, settings_manager, str(path))
    assert calls == []
