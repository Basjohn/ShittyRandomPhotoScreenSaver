"""CLI overrides must survive the same curated/Custom activation used by the live owner."""
import json
import pytest
from tools.visualizer_live_check import _prepare_profile, parse_display_off
from core.settings.visualizer_presets import resolve_visualizer_activation_payload


def test_display_off_schedule_is_sorted_pairs_and_rejects_overlap_or_nonpositive_times():
    assert parse_display_off("50:10,20:5") == [(20.0, 25.0), (50.0, 60.0)]
    for bad in ("20:0", "0:5", "20:10,25:5", "x:1"):
        with pytest.raises(ValueError):
            parse_display_off(bad)


def test_isolated_profile_overrides_survive_curated_activation_without_editing_presets(tmp_path):
    appdata=tmp_path/'source'
    (appdata/'SRPSS').mkdir(parents=True)
    (appdata/'SRPSS_MC').mkdir()
    source=appdata/'SRPSS_MC/settings_v2.json'
    before=json.dumps({'snapshot':{'widgets':{'spotify_visualizer':{'mode':'waveform_ribbon','preset_waveform_ribbon':0}}}})
    source.write_text(before)
    overrides={'waveform_ribbon_mist_enabled':False,'waveform_ribbon_input_gain':.37}
    root=_prepare_profile(tmp_path/'run','waveform_ribbon',1,overrides,appdata_root=appdata)
    raw=json.loads((root/'SRPSS_MC/settings_v2.json').read_text())['snapshot']['widgets']['spotify_visualizer']
    activation=resolve_visualizer_activation_payload(raw,mode='waveform_ribbon')
    assert activation.is_custom
    assert {key:activation.resolved_config[key] for key in overrides}==overrides
    assert source.read_text()==before


def test_observation_reads_the_applied_worker_instead_of_requested_settings(qt_app):
    from tests.test_waveform_ribbon_source_policy import configured
    from tools.eb_live_phases import waveform_worker_configuration
    engine=configured()
    try:
        engine.set_input_gain(.37)
        engine.set_floor_config(False,.12)
        engine._audio_worker.set_audio_block_size(256)
        actual=waveform_worker_configuration(engine)
        assert actual['waveform_ribbon_input_gain']==.37
        assert actual['waveform_ribbon_dynamic_floor'] is False
        assert actual['waveform_ribbon_manual_floor']==.12
        assert actual['waveform_ribbon_audio_block_size']==256
    finally:engine.force_stop()
