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
#version 460 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUV;
layout(location = 0) out vec2 vUV;
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

        Links through the one program link owner (``gl_resources.compile_program``: the program binary cache
        included). Raises RuntimeError on compilation/link failure.
        """
        if gl is None:
            raise RuntimeError("PyOpenGL not available")
        from rendering.quick.render.gl_resources import compile_program

        program = compile_program(self.vertex_source, self.fragment_source, label=self.name)
        logger.debug("[GL PROGRAM] %s shader program created: %d", self.name, program)
        return int(program)

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
