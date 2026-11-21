#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_bursts_fragment for the bursts_mirror pass, its block's members named for it (the arithmetic the body's)
#define uMvp bursts_mirror_uMvp
#define uViewport bursts_mirror_uViewport
#define uNow bursts_mirror_uNow
#define uMist bursts_mirror_uMist
#define uMistShape bursts_mirror_uMistShape
#define uFogView bursts_mirror_uFogView
#define uFogLens bursts_mirror_uFogLens
#define uFogRange bursts_mirror_uFogRange
#define uGradeStops bursts_mirror_uGradeStops
#define uGrade bursts_mirror_uGrade
#include "waveform_bursts_fragment.glsl"
