#version 440
// Bake with PySide6 qsb: --glsl "410" -o widget_glow.frag.qsb widget_glow.frag
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 effectSize;
    vec2 cardSize;
    float cornerRadius;
    vec4 glowColor;
};
void main() {
    vec2 p = (qt_TexCoord0 - vec2(0.5)) * effectSize;
    float radius = clamp(cornerRadius, 0.0, min(cardSize.x, cardSize.y) * 0.5);
    vec2 q = abs(p) - cardSize * 0.5 + vec2(radius);
    float distanceToEdge = length(max(q, vec2(0.0)))
        + min(max(q.x, q.y), 0.0) - radius;
    float antialiasWidth = max(fwidth(distanceToEdge), 0.001);
    float outside = smoothstep(-antialiasWidth, antialiasWidth, distanceToEdge);
    float halo = exp(-max(distanceToEdge, 0.0) * 0.35)
        * (1.0 - smoothstep(10.0, 12.0, distanceToEdge));
    fragColor = glowColor * (qt_Opacity * outside * halo);
}
