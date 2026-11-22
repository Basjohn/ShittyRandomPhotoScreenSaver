layout(std140, binding = 18) uniform WaveformMedium {
    mat4 uFogInvView;
    vec4 uFogLens;
    vec4 uFogRange;
    vec4 uFieldOrigin;
    float uFieldSide;
    vec4 uGradeStops[6];
    vec4 uGrade;
    vec2 uBodySpan;
    vec4 uBodyShape;
    vec2 uAtmosphereLight;
    vec4 uAtmosphere;
    vec4 uAtmosphereMotion;
    vec3 uAtmosphereAmbient;
};
layout(local_size_x=4,local_size_y=4,local_size_z=4) in;
layout(rgba16f,binding=2) uniform writeonly image3D uFogInject;
layout(r16f,binding=3) uniform writeonly image3D uFogSteady;




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

 // ceiling radiance, source-hue share
vec3 atmosphereLight(vec3 local,vec3 ambient) {
    float strength=max(max(local.r,local.g),max(local.b,0.0));
    if(strength<=1e-6)return vec3(0);
    float ceiling=max(uAtmosphereLight.x,1e-6);
    float lit=ceiling*(1.0-exp(-strength/ceiling));
    vec3 own=ambient/max(max(ambient.r,ambient.g),max(ambient.b,1e-6));
    vec3 hue=mix(own,max(local,vec3(0))/strength,clamp(uAtmosphereLight.y,0.0,1.0));
    return lit*hue/max(dot(hue,vec3(0.2126,0.7152,0.0722)),1e-3);
}

float atmosphereGround(float y) { return smoothstep(-0.05,0.0,y); }

 // ground extinction, height e-fold, clearance transition, local light gain
 // time, drift speed, noise amount, world noise scale

float atmosphereNoise(vec3 p) {
    // Smooth low frequencies only; no jitter, fringe, detail erosion or grain texture.
    return 0.5+0.25*sin(p.x+sin(p.z*0.73))*cos(p.y*0.81+p.z*0.47)
        +0.25*sin(p.z*1.41+p.x*0.39)*cos(p.x*0.57-p.y*0.68);
}
void fogMedium(vec3 world,out vec3 radiance,out float extinction,out float steady) {
    float ground=atmosphereGround(world.y);
    if(ground<=0.0){radiance=vec3(0);extinction=0.0;steady=0.0;return;}
    vec4 body=bodyField(world);
    vec3 moving=world*uAtmosphereMotion.w+uAtmosphereMotion.x*uAtmosphereMotion.y*vec3(0.07,-0.11,0.03);
    float variation=mix(1.0,0.6+0.8*atmosphereNoise(moving),uAtmosphereMotion.z);
    float clearance=smoothstep(uBodyShape.w,uBodyShape.w+uAtmosphere.z,body.a);
    // One continuous medium with a tiny high-altitude density.
    // Distance thickening belongs to this same medium, behind the world waveform rather than the viewport.
    // Without it grazing rays through the same ground-height profile expose textured far ground across the sky.
    float behind=max(-world.z-6.0,0.0);
    float distanceWeight=1.0+min(pow(behind/12.0,2.0),64.0);
    float foreground=mix(1.0,0.15,smoothstep(4.0,35.0,world.z));
    extinction=uAtmosphere.x*(0.0004+exp(-world.y/max(uAtmosphere.y,0.05))*distanceWeight)
        *foreground*variation*clearance*ground;
    steady=extinction;
    radiance=uAtmosphereAmbient*(0.4+0.6*exp(-behind/30.0))+atmosphereLight(body.rgb*uAtmosphere.w,uAtmosphereAmbient);
}

void main() {
    ivec3 size=imageSize(uFogInject);
    ivec3 cell=ivec3(gl_GlobalInvocationID);
    if(any(greaterThanEqual(cell,size))) return;
    vec2 ndc=(vec2(cell.xy)+0.5)/vec2(size.xy)*2.0-1.0;
    float depth=fogSliceDepth(float(cell.z)+0.5);
    vec3 view=vec3(ndc*uFogLens.xy*depth,-depth);
    vec3 radiance; float extinction, steady=0.0;
    fogMedium((uFogInvView*vec4(view,1.0)).xyz,radiance,extinction,steady);
    extinction=max(extinction,0.0);
    imageStore(uFogInject,cell,vec4(radiance,extinction));
    imageStore(uFogSteady,cell,vec4(clamp(steady,0.0,extinction)));
}
