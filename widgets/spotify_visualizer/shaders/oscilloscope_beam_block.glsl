// The Oscilloscope beam's pass block (std140 at the pass-block binding; included by oscilloscope_beam.vert and both
// beam fragments, so every stage declares the very same block). Each member is filled by one source, by its name: the
// core's conventions (uMatrix, uContentRotationQuarters, u_resolution), the settings (oscilloscope_settings_values: what
// follows the Settings and the card) or the record (oscilloscope_frame_values: what follows the music each frame).
layout(std140, binding = 18) uniform OscilloscopeBeam {
    mat4 uMatrix;                  // item logical px to the drawn target's clip space
    vec4 uField;                   // the content rect (item logical px)
    vec4 uLayout;                  // x: the Trace's half extent past the centre (before its overrun), y: the vertical
                                   // scale (logical px per unit), z: the Ring's and Phase's radius, w: their length
    vec4 u_beam;                    // the beam's colour (rgb; the tone's tint under Spectral)
    vec4 uGlowColour;              // the light's colour (rgb)
    vec2 u_resolution;             // the content's (rotated) logical size
    int uContentRotationQuarters;  // CUSTOM quarter turns of the content
    int u_points;                   // points per trace
    int uTrace;                    // 1: the Trace display (its ends run past the item by the beam's reach)
    float uPixel;                  // one device pixel in logical px (the anti-aliased edge)
    float uCoreBase;               // the beam's half width before the flare (px)
    float u_widen;                  // how much the flare widens it (1 + 0.9 flare)
    float uGlow;                   // the light the beam sends to the bloom
    float u_bright;                 // the beam's brightness (drive, flare)
    float uAnalog;                 // dimming where the beam moves fast
    float u_hot;                    // the white-hot centre
    float uCentreFade;             // Phase: the beam fades where quiet scribbles pile up at the centre
    float u_alpha[16];              // each trace's brightness, oldest first
};
