
#ifndef SRPSS_VERTEX_INDEX
#define SRPSS_VERTEX_INDEX
#ifdef VULKAN
#define srpssVertexIndex gl_VertexIndex
#define srpssInstanceIndex gl_InstanceIndex
#else
#define srpssVertexIndex gl_VertexID
#define srpssInstanceIndex gl_InstanceID
#endif
#endif
layout(std140, binding = 18) uniform WaveformSky {
    vec3 uBackdrop;
    int uSkyReflection;
    vec4 uMist;
    vec4 uMistShape;
    mat4 uFogView;
    vec4 uFogLens;
    vec4 uFogRange;
};

#ifndef SRPSS_VERTEX_INDEX
#define SRPSS_VERTEX_INDEX
#ifdef VULKAN
#define srpssVertexIndex gl_VertexIndex
#define srpssInstanceIndex gl_InstanceIndex
#else
#define srpssVertexIndex srpssVertexIndex
#define srpssInstanceIndex srpssInstanceIndex
#endif
#endif
layout(location = 0) out vec2 vNdc;
void main() {
    vec2 corner=vec2(float((srpssVertexIndex<<1)&2),float(srpssVertexIndex&2));
    vNdc=corner*2.0-1.0;
    gl_Position=vec4(vNdc,0.0,1.0);
}
