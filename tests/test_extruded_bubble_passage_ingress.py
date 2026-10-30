"""EB passage and zero-minimum motion use the actual body feed at logical ingress.

Recorded PCM gates are local evidence; native capture cadence and operator acceptance
remain separate. The shared historical loudness must never supply EB passage.
"""
from dataclasses import replace
import json
from pathlib import Path
from statistics import median
from unittest.mock import patch

import numpy as np
import pytest

from tests._visualizer_frozen_settings import frozen_visualizer_settings
from tools.visualizer_replay.driver import replay_clip
from tools.visualizer_replay.engine import ReplayBeatEngine
from tools.visualizer_replay.pcm_reanalysis import reanalyzed_bubble_bands
from widgets.spotify_visualizer.extruded_bubble_frame_runtime import passage_intensity_from_body_bands
from widgets.spotify_visualizer.feature_frame import FeatureClip, FeatureFrame


def test_fixed_body_passage_anchors_have_no_dead_band_or_learned_reference():
    for body, expected in ((0., 0.), (.25, .378929), (.5, .615572), (.8, .855388), (1., 1.)):
        assert passage_intensity_from_body_bands((body,) * 3) == pytest.approx(expected, abs=1e-6)
    assert passage_intensity_from_body_bands((.001,) * 3) > 0.
    assert passage_intensity_from_body_bands((1., 0., 0.)) == pytest.approx(.46 ** .7)


@pytest.fixture(scope='module')
def scaled_recording():
    path = Path(__file__).resolve().parents[1] / 'logs/visualizer_recordings/dontyouseemetrying_mixed.jsonl'
    if not path.is_file():
        pytest.skip('local recorded PCM required for production passage ingress gate')
    source = []
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            frame = FeatureFrame.from_dict(json.loads(line))
            if source and frame.timestamp_us - source[0].timestamp_us >= 4_000_000:
                break
            source.append(frame)
    origin = source[0].timestamp_us
    # Repeat the same actual PCM phrase at quiet/loud/quiet levels. Remove recorded
    # onsets: passage must respond without relying on an old recorded accent lane.
    output = []
    for segment, gain in enumerate((.02, 4., .02, .02)):
        for frame in source:
            history = frame.capture_history
            assert history is not None
            pcm = np.frombuffer(history.pcm_f32le, dtype='<f4') * gain
            output.append(replace(frame,
                timestamp_us=origin + segment * 4_000_000 + frame.timestamp_us - origin,
                capture_history=replace(history, pcm_f32le=pcm.astype('<f4').tobytes(),
                                        capture_serial=history.capture_serial + segment * 1_000_000),
                real=replace(frame.real, onsets=(), events=())))
    return FeatureClip('actual_pcm_quiet_loud_quiet', tuple(output))


def test_non_pcm_replay_uses_same_body_passage_authority_without_historical_scalar(scaled_recording):
    settings = {**frozen_visualizer_settings('extruded_bubble'),
        'extruded_bubble_large_bubbles': [0., 0.], 'extruded_bubble_mid_bubbles': [0., 0.],
        'extruded_bubble_bead_chains': [0., 0.], 'extruded_bubble_particles': [0., 0.]}
    clip = FeatureClip('recorded_body_seam', scaled_recording.frames[:30])
    with patch.object(ReplayBeatEngine, 'get_musical_intensity',
                      side_effect=AssertionError('historical intensity reached EB')):
        frames = replay_clip(clip, 'extruded_bubble', settings=settings)['logical_series']
    assert any(frame.mode_state.passage > 0. for frame in frames)


@pytest.mark.parametrize('block', (256, 512, 1024))
def test_live_equivalent_pcm_drives_zero_minimum_ranges_and_releases_without_shared_scalar(scaled_recording, block):
    settings = {**frozen_visualizer_settings('extruded_bubble'),
        'extruded_bubble_audio_block_size': block,
        'extruded_bubble_large_bubbles': [1, 1], 'extruded_bubble_mid_bubbles': [1, 1],
        'extruded_bubble_collision_scope': 'Off', 'extruded_bubble_drift': [0., 1.],
        'extruded_bubble_drift_chains': [0., .5], 'extruded_bubble_bead_chains': [1., 1.],
        'extruded_bubble_particles': [0., 0.], 'extruded_bubble_sway': 0.}
    with reanalyzed_bubble_bands(), patch.object(ReplayBeatEngine, 'get_musical_intensity',
            side_effect=AssertionError('shared historical intensity reached EB')):
        frames = replay_clip(scaled_recording, 'extruded_bubble', settings=settings)['logical_series']
    origin = scaled_recording.frames[0].timestamp_us
    def window(start, stop, field):
        return median(getattr(frame.mode_state, field) for frame, feature in zip(frames, scaled_recording.frames)
                      if start <= (feature.timestamp_us - origin) / 1e6 < stop)
    for field, minimum_lift in (('passage', .35), ('drift', .30), ('stream_speed', .20)):
        quiet = window(3., 4., field)
        loud = window(7., 8., field)
        released = window(15., 16., field)
        assert loud > quiet + minimum_lift, (block, field, quiet, loud, released)
        assert released < quiet + .10, (block, field, quiet, loud, released)
    from widgets.spotify_visualizer.extruded_bubble_drift_log import MaterialDriftReference
    reference = MaterialDriftReference()
    active_paths = []
    for frame, feature in zip(frames, scaled_recording.frames):
        chains = reference.apply(frame.mode_state.drift_families, frame.mode_state.drift_steps).get('chains', b'')
        if 7. <= (feature.timestamp_us - origin) / 1e6 < 8. and chains:
            active_paths.append(np.frombuffer(chains, dtype='f4').reshape(-1, 4)[:, :3])
    assert active_paths and max(np.max(np.linalg.norm(paths, axis=-1)) for paths in active_paths) > .01
