#version 440
// The photo environment's copy (Current_Plan.md N5.2c, N4.j; native/core/src/post_stages.h, "The photo environment"):
// rendering/quick/scene3d/environment.py _COPY_FRAGMENT, 16 bilinear taps a quarter copy texel apart over the output
// texel's footprint (a box wide enough for a 4K photograph), summed in Python's order and divided by 16, opaque. The
// core's rows are top first on every backend (conventions.h rule 2) and so are the photograph's: the copy's row r reads
// the photograph at v = (r + 0.5) / h as Python's GL row r does (vUv is 1 at the copy's top row, so v is 1 - vUv.y; the
// taps' offsets keep Python's sign in v), so the copy holds Python's texels at Python's rows and the passes that read it
// at their own uv see Python's reflection. uStep is Python's, divided in double and packed as float by the core.
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;

layout(std140, binding = 0) uniform ScenePhotoCopy {
    vec2 uStep;
};
layout(binding = 1) uniform sampler2D uPhoto;

void main()
{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    vec3 sum = vec3(0.0);
    for (int y = 0; y < 4; ++y) {
        for (int x = 0; x < 4; ++x) {
            sum += texture(uPhoto, uv + (vec2(x, y) - 1.5) * uStep).rgb;
        }
    }
    FragColor = vec4(sum / 16.0, 1.0);
}
