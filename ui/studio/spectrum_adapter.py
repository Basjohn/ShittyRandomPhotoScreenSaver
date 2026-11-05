"""Spectrum's Studio adapter (Rainbow Ghost included): schema, evaluator, fixtures and renderer, on the shared framework.

Truthfulness: the Studio changes no Spectrum simulation, timing, engine or render code and re-implements none of it.

* **Two owners.** Spectrum's step reads the beat engine's *own processing*: ``consume_engine_bars`` ticks the engine
  and copies its smoothed, shape-processed bars, and the shape editor (curve nodes, frequency boundaries, lane
  strengths), the Audio sliders and the technical analysis configure that processing on the process clock. Those
  are **engine-owned**. Everything else (visual smoothing, render mode, ghosts and Rainbow Ghost, colours, glow,
  rainbow, corner radius) is read by Spectrum's own step, capture or renderer: **Spectrum-owned**.
* **Engine answers, out of process.** ``ui.studio.spectrum_recorded_inputs`` replays the source (a recorded clip,
  or generated audio for the synthetic Quiet / Mid / Peak fixtures) through the production offline replay in a
  separate process and records, per production tick, every answer the engine gave Spectrum's step.
* **Spectrum's step, in process.** The evaluator configures a ``VisualizerRuntimeController`` exactly as the offline
  replay does and, per recorded tick, runs the production step itself (``tick_pipeline.consume_engine_bars`` then
  ``logical_frame_capture.capture_visualizer_logical_frame``, the two calls ``logical_tick`` makes for a mode with
  no tick hook) with ``RecordedEngineAnswers`` standing in for the engine. A Spectrum-owned edit therefore replays
  exactly and at once; an engine-owned edit changes the answers' key and re-runs the worker (about a second), the
  previous answers (with their own engine values) staying on screen meanwhile.
* The production ``QuickSpectrumRenderer`` draws the resulting ``VisualizerLogicalFrame``.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import cache
from typing import Any, Callable, Iterable, Mapping

from core.settings.visualizer_mode_settings import Choice, Colour, Custom, Slider, Toggle, require_mode_settings
from ui.studio import framed
from ui.studio.adapter import (
    RECORDED, REFERENCE, SYNTHETIC, StudioCapabilities, StudioFixture, StudioModeAdapter, control_condition,
)
from ui.studio.schema import (
    CHOICE, COLOUR, SCALAR, SWITCH, StudioProperty, StudioSchema, Workspace, WorkspaceColumn,
)
from ui.studio.technical import TECHNICAL_GROUP, admit_technical, technical_properties

MODE = "spectrum"
PREFIX = "spectrum_"
WORKER = "ui.studio.spectrum_recorded_inputs"
SHAPE_NODES = "spectrum_shape_nodes"
MIRRORED = "spectrum_mirrored"
NOTCHES = {True: "spectrum_notch_positions_mirrored", False: "spectrum_notch_positions_linear"}
LANES = {True: "spectrum_lane_strengths_mirrored", False: "spectrum_lane_strengths_linear"}
RAINBOW_GROUP = "Rainbow"
BAR_COLOUR_GROUP = "Bar Colours"

_BUCKET_WORKSPACE = {"render": "bars", "appearance": "colour", "ghost": "colour", "shape": "shape", "audio": "shape"}
_WORKSPACES = (
    ("bars", "Bars", "bars", "How the bars are drawn: segments or solid bars, their colours, corners and smoothing."),
    ("colour", "Colour & Ghosts", "palette", "Rim glow, the rainbow and the falling peak ghosts (Rainbow Ghost)."),
    ("shape", "Shape & Response", "wave", "The authored silhouette, its frequency lanes and how hard the music "
                                          "drives them, and the audio analysis feeding the bars."),
)
_GROUP_PANEL = {
    "render": ("bars", "Bars, corners and smoothing"), "appearance": ("sparkle", "Rim glow"),
    "ghost": ("sparkle", "Falling peak trails"), "shape": ("wave", "Silhouette and frequency lanes"),
    "audio": ("bolt", "Reactivity and falloff"),
}
_PRIORITY = {PREFIX + key: rank for rank, key in enumerate((
    "render_mode", "bar_fill_color", "bar_border_color", "bar_border_opacity", "border_radius",
    "visual_smoothing_enabled", "visual_smoothing", "rainbow_enabled", "rainbow_speed", "unique_colors",
    "rainbow_fill", "rainbow_border", "ghosting_enabled", "rainbow_ghost", "ghost_alpha", "ghost_decay",
    "glow_enabled", "glow_color", "glow_intensity", "mirrored", "wave_amplitude", "profile_floor", "drop_speed"))}
_ROW_ICONS = {"render_mode": "bars", "bar_fill_color": "colour", "bar_border_color": "colour",
              "glow_color": "colour", "rainbow_ghost": "sparkle", "ghosting_enabled": "sparkle",
              "rainbow_enabled": "gradient", "wave_amplitude": "bolt", "drop_speed": "height", "mirrored": "wave"}
_RENDER_LABELS = {"segment": "Segments", "bars": "Bars"}


def _label(text: str) -> str:
    return str(text).rstrip(":").strip()


def _canonical(key: str):
    from core.settings.default_contract import require_canonical_default
    return require_canonical_default("widgets.spotify_visualizer")[key]


def _family_keys(family: str) -> dict[str, str]:
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    return get_owned_mode_setting_keys(MODE, family)


def _custom_keys(spec) -> dict[str, tuple[str, ...]]:
    """Each Custom row's own keys (the shape editor's six, the smoothing pair); a bucketless spec control is edited
    by the Custom row of its name (``render_mode`` writes ``spectrum_render_mode``)."""
    out = {entry.name: tuple(entry.keys) for entry in spec.entries if isinstance(entry, Custom) and entry.bucket}
    for control in spec.controls:
        if not control.bucket and control.key[len(PREFIX):] in out:
            out[control.key[len(PREFIX):]] += (control.key,)
    return out


@cache
def spectrum_owned_keys() -> frozenset[str]:
    """Settings Spectrum's own step, capture or renderer reads: every non-source spec control, the visual smoothing
    row and the mode's shared bar-colour and rainbow families. Anything else Spectrum stores is engine-owned."""
    spec = require_mode_settings(MODE)
    smoothing = next(entry for entry in spec.entries if isinstance(entry, Custom) and entry.name == "smoothing")
    return frozenset({c.key for c in spec.controls if not c.source} | set(smoothing.keys)
                     | set(_family_keys("shared_bar").values()) | set(_family_keys("rainbow").values()))


def engine_values(values: Mapping[str, Any]) -> dict:
    """The engine-owned subset of ``values``: the mode's stored keys (its descriptor prefixes) that Spectrum's own
    step does not read. The recorded answers depend on exactly these (``tests/test_spectrum_studio.py`` proves both
    directions on the production replay)."""
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    prefixes = tuple(get_visualizer_mode_descriptor(MODE).setting_prefixes)
    owned = spectrum_owned_keys()
    return {key: values[key] for key in sorted(values) if key.startswith(prefixes) and key not in owned}


def engine_key(values: Mapping[str, Any]) -> str:
    return json.dumps(engine_values(values), sort_keys=True, default=repr)


# ------------------------------------------------------------------------------- admission
def _unit(value: Any, previous: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(previous)
    return max(0.0, min(1.0, number)) if math.isfinite(number) else float(previous)


def _admit_nodes(candidate: Any, previous: Any) -> list:
    """The shape editor's rules: 1..5 nodes of [x, y] in 0..1, kept in x order. A moved node stops at its
    neighbours (Settings re-sorts a node dragged past one; a Studio slider keeps addressing the same node)."""
    from ui.tabs.media.spectrum_shape_editor import _MAX_NODES, _MIN_NODES
    try:
        old = [[float(x), float(y)] for x, y in previous]
    except (TypeError, ValueError):
        old = [list(map(float, node)) for node in _canonical(SHAPE_NODES)]
    try:
        new = [[_unit(x, 0.0), _unit(y, 0.0)] for x, y in candidate]
    except (TypeError, ValueError):
        return old
    if not _MIN_NODES <= len(new) <= _MAX_NODES:
        return old
    if len(new) == len(old):
        for index, (node, before) in enumerate(zip(new, old)):
            if abs(node[0] - before[0]) > 1e-12:
                low = new[index - 1][0] if index > 0 else 0.0
                high = new[index + 1][0] if index + 1 < len(new) else 1.0
                node[0] = max(low, min(high, node[0]))
    return sorted(new, key=lambda node: node[0])


def _admit_notches(candidate: Any, previous: Any) -> list:
    """Frequency boundaries [[x, label], ...]: the count and labels never change (Settings keeps both); a moved
    boundary stops at its neighbours, then the list stays in x order."""
    try:
        old = [[float(x), str(label)] for x, label in previous]
        new = [[_unit(x, 0.0), str(label)] for x, label in candidate]
    except (TypeError, ValueError):
        return [list(n) for n in previous]
    if len(new) != len(old):
        return old
    for index, (node, before) in enumerate(zip(new, old)):
        node[1] = before[1]
        if abs(node[0] - before[0]) > 1e-12:
            low = new[index - 1][0] if index > 0 else 0.0
            high = new[index + 1][0] if index + 1 < len(new) else 1.0
            node[0] = max(low, min(high, node[0]))
    return sorted(new, key=lambda node: node[0])


def _admit_lanes(candidate: Any, previous: Any) -> dict:
    """Lane strengths {label: 0..1} for the labels the profile already has (``_normalize_lane_strengths``)."""
    old = dict(previous) if isinstance(previous, Mapping) else {}
    source = candidate if isinstance(candidate, Mapping) else {}
    return {label: _unit(source.get(label, value), value) for label, value in old.items()}


def _admit_colour(candidate: Any, previous: Any) -> list:
    try:
        values = [int(round(float(v))) for v in candidate]
    except (TypeError, ValueError):
        return list(previous)
    if len(values) == 3:
        values.append(int(previous[3]) if len(previous) > 3 else 255)
    if len(values) != 4:
        return list(previous)
    return [max(0, min(255, v)) for v in values]


def _percent(value: Any, previous: Any, low: float = 0.0) -> float:
    """A Settings 0..100 % slider's stored value (hundredths)."""
    return round(max(low, _unit(value, previous)), 2)


# ---------------------------------------------------------------------------------- schema
def build_schema() -> StudioSchema:
    from ui.tabs.media.spectrum_shape_editor import _MAX_NODES
    spec = require_mode_settings(MODE)
    titles = {bucket.key: bucket.title for bucket in spec.buckets}
    props: list[StudioProperty] = []
    placed: dict[str, list[str]] = {w[0]: [] for w in _WORKSPACES}
    customs = _custom_keys(spec)
    custom_bucket = {key: entry.bucket for entry in spec.entries if isinstance(entry, Custom) and entry.bucket
                     for key in customs.get(entry.name, ())}

    def place(workspace: str, group: str) -> None:
        if group not in placed[workspace]:
            placed[workspace].append(group)

    def add(key_id: str, path: tuple, label: str, workspace: str, group: str, instrument: str, **extra) -> None:
        place(workspace, group)
        root = path[0]
        extra.setdefault("priority", _PRIORITY.get(root, 100))
        extra.setdefault("icon", _ROW_ICONS.get(root[len(PREFIX):], "") if len(path) == 1 else "")
        props.append(StudioProperty(id=key_id, path=path, label=label, workspace=workspace, group=group,
                                    instrument=instrument, **extra))

    for control in spec.controls:
        bucket = control.bucket or custom_bucket.get(control.key, "")
        if not bucket:
            continue
        workspace, group = _BUCKET_WORKSPACE.get(bucket, "colour"), titles.get(bucket, bucket)
        text = getattr(control, "text", "") if isinstance(control, Toggle) else ""
        label = _label(control.label) or _label(text) or control.key
        if control.key == PREFIX + "render_mode":
            label = "Render Mode"
        common = dict(tooltip=getattr(control, "tooltip", ""), when=control_condition(control))
        if isinstance(control, Slider):
            extra = max(0, int(round(math.log10(control.display_multiplier)))) if control.display_multiplier > 1 else 0
            decimals = 0 if control.integer else max(control.decimals + extra, 2 if control.percent else 0)
            add(control.key, (control.key,), label, workspace, group, SCALAR, minimum=control.low,
                maximum=control.high, decimals=decimals, units="" if control.percent else control.suffix,
                integer=control.integer, **common)
        elif isinstance(control, Toggle):
            add(control.key, (control.key,), label, workspace, group, SWITCH, **common)
        elif isinstance(control, Choice):
            stored = tuple(control.choices)
            shown = tuple(control.labels) if control.labels else tuple(_RENDER_LABELS.get(c, str(c)) for c in stored)
            add(control.key, (control.key,), label, workspace, group, CHOICE, choices=shown, choice_values=stored,
                **common)
        elif isinstance(control, Colour):
            add(control.key, (control.key,), label, workspace, group, COLOUR, **common)
            if control.alpha:
                add(f"{control.key}.3", (control.key, 3), f"{label} Opacity", workspace, group, SCALAR,
                    minimum=0.0, maximum=255.0, decimals=0, integer=True, icon="",
                    priority=_PRIORITY.get(control.key, 100) + 1, **common)

    # The visual smoothing row (Custom): Spectrum's own one-pole on the resolved bars.
    render = titles["render"]
    smoothing_on = PREFIX + "visual_smoothing_enabled"
    add(smoothing_on, (smoothing_on,), "Visual Smoothing", "bars", render, SWITCH,
        tooltip="Ease the drawn bars toward the engine's bars (Spectrum's own presentation smoothing).")
    add(PREFIX + "visual_smoothing", (PREFIX + "visual_smoothing",), "Smoothing Strength", "bars", render, SCALAR,
        minimum=0.0, maximum=1.0, decimals=2, when=((smoothing_on, (True,)),),
        tooltip="Higher = calmer bars; lower = the engine's bars more directly.")

    # The shared bar colours and the rainbow (Settings shows them on Spectrum's page; stored per mode).
    shared = _family_keys("shared_bar")
    for suffix, label in (("bar_fill_color", "Bar Fill Color"), ("bar_border_color", "Bar Border Color")):
        key = shared[suffix]
        add(key, (key,), label, "bars", BAR_COLOUR_GROUP, COLOUR)
        add(f"{key}.3", (key, 3), f"{label} Opacity", "bars", BAR_COLOUR_GROUP, SCALAR, minimum=0.0,
            maximum=255.0, decimals=0, integer=True, icon="", priority=_PRIORITY.get(key, 100) + 1)
    border = shared["bar_border_opacity"]
    add(border, (border,), "Border Opacity", "bars", BAR_COLOUR_GROUP, SCALAR, minimum=0.0, maximum=1.0, decimals=2,
        tooltip="Opacity of the bar borders.")
    rainbow = _family_keys("rainbow")
    add(rainbow["rainbow_enabled"], (rainbow["rainbow_enabled"],), "Taste the Rainbow", "colour", RAINBOW_GROUP,
        SWITCH, tooltip="Slowly shift the hue of the bars through the spectrum. Saved per visualizer mode.")
    add(rainbow["rainbow_speed"], (rainbow["rainbow_speed"],), "Rainbow Speed", "colour", RAINBOW_GROUP, SCALAR,
        minimum=0.01, maximum=1.0, decimals=2, when=((rainbow["rainbow_enabled"], (True,)),),
        tooltip="How fast the hue cycles through the spectrum.")

    # The shape editor (Custom): layout, curve nodes, frequency boundaries and lane strengths.
    shape, workspace = titles["shape"], "shape"
    add(MIRRORED, (MIRRORED,), "Mirrored Layout", workspace, shape, SWITCH,
        tooltip="On: the shape is mirrored around the centre (centre <-> edge). Off: a left-to-right profile.")
    for index in range(_MAX_NODES):
        for axis, word in ((0, "Position"), (1, "Height")):
            add(f"{SHAPE_NODES}.{index}.{axis}", (SHAPE_NODES, index, axis), f"Node {index + 1} {word}", workspace,
                shape, SCALAR, minimum=0.0, maximum=1.0, decimals=3, priority=200 + 2 * index + axis,
                tooltip="A control node of the authored silhouette (across the bars, then its height). A node "
                        "stops at its neighbours; add or remove nodes in Settings' shape editor.")
    for mirrored in (True, False):
        layout = "Mirrored" if mirrored else "Linear"
        notches, lanes = NOTCHES[mirrored], LANES[mirrored]
        for index, (_x, lane) in enumerate(_canonical(notches)):
            add(f"{notches}.{index}", (notches, index, 0), f"{lane} Boundary ({layout})", workspace, shape, SCALAR,
                minimum=0.0, maximum=1.0, decimals=3, priority=300 + index, when=((MIRRORED, (mirrored,)),),
                tooltip="Where this frequency lane sits across the bars. A boundary stops at its neighbours.")
        for index, lane in enumerate(_canonical(lanes)):
            add(f"{lanes}.{lane}", (lanes, lane), f"{lane} Strength ({layout})", workspace, shape, SCALAR,
                minimum=0.0, maximum=1.0, decimals=2, priority=320 + index, when=((MIRRORED, (mirrored,)),),
                tooltip="How strongly this lane drives its bars.")

    technical = technical_properties(MODE, workspace="shape")
    props.extend(prop for prop, _defn in technical.values())
    placed["shape"].append(TECHNICAL_GROUP)

    bucket_of = {title: key for key, title in titles.items()}
    order = {key: rank for rank, key in enumerate(("render", "appearance", "ghost", "shape", "audio"))}
    workspaces = []
    for workspace_id, title, icon, help_text in _WORKSPACES:
        groups = placed[workspace_id]
        if not groups:
            continue
        groups = sorted(groups, key=lambda g: (order.get(bucket_of.get(g, ""), len(order)),
                                               g == TECHNICAL_GROUP))
        columns = []
        for group in groups:
            if group == BAR_COLOUR_GROUP:
                glyph, subtitle = "colour", "Fill, border and border opacity"
            elif group == RAINBOW_GROUP:
                glyph, subtitle = "gradient", "Hue drift across the bars"
            else:
                glyph, subtitle = _GROUP_PANEL.get(bucket_of.get(group, ""), ("bars", "Live analysis feeding Spectrum"))
            columns.append(WorkspaceColumn(group, (group,), glyph, subtitle))
        workspaces.append(Workspace(workspace_id, title, tuple(groups), open_groups=tuple(groups), icon=icon,
                                    help=help_text, columns=tuple(columns)))

    controls = {control.key: control for control in spec.controls}
    colours = {shared["bar_fill_color"], shared["bar_border_color"]}

    def admit(key: str, candidate: Any, previous: Any) -> Any:
        if key in technical:
            return admit_technical(technical[key], candidate, previous)
        if key in controls:
            return controls[key].admit(candidate, previous)
        if key == SHAPE_NODES:
            return _admit_nodes(candidate, previous)
        if key in NOTCHES.values():
            return _admit_notches(candidate, previous)
        if key in LANES.values():
            return _admit_lanes(candidate, previous)
        if key in colours:
            return _admit_colour(candidate, previous)
        if key == rainbow["rainbow_speed"]:
            return _percent(candidate, previous, low=0.01)
        if key in (border, PREFIX + "visual_smoothing"):
            return _percent(candidate, previous)
        if key in (MIRRORED, smoothing_on, rainbow["rainbow_enabled"]):
            return bool(candidate)
        raise KeyError(f"{key} is not a Spectrum Studio value")

    group_icons = {titles[key]: glyph for key, (glyph, _sub) in _GROUP_PANEL.items() if key in titles}
    group_icons.update({TECHNICAL_GROUP: "bars", BAR_COLOUR_GROUP: "colour", RAINBOW_GROUP: "gradient"})
    return StudioSchema(MODE, "Spectrum Studio", tuple(workspaces), tuple(props), admit,
                        group_traces=((titles["audio"], ("Level", "Peak")), (titles["ghost"], ("Ghost",)),
                                      (titles["render"], ("Level",))),
                        group_icons=tuple(group_icons.items()), object_noun="Bar")


# -------------------------------------------------------------------------------- inputs
@dataclass(frozen=True)
class ServedTick:
    """One production tick: its time, the playback flag and what the engine answered Spectrum's step (encoded)."""

    now: float
    playing: bool
    answers: Mapping[str, Any]


class RecordedInputs:
    """Engine answers for one source under one set of engine-owned values (``ui.studio.spectrum_recorded_inputs``)."""

    def __init__(self, fixture: StudioFixture, steps: tuple[ServedTick, ...], origin: float, *, source: str,
                 engine_values: Mapping[str, Any]) -> None:
        self.fixture = fixture
        self._steps = steps
        self._origin = origin
        self.source = source
        self.engine_values = dict(engine_values)
        self.key = (source, json.dumps(self.engine_values, sort_keys=True, default=repr))
        self._levels: list[float] | None = None

    def steps(self, until: float) -> Iterable[ServedTick]:
        limit = self._origin + until + 1e-9
        for step in self._steps:
            if step.now > limit:
                return
            yield step

    def levels(self) -> list[tuple[float, float]]:
        """(fixture time, mean engine bar) per tick, for the transport's overview."""
        if self._levels is None:
            from ui.studio.replay_engine import decode_answer
            out = []
            for step in self._steps:
                bars = decode_answer(step.answers.get("get_smoothed_bars", {"list": []})) or [0.0]
                out.append((step.now - self._origin, sum(bars) / len(bars)))
            self._levels = out
        return self._levels


class RestInputs:
    """No answers yet (the first analysis is running): Spectrum's paused, sourceless resting scene, which is what
    the card shows with no audio. Every getter then answers from the freshly configured engine."""

    def __init__(self, fixture: StudioFixture) -> None:
        self.fixture = fixture
        self._origin = 0.0
        self.source = ""
        self.engine_values: dict = {}
        self.key = ("", "")

    def steps(self, until: float) -> Iterable[ServedTick]:
        yield ServedTick(now=0.0, playing=False, answers={})

    def levels(self) -> list:
        return []


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


def synthetic_fixtures() -> tuple[StudioFixture, ...]:
    from ui.studio.spectrum_recorded_inputs import DURATION, SYNTHETIC
    kinds = {"reference": REFERENCE, "synthetic": SYNTHETIC}
    return tuple(StudioFixture(fixture_id, label, kinds[kind], DURATION, description)
                 for fixture_id, (label, kind, description) in SYNTHETIC.items())


def source_of(fixture: StudioFixture) -> str:
    """What the worker analyses for ``fixture``: a recorded clip's path, else ``synthetic:<id>``."""
    from ui.studio.spectrum_recorded_inputs import SYNTHETIC_PREFIX
    return fixture.description if fixture.kind == RECORDED else SYNTHETIC_PREFIX + fixture.id


def worker_loader(fixture: StudioFixture, values: Mapping[str, Any], finished: Callable[..., None]):
    """Analyse ``fixture``'s source out of process (``ClipLoadJob`` passes the description as the source)."""
    from dataclasses import replace
    from ui.studio.spectrum_recorded_inputs import to_inputs
    from ui.studio.waveform_recorded_inputs import ClipLoadJob
    return ClipLoadJob(replace(fixture, description=source_of(fixture)), values, finished, module=WORKER,
                       convert=to_inputs)


# Analysed answers for this process, keyed by (source, engine-owned values), newest last.
_ANALYSED: dict = {}
_ANALYSED_LIMIT = 24


def remember(inputs: RecordedInputs) -> None:
    _ANALYSED.pop(inputs.key, None)
    _ANALYSED[inputs.key] = inputs
    while len(_ANALYSED) > _ANALYSED_LIMIT:
        _ANALYSED.pop(next(iter(_ANALYSED)))


def analysed(key) -> RecordedInputs | None:
    return _ANALYSED.get(key)


# ------------------------------------------------------------------------------- evaluator
class SpectrumStudioEvaluator:
    """Spectrum's production step and capture, run in process from recorded engine answers.

    ``loader(fixture, values, finished)`` starts one analysis (default: the out-of-process worker) and returns a
    cancellable job, or None when it already called ``finished(inputs, error)``."""

    def __init__(self, loader: Callable | None = None) -> None:
        self._loader = loader or worker_loader
        self._builtin = synthetic_fixtures()
        self._clips: dict[str, StudioFixture] = {}
        self._fixture = next(f for f in self._builtin if f.id == "mid")
        self._inputs = None            # the inputs the current history replays
        self._controller = None
        self._engine = None
        self._view = None
        self._extent: tuple[float, float] | None = None
        self._invalidate: Callable[[], None] | None = None
        self._job = None
        self._job_key = None
        self.errors: dict = {}
        self._last_wanted = None
        self.steps_run = 0
        self.replays = 0
        self._reset_history()

    # fixtures ---------------------------------------------------------------
    def fixtures(self) -> tuple[StudioFixture, ...]:
        return self._builtin + tuple(self._clips.values())

    @property
    def fixture(self) -> StudioFixture:
        return self._fixture

    def add_recorded(self, inputs: RecordedInputs) -> None:
        """A recorded clip analysed through the controller's clip loader (``start_clip_load``)."""
        self._clips[inputs.fixture.id] = inputs.fixture
        remember(inputs)

    def select(self, fixture_id: str) -> StudioFixture:
        fixture = next((f for f in self.fixtures() if f.id == fixture_id), None)
        if fixture is None:
            raise KeyError(fixture_id)
        self._fixture = fixture
        self._retire()
        return fixture

    def set_viewport_extent(self, extent) -> None:
        """Spectrum's capture reads the card's presented height (segment count, height scale): a new extent replays
        the history at it. The engine answers do not depend on it."""
        extent = None if extent is None else (float(extent[0]), float(extent[1]))
        if extent != self._extent:
            self._extent = extent
            self._retire()

    def set_invalidate(self, callback: Callable[[], None] | None) -> None:
        """The Studio's re-evaluate request, called when a background analysis lands."""
        self._invalidate = callback

    @property
    def analysing(self) -> bool:
        return self._job is not None

    # analysis ----------------------------------------------------------------
    def _wanted(self, values: Mapping[str, Any]):
        return (source_of(self._fixture), engine_key(values))

    def _analyse(self, values: Mapping[str, Any], wanted) -> None:
        if self._job_key == wanted or wanted in self.errors:
            return
        self._cancel_job()
        fixture = self._fixture
        self._job_key = wanted

        def finished(result, error: str = "") -> None:
            if self._job_key != wanted:
                return
            self._job, self._job_key = None, None
            if error or result is None:
                self.errors[wanted] = error or "analysis failed"
                from core.logging.logger import get_logger
                get_logger(__name__).error("[STUDIO] Spectrum analysis of %s failed: %s", wanted[0],
                                           self.errors[wanted])
            else:
                remember(result)
            if self._invalidate is not None:
                self._invalidate()
        job = self._loader(fixture, dict(values), finished)
        if self._job_key == wanted:          # still running (a synchronous loader already finished)
            self._job = job

    def _cancel_job(self) -> None:
        job, self._job, self._job_key = self._job, None, None
        if job is not None:
            job.cancel()

    def _choose_inputs(self, values: Mapping[str, Any], exact: bool):
        wanted = self._wanted(values)
        self._last_wanted = wanted
        inputs = analysed(wanted)
        if inputs is None and (exact or self._inputs is None):
            self._analyse(values, wanted)
            inputs = analysed(wanted)
        if inputs is None:
            current = self._inputs
            if current is not None and current.source == wanted[0]:
                return current
            latest = [i for k, i in _ANALYSED.items() if k[0] == wanted[0]]
            return latest[-1] if latest else RestInputs(self._fixture)
        return inputs

    # lifecycle --------------------------------------------------------------
    def _reset_history(self) -> None:
        self._iterator = None
        self._pending: ServedTick | None = None
        self._time = -math.inf
        self._last = None
        self._last_tick: ServedTick | None = None
        self._signature = None
        self._approximate = False

    def _retire(self) -> None:
        controller, self._controller = self._controller, None
        if controller is not None:
            from widgets.spotify_visualizer.spectrum_frame_runtime import SpectrumFrameRuntime
            runtime = controller.peek_logical_mode_state(MODE)
            if isinstance(runtime, SpectrumFrameRuntime):
                runtime.retire()
        self._reset_history()

    def _effective(self, values: Mapping[str, Any], inputs) -> dict:
        """``values`` with the engine-owned values the answers were recorded under (an analysis still running
        keeps the previous answers *and* their configuration, so bar count and shape stay consistent)."""
        out = dict(values)
        out.update(inputs.engine_values)
        return out

    def _start(self, values: Mapping[str, Any], inputs) -> None:
        from widgets.spotify_visualizer.feature_replay import ReplayBeatEngine
        from ui.studio.replay_engine import RecordedEngineAnswers, offline_controller
        self._retire()
        if self._engine is None:
            self._engine = ReplayBeatEngine(32)
        controller = offline_controller(self._engine, MODE, resolved_settings(self._effective(values, inputs)))
        if self._extent is not None:
            controller.hydrate_committed_layout_metrics(self._extent, 0)
        if controller.active_logical_tick_hook is not None:
            raise RuntimeError("Spectrum gained a logical tick hook; the Studio step must call it")
        self._view = RecordedEngineAnswers(self._engine)
        controller.engine = self._view
        self._controller = controller
        self._inputs = inputs
        self._iterator = iter(inputs.steps(self.fixture.duration))
        self._signature = self._own_signature(values)
        self.replays += 1

    @staticmethod
    def _own_signature(values: Mapping[str, Any]):
        return tuple(repr(values.get(key)) for key in sorted(spectrum_owned_keys()))

    def _step(self, tick: ServedTick) -> None:
        """One production Spectrum tick: what ``tick_pipeline.logical_tick`` runs for a mode with no tick hook
        (``consume_engine_bars``, the teardown readiness query, the publication capture) at the tick's time."""
        from widgets.spotify_visualizer.logical_frame_capture import capture_visualizer_logical_frame
        from widgets.spotify_visualizer.tick_pipeline import consume_engine_bars
        controller = self._controller
        controller.playing = tick.playing
        self._view.serve(tick.answers)
        state = controller.logical_tick_state
        now = float(tick.now)
        changed, _any = consume_engine_bars(state, now)
        ready = bool(state._check_mode_teardown_ready(state._engine, now))
        if state._waiting_for_fresh_engine_frame or (state._mode_teardown_block_until_ready
                                                     and not state._mode_transition_ready):
            raise RuntimeError("The Studio step reached a fresh-frame fence the offline replay never arms")
        frame = capture_visualizer_logical_frame(state, now_ts=now, changed=changed, mode_reveal_ready=ready)
        self.steps_run += 1
        self._last_tick = tick
        if frame is not None:
            self._last = frame

    def _restyle(self, values: Mapping[str, Any]) -> None:
        from widgets.spotify_visualizer.config_applier import (
            apply_logical_vis_mode_kwargs, apply_presentation_vis_mode_kwargs,
        )
        kwargs = _mode_kwargs(self._effective(values, self._inputs))
        apply_logical_vis_mode_kwargs(self._controller.logical_tick_state, kwargs)
        apply_presentation_vis_mode_kwargs(self._controller.presentation_state, kwargs)
        self._signature = self._own_signature(values)

    def evaluate(self, time: float, values: Mapping[str, Any], *, exact: bool = True, revision: Any = None):
        """The logical frame ``time`` seconds into the fixture under ``values``: Spectrum's production step replayed
        from the fixture start over the engine answers for these engine-owned values (equal fixture, values, extent
        and time give equal frames). A Spectrum-owned change replays at once; an engine-owned change starts its
        analysis and shows the previous answers until it lands. ``exact=False`` (a live gesture) applies a
        Spectrum-owned change to the running history from the current tick; the gesture end replays exactly."""
        del revision
        time = max(0.0, min(float(time), self.fixture.duration))
        inputs = self._choose_inputs(values, exact)
        signature = self._own_signature(values)
        restart = (self._controller is None or inputs is not self._inputs or time < self._time
                   or (exact and (signature != self._signature or self._approximate)))
        restyled = False
        if restart:
            self._start(values, inputs)
        elif signature != self._signature:
            self._restyle(values)
            self._approximate = restyled = True
        origin = inputs._origin
        stepped = 0
        while True:
            tick = self._pending if self._pending is not None else next(self._iterator, None)
            self._pending = None
            if tick is None or (tick.now - origin > time + 1e-9 and self._last is not None):
                self._pending = tick
                break
            self._step(tick)
            stepped += 1
        if restyled and not stepped and self._last_tick is not None:
            self._step(self._last_tick)            # show the change on this instant (approximate)
        self._time = time
        if self._last is None:
            raise RuntimeError("Fixture produced no logical frame")
        return self._last

    @property
    def unrecorded_reads(self) -> int:
        """Engine reads the record lacked in this history (``RecordedEngineAnswers.unrecorded``)."""
        return 0 if self._view is None else int(self._view.unrecorded)

    def _overview(self):
        """The answers the transport's overview shows: those wanted for the current values once they landed."""
        wanted = self._last_wanted
        inputs = analysed(wanted) if wanted is not None and wanted[0] == source_of(self._fixture) else None
        current = self._inputs
        if inputs is None and current is not None and current.source == source_of(self._fixture):
            inputs = current
        return inputs

    @property
    def timeline_revision(self):
        overview = self._overview()
        return None if overview is None else overview.key

    def timeline(self, samples: int = 240) -> list[float]:
        duration = max(1e-6, self.fixture.duration)
        levels = [0.0] * samples
        source = self._overview()
        for t, level in (source.levels() if source is not None else ()):
            if 0.0 <= t <= duration:
                index = min(samples - 1, int(t / duration * samples))
                levels[index] = max(levels[index], level)
        peak = max(levels) or 1.0
        return [round(v / peak, 4) for v in levels]

    def measurements(self) -> dict[str, dict[str, float]]:
        frame = self._last
        if frame is None:
            return {"sources": {}, "targets": {}, "signals": {}}
        bars = frame.common.bars or (0.0,)
        peaks = frame.mode_state.peaks or (0.0,)
        ghosts = frame.mode_state.ghost_bars or (0.0,)
        return {"sources": {}, "targets": {}, "signals": {
            "Level": sum(bars) / len(bars), "Peak": max(peaks), "Ghost": sum(ghosts) / len(ghosts)}}

    def release(self) -> None:
        self._cancel_job()
        self._retire()
        self._invalidate = None
        engine, self._engine = self._engine, None
        if engine is not None:
            try:
                engine.force_stop()
            except Exception:
                pass
            engine.deleteLater()


# ------------------------------------------------------------------------------- renderer
class SpectrumStudioRenderer(framed.ContractModeRenderer):
    """The production ``QuickSpectrumRenderer`` handed the production render-frame contract (the full logical
    frame: common bars and style plus the Spectrum frame), the live card's presentation and the item mapping."""

    def __init__(self) -> None:
        from rendering.quick.visualizer.implementations.spectrum import create_visualizer_renderer
        super().__init__(MODE, create_visualizer_renderer)


# --------------------------------------------------------------------------------- adapter
class SpectrumStudioAdapter(StudioModeAdapter):
    mode_id = MODE
    title = "Spectrum Studio"

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

    def create_evaluator(self) -> SpectrumStudioEvaluator:
        return SpectrumStudioEvaluator()

    def create_renderer(self):
        return SpectrumStudioRenderer()

    def framings(self, card_extent, card_style=None):
        return framed.card_framings(card_extent, card_style)

    def default_framing(self) -> str:
        return "fill"           # the live card's world and scale, filling the viewport; Live Card is exact

    def default_fixture(self, evaluator) -> str | None:
        return "mid"

    def recorded_clips(self) -> tuple[StudioFixture, ...]:
        """The Studios' shared recorded music (the shipped clips first, then a checkout's recordings)."""
        from ui.studio.waveform_adapter import recordings_directory
        from ui.studio.waveform_recorded_inputs import studio_clips
        return studio_clips(recordings_directory())

    def start_clip_load(self, clip: StudioFixture, values: Mapping[str, Any], finished):
        """Analyse ``clip`` under ``values``' engine-owned settings out of process (cached per engine values)."""
        cached = analysed((source_of(clip), engine_key(values)))
        if cached is not None:
            finished(cached, "")
            return None

        def remembered(result, error=""):
            if result is not None and not error:
                remember(result)
            finished(result, error)
        return worker_loader(clip, values, remembered)


__all__ = [
    "RecordedInputs", "RestInputs", "ServedTick", "SpectrumStudioAdapter", "SpectrumStudioEvaluator",
    "SpectrumStudioRenderer", "build_schema", "engine_key", "engine_values", "resolved_settings",
    "spectrum_owned_keys", "synthetic_fixtures",
]
