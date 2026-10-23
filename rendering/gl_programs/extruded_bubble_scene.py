"""Extruded Bubble's scene from its Settings: the programs' knobs, the camera and the instance records.

No GL: the renderer (``rendering/quick/visualizer/implementations/extruded_bubble.py``) uploads what these return,
and the composition lab (``tools/labs/extruded_bubble_lab.py``) shares ``ENGINE`` and ``MODES`` so a lab scene and a
preset authored through the Settings are the same knobs (``Extruded_Bubble/Target.md`` section 9).

**Knobs.** ``ENGINE`` is the same for every scene; ``MODES`` holds what a Light Type implies; ``scene_knobs`` reads
the mode's Settings (``extruded_bubble_*``) on top: colours (0..255 to linear 0..1), the light's direction and
strength, rays, water, glass, particles and lens, each mapped as section 9's table says. ``ray_strength`` and
``ray_motion`` read the Light Rays range, Ray Flicker and the fan's reach at the simulation's ray driver and sustain
(never the raw passage level, which holds at 1 through loud music).

**Camera.** A 45-degree default vertical field of view, now authorable 35–62 degrees.
The product uses ``physical_camera`` for separate orbit (existing Alt+left drag),
real lateral/up camera translation (Scene Pan), and dolly distance (Scene Scale).
The sensor is centred, and the visible FOV is not changed by pan or zoom.
Native appearance, peripheral perspective and gesture parity require visual acceptance.
The simulation and procedural populations inhabit the fixed world domain in
``extruded_bubble_geometry``.

**Instances.** Packing preserves physical position/radius and carries lifetime opacity
separately. No depth scaling, camera-dependent wrapping or view-relative reinstallation.
"""
from __future__ import annotations

from core.settings.visualizer_paths import admit_path, direction_of, world_point

import math
from collections.abc import Mapping

import numpy as np

from rendering.gl_programs.scene3d_water import water_sun_below
from widgets.spotify_visualizer.extruded_bubble_geometry import WATER_SURFACE_Y, WORLD_UNIT
from core.settings.extruded_bubble_camera import camera_axes, resolve_camera_position, ORBIT_DISTANCE, ORBIT_PIVOT

FOV_Y_DEGREES = 45.0  # narrower photographic comparison; operator visual acceptance still open
NEAR, FAR = 0.05, 200.0
SURFACE_Y = WATER_SURFACE_Y
SHELL_FLOATS, CLUSTER_FLOATS, PROXY_FLOATS = 7, 19, 8
# What a Light Type implies (the lab's "surface" and "deep" modes) and what every scene shares.
ENGINE = dict(shell=0.03, iors=(1.15, 2.0, 1.0), lens=1.0)
MODES = {
    "surface": dict(near_lens=1.0, near_reflect=0.08, shaft_fan=1.0, fan_reach=0.65, shaft_scale=0.55,
                    shaft_soft=0.35, ray_focus=0.3, ray_cut=0.1, surface_sky=0.35, glint_power=120.0,
                    glint_sharp=300.0, probe_fill=2.0, proxy_power=10.0, rough=0.05, chains=3.0),
    "deep": dict(crisp=1.0, proxy_power=2.5),
}
_LIGHT_TYPES = {"Sunlit Surface": "surface", "Deep Light": "deep"}


def _p(parameters: Mapping[str, object], key: str):
    return parameters[f"extruded_bubble_{key}"]


def _rgb(value) -> tuple[float, float, float]:
    return tuple(max(0.0, min(255.0, float(c))) / 255.0 for c in list(value)[:3])  # type: ignore[return-value]


def _hue(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    top = max(max(rgb), 1e-4)
    return tuple(c / top for c in rgb)  # type: ignore[return-value]


def _mix(a, b, t: float):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def _unit(v) -> tuple[float, float, float]:
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(float(c) / length for c in v)  # type: ignore[return-value]


def direction_vector(around: float, height: float) -> tuple[float, float, float]:
    """A direction mapper value as a world vector: around 0 is straight ahead (away from the default view), clockwise
    seen from above; height lifts it toward straight up."""
    a, h = math.radians(around), math.radians(height)
    return math.sin(a) * math.cos(h), math.sin(h), -math.cos(a) * math.cos(h)


def water_sun_below_safe(direction):
    """The sun above the water as seen from below it (refracted); a sun below the horizon is lifted to it."""
    x, y, z = direction
    return water_sun_below((x, max(y, 0.05), z))


def scene_knobs(parameters: Mapping[str, object]) -> dict[str, object]:
    """The programs' knobs for these Settings (all but the rays' strength, ``ray_strength``)."""
    mode = _LIGHT_TYPES[str(_p(parameters, "light_type"))]
    knobs: dict[str, object] = {**ENGINE, **MODES[mode], "mode": mode,
                               "lighting_scene": float(_p(parameters, "lighting_coverage") == "SCENE"),
                               "beam_width": float(_p(parameters, "beam_width"))}
    light = _rgb(_p(parameters, "light_colour"))
    water, deep = _rgb(_p(parameters, "water_colour")), _rgb(_p(parameters, "depth_colour"))
    water_hue = _hue(water)
    strength = float(_p(parameters, "light_strength"))
    knobs["proxy_power"] = float(knobs["proxy_power"]) * strength
    light_path = admit_path(_p(parameters, "light_direction"), [0.0, 55.0], 'light')
    direction = _unit(tuple(-v for v in direction_of(light_path)))
    # World-space light source/end and its separate authored beam path.
    ray_path = admit_path(parameters.get('extruded_bubble_ray_path', [0., 1., 0., 0., -1., 0.]),
                          [0., 1., 0., 0., -1., 0.], 'light')
    knobs.update(water=water, deep=deep, light=light, light_strength=strength,
                 specular_light=tuple(c * 300.0 * strength for c in light),
                 sky=_mix(water_hue, light, 0.6),
                 shaft=tuple(0.85 * c for c in _mix(water_hue, light, 0.45)), absorb=(0.08, 0.05, 0.035),
                 exposure=float(_p(parameters, "exposure")),
                 light_source=world_point(light_path[:3]),
                 light_end=world_point(light_path[3:]),
                 ray_source=world_point(ray_path[:3]),
                 ray_end=world_point(ray_path[3:]))
    if mode == "surface":
        # Surface glass sees the same refracted distant sun as water, particles
        # and probe glints; a world-up lobe invents a second physical emitter.
        sun_below = water_sun_below_safe(direction)
        knobs.update(sun=direction, sun_below=sun_below, spec_dir=sun_below,
                     surface_gain=2.0 * strength * float(_p(parameters, "surface_brightness")),
                     glint_power=float(MODES["surface"]["glint_power"]) * strength, light_power=0.0,
                     surface=SURFACE_Y, shaft_y=SURFACE_Y)
    else:
        # Deep scene: visible emitter, shaft origin and glint source are one
        # authored Light Source. The separately editable Ray End still shapes
        # the shaft segment; the older Ray Source is legacy preset metadata.
        knobs["ray_source"] = knobs["light_source"]
        # No surface in view: the light is in the water; its highlights face the bubbles from where it is.
        # Its colour carries through the water it lights (its glow, beams and veils take its colour; under a surface
        # the sky's light is mostly the water's own).
        knobs.update(sun=direction, sun_below=direction, spec_dir=direction, surface_gain=0.6,
                     glint_power=600.0 * strength, light_power=1.2 * strength, surface=60.0, shaft_y=16.0,
                     glow=0.6, ray_focus=1.0, sky=_mix(water_hue, light, 0.85),
                     shaft=tuple(0.95 * c for c in _mix(water_hue, light, 0.85)))
    knobs["surface_shaft"] = 1.0 if mode == "surface" else 0.0
    softness = float(_p(parameters, "ray_softness"))
    knobs.update(shaft_soft=softness, fan_contrast=0.8+(0.2-0.8)*softness,
                 fan_march=0.15+(0.6-0.15)*softness, fan_rays=80.0+(30.0-80.0)*softness, fan_reach=0.3 + 0.7 * float(_p(parameters, "ray_reach")))
    knobs.update(mist=float(_p(parameters, "haze")), veils=float(_p(parameters, "veils")))
    clarity, softness = float(_p(parameters, "clarity")), float(_p(parameters, "softness"))
    knobs.update(face_reflect=1.0 + (0.2 - 1.0) * clarity,
                 probe_fill=float(MODES["surface"]["probe_fill"] if mode == "surface" else 3.0) * float(_p(parameters, "rim_glow")),
                 film=float(_p(parameters, "iridescence")), film_range=(255.0, 345.0),
                 rough=0.03 + 0.1 * softness, inner_blur=0.12 + 0.5 * softness,
                 sparkle=float(_p(parameters, "sparkle")), glint_sharp=300.0)
    knobs.update(specks_scale=2.4, speck_size=float(_p(parameters, "particle_size")),
                 speck_warm=_rgb(_p(parameters, "particle_colour")), warm_share=float(_p(parameters, "particle_warmth")),
                 speck_bloom=float(_p(parameters, "particle_glow")), banded=bool(_p(parameters, "particle_bands")))
    # Clouds stretched along the stream; Particle Bands sharpens them into the sixth mock's diagonal bands.
    banded = bool(knobs["banded"])
    knobs.update(cloud_contrast=1.5 + 2.5 * float(_p(parameters, "band_contrast")) if banded else 1.5,
                 cloud_floor=0.03 if banded else 0.12, cloud_glow=1.8 if banded else 1.3, band_freq=9.0)
    knobs.update(focus=2.5 + 3.0 * float(_p(parameters, "focus")), aperture=0.3 + 2.7 * float(_p(parameters, "aperture")))
    return knobs


SPECKS_FULL = 216000          # specks at the top of the Particles range (the lab's heaviest scene, the sixth mock)


def speck_amount(emission: float) -> tuple[float, float]:
    """Consume the already Range-resolved emission follower once (never the raw musical level).

    Return (density share, per-point radiance). Amount controls density; it must
    not dim each remaining point again as its quiet size and glow contract.
    The existing full-strength radiance calibration and squared density remain.
    """
    # `emission` is already the smoothed value of the operator's Particles Range,
    # resolved exactly once by ExtrudedBubbleSimulation. Never apply that Range again.
    value = max(0.0, min(1.0, float(emission)))
    return value * value, 2.4


def ray_strength(parameters: Mapping[str, object], rays: float) -> float:
    """Resolve the authored Range once, with collapsed resting activity in silence.

    A strong quiet-music endpoint must not keep the full fan bright with no musical
    input. The continuous simulation driver opens the light from 3% resting activity
    to the authored loud endpoint; disabled rays still emit no shafts.
    """
    if not bool(_p(parameters, "rays_enabled")):
        return 0.0
    low, high = (float(v) for v in _p(parameters, "rays"))
    drive = max(0.0, min(1.0, float(rays)))
    return (low + (high - low) * drive) * (0.03 + 0.97 * drive)


def ray_motion(parameters: Mapping[str, object], rays: float, sustain: float) -> tuple[float, float]:
    """(flicker, reach scale): Ray Flicker's shimmer, deeper as the rays rise (a light shimmer stays in quiet music),
    and the fan reaching further through a held loud passage."""
    if not bool(_p(parameters, "rays_enabled")):
        return 0.0, 1.0
    rays = max(0.0, min(1.0, float(rays)))
    return (float(_p(parameters, "ray_flicker")) * (0.3 + 0.7 * rays),
            0.85 + 0.3 * max(0.0, min(1.0, float(sustain))))


def camera(turn: float, tilt: float, aspect: float, scale: float = 1.0,
           fov_y_degrees: float = FOV_Y_DEGREES):
    """(view_to_world, world_to_view, tan, projection): column-major mat3s (GL order) and the mat4 projection.
    ``turn`` -1..1 is a full circle of yaw; ``tilt`` -0.5..0.5 pitches up to +-45 degrees beyond the authored 16
    degrees up (looking toward the surface, as the mocks do). ``scale`` is a legacy
    projection-only calculation for the lab; production uses ``physical_camera``
    with real dolly distance and always calls this helper at scale 1. No off-axis
    shift is supported: panning must translate the physical eye. """
    view_to_world = camera_axes(turn, tilt)
    right, up, back = view_to_world[:3], view_to_world[3:6], view_to_world[6:9]
    world_to_view = (right[0], up[0], back[0], right[1], up[1], back[1], right[2], up[2], back[2])
    tan_y = math.tan(math.radians(max(35.0, min(62.0, float(fov_y_degrees)))) / 2.0) / max(float(scale), 1e-3)
    tan = (tan_y * aspect, tan_y)
    f = 1.0 / tan_y
    projection = (f / aspect, 0.0, 0.0, 0.0, 0.0, f, 0.0, 0.0, 0.0, 0.0,
                  (FAR + NEAR) / (NEAR - FAR), -1.0, 0.0, 0.0, 2.0 * FAR * NEAR / (NEAR - FAR), 0.0)
    return view_to_world, world_to_view, tan, projection



def physical_camera(turn: float, tilt: float, aspect: float, scale: float = 1.0,
                    pan_x: float = 0.0, pan_y: float = 0.0,
                    fov_y_degrees: float = FOV_Y_DEGREES,
                    position_offset=(0.0, 0.0, 0.0), surface_bound=True):
    """World-space physical camera: (view_to_world, world_to_view, eye, tan, projection).

    Orbit rotates around a fixed WORLD pivot while the scene remains stationary;
    Scene Pan moves the subject WITH the screen drag by translating the physical
    camera in the opposite direction; it never alters
    yaw or pitch; Scene Scale dollies the eye toward/away from that pivot, without
    shrinking the focal angle. Depth-dependent parallax follows automatically.
    All modes of presentation, including shaders and reflected cube probe, MUST
    use the returned ``eye`` to express world coordinates relative to the camera.
    """
    view_to_world, world_to_view, tan, projection = camera(
        turn, tilt, aspect, fov_y_degrees=fov_y_degrees)
    eye, _ = resolve_camera_position(turn, tilt, scale, pan_x, pan_y, fov_y_degrees,
                                     position_offset, surface_bound, axes=view_to_world)
    return view_to_world, world_to_view, eye, tan, projection



def bubble_instances(records) -> np.ndarray:
    """Pack physical xyz/radius, stable seed, kind and material opacity."""
    rows = np.asarray(records, dtype=np.float64).reshape(-1, 8)
    rows = rows[(rows[:, 7] < 0.0) & (rows[:, 4] > 0.0)]
    out = np.empty((len(rows), SHELL_FLOATS), dtype=np.float32)
    out[:, :4] = rows[:, :4]
    out[:, 4] = np.mod(rows[:, 6] * 0.6180339887, 1.0)
    out[:, 5] = 0.0
    out[:, 6] = rows[:, 4]
    return out


def wake_instances(records) -> np.ndarray:
    """Pack stable physical emitters unchanged, including frozen retiring anchors.

    xyz, reacted radius, stable ID, retirement, opacity, nominal radius.
    """
    return np.asarray(records, dtype=np.float32).reshape(-1, 8)


def cluster_instances(records, clusters) -> np.ndarray:
    """Physical union members, blend/seed and each member's lifetime opacity."""
    out = []
    for i in range(0, len(clusters), 4):
        count = int(clusters[i])
        slots = [int(slot) * 8 for slot in clusters[i + 1:i + 1 + count]]
        if len(slots) < 2:
            continue
        rows = [records[j:j + 8] for j in slots]
        members = [tuple(row[:4]) for row in rows]
        blend = .15 * max(m[3] for m in members)
        padded = members + [(0.0, 0.0, 0.0, 0.0)] * (3 - len(members))
        alphas = [row[4] for row in rows] + [0.0] * (3 - len(rows))
        out.append(tuple(float(v) for m in padded for v in m) + (float(len(members)), blend,
                   (rows[0][6] * .618) % 1.0, 0.0) + tuple(alphas))
    return np.asarray(out, dtype=np.float32).reshape(-1, CLUSTER_FLOATS)


def glint_proxies(shells: np.ndarray, sun_below, power: float, size: float = 0.6, *, light_source=None) -> np.ndarray:
    """Each bubble's glint toward the light as the probe sees it: a small bright point near its surface, so its
    neighbours mirror it (bubbles sparkling in each other)."""
    bubbles = shells[(shells[:, 5] == 0.0) & (shells[:, 3] > 0.01)]
    out = np.zeros((len(bubbles), PROXY_FLOATS), dtype=np.float32)
    light_dirs = np.broadcast_to(np.asarray(sun_below, dtype=np.float32), (len(bubbles), 3))
    if light_source is not None and len(bubbles):
        light_dirs = np.asarray(light_source, dtype=np.float32)[None, :] - bubbles[:, :3]
        light_dirs = light_dirs / np.maximum(np.linalg.norm(light_dirs, axis=1, keepdims=True), 1e-5)
    out[:, :3] = bubbles[:, :3] + light_dirs * bubbles[:, 3:4] * 0.7
    out[:, 3] = np.maximum(bubbles[:, 3] * size, 0.004)
    out[:, 4] = power * bubbles[:, 6]
    out[:, 5] = 1.0
    return out


def screen_streak(stream) -> tuple[float, float]:
    """The on-screen direction particulate clouds stretch along: the stream's across/up components."""
    x, y = float(stream[0]), float(stream[1])
    length = math.hypot(x, y)
    return (0.0, 1.0) if length < 1e-4 else (x / length, y / length)


def light_on_screen(sun_below, world_to_view, projection, size) -> tuple[float, float, float]:
    """The light's pixel position (and 1) when it lies in front of the camera, else zeros."""
    view = np.asarray(sun_below, dtype=np.float64) @ np.asarray(world_to_view, dtype=np.float64).reshape(3, 3)
    if view[2] >= -1e-3:
        return 0.0, 0.0, 0.0
    width, height = size
    return (((projection[0] * view[0] / -view[2] - projection[8]) * 0.5 + 0.5) * width,
            ((projection[5] * view[1] / -view[2] - projection[9]) * 0.5 + 0.5) * height, 1.0)


__all__ = ["CLUSTER_FLOATS", "ENGINE", "FAR", "FOV_Y_DEGREES", "MODES", "NEAR",
           "ORBIT_DISTANCE", "ORBIT_PIVOT", "PROXY_FLOATS", "SHELL_FLOATS", "SURFACE_Y", "bubble_instances", "camera", "physical_camera",
           "cluster_instances", "direction_vector", "glint_proxies", "light_on_screen", "ray_strength",
           "ray_motion", "scene_knobs", "screen_streak", "speck_amount", "SPECKS_FULL"]
