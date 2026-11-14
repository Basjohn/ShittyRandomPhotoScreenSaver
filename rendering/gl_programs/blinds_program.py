"""Blinds transition shader program.

Blinds is modelled as horizontal bands within each grid cell that grow
symmetrically from the centre outwards. At t=0 the bands are collapsed
to thin lines; by t=1 they cover the full cell width.
"""

from __future__ import annotations

from rendering.gl_programs.base_program import BaseGLProgram


class BlindsProgram(BaseGLProgram):
    """Shader program for the Blinds transition effect."""

    @property
    def name(self) -> str:
        return "Blinds"

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
layout(std140, binding = 18) uniform BlindsPass {
    mat4 uMatrix;
    vec2 uItemSize;
    float u_progress;
    vec2 u_resolution;
    vec2 u_grid;        // (cols, rows)
    float u_feather;     // soft-edge width (0..0.5)
    int u_direction;     // 0=Horizontal, 1=Vertical, 2=Diagonal
};

void main() {
    // Flip V to match Qt's top-left image origin.
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    // Logical grid in UV space; when u_grid is unset we fall back to a
    // single full-frame cell so the effect still works.
    vec2 grid = max(u_grid, vec2(1.0));

    float coord;
    if (u_direction == 2) {
        // Diagonal: true screen-spanning diagonal bands.
        // Project UV onto the diagonal axis (top-left → bottom-right).
        // Use the average of grid.x and grid.y as the band count so the
        // number of diagonal stripes scales with the configured grid.
        float bands = max(1.0, (grid.x + grid.y) * 0.5);
        float diag = (uv.x + uv.y) * 0.5;  // 0..1 along diagonal
        coord = fract(diag * bands);         // repeat into bands
    } else {
        // Horizontal / Vertical: per-cell bands as before.
        vec2 cell = clamp(floor(uv * grid), vec2(0.0), grid - vec2(1.0));
        vec2 cellOrigin = cell / grid;
        vec2 cellSize = vec2(1.0) / grid;
        vec2 uvLocal = (uv - cellOrigin) / cellSize; // 0..1 inside cell

        if (u_direction == 1) {
            coord = uvLocal.y;
        } else {
            coord = uvLocal.x;
        }
    }

    // Blinds are modelled as bands that grow symmetrically from the centre
    // outwards. At t=0 the band is collapsed to a thin line; by t=1 it
    // covers the full cell / stripe.
    float w = clamp(t, 0.0, 1.0);
    float halfWidth = 0.5 * w;
    float left = 0.5 - halfWidth;
    float right = 0.5 + halfWidth;

    // Soft edges so the band does not appear as a harsh 1px stripe.
    float feather = clamp(u_feather, 0.001, 0.5);
    float edgeL = smoothstep(left - feather, left, coord);
    float edgeR = 1.0 - smoothstep(right, right + feather, coord);
    float bandMask = clamp(edgeL * edgeR, 0.0, 1.0);

    // Late global tail to guarantee we land on a fully revealed frame even
    // if numerical jitter leaves small gaps in the band coverage.
    float tail = smoothstep(0.96, 1.0, t);
    float mixFactor = clamp(max(bandMask, tail), 0.0, 1.0);

    FragColor = mix(oldColor, newColor, mixFactor);
}
"""


# Singleton instance for convenience
blinds_program = BlindsProgram()
