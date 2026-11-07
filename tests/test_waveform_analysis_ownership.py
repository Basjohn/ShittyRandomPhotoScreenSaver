"""Waveform owns no sensitivity or noise-floor setting (retired 8 Nov 2026): nothing it reads sits behind them.

Waveform reads raw musical signals (``raw_musical_signals``): fixed-scale body bands and the transient bus's onsets,
level and intensity, all taken ahead of the sensitivity and noise-floor stage. Its Use Recommended Sensitivity,
Sensitivity, Dynamic Noise Floor and Noise Floor Baseline were owned but hidden (6 Nov); they are now retired:

* on recorded music re-analysed through the production DSP, the shared worker's sensitivity and floor (whatever they
  are while Waveform runs) leave Waveform's published frame bit-identical, while the post-floor lanes of the same
  replay move (negative control: the change reached the DSP) and Input Gain moves the frame (the comparison sees);
* no owner offers, stores or authors them: registry, spec, canonical defaults, model, Settings, Studio, curated presets;
* saved profiles and imported presets drop them at the input seam and keep their neighbours (negative control).

Test-owned values only; nothing shows a window.
"""
from __future__ import annotations

import gc
import uuid
from pathlib import Path

import pytest

MODE = "waveform_ribbon"
PREFIX = "widgets.spotify_visualizer"
RETIRED = tuple(f"{MODE}_{suffix}" for suffix in ("adaptive_sensitivity", "sensitivity", "dynamic_floor", "manual_floor"))
NEIGHBOUR = f"{MODE}_input_gain"            # an owned analysis setting beside them: it must survive every seam
WINDOW = {"clip": "growing_pains", "start": 7.5, "seconds": 4.0}      # the hot groove of a shipped Studio clip


# ----------------------------------------------------------------------------------------- what Waveform shows
@pytest.fixture(scope="module")
def audit(qt_app):
    from tools.visualizer_replay import analysis_controls_audit as module
    return module


def _worker(sensitivity=None, floor=None, lanes=None):
    """A ``replay`` prepare hook: sets the shared worker's sensitivity / floor, and records the post-floor lanes."""
    def prepare(engine):
        if sensitivity is not None:
            engine.set_sensitivity_config(*sensitivity)
        if floor is not None:
            engine.set_floor_config(*floor)
        if lanes is None:
            return
        accept = engine.accept_feature_frame

        def recorded(feature):
            accepted = accept(feature)
            worker = engine._audio_worker
            lanes.append((worker._pre_agc_live_bass, worker._pre_agc_live_mid, worker._pre_agc_live_treble))
            return accepted
        engine.accept_feature_frame = recorded
    return prepare


def test_the_workers_sensitivity_and_floor_never_move_what_waveform_shows(audit):
    clip = audit.load_clip(WINDOW["clip"], WINDOW["seconds"], WINDOW["start"])
    base_lanes: list = []
    base = audit.replay(MODE, clip, {}, prepare=_worker(lanes=base_lanes))
    assert any(frame["ready"] == (1.0,) for frame in base), "Waveform published live frames"
    assert not audit.difference(base, audit.replay(MODE, clip, {}))["moved"], "the replay is deterministic"
    # (Use Recommended, Sensitivity), (Dynamic Noise Floor, Noise Floor Baseline): test-owned, both toggles moved.
    for sensitivity, floor in (((False, 0.5), (False, 0.1)), ((False, 2.0), (True, 0.6)), ((False, 1.0), None)):
        lanes: list = []
        series = audit.replay(MODE, clip, {}, prepare=_worker(sensitivity, floor, lanes))
        assert lanes != base_lanes, f"negative control: {sensitivity}/{floor} reached the post-floor lanes"
        moved = audit.difference(base, series)
        assert not moved["moved"], f"{sensitivity}/{floor} moved Waveform: {sorted(moved['channels'])}"
    # Negative control: the comparison sees what Waveform does read (Input Gain scales every lane it hears).
    assert audit.difference(base, audit.replay(MODE, clip, {NEIGHBOUR: 1.6}))["moved"]


# ---------------------------------------------------------------------------------------------- the owners
def test_no_owner_offers_stores_or_authors_them():
    from core.settings.default_contract import require_canonical_default
    from core.settings.models import SpotifyVisualizerSettings
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys, get_visualizer_mode_descriptor
    from core.settings.visualizer_mode_settings import require_mode_settings, spec_control
    from core.settings.visualizer_retired_modes import _RETIRED_VISUALIZER_KEYS
    from ui.studio.technical import technical_properties

    owned = set(get_owned_mode_setting_keys(MODE, "technical").values())
    assert NEIGHBOUR in owned
    assert not get_visualizer_mode_descriptor(MODE).technical_hidden_suffixes, "nothing owned and hidden is left"
    defaults = require_canonical_default(PREFIX)
    model = SpotifyVisualizerSettings.from_mapping({key: 0.5 for key in RETIRED}, apply_preset_overlay=False)
    settings_keys = {control.key for control in require_mode_settings(MODE).technical_controls(offered=False)}
    studio_keys = set(technical_properties(MODE, workspace="reactivity"))
    assert settings_keys == owned and studio_keys == owned
    for key in RETIRED:
        assert key in _RETIRED_VISUALIZER_KEYS and key not in owned
        assert spec_control(key) is None
        assert key not in defaults
        assert not hasattr(model, key) and not any(name.endswith(key) for name in model.to_dict())
    root = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes" / MODE
    presets = sorted(root.glob("*.json"))
    assert presets
    for path in presets:
        text = path.read_text(encoding="utf-8")
        assert f'"{NEIGHBOUR}"' in text, path
        assert not [key for key in RETIRED if f'"{key}"' in text], path


# ------------------------------------------------------------------------------------------ the input seams
def test_section_dotted_and_preset_input_drop_them_and_keep_the_neighbour():
    from core.settings import visualizer_presets as vp
    from core.settings.visualizer_retired_modes import strip_retired_visualizer_settings

    stored = {**{key: 0.5 for key in RETIRED}, **{f"{PREFIX}.{key}": 0.5 for key in RETIRED}, NEIGHBOUR: 0.37}
    assert strip_retired_visualizer_settings(stored) == {NEIGHBOUR: 0.37}
    parsed = vp._parse_preset_payload(
        Path("preset_1_retired_analysis.json"),
        {"name": "Retired analysis witness", "preset_index": 0,
         "settings": {**{key: 0.5 for key in RETIRED}, NEIGHBOUR: 0.37}},
        MODE,
    )
    assert parsed is not None
    _, preset = parsed
    assert not set(RETIRED) & set(preset.settings)
    assert preset.settings[NEIGHBOUR] == pytest.approx(0.37)


def test_a_saved_profile_drops_them_on_load_and_keeps_its_input_gain(tmp_path):
    from core.settings import SettingsManager

    app = f"WaveformAnalysisRetired_{uuid.uuid4().hex}"
    first = SettingsManager(application=app, storage_base_dir=tmp_path)
    widgets = dict(first.get("widgets"))
    section = dict(widgets["spotify_visualizer"])
    section.update({key: 0.5 for key in RETIRED})
    section[NEIGHBOUR] = 0.37
    widgets["spotify_visualizer"] = section
    first._settings.setValue("widgets", widgets)            # below the normalizing API, as an older build wrote it
    first._settings.sync()
    assert first._settings.value("widgets")["spotify_visualizer"][RETIRED[0]] == 0.5
    del first
    gc.collect()

    reopened = SettingsManager(application=app, storage_base_dir=tmp_path)
    section = reopened.get("widgets")["spotify_visualizer"]
    assert not set(RETIRED) & set(section)
    assert section[NEIGHBOUR] == pytest.approx(0.37)
