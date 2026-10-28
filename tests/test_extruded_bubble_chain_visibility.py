"""Logical free-chain visibility; shared music/motion must remain independent."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from widgets.spotify_visualizer.extruded_bubble_simulation import (
    ExtrudedBubbleControls, ExtrudedBubbleSimulation, MusicInput, idle_activity,
)


def test_resume_visibility_has_own_attack_and_preserves_existing_release():
    sim = ExtrudedBubbleSimulation(28)
    controls = ExtrudedBubbleControls(large_count=(0, 0), mid_count=(0, 0))
    dt = 1 / 60
    for cycle in range(3):
        frames = [sim.advance(MusicInput(dt, True, .8, (), (.8, .5, .3)), controls)
                  for _ in range(300)]
        assert frames[1].level > .1  # capture/music is already warm
        assert frames[1].chain_activity < .12
        assert .45 < frames[14].chain_activity < .6
        assert frames[-1].chain_activity > .98
        assert all(a.chain_activity <= b.chain_activity for a, b in zip(frames, frames[1:]))
        released = [sim.advance(MusicInput(dt, False, 0., (), (0.,) * 3), controls)
                    for _ in range(240)]
        assert [s.chain_activity for s in released] == pytest.approx(
            [idle_activity(s.level) for s in released])
        assert released[-1].chain_activity < .0001


def test_visibility_history_cannot_change_audio_motion_or_physical_records():
    a, b = ExtrudedBubbleSimulation(29), ExtrudedBubbleSimulation(29)
    controls = ExtrudedBubbleControls(collision_scope="off")
    for index in range(120):
        b._chain_activity = 0.0
        music = MusicInput(1 / 60, True, .6, (), (.6, .3, .2))
        left, right = a.advance(music, controls), b.advance(music, controls)
        assert replace(left, chain_activity=0.) == replace(right, chain_activity=0.)


def test_pause_during_fade_in_never_brightens_and_short_toggles_remain_gentle():
    sim = ExtrudedBubbleSimulation(30)
    controls = ExtrudedBubbleControls(large_count=(0, 0), mid_count=(0, 0))
    for cycle in range(4):
        for _ in range(8):
            active = sim.advance(MusicInput(1/60, True, .8, (), (.8, .5, .3)), controls)
        assert active.chain_activity < .4
        previous = active.chain_activity
        for _ in range(120):
            paused = sim.advance(MusicInput(1/60, False, 0., (), (0.,)*3), controls)
            assert paused.chain_activity <= previous
            previous = paused.chain_activity


def test_recorded_warm_resume_projects_visibility_through_production_snapshot(qt_app):
    from tools.visualizer_replay.driver import replay_clip
    from tools.visualizer_replay.pcm_reanalysis import reanalyzed_bubble_bands
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    from widgets.spotify_visualizer.feature_frame import FeatureClip, FeatureFrame
    path = Path(__file__).resolve().parents[1] / 'logs/visualizer_recordings/dontyouseemetrying_mixed.jsonl'
    if not path.is_file():
        pytest.skip('local PCM recording required; no synthetic music substitute')
    frames = []
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            frame = FeatureFrame.from_dict(json.loads(line))
            t = (frame.timestamp_us - (frames[0].timestamp_us if frames else frame.timestamp_us)) / 1e6
            if t > 9:
                break
            frames.append(replace(frame, playing=not 2 <= t < 6))
    settings = {**frozen_visualizer_settings('extruded_bubble'),
                'extruded_bubble_large_bubbles': (0, 0), 'extruded_bubble_mid_bubbles': (0, 0)}
    with reanalyzed_bubble_bands():
        result = replay_clip(FeatureClip('recorded_warm_resume', tuple(frames)), 'extruded_bubble',
                             settings=settings, snapshots_at=(len(frames)-1,))
    rows = [((frame.timestamp_us-frames[0].timestamp_us)/1e6, logical.mode_state)
            for frame, logical in zip(frames, result['logical_series'])]
    value = lambda t: min(rows, key=lambda row: abs(row[0]-t))[1]
    assert value(5.9).chain_activity < .001
    assert .1 < value(6.5).chain_activity < .7
    assert value(6.5).chain_activity < idle_activity(value(6.5).level)
    assert value(8).chain_activity > .98
    assert result['snapshots'][len(frames)-1].logical.mode_state.chain_activity == rows[-1][1].chain_activity
