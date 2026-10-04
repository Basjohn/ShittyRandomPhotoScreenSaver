"""Photo reflections: a per-run, renderer-owned, mipmapped copy of a photograph.

``BackdropEnvironment`` is the same idea for a Visualizer: the displayed photograph, downsampled
once per image change by the Visualizer's owner, uploaded into a small owned mipmapped texture.

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


class BackdropEnvironment:
    """The wallpaper a Visualizer reflects, as small mipmapped textures this object owns.

    ``textures`` uploads a ``VisualizerBackdrop`` (``widgets/spotify_visualizer/backdrop.py``: the
    displayed photograph, downsampled once per image change on the GUI thread, bottom row first)
    when its identity changes, builds its mip levels, and reuses it until the next one: one ~0.6 MB
    upload per wallpaper. The reflection never switches in one frame (operator 2026-10-04): the
    new wallpaper goes into the other of two slots and the reflection crossfades from the old one
    over ``BLEND_S`` of the caller's logical time; the first wallpaper fades in from no reflection.
    Nothing reads back the target being drawn (which stalled the GPU ~0.55 ms per copy) and no GL
    texture is shared with the background. Pixel-unpack state and the unpack-buffer binding are
    handed back as found. Nothing is held once ``release`` runs.
    """

    BLEND_S = 2.0

    def __init__(self, label: str) -> None:
        self.label = label
        # Two slots: (texture, size, identity); ``_current`` indexes the newest.
        self._slots: list[list] = [[0, None, None], [0, None, None]]
        self._current = 0
        self._changed_at: float | None = None
        self._has_previous = False
        self.uploads = 0

    @property
    def has_resources(self) -> bool:
        return any(slot[0] for slot in self._slots)

    def warm(self, backdrop) -> bool:
        """Allocate ahead (one unit) what ``textures`` will first use for ``backdrop``; True once
        done. The first ``textures`` still uploads."""
        size = tuple(int(value) for value in backdrop["size"])
        slot = self._slots[self._current]
        if slot[1] != size:
            self._allocate(self._current, size)
            return False
        return True

    def textures(self, backdrop, now: float) -> tuple[int, int, float]:
        """(current, previous, blend) for ``backdrop`` at logical time ``now``: the reflection is
        ``previous`` faded to ``current`` by ``blend`` (0..1 over ``BLEND_S`` since it changed).
        ``previous`` is 0 for the first wallpaper, which then fades in from no reflection."""
        identity = str(backdrop["identity"])
        size = tuple(int(value) for value in backdrop["size"])
        now = float(now)
        current = self._slots[self._current]
        if current[2] != identity:
            target = self._current if not current[0] or current[2] is None else 1 - self._current
            if self._slots[target][1] != size:
                self._allocate(target, size)
            self._upload(target, backdrop["rgba"], size)
            self._slots[target][2] = identity
            self.uploads += 1
            self._has_previous = target != self._current
            self._current = target
            self._changed_at = now
        blend = 1.0
        if self._changed_at is not None and now >= self._changed_at:
            blend = min(1.0, (now - self._changed_at) / self.BLEND_S)
        previous = self._slots[1 - self._current][0] if self._has_previous and blend < 1.0 else 0
        if blend >= 1.0:
            self._has_previous = False
        return self._slots[self._current][0], previous, blend

    def _allocate(self, index: int, size: tuple[int, int]) -> None:
        self._delete(index)
        name = (ctypes.c_uint * 1)()
        gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
        texture = int(name[0])
        if not texture:
            raise RuntimeError(f"{self.label} backdrop texture allocation failed")
        gl.glTextureParameteri(texture, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
        gl.glTextureParameteri(texture, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
            gl.glTextureParameteri(texture, wrap, gl.GL_CLAMP_TO_EDGE)
        gl.glTextureStorage2D(texture, max(size).bit_length(), gl.GL_RGBA8, *size)
        self._slots[index] = [texture, size, None]

    def _upload(self, index: int, rgba: bytes, size: tuple[int, int]) -> None:
        texture = self._slots[index][0]
        if len(rgba) != size[0] * size[1] * 4:
            raise ValueError(f"{self.label} backdrop has {len(rgba)} bytes for {size}")
        prior = {name: gl_query.get_int(name) for name in (
            gl.GL_PIXEL_UNPACK_BUFFER_BINDING, gl.GL_UNPACK_ALIGNMENT, gl.GL_UNPACK_ROW_LENGTH,
            gl.GL_UNPACK_SKIP_ROWS, gl.GL_UNPACK_SKIP_PIXELS)}
        try:
            gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 4)
            for name in (gl.GL_UNPACK_ROW_LENGTH, gl.GL_UNPACK_SKIP_ROWS, gl.GL_UNPACK_SKIP_PIXELS):
                gl.glPixelStorei(name, 0)
            gl.glTextureSubImage2D(texture, 0, 0, 0, size[0], size[1], gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, rgba)
            gl.glGenerateTextureMipmap(texture)
        finally:
            gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, prior[gl.GL_PIXEL_UNPACK_BUFFER_BINDING])
            for name in (gl.GL_UNPACK_ALIGNMENT, gl.GL_UNPACK_ROW_LENGTH, gl.GL_UNPACK_SKIP_ROWS,
                         gl.GL_UNPACK_SKIP_PIXELS):
                gl.glPixelStorei(name, prior[name])

    def _delete(self, index: int) -> None:
        texture = self._slots[index][0]
        if texture:
            try:
                gl.glDeleteTextures([texture])
            except Exception as exc:
                raise RuntimeError(f"{self.label} backdrop cleanup incomplete: {exc}") from exc
        self._slots[index] = [0, None, None]

    def release(self) -> None:
        for index in (0, 1):
            self._delete(index)
        self._current = 0
        self._changed_at = None
        self._has_previous = False
