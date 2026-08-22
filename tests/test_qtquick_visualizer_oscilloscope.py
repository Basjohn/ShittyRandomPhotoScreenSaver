"""Focused Phase-D Oscilloscope logical-state and Quick geometry regressions."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from core.settings.visualizer_mode_registry import (
    get_visualizer_presentation_policy,
)
from rendering.quick.visualizer.implementations.oscilloscope import (
    QuickOscilloscopeRenderer,
    compute_quick_oscilloscope_layout,
)
from widgets.spotify_visualizer.oscilloscope_frame_runtime import (
    OscilloscopeFrameRuntime,
)
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.render_state import (
    OscilloscopeFrame,
    VisualizerEnergyState,
)
from widgets.spotify_visualizer.runtime_controller import (
    VisualizerRuntimeController,
)


_IDENTITY = {
    "runtime_generation": 2,
    "engine_generation": 5,
    "activation_id": 7,
    "source_generation": 5,
    "source_activation_id": 7,
}


def _resolve(
    runtime: OscilloscopeFrameRuntime,
    waveform,
    *,
    now_ts: float,
    playing: bool = True,
    waveform_count: int | None = None,
    source_generation: int = 5,
    source_activation_id: int = 7,
    line_speed: float = 1.0,
    ghosting_enabled: bool = True,
    ghost_decay: float = 0.4,
    energy: VisualizerEnergyState = VisualizerEnergyState(),
    kick_event: float = 0.0,
    snare_event: float = 0.0,
    transient_width_mix: float = 0.35,
    base_sensitivity: float = 3.0,
    animation_enabled: bool = False,
):
    values = tuple(waveform)
    return runtime.resolve(
        values,
        waveform_count=len(values) if waveform_count is None else waveform_count,
        now_ts=now_ts,
        runtime_generation=_IDENTITY["runtime_generation"],
        engine_generation=_IDENTITY["engine_generation"],
        activation_id=_IDENTITY["activation_id"],
        source_generation=source_generation,
        source_activation_id=source_activation_id,
        playing=playing,
        line_speed=line_speed,
        ghosting_enabled=ghosting_enabled,
        ghost_decay=ghost_decay,
        energy=energy,
        kick_event=kick_event,
        snare_event=snare_event,
        transient_width_mix=transient_width_mix,
        base_sensitivity=base_sensitivity,
        animation_enabled=animation_enabled,
    )


def test_paused_idle_waveform_is_current_without_authoritative_timestamp() -> None:
    runtime = OscilloscopeFrameRuntime()
    idle = tuple(0.04 * math.sin(index * math.tau / 16.0) for index in range(64))

    resolved = _resolve(runtime, idle, now_ts=1.0, playing=False)

    assert resolved.reactive_source_ready is True
    assert resolved.waveform == pytest.approx(idle)
    assert resolved.waveform_count == len(idle)
    assert resolved.previous_waveform == ()


def test_stale_source_cannot_replace_current_oscilloscope_state() -> None:
    runtime = OscilloscopeFrameRuntime()
    live = _resolve(runtime, [0.8] * 64, now_ts=1.0)

    stale = _resolve(
        runtime,
        [-1.0] * 64,
        now_ts=1.016,
        source_generation=4,
        source_activation_id=7,
    )

    assert stale.reactive_source_ready is False
    assert stale.waveform == live.waveform
    assert stale.waveform_count == live.waveform_count


def test_idle_live_boundaries_do_not_blend_across_content_authority() -> None:
    runtime = OscilloscopeFrameRuntime()
    idle = _resolve(
        runtime,
        [0.035] * 64,
        now_ts=1.0,
        playing=False,
        line_speed=0.18,
    )
    live = _resolve(
        runtime,
        [0.85] * 64,
        now_ts=1.016,
        playing=True,
        line_speed=0.18,
    )

    assert live.previous_waveform == ()
    assert live.waveform != idle.waveform
    assert live.waveform[0] < 0.85

    next_live = _resolve(
        runtime,
        [0.65] * 64,
        now_ts=1.032,
        playing=True,
        line_speed=0.18,
    )
    paused = _resolve(
        runtime,
        [0.035] * 64,
        now_ts=1.048,
        playing=False,
        line_speed=0.18,
    )

    assert paused.waveform == pytest.approx((0.035,) * 64)
    assert paused.previous_waveform == pytest.approx(next_live.waveform)
    assert paused.previous_waveform[0] > paused.waveform[0]


def test_ghost_delay_uses_oldest_logical_waveform_and_goes_dormant_when_off() -> None:
    runtime = OscilloscopeFrameRuntime()
    frames = []
    for index in range(1, 8):
        frames.append(
            _resolve(
                runtime,
                [float(index) / 10.0] * 4,
                now_ts=1.0 + index * 0.016,
                playing=False,
                ghost_decay=0.1,
            )
        )

    assert frames[0].previous_waveform == ()
    assert [frame.previous_waveform[0] for frame in frames[1:6]] == [
        0.1,
        0.1,
        0.1,
        0.1,
        0.1,
    ]
    assert frames[6].previous_waveform[0] == pytest.approx(0.2)

    disabled = _resolve(
        runtime,
        [8.0] * 4,
        now_ts=1.2,
        playing=False,
        ghosting_enabled=False,
    )
    enabled_again = _resolve(
        runtime,
        [9.0] * 4,
        now_ts=1.216,
        playing=False,
        ghosting_enabled=True,
    )
    assert disabled.previous_waveform == ()
    assert enabled_again.previous_waveform == pytest.approx(disabled.waveform)


def test_energy_events_and_rainbow_time_advance_only_on_logical_ticks() -> None:
    runtime = OscilloscopeFrameRuntime()
    first = _resolve(
        runtime,
        [0.2] * 16,
        now_ts=1.0,
        energy=VisualizerEnergyState(bass=0.6, mid=0.4, high=0.2, overall=0.8),
        animation_enabled=True,
    )
    second = _resolve(
        runtime,
        [0.2] * 16,
        now_ts=1.03,
        energy=VisualizerEnergyState(bass=0.6, mid=0.4, high=0.2, overall=0.8),
        kick_event=1.0,
        snare_event=0.5,
        animation_enabled=True,
    )

    assert first.energy.bass == 0.0
    assert first.energy.overall == pytest.approx(0.8)
    assert second.energy.bass == pytest.approx(0.3)
    assert second.energy.mid == pytest.approx(0.2)
    assert second.energy.high == pytest.approx(0.1)
    assert second.resolved_sensitivity > first.resolved_sensitivity
    assert second.animation_time == pytest.approx(0.03)
    assert second.changed is True

    authored_off = _resolve(
        runtime,
        [0.2] * 16,
        now_ts=1.06,
        energy=VisualizerEnergyState(bass=1.0, overall=1.0),
        kick_event=1.0,
        snare_event=1.0,
        transient_width_mix=0.0,
        base_sensitivity=3.0,
    )
    assert authored_off.resolved_sensitivity == pytest.approx(3.0)


def _presentation(
    *,
    scale: float = 1.0,
    extent: tuple[float, float] = (420.0, 280.0),
):
    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("oscilloscope"),
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
    return compute_quick_oscilloscope_layout(
        local_content_rect=(
            content_x - outer_x,
            content_y - outer_y,
            content_width,
            content_height,
        ),
        visual_scale=presentation.uniform_visual_scale,
    )


def test_oscilloscope_layout_recomputes_domain_with_uniform_stroke_scale() -> None:
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


def test_quick_oscilloscope_registry_is_static_lazy_and_resource_dormant(
    monkeypatch,
) -> None:
    from rendering.quick.visualizer import implementation_registry

    descriptors = implementation_registry.iter_quick_visualizer_implementations()
    assert tuple(descriptor.mode_id for descriptor in descriptors) == (
        "spectrum",
        "oscilloscope",
        "sine_wave",
        "bubble",
        "devcurve",
    )
    assert all(isinstance(descriptor.module_name, str) for descriptor in descriptors)

    imported: list[str] = []
    real_import = implementation_registry.import_module

    def _tracked_import(name: str):
        imported.append(name)
        return real_import(name)

    monkeypatch.setattr(implementation_registry, "import_module", _tracked_import)
    implementation_registry.iter_quick_visualizer_implementations()
    assert imported == []

    renderer = implementation_registry.resolve_quick_visualizer_renderer(
        "oscilloscope"
    )
    assert renderer is not None
    assert renderer.mode_id == "oscilloscope"
    assert renderer.has_resources is False
    assert imported == [
        "rendering.quick.visualizer.implementations.oscilloscope"
    ]
    bubble = implementation_registry.resolve_quick_visualizer_renderer("bubble")
    assert bubble is not None
    assert bubble.mode_id == "bubble"


def test_quick_oscilloscope_renderer_has_no_legacy_presentation_dependency() -> None:
    source = __import__(
        QuickOscilloscopeRenderer.__module__,
        fromlist=["QuickOscilloscopeRenderer"],
    ).__loader__.get_source(QuickOscilloscopeRenderer.__module__)

    assert "spotify_bars_gl_overlay" not in source
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


def _osc_widget(controller, engine, waveform):
    return SimpleNamespace(
        runtime_controller=controller,
        _engine=engine,
        _runtime_generation=2,
        _vis_mode_str="oscilloscope",
        _spotify_playing=True,
        _has_pushed_first_frame=False,
        _display_bars=(0.1, 0.2, 0.3, 0.4),
        _bar_count=4,
        _bar_fill_color=(10, 220, 80, 255),
        _bar_border_color=(255, 255, 255, 255),
        _ghosting_enabled=True,
        _ghost_alpha=0.4,
        _ghost_decay_rate=0.4,
        _spectrum_single_piece=False,
        _spectrum_border_radius=4.0,
        _rainbow_enabled=False,
        _rainbow_speed=0.5,
        _rainbow_per_bar=False,
        _spectrum_rainbow_border=False,
        _spectrum_glow_enabled=False,
        _spectrum_glow_intensity=0.55,
        _spectrum_glow_color=None,
        _spectrum_ghosting_enabled=True,
        _spectrum_ghost_alpha=0.4,
        _spectrum_ghost_decay=0.4,
        _osc_ghosting_enabled=True,
        _osc_ghost_intensity=0.5,
        _osc_ghost_decay=0.4,
        _osc_ghost_line2_enabled=True,
        _osc_ghost_line3_enabled=True,
        _osc_ghost_line4_enabled=True,
        _osc_ghost_line5_enabled=True,
        _osc_ghost_line6_enabled=True,
        _sine_ghosting_enabled=True,
        _sine_ghost_alpha=0.45,
        _sine_ghost_decay=0.3,
        _sine_ghost_line2_enabled=True,
        _sine_ghost_line3_enabled=True,
        _bubble_ghosting_enabled=False,
        _bubble_ghost_alpha=0.0,
        _bubble_ghost_decay=0.4,
        _sine_heartbeat=0.0,
        _heartbeat_intensity=0.0,
        _sine_density=1.0,
        _sine_displacement=0.0,
        _osc_glow_enabled=True,
        _osc_glow_intensity=0.5,
        _osc_glow_size=1.0,
        _osc_glow_reactivity=1.0,
        _osc_glow_color=(0, 200, 255, 230),
        _osc_reactive_glow=True,
        _osc_line_amplitude=3.0,
        _osc_smoothing=0.7,
        _osc_speed=0.33,
        _osc_line_dim=False,
        _osc_line_offset_bias=0.0,
        _osc_vertical_shift=0,
        _osc_line_color=(255, 255, 255, 255),
        _osc_line_count=1,
        _osc_line2_color=(255, 120, 50, 230),
        _osc_line2_glow_color=(255, 120, 50, 180),
        _osc_line3_color=(50, 255, 120, 230),
        _osc_line3_glow_color=(50, 255, 120, 180),
        _osc_line4_color=(255, 0, 150, 230),
        _osc_line4_glow_color=(255, 0, 150, 180),
        _osc_line5_color=(0, 255, 200, 230),
        _osc_line5_glow_color=(0, 255, 200, 180),
        _osc_line6_color=(200, 100, 255, 230),
        _osc_line6_glow_color=(200, 100, 255, 180),
        _osc_transient_width_mix=0.35,
        _sine_glow_enabled=True,
        _sine_glow_intensity=0.5,
        _sine_glow_size=1.0,
        _sine_glow_reactivity=1.0,
        _sine_glow_color=(255, 255, 255, 255),
        _sine_reactive_glow=True,
        _sine_sensitivity=3.0,
        _sine_smoothing=0.7,
        _sine_speed=0.33,
        _sine_line_dim=False,
        _sine_line_offset_bias=0.0,
        _sine_wave_travel=0,
        _sine_card_adaptation=1.0,
        _sine_travel_line2=0,
        _sine_travel_line3=0,
        _sine_travel_line4=0,
        _sine_travel_line5=0,
        _sine_travel_line6=0,
        _sine_line1_shift=0.0,
        _sine_line2_shift=0.0,
        _sine_line3_shift=0.0,
        _sine_line4_shift=0.0,
        _sine_line5_shift=0.0,
        _sine_line6_shift=0.0,
        _sine_wave_effect=0.0,
        _sine_micro_wobble=0.0,
        _sine_crawl_amount=0.0,
        _sine_width_reaction=0.0,
        _sine_vertical_shift=0,
        _sine_line_color=(255, 255, 255, 255),
        _sine_line_count=1,
        _sine_line2_color=(255, 255, 255, 255),
        _sine_line2_glow_color=(255, 255, 255, 255),
        _sine_line3_color=(255, 255, 255, 255),
        _sine_line3_glow_color=(255, 255, 255, 255),
        _sine_line4_color=(255, 255, 255, 255),
        _sine_line4_glow_color=(255, 255, 255, 255),
        _sine_line5_color=(255, 255, 255, 255),
        _sine_line5_glow_color=(255, 255, 255, 255),
        _sine_line6_color=(255, 255, 255, 255),
        _sine_line6_glow_color=(255, 255, 255, 255),
        _waveform_source=waveform,
    )


def test_legacy_capture_freezes_controller_owned_oscilloscope_state() -> None:
    from widgets.spotify_visualizer.legacy_render_snapshot_adapter import (
        capture_legacy_visualizer_logical_frame,
    )

    waveform = [0.8] * 64
    engine = SimpleNamespace(
        get_generation_id=lambda: 5,
        get_activation_id=lambda: 7,
        get_latest_generation_with_frame=lambda: 5,
        get_latest_generation_with_waveform=lambda: 5,
        get_latest_authoritative_frame=lambda: (9.9, 5, 7),
        get_waveform=lambda: waveform,
        get_waveform_count=lambda: len(waveform),
        get_energy_bands=lambda: _Energy(),
        get_transient_energy_bands=lambda: None,
        get_floor_snapshot=lambda: None,
        get_event_scheduler=lambda: _Scheduler(),
    )
    controller = VisualizerRuntimeController(
        runtime_generation=2,
        bar_count=4,
        initial_mode="oscilloscope",
        engine_factory=lambda _count: engine,
    )
    controller.engine = engine
    widget = _osc_widget(controller, engine, waveform)
    widget._osc_transient_width_mix = 0.0

    captured = capture_legacy_visualizer_logical_frame(
        widget,
        now_ts=10.0,
        changed=False,
        mode_reveal_ready=True,
    )

    assert isinstance(captured.mode_state, OscilloscopeFrame)
    assert captured.common.waveform_count == len(waveform)
    assert captured.common.waveform[0] < waveform[0]
    assert captured.common.energy.overall == pytest.approx(0.8)
    assert captured.mode_state.parameters["resolved_sensitivity"] == pytest.approx(
        3.0
    )
    assert captured.changed is True
    state = controller.resolve_logical_mode_state(
        "oscilloscope",
        OscilloscopeFrameRuntime,
    )
    assert isinstance(state, OscilloscopeFrameRuntime)
    assert not hasattr(widget, "_qtquick_oscilloscope_frame_runtime")

    waveform[0] = -1.0
    assert captured.common.waveform[0] > -1.0
