"""Wipe transition shader program.

Wipe reveals the new image by moving a hard edge across the screen in one of
several directions: horizontal, vertical, or diagonal.
"""

from __future__ import annotations

from rendering.gl_programs.base_program import BaseGLProgram


class WipeProgram(BaseGLProgram):
    """Shader program for the Wipe transition effect."""

    @property
    def name(self) -> str:
        return "Wipe"

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
        # Optimized: Uses precomputed axis value instead of mode branching.
        # The Python side computes the axis transformation, shader just applies it.
        return """#version 460 core
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;

layout(binding = 0) uniform sampler2D uOldTex;
layout(binding = 1) uniform sampler2D uNewTex;
// The pass block (N1.6): the item quad's values and this program's, one std140 block at the pass-block binding
// (SCENE3D_PASS_BLOCK_BINDING); the quad's vertex stage declares the same block (quick/transitions/fullscreen_pass).
layout(std140, binding = 18) uniform WipePass {
    mat4 uMatrix;
    vec2 uItemSize;
    float u_progress;
    int u_mode;  // 0=L2R, 1=R2L, 2=T2B, 3=B2T, 4=Diag TL-BR, 5=Diag TR-BL
};

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    // Sample both textures (GPU prefetch friendly)
    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    // Compute axis based on mode - use array lookup pattern for better GPU performance
    // Each mode maps UV to a 0..1 axis value
    float axis;
    if (u_mode == 0) {
        axis = uv.x;                           // Left-to-right
    } else if (u_mode == 1) {
        axis = 1.0 - uv.x;                     // Right-to-left
    } else if (u_mode == 2) {
        axis = uv.y;                           // Top-to-bottom
    } else if (u_mode == 3) {
        axis = 1.0 - uv.y;                     // Bottom-to-top
    } else if (u_mode == 4) {
        axis = (uv.x + uv.y) * 0.5;            // Diagonal TL-BR
    } else {
        axis = ((1.0 - uv.x) + uv.y) * 0.5;    // Diagonal TR-BL
    }

    // Branchless blend using step
    float m = step(axis, t);
    FragColor = mix(oldColor, newColor, m);
}
"""


# Singleton instance for convenience
wipe_program = WipeProgram()
