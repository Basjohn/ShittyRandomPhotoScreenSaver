
// N0.3 scenes: the declarations every fragment stage shares (spliced in at the n03_common marker by
// cmake/compose_shader.cmake). The varyings and the Scene block are n03_geom.vert's.
layout(location = 0) in vec2 v_item;      // the model-space position (scenes 1 and 3: item pixels, y down)
layout(location = 1) in vec4 v_color;
layout(location = 2) in vec2 v_ndc_post;  // NDC of the uploaded (corrected) matrix: what the rasterizer used
layout(location = 3) in vec2 v_ndc_view;  // NDC of the same matrix in OpenGL form (y up), uncorrected
layout(std140, binding = 0) uniform Scene {
    mat4 uploaded;
    mat4 glForm;
    vec4 targetSize;   // xy: this pass's target in pixels
    vec4 params;       // x: the checker's cell size
};
// Every varying the vertex stage writes is read, so no stage leaves an output unconsumed (the validation layer
// reports one). The value is 0 for every finite input, so adding it changes no output bit.
float consumeVaryings()
{
    return (v_item.x + v_color.x + v_ndc_post.x + v_ndc_view.x) * 0.0;
}
