"""Activation-fenced authored state for the experimental Sphere mode."""
from __future__ import annotations

from dataclasses import dataclass

from widgets.spotify_visualizer.frame_runtime_lifecycle import RetirableFrameRuntime, retirement_fenced
from widgets.spotify_visualizer.render_state import FrozenFields, VisualizerEnergyState


@dataclass(frozen=True, slots=True)
class SphereResolvedFrame:
    authored_time: float
    parameters: FrozenFields
    energy: VisualizerEnergyState
    changed: bool


class SphereFrameRuntime(RetirableFrameRuntime):
    """Owns only activation-relative time; capture is its sole advance seam."""

    def __init__(self) -> None:
        super().__init__()
        self._activation_identity: tuple[int, int, int] | None = None
        self._started_at = 0.0
        self._latest = SphereResolvedFrame(0.0, FrozenFields(), VisualizerEnergyState(), False)

    def reset(self) -> None:
        self._activation_identity = None
        self._started_at = 0.0
        self._latest = SphereResolvedFrame(0.0, FrozenFields(), VisualizerEnergyState(), False)

    @retirement_fenced
    def resolve(self, *, now_ts: float, runtime_generation: int, engine_generation: int,
                activation_id: int, energy: VisualizerEnergyState, parameters: FrozenFields) -> SphereResolvedFrame | None:
        if not isinstance(parameters, FrozenFields):
            raise TypeError("Sphere runtime requires configure-owned FrozenFields")
        identity = (int(runtime_generation), int(engine_generation), int(activation_id))
        if identity != self._activation_identity:
            self._activation_identity = identity
            self._started_at = float(now_ts)
        authored_time = max(0.0, float(now_ts) - self._started_at)
        resolved = SphereResolvedFrame(authored_time, parameters, energy, resolved_differs(self._latest, authored_time, parameters, energy))
        self._latest = resolved
        return resolved


def resolved_differs(previous: SphereResolvedFrame, time_value: float, parameters: FrozenFields,
                     energy: VisualizerEnergyState) -> bool:
    return previous.authored_time != time_value or previous.parameters != parameters or previous.energy != energy


__all__ = ["SphereFrameRuntime", "SphereResolvedFrame"]
