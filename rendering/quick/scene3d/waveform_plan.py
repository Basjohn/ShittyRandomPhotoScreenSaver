"""Waveform Ribbon's frame plan: every per-frame value its passes draw with, GL-free (Current_Plan.md N5.4).

Why it exists: the native core draws Waveform from a record and settings filled by name, while the Python renderer
(``rendering.quick.scene3d.waveform.WaveformScene``) computed its values inside its GL calls. This module is the one
owner of that arithmetic, and both read it: the Python scene draws with these values, and the native record and
settings are packed from them, so the two renderers draw from the same numbers.

``frame_geometry`` is the frame's cameras, history mirror, scroll, culled span and the ribbons' shared draw inputs
(the scene's ``_render_packet``); the other functions give one program's members each: the world field's receivers
(``field_receiver_values``), the fog medium (``medium_values``), the sky (``sky_values``) and the floor
(``floor_values``, with ``floor_prepass`` for its reduced pre-pass). The ribbons', strays', event sparks', fog
volumes', world field's and yielding floor's own members are their owners' (``RibbonValues``, ``burst_values``,
``fog_volume_values``, ``field_values``, ``floor_give_values``).
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from core.ribbon_continuation import continuation_bounds, frustum_axial_span
from core.waveform_ribbon_scene import FLOOR_CONTACT, SPEC
from rendering.gl_programs.mist import FOG_OFF
from rendering.gl_programs.reflection import mirror_view

# Travel Direction's x mirror from the history axis into the world: one read-only constant, not rebuilt every frame.
HISTORY_X_MIRROR = np.diag((-1., 1., 1., 1.))
HISTORY_X_MIRROR.setflags(write=False)


def floor_images(floor) -> dict:
    """The floor's maps as both renderers upload them, rows top first: ``albedo`` and ``roughness`` RGBA8 (colour
    sRGB-encoded, decoded by the floor shader), and ``slope`` RGBA16F, the height's slope per uv unit by periodic
    central differences (r, g; b 0, a 1), baked once so the floor fetches two values instead of eight. Each entry:
    (pixels as a numpy array, (width, height), format). The level chains are each renderer's box kernel. Missing
    assets fail."""
    from pathlib import Path

    from PIL import Image

    root = Path(__file__).resolve().parents[3]
    images = {}
    for key, path in (("albedo", floor.albedo), ("roughness", floor.roughness), ("height", floor.height)):
        with Image.open(root / path) as source:
            pixels = np.ascontiguousarray(np.asarray(source.convert("RGBA"), np.uint8))
        size = (int(pixels.shape[1]), int(pixels.shape[0]))
        if key != "height":
            images[key] = (pixels, size, "rgba8")
            continue
        images["slope"] = (slope_pixels(pixels[:, :, 0].astype(np.float32) / 255.), size, "rgba16f")
    return images


def slope_pixels(height: np.ndarray) -> np.ndarray:
    """A height map's slope per uv unit (periodic central differences) as RGBA16F rows: (d/du, d/dv, 0, 1)."""
    rows, columns = height.shape
    slope = np.zeros((rows, columns, 4), np.float32)
    slope[..., 0] = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * np.float32(columns / 2)
    slope[..., 1] = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * np.float32(rows / 2)
    slope[..., 3] = 1.
    return np.ascontiguousarray(slope.astype(np.float16))


def capped(size, scale: float, max_height: int) -> tuple[float, float]:
    """A reduced-resolution target: ``scale`` of the viewport, but never taller than ``max_height`` (same aspect).
    Detail per screen fraction stays that of the approved look; cost stops growing with display resolution."""
    factor = min(scale, max_height/max(size[1], 1))
    return size[0]*factor, size[1]*factor


def reflection_size(size, floor) -> tuple[int, int]:
    """The planar reflection target's size for a scene of ``size``."""
    return tuple(int(v) for v in capped(size, floor.resolution, floor.resolution_max_height))


def floor_prepass_size(size, floor) -> tuple[int, int] | None:
    """The floor's reduced pre-pass target (the reflection term alone, read back by the full pass), or None when the
    scene is short enough to evaluate it inline."""
    factor = min(1., floor.specular_max_height/max(size[1], 1))
    if factor >= 1.:
        return None
    return int(size[0]*factor), int(size[1]*factor)


def fog_grid(size, cell, slices) -> tuple[int, int, int]:
    """A fog volume's grid for a scene of ``size`` (cells of ``cell`` pixels, at most 128 x 72)."""
    return min(128, -(-size[0]//cell)), min(72, -(-size[1]//cell)), slices


def fog_focus(view) -> float:
    """The fog's focus depth: the scene pivot's view depth."""
    return -float((np.asarray(view, float)@np.array((*SPEC.pivot, 1.)))[2])


def history_mist(mist, mirror):
    """Mist uniforms for history-bound draws: their world positions are on the history axis, so the volume's
    world -> view transform takes the Travel Direction mirror first."""
    if mirror is None or 'uFogView' not in mist:
        return mist
    view = np.asarray(mist['uFogView'], float).reshape(4, 4, order='F') @ mirror
    return {**mist, 'uFogView': tuple(view.flatten(order='F'))}


def history_grade(grade, mirror):
    """(nodes, world x range, share) of the colour grade as read at history-axis x: with the history mirrored the
    range and its nodes are mirrored, so the grade stays where it is in the world."""
    if mirror is None:
        return grade
    nodes, (x0, x1), share = grade
    return tuple((1.-position, colour) for position, colour in reversed(nodes)), (-x1, -x0), share


def history_mvp(matrix, mirror):
    """A world clip matrix for history-axis positions (bursts' births)."""
    return matrix if mirror is None else matrix @ mirror


def frame_geometry(packet, *, capacity, now, travel, recipe, size, view, projection, grade, pulse_rim=None,
                   floor_give=None):
    """The frame's shared geometry (``WaveformScene._render_packet``'s): the scroll, the scene's clip matrix, the
    Travel Direction mirror, the ribbons' and the mirrored camera's views and clip matrices, the culled span and the
    ribbons' draw inputs (``draw``: ``RibbonPrimitive.draw``'s keywords in their values form: ``pulse_rim`` = (rim,
    shape) or None, ``floor_give`` = (uFloorGive[, side]) or None). ``grade``: ``colour_grade`` of the frame."""
    from rendering.quick.scene3d.ribbon import ribbon_grade

    width, height = size
    environment, flow = recipe.environment, recipe.flow
    scroll = np.identity(4)
    scroll[0, 3] = flow.head_x - travel
    mvp = (projection @ view).flatten(order='F')
    # Travel Direction: the history (ribbons, sparks, strands, their fields) lives on its own axis, mirrored into
    # the world here (world x = side * axis) and nowhere else. +1 is the identity and multiplies nothing.
    side = -1. if flow.direction < 0. else 1.
    mirror = None if side > 0. else HISTORY_X_MIRROR
    history_view = view if mirror is None else view @ mirror
    ribbon_view = history_view @ scroll
    ribbon_mvp = tuple((projection @ ribbon_view).flatten(order='F'))
    continuation_origin = tuple(np.asarray(packet.world_origin)+scroll[:3, 3])
    transverse = continuation_bounds(packet, scroll[:3, 3], recipe.material.cross_curve)
    main_span = frustum_axial_span(projection@history_view, transverse)
    mirrored = mirror_view(view, 0.)
    reflected_span = frustum_axial_span(projection@(mirrored if mirror is None else mirrored@mirror), transverse)
    span = (min(main_span[0], reflected_span[0]), max(main_span[1], reflected_span[1]))
    draw = dict(view=tuple(ribbon_view.flatten(order='F')), material=recipe.material,
                sweep_axis=(1., 0., 0.), floor=FLOOR_CONTACT,
                age_fade=(now, 0., (capacity - 1)/flow.knot_hz, 0.), continuation=(*span, 2048),
                mist=environment.mist, mist_frame=(scroll[0, 3], 0., 0.),
                grade=ribbon_grade(*history_grade(grade[:3], mirror)),
                pulse_rim=pulse_rim, viewport=(width, height),
                floor_give=None if floor_give is None else (floor_give,) if mirror is None else (floor_give, side))
    reflected_view = (mirrored if mirror is None else mirrored @ mirror) @ scroll
    return SimpleNamespace(scroll=scroll, mvp=mvp, side=side, mirror=mirror, ribbon_view=ribbon_view,
                           ribbon_mvp=ribbon_mvp, continuation_origin=continuation_origin,
                           continuation_count=packet.instances, span=span, draw=draw, mirrored=mirrored,
                           reflected_view=reflected_view,
                           reflected_mvp=tuple((projection @ reflected_view).flatten(order='F')))


def field_receiver_values(recipe, *, origin, count, mirror, grade) -> dict:
    """The world body field's receiver members (``WORLD_FIELD_GLSL``: the floor and the fog medium read the field)."""
    from rendering.quick.scene3d.ribbon import ribbon_grade

    fog = recipe.fog
    first, last, samples = fog.field_span
    step = (last-first)/(samples-1)
    values = {'uFieldOrigin': (*origin, float(count)), 'uFieldSide': 1. if mirror is None else -1.}
    values.update(ribbon_grade(grade[0], grade[1], grade[3]))
    values['uBodySpan'] = (first-step*.5, 1./(last-first+step))
    values['uBodyShape'] = (FLOOR_CONTACT[0]+FLOOR_CONTACT[1], FLOOR_CONTACT[2], recipe.material.cross_curve,
                            fog.clearance)
    return values


def medium_values(recipe, *, now, origin, count, mirror, grade) -> dict:
    """The fog medium's own members (its one block also holds the volume's: ``fog_volume_values``)."""
    fog = recipe.fog
    values = field_receiver_values(recipe, origin=origin, count=count, mirror=mirror, grade=grade)
    values['uAtmosphere'] = (fog.density, fog.height, fog.softness, fog.light)
    values['uAtmosphereMotion'] = (now, fog.drift, fog.noise, fog.noise_scale)
    values['uAtmosphereAmbient'] = tuple(fog.ambient)
    values['uAtmosphereLight'] = (fog.light_ceiling, fog.light_tint)
    return values


def sky_values(fog_uniforms, *, backdrop, reflection, size) -> dict:
    """The sky's members: the volume's receiver uniforms, the backdrop, whether it draws the mirrored sky and its
    target's size (the scene's or the reflection's)."""
    return {**fog_uniforms, 'uBackdrop': tuple(backdrop), 'uSkyReflection': int(reflection),
            'uViewport': (float(size[0]), float(size[1]))}


def floor_values(recipe, *, mvp, eye, view, size, flat=False, lit, give_span=None, field=None, fog_uniforms=None,
                 mist_off=False) -> dict:
    """The floor's members for its full pass (``uSpecMode`` 0 inline, or 2 reading its pre-pass: ``floor_prepass``).
    ``lit``: the fog volume lights it (``field``: ``field_receiver_values``, ``fog_uniforms``: the camera volume's
    receiver uniforms); ``give_span``: the yielding floor's ``uFloorGive`` or None."""
    floor, environment = recipe.floor, recipe.environment
    u = {}
    inverse = np.linalg.inv(np.asarray(mvp, float).reshape(4, 4, order='F'))
    u['uFloorInverseMvp'] = tuple(np.asarray(inverse.flatten(order='F'), np.float32))
    u['uFlat'] = int(flat)
    u['uMvp'] = tuple(np.asarray(mvp, np.float32))
    u['uFogLit'] = int(lit)
    u['uReflectionLook'] = (floor.streak[0], floor.lod[0], floor.lod[1], 0.)
    u['uHot'] = (*floor.hot, floor.albedo_bias)
    u['uPool'] = floor.pool if lit else 0.
    u['uColumn'] = tuple(floor.column)
    u['uReflectionHue'] = floor.hue
    u['uBound'] = (floor.glow_limit, floor.light_reach, floor.light_far)
    if give_span is None:
        u['uFloorGive'] = (0., 0., 1., 1.)
    else:
        u['uFloorGive'] = tuple(give_span)
        u['uFloorGiveLook'] = (floor.give_reach, floor.shading)
    if lit:
        u.update(field)
    u['uStreak'] = (floor.streak_length, floor.streak[1], floor.streak[2], 8.)
    u['uMaterial'] = (floor.contrast, floor.shading, floor.breakup, floor.pool_spread)
    u['uMaterialShape'] = (floor.elongation, floor.relief_bias, floor.column_height)
    u['uViewport'] = tuple(size)
    u['uBackdrop'] = tuple(environment.backdrop)
    u['uAmbient'] = tuple(floor.ambient)
    u['uFloorTint'] = tuple(floor.tint)
    u['uFloor'] = (floor.tile, floor.micro_tile, floor.reflection, floor.f0)
    u['uFloorTone'] = (floor.albedo_gain, *floor.relief)
    u['uRipple'] = tuple(floor.ripple)
    u['uEye'] = tuple(eye)
    u['uForward'] = tuple(-np.asarray(view)[2, :3])
    u['uMist'] = environment.mist['uMist']
    u['uMistShape'] = (0., 0., 0., 0.) if mist_off else environment.mist['uMistShape']
    if lit and not mist_off:  # one integrated medium, sampled to this exact world-floor hit
        u['uFogView'] = fog_uniforms['uFogView']
        u['uFogLens'] = fog_uniforms['uFogLens']
        u['uFogRange'] = fog_uniforms['uFogRange']
    else:
        u['uFogRange'] = FOG_OFF['uFogRange']
    prepass = None if flat else floor_prepass_size(size, floor)
    u['uSpecMode'] = 0 if prepass is None else 2
    return u


def floor_prepass(values, size) -> dict:
    """The floor's pre-pass members: the full pass's with the reflection term alone (``uSpecMode`` 1) at its size."""
    return {**values, 'uSpecMode': 1, 'uViewport': tuple(size)}


__all__ = ["HISTORY_X_MIRROR", "capped", "field_receiver_values", "floor_prepass", "floor_prepass_size",
           "floor_values", "fog_focus", "fog_grid", "frame_geometry", "history_grade", "history_mist", "history_mvp",
           "medium_values", "reflection_size", "sky_values"]
