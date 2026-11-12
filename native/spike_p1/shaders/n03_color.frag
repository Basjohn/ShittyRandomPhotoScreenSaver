#version 440
// N0.3 scenes 2 and 3: the vertex colour (scene 2's planes with the depth test, scene 3's culled triangles).
//@n03_common

layout(location = 0) out vec4 fragColor;

void main()
{
    fragColor = vec4(v_color.rgb, v_color.a + consumeVaryings());
}
