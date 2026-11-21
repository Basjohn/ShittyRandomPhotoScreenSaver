#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_sky_vertex for the sky pass, its block's members named for it (the arithmetic the body's)
#define uBackdrop sky_uBackdrop
#define uSkyReflection sky_uSkyReflection
#define uMist sky_uMist
#define uMistShape sky_uMistShape
#define uFogView sky_uFogView
#define uFogLens sky_uFogLens
#define uFogRange sky_uFogRange
#include "waveform_sky_vertex.glsl"
