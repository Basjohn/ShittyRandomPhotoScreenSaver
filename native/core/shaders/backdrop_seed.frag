#version 440
// The backdrop pyramid's seed (Current_Plan.md N5.7b; native/core/src/backdrop.h): its first level, half the window,
// from the core's background layer, in place of the Python pyramid's blit of Qt Quick's window target
// (rendering/quick/render/surface_backdrop.py: glBlitFramebuffer with GL_LINEAR into 1/2).
//
// Each texel reads the window position the blit reads (its centre scaled to the window), in the window framebuffer's own
// row order, so the level's rows run as the window's do (bottom-up on OpenGL) and a card samples it in screen space as
// it samples the Python level. The layer lies in the window at uSeedWindow.zw (rows top-down) and its target is top-down
// in memory on every backend (N0.3 F1); outside it the window is its clear colour, black. Inside, the hardware's bilinear
// tap the blit uses; where the tap's 2 x 2 texels straddle the layer's edge, the same tap by hand with black outside.
// Emulated against the Python blit on OpenGL before the build (two PERSONALSET photos at the overscan placement): the
// interior equal, the hand tap within 1 level on a few texels of the outermost column or row (the blit's hardware weights
// round its half-black taps their own way; whole-level ties to even, half up and truncation all matched it worse).
// Dimming, the black rectangle over the wallpaper, is the uniform blend it is: the layer times uSeedLayer.w.

layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform BackdropPass {
    vec4 uHalfPixel;  // xy: half a texel of this pass's target (the down and up passes)
    vec4 uSeedWindow; // xy: the window framebuffer's pixels; zw: the layer's origin in it (pixels, rows top-down)
    vec4 uSeedLayer;  // xy: the layer's pixels; z: 1 when the framebuffer's rows run bottom-up (OpenGL); w: 1 - dimming
};

layout(binding = 1) uniform sampler2D uSource;

vec3 layerTexel(ivec2 t, ivec2 size)
{
    if (t.x < 0 || t.y < 0 || t.x >= size.x || t.y >= size.y)
        return vec3(0.0);
    return texelFetch(uSource, t, 0).rgb;
}

void main()
{
    vec2 window = vUv * uSeedWindow.xy;
    if (uSeedLayer.z > 0.5)
        window.y = uSeedWindow.y - window.y;
    vec2 p = window - uSeedWindow.zw;
    vec2 size = uSeedLayer.xy;
    vec3 c;
    if (p.x >= 0.5 && p.y >= 0.5 && p.x <= size.x - 0.5 && p.y <= size.y - 0.5) {
        c = texture(uSource, p / size).rgb;
    } else {
        ivec2 isize = ivec2(size + 0.5);
        vec2 q = p - 0.5;
        vec2 base = floor(q);
        vec2 f = q - base;
        ivec2 i = ivec2(base);
        vec3 top = mix(layerTexel(i, isize), layerTexel(i + ivec2(1, 0), isize), f.x);
        vec3 bottom = mix(layerTexel(i + ivec2(0, 1), isize), layerTexel(i + ivec2(1, 1), isize), f.x);
        c = mix(top, bottom, f.y);
    }
    fragColor = vec4(c * uSeedLayer.w, 1.0);
}
