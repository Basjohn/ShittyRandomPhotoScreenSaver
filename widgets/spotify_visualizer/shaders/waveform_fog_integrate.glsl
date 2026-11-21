layout(local_size_x=8,local_size_y=8) in;
layout(rgba16f,binding=0) uniform readonly image3D uFogInject;
layout(rgba16f,binding=1) uniform writeonly image3D uFogIntegrated;
layout(std140, binding = 16) uniform FogVolumeDispatch {
    mat4 uFogInvView;
    vec4 uFogLens;
    vec4 uFogRange;
};

float fogDepthFraction(float depth) {
    if(uFogLens.w>0.0) {
        float focus=max(uFogRange.w-1.0,0.0);
        return (asinh((depth-focus)/uFogLens.w)-asinh((uFogRange.x-focus)/uFogLens.w)) /
            (asinh((uFogRange.y-focus)/uFogLens.w)-asinh((uFogRange.x-focus)/uFogLens.w));
    }
    return log(max(depth,uFogRange.x)/uFogRange.x)/log(uFogRange.y/uFogRange.x);
}
float fogSliceDepth(float f) {
    if(uFogLens.w>0.0) {
        float focus=max(uFogRange.w-1.0,0.0);
        return focus+uFogLens.w*sinh(mix(asinh((uFogRange.x-focus)/uFogLens.w),
            asinh((uFogRange.y-focus)/uFogLens.w),f/uFogRange.z));
    }
    return uFogRange.x*pow(uFogRange.y/uFogRange.x,f/uFogRange.z);
}

void main() {
    ivec3 size=imageSize(uFogInject);
    ivec2 column=ivec2(gl_GlobalInvocationID.xy);
    if(any(greaterThanEqual(column,size.xy))) return;
    vec2 ndc=(vec2(column)+0.5)/vec2(size.xy)*2.0-1.0;
    // World length per unit of view depth along this column's ray.
    float stretch=length(vec3(ndc*uFogLens.xy,1.0));
    vec3 scatter=vec3(0.0);
    float transmittance=1.0;
    for(int k=0;k<size.z;k++) {
        vec4 medium=imageLoad(uFogInject,ivec3(column,k));
        float slice=exp(-medium.a*(fogSliceDepth(float(k+1))-fogSliceDepth(float(k)))*stretch);
        scatter+=transmittance*medium.rgb*(1.0-slice);
        transmittance*=slice;
        imageStore(uFogIntegrated,ivec3(column,k),vec4(scatter,transmittance));
    }
}
