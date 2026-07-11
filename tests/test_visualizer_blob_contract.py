"""Focused persistence and migration bars for the Blob subtype contract."""
from __future__ import annotations

from pathlib import Path
import uuid

import pytest

from core.settings.defaults import get_default_settings
from core.settings.models import SpotifyVisualizerSettings
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_blob_contract import (
    BLOB_MIGHTY_ONLY_KEYS,
    BLOB_SHAPED_ONLY_KEYS,
    BLOB_TYPE_MIGHTY,
    BLOB_TYPE_SHAPED,
    migrate_blob_type_mapping,
    normalize_blob_type,
)
from core.settings.visualizer_settings_snapshot import normalize_visualizer_mode_payload
from tools import visualizer_preset_repair as repair


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, BLOB_TYPE_MIGHTY),
        ("mighty", BLOB_TYPE_MIGHTY),
        ("MIGHTY", BLOB_TYPE_MIGHTY),
        ("normal", BLOB_TYPE_MIGHTY),
        ("unshaped", BLOB_TYPE_MIGHTY),
        ("shaped", BLOB_TYPE_SHAPED),
        ("unknown", BLOB_TYPE_MIGHTY),
    ],
)
def test_normalize_blob_type_emits_only_canonical_values(raw, expected):
    assert normalize_blob_type(raw) == expected


def test_legacy_boolean_is_used_only_when_canonical_type_is_absent():
    assert normalize_blob_type(None, legacy_shaper_enabled=True) == BLOB_TYPE_SHAPED
    assert normalize_blob_type(None, legacy_shaper_enabled="false") == BLOB_TYPE_MIGHTY
    assert normalize_blob_type("mighty", legacy_shaper_enabled=True) == BLOB_TYPE_MIGHTY


def test_blob_type_mapping_migrates_plain_and_dotted_legacy_keys_without_reemitting_them():
    plain = migrate_blob_type_mapping({"blob_shaper_enabled": True})
    assert plain == {"blob_type": BLOB_TYPE_SHAPED}

    prefix = "widgets.spotify_visualizer"
    dotted = migrate_blob_type_mapping({f"{prefix}.blob_shaper_enabled": False})
    assert dotted == {f"{prefix}.blob_type": BLOB_TYPE_MIGHTY}


@pytest.mark.parametrize(
    ("source", "expected_type", "preserves_shape"),
    [
        ({"blob_shaper_enabled": True}, BLOB_TYPE_SHAPED, True),
        ({"blob_shaper_enabled": False}, BLOB_TYPE_MIGHTY, False),
        ({"blob_type": "normal"}, BLOB_TYPE_MIGHTY, False),
        ({"blob_type": "unshaped"}, BLOB_TYPE_MIGHTY, False),
        ({"blob_type": "shaped"}, BLOB_TYPE_SHAPED, True),
    ],
)
def test_blob_mode_snapshot_migrates_type_and_strips_inactive_subtype_payload(
    source,
    expected_type,
    preserves_shape,
):
    payload = {
        "mode": "blob",
        **source,
        "blob_shape_base_nodes": [[0.0, 0.8], [0.5, 1.2]],
        "blob_topology": "ring",
        "blob_constant_wobble": 1.7,
        "blob_reactive_wobble": 2.2,
        "blob_stretch": 0.65,
        "blob_inward_liquid_enabled": True,
    }

    normalized = normalize_visualizer_mode_payload("blob", payload)

    assert normalized["blob_type"] == expected_type
    assert "blob_shaper_enabled" not in normalized
    assert ("blob_shape_base_nodes" in normalized) is preserves_shape
    assert ("blob_topology" in normalized) is preserves_shape
    assert bool(BLOB_MIGHTY_ONLY_KEYS.intersection(normalized)) is not preserves_shape
    # Inward liquid is shared appearance, not Shaped contour authority.
    assert normalized["blob_inward_liquid_enabled"] is True


def test_model_round_trip_emits_blob_type_and_never_legacy_boolean():
    model = SpotifyVisualizerSettings.from_mapping(
        {
            "mode": "blob",
            "blob_shaper_enabled": True,
            "blob_shape_base_nodes": [[0.0, 0.9], [0.5, 1.1]],
        },
        apply_preset_overlay=False,
    )

    serialized = model.to_dict()

    assert model.blob_type == BLOB_TYPE_SHAPED
    assert serialized["widgets.spotify_visualizer.blob_type"] == BLOB_TYPE_SHAPED
    assert "widgets.spotify_visualizer.blob_shaper_enabled" not in serialized


def test_canonical_defaults_use_mighty_without_legacy_boolean():
    visualizer = get_default_settings()["widgets"]["spotify_visualizer"]
    assert visualizer["blob_type"] == BLOB_TYPE_MIGHTY
    assert "blob_shaper_enabled" not in visualizer


def test_schema_v1_migrates_legacy_shaped_blob_before_default_merge(tmp_path: Path):
    app_name = f"BlobSchema_{uuid.uuid4().hex}"
    manager = SettingsManager(
        organization="Test",
        application=app_name,
        storage_base_dir=tmp_path,
    )
    manager._settings.setValue(
        "widgets",
        {
            "spotify_visualizer": {
                "mode": "blob",
                "blob_shaper_enabled": True,
                "blob_shape_base_nodes": [[0.0, 0.75], [0.5, 1.25]],
            }
        },
    )
    manager._settings.update_metadata(visualizer_schema_version=1)
    manager._settings.sync()

    reloaded = SettingsManager(
        organization="Test",
        application=app_name,
        storage_base_dir=tmp_path,
    )
    visualizer = reloaded.get("widgets.spotify_visualizer")

    assert visualizer["blob_type"] == BLOB_TYPE_SHAPED
    assert "blob_shaper_enabled" not in visualizer
    assert visualizer["blob_shape_base_nodes"] == [[0.0, 0.75], [0.5, 1.25]]
    assert (
        reloaded._settings.metadata()["visualizer_schema_version"]
        == SettingsManager._VISUALIZER_SCHEMA_VERSION
    )


def test_current_schema_validation_does_not_preserve_reintroduced_legacy_boolean(tmp_path: Path):
    manager = SettingsManager(
        organization="Test",
        application=f"BlobValidation_{uuid.uuid4().hex}",
        storage_base_dir=tmp_path,
    )
    manager._settings.setValue(
        "widgets",
        {
            "spotify_visualizer": {
                "mode": "blob",
                "blob_shaper_enabled": True,
                "blob_shape_base_nodes": [[0.0, 0.8], [0.5, 1.2]],
            }
        },
    )
    manager._settings.update_metadata(
        visualizer_schema_version=SettingsManager._VISUALIZER_SCHEMA_VERSION
    )

    manager.validate_and_repair()
    visualizer = manager.get("widgets.spotify_visualizer")

    assert visualizer["blob_type"] == BLOB_TYPE_SHAPED
    assert "blob_shaper_enabled" not in visualizer


def test_preset_repair_migrates_legacy_blob_contract_and_audits_aliases():
    payload = {
        "snapshot": {
            "widgets": {
                "spotify_visualizer": {
                    "mode": "blob",
                    "blob_shaper_enabled": True,
                    "blob_shape_base_nodes": [[0.0, 0.8], [0.5, 1.2]],
                }
            }
        }
    }

    report = repair.audit_payload("blob", payload)
    sanitized, _stats = repair._sanitize_settings("blob", payload)

    assert report["deprecated_mode_alias_keys"] == ["blob_shaper_enabled"]
    assert sanitized["blob_type"] == BLOB_TYPE_SHAPED
    assert "blob_shaper_enabled" not in sanitized
    assert BLOB_SHAPED_ONLY_KEYS.intersection(sanitized) == {"blob_shape_base_nodes"}


def test_preset_repair_strips_shaped_payload_from_mighty_alias():
    payload = {
        "snapshot": {
            "widgets": {
                "spotify_visualizer": {
                    "mode": "blob",
                    "blob_type": "normal",
                    "blob_shape_base_nodes": [[0.0, 0.8], [0.5, 1.2]],
                    "blob_inward_liquid_enabled": True,
                }
            }
        }
    }

    sanitized, _stats = repair._sanitize_settings("blob", payload)

    assert sanitized["blob_type"] == BLOB_TYPE_MIGHTY
    assert not BLOB_SHAPED_ONLY_KEYS.intersection(sanitized)
    assert sanitized["blob_inward_liquid_enabled"] is True


def test_preset_repair_strips_mighty_payload_from_shaped_blob():
    payload = {
        "snapshot": {
            "widgets": {
                "spotify_visualizer": {
                    "mode": "blob",
                    "blob_type": "shaped",
                    "blob_constant_wobble": 1.8,
                    "blob_reactive_wobble": 2.4,
                    "blob_stretch": 0.7,
                    "blob_shape_base_nodes": [[0.0, 0.8], [0.5, 1.2]],
                    "blob_inward_liquid_enabled": True,
                }
            }
        }
    }

    report = repair.audit_payload("blob", payload)
    sanitized, _stats = repair._sanitize_settings("blob", payload)

    assert report["inactive_blob_mighty_payload"] is True
    assert sanitized["blob_type"] == BLOB_TYPE_SHAPED
    assert not BLOB_MIGHTY_ONLY_KEYS.intersection(sanitized)
    assert sanitized["blob_shape_base_nodes"] == [[0.0, 0.8], [0.5, 1.2]]
    assert sanitized["blob_inward_liquid_enabled"] is True
