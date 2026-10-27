"""Physical selection bindings retain their identity through a real JSON load.

These tests use separate file-backed stores, not a second manager sharing the
process-local settings-store registry. Monitor identities are test-authored.
"""
from __future__ import annotations

import json

from core.settings.json_store import JsonSettingsStore


MSI = "serial:msi-test-owned"
LG = "serial:lg-test-owned"


def _store(path):
    return JsonSettingsStore(storage_path=path, profile="TestPhysicalSelection")


def test_monitor_mapping_survives_actual_disk_roundtrip_and_unrelated_save(tmp_path):
    target = tmp_path / "settings_v2.json"
    original = _store(target)
    original.setValue("display.show_on_monitors", [1, 2])
    original.setValue("display.monitor_bindings", {"1": MSI, "2": LG})
    original.setValue("display.mode", "fit")
    assert original.sync(wait=True)

    snapshot = json.loads(target.read_text(encoding="utf-8"))["snapshot"]
    assert snapshot["display"]["monitor_bindings"] == {"1": MSI, "2": LG}

    # A distinct store reads the actual disk file, bypassing the shared-store
    # registry that previously let manager-to-manager tests miss this defect.
    restarted = _store(target)
    assert restarted is not original
    assert restarted.value("display.monitor_bindings") == {"1": MSI, "2": LG}
    assert not restarted.contains("display.monitor_bindings.1")
    assert not restarted.contains("display.monitor_bindings.2")

    # An unrelated save cannot drop the now-unavailable monitor identity.
    # The GUI topology case is covered by test_saver_physical_selection.py.
    restarted.setValue("display.mode", "fill")  # unrelated settings save
    assert restarted.sync(wait=True)

    after_return = _store(target)
    assert after_return.value("display.monitor_bindings") == {"1": MSI, "2": LG}
    assert after_return.value("display.show_on_monitors") == [1, 2]
    assert after_return.value("display.mode") == "fill"
    assert after_return.persistence_snapshot()["dirty"] is False


def test_legacy_flattened_bindings_are_promoted_and_durable(tmp_path):
    target = tmp_path / "settings_v2.json"
    target.write_text(json.dumps({
        "version": 2,
        "profile": "TestPhysicalSelection",
        "snapshot": {"display": {
            "show_on_monitors": [1, 2],
            "monitor_bindings.1": MSI,
            "monitor_bindings.2": LG,
            "mode": "fit",
        }},
    }), encoding="utf-8")

    migrated = _store(target)
    assert migrated.value("display.monitor_bindings") == {"1": MSI, "2": LG}
    assert migrated.persistence_snapshot()["dirty"] is True
    assert migrated.sync(wait=True)
    snapshot = json.loads(target.read_text(encoding="utf-8"))["snapshot"]["display"]
    assert snapshot["monitor_bindings"] == {"1": MSI, "2": LG}
    assert not any(key.startswith("monitor_bindings.") for key in snapshot)

    reopened = _store(target)
    assert reopened.value("display.monitor_bindings") == {"1": MSI, "2": LG}
    assert reopened.persistence_snapshot()["dirty"] is False


def test_canonical_binding_wins_over_duplicate_legacy_key(tmp_path):
    target = tmp_path / "settings_v2.json"
    target.write_text(json.dumps({
        "version": 2,
        "profile": "TestPhysicalSelection",
        "snapshot": {
            "display": {
                "monitor_bindings": {"1": MSI},
                "monitor_bindings.1": LG,
                "monitor_bindings.2": LG,
            },
            "display.monitor_bindings.0": "invalid-monitor-label",
            "display.monitor_bindings.foo": "unrelated-invalid-key",
        },
    }), encoding="utf-8")
    store = _store(target)
    assert store.value("display.monitor_bindings") == {"1": MSI, "2": LG}
    assert store.contains("display.monitor_bindings.0")
    assert store.contains("display.monitor_bindings.foo")
    assert store.sync(wait=True)
    assert _store(target).value("display.monitor_bindings") == {"1": MSI, "2": LG}


def test_direct_dotted_root_mapping_loads_without_loss(tmp_path):
    target = tmp_path / "settings_v2.json"
    target.write_text(json.dumps({
        "version": 2,
        "profile": "TestPhysicalSelection",
        "snapshot": {"display.monitor_bindings": {"1": MSI, "2": LG}},
    }), encoding="utf-8")
    store = _store(target)
    assert store.value("display.monitor_bindings") == {"1": MSI, "2": LG}
    assert store.persistence_snapshot()["dirty"] is False
