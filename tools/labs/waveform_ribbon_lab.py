"""Waveform Ribbon scene lab: a world-first, navigable hall composed by hand over the shared primitives.

The world is authored in world units and viewed through the shared framed camera (``core.settings.framed_camera``)
with a lab-local spec; nothing is placed relative to the camera or the card. ``POSES['mock']`` reproduces the mock's
view for comparison; the other poses navigate the same world. No walls: a floor, staggered pillar rows receding from
the ribbon, and world-space mist (``rendering.gl_programs.mist``) that thickens beyond a corridor of clear air.

Ribbons are flowing history (Lab Plan section 4A): one ``RibbonRing`` fed by a labelled synthetic head (no music)
whose head and tail sit at fixed world x and fade by age. Two renders per state and pose:

- ``flat``: solid colours, no light, bloom or mist. At the mock pose the ribbon envelope and the first pillar row's
  floor contact are measured from its pixels against the WR-00 target table.
- ``lit``: ribbon material, emissive pillars, mist and bloom through the Visualizer-shaped scope.

The floor is the operator's matched PBR pack (albedo, normal, roughness) with the shared planar reflection
(S3D-5): pillars and ribbon light drawn through the mirrored camera, sampled at the floor's own screen position,
streaked and blurred by roughness and perturbed by the normal map. Missing until their step lands: particles (S3D-2).

    .venv\\Scripts\\python.exe tools/labs/waveform_ribbon_lab.py --output .artifacts/evidence/waveform_ribbon/<new-run>
        [--cards .artifacts/evidence/waveform_ribbon/wr00_reference_projection]
"""
from __future__ import annotations

import argparse
import io
import zipfile
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
from rendering.gl_programs.mist import MIST_GLSL, mist_uniforms
from rendering.gl_programs.reflection import PLANAR_REFLECTION_GLSL, mirror_view
from rendering.quick.scene3d.reflection import PlanarReflection
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.ribbon import RibbonMaterial, RibbonPrimitive, RibbonSparks
from rendering.quick.scene3d.target import SceneTarget
from tools.labs.render_target import OffscreenRenderTarget
from tools.labs.waveform_ribbon_targets import ENVELOPE, TRACED

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
class Hall:
    floor_x: float = 70.
    floor_z: tuple = (-60., 30.)
    # Pillar rows (depth, mean spacing, seed), authored in world units; spacing jitters deterministically.
    rows: tuple = ((-2.3, 1.9, 1), (-6.5, 3.4, 2), (-12., 4.6, 3), (-19., 5.8, 4))
    pillar_half: float = .12
    pillar_height: float = 14.
    pillar_light: float = 1.0
    pillar_colours: tuple = ((.2, .55, 1.), (.5, .35, 1.), (.25, .6, 1.), (.35, .45, 1.), (.2, .65, 1.), (.45, .5, 1.))
    floor_colour: tuple = (.018, .024, .045)
    backdrop: tuple = (.022, .036, .10)
    mist: dict = field(default_factory=lambda: mist_uniforms(centre_xz=(0., 6.), radii_xz=(30., 9.), falloff=.45, floor_thickening=1.2,
                                                             thickening_height=1.2, low_glow=5.))


@dataclass(frozen=True)
class Floor:
    pack: str = 'assets/textures/Dark_Concrete_PBR_Matched_Set_DarkGrey.zip'  # operator's local matched set
    tile: float = 3.5               # world units per texture repeat
    ambient: tuple = (.20, .24, .52)  # cool blue-violet hall light on the bare concrete
    reflection: float = 2.6         # wet film: reflection strength before Fresnel
    f0: float = .04
    normal_shift: float = .012      # screen-uv shift of the reflection lookup per unit normal tilt
    streak: float = .14             # vertical reflection streak (uv) at roughness 1
    lod: tuple = (0., 2.2)          # reflection mip at roughness 0 and 1 (half-resolution target)
    resolution: float = .5          # reflection target size relative to the view
    diffuse: float = 9.             # light from the glowing scene above, on the albedo
    diffuse_lod: float = 5.5        # mip of the reflection used as that light (wide)


@dataclass(frozen=True)
class Flow:  # Lab Plan section 4A: history enters at the head (world +x) and drifts toward the tail
    speed: float = 1.6
    head_hz: float = .4
    knot_hz: float = 6.
    shape_tau: float = .45          # per smoothing stage of history-carried shape controls
    head_x: float = 34.
    fade_in: float = 2.5            # seconds of age over which the head fades in
    fade_out: float = 5.            # seconds of age over which the tail fades out


PALETTE = (((.0, .75, 1.), (.05, .45, 1.)),   # electric cyan -> blue (mock: saturated, blue-dominant)
           ((.15, .2, 1.), (.45, .12, 1.)),    # blue -> violet
           ((.5, .1, 1.), (.95, .1, .8)),      # violet -> magenta
           ((.05, .4, 1.), (.3, .25, 1.)),     # deep blue
           ((.35, .15, 1.), (.75, .2, 1.)))    # violet
# Per-ribbon character (amplitude, width, wave frequency, phase, light): identical sheets on even phases braid into a
# regular lattice and sum to white; the mock's sheets differ and cross irregularly.
CHARACTER = ((1.0, 1.0, 1.0, 0.0, 1.0), (.7, .6, 1.13, 2.1, .8), (1.15, 1.2, .9, 4.0, 1.0), (.55, .45, 1.22, 1.2, .7),
             (.85, .8, .95, 5.3, .85))
STATES = {  # labelled synthetic controls sized from the WR-00 target table; not music
    'low': dict(width=.11, width_swell=.04, twist=1.1, emission=.42, spread=.32, amplitude=.55, lift=0., sparkle=.18),
    'high': dict(width=.32, width_swell=.12, twist=2.4, emission=.4, spread=1.1, amplitude=.85, lift=.5, sparkle=.85),
}


@dataclass(frozen=True)
class Recipe:
    hall: Hall = field(default_factory=Hall)
    floor: Floor = field(default_factory=Floor)
    flow: Flow = field(default_factory=Flow)
    # Mock-directed look (WR-04): saturated darker body, thin near-white irregular strands and rims, visible glints.
    material: RibbonMaterial = field(default_factory=lambda: RibbonMaterial(
        strands=16., strand_half_width=.06, strand_light=2.4, strand_white=.25, strand_jitter=.6, strand_warp=.1,
        rim_light=1.6, rim_white=.35, rim_half_width=.015, fill_light=.2, fill_centre=.5, rim_glow_light=.15,
        rim_glow_width=.05, body_alpha=.05, body_tint=.5, glint_density=1.4, glint_chance=.18, glint_light=7.,
        glint_radius=.35, glint_min_pixels=1.3))
    sparks: RibbonSparks = field(default_factory=lambda: RibbonSparks(per_knot=16, lifetime=4.5, drift=1.2, rise=.4,
                                                                       smallest=1.6, largest=5., light=16., white=.25))
    bloom: float = .32
    exposure: float = 1.


HALL_VERTEX = """#version 460 core
layout(location=0) in vec3 aPosition;
layout(location=1) in vec4 aColour;   // rgb, emission (pillars)
layout(location=2) in vec3 aLocal;    // across (-1..1), height (world), pillar seed
uniform mat4 uMvp;
out vec3 vWorldPos;
out vec4 vColour;
out vec2 vLocal;
// Flat: a per-pillar constant hashed through a large sine must not be interpolated. Perspective-correct interpolation
// reproduces a "constant" only to ~1e-7 relative, and the hash amplified that into per-row banding of the glow.
flat out float vSeed;
void main() { vWorldPos=aPosition; vColour=aColour; vLocal=aLocal.xy; vSeed=aLocal.z; gl_Position=uMvp*vec4(aPosition,1.0); }
"""
HALL_FRAGMENT = """#version 460 core
in vec3 vWorldPos;
in vec4 vColour;
in vec2 vLocal;
flat in float vSeed;
uniform int uFlat;
uniform vec3 uBackdrop;
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
""" + MIST_GLSL + """
void main() {
    if(uFlat==1) { FragColor=vec4(vColour.rgb,1.0); Emission=vec4(0.0); return; }
    vec3 colour=vColour.rgb;
    vec3 light=vec3(0.0);
    if(vColour.a>0.0) {
        // A light pillar: mostly dim haze, two localized bright segments at seeded heights, and a bright pool where
        // it meets the floor. Uniform full-height tubes read as neon signage.
        // Clamped: MSAA shades sliver faces (seen edge-on) at pixel centres outside the triangle, where the across
        // coordinate extrapolates and the profile collapsed on alternate rows (banded pillars in Perspective).
        float core=exp(-pow(clamp(vLocal.x,-1.0,1.0)*1.1,2.0));
        float height=vLocal.y, seed=vSeed;
        float h1=1.6+2.6*fract(sin(seed*91.7)*4375.85), h2=3.8+3.0*fract(sin(seed*37.1)*9123.17);
        float segments=exp(-pow((height-h1)/0.45,2.0))+0.7*exp(-pow((height-h2)/0.7,2.0));
        float profile=0.025+segments+1.4*exp(-height*2.4);
        float bright=0.12+0.88*pow(fract(sin(seed*17.13)*29871.7),2.0);  // most pillars dim, a few bright
        light=mix(colour,vec3(1.0),0.12*core*core)*vColour.a*bright*core*profile*smoothstep(0.0,0.05,height);
        // A column of light, not a dark solid: its body takes the mist behind it, so only its light shows
        // (black bodies read as dark bars against the lit haze).
        colour=mistColour(uBackdrop,vWorldPos);
    }
    float clear=mistTransmittance(vWorldPos);
    vec3 shaded=mix(mistColour(uBackdrop,vWorldPos),colour,clear)+light*clear;
    FragColor=vec4(shaded,1.0);
    Emission=vec4(light*clear,dot(light*clear,vec3(0.2126,0.7152,0.0722)));
}
"""
FLOOR_VERTEX = """#version 460 core
layout(location=0) in vec3 aPosition;
uniform mat4 uMvp;
out vec3 vWorldPos;
void main() { vWorldPos=aPosition; gl_Position=uMvp*vec4(aPosition,1.0); }
"""
FLOOR_FRAGMENT = """#version 460 core
in vec3 vWorldPos;
uniform sampler2D uAlbedo;
uniform sampler2D uNormal;
uniform sampler2D uRoughness;
uniform vec2 uViewport;
uniform vec3 uBackdrop;
uniform vec3 uAmbient;
uniform vec4 uFloor;        // tile, reflection strength, f0, normal shift
uniform vec2 uFloorLight;   // diffuse gain, diffuse mip: the glowing scene above lights the concrete
uniform vec3 uEye;
uniform vec3 uForward;
uniform int uOrthographic;
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
""" + MIST_GLSL + PLANAR_REFLECTION_GLSL + """
void main() {
    vec2 uv=vWorldPos.xz/uFloor.x;
    vec3 albedo=texture(uAlbedo,uv).rgb;                 // sRGB texture: already linear here
    vec3 tangent=texture(uNormal,uv).rgb*2.0-1.0;         // OpenGL convention: +y up the texture (world -z)
    vec3 normal=normalize(vec3(tangent.x,tangent.z,-tangent.y));
    float roughness=texture(uRoughness,uv).r;
    vec3 view=uOrthographic==1?normalize(uForward):normalize(vWorldPos-uEye);
    float cosine=clamp(abs(dot(normal,view)),0.0,1.0);
    float fresnel=uFloor.z+(1.0-uFloor.z)*pow(1.0-cosine,5.0);
    vec3 reflected=planarReflection(gl_FragCoord.xy/uViewport,tangent.xy*uFloor.w,roughness);
    // Diffuse light from the emissive ribbons and pillars above: the mirrored scene's widest blur approximates the
    // light arriving over the floor (a mirror alone left the concrete dark between reflections).
    vec3 above=textureLod(uReflection,gl_FragCoord.xy/uViewport,uFloorLight.y).rgb;
    vec3 light=reflected*fresnel*uFloor.y*(1.0-0.45*roughness)+albedo*above*uFloorLight.x;
    float clear=mistTransmittance(vWorldPos);
    vec3 colour=mix(mistColour(uBackdrop,vWorldPos),albedo*uAmbient,clear)+light*clear;
    FragColor=vec4(colour,1.0);
    Emission=vec4(light*clear,dot(light*clear,vec3(0.2126,0.7152,0.0722)));
}
"""
FLAT = {'floor': (.25, .25, .25), 'pillar': (.6, .6, .1), 'front_pillar': (.1, .6, .6), 'ribbon': (1., 0., 1.)}


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


def pillar_positions(hall: Hall):
    """World pillars: (x, z, row, seed). Spacing jitters by a fixed hash per row, never by the view."""
    out = []
    for row, (z, spacing, seed) in enumerate(hall.rows):
        x, k = -hall.floor_x, 0
        while x < hall.floor_x:
            jitter = math.sin(seed*12.9898 + k*78.233)*43758.5453 % 1.
            x += spacing*(.55 + .9*jitter)
            k += 1
            if abs(x) < hall.floor_x:
                out.append((x, z, row, seed*100 + k))
    return out


def floor_vertices(hall: Hall) -> bytes:
    (z0, z1), fx = hall.floor_z, hall.floor_x
    corners = ((-fx, 0., z0), (fx, 0., z0), (fx, 0., z1), (-fx, 0., z0), (fx, 0., z1), (-fx, 0., z1))
    return b''.join(struct.pack('3f', *c) for c in corners)


def load_floor_textures(floor: Floor) -> dict:
    """The matched pack's maps as mipmapped, repeating GL textures (albedo sRGB, normal and roughness linear)."""
    from PIL import Image as PILImage
    textures = {}
    with zipfile.ZipFile(ROOT/floor.pack) as pack:
        members = {name.rsplit('_', 1)[-1].split('.')[0].lower(): name for name in pack.namelist() if name.endswith('.png')}
        for key, member, internal in (('albedo', members['albedo'], gl.GL_SRGB8_ALPHA8),
                                      ('normal', members['opengl'], gl.GL_RGBA8),
                                      ('roughness', members['roughness'], gl.GL_RGBA8)):
            image = PILImage.open(io.BytesIO(pack.read(member))).convert('RGBA')
            data = np.asarray(image, np.uint8)
            name = (gl.GLuint*1)()
            gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
            texture = int(name[0])
            gl.glTextureStorage2D(texture, max(image.size).bit_length(), internal, *image.size)
            gl.glTextureSubImage2D(texture, 0, 0, 0, *image.size, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, data)
            gl.glGenerateTextureMipmap(texture)
            gl.glTextureParameteri(texture, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
            gl.glTextureParameteri(texture, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTextureParameterf(texture, 0x84FE, 8.)  # GL_TEXTURE_MAX_ANISOTROPY: the floor is seen at a glancing angle
            for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
                gl.glTextureParameteri(texture, wrap, gl.GL_REPEAT)
            textures[key] = texture
    return textures


def hall_vertices(hall: Hall, flat: bool, *, include_floor: bool = True) -> bytes:
    """Pillar prisms (and the flat floor) as one static triangle list: position, colour+emission, local."""
    rows = []

    def quad(corners, colour, emission, locals_):
        for i in (0, 1, 2, 0, 2, 3):
            rows.append((*corners[i], *colour, emission, *locals_[i]))
    zero = ((0., 0., 0.),)*4
    (z0, z1), fx = hall.floor_z, hall.floor_x
    if include_floor:
        quad(((-fx, 0., z0), (fx, 0., z0), (fx, 0., z1), (-fx, 0., z1)), FLAT['floor'] if flat else hall.floor_colour, 0., zero)
    h, w = hall.pillar_height, hall.pillar_half
    for x, z, row, seed in pillar_positions(hall):
        colour = (FLAT['front_pillar'] if row == 0 else FLAT['pillar']) if flat else \
            hall.pillar_colours[int(seed) % len(hall.pillar_colours)]
        light = 0. if flat else hall.pillar_light
        for (ax, az), (bx, bz) in (((-w, w), (w, w)), ((w, w), (w, -w)), ((w, -w), (-w, -w)), ((-w, -w), (-w, w))):
            quad(((x + ax, 0., z + az), (x + ax, h, z + az), (x + bx, h, z + bz), (x + bx, 0., z + bz)), colour, light,
                 ((-1., 0., seed), (-1., h, seed), (1., h, seed), (1., 0., seed)))
    return b''.join(struct.pack('10f', *row) for row in rows)


def fill_ring(recipe: Recipe, state: str, knots: int = 256) -> tuple[RibbonRing, float]:
    """Synthetic head: band-limited shape controls (Lab Plan section 4A); returns the ring and newest time."""
    s, flow = STATES[state], recipe.flow
    ring = RibbonRing(len(PALETTE), colours=[(*a, 1.) for a, _ in PALETTE], edge_colours=[(*b, 1.) for _, b in PALETTE], period=.5)
    alpha = 1 - math.exp(-1/flow.knot_hz/flow.shape_tau)
    count = len(PALETTE)
    stages = [[0., 0.] for _ in range(count)]
    pivot_y = SPEC.pivot[1]
    t = 0.
    for i in range(knots):
        t = i/flow.knot_hz
        positions, widths, twists, light, sparkle = [], [], [], [], []
        for r in range(count):
            k = r - (count - 1)/2  # -2..2: a fan in height and depth
            amplitude, width, frequency, offset, brightness = CHARACTER[r]
            phase = 2*math.pi*flow.head_hz*frequency*t + offset
            section = 1. if math.sin(2*math.pi*.3*t + r*2.) > .2 else 0.
            stages[r][0] += (section - stages[r][0])*alpha
            stages[r][1] += (stages[r][0] - stages[r][1])*alpha
            swell = stages[r][1]
            positions.append((flow.speed*t, pivot_y + s['lift'] + s['amplitude']*amplitude*math.sin(phase)
                              + .5*k*s['spread']*math.cos(.37*phase), .3*k + .35*math.cos(phase*.8)))
            widths.append(width*(s['width'] + s['width_swell']*swell))
            twists.append(s['twist']*math.sin(2*math.pi*.07*t + r*2.))
            light.append(brightness*s['emission']*(.85 + .3*swell))
            highs = .5 + .5*math.sin(2*math.pi*.53*t + r*1.7)  # synthetic highs: sparkle density
            sparkle.append(min(1., s['sparkle']*(.35 + .65*highs)))
        ring.append(t, positions, widths, twists, light, sparkle)
    return ring, t


class Lab:
    """Owns the diagnostic target and lab GL resources; `close()` retires them under the target's context."""

    def __init__(self, recipe: Recipe, size: tuple[int, int]):
        self.recipe, self.size = recipe, size
        self.target = OffscreenRenderTarget(*size)
        self.resources, self.scene, self.ribbons = MeshResources('waveform lab'), SceneTarget('waveform lab'), RibbonPrimitive()
        self.reflection = PlanarReflection('waveform lab floor')
        self.textures = {}

    def close(self):
        with self.target.current():
            if self.textures:
                gl.glDeleteTextures(len(self.textures), list(self.textures.values()))
                self.textures = {}
            self.reflection.release()
            self.ribbons.release()
            self.scene.release()
            self.resources.release_resources()
        self.target.close()

    def render(self, state: str, *, flat: bool, pose: str = 'mock') -> np.ndarray:
        recipe, (width, height) = self.recipe, self.size
        hall, flow = recipe.hall, recipe.flow
        ring, now = fill_ring(recipe, state)
        view, projection, eye = camera(POSES[pose], width/height)
        scroll = np.identity(4)
        scroll[0, 3] = flow.head_x - flow.speed*now  # the flow frame's knot at time t sits at head_x - speed*(now - t)
        hall_mvp = (projection @ view).flatten(order='F')
        ribbon_view = view @ scroll
        ribbon_mvp = tuple((projection @ ribbon_view).flatten(order='F'))
        key = 'hall_flat' if flat else 'pillars'
        vao, count = self.resources.mesh(key, hall_vertices(hall, flat, include_floor=flat), (3, 4, 3))
        program = self.resources.program('hall', HALL_VERTEX, HALL_FRAGMENT)
        uniforms = self.resources.uniforms('hall', ('uMvp', 'uFlat', 'uBackdrop', 'uMist', 'uMistShape'), required=False)
        orthographic = POSES[pose].projection == 'Orthographic'
        draw = dict(view=tuple(ribbon_view.flatten(order='F')), material=recipe.material, orthographic=orthographic,
                    age_fade=(now, flow.fade_in, (ring.capacity - 1)/flow.knot_hz, flow.fade_out),
                    mist=hall.mist, mist_frame=(scroll[0, 3], 0., 0.))
        card = SimpleNamespace(viewport=(0, 0, width, height), logical_size=(float(width), float(height)),
                               matrix_values=(2/width, 0, 0, 0, 0, -2/height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                               quad_vao=self.target.vao)
        packet = ring.packet()
        self.target.bind(clear=(0., 0., 0., 0.))
        if not flat:
            self._reflect(packet, projection, view, scroll, program, uniforms, vao, count, draw)
        with self.scene.scope(card, 4, self.resources, overlay=1.0, bloom=0. if flat else recipe.bloom,
                              oit=True, hdr=None if flat or not recipe.bloom else recipe.exposure):
            gl.glViewport(0, 0, width, height)
            gl.glClearBufferfv(gl.GL_COLOR, 0, (*hall.backdrop, 1.))
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthFunc(gl.GL_LESS)
            gl.glDepthMask(gl.GL_TRUE)
            with self.scene.emission_writes():
                gl.glUseProgram(program)
                gl.glUniformMatrix4fv(uniforms['uMvp'], 1, gl.GL_FALSE, np.asarray(hall_mvp, np.float32))
                gl.glUniform1i(uniforms['uFlat'], int(flat))
                gl.glUniform3f(uniforms['uBackdrop'], *hall.backdrop)
                gl.glUniform4f(uniforms['uMist'], *hall.mist['uMist'])
                gl.glUniform4f(uniforms['uMistShape'], *hall.mist['uMistShape'])
                gl.glBindVertexArray(vao)
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
                if flat:
                    self._flat_ribbons(packet, ribbon_mvp)
                else:
                    self._floor(hall_mvp, eye, view, orthographic, (width, height))
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
                                      mist=hall.mist, mist_frame=draw['mist_frame'])
                    gl.glDepthMask(gl.GL_TRUE)
                    gl.glDisablei(gl.GL_BLEND, 0)
        return self.target.read_rgba()

    def _reflect(self, packet, projection, view, scroll, program, uniforms, vao, count, draw):
        """Pillars and ribbon light through the mirrored camera (the floor, the receiver, is not drawn)."""
        floor, (width, height) = self.recipe.floor, self.size
        mirrored = mirror_view(view, 0.)
        self.reflection.begin(int(width*floor.resolution), int(height*floor.resolution))
        try:
            gl.glDepthFunc(gl.GL_LESS)
            gl.glUseProgram(program)
            gl.glUniformMatrix4fv(uniforms['uMvp'], 1, gl.GL_FALSE, np.asarray((projection @ mirrored).flatten(order='F'), np.float32))
            gl.glUniform1i(uniforms['uFlat'], 0)
            gl.glUniform3f(uniforms['uBackdrop'], 0., 0., 0.)  # mist dims reflected light toward no light
            gl.glUniform4f(uniforms['uMist'], *self.recipe.hall.mist['uMist'])
            gl.glUniform4f(uniforms['uMistShape'], *self.recipe.hall.mist['uMistShape'])
            gl.glBindVertexArray(vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
            gl.glEnablei(gl.GL_BLEND, 0)
            gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
            gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
            gl.glDepthMask(gl.GL_FALSE)
            reflected_view = mirrored @ scroll
            reflected_mvp = tuple((projection @ reflected_view).flatten(order='F'))
            self.ribbons.draw(packet, reflected_mvp, shading='light', **{**draw, 'view': tuple(reflected_view.flatten(order='F'))})
            self.ribbons.draw(packet, reflected_mvp, shading='sparks', sparks=self.recipe.sparks, now=draw['age_fade'][0],
                              mist=draw['mist'], mist_frame=draw['mist_frame'])
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDisablei(gl.GL_BLEND, 0)
        finally:
            self.reflection.end()

    def _floor(self, mvp, eye, view, orthographic, size):
        recipe = self.recipe
        floor, hall = recipe.floor, recipe.hall
        if not self.textures:
            self.textures = load_floor_textures(floor)
        vao, count = self.resources.mesh('floor', floor_vertices(hall), (3,))
        program = self.resources.program('floor', FLOOR_VERTEX, FLOOR_FRAGMENT)
        names = ('uMvp', 'uAlbedo', 'uNormal', 'uRoughness', 'uReflection', 'uReflectionLook', 'uViewport', 'uBackdrop',
                 'uAmbient', 'uFloor', 'uFloorLight', 'uEye', 'uForward', 'uOrthographic', 'uMist', 'uMistShape')
        u = self.resources.uniforms('floor', names, required=False)
        gl.glUseProgram(program)
        gl.glUniformMatrix4fv(u['uMvp'], 1, gl.GL_FALSE, np.asarray(mvp, np.float32))
        for unit, (name, texture) in enumerate((('uAlbedo', self.textures['albedo']), ('uNormal', self.textures['normal']),
                                                ('uRoughness', self.textures['roughness']),
                                                ('uReflection', self.reflection.texture))):
            gl.glBindTextureUnit(unit, texture)
            gl.glUniform1i(u[name], unit)
        gl.glUniform4f(u['uReflectionLook'], floor.streak, floor.lod[0], floor.lod[1], 0.)
        gl.glUniform2f(u['uViewport'], *size)
        gl.glUniform3f(u['uBackdrop'], *hall.backdrop)
        gl.glUniform3f(u['uAmbient'], *floor.ambient)
        gl.glUniform4f(u['uFloor'], floor.tile, floor.reflection, floor.f0, floor.normal_shift)
        gl.glUniform2f(u['uFloorLight'], floor.diffuse, floor.diffuse_lod)
        gl.glUniform3f(u['uEye'], *eye)
        gl.glUniform3f(u['uForward'], *(-view[2, :3]))
        gl.glUniform1i(u['uOrthographic'], int(orthographic))
        gl.glUniform4f(u['uMist'], *hall.mist['uMist'])
        gl.glUniform4f(u['uMistShape'], *hall.mist['uMistShape'])
        gl.glBindVertexArray(vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
        for unit in range(4):
            gl.glBindTextureUnit(unit, 0)

    def _flat_ribbons(self, packet, mvp):
        """Flat ribbon silhouettes in one known colour: rewrite every ribbon's colours in a copy of the packet."""
        data = np.frombuffer(packet.payload, np.float32).copy().reshape(packet.instances, -1, 4)
        data[:, 2] = data[:, 3] = (*FLAT['ribbon'], 1.)
        flat = type(packet)(data.tobytes(), packet.instances, packet.vertices, packet.world_origin, packet.coordinate_origin)
        self.ribbons.draw(flat, mvp)


def measure_flat(pixels: np.ndarray) -> dict:
    """Ribbon envelope and the front pillar row's floor contact from a flat mock-pose render, as panel fractions."""
    height, width = pixels.shape[:2]
    rgb = pixels[:, :, :3].astype(int)
    ribbon = (rgb[:, :, 0] > 120) & (rgb[:, :, 2] > 120) & (rgb[:, :, 1] < 60)  # FLAT['ribbon'] magenta
    envelope = {}
    for x in ENVELOPE['low']:
        column = np.where(ribbon[:, min(x, width - 1)])[0]
        envelope[str(x)] = [float(column.min()/height), float(column.max()/height)] if column.size else None
    front = (np.abs(rgb - np.array(FLAT['front_pillar'])*255).max(2) <= 6)
    rows = np.where(front.any(1))[0]
    return dict(envelope=envelope, floor_top=float((rows.max() + 1)/height) if rows.size else None)


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
                floor=dict(lab=measured['floor_top'], target=TRACED['floor_contact_y'][state]/height),
                lab_envelope=[min(v[0] for v in present), max(v[1] for v in present)] if present else None,
                target_envelope=[min(t for t, _ in target.values()), max(b for _, b in target.values())])


def overlay(image: Image.Image, state: str) -> Image.Image:
    """Target landmarks over an image: traced envelope (yellow), floor contact (orange)."""
    sheet = image.convert('RGB').resize((640, 709))
    draw = ImageDraw.Draw(sheet)
    xs = sorted(ENVELOPE[state])
    for edge in (0, 1):
        draw.line([(x, ENVELOPE[state][x][edge]) for x in xs], fill=(255, 230, 0), width=1)
    floor = TRACED['floor_contact_y'][state]
    draw.line([(0, floor), (640, floor)], fill=(255, 140, 0))
    return sheet


def run(output: Path, cards: Path | None) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Refusing to overwrite evidence: {output}')
    output.mkdir(parents=True, exist_ok=True)
    recipe = Recipe()
    report, images = {}, {}
    lab = Lab(recipe, (640, 709))
    try:
        for state in STATES:
            flat = lab.render(state, flat=True)
            lit = lab.render(state, flat=False)
            images[state] = (Image.fromarray(flat), Image.fromarray(lit))
            Image.fromarray(flat).save(output/f'flat_{state}.png')
            Image.fromarray(lit).save(output/f'lit_{state}.png')
            report[state] = landmark_report(measure_flat(flat), state)
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
        sheet = Image.new('RGB', (640*3 + 16, 709*2 + 8))
        for row, state in enumerate(STATES):
            sheet.paste(overlay(Image.open(cards/f'{state}.png'), state), (0, row*717))
            sheet.paste(overlay(images[state][0], state), (648, row*717))
            sheet.paste(images[state][1].convert('RGB'), (1296, row*717))
        sheet.save(output/'mock_flat_lit.png')
    poses = Image.new('RGB', (640*len(POSES), 360*2))
    for row, state in enumerate(STATES):
        for column, pose in enumerate(POSES):
            poses.paste(Image.open(output/f'wide_{state}_{pose}.png').convert('RGB').resize((640, 360)), (column*640, row*360))
    poses.save(output/'navigation_poses.png')
    receipt = dict(stage='WR-05 world-first hall with PBR floor and planar reflection, world mist, navigation poses',
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
    args = parser.parse_args()
    result = run(args.output, args.cards)
    print(json.dumps({state: {k: v for k, v in r.items() if k != 'rows'} for state, r in result['landmarks'].items()}, indent=2))
