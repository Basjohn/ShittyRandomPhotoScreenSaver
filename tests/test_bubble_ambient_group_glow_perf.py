"""Slice 11 opt-in ambient carrier, luminous release and diagnostic HUD contracts."""
from __future__ import annotations

from pathlib import Path
import pytest

from widgets.spotify_visualizer.bubble_ambient import BubbleAmbientSimulation, _Dot, RECORD_STRIDE
from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import require_mode_settings


def _settings(**changes):
    defaults = require_canonical_default('widgets.spotify_visualizer')
    keys = ('bubble_drift_amount', 'bubble_drift_direction', 'bubble_drift_speed',
            'bubble_drift_frequency', 'bubble_stream_direction', 'bubble_group_drift')
    out = {key: defaults[key] for key in keys}
    out.update({control.key: defaults[control.key]
                for control in require_mode_settings('bubble').controls
                if control.bucket == 'particles'})
    out.update(changes)
    return out


def _one_particle_record(payload, settings):
    micro_count = round(96 * settings['bubble_microbubble_density']) if (settings['bubble_microbubble_stream'] or settings['bubble_microbubble_drift']) else 0
    return payload[micro_count * RECORD_STRIDE: (micro_count+1) * RECORD_STRIDE]


def test_group_drift_carrier_is_inherited_when_decorative_drift_is_enabled():
    initial = _Dot(.5,.5,1.,0.,1.,1.,(0.,1.))
    direct = _Dot(.5,.5,1.,0.,1.,1.,(0.,1.))
    reverse = _Dot(.5,.5,1.,0.,1.,1.,(0.,1.))
    kwargs = dict(dt=.05, velocity=0., stream=False, drift=True,
                  stream_direction='up', drift_direction='swish_horizontal',
                  drift_amount=.2, drift_speed=.3, drift_frequency=.2,
                  time_s=0., group_motion=(.2,.06,.05))
    BubbleAmbientSimulation._advance_pool([direct], direction_mode='same', **kwargs)
    BubbleAmbientSimulation._advance_pool([reverse], direction_mode='reversed', **kwargs)
    assert direct.x != .5 and direct.y != .5
    assert direct.x - .5 == pytest.approx(- (reverse.x-.5), abs=1e-12)
    assert direct.y - .5 == pytest.approx(- (reverse.y-.5), abs=1e-12)
    assert (initial.x,initial.y)==(.5,.5)


def test_group_carrier_is_inert_if_decorative_drift_is_disabled():
    no_drift = _Dot(.5,.5,1.,0.,1.,1.,(0.,1.))
    BubbleAmbientSimulation._advance_pool(
        [no_drift], dt=.05, velocity=0., stream=False, drift=False,
        stream_direction='up', drift_direction='swish_horizontal',
        drift_amount=.2, drift_speed=.3, drift_frequency=.2,
        time_s=0., group_motion=(.2,.06,.05), direction_mode='same')
    assert (no_drift.x,no_drift.y)==(.5,.5)


def test_glow_quick_release_keeps_particle_body_fixed():
    s = _settings(bubble_particle_glow=True, bubble_particle_density=.4,
                  bubble_particle_glow_intensity=1.5,
                  bubble_particle_glow_reactivity=3.,
                  bubble_particle_glow_release_ms=160)
    sim = BubbleAmbientSimulation()
    peak = ()
    for _ in range(35):
        peak=sim.advance(.016,s,resolved_stream_velocity=0.,small_bubble_breathing=1.)
    core = _one_particle_record(peak,s)
    assert core[4]>1.
    tail=peak
    for _ in range(18):
        tail=sim.advance(.016,s,resolved_stream_velocity=0.,small_bubble_breathing=0.)
    faded=_one_particle_record(tail,s)
    assert faded[2]==pytest.approx(core[2])
    assert faded[4] < core[4] * .32
    assert faded[4] >= 0


def test_glow_release_slider_controls_fade_without_new_audio_path():
    base=_settings(bubble_particle_glow=True,bubble_particle_density=.2,
                   bubble_particle_glow_intensity=1.5,bubble_particle_glow_reactivity=3.)
    fast=BubbleAmbientSimulation();slow=BubbleAmbientSimulation()
    for _ in range(30):
        fast.advance(.016,{**base,'bubble_particle_glow_release_ms':80},resolved_stream_velocity=0.,small_bubble_breathing=1.)
        slow.advance(.016,{**base,'bubble_particle_glow_release_ms':600},resolved_stream_velocity=0.,small_bubble_breathing=1.)
    for _ in range(12):
        f=fast.advance(.016,{**base,'bubble_particle_glow_release_ms':80},resolved_stream_velocity=0.,small_bubble_breathing=0.)
        x=slow.advance(.016,{**base,'bubble_particle_glow_release_ms':600},resolved_stream_velocity=0.,small_bubble_breathing=0.)
    assert _one_particle_record(f,base)[4] < _one_particle_record(x,base)[4]


def test_glow_controls_are_real_canonical_optional_builder_properties():
    s=require_mode_settings('bubble')
    defaults=require_canonical_default('widgets.spotify_visualizer')
    for key in ('bubble_particle_glow_release_ms','bubble_particle_glow_spread'):
        control=s.control(key)
        assert control.when == ('bubble_particle_glow', True)
        assert key in defaults


def test_perf_huds_centered_with_independent_opacity_and_lower_visualizer_inset():
    root = Path(__file__).resolve().parents[1]
    checks = (
        ('rendering/quick/qml/DisplayScene.qml', 'perfHud', '#99000000', 8),
        ('rendering/quick/qml/VisualizerPresentation.qml', 'visualizerPerfHud', '#80000000', 12),
    )
    for filename, object_name, background, top_margin in checks:
        content = (root / filename).read_text(encoding='utf-8')
        block = content.split(f'id: {object_name}', 1)[1].split('Text {', 1)[0]
        assert 'anchors.horizontalCenter: parent.horizontalCenter' in block
        assert 'anchors.left: parent.left' not in block
        assert f'anchors.topMargin: {top_margin}' in block
        assert f'color: "{background}"' in block
    # The visualizer counter keeps the 1px vertical internal-padding increase.
    viz = (root / 'rendering/quick/qml/VisualizerPresentation.qml').read_text(encoding='utf-8')
    block = viz.split('id: visualizerPerfHud', 1)[1].split('Text {', 1)[0]
    assert 'height: visualizerPerfHudLabel.implicitHeight + 8' in block
