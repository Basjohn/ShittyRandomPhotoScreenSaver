#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_strays_vertex for the strays pass, its block's members named for it (the arithmetic the body's)
#define uFloorGive strays_uFloorGive
#define uSurface strays_uSurface
#define uSweepAxis strays_uSweepAxis
#define uFloorContact strays_uFloorContact
#define uFloorGiveFrame strays_uFloorGiveFrame
#define uVertexBase strays_uVertexBase
#define uMvp strays_uMvp
#define uViewport strays_uViewport
#define uStray strays_uStray
#define uStrayLook strays_uStrayLook
#define uStrayClock strays_uStrayClock
#define uStrayAdmission strays_uStrayAdmission
#define uStrayBirthNow strays_uStrayBirthNow
#define uStrayPulse strays_uStrayPulse
#define uMistOrigin strays_uMistOrigin
#define uMist strays_uMist
#define uMistShape strays_uMistShape
#define uFogView strays_uFogView
#define uFogLens strays_uFogLens
#define uFogRange strays_uFogRange
#define uGradeStops strays_uGradeStops
#define uGrade strays_uGrade
#include "waveform_strays_vertex.glsl"
