"""Photo reflections: a per-run, renderer-owned, mipmapped copy of a photograph.

Glossy pieces reflect the picture's colours through ``sceneEnvironment`` (blurred by
roughness from the copy's mip levels) at ``sceneReflectionUv`` (the reflected ray's
direction, so a reflection moves with the piece's turn, not with where it sits on
screen). The photographs themselves are lent presentation textures (PR-04 lends the
destination to the native branch): they are only ever sampled, never given mip
levels or written. Once per run each needed photograph is drawn, box-filtered, into
a small texture this object owns, which then gets its own mipmaps; the copies are
dropped at the host's ``park()`` with the renderer's other per-run resources.
"""
from __future__ import annotations

import ctypes

from OpenGL import GL as gl

from rendering.gl_programs.scene3d import SCENE3D_ENVIRONMENT_SIZE
from rendering.quick import gl_query

from .post import FULLSCREEN_VERTEX_SOURCE

# 16 bilinear taps over the output texel's footprint: a box filter wide enough for a
# 4K photograph (~7.5 source texels per copy texel) without aliasing into the copy.
_COPY_FRAGMENT = """#version 460 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uPhoto;
uniform vec2 uStep;   // a quarter of one copy texel, in uv
void main() {
    vec3 sum = vec3(0.0);
    for (int y = 0; y < 4; ++y) {
        for (int x = 0; x < 4; ++x) {
            sum += texture(uPhoto, vUv + (vec2(x, y) - 1.5) * uStep).rgb;
        }
    }
    FragColor = vec4(sum / 16.0, 1.0);
}
"""


def environment_size(pixel_size: tuple[int, int]) -> tuple[int, int]:
    """The copy's size: the photograph's aspect, ``SCENE3D_ENVIRONMENT_SIZE`` on the longer side."""
    width, height = max(1, int(pixel_size[0])), max(1, int(pixel_size[1]))
    scale = SCENE3D_ENVIRONMENT_SIZE / max(width, height)
    return max(1, round(width * scale)), max(1, round(height * scale))


class PhotoEnvironment:
    """The destination (and, if asked, the source) photograph as a blurred environment."""

    def __init__(self, label: str) -> None:
        self.label = label
        self._textures: dict[str, tuple[int, tuple]] = {}   # role -> (texture, key)
        # Allocation can fail after the driver assigned a name.  Retain a name
        # whose immediate cleanup failed so ``release()`` remains its retrying
        # deletion owner instead of silently leaking it.
        self._failed_textures: set[int] = set()
        self._fbo = 0
        self.copies = 0   # photographs copied (once per run and role; for tests and traces)

    @property
    def has_resources(self) -> bool:
        return bool(self._textures) or bool(self._failed_textures) or bool(self._fbo)

    def texture(self, frame, resources, role: str = "destination") -> int:
        """The run's environment for ``role`` ("destination" or "source"), copied on first use."""
        image = frame.run.request.destination_image if role == "destination" else frame.run.request.source_image
        lent = frame.destination_texture_id if role == "destination" else frame.source_texture_id
        size = environment_size(image.pixel_size)
        key = (frame.run.run_id, image.identity, size)
        held = self._textures.get(role)
        if held is not None and held[1] == key:
            return held[0]
        texture = 0
        if held is not None:
            if held[1][2] == size:
                texture = held[0]          # same size: copy over it
            else:
                gl.glDeleteTextures([held[0]])
                del self._textures[role]
        if not texture:
            texture = self._allocate(size)
        try:
            self._copy(lent, texture, size, resources, frame.quad_vao)
        except Exception:
            # A failed draw may have written part of a same-size reused copy;
            # do not leave that old key advertising valid pixels.  Delete it
            # now or retain its name for ``release()`` retry ownership.
            if held is not None and held[0] == texture:
                self._textures.pop(role, None)
            self._discard_failed_allocation(texture)
            raise
        self._textures[role] = (texture, key)
        self.copies += 1
        return texture

    def _allocate(self, size: tuple[int, int]) -> int:
        """Create one known-size, complete immutable mip chain without rebinding texture state."""

        texture = 0
        try:
            texture_name = (ctypes.c_uint * 1)()
            gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, texture_name)
            texture = int(texture_name[0])
            if not texture:
                raise RuntimeError(f"{self.label} photo environment texture allocation failed")
            gl.glTextureParameteri(
                texture,
                gl.GL_TEXTURE_MIN_FILTER,
                gl.GL_LINEAR_MIPMAP_LINEAR,
            )
            gl.glTextureParameteri(texture, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
                gl.glTextureParameteri(texture, wrap, gl.GL_CLAMP_TO_EDGE)
            gl.glTextureStorage2D(
                texture,
                max(size).bit_length(),
                gl.GL_RGBA8,
                *size,
            )
            return texture
        except Exception:
            if texture:
                self._discard_failed_allocation(texture)
            raise

    def _discard_failed_allocation(self, texture: int) -> None:
        """Delete an unadmitted texture now, retaining it only for a cleanup retry."""

        try:
            gl.glDeleteTextures([texture])
        except Exception:
            self._failed_textures.add(texture)

    def _copy(self, lent: int, texture: int, size: tuple[int, int], resources, vao: int) -> None:
        draw, read = gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING), gl_query.get_int(gl.GL_READ_FRAMEBUFFER_BINDING)
        viewport = gl_query.get_ints(gl.GL_VIEWPORT, 4)
        scissor = gl_query.is_enabled(gl.GL_SCISSOR_TEST)
        try:
            if not self._fbo:
                fbo_name = (ctypes.c_uint * 1)()
                gl.glCreateFramebuffers(1, fbo_name)
                self._fbo = int(fbo_name[0])
                if not self._fbo:
                    raise RuntimeError(f"{self.label} photo environment framebuffer allocation failed")
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo)
            gl.glNamedFramebufferTexture(self._fbo, gl.GL_COLOR_ATTACHMENT0, texture, 0)
            if (
                gl.glCheckNamedFramebufferStatus(self._fbo, gl.GL_FRAMEBUFFER)
                != gl.GL_FRAMEBUFFER_COMPLETE
            ):
                raise RuntimeError(f"{self.label} photo environment incomplete at {size}")
            gl.glViewport(0, 0, *size)
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glDepthMask(gl.GL_FALSE)
            program = resources.program("photo_environment", FULLSCREEN_VERTEX_SOURCE, _COPY_FRAGMENT)
            uniforms = resources.uniforms("photo_environment", ("uPhoto", "uStep"))
            gl.glUseProgram(program)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, lent)          # sampled only
            gl.glUniform1i(uniforms["uPhoto"], 0)
            gl.glUniform2f(uniforms["uStep"], 0.25 / size[0], 0.25 / size[1])
            gl.glBindVertexArray(vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            gl.glGenerateTextureMipmap(texture)                # only our owned copy gets mip levels
        finally:
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, draw)
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, read)
            gl.glViewport(*viewport)
            if scissor:
                gl.glEnable(gl.GL_SCISSOR_TEST)

    def release(self) -> None:
        errors: list[str] = []
        for role, (texture, key) in tuple(self._textures.items()):
            try:
                gl.glDeleteTextures([texture])
            except Exception as exc:
                errors.append(f"{role}: {exc}")
            else:
                del self._textures[role]
        for texture in tuple(self._failed_textures):
            try:
                gl.glDeleteTextures([texture])
            except Exception as exc:
                errors.append(f"failed texture: {exc}")
            else:
                self._failed_textures.discard(texture)
        if self._fbo:
            try:
                gl.glDeleteFramebuffers(1, [self._fbo])
            except Exception as exc:
                errors.append(f"fbo: {exc}")
            else:
                self._fbo = 0
        if errors:
            raise RuntimeError(f"{self.label} photo environment cleanup incomplete: {' | '.join(errors)}")

# (key, vertex, fragment) of the copy program (for a gradual warm-up).
PHOTO_ENVIRONMENT_PROGRAM = ("photo_environment", FULLSCREEN_VERTEX_SOURCE, _COPY_FRAGMENT)
