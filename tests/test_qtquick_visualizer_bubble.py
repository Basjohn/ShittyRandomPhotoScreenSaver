"""Focused Phase-D Bubble logical ownership and Quick renderer regressions."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from core.settings.visualizer_mode_registry import (
    get_visualizer_presentation_policy,
)
from rendering.quick.visualizer.implementations.bubble import (
    QuickBubbleRenderer,
    compute_quick_bubble_layout,
    resolve_quick_bubble_payload,
)
from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime
from widgets.spotify_visualizer.presentation_geometry import (
    resolve_visualizer_presentation,
)
from widgets.spotify_visualizer.render_state import (
    BubbleFrame,
    VisualizerCommonState,
    VisualizerLogicalFrame,
    VisualizerProtectedEdge,
    compose_visualizer_render_snapshot,
    freeze_render_fields,
)
from widgets.spotify_visualizer.runtime_controller import (
    VisualizerRuntimeController,
)


def _presentation(
    *,
    scale: float = 1.0,
    extent: tuple[float, float] = (420.0, 280.0),
):
    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("bubble"),
        display_size=(1920.0, 1080.0),
        outer_origin=(120.0, 80.0),
        uniform_visual_scale=scale,
        viewport_extent=extent,
        border_width=4.0,
        corner_radius=8.0,
    )


def _logical(
    *,
    positions=(0.25, 0.5, 0.04, 1.0),
    extras=(0.8, 0.0, 0.0, 0.0),
    trails=(),
    protected_edges=(),
) -> VisualizerLogicalFrame:
    return VisualizerLogicalFrame(
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        source_generation=5,
        source_activation_id=7,
        mode_id="bubble",
        playing=True,
        logical_timestamp=10.0,
        source_timestamp=9.99,
        changed=True,
        present_frame=True,
        mode_reveal_ready=True,
        common=VisualizerCommonState(bars=(), bar_count=0),
        mode_state=BubbleFrame(
            positions=tuple(positions),
            extras=tuple(extras),
            trails=tuple(trails),
            bubble_count=1,
            source_timestamp=9.99,
            simulation_timestamp=10.0,
            parameters=freeze_render_fields(
                {
                    "bubble_trail_strength": 0.8,
                    "bubble_tail_opacity": 0.5,
                    "bubble_ghosting_enabled": True,
                    "bubble_ghost_alpha": 0.4,
                    "bubble_specular_direction": "top_left",
                    "bubble_gradient_direction": "top",
                }
            ),
        ),
        protected_edges=tuple(protected_edges),
    )


def _snapshot(**logical_kwargs):
    return compose_visualizer_render_snapshot(
        _logical(**logical_kwargs),
        _presentation(),
        logical_revision=1,
    )


def test_bubble_frame_runtime_freezes_one_authored_step_and_visible_event() -> None:
    output_positions = [0.2, 0.4, 0.07, 1.0]

    class _Simulation:
        count = 1

        def tick(self, dt, energy, settings):
            assert dt == pytest.approx(0.01)
            assert energy["bass"] == pytest.approx(0.8)
            event = settings["_event_scheduler"].consume_next(
                "kick",
                max_age_s=0.3,
            )
            assert event.strength == pytest.approx(1.0)

        def snapshot(self, **_pulse):
            return output_positions, [0.9, 0.0, 0.0, 0.0], []

        @staticmethod
        def get_perf_diagnostics():
            return {"tick_ms": 0.04}

        @staticmethod
        def reset():
            return None

    scheduler = SimpleNamespace(
        consume_next=lambda name, max_age_s: SimpleNamespace(
            strength=1.0,
            timestamp=4.99,
        )
        if name == "kick" and max_age_s == pytest.approx(0.3)
        else None
    )
    runtime = BubbleFrameRuntime(simulation_factory=_Simulation)
    resolved = runtime.advance(
        dt=0.01,
        energy={"bass": 0.8},
        settings={"_event_scheduler": scheduler},
        pulse={"bass": 0.8},
        source_timestamp=4.98,
        authored_timestamp=5.0,
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        playing=True,
        source_ready=True,
        source_generation=5,
        source_activation_id=7,
        edge_token=3,
    )

    output_positions[2] = 0.0
    assert resolved.positions == pytest.approx((0.2, 0.4, 0.07, 1.0))
    perf = dict(resolved.perf_diagnostics)
    assert perf["tick_ms"] == pytest.approx(0.04)
    assert perf["integration_total_ms"] >= 0.0
    assert perf["result_count"] == 1.0
    assert resolved.runtime_generation == 2
    assert resolved.engine_generation == 5
    assert resolved.activation_id == 7
    assert resolved.source_generation == 5
    assert resolved.source_activation_id == 7
    assert len(resolved.protected_edges) == 1
    edge = resolved.protected_edges[0]
    assert edge.token == 3
    assert edge.kind == "bubble_visible_result"
    assert edge.result["positions"] == pytest.approx(resolved.positions)
    assert edge.result["event_kinds"] == ("kick",)


def test_stale_playing_source_cannot_feed_energy_or_consume_event() -> None:
    observed: dict[str, object] = {}

    class _Simulation:
        count = 0

        def tick(self, _dt, energy, settings):
            observed["energy"] = dict(energy)
            observed["event"] = settings["_event_scheduler"].consume_next(
                "kick",
                max_age_s=0.3,
            )

        @staticmethod
        def snapshot(**pulse):
            observed["pulse"] = dict(pulse)
            return [], [], []

        @staticmethod
        def reset():
            return None

    scheduler_calls: list[str] = []
    runtime = BubbleFrameRuntime(simulation_factory=_Simulation)
    resolved = runtime.advance(
        dt=0.01,
        energy={"bass": 0.9, "mid": 0.4},
        settings={
            "_event_scheduler": SimpleNamespace(
                consume_next=lambda name, **_kwargs: scheduler_calls.append(name)
            )
        },
        pulse={"bass": 0.9},
        source_timestamp=10.0,
        authored_timestamp=10.1,
        runtime_generation=2,
        engine_generation=5,
        activation_id=7,
        playing=True,
        source_ready=False,
        source_generation=5,
        source_activation_id=7,
        edge_token=1,
    )

    assert observed["energy"] == {"bass": 0.0, "mid": 0.0}
    assert observed["pulse"]["bass"] == 0.0
    assert observed["pulse"]["mid_high"] == 0.0
    assert observed["event"] is None
    assert scheduler_calls == []
    assert resolved.source_timestamp == 0.0
    assert resolved.source_generation == -1
    assert resolved.source_activation_id == -1
    assert resolved.protected_edges == ()


def test_bubble_retirement_waits_for_inflight_step_then_clears_state() -> None:
    tick_started = threading.Event()
    release_tick = threading.Event()
    retirement_finished = threading.Event()
    errors: list[BaseException] = []

    class _BlockingSimulation:
        count = 1

        def __init__(self) -> None:
            self.reset_calls = 0

        def tick(self, _dt, _energy, _settings) -> None:
            tick_started.set()
            if not release_tick.wait(timeout=1.0):
                raise TimeoutError("Bubble test step was not released")

        @staticmethod
        def snapshot(**_pulse):
            return [0.2, 0.3, 0.05, 1.0], [0.0] * 4, []

        def reset(self) -> None:
            self.reset_calls += 1

    controller = VisualizerRuntimeController(
        runtime_generation=4,
        initial_mode="bubble",
    )
    runtime = BubbleFrameRuntime(simulation_factory=_BlockingSimulation)
    assert controller.resolve_logical_mode_state(
        "bubble",
        lambda: runtime,
    ) is runtime

    def _advance() -> None:
        try:
            runtime.advance(
                dt=0.016,
                energy={"bass": 0.5},
                settings={},
                pulse={"bass": 0.5},
                source_timestamp=2.0,
                authored_timestamp=2.01,
                runtime_generation=4,
                engine_generation=8,
                activation_id=3,
                playing=True,
                source_ready=True,
                source_generation=8,
                source_activation_id=3,
                edge_token=1,
            )
        except BaseException as exc:  # pragma: no cover - assertion reports it
            errors.append(exc)

    def _retire() -> None:
        try:
            controller.set_mode("sine_wave")
        except BaseException as exc:  # pragma: no cover - assertion reports it
            errors.append(exc)
        finally:
            retirement_finished.set()

    advance_thread = threading.Thread(target=_advance, daemon=True)
    advance_thread.start()
    assert tick_started.wait(timeout=1.0)

    retirement_thread = threading.Thread(target=_retire, daemon=True)
    retirement_thread.start()
    assert not retirement_finished.wait(timeout=0.05)

    release_tick.set()
    advance_thread.join(timeout=1.0)
    retirement_thread.join(timeout=1.0)

    assert not advance_thread.is_alive()
    assert not retirement_thread.is_alive()
    assert errors == []
    simulation = runtime.simulation
    assert isinstance(simulation, _BlockingSimulation)
    assert simulation.reset_calls == 1
    assert runtime.latest.positions == ()
    assert controller.mode_id == "sine_wave"
    assert controller.peek_logical_mode_state("bubble") is None
    assert runtime.advance(
        dt=0.016,
        energy={"bass": 1.0},
        settings={},
        pulse={"bass": 1.0},
        source_timestamp=3.0,
        authored_timestamp=3.01,
        runtime_generation=4,
        engine_generation=8,
        activation_id=3,
        playing=True,
        source_ready=True,
        source_generation=8,
        source_activation_id=3,
        edge_token=2,
    ) is None
    assert simulation.reset_calls == 1


def test_quick_bubble_payload_uses_protected_result_without_fifo_replay() -> None:
    edge = VisualizerProtectedEdge(
        token=4,
        kind="bubble_visible_result",
        authored_timestamp=9.9,
        result_timestamp=10.0,
        result=freeze_render_fields(
            {
                "positions": (0.7, 0.4, 0.09, 1.0),
                "extras": (1.0, 0.0, 0.0, 0.0),
                "trails": (),
                "bubble_count": 1,
            }
        ),
    )
    payload = resolve_quick_bubble_payload(_snapshot(protected_edges=(edge,)))

    assert payload.protected is True
    assert payload.positions[0] == pytest.approx(0.7)
    assert payload.positions[2] == pytest.approx(0.09)

    current = resolve_quick_bubble_payload(_snapshot())
    assert current.protected is False
    assert current.positions[0] == pytest.approx(0.25)


def _layout(presentation):
    outer_x, outer_y, _width, _height = presentation.outer_rect
    content_x, content_y, content_width, content_height = (
        presentation.content_rect
    )
    return compute_quick_bubble_layout(
        local_content_rect=(
            content_x - outer_x,
            content_y - outer_y,
            content_width,
            content_height,
        ),
        visual_scale=presentation.uniform_visual_scale,
    )


def test_bubble_layout_scales_uniformly_and_keeps_circle_radii_isotropic() -> None:
    canonical = _layout(_presentation())
    scaled = _layout(_presentation(scale=0.65))
    wide = _layout(_presentation(extent=(560.0, 280.0)))
    tall = _layout(_presentation(extent=(420.0, 420.0)))

    assert scaled.content_rect[2] == pytest.approx(canonical.content_rect[2] * 0.65)
    assert scaled.content_rect[3] == pytest.approx(canonical.content_rect[3] * 0.65)
    assert wide.aspect_ratio > canonical.aspect_ratio > tall.aspect_ratio
    radius = 0.04
    for layout in (canonical, scaled, wide, tall):
        # Shader X distance is multiplied by aspect, so the normalized X
        # radius is r/aspect and maps to the same physical radius as Y.
        x_radius_px = (radius / layout.aspect_ratio) * layout.content_rect[2]
        y_radius_px = radius * layout.content_rect[3]
        assert x_radius_px == pytest.approx(y_radius_px)


def test_quick_bubble_registry_is_static_lazy_and_resource_dormant() -> None:
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
    renderer = resolve_quick_visualizer_renderer("bubble")
    assert isinstance(renderer, QuickBubbleRenderer)
    assert renderer.has_resources is False


def test_quick_bubble_renderer_has_no_live_widget_or_simulation_dependency() -> None:
    module = __import__(
        QuickBubbleRenderer.__module__,
        fromlist=["QuickBubbleRenderer"],
    )
    source = module.__loader__.get_source(QuickBubbleRenderer.__module__)
    assert "SpotifyVisualizerWidget" not in source
    assert "BubbleSimulation" not in source
    assert "QWidget" not in source
    assert "gl_FragCoord" not in source
