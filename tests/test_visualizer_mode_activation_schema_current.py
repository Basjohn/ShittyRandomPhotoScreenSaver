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
    assert resolve_effective_enabled_modes(activation) == VISUALIZER_MODE_IDS


def test_boolean_map_preserves_registry_order_and_last_mode_guard_recovery() -> None:
    requested = _canonical_activation()
    requested["oscilloscope"] = False
    requested["bubble"] = False
    assert resolve_effective_enabled_modes(requested) == (
        "spectrum",
        "sine_wave",
        "devcurve",
        "sphere",
    )

    # Persisted all-off state cannot strand an active Visualizer family.
    all_off = {mode_id: False for mode_id in VISUALIZER_MODE_IDS}
    assert resolve_effective_enabled_modes(all_off) == VISUALIZER_MODE_IDS


def test_model_serializes_only_current_mode_activation_schema() -> None:
    model = SpotifyVisualizerSettings.from_mapping(
        {
            "mode_activation": build_visualizer_mode_activation(
                ("spectrum", "bubble", "sphere")
            )
        }
    )
    payload = model.to_dict()

    assert not any(key.endswith(".enabled_modes") for key in payload)
    assert payload["widgets.spotify_visualizer.mode_activation"] == {
        "spectrum": True,
        "oscilloscope": False,
        "sine_wave": False,
        "bubble": True,
        "devcurve": False,
        "sphere": True,
    }
    assert model.enabled_modes == ("spectrum", "bubble", "sphere")


def test_retired_enabled_modes_is_migrated_once_and_removed(caplog) -> None:
    with caplog.at_level("WARNING"):
        migrated = migrate_legacy_visualizer_mode_activation_schema(
            {
                "enabled_modes": ["spectrum", "bubble"],
                "mode": "bubble",
            }
        )

    assert "enabled_modes" not in migrated
    assert migrated["mode_activation"] == {
        "spectrum": True,
        "oscilloscope": False,
        "sine_wave": False,
        "bubble": True,
        "devcurve": False,
        "sphere": False,
    }
    assert "Retired enabled_modes was relied on" in caplog.text
