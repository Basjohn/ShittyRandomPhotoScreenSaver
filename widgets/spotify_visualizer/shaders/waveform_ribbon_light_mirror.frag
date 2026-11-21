#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_ribbon_light for the ribbon_mirror pass, its block's members named for it (the arithmetic the body's)
#define SRPSS_NO_EMISSION
#define SRPSS_GL_FORM_TARGET
#define uFloorGive ribbon_mirror_u_floor_give
#define uSurface ribbon_mirror_u_surface
#define uSweepAxis ribbon_mirror_u_sweep_axis
#define uFloorContact ribbon_mirror_u_floor_contact
#define uFloorGiveFrame ribbon_mirror_u_floor_give_frame
#define uMvp ribbon_mirror_u_mvp
#define uViewport ribbon_mirror_u_viewport
#define uRim ribbon_mirror_u_rim
#define uEye ribbon_mirror_u_eye
#define uDrawCounts ribbon_mirror_u_draw_counts
#define uDrawBases ribbon_mirror_u_draw_bases
#define uContinuationBefore ribbon_mirror_u_continuation_before
#define uContinuationAfter ribbon_mirror_u_continuation_after
#define uDiagnostic ribbon_mirror_u_diagnostic
#define uViewZ ribbon_mirror_u_view_z
#define uStrands ribbon_mirror_u_strands
#define uBody ribbon_mirror_u_body
#define uFill ribbon_mirror_u_fill
#define uGlint ribbon_mirror_u_glint
#define uTone ribbon_mirror_u_tone
#define uAge ribbon_mirror_u_age
#define uMistOrigin ribbon_mirror_u_mist_origin
#define uGlow ribbon_mirror_u_glow
#define uLattice ribbon_mirror_u_lattice
#define uLatticeTone ribbon_mirror_u_lattice_tone
#define uGradeStops ribbon_mirror_u_grade_stops
#define uGrade ribbon_mirror_u_grade
#define uMist ribbon_mirror_u_mist
#define uMistShape ribbon_mirror_u_mist_shape
#define uFogView ribbon_mirror_u_fog_view
#define uFogLens ribbon_mirror_u_fog_lens
#define uFogRange ribbon_mirror_u_fog_range
#define uPulseRim ribbon_mirror_u_pulse_rim
#define uPulseRimShape ribbon_mirror_u_pulse_rim_shape
#include "waveform_ribbon_light.glsl"
