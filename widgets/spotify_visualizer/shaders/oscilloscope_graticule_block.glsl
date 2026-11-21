// The Oscilloscope graticule's pass block (included by oscilloscope_graticule.vert and both graticule fragments). Its
// members are the core's (uMatrix, uContentRotationQuarters, u_resolution) and the settings' (every frame draws the same
// graticule; whether it draws at all is the record's vertex count).
layout(std140, binding = 18) uniform OscilloscopeGraticule {
    mat4 uMatrix;                  // item logical px to the drawn target's clip space
    vec4 uScreen;                  // the scope's screen, centred in the content (item logical px)
    vec4 uGraticuleColour;
    vec2 uDivisions;
    vec2 u_resolution;             // the content's (rotated) logical size
    int uContentRotationQuarters;  // CUSTOM quarter turns of the content
    int uStyle;                    // 1 grid, 2 crosshair
};
