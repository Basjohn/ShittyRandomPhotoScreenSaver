"""Retained waveform scene composed over shared Scene3D owners; no window, context or clock."""
from __future__ import annotations
import struct
from pathlib import Path
from dataclasses import replace
from contextlib import contextmanager, nullcontext
import numpy as np
from PIL import Image
from OpenGL import GL as gl
from PySide6.QtGui import QOpenGLContext
from rendering.quick import gl_query
from core.ribbon_packet import KNOT_ROWS
from core.ribbon_continuation import continuation_bounds, frustum_axial_span
from core.waveform_ribbon_scene import Floor, Recipe, SPEC, FLOOR_CONTACT
from rendering.gl_programs.waveform_ribbon import (FLOOR_BLOCK, FLOOR_VERTEX, FLOOR_FRAGMENT, FLAT)
from rendering.gl_programs.waveform_atmosphere import (BODY_FIELD_UNIT, MEDIUM_BLOCK, MEDIUM_INJECT_SOURCE, SKY_BLOCK,
                                                       SKY_VERTEX, SKY_FRAGMENT)
from rendering.gl_programs.portable import pack_block
from rendering.gl_programs.mist import FOG_OFF
from rendering.gl_programs.reflection import mirror_view
from rendering.quick.scene3d.fog_volume import FogVolume
from rendering.quick.scene3d.floor_give import FloorGiveField, FLOOR_GIVE_UNIT
from rendering.quick.scene3d.pulse_rim import PulseRimField
from rendering.quick.scene3d.reflection import PlanarReflection
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.ribbon import GRADE_STOPS, RibbonPrimitive, ribbon_grade
from rendering.quick.scene3d.ribbon_bursts import RibbonBurstRenderer
from rendering.quick.scene3d.waveform_field import WaveformField
from rendering.quick.scene3d.target import SceneTarget
ROOT=Path(__file__).resolve().parents[3]


# The scene owns the GL state of its whole frame: the render host's fence hands the inherited state back afterwards,
# and every pass here sets what it draws with. So the shared primitives are asked not to read state back and restore
# it (``restore=False``): each read is a round trip to the driver thread, which on a loaded machine waits for a time
# slice; a frame used to make about 170 of them. Pixels are unchanged.
OWNED = dict(restore=False)

# Travel Direction's x mirror from the history axis into the world: one read-only constant, not rebuilt every frame.
_HISTORY_X_MIRROR = np.diag((-1., 1., 1., 1.))
_HISTORY_X_MIRROR.setflags(write=False)


@contextmanager
def unclipped_prepasses():
    """World targets have local viewports; the host's item scissor applies only to the final composition."""
    clipped=bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
    if clipped:gl.glDisable(gl.GL_SCISSOR_TEST)
    try:yield
    finally:
        if clipped:gl.glEnable(gl.GL_SCISSOR_TEST)

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


def capped(size, scale: float, max_height: int) -> tuple[float, float]:
    """A reduced-resolution target: ``scale`` of the viewport, but never taller than ``max_height`` (same aspect).
    Detail per screen fraction stays that of the approved look; cost stops growing with display resolution."""
    factor = min(scale, max_height/max(size[1], 1))
    return size[0]*factor, size[1]*factor


def floor_vertices() -> bytes:
    """Retained coverage footprint; the fragment evaluates the actual infinite world plane."""
    corners = ((0.,0.,0.),(1.,0.,0.),(1.,0.,1.),(0.,0.,0.),(1.,0.,1.),(0.,0.,1.))
    return b''.join(struct.pack('3f', *c) for c in corners)


def _slope_texture(height: np.ndarray) -> int:
    """Height slope per uv unit (periodic central differences), baked once: two fetches instead of eight per pixel."""
    size = np.asarray(height.shape[::-1], np.float32)
    slope = np.stack(((np.roll(height, -1, 1) - np.roll(height, 1, 1))*size[0]/2,
                      (np.roll(height, -1, 0) - np.roll(height, 1, 0))*size[1]/2), axis=-1).astype(np.float32)
    name = (gl.GLuint*1)()
    gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
    texture = int(name[0])
    # RGBA16F (N1.7: QRhi has no RG16F); the GL_RG upload leaves b = 0, a = 1, and the floor reads .rg.
    gl.glTextureStorage2D(texture, max(slope.shape[:2]).bit_length(), gl.GL_RGBA16F, slope.shape[1], slope.shape[0])
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
    """Saved maps: colour stays sRGB-encoded in plain RGBA8 and the floor shader decodes it (``srgbToLinear``, N0.3
    decision F4: Qt's OpenGL backend ignores the sRGB texture flag, so no backend relies on it; the GPU filters and
    mips the encoded values); roughness and height are linear data. Missing assets fail."""
    textures={}
    try:
        for key,path,storage in (('albedo',floor.albedo,gl.GL_RGBA8),('roughness',floor.roughness,gl.GL_RGBA8),
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
        # The floor's pass block (N1.6) is the largest these resources' draws bind; its reflection pre-pass and the
        # full pass take a copy each.
        self.resources = MeshResources('waveform scene', block_bytes=FLOOR_BLOCK.size, copies=2)
        self.scene, self.ribbons = SceneTarget('waveform scene'), RibbonPrimitive()
        self.fog_resources = MeshResources('waveform scene mist programs',
                                           block_bytes=max(SKY_BLOCK.size, MEDIUM_BLOCK.size))
        self.bursts = RibbonBurstRenderer()
        self.field = WaveformField()
        self.floor_give = FloorGiveField()  # the yielding floor's field: only while the recipe's floor gives
        self._floor_give = None
        self.pulse_rim = PulseRimField()  # the published pulse field for the rims: only while Pulse Rim is on
        self._history_mirror = None  # Travel Direction: None, or the x mirror from the history axis into the world
        self.reflection = PlanarReflection('waveform scene floor')
        self.fog, self.reflected_fog = FogVolume('waveform scene mist'), FogVolume('waveform scene reflected mist')
        self._specular, self._specular_size = None, None
        self.textures = {}
        # Studio preview-only layer omission (a Python attribute, never a setting): 'actors' skips the direct
        # ribbon/particle/strand draws, 'reflected_actors' their mirrored draws. The mist field, sky, floor and
        # everything else are unchanged. Production never sets it, so it stays empty there.
        self.preview_hidden = frozenset()

    @property
    def has_resources(self):
        return bool(self.textures or self._specular or self.resources.has_resources or self.scene.has_resources
                    or self.ribbons.has_resources or self.reflection.has_resources or self.fog.has_resources
                    or self.reflected_fog.has_resources or self.fog_resources.has_resources
                    or self.bursts.has_resources or self.field.has_resources or self.floor_give.has_resources
                    or self.pulse_rim.has_resources)


    def _check_context(self, *, admit=False):
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
        self._retire((self.fog.release,self.reflected_fog.release,
                      self.fog_resources.release_resources,self.field.release))

    def release(self):
        if self.has_resources:
            self._check_context()
        self._retire((*(lambda key=key: self._release_texture(key) for key in tuple(self.textures)),
                      self.reflection.release, self._release_specular, self.fog.release, self.reflected_fog.release,
                      self.ribbons.release, self.scene.release,
                      self.resources.release_resources, self.fog_resources.release_resources, self.bursts.release,
                      self.field.release, self.floor_give.release, self.pulse_rim.release))
        self._context = None


    def render(self,packet,**parameters):
        self._check_context(admit=True)
        if parameters.get('flat',False):return self._render_packet(packet,**parameters)
        with self.ribbons.packet_scope(packet, **OWNED):
            return self._render_packet(packet,**parameters)

    def _render_packet(self, packet, *, capacity, now, travel, recipe, size, view, projection, eye, camera_lens, card,
               flat=False, react=0., overlay=1., burst_payload=None, burst_origin=0.,strand_payload=None,strand_origin=0.,
               pulse=b''):
        self._check_context(admit=True)
        self.recipe, self.size, self._overlay = recipe, size, overlay
        # None is the lab's historical procedural-spark fixture; production explicitly supplies birth bytes.
        self._burst_payload, self._burst_origin = burst_payload, burst_origin
        self._strand_payload,self._strand_origin=strand_payload,strand_origin
        if recipe.strays is None:self.ribbons.release_strands()
        if recipe.sparks is None and self.bursts.has_resources:
            self.bursts.release()
        if recipe.fog is None and (self.fog.has_resources or self.reflected_fog.has_resources
                or self.fog_resources.has_resources or self.field.has_resources):
            self._release_fog()
        giving = not flat and recipe.floor.give > 0.
        if not giving and self.floor_give.has_resources:
            self.floor_give.release()
        # Pulse Rim: the logical owner's published pulse field, sampled by the light passes (direct and reflected).
        rim = not flat and recipe.pulse_rim > 0. and bool(pulse)
        if not rim and self.pulse_rim.has_resources:
            self.pulse_rim.release()
        self._now=now
        width, height = size
        environment, flow = recipe.environment, recipe.flow
        scroll = np.identity(4)
        scroll[0, 3] = flow.head_x - travel
        mvp = (projection @ view).flatten(order='F')
        # Travel Direction: the history (ribbons, sparks, strands, their fields) lives on its own axis, mirrored into
        # the world here (world x = side * axis) and nowhere else. +1 is the identity and multiplies nothing.
        side = -1. if flow.direction < 0. else 1.
        mirror = None if side > 0. else _HISTORY_X_MIRROR
        history_view = view if mirror is None else view @ mirror
        self._history_mirror = mirror
        ribbon_view = history_view @ scroll
        ribbon_mvp = tuple((projection @ ribbon_view).flatten(order='F'))
        self._continuation_origin=tuple(np.asarray(packet.world_origin)+scroll[:3,3])
        self._continuation_count=packet.instances
        self._continuation_camber=recipe.material.cross_curve
        transverse=continuation_bounds(packet,scroll[:3,3],recipe.material.cross_curve)
        main_span=frustum_axial_span(projection@history_view,transverse)
        reflected_span=frustum_axial_span(projection@(mirror_view(view,0.) if mirror is None
                                                      else mirror_view(view,0.)@mirror),transverse)
        span=(min(main_span[0],reflected_span[0]),max(main_span[1],reflected_span[1]))
        grade = colour_grade(recipe, react)  # one evaluation per frame for the ribbons, the field and the medium
        draw = dict(view=tuple(ribbon_view.flatten(order='F')), material=recipe.material,
                    sweep_axis=(1.,0.,0.), floor=FLOOR_CONTACT,
                    age_fade=(now, 0., (capacity - 1)/flow.knot_hz, 0.),continuation=(*span,2048),
                    mist=environment.mist, mist_frame=(scroll[0, 3], 0., 0.),
                    grade=ribbon_grade(*self._history_grade(grade[:3])),
                    pulse_rim=self.pulse_rim.update(pulse, recipe.pulse_rim) if rim else None,
                    viewport=(width, height), **OWNED)
        with unclipped_prepasses():
            # First inside the packet scope: the reduction reads the packet bound by it (the same knots every pass
            # draws), and the floor, the reflection and the ribbons then read one yielding surface.
            if giving:
                self.floor_give.update(packet, translation=scroll[:3, 3], floor=recipe.floor, contact=FLOOR_CONTACT,
                                       camber=recipe.material.cross_curve, side=side, **OWNED)
            self._floor_give = (self.floor_give.texture, self.floor_give.uniforms) if giving else None
            draw['floor_give'] = self._floor_give if not giving or mirror is None else (*self._floor_give, side)
            fogged = not flat and recipe.fog is not None
            if fogged:
                self._field_grade=grade
                self.field.update(packet,translation=scroll[:3,3],span=recipe.fog.field_span,
                                  grade=grade,side=side,**OWNED)
                self._update_fog(self.fog,view,camera_lens,size,recipe.fog.cell,recipe.fog.slices)
                self._update_fog(self.reflected_fog,mirror_view(view,0.),camera_lens,size,
                                 recipe.fog.reflection_cell,recipe.fog.reflection_slices)
            if not flat:
                with self._fog_bound(self.reflected_fog if fogged else None) as fog:
                    self._reflect(packet, projection, view, scroll,
                                  {**draw, 'mist': self._history_mist({**draw['mist'], **fog})})
        with self._fog_bound(self.fog if fogged else None) as fog:
            draw = {**draw, 'mist': self._history_mist({**draw['mist'], **fog})}
            self._draw_scene(flat, packet, draw, mvp, eye, view, ribbon_mvp, card, now, fogged)



    def _history_mist(self, mist):
        """Mist uniforms for history-bound draws: their world positions are on the history axis, so the volume's
        world -> view transform takes the Travel Direction mirror first."""
        if self._history_mirror is None or 'uFogView' not in mist:
            return mist
        view = np.asarray(mist['uFogView'], float).reshape(4, 4, order='F') @ self._history_mirror
        return {**mist, 'uFogView': tuple(view.flatten(order='F'))}

    def _history_grade(self, grade):
        """(nodes, world x range, share) of the colour grade as read at history-axis x: with the history mirrored the
        range and its nodes are mirrored, so the grade stays where it is in the world."""
        if self._history_mirror is None:
            return grade
        nodes, (x0, x1), share = grade
        return tuple((1.-position, colour) for position, colour in reversed(nodes)), (-x1, -x0), share

    def _history_mvp(self, matrix):
        """A world clip matrix for history-axis positions (bursts' births)."""
        return matrix if self._history_mirror is None else matrix @ self._history_mirror

    def _fog_bound(self, volume):
        """The volume bound for its passes, or a no-op scope with the analytic-mist uniforms."""
        return volume.bound(**OWNED) if volume is not None else nullcontext(dict(FOG_OFF))


    def _update_fog(self,volume,view,camera_lens,size,cell,slices):
        fog=self.recipe.fog
        grid=(min(128,-(-size[0]//cell)),min(72,-(-size[1]//cell)),slices)
        program=self.fog_resources.compute_program('fog medium',MEDIUM_INJECT_SOURCE)
        # The medium's values are its own pass block beside the volume's dispatch block (N1.6); the body field is on
        # its unit for the dispatch.
        values=self.fog_resources.values('fog medium')
        self._fog_values(values)
        with self.fog_resources.pass_blocks.bound(pack_block(MEDIUM_BLOCK,values)):
            volume.update(program,view=view,lens=camera_lens,depth_range=fog.depth_range,grid=grid,
                          focus_depth=-float((view@np.array((*SPEC.pivot,1.)))[2]),**OWNED)

    def _field_values(self,values):
        """The world body field's values (``WORLD_FIELD_GLSL``) into a program's pass block values; its texture bound
        at its unit."""
        fog=self.recipe.fog;first,last,samples=fog.field_span;step=(last-first)/(samples-1)
        gl.glBindTextureUnit(BODY_FIELD_UNIT,self.field.texture)
        values['uFieldOrigin']=(*self._continuation_origin,float(self._continuation_count))
        values['uFieldSide']=1. if self._history_mirror is None else -1.
        grade=self._field_grade
        values.update(ribbon_grade(grade[0],grade[1],grade[3]))
        values['uBodySpan']=(first-step*.5,1./(last-first+step))
        values['uBodyShape']=(FLOOR_CONTACT[0]+FLOOR_CONTACT[1],FLOOR_CONTACT[2],
                              self.recipe.material.cross_curve,fog.clearance)

    def _fog_values(self,values):
        fog=self.recipe.fog;self._field_values(values)
        values['uAtmosphere']=(fog.density,fog.height,fog.softness,fog.light)
        values['uAtmosphereMotion']=(self._now,fog.drift,fog.noise,fog.noise_scale)
        values['uAtmosphereAmbient']=tuple(fog.ambient)
        values['uAtmosphereLight']=(fog.light_ceiling,fog.light_tint)

    def _sky(self,volume,*,reflection=False):
        program=self.fog_resources.program('sky',SKY_VERTEX,SKY_FRAGMENT)
        vao,_=self.fog_resources.mesh('sky',bytes(36),(3,))
        gl.glUseProgram(program)
        values=self.fog_resources.values('sky')     # the volume at its unit; every value in the pass block (N1.6)
        values.update(volume.uniforms)
        values['uBackdrop']=tuple(self.recipe.environment.backdrop)
        values['uSkyReflection']=int(reflection)
        with self.fog_resources.pass_blocks.bound(pack_block(SKY_BLOCK,values)):
            gl.glBindVertexArray(vao);gl.glDrawArrays(gl.GL_TRIANGLES,0,3)

    def _draw_scene(self, flat, packet, draw, mvp, eye, view, ribbon_mvp, card, now, fogged):
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
                if fogged:
                    gl.glDisable(gl.GL_DEPTH_TEST);gl.glDepthMask(gl.GL_FALSE)
                    self._sky(self.fog)
                    gl.glEnable(gl.GL_DEPTH_TEST);gl.glDepthMask(gl.GL_TRUE)
                self._floor(mvp, eye, view, (width, height), flat=flat, drawing_to=self.scene.framebuffer)
                if flat:
                    self._flat_ribbons(packet, ribbon_mvp)
            if not flat and 'actors' not in self.preview_hidden:
                with self.scene.transparent_writes(card, self.resources, **OWNED):
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
                                          sweep_axis=draw['sweep_axis'], grade=draw['grade'], floor=draw['floor'],
                                          floor_give=draw['floor_give'], viewport=draw['viewport'], **OWNED)
                    if recipe.strays is not None:
                        self.ribbons.draw(packet, ribbon_mvp, shading='strays', strays=recipe.strays, now=now,
                                          mist=draw['mist'], mist_frame=draw['mist_frame'], material=recipe.material,
                                          sweep_axis=draw['sweep_axis'], grade=draw['grade'], floor=draw['floor'],
                                          strand_births=self._strand_payload,strand_origin=self._strand_origin,
                                          continuation=draw['continuation'],floor_give=draw['floor_give'],
                                          viewport=draw['viewport'], **OWNED)
                    if recipe.sparks is not None and self._burst_payload:
                        self.bursts.draw(self._burst_payload,now=now-self._burst_origin,
                                         mvp=tuple(self._history_mvp(np.asarray(mvp,float).reshape(4,4,order='F')).flatten(order='F')),
                                         viewport=(width,height),mist=draw['mist'],grade=draw['grade'],**OWNED)
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
                self._sky(self.reflected_fog,reflection=True)
            if 'reflected_actors' in self.preview_hidden:
                return                    # Studio preview only: the mirrored mist without its emitters
            reflected_view = (mirrored if self._history_mirror is None else mirrored @ self._history_mirror) @ scroll
            reflected_mvp = tuple((projection @ reflected_view).flatten(order='F'))
            self.ribbons.draw(packet, reflected_mvp, shading='light', **{**draw, 'view': tuple(reflected_view.flatten(order='F')),
                                                                          'viewport': self.reflection.size})
            if self.recipe.sparks is not None and self._burst_payload is None:
                self.ribbons.draw(packet, reflected_mvp, shading='sparks', sparks=self.recipe.sparks, now=draw['age_fade'][0],
                                  mist=draw['mist'], mist_frame=draw['mist_frame'], material=self.recipe.material,
                                  sweep_axis=draw['sweep_axis'], grade=draw['grade'], floor=draw['floor'],
                                  floor_give=draw['floor_give'], viewport=self.reflection.size, **OWNED)
            if self.recipe.strays is not None:
                self.ribbons.draw(packet, reflected_mvp, shading='strays', strays=self.recipe.strays,
                                  now=draw['age_fade'][0], mist=draw['mist'], mist_frame=draw['mist_frame'],
                                  material=self.recipe.material, sweep_axis=draw['sweep_axis'], grade=draw['grade'],
                                  floor=draw['floor'],strand_births=self._strand_payload,strand_origin=self._strand_origin,
                                  continuation=draw['continuation'],floor_give=draw['floor_give'],
                                  viewport=self.reflection.size, **OWNED)
            if self.recipe.sparks is not None and self._burst_payload:
                self.bursts.draw(self._burst_payload,mvp=tuple(self._history_mvp(projection @ mirrored).flatten(order='F')),
                    now=draw['age_fade'][0]-self._burst_origin,
                    viewport=self.reflection.size,mist=draw['mist'],grade=draw['grade'],**OWNED)
        finally:
            gl.glDisablei(gl.GL_BLEND, 0)
            self.reflection.end()


    def _floor(self, mvp, eye, view, size, *, flat=False, mist_off=False, drawing_to=None):
        """``drawing_to``: the bound framebuffer when the caller knows it (the scene's, at viewport ``size`` with depth
        testing on), so nothing is read back; otherwise the bound state is read and restored."""
        recipe = self.recipe
        floor, environment = recipe.floor, recipe.environment
        if 'albedo' not in self.textures:
            self.textures.update(load_floor_textures(floor))
        vao, count = self.resources.mesh('floor', floor_vertices(), (3,))
        program = self.resources.program('floor', FLOOR_VERTEX, FLOOR_FRAGMENT)
        # The floor's values as its uniforms held them, one pass block (N1.6); every sampler carries its unit.
        u = self.resources.values('floor')
        gl.glUseProgram(program)
        inverse=np.linalg.inv(np.asarray(mvp,float).reshape(4,4,order='F'))
        u['uFloorInverseMvp'] = tuple(np.asarray(inverse.flatten(order='F'),np.float32))
        u['uFlat'] = int(flat)
        u['uMvp'] = tuple(np.asarray(mvp, np.float32))
        lit = not flat and self.fog.has_resources and self.recipe.fog is not None
        for unit,texture in enumerate((self.textures['albedo'],self.textures['slope'],self.reflection.texture,
                                       self.textures['roughness'])):
            gl.glBindTextureUnit(unit,texture)
        u['uFogLit'] = int(lit)
        u['uReflectionLook'] = (floor.streak[0], floor.lod[0], floor.lod[1], 0.)
        u['uHot'] = (*floor.hot, floor.albedo_bias)
        u['uPool'] = floor.pool if lit else 0.
        u['uColumn'] = tuple(floor.column)
        u['uReflectionHue'] = floor.hue
        u['uBound'] = (floor.glow_limit, floor.light_reach, floor.light_far)
        give = None if flat else self._floor_give
        if give is None:
            u['uFloorGive'] = (0., 0., 1., 1.)
        else:
            gl.glBindTextureUnit(FLOOR_GIVE_UNIT, give[0])
            u['uFloorGive'] = tuple(give[1])
            u['uFloorGiveLook'] = (floor.give_reach, floor.shading)
        if lit:self._field_values(u)
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
        u['uForward'] = tuple(-view[2, :3])
        u['uMist'] = environment.mist['uMist']
        u['uMistShape'] = (0., 0., 0., 0.) if mist_off else environment.mist['uMistShape']
        if lit and not mist_off:  # one integrated medium, sampled to this exact world-floor hit
            fog = self.fog.uniforms
            u['uFogView'] = fog['uFogView']
            u['uFogLens'] = fog['uFogLens']
            u['uFogRange'] = fog['uFogRange']
        else:
            u['uFogRange'] = FOG_OFF['uFogRange']
        gl.glBindVertexArray(vao)
        # The reflection term (column taps) holds no detail finer than its reflection target, so on
        # large displays it is evaluated at a capped height and read back by the full-resolution pass.
        factor = min(1., floor.specular_max_height/max(size[1], 1))
        if flat or factor >= 1.:
            u['uSpecMode'] = 0
            with self.resources.pass_blocks.bound(pack_block(FLOOR_BLOCK, u)):
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
        else:
            texture, target = self._specular_target((int(size[0]*factor), int(size[1]*factor)))
            if drawing_to is None:
                framebuffer = gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING)
                viewport = list(gl_query.get_ints(gl.GL_VIEWPORT, 4))
                depth_test = gl_query.is_enabled(gl.GL_DEPTH_TEST)
            else:
                framebuffer, viewport, depth_test = drawing_to, [0, 0, *size], True
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, target)
            gl.glViewport(0, 0, *self._specular_size)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glClearBufferfv(gl.GL_COLOR, 0, (0., 0., 0., 0.))
            u['uSpecMode'] = 1
            u['uViewport'] = tuple(self._specular_size)
            with self.resources.pass_blocks.bound(pack_block(FLOOR_BLOCK, u)) as rebind:
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
                gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, framebuffer)
                gl.glViewport(*viewport)
                if depth_test:
                    gl.glEnable(gl.GL_DEPTH_TEST)
                u['uSpecMode'] = 2
                u['uViewport'] = tuple(size)
                rebind(pack_block(FLOOR_BLOCK, u))
                gl.glBindTextureUnit(4, texture)
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
        for unit in (0, 1, 2, 3, 4, 14) if give is None else (0, 1, 2, 3, 4, 14, FLOOR_GIVE_UNIT):
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


