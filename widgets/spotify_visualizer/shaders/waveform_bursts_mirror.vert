#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_bursts_vertex, the mirror variant (its members renamed, the arithmetic the body's)
#define uMvp uMirrorMvp
#define uEye uMirrorEye
#define uViewZ uMirrorViewZ
#define uViewport uMirrorViewport
#define uFogView uMirrorFogView
#define uFogRange uMirrorFogRange
#define uFogInvView uMirrorFogInvView
#define uSkyReflection uMirrorSkyReflection
#include "waveform_bursts_vertex.glsl"
