"""FBO Manager for resolution-scaled rendering.

Provides framebuffer objects for rendering transitions at reduced resolution
to improve performance, then upscaling to display resolution.
"""

from __future__ import annotations

import logging
from typing import Tuple
try:
    from OpenGL import GL as gl
except ImportError:
    gl = None

logger = logging.getLogger(__name__)


class FBOManager:
    """Manages framebuffer objects for resolution-scaled rendering.

    Features:
    - Automatic FBO creation and sizing
    - Resolution scaling (e.g., 0.75x for performance)
    - Texture attachment management
    - Cleanup and resource tracking

    Thread Safety:
    - All methods must be called from UI thread with valid GL context
    """

    def __init__(self, scale: float = 0.75):
        """Initialize FBO manager.

        Args:
            scale: Resolution scale factor (0.5-1.0). Lower = better performance.
        """
        self._scale = max(0.5, min(1.0, scale))
        self._fbo_id: int = 0
        self._texture_id: int = 0
        self._current_width: int = 0
        self._current_height: int = 0
        self._initialized: bool = False
        self._blit_program: int = 0
        self._blit_vao: int = 0
        self._blit_vbo: int = 0

    @property
    def scale(self) -> float:
        """Current resolution scale factor."""
        return self._scale

    @property
    def fbo_id(self) -> int:
        """Current FBO ID."""
        return self._fbo_id

    @property
    def texture_id(self) -> int:
        """Current FBO texture ID."""
        return self._texture_id

    def initialize(self, width: int, height: int) -> bool:
        """Initialize or resize FBO to match display size.

        Args:
            width: Display width in pixels
            height: Display height in pixels

        Returns:
            True if successful
        """
        if gl is None:
            logger.debug("[FBO] GL not available")
            return False

        scaled_w = max(1, int(width * self._scale))
        scaled_h = max(1, int(height * self._scale))

        # Check if we need to resize
        if self._initialized and self._current_width == scaled_w and self._current_height == scaled_h:
            return True

        # Cleanup old FBO if exists
        if self._initialized:
            self.cleanup()

        try:
            # Create FBO
            fbo = gl.glGenFramebuffers(1)
            self._fbo_id = int(fbo)
            logger.debug("[FBO] Created FBO id=%d for %dx%d", self._fbo_id, scaled_w, scaled_h)

            # Create texture for color attachment
            tex = gl.glGenTextures(1)
            self._texture_id = int(tex)

            # Setup texture
            gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture_id)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8,
                scaled_w, scaled_h, 0,
                gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None
            )
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

            # Attach texture to FBO
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo_id)
            gl.glFramebufferTexture2D(
                gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                gl.GL_TEXTURE_2D, self._texture_id, 0
            )

            # Check FBO completeness
            status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
            logger.debug("[FBO] Framebuffer status check: 0x%x (complete=0x%x)", status, gl.GL_FRAMEBUFFER_COMPLETE)
            if status != gl.GL_FRAMEBUFFER_COMPLETE:
                logger.warning("[FBO] Framebuffer incomplete: status=0x%x", status)
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
                self.cleanup()
                return False

            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)

            self._current_width = scaled_w
            self._current_height = scaled_h
            self._initialized = True

            logger.info("[PERF] [FBO] Initialized: %dx%d (scale=%.2f, display=%dx%d)",
                       scaled_w, scaled_h, self._scale, width, height)

            return True

        except Exception:
            logger.debug("[FBO] Initialization failed", exc_info=True)
            self.cleanup()
            return False

    def bind(self) -> bool:
        """Bind FBO for rendering.

        Returns:
            True if successful
        """
        if not self._initialized:
            logger.debug("[FBO] Bind failed: not initialized")
            return False
        if self._fbo_id == 0:
            logger.debug("[FBO] Bind failed: fbo_id=0")
            return False

        try:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._fbo_id)
            gl.glViewport(0, 0, self._current_width, self._current_height)
            return True
        except Exception:
            logger.debug("[FBO] Bind failed", exc_info=True)
            return False

    def unbind(self) -> None:
        """Unbind FBO, restore default framebuffer."""
        try:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        except Exception:
            logger.debug("[FBO] Unbind failed", exc_info=True)

    def _init_blit_shader(self) -> bool:
        """Initialize shader program for FBO blit."""
        if gl is None or self._blit_program != 0:
            return self._blit_program != 0

        try:
            # Simple vertex shader - fullscreen quad
            vs_source = """#version 410 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aTexCoord;
out vec2 vTexCoord;

void main() {
    vTexCoord = aTexCoord;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

            # Simple fragment shader - texture sampling
            fs_source = """#version 410 core
in vec2 vTexCoord;
out vec4 FragColor;
uniform sampler2D uTexture;

void main() {
    FragColor = texture(uTexture, vTexCoord);
}
"""

            # Compile shaders
            vs = gl.glCreateShader(gl.GL_VERTEX_SHADER)
            gl.glShaderSource(vs, vs_source)
            gl.glCompileShader(vs)

            fs = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
            gl.glShaderSource(fs, fs_source)
            gl.glCompileShader(fs)

            # Link program
            program = gl.glCreateProgram()
            gl.glAttachShader(program, vs)
            gl.glAttachShader(program, fs)
            gl.glLinkProgram(program)

            gl.glDeleteShader(vs)
            gl.glDeleteShader(fs)

            self._blit_program = int(program)

            # Create fullscreen quad VAO/VBO
            # Positions and UVs for fullscreen quad
            vertices = [
                -1.0, -1.0, 0.0, 0.0,  # bottom-left
                 1.0, -1.0, 1.0, 0.0,  # bottom-right
                -1.0,  1.0, 0.0, 1.0,  # top-left
                 1.0,  1.0, 1.0, 1.0,  # top-right
            ]

            import ctypes
            import array
            vertex_data = array.array('f', vertices)

            vao = gl.glGenVertexArrays(1)
            vbo = gl.glGenBuffers(1)

            gl.glBindVertexArray(vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, len(vertex_data) * 4, vertex_data.tobytes(), gl.GL_STATIC_DRAW)

            # Position attribute
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 16, ctypes.c_void_p(0))

            # TexCoord attribute
            gl.glEnableVertexAttribArray(1)
            gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, 16, ctypes.c_void_p(8))

            gl.glBindVertexArray(0)

            self._blit_vao = int(vao)
            self._blit_vbo = int(vbo)

            return True

        except Exception:
            logger.debug("[FBO] Blit shader init failed", exc_info=True)
            return False

    def blit_to_screen(self, display_width: int, display_height: int) -> bool:
        """Blit FBO texture to screen using shader-based rendering.

        Args:
            display_width: Target display width
            display_height: Target display height

        Returns:
            True if successful
        """
        if not self._initialized or self._texture_id == 0:
            return False

        try:
            # Initialize blit shader if needed
            if self._blit_program == 0:
                if not self._init_blit_shader():
                    return False

            # Restore default framebuffer and viewport
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            gl.glViewport(0, 0, display_width, display_height)

            # Use blit shader
            gl.glUseProgram(self._blit_program)

            # Bind FBO texture
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture_id)
            gl.glUniform1i(gl.glGetUniformLocation(self._blit_program, "uTexture"), 0)

            # Draw fullscreen quad
            gl.glBindVertexArray(self._blit_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glBindVertexArray(0)

            # Cleanup
            gl.glUseProgram(0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

            return True

        except Exception:
            logger.debug("[FBO] Blit failed", exc_info=True)
            return False

    def get_scaled_size(self, width: int, height: int) -> Tuple[int, int]:
        """Get scaled dimensions for given display size.

        Args:
            width: Display width
            height: Display height

        Returns:
            (scaled_width, scaled_height)
        """
        return (
            max(1, int(width * self._scale)),
            max(1, int(height * self._scale))
        )

    def cleanup(self) -> None:
        """Cleanup FBO and texture resources."""
        if gl is None:
            return

        try:
            if self._texture_id > 0:
                gl.glDeleteTextures(int(self._texture_id))
                self._texture_id = 0

            if self._fbo_id > 0:
                gl.glDeleteFramebuffers(int(self._fbo_id))
                self._fbo_id = 0

            if self._blit_vbo > 0:
                gl.glDeleteBuffers(int(self._blit_vbo))
                self._blit_vbo = 0

            if self._blit_vao > 0:
                gl.glDeleteVertexArrays(int(self._blit_vao))
                self._blit_vao = 0

            if self._blit_program > 0:
                gl.glDeleteProgram(int(self._blit_program))
                self._blit_program = 0

            self._initialized = False
            self._current_width = 0
            self._current_height = 0

        except Exception:
            logger.debug("[FBO] Cleanup failed", exc_info=True)
