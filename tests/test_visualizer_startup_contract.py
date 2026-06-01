from __future__ import annotations

from widgets.spotify_visualizer.startup_contract import VisualizerStartupState


def test_visualizer_startup_contract_derives_delays_from_shared_fade_duration():
    state = VisualizerStartupState.from_shared_fade_duration(2000)

    assert state.min_reveal_delay_ms == 1600
    assert state.reveal_watchdog_ms == 2600
    assert state.secondary_stage_registered is False
    assert state.reveal_pending is False


def test_visualizer_startup_contract_keeps_minimum_hidden_warmup_floor():
    state = VisualizerStartupState.from_shared_fade_duration(800)

    assert state.min_reveal_delay_ms == 900
    assert state.reveal_watchdog_ms == 1900
