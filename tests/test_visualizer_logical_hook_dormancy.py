"""L1-L3: optional mode work is one activation-resolved logical hook."""
from __future__ import annotations

from dataclasses import replace

import pytest


def test_inactive_sine_heartbeat_never_queries_audio_even_with_a_saved_value():
    from widgets.spotify_visualizer.logical_tick_state import (
        install_default_logical_tick_state,
    )
    from widgets.spotify_visualizer.runtime_controller import (
        VisualizerRuntimeController,
    )
    from widgets.spotify_visualizer.tick_pipeline import process_heartbeat

    class Engine:
        energy_queries = 0
        scheduler_queries = 0

        def get_energy_bands(self):
            self.energy_queries += 1
            return None

        def get_event_scheduler(self):
            self.scheduler_queries += 1
            return None

    controller = VisualizerRuntimeController(
        runtime_generation=0, initial_mode="spectrum"
    )
    state = controller.logical_tick_state
    install_default_logical_tick_state(state, bar_count=32)
    state._sine_heartbeat = 1.0
    engine = Engine()
    controller.engine = engine

    assert controller.active_logical_tick_hook is None
    # This is also the replacement-race fence: even an accidentally retained
    # callable must exit before touching the shared engine or event scheduler.
    process_heartbeat(state, now_ts=1.0)

    assert engine.energy_queries == 0
    assert engine.scheduler_queries == 0


def test_active_sine_heartbeat_queries_audio_through_the_retained_hook(monkeypatch):
    """The active Sine owner still receives the one permitted audio query."""
    from widgets.spotify_visualizer import tick_pipeline
    from widgets.spotify_visualizer.logical_tick_state import (
        install_default_logical_tick_state,
    )
    from widgets.spotify_visualizer.runtime_controller import (
        VisualizerRuntimeController,
    )

    class Engine:
        energy_queries = 0
        scheduler_queries = 0

        def get_energy_bands(self):
            self.energy_queries += 1
            return None

        def get_event_scheduler(self):
            self.scheduler_queries += 1
            return None

    controller = VisualizerRuntimeController(
        runtime_generation=0, initial_mode="sine_wave"
    )
    state = controller.logical_tick_state
    install_default_logical_tick_state(state, bar_count=32)
    state._sine_heartbeat = 1.0
    engine = Engine()
    controller.engine = engine
    controller.enabled = True
    controller.playing = True

    monkeypatch.setattr(
        tick_pipeline, "consume_engine_bars", lambda _state, _now: (True, True)
    )
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda _state, _now: None)
    monkeypatch.setattr(
        tick_pipeline, "_publish_logical_state", lambda *_args, **_kwargs: None
    )

    tick_pipeline.logical_tick(state)

    assert engine.energy_queries == 1
    assert engine.scheduler_queries == 1


def test_controller_resolves_only_the_active_mode_hook_at_activation():
    from widgets.spotify_visualizer.runtime_controller import (
        VisualizerRuntimeController,
    )
    from widgets.spotify_visualizer.tick_pipeline import (
        dispatch_bubble_simulation,
        dispatch_devcurve_field,
        process_heartbeat,
    )

    controller = VisualizerRuntimeController(
        runtime_generation=0, initial_mode="spectrum"
    )
    assert controller.active_logical_tick_hook is None

    controller.set_mode("sine_wave")
    assert controller.active_logical_tick_hook is process_heartbeat
    controller.set_mode("bubble")
    assert controller.active_logical_tick_hook is dispatch_bubble_simulation
    controller.set_mode("devcurve")
    assert controller.active_logical_tick_hook is dispatch_devcurve_field
    controller.set_mode("spectrum")
    assert controller.active_logical_tick_hook is None


def test_repeated_registry_switches_advance_only_the_active_hook(monkeypatch):
    """Every descriptor transition replaces the one callable used by the tick."""
    from importlib import import_module

    import core.settings.visualizer_mode_registry as registry
    from widgets.spotify_visualizer import tick_pipeline
    from widgets.spotify_visualizer.logical_tick_state import (
        install_default_logical_tick_state,
    )
    from widgets.spotify_visualizer.runtime_controller import (
        VisualizerRuntimeController,
    )

    calls: list[str] = []
    hook_descriptors = tuple(
        descriptor
        for descriptor in registry.iter_all_visualizer_mode_descriptors()
        if descriptor.logical_tick_hook_module
        or descriptor.logical_tick_hook_factory
    )
    for descriptor in hook_descriptors:
        assert descriptor.logical_tick_hook_module
        assert descriptor.logical_tick_hook_factory
        module = import_module(descriptor.logical_tick_hook_module)
        monkeypatch.setattr(
            module,
            descriptor.logical_tick_hook_factory,
            lambda _state, _now, mode_id=descriptor.mode_id: calls.append(mode_id),
        )
    monkeypatch.setattr(
        tick_pipeline, "consume_engine_bars", lambda _state, _now: (True, True)
    )
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda _state, _now: None)
    monkeypatch.setattr(
        tick_pipeline, "_publish_logical_state", lambda *_args, **_kwargs: None
    )

    controller = VisualizerRuntimeController(
        runtime_generation=0, initial_mode="spectrum"
    )
    state = controller.logical_tick_state
    install_default_logical_tick_state(state, bar_count=32)
    controller.enabled = True
    controller.playing = True

    # Include two complete passes through the descriptor owners and ordinary
    # no-hook modes.  A newly selected owner must be the only one advanced;
    # returning to a no-hook mode must advance none.
    sequence = registry.VISUALIZER_MODE_IDS * 2
    for mode_id in sequence:
        controller.set_mode(mode_id)
        tick_pipeline.logical_tick(state)

    hook_mode_ids = {descriptor.mode_id for descriptor in hook_descriptors}
    assert calls == [mode_id for mode_id in sequence if mode_id in hook_mode_ids]


def test_incomplete_hook_wiring_rejects_activation_without_mutating_identity(monkeypatch):
    """Descriptor validation fails before retiring the admitted active owner."""
    import core.settings.visualizer_mode_registry as registry
    from widgets.spotify_visualizer.runtime_controller import (
        VisualizerRuntimeController,
    )

    malformed = replace(
        registry.get_visualizer_mode_descriptor("spectrum"),
        mode_id="synthetic_incomplete_hook",
        display_name="Synthetic Incomplete Hook",
        logical_tick_hook_module="widgets.spotify_visualizer.tick_pipeline",
        logical_tick_hook_factory="",
    )
    monkeypatch.setattr(
        registry,
        "_ALL_DESCRIPTORS",
        registry.iter_all_visualizer_mode_descriptors() + (malformed,),
    )
    monkeypatch.setattr(
        registry,
        "VISUALIZER_MODE_IDS",
        registry.VISUALIZER_MODE_IDS + (malformed.mode_id,),
    )

    controller = VisualizerRuntimeController(
        runtime_generation=0, initial_mode="sine_wave"
    )
    active_hook = controller.active_logical_tick_hook
    policy = controller.presentation_policy

    with pytest.raises(ValueError, match="incomplete logical hook wiring"):
        controller.set_mode(malformed.mode_id)

    assert controller.mode_id == "sine_wave"
    assert controller.presentation_policy is policy
    assert controller.active_logical_tick_hook is active_hook


def test_synthetic_registry_growth_does_not_add_steady_logical_tick_work(monkeypatch):
    """The common tick calls its retained owner once; it never scans modes."""
    import core.settings.visualizer_mode_registry as registry
    from widgets.spotify_visualizer import tick_pipeline
    from widgets.spotify_visualizer.logical_tick_state import (
        install_default_logical_tick_state,
    )
    from widgets.spotify_visualizer.runtime_controller import (
        VisualizerRuntimeController,
    )

    synthetic = replace(
        registry.get_visualizer_mode_descriptor("spectrum"),
        mode_id="synthetic_dormant_mode",
        display_name="Synthetic Dormant Mode",
        logical_tick_hook_module="",
        logical_tick_hook_factory="",
    )
    monkeypatch.setattr(
        registry,
        "_ALL_DESCRIPTORS",
        registry.iter_all_visualizer_mode_descriptors() + (synthetic,),
    )
    monkeypatch.setattr(
        registry,
        "VISUALIZER_MODE_IDS",
        registry.VISUALIZER_MODE_IDS + (synthetic.mode_id,),
    )
    # Any hot-path registry walk is a regression.  Mode selection happened at
    # activation; steady logical work must use only the retained callable.
    monkeypatch.setattr(
        registry,
        "iter_visualizer_mode_descriptors",
        lambda: (_ for _ in ()).throw(AssertionError("common tick scanned the registry")),
    )

    controller = VisualizerRuntimeController(
        runtime_generation=0, initial_mode="spectrum"
    )
    state = controller.logical_tick_state
    install_default_logical_tick_state(state, bar_count=32)
    controller.enabled = True
    controller.playing = True
    calls: list[float] = []
    controller._active_logical_tick_hook = lambda _state, now: calls.append(now)

    monkeypatch.setattr(tick_pipeline, "consume_engine_bars", lambda _state, _now: (True, True))
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda _state, _now: None)
    monkeypatch.setattr(tick_pipeline, "_publish_logical_state", lambda *_args, **_kwargs: None)

    tick_pipeline.logical_tick(state)
    tick_pipeline.logical_tick(state)

    assert len(calls) == 2
