"""Tests for core.settings.visualizer_presets drop-in loading."""
from __future__ import annotations

import json

from core.settings import visualizer_presets as vp


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
    assert glow_burst.name == "Glow Burst"
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
