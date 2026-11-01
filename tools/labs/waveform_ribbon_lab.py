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
        [--cards .artifacts/evidence/waveform_ribbon/wr00_reference_projection]
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
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

from core.ribbon_ring import RibbonRing
from core.settings import framed_camera as fc
from rendering.gl_programs.fog_volume import fog_inject_source
from rendering.gl_programs.mist import FOG_OFF, MIST_GLSL, mist_uniforms
from rendering.gl_programs.reflection import PLANAR_REFLECTION_GLSL, mirror_view
from rendering.quick.scene3d.fog_volume import FogMarch, FogVolume
from rendering.quick.scene3d.reflection import PlanarReflection
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.ribbon import RibbonMaterial, RibbonPrimitive, RibbonSparks
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
    backdrop: tuple = (.12, .16, .24)
    # Clear around the waveform, dense immediately beyond it, then continuous with the far background.
    mist: dict = field(default_factory=lambda: mist_uniforms(centre_xz=(0., 9.), radii_xz=(24., 10.), falloff=.25,
                                    floor_thickening=2., thickening_height=2., low_glow=.5))


@dataclass(frozen=True)
class Fog:
    """S3D-7 volume mist shaped by the waveform: thick everywhere behind the sheets except a clear band that hugs their
    exact lower/upper envelope along x (reduced per frame from the admitted history). The band's rim glows in the
    colour of the nearest sheet edge and darkens into the mass; a detail march adds the billows."""
    density: float = 1.6            # extinction per world unit inside the mist
    margin: float = .1              # clear air beyond the envelope (world units)
    softness: float = 1.5           # depth over which coarse coverage rises: the detail march erodes within it
    noise_scale: float = .35        # lobe frequency of the band's edge (per world unit)
    noise: float = 2.6              # lobe displacement of the edge (world units)
    start_z: float = -1.7           # the mist begins behind this world z (just behind the sheets)
    band_depth: float = 7.          # the clear band reaches this far behind start_z; the far wall closes it
    sheets_z: tuple = (-1.7, 1.7)   # depth range of the sheets, for the rim light's distance
    ambient: tuple = (.09, .1, .17)  # radiance of unlit mist: the cloud bodies' own dim structure
    rim: float = 120.               # rim light gain on the nearest sheet edge colour
    reach: float = .35              # e-folding distance of the rim light from the envelope (world units)
    light_decay: float = 2.         # its extinction per world unit of depth into the mist
    haze: float = 0.                # faint haze in the clear band behind the sheets (never eroded)
    envelope_range: tuple = (-40., 40., 640)  # world x span and samples of the envelope reduction
    envelope_smoothing: float = .25 # Gaussian along x (world units)
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
    steps: int = 96
    step: tuple = (.15, 1.)
    erosion: float = .75
    detail_frequency: float = .8
    shadow: tuple = (.6, 4.)
    shadow_floor: float = .5
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
    albedo_gain: float = .35        # wet concrete is dark
    ambient: tuple = (.010, .012, .020)
    diffuse: float = .8             # gain on the mist's light field at the floor (the ribbon light, shared)
    reflection: float = 1.2         # reflection strength before Fresnel (look gain)
    f0: float = .02                 # water film
    relief: tuple = (.03, .4)       # height amplitude of the broad and micro relief (world units)
    # Reflection offset per unit slope (uv): broad wobble, micro offset across and along the view.
    ripple: tuple = (.25, .01, .12)
    lod: tuple = (1., 1.)           # reflection mip (half-resolution target: already soft)
    contact: tuple = (.002, 6., 6.)  # spread (uv) per unit of reflected height; along/across; probe mip
    resolution: float = .5          # reflection target scale


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
# Per-ribbon character (amplitude, width, wave frequency, phase, light): identical sheets on even phases braid into a
# regular lattice and sum to white; the mock's sheets differ and cross irregularly.
CHARACTER = ((1., 1., 1., 0., 1.), (.85, 1.1, .96, 1.1, 1.5), (.72, .75, 1.07, .55, .65))
STATES = {  # labelled synthetic controls, authored toward the complete-scene fog board; not music
    'low': dict(width=.40, width_swell=.08, twist=.85, emission=.7, spread=.32, amplitude=.5, lift=-.35, sparkle=.18,
                deformation=.15),
    'high': dict(width=.78, width_swell=.28, twist=1.85, emission=.85, spread=1.25, amplitude=1.2, lift=.2, sparkle=.85,
                 deformation=.3),
}


@dataclass(frozen=True)
class Recipe:
    environment: Environment = field(default_factory=Environment)
    fog: Fog | None = field(default_factory=Fog)
    floor: Floor = field(default_factory=Floor)
    flow: Flow = field(default_factory=Flow)
    # Mock-directed look (WR-04): saturated darker body, thin near-white irregular strands and rims, visible glints.
    material: RibbonMaterial = field(default_factory=lambda: RibbonMaterial(
        strands=40., strand_half_width=.018, strand_light=3.2, strand_white=.04, strand_jitter=.35, strand_warp=.18,
        strand_variation=.9, cross_curve=.35, warp_frequency=.2, rim_light=3.5, rim_white=.08, rim_half_width=.009,
        fill_light=.20, fill_centre=.3, rim_glow_light=.5,
        rim_glow_width=.04, body_alpha=.025, body_tint=.4, glint_density=1.4, glint_chance=.12, glint_light=3.,
        glint_radius=.25, glint_min_pixels=.8))
    sparks: RibbonSparks = field(default_factory=lambda: RibbonSparks(per_knot=16, lifetime=4.5, drift=1.2, rise=.4,
                                                                       smallest=1.6, largest=5., light=16., white=.25))
    bloom: float = .18
    exposure: float = 1.


FLOOR_VERTEX = """#version 460 core
layout(location=0) in vec3 aPosition;
uniform mat4 uMvp;
out vec3 vWorldPos;
void main() { vWorldPos=aPosition; gl_Position=uMvp*vec4(aPosition,1.0); }
"""
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
uniform vec3 uEye;
uniform vec3 uForward;
uniform int uOrthographic;
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
""" + MIST_GLSL + PLANAR_REFLECTION_GLSL + """
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
    vec3 albedo=mix(texture(uAlbedo,uv).rgb,texture(uAlbedo,turn*uv*1.37+vec2(.31,.47)).rgb,.4)*uFloorTone.x;
    vec2 broad=slopeAt(vWorldPos.xz,uFloor.x)*uFloorTone.z;
    vec2 micro=slopeAt(vWorldPos.xz,uFloor.y)*uFloorTone.w;
    // Offsets follow the viewed ground axes, so a turned camera streaks along its own view.
    vec3 groundForward=normalize(vec3(uForward.x,0.0,uForward.z));
    vec3 groundRight=cross(groundForward,vec3(0,1,0));
    vec2 axes=vec2(dot(vec3(broad.x,0,broad.y),groundRight),dot(vec3(broad.x,0,broad.y),groundForward));
    vec2 fine=vec2(dot(vec3(micro.x,0,micro.y),groundRight),dot(vec3(micro.x,0,micro.y),groundForward));
    vec2 offset=axes*uRipple.x+fine*vec2(uRipple.y,uRipple.z);
    vec3 reflected=planarReflection(gl_FragCoord.xy/uViewport,offset,0.0);
    vec3 view=uOrthographic==1?normalize(uForward):normalize(vWorldPos-uEye);
    float cosine=clamp(abs(view.y),0.0,1.0);
    float fresnel=uFloor.w+(1.0-uFloor.w)*pow(1.0-cosine,5.0);
    vec3 specular=reflected*fresnel*uFloor.z;
    vec3 field=uFogLit==1?texture(uFogLight,clamp(fogCoordinate(vWorldPos+vec3(0,0.05,0))/vec3(1,1,uFogRange.z),
                                                   vec3(0.0),vec3(1.0))).rgb:vec3(0.0);
    vec3 colour=albedo*(uAmbient+field*uFloorTone.y)+specular;
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
FOG_SHAPE_GLSL = """
uniform sampler2D uEnvelope;  // rows: (lower, upper, presence), upper edge colour, lower edge colour
uniform vec2 uEnvelopeSpan;   // world x at u=0, 1/(world span)
uniform vec4 uFogForm;      // density, margin, edge softness, billow frequency
uniform vec4 uFogShape;       // start z, band depth, billow displacement, light decay
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
// Depth into the mist (world units): behind the start plane, and outside the clear band around the waveform's
// envelope unless beyond the band's depth. Billows displace the band's edge.
float fogInside(vec3 world, out vec4 band, out float above, out float below) {
    band=texture(uEnvelope,vec2((world.x-uEnvelopeSpan.x)*uEnvelopeSpan.y,0.5/3.0));
    above=world.y-band.y; below=band.x-world.y;
    float outside=max(above,below)-uFogForm.y+uFogShape.z*(fogBillow(world*uFogForm.w)-0.5);
    float behind=uFogShape.x-world.z+uFogShape.z*(fogBillow(world.zyx*uFogForm.w*0.8+vec3(5.3))-0.5)*1.5;
    return world.y<0.0?-1.0:min(behind,max(outside,behind-uFogShape.y));
}
"""

# The march's fine coverage: the same shape per sample, so the band's edge never stair-steps at the coarse cells.
FOG_COVERAGE_GLSL = FOG_SHAPE_GLSL + """
float fogCoverage(vec3 world, float coarse) {
    vec4 band; float above, below;
    return smoothstep(0.0,uFogForm.z,fogInside(world,band,above,below));
}
// Each lobe is lit from the waveform: mist above the band from below, mist below it from above, the far wall from
// the front. Shading toward clearer air pointed at the camera and left the lobes flat.
vec3 fogLightDirection(vec3 world) {
    vec4 band; float above, below;
    fogInside(world,band,above,below);
    return normalize(above>0.0?vec3(0.0,-1.0,0.35):below>0.0?vec3(0.0,1.0,0.35):vec3(0.0,0.0,1.0));
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
    float u=(world.x-uEnvelopeSpan.x)*uEnvelopeSpan.y;
    vec3 upperColour=texture(uEnvelope,vec2(u,1.5/3.0)).rgb;
    vec3 lowerColour=texture(uEnvelope,vec2(u,2.5/3.0)).rgb;
    // The nearest sheet edge lights the mist in its colour, by distance from the sheets (outside the envelope and
    // behind or before their depth): continuous, since the light lives on the coarse cells. The far wall behind
    // the band stays dark; light fades with depth into the mist, so rims glow and interiors stay dark.
    vec3 edge=above>0.0?upperColour:below>0.0?lowerColour
             :mix(lowerColour,upperColour,clamp(-below/max(band.y-band.x,1e-3),0.0,1.0));
    float dy=max(max(above,below),0.0);
    float dz=max(max(uFogRim.y-world.z,world.z-uFogRim.z),0.0);
    float rim=exp(-length(vec2(dy,dz))/uFogRim.x)*exp(-max(inside,0.0)*uFogShape.w);
    radiance=uFogLook.rgb+edge*uFogLook.w*rim;
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
        projection = fc.orthographic_matrix((tan[0]*distance, tan[1]*distance), .1, 200.)
    else:
        projection = fc.perspective_matrix(fc.viewport_tangents(pose.fov, aspect), .3, 200.)
    return view, np.asarray(projection).reshape(4, 4, order='F'), np.asarray(eye)


def waveform_envelope(packet, translation, age_fade, fog: Fog) -> np.ndarray:
    """Lower/upper sheet bounds and their colours along world x from the admitted ring packet (3 x samples x RGBA).

    Each ribbon's knots are monotone in x (the history flows along +x), so its centre height and half-width
    interpolate along x. Faded ends (head, tail) relax toward a closed band at the pivot so the mist closes in
    softly where no sheet is. A lab reduction; production would reduce the same packet on the GPU."""
    now, fade_in, lifetime, fade_out = age_fade
    x0, x1, samples = fog.envelope_range
    xs = np.linspace(x0, x1, int(samples))
    rows = np.frombuffer(packet.payload, np.float32).reshape(packet.instances, -1, 4)
    origin = np.asarray(packet.world_origin, float) + np.asarray(translation, float)
    lower, upper = np.full(xs.shape, np.inf), np.full(xs.shape, -np.inf)
    presence = np.zeros(xs.shape)
    sheets = []

    def smooth(x):
        x = np.clip(x, 0., 1.)
        return x*x*(3. - 2.*x)
    for path in rows:
        count, start, capacity = int(path[0, 0]), int(path[1, 1]), int(path[1, 2])
        knots = path[4:].reshape(-1, 4, 4)[(start + np.arange(count)) % capacity].astype(float)
        valid = knots[:, 1, 2] > .5
        knots = knots[valid]
        if len(knots) < 2:
            continue
        x = knots[:, 0, 0] + origin[0]
        order = np.argsort(x)
        x, knots = x[order], knots[order]
        age = now - (knots[:, 1, 0] + packet.coordinate_origin)
        fade = smooth(age/fade_in) if fade_in > 0 else np.ones_like(age)
        fade = fade*(smooth((lifetime - age)/fade_out) if fade_out > 0 else 1.)
        centre = np.interp(xs, x, knots[:, 0, 1] + origin[1], left=np.nan, right=np.nan)
        half = fog.envelope_width*np.interp(xs, x, knots[:, 0, 3])*np.interp(xs, x, fade, left=0., right=0.)
        light = np.interp(xs, x, knots[:, 3, 3]*fade, left=0., right=0.)
        colour = .5*(path[2, :3] + path[3, :3])
        here = ~np.isnan(centre)
        top, bottom = np.where(here, centre + half, -np.inf), np.where(here, centre - half, np.inf)
        sheets.append((top, bottom, colour*light[:, None]))
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
    table = np.zeros((3, xs.size, 4), np.float32)
    table[0, :, 0], table[0, :, 1], table[0, :, 2] = lower, upper, presence
    table[1, :, :3], table[2, :, :3] = upper_colour, lower_colour
    return table


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
    """Synthetic head: band-limited shape controls (Lab Plan section 4A); returns the ring and newest time."""
    s, flow = STATES[state], recipe.flow
    now = (knots-1)/flow.knot_hz if at is None else float(at)
    if not math.isfinite(now) or not (knots-1)/flow.knot_hz <= now <= 120.:
        raise ValueError('Lab sample time must contain warm history and stay within 120 seconds')
    ring = RibbonRing(len(PALETTE), colours=[(*a, 1.) for a, _ in PALETTE], edge_colours=[(*b, 1.) for _, b in PALETTE], period=.5)
    alpha = 1 - math.exp(-1/flow.knot_hz/flow.shape_tau)
    count = len(PALETTE)
    stages = [[0., 0.] for _ in range(count)]
    pivot_y = SPEC.pivot[1]
    t = 0.
    for i in range(math.floor(now*flow.knot_hz)+1):
        t = i/flow.knot_hz
        positions, widths, twists, light, sparkle = [], [], [], [], []
        for r in range(count):
            k = r - (count - 1)/2  # a fixed fan in height and depth, identical in low/high
            amplitude, width, frequency, offset, brightness = CHARACTER[r]
            phase = 2*math.pi*flow.head_hz*frequency*t + offset + flow.phase
            phase += flow.phase_swell*math.sin(.31*phase+r*.6)
            envelope = 1. + flow.amplitude_swell*math.sin(.23*phase+.4)
            section = 1. if math.sin(2*math.pi*.3*t + r*2.) > .2 else 0.
            stages[r][0] += (section - stages[r][0])*alpha
            stages[r][1] += (stages[r][0] - stages[r][1])*alpha
            swell = stages[r][1]
            deformation = s['deformation']*(.24*math.sin(2*phase+.7)+.18*math.sin(.61*phase+offset))
            positions.append((flow.speed*t, pivot_y + s['lift'] + s['amplitude']*amplitude*envelope*(math.sin(phase)+deformation)
                              + .5*k*s['spread']*math.cos(.37*phase), .65*k + flow.depth_sway*math.cos(phase*.55+r)))
            widths.append(width*(s['width'] + s['width_swell']*swell)*(1.0 + .2*math.sin(phase)))
            twists.append(s['twist']*(.7*math.sin(.48*phase+r*1.3)+.3*math.sin(.87*phase+.4)))
            light.append(brightness*s['emission']*(.85 + .3*swell))
            highs = .5 + .5*math.sin(2*math.pi*.53*t + r*1.7)  # synthetic highs: sparkle density
            sparkle.append(min(1., s['sparkle']*(.35 + .65*highs)))
        ring.append(t, positions, widths, twists, light, sparkle)
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
        self.reflected_march = FogMarch('waveform lab reflected mist', FOG_COVERAGE_GLSL)
        self.textures = {}

    def close(self):
        with self.target.current():
            if self.textures:
                gl.glDeleteTextures(len(self.textures), list(self.textures.values()))
                self.textures = {}
            self.reflection.release()
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

    def _render(self, state: str, *, flat: bool, pose: str, at: float | None) -> np.ndarray:
        recipe, (width, height) = self.recipe, self.size
        environment, flow = recipe.environment, recipe.flow
        ring, now = fill_ring(recipe, state, at=at)
        view, projection, eye = camera(POSES[pose], width/height)
        scroll = np.identity(4)
        scroll[0, 3] = flow.head_x - flow.speed*now
        mvp = (projection @ view).flatten(order='F')
        ribbon_view = view @ scroll
        ribbon_mvp = tuple((projection @ ribbon_view).flatten(order='F'))
        orthographic = POSES[pose].projection == 'Orthographic'
        draw = dict(view=tuple(ribbon_view.flatten(order='F')), material=recipe.material, orthographic=orthographic,
                    sweep_axis=(1.,0.,0.),
                    age_fade=(now, flow.fade_in, (ring.capacity - 1)/flow.knot_hz, flow.fade_out),
                    mist=environment.mist, mist_frame=(scroll[0, 3], 0., 0.))
        card = SimpleNamespace(viewport=(0, 0, width, height), logical_size=(float(width), float(height)),
                               matrix_values=(2/width, 0, 0, 0, 0, -2/height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                               quad_vao=self.target.vao)
        packet = ring.packet()
        envelope = None if flat or recipe.fog is None else waveform_envelope(packet, scroll[:3, 3], draw['age_fade'],
                                                                              recipe.fog)
        self.target.bind(clear=(0., 0., 0., 0.))
        fogged = not flat and recipe.fog is not None
        if fogged:
            camera_lens = lens(POSES[pose], width/height)
            self._update_fog(self.fog, view, camera_lens, (width, height), recipe.fog.cell, recipe.fog.slices, envelope)
            self._update_fog(self.reflected_fog, mirror_view(view, 0.), camera_lens, (width, height),
                             recipe.fog.reflection_cell, recipe.fog.reflection_slices, envelope)
            fog = recipe.fog
            march = dict(steps=fog.steps, max_extinction=fog.density, erosion=fog.erosion,
                         detail_frequency=fog.detail_frequency, shadow=fog.shadow, step=fog.step,
                         medium=self._fog_uniforms, shadow_floor=fog.shadow_floor)
            self.march.march(self.fog, size=(width*fog.march_scale, height*fog.march_scale), ground=0., **march)
            # The mirrored camera starts below the floor (no medium there) and sees the mist above it.
            self.reflected_march.march(self.reflected_fog, size=(width*fog.reflection_march_scale,
                                                                 height*fog.reflection_march_scale), **march)
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
                # With the volume, the march composite owns the floor's mist (in front of it, to the plane).
                self._floor(mvp, eye, view, orthographic, (width, height), flat=flat, mist_off=fogged)
                if flat:
                    self._flat_ribbons(packet, ribbon_mvp)
                if fogged:
                    self.march.composite(glow=recipe.fog.glow)
            if not flat:
                with self.scene.transparent_writes(card, self.resources):
                    self.ribbons.draw(packet, ribbon_mvp, shading='body', **draw)
                with self.scene.emission_writes():
                    gl.glEnablei(gl.GL_BLEND, 0)
                    gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
                    gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
                    gl.glDepthMask(gl.GL_FALSE)
                    self.ribbons.draw(packet, ribbon_mvp, shading='light', **draw)
                    self.ribbons.draw(packet, ribbon_mvp, shading='sparks', sparks=recipe.sparks, now=now,
                                      mist=draw['mist'], mist_frame=draw['mist_frame'], material=recipe.material,
                                      sweep_axis=draw['sweep_axis'])
                    gl.glDepthMask(gl.GL_TRUE)
                    gl.glDisablei(gl.GL_BLEND, 0)

    def _reflect(self, packet, projection, view, scroll, draw):
        """Ribbon light through the mirrored camera; the receiver is never drawn into its own reflection."""
        floor, (width, height) = self.recipe.floor, self.size
        mirrored = mirror_view(view, 0.)
        self.reflection.begin(int(width*floor.resolution), int(height*floor.resolution))
        try:
            gl.glDepthFunc(gl.GL_LESS)
            gl.glEnablei(gl.GL_BLEND, 0)
            gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
            gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)  # alpha: weighted height
            gl.glDepthMask(gl.GL_FALSE)
            if draw['mist'].get('uFogRange', (0., 0., 0., 0.))[3] > .5:
                # The mist's own light, mirrored (additive); alpha stays the emitters' weighted height.
                self.reflected_march.composite(additive=True)
            reflected_view = mirrored @ scroll
            reflected_mvp = tuple((projection @ reflected_view).flatten(order='F'))
            self.ribbons.draw(packet, reflected_mvp, shading='light', **{**draw, 'view': tuple(reflected_view.flatten(order='F'))})
            self.ribbons.draw(packet, reflected_mvp, shading='sparks', sparks=self.recipe.sparks, now=draw['age_fade'][0],
                              mist=draw['mist'], mist_frame=draw['mist_frame'], material=self.recipe.material,
                              sweep_axis=draw['sweep_axis'])
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
                 'uForward', 'uOrthographic', 'uMist', 'uMistShape', 'uFogVolume', 'uFogView', 'uFogLens', 'uFogRange')
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
        gl.glUniform4f(u['uReflectionLook'], 0., floor.lod[0], floor.lod[1], 0.)
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
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
        for unit in (0, 1, 2, 13):
            gl.glBindTextureUnit(unit, 0)

    def _flat_ribbons(self, packet, mvp):
        """Flat ribbon silhouettes in one known colour: rewrite every ribbon's colours in a copy of the packet."""
        data = np.frombuffer(packet.payload, np.float32).copy().reshape(packet.instances, -1, 4)
        data[:, 2] = data[:, 3] = (*FLAT['ribbon'], 1.)
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


def run(output: Path, cards: Path | None, *, board: str = 'primary') -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Refusing to overwrite evidence: {output}')
    output.mkdir(parents=True, exist_ok=True)
    if board not in ('primary','fog'):
        raise ValueError('Unknown reference board')
    width,height = (820,718) if board=='fog' else (640,709)
    recipe = Recipe()
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
    receipt = dict(stage='WR-04 floor, waveform and dense distance mist; navigation poses', board=board, card_size=(width,height),
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
    args = parser.parse_args()
    result = run(args.output, args.cards, board=args.board)
    print(json.dumps({state: {k: v for k, v in r.items() if k != 'rows'} for state, r in result['landmarks'].items()}, indent=2))
