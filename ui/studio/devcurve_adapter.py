"""DevCurve's Studio adapter: schema, evaluator, fixtures and renderer, on the shared Studio framework.

Truthfulness: the Studio changes no DevCurve solver, timing, engine or render code and re-implements none of it.

* **Engine answers, out of process.** DevCurve's step (its logical tick hook ``tick_pipeline.dispatch_devcurve_field``
  feeding ``DevCurveFrameRuntime.advance`` and the solver ``devcurve_runtime.solve_devcurve_frame``) reads the beat
  engine's live answers every tick: the pre-AGC control lanes (each band's share), the transient lanes, the musical
  level (the bus loudness that turns a share into a level) and intensity (the passage), and the authoritative source
  frame. The engine produces them from the audio on the process clock, configured by the technical analysis. So
  DevCurve uses the shared recorded engine answers (``ui.studio.engine_answers``): the worker
  ``ui.studio.devcurve_recorded_inputs`` replays the source (a recorded clip, or generated audio for the synthetic
  Quiet / Mid / Peak fixtures) through the production offline replay in a separate process and records every
  answer the engine gave the tick; the Studio runs the production tick in process from those answers
  (``consume_engine_bars``, the DevCurve hook, the production capture).
* **Two owners.** The technical (audio analysis) values configure the engine: **engine-owned**, an edit re-runs the
  worker while the previous answers stay on screen. Everything else DevCurve stores (the layers and their shapes,
  Core, Foreground FX, Ghost, the rainbow) is read by its own step, capture or renderer: **DevCurve-owned**, exact
  and instant (``EngineAnswerMode.owned_keys``, proven in both directions by ``tests/test_devcurve_studio.py``).
* **Reactivity traces.** Each layer's group traces its **Body** (the slow, self-normalised passage height, over its
  body top) and **Accent** (the kicks and hits in the reserved headroom, over its accent room) drives and its
  travelling **Swell** (the envelope's peak gain over 1 in view); Core traces the passage drive, the visible reaction
  (mean undulation over its geometric ceiling) and the strongest swell; Audio Analysis the band shares and loudness
  the step was served. All are read-only Studio reads of the evaluator's own runtime and served answers: the saver
  does no work for them.
* The production ``QuickDevCurveRenderer`` draws the resulting ``VisualizerLogicalFrame`` at the live card's
  presentation (Fill by default).

The schema follows DevCurve's Settings buckets: Shaper (one group per layer, Settings' Custom layer row and shape
editor), Core with the technical analysis, and Foreground FX / Ghost with the rainbow.
"""
from __future__ import annotations

import math
from functools import cache
from typing import Any, Callable, Mapping

from core.settings.visualizer_mode_settings import Choice, Colour, Slider, Toggle, require_mode_settings
from ui.studio import engine_answers, framed, spectrum_shape
from ui.studio.adapter import StudioCapabilities, StudioFixture, StudioModeAdapter, control_condition
from ui.studio.engine_answers import EngineAnswerEvaluator, EngineAnswerMode
from ui.studio.schema import (
    CHOICE, COLOUR, COUNT, SCALAR, SWITCH, StudioAction, StudioProperty, StudioSchema, Workspace, WorkspaceColumn,
)
from ui.studio.technical import TECHNICAL_GROUP, admit_technical, technical_properties

MODE = "devcurve"
PREFIX = "devcurve_"
DEVCURVE = EngineAnswerMode(MODE, production_lanes=True)
ACTIVE_LAYER = PREFIX + "active_layer"
RAINBOW_GROUP = "Rainbow"
ADD_NODE = "devcurve.add_node."            # + layer
REMOVE_NODE = "devcurve.remove_node."      # + layer + "." + node index

_BUCKET_WORKSPACE = {"shaper": "shaper", "core": "core", "foreground_fx": "finish", "ghost": "finish"}
_WORKSPACES = (
    ("shaper", "Layers", "wave", "The four curve layers: each one's shape, power, place in the stack and colours, "
                                 "and how its body and accents react to the music."),
    ("core", "Motion & Swell", "bolt", "Global motion power, idle wobble, smoothness and the travelling swell, and "
                                       "the audio analysis feeding every layer."),
    ("finish", "Foreground & Ghost", "sparkle", "The foreground layer's shadow and specular highlight, the trail "
                                                "and the rainbow."),
)
_GROUP_PANEL = {
    "shaper": ("wave", "Which layer Settings edits"), "core": ("bolt", "Power, idle motion and swell"),
    "foreground_fx": ("sparkle", "Shadow and specular"), "ghost": ("sparkle", "Motion trail"),
}
_PRIORITY = {PREFIX + key: rank for rank, key in enumerate((
    "motion_power", "swell_strength", "swell_speed", "smoothness", "base_level", "idle_motion", "idle_speed",
    "foreground_shadow_enabled", "foreground_shadow_alpha", "foreground_shadow_darken", "foreground_shadow_offset",
    "foreground_specular_enabled", "foreground_specular_alpha", "foreground_specular_width",
    "foreground_specular_offset", "foreground_specular_crest_bias", "ghosting_enabled", "ghost_alpha",
    "ghost_decay"))}
_ROW_ICONS = {"motion_power": "bolt", "swell_strength": "wave", "swell_speed": "flow", "smoothness": "wave",
              "base_level": "height", "idle_motion": "wave", "idle_speed": "flow",
              "foreground_shadow_enabled": "floor", "foreground_specular_enabled": "sun",
              "ghosting_enabled": "sparkle"}
# Per-layer rows (Settings' Custom layer row): suffix -> (label, priority, icon).
_LAYER_ROWS = {"enabled": ("Enabled", 0, ""), "power": ("Power", 1, "bolt"), "offset": ("Offset", 2, "height"),
               "order": ("Order", 3, "grid"), "alpha": ("Alpha", 4, ""), "color": ("Color", 5, "colour"),
               "outline_color": ("Outline Color", 7, "colour"), "outline_width": ("Outline Width", 8, "")}
# Each layer's trace channels ("<Layer> Body", ...); body and accent are traced over the solver's own body top and
# accent room (read in ``DevCurveStudioEvaluator.measurements``).
TRACE_LAYERS = ("Body", "Accent", "Swell")


def _label(text: str) -> str:
    return str(text).rstrip(":").strip()


# DevCurve's layers in their stored order, their titles and the row tooltips (formerly Settings' Shaper).
_LAYER_ORDER = ("bass", "vocals", "mids", "transients")
_LAYER_LABEL = {"bass": "Bass", "vocals": "Vocals", "mids": "Mids", "transients": "Transients"}
_LAYER_TIPS = {
    "enabled": "Enable/disable this layer's rendering and audio response.",
    "alpha": "Fill opacity for this layer only.",
    "offset": "Vertical lane offset for this layer before audio deformation.",
    "order": "Layer stack order. Higher numbers render on top of lower numbers.",
    "color": "Fill colour of this layer.",
    "outline_color": "Outline colour of this layer. Outline alpha is always fully opaque.",
    "outline_width": "Outline thickness of this layer.",
    "power": "How strongly the music drives this layer.",
}
# Nodes per layer contour (the production solver needs at least two).
_MIN_NODES, _MAX_NODES = 2, 5


def layers() -> tuple[str, ...]:
    """DevCurve's layers in their stored order."""
    return tuple(_LAYER_ORDER)


def layer_label(layer: str) -> str:
    return _LAYER_LABEL[layer]


def layer_key(layer: str, suffix: str) -> str:
    return f"{PREFIX}layer_{layer}_{suffix}"


def node_limits() -> tuple[int, int]:
    """The node range per layer, never below the two the production solver needs
    (``DevCurveFrameRuntime.advance`` refuses fewer)."""
    return max(2, int(_MIN_NODES)), int(_MAX_NODES)


def _family_keys(family: str) -> dict[str, str]:
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    return get_owned_mode_setting_keys(MODE, family)


@cache
def owned_keys() -> frozenset[str]:
    """Settings DevCurve's own step, capture or renderer reads (``EngineAnswerMode.owned_keys``)."""
    return DEVCURVE.owned_keys()


def engine_values(values: Mapping[str, Any]) -> dict:
    """The engine-owned subset of ``values`` (the technical analysis): the recorded answers depend on exactly these."""
    return DEVCURVE.engine_values(values)


def engine_key(values: Mapping[str, Any]) -> str:
    return DEVCURVE.engine_key(values)


# ------------------------------------------------------------------------------- admission
def _number(value: Any, previous: Any, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(previous)
    return max(low, min(high, number)) if math.isfinite(number) else float(previous)


def admit_nodes(candidate: Any, previous: Any, fallback: str) -> list:
    """The shape editor's rules (nodes [x, y] in 0..1, kept in x order, at most five) with the solver's minimum of
    two. A moved node stops at its neighbours (Settings re-sorts a node dragged past one; a Studio slider keeps
    addressing the same node)."""
    low, high = node_limits()
    try:
        old = [[float(x), float(y)] for x, y in previous]
    except (TypeError, ValueError):
        old = [list(map(float, node)) for node in spectrum_shape.canonical(fallback)]
    try:
        new = [[spectrum_shape.unit(x, 0.0), spectrum_shape.unit(y, 0.0)] for x, y in candidate]
    except (TypeError, ValueError):
        return old
    if not low <= len(new) <= high:
        return old
    if len(new) == len(old):
        for index, (node, before) in enumerate(zip(new, old)):
            if abs(node[0] - before[0]) > 1e-12:
                left = new[index - 1][0] if index > 0 else 0.0
                right = new[index + 1][0] if index + 1 < len(new) else 1.0
                node[0] = max(left, min(right, node[0]))
    return sorted(new, key=lambda node: node[0])


def _admit_layer(suffix: str, key: str, candidate: Any, previous: Any) -> Any:
    """One layer value as it is stored (the former Settings layer row's resolution): percent sliders in
    hundredths, the outline width in thousandths of 1..20, the outline opaque, the order 1..4."""
    if suffix == "enabled":
        return bool(candidate)
    if suffix == "alpha":
        return round(_number(candidate, previous, 0.0, 1.0), 2)
    if suffix == "offset":
        return round(_number(candidate, previous, -0.45, 0.45), 2)
    if suffix == "power":
        return _number(candidate, previous, 0.0, 3.0)
    if suffix == "order":
        return int(round(_number(candidate, previous, 1.0, 4.0)))
    if suffix == "outline_width":
        return round(_number(candidate, previous, 0.001, 0.020) * 1000.0) / 1000.0
    if suffix == "color":
        return spectrum_shape.admit_colour(candidate, previous)
    if suffix == "outline_color":
        return spectrum_shape.admit_colour(candidate, previous)[:3] + [255]
    if suffix == "shape_nodes":
        return admit_nodes(candidate, previous, key)
    raise KeyError(key)


def normalized_orders(values: Mapping[str, Any], target: str | None = None, rank: int | None = None) -> dict:
    """The stack normalisation (the former Settings shaper's): enabled layers take ranks 1..n
    in their order (``target`` moved to ``rank`` when given), disabled layers follow in theirs."""
    names = layers()
    enabled = [name for name in names if bool(values.get(layer_key(name, "enabled")))]
    disabled = [name for name in names if name not in enabled]

    def order(name):
        return int(values.get(layer_key(name, "order"), 0))
    ordered = sorted(enabled, key=order)
    if target in ordered and rank is not None:
        ordered.remove(target)
        ordered.insert(max(1, min(len(ordered) + 1, int(rank))) - 1, target)
    out = {layer_key(name, "order"): index for index, name in enumerate(ordered, start=1)}
    out.update({layer_key(name, "order"): index
                for index, name in enumerate(sorted(disabled, key=order), start=len(ordered) + 1)})
    return out


def follow(key: str, value: Any, values: Mapping[str, Any]) -> dict:
    """Settings' coupling: changing a layer's order or switching a layer re-ranks the whole stack."""
    for name in layers():
        if key == layer_key(name, "order"):
            current = dict(values)
            current[key] = value
            return normalized_orders(current, name, int(value))
        if key == layer_key(name, "enabled"):
            current = dict(values)
            current[key] = bool(value)
            return normalized_orders(current, name)
    return {}


# --------------------------------------------------------------------------- structural edits
def added_node(nodes) -> list:
    """Settings adds a node where the user clicks; the Studio adds one in the middle of the widest gap (the ends
    included) on the layer's current contour (the solver's own ``_smooth_points``), so the shape barely changes until
    the node is moved."""
    from widgets.spotify_visualizer.devcurve_runtime import _smooth_points
    current = [[float(x), float(y)] for x, y in nodes]
    xs = [0.0] + [x for x, _y in current] + [1.0]
    width, left = max((xs[i + 1] - xs[i], xs[i]) for i in range(len(xs) - 1))
    x = left + width / 2.0
    samples = 1001
    y = _smooth_points(current, samples)[int(round(x * (samples - 1)))]
    return sorted(current + [[x, max(0.0, min(1.0, float(y)))]], key=lambda n: n[0])


def structure_edit(action_id: str, values: Mapping[str, Any]):
    """(undo label, {path: value}) for Add / Remove Node on one layer, or None while not admissible."""
    low, high = node_limits()
    if action_id.startswith(ADD_NODE):
        name = action_id[len(ADD_NODE):]
        if name not in layers():
            return None
        key = layer_key(name, "shape_nodes")
        nodes = [[float(x), float(y)] for x, y in values.get(key, ())]
        return (f"Add {layer_label(name)} Node", {(key,): added_node(nodes)}) if len(nodes) < high else None
    if action_id.startswith(REMOVE_NODE):
        name, _dot, index_text = action_id[len(REMOVE_NODE):].partition(".")
        if name not in layers() or not index_text.isdigit():
            return None
        key, index = layer_key(name, "shape_nodes"), int(index_text)
        nodes = [[float(x), float(y)] for x, y in values.get(key, ())]
        if len(nodes) <= low or not 0 <= index < len(nodes):
            return None
        return f"Remove {layer_label(name)} Node {index + 1}", {(key,): nodes[:index] + nodes[index + 1:]}
    return None


# ------------------------------------------------------------------------------------ schema
def _layer_properties(name: str, add: Callable[..., None]) -> None:
    """One layer's rows (Settings' Custom layer row and its shape-editor nodes) in that layer's own group."""
    group = layer_label(name)
    tips = _LAYER_TIPS
    for suffix, (label, priority, icon) in _LAYER_ROWS.items():
        key = layer_key(name, suffix)
        common = dict(tooltip=tips[suffix], priority=priority, icon=icon)
        if suffix == "enabled":
            add(key, (key,), label, "shaper", group, SWITCH, **common)
        elif suffix == "order":
            add(key, (key,), label, "shaper", group, COUNT, minimum=1.0, maximum=4.0, decimals=0, integer=True,
                when=((layer_key(name, "enabled"), (True,)),), **common)
        elif suffix in ("color", "outline_color"):
            add(key, (key,), label, "shaper", group, COLOUR, **common)
            if suffix == "color":
                add(f"{key}.3", (key, 3), "Color Opacity", "shaper", group, SCALAR, minimum=0.0, maximum=255.0,
                    decimals=0, integer=True, tooltip="The layer colour's own opacity.", priority=priority + 1)
        else:
            low, high, decimals = {"power": (0.0, 3.0, 2), "offset": (-0.45, 0.45, 2), "alpha": (0.0, 1.0, 2),
                                   "outline_width": (0.001, 0.020, 3)}[suffix]
            add(key, (key,), label, "shaper", group, SCALAR, minimum=low, maximum=high, decimals=decimals, **common)
    key = layer_key(name, "shape_nodes")
    _low, high = node_limits()
    for index in range(high):
        for axis, word in ((0, "Position"), (1, "Height")):
            remove = (StudioAction(f"{REMOVE_NODE}{name}.{index}", f"Remove Node {index + 1}", "minus",
                                   "Remove this node (the shape keeps at least two)."),) if axis == 0 else ()
            add(f"{key}.{index}.{axis}", (key, index, axis), f"Node {index + 1} {word}", "shaper", group, SCALAR,
                minimum=0.0, maximum=1.0, decimals=3, priority=200 + 2 * index + axis, actions=remove,
                tooltip="A control node of this layer's resting contour (across the card, then its height). A node "
                        "stops at its neighbours; Add Node adds one in the widest gap.")


def build_schema() -> StudioSchema:
    spec = require_mode_settings(MODE)
    titles = {bucket.key: bucket.title for bucket in spec.buckets}
    props: list[StudioProperty] = []
    placed: dict[str, list[str]] = {w[0]: [] for w in _WORKSPACES}

    def add(prop_id, path, label, workspace, group, instrument, **extra):
        if group not in placed[workspace]:
            placed[workspace].append(group)
        props.append(StudioProperty(id=prop_id, path=path, label=label, workspace=workspace, group=group,
                                    instrument=instrument, **extra))

    for control in spec.body_controls:
        if not control.bucket:
            continue                              # (none today: the coverage test names any that appear)
        workspace = _BUCKET_WORKSPACE.get(control.bucket, "finish")   # an unplaced new bucket still appears
        group = titles.get(control.bucket, control.bucket)
        text = control.text if isinstance(control, Toggle) else ""
        label = _label(control.label) or _label(text) or control.key
        common = dict(tooltip=getattr(control, "tooltip", ""), when=control_condition(control),
                      priority=_PRIORITY.get(control.key, 100), icon=_ROW_ICONS.get(control.key[len(PREFIX):], ""))
        if isinstance(control, Slider):
            decimals = 0 if control.integer else max(control.decimals, 2)
            add(control.key, (control.key,), label, workspace, group, SCALAR, minimum=control.low,
                maximum=control.high, decimals=decimals, units="" if control.percent else control.suffix,
                integer=control.integer, **common)
        elif isinstance(control, Toggle):
            add(control.key, (control.key,), label, workspace, group, SWITCH, **common)
        elif isinstance(control, Choice):
            shown = tuple(control.labels or control.choices)
            stored = tuple(control.choices) if control.labels else (
                tuple(range(len(control.choices))) if control.indexed else ())
            add(control.key, (control.key,), label, workspace, group, CHOICE, choices=shown, choice_values=stored,
                **common)
        elif isinstance(control, Colour):
            add(control.key, (control.key,), label, workspace, group, COLOUR, **common)
        # Any other control type is deliberately not guessed at: the full-coverage test names it.

    # The Shaper bucket: the stored edit layer, then one group per layer.
    shaper = titles.get("shaper", "Shaper")
    names = layers()
    add(ACTIVE_LAYER, (ACTIVE_LAYER,), "Edit Layer", "shaper", shaper, CHOICE,
        choices=tuple(layer_label(n) for n in names), choice_values=names, priority=0, icon="wave",
        tooltip="The layer a preset marks for editing. It changes nothing on screen; every layer is edited here.")
    for name in names:
        _layer_properties(name, add)

    rainbow = _family_keys("rainbow")
    if rainbow:
        add(rainbow["rainbow_enabled"], (rainbow["rainbow_enabled"],), "Taste the Rainbow", "finish", RAINBOW_GROUP,
            SWITCH, tooltip="Slowly shift the hue of the curves through the spectrum. Saved per visualizer mode.")
        speed = spec.control(rainbow["rainbow_speed"])     # range from the spec's shared-family entries
        add(rainbow["rainbow_speed"], (rainbow["rainbow_speed"],), "Rainbow Speed", "finish", RAINBOW_GROUP, SCALAR,
            minimum=speed.low, maximum=speed.high, decimals=2, when=((rainbow["rainbow_enabled"], (True,)),),
            tooltip="How fast the hue cycles through the spectrum.")

    technical = technical_properties(MODE, workspace="core")
    props.extend(prop for prop, _defn in technical.values())
    placed["core"].append(TECHNICAL_GROUP)

    bucket_of = {title: key for key, title in titles.items()}
    workspaces = []
    for workspace_id, title, icon, help_text in _WORKSPACES:
        groups = tuple(placed[workspace_id])
        if not groups:
            continue
        if workspace_id == "shaper":
            # Four layer panels; the Settings Edit Layer choice heads the first.
            layer_groups = [g for g in groups if g != shaper]
            columns = tuple(WorkspaceColumn(g, ((shaper, g) if i == 0 and shaper in groups else (g,)), "wave",
                                            "Shape, power, stack and colours")
                            for i, g in enumerate(layer_groups))
        else:
            columns = []
            for group in groups:
                if group == RAINBOW_GROUP:
                    glyph, subtitle = "gradient", "Hue drift across the curves"
                else:
                    glyph, subtitle = _GROUP_PANEL.get(bucket_of.get(group, ""),
                                                       ("bars", "Live analysis feeding every layer"))
                columns.append(WorkspaceColumn(group, (group,), glyph, subtitle))
            columns = tuple(columns)
        workspaces.append(Workspace(workspace_id, title, groups, open_groups=groups, icon=icon, help=help_text,
                                    columns=columns))

    controls = {control.key: control for control in spec.controls}
    layer_suffix = {layer_key(n, s): s for n in names for s in (*_LAYER_ROWS, "shape_nodes")}

    def admit(key: str, candidate: Any, previous: Any) -> Any:
        if key in technical:
            return admit_technical(technical[key], candidate, previous)
        if key in controls:
            return controls[key].admit(candidate, previous)
        if key in layer_suffix:
            return _admit_layer(layer_suffix[key], key, candidate, previous)
        if key == ACTIVE_LAYER:
            text = str(candidate).strip().lower()
            return text if text in names else str(previous)
        raise KeyError(f"{key} is not a DevCurve Studio value")

    group_icons = {titles[key]: glyph for key, (glyph, _sub) in _GROUP_PANEL.items() if key in titles}
    group_icons.update({TECHNICAL_GROUP: "bars", RAINBOW_GROUP: "gradient"})
    group_icons.update({layer_label(n): "wave" for n in names})
    traces = [(layer_label(n), tuple(f"{layer_label(n)} {part}" for part in TRACE_LAYERS)) for n in names]
    traces += [(titles.get("core", "Core"), ("Passage", "Reaction", "Swell")),
               (TECHNICAL_GROUP, ("Bass Share", "Mid Share", "Loudness"))]
    add_node = tuple((layer_label(n), (StudioAction(f"{ADD_NODE}{n}", "Add Node", "plus",
                                                    f"Add a node to the {layer_label(n)} contour in its widest gap "
                                                    f"(at most {node_limits()[1]})."),))
                     for n in names)
    return StudioSchema(MODE, "DevCurve Studio", tuple(workspaces), tuple(props), admit,
                        group_traces=tuple(traces), group_icons=tuple(group_icons.items()), object_noun="Layer",
                        follow=follow, group_actions=add_node)


# ------------------------------------------------------------------------------------ evaluator
class DevCurveStudioEvaluator(EngineAnswerEvaluator):
    """DevCurve's production tick (``consume_engine_bars``, ``dispatch_devcurve_field``, the capture) run in process
    from recorded engine answers (``engine_answers.EngineAnswerEvaluator``), with the reactivity traces."""

    def __init__(self, loader: Callable | None = None) -> None:
        super().__init__(DEVCURVE, loader)

    def _runtime(self):
        from widgets.spotify_visualizer.devcurve_frame_runtime import DevCurveFrameRuntime
        controller = self._controller
        runtime = controller.peek_logical_mode_state(MODE) if controller is not None else None
        return runtime if isinstance(runtime, DevCurveFrameRuntime) else None

    def measurements(self) -> dict[str, dict[str, float]]:
        """Read-only values of this evaluator's own DevCurve runtime at the current instant (trace channels): each
        layer's body over its body top, its accent over its reserved room and its swell, the passage drive, the
        visible reaction and the served band shares and loudness. Nothing here runs in the saver."""
        runtime = self._runtime()
        if runtime is None or self._last is None:
            return {"sources": {}, "targets": {}, "signals": {}}
        from widgets.spotify_visualizer import devcurve_runtime as solver
        state = runtime.solver_state
        latest = runtime.latest
        drives = dict(dict(latest.diagnostics).get("drives", {}) or {})
        signals: dict[str, float] = {}
        swells, reactions = [], []
        for name in layers():
            label = layer_label(name)
            body = float(state.drive_body.get(name, 0.0)) / max(1e-9, solver.DEVCURVE_BODY_TOP[name])
            accent = float(state.drive_accent.get(name, 0.0)) / max(1e-9, solver.DEVCURVE_ACCENT_ROOM[name])
            swell = float(drives.get(f"swell_{name}", 0.0))
            signals[f"{label} Body"], signals[f"{label} Accent"], signals[f"{label} Swell"] = body, accent, swell
            swells.append(swell)
            reactions.append(float(drives.get(f"reaction_{name}", 0.0)))
        signals["Passage"] = float(state.passage_drive)
        signals["Reaction"] = sum(reactions) / len(reactions) if reactions else 0.0
        signals["Swell"] = max(swells, default=0.0)
        energy = latest.energy
        signals["Bass Share"] = float(energy.bass)
        signals["Mid Share"] = float(energy.mid)
        signals["Loudness"] = self._served_loudness() / 17.0       # the fixed real-music scale (3-17 in music)
        return {"sources": {}, "targets": {}, "signals": signals}

    def _served_loudness(self) -> float:
        tick = self._last_tick
        answer = None if tick is None else tick.answers.get("get_musical_level")
        if answer is None:
            return 0.0
        from ui.studio.replay_engine import decode_answer
        level = decode_answer(answer)
        return float(level[0]) if level else 0.0


# ------------------------------------------------------------------------------------- renderer
class DevCurveStudioRenderer(framed.ContractModeRenderer):
    """The production ``QuickDevCurveRenderer`` handed the production render-frame contract (the full logical
    frame), the live card's presentation and the item mapping."""

    def __init__(self) -> None:
        from rendering.quick.visualizer.implementations.devcurve import create_visualizer_renderer
        super().__init__(MODE, create_visualizer_renderer)


# -------------------------------------------------------------------------------------- adapter
class DevCurveStudioAdapter(StudioModeAdapter):
    mode_id = MODE
    title = "DevCurve Studio"

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

    def create_evaluator(self) -> DevCurveStudioEvaluator:
        return DevCurveStudioEvaluator()

    def create_renderer(self):
        return DevCurveStudioRenderer()

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
        return engine_answers.start_clip_load(DEVCURVE, clip, values, finished)


__all__ = [
    "ACTIVE_LAYER", "ADD_NODE", "DEVCURVE", "DevCurveStudioAdapter", "DevCurveStudioEvaluator",
    "DevCurveStudioRenderer", "REMOVE_NODE", "added_node", "admit_nodes", "build_schema", "engine_key",
    "engine_values", "follow", "layer_key", "layer_label", "layers", "node_limits", "normalized_orders",
    "owned_keys", "structure_edit",
]
