#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_strays_fragment for the strays_mirror pass, its block's members named for it (the arithmetic the body's)
#define SRPSS_NO_EMISSION
#define uFloorGive strays_mirror_u_floor_give
#define uSurface strays_mirror_u_surface
#define uSweepAxis strays_mirror_u_sweep_axis
#define uFloorContact strays_mirror_u_floor_contact
#define uFloorGiveFrame strays_mirror_u_floor_give_frame
#define uVertexBase strays_mirror_u_vertex_base
#define uMvp strays_mirror_u_mvp
#define uViewport strays_mirror_u_viewport
#define uStray strays_mirror_u_stray
#define uStrayLook strays_mirror_u_stray_look
#define uStrayClock strays_mirror_u_stray_clock
#define uStrayAdmission strays_mirror_u_stray_admission
#define uStrayBirthNow strays_mirror_u_stray_birth_now
#define uStrayPulse strays_mirror_u_stray_pulse
#define uMistOrigin strays_mirror_u_mist_origin
#define uMist strays_mirror_u_mist
#define uMistShape strays_mirror_u_mist_shape
#define uFogView strays_mirror_u_fog_view
#define uFogLens strays_mirror_u_fog_lens
#define uFogRange strays_mirror_u_fog_range
#define uGradeStops strays_mirror_u_grade_stops
#define uGrade strays_mirror_u_grade
#include "waveform_strays_fragment.glsl"
