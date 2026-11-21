#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_bursts_vertex for the bursts_mirror pass, its block's members named for it (the arithmetic the body's)
#define SRPSS_GL_FORM_TARGET
#define uMvp bursts_mirror_u_mvp
#define uViewport bursts_mirror_u_viewport
#define uNow bursts_mirror_u_now
#define uMist bursts_mirror_u_mist
#define uMistShape bursts_mirror_u_mist_shape
#define uFogView bursts_mirror_u_fog_view
#define uFogLens bursts_mirror_u_fog_lens
#define uFogRange bursts_mirror_u_fog_range
#define uGradeStops bursts_mirror_u_grade_stops
#define uGrade bursts_mirror_u_grade
#include "waveform_bursts_vertex.glsl"
