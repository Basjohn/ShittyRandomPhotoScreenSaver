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

from rendering.gl_programs.extruded_spectrum_options import EXTRUDED_COLOURINGS


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
    ``integer`` keeps it a whole number; ``tick`` marks every that many positions under it;
    ``signed`` shows a plus sign for nonnegative values. ``source`` delegates consumption to the
    existing descriptor source-profile projection; it creates no private logical/renderer value.
    ``availability`` optionally names an import-safe capability flag and its disabled tooltip."""

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
        sign = "+" if self.signed else ""
        return f"{position / self.scale:{sign}.{self.decimals}f}{self.suffix}"


@dataclass(frozen=True)
class Toggle:
    """A checkbox; ``text`` is the checkbox's own words, ``label`` its row label (none: the checkbox
    stands alone across the bucket). ``row_group`` places toggles together in one aligned row."""

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
    source: bool = False
    availability: tuple[str, str] = ()
    compact: bool = True

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
    source: bool = False
    availability: tuple[str, str] = ()

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
        return tuple(control for control in self.controls if not control.logical and not control.source)

    def logical_controls(self) -> tuple[Control, ...]:
        return tuple(control for control in self.controls if control.logical and not control.source)

    def source_controls(self) -> tuple[Control, ...]:
        return tuple(control for control in self.controls if control.source)


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


_SPECS: tuple[ModeSettings, ...] = (_SINE_WAVE, _oscilloscope(), _SHOCKWAVE_GRID, _DEVCURVE, _EXTRUDED_SPECTRUM)
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
