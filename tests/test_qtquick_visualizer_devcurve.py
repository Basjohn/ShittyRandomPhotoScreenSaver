"""Focused Phase-D DevCurve logical ownership and Qt Quick regressions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.settings.visualizer_mode_registry import (
    get_visualizer_presentation_policy,
)
from rendering.quick.visualizer.implementations.devcurve import (
    QuickDevCurveRenderer,
    compute_quick_devcurve_layout,
)
from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
from widgets.spotify_visualizer.logical_frame_capture import capture_visualizer_logical_frame
from widgets.spotify_visualizer.devcurve_frame_runtime import (
    DevCurveFrameRuntime,
)
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.render_state import (
    VisualizerEnergyState,
    VisualizerTransientState,
)
from widgets.spotify_visualizer.runtime_controller import (
    VisualizerRuntimeController,
)
from widgets.spotify_visualizer.shaders import load_fragment_shader


_LAYERS = ("bass", "vocals", "mids", "transients")


def _nodes():
    return {
        name: [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]]
        for name in _LAYERS
    }


def _parameters(*, ghosting: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "devcurve_base_level": 0.58,
        "devcurve_motion_power": 1.0,
        "devcurve_idle_motion": 0.2,
        "devcurve_idle_speed": 0.6,
        "devcurve_smoothness": 0.55,
        "devcurve_ghosting_enabled": ghosting,
        "devcurve_ghost_alpha": 0.65 if ghosting else 0.0,
        "devcurve_ghost_decay": 0.4,
        "devcurve_foreground_shadow_enabled": True,
        "devcurve_foreground_shadow_alpha": 0.36,
        "devcurve_foreground_shadow_darken": 0.42,
        "devcurve_foreground_shadow_offset": 0.10,
        "devcurve_foreground_specular_enabled": True,
        "devcurve_foreground_specular_alpha": 0.78,
        "devcurve_foreground_specular_width": 0.022,
        "devcurve_foreground_specular_offset": 0.028,
        "devcurve_foreground_specular_crest_bias": 1.05,
        "rainbow_enabled": False,
        "rainbow_speed": 0.5,
    }
    defaults = {
        "bass": ((82, 167, 255, 230), 0.55, 1.0, 0.0),
        "vocals": ((136, 190, 255, 220), 0.42, 1.0, -0.01),
        "mids": ((100, 145, 255, 220), 0.46, 1.0, 0.01),
        "transients": ((215, 240, 255, 240), 0.66, 1.15, 0.0),
    }
    for index, name in enumerate(_LAYERS):
        color, alpha, power, offset = defaults[name]
        prefix = f"devcurve_layer_{name}"
        values.update(
            {
                f"{prefix}_enabled": True,
                f"{prefix}_color": color,
                f"{prefix}_alpha": alpha,
                f"{prefix}_power": power,
                f"{prefix}_offset": offset,
                f"{prefix}_outline_color": (255, 255, 255, 255),
                f"{prefix}_outline_width": 0.006,
                f"{prefix}_order": index + 1,
            }
        )
    return values


def _advance(
    runtime: DevCurveFrameRuntime,
    *,
    now_ts: float,
    playing: bool = True,
    source_generation: int = 5,
    source_activation_id: int = 7,
    energy: VisualizerEnergyState = VisualizerEnergyState(
        bass=0.7,
        mid=0.5,
        high=0.3,
        overall=0.6,
    ),
    transient: VisualizerTransientState = VisualizerTransientState(bass=0.8),
    parameters: dict[str, object] | None = None,
):
    return runtime.advance(
        now_ts=now_ts,
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        source_generation=source_generation,
        source_activation_id=source_activation_id,
        source_timestamp=now_ts - 0.01,
        playing=playing,
        energy=energy,
        transient=transient,
        layer_shape_nodes=_nodes(),
        parameters=_parameters() if parameters is None else parameters,
    )


def test_devcurve_frame_capture_uses_presentation_owned_rainbow_state() -> None:
    controller = VisualizerRuntimeController(
        runtime_generation=2,
        initial_mode="devcurve",
    )
    runtime = DevCurveFrameRuntime()
    controller.resolve_logical_mode_state("devcurve", lambda: runtime)
    assert _advance(
        runtime,
        now_ts=5.0,
        parameters=_parameters(),
    ) is not None

    apply_presentation_vis_mode_kwargs(
        controller.presentation_state,
        {"devcurve_rainbow_enabled": True, "devcurve_rainbow_speed": 0.8},
    )
    widget = SimpleNamespace(
        _vis_mode_str="devcurve",
        runtime_controller=controller,
        presentation_config_host=controller.presentation_state,
        _engine=None,
        _runtime_generation=2,
        _spotify_playing=True,
        _has_pushed_first_frame=True,
        _display_bars_source_generation=5,
        _display_bars_source_activation=7,
    )

    frame = capture_visualizer_logical_frame(
        widget,
        now_ts=5.1,
        changed=True,
        mode_reveal_ready=True,
    )
    assert frame is not None
    assert frame.mode_state.parameters["rainbow_enabled"] is True
    assert frame.mode_state.parameters["rainbow_speed"] == pytest.approx(0.8)


def test_devcurve_runtime_freezes_layers_tuning_and_source_identity() -> None:
    runtime = DevCurveFrameRuntime()
    parameters = _parameters()
    nodes = _nodes()
    resolved = runtime.advance(
        now_ts=3.0,
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        source_generation=5,
        source_activation_id=7,
        source_timestamp=2.99,
        playing=True,
        energy=VisualizerEnergyState(bass=0.8, mid=0.6, high=0.4, overall=0.7),
        transient=VisualizerTransientState(bass=0.9),
        layer_shape_nodes=nodes,
        parameters=parameters,
    )

    assert resolved is not None
    parameters["devcurve_layer_bass_alpha"] = 0.0
    nodes["bass"][0][1] = 0.0
    assert resolved.runtime_generation == 2
    assert resolved.engine_generation == 5
    assert resolved.activation_id == 7
    assert resolved.source_generation == 5
    assert resolved.source_activation_id == 7
    assert resolved.reactive_source_ready is True
    assert tuple(name for name, _curve in resolved.curves) == _LAYERS
    assert all(len(curve) == 96 for _name, curve in resolved.curves)
    assert resolved.parameters["devcurve_layer_bass_alpha"] == pytest.approx(0.55)
    assert resolved.parameters["devcurve_layer_bass_shape_nodes"][0][1] == (
        pytest.approx(0.58)
    )
    assert resolved.parameters["devcurve_layer_vocals_offset"] == pytest.approx(
        -0.01
    )
    assert "devcurve_growth" not in resolved.parameters


def test_devcurve_stale_playing_source_is_zeroed_but_paused_idle_stays_alive() -> None:
    stale_runtime = DevCurveFrameRuntime()
    stale = _advance(
        stale_runtime,
        now_ts=4.0,
        source_generation=4,
        energy=VisualizerEnergyState(bass=1.0, mid=1.0, high=1.0, overall=1.0),
        transient=VisualizerTransientState(bass=1.0),
    )

    assert stale is not None
    assert stale.reactive_source_ready is False
    assert stale.source_generation == -1
    assert stale.source_activation_id == -1
    assert stale.energy == VisualizerEnergyState()
    assert stale.transient == VisualizerTransientState()
    assert all(
        value == pytest.approx(0.0)
        for value in stale.diagnostics["energies"].values()
    )

    idle_runtime = DevCurveFrameRuntime()
    idle = _advance(
        idle_runtime,
        now_ts=4.0,
        playing=False,
        energy=VisualizerEnergyState(bass=1.0, overall=1.0),
    )
    assert idle is not None
    assert idle.reactive_source_ready is False
    assert idle.source_generation == -1
    assert idle.energy.bass > 0.0
    assert idle.diagnostics["idle_amplitude"] > 0.0
    assert any(len(curve) == 96 for _name, curve in idle.curves)


def test_devcurve_shader_does_not_render_migration_invented_ghost_layers() -> None:
    source = load_fragment_shader("devcurve")
    assert source is not None
    assert "u_devcurve_ghost_curve_" not in source
    assert "u_devcurve_ghost_enabled" not in source


def test_devcurve_quick_aa_keeps_historical_logical_pixel_width() -> None:
    source = load_fragment_shader("devcurve")
    assert source is not None
    assert "float aa = max(1.15 / max(inner_h, 1.0), _quick_norm_y(0.0010));" in source
    assert "1.15 * authoredScale" not in source
    assert "uniform float u_visual_scale" not in source


def test_devcurve_transient_layer_preserves_historical_bass_only_input() -> None:
    mid_high_only = _advance(
        DevCurveFrameRuntime(),
        now_ts=4.5,
        transient=VisualizerTransientState(bass=0.0, mid=1.2, high=1.4),
    )
    bass_hit = _advance(
        DevCurveFrameRuntime(),
        now_ts=4.5,
        transient=VisualizerTransientState(bass=0.8, mid=0.0, high=0.0),
    )

    assert mid_high_only is not None and bass_hit is not None
    assert mid_high_only.diagnostics["energies"]["transients"] == pytest.approx(
        0.0
    )
    assert bass_hit.diagnostics["energies"]["transients"] > 0.0


def test_devcurve_ghost_settings_remain_visual_noop_for_historical_parity() -> None:
    runtime = DevCurveFrameRuntime()
    first = _advance(runtime, now_ts=5.0)
    second = _advance(
        runtime,
        now_ts=5.05,
        energy=VisualizerEnergyState(bass=0.1, mid=0.2, high=0.9, overall=0.5),
    )

    assert first is not None and second is not None
    assert second.curves != first.curves
    # The pre-migration shader accepted the persisted ghost controls but never
    # sampled a ghost curve. Quick must not invent duplicate filled/outlined
    # layers merely because the saved preset has ghosting=true.
    assert first.parameters["devcurve_ghosting_enabled"] is True
    assert first.parameters["devcurve_ghost_alpha"] == pytest.approx(0.65)
    assert first.ghost_curves == ()
    assert second.ghost_curves == ()


def test_devcurve_runtime_retirement_is_authoritative() -> None:
    controller = VisualizerRuntimeController(
        runtime_generation=2,
        initial_mode="devcurve",
    )
    runtime = DevCurveFrameRuntime()
    assert controller.resolve_logical_mode_state(
        "devcurve",
        lambda: runtime,
    ) is runtime
    assert _advance(runtime, now_ts=6.0) is not None

    controller.set_mode("spectrum")

    assert runtime.latest.curves == ()
    assert controller.peek_logical_mode_state("devcurve") is None
    assert _advance(runtime, now_ts=6.1) is None


def _presentation(
    *,
    scale: float = 1.0,
    extent: tuple[float, float] = (420.0, 280.0),
):
    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("devcurve"),
        display_size=(1920.0, 1080.0),
        outer_origin=(120.0, 80.0),
        uniform_visual_scale=scale,
        viewport_extent=extent,
        border_width=4.0,
        corner_radius=8.0,
    )


def _layout(presentation):
    outer_x, outer_y, _outer_width, _outer_height = presentation.outer_rect
    content_x, content_y, content_width, content_height = presentation.content_rect
    scale = presentation.uniform_visual_scale
    authored_inset = presentation.border_width / scale
    baseline_width, baseline_height = presentation.baseline_viewport_size
    return compute_quick_devcurve_layout(
        local_content_rect=(
            content_x - outer_x,
            content_y - outer_y,
            content_width,
            content_height,
        ),
        visual_scale=scale,
        baseline_content_extent=(
            baseline_width - 2.0 * authored_inset,
            baseline_height - 2.0 * authored_inset,
        ),
    )


def test_devcurve_layout_reflows_domain_and_keeps_authored_stroke_scale() -> None:
    canonical = _layout(_presentation())
    scaled = _layout(_presentation(scale=0.65))
    wide = _layout(_presentation(extent=(560.0, 280.0)))
    tall = _layout(_presentation(extent=(420.0, 420.0)))

    assert scaled.content_rect[2] == pytest.approx(canonical.content_rect[2] * 0.65)
    assert scaled.content_rect[3] == pytest.approx(canonical.content_rect[3] * 0.65)
    assert canonical.normalized_x_scale == pytest.approx(1.0)
    assert canonical.normalized_y_scale == pytest.approx(1.0)
    assert scaled.normalized_x_scale == pytest.approx(1.0)
    assert scaled.normalized_y_scale == pytest.approx(1.0)
    assert wide.normalized_x_scale < 1.0
    assert wide.normalized_y_scale == pytest.approx(1.0)
    assert tall.normalized_x_scale == pytest.approx(1.0)
    assert tall.normalized_y_scale < 1.0


def test_quick_devcurve_registry_is_static_lazy_and_resource_dormant(
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
    imported: list[str] = []
    real_import = implementation_registry.import_module

    def _tracked_import(name: str):
        imported.append(name)
        return real_import(name)

    monkeypatch.setattr(implementation_registry, "import_module", _tracked_import)
    implementation_registry.iter_quick_visualizer_implementations()
    assert imported == []

    renderer = implementation_registry.resolve_quick_visualizer_renderer(
        "devcurve"
    )
    assert isinstance(renderer, QuickDevCurveRenderer)
    assert renderer.has_resources is False
    assert imported == [
        "rendering.quick.visualizer.implementations.devcurve"
    ]


def test_quick_devcurve_renderer_has_no_legacy_presentation_dependency() -> None:
    module = __import__(
        QuickDevCurveRenderer.__module__,
        fromlist=["QuickDevCurveRenderer"],
    )
    source = module.__loader__.get_source(QuickDevCurveRenderer.__module__)

    assert "SpotifyVisualizerWidget" not in source
    assert "spotify_bars_gl_overlay" not in source
    assert "renderers.devcurve" not in source
    assert "devcurve_growth" not in source
    assert "gl_FragCoord" not in source
