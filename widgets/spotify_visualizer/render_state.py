"""Immutable visualizer state crossing the future Qt Quick render boundary.

Logical mode implementations produce :class:`VisualizerLogicalFrame` values on
the sole authored clock.  The GUI/Quick synchronization owner combines the
latest frame with already-resolved presentation geometry and policy, producing
one :class:`VisualizerRenderSnapshot`.  Render code receives only that complete
value; it never reads a live widget, QObject, provider, settings object, or mode
registry.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Protocol, TypeAlias

from core.settings.visualizer_mode_registry import (
    VisualizerClipPolicy,
    VisualizerShellPolicy,
)


RectTuple: TypeAlias = tuple[float, float, float, float]
SizeTuple: TypeAlias = tuple[float, float]


# Visualizer baseline geometry authority. Distinguish three concepts:
#   1. default/baseline ASPECT (1.5) - the sensible default shape for ordinary
#      non-CUSTOM visualizer layout, shared by all five current modes;
#   2. resolved runtime SIZE - outer_rect = viewport_extent * uniform scale,
#      resolved per display (the layout owner picks width from media/free-space
#      rules; height derives from the baseline aspect) with uniform screen-fit;
#   3. explicit viewport EXTENT - the logical/render world, defaulting to the
#      reference below but allowed to depart from 1.5 via the Phase-G edge-resize
#      operation (modes reflow rather than stretching finished pixels).
#
# CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE is an INTERNAL REFERENCE coordinate
# extent corresponding to the 1.5 baseline aspect. The literal 420x280 arose from
# layout history and is NOT a required/sacred visible or runtime output size; it
# is retained only as a stable reference for normalization and authored
# stroke/radius scaling (e.g. DevCurve's baseline_content_extent). Do not freeze
# runtime visualizers to 420x280, and do not delete the 1.5 default aspect in
# favour of arbitrary mode-specific card shapes. The retired per-mode *_growth
# controls are not an alternate aspect/height authority.
CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE: SizeTuple = (420.0, 280.0)
CANONICAL_VISUALIZER_BASELINE_ASPECT_RATIO = 1.5


def _finite(value: object, *, name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _thaw(value: object) -> object:
    if isinstance(value, FrozenFields):
        return value.as_dict()
    if isinstance(value, tuple):
        return tuple(_thaw(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class FrozenFields(Mapping[str, object]):
    """Small deterministic immutable mapping used for authored mode fields."""

    entries: tuple[tuple[str, object], ...] = ()

    def __post_init__(self) -> None:
        names = tuple(name for name, _value in self.entries)
        if not all(isinstance(name, str) and name for name in names):
            raise ValueError("frozen field names must be non-empty strings")
        if names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValueError("frozen field names must be unique and sorted")
        object.__setattr__(
            self,
            "entries",
            tuple(
                (name, freeze_render_value(value))
                for name, value in self.entries
            ),
        )

    def __getitem__(self, key: str) -> object:
        for name, value in self.entries:
            if name == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (name for name, _value in self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def as_dict(self) -> dict[str, object]:
        return {name: _thaw(value) for name, value in self.entries}


def freeze_render_value(value: object) -> object:
    """Deep-freeze a render value without retaining its mutable source.

    NumPy arrays and Qt colors are detected without importing either runtime,
    keeping this contract usable by presentation-neutral tests and owners.
    """

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return _finite(value, name="render value")
    if isinstance(value, Enum):
        return freeze_render_value(value.value)
    if isinstance(value, Mapping):
        return freeze_render_fields(value)
    if isinstance(value, (tuple, list)):
        return tuple(freeze_render_value(item) for item in value)

    value_type = type(value)
    module_name = str(getattr(value_type, "__module__", ""))
    if module_name.startswith("numpy"):
        to_list = getattr(value, "tolist", None)
        if callable(to_list):
            return freeze_render_value(to_list())

    get_rgba = getattr(value, "getRgb", None)
    if module_name.startswith("PySide6") and callable(get_rgba):
        rgba = get_rgba()
        return tuple(int(channel) for channel in rgba[:4])

    if is_dataclass(value) and not isinstance(value, type):
        return freeze_render_fields(
            {field.name: getattr(value, field.name) for field in fields(value)}
        )

    raise TypeError(f"unsupported visualizer render value: {value_type.__name__}")


def freeze_render_fields(
    values: Mapping[str, object] | None = None,
) -> FrozenFields:
    if values is None:
        return FrozenFields()
    frozen: dict[str, object] = {}
    for raw_name, value in values.items():
        name = str(raw_name).strip()
        if not name:
            raise ValueError("render field names must not be empty")
        if name in frozen:
            raise ValueError(f"duplicate render field: {name}")
        frozen[name] = freeze_render_value(value)
    return FrozenFields(tuple(sorted(frozen.items())))


def _float_tuple(values: Sequence[object], *, name: str) -> tuple[float, ...]:
    return tuple(_finite(value, name=name) for value in values)


def _float_tuple_rows(
    values: Sequence[Sequence[object]],
    *,
    name: str,
) -> tuple[tuple[float, ...], ...]:
    return tuple(_float_tuple(row, name=name) for row in values)


def _coerce_frozen_fields(value: object, *, name: str) -> FrozenFields:
    if isinstance(value, FrozenFields):
        return value
    if isinstance(value, Mapping):
        return freeze_render_fields(value)
    raise TypeError(f"{name} must be immutable render fields")


@dataclass(frozen=True, slots=True)
class VisualizerEnergyState:
    bass: float = 0.0
    mid: float = 0.0
    high: float = 0.0
    overall: float = 0.0

    def __post_init__(self) -> None:
        for name in ("bass", "mid", "high", "overall"):
            object.__setattr__(self, name, _finite(getattr(self, name), name=name))


@dataclass(frozen=True, slots=True)
class VisualizerTransientState:
    bass: float = 0.0
    mid: float = 0.0
    high: float = 0.0
    onset_detected: bool = False
    onset_type: str = ""
    onset_strength: float = 0.0

    def __post_init__(self) -> None:
        for name in ("bass", "mid", "high", "onset_strength"):
            object.__setattr__(self, name, _finite(getattr(self, name), name=name))
        object.__setattr__(self, "onset_detected", bool(self.onset_detected))
        object.__setattr__(self, "onset_type", str(self.onset_type or ""))


@dataclass(frozen=True, slots=True)
class VisualizerCommonState:
    bars: tuple[float, ...]
    bar_count: int
    waveform: tuple[float, ...] = ()
    waveform_count: int = 0
    energy: VisualizerEnergyState = VisualizerEnergyState()
    transient: VisualizerTransientState = VisualizerTransientState()
    style: FrozenFields = FrozenFields()

    def __post_init__(self) -> None:
        count = int(self.bar_count)
        waveform_count = int(self.waveform_count)
        if count < 0 or waveform_count < 0:
            raise ValueError("visualizer sample counts must be non-negative")
        object.__setattr__(self, "bar_count", count)
        object.__setattr__(self, "waveform_count", waveform_count)
        object.__setattr__(self, "bars", _float_tuple(self.bars, name="bar"))
        object.__setattr__(
            self,
            "waveform",
            _float_tuple(self.waveform, name="waveform sample"),
        )
        if not isinstance(self.energy, VisualizerEnergyState):
            raise TypeError("energy must be VisualizerEnergyState")
        if not isinstance(self.transient, VisualizerTransientState):
            raise TypeError("transient must be VisualizerTransientState")
        object.__setattr__(
            self,
            "style",
            _coerce_frozen_fields(self.style, name="common style"),
        )


class VisualizerModeState(Protocol):
    @property
    def mode_id(self) -> str: ...


@dataclass(frozen=True, slots=True)
class SpectrumFrame:
    peaks: tuple[float, ...] = ()
    ghost_bars: tuple[float, ...] = ()
    animation_time: float = 0.0
    parameters: FrozenFields = FrozenFields()

    def __post_init__(self) -> None:
        object.__setattr__(self, "peaks", _float_tuple(self.peaks, name="spectrum peak"))
        object.__setattr__(
            self,
            "ghost_bars",
            _float_tuple(self.ghost_bars, name="spectrum ghost bar"),
        )
        object.__setattr__(
            self,
            "animation_time",
            _finite(self.animation_time, name="spectrum animation time"),
        )
        if self.animation_time < 0.0:
            raise ValueError("spectrum animation time must be non-negative")
        object.__setattr__(
            self,
            "parameters",
            _coerce_frozen_fields(self.parameters, name="spectrum parameters"),
        )

    @property
    def mode_id(self) -> str:
        return "spectrum"


@dataclass(frozen=True, slots=True)
class SphereFrame:
    """Small immutable Sphere payload; reactive energy stays in ``common``."""

    authored_time: float = 0.0
    size_pulse: float = 0.0
    parameters: FrozenFields = FrozenFields()

    def __post_init__(self) -> None:
        authored_time = _finite(self.authored_time, name="sphere authored time")
        if authored_time < 0.0:
            raise ValueError("sphere authored time must be non-negative")
        object.__setattr__(self, "authored_time", authored_time)
        size_pulse = _finite(self.size_pulse, name="sphere size pulse")
        if size_pulse < 0.0:
            raise ValueError("sphere size pulse must be non-negative")
        object.__setattr__(self, "size_pulse", size_pulse)
        object.__setattr__(
            self, "parameters", _coerce_frozen_fields(self.parameters, name="sphere parameters")
        )

    @property
    def mode_id(self) -> str:
        return "sphere"


@dataclass(frozen=True, slots=True)
class OscilloscopeFrame:
    previous_waveform: tuple[float, ...] = ()
    ghost_waveforms: tuple[tuple[float, ...], ...] = ()
    animation_time: float = 0.0
    parameters: FrozenFields = FrozenFields()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "previous_waveform",
            _float_tuple(self.previous_waveform, name="previous waveform sample"),
        )
        object.__setattr__(
            self,
            "ghost_waveforms",
            _float_tuple_rows(self.ghost_waveforms, name="ghost waveform sample"),
        )
        object.__setattr__(
            self,
            "animation_time",
            _finite(self.animation_time, name="oscilloscope animation time"),
        )
        if self.animation_time < 0.0:
            raise ValueError("oscilloscope animation time must be non-negative")
        object.__setattr__(
            self,
            "parameters",
            _coerce_frozen_fields(self.parameters, name="oscilloscope parameters"),
        )

    @property
    def mode_id(self) -> str:
        return "oscilloscope"


@dataclass(frozen=True, slots=True)
class SineFrame:
    heartbeat_intensity: float = 0.0
    ghost_energy: VisualizerEnergyState = VisualizerEnergyState()
    ghost_waveforms: tuple[tuple[float, ...], ...] = ()
    animation_time: float = 0.0
    parameters: FrozenFields = FrozenFields()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "heartbeat_intensity",
            _finite(self.heartbeat_intensity, name="heartbeat intensity"),
        )
        if not isinstance(self.ghost_energy, VisualizerEnergyState):
            raise TypeError("sine ghost energy must be immutable energy state")
        object.__setattr__(
            self,
            "ghost_waveforms",
            _float_tuple_rows(self.ghost_waveforms, name="sine ghost waveform sample"),
        )
        object.__setattr__(
            self,
            "animation_time",
            _finite(self.animation_time, name="sine animation time"),
        )
        if self.animation_time < 0.0:
            raise ValueError("sine animation time must be non-negative")
        object.__setattr__(
            self,
            "parameters",
            _coerce_frozen_fields(self.parameters, name="sine parameters"),
        )

    @property
    def mode_id(self) -> str:
        return "sine_wave"


@dataclass(frozen=True, slots=True)
class BubbleFrame:
    positions: tuple[float, ...] = ()
    extras: tuple[float, ...] = ()
    trails: tuple[float, ...] = ()
    bubble_count: int = 0
    source_timestamp: float = 0.0
    simulation_timestamp: float = 0.0
    parameters: FrozenFields = FrozenFields()
    geometry_diagnostics: FrozenFields = FrozenFields()

    def __post_init__(self) -> None:
        count = int(self.bubble_count)
        if count < 0:
            raise ValueError("bubble count must be non-negative")
        object.__setattr__(self, "bubble_count", count)
        object.__setattr__(self, "positions", _float_tuple(self.positions, name="bubble position"))
        object.__setattr__(self, "extras", _float_tuple(self.extras, name="bubble extra"))
        object.__setattr__(self, "trails", _float_tuple(self.trails, name="bubble trail"))
        object.__setattr__(
            self,
            "parameters",
            _coerce_frozen_fields(self.parameters, name="bubble parameters"),
        )
        object.__setattr__(
            self,
            "geometry_diagnostics",
            _coerce_frozen_fields(
                self.geometry_diagnostics,
                name="bubble geometry diagnostics",
            ),
        )
        object.__setattr__(
            self,
            "source_timestamp",
            _finite(self.source_timestamp, name="bubble source timestamp"),
        )
        object.__setattr__(
            self,
            "simulation_timestamp",
            _finite(self.simulation_timestamp, name="bubble simulation timestamp"),
        )

    @property
    def mode_id(self) -> str:
        return "bubble"


@dataclass(frozen=True, slots=True)
class DevCurveFrame:
    curves: tuple[tuple[str, tuple[float, ...]], ...] = ()
    ghost_curves: tuple[tuple[str, tuple[float, ...]], ...] = ()
    draw_order: tuple[str, ...] = ()
    foreground_layer_id: int = -1
    specular_slots: tuple[tuple[float, ...], ...] = ()
    parameters: FrozenFields = FrozenFields()

    def __post_init__(self) -> None:
        curves: list[tuple[str, tuple[float, ...]]] = []
        for raw_name, values in self.curves:
            name = str(raw_name or "").strip()
            if not name:
                raise ValueError("DevCurve curve name must not be empty")
            curves.append((name, _float_tuple(values, name=f"{name} curve sample")))
        object.__setattr__(self, "curves", tuple(curves))
        ghost_curves: list[tuple[str, tuple[float, ...]]] = []
        for raw_name, values in self.ghost_curves:
            name = str(raw_name or "").strip()
            if not name:
                raise ValueError("DevCurve ghost curve name must not be empty")
            ghost_curves.append(
                (name, _float_tuple(values, name=f"{name} ghost curve sample"))
            )
        object.__setattr__(self, "ghost_curves", tuple(ghost_curves))
        object.__setattr__(
            self,
            "draw_order",
            tuple(str(name or "").strip() for name in self.draw_order),
        )
        object.__setattr__(
            self,
            "foreground_layer_id",
            int(self.foreground_layer_id),
        )
        object.__setattr__(
            self,
            "specular_slots",
            _float_tuple_rows(self.specular_slots, name="DevCurve specular slot"),
        )
        object.__setattr__(
            self,
            "parameters",
            _coerce_frozen_fields(self.parameters, name="DevCurve parameters"),
        )

    @property
    def mode_id(self) -> str:
        return "devcurve"


ModeFrame: TypeAlias = (
    SpectrumFrame | SphereFrame | OscilloscopeFrame | SineFrame | BubbleFrame | DevCurveFrame
)


@dataclass(frozen=True, slots=True)
class VisualizerProtectedEdge:
    """One consume-once visible result that must survive slot coalescing."""

    token: int
    kind: str
    authored_timestamp: float
    result_timestamp: float
    result: FrozenFields

    def __post_init__(self) -> None:
        token = int(self.token)
        if token < 0:
            raise ValueError("protected edge token must be non-negative")
        kind = str(self.kind or "").strip()
        if not kind:
            raise ValueError("protected edge kind must not be empty")
        object.__setattr__(self, "token", token)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self,
            "authored_timestamp",
            _finite(self.authored_timestamp, name="edge authored timestamp"),
        )
        object.__setattr__(
            self,
            "result_timestamp",
            _finite(self.result_timestamp, name="edge result timestamp"),
        )
        object.__setattr__(
            self,
            "result",
            _coerce_frozen_fields(self.result, name="protected-edge result"),
        )


@dataclass(frozen=True, slots=True)
class VisualizerLogicalFrame:
    runtime_generation: int
    engine_generation: int
    activation_id: int
    source_generation: int
    source_activation_id: int
    mode_id: str
    playing: bool
    logical_timestamp: float
    source_timestamp: float | None
    changed: bool
    present_frame: bool
    mode_reveal_ready: bool
    common: VisualizerCommonState
    mode_state: ModeFrame
    protected_edges: tuple[VisualizerProtectedEdge, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "runtime_generation",
            "engine_generation",
            "activation_id",
            "source_generation",
            "source_activation_id",
        ):
            identity = int(getattr(self, name))
            if identity < -1:
                raise ValueError(f"{name} must be -1 or non-negative")
            object.__setattr__(self, name, identity)
        mode_id = str(self.mode_id or "").strip().lower()
        if not mode_id or mode_id != self.mode_state.mode_id:
            raise ValueError("logical mode identity must match its mode state")
        if not isinstance(self.common, VisualizerCommonState):
            raise TypeError("common state must be VisualizerCommonState")
        if not isinstance(
            self.mode_state,
            (SpectrumFrame, SphereFrame, OscilloscopeFrame, SineFrame, BubbleFrame, DevCurveFrame),
        ):
            raise TypeError("mode state must be one of the canonical immutable frames")
        edges = tuple(self.protected_edges)
        if not all(isinstance(edge, VisualizerProtectedEdge) for edge in edges):
            raise TypeError("protected edges must be VisualizerProtectedEdge values")
        object.__setattr__(self, "protected_edges", edges)
        object.__setattr__(self, "mode_id", mode_id)
        object.__setattr__(self, "playing", bool(self.playing))
        object.__setattr__(self, "changed", bool(self.changed))
        object.__setattr__(self, "present_frame", bool(self.present_frame))
        object.__setattr__(self, "mode_reveal_ready", bool(self.mode_reveal_ready))
        object.__setattr__(
            self,
            "logical_timestamp",
            _finite(self.logical_timestamp, name="logical timestamp"),
        )
        if self.source_timestamp is not None:
            object.__setattr__(
                self,
                "source_timestamp",
                _finite(self.source_timestamp, name="source timestamp"),
            )


def _rect_tuple(value: Sequence[object], *, name: str) -> RectTuple:
    if len(value) != 4:
        raise ValueError(f"{name} must contain x, y, width, height")
    rect = tuple(_finite(part, name=name) for part in value)
    if rect[2] < 0.0 or rect[3] < 0.0:
        raise ValueError(f"{name} size must be non-negative")
    return rect  # type: ignore[return-value]


def _size_tuple(value: Sequence[object], *, name: str) -> SizeTuple:
    if len(value) != 2:
        raise ValueError(f"{name} must contain width and height")
    size = tuple(_finite(part, name=name) for part in value)
    if size[0] <= 0.0 or size[1] <= 0.0:
        raise ValueError(f"{name} must be positive")
    return size  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class ResolvedVisualizerPresentation:
    """GUI-resolved presentation facts; no live registry or geometry reads."""

    shell_policy: VisualizerShellPolicy
    clip_policy: VisualizerClipPolicy
    viewport_resize_capable: bool
    outer_rect: RectTuple
    content_rect: RectTuple
    dpr: float
    baseline_viewport_size: SizeTuple
    baseline_aspect_ratio: float
    uniform_visual_scale: float
    viewport_extent: SizeTuple
    # Quick fade layers. ``scene_fade`` is the owner-authored visualizer scene
    # reveal resolved by ``QuickDisplayVisualizerOwner``. ``content_fade`` is
    # the renderer-side layer used for mode-transition/content attenuation and
    # is multiplied at the retained render seam by inherited Quick opacity
    # (including scene/startup reveal). Neither field owns a timer or cadence;
    # no QWidget/presentation-fade side channel exists.
    current_aspect_ratio: float
    scene_fade: float
    content_fade: float
    border_width: float
    shell_style: FrozenFields = FrozenFields()

    def __post_init__(self) -> None:
        if not isinstance(self.shell_policy, VisualizerShellPolicy):
            raise TypeError("shell policy must already be resolved")
        if not isinstance(self.clip_policy, VisualizerClipPolicy):
            raise TypeError("clip policy must already be resolved")
        object.__setattr__(self, "viewport_resize_capable", bool(self.viewport_resize_capable))
        object.__setattr__(self, "outer_rect", _rect_tuple(self.outer_rect, name="outer rect"))
        object.__setattr__(self, "content_rect", _rect_tuple(self.content_rect, name="content rect"))
        object.__setattr__(self, "dpr", _finite(self.dpr, name="DPR"))
        if self.dpr <= 0.0:
            raise ValueError("DPR must be positive")
        object.__setattr__(
            self,
            "baseline_viewport_size",
            _size_tuple(self.baseline_viewport_size, name="baseline viewport size"),
        )
        if self.baseline_viewport_size != CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE:
            raise ValueError("visualizer baseline viewport size is not canonical")
        object.__setattr__(
            self,
            "viewport_extent",
            _size_tuple(self.viewport_extent, name="viewport extent"),
        )
        for name in (
            "baseline_aspect_ratio",
            "uniform_visual_scale",
            "current_aspect_ratio",
        ):
            value = _finite(getattr(self, name), name=name)
            if value <= 0.0:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, value)
        if not math.isclose(
            self.baseline_aspect_ratio,
            CANONICAL_VISUALIZER_BASELINE_ASPECT_RATIO,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("visualizer baseline aspect ratio is not canonical")
        expected_aspect = self.viewport_extent[0] / self.viewport_extent[1]
        if not math.isclose(
            self.current_aspect_ratio,
            expected_aspect,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("current aspect ratio does not match viewport extent")
        for name in ("scene_fade", "content_fade"):
            value = _finite(getattr(self, name), name=name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
            object.__setattr__(self, name, value)
        border_width = _finite(self.border_width, name="border width")
        if border_width < 0.0:
            raise ValueError("border width must be non-negative")
        object.__setattr__(self, "border_width", border_width)
        object.__setattr__(
            self,
            "shell_style",
            _coerce_frozen_fields(self.shell_style, name="shell style"),
        )

    @property
    def content_viewport_size(self) -> SizeTuple:
        return self.viewport_extent


@dataclass(frozen=True, slots=True)
class VisualizerRenderSnapshot:
    logical_revision: int
    logical: VisualizerLogicalFrame
    presentation: ResolvedVisualizerPresentation

    def __post_init__(self) -> None:
        revision = int(self.logical_revision)
        if revision <= 0:
            raise ValueError("logical revision must be positive")
        if not isinstance(self.logical, VisualizerLogicalFrame):
            raise TypeError("logical state must be VisualizerLogicalFrame")
        if not isinstance(self.presentation, ResolvedVisualizerPresentation):
            raise TypeError("presentation must be ResolvedVisualizerPresentation")
        object.__setattr__(self, "logical_revision", revision)


def compose_visualizer_render_snapshot(
    logical: VisualizerLogicalFrame,
    presentation: ResolvedVisualizerPresentation,
    *,
    logical_revision: int,
) -> VisualizerRenderSnapshot:
    """Compose one complete render snapshot at the GUI/Quick sync boundary."""

    if not isinstance(logical, VisualizerLogicalFrame):
        raise TypeError("logical frame must be immutable VisualizerLogicalFrame")
    if not isinstance(presentation, ResolvedVisualizerPresentation):
        raise TypeError("presentation must already be resolved")
    return VisualizerRenderSnapshot(
        logical_revision=logical_revision,
        logical=logical,
        presentation=presentation,
    )


__all__ = [
    "BubbleFrame",
    "CANONICAL_VISUALIZER_BASELINE_ASPECT_RATIO",
    "CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE",
    "DevCurveFrame",
    "FrozenFields",
    "ModeFrame",
    "OscilloscopeFrame",
    "ResolvedVisualizerPresentation",
    "SineFrame",
    "SphereFrame",
    "SpectrumFrame",
    "VisualizerCommonState",
    "VisualizerEnergyState",
    "VisualizerLogicalFrame",
    "VisualizerProtectedEdge",
    "VisualizerRenderSnapshot",
    "VisualizerTransientState",
    "compose_visualizer_render_snapshot",
    "freeze_render_fields",
    "freeze_render_value",
]
