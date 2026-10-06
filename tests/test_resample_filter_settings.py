"""Persisted-input migration coverage for the wallpaper resampling enum."""
from __future__ import annotations

import json
import uuid

import pytest

from core.settings.default_contract import require_canonical_default
from rendering.image_quality import RESAMPLE_FILTERS
from core.settings.resample_filter_input_compat import (
    LEGACY_USE_LANCZOS_KEY,
    RESAMPLE_FILTER_KEY,
    normalize_resample_filter,
)
from core.settings.settings_manager import SettingsManager
from core.settings.sst_io import import_from_sst


def _manager(tmp_path, name: str) -> SettingsManager:
    return SettingsManager(
        organization="Test",
        application=f"resample_filter_{name}_{uuid.uuid4().hex}",
        storage_base_dir=tmp_path / name,
    )


@pytest.mark.parametrize(
    ("legacy_value", "expected"),
    ((True, "lanczos"), (False, "smooth")),
)
def test_existing_profile_migrates_retired_lanczos_bool_before_defaults(
    tmp_path, legacy_value, expected,
) -> None:
    """A real persisted legacy leaf becomes one enum value and is removed."""

    manager = _manager(tmp_path, "persisted")
    with manager._lock:
        manager._settings.remove(RESAMPLE_FILTER_KEY)
        manager._settings.setValue(LEGACY_USE_LANCZOS_KEY, legacy_value)
        manager._settings.sync()

    reloaded = SettingsManager(
        organization=manager.get_organization_name(),
        application=manager.get_application_name(),
        storage_base_dir=tmp_path / "persisted",
    )

    assert reloaded.get(RESAMPLE_FILTER_KEY) == expected
    assert reloaded._settings.contains(LEGACY_USE_LANCZOS_KEY) is False
    with pytest.raises(KeyError, match="Retired setting key"):
        reloaded.get(LEGACY_USE_LANCZOS_KEY)


def test_existing_current_resample_filter_wins_over_retired_bool(tmp_path) -> None:
    """Migration must not overwrite an explicit current user choice."""

    manager = _manager(tmp_path, "current_wins")
    with manager._lock:
        manager._settings.setValue(RESAMPLE_FILTER_KEY, "hamming")
        manager._settings.setValue(LEGACY_USE_LANCZOS_KEY, True)
        manager._settings.sync()

    reloaded = SettingsManager(
        organization=manager.get_organization_name(),
        application=manager.get_application_name(),
        storage_base_dir=tmp_path / "current_wins",
    )

    assert reloaded.get(RESAMPLE_FILTER_KEY) == "hamming"
    assert reloaded._settings.contains(LEGACY_USE_LANCZOS_KEY) is False


def test_invalid_resample_filter_repairs_to_canonical_smooth(tmp_path) -> None:
    """Only the three current enum strings may survive persistence."""

    manager = _manager(tmp_path, "invalid")
    with manager._lock:
        manager._settings.setValue(RESAMPLE_FILTER_KEY, "bicubic")
        manager._settings.sync()

    reloaded = SettingsManager(
        organization=manager.get_organization_name(),
        application=manager.get_application_name(),
        storage_base_dir=tmp_path / "invalid",
    )

    canonical = require_canonical_default(RESAMPLE_FILTER_KEY)
    assert canonical in RESAMPLE_FILTERS
    assert reloaded.get(RESAMPLE_FILTER_KEY) == canonical
    assert normalize_resample_filter("Lanczos") == "lanczos"
    assert normalize_resample_filter("bicubic") == canonical


def test_sst_import_promotes_legacy_filter_and_current_enum_wins(tmp_path) -> None:
    """SST uses the same input migration seam as profile startup."""

    manager = _manager(tmp_path, "sst")
    snapshot = tmp_path / "legacy_filter.sst"
    snapshot.write_text(
        json.dumps(
            {
                "snapshot": {
                    "display": {
                        "use_lanczos": True,
                        "resample_filter": "hamming",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    assert import_from_sst(manager, str(snapshot), merge=True) is True
    assert manager.get(RESAMPLE_FILTER_KEY) == "hamming"
    assert manager._settings.contains(LEGACY_USE_LANCZOS_KEY) is False
