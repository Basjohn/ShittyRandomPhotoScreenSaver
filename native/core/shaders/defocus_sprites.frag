#version 440
// The defocus step's highlight sprites, fragment stage (Current_Plan.md item 8b, N3.4; D17 point 6):
// rendering/quick/scene3d/defocus.py _SPRITE_FRAGMENT, a lens disc of even light, its edge a little brighter, added on
// colour (ONE, ONE; alpha ZERO, ONE).
layout(location = 0) in vec2 vOffset;
layout(location = 1) flat in float vCircle;
layout(location = 2) flat in vec3 vLight;
layout(location = 0) out vec4 FragColor;

void main() {
    float d = length(vOffset);
    float inside = clamp(vCircle - d + 0.5, 0.0, 1.0);
    if (inside <= 0.0) discard;
    // A lens disc: even, its edge a little brighter (the mean of this profile over the disc is ~1).
    float rim = 0.88 + 0.3 * smoothstep(0.55, 1.0, d / vCircle);
    FragColor = vec4(vLight * inside * rim, 0.0);
}
