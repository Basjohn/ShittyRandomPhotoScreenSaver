#version 440
// N0.3 scene 1, second pass (coordinates): what the conventions include says about this fragment, beside the raw
// values it is derived from, as float32 (the analysis in python/run_n03.py compares them with the content).
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions
//@n03_common

layout(location = 0) out vec4 outPixel;    // fragPixel, fragTexel
layout(location = 1) out vec4 outUv;       // fragUv, ndcToUv(the clip NDC)
layout(location = 2) out vec4 outRaw;      // gl_FragCoord.xy, the item position the geometry put here
layout(location = 3) out vec4 outNdc;      // the clip NDC (corrected matrix), the view NDC (OpenGL form)
layout(location = 4) out vec4 outMapping;  // uvToNdc(fragUv), ndcToUv(the view NDC)

void main()
{
    vec2 size = targetSize.xy;
    outPixel = vec4(fragPixel(size), vec2(fragTexel(ivec2(size))));
    outUv = vec4(fragUv(size), ndcToUv(v_ndc_post));
    outRaw = vec4(gl_FragCoord.xy, v_item);
    outNdc = vec4(v_ndc_post, v_ndc_view);
    outMapping = vec4(uvToNdc(fragUv(size)), ndcToUv(v_ndc_view) + consumeVaryings());
}
