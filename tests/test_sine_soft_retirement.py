"""Disabled SINE remains a registered compatibility mode, never a selectable one."""
from __future__ import annotations

from core.settings.visualizer_mode_body_host import VisualizerModeBodyHost, visualizer_pill_model
from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    build_visualizer_mode_activation,
    get_visualizer_mode_descriptor,
    is_mode_active,
    iter_all_visualizer_mode_descriptors,
    iter_visualizer_mode_descriptors,
    resolve_admissible_enabled_modes,
    resolve_effective_mode,
)


def test_sine_is_registered_but_not_offered_or_admitted():
    assert 'sine_wave' in VISUALIZER_MODE_IDS
    assert get_visualizer_mode_descriptor('sine_wave').guided_setup_offered is False
    assert is_mode_active('sine_wave') is False
    assert 'sine_wave' in [d.mode_id for d in iter_all_visualizer_mode_descriptors()]
    assert 'sine_wave' not in [d.mode_id for d in iter_visualizer_mode_descriptors()]


def test_saved_sine_selection_is_preserved_but_falls_back_to_bubble():
    saved = build_visualizer_mode_activation(('bubble', 'sine_wave'))
    assert saved['sine_wave'] is True  # preserved for possible migration/recovery
    assert resolve_admissible_enabled_modes(saved) == ('bubble',)
    assert resolve_effective_mode('sine_wave', saved) == ('bubble', True)
    assert ('sine_wave', 'Sine Waves') not in visualizer_pill_model(saved)
    host = VisualizerModeBodyHost(body_factory=lambda mode: mode, mode_activation=saved)
    assert host.enabled_modes == ('bubble',)


def test_sine_only_old_selection_has_a_live_non_sine_fallback():
    saved = build_visualizer_mode_activation(('sine_wave',))
    admitted = resolve_admissible_enabled_modes(saved)
    assert admitted
    assert all(mode != 'sine_wave' for mode in admitted)
    resolved, substituted = resolve_effective_mode('sine_wave', saved)
    assert substituted is True
    assert resolved in admitted
