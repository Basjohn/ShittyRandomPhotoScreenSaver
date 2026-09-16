from __future__ import annotations

import json
from pathlib import Path

from core.settings.json_store import JsonSettingsStore
from core.settings.structured_input_compat import (
    normalize_legacy_structured_mapping_shape,
    promote_legacy_structured_store_shape,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "settings_legacy_structured_profile.json"


def test_legacy_structured_profile_fixture_is_distinguishing_old_input() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snapshot = payload["snapshot"]

    assert "dialog_geometry.width" in snapshot["ui"]
    assert "ui.dialog_geometry.height" in snapshot
    assert "clock.enabled" in snapshot["widgets"]
    assert "widgets.clock.show_seconds" in snapshot
    assert snapshot["ui"]["dialog_geometry"]["width"] == 1600


def test_mapping_promotion_prefers_current_nested_shape_and_is_idempotent() -> None:
    old = {
        "dialog_geometry.width": 1389,
        "dialog_geometry.height": 900,
        "dialog_geometry": {"width": 1600},
    }

    promoted, changed = normalize_legacy_structured_mapping_shape(old)
    assert changed is True
    assert promoted == {"dialog_geometry": {"width": 1600, "height": 900}}

    second, second_changed = normalize_legacy_structured_mapping_shape(promoted)
    assert second == promoted
    assert second_changed is False


def test_store_promotion_folds_root_member_keys_without_touching_unrelated_state() -> None:
    old = {
        "ui": {"dialog_geometry.width": 1389, "dialog_geometry": {"width": 1600}},
        "ui.dialog_geometry.height": 900,
        "widgets.clock.enabled": False,
        "display.image_interval": 47,
    }

    promoted, repaired = promote_legacy_structured_store_shape(old)
    assert repaired == ("ui", "widgets")
    assert promoted["ui"] == {"dialog_geometry": {"width": 1600, "height": 900}}
    assert promoted["widgets"] == {"clock": {"enabled": False}}
    assert promoted["display.image_interval"] == 47
    assert "ui.dialog_geometry.height" not in promoted
    assert "widgets.clock.enabled" not in promoted


def test_json_store_load_promotes_old_structured_shape_at_input_boundary(tmp_path: Path) -> None:
    target = tmp_path / "settings_v2.json"
    target.write_bytes(FIXTURE.read_bytes())

    store = JsonSettingsStore(storage_path=target, profile="Screensaver")

    assert store.value("ui") == {"dialog_geometry": {"width": 1600, "height": 900}}
    assert store.value("widgets") == {
        "clock": {
            "enabled": False,
            "show_separator": True,
            "show_seconds": False,
        }
    }
    assert store.value("display.image_interval") == 47
    assert store.contains("ui.dialog_geometry.height") is False
    assert store.contains("widgets.clock.show_seconds") is False
    assert store.persistence_snapshot()["dirty"] is True

    assert store.sync(wait=True) is True
    written = json.loads(target.read_text(encoding="utf-8"))["snapshot"]
    assert written["ui"] == {"dialog_geometry": {"width": 1600, "height": 900}}
    assert written["widgets"]["clock"]["show_seconds"] is False
    assert "ui.dialog_geometry.height" not in written
    assert "widgets.clock.show_seconds" not in written

    second = JsonSettingsStore(storage_path=target, profile="Screensaver")
    assert second.persistence_snapshot()["dirty"] is False
    assert second.value("ui") == store.value("ui")
    assert second.value("widgets") == store.value("widgets")


def test_nested_semantic_dotted_keys_are_not_reinterpreted() -> None:
    old = {
        "widget_theme": {
            "custom": {
                "colors": {
                    "card.background": [12, 34, 56, 255],
                }
            }
        }
    }

    promoted, repaired = promote_legacy_structured_store_shape(old)
    assert repaired == ()
    assert promoted == old


def test_qsettings_and_sst_use_the_same_explicit_compatibility_owner() -> None:
    manager = (ROOT / "core" / "settings" / "settings_manager.py").read_text(encoding="utf-8")
    sst = (ROOT / "core" / "settings" / "sst_io.py").read_text(encoding="utf-8")

    qsettings_promotion = "flat, repaired_roots = promote_legacy_structured_store_shape(flat)"
    assert qsettings_promotion in manager
    assert manager.index(qsettings_promotion) < manager.index("self._settings.replace_all(flat)")
    assert "normalize_legacy_structured_mapping_shape(section_value)" in sst
    assert "mgr._normalize_structured_mapping_shape" not in sst


def test_current_writer_keeps_declared_structured_roots_nested() -> None:
    persistence = (ROOT / "core" / "settings" / "persistence.py").read_text(encoding="utf-8")
    manager = (ROOT / "core" / "settings" / "settings_manager.py").read_text(encoding="utf-8")

    assert "if key in STRUCTURED_SETTINGS_ROOTS and isinstance(value, Mapping):" in persistence
    assert "snapshot[key] = value" in persistence
    assert "def _normalize_structured_root_storage" not in manager
    assert "def _normalize_structured_mapping_shape" not in manager
