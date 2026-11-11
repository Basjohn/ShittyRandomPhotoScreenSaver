"""Neon Lake's Studio adapter (mode id ``shockwave_grid``): schema, evaluator, fixtures, camera and renderer.

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
* **Terrain.** The authored heightfield is painted on the preview with the Studio's shared brush instrument
  (``ui.studio.brush``: Raise, Lower, Flatten, Water; radius, strength, falloff, flatten height), its strokes painted
  by the one brush owner (``rendering.gl_programs.heightfield_brush``). A pointer lands on the drawn ground through
  the frame's production framed camera (``basin_view``: the ray from the eye through the point, met with the scene's
  land, ``rendering.gl_programs.neon_terrain_surface``). The session carries the record (Undo, saving, Save To
  <Preset>) and the whole-record edits (Reset Terrain, Extend Toward Horizon) are structural actions.
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
from ui.studio.registry import studio_title
from ui.studio.adapter import StudioCapabilities, StudioFixture, StudioModeAdapter, control_condition
from ui.studio.engine_answers import EngineAnswerEvaluator
from ui.studio.shockwave_grid_recorded_inputs import NEON_LAKE
from ui.studio.schema import (
    CHOICE, COLOUR, SCALAR, SHAPE_BANDS, SWITCH, ShapeLayout, ShapeSpec, StudioAction, StudioProperty,
    StudioSchema, Workspace, WorkspaceColumn,
)
from ui.studio.schema import SHAPE as SHAPE_INSTRUMENT       # ``SHAPE`` here names the Frequency Response keys
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
# The terrain shaper's structural edits (the shared shape instrument's rules along the land's height).
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
@cache
def _shaper_default() -> dict:
    """The canonical shaper record (read only: a drag admits and previews against it every frame)."""
    return canonical(SHAPER)


def admit_shaper(candidate: Any, previous: Any) -> dict:
    """Settings' shaper rules (``normalize_terrain_shaper``) with the shape editor's moves: a moved node or boundary
    stops at its neighbours, the lanes and their set never change, two to five nodes."""
    from rendering.gl_programs.neon_terrain_reaction import normalize_terrain_shaper
    default = _shaper_default()
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


def shaper_profile(values: Mapping[str, Any]) -> dict:
    """What the shaper does along the land's height, for the instrument's preview: per elevation sample of the
    baked tables the height shader reads (``bake_terrain_shaper``), the curve and the curve at its lane's strength;
    and each lane's strength over the span it owns (from its boundary up to the next one, as the bake assigns it)."""
    from rendering.gl_programs.neon_terrain_reaction import bake_terrain_shaper
    shaper = admit_shaper(values.get(SHAPER), values.get(SHAPER))
    baked = bake_terrain_shaper(shaper)
    notches, lanes = shaper["notches"], []
    for index, (position, label) in enumerate(notches):
        top = notches[index + 1][0] if index + 1 < len(notches) else 1.0
        lanes += [[position, shaper["lanes"][label]], [top, shaper["lanes"][label]]]
    return {"bars": [[bias, weight] for bias, weight in zip(baked["bias"], baked["weight"])], "lanes": lanes}


def _shaper_properties(add: Callable[..., None], workspace: str, group: str) -> ShapeSpec:
    """The shaper as ONE shape instrument (its nodes, the lane boundaries and the five lane strengths, all in the
    one stored record), shown with React to Music (Settings showed the shaper only then)."""
    add(SHAPER, (SHAPER, "nodes"), "Reaction Shaper", workspace, group, SHAPE_INSTRUMENT, priority=200,
        when=REACTION_ON,
        tooltip=f"How strongly each height of the land deforms, shoreline to summit ({SHAPER_NODES[0]} to "
                f"{SHAPER_NODES[1]} nodes), and which part of the spectrum moves it.")
    # The first boundary is pinned at the shoreline by the canonical shaper rule; the others move.
    layout = ShapeLayout((SHAPER, "notches"), (SHAPER, "lanes"), low="Shoreline", high="Summit",
                         previous=SHAPER_PREVIOUS, next=SHAPER_NEXT)
    return ShapeSpec(SHAPER, (layout,), node_limits=SHAPER_NODES, lane_mode=SHAPE_BANDS, pinned_lanes=1,
                     value_label="Amount", node_noun="Reaction Node", lane_noun="Reaction Lane", add=SHAPER_ADD,
                     remove=SHAPER_REMOVE, profile=shaper_profile)


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

    for control in spec.body_controls:
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

    # Terrain (Custom: painted with the viewport's brush instrument, ``brush_target``). The record is carried by the
    # session (undo, save, Save To <Preset>) through this schema-only marker; its whole-record edits are the group's
    # actions.
    terrain_group = titles[customs["terrain"].bucket]
    add(f"{TERRAIN}.size", (TERRAIN, "size"), "Terrain Grid", _BUCKET_WORKSPACE[customs["terrain"].bucket],
        terrain_group, SCALAR, minimum=2.0, maximum=float(_max_grid()), decimals=0, integer=True,
        instrument_only=True, tooltip="The authored heightfield (painted with the viewport's terrain brush).")

    # Terrain Reaction's shaper (Custom).
    reaction = titles[customs["terrain_shaper"].bucket]
    shaper_spec = _shaper_properties(add, _BUCKET_WORKSPACE[customs["terrain_shaper"].bucket], reaction)

    # Frequency Response (Custom): the smoothing rows and the Spectrum family's shape instrument.
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
    response_spec = spectrum_shape.shape_properties(SHAPE, add, response_workspace, response,
                                                    label="Response Shape")

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
    return StudioSchema(MODE, studio_title(MODE), tuple(workspaces), tuple(props), admit,
                        group_traces=((titles["waves"], ("Waves",)), (reaction, ("Land", "Level")),
                                      (response, ("Level", "Peak"))),
                        group_icons=tuple(group_icons.items()), object_noun="Layer",
                        group_actions=((terrain_group, terrain_actions),),
                        shapes=(shaper_spec, response_spec))


# ------------------------------------------------------------------------------- terrain brush
_PICK_SAMPLES = 512          # samples along a pick ray, spaced geometrically from the eye to the far plane
_PICK_REFINE = 24            # bisection steps on the first crossing
_RING_POINTS = 72


def terrain_view(frame, geometry):
    """The frame's production framed camera at the presented frame (``QuickShockwaveGridRenderer._view``: the card's
    content field and its aperture), for the brush's picks and footprint."""
    from rendering.gl_programs.neon_lake_basin_program import basin_view
    from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale
    size, extent, style = geometry
    resolved = framed.presentation(MODE, (float(size[0]), float(size[1])), extent, style)
    outer_x, outer_y, _w, _h = resolved.outer_rect
    x, y, width, height = resolved.content_rect
    return basin_view(frame.mode_state.parameters, (x - outer_x, y - outer_y, width, height),
                      aperture_scale=framed_aperture_scale(resolved, content=True))


def _terrain_surface(values: Mapping[str, Any]):
    """(size, heights grid, basin, Terrain Height) of the values' authored terrain."""
    import numpy as np
    from rendering.gl_programs.heightfield import heightfield_basin
    record = admit_terrain(values[TERRAIN], values[TERRAIN])
    size = int(record["size"])
    grid = np.asarray(record["heights"], dtype=np.float64).reshape(size, size)
    return size, grid, heightfield_basin(record), float(values[PREFIX + "terrain_height"])


def _ground(grid, basin, terrain_height: float, gu, gv):
    """The drawn ground's world height at grid uv (land scaled by Terrain Height, water at the scene's level)."""
    import numpy as np
    from rendering.gl_programs.neon_terrain_surface import scene_surface
    land, water = scene_surface(grid, basin, gu, gv)
    return np.where(water, land, land * terrain_height)


def _grid_uv(size: int, basin, x, z):
    """World x / z -> grid uv (the inverse of ``neon_terrain_surface.world_points``)."""
    from core.constants.neon_lake_world import DEPTH, NOMINAL_HALF_WIDTH
    x0, y0, cells = basin
    n1 = size - 1
    return (((x / (2.0 * NOMINAL_HALF_WIDTH) + 0.5) * cells + x0) / n1, ((-z / DEPTH) * cells + y0) / n1)


def pick_terrain(frame, values: Mapping[str, Any], point, geometry):
    """The authored grid's uv under ``point`` (presented-frame pixels): the first place the camera's ray through it
    meets the drawn ground; None on the sky, past the grid or outside the card's field."""
    import numpy as np
    from core.constants.neon_lake_world import FAR_PLANE
    if frame is None or getattr(frame, "mode_state", None) is None:
        return None
    view = terrain_view(frame, geometry)
    fx, fy, fw, fh = view.field
    u, v = (float(point[0]) - fx) / fw, (float(point[1]) - fy) / fh
    if not (0.0 <= u <= 1.0 and 0.0 <= v <= 1.0):
        return None
    size, grid, basin, height = _terrain_surface(values)
    eye, direction = np.asarray(view.eye, dtype=np.float64), np.asarray(view.ray(u, v), dtype=np.float64)

    def above(t):
        p = eye + np.multiply.outer(t, direction)
        gu, gv = _grid_uv(size, basin, p[..., 0], p[..., 2])
        return p[..., 1] - _ground(grid, basin, height, gu, gv)

    t = np.geomspace(0.01, FAR_PLANE, _PICK_SAMPLES)
    crossing = np.flatnonzero(above(t) <= 0.0)
    if crossing.size == 0:
        return None
    index = int(crossing[0])
    near, far = (0.0, float(t[0])) if index == 0 else (float(t[index - 1]), float(t[index]))
    for _ in range(_PICK_REFINE):
        middle = 0.5 * (near + far)
        if float(above(np.array([middle]))[0]) > 0.0:
            near = middle
        else:
            far = middle
    hit = eye + far * direction
    gu, gv = _grid_uv(size, basin, float(hit[0]), float(hit[2]))
    if not (0.0 <= gu <= 1.0 and 0.0 <= gv <= 1.0):
        return None
    return float(gu), float(gv)


def terrain_footprint(frame, values: Mapping[str, Any], uv, rings, geometry) -> list:
    """Each ring (a radius in grid uv round ``uv``, clipped to the grid) on the drawn ground, in presented-frame
    pixels; parts behind the eye are left out."""
    import numpy as np
    from rendering.gl_programs.neon_terrain_surface import world_points
    if frame is None or getattr(frame, "mode_state", None) is None:
        return []
    view = terrain_view(frame, geometry)
    size, grid, basin, height = _terrain_surface(values)
    angle = np.linspace(0.0, 2.0 * math.pi, _RING_POINTS + 1)
    out = []
    for radius in rings:
        gu = np.clip(uv[0] + radius * np.cos(angle), 0.0, 1.0)
        gv = np.clip(uv[1] + radius * np.sin(angle), 0.0, 1.0)
        world = world_points(size, basin, gu, gv, _ground(grid, basin, height, gu, gv))
        line = []
        for point in world:
            if view.depth(tuple(point)) > 1e-3:
                x, y = view.item_point(tuple(point))
                line.append([round(float(x), 1), round(float(y), 1)])
        if len(line) > 1:
            out.append(line)
    return out


def brush_target():
    """The terrain brush's target: the authored heightfield, picked and drawn on the preview's ground."""
    from ui.studio.brush import BrushTarget
    return BrushTarget(TERRAIN, "Terrain", pick_terrain, terrain_footprint)


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
    title = studio_title(MODE)

    def __init__(self) -> None:
        self._schema: StudioSchema | None = None

    def capabilities(self) -> StudioCapabilities:
        return StudioCapabilities(viewport=True, camera=True, handles=False, objects=False, brush=True)

    def brush_target(self):
        """The terrain brush: paints the authored heightfield on the preview's drawn ground."""
        return brush_target()

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
    "admit_terrain", "brush_target", "build_schema", "camera_position_bounds", "pick_terrain", "terrain_footprint",
    "terrain_view", "engine_key", "engine_values", "owned_keys",
    "shaper_profile", "structure_edit",
]
