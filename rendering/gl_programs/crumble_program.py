"""Crumble transition shader program.

Crumble creates a rock-like crack pattern across the old image, then the pieces
fall away with physics-based motion to reveal the new image underneath. The
cracks form a Voronoi-like pattern with randomized, organic edges and optional
grain texture during crack formation.

Settings:
- u_piece_count: Number of pieces (4-16, default 8)
- u_crack_complexity: Crack detail level (0.5-2.0, default 1.0)
- u_mosaic_mode: 0=normal crumble, 1=glass shatter with 3D depth
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
uniform float u_seed;           // Random seed for crack pattern variation
uniform float u_piece_count;    // Approximate number of pieces (grid density)
uniform float u_crack_complexity; // Crack detail level (0.5-2.0)
uniform float u_mosaic_mode;    // 0=crumble, 1=glass shatter
uniform float u_weight_mode;    // 0=Top,1=Bottom,2=Random Weighted,3=Random Choice,4=Age Weighted

// Hash functions for procedural randomness with better distribution
float hash1(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

vec2 hash2(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.xx + p3.yz) * p3.zy);
}

// Noise for grain effect
float noise(vec2 p) {
    vec2 ip = floor(p);
    vec2 fp = fract(p);
    fp = fp * fp * (3.0 - 2.0 * fp); // Smoothstep
    
    float a = hash1(ip);
    float b = hash1(ip + vec2(1.0, 0.0));
    float c = hash1(ip + vec2(0.0, 1.0));
    float d = hash1(ip + vec2(1.0, 1.0));
    
    return mix(mix(a, b, fp.x), mix(c, d, fp.x), fp.y);
}

// Voronoi distance for crack pattern with randomized edges
vec4 voronoi(vec2 uv, float scale, float seed, float complexity) {
    vec2 p = uv * scale;
    vec2 ip = floor(p);
    vec2 fp = fract(p);
    
    float minDist = 10.0;
    float secondDist = 10.0;
    vec2 closestCell = vec2(0.0);
    vec2 closestPoint = vec2(0.0);
    
    // Check 3x3 neighborhood
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec2 neighbor = vec2(float(x), float(y));
            vec2 cellId = ip + neighbor;
            
            // Random point within cell with seed-based variation
            // Add complexity-based jitter for more organic shapes
            vec2 jitter = hash2(cellId + seed * 0.1);
            float jitterAmount = 0.6 + complexity * 0.2;
            vec2 point = jitter * jitterAmount + (1.0 - jitterAmount) * 0.5;
            point += neighbor;
            
            // Add slight distortion based on position for non-uniform cells
            float distort = hash1(cellId * 2.3 + seed) * 0.15 * complexity;
            point += vec2(sin(cellId.y * 3.14), cos(cellId.x * 3.14)) * distort;
            
            float d = length(fp - point);
            
            if (d < minDist) {
                secondDist = minDist;
                minDist = d;
                closestCell = cellId;
                closestPoint = point;
            } else if (d < secondDist) {
                secondDist = d;
            }
        }
    }
    
    // Edge distance (for cracks) with slight noise for rough edges
    float edge = secondDist - minDist;
    float edgeNoise = noise(uv * scale * 8.0 + seed) * 0.02 * complexity;
    edge += edgeNoise;
    
    return vec4(closestCell, edge, hash1(closestCell + seed));
}

// Sub-crack pattern within pieces (forms just before falling)
float subCracks(vec2 uv, vec2 cellId, float seed, float intensity) {
    // Create smaller cracks within each piece
    vec2 localUv = fract(uv * 4.0 + cellId * 0.5);
    float n1 = noise(localUv * 20.0 + seed * 10.0);
    float n2 = noise(localUv * 35.0 + seed * 7.0);
    
    // Create crack-like lines from noise
    float crack = abs(n1 - 0.5) * 2.0;
    crack = 1.0 - step(0.15, crack);
    crack *= abs(n2 - 0.5) > 0.3 ? 1.0 : 0.0;
    
    return crack * intensity;
}

// Helper to get piece transform for a given cell
void getPieceTransform(vec2 cellId, float scale, float t, float seed,
                       out float pieceFall, out float fallDist, out float driftX, out float rotAngle) {
    float pieceRand = hash1(cellId + seed);
    float pieceRand2 = hash1(cellId * 1.7 + seed + 100.0);
    
    int mode = int(floor(u_weight_mode + 0.5));
    // Random Choice picks one of the other modes once based on seed
    if (mode == 3) {
        float choice = hash1(vec2(seed * 0.73, seed * 1.31));
        if (choice < 0.33) mode = 0;
        else if (choice < 0.66) mode = 1;
        else mode = 2;
    }
    float ageRand = hash1(cellId * 3.11 + seed * 2.7);
    
    float baseY = cellId.y / scale;
    float weightedY;
    if (mode == 0) {            // Top weighted
        weightedY = baseY;
    } else if (mode == 1) {     // Bottom weighted
        weightedY = 1.0 - baseY;
    } else if (mode == 2) {     // Random Weighted per piece
        float coin = pieceRand > 0.5 ? 1.0 : 0.0;
        weightedY = mix(baseY, 1.0 - baseY, coin);
    } else {                    // Age Weighted (based on per-piece crack age hash)
        weightedY = ageRand;
    }
    
    // Slight jitter so pieces don't move as a monolith
    weightedY += (pieceRand - 0.5) * 0.08;
    weightedY = clamp(weightedY, 0.0, 1.0);
    
    // Stagger with randomness; bias from weighting but everyone can fall
    float fallDelay = weightedY * 0.20 + pieceRand * 0.10;  // Max delay ~0.30
    
    // Fall phase: starts at t=0.05 (cracks form first), ends at t=0.95
    float fallPhase = (t - 0.05) / 0.90;
    fallPhase = clamp(fallPhase, 0.0, 1.0);
    
    // Per-piece progress accounting for staggered start
    pieceFall = fallPhase > fallDelay ? (fallPhase - fallDelay) / (1.0 - fallDelay) : 0.0;
    pieceFall = clamp(pieceFall, 0.0, 1.0);
    
    // Per-piece fall speed variation
    float fallSpeed = 0.90 + pieceRand2 * 0.30;  // 0.9x - 1.2x speed
    
    // Accelerating fall with cubic easing; ensure enough distance to leave screen on high DPI
    float accel = pieceFall * pieceFall * pieceFall;  // Cubic for faster acceleration
    fallDist = accel * (7.5 * fallSpeed);  // More breathing room to exit screen
    
    driftX = pieceFall * (pieceRand - 0.5) * 0.3;
    // Increased rotation amplitude for more visible spin
    rotAngle = pieceFall * (pieceRand2 - 0.5) * 3.75;
}

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    
    vec4 newColor = texture(uNewTex, uv);
    float t = clamp(u_progress, 0.0, 1.0);
    
    if (t <= 0.0) {
        FragColor = texture(uOldTex, uv);
        return;
    }
    // At t >= 0.995, all pieces should be off-screen, show clean new image
    // With the compressed fall phase (ends at t=0.95), pieces have 5% buffer
    // to fully exit before this cutoff
    if (t >= 0.995) {
        FragColor = newColor;
        return;
    }
    
    float scale = max(4.0, u_piece_count);
    float complexity = clamp(u_crack_complexity, 0.5, 2.0);
    
    // Crack width - visible borders on pieces
    float crackWidth = 0.025 + complexity * 0.012;
    // Border width for dark outline around cracks (thicker for visibility with dimming)
    float borderWidth = crackWidth + 0.020;
    
    vec3 finalColor = newColor.rgb;
    bool pixelCovered = false;
    float bestFall = 1.0;
    float totalShadow = 0.0;
    
    // Get the cell at current screen position as starting point
    vec4 vorHere = voronoi(uv, scale, u_seed, complexity);
    
    // Search nearby cells - pieces fall DOWNWARD so we need to search UPWARD
    // (negative dy in cell space) to find pieces that started above and fell here.
    // 
    // Max fall distance is ~1.4 UV units (top piece falling to bottom + margin).
    // In cell space with scale=8, that's ~11 cells. But we use aggressive early-exit
    // to skip most iterations. The bounds check eliminates ~90% of candidates.
    //
    // Search range: dy from -16 to +2 (wider for larger fall distance and DPI)
    // With early exits, actual work per pixel is typically limited.
    for (int dy = -16; dy <= 2; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            vec2 candidateCell = vorHere.xy + vec2(float(dx), float(dy));
            
            // Skip cells far outside valid range
            // Allow y < 0 (cells above screen) to cover top edge voronoi patterns
            // Allow y >= scale (cells below screen) for bottom edge
            if (candidateCell.y < -1.0 || candidateCell.y > scale) continue;
            if (candidateCell.x < -1.0 || candidateCell.x > scale) continue;
            
            // Get this cell's transform
            float pieceFall, fallDist, driftX, rotAngle;
            getPieceTransform(candidateCell, scale, t, u_seed, pieceFall, fallDist, driftX, rotAngle);
            
            // Early exit: if piece hasn't started falling and isn't our cell, skip
            if (pieceFall < 0.001 && candidateCell != vorHere.xy) continue;
            
            // Where is this cell's center now?
            vec2 originalCenter = (candidateCell + 0.5) / scale;
            vec2 movedCenter = originalCenter + vec2(driftX, fallDist);
            
            // Quick bounds check - skip if piece is nowhere near this pixel
            // This eliminates most candidates without expensive voronoi call
            float cellSize = 1.0 / scale;
            if (abs(uv.x - movedCenter.x) > cellSize * 1.2) continue;
            if (abs(uv.y - movedCenter.y) > cellSize * 1.2) continue;
            
            // Inverse transform: find what original point maps to current screen pos
            vec2 fromMoved = uv - movedCenter;
            float cosR = cos(-rotAngle);
            float sinR = sin(-rotAngle);
            vec2 unrotated = vec2(
                fromMoved.x * cosR - fromMoved.y * sinR,
                fromMoved.x * sinR + fromMoved.y * cosR
            );
            vec2 originalPos = originalCenter + unrotated;
            
            // Check if this original position belongs to this Voronoi cell
            vec4 vorCheck = voronoi(originalPos, scale, u_seed, complexity);
            
            if (vorCheck.xy == candidateCell) {
                if (originalPos.x >= 0.0 && originalPos.x <= 1.0 && 
                    originalPos.y >= 0.0 && originalPos.y <= 1.0) {
                    
                    if (!pixelCovered || pieceFall < bestFall) {
                        pixelCovered = true;
                        bestFall = pieceFall;
                        
                        // Sample texture at original position
                        vec4 oldColor = texture(uOldTex, originalPos);
                        finalColor = oldColor.rgb;
                        float fadePiece = 1.0 - smoothstep(0.93, 1.0, pieceFall);
                        
                        // Crack lines with dark border
                        float crackPhase = t / 0.25;  // Cracks appear early
                        crackPhase = clamp(crackPhase, 0.0, 1.0);
                        float pieceRandCrack = hash1(candidateCell + u_seed);
                        float crackAppear = crackPhase > pieceRandCrack * 0.2 ? 1.0 : 0.0;
                        
                        // Once piece starts falling, always show the border
                        bool showBorder = crackAppear > 0.5 || pieceFall > 0.01;
                        
                        if (showBorder) {
                            // Calculate distance to screen edge (for pieces at screen boundary)
                            // This ensures top/left/right/bottom pieces have visible borders
                            float edgeDist = min(min(originalPos.x, 1.0 - originalPos.x),
                                                 min(originalPos.y, 1.0 - originalPos.y));
                            // Use the minimum of Voronoi edge distance and screen edge distance
                            float effectiveEdge = min(vorCheck.z, edgeDist * 8.0);  // Scale screen edge to match Voronoi units
                            
                            // Dark border zone (outer edge of piece)
                            if (effectiveEdge < borderWidth && effectiveEdge >= crackWidth) {
                                // Soft dark border - blend based on distance
                                float borderBlend = 1.0 - (effectiveEdge - crackWidth) / (borderWidth - crackWidth);
                                borderBlend = borderBlend * borderBlend; // Quadratic falloff
                                finalColor = mix(finalColor, vec3(0.0), borderBlend * 0.6);
                            }
                            // Inner crack (darkest)
                            if (effectiveEdge < crackWidth) {
                                finalColor = vec3(0.0);  // Pure black crack
                            }
                        }
                        
                        // Piece gets slightly darker as it falls
                        float pieceShadow = pieceFall * 0.12;
                        finalColor *= (1.0 - pieceShadow);
                        // Fade piece into underlying new image near end of its fall
                        finalColor = mix(newColor.rgb, finalColor, fadePiece);
                    }
                }
            }
        }
    }
    
    // Simplified shadow: just darken areas where new image is exposed
    // based on proximity to falling pieces (skip expensive shadow raycast)
    // Shadow fades in from t=0.15 to t=0.5, then fades out from t=0.85 to t=0.995
    // This prevents the brightness pop when transition ends
    if (!pixelCovered && t > 0.15) {
        float shadowFadeIn = smoothstep(0.15, 0.5, t);
        float shadowFadeOut = 1.0 - smoothstep(0.85, 0.995, t);
        totalShadow = shadowFadeIn * shadowFadeOut * 0.15;  // Reduced shadow intensity
    }
    
    // Apply drop shadow to exposed areas (new image showing through)
    if (!pixelCovered) {
        finalColor = newColor.rgb * (1.0 - totalShadow);
    }
    
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
            "u_crack_complexity": gl.glGetUniformLocation(program, "u_crack_complexity"),
            "u_mosaic_mode": gl.glGetUniformLocation(program, "u_mosaic_mode"),
            "u_weight_mode": gl.glGetUniformLocation(program, "u_weight_mode"),
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
            state: CrumbleState dataclass with progress, seed, piece_count,
                   crack_complexity, mosaic_mode
            quad_vao: VAO for fullscreen quad
        """
        if gl is None:
            return

        vp_w, vp_h = viewport
        progress = max(0.0, min(1.0, float(getattr(state, "progress", 0.0))))
        seed = float(getattr(state, "seed", 0.0))
        piece_count = float(getattr(state, "piece_count", 8.0))
        crack_complexity = float(getattr(state, "crack_complexity", 1.0))
        mosaic_mode = 1.0 if getattr(state, "mosaic_mode", False) else 0.0
        weight_mode = float(getattr(state, "weight_mode", 0.0))

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

            if uniforms.get("u_crack_complexity", -1) != -1:
                gl.glUniform1f(uniforms["u_crack_complexity"], float(crack_complexity))

            if uniforms.get("u_mosaic_mode", -1) != -1:
                gl.glUniform1f(uniforms["u_mosaic_mode"], float(mosaic_mode))

            if uniforms.get("u_weight_mode", -1) != -1:
                gl.glUniform1f(uniforms["u_weight_mode"], float(weight_mode))

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
