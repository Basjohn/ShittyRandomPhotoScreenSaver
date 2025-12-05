"""Peel transition shader program.

Peel is implemented as a fullscreen-quad shader that always draws the new image
as the stable base frame while strips of the old image slide and fade away along
a configured direction. Each logical strip has a small per-strip timing offset
so the wave feels organic rather than perfectly synchronous.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from rendering.gl_programs.base_program import BaseGLProgram

logger = logging.getLogger(__name__)

# PyOpenGL import with graceful fallback
try:
    from OpenGL import GL as gl
except ImportError:
    gl = None  # type: ignore


class PeelProgram(BaseGLProgram):
    """Shader program for the Peel transition effect."""

    @property
    def name(self) -> str:
        return "Peel"

    @property
    def vertex_source(self) -> str:
        return """#version 410 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUv;

out vec2 vUv;

void main() {
    vUv = aUv;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

    @property
    def fragment_source(self) -> str:
        return """#version 410 core
in vec2 vUv;
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform vec2 u_resolution;
uniform vec2 u_direction;  // peel travel direction
uniform float u_strips;    // logical strip count

float hash1(float n) {
    return fract(sin(n) * 43758.5453123);
}

void main() {
    // Flip V to match Qt's top-left image origin.
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    if (t <= 0.0) {
        FragColor = oldColor;
        return;
    }
    if (t >= 1.0) {
        FragColor = newColor;
        return;
    }

    // Normalised peel direction.
    vec2 dir = u_direction;
    if (length(dir) < 1e-3) {
        dir = vec2(-1.0, 0.0);  // Default: peel left
    } else {
        dir = normalize(dir);
    }

    float strips = max(u_strips, 1.0);

    // Choose a 1D coordinate along the strip index based on direction.
    // Horizontal peel (LEFT/RIGHT): strips are vertical, indexed by X
    // Vertical peel (UP/DOWN): strips are horizontal, indexed by Y
    bool horizontal = abs(dir.x) >= abs(dir.y);
    float axisCoord = horizontal ? uv.x : uv.y;

    // For RIGHT or DOWN directions, reverse the strip ordering so strips
    // peel from the opposite edge (matching the visual expectation).
    bool reverseOrder = (horizontal && dir.x > 0.0) || (!horizontal && dir.y > 0.0);
    if (reverseOrder) {
        axisCoord = 1.0 - axisCoord;
    }

    axisCoord = clamp(axisCoord, 0.0, 1.0);
    float stripIndex = floor(axisCoord * strips + 1e-4);

    // Sequential per-strip timing: early strips start earlier, later strips
    // start later but all complete by t = 1.0.
    float start = 0.0;
    if (strips > 1.0) {
        float delay_per_strip = 0.7 / (strips - 1.0);
        start = delay_per_strip * stripIndex;
    }

    float local;
    if (t <= start) {
        local = 0.0;
    } else {
        float span = max(1.0 - start, 1e-4);
        local = clamp((t - start) / span, 0.0, 1.0);
    }

    // If this strip has completely peeled away, only the new image remains.
    if (local >= 1.0) {
        FragColor = newColor;
        return;
    }

    // Local coordinate within this logical strip in [0,1).
    float segPos = fract(axisCoord * strips);
    float baseWidth = 0.30;  // 30% thinner strips
    float width = mix(1.0, baseWidth, local);
    float halfBand = 0.5 * width;
    float bandMin = 0.5 - halfBand;
    float bandMax = 0.5 + halfBand;

    // Slide the strip off-screen along the peel direction.
    float travel = 1.2;
    vec2 shifted = uv + dir * local * travel;

    // Recompute the band mask in shifted space.
    float shiftedAxisCoord = horizontal ? shifted.x : shifted.y;
    if (reverseOrder) {
        shiftedAxisCoord = 1.0 - shiftedAxisCoord;
    }
    float segPosShifted = fract(clamp(shiftedAxisCoord, 0.0, 1.0) * strips);
    float inBandShifted = step(bandMin, segPosShifted) * step(segPosShifted, bandMax);

    // Only sample old image where the shifted strip still overlaps it.
    float inside = 0.0;
    if (shifted.x >= 0.0 && shifted.x <= 1.0 && shifted.y >= 0.0 && shifted.y <= 1.0) {
        inside = 1.0;
    }

    vec4 peeledOld = texture(uOldTex, shifted);

    // Opacity: fade as the strip peels.
    float fade = 1.0 - local;
    float alpha = inside * inBandShifted * fade * fade;

    // Global tail to ensure clean landing on new image.
    float tail = smoothstep(0.90, 1.0, t);
    alpha *= (1.0 - tail);

    vec4 color = mix(newColor, peeledOld, clamp(alpha, 0.0, 1.0));
    FragColor = color;
}
"""

    def cache_uniforms(self, program: int) -> Dict[str, int]:
        """Cache uniform locations for the Peel program."""
        if gl is None:
            return {}
        return {
            "u_progress": gl.glGetUniformLocation(program, "u_progress"),
            "u_resolution": gl.glGetUniformLocation(program, "u_resolution"),
            "uOldTex": gl.glGetUniformLocation(program, "uOldTex"),
            "uNewTex": gl.glGetUniformLocation(program, "uNewTex"),
            "u_direction": gl.glGetUniformLocation(program, "u_direction"),
            "u_strips": gl.glGetUniformLocation(program, "u_strips"),
        }

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
        """Draw one frame of the Peel transition.
        
        Args:
            program: GL program ID
            uniforms: Dict of uniform locations from cache_uniforms()
            viewport: (width, height) of the viewport
            old_tex: GL texture ID for old image
            new_tex: GL texture ID for new image
            state: PeelState dataclass with progress, direction, strips
            quad_vao: VAO for fullscreen quad
        """
        if gl is None:
            return

        vp_w, vp_h = viewport
        progress = max(0.0, min(1.0, float(getattr(state, "progress", 0.0))))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(program)
        try:
            # Set progress uniform
            if uniforms.get("u_progress", -1) != -1:
                gl.glUniform1f(uniforms["u_progress"], float(progress))

            # Set resolution uniform
            if uniforms.get("u_resolution", -1) != -1:
                gl.glUniform2f(uniforms["u_resolution"], float(vp_w), float(vp_h))

            # Map direction to travel vector
            dx, dy = self._get_direction_vector(state)
            if uniforms.get("u_direction", -1) != -1:
                gl.glUniform2f(uniforms["u_direction"], float(dx), float(dy))

            # Set strip count
            if uniforms.get("u_strips", -1) != -1:
                try:
                    strips = max(1, int(getattr(state, "strips", 1)))
                except Exception:
                    strips = 1
                gl.glUniform1f(uniforms["u_strips"], float(strips))

            # Bind old texture to unit 0
            if uniforms.get("uOldTex", -1) != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, old_tex)
                gl.glUniform1i(uniforms["uOldTex"], 0)

            # Bind new texture to unit 1
            if uniforms.get("uNewTex", -1) != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, new_tex)
                gl.glUniform1i(uniforms["uNewTex"], 1)

            # Draw fullscreen quad
            self._draw_fullscreen_quad(quad_vao)

        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)

    def _get_direction_vector(self, state: Any) -> Tuple[float, float]:
        """Map SlideDirection to a cardinal travel vector.
        
        LEFT moves strips left, RIGHT moves them right, DOWN moves them down,
        UP moves them up.
        """
        try:
            direction = getattr(state, "direction", None)
            if direction is None:
                return (-1.0, 0.0)
            
            # Import here to avoid circular imports
            from transitions.slide_transition import SlideDirection
            
            if direction == SlideDirection.LEFT:
                return (-1.0, 0.0)
            elif direction == SlideDirection.RIGHT:
                return (1.0, 0.0)
            elif direction == SlideDirection.DOWN:
                return (0.0, 1.0)
            elif direction == SlideDirection.UP:
                return (0.0, -1.0)
        except Exception:
            pass
        return (-1.0, 0.0)


# Singleton instance for convenience
peel_program = PeelProgram()
