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


def _population_opacities(fill):
    from widgets.spotify_visualizer.extruded_bubble_material_paths import chain_opacity
    return [chain_opacity(fill, chain) for chain in range(80)]


def test_beat_swing_at_the_population_edge_fades_a_free_chain_instead_of_blinking_it():
    """A steady passage with a 2 Hz beat: the chain at the fill's edge must not drop out and return (2026-10-31)."""
    from rendering.quick.visualizer.implementations.extruded_bubble import _procedural_fill, chain_drive
    from widgets.spotify_visualizer.extruded_bubble_material_paths import CHAIN_FADE_BAND, CHAIN_FADE_RATE
    chains = (2.0, 5.0)  # test-owned Range, not a preset's
    settings = {'scene3d_detail': 'High', 'extruded_bubble_bead_chains': chains}
    sim = ExtrudedBubbleSimulation(31)
    controls = ExtrudedBubbleControls(large_count=(0, 0), mid_count=(0, 0), bead_chains=chains)
    dt = 1 / 90
    rows = []
    for tick in range(int(20 / dt)):
        t = tick * dt
        bass = .95 if (t % .5) < .12 else .25           # kick on every beat, deep release between
        intensity = .6 if t < 10 else .4                  # one phrase change half way
        snap = sim.advance(MusicInput(dt, True, intensity, (), (bass, .3, .2)), controls)
        rows.append((t, _population_opacities(_procedural_fill(settings, chain_drive(snap), snap.emission)[0])))
    rows = rows[90:]  # the first second is activation
    shortest = CHAIN_FADE_BAND / CHAIN_FADE_RATE
    for chain in range(80):
        state, left, entered = None, None, None
        for t, opacity in rows:
            value = opacity[chain]
            now = 1 if value > .9 else 0 if value < .1 else None
            if now is None and entered is None and state is not None:
                entered = t
            if now is not None:
                if state is not None and now != state:
                    # A whole fade (on to off or back) takes at least most of the band at the capped rate.
                    assert t - entered >= .75 * shortest, (chain, t)
                    if now == 0:
                        left = t
                    else:
                        assert left is None or t - left >= 2.0, f'chain {chain} blinked off at {left:.2f}, back at {t:.2f}'
                state, entered = now, None
    for (_, before), (_, after) in zip(rows, rows[1:]):
        assert max(abs(a - b) for a, b in zip(before, after)) <= dt * CHAIN_FADE_RATE / CHAIN_FADE_BAND + 1e-6


def test_population_band_preserves_the_fill_and_draws_nothing_at_zero():
    from widgets.spotify_visualizer.extruded_bubble_material_paths import (
        chain_draw_count, chain_opacity, drawable_chains)
    chains = (2.0, 5.0)
    assert chain_draw_count(0.0, chains) == 0
    for fill in (.0, .3, 1., 1.7, 2.5, 7.25, 30., 41.6):
        opacities = [chain_opacity(fill, c) for c in range(drawable_chains(chains) + 8)]
        # Exact once the band is whole; below two chains of fill it narrows and stays within a twentieth of a chain.
        assert sum(opacities) == pytest.approx(fill, abs=1e-9 if fill >= 2 else .05)
        count = chain_draw_count(fill, chains)
        assert all(v == 0. for v in opacities[count:]) and (fill == 0 or opacities[count - 1] > 0)
    assert chain_draw_count(1e6, chains) == drawable_chains(chains)
