"""Immutable post-DSP inputs for deterministic visualizer replay.

Schema 1 carries the normalised lanes only, each validated into ``0..1``. Real music is far
louder than that (``Docs/Guides/Visualizer_Reactivity_Authoring.md`` 2A: transient-bus loudness
3-17, the live pre-AGC lane pinned at its 2.5 clamp), so schema 2 adds optional ``RealScaleLanes``
in the units production reads them in, finite and non-negative but never capped, plus the seams
Voxel Sphere consumes. A schema 1 frame serialises exactly as before.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from numbers import Real
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = 1
REAL_SCALE_SCHEMA_VERSION = 2          # frames that carry RealScaleLanes
SUPPORTED_SCHEMA_VERSIONS = frozenset({SCHEMA_VERSION, REAL_SCALE_SCHEMA_VERSION})
TIMESTAMP_UNIT = "us"
RAW_BAR_COUNT = 32
WAVEFORM_COUNT = 64

SUPPORTED_MODES = frozenset(
    {"spectrum", "oscilloscope", "sine_wave", "bubble", "devcurve", "sphere", "shockwave_grid"}
)
# Modes whose inputs exist only in the real-scale lanes (schema 2).
REAL_SCALE_MODES = frozenset({"sphere", "shockwave_grid"})
TYPED_EVENT_KINDS = frozenset({"kick", "snare", "vocal_swell"})
LIVE_LANE_CLAMP = 2.5          # get_live_pre_agc_energy_bands' bound
CONTROL_EVENTS = frozenset({"none", "mode_switch", "visibility_toggle"})
ONSET_TYPES = frozenset({"bass", "mid", "high", "broadband"})


def _finite_unit_value(
    value: float,
    name: str,
    *,
    signed: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")

    result = float(value)
    lower_bound = -1.0 if signed else 0.0
    if not math.isfinite(result) or not lower_bound <= result <= 1.0:
        raise ValueError(
            f"{name} must be finite and in [{lower_bound}, 1.0]"
        )
    return result


def _fixed_tuple(
    values: Iterable[float],
    count: int,
    name: str,
    *,
    signed: bool = False,
) -> tuple[float, ...]:
    result = tuple(
        _finite_unit_value(value, f"{name}[{index}]", signed=signed)
        for index, value in enumerate(values)
    )
    if len(result) != count:
        raise ValueError(f"{name} must contain exactly {count} values")
    return result


def _finite_non_negative(value: float, name: str, *, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result) or result < 0.0 or (maximum is not None and result > maximum):
        bound = "" if maximum is None else f" and <= {maximum}"
        raise ValueError(f"{name} must be finite, >= 0{bound}")
    return result


@dataclass(frozen=True, slots=True)
class TypedEvent:
    """One scheduler event (``kick``, ``snare``, ``vocal_swell``) available on its frame."""

    kind: str
    strength: float

    def __post_init__(self) -> None:
        if self.kind not in TYPED_EVENT_KINDS:
            raise ValueError(f"unsupported typed event kind: {self.kind}")
        object.__setattr__(self, "strength", _finite_unit_value(self.strength, "strength"))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TypedEvent":
        return cls(kind=payload["kind"], strength=payload["strength"])


@dataclass(frozen=True, slots=True)
class RecordedOnset:
    """One transient-bus ``MusicalOnset`` published on its frame (the serial is the replay's own)."""

    kind: str
    strength: float
    magnitude: float
    loudness: float
    presence: float

    def __post_init__(self) -> None:
        if self.kind not in TYPED_EVENT_KINDS:
            raise ValueError(f"unsupported onset kind: {self.kind}")
        object.__setattr__(self, "strength", _finite_unit_value(self.strength, "strength"))
        for name in ("magnitude", "loudness", "presence"):
            object.__setattr__(self, name, _finite_non_negative(getattr(self, name), name))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RecordedOnset":
        return cls(kind=payload["kind"], strength=payload["strength"], magnitude=payload["magnitude"],
                   loudness=payload["loudness"], presence=payload["presence"])


@dataclass(frozen=True, slots=True)
class RealScaleLanes:
    """Production-unit inputs (schema 2): the live pre-AGC bands as
    ``get_live_pre_agc_energy_bands`` returns them (0..2.5), the transient bus's
    (loudness, presence) as ``get_musical_level`` does (unbounded), the raw pre-shape/pre-AGC
    analysis spectrum (``get_pre_agc_analysis_spectrum``), the typed scheduler events available on
    this frame and the bus's ``MusicalOnset``s published since the previous frame."""

    live: tuple[float, float, float, float]
    musical_level: tuple[float, float]
    analysis_spectrum: tuple[float, ...]
    events: tuple[TypedEvent, ...] = ()
    onsets: tuple[RecordedOnset, ...] = ()

    def __post_init__(self) -> None:
        live = tuple(self.live)
        if len(live) != 4:
            raise ValueError("live must be (bass, mid, high, overall)")
        object.__setattr__(self, "live", tuple(
            _finite_non_negative(v, f"live[{i}]", maximum=LIVE_LANE_CLAMP) for i, v in enumerate(live)))
        level = tuple(self.musical_level)
        if len(level) != 2:
            raise ValueError("musical_level must be (loudness, presence)")
        object.__setattr__(self, "musical_level", tuple(
            _finite_non_negative(v, f"musical_level[{i}]") for i, v in enumerate(level)))
        spectrum = tuple(_finite_non_negative(v, f"analysis_spectrum[{i}]")
                         for i, v in enumerate(self.analysis_spectrum))
        if spectrum and not 8 <= len(spectrum) <= 1024:
            raise ValueError("analysis_spectrum must be empty or hold 8..1024 bands")
        object.__setattr__(self, "analysis_spectrum", spectrum)
        events = tuple(self.events)
        if any(not isinstance(event, TypedEvent) for event in events):
            raise TypeError("events must be TypedEvent instances")
        if len({event.kind for event in events}) != len(events):
            raise ValueError("at most one event of each kind per frame")
        object.__setattr__(self, "events", events)
        onsets = tuple(self.onsets)
        if any(not isinstance(onset, RecordedOnset) for onset in onsets):
            raise TypeError("onsets must be RecordedOnset instances")
        object.__setattr__(self, "onsets", onsets)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RealScaleLanes":
        return cls(
            live=tuple(payload["live"]),
            musical_level=tuple(payload["musical_level"]),
            analysis_spectrum=tuple(payload["analysis_spectrum"]),
            events=tuple(TypedEvent.from_dict(event) for event in payload.get("events", ())),
            onsets=tuple(RecordedOnset.from_dict(onset) for onset in payload.get("onsets", ())),
        )


@dataclass(frozen=True, slots=True)
class BandEnergy:
    """One normalized energy sample across the visualizer frequency bands."""

    bass: float
    mid: float
    high: float
    overall: float

    def __post_init__(self) -> None:
        for name in ("bass", "mid", "high", "overall"):
            object.__setattr__(
                self,
                name,
                _finite_unit_value(getattr(self, name), name),
            )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BandEnergy":
        return cls(
            bass=payload["bass"],
            mid=payload["mid"],
            high=payload["high"],
            overall=payload["overall"],
        )


@dataclass(frozen=True, slots=True)
class TransientEnergy(BandEnergy):
    """Band energy plus the discrete onset accepted by the visualizer."""

    onset_detected: bool
    onset_type: str
    onset_strength: float

    def __post_init__(self) -> None:
        BandEnergy.__post_init__(self)

        if type(self.onset_detected) is not bool:
            raise TypeError("onset_detected must be bool")
        if not isinstance(self.onset_type, str):
            raise TypeError("onset_type must be str")

        object.__setattr__(
            self,
            "onset_strength",
            _finite_unit_value(self.onset_strength, "onset_strength"),
        )

        if self.onset_detected:
            if self.onset_type not in ONSET_TYPES:
                raise ValueError(f"unsupported onset_type: {self.onset_type}")
            if self.onset_strength == 0.0:
                raise ValueError(
                    "detected onset must have positive onset_strength"
                )
        elif self.onset_type or self.onset_strength != 0.0:
            raise ValueError(
                "undetected onset must use an empty type and zero strength"
            )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TransientEnergy":
        return cls(
            bass=payload["bass"],
            mid=payload["mid"],
            high=payload["high"],
            overall=payload["overall"],
            onset_detected=payload["onset_detected"],
            onset_type=payload["onset_type"],
            onset_strength=payload["onset_strength"],
        )


@dataclass(frozen=True, slots=True)
class EnergyLanes:
    """All post-DSP energy representations consumed by visualizer modes."""

    continuous: BandEnergy
    pre_agc: BandEnergy
    bubble: BandEnergy
    transient: TransientEnergy

    def __post_init__(self) -> None:
        for name in ("continuous", "pre_agc", "bubble"):
            if type(getattr(self, name)) is not BandEnergy:
                raise TypeError(f"{name} must be BandEnergy")
        if not isinstance(self.transient, TransientEnergy):
            raise TypeError("transient must be TransientEnergy")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EnergyLanes":
        return cls(
            continuous=BandEnergy.from_dict(payload["continuous"]),
            pre_agc=BandEnergy.from_dict(payload["pre_agc"]),
            bubble=BandEnergy.from_dict(payload["bubble"]),
            transient=TransientEnergy.from_dict(payload["transient"]),
        )


@dataclass(frozen=True, slots=True)
class FeatureFrame:
    """One timestamped feature frame at the post-DSP replay boundary."""

    timestamp_us: int
    energy: EnergyLanes
    raw_bars: tuple[float, ...]
    waveform: tuple[float, ...]
    playing: bool
    visible: bool
    mode: str
    control_event: str = "none"
    schema_version: int = SCHEMA_VERSION
    real: RealScaleLanes | None = None

    def __post_init__(self) -> None:
        if type(self.timestamp_us) is not int or self.timestamp_us < 0:
            raise ValueError("timestamp_us must be a non-negative integer")
        if self.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"unsupported feature schema version: {self.schema_version}"
            )
        if self.real is not None and not isinstance(self.real, RealScaleLanes):
            raise TypeError("real must be RealScaleLanes")
        if (self.real is not None) != (self.schema_version == REAL_SCALE_SCHEMA_VERSION):
            raise ValueError("real-scale lanes and schema 2 go together")
        if self.mode in REAL_SCALE_MODES and self.real is None:
            raise ValueError(f"{self.mode} replay needs the real-scale lanes (schema 2)")
        if not isinstance(self.energy, EnergyLanes):
            raise TypeError("energy must be EnergyLanes")

        object.__setattr__(
            self,
            "raw_bars",
            _fixed_tuple(self.raw_bars, RAW_BAR_COUNT, "raw_bars"),
        )
        object.__setattr__(
            self,
            "waveform",
            _fixed_tuple(
                self.waveform,
                WAVEFORM_COUNT,
                "waveform",
                signed=True,
            ),
        )

        if type(self.playing) is not bool or type(self.visible) is not bool:
            raise TypeError("playing and visible must be bool")
        if self.mode not in SUPPORTED_MODES:
            raise ValueError(f"unsupported mode: {self.mode}")
        if self.control_event not in CONTROL_EVENTS:
            raise ValueError(
                f"unsupported control_event: {self.control_event}"
            )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.real is None:
            del payload["real"]          # a schema 1 frame serialises exactly as before
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FeatureFrame":
        real = payload.get("real")
        return cls(
            timestamp_us=payload["timestamp_us"],
            energy=EnergyLanes.from_dict(payload["energy"]),
            raw_bars=tuple(payload["raw_bars"]),
            waveform=tuple(payload["waveform"]),
            playing=payload["playing"],
            visible=payload["visible"],
            mode=payload["mode"],
            control_event=payload.get("control_event", "none"),
            schema_version=payload.get("schema_version", SCHEMA_VERSION),
            real=None if real is None else RealScaleLanes.from_dict(real),
        )


@dataclass(frozen=True, slots=True)
class FeatureClip:
    """A named, strictly ordered sequence of immutable feature frames."""

    name: str
    frames: tuple[FeatureFrame, ...]

    def __post_init__(self) -> None:
        if not self.name or not self.name.replace("_", "").isalnum():
            raise ValueError(
                "clip name must be non-empty alphanumeric snake_case"
            )
        if not self.frames:
            raise ValueError("clip must contain at least one frame")
        if any(not isinstance(frame, FeatureFrame) for frame in self.frames):
            raise TypeError("frames must be FeatureFrame instances")
        if any(
            right.timestamp_us <= left.timestamp_us
            for left, right in zip(self.frames, self.frames[1:])
        ):
            raise ValueError("clip timestamps must be strictly monotonic")

    def to_jsonl_bytes(self) -> bytes:
        return b"".join(
            canonical_json(frame.to_dict()) + b"\n" for frame in self.frames
        )

    @classmethod
    def from_jsonl_bytes(cls, name: str, data: bytes) -> "FeatureClip":
        lines = data.decode("utf-8").splitlines()
        if not lines:
            raise ValueError("clip JSONL is empty")
        return cls(
            name=name,
            frames=tuple(
                FeatureFrame.from_dict(json.loads(line)) for line in lines
            ),
        )

    def sha256(self) -> str:
        return sha256_hex(self.to_jsonl_bytes())


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_jsonl(path: str | Path, *, name: str | None = None) -> FeatureClip:
    source = Path(path)
    return FeatureClip.from_jsonl_bytes(
        name or source.stem,
        source.read_bytes(),
    )