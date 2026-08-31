"""Authored DevCurve state advanced by the sole visualizer logical clock."""

from __future__ import annotations

from dataclasses import dataclass
import math
import threading
from collections.abc import Mapping, Sequence

from widgets.spotify_visualizer.devcurve_runtime import (
    DevCurveRuntimeState,
    solve_devcurve_frame,
)
from widgets.spotify_visualizer.render_state import (
    FrozenFields,
    VisualizerEnergyState,
    VisualizerTransientState,
    freeze_render_fields,
)


_LAYER_NAMES = ("bass", "vocals", "mids", "transients")
_DEFAULT_SHAPE = (
    (0.0, 0.58),
    (0.35, 0.64),
    (0.70, 0.52),
    (1.0, 0.60),
)


def _bounded(value: object, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return minimum
    if not math.isfinite(number):
        return minimum
    return max(minimum, min(maximum, number))


def _parameter(
    parameters: Mapping[str, object],
    name: str,
    default: object,
) -> object:
    try:
        return parameters[name]
    except KeyError:
        return default


def _idle_energy(now_ts: float) -> VisualizerEnergyState:
    return VisualizerEnergyState(
        bass=0.018 + 0.010 * (0.5 + 0.5 * math.sin(now_ts * 0.58)),
        mid=0.015 + 0.007 * (0.5 + 0.5 * math.sin(now_ts * 0.41 + 1.3)),
        high=0.012 + 0.005 * (0.5 + 0.5 * math.sin(now_ts * 0.71 + 2.1)),
        overall=0.018,
    )


def _curves(
    values: Mapping[str, Sequence[object]],
) -> tuple[tuple[str, tuple[float, ...]], ...]:
    return tuple(
        (
            name,
            tuple(float(value) for value in values.get(name, ())),
        )
        for name in _LAYER_NAMES
    )


@dataclass(frozen=True, slots=True)
class DevCurveResolvedFrame:
    curves: tuple[tuple[str, tuple[float, ...]], ...] = ()
    ghost_curves: tuple[tuple[str, tuple[float, ...]], ...] = ()
    draw_order: tuple[str, ...] = ()
    foreground_layer: str = ""
    foreground_layer_id: int = -1
    specular_slots: tuple[tuple[float, ...], ...] = ()
    parameters: FrozenFields = FrozenFields()
    diagnostics: FrozenFields = FrozenFields()
    energy: VisualizerEnergyState = VisualizerEnergyState()
    transient: VisualizerTransientState = VisualizerTransientState()
    runtime_generation: int = -1
    engine_generation: int = -1
    activation_id: int = -1
    source_generation: int = -1
    source_activation_id: int = -1
    source_timestamp: float = 0.0
    logical_timestamp: float = 0.0
    playing: bool = False
    reactive_source_ready: bool = False
    changed: bool = False


class DevCurveFrameRuntime:
    """Own one DevCurve solver and its latest immutable authored result."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._solver_state = DevCurveRuntimeState()
        self._activation_identity: tuple[int, int, int] | None = None
        self._last_timestamp = 0.0
        self._last_playing: bool | None = None
        self._specular_activity_alpha = 0.0
        self._latest = DevCurveResolvedFrame()
        self._retired = False

    @property
    def latest(self) -> DevCurveResolvedFrame:
        with self._lock:
            return self._latest

    @property
    def solver_state(self) -> DevCurveRuntimeState:
        """Read-only diagnostics seam for the deterministic replay harness."""

        with self._lock:
            return self._solver_state

    def reset(self) -> None:
        with self._lock:
            self._reset_locked()

    def retire(self) -> None:
        """Permanently quiesce this generation-scoped mode state."""

        with self._lock:
            self._reset_locked()
            self._retired = True

    def _reset_locked(self) -> None:
        self._solver_state = DevCurveRuntimeState()
        self._activation_identity = None
        self._last_timestamp = 0.0
        self._last_playing = None
        self._specular_activity_alpha = 0.0
        self._latest = DevCurveResolvedFrame()

    def advance(
        self,
        *,
        now_ts: float,
        runtime_generation: int,
        engine_generation: int,
        activation_id: int,
        source_generation: int,
        source_activation_id: int,
        source_timestamp: float,
        playing: bool,
        energy: VisualizerEnergyState,
        transient: VisualizerTransientState,
        layer_shape_nodes: Mapping[str, Sequence[Sequence[object]]],
        parameters: Mapping[str, object],
    ) -> DevCurveResolvedFrame | None:
        """Integrate one authored step and detach all renderer-visible state."""

        with self._lock:
            if self._retired:
                return None
            return self._advance_locked(
                now_ts=now_ts,
                runtime_generation=runtime_generation,
                engine_generation=engine_generation,
                activation_id=activation_id,
                source_generation=source_generation,
                source_activation_id=source_activation_id,
                source_timestamp=source_timestamp,
                playing=playing,
                energy=energy,
                transient=transient,
                layer_shape_nodes=layer_shape_nodes,
                parameters=parameters,
            )

    def _advance_locked(
        self,
        *,
        now_ts: float,
        runtime_generation: int,
        engine_generation: int,
        activation_id: int,
        source_generation: int,
        source_activation_id: int,
        source_timestamp: float,
        playing: bool,
        energy: VisualizerEnergyState,
        transient: VisualizerTransientState,
        layer_shape_nodes: Mapping[str, Sequence[Sequence[object]]],
        parameters: Mapping[str, object],
    ) -> DevCurveResolvedFrame:
        timestamp = float(now_ts)
        identity = (
            int(runtime_generation),
            int(engine_generation),
            int(activation_id),
        )
        if identity != self._activation_identity:
            self._reset_locked()
            self._activation_identity = identity

        dt = 0.016
        if self._last_timestamp > 0.0:
            dt = max(0.001, min(0.1, timestamp - self._last_timestamp))

        is_playing = bool(playing)
        source_ready = bool(
            is_playing
            and int(source_generation) >= 0
            and int(source_activation_id) >= 0
            and int(source_generation) == int(engine_generation)
            and int(source_activation_id) == int(activation_id)
        )
        if is_playing:
            resolved_energy = energy if source_ready else VisualizerEnergyState()
            resolved_transient = (
                transient if source_ready else VisualizerTransientState()
            )
            if not source_ready:
                source_generation = -1
                source_activation_id = -1
                source_timestamp = 0.0
        else:
            resolved_energy = _idle_energy(timestamp)
            resolved_transient = VisualizerTransientState()
            source_generation = -1
            source_activation_id = -1
            source_timestamp = 0.0

        parameter_values = {
            str(name): value
            for name, value in parameters.items()
            if str(name) != "devcurve_growth"
        }
        layer_settings: dict[str, dict[str, float | bool | int]] = {}
        resolved_nodes: dict[str, list[list[float]]] = {}
        for index, name in enumerate(_LAYER_NAMES):
            layer_settings[name] = {
                "enabled": bool(
                    _parameter(
                        parameter_values,
                        f"devcurve_layer_{name}_enabled",
                        True,
                    )
                ),
                "power": _bounded(
                    _parameter(
                        parameter_values,
                        f"devcurve_layer_{name}_power",
                        1.0,
                    ),
                    0.0,
                    3.0,
                ),
                "offset": _bounded(
                    _parameter(
                        parameter_values,
                        f"devcurve_layer_{name}_offset",
                        0.0,
                    ),
                    -0.45,
                    0.45,
                ),
                "order": max(
                    1,
                    min(
                        4,
                        int(
                            _parameter(
                                parameter_values,
                                f"devcurve_layer_{name}_order",
                                index + 1,
                            )
                        ),
                    ),
                ),
            }
            raw_nodes = layer_shape_nodes.get(name, _DEFAULT_SHAPE)
            nodes = [
                [float(node[0]), float(node[1])]
                for node in raw_nodes
                if len(node) >= 2
            ]
            if not nodes:
                nodes = [list(node) for node in _DEFAULT_SHAPE]
            resolved_nodes[name] = nodes
            parameter_values[f"devcurve_layer_{name}_shape_nodes"] = nodes

        frame = solve_devcurve_frame(
            self._solver_state,
            dt=dt,
            now_ts=timestamp,
            playing=is_playing,
            energy_bands=resolved_energy,
            transient_bus=resolved_transient,
            layer_shape_nodes=resolved_nodes,
            base_level=_bounded(
                _parameter(parameter_values, "devcurve_base_level", 0.58),
                0.10,
                0.90,
            ),
            motion_power=_bounded(
                _parameter(parameter_values, "devcurve_motion_power", 1.0),
                0.0,
                3.0,
            ),
            idle_motion=_bounded(
                _parameter(parameter_values, "devcurve_idle_motion", 0.20),
                0.0,
                1.5,
            ),
            idle_speed=_bounded(
                _parameter(parameter_values, "devcurve_idle_speed", 0.60),
                0.05,
                2.0,
            ),
            smoothness=_bounded(
                _parameter(parameter_values, "devcurve_smoothness", 0.55),
                0.0,
                1.0,
            ),
            layer_settings=layer_settings,
        )
        layer_map = frame.get("layers", {})
        if not isinstance(layer_map, Mapping):
            layer_map = {}
        current_curves = _curves(layer_map)

        # Historical DevCurve accepted ghost settings but never rendered a
        # ghost curve: the old fragment shader declared u_ghost_alpha without
        # consuming it and had no ghost-curve uniforms.  Quick briefly invented
        # delayed duplicate filled layers here, which changed outline quality
        # and could mask short transient motion.  Keep the persisted settings in
        # parameters, but author no additional visual layer for parity.
        ghost_curves: tuple[tuple[str, tuple[float, ...]], ...] = ()

        if self._last_playing is None:
            self._specular_activity_alpha = 1.0 if is_playing else 0.0
        else:
            target_activity = 1.0 if is_playing else 0.0
            blend = max(0.0, min(1.0, dt / 0.85))
            self._specular_activity_alpha += (
                target_activity - self._specular_activity_alpha
            ) * blend

        draw_order = tuple(
            str(name)
            for name in frame.get("draw_order", _LAYER_NAMES)
        )
        foreground_layer = str(frame.get("foreground_layer", "") or "")
        foreground_layer_id = int(frame.get("foreground_layer_id", -1))
        raw_slots = frame.get("specular_slots", ())
        specular_slots = tuple(
            tuple(float(value) for value in slot)
            for slot in raw_slots
        )
        parameter_values["devcurve_sample_count"] = int(
            frame.get("sample_count", 0)
        )
        parameter_values["devcurve_foreground_layer_id"] = (
            foreground_layer_id
        )
        parameter_values["devcurve_specular_activity_alpha"] = (
            self._specular_activity_alpha
        )
        parameter_values["devcurve_reactive_source_ready"] = source_ready
        frozen_parameters = freeze_render_fields(parameter_values)
        frozen_diagnostics = freeze_render_fields(
            {
                "smoothness_max_step": float(
                    frame.get("smoothness_max_step", 0.0)
                ),
                "active_amplitude": float(
                    frame.get("active_amplitude", 0.0)
                ),
                "idle_amplitude": float(frame.get("idle_amplitude", 0.0)),
                "foreground_travel_rate": float(
                    frame.get("foreground_travel_rate", 0.0)
                ),
                "foreground_travel_pos": float(
                    frame.get("foreground_travel_pos", 0.0)
                ),
                "specular_travel_rate": float(
                    frame.get("specular_travel_rate", 0.0)
                ),
                "energies": frame.get("energies", {}),
            }
        )

        previous = self._latest
        changed = bool(
            previous.curves != current_curves
            or previous.ghost_curves != ghost_curves
            or previous.draw_order != draw_order
            or previous.foreground_layer_id != foreground_layer_id
            or previous.specular_slots != specular_slots
            or previous.parameters != frozen_parameters
            or previous.diagnostics != frozen_diagnostics
            or previous.playing != is_playing
            or previous.source_generation != int(source_generation)
            or previous.source_activation_id != int(source_activation_id)
        )
        self._latest = DevCurveResolvedFrame(
            curves=current_curves,
            ghost_curves=ghost_curves,
            draw_order=draw_order,
            foreground_layer=foreground_layer,
            foreground_layer_id=foreground_layer_id,
            specular_slots=specular_slots,
            parameters=frozen_parameters,
            diagnostics=frozen_diagnostics,
            energy=resolved_energy,
            transient=resolved_transient,
            runtime_generation=int(runtime_generation),
            engine_generation=int(engine_generation),
            activation_id=int(activation_id),
            source_generation=int(source_generation),
            source_activation_id=int(source_activation_id),
            source_timestamp=float(source_timestamp or 0.0),
            logical_timestamp=timestamp,
            playing=is_playing,
            reactive_source_ready=source_ready,
            changed=changed,
        )
        self._last_timestamp = timestamp
        self._last_playing = is_playing
        return self._latest


__all__ = ["DevCurveFrameRuntime", "DevCurveResolvedFrame"]
