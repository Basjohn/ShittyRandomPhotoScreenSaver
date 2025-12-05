"""Abstract base class for per-transition GL shader programs.

Each concrete program helper implements:
- GLSL vertex/fragment source as properties
- create_program() to compile and link
- cache_uniforms() to store uniform locations
- render() to draw one frame given current state

Helpers do NOT own GL contexts, textures, or animation timing. They are pure
renderers invoked by the compositor.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

# PyOpenGL import with graceful fallback
try:
    from OpenGL import GL as gl
except ImportError:
    gl = None  # type: ignore


class BaseGLProgram(ABC):
    """Abstract base for per-transition shader programs."""

    # Shared vertex shader for fullscreen quad transitions.
    # Subclasses can override if they need custom vertex logic.
    FULLSCREEN_VERTEX_SHADER = """
#version 330 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUV;
out vec2 vUV;
void main() {
    gl_Position = vec4(aPos, 0.0, 1.0);
    vUV = aUV;
}
"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for logging."""
        pass

    @property
    def vertex_source(self) -> str:
        """GLSL vertex shader source. Override for custom vertex logic."""
        return self.FULLSCREEN_VERTEX_SHADER

    @property
    @abstractmethod
    def fragment_source(self) -> str:
        """GLSL fragment shader source."""
        pass

    def create_program(self) -> int:
        """Compile and link shader program, return program ID.
        
        Raises RuntimeError on compilation/link failure.
        """
        if gl is None:
            raise RuntimeError("PyOpenGL not available")

        vs = self._compile_shader(self.vertex_source, gl.GL_VERTEX_SHADER)
        fs = self._compile_shader(self.fragment_source, gl.GL_FRAGMENT_SHADER)

        program = gl.glCreateProgram()
        gl.glAttachShader(program, vs)
        gl.glAttachShader(program, fs)
        gl.glLinkProgram(program)

        # Check link status
        link_status = gl.glGetProgramiv(program, gl.GL_LINK_STATUS)
        if not link_status:
            info_log = gl.glGetProgramInfoLog(program)
            gl.glDeleteProgram(program)
            gl.glDeleteShader(vs)
            gl.glDeleteShader(fs)
            raise RuntimeError(f"{self.name} program link failed: {info_log}")

        # Shaders can be detached after linking
        gl.glDetachShader(program, vs)
        gl.glDetachShader(program, fs)
        gl.glDeleteShader(vs)
        gl.glDeleteShader(fs)

        logger.debug("[GL PROGRAM] %s shader program created: %d", self.name, program)
        return int(program)

    def _compile_shader(self, source: str, shader_type: int) -> int:
        """Compile a single shader, return shader ID.
        
        Raises RuntimeError on compilation failure.
        """
        if gl is None:
            raise RuntimeError("PyOpenGL not available")

        shader = gl.glCreateShader(shader_type)
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)

        compile_status = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)
        if not compile_status:
            info_log = gl.glGetShaderInfoLog(shader)
            gl.glDeleteShader(shader)
            type_name = "vertex" if shader_type == gl.GL_VERTEX_SHADER else "fragment"
            raise RuntimeError(f"{self.name} {type_name} shader compile failed: {info_log}")

        return int(shader)

    @abstractmethod
    def cache_uniforms(self, program: int) -> Dict[str, int]:
        """Cache uniform locations for the program.
        
        Returns a dict mapping uniform name to location.
        """
        pass

    @abstractmethod
    def render(
        self,
        program: int,
        uniforms: Dict[str, int],
        viewport: Tuple[int, int],
        old_tex: int,
        new_tex: int,
        state: Any,
        quad_vao: int,
    ) -> None:
        """Draw one frame of the transition.
        
        Args:
            program: GL program ID
            uniforms: Dict of uniform locations from cache_uniforms()
            viewport: (width, height) of the viewport
            old_tex: GL texture ID for old image
            new_tex: GL texture ID for new image
            state: Transition-specific state dataclass
            quad_vao: VAO for fullscreen quad
        """
        pass

    def _draw_fullscreen_quad(self, quad_vao: int) -> None:
        """Draw the fullscreen quad using the provided VAO."""
        if gl is None:
            return
        gl.glBindVertexArray(quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        gl.glBindVertexArray(0)

    def _get_uniform_location(self, program: int, name: str) -> int:
        """Get uniform location, returning -1 if not found."""
        if gl is None:
            return -1
        return gl.glGetUniformLocation(program, name)
