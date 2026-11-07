"""Bubble's Studio adapter: schema, deterministic evaluator, fixtures and renderer, on the shared Studio framework.

Truthfulness (Bubble Temporal Fidelity, ``Docs/Guardrails/Bubble_Temporal_Fidelity.md``): the Studio changes no
Bubble simulation, timing or render code and never re-implements any of it. Every preview frame is integrated by the
production logical step itself (``tick_pipeline.dispatch_bubble_simulation``, reached through the controller's own
``active_logical_tick_hook``) on a ``VisualizerRuntimeController`` configured by the production offline path
(``feature_replay.configure_offline_controller``), captured by the production capture (``logical_frame_capture``'s
Bubble capture) and drawn by the production ``QuickBubbleRenderer``. One authored logical step per input tick: the
synthetic fixtures tick at Bubble's authored 90 Hz class, recorded clips at the production replay's own ticks, so no
cadence is substituted, batched or decimated.

The only Studio-owned pieces are on the *engine* side of that seam: ``FixtureBeatEngine`` (the production replay
engine serving one fixture tick's post-DSP Bubble lane, transient lane and typed events) and the event scheduler's
clock, which is the fixture's time instead of the process clock (the production replay pins the process clock
instead; the Studio runs inside the app and must not). Bubble's spawn randomness comes from the process ``random``
module; the evaluator keeps its own seeded generator state and swaps it in only around its own steps, so replays are
exact and the app's random stream is untouched.
"""
from __future__ import annotations

import dataclasses
import math
import random
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from core.settings.visualizer_mode_settings import (
    Choice, Colour, Custom, Gradient, Slider, Toggle, require_mode_settings,
)
from ui.studio import clip_loop, framed
from ui.studio.adapter import (
    RECORDED, REFERENCE, SYNTHETIC, StudioCapabilities, StudioFixture, StudioModeAdapter, control_condition,
)
from ui.studio.schema import (
    CHOICE, COLOUR, SCALAR, SWITCH, StudioProperty, StudioSchema, Workspace, WorkspaceColumn,
)
from ui.studio.technical import (RAINBOW_GROUP, TECHNICAL_GROUP, admit_rainbow, admit_technical, rainbow_properties,
                                 technical_properties)

MODE = "bubble"
PREFIX = "bubble_"
STEP = 1.0 / 90.0             # Bubble's authored logical service class (BTF 5.1)
PREROLL = 3.0                 # inputs before t = 0 so the population has spawned and settled into the music
DURATION = 10.0
SEED = 1729                   # the production replay's seed (``feature_replay.deterministic_clock``)

# Workspace of each canonical bucket (presentation only; group titles are the registry's bucket titles).
_BUCKET_WORKSPACE = {
    "population": "bubbles", "bounce": "bubbles",
    "motion": "motion", "layout": "motion",
    "reactivity": "reactivity",
    "appearance": "look", "ghost": "look", "particles": "look",
}
_BUCKET_PANEL = {
    "population": ("dots", "Counts and sizes"), "bounce": ("grid", "Meeting and popping"),
    "motion": ("flow", "Stream and drift"), "layout": ("view", "Where they live"),
    "reactivity": ("bolt", "Pulse and smoothing"), "appearance": ("palette", "Glass, light and colour"),
    "ghost": ("sparkle", "Afterimages"), "particles": ("dots", "Microbubbles and particles"),
}
_WORKSPACES = (
    ("bubbles", "Bubbles", "dots", "How many bubbles there are, how big they grow and what happens when they meet."),
    ("motion", "Motion", "flow", "The stream that carries the bubbles, their drift, swirl and tails."),
    ("reactivity", "Reactivity", "bolt", "How the music pulses the bubbles, and the audio analysis feeding them."),
    ("look", "Appearance", "palette", "The bubbles' glass, light and colours, their ghosts and the particles."),
)
_PRIORITY = {PREFIX + key: rank for rank, key in enumerate((
    "big_count", "small_count", "big_size_max", "small_size_max", "stream_direction", "stream_constant_speed",
    "drift_direction", "drift_amount", "big_bass_pulse", "small_freq_pulse", "gradient_direction",
    "gradient_light", "gradient_dark", "outline_color"))}
_ROW_ICONS = {"big_count": "dots", "small_count": "dots", "big_size_max": "height", "small_size_max": "height",
              "stream_direction": "flow", "drift_direction": "wave", "drift_amount": "wave",
              "big_bass_pulse": "bolt", "small_freq_pulse": "bolt", "gradient_direction": "gradient",
              "outline_color": "colour", "trail_strength": "strand", "rotation_amount": "roll"}
_AXES = ("X", "Y")
DRIFT = PREFIX + "drift_direction"
STREAM = PREFIX + "stream_direction"
GRADIENT_DIRECTION, GRADIENT_ENDPOINTS, GRADIENT_CUSTOM = PREFIX + "gradient_direction", PREFIX + "gradient_endpoints", "custom"
# Settings' Particles rule: a population's size, density, direction and colour show while any of its toggles is on
# (the rows stay stored either way).
_AMBIENT = (
    (("microbubble_stream", "microbubble_drift"),
     ("microbubble_density", "microbubble_size", "microbubble_direction_mode", "microbubble_columnarity")),
    (("particle_stream", "particle_drift", "particle_glow"),
     ("particle_size", "particle_density", "particle_direction_mode", "particle_color")),
)


def _extra_conditions(spec) -> dict[str, dict]:
    """Settings' Bubble conditions beyond the registry's ``when``: the stream direction shows only while Drift is not
    a Swirl (Swirl replaces the stream), and each particle population's rows show while any of its toggles is on."""
    drift = spec.control(DRIFT)
    out = {STREAM: {"when": ((DRIFT, tuple(v for v in drift.choices if not str(v).startswith("swirl_"))),)}}
    for toggles, rows in _AMBIENT:
        terms = tuple((PREFIX + toggle, (True,)) for toggle in toggles)
        for row in rows:
            out[PREFIX + row] = {"when_any": terms}
    return out


def _follow(key: str, value: Any, values: Mapping[str, Any]) -> dict:
    """Settings' gradient coupling: moving a Custom Gradient endpoint selects the Custom recipe (named recipes keep
    their own appearance and the latent endpoints)."""
    if key == GRADIENT_ENDPOINTS and values.get(GRADIENT_DIRECTION) != GRADIENT_CUSTOM:
        return {GRADIENT_DIRECTION: GRADIENT_CUSTOM}
    return {}


def _label(text: str) -> str:
    return str(text).rstrip(":").strip()


def _choice_entries(control: Choice) -> tuple[tuple[str, ...], tuple]:
    """(shown labels, stored values): a labelled choice stores its value, an indexed one its index."""
    if control.labels:
        return tuple(control.labels), tuple(control.choices)
    if control.indexed:
        return tuple(control.choices), tuple(range(len(control.choices)))
    return tuple(control.choices), ()


def _custom_controls(spec) -> dict[str, str]:
    """Controls with no bucket of their own, edited in Settings by the mode's Custom row (Bubble's Swirl row
    writes ``bubble_drift_direction``): key -> that row's bucket. The coverage test proves every one is reached."""
    rows = [entry for entry in spec.entries if isinstance(entry, Custom) and entry.bucket]
    if not rows:
        return {}
    return {control.key: rows[0].bucket for control in spec.controls if not control.bucket}


def build_schema() -> StudioSchema:
    spec = require_mode_settings(MODE)
    titles = {bucket.key: bucket.title for bucket in spec.buckets}
    props: list[StudioProperty] = []
    placed: dict[str, list[str]] = {w[0]: [] for w in _WORKSPACES}
    customs = _custom_controls(spec)
    conditions_of = _extra_conditions(spec)
    for control in spec.body_controls:
        bucket = control.bucket or customs.get(control.key, "")
        if not bucket:
            continue
        workspace = _BUCKET_WORKSPACE.get(bucket, "look")       # an unplaced new bucket still appears
        group = titles.get(bucket, bucket)
        if group not in placed[workspace]:
            placed[workspace].append(group)
        text = getattr(control, "text", "") if isinstance(control, Toggle) else ""
        label = _label(control.label) or _label(text) or control.key
        if not control.label and control.key in customs:
            label = "Drift Direction"                                # the Custom row's own title
        tooltip = getattr(control, "tooltip", "")
        conditions = conditions_of.get(control.key, {})
        common = dict(workspace=workspace, group=group, tooltip=tooltip,
                      when=control_condition(control) + conditions.get("when", ()),
                      when_any=conditions.get("when_any", ()),
                      priority=_PRIORITY.get(control.key, 100), icon=_ROW_ICONS.get(control.key[len(PREFIX):], ""))
        if isinstance(control, Slider):
            # Stored values are shown; a Settings display multiplier (sizes x1000) becomes extra decimals.
            extra = max(0, int(round(math.log10(control.display_multiplier)))) if control.display_multiplier > 1 else 0
            decimals = 0 if control.integer else max(control.decimals + extra, 2 if control.percent else 0)
            props.append(StudioProperty(id=control.key, path=(control.key,), label=label, instrument=SCALAR,
                                        minimum=control.low, maximum=control.high,
                                        decimals=decimals, units="" if control.percent else control.suffix,
                                        integer=control.integer, **common))
        elif isinstance(control, Toggle):
            props.append(StudioProperty(id=control.key, path=(control.key,), label=label, instrument=SWITCH,
                                        **common))
        elif isinstance(control, Choice):
            shown, stored = _choice_entries(control)
            props.append(StudioProperty(id=control.key, path=(control.key,), label=label, instrument=CHOICE,
                                        choices=shown, choice_values=stored, **common))
        elif isinstance(control, Colour):
            props.append(StudioProperty(id=control.key, path=(control.key,), label=label, instrument=COLOUR,
                                        **common))
            if control.alpha:
                props.append(StudioProperty(id=f"{control.key}.3", path=(control.key, 3),
                                            label=f"{label} Opacity", instrument=SCALAR, minimum=0.0,
                                            maximum=255.0, decimals=0, integer=True,
                                            **{**common, "priority": common["priority"] + 1, "icon": ""}))
        elif isinstance(control, Gradient):
            # Dark / Light endpoints in normalized top-left coordinates (the GradientMapper's four numbers).
            for index, (end, axis) in enumerate((("Dark", "X"), ("Dark", "Y"), ("Light", "X"), ("Light", "Y"))):
                props.append(StudioProperty(id=f"{control.key}.{index}", path=(control.key, index),
                                            label=f"{label} · {end} {axis}", instrument=SCALAR, minimum=0.0,
                                            maximum=1.0, decimals=2,
                                            **{**common, "priority": common["priority"] + index, "icon": ""}))
        # Any other control type is deliberately not guessed at: the coverage test names it.
    rainbow = rainbow_properties(MODE, workspace="look", subject="the bubbles' colours")
    props.extend(rainbow.values())
    if rainbow:
        placed["look"].append(RAINBOW_GROUP)
    technical = technical_properties(MODE, workspace="reactivity")
    props.extend(prop for prop, _defn in technical.values())
    placed["reactivity"].append(TECHNICAL_GROUP)
    bucket_of = {title: key for key, title in titles.items()}
    order = {key: rank for rank, key in enumerate(_BUCKET_WORKSPACE)}
    workspaces = []
    for workspace_id, title, icon, help_text in _WORKSPACES:
        groups = sorted(placed[workspace_id], key=lambda g: order.get(bucket_of.get(g, ""), len(order)))
        if not groups:
            continue
        columns = []
        for group in groups:
            glyph, subtitle = (("gradient", "Hue drift across the bubbles") if group == RAINBOW_GROUP else
                               _BUCKET_PANEL.get(bucket_of.get(group, ""), ("bars", "Live analysis feeding Bubble")))
            columns.append(WorkspaceColumn(group, (group,), glyph, subtitle))
        workspaces.append(Workspace(workspace_id, title, tuple(groups), open_groups=tuple(groups), icon=icon,
                                    help=help_text, columns=tuple(columns)))
    controls = {control.key: control for control in spec.controls}

    def admit(key: str, candidate: Any, previous: Any) -> Any:
        if key in technical:
            return admit_technical(technical[key], candidate, previous)
        if key in rainbow:
            return admit_rainbow(rainbow, key, candidate, previous)
        return controls[key].admit(candidate, previous)

    group_icons = {titles[key]: glyph for key, (glyph, _sub) in _BUCKET_PANEL.items() if key in titles}
    group_icons[TECHNICAL_GROUP] = "bars"
    group_icons[RAINBOW_GROUP] = "gradient"
    return StudioSchema(MODE, "Bubble Studio", tuple(workspaces), tuple(props), admit,
                        group_traces=((titles.get("reactivity", ""), ("Bass", "Mid / High", "Hero Pulse")),
                                      (titles.get("population", ""), ("Bubbles", "Hero Size")),
                                      (titles.get("motion", ""), ("Stream", "Drift"))),
                        group_icons=tuple(group_icons.items()), object_noun="Bubble", follow=_follow)


# --------------------------------------------------------------------------- inputs
@dataclass(frozen=True)
class TickInput:
    """What the production engine serves Bubble's logical step at one authored tick (post-DSP)."""

    now: float
    playing: bool
    bubble: tuple[float, float, float, float]            # get_bubble_energy_bands: bass, mid, high, overall
    transient: tuple = (0.0, 0.0, 0.0, False, "", 0.0)   # get_transient_energy_bands fields, in order
    events: tuple = ()                                   # typed events fed this tick: (timestamp, kind, strength)
    authoritative: float = 0.0                           # latest authoritative source frame time (0: none)
    fresh: bool = True                                   # that frame belongs to the engine's current activation
    scheduler: bool = True                               # the engine serves its event scheduler (schema 2)


# A beat: (lane shares bass/mid/high, size, decay seconds, transient lane). Kicks, snares and vocal swells are the
# three typed events Bubble's step consumes once each.
_BEAT_SHAPE = {"kick": ((1.0, .25, .05), .22, .12, 0), "snare": ((.2, 1.0, .35), .16, .1, 1),
               "vocal_swell": ((.1, .35, 1.0), .14, .4, 1)}
_ACCENTS = (1.0, .55, .8, .45)
# Held Bubble-lane bodies (bass, mid, high): a soft, an ordinary and a hot passage.
_QUIET, _MID, _PEAK = (.22, .18, .12), (.5, .42, .3), (.86, .74, .55)


def _beats(period: float, start: float, end: float, kind: str, strength: float, offset: int = 0):
    count = int((end - start) / period) + 1
    return [(start + i * period, kind, strength * _ACCENTS[(i + offset) % len(_ACCENTS)]) for i in range(count)]


def _groove(body, beats, *, level=lambda _t: 1.0, lanes=(1., 1., 1.)):
    def signal(t):
        k = level(t)
        out = [b * share * k for b, share in zip(body, lanes)]
        transient = [0.0, 0.0, 0.0]
        for when, kind, magnitude in beats:
            if when <= t:
                shares, size, decay, _lane = _BEAT_SHAPE[kind]
                envelope = size * min(1., magnitude) * math.exp(-(t - when) / decay)
                out = [v + envelope * share for v, share in zip(out, shares)]
                transient = [v + envelope * share * 2.0 for v, share in zip(transient, shares)]
        bass, mid, high = (min(1., v) for v in out)
        return (bass, mid, high, min(1., bass * .46 + mid * .34 + high * .2)), tuple(min(1., v) for v in transient)
    return signal


def _synthetic_table():
    duration = DURATION
    quiet_beats = _beats(1.0, .3, duration, "kick", .5)
    mid_beats = _beats(.5, .1, duration, "kick", 1.4) + _beats(1.0, .35, duration, "snare", 1.0, 1)
    peak_beats = (_beats(.45, .05, duration, "kick", 2.4) + _beats(.9, .275, duration, "snare", 1.8, 2)
                  + _beats(1.8, .6, duration, "vocal_swell", 1.2))
    bass_beats = _beats(.6, 0., duration, "kick", 1.8)
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
        "bass": ("Bass Pulses", SYNTHETIC, "Bass body and kicks alone.",
                 _groove(_MID, bass_beats, lanes=(1., .3, .3)), bass_beats),
        "transient": ("Hit Over Loud Bed", SYNTHETIC, "A loud held bed with two isolated hits.",
                      _groove(_PEAK, hits), hits),
        "decay": ("Decay To Silence", SYNTHETIC, "A hot beat that releases to silence.",
                  _groove(_PEAK, decay_beats, level=decaying), decay_beats),
    }, duration


class SyntheticInputs:
    """Deterministic engine outputs for one synthetic/reference fixture, one per authored tick."""

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

    def steps(self, until: float) -> Iterable[TickInput]:
        first = -int(round(PREROLL / STEP))
        last = int(math.floor(until / STEP + 1e-9))
        for k in range(first, last + 1):
            t = k * STEP
            bands, transient = self._signal(max(0., t))
            events = []
            onset = ("", 0.0)
            if t > 0.:
                for when, kind, magnitude in self._onsets:
                    if t - STEP < when <= t:
                        strength = min(1., magnitude / 3.)
                        events.append((when, kind, strength))
                        onset = (kind, strength)
            yield TickInput(now=t, playing=True, bubble=tuple(float(v) for v in bands),
                            transient=(*transient, bool(onset[0]), onset[0], onset[1]), events=tuple(events),
                            authoritative=max(1e-3, t))


class RecordedInputs:
    """Ticks extracted from a recording by the production replay (``ui.studio.bubble_recorded_inputs``)."""

    def __init__(self, fixture: StudioFixture, steps: tuple[TickInput, ...], origin: float, period: float = 0.0) -> None:
        self.fixture = fixture
        self._steps = steps
        self._origin = origin
        self.period = float(period)        # > 0: a seamless loop (``ui/studio/clip_loop.py``)

    def shifted(self, tick, cycle: int):
        """``tick`` ``cycle`` whole passes on."""
        return clip_loop.shift_clock_tick(tick, cycle * self.period)

    def steps(self, until: float) -> Iterable[TickInput]:
        limit = self._origin + until + 1e-9
        for step in self._steps:
            if step.now > limit:
                return
            yield step


# ----------------------------------------------------------------------- engine side
# The production replay engine serving one tick, and the production scheduler on fixture time (shared, mode-neutral).
from ui.studio.replay_engine import fixture_engine_type as _fixture_engine_type  # noqa: E402


def resolved_settings(values: Mapping[str, Any]) -> dict:
    out = dict(values)
    out["mode"] = MODE
    return out


def _mode_kwargs(values: Mapping[str, Any]) -> dict:
    """The per-mode kwargs the production configuration applies (``configure_offline_controller``'s own steps)."""
    from dataclasses import asdict
    from core.settings.models import SpotifyVisualizerSettings
    from widgets.spotify_visualizer.source_config_applier import resolve_mode_source_config
    model = SpotifyVisualizerSettings.from_mapping(resolved_settings(values), apply_preset_overlay=False,
                                                   resolve_preset_indices=False)
    return resolve_mode_source_config(MODE, asdict(model))


def simulation_keys() -> frozenset[str]:
    """Settings the logical step reads (the spec's logical controls and the technical lane config)."""
    spec = require_mode_settings(MODE)
    return frozenset({c.key for c in spec.logical_controls()} | {c.key for c in spec.technical_controls()})


def presentation_keys() -> tuple[str, ...]:
    """Settings the presentation reads: the spec's presentation controls and the shared rainbow family."""
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    keys = {c.key for c in require_mode_settings(MODE).presentation_controls()}
    keys |= set(get_owned_mode_setting_keys(MODE, "rainbow").values())
    return tuple(sorted(keys))


# ------------------------------------------------------------------------- evaluator
class BubbleStudioEvaluator:
    """Own runtime controller and Bubble runtime, stepped deterministically through one fixture's ticks."""

    def __init__(self) -> None:
        table, _duration = _synthetic_table()
        self._builtin = tuple(SyntheticInputs(key).fixture for key in table)
        self._recorded: dict[str, RecordedInputs] = {}
        self._inputs: SyntheticInputs | RecordedInputs = SyntheticInputs("mid")
        self._controller = None
        self._engine = None
        self._extent: tuple[float, float] | None = None
        self._signature = None
        self._presentation = None
        self._anchor = clip_loop.Anchor()
        self.steps_run = 0
        self._reset_history()

    # fixtures ---------------------------------------------------------------
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

    def set_viewport_extent(self, extent) -> None:
        """The world extent the frame is presented at: Bubble's logical domain is spatial configuration (the
        production step reads the card's committed extent), so a new extent replays the history at it."""
        extent = None if extent is None else (float(extent[0]), float(extent[1]))
        if extent != self._extent:
            self._extent = extent
            self._retire()

    # lifecycle --------------------------------------------------------------
    def _reset_history(self) -> None:
        self._iterator = None
        self._pending: TickInput | None = None
        self._time = -math.inf
        self._last_tick: TickInput | None = None
        self._approximate = False
        state = random.getstate()
        random.seed(SEED)
        self._rng = random.getstate()
        random.setstate(state)

    def _retire(self) -> None:
        controller, self._controller = self._controller, None
        if controller is not None:
            from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime
            runtime = controller.peek_logical_mode_state(MODE)
            if isinstance(runtime, BubbleFrameRuntime):
                runtime.retire()
        self._signature = None
        self._presentation = None
        self._reset_history()

    def _start(self, values: Mapping[str, Any]) -> None:
        from widgets.spotify_visualizer.feature_replay import configure_offline_controller
        from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
        self._retire()
        if self._engine is None:
            self._engine = _fixture_engine_type()(32)
        engine = self._engine
        engine.reset_ticks()
        controller = VisualizerRuntimeController(runtime_generation=0, initial_mode=MODE,
                                                 engine_factory=lambda _bars: engine)
        controller.engine = engine
        configure_offline_controller(controller, MODE, settings=resolved_settings(values))
        if self._extent is not None:
            controller.hydrate_committed_layout_metrics(self._extent, 0)
        self._controller = controller
        self._iterator = iter(clip_loop.unrolled_ticks(self._inputs, self.fixture.duration))
        self._signature = self._simulation_signature(values)
        self._presentation = self._presentation_signature(values)

    @staticmethod
    def _simulation_signature(values: Mapping[str, Any]):
        return tuple(repr(values.get(key)) for key in sorted(simulation_keys()))

    @staticmethod
    def _presentation_signature(values: Mapping[str, Any]):
        return tuple(repr(values.get(key)) for key in presentation_keys())

    def _restyle_controller(self, values: Mapping[str, Any]) -> None:
        from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
        apply_presentation_vis_mode_kwargs(self._controller.presentation_state, _mode_kwargs(values))
        self._presentation = self._presentation_signature(values)

    def _step(self, tick: TickInput) -> None:
        controller = self._controller
        controller.playing = tick.playing
        state = controller.logical_tick_state
        self._engine.serve(tick)
        hook = controller.active_logical_tick_hook
        if hook is None:
            raise RuntimeError("Bubble has no logical step hook")
        hook(state, float(tick.now))
        self.steps_run += 1

    def _capture(self):
        from widgets.spotify_visualizer import logical_frame_capture
        capture = logical_frame_capture._BUILTIN_MODE_CAPTURE[MODE]
        result = capture(self._controller.logical_tick_state, self._engine, None)
        if result is None:
            raise RuntimeError("Bubble capture produced no frame")
        return result[0]

    def evaluate(self, time: float, values: Mapping[str, Any], *, exact: bool = True, revision: Any = None):
        """The frame ``time`` seconds into the fixture under ``values``.

        Exact: the production step replayed from the fixture start under these values, so equal fixture, values,
        extent and time give equal frames. A change only to render-side controls (colours, gradient, ghost look)
        re-presents the same logical instant: the step reads none of them. ``exact=False`` (a live gesture) shows a
        logical change on the next tick instead of replaying (the next exact evaluation replays)."""
        del revision
        at = float(time)
        anchor = self._anchor = self._anchor.sync(getattr(self._inputs, "period", 0.0))
        # A seamless loop plays on through its wrap in the transport's unrolled time (``ui/studio/clip_loop.py``).
        time = max(0.0, anchor.virtual(at)) if anchor.looped else max(0.0, min(at, self.fixture.duration))
        signature = self._simulation_signature(values)
        if self._controller is None or time < self._time or (exact and (signature != self._signature
                                                                        or self._approximate)):
            self._start(values)
            if anchor.looped:
                time = anchor.rebase(at)       # a replay from the start of the pass the instant is in
        elif signature != self._signature:
            from widgets.spotify_visualizer.config_applier import apply_logical_vis_mode_kwargs
            apply_logical_vis_mode_kwargs(self._controller.logical_tick_state, _mode_kwargs(values))
            self._signature = signature
            self._approximate = True
        if self._presentation_signature(values) != self._presentation:
            self._restyle_controller(values)
        origin = getattr(self._inputs, "_origin", 0.0)
        saved = random.getstate()
        random.setstate(self._rng)
        try:
            while True:
                tick = self._pending if self._pending is not None else next(self._iterator, None)
                self._pending = None
                if tick is None or tick.now - origin > time + 1e-9:
                    self._pending = tick
                    break
                self._step(tick)
                self._last_tick = tick
        finally:
            self._rng = random.getstate()
            random.setstate(saved)
        self._time = time
        if self._last_tick is None:
            raise RuntimeError("Fixture produced no logical step")
        return self._capture()

    def restyle(self, values: Mapping[str, Any]):
        """The instant last evaluated under other render-side ``values`` (no stepping); None before any."""
        if self._controller is None or self._last_tick is None:
            return None
        self._restyle_controller(values)
        return self._capture()

    def timeline(self, samples: int = 240) -> list[float]:
        duration = max(1e-6, self.fixture.duration)
        origin = getattr(self._inputs, "_origin", 0.0)
        levels = [0.0] * samples
        for tick in self._inputs.steps(duration):
            t = tick.now - origin
            if t < 0.0:
                continue
            index = min(samples - 1, int(t / duration * samples))
            levels[index] = max(levels[index], tick.bubble[3] + (.25 if tick.events else 0.0))
        peak = max(levels) or 1.0
        return [round(v / peak, 4) for v in levels]

    def measurements(self) -> dict[str, dict[str, float]]:
        """Read-only live values of the evaluator's own step (trace channels)."""
        controller, tick = self._controller, self._last_tick
        if controller is None or tick is None:
            return {"sources": {}, "targets": {}, "signals": {}}
        from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime
        runtime = controller.peek_logical_mode_state(MODE)
        latest = runtime.latest if isinstance(runtime, BubbleFrameRuntime) else None
        geometry = dict(latest.geometry_diagnostics) if latest is not None else {}
        pulse = getattr(controller.logical_tick_state, "_bubble_dispatch_pulse_params", {}) or {}
        return {"sources": {}, "targets": {}, "signals": {
            "Bass": float(pulse.get("bass", 0.0)), "Mid / High": float(pulse.get("mid_high", 0.0)),
            "Hero Pulse": float(geometry.get("max_big_pulse_after", 0.0)),
            "Hero Size": float(geometry.get("final_big_max_radius", 0.0)) * 10.0,
            "Bubbles": (latest.bubble_count / 110.0) if latest is not None else 0.0,
            "Stream": float(geometry.get("stream_step_mean", 0.0)) * 100.0,
            "Drift": float(geometry.get("drift_step_mean", 0.0)) * 100.0}}

    def release(self) -> None:
        self._retire()
        engine, self._engine = self._engine, None
        if engine is not None:
            try:
                engine.force_stop()
            except Exception:
                pass
            engine.deleteLater()


# ------------------------------------------------------------------------- renderer
class BubbleStudioRenderer(framed.ContractModeRenderer):
    """The production ``QuickBubbleRenderer`` handed the production render-frame contract
    (``QuickVisualizerRenderFrame``): mode frame + the live card's resolved presentation + item mapping."""

    def __init__(self) -> None:
        from rendering.quick.visualizer.implementations.bubble import QuickBubbleRenderer
        super().__init__(MODE, QuickBubbleRenderer)


# --------------------------------------------------------------------------- adapter
class BubbleStudioAdapter(StudioModeAdapter):
    mode_id = MODE
    title = "Bubble Studio"

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

    def create_evaluator(self) -> BubbleStudioEvaluator:
        return BubbleStudioEvaluator()

    def create_renderer(self):
        return BubbleStudioRenderer()

    def framings(self, card_extent, card_style=None):
        return framed.card_framings(card_extent, card_style)

    def default_framing(self) -> str:
        return "fill"           # the live card's world and scale, filling the viewport; Live Card is exact

    def default_fixture(self, evaluator) -> str | None:
        return "mid"

    def recorded_clips(self) -> tuple[StudioFixture, ...]:
        """The Studios' shared recorded music: the shipped clips (Rag Doll, Human, Growing Pains), then a checkout's
        native-PCM recordings (Bubble replays the production Bubble lane and typed events from their PCM)."""
        from ui.studio.waveform_adapter import recordings_directory
        from ui.studio.waveform_recorded_inputs import studio_clips
        return studio_clips(recordings_directory())

    # Analysed clips for this process, keyed by clip and the Audio Analysis values: the recorded ticks are the
    # production DSP's answers on the clip's PCM under those values, never dependent on Bubble's authored controls.
    _clip_cache: dict = {}

    def clip_analysis_keys(self) -> frozenset[str]:
        """The values a recorded clip is re-analysed for (the controller re-runs the worker when they change)."""
        from ui.studio.technical import technical_keys
        return technical_keys(MODE)

    def start_clip_load(self, clip: StudioFixture, values: Mapping[str, Any], finished):
        from ui.studio.bubble_recorded_inputs import to_inputs
        from ui.studio.technical import clip_analysis_key
        from ui.studio.waveform_recorded_inputs import ClipLoadJob
        key = clip_analysis_key(clip, MODE, values)
        cached = BubbleStudioAdapter._clip_cache.get(key)
        if cached is not None:
            finished(cached, "")
            return None

        def remember(result, error=""):
            if result is not None and not error:
                BubbleStudioAdapter._clip_cache[key] = result
            finished(result, error)
        return ClipLoadJob(clip, values, remember, module="ui.studio.bubble_recorded_inputs", convert=to_inputs)


__all__ = [
    "BubbleStudioAdapter", "BubbleStudioEvaluator", "BubbleStudioRenderer", "RecordedInputs", "SyntheticInputs",
    "TickInput", "build_schema", "resolved_settings", "simulation_keys",
]
