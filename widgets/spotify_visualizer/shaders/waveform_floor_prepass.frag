#version 460 core
// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): waveform_floor_fragment, the prepass variant (its members renamed, the arithmetic the body's)
#define uSpecMode uPrepassSpecMode
#define uViewport uPrepassViewport
#include "waveform_floor_fragment.glsl"
