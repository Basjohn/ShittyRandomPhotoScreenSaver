"""Voxel Sphere's Studio adapter: schema, deterministic evaluator, fixtures and renderer, on the shared framework.

Truthfulness: the Studio changes no Sphere simulation, timing or render code and never re-implements any of it.
Sphere's logical step *is* its production capture: every logical tick the production
``capture_visualizer_logical_frame`` resolves the Sphere frame runtime (``sphere_capture.capture_sphere`` ->
``SphereFrameRuntime.resolve``) from the engine's answers. The evaluator calls exactly that, once per input tick, on
a ``VisualizerRuntimeController`` configured by the production offline path, and the production
``QuickSphereVoxelRenderer`` draws the resulting logical frame. Synthetic fixtures tick at the production logical
cadence (90 Hz), recorded clips at the production replay's own captures. Sphere draws no randomness.

The only Studio-owned pieces are on the engine side (``ui.studio.replay_engine``): the production replay engine
answering one fixture tick, and the production event scheduler on the fixture's clock. Mirror Cubes reflect the
desktop wallpaper, which the Studio does not have: the renderer draws them off (its own rule without a backdrop).
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

from core.settings.visualizer_mode_settings import Choice, Colour, Custom, Slider, Toggle, require_mode_settings
from ui.studio import clip_loop, framed
from ui.studio.exact_replay import PassRestart
from ui.studio.registry import studio_title
from ui.studio.adapter import (
    REFERENCE, SYNTHETIC, StudioCapabilities, StudioFixture, StudioModeAdapter, control_condition,
)
from ui.studio.replay_engine import EngineTick, fixture_engine_type, offline_controller
from ui.studio.schema import (
    CHOICE, COLOUR, SCALAR, SWITCH, StudioProperty, StudioSchema, Workspace, WorkspaceColumn,
)
from ui.studio.technical import TECHNICAL_GROUP, admit_technical, technical_properties

MODE = "sphere"
PREFIX = "sphere_"
STEP = 1.0 / 90.0             # the production logical cadence (quick_display_visualizer_owner._DEFAULT_MAX_FPS)
PREROLL = 2.0
DURATION = 10.0
NOTCH_KEY = "sphere_analysis_notch_positions"
VIEW_GROUP = "View"

_BUCKET_WORKSPACE = {
    "appearance": "look", "effects": "look",
    "reaction": "reaction", "particle_flow": "reaction", "analysis": "reaction",
    "rotation": "motion",
}
_BUCKET_PANEL = {
    "appearance": ("palette", "Finish, colour and light"), "effects": ("sparkle", "Shadow, depth and tracer"),
    "reaction": ("bolt", "Fragments and size"), "particle_flow": ("dots", "Incoming particles"),
    "analysis": ("bars", "Frequency zones"), "rotation": ("roll", "Spin and velocity"),
}
_WORKSPACES = (
    ("look", "Appearance", "palette", "The voxels' finish, colours and light, and the shadow, depth and tracer."),
    ("reaction", "Reactivity", "bolt", "How the music fragments, sizes and feeds the sphere, and which frequencies "
                                       "drive what."),
    ("motion", "Motion", "roll", "The sphere's spin and how fast the music turns it, and the saved view."),
)
_PRIORITY = {PREFIX + key: rank for rank, key in enumerate((
    "finish", "fill_color", "edge_color", "edge_weight", "fragment_strength", "size_response", "particle_amount",
    "spin_direction", "base_rotation_speed", "rotation_speed"))}
_ROW_ICONS = {"finish": "material", "fill_color": "colour", "edge_color": "colour", "fragment_strength": "bolt",
              "size_response": "height", "particle_amount": "dots", "spin_direction": "roll",
              "base_rotation_speed": "roll", "light_direction": "sun", "shadow_enabled": "floor"}


def _label(text: str) -> str:
    return str(text).rstrip(":").strip()


def _norm(name: str) -> str:
    return name.replace("colour", "color")


def _custom_controls(spec) -> dict[str, str]:
    """Controls with no bucket of their own, edited in Settings by the bucket's Custom row of the same name
    (``fill_colour`` -> ``sphere_fill_color``, ``finish`` -> ``sphere_finish``): key -> that row's bucket."""
    rows = {_norm(entry.name): entry.bucket for entry in spec.entries if isinstance(entry, Custom) and entry.bucket}
    return {c.key: rows[_norm(c.key[len(PREFIX):])] for c in spec.controls
            if not c.bucket and _norm(c.key[len(PREFIX):]) in rows}


# The Finish bundles: (Gloss, Specular) each finish writes. The finish name is never sent to the renderer.
_FINISH_PRESETS: dict[str, tuple[float, float]] = {
    "Neutral": (0.20, 0.25),
    "Matte": (0.05, 0.08),
    "Plastic": (0.55, 0.45),
    "Polished": (0.82, 0.70),
    "Metallic": (0.72, 1.00),
    "Glassy": (0.95, 0.75),
}


def finish_presets() -> dict[str, tuple[float, float]]:
    """The Finish bundles: (Gloss, Specular) a finish writes."""
    return dict(_FINISH_PRESETS)


def _follow(key: str, value: Any, values: Mapping[str, Any]) -> dict:
    """The Finish coupling (Settings' former Finish row): a finish writes Gloss and Specular; a manual Gloss or
    Specular edit marks the finish Custom."""
    finish, gloss, specular = PREFIX + "finish", PREFIX + "gloss", PREFIX + "specular"
    if key == finish:
        pair = finish_presets().get(str(value))
        return {} if pair is None else {gloss: pair[0], specular: pair[1]}
    if key in (gloss, specular) and values.get(finish) != "Custom":
        return {finish: "Custom"}
    return {}


def _admit_notches(candidate: Any, previous: Any) -> list:
    """Settings' boundary rule (an edited boundary stops at the other one) then the canonical normalizer."""
    from core.settings.sphere_analysis_contract import normalize_sphere_analysis_notches
    try:
        old = normalize_sphere_analysis_notches(previous)
    except ValueError:
        old = normalize_sphere_analysis_notches(require_canonical_notches())
    try:
        new = [list(record) for record in candidate]
        bass, high = (max(0.0, min(1.0, float(new[i][0]))) for i in (1, 2))
    except (TypeError, ValueError, IndexError):
        return old
    if abs(bass - old[1][0]) > 1e-12:
        bass = min(bass, old[2][0])
        high = old[2][0]
    elif abs(high - old[2][0]) > 1e-12:
        high = max(high, old[1][0])
        bass = old[1][0]
    return normalize_sphere_analysis_notches([[0.0, "Bass"], [bass, "Mid"], [high, "Treble"], [1.0, "End"]])


def require_canonical_notches():
    from core.settings.default_contract import require_canonical_default
    return require_canonical_default("widgets.spotify_visualizer")[NOTCH_KEY]


def build_schema() -> StudioSchema:
    spec = require_mode_settings(MODE)
    titles = {bucket.key: bucket.title for bucket in spec.buckets}
    props: list[StudioProperty] = []
    placed: dict[str, list[str]] = {w[0]: [] for w in _WORKSPACES}
    customs = _custom_controls(spec)
    tracer_on = ((PREFIX + "light_tracer_enabled", (True,)),)

    def place(workspace, group):
        if group not in placed[workspace]:
            placed[workspace].append(group)

    for control in spec.body_controls:
        bucket = control.bucket or customs.get(control.key, "")
        if bucket:
            workspace, group = _BUCKET_WORKSPACE.get(bucket, "look"), titles.get(bucket, bucket)
        elif control.key in (PREFIX + "turn", PREFIX + "tilt"):
            workspace, group = "motion", VIEW_GROUP           # the saved view the live orbit writes
        else:
            continue
        place(workspace, group)
        label = _label(control.label) or _label(getattr(control, "text", "")) or control.key
        if control.key == PREFIX + "finish":
            label = "Finish Preset"
        elif control.key in (PREFIX + "turn", PREFIX + "tilt"):
            label = "View " + control.key[len(PREFIX):].title()
        when = control_condition(control) or (tracer_on if control.key == PREFIX + "tracer_color" else ())
        common = dict(workspace=workspace, group=group, tooltip=getattr(control, "tooltip", ""), when=when,
                      priority=_PRIORITY.get(control.key, 100), icon=_ROW_ICONS.get(control.key[len(PREFIX):], ""))
        if isinstance(control, Slider):
            extra = max(0, int(round(math.log10(control.display_multiplier)))) if control.display_multiplier > 1 else 0
            decimals = 0 if control.integer else max(control.decimals + extra, 2 if control.percent else 0)
            props.append(StudioProperty(id=control.key, path=(control.key,), label=label, instrument=SCALAR,
                                        minimum=control.low, maximum=control.high, decimals=max(decimals, 2)
                                        if not control.integer else 0, units="" if control.percent else control.suffix,
                                        integer=control.integer, **common))
        elif isinstance(control, Toggle):
            props.append(StudioProperty(id=control.key, path=(control.key,), label=label, instrument=SWITCH, **common))
        elif isinstance(control, Choice):
            shown = tuple(control.labels or control.choices)
            stored = tuple(control.choices) if control.labels else (
                tuple(range(len(control.choices))) if control.indexed else ())
            props.append(StudioProperty(id=control.key, path=(control.key,), label=label, instrument=CHOICE,
                                        choices=shown, choice_values=stored, **common))
        elif isinstance(control, Colour):
            props.append(StudioProperty(id=control.key, path=(control.key,), label=label, instrument=COLOUR, **common))
            if control.alpha:
                props.append(StudioProperty(id=f"{control.key}.3", path=(control.key, 3),
                                            label=f"{label} Opacity", instrument=SCALAR, minimum=0.0, maximum=255.0,
                                            decimals=0, integer=True,
                                            **{**common, "priority": common["priority"] + 1, "icon": ""}))
    # Frequency zones (Settings' Custom analysis row): the two interior boundaries of the shared analysis bands.
    analysis = next((e for e in spec.entries if isinstance(e, Custom) and NOTCH_KEY in e.keys), None)
    if analysis is not None:
        group = titles.get(analysis.bucket, analysis.bucket)
        workspace = _BUCKET_WORKSPACE.get(analysis.bucket, "reaction")
        place(workspace, group)
        for index, label in ((1, "Bass / Mid"), (2, "Mid / Treble")):
            props.append(StudioProperty(
                id=f"{NOTCH_KEY}.{index}", path=(NOTCH_KEY, index, 0), label=label, workspace=workspace,
                group=group, instrument=SCALAR, minimum=0.0, maximum=1.0, decimals=3, priority=index,
                tooltip="Boundary within the shared logarithmic analysis bands. This changes Sphere's frequency "
                        "routing only; a boundary stops at the other one."))
    technical = technical_properties(MODE, workspace="reaction")
    props.extend(prop for prop, _defn in technical.values())
    placed["reaction"].append(TECHNICAL_GROUP)
    bucket_of = {title: key for key, title in titles.items()}
    order = {key: rank for rank, key in enumerate(_BUCKET_WORKSPACE)}
    workspaces = []
    for workspace_id, title, icon, help_text in _WORKSPACES:
        groups = sorted(placed[workspace_id], key=lambda g: order.get(bucket_of.get(g, ""), len(order)))
        if not groups:
            continue
        columns = []
        for group in groups:
            if group == VIEW_GROUP:
                glyph, subtitle = "view", "The saved orbit"
            else:
                glyph, subtitle = _BUCKET_PANEL.get(bucket_of.get(group, ""), ("bars", "Live analysis feeding Sphere"))
            columns.append(WorkspaceColumn(group, (group,), glyph, subtitle))
        workspaces.append(Workspace(workspace_id, title, tuple(groups), open_groups=tuple(groups), icon=icon,
                                    help=help_text, columns=tuple(columns)))
    controls = {control.key: control for control in spec.controls}

    def admit(key: str, candidate: Any, previous: Any) -> Any:
        if key in technical:
            return admit_technical(technical[key], candidate, previous)
        if key == NOTCH_KEY:
            return _admit_notches(candidate, previous)
        return controls[key].admit(candidate, previous)

    group_icons = {titles[key]: glyph for key, (glyph, _sub) in _BUCKET_PANEL.items() if key in titles}
    group_icons.update({TECHNICAL_GROUP: "bars", VIEW_GROUP: "view"})
    return StudioSchema(MODE, studio_title(MODE), tuple(workspaces), tuple(props), admit,
                        group_traces=((titles.get("reaction", ""), ("Size", "Fragments", "Tracer")),
                                      (titles.get("rotation", ""), ("Spin",)),
                                      (titles.get("particle_flow", ""), ("Particles",))),
                        group_icons=tuple(group_icons.items()), object_noun="Sphere", follow=_follow)


# --------------------------------------------------------------------------- inputs
# A beat: (lane shares bass/mid/high, size, decay seconds). Kicks, snares and vocal swells are the typed events
# Sphere's runtime consumes once each.
_BEAT_SHAPE = {"kick": ((1.0, .25, .05), .22, .12), "snare": ((.2, 1.0, .35), .16, .1),
               "vocal_swell": ((.1, .35, 1.0), .14, .4)}
_ACCENTS = (1.0, .55, .8, .45)
# (body bass/mid/high on the 0..1 lanes, loudness on the musical scale, presence, intensity).
_QUIET, _MID, _PEAK = ((.22, .18, .12), 4.0, .55, .25), ((.5, .42, .3), 8.5, .95, .55), ((.86, .74, .55), 13.0,
                                                                                         1.4, .9)
_BINS = 35                     # the production pre-AGC analysis spectrum's bin count


def _beats(period: float, start: float, end: float, kind: str, strength: float, offset: int = 0):
    count = int((end - start) / period) + 1
    return [(start + i * period, kind, strength * _ACCENTS[(i + offset) % len(_ACCENTS)]) for i in range(count)]


def _groove(passage, beats, *, level=lambda _t: 1.0):
    body, loudness, presence, intensity = passage

    def signal(t):
        k = level(t)
        out = [b * k for b in body]
        transient = [0.0, 0.0, 0.0]
        for when, kind, magnitude in beats:
            if when <= t:
                shares, size, decay = _BEAT_SHAPE[kind]
                envelope = size * min(1., magnitude) * math.exp(-(t - when) / decay)
                out = [v + envelope * share for v, share in zip(out, shares)]
                transient = [v + envelope * share * 2.0 for v, share in zip(transient, shares)]
        bass, mid, high = (min(1., v) for v in out)
        overall = min(1., bass * .46 + mid * .34 + high * .2)
        # Spectrum: a falling tilt shaped by the three lanes (low bins bass, middle mid, top high), on the
        # analysis scale (about 0..4 per bin).
        spectrum = []
        for i in range(_BINS):
            x = i / (_BINS - 1)
            lane = bass * max(0., 1. - x / .3) + mid * math.exp(-((x - .5) / .2) ** 2) + high * max(0., (x - .6) / .4)
            spectrum.append(round(4.0 * lane * (1.0 - .6 * x), 6))
        return {"bubble": (bass, mid, high, overall), "energy": (bass, mid, high, overall),
                "live": tuple(min(2.5, 2.5 * v) for v in (bass, mid, high, overall)),
                "musical_level": (loudness * k, presence * min(1., .4 + .6 * k)),
                "musical_intensity": intensity * k, "spectrum": tuple(spectrum),
                "transient": tuple(min(1., v) for v in transient)}
    return signal


def _synthetic_table():
    duration = DURATION
    quiet_beats = _beats(1.0, .3, duration, "kick", .5)
    mid_beats = _beats(.5, .1, duration, "kick", 1.4) + _beats(1.0, .35, duration, "snare", 1.0, 1)
    peak_beats = (_beats(.45, .05, duration, "kick", 2.4) + _beats(.9, .275, duration, "snare", 1.8, 2)
                  + _beats(1.8, .6, duration, "vocal_swell", 1.2))
    hits = [(3., "kick", 2.6), (6.5, "snare", 2.4)]
    decay_beats = _beats(.5, .1, 2., "kick", 2.0)

    def decaying(t):
        return 1. if t < 2. else math.exp(-(t - 2.) / 1.5)

    return {
        "quiet": ("Quiet", REFERENCE, "A soft passage with light kicks.", _groove(_QUIET, quiet_beats), quiet_beats),
        "mid": ("Mid", REFERENCE, "An ordinary passage at 120 BPM with kicks and snares.",
                _groove(_MID, mid_beats), mid_beats),
        "peak": ("Peak", REFERENCE, "A hot passage with strong typed beats.", _groove(_PEAK, peak_beats),
                 peak_beats),
        "transient": ("Hit Over Loud Bed", SYNTHETIC, "A loud held bed with two isolated hits.",
                      _groove(_PEAK, hits), hits),
        "decay": ("Decay To Silence", SYNTHETIC, "A hot beat that releases to silence.",
                  _groove(_PEAK, decay_beats, level=decaying), decay_beats),
    }, duration


class SyntheticInputs:
    """Deterministic engine answers for one synthetic/reference fixture, one per production logical tick."""

    def __init__(self, fixture_id: str) -> None:
        table, duration = _synthetic_table()
        if fixture_id not in table:
            raise KeyError(fixture_id)
        label, kind, description, signal, onsets = table[fixture_id]
        self.fixture = StudioFixture(fixture_id, label, kind, duration, description)
        self._signal = signal
        self._onsets = sorted(onsets)
        self._origin = 0.0
        self.period = 0.0

    def steps(self, until: float) -> Iterable[EngineTick]:
        first = -int(round(PREROLL / STEP))
        last = int(math.floor(until / STEP + 1e-9))
        for k in range(first, last + 1):
            t = k * STEP
            answers = self._signal(max(0., t))
            events, onset = [], ("", 0.0)
            if t > 0.:
                for when, kind, magnitude in self._onsets:
                    if t - STEP < when <= t:
                        strength = min(1., magnitude / 3.)
                        events.append((when, kind, strength))
                        onset = (kind, strength)
            transient = answers.pop("transient")
            yield EngineTick(now=t, playing=True, transient=(*transient, bool(onset[0]), onset[0], onset[1]),
                             events=tuple(events), authoritative=max(1e-3, t), **answers)


class RecordedInputs:
    """Ticks extracted from a recording by the production replay (``ui.studio.sphere_recorded_inputs``)."""

    def __init__(self, fixture: StudioFixture, steps: tuple[EngineTick, ...], origin: float, period: float = 0.0) -> None:
        self.fixture = fixture
        self._steps = steps
        self._origin = origin
        self.period = float(period)        # > 0: a seamless loop (``ui/studio/clip_loop.py``)

    def shifted(self, tick, cycle: int):
        """``tick`` ``cycle`` whole passes on."""
        return clip_loop.shift_clock_tick(tick, cycle * self.period)

    def steps(self, until: float) -> Iterable[EngineTick]:
        limit = self._origin + until + 1e-9
        for step in self._steps:
            if step.now > limit:
                return
            yield step


def resolved_settings(values: Mapping[str, Any]) -> dict:
    out = dict(values)
    out["mode"] = MODE
    return out


# ------------------------------------------------------------------------- evaluator
class SphereStudioEvaluator(PassRestart):
    """Own runtime controller and Sphere runtime, stepped deterministically through one fixture's ticks."""

    def __init__(self) -> None:
        table, _duration = _synthetic_table()
        self._builtin = tuple(SyntheticInputs(key).fixture for key in table)
        self._recorded: dict[str, RecordedInputs] = {}
        self._inputs: SyntheticInputs | RecordedInputs = SyntheticInputs("mid")
        self._controller = None
        self._engine = None
        self._values_key = None
        self._environment = None
        self._anchor = clip_loop.Anchor()
        self.steps_run = 0
        self._reset_history()

    def set_environment(self, image) -> None:
        """The photograph Mirror Cubes reflect (``ui.studio.environment``); a change replays."""
        self._environment = image
        self._retire()

    def fixtures(self) -> tuple[StudioFixture, ...]:
        return self._builtin + tuple(item.fixture for item in self._recorded.values())

    @property
    def fixture(self) -> StudioFixture:
        return self._inputs.fixture

    def add_recorded(self, inputs: RecordedInputs) -> None:
        self._recorded[inputs.fixture.id] = inputs

    def select(self, fixture_id: str) -> StudioFixture:
        self._inputs = self._recorded[fixture_id] if fixture_id in self._recorded else SyntheticInputs(fixture_id)
        self._retire()
        return self.fixture

    def _reset_history(self) -> None:
        self._iterator = None
        self._pending: EngineTick | None = None
        self._time = -math.inf
        self._last = None
        self._last_tick: EngineTick | None = None

    def _retire(self) -> None:
        controller, self._controller = self._controller, None
        if controller is not None:
            from widgets.spotify_visualizer.sphere_frame_runtime import SphereFrameRuntime
            runtime = controller.peek_logical_mode_state(MODE)
            if isinstance(runtime, SphereFrameRuntime):
                runtime.retire()
        self._values_key = None
        self._reset_history()

    def _start(self, values: Mapping[str, Any]) -> None:
        self._retire()
        if self._engine is None:
            self._engine = fixture_engine_type()(32)
        self._engine.reset_ticks()
        self._controller = offline_controller(self._engine, MODE, resolved_settings(values))
        self._reflect()
        self._iterator = iter(clip_loop.unrolled_ticks(self._inputs, self.fixture.duration))
        self._values_key = self._key(values)

    @staticmethod
    def _key(values: Mapping[str, Any]):
        """Every value the runtime or the capture reads: the spec controls, the zones and the technical lane."""
        spec = require_mode_settings(MODE)
        keys = {c.key for c in spec.controls} | {NOTCH_KEY}
        return tuple(repr(values.get(key)) for key in sorted(keys))

    def _reflect(self) -> None:
        from ui.studio.environment import refresh_backdrop
        refresh_backdrop(self._controller.presentation_state, MODE, self._environment)

    def _step(self, tick: EngineTick):
        from widgets.spotify_visualizer.logical_frame_capture import capture_visualizer_logical_frame
        controller = self._controller
        controller.playing = tick.playing
        self._engine.serve(tick)
        frame = capture_visualizer_logical_frame(controller.logical_tick_state, now_ts=float(tick.now),
                                                 changed=True, mode_reveal_ready=True)
        self.steps_run += 1
        if frame is not None:
            self._last = frame

    def evaluate(self, time: float, values: Mapping[str, Any], *, exact: bool = True, revision: Any = None):
        """The logical frame ``time`` seconds into the fixture under ``values``: the production capture replayed
        from the fixture start under these values (equal fixture, values and time give equal frames). Every
        Sphere control is read by the runtime or by the capture's render parameters, so a values change replays
        exactly; a live gesture (``exact=False``) keeps the current history and shows the change from the next
        tick."""
        del revision
        at = float(time)
        anchor = self._anchor = self._anchor.sync(getattr(self._inputs, "period", 0.0))
        # A seamless loop plays on through its wrap in the transport's unrolled time (``ui/studio/clip_loop.py``).
        time = max(0.0, anchor.virtual(at)) if anchor.looped else max(0.0, min(at, self.fixture.duration))
        key = self._key(values)
        if self._controller is None or time < self._time or (exact and key != self._values_key):
            back = time < self._time           # a seek back (anything else is a change: values, inputs)
            self._start(values)
            if anchor.looped:
                time = anchor.rebase(at)       # a replay from the start of the pass the instant is in
            if not back:
                time = self._restart_point(time)   # while playing, a long replay restarts the pass instead
        elif key != self._values_key:
            from widgets.spotify_visualizer.feature_replay import configure_offline_controller
            configure_offline_controller(self._controller, MODE, settings=resolved_settings(values))
            self._reflect()
            self._values_key = None             # the next exact evaluation replays
        origin = getattr(self._inputs, "_origin", 0.0)
        while True:
            tick = self._pending if self._pending is not None else next(self._iterator, None)
            self._pending = None
            if tick is None or tick.now - origin > time + 1e-9:
                self._pending = tick
                break
            self._step(tick)
            self._last_tick = tick
        self._time = time
        if self._last is None:
            raise RuntimeError("Fixture produced no logical frame")
        return self._last

    def timeline(self, samples: int = 240) -> list[float]:
        duration = max(1e-6, self.fixture.duration)
        origin = getattr(self._inputs, "_origin", 0.0)
        levels = [0.0] * samples
        for tick in self._inputs.steps(duration):
            t = tick.now - origin
            if t < 0.0:
                continue
            index = min(samples - 1, int(t / duration * samples))
            overall = (tick.bubble or (0.0, 0.0, 0.0, 0.0))[3]
            levels[index] = max(levels[index], overall + (.25 if tick.events else 0.0))
        peak = max(levels) or 1.0
        return [round(v / peak, 4) for v in levels]

    def measurements(self) -> dict[str, dict[str, float]]:
        frame = self._last
        if frame is None:
            return {"sources": {}, "targets": {}, "signals": {}}
        state = frame.mode_state
        return {"sources": {}, "targets": {}, "signals": {
            "Size": float(state.size_pulse), "Fragments": max((float(v) for v in state.section_drives), default=0.0),
            "Tracer": float(state.tracer_drive), "Spin": float(state.rotation_drive),
            "Particles": float(state.incoming_drive)}}

    def release(self) -> None:
        self._retire()
        engine, self._engine = self._engine, None
        if engine is not None:
            try:
                engine.force_stop()
            except Exception:
                pass
            engine.deleteLater()


# --------------------------------------------------------------------------- adapter
class SphereStudioRenderer(framed.ContractModeRenderer):
    """The production ``QuickSphereVoxelRenderer`` handed the production render-frame contract.

    Mirror Cubes fade a newly displayed wallpaper in over the renderer's blend time from when it first sees it
    (``BackdropEnvironment.textures``). In the saver the photograph has been on screen for a while; a Studio frame
    is one instant of a fixture, so the renderer's public ``settle_backdrop`` seam introduces the environment as
    already faded in at the frame's logical time, exactly as if the saver had already shown it. Nothing else changes."""

    def __init__(self) -> None:
        from rendering.quick.visualizer.implementations.sphere_voxel import create_visualizer_renderer
        super().__init__(MODE, create_visualizer_renderer)
        self._settled = None

    def _settle_environment(self, frame) -> None:
        from rendering.quick.visualizer.implementations.sphere_voxel import sphere_mirror
        from ui.studio.environment import settle_backdrop
        self._settled = settle_backdrop(self._impl, frame, sphere_mirror, self._settled)

    def prepare(self, card, frame) -> bool:
        self._settle_environment(frame)
        return super().prepare(card, frame)

    def render(self, card, frame) -> None:
        self._settle_environment(frame)
        super().render(card, frame)


class SphereStudioAdapter(StudioModeAdapter):
    mode_id = MODE
    title = studio_title(MODE)

    def __init__(self) -> None:
        self._schema: StudioSchema | None = None

    def capabilities(self) -> StudioCapabilities:
        return StudioCapabilities(viewport=True, camera=False, handles=False, objects=False)

    def schema(self) -> StudioSchema:
        if self._schema is None:
            self._schema = build_schema()
        return self._schema

    def scene_objects(self, values: Mapping[str, Any]):
        return ()

    def create_evaluator(self) -> SphereStudioEvaluator:
        return SphereStudioEvaluator()

    def create_renderer(self):
        return SphereStudioRenderer()

    def framings(self, card_extent, card_style=None):
        return framed.card_framings(card_extent, card_style)

    def default_framing(self) -> str:
        return "fill"

    def default_fixture(self, evaluator) -> str | None:
        return "mid"

    def recorded_clips(self) -> tuple[StudioFixture, ...]:
        """The Studios' shared recorded music (the shipped clips first)."""
        from ui.studio.waveform_adapter import recordings_directory
        from ui.studio.waveform_recorded_inputs import studio_clips
        return studio_clips(recordings_directory())

    def clip_analysis_keys(self) -> frozenset[str]:
        """The values a recorded clip is re-analysed for (the controller re-runs the worker when they change)."""
        from ui.studio.technical import technical_keys
        return technical_keys(MODE)

    def start_clip_load(self, clip: StudioFixture, values: Mapping[str, Any], finished):
        from ui.studio.sphere_recorded_inputs import to_inputs
        from ui.studio.technical import clip_analysis_key
        from ui.studio import engine_answers
        from ui.studio.waveform_recorded_inputs import ClipLoadJob
        key = clip_analysis_key(clip, MODE, values)
        cached = engine_answers.analysed(MODE, key)
        if cached is not None:
            finished(cached, "")
            return None

        def remember(result, error=""):
            if result is not None and not error:
                engine_answers.remember(MODE, result, key)   # the bounded per-mode store
            finished(result, error)
        return ClipLoadJob(clip, values, remember, module="ui.studio.sphere_recorded_inputs", convert=to_inputs)


__all__ = [
    "RecordedInputs", "SphereStudioAdapter", "SphereStudioEvaluator", "SphereStudioRenderer", "SyntheticInputs",
    "build_schema", "finish_presets", "resolved_settings",
]
