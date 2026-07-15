from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from core.settings.defaults import MC_PROFILE, NORMAL_PROFILE, get_profile_default_overrides
from core.settings.defaults_snapshot_builder import build_sst_defaults_snapshot
from tools import regenerate_sst_defaults as module


def _flatten_leaves(value: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    leaves: dict[str, Any] = {}
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(child, Mapping):
            leaves.update(_flatten_leaves(child, path))
        else:
            leaves[path] = child
    return leaves


def _load_outputs(root: Path) -> dict[str, dict[str, Any]]:
    outputs = module.regenerate_sst_defaults(root)
    assert all(path.parent == root and path.exists() for path in outputs)
    return {
        app_name: json.loads(path.read_text(encoding="utf-8"))
        for (app_name, _filename), path in zip(module.EXPORT_TARGETS, outputs)
    }


def test_sst_regeneration_is_byte_reproducible_and_profile_canonical(tmp_path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    first = _load_outputs(first_root)
    second = _load_outputs(second_root)

    for application, filename in module.EXPORT_TARGETS:
        first_bytes = (first_root / filename).read_bytes()
        second_bytes = (second_root / filename).read_bytes()
        assert first_bytes == second_bytes

        payload = first[application]
        assert payload == second[application]
        assert payload["application"] == application
        assert payload["profile"] == application
        assert payload["metadata"] == module.GENERATED_METADATA
        assert "migrated_at" not in payload["metadata"]
        assert "last_migration_completed" not in payload["metadata"]
        assert payload["snapshot"] == build_sst_defaults_snapshot(application)
        assert "latitude" not in payload["snapshot"]["widgets"]["weather"]
        assert "longitude" not in payload["snapshot"]["widgets"]["weather"]
        assert not module._walk_private_paths(payload["snapshot"])


def test_mc_sst_delta_is_exactly_the_canonical_profile_override(tmp_path) -> None:
    generated = _load_outputs(tmp_path / "docs")
    normal = _flatten_leaves(generated[NORMAL_PROFILE]["snapshot"])
    mc = _flatten_leaves(generated[MC_PROFILE]["snapshot"])
    actual_delta = {
        key for key in normal.keys() | mc.keys() if normal.get(key) != mc.get(key)
    }
    override_delta = set(
        _flatten_leaves(get_profile_default_overrides()[MC_PROFILE])
    )

    assert actual_delta == override_delta


def test_sst_regeneration_never_opens_or_rewrites_installed_settings(
    tmp_path,
    monkeypatch,
) -> None:
    from core.settings.settings_manager import SettingsManager

    installed_settings = tmp_path / "installed" / "settings_v2.json"
    installed_settings.parent.mkdir(parents=True)
    sentinel = b'{"installed": "must remain untouched"}\n'
    installed_settings.write_bytes(sentinel)

    def _forbid_manager_construction(*_args, **_kwargs):
        raise AssertionError("canonical SST generation must not construct SettingsManager")

    monkeypatch.setattr(SettingsManager, "__init__", _forbid_manager_construction)
    _load_outputs(tmp_path / "docs")

    assert installed_settings.read_bytes() == sentinel


@pytest.mark.parametrize("application", [NORMAL_PROFILE, MC_PROFILE])
def test_generated_sst_import_matches_fresh_profile_reset(
    application: str,
    tmp_path,
    monkeypatch,
) -> None:
    from core.settings.settings_manager import SettingsManager

    monkeypatch.setattr(
        SettingsManager,
        "_run_initial_migration",
        lambda *_args, **_kwargs: None,
    )
    generated = _load_outputs(tmp_path / "docs")[application]
    generated_path = tmp_path / f"{application}.sst"
    generated_path.write_text(
        json.dumps(generated, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    reference = SettingsManager(
        organization="SSTParityReference",
        application=application,
        storage_base_dir=tmp_path / "reference",
    )
    reference.reset_to_defaults()
    reference_export = tmp_path / f"{application}-reference.sst"
    assert reference.export_to_sst(str(reference_export)) is True

    imported = SettingsManager(
        organization="SSTParityImported",
        application=application,
        storage_base_dir=tmp_path / "imported",
    )
    # Canonical default artifacts use the normal overlay import path. Replace
    # mode intentionally omits retired display keys guarded by sst_io.
    assert imported.import_from_sst(str(generated_path), merge=True) is True
    imported_export = tmp_path / f"{application}-imported.sst"
    assert imported.export_to_sst(str(imported_export)) is True

    reference_snapshot = json.loads(reference_export.read_text(encoding="utf-8"))["snapshot"]
    imported_snapshot = json.loads(imported_export.read_text(encoding="utf-8"))["snapshot"]
    assert imported_snapshot == reference_snapshot


def test_sst_generation_rejects_private_credential_fields(monkeypatch) -> None:
    original_builder = module.build_sst_defaults_snapshot

    def _defaults_with_secret(application: str) -> dict[str, Any]:
        snapshot = original_builder(application)
        snapshot["widgets"]["steam"]["api_key"] = "must-not-export"
        return snapshot

    monkeypatch.setattr(module, "build_sst_defaults_snapshot", _defaults_with_secret)

    with pytest.raises(ValueError, match="private credential fields"):
        module._build_payload(NORMAL_PROFILE)
