"""Focused Phase-D Spectrum immutable-state and Quick geometry regressions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.settings.visualizer_mode_registry import (
    get_visualizer_presentation_policy,
)
from widgets.spotify_visualizer import mode_capabilities
from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
from widgets.spotify_visualizer.logical_frame_capture import capture_visualizer_logical_frame
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


def test_spectrum_frame_capture_advances_rainbow_from_presentation_owner() -> None:
    controller = VisualizerRuntimeController(
        runtime_generation=2,
        initial_mode="spectrum",
    )
    apply_presentation_vis_mode_kwargs(
        controller.presentation_state,
        {"spectrum_rainbow_enabled": True, "spectrum_rainbow_speed": 0.7},
    )
    widget = SimpleNamespace(
        _vis_mode_str="spectrum",
        runtime_controller=controller,
        presentation_config_host=controller.presentation_state,
        _engine=None,
        _runtime_generation=2,
        _spotify_playing=True,
        _has_pushed_first_frame=True,
        _display_bars=(0.2, 0.6, 0.9, 0.4),
        _bar_count=4,
        _display_bars_source_generation=5,
        _display_bars_source_activation=7,
        _spectrum_visual_smoothing_enabled=False,
        _spectrum_visual_smoothing=0.5,
        _spectrum_single_piece=False,
        _spectrum_ghosting_enabled=False,
        _spectrum_ghost_decay=0.4,
    )

    first = capture_visualizer_logical_frame(
        widget,
        now_ts=1.0,
        changed=True,
        mode_reveal_ready=True,
    )
    second = capture_visualizer_logical_frame(
        widget,
        now_ts=1.5,
        changed=True,
        mode_reveal_ready=True,
    )

    assert first is not None and second is not None
    assert first.mode_state.parameters["rainbow_enabled"] is True
    assert second.mode_state.parameters["rainbow_speed"] == pytest.approx(0.7)
    assert second.mode_state.animation_time > first.mode_state.animation_time


def _resolve_runtime_frame(
    runtime: SpectrumFrameRuntime,
    bars,
    *,
    now_ts: float,
    playing: bool,
    first_frame: bool = False,
    smoothing_enabled: bool = False,
):
    return runtime.resolve(
        bars,
        bar_count=len(bars),
        now_ts=now_ts,
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        source_generation=5 if playing else -1,
        source_activation_id=7 if playing else -1,
        playing=playing,
        first_frame=first_frame,
        smoothing_enabled=smoothing_enabled,
        smoothing_strength=0.5,
        single_piece=False,
        segments=53,
        ghosting_enabled=False,
        ghost_decay=0.4,
        animation_enabled=False,
    )


def test_spectrum_pause_edge_falls_slowly_but_natural_active_drop_is_unchanged() -> None:
    runtime = SpectrumFrameRuntime()
    live = _resolve_runtime_frame(
        runtime, [0.92, 0.78, 0.64, 0.50], now_ts=1.0, playing=True, first_frame=True
    )
    natural_drop = _resolve_runtime_frame(
        runtime, [0.18, 0.16, 0.14, 0.12], now_ts=1.016, playing=True
    )
    assert natural_drop.bars == pytest.approx((0.18, 0.16, 0.14, 0.12))

    # Rebuild a high live scene, then only the explicit playing->paused edge gets
    # the deliberately slow presentation-owned fall.
    live_again = _resolve_runtime_frame(
        runtime, [0.90, 0.80, 0.70, 0.60], now_ts=1.032, playing=True
    )
    paused_edge = _resolve_runtime_frame(
        runtime, [0.0, 0.0, 0.0, 0.0], now_ts=1.048, playing=False
    )
    paused_mid = _resolve_runtime_frame(
        runtime, [0.0, 0.0, 0.0, 0.0], now_ts=1.448, playing=False
    )
    paused_later = _resolve_runtime_frame(
        runtime, [0.0, 0.0, 0.0, 0.0], now_ts=2.038, playing=False
    )
    paused_settled = _resolve_runtime_frame(
        runtime, [0.0, 0.0, 0.0, 0.0], now_ts=2.738, playing=False
    )

    assert paused_edge.bars == pytest.approx(live_again.bars)
    assert paused_mid.bars[0] > 0.70
    assert paused_later.bars[0] < paused_mid.bars[0]
    assert max(paused_settled.bars) < 0.30
    assert paused_settled.changed is True


def test_spectrum_resume_mid_pause_descent_waits_for_fresh_source_then_hands_back_cleanly() -> None:
    runtime = SpectrumFrameRuntime()
    live = _resolve_runtime_frame(
        runtime, [0.88, 0.72, 0.56, 0.40], now_ts=1.0, playing=True, first_frame=True
    )
    _resolve_runtime_frame(
        runtime, [0.0, 0.0, 0.0, 0.0], now_ts=1.016, playing=False
    )
    descending = _resolve_runtime_frame(
        runtime, [0.0, 0.0, 0.0, 0.0], now_ts=1.616, playing=False
    )

    # Resume before a current-activation source exists: keep the presentation
    # exactly where the pause handoff left it and do not grant reactive authority.
    waiting = runtime.resolve(
        [0.99, 0.99, 0.99, 0.99],
        bar_count=4,
        now_ts=1.632,
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        source_generation=4,
        source_activation_id=7,
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
    assert waiting.bars == pytest.approx(descending.bars)
    assert waiting.reactive_source_ready is False

    # The first fresh source owns presentation immediately; no pause animation
    # survives across the fresh-source authority boundary.
    fresh = _resolve_runtime_frame(
        runtime, [0.62, 0.48, 0.34, 0.20], now_ts=1.648, playing=True
    )
    assert fresh.bars == pytest.approx((0.62, 0.48, 0.34, 0.20))
    assert fresh.reactive_source_ready is True
    assert fresh.bars != pytest.approx(live.bars)


def test_paused_spectrum_idle_energy_travels_left_to_right_on_existing_clock() -> None:
    runtime = SpectrumFrameRuntime()
    initial = _resolve_runtime_frame(
        runtime, [0.0] * 6, now_ts=1.0, playing=False, first_frame=True
    )
    left_rising = _resolve_runtime_frame(
        runtime, [0.0] * 6, now_ts=1.5, playing=False
    )
    left_peak = _resolve_runtime_frame(
        runtime, [0.0] * 6, now_ts=2.1, playing=False
    )
    handoff = _resolve_runtime_frame(
        runtime, [0.0] * 6, now_ts=2.65, playing=False
    )
    second_peak = _resolve_runtime_frame(
        runtime, [0.0] * 6, now_ts=3.2, playing=False
    )

    assert left_rising.bars[0] > initial.bars[0]
    assert left_peak.bars[0] > left_rising.bars[0]
    assert handoff.bars[0] > initial.bars[0]
    assert handoff.bars[1] > initial.bars[1]
    assert second_peak.bars[1] > handoff.bars[1]
    assert second_peak.bars[0] < handoff.bars[0]


def test_spectrum_idle_motion_stays_presentation_owned_for_mode_isolation() -> None:
    assert mode_capabilities.has_presentation_owned_idle_scene("spectrum") is True
    assert mode_capabilities.is_idle_self_animating("spectrum") is False
    assert mode_capabilities.requires_authoritative_first_source("spectrum") is True


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
    count = 16
    canonical_pres = _presentation()
    scaled_pres = _presentation(scale=0.65)
    canonical = _layout(canonical_pres, count)
    scaled = _layout(scaled_pres, count)
    wide = _layout(_presentation(extent=(560.0, 280.0)), count)
    tall = _layout(_presentation(extent=(420.0, 420.0)), count)

    # Visible border obeys the bounded/non-linear stroke rule: authored 4px clamps
    # to 3.3px at 0.65x, not a naive 2.6px. Pure scale-derived bar metrics still
    # scale uniformly; anything derived from the border-inset content geometry
    # differs from a naive 0.65x by exactly the bounded border delta.
    assert canonical_pres.border_width == pytest.approx(4.0)
    assert scaled_pres.border_width == pytest.approx(3.3)
    border_delta = scaled_pres.border_width - canonical_pres.border_width * 0.65
    assert border_delta == pytest.approx(0.7)

    # bar_gap is a pure function of visual scale, so it scales uniformly, as do the
    # scale-only segment/height metrics.
    assert scaled.bar_gap == pytest.approx(canonical.bar_gap * 0.65)
    assert scaled.segment_count == canonical.segment_count
    assert scaled.height_scale == pytest.approx(canonical.height_scale)

    # bars_left = content-origin (the border inset) + scale-derived margins, so it
    # shifts from a naive 0.65x by exactly +border_delta.
    assert scaled.bars_left == pytest.approx(canonical.bars_left * 0.65 + border_delta)

    # The bar field lives inside content_width (= outer - 2*border), whose only
    # non-uniform term is the bounded border. bar_span carries the whole -2*delta;
    # bar_width carries that same content-width delta shared across the bars.
    assert scaled.bar_span == pytest.approx(canonical.bar_span * 0.65 - 2.0 * border_delta)
    assert scaled.bar_width == pytest.approx(
        canonical.bar_width * 0.65 - (2.0 * border_delta) / count
    )

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


def test_all_five_modes_claim_viewport_resize_capability() -> None:
    # G4 deterministic reflow is complete for every mode, including Bubble's
    # baseline-relative logical domain, so all five are viewport-resize-capable.
    for mode_id in ("spectrum", "oscilloscope", "sine_wave", "devcurve", "bubble"):
        assert get_visualizer_presentation_policy(mode_id).viewport_resize_capable


def test_quick_spectrum_registry_is_static_and_lazy() -> None:
    from rendering.quick.visualizer.implementation_registry import (
        iter_quick_visualizer_implementations,
        resolve_quick_visualizer_renderer,
    )

    descriptors = iter_quick_visualizer_implementations()
    assert tuple(descriptor.mode_id for descriptor in descriptors) == (
        "spectrum",
        "oscilloscope",
        "sine_wave",
        "bubble",
        "devcurve",
    )
    assert all(isinstance(descriptor.module_name, str) for descriptor in descriptors)
    renderer = resolve_quick_visualizer_renderer("spectrum")
    assert renderer is not None
    assert renderer.mode_id == "spectrum"
    assert renderer.has_resources is False
    oscilloscope = resolve_quick_visualizer_renderer("oscilloscope")
    assert oscilloscope is not None
    assert oscilloscope.mode_id == "oscilloscope"
    assert oscilloscope.has_resources is False
    sine = resolve_quick_visualizer_renderer("sine_wave")
    assert sine is not None
    assert sine.mode_id == "sine_wave"
    assert sine.has_resources is False
    bubble = resolve_quick_visualizer_renderer("bubble")
    assert bubble is not None
    assert bubble.mode_id == "bubble"
    assert bubble.has_resources is False
    devcurve = resolve_quick_visualizer_renderer("devcurve")
    assert devcurve is not None
    assert devcurve.mode_id == "devcurve"
    assert devcurve.has_resources is False




def test_spectrum_shader_separates_fill_border_and_ghost_rainbow_participation() -> None:
    from widgets.spotify_visualizer.shaders import load_fragment_shader

    source = load_fragment_shader("spectrum")
    assert source is not None
    assert "uniform int u_rainbow_fill" in source
    assert "? (u_rainbow_border == 1)" in source
    assert ": (u_rainbow_fill == 1)" in source
    # Ghost keeps the explicit per-bar rainbow path even when fill participation
    # is disabled, which is the Preset 1 Organs contract.
    assert "ghost_base = apply_spectrum_rainbow(ghost_base, bar_index)" in source
    assert "ghost = apply_spectrum_rainbow(ghost, bar_index)" in source


def test_organs_preset_keeps_black_fill_static_while_border_and_ghost_ride_rainbow() -> None:
    import json
    from pathlib import Path

    preset = json.loads(
        (Path(__file__).resolve().parents[1]
         / "presets" / "visualizer_modes" / "spectrum" / "preset_1_organs.json")
        .read_text(encoding="utf-8")
    )
    values = preset["snapshot"]["widgets"]["spotify_visualizer"]
    assert values["spectrum_rainbow_enabled"] is True
    assert values["spectrum_unique_colors"] is True
    # The near-black bar FILL stays out of the rainbow so the bar bodies read dark.
    assert values["spectrum_rainbow_fill"] is False
    # The later visual-parity/customization pass opted the white BORDER into the
    # rainbow (the shader keeps fill/border/ghost participation independent). The
    # curated preset is authoritative for this design choice.
    assert values["spectrum_rainbow_border"] is True
    assert values["spectrum_ghosting_enabled"] is True
