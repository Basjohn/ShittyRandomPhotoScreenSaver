"""Bubble settings reach the established consumers once, with preserved runtime limits."""
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_settings import require_mode_settings
from widgets.spotify_visualizer.config_applier import (
    apply_logical_vis_mode_kwargs, apply_presentation_vis_mode_kwargs,
)


def test_each_bubble_control_is_applied_once_per_actual_consumer():
    class Owner:
        def __init__(self):
            object.__setattr__(self, 'writes', {})

        def __setattr__(self, key, value):
            self.writes[key] = self.writes.get(key, 0)+1
            object.__setattr__(self, key, value)

    spec = require_mode_settings('bubble')
    defaults = require_canonical_default('widgets.spotify_visualizer')
    values = {control.key: defaults[control.key] for control in spec.controls}
    logical, presentation = Owner(), Owner()
    apply_logical_vis_mode_kwargs(logical, values)
    apply_presentation_vis_mode_kwargs(presentation, values)
    assert logical.writes == {f'_{control.key}': 1 for control in spec.logical_controls()}
    assert presentation.writes == {f'_{control.key}': 1 for control in spec.presentation_controls()}
    assert logical._bubble_ghosting_enabled is presentation._bubble_ghosting_enabled
    assert '_bubble_trail_strength' in logical.writes
    assert '_bubble_trail_strength' not in presentation.writes


@pytest.mark.parametrize('key,stored,runtime', [
    ('bubble_big_bass_pulse',1.8,1.),
    ('bubble_small_freq_pulse',1.7,1.),
    ('bubble_stream_reactivity',1.9,1.25),
    ('bubble_stream_speed_cap',.15,.15),
    ('bubble_big_contraction_bias',1.6,1.6),
    ('bubble_big_count',4.9,4),
    ('bubble_bounce_big_pct',62.9,62),
])
def test_stored_intent_and_runtime_ranges_preserve_existing_bubble_behavior(key,stored,runtime):
    model = SpotifyVisualizerSettings.from_mapping({key:stored},apply_preset_overlay=False)
    expected = int(stored) if key in {'bubble_big_count','bubble_bounce_big_pct'} else stored
    assert getattr(model,key) == pytest.approx(expected)
    logical = SimpleNamespace()
    apply_logical_vis_mode_kwargs(logical,asdict(model))
    assert getattr(logical,'_'+key) == pytest.approx(runtime)


@pytest.mark.parametrize('version,direction', [(0,'bottom'),(1,'bottom'),(2,'top')])
def test_gradient_ingress_migrates_once_then_round_trips_canonically(version,direction):
    raw = {'bubble_gradient_direction':'top','bubble_gradient_semantics_version':version}
    model = SpotifyVisualizerSettings.from_mapping(raw,apply_preset_overlay=False)
    assert model.bubble_gradient_direction == direction
    saved = model.to_dict()
    assert saved['widgets.spotify_visualizer.bubble_gradient_semantics_version'] == 2
    reloaded = SpotifyVisualizerSettings.from_mapping(saved,apply_preset_overlay=False)
    assert reloaded.bubble_gradient_direction == direction
