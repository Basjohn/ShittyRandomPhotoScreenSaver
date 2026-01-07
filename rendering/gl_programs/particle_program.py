"""Particle transition shader program.

Particles fly in from off-screen and stack to reveal the new image.
Uses a grid-driven analytic approach for predictable performance - each pixel
evaluates only a small neighborhood of candidate cells rather than iterating
all particles.

Modes:
- Directional: Particles come from one direction (L→R, R→L, T→B, B→T, diagonals)
- Swirl: Particles spiral in from edges toward center
- Converge: Particles spawn from all edges and converge to center

Settings:
- u_mode: 0=Directional, 1=Swirl, 2=Converge
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
uniform float u_mode;           // 0=Directional, 1=Swirl, 2=Converge
uniform float u_direction;      // 0-7=directions, 8=random, 9=random placement
uniform float u_particle_radius; // Base radius in pixels
uniform float u_overlap;        // Overlap in pixels
uniform float u_trail_length;   // Trail length fraction
uniform float u_trail_strength; // Trail opacity
uniform float u_swirl_strength; // Swirl angular component
uniform float u_swirl_turns;    // Spiral turns
uniform float u_use_3d;         // 3D shading flag
uniform float u_texture_map;    // Texture mapping flag
uniform float u_wobble;         // Per-particle wobble enable
uniform float u_gloss_size;     // Specular highlight size (higher = smaller/sharper)
uniform float u_light_dir;      // Light direction: 0=TL, 1=TR, 2=Center, 3=BL, 4=BR
uniform float u_swirl_order;    // 0=Typical, 1=Center Outward, 2=Edges Inward

// Constants
const float PI = 3.14159265359;
const float TWO_PI = 6.28318530718;
const float SPAWN_SPREAD = 0.65;  // Particles spawn over first 65% of transition
const float FLIGHT_TIME = 0.30;   // Each particle takes 30% of transition to arrive
const float MAX_RADIUS_NORM = 0.707;  // sqrt(0.5) - max distance from center to corner
const float FINAL_BLEND_START = 0.95;  // When final crossfade begins
const float FINAL_BLEND_END = 0.995;   // When transition is complete

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
vec2 getSpawnDirection(int dir, vec2 cellUV, float seed) {
    // 0=L→R, 1=R→L, 2=T→B, 3=B→T, 4=TL→BR, 5=TR→BL, 6=BL→TR, 7=BR→TL
    // 8=Random direction (per-transition), 9=Random placement (per-particle)
    if (dir == 8) {
        // Random direction - same for all particles in this transition
        float angle = seed * 2.0 * PI;
        return vec2(cos(angle), sin(angle));
    }
    if (dir == 9) {
        // Random placement - each particle from random direction
        float angle = hash1(cellUV * 100.0 + seed) * 2.0 * PI;
        return vec2(cos(angle), sin(angle));
    }
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
    float jitter = rand * 0.12;  // Small randomness in arrival
    
    // Random direction/placement: use random order
    if (dir == 8 || dir == 9) {
        return rand;  // Fully random arrival order
    }
    
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

// Calculate swirl order key based on build order setting
float getSwirlOrderKey(vec2 cellUV, float swirlTurns, float seed, int swirlOrder) {
    vec2 center = vec2(0.5, 0.5);
    vec2 delta = cellUV - center;
    float r = length(delta);
    float theta = atan(delta.y, delta.x);
    float thetaNorm = (theta + PI) / TWO_PI;
    float rNorm = clamp(r / MAX_RADIUS_NORM, 0.0, 1.0);  // Normalize and clamp
    float rand = hash1(cellUV * 100.0 + seed);
    
    if (swirlOrder == 1) {
        // Center Outward: true sequential spiral from center to edges
        // Each particle appears one at a time in a continuous clockwise spiral.
        // 
        // The key insight: for a true Archimedean spiral r = a*θ, the arc length
        // from the origin is proportional to θ². We use this to create ordering
        // where particles at the same "spiral distance" from center appear together.
        //
        // Convert to polar spiral coordinates:
        // - theta gives angular position (0 to 2π mapped to 0 to 1)
        // - r gives radial distance from center
        //
        // For clockwise spiral growth, we want:
        // - Center particles first (low r)
        // - At each radius band, particles appear in clockwise order
        // - Smooth transition between radius bands (no grid artifacts)
        
        // Clockwise angle (flip direction)
        float cwAngle = 1.0 - thetaNorm;
        
        // Number of spiral turns from center to edge
        float spiralTurns = 4.0;
        
        // Calculate position along the spiral using Archimedean formula
        // For r = k*θ, solving for θ gives θ = r/k
        // We add the angular position to create the spiral effect
        float spiralTheta = rNorm * spiralTurns + cwAngle;
        
        // The order key is simply the spiral theta normalized
        // This gives a continuous ordering from center outward in a spiral
        float order = spiralTheta / (spiralTurns + 1.0);
        
        // Tiny random jitter to break up any remaining patterns
        return clamp(order, 0.0, 0.95) + rand * 0.003;
    }
    
    if (swirlOrder == 2) {
        // Edges Inward: spiral from edges to center
        // Invert radius so edges (high r) arrive first, center (low r) arrives last
        float rInverted = 1.0 - rNorm;
        // Gentle spiral twist
        float spiralTwist = sin(thetaNorm * TWO_PI - rInverted * swirlTurns * TWO_PI) * 0.03;
        float order = rInverted * 0.88 + spiralTwist;
        return clamp(order, 0.0, 0.92) + rand * 0.02;
    }
    
    // Typical (0): Smooth organic swirl with natural variation
    // Use continuous spiral with soft randomness instead of hard dual-arm selection
    float spiralAngle = thetaNorm + swirlTurns * rNorm;
    // Smooth wave pattern instead of hard fract boundaries
    float wave = (sin(spiralAngle * TWO_PI) + 1.0) * 0.5;  // 0 to 1
    // Blend with radius for natural flow from edges
    float order = wave * 0.5 + rNorm * 0.35 + rand * 0.08;
    return clamp(order, 0.0, 0.92);
}

// Calculate converge order key - all edges at once, converging to center
float getConvergeOrderKey(vec2 cellUV, float seed) {
    vec2 center = vec2(0.5, 0.5);
    float r = length(cellUV - center);
    float rNorm = clamp(r / MAX_RADIUS_NORM, 0.0, 1.0);  // Clamp to valid range
    float rand = hash1(cellUV * 100.0 + seed);
    // Edges arrive first (low orderKey near 0), center arrives last (high orderKey near 0.9)
    // Use pow to make center particles arrive more gradually and later
    float centerBias = pow(1.0 - rNorm, 1.5);  // Center particles arrive much later
    return clamp(centerBias * 0.88 + rand * 0.03, 0.0, 0.92);  // Cap so center arrives before final blend
}

// Get spawn position for a particle
vec2 getSpawnPos(vec2 targetUV, int dir, int mode, float seed, float swirlStrength, int swirlOrder) {
    // Use multiple hash calls for better randomization
    vec2 rand1 = hash2(targetUV * 100.0 + seed);
    vec2 rand2 = hash2(targetUV * 73.7 + seed * 1.3);
    
    if (mode == 1) {
        // Swirl mode - spawn position depends on swirl order
        vec2 center = vec2(0.5, 0.5);
        vec2 delta = targetUV - center;
        float r = length(delta);
        float baseAngle = atan(delta.y, delta.x);
        
        float angle;
        if (swirlOrder == 1) {
            angle = baseAngle;
        } else {
            // Add random angular offset to break grid pattern
            float randomAngle = (rand1.x - 0.5) * PI * 0.6;
            angle = baseAngle + randomAngle;
            
            // Add spiral offset
            float spiralOffset = swirlStrength * r * 2.0;
            angle += spiralOffset;
        }
        
        if (swirlOrder == 1) {
            // Center Outward: spawn FROM center, fly TO target (outward)
            // Spawn near center with slight offset for visual interest
            float spawnDist = 0.02 + rand1.y * 0.05;
            return center + vec2(cos(angle), sin(angle)) * spawnDist;
        } else {
            // Edges Inward or Typical: spawn FROM edges, fly TO target
            float spawnDist = 0.55 + rand1.y * 0.08;
            return center + vec2(cos(angle), sin(angle)) * spawnDist;
        }
    }
    
    if (mode == 2) {
        // Converge: spawn from all edges, converge to center
        vec2 center = vec2(0.5, 0.5);
        vec2 delta = targetUV - center;
        float baseAngle = atan(delta.y, delta.x);
        // Add slight random angle variation
        float angle = baseAngle + (rand1.x - 0.5) * 0.3;
        // Spawn from edge of screen
        float spawnDist = 0.55 + rand1.y * 0.1;
        return center + vec2(cos(angle), sin(angle)) * spawnDist;
    }
    
    // Directional: spawn at screen edge for immediate visibility
    vec2 spawnDir = getSpawnDirection(dir, targetUV, seed);
    // Spawn at edge (0.3-0.4) so particles enter screen immediately
    float spawnDist = 0.3 + rand1.x * 0.1;
    vec2 perpendicular = vec2(-spawnDir.y, spawnDir.x);
    float perpOffset = (rand1.y - 0.5) * 0.1;
    
    return targetUV - spawnDir * spawnDist + perpendicular * perpOffset;
}

// Get light direction based on setting
vec3 getLightDir(float lightSetting) {
    int ld = int(lightSetting);
    // 0=Top-Left, 1=Top-Right, 2=Center, 3=Bottom-Left, 4=Bottom-Right
    if (ld == 0) return normalize(vec3(-0.4, -0.4, 1.0));  // Top-Left
    if (ld == 1) return normalize(vec3(0.4, -0.4, 1.0));   // Top-Right
    if (ld == 2) return normalize(vec3(0.0, 0.0, 1.0));    // Center (front)
    if (ld == 3) return normalize(vec3(-0.4, 0.4, 1.0));   // Bottom-Left
    return normalize(vec3(0.4, 0.4, 1.0));                  // Bottom-Right
}

// 3D ball shading with glass/reflective effects
vec3 shade3DBall(vec2 localPos, vec3 baseColor) {
    float r2 = dot(localPos, localPos);
    if (r2 > 1.0) return baseColor;
    
    float z = sqrt(1.0 - r2);
    vec3 normal = vec3(localPos, z);
    
    // Get configurable light direction
    vec3 lightDir = getLightDir(u_light_dir);
    
    // Fresnel effect - edges are more reflective (glass-like)
    float fresnel = 1.0 - z;
    fresnel = pow(fresnel, 1.5) * 0.7;
    
    // Diffuse lighting - keep base color visible
    float diffuse = max(dot(normal, lightDir), 0.0);
    diffuse = 0.4 + 0.6 * diffuse;
    
    // View direction (looking at screen)
    vec3 viewDir = vec3(0.0, 0.0, 1.0);
    vec3 halfDir = normalize(lightDir + viewDir);
    
    // Configurable gloss size: u_gloss_size controls sharpness (default 64, range ~16-128)
    float glossPower = max(8.0, u_gloss_size);
    
    // Primary specular - sharp white highlight (glass reflection)
    float spec1 = pow(max(dot(normal, halfDir), 0.0), glossPower * 1.5);
    
    // Secondary specular - broader highlight
    float spec2 = pow(max(dot(normal, halfDir), 0.0), glossPower * 0.4);
    
    // Tertiary specular - very broad glow
    float spec3 = pow(max(dot(normal, halfDir), 0.0), glossPower * 0.125);
    
    // Environment reflection approximation - reflect sky/light
    vec3 reflectDir = reflect(-viewDir, normal);
    float envReflect = max(0.0, reflectDir.y * 0.5 + 0.5);
    vec3 envColor = mix(vec3(0.6, 0.7, 0.8), vec3(0.95, 0.97, 1.0), envReflect);
    
    // Combine lighting
    vec3 result = baseColor * diffuse;
    
    // Add reflections - glass-like appearance
    result = mix(result, envColor, fresnel * 0.4);
    
    // Specular highlights
    result += vec3(1.0) * spec1 * 0.7;
    result += vec3(0.95, 0.97, 1.0) * spec2 * 0.25;
    result += vec3(0.9, 0.95, 1.0) * spec3 * 0.1;
    
    // Rim lighting for depth
    result += vec3(0.85, 0.9, 1.0) * fresnel * 0.3;
    
    return result;
}

// Get the expected arrival time for a pixel based on its position and mode
float getPixelArrivalTime(vec2 pixelUV, int mode, int dir, float swirlTurns, float seed, int swirlOrder) {
    float orderKey;
    
    if (mode == 1) {
        orderKey = getSwirlOrderKey(pixelUV, swirlTurns, seed, swirlOrder);
    } else if (mode == 2) {
        orderKey = getConvergeOrderKey(pixelUV, seed);
    } else {
        // For directional, use smoother orderKey without per-pixel randomness for blend
        orderKey = getOrderKey(pixelUV, dir, seed * 0.01);  // Reduce randomness for smoother blend
    }
    
    float spawnTime = orderKey * SPAWN_SPREAD;
    return spawnTime + FLIGHT_TIME;  // When particle arrives at this location
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
    if (t >= FINAL_BLEND_END) {
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
    
    // POSITION-AWARE BACKGROUND BLEND: Only blend background after particles should have arrived
    // This prevents the center from crossfading before particles reach it in Converge mode
    float pixelArrival = getPixelArrivalTime(uv, mode, dir, u_swirl_turns, u_seed, int(u_swirl_order));
    // Background starts blending ONLY AFTER particle arrives at this location
    // For Converge mode, delay center blend even more to ensure particles are visible
    float bgBlendStart = pixelArrival;
    float bgBlendDuration = (mode == 2) ? 0.05 : 0.10;  // Shorter blend for Converge
    float bgBlendEnd = min(pixelArrival + bgBlendDuration, FINAL_BLEND_START);
    float bgBlend = smoothstep(bgBlendStart, bgBlendEnd, t);
    vec3 finalColor = mix(oldColor.rgb, newColor.rgb, bgBlend);
    float coverage = 0.0;
    
    // Find which cell this pixel is in
    vec2 cellId = floor(uv / vec2(cellW, cellH));
    
    // Search neighborhood for particles that might cover this pixel
    int searchRange = 3;
    
    for (int dy = -searchRange; dy <= searchRange; dy++) {
        for (int dx = -searchRange; dx <= searchRange; dx++) {
            vec2 checkCell = cellId + vec2(float(dx), float(dy));
            
            // Skip invalid cells
            if (checkCell.x < 0.0 || checkCell.x >= cols) continue;
            if (checkCell.y < 0.0 || checkCell.y >= rows) continue;
            
            // Cell center (target position)
            vec2 targetUV = (checkCell + 0.5) * vec2(cellW, cellH);
            
            // Per-particle random values for wobble
            vec2 particleRand = hash2(targetUV * 50.0 + u_seed * 2.0);
            
            // Get particle timing
            float orderKey;
            if (mode == 1) {
                orderKey = getSwirlOrderKey(targetUV, u_swirl_turns, u_seed, int(u_swirl_order));
            } else if (mode == 2) {
                orderKey = getConvergeOrderKey(targetUV, u_seed);
            } else {
                orderKey = getOrderKey(targetUV, dir, u_seed);
            }
            
            // TIMING: Use global constants for consistent timing
            float spawnTime = orderKey * SPAWN_SPREAD;
            float arrivalTime = spawnTime + FLIGHT_TIME;
            
            // Calculate local progress for this particle
            float tLocal = (t - spawnTime) / FLIGHT_TIME;
            tLocal = clamp(tLocal, 0.0, 1.0);
            
            // Skip if particle hasn't spawned yet
            if (tLocal <= 0.0) continue;
            
            // Get spawn position
            vec2 spawnPos = getSpawnPos(targetUV, dir, mode, u_seed, u_swirl_strength, int(u_swirl_order));
            
            // Interpolate position with easing
            float easedT = easeOutCubic(tLocal);
            vec2 currentPos = mix(spawnPos, targetUV, easedT);
            
            // Per-particle wobble (optional, uses particle's own random values)
            if (u_wobble > 0.5 && tLocal >= 1.0 && t < 0.92) {
                float timeSinceArrival = t - arrivalTime;
                // Each particle has unique phase and frequency
                float phase = particleRand.x * 6.28;
                float freq = 15.0 + particleRand.y * 10.0;
                float decay = exp(-timeSinceArrival * 6.0);
                // X and Y wobble independently
                float wobbleX = sin(timeSinceArrival * freq + phase) * decay;
                float wobbleY = sin(timeSinceArrival * freq * 1.3 + phase + 1.5) * decay;
                vec2 wobbleOffset = vec2(wobbleX, wobbleY) * 0.004 * radiusUVx;
                currentPos += wobbleOffset;
            }
            
            // Distance from pixel to particle center (normalized to particle radius)
            vec2 delta = uv - currentPos;
            vec2 normalizedDelta = vec2(delta.x / radiusUVx, delta.y / radiusUVy);
            float dist = length(normalizedDelta);
            
            // Check if pixel is inside particle
            if (dist < 1.0) {
                // Inside particle - sample new image
                vec2 sampleUV = targetUV;
                
                if (u_texture_map > 0.5) {
                    vec2 localPos = normalizedDelta;
                    if (u_use_3d > 0.5) {
                        float z = sqrt(max(0.0, 1.0 - dot(localPos, localPos)));
                        sampleUV = targetUV + localPos * vec2(radiusUVx, radiusUVy) * 0.3 * (1.0 - z);
                    }
                }
                sampleUV = clamp(sampleUV, vec2(0.0), vec2(1.0));
                vec3 particleColor = texture(uNewTex, sampleUV).rgb;
                
                // SEQUENTIAL FADE: Each particle fades based on its own arrival time
                // Early arrivers start fading first, creating a wave effect
                float fadeStart = arrivalTime + 0.08;  // Wait 8% after arrival before fading
                float fadeEnd = min(fadeStart + 0.20, 0.95);  // Fade over 20% duration
                float particleFade = smoothstep(fadeStart, fadeEnd, t);
                
                // Apply 3D shading, reduced as particle fades
                if (u_use_3d > 0.5) {
                    vec2 localPos = normalizedDelta;
                    vec3 shadedColor = shade3DBall(localPos, particleColor);
                    // Blend from full 3D to flat as we fade
                    particleColor = mix(shadedColor, particleColor, particleFade * 0.7);
                }
                
                // Soft edge
                float edge = 1.0 - smoothstep(0.85, 1.0, dist);
                
                // Particle alpha decreases as it fades into the image
                float particleAlpha = edge * (1.0 - particleFade * 0.85);
                
                // Blend particle with background (which is already transitioning to new image)
                finalColor = mix(finalColor, particleColor, particleAlpha);
                coverage = max(coverage, particleAlpha);
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
    
    // FINAL CROSSFADE: Ensure perfect finish to new image
    // Only start final blend after ALL particles should have arrived (t > 0.95)
    // This prevents any premature crossfade artifacts
    float finalBlend = smoothstep(FINAL_BLEND_START, FINAL_BLEND_END, t);
    finalColor = mix(finalColor, newColor.rgb, finalBlend);
    
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
            "u_swirl_turns", "u_use_3d", "u_texture_map", "u_wobble",
            "u_gloss_size", "u_light_dir", "u_swirl_order",
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
            if uniforms.get("u_wobble", -1) >= 0:
                gl.glUniform1f(uniforms["u_wobble"], 1.0 if getattr(state, 'wobble', False) else 0.0)
            if uniforms.get("u_gloss_size", -1) >= 0:
                gl.glUniform1f(uniforms["u_gloss_size"], getattr(state, 'gloss_size', 64.0))
            if uniforms.get("u_light_dir", -1) >= 0:
                gl.glUniform1f(uniforms["u_light_dir"], float(getattr(state, 'light_direction', 0)))
            if uniforms.get("u_swirl_order", -1) >= 0:
                gl.glUniform1f(uniforms["u_swirl_order"], float(getattr(state, 'swirl_order', 0)))
            
            # Draw fullscreen quad
            self._draw_fullscreen_quad(quad_vao)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)


# Module-level singleton instance
particle_program = ParticleProgram()
