#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_sky_vertex for the sky pass, its block's members named for it (the arithmetic the body's)
#define uBackdrop sky_u_backdrop
#define uSkyReflection sky_u_sky_reflection
#define uMist sky_u_mist
#define uMistShape sky_u_mist_shape
#define uFogView sky_u_fog_view
#define uFogLens sky_u_fog_lens
#define uFogRange sky_u_fog_range
#include "waveform_sky_vertex.glsl"
