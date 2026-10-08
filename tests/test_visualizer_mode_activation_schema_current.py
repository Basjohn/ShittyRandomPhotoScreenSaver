"""Current per-mode Visualizer dormancy schema contracts.

These tests are intentionally Qt-free.  Physical Settings toggle hydration still
belongs to the Windows/PySide gate, while the persisted schema and one-time
legacy migration can be proven directly here.
"""
from __future__ import annotations

from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.models._spotify_visualizer import SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    build_visualizer_mode_activation,
    get_visualizer_mode_descriptor,
    is_mode_active,
    resolve_effective_enabled_modes,
)
from core.settings.visualizer_settings_snapshot import (
    migrate_legacy_visualizer_mode_activation_schema,
)


def _canonical_activation() -> dict[str, bool]:
    return dict(DEFAULT_SETTINGS["widgets"]["spotify_visualizer"]["mode_activation"])


def test_canonical_visualizer_dormancy_is_explicit_boolean_map() -> None:
    section = DEFAULT_SETTINGS["widgets"]["spotify_visualizer"]
    activation = section["mode_activation"]

    assert "enabled_modes" not in section
    # Mapping insertion order is serialization detail, not mode-order authority.
    # The registry owns canonical UI/runtime order; persisted activation owns one
    # boolean leaf per registered id.
    assert set(activation) == set(VISUALIZER_MODE_IDS)
    assert len(activation) == len(VISUALIZER_MODE_IDS)
    assert all(type(value) is bool for value in activation.values())
    assert resolve_effective_enabled_modes(activation) == tuple(
        mode_id for mode_id in VISUALIZER_MODE_IDS if activation[mode_id]
    )


def test_boolean_map_preserves_registry_order_and_last_mode_guard_recovery() -> None:
    requested = _canonical_activation()
    requested["oscilloscope"] = False
    requested["bubble"] = False
    assert resolve_effective_enabled_modes(requested) == tuple(
        mode_id for mode_id in VISUALIZER_MODE_IDS if requested[mode_id]
    )

    # Persisted all-off state cannot strand an active Visualizer family.
    all_off = {mode_id: False for mode_id in VISUALIZER_MODE_IDS}
    assert resolve_effective_enabled_modes(all_off) == resolve_effective_enabled_modes(
        _canonical_activation()
    )



def test_sphere_is_a_standard_selectable_registry_mode() -> None:
    descriptor = get_visualizer_mode_descriptor("sphere")
    assert descriptor.display_name == "Voxel Sphere"
    assert descriptor.guided_setup_offered is True
    assert is_mode_active("sphere") is True

    activation = build_visualizer_mode_activation(("sphere",))
    assert activation["sphere"] is True
    assert resolve_effective_enabled_modes(activation) == ("sphere",)

def test_model_serializes_only_current_mode_activation_schema() -> None:
    selected = ("spectrum", "bubble", "sphere")
    model = SpotifyVisualizerSettings.from_mapping(
        {"mode_activation": build_visualizer_mode_activation(selected)}
    )
    payload = model.to_dict()

    assert not any(key.endswith(".enabled_modes") for key in payload)
    assert payload["widgets.spotify_visualizer.mode_activation"] == {
        mode_id: mode_id in selected for mode_id in VISUALIZER_MODE_IDS
    }
    assert model.enabled_modes == selected


def test_retired_enabled_modes_is_migrated_once_and_removed(caplog) -> None:
    with caplog.at_level("WARNING"):
        migrated = migrate_legacy_visualizer_mode_activation_schema(
            {
                "enabled_modes": ["spectrum", "bubble"],
                "mode": "bubble",
            }
        )

    assert "enabled_modes" not in migrated
    selected = {"spectrum", "bubble"}
    assert migrated["mode_activation"] == {
        mode_id: mode_id in selected for mode_id in VISUALIZER_MODE_IDS
    }
    assert "Retired enabled_modes was relied on" in caplog.text
