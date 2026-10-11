"""Each transition's Settings, declared once.

A transition's spec lists what its Settings page offers: the Direction choices and the codes they
resolve to, the controls on its page in order, and the optional choices in its closed Advanced
bucket. The Transitions tab builds, hydrates, saves and signal-blocks a page from its spec; the
request resolver clamps numbers to the same ranges, admits choices from the same lists and
resolves directions through the same codes; tests check every spec against the canonical defaults
and the transition registry. Values never live here: defaults stay in the canonical defaults.

Adding a transition's Settings means adding its spec here (and its defaults section); its page,
persistence and admission follow. A page with controls no spec type describes (sliders with value
labels, colours with alpha, controls that show or hide each other) sets ``custom`` and builds,
hydrates and saves those itself, listing their fields in ``custom_fields``.

Import-safe: plain data and the light ``*_options`` modules only; no Qt, no GL, no shader module.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Protocol, Union

from rendering.gl_programs.blinds_options import BLINDS_SLATS_RANGE, BLINDS_STYLE_CHOICES
from rendering.gl_programs.blockspin_options import BLOCK_SPIN_EDGE_GLASS_CHOICES
from rendering.gl_programs.capillary_bloom_options import CAPILLARY_SOURCES_RANGE
from rendering.gl_programs.chromatic_shear_options import SHEAR_DIRECTIONS, SHEAR_SLICES_RANGE
from rendering.gl_programs.cube_turn_options import CUBE_TURN_DIRECTIONS
from rendering.gl_programs.depth_cascade_options import CASCADE_CARDS_RANGE, CASCADE_SWEEPS
from rendering.gl_programs.edge_bloom_options import EDGE_BLOOM_COLOUR_SOURCE_CHOICES
from rendering.gl_programs.jigsaw_options import JIGSAW_ORDERS, JIGSAW_PIECES_RANGE
from rendering.gl_programs.liquid_lens_options import LIQUID_LENS_STOPS_RANGE
from rendering.gl_programs.membrane_options import MEMBRANE_SWEEPS
from rendering.gl_programs.page_curl_options import PAGE_CURL_ORIGINS
from rendering.gl_programs.scene3d import (
    SCENE3D_ANTIALIASING_CHOICES,
    SCENE3D_EFFECT_CHOICES,
    SCENE3D_TRAIL_CHOICES,
)
from rendering.gl_programs.surface_tension_options import TENSION_POOLS_RANGE
from rendering.gl_programs.vhs_options import VHS_DIRECTIONS
from rendering.gl_programs.volumetric_dissolve_options import (
    VOLUMETRIC_DIRECTIONS,
    VOLUMETRIC_PARTICLE_SIZE_RANGE,
)


class RandomSource(Protocol):
    def choice(self, seq): ...


# ---- Admission: how a persisted value becomes a usable one ------------------------------------
#
# Shared by the Settings page (hydrating a control) and the request resolver (building a run), so
# a malformed or out-of-range persisted value is repaired the same way in both.

def as_number(value: object, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float(default)
    return result if math.isfinite(result) else float(default)


def as_integer(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return int(default)


def as_bool(value: object, default: bool) -> bool:
    """The Settings layer's bool coercion (strings such as "on" and "false" included)."""

    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "on", "enabled"}:
            return True
        if normalized in {"false", "no", "0", "off", "disabled"}:
            return False
    return bool(default)


# ---- Control types -----------------------------------------------------------------------------

@dataclass(frozen=True)
class Number:
    """A spin box: whole numbers when ``integer``, else two decimals in ``step`` steps."""

    field: str
    label: str
    low: float
    high: float
    tooltip: str = ""
    integer: bool = False
    suffix: str = ""
    step: float = 0.05
    decimals: int = 2

    def admit(self, value: object, default: object) -> Union[int, float]:
        if self.integer:
            return max(int(self.low), min(int(self.high), as_integer(value, int(default))))
        return max(float(self.low), min(float(self.high), as_number(value, float(default))))


@dataclass(frozen=True)
class Toggle:
    """A checkbox; ``label`` is its text (its row has no label)."""

    field: str
    label: str
    tooltip: str = ""

    def admit(self, value: object, default: object) -> bool:
        return as_bool(value, bool(default))


@dataclass(frozen=True)
class Choice:
    """A drop-down of fixed labels. ``aliases`` maps retired spellings that older profiles may still
    hold to the label that now does the same thing; anything else unknown becomes the default."""

    field: str
    label: str
    choices: tuple[str, ...]
    tooltip: str = ""
    compact: bool = True
    aliases: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def admit(self, value: object, default: object) -> str:
        if isinstance(value, str):
            value = self.aliases.get(value, value)
            if value in self.choices:
                return value
        return str(default)


@dataclass(frozen=True)
class Colour:
    """An RGB swatch persisted as ``[r, g, b, 255]``. ``enabled_when`` names a Choice field and the
    label under which the colour applies; otherwise the swatch is disabled."""

    field: str
    label: str
    title: str
    tooltip: str = ""
    enabled_when: tuple[str, str] | None = None

    def admit(self, value: object, default: object) -> tuple[int, int, int]:
        if not (isinstance(value, (list, tuple)) and len(value) >= 3
                and all(isinstance(c, (int, float)) and math.isfinite(c) for c in value[:3])):
            value = default
        return tuple(max(0, min(255, int(c))) for c in value[:3])


Control = Union[Number, Toggle, Choice, Colour]


@dataclass(frozen=True)
class Directions:
    """The shared Direction box's choices: each offered label and the code it resolves to.

    ``aliases`` are spellings older profiles or internal callers use (not offered). ``pool`` is
    the order Random draws from; it stays fixed so a seeded run picks the same direction it always
    did. ``strict`` raises on an unknown label; otherwise an unknown label picks at random, as
    Random does (retired choices from older profiles).
    """

    codes: Mapping[str, str]
    aliases: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    pool: tuple[str, ...] = ()
    strict: bool = False

    @property
    def choices(self) -> tuple[str, ...]:
        return (*self.codes, "Random")

    @property
    def random_pool(self) -> tuple[str, ...]:
        return self.pool or tuple(dict.fromkeys(self.codes.values()))

    def code(self, raw: object) -> str | None:
        text = str(raw or "Random")
        return self.codes.get(text) or self.aliases.get(text)

    def resolve(self, raw: object, rng: RandomSource) -> str:
        code = self.code(raw)
        if code is not None:
            return code
        if self.strict and str(raw or "Random") != "Random":
            raise ValueError(f"unknown transition direction: {raw!r}")
        return str(rng.choice(self.random_pool))


@dataclass(frozen=True)
class TransitionSettings:
    """One transition's Settings page. ``name`` is its registry setting name, ``section`` its key
    under ``transitions``. ``title`` overrides the page title ("<name> Settings")."""

    name: str
    section: str
    directions: Directions | None = None
    controls: tuple[Control, ...] = ()
    advanced: tuple[Control, ...] = ()
    custom: bool = False
    custom_fields: tuple[str, ...] = ()
    title: str = ""

    @property
    def page_title(self) -> str:
        return self.title or f"{self.name} Settings"

    @property
    def has_page(self) -> bool:
        return bool(self.controls or self.advanced or self.custom)

    @property
    def all_controls(self) -> tuple[Control, ...]:
        return self.controls + self.advanced

    def control(self, name: str) -> Control:
        for item in self.all_controls:
            if item.field == name:
                return item
        raise KeyError(f"{self.section} declares no control {name!r}")

    def fields(self) -> tuple[str, ...]:
        """Every persisted field this page owns: direction, controls and custom fields."""
        names = ("direction",) if self.directions is not None else ()
        return names + tuple(item.field for item in self.all_controls) + self.custom_fields

    def page_values(self, config: Mapping[str, object], defaults: Mapping[str, object]) -> dict[str, object]:
        """The admitted value of every number and toggle on the page (not the Advanced bucket):
        the run parameters most renderers take by the same names."""
        return {item.field: item.admit(config.get(item.field, defaults[item.field]), defaults[item.field])
                for item in self.controls if isinstance(item, (Number, Toggle))}

    def admit(self, name: str, config: Mapping[str, object], defaults: Mapping[str, object]):
        item = self.control(name)
        return item.admit(config.get(name, defaults[name]), defaults[name])


def widget_attr(section: str, control: Control) -> str:
    """The Settings tab attribute holding ``control``'s widget, e.g. ``liquid_lens_stops_spin``.
    A field already named after its section is not repeated (``ripple_count_spin``)."""
    stem = control.field if control.field.startswith(f"{section}_") else f"{section}_{control.field}"
    kind = {Number: "spin", Toggle: "check", Choice: "combo", Colour: "btn"}[type(control)]
    return f"{stem}_{kind}"


# ---- Shared choices ----------------------------------------------------------------------------

_EDGES = {
    "Left to Right": "right",
    "Right to Left": "left",
    "Top to Bottom": "down",
    "Bottom to Top": "up",
}
_DIAGONALS = {"Diagonal TL-BR": "diag_tl_br", "Diagonal TR-BL": "diag_tr_bl"}
_REVERSE_DIAGONALS = {"Diagonal BL-TR": "diag_bl_tr", "Diagonal BR-TL": "diag_br_tl"}
# Older spellings of the diagonals.
_DIAGONAL_ALIASES = {"Diagonal TL to BR": "diag_tl_br", "Diagonal TR to BL": "diag_tr_bl"}
_CODE_ALIASES = {code: code for code in ("left", "right", "up", "down", "diag_tl_br", "diag_tr_bl")}

BLOCK_SPIN_DIRECTIONS = _SWEEP = Directions({**_EDGES, **_DIAGONALS}, aliases=_DIAGONAL_ALIASES,
                    pool=("left", "right", "down", "up", "diag_tl_br", "diag_tr_bl"), strict=True)
_FRACTURE = Directions(
    {**_EDGES, **_DIAGONALS, "Center Out": "center_out"},
    aliases={**_DIAGONAL_ALIASES, **_CODE_ALIASES, "center_out": "center_out"},
    pool=("left", "right", "up", "down", "diag_tl_br", "diag_tr_bl", "center_out"),
    strict=True,
)
_EIGHT_WAY = Directions(
    {**_EDGES, **_DIAGONALS, **_REVERSE_DIAGONALS},
    aliases={**_DIAGONAL_ALIASES, **_CODE_ALIASES, "center_out": "center_out",
             "diag_bl_tr": "diag_bl_tr", "diag_br_tl": "diag_br_tl", "Center Out": "center_out"},
    pool=("left", "right", "up", "down", "diag_tl_br", "diag_tr_bl", "diag_bl_tr", "diag_br_tl"),
    strict=True,
)
# Melt starts at an origin rather than sweeping from an edge; retired edge directions from older
# profiles pick an origin per run, as Random does.
MELT_ORIGINS = {
    "Top Left": "top_left",
    "Top Center": "top_center",
    "Top Right": "top_right",
    "Center Out": "center_out",
    "Center In": "center_in",
}


def _choice_of(codes: Mapping[str, str]) -> Directions:
    return Directions(dict(codes))


_AUTO_TIP = " Auto follows 3D Transitions on the 3D tab."
_ANTIALIASING = Choice("antialiasing", "Anti-aliasing:", SCENE3D_ANTIALIASING_CHOICES,
                       "Multisampling that smooths the 3D edges; 4x and 8x cost the most GPU time." + _AUTO_TIP)
_MOTION_BLUR = Choice("motion_blur", "Motion Blur:", SCENE3D_EFFECT_CHOICES,
                      "Blurs fast pieces along their motion, as a camera would; still parts stay sharp." + _AUTO_TIP)
_MOTION_TRAILS = Choice("motion_trails", "Motion Trails:", SCENE3D_TRAIL_CHOICES,
                        "Faint, fading outlines of where fast pieces just were.")
_MOTION = (_ANTIALIASING, _MOTION_BLUR, _MOTION_TRAILS)


def _unit(name: str, label: str, tooltip: str) -> Number:
    """A 0-1 look control (gloss, glow, thickness...)."""
    return Number(name, label, 0.0, 1.0, tooltip)


def _gloss(tooltip: str, label: str = "Gloss:") -> Number:
    return _unit("gloss", label, tooltip)


# ---- The specs, in registry order --------------------------------------------------------------

_SPECS: tuple[TransitionSettings, ...] = (
    TransitionSettings(
        "Ripple", "ripple",
        controls=(Number("ripple_count", "Ripple Count:", 1, 8, integer=True),),
    ),
    TransitionSettings("Wipe", "wipe", directions=Directions(
        {"Left to Right": "left_to_right", "Right to Left": "right_to_left", "Top to Bottom": "top_to_bottom",
         "Bottom to Top": "bottom_to_top", "Diagonal TL-BR": "diag_tl_br", "Diagonal TR-BL": "diag_tr_bl"},
        strict=True)),
    TransitionSettings(
        "3D Block Spins", "blockspin",
        # Its Direction sits on its own page; BLOCK_SPIN_DIRECTIONS resolves it.
        controls=(Choice("direction", "Direction:", BLOCK_SPIN_DIRECTIONS.choices, compact=False),),
        advanced=(
            Choice("edge_glass", "Edge Glass:", BLOCK_SPIN_EDGE_GLASS_CHOICES,
                   "Polished glass edges on the spinning slab, showing the next image: Reflection, Refraction or "
                   "Both. The sheen and gloss stay."),
            *_MOTION,
        ),
    ),
    TransitionSettings(
        "Slide", "slide", title="Slide Motion",
        directions=Directions(dict(_EDGES), aliases={**_DIAGONALS, **_DIAGONAL_ALIASES},
                              pool=("left", "right", "down", "up"), strict=True),
        controls=(Choice("motion_style", "Motion Style:", ("Linear", "Elastic", "Wobble", "Flex", "Perspective Push")),),
    ),
    TransitionSettings(
        "Glass Shatter", "glass_shatter", directions=_FRACTURE,
        controls=(
            Number("shards", "Shard Count:", 24, 180, integer=True),
            Number("depth", "Depth:", 0.2, 1.5),
            Toggle("collisions", "Shards Collide", "Shards that meet in flight bounce off each other and spin away."),
            Toggle("reshatter", "Shards Break Again",
                   "Shards crack into smaller pieces in flight: when they collide if Shards Collide is on, "
                   "otherwise about 30% of shards crack at random."),
            _unit("thickness", "Glass Thickness:",
                  "Thickness of the solid shards and their beveled edges. Zero makes a thin pane."),
            _unit("transparency", "Transparency:",
                  "How much of the next image is visible through moving glass. Zero keeps opaque image faces."),
            _unit("refraction", "Refraction:",
                  "Bending of the next image through the glass. Visible with transparency; zero disables distortion."),
            _unit("dispersion", "Color Dispersion:", "Prismatic color separation in refraction. Zero disables it."),
            _unit("sheen", "Reflections / Sheen:",
                  "Reflections, rim glints and bevel highlights. Zero removes the optical highlights."),
        ),
        advanced=_MOTION,
    ),
    TransitionSettings(
        "Exploding Tiles", "exploding_tiles", directions=_FRACTURE,
        controls=(
            Number("columns", "Tile Columns:", 6, 48, integer=True),
            Number("depth", "Depth:", 0.2, 1.5),
            _unit("thickness", "Tile Thickness:", "Solid tile thickness relative to tile size, with beveled edges."),
            Number("force", "Explosion Force:", 0.5, 2.0,
                   "Strength of the outward launch and tumble. Tiles travel beyond the screen edge."),
        ),
        advanced=(
            _ANTIALIASING,
            Choice("bloom", "Bloom:", SCENE3D_EFFECT_CHOICES,
                   "Glow around sparks, hot edges and glowing cracks; the photographs never glow." + _AUTO_TIP),
            _unit("bloom_strength", "Bloom Strength:",
                  "How strongly sparks, hot edges and glowing cracks glow when Bloom is on."),
            _MOTION_BLUR,
            _MOTION_TRAILS,
        ),
    ),
    TransitionSettings(
        "Directional Pixel Accretion", "pixel_accretion", directions=_EIGHT_WAY,
        controls=(
            Number("tile_size", "Tile Size:", 4, 32, integer=True),
            Number("travel", "Travel:", 0.1, 1.0),
        ),
        advanced=_MOTION,
    ),
    TransitionSettings(
        "Melt Drip", "melt_drip",
        directions=Directions(MELT_ORIGINS, aliases={code: code for code in MELT_ORIGINS.values()}),
        controls=(
            Number("detail", "Detail:", 0.5, 2.0),
            _unit("depth", "Liquid Depth:", "Thickness and relief of the liquid sheet and falling drops."),
            _gloss("Reflections on the rounded liquid surfaces.", "Wet Gloss:"),
        ),
    ),
    TransitionSettings(
        "Beam", "beam", directions=_EIGHT_WAY,
        controls=(
            Colour("color", "Beam Colour:", "Choose Beam Colour",
                   "The colour of the beam and its glow; its core always burns white."),
            _unit("glow", "Glow:", "How far the beam's light reaches and how strongly it lights the picture."),
            _unit("scorch", "Scorch:", "How strongly the beam scorches the new picture before it cures clean."),
            _unit("cure", "Cure Time:", "How long the scorch takes to cure clean. A longer cure has the beam cross "
                                        "sooner, so the run still ends on the clean picture."),
            Toggle("sparks", "Sparks", "Sparks spraying from where the beam cuts the picture."),
        ),
    ),
    TransitionSettings(
        "Volumetric Dissolve", "volumetric_dissolve", directions=_choice_of(VOLUMETRIC_DIRECTIONS),
        controls=(
            Number("particle_size", "Particle Size:", *VOLUMETRIC_PARTICLE_SIZE_RANGE,
                   "Size of each particle in screen pixels. Very large screens use slightly bigger particles.",
                   integer=True, suffix=" px"),
            _unit("mist", "Mist:", "How much luminous mist, coloured by the old picture, rises as it dissolves."),
            _unit("depth", "Depth:", "How far the particles fly toward you, growing and blurring as they near."),
        ),
        advanced=(_ANTIALIASING,),
    ),
    TransitionSettings(
        "VHS Distortion", "vhs", directions=_choice_of(VHS_DIRECTIONS),
        controls=(
            _unit("tracking", "Tracking:", "How badly tracking is lost: jittering, swaying and tearing lines, and "
                                           "the bent top of each frame as the picture rolls."),
            _unit("bleed", "Colour Bleed:", "How far colour smears and lags behind the picture, with ringing edges, "
                                            "as on worn tape."),
            _unit("noise", "Noise:", "Snow, dropout streaks, scanlines and a drifting interference band."),
        ),
    ),
    TransitionSettings(
        "Edge Bloom Reveal", "edge_bloom",
        controls=(
            Choice("color_source", "Glow Colour:", EDGE_BLOOM_COLOUR_SOURCE_CHOICES,
                   "Custom: the colour you choose. Next Picture: every line glows in the next picture's most "
                   "vivid colour. Each Picture: each picture's lines glow in its own colour."),
            Colour("color", "Custom Colour:", "Choose Glow Colour",
                   "The colour of the glowing edges; the strongest lines burn toward white.",
                   enabled_when=("color_source", "Custom")),
            _unit("glow", "Glow:", "How brightly the edges and the growing fill glow."),
            _unit("detail", "Detail:", "How many edges light up: only the strongest outlines at 0, fine detail at 1."),
        ),
    ),
    TransitionSettings(
        "Liquid Lens", "liquid_lens",
        controls=(
            Number("stops", "Stops:", *LIQUID_LENS_STOPS_RANGE,
                   "Which stop the lens floods the picture from: it starts in the middle and grows at each stop "
                   "before it. 1 floods from the middle.", integer=True),
            _unit("refraction", "Refraction:", "How strongly the water bends the next picture: thin and clear at 0, "
                                               "a thick, magnifying lens at 1."),
            _unit("dispersion", "Colour Fringes:", "Rainbow fringes where the water's rim bends the light most. "
                                                   "Zero keeps the colours together."),
        ),
    ),
    TransitionSettings(
        "Membrane Turnover", "membrane", directions=_choice_of(MEMBRANE_SWEEPS),
        controls=(_gloss("Shine of the membrane and reflections of the next picture on it as it twists."),),
        advanced=(_ANTIALIASING,),
    ),
    TransitionSettings(
        "Surface Tension Merge", "surface_tension",
        controls=(
            Number("pools", "Pools:", *TENSION_POOLS_RANGE,
                   "How many pools of the next picture appear: a few large ones up to many small ones.", integer=True),
            _gloss("Light on the liquid where the two pictures meet: highlights and sheen along every edge."),
        ),
    ),
    TransitionSettings(
        "Chromatic Shear", "chromatic_shear", directions=_choice_of(SHEAR_DIRECTIONS),
        controls=(
            Number("slices", "Slices:", *SHEAR_SLICES_RANGE, "How many broad slices the picture shears into.",
                   integer=True),
            _unit("spread", "Spread:", "How far the slices shear apart and the colours fan out."),
        ),
    ),
    TransitionSettings(
        "Depth Card Cascade", "depth_cascade", directions=_choice_of(CASCADE_SWEEPS),
        controls=(
            Number("cards", "Cards:", *CASCADE_CARDS_RANGE, "How many cards the picture splits into.", integer=True),
            _gloss("Shine of the cards and reflections of the next picture on them as they tilt."),
            Toggle("shadows", "Shadows", "Soft shadows the lifting cards cast on the next picture."),
        ),
        advanced=(_ANTIALIASING,),
    ),
    TransitionSettings(
        "Capillary Bloom", "capillary_bloom",
        controls=(
            Number("sources", "Sources:", *CAPILLARY_SOURCES_RANGE, "How many drops of dye start the bloom.",
                   integer=True),
            _unit("fibres", "Fibres:", "How strongly the dye races along the paper's fibres: a smooth, round bloom "
                                       "at 0, branching tendrils at 1."),
        ),
    ),
    TransitionSettings(
        # The stored "direction" is the order the pieces flip in.
        "Jigsaw Piece Flip", "jigsaw", directions=_choice_of(JIGSAW_ORDERS),
        controls=(
            Number("pieces", "Pieces:", *JIGSAW_PIECES_RANGE,
                   "About how many pieces the picture is cut into. More pieces flip faster, more at once.",
                   integer=True),
        ),
        advanced=(_ANTIALIASING,),
    ),
    TransitionSettings(
        # The way the box turns: its front moves toward this side.
        "Cube Turn", "cube_turn", directions=_choice_of(CUBE_TURN_DIRECTIONS),
        controls=(_gloss("Shine and reflections of the next image on the turning box."),),
        advanced=(_ANTIALIASING,),
    ),
    TransitionSettings(
        "Disintegrate", "disintegrate", directions=_EIGHT_WAY,
        controls=(
            Number("grain_size", "Grain Size:", 2, 8,
                   "Size of each grain in screen pixels. Very large screens use slightly bigger grains.",
                   integer=True, suffix=" px"),
            Number("wind", "Wind:", 0.5, 2.0,
                   "How hard the wind blows the grains away: their speed and how far they fly."),
        ),
        advanced=(_ANTIALIASING,),
    ),
    TransitionSettings(
        # Where the page starts to peel: a corner or an edge.
        "Page Curl", "page_curl", directions=_choice_of(PAGE_CURL_ORIGINS),
        controls=(
            _unit("size", "Curl Size:", "How large the peeled sheet's roll grows: thin and tight up to a loose, "
                                        "wide curl."),
            _gloss("Shine of the laminated sheet and reflections of the next image on it."),
        ),
        advanced=(_ANTIALIASING,),
    ),
    TransitionSettings(
        # Flat and 3D Slats show different controls; the Edge Softness slider is the page's own.
        "Blinds", "blinds", custom=True, custom_fields=("feather",),
        controls=(
            Choice("style", "Style:", BLINDS_STYLE_CHOICES,
                   "Flat: soft bands open over the picture. 3D Slats: solid slats turn over one after another, "
                   "the next image on their backs."),
            Choice("direction", "Direction:", ("Horizontal", "Vertical", "Diagonal", "Random"),
                   "Horizontal: upright stripes. Vertical: lying stripes. 3D Slats turn only these two ways; "
                   "Diagonal or Random picks one of them per transition."),
            Number("slats", "Slats:", *BLINDS_SLATS_RANGE, "How many slats cover the picture.", integer=True),
            _gloss("Shine and reflections of the next image on the turning slats.", "Slat Gloss:"),
        ),
        advanced=(_ANTIALIASING,),
    ),
    TransitionSettings(
        "Crumble", "crumble",
        controls=(
            Number("piece_count", "Piece Count:", 4, 128, integer=True),
            Number("crack_complexity", "Crack Complexity:", 0.5, 2.0, step=0.1),
            # The former Bias labels both ran Top Weighted.
            Choice("weighting", "Weighting:",
                   ("Random Choice", "Top Weighted", "Bottom Weighted", "Random Weighted", "Age Weighted"),
                   aliases=MappingProxyType({"Bias Old Image": "Top Weighted", "Bias New Image": "Top Weighted"})),
            Toggle("collisions", "Slabs Collide",
                   "Falling slabs bounce off each other instead of passing through, and a standing slab struck by a "
                   "falling one is knocked loose."),
            Number("depth", "Collapse Depth:", 0.2, 1.5, "Out-of-plane movement and tumble of falling wall chunks."),
            _unit("thickness", "Wall Thickness:", "Thickness of the solid wall and its broken edges."),
            _unit("debris", "Crumbling Debris:", "Small solid fragments released around falling chunks. Zero "
                                                 "disables debris geometry and drawing."),
        ),
        advanced=_MOTION,
    ),
    TransitionSettings(
        # Mode-dependent controls, a light-direction list stored by index and fixed trail values.
        "Particle", "particle", custom=True,
        custom_fields=("mode", "direction", "particle_radius", "overlap", "trail_length", "trail_strength",
                       "swirl_strength", "swirl_turns", "use_3d_shading", "texture_mapping", "wobble",
                       "gloss_size", "light_direction", "swirl_order"),
    ),
    TransitionSettings(
        # Percentage sliders and colours with alpha.
        "Burn", "burn", custom=True,
        custom_fields=("direction", "jaggedness", "glow_intensity", "char_width", "glow_color", "ember_color",
                       "smoke_enabled", "smoke_density", "ash_enabled", "ash_density", "flames", "ember_veins"),
    ),
)

TRANSITION_SETTINGS: Mapping[str, TransitionSettings] = MappingProxyType({spec.name: spec for spec in _SPECS})
_BY_SECTION: Mapping[str, TransitionSettings] = MappingProxyType({spec.section: spec for spec in _SPECS})


def iter_transition_settings() -> tuple[TransitionSettings, ...]:
    return _SPECS


def transition_settings(name_or_section: str) -> TransitionSettings | None:
    """A transition's spec by setting name ("Liquid Lens") or section ("liquid_lens")."""
    return TRANSITION_SETTINGS.get(name_or_section) or _BY_SECTION.get(name_or_section)


def require_transition_settings(name_or_section: str) -> TransitionSettings:
    spec = transition_settings(name_or_section)
    if spec is None:
        raise KeyError(f"no Settings spec for transition {name_or_section!r}")
    return spec


__all__ = [
    "BLOCK_SPIN_DIRECTIONS",
    "Choice",
    "Colour",
    "Control",
    "Directions",
    "MELT_ORIGINS",
    "Number",
    "TRANSITION_SETTINGS",
    "Toggle",
    "TransitionSettings",
    "as_bool",
    "as_integer",
    "as_number",
    "iter_transition_settings",
    "require_transition_settings",
    "transition_settings",
    "widget_attr",
]
