"""Crumble transition shader program.

Crumble creates a rock-like crack pattern across the old image, then the pieces
fall away with physics-based motion to reveal the new image underneath. The
cracks form a Voronoi-like pattern with slightly randomized, organic edges.
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


class CrumbleProgram(BaseGLProgram):
    """Shader program for the Crumble transition effect."""

    @property
    def name(self) -> str:
        return "Crumble"

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
uniform float u_seed;       // Random seed for crack pattern variation
uniform float u_piece_count; // Approximate number of pieces (grid density)

// Hash functions for procedural randomness
float hash1(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

vec2 hash2(vec2 p) {
    p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
    return fract(sin(p) * 43758.5453);
}

// Voronoi distance for crack pattern
vec3 voronoi(vec2 uv, float scale, float seed) {
    vec2 p = uv * scale;
    vec2 ip = floor(p);
    vec2 fp = fract(p);
    
    float minDist = 10.0;
    float secondDist = 10.0;
    vec2 closestCell = vec2(0.0);
    
    // Check 3x3 neighborhood
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec2 neighbor = vec2(float(x), float(y));
            vec2 cellId = ip + neighbor;
            
            // Random point within cell, offset by seed
            vec2 point = hash2(cellId + seed * 0.1) * 0.8 + 0.1;
            point += neighbor;
            
            float d = length(fp - point);
            
            if (d < minDist) {
                secondDist = minDist;
                minDist = d;
                closestCell = cellId;
            } else if (d < secondDist) {
                secondDist = d;
            }
        }
    }
    
    // Edge distance (for cracks)
    float edge = secondDist - minDist;
    
    return vec3(closestCell, edge);
}

void main() {
    // Flip V to match Qt's top-left image origin
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    
    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);
    
    float t = clamp(u_progress, 0.0, 1.0);
    
    // Early exit for start/end states
    if (t <= 0.0) {
        FragColor = oldColor;
        return;
    }
    if (t >= 1.0) {
        FragColor = newColor;
        return;
    }
    
    // Scale for Voronoi pattern (more pieces = higher scale)
    float scale = max(4.0, u_piece_count);
    
    // Get Voronoi cell info
    vec3 vor = voronoi(uv, scale, u_seed);
    vec2 cellId = vor.xy;
    float edgeDist = vor.z;
    
    // Per-piece random values based on cell ID
    float pieceRand = hash1(cellId + u_seed);
    float pieceRand2 = hash1(cellId * 1.7 + u_seed + 100.0);
    
    // === PHASE 1: Crack formation (t = 0.0 to 0.3) ===
    float crackPhase = smoothstep(0.0, 0.3, t);
    
    // Cracks appear progressively based on piece random value
    // Pieces with lower random values crack first
    float crackThreshold = pieceRand * 0.8;
    float crackAppear = smoothstep(crackThreshold, crackThreshold + 0.15, crackPhase);
    
    // Crack line width (thin dark lines between pieces)
    float crackWidth = 0.08;
    float crackLine = 1.0 - smoothstep(0.0, crackWidth, edgeDist);
    crackLine *= crackAppear;
    
    // === PHASE 2: Pieces start falling (t = 0.25 to 1.0) ===
    float fallPhase = smoothstep(0.25, 1.0, t);
    
    // Each piece has a different fall start time based on its position and randomness
    // Pieces at the bottom fall first (like gravity pulling them down)
    float yBias = 1.0 - (cellId.y / scale); // Bottom pieces have higher bias
    float fallStart = pieceRand * 0.4 + yBias * 0.3;
    float pieceFall = smoothstep(fallStart, fallStart + 0.3, fallPhase);
    
    // Fall physics: accelerating downward motion
    float fallDistance = pieceFall * pieceFall * 2.0; // Quadratic for acceleration
    
    // Slight rotation during fall (pieces tumble)
    float rotation = pieceFall * (pieceRand2 - 0.5) * 0.5;
    
    // Horizontal drift (pieces don't fall straight down)
    float drift = pieceFall * (pieceRand - 0.5) * 0.3;
    
    // Calculate displaced UV for the falling piece
    vec2 pieceCenter = (cellId + 0.5) / scale;
    vec2 toCenter = uv - pieceCenter;
    
    // Apply rotation around piece center
    float cosR = cos(rotation);
    float sinR = sin(rotation);
    vec2 rotated = vec2(
        toCenter.x * cosR - toCenter.y * sinR,
        toCenter.x * sinR + toCenter.y * cosR
    );
    
    // Apply fall displacement
    vec2 displaced = pieceCenter + rotated;
    displaced.y += fallDistance;
    displaced.x += drift;
    
    // Check if this pixel is still part of a visible piece
    // Pieces that have fallen off screen are invisible
    float visible = 1.0 - step(1.2, displaced.y); // Fade out when piece falls below screen
    visible *= 1.0 - pieceFall * 0.3; // Gradual fade during fall
    
    // Sample old image at displaced position for falling pieces
    vec4 fallingColor = texture(uOldTex, clamp(displaced, 0.0, 1.0));
    
    // === Combine phases ===
    
    // Darken cracks
    vec3 crackedOld = oldColor.rgb * (1.0 - crackLine * 0.7);
    
    // Mix between cracked old image and falling pieces
    float useFalling = pieceFall * visible;
    vec3 pieceColor = mix(crackedOld, fallingColor.rgb, useFalling * 0.5);
    
    // Reveal new image where pieces have fallen away
    float reveal = pieceFall * (1.0 - visible * 0.7);
    
    // Final blend
    vec3 finalColor = mix(pieceColor, newColor.rgb, reveal);
    
    // Add subtle shadow under falling pieces
    float shadow = pieceFall * visible * 0.2;
    finalColor = mix(finalColor, vec3(0.0), shadow * (1.0 - edgeDist));
    
    FragColor = vec4(finalColor, 1.0);
}
"""

    def cache_uniforms(self, program: int) -> Dict[str, int]:
        """Cache uniform locations for the Crumble program."""
        if gl is None:
            return {}
        return {
            "u_progress": gl.glGetUniformLocation(program, "u_progress"),
            "u_resolution": gl.glGetUniformLocation(program, "u_resolution"),
            "uOldTex": gl.glGetUniformLocation(program, "uOldTex"),
            "uNewTex": gl.glGetUniformLocation(program, "uNewTex"),
            "u_seed": gl.glGetUniformLocation(program, "u_seed"),
            "u_piece_count": gl.glGetUniformLocation(program, "u_piece_count"),
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
        """Draw one frame of the Crumble transition.
        
        Args:
            program: GL program ID
            uniforms: Dict of uniform locations from cache_uniforms()
            viewport: (width, height) of the viewport
            old_tex: GL texture ID for old image
            new_tex: GL texture ID for new image
            state: CrumbleState dataclass with progress, seed, piece_count
            quad_vao: VAO for fullscreen quad
        """
        if gl is None:
            return

        vp_w, vp_h = viewport
        progress = max(0.0, min(1.0, float(getattr(state, "progress", 0.0))))
        seed = float(getattr(state, "seed", 0.0))
        piece_count = float(getattr(state, "piece_count", 8.0))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(program)
        try:
            # Set uniforms
            if uniforms.get("u_progress", -1) != -1:
                gl.glUniform1f(uniforms["u_progress"], float(progress))

            if uniforms.get("u_resolution", -1) != -1:
                gl.glUniform2f(uniforms["u_resolution"], float(vp_w), float(vp_h))

            if uniforms.get("u_seed", -1) != -1:
                gl.glUniform1f(uniforms["u_seed"], float(seed))

            if uniforms.get("u_piece_count", -1) != -1:
                gl.glUniform1f(uniforms["u_piece_count"], float(piece_count))

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


# Singleton instance for convenience
crumble_program = CrumbleProgram()
