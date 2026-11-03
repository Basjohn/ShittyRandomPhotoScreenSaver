from __future__ import annotations

import pytest

from widgets.spotify_visualizer.bubble_ambient import BubbleAmbientSimulation, RECORD_STRIDE


def _settings(**overrides):
    base = {
        'bubble_microbubble_stream': True,
        'bubble_microbubble_drift': False,
        'bubble_microbubble_density': 0.2,
        'bubble_microbubble_size': 3.0,
        'bubble_microbubble_direction_mode': 'same',
        'bubble_microbubble_columnarity': 0.0,
        'bubble_particle_stream': True,
        'bubble_particle_drift': False,
        'bubble_particle_glow': True,
        'bubble_particle_density': 0.2,
        'bubble_particle_size': 2.4,
        'bubble_particle_direction_mode': 'same',
        'bubble_particle_color': [195, 226, 255, 210],
        'bubble_particle_glow_intensity': 0.9,
        'bubble_particle_glow_reactivity': 1.35,
        'bubble_stream_direction': 'up',
        'bubble_drift_direction': 'swish_horizontal',
        'bubble_drift_amount': 0.5,
        'bubble_drift_speed': 0.4,
        'bubble_drift_frequency': 0.3,
    }
    base.update(overrides)
    return base


def test_particle_glow_uses_breathing_signal_but_not_particle_size():
    sim_a = BubbleAmbientSimulation()
    quiet = sim_a.advance(0.016, _settings(), resolved_stream_velocity=0.18, small_bubble_breathing=0.0)
    sim_b = BubbleAmbientSimulation()
    loud = sim_b.advance(0.016, _settings(), resolved_stream_velocity=0.18, small_bubble_breathing=1.0)
    # First particle record follows the microbubble records.
    stride = RECORD_STRIDE
    first_particle = round(96 * 0.2) * stride
    assert quiet[first_particle + 2] == pytest.approx(loud[first_particle + 2])
    assert loud[first_particle + 4] > quiet[first_particle + 4]


def test_same_and_reversed_direction_modes_produce_opposite_motion():
    baseline = BubbleAmbientSimulation()
    initial = baseline.advance(0.0, _settings(), resolved_stream_velocity=0.18, small_bubble_breathing=0.0)
    x0, y0 = initial[0], initial[1]

    same = BubbleAmbientSimulation().advance(
        0.05, _settings(bubble_microbubble_direction_mode='same'),
        resolved_stream_velocity=0.18, small_bubble_breathing=0.0,
    )
    reversed_mode = BubbleAmbientSimulation().advance(
        0.05, _settings(bubble_microbubble_direction_mode='reversed'),
        resolved_stream_velocity=0.18, small_bubble_breathing=0.0,
    )
    dy_same = same[1] - y0
    dy_reversed = reversed_mode[1] - y0
    assert dy_same != pytest.approx(0.0)
    assert dy_reversed == pytest.approx(-dy_same, rel=1e-6, abs=1e-6)


def test_columnarity_tightens_microbubble_x_spread_within_seeded_chain():
    low = BubbleAmbientSimulation().advance(
        0.0, _settings(bubble_microbubble_columnarity=0.0),
        resolved_stream_velocity=0.18, small_bubble_breathing=0.0,
    )
    high = BubbleAmbientSimulation().advance(
        0.0, _settings(bubble_microbubble_columnarity=1.0),
        resolved_stream_velocity=0.18, small_bubble_breathing=0.0,
    )
    stride = RECORD_STRIDE
    # First 8 microbubbles are one seeded chain.
    low_x = [low[i * stride] for i in range(8)]
    high_x = [high[i * stride] for i in range(8)]
    assert (max(high_x) - min(high_x)) < (max(low_x) - min(low_x))


def test_columnarity_is_live_reversible_without_reseeding():
    simulation = BubbleAmbientSimulation()
    initial = simulation.advance(0.0, _settings(bubble_microbubble_columnarity=0.0),
                                 resolved_stream_velocity=0.0, small_bubble_breathing=0.0)
    columns = simulation.advance(0.0, _settings(bubble_microbubble_columnarity=1.0),
                                 resolved_stream_velocity=0.0, small_bubble_breathing=0.0)
    restored = simulation.advance(0.0, _settings(bubble_microbubble_columnarity=0.0),
                                  resolved_stream_velocity=0.0, small_bubble_breathing=0.0)
    stride = RECORD_STRIDE
    start_x = [initial[i * stride] for i in range(8)]
    column_x = [columns[i * stride] for i in range(8)]
    assert max(column_x) - min(column_x) < max(start_x) - min(start_x)
    assert restored == pytest.approx(initial, abs=1e-12)


@pytest.mark.parametrize('mode,drift,expected', [
    ('same', 'swirl_cw', 1),
    ('same', 'swirl_ccw', -1),
    ('reversed', 'swirl_cw', -1),
    ('reversed', 'swirl_ccw', 1),
])
def test_spiral_direction_matches_screen_space_winding(mode, drift, expected):
    from widgets.spotify_visualizer.bubble_ambient import _Dot

    # A bead to the right of centre should move DOWN for clockwise and UP
    # for counter-clockwise in screen/UV coordinates (Y grows downward).
    dot = _Dot(x=.75, y=.5, size_factor=1., phase=0., speed_factor=1.,
               opacity=1., tangent=(0., 0.))
    BubbleAmbientSimulation._advance_pool(
        [dot], dt=.05, velocity=0., stream=False, drift=True,
        stream_direction='up', drift_direction=drift,
        drift_amount=.7, drift_speed=.6, drift_frequency=0., time_s=0.,
        direction_mode=mode,
    )
    assert (dot.y - .5) * expected > 0


def test_max_glow_strength_is_independent_of_particle_core():
    settings = _settings(bubble_particle_glow_intensity=1.5,
                         bubble_particle_glow_reactivity=3.0)
    first_particle = round(96 * .2) * RECORD_STRIDE
    quiet = BubbleAmbientSimulation().advance(
        .016, settings, resolved_stream_velocity=.18, small_bubble_breathing=0.,
    )
    loud = BubbleAmbientSimulation().advance(
        .016, settings, resolved_stream_velocity=.18, small_bubble_breathing=.65,
    )
    assert quiet[first_particle+2] == pytest.approx(loud[first_particle+2])
    assert loud[first_particle+4] > quiet[first_particle+4] * 3.
