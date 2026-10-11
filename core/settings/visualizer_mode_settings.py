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
A control may also be shown only while another control holds a value (``when``), so a group that only
matters while its toggle is on hides with it.
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


When = tuple   # (key, value): shown only while that control of the same mode holds that value


@dataclass(frozen=True)
class Slider:
    """A float shown on a slider of ``scale`` positions per unit (0.01 steps by default).

    Its value reads as ``decimals`` places plus ``suffix``, or as a whole percent (``percent``);
    ``integer`` keeps it a whole number; ``tick`` marks every that many positions under it."""

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

    def admit(self, value: object, default: object) -> float | int:
        number = _finite(value)
        if number is None:
            number = float(default)
        number = max(float(self.low), min(float(self.high), number))
        return int(round(number)) if self.integer else number

    def coerce(self, value: object) -> float | int:
        return int(value) if self.integer else float(value)

    def text(self, position: int) -> str:
        """The value label for a slider position."""
        if self.percent:
            return f"{round(position * 100 / self.scale)}%"
        return f"{position / self.scale:.{self.decimals}f}{self.suffix}"


@dataclass(frozen=True)
class Toggle:
    """A checkbox; ``text`` is the checkbox's own words, ``label`` its row label (none: the checkbox
    stands alone across the bucket)."""

    key: str
    label: str
    text: str
    tooltip: str = ""
    bucket: str = ""
    logical: bool = False
    when: When = ()

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


@dataclass(frozen=True)
class Choice:
    """A drop-down of fixed labels; an unknown stored value becomes the default. It persists the
    label, or its position among ``choices`` when ``indexed`` (a number outside them is clamped in)."""

    key: str
    label: str
    choices: tuple[str, ...]
    tooltip: str = ""
    bucket: str = ""
    logical: bool = False
    indexed: bool = False
    when: When = ()

    def admit(self, value: object, default: object) -> str | int:
        if self.indexed:
            number = None if isinstance(value, bool) else _finite(value)
            if number is None or number != int(number):
                return int(default)
            return max(0, min(len(self.choices) - 1, int(number)))
        return value if isinstance(value, str) and value in self.choices else str(default)

    def coerce(self, value: object) -> str | int:
        return int(value) if self.indexed else str(value)


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
               "Extra line colors, travel, ghosting, displacement, and line offsets still apply when hidden.",
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
               "Bass-reactive XY displacement of multi-line sine waves. "
               "Higher = larger transient shoves when bass hits. "
               "Most visible with 2-3 lines enabled.", bucket="multi_line", percent=True, tick=10),
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


_SPECS: tuple[ModeSettings, ...] = (_SINE_WAVE, _oscilloscope(), _SHOCKWAVE_GRID)
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
