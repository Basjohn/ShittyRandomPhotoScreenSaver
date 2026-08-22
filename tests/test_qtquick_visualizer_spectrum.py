"""Focused Phase-D Spectrum immutable-state and Quick geometry regressions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.settings.visualizer_mode_registry import (
    get_visualizer_presentation_policy,
)
from rendering.quick.visualizer import (
    VisualizerRenderNode,
    snapshot_has_current_reactive_source,
    snapshot_is_render_admissible,
)
from rendering.quick.visualizer.implementations.spectrum import (
    compute_quick_spectrum_layout,
)
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.render_bridge import VisualizerRenderIdentity
from widgets.spotify_visualizer.render_state import (
    SpectrumFrame,
    VisualizerCommonState,
    VisualizerLogicalFrame,
    compose_visualizer_render_snapshot,
    freeze_render_fields,
)
from widgets.spotify_visualizer.runtime_controller import (
    VisualizerRuntimeController,
)
from widgets.spotify_visualizer.spectrum_frame_runtime import (
    SpectrumFrameRuntime,
)
from widgets.spotify_visualizer.spectrum_solid_hysteresis import (
    compute_spectrum_height_scale,
)


def _presentation(
    *,
    scale: float = 1.0,
    extent: tuple[float, float] = (420.0, 280.0),
):
    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("spectrum"),
        display_size=(1920.0, 1080.0),
        outer_origin=(120.0, 80.0),
        uniform_visual_scale=scale,
        viewport_extent=extent,
        border_width=4.0,
        corner_radius=8.0,
    )


def _logical(
    *,
    playing: bool,
    source_generation: int,
    source_activation_id: int,
    bars=(0.2, 0.6, 0.9, 0.4),
    peaks=(0.3, 0.8, 0.95, 0.5),
    present_frame: bool = True,
) -> VisualizerLogicalFrame:
    return VisualizerLogicalFrame(
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        source_generation=source_generation,
        source_activation_id=source_activation_id,
        mode_id="spectrum",
        playing=playing,
        logical_timestamp=10.0,
        source_timestamp=None,
        changed=True,
        present_frame=present_frame,
        mode_reveal_ready=True,
        common=VisualizerCommonState(
            bars=tuple(bars),
            bar_count=len(bars),
            style=freeze_render_fields(
                {
                    "fill_color": (10, 220, 80, 255),
                    "border_color": (245, 245, 255, 255),
                    "single_piece": True,
                    "border_radius": 4.0,
                }
            ),
        ),
        mode_state=SpectrumFrame(
            peaks=tuple(peaks),
            ghost_bars=tuple(peaks),
            parameters=freeze_render_fields(
                {
                    "spectrum_ghosting_enabled": True,
                    "spectrum_ghost_alpha": 0.4,
                }
            ),
        ),
    )


def _snapshot(**logical_kwargs):
    return compose_visualizer_render_snapshot(
        _logical(**logical_kwargs),
        _presentation(),
        logical_revision=1,
    )


def test_paused_spectrum_authors_visible_idle_without_source_identity() -> None:
    runtime = SpectrumFrameRuntime()
    frame = runtime.resolve(
        [0.0] * 8,
        bar_count=8,
        now_ts=1.0,
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        source_generation=-1,
        source_activation_id=-1,
        playing=False,
        first_frame=True,
        smoothing_enabled=True,
        smoothing_strength=0.5,
        single_piece=False,
        segments=53,
        ghosting_enabled=True,
        ghost_decay=0.4,
        animation_enabled=False,
    )

    assert frame.reactive_source_ready is False
    assert len(frame.bars) == 8
    assert max(frame.bars) >= 0.20
    assert frame.peaks == frame.bars
    assert frame.ghost_bars == frame.peaks
    assert frame.animation_time == 0.0


def test_fresh_play_replaces_idle_in_place_and_peaks_decay_on_logical_time() -> None:
    runtime = SpectrumFrameRuntime()
    idle = runtime.resolve(
        [0.0] * 4,
        bar_count=4,
        now_ts=1.0,
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        source_generation=-1,
        source_activation_id=-1,
        playing=False,
        first_frame=True,
        smoothing_enabled=True,
        smoothing_strength=0.5,
        single_piece=False,
        segments=53,
        ghosting_enabled=True,
        ghost_decay=0.4,
        animation_enabled=True,
    )
    live = runtime.resolve(
        [0.9, 0.7, 0.5, 0.3],
        bar_count=4,
        now_ts=1.016,
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        source_generation=5,
        source_activation_id=7,
        playing=True,
        first_frame=False,
        smoothing_enabled=True,
        smoothing_strength=0.5,
        single_piece=False,
        segments=53,
        ghosting_enabled=True,
        ghost_decay=0.4,
        animation_enabled=True,
    )
    falling = runtime.resolve(
        [0.1, 0.1, 0.1, 0.1],
        bar_count=4,
        now_ts=1.049,
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        source_generation=5,
        source_activation_id=7,
        playing=True,
        first_frame=False,
        smoothing_enabled=False,
        smoothing_strength=0.5,
        single_piece=False,
        segments=53,
        ghosting_enabled=True,
        ghost_decay=0.4,
        animation_enabled=True,
    )

    assert idle.reactive_source_ready is False
    assert live.reactive_source_ready is True
    assert live.bars[0] == pytest.approx(0.9)
    assert falling.peaks[0] > falling.bars[0]
    assert falling.peaks[0] < live.peaks[0]
    assert falling.animation_time > live.animation_time >= 0.0


def test_play_waiting_for_fresh_source_keeps_idle_but_never_grants_authority() -> None:
    runtime = SpectrumFrameRuntime()
    idle = runtime.resolve(
        [0.0] * 5,
        bar_count=5,
        now_ts=1.0,
        runtime_generation=1,
        engine_generation=3,
        activation_id=4,
        source_generation=-1,
        source_activation_id=-1,
        playing=False,
        first_frame=True,
        smoothing_enabled=True,
        smoothing_strength=0.5,
        single_piece=False,
        segments=53,
        ghosting_enabled=False,
        ghost_decay=0.4,
        animation_enabled=False,
    )
    waiting = runtime.resolve(
        [0.95] * 5,
        bar_count=5,
        now_ts=1.016,
        runtime_generation=1,
        engine_generation=3,
        activation_id=4,
        source_generation=2,
        source_activation_id=4,
        playing=True,
        first_frame=False,
        smoothing_enabled=True,
        smoothing_strength=0.5,
        single_piece=False,
        segments=53,
        ghosting_enabled=False,
        ghost_decay=0.4,
        animation_enabled=False,
    )

    assert waiting.bars == idle.bars
    assert waiting.reactive_source_ready is False
    assert waiting.ghost_bars == ()


def test_generic_source_admission_keeps_paused_scene_until_fresh_play_frame() -> None:
    paused = _snapshot(
        playing=False,
        source_generation=-1,
        source_activation_id=-1,
    )
    stale_play = _snapshot(
        playing=True,
        source_generation=4,
        source_activation_id=7,
    )
    fresh_play = _snapshot(
        playing=True,
        source_generation=5,
        source_activation_id=7,
    )
    non_present = _snapshot(
        playing=False,
        source_generation=-1,
        source_activation_id=-1,
        present_frame=False,
    )

    assert snapshot_is_render_admissible(paused) is True
    assert snapshot_has_current_reactive_source(paused) is False
    assert snapshot_is_render_admissible(stale_play) is False
    assert snapshot_is_render_admissible(non_present) is False
    assert snapshot_has_current_reactive_source(fresh_play) is True
    assert snapshot_is_render_admissible(fresh_play) is True

    node = VisualizerRenderNode()
    identity = VisualizerRenderIdentity(
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        mode_id="spectrum",
    )
    node.synchronize(
        identity=identity,
        snapshot=paused,
        logical_size=(420.0, 280.0),
        device_pixel_ratio=1.0,
    )
    assert node.snapshot is paused
    node.synchronize(
        identity=identity,
        snapshot=stale_play,
        logical_size=(420.0, 280.0),
        device_pixel_ratio=1.0,
    )
    assert node.snapshot is paused
    node.synchronize(
        identity=identity,
        snapshot=fresh_play,
        logical_size=(420.0, 280.0),
        device_pixel_ratio=1.0,
    )
    assert node.snapshot is fresh_play
    assert node.telemetry.snapshot().admission_rejection_count == 1


def _layout(presentation, count=16):
    outer_x, outer_y, _width, _height = presentation.outer_rect
    content_x, content_y, content_width, content_height = (
        presentation.content_rect
    )
    return compute_quick_spectrum_layout(
        local_content_rect=(
            content_x - outer_x,
            content_y - outer_y,
            content_width,
            content_height,
        ),
        viewport_extent=presentation.viewport_extent,
        visual_scale=presentation.uniform_visual_scale,
        bar_count=count,
    )


def test_spectrum_layout_uniformly_scales_and_reflows_wide_tall_viewports() -> None:
    canonical = _layout(_presentation())
    scaled = _layout(_presentation(scale=0.65))
    wide = _layout(_presentation(extent=(560.0, 280.0)))
    tall = _layout(_presentation(extent=(420.0, 420.0)))

    assert scaled.bars_left == pytest.approx(canonical.bars_left * 0.65)
    assert scaled.bar_width == pytest.approx(canonical.bar_width * 0.65)
    assert scaled.bar_gap == pytest.approx(canonical.bar_gap * 0.65)
    assert scaled.bar_span == pytest.approx(canonical.bar_span * 0.65)
    assert scaled.segment_count == canonical.segment_count
    assert scaled.height_scale == pytest.approx(canonical.height_scale)

    assert wide.bar_width > canonical.bar_width
    assert wide.bar_gap == pytest.approx(canonical.bar_gap)
    assert tall.bar_width == pytest.approx(canonical.bar_width)
    assert tall.segment_count > canonical.segment_count
    assert wide.content_rect[2] > canonical.content_rect[2]
    assert tall.content_rect[3] > canonical.content_rect[3]

    # The field ends at the authored right margin/inset inside Quick content;
    # no legacy card-shadow shrink is subtracted from the available width.
    right_guard = (
        canonical.content_rect[0]
        + canonical.content_rect[2]
        - (canonical.bars_left + canonical.bar_span)
    )
    assert right_guard == pytest.approx(11.0)


def test_only_proven_spectrum_policy_claims_viewport_resize_capability() -> None:
    assert get_visualizer_presentation_policy("spectrum").viewport_resize_capable
    for mode_id in ("oscilloscope", "sine_wave", "bubble", "devcurve"):
        assert not get_visualizer_presentation_policy(
            mode_id
        ).viewport_resize_capable


def test_quick_spectrum_registry_is_static_and_lazy() -> None:
    from rendering.quick.visualizer.implementation_registry import (
        iter_quick_visualizer_implementations,
        resolve_quick_visualizer_renderer,
    )

    descriptors = iter_quick_visualizer_implementations()
    assert tuple(descriptor.mode_id for descriptor in descriptors) == ("spectrum",)
    assert all(isinstance(descriptor.module_name, str) for descriptor in descriptors)
    renderer = resolve_quick_visualizer_renderer("spectrum")
    assert renderer is not None
    assert renderer.mode_id == "spectrum"
    assert renderer.has_resources is False
    assert resolve_quick_visualizer_renderer("oscilloscope") is None


def test_legacy_capture_freezes_quick_spectrum_peaks_without_geometry_reads() -> None:
    from widgets.spotify_visualizer.legacy_render_snapshot_adapter import (
        capture_legacy_visualizer_logical_frame,
    )

    engine = SimpleNamespace(
        get_generation_id=lambda: 5,
        get_activation_id=lambda: 7,
        get_latest_generation_with_frame=lambda: 5,
        get_latest_generation_with_waveform=lambda: -1,
        get_latest_authoritative_frame=lambda: (9.9, 5, 7),
        get_waveform=lambda: (),
        get_waveform_count=lambda: 0,
        get_energy_bands=lambda: None,
        get_transient_energy_bands=lambda: None,
        get_floor_snapshot=lambda: None,
    )
    controller = VisualizerRuntimeController(
        runtime_generation=2,
        bar_count=4,
        initial_mode="spectrum",
        engine_factory=lambda _count: engine,
    )
    controller.engine = engine
    tall_presentation = _presentation(extent=(420.0, 420.0))
    controller.commit_presentation_metrics(tall_presentation)
    widget = SimpleNamespace(
        runtime_controller=controller,
        _engine=engine,
        _runtime_generation=2,
        _vis_mode_str="spectrum",
        _spotify_playing=True,
        _display_bars=[0.8, 0.6, 0.4, 0.2],
        _display_bars_source_generation=5,
        _display_bars_source_activation=7,
        _bar_count=4,
        _has_pushed_first_frame=False,
        _spectrum_visual_smoothing_enabled=True,
        _spectrum_visual_smoothing=0.5,
        _spectrum_single_piece=True,
        _spectrum_border_radius=4.0,
        _spectrum_ghosting_enabled=True,
        _spectrum_ghost_alpha=0.4,
        _spectrum_ghost_decay=0.4,
        _ghosting_enabled=True,
        _ghost_alpha=0.4,
        _ghost_decay_rate=0.4,
        _bar_fill_color=(10, 220, 80, 255),
        _bar_border_color=(255, 255, 255, 255),
        _dynamic_bar_segments=lambda: (_ for _ in ()).throw(
            AssertionError("legacy QWidget geometry was queried")
        ),
    )

    captured = capture_legacy_visualizer_logical_frame(
        widget,
        now_ts=10.0,
        changed=True,
        mode_reveal_ready=True,
    )

    assert isinstance(captured.mode_state, SpectrumFrame)
    assert captured.common.bars == pytest.approx((0.8, 0.6, 0.4, 0.2))
    assert captured.mode_state.peaks == pytest.approx(captured.common.bars)
    assert captured.mode_state.ghost_bars == pytest.approx(
        captured.mode_state.peaks
    )
    assert captured.mode_state.parameters[
        "spectrum_height_scale"
    ] == pytest.approx(compute_spectrum_height_scale(420.0))
    state = controller.resolve_logical_mode_state(
        "spectrum",
        SpectrumFrameRuntime,
    )
    assert state._spectrum_solid_hysteresis_segments == 64
    assert not hasattr(widget, "_qtquick_spectrum_frame_runtime")
    assert not hasattr(widget, "_qtquick_visualizer_viewport_height")
    widget._display_bars[0] = 0.0
    assert captured.common.bars[0] == pytest.approx(0.8)
