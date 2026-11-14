"""Crossfade transition shader program.

Crossfade is the simplest transition: a linear blend between old and new images
based on progress. This serves as a good template for other simple transitions.
"""

from __future__ import annotations

from rendering.gl_programs.base_program import BaseGLProgram


class CrossfadeProgram(BaseGLProgram):
    """Shader program for the Crossfade transition effect."""

    @property
    def name(self) -> str:
        return "Crossfade"

    @property
    def vertex_source(self) -> str:
        return """#version 460 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUv;

layout(location = 0) out vec2 vUv;

void main() {
    vUv = aUv;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

    @property
    def fragment_source(self) -> str:
        return """#version 460 core
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;

layout(binding = 0) uniform sampler2D uOldTex;
layout(binding = 1) uniform sampler2D uNewTex;
// The pass block (N1.6): the item quad's values and this program's, one std140 block at the pass-block binding
// (SCENE3D_PASS_BLOCK_BINDING); the quad's vertex stage declares the same block (quick/transitions/fullscreen_pass).
layout(std140, binding = 18) uniform CrossfadePass {
    mat4 uMatrix;
    vec2 uItemSize;
    float u_progress;
};

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    FragColor = mix(oldColor, newColor, t);
}
"""


# Singleton instance for convenience
crossfade_program = CrossfadeProgram()
