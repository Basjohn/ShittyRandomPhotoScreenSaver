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

Adding a setting to a spec'd mode is its default plus one control here; the renderer reads it by key.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Union


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


@dataclass(frozen=True)
class Slider:
    """A float shown on a slider of ``scale`` positions per unit (0.01 steps by default)."""

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

    def admit(self, value: object, default: object) -> float:
        number = _finite(value)
        if number is None:
            number = float(default)
        return max(float(self.low), min(float(self.high), number))

    coerce = staticmethod(float)


@dataclass(frozen=True)
class Toggle:
    """A checkbox; ``text`` is the checkbox's own words, ``label`` its row label."""

    key: str
    label: str
    text: str
    tooltip: str = ""
    bucket: str = ""
    logical: bool = False

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

    coerce = staticmethod(bool)


@dataclass(frozen=True)
class Choice:
    """A drop-down of fixed labels; an unknown stored label becomes the default."""

    key: str
    label: str
    choices: tuple[str, ...]
    tooltip: str = ""
    bucket: str = ""
    logical: bool = False

    def admit(self, value: object, default: object) -> str:
        return value if isinstance(value, str) and value in self.choices else str(default)

    coerce = staticmethod(str)


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

    def admit(self, value: object, default: object) -> list[int]:
        channels = list(value) if isinstance(value, (list, tuple)) else []
        numbers = [_finite(channel) for channel in channels[:4]]
        if len(numbers) < 3 or any(number is None for number in numbers):
            numbers = [float(channel) for channel in list(default)[:4]]
        while len(numbers) < 4:
            numbers.append(255.0)
        return [max(0, min(255, int(round(number)))) for number in numbers]

    coerce = staticmethod(list)


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


Control = Union[Slider, Toggle, Choice, Colour]
Entry = Union[Slider, Toggle, Choice, Colour, Custom]


@dataclass(frozen=True)
class ModeSettings:
    """One mode's Settings body. ``attr_prefix`` names the body's scaffold attributes
    (``_<prefix>_settings_container``, ``_<prefix>_normal``...), the mode id unless older code
    already names them otherwise."""

    mode_id: str
    buckets: tuple[Bucket, ...]
    entries: tuple[Entry, ...]
    attr_prefix: str = ""

    @property
    def prefix(self) -> str:
        return self.attr_prefix or self.mode_id

    @property
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
        return tuple(control for control in self.controls if not control.logical)

    def logical_controls(self) -> tuple[Control, ...]:
        return tuple(control for control in self.controls if control.logical)


# ---- Shockwave Grid ----------------------------------------------------------------------------

_SHOCKWAVE_GRID = ModeSettings(
    "shockwave_grid",
    buckets=(
        Bucket("appearance", "Appearance",
               "Author the grid-line and shockwave-crest colours directly, including alpha."),
        Bucket("waves", "Waves",
               "Beats send shockwaves across a neon grid; Spectrum's bars raise its horizon. "
               "This grid owns the horizon's bar count and response."),
        Bucket("response", "Bar Response",
               "The shared Spectrum shaper is reused, while this grid owns its layout, nodes, lanes and response."),
        Bucket("render", "Render",
               "Density, glow, floor, scrolling and overflow are rendering axes, not colour authoring.",
               advanced=True),
    ),
    entries=(
        Colour("shockwave_grid_line_color", "Line Colour:", "Choose Grid Line Colour",
               "The base grid line colour, including alpha.", bucket="appearance"),
        Colour("shockwave_grid_crest_color", "Crest Colour:", "Choose Shockwave Crest Colour",
               "The colour the lines turn as a shockwave's crest and the horizon pass through them, including alpha.",
               bucket="appearance"),
        Slider("shockwave_grid_wave_height", "Wave Height:", 0.0, 1.0,
               "How high each beat's shockwave lifts the grid.", bucket="waves"),
        Slider("shockwave_grid_wave_speed", "Wave Speed:", 0.0, 1.0,
               "How fast the shockwaves spread across the grid.", bucket="waves"),
        Slider("shockwave_grid_horizon", "Horizon:", 0.0, 1.0,
               "How strongly Spectrum's bar field raises the grid horizon.", bucket="waves"),
        Slider("shockwave_grid_idle", "Idle Swell:", 0.0, 1.0,
               "How much the grid breathes when the music is quiet.", bucket="waves"),
        Custom("shape", "response", build="ui.tabs.media.shockwave_grid_builder:build_response_section",
               load="ui.tabs.media.shockwave_grid_settings_binding:load_response_section",
               collect="ui.tabs.media.shockwave_grid_settings_binding:collect_response_section",
               keys=("shockwave_grid_mirrored", "shockwave_grid_shape_nodes",
                     "shockwave_grid_notch_positions_mirrored", "shockwave_grid_notch_positions_linear",
                     "shockwave_grid_lane_strengths_mirrored", "shockwave_grid_lane_strengths_linear",
                     "shockwave_grid_wave_amplitude", "shockwave_grid_profile_floor", "shockwave_grid_drop_speed",
                     "shockwave_grid_visual_smoothing_enabled", "shockwave_grid_visual_smoothing",
                     "shockwave_grid_solid_bar_hysteresis_enabled")),
        Slider("shockwave_grid_density", "Grid Density:", 0.0, 1.0, "How many grid lines there are.",
               bucket="render"),
        Slider("shockwave_grid_glow", "Glow:", 0.0, 1.0,
               "How much the lines and the shockwave crests glow; zero turns the glow off.", bucket="render"),
        Slider("shockwave_grid_floor", "Floor:", 0.0, 1.0,
               "How much of the receding grid floor remains visible.", bucket="render"),
        Slider("shockwave_grid_scroll", "Scroll:", 0.0, 1.0,
               "How quickly the grid texture travels under the camera.", bucket="render"),
        Toggle("shockwave_grid_allow_overflow", "Allow Overflow:", "Let the grid leave the visualizer's rectangle",
               "On: the grid may reach past the rectangle as it turns and tilts. Off: it is cut at the rectangle.",
               bucket="render"),
        # Orbited live (W/A/S/D, Alt + drag) rather than from a body control.
        Slider("shockwave_grid_tilt", "", 0.0, 1.0, bucket=""),
        Slider("shockwave_grid_turn", "", -1.0, 1.0, bucket=""),
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
                   bucket="display", logical=True, scale=10, decimals=1, suffix=" ms"),
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
                   "The scale's colour; its alpha sets how faint it is.", bucket="screen"),
        ),
    )


_SPECS: tuple[ModeSettings, ...] = (_oscilloscope(), _SHOCKWAVE_GRID)
_BY_MODE: Mapping[str, ModeSettings] = MappingProxyType({spec.mode_id: spec for spec in _SPECS})


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
    return tuple(control for spec in _SPECS for control in spec.controls)


def spec_control(key: str) -> Control | None:
    for control in spec_controls():
        if control.key == key:
            return control
    return None


__all__ = [
    "Bucket",
    "Choice",
    "Colour",
    "Control",
    "Custom",
    "ModeSettings",
    "Slider",
    "Toggle",
    "iter_mode_settings",
    "mode_settings",
    "require_mode_settings",
    "spec_control",
    "spec_controls",
]
