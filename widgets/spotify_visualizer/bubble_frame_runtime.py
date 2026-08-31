"""Authored Bubble state advanced by the sole visualizer logical clock."""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any, Callable

from widgets.spotify_visualizer.render_state import (
    VisualizerProtectedEdge,
    freeze_render_fields,
)


SimulationFactory = Callable[[], Any]


def _read_float_diagnostics(source: Any, method_name: str) -> dict[str, float]:
    method = getattr(source, method_name, None)
    if not callable(method):
        return {}
    try:
        return {
            str(name): float(value)
            for name, value in dict(method()).items()
        }
    except (TypeError, ValueError):
        return {}


class _EventRecorder:
    """Record consume-once source events without changing scheduler semantics."""

    def __init__(self, scheduler: Any) -> None:
        self._scheduler = scheduler
        self.consumed: list[tuple[str, float, float]] = []

    def consume_next(self, name: str, *, max_age_s: float):
        event = self._scheduler.consume_next(name, max_age_s=max_age_s)
        if event is not None:
            self.consumed.append(
                (
                    str(name),
                    float(getattr(event, "strength", 0.0) or 0.0),
                    float(getattr(event, "timestamp", 0.0) or 0.0),
                )
            )
        return event


class _NoEventScheduler:
    """Disable delta fallback when a playing source identity is stale."""

    @staticmethod
    def consume_next(_name: str, *, max_age_s: float):
        del max_age_s
        return None


@dataclass(frozen=True, slots=True)
class BubbleResolvedFrame:
    positions: tuple[float, ...] = ()
    extras: tuple[float, ...] = ()
    trails: tuple[float, ...] = ()
    bubble_count: int = 0
    source_timestamp: float = 0.0
    simulation_timestamp: float = 0.0
    runtime_generation: int = -1
    engine_generation: int = -1
    activation_id: int = -1
    source_generation: int = -1
    source_activation_id: int = -1
    playing: bool = False
    protected_edges: tuple[VisualizerProtectedEdge, ...] = ()
    perf_diagnostics: tuple[tuple[str, float], ...] = ()
    geometry_diagnostics: tuple[tuple[str, float], ...] = ()


class BubbleFrameRuntime:
    """Own one Bubble simulation and its latest immutable render result."""

    def __init__(
        self,
        simulation_factory: SimulationFactory | None = None,
    ) -> None:
        self._simulation_factory = simulation_factory
        self._lock = threading.RLock()
        self._simulation: Any = None
        self._activation_identity: tuple[int, int, int] | None = None
        self._latest = BubbleResolvedFrame()
        self._retired = False

    @property
    def simulation(self) -> Any:
        """Read-only diagnostics seam for the protected replay harness."""

        with self._lock:
            return self._simulation

    @property
    def latest(self) -> BubbleResolvedFrame:
        with self._lock:
            return self._latest

    def reset(self) -> None:
        with self._lock:
            self._reset_locked()

    def retire(self) -> None:
        """Permanently quiesce this generation-scoped mode state."""

        with self._lock:
            self._reset_locked()
            self._retired = True

    def _reset_locked(self) -> None:
        simulation = self._simulation
        if simulation is not None:
            reset = getattr(simulation, "reset", None)
            if callable(reset):
                reset()
        self._activation_identity = None
        self._latest = BubbleResolvedFrame()

    def _ensure_simulation(self) -> Any:
        if self._simulation is None:
            factory = self._simulation_factory
            if factory is None:
                from widgets.spotify_visualizer.bubble_simulation import (
                    BubbleSimulation,
                )

                factory = BubbleSimulation
            self._simulation = factory()
        return self._simulation

    def advance(
        self,
        *,
        dt: float,
        energy: dict[str, float],
        settings: dict[str, Any],
        pulse: dict[str, float],
        source_timestamp: float,
        authored_timestamp: float,
        runtime_generation: int,
        engine_generation: int,
        activation_id: int,
        playing: bool,
        source_ready: bool,
        source_generation: int,
        source_activation_id: int,
        edge_token: int,
        viewport_extent: tuple[float, float] | None = None,
    ) -> BubbleResolvedFrame | None:
        """Integrate exactly one authored step and freeze its visible result.

        ``viewport_extent`` is the latest committed CUSTOM logical world (or
        ``None`` for the canonical baseline). It is spatial configuration, not an
        authored temporal event: it enters the current step and coalesces freely,
        never creating a step or altering cadence.
        """

        with self._lock:
            if self._retired:
                return None
            return self._advance_locked(
                dt=dt,
                energy=energy,
                settings=settings,
                pulse=pulse,
                source_timestamp=source_timestamp,
                authored_timestamp=authored_timestamp,
                runtime_generation=runtime_generation,
                engine_generation=engine_generation,
                activation_id=activation_id,
                playing=playing,
                source_ready=source_ready,
                source_generation=source_generation,
                source_activation_id=source_activation_id,
                edge_token=edge_token,
                viewport_extent=viewport_extent,
            )

    def _advance_locked(
        self,
        *,
        dt: float,
        energy: dict[str, float],
        settings: dict[str, Any],
        pulse: dict[str, float],
        source_timestamp: float,
        authored_timestamp: float,
        runtime_generation: int,
        engine_generation: int,
        activation_id: int,
        playing: bool,
        source_ready: bool,
        source_generation: int,
        source_activation_id: int,
        edge_token: int,
        viewport_extent: tuple[float, float] | None = None,
    ) -> BubbleResolvedFrame:

        identity = (
            int(runtime_generation),
            int(engine_generation),
            int(activation_id),
        )
        if identity != self._activation_identity:
            self._reset_locked()
            self._activation_identity = identity

        energy_payload = dict(energy)
        pulse_payload = dict(pulse)
        settings_payload = dict(settings)
        # Latest spatial configuration for this authored step. The simulation
        # treats a canonical/None extent as a strict baseline no-op; a non-baseline
        # extent expands its logical domain. This is state, not a clock.
        settings_payload["_bubble_viewport_extent"] = viewport_extent
        event_recorder: _EventRecorder | None = None
        scheduler = settings_payload.get("_event_scheduler")
        if bool(playing) and not bool(source_ready):
            for name in tuple(energy_payload):
                energy_payload[name] = 0.0
            pulse_payload["bass"] = 0.0
            pulse_payload["mid_high"] = 0.0
            settings_payload["_event_scheduler"] = _NoEventScheduler()
            source_timestamp = 0.0
            source_generation = -1
            source_activation_id = -1
        elif scheduler is not None:
            event_recorder = _EventRecorder(scheduler)
            settings_payload["_event_scheduler"] = event_recorder

        integration_started = time.perf_counter()
        simulation = self._ensure_simulation()
        simulation.tick(float(dt), energy_payload, settings_payload)
        positions, extras, trails = simulation.snapshot(
            bass=float(pulse_payload.get("bass", 0.0)),
            mid_high=float(pulse_payload.get("mid_high", 0.0)),
            big_bass_pulse=float(pulse_payload.get("big_bass_pulse", 0.5)),
            small_freq_pulse=float(pulse_payload.get("small_freq_pulse", 0.5)),
            big_specular_max_size=float(
                pulse_payload.get("big_specular_max_size", 2.5)
            ),
            big_visual_smoothing=float(
                pulse_payload.get("big_visual_smoothing", 0.5)
            ),
            big_contraction_bias=float(
                pulse_payload.get("big_contraction_bias", 1.0)
            ),
            big_size_clamp=float(pulse_payload.get("big_size_clamp", 4.0)),
        )
        frozen_positions = tuple(float(value) for value in positions)
        frozen_extras = tuple(float(value) for value in extras)
        frozen_trails = tuple(float(value) for value in trails)
        bubble_count = int(getattr(simulation, "count", 0) or 0)
        authored_ts = float(authored_timestamp)
        source_ts = float(source_timestamp or 0.0)
        lane_diag = _read_float_diagnostics(
            simulation,
            "get_big_lane_diagnostics",
        )
        render_diag = _read_float_diagnostics(
            simulation,
            "get_big_render_diagnostics",
        )
        geometry_diag = {
            "active_big_count": lane_diag.get("active_big_count", 0.0),
            "final_big_avg_radius": render_diag.get(
                "avg_big_render_radius",
                0.0,
            ),
            "final_big_max_delta": render_diag.get(
                "max_big_render_delta",
                0.0,
            ),
            "final_big_max_radius": render_diag.get(
                "max_big_render_radius",
                0.0,
            ),
            "big_clamp_hits": render_diag.get("big_clamp_hits", 0.0),
            "big_render_count": render_diag.get("big_render_count", 0.0),
            "configured_big_bass_pulse": float(
                pulse_payload.get("big_bass_pulse", 0.5)
            ),
            "configured_big_size_clamp": float(
                pulse_payload.get("big_size_clamp", 4.0)
            ),
            "configured_big_size_max": float(
                settings_payload.get("bubble_big_size_max", 0.038)
            ),
            "configured_big_visual_smoothing": float(
                pulse_payload.get("big_visual_smoothing", 0.5)
            ),
            "domain_h": float(getattr(simulation, "_domain_h", 1.0) or 1.0),
            "domain_w": float(getattr(simulation, "_domain_w", 1.0) or 1.0),
            "max_big_gated_energy": lane_diag.get(
                "max_big_gated_energy",
                0.0,
            ),
            "max_big_pulse_after": lane_diag.get("max_big_pulse_after", 0.0),
            "max_big_raw_src": lane_diag.get("max_big_raw_src", 0.0),
            "frozen_big_max_radius": render_diag.get(
                "max_big_payload_radius",
                0.0,
            ),
            "frozen_max_alpha": max(frozen_positions[3::4], default=0.0),
            "frozen_any_max_radius": max(
                frozen_positions[2::4],
                default=0.0,
            ),
        }

        protected_edges: tuple[VisualizerProtectedEdge, ...] = ()
        consumed = tuple(event_recorder.consumed) if event_recorder else ()
        if consumed:
            protected_edges = (
                VisualizerProtectedEdge(
                    token=max(0, int(edge_token)),
                    kind="bubble_visible_result",
                    authored_timestamp=min(
                        (
                            event_timestamp
                            for _name, _strength, event_timestamp in consumed
                            if event_timestamp > 0.0
                        ),
                        default=authored_ts,
                    ),
                    result_timestamp=authored_ts,
                    # Protect only the consume-once authored event semantic.
                    # Bubble geometry is continuously forward-carried by the
                    # simulation and MUST remain latest-state authoritative at
                    # the Quick boundary; copying full arrays here let an older
                    # event result override a newer authored Bubble frame.
                    result=freeze_render_fields(
                        {
                            "source_timestamp": source_ts,
                            "simulation_timestamp": authored_ts,
                            "source_generation": int(source_generation),
                            "source_activation_id": int(source_activation_id),
                            "event_kinds": tuple(name for name, _s, _t in consumed),
                        }
                    ),
                ),
            )

        perf: dict[str, float] = {}
        diagnostics = getattr(simulation, "get_perf_diagnostics", None)
        if callable(diagnostics):
            try:
                perf = {
                    str(name): float(value)
                    for name, value in dict(diagnostics()).items()
                }
            except (TypeError, ValueError):
                perf = {}
        perf["integration_total_ms"] = (
            time.perf_counter() - integration_started
        ) * 1000.0
        perf["result_count"] = float(bubble_count)
        self._latest = BubbleResolvedFrame(
            positions=frozen_positions,
            extras=frozen_extras,
            trails=frozen_trails,
            bubble_count=bubble_count,
            source_timestamp=source_ts,
            simulation_timestamp=authored_ts,
            runtime_generation=int(runtime_generation),
            engine_generation=int(engine_generation),
            activation_id=int(activation_id),
            source_generation=int(source_generation),
            source_activation_id=int(source_activation_id),
            playing=bool(playing),
            protected_edges=protected_edges,
            perf_diagnostics=tuple(sorted(perf.items())),
            geometry_diagnostics=tuple(sorted(geometry_diag.items())),
        )
        return self._latest


__all__ = ["BubbleFrameRuntime", "BubbleResolvedFrame"]
