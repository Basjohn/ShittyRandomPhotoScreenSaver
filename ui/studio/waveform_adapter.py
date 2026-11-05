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

import math
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Iterable, Mapping

from core.settings.visualizer_mode_settings import (
    Choice, Colour, Range, Slider, Toggle, VisualEditor, require_mode_settings,
)
from ui.studio.adapter import (
    RECORDED, REFERENCE, SYNTHETIC, RenderCard, StudioFixture, StudioModeAdapter,
)
from ui.studio.schema import (
    CHOICE, COLOUR, COUNT, GRADIENT, QUIET_PEAK, SCALAR, SWITCH, CardSpec, LifecycleSpec, SceneObject,
    StudioPreset, StudioProperty, StudioSchema, Workspace,
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
_WORKSPACES = (
    Workspace("composition", "Composition", ("Ribbons", "{object}", "Flow"), icon="wave"),
    Workspace("reactivity", "Reactivity", ("Energy Pulse", "Shape Response", "Roll & Twist", "Timing",
                                           "Routing Details", "Advanced (Retired)"),
              open_groups=("Energy Pulse", "Shape Response"), icon="bars"),
    Workspace("appearance", "Appearance", ("Gradient Nodes", "Sheet & Highlights", "{object} Colours", "Colour",
                                           "Particles", "Free Strands"),
              open_groups=("Gradient Nodes", "Sheet & Highlights"), icon="palette"),
    Workspace("world", "World", ("Mist", "Floor", "Lens & Quality", "Camera", "View"),
              open_groups=("Mist", "Floor"), icon="cube"),
)
_CAMERA_FIELDS = ("turn", "tilt", "scene_scale", "scene_pan_x", "scene_pan_y")
# Headline controls lead their group (operator, 5 Nov): mist density and floor look are tuned constantly;
# the reaction mode is the first decision in Reactivity.
_PRIORITY = {PREFIX + key: rank for rank, key in enumerate((
    "reaction_mode", "bend", "pulse_direction", "mist_enabled", "fog_density", "floor_brightness",
    "floor_reflection", "floor_tint"))}
# Material starting points (mock: Sheen / Glass / Satin / Crystal): scale the OPENING material values
# (both quiet and peak endpoints), clamped by the canonical ranges. Applying one replaces the previous
# one (always from the opening values) and is a single undoable edit; "Original" restores them.
_MATERIAL_SCALES = {
    "sheen": {"material_body_alpha": .8, "material_fill_light": 1.4, "material_cross_curve": 1.2,
              "material_glow": 1.0, "material_rim_light": 1.05},
    "glass": {"material_body_alpha": .45, "material_rim_light": 1.35, "material_rim_glow_light": 1.3,
              "material_fill_centre": .6, "material_glow": 1.2, "material_fill_light": .8},
    "satin": {"material_body_alpha": 1.35, "material_fill_light": 1.2, "material_rim_light": .75,
              "material_glint_light": .6, "material_glow": .8, "material_cross_curve": .8},
    "crystal": {"material_glint_density": 1.6, "material_glint_light": 1.4, "material_rim_white": 1.5,
                "material_strand_white": 1.4, "material_glow": 1.1, "material_body_alpha": .7},
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
    "Group Wave": "Crests rise toward a travelling group's leading edge and the cloth surges along its curve.",
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


def build_schema() -> StudioSchema:
    spec = require_mode_settings(MODE)
    from core.waveform_ribbon_authoring import RIBBON_CAPACITY, SOURCES
    props: list[StudioProperty] = []
    # A bucket the Studio has not placed yet still appears (World, under its own title): new
    # canonical controls are never silently missing from the Studio.
    titles = {bucket.key: bucket.title for bucket in spec.buckets}
    extra_groups: list[str] = []
    for control in spec.controls:
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
                      tooltip=tooltip, priority=_PRIORITY.get(control.key, 100))
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

    controls = {control.key: control for control in spec.controls}

    def admit(key: str, candidate: Any, previous: Any) -> Any:
        return controls[key].admit(candidate, previous)

    response = _response_model(spec, props)
    workspaces = tuple(Workspace(w.id, w.title, w.groups + tuple(extra_groups), w.open_groups, w.icon) if w.id == "world" else w
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
                                        "Atmosphere cross-section"),
                               CardSpec("Floor", "reflection", (("brightness", PREFIX + "floor_brightness"),
                                                                ("reflection", PREFIX + "floor_reflection"),
                                                                ("wetness", PREFIX + "floor_wetness"),
                                                                ("streak", PREFIX + "floor_streak"),
                                                                ("tint", PREFIX + "floor_tint")),
                                        "Floor & reflections"),
                               CardSpec("Lens & Quality", "exposure", (("exposure", PREFIX + "exposure"),
                                                                       ("bloom", PREFIX + "bloom")),
                                        "Lighting")))


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
    timing = tuple(PREFIX + k for k in ("attack", "release", "elastic_frequency", "damping", "impulse")
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

    def __init__(self, fixture: StudioFixture, steps: tuple[AdvanceInput, ...], origin: float) -> None:
        self.fixture = fixture
        self._steps = steps
        self._origin = origin      # first source time whose frame is ready; Studio time 0

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
    return {control.key: values[control.key] for control in spec.controls
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


def advance_options(runtime, values: Mapping[str, Any]) -> dict[str, Any]:
    """Optional production advance inputs derived from settings, when this runtime accepts them."""
    import inspect
    accepted = inspect.signature(runtime.advance).parameters
    options = {}
    if "dynamic_zoom" in accepted:
        options["dynamic_zoom"] = bool(values.get(PREFIX + "dynamic_zoom", False))
    if "zoom_hold" in accepted:
        options["zoom_hold"] = False     # the Studio's preview orbit is not a live camera operation
    return options


class WaveformStudioEvaluator:
    """Own runtime + own dynamics, stepped deterministically through one fixture's inputs."""

    def __init__(self) -> None:
        table, _duration = _synthetic_table()
        self._builtin = tuple(SyntheticInputs(key).fixture for key in table)
        self._recorded: dict[str, RecordedInputs] = {}
        self._inputs: SyntheticInputs | RecordedInputs = SyntheticInputs("mid")
        self._runtime = None
        self._iterator = None
        self._pending: AdvanceInput | None = None
        self._time = -math.inf
        self._last = None
        self._last_step = None
        self._configuration = None
        self.steps_run = 0

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
        return self.fixture

    def _restart(self) -> None:
        from widgets.spotify_visualizer.waveform_ribbon_frame_runtime import WaveformRibbonFrameRuntime
        if self._runtime is not None:
            self._runtime.retire()
        self._runtime = WaveformRibbonFrameRuntime()
        self._iterator = iter(self._inputs.steps(self.fixture.duration))
        self._pending = None
        self._time = -math.inf
        self._last = None
        self._last_step = None
        self._configuration = None
        self._approximate = False     # history was stepped with values other than the current ones
        self._revision = None
        self._options = {}

    def evaluate(self, time: float, values: Mapping[str, Any], *, exact: bool = True, revision: Any = None):
        """The frame ``time`` seconds into the fixture under ``values``.

        ``exact`` (the default): the production runtime replayed from the fixture start with
        these values, so equal fixture/values/time always give equal bytes. ``exact=False``
        is the live-gesture path: a values change re-publishes the current step with the new
        controls (production's live-edit behaviour: dt = 0, no time moves) instead of a replay.
        ``revision``: an optional caller token that changes whenever ``values`` change; an equal
        token skips re-deriving the configuration (the per-frame cost while playing)."""
        time = max(0.0, min(float(time), self.fixture.duration))
        if self._runtime is None or time < self._time:
            self._restart()
        if revision is not None and revision == self._revision and self._configuration is not None:
            configuration, options = self._configuration, self._options
        else:
            configuration = self._runtime.configure(_logical_values(values))
            options = advance_options(self._runtime, values)
        self._revision, self._options = revision, options
        changed = self._configuration is not None and configuration is not self._configuration
        if exact and (changed or self._approximate):
            self._restart()
            configuration = self._runtime.configure(_logical_values(values))
            self._revision = revision
        elif changed:
            self._approximate = True
            if self._last_step is not None and time == self._time:
                step = self._last_step
                self._last = self._runtime.advance(onsets=(), now_ts=step.now, playing=step.playing,
                    identity=step.identity, source_identity=step.source_identity, controls=configuration.controls,
                    body_bands=step.body_bands, intensity=step.intensity, loudness=step.loudness,
                    presence=step.presence, **options)
                self.steps_run += 1
                self._configuration = configuration
                return build_frame(configuration, self._last, values)
        self._configuration = configuration
        origin = getattr(self._inputs, "_origin", 0.0)
        while True:
            step = self._pending if self._pending is not None else next(self._iterator, None)
            self._pending = None
            if step is None or step.now - origin > time + 1e-9:
                self._pending = step
                break
            self._last = self._runtime.advance(onsets=step.onsets, now_ts=step.now, playing=step.playing,
                identity=step.identity, source_identity=step.source_identity, controls=configuration.controls,
                body_bands=step.body_bands, intensity=step.intensity, loudness=step.loudness,
                presence=step.presence, **options)
            self._last_step = step
            self.steps_run += 1
        self._time = time
        if self._last is None:
            raise RuntimeError("Fixture produced no logical step")
        if not self._last.ready:
            raise RuntimeError("Waveform history is not primed at this time; extend the fixture pre-roll")
        return build_frame(configuration, self._last, values)

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
        self._runtime = self._iterator = self._pending = self._last = self._last_step = None
        self._configuration = None


# ------------------------------------------------------------------ presentation + handles
def studio_presentation(logical_size, extent, style):
    """The production presentation of the presented card extent at a Studio frame size.

    Same resolver and uniform-scale rule as the display owner, so ``framed_aperture_scale`` (lens aperture,
    edge-resize reveal/crop) is production's. Shared by the renderer and the handle projection."""
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from widgets.spotify_visualizer.presentation_geometry import (
        CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE, resolve_visualizer_presentation)
    width, height = logical_size
    extent = extent or CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
    style = dict(style or ())
    return resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(MODE), display_size=(width, height),
        viewport_extent=extent, uniform_visual_scale=width / extent[0],
        border_width=float(style.get("border_width", 0.0)), corner_radius=0.0,
        content_inset=float(style.get("content_inset", 0.0)), background_color=(0, 0, 0, 0),
        border_color=(0, 0, 0, 0), shadow_enabled=False, shadow_color=(0, 0, 0, 0), shadow_blur=0.0,
        shadow_offset=(0.0, 0.0), shadow_spread=0.0, shadow_extensions=(0.0, 0.0, 0.0, 0.0))


def frame_camera(frame, size, extent, style):
    """(clip-from-world matrix, aperture) exactly as the production renderer would draw ``frame``."""
    import numpy as np
    from core.settings.waveform_ribbon_camera import scene_raster_support
    from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
    from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale
    width, height = size
    aperture = framed_aperture_scale(studio_presentation(size, extent, style), content=True)
    parameters = frame.parameters
    support = (scene_raster_support(frame.packet, frame.scene, frame.travel, now=frame.time,
                                    viewport=(width, height), burst_payload=frame.particles,
                                    burst_origin=frame.particle_origin, strand_payload=frame.strands)
               if parameters[PREFIX + "camera_projection"] == "Orthographic" else None)
    view, projection, _eye, _lens = physical_view(parameters, width / height, aperture, geometry_bounds=support,
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
    x = knots[:, 0, 0] + origin[0] + frame.scene.flow.head_x - frame.travel
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

    def prepare(self, card: RenderCard, frame) -> bool:
        return bool(self._impl.prepare_step(self._frame(card, frame)))

    def render(self, card: RenderCard, frame) -> None:
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
            # The canonical store may quantise what it saves: equal within its precision is "already applied".
            if any(abs(float(a) - float(b)) > 1e-4 * max(1.0, abs(float(a)))
                   for a, b in zip(pair, values[control.key])):
                changes[(control.key,)] = pair
        return changes

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
        from ui.studio.adapter import StudioFraming
        from widgets.spotify_visualizer.presentation_geometry import CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
        base_w, base_h = CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
        card = card_extent or (base_w, base_h)
        label = f"Live Card {card[0] / card[1]:.2f}:1"
        # Wider frames follow production's edge-resize rule: same height, more world revealed.
        style = tuple(sorted((card_style or {}).items()))
        return (StudioFraming("card", label, tuple(card),
                              "The visualizer card as it is laid out (CUSTOM extent, else the card baseline).", style),
                StudioFraming("wide", "16:9", (base_h * 16 / 9, base_h), "A wide card at the baseline height.", style),
                StudioFraming("cinema", "21:9", (base_h * 21 / 9, base_h), "An ultrawide card at the baseline height.",
                              style))

    def default_fixture(self, evaluator) -> str | None:
        return "mid"

    def recorded_clips(self) -> tuple[StudioFixture, ...]:
        from ui.studio.waveform_recorded_inputs import frozen_build, has_native_history
        directory = recordings_directory()
        if frozen_build() or not directory.is_dir():
            return ()     # the replay analysis tools ship only with the source tree
        return tuple(StudioFixture("clip:" + path.stem, path.stem.replace("_", " ").title(), RECORDED, 0.0,
                                   str(path)) for path in sorted(directory.glob("*.jsonl"))
                     if has_native_history(path))

    # Analysed clips for this process, keyed by clip and the analysis (non-authored) settings: the inputs do
    # not depend on authored Waveform controls, so reopening the Studio does not re-run a 30 s analysis.
    _clip_cache: dict = {}

    @staticmethod
    def _clip_key(clip: StudioFixture, values: Mapping[str, Any]) -> str:
        import json
        authored = {control.key for control in require_mode_settings(MODE).controls}
        analysis = {key: value for key, value in values.items() if key not in authored}
        return clip.description + "|" + json.dumps(analysis, sort_keys=True, default=str)

    def start_clip_load(self, clip: StudioFixture, values: Mapping[str, Any], finished):
        """Analyse ``clip`` out of process; ``finished(RecordedInputs | None, error)`` on the GUI thread.
        Returns the cancellable job, or None when the result was cached (``finished`` already ran)."""
        from ui.studio.waveform_recorded_inputs import ClipLoadJob
        key = self._clip_key(clip, values)
        cached = WaveformStudioAdapter._clip_cache.get(key)
        if cached is not None:
            finished(cached, "")
            return None

        def remember(result, error=""):
            if result is not None and not error:
                WaveformStudioAdapter._clip_cache[key] = result
            finished(result, error)
        return ClipLoadJob(clip, values, remember)


__all__ = [
    "AdvanceInput", "RecordedInputs", "SyntheticInputs", "WaveformStudioAdapter", "WaveformStudioEvaluator",
    "WaveformStudioRenderer", "build_frame", "build_schema", "display_hex", "linear_from_hex",
]
