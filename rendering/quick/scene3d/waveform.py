"""Retained waveform scene composed over shared Scene3D owners; no window, context or clock."""
from __future__ import annotations
import math, struct
from pathlib import Path
from dataclasses import replace
from contextlib import contextmanager
import numpy as np
from PIL import Image
from OpenGL import GL as gl
from core.ribbon_packet import KNOT_ROWS
from core.waveform_ribbon_scene import Fog, Floor, Recipe, SPEC, VIEW_SLOPE, FLOOR_CONTACT
from rendering.gl_programs.waveform_ribbon import (FLOOR_VERTEX, FLOOR_FRAGMENT, FLAT, ENVELOPE_RIBBONS,
    FOG_SHAPE_GLSL, FOG_COVERAGE_GLSL, FOG_MEDIUM_GLSL, SHAPE_BAKE_COMPUTE)
from rendering.gl_programs.fog_volume import fog_inject_source
from rendering.gl_programs.mist import FOG_OFF
from rendering.gl_programs.reflection import mirror_view
from rendering.quick.scene3d.fog_volume import FogVolume, FogMarch
from rendering.quick.scene3d.reflection import PlanarReflection
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.ribbon import GRADE_STOPS, RibbonPrimitive, ribbon_grade
from rendering.quick.scene3d.ribbon_bursts import RibbonBurstRenderer
from rendering.quick.scene3d.target import SceneTarget
ROOT=Path(__file__).resolve().parents[3]


@contextmanager
def unclipped_prepasses():
    """World targets have local viewports; the host's item scissor applies only to the final composition."""
    clipped=bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
    if clipped:gl.glDisable(gl.GL_SCISSOR_TEST)
    try:yield
    finally:
        if clipped:gl.glEnable(gl.GL_SCISSOR_TEST)

def waveform_envelope(packet, translation, age_fade, fog: Fog, grade=None, slopes=(0., VIEW_SLOPE),
                      camber=0.) -> np.ndarray:
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
        ribbon_share = float(np.clip(min(path[2,3],path[3,3]),0.,1.))
        if ribbon_share == 0.:
            continue
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
            tk = knots[t_order]
            # Match the swept body B-spline, not straight interpolation through its control points. Its full
            # cross-section lies inside this disk: width + transverse camber, then the same 1-Lipschitz floor map.
            # Four samples per interval are finer than the envelope texture at the admitted history speeds.
            if len(tk)>=4:
                u=np.arange(4)/4.;v=1.-u
                weights=np.stack((v**3,3*u**3-6*u*u+4.,-3*u**3+3*u*u+3*u+1.,u**3),axis=1)/6.
                windows=np.stack([tk[i:len(tk)-3+i] for i in range(4)],axis=1)
                dense=np.einsum('uk,ikrc->iurc',weights,windows).reshape(-1,KNOT_ROWS,4)
                tx=dense[:,0,0]+origin[0]
                cy=dense[:,0,1]+origin[1]
                low=FLOOR_CONTACT[0]+FLOOR_CONTACT[1]
                softness=FLOOR_CONTACT[2]
                cy=low+softness*np.logaddexp(0.,(cy-low)/softness)
                tube[:,0]=np.interp(xs,tx,cy)
                tube[:,1]=np.interp(xs,tx,dense[:,0,2]+origin[2])
                # Positive disk margin covers envelope texel interpolation and the finer spline chord error.
                radius=dense[:,0,3]*math.sqrt(1.+camber*camber)+.08
                tube[:,2]=np.interp(xs,tx,radius)
                tube[:,3]=np.interp(xs,true_x[t_order],fade[t_order],left=0.,right=0.)
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
    # Artistic side walls close the projected hall; physical clearance follows visible geometry independently.
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



class WaveformScene:
    """Caller owns the current GL context, camera, output frame and explicit snapshot time."""
    def __init__(self):
        self._context = None
        self.resources, self.scene, self.ribbons = MeshResources('waveform scene'), SceneTarget('waveform scene'), RibbonPrimitive()
        self.fog_resources = MeshResources('waveform scene mist programs')
        self.bursts = RibbonBurstRenderer()
        self.reflection = PlanarReflection('waveform scene floor')
        self.fog, self.reflected_fog = FogVolume('waveform scene mist'), FogVolume('waveform scene reflected mist')
        self.march = FogMarch('waveform scene mist', FOG_COVERAGE_GLSL)
        self._crackle_limit = None
        self._bake_grid = None
        self._specular, self._specular_size = None, None
        self._slopes = (0., VIEW_SLOPE)
        self.reflected_march = FogMarch('waveform scene reflected mist', FOG_COVERAGE_GLSL)
        self.textures = {}

    @property
    def has_resources(self):
        return bool(self.textures or self._specular or self.resources.has_resources or self.scene.has_resources
                    or self.ribbons.has_resources or self.reflection.has_resources or self.fog.has_resources
                    or self.reflected_fog.has_resources or self.march.has_resources or self.reflected_march.has_resources
                    or self.fog_resources.has_resources or self.bursts.has_resources)


    def _check_context(self, *, admit=False):
        from PySide6.QtGui import QOpenGLContext
        current = QOpenGLContext.currentContext()
        if current is None:
            raise RuntimeError('Waveform scene requires its owning current GL context')
        # Keep the Python wrapper alive. Qt owns the native context; a weak-only wrapper can disappear between
        # currentContext() calls on Qt Quick's render thread, falsely rejecting the same native context as foreign.
        if self._context is None and admit:
            self._context = current
        if self._context is None or self._context != current:
            raise RuntimeError('Waveform scene used in a foreign GL context')

    def admit_preparation(self):
        """Preparation owns resources before any render has occurred; cancellation must remain legally retireable."""
        self._check_context(admit=True)

    @staticmethod
    def _retire(actions):
        errors = []
        for action in actions:
            try:
                action()
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup('Waveform resources remain for retry', errors)

    def _release_texture(self, key):
        if key in self.textures:
            gl.glDeleteTextures(1, [self.textures[key]])
            del self.textures[key]

    def _release_fog(self):
        self._retire((self.fog.release, self.reflected_fog.release, self.march.release, self.reflected_march.release,
                      self.fog_resources.release_resources,
                      lambda: self._release_texture('shape'), lambda: self._release_texture('envelope')))
        self._bake_grid = self._crackle_limit = None

    def release(self):
        if self.has_resources:
            self._check_context()
        self._retire((*(lambda key=key: self._release_texture(key) for key in tuple(self.textures)),
                      self.reflection.release, self._release_specular, self.fog.release, self.reflected_fog.release,
                      self.march.release, self.reflected_march.release, self.ribbons.release, self.scene.release,
                      self.resources.release_resources, self.fog_resources.release_resources, self.bursts.release))
        self._context = None


    def render(self, packet, *, capacity, now, travel, recipe, size, view, projection, eye, camera_lens, card,
               flat=False, react=0., overlay=1., burst_payload=None, burst_origin=0.):
        self._check_context(admit=True)
        self.recipe, self.size, self._overlay = recipe, size, overlay
        # None is the lab's historical procedural-spark fixture; production explicitly supplies birth bytes.
        self._burst_payload, self._burst_origin = burst_payload, burst_origin
        if recipe.sparks is None and self.bursts.has_resources:
            self.bursts.release()
        if recipe.fog is None and (self.fog.has_resources or self.reflected_fog.has_resources
                or self.march.has_resources or self.reflected_march.has_resources or self.fog_resources.has_resources
                or 'envelope' in self.textures or 'shape' in self.textures):
            self._release_fog()
        width, height = size
        environment, flow = recipe.environment, recipe.flow
        scroll = np.identity(4)
        scroll[0, 3] = flow.head_x - travel
        mvp = (projection @ view).flatten(order='F')
        ribbon_view = view @ scroll
        ribbon_mvp = tuple((projection @ ribbon_view).flatten(order='F'))
        orthographic = camera_lens[2]
        draw = dict(view=tuple(ribbon_view.flatten(order='F')), material=recipe.material, orthographic=orthographic,
                    sweep_axis=(1.,0.,0.), floor=FLOOR_CONTACT,
                    age_fade=(now, flow.fade_in, (capacity - 1)/flow.knot_hz, flow.fade_out),
                    mist=environment.mist, mist_frame=(scroll[0, 3], 0., 0.),
                    grade=ribbon_grade(*colour_grade(recipe, react)[:3]))
        # The mist is a world field. Its authored extrusion stays fixed while the physical eye navigates;
        # deriving slopes from forward.z made end-on views singular and changed the medium with the camera.
        self._slopes = (0., VIEW_SLOPE)
        with unclipped_prepasses():
            envelope = None if flat or recipe.fog is None else waveform_envelope(packet, scroll[:3, 3], draw['age_fade'],
                                                                                  recipe.fog,
                                                                                  colour_grade(recipe, react),
                                                                                  self._slopes,recipe.material.cross_curve)
            fogged = not flat and recipe.fog is not None
            if fogged:
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
            self._draw_scene(flat, packet, draw, mvp, eye, view, orthographic, ribbon_mvp, card, now, fogged)



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
        program = self.fog_resources.compute_program('shape bake', SHAPE_BAKE_COMPUTE)
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
        program = self.fog_resources.compute_program('fog medium', fog_inject_source(FOG_MEDIUM_GLSL))
        self._upload_envelope(envelope)
        volume.update(program, view=view, lens=camera_lens, depth_range=fog.depth_range, grid=grid,
                      medium=self._fog_uniforms)


    def _fog_uniforms(self, program):
        """The shape's (and the medium's light) uniforms, for the inject and march programs alike."""
        fog = self.recipe.fog
        x0, x1, count = fog.envelope_range
        location = lambda name: gl.glGetUniformLocation(program, name)
        gl.glBindTextureUnit(14, self.textures['envelope'])
        gl.glUniform1i(location('uEnvelope'), 14)
        step=(x1-x0)/(count-1)
        gl.glUniform2f(location('uEnvelopeSpan'), x0-step*.5, 1./(x1-x0+step))
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


    def _draw_scene(self, flat, packet, draw, mvp, eye, view, orthographic, ribbon_mvp, card, now, fogged):
        recipe, (width, height) = self.recipe, self.size
        environment = recipe.environment
        with self.scene.scope(card, 4, self.resources, overlay=self._overlay, bloom=0. if flat else recipe.bloom,
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
                    if recipe.sparks is not None and self._burst_payload is None:
                        self.ribbons.draw(packet, ribbon_mvp, shading='sparks', sparks=recipe.sparks, now=now,
                                          mist=draw['mist'], mist_frame=draw['mist_frame'], material=recipe.material,
                                          sweep_axis=draw['sweep_axis'], grade=draw['grade'], floor=draw['floor'])
                    if recipe.strays is not None:
                        self.ribbons.draw(packet, ribbon_mvp, shading='strays', strays=recipe.strays, now=now,
                                          mist=draw['mist'], mist_frame=draw['mist_frame'], material=recipe.material,
                                          sweep_axis=draw['sweep_axis'], grade=draw['grade'], floor=draw['floor'])
                    if recipe.sparks is not None and self._burst_payload:
                        self.bursts.draw(self._burst_payload,mvp=mvp,now=now-self._burst_origin,
                                         viewport=(width,height),mist=draw['mist'],grade=draw['grade'])
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
            if self.recipe.sparks is not None and self._burst_payload is None:
                self.ribbons.draw(packet, reflected_mvp, shading='sparks', sparks=self.recipe.sparks, now=draw['age_fade'][0],
                                  mist=draw['mist'], mist_frame=draw['mist_frame'], material=self.recipe.material,
                                  sweep_axis=draw['sweep_axis'], grade=draw['grade'], floor=draw['floor'])
            if self.recipe.strays is not None:
                self.ribbons.draw(packet, reflected_mvp, shading='strays', strays=self.recipe.strays,
                                  now=draw['age_fade'][0], mist=draw['mist'], mist_frame=draw['mist_frame'],
                                  material=self.recipe.material, sweep_axis=draw['sweep_axis'], grade=draw['grade'],
                                  floor=draw['floor'])
            if self.recipe.sparks is not None and self._burst_payload:
                self.bursts.draw(self._burst_payload,mvp=tuple((projection @ mirrored).flatten(order='F')),
                    now=draw['age_fade'][0]-self._burst_origin,
                    viewport=self.reflection.size,mist=draw['mist'],grade=draw['grade'])
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
                 'uSpecular', 'uFloorTint')
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
            x0, x1, count = self.recipe.fog.envelope_range
            gl.glBindTextureUnit(14, envelope)
            gl.glUniform1i(u['uEnvelope'], 14)
            step=(x1-x0)/(count-1)
            gl.glUniform2f(u['uEnvelopeSpan'], x0-step*.5, 1./(x1-x0+step))
        gl.glUniform4f(u['uStreak'], 0., floor.streak[1], floor.streak[2], 8.)
        gl.glUniform4f(u['uReflectionContact'], 0., *floor.contact)
        gl.glUniform2f(u['uViewport'], *size)
        gl.glUniform3f(u['uBackdrop'], *environment.backdrop)
        gl.glUniform3f(u['uAmbient'], *floor.ambient)
        gl.glUniform3f(u['uFloorTint'], *floor.tint)
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
            if target:
                gl.glDeleteFramebuffers(1, [target])
                self._specular = (texture, 0)
            if texture:
                gl.glDeleteTextures(1, [texture])
        self._specular, self._specular_size = None, None


    def _flat_ribbons(self, packet, mvp):
        """Flat ribbon silhouettes in one known colour: rewrite every ribbon's colours in a copy of the packet."""
        data = np.frombuffer(packet.payload, np.float32).copy().reshape(packet.instances, -1, 4)
        data[:, 2] = data[:, 3] = (*FLAT['ribbon'], 1.)
        data[:, 4 + 4::KNOT_ROWS, 3] = 0.  # tint share off: one known colour
        flat = type(packet)(data.tobytes(), packet.instances, packet.vertices, packet.world_origin, packet.coordinate_origin)
        self.ribbons.draw(flat, mvp, material=self.recipe.material, sweep_axis=(1.,0.,0.))


