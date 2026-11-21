#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_sky_fragment for the sky_mirror pass, its block's members named for it (the arithmetic the body's)
#define uBackdrop sky_mirror_uBackdrop
#define uSkyReflection sky_mirror_uSkyReflection
#define uMist sky_mirror_uMist
#define uMistShape sky_mirror_uMistShape
#define uFogView sky_mirror_uFogView
#define uFogLens sky_mirror_uFogLens
#define uFogRange sky_mirror_uFogRange
#include "waveform_sky_fragment.glsl"
