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

The recorder, inputs and evaluator are the Spectrum family's shared ``ui.studio.engine_answers`` and the shape (its
rules and its instrument) ``ui.studio.spectrum_shape``; this module supplies Spectrum's schema and names.
"""
from __future__ import annotations

import math
from functools import cache
from typing import Any, Callable, Mapping

from core.settings.visualizer_mode_settings import Choice, Colour, Custom, Slider, Toggle, require_mode_settings
from ui.studio import engine_answers, framed, spectrum_shape
from ui.studio.registry import studio_title
from ui.studio.adapter import StudioCapabilities, StudioFixture, StudioModeAdapter, control_condition
from ui.studio.engine_answers import (  # noqa: F401  (re-exported: Spectrum's evaluator inputs)
    EngineAnswerEvaluator, EngineAnswerMode, RecordedInputs, RestInputs, ServedTick, source_of, synthetic_fixtures,
)
from ui.studio.schema import (
    CHOICE, COLOUR, SCALAR, SWITCH, StudioProperty, StudioSchema, Workspace, WorkspaceColumn,
)
from ui.studio.spectrum_shape import (  # noqa: F401  (re-exported: Spectrum's structural action ids)
    ADD_NODE, LANE_NEXT, LANE_PREVIOUS, REMOVE_NODE, ShapeKeys, added_node,
)
from ui.studio.technical import TECHNICAL_GROUP, admit_technical, technical_properties

MODE = "spectrum"
PREFIX = "spectrum_"
SPECTRUM = EngineAnswerMode(MODE)
WORKER = SPECTRUM.worker
SHAPE = ShapeKeys(PREFIX)
SHAPE_NODES = SHAPE.nodes
MIRRORED = SHAPE.mirrored
NOTCHES = SHAPE.notches
LANES = SHAPE.lanes
RAINBOW_GROUP = "Rainbow"
BAR_COLOUR_GROUP = "Bar Colours"

_BUCKET_WORKSPACE = {"render": "bars", "appearance": "colour", "ghost": "colour", "shape": "shape", "audio": "shape",
                     "finish": "finish", "pattern": "finish"}
_WORKSPACES = (
    ("bars", "Bars", "bars", "How the bars are drawn: segments or solid bars, their colours, corners and smoothing."),
    ("colour", "Colour & Ghosts", "palette", "Rim glow, the rainbow and the falling peak ghosts (Rainbow Ghost "
                                             "or their own colour and gradient)."),
    ("finish", "Pattern & Finish", "material", "Optional extras on the bars: a second-colour pattern, a fill "
                                               "gradient, gloss and peak caps."),
    ("shape", "Shape & Response", "wave", "The authored silhouette, its frequency lanes and how hard the music "
                                          "drives them, and the audio analysis feeding the bars."),
)
_GROUP_PANEL = {
    "render": ("bars", "Bars, corners and smoothing"), "appearance": ("sparkle", "Rim glow"),
    "ghost": ("sparkle", "Falling peak trails"), "shape": ("wave", "Silhouette and frequency lanes"),
    "audio": ("bolt", "Reactivity and falloff"), "finish": ("material", "Fill gradient, gloss and peak caps"),
    "pattern": ("grid", "A second colour over the fill"),
}
_PRIORITY = {PREFIX + key: rank for rank, key in enumerate((
    "render_mode", "bar_fill_color", "bar_border_color", "bar_border_opacity", "border_radius",
    "bar_gap", "visual_smoothing_enabled", "visual_smoothing", "rainbow_enabled", "rainbow_speed", "unique_colors",
    "rainbow_fill", "rainbow_border", "ghosting_enabled", "rainbow_ghost", "ghost_alpha", "ghost_decay",
    "ghost_color_source", "ghost_color", "ghost_color.3", "ghost_gradient", "ghost_tip_color", "ghost_tip_color.3",
    "pattern", "pattern_anchor", "pattern_color", "pattern_color.3", "pattern_scale", "pattern_strength", "fill_gradient",
    "fill_tip_color", "fill_tip_color.3", "gloss", "peak_caps", "peak_cap_color", "peak_cap_color.3",
    "peak_cap_thickness", "glow_enabled", "glow_color", "glow_intensity", "mirrored", "wave_amplitude", "profile_floor", "drop_speed"))}
_ROW_ICONS = {"render_mode": "bars", "bar_fill_color": "colour", "bar_border_color": "colour",
              "glow_color": "colour", "rainbow_ghost": "sparkle", "ghosting_enabled": "sparkle",
              "rainbow_enabled": "gradient", "wave_amplitude": "bolt", "drop_speed": "height", "mirrored": "wave",
              "ghost_color": "colour", "ghost_tip_color": "colour", "pattern": "grid", "pattern_color": "colour",
              "fill_tip_color": "colour", "fill_gradient": "gradient", "peak_cap_color": "colour",
              "peak_caps": "height", "gloss": "sun"}
_RENDER_LABELS = {"segment": "Segments", "bars": "Bars"}


def _label(text: str) -> str:
    return str(text).rstrip(":").strip()


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
    row and the mode's shared bar-colour and rainbow families (``EngineAnswerMode.owned_keys``). Anything else
    Spectrum stores is engine-owned."""
    return SPECTRUM.owned_keys()


def engine_values(values: Mapping[str, Any]) -> dict:
    """The engine-owned subset of ``values``: the mode's stored keys (its descriptor prefixes) that Spectrum's own
    step does not read. The recorded answers depend on exactly these (``tests/test_spectrum_studio.py`` proves both
    directions on the production replay)."""
    return SPECTRUM.engine_values(values)


def engine_key(values: Mapping[str, Any]) -> str:
    return SPECTRUM.engine_key(values)


def structure_edit(action_id: str, values: Mapping[str, Any]):
    """Spectrum's shape-editor structural edits (``spectrum_shape.structure_edit``)."""
    return spectrum_shape.structure_edit(SHAPE, action_id, values)


# ---------------------------------------------------------------------------------- schema
def build_schema() -> StudioSchema:
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

    for control in spec.body_controls:
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
    opacity = spec.control(border)                      # ranges from the spec's shared-family entries
    add(border, (border,), "Border Opacity", "bars", BAR_COLOUR_GROUP, SCALAR, minimum=opacity.low,
        maximum=opacity.high, decimals=2, tooltip=opacity.tooltip)
    rainbow = _family_keys("rainbow")
    speed = spec.control(rainbow["rainbow_speed"])
    add(rainbow["rainbow_enabled"], (rainbow["rainbow_enabled"],), "Taste the Rainbow", "colour", RAINBOW_GROUP,
        SWITCH, tooltip="Slowly shift the hue of the bars through the spectrum. Saved per visualizer mode.")
    add(rainbow["rainbow_speed"], (rainbow["rainbow_speed"],), "Rainbow Speed", "colour", RAINBOW_GROUP, SCALAR,
        minimum=speed.low, maximum=speed.high, decimals=2, when=((rainbow["rainbow_enabled"], (True,)),),
        tooltip=speed.tooltip)

    # The shape (Custom): the layout switch and the shape instrument (curve nodes, frequency lanes and strengths).
    shape = titles["shape"]
    shape_spec = spectrum_shape.shape_properties(SHAPE, add, "shape", shape)

    technical = technical_properties(MODE, workspace="shape")
    props.extend(prop for prop, _defn in technical.values())
    placed["shape"].append(TECHNICAL_GROUP)

    bucket_of = {title: key for key, title in titles.items()}
    order = {key: rank for rank, key in enumerate(("render", "appearance", "ghost", "pattern", "finish", "shape",
                                                   "audio"))}
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

    controls = {control.key: control for control in spec.controls}     # the shared families included

    def admit(key: str, candidate: Any, previous: Any) -> Any:
        if key in technical:
            return admit_technical(technical[key], candidate, previous)
        if key in controls:
            return controls[key].admit(candidate, previous)
        shaped = spectrum_shape.admit_shape(SHAPE, key, candidate, previous)
        if shaped is not NotImplemented:
            return shaped
        if key == PREFIX + "visual_smoothing":
            return spectrum_shape.percent(candidate, previous)
        if key == smoothing_on:
            return bool(candidate)
        raise KeyError(f"{key} is not a Spectrum Studio value")

    group_icons = {titles[key]: glyph for key, (glyph, _sub) in _GROUP_PANEL.items() if key in titles}
    group_icons.update({TECHNICAL_GROUP: "bars", BAR_COLOUR_GROUP: "colour", RAINBOW_GROUP: "gradient"})
    return StudioSchema(MODE, studio_title(MODE), tuple(workspaces), tuple(props), admit,
                        group_traces=((titles["audio"], ("Level", "Peak")), (titles["ghost"], ("Ghost",)),
                                      (titles["render"], ("Level",))),
                        group_icons=tuple(group_icons.items()), object_noun="Bar", shapes=(shape_spec,))


# ------------------------------------------------------------------------------- evaluator
def resolved_settings(values: Mapping[str, Any]) -> dict:
    return SPECTRUM.resolved_settings(values)


def worker_loader(fixture: StudioFixture, values: Mapping[str, Any], finished: Callable[..., None]):
    """Analyse ``fixture``'s source out of process (``ClipLoadJob`` passes the description as the source)."""
    return engine_answers.worker_loader(SPECTRUM)(fixture, values, finished)


# Analysed answers for this process, keyed by (source, engine-owned values), newest last.
_ANALYSED = engine_answers.analysed_cache(MODE)


def remember(inputs: RecordedInputs) -> None:
    engine_answers.remember(MODE, inputs)


def analysed(key) -> RecordedInputs | None:
    return engine_answers.analysed(MODE, key)


class SpectrumStudioEvaluator(EngineAnswerEvaluator):
    """Spectrum's production step and capture, run in process from recorded engine answers
    (``engine_answers.EngineAnswerEvaluator``)."""

    def __init__(self, loader: Callable | None = None) -> None:
        super().__init__(SPECTRUM, loader)


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

    def structure_edit(self, action_id: str, values: Mapping[str, Any]):
        return structure_edit(action_id, values)

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
        return engine_answers.start_clip_load(SPECTRUM, clip, values, finished)


__all__ = [
    "RecordedInputs", "RestInputs", "ServedTick", "SpectrumStudioAdapter", "SpectrumStudioEvaluator",
    "SpectrumStudioRenderer", "build_schema", "engine_key", "engine_values", "resolved_settings",
    "spectrum_owned_keys", "synthetic_fixtures",
]
