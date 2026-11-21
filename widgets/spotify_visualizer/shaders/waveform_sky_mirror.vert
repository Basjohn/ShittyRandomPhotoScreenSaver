#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_sky_vertex for the sky_mirror pass, its block's members named for it (the arithmetic the body's)
#define uViewport sky_mirror_u_viewport
#define uBackdrop sky_mirror_u_backdrop
#define uSkyReflection sky_mirror_u_sky_reflection
#define uMist sky_mirror_u_mist
#define uMistShape sky_mirror_u_mist_shape
#define uFogView sky_mirror_u_fog_view
#define uFogLens sky_mirror_u_fog_lens
#define uFogRange sky_mirror_u_fog_range
#include "waveform_sky_vertex.glsl"
