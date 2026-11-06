"""Neon Lake Basin's Studio adapter (mode id ``shockwave_grid``): schema, evaluator, fixtures, camera and renderer.

Truthfulness: the Studio changes no Neon Lake simulation, timing, engine or render code and re-implements none of it.

* **Spectrum's step under the Neon Lake identity.** Neon Lake's capture (``logical_frame_capture._capture_shockwave_grid``)
  is Spectrum's (``_capture_spectrum_family``) plus the transient bus's onsets (admitted and aged into waves by the
  mode's frame runtime), the musical level and intensity, and the pre-AGC analysis spectrum Terrain Reaction reads:
  all the beat engine's processing on the process clock. It therefore uses the Spectrum family's recorded engine
  answers (``ui.studio.engine_answers``): the worker ``ui.studio.shockwave_grid_recorded_inputs`` replays the source
  through the production offline replay out of process and records every answer the engine gave the step; the
  Studio runs the production step in process from those answers. Engine-owned values (the Frequency Response shape,
  Reactivity / Response Floor / Falloff and the audio analysis: what the production source projection hands the
  engine) re-run the worker; everything else (terrain, water, Terrain Reaction, surface, sky, Sun & Moon, glow,
  camera, smoothing) is the mode's own and replays exactly at once.
* **Camera.** Neon Lake uses the shared framed physical camera (``core.settings.framed_camera``, spec
  ``core.settings.neon_lake_camera``; Extruded Bubble's camera is the standard): navigation is
  ``framed.camera_navigation`` (orbit = turn / tilt, wheel = lens, Shift+wheel = dolly, pan). The orbit is saved only
  under the store's camera policy; the lens on Keep View; dolly and pan stay preview views.
* **Environment.** Neon Lake draws its own scene (sky, Sun / Moon, terrain, lake) and its descriptor declares no
  backdrop setting: the renderer reads no wallpaper, so the Studio hands it none (``set_environment`` is inert).
* **Terrain.** The authored heightfield is painted with Settings' terrain brush; the Studio carries the record (Undo,
  saving, Save To <Preset>) and offers the terrain editor's whole-record edits (Reset Terrain, Extend Toward Horizon)
  as structural actions. There is no brush instrument in the shared shell.
* The production ``QuickShockwaveGridRenderer`` draws the resulting ``VisualizerLogicalFrame`` at the live card's
  presentation (Fill by default).
"""
from __future__ import annotations

import math
from functools import cache
from typing import Any, Callable, Mapping

from core.settings.visualizer_mode_settings import (
    Choice, Colour, Custom, SceneCameraPosition, Slider, Toggle, require_mode_settings,
)
from ui.studio import engine_answers, framed, spectrum_shape
from ui.studio.adapter import StudioCapabilities, StudioFixture, StudioModeAdapter, control_condition
from ui.studio.engine_answers import EngineAnswerEvaluator
from ui.studio.shockwave_grid_recorded_inputs import NEON_LAKE
from ui.studio.schema import (
    CHOICE, COLOUR, SCALAR, SWITCH, StudioAction, StudioProperty, StudioSchema, Workspace, WorkspaceColumn,
)
from ui.studio.spectrum_shape import ShapeKeys
from ui.studio.technical import TECHNICAL_GROUP, admit_technical, technical_properties

MODE = "shockwave_grid"
PREFIX = "shockwave_grid_"
SHAPE = ShapeKeys(PREFIX)                       # the Frequency Response shape (Spectrum's keys under this prefix)
TERRAIN = PREFIX + "terrain"
SHAPER = PREFIX + "terrain_shaper"
REACTION_ON = ((PREFIX + "terrain_reaction_enabled", (True,)),)
VIEW_GROUP = "View"
_AXES = ("X", "Y", "Z")

# Workspace of each canonical bucket (group titles are the registry's bucket titles).
_BUCKET_WORKSPACE = {"terrain": "land", "render": "land", "waves": "water", "glow": "water", "sky": "sky",
                     "celestial": "sky", "reaction": "music", "response": "music", "camera": "camera"}
_WORKSPACES = (
    ("land", "Land", "height", "The authored terrain's height, detail and fill, and how its surface is drawn: "
                               "vertices or glass, density, depth and the horizon line."),
    ("water", "Water & Glow", "drop", "The lake's colours, waves, flow and reflection, and the glow on the "
                                      "surface, ridges, water lines and shore."),
    ("sky", "Sky & Light", "sun", "The sky, clouds, nebula and beat stars, and the Sun or Moon with its halo and "
                                  "light rays."),
    ("music", "Reaction", "bolt", "How the music reshapes the land (Terrain Reaction and its shaper), and the "
                                  "frequency response and audio analysis feeding the waves."),
    ("camera", "Camera", "camera", "The framed camera's lens, auto rotate and position, and the preview view."),
)
_BUCKET_PANEL = {
    "terrain": ("height", "Height, detail and fill"), "render": ("material", "Vertices, glass and lines"),
    "waves": ("drop", "Colour, waves and reflection"), "glow": ("sparkle", "Surface, ridge and shore glow"),
    "sky": ("cloud", "Sky, clouds, nebula and stars"), "celestial": ("sun", "Sun or Moon, halo and rays"),
    "reaction": ("height", "Pulses, peaks and swell"), "response": ("bars", "Shape, reactivity and smoothing"),
    "camera": ("camera", "Lens, auto rotate, position"),
}
_PRIORITY = {PREFIX + key: rank for rank, key in enumerate((
    "terrain_height", "terrain_detail", "terrain_fill_color", "wire_display", "water_color", "line_color",
    "crest_color", "wave_height", "wave_speed", "terrain_reaction_enabled", "terrain_reaction_strength",
    "sky_enabled", "sky_color", "sun_enabled", "sun_mode", "glow", "wave_amplitude", "camera_fov"))}
_ROW_ICONS = {"terrain_height": "height", "terrain_fill_color": "colour", "water_color": "drop",
              "wave_height": "wave", "scroll": "flow", "water_reflection": "floor", "wire_display": "material",
              "terrain_reaction_enabled": "bolt", "sky_enabled": "cloud", "volumetric_clouds": "cloud",
              "starscape_beat": "sparkle", "sun_enabled": "sun", "sun_rays_enabled": "sparkle", "glow": "sparkle",
              "camera_fov": "lens", "auto_rotate": "roll", "wave_amplitude": "bolt"}
_SMOOTHING = (
    ("visual_smoothing_enabled", "Smooth Sudden Bar Changes", SWITCH,
     "Interpolate the analysed levels on the existing visualizer tick. Audio analysis remains unchanged."),
    ("visual_smoothing", "Smoothing Strength", SCALAR,
     "Higher values soften one-tick spikes and drops more strongly."),
    ("solid_bar_hysteresis_enabled", "Stabilize Levels", SWITCH,
     "Use the shared bar evaluator's hysteresis to suppress tiny level fluctuations."),
)
# The terrain shaper's structural edits (the shared shape editor's rules along the land's height).
SHAPER_ADD = "terrain_shaper.add_node"
SHAPER_REMOVE = "terrain_shaper.remove_node."           # + node index
SHAPER_PREVIOUS = "terrain_shaper.lane_previous."       # + boundary index
SHAPER_NEXT = "terrain_shaper.lane_next."
SHAPER_NODES = (2, 5)                                  # ``normalize_terrain_shaper``'s node count
TERRAIN_RESET = "terrain.reset"
TERRAIN_EXTEND = "terrain.extend"


def _label(text: str) -> str:
    return str(text).rstrip(":").strip()


def canonical(key: str):
    from core.settings.default_contract import require_canonical_default
    return require_canonical_default("widgets.spotify_visualizer")[key]


@cache
def owned_keys() -> frozenset[str]:
    """Settings Neon Lake's own step, capture or renderer reads (``EngineAnswerMode.owned_keys``)."""
    return NEON_LAKE.owned_keys()


def engine_values(values: Mapping[str, Any]) -> dict:
    """The engine-owned subset of ``values`` (``tests/test_neon_lake_studio.py`` proves both directions)."""
    return NEON_LAKE.engine_values(values)


def engine_key(values: Mapping[str, Any]) -> str:
    return NEON_LAKE.engine_key(values)


# ------------------------------------------------------------------------------- terrain shaper
def admit_shaper(candidate: Any, previous: Any) -> dict:
    """Settings' shaper rules (``normalize_terrain_shaper``) with the shape editor's moves: a moved node or boundary
    stops at its neighbours, the lanes and their set never change, two to five nodes."""
    from rendering.gl_programs.neon_terrain_reaction import normalize_terrain_shaper
    default = canonical(SHAPER)
    old = normalize_terrain_shaper(previous, default)
    if not isinstance(candidate, Mapping):
        return old
    nodes = old["nodes"]
    try:
        wanted = [[float(x), float(y)] for x, y in candidate.get("nodes", nodes)]
    except (TypeError, ValueError):
        wanted = nodes
    if SHAPER_NODES[0] <= len(wanted) <= SHAPER_NODES[1]:
        nodes = spectrum_shape.admit_nodes(wanted, old["nodes"])
    notches = spectrum_shape.admit_notches(candidate.get("notches", old["notches"]), old["notches"])
    lanes = spectrum_shape.admit_lanes(candidate.get("lanes", old["lanes"]), old["lanes"])
    return normalize_terrain_shaper({"nodes": nodes, "notches": notches, "lanes": lanes}, default)


def _shaper_edit(action_id: str, shaper: Mapping) -> tuple[str, dict] | None:
    record = {"nodes": [list(n) for n in shaper["nodes"]], "notches": [list(n) for n in shaper["notches"]],
              "lanes": dict(shaper["lanes"])}
    nodes = record["nodes"]
    if action_id == SHAPER_ADD:
        if len(nodes) >= SHAPER_NODES[1]:
            return None
        record["nodes"] = spectrum_shape.added_node(nodes)
        return "Add Reaction Node", record
    if action_id.startswith(SHAPER_REMOVE):
        index = int(action_id[len(SHAPER_REMOVE):])
        if len(nodes) <= SHAPER_NODES[0] or not 0 <= index < len(nodes):
            return None
        record["nodes"] = nodes[:index] + nodes[index + 1:]
        return f"Remove Reaction Node {index + 1}", record
    for prefix, step in ((SHAPER_PREVIOUS, -1), (SHAPER_NEXT, 1)):
        if action_id.startswith(prefix):
            index = int(action_id[len(prefix):])
            notches, other = record["notches"], index + step
            if not (0 <= index < len(notches) and 0 <= other < len(notches)):
                return None
            notches[index][1], notches[other][1] = notches[other][1], notches[index][1]
            return f"Swap {notches[other][1]} And {notches[index][1]} Reaction Lanes", record
    return None


def _shaper_properties(add: Callable[..., None], workspace: str, group: str) -> None:
    """The shaper's rows: every node slot (both axes), the movable lane boundaries and the five lane strengths, shown
    with React to Music (Settings shows the shaper only then)."""
    from rendering.gl_programs.neon_terrain_reaction import REACTION_LANES
    for index in range(SHAPER_NODES[1]):
        for axis, word in ((0, "Height"), (1, "Amount")):
            remove = (StudioAction(f"{SHAPER_REMOVE}{index}", f"Remove Node {index + 1}", "minus",
                                   "Remove this node (the shaper keeps at least two)."),) if axis == 0 else ()
            add(f"{SHAPER}.nodes.{index}.{axis}", (SHAPER, "nodes", index, axis),
                f"Shaper Node {index + 1} {word}", workspace, group, SCALAR, minimum=0.0, maximum=1.0, decimals=3,
                priority=200 + 2 * index + axis, actions=remove, when=REACTION_ON,
                tooltip="A node of the reaction curve along the land's height (shoreline 0 to summit 1), then how "
                        "strongly that elevation deforms. A node stops at its neighbours.")
    # The first boundary is pinned at the shoreline by the canonical shaper rule; the others move.
    for index in range(1, len(REACTION_LANES)):
        swaps = (StudioAction(f"{SHAPER_PREVIOUS}{index}", "Swap With Previous Lane", "chevron-left",
                              "Exchange this lane with the one below it (the boundaries stay)."),
                 StudioAction(f"{SHAPER_NEXT}{index}", "Swap With Next Lane", "chevron-right",
                              "Exchange this lane with the one above it (the boundaries stay)."))
        add(f"{SHAPER}.notches.{index}", (SHAPER, "notches", index, 0), f"Reaction Boundary {index + 1}", workspace,
            group, SCALAR, minimum=0.0, maximum=1.0, decimals=3, priority=300 + index, actions=swaps,
            when=REACTION_ON, tooltip="The height where this frequency lane takes over. A boundary stops at its "
                                      "neighbours.")
    for index, lane in enumerate(REACTION_LANES):
        add(f"{SHAPER}.lanes.{lane}", (SHAPER, "lanes", lane), f"{lane} Lane Strength", workspace, group, SCALAR,
            minimum=0.0, maximum=1.0, decimals=2, priority=320 + index, when=REACTION_ON,
            tooltip="How strongly this part of the spectrum moves the heights it owns.")


# ------------------------------------------------------------------------------------ terrain
def admit_terrain(candidate: Any, previous: Any) -> dict:
    """The canonical heightfield admission (``normalize_heightfield``); a malformed record keeps the previous."""
    from rendering.gl_programs.heightfield import normalize_heightfield
    try:
        return normalize_heightfield(candidate)
    except ValueError:
        return normalize_heightfield(previous)


def _terrain_edit(action_id: str, terrain: Mapping) -> tuple[str, dict] | None:
    """The terrain editor's whole-record edits: Reset (the canonical basin) and Extend Toward Horizon."""
    from rendering.gl_programs.heightfield import normalize_heightfield
    from rendering.gl_programs.neon_terrain_extent import extend_heightfield, horizon_extension_cells
    if action_id == TERRAIN_RESET:
        default = normalize_heightfield(canonical(TERRAIN))
        return None if normalize_heightfield(terrain) == default else ("Reset Terrain", default)
    if action_id == TERRAIN_EXTEND:
        cells = horizon_extension_cells(terrain)
        return None if cells is None else ("Extend Toward Horizon", extend_heightfield(terrain, *cells))
    return None


def structure_edit(action_id: str, values: Mapping[str, Any]):
    """(undo label, {path: value}) for a structural edit, or None while it is not admissible."""
    if action_id.startswith("terrain_shaper."):
        if not values.get(REACTION_ON[0][0]):
            return None                    # Settings shows the shaper only with React to Music
        edit = _shaper_edit(action_id, admit_shaper(values.get(SHAPER), values.get(SHAPER)))
        return None if edit is None else (edit[0], {(SHAPER,): edit[1]})
    if action_id.startswith("terrain."):
        edit = _terrain_edit(action_id, values[TERRAIN])
        return None if edit is None else (edit[0], {(TERRAIN,): edit[1]})
    return spectrum_shape.structure_edit(SHAPE, action_id, values)


def row_label(prop: StudioProperty, values: Mapping[str, Any]) -> str:
    """Boundary rows are titled by the lane they currently bound (lanes can be swapped)."""
    if prop.path[0] == SHAPER and prop.path[1] == "notches":
        return f"{values[SHAPER]['notches'][prop.path[2]][1]} Boundary"
    return spectrum_shape.row_label(SHAPE, prop, values)


def camera_position_bounds() -> tuple[tuple[float, float], ...]:
    """Camera Position's per-axis reach in its stored (normalized) units: the framed camera's eye box spanned in
    offset units (``offset_scale``); the eye itself is bounded by the box and the terrain floor."""
    from core.settings.framed_camera import spec_for_mode
    spec = spec_for_mode(MODE)
    return tuple((-2.0 * h / s, 2.0 * h / s) for h, s in zip(spec.eye_half, spec.offset_scale))


# ---------------------------------------------------------------------------------- schema
def build_schema() -> StudioSchema:
    spec = require_mode_settings(MODE)
    titles = {bucket.key: bucket.title for bucket in spec.buckets}
    customs = {entry.name: entry for entry in spec.entries if isinstance(entry, Custom) and entry.bucket}
    navigation = framed.camera_navigation(MODE, PREFIX)
    view_axes = (navigation.orbit_h, navigation.orbit_v, navigation.dolly, navigation.pan_x, navigation.pan_y)
    view_keys = {axis.key for axis in view_axes}
    props: list[StudioProperty] = []
    placed: dict[str, list[str]] = {w[0]: [] for w in _WORKSPACES}

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
        if control.key in view_keys:
            continue                                    # the live view below
        bucket = control.bucket
        if not bucket:
            raise KeyError(f"{control.key} has no Settings owner the Studio knows")
        workspace, group = _BUCKET_WORKSPACE.get(bucket, "land"), titles.get(bucket, bucket)
        text = getattr(control, "text", "") if isinstance(control, Toggle) else ""
        label = _label(control.label) or _label(text) or control.key[len(PREFIX):].replace("_", " ").title()
        common = dict(tooltip=getattr(control, "tooltip", "") or text, when=control_condition(control))
        if isinstance(control, SceneCameraPosition):
            for index, ((low, high), axis) in enumerate(zip(camera_position_bounds(), _AXES)):
                add(f"{control.key}.{index}", (control.key, index), f"Camera {axis}", workspace, group, SCALAR,
                    minimum=low, maximum=high, decimals=3, priority=_PRIORITY.get(control.key, 100) + index,
                    **{**common, "tooltip": common["tooltip"] or "Camera Position: the eye's offset from its orbit "
                                                                   "pose; the framed camera keeps it above the land."})
        elif isinstance(control, Slider):
            extra = max(0, int(round(math.log10(control.display_multiplier)))) if control.display_multiplier > 1 else 0
            decimals = 0 if control.integer else max(control.decimals + extra, 2)
            add(control.key, (control.key,), label, workspace, group, SCALAR, minimum=control.low,
                maximum=control.high, decimals=decimals, units="" if control.percent else control.suffix,
                integer=control.integer, **common)
        elif isinstance(control, Toggle):
            add(control.key, (control.key,), label, workspace, group, SWITCH, **common)
        elif isinstance(control, Choice):
            stored = tuple(control.choices)
            add(control.key, (control.key,), label, workspace, group, CHOICE,
                choices=tuple(control.labels) if control.labels else tuple(str(c) for c in stored),
                choice_values=stored, **common)
        elif isinstance(control, Colour):
            add(control.key, (control.key,), label, workspace, group, COLOUR, **common)
            if control.alpha:
                add(f"{control.key}.3", (control.key, 3), f"{label} Opacity", workspace, group, SCALAR,
                    minimum=0.0, maximum=255.0, decimals=0, integer=True, icon="",
                    priority=_PRIORITY.get(control.key, 100) + 1, **common)
        # Any other control type is deliberately not guessed at: the full-coverage test names it.

    # The live view (the framed camera's orbit, dolly and pan): a preview pose, saved only by the camera policy.
    for axis, label in zip(view_axes, ("Orbit Turn", "Orbit Tilt", "Zoom", "Pan X", "Pan Y")):
        add(axis.key, (axis.key,), label, "camera", VIEW_GROUP, SCALAR, minimum=axis.bounds[0],
            maximum=axis.bounds[1], decimals=3, view_pose=True,
            tooltip="Preview view. Drag the viewport to orbit. The view is saved only when the preset's camera "
                    "choice includes it.")

    # Terrain (Custom: the bespoke brush editor). The record is carried by the session (undo, save, Save To
    # <Preset>) through this schema-only marker; its whole-record edits are the group's actions.
    terrain_group = titles[customs["terrain"].bucket]
    add(f"{TERRAIN}.size", (TERRAIN, "size"), "Terrain Grid", _BUCKET_WORKSPACE[customs["terrain"].bucket],
        terrain_group, SCALAR, minimum=2.0, maximum=float(_max_grid()), decimals=0, integer=True,
        instrument_only=True, tooltip="The authored heightfield (painted in Settings' terrain editor).")

    # Terrain Reaction's shaper (Custom).
    reaction = titles[customs["terrain_shaper"].bucket]
    _shaper_properties(add, _BUCKET_WORKSPACE[customs["terrain_shaper"].bucket], reaction)

    # Frequency Response (Custom): the smoothing rows and Spectrum's shape editor.
    response = titles[customs["shape"].bucket]
    response_workspace = _BUCKET_WORKSPACE[customs["shape"].bucket]
    smoothing = customs["smoothing"]
    for suffix, label, instrument, tooltip in _SMOOTHING:
        key = PREFIX + suffix
        if key not in smoothing.keys:
            raise KeyError(f"{key} is no longer a smoothing row key")
        extra = (dict(minimum=0.0, maximum=1.0, decimals=2, when=((PREFIX + "visual_smoothing_enabled", (True,)),))
                 if instrument == SCALAR else {})
        add(key, (key,), label, response_workspace, response, instrument, tooltip=tooltip, **extra)
    spectrum_shape.shape_properties(SHAPE, add, response_workspace, response)

    technical = technical_properties(MODE, workspace=response_workspace)
    props.extend(prop for prop, _defn in technical.values())
    placed[response_workspace].append(TECHNICAL_GROUP)

    bucket_of = {title: key for key, title in titles.items()}
    order = {key: rank for rank, key in enumerate(bucket.key for bucket in spec.buckets)}   # Settings' order
    workspaces = []
    for workspace_id, title, icon, help_text in _WORKSPACES:
        groups = placed[workspace_id]
        if not groups:
            continue
        groups = sorted(groups, key=lambda g: (g == VIEW_GROUP, g == TECHNICAL_GROUP,
                                               order.get(bucket_of.get(g, ""), len(order))))
        columns = []
        for group in groups:
            if group == VIEW_GROUP:
                glyph, subtitle = "view", "The preview orbit, zoom and pan"
            else:
                glyph, subtitle = _BUCKET_PANEL.get(bucket_of.get(group, ""), ("bars", "Live analysis feeding the "
                                                                                       "waves"))
            columns.append(WorkspaceColumn(group, (group,), glyph, subtitle))
        workspaces.append(Workspace(workspace_id, title, tuple(groups), open_groups=tuple(groups), icon=icon,
                                    help=help_text, columns=tuple(columns)))

    controls = {control.key: control for control in spec.controls}
    switches = {PREFIX + suffix for suffix, _l, instrument, _t in _SMOOTHING if instrument == SWITCH}

    def admit(key: str, candidate: Any, previous: Any) -> Any:
        if key in technical:
            return admit_technical(technical[key], candidate, previous)
        if key in controls:
            return controls[key].admit(candidate, previous)
        if key == TERRAIN:
            return admit_terrain(candidate, previous)
        if key == SHAPER:
            return admit_shaper(candidate, previous)
        shaped = spectrum_shape.admit_shape(SHAPE, key, candidate, previous)
        if shaped is not NotImplemented:
            return shaped
        if key == PREFIX + "visual_smoothing":
            return spectrum_shape.percent(candidate, previous)
        if key in switches:
            return bool(candidate)
        raise KeyError(f"{key} is not a Neon Lake Studio value")

    group_icons = {titles[key]: glyph for key, (glyph, _sub) in _BUCKET_PANEL.items() if key in titles}
    group_icons.update({TECHNICAL_GROUP: "bars", VIEW_GROUP: "view"})
    terrain_actions = (StudioAction(TERRAIN_EXTEND, "Extend Toward Horizon", "expand",
                                    "Grow the authored grid back and to the sides by whole cells; the basin's cells "
                                    "are kept exactly and the new ones follow the land's continuation."),
                       StudioAction(TERRAIN_RESET, "Reset Terrain", "reset",
                                    "Replace the painted terrain with the canonical basin (one undoable edit)."))
    return StudioSchema(MODE, "Neon Lake Studio", tuple(workspaces), tuple(props), admit,
                        group_traces=((titles["waves"], ("Waves",)), (reaction, ("Land", "Level")),
                                      (response, ("Level", "Peak"))),
                        group_icons=tuple(group_icons.items()), object_noun="Layer",
                        group_actions=((terrain_group, terrain_actions),
                                       (reaction, (StudioAction(SHAPER_ADD, "Add Node", "plus",
                                                                "Add a reaction node in the curve's widest gap "
                                                                f"(at most {SHAPER_NODES[1]})."),)),
                                       (response, (spectrum_shape.add_node_action(),))),
                        row_label=row_label)


def _max_grid() -> int:
    from rendering.gl_programs.heightfield import HEIGHTFIELD_MAX_SIZE
    return int(HEIGHTFIELD_MAX_SIZE)


# ------------------------------------------------------------------------------- evaluator
class NeonLakeStudioEvaluator(EngineAnswerEvaluator):
    """Neon Lake's production step and capture, run in process from recorded engine answers
    (``engine_answers.EngineAnswerEvaluator``)."""

    def __init__(self, loader: Callable | None = None) -> None:
        super().__init__(NEON_LAKE, loader)

    def measurements(self) -> dict[str, dict[str, float]]:
        """The shared Level / Peak, plus the waves (the newest wave's decaying strength, as the renderer's beat pulse
        reads the onset ring) and the land (the strongest Terrain Reaction lane drive) of the frame on screen."""
        out = super().measurements()
        frame = self._last
        if frame is not None:
            state = frame.mode_state
            out["signals"]["Waves"] = max((min(1.0, float(s)) * math.exp(-float(age) * 2.8)
                                           for age, _x, _z, s in state.events if age >= 0.0), default=0.0)
            out["signals"]["Land"] = max((float(v) for v in state.terrain_bands), default=0.0)
        return out


# --------------------------------------------------------------------------------- adapter
class NeonLakeStudioAdapter(StudioModeAdapter):
    mode_id = MODE
    title = "Neon Lake Studio"

    def __init__(self) -> None:
        self._schema: StudioSchema | None = None

    def capabilities(self) -> StudioCapabilities:
        return StudioCapabilities(viewport=True, camera=True, handles=False, objects=False)

    def schema(self) -> StudioSchema:
        if self._schema is None:
            self._schema = build_schema()
        return self._schema

    def scene_objects(self, values: Mapping[str, Any]):
        return ()

    def structure_edit(self, action_id: str, values: Mapping[str, Any]):
        return structure_edit(action_id, values)

    def create_evaluator(self) -> NeonLakeStudioEvaluator:
        return NeonLakeStudioEvaluator()

    def create_renderer(self):
        """The production ``QuickShockwaveGridRenderer`` handed the production render-frame contract (no backdrop:
        the mode draws its own sky)."""
        from rendering.quick.visualizer.implementations.shockwave_grid import create_visualizer_renderer
        return framed.ContractModeRenderer(MODE, create_visualizer_renderer)

    def navigation(self):
        return framed.camera_navigation(MODE, PREFIX)

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
        return engine_answers.start_clip_load(NEON_LAKE, clip, values, finished)


__all__ = [
    "NEON_LAKE", "NeonLakeStudioAdapter", "NeonLakeStudioEvaluator", "SHAPE", "SHAPER", "TERRAIN", "admit_shaper",
    "admit_terrain", "build_schema", "camera_position_bounds", "engine_key", "engine_values", "owned_keys",
    "row_label", "structure_edit",
]
