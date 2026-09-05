"""Activation-fenced authored state for the experimental Sphere mode."""
from __future__ import annotations

from dataclasses import dataclass

from widgets.spotify_visualizer.frame_runtime_lifecycle import RetirableFrameRuntime, retirement_fenced
from widgets.spotify_visualizer.render_state import (
    FrozenFields,
    VisualizerEnergyState,
    VisualizerTransientState,
)


# Whole-body size is authored state, not render cadence. A near-critical spring
# turns the shared transient bus into one smooth breathing/elastic response while
# still allowing intentionally large expansion at the top of the Settings range.
_SPHERE_SIZE_SPRING_STIFFNESS = 26.0
_SPHERE_SIZE_SPRING_DAMPING = 8.5
_SPHERE_SIZE_PULSE_GAIN = 0.30
_SPHERE_SIZE_PULSE_LIMIT = 0.72
_SPHERE_SIZE_MAX_STEP_S = 0.05


@dataclass(frozen=True, slots=True)
class SphereResolvedFrame:
    authored_time: float
    size_pulse: float
    parameters: FrozenFields
    energy: VisualizerEnergyState
    changed: bool


def sphere_size_pulse_target(
    energy: VisualizerEnergyState,
    transient: VisualizerTransientState,
    parameters: FrozenFields,
) -> float:
    """Resolve the configure-owned whole-body growth target for one logical step."""

    response = max(0.0, min(2.0, float(parameters.get("sphere_size_response", 1.5))))
    if response <= 0.0:
        return 0.0
    curve = max(0.2, min(2.0, float(parameters.get("sphere_energy_curve", 0.60))))
    drive = max(
        float(energy.overall) * 0.25,
        float(energy.bass) * 0.35,
        float(transient.bass),
        float(transient.mid),
        float(transient.high),
        float(transient.onset_strength),
    )
    drive = max(0.0, min(1.0, drive))
    return min(
        _SPHERE_SIZE_PULSE_LIMIT,
        _SPHERE_SIZE_PULSE_GAIN * response * (drive ** curve),
    )


class SphereFrameRuntime(RetirableFrameRuntime):
    """Own activation-relative time and the sole authored size-response envelope."""

    def __init__(self) -> None:
        super().__init__()
        self._activation_identity: tuple[int, int, int] | None = None
        self._started_at = 0.0
        self._last_ts = 0.0
        self._size_pulse = 0.0
        self._size_pulse_velocity = 0.0
        self._latest = SphereResolvedFrame(
            0.0, 0.0, FrozenFields(), VisualizerEnergyState(), False
        )

    def reset(self) -> None:
        self._activation_identity = None
        self._started_at = 0.0
        self._last_ts = 0.0
        self._size_pulse = 0.0
        self._size_pulse_velocity = 0.0
        self._latest = SphereResolvedFrame(
            0.0, 0.0, FrozenFields(), VisualizerEnergyState(), False
        )

    @retirement_fenced
    def resolve(
        self,
        *,
        now_ts: float,
        runtime_generation: int,
        engine_generation: int,
        activation_id: int,
        energy: VisualizerEnergyState,
        parameters: FrozenFields,
        transient: VisualizerTransientState = VisualizerTransientState(),
    ) -> SphereResolvedFrame | None:
        if not isinstance(parameters, FrozenFields):
            raise TypeError("Sphere runtime requires configure-owned FrozenFields")
        if not isinstance(energy, VisualizerEnergyState):
            raise TypeError("Sphere runtime requires VisualizerEnergyState")
        if not isinstance(transient, VisualizerTransientState):
            raise TypeError("Sphere runtime requires VisualizerTransientState")

        now = float(now_ts)
        identity = (int(runtime_generation), int(engine_generation), int(activation_id))
        if identity != self._activation_identity:
            self._activation_identity = identity
            self._started_at = now
            self._last_ts = now
            self._size_pulse = 0.0
            self._size_pulse_velocity = 0.0
        else:
            dt = max(0.0, min(_SPHERE_SIZE_MAX_STEP_S, now - self._last_ts))
            self._last_ts = now
            if dt > 0.0:
                target = sphere_size_pulse_target(energy, transient, parameters)
                acceleration = (
                    _SPHERE_SIZE_SPRING_STIFFNESS * (target - self._size_pulse)
                    - _SPHERE_SIZE_SPRING_DAMPING * self._size_pulse_velocity
                )
                self._size_pulse_velocity += acceleration * dt
                self._size_pulse += self._size_pulse_velocity * dt
                if self._size_pulse <= 0.0:
                    self._size_pulse = 0.0
                    if self._size_pulse_velocity < 0.0:
                        self._size_pulse_velocity = 0.0
                elif self._size_pulse >= _SPHERE_SIZE_PULSE_LIMIT:
                    self._size_pulse = _SPHERE_SIZE_PULSE_LIMIT
                    if self._size_pulse_velocity > 0.0:
                        self._size_pulse_velocity = 0.0

        authored_time = max(0.0, now - self._started_at)
        resolved = SphereResolvedFrame(
            authored_time,
            self._size_pulse,
            parameters,
            energy,
            resolved_differs(
                self._latest,
                authored_time,
                self._size_pulse,
                parameters,
                energy,
            ),
        )
        self._latest = resolved
        return resolved


def resolved_differs(
    previous: SphereResolvedFrame,
    time_value: float,
    size_pulse: float,
    parameters: FrozenFields,
    energy: VisualizerEnergyState,
) -> bool:
    return (
        previous.authored_time != time_value
        or previous.size_pulse != size_pulse
        or previous.parameters != parameters
        or previous.energy != energy
    )


__all__ = [
    "SphereFrameRuntime",
    "SphereResolvedFrame",
    "sphere_size_pulse_target",
]
