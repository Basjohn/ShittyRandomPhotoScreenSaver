"""Local real-recording gates through the production logical capture, not a scalar substitute.

Native pixel/motion and physical acceptance remain separate. Missing local recordings
are explicitly skipped; no synthetic clip is substituted or operator preset used as a golden.
"""
from dataclasses import replace
import json
from pathlib import Path
from statistics import median

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
    return [f.mode_state for f in replay_clip(clip, 'extruded_bubble', settings=settings(**overrides))['logical_series']]


def test_recorded_music_reaches_strong_contraction_and_expansion_in_both_populations(clip):
    by_id = {}
    for state in states(clip):
        for i in range(0, len(state.bubbles), 8):
            x, y, z, radius, alpha, swell, ident, cluster = state.bubbles[i:i+8]
            if alpha == 1 and cluster < 0 and ident <= 12:
                by_id.setdefault(int(ident), []).append(1 + swell)
    # IDs identify authored classes even when contraction/expansion crosses their old size thresholds.
    for low, high, max_rest in ((1, 4, .8), (5, 12, .6)):
        groups = [v for ident, v in by_id.items() if low <= ident <= high and len(v) >= 100]
        assert groups
        assert median(min(v) for v in groups) < max_rest
        assert median((max(v)-min(v))/min(v) for v in groups) > 1.0
    assert max(max(v) for ident, v in by_id.items() if ident <= 4) > 1.3


def test_sustained_control_changes_actual_recorded_production_output(clip):
    low, high = states(clip, extruded_bubble_sustained=0.), states(clip, extruded_bubble_sustained=1.)
    assert max(abs(a-b) for left, right in zip(low, high)
               for a, b in zip(left.bubbles[5::8], right.bubbles[5::8])) > .02


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
    state=states(held,extruded_bubble_stream_speed=(0.,0.),extruded_bubble_drift=(0.,0.),extruded_bubble_sway=0.)[-1]
    large=[1+state.bubbles[i+5] for i in range(0,len(state.bubbles),8) if state.bubbles[i+6]<=4]
    small=[1+state.bubbles[i+5] for i in range(0,len(state.bubbles),8) if 5<=state.bubbles[i+6]<=12]
    assert large and small
    assert median(small)<1.6  # sustained support, not near 3x inflation of every small bubble


def test_pause_releases_radius_and_every_motion_phase_into_slow_rest(clip):
    last = clip.frames[-1]
    paused = tuple(replace(last, timestamp_us=last.timestamp_us + (i+1)*11_000, playing=False)
                   for i in range(1500))
    combined = FeatureClip('real_music_then_pause', clip.frames + paused)
    result = states(combined)
    active, start, end = result[len(clip.frames)-1], result[len(clip.frames)], result[-1]
    assert active.stream_speed > end.stream_speed * 10
    assert active.emission > end.emission * 3
    assert end.emission > .02  # sparse visible rest survives downstream squared particle density
    assert active.rays > end.rays + .1
    assert start.stream_speed > active.stream_speed * .95  # no pause snap
    initial = dict(zip(active.bubbles[6::8], active.bubbles[5::8]))
    first = dict(zip(start.bubbles[6::8], start.bubbles[5::8]))
    assert all(1 + first[i] > .97 * (1 + v) for i, v in initial.items() if i in first)
    after_one_second = result[len(clip.frames) + 90]
    settling = dict(zip(after_one_second.bubbles[6::8], after_one_second.bubbles[5::8]))
    resting = dict(zip(end.bubbles[6::8], end.bubbles[5::8]))
    remaining = [(settling[i] - resting[i]) / (v - resting[i]) for i, v in initial.items()
                 if i in settling and i in resting and v - resting[i] > .05]
    assert remaining and min(remaining) > .25  # gradual, not instant collapse
    assert all(v < -.1 for v in end.bubbles[5::8])
    assert all(1 + v < .15 for v in end.bubbles[5::8])  # minimum size is independent of excursion
    before = result[-92]
    assert .04 < end.motion_phase - before.motion_phase < .08
    assert .04 < end.shimmer - before.shimmer < .08
    from widgets.spotify_visualizer.extruded_bubble_geometry import WORLD_UNIT
    assert 0 < end.travel - before.travel < .01 * WORLD_UNIT
