"""Focused Phase-D Sine logical-state and Qt Quick regressions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.settings.visualizer_mode_registry import (
    get_visualizer_presentation_policy,
)
from rendering.quick.visualizer.implementations.sine_wave import (
    QuickSineRenderer,
    compute_quick_sine_layout,
)
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.render_state import (
    SineFrame,
    VisualizerEnergyState,
)
from widgets.spotify_visualizer.runtime_controller import (
    VisualizerRuntimeController,
)
from widgets.spotify_visualizer.sine_frame_runtime import SineFrameRuntime
from widgets.spotify_visualizer.shaders import load_fragment_shader


_IDENTITY = {
    "runtime_generation": 2,
    "engine_generation": 5,
    "activation_id": 7,
    "source_generation": 5,
    "source_activation_id": 7,
}


def _resolve(
    runtime: SineFrameRuntime,
    *,
    now_ts: float,
    playing: bool = True,
    source_generation: int = 5,
    source_activation_id: int = 7,
    energy: VisualizerEnergyState = VisualizerEnergyState(),
    kick_event: float = 0.0,
    snare_event: float = 0.0,
    ghosting_enabled: bool = True,
    ghost_decay: float = 0.3,
    line_count: int = 3,
    line_speed: float = 0.18,
    travels=(0, 0, 0, 0, 0, 0),
    line_shifts=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    transient_width_mix: float = 0.4,
    base_width_reaction: float = 0.0,
    base_sensitivity: float = 1.0,
    base_heartbeat: float = 0.0,
    heartbeat_slider: float = 0.0,
):
    return runtime.resolve(
        now_ts=now_ts,
        runtime_generation=_IDENTITY["runtime_generation"],
        engine_generation=_IDENTITY["engine_generation"],
        activation_id=_IDENTITY["activation_id"],
        source_generation=source_generation,
        source_activation_id=source_activation_id,
        playing=playing,
        energy=energy,
        kick_event=kick_event,
        snare_event=snare_event,
        ghosting_enabled=ghosting_enabled,
        ghost_decay=ghost_decay,
        line_count=line_count,
        line_speed=line_speed,
        travels=travels,
        line_shifts=line_shifts,
        transient_width_mix=transient_width_mix,
        base_width_reaction=base_width_reaction,
        base_sensitivity=base_sensitivity,
        base_heartbeat=base_heartbeat,
        heartbeat_slider=heartbeat_slider,
    )


def test_paused_sine_keeps_authored_idle_motion_without_a_source() -> None:
    runtime = SineFrameRuntime()

    first = _resolve(
        runtime,
        now_ts=1.0,
        playing=False,
        source_generation=-1,
        source_activation_id=-1,
        energy=VisualizerEnergyState(bass=1.0, overall=1.0),
    )
    second = _resolve(
        runtime,
        now_ts=1.05,
        playing=False,
        source_generation=-1,
        source_activation_id=-1,
        energy=VisualizerEnergyState(bass=1.0, overall=1.0),
    )

    assert first.reactive_source_ready is False
    assert first.energy == VisualizerEnergyState()
    assert first.line_speed == pytest.approx(0.22)
    assert first.travels == (2, 2, 2, 0, 0, 0)
    assert all(value < 0.0 for value in first.line_shifts[:3])
    assert second.animation_time == pytest.approx(0.05)
    assert second.line_shifts[0] < first.line_shifts[0]



def test_paused_sine_shader_idle_motion_is_twenty_percent_stronger_only_when_paused() -> None:
    source = load_fragment_shader("sine_wave")
    assert source is not None
    assert "? 1.0 : 0.168" in source
    assert "u_time * 0.264 * max(0.6, speed)" in source
    # Live path remains a 1.0 gate; this is not a shared/music gain change.
    assert "float effective_speed = speed * idle_motion_gate" in source

def test_sine_source_fence_reactivity_and_time_advance_once_per_logical_tick() -> None:
    runtime = SineFrameRuntime()
    first = _resolve(
        runtime,
        now_ts=1.0,
        energy=VisualizerEnergyState(bass=0.6, mid=0.4, high=0.2, overall=0.8),
    )
    live = _resolve(
        runtime,
        now_ts=1.03,
        energy=VisualizerEnergyState(bass=0.6, mid=0.4, high=0.2, overall=0.8),
        kick_event=1.0,
        snare_event=0.5,
        base_heartbeat=0.7,
    )
    same_tick = _resolve(
        runtime,
        now_ts=1.03,
        energy=VisualizerEnergyState(bass=1.0, mid=1.0, high=1.0, overall=1.0),
        kick_event=1.0,
        snare_event=1.0,
    )
    stale = _resolve(
        runtime,
        now_ts=1.06,
        source_generation=4,
        energy=VisualizerEnergyState(bass=1.0, mid=1.0, high=1.0, overall=1.0),
        kick_event=1.0,
        snare_event=1.0,
        base_heartbeat=1.0,
    )

    assert first.energy.bass == 0.0
    assert first.energy.overall == pytest.approx(0.8)
    assert live.reactive_source_ready is True
    assert live.energy.bass > first.energy.bass
    assert live.sensitivity > first.sensitivity
    assert live.heartbeat_intensity > first.heartbeat_intensity
    assert live.animation_time == pytest.approx(0.03)
    assert same_tick.animation_time == live.animation_time
    assert same_tick.energy == live.energy
    assert stale.reactive_source_ready is False
    assert stale.animation_time == pytest.approx(0.06)
    assert stale.energy.bass < live.energy.bass
    assert stale.heartbeat_intensity < live.heartbeat_intensity


def test_sine_ghost_peak_holds_decays_and_goes_dormant_when_disabled() -> None:
    runtime = SineFrameRuntime()
    _resolve(runtime, now_ts=1.0)
    peak = _resolve(
        runtime,
        now_ts=1.03,
        energy=VisualizerEnergyState(bass=0.7, mid=0.5, high=0.3, overall=0.7),
    )
    held = _resolve(
        runtime,
        now_ts=1.08,
        energy=VisualizerEnergyState(),
    )

    assert peak.ghost_energy.bass > 0.7
    assert held.ghost_energy.bass == pytest.approx(peak.ghost_energy.bass)

    disabled = _resolve(
        runtime,
        now_ts=1.11,
        ghosting_enabled=False,
    )
    assert disabled.ghost_energy == VisualizerEnergyState()

    enabled_again = _resolve(
        runtime,
        now_ts=1.14,
        energy=VisualizerEnergyState(bass=0.2, mid=0.1, high=0.05, overall=0.2),
    )
    assert enabled_again.ghost_energy.bass < peak.ghost_energy.bass


def test_sine_absent_source_never_manufactures_a_minimum_ghost() -> None:
    runtime = SineFrameRuntime()
    _resolve(
        runtime,
        now_ts=1.0,
        playing=False,
        source_generation=-1,
        source_activation_id=-1,
    )
    absent = _resolve(
        runtime,
        now_ts=1.05,
        playing=False,
        source_generation=-1,
        source_activation_id=-1,
    )
    assert absent.ghost_energy == VisualizerEnergyState()

    runtime = SineFrameRuntime()
    _resolve(runtime, now_ts=2.0)
    live = _resolve(
        runtime,
        now_ts=2.03,
        energy=VisualizerEnergyState(bass=0.7, mid=0.5, high=0.3, overall=0.7),
    )
    stale = _resolve(
        runtime,
        now_ts=2.08,
        source_generation=4,
        energy=VisualizerEnergyState(bass=1.0, mid=1.0, high=1.0, overall=1.0),
    )

    assert stale.reactive_source_ready is False
    assert 0.0 < stale.ghost_energy.bass < live.ghost_energy.bass


def test_sine_activation_change_resets_animation_and_idle_state() -> None:
    runtime = SineFrameRuntime()
    _resolve(runtime, now_ts=1.0, playing=False)
    advanced = _resolve(runtime, now_ts=1.05, playing=False)
    reset = runtime.resolve(
        now_ts=2.0,
        runtime_generation=3,
        engine_generation=8,
        activation_id=11,
        source_generation=-1,
        source_activation_id=-1,
        playing=False,
        energy=VisualizerEnergyState(),
        kick_event=0.0,
        snare_event=0.0,
        ghosting_enabled=False,
        ghost_decay=0.3,
        line_count=1,
        line_speed=0.18,
        travels=(0,) * 6,
        line_shifts=(0.0,) * 6,
        transient_width_mix=0.4,
        base_width_reaction=0.0,
        base_sensitivity=1.0,
        base_heartbeat=0.0,
        heartbeat_slider=0.0,
    )

    assert advanced.animation_time > 0.0
    assert reset.animation_time == 0.0
    assert reset.line_shifts[0] == pytest.approx(-0.00044)


def _presentation(
    *,
    scale: float = 1.0,
    extent: tuple[float, float] = (420.0, 280.0),
):
    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("sine_wave"),
        display_size=(1920.0, 1080.0),
        outer_origin=(120.0, 80.0),
        uniform_visual_scale=scale,
        viewport_extent=extent,
        border_width=4.0,
        corner_radius=8.0,
    )


def _layout(presentation):
    outer_x, outer_y, _width, _height = presentation.outer_rect
    content_x, content_y, content_width, content_height = presentation.content_rect
    return compute_quick_sine_layout(
        local_content_rect=(
            content_x - outer_x,
            content_y - outer_y,
            content_width,
            content_height,
        ),
        visual_scale=presentation.uniform_visual_scale,
    )


def test_sine_layout_recomputes_domain_with_uniform_authored_scale() -> None:
    canonical = _layout(_presentation())
    scaled = _layout(_presentation(scale=0.65))
    wide = _layout(_presentation(extent=(560.0, 280.0)))
    tall = _layout(_presentation(extent=(420.0, 420.0)))

    assert scaled.line_width == pytest.approx(canonical.line_width * 0.65)
    assert scaled.glow_sigma == pytest.approx(canonical.glow_sigma * 0.65)
    assert scaled.vertical_spacing_range == pytest.approx(
        tuple(value * 0.65 for value in canonical.vertical_spacing_range)
    )
    assert wide.inner_rect[2] > canonical.inner_rect[2]
    assert wide.inner_rect[3] == pytest.approx(canonical.inner_rect[3])
    assert tall.inner_rect[2] == pytest.approx(canonical.inner_rect[2])
    assert tall.inner_rect[3] > canonical.inner_rect[3]
    assert wide.line_width == canonical.line_width == tall.line_width
    assert wide.glow_sigma == canonical.glow_sigma == tall.glow_sigma


def test_quick_sine_registry_is_lazy_and_resource_dormant(monkeypatch) -> None:
    from rendering.quick.visualizer import implementation_registry

    imported: list[str] = []
    real_import = implementation_registry.import_module

    def _tracked_import(name: str):
        imported.append(name)
        return real_import(name)

    monkeypatch.setattr(implementation_registry, "import_module", _tracked_import)
    descriptors = implementation_registry.iter_quick_visualizer_implementations()
    assert tuple(descriptor.mode_id for descriptor in descriptors) == (
        "spectrum",
        "oscilloscope",
        "sine_wave",
        "bubble",
        "devcurve",
    )
    assert imported == []

    renderer = implementation_registry.resolve_quick_visualizer_renderer(
        "sine_wave"
    )
    assert renderer is not None
    assert renderer.mode_id == "sine_wave"
    assert renderer.has_resources is False
    assert imported == [
        "rendering.quick.visualizer.implementations.sine_wave"
    ]


def test_quick_sine_renderer_has_no_clock_or_legacy_presentation_dependency() -> None:
    module = __import__(
        QuickSineRenderer.__module__,
        fromlist=["QuickSineRenderer"],
    )
    source = module.__loader__.get_source(QuickSineRenderer.__module__)

    assert "time.time" not in source
    assert "spotify_bars_gl_overlay" not in source
    assert "renderers.sine_wave" not in source
    assert "QWidget" not in source
    assert "DisplayWidget" not in source
    assert "gl_FragCoord" not in source


class _Energy:
    bass = 0.6
    mid = 0.4
    high = 0.2
    overall = 0.8


class _Scheduler:
    @staticmethod
    def peek_latest(name: str, *, max_age_s: float):
        del max_age_s
        return SimpleNamespace(strength=0.8 if name == "kick" else 0.3)


class _SineWidget(SimpleNamespace):
    heartbeat_reads = 0

    @property
    def _heartbeat_intensity(self):
        self.heartbeat_reads += 1
        return 0.65


def _sine_widget(controller, engine):
    return _SineWidget(
        runtime_controller=controller,
        _engine=engine,
        _runtime_generation=2,
        _vis_mode_str="sine_wave",
        _spotify_playing=True,
        _has_pushed_first_frame=False,
        _display_bars=(),
        _bar_count=0,
        _sine_glow_enabled=True,
        _sine_glow_intensity=0.5,
        _sine_glow_size=1.0,
        _sine_glow_color=(80, 210, 255, 230),
        _sine_reactive_glow=True,
        _sine_sensitivity=1.0,
        _sine_smoothing=0.7,
        _sine_speed=0.33,
        _sine_line_dim=False,
        _sine_line_offset_bias=0.0,
        _osc_vertical_shift=0,
        _sine_wave_transient_width_mix=0.4,
        _sine_wave_travel=1,
        _sine_card_adaptation=0.8,
        _sine_travel_line2=2,
        _sine_travel_line3=1,
        _sine_travel_line4=2,
        _sine_travel_line5=1,
        _sine_travel_line6=2,
        _sine_line1_shift=0.1,
        _sine_line2_shift=-0.1,
        _sine_line3_shift=0.2,
        _sine_line4_shift=-0.2,
        _sine_line5_shift=0.3,
        _sine_line6_shift=-0.3,
        _sine_wave_effect=0.4,
        _sine_micro_wobble=0.2,
        _sine_crawl_amount=0.3,
        _sine_width_reaction=0.25,
        _sine_vertical_shift=100,
        _sine_line_color=(245, 250, 255, 255),
        _sine_line_count=6,
        _sine_line2_color=(255, 120, 50, 230),
        _sine_line2_glow_color=(255, 120, 50, 180),
        _sine_line3_color=(50, 255, 120, 230),
        _sine_line3_glow_color=(50, 255, 120, 180),
        _sine_line4_color=(255, 0, 150, 230),
        _sine_line4_glow_color=(255, 0, 150, 180),
        _sine_line5_color=(0, 255, 200, 230),
        _sine_line5_glow_color=(0, 255, 200, 180),
        _sine_line6_color=(200, 100, 255, 230),
        _sine_line6_glow_color=(200, 100, 255, 180),
        _sine_ghosting_enabled=True,
        _sine_ghost_alpha=0.7,
        _sine_ghost_decay=0.3,
        _sine_ghost_line2_enabled=True,
        _sine_ghost_line3_enabled=True,
        _sine_ghost_line4_enabled=True,
        _sine_ghost_line5_enabled=True,
        _sine_ghost_line6_enabled=True,
        _sine_heartbeat=0.4,
        _sine_density=1.2,
        _sine_displacement=0.3,
    )


def test_legacy_capture_freezes_controller_owned_sine_state_once() -> None:
    from widgets.spotify_visualizer.legacy_render_snapshot_adapter import (
        capture_legacy_visualizer_logical_frame,
    )

    engine = SimpleNamespace(
        get_generation_id=lambda: 5,
        get_activation_id=lambda: 7,
        get_latest_generation_with_frame=lambda: 5,
        get_latest_generation_with_waveform=lambda: 5,
        get_latest_authoritative_frame=lambda: (9.9, 5, 7),
        get_waveform=lambda: (),
        get_waveform_count=lambda: 0,
        get_energy_bands=lambda: _Energy(),
        get_transient_energy_bands=lambda: None,
        get_floor_snapshot=lambda: None,
        get_event_scheduler=lambda: _Scheduler(),
    )
    controller = VisualizerRuntimeController(
        runtime_generation=2,
        bar_count=0,
        initial_mode="sine_wave",
        engine_factory=lambda _count: engine,
    )
    controller.engine = engine
    widget = _sine_widget(controller, engine)

    captured = capture_legacy_visualizer_logical_frame(
        widget,
        now_ts=10.0,
        changed=False,
        mode_reveal_ready=True,
    )

    assert isinstance(captured.mode_state, SineFrame)
    assert captured.common.energy.overall == pytest.approx(0.8)
    assert captured.mode_state.heartbeat_intensity >= 0.65
    assert captured.mode_state.parameters["sine_wave_travel"] == 1
    assert captured.mode_state.parameters["sine_travel_line6"] == 2
    assert captured.mode_state.parameters["resolved_sensitivity"] > 1.0
    assert captured.changed is True
    assert widget.heartbeat_reads == 1
    assert not hasattr(widget, "_sine_reactivity_state_smoothed")
    assert not hasattr(widget, "_sine_idle_shift_phase")
    state = controller.resolve_logical_mode_state("sine_wave", SineFrameRuntime)
    assert isinstance(state, SineFrameRuntime)
