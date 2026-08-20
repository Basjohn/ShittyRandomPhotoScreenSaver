"""Immutable transition requests and render-thread sampling state."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
import math
from typing import TypeAlias

from core.animation.easing import ease
from core.animation.types import EasingCurve
from rendering.transition_registry import (
    get_transition_descriptor_for_runtime_identity,
)
from ..image_state import PresentationImage


TransitionValue: TypeAlias = (
    None | bool | int | float | str | tuple["TransitionValue", ...]
)
TransitionParameters: TypeAlias = tuple[tuple[str, TransitionValue], ...]


def _freeze_value(value: object) -> TransitionValue:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("transition parameter floats must be finite")
        return value
    if isinstance(value, Enum):
        return _freeze_value(value.value)
    if isinstance(value, Mapping):
        return tuple(
            (str(key), _freeze_value(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_value(item) for item in value)
    raise TypeError(
        f"unsupported transition parameter value: {type(value).__name__}"
    )


def freeze_transition_parameters(
    parameters: Mapping[str, object] | Iterable[tuple[str, object]] | None,
) -> TransitionParameters:
    """Deep-freeze authored renderer parameters into deterministic key order."""

    if parameters is None:
        return ()
    items = parameters.items() if isinstance(parameters, Mapping) else parameters
    frozen: dict[str, TransitionValue] = {}
    for raw_name, value in items:
        name = str(raw_name).strip()
        if not name:
            raise ValueError("transition parameter names must not be empty")
        if name in frozen:
            raise ValueError(f"duplicate transition parameter: {name}")
        frozen[name] = _freeze_value(value)
    return tuple(sorted(frozen.items()))


@dataclass(frozen=True, slots=True)
class TransitionRequest:
    """Fully resolved transition intent with no presentation-object references."""

    runtime_generation: int
    transition_id: str
    requested_name: str
    selected_from_random: bool
    duration_ms: int
    easing_name: str
    easing_curve: EasingCurve
    direction: TransitionValue
    parameters: TransitionParameters
    source_image: PresentationImage
    destination_image: PresentationImage

    def __post_init__(self) -> None:
        generation = int(self.runtime_generation)
        if generation < 0:
            raise ValueError("runtime generation must be non-negative")
        descriptor = get_transition_descriptor_for_runtime_identity(
            self.transition_id
        )
        if descriptor is None:
            raise ValueError(f"unknown canonical transition: {self.transition_id!r}")
        duration_ms = int(self.duration_ms)
        if duration_ms <= 0:
            raise ValueError("transition duration must be positive")
        if not isinstance(self.easing_curve, EasingCurve):
            raise TypeError("transition easing_curve must be an EasingCurve")
        if not isinstance(self.source_image, PresentationImage) or not isinstance(
            self.destination_image,
            PresentationImage,
        ):
            raise TypeError("transition images must be immutable PresentationImage values")

        object.__setattr__(self, "runtime_generation", generation)
        object.__setattr__(self, "transition_id", descriptor.stable_id)
        object.__setattr__(
            self,
            "requested_name",
            str(self.requested_name or descriptor.setting_name),
        )
        object.__setattr__(self, "duration_ms", duration_ms)
        object.__setattr__(
            self,
            "selected_from_random",
            bool(self.selected_from_random),
        )
        object.__setattr__(self, "easing_name", str(self.easing_name or "Auto"))
        object.__setattr__(self, "direction", _freeze_value(self.direction))
        object.__setattr__(
            self,
            "parameters",
            freeze_transition_parameters(self.parameters),
        )

    @property
    def source_image_identity(self) -> str:
        return self.source_image.identity

    @property
    def destination_image_identity(self) -> str:
        return self.destination_image.identity

    @property
    def setting_name(self) -> str:
        descriptor = get_transition_descriptor_for_runtime_identity(
            self.transition_id
        )
        if descriptor is None:  # pragma: no cover - fenced during construction
            raise RuntimeError(f"transition registry lost {self.transition_id!r}")
        return descriptor.setting_name

    @property
    def include_in_cycle(self) -> bool:
        descriptor = get_transition_descriptor_for_runtime_identity(
            self.transition_id
        )
        if descriptor is None:  # pragma: no cover - fenced during construction
            raise RuntimeError(f"transition registry lost {self.transition_id!r}")
        return bool(descriptor.include_in_cycle)

    def parameter_dict(self) -> dict[str, TransitionValue]:
        return dict(self.parameters)


@dataclass(frozen=True, slots=True)
class TransitionSample:
    run_id: int
    runtime_generation: int
    linear_progress: float
    eased_progress: float
    complete: bool


@dataclass(frozen=True, slots=True)
class TransitionRun:
    """One immutable, generation-fenced monotonic transition timeline."""

    run_id: int
    request: TransitionRequest
    start_ns: int
    end_ns: int

    def __post_init__(self) -> None:
        run_id = int(self.run_id)
        start_ns = int(self.start_ns)
        end_ns = int(self.end_ns)
        if run_id <= 0:
            raise ValueError("transition run id must be positive")
        if start_ns < 0 or end_ns <= start_ns:
            raise ValueError("transition run deadline must follow its start")
        expected_end = start_ns + (self.request.duration_ms * 1_000_000)
        if end_ns != expected_end:
            raise ValueError(
                f"transition run deadline mismatch: {end_ns} != {expected_end}"
            )
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "start_ns", start_ns)
        object.__setattr__(self, "end_ns", end_ns)

    @classmethod
    def start(
        cls,
        *,
        run_id: int,
        request: TransitionRequest,
        start_ns: int,
    ) -> "TransitionRun":
        start = int(start_ns)
        return cls(
            run_id=run_id,
            request=request,
            start_ns=start,
            end_ns=start + (request.duration_ms * 1_000_000),
        )

    def sample(self, now_ns: int) -> TransitionSample:
        now = int(now_ns)
        duration_ns = self.end_ns - self.start_ns
        linear = max(0.0, min(1.0, (now - self.start_ns) / duration_ns))
        return TransitionSample(
            run_id=self.run_id,
            runtime_generation=self.request.runtime_generation,
            linear_progress=linear,
            eased_progress=float(ease(linear, self.request.easing_curve)),
            complete=now >= self.end_ns,
        )


class TransitionOutcome(str, Enum):
    COMPLETED = "completed"
    CANCELLED_TO_DESTINATION = "cancelled-to-destination"


@dataclass(frozen=True, slots=True)
class TransitionCompletion:
    """Exactly-once destination-finalization record for one run."""

    run_id: int
    runtime_generation: int
    outcome: TransitionOutcome
    destination_image_identity: str
    finalized_at_ns: int
    reason: str
