// The Oscilloscope graticule's fragment (included by oscilloscope_graticule.frag, which writes no light into the
// emission at location 1, and by oscilloscope_graticule_plain.frag, OSC_PLAIN: Glow 0, a target of colour alone).
#include "oscilloscope_graticule_block.glsl"
layout(location = 0) in vec2 vUnit;
layout(location = 0) out vec4 FragColor;
#ifndef OSC_PLAIN
layout(location = 1) out vec4 Emission;
#endif
float lineCoverage(float distancePx) { return 1.0 - clamp(distancePx - 0.25, 0.0, 1.0); }
void main() {
    vec2 grid = (vUnit * 0.5 + 0.5) * uDivisions;
    vec2 gridWidth = max(fwidth(grid), vec2(1e-5));
    vec2 toLine = abs(fract(grid + 0.5) - 0.5) / gridWidth;
    float lines = lineCoverage(min(toLine.x, toLine.y));
    vec2 axisWidth = max(fwidth(vUnit), vec2(1e-5));
    vec2 toAxis = abs(vUnit) / axisWidth;
    float axes = lineCoverage(min(toAxis.x, toAxis.y));
    // Minor ticks: five per division along the centre axes.
    vec2 ticks = abs(fract(grid * 5.0 + 0.5) - 0.5) / (gridWidth * 5.0);
    float tickX = lineCoverage(ticks.x) * step(toAxis.y, 4.0);
    float tickY = lineCoverage(ticks.y) * step(toAxis.x, 4.0);
    float tick = max(tickX, tickY) * 0.8;
    float cover = uStyle == 1 ? max(max(lines * 0.45, axes), tick) : max(axes, tick);
    float edge = 1.0 - smoothstep(0.97, 1.0, max(abs(vUnit.x), abs(vUnit.y)));
    float a = uGraticuleColour.a * cover * edge;
    FragColor = vec4(uGraticuleColour.rgb * a, a);
#ifndef OSC_PLAIN
    Emission = vec4(0.0);
#endif
}
