#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_strays_vertex for the strays pass, its block's members named for it (the arithmetic the body's)
#define uFloorGive strays_u_floor_give
#define uSurface strays_u_surface
#define uSweepAxis strays_u_sweep_axis
#define uFloorContact strays_u_floor_contact
#define uFloorGiveFrame strays_u_floor_give_frame
#define uVertexBase strays_u_vertex_base
#define uMvp strays_u_mvp
#define uViewport strays_u_viewport
#define uStray strays_u_stray
#define uStrayLook strays_u_stray_look
#define uStrayClock strays_u_stray_clock
#define uStrayAdmission strays_u_stray_admission
#define uStrayBirthNow strays_u_stray_birth_now
#define uStrayPulse strays_u_stray_pulse
#define uMistOrigin strays_u_mist_origin
#define uMist strays_u_mist
#define uMistShape strays_u_mist_shape
#define uFogView strays_u_fog_view
#define uFogLens strays_u_fog_lens
#define uFogRange strays_u_fog_range
#define uGradeStops strays_u_grade_stops
#define uGrade strays_u_grade
#include "waveform_strays_vertex.glsl"
