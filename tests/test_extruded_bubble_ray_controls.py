"""Ray brightness endpoints, independent shimmer and forward-only authored migration."""
import pytest
from rendering.gl_programs.extruded_bubble_scene import ray_strength, ray_motion
from tests._visualizer_frozen_settings import frozen_visualizer_settings
from core.settings.visualizer_settings_contract import migrate_extruded_bubble_ray_controls


@pytest.mark.parametrize('span', ((0.,1.),(.3,.8),(.4,.4),(0.,0.)))
def test_ray_modulation_zero_is_steady_upper_and_full_response_has_honest_floor(span):
    p={**frozen_visualizer_settings('extruded_bubble'), 'extruded_bubble_rays_enabled':True,
       'extruded_bubble_rays':span}
    for drive in (0.,.01,.1,.5,1.):
        assert ray_strength({**p,'extruded_bubble_ray_modulation':0.},drive)==pytest.approx(span[1])
        assert ray_strength({**p,'extruded_bubble_ray_modulation':1.},drive)==pytest.approx(
            span[0]+(span[1]-span[0])*drive)
        assert ray_strength({**p,'extruded_bubble_ray_modulation':.5},drive)==pytest.approx(
            (span[1]+span[0]+(span[1]-span[0])*drive)/2)


@pytest.mark.parametrize('scope', ('','widgets.spotify_visualizer.'))
def test_old_cosmetic_value_is_migrated_without_becoming_modulation(scope):
    old=scope+'extruded_bubble_ray_flicker';new=scope+'extruded_bubble_ray_shimmer'
    result=migrate_extruded_bubble_ray_controls({old:.72})
    assert result=={new:.72}
    assert migrate_extruded_bubble_ray_controls({old:.72,new:.13})=={new:.13}
    assert migrate_extruded_bubble_ray_controls(result)==result


def test_model_snapshot_and_preset_inputs_share_migration():
    from core.settings.models import SpotifyVisualizerSettings
    from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping
    from core.settings.visualizer_presets import _migrate_preset_settings
    raw={'extruded_bubble_ray_flicker':.72}
    model=SpotifyVisualizerSettings.from_mapping(raw,apply_preset_overlay=False)
    assert model.extruded_bubble_ray_shimmer==.72
    assert model.extruded_bubble_ray_modulation==1.
    assert normalize_visualizer_section_mapping(raw)['extruded_bubble_ray_shimmer']==.72
    assert _migrate_preset_settings('extruded_bubble',raw)=={'extruded_bubble_ray_shimmer':.72}


def test_held_energy_keeps_rays_open_and_releases_without_requiring_new_onsets():
    from widgets.spotify_visualizer.extruded_bubble_simulation import (
        ExtrudedBubbleSimulation, ExtrudedBubbleControls, MusicInput,
    )
    sim=ExtrudedBubbleSimulation(285)
    controls=ExtrudedBubbleControls(large_count=(0,0),mid_count=(0,0))
    def hold(intensity,bands,count):
        return [sim.advance(MusicInput(1/60,True,intensity,(),bands),controls) for _ in range(count)]
    hold(.03,(.02,.01,.01),600)  # same activation: exercise the old learned-reference overshoot/drop
    held=hold(.6,(.7,.5,.3),600)
    assert held[120].rays > .35
    assert all(b.rays >= a.rays-1e-10 for a,b in zip(held,held[1:]))
    assert abs(held[180].rays-held[-1].rays)<.005
    assert min(s.rays for s in held[120:])>.35
    quiet=hold(.05,(.03,.02,.01),600)
    assert quiet[-1].rays<held[-1].rays*.15
    again=hold(.6,(.7,.5,.3),600)
    assert again[-1].rays==pytest.approx(held[-1].rays,abs=.001)


def test_persisted_schema_migrates_before_default_fill_and_preserves_custom_cache(qt_app,tmp_path):
    from core.settings.settings_manager import SettingsManager
    from core.settings.visualizer_presets import get_custom_preset_index
    manager=SettingsManager(organization='EBRayMigrationTest',application='isolated',storage_base_dir=tmp_path)
    raw={'mode':'extruded_bubble','preset_extruded_bubble':get_custom_preset_index('extruded_bubble'),
         'extruded_bubble_ray_flicker':.72,'extruded_bubble_rays':[.17,.81]}
    manager._settings.setValue('widgets',{'spotify_visualizer':raw})
    manager._settings.setValue('visualizer_custom_presets',{'extruded_bubble':raw})
    manager._settings.update_metadata(visualizer_schema_version=12)
    assert manager.flush(timeout=5.)
    reloaded=SettingsManager(organization='EBRayMigrationTest',application='isolated',storage_base_dir=tmp_path)
    for result in (reloaded.get('widgets.spotify_visualizer'),
                   reloaded.get('visualizer_custom_presets')['extruded_bubble']):
        assert result['extruded_bubble_ray_shimmer']==.72
        assert result['extruded_bubble_rays']==[.17,.81]
        assert 'extruded_bubble_ray_flicker' not in result
    assert reloaded.get('widgets.spotify_visualizer.extruded_bubble_ray_modulation')==1.
    assert reloaded.flush(timeout=5.)
