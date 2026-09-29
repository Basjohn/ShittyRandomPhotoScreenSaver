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

from OpenGL import GL as gl

from rendering.gl_programs.scene3d import SCENE3D_ENVIRONMENT_SIZE
from rendering.quick import gl_query

from .post import FULLSCREEN_VERTEX_SOURCE

# 16 bilinear taps over the output texel's footprint: a box filter wide enough for a
# 4K photograph (~7.5 source texels per copy texel) without aliasing into the copy.
_COPY_FRAGMENT = """#version 410 core
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
        self._fbo = 0
        self.copies = 0   # photographs copied (once per run and role; for tests and traces)

    @property
    def has_resources(self) -> bool:
        return bool(self._textures) or bool(self._fbo)

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
        self._textures[role] = (texture, key)
        self._copy(lent, texture, size, resources, frame.quad_vao)
        self.copies += 1
        return texture

    def _allocate(self, size: tuple[int, int]) -> int:
        texture = int(gl.glGenTextures(1))
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, wrap, gl.GL_CLAMP_TO_EDGE)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, size[0], size[1], 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
        return texture

    def _copy(self, lent: int, texture: int, size: tuple[int, int], resources, vao: int) -> None:
        draw, read = gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING), gl_query.get_int(gl.GL_READ_FRAMEBUFFER_BINDING)
        viewport = gl_query.get_ints(gl.GL_VIEWPORT, 4)
        scissor = gl_query.is_enabled(gl.GL_SCISSOR_TEST)
        try:
            if not self._fbo:
                self._fbo = int(gl.glGenFramebuffers(1))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo)
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
            if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
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
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)       # our own copy gets the mip levels
            gl.glGenerateMipmap(gl.GL_TEXTURE_2D)
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
        if self._fbo:
            try:
                gl.glDeleteFramebuffers(1, [self._fbo])
            except Exception as exc:
                errors.append(f"fbo: {exc}")
            else:
                self._fbo = 0
        if errors:
            raise RuntimeError(f"{self.label} photo environment cleanup incomplete: {' | '.join(errors)}")
