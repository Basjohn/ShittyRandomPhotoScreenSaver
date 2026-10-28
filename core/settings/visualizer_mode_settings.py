"""Each Visualizer mode's own Settings, declared once.

A mode's spec lists the controls its Settings body offers, in order, grouped into its collapsible
buckets: the persisted key, label, range, tooltip and who consumes the value (the renderer, by
default, or the mode's authored logical evolution). From the spec:

- the settings model gains the fields, reads, clamps and serializes them
  (``core/settings/models/_spotify_visualizer.py``);
- the logical and presentation appliers store them on their owner, so canonical defaults install
  through the same path (``widgets/spotify_visualizer/config_applier.py``);
- the renderer receives every presentation value in the mode's parameters under its own key;
- the Visualizers tab builds, loads and saves the body (``ui/tabs/media/spec_mode_builder.py``);
- ``tests/test_visualizer_mode_settings_spec.py`` checks each spec against the canonical defaults,
  the registry and the real Settings body.

Values never live here: defaults stay in the canonical defaults and presets stay authored. A body
part no control type describes (Spectrum's shape editor, smoothing controls) is a ``Custom`` entry
naming its own build/load/collect functions by import path, so this module stays free of Qt.

``source=True`` delegates a control to the existing descriptor source-profile projection, without
creating private logical or presentation attributes under its authored mode key. That projection
owns the aliases: source shaping reaches BeatEngine, while ordinary ghost aliases reach the existing
shared logical and presentation consumers. It introduces no new runtime owner.

``authoring=True`` choices persist convenience metadata without installing a runtime attribute.
``enabled_when`` keeps dependent controls visible and preserves their values while disabling them;
``when`` hides irrelevant rows without changing saved values. Both accept an AND tuple of predicate
pairs; Choice predicates may admit a tuple of alternative values;
``when`` hides their rows. Runtime aliases and strict admission remain configuration-only. Immutable
specs cache their derived control/consumer tuples; frame extraction does not rebuild membership.

Visual controls (``Range``, ``Triangle``, ``Direction``) persist short lists and are shown by the shared widgets in
``ui/widgets/visual_controls.py``; prefer them to number pairs for spans, proportions and directions.

Adding a setting to a spec'd mode is its default plus one control here; the renderer reads it by key.
A control may also be shown only while another control holds a value (``when``), so a group that only
matters while its toggle is on hides with it.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from functools import cached_property
from importlib import import_module
from types import MappingProxyType
from typing import Union

from rendering.gl_programs.extruded_spectrum_options import EXTRUDED_COLOURINGS
from rendering.gl_programs.neon_lake_basin_options import BASIN_SURFACE_STYLES, BASIN_BODY_MODES
from core.settings.visualizer_settings_contract import SPHERE_FINISH_VALUES


def _finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


@dataclass(frozen=True)
class Bucket:
    """A collapsible group of controls. ``advanced`` places it under the mode's Advanced toggle."""

    key: str
    title: str
    helper: str = ""
    advanced: bool = False


Predicate = tuple[str, bool | str | int | tuple[str, ...]]
When = Predicate | tuple[Predicate, ...]
EnabledWhen = When | tuple[Predicate, ...]


@dataclass(frozen=True)
class Slider:
    """A float shown on a slider of ``scale`` positions per unit (0.01 steps by default).

    Its value reads as ``decimals`` places plus ``suffix``, or as a whole percent (``percent``);
    ``integer`` keeps it a whole number; ``tick`` marks every that many positions under it;
    ``signed`` shows a plus sign for nonnegative values. ``source`` delegates consumption to the
    existing descriptor source-profile projection; it creates no private logical/renderer value.
    ``availability`` optionally names an import-safe capability flag and its disabled tooltip.
    ``truncate`` retains a body's existing position and integer conversion. Admission bounds
    preserve a wider stored domain than the slider; runtime bounds independently retain existing
    consumer caps. ``display_multiplier`` changes only the label's units."""

    key: str
    label: str
    low: float
    high: float
    tooltip: str = ""
    bucket: str = ""
    logical: bool = False
    scale: int = 100
    decimals: int = 2
    suffix: str = ""
    percent: bool = False
    integer: bool = False
    tick: int = 0
    when: When = ()
    signed: bool = False
    source: bool = False
    availability: tuple[str, str] = ()
    truncate: bool = False
    admission_high: float | None = None
    bottom_padding: int = 0
    enabled_when: EnabledWhen = ()
    recommended: float | None = None
    runtime_strict: bool = False
    admission_low: float | None = None
    runtime_low: float | None = None
    runtime_high: float | None = None
    display_multiplier: float = 1.0

    def position(self, value: object) -> int:
        number = float(value) * self.scale
        return int(number) if self.truncate else round(number)

    def _admit_bounds(self, value: object, default: object, low: float, high: float) -> float | int:
        number = _finite(value)
        if number is None:
            number = float(default)
        number = max(float(low), min(float(high), number))
        if self.integer:
            return int(number) if self.truncate else int(round(number))
        return number

    def admit(self, value: object, default: object) -> float | int:
        low = self.low if self.admission_low is None else self.admission_low
        high = self.high if self.admission_high is None else self.admission_high
        return self._admit_bounds(value, default, low, high)

    def coerce(self, value: object) -> float | int:
        return int(value) if self.integer else float(value)

    def admit_runtime(self, value: object, default: object) -> float | int:
        if self.runtime_strict:
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{self.key} must be numeric") from exc
            if not math.isfinite(number):
                raise ValueError(f"{self.key} must be finite")
            value = number
        low = self.low if self.admission_low is None else self.admission_low
        high = self.high if self.admission_high is None else self.admission_high
        return self._admit_bounds(value, default,
                                  low if self.runtime_low is None else self.runtime_low,
                                  high if self.runtime_high is None else self.runtime_high)

    def text(self, position: int) -> str:
        """The value label for a slider position."""
        if self.percent:
            return f"{round(position * 100 / self.scale)}%"
        sign = "+" if self.signed else ""
        return f"{position / self.scale * self.display_multiplier:{sign}.{self.decimals}f}{self.suffix}"


@dataclass(frozen=True)
class Toggle:
    """A checkbox; ``text`` is the checkbox's own words, ``label`` its row label (none: the checkbox
    stands alone across the bucket). ``row_group`` places toggles together in one aligned row.
    ``also_presentation`` lets a logical setting feed both existing consumers from one intent."""

    key: str
    label: str
    text: str
    tooltip: str = ""
    bucket: str = ""
    logical: bool = False
    when: When = ()
    row_group: str = ""
    source: bool = False
    availability: tuple[str, str] = ()
    runtime_attr: str = ""
    read: str = ""
    input_aliases: tuple[str, ...] = ()
    enabled_when: EnabledWhen = ()
    runtime_bool: bool = False
    also_presentation: bool = False

    def admit(self, value: object, default: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return bool(value)
        if isinstance(value, str) and value.strip().lower() in {"true", "1", "on", "yes"}:
            return True
        if isinstance(value, str) and value.strip().lower() in {"false", "0", "off", "no"}:
            return False
        return bool(default)

    def coerce(self, value: object) -> bool:
        return bool(value)

    def admit_runtime(self, value: object, default: object) -> bool:
        return bool(value) if self.runtime_bool else self.admit(value, default)


@dataclass(frozen=True)
class Choice:
    """A drop-down of fixed labels; an unknown stored value becomes the default. It persists the
    label, or its position among ``choices`` when ``indexed`` (a number outside them is clamped in).
    Optional ``labels`` display friendly text while ``choices`` remain the persisted values."""

    key: str
    label: str
    choices: tuple[str, ...]
    tooltip: str = ""
    bucket: str = ""
    logical: bool = False
    indexed: bool = False
    when: When = ()
    source: bool = False
    availability: tuple[str, str] = ()
    compact: bool = True
    runtime_attr: str = ""
    runtime_values: tuple[object, ...] = ()
    read: str = ""
    input_aliases: tuple[str, ...] = ()
    enabled_when: EnabledWhen = ()
    authoring: bool = False
    runtime_strict: bool = False
    ingress_strict: bool = False
    normalizer: str = ""
    uppercase: bool = False
    labels: tuple[str, ...] = ()
    size_variant: str = ""
    direction_mapper: bool = False

    def _normalize(self, value: object) -> object:
        if self.normalizer:
            module, _, name = self.normalizer.partition(":")
            return getattr(import_module(module), name)(value)
        return str(value).strip().upper() if self.uppercase else value

    def admit(self, value: object, default: object) -> str | int:
        try:
            value = self._normalize(value)
        except ValueError:
            if self.ingress_strict:
                raise
            return str(default)
        if self.indexed:
            number = None if isinstance(value, bool) else _finite(value)
            if number is None or number != int(number):
                return int(default)
            return max(0, min(len(self.choices) - 1, int(number)))
        if isinstance(value, str) and value in self.choices:
            return value
        if self.ingress_strict:
            raise ValueError(f"invalid {self.key} {value!r}")
        return str(default)

    def coerce(self, value: object) -> str | int:
        return int(value) if self.indexed else str(value)

    def admit_runtime(self, value: object, default: object) -> str | int:
        value = self._normalize(value)
        if self.runtime_strict and value not in self.choices:
            raise ValueError(f"invalid {self.key} {value!r}")
        return self.admit(value, default)


@dataclass(frozen=True)
class Colour:
    """An RGBA swatch persisted as four 0-255 integers (``alpha`` False hides the alpha channel)."""

    key: str
    label: str
    title: str
    tooltip: str = ""
    bucket: str = ""
    logical: bool = False
    alpha: bool = True
    when: When = ()
    source: bool = False
    availability: tuple[str, str] = ()
    swatch_row: bool = True
    runtime_strict: bool = False
    enabled_when: EnabledWhen = ()

    def admit(self, value: object, default: object) -> list[int]:
        channels = list(value) if isinstance(value, (list, tuple)) else []
        numbers = [_finite(channel) for channel in channels[:4]]
        if len(numbers) < 3 or any(number is None for number in numbers):
            numbers = [float(channel) for channel in list(default)[:4]]
        while len(numbers) < 4:
            numbers.append(255.0)
        return [max(0, min(255, int(round(number)))) for number in numbers]

    def coerce(self, value: object) -> list:
        return list(value)

    def admit_runtime(self, value: object, default: object) -> list[int] | tuple[int, ...]:
        if self.runtime_strict:
            if not isinstance(value, (list, tuple)) or len(value) < 3:
                raise ValueError(f"{self.key} must be an RGB/RGBA sequence")
            if any(_finite(channel) is None for channel in value[:4]):
                raise ValueError(f"{self.key} must contain numeric RGB/RGBA channels")
            return tuple(self.admit(value, default))
        return self.admit(value, default)


@dataclass(frozen=True)
class Range:
    """Two floats on one bar, ``low <= high``, persisted as ``[low, high]`` and shown as the shared range
    slider (``ui/widgets/visual_controls.py``) of ``scale`` positions per unit. The usual reactive use: what an
    amount is with quiet music (low) and with loud music (high). Labels read as ``Slider`` values do."""

    key: str
    label: str
    low: float
    high: float
    tooltip: str = ""
    bucket: str = ""
    logical: bool = False
    scale: int = 100
    decimals: int = 2
    suffix: str = ""
    percent: bool = False
    integer: bool = False
    when: When = ()
    enabled_when: EnabledWhen = ()
    source: bool = False
    availability: tuple[str, str] = ()

    def admit(self, value: object, default: object) -> list[float | int]:
        pair = list(value) if isinstance(value, (list, tuple)) else []
        numbers = [_finite(v) for v in pair[:2]]
        if len(numbers) != 2 or any(number is None for number in numbers):
            numbers = [float(v) for v in list(default)[:2]]
        numbers = sorted(max(float(self.low), min(float(self.high), number)) for number in numbers)
        return [int(round(number)) for number in numbers] if self.integer else numbers

    def coerce(self, value: object) -> list:
        return list(value)

    def admit_runtime(self, value: object, default: object) -> tuple:
        return tuple(self.admit(value, default))

    def positions(self, value: object) -> tuple[int, int]:
        low, high = self.admit(value, value)
        return round(low * self.scale), round(high * self.scale)

    def text(self, positions: tuple[int, int]) -> str:
        def one(position: int) -> str:
            if self.percent:
                return f"{round(position * 100 / self.scale)}%"
            if self.integer:
                return f"{round(position / self.scale)}{self.suffix}"
            return f"{position / self.scale:.{self.decimals}f}{self.suffix}"
        return f"{one(positions[0])} – {one(positions[1])}"


@dataclass(frozen=True)
class Triangle:
    """Three shares placed by one node inside a triangle (``corners`` name its top, bottom-left and
    bottom-right), persisted as three fractions summing to 1; shown as the shared triangle mapper."""

    key: str
    label: str
    corners: tuple[str, str, str]
    tooltip: str = ""
    bucket: str = ""
    logical: bool = False
    when: When = ()
    enabled_when: EnabledWhen = ()
    source: bool = False
    availability: tuple[str, str] = ()

    def admit(self, value: object, default: object) -> list[float]:
        shares = list(value) if isinstance(value, (list, tuple)) else []
        numbers = [_finite(v) for v in shares[:3]]
        if len(numbers) != 3 or any(n is None or n < 0.0 for n in numbers) or sum(numbers) <= 0.0:
            numbers = [float(v) for v in list(default)[:3]]
        total = sum(numbers)
        return [round(n / total, 4) for n in numbers]

    def coerce(self, value: object) -> list:
        return list(value)

    def admit_runtime(self, value: object, default: object) -> tuple:
        return tuple(self.admit(value, default))

    def text(self, value: object) -> str:
        shares = self.admit(value, value)
        return " · ".join(f"{name} {round(share * 100)}%" for name, share in zip(self.corners, shares))


@dataclass(frozen=True)
class Direction:
    """A direction persisted as ``[around, height]`` degrees and placed on the shared direction mapper's
    disc: ``around`` is the angle round it (0 up, clockwise, wrapped to [-180, 180)), ``height`` its
    distance from the rim (the disc's centre is ``height_high``, its rim ``height_low``). ``centre_text``
    names the centre ("Overhead", "Into Scene"); ``marker`` is "arrow" (a stream) or "light". Equal height
    bounds make it a plain angle dial (2D directions: gradients, shadows, screen-plane rays)."""

    key: str
    label: str
    height_low: float = 0.0
    height_high: float = 90.0
    centre_text: str = ""
    marker: str = "arrow"
    midline: bool = False  # optional horizontal horizon/height guide, not a value
    tooltip: str = ""
    bucket: str = ""
    logical: bool = False
    when: When = ()
    enabled_when: EnabledWhen = ()
    source: bool = False
    availability: tuple[str, str] = ()

    def admit(self, value: object, default: object) -> list[float]:
        pair = list(value) if isinstance(value, (list, tuple)) else []
        numbers = [_finite(v) for v in pair[:2]]
        if len(numbers) != 2 or any(number is None for number in numbers):
            numbers = [float(v) for v in list(default)[:2]]
        around = (numbers[0] + 180.0) % 360.0 - 180.0
        height = max(float(self.height_low), min(float(self.height_high), numbers[1]))
        return [round(around, 1), round(height, 1)]

    def coerce(self, value: object) -> list:
        return list(value)

    def admit_runtime(self, value: object, default: object) -> tuple:
        return tuple(self.admit(value, default))

    def text(self, value: object) -> str:
        around, height = self.admit(value, value)
        if self.height_high - self.height_low < 1e-6:
            return f"{round(around)}°"               # a plain angle dial
        return f"Around {round(around)}°, Height {round(height)}°"


@dataclass(frozen=True)
class ScenePath(Direction):
    """Two independently placed 3D endpoints in a fixed world box (normalized xyz).

    Old [around, height] presets are interpreted, never overwritten. The Settings
    control shows screen x/y plus independent source/end depth handles.
    """
    legacy_kind: str = "stream"

    def admit(self, value: object, default: object) -> list[float]:
        from core.settings.visualizer_paths import admit_path
        return list(admit_path(value, default, self.legacy_kind))

    def text(self, value: object) -> str:
        x = self.admit(value, value)
        return f"Source ({x[0]:+.2f}, {x[1]:+.2f}, {x[2]:+.2f}) → End ({x[3]:+.2f}, {x[4]:+.2f}, {x[5]:+.2f})"


@dataclass(frozen=True)
class SceneVolumePath(ScenePath):
    """EB-specific oblique 3D world-path editor; persists the SAME six coordinates."""


@dataclass(frozen=True)
class SceneCameraPosition(Direction):
    """User camera world translation in world-box units, separate from orbit/FOV.

    Values are offsets from the existing physical eye, not an alternate camera;
    Settings composes the current live pose into the visible camera marker.
    """

    def admit(self, value: object, default: object) -> list[float]:
        try:
            nums = [float(v) for v in value]
            if len(nums) != 3 or any(not math.isfinite(v) for v in nums):
                raise ValueError('Camera offset requires finite xyz')
        except (TypeError, ValueError, OverflowError):
            nums = [float(v) for v in default]
        return [round(max(-8.0, min(8.0, v)), 6) for v in nums]

    def text(self, value: object) -> str:
        x, y, z = self.admit(value, value)
        return f'Camera translation x {x:+.2f}, y {y:+.2f}, depth {z:+.2f}'


@dataclass(frozen=True)
class Custom:
    """A body part built by the mode's own code: ``build(tab, layout)``, ``load(tab, config)`` and
    ``collect(tab) -> dict`` named as ``"module:function"``. Its persisted keys stay with their
    existing owner (they are listed in ``keys`` only so the spec knows what the body covers)."""

    name: str
    bucket: str
    build: str
    load: str = ""
    collect: str = ""
    keys: tuple[str, ...] = ()


Control = Union[Slider, Toggle, Choice, Colour, Range, Triangle, Direction, SceneVolumePath, SceneCameraPosition]
Entry = Union[Slider, Toggle, Choice, Colour, Range, Triangle, Direction, SceneVolumePath, SceneCameraPosition, Custom]
# Controls shown by a shared visual control (``ui/widgets/visual_controls.py``) rather than a stock widget.
VISUAL_CONTROLS = (Range, Triangle, Direction, ScenePath, SceneVolumePath, SceneCameraPosition)


@dataclass(frozen=True)
class ModeSettings:
    """One mode's Settings body. ``attr_prefix`` names the body's scaffold attributes
    (``_<prefix>_settings_container``, ``_<prefix>_normal``...), the mode id unless older code
    already names them otherwise."""

    mode_id: str
    buckets: tuple[Bucket, ...]
    entries: tuple[Entry, ...]
    attr_prefix: str = ""
    auto_switch: bool = True

    @property
    def prefix(self) -> str:
        return self.attr_prefix or self.mode_id

    @cached_property
    def controls(self) -> tuple[Control, ...]:
        return tuple(entry for entry in self.entries if not isinstance(entry, Custom))

    def control(self, key: str) -> Control:
        for control in self.controls:
            if control.key == key:
                return control
        raise KeyError(f"{self.mode_id} declares no control {key!r}")

    def keys(self) -> tuple[str, ...]:
        return tuple(control.key for control in self.controls)

    def bucket(self, key: str) -> Bucket:
        for bucket in self.buckets:
            if bucket.key == key:
                return bucket
        raise KeyError(f"{self.mode_id} declares no bucket {key!r}")

    def presentation_controls(self) -> tuple[Control, ...]:
        return self._presentation_controls

    @cached_property
    def _presentation_controls(self) -> tuple[Control, ...]:
        return tuple(control for control in self.controls
                     if (not control.logical or getattr(control, "also_presentation", False)) and not control.source
                     and not getattr(control, "authoring", False))

    def logical_controls(self) -> tuple[Control, ...]:
        return self._logical_controls

    @cached_property
    def _logical_controls(self) -> tuple[Control, ...]:
        return tuple(control for control in self.controls if control.logical and not control.source
                     and not getattr(control, "authoring", False))

    def authoring_controls(self) -> tuple[Control, ...]:
        return self._authoring_controls

    @cached_property
    def _authoring_controls(self) -> tuple[Control, ...]:
        return tuple(control for control in self.controls if getattr(control, "authoring", False))

    def source_controls(self) -> tuple[Control, ...]:
        return self._source_controls

    @cached_property
    def _source_controls(self) -> tuple[Control, ...]:
        return tuple(control for control in self.controls if control.source)


# ---- Shockwave Grid ----------------------------------------------------------------------------

_BASIN_WIRE_CHOICES = tuple(BASIN_SURFACE_STYLES)
_BASIN_GLASS = tuple(value for value,bits in BASIN_SURFACE_STYLES.items() if bits&4)
_BASIN_PLAIN_POINTS = tuple(value for value,bits in BASIN_SURFACE_STYLES.items() if bits&2 and not bits&4)
_BASIN_GLASS_POINTS = tuple(value for value,bits in BASIN_SURFACE_STYLES.items() if bits&6==6)
_BASIN_BODY = ("shockwave_grid_sun_enabled", True)
_TERRAIN_REACTION = ("shockwave_grid_terrain_reaction_enabled", True)
_SKY = ("shockwave_grid_sky_enabled", True)
_CLOUDS = (_SKY, ("shockwave_grid_volumetric_clouds", True))
_NEBULA = (_SKY, ("shockwave_grid_nebula_enabled", True))


_NEON_AUTO_ROTATE = ("shockwave_grid_auto_rotate", True)

_SHOCKWAVE_GRID = ModeSettings(
    "shockwave_grid",
    buckets=(
        Bucket("terrain", "Terrain", "Sculpt mountains and islands; exact base-level regions are the lake's water."),
        Bucket("waves", "Water", "The lake's colours, its musical waves, flow, idle swell and reflection."),
        Bucket("reaction", "Terrain Reaction",
               "Let the music reshape the land for a moment: ground waves from each hit, landforms that rise "
               "and sink with their part of the spectrum, and an optional slow swell. The shoreline never moves."),
        Bucket("render", "Surface", "How the land and water are drawn: vertices, glass or both, and the horizon line.",
               advanced=True),
        Bucket("sky", "Sky", "Atmosphere, clouds and stars, and stars that flare on strong beats.", advanced=True),
        Bucket("celestial", "Sun & Moon", "The Sun or Moon, its halo, placement, orbit and light rays.", advanced=True),
        Bucket("glow", "Glow", "How brightly the land, ridges and water lines glow.", advanced=True),
        Bucket("camera", "Camera", "The camera's lens; fly the view itself with the keyboard and mouse.",
               advanced=True),
        Bucket("response", "Frequency Response",
               "This independent audio profile routes frequency lanes into water and ridge energy; it does not author terrain.",
               advanced=True),
    ),
    entries=(
        Custom("terrain", "terrain", "ui.tabs.media.shockwave_grid_builder:build_terrain_section",
               "ui.tabs.media.shockwave_grid_settings_binding:load_terrain_section",
               "ui.tabs.media.shockwave_grid_settings_binding:collect_terrain_section", keys=("shockwave_grid_terrain",)),
        Slider("shockwave_grid_terrain_height", "Terrain Height:", 0.0, 1.5,
               "Vertical scale of the authored solid land. Authored zero regions remain water.", bucket="terrain"),
        Slider("shockwave_grid_terrain_detail", "Terrain Detail:", 0.0, 1.0,
               "Fine surface definition on solid terrain, without moving its water boundary.", bucket="terrain"),
        Colour("shockwave_grid_terrain_fill_color", "Terrain Fill:", "Choose Terrain Fill Colour", bucket="terrain"),
        Colour("shockwave_grid_water_color", "Water Colour:", "Choose Lake Water Colour",
               "The water's authored base colour, including alpha.", bucket="waves"),
        Colour("shockwave_grid_line_color", "Ripple / Shore Colour:", "Choose Ripple and Shore Colour",
               "Base colour of water ripple lines and shoreline accents. Wave crests blend toward Wave / Ridge Glow. "
               "Alpha controls the ripple lines' opacity.", bucket="waves"),
        Colour("shockwave_grid_crest_color", "Wave / Ridge Glow:", "Choose Wave and Ridge Glow Colour",
               "Colour of musical water crests and energized terrain ridges, including alpha.",
               bucket="waves"),
        Slider("shockwave_grid_wave_height", "Wave Height:", 0.0, 1.0,
               "How high musical waves lift the water surface.", bucket="waves"),
        Slider("shockwave_grid_wave_speed", "Wave Speed:", 0.0, 1.0,
               "How fast musical waves propagate across the water.", bucket="waves"),
        Slider("shockwave_grid_water_detail", "Water Detail:", 0.0, 1.0,
               "Small surface details on the lake, separate from musical wave height.", bucket="waves"),
        Slider("shockwave_grid_scroll", "Water Flow:", 0.0, 1.0,
               "Slow surface flow across the water, without moving authored terrain.", bucket="waves"),
        Slider("shockwave_grid_idle", "Idle Swell:", 0.0, 1.0,
               "Subtle water swell between musical waves.", bucket="waves"),
        Slider("shockwave_grid_water_reflection", "Water Reflection:", 0.0, 1.0,
               "Reflection strength on the water surface.", bucket="waves"),
        Slider("shockwave_grid_water_shine", "Water Shine:", 0.0, 1.0,
               "The water's own surface, whatever the land's style: a tinted body under a rippled mirror of the sky, "
               "dark looking down and bright at grazing angles, with the Sun or Moon glinting in it.", bucket="waves"),
        Slider("shockwave_grid_splashes", "Splashes:", 0.0, 1.0,
               "Droplets thrown up where the heaviest hits land on the water. 0 turns them off.", bucket="waves"),
        Toggle("shockwave_grid_terrain_reaction_enabled", "React to Music:", "Reshape the land with the music",
               "Off keeps the land exactly as authored, with no reaction work at all.", bucket="reaction"),
        Slider("shockwave_grid_terrain_reaction_strength", "Strength:", 0.0, 1.0,
               "How far the land moves, as a share of Terrain Height.", bucket="reaction",
               when=_TERRAIN_REACTION),
        Slider("shockwave_grid_terrain_pulses", "Pulses:", 0.0, 1.0,
               "Ground waves: each hit sends a broad roll through the land, rising and sinking as it passes.",
               bucket="reaction", when=_TERRAIN_REACTION),
        Slider("shockwave_grid_terrain_peaks", "Peaks:", 0.0, 1.0,
               "Landforms answer their part of the spectrum: bass heaves the low ground, mids roll the slopes, "
               "treble lifts the peaks. Each part is weighed by its share and its change, so no one band drowns "
               "the rest.", bucket="reaction", when=_TERRAIN_REACTION),
        Slider("shockwave_grid_terrain_swell", "Swell:", 0.0, 1.0,
               "A broad, slow rise and fall across the whole land.", bucket="reaction", when=_TERRAIN_REACTION),
        Custom("terrain_shaper", "reaction", "ui.tabs.media.shockwave_grid_builder:build_reaction_shaper_section",
               "ui.tabs.media.shockwave_grid_settings_binding:load_reaction_shaper_section",
               "ui.tabs.media.shockwave_grid_settings_binding:collect_reaction_shaper_section",
               keys=("shockwave_grid_terrain_shaper",)),
        Slider("shockwave_grid_terrain_motion_speed", "Motion Speed:", 0.0, 1.0,
               "How quickly the reshaping wanders while the music plays; it holds still in silence.",
               bucket="reaction", when=_TERRAIN_REACTION),
        Slider("shockwave_grid_terrain_growth_attack", "Rise:", 0.08, 2.0,
               "Seconds for the land to answer the music.", bucket="reaction", suffix="s", when=_TERRAIN_REACTION),
        Slider("shockwave_grid_terrain_growth_release", "Settle:", 0.2, 4.0,
               "Seconds for the land to settle back after the music eases.", bucket="reaction", suffix="s",
               when=_TERRAIN_REACTION),
        Choice("shockwave_grid_wire_display", "Surface Style:", _BASIN_WIRE_CHOICES,
               "Choose vertices, glass or both; lake and mountain outlines are always independent.", bucket="render"),
        Colour("shockwave_grid_glass_tint", "Glass Tint:", "Choose Glass Tint", bucket="render",
               when=("shockwave_grid_wire_display", _BASIN_GLASS)),
        Slider("shockwave_grid_glass_strength", "Glass Strength:", 0.0, 1.0, bucket="render",
               when=("shockwave_grid_wire_display", _BASIN_GLASS)),
        Slider("shockwave_grid_glass_roughness", "Glass Roughness:", 0.05, 0.5, bucket="render",
               when=("shockwave_grid_wire_display", _BASIN_GLASS)),
        Colour("shockwave_grid_vertex_color", "Vertex Colour:", "Choose Vertex Colour", bucket="render",
               when=("shockwave_grid_wire_display", _BASIN_PLAIN_POINTS)),
        Colour("shockwave_grid_vertex_accent_color", "Vertex Accent:", "Choose Vertex Accent Colour", bucket="render",
               when=("shockwave_grid_wire_display", _BASIN_PLAIN_POINTS)),
        Colour("shockwave_grid_vertex_outline_color", "Vertex Outline:", "Choose Glass Vertex Outline Colour", bucket="render",
               when=("shockwave_grid_wire_display", _BASIN_GLASS_POINTS)),
        Slider("shockwave_grid_density", "Surface Detail:", 0.0, 1.0, "Vertex density and water-surface detail (also affects render workload).",
               bucket="render"),
        Slider("shockwave_grid_floor", "Base Opacity:", 0.0, 1.0,
               "Shared base visibility of land and water before their independent colour alpha.", bucket="render"),
        Slider("shockwave_grid_horizon_thickness", "Horizon Thickness:", 0.0, 4.0,
               "Distant horizon width in physical pixels; inherits Ridge/Shore Colour. Zero hides its highlight, not land occlusion.",
               bucket="render", scale=10, decimals=1, suffix=" px"),
        Toggle("shockwave_grid_sky_enabled", "Sky:", "Enable neon sky", bucket="sky"),
        Slider("shockwave_grid_sky_strength", "Sky Strength:", 0.0, 1.0,
               "Sky intensity behind the basin.", bucket="sky", enabled_when=("shockwave_grid_sky_enabled", True)),
        Colour("shockwave_grid_sky_color", "Sky Colour:", "Choose Basin Sky Colour", bucket="sky",
               enabled_when=("shockwave_grid_sky_enabled", True)),
        Colour("shockwave_grid_horizon_color", "Horizon:", "Choose Horizon Colour", bucket="sky",
               enabled_when=("shockwave_grid_sky_enabled", True)),
        Colour("shockwave_grid_cloud_color", "Clouds:", "Choose Cloud Colour", bucket="sky",
               enabled_when=("shockwave_grid_sky_enabled", True)),
        Colour("shockwave_grid_star_color", "Stars:", "Choose Star Colour", bucket="sky",
               enabled_when=("shockwave_grid_sky_enabled", True)),
        Toggle("shockwave_grid_volumetric_clouds", "Volumetric Clouds:", "Draw lit, drifting clouds",
               "Soft clouds across the sky, lit from the Sun or Moon's side and drifting slowly. They replace the "
               "thin cloud bands and take the Cloud Colour.", bucket="sky", when=_SKY, enabled_when=_SKY),
        Slider("shockwave_grid_cloud_coverage", "Cloud Coverage:", 0.0, 1.0, "How much of the sky the clouds cover.",
               bucket="sky", when=_CLOUDS, enabled_when=_CLOUDS),
        Slider("shockwave_grid_cloud_softness", "Cloud Softness:", 0.0, 1.0,
               "Crisp-edged clouds at 0, soft wispy ones at 1.", bucket="sky", when=_CLOUDS, enabled_when=_CLOUDS),
        Slider("shockwave_grid_cloud_scale", "Cloud Size:", 0.0, 1.0, "Large, near clouds at 0; small, far ones at 1.",
               bucket="sky", when=_CLOUDS, enabled_when=_CLOUDS),
        Slider("shockwave_grid_cloud_opacity", "Cloud Opacity:", 0.0, 1.0, "How solid the clouds are.",
               bucket="sky", when=_CLOUDS, enabled_when=_CLOUDS),
        Slider("shockwave_grid_cloud_drift", "Cloud Drift:", 0.0, 1.0, "How fast the clouds drift; 0 holds them still.",
               bucket="sky", when=_CLOUDS, enabled_when=_CLOUDS),
        Toggle("shockwave_grid_nebula_enabled", "Nebula:", "Paint a nebula into the sky",
               "Wisps of two colours behind the stars.", bucket="sky", when=_SKY, enabled_when=_SKY),
        Slider("shockwave_grid_nebula_intensity", "Nebula Intensity:", 0.0, 1.0, "How bright the nebula is.",
               bucket="sky", when=_NEBULA, enabled_when=_NEBULA),
        Slider("shockwave_grid_nebula_scale", "Nebula Detail:", 0.0, 1.0, "Broad clouds of colour at 0, fine wisps at 1.",
               bucket="sky", when=_NEBULA, enabled_when=_NEBULA),
        Slider("shockwave_grid_nebula_filaments", "Nebula Filaments:", 0.0, 1.0,
               "Soft billowing gas at 0; thin bright strands at 1.", bucket="sky", when=_NEBULA, enabled_when=_NEBULA),
        Slider("shockwave_grid_nebula_dust", "Nebula Dust:", 0.0, 1.0,
               "Dark lanes of dust through the gas that hide the stars behind them.", bucket="sky", when=_NEBULA,
               enabled_when=_NEBULA),
        Slider("shockwave_grid_nebula_position", "Nebula Position:", 0.0, 1.0,
               "Where around the sky the nebula sits; 0 is above the far shore.", bucket="sky", when=_NEBULA,
               enabled_when=_NEBULA),
        Slider("shockwave_grid_nebula_drift", "Nebula Drift:", 0.0, 1.0,
               "How fast the nebula turns slowly across the sky; 0 holds it still.", bucket="sky", when=_NEBULA,
               enabled_when=_NEBULA),
        Colour("shockwave_grid_nebula_color_a", "Nebula Rim Colour:", "Choose Nebula Rim Colour",
               "The outer gas and its filaments.", bucket="sky", when=_NEBULA, enabled_when=_NEBULA),
        Colour("shockwave_grid_nebula_color_b", "Nebula Core Colour:", "Choose Nebula Core Colour",
               "The dense heart of the gas, which burns toward white.", bucket="sky", when=_NEBULA,
               enabled_when=_NEBULA),
        Toggle("shockwave_grid_starscape_beat", "Starscape Beat:",
               "On stronger admitted beats, briefly brighten three widely separated stars across the sky. Gentle decay; no separate DSP clock.",
               bucket="sky", when=("shockwave_grid_sky_enabled", True), enabled_when=("shockwave_grid_sky_enabled", True)),
        Slider("shockwave_grid_star_glow_strength", "Star Glow Intensity:", 0.0, 2.0,
               "Brightened stars on admitted strong beats.", bucket="sky",
               when=(("shockwave_grid_sky_enabled", True), ("shockwave_grid_starscape_beat", True)),
               enabled_when=(("shockwave_grid_sky_enabled", True), ("shockwave_grid_starscape_beat", True))),
        Slider("shockwave_grid_star_glow_reactivity", "Star Glow Reactivity:", 0.0, 2.0,
               "Brightness response of the three selected beat stars.", bucket="sky",
               when=(("shockwave_grid_sky_enabled", True), ("shockwave_grid_starscape_beat", True)),
               enabled_when=(("shockwave_grid_sky_enabled", True), ("shockwave_grid_starscape_beat", True))),
        Slider("shockwave_grid_star_size", "Star Size:", 0.0, 1.0,
               "How large beat stars burst at their peak: a small diamond at 0, long four-point spikes with "
               "shorter diagonals at 1.", bucket="sky",
               when=(("shockwave_grid_sky_enabled", True), ("shockwave_grid_starscape_beat", True)),
               enabled_when=(("shockwave_grid_sky_enabled", True), ("shockwave_grid_starscape_beat", True))),
        Colour("shockwave_grid_star_glow_color", "Star Glow Colour:", "Choose Beat Star Glow Colour",
               "The colour beat stars light up in. Alpha is how far they move from the Stars colour toward "
               "this one (0 keeps the Stars colour); their brightness stays with Star Glow Intensity.", bucket="sky",
               when=(("shockwave_grid_sky_enabled", True), ("shockwave_grid_starscape_beat", True)),
               enabled_when=(("shockwave_grid_sky_enabled", True), ("shockwave_grid_starscape_beat", True))),
        Toggle("shockwave_grid_sun_enabled", "Celestial Body:", "Show Sun / Moon", bucket="celestial"),
        Choice("shockwave_grid_sun_mode", "Body:", tuple(BASIN_BODY_MODES), bucket="celestial", enabled_when=_BASIN_BODY),
        Colour("shockwave_grid_sun_color", "Sun Colour:", "Choose Neon Sun Colour", bucket="celestial",
               when=("shockwave_grid_sun_mode", "Sun"), enabled_when=_BASIN_BODY),
        Colour("shockwave_grid_moon_color", "Moon Colour:", "Choose Moon Colour", bucket="celestial",
               when=("shockwave_grid_sun_mode", "Moon"), enabled_when=_BASIN_BODY),
        Slider("shockwave_grid_moon_phase", "Moon Phase:", 0.0, 1.0,
               "Manually chosen lunar phase: 0/1 New, 0.125 waxing crescent, 0.25 first quarter, "
               "0.5 Full, 0.75 last quarter, 0.875 waning crescent. Not based on real date, "
               "time or celestial orbit speed.", bucket="celestial",
               when=("shockwave_grid_sun_mode", "Moon"), enabled_when=_BASIN_BODY),
        Slider("shockwave_grid_sun_size", "Size:", 0.1, 1.0,
               "Celestial body size in scene units.", bucket="celestial", enabled_when=_BASIN_BODY),
        Slider("shockwave_grid_sun_x", "Position X:", -2.0, 2.0,
               "Horizontal position in basin half-widths. Easiest placed by dragging the Sun / Moon in the Terrain editor's 3/4 view; this fine-tunes it.", bucket="celestial", signed=True, enabled_when=_BASIN_BODY),
        Slider("shockwave_grid_sun_y", "Position Y:", 0.1, 3.0,
               "Height above the basin in scene units. Easiest placed by dragging the Sun / Moon in the Terrain editor's 3/4 view.", bucket="celestial", enabled_when=_BASIN_BODY),
        Slider("shockwave_grid_sun_z", "Position Z:", -6.0, 2.0,
               "Scene depth: negative positions lie farther into the basin. Easiest placed by dragging the Sun / Moon in the Terrain editor's 3/4 view.", bucket="celestial", signed=True, enabled_when=_BASIN_BODY),
        Toggle("shockwave_grid_sun_orbit_enabled", "Orbit:", "Orbit around basin centre", bucket="celestial", enabled_when=_BASIN_BODY),
        Slider("shockwave_grid_sun_orbit_speed", "Orbit Speed:", 0.0, 0.025, bucket="celestial", scale=1000, decimals=3, suffix=" rev/s",
               enabled_when=(_BASIN_BODY, ("shockwave_grid_sun_orbit_enabled", True))),
        Toggle("shockwave_grid_celestial_glow_enabled", "Celestial Halo:",
               "Show a halo surrounding the Sun or Moon without changing its light or reflections.",
               bucket="celestial", when=_BASIN_BODY),
        Slider("shockwave_grid_celestial_glow_strength", "Halo Intensity:", 0.0, 2.0,
               "Baseline brightness of the Sun/Moon glow.", bucket="celestial",
               when=(_BASIN_BODY, ("shockwave_grid_celestial_glow_enabled", True)), enabled_when=_BASIN_BODY),
        Slider("shockwave_grid_celestial_glow_reactivity", "Halo Reactivity:", 0.0, 2.0,
               "Musical halo pulse from existing midband presence and recent beats; higher values retain beat contrast.", bucket="celestial",
               when=(_BASIN_BODY, ("shockwave_grid_celestial_glow_enabled", True)), enabled_when=_BASIN_BODY),
        Toggle("shockwave_grid_celestial_rim_vertices", "Celestial Rim Vertices:",
               "Experimental sparse glowing marks along the illuminated outer rim of the Sun or Moon.",
               bucket="celestial", when=(_BASIN_BODY, ("shockwave_grid_celestial_glow_enabled", True)),
               enabled_when=_BASIN_BODY),
        Toggle("shockwave_grid_sun_rays_enabled", "Light Rays:", "Show light rays streaming from the Sun or Moon",
               "Visible rays from the Sun or Moon that the mountains, water and clouds block.", bucket="celestial",
               when=_BASIN_BODY, enabled_when=_BASIN_BODY),
        Slider("shockwave_grid_sun_rays_strength", "Ray Strength:", 0.0, 1.0, bucket="celestial",
               when=(_BASIN_BODY, ("shockwave_grid_sun_rays_enabled", True)),
               enabled_when=(_BASIN_BODY, ("shockwave_grid_sun_rays_enabled", True))),
        Colour("shockwave_grid_sun_rays_color", "Ray Colour:", "Choose Light Ray Colour", bucket="celestial",
               when=(_BASIN_BODY, ("shockwave_grid_sun_rays_enabled", True)),
               enabled_when=(_BASIN_BODY, ("shockwave_grid_sun_rays_enabled", True))),
        Slider("shockwave_grid_sun_rays_length", "Ray Length:", 0.0, 1.0,
               "How far the rays stream from the light: short beams at 0, across the whole card at 1.",
               bucket="celestial", when=(_BASIN_BODY, ("shockwave_grid_sun_rays_enabled", True)),
               enabled_when=(_BASIN_BODY, ("shockwave_grid_sun_rays_enabled", True))),
        Slider("shockwave_grid_sun_rays_spread", "Ray Spread:", 0.0, 1.0,
               "How wide a glow round the Sun or Moon the rays stream from: narrow beams at 0, broad at 1.",
               bucket="celestial", when=(_BASIN_BODY, ("shockwave_grid_sun_rays_enabled", True)),
               enabled_when=(_BASIN_BODY, ("shockwave_grid_sun_rays_enabled", True))),
        Slider("shockwave_grid_glow", "Surface Glow:", 0.0, 1.0,
               "Emission from terrain, shoreline, skyline and wave highlights; distinct from body and star halos.", bucket="glow"),
        Slider("shockwave_grid_horizon", "Ridge Light Response:", 0.0, 1.0,
               "How strongly the frequency response lights up terrain ridges.", bucket="glow"),
        Colour("shockwave_grid_water_line_glow_color", "Water Line Glow:", "Choose Water Line Glow Colour",
               "The colour the lines on the water glow in. Alpha is how far their glow moves from the ripple "
               "colours toward this one (0 keeps the ripple colours). Glows only while Surface Glow is above zero.",
               bucket="glow"),
        Slider("shockwave_grid_water_line_glow", "Water Line Glow Strength:", 0.0, 3.0,
               "How brightly the lines on the water glow, on top of Surface Glow; 1 is the shared surface glow.",
               bucket="glow"),
        Custom("shape", "response", build="ui.tabs.media.shockwave_grid_builder:build_response_section",
               load="ui.tabs.media.shockwave_grid_settings_binding:load_response_section",
               collect="ui.tabs.media.shockwave_grid_settings_binding:collect_response_section",
               keys=("shockwave_grid_mirrored", "shockwave_grid_shape_nodes",
                     "shockwave_grid_notch_positions_mirrored", "shockwave_grid_notch_positions_linear",
                     "shockwave_grid_lane_strengths_mirrored", "shockwave_grid_lane_strengths_linear")),
        Slider("shockwave_grid_wave_amplitude", "Reactivity:", 0.0, 1.0,
               "Overall musical drive after the independent frequency lane routing.", bucket="response", source=True),
        Slider("shockwave_grid_profile_floor", "Response Floor:", 0.05, 0.30,
               "Minimum retained body of the audio response profile.", bucket="response", source=True),
        Slider("shockwave_grid_drop_speed", "Falloff:", 0.5, 3.0,
               "How quickly the frequency response falls after the music softens.", bucket="response", source=True),
        Custom("smoothing", "response", "ui.tabs.media.shockwave_grid_builder:build_smoothing_section",
               "ui.tabs.media.shockwave_grid_settings_binding:load_smoothing_section",
               "ui.tabs.media.shockwave_grid_settings_binding:collect_smoothing_section",
               keys=("shockwave_grid_visual_smoothing_enabled", "shockwave_grid_visual_smoothing", "shockwave_grid_solid_bar_hysteresis_enabled")),
        Slider("shockwave_grid_camera_fov", "Camera Field of View:", 20.0, 62.0,
               scale=1, integer=True, suffix="\u00b0", decimals=0, bucket="camera",
               tooltip="Change the vertical viewing angle without moving the camera. Narrow angles frame distant "
                       "land like a long lens; W/A/S/D fly, Q/E turn, Shift+W/S look up or down, R returns home."),
        Toggle("shockwave_grid_auto_rotate", "", "Auto Rotate", bucket="camera",
               tooltip="Let the camera pan slowly back and forth across the landscape by itself after a while "
                       "without camera input."),
        Slider("shockwave_grid_auto_rotate_after", "Auto Rotate After:", 1.0, 120.0, scale=1, integer=True,
               suffix=" s", decimals=0, bucket="camera", when=_NEON_AUTO_ROTATE,
               tooltip="Wait this many seconds after the last camera interaction before Auto Rotate begins."),
        Slider("shockwave_grid_auto_rotate_speed", "Auto Rotate Speed:", 1.0, 30.0, scale=1, integer=True,
               suffix="\u00b0/s", decimals=0, bucket="camera", when=_NEON_AUTO_ROTATE,
               tooltip="Set how fast the camera pans across the middle of its sweep, in degrees per second; it "
                       "slows to a stop at each end before turning back."),
        # The shared framed camera (core.settings.framed_camera), moved live: W/A/S/D flight, Q/E yaw,
        # Shift+W/S pitch, held-left orbit, Alt+right pan, Alt+wheel dolly and R home. Tilt 0 is a level
        # horizon; the eye itself never enters the land or water.
        Slider("shockwave_grid_tilt", "", -0.10, 0.58, bucket=""),
        Slider("shockwave_grid_turn", "", -0.50, 0.50, bucket=""),
        SceneCameraPosition("shockwave_grid_camera_position", "Camera Position:", bucket="camera",
               tooltip="Move the real camera eye over the landscape without changing the lens. It stays above the "
                       "land and water. Drag the diamond to move, Shift+drag for depth, drag the Aim point to turn; "
                       "W/A/S/D fly the same eye in the card and R returns to the preset's view."),
        Slider("shockwave_grid_scene_scale", "", 0.25, 4.0),
        Slider("shockwave_grid_scene_pan_x", "", -2.0, 2.0),
        Slider("shockwave_grid_scene_pan_y", "", -2.0, 2.0),
    ),
)


# ---- Sine Waves --------------------------------------------------------------------------------

_LINE_KEYS = tuple(
    f"sine_{name}"
    for line in range(2, 7)
    for name in (f"line{line}_color", f"line{line}_glow_color", f"travel_line{line}", f"ghost_line{line}_enabled",
                 f"line{line}_shift")
)
_GLOW = ("sine_glow_enabled", True)
_GHOST = ("sine_ghosting_enabled", True)

_SINE_WAVE = ModeSettings(
    "sine_wave",
    buckets=(
        Bucket("appearance", "Appearance", "Line color, glow, and ghosting controls still apply when hidden."),
        Bucket("motion", "Motion", "Speed, travel, crawl, and wave-motion controls still apply when hidden."),
        Bucket("response", "Response", "Energy response and width behavior still apply when hidden."),
        Bucket("multi_line", "Multi-Line",
               "Extra line colors, travel, ghosting, and line offsets still apply when hidden.",
               advanced=True),
        Bucket("layout", "Layout", "Density, spacing, and card-height controls still apply when hidden.",
               advanced=True),
    ),
    entries=(
        Toggle("sine_glow_enabled", "", "Enable Glow", bucket="appearance"),
        Slider("sine_glow_intensity", "Glow Intensity:", 0.0, 1.0, bucket="appearance", percent=True, tick=10,
               when=_GLOW),
        Slider("sine_glow_reactivity", "Glow Reactivity:", 0.0, 2.0, bucket="appearance", percent=True, tick=20,
               when=_GLOW),
        Colour("sine_line_color", "Line Color:", "Choose Sine Wave Line Color", bucket="appearance"),
        Colour("sine_glow_color", "Glow Color:", "Choose Sine Wave Glow Color", bucket="appearance", when=_GLOW),
        Toggle("sine_reactive_glow", "", "Reactive Glow (Energy-Driven)", bucket="appearance", when=_GLOW),
        Toggle("sine_ghosting_enabled", "", "Enable Ghosting",
               "When enabled, a faded afterimage of the previous waveform trails behind the current one.",
               bucket="appearance", logical=True),
        Slider("sine_ghost_alpha", "Ghost Opacity:", 0.0, 1.0, bucket="appearance", logical=True, percent=True,
               tick=5, when=_GHOST),
        Slider("sine_ghost_decay", "Ghost Decay:", 0.1, 1.0, bucket="appearance", logical=True, suffix="x", tick=5,
               when=_GHOST),
        Slider("sine_speed", "Speed:", 0.1, 1.0, "Wave animation speed multiplier.", bucket="motion",
               logical=True, suffix="x", tick=10),
        Choice("sine_wave_travel", "Travel:", ("None", "Scroll Left", "Scroll Right"),
               "Direction the sine wave scrolls.", bucket="motion", logical=True, indexed=True),
        Slider("sine_wave_effect", "Wave Effect:", 0.0, 1.0,
               "Adds a wave-like positional undulation along the sine lines. Higher = more movement.",
               bucket="motion", percent=True, tick=10),
        Slider("sine_micro_wobble", "Micro Wobble:", 0.0, 1.0,
               "Legacy jagged wobble effect (energy-reactive dents). Leave at 0% if using Crawl.",
               bucket="motion", percent=True, tick=10),
        Slider("sine_crawl_amount", "Crawl:", 0.0, 1.0,
               "Gentle horizontal dents that crawl across the lines in response to vocals. Higher = more visible "
               "crawl.", bucket="motion", percent=True, tick=10),
        Slider("sine_sensitivity", "Line Response:", 0.1, 5.0,
               "Renderer-side sine line response multiplier.\n"
               "Lower = calmer amplitude reaction after the shared FFT signal is already computed.\n"
               "Higher = larger visible swings. This is separate from Technical sensitivity.",
               bucket="response", logical=True, suffix="x", tick=50),
        Slider("sine_smoothing", "Smoothing:", 0.0, 1.0,
               "Temporal smoothing for sine-line motion. Higher = steadier, slower response.",
               bucket="response", percent=True, tick=10),
        Slider("sine_width_reaction", "Width Reaction:", 0.0, 1.0,
               "Bass-driven line width stretching. All lines stretch wider in reaction to bass. "
               "0 = off (2px lines), higher = thicker lines on bass hits (up to ~8px). "
               "Lines still resemble a sine wave at maximum.", bucket="response", logical=True, percent=True,
               tick=10),
        Slider("sine_heartbeat", "Heartbeat:", 0.0, 1.0,
               "Bass-transient amplitude swell. Higher = more sensitive triggers, "
               "bigger swells. CPU detects bass transients and the shader briefly "
               "amplifies all sine lines.", bucket="response", logical=True, percent=True, tick=10),
        Slider("sine_displacement", "Displacement:", 0.0, 1.0,
               "Bass-reactive XY displacement of sine waves. "
               "Higher = larger transient shoves when bass hits. "
               "Applies to every enabled line, including single-line mode.", bucket="motion", percent=True, tick=10),
        # Lines 2-6 sit side by side (colour, glow, travel) and appear with the line count.
        Custom("lines", "multi_line", build="ui.tabs.media.sine_wave_builder:build_lines_section",
               load="ui.tabs.media.sine_wave_settings_binding:load_lines_section",
               collect="ui.tabs.media.sine_wave_settings_binding:collect_lines_section",
               keys=("sine_line_count", *_LINE_KEYS)),
        Slider("sine_density", "Density:", 0.25, 3.0,
               "Number of sine cycles across the card. Low = wide gentle waves, "
               "high = tightly packed oscillation. Default 1.0× ≈ 3 cycles.",
               bucket="layout", suffix="×", tick=25),
        Slider("sine_vertical_shift", "Vertical Shift:", -50, 200,
               "Controls vertical spread between lines. 0 = all aligned, 100 = default spread, 200 = max spread, "
               "negative = lines cross. Multi-line only.", bucket="layout", scale=1, decimals=0, integer=True,
               tick=25),
        Slider("sine_line1_shift", "Line 1 Horizontal Shift:", -1.0, 1.0,
               "Phase offset for the primary sine line. Negative values lead, positive values lag.",
               bucket="layout", logical=True, suffix=" cycles", tick=10),
        Slider("sine_line_offset_bias", "Line Offset Bias:", 0.0, 1.0,
               "Vertical spread between lines in multi-line mode.", bucket="layout", percent=True, tick=10),
        Slider("sine_card_adaptation", "Card Adaptation:", 0.05, 1.0,
               "How much of the card height the wave uses. Higher = taller waves.", bucket="layout",
               percent=True, tick=10),
    ),
)


# ---- Oscilloscope ------------------------------------------------------------------------------

def _oscilloscope() -> ModeSettings:
    from rendering.gl_programs.oscilloscope_options import OSC_DISPLAYS, OSC_GRATICULES

    return ModeSettings(
        "oscilloscope",
        attr_prefix="osc",
        buckets=(
            Bucket("display", "Display",
                   "How the audio is drawn: the triggered trace, the trace around a ring, or the signal against "
                   "itself as an X/Y figure."),
            Bucket("beam", "Beam", "The beam's colours, width and glow, and how long its afterglow lasts."),
            Bucket("reaction", "Reaction", "How the beam answers the music beyond the waveform itself."),
            Bucket("screen", "Screen", "The scope's faint scale behind the beam.", advanced=True),
        ),
        entries=(
            Choice("osc_display", "Display:", OSC_DISPLAYS,
                   "Trace: the waveform across the screen, held steady by a trigger. Ring: the same trace around a "
                   "circle. Phase: the signal against itself a moment later, the swirling figures of an X/Y scope.",
                   bucket="display", logical=True),
            Slider("osc_span", "Time Span:", 5.0, 60.0,
                   "How much audio the trace shows: a few cycles of a note at 5 ms, a dense sweep at 60 ms.",
                   bucket="display", logical=True, scale=1, decimals=0, suffix=" ms"),
            Slider("osc_detail", "Detail:", 0.0, 1.0,
                   "How much of the music's fine detail the trace draws: smooth flowing waves at 0, every "
                   "cymbal and breath at 1.", bucket="display", logical=True),
            Slider("osc_gain", "Gain:", 0.25, 4.0,
                   "How tall the waveform is drawn. High gain squeezes loud passages softly at the edges.",
                   bucket="display", logical=True),
            Slider("osc_delay", "Phase Delay:", 0.1, 6.0,
                   "Phase display only: how far apart the two moments it compares are. Short delays draw tight "
                   "loops, long ones wide knots.",
                   bucket="display", logical=True, scale=10, decimals=1, suffix=" ms", when=("osc_display", "Phase")),
            Colour("osc_beam_color", "Beam Colour:", "Choose Beam Colour",
                   "The beam's colour; its centre burns toward white.", bucket="beam", alpha=False),
            Colour("osc_beam_glow_color", "Glow Colour:", "Choose Glow Colour",
                   "The colour of the light around the beam.", bucket="beam", alpha=False),
            Slider("osc_beam_width", "Beam Width:", 0.5, 4.0, "The beam's thickness in pixels at normal size.",
                   bucket="beam", scale=10, decimals=1, suffix=" px"),
            Slider("osc_glow", "Glow:", 0.0, 1.0, "How much light spreads around the beam; zero turns it off.",
                   bucket="beam"),
            Slider("osc_afterglow", "Afterglow:", 0.0, 1.0,
                   "How long earlier traces linger and fade, like a scope's phosphor. Zero shows only the live trace.",
                   bucket="beam", logical=True),
            Slider("osc_analog", "Analog Beam:", 0.0, 1.0,
                   "Dims the beam where it moves fast, as a real scope's beam does, so steep strokes read fainter "
                   "than slow ones.", bucket="beam"),
            Slider("osc_spectral", "Spectral Colour:", 0.0, 1.0,
                   "Tints the beam by how bright the music sounds: warm for bass, cool for treble.",
                   bucket="reaction"),
            Slider("osc_flare", "Hit Flare:", 0.0, 1.0,
                   "How much the beam thickens and flares on each beat; big hits flare most.", bucket="reaction"),
            Slider("osc_pulse", "Loudness Glow:", 0.0, 1.0,
                   "How much louder passages make the beam burn and glow brighter.", bucket="reaction"),
            Choice("osc_graticule", "Graticule:", OSC_GRATICULES,
                   "The scale behind the beam: the classic grid, only the centre axes, or none.", bucket="screen"),
            Colour("osc_graticule_color", "Graticule Colour:", "Choose Graticule Colour",
                   "The scale's colour; its alpha sets how faint it is.", bucket="screen",
                   when=("osc_graticule", ("Grid", "Crosshair"))),
        ),
    )


# ---- Spline Curve ------------------------------------------------------------------------------

# DevCurve solves its full visual snapshot on the logical clock, including styling.

_DEVCURVE = ModeSettings(
    "devcurve",
    buckets=(
        Bucket("shaper", "Shaper", "Layer-first spline editor with per-layer shape and energy arrows."),
        Bucket("core", "Core", "Global curve motion and fill styling."),
        Bucket("foreground_fx", "Foreground FX", "Optional dynamic shadow/specular effects for the current top layer."),
        Bucket("ghost", "Ghost", "Optional trail for debug visibility.", advanced=True),
    ),
    entries=(
        Custom("layers", "shaper", "ui.tabs.media.devcurve_builder:build_devcurve_layers",
               "ui.tabs.media.devcurve_settings_binding:load_devcurve_layers",
               "ui.tabs.media.devcurve_settings_binding:collect_devcurve_layers",
               keys=(
                   'devcurve_active_layer',
                   'devcurve_layer_bass_shape_nodes',
                   'devcurve_layer_bass_enabled',
                   'devcurve_layer_bass_color',
                   'devcurve_layer_bass_alpha',
                   'devcurve_layer_bass_power',
                   'devcurve_layer_bass_offset',
                   'devcurve_layer_bass_outline_color',
                   'devcurve_layer_bass_outline_width',
                   'devcurve_layer_bass_order',
                   'devcurve_layer_vocals_shape_nodes',
                   'devcurve_layer_vocals_enabled',
                   'devcurve_layer_vocals_color',
                   'devcurve_layer_vocals_alpha',
                   'devcurve_layer_vocals_power',
                   'devcurve_layer_vocals_offset',
                   'devcurve_layer_vocals_outline_color',
                   'devcurve_layer_vocals_outline_width',
                   'devcurve_layer_vocals_order',
                   'devcurve_layer_mids_shape_nodes',
                   'devcurve_layer_mids_enabled',
                   'devcurve_layer_mids_color',
                   'devcurve_layer_mids_alpha',
                   'devcurve_layer_mids_power',
                   'devcurve_layer_mids_offset',
                   'devcurve_layer_mids_outline_color',
                   'devcurve_layer_mids_outline_width',
                   'devcurve_layer_mids_order',
                   'devcurve_layer_transients_shape_nodes',
                   'devcurve_layer_transients_enabled',
                   'devcurve_layer_transients_color',
                   'devcurve_layer_transients_alpha',
                   'devcurve_layer_transients_power',
                   'devcurve_layer_transients_offset',
                   'devcurve_layer_transients_outline_color',
                   'devcurve_layer_transients_outline_width',
                   'devcurve_layer_transients_order',
               )),
        Slider('devcurve_base_level', 'Base Level:', 0.1, 0.9,
               'Global baseline height for all Spline Curve layers.', bucket='core', logical=True, percent=True),
        Slider('devcurve_motion_power', 'Motion Power:', 0.0, 3.0,
               'Master reactive deformation gain for all layers.', bucket='core', logical=True, suffix="x"),
        Slider('devcurve_idle_motion', 'Idle Motion:', 0.0, 1.5,
               'Constant low-energy wobble while idle or between beats.', bucket='core', logical=True),
        Slider('devcurve_idle_speed', 'Idle Speed:', 0.05, 2.0,
               'Travel speed of the low-energy idle wobble.', bucket='core', logical=True, suffix="x"),
        Slider('devcurve_smoothness', 'Smoothness:', 0.0, 1.0,
               'Extra curve smoothing. Higher values reduce lumpiness while keeping spline motion reactive.', bucket='core', logical=True, percent=True),
        Toggle('devcurve_foreground_shadow_enabled', '', 'Shadow',
               'Enable a dynamic full-width shadow fill tied to the current foreground layer.', bucket='foreground_fx', logical=True, row_group='foreground'),
        Toggle('devcurve_foreground_specular_enabled', '', 'Specular',
               'Enable a dynamic crest-following specular highlight on the foreground layer.', bucket='foreground_fx', logical=True, row_group='foreground'),
        Slider('devcurve_foreground_shadow_alpha', 'Shadow Alpha:', 0.0, 1.0,
               'Opacity of the dynamic foreground shadow.', bucket='foreground_fx', logical=True, percent=True, when=("devcurve_foreground_shadow_enabled", True)),
        Slider('devcurve_foreground_shadow_darken', 'Shadow Darken:', 0.0, 1.0,
               'How much darker the shadow is than the foreground layer color.', bucket='foreground_fx', logical=True, percent=True, when=("devcurve_foreground_shadow_enabled", True)),
        Slider('devcurve_foreground_shadow_offset', 'Shadow Offset:', 0.0, 0.45,
               'Vertical offset of the foreground shadow below the foreground spline.', bucket='foreground_fx', logical=True, when=("devcurve_foreground_shadow_enabled", True)),
        Slider('devcurve_foreground_specular_alpha', 'Specular Alpha:', 0.0, 1.0,
               'Opacity of the foreground specular highlight.', bucket='foreground_fx', logical=True, percent=True, when=("devcurve_foreground_specular_enabled", True)),
        Slider('devcurve_foreground_specular_width', 'Specular Width:', 0.002, 0.12,
               'Thickness of the specular band around the foreground spline.', bucket='foreground_fx', logical=True, scale=1000, decimals=3, when=("devcurve_foreground_specular_enabled", True)),
        Slider('devcurve_foreground_specular_offset', 'Specular Offset:', -0.2, 0.2,
               'Vertical offset for the specular band relative to the foreground spline.', bucket='foreground_fx', logical=True, signed=True, when=("devcurve_foreground_specular_enabled", True)),
        Slider('devcurve_foreground_specular_crest_bias', 'Specular Crest Bias:', 0.0, 2.0,
               'Bias toward crest zones based on local curvature.', bucket='foreground_fx', logical=True, suffix="x", when=("devcurve_foreground_specular_enabled", True)),
        Toggle('devcurve_ghosting_enabled', ' ', 'Enable Ghosting',
               'Enable a lightweight trail to inspect motion history.', bucket='ghost', logical=True),
        Slider('devcurve_ghost_alpha', 'Ghost Opacity:', 0.0, 1.0,
               'Opacity of the trail overlay.', bucket='ghost', logical=True, percent=True),
        Slider('devcurve_ghost_decay', 'Ghost Decay:', 0.1, 1.0,
               'How quickly the trail fades.', bucket='ghost', logical=True, suffix="x"),
    ),
)


# ---- Extruded Spectrum -------------------------------------------------------------------------

# Source controls project through the descriptor onto the existing Spectrum source/ghost owners.
_EXTRUDED_SPECTRUM = ModeSettings(
    "extruded_spectrum",
    buckets=(
        Bucket("appearance", "Appearance",
               "Rainbow participation and hue drift are authored explicitly here. Fill and border colour/alpha "
               "live in this mode's Bar Appearance bucket rather than behind a colouring preset."),
        Bucket("shape", "Shape", "3D bar geometry plus this mode's mirrored/linear silhouette and lane-energy mapping."),
        Bucket("response", "Response", "Tune global reactivity, shape-floor support, falloff and smoothing after the authored lane mapping."),
        Bucket("effects", "3D Effects", "Material finish, floor reflection, directional shadow, overflow and trailing ghosts.", advanced=True),
    ),
    entries=(
        Choice("extruded_spectrum_colouring", "", EXTRUDED_COLOURINGS),
        Custom("rainbow", "appearance", "ui.tabs.media.extruded_spectrum_builder:build_extruded_rainbow",
               "ui.tabs.media.extruded_spectrum_settings_binding:load_extruded_rainbow",
               "ui.tabs.media.extruded_spectrum_settings_binding:collect_extruded_rainbow"),
        Slider('extruded_spectrum_hue_drift', 'Hue Drift:', 0.0, 1.0,
               'How fast Rainbow hues drift across the bars; zero holds the spectral colours still.', bucket='appearance'),
        Slider('extruded_spectrum_depth', 'Bar Depth:', 0.25, 3.0,
               'How deep each bar is, as a multiple of its width.', bucket='shape'),
        Custom("shape", "shape", "ui.tabs.media.extruded_spectrum_builder:build_extruded_shape",
               "ui.tabs.media.extruded_spectrum_settings_binding:load_extruded_shape",
               "ui.tabs.media.extruded_spectrum_settings_binding:collect_extruded_shape",
               keys=tuple(f"extruded_spectrum_{suffix}" for suffix in (
                   "mirrored", "shape_nodes", "notch_positions_mirrored", "notch_positions_linear",
                   "lane_strengths_mirrored", "lane_strengths_linear"))),
        Slider('extruded_spectrum_wave_amplitude', 'Reactivity:', 0.0, 1.0,
               'Overall motion scaling after the authored lane routing.', bucket='response', source=True),
        Slider('extruded_spectrum_profile_floor', 'Shape Floor:', 0.05, 0.3,
               'Minimum body retained by the authored bar profile.', bucket='response', source=True),
        Slider('extruded_spectrum_drop_speed', 'Falloff:', 0.5, 3.0,
               'How quickly the shared bar field falls after an energy drop.', bucket='response', source=True),
        Custom("smoothing", "response", "ui.tabs.media.extruded_spectrum_builder:build_extruded_smoothing",
               "ui.tabs.media.extruded_spectrum_settings_binding:load_extruded_smoothing",
               "ui.tabs.media.extruded_spectrum_settings_binding:collect_extruded_smoothing",
               keys=("extruded_spectrum_visual_smoothing_enabled", "extruded_spectrum_visual_smoothing",
                     "extruded_spectrum_solid_bar_hysteresis_enabled")),
        Slider('extruded_spectrum_gloss', 'Gloss:', 0.0, 1.0,
               "Shine on the bars' faces.", bucket='effects'),
        Slider('extruded_spectrum_face_mirror', 'Mirror Faces:', 0.0, 1.0,
               "Gives the bars' faces (not their edges) a polished, mirror surface reflecting the wallpaper, sharper with Gloss; zero leaves them plain.", bucket='effects'),
        Toggle('extruded_spectrum_smooth_edges', 'Smooth Edges:', "Anti-alias the bars' edge lines at an angle",
               'On: edge lines keep an even, smoothed width however the bars are turned or tilted. Off: lines are sized as if seen head-on, which thins and roughens them on faces seen at an angle.', bucket="effects"),
        Slider('extruded_spectrum_reflection', 'Reflection:', 0.0, 1.0,
               'How strongly the bars reflect in the floor beneath them; zero shows no floor.', bucket='effects'),
        Toggle('extruded_spectrum_shadow_enabled', 'Cast Shadow:', 'Project a shared Scene3D shadow',
               "Draw the optional Scene3D ground shadow using the display's existing shadow direction.", bucket="effects", availability=("core.settings.visualizer_mode_registry:EXTRUDED_CAST_SHADOW_AVAILABLE", "Temporarily unavailable: Extruded cast shadows are disabled pending a redesign.")),
        Choice("extruded_spectrum_shadow_reach", "Shadow Reach:", ("Nearby", "Distant"),
               "Nearby hugs the base line; Distant casts a longer silhouette. Both inherit the global Widgets shadow direction.",
               bucket="effects", compact=False, availability=("core.settings.visualizer_mode_registry:EXTRUDED_CAST_SHADOW_AVAILABLE", "Temporarily unavailable: Extruded cast shadows are disabled pending a redesign.")),
        Slider('extruded_spectrum_shadow_strength', 'Shadow Strength:', 0.0, 1.0,
               'Opacity of the cast shadow (requires Cast Shadow enabled).', bucket='effects', availability=("core.settings.visualizer_mode_registry:EXTRUDED_CAST_SHADOW_AVAILABLE", "Temporarily unavailable: Extruded cast shadows are disabled pending a redesign.")),
        Toggle('extruded_spectrum_allow_overflow', 'Allow Overflow:', "Let the 3D leave the visualizer's rectangle",
               "On: the bars keep Spectrum's size and tilted tops, the turn and the reflection may reach past the rectangle. Off: the whole 3D scene is fitted inside it.", bucket="effects"),
        Toggle('extruded_spectrum_ghosting_enabled', 'Enable Ghosting:', 'Draw trailing bar ghosts',
               '', bucket="effects", source=True),
        Toggle('extruded_spectrum_rainbow_ghost', 'Rainbow Ghost:', 'Colour trailing ghosts with rainbow hues',
               'Colour only the existing 3D ghost columns; faces and edges retain their independently authored Rainbow/Bar Colours presentation.', bucket="effects"),
        Slider('extruded_spectrum_ghost_alpha', 'Ghost Opacity:', 0.0, 1.0,
               'Opacity of the bar-history ghosts.', bucket='effects', source=True, when=('extruded_spectrum_ghosting_enabled', True)),
        Slider('extruded_spectrum_ghost_decay', 'Ghost Decay:', 0.1, 1.0,
               'How quickly ghosts descend after a bar falls.', bucket='effects', source=True, when=('extruded_spectrum_ghosting_enabled', True)),
        Slider("extruded_spectrum_turn", "", -1.0, 1.0),
        Slider("extruded_spectrum_tilt", "", 0.0, 1.0),
    ),
)


# ---- Spectrum ----------------------------------------------------------------------------------

_SPECTRUM = ModeSettings(
    "spectrum",
    auto_switch=False,
    buckets=(
        Bucket("appearance", "Appearance", "Spectrum colors and rim-glow styling still apply when hidden."),
        Bucket("shape", "Shape", "Spectrum layout and authored silhouette still apply when hidden."),
        Bucket("render", "Render", "Render-style controls still apply when hidden.", advanced=True),
        Bucket("audio", "Audio", "Creative motion controls live here. Technical noise-floor and signal tuning live in Technical.", advanced=True),
        Bucket("ghost", "Ghost", "Ghost controls still apply when hidden.", advanced=True),
    ),
    entries=(
        Toggle('spectrum_glow_enabled', " ", 'Enable Rim Glow',
               'Add a thin emissive rim around Spectrum bars without adding bloom smear.', bucket='appearance'),
        Colour("spectrum_glow_color", "Glow Color:", "Choose Spectrum Rim Glow Color",
               bucket="appearance", when=("spectrum_glow_enabled", True), swatch_row=False),
        Slider('spectrum_glow_intensity', 'Glow Intensity:', 0.0, 1.5,
               'How bright the thin Spectrum rim glow appears. Higher = stronger emissive edge.', bucket='appearance', truncate=True, percent=True, tick=10, when=('spectrum_glow_enabled', True)),
        Custom("shape", "shape", "ui.tabs.media.spectrum_builder:build_spectrum_shape",
               "ui.tabs.media.spectrum_settings_binding:load_spectrum_shape",
               "ui.tabs.media.spectrum_settings_binding:collect_spectrum_shape",
               keys=("spectrum_mirrored", "spectrum_shape_nodes", "spectrum_notch_positions_mirrored",
                     "spectrum_notch_positions_linear", "spectrum_lane_strengths_mirrored", "spectrum_lane_strengths_linear")),
        Choice("spectrum_render_mode", "", ("segment", "bars"), logical=True,
               runtime_attr="_spectrum_single_piece", runtime_values=(False, True),
               read="core.settings.visualizer_settings_contract:resolve_spectrum_render_mode",
               input_aliases=("spectrum_single_piece",)),
        Custom("render_mode", "render", "ui.tabs.media.spectrum_builder:build_spectrum_render_mode",
               "ui.tabs.media.spectrum_settings_binding:load_spectrum_render_mode",
               "ui.tabs.media.spectrum_settings_binding:collect_spectrum_render_mode"),
        Custom("smoothing", "render", "ui.tabs.media.spectrum_builder:build_spectrum_smoothing",
               "ui.tabs.media.spectrum_settings_binding:load_spectrum_smoothing",
               "ui.tabs.media.spectrum_settings_binding:collect_spectrum_smoothing",
               keys=("spectrum_visual_smoothing_enabled", "spectrum_visual_smoothing")),
        Toggle('spectrum_unique_colors', " ", 'Unique Colours Per Bar',
               "When 'Taste the Rainbow' is enabled: each bar gets its own unique colour spread across the rainbow. Off = all bars share one shifting colour.", bucket='render', runtime_attr='_rainbow_per_bar', read='core.settings.visualizer_settings_contract:resolve_spectrum_unique_colors', input_aliases=('spectrum_rainbow_per_bar', 'rainbow_per_bar')),
        Toggle('spectrum_rainbow_fill', " ", 'Rainbow Fill',
               'When rainbow/unique colours are active: bar fill participates in the colour shift. Off = keep the configured fill colour while rainbow ghost and optional rainbow borders remain independent.', bucket='render'),
        Toggle('spectrum_rainbow_border', " ", 'Rainbow Borders',
               'When rainbow/unique colours are active: bar borders also participate in the colour shift. Off = borders keep their configured border colour.', bucket='render'),
        Slider('spectrum_border_radius', 'Border Radius:', 0.0, 12.0,
               'Round bar corners (0 = square, 6 = nicely rounded).', bucket='render', truncate=True, scale=1, decimals=0, suffix='px', admission_high=20.0),
        Custom("audio_hint", "audio", "ui.tabs.media.spectrum_builder:build_spectrum_audio_hint"),
        Slider('spectrum_wave_amplitude', 'Reactivity:', 0.0, 1.0,
               'Overall Spectrum motion scaling after lane routing.\nLower = calmer, more reserved movement.\nHigher = punchier motion and stronger lane response.\nThis is creative reactivity, not the Technical sensitivity/noise-floor path.', bucket='audio', truncate=True, source=True, percent=True, tick=25),
        Slider('spectrum_profile_floor', 'Shape Floor:', 0.05, 0.3,
               'Minimum visual shape floor for the authored Spectrum silhouette.\nLower = bars can collapse more deeply into the drawn profile.\nHigher = bars keep more body even when a lane is quiet.\nThis is separate from the Technical noise-floor controls.', bucket='audio', truncate=True, source=True, tick=5),
        Slider('spectrum_drop_speed', 'Drop Speed:', 0.5, 3.0,
               'How fast Spectrum bars fall after a peak.\nLower = stickier sustain and softer release.\nHigher = sharper, snappier drops.\n1.0x is the current neutral baseline.', bucket='audio', truncate=True, source=True, decimals=1, suffix='x', tick=25),
        Toggle('spectrum_ghosting_enabled', " ", 'Enable Ghosting',
               'When enabled, the visualizer draws trailing ghost bars above the current height.', bucket='ghost', logical=True),
        Toggle('spectrum_rainbow_ghost', " ", 'Rainbow Ghost',
               'Colour only the existing falling peak trails with a per-bar rainbow, independently of Rainbow Fill and Rainbow Borders.', bucket='ghost'),
        Slider('spectrum_ghost_alpha', 'Ghost Opacity:', 0.0, 1.0,
               '', bucket='ghost', truncate=True, percent=True, tick=5, when=('spectrum_ghosting_enabled', True)),
        Slider('spectrum_ghost_decay', 'Ghost Decay Speed:', 0.1, 1.0,
               '', bucket='ghost', truncate=True, logical=True, suffix='x', tick=5, when=('spectrum_ghosting_enabled', True), bottom_padding=12),
    ),
)


# ---- Voxel Sphere ------------------------------------------------------------------------------

# Styling and response belong to Sphere's configure-owned frozen logical bundle. Finish is authoring only.
_SPHERE = ModeSettings(
    "sphere",
    buckets=(
        Bucket("analysis", "Frequency Zones", "Sphere's own bass, mid and treble boundaries for spatial response and source events."),
        Bucket("appearance", "Appearance", "Literal voxel colours, finish and fixed-light presentation. These are Sphere-local presentation controls and do not author audio response."),
        Bucket("particle_flow", "Particle Flow", "Detached voxel intake/outtake options. Sub-options keep their authored values when the master Particle Flow switch is off."),
        Bucket("reaction", "Reactivity", "Music-driven geometry response. These controls affect Sphere only; they do not retune shared visualizer analysis.", advanced=True),
        Bucket("rotation", "Rotation", "Base Rotation is the continuous floor; Velocity Reaction adds music-driven speed without changing phase or direction.", advanced=True),
        Bucket("effects", "Effects", "Optional Sphere-only render effects. None may become a shared visualizer setting family; Sphere keeps these controls mode-owned.", advanced=True),
    ),
    entries=(
        Custom("analysis", "analysis", "ui.tabs.media.sphere_builder:build_sphere_analysis",
               "ui.tabs.media.sphere_settings_binding:load_sphere_analysis",
               "ui.tabs.media.sphere_settings_binding:collect_sphere_analysis",
               keys=("sphere_analysis_notch_positions",)),
        Choice("sphere_finish", "", SPHERE_FINISH_VALUES, authoring=True, ingress_strict=True,
               normalizer="core.settings.visualizer_settings_contract:normalize_sphere_finish"),
        Custom("finish", "appearance", "ui.tabs.media.sphere_builder:build_sphere_finish",
               "ui.tabs.media.sphere_settings_binding:load_sphere_finish",
               "ui.tabs.media.sphere_settings_binding:collect_sphere_finish"),
        Colour("sphere_fill_color", 'Fill Color:', 'Choose Sphere Fill Color',
               'Literal voxel base RGBA. No finish preset or per-cube pseudo-material multiplier changes this colour.', logical=True, runtime_strict=True, swatch_row=False),
        Custom("fill_colour", "appearance", "ui.tabs.media.sphere_builder:build_sphere_fill_colour",
               "ui.tabs.media.sphere_settings_binding:load_sphere_fill_colour",
               "ui.tabs.media.sphere_settings_binding:collect_sphere_fill_colour"),
        Colour("sphere_edge_color", 'Edge Color:', 'Choose Sphere Edge Color',
               'Independent cube bevel/ink RGBA. Its alpha is authored separately from Fill Color alpha.', logical=True, runtime_strict=True, swatch_row=False),
        Custom("edge_colour", "appearance", "ui.tabs.media.sphere_builder:build_sphere_edge_colour",
               "ui.tabs.media.sphere_settings_binding:load_sphere_edge_colour",
               "ui.tabs.media.sphere_settings_binding:collect_sphere_edge_colour"),
        Slider('sphere_edge_weight', 'Edge Weight:', 0.25, 1.75,
               'Controls how much of each existing cube face is treated as the authored Edge Color. 1.0 is the accepted current edge width; lower values thin it and higher values thicken it without adding geometry or another draw.', bucket='appearance', logical=True, runtime_strict=True, suffix='x', recommended=1.0),
        Slider('sphere_voxel_size_variation', 'Voxel Size Variation:', 0.0, 1.0,
               'Exposes the existing deterministic per-voxel size variation. 0.35 is the accepted current appearance; zero makes every cube uniform and higher values increase the existing variation without changing voxel count or audio response.', bucket='appearance', logical=True, runtime_strict=True, recommended=0.35),
        Toggle('sphere_taste_the_rainbow_enabled', 'Taste The Rainbow:', 'Enable Sphere-local voxel rainbow',
               "Sphere-only presentation effect. It uses the voxel renderer's own colour field and does not opt Sphere into the shared Rainbow settings family.", bucket='appearance', logical=True, runtime_bool=True),
        Toggle('sphere_taste_the_rainbow_surfaces', 'Rainbow Surfaces:', 'Apply rainbow to voxel surfaces',
               'Replaces Fill RGB with one coherent moving partial-spectrum gradient across blocks while preserving the authored Fill alpha.', bucket='appearance', logical=True, runtime_bool=True, enabled_when=('sphere_taste_the_rainbow_enabled', True)),
        Toggle('sphere_taste_the_rainbow_edges', 'Rainbow Edges:', 'Apply rainbow to voxel edges',
               'Replaces Edge RGB with the same coherent moving partial-spectrum gradient while preserving the independently authored Edge alpha.', bucket='appearance', logical=True, runtime_bool=True, enabled_when=('sphere_taste_the_rainbow_enabled', True)),
        Slider('sphere_taste_the_rainbow_speed', 'Rainbow Speed:', 0.0, 1.0,
               'How fast the voxel colour field travels. Zero holds its colours still.', bucket='appearance', logical=True, runtime_strict=True, scale=1000, decimals=3, suffix=' cycles/s', enabled_when=('sphere_taste_the_rainbow_enabled', True)),
        Slider('sphere_taste_the_rainbow_extent', 'Rainbow Extent:', 0.0, 1.0,
               'How much of the colour wheel spans the voxel field; zero gives one uniform hue.', bucket='appearance', logical=True, runtime_strict=True, enabled_when=('sphere_taste_the_rainbow_enabled', True)),
        Choice("sphere_light_direction", "Light Direction:", ("N", "NE", "E", "SE", "S", "SW", "W", "NW"),
               bucket="appearance", logical=True, compact=False, uppercase=True, runtime_strict=True, ingress_strict=True, direction_mapper=True),
        Slider('sphere_perspective_strength', 'Perspective Strength:', 0.0, 1.0,
               'Controls only the existing voxel camera perspective. 1.0 is the accepted current projection; lower values flatten toward orthographic. The range cannot exceed the current golden perspective.', bucket='appearance', logical=True, runtime_strict=True, suffix='x', recommended=1.0),
        Slider('sphere_gloss', 'Gloss:', 0.0, 1.0,
               'Controls per-face highlight width/smoothness. It does not select or brighten a special cube.', bucket='appearance', logical=True, runtime_strict=True, recommended=0.75),
        Slider('sphere_specular', 'Specular:', 0.0, 2.0,
               'Controls per-face reflected sheen strength. Zero is matte; high values increase face shine without a shell-space glow lobe.', bucket='appearance', logical=True, runtime_strict=True, recommended=1.08),
        Slider('sphere_mirror', 'Mirror Cubes:', 0.0, 1.0,
               "Gives the cubes' faces (not their edges) a polished mirror surface reflecting the wallpaper, sharper with Gloss; zero leaves them plain. Needs a 3D Detail tier with reflections.", bucket='appearance', logical=False, runtime_strict=True),
        Custom("finish_hooks", "appearance", "ui.tabs.media.sphere_builder:bind_sphere_finish_axes"),
        Toggle('sphere_fade_incoming_blocks', 'Particle Flow:', 'Enable detached voxel intake/outtake',
               'Master detached-voxel presentation. In Intake mode selected shell voxels begin outside and return to their canonical slots; Particle Outtake reverses newly launched cohorts so source voxels leave/fade while replacements fade into the canonical shell.', bucket='particle_flow', logical=True, runtime_bool=True),
        Toggle('sphere_incoming_density_response_enabled', 'Particle Density Response:', 'Scale detached voxel count with live energy',
               'Keeps all four stable ingress quadrants participating, but quiet passages launch a smaller subset and strong passages approach the full 46/46/46/70 population. Playing-state silence still admits no new detached voxels even when this option is off.', bucket='particle_flow', logical=True, runtime_bool=True, enabled_when=('sphere_fade_incoming_blocks', True)),
        Toggle('sphere_incoming_transient_velocity_enabled', 'Particle Velocity:', 'Use transient-responsive detached-voxel travel speed',
               'Uses real cohort travel progress. Speed is captured from Sphere-local acoustic contrast at launch; in-flight cohorts do not globally chase later audio.', bucket='particle_flow', logical=True, runtime_bool=True, enabled_when=('sphere_fade_incoming_blocks', True)),
        Toggle('sphere_particle_outtake_enabled', 'Particle Outtake:', 'Reverse detached voxel flow outward',
               'New qualified cohorts shed stable shell voxels outward and fade them gently while replacement voxels fade into the canonical shell positions. Direction is captured at launch, so toggling this never reverses a cohort already in flight.', bucket='particle_flow', logical=True, runtime_bool=True, enabled_when=('sphere_fade_incoming_blocks', True)),
        Slider('sphere_particle_amount', 'Particle Amount:', 0.25, 1.75,
               'Scales the number of voxels selected after a qualified cohort has already been admitted. It never changes onset thresholds, event qualification, acoustic impact or particle velocity.', bucket='particle_flow', logical=True, runtime_strict=True, suffix='x', recommended=1.0, enabled_when=('sphere_fade_incoming_blocks', True)),
        Slider('sphere_particle_energy_floor', 'Particle Energy Floor:', 0.0, 1.0,
               "How loud the passage must be, within the track's own range, for a qualified event to launch particles: 0 its quietest passages, 1 its loudest. Raise it to keep particles for the louder moments. Real silence never launches particles.", bucket='particle_flow', logical=True, runtime_strict=True, scale=1000, decimals=3, enabled_when=('sphere_fade_incoming_blocks', True)),
        Toggle('sphere_fragment_interpolation_enabled', 'Fragment Interpolation:', 'Smooth fragment travel (visual only)',
               'Keeps audio/onset admission instantaneous but interpolates detached cube displacement over a few rendered frames. It does not smooth the audio signal, reduce packet strength, blur frames, or add motion blur.', bucket='reaction', logical=True, runtime_bool=True),
        Slider('sphere_fragment_energy_floor', 'Fragment Energy Floor:', 0.0, 1.0,
               "How loud the passage must be, within the track's own range, for a qualified event to fragment the sphere: 0 its quietest passages, 1 its loudest. Raise it to keep fragmentation for the louder moments. Does not change particles or the tracer.", bucket='reaction', logical=True, runtime_strict=True, scale=1000, decimals=3),
        Slider('sphere_fragment_strength', 'Fragment Strength:', 0.0, 9.0,
               'Single authority for earned local sectional displacement. Existing settings migrate exactly from the former Deformation × Block Reactivity product.', bucket='reaction', logical=True, runtime_strict=True, recommended=3.6),
        Slider('sphere_particle_distance', 'Particle Distance:', 0.0, 4.5,
               'Controls detached intake/outtake travel distance only. It no longer changes local fragment strength.', bucket='reaction', logical=True, runtime_strict=True, recommended=2.25),
        Slider('sphere_size_response', 'Size Response:', 0.0, 2.54,
               'Controls staged slow sustained passage-weight growth without beat-pulsing or flicker. The range stops where the existing growth equation saturates.', bucket='reaction', logical=True, runtime_strict=True, recommended=2.25),
        Slider('sphere_vocal_response', 'Vocal Response:', 0.0, 1.35,
               'Controls the dominant vocal/mid-high sectional event voice. The range ends at the existing effective maximum rather than exposing a dead tail.', bucket='reaction', logical=True, runtime_strict=True, recommended=1.35),
        Choice("sphere_spin_direction", "Spin Direction:", ("Default", "Reverse", "Y Clockwise", "Y Counterclockwise"),
               "Choose the shell rotation axis/direction. Default keeps the original compound rotation; the velocity floor remains continuous.",
               bucket="rotation", logical=True, compact=False, runtime_strict=True),
        Slider('sphere_base_rotation_speed', 'Base Rotation:', 0.0, 0.5,
               'Continuous authored rotation floor/idle velocity.', bucket='rotation', logical=True, runtime_strict=True, suffix='x', recommended=0.02),
        Slider('sphere_rotation_speed', 'Velocity Reaction:', 0.0, 2.0,
               'Additional rotation velocity driven by current articulation; phase/direction remain continuous.', bucket='rotation', logical=True, runtime_strict=True, suffix='x', recommended=0.99),
        Toggle('sphere_shadow_enabled', 'Drop Shadow:', 'Enable projected voxel drop shadow',
               'Draws a Sphere-local flat-colour projection of the same rotating/deforming voxel instances. It follows detached particles without shadow maps, mutual lighting, an FBO blur, or another cadence.', bucket='effects', logical=True, runtime_bool=True),
        Slider('sphere_shadow_opacity', 'Shadow Opacity:', 0.0, 2.0,
               'Scales the inherited shadow-colour alpha. 1.00x preserves the previous Sphere shadow intensity curve; lower values soften it and values above 1.00x deliberately strengthen it.', bucket='effects', logical=True, runtime_strict=True, suffix='x', recommended=1.0, enabled_when=('sphere_shadow_enabled', True)),
        Slider('sphere_shadow_softness', 'Shadow Softness:', 0.0, 0.45,
               'Controls one cheap expanded feather layer around the projected voxel silhouette. 0 disables that extra layer; 0.18 is the suggested starting point without an offscreen blur pass.', bucket='effects', logical=True, runtime_strict=True, recommended=0.18, enabled_when=('sphere_shadow_enabled', True)),
        Slider('sphere_shadow_distance', 'Shadow Distance:', 0.0, 2.5,
               'Scales the existing light-opposite Sphere shadow offset. 1.00x preserves the previous distance response, including its small whole-body pulse accent.', bucket='effects', logical=True, runtime_strict=True, suffix='x', recommended=1.0, enabled_when=('sphere_shadow_enabled', True)),
        Slider('sphere_shadow_size', 'Shadow Size:', 0.6, 1.6,
               'Scales the projected silhouette around the Sphere centre. 1.00x follows the actual voxel projection; detached particle positions remain represented rather than collapsing back to a circular proxy.', bucket='effects', logical=True, runtime_strict=True, suffix='x', recommended=1.0, enabled_when=('sphere_shadow_enabled', True)),
        Toggle('sphere_depth_shading_enabled', 'Depth Shading:', 'Darken rear voxels to reinforce sphere depth',
               'Cheap Sphere-only luminance cue derived from the existing transformed voxel depth. It does not cast shadows, sample neighbouring voxels, desaturate colours, or add a render pass.', bucket='effects', logical=True, runtime_bool=True),
        Slider('sphere_depth_shading_strength', 'Depth Strength:', 0.0, 0.5,
               'Maximum rear-hemisphere darkening. 0.20 is the suggested restrained value; the front remains unchanged and authored/Rainbow colour hue and alpha are preserved.', bucket='effects', logical=True, runtime_strict=True, recommended=0.2, enabled_when=('sphere_depth_shading_enabled', True)),
        Toggle('sphere_cel_shading', 'Toon Shading:', 'Enable hard toon bands + inked cube edges',
               'Uses deliberately hard light bands and strong edge ink. It changes presentation only, never voxel motion or audio reactivity.', bucket='effects', logical=True, runtime_bool=True),
        Toggle('sphere_light_tracer_enabled', 'Light Tracer:', 'Enable music-driven light snake',
               'The sole moving bright-block effect. Each accepted audio onset queues one bounded step; travel is speed-capped and settles before fading. Gloss/Specular are per-face finish controls and cannot create a competing bright block.', bucket='effects', logical=True, runtime_bool=True),
        Colour("sphere_tracer_color", "Tracer Color:", "Choose Sphere Tracer Color",
               'Styles the existing causal tracer only. The default warm cream exactly matches the accepted hard-coded tracer colour; alpha may soften its blend without changing tracer timing or admission.', logical=True, runtime_strict=True, swatch_row=False),
        Custom("tracer_colour", "effects", "ui.tabs.media.sphere_builder:build_sphere_tracer_colour",
               "ui.tabs.media.sphere_settings_binding:load_sphere_tracer_colour",
               "ui.tabs.media.sphere_settings_binding:collect_sphere_tracer_colour"),
        Toggle('sphere_allow_overflow', 'Scene Overflow:', 'Allow blocks outside the visualizer bounds',
               'Sphere-only render capability. Other visualizer modes remain on the existing clipped path.', bucket='effects', logical=True, runtime_bool=True),
        Slider("sphere_turn", "", -1.0, 1.0, runtime_strict=True),
        Slider("sphere_tilt", "", 0.0, 1.0, runtime_strict=True),
    ),
)



def _bubble_choice(value: object) -> str:
    return str(value).strip().lower()


def _bubble_stream_direction(value: object) -> str:
    value = _bubble_choice(value)
    return "top_right" if value == "diagonal" else value


_BUBBLE = ModeSettings(
    "bubble",
    buckets=(
        Bucket("appearance", "Appearance", "Bubble shading, gradient direction, and color styling still apply when hidden."),
        Bucket("motion", "Motion", "Streaming, drift, swirl, and motion-tail controls still apply when hidden."),
        Bucket("bounce", "Bounce", "Adjust collision rebound probability and speed by bubble class."),
        Bucket("reactivity", "Reactivity", "Audio-driven pulse behavior still applies when hidden.", advanced=True),
        Bucket("population", "Population", "Bubble counts, size limits, and lifecycle controls still apply when hidden.", advanced=True),
        Bucket("layout", "Layout", "Card sizing still applies when hidden.", advanced=True),
        Bucket("ghost", "Ghost", "Bubble ghosting still applies when hidden.", advanced=True),
    ),
    entries=(
        Choice("bubble_specular_direction", "Specular Direction:",
               ("top", "bottom", "left", "right", "top_left", "top_right", "bottom_left", "bottom_right"),
               bucket="appearance", size_variant="mini",
               labels=("Top", "Bottom", "Left", "Right", "Top Left", "Top Right", "Bottom Left", "Bottom Right"),
               normalizer="core.settings.bubble_gradient_semantics:normalize_bubble_specular_direction", direction_mapper=True),
        Choice("bubble_gradient_direction", "Gradient Direction:",
               ("top", "bottom", "left", "right", "top_left", "top_right", "bottom_left", "bottom_right",
                "center_out", "center_out_reverse"), bucket="appearance", size_variant="mini",
               labels=("Top", "Bottom", "Left", "Right", "Top Left", "Top Right", "Bottom Left", "Bottom Right",
                       "Center Out", "Center Out Reverse"),
               normalizer="core.settings.bubble_gradient_semantics:normalize_bubble_gradient_direction", direction_mapper=True),
        Colour("bubble_outline_color", "Outline Colour:", "Choose Bubble Outline Color", bucket="appearance"),
        Colour("bubble_specular_color", "Specular Colour:", "Choose Bubble Specular Color", bucket="appearance"),
        Colour("bubble_gradient_light", "Gradient Light:", "Choose Bubble Gradient Light", bucket="appearance"),
        Colour("bubble_gradient_dark", "Gradient Dark:", "Choose Bubble Gradient Dark", bucket="appearance"),
        Colour("bubble_pop_color", "Pop Colour:", "Choose Bubble Pop Color", bucket="appearance"),
        Choice("bubble_stream_direction", "Stream Direction:",
               ("none", "up", "down", "left", "right", "top_left", "top_right", "bottom_left", "bottom_right", "random"),
               bucket="motion", logical=True,
               labels=("None", "Up", "Down", "Left", "Right", "Top Left", "Top Right", "Bottom Left", "Bottom Right", "Random"),
               normalizer="core.settings.visualizer_mode_settings:_bubble_stream_direction", direction_mapper=True),
        Slider("bubble_stream_constant_speed", "Stream Constant Speed:", 0.0, 2.0, bucket="motion",
               logical=True, percent=True, tick=25, truncate=True),
        Slider("bubble_stream_speed_cap", "Stream Speed Cap:", 0.5, 4.0, bucket="motion",
               logical=True, percent=True, tick=25, truncate=True, admission_low=0.1),
        Slider("bubble_stream_reactivity", "Stream Reactivity:", 0.0, 2.0, bucket="motion",
               logical=True, percent=True, tick=50, truncate=True, runtime_high=1.25),
        Slider("bubble_rotation_amount", "Rotation Amount:", 0.0, 1.0, bucket="motion",
               logical=True, percent=True, truncate=True),
        Slider("bubble_drift_amount", "Drift Amount:", 0.0, 1.0, bucket="motion",
               logical=True, percent=True, truncate=True),
        Toggle("bubble_group_drift", "Group Drift:", "Enable", bucket="motion", logical=True,
               tooltip="Uses one shared drift carrier for non-swirl Bubble drift modes, while still "
                       "keeping per-bubble force variation so the field moves together without becoming robotic."),
        Slider("bubble_drift_speed", "Drift Speed:", 0.0, 1.0, bucket="motion",
               logical=True, percent=True, truncate=True),
        Slider("bubble_drift_frequency", "Drift Frequency:", 0.0, 1.0, bucket="motion",
               logical=True, percent=True, truncate=True),
        Choice("bubble_drift_direction", "",
               ("none", "left", "right", "diagonal", "swish_horizontal", "swish_vertical", "random", "swirl_cw", "swirl_ccw"),
               logical=True,
               labels=("None", "Left", "Right", "Diagonal", "Swish (Horizontal)", "Swish (Vertical)", "Random",
                       "Clockwise", "Counter-Clockwise"),
               normalizer="core.settings.visualizer_mode_settings:_bubble_choice"),
        Custom("swirl", "motion", "ui.tabs.media.bubble_builder:build_bubble_swirl",
               "ui.tabs.media.bubble_builder:load_bubble_swirl", "ui.tabs.media.bubble_builder:collect_bubble_swirl"),
        Slider("bubble_trail_strength", "Tail Length:", 0.0, 1.5, bucket="motion",
               logical=True, percent=True, tick=10, truncate=True,
               tooltip="How long the motion tail stretches behind each bubble (0 = off)."),
        Slider("bubble_tail_opacity", "Tail Opacity:", 0.0, 0.85, bucket="motion",
               percent=True, tick=5, truncate=True,
               tooltip="Maximum opacity of the tail gradient (0 = off). Always somewhat translucent."),
        Slider("bubble_bounce_big_pct", "Big Bounce Chance:", 0, 100, bucket="bounce",
               logical=True, scale=1, integer=True, decimals=0, suffix="%", tick=10, truncate=True),
        Slider("bubble_bounce_small_pct", "Small Bounce Chance:", 0, 100, bucket="bounce",
               logical=True, scale=1, integer=True, decimals=0, suffix="%", tick=10, truncate=True),
        Slider("bubble_bounce_big_speed", "Big Bounce Speed:", 0.0, 2.0, bucket="bounce",
               logical=True, suffix="x", tick=10, truncate=True),
        Slider("bubble_bounce_small_speed", "Small Bounce Speed:", 0.0, 2.0, bucket="bounce",
               logical=True, suffix="x", tick=10, truncate=True),
        Toggle("bubble_bounce_same_only", "Collision Filter:", "Same Bubbles Bounce Only",
               bucket="bounce", logical=True),
        Choice("bubble_collision_pop_mode", "Pop on Collision:", ("off", "one", "all"),
               bucket="bounce", logical=True, size_variant="mini", labels=("Off", "One Bubble", "All Bubbles"),
               normalizer="core.settings.visualizer_mode_settings:_bubble_choice"),
        Slider("bubble_big_bass_pulse", "Big Bubble Bass Pulse:", 0.0, 2.0, bucket="reactivity",
               logical=True, percent=True, tick=50, truncate=True, runtime_high=1.0),
        Slider("bubble_small_freq_pulse", "Small Bubble Freq Pulse:", 0.0, 2.0, bucket="reactivity",
               logical=True, percent=True, tick=50, truncate=True, runtime_high=1.0),
        Slider("bubble_big_visual_smoothing", "Hero Visual Smoothing:", 0.0, 1.0, bucket="reactivity",
               logical=True, percent=True, tick=10, truncate=True,
               tooltip="Display-only smoothing for big/hero bubble size. Lower = rawer motion, higher = softer visual settling. "
                       "Does not smooth the audio signal or Bubble loud-path authority."),
        Slider("bubble_big_size_max", "Big Bubble Size:", 0.010, 0.060, bucket="population",
               logical=True, scale=1000, decimals=0, tick=10, truncate=True, display_multiplier=1000,
               tooltip="Base starting radius for big bubbles. Actual size varies ±40% around this value."),
        Slider("bubble_small_size_max", "Small Bubble Size:", 0.004, 0.030, bucket="population",
               logical=True, scale=1000, decimals=0, tick=5, truncate=True, display_multiplier=1000,
               tooltip="Base starting radius for small bubbles. Actual size varies ±45% around this value."),
        Slider("bubble_big_specular_max_size", "Specular Max Size:", 0.5, 5.0, bucket="population",
               logical=True, decimals=1, suffix="x", tick=50, truncate=True,
               tooltip="Maximum specular highlight scale for big bubbles. "
                       "Caps pulse-driven specular growth so highlights stay visually sane at large radii."),
        Slider("bubble_big_size_clamp", "Max Pulse Clamp:", 1.5, 8.0, bucket="population",
               logical=True, decimals=1, suffix="x", tick=50, truncate=True,
               tooltip="Maximum pulse multiplier for big bubbles. Caps how large a bubble can grow "
                       "during bass hits (e.g. 4.0x = bubble can grow up to 4× its base radius)."),
        Slider("bubble_big_contraction_bias", "Contraction Bias:", 0.0, 1.0, bucket="population",
               logical=True, percent=True, tick=10, truncate=True, admission_high=2.0,
               tooltip="How much big bubbles shrink during quiet passages. "
                       "100% = no contraction (default). Lower values make bubbles visibly breathe."),
        Slider("bubble_big_count", "Big Bubbles:", 0, 30, bucket="population",
               logical=True, scale=1, integer=True, decimals=0, truncate=True),
        Slider("bubble_small_count", "Small Bubbles:", 5, 80, bucket="population",
               logical=True, scale=1, integer=True, decimals=0, truncate=True),
        Slider("bubble_surface_reach", "Surface Reach:", 0.0, 1.0, bucket="population",
               logical=True, percent=True, truncate=True),
        Toggle("bubble_ghosting_enabled", "", "Enable Ghosting", bucket="ghost",
               logical=True, also_presentation=True, row_group="enable",
               tooltip="Show a fading afterimage trail behind moving bubbles."),
        Slider("bubble_ghost_alpha", "Ghost Opacity:", 0.0, 1.0, bucket="ghost",
               percent=True, tick=5, truncate=True, when=("bubble_ghosting_enabled", True)),
        Slider("bubble_ghost_decay", "Ghost Decay:", 0.1, 1.0, bucket="ghost",
               suffix="x", tick=5, bottom_padding=12, when=("bubble_ghosting_enabled", True)),
    ),
)


# ---- Extruded Bubble ------------------------------------------------------------------------------------------
# Its own control set (original Bubble's is only a guideline). Extruded_Bubble_Target.md section 9: nested buckets,
# visual controls (direction mappers, the collision triangle, range sliders for every quiet..loud amount) and
# conditionals so only what the current choices use is shown.

_EB_RAYS = ("extruded_bubble_rays_enabled", True)
_EB_BEAM_RAYS = (_EB_RAYS, ("extruded_bubble_lighting_coverage", "BEAM"))
_EB_SURFACE = ("extruded_bubble_light_type", "Sunlit Surface")
_EB_SURFACE_RAYS = (_EB_RAYS, _EB_SURFACE)
_EB_BANDS = ("extruded_bubble_particle_bands", True)
_EB_BEAM_EMISSION = ("extruded_bubble_emission_geometry", "BEAM")   # greyed under SCENE (whole inlet faces)
_EB_AUTO_ROTATE = ("extruded_bubble_auto_rotate", True)

_EXTRUDED_BUBBLE = ModeSettings(
    "extruded_bubble",
    buckets=(
        Bucket("light", "Light", "Where the scene's light comes from, its colour and strength."),
        Bucket("rays", "Light Rays", "Rays of light through the water and how they answer the music."),
        Bucket("bubbles", "Bubbles", "How many bubbles there are, quiet to loud, and how varied their sizes."),
        Bucket("motion", "Motion", "The stream's source, direction and forward speed."),
        Bucket("drift", "Drift", "Master drift and each population's quiet-to-loud multiplier. Negative reverses; 0 adds no drift; 1 retains the calibrated amount."),
        Bucket("reaction", "Reaction", "Breathing, pulse and the response to sustained loud passages."),
        Bucket("collision", "Collision", "What happens when bubbles meet: fuse, pop or bounce."),
        Bucket("camera", "Camera", "Turn the view slowly on its own after a while without camera input.", advanced=True),
        Bucket("water", "Water", "The water's colours, haze and veils of light.", advanced=True),
        Bucket("glass", "Glass", "How the bubbles' glass looks: clarity, rim glow, iridescence.", advanced=True),
        Bucket("particles", "Particles", "Specks, dust and their glow, quiet to loud.", advanced=True),
        Bucket("lens", "Lens", "Focus, depth of field and exposure.", advanced=True),
    ),
    entries=(
        Choice("extruded_bubble_light_type", "Light Type:", ("Sunlit Surface", "Deep Light"), bucket="light",
               tooltip='Choose an overhead Sunlit Surface light or a submerged Deep Light source. Surface mode draws the water surface; Deep Light does not.'),
        Choice("extruded_bubble_lighting_coverage", "Lighting Coverage:", ("BEAM", "SCENE"), bucket="light",
               tooltip="BEAM keeps light shafts within the authored ray beam. SCENE lights the water broadly, shaped by Ray Source → End: sunlight reaches Ray End's depth; a Deep Light reaches as far as Ray End, brightest toward it. This does not change where bubbles or particles are emitted."),
        SceneVolumePath("extruded_bubble_light_direction", "Light Source → End:", bucket="light", legacy_kind="light",
                  tooltip='Position the authored light Source and End in the 3D scene, including depth. The visible Deep Light emitter should follow Source. [NEEDS AUDIT] Verify emitter, rays and bubble glints coincide in the actual rendered scene.'),
        Colour("extruded_bubble_light_colour", "Light Colour:", "Light Colour", bucket="light", alpha=False,
               tooltip='Choose the colour of the scene light; it also tints the illuminated water and bubble highlights.'),
        Slider("extruded_bubble_light_strength", "Light Strength:", 0.0, 2.0, bucket="light",
               tooltip='Set direct light intensity on bubbles, shafts, water glow and particles. Ambient water and faint resting particles remain visible at zero.'),
        Slider("extruded_bubble_light_tint", "Light Tint:", 0.0, 1.0, bucket="light",
               tooltip="Set how much of the Light Colour the water's shafts and glow carry: 0 the water's own hue, 1 the light's. Around 0.45 suits a sunlit surface, 0.85 a deep light."),
        Toggle("extruded_bubble_rays_enabled", "", "Light Rays", bucket="rays",
               tooltip='Show or hide the light shafts. Ray intensity, fan shape and musical response are configured in the rest of this bucket.'),
        Range("extruded_bubble_rays", "Ray Strength:", 0.0, 1.0, percent=True, bucket="rays", when=_EB_RAYS,
              tooltip='Set the actual quiet and loud ray strengths. Ray Modulation 0 holds the upper handle; 1 uses the whole musical range. Equal handles give constant brightness; both at 0 turns rays off.'),
        Slider("extruded_bubble_ray_softness", "Ray Softness:", 0.0, 1.0, bucket="rays", when=_EB_RAYS,
               tooltip='Control how softly the edges of the light shafts blend into the surrounding water.'),
        Slider("extruded_bubble_beam_width", "Beam Width:", 0.25, 3.0, bucket="rays", when=_EB_BEAM_RAYS,
               decimals=2, suffix="x", tooltip='Widen or narrow the BEAM light footprint. The default 1x retains the accepted original footprint. This does not move the source or change stream emission.'),
        SceneVolumePath("extruded_bubble_ray_path", "Ray Source → End:", bucket="rays", legacy_kind="light",
                  when=_EB_RAYS, tooltip="BEAM: the physical beam's Source and End in all three axes; End controls how far it extends. SCENE: sunlight enters through the water surface and End's depth is how deep it reaches; a Deep Light lights out to End (its range), brightest toward it. Deep Light shares the physical Light Source."),
        Slider("extruded_bubble_ray_reach", "Ray Fan Spread:", 0.0, 1.0, bucket="rays", when=_EB_SURFACE_RAYS,
               tooltip='Change how far the sunlight fan spreads from the light direction. BEAM Source and End limit its illuminated path; in SCENE it spreads through the lit water.'),
        Slider("extruded_bubble_ray_modulation", "Ray Modulation:", 0.0, 1.0, bucket="rays", when=_EB_RAYS,
               tooltip='0 holds the upper Ray Strength continuously, including pauses. 1 follows music between the strength handles. Intermediate values narrow excursions toward the upper handle. Light Strength, disabled rays and physical occlusion still apply.'),
        Slider("extruded_bubble_ray_shimmer", "Ray Shimmer:", 0.0, 1.0, bucket="rays", when=_EB_RAYS,
               tooltip='Cosmetic shaft shimmer, independent of brightness modulation. 0 removes shimmer without changing the authored Ray Strength.'),
        Range("extruded_bubble_large_bubbles", "Large Bubbles:", 0.0, 40.0, scale=1, integer=True, bucket="bubbles",
               tooltip='Set the quiet-to-loud number of large bubbles: quiet passages head for the left handle, loud ones for the right. Bubbles leave by travelling out, never popping, so the count follows a section over seconds.'),
        Range("extruded_bubble_mid_bubbles", "Small Bubbles:", 0.0, 150.0, scale=1, integer=True, bucket="bubbles",
               tooltip='Set the quiet-to-loud number of small bubbles: quiet passages head for the left handle, loud ones for the right. Bubbles leave by travelling out, never popping, so the count follows a section over seconds.'),
        Range("extruded_bubble_bead_chains", "Bead Chains:", 0.0, 20.0, scale=1, integer=True, bucket="bubbles",
               tooltip='Set the quiet-to-loud amount of free bead chains in the current stream: quiet passages sit near the left handle, loud ones near the right.'),
        Slider("extruded_bubble_large_size", "Large Size:", 0.5, 2.0, bucket="bubbles",
               tooltip='Set the nominal physical radius of large bubbles; 1.0 is the original size, before musical breathing and per-bubble variation.'),
        Slider("extruded_bubble_small_size", "Small Size:", 0.5, 2.0, bucket="bubbles",
               tooltip='Set the nominal physical radius of small bubbles, independently of Large Size and the musical pulse.'),
        Slider("extruded_bubble_bead_size", "Bead/Wake Size:", 0.5, 2.0, bucket="bubbles",
               tooltip='Set the size of procedural beads and parent-attached wake bubbles. Does not change ordinary large or small bubble sizes.'),
        Slider("extruded_bubble_bead_scatter", "Bead Scatter:", 0.0, 1.0, bucket="bubbles",
               tooltip='Loosen bead chains into plumes of microbubbles that widen as they rise. 0 keeps each chain a single file.'),
        Slider("extruded_bubble_wake_trails", "Wake Trails:", 0.0, 1.0, bucket="bubbles",
               tooltip='Let bubbles trail translucent sheets of disturbed water with fine light-catching strands; higher values give more bubbles a trail.'),
        Slider("extruded_bubble_doublets", "Doublets:", 0.0, 1.0, bucket="bubbles",
               tooltip='Set the chance that a bubble rises already fused with a smaller companion, now and then two, as merged doublets and triplets.'),
        Slider("extruded_bubble_size_variety", "Size Variety:", 0.0, 1.0, bucket="bubbles",
               tooltip='Vary individual bubble birth sizes within a population; low values are more uniform, high values produce a wider range.'),
        Slider("extruded_bubble_columns", "Columns:", 0.0, 1.0, bucket="bubbles", enabled_when=_EB_BEAM_EMISSION,
               tooltip='In BEAM, gather a share of bubble births into stream-aligned columns. SCENE uses full-area inlet faces and does not quantize them into columns.'),
        Slider("extruded_bubble_bubble_spread", "Bubble Spread:", 0.0, 4.0, bucket="bubbles",
               enabled_when=_EB_BEAM_EMISSION,
               tooltip='In BEAM, widen or narrow bubble births around the local Stream Source. SCENE instead uses complete inlet faces; this does not change the population limits.'),
        Choice("extruded_bubble_emission_geometry", "Emission Geometry:", ("BEAM", "SCENE"), bucket="motion",
               tooltip="BEAM emits from the authored local source. SCENE fills the physical tank from upstream boundary faces and exits at downstream faces. Same bubbles, physics and count limits. [NEEDS AUDIT] Visual density and rendering cost remain unaccepted."),
        SceneVolumePath("extruded_bubble_stream_direction", "Stream Source → End:", bucket="motion", legacy_kind="stream",
                  tooltip='BEAM: move the local Source and End. SCENE: Source selects full inlet faces and End determines the flow direction; bubbles leave through the physical far boundary, not the End dot. [NEEDS AUDIT] Confirm native emitter alignment and source-to-exit fading.'),
        Range("extruded_bubble_stream_speed", "Stream Speed:", 0.0, 1.0, percent=True, bucket="motion",
               tooltip='Set the quiet-to-loud travel speed along the authored stream: a quiet passage sits near the left handle, a loud one near the right, and phrase changes swing it around that. Silence drifts slowly (Idle).'),
        Range("extruded_bubble_drift", "Drift:", 0.0, 1.0, percent=True, bucket="drift",
               tooltip='Set the quiet-to-loud amount of sideways/depth wandering around the stream: quiet passages sit near the left handle, loud ones near the right.'),
        Choice("extruded_bubble_drift_direction", "Drift Direction:",
               ("Wander", "Left", "Right", "Diagonal", "Swish (Across)", "Swish (Depth)", "Random",
                "Clockwise", "Counter-Clockwise"), bucket="drift",
               tooltip='Choose how Drift moves bubbles around the stream. Wander meanders each bubble; Left, Right and Diagonal steer the field across the stream; Swish sways it together; Random gives each bubble its own heading; Clockwise and Counter-Clockwise spiral bubbles outward around the stream (seen from its end).'),
        Range("extruded_bubble_drift_large", "Large Bubble Drift:", -1.0, 2.0, bucket="drift", suffix="x",
              tooltip='Quiet-to-loud multiplier of master Drift for existing and forming large bubbles. -1 reverses, 0 disables added drift, 1 preserves the prior amount, 2 doubles it. Stream, Sway and collision pushes are independent.'),
        Range("extruded_bubble_drift_small", "Small Bubble Drift:", -1.0, 2.0, bucket="drift", suffix="x",
              tooltip='Quiet-to-loud multiplier of master Drift for existing and forming small bubbles. Negative reverses, 0 disables added drift, 1 preserves the prior amount; Stream, Sway and collisions remain independent.'),
        Range("extruded_bubble_drift_fused", "Fused Bubble Drift:", -1.0, 2.0, bucket="drift", suffix="x",
              tooltip='Quiet-to-loud multiplier of master Drift at a fused group centre, applied once to the group. 1 retains the previous amount. Member shape and inherited contact pushes remain independent.'),
        Range("extruded_bubble_drift_chains", "Free Microbubble Drift:", -1.0, 2.0, bucket="drift", suffix="x",
              tooltip='Quiet-to-loud multiplier of master Drift for free bead chains and microbubble plumes. 0 preserves their previous transport; 1 uses calibrated bubble drift. Existing material retains its path when the gain changes; negative reverses added drift. Attached wakes retain parent history and inertia.'),
        Range("extruded_bubble_drift_snow", "Marine Snow Drift:", -1.0, 2.0, bucket="drift", suffix="x",
              tooltip='Quiet-to-loud added drift for free marine snow. 0 preserves its previous stream transport, negative reverses drift, 1 uses calibrated bubble drift. Existing drifted material retains its history when the gain returns to 0.'),
        Range("extruded_bubble_drift_specks", "Particle Drift:", -1.0, 2.0, bucket="drift", suffix="x",
              tooltip='Quiet-to-loud added drift for decorative specks and particle bands. 0 preserves their previous stream transport; negative reverses added drift. Parent-attached wakes retain their original history and inertia.'),
        Slider("extruded_bubble_sway", "Sway:", 0.0, 1.0, bucket="drift",
               tooltip='Increase the gentle side-to-side oscillation of rising bubbles without altering their forward stream direction.'),
        Range("extruded_bubble_breathing", "Breathing:", 0.0, 1.0, percent=True, bucket="reaction",
              tooltip="Set quiet contraction and loud expansion of large bubbles independently: the left handle is how far they shrink at rest and in silence (deepest from half way), the right handle how far a loud swell grows them."),
        Range("extruded_bubble_small_pulse", "Small Bubble Pulse:", 0.0, 1.0, percent=True, bucket="reaction",
              tooltip='Set quiet contraction and loud expansion of small bubbles independently: the left handle is how far they shrink at rest and in silence (deepest from half way, still a readable shell), the right handle how far a loud swell grows them.'),
        Slider("extruded_bubble_sustained", "Sustained Response:", 0.0, 1.0, bucket="reaction",
               tooltip='Choose how much extended musical energy supports the large-bubble body and influences other ongoing reactions.'),
        Slider("extruded_bubble_smoothing", "Smoothing:", 0.0, 1.0, bucket="reaction",
               tooltip='Ease each bubble’s displayed radius without changing music analysis, physical contacts or emission targets. [NEEDS AUDIT] Maximum visual smoothing still needs to pass small-bubble temporal fidelity and recorded-audio comparisons.'),
        Slider("extruded_bubble_idle", "Idle Energy:", 0.0, 1.0, bucket="reaction",
               tooltip='Set gentle baseline movement while music is quiet or stopped; it is not an audio sensitivity or gain control. Excludes surface-water animation.'),
        Triangle("extruded_bubble_collision", "Collision:", ("Fuse", "Pop", "Bounce"), bucket="collision",
                 tooltip='Choose the relative blend of Fuse, Pop and Bounce when bubbles collide. Move the point nearer the desired outcome.'),
        Choice("extruded_bubble_collision_scope", "Applies To:", ("All", "Big", "Small", "Off"), bucket="collision",
               tooltip='Choose which ordinary bubbles can participate in collision behavior: All, Big, Small, or Off.'),
        SceneCameraPosition("extruded_bubble_camera_position", "Camera Position:", bucket="camera",
               tooltip='Move the real camera eye inside the populated tank without changing FOV. The same water-clearance bounds apply here and during travel. WASD travels relative to view; Shift+WASD rotates; Q/E yaw; R resets. [NEEDS AUDIT] Confirm native drag feel and compositor presentation.'),
        Slider("extruded_bubble_camera_fov", "Camera Field of View:", 35.0, 62.0,
               scale=1, integer=True, suffix="°", decimals=0, bucket="camera",
               tooltip='Change the vertical viewing angle independently of camera travel and zoom/dolly. Narrower angles usually reduce peripheral perspective stretch.'),
        Toggle("extruded_bubble_auto_rotate", "", "Auto Rotate", bucket="camera",
               tooltip='Allow the camera to rotate by itself after the configured period without manual camera input.'),
        Slider("extruded_bubble_auto_rotate_after", "Auto Rotate After:", 1.0, 120.0, scale=1, integer=True,
               suffix=" s", decimals=0, bucket="camera", when=_EB_AUTO_ROTATE,
               tooltip='Wait this many seconds after the last camera interaction before Auto Rotate begins.'),
        Slider("extruded_bubble_auto_rotate_speed", "Auto Rotate Speed:", 1.0, 30.0, scale=1, integer=True,
               suffix="\u00b0/s", decimals=0, bucket="camera", when=_EB_AUTO_ROTATE,
               tooltip='Set the slow automatic camera orbit rate in degrees per second.'),
        Colour("extruded_bubble_water_colour", "Water Colour:", "Water Colour", bucket="water", alpha=False,
               tooltip='Choose the primary colour tint of the water and the nearer visible water volume.'),
        Colour("extruded_bubble_depth_colour", "Depth Colour:", "Depth Colour", bucket="water", alpha=False,
               tooltip='Choose the colour of deeper water and the distant fading background.'),
        Slider("extruded_bubble_haze", "Haze:", 0.0, 1.0, bucket="water",
               tooltip='Control how strongly the water obscures objects with depth; higher values create a murkier scene.'),
        Slider("extruded_bubble_floor", "Floor:", 0.0, 1.0, bucket="water",
               tooltip='Show a floor far below, lit by a moving caustic net of focused light over darker rocky patches and fading into the haze with distance.'),
        Slider("extruded_bubble_dust", "Dust:", 0.0, 1.0, bucket="water",
               tooltip='Add glowing clouds of fine dust in the water, stretched along the stream and brightest toward the light.'),
        Slider("extruded_bubble_veils", "Light Veils:", 0.0, 1.0, bucket="water",
               tooltip='Control the subtle layered veils of light visible through the water, independently of individual light-ray shafts.'),
        Slider("extruded_bubble_surface_brightness", "Surface Brightness:", 0.0, 2.0, bucket="water",
               when=_EB_SURFACE,
               tooltip='Set how bright the visible overhead water surface appears. Available only with Sunlit Surface lighting.'),
        Slider("extruded_bubble_clarity", "Clarity:", 0.0, 1.0, bucket="glass",
               tooltip='Control the intended clearness and visibility of the bubble glass and the scene seen through it.'),
        Slider("extruded_bubble_rim_glow", "Rim Glow:", 0.0, 2.0, bucket="glass",
               tooltip='Set the strength of luminous light around bubble rims.'),
        Slider("extruded_bubble_iridescence", "Iridescence:", 0.0, 1.0, bucket="glass",
               tooltip='Control the strength of subtle rainbow-film colours on the bubble glass.'),
        Slider("extruded_bubble_softness", "Softness:", 0.0, 1.0, bucket="glass",
               tooltip='Control the apparent softness or diffusion of bubble-glass highlights and surface detail.'),
        Slider("extruded_bubble_sparkle", "Sparkle:", 0.0, 2.0, bucket="glass",
               tooltip="Adjust the bright specular glints on the bubbles' glass (and the sparkle of glittering specks); 0 removes them, 1 is the original look."),
        Range("extruded_bubble_particles", "Particles:", 0.0, 1.0, percent=True, bucket="particles",
               tooltip='Set quiet-to-loud particle density: quiet passages sit near the left handle, loud ones near the right. Individual speck radiance stays constant while size and glow release separately.'),
        Slider("extruded_bubble_particle_spread", "Particle Spread:", 0.0, 4.0, bucket="particles",
               enabled_when=_EB_BEAM_EMISSION,
               tooltip='In BEAM, widen or narrow decorative specks, free beads and snow around the stream. SCENE distributes them across actual inlet faces instead. Attached wakes always keep their parent bubble source.'),
        Slider("extruded_bubble_particle_size", "Particle Size:", 0.5, 2.0, bucket="particles",
               tooltip='Set the apparent size of floating decorative specks. It does not resize ordinary bubbles.'),
        Colour("extruded_bubble_particle_colour", "Particle Colour:", "Particle Colour", bucket="particles",
               alpha=False,
               tooltip='Choose the base colour used by decorative specks, distinct from the primary scene light colour.'),
        Slider("extruded_bubble_particle_warmth", "Warm Share:", 0.0, 1.0, bucket="particles",
               tooltip='Choose what fraction of the particle/speck lighting appears warm rather than cool.'),
        Slider("extruded_bubble_particle_glow", "Particle Glow:", 0.0, 1.0, bucket="particles",
               tooltip='Set baseline luminous glow around decorative specks. The separate Glow Reactivity slider can add musical lifts.'),
        Slider("extruded_bubble_particle_glow_reactivity", "Glow Reactivity:", 0.0, 1.0, bucket="particles",
               tooltip='Add an optional gentle musical lift to the baseline particle glow; zero keeps constant authored glow.'),
        Toggle("extruded_bubble_particle_bands", "", "Particle Bands", bucket="particles",
               tooltip='Enable or disable spatial banding/clustering of floating specks; does not control audio frequency bands.'),
        Slider("extruded_bubble_band_contrast", "Band Contrast:", 0.0, 1.0, bucket="particles", when=_EB_BANDS,
               tooltip='Control how distinctly the particle bands stand out from the surrounding speck field. Shown when Particle Bands is enabled.'),
        Slider("extruded_bubble_band_gather", "Band Gathering:", 0.0, 1.0, bucket="particles", when=_EB_BANDS,
               tooltip='Gather the background dust into the bands, and with SCENE emission the specks themselves too, leaving dark water between them. 0 keeps the whole field and lets the bands vary its glow.'),
        Slider("extruded_bubble_focus", "Focus:", 0.0, 1.0, bucket="lens",
               tooltip='Choose the focus distance: bubbles nearer than it soften. The lower half softens only very close bubbles; the upper half reaches the bubbles in view.'),
        Slider("extruded_bubble_aperture", "Aperture:", 0.0, 1.0, bucket="lens",
               tooltip='Set how strongly bubbles nearer than the Focus distance soften; 0 keeps everything sharp.'),
        Slider("extruded_bubble_exposure", "Exposure:", 0.5, 1.5, bucket="lens",
               tooltip='Scale the overall scene exposure/brightness; it does not alter musical input gain, sensitivity or ray-response timing.'),
        # The live view pose (set by orbiting, scrolling and panning inside the card, not from the body).
        Slider("extruded_bubble_turn", "", -1.0, 1.0, bucket=""),
        Slider("extruded_bubble_tilt", "", -0.5, 0.5, bucket=""),
        Slider("extruded_bubble_scene_scale", "", 0.2, 5.0),  # physical dolly: 75..3 world units at default pivot, FOV unchanged
        Slider("extruded_bubble_scene_pan_x", "", -0.5, 0.5),
        Slider("extruded_bubble_scene_pan_y", "", -0.5, 0.5),
    ),
)

_SPECS: tuple[ModeSettings, ...] = (_SINE_WAVE, _oscilloscope(), _SHOCKWAVE_GRID, _DEVCURVE, _EXTRUDED_SPECTRUM, _SPECTRUM, _SPHERE, _BUBBLE,
                                    _EXTRUDED_BUBBLE)
_BY_MODE: Mapping[str, ModeSettings] = MappingProxyType({spec.mode_id: spec for spec in _SPECS})
_CONTROLS = tuple(control for spec in _SPECS for control in spec.controls)


def iter_mode_settings() -> tuple[ModeSettings, ...]:
    return _SPECS


def mode_settings(mode_id: str) -> ModeSettings | None:
    return _BY_MODE.get(str(mode_id))


def require_mode_settings(mode_id: str) -> ModeSettings:
    spec = mode_settings(mode_id)
    if spec is None:
        raise KeyError(f"no Settings spec for Visualizer mode {mode_id!r}")
    return spec


def spec_controls() -> tuple[Control, ...]:
    """Every spec'd mode's controls (the settings model gains a field for each)."""
    return _CONTROLS


def spec_control(key: str) -> Control | None:
    for control in spec_controls():
        if control.key == key:
            return control
    return None


def control_runtime_attr(control: Control) -> str:
    return getattr(control, "runtime_attr", "") or f"_{control.key}"


def control_runtime_value(control: Control, value: object) -> object:
    if isinstance(control, Choice) and control.runtime_values:
        return control.runtime_values[control.choices.index(value)]
    return value


def read_control_value(control: Control, read_value, default: object) -> object:
    """Reuse a declared canonical input migration when a setting has historical aliases."""
    path = getattr(control, "read", "")
    if path:
        module, _, name = path.partition(":")
        return getattr(import_module(module), name)(read_value, fallback=default)
    return read_value(control.key, default)


__all__ = [
    "Bucket",
    "Choice",
    "Colour",
    "Control",
    "Custom",
    "Direction",
    "ScenePath",
    "SceneVolumePath",
    "SceneCameraPosition",
    "ModeSettings",
    "Range",
    "Slider",
    "Toggle",
    "Triangle",
    "VISUAL_CONTROLS",
    "iter_mode_settings",
    "mode_settings",
    "require_mode_settings",
    "spec_control",
    "spec_controls",
    "control_runtime_attr",
    "control_runtime_value",
    "read_control_value",
]
