#version 440
// The scene probe's prefilter (ABI 42, N5.6; native/core/src/cube_prefilter.h): level L of one cube face from the
// cube's level L - 1, over a cone of directions (32 taps, Gaussian, sampled across face edges), the cone about two of
// the level's texels wide. The filter is rendering/quick/scene3d/probe.py's _PREFILTER_FRAGMENT, tap for tap; the face
// is a render target of its own (no geometry-shader gl_Layer, which D3D lacks: the lead's N4.d decision) and its rows
// are OpenGL's cube-map rows (memory row 0 is the face's bottom: probe.py's vNdc.y = -1), read through fragPixel.
#define SRPSS_NATIVE_CORE
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions

layout(location = 0) out vec4 FragColor;

layout(std140, binding = 0) uniform CubePrefilter {
    mat4 uWorldToFace[6];   // each face's world-to-view rotation (probe.py scene3d_probe_face_rotation) in its 3 x 3
    float uCone;            // half-angle of the filter cone, radians
    float uSourceLod;       // the level read (L - 1)
    int uFace;              // the face drawn (OpenGL's order: +X, -X, +Y, -Y, +Z, -Z)
    float uSide;            // the level's side in texels
};
layout(binding = 1) uniform samplerCube uSource;

void main()
{
    vec2 fNdc = fragPixel(vec2(uSide)) / uSide * 2.0 - 1.0;
    vec3 axis = transpose(mat3(uWorldToFace[uFace])) * normalize(vec3(fNdc, -1.0));
    vec3 helper = abs(axis.y) < 0.99 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
    vec3 u = normalize(cross(helper, axis));
    vec3 v = cross(axis, u);
    float sigma = max(uCone * 0.5, 1e-4);
    vec3 sum = vec3(0.0);
    float weights = 0.0;
    for (int i = 0; i < 32; ++i) {
        float cosTheta = 1.0 - (float(i) + 0.5) / 32.0 * (1.0 - cos(uCone));
        float theta = acos(cosTheta);
        float phi = float(i) * 2.39996323;
        vec3 d = axis * cosTheta + (u * cos(phi) + v * sin(phi)) * sin(theta);
        float w = exp(-theta * theta / (2.0 * sigma * sigma));
        sum += textureLod(uSource, d, uSourceLod).rgb * w;
        weights += w;
    }
    FragColor = vec4(sum / weights, 1.0);
}
