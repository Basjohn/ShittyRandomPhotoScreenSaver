"""Production-shaped admission, configuration, and dormant capture tests for Sphere."""
from __future__ import annotations

from types import SimpleNamespace

from core.settings.models._spotify_visualizer import SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import (
    VisualizerClipPolicy, VisualizerShellPolicy, get_visualizer_mode_descriptor,
    resolve_effective_enabled_modes,
)
from widgets.spotify_visualizer.config_applier import apply_logical_vis_mode_kwargs
from widgets.spotify_visualizer.render_state import (
    SphereFrame,
    VisualizerEnergyState,
    VisualizerTransientState,
)
from widgets.spotify_visualizer.sphere_frame_runtime import SphereFrameRuntime


def test_sphere_is_canonical_but_absent_from_legacy_enabled_defaults():
    descriptor = get_visualizer_mode_descriptor("sphere")
    assert descriptor.display_name == "Sphere (Experimental)"
    assert descriptor.default_enabled is False
    assert descriptor.presentation_policy.shell_policy is VisualizerShellPolicy.FRAMELESS
    assert descriptor.presentation_policy.clip_policy is VisualizerClipPolicy.VIEWPORT_RECT
    assert "sphere" not in resolve_effective_enabled_modes(None)
    assert resolve_effective_enabled_modes(["sphere"]) == ("sphere",)


def test_sphere_curated_presets_load_and_custom_restore_owns_all_surface_fields():
    from core.settings.visualizer_presets import (
        apply_preset_to_config, get_custom_preset_index, get_presets,
        restore_visualizer_snapshot,
    )

    presets = get_presets("sphere")
    assert [preset.name for preset in presets] == [
        "Preset 1 (Chrome)", "Preset 2 (Obsidian)", "Preset 3 (Magma)",
        "Preset 4 (Silver)", "Preset 5 (Water)", "Custom",
    ]
    assert get_custom_preset_index("sphere") == 5
    magma = apply_preset_to_config("sphere", 2, {"mode": "sphere"})
    assert magma["sphere_material"] == "Magma"
    assert magma["sphere_surface_detail"] == 1.35
    assert magma["sphere_bump_reactivity"] == .85
    assert magma["sphere_size_response"] == 1.6

    restored = {"mode": "sphere", **magma}
    assert restore_visualizer_snapshot("sphere", restored, {
        "mode": "sphere", "sphere_material": "Water", "sphere_deformation": 0.0,
        "sphere_rotation_speed": .4, "sphere_gloss": .9, "sphere_specular": 1.35,
        "sphere_light_direction": "W", "sphere_idle_motion": .22,
        "sphere_surface_detail": 0.0,
    })
    assert restored["sphere_material"] == "Water"
    assert restored["sphere_surface_detail"] == 0.0


def test_sphere_config_round_trips_and_applies_at_logical_owner():
    settings = SpotifyVisualizerSettings.from_mapping({
        "mode": "sphere", "enabled_modes": ["sphere"], "preset_sphere": 5, "sphere_material": "Magma",
        "sphere_deformation": 3.0, "sphere_rotation_speed": .5, "sphere_gloss": .2,
        "sphere_specular": 1.6, "sphere_light_direction": "se", "sphere_idle_motion": .3,
        "sphere_surface_detail": 0.0, "sphere_bump_reactivity": .9, "sphere_size_response": 1.7, "sphere_bass_response": 1.7,
        "sphere_mid_response": .8, "sphere_high_response": .4,
        "sphere_vocal_response": 1.75, "sphere_energy_curve": .55, "sphere_material_fx": 1.3,
    })
    assert settings.sphere_deformation == 3.0
    serialized = settings.to_dict()
    assert serialized["widgets.spotify_visualizer.sphere_material"] == "Magma"
    assert serialized["widgets.spotify_visualizer.sphere_surface_detail"] == 0.0
    assert serialized["widgets.spotify_visualizer.sphere_bump_reactivity"] == .9
    assert serialized["widgets.spotify_visualizer.sphere_size_response"] == 1.7
    assert serialized["widgets.spotify_visualizer.sphere_vocal_response"] == 1.75
    assert serialized["widgets.spotify_visualizer.sphere_energy_curve"] == .55

    class Host: pass
    host = Host()
    apply_logical_vis_mode_kwargs(host, settings.__dict__)
    assert (host._sphere_material, host._sphere_deformation, host._sphere_light_direction) == ("Magma", 3.0, "SE")
    assert host._sphere_parameters["sphere_surface_detail"] == 0.0
    assert host._sphere_parameters["sphere_bump_reactivity"] == .9
    assert host._sphere_parameters["sphere_size_response"] == 1.7
    assert host._sphere_parameters["sphere_bass_response"] == 1.7
    assert host._sphere_parameters["sphere_vocal_response"] == 1.75
    assert host._sphere_parameters["sphere_material_fx"] == 1.3


def test_sphere_response_controls_are_frozen_bounded_and_default_dormant():
    from widgets.spotify_visualizer.config_applier import SPHERE_DEFAULT_PARAMETERS, apply_logical_vis_mode_kwargs

    assert SPHERE_DEFAULT_PARAMETERS["sphere_energy_curve"] == .60
    assert SPHERE_DEFAULT_PARAMETERS["sphere_material_fx"] == 1.0
    assert SPHERE_DEFAULT_PARAMETERS["sphere_vocal_response"] == 1.4
    assert SPHERE_DEFAULT_PARAMETERS["sphere_bump_reactivity"] == .65
    assert SPHERE_DEFAULT_PARAMETERS["sphere_size_response"] == 1.5
    host = SimpleNamespace()
    apply_logical_vis_mode_kwargs(host, {
        "sphere_deformation": 0.0,
        "sphere_bass_response": 3.0,
        "sphere_mid_response": -1.0,
        "sphere_high_response": .75,
        "sphere_vocal_response": 3.0,
        "sphere_bump_reactivity": 3.0,
        "sphere_size_response": 3.0,
        "sphere_energy_curve": .55,
        "sphere_material_fx": 0.0,
    })
    assert host._sphere_deformation == 0.0
    assert host._sphere_parameters["sphere_bass_response"] == 2.0
    assert host._sphere_parameters["sphere_mid_response"] == 0.0
    assert host._sphere_parameters["sphere_high_response"] == .75
    assert host._sphere_parameters["sphere_vocal_response"] == 3.0
    assert host._sphere_parameters["sphere_bump_reactivity"] == 2.0
    assert host._sphere_parameters["sphere_size_response"] == 2.0
    assert host._sphere_parameters["sphere_energy_curve"] == .55
    assert host._sphere_parameters["sphere_material_fx"] == 0.0
    apply_logical_vis_mode_kwargs(host, {"sphere_vocal_response": -1.0, "sphere_bump_reactivity": -1.0, "sphere_size_response": -1.0})
    assert host._sphere_parameters["sphere_vocal_response"] == 0.0
    assert host._sphere_parameters["sphere_bump_reactivity"] == 0.0
    assert host._sphere_parameters["sphere_size_response"] == 0.0


def test_sphere_runtime_fences_activation_and_carries_only_frozen_parameters():
    runtime = SphereFrameRuntime()
    energy = VisualizerEnergyState(bass=.2, mid=.3, high=.4, overall=.3)
    class Host: pass
    host = Host()
    apply_logical_vis_mode_kwargs(host, {"sphere_material": "Silver"})
    first = runtime.resolve(now_ts=10.0, runtime_generation=1, engine_generation=2,
        activation_id=3, energy=energy, parameters=host._sphere_parameters)
    later = runtime.resolve(now_ts=11.0, runtime_generation=1, engine_generation=2,
        activation_id=3, energy=energy, parameters=host._sphere_parameters)
    reset = runtime.resolve(now_ts=12.0, runtime_generation=1, engine_generation=2,
        activation_id=4, energy=energy, parameters=host._sphere_parameters)
    assert first is not None and later is not None and reset is not None
    assert first.authored_time == 0.0 and later.authored_time == 1.0 and reset.authored_time == 0.0
    frame = SphereFrame(
        authored_time=later.authored_time,
        size_pulse=later.size_pulse,
        parameters=later.parameters,
    )
    assert frame.parameters["sphere_material"] == "Silver"
    prior_parameters = host._sphere_parameters
    apply_logical_vis_mode_kwargs(host, {"sphere_material": "Magma", "sphere_gloss": .2})
    updated = runtime.resolve(now_ts=12.5, runtime_generation=1, engine_generation=2,
        activation_id=4, energy=energy, parameters=host._sphere_parameters)
    assert updated is not None and host._sphere_parameters is not prior_parameters
    assert updated.parameters["sphere_material"] == "Magma"
    runtime.retire()
    assert runtime.resolve(now_ts=13.0, runtime_generation=1, engine_generation=2,
        activation_id=5, energy=energy, parameters=host._sphere_parameters) is None


def test_sphere_size_response_is_smooth_elastic_and_materially_larger_at_high_setting():
    runtime = SphereFrameRuntime()
    energy = VisualizerEnergyState()
    transient = VisualizerTransientState(mid=1.0, onset_detected=True, onset_strength=1.0)

    class Host: pass
    host = Host()
    apply_logical_vis_mode_kwargs(host, {
        "sphere_size_response": 2.0,
        "sphere_energy_curve": 0.60,
    })
    first = runtime.resolve(
        now_ts=20.0, runtime_generation=1, engine_generation=2, activation_id=3,
        energy=energy, parameters=host._sphere_parameters, transient=transient,
    )
    assert first is not None and first.size_pulse == 0.0

    samples = []
    for index in range(1, 181):
        frame = runtime.resolve(
            now_ts=20.0 + index / 90.0,
            runtime_generation=1, engine_generation=2, activation_id=3,
            energy=energy, parameters=host._sphere_parameters, transient=transient,
        )
        assert frame is not None
        samples.append(frame.size_pulse)
    # The first logical step cannot snap anywhere near the final growth, while
    # a sustained strong transient may breathe out to roughly +60% radius.
    assert 0.0 < samples[0] < 0.05
    assert samples[20] < samples[60]
    assert samples[-1] > 0.50
    assert max(samples) <= 0.72

    quiet = VisualizerTransientState()
    release = []
    for index in range(181, 226):
        frame = runtime.resolve(
            now_ts=20.0 + index / 90.0,
            runtime_generation=1, engine_generation=2, activation_id=3,
            energy=energy, parameters=host._sphere_parameters, transient=quiet,
        )
        assert frame is not None
        release.append(frame.size_pulse)
    assert 0.0 < release[0] < samples[-1]
    assert release[-1] < release[0] * 0.5

    apply_logical_vis_mode_kwargs(host, {"sphere_size_response": 0.0})
    reset = runtime.resolve(
        now_ts=30.0, runtime_generation=1, engine_generation=2, activation_id=4,
        energy=energy, parameters=host._sphere_parameters, transient=transient,
    )
    next_frame = runtime.resolve(
        now_ts=30.1, runtime_generation=1, engine_generation=2, activation_id=4,
        energy=energy, parameters=host._sphere_parameters, transient=transient,
    )
    assert reset is not None and next_frame is not None
    assert reset.size_pulse == 0.0
    assert next_frame.size_pulse == 0.0


def test_capture_publishes_sphere_payload_and_common_energy_at_snapshot_seam():
    from types import SimpleNamespace
    from widgets.spotify_visualizer.logical_frame_capture import capture_visualizer_logical_frame
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

    class Engine:
        latest_frame_generation = 5
        def get_generation_id(self): return 5
        def get_activation_id(self): return 7
        def get_energy_bands(self): return SimpleNamespace(bass=.3, mid=.2, high=.1, overall=.2)
        def get_latest_generation_with_frame(self): return self.latest_frame_generation
        def get_latest_generation_with_waveform(self): return 5
        def get_waveform(self): return ()
        def get_waveform_count(self): return 0
        def get_transient_energy_bands(self): return None
        def get_floor_snapshot(self): return None
        def get_latest_authoritative_frame(self): return (9.9, 5, 7)

    controller = VisualizerRuntimeController(runtime_generation=2, initial_mode="sphere")
    widget = SimpleNamespace(_vis_mode_str="sphere", runtime_controller=controller, _engine=Engine(),
        _runtime_generation=2, _spotify_playing=True, _has_pushed_first_frame=True,
        _sphere_material="Magma", _sphere_deformation=1.0, _sphere_rotation_speed=.35,
        _sphere_gloss=.65, _sphere_specular=.8, _sphere_light_direction="NW", _sphere_idle_motion=.12)
    apply_logical_vis_mode_kwargs(widget, {"sphere_material": "Magma"})
    frame = capture_visualizer_logical_frame(widget, now_ts=10.0, changed=True, mode_reveal_ready=True)
    assert frame is not None
    assert isinstance(frame.mode_state, SphereFrame)
    assert frame.mode_state.parameters["sphere_material"] == "Magma"
    assert frame.common.energy.bass == .3


def test_sphere_capture_keeps_first_valid_generation_energy():
    """Generation/activation zero is live source identity, never an idle alias."""
    from types import SimpleNamespace
    from widgets.spotify_visualizer.logical_frame_capture import capture_visualizer_logical_frame
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController

    class Engine:
        def get_generation_id(self): return 0
        def get_activation_id(self): return 0
        def get_energy_bands(self): return SimpleNamespace(bass=.7, mid=.4, high=.2, overall=.5)
        def get_latest_authoritative_frame(self): return (9.9, 0, 0)

    controller = VisualizerRuntimeController(runtime_generation=0, initial_mode="sphere")
    widget = SimpleNamespace(_vis_mode_str="sphere", runtime_controller=controller, _engine=Engine(),
        _runtime_generation=0, _spotify_playing=True, _has_pushed_first_frame=True)
    apply_logical_vis_mode_kwargs(widget, {"sphere_material": "Chrome"})
    frame = capture_visualizer_logical_frame(widget, now_ts=10.0, changed=True, mode_reveal_ready=True)
    assert frame is not None
    assert frame.source_generation == frame.source_activation_id == 0
    assert frame.common.energy == VisualizerEnergyState(bass=.7, mid=.4, high=.2, overall=.5)


def test_sphere_settings_body_is_lazy_and_persists_when_explicitly_enabled(qt_app, settings_manager):
    from ui.tabs.visualizers_tab import VisualizersTab

    settings_manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": "bubble",
        "enabled_modes": ["bubble"], "sphere_material": "Chrome",
    }})
    tab = VisualizersTab(settings_manager)
    try:
        assert not tab._vis_body_host.is_constructed("sphere")
        tab._on_mode_admission_toggled("sphere", True)
        tab._select_mode_page("sphere")
        assert tab._vis_body_host.is_constructed("sphere")
        tab.sphere_material.setCurrentText("Water")
        tab.sphere_gloss.setValue(40)
        tab.sphere_bass_response.setValue(165)
        tab.sphere_vocal_response.setValue(175)
        tab.sphere_bump_reactivity.setValue(85)
        tab.sphere_size_response.setValue(170)
        tab.sphere_energy_curve.setValue(55)
        tab.sphere_material_fx.setValue(120)
        tab._save_settings_now()
        saved = settings_manager.get("widgets", {})["spotify_visualizer"]
        assert saved["sphere_material"] == "Water"
        assert saved["sphere_gloss"] == .4
        assert saved["sphere_bass_response"] == 1.65
        assert saved["sphere_vocal_response"] == 1.75
        assert saved["sphere_bump_reactivity"] == .85
        assert saved["sphere_size_response"] == 1.7
        assert saved["sphere_energy_curve"] == .55
        assert saved["sphere_material_fx"] == 1.2
        assert "sphere" in saved["enabled_modes"]
    finally:
        tab.deleteLater()


def test_unbuilt_sphere_settings_survive_another_mode_save(qt_app, settings_manager):
    from ui.tabs.visualizers_tab import VisualizersTab

    settings_manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": "bubble",
        "enabled_modes": ["bubble", "sphere"], "sphere_material": "Magma", "sphere_gloss": .22,
    }})
    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page("bubble")
        tab._save_settings_now()
        saved = settings_manager.get("widgets", {})["spotify_visualizer"]
        assert saved["sphere_material"] == "Magma"
        assert saved["sphere_gloss"] == .22
        assert not tab._vis_body_host.is_constructed("sphere")
    finally:
        tab.deleteLater()


def test_constructed_sphere_body_hides_on_bubble_selection_and_reappears(qt_app, settings_manager):
    from ui.tabs.visualizers_tab import VisualizersTab

    settings_manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": "bubble",
        "enabled_modes": ["bubble", "sphere"],
    }})
    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page("sphere")
        sphere = tab._sphere_settings_container
        assert not sphere.isHidden()
        tab._select_mode_page("bubble")
        assert sphere.isHidden()
        tab._select_mode_page("sphere")
        assert not sphere.isHidden()
    finally:
        tab.deleteLater()


def test_owner_publishes_sphere_without_constructing_another_mode_runtime(qt_app, monkeypatch):
    from types import SimpleNamespace
    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from widgets.spotify_visualizer import tick_pipeline
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    class Engine:
        latest_frame_generation = 5
        authoritative_generation = 5
        def get_generation_id(self): return 5
        def get_activation_id(self): return 7
        def get_latest_generation_with_frame(self): return self.latest_frame_generation
        def get_latest_generation_with_waveform(self): return 5
        def get_latest_authoritative_frame(self): return (1.0, self.authoritative_generation, 7)
        def get_waveform(self): return ()
        def get_waveform_count(self): return 0
        def get_energy_bands(self): return SimpleNamespace(bass=.4, mid=.2, high=.1, overall=.25)
        def get_transient_energy_bands(self): return SimpleNamespace(bass_transient=.7, mid_transient=.9, high_transient=.1)
        def get_floor_snapshot(self): return None
        def get_event_scheduler(self): return None
        def get_perf_diagnostics(self): return {}

    monkeypatch.setattr(tick_pipeline, "consume_engine_bars", lambda _owner, _now: (True, True))
    monkeypatch.setattr(tick_pipeline, "process_heartbeat", lambda _owner, _now: None)
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda _owner, _now: None)
    clock_values = iter(float(value) for value in range(10, 40))
    monkeypatch.setattr(tick_pipeline.time, "time", lambda: next(clock_values))
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(screen_index=0, runtime_generation=91, screen=qt_app.primaryScreen(),
        scene_factory=factory, window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
    try:
        engine = Engine()
        owner = QuickDisplayVisualizerOwner(runtime, bar_count=32, initial_mode="sphere", engine_factory=lambda _bc: engine)
        owner.configure(logical_kwargs={"sphere_material": "Silver", "sphere_idle_motion": .25}, playing=True)
        identity = owner.bind(engine_generation=5, activation_id=7)
        state = owner.controller.logical_tick_state
        state._mode_teardown_block_until_ready = False
        state._mode_transition_ready = True
        state._waiting_for_fresh_engine_frame = False
        state._display_bars_source_generation = 5
        state._display_bars_source_activation = 7
        frame = tick_pipeline.logical_tick(state)
        assert frame is not None and frame.mode_state.mode_id == "sphere"
        assert frame.common.energy.bass == .4
        assert owner.controller.peek_logical_mode_state("sphere") is not None
        assert owner.controller.peek_logical_mode_state("bubble") is None
        assert owner.sync_present() is True
        first_snapshot = owner.controller.render_bridge.peek()
        assert first_snapshot is not None
        assert first_snapshot.logical_revision > 0
        assert first_snapshot.logical.mode_state.authored_time == 0.0
        assert first_snapshot.logical.common.energy.bass == .4
        assert first_snapshot.logical.common.transient.mid == .9

        later = tick_pipeline.logical_tick(state)
        assert later is not None
        assert owner.sync_present() is True
        later_snapshot = owner.controller.render_bridge.peek()
        assert later_snapshot is not None
        assert later_snapshot.logical_revision > first_snapshot.logical_revision
        assert later_snapshot.logical.mode_state.authored_time > first_snapshot.logical.mode_state.authored_time
        assert later_snapshot.logical.common.energy.bass == .4
        # Sphere remains legitimately idle/self-animating while a source frame
        # becomes stale; its musical energy must drop to zero.
        engine.latest_frame_generation = 4
        engine.authoritative_generation = 4
        stale = tick_pipeline.logical_tick(state)
        assert stale is not None and stale.source_generation == 4
        assert stale.common.energy.bass == 0.0
        assert stale.common.transient.bass == 0.0
        assert stale.common.transient.mid == 0.0
        assert owner.sync_present() is True
        assert owner.retire() is True
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()
