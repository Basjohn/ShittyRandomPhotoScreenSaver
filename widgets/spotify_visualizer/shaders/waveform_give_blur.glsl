layout(local_size_x=64) in;
layout(rgba32f,binding=0) readonly uniform image2D uSections;
layout(rgba32f,binding=1) writeonly uniform image2D uOutput;
layout(std140, binding = 16) uniform FloorGiveBlurDispatch {
    vec4 uGiveBlur;
};

void main() {
    int column=int(gl_GlobalInvocationID.x),samples=int(uGiveBlur.x);
    if(column>=samples)return;
    int reach_=int(ceil(2.0*uGiveBlur.y));
    vec4 depth=vec4(0),centre=vec4(0),inverse=vec4(1);
    for(int owner=0;owner<4;owner++) {
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
