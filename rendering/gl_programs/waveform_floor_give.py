"""The yielding floor's field: reduced once per frame from the published swept cloth; no camera inputs.

Per world x and per ribbon (one channel each of three rows): how deep the floor gives under that ribbon, the world z of
the dent's centre and its inverse squared z radius (sampled by ``FLOOR_GIVE_GLSL``). Each cross-section is the exact
cambered section the ribbon draws (``fieldSection`` without the floor map); every section point that reaches below the
contact level adds its reach (softplus: smooth, never a threshold), and the section's dent is the deepest reach, centred
at the reach-weighted mean z with the reach-weighted spread of z added to the radius (a flat sheet lying on the floor
dents the floor across its width; an edge dents it under the edge, and the centre moves continuously as the sheet
turns over). Sections are blurred along x (Gaussian), so the field is a smooth function of the cloth, which is itself
smooth in time: the dent cannot pop or flicker. Ribbons fade their dents with their own visibility.

Two small dispatches: the sections, one invocation per (x sample, ribbon) so the cloth is evaluated once per sample in
parallel; then the blur along x over those samples, one invocation per x sample.
"""
from rendering.gl_programs.scene3d import Scene3DBlockLayout
from rendering.gl_programs.waveform_atmosphere import (FIELD_BLOCK_BINDING, FIELD_RIBBONS, PACKET_FIELDS,
                                                       packet_compute_glsl)

FLOOR_GIVE_ROWS = 3
# uGiveSpan: first x, last x, samples, edge fade (world); uGiveShape: contact level (world y: floor plus gap), reach
# softness, cross camber, unused. The packet's grade is never set here (zero: the sections read only the light's
# presence).
FLOOR_GIVE_SECTION_BLOCK = Scene3DBlockLayout.of('FloorGiveSectionDispatch',
                                                 (*PACKET_FIELDS, ('uGiveSpan', 'vec4'), ('uGiveShape', 'vec4')))
# uGiveBlur: samples, blur sigma (samples), share of the reach the floor takes, base z radius.
FLOOR_GIVE_BLUR_BLOCK = Scene3DBlockLayout.of('FloorGiveBlurDispatch', (('uGiveBlur', 'vec4'),))
FLOOR_GIVE_SECTION_COMPUTE = ('#version 460 core\n'
                              + packet_compute_glsl(FLOOR_GIVE_SECTION_BLOCK.glsl(FIELD_BLOCK_BINDING)) + '''
layout(local_size_x=64) in;
layout(rgba32f,binding=1) writeonly uniform image2D uSections;  // binding 0 is the packet
const int ACROSS=9;
void main() {
    int column=int(gl_GlobalInvocationID.x),owner=int(gl_GlobalInvocationID.y),samples=int(uGiveSpan.z);
    if(column>=samples)return;
    float x=mix(uGiveSpan.x,uGiveSpan.y,float(column)/float(samples-1));
    // Deepest reach, reach-weighted mass and z moments: the blur sums these.
    vec4 section=vec4(0);
    float visible=owner<int(uFieldOrigin.w)?clamp(min(paths[owner].colourA.a,paths[owner].colourB.a),0.0,1.0):0.0;
    if(visible>0.0) {
        vec4 shape,light;packetField(x,owner,shape,light);
        if(light.a>0.0) {
            vec2 side=vec2(cos(shape.w),sin(shape.w)),bow=vec2(-side.y,side.x);
            for(int i=0;i<ACROSS;i++) {
                float across=-1.0+2.0*float(i)/float(ACROSS-1);
                vec2 point=shape.xy+shape.z*(across*side+(1.0-across*across)*uGiveShape.z*bow);
                float below=(uGiveShape.x-point.x)/uGiveShape.y;
                float reach=uGiveShape.y*(max(below,0.0)+log(1.0+exp(-abs(below))));
                section.x=max(section.x,reach);
                float w=reach*reach;
                section.yzw+=vec3(w,w*point.y,w*point.y*point.y);
            }
            float edge=smoothstep(uGiveSpan.x,uGiveSpan.x+uGiveSpan.w,x)*(1.0-smoothstep(uGiveSpan.y-uGiveSpan.w,uGiveSpan.y,x));
            section.x*=visible*edge;
        }
    }
    imageStore(uSections,ivec2(column,owner),section);
}
''')
FLOOR_GIVE_BLUR_COMPUTE = '''#version 460 core
layout(local_size_x=64) in;
layout(rgba32f,binding=0) readonly uniform image2D uSections;
layout(rgba32f,binding=1) writeonly uniform image2D uOutput;
''' + FLOOR_GIVE_BLUR_BLOCK.glsl(FIELD_BLOCK_BINDING) + '''
void main() {
    int column=int(gl_GlobalInvocationID.x),samples=int(uGiveBlur.x);
    if(column>=samples)return;
    int reach_=int(ceil(2.0*uGiveBlur.y));
    vec4 depth=vec4(0),centre=vec4(0),inverse=vec4(1);
    for(int owner=0;owner<OWNERS;owner++) {
        float weights=0.0,deepest=0.0,mass=0.0,first=0.0,second=0.0;
        for(int k=-reach_;k<=reach_;k++) {
            float weight=exp(-0.5*float(k*k)/(uGiveBlur.y*uGiveBlur.y));
            weights+=weight;
            int at=column+k;
            if(at<0 || at>=samples)continue;
            vec4 section=imageLoad(uSections,ivec2(at,owner));
            deepest+=weight*section.x;
            mass+=weight*section.y;first+=weight*section.z;second+=weight*section.w;
        }
        if(mass>1e-12 && deepest>0.0) {
            float mean=first/mass;
            float radius=uGiveBlur.w+sqrt(max(second/mass-mean*mean,0.0));
            depth[owner]=uGiveBlur.z*deepest/weights;
            centre[owner]=mean;
            inverse[owner]=1.0/(radius*radius);
        }
    }
    imageStore(uOutput,ivec2(column,0),depth);
    imageStore(uOutput,ivec2(column,1),centre);
    imageStore(uOutput,ivec2(column,2),inverse);
}
'''.replace('OWNERS', str(FIELD_RIBBONS))
