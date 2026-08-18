"""Compositor-owned GL texture for the visualizer card visual.

The card image is already produced once by the card's own QPainter code and
cached as a ``QPixmap``. The first single-surface landing then drew that cached
pixmap through ``QOpenGLPaintDevice``/``QPainter`` on **every presented frame**,
so a steady ~60 Hz visualizer crossed

    raw GL -> QOpenGLPaintDevice -> QPainter -> drawPixmap -> end -> raw GL

for an image that had not changed. That bridge is pure steady-state presentation
work and a plausible contributor to the measured 55-58 FPS visualizer-only
cadence.

This uploads the authored pixmap to a GL texture when its cache revision
changes, and draws a textured quad thereafter. The source pixels remain the
existing authored ``QPixmap``: the card appearance is not reimplemented as a
procedural shader, so border thickness, rounded radius, painted shadow,
background opacity, CUSTOM geometry and DPR are whatever the card already
produced. Fade is applied as a cheap GL alpha multiplier rather than re-uploading
the texture per fade frame.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtGui import QImage

from core.logging.logger import get_logger

try:  # pragma: no cover - PyOpenGL is required for accelerated presentation
    from OpenGL import GL as gl  # type: ignore[import]
except ImportError:  # pragma: no cover
    gl = None

logger = get_logger(__name__)


_VERTEX_SHADER = """#version 330 core
layout(location = 0) in vec2 a_pos;
out vec2 v_uv;
void main() {
    // Quad is drawn in normalised device coordinates over the card viewport.
    // Texture rows arrive top-down from QImage, so V is flipped here rather
    // than by re-uploading a flipped image every revision.
    v_uv = vec2(a_pos.x * 0.5 + 0.5, 1.0 - (a_pos.y * 0.5 + 0.5));
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

_FRAGMENT_SHADER = """#version 330 core
in vec2 v_uv;
out vec4 fragColor;
uniform sampler2D u_card;
uniform float u_fade;
void main() {
    vec4 texel = texture(u_card, v_uv);
    // Fade is a cheap alpha multiplier; the texture itself is fade-independent
    // so a fade animation never re-uploads it.
    fragColor = vec4(texel.rgb, texel.a * u_fade);
}
"""


class CompositorCardTexture:
    """One GL texture per active compositor visualizer card.

    Ownership follows the established compositor contract: created and deleted
    on the compositor's borrowed QRhi OpenGL context, exactly one deletion owner
    per numeric handle, deletion failure retains ownership and fails closed.
    """

    def __init__(self, resource_group: str = "compositor_visualizer_card") -> None:
        self._texture = 0
        self._program = 0
        self._vao = 0
        self._vbo = 0
        self._revision: Optional[tuple] = None
        self._size_px: tuple[int, int] = (0, 0)
        self._bytes = 0
        self._resource_group = resource_group
        self._resource_id: Optional[str] = None
        self._uniform_card = -1
        self._uniform_fade = -1

    # -- identity ---------------------------------------------------------

    @property
    def revision(self) -> Optional[tuple]:
        return self._revision

    @property
    def texture_id(self) -> int:
        return self._texture

    @property
    def tracked_bytes(self) -> int:
        return self._bytes

    def has_texture(self) -> bool:
        return bool(self._texture)

    # -- upload -----------------------------------------------------------

    def ensure_uploaded(self, pixmap: Any, revision: tuple) -> bool:
        """Upload the card pixmap only when its cache revision changed.

        Ordinary visualizer state publications do not change the revision, so
        they must never re-upload.
        """
        if gl is None or pixmap is None or pixmap.isNull():
            return False
        if self._texture and self._revision == revision:
            return True

        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        width = int(image.width())
        height = int(image.height())
        if width <= 0 or height <= 0:
            return False

        if not self._texture:
            self._texture = int(gl.glGenTextures(1))

        gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0,
            gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, bytes(image.constBits()),
        )
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

        self._revision = revision
        self._size_px = (width, height)
        self._retrack_bytes(width * height * 4)
        return True

    def _retrack_bytes(self, byte_count: int) -> None:
        """Update ResourceManager accounting for the replaced texture bytes."""
        self._bytes = int(byte_count)
        try:
            from core.resources.manager import ResourceManager

            manager = ResourceManager.get_or_create_app_shared()
            if manager is None:
                return
            if self._resource_id:
                manager.release_tracking(self._resource_id)
                self._resource_id = None
            self._resource_id = manager.register_gl_handle(
                int(self._texture), "texture",
                description="Compositor visualizer card texture",
                group=self._resource_group,
                owner=self._resource_group,
                generation=id(self),
                dimensions=self._size_px,
                format="RGBA8",
                tracked_bytes=self._bytes,
            )
        except Exception:
            logger.debug("[VIS CARD] Card texture accounting unavailable", exc_info=True)

    # -- draw -------------------------------------------------------------

    def _ensure_program(self) -> bool:
        if self._program and self._vao:
            return True
        if gl is None:
            return False
        import numpy as np

        def _compile(kind, source):
            shader = gl.glCreateShader(kind)
            gl.glShaderSource(shader, source)
            gl.glCompileShader(shader)
            if not gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS):
                info = gl.glGetShaderInfoLog(shader)
                raise RuntimeError(f"card texture shader compile failed: {info}")
            return shader

        vs = _compile(gl.GL_VERTEX_SHADER, _VERTEX_SHADER)
        fs = _compile(gl.GL_FRAGMENT_SHADER, _FRAGMENT_SHADER)
        program = gl.glCreateProgram()
        gl.glAttachShader(program, vs)
        gl.glAttachShader(program, fs)
        gl.glLinkProgram(program)
        gl.glDeleteShader(vs)
        gl.glDeleteShader(fs)
        if not gl.glGetProgramiv(program, gl.GL_LINK_STATUS):
            info = gl.glGetProgramInfoLog(program)
            gl.glDeleteProgram(program)
            raise RuntimeError(f"card texture program link failed: {info}")

        vao = int(gl.glGenVertexArrays(1))
        vbo = int(gl.glGenBuffers(1))
        gl.glBindVertexArray(vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        vertices = np.array(
            [-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0], dtype="float32"
        )
        gl.glBufferData(
            gl.GL_ARRAY_BUFFER, int(vertices.nbytes), vertices, gl.GL_STATIC_DRAW
        )
        gl.glEnableVertexAttribArray(0)
        gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, False, 0, None)
        gl.glBindVertexArray(0)

        self._program = int(program)
        self._vao = vao
        self._vbo = vbo
        self._uniform_card = gl.glGetUniformLocation(self._program, "u_card")
        self._uniform_fade = gl.glGetUniformLocation(self._program, "u_fade")
        return True

    def draw(self, fade: float) -> bool:
        """Draw the cached card texture over the current viewport."""
        if gl is None or not self._texture:
            return False
        if not self._ensure_program():
            return False

        gl.glUseProgram(self._program)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture)
        if self._uniform_card != -1:
            gl.glUniform1i(self._uniform_card, 0)
        if self._uniform_fade != -1:
            gl.glUniform1f(self._uniform_fade, float(max(0.0, min(1.0, fade))))
        gl.glBindVertexArray(self._vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        gl.glBindVertexArray(0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glUseProgram(0)
        return True

    # -- teardown ---------------------------------------------------------

    def cleanup(self) -> None:
        """Delete owned handles exactly once; failure retains ownership."""
        if gl is None:
            return
        errors: list[str] = []

        if self._texture:
            try:
                gl.glDeleteTextures(1, [int(self._texture)])
            except Exception as exc:
                errors.append(f"card_texture:{type(exc).__name__}:{exc}")
            else:
                self._texture = 0
                self._revision = None
                try:
                    from core.resources.manager import ResourceManager

                    manager = ResourceManager.get_or_create_app_shared()
                    if manager is not None and self._resource_id:
                        manager.release_tracking(self._resource_id)
                except Exception:
                    logger.debug("[VIS CARD] Card texture release failed", exc_info=True)
                self._resource_id = None
                self._bytes = 0

        if self._vao:
            try:
                gl.glDeleteVertexArrays(1, [int(self._vao)])
            except Exception as exc:
                errors.append(f"card_vao:{type(exc).__name__}:{exc}")
            else:
                self._vao = 0
        if self._vbo:
            try:
                gl.glDeleteBuffers(1, [int(self._vbo)])
            except Exception as exc:
                errors.append(f"card_vbo:{type(exc).__name__}:{exc}")
            else:
                self._vbo = 0
        if self._program:
            try:
                gl.glDeleteProgram(int(self._program))
            except Exception as exc:
                errors.append(f"card_program:{type(exc).__name__}:{exc}")
            else:
                self._program = 0

        if errors:
            raise RuntimeError(
                "Visualizer card texture deletion incomplete: " + " | ".join(errors)
            )
