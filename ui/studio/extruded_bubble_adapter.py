"""Extruded Bubble's Studio adapter: schema, deterministic evaluator, fixtures, handles, renderer.

Truthfulness: every preview frame comes from EB's production logical owner (``ExtrudedBubbleFrameRuntime`` -> its
own ``ExtrudedBubbleSimulation``, configured by ``controls_from_parameters``) and is drawn by the production
``QuickExtrudedBubbleRenderer`` (``ui.studio.framed.QuickModeRenderer``). The renderer parameters are built by the
production presentation path (``config_applier``: spec admission, scene pan envelope, the framed camera's joint
admission) on a bare presentation host, so no runtime controller is needed. The evaluator owns its *own* runtime;
it never touches the desktop visualizer's runtime, engine or GL objects. Synthetic fixtures feed exactly the keyword
inputs the production capture (``logical_frame_capture._capture_extruded_bubble``) passes to ``advance``.

EB's physical camera is the shared framed standard (``core.settings.framed_camera``): navigation, framings and the
presentation come from ``ui.studio.framed``. Handles move the authored world paths' Source / End through the same
``physical_camera`` the renderer uses.
"""
from __future__ import annotations

import dataclasses
import math
from array import array
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Iterable, Mapping

from core.settings.visualizer_mode_settings import (
    Choice, Colour, Range, SceneCameraPosition, ScenePath, Slider, Toggle, Triangle, require_mode_settings,
)
from ui.studio import framed
from ui.studio.adapter import RECORDED, REFERENCE, SYNTHETIC, StudioCapabilities, StudioFixture, StudioModeAdapter
from ui.studio.schema import (
    CHOICE, COLOUR, QUIET_PEAK, SCALAR, SWITCH, CardSpec, SceneObject, StudioProperty, StudioSchema, Workspace,
    WorkspaceColumn,
)

MODE = "extruded_bubble"
PREFIX = "extruded_bubble_"
STEP = 1.0 / 60.0            # synthetic logical step (s), the production capture cadence
PREROLL = 4.0                # held first input before t = 0 so the stream has filled the volume
DURATION = 10.0

# Workspace of each canonical bucket (presentation only; group titles are the registry's bucket titles).
_BUCKET_WORKSPACE = {
    "light": "scene", "rays": "scene",
    "bubbles": "bubbles", "motion": "bubbles",
    "reaction": "reactivity", "drift": "reactivity", "collision": "reactivity",
    "water": "look", "glass": "look", "particles": "look",
    "lens": "camera", "camera": "camera",
}
# Dashboard panel subtitles and icons per bucket (short Studio words; the registry helpers stay tooltips).
_BUCKET_PANEL = {
    "light": ("sun", "Type, colour, strength"), "rays": ("sparkle", "Shafts through the water"),
    "bubbles": ("dots", "Counts and sizes"), "motion": ("flow", "Stream and speed"),
    "reaction": ("bolt", "Breathing and pulse"), "drift": ("wave", "Quiet-to-loud drift"),
    "collision": ("grid", "Fuse, pop, bounce"), "water": ("drop", "Colour and haze"),
    "glass": ("material", "Bubble glass"), "particles": ("dots", "Specks and dust"),
    "lens": ("lens", "Focus and exposure"), "camera": ("camera", "Lens and auto rotate"),
}
PATH_GROUP = "{object} Path"
_WORKSPACES = (
    ("scene", "Scene", "sun",
     "Place the light, its rays and the bubble stream in the 3D volume (drag a path's Source / End handles), "
     "then set the light's type, colour and strength."),
    ("bubbles", "Bubbles", "dots", "How many bubbles there are, quiet to loud, their sizes and the stream that "
                                   "carries them."),
    ("reactivity", "Reactivity", "bolt", "How the music moves the bubbles: breathing, pulse, drift and what "
                                         "happens when they meet."),
    ("look", "Water & Glass", "drop", "The water's colours and haze, the bubbles' glass and the particles."),
    ("camera", "Camera & Lens", "camera", "Focus, exposure, the framed camera and its view."),
)
# Headline controls lead their group (the first decisions an author makes); everything else keeps registry order.
_PRIORITY = {PREFIX + key: rank for rank, key in enumerate((
    "light_type", "light_strength", "light_colour", "rays_enabled", "rays", "large_bubbles", "mid_bubbles",
    "stream_speed", "breathing", "small_pulse", "drift", "collision", "water_colour", "haze", "clarity",
    "particles", "focus", "exposure", "camera_fov"))}
_ROW_ICONS = {"light_type": "sun", "light_strength": "sun", "light_colour": "colour", "rays_enabled": "sparkle",
              "large_bubbles": "dots", "mid_bubbles": "dots", "stream_speed": "flow", "drift": "wave",
              "breathing": "height", "haze": "cloud", "water_colour": "drop", "clarity": "material",
              "camera_fov": "lens", "exposure": "sun", "focus": "lens"}
_GROUP_ICONS = {PATH_GROUP: "move", "View": "view"}
_AXES = ("X", "Y", "Z")


def _label(text: str) -> str:
    return text.rstrip(":").strip()


def _path_bounds() -> tuple[float, float]:
    """The normalized world-box bounds, read back from the canonical path admission itself (it clips)."""
    from core.settings.visualizer_paths import admit_path
    far = admit_path([1e6, 1e6, 1e6, -1e6, -1e6, -1e6], [0., 1., 0., 0., -1., 0.])
    return float(far[3]), float(far[0])


def path_controls() -> tuple:
    """EB's authored world paths (Source -> End), in registry order: the Studio's scene objects."""
    return tuple(c for c in require_mode_settings(MODE).controls if isinstance(c, ScenePath))


def path_object_id(control) -> str:
    return control.key[len(PREFIX):]


def path_object_label(control) -> str:
    # "Light Source -> End:" -> "Light" (the registry's own words before the endpoints).
    return _label(control.label).split(" Source")[0].strip() or path_object_id(control)


def _admit(controls: Mapping[str, Any]):
    def admit(key: str, candidate: Any, previous: Any) -> Any:
        control = controls[key]
        if isinstance(control, Triangle):
            candidate = hold_share(candidate, previous)
        return control.admit(candidate, previous)
    return admit


def hold_share(candidate: Any, previous: Any) -> list[float]:
    """One edited share of a three-way blend holds; the other two share the rest in their previous proportion.

    The canonical admission then normalizes (a no-op here): editing one share never moves itself."""
    try:
        new = [float(v) for v in candidate]
        old = [float(v) for v in previous]
    except (TypeError, ValueError):
        return candidate
    if len(new) != 3 or len(old) != 3:
        return candidate
    changed = [i for i in range(3) if abs(new[i] - old[i]) > 1e-12]
    if len(changed) != 1:
        return candidate
    index = changed[0]
    held = max(0.0, min(1.0, new[index]))
    others = [i for i in range(3) if i != index]
    weight = sum(max(0.0, old[i]) for i in others)
    out = [0.0, 0.0, 0.0]
    out[index] = held
    for i in others:
        out[i] = (1.0 - held) * (max(0.0, old[i]) / weight if weight > 0.0 else 0.5)
    return out


def build_schema() -> StudioSchema:
    spec = require_mode_settings(MODE)
    titles = {bucket.key: bucket.title for bucket in spec.buckets}
    props: list[StudioProperty] = []
    low, high = _path_bounds()
    placed: dict[str, list[str]] = {w[0]: [] for w in _WORKSPACES}
    for control in spec.controls:
        bucket = control.bucket
        if not bucket:
            continue                               # the live view pose: View group below
        workspace = _BUCKET_WORKSPACE.get(bucket, "look")      # an unplaced new bucket still appears
        group = titles.get(bucket, bucket)
        if not isinstance(control, ScenePath) and group not in placed[workspace]:
            placed[workspace].append(group)
        text = control.text if isinstance(control, Toggle) else ""        # a checkbox's own words
        label = _label(control.label) or _label(text) or control.key
        tooltip = getattr(control, "tooltip", "")
        common = dict(workspace=workspace, group=group, tooltip=tooltip,
                      priority=_PRIORITY.get(control.key, 100), icon=_ROW_ICONS.get(control.key[len(PREFIX):], ""))
        if isinstance(control, ScenePath):
            # One per-object inspector: the path's six normalized world coordinates (Source, End).
            scope = path_object_id(control)
            for index in range(6):
                end = "Source" if index < 3 else "End"
                props.append(StudioProperty(
                    id=f"{control.key}.{index}", path=(control.key, index), label=f"{end} {_AXES[index % 3]}",
                    workspace="scene", group=PATH_GROUP, instrument=SCALAR, minimum=low, maximum=high, decimals=3,
                    tooltip=tooltip, object_scope=scope, targets=(scope,), priority=index))
        elif isinstance(control, SceneCameraPosition):
            for index, axis in enumerate(_AXES):
                props.append(StudioProperty(id=f"{control.key}.{index}", path=(control.key, index),
                                            label=f"Camera {axis}", instrument=SCALAR, minimum=-1.0, maximum=1.0,
                                            decimals=3, **{**common, "tooltip": tooltip or
                                                           "Normalized camera offset; admitted by the framed camera."}))
        elif isinstance(control, Triangle):
            for index, corner in enumerate(control.corners):
                props.append(StudioProperty(id=f"{control.key}.{index}", path=(control.key, index),
                                            label=f"{label} · {corner}", instrument=SCALAR, minimum=0.0, maximum=1.0,
                                            decimals=2, **{**common, "tooltip": tooltip + " Editing one share keeps "
                                                           "it; the other two share the rest."}))
        elif isinstance(control, Range):
            props.append(StudioProperty(id=control.key, path=(control.key,), label=label, instrument=QUIET_PEAK,
                                        minimum=control.low, maximum=control.high,
                                        decimals=0 if control.integer else control.decimals, units=control.suffix,
                                        integer=control.integer, **common))
        elif isinstance(control, Slider):
            props.append(StudioProperty(id=control.key, path=(control.key,), label=label, instrument=SCALAR,
                                        minimum=control.low, maximum=control.high,
                                        decimals=0 if control.integer else control.decimals, units=control.suffix,
                                        integer=control.integer, **common))
        elif isinstance(control, Toggle):
            props.append(StudioProperty(id=control.key, path=(control.key,), label=label, instrument=SWITCH,
                                        **common))
        elif isinstance(control, Choice):
            props.append(StudioProperty(id=control.key, path=(control.key,), label=label, instrument=CHOICE,
                                        choices=tuple(control.choices), **common))
        elif isinstance(control, Colour):
            props.append(StudioProperty(id=control.key, path=(control.key,), label=label, instrument=COLOUR,
                                        **common))
        # Any other control type is deliberately not guessed at: the full-coverage test names it.
    # Live view pose (not body controls): previewed while navigating; the framed camera's navigation keys.
    camera_nav = framed.camera_navigation(MODE, PREFIX)
    for axis, label in ((camera_nav.orbit_h, "Orbit Turn"), (camera_nav.orbit_v, "Orbit Tilt"),
                        (camera_nav.dolly, "Zoom"), (camera_nav.pan_x, "Pan X"), (camera_nav.pan_y, "Pan Y")):
        props.append(StudioProperty(id=axis.key, path=(axis.key,), label=label, workspace="camera", group="View",
                                    instrument=SCALAR, minimum=axis.bounds[0], maximum=axis.bounds[1], decimals=3,
                                    view_pose=True,
                                    tooltip="Preview view. Drag the viewport to orbit. Orbit is saved only when the "
                                            "preset's camera checkbox includes the view."))
    bucket_of = {title: key for key, title in titles.items()}
    order = {key: rank for rank, key in enumerate(_BUCKET_WORKSPACE)}       # headline buckets first
    for groups in placed.values():
        groups.sort(key=lambda title: order.get(bucket_of.get(title, ""), len(order)))
    placed["camera"].append("View")
    placed["scene"].insert(0, PATH_GROUP)
    workspaces = []
    for workspace_id, title, icon, help_text in _WORKSPACES:
        groups = tuple(placed[workspace_id])
        if not groups:
            continue
        columns = []
        for group in groups:
            if group == PATH_GROUP:
                columns.append(WorkspaceColumn("Path", (group,), "move", "Selected path: Source and End"))
            elif group == "View":
                columns[-1] = dataclasses.replace(columns[-1], groups=columns[-1].groups + (group,))
            else:
                glyph, subtitle = _BUCKET_PANEL.get(bucket_of.get(group, ""), ("", ""))
                columns.append(WorkspaceColumn(group, (group,), glyph, subtitle))
        workspaces.append(Workspace(workspace_id, title, groups, open_groups=groups, icon=icon, help=help_text,
                                    columns=tuple(columns)))
    controls = {control.key: control for control in spec.controls}
    group_icons = {**{titles[key]: glyph for key, (glyph, _sub) in _BUCKET_PANEL.items() if key in titles},
                   **_GROUP_ICONS}
    rays = PREFIX + "rays"
    cards = ()
    if rays in controls and controls[rays].bucket in titles:
        modulation = PREFIX + "ray_modulation"
        roles = (("strength", rays),) + ((("modulation", modulation),) if modulation in controls else ())
        cards = (CardSpec(titles[controls[rays].bucket], "render", roles, "Ray strength", rendered=True),)
    return StudioSchema(MODE, "Extruded Bubble Studio", tuple(workspaces), tuple(props), _admit(controls),
                        group_traces=((titles.get("reaction", ""), ("Passage", "Level", "Sustain")),
                                      (titles.get("rays", ""), ("Rays",)),
                                      (titles.get("bubbles", ""), ("Bubbles", "Passage")),
                                      (titles.get("particles", ""), ("Emission",))),
                        group_icons=tuple(group_icons.items()), object_noun="Path", cards=cards)


# --------------------------------------------------------------------------- inputs
@dataclass(frozen=True)
class AdvanceInput:
    """Exactly the keyword inputs production capture passes to ``ExtrudedBubbleFrameRuntime.advance``."""

    now: float
    playing: bool
    onsets: tuple
    body_bands: tuple[float, float, float]
    play_ramping: bool = False
    identity: tuple = (0, 1, 1)
    source_identity: tuple = (1, 1)


# A beat's body envelope: (lane shares, size, decay seconds). A beat is a short rise of the body feed plus a typed
# onset, the two things EB's simulation turns into flashes, pulses and flow surges.
_BEAT_SHAPE = {"kick": ((1.0, .25, .05), .22, .12), "snare": ((.2, 1.0, .35), .16, .1),
               "vocal_swell": ((.1, .35, 1.0), .14, .4)}
_ACCENTS = (1.0, .55, .8, .45)
# Held body feeds (bass, mid, high) on EB's fixed scale (``get_extruded_bubble_body_bands``) and their onsets'
# loudness: a soft, an ordinary and a hot passage (overall body about .25 / .5 / .8 -> passage .38 / .62 / .86).
_QUIET, _MID, _PEAK = (.28, .25, .15), (.55, .5, .35), (.85, .8, .6)


def _beats(period: float, start: float, end: float, kind: str, strength: float, offset: int = 0):
    count = int((end - start) / period) + 1
    return [(start + i * period, kind, strength * _ACCENTS[(i + offset) % len(_ACCENTS)]) for i in range(count)]


def _groove(body, loudness, presence, beats, *, level=lambda _t: 1.0, lanes=(1., 1., 1.)):
    def signal(t):
        k = level(t)
        out = [b * share * k for b, share in zip(body, lanes)]
        for when, kind, magnitude in beats:
            if when <= t:
                shares, size, decay = _BEAT_SHAPE[kind]
                envelope = size * min(1., magnitude) * math.exp(-(t - when) / decay)
                out = [v + envelope * share for v, share in zip(out, shares)]
        return tuple(min(1., v) for v in out), loudness * k, presence * min(1., .4 + .6 * k)
    return signal


def _synthetic_table():
    duration = DURATION
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
        "quiet": ("Quiet", REFERENCE, "A soft passage on EB's fixed body scale with light kicks.",
                  _groove(_QUIET, 5., .9, quiet_beats), quiet_beats),
        "mid": ("Mid", REFERENCE, "An ordinary passage at 120 BPM with kicks and snares.",
                _groove(_MID, 8.5, 1., mid_beats), mid_beats),
        "peak": ("Peak", REFERENCE, "A hot passage with strong typed beats.",
                 _groove(_PEAK, 12., 1.05, peak_beats), peak_beats),
        "bass": ("Bass Pulses", SYNTHETIC, "Bass body and kicks alone.",
                 _groove(_MID, 9., 1., bass_beats, lanes=(1., .3, .3)), bass_beats),
        "mids": ("Mid Pulses", SYNTHETIC, "Mid body and snares alone.",
                 _groove(_MID, 9., 1., mid_lane, lanes=(.3, 1., .3)), mid_lane),
        "highs": ("High Shimmer", SYNTHETIC, "High body and vocal swells alone.",
                  _groove(_MID, 8.5, 1., high_lane, lanes=(.3, .3, 1.)), high_lane),
        "transient": ("Hit Over Loud Bed", SYNTHETIC, "A loud held bed with two isolated hits.",
                      _groove(_PEAK, 12., 1., hits), hits),
        "sustained": ("Sustained Intensity", SYNTHETIC, "Rises to a long held hot passage, no hits.",
                      _groove(_PEAK, 12., 1.05, [], level=lambda t: min(1., .15 + .85 * t / 2.)), []),
        "decay": ("Decay To Silence", SYNTHETIC, "A hot beat that releases to silence.",
                  _groove(_PEAK, 12., 1.05, decay_beats, level=decaying), decay_beats),
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
            bands, loudness, presence = self._signal(max(0., t))
            onsets = []
            if t > 0.:
                for when, kind, magnitude in self._onsets:
                    if t - STEP < when <= t:
                        serial += 1
                        onsets.append(MusicalOnset(serial=serial, timestamp=when, kind=kind,
                                                   strength=min(1., magnitude / 3.), magnitude=magnitude,
                                                   loudness=loudness, presence=presence))
            yield AdvanceInput(now=t, playing=True, onsets=tuple(onsets),
                               body_bands=tuple(float(b) for b in bands))


class RecordedInputs:
    """Advance inputs extracted from a recording by the production replay (``extruded_bubble_recorded_inputs``)."""

    def __init__(self, fixture: StudioFixture, steps: tuple[AdvanceInput, ...], origin: float) -> None:
        self.fixture = fixture
        self._steps = steps
        self._origin = origin      # the first source time whose capture built a frame; Studio time 0

    def steps(self, until: float) -> Iterable[AdvanceInput]:
        limit = self._origin + until + 1e-9
        for step in self._steps:
            if step.now > limit:
                return
            yield step


# ------------------------------------------------------------------------- evaluator
def scene3d_tier(values: Mapping[str, Any]) -> str:
    """The 3D Detail tier the frame is drawn with: the store's resolved tier (``scene3d_detail``, as the display
    manager hands it to the presentation), else the canonical resolution for this GPU."""
    from rendering.gl_programs.scene3d import scene3d_detail
    tier = values.get("scene3d_detail")
    if tier is None:
        from core.settings.scene3d_quality import resolve_visualizer_tier
        from rendering.quick.bootstrap import last_validated_gpu
        tier = resolve_visualizer_tier(None, MODE, gpu=last_validated_gpu())
    return scene3d_detail(tier).name


def render_parameters(values: Mapping[str, Any]) -> dict[str, object]:
    """EB's renderer parameters exactly as the production capture builds them, from Settings values.

    The production presentation path on a bare presentation host (``config_applier``'s documented bare-host case):
    every spec control admitted for runtime, the scene pan envelope, the 3D Detail tier, then
    ``extruded_bubble_parameters`` with no live orbit / flight / auto-rotate (the framed camera's joint admission
    still applies). The Studio's preview view is a value like any other, never a live camera operation."""
    from widgets.spotify_visualizer import config_applier
    spec = require_mode_settings(MODE)
    host = SimpleNamespace()
    config_applier._apply_spec_controls(host, {c.key: values[c.key] for c in spec.presentation_controls()},
                                        logical=False)
    host._scene3d_detail = scene3d_tier(values)
    return config_applier.extruded_bubble_parameters(host, 0.0)


def build_frame(snapshot, parameters: Mapping[str, object]):
    """Production capture's frame construction: every frame field the snapshot publishes under the same name, the
    wakes as the float32 records the renderer uploads, and the frozen renderer parameters."""
    from widgets.spotify_visualizer.render_state import ExtrudedBubbleFrame, freeze_render_fields
    kwargs: dict[str, Any] = {}
    for field in dataclasses.fields(ExtrudedBubbleFrame):
        if field.name == "parameters":
            kwargs["parameters"] = (parameters if not isinstance(parameters, dict)
                                    else freeze_render_fields(parameters))
        elif field.name == "wakes":
            kwargs["wakes"] = array("f", snapshot.wakes).tobytes()
        elif hasattr(snapshot, field.name):
            kwargs[field.name] = getattr(snapshot, field.name)
    return ExtrudedBubbleFrame(**kwargs)


class ExtrudedBubbleStudioEvaluator:
    """Own frame runtime (own simulation), stepped deterministically through one fixture's inputs."""

    def __init__(self) -> None:
        table, _duration = _synthetic_table()
        self._builtin = tuple(SyntheticInputs(key).fixture for key in table)
        self._recorded: dict[str, RecordedInputs] = {}
        self._inputs: SyntheticInputs | RecordedInputs = SyntheticInputs("mid")
        self._runtime = None
        self._revision = object()
        self._parameters = None
        self._frozen = None
        self._wanted = None
        self.steps_run = 0
        self._restart()

    def fixtures(self) -> tuple[StudioFixture, ...]:
        return self._builtin + tuple(item.fixture for item in self._recorded.values())

    @property
    def fixture(self) -> StudioFixture:
        return self._inputs.fixture

    def add_recorded(self, inputs: RecordedInputs) -> None:
        self._recorded[inputs.fixture.id] = inputs

    def select(self, fixture_id: str) -> StudioFixture:
        self._inputs = self._recorded[fixture_id] if fixture_id in self._recorded else SyntheticInputs(fixture_id)
        self._restart()
        return self.fixture

    def _restart(self) -> None:
        from widgets.spotify_visualizer.extruded_bubble_frame_runtime import ExtrudedBubbleFrameRuntime
        if self._runtime is not None:
            self._runtime.retire()
        self._runtime = ExtrudedBubbleFrameRuntime()
        self._iterator = iter(self._inputs.steps(self.fixture.duration))
        self._pending: AdvanceInput | None = None
        self._time = -math.inf
        self._last = None
        self._last_step: AdvanceInput | None = None
        self._controls = None            # the controls the history was stepped with
        self._approximate = False        # history was stepped with controls other than the current ones

    def _derive(self, values: Mapping[str, Any], revision: Any):
        """(frozen renderer parameters, simulation controls) for ``values``; an equal revision skips the work."""
        from widgets.spotify_visualizer.extruded_bubble_frame_runtime import controls_from_parameters
        from widgets.spotify_visualizer.render_state import freeze_render_fields
        if revision is None or revision != self._revision or self._frozen is None:
            parameters = render_parameters(values)
            self._parameters, self._frozen = parameters, freeze_render_fields(parameters)
            self._wanted = controls_from_parameters(parameters)
            self._revision = revision
        return self._frozen, self._wanted

    def _advance(self, step: AdvanceInput, controls, onsets=None):
        snapshot = self._runtime.advance(onsets=step.onsets if onsets is None else onsets, now_ts=step.now,
                                         playing=step.playing, identity=step.identity,
                                         source_identity=step.source_identity, controls=controls,
                                         body_bands=step.body_bands, play_ramping=step.play_ramping)
        self.steps_run += 1
        return snapshot

    def evaluate(self, time: float, values: Mapping[str, Any], *, exact: bool = True, revision: Any = None):
        """The frame ``time`` seconds into the fixture under ``values``.

        ``exact``: the production runtime replayed from the fixture start with these values' simulation controls,
        so equal fixture/values/time give equal frames. A values change that leaves the simulation controls equal
        (light, water, glass, lens, camera...) only re-presents the same logical instant: the simulation would step
        identically. ``exact=False`` (a live gesture) re-publishes the current step with new controls (dt = 0, no
        time moves) instead of replaying."""
        time = max(0.0, min(float(time), self.fixture.duration))
        if time < self._time:
            self._restart()
        frozen, controls = self._derive(values, revision)
        changed = self._controls is not None and controls != self._controls
        if exact and (changed or self._approximate):
            self._restart()
        elif changed:
            self._approximate = True
            if self._last_step is not None and time == self._time:
                self._last = self._advance(self._last_step, controls, onsets=())
                self._controls = controls
                return build_frame(self._last, frozen)
        self._controls = controls
        origin = getattr(self._inputs, "_origin", 0.0)
        while True:
            step = self._pending if self._pending is not None else next(self._iterator, None)
            self._pending = None
            if step is None or step.now - origin > time + 1e-9:
                self._pending = step
                break
            self._last = self._advance(step, controls)
            self._last_step = step
        self._time = time
        if self._last is None:
            raise RuntimeError("Fixture produced no logical step")
        return build_frame(self._last, frozen)

    def restyle(self, values: Mapping[str, Any]):
        """The instant last evaluated, re-presented under other render-side ``values`` (no stepping, no replay):
        truthful for controls the simulation does not read (light, rays, water, glass, lens); None before any
        evaluation."""
        if self._last is None:
            return None
        return build_frame(self._last, render_parameters(values))

    def timeline(self, samples: int = 240) -> list[float]:
        """The selected input's passage drive over its duration (0..1), for the transport's scrub track."""
        from widgets.spotify_visualizer.extruded_bubble_frame_runtime import passage_intensity_from_body_bands
        duration = max(1e-6, self.fixture.duration)
        origin = getattr(self._inputs, "_origin", 0.0)
        levels = [0.0] * samples
        for step in self._inputs.steps(duration):
            t = step.now - origin
            if t < 0.0:
                continue
            index = min(samples - 1, int(t / duration * samples))
            energy = passage_intensity_from_body_bands(step.body_bands)
            levels[index] = max(levels[index], energy + (.25 if step.onsets else 0.0))
        peak = max(levels) or 1.0
        return [round(v / peak, 4) for v in levels]

    def measurements(self) -> dict[str, dict[str, float]]:
        """Read-only live values of the evaluator's own simulation snapshot (trace channels)."""
        snapshot = self._last
        if snapshot is None:
            return {"sources": {}, "targets": {}, "signals": {}}
        from widgets.spotify_visualizer.extruded_bubble_simulation import MAX_BUBBLES
        return {"sources": {}, "targets": {}, "signals": {
            "Passage": float(snapshot.passage), "Level": float(snapshot.level), "Sustain": float(snapshot.sustain),
            "Rays": float(snapshot.rays), "Emission": float(snapshot.emission), "Hit": float(snapshot.flash),
            "Bubbles": snapshot.count / float(MAX_BUBBLES)}}

    def release(self) -> None:
        if self._runtime is not None:
            self._runtime.retire()
        self._runtime = self._iterator = self._pending = self._last = self._last_step = None
        self._frozen = self._parameters = self._wanted = self._controls = None


# ------------------------------------------------------------------ camera + handles
def frame_camera(parameters, size, extent, style):
    """(world_to_view 3x3, eye, projection 4x4) exactly as the production renderer would draw at ``size``."""
    import numpy as np
    from rendering.gl_programs.extruded_bubble_scene import physical_camera, scene_knobs
    from rendering.quick.visualizer.implementation_values import parameter
    from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale
    width, height = float(size[0]), float(size[1])
    presentation = framed.presentation(MODE, (width, height), extent, style)

    def p(key):
        return parameter(parameters, PREFIX + key)
    _v2w, world_to_view, eye, _tan, projection = physical_camera(
        float(p("turn")), float(p("tilt")), width / height, float(p("scene_scale")),
        pan_x=float(p("scene_pan_x")), pan_y=float(p("scene_pan_y")),
        position_offset=tuple(p("camera_position")), fov_y_degrees=float(p("camera_fov")),
        surface_bound=scene_knobs(parameters)["mode"] == "surface",
        aperture_scale=framed_aperture_scale(presentation), projection_kind=str(p("camera_projection")))
    rotation = np.asarray(world_to_view, dtype=np.float64).reshape(3, 3).T     # GL column-major mat3
    clip = np.asarray(projection, dtype=np.float64).reshape(4, 4).T            # GL column-major mat4
    return rotation, np.asarray(eye, dtype=np.float64), clip


def project(camera, points, size):
    """World points -> (presented-frame pixels with origin top-left, in-front-and-on-screen mask)."""
    import numpy as np
    rotation, eye, clip = camera
    points = np.atleast_2d(np.asarray(points, dtype=np.float64))
    view = (points - eye) @ rotation.T
    homogeneous = np.c_[view, np.ones(len(view))] @ clip.T
    w = homogeneous[:, 3:4]
    ndc = homogeneous[:, :3] / np.where(np.abs(w) < 1e-9, 1e-9, w)
    screen = np.c_[(ndc[:, 0] + 1.0) * .5 * size[0], (1.0 - ndc[:, 1]) * .5 * size[1]]
    visible = (view[:, 2] < 0.0) & (np.abs(ndc[:, 0]) <= 1.05) & (np.abs(ndc[:, 1]) <= 1.05)
    return screen, visible


def _path_points(values: Mapping[str, Any], object_id: str):
    """(path key, source key, normalized six coordinates drawn) for a path object. Under Deep Light the rays share
    the light's physical Source (the renderer's rule), so their Source handle edits the light's Source."""
    from core.settings.visualizer_paths import admit_path
    key = PREFIX + object_id
    path = list(admit_path(values[key], values[key], "light"))
    source_key = key
    light_key = PREFIX + "light_direction"
    if (object_id == "ray_path" and values.get(PREFIX + "light_type") == "Deep Light" and light_key in values):
        light = admit_path(values[light_key], values[light_key], "light")
        path[:3] = light[:3]
        source_key = light_key
    return key, source_key, path


def path_handles(frame, values, object_id, size, extent, style) -> dict:
    """The selected path's Source / End move gizmos and its line, through EB's production physical camera.

    Horizontal drags move the endpoint along whichever world floor axis (X or Z) runs most across the screen at
    that point; vertical drags move it in Y. ``perPixel`` is the inverse projected rate there, so the endpoint
    tracks the pointer."""
    import numpy as np
    from core.settings.visualizer_paths import world_point
    empty = {"outline": [], "handles": []}
    width, height = float(size[0]), float(size[1])
    if frame is None or width <= 1 or height <= 1 or PREFIX + str(object_id) not in values:
        return empty
    key, source_key, path = _path_points(values, str(object_id))
    camera = frame_camera(frame.parameters, (width, height), extent, style)
    source, end = np.asarray(world_point(path[:3])), np.asarray(world_point(path[3:]))
    line = source[None, :] + np.linspace(0.0, 1.0, 33)[:, None] * (end - source)[None, :]
    screen, visible = project(camera, line, (width, height))
    outline = [[round(float(x), 1), round(float(y), 1)] for (x, y), v in zip(screen, visible) if v]
    from core.constants.extruded_bubble_world import WORLD_HALF
    handles = []
    for name, base, coords, prop_key in (("Source", 0, path[:3], source_key), ("End", 3, path[3:], key)):
        point = np.asarray(world_point(coords))
        here, shown = project(camera, point, (width, height))
        if not shown[0]:
            continue
        rates = []
        for axis in range(3):
            step = np.zeros(3)
            step[axis] = .01 * WORLD_HALF[axis]          # 0.01 normalized units
            moved, _ = project(camera, point + step, (width, height))
            rates.append((moved[0] - here[0]) / .01)       # screen pixels per normalized unit
        horizontal = 0 if abs(rates[0][0]) >= abs(rates[2][0]) else 2
        if abs(rates[horizontal][0]) < 1.0 or abs(rates[1][1]) < 1.0:
            continue                                       # seen edge-on: no truthful drag mapping here
        # Source coordinates are the path's (or, shared under Deep Light, the light's) indices 0..2; End's 3..5.
        handles.append({"id": name.lower(), "property": f"{prop_key}.{base + horizontal}", "endpoint": 0,
                        "axis": "xy", "x": float(here[0, 0]), "y": float(here[0, 1]),
                        "perPixel": 1.0 / float(rates[horizontal][0]),
                        "propertyY": f"{prop_key}.{base + 1}", "perPixelY": 1.0 / float(rates[1][1]),
                        "label": name, "shape": "diamond" if name == "End" else "",
                        "tooltip": f"{name}: drag left/right to move it across the volume ({_AXES[horizontal]}), "
                                   "up/down to raise or lower it (Y). One edit; Undo reverts."})
    return {"outline": outline, "handles": handles}


# --------------------------------------------------------------------------- adapter
def _hex(rgba) -> str:
    channels = [max(0, min(255, int(round(float(c))))) for c in list(rgba)[:3]]
    return "#%02x%02x%02x" % tuple(channels)


class ExtrudedBubbleStudioAdapter(StudioModeAdapter):
    mode_id = MODE
    title = "Extruded Bubble Studio"

    def __init__(self) -> None:
        self._schema: StudioSchema | None = None

    def capabilities(self) -> StudioCapabilities:
        return StudioCapabilities(viewport=True, camera=True, handles=True)

    def schema(self) -> StudioSchema:
        if self._schema is None:
            self._schema = build_schema()
        return self._schema

    def scene_objects(self, values: Mapping[str, Any]) -> tuple[SceneObject, ...]:
        spec = require_mode_settings(MODE)
        objects = []
        for control in path_controls():
            object_id = path_object_id(control)
            colour_key = PREFIX + ("water_colour" if object_id.startswith("stream") else "light_colour")
            swatch = _hex(values[colour_key]) if colour_key in values else "#808080"
            # A path is hidden only where the registry has a switch for its layer (the rays).
            switch = next((c for c in spec.controls if isinstance(c, Toggle) and c.bucket == control.bucket
                           and c.key.endswith("_enabled")), None)
            visible = bool(values.get(switch.key, True)) if switch is not None else True
            objects.append(SceneObject(id=object_id, label=path_object_label(control), swatch=swatch,
                                       visible=visible, visibility_path=(switch.key,) if switch else None,
                                       toggleable=switch is not None,
                                       hidden_note="" if visible else "switched off"))
        return tuple(objects)

    def set_object_visible(self, values, object_id, visible):
        target = next((o for o in self.scene_objects(values) if o.id == object_id), None)
        if target is None or target.visibility_path is None:
            return None
        return target.visibility_path, bool(visible)

    def create_evaluator(self) -> ExtrudedBubbleStudioEvaluator:
        return ExtrudedBubbleStudioEvaluator()

    def create_renderer(self):
        from rendering.quick.visualizer.implementations.extruded_bubble import QuickExtrudedBubbleRenderer
        return framed.QuickModeRenderer(MODE, QuickExtrudedBubbleRenderer)

    def navigation(self):
        return framed.camera_navigation(MODE, PREFIX)

    def framings(self, card_extent, card_style=None):
        return framed.card_framings(card_extent, card_style)

    def default_framing(self) -> str:
        return "wide"           # the dashboard's wide viewport; Live Card shows the true card, letterboxed

    def default_fixture(self, evaluator) -> str | None:
        return "mid"

    def recorded_clips(self) -> tuple[StudioFixture, ...]:
        """Project recordings with native PCM (EB's production body feed is recomputed from it)."""
        from ui.studio.waveform_adapter import recordings_directory
        from ui.studio.waveform_recorded_inputs import frozen_build, has_native_history
        directory = recordings_directory()
        if frozen_build() or not directory.is_dir():
            return ()     # the replay analysis runs only from the source tree
        return tuple(StudioFixture("clip:" + path.stem, path.stem.replace("_", " ").title(), RECORDED, 0.0,
                                   str(path)) for path in sorted(directory.glob("*.jsonl"))
                     if has_native_history(path))

    # Analysed clips for this process, keyed by clip and the non-authored (analysis) settings: the advance inputs
    # do not depend on EB's authored controls, so reopening the Studio does not re-run the analysis.
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
        from ui.studio.extruded_bubble_recorded_inputs import to_inputs
        from ui.studio.waveform_recorded_inputs import ClipLoadJob
        key = self._clip_key(clip, values)
        cached = ExtrudedBubbleStudioAdapter._clip_cache.get(key)
        if cached is not None:
            finished(cached, "")
            return None

        def remember(result, error=""):
            if result is not None and not error:
                ExtrudedBubbleStudioAdapter._clip_cache[key] = result
            finished(result, error)
        return ClipLoadJob(clip, values, remember, module="ui.studio.extruded_bubble_recorded_inputs",
                           convert=to_inputs)

    def scene_handles(self, frame, values, object_id, size, extent, style):
        return path_handles(frame, values, object_id, size, extent, style)

    def card_preview(self, group, values, endpoint, framing, evaluator=None):
        """Ray Strength's Quiet / Peak card: the scene on screen re-presented with both handles held at one end
        (the renderer reads Ray Strength; the simulation does not), drawn by the production renderer."""
        from ui.studio.adapter import StudioPreview
        card = next((c for c in self.schema().cards if c.group == group and c.rendered), None)
        if card is None or evaluator is None or not hasattr(evaluator, "restyle"):
            return None
        view = dict(values)
        side = 1 if int(endpoint) else 0
        for _role, prop_id in card.roles:
            prop = self.schema().find(prop_id)
            if prop.instrument == QUIET_PEAK and prop.path[0] in view:
                pair = list(view[prop.path[0]])
                view[prop.path[0]] = [pair[side], pair[side]]
        frame = evaluator.restyle(view)
        if frame is None:
            return None
        extent = framing.extent if framing is not None else None
        aspect = (extent[0] / extent[1]) if extent else 1.5
        return StudioPreview(frame, extent, framing.style if framing is not None else (),
                             (220.0, round(220.0 / aspect, 1)))


__all__ = [
    "AdvanceInput", "ExtrudedBubbleStudioAdapter", "ExtrudedBubbleStudioEvaluator", "RecordedInputs",
    "SyntheticInputs",
    "build_frame", "build_schema", "frame_camera", "hold_share", "path_handles", "project", "render_parameters",
]
