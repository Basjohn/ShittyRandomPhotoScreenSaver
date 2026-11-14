"""Slide transition shader program.

Slide moves the old image out while the new image slides in from the opposite
direction. The shader uses rect uniforms to position both images.
"""

from __future__ import annotations

from rendering.gl_programs.base_program import BaseGLProgram


class SlideProgram(BaseGLProgram):
    """Shader program for the Slide transition effect."""

    @property
    def name(self) -> str:
        return "Slide"

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
        # Optimized: Uses branchless bounds checking with step() for better GPU performance.
        # This eliminates thread divergence from if-statements.
        return """#version 460 core
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;

layout(binding = 0) uniform sampler2D uOldTex;
layout(binding = 1) uniform sampler2D uNewTex;
// The pass block (N1.6): one std140 block at the pass-block binding (SCENE3D_PASS_BLOCK_BINDING).
layout(std140, binding = 18) uniform SlideRectsPass {
    float u_progress;
    vec4 u_oldRect; // xy = pos, zw = size, in normalised viewport coords
    vec4 u_newRect; // xy = pos, zw = size, in normalised viewport coords
};

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    // Compute rect bounds
    vec2 oldMin = u_oldRect.xy;
    vec2 oldMax = u_oldRect.xy + u_oldRect.zw;
    vec2 newMin = u_newRect.xy;
    vec2 newMax = u_newRect.xy + u_newRect.zw;

    // Branchless bounds checking using step()
    // inOld = 1.0 if uv is inside old rect, 0.0 otherwise
    float inOld = step(oldMin.x, uv.x) * step(uv.x, oldMax.x) *
                  step(oldMin.y, uv.y) * step(uv.y, oldMax.y);
    
    // inNew = 1.0 if uv is inside new rect, 0.0 otherwise
    float inNew = step(newMin.x, uv.x) * step(uv.x, newMax.x) *
                  step(newMin.y, uv.y) * step(uv.y, newMax.y);

    // Compute texture coordinates (safe division)
    vec2 oldSpan = max(u_oldRect.zw, vec2(1e-5));
    vec2 newSpan = max(u_newRect.zw, vec2(1e-5));
    vec2 oldLocal = (uv - oldMin) / oldSpan;
    vec2 newLocal = (uv - newMin) / newSpan;

    // Sample textures (GPU prefetch friendly - always sample both)
    vec4 oldColor = texture(uOldTex, oldLocal);
    vec4 newColor = texture(uNewTex, newLocal);

    // Start with black background
    vec4 color = vec4(0.0, 0.0, 0.0, 1.0);
    
    // Layer old image where visible
    color = mix(color, oldColor, inOld);
    
    // Layer new image on top where visible (new always wins in overlap)
    color = mix(color, newColor, inNew);

    FragColor = color;
}
"""


# Singleton instance for convenience
slide_program = SlideProgram()
