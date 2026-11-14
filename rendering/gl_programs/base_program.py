"""Abstract base class for per-transition GL shader programs.

Each concrete program helper holds its GLSL vertex/fragment source as properties
(create_program() compiles and links them). The Quick transitions draw with the
sources themselves (rendering/quick/transitions); the helpers own no GL context,
texture, draw call or animation timing.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

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
