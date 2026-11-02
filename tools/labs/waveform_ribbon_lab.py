"""Waveform Ribbon scene lab: world-first floor, waveform and distance mist over shared primitives.

The world is authored in world units and viewed through the shared framed camera (``core.settings.framed_camera``)
with a lab-local spec; nothing is placed relative to the camera or the card. ``POSES['mock']`` reproduces the mock's
view for comparison; the other poses navigate the same world. No walls or pillars: the floor disappears into mist
beyond a corridor of clear air. Volumetric clearance and illumination follow the live Lab Plan.

Ribbons are flowing history (Lab Plan section 4A): one ``RibbonRing`` fed by a labelled synthetic head (no music)
whose head and tail sit at fixed world x and fade by age. Two renders per state and pose:

- ``flat``: solid colours, no light, bloom or mist; ribbon envelopes measured against the WR-00 target table.
- ``lit``: ribbon material, wet floor, mist and bloom through the Visualizer-shaped scope.

The floor uses saved generated concrete colour, roughness and smooth wet-surface height with the shared planar reflection
(S3D-5): ribbon light drawn through the mirrored camera, sampled at the floor's own screen position,
streaked and blurred by wet roughness and perturbed by the micro-surface.

    .venv\\Scripts\\python.exe tools/labs/waveform_ribbon_lab.py --output .artifacts/evidence/waveform_ribbon/<new-run>
        [--cards .artifacts/evidence/waveform_ribbon/wr00_reference_projection] [--recipe complete|alternate|range]

Named looks (``RECIPES``) share every program and function; they differ in values only.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field, replace
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rendering.gl_error_policy import disable_per_call_gl_error_checking
# As a script, GL must load under the production error policy; imported (tests) it reuses the caller's GL.
if not disable_per_call_gl_error_checking() and __name__ == '__main__':
    raise RuntimeError('GL imported before benchmark production policy')
from OpenGL import GL as gl
import numpy as np
from PIL import Image, ImageDraw

from core.ribbon_packet import KNOT_ROWS
from core.ribbon_ring import RibbonRing
from core.settings import framed_camera as fc
from rendering.gl_programs.fog_volume import fog_inject_source
from rendering.gl_programs.mist import FOG_OFF, MIST_GLSL, mist_uniforms
from rendering.gl_programs.reflection import PLANAR_REFLECTION_GLSL, mirror_view
from rendering.quick.scene3d.fog_volume import FogMarch, FogVolume
from rendering.quick.scene3d.reflection import PlanarReflection
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.ribbon import (GRADE_STOPS, RibbonMaterial, RibbonPrimitive, RibbonSparks, RibbonStrays,
                                            ribbon_grade)
from rendering.quick.scene3d.target import SceneTarget
from tools.labs.render_target import OffscreenRenderTarget
from tools.labs.waveform_ribbon_targets import ENVELOPE

# Lab-local framed camera on the shared API (no production registration). Orthographic half-extents follow the
# shared rule: the reference lens's tangents at the orbit distance, divided by Scene Scale. At the mock pose that is
# the WR-00 fit: pivot 2 above the floor, 15 degrees down, half-height 12*tan(22.5 deg) = 4.97.
SPEC = fc.FramedCameraSpec(
    prefix='waveform_ribbon_', pivot=(0., 2., 0.), orbit_distance=12., pitch_base_degrees=-15.,
    pitch_span_degrees=60., yaw_span=math.pi, tilt_range=(-.5, .5), eye_center=(0., 8., 0.), eye_half=(60., 8., 60.),
    clearance=.4, offset_scale=(60., 8., 60.), travel_speed=4.)
ORTHO_REFERENCE_FOV = 45.


@dataclass(frozen=True)
class Pose:
    turn: float = 0.
    tilt: float = 0.
    scale: float = 1.
    pan_x: float = 0.
    pan_y: float = 0.
    projection: str = 'Orthographic'
    fov: float = 45.


POSES = {'mock': Pose(), 'turned': Pose(turn=.14), 'raised': Pose(tilt=-.12), 'dolly': Pose(scale=1.6, pan_x=.12),
         'perspective': Pose(projection='Perspective', fov=40.)}


@dataclass(frozen=True)
class Environment:
    backdrop: tuple = (.05, .055, .07)  # the cheap floor mist: barely tinted, dark
    # Floor mist (analytic, cheap): clear around the waveform, thickening toward the camera-side floor edges, the
    # extreme sides and most of all into the distance, where it is thick dark grey and hides the horizon.
    mist: dict = field(default_factory=lambda: mist_uniforms(centre_xz=(0., -1.), radii_xz=(9., 7.5), falloff=1.6,
                                    floor_thickening=1., thickening_height=1.5, low_glow=0.))


@dataclass(frozen=True)
class Fog:
    """S3D-7 volume mist shaped by the waveform: thick everywhere behind the sheets except a clear band that hugs their
    exact lower/upper envelope along x (reduced per frame from the admitted history). The band's rim glows in the
    colour of the nearest sheet edge and darkens into the mass; a detail march adds the billows."""
    density: float = 1.6            # extinction per world unit inside the mist
    margin: float = .1              # clear air beyond the envelope (world units)
    tube: float = .3                # true 3D clearance around every sheet (world units)
    clearance: tuple = (.3, .25)    # push of the whole field from the envelope; the mist never enters within
    ends: float = 6.                # the mist comes this far forward where the sheets fade (world units)
    # |world x| where the clear band and the sheets' clearance start to close, and where they are closed: beyond the
    # framed view the ribbons run into mist (the off-screen edge mist), so no view along them sees a clear corridor.
    sides: tuple = (8., 13.)
    floor: tuple = (0., 5.5, 2.5)   # floor bank height, forward reach at the sides, |x| where the sides begin
    interior: tuple = (.25, .22, 1.5)   # unlit body lumps: floor, frequency; rim fall per unit of billow push
    floor_light: tuple = (0., 2., .08)  # floor mist light share, its reach from the sheets; wall-behind light
    softness: float = 1.5           # depth over which coarse coverage rises: the detail march erodes within it
    noise_scale: float = .35        # lobe frequency of the band's edge (per world unit)
    noise: float = 1.8              # lobe displacement of the edge (world units)
    start_z: float = -1.7           # the mist begins behind this world z (just behind the sheets)
    band_depth: float = 1.          # the clear band reaches this far behind start_z; the far wall closes it
    sheets_z: tuple = (-1.7, 1.7)   # depth range of the sheets, for the rim light's distance
    ambient: tuple = (.08, .09, .15)  # radiance of unlit mist: the distant cloud bodies, dark grey not black
    rim: float = 120.               # rim light gain on the nearest sheet edge colour
    reach: float = .35              # e-folding distance of the rim light from the envelope (world units)
    light_decay: float = 2.         # its extinction per world unit of depth into the mist
    haze: float = 0.                # faint haze in the clear band behind the sheets (never eroded)
    envelope_range: tuple = (-40., 40., 640)  # world x span and samples of the envelope reduction
    envelope_smoothing: float = .25 # Gaussian along x (world units)
    edge_evening: float = 4.        # world-x width over which the fringe's brightness is evened
    envelope_width: float = .5      # share of a sheet's half-width counted as its vertical extent (twisted sheets)
    depth_range: tuple = (3., 90.)
    cell: int = 16                  # viewport pixels per coarse cell (light and coverage only)
    slices: int = 64
    reflection_cell: int = 24
    reflection_slices: int = 32
    # Detail march (per pixel at a reduced scale): bound on adaptive steps and their lengths in and out of the mist,
    # erosion by the tiling noise and its frequency (per world unit), self-shadow reach (world) and strength, and
    # the in-scatter's share of bloom.
    march_scale: float = .5
    reflection_march_scale: float = .25
    # Height caps (pixels) of the reduced-resolution targets: they leave the 718-pixel lab untouched and keep 1440p
    # and 4K at the approved look's detail per screen fraction instead of quadrupling the cost.
    march_max_height: int = 540
    reflection_march_max_height: int = 270
    # Shape bake box (world min, max) and cell size: the march reads the shape from it; outside, exact.
    bake_box: tuple = ((-30., 0., -12.), (30., 12., 4.))
    bake_cell: float = .2
    steps: int = 96
    step: tuple = (.15, 1.)
    erosion: float = .75
    detail_frequency: float = .8
    shadow: tuple = (.6, 4.)
    shadow_floor: float = .3
    crackle: tuple = (2.4, .08, 4., 4.)  # silhouette line: brightness, filament frequency (per px), sharpness, width
    crackle_glow: float = 3.      # the line's bloom share
    fringe_smoothing: float = 1.  # wider existing filter taps; preserve billows without march-jitter sand
    edge_glow: float = 3.          # extra light on thin eroded wisps (curl rims)
    glow: float = .3


@dataclass(frozen=True)
class Floor:
    """Smooth wet concrete: dark base lit by the mist's light field, and one crisp reflection broken by the surface.

    At grazing angles a micro-surface tilt toward or away from the viewer moves the reflection a long way vertically
    and a sideways tilt hardly at all: the wet-floor columns come from that offset, not from blurring a mirror.
    Reflections stay crisp at the contact and soften with the height of what they reflect (contact hardening)."""
    half_span: float = 100.
    depth_bounds: tuple = (-80., 60.)
    albedo: str = 'assets/textures/waveform_floor/concrete_albedo.png'
    roughness: str = 'assets/textures/waveform_floor/concrete_roughness.png'
    height: str = 'assets/textures/waveform_floor/wet_surface_height.png'
    tile: float = 12.               # concrete colour and broad relief patch (world units)
    micro_tile: float = 1.6         # micro relief patch (world units); the same smooth height data, finer
    albedo_gain: float = 1.        # wet concrete is dark
    albedo_bias: float = 2.5        # mip bias of the colour scan (grazing aliasing)
    ambient: tuple = (.03, .035, .05)
    diffuse: float = 0.             # gain on the mist's coarse light field (off: its depth slices band the floor)
    reflection: float = 6.         # reflection strength before Fresnel (look gain)
    f0: float = .02                 # water film
    relief: tuple = (.03, .4)       # height amplitude of the broad and micro relief (world units)
    # Reflection offset per unit slope (uv): broad wobble, micro offset across and along the view.
    ripple: tuple = (.25, 0., 0.)
    # Micro facets are many per pixel at this grazing view: their average is a vertical streak (the receiver's
    # roughness footprint), never per-pixel offsets, which aliased into horizontal scanlines. Streak half-length
    # (uv) and the roughness range across the surface (from the broad relief's slope).
    streak: tuple = (.5, .8, 1.)
    lod: tuple = (1., 1.)           # reflection mip (half-resolution target: already soft)
    contact: tuple = (.002, 6., 6.)  # spread (uv) per unit of reflected height; along/across; probe mip
    resolution: float = .5          # reflection target scale
    resolution_max_height: int = 360  # reflection target height cap (pixels)
    specular_max_height: int = 1080  # the reflection term is evaluated at most this tall, then read back
    blur: float = 0.               # horizontal Gaussian across each column (receiver pixels)
    # Column fade toward the camera and its far level; a sparkle threshold above 0 adds wet-film grain (rejected:
    # it read as the mottled wet/dry floor).
    column: tuple = (6., .6, 0.)
    pool: tuple = (14., 1., 1.5, 1.5)  # waveform light on the concrete: gain, height, depth falloffs behind/front
    hot: tuple = (3., .7, 1.5)       # full strength at this multiple of the mean reflected light; wet-film breakup; power
    mist_reflection: float = .35   # share of the mist the floor mirrors: the mock's floor mirrors the hot light


@dataclass(frozen=True)
class Flow:  # Lab Plan section 4A: history enters at the head (world +x) and drifts toward the tail
    speed: float = 1.6
    head_hz: float = .33
    phase: float = 4.2             # explicit synthetic start phase, not a second clock
    phase_swell: float = .35       # broad smooth compression/expansion of neighbouring folds
    amplitude_swell: float = .3
    depth_sway: float = 1.
    knot_hz: float = 6.
    shape_tau: float = .45          # per smoothing stage of history-carried shape controls
    head_x: float = 34.
    fade_in: float = 2.5            # seconds of age over which the head fades in
    fade_out: float = 5.            # seconds of age over which the tail fades out


PALETTE = (((0., .52, 1.), (0., .22, 1.)),    # cyan -> electric blue
           ((.03, .08, 1.), (.24, .025, 1.)),  # blue -> violet
           ((.38, .006, 1.), (1., .012, .62))) # violet -> magenta
STATES = {'low': dict(react=0.), 'high': dict(react=1.)}  # labelled synthetic reactivity, not music
SOURCES = ('loudness', 'bass')  # the synthetic energy sources a tuner target can follow (see synthetic_sources)


def hue_between(a, b) -> tuple:
    """The colour halfway between two in hue (the short way round), at their mean saturation and value, so a
    cyan -> magenta gradient passes through blue, not lavender."""
    import colorsys
    (h0, s0, v0), (h1, s1, v1) = colorsys.rgb_to_hsv(*a), colorsys.rgb_to_hsv(*b)
    if abs(h1 - h0) > .5:
        h1 += -1. if h1 > h0 else 1.
    return colorsys.hsv_to_rgb(((h0 + h1)/2) % 1., (s0 + s1)/2, (v0 + v1)/2)


@dataclass(frozen=True)
class Shaping:
    """Shape and reactivity tuner (Lab Plan section 0, the WR-08 tuner control's model): which energy shapes which
    ribbon property, and how far. A tuner, not a shape builder: the head oscillator (musical history) still draws the
    waves; every target is a smooth function of band-limited history (two smoothing stages of at least
    ``Flow.shape_tau``), so no setting can make a sharp or jagged ribbon."""
    # target -> (quiet, loud): the range its source's 0..1 level sweeps.
    ranges: dict = field(default_factory=lambda: dict(
        width=(.40, .78), width_swell=(.08, .28), twist=(.85, 1.85), emission=(.7, .85), spread=(.32, 1.25),
        amplitude=(.5, 1.2), lift=(-.35, .2), sparkle=(.18, .85), deformation=(.15, .3), arc=(0., 0.),
        tint=(0., 0.)))
    # target -> source (SOURCES); targets not named follow loudness.
    drive: dict = field(default_factory=dict)
    # The bass arc: wave height grows by up to ``arc`` (a target above) where the bass source swells, so a bass
    # passage draws one taller arc that flows along the history (the preset-range board's dominant peak).
    # Synthetic bass timing: (every, length, offset) seconds; a raised cosine, the length about one wave.
    bass: tuple = (12., 3., 0.)
    # ``tint`` is how far each knot takes its ribbon's loud colours (Recipe.ribbon_colours): colour reactivity that
    # flows along the history like the shape does.
    # Per-ribbon character (amplitude, width, wave frequency, phase, light): identical sheets on even phases braid
    # into a regular lattice and sum to white; the mock's sheets differ and cross irregularly.
    characters: tuple = ((1., 1., 1., 0., 1.), (.85, 1.1, .96, 1.1, 1.5), (.72, .75, 1.07, .55, .65))


# A sheet that reaches the floor deforms along it (rule, not a tuner setting): world floor height, gap, softness.
FLOOR_CONTACT = (0., .03, .15)


def synthetic_sources(state: str, t: float, shaping: Shaping) -> dict:
    """The labelled states' synthetic energy (0..1), not music: loudness holds the state's reactivity; bass swells
    for ``length`` seconds once every ``every`` seconds (a raised cosine), scaled by the reactivity."""
    react = STATES[state]['react']
    every, length, offset = shaping.bass
    u = ((t - offset) % every)/length
    return dict(loudness=react, bass=react*(.5 - .5*math.cos(2*math.pi*u)) if u < 1. else 0.)


@dataclass(frozen=True)
class Recipe:
    environment: Environment = field(default_factory=Environment)
    fog: Fog | None = field(default_factory=Fog)
    floor: Floor = field(default_factory=Floor)
    flow: Flow = field(default_factory=Flow)
    shaping: Shaping = field(default_factory=Shaping)
    # Each ribbon's own colours, (centre, edge) per ribbon: quiet (the ribbon's base) and loud (taken per knot by
    # the tuner's tint target). A look coloured by ribbon (bass, mid, high) rather than by the world grade sets the
    # grade's sheet share near 0.
    ribbon_colours: dict = field(default_factory=lambda: dict(low=PALETTE, high=PALETTE))
    # Mock-directed look (WR-04): saturated darker body, thin near-white irregular strands and rims, visible glints.
    material: RibbonMaterial = field(default_factory=lambda: RibbonMaterial(
        strands=40., strand_half_width=.018, strand_light=1.5, strand_white=.04, strand_jitter=.35, strand_warp=.18,
        strand_variation=.9, cross_curve=.35, warp_frequency=.2, rim_light=2.9, rim_white=.08, rim_half_width=.009,
        fill_light=.12, fill_centre=.3, rim_glow_light=.35,
        rim_glow_width=.04, body_alpha=.025, body_tint=.4, glint_density=1.4, glint_chance=.12, glint_light=3.,
        glint_radius=.25, glint_min_pixels=.8))
    sparks: RibbonSparks | None = field(default_factory=lambda: RibbonSparks(per_knot=16, lifetime=4.5, drift=1.2, rise=.4,
                                                                       smallest=1.6, largest=5., light=16., white=.25))
    strays: RibbonStrays | None = None  # free liquid strands peeling off the sheets (the alternate board)
    # World colour grade (preset look): the mock's cyan left, blue-violet middle, magenta right across the view,
    # taking this share of each ribbon's own colour so identities still read. History tint carries reactivity.
    # (left, mid, right, world x range, ribbon share, mist share): mixing a magenta sheet far toward cyan passes
    # through grey, so the sheets take a small share and keep their identities; the mist takes most of it.
    # Preset colour data: a low-reactivity and a high-reactivity colour pair (left, right across the view). The
    # middle stop is derived by hue, so cyan -> magenta passes through blue, not lavender. Reactivity blends the
    # pairs (the lab's synthetic states are react 0 and 1). Settings (WR-08) edits these as gradient nodes.
    # Nodes are (position 0..1 across grade_range, rgb): the WR-08 gradient editor's circles. Up to six positions
    # across both pairs together; reactivity blends the two gradients position by position.
    palette: dict = field(default_factory=lambda: dict(
        low=((0., (0., .85, 1.)), (.5, hue_between((0., .85, 1.), (1., .1, .85))), (1., (1., .1, .85))),
        high=((0., (0., .85, 1.)), (.5, hue_between((0., .85, 1.), (1., .1, .85))), (1., (1., .1, .85)))))
    # World x range of the pair, the sheets' share (small: identities hold), the mist's share.
    grade_range: tuple = (-6., 6.)
    grade_share: tuple = (.3, .75)
    bloom: float = .14
    exposure: float = 1.


# Second look: the preset-range board (Lab Plan section 0). The same lab, programs and functions with other values
# only: a tight braided bundle, more and smaller waves, one bass arc that towers over the rest when loud, and a
# gradient that runs on to orange at the right in high react. The sheets take most of the gradient, so the whole
# bundle shares one colour at each x as on the board. Mist stays (core to every look).
PRESET_RANGE = Recipe(
    flow=Flow(head_hz=.42, phase_swell=.2, amplitude_swell=.1, depth_sway=.5),
    shaping=Shaping(
        ranges=dict(width=(.16, .5), width_swell=(.04, .16), twist=(.9, 1.6), emission=(.7, .9), spread=(.12, .45),
                    amplitude=(.3, .8), lift=(.35, .55), sparkle=(.18, .9), deformation=(.08, .15), arc=(.15, 1.8),
                    tint=(0., 0.)),
        bass=(12., 2.4, 8.8),
        characters=((1., 1., 1., 0., 1.), (.92, .9, 1., .35, 1.2), (.85, .8, 1., .7, .8))),
    material=replace(Recipe().material, strand_white=0., rim_white=.03),
    palette=dict(low=((0., (0., .9, 1.)), (.3, (.1, .3, 1.)), (.55, (.55, .12, 1.)), (.8, (1., .15, .85)),
                      (1., (1., .15, .85))),
                 high=((0., (0., .9, 1.)), (.3, (.15, .25, 1.)), (.55, (1., .1, .8)), (.8, (1., .22, .03)),
                       (1., (1., .22, .03)))),
    grade_range=(-5.5, 5.5), grade_share=(.8, .85))
# Second goal (operator, 1 November): the package's alternate board. Three broad ribbons, one per band (bass, mid,
# high), coloured by ribbon rather than by the world grade: blue, teal and lavender when quiet; magenta, orange and
# blue-violet when loud, taken knot by knot so the colour flows with the history. Long sweeping waves with large
# depth sway, dense bright filaments, many sparks when loud. Mist stays.
ALTERNATE = Recipe(
    flow=Flow(head_hz=.2, phase_swell=.3, amplitude_swell=.3, depth_sway=2.),
    shaping=Shaping(
        ranges=dict(width=(.95, .9), width_swell=(.1, .3), twist=(.9, 1.7), emission=(.75, .75), spread=(1.6, 2.4),
                    amplitude=(1.2, 1.5), lift=(.3, .6), sparkle=(.25, 1.), deformation=(.15, .3), arc=(0., 0.),
                    tint=(0., .9)),
        characters=((1., 1., 1., 0., 1.), (.8, 1.2, .9, 1.6, 1.3), (.7, .85, 1.15, 2.8, .9))),
    # Colours are linear light: orange is about (1, .2, .03); (1, .4, .05) displays as gold.
    ribbon_colours=dict(low=(((.15, .35, 1.), (.35, .25, 1.)), ((0., .7, .9), (.1, .4, 1.)), ((.5, .2, 1.), (.4, .15, 1.))),
                        high=(((1., .1, .7), (.6, .05, 1.)), ((1., .2, .03), (1., .13, .06)), ((.15, .2, 1.), (.45, .1, 1.)))),
    # Loud ribbons stay narrower and further apart than quiet ones: broad overlapping sheets summed to pastel pink.
    # Luminous silk: a glowing body, local bloom on the sheets only (glow), white-hot cores on the brightest strands.
    material=replace(Recipe().material, strands=48., strand_half_width=.022, strand_light=2.4, strand_white=0.,
                     rim_white=.02, fill_light=.1, rim_glow_light=.45, body_tint=.85, glint_density=3.,
                     glint_chance=.3, glint_light=5., glow=2., hot=.3),
    # Sparks hug the ribbons (little drift or rise), mostly fine with a few large.
    sparks=replace(Recipe().sparks, drift=1.1, rise=.15, light=40., smallest=1.2, largest=8., lifetime=6., white=.04),
    palette=dict(low=((0., (.2, .6, 1.)), (1., (.55, .35, 1.))), high=((0., (1., .3, .85)), (1., (1., .22, .05)))),
    # Free strands splash off the sheets and curl away, droplets toward their tips (short, far-reaching).
    strays=RibbonStrays(per_knot=4, length=6., reach=1.6, chance=.6, width=1.6, light=3.2, beads=4., peel_time=1.5,
                        halo=.5, glow=2.2),
    # More tint for any colour pair: less highlight compression (exposure), less white-hot, more body tint.
    grade_share=(0., .35), bloom=.12, exposure=.85)
RECIPES = {'complete': Recipe(), 'alternate': ALTERNATE, 'range': PRESET_RANGE}


FLOOR_VERTEX = """#version 460 core
layout(location=0) in vec3 aPosition;
uniform mat4 uMvp;
out vec3 vWorldPos;
void main() { vWorldPos=aPosition; gl_Position=uMvp*vec4(aPosition,1.0); }
"""
ENVELOPE_RIBBONS = 3   # sheets with their own 3D rows in the envelope table (true 3D clearance)
ENVELOPE_ROWS_GLSL = (f"const float ENV_ROWS={3 + ENVELOPE_RIBBONS}.0;\n"
                      f"const int ENV_RIBBONS={ENVELOPE_RIBBONS};\n")

FLOOR_FRAGMENT = """#version 460 core
in vec3 vWorldPos;
uniform sampler2D uAlbedo;
uniform sampler2D uSlope;      // height slope per uv unit (rg), from the smooth wet-surface height map
uniform sampler3D uFogLight;   // the mist's coarse medium: its radiance is the ribbon light field
uniform int uFlat;
uniform int uFogLit;
uniform vec2 uViewport;
uniform vec3 uBackdrop;
uniform vec3 uAmbient;
uniform vec4 uFloor;        // tile, micro tile, reflection gain, f0
uniform vec4 uFloorTone;    // albedo gain, diffuse gain, broad relief amplitude, micro relief amplitude
uniform vec3 uRipple;       // reflection offset per unit slope: broad, micro across, micro along
uniform vec4 uStreak;       // unused, roughness min/max, broad-slope gain to roughness
uniform vec4 uHot;          // reflected luminance at full strength; wet-film breakup share; suppression power; albedo mip bias
uniform sampler2D uEnvelope;  // the waveform's envelope table (lower/upper, colours), shared with the mist
uniform vec2 uEnvelopeSpan;
uniform vec4 uPool;         // gain, height falloff, depth falloff behind, depth falloff toward the camera
uniform float uPoolZ;       // the sheets' depth (world z)
uniform vec3 uColumn;       // fade length toward the camera, far sparkle strength, sparkle threshold
uniform int uSpecMode;      // reflection term: 0 inline, 1 write it alone (pre-pass), 2 read it from uSpecular
uniform sampler2D uSpecular;
uniform vec3 uEye;
uniform vec3 uForward;
uniform int uOrthographic;
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
""" + ENVELOPE_ROWS_GLSL + MIST_GLSL + PLANAR_REFLECTION_GLSL + """
// World-space slope of one height sample set at two incommensurate orientations (no visible tile lattice).
vec2 slopeAt(vec2 xz, float tile) {
    mat2 turn=mat2(0.6,-0.8,0.8,0.6);
    vec2 uv=xz/tile;
    vec2 near=texture(uSlope,uv).rg;
    vec2 far=transpose(turn)*texture(uSlope,turn*uv*1.37+vec2(.31,.47)).rg*1.37;
    return (0.6*near+0.4*far)/tile;
}
void main() {
    if(uFlat==1) { FragColor=vec4(vec3(0.25),1.0); Emission=vec4(0.0); return; }
    mat2 turn=mat2(0.6,-0.8,0.8,0.6);
    vec2 uv=vWorldPos.xz/uFloor.x;
    // Mip-biased and toned down: at this grazing angle the colour scan aliases into horizontal bands once lit.
    vec3 albedo=mix(texture(uAlbedo,uv,uHot.w).rgb,texture(uAlbedo,turn*uv*1.37+vec2(.31,.47),uHot.w).rgb,.4);
    albedo=mix(vec3(dot(textureLod(uAlbedo,vec2(.5),20.0).rgb,vec3(.333))),albedo,0.5)*uFloorTone.x;
    vec3 specular;
    if(uSpecMode==2) {
        specular=texture(uSpecular,gl_FragCoord.xy/uViewport).rgb;
    } else {
    vec2 broad=slopeAt(vWorldPos.xz,uFloor.x)*uFloorTone.z;
    vec2 micro=slopeAt(vWorldPos.xz,uFloor.y)*uFloorTone.w;
    // Offsets follow the viewed ground axes, so a turned camera streaks along its own view.
    vec3 groundForward=normalize(vec3(uForward.x,0.0,uForward.z));
    vec3 groundRight=cross(groundForward,vec3(0,1,0));
    vec2 axes=vec2(dot(vec3(broad.x,0,broad.y),groundRight),dot(vec3(broad.x,0,broad.y),groundForward));
    vec2 fine=vec2(dot(vec3(micro.x,0,micro.y),groundRight),dot(vec3(micro.x,0,micro.y),groundForward));
    vec2 offset=axes*uRipple.x+fine*vec2(uRipple.y,uRipple.z);
    float roughness=mix(uStreak.y,uStreak.z,clamp(length(broad)*uStreak.w,0.0,1.0));
    vec3 reflected=planarReflection(gl_FragCoord.xy/uViewport,offset,roughness);
    vec3 view=uOrthographic==1?normalize(uForward):normalize(vWorldPos-uEye);
    float cosine=clamp(abs(view.y),0.0,1.0);
    float fresnel=uFloor.w+(1.0-uFloor.w)*pow(1.0-cosine,5.0);
    // A rough wet floor shows its hot light, not a dim copy of everything: reflected light below uHot.x falls
    // away quadratically, so columns stand over dark concrete. The wet film breaks them up gently (uHot.y).
    // Relative to the scene's own reflected light (the reflection's coarsest mip): quiet and loud states both keep
    // columns over dark concrete. A fixed threshold blacked out the quiet floor and washed the loud one.
    float hot=dot(reflected,vec3(0.2126,0.7152,0.0722));
    float scene=dot(textureLod(uReflection,vec2(0.5),20.0).rgb,vec3(0.2126,0.7152,0.0722));
    reflected*=pow(clamp(hot/max(uHot.x*scene,1e-4),0.0,1.0),uHot.z);
    float film=texture(uAlbedo,uv*2.3+vec2(.17,.61)).r/max(texture(uAlbedo,uv*2.3+vec2(.17,.61),6.0).r,1e-3);
    reflected*=mix(1.0,smoothstep(0.6,1.25,film),uHot.y);
    // Column shaping: brightest at the contact under the sheets, fading toward the camera, where only the
    // wet film's brighter grains still catch it (sparkle).
    float toward=max(vWorldPos.z-uPoolZ,0.0);
    float near=exp(-toward/max(uColumn.x,1e-3));
    float grain=smoothstep(uColumn.z,1.0,film);
    reflected*=mix(grain*uColumn.y,1.0,near);
    specular=reflected*fresnel*uFloor.z;
    }
    if(uSpecMode==1) { FragColor=vec4(specular,1.0); Emission=vec4(0.0); return; }
    vec3 field=uFogLit==1?texture(uFogLight,clamp(fogCoordinate(vWorldPos+vec3(0,0.05,0))/vec3(1,1,uFogRange.z),
                                                   vec3(0.0),vec3(1.0))).rgb:vec3(0.0);
    // Coloured pools under the waveform: its lower edge lights the concrete beneath it, falling off with the edge's
    // height and with depth away from the sheets (further toward the camera), smoothed along x.
    vec3 pool=vec3(0.0);
    if(uPool.x>0.0) {
        float u=(vWorldPos.x-uEnvelopeSpan.x)*uEnvelopeSpan.y;
        float du=0.6*uEnvelopeSpan.y;
        for(int i=-2;i<=2;i++) {
            vec2 at=vec2(u+float(i)*du,0.0);
            float lower=texture(uEnvelope,at+vec2(0,0.5/ENV_ROWS)).x;
            vec3 tone=texture(uEnvelope,at+vec2(0,2.5/ENV_ROWS)).rgb;
            pool+=tone*exp(-max(lower,0.0)/uPool.y)*(1.0-abs(float(i))*0.3);
        }
        float dz=vWorldPos.z-uPoolZ;
        pool*=uPool.x*0.25*exp(-max(dz,0.0)/uPool.w)*exp(-max(-dz,0.0)/uPool.z);
    }
    vec3 colour=albedo*(uAmbient+field*uFloorTone.y+pool)+specular;
    float clear=mistTransmittance(vWorldPos);
    colour=mix(mistColour(uBackdrop,vWorldPos),colour,clear);
    FragColor=vec4(colour,1.0);
    Emission=vec4(specular*clear,dot(specular*clear,vec3(0.2126,0.7152,0.0722)));
}
"""
FLAT = {'ribbon': (1., 0., 1.)}

# The lab's mist medium for the S3D-7 volume: the clear band follows the waveform's exact envelope (lower and upper
# sheet bounds along world x, with the colours of the sheets that define them), reduced per frame from the same
# admitted history the ribbons draw. Static billows anchored in the world; nothing below the floor. No clock and
# no second ribbon path.
FOG_SHAPE_GLSL = ENVELOPE_ROWS_GLSL + """
uniform sampler2D uEnvelope;  // rows: (lower, upper, presence), upper edge colour, lower edge colour
uniform vec2 uEnvelopeSpan;   // world x at u=0, 1/(world span)
uniform vec4 uFogForm;      // density, margin, edge softness, billow frequency
uniform vec4 uFogShape;       // start z, band depth, billow displacement, light decay
uniform float uFogTube;       // true 3D clearance around every sheet (world units)
uniform vec2 uFogClearance;   // push of the whole field from the envelope; distance the mist never enters
uniform vec2 uFogSlope;       // the camera's view direction: x and y change per unit z (band projection)
uniform float uFogEnds;       // how far the mist comes forward where the sheets fade (world units)
uniform vec2 uFogSides;       // |world x| where the clear room starts to close, and where the side wall stands
uniform vec3 uFogFloor;       // floor bank height, forward reach at the sides, |x| where the sides begin
uniform vec3 uFogInterior;   // lump floor (0..1), lump frequency, rim fall per unit of push
uniform vec3 uFogFloorLight;  // floor mist light share, its reach from the sheets, light of the wall behind them
float fogHash(vec3 p) { p=fract(p*0.3183099+0.1); p*=17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
float fogNoise(vec3 x) {
    vec3 i=floor(x), f=fract(x);
    f=f*f*(3.0-2.0*f);
    return mix(mix(mix(fogHash(i),fogHash(i+vec3(1,0,0)),f.x),mix(fogHash(i+vec3(0,1,0)),fogHash(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(fogHash(i+vec3(0,0,1)),fogHash(i+vec3(1,0,1)),f.x),mix(fogHash(i+vec3(0,1,1)),fogHash(i+vec3(1,1,1)),f.x),f.y),f.z);
}
float fogBillow(vec3 p) {
    float sum=0.0, amplitude=0.5;
    for(int i=0;i<3;i++) { sum+=amplitude*fogNoise(p); p=p*2.03+vec3(1.7,9.2,3.1); amplitude*=0.5; }
    return sum/0.875;
}
// True 3D distance to the nearest sheet (a tube of its half-width around its centreline), sampled at a few x
// offsets so steep stretches are not under-measured. Every view angle sees the mist keep this clearance.
float fogSheetDistance(vec3 world) {
    float d=1e3;
    for(int r=0;r<ENV_RIBBONS;r++) {
        float v=(3.5+float(r))/ENV_ROWS;
        for(int k=-2;k<=2;k++) {
            float xo=float(k)*0.35;
            vec4 s=texture(uEnvelope,vec2((world.x+xo-uEnvelopeSpan.x)*uEnvelopeSpan.y,v));
            if(s.w<0.02) continue;
            d=min(d,length(vec3(xo,world.y-s.x,world.z-s.y))-s.z);
        }
    }
    return d;
}
// Depth into the mist (world units): behind the start plane, and outside the clear band around the waveform's
// envelope unless beyond the band's depth. Billows displace the band's edge.
float fogInside(vec3 world, out vec4 band, out float above, out float below) {
    // Projected along the camera's view direction onto z = 0 (see waveform_envelope): the band follows the
    // waveform's outline as this camera sees it, at any yaw or pitch.
    float px=world.x-uFogSlope.x*world.z;
    band=texture(uEnvelope,vec2((px-uEnvelopeSpan.x)*uEnvelopeSpan.y,0.5/ENV_ROWS));
    // The waveform repels the mist: the whole field (shape and light) is pushed out from the envelope by the
    // first clearance; billow tips that still come closer than the second are cut, so the cut face is lit.
    float y=world.y-uFogSlope.y*world.z;
    float raw=max(y-band.y,band.x-y);
    // Only the mist above is pushed up: pushing the lower mist down squashed it into a flat lit slab on the floor.
    above=y-band.y-uFogClearance.x; below=band.x-y;
    // Billows shape the mist freely, but the waveform repels it: nothing within the clearance of the sheets
    // (measured from the envelope, which counts part of each sheet's width) survives.
    float outside=min(max(above,below)-uFogForm.y+uFogShape.z*(fogBillow(world*uFogForm.w)-0.5),
                      raw-uFogClearance.y);
    // Where the sheets fade out (head, tail) the mist comes forward around them, so they blend into it in wide
    // views; elsewhere it begins just behind the sheets.
    float front=uFogShape.x+(1.0-band.z)*uFogEnds;
    float behind=front-world.z+uFogShape.z*(fogBillow(world.zyx*uFogForm.w*0.8+vec3(5.3))-0.5)*1.5;
    float field=min(behind,max(outside,behind-uFogShape.y));
    // Side walls beyond the framed view, at every depth: views along the ribbons see them run into mist instead of
    // a clear slab to the far floor and the sky. Billows break the wall's face.
    float sideWall=abs(world.x)-uFogSides.y+uFogShape.z*(fogBillow(world.zyx*uFogForm.w*0.7+vec3(2.9))-0.5)*1.5;
    field=max(field,sideWall);
    // Under the waveform (where sheets are present) the reactive mist is absent: the floor takes the cheap analytic
    // mist. Isolated eroded lumps survived there and read as stray puffs at the contact line. Only near the sheets:
    // beyond the band's depth the distant wall returns, or high sheets left the sky down to the horizon unfilled
    // (black) under them.
    field=below>0.0?mix(field,-1.0,smoothstep(0.0,0.3,below)*band.z
                         *(1.0-smoothstep(uFogShape.y-2.0,uFogShape.y,behind))):field;
    // Floor mist: low billowed banks on the floor, reaching toward the camera at the sides (the mock's lower
    // corners), thin under the sheets and never within their clearance.
    float side=smoothstep(uFogFloor.z,uFogFloor.z+3.0,abs(world.x));
    // A rounded mound (height over its forward reach, an ellipse in y/z), so banks never show a flat top or a
    // vertical face where a height limit meets a depth limit; billows break its surface.
    float height=uFogFloor.x*(0.2+1.2*side);
    float reach=max(side*uFogFloor.y,1e-3);
    float mound=height*(1.0-length(vec2(world.y/max(height,1e-3),max(world.z-uFogShape.x,0.0)/reach)))
                +uFogShape.z*0.9*(fogBillow(world*uFogForm.w*1.3+vec3(2.1))-0.5);
    // Banks off: no mound at all (its billow term alone would float noise puffs anywhere in the world).
    float floorMist=uFogFloor.x>0.0?min(mound,raw-uFogClearance.y):-1e3;
    // The waveform truly repels the mist in 3D: nothing within the tube clearance of any sheet, from any angle.
    return world.y<0.0?-1.0:min(max(field,floorMist),fogSheetDistance(world)-uFogTube);
}
"""

# The march's fine coverage: the same shape per sample, so the band's edge never stair-steps at the coarse cells.
FOG_COVERAGE_GLSL = FOG_SHAPE_GLSL + """
// The march asks for coverage and then the light direction at the same sample: the shape is evaluated once and its
// side (above/below the band) remembered for the direction (the shape and its noise dominate the march's cost).
vec3 fogLastWorld=vec3(1e30);
float fogLastSide=0.0;
uniform sampler3D uShapeBake;  // per-frame bake of the shape: inside-distance (r), side above/below the band (g)
uniform vec3 uBakeMin;
uniform vec3 uBakeSize;
uniform int uBaked;
float fogCoverage(vec3 world, float coarse) {
    vec3 t=(world-uBakeMin)/uBakeSize;
    float inside;
    if(uBaked==1 && all(greaterThanEqual(t,vec3(0.0))) && all(lessThanEqual(t,vec3(1.0)))) {
        vec2 baked=texture(uShapeBake,t).rg;
        inside=baked.r;
        fogLastSide=baked.g;
    } else {
        vec4 band; float above, below;
        inside=fogInside(world,band,above,below);
        fogLastSide=above>0.0?1.0:below>0.0?-1.0:0.0;
    }
    fogLastWorld=world;
    return smoothstep(0.0,uFogForm.z,inside);
}
// Each lobe is lit from the waveform: mist above the band from below, mist below it from above, the far wall from
// the front. Shading toward clearer air pointed at the camera and left the lobes flat.
vec3 fogLightDirection(vec3 world) {
    float side=fogLastSide;
    if(world!=fogLastWorld) {
        vec4 band; float above, below;
        fogInside(world,band,above,below);
        side=above>0.0?1.0:below>0.0?-1.0:0.0;
    }
    return normalize(side>0.5?vec3(0.0,-1.0,0.35):side<-0.5?vec3(0.0,1.0,0.35):vec3(0.0,0.0,1.0));
}
"""

# Per-frame shape bake: the march samples the shape many times per pixel; evaluating it once per cell of a world
# grid (trilinear in the march) is several times cheaper. The coarse medium keeps the exact shape.
SHAPE_BAKE_COMPUTE = """#version 460 core
layout(local_size_x=8,local_size_y=8,local_size_z=4) in;
layout(rg16f,binding=0) uniform writeonly image3D uShapeOut;
uniform vec3 uBakeMin;
uniform vec3 uBakeCell;
""" + FOG_SHAPE_GLSL + """
void main() {
    ivec3 cell=ivec3(gl_GlobalInvocationID);
    if(any(greaterThanEqual(cell,imageSize(uShapeOut)))) return;
    vec3 world=uBakeMin+(vec3(cell)+0.5)*uBakeCell;
    vec4 band; float above, below;
    float inside=fogInside(world,band,above,below);
    imageStore(uShapeOut,cell,vec4(clamp(inside,-64.0,64.0),above>0.0?1.0:below>0.0?-1.0:0.0,0.0,0.0));
}
"""

# The coarse medium: the same shape, lit by the nearest sheet edge's colour.
FOG_MEDIUM_GLSL = FOG_SHAPE_GLSL + """
uniform vec4 uFogLook;        // ambient rgb, rim gain
uniform vec3 uFogRim;         // reach, sheets back z, sheets front z
uniform float uFogHaze;       // extinction of the faint haze in the clear band (steady)
void fogMedium(vec3 world, out vec3 radiance, out float extinction, out float steady) {
    radiance=vec3(0.0); extinction=0.0; steady=0.0;
    if(world.y<0.0) return;
    vec4 band; float above, below;
    float inside=fogInside(world,band,above,below);
    steady=world.z<uFogShape.x+1.0?uFogHaze:0.0;
    extinction=uFogForm.x*smoothstep(0.0,uFogForm.z,inside)+steady;
    float u=(world.x-uFogSlope.x*world.z-uEnvelopeSpan.x)*uEnvelopeSpan.y;
    vec3 upperColour=texture(uEnvelope,vec2(u,1.5/ENV_ROWS)).rgb;
    vec3 lowerColour=texture(uEnvelope,vec2(u,2.5/ENV_ROWS)).rgb;
    // The nearest sheet edge lights the mist in its colour, by distance from the sheets (outside the envelope and
    // behind or before their depth): continuous, since the light lives on the coarse cells. The far wall behind
    // the band stays dark; light fades with depth into the mist, so rims glow and interiors stay dark.
    vec3 edge=above>0.0?upperColour:below>0.0?lowerColour
             :mix(lowerColour,upperColour,clamp(-below/max(band.y-band.x,1e-3),0.0,1.0));
    float dy=max(max(above,below),0.0);
    float dz=max(max(uFogRim.y-world.z,world.z-uFogRim.z),0.0);
    // The face glows wherever the billows pushed it (a gentle fall with the push, uFogInterior.z), and fades into
    // the mist from that face. Falling off by distance from the envelope left pushed stretches dark: a broken edge.
    float rim=exp(-dz/uFogRim.x)*exp(-max(dy-uFogForm.y,0.0)*uFogInterior.z)*exp(-max(inside,0.0)*uFogShape.w);
    // The wall directly behind the sheets (inside their outline) and the far wall under them (the only volume mist
    // below the band) are distant haze: dark grey, barely lit. Lit, the far wall showed as puffs at the contact line.
    if(above<=0.0) rim*=uFogFloorLight.z;
    // Floor mist is lit from above by the sheets' lower edge colour, with a longer reach than the rims.
    float low=1.0-smoothstep(0.0,uFogFloor.x*1.5,world.y);
    // Only mist below the sheets' outline: the wall behind them must stay dark grey haze.
    float sides=smoothstep(uFogFloor.z,uFogFloor.z+3.0,abs(world.x));  // the mock's lit corner banks
    float floorLit=low*mix(0.15,1.0,sides)*smoothstep(0.0,0.3,below)*uFogFloorLight.x*exp(-below/uFogFloorLight.y)
                   *exp(-max(inside,0.0)*uFogShape.w*0.5);
    // Interior volume: large dim lumps in the unlit body, so the mass away from its edges is not one flat grey.
    float lumps=mix(1.0,uFogInterior.x+(2.0-2.0*uFogInterior.x)*fogBillow(world*uFogInterior.y+vec3(7.7,3.1,1.9)),
                    smoothstep(0.0,1.5,inside));
    radiance=uFogLook.rgb*lumps+edge*uFogLook.w*rim+lowerColour*uFogLook.w*floorLit;
}
"""


def camera(pose: Pose, aspect: float):
    """(world->view 4x4, projection 4x4, eye) from the shared framed camera; the world never moves."""
    axes = fc.camera_axes(SPEC, pose.turn, pose.tilt)
    eye, _ = fc.resolve_camera_position(SPEC, pose.turn, pose.tilt, pose.scale, pose.pan_x, pose.pan_y, pose.fov,
                                        (0., 0., 0.), None, lambda x, z: 0., axes=axes)
    right, up, back = (np.asarray(axes[i:i + 3]) for i in (0, 3, 6))
    view = np.identity(4)
    view[0, :3], view[1, :3], view[2, :3] = right, up, back
    view[:3, 3] = -view[:3, :3] @ np.asarray(eye)
    if pose.projection == 'Orthographic':
        tan = fc.viewport_tangents(ORTHO_REFERENCE_FOV, aspect)
        distance = SPEC.orbit_distance/max(pose.scale, 1e-3)
        # Parallel rays: the near plane sits well behind the eye. At .1 a zoomed-out or low camera clipped the floor
        # between the eye and the near plane, a black band along the bottom of the view.
        projection = fc.orthographic_matrix((tan[0]*distance, tan[1]*distance), -60., 200.)
    else:
        projection = fc.perspective_matrix(fc.viewport_tangents(pose.fov, aspect), .3, 200.)
    return view, np.asarray(projection).reshape(4, 4, order='F'), np.asarray(eye)


# Rise per unit z (toward the camera) of the admitted base view ray: the mist's clearance is extruded along it.
VIEW_SLOPE = math.tan(math.radians(-SPEC.pitch_base_degrees))


def waveform_envelope(packet, translation, age_fade, fog: Fog, grade=None, slopes=(0., VIEW_SLOPE)) -> np.ndarray:
    """Lower/upper sheet bounds and their colours along world x from the admitted ring packet (3 x samples x RGBA).

    Each ribbon's knots are monotone in x (the history flows along +x), so its centre height and half-width
    interpolate along x. Bounds are projected to z = 0 along the admitted base view direction (y - VIEW_SLOPE*z):
    the band at a point is A(x) + VIEW_SLOPE*z, so the mist edge follows the waveform's visible outline from the
    base view whichever sheet's depth defines it, and stays fixed in the world. Faded ends (head, tail) relax toward
    a closed band at the pivot so the mist closes in softly where no sheet is. A lab reduction; production would
    reduce the same packet on the GPU."""
    now, fade_in, lifetime, fade_out = age_fade
    x0, x1, samples = fog.envelope_range
    xs = np.linspace(x0, x1, int(samples))
    rows = np.frombuffer(packet.payload, np.float32).reshape(packet.instances, -1, 4)
    origin = np.asarray(packet.world_origin, float) + np.asarray(translation, float)
    lower, upper = np.full(xs.shape, np.inf), np.full(xs.shape, -np.inf)
    presence = np.zeros(xs.shape)
    sheets = []
    tubes = np.zeros((ENVELOPE_RIBBONS, xs.size, 4))  # per sheet: centre y, centre z, faded half-width, presence

    def smooth(x):
        x = np.clip(x, 0., 1.)
        return x*x*(3. - 2.*x)
    for path in rows:
        count, start, capacity = int(path[0, 0]), int(path[1, 1]), int(path[1, 2])
        knots = path[4:].reshape(-1, KNOT_ROWS, 4)[(start + np.arange(count)) % capacity].astype(float)
        valid = knots[:, 1, 2] > .5
        knots = knots[valid]
        if len(knots) < 2:
            continue
        x = knots[:, 0, 0] + origin[0]
        order = np.argsort(x)
        x, knots = x[order], knots[order]
        true_x = x
        z = knots[:, 0, 2] + origin[2]
        x = x - slopes[0]*z  # projected along the camera direction for the band
        order = np.argsort(x)
        x, knots, true_x, z = x[order], knots[order], true_x[order], z[order]
        age = now - (knots[:, 1, 0] + packet.coordinate_origin)
        fade = smooth(age/fade_in) if fade_in > 0 else np.ones_like(age)
        fade = fade*(smooth((lifetime - age)/fade_out) if fade_out > 0 else 1.)
        projected = knots[:, 0, 1] + origin[1] - slopes[1]*z
        centre = np.interp(xs, x, projected, left=np.nan, right=np.nan)
        half = fog.envelope_width*np.interp(xs, x, knots[:, 0, 3])*np.interp(xs, x, fade, left=0., right=0.)
        light = np.interp(xs, x, knots[:, 3, 3]*fade, left=0., right=0.)
        header = .5*(path[2, :3] + path[3, :3])
        share = np.clip(knots[:, 4, 3], 0., 1.)[:, None]
        colour = np.stack([np.interp(xs, x, c, left=0., right=0.)
                           for c in ((1. - share)*header + share*knots[:, 4, :3]).T], 1)
        here = ~np.isnan(centre)
        top, bottom = np.where(here, centre + half, -np.inf), np.where(here, centre - half, np.inf)
        sheets.append((top, bottom, colour*light[:, None]))  # per-x colour: it flows along the history
        if len(sheets) <= ENVELOPE_RIBBONS:  # the sheet itself in 3D (unprojected), for true 3D clearance
            tube = tubes[len(sheets) - 1]
            t_order = np.argsort(true_x)
            tx, tk, tf = true_x[t_order], knots[t_order], fade[t_order]
            tube[:, 0] = np.interp(xs, tx, tk[:, 0, 1] + origin[1])
            tube[:, 1] = np.interp(xs, tx, tk[:, 0, 2] + origin[2])
            tube[:, 2] = np.interp(xs, tx, tk[:, 0, 3])*np.interp(xs, tx, tf, left=0., right=0.)
            tube[:, 3] = np.interp(xs, tx, tf, left=0., right=0.)
        upper, lower = np.maximum(upper, top), np.minimum(lower, bottom)
        presence = np.maximum(presence, np.where(here, np.interp(xs, x, fade), 0.))
    # Each edge glows in a blend of the sheets near it (by proximity), never a hard switch to whichever is outermost.
    upper_colour, lower_colour = np.zeros((xs.size, 3)), np.zeros((xs.size, 3))
    upper_weight, lower_weight = np.full(xs.shape, 1e-6), np.full(xs.shape, 1e-6)
    for top, bottom, light in sheets:
        with np.errstate(invalid='ignore'):  # no sheet at x: inf - inf
            w_up = np.exp(-np.square(np.nan_to_num(upper - top, nan=1e3, posinf=1e3)/.5))
            w_down = np.exp(-np.square(np.nan_to_num(bottom - lower, nan=1e3, posinf=1e3)/.5))
        upper_colour += w_up[:, None]*light; upper_weight += w_up
        lower_colour += w_down[:, None]*light; lower_weight += w_down
    upper_colour /= upper_weight[:, None]; lower_colour /= lower_weight[:, None]
    if grade is not None:  # the mist glows in the graded colour, as the sheets do
        (nodes, (g0, g1), _, share) = grade
        tone = gradient_at(nodes, np.clip((xs - g0)/(g1 - g0), 0., 1.))
        luma = np.array((.2126, .7152, .0722))
        for c in (upper_colour, lower_colour):  # hue changes, the mist's light level does not
            level = (c @ luma)[:, None]/np.maximum(tone @ luma, 1e-6)[:, None]
            c[:] = c*(1 - share) + tone*level*share
    closed = SPEC.pivot[1]
    upper = np.where(np.isfinite(upper), upper, closed)
    lower = np.where(np.isfinite(lower), lower, closed)
    upper, lower = closed + (upper - closed)*presence, closed + (lower - closed)*presence
    def blur(a, width):
        sigma = width/((x1 - x0)/(samples - 1))
        if sigma <= 0:
            return a
        taps = np.arange(-int(3*sigma) - 1, int(3*sigma) + 2)
        kernel = np.exp(-.5*(taps/sigma)**2); kernel /= kernel.sum()
        return np.convolve(np.pad(a, len(taps)//2, mode='edge'), kernel, mode='valid')
    upper, lower = blur(upper, fog.envelope_smoothing), blur(lower, fog.envelope_smoothing)
    upper_colour = np.stack([blur(c, 4*fog.envelope_smoothing) for c in upper_colour.T], 1)
    lower_colour = np.stack([blur(c, 4*fog.envelope_smoothing) for c in lower_colour.T], 1)
    # The fringe's brightness follows a broad average, not whichever sheet happens to be outermost: a dimmer
    # topmost sheet otherwise dimmed a stretch of the lit edge into a visible break in the bank.
    luma = np.array((.2126, .7152, .0722))
    for c in (upper_colour, lower_colour):
        level = c @ luma
        even = blur(level, fog.edge_evening)
        c *= (even/np.maximum(level, 1e-4))[:, None]
    # Off the framed view's sides the band closes: views along the ribbons see them run into mist, not a clear
    # corridor to the horizon (black sky, unmisted far sheets and reflections stacking along the line of sight).
    side = 1. - smooth((np.abs(xs) - fog.sides[0])/max(fog.sides[1] - fog.sides[0], 1e-6))
    upper, lower = closed + (upper - closed)*side, closed + (lower - closed)*side
    presence = presence*side
    tubes[:, :, 2:] *= side[None, :, None]
    table = np.zeros((3 + ENVELOPE_RIBBONS, xs.size, 4), np.float32)
    table[0, :, 0], table[0, :, 1], table[0, :, 2] = lower, upper, presence
    table[1, :, :3], table[2, :, :3] = upper_colour, lower_colour
    table[3:] = tubes
    return table


def gradient_at(stops, t) -> np.ndarray:
    """Colours of gradient nodes ``((position, rgb), ...)`` at positions ``t``, exactly as RIBBON_GRADE_GLSL eases
    between neighbouring nodes."""
    t = np.asarray(t, float)
    colour = np.broadcast_to(np.asarray(stops[0][1], float), t.shape + (3,)).copy()
    for (p0, _), (p1, c1) in zip(stops, stops[1:]):
        u = np.clip((t - p0)/(p1 - p0), 0., 1.)
        colour += (np.asarray(c1, float) - colour)*(u*u*(3. - 2.*u))[..., None]
    return colour


def colour_grade(recipe, react: float) -> tuple:
    """(nodes, x range, sheet share, mist share) from the recipe's low/high gradients at a reactivity: both are
    evaluated at the union of their node positions and blended linearly there."""
    react = min(max(float(react), 0.), 1.)
    low, high = recipe.palette['low'], recipe.palette['high']
    positions = sorted({float(p) for p, _ in (*low, *high)})
    if len(positions) > GRADE_STOPS:
        raise ValueError(f'The low and high gradients together use more than {GRADE_STOPS} node positions')
    a, b = gradient_at(low, positions), gradient_at(high, positions)
    nodes = tuple((p, tuple(float(v) for v in np.clip(a[i] + (b[i] - a[i])*react, 0., 1.)))
                  for i, p in enumerate(positions))
    return (nodes, recipe.grade_range, *recipe.grade_share)


def crackle_limit(envelope, fog: Fog, mvp, width: int, samples: int = 256, slopes=(0., VIEW_SLOPE)) -> np.ndarray:
    """Per screen column, the screen v (0..1, up) of the waveform's projected top outline: the mist's edge line
    belongs to the bank above the waveform, never to boundaries below it (floor mist, the contact line)."""
    x0, x1, n = fog.envelope_range
    xs = np.linspace(x0, x1, int(n))
    upper = envelope[0, :, 1]
    limit = np.full(samples, -1.)
    for z in np.linspace(fog.sheets_z[0], fog.sheets_z[1], 5):
        world = np.stack((xs + slopes[0]*z, upper + slopes[1]*z, np.full_like(xs, z), np.ones_like(xs)))
        clip = mvp @ world
        sx, sy = (clip[0]/clip[3]*.5 + .5), (clip[1]/clip[3]*.5 + .5)
        column = np.clip((sx*samples).astype(int), 0, samples - 1)
        np.maximum.at(limit, column, sy)
    # Fill columns without a sample from neighbours, then open slightly downward.
    known = limit > -1.
    if known.any():
        limit = np.interp(np.arange(samples), np.where(known)[0], limit[known])
    return (limit - .02).astype(np.float32)


def capped(size, scale: float, max_height: int) -> tuple[float, float]:
    """A reduced-resolution target: ``scale`` of the viewport, but never taller than ``max_height`` (same aspect).
    Detail per screen fraction stays that of the approved look; cost stops growing with display resolution."""
    factor = min(scale, max_height/max(size[1], 1))
    return size[0]*factor, size[1]*factor


def lens(pose: Pose, aspect: float) -> tuple[float, float, bool]:
    """The fog volume's lens for a pose: Orthographic half-extents, or Perspective tangents."""
    if pose.projection == 'Orthographic':
        tan = fc.viewport_tangents(ORTHO_REFERENCE_FOV, aspect)
        distance = SPEC.orbit_distance/max(pose.scale, 1e-3)
        return tan[0]*distance, tan[1]*distance, True
    tan = fc.viewport_tangents(pose.fov, aspect)
    return tan[0], tan[1], False


def floor_vertices(floor: Floor) -> bytes:
    (z0, z1), fx = floor.depth_bounds, floor.half_span
    corners = ((-fx, 0., z0), (fx, 0., z0), (fx, 0., z1), (-fx, 0., z0), (fx, 0., z1), (-fx, 0., z1))
    return b''.join(struct.pack('3f', *c) for c in corners)


def _slope_texture(height: np.ndarray) -> int:
    """Height slope per uv unit (periodic central differences), baked once: two fetches instead of eight per pixel."""
    size = np.asarray(height.shape[::-1], np.float32)
    slope = np.stack(((np.roll(height, -1, 1) - np.roll(height, 1, 1))*size[0]/2,
                      (np.roll(height, -1, 0) - np.roll(height, 1, 0))*size[1]/2), axis=-1).astype(np.float32)
    name = (gl.GLuint*1)()
    gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
    texture = int(name[0])
    gl.glTextureStorage2D(texture, max(slope.shape[:2]).bit_length(), gl.GL_RG16F, slope.shape[1], slope.shape[0])
    gl.glTextureSubImage2D(texture, 0, 0, 0, slope.shape[1], slope.shape[0], gl.GL_RG, gl.GL_FLOAT,
                           np.ascontiguousarray(slope))
    gl.glGenerateTextureMipmap(texture)
    gl.glTextureParameteri(texture, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
    gl.glTextureParameteri(texture, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glTextureParameterf(texture, 0x84FE, 8.)
    for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
        gl.glTextureParameteri(texture, wrap, gl.GL_REPEAT)
    return texture


def load_floor_textures(floor: Floor) -> dict:
    """Saved maps: colour decoded from sRGB; roughness and height are linear data. Missing assets fail."""
    textures={}
    try:
        for key,path,storage in (('albedo',floor.albedo,gl.GL_SRGB8_ALPHA8),('roughness',floor.roughness,gl.GL_RGBA8),
                                 ('height',floor.height,gl.GL_RGBA8)):
            with Image.open(ROOT/path) as source:
                image=source.convert('RGBA')
            name = (gl.GLuint*1)()
            gl.glCreateTextures(gl.GL_TEXTURE_2D,1,name)
            texture=textures[key]=int(name[0])
            gl.glTextureStorage2D(texture,max(image.size).bit_length(),storage,*image.size)
            gl.glTextureSubImage2D(texture,0,0,0,*image.size,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE,np.asarray(image,np.uint8))
            gl.glGenerateTextureMipmap(texture)
            gl.glTextureParameteri(texture,gl.GL_TEXTURE_MIN_FILTER,gl.GL_LINEAR_MIPMAP_LINEAR)
            gl.glTextureParameteri(texture,gl.GL_TEXTURE_MAG_FILTER,gl.GL_LINEAR)
            gl.glTextureParameterf(texture,0x84FE,8.)  # anisotropy at glancing floor angles
            for wrap in (gl.GL_TEXTURE_WRAP_S,gl.GL_TEXTURE_WRAP_T):
                gl.glTextureParameteri(texture,wrap,gl.GL_REPEAT)
            if key == 'height':
                textures['slope'] = _slope_texture(np.asarray(image, np.float32)[:, :, 0]/255.)
        return textures
    except Exception:
        if textures:
            gl.glDeleteTextures(len(textures),list(textures.values()))
        raise


def fill_ring(recipe: Recipe, state: str, knots: int = 256, *, at: float | None = None) -> tuple[RibbonRing, float]:
    """Synthetic head: band-limited shape controls (Lab Plan section 4A) through the recipe's shape tuner; returns
    the ring and newest time."""
    flow, shaping = recipe.flow, recipe.shaping
    now = (knots-1)/flow.knot_hz if at is None else float(at)
    if not math.isfinite(now) or not (knots-1)/flow.knot_hz <= now <= 120.:
        raise ValueError('Lab sample time must contain warm history and stay within 120 seconds')
    quiet, loud = recipe.ribbon_colours['low'], recipe.ribbon_colours['high']
    ring = RibbonRing(len(PALETTE), colours=[(*a, 1.) for a, _ in quiet], edge_colours=[(*b, 1.) for _, b in quiet], period=.5)
    loud_colours = [tuple((np.asarray(a) + np.asarray(b))/2) for a, b in loud]
    alpha = 1 - math.exp(-1/flow.knot_hz/flow.shape_tau)
    count = len(PALETTE)
    if len(shaping.characters) != count:
        raise ValueError('The shape tuner needs one character per ribbon')
    stages = [[0., 0.] for _ in range(count)]
    levels = None  # per source, the two smoothing stages (band-limited like every history-carried control)
    pivot_y = SPEC.pivot[1]
    t = 0.
    for i in range(math.floor(now*flow.knot_hz)+1):
        t = i/flow.knot_hz
        positions, widths, twists, light, sparkle, tints = [], [], [], [], [], []
        raw = synthetic_sources(state, t, shaping)
        if levels is None:
            levels = {k: [v, v] for k, v in raw.items()}
        for k, v in raw.items():
            levels[k][0] += (v - levels[k][0])*alpha
            levels[k][1] += (levels[k][0] - levels[k][1])*alpha
        s = {target: quiet + (loud - quiet)*levels[shaping.drive.get(target, 'loudness')][1]
             for target, (quiet, loud) in shaping.ranges.items()}
        arc = 1. + s['arc']*levels['bass'][1]
        for r in range(count):
            k = r - (count - 1)/2  # a fixed fan in height and depth, identical in low/high
            amplitude, width, frequency, offset, brightness = shaping.characters[r]
            phase = 2*math.pi*flow.head_hz*frequency*t + offset + flow.phase
            phase += flow.phase_swell*math.sin(.31*phase+r*.6)
            envelope = 1. + flow.amplitude_swell*math.sin(.23*phase+.4)
            section = 1. if math.sin(2*math.pi*.3*t + r*2.) > .2 else 0.
            stages[r][0] += (section - stages[r][0])*alpha
            stages[r][1] += (stages[r][0] - stages[r][1])*alpha
            swell = stages[r][1]
            deformation = s['deformation']*(.24*math.sin(2*phase+.7)+.18*math.sin(.61*phase+offset))
            half = width*(s['width'] + s['width_swell']*swell)*(1.0 + .2*math.sin(phase))
            y = pivot_y + s['lift'] + s['amplitude']*arc*amplitude*envelope*(math.sin(phase)+deformation) \
                + .5*k*s['spread']*math.cos(.37*phase)
            positions.append((flow.speed*t, y, .65*k + flow.depth_sway*math.cos(phase*.55+r)))
            widths.append(half)
            twists.append(s['twist']*(.7*math.sin(.48*phase+r*1.3)+.3*math.sin(.87*phase+.4)))
            light.append(brightness*s['emission']*(.85 + .3*swell))
            highs = .5 + .5*math.sin(2*math.pi*.53*t + r*1.7)  # synthetic highs: sparkle density
            sparkle.append(min(1., s['sparkle']*(.35 + .65*highs)))
            tints.append((*loud_colours[r], min(max(s['tint'], 0.), 1.)))
        ring.append(t, positions, widths, twists, light, sparkle, tints)
    return ring, now


class Lab:
    """Owns the diagnostic target and lab GL resources; `close()` retires them under the target's context."""

    def __init__(self, recipe: Recipe, size: tuple[int, int]):
        self.recipe, self.size = recipe, size
        self.target = OffscreenRenderTarget(*size)
        self.resources, self.scene, self.ribbons = MeshResources('waveform lab'), SceneTarget('waveform lab'), RibbonPrimitive()
        self.reflection = PlanarReflection('waveform lab floor')
        self.fog, self.reflected_fog = FogVolume('waveform lab mist'), FogVolume('waveform lab reflected mist')
        self.march = FogMarch('waveform lab mist', FOG_COVERAGE_GLSL)
        self._crackle_limit = None
        self._bake_grid = None
        self._specular, self._specular_size = None, None
        self._slopes = (0., VIEW_SLOPE)
        self.reflected_march = FogMarch('waveform lab reflected mist', FOG_COVERAGE_GLSL)
        self.textures = {}

    def close(self):
        with self.target.current():
            if self.textures:
                gl.glDeleteTextures(len(self.textures), list(self.textures.values()))
                self.textures = {}
            self.reflection.release()
            self._release_specular()
            self.fog.release()
            self.reflected_fog.release()
            self.march.release()
            self.reflected_march.release()
            self.ribbons.release()
            self.scene.release()
            self.resources.release_resources()
        self.target.close()

    def render(self, state: str, *, flat: bool, pose: str = 'mock', at: float | None = None) -> np.ndarray:
        with self.target.current():
            return self._render(state, flat=flat, pose=pose, at=at)

    def render_history(self, ring: RibbonRing, now: float, *, flat: bool = False, pose: str = 'mock') -> np.ndarray:
        """Read explicitly advanced lab history; rendering never appends or integrates it."""
        if not math.isfinite(now):
            raise ValueError('History render time must be finite')
        with self.target.current():
            return self._render('low', flat=flat, pose=pose, at=None, history=(ring, float(now)))

    def _render(self, state: str, *, flat: bool, pose: str, at: float | None,
                history: tuple[RibbonRing, float] | None = None) -> np.ndarray:
        recipe, (width, height) = self.recipe, self.size
        environment, flow = recipe.environment, recipe.flow
        ring, now = fill_ring(recipe, state, at=at) if history is None else history
        view, projection, eye = camera(POSES[pose], width/height)
        scroll = np.identity(4)
        scroll[0, 3] = flow.head_x - flow.speed*now
        mvp = (projection @ view).flatten(order='F')
        ribbon_view = view @ scroll
        ribbon_mvp = tuple((projection @ ribbon_view).flatten(order='F'))
        orthographic = POSES[pose].projection == 'Orthographic'
        draw = dict(view=tuple(ribbon_view.flatten(order='F')), material=recipe.material, orthographic=orthographic,
                    sweep_axis=(1.,0.,0.), floor=FLOOR_CONTACT,
                    age_fade=(now, flow.fade_in, (ring.capacity - 1)/flow.knot_hz, flow.fade_out),
                    mist=environment.mist, mist_frame=(scroll[0, 3], 0., 0.),
                    grade=ribbon_grade(*colour_grade(recipe, STATES[state]['react'])[:3]))
        card = SimpleNamespace(viewport=(0, 0, width, height), logical_size=(float(width), float(height)),
                               matrix_values=(2/width, 0, 0, 0, 0, -2/height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                               quad_vao=self.target.vao)
        packet = ring.packet()
        forward = -view[2, :3]
        self._slopes = (float(forward[0]/forward[2]), float(forward[1]/forward[2]))
        envelope = None if flat or recipe.fog is None else waveform_envelope(packet, scroll[:3, 3], draw['age_fade'],
                                                                              recipe.fog,
                                                                              colour_grade(recipe, STATES[state]['react']),
                                                                              self._slopes)
        self.target.bind(clear=(0., 0., 0., 0.))
        fogged = not flat and recipe.fog is not None
        if fogged:
            camera_lens = lens(POSES[pose], width/height)
            self._update_fog(self.fog, view, camera_lens, (width, height), recipe.fog.cell, recipe.fog.slices, envelope)
            self._bake_shape()
            self._crackle_limit = crackle_limit(envelope, recipe.fog, projection @ view, width, slopes=self._slopes)
            self._update_fog(self.reflected_fog, mirror_view(view, 0.), camera_lens, (width, height),
                             recipe.fog.reflection_cell, recipe.fog.reflection_slices, envelope)
            fog = recipe.fog
            march = dict(steps=fog.steps, max_extinction=fog.density, erosion=fog.erosion,
                         detail_frequency=fog.detail_frequency, shadow=fog.shadow, step=fog.step,
                         medium=self._fog_uniforms, shadow_floor=fog.shadow_floor, edge_glow=fog.edge_glow,
                         base=fog.ambient)
            self.march.march(self.fog, size=capped((width, height), fog.march_scale, fog.march_max_height), ground=0.,
                             **march)
            # The mirrored camera starts below the floor (no medium there) and sees the mist above it.
            self.reflected_march.march(self.reflected_fog,
                                       size=capped((width, height), fog.reflection_march_scale,
                                                   fog.reflection_march_max_height), **march)
        if not flat:
            with self._fog_bound(self.reflected_fog if fogged else None) as fog:
                self._reflect(packet, projection, view, scroll, {**draw, 'mist': {**draw['mist'], **fog}})
        with self._fog_bound(self.fog if fogged else None) as fog:
            draw = {**draw, 'mist': {**draw['mist'], **fog}}
            self._draw_scene(state, flat, packet, draw, mvp, eye, view, orthographic, ribbon_mvp, card, now, fogged)
        return self.target.read_rgba()

    def _fog_bound(self, volume):
        """The volume bound for its passes, or a no-op scope with the analytic-mist uniforms."""
        from contextlib import nullcontext
        return volume.bound() if volume is not None else nullcontext(dict(FOG_OFF))

    def _bake_shape(self):
        """Evaluate the mist shape once per cell of the bake box (RG16F, allocated once per box size)."""
        fog = self.recipe.fog
        if fog.bake_cell <= 0:
            return
        from rendering.quick.scene3d.compute import bound_image, dispatch
        lo, hi = (np.asarray(v, float) for v in fog.bake_box)
        grid = tuple(int(math.ceil(v)) for v in (hi - lo)/fog.bake_cell)
        texture = self.textures.get('shape')
        if texture is None or self._bake_grid != grid:
            if texture is not None:
                gl.glDeleteTextures(1, [texture])
            name = (gl.GLuint*1)()
            gl.glCreateTextures(gl.GL_TEXTURE_3D, 1, name)
            texture = self.textures['shape'] = int(name[0])
            gl.glTextureStorage3D(texture, 1, gl.GL_RG16F, *grid)
            for parameter, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                                     (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE),
                                     (gl.GL_TEXTURE_WRAP_R, gl.GL_CLAMP_TO_EDGE)):
                gl.glTextureParameteri(texture, parameter, value)
            self._bake_grid = grid
        program = self.resources.compute_program('shape bake', SHAPE_BAKE_COMPUTE)
        gl.glUseProgram(program)
        self._fog_uniforms(program)
        gl.glUniform3f(gl.glGetUniformLocation(program, 'uBakeMin'), *lo)
        gl.glUniform3f(gl.glGetUniformLocation(program, 'uBakeCell'), *((hi - lo)/np.asarray(grid, float)))
        with bound_image(0, texture, gl.GL_WRITE_ONLY, gl.GL_RG16F, layered=True):
            dispatch((-(-grid[0]//8), -(-grid[1]//8), -(-grid[2]//4)), gl.GL_TEXTURE_FETCH_BARRIER_BIT)
        gl.glUseProgram(0)

    def _update_fog(self, volume, view, camera_lens, size, cell, slices, envelope):
        fog = self.recipe.fog
        grid = (-(-size[0]//cell), -(-size[1]//cell), slices)
        program = self.resources.compute_program('fog medium', fog_inject_source(FOG_MEDIUM_GLSL))
        self._upload_envelope(envelope)
        volume.update(program, view=view, lens=camera_lens, depth_range=fog.depth_range, grid=grid,
                      medium=self._fog_uniforms)

    def _fog_uniforms(self, program):
        """The shape's (and the medium's light) uniforms, for the inject and march programs alike."""
        fog = self.recipe.fog
        x0, x1, _ = fog.envelope_range
        location = lambda name: gl.glGetUniformLocation(program, name)
        gl.glBindTextureUnit(14, self.textures['envelope'])
        gl.glUniform1i(location('uEnvelope'), 14)
        gl.glUniform2f(location('uEnvelopeSpan'), x0, 1./(x1 - x0))
        gl.glUniform4f(location('uFogForm'), fog.density, fog.margin, fog.softness, fog.noise_scale)
        gl.glUniform4f(location('uFogShape'), fog.start_z, fog.band_depth, fog.noise, fog.light_decay)
        gl.glUniform2f(location('uFogClearance'), *fog.clearance)
        gl.glUniform1f(location('uFogTube'), fog.tube)
        bake = self.textures.get('shape')
        gl.glUniform1i(location('uBaked'), int(bake is not None and fog.bake_cell > 0))
        if bake is not None:
            lo, hi = (np.asarray(v, float) for v in fog.bake_box)
            gl.glBindTextureUnit(13, bake)
            gl.glUniform1i(location('uShapeBake'), 13)
            gl.glUniform3f(location('uBakeMin'), *lo)
            gl.glUniform3f(location('uBakeSize'), *(hi - lo))
        gl.glUniform2f(location('uFogSlope'), *self._slopes)
        gl.glUniform1f(location('uFogEnds'), fog.ends)
        gl.glUniform2f(location('uFogSides'), *fog.sides)
        gl.glUniform3f(location('uFogFloor'), *fog.floor)
        gl.glUniform3f(location('uFogFloorLight'), *fog.floor_light)
        gl.glUniform3f(location('uFogInterior'), *fog.interior)
        gl.glUniform4f(location('uFogLook'), *fog.ambient, fog.rim)
        gl.glUniform3f(location('uFogRim'), fog.reach, *fog.sheets_z)
        gl.glUniform1f(location('uFogHaze'), fog.haze)

    def _upload_envelope(self, envelope):
        """One small RGBA32F table, allocated once per size and rewritten per frame."""
        texture = self.textures.get('envelope')
        if texture is None:
            name = (gl.GLuint*1)()
            gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
            texture = self.textures['envelope'] = int(name[0])
            gl.glTextureStorage2D(texture, 1, gl.GL_RGBA32F, envelope.shape[1], envelope.shape[0])
            for parameter, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                                     (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)):
                gl.glTextureParameteri(texture, parameter, value)
        gl.glTextureSubImage2D(texture, 0, 0, 0, envelope.shape[1], envelope.shape[0], gl.GL_RGBA, gl.GL_FLOAT,
                               np.ascontiguousarray(envelope))

    def _draw_scene(self, state, flat, packet, draw, mvp, eye, view, orthographic, ribbon_mvp, card, now, fogged):
        recipe, (width, height) = self.recipe, self.size
        environment = recipe.environment
        with self.scene.scope(card, 4, self.resources, overlay=1.0, bloom=0. if flat else recipe.bloom,
                              oit=True, hdr=None if flat or not recipe.bloom else recipe.exposure):
            gl.glViewport(0, 0, width, height)
            # The finite ground dissolves into the mist's far colour, including above its Perspective horizon.
            background = environment.backdrop if flat else tuple(c*.35 for c in environment.backdrop)
            gl.glClearBufferfv(gl.GL_COLOR, 0, (*background, 1.))
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthFunc(gl.GL_LESS)
            gl.glDepthMask(gl.GL_TRUE)
            with self.scene.emission_writes():
                # The floor takes the cheap analytic mist (slightly tinted, dark with distance); the reactive volume
                # mist is for the space above and the edges, composited separately after the floor.
                self._floor(mvp, eye, view, orthographic, (width, height), flat=flat)
                if flat:
                    self._flat_ribbons(packet, ribbon_mvp)
                if fogged:
                    self.march.composite(glow=recipe.fog.glow, crackle=recipe.fog.crackle,
                                         crackle_glow=recipe.fog.crackle_glow, crackle_limit=self._crackle_limit,
                                         fringe_smoothing=recipe.fog.fringe_smoothing)
            if not flat:
                with self.scene.transparent_writes(card, self.resources):
                    self.ribbons.draw(packet, ribbon_mvp, shading='body', **draw)
                with self.scene.emission_writes():
                    gl.glEnablei(gl.GL_BLEND, 0)
                    gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
                    gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
                    gl.glDepthMask(gl.GL_FALSE)
                    self.ribbons.draw(packet, ribbon_mvp, shading='light', **draw)
                    if recipe.sparks is not None:
                        self.ribbons.draw(packet, ribbon_mvp, shading='sparks', sparks=recipe.sparks, now=now,
                                          mist=draw['mist'], mist_frame=draw['mist_frame'], material=recipe.material,
                                          sweep_axis=draw['sweep_axis'], grade=draw['grade'], floor=draw['floor'])
                    if recipe.strays is not None:
                        self.ribbons.draw(packet, ribbon_mvp, shading='strays', strays=recipe.strays, now=now,
                                          mist=draw['mist'], mist_frame=draw['mist_frame'], material=recipe.material,
                                          sweep_axis=draw['sweep_axis'], grade=draw['grade'], floor=draw['floor'])
                    gl.glDepthMask(gl.GL_TRUE)
                    gl.glDisablei(gl.GL_BLEND, 0)

    def _reflect(self, packet, projection, view, scroll, draw):
        """Ribbon light through the mirrored camera; the receiver is never drawn into its own reflection."""
        floor, (width, height) = self.recipe.floor, self.size
        mirrored = mirror_view(view, 0.)
        self.reflection.begin(*(int(v) for v in capped((width, height), floor.resolution, floor.resolution_max_height)))
        try:
            gl.glDepthFunc(gl.GL_LESS)
            gl.glEnablei(gl.GL_BLEND, 0)
            gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
            gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)  # alpha: weighted height
            gl.glDepthMask(gl.GL_FALSE)
            if draw['mist'].get('uFogRange', (0., 0., 0., 0.))[3] > .5:
                # The mist's own light, mirrored (additive); alpha stays the emitters' weighted height.
                self.reflected_march.composite(additive=True, scale=self.recipe.floor.mist_reflection)
            reflected_view = mirrored @ scroll
            reflected_mvp = tuple((projection @ reflected_view).flatten(order='F'))
            self.ribbons.draw(packet, reflected_mvp, shading='light', **{**draw, 'view': tuple(reflected_view.flatten(order='F'))})
            if self.recipe.sparks is not None:
                self.ribbons.draw(packet, reflected_mvp, shading='sparks', sparks=self.recipe.sparks, now=draw['age_fade'][0],
                                  mist=draw['mist'], mist_frame=draw['mist_frame'], material=self.recipe.material,
                                  sweep_axis=draw['sweep_axis'], grade=draw['grade'], floor=draw['floor'])
            if self.recipe.strays is not None:
                self.ribbons.draw(packet, reflected_mvp, shading='strays', strays=self.recipe.strays,
                                  now=draw['age_fade'][0], mist=draw['mist'], mist_frame=draw['mist_frame'],
                                  material=self.recipe.material, sweep_axis=draw['sweep_axis'], grade=draw['grade'],
                                  floor=draw['floor'])
        finally:
            gl.glDisablei(gl.GL_BLEND, 0)
            self.reflection.end()

    def _floor(self, mvp, eye, view, orthographic, size, *, flat=False, mist_off=False):
        recipe = self.recipe
        floor, environment = recipe.floor, recipe.environment
        if 'albedo' not in self.textures:
            self.textures.update(load_floor_textures(floor))
        vao, count = self.resources.mesh('floor', floor_vertices(floor), (3,))
        program = self.resources.program('floor', FLOOR_VERTEX, FLOOR_FRAGMENT)
        names = ('uMvp', 'uFlat', 'uAlbedo', 'uSlope', 'uFogLight', 'uFogLit', 'uReflection', 'uReflectionLook',
                 'uReflectionContact', 'uViewport', 'uBackdrop', 'uAmbient', 'uFloor', 'uFloorTone', 'uRipple', 'uEye',
                 'uForward', 'uOrthographic', 'uMist', 'uMistShape', 'uFogVolume', 'uFogView', 'uFogLens', 'uFogRange',
                 'uStreak', 'uHot', 'uEnvelope', 'uEnvelopeSpan', 'uPool', 'uPoolZ', 'uColumn', 'uSpecMode',
                 'uSpecular')
        u = self.resources.uniforms('floor', names, required=False)
        gl.glUseProgram(program)
        gl.glUniform1i(u['uFlat'], int(flat))
        gl.glUniformMatrix4fv(u['uMvp'], 1, gl.GL_FALSE, np.asarray(mvp, np.float32))
        lit = not flat and self.fog.has_resources and self.recipe.fog is not None
        for unit, (name, texture) in enumerate((('uAlbedo', self.textures['albedo']), ('uSlope', self.textures['slope']),
                                                ('uReflection', self.reflection.texture),
                                                ('uFogLight', self.fog.medium_texture if lit else 0))):
            if name == 'uFogLight':
                unit = 13  # a 3D sampler never shares a unit with the 2D ones
            gl.glBindTextureUnit(unit, texture)
            gl.glUniform1i(u[name], unit)
        gl.glUniform1i(u['uFogLit'], int(lit))
        gl.glUniform4f(u['uReflectionLook'], floor.streak[0], floor.lod[0], floor.lod[1], floor.blur)
        gl.glUniform4f(u['uHot'], *floor.hot, floor.albedo_bias)
        envelope = self.textures.get('envelope') if lit else None
        gl.glUniform4f(u['uPool'], floor.pool[0] if envelope else 0., *floor.pool[1:])
        gl.glUniform1f(u['uPoolZ'], 0.)
        gl.glUniform3f(u['uColumn'], *floor.column)
        if envelope:
            x0, x1, _ = self.recipe.fog.envelope_range
            gl.glBindTextureUnit(14, envelope)
            gl.glUniform1i(u['uEnvelope'], 14)
            gl.glUniform2f(u['uEnvelopeSpan'], x0, 1./(x1 - x0))
        gl.glUniform4f(u['uStreak'], 0., floor.streak[1], floor.streak[2], 8.)
        gl.glUniform4f(u['uReflectionContact'], 0., *floor.contact)
        gl.glUniform2f(u['uViewport'], *size)
        gl.glUniform3f(u['uBackdrop'], *environment.backdrop)
        gl.glUniform3f(u['uAmbient'], *floor.ambient)
        gl.glUniform4f(u['uFloor'], floor.tile, floor.micro_tile, floor.reflection, floor.f0)
        gl.glUniform4f(u['uFloorTone'], floor.albedo_gain, floor.diffuse, *floor.relief)
        gl.glUniform3f(u['uRipple'], *floor.ripple)
        gl.glUniform3f(u['uEye'], *eye)
        gl.glUniform3f(u['uForward'], *(-view[2, :3]))
        gl.glUniform1i(u['uOrthographic'], int(orthographic))
        gl.glUniform4f(u['uMist'], *environment.mist['uMist'])
        gl.glUniform4f(u['uMistShape'], *((0., 0., 0., 0.) if mist_off else environment.mist['uMistShape']))
        gl.glUniform1i(u['uFogVolume'], FOG_OFF['uFogVolume'])
        if lit:  # the light field's coordinates; transmittance stays with the march composite
            fog = self.fog.uniforms
            gl.glUniformMatrix4fv(u['uFogView'], 1, gl.GL_FALSE, np.asarray(fog['uFogView'], np.float32))
            gl.glUniform4f(u['uFogLens'], *fog['uFogLens'])
            gl.glUniform4f(u['uFogRange'], *fog['uFogRange'][:3], 0.)
        else:
            gl.glUniform4f(u['uFogRange'], *FOG_OFF['uFogRange'])
        gl.glBindVertexArray(vao)
        # The reflection term (streak taps, contact probe) holds no detail finer than its reflection target, so on
        # large displays it is evaluated at a capped height and read back by the full-resolution pass.
        factor = min(1., floor.specular_max_height/max(size[1], 1))
        if flat or factor >= 1.:
            gl.glUniform1i(u['uSpecMode'], 0)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
        else:
            texture, target = self._specular_target((int(size[0]*factor), int(size[1]*factor)))
            framebuffer = int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING))
            viewport = [int(v) for v in np.asarray(gl.glGetIntegerv(gl.GL_VIEWPORT)).reshape(-1)[:4]]
            depth_test = gl.glIsEnabled(gl.GL_DEPTH_TEST)
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, target)
            gl.glViewport(0, 0, *self._specular_size)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glClearBufferfv(gl.GL_COLOR, 0, (0., 0., 0., 0.))
            gl.glUniform1i(u['uSpecMode'], 1)
            gl.glUniform2f(u['uViewport'], *self._specular_size)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, framebuffer)
            gl.glViewport(*viewport)
            if depth_test:
                gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glUniform1i(u['uSpecMode'], 2)
            gl.glUniform2f(u['uViewport'], *size)
            gl.glBindTextureUnit(3, texture)
            gl.glUniform1i(u['uSpecular'], 3)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
        for unit in (0, 1, 2, 3, 13, 14):
            gl.glBindTextureUnit(unit, 0)

    def _specular_target(self, size):
        """RGBA16F target for the floor's reflection pre-pass, reallocated only when its size changes."""
        if self._specular_size != size:
            self._release_specular()
            name = (gl.GLuint*1)()
            gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
            texture = int(name[0])
            gl.glTextureStorage2D(texture, 1, gl.GL_RGBA16F, *size)
            for parameter, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                                     (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)):
                gl.glTextureParameteri(texture, parameter, value)
            gl.glCreateFramebuffers(1, name)
            target = int(name[0])
            gl.glNamedFramebufferTexture(target, gl.GL_COLOR_ATTACHMENT0, texture, 0)
            self._specular = (texture, target)
            self._specular_size = size
        return self._specular

    def _release_specular(self):
        if self._specular:
            texture, target = self._specular
            gl.glDeleteFramebuffers(1, [target])
            gl.glDeleteTextures(1, [texture])
        self._specular, self._specular_size = None, None

    def _flat_ribbons(self, packet, mvp):
        """Flat ribbon silhouettes in one known colour: rewrite every ribbon's colours in a copy of the packet."""
        data = np.frombuffer(packet.payload, np.float32).copy().reshape(packet.instances, -1, 4)
        data[:, 2] = data[:, 3] = (*FLAT['ribbon'], 1.)
        data[:, 4 + 4::KNOT_ROWS, 3] = 0.  # tint share off: one known colour
        flat = type(packet)(data.tobytes(), packet.instances, packet.vertices, packet.world_origin, packet.coordinate_origin)
        self.ribbons.draw(flat, mvp, material=self.recipe.material, sweep_axis=(1.,0.,0.))


def measure_flat(pixels: np.ndarray) -> dict:
    """Ribbon envelope from a flat mock-pose render, as panel fractions."""
    height, width = pixels.shape[:2]
    rgb = pixels[:, :, :3].astype(int)
    ribbon = (rgb[:, :, 0] > 120) & (rgb[:, :, 2] > 120) & (rgb[:, :, 1] < 60)  # FLAT['ribbon'] magenta
    envelope = {}
    for x in ENVELOPE['low']:
        column = np.where(ribbon[:, min(x, width - 1)])[0]
        envelope[str(x)] = [float(column.min()/height), float(column.max()/height)] if column.size else None
    return dict(envelope=envelope)


def landmark_report(measured: dict, state: str, height: int = 709) -> dict:
    target = {str(x): (top/height, bottom/height) for x, (top, bottom) in ENVELOPE[state].items()}
    rows, errors = {}, []
    for x, value in measured['envelope'].items():
        goal = target.get(x)
        if value is None or goal is None:
            continue
        rows[x] = dict(lab=value, target=list(goal))
        errors += [value[0] - goal[0], value[1] - goal[1]]
    present = [v for v in measured['envelope'].values() if v]
    return dict(rows=rows, envelope_mean_abs_error=float(np.mean(np.abs(errors))) if errors else None,
                lab_envelope=[min(v[0] for v in present), max(v[1] for v in present)] if present else None,
                target_envelope=[min(t for t, _ in target.values()), max(b for _, b in target.values())])


def overlay(image: Image.Image, state: str) -> Image.Image:
    """Target ribbon envelope over an image; the scene has no visible horizon/contact boundary."""
    sheet = image.convert('RGB')
    draw = ImageDraw.Draw(sheet)
    xs = sorted(ENVELOPE[state])
    for edge in (0, 1):
        draw.line([(x, ENVELOPE[state][x][edge]) for x in xs], fill=(255, 230, 0), width=1)
    return sheet


def run(output: Path, cards: Path | None, *, board: str = 'primary', recipe_name: str = 'complete') -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Refusing to overwrite evidence: {output}')
    output.mkdir(parents=True, exist_ok=True)
    if board not in ('primary','fog'):
        raise ValueError('Unknown reference board')
    width,height = (820,718) if board=='fog' else (640,709)
    recipe = RECIPES[recipe_name]
    report, images = {}, {}
    lab = Lab(recipe, (width,height))
    try:
        for state in STATES:
            flat = lab.render(state, flat=True)
            lit = lab.render(state, flat=False)
            images[state] = (Image.fromarray(flat), Image.fromarray(lit))
            Image.fromarray(flat).save(output/f'flat_{state}.png')
            Image.fromarray(lit).save(output/f'lit_{state}.png')
            report[state] = (landmark_report(measure_flat(flat), state) if board=='primary'
                             else dict(status='Use fog ROI comparisons; no ribbon envelope has been traced for this board'))
    finally:
        lab.close()
    wide = Lab(recipe, (1280, 720))
    try:
        for state in STATES:
            for pose in POSES:
                Image.fromarray(wide.render(state, flat=False, pose=pose)).save(output/f'wide_{state}_{pose}.png')
    finally:
        wide.close()
    if cards is not None:
        sheet = Image.new('RGB', (width*3 + 16, height*2 + 8))
        for row, state in enumerate(STATES):
            mock = Image.open(cards/f'{state}.png')
            expected = (width if board=='fog' or state=='low' else 638,height)
            if mock.size != expected:
                raise ValueError(f'Expected native {board} {state} card of size {expected}')
            picture = (lambda im: overlay(im,state)) if board=='primary' else (lambda im: im.convert('RGB'))
            sheet.paste(picture(mock), (0,row*(height+8)))
            sheet.paste(picture(images[state][0]), (width+8,row*(height+8)))
            sheet.paste(images[state][1].convert('RGB'), (2*width+16,row*(height+8)))
        sheet.save(output/'mock_flat_lit.png')
    poses = Image.new('RGB', (640*len(POSES), 360*2))
    for row, state in enumerate(STATES):
        for column, pose in enumerate(POSES):
            poses.paste(Image.open(output/f'wide_{state}_{pose}.png').convert('RGB').resize((640, 360)), (column*640, row*360))
    poses.save(output/'navigation_poses.png')
    receipt = dict(stage='WR-04 floor, waveform and dense distance mist; navigation poses', board=board, recipe_name=recipe_name,
                   card_size=(width,height),
                   recipe=json.loads(json.dumps(asdict(recipe), default=str)), states=STATES,
                   poses={k: asdict(v) for k, v in POSES.items()}, landmarks=report,
                   producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
    (output/'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cards', type=Path)
    parser.add_argument('--board', choices=('primary','fog'), default='primary')
    parser.add_argument('--recipe', choices=tuple(RECIPES), default='complete',
                        help='named look: the complete-scene board, the alternate board, or the preset-range board')
    args = parser.parse_args()
    result = run(args.output, args.cards, board=args.board, recipe_name=args.recipe)
    print(json.dumps({state: {k: v for k, v in r.items() if k != 'rows'} for state, r in result['landmarks'].items()}, indent=2))
