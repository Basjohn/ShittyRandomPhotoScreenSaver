#version 440
// N0.3's convention scenes (Docs/Future_Work/Native_Core_P3_Decisions.md, "The three test scenes"): the one vertex
// stage of every pass. The matrix arrives in OpenGL form and is corrected once, at upload, by the core (rule 1):
// `uploaded` is that corrected matrix, `glForm` the same matrix uncorrected (kept only to record the view NDC).

layout(location = 0) in vec4 position;   // the run's model space (scenes 1 and 3: item pixels, y down; 2: view space)
layout(location = 1) in vec4 color;

layout(location = 0) out vec2 v_item;
layout(location = 1) out vec4 v_color;
layout(location = 2) out vec2 v_ndc_post;
layout(location = 3) out vec2 v_ndc_view;

layout(std140, binding = 0) uniform Scene {
    mat4 uploaded;
    mat4 glForm;
    vec4 targetSize;
    vec4 params;
};

void main()
{
    vec4 clip = uploaded * position;
    vec4 view = glForm * position;
    v_item = position.xy;
    v_color = color;
    v_ndc_post = clip.xy / clip.w;
    v_ndc_view = view.xy / view.w;
    gl_Position = clip;
}
