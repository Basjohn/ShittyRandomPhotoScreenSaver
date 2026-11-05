"""The yielding floor's fixed-world field, reduced once per frame on GPU without readback or camera inputs."""
from OpenGL import GL as gl
from rendering.quick import gl_query
from rendering.quick.scene3d.compute import bound_image,dispatch
from rendering.quick.scene3d.resources import MeshResources,warm_programs
from rendering.gl_programs.waveform_atmosphere import FIELD_RIBBONS
from rendering.gl_programs.waveform_floor_give import (FLOOR_GIVE_SECTION_COMPUTE,FLOOR_GIVE_BLUR_COMPUTE,
                                                       FLOOR_GIVE_ROWS)

# Texture unit the yielding floor's field is bound to for the floor and ribbon passes (clear of the floor's 0-4, the
# mist's 8-12 and 15 and the world field's 14).
FLOOR_GIVE_UNIT=13
# The field fades to the plane over this many world units inside each end of its span: no edge in the floor.
EDGE_FADE=8.


def _texture(width,height):
    name=(gl.GLuint*1)();gl.glCreateTextures(gl.GL_TEXTURE_2D,1,name);texture=int(name[0])
    gl.glTextureStorage2D(texture,1,gl.GL_RGBA32F,width,height)
    for key,value in ((gl.GL_TEXTURE_MIN_FILTER,gl.GL_LINEAR),(gl.GL_TEXTURE_MAG_FILTER,gl.GL_LINEAR),
            (gl.GL_TEXTURE_WRAP_S,gl.GL_CLAMP_TO_EDGE),(gl.GL_TEXTURE_WRAP_T,gl.GL_CLAMP_TO_EDGE)):
        gl.glTextureParameteri(texture,key,value)
    return texture


class FloorGiveField:
    """Caller owns the current GL context; ``update`` once per frame, then ``uniforms`` for every consumer."""
    def __init__(self):
        self.resources=MeshResources('waveform floor give');self.texture=0;self._sections=0;self._samples=0
        self._context=None;self._span=None

    @property
    def has_resources(self):return bool(self.texture or self._sections or self.resources.has_resources)

    def _check(self):
        from PySide6.QtGui import QOpenGLContext
        current=QOpenGLContext.currentContext()
        if current is None:raise RuntimeError('Floor give field requires its current GL context')
        if self._context is None:self._context=current
        if current!=self._context:raise RuntimeError('Floor give field used in a foreign GL context')

    def prepare_step(self):
        self._check()
        return warm_programs(((self.resources,'sections',FLOOR_GIVE_SECTION_COMPUTE),
                              (self.resources,'blur',FLOOR_GIVE_BLUR_COMPUTE)))

    def _release_textures(self):
        names=[name for name in (self.texture,self._sections) if name]
        if names:gl.glDeleteTextures(len(names),names)
        self.texture=self._sections=0;self._samples=0

    def update(self,packet,*,translation,floor,contact,camber,side=1.,restore=True):
        """``floor`` is the scene's ``Floor`` (give > 0); ``contact`` the ribbons' (floor height, gap, softness).
        Reads the packet bound at shader-storage binding 0 by the caller's packet scope. ``restore=False``: the caller
        owns the program and image units for its frame (nothing read back; units left unbound)."""
        self._check();first,last,samples=floor.give_span;samples=int(samples)
        if (not 8<=samples<=4096 or packet.instances>FIELD_RIBBONS or not first+2*EDGE_FADE<last
                or not 0.<floor.give<=1. or not floor.give_depth>0. or not floor.give_radius>0. or not floor.give_blur>0.
                or not floor.give_softness>0.):
            raise ValueError('Floor give field exceeds its bounded domain')
        if samples!=self._samples:
            self._release_textures()
            self._sections=_texture(samples,FIELD_RIBBONS);self.texture=_texture(samples,FLOOR_GIVE_ROWS)
            self._samples=samples
        height,gap,_softness=(float(v) for v in contact)
        step=(last-first)/(samples-1)
        before=gl_query.get_int(gl.GL_CURRENT_PROGRAM) if restore else None
        try:
            program=self.resources.compute_program('sections',FLOOR_GIVE_SECTION_COMPUTE);gl.glUseProgram(program)
            u=self.resources.uniforms('sections',('uGiveSpan','uGiveShape','uFieldOrigin','uFieldSide'),required=False)
            gl.glUniform1f(u['uFieldSide'],float(side))
            gl.glUniform4f(u['uGiveSpan'],first,last,samples,EDGE_FADE)
            gl.glUniform4f(u['uGiveShape'],height+gap,floor.give_softness,float(camber),0.)
            gl.glUniform4f(u['uFieldOrigin'],*(float(a+b) for a,b in zip(packet.world_origin,translation)),packet.instances)
            with bound_image(0,self._sections,gl.GL_WRITE_ONLY,gl.GL_RGBA32F,restore=restore):
                dispatch((-(-samples//64),FIELD_RIBBONS,1),gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)
            program=self.resources.compute_program('blur',FLOOR_GIVE_BLUR_COMPUTE);gl.glUseProgram(program)
            u=self.resources.uniforms('blur',('uGiveBlur',),required=False)
            gl.glUniform4f(u['uGiveBlur'],samples,floor.give_blur/step,floor.give,floor.give_radius)
            with bound_image(0,self._sections,gl.GL_READ_ONLY,gl.GL_RGBA32F,restore=restore),\
                 bound_image(1,self.texture,gl.GL_WRITE_ONLY,gl.GL_RGBA32F,restore=restore):
                dispatch((-(-samples//64),1,1),gl.GL_TEXTURE_FETCH_BARRIER_BIT)
        finally:
            if before is not None:gl.glUseProgram(before)
        self._span=(first-.5*step,1./(last-first+step),floor.give_depth,step)

    @property
    def uniforms(self):
        """``uFloorGive`` for ``FLOOR_GIVE_GLSL`` after this frame's ``update`` (bind ``texture`` at FLOOR_GIVE_UNIT)."""
        if self._span is None:raise RuntimeError('Floor give field has not been reduced this frame')
        return self._span

    def release(self):
        if self.has_resources:self._check()
        errors=[]
        try:self._release_textures()
        except Exception as error:errors.append(error)
        try:self.resources.release_resources()
        except Exception as error:errors.append(error)
        if errors:raise ExceptionGroup('Floor give field remains for retry',errors)
        self._context=None;self._span=None
