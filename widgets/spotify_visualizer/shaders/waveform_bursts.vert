#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_bursts_vertex for the bursts pass, its block's members named for it (the arithmetic the body's)
#define uMvp bursts_uMvp
#define uViewport bursts_uViewport
#define uNow bursts_uNow
#define uMist bursts_uMist
#define uMistShape bursts_uMistShape
#define uFogView bursts_uFogView
#define uFogLens bursts_uFogLens
#define uFogRange bursts_uFogRange
#define uGradeStops bursts_uGradeStops
#define uGrade bursts_uGrade
#include "waveform_bursts_vertex.glsl"
