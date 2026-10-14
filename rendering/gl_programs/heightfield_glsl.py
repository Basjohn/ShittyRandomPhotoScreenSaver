"""Opt-in GPU mirror of the canonical bilinear heightfield sampler."""

HEIGHTFIELD_GLSL = """
float sceneHeightfield(sampler2D field, int size, vec2 uv) {
    // Canonical UV endpoints are the centres of the first and last texels.
    vec2 centreUv = (clamp(uv, vec2(0.0), vec2(1.0)) * float(size - 1) + 0.5) / float(size);
    return textureLod(field, centreUv, 0.0).r;
}
float sceneHeightfieldBankDistance(sampler2D field, int size, vec2 uv) {
    vec2 centreUv = (clamp(uv, vec2(0.0), vec2(1.0)) * float(size - 1) + 0.5) / float(size);
    return textureLod(field, centreUv, 0.0).g;
}
bool sceneHeightfieldWater(float authoredHeight) {
    return authoredHeight == 0.0;
}
vec4 sceneHeightfieldWeights(float t) {
    float t2=t*t,t3=t2*t;
    return vec4(pow(1.0-t,3.0),3.0*t3-6.0*t2+4.0,-3.0*t3+3.0*t2+3.0*t+1.0,t3)/6.0;
}
float sceneHeightfieldCurve(sampler2D field,int size,vec2 uv) {
    vec2 p=clamp(uv,vec2(0.0),vec2(1.0))*float(size-1);
    ivec2 cell=ivec2(floor(p));
    vec4 wx=sceneHeightfieldWeights(fract(p.x)),wy=sceneHeightfieldWeights(fract(p.y));
    float height=0.0;
    for (int y=0;y<4;++y) for (int x=0;x<4;++x) {
        ivec2 sampleCell=clamp(cell+ivec2(x-1,y-1),ivec2(0),ivec2(size-1));
        height+=wx[x]*wy[y]*texelFetch(field,sampleCell,0).r;
    }
    return height;
}
"""

HEIGHTFIELD_WIRE_GLSL = """
vec2 sceneHeightfieldCurveCoordinates(vec2 uv,float height) {
    return uv+vec2(0.045*sin(uv.y*7.0+height*2.0),
                   0.035*sin(uv.x*6.0-height*3.0));
}
float sceneHeightfieldCurveWire(vec2 uv,float height,float cells,float pixels) {
    vec2 coordinates=sceneHeightfieldCurveCoordinates(uv,height)*vec2(cells,cells*0.65);
    vec2 widths=max(fwidth(coordinates),vec2(1e-5));
    vec2 distance=abs(fract(coordinates-0.5)-0.5)/widths;
    float diagonal=coordinates.x+coordinates.y+0.28*sin(uv.x*6.0+uv.y*5.0+height*3.0);
    float diagonalDistance=abs(fract(diagonal-0.5)-0.5)/max(fwidth(diagonal),1e-5);
    float contour=height*cells*0.45;
    float contourWidth=fwidth(contour);
    float contourDistance=contourWidth>1e-4 ? abs(fract(contour-0.5)-0.5)/contourWidth : 1e5;
    return 1.0-smoothstep(0.0,pixels,min(min(distance.x,distance.y),min(diagonalDistance,contourDistance)));
}
float sceneHeightfieldWaterCurves(vec2 uv,float height,float cells,float pixels) {
    // Two continuous, coherent families on the displaced surface. The lake
    // does not inherit the terrain's diagonal drafting pattern.
    vec2 coordinates=(uv+vec2(0.055*sin(uv.y*5.0+height*3.0),
                             0.025*sin(uv.x*7.0-height*2.0)))*vec2(cells*0.4,cells*0.9);
    vec2 widths=max(fwidth(coordinates),vec2(1e-5));
    vec2 distance=abs(fract(coordinates-0.5)-0.5)/widths;
    vec2 curves=1.0-smoothstep(vec2(0.0),vec2(pixels),distance);
    float contour=height*cells*0.6;
    float width=fwidth(contour);
    float contourDistance=width>1e-4 ? abs(fract(contour-0.5)-0.5)/width : 1e5;
    return max(max(curves.x*0.14,curves.y),1.0-smoothstep(0.0,pixels,contourDistance));
}
"""

__all__ = ["HEIGHTFIELD_GLSL", "HEIGHTFIELD_WIRE_GLSL"]
