#version 440
// N0.3 scene 1, second pass (samples): the first pass's texture, an uploaded copy of the same content and the sRGB
// strip, each read at this fragment's texel or uv from the conventions include.
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions
//@n03_common

layout(binding = 2) uniform sampler2D written;      // the first pass's target
layout(binding = 3) uniform sampler2D uploadTex;    // the same content uploaded from an image (row 0 = top)
layout(binding = 4) uniform sampler2D srgbStrip;    // grey bytes with the sRGB flag
layout(binding = 5) uniform sampler2D linearStrip;  // the same bytes without it

layout(location = 0) out vec4 outFetch;
layout(location = 1) out vec4 outSample;
layout(location = 2) out vec4 outUpload;
layout(location = 3) out vec4 outStrip;

void main()
{
    ivec2 t = fragTexel(ivec2(targetSize.xy));
    outFetch = texelFetch(written, t, 0);
    outSample = texture(written, fragUv(targetSize.xy));
    outUpload = texelFetch(uploadTex, t, 0);
    outStrip = vec4(texelFetch(srgbStrip, t, 0).r, texelFetch(linearStrip, t, 0).r, 0.0, 1.0 + consumeVaryings());
}
