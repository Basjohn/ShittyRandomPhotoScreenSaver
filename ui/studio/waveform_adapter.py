"""Waveform Ribbon's Studio adapter: schema, deterministic evaluator, fixtures, renderer.

Truthfulness: every preview frame comes from the production logical owner
(``WaveformRibbonFrameRuntime`` -> its own ``WaveformDynamics``, configured through
``CompiledWaveformSettings``) and is drawn by the production
``QuickWaveformRibbonRenderer``. The evaluator owns its *own* instances; it never
touches the desktop visualizer's runtime, history or GL objects. Synthetic fixtures
and recorded clips both feed the exact keyword inputs the production capture passes
to ``WaveformRibbonFrameRuntime.advance``.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Iterable, Mapping

from core.settings.visualizer_mode_settings import (
    Choice, Colour, Range, Slider, Toggle, VisualEditor, require_mode_settings,
)
from ui.studio.adapter import (
    RECORDED, REFERENCE, SYNTHETIC, RenderCard, StudioCapabilities, StudioFixture, StudioModeAdapter,
)
from ui.studio import clip_loop
from ui.studio.exact_replay import ExactReplay
from ui.studio.schema import (
    CHOICE, COLOUR, COUNT, GRADIENT, QUIET_PEAK, SCALAR, SWITCH, CardSpec, LifecycleSpec, SceneObject,
    RESPONSE_PANEL, StudioPreset, StudioProperty, StudioSchema, Workspace, WorkspaceColumn,
)

MODE = "waveform_ribbon"
PREFIX = "waveform_ribbon_"
STEP = 1.0 / 60.0            # synthetic logical step (s)
PREROLL = 1.5                # held first-input pre-roll so history is primed before t = 0

# Workspace and group placement of the canonical buckets (presentation only).
_BUCKET_PLACEMENT = {
    "ribbons": ("composition", "Ribbons"),
    "flow": ("composition", "Flow"),
    "shape": ("reactivity", "Shape Response"),
    "pulse": ("reactivity", "Energy Pulse"),
    "reaction": ("reactivity", "Timing"),
    "colour": ("appearance", "Colour"),
    "surface": ("appearance", "Sheet & Highlights"),
    "sparks": ("appearance", "Particles"),
    "strands": ("appearance", "Free Strands"),
    "mist": ("world", "Mist"),
    "floor": ("world", "Floor"),
    "lens": ("world", "Lens & Quality"),
    "camera": ("world", "Camera"),
}
# Flow-bucket values that describe musical roll/twist response rather than resting composition.
_ROLL_KEYS = frozenset(PREFIX + k for k in ("rotation_enabled", "rotation", "twist_speed",
                                            "rotation_attack", "rotation_release"))
# The dashboard (mock): each workspace's groups as side-by-side panels under the wide viewport.
_WORKSPACES = (
    Workspace("composition", "Composition", ("Ribbons", "{object}", "Flow"), icon="wave",
              open_groups=("Ribbons", "{object}", "Flow"),
              help="Lay out the ribbons: how many, how tall and wide, their spacing and phase, and how the waves flow.",
              columns=(WorkspaceColumn("Ribbon Shape", ("{object}",), "wave", "Selected ribbon", 1.2),
                       WorkspaceColumn("Global", ("Ribbons", "Flow"), "ribbons", "Every ribbon"))),
    Workspace("reactivity", "Reactivity", ("Energy Pulse", "Shape Response", "Roll & Twist", "Timing",
                                           "Routing Details", "Audio Analysis", "Advanced (Retired)"),
              open_groups=("Energy Pulse", "Shape Response", "Timing"), icon="bars",
              help="Decide how the music moves the scene: the travelling pulse, what each target listens to "
                   "(the Response Editor panel) and how quickly it reacts.",
              columns=(WorkspaceColumn("Reactivity", (RESPONSE_PANEL,), "bars", "Response Editor", 2.0),
                       WorkspaceColumn("Energy & Timing", ("Energy Pulse", "Shape Response", "Roll & Twist", "Timing",
                                                           "Routing Details", "Audio Analysis", "Advanced (Retired)"),
                                       "bolt",
                                       "Pulse, shape and timing"))),
    Workspace("appearance", "Appearance", ("Gradient Nodes", "Sheet & Highlights", "{object} Colours", "Colour",
                                           "Particles", "Free Strands"),
              open_groups=("Gradient Nodes", "Sheet & Highlights", "{object} Colours", "Particles", "Free Strands"),
              icon="palette",
              help="Colour and material: the quiet and peak palettes, sheet and highlight looks, particles and strands.",
              columns=(WorkspaceColumn("Ribbon Colours", ("Gradient Nodes", "{object} Colours", "Colour"), "palette",
                                       "Colours"),
                       WorkspaceColumn("Material", ("Sheet & Highlights",), "material", "Sheet & highlights"),
                       WorkspaceColumn("Particles & Strands", ("Particles", "Free Strands"), "dots", "Emitters"))),
    Workspace("world", "World", ("Mist", "Floor", "Lens & Quality", "Camera", "View"),
              open_groups=("Mist", "Floor", "Lens & Quality"), icon="cube",
              help="The world around the ribbons: mist, the reflective floor, lens and lighting, and the camera.",
              columns=(WorkspaceColumn("Mist", ("Mist",), "cloud", "Atmosphere"),
                       WorkspaceColumn("Floor", ("Floor",), "floor", "Floor & reflections"),
                       WorkspaceColumn("Lighting", ("Lens & Quality", "Camera", "View"), "sun", "Lens & camera"))),
)
# Row glyphs where a canonical icon exists (mock: an icon before each shape control).
_ROW_ICONS = {"height": "height", "width": "width", "rate": "wave", "phase": "clock", "light": "sun", "band": "bars",
              "count": "ribbons", "fog_density": "cloud", "floor_brightness": "floor", "floor_reflection": "drop",
              "exposure": "sun", "bloom": "sparkle", "reaction_mode": "bolt", "camera_fov": "lens",
              "sparks_enabled": "dots", "strands_enabled": "strand", "mist_enabled": "cloud",
              "pulse_direction": "flow", "travel_direction": "flow"}
_CAMERA_FIELDS = ("turn", "tilt", "scene_scale", "scene_pan_x", "scene_pan_y")
# Headline controls lead their group (operator, 5 Nov): mist density and the floor controls tuned most
# (surface, far surface, reflection, its contrast / ceiling / colour) come first; the reaction mode is the
# first decision in Reactivity. Everything else keeps registry order.
HEADLINE_FLOOR = ("floor_brightness", "floor_light_far", "floor_reflection", "floor_contrast",
                  "floor_glow_limit", "floor_colour")
# Direction is a basic need (operator, 5 Nov): Pulse Direction sits right under Reaction Mode and Travel Direction
# (when the registry has it) heads Flow, both visible without scrolling.
_PRIORITY = {PREFIX + key: rank for rank, key in enumerate((
    "reaction_mode", "pulse_direction", "travel_direction", "bend", "mist_enabled", "fog_density") + HEADLINE_FLOOR)}
# Material starting points (mock: Sheen / Glass / Satin / Crystal): scale the OPENING material values
# (both quiet and peak endpoints), clamped by the canonical ranges. Applying one replaces the previous
# one (always from the opening values) and is a single undoable edit; "Original" restores them.
_MATERIAL_SCALES = {
    # Wide enough to read as different materials at tile size (5 Nov: the first scales differed from Original by
    # 1-9 grey levels on a 192x128 tile, Crystal/Sheen barely at all).
    "sheen": {"material_body_alpha": .85, "material_fill_light": 1.9, "material_cross_curve": 1.6,
              "material_glow": 1.1, "material_rim_light": .85, "material_glint_light": .6},
    "glass": {"material_body_alpha": .25, "material_rim_light": 1.8, "material_rim_glow_light": 1.7,
              "material_fill_centre": .35, "material_glow": 1.4, "material_fill_light": .55},
    "satin": {"material_body_alpha": 1.8, "material_fill_light": 1.45, "material_rim_light": .5,
              "material_glint_light": .25, "material_glow": .6, "material_cross_curve": .6},
    "crystal": {"material_glint_density": 2.6, "material_glint_light": 2.3, "material_rim_white": 2.5,
                "material_strand_white": 2.0, "material_glow": 1.25, "material_body_alpha": .5},
}
MATERIAL_PRESETS = (
    StudioPreset("original", "Original", "The material the Studio opened with.", ("#5b5f7a", "#9aa0c8")),
    StudioPreset("sheen", "Sheen", "Brighter fill and a fuller curve: a soft satin sheen.", ("#4a64d8", "#c8d4ff")),
    StudioPreset("glass", "Glass", "Thin body, strong glowing rims: see-through glass.", ("#3a2a8a", "#e4dcff")),
    StudioPreset("satin", "Satin", "Denser body, softer rims and fewer glints.", ("#6a3aa0", "#b890e0")),
    StudioPreset("crystal", "Crystal", "Dense bright glints and whiter edges.", ("#2a6ad0", "#ffffff")),
)

# One line per reaction mode, matched by name so a reordered registry tuple stays correct.
_CHOICE_NOTES = {PREFIX + "reaction_mode": {
    "Travelling Pulse": "Music launches swells that travel along the waveform like waves on water.",
    "Frozen Past": "Each passage leaves its peak swell held on the cloth, carried along with the history.",
    "Whole Swell": "The whole waveform rises and settles together; direction, width and speed do not apply.",
    "Group Wave": "Each swell arrives as a set: several crests lift together, leaning toward the front.",
}, PREFIX + "travel_direction": {
    "Right To Left": "New history enters at the right and flows to the left.",
    "Left To Right": "New history enters at the left and flows to the right (the mirror image).",
}}
# Targets kept in data but no longer moving geometry (operator, 5 Nov): Advanced only, never in the tuner.
_RETIRED_TARGETS = frozenset({"stretch"})


def _label(text: str) -> str:
    return text.rstrip(":").strip()


def _card_limits() -> dict[str, tuple[float, float]]:
    """Ribbon card numeric bounds, read back from the canonical admission itself."""
    from core.settings.default_contract import require_canonical_default
    from core.waveform_ribbon_authoring import admit_ribbons
    cards = admit_ribbons(require_canonical_default("widgets.spotify_visualizer." + PREFIX + "ribbons"))

    def accepted(field: str, value: float) -> bool:
        try:
            admit_ribbons([{**cards[0], field: value}, *cards[1:]])
        except ValueError:
            return False
        return True

    def edge(field: str, inside: float, outside: float) -> float:
        # The admission is strict (it rejects, never clamps); bisect its accepted interval.
        for _ in range(80):
            middle = (inside + outside) / 2.0
            inside, outside = (middle, outside) if accepted(field, middle) else (inside, middle)
        return round(inside, 6)

    limits = {}
    for field in ("height", "width", "rate", "phase", "light"):
        start = float(cards[0][field])
        limits[field] = (edge(field, start, -1e6), edge(field, start, 1e6))
    return limits


from ui.studio.colour import display_hex, linear_from_hex  # noqa: E402  (re-exported for callers)


from ui.studio.technical import TECHNICAL_GROUP  # noqa: E402


def _technical_properties() -> dict:
    """The mode's technical (audio analysis) controls exactly as Settings' Technical group builds them."""
    from ui.studio.technical import technical_properties
    return technical_properties(MODE, workspace="reactivity")


def _condition(control) -> tuple:
    from ui.studio.adapter import control_condition
    return control_condition(control)


def build_schema() -> StudioSchema:
    spec = require_mode_settings(MODE)
    from core.waveform_ribbon_authoring import RIBBON_CAPACITY, SOURCES
    props: list[StudioProperty] = []
    # A bucket the Studio has not placed yet still appears (World, under its own title): new
    # canonical controls are never silently missing from the Studio.
    titles = {bucket.key: bucket.title for bucket in spec.buckets}
    extra_groups: list[str] = []
    for control in spec.body_controls:
        bucket = control.bucket
        if not bucket or isinstance(control, VisualEditor):
            continue  # routing / palette / ribbon cards get dedicated instruments below or in Stage C/D
        if bucket in _BUCKET_PLACEMENT:
            workspace, group = _BUCKET_PLACEMENT[bucket]
        else:
            workspace, group = "world", titles.get(bucket, bucket)
            if group not in extra_groups:
                extra_groups.append(group)
        if control.key in _ROLL_KEYS:
            workspace, group = "reactivity", "Roll & Twist"
        if control.key in {PREFIX + t for t in _RETIRED_TARGETS}:
            workspace, group = "reactivity", "Advanced (Retired)"
        label = _label(control.label) or _label(getattr(control, "text", "")) or control.key
        tooltip = getattr(control, "tooltip", "")
        common = dict(id=control.key, path=(control.key,), label=label, workspace=workspace, group=group,
                      tooltip=tooltip, priority=_PRIORITY.get(control.key, 100), when=_condition(control))
        if isinstance(control, Range):
            props.append(StudioProperty(instrument=QUIET_PEAK, minimum=control.low, maximum=control.high,
                                        decimals=0 if control.integer else control.decimals,
                                        units=control.suffix, integer=control.integer, **common))
        elif isinstance(control, Slider):
            props.append(StudioProperty(instrument=COUNT if control.key == PREFIX + "count" else SCALAR,
                                        minimum=control.low, maximum=control.high,
                                        decimals=0 if control.integer else control.decimals,
                                        units=control.suffix, integer=control.integer, **common))
        elif isinstance(control, Toggle):
            props.append(StudioProperty(instrument=SWITCH, **common))
        elif isinstance(control, Choice):
            notes = _CHOICE_NOTES.get(control.key, {})
            props.append(StudioProperty(instrument=CHOICE, choices=tuple(control.choices),
                                        choice_notes=tuple(notes.get(choice, "") for choice in control.choices)
                                        if notes else (), **common))
        elif isinstance(control, Colour):
            props.append(StudioProperty(instrument=COLOUR, **common))
    # Camera position: three normalized offsets of the shared framed-camera owner.
    position = spec.control(PREFIX + "camera_position")
    for index, axis in enumerate(("X", "Y", "Z")):
        props.append(StudioProperty(id=f"{position.key}.{index}", path=(position.key, index),
                                    label=f"Camera {axis}", workspace="world", group="Camera", instrument=SCALAR,
                                    minimum=-1.0, maximum=1.0, decimals=3,
                                    tooltip="Normalized camera offset; admitted by the shared framed camera."))
    # Live view pose (not body controls): previewed while navigating; turn/tilt are saved only when the
    # preset's camera checkbox includes the view, zoom/pan stay preview views.
    for field, label in (("turn", "Orbit Turn"), ("tilt", "Orbit Tilt"), ("scene_scale", "Zoom"),
                         ("scene_pan_x", "Pan X"), ("scene_pan_y", "Pan Y")):
        control = spec.control(PREFIX + field)
        props.append(StudioProperty(id=control.key, path=(control.key,), label=label, workspace="world",
                                    group="View", instrument=SCALAR, minimum=control.low,
                                    maximum=control.high, decimals=3, view_pose=True,
                                    tooltip="Preview view. Drag the viewport to orbit. Orbit is saved only when "
                                            "the preset's camera checkbox includes the view."))
    # Colour gradient nodes (quiet and peak): one strip each, draggable nodes + picker (1..6 nodes).
    palette_key = PREFIX + "palette"
    for side, side_label in (("low", "Quiet Gradient"), ("high", "Peak Gradient")):
        props.append(StudioProperty(id=f"{palette_key}.{side}", path=(palette_key, side), label=side_label,
            workspace="appearance", group="Gradient Nodes", instrument=GRADIENT, minimum=1, maximum=6,
            colour_format="linear01", priority=10 if side == "low" else 11,
            tooltip="World colour gradient. Drag a node to move it, click to pick its colour, "
                    "double-click the strip to add a node; nodes stay ordered."))
    # Per-ribbon cards: one inspector per selected ribbon.
    limits = _card_limits()
    bands = ("All", *SOURCES[:3])
    for index in range(RIBBON_CAPACITY):
        scope = f"ribbon{index}"
        key = PREFIX + "ribbons"
        def card(field, label, instrument, group="{object}", workspace="composition", **extra):
            props.append(StudioProperty(id=f"{key}[{index}].{field}", path=(key, index, *field.split(".")),
                                        label=label, workspace=workspace, group=group, instrument=instrument,
                                        object_scope=scope, targets=(scope,), **extra))
        card("band", "Band", CHOICE, choices=bands, tooltip="Which musical band this ribbon follows.")
        for field, label, units in (("height", "Height", ""), ("width", "Width", ""),
                                    ("rate", "Wave Spacing", ""), ("phase", "Phase Offset", " rad"),
                                    ("light", "Light", "")):
            low, high = limits[field]
            card(field, label, SCALAR, minimum=low, maximum=high, units=units)
        for side, side_label in (("quiet", "Quiet"), ("peak", "Peak")):
            for slot, slot_label in ((0, "Centre"), (1, "Edge")):
                props.append(StudioProperty(
                    id=f"{key}[{index}].{side}.{slot}", path=(key, index, side, slot),
                    label=f"{side_label} {slot_label}", workspace="appearance", group="{object} Colours",
                    instrument=COLOUR, object_scope=scope, targets=(scope,), colour_format="linear01",
                    tooltip="Linear-light ribbon colour, shown and entered as a display colour."))

    props = [dataclasses.replace(p, icon=_ROW_ICONS.get(p.id.rsplit(".", 1)[-1] if "[" in p.id
                                                        else p.id[len(PREFIX):], ""))
             if not p.icon else p for p in props]
    technical = _technical_properties()
    props.extend(prop for prop, _defn in technical.values())
    controls = {control.key: control for control in spec.controls}

    def admit(key: str, candidate: Any, previous: Any) -> Any:
        if key in technical:
            from ui.studio.technical import admit_technical
            return admit_technical(technical[key], candidate, previous)
        return controls[key].admit(candidate, previous)

    response = _response_model(spec, props)
    workspaces = tuple(dataclasses.replace(w, groups=w.groups + tuple(extra_groups)) if w.id == "world" else w
                       for w in _WORKSPACES)
    return StudioSchema(MODE, "Waveform Studio", workspaces, tuple(props), admit, response=response,
                        group_traces=(("Energy Pulse", ("Input Energy", "Travelling Pulse")),
                                      ("Shape Response", ("Passage", "Height", "Pulse Strength"))),
                        group_icons=(("Ribbons", "ribbons"), ("{object}", "wave"), ("Flow", "flow"),
                                     ("Energy Pulse", "bolt"), ("Shape Response", "height"),
                                     ("Roll & Twist", "roll"), ("Timing", "clock"), ("Routing Details", "grid"),
                                     ("Advanced (Retired)", "grid"), ("{object} Colours", "colour"),
                                     ("Colour", "palette"), ("Gradient Nodes", "gradient"),
                                     ("Sheet & Highlights", "material"), ("Particles", "dots"),
                                     ("Free Strands", "strand"), ("Mist", "cloud"), ("Floor", "floor"),
                                     ("Lens & Quality", "sun"), ("Camera", "camera"), ("View", "view")),
                        object_noun="Ribbon",
                        group_presets=(("Sheet & Highlights", MATERIAL_PRESETS),),
                        lifecycles=(LifecycleSpec("Particles", PREFIX + "spark_lifetime", label="Particle life"),
                                    LifecycleSpec("Free Strands", PREFIX + "strand_eol", PREFIX + "strand_fade",
                                                  PREFIX + "strand_peel", label="Strand life")),
                        cards=(CardSpec("Mist", "falloff", (("density", PREFIX + "fog_density"),
                                                            ("height", PREFIX + "fog_height"),
                                                            ("clearance", PREFIX + "fog_clearance"),
                                                            ("softness", PREFIX + "fog_softness"),
                                                            ("enabled", PREFIX + "mist_enabled")),
                                        "Atmosphere", rendered=True),
                               CardSpec("Floor", "reflection", (("brightness", PREFIX + "floor_brightness"),
                                                                ("reflection", PREFIX + "floor_reflection"),
                                                                ("wetness", PREFIX + "floor_wetness"),
                                                                ("streak", PREFIX + "floor_streak"),
                                                                ("tint", PREFIX + "floor_tint")),
                                        "Floor & reflections", rendered=True),
                               CardSpec("Lens & Quality", "exposure", (("exposure", PREFIX + "exposure"),
                                                                       ("bloom", PREFIX + "bloom")),
                                        "Lighting"),
                               CardSpec("Particles", "particles", (("enabled", PREFIX + "sparks_enabled"),
                                                                  ("count", PREFIX + "spark_count"),
                                                                  ("lifetime", PREFIX + "spark_lifetime"),
                                                                  ("drift", PREFIX + "spark_drift"),
                                                                  ("rise", PREFIX + "spark_rise"),
                                                                  ("size", PREFIX + "spark_size"),
                                                                  ("glow", PREFIX + "spark_glow"),
                                                                  ("white", PREFIX + "spark_white"),
                                                                  ("span", PREFIX + "spark_span"),
                                                                  ("palette", PREFIX + "palette.high")),
                                        "Particles (peak)"),
                               CardSpec("Free Strands", "strands", (("enabled", PREFIX + "strands_enabled"),
                                                                    ("count", PREFIX + "strand_count"),
                                                                    ("length", PREFIX + "strand_length"),
                                                                    ("reach", PREFIX + "strand_reach"),
                                                                    ("width", PREFIX + "strand_width"),
                                                                    ("beads", PREFIX + "strand_beads"),
                                                                    ("glow", PREFIX + "strand_glow"),
                                                                    ("palette", PREFIX + "palette.high")),
                                        "Free strands (peak)")))


# What each routed target does, in plain words (the tuner's subtitle).
_TARGET_NOTES = {
    "height": "How tall the carrier waves stand.", "width": "How wide each ribbon sheet opens.",
    "bend": "Strength of the travelling energy pulse swells.", "torsion": "Elastic twisting of the sheet.",
    "twist": "Rate of the local rolling twist.", "stretch": "Elastic stretch along the ribbon.",
    "lift": "Whole-ribbon vertical lift.", "spread": "Separation between ribbons.",
    "depth": "Sway toward and away from the camera.", "rotation": "Speed of the whole-waveform axial roll.",
    "light": "Musical brightness of the sheet.", "sparkle": "How readily particles are admitted.",
    "colour": "Shift from quiet toward peak colours.", "highlights": "Packing of local crest highlights.",
}


def _routing_bounds() -> tuple[tuple[float, float], tuple[float, float]]:
    """Gain and curve-power bounds, read back from the canonical (strict) routing admission."""
    from core.settings.default_contract import require_canonical_default
    from core.waveform_ribbon_authoring import TARGETS, admit_routing
    routing = admit_routing(require_canonical_default("widgets.spotify_visualizer." + PREFIX + "routing"))

    def accepted(slot: int, value: float) -> bool:
        trial = {key: [list(cell) for cell in row] for key, row in routing.items()}
        trial[TARGETS[0]][0][slot] = value
        try:
            admit_routing(trial)
        except ValueError:
            return False
        return True

    def edge(slot: int, inside: float, outside: float) -> float:
        for _ in range(80):
            middle = (inside + outside) / 2.0
            inside, outside = (middle, outside) if accepted(slot, middle) else (inside, middle)
        return round(inside, 6)

    gain, power = (float(v) for v in routing[TARGETS[0]][0])
    return (edge(0, gain, -1e6), edge(0, gain, 1e6)), (edge(1, power, -1e6), edge(1, power, 1e6))


def _response_model(spec, props: list):
    """The routing matrix as a provider-driven target x source model (cells become session properties)."""
    from core.waveform_ribbon_authoring import SOURCES, TARGETS
    from ui.studio.schema import ResponseCell, ResponseSource, ResponseTarget, StudioResponse
    gain_bounds, power_bounds = _routing_bounds()
    key = PREFIX + "routing"
    labels = {control.key: _label(control.label) for control in spec.controls}
    sources = tuple(ResponseSource(f"s{index}", name) for index, name in enumerate(SOURCES))
    targets = []
    for target in TARGETS:
        label = labels.get(PREFIX + target, target.title())
        retired = target in _RETIRED_TARGETS
        cells = []
        for index, source in enumerate(sources):
            gain_id, power_id = f"{key}.{target}.{index}.gain", f"{key}.{target}.{index}.power"
            for pid, slot, bounds, what in ((gain_id, 0, gain_bounds, "gain"), (power_id, 1, power_bounds, "curve")):
                props.append(StudioProperty(id=pid, path=(key, target, index, slot),
                    label=f"{label} · {source.label} {what}", workspace="reactivity", group="Routing Details",
                    instrument=SCALAR, minimum=bounds[0], maximum=bounds[1], decimals=2, instrument_only=True))
            cells.append(ResponseCell(source.id, gain_id, power_id))
        if retired:
            continue           # cells stay editable in Routing Details; the tuner shows live targets only
        targets.append(ResponseTarget(target, label, _TARGET_NOTES.get(target, ""), tuple(cells),
                                      range_property=PREFIX + target if PREFIX + target in labels else ""))
    timing = tuple(PREFIX + k for k in ("attack", "release", "breathing", "elastic_frequency", "damping", "impulse")
                   if PREFIX + k in labels)
    return StudioResponse(sources, tuple(targets), gain_bounds, power_bounds, timing,
                          "Attack and decay are shared by every target in this mode.",
                          (("Gentle", 2.0), ("Smooth", 1.4), ("Linear", 1.0), ("Punchy", .6)))


# --------------------------------------------------------------------------- inputs
@dataclass(frozen=True)
class AdvanceInput:
    """Exactly the keyword inputs production capture passes to the frame runtime."""

    now: float
    playing: bool
    onsets: tuple
    body_bands: tuple[float, float, float]
    intensity: float
    loudness: float
    presence: float
    identity: tuple = (0, 1, 1)
    source_identity: tuple = (1, 1)


# Band envelope a typed beat adds to the body lanes: (lane shares, size, decay seconds). A beat is a short
# rise of body energy plus a typed onset, the two things production turns into hits and travelling pulses.
_BEAT_SHAPE = {"kick": ((1.0, .25, .05), .2, .12), "snare": ((.2, 1.0, .35), .16, .1),
               "vocal_swell": ((.1, .35, 1.0), .14, .4)}
# Onset magnitudes cycle so the runtime's accent contrast (against a running mean) stays musical.
_ACCENTS = (1.0, .55, .8, .45)


def _calibrated(position: float):
    """Body bands and passage at a position inside the dynamics' fixed real-music anchors (0 = p05, 1 = p95).

    Read from those anchors so fixtures follow their calibration. Measured against four pooled recordings
    (5 Nov, Preset 1): the published passage at positions .3 / .6 / .75 sits at the real p10 / p50 / p92."""
    from core.waveform_ribbon_dynamics import BAND_SPAN, PASSAGE_SPAN
    f = max(0., min(1., position))
    bands = tuple(low + (high - low) * f for low, high in BAND_SPAN)
    return bands, PASSAGE_SPAN[0] + (PASSAGE_SPAN[1] - PASSAGE_SPAN[0]) * f


def _beats(period: float, start: float, end: float, kind: str, strength: float, offset: int = 0):
    count = int((end - start) / period) + 1
    return [(start + i * period, kind, strength * _ACCENTS[(i + offset) % len(_ACCENTS)]) for i in range(count)]


def _groove(position, loudness, presence, beats, *, level=lambda _t: 1.0, lanes=(1., 1., 1.)):
    """A passage held at ``position`` (scaled per lane / over time by ``level``) plus its beat envelopes."""
    def signal(t):
        bands, passage = _calibrated(position)
        k = level(t)
        out = [b * share * k for b, share in zip(bands, lanes)]
        for when, kind, magnitude in beats:
            if when <= t:
                shares, size, decay = _BEAT_SHAPE[kind]
                envelope = size * min(1., magnitude) * math.exp(-(t - when) / decay)
                out = [v + envelope * share for v, share in zip(out, shares)]
        return tuple(min(1., v) for v in out), passage * k, loudness * k, presence * min(1., .4 + .6 * k)
    return signal


# Each fixture: (label, kind, description, signal(t) -> (bands, intensity, loudness, presence),
#                onsets: [(time, kind, magnitude)])
def _synthetic_table():
    duration = 10.0
    quiet_beats = _beats(1.0, .3, duration, "kick", .5)
    mid_beats = _beats(.5, .1, duration, "kick", 1.4) + _beats(1.0, .35, duration, "snare", 1.0, 1)
    peak_beats = (_beats(.45, .05, duration, "kick", 2.4) + _beats(.9, .275, duration, "snare", 1.8, 2)
                  + _beats(1.8, .6, duration, "vocal_swell", 1.2))
    bass_beats = _beats(.6, 0., duration, "kick", 1.8)
    mid_lane = _beats(.8, .2, duration, "snare", 1.6)
    high_lane = _beats(1.25, 0., duration, "vocal_swell", 1.4)
    hits = [(3., "kick", 2.6), (6.5, "snare", 2.4)]
    decay_beats = _beats(.5, .1, 2., "kick", 2.0)

    def decaying(t):
        return 1. if t < 2. else math.exp(-(t - 2.) / 1.5)

    return {
        "quiet": ("Quiet", REFERENCE, "A soft passage (published passage at the real-music p10) with light beats.",
                  _groove(.3, 5., .9, quiet_beats), quiet_beats),
        "mid": ("Mid", REFERENCE, "An ordinary passage (real-music p50) at 120 BPM with kicks and snares.",
                _groove(.6, 8.5, 1., mid_beats), mid_beats),
        "peak": ("Peak", REFERENCE, "A hot passage (real-music p92) with strong typed beats.",
                 _groove(.75, 12., 1.05, peak_beats), peak_beats),
        "bass": ("Bass Pulses", SYNTHETIC, "Bass band and kicks alone.",
                 _groove(.3, 9., 1., bass_beats, lanes=(1., .3, .3)), bass_beats),
        "mids": ("Mid Pulses", SYNTHETIC, "Mid band and snares alone.",
                 _groove(.3, 9., 1., mid_lane, lanes=(.3, 1., .3)), mid_lane),
        "highs": ("High Shimmer", SYNTHETIC, "High band and vocal swells alone.",
                  _groove(.3, 8.5, 1., high_lane, lanes=(.3, .3, 1.)), high_lane),
        "transient": ("Hit Over Loud Bed", SYNTHETIC, "A loud held bed (about p85) with two isolated hits.",
                      _groove(.7, 12., 1., hits), hits),
        "sustained": ("Sustained Intensity", SYNTHETIC, "Rises to a long held hot passage, no hits.",
                      _groove(.75, 12., 1.05, [], level=lambda t: min(1., .15 + .85 * t / 2.)), []),
        "decay": ("Decay To Silence", SYNTHETIC, "A hot beat that releases to silence.",
                  _groove(.75, 12., 1.05, decay_beats, level=decaying), decay_beats),
    }, duration


class SyntheticInputs:
    """Deterministic advance inputs for one synthetic/reference fixture."""

    def __init__(self, fixture_id: str) -> None:
        table, duration = _synthetic_table()
        if fixture_id not in table:
            raise KeyError(fixture_id)
        label, kind, description, signal, onsets = table[fixture_id]
        self.fixture = StudioFixture(fixture_id, label, kind, duration, description)
        self._signal = signal
        self._onsets = sorted(onsets)

    def steps(self, until: float) -> Iterable[AdvanceInput]:
        """Inputs from the pre-roll through ``until`` (inclusive of its step)."""
        from widgets.spotify_visualizer.transient_bus import MusicalOnset
        serial = 0
        first = -int(round(PREROLL / STEP))
        last = int(math.floor(until / STEP + 1e-9))
        for k in range(first, last + 1):
            t = k * STEP
            bands, intensity, loudness, presence = self._signal(max(0., t))
            onsets = []
            if t > 0.:
                for when, kind, magnitude in self._onsets:
                    if t - STEP < when <= t:
                        serial += 1
                        onsets.append(MusicalOnset(serial=serial, timestamp=when, kind=kind,
                                                   strength=min(1., magnitude / 3.), magnitude=magnitude,
                                                   loudness=loudness, presence=presence))
            yield AdvanceInput(now=t, playing=True, onsets=tuple(onsets),
                               body_bands=tuple(float(b) for b in bands), intensity=float(intensity),
                               loudness=float(loudness), presence=float(presence))


class RecordedInputs:
    """Advance inputs extracted from a recording by the production replay (see waveform_recorded_inputs)."""

    def __init__(self, fixture: StudioFixture, steps: tuple[AdvanceInput, ...], origin: float,
                 period: float = 0.0) -> None:
        self.fixture = fixture
        self._steps = steps
        self._origin = origin      # first source time whose frame is ready; Studio time 0
        self.period = float(period)        # > 0: a seamless loop (``ui/studio/clip_loop.py``)
        serials = [o.serial for step in steps if step.now >= origin - 1e-9 for o in step.onsets]
        self._span = clip_loop.onset_span(serials, (min(serials) - 1) if serials else 0)

    def shifted(self, step, cycle: int):
        """``step`` ``cycle`` whole passes on (times moved, onset serials kept increasing)."""
        return clip_loop.shift_advance(step, cycle * self.period, cycle * self._span)

    def steps(self, until: float) -> Iterable[AdvanceInput]:
        limit = self._origin + until + 1e-9
        for step in self._steps:
            if step.now > limit:
                return
            yield step


# ------------------------------------------------------------------------- evaluator
def camera_parameters(values: Mapping[str, Any]) -> dict[str, Any]:
    """The compact view fields the production capture hands the renderer."""
    return {key: value for key, value in values.items()
            if key.startswith(PREFIX + "camera_") or key in tuple(PREFIX + f for f in _CAMERA_FIELDS)}


def _logical_values(values: Mapping[str, Any]) -> dict[str, Any]:
    from widgets.spotify_visualizer.waveform_ribbon_capture import _CAMERA_KEYS
    spec = require_mode_settings(MODE)
    return {control.key: values[control.key] for control in spec.body_controls
            if control.key in values and control.key not in _CAMERA_KEYS}


def build_frame(configuration, snapshot, values: Mapping[str, Any]):
    """Production capture's frame construction (minus the live view-orbit motion).

    Every frame field the logical snapshot publishes under the same name is carried
    over, so a field added to both (as capture does) needs no Studio change."""
    from dataclasses import fields
    from widgets.spotify_visualizer.render_state import WaveformRibbonFrame, freeze_render_fields
    kwargs = {}
    for field in fields(WaveformRibbonFrame):
        if field.name == "scene":
            kwargs["scene"] = configuration.scene(snapshot)
        elif field.name == "parameters":
            kwargs["parameters"] = freeze_render_fields(camera_parameters(values))
        elif hasattr(snapshot, field.name):
            kwargs[field.name] = getattr(snapshot, field.name)
    return WaveformRibbonFrame(**kwargs)


def advance_options(runtime, values: Mapping[str, Any], extent=None) -> dict[str, Any]:
    """Optional production advance inputs derived from settings (and the presented card ``extent``), when this
    runtime accepts them."""
    import inspect
    accepted = inspect.signature(runtime.advance).parameters
    options = {}
    if "dynamic_zoom" in accepted:
        options["dynamic_zoom"] = bool(values.get(PREFIX + "dynamic_zoom", False))
    if "zoom_hold" in accepted:
        options["zoom_hold"] = False     # the Studio's preview orbit is not a live camera operation
    if "view_span" in accepted:
        # As the production capture: the scene-axis span the presented card's camera shows (pulse birth edge); with
        # no extent, the canonical card production uses until a CUSTOM edge drag commits one.
        from core.waveform_ribbon_view import card_span
        from widgets.spotify_visualizer.presentation_geometry import CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
        options["view_span"] = card_span(camera_parameters(values), extent or CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
                                         CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[1])
    return options


class _RuntimeCheckpoint:
    """The Waveform frame runtime's step state (``replay_engine.StepState`` over the runtime itself) and the
    configuration it was stepped with; the compiled configuration is shared, not copied."""

    def __init__(self, evaluator: "WaveformStudioEvaluator") -> None:
        from ui.studio.replay_engine import StepState
        self._evaluator = evaluator
        self._configuration, self._options = evaluator._configuration, dict(evaluator._options)
        self._state = StepState(None, keep=(evaluator._configuration,), owners=(evaluator._runtime,))

    def restore(self) -> None:
        self._state.restore()
        self._evaluator._configuration, self._evaluator._options = self._configuration, dict(self._options)


def _signature(logical: Mapping[str, Any], options: Mapping[str, Any]) -> str:
    """What the logical history depends on: the logical values and the advance options (view span, zoom)."""
    import json
    return json.dumps([logical, options], sort_keys=True, default=repr)


class WaveformStudioEvaluator(ExactReplay):
    """Own runtime + own dynamics, stepped deterministically through one fixture's inputs. The exact history, its
    checkpoints and the frame budget are the shared ``ui.studio.exact_replay.ExactReplay``: a commit replays from the
    latest checkpoint of its values (else the fixture start) within the Studio's frame budget, the last frame shown
    staying on screen until the exact replay lands."""

    def __init__(self) -> None:
        table, _duration = _synthetic_table()
        self._builtin = tuple(SyntheticInputs(key).fixture for key in table)
        self._recorded: dict[str, RecordedInputs] = {}
        self._inputs: SyntheticInputs | RecordedInputs = SyntheticInputs("mid")
        self._runtime = None
        self._configuration = None
        self._options: dict = {}
        self._resolved = None              # (logical values, advance options, signature) of ``_revision``
        self._revision = None
        self._origin = 0.0
        self._presented = None             # the logical snapshot of the frame shown (``restyle`` re-presents it)
        # Production always has a card extent (the canonical baseline until a CUSTOM edge drag commits one).
        from widgets.spotify_visualizer.presentation_geometry import CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
        self._extent = tuple(float(v) for v in CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE)
        self.steps_run = 0
        self.rewinds = 0
        self._shown = None
        self._reset_history()

    def set_viewport_extent(self, extent) -> None:
        """The card world extent the frame is presented at: the pulse is born at that camera's visible edge (as the
        production capture reads the card's committed extent), so a new extent replays the history at it."""
        if extent is None:
            from widgets.spotify_visualizer.presentation_geometry import CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
            extent = CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
        extent = (float(extent[0]), float(extent[1]))
        if extent != self._extent:
            self._extent = extent
            self._restart()

    def fixtures(self) -> tuple[StudioFixture, ...]:
        return self._builtin + tuple(item.fixture for item in self._recorded.values())

    @property
    def fixture(self) -> StudioFixture:
        return self._inputs.fixture

    def add_recorded(self, inputs: RecordedInputs) -> None:
        self._recorded[inputs.fixture.id] = inputs

    def select(self, fixture_id: str) -> StudioFixture:
        if fixture_id in self._recorded:
            self._inputs = self._recorded[fixture_id]
        else:
            self._inputs = SyntheticInputs(fixture_id)
        self._restart()
        self._shown = self._presented = None
        return self.fixture

    def _restart(self) -> None:
        """A new history (lifecycle: a new fixture or extent); the frame shown stays until the replay lands."""
        if self._runtime is not None:
            self._runtime.retire()
        self._runtime = None
        self._configuration = None
        self._resolved = self._revision = None
        self._reset_history()

    # replay hooks (ExactReplay) ------------------------------------------------
    def _tick_time(self, step: AdvanceInput) -> float:
        return step.now - self._origin

    def _configure(self) -> None:
        logical, options, _signature_ = self._resolved
        self._configuration = self._runtime.configure(logical)
        self._options = options

    def _step(self, step: AdvanceInput, onsets=None) -> None:
        self._last = self._runtime.advance(
            onsets=step.onsets if onsets is None else onsets, now_ts=step.now, playing=step.playing,
            identity=step.identity, source_identity=step.source_identity, controls=self._configuration.controls,
            body_bands=step.body_bands, intensity=step.intensity, loudness=step.loudness, presence=step.presence,
            **self._options)
        self._last_tick = step
        self.steps_run += 1

    def _restep(self) -> None:
        # Production's live-edit behaviour: the new controls re-publish the current step (dt = 0, no onsets).
        self._step(self._last_tick, onsets=())

    def _capture(self) -> _RuntimeCheckpoint:
        return _RuntimeCheckpoint(self)

    def _rewind_to_start(self, values: Mapping[str, Any], signature) -> None:
        self._runtime.reset()              # the production runtime's own reset: the state of a new runtime
        self._configure()
        self._signature = signature

    def _restyle(self, values: Mapping[str, Any], signature=None) -> None:
        self._configure()
        self._signature = signature

    def _can_pause(self) -> bool:
        return self._shown is not None or (self._last is not None and self._last.ready)

    def _present(self, values: Mapping[str, Any]):
        if self._last is None:
            raise RuntimeError("Fixture produced no logical step")
        if not self._last.ready:
            raise RuntimeError("Waveform history is not primed at this time; extend the fixture pre-roll")
        self._presented = self._last
        return build_frame(self._configuration, self._last, values)

    def evaluate(self, time: float, values: Mapping[str, Any], *, exact: bool = True, revision: Any = None):
        """The frame ``time`` seconds into the fixture under ``values``.

        ``exact`` (the default): the production runtime replayed from the fixture start with
        these values (from a checkpoint of them when one is at or before ``time``), so equal
        fixture/values/time always give equal bytes; with a frame budget the replay may take
        several evaluations (``converging``), the last frame shown staying meanwhile.
        ``exact=False`` is the live-gesture path: a values change re-publishes the current step
        with the new controls (production's live-edit behaviour: dt = 0, no time moves) instead
        of a replay. ``revision``: an optional caller token that changes whenever ``values``
        change; an equal token skips re-deriving the configuration (the per-frame cost while playing)."""
        deadline = self._deadline()
        time = self._history_time(time)
        fresh = self._runtime is None
        if fresh:
            from widgets.spotify_visualizer.waveform_ribbon_frame_runtime import WaveformRibbonFrameRuntime
            self._runtime = WaveformRibbonFrameRuntime()
            self._ticks = clip_loop.unrolled_ticks(self._inputs, self.fixture.duration)
            self._origin = getattr(self._inputs, "_origin", 0.0)
        if revision is None or revision != self._revision or self._resolved is None:
            logical = _logical_values(values)
            options = advance_options(self._runtime, values, self._extent)
            self._resolved = (logical, options, _signature(logical, options))
            self._revision = revision
        signature = self._resolved[2]
        if fresh:
            self._configure()
            self._signature = signature
        return self._replay(time, values, signature, exact=exact, deadline=deadline)

    def restyle(self, values: Mapping[str, Any]):
        """The instant last evaluated, re-presented under other ``values`` without stepping or replaying:
        the production scene construction (``CompiledWaveformSettings.scene``) applied to the same logical
        snapshot. Truthful for render-side controls (world, material, colour); None before any evaluation."""
        from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings
        shown = self._presented
        if shown is None or not shown.ready:
            return None
        return build_frame(CompiledWaveformSettings(_logical_values(values)), shown, values)

    def timeline(self, samples: int = 240) -> list[float]:
        """The selected input's energy over its duration (0..1), for the transport's scrub track."""
        from core.waveform_ribbon_dynamics import ENERGY_WEIGHTS
        duration = max(1e-6, self.fixture.duration)
        origin = getattr(self._inputs, "_origin", 0.0)
        levels = [0.0] * samples
        for step in self._inputs.steps(duration):
            t = step.now - origin
            if t < 0.0:
                continue
            index = min(samples - 1, int(t / duration * samples))
            energy = sum(w * b for w, b in zip(ENERGY_WEIGHTS, step.body_bands))
            levels[index] = max(levels[index], energy + (.25 if step.onsets else 0.0))
        peak = max(levels) or 1.0
        return [round(v / peak, 4) for v in levels]

    def measurements(self) -> dict[str, dict[str, float]]:
        """Read-only live values of the evaluator's own model at the current instant.

        ``sources``/``targets`` are keyed like the response model (source ids, target ids);
        ``signals`` are the named trace channels the schema places beside inspector groups."""
        model = getattr(self._runtime, "_model", None) if self._runtime is not None else None
        if model is None or not model.ready:
            return {"sources": {}, "targets": {}, "signals": {}}
        from core.waveform_ribbon_dynamics import ENERGY_WEIGHTS
        bands = tuple(float(v) for v in model.bands)
        sources = (*bands, float(model.power), float(getattr(model, "_hit", 0.)), .5 + .5 * math.sin(model.phase))
        drives = {key: float(value) for key, value in model.drive.items()}
        signals = {"Input Energy": sum(w * v for w, v in zip(ENERGY_WEIGHTS, bands)),
                   "Passage": float(model.passage), "Height": drives.get("height", 0.),
                   "Pulse Strength": drives.get("bend", 0.)}
        pulse_at = getattr(model, "pulse_at", None)
        if callable(pulse_at):
            from core.waveform_ribbon_dynamics import PULSE_GRID, PULSE_SATURATION
            signals["Travelling Pulse"] = float(max(0., float(pulse_at(PULSE_GRID).max())) / PULSE_SATURATION)
        return {"sources": {f"s{i}": float(v) for i, v in enumerate(sources)}, "targets": drives,
                "signals": signals}

    def release(self) -> None:
        if self._runtime is not None:
            self._runtime.retire()
        self._runtime = self._configuration = self._shown = self._presented = None
        self._reset_history()


# ------------------------------------------------------------------ presentation + handles
def studio_presentation(logical_size, extent, style):
    """The production presentation of the presented card extent at a Studio frame size.

    Same resolver and uniform-scale rule as the display owner, so ``framed_aperture_scale`` (lens aperture,
    edge-resize reveal/crop) is production's. Shared by the renderer and the handle projection."""
    from ui.studio.framed import presentation
    return presentation(MODE, logical_size, extent, style)


def frame_camera(frame, size, extent, style):
    """(clip-from-world matrix, aperture) exactly as the production renderer would draw ``frame``."""
    import numpy as np
    from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
    from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale
    width, height = size
    aperture = framed_aperture_scale(studio_presentation(size, extent, style), content=True)
    parameters = frame.parameters
    view, projection, _eye, _lens = physical_view(parameters, width / height, aperture,
                                                  zoom=float(getattr(frame, "zoom", 1.0)))
    return np.asarray(projection) @ np.asarray(view), aperture


def ribbon_world_points(frame, index):
    """World (x, y, z, half_width) of one ribbon's published knots, in axial order."""
    import numpy as np
    from core.ribbon_packet import KNOT_ROWS
    from core.waveform_ribbon_authoring import RIBBON_CAPACITY
    packet = frame.packet
    if not packet.payload:
        return np.empty((0, 4))
    data = np.frombuffer(packet.payload, np.float32).reshape(RIBBON_CAPACITY, -1, 4)
    path = data[index]
    count, start, capacity = int(path[0, 0]), int(path[1, 1]), int(path[1, 2])
    if count < 4 or capacity <= 0:
        return np.empty((0, 4))
    knots = path[4:].reshape(-1, KNOT_ROWS, 4)[(start + np.arange(count)) % capacity]
    origin = packet.world_origin
    # History axis -> world: Travel Direction mirrors x (Flow.direction, the renderer's one sign).
    x = (knots[:, 0, 0] + origin[0] + frame.scene.flow.head_x - frame.travel)*frame.scene.flow.direction
    return np.stack((x, knots[:, 0, 1] + origin[1], knots[:, 0, 2] + origin[2], knots[:, 0, 3]), axis=1)


def _project(matrix, points, size):
    import numpy as np
    homogeneous = np.c_[points[:, :3], np.ones(len(points))]
    clip = homogeneous @ matrix.T
    w = clip[:, 3:4]
    ndc = clip[:, :3] / np.where(np.abs(w) < 1e-9, 1e-9, w)
    screen = np.c_[(ndc[:, 0] + 1.0) * .5 * size[0], (1.0 - ndc[:, 1]) * .5 * size[1]]
    visible = (w[:, 0] > 0) & (np.abs(ndc[:, 0]) <= 1.05) & (np.abs(ndc[:, 1]) <= 1.05)
    return screen, visible


def ribbon_handles(frame, values, object_id, size, extent, style):
    """Selected ribbon outline + height / width / phase handles, through the production camera.

    Each handle edits a real card value. ``perPixel`` maps a drag in presented-frame pixels to the value
    so the handle tracks the projected geometry: height scales the carrier amplitude, width the sheet's
    projected span, phase one projected wavelength per 2*pi."""
    import math
    import numpy as np
    empty = {"outline": [], "handles": []}
    try:
        index = int(str(object_id).replace("ribbon", ""))
    except ValueError:
        return empty
    width, height = float(size[0]), float(size[1])
    if width <= 1 or height <= 1 or frame is None or not getattr(frame, "ready", False):
        return empty
    cards = values.get(PREFIX + "ribbons") or ()
    if index >= len(cards) or index >= int(values.get(PREFIX + "count", len(cards))):
        return empty
    points = ribbon_world_points(frame, index)
    if len(points) < 4:
        return empty
    matrix, _aperture = frame_camera(frame, (width, height), extent, style)
    screen, visible = _project(matrix, points, (width, height))
    if visible.sum() < 4:
        return empty
    step = max(1, int(visible.sum() // 160))
    outline = [[round(float(x), 1), round(float(y), 1)] for (x, y), v in zip(screen[::step], visible[::step]) if v]
    # Crest: the highest visible knot in the central 70% of the frame.
    centre = visible & (screen[:, 0] > .15 * width) & (screen[:, 0] < .85 * width)
    candidates = np.flatnonzero(centre if centre.any() else visible)
    crest = int(candidates[np.argmin(screen[candidates, 1])])
    base_y = float(np.median(points[visible, 1]))
    crest_point = points[crest]
    base_screen, _ = _project(matrix, np.array([[crest_point[0], base_y, crest_point[2], 0.]]), (width, height))
    amplitude_px = max(4.0, float(base_screen[0, 1] - screen[crest, 1]))
    card = cards[index]
    key = PREFIX + "ribbons"
    handles = [{"id": "height", "property": f"{key}[{index}].height", "endpoint": 0, "axis": "y",
                "x": float(screen[crest, 0]), "y": float(screen[crest, 1]),
                "perPixel": -float(card["height"]) / amplitude_px, "label": "Height"}]
    half = float(crest_point[3])
    edge, _ = _project(matrix, np.array([[crest_point[0], crest_point[1] + max(half, 1e-3), crest_point[2], 0.]]),
                       (width, height))
    span_px = max(4.0, abs(float(screen[crest, 1] - edge[0, 1])))
    handles.append({"id": "width", "property": f"{key}[{index}].width", "endpoint": 0, "axis": "y",
                    "x": float(screen[crest, 0]) - 30.0, "y": float(screen[crest, 1] - span_px),
                    "perPixel": -float(card["width"]) / span_px, "label": "Width", "span": span_px})
    # Wavelength: distance to the next visible crest of this ribbon (local maxima in screen height).
    ys = screen[:, 1]
    maxima = [i for i in range(1, len(ys) - 1) if visible[i] and ys[i] <= ys[i - 1] and ys[i] < ys[i + 1]]
    spacing = [abs(float(screen[b, 0] - screen[a, 0])) for a, b in zip(maxima, maxima[1:])]
    wavelength = float(np.median(spacing)) if spacing else width / 3.0
    handles.append({"id": "phase", "property": f"{key}[{index}].phase", "endpoint": 0, "axis": "x",
                    "x": float(screen[crest, 0]), "y": float(min(height - 14.0, base_screen[0, 1] + 18.0)),
                    "perPixel": 2.0 * math.pi / max(8.0, wavelength), "label": "Phase"})
    # Combined move gizmo (mock): one crosshair on the spine; up/down = height, left/right = phase. It sits
    # on the visible spine nearest the frame centre, kept clear of the crest's precise handles.
    crest_x = float(screen[crest, 0])
    targets = [width * .5, width * .3, width * .7]
    target = next((t for t in targets if abs(t - crest_x) > 90.0), targets[0])
    spine = np.flatnonzero(visible)
    nearest = int(spine[np.argmin(np.abs(screen[spine, 0] - target))])
    handles.append({"id": "move", "property": f"{key}[{index}].phase", "endpoint": 0, "axis": "xy",
                    "x": float(screen[nearest, 0]), "y": float(screen[nearest, 1]),
                    "perPixel": 2.0 * math.pi / max(8.0, wavelength),
                    "propertyY": f"{key}[{index}].height", "perPixelY": -float(card["height"]) / amplitude_px,
                    "label": "Move"})
    return {"outline": outline, "handles": handles}


# -------------------------------------------------------------------------- renderer
class WaveformStudioRenderer:
    """Render-thread adapter around the production Quick renderer (own scene instance)."""

    def __init__(self) -> None:
        from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
        self._impl = QuickWaveformRibbonRenderer()
        self._presentation_key = None
        self._presentation = None

    def _resolved_presentation(self, card: RenderCard):
        """The production presentation of the presented card extent at this viewport's size.

        Same resolver the runtime uses, so ``framed_aperture_scale`` (lens aperture, edge-resize
        reveal/crop) is production's. Card chrome (border/inset) is not drawn by the Studio."""
        key = (card.logical_size, card.extent, card.style)
        if key != self._presentation_key:
            self._presentation = studio_presentation(card.logical_size, card.extent, card.style)
            self._presentation_key = key
        return self._presentation

    def _frame(self, card: RenderCard, state):
        presentation = self._resolved_presentation(card)
        return SimpleNamespace(snapshot=SimpleNamespace(logical=SimpleNamespace(mode_state=state),
                                                        presentation=presentation),
                               viewport=card.viewport, logical_size=card.logical_size,
                               matrix_values=card.matrix_values, quad_vao=card.quad_vao)

    def _preview_layers(self, card: RenderCard) -> None:
        """Studio-only layer omission for rendered cards (``preview_hidden`` in the card style); the live
        viewport's style never carries it, so the production scene draws everything there."""
        self._impl._scene.preview_hidden = frozenset(dict(card.style or ()).get("preview_hidden", ()))

    def prepare(self, card: RenderCard, frame) -> bool:
        self._preview_layers(card)
        return bool(self._impl.prepare_step(self._frame(card, frame)))

    def render(self, card: RenderCard, frame) -> None:
        self._preview_layers(card)
        self._impl.render(self._frame(card, frame))

    def release(self) -> None:
        self._impl.release_resources()


# --------------------------------------------------------------------------- adapter
def recordings_directory():
    from pathlib import Path
    return Path(__file__).resolve().parents[2] / "logs" / "visualizer_recordings"


class WaveformStudioAdapter(StudioModeAdapter):
    mode_id = MODE
    title = "Waveform Studio"

    def __init__(self) -> None:
        self._schema: StudioSchema | None = None

    def capabilities(self) -> StudioCapabilities:
        return StudioCapabilities(viewport=True, camera=True, handles=True)

    def schema(self) -> StudioSchema:
        if self._schema is None:
            self._schema = build_schema()
        return self._schema

    def scene_objects(self, values: Mapping[str, Any]) -> tuple[SceneObject, ...]:
        cards = values.get(PREFIX + "ribbons") or ()
        count = int(values.get(PREFIX + "count", len(cards)))
        # Ribbon Count shows the first N ribbons: an eye toggles the count, so a ribbon is shown or
        # hidden together with every ribbon after it (the data is a count, not per-ribbon flags).
        return tuple(SceneObject(id=f"ribbon{index}", label=f"Ribbon {index + 1}",
                                 swatch=display_hex(card["quiet"][0]), visible=index < count, toggleable=True,
                                 hidden_note="" if index < count else "beyond Ribbon Count")
                     for index, card in enumerate(cards))

    def apply_preset(self, group, preset_id, baseline, values):
        if group != "Sheet & Highlights":
            return {}
        spec = require_mode_settings(MODE)
        scales = _MATERIAL_SCALES.get(preset_id, {})
        changes = {}
        for control in spec.controls:
            if not control.key.startswith(PREFIX + "material_"):
                continue
            field = control.key[len(PREFIX):]
            factor = scales.get(field, 1.0)
            pair = [min(control.high, max(control.low, float(v) * factor)) for v in baseline[control.key]]
            if control.integer:
                pair = [int(round(v)) for v in pair]
            # The canonical store keeps the control's displayed precision: equal within half its step is
            # "already applied" (stronger material scales produce values the store rounds).
            step = .5 * 10.0 ** -int(getattr(control, "decimals", 4) or 4) + 1e-9
            if any(abs(float(a) - float(b)) > max(step, 1e-4 * abs(float(a)))
                   for a, b in zip(pair, values[control.key])):
                changes[(control.key,)] = pair
        return changes

    # Tile previews: a private evaluator held on the Mid reference at one instant; each starting point
    # re-publishes that instant with its values (the live-edit path, no replay).

    def release(self) -> None:
        for evaluator in self.__dict__.pop("_preview_evaluators", {}).values():
            evaluator.release()

    def _preview_frame(self, values):
        """One instant of the Mid reference under ``values``. A private evaluator per scene structure (the
        ribbon count) replays once; later requests re-publish that instant with their values (the live-edit
        path, no replay). Structure changes cannot be re-published, so they get their own evaluator."""
        evaluators = self.__dict__.setdefault("_preview_evaluators", {})
        structure = int(values.get(PREFIX + "count", 0))
        evaluator = evaluators.get(structure)
        if evaluator is None:
            if len(evaluators) >= 3:                     # tiles + cards + one recent count
                evaluators.pop(next(iter(evaluators))).release()
            evaluator = evaluators[structure] = WaveformStudioEvaluator()
            evaluator.select("mid")
        return evaluator.evaluate(min(3.0, evaluator.fixture.duration), dict(values), exact=False)

    # Tile close-up: the selected ribbon alone, nothing around it (no particles, strands, mist or floor);
    # the lens factor and pose frame one crest and one trough running across the 3:2 tile (measured, 5 Nov).
    TILE_LENS = 1.1
    TILE_POSE = {"turn": 0.25, "tilt": 0.15, "scene_pan_x": 0.0, "scene_pan_y": 0.0, "scene_scale": 1.0}
    _TILE_OFF = {"sparks_enabled": False, "strands_enabled": False, "mist_enabled": False}
    _TILE_ZERO = ("floor_brightness", "floor_reflection")

    def tile_values(self, values, object_id):
        view = dict(values)
        cards = list(view.get(PREFIX + "ribbons") or ())
        try:
            index = int(str(object_id).replace("ribbon", ""))
        except ValueError:
            index = 0
        if cards:
            # The card set is always complete; the selected card moves first and only the first is shown.
            index = min(max(index, 0), len(cards) - 1)
            view[PREFIX + "ribbons"] = [cards[index]] + cards[:index] + cards[index + 1:]
            view[PREFIX + "count"] = 1
        for key, value in self._TILE_OFF.items():
            if PREFIX + key in view:
                view[PREFIX + key] = value
        for key in self._TILE_ZERO:
            if PREFIX + key in view:
                view[PREFIX + key] = [0.0, 0.0]
        if PREFIX + "camera_fov" in view:
            spec = require_mode_settings(MODE).control(PREFIX + "camera_fov")
            view[PREFIX + "camera_fov"] = min(float(spec.high), max(float(spec.low),
                                              float(view[PREFIX + "camera_fov"]) * self.TILE_LENS))
        # A composed tile view (mock): the ribbon seen slightly from the side and above, so the curve runs
        # diagonally across the tile; the pan centres it. Preview-only pose values, admitted by the camera.
        for field, value in self.TILE_POSE.items():
            if PREFIX + field in view:
                view[PREFIX + field] = value
        return view

    def preset_preview(self, group, preset_id, values, object_id=""):
        from ui.studio.adapter import StudioPreview
        from widgets.spotify_visualizer.presentation_geometry import CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
        base_h = float(CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[1])
        frame = self._preview_frame(self.tile_values(values, object_id or "ribbon0"))
        return StudioPreview(frame, (base_h * 1.5, base_h), (), (96.0, 64.0))

    # Rendered world cards: the live framing, the group's Quiet/Peak pairs held on one lane, drawn by the
    # production scene with its actors omitted (Studio preview-only layers): Mist = the haze lit by the ribbons'
    # light field with no ribbon/particle/strand geometry; Floor = the floor with its reflections, no direct actors.
    CARD_HIDDEN = {"Mist": ("actors", "reflected_actors"), "Floor": ("actors",)}
    CARD_CROPS = {"Mist": (0.0, 0.34, 1.0, 0.46), "Floor": (0.0, 0.52, 1.0, 0.48)}

    def card_preview(self, group, values, endpoint, framing, evaluator=None):
        from ui.studio.adapter import StudioPreview
        if group not in self.CARD_CROPS:
            return None
        view = dict(values)
        endpoint = 1 if int(endpoint) else 0
        for prop in self.schema().properties:
            if prop.group == group and prop.instrument == QUIET_PEAK and len(prop.path) == 1 and prop.path[0] in view:
                pair = list(view[prop.path[0]])
                view[prop.path[0]] = [pair[endpoint], pair[endpoint]]
        for key in ("sparks_enabled", "strands_enabled"):       # the card is about the world, not the emitters
            if PREFIX + key in view:
                view[PREFIX + key] = False
        extent = framing.extent if framing is not None else None
        style = (*(framing.style if framing is not None else ()), ("preview_hidden", self.CARD_HIDDEN[group]))
        aspect = (extent[0] / extent[1]) if extent else 1.5
        logical = (220.0, round(220.0 / aspect, 1))
        # The scene on screen (the Studio evaluator's current instant), re-presented with these values.
        frame = evaluator.restyle(view) if evaluator is not None and hasattr(evaluator, "restyle") else None
        if frame is None:
            return None
        return StudioPreview(frame, extent, style, logical, self.CARD_CROPS[group])

    def scene_handles(self, frame, values, object_id, size, extent, style):
        return ribbon_handles(frame, values, object_id, size, extent, style)

    def set_object_visible(self, values, object_id, visible):
        index = int(object_id.replace("ribbon", ""))
        count = index + 1 if visible else index
        spec = require_mode_settings(MODE).control(PREFIX + "count")
        return (PREFIX + "count",), max(int(spec.low), min(int(spec.high), count))

    def add_object(self, values):
        spec = require_mode_settings(MODE).control(PREFIX + "count")
        count = int(values.get(PREFIX + "count", 0))
        return None if count >= int(spec.high) else ((PREFIX + "count",), count + 1)

    def create_evaluator(self) -> WaveformStudioEvaluator:
        return WaveformStudioEvaluator()

    def create_renderer(self) -> WaveformStudioRenderer:
        return WaveformStudioRenderer()

    def navigation(self):
        """Orbit = turn/tilt; wheel zoom = the lens field of view (a saved Camera setting); Shift+wheel =
        the framed camera's grounded dolly (scene_scale); pan = scene pan. Bounds are the registry's."""
        from ui.studio.adapter import NavAxis, StudioNavigation
        spec = require_mode_settings(MODE)

        def axis(field, label, units=""):
            control = spec.control(PREFIX + field)
            return NavAxis(control.key, (float(control.low), float(control.high)), label, units)
        orbit_h, orbit_v = axis("turn", "Turn"), axis("tilt", "Tilt")
        return StudioNavigation(orbit_h=orbit_h, orbit_v=orbit_v, zoom=axis("camera_fov", "FOV", "°"),
                                zoom_inverts=True, dolly=axis("scene_scale", "Dolly", "×"),
                                pan_x=axis("scene_pan_x", "Pan X"), pan_y=axis("scene_pan_y", "Pan Y"),
                                saved_with_camera_policy=frozenset({orbit_h.key, orbit_v.key}),
                                saved_on_keep=frozenset({PREFIX + "camera_fov"}))

    def framings(self, card_extent, card_style=None):
        from ui.studio.framed import card_framings
        return card_framings(card_extent, card_style)

    def default_framing(self) -> str:
        return "fill"           # the live card's world and scale, filling the viewport; Live Card is exact

    def default_fixture(self, evaluator) -> str | None:
        return "mid"

    def recorded_clips(self) -> tuple[StudioFixture, ...]:
        """The shipped clips (Rag Doll, Human, Growing Pains), then a checkout's native-PCM recordings."""
        from ui.studio.waveform_recorded_inputs import studio_clips
        return studio_clips(recordings_directory())

    @staticmethod
    def _clip_key(clip: StudioFixture, values: Mapping[str, Any]) -> str:
        import json
        authored = {control.key for control in require_mode_settings(MODE).body_controls}
        analysis = {key: value for key, value in values.items() if key not in authored}
        return clip.description + "|" + json.dumps(analysis, sort_keys=True, default=str)

    def start_clip_load(self, clip: StudioFixture, values: Mapping[str, Any], finished):
        """Analyse ``clip`` out of process; ``finished(RecordedInputs | None, error)`` on the GUI thread.
        Returns the cancellable job, or None when the result was cached (``finished`` already ran)."""
        from ui.studio import engine_answers
        from ui.studio.waveform_recorded_inputs import ClipLoadJob
        key = self._clip_key(clip, values)
        cached = engine_answers.analysed(MODE, key)
        if cached is not None:
            finished(cached, "")
            return None

        def remember(result, error=""):
            if result is not None and not error:
                engine_answers.remember(MODE, result, key)   # the bounded per-mode store
            finished(result, error)
        return ClipLoadJob(clip, values, remember)


__all__ = [
    "AdvanceInput", "RecordedInputs", "SyntheticInputs", "WaveformStudioAdapter", "WaveformStudioEvaluator",
    "WaveformStudioRenderer", "build_frame", "build_schema", "display_hex", "linear_from_hex",
]
