#version 440
// A scene target's clearing draw with 4 colour attachment(s) (Current_Plan.md item 8b, N3.1; D14 point 4; targets.h
// rule B): drawn over the whole allocation with blending off at a run's first pass on the target in a record, every
// attachment to its declared clear value and the depth (when the target has one: depth test always, writes on) to the
// far plane, as the Python renderer's SceneTarget.begin clears its whole allocation. The target keeps its contents, so
// it is cleared by this draw and never by an UNDEFINED load.

layout(std140, binding = 0) uniform SceneClear {
    vec4 uClear[4];
};

layout(location = 0) out vec4 clear0;
layout(location = 1) out vec4 clear1;
layout(location = 2) out vec4 clear2;
layout(location = 3) out vec4 clear3;

void main()
{
    clear0 = uClear[0];
    clear1 = uClear[1];
    clear2 = uClear[2];
    clear3 = uClear[3];
    gl_FragDepth = 1.0;
}
