"""Waveform Ribbon scene lab: world-first floor, waveform and distance mist over shared primitives.

The world is authored in world units and viewed through the shared framed camera (``core.settings.framed_camera``)
with a lab-local spec; nothing is placed relative to the camera or the card. ``POSES['mock']`` reproduces the mock's
view for comparison; the other poses navigate the same world. No walls or pillars: the floor disappears into mist
beyond a corridor of clear air. Volumetric clearance and illumination follow the live Lab Plan.

Ribbons are flowing history (Lab Plan section 4A): one ``RibbonRing`` fed by a labelled synthetic head (no music)
whose head and tail sit at fixed world x and fade by age. Two renders per state and pose:

- ``flat``: solid colours, no light, bloom or mist; ribbon envelopes measured against the WR-00 target table.
- ``lit``: ribbon material, wet floor, mist and bloom through the Visualizer-shaped scope.

The floor uses a saved generated concrete albedo with a restrained derived micro-surface and the shared planar reflection
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
from rendering.gl_programs.mist import MIST_GLSL, mist_uniforms
from rendering.gl_programs.reflection import PLANAR_REFLECTION_GLSL, mirror_view
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
class Floor:
    half_span: float = 100.
    depth_bounds: tuple = (-80., 60.)
    albedo: str = 'assets/textures/waveform_floor/concrete_albedo.png'
    roughness: str = 'assets/textures/waveform_floor/concrete_roughness.png'
    tile: float = 12.               # broad world-space patch, blended at a second incommensurate orientation/scale
    ambient: tuple = (.6, .75, 1.1)
    reflection: float = 1.8         # wet film: reflection strength before Fresnel
    f0: float = .04
    normal_shift: float = .025      # screen-uv shift of the reflection lookup per unit normal tilt
    streak: float = .22             # vertical reflection streak (uv) at roughness 1
    lod: tuple = (1., 6.)           # blur footprint covers the streak taps, avoiding repeated reflection bands
    surface: tuple = (.06, .12, .65, .7)  # dry bump (world), wet/dry optical roughness, wet albedo gain
    resolution: float = .5          # reflection target size relative to the view
    diffuse: float = 3.             # light from the glowing scene above, on the albedo
    diffuse_lod: float = 5.5        # mip of the reflection used as that light (wide)


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
uniform sampler2D uRoughness;
uniform int uFlat;
uniform vec2 uViewport;
uniform vec3 uBackdrop;
uniform vec3 uAmbient;
uniform vec4 uFloor;        // tile, reflection strength, f0, normal shift
uniform vec2 uFloorLight;   // diffuse gain, diffuse mip
uniform vec4 uSurface;      // dry micro-height scale (world), wet/dry optical roughness, wet albedo gain
uniform vec3 uEye;
uniform vec3 uForward;
uniform int uOrthographic;
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
""" + MIST_GLSL + PLANAR_REFLECTION_GLSL + """
void main() {
    if(uFlat==1) { FragColor=vec4(vec3(0.25),1.0); Emission=vec4(0.0); return; }
    vec2 uv=vWorldPos.xz/uFloor.x;
    // Same saved scan in two world-fixed, differently scaled orientations: no recognisable tile lattice.
    // No lighting/reflections are baked into this asset. sRGB reads decode the base colour into linear light.
    vec2 other=mat2(0.6,-0.8,0.8,0.6)*uv*1.37+vec2(.31,.47);
    vec3 albedo=mix(texture(uAlbedo,uv).rgb,texture(uAlbedo,other).rgb,.4);
    float mask=mix(texture(uRoughness,uv*3.1).r,texture(uRoughness,other*3.1).r,.4);
    float wet=1.0-smoothstep(.22,.45,mask);
    float stone=dot(sqrt(max(albedo,vec3(0.0))),vec3(.2126,.7152,.0722));
    // A small authored micro-height from the same grain; screen derivatives include both UV fields and mips.
    float bump=uSurface.x*mix(1.0,.05,wet);
    vec3 dx=dFdx(vWorldPos)+vec3(0,bump*dFdx(stone),0);
    vec3 dy=dFdy(vWorldPos)+vec3(0,bump*dFdy(stone),0);
    vec3 normal=normalize(cross(dx,dy));
    if(normal.y<0.0) normal=-normal;
    float roughness=mix(uSurface.z,uSurface.y,wet);
    albedo*=uSurface.w;
    vec3 view=uOrthographic==1?normalize(uForward):normalize(vWorldPos-uEye);
    float cosine=clamp(abs(dot(normal,view)),0.0,1.0);
    float fresnel=uFloor.z+(1.0-uFloor.z)*pow(1.0-cosine,5.0);
    vec3 reflected=planarReflection(gl_FragCoord.xy/uViewport,vec2(normal.x,-normal.z)*uFloor.w,roughness);
    // Diffuse light from the emissive ribbons above: the mirrored scene's widest blur approximates the
    // light arriving over the floor (a mirror alone left the concrete dark between reflections).
    vec3 above=textureLod(uReflection,gl_FragCoord.xy/uViewport,uFloorLight.y).rgb;
    vec3 specular=reflected*fresnel*uFloor.y*mix(.12,1.0,wet);
    vec3 light=specular+albedo*above*uFloorLight.x;
    float clear=mistTransmittance(vWorldPos);
    vec3 colour=mix(mistColour(uBackdrop,vWorldPos),albedo*uAmbient,clear)+light*clear;
    FragColor=vec4(colour,1.0);
    Emission=vec4(specular*clear,dot(specular*clear,vec3(0.2126,0.7152,0.0722)));
}
"""
FLAT = {'ribbon': (1., 0., 1.)}


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


def floor_vertices(floor: Floor) -> bytes:
    (z0, z1), fx = floor.depth_bounds, floor.half_span
    corners = ((-fx, 0., z0), (fx, 0., z0), (fx, 0., z1), (-fx, 0., z0), (fx, 0., z1), (-fx, 0., z1))
    return b''.join(struct.pack('3f', *c) for c in corners)


def load_floor_textures(floor: Floor) -> dict:
    """Saved generated maps: colour decoded from sRGB, roughness sampled as linear data. Missing assets fail."""
    textures={}
    try:
        for key,path,storage in (('albedo',floor.albedo,gl.GL_SRGB8_ALPHA8),('roughness',floor.roughness,gl.GL_RGBA8)):
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
        self.target.bind(clear=(0., 0., 0., 0.))
        if not flat:
            self._reflect(packet, projection, view, scroll, draw)
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
                self._floor(mvp, eye, view, orthographic, (width, height), flat=flat)
                if flat:
                    self._flat_ribbons(packet, ribbon_mvp)
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
                                      mist=environment.mist, mist_frame=draw['mist_frame'], material=recipe.material,
                                      sweep_axis=draw['sweep_axis'])
                    gl.glDepthMask(gl.GL_TRUE)
                    gl.glDisablei(gl.GL_BLEND, 0)
        return self.target.read_rgba()

    def _reflect(self, packet, projection, view, scroll, draw):
        """Ribbon light through the mirrored camera; the receiver is never drawn into its own reflection."""
        floor, (width, height) = self.recipe.floor, self.size
        mirrored = mirror_view(view, 0.)
        self.reflection.begin(int(width*floor.resolution), int(height*floor.resolution))
        try:
            gl.glDepthFunc(gl.GL_LESS)
            gl.glEnablei(gl.GL_BLEND, 0)
            gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
            gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
            gl.glDepthMask(gl.GL_FALSE)
            reflected_view = mirrored @ scroll
            reflected_mvp = tuple((projection @ reflected_view).flatten(order='F'))
            self.ribbons.draw(packet, reflected_mvp, shading='light', **{**draw, 'view': tuple(reflected_view.flatten(order='F'))})
            self.ribbons.draw(packet, reflected_mvp, shading='sparks', sparks=self.recipe.sparks, now=draw['age_fade'][0],
                              mist=draw['mist'], mist_frame=draw['mist_frame'], material=self.recipe.material,
                              sweep_axis=draw['sweep_axis'])
        finally:
            gl.glDisablei(gl.GL_BLEND, 0)
            self.reflection.end()

    def _floor(self, mvp, eye, view, orthographic, size, *, flat=False):
        recipe = self.recipe
        floor, environment = recipe.floor, recipe.environment
        if not self.textures:
            self.textures = load_floor_textures(floor)
        vao, count = self.resources.mesh('floor', floor_vertices(floor), (3,))
        program = self.resources.program('floor', FLOOR_VERTEX, FLOOR_FRAGMENT)
        names = ('uMvp', 'uFlat', 'uAlbedo', 'uRoughness', 'uReflection', 'uReflectionLook', 'uViewport', 'uBackdrop',
                 'uAmbient', 'uFloor', 'uFloorLight', 'uSurface', 'uEye', 'uForward', 'uOrthographic', 'uMist', 'uMistShape')
        u = self.resources.uniforms('floor', names, required=False)
        gl.glUseProgram(program)
        gl.glUniform1i(u['uFlat'], int(flat))
        gl.glUniformMatrix4fv(u['uMvp'], 1, gl.GL_FALSE, np.asarray(mvp, np.float32))
        for unit, (name, texture) in enumerate((('uAlbedo', self.textures['albedo']),('uRoughness',self.textures['roughness']),
                                               ('uReflection', self.reflection.texture))):
            gl.glBindTextureUnit(unit, texture)
            gl.glUniform1i(u[name], unit)
        gl.glUniform4f(u['uReflectionLook'], floor.streak, floor.lod[0], floor.lod[1], 0.)
        gl.glUniform2f(u['uViewport'], *size)
        gl.glUniform3f(u['uBackdrop'], *environment.backdrop)
        gl.glUniform3f(u['uAmbient'], *floor.ambient)
        gl.glUniform4f(u['uFloor'], floor.tile, floor.reflection, floor.f0, floor.normal_shift)
        gl.glUniform2f(u['uFloorLight'], floor.diffuse, floor.diffuse_lod)
        gl.glUniform4f(u['uSurface'], *floor.surface)
        gl.glUniform3f(u['uEye'], *eye)
        gl.glUniform3f(u['uForward'], *(-view[2, :3]))
        gl.glUniform1i(u['uOrthographic'], int(orthographic))
        gl.glUniform4f(u['uMist'], *environment.mist['uMist'])
        gl.glUniform4f(u['uMistShape'], *environment.mist['uMistShape'])
        gl.glBindVertexArray(vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
        for unit in range(3):
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
