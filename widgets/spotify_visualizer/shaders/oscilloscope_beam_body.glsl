// The Oscilloscope beam's fragment (included by oscilloscope_beam.frag, which writes the light into the emission
// attachment at location 1, and by oscilloscope_beam_plain.frag, OSC_PLAIN: Glow 0, a target of colour alone). It
// measures the distance to its segment, so the beam is anti-aliased at any width and joints never bead (the traces
// combine by their maximum).
#include "oscilloscope_beam_block.glsl"
layout(location = 0) in vec2 vLocal;
layout(location = 1) in vec2 vA;
layout(location = 2) in vec2 vB;
layout(location = 3) flat in float vAlpha;
layout(location = 4) flat in float vLength;
layout(location = 5) flat in float vRadius;
layout(location = 6) flat in float vCore;
layout(location = 7) flat in float vFocus;
layout(location = 0) out vec4 FragColor;
#ifndef OSC_PLAIN
layout(location = 1) out vec4 Emission;
#endif
void main() {
    vec2 pa = vLocal - vA;
    vec2 ba = vB - vA;
    float h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-6), 0.0, 1.0);
    float dist = length(pa - ba * h);
    float core = 1.0 - smoothstep(vCore - uPixel, vCore + uPixel, dist);
    if (core <= 0.0) discard;
    float speed = clamp(vFocus / max(vLength, vFocus * 0.2), 0.2, 1.0);
    float centre_fade = mix(1.0, smoothstep(0.03, 0.22, vRadius), uCentreFade);
    float intensity = clamp(core * vAlpha * u_bright * mix(1.0, speed, uAnalog) * centre_fade, 0.0, 1.0);
    float centre = 1.0 - smoothstep(0.0, vCore, dist);
    vec3 colour = mix(u_beam.rgb, vec3(1.0), centre * centre * centre * u_hot);
    FragColor = vec4(colour * intensity, intensity);
#ifndef OSC_PLAIN
    vec3 light = uGlowColour.rgb * (intensity * uGlow);
    Emission = vec4(light, dot(light, vec3(0.2126, 0.7152, 0.0722)));
#endif
}
