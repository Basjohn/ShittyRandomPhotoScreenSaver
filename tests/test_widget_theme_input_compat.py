"""Retired Widget Theme material-state compatibility boundary.

Old profile/QSettings/SST state is still admitted while its support horizon is
open, but current Widget Theme UI/runtime/file I/O must consume colour-only v3
state and must not own the abandoned material keys.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from core.settings.json_store import JsonSettingsStore
from core.settings.sst_io import _project_import_state, normalize_sst_snapshot
from core.settings.widget_theme_input_compat import promote_legacy_widget_theme_state


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "widget_theme_legacy_material_state_profile.json"


def _fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _legacy_state() -> dict:
    return deepcopy(_fixture_payload()["snapshot"]["widget_theme"])


def test_fixture_is_distinguishing_legacy_material_state() -> None:
    state = _legacy_state()
    assert state["card_material_override"] == "acrylic"
    assert state["custom"]["schema_version"] == 2
    assert state["custom"]["default_card_material_mode"] == "glass"
    assert state["custom"]["colors"]["card.background"] == [35, 35, 35, 76]


def test_v1_and_v2_material_state_promote_exactly_to_v3() -> None:
    for old_version in (1, 2):
        state = _legacy_state()
        state["custom"]["schema_version"] = old_version
        expected_colors = deepcopy(state["custom"]["colors"])

        promoted, changed = promote_legacy_widget_theme_state(state)

        assert changed is True
        assert "card_material_override" not in promoted
        assert promoted["selected_id"] == "custom"
        assert promoted["keep_synced"] is False
        assert promoted["custom"]["schema_version"] == 3
        assert "default_card_material_mode" not in promoted["custom"]
        assert promoted["custom"]["theme_id"] == "custom"
        assert promoted["custom"]["name"] == "Legacy Custom"
        assert promoted["custom"]["linked_settings_theme_id"] is None
        assert promoted["custom"]["colors"] == expected_colors


def test_promotion_is_idempotent_and_does_not_repair_current_v3_payloads() -> None:
    promoted, changed = promote_legacy_widget_theme_state(_legacy_state())
    assert changed is True
    second, changed_again = promote_legacy_widget_theme_state(promoted)
    assert changed_again is False
    assert second == promoted

    current_with_unknown_member = deepcopy(promoted)
    current_with_unknown_member["custom"]["future_or_invalid_member"] = "preserve"
    unchanged, changed = promote_legacy_widget_theme_state(current_with_unknown_member)
    assert changed is False
    assert unchanged == current_with_unknown_member


def test_json_profile_migrates_once_and_second_load_is_clean(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(_fixture_payload(), indent=2), encoding="utf-8")

    store = JsonSettingsStore(storage_path=path, profile="test")
    state = store.value("widget_theme")
    assert isinstance(state, dict)
    assert "card_material_override" not in state
    assert state["custom"]["schema_version"] == 3
    assert "default_card_material_mode" not in state["custom"]
    assert store.value("display.image_interval") == 47
    assert store.persistence_snapshot()["dirty"] is True
    assert store.sync(wait=True)

    disk = json.loads(path.read_text(encoding="utf-8"))
    disk_state = disk["snapshot"]["widget_theme"]
    assert "card_material_override" not in disk_state
    assert disk_state["custom"]["schema_version"] == 3
    assert "default_card_material_mode" not in disk_state["custom"]

    reloaded = JsonSettingsStore(storage_path=path, profile="test")
    assert reloaded.value("widget_theme") == state
    assert reloaded.persistence_snapshot()["dirty"] is False


def test_all_supported_old_input_boundaries_use_compat_owner() -> None:
    json_store = (ROOT / "core" / "settings" / "json_store.py").read_text(encoding="utf-8")
    manager = (ROOT / "core" / "settings" / "settings_manager.py").read_text(encoding="utf-8")
    sst = (ROOT / "core" / "settings" / "sst_io.py").read_text(encoding="utf-8")

    assert "promote_legacy_widget_theme_state(raw_widget_theme)" in json_store
    assert "promote_legacy_widget_theme_state(raw_widget_theme)" in manager
    assert 'section_key == "widget_theme"' in sst
    assert "promote_legacy_widget_theme_state(normalized)" in sst


def test_sst_projection_promotes_old_material_state_before_current_store() -> None:
    class _EmptySettings:
        def allKeys(self) -> list[str]:
            return []

        def value(self, _key: str):
            return None

    class _Manager:
        _settings = _EmptySettings()

        @staticmethod
        def _coerce_import_value(_key: str, value):
            return value

    normalized = normalize_sst_snapshot({"widget_theme": _legacy_state()})
    projected = _project_import_state(_Manager(), normalized, merge=True)
    state = projected["widget_theme"]
    assert "card_material_override" not in state
    assert state["custom"]["schema_version"] == 3
    assert "default_card_material_mode" not in state["custom"]
    assert state["custom"]["colors"]["card.background"] == [35, 35, 35, 76]


def test_current_widget_theme_selection_and_file_io_have_no_material_compatibility() -> None:
    selection = (ROOT / "ui" / "widget_theme_selection.py").read_text(encoding="utf-8")
    file_io = (ROOT / "ui" / "widget_theme_io.py").read_text(encoding="utf-8")
    runtime = (ROOT / "ui" / "widget_theme_runtime.py").read_text(encoding="utf-8")

    for retired in ("card_material_override", "default_card_material_mode"):
        assert retired not in selection
        assert retired not in file_io
        assert retired not in runtime
    assert "schema_version != WIDGET_THEME_SCHEMA_VERSION" in file_io
