#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_ribbon_body_sorted for the ribbon pass, its block's members named for it (the arithmetic the body's)
#define SRPSS_SCENE_ITEM_ONLY
#define uFloorGive ribbon_u_floor_give
#define uSurface ribbon_u_surface
#define uSweepAxis ribbon_u_sweep_axis
#define uFloorContact ribbon_u_floor_contact
#define uFloorGiveFrame ribbon_u_floor_give_frame
#define uMvp ribbon_u_mvp
#define uViewport ribbon_u_viewport
#define uRim ribbon_u_rim
#define uEye ribbon_u_eye
#define uDrawCounts ribbon_u_draw_counts
#define uDrawBases ribbon_u_draw_bases
#define uContinuationBefore ribbon_u_continuation_before
#define uContinuationAfter ribbon_u_continuation_after
#define uDiagnostic ribbon_u_diagnostic
#define uViewZ ribbon_u_view_z
#define uStrands ribbon_u_strands
#define uBody ribbon_u_body
#define uFill ribbon_u_fill
#define uGlint ribbon_u_glint
#define uTone ribbon_u_tone
#define uAge ribbon_u_age
#define uMistOrigin ribbon_u_mist_origin
#define uGlow ribbon_u_glow
#define uLattice ribbon_u_lattice
#define uLatticeTone ribbon_u_lattice_tone
#define uGradeStops ribbon_u_grade_stops
#define uGrade ribbon_u_grade
#define uMist ribbon_u_mist
#define uMistShape ribbon_u_mist_shape
#define uFogView ribbon_u_fog_view
#define uFogLens ribbon_u_fog_lens
#define uFogRange ribbon_u_fog_range
#define uPulseRim ribbon_u_pulse_rim
#define uPulseRimShape ribbon_u_pulse_rim_shape
#include "waveform_ribbon_body_sorted.glsl"
