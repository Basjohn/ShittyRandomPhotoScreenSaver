#version 440
#ifdef VULKAN
#define vertexIndex gl_VertexIndex
#else
#define vertexIndex gl_VertexID
#endif
// An actual four-vertex quad, through the same own-vertex path N3.2's geometry uses.
const vec2 corners[4] = vec2[4](vec2(-1, -1), vec2(1, -1), vec2(-1, 1), vec2(1, 1));
void main()
{
    gl_Position = vec4(corners[vertexIndex], 0.0, 1.0);
}
