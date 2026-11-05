"""Orthographic retired 5 Nov 2026 (operator): Perspective is the only framed-camera projection.

The per-mode ``*_camera_projection`` choice no longer exists, so a saved ``Orthographic`` (or
``Perspective``) leaf is forward-stripped at every input seam and the scene renders through the one
Perspective camera. The rest of the authored camera (FOV, pose, position) is untouched.
"""
from __future__ import annotations

import gc
import uuid
from pathlib import Path

import pytest

from core.settings.visualizer_retired_modes import (
    _RETIRED_VISUALIZER_KEYS,
    strip_retired_visualizer_settings,
)

_PREFIX = "widgets.spotify_visualizer"
_KEYS = ("waveform_ribbon_camera_projection", "extruded_bubble_camera_projection")
_FOV = {"waveform_ribbon_camera_projection": "waveform_ribbon_camera_fov",
        "extruded_bubble_camera_projection": "extruded_bubble_camera_fov"}
# Arbitrary in-range authored lenses (never the shipped values).
_WITNESS_FOV = {"waveform_ribbon_camera_projection": 23.0, "extruded_bubble_camera_projection": 50.0}


@pytest.mark.parametrize("key", _KEYS)
def test_projection_control_default_and_typed_field_are_gone(key) -> None:
    from core.settings.default_contract import require_canonical_default
    from core.settings.models import SpotifyVisualizerSettings
    from core.settings.visualizer_mode_settings import spec_control

    assert key in _RETIRED_VISUALIZER_KEYS
    assert spec_control(key) is None
    assert key not in require_canonical_default(_PREFIX)
    model = SpotifyVisualizerSettings.from_mapping({key: "Orthographic"}, apply_preset_overlay=False)
    assert not hasattr(model, key)
    assert not any(name.endswith(key) for name in model.to_dict())
    # The FOV no longer depends on a projection condition.
    assert not spec_control(_FOV[key]).when


@pytest.mark.parametrize("key", _KEYS)
@pytest.mark.parametrize("saved", ("Orthographic", "Perspective"))
def test_section_and_dotted_input_drop_the_projection_leaf(key, saved) -> None:
    fov = _FOV[key]
    cleaned = strip_retired_visualizer_settings({key: saved, f"{_PREFIX}.{key}": saved, fov: 23.0})
    # Negative control: the neighbouring authored camera value survives unchanged.
    assert cleaned == {fov: 23.0}


@pytest.mark.parametrize("key", _KEYS)
def test_imported_preset_keeps_its_camera_and_loses_only_the_projection(key) -> None:
    from core.settings import visualizer_presets as vp

    mode = key.rsplit("_camera_projection", 1)[0]
    fov = _FOV[key]
    parsed = vp._parse_preset_payload(
        Path("preset_1_projection.json"),
        {"name": "Projection witness", "preset_index": 0, "settings": {key: "Orthographic", fov: _WITNESS_FOV[key]}},
        mode,
    )
    assert parsed is not None
    _, preset = parsed
    assert key not in preset.settings
    assert preset.settings[fov] == _WITNESS_FOV[key]


def test_persisted_orthographic_profile_resolves_to_perspective_and_cannot_resave(tmp_path) -> None:
    from core.settings import SettingsManager

    app = f"ProjectionRetired_{uuid.uuid4().hex}"
    first = SettingsManager(application=app, storage_base_dir=tmp_path)
    widgets = dict(first.get("widgets"))
    section = dict(widgets["spotify_visualizer"])
    for key in _KEYS:
        section[key] = "Orthographic"
    section[_FOV[_KEYS[0]]] = 23.0
    widgets["spotify_visualizer"] = section
    # Written below the manager's normalizing API, as an older build would have.
    first._settings.setValue("widgets", widgets)
    first._settings.sync()
    assert first._settings.value("widgets")["spotify_visualizer"][_KEYS[0]] == "Orthographic"
    del first
    gc.collect()

    reopened = SettingsManager(application=app, storage_base_dir=tmp_path)
    section = reopened.get("widgets")["spotify_visualizer"]
    for key in _KEYS:
        assert key not in section
    assert section[_FOV[_KEYS[0]]] == 23.0


def test_curated_presets_carry_no_projection() -> None:
    root = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes"
    for path in root.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "camera_projection" not in text, path
