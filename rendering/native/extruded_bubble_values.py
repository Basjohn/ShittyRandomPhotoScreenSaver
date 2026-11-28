"""Extruded Bubble's native values (Current_Plan.md N5.6, "Native record and route"): every block member each of its
twelve programs draws with, as the Python renderer sets it (``QuickExtrudedBubbleRenderer.render``, its
``_capture_probe`` and ``_draw_shafts``), split by what decides it:

- ``state_values``: what follows the frame (the simulation's state: its populations, phases, followers, stream and
  drift), the worker's record (``extruded_bubble_native_schema``), each member named for its program
  (``extruded_bubble_shaders.member_name``);
- ``settings_values``: what the Settings and the card decide (the camera, the lens, the targets' sizes, the scene's
  knobs and every member the renderer never sets, at its block's initial value), the route's settings, a member one
  pass alone draws with scoped to it (``<member>@<pass>``: each cube face's view, each blur direction's step).

The Python renderer packs the last value each member was set to in its frame (``_Uniforms``), so each function here
follows the renderer's order of sets, restricted to its side's members (``STATE_MEMBERS``). The arithmetic is the
renderer's own (its module's helpers are called, never copied).
"""
from __future__ import annotations

import math
from typing import Any

from rendering.native.extruded_bubble_shaders import PROGRAMS, block_layout, member_name

#: The members a program's frame state decides (the record's), by program: every other member is a setting.
_COMMON_STATE = frozenset({"uTime", "uSurfaceTravel", "uRays", "uFanReach", "uStreak", "uDustAlong", "uDustAcross"})
_DRIFT = frozenset({"uChainDriftEnabled", "uSnowDriftOffset", "uSpeckDriftOffset"})
STATE_MEMBERS: dict[str, frozenset] = {
    "backdrop": _COMMON_STATE,
    "probe_backdrop": _COMMON_STATE,
    "shafts": _COMMON_STATE | {"uFlicker", "uShimmer", "uParticleAtten", "uBlock0", "uBlock1", "uBlock2", "uBlock3"},
    "blur": frozenset(),
    "shells": _COMMON_STATE,
    "clusters": _COMMON_STATE,
    "beads": _COMMON_STATE | _DRIFT | {
        "uStreamAcross", "uStreamDepth", "uStreamWorld", "uSceneFaces", "uBeadCount", "uBeadSize", "uChainFill",
        "uChainActivity", "uSnowFill", "uFizzFill", "uBeadTravel", "uSnowDrift", "uSnowCount", "uFizzPer",
        "uWakeCount", "uTrailTime"},
    "near": _COMMON_STATE,
    "near_clusters": _COMMON_STATE,
    "proxies": _COMMON_STATE,
    "specks": _COMMON_STATE | _DRIFT | {
        "uSpecks", "uSpeckBloom", "uParticleActivity", "uParticleRadiusShare", "uStreamWorld", "uStreamAcross",
        "uSpeckTravel", "uSceneFaces"},
    "trails": _COMMON_STATE | {"uTrailTime"},
}
#: The programs whose block takes a pass of its own per draw (the native passes' names).
FACE_PASSES = tuple(f"probe_backdrop_f{face}" for face in range(6))
PROXY_PASSES = tuple(f"proxies_f{face}" for face in range(6))
BLUR_PASSES = ("blur_x", "blur_y")
_GLASS = ("shells", "clusters", "near", "near_clusters", "beads")
#: The near layer's highlight (``DefocusLayer.composite``'s default, which the renderer keeps).
_HIGHLIGHT = 0.25
_NUMBERS = {"float": 1, "int": 1, "uint": 1, "bool": 1, "vec2": 2, "vec3": 3, "vec4": 4, "mat3": 9, "mat4": 16}
_INTEGER = ("int", "uint", "bool")


def block_members(program: str) -> dict[str, str]:
    """The program's block members (unprefixed) -> GLSL type, the core's own members left out."""
    from rendering.native.mode import MODE_CORE_MEMBERS

    return {name: kind for name, kind in block_layout(program).fields if name not in MODE_CORE_MEMBERS}


def state_fields() -> tuple[tuple[str, str, str], ...]:
    """(record field, program, member) of every state member a program's block declares, in program order."""
    out = []
    for program in PROGRAMS:
        members = block_members(program)
        out += [(member_name(program, m), program, m) for m in members if m in STATE_MEMBERS[program]]
    return tuple(out)


def _defaults(program: str) -> dict[str, Any]:
    """Each member's initial value (``block_defaults``: zeros, the fullscreen family's light shape)."""
    from rendering.gl_programs.extruded_bubble_program import FULLSCREEN_BLOCK, FULLSCREEN_DEFAULTS

    shaped = FULLSCREEN_DEFAULTS if block_layout(program) is FULLSCREEN_BLOCK else {}
    out: dict[str, Any] = {}
    for name, kind in block_members(program).items():
        count = _NUMBERS[kind]
        zero = 0 if kind in _INTEGER else 0.0
        out[name] = shaped.get(name, zero if count == 1 else (zero,) * count)
    return out


# ------------------------------------------------------------------------------------------------- the scene

_SCENE_CACHE: list = [None, None]


def _scene(parameters) -> dict:
    """The Settings-decided pieces both sides read (the renderer's ``scene_knobs`` and its stream path), once per
    Settings change."""
    if _SCENE_CACHE[0] is not None and _SCENE_CACHE[0] == parameters:
        return _SCENE_CACHE[1]
    from core.settings.visualizer_paths import admit_path, world_point
    from rendering.gl_programs.extruded_bubble_scene import scene_knobs
    from rendering.gl_programs.scene3d import scene3d_detail
    from rendering.quick.visualizer.implementation_values import parameter
    from rendering.quick.visualizer.implementations.extruded_bubble import _FIZZ_PER_BUBBLE, _floats

    knobs = scene_knobs(parameters)
    path = admit_path(parameter(parameters, "extruded_bubble_stream_direction"), [0., 0.], "stream")
    detail = scene3d_detail(parameter(parameters, "scene3d_detail"))
    trails = float(parameter(parameters, "extruded_bubble_wake_trails"))
    scene = {
        "knobs": knobs, "path": path, "source": _floats(world_point(path[:3])), "end": _floats(world_point(path[3:])),
        "detail": detail, "trails": trails, "trail_fizz": _FIZZ_PER_BUBBLE * detail.particles * trails,
        "scene_emission": 1 if parameter(parameters, "extruded_bubble_emission_geometry") == "SCENE" else 0,
    }
    _SCENE_CACHE[:] = [parameters, scene]
    return scene


def _deep(knobs: dict, eye) -> dict:
    """``render``'s deep light: the sun's direction toward the emitter from the eye."""
    if knobs["mode"] != "deep":
        return knobs
    to_emitter = tuple(float(p) - float(e) for p, e in zip(knobs["light_source"], eye))
    distance = math.sqrt(sum(v * v for v in to_emitter))
    return {**knobs, "sun_below": tuple(v / distance for v in to_emitter)} if distance > 1e-6 else knobs


# ------------------------------------------------------------------------------------------------- the record

def state_values(state: Any) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, bytes]]:
    """The frame's state members by program, its counts (the draws' instances, the near layer's gate, each drift
    family's capacity, output offset, carry and groups) and its instance streams' float32 rows (each truncated to its
    buffer's capacity, as ``_Instances.upload``)."""
    import numpy as np

    from rendering.gl_programs.extruded_bubble_scene import (
        SPECKS_FULL, bubble_instances, cluster_instances, glint_proxies, ray_motion, ray_strength, screen_streak,
        speck_amount, wake_instances)
    from rendering.quick.visualizer.implementation_values import parameter
    from rendering.quick.visualizer.implementations import extruded_bubble as eb
    from rendering.quick.visualizer.implementations.extruded_bubble_drift_solver import DriftSolver
    from widgets.spotify_visualizer.extruded_bubble_geometry import scene_source_face_weights, stream_basis
    from widgets.spotify_visualizer.extruded_bubble_material_paths import chain_draw_count

    parameters = state.parameters
    scene = _scene(parameters)
    knobs = scene["knobs"]
    floats = eb._floats
    shells = bubble_instances(state.bubbles)
    rows = {"shells": shells[:eb._SHELL_CAPACITY],
            "wakes": wake_instances(state.wakes)[:eb.MAX_BUBBLES * 2],
            "clusters": cluster_instances(state.bubbles, state.clusters)[:eb._CLUSTER_CAPACITY],
            "proxies": glint_proxies(shells, knobs["sun_below"], float(knobs["proxy_power"]),
                                     light_source=(knobs["light_source"] if knobs["mode"] == "deep" else None)
                                     )[:eb._SHELL_CAPACITY]}
    streams = {name: np.ascontiguousarray(r, dtype=np.float32).tobytes() for name, r in rows.items()}
    shell_count, cluster_count, wake_count = len(rows["shells"]), len(rows["clusters"]), len(rows["wakes"])

    # The drift layout the draws read (``DriftSolver.layout``: every live family, chain rows first).
    families = tuple(state.drift_families)
    layout = DriftSolver.layout(families)
    material = bool(families)
    drift = {"uChainDriftEnabled": int(material and "chains" in layout),
             "uSnowDriftOffset": layout["snow"] + 1 if material and "snow" in layout else 0,
             "uSpeckDriftOffset": layout["specks"] + 1 if material and "specks" in layout else 0}

    flicker, reach = ray_motion(parameters, state.rays, state.sustain)
    stream = floats(state.stream)
    dust_across, _depth = stream_basis(stream)
    common = {"uTime": float(state.motion_phase), "uSurfaceTravel": float(state.motion_phase),
              "uRays": float(ray_strength(parameters, state.rays)) * float(knobs["light_strength"]),
              "uFanReach": float(float(knobs.get("fan_reach", 0.6)) * reach), "uStreak": floats(screen_streak(state.stream)),
              "uDustAlong": stream, "uDustAcross": dust_across}
    leaders = sorted((tuple(float(v) for v in row[:4]) for row in shells if row[3] > 0.0), key=lambda b: -b[3])[:4]
    leaders += [(0.0, 0.0, 0.0, 0.0)] * (4 - len(leaders))
    shafts = {"uFlicker": flicker, "uShimmer": float(state.shimmer),
              "uParticleAtten": max(0.0, min(0.08, 0.08 * float(state.emission))),
              **{f"uBlock{i}": bubble for i, bubble in enumerate(leaders)}}

    chain_fill, snow_fill, fizz_fill = eb._procedural_fill(parameters, eb.chain_drive(state), state.emission)
    idle = eb._idle_activity(state.level)
    beads = chain_draw_count(chain_fill, parameter(parameters, "extruded_bubble_bead_chains")) * eb._BEADS_PER_CHAIN
    snow = math.ceil(snow_fill)
    fizz_per = math.ceil(max(fizz_fill, scene["trail_fizz"]))
    across, depth_axis = stream_basis(stream)
    faces = floats(scene_source_face_weights(scene["path"][:3], stream))
    bead_values = {
        **drift, "uStreamAcross": across, "uStreamDepth": depth_axis, "uStreamWorld": stream, "uSceneFaces": faces,
        "uBeadCount": beads,
        "uBeadSize": float(parameter(parameters, "extruded_bubble_bead_size"))
        * (0.9 + 0.2 * max(0.0, min(1.0, float(state.level)))),
        "uChainFill": chain_fill, "uChainActivity": float(state.chain_activity), "uSnowFill": snow_fill,
        "uFizzFill": fizz_fill, "uBeadTravel": eb._BEAD_CLIMB * float(state.travel),
        "uSnowDrift": eb._SNOW_CARRY * float(state.travel), "uSnowCount": snow, "uFizzPer": fizz_per,
        "uWakeCount": wake_count, "uTrailTime": float(state.motion_phase)}
    share, brightness = speck_amount(state.emission)
    glow_react = max(0.0, min(1.0, float(parameter(parameters, "extruded_bubble_particle_glow_reactivity"))))
    glow = 1.0 + glow_react * (0.50 * float(state.rays) + 0.20 * float(state.flash))
    specks = round(SPECKS_FULL * share * scene["detail"].particles)
    speck_values = {
        **drift, "uSpecks": brightness, "uSpeckBloom": float(knobs["speck_bloom"]) * glow,
        "uParticleActivity": idle, "uParticleRadiusShare": 0.25 + 0.75 * idle, "uStreamWorld": stream,
        "uStreamAcross": across, "uSpeckTravel": eb._SPECK_CARRY * float(state.travel), "uSceneFaces": faces}

    values: dict[str, dict[str, Any]] = {}
    for program in PROGRAMS:
        members = block_members(program)
        mine = {} if program == "blur" else dict(common)
        mine.update({"shafts": shafts, "beads": bead_values, "specks": speck_values,
                     "trails": {"uTrailTime": float(state.motion_phase)}}.get(program, {}))
        values[program] = {m: v for m, v in mine.items() if m in members and m in STATE_MEMBERS[program]}

    counts: dict[str, Any] = {
        "speck_count": int(specks), "bead_instances": int(beads + snow + wake_count * fizz_per),
        "trail_instances": int(wake_count) if scene["trails"] > 0.0 else 0,
        "near_layer": 1 if shell_count or cluster_count else 0}
    by_name = {family.family: family for family in families}
    from widgets.spotify_visualizer.extruded_bubble_drift_log import FAMILIES

    for family in FAMILIES:
        descriptor = by_name.get(family)
        capacity = int(descriptor.capacity) if descriptor is not None else 0
        counts[f"{family}_capacity"] = capacity
        counts[f"{family}_out_offset"] = int(layout.get(family, 0))
        counts[f"{family}_carry"] = float(descriptor.carry) if descriptor is not None else 0.0
        counts[f"{family}_groups"] = capacity if family == "chains" else -(-capacity // 256)
    return values, counts, streams


# ----------------------------------------------------------------------------------------------- the settings

def card_geometry(presentation: Any) -> dict:
    """What the card decides of the frame: the oriented content's device pixels, the framed aperture, the scene
    target's bucketed allocation and the shafts' half resolution (``render``'s ``item_pixel_rect``,
    ``framed_aperture_scale``, ``SceneTarget.allocation``, ``_ShaftTargets.size``)."""
    from rendering.quick.scene3d.target import _bucket
    from rendering.quick.visualizer.native_route import waveform_card_size
    from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale

    width, height = waveform_card_size(presentation)
    return {"size": (width, height), "aperture": framed_aperture_scale(presentation),
            "allocation": (_bucket(width), _bucket(height)), "shafts": (max(1, width // 2), max(1, height // 2))}


def settings_values(parameters, geometry: dict) -> dict[str, Any]:
    """The route's settings by name (``<program>_<member>``, ``<program>_<member>@<pass>``, the post steps' own)."""
    from rendering.quick.scene3d.defocus import DEFOCUS_TAPS
    from rendering.quick.scene3d.probe import scene3d_probe_face_rotation, scene3d_probe_projection
    from rendering.gl_programs.extruded_bubble_scene import light_on_screen, parameter_camera
    from rendering.quick.visualizer.implementation_values import parameter
    from rendering.quick.visualizer.implementations import extruded_bubble as eb
    from widgets.spotify_visualizer.extruded_bubble_geometry import WORLD_CENTER, WORLD_HALF, WORLD_UNIT

    scene = _scene(parameters)
    floats = eb._floats
    width, height = geometry["size"]
    aperture = geometry["aperture"]
    optical = eb._optical_height(parameters, aperture, width, height)
    view_to_world, world_to_view, eye, tan, projection = parameter_camera(parameters, width / height, aperture)
    knobs = _deep(scene["knobs"], eye)
    probe_size = eb._PROBE_SIZE[scene["detail"].name]
    probe_levels = int(math.log2(probe_size)) + 1
    pixel = 2.0 * tan[1] / height
    shift = tuple(float(v) for v in eb.LENS_SHIFT)      # the Python owner's (zero in the product)
    values ={program: _defaults(program) for program in PROGRAMS}

    def put(program: str, given: dict) -> None:
        held = values[program]
        for name, value in given.items():
            if name in held:
                held[name] = value

    put("beads", {"uDriftFadeOut": 0.0})
    put("specks", {"uDriftFadeOut": 0.0})
    common = eb._common({**knobs, "fan_reach": float(knobs.get("fan_reach", 0.6))}, view_to_world=view_to_world,
                        eye=eye, tan=tan, time=0.0, surface_travel=0.0, rays=0.0, streak=(0.0, 1.0))
    axis = tuple(0.5 * (s + e) for s, e in zip(scene["source"], scene["end"]))
    common.update({"uDustBands": (float(knobs["band_freq"]), float(WORLD_UNIT), float(knobs["band_gather"])),
                   "uEmberBand": (*axis, float(knobs.get("ember_band", 0.0)))})
    for program in PROGRAMS:
        if program != "blur":
            put(program, common)
    put("shafts", {"uLensShift": shift, "uRaySource": floats(knobs["ray_source"]), "uRayEnd": floats(knobs["ray_end"]),
                   "uLightFaces": floats(knobs["scene_light"]["faces"]),
                   "uLightTravel": floats(knobs["scene_light"]["travel"]),
                   "uLightAxis": floats(knobs["scene_light"]["axis"]),
                   "uLightReach": floats(knobs["scene_light"]["reach"])})
    sun_screen = light_on_screen(knobs["sun_below"], world_to_view, projection, (width, height))
    view = {"uWorldToView": floats(world_to_view), "uEye": floats(eye), "uProjection": floats(projection),
            "uPixel": pixel, "uPixelSize": pixel, "uFrameSize": (float(width), float(height)),
            "uSunScreen": sun_screen, "uProbeLevels": float(probe_levels), "uLensShift": shift}
    near_coc, near_max = 22.0 * optical / 941.0, eb._near_spread(optical)
    for program in _GLASS:
        put(program, {**view, **eb._glass(knobs, program in ("near", "near_clusters")), "uNearCoc": near_coc,
                      "uNearMax": near_max})
    put("trails", {**view, "uFocus": float(knobs.get("focus", 4.2)), "uAperture": float(knobs.get("aperture", 3.0)),
                   "uNearCoc": near_coc, "uNearMax": near_max})
    spread = float(parameter(parameters, "extruded_bubble_particle_spread"))
    put("beads", {"uWorldCenter": WORLD_CENTER, "uWorldHalf": WORLD_HALF, "uStreamSource": scene["source"],
                  "uStreamEnd": scene["end"], "uParticleSpread": spread, "uSceneEmission": scene["scene_emission"],
                  "uBeadsPerChain": eb._BEADS_PER_CHAIN,
                  "uBeadScatter": float(parameter(parameters, "extruded_bubble_bead_scatter")),
                  "uStreamLanes": float(knobs.get("stream_lanes", 0.0)), "uTrailFizz": scene["trail_fizz"]})
    for program in ("trails", "beads"):
        put(program, {"uTrails": scene["trails"]})
    put("specks", {"uWorldToView": floats(world_to_view), "uRowMajor": 0, "uProjection": floats(projection),
                   "uPixel": pixel, "uParticleLighting": 1.0, "uSpeckWarm": floats(knobs["speck_warm"]),
                   "uWorldCenter": WORLD_CENTER, "uWorldHalf": WORLD_HALF, "uWorldUnit": WORLD_UNIT,
                   "uParticleSpread": spread, "uSceneEmission": scene["scene_emission"],
                   "uSpeckSource": scene["source"], "uSpeckEnd": scene["end"],
                   "uWarmShare": float(knobs["warm_share"]),
                   "uClouds": (float(knobs["cloud_contrast"]), float(knobs["cloud_floor"]),
                               float(knobs["cloud_glow"])),
                   "uBandFreq": float(knobs["band_freq"]), "uBandGather": float(knobs["band_gather"]),
                   "uSpeckSize": float(knobs["speck_size"])})
    put("proxies", {"uSpecks": 1.0, "uSpeckBloom": 0.0, "uParticleActivity": 1.0, "uParticleLighting": 0.0,
                    "uParticleRadiusShare": 1.0, "uSpeckWarm": floats(knobs["light"]), "uRowMajor": 1,
                    "uPixel": 2.0 / probe_size})
    put("probe_backdrop", {"uTan": (1.0, 1.0), "uLensShift": (0.0, 0.0), "uProbeMode": 1.0,
                           "uFrameSize": (float(probe_size), float(probe_size))})
    put("backdrop", {"uLensShift": shift, "uFrameSize": (float(width), float(height)),
                     "uShaftContentPx": floats(geometry["shafts"])})
    allocation = (float(geometry["allocation"][0]), float(geometry["allocation"][1]))
    for program in (*_GLASS, "trails"):
        put(program, {"uTargetSize": allocation})

    # Each pass's own: the cube faces' views and the blur's directions (scoped; the unscoped member is no pass's).
    scoped: dict[str, Any] = {}
    face_projection = floats(scene3d_probe_projection(0.05, 200.0))
    for face in range(6):
        rotation = floats(scene3d_probe_face_rotation(face))
        scoped[f"{member_name('probe_backdrop', 'uViewToWorld')}@{FACE_PASSES[face]}"] = rotation
        scoped[f"{member_name('proxies', 'uWorldToView')}@{PROXY_PASSES[face]}"] = rotation
        scoped[f"{member_name('proxies', 'uProjection')}@{PROXY_PASSES[face]}"] = face_projection
    for name, step in zip(BLUR_PASSES, ((1.0, 0.0), (0.0, 1.0))):
        scoped[f"{member_name('blur', 'uStep')}@{name}"] = step
    for program, member in (("probe_backdrop", "uViewToWorld"), ("proxies", "uWorldToView"),
                            ("proxies", "uProjection"), ("blur", "uStep")):
        values[program].pop(member, None)

    out: dict[str, Any] = {}
    for program in PROGRAMS:
        for member, value in values[program].items():
            if member not in STATE_MEMBERS[program]:
                out[member_name(program, member)] = _plain(value)
    out.update({name: _plain(value) for name, value in scoped.items()})
    tap_area = math.pi * near_max * near_max / DEFOCUS_TAPS
    out.update({"u_bloom_strength": float(eb._BLOOM), "u_hdr_exposure": 1.0, "u_defocus_radius": float(near_max),
                "u_defocus_highlight": _HIGHLIGHT,
                "u_defocus_level": max(int(math.floor(math.log2(max(math.sqrt(tap_area), 1.0)))), 0)})
    return out


def _plain(value: Any) -> Any:
    """A value as JSON numbers (tuples of floats, ints kept)."""
    if isinstance(value, (bool, int)):
        return int(value)
    if isinstance(value, float) or hasattr(value, "__float__") and not hasattr(value, "__len__"):
        return float(value)
    return tuple(_plain(v) for v in value)


_SETTINGS_CACHE: list = [None, None]


def settings(snapshot: Any, card: dict) -> dict:
    """The route's settings function (``GENERIC_MODE_SETTINGS``): computed once per Settings or card change."""
    parameters = snapshot.logical.mode_state.parameters
    geometry = card_geometry(snapshot.presentation)
    from rendering.quick.visualizer.implementations.extruded_bubble import LENS_SHIFT

    key = (parameters, tuple(sorted((k, v if not isinstance(v, tuple) else tuple(v)) for k, v in geometry.items())),
           tuple(LENS_SHIFT))
    if _SETTINGS_CACHE[0] is not None and _SETTINGS_CACHE[0] == key:
        return _SETTINGS_CACHE[1]
    values = settings_values(parameters, geometry)
    _SETTINGS_CACHE[:] = [key, values]
    return values


__all__ = ["BLUR_PASSES", "FACE_PASSES", "PROXY_PASSES", "STATE_MEMBERS", "block_members", "card_geometry",
           "settings", "settings_values", "state_fields", "state_values"]
