#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_strays_fragment for the strays_mirror pass, its block's members named for it (the arithmetic the body's)
#define uFloorGive strays_mirror_uFloorGive
#define uSurface strays_mirror_uSurface
#define uSweepAxis strays_mirror_uSweepAxis
#define uFloorContact strays_mirror_uFloorContact
#define uFloorGiveFrame strays_mirror_uFloorGiveFrame
#define uVertexBase strays_mirror_uVertexBase
#define uMvp strays_mirror_uMvp
#define uViewport strays_mirror_uViewport
#define uStray strays_mirror_uStray
#define uStrayLook strays_mirror_uStrayLook
#define uStrayClock strays_mirror_uStrayClock
#define uStrayAdmission strays_mirror_uStrayAdmission
#define uStrayBirthNow strays_mirror_uStrayBirthNow
#define uStrayPulse strays_mirror_uStrayPulse
#define uMistOrigin strays_mirror_uMistOrigin
#define uMist strays_mirror_uMist
#define uMistShape strays_mirror_uMistShape
#define uFogView strays_mirror_uFogView
#define uFogLens strays_mirror_uFogLens
#define uFogRange strays_mirror_uFogRange
#define uGradeStops strays_mirror_uGradeStops
#define uGrade strays_mirror_uGrade
#include "waveform_strays_fragment.glsl"
