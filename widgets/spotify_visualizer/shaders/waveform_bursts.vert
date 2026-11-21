#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_bursts_vertex for the bursts pass, its block's members named for it (the arithmetic the body's)
#define uMvp bursts_u_mvp
#define uViewport bursts_u_viewport
#define uNow bursts_u_now
#define uMist bursts_u_mist
#define uMistShape bursts_u_mist_shape
#define uFogView bursts_u_fog_view
#define uFogLens bursts_u_fog_lens
#define uFogRange bursts_u_fog_range
#define uGradeStops bursts_u_grade_stops
#define uGrade bursts_u_grade
#include "waveform_bursts_vertex.glsl"
