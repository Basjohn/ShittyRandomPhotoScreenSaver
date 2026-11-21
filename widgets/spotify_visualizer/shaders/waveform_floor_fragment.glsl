layout(std140, binding = 18) uniform WaveformFloor {
    vec4 uFloorGive;
    mat4 uMvp;
    mat4 uFloorInverseMvp;
    vec3 uEye;
    int uFlat;
    int uFogLit;
    vec2 uViewport;
    vec3 uBackdrop;
    vec3 uAmbient;
    vec3 uFloorTint;
    vec4 uFloor;
    vec3 uFloorTone;
    vec3 uRipple;
    vec4 uStreak;
    vec4 uHot;
    vec4 uMaterial;
    vec3 uMaterialShape;
    float uPool;
    float uPoolZ;
    vec3 uColumn;
    float uReflectionHue;
    vec3 uBound;
    int uSpecMode;
    vec3 uForward;
    vec2 uFloorGiveLook;
    vec4 uFieldOrigin;
    float uFieldSide;
    vec4 uGradeStops[6];
    vec4 uGrade;
    vec2 uBodySpan;
    vec4 uBodyShape;
    vec4 uMist;
    vec4 uMistShape;
    mat4 uFogView;
    vec4 uFogLens;
    vec4 uFogRange;
    vec4 uReflectionLook;
    vec4 uReflectionContact;
};

layout(binding = 13) uniform sampler2D uFloorGiveField;
  // field edge x (world), inverse covered length (0: off), maximum depth, x derivative step
float floorGiveDepth(vec2 xz) {
    float u=(xz.x-uFloorGive.x)*uFloorGive.y;
    if(u<=0.0 || u>=1.0) return 0.0;
    vec4 depth=textureLod(uFloorGiveField,vec2(u,0.5/3.0),0.0);
    vec4 centre=textureLod(uFloorGiveField,vec2(u,1.5/3.0),0.0);
    vec4 inverse=textureLod(uFloorGiveField,vec2(u,2.5/3.0),0.0);
    vec4 d=xz.y-centre;
    float total=dot(depth,exp(-d*d*inverse));
    return uFloorGive.z*(1.0-exp(-total/uFloorGive.z));
}
// d depth / d (x, z): central differences, one field column along x.
vec2 floorGiveGradient(vec2 xz) {
    vec2 e=vec2(uFloorGive.w,0.05);
    return vec2(floorGiveDepth(xz+vec2(e.x,0.0))-floorGiveDepth(xz-vec2(e.x,0.0)),
                floorGiveDepth(xz+vec2(0.0,e.y))-floorGiveDepth(xz-vec2(0.0,e.y)))/(2.0*e);
}

layout(location = 0) in vec2 vFloorNdc;



bool floorWorldHit(out vec3 world, out float depth) {
    // A miss leaves the eye's foot point (defined, so the quad's derivatives taken before the miss discards read a
    // value, never an unwritten one).
    world=vec3(uEye.x,0.0,uEye.z);
    depth=1.0;
    vec4 b=uFloorInverseMvp*vec4(vFloorNdc,1.0,1.0);
    vec3 farPoint=b.xyz/b.w;
    vec3 origin=uEye;
    vec3 direction=normalize(farPoint-origin);
    if(direction.y>=0.0)return false;
    float distance_=-origin.y/direction.y;
    if(distance_<=0.0)return false;
    world=origin+direction*distance_;
    world.y=0.0;
    if(uFloorGive.y>0.0) {
        const int STEPS=24;
        float near_=distance_,far_=distance_+uFloorGive.z/max(-direction.y,1e-4);
        float above=near_,below=far_;
        for(int i=1;i<STEPS;i++) {
            float t=mix(near_,far_,float(i)/float(STEPS));
            vec3 p=origin+direction*t;
            if(p.y<=-floorGiveDepth(p.xz)) { below=t; break; }
            above=t;
        }
        for(int i=0;i<8;i++) {
            float t=0.5*(above+below);
            vec3 p=origin+direction*t;
            if(p.y<=-floorGiveDepth(p.xz)) below=t; else above=t;
        }
        world=origin+direction*below;
        world.y=-floorGiveDepth(world.xz);
    }
    vec4 clip=uMvp*vec4(world,1.0);
    // Strictly below the clear depth, so the far ground survives GL_LESS.
    depth=clamp(0.5*(clip.z/clip.w+1.0),0.0,uintBitsToFloat(0x3f7fffffu));
    return true;
}

layout(binding = 0) uniform sampler2D uAlbedo;
layout(binding = 3) uniform sampler2D uRoughness;
layout(binding = 1) uniform sampler2D uSlope;      // height slope per uv unit (rg), from the smooth wet-surface height map






        // tile, micro tile, reflection gain, f0
    // albedo gain, broad relief amplitude, micro relief amplitude
       // reflection offset per unit slope: broad, micro across, micro along
       // optical streak length (world units at Streak Length 1), roughness min/max, broad-slope gain to roughness
          // reflected luminance at full strength; wet-film breakup share; suppression power; albedo mip bias
     // albedo contrast, relief shading, reflection relief breakup, source-light depth spread
 // material elongation along world z, relief mip bias, column height falloff (world)

       // the sheets' depth (world z)
       // fade length toward the camera, far sparkle strength, sparkle threshold
 // reflected chroma about its luminance (1 as reflected)
        // reflected-light ceiling (linear luminance), surface-light reach (world), far surface level
      // reflection term: 0 inline, 1 write it alone (pre-pass), 2 read it from uSpecular
layout(binding = 4) uniform sampler2D uSpecular;

 // yielding floor: reflection reach (world), relief shading per unit tilt
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;

#define SRPSS_CONVENTIONS_FRAGMENT
#ifndef SRPSS_CONVENTIONS_MAPPING
#define SRPSS_CONVENTIONS_MAPPING
layout(std140, binding = 17) uniform SrpssConventions {
    vec4 srpssConventions;   // the target's: x 1 flips the fragment row; y 1 negates the clip NDC's Y; z, w reserved
};
#ifdef SRPSS_NATIVE_CORE
vec2 ndcToUv(vec2 ndc) { return vec2(ndc.x, srpssConventions.y > 0.5 ? -ndc.y : ndc.y) * 0.5 + 0.5; }
vec2 uvToNdc(vec2 uv) {
    vec2 ndc = uv * 2.0 - 1.0;
    return vec2(ndc.x, srpssConventions.y > 0.5 ? -ndc.y : ndc.y);
}
#else
// This renderer: y is 0 for every target and never changes, so these are the authored arithmetic, bit for bit.
vec2 ndcToUv(vec2 ndc) { return ndc * 0.5 + 0.5; }
vec2 uvToNdc(vec2 uv) { return uv * 2.0 - 1.0; }
#endif
float viewDepthFromDepthTexture(float depth) { return depth; }
// IEC 61966-2-1, exactly, for an sRGB asset uploaded as plain RGBA8 (decided F4: no backend's sRGB flag is relied on;
// the GPU filters the encoded values before this decode).
vec3 srgbToLinear(vec3 encoded) {
    return mix(pow((encoded + 0.055) / 1.055, vec3(2.4)), encoded / 12.92, lessThanEqual(encoded, vec3(0.04045)));
}
#endif
#if defined(SRPSS_CONVENTIONS_FRAGMENT) && !defined(SRPSS_CONVENTIONS_FRAGMENT_DECLARED)
#define SRPSS_CONVENTIONS_FRAGMENT_DECLARED
vec2 fragPixel(vec2 targetSize) {
    return vec2(gl_FragCoord.x, srpssConventions.x > 0.5 ? targetSize.y - gl_FragCoord.y : gl_FragCoord.y);
}
ivec2 fragTexel(ivec2 targetSize) { return ivec2(fragPixel(vec2(targetSize))); }
vec2 fragUv(vec2 targetSize) { return fragPixel(targetSize) / targetSize; }
#endif

struct Knot {vec4 p;vec4 q;vec4 tangent;vec4 side;vec4 tint;};
struct Path {vec4 meta;vec4 extra;vec4 colourA;vec4 colourB;Knot knots[256];};
layout(std430,binding=0) readonly buffer Paths {Path paths[];};
 // packet origin+scroll, ribbon count
   // Travel Direction: -1 maps world x to the history axis mirrored (0/unset: +1)

Knot continuationControl(int owner,int i) {
    int count=int(paths[owner].meta.x),cap=int(paths[owner].extra.z),start=int(paths[owner].extra.y);
    return paths[owner].knots[(start+clamp(i,0,count-1))%cap];
}
// Components: transverse centre y/z, half width, axial twist.
vec4 continuationValues(Knot k) { return vec4(k.p.yz,k.p.w,k.q.y); }
vec4 continuationWeights(float u) {
    float u2=u*u,u3=u2*u,v=1.0-u;
    return vec4(v*v*v,3.0*u3-6.0*u2+4.0,-3.0*u3+3.0*u2+3.0*u+1.0,u3)/6.0;
}
vec4 clothField(int owner,float x) {
    int last=int(paths[owner].meta.x)-1,lo=0,hi=last;
    while(hi-lo>1) { int mid=(lo+hi)/2;if(continuationControl(owner,mid).p.x<=x)lo=mid;else hi=mid; }
    Knot a=continuationControl(owner,lo-1),b=continuationControl(owner,lo),
         c=continuationControl(owner,hi),d=continuationControl(owner,hi+1);
    vec4 av=continuationValues(a),bv=continuationValues(b),cv=continuationValues(c),dv=continuationValues(d);
    if(lo==0) { a.p.xyz=2.0*b.p.xyz-c.p.xyz;av.xy=a.p.yz; }
    if(hi==last) { d.p.xyz=2.0*c.p.xyz-b.p.xyz;dv.xy=d.p.yz; }
    vec4 xs=vec4(a.p.x,b.p.x,c.p.x,d.p.x);
    float u=clamp((x-b.p.x)/(c.p.x-b.p.x),0.0,1.0);
    for(int i=0;i<5;i++) {
        vec4 w=continuationWeights(u);
        vec4 dw=vec4(-3.0*(1.0-u)*(1.0-u),9.0*u*u-12.0*u,-9.0*u*u+6.0*u+3.0,3.0*u*u)/6.0;
        u=clamp(u-(dot(w,xs)-x)/max(dot(dw,xs),1e-8),0.0,1.0);
    }
    vec4 w=continuationWeights(u);
    return av*w.x+bv*w.y+cv*w.z+dv*w.w;
}
const int ANCHOR_INSET=2;
bool continuationAnchored(int owner) { return int(paths[owner].meta.x)>=2*ANCHOR_INSET+2; }
// The anchor segment's first chronological knot: its controls never include an admitted or evicted knot.
int continuationAnchorKnot(int owner,bool before) {
    return before?ANCHOR_INSET:int(paths[owner].meta.x)-2-ANCHOR_INSET;
}
float continuationAnchor(int owner,bool before) {
    int last=int(paths[owner].meta.x)-1;
    if(!continuationAnchored(owner)) return continuationControl(owner,before?0:last).p.x;
    int i=continuationAnchorKnot(owner,before);
    return mix(continuationControl(owner,i).p.x,continuationControl(owner,i+1).p.x,clamp(paths[owner].extra.w,0.0,1.0));
}
// Exact cloth value and its first/second axial derivatives at x (same spline and guards as clothField).
void clothJet(int owner,float x,out vec4 value,out vec4 first,out vec4 second) {
    int last=int(paths[owner].meta.x)-1,lo=0,hi=last;
    while(hi-lo>1) { int mid=(lo+hi)/2;if(continuationControl(owner,mid).p.x<=x)lo=mid;else hi=mid; }
    Knot a=continuationControl(owner,lo-1),b=continuationControl(owner,lo),
         c=continuationControl(owner,hi),d=continuationControl(owner,hi+1);
    vec4 av=continuationValues(a),bv=continuationValues(b),cv=continuationValues(c),dv=continuationValues(d);
    if(lo==0) { a.p.xyz=2.0*b.p.xyz-c.p.xyz;av.xy=a.p.yz; }
    if(hi==last) { d.p.xyz=2.0*c.p.xyz-b.p.xyz;dv.xy=d.p.yz; }
    vec4 xs=vec4(a.p.x,b.p.x,c.p.x,d.p.x);
    float u=clamp((x-b.p.x)/(c.p.x-b.p.x),0.0,1.0);
    for(int i=0;i<5;i++) {
        vec4 w=continuationWeights(u);
        vec4 dw=vec4(-3.0*(1.0-u)*(1.0-u),9.0*u*u-12.0*u,-9.0*u*u+6.0*u+3.0,3.0*u*u)/6.0;
        u=clamp(u-(dot(w,xs)-x)/max(dot(dw,xs),1e-8),0.0,1.0);
    }
    vec4 w=continuationWeights(u);
    vec4 dw=vec4(-3.0*(1.0-u)*(1.0-u),9.0*u*u-12.0*u,-9.0*u*u+6.0*u+3.0,3.0*u*u)/6.0;
    vec4 ddw=vec4(6.0*(1.0-u),18.0*u-12.0,-18.0*u+6.0,6.0*u)/6.0;
    float dx=dot(dw,xs),ddx=dot(ddw,xs);
    vec4 du=av*dw.x+bv*dw.y+cv*dw.z+dv*dw.w,ddu=av*ddw.x+bv*ddw.y+cv*ddw.z+dv*ddw.w;
    value=av*w.x+bv*w.y+cv*w.z+dv*w.w;
    first=du/dx;second=(ddu*dx-du*ddx)/(dx*dx*dx);
}
vec4 continuationField(int owner,float x) {
    int last=int(paths[owner].meta.x)-1;
    if(continuationAnchored(owner)) {
        float tail=continuationAnchor(owner,true),head=continuationAnchor(owner,false);
        bool before=x<=0.5*(tail+head);
        float origin=before?tail:head,delta=x-origin,sign_=before?-1.0:1.0;
        vec4 f,first,second;
        clothJet(owner,origin,f,first,second);
        int i=continuationAnchorKnot(owner,before);
        float reach=max(abs(continuationControl(owner,i+1).p.x-continuationControl(owner,i).p.x),1e-5);
        vec4 result=f;
        result.xy+=first.xy*sin(delta)+second.xy*(1.0-cos(delta));
        float s=abs(delta),scaled=min(s/reach,80.0),decay=exp(-scaled);
        vec2 g1=first.zw*sign_,g2=second.zw;
        g2.x=g2.x/f.z-pow(g1.x/f.z,2.0);g1.x/=f.z;
        vec2 correction=(g1*reach*scaled+(0.5*g2*reach*reach+g1*reach)*scaled*scaled)*decay;
        result.z=f.z*exp(correction.x);result.w=f.w+correction.y;
        return result;
    }
    bool before=x<=0.5*(continuationControl(owner,0).p.x+continuationControl(owner,last).p.x);
    Knot b=continuationControl(owner,before?0:last-1),c=continuationControl(owner,before?1:last);
    Knot a=continuationControl(owner,before?0:last-2),d=continuationControl(owner,before?2:last);
    vec4 av=continuationValues(a),bv=continuationValues(b),cv=continuationValues(c),dv=continuationValues(d);
    // Geometric guard positions extrapolate; scalar width/twist guards repeat, exactly as station().
    if(before) { a.p.xyz=2.0*b.p.xyz-c.p.xyz;av.xy=a.p.yz; }
    else { d.p.xyz=2.0*c.p.xyz-b.p.xyz;dv.xy=d.p.yz; }
    vec4 f=before?(av+4.0*bv+cv)/6.0:(bv+4.0*cv+dv)/6.0;
    vec4 du=before?(cv-av)*0.5:(dv-bv)*0.5;
    vec4 ddu=before?av-2.0*bv+cv:bv-2.0*cv+dv;
    float dx=before?(c.p.x-a.p.x)*0.5:(d.p.x-b.p.x)*0.5;
    float ddx=before?a.p.x-2.0*b.p.x+c.p.x:b.p.x-2.0*c.p.x+d.p.x;
    vec4 first=du/dx,second=(ddu*dx-du*ddx)/(dx*dx*dx);
    float origin=before?b.p.x:c.p.x,delta=x-origin,sign_=before?-1.0:1.0;
    // Fixed world-unit frequency; phase is inherited from the actual endpoint jets, never from the view.
    float frequency=1.0;
    vec4 result=f;
    result.xy+=first.xy*sin(frequency*delta)/frequency+second.xy*(1.0-cos(frequency*delta))/(frequency*frequency);
    // Positive widths: continue log(width). Twist and width settle smoothly over one control spacing.
    float reach=max(abs(c.p.x-b.p.x),1e-5),s=abs(delta),scaled=min(s/reach,80.0),decay=exp(-scaled);
    vec2 g1=first.zw*sign_,g2=second.zw;
    g2.x=g2.x/f.z-pow(g1.x/f.z,2.0);g1.x/=f.z;
    vec2 correction=(g1*reach*scaled+(0.5*g2*reach*reach+g1*reach)*scaled*scaled)*decay;
    result.z=f.z*exp(correction.x);result.w=f.w+correction.y;
    return result;
}

// World colour grade (a preset look): up to GRADE_STOPS colour nodes at ascending positions across a world-x range,
// and the share they take of the ribbon's own colour. Share 0 leaves every ribbon its own colours. Between two nodes
// the colour eases (smoothstep), so a node is a soft waypoint, never a visible seam.
const int GRADE_STOPS=6;
  // rgb, position along the range (0..1, strictly ascending)
                    // world x of position 0, world x of position 1, share, node count
vec3 graded(vec3 colour, float worldX) {
    if(uGrade.z<=0.0) return colour;
    float t=clamp((worldX-uGrade.x)/max(uGrade.y-uGrade.x,1e-3),0.0,1.0);
    int count=clamp(int(uGrade.w),1,GRADE_STOPS);
    vec3 grade=uGradeStops[0].rgb;
    for(int i=1;i<count;++i)
        grade=mix(grade,uGradeStops[i].rgb,smoothstep(uGradeStops[i-1].w,uGradeStops[i].w,t));
    return mix(colour,grade,clamp(uGrade.z,0.0,1.0));
}

void packetField(float x,int owner,out vec4 shape,out vec4 light) {
    float local=(uFieldSide<0.0?-x:x)-uFieldOrigin.x;
        shape=vec4(0);light=vec4(0);
        if(owner<int(uFieldOrigin.w) && min(paths[owner].colourA.a,paths[owner].colourB.a)>0.0) {
            int last=int(paths[owner].meta.x)-1;
            if(last>0) {
                float tail=continuationAnchor(owner,true),head=continuationAnchor(owner,false);
                shape=local<tail || local>head?continuationField(owner,local):clothField(owner,local);
                shape.xy+=uFieldOrigin.yz;
                shape.w+=paths[owner].extra.x;
                int lo=0,hi=last;
                while(hi-lo>1) {int mid=(lo+hi)/2;if(continuationControl(owner,mid).p.x<=local)lo=mid;else hi=mid;}
                Knot a=continuationControl(owner,lo),b=continuationControl(owner,hi);
                float t=clamp((local-a.p.x)/max(b.p.x-a.p.x,1e-6),0.0,1.0);
                vec3 header=0.5*(paths[owner].colourA.rgb+paths[owner].colourB.rgb);
                vec3 ca=mix(header,a.tint.rgb,clamp(a.tint.a,0.0,1.0));
                vec3 cb=mix(header,b.tint.rgb,clamp(b.tint.a,0.0,1.0));
                vec3 colour=mix(ca,cb,t);
                light=vec4(graded(colour,x)*mix(a.side.w,b.side.w,t),1.0);
            }
        }
}

layout(binding = 14) uniform sampler2D uBodyField;
 // texture edge x, inverse covered world length
 // floor+gap, floor softness, cross camber, clearance
float fieldFloor(float y) {
    float x=(y-uBodyShape.x)/uBodyShape.y;
    return uBodyShape.x+uBodyShape.y*(max(x,0.0)+log(1.0+exp(-abs(x))));
}
vec2 fieldSection(vec4 shape,float across) {
    vec2 side=vec2(cos(shape.w),sin(shape.w));
    vec2 bow=vec2(-side.y,side.x);
    vec2 point=shape.xy+shape.z*(across*side+(1.0-across*across)*uBodyShape.z*bow);
    point.x=fieldFloor(point.x);
    return point;
}
void sourceField(float x,int owner,out vec4 shape,out vec4 light);
vec3 groundLight(vec3 world) {
    vec3 light=vec3(0);
    for(int owner=0;owner<4;owner++) {
        vec4 shape,source;sourceField(world.x,owner,shape,source);
        float height=max(fieldFloor(shape.x)-shape.z*abs(cos(shape.w)),0.0);
        light+=source.rgb*source.a*exp(-height)*exp(-abs(world.z-shape.y)/1.5);
    }
    return light;
}
void sourceField(float x,int owner,out vec4 shape,out vec4 light) {
    float u=(x-uBodySpan.x)*uBodySpan.y;
    if(u>=0.0 && u<=1.0) {
        shape=textureLod(uBodyField,vec2(u,(float(owner*2)+0.5)/8.0),0.0);   // one level: no derivative
        light=textureLod(uBodyField,vec2(u,(float(owner*2)+1.5)/8.0),0.0);return;
    }
    packetField(x,owner,shape,light);
}
vec4 bodyField(vec3 world) {
    float distance_=1e4;vec3 illumination=vec3(0);
    for(int owner=0;owner<4;owner++) {
        vec4 shape,light;sourceField(world.x,owner,shape,light);
        if(light.a<=0.0)continue;
        // The floor map is 1-Lipschitz: this disk encloses every cambered cross-section point.
        float lowerBound=max(length(world.yz-vec2(fieldFloor(shape.x),shape.y))
            -shape.z*(1.0+abs(uBodyShape.z)),0.0);
        // At 20 units even four maximum-64 HDR sources contribute <0.00016 radiance before fog weighting.
        if(lowerBound>20.0)continue;
        float d=1e4;vec2 a=fieldSection(shape,-1.0);
        for(int i=1;i<=8;i++) {
            vec2 b=fieldSection(shape,-1.0+float(i)*0.25),v=b-a;
            vec2 nearest=a+v*clamp(dot(world.yz-a,v)/max(dot(v,v),1e-8),0.0,1.0);
            d=min(d,length(world.yz-nearest));a=b;
        }
        distance_=min(distance_,d);
        illumination+=light.rgb*exp(-d/1.4);
    }
    return vec4(illumination,distance_);
}

        // clear-air centre x, centre z, radius x, radius z (world units)
   // falloff (radii beyond the edge per e-fold), floor thickening, thickening height, low glow
layout(binding = 8) uniform sampler3D uFogVolume; // integrated in-scatter (rgb) and transmittance (a), exponential view-depth slices
     // world -> the volume camera's view
     // Perspective tangents, unused, asinh scale (0: positive logarithmic depth)
    // near, far, slices, 1 + optional focus depth (0: disabled)

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

#ifndef SRPSS_CONVENTIONS_MAPPING
#define SRPSS_CONVENTIONS_MAPPING
layout(std140, binding = 17) uniform SrpssConventions {
    vec4 srpssConventions;   // the target's: x 1 flips the fragment row; y 1 negates the clip NDC's Y; z, w reserved
};
#ifdef SRPSS_NATIVE_CORE
vec2 ndcToUv(vec2 ndc) { return vec2(ndc.x, srpssConventions.y > 0.5 ? -ndc.y : ndc.y) * 0.5 + 0.5; }
vec2 uvToNdc(vec2 uv) {
    vec2 ndc = uv * 2.0 - 1.0;
    return vec2(ndc.x, srpssConventions.y > 0.5 ? -ndc.y : ndc.y);
}
#else
// This renderer: y is 0 for every target and never changes, so these are the authored arithmetic, bit for bit.
vec2 ndcToUv(vec2 ndc) { return ndc * 0.5 + 0.5; }
vec2 uvToNdc(vec2 uv) { return uv * 2.0 - 1.0; }
#endif
float viewDepthFromDepthTexture(float depth) { return depth; }
// IEC 61966-2-1, exactly, for an sRGB asset uploaded as plain RGBA8 (decided F4: no backend's sRGB flag is relied on;
// the GPU filters the encoded values before this decode).
vec3 srgbToLinear(vec3 encoded) {
    return mix(pow((encoded + 0.055) / 1.055, vec3(2.4)), encoded / 12.92, lessThanEqual(encoded, vec3(0.04045)));
}
#endif
#if defined(SRPSS_CONVENTIONS_FRAGMENT) && !defined(SRPSS_CONVENTIONS_FRAGMENT_DECLARED)
#define SRPSS_CONVENTIONS_FRAGMENT_DECLARED
vec2 fragPixel(vec2 targetSize) {
    return vec2(gl_FragCoord.x, srpssConventions.x > 0.5 ? targetSize.y - gl_FragCoord.y : gl_FragCoord.y);
}
ivec2 fragTexel(ivec2 targetSize) { return ivec2(fragPixel(vec2(targetSize))); }
vec2 fragUv(vec2 targetSize) { return fragPixel(targetSize) / targetSize; }
#endif

// Volume coordinates of a world point: xy over the view, z the continuous slice (0 at near, slices at far).
vec3 fogCoordinate(vec3 world) {
    vec3 v=(uFogView*vec4(world,1.0)).xyz;
    float depth=uFogLens.w>0.0?-v.z:max(-v.z,1e-4);
    vec2 ndc=v.xy/(uFogLens.xy*depth);
    float slice=fogDepthFraction(depth);
    return vec3(ndcToUv(ndc),slice*uFogRange.z);
}
vec4 fogVolumeAt(vec3 world) {
    vec3 c=fogCoordinate(world);
    // Texel k holds the integral to the far boundary of slice k; before the first boundary blend from clear air.
    // Level 0 named (the volume has one): no implicit derivative, so a pass may read it after a discard (R-210).
    vec4 s=textureLod(uFogVolume,clamp(vec3(c.xy,(c.z-0.5)/uFogRange.z),vec3(0.0),vec3(1.0)),0.0);
    return mix(vec4(0.0,0.0,0.0,1.0),s,clamp(c.z,0.0,1.0));
}
float mistTransmittance(vec3 world) {
    if(uFogRange.w>0.5) return fogVolumeAt(world).a;
    if(uMistShape.x<=0.0) return 1.0;
    vec2 radii=max(uMist.zw,vec2(1e-3));
    float beyond=max(0.0,length((world.xz-uMist.xy)/radii)-1.0)/uMistShape.x;
    float low=uMistShape.z>0.0?exp(-max(world.y,0.0)/uMistShape.z):0.0;
    return exp(-beyond*beyond*(1.0+uMistShape.y*low));
}
// The mist's own colour: the backdrop, lit where the haze is low and near the edge of the clear air, fading into
// darkness deeper in. (Glow by height alone lit the whole far floor.)
vec3 mistColour(vec3 backdrop, vec3 world) {
    vec2 radii=max(uMist.zw,vec2(1e-3));
    float beyond=max(0.0,length((world.xz-uMist.xy)/radii)-1.0)/max(uMistShape.x,1e-3);
    float low=uMistShape.z>0.0?exp(-max(world.y,0.0)/uMistShape.z):0.0;
    // Deeper mist also darkens (the far floor: dark toward the horizon, lit low).
    return backdrop*(0.35+0.65*exp(-0.25*beyond))*(1.0+uMistShape.w*low*exp(-0.6*beyond*beyond));
}
// An opaque surface seen through the mist: the volume's in-scatter in front of it, or the analytic mix.
vec3 mistOver(vec3 surface, vec3 backdrop, vec3 world) {
    if(uFogRange.w>0.5) { vec4 fog=fogVolumeAt(world); return surface*fog.a+fog.rgb; }
    return mix(mistColour(backdrop,world),surface,mistTransmittance(world));
}

// Anisotropic filtering in the shader (rendering/gl_programs/anisotropic.py): taps on a lattice along the footprint's
// major axis, each weighted by its overlap with the footprint and filtered at the minor axis's level.
vec4 srpssAnisotropic(sampler2D tex, vec2 uv, vec2 dPdx, vec2 dPdy, float maxAnisotropy)
{
    vec2 size = vec2(textureSize(tex, 0));
    vec2 px = dPdx * size;
    vec2 py = dPdy * size;
    float lx = dot(px, px);
    float ly = dot(py, py);
    bool xMajor = lx >= ly;
    vec2 major = xMajor ? dPdx : dPdy;
    vec2 minor = xMajor ? dPdy : dPdx;
    float pMax = sqrt(max(lx, ly));
    float pMin = sqrt(min(lx, ly));
    float r = clamp(pMax / max(pMin, 1e-8), 1.0, min(maxAnisotropy, 15.0));
    int reach = int(ceil((r - 1.0) * 0.5));
    vec2 stepUv = major / r;
    vec4 sum = vec4(0.0);
    for (int j = -7; j <= 7; ++j) {
        if (j < -reach || j > reach)
            continue;
        float t = float(j);
        float w = max(0.0, min(t + 0.5, 0.5 * r) - max(t - 0.5, -0.5 * r));
        sum += w * textureGrad(tex, uv + stepUv * t, stepUv, minor);
    }
    return sum / r;
}

layout(binding = 2) uniform sampler2D uReflection;
   // streak half-length (uv), min/max optical mip, Gaussian sigma (receiver pixels)
 // plane height (world), spread (uv per world unit of height; 0 off), along/across, probe mip

const float HEIGHT_SLOPE_RMS=5.0;
// The maps' and the reflection's anisotropy (N5.4: the shader's taps, rendering/gl_programs/anisotropic.py, in both
// renderers; the samplers at 1x, as the native core's are): the maps' former hardware 8x, the reflection's 16x.
const float MAP_ANISOTROPY=8.0;
const float REFLECTION_ANISOTROPY=16.0;
// A map read at a mip bias, given the coordinate's screen gradients (taken by the caller before any lane can leave):
// the bias scales the footprint by 2^bias, the hardware's bias on its own level.
vec4 mapRead(sampler2D map, vec2 uv, vec2 dUvdx, vec2 dUvdy, float bias) {
    float scale=exp2(bias);
    return srpssAnisotropic(map,uv,dUvdx*scale,dUvdy*scale,MAP_ANISOTROPY);
}
// World-space slope of one height sample set at two incommensurate orientations (no visible tile lattice); dXz the
// screen gradients of xz.
vec2 slopeAt(vec2 xz, mat2 dXz, float tile, float bias) {
    mat2 turn=mat2(0.6,-0.8,0.8,0.6);
    vec2 uv=xz/tile;
    vec2 dx=dXz[0]/tile, dy=dXz[1]/tile;
    vec2 near=mapRead(uSlope,uv,dx,dy,bias).rg;
    vec2 far=transpose(turn)*mapRead(uSlope,turn*uv*1.37+vec2(.31,.47),turn*dx*1.37,turn*dy*1.37,bias).rg*1.37;
    return (0.6*near+0.4*far)/tile;
}
// A wet floor's column: the reflected image drawn out along the view, as smooth coloured mass. A plain average over
// a long column is the mean of every crossing sheet above it (a uniform grey veil); a column belongs to the light it
// reflects. Taps are weighted by their luminance (power COLUMN_POWER), so the column carries the strength of the
// light along it and dim reflected light stays dim. The power is gentle on purpose: a steep power is winner-take-all,
// and as sheets move the winning tap jumps, so the column's colour and level pop between frames (flicker). Its hue
// comes from the coloured light along it (chroma-weighted), so a grey haze or a white crossing never washes a column
// out to pastel. Light high above the floor spreads its column over far more floor (glossy spread grows with height),
// so each tap's light falls with its own reflected height (the emitters' luminance-weighted height in alpha). Tap
// footprints overlap (COLUMN_OVERLAP spacings tall): a sheet thinner than a reflection texel never falls between taps
// or through a footprint edge, so the column changes only as smoothly as the sheets above it, a soft smeared mass
// rather than a crisp streak.
const int COLUMN_TAPS=8;
const float COLUMN_POWER=2.0;
const float COLUMN_OVERLAP=2.0;
vec3 columnReflection(vec2 screenUv, vec2 dScreenUvdx, vec2 dScreenUvdy, vec2 offset, float halfLength, float across) {
    vec2 size=vec2(textureSize(uReflection,0));
    float pixelSpan=max(length(dScreenUvdx*size),length(dScreenUvdy*size));
    float span=max(across,pixelSpan);
    float spacing=2.0*halfLength/float(COLUMN_TAPS);
    vec2 dx=vec2(span/size.x,0.0), dy=vec2(0.0,max(span/size.y,COLUMN_OVERLAP*spacing));
    vec2 uv=screenUv+offset;
    vec3 colour=vec3(0.0);
    float tint=0.0, weight=0.0, moment=0.0, total=0.0;
    for(int i=0;i<COLUMN_TAPS;i++) {
        float t=(float(i)+0.5)*2.0/float(COLUMN_TAPS)-1.0;
        vec4 sample_=srpssAnisotropic(uReflection,clamp(uv+vec2(0.0,t*halfLength),vec2(0),vec2(1)),dx,dy,
                                      REFLECTION_ANISOTROPY);
        float raw=max(dot(sample_.rgb,vec3(0.2126,0.7152,0.0722)),0.0);
        float height=raw>1e-6?max(sample_.a/raw,0.0):0.0;
        float spread=uMaterialShape.z/(uMaterialShape.z+height);
        spread*=spread;  // the glossy lobe spreads in both image axes
        vec3 tap=sample_.rgb*spread;
        float luminance=raw*spread;
        // Light decays with its distance along the column, so a column fades away from its source, not a bar.
        float along=exp(-2.0*t*t);
        float decayed=along*luminance;
        float hot=pow(decayed,COLUMN_POWER);
        // Chroma share of this tap (0 grey .. 1 pure hue): coloured light names the column's hue.
        float peak=max(max(tap.r,tap.g),tap.b);
        float chroma=peak>1e-6?(peak-min(min(tap.r,tap.g),tap.b))/peak:0.0;
        float hue=hot*(0.05+chroma*chroma);
        colour+=hue*tap/max(luminance,1e-6); tint+=hue;
        weight+=hot; moment+=hot*decayed; total+=pow(along,COLUMN_POWER+1.0);
    }
    if(weight<=1e-12 || tint<=1e-12) return vec3(0.0);
    colour/=tint;  // unit-luminance hue of the coloured light along the column
    // Strength: the power mean of the decayed light along the column (a uniform field keeps its own level),
    // carried by the column's hue.
    float strength=pow(moment/total,1.0/(COLUMN_POWER+1.0));
    return colour*strength/max(dot(colour,vec3(0.2126,0.7152,0.0722)),1e-6);
}
// The wet film follows the yielding floor: the reflected ray leaves the dented surface about its own normal, and the
// planar reflection is read where the image of what that ray reaches (uFloorGiveLook.x along it) lies on screen. On
// the undented plane this is exactly the pixel itself, so the dent bends the reflected column; it never shifts it.
// Perspective only (the sole projection): the view ray runs from the eye.
vec2 floorGiveReflection(vec3 world, vec3 normal, vec2 screenUv) {
    vec3 view=normalize(world-uEye);
    vec3 target=world+reflect(view,normal)*uFloorGiveLook.x;
    target.y=-target.y;
    vec4 clip=uMvp*vec4(target,1.0);
    if(clip.w<=1e-4) return vec2(0.0);
    return clamp(ndcToUv(clip.xy/clip.w)-screenUv,vec2(-0.25),vec2(0.25));
}
void main() {
    vec2 screenUv=fragUv(uViewport);
    vec3 vWorldPos;float groundDepth;
    bool hit=floorWorldHit(vWorldPos,groundDepth);
    // Every derivative is taken here, before the miss discards: Vulkan's discard ends the lane (SPIR-V OpKill) where
    // OpenGL keeps it as a helper, so a derivative after it is undefined (R-210). The map reads below take them.
    vec2 dScreenUvdx=dFdx(screenUv), dScreenUvdy=dFdy(screenUv);
    mat2 dWorldXz=mat2(dFdx(vWorldPos.xz),dFdy(vWorldPos.xz));
    if(!hit)discard;
    gl_FragDepth=groundDepth;
    if(uFlat==1) { FragColor=vec4(vec3(0.25),1.0); Emission=vec4(0.0); return; }
    vec3 giveNormal=vec3(0.0,1.0,0.0);
    if(uFloorGive.y>0.0) { vec2 g=floorGiveGradient(vWorldPos.xz); giveNormal=normalize(vec3(g.x,1.0,g.y)); }
    mat2 turn=mat2(0.6,-0.8,0.8,0.6);
    // The material is laid out elongated along world z: this camera looks along the ground at a few degrees, which
    // flattens isotropic concrete into hairline scanlines; elongated, its blotches and relief read at the
    // proportions of a wet floor seen from standing height. World-fixed, so it never swims with the view.
    vec2 materialXz=vec2(vWorldPos.x,vWorldPos.z/max(uMaterialShape.x,1.0));
    vec2 materialScale=vec2(1.0,1.0/max(uMaterialShape.x,1.0));
    mat2 dMaterialXz=mat2(dWorldXz[0]*materialScale,dWorldXz[1]*materialScale);
    vec2 uv=materialXz/uFloor.x;
    vec2 dUvdx=dMaterialXz[0]/uFloor.x, dUvdy=dMaterialXz[1]/uFloor.x;
    // Mip-biased: at this grazing angle the colour scan aliases into horizontal bands once lit. The concrete's own
    // variation is restored around its exact mean (the 1x1 level), so legibility never changes the floor's level.
    // The albedo is stored sRGB-encoded in plain RGBA8 and decoded here (N0.3 decision F4).
    vec3 grain=mix(srgbToLinear(mapRead(uAlbedo,uv,dUvdx,dUvdy,uHot.w).rgb),
                   srgbToLinear(mapRead(uAlbedo,turn*uv*1.37+vec2(.31,.47),turn*dUvdx*1.37,turn*dUvdy*1.37,
                                        uHot.w).rgb),.4);
    vec3 mean=srgbToLinear(textureLod(uAlbedo,vec2(0.5),20.0).rgb);
    vec3 albedo=max(mean+(grain-mean)*uMaterial.x,vec3(0.0))*uFloorTone.x;
    float surfaceRoughness=mapRead(uRoughness,uv,dUvdx,dUvdy,uHot.w).r;
    // Offsets and relief follow the viewed ground axes, so a turned camera streaks along its own view.
    vec3 groundForward=normalize(vec3(uForward.x,0.0,uForward.z));
    vec3 groundRight=cross(groundForward,vec3(0,1,0));
    vec2 broadSlope=slopeAt(materialXz,dMaterialXz,uFloor.x,uMaterialShape.y);
    // Unit-RMS rise of the broad relief along the view. Foreshortening turns it into the long horizontal breaks a
    // grazing wet floor shows; the material's shading and the reflection's breakup are both this one surface.
    float rise=dot(vec3(broadSlope.x,0,broadSlope.y),groundForward)*uFloor.x/HEIGHT_SLOPE_RMS;
    vec3 specular;
    if(uSpecMode==2) {
        specular=textureLod(uSpecular,screenUv,0.0).rgb;   // one level: no derivative
    } else {
    vec2 broad=broadSlope*uFloorTone.y;
    vec2 micro=slopeAt(vWorldPos.xz,dWorldXz,uFloor.y,0.0)*uFloorTone.z;
    vec2 axes=vec2(dot(vec3(broad.x,0,broad.y),groundRight),dot(vec3(broad.x,0,broad.y),groundForward));
    vec2 fine=vec2(dot(vec3(micro.x,0,micro.y),groundRight),dot(vec3(micro.x,0,micro.y),groundForward));
    vec2 offset=axes*uRipple.x+fine*vec2(uRipple.y,uRipple.z);
    if(uFloorGive.y>0.0) offset+=floorGiveReflection(vWorldPos,giveNormal,screenUv);
    float roughness=mix(uStreak.y,uStreak.z,clamp(surfaceRoughness+length(broad)*uStreak.w,0.0,1.0));
    // Optical streak length is fixed in world units. A fixed UV length grew with
    // the edge-resize aperture and washed the same physical reflection away.
    vec4 clip=uMvp*vec4(vWorldPos,1.0);
    vec4 direction=uMvp*vec4(groundForward,0.0);
    float projected=abs(0.5*(direction.y*clip.w-clip.y*direction.w)/(clip.w*clip.w));
    float streak=uStreak.x*uReflectionLook.x*projected;
    vec3 reflected=columnReflection(screenUv,dScreenUvdx,dScreenUvdy,offset,streak*roughness,
                                    exp2(mix(uReflectionLook.y,uReflectionLook.z,roughness)));
    vec3 view=normalize(vWorldPos-uEye);
    float cosine=clamp(abs(uFloorGive.y>0.0?dot(view,giveNormal):view.y),0.0,1.0);
    float fresnel=uFloor.w+(1.0-uFloor.w)*pow(1.0-cosine,5.0);
    // A rough wet floor shows its hot light, not a dim copy of everything: reflected light below uHot.x falls
    // away quadratically, so columns stand over dark concrete. The wet film breaks them up gently (uHot.y).
    // Relative to the scene's own reflected light (the reflection's coarsest mip): quiet and loud states both keep
    // columns over dark concrete. A fixed threshold blacked out the quiet floor and washed the loud one.
    float hot=dot(reflected,vec3(0.2126,0.7152,0.0722));
    float scene=dot(textureLod(uReflection,vec2(0.5),20.0).rgb,vec3(0.2126,0.7152,0.0722));
    reflected*=pow(clamp(hot/max(uHot.x*scene,1e-4),0.0,1.0),uHot.z);
    // The reflection carries the sheets' own saturated hue: chroma about its luminance is lifted (uReflectionHue),
    // so the coloured mass reads as teal or orange over the grey concrete rather than a pastel wash.
    float hueLevel=dot(reflected,vec3(0.2126,0.7152,0.0722));
    reflected=max(vec3(hueLevel)+(reflected-vec3(hueLevel))*uReflectionHue,vec3(0.0));
    // Wet-film grain and sparkle sample the albedo's finest level; at this grazing view that grain is sub-pixel
    // and shimmers as the light under it moves, so both are opt-in (uHot.y, uColumn.z; 0 is a smooth column).
    float film=1.0;
    if(uHot.y>0.0 || uColumn.z>0.0)
        film=srgbToLinear(mapRead(uAlbedo,uv*2.3+vec2(.17,.61),dUvdx*2.3,dUvdy*2.3,0.0).rgb).r
             /max(srgbToLinear(mapRead(uAlbedo,uv*2.3+vec2(.17,.61),dUvdx*2.3,dUvdy*2.3,6.0).rgb).r,1e-3);
    if(uHot.y>0.0) reflected*=mix(1.0,smoothstep(0.6,1.25,film),uHot.y);
    // Relief breakup: facets tilted along the view send the column's light toward or away from the eye. Linear in
    // the zero-mean rise, so the column's mass is broken into the relief's long horizontal bands at any filtering
    // distance, never dimmed or brightened overall.
    reflected*=max(1.0-uMaterial.z*rise,0.0);
    // Column shaping: brightest at the contact under the sheets, fading toward the camera to its far level
    // (where, with a sparkle threshold, only the wet film's brighter grains still catch it).
    float toward=max(vWorldPos.z-uPoolZ,0.0);
    float near=exp(-toward/max(uColumn.x,1e-3));
    float sparkle=uColumn.z>0.0?smoothstep(uColumn.z,1.0,film):1.0;
    reflected*=mix(sparkle*uColumn.y,1.0,near);
    specular=reflected*fresnel*uFloor.z;
    // Bounded at its owner: the reflected light compresses smoothly toward a ceiling (saturating, never clipped,
    // hue kept), so strong preset lighting gives coloured mass under the sheets, never a flooded plane. Below the
    // ceiling the response is nearly linear, so restrained reflections keep their look.
    float level=dot(specular,vec3(0.2126,0.7152,0.0722));
    float ceiling=max(uBound.x,1e-4);
    if(level>1e-6) specular*=ceiling*(1.0-exp(-level/ceiling))/level;
    }
    if(uSpecMode==1) { FragColor=vec4(specular,1.0); Emission=vec4(0.0); return; }
    // Local source light uses the same physical cloth field as the atmosphere, never a projected envelope. A grazing
    // view compresses its depth falloff into one bright line across the image, so the receiver reads it with depth
    // spread out from the sheets' plane and its peak lowered by the square root of that spread (a soft pool, not a
    // seam; its light still reaches the ground under the sheets).
    float spread=max(uMaterial.w,1.0);
    vec3 poolPoint=vec3(vWorldPos.x,0.0,uPoolZ+(vWorldPos.z-uPoolZ)/spread);
    vec3 pool=uFogLit==1?groundLight(poolPoint)*uPool/sqrt(spread):vec3(0.0);
    // Relief shading: light arrives from beyond the sheets, so faces falling away from the eye catch it. Zero-mean
    // over the relief: the concrete reads at every reflection strength without changing its level.
    float shade=clamp(1.0-uMaterial.y*rise,0.25,2.0);
    // The dent's slopes by the same rule: its far side, turned toward the eye, is a little darker.
    if(uFloorGive.y>0.0) shade*=clamp(1.0+uFloorGiveLook.y*dot(giveNormal.xz,groundForward.xz),0.25,2.0);
    // The night's light is the sheets': concrete is lit near them and falls off toward the camera to a dark far
    // level, so a wide view shows dark wet ground in front rather than an evenly lit grey plane (beyond the sheets
    // the mist already takes the ground into the dark). Smooth and world-fixed: no seam, no motion.
    float reach=exp(-max(vWorldPos.z-uPoolZ,0.0)/max(uBound.y,1e-3));
    vec3 ambient=uAmbient*mix(uBound.z,1.0,reach);
    vec3 colour=albedo*uFloorTint*(ambient+pool)*shade+specular;
    float clear=mistTransmittance(vWorldPos);
    colour=mistOver(colour,uBackdrop,vWorldPos);
    FragColor=vec4(colour,1.0);
    Emission=vec4(specular*clear,dot(specular*clear,vec3(0.2126,0.7152,0.0722)));
}
