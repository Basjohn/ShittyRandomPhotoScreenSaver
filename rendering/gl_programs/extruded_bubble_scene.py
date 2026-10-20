"""Extruded Bubble's scene from its Settings: the programs' knobs, the camera and the instance records.

No GL: the renderer (``rendering/quick/visualizer/implementations/extruded_bubble.py``) uploads what these return,
and the composition lab (``tools/labs/extruded_bubble_lab.py``) shares ``ENGINE`` and ``MODES`` so a lab scene and a
preset authored through the Settings are the same knobs (``Extruded_Bubble_Target.md`` section 9).

**Knobs.** ``ENGINE`` is the same for every scene; ``MODES`` holds what a Light Type implies; ``scene_knobs`` reads
the mode's Settings (``extruded_bubble_*``) on top: colours (0..255 to linear 0..1), the light's direction and
strength, rays, water, glass, particles and lens, each mapped as section 9's table says. ``ray_strength`` and
``ray_motion`` read the Light Rays range, Ray Flicker and the fan's reach at the simulation's ray driver and sustain
(never the raw passage level, which holds at 1 through loud music).

**Camera.** A 62 degree vertical field of view from the eye at the independent scene origin;
turn, tilt, scale and lens shift affect view/projection only. The simulation and procedural
populations inhabit the fixed world domain in ``extruded_bubble_geometry``.

**Instances.** Packing preserves physical position/radius and carries lifetime opacity
separately. No depth scaling, camera-dependent wrapping or view-relative reinstallation.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np

from rendering.gl_programs.scene3d_water import water_sun_below
from widgets.spotify_visualizer.extruded_bubble_geometry import WATER_SURFACE_Y

FOV_Y_DEGREES = 62.0
NEAR, FAR = 0.05, 200.0
SURFACE_Y = WATER_SURFACE_Y
SHELL_FLOATS, CLUSTER_FLOATS, PROXY_FLOATS = 7, 19, 8
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
        # Its colour carries through the water it lights (its glow, beams and veils take its colour; under a surface
        # the sky's light is mostly the water's own).
        knobs.update(sun=direction, sun_below=direction, spec_dir=direction, surface_gain=0.6,
                     glint_power=600.0 * strength, light_power=1.2 * strength, surface=60.0, shaft_y=16.0,
                     glow=0.6, ray_focus=1.0, sky=_mix(water_hue, light, 0.85),
                     shaft=tuple(0.95 * c for c in _mix(water_hue, light, 0.85)))
    softness = float(_p(parameters, "ray_softness"))
    knobs.update(shaft_soft=softness,
                 fan_contrast=0.8 + (0.2 - 0.8) * softness, fan_march=0.15 + (0.6 - 0.15) * softness,
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
                 speck_bloom=float(_p(parameters, "particle_glow")), banded=bool(_p(parameters, "particle_bands")))
    # Clouds stretched along the stream; Particle Bands sharpens them into the sixth mock's diagonal bands.
    banded = bool(knobs["banded"])
    knobs.update(cloud_contrast=1.5 + 2.5 * float(_p(parameters, "band_contrast")) if banded else 1.5,
                 cloud_floor=0.03 if banded else 0.12, cloud_glow=1.8 if banded else 1.3, band_freq=9.0)
    knobs.update(focus=2.5 + 3.0 * float(_p(parameters, "focus")), aperture=0.3 + 2.7 * float(_p(parameters, "aperture")))
    return knobs


SPECKS_FULL = 216000          # specks at the top of the Particles range (the lab's heaviest scene, the sixth mock)


def speck_amount(parameters: Mapping[str, object], emission: float) -> tuple[float, float]:
    """Consume the already Range-resolved emission follower once (never the raw musical level).

    Return (density share, brightness); the authored range is mapped in the simulation,
    not here. The nonlinear density curve is retained, unvalidated on a real display."""
    # `emission` is already the smoothed value of the operator's Particles Range,
    # resolved exactly once by ExtrudedBubbleSimulation. Never apply that Range again.
    value = max(0.0, min(1.0, float(emission)))
    return value * value, 2.4 * value


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


def camera(turn: float, tilt: float, aspect: float, scale: float = 1.0, shift=(0.0, 0.0)):
    """(view_to_world, world_to_view, tan, projection): column-major mat3s (GL order) and the mat4 projection.
    ``turn`` -1..1 is a full circle of yaw; ``tilt`` -0.5..0.5 pitches up to +-45 degrees beyond the authored 16
    degrees up (looking toward the surface, as the mocks do); ``scale`` above 1 zooms in; ``shift`` (NDC, from
    ``lens_shift``) moves the view's centre on screen (an off-axis frustum: Scene Pan, no parallax)."""
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
    projection = (f / aspect, 0.0, 0.0, 0.0, 0.0, f, 0.0, 0.0, -float(shift[0]), -float(shift[1]),
                  (FAR + NEAR) / (NEAR - FAR), -1.0, 0.0, 0.0, 2.0 * FAR * NEAR / (NEAR - FAR), 0.0)
    return view_to_world, world_to_view, tan, projection


def lens_shift(pan_x: float, pan_y: float) -> tuple[float, float]:
    """Scene Pan (fractions of the card, y down, as the framed camera's envelope bounds it) as an NDC lens shift."""
    return 2.0 * float(pan_x), -2.0 * float(pan_y)


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


def glint_proxies(shells: np.ndarray, sun_below, power: float, size: float = 0.6) -> np.ndarray:
    """Each bubble's glint toward the light as the probe sees it: a small bright point near its surface, so its
    neighbours mirror it (bubbles sparkling in each other)."""
    bubbles = shells[(shells[:, 5] == 0.0) & (shells[:, 3] > 0.01)]
    out = np.zeros((len(bubbles), PROXY_FLOATS), dtype=np.float32)
    out[:, :3] = bubbles[:, :3] + np.asarray(sun_below, dtype=np.float32)[None, :] * bubbles[:, 3:4] * 0.7
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
           "PROXY_FLOATS", "SHELL_FLOATS", "SURFACE_Y", "bubble_instances", "camera",
           "cluster_instances", "direction_vector", "glint_proxies", "lens_shift", "light_on_screen", "ray_strength",
           "ray_motion", "scene_knobs", "screen_streak", "speck_amount", "SPECKS_FULL"]
