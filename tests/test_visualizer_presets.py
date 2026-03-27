"""Tests for core.settings.visualizer_presets drop-in loading."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from core.settings import visualizer_presets as vp
from core.settings.settings_manager import SettingsManager
from core.settings import sst_io
from tools import visualizer_preset_repair as repair


def test_snapshot_presets_expand_slots_and_filter_settings(tmp_path, monkeypatch):
    """Snapshot presets expand slot count and drop invalid keys."""

    curated_root = tmp_path / "curated"
    snapshots_root = tmp_path / "snapshots"
    (curated_root / "sine_wave").mkdir(parents=True)
    snapshots_root.mkdir()

    monkeypatch.setattr(vp, "_presets_root", lambda: curated_root)
    monkeypatch.setattr(vp, "_snapshot_presets_root", lambda: snapshots_root)

    payload = {
        "visualizer_preset_override": True,
        "visualizer_preset_mode": "sine_wave",
        "preset_index": 4,
        "snapshot": {
            "widgets": {
                "spotify_visualizer": {
                    "mode": "sine_wave",
                    "sine_wave_effect": 0.42,
                    "rainbow_enabled": True,
                    "blob_growth": 5.0,
                },
                "clock": {"enabled": False},
            }
        }
    }
    (snapshots_root / "preset_5_glow_burst.json").write_text(json.dumps(payload), encoding="utf-8")

    presets = vp._build_presets_for_mode("sine_wave")

    assert len(presets) == 6  # 5 curated slots + Custom
    glow_burst = presets[4]
    assert glow_burst.name == "Preset 5 (Glow Burst)"
    assert glow_burst.settings.get("sine_wave_effect") == 0.42
    # rainbow_enabled migrated to the canonical mode-id scoped key.
    assert glow_burst.settings.get("sine_wave_rainbow_enabled") is True
    assert "rainbow_enabled" not in glow_burst.settings
    assert "blob_growth" not in glow_burst.settings

    # Update global registry temporarily to validate helper behavior
    original = vp._PRESETS.get("sine_wave")
    monkeypatch.setitem(vp._PRESETS, "sine_wave", presets)
    try:
        assert vp.get_custom_preset_index("sine_wave") == len(presets) - 1
    finally:
        if original is not None:
            monkeypatch.setitem(vp._PRESETS, "sine_wave", original)


def test_generic_sst_snapshot_does_not_override_curated_presets(tmp_path, monkeypatch):
    curated_root = tmp_path / "curated"
    snapshots_root = tmp_path / "snapshots"
    (curated_root / "spectrum").mkdir(parents=True)
    snapshots_root.mkdir()

    monkeypatch.setattr(vp, "_presets_root", lambda: curated_root)
    monkeypatch.setattr(vp, "_snapshot_presets_root", lambda: snapshots_root)

    generic_sst = {
        "snapshot": {
            "widgets": {
                "spotify_visualizer": {
                    "mode": "spectrum",
                    "spectrum_growth": 4.0,
                    "spectrum_bass_emphasis": 1.0,
                }
            }
        }
    }
    (snapshots_root / "preset_1_exported_profile.json").write_text(json.dumps(generic_sst), encoding="utf-8")

    presets = vp._build_presets_for_mode("spectrum")
    # No explicit override marker -> snapshot should be ignored.
    assert len(presets) == 4
    assert presets[0].settings == {}


def test_snapshot_override_fallback_without_marker(tmp_path, monkeypatch):
    curated_root = tmp_path / "curated"
    snapshots_root = tmp_path / "snapshots"
    (curated_root / "spectrum").mkdir(parents=True)
    snapshots_root.mkdir()

    monkeypatch.setattr(vp, "_presets_root", lambda: curated_root)
    monkeypatch.setattr(vp, "_snapshot_presets_root", lambda: snapshots_root)

    payload = {
        # No visualizer_preset_override / visualizer_preset_mode markers
        "preset_index": 2,
        "snapshot": {
            "widgets": {
                "spotify_visualizer": {
                    "mode": "spectrum",
                    "spectrum_growth": 6.0,
                    "spectrum_profile_floor": 0.2,
                }
            }
        }
    }
    (snapshots_root / "preset_3_markerless.json").write_text(json.dumps(payload), encoding="utf-8")

    presets = vp._build_presets_for_mode("spectrum")

    # Marker-less snapshots reuse the existing curated slot; they no longer grow
    # the preset count beyond the curated allocation.
    assert len(presets) == 4
    slot = presets[2]
    assert slot.settings["spectrum_growth"] == 6.0
    assert slot.settings["spectrum_profile_floor"] == 0.2


def test_curated_bubble_preset_is_pre_filtered_and_tracks_gradient_direction():
    preset_path = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes" / "bubble" / "preset_3_sideway_swish.json"
    payload = json.loads(preset_path.read_text(encoding="utf-8"))
    sv = payload["snapshot"]["widgets"]["spotify_visualizer"]

    assert sv["mode"] == "bubble"
    assert "bubble_gradient_direction" in sv
    assert "bubble_specular_direction" in sv

    # Curated payloads should already be filtered to allowed keys for the mode
    filtered = vp._filter_settings_for_mode("bubble", sv)
    assert filtered == sv


def test_snapshot_widgets_override_custom_backup(tmp_path, monkeypatch):
    curated_root = tmp_path / "curated"
    (curated_root / "spectrum").mkdir(parents=True)

    monkeypatch.setattr(vp, "_presets_root", lambda: curated_root)

    payload = {
        "mode": "spectrum",
        "preset_index": 1,
        "snapshot": {
            "custom_preset_backup": {
                "widgets.spotify_visualizer.spectrum_growth": 2.0,
                "widgets.spotify_visualizer.spectrum_profile_floor": 0.05,
            },
            "widgets": {
                "spotify_visualizer": {
                    "mode": "spectrum",
                    "spectrum_growth": 4.5,
                    "spectrum_profile_floor": 0.3,
                }
            },
        },
    }
    (curated_root / "spectrum" / "preset_2_custom_curve.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    presets = vp._build_presets_for_mode("spectrum")
    slot = presets[1]
    # snapshot.widgets should win over backup defaults
    assert slot.settings["spectrum_growth"] == 4.5
    assert slot.settings["spectrum_profile_floor"] == 0.3


def test_double_prefixed_mode_keys_are_normalized():
    migrated = vp._migrate_preset_settings(
        "blob",
        {
            "blob_blob_transient_mix_bass": 0.2,
            "blob_blob_transient_mix_vocal": 0.15,
        },
    )
    assert "blob_blob_transient_mix_bass" not in migrated
    assert "blob_blob_transient_mix_vocal" not in migrated
    assert migrated["blob_transient_mix_bass"] == 0.2
    assert migrated["blob_transient_mix_vocal"] == 0.15


def test_double_prefixed_alt_mode_keys_are_normalized():
    migrated = vp._migrate_preset_settings(
        "oscilloscope",
        {
            "oscilloscope_oscilloscope_transient_width_mix": 0.35,
        },
    )
    assert "oscilloscope_oscilloscope_transient_width_mix" not in migrated
    assert migrated["oscilloscope_transient_width_mix"] == 0.35


def test_sst_roundtrip_preserves_visualizer_mode_settings(tmp_path):
    def _make_manager(suffix: str) -> SettingsManager:
        base = tmp_path / suffix
        base.mkdir(parents=True, exist_ok=True)
        return SettingsManager(
            organization="Test",
            application=f"PresetAudit_{uuid.uuid4().hex}",
            storage_base_dir=base,
        )

    source_mgr = _make_manager("src")
    bubble_config = {
        "mode": "bubble",
        "monitor": "ALL",
        "adaptive_sensitivity": True,
        "bubble_specular_direction": "bottom_right",
        "bubble_gradient_direction": "left",
        "bubble_big_bass_pulse": 0.65,
        "bubble_small_freq_pulse": 0.35,
        "bubble_stream_direction": "up",
        "bubble_stream_constant_speed": 0.45,
    }
    source_mgr.set("widgets.spotify_visualizer", bubble_config)

    export_path = tmp_path / "snapshot_roundtrip.json"
    assert sst_io.export_to_sst(source_mgr, str(export_path))

    target_mgr = _make_manager("dst")
    assert sst_io.import_from_sst(target_mgr, str(export_path), merge=True)

    round_tripped = target_mgr.get("widgets.spotify_visualizer")
    assert round_tripped["bubble_gradient_direction"] == "left"
    assert round_tripped["bubble_specular_direction"] == "bottom_right"
    assert round_tripped["mode"] == "bubble"

    from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping

    assert round_tripped == normalize_visualizer_section_mapping(
        round_tripped,
        apply_preset_overlay=False,
    )

    filtered = vp._filter_settings_for_mode("bubble", round_tripped)
    assert filtered["bubble_gradient_direction"] == "left"
    assert filtered["bubble_specular_direction"] == "bottom_right"
    assert filtered["mode"] == "bubble"


def test_all_curated_presets_have_unique_keys_and_filtered_settings():
    presets_root = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes"
    known_modes = tuple(vp.MODES)

    def _load_json_no_dupes(path: Path):
        def _hook(pairs):
            container = {}
            for key, value in pairs:
                if key in container:
                    raise AssertionError(f"Duplicate JSON key '{key}' in {path}")
                container[key] = value
            return container

        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_hook)

    for mode_dir in sorted(presets_root.iterdir()):
        if not mode_dir.is_dir():
            continue
        mode = mode_dir.name
        for preset_path in sorted(mode_dir.glob("*.json")):
            payload = _load_json_no_dupes(preset_path)
            snapshot = payload.get("snapshot", {})
            assert isinstance(snapshot, dict), f"{preset_path} snapshot must be a dict"
            widgets = snapshot.get("widgets", {}) if isinstance(snapshot, dict) else {}
            sv = widgets.get("spotify_visualizer") if isinstance(widgets, dict) else None
            if not isinstance(sv, dict):
                continue

            bad_double_prefix = [
                key for key in sv
                if any(key.startswith(f"{mode_name}_{mode_name}_") for mode_name in known_modes)
            ]
            assert not bad_double_prefix, (
                f"{preset_path} contains duplicate-prefixed keys: {bad_double_prefix}"
            )

            assert sv.get("mode") == mode, f"{preset_path} must declare mode={mode}"
            filtered = vp._filter_settings_for_mode(mode, sv)
            assert filtered, f"{preset_path} filtered to an empty settings payload"
            for key, value in filtered.items():
                assert sv.get(key) == value, (
                    f"{preset_path} changed value for allowed key {key!r} during filtering"
                )


def test_repair_tool_payloads_are_marked_as_overrides(tmp_path):
    mode = "sine_wave"
    preset_path = tmp_path / "preset_5_sine.json"
    cleaned = {"sine_glow_intensity": 0.75, "mode": mode}
    payload = {"preset_index": 4, "snapshot": {}}

    lean, _ = repair._build_clean_payload(preset_path, payload, mode, cleaned)

    assert lean["visualizer_preset_override"] is True
    assert lean["visualizer_preset_mode"] == mode


def test_repair_tool_audit_flags_duplicate_prefixes_and_backup_blocks():
    payload = {
        "snapshot": {
            "custom_preset_backup": {
                "widgets.spotify_visualizer.blob_blob_transient_mix_bass": 0.5,
            },
            "widgets": {
                "spotify_visualizer": {
                    "mode": "blob",
                    "blob_blob_transient_mix_bass": 0.5,
                    "blob_energy_boost": 1.1,
                }
            },
        },
        "widgets": {
            "spotify_visualizer": {
                "mode": "blob",
            }
        },
    }

    report = repair.audit_payload("blob", payload)

    assert report["has_custom_preset_backup"] is True
    assert report["top_level_visualizer_duplication"] is True
    assert "blob_blob_transient_mix_bass" in report["duplicate_prefixed_keys"]
    assert "blob_energy_boost" in report["deprecated_authored_keys"]


def test_repair_tool_stops_emitting_deprecated_compat_tech_keys():
    payload = {
        "snapshot": {
            "widgets": {
                "spotify_visualizer": {
                    "mode": "blob",
                    "blob_color": "#ff00ff",
                }
            }
        }
    }

    cleaned, _stats = repair._sanitize_settings("blob", payload)

    assert "blob_energy_boost" not in cleaned
    assert "blob_use_raw_energy" not in cleaned


def test_repair_tool_backfills_direct_transient_keys_from_current_defaults():
    payload = {
        "snapshot": {
            "widgets": {
                "spotify_visualizer": {
                    "mode": "bubble",
                    "bubble_stream_reactivity": 0.45,
                }
            }
        }
    }

    cleaned, _stats = repair._sanitize_settings("bubble", payload)

    assert "bubble_transient_mix_bass" in cleaned
    assert "bubble_transient_mix_vocal" in cleaned
    assert "bubble_bubble_transient_mix_bass" not in cleaned
    assert "bubble_bubble_transient_mix_vocal" not in cleaned


def test_repair_tool_backfills_spectrum_glow_and_line_ghost_toggles():
    spectrum_payload = {
        "snapshot": {
            "widgets": {
                "spotify_visualizer": {
                    "mode": "spectrum",
                    "spectrum_growth": 2.7,
                }
            }
        }
    }
    spectrum_cleaned, _ = repair._sanitize_settings("spectrum", spectrum_payload)
    assert spectrum_cleaned["spectrum_glow_enabled"] is False
    assert spectrum_cleaned["spectrum_glow_intensity"] == pytest.approx(0.55)
    assert spectrum_cleaned["spectrum_glow_color"] == [110, 220, 255, 235]

    osc_payload = {
        "snapshot": {
            "widgets": {
                "spotify_visualizer": {
                    "mode": "oscilloscope",
                    "osc_line_count": 3,
                }
            }
        }
    }
    osc_cleaned, _ = repair._sanitize_settings("oscilloscope", osc_payload)
    assert osc_cleaned["osc_ghost_line2_enabled"] is True
    assert osc_cleaned["osc_ghost_line3_enabled"] is True


def test_reindex_curated_presets_fills_gaps_with_markerless_files(tmp_path, monkeypatch):
    root = tmp_path
    mode = "blob"
    mode_dir = root / "presets" / "visualizer_modes" / mode
    mode_dir.mkdir(parents=True)

    def _payload(name: str | None, preset_index: int | None, growth: float) -> dict:
        payload = {
            "description": "Test payload",
            "snapshot": {
                "widgets": {
                    "spotify_visualizer": {
                        "mode": mode,
                        "blob_growth": growth,
                    }
                }
            },
        }
        if name is not None:
            payload["name"] = name
        if preset_index is not None:
            payload["preset_index"] = preset_index
        return payload

    (mode_dir / "preset_1_alpha.json").write_text(
        json.dumps(_payload("Preset 1 (Alpha)", 0, 1.0)), encoding="utf-8"
    )
    (mode_dir / "preset_4_delta.json").write_text(
        json.dumps(_payload("Preset 4 (Delta)", 3, 4.0)), encoding="utf-8"
    )
    (mode_dir / "preset_5_echo.json").write_text(
        json.dumps(_payload("Preset 5 (Echo)", 4, 5.0)), encoding="utf-8"
    )
    (mode_dir / "preset_6_foxtrot.json").write_text(
        json.dumps(_payload("Preset 6 (Foxtrot)", 5, 6.0)), encoding="utf-8"
    )
    (mode_dir / "thunder.json").write_text(
        json.dumps(_payload("Thunder", None, 2.0)), encoding="utf-8"
    )

    monkeypatch.setattr(repair, "ROOT", root)

    results = repair.reindex_mode_presets(mode)

    assert len(results) == 5
    names = sorted(path.name for path in mode_dir.glob("*.json"))
    assert names == [
        "preset_1_alpha.json",
        "preset_2_thunder.json",
        "preset_3_delta.json",
        "preset_4_echo.json",
        "preset_5_foxtrot.json",
    ]

    thunder_payload = json.loads((mode_dir / "preset_2_thunder.json").read_text(encoding="utf-8"))
    assert thunder_payload["preset_index"] == 1
    assert thunder_payload["name"] == "Preset 2 (Thunder)"
    assert thunder_payload["snapshot"]["widgets"]["spotify_visualizer"]["blob_growth"] == 2.0

    delta_payload = json.loads((mode_dir / "preset_3_delta.json").read_text(encoding="utf-8"))
    assert delta_payload["preset_index"] == 2
    assert delta_payload["name"] == "Preset 3 (Delta)"
    assert delta_payload["snapshot"]["widgets"]["spotify_visualizer"]["blob_growth"] == 4.0


def test_reindex_curated_presets_normalizes_first_remaining_slot_to_preset_1(tmp_path, monkeypatch):
    root = tmp_path
    mode = "spectrum"
    mode_dir = root / "presets" / "visualizer_modes" / mode
    mode_dir.mkdir(parents=True)

    def _payload(name: str, preset_index: int, growth: float) -> dict:
        return {
            "name": name,
            "preset_index": preset_index,
            "snapshot": {
                "widgets": {
                    "spotify_visualizer": {
                        "mode": mode,
                        "spectrum_growth": growth,
                    }
                }
            },
        }

    (mode_dir / "preset_2_second.json").write_text(
        json.dumps(_payload("Preset 2 (Second)", 1, 2.0)), encoding="utf-8"
    )
    (mode_dir / "preset_3_third.json").write_text(
        json.dumps(_payload("Preset 3 (Third)", 2, 3.0)), encoding="utf-8"
    )

    monkeypatch.setattr(repair, "ROOT", root)

    results = repair.reindex_mode_presets(mode)

    assert len(results) == 2
    names = sorted(path.name for path in mode_dir.glob("*.json"))
    assert names == [
        "preset_1_second.json",
        "preset_2_third.json",
    ]

    second_payload = json.loads((mode_dir / "preset_1_second.json").read_text(encoding="utf-8"))
    assert second_payload["preset_index"] == 0
    assert second_payload["name"] == "Preset 1 (Second)"
    assert second_payload["snapshot"]["widgets"]["spotify_visualizer"]["spectrum_growth"] == 2.0


def test_primary_visualizer_modes_ship_at_least_one_curated_preset():
    presets_root = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes"
    required_modes = ("blob", "spectrum", "oscilloscope", "sine_wave")

    for mode in required_modes:
        mode_dir = presets_root / mode
        payloads = sorted(mode_dir.glob("*.json"))
        assert payloads, f"{mode} should ship at least one curated preset"

        first_slot = False
        for preset_path in payloads:
            payload = json.loads(preset_path.read_text(encoding="utf-8"))
            if payload.get("preset_index") == 0:
                first_slot = True
                break

        assert first_slot, f"{mode} should still ship a Preset 1 / slot 0 payload"


def test_curated_presets_have_unique_slot_numbers_per_mode():
    presets_root = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes"

    for mode_dir in sorted(presets_root.iterdir()):
        if not mode_dir.is_dir():
            continue

        seen = {}
        for preset_path in sorted(mode_dir.glob("*.json")):
            payload = json.loads(preset_path.read_text(encoding="utf-8"))
            preset_index = payload.get("preset_index")
            assert isinstance(preset_index, int), f"{preset_path} missing preset_index"
            if preset_index in seen:
                raise AssertionError(
                    f"{mode_dir.name} duplicate preset_index {preset_index}: "
                    f"{seen[preset_index].name} and {preset_path.name}"
                )
            seen[preset_index] = preset_path
