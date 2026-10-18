"""Extruded Bubble's scene from its Settings: the programs' knobs, the camera and the instance records.

No GL: the renderer (``rendering/quick/visualizer/implementations/extruded_bubble.py``) uploads what these return,
and the composition lab (``tools/labs/extruded_bubble_lab.py``) shares ``ENGINE`` and ``MODES`` so a lab scene and a
preset authored through the Settings are the same knobs (``Extruded_Bubble_Target.md`` section 9).

**Knobs.** ``ENGINE`` is the same for every scene; ``MODES`` holds what a Light Type implies; ``scene_knobs`` reads
the mode's Settings (``extruded_bubble_*``) on top: colours (0..255 to linear 0..1), the light's direction and
strength, rays, water, glass, particles and lens, each mapped as section 9's table says. ``ray_strength`` reads the
Light Rays range at the passage level (the one knob that moves with the music every frame).

**Camera.** A 62 degree vertical field of view from the eye at the origin; tilt (pitch) and turn (yaw) from the live
view pose, Scene Scale as a zoom. **Volume.** The simulation's normalised volume (x, y -1..1 across the view, z 0..1
near to far) maps into the view at depth ``DEPTH_NEAR + z * DEPTH_SPAN`` with radii as shares of the half view height
(a radius of 0.1 is a tenth of the half height on screen at any depth), as the lab sizes its populations.

**Instances.** Shell records are (world centre, world radius, seed, kind): kind 0 a bubble, 3 a near giant (drawn
by the near defocus layer only). Clusters are three member spheres then (members, neck blend, seed, 0). Glint proxies
are each bubble's highlight as the scene probe sees it (particle records: point, radius, brightness, warm, seed, 0).
"""
from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np

from rendering.gl_programs.scene3d_water import water_sun_below

FOV_Y_DEGREES = 62.0
NEAR, FAR = 0.05, 200.0
DEPTH_NEAR, DEPTH_SPAN = 6.0, 26.0
SURFACE_Y = 9.0
SHELL_FLOATS, CLUSTER_FLOATS, PROXY_FLOATS = 6, 16, 8
NEAR_GIANTS = 3
# What a Light Type implies (the lab's "surface" and "deep" modes) and what every scene shares.
ENGINE = dict(shell=0.03, iors=(1.15, 2.0, 1.0), lens=1.0)
MODES = {
    "surface": dict(near_lens=1.0, near_reflect=0.08, shaft_fan=1.0, fan_rays=70.0, fan_reach=0.65, shaft_scale=0.55,
                    shaft_soft=0.35, ray_focus=0.3, ray_cut=0.1, surface_sky=0.35, glint_power=120.0,
                    glint_sharp=300.0, probe_fill=2.0, proxy_power=10.0, rough=0.05, chains=3.0),
    "deep": dict(crisp=1.0),
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
    knobs: dict[str, object] = {**ENGINE, **MODES[mode], "mode": mode}
    light = _rgb(_p(parameters, "light_colour"))
    water, deep = _rgb(_p(parameters, "water_colour")), _rgb(_p(parameters, "depth_colour"))
    water_hue = _hue(water)
    strength = float(_p(parameters, "light_strength"))
    around, height = (float(v) for v in _p(parameters, "light_direction"))
    direction = _unit(direction_vector(around, height))
    knobs.update(water=water, deep=deep, light=light, sky=_mix(water_hue, light, 0.6),
                 shaft=tuple(0.85 * c for c in _mix(water_hue, light, 0.45)), absorb=(0.08, 0.05, 0.035),
                 exposure=float(_p(parameters, "exposure")))
    if mode == "surface":
        knobs.update(sun=direction, sun_below=water_sun_below_safe(direction), spec_dir=(0.0, 1.0, 0.0),
                     surface_gain=2.0 * strength * float(_p(parameters, "surface_brightness")),
                     glint_power=float(MODES["surface"]["glint_power"]) * strength, light_power=0.0,
                     surface=SURFACE_Y, shaft_y=SURFACE_Y)
    else:
        # No surface in view: the light is in the water; its highlights face the bubbles from where it is.
        knobs.update(sun=direction, sun_below=direction, spec_dir=direction, surface_gain=0.6,
                     glint_power=600.0 * strength, light_power=1.2 * strength, surface=60.0, shaft_y=16.0,
                     glow=0.6, ray_focus=1.0)
    softness = float(_p(parameters, "ray_softness"))
    knobs.update(fan_contrast=0.8 + (0.2 - 0.8) * softness, fan_march=0.15 + (0.6 - 0.15) * softness,
                 fan_rays=80.0 + (30.0 - 80.0) * softness, fan_reach=0.3 + 0.7 * float(_p(parameters, "ray_reach")))
    knobs.update(mist=float(_p(parameters, "haze")), veils=float(_p(parameters, "veils")))
    clarity, softness = float(_p(parameters, "clarity")), float(_p(parameters, "softness"))
    knobs.update(face_reflect=1.0 + (0.2 - 1.0) * clarity,
                 probe_fill=float(MODES["surface"]["probe_fill"] if mode == "surface" else 3.0) * float(_p(parameters, "rim_glow")),
                 film=float(_p(parameters, "iridescence")), film_range=(255.0, 345.0),
                 rough=0.03 + 0.1 * softness, inner_blur=0.12 + 0.5 * softness,
                 sparkle=float(_p(parameters, "sparkle")), glint_sharp=300.0)
    knobs.update(specks_scale=2.4, speck_size=float(_p(parameters, "particle_size")),
                 speck_warm=_rgb(_p(parameters, "particle_colour")), warm_share=float(_p(parameters, "particle_warmth")),
                 speck_bloom=float(_p(parameters, "particle_glow")), banded=bool(_p(parameters, "particle_bands")),
                 cloud_contrast=1.5 + 2.5 * float(_p(parameters, "band_contrast")))
    knobs.update(focus=2.5 + 3.0 * float(_p(parameters, "focus")), aperture=0.3 + 2.7 * float(_p(parameters, "aperture")))
    return knobs


def ray_strength(parameters: Mapping[str, object], level: float) -> float:
    """The Light Rays range read at the passage ``level`` (0..1), or none when the rays are off."""
    if not bool(_p(parameters, "rays_enabled")):
        return 0.0
    low, high = (float(v) for v in _p(parameters, "rays"))
    return low + (high - low) * max(0.0, min(1.0, float(level)))


def camera(turn: float, tilt: float, aspect: float, scale: float = 1.0):
    """(view_to_world, world_to_view, tan, projection): column-major mat3s (GL order) and the mat4 projection.
    ``turn`` -1..1 is a full circle of yaw; ``tilt`` -0.5..0.5 pitches up to +-45 degrees beyond the authored 16
    degrees up (looking toward the surface, as the mocks do); ``scale`` above 1 zooms in."""
    pitch = math.radians(16.0 + 90.0 * float(tilt))
    yaw = math.pi * float(turn)
    cp, sp, cy, sy = math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    # View axes in world: right, up, back (the camera looks along -back: up and ahead when pitched up).
    right = (cy, 0.0, -sy)
    back = (sy * cp, -sp, cy * cp)
    up = (back[1] * right[2] - back[2] * right[1], back[2] * right[0] - back[0] * right[2],
          back[0] * right[1] - back[1] * right[0])
    view_to_world = (*right, *up, *back)
    world_to_view = (right[0], up[0], back[0], right[1], up[1], back[1], right[2], up[2], back[2])
    tan_y = math.tan(math.radians(FOV_Y_DEGREES) / 2.0) / max(float(scale), 1e-3)
    tan = (tan_y * aspect, tan_y)
    f = 1.0 / tan_y
    projection = (f / aspect, 0.0, 0.0, 0.0, 0.0, f, 0.0, 0.0, 0.0, 0.0, (FAR + NEAR) / (NEAR - FAR), -1.0,
                  0.0, 0.0, 2.0 * FAR * NEAR / (NEAR - FAR), 0.0)
    return view_to_world, world_to_view, tan, projection


def _axes(view_to_world) -> np.ndarray:
    """Rows: the view's right, up and back axes in world (a view vector times this is its world vector)."""
    return np.asarray(view_to_world, dtype=np.float64).reshape(3, 3)


def volume_to_world(x: float, y: float, z: float, view_to_world, tan) -> tuple[tuple[float, float, float], float]:
    """A point of the simulation's volume in world space (eye at the origin) and its view depth."""
    depth = DEPTH_NEAR + DEPTH_SPAN * float(z)
    view = np.array((float(x) * 1.12 * tan[0] * depth, float(y) * 1.1 * tan[1] * depth, -depth))
    return tuple(float(v) for v in view @ _axes(view_to_world)), depth  # type: ignore[return-value]


def bubble_instances(records, view_to_world, tan) -> np.ndarray:
    """The simulation's bubble records (x, y, z, radius, alpha, swell, identity, cluster: 8 floats each) as shell
    instances. A fading bubble shrinks with its fade (its light leaves with it); fused members are drawn by the
    cluster pass, not here."""
    rows = np.asarray(records, dtype=np.float64).reshape(-1, 8)
    rows = rows[(rows[:, 7] < 0.0) & (rows[:, 4] > 0.02)]
    depth = DEPTH_NEAR + DEPTH_SPAN * rows[:, 2]
    view = np.column_stack((rows[:, 0] * 1.12 * tan[0] * depth, rows[:, 1] * 1.1 * tan[1] * depth, -depth))
    out = np.empty((len(rows), SHELL_FLOATS), dtype=np.float32)
    out[:, :3] = view @ _axes(view_to_world)
    out[:, 3] = rows[:, 3] * tan[1] * depth * np.sqrt(rows[:, 4])
    out[:, 4] = np.mod(rows[:, 6] * 0.6180339887, 1.0)
    out[:, 5] = 0.0
    return out


def cluster_instances(records, clusters, view_to_world, tan) -> np.ndarray:
    """Each fused cluster as the cluster pass's instance."""
    out = []
    for i in range(0, len(clusters), 4):
        count = int(clusters[i])
        members = []
        for slot in clusters[i + 1:i + 1 + count]:
            j = int(slot) * 8
            x, y, z, radius = records[j:j + 4]
            centre, depth = volume_to_world(x, y, z, view_to_world, tan)
            members.append((*centre, radius * tan[1] * depth))
        if len(members) < 2:
            continue
        blend = 0.15 * max(m[3] for m in members)
        padded = members + [(0.0, 0.0, 0.0, 0.0)] * (3 - len(members))
        out.append(tuple(v for m in padded for v in m) + (float(len(members)), blend,
                                                           (clusters[i + 1] * 0.618) % 1.0, 0.0))
    return np.asarray(out, dtype=np.float32).reshape(-1, CLUSTER_FLOATS)


def near_giants(time: float, view_to_world, tan) -> np.ndarray:
    """A few huge, out-of-focus bubbles just in front of the lens at the frame's edges (the mocks' corners), drifting
    very slowly so they never jump. View-anchored: they float at the camera, wherever it turns."""
    out = np.empty((NEAR_GIANTS, SHELL_FLOATS), dtype=np.float32)
    axes = _axes(view_to_world)
    t = float(time)
    for k, (u, v, depth, radius, seed) in enumerate(((-0.92, -0.55, 3.2, 0.68, 0.31),
                                                     (0.95, -0.42, 3.0, 0.62, 0.57),
                                                     (-0.88, 0.62, 3.5, 0.55, 0.83))):
        u += 0.04 * math.sin(t * 0.05 + 6.28 * seed)
        v += 0.05 * math.sin(t * 0.037 + 3.1 * seed)
        view = np.array((u * tan[0] * depth, v * tan[1] * depth, -depth))
        out[k, :3] = view @ axes
        out[k, 3:] = (radius, seed, 3.0)
    return out


def glint_proxies(shells: np.ndarray, sun_below, power: float, size: float = 0.6) -> np.ndarray:
    """Each bubble's glint toward the light as the probe sees it: a small bright point near its surface, so its
    neighbours mirror it (bubbles sparkling in each other)."""
    bubbles = shells[(shells[:, 5] == 0.0) & (shells[:, 3] > 0.01)]
    out = np.zeros((len(bubbles), PROXY_FLOATS), dtype=np.float32)
    out[:, :3] = bubbles[:, :3] + np.asarray(sun_below, dtype=np.float32)[None, :] * bubbles[:, 3:4] * 0.7
    out[:, 3] = np.maximum(bubbles[:, 3] * size, 0.004)
    out[:, 4] = power
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
    return ((projection[0] * view[0] / -view[2] * 0.5 + 0.5) * width,
            (projection[5] * view[1] / -view[2] * 0.5 + 0.5) * height, 1.0)


__all__ = ["CLUSTER_FLOATS", "DEPTH_NEAR", "DEPTH_SPAN", "ENGINE", "FAR", "FOV_Y_DEGREES", "MODES", "NEAR",
           "NEAR_GIANTS", "PROXY_FLOATS", "SHELL_FLOATS", "SURFACE_Y", "bubble_instances", "camera",
           "cluster_instances", "direction_vector", "glint_proxies", "light_on_screen", "near_giants", "ray_strength",
           "scene_knobs", "screen_streak", "volume_to_world"]
