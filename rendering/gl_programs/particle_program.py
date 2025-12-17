"""Particle transition shader program.

Particles fly in from off-screen and stack to reveal the new image.
Uses a grid-driven analytic approach for predictable performance - each pixel
evaluates only a small neighborhood of candidate cells rather than iterating
all particles.

Modes:
- Directional: Particles come from one direction (L→R, R→L, T→B, B→T, diagonals)
- Swirl: Particles spiral in from edges toward center

Settings:
- u_mode: 0=Directional, 1=Swirl
- u_direction: Direction for directional mode (0-7)
- u_particle_radius: Base radius in pixels
- u_overlap: Overlap in pixels to avoid gaps
- u_trail_length: Trail length as fraction of particle size
- u_trail_strength: Trail opacity 0..1
- u_swirl_strength: Angular component for swirl mode
- u_swirl_turns: Number of spiral turns
- u_use_3d: Enable 3D ball shading
- u_texture_map: Map new image onto particles
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from rendering.gl_programs.base_program import BaseGLProgram

logger = logging.getLogger(__name__)

try:
    from OpenGL import GL as gl
except ImportError:
    gl = None


class ParticleProgram(BaseGLProgram):
    """Shader program for the Particle transition effect."""

    @property
    def name(self) -> str:
        return "Particle"

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
uniform float u_seed;
uniform float u_mode;           // 0=Directional, 1=Swirl
uniform float u_direction;      // 0=L→R, 1=R→L, 2=T→B, 3=B→T, 4-7=diagonals
uniform float u_particle_radius; // Base radius in pixels
uniform float u_overlap;        // Overlap in pixels
uniform float u_trail_length;   // Trail length fraction
uniform float u_trail_strength; // Trail opacity
uniform float u_swirl_strength; // Swirl angular component
uniform float u_swirl_turns;    // Spiral turns
uniform float u_use_3d;         // 3D shading flag
uniform float u_texture_map;    // Texture mapping flag

// Constants
const float PI = 3.14159265359;
const vec3 LIGHT_DIR = normalize(vec3(0.3, 0.3, 1.0));

// Hash functions for procedural randomness
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

// Smooth easing function
float easeOutCubic(float t) {
    return 1.0 - pow(1.0 - t, 3.0);
}

float easeInOutQuad(float t) {
    return t < 0.5 ? 2.0 * t * t : 1.0 - pow(-2.0 * t + 2.0, 2.0) / 2.0;
}

// Get spawn direction vector based on direction setting
vec2 getSpawnDirection(int dir) {
    // 0=L→R, 1=R→L, 2=T→B, 3=B→T, 4=TL→BR, 5=TR→BL, 6=BL→TR, 7=BR→TL
    if (dir == 0) return vec2(-1.0, 0.0);  // From left
    if (dir == 1) return vec2(1.0, 0.0);   // From right
    if (dir == 2) return vec2(0.0, -1.0);  // From top
    if (dir == 3) return vec2(0.0, 1.0);   // From bottom
    if (dir == 4) return normalize(vec2(-1.0, -1.0)); // From top-left
    if (dir == 5) return normalize(vec2(1.0, -1.0));  // From top-right
    if (dir == 6) return normalize(vec2(-1.0, 1.0));  // From bottom-left
    return normalize(vec2(1.0, 1.0));  // From bottom-right
}

// Calculate order key for stacking (determines when particle arrives)
float getOrderKey(vec2 cellUV, int dir, float seed) {
    float rand = hash1(cellUV * 100.0 + seed);
    float jitter = rand * 0.15;  // Small randomness in arrival
    
    // For directional modes, order by position along direction
    if (dir == 0) return cellUV.x + jitter;           // L→R: left arrives first
    if (dir == 1) return (1.0 - cellUV.x) + jitter;   // R→L: right arrives first
    if (dir == 2) return cellUV.y + jitter;           // T→B: top arrives first
    if (dir == 3) return (1.0 - cellUV.y) + jitter;   // B→T: bottom arrives first
    if (dir == 4) return (cellUV.x + cellUV.y) * 0.5 + jitter;
    if (dir == 5) return ((1.0 - cellUV.x) + cellUV.y) * 0.5 + jitter;
    if (dir == 6) return (cellUV.x + (1.0 - cellUV.y)) * 0.5 + jitter;
    return ((1.0 - cellUV.x) + (1.0 - cellUV.y)) * 0.5 + jitter;
}

// Calculate swirl order key
float getSwirlOrderKey(vec2 cellUV, float swirlTurns, float seed) {
    vec2 center = vec2(0.5, 0.5);
    vec2 delta = cellUV - center;
    float r = length(delta);
    float theta = atan(delta.y, delta.x);
    float thetaNorm = (theta + PI) / (2.0 * PI);
    float rNorm = r / 0.707;  // Normalize by max distance to corner
    
    // Spiral order: combine angle and radius
    float order = fract(thetaNorm + swirlTurns * rNorm);
    float rand = hash1(cellUV * 100.0 + seed);
    return order + rand * 0.1;
}

// Get spawn position for a particle
vec2 getSpawnPos(vec2 targetUV, int dir, int mode, float seed, float swirlStrength) {
    vec2 rand = hash2(targetUV * 100.0 + seed);
    
    if (mode == 1) {
        // Swirl: spawn from edges with smooth spiral path
        vec2 center = vec2(0.5, 0.5);
        vec2 delta = targetUV - center;
        float r = length(delta);
        float angle = atan(delta.y, delta.x);
        
        // Add spiral offset based on radius - creates smooth spiral inward motion
        float spiralOffset = swirlStrength * r * 3.0;
        angle += spiralOffset;
        
        // Spawn from outside with some randomness to avoid grid patterns
        float spawnDist = 1.3 + rand.x * 0.4;
        
        // Add slight random angular jitter to break up grid patterns
        angle += (rand.y - 0.5) * 0.3;
        
        return center + vec2(cos(angle), sin(angle)) * spawnDist;
    }
    
    // Directional: spawn off-screen along direction
    vec2 spawnDir = getSpawnDirection(dir);
    float spawnDist = 1.2 + rand.x * 0.3;  // Vary spawn distance
    vec2 perpendicular = vec2(-spawnDir.y, spawnDir.x);
    float perpOffset = (rand.y - 0.5) * 0.1;  // Slight perpendicular jitter
    
    return targetUV - spawnDir * spawnDist + perpendicular * perpOffset;
}

// 3D ball shading with glow and reflective effects
vec3 shade3DBall(vec2 localPos, vec3 baseColor) {
    float r2 = dot(localPos, localPos);
    if (r2 > 1.0) return baseColor;
    
    float z = sqrt(1.0 - r2);
    vec3 normal = vec3(localPos, z);
    
    // Fresnel effect - edges glow more (rim lighting)
    float fresnel = 1.0 - z;
    fresnel = pow(fresnel, 2.0) * 0.6;
    
    // Diffuse lighting with softer falloff
    float diffuse = max(dot(normal, LIGHT_DIR), 0.0);
    diffuse = 0.35 + 0.65 * diffuse;  // Ambient + diffuse
    
    // Primary specular highlight (sharp)
    vec3 viewDir = vec3(0.0, 0.0, 1.0);
    vec3 halfDir = normalize(LIGHT_DIR + viewDir);
    float spec1 = pow(max(dot(normal, halfDir), 0.0), 64.0);
    
    // Secondary specular (broader, softer glow)
    float spec2 = pow(max(dot(normal, halfDir), 0.0), 16.0);
    
    // Subsurface scattering approximation - light passes through edges
    float sss = pow(1.0 - z, 3.0) * 0.15;
    vec3 sssColor = baseColor * 1.3;  // Brighter at edges
    
    // Combine all lighting
    vec3 result = baseColor * diffuse;
    result += vec3(1.0) * spec1 * 0.5;      // Sharp highlight
    result += vec3(0.9, 0.95, 1.0) * spec2 * 0.2;  // Soft glow
    result += sssColor * sss;               // Subsurface glow
    result += vec3(0.8, 0.9, 1.0) * fresnel; // Rim light
    
    return result;
}

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float t = clamp(u_progress, 0.0, 1.0);
    
    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);
    
    // At start, show old image
    if (t <= 0.0) {
        FragColor = oldColor;
        return;
    }
    // At end, show new image cleanly
    if (t >= 0.999) {
        FragColor = newColor;
        return;
    }
    
    // Calculate grid parameters
    float radiusPx = max(8.0, u_particle_radius);
    float overlapPx = max(0.0, u_overlap);
    float cellSizePx = radiusPx * 2.0 - overlapPx;
    
    // Grid dimensions
    float cols = ceil(u_resolution.x / cellSizePx);
    float rows = ceil(u_resolution.y / cellSizePx);
    float cellW = 1.0 / cols;
    float cellH = 1.0 / rows;
    
    // Particle radius in UV space (consistent calculation)
    // Use separate X and Y radii to handle aspect ratio properly
    float radiusUVx = radiusPx / u_resolution.x;
    float radiusUVy = radiusPx / u_resolution.y;
    
    int mode = int(u_mode);
    int dir = int(u_direction);
    
    // Start with old image, particles will cover it
    vec3 finalColor = oldColor.rgb;
    float coverage = 0.0;
    
    // Find which cell this pixel is in
    vec2 cellId = floor(uv / vec2(cellW, cellH));
    
    // Search neighborhood for particles that might cover this pixel
    // Particles move, so we need to check nearby cells
    int searchRange = 3;
    
    for (int dy = -searchRange; dy <= searchRange; dy++) {
        for (int dx = -searchRange; dx <= searchRange; dx++) {
            vec2 checkCell = cellId + vec2(float(dx), float(dy));
            
            // Skip invalid cells
            if (checkCell.x < 0.0 || checkCell.x >= cols) continue;
            if (checkCell.y < 0.0 || checkCell.y >= rows) continue;
            
            // Cell center (target position)
            vec2 targetUV = (checkCell + 0.5) * vec2(cellW, cellH);
            
            // Get particle timing
            float orderKey;
            if (mode == 1) {
                orderKey = getSwirlOrderKey(targetUV, u_swirl_turns, u_seed);
            } else {
                orderKey = getOrderKey(targetUV, dir, u_seed);
            }
            
            // Stagger arrival times - all particles should arrive by t=1.0
            float spawnSpread = 0.5;  // Particles spawn over 50% of duration
            float flightTime = 0.5;   // Each particle takes 50% of duration to arrive
            float spawnTime = orderKey * spawnSpread;
            float arrivalTime = spawnTime + flightTime;
            
            // Calculate local progress for this particle
            float tLocal = (t - spawnTime) / flightTime;
            tLocal = clamp(tLocal, 0.0, 1.0);
            
            // Skip if particle hasn't spawned yet
            if (tLocal <= 0.0) continue;
            
            // Get spawn position
            vec2 spawnPos = getSpawnPos(targetUV, dir, mode, u_seed, u_swirl_strength);
            
            // Interpolate position with easing
            float easedT = easeOutCubic(tLocal);
            vec2 currentPos = mix(spawnPos, targetUV, easedT);
            
            // Distance from pixel to particle center (normalized to particle radius)
            vec2 delta = uv - currentPos;
            // Normalize delta by particle radius in each dimension
            vec2 normalizedDelta = vec2(delta.x / radiusUVx, delta.y / radiusUVy);
            float dist = length(normalizedDelta);
            
            // Check if pixel is inside particle (dist < 1.0 means inside)
            if (dist < 1.0) {
                // Inside particle - sample new image
                vec2 sampleUV = targetUV;
                
                if (u_texture_map > 0.5) {
                    // Map texture with curvature for 3D effect
                    vec2 localPos = normalizedDelta;  // Already normalized to [-1, 1]
                    if (u_use_3d > 0.5) {
                        float z = sqrt(max(0.0, 1.0 - dot(localPos, localPos)));
                        sampleUV = targetUV + localPos * vec2(radiusUVx, radiusUVy) * 0.3 * (1.0 - z);
                    }
                }
                sampleUV = clamp(sampleUV, vec2(0.0), vec2(1.0));
                vec3 particleColor = texture(uNewTex, sampleUV).rgb;
                
                // Apply 3D shading if enabled
                if (u_use_3d > 0.5) {
                    vec2 localPos = normalizedDelta;
                    particleColor = shade3DBall(localPos, particleColor);
                }
                
                // Soft edge (dist is already normalized, so 0.85-1.0 range)
                float edge = 1.0 - smoothstep(0.85, 1.0, dist);
                
                // Blend with existing color (later particles on top)
                float alpha = edge;
                finalColor = mix(finalColor, particleColor, alpha);
                coverage = max(coverage, alpha);
            }
            
            // Motion trail
            if (u_trail_strength > 0.01 && tLocal < 1.0 && tLocal > 0.0) {
                vec2 velocity = targetUV - spawnPos;
                vec2 velNorm = normalize(velocity);
                
                // Project pixel position onto velocity line behind particle
                vec2 toPixel = uv - currentPos;
                float proj = dot(toPixel, -velNorm);
                
                float avgRadius = (radiusUVx + radiusUVy) * 0.5;
                float trailLen = avgRadius * u_trail_length * 3.0;
                if (proj > 0.0 && proj < trailLen) {
                    // Perpendicular distance to trail line
                    vec2 perpVec = toPixel - (-velNorm) * proj;
                    perpVec.x *= u_resolution.x / u_resolution.y;
                    float perpDist = length(perpVec);
                    
                    // Trail width tapers
                    float trailWidth = avgRadius * (1.0 - proj / trailLen) * 0.6;
                    
                    if (perpDist < trailWidth) {
                        float trailAlpha = (1.0 - proj / trailLen) * u_trail_strength;
                        trailAlpha *= 1.0 - perpDist / trailWidth;
                        trailAlpha *= 0.5;  // Trails are semi-transparent
                        
                        vec3 trailColor = texture(uNewTex, targetUV).rgb * 0.8;
                        finalColor = mix(finalColor, trailColor, trailAlpha * (1.0 - coverage));
                    }
                }
            }
        }
    }
    
    FragColor = vec4(finalColor, 1.0);
}
"""

    def cache_uniforms(self, program: int) -> Dict[str, int]:
        """Cache uniform locations for the particle program."""
        if gl is None:
            return {}
        
        uniforms = {}
        uniform_names = [
            "uOldTex", "uNewTex", "u_progress", "u_resolution", "u_seed",
            "u_mode", "u_direction", "u_particle_radius", "u_overlap",
            "u_trail_length", "u_trail_strength", "u_swirl_strength",
            "u_swirl_turns", "u_use_3d", "u_texture_map",
        ]
        
        for name in uniform_names:
            loc = gl.glGetUniformLocation(program, name)
            uniforms[name] = loc
            if loc == -1:
                logger.debug("[PARTICLE] Uniform %s not found (may be optimized out)", name)
        
        return uniforms

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
        """Draw one frame of the particle transition."""
        if gl is None:
            return
        
        vp_w, vp_h = viewport
        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)
        
        gl.glUseProgram(program)
        try:
            # Bind textures
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, old_tex)
            gl.glUniform1i(uniforms.get("uOldTex", -1), 0) if uniforms.get("uOldTex", -1) >= 0 else None
            
            gl.glActiveTexture(gl.GL_TEXTURE1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, new_tex)
            gl.glUniform1i(uniforms.get("uNewTex", -1), 1) if uniforms.get("uNewTex", -1) >= 0 else None
            
            # Set uniforms
            if uniforms.get("u_progress", -1) >= 0:
                gl.glUniform1f(uniforms["u_progress"], state.progress)
            if uniforms.get("u_resolution", -1) >= 0:
                gl.glUniform2f(uniforms["u_resolution"], float(viewport[0]), float(viewport[1]))
            if uniforms.get("u_seed", -1) >= 0:
                gl.glUniform1f(uniforms["u_seed"], state.seed)
            if uniforms.get("u_mode", -1) >= 0:
                gl.glUniform1f(uniforms["u_mode"], float(state.mode))
            if uniforms.get("u_direction", -1) >= 0:
                gl.glUniform1f(uniforms["u_direction"], float(state.direction))
            if uniforms.get("u_particle_radius", -1) >= 0:
                gl.glUniform1f(uniforms["u_particle_radius"], state.particle_radius)
            if uniforms.get("u_overlap", -1) >= 0:
                gl.glUniform1f(uniforms["u_overlap"], state.overlap)
            if uniforms.get("u_trail_length", -1) >= 0:
                gl.glUniform1f(uniforms["u_trail_length"], state.trail_length)
            if uniforms.get("u_trail_strength", -1) >= 0:
                gl.glUniform1f(uniforms["u_trail_strength"], state.trail_strength)
            if uniforms.get("u_swirl_strength", -1) >= 0:
                gl.glUniform1f(uniforms["u_swirl_strength"], state.swirl_strength)
            if uniforms.get("u_swirl_turns", -1) >= 0:
                gl.glUniform1f(uniforms["u_swirl_turns"], state.swirl_turns)
            if uniforms.get("u_use_3d", -1) >= 0:
                gl.glUniform1f(uniforms["u_use_3d"], 1.0 if state.use_3d_shading else 0.0)
            if uniforms.get("u_texture_map", -1) >= 0:
                gl.glUniform1f(uniforms["u_texture_map"], 1.0 if state.texture_mapping else 0.0)
            
            # Draw fullscreen quad
            self._draw_fullscreen_quad(quad_vao)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)


# Module-level singleton instance
particle_program = ParticleProgram()
