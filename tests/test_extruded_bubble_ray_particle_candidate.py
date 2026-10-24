"""Qt-free recovery gates only, NOT acceptance for light/particle response.

Run: py -3.14 tests/test_extruded_bubble_ray_particle_candidate.py
"""
from __future__ import annotations

from pathlib import Path
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.visualizer_replay.eb_simulation_support import simulation_module


def test_rays_follow_phrase_changes_during_continuous_playback():
    m = simulation_module()
    sim = m.ExtrudedBubbleSimulation(300)
    c = m.ExtrudedBubbleControls(large_count=(1,1), mid_count=(1,1), collision_scope="off")
    readings = {}
    # Each phrase carries its own passage level (the engine's PassageIntensity) with its bands.
    for name, bands, passage in (
        ("soft", (.10,.10,.10), .2), ("loud", (.72,.65,.58), .85),
        ("mid", (.46,.48,.33), .55), ("faster", (.85,.89,.70), 1.),
        ("release", (.32,.23,.15), .35),
    ):
        values=[]
        for i in range(180):
            # Onsets are discrete; do NOT stop/restart playback across phrases.
            onsets = (("snare", .7),) if i % 45 == 0 else ()
            snap=sim.advance(m.MusicInput(1/90, True, passage, onsets, bands), c)
            values.append(snap.rays)
        readings[name]=values
    assert readings['loud'][50] > readings['soft'][-1] + .2
    assert readings['faster'][50] > readings['mid'][-1] + .2
    assert readings['mid'][-1] < readings['loud'][-1] - .12
    assert readings['release'][-1] < readings['faster'][-1] - .15
    for values in readings.values():
        assert all(0 <= v < 1 for v in values)
        assert max(abs(b-a) for a,b in zip(values,values[1:])) < .030
    # A soft passage sits near the quiet handle (beats once lifted every passage to mid-range).
    assert readings['soft'][-1] < .15


def test_particle_world_path_wired_in_shader_and_renderer():
    shader=(ROOT/'rendering/gl_programs/extruded_bubble_program.py').read_text()
    render=(ROOT/'rendering/quick/visualizer/implementations/extruded_bubble.py').read_text()
    defaults=(ROOT/'core/settings/default_settings.py').read_text()
    spec=(ROOT/'core/settings/visualizer_mode_settings.py').read_text()
    assert 'uSpeckSource' in shader and 'uSpeckEnd' in shader
    assert 'smoothstep(0.82, 1.0, progress)' in shader
    assert 'mix(uSpeckSource, uSpeckEnd, progress)' in shader
    assert '"uSpeckSource": stream_source, "uSpeckEnd": stream_end' in render
    assert '"uStreamSource": stream_source, "uStreamEnd": stream_end' in render
    assert 'stream_source = _floats(world_point(stream_path[:3]))' in render
    assert 'stream_end = _floats(world_point(stream_path[3:]))' in render
    assert '_SPECK_CARRY = 5.0 / WORLD_UNIT, 8.0 / WORLD_UNIT, 0.30' in render
    assert "'extruded_bubble_particle_glow_reactivity': 0.0" in defaults
    assert 'Slider("extruded_bubble_particle_glow_reactivity"' in spec


if __name__ == '__main__':
    test_rays_follow_phrase_changes_during_continuous_playback()
    test_particle_world_path_wired_in_shader_and_renderer()
    print('RAY_PARTICLE_CANDIDATE: 2 Qt-free gates passed; unaccepted native visuals')
