"""Tests for core.settings.visualizer_presets drop-in loading."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from core.settings import visualizer_presets as vp
from core.settings.settings_manager import SettingsManager
from core.settings import sst_io


def test_snapshot_presets_expand_slots_and_filter_settings(tmp_path, monkeypatch):
    """Snapshot presets expand slot count and drop invalid keys."""

    curated_root = tmp_path / "curated"
    snapshots_root = tmp_path / "snapshots"
    (curated_root / "sine_wave").mkdir(parents=True)
    snapshots_root.mkdir()

    monkeypatch.setattr(vp, "_presets_root", lambda: curated_root)
    monkeypatch.setattr(vp, "_snapshot_presets_root", lambda: snapshots_root)

    payload = {
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
    assert glow_burst.settings.get("rainbow_enabled") is True
    assert "blob_growth" not in glow_burst.settings

    # Update global registry temporarily to validate helper behavior
    original = vp._PRESETS.get("sine_wave")
    monkeypatch.setitem(vp._PRESETS, "sine_wave", presets)
    try:
        assert vp.get_custom_preset_index("sine_wave") == len(presets) - 1
    finally:
        if original is not None:
            monkeypatch.setitem(vp._PRESETS, "sine_wave", original)


def test_curated_bubble_preset_is_pre_filtered_and_tracks_gradient_direction():
    preset_path = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes" / "bubble" / "preset_3_sideway_swish.json"
    payload = json.loads(preset_path.read_text(encoding="utf-8"))
    sv = payload["snapshot"]["widgets"]["spotify_visualizer"]

    assert sv["mode"] == "bubble"
    assert sv["bubble_gradient_direction"] == "top"
    assert "bubble_specular_direction" in sv

    # Curated payloads should already be filtered to allowed keys for the mode
    filtered = vp._filter_settings_for_mode("bubble", sv)
    assert filtered == sv


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

    filtered = vp._filter_settings_for_mode("bubble", round_tripped)
    assert filtered == round_tripped


def test_all_curated_presets_have_unique_keys_and_filtered_settings():
    presets_root = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes"

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
            widgets = snapshot.get("widgets", {}) if isinstance(snapshot, dict) else {}
            sv = widgets.get("spotify_visualizer") if isinstance(widgets, dict) else None
            if not isinstance(sv, dict):
                continue

            assert sv.get("mode") == mode, f"{preset_path} must declare mode={mode}"
            filtered = vp._filter_settings_for_mode(mode, sv)
            assert filtered == sv, f"{preset_path} contains disallowed keys for mode {mode}"
