"""Local real-recording gates through the production logical capture, not a scalar substitute.

Native pixel/motion and physical acceptance remain separate. Missing local recordings
are explicitly skipped; no synthetic clip is substituted or operator preset used as a golden.
"""
from dataclasses import replace
import json
from pathlib import Path
from statistics import median
from unittest.mock import patch

import pytest

from tests._visualizer_frozen_settings import frozen_visualizer_settings
from tools.visualizer_replay.driver import replay_clip
from widgets.spotify_visualizer.feature_frame import FeatureClip, FeatureFrame

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def clip():
    path = ROOT / 'logs/visualizer_recordings/anything_mixed2.jsonl'
    if not path.is_file():
        pytest.skip('local real-music recording anything_mixed2.jsonl is required for this gate')
    frames = []
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            frame = FeatureFrame.from_dict(json.loads(line))
            if frames and frame.timestamp_us - frames[0].timestamp_us > 8_000_000:
                break
            frames.append(frame)
    return FeatureClip('anything_real_response', tuple(frames))


def settings(**overrides):
    return {**frozen_visualizer_settings('extruded_bubble'),
            'extruded_bubble_large_bubbles': (4, 4), 'extruded_bubble_mid_bubbles': (8, 8),
            'extruded_bubble_breathing': (0.15, 0.6), 'extruded_bubble_small_pulse': (0.15, 0.8),
            'extruded_bubble_collision_scope': 'Off', **overrides}


def states(clip, **overrides):
    return states_and_kinds(clip, **overrides)[0]


def states_and_kinds(clip, **overrides):
    # Paced BEAM admission interleaves classes. ID ranges are not class metadata.
    from widgets.spotify_visualizer.extruded_bubble_simulation import ExtrudedBubbleSimulation
    original = ExtrudedBubbleSimulation._spawn
    kinds = {}
    def spawn(simulation, large, *args, **kwargs):
        admitted = original(simulation, large, *args, **kwargs)
        if admitted:
            kinds[simulation._bubbles[-1].ident] = large
        return admitted
    with patch.object(ExtrudedBubbleSimulation, '_spawn', spawn):
        series = replay_clip(clip,'extruded_bubble',settings=settings(**overrides))['logical_series']
    return [f.mode_state for f in series], kinds


def test_recorded_music_reaches_strong_contraction_and_expansion_in_both_populations(clip):
    by_id = {}
    series,kinds = states_and_kinds(clip)
    for state in series:
        for i in range(0, len(state.bubbles), 8):
            x, y, z, radius, alpha, swell, ident, cluster = state.bubbles[i:i+8]
            if alpha == 1 and cluster < 0:
                by_id.setdefault(int(ident), []).append(1 + swell)
    for large, max_rest in ((True,.8),(False,1.1)):
        groups = [v for ident,v in by_id.items() if kinds[ident] is large and len(v)>=100]
        assert groups
        assert median(min(v) for v in groups) < max_rest
        assert median((max(v)-min(v))/min(v) for v in groups) > 1.0
    assert max(max(v) for ident,v in by_id.items() if kinds[ident]) > 1.3


def test_sustained_control_changes_actual_recorded_production_output(clip):
    low, high = states(clip, extruded_bubble_sustained=0.), states(clip, extruded_bubble_sustained=1.)
    assert max(abs(a-b) for left, right in zip(low, high)
               for a, b in zip(left.bubbles[5::8], right.bubbles[5::8])) > .02


def test_active_recorded_phrase_has_large_absolute_excursion_in_each_class(clip):
    # A tiny initial rest can make percentages impressive while 4-8s music remains
    # almost static. Compare mature SAME IDs strictly inside that active phrase.
    by_id={}
    source,kinds=states_and_kinds(clip)
    for feature,state in zip(clip.frames,source,strict=True):
        at=(feature.timestamp_us-clip.frames[0].timestamp_us)/1e6
        if not 4.<=at<=8.:
            continue
        for i in range(0,len(state.bubbles),8):
            if state.bubbles[i+4]>.999 and state.bubbles[i+7]<0:
                by_id.setdefault(int(state.bubbles[i+6]),[]).append(1+state.bubbles[i+5])
    for large in (True,False):
        spans=[max(v)-min(v) for ident,v in by_id.items() if kinds[ident] is large and len(v)>200]
        assert spans and median(spans)>1.8


def test_held_real_hot_vocal_frame_keeps_the_small_population_distinct_from_large():
    path=ROOT/'logs/visualizer_recordings/cindarellaman_heavy2.jsonl'
    if not path.is_file():
        pytest.skip('local real heavy recording is required for the hot vocal hold gate')
    from tools.visualizer_replay.extruded_bubble_forensics import load_clip
    source=load_clip(path,10)
    peak=max(source.frames,key=lambda f:.7*f.energy.bubble.mid+.35*f.energy.bubble.high)
    quiet_events=replace(peak.real,onsets=(),events=())
    quiet_transient=replace(peak.energy.transient,bass=0.,mid=0.,high=0.,overall=0.,
                            onset_detected=False,onset_type='',onset_strength=0.)
    quiet_energy=replace(peak.energy,transient=quiet_transient)
    held=FeatureClip('held_actual_hot_vocal',tuple(replace(peak,timestamp_us=peak.timestamp_us+i*11000,
                                                        real=quiet_events,energy=quiet_energy)
                                                for i in range(1200)))
    series,kinds=states_and_kinds(held,extruded_bubble_stream_speed=(0.,0.),extruded_bubble_drift=(0.,0.),extruded_bubble_sway=0.)
    state=series[-1]
    large=[1+state.bubbles[i+5] for i in range(0,len(state.bubbles),8) if kinds[int(state.bubbles[i+6])]]
    small=[1+state.bubbles[i+5] for i in range(0,len(state.bubbles),8) if not kinds[int(state.bubbles[i+6])]]
    assert large and small
    assert median(small)<1.6  # sustained support, not near 3x inflation of every small bubble


def test_pause_releases_radius_and_every_motion_phase_into_slow_rest(clip):
    last = clip.frames[-1]
    paused = tuple(replace(last, timestamp_us=last.timestamp_us + (i+1)*11_000, playing=False)
                   for i in range(1500))
    combined = FeatureClip('real_music_then_pause', clip.frames + paused)
    result,kinds = states_and_kinds(combined)
    active, start, end = result[len(clip.frames)-1], result[len(clip.frames)], result[-1]
    assert active.stream_speed > end.stream_speed * 10
    assert active.emission > end.emission + .1
    assert end.emission == pytest.approx(settings()['extruded_bubble_particles'][0],abs=.002)
    assert end.emission > .02  # sparse visible rest survives downstream squared particle density
    assert active.rays > end.rays + .1
    assert start.stream_speed > active.stream_speed * .95  # no pause snap
    initial = dict(zip(active.bubbles[6::8], active.bubbles[5::8]))
    first = dict(zip(start.bubbles[6::8], start.bubbles[5::8]))
    # The recording may already be contracting rapidly when pause arrives.
    # Isolate pause from that existing motion rather than capping musical fall
    # at 3% per frame (which contradicts the within-song excursion gate).
    continued = states(FeatureClip('same_frame_without_pause',clip.frames+(
        replace(last,timestamp_us=last.timestamp_us+11_000),)))[-1]
    reference = dict(zip(continued.bubbles[6::8],continued.bubbles[5::8]))
    assert all(1 + first[i] > .97 * (1 + v) for i,v in reference.items() if i in first)
    after_one_second = result[len(clip.frames) + 90]
    settling = dict(zip(after_one_second.bubbles[6::8], after_one_second.bubbles[5::8]))
    resting = dict(zip(end.bubbles[6::8], end.bubbles[5::8]))
    remaining = [(settling[i] - resting[i]) / (v - resting[i]) for i, v in initial.items()
                 if i in settling and i in resting and v - resting[i] > .05]
    assert remaining and min(remaining) > .25  # gradual, not instant collapse
    assert all(v < -.1 for v in end.bubbles[5::8])
    for i in range(0,len(end.bubbles),8):
        assert 1+end.bubbles[i+5] == pytest.approx(.13 if kinds[int(end.bubbles[i+6])] else .7825,abs=.002)
    before = result[-92]
    assert .04 < end.motion_phase - before.motion_phase < .08
    assert .04 < end.shimmer - before.shimmer < .08
    from widgets.spotify_visualizer.extruded_bubble_geometry import WORLD_UNIT
    assert 0 < end.travel - before.travel < .01 * WORLD_UNIT
