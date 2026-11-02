"""Bounded Waveform packet reduction. CPU counterpart remains a diagnostic oracle, never a live readback path."""
from core.ribbon_geometry import MAX_PATH_SAMPLES
from rendering.gl_programs.ribbon import RIBBON_GRADE_GLSL
from rendering.gl_programs.ribbon_continuation import CONTINUATION_GLSL

RAW = ("""#version 460 core
layout(local_size_x=64) in;
struct Knot { vec4 p;vec4 q;vec4 tangent;vec4 side;vec4 tint; };
struct Path { vec4 meta;vec4 extra;vec4 colourA;vec4 colourB;Knot knots[MAX_KNOTS]; };
layout(std430,binding=0) readonly buffer Paths { Path paths[]; };
layout(rgba32f,binding=0) writeonly uniform image2D uOutput;
uniform vec4 uSpan; // first x, last x, count, ribbon count
uniform vec4 uOrigin; // packet world origin + scroll, unused
uniform vec4 uAge; // local now, fade in, maximum age, fade out
uniform vec4 uShape; // band width share, camber, world floor + gap, floor softness
uniform vec2 uSlope;
uniform float uContinue;
"""+RIBBON_GRADE_GLSL+CONTINUATION_GLSL+"""
int owner,first,last,capacity,start;
Knot knot(int i) { return paths[owner].knots[(start+clamp(i,first,last))%capacity]; }
float faded(Knot k) {
    float age=uAge.x-k.q.x;
    return (uAge.y>0.0?smoothstep(0.0,uAge.y,age):1.0)
        *(uAge.w>0.0?smoothstep(0.0,uAge.w,uAge.z-age):1.0);
}
vec4 dense(int i) {
    int base=first+i/4;float u=float(i%4)*0.25,v=1.0-u;
    vec4 w=vec4(v*v*v,3.0*u*u*u-6.0*u*u+4.0,-3.0*u*u*u+3.0*u*u+3.0*u+1.0,u*u*u)/6.0;
    vec4 p=knot(base).p*w.x+knot(base+1).p*w.y+knot(base+2).p*w.z+knot(base+3).p*w.w;
    p.xyz+=uOrigin.xyz;
    float y=(p.y-uShape.z)/uShape.w;
    p.y=uShape.z+uShape.w*(max(y,0.0)+log(1.0+exp(-abs(y))));
    p.w=p.w*sqrt(1.0+uShape.y*uShape.y)+0.08;
    return p;
}
vec3 tone(float x) {
    float t=clamp((x-uGrade.x)/(uGrade.y-uGrade.x),0.0,1.0);
    vec3 c=uGradeStops[0].rgb;
    for(int i=1;i<int(uGrade.w);i++)
        c=mix(c,uGradeStops[i].rgb,smoothstep(uGradeStops[i-1].w,uGradeStops[i].w,t));
    return c;
}
void main() {
    int col=int(gl_GlobalInvocationID.x),n=int(uSpan.z);
    if(col>=n)return;
    float x=mix(uSpan.x,uSpan.y,float(col)/float(n-1));
    float tops[3],bottoms[3];vec3 colours[3];int count=0;
    float upper=-1e30,lower=1e30,presence=0.0;
    for(owner=0;owner<3;owner++) {
        imageStore(uOutput,ivec2(col,3+owner),vec4(0));
        if(owner>=int(uSpan.w) || min(paths[owner].colourA.a,paths[owner].colourB.a)<=0.0)continue;
        capacity=int(paths[owner].extra.z);start=int(paths[owner].extra.y);
        first=0;last=int(paths[owner].meta.x)-1;
        if(last<1)continue;
        // Mode history is one contiguous monotone run; new source identity seeds a fresh idle run before reveal.
        while(first<last && knot(first).q.z<0.5)first++;
        while(last>first && knot(last).q.z<0.5)last--;
        if(last-first<1)continue;
        float local=x-uOrigin.x;
        int lo=first,hi=last;
        while(hi-lo>1) { int mid=(lo+hi)/2;if(knot(mid).p.x<=local)lo=mid;else hi=mid; }
        Knot a=knot(lo),b=knot(hi);
        float t=clamp((local-a.p.x)/max(b.p.x-a.p.x,1e-8),0.0,1.0);
        float fade=mix(faded(a),faded(b),t);
        bool outside=local<knot(first).p.x || local>knot(last).p.x;
        vec4 continuation=vec4(0);
        if(outside && uContinue>0.5) {
            continuation=continuationField(owner,local);
            a=local<knot(first).p.x?knot(first):knot(last);b=a;t=0.0;fade=1.0;
            a.p=vec4(local,continuation.xyz);a.q.y=continuation.w;b=a;
        }
        bool here=!outside || uContinue>0.5;
        float live=here?fade:0.0;
        vec3 p=mix(a.p.xyz,b.p.xyz,t)+uOrigin.xyz;
        vec4 actual=vec4(0);
        if(uContinue>0.5) {
            actual=outside?continuation:clothField(owner,local);
            p=vec3(local,actual.xy)+uOrigin.xyz;
        }
        float centre=p.y-uSlope.y*p.z;
        float half_=uShape.x*mix(a.p.w,b.p.w,t)*live;
        if(uContinue>0.5)half_=uShape.x*actual.z;
        float light=mix(a.side.w*faded(a),b.side.w*faded(b),t);
        vec3 header=0.5*(paths[owner].colourA.rgb+paths[owner].colourB.rgb);
        vec3 ca=mix(header,a.tint.rgb,clamp(a.tint.a,0.0,1.0));
        vec3 cb=mix(header,b.tint.rgb,clamp(b.tint.a,0.0,1.0));
        if(here) {
            tops[count]=centre+half_;bottoms[count]=centre-half_;
            colours[count]=mix(ca,cb,t)*light;
            upper=max(upper,tops[count]);lower=min(lower,bottoms[count]);count++;
            presence=max(presence,live);
        }
        if(uContinue>0.5) {
            vec3 c=p;
            float y=(c.y-uShape.z)/uShape.w;
            c.y=uShape.z+uShape.w*(max(y,0.0)+log(1.0+exp(-abs(y))));
            imageStore(uOutput,ivec2(col,3+owner),vec4(c.yz,actual.z*sqrt(1.0+uShape.y*uShape.y)+0.08,live));
        } else if(last-first>=3) {
            int total=4*(last-first-2),l=0,r=total-1;
            while(r-l>1) { int mid=(l+r)/2;if(dense(mid).x<=x)l=mid;else r=mid; }
            vec4 da=dense(l),db=dense(r);
            float dt=clamp((x-da.x)/max(db.x-da.x,1e-8),0.0,1.0);
            vec4 d=mix(da,db,dt);
            imageStore(uOutput,ivec2(col,3+owner),vec4(d.y,d.z,d.w,live));
        }
    }
    vec3 up=vec3(0),down=vec3(0);float uw=1e-6,dw=1e-6;
    for(int i=0;i<count;i++) {
        float a=exp(-pow((upper-tops[i])/0.5,2.0)),b=exp(-pow((bottoms[i]-lower)/0.5,2.0));
        up+=a*colours[i];down+=b*colours[i];uw+=a;dw+=b;
    }
    up/=uw;down/=dw;
    vec3 gradient=tone(x),luma=vec3(0.2126,0.7152,0.0722);
    up=mix(up,gradient*dot(up,luma)/max(dot(gradient,luma),1e-6),uGrade.z);
    down=mix(down,gradient*dot(down,luma)/max(dot(gradient,luma),1e-6),uGrade.z);
    if(count==0)upper=lower=2.0;
    imageStore(uOutput,ivec2(col,0),vec4(2.0+(lower-2.0)*presence,2.0+(upper-2.0)*presence,presence,0));
    imageStore(uOutput,ivec2(col,1),vec4(up,0));imageStore(uOutput,ivec2(col,2),vec4(down,0));
}
""").replace('MAX_KNOTS',str(MAX_PATH_SAMPLES))

BLUR = """#version 460 core
layout(local_size_x=64) in;
layout(rgba32f,binding=0) writeonly uniform image2D uOutput;
uniform sampler2D uInput;
uniform vec2 uSigma; // bounds sigma in texels, colour sigma in texels
vec4 blur(int x,int row,float sigma) {
    if(sigma<=0.0)return texelFetch(uInput,ivec2(x,row),0);
    int n=textureSize(uInput,0).x,r=int(3.0*sigma)+1;vec4 c=vec4(0);float sum=0.0;
    for(int k=-r;k<=r;k++) { float w=exp(-0.5*pow(float(k)/sigma,2.0));
        c+=w*texelFetch(uInput,ivec2(clamp(x+k,0,n-1),row),0);sum+=w; }
    return c/sum;
}
void main() {
    int x=int(gl_GlobalInvocationID.x),n=textureSize(uInput,0).x;if(x>=n)return;
    vec4 bounds=texelFetch(uInput,ivec2(x,0),0);bounds.xy=blur(x,0,uSigma.x).xy;
    imageStore(uOutput,ivec2(x,0),bounds);
    for(int row=1;row<6;row++)imageStore(uOutput,ivec2(x,row),row<3?blur(x,row,uSigma.y):texelFetch(uInput,ivec2(x,row),0));
}
"""

EVEN = """#version 460 core
layout(local_size_x=64) in;
layout(rgba32f,binding=0) writeonly uniform image2D uOutput;
uniform sampler2D uInput;
uniform vec4 uWorld; // first x,last x,sigma in texels,side start
uniform float uSideEnd;
void main() {
    int x=int(gl_GlobalInvocationID.x),n=textureSize(uInput,0).x;if(x>=n)return;
    float world=mix(uWorld.x,uWorld.y,float(x)/float(n-1));
    float side=1.0-smoothstep(uWorld.w,uSideEnd,abs(world));
    vec4 bounds=texelFetch(uInput,ivec2(x,0),0);bounds.xy=vec2(2)+(bounds.xy-vec2(2))*side;bounds.z*=side;
    imageStore(uOutput,ivec2(x,0),bounds);
    for(int row=1;row<6;row++) {
        vec4 c=texelFetch(uInput,ivec2(x,row),0);
        if(row<3) {
            float even=0.0,sum=0.0,sigma=uWorld.z;int r=int(3.0*sigma)+1;
            if(sigma>0.0)for(int k=-r;k<=r;k++) {
                float w=exp(-0.5*pow(float(k)/sigma,2.0));
                even+=w*dot(texelFetch(uInput,ivec2(clamp(x+k,0,n-1),row),0).rgb,vec3(0.2126,0.7152,0.0722));sum+=w;
            }
            else { even=dot(c.rgb,vec3(0.2126,0.7152,0.0722));sum=1.0; }
            c.rgb*=even/sum/max(dot(c.rgb,vec3(0.2126,0.7152,0.0722)),1e-4);
        }
        imageStore(uOutput,ivec2(x,row),c);
    }
}
"""

LIMIT = """#version 460 core
layout(local_size_x=64) in;
layout(r32f,binding=0) writeonly uniform image2D uOutput;
uniform sampler2D uInput;
uniform mat4 uMvp;
uniform vec4 uWorld; // first x,last x,slope x,slope y
uniform vec2 uDepth;
void main() {
    int column=int(gl_GlobalInvocationID.x);if(column>=256)return;
    int n=textureSize(uInput,0).x;float limit=-1.0;
    for(int x=0;x<n;x++) {
        float wx=mix(uWorld.x,uWorld.y,float(x)/float(n-1)),y=texelFetch(uInput,ivec2(x,0),0).y;
        for(int zi=0;zi<5;zi++) {
            float z=mix(uDepth.x,uDepth.y,float(zi)*0.25);
            vec4 p=uMvp*vec4(wx+uWorld.z*z,y+uWorld.w*z,z,1);
            if(abs(p.w)<1e-8)continue;
            int c=clamp(int((p.x/p.w*0.5+0.5)*256.0),0,255);
            if(c==column)limit=max(limit,p.y/p.w*0.5+0.5);
        }
    }
    imageStore(uOutput,ivec2(column,0),vec4(limit));
}
"""

FILL_LIMIT = """#version 460 core
layout(local_size_x=64) in;
layout(r32f,binding=0) writeonly uniform image2D uOutput;
uniform sampler2D uInput;
void main() {
    int x=int(gl_GlobalInvocationID.x);if(x>=256)return;
    float value=texelFetch(uInput,ivec2(x,0),0).r;
    if(value<=-1.0) {
        int left=x-1,right=x+1;
        while(left>=0 && texelFetch(uInput,ivec2(left,0),0).r<=-1.0)left--;
        while(right<256 && texelFetch(uInput,ivec2(right,0),0).r<=-1.0)right++;
        if(left>=0 && right<256)value=mix(texelFetch(uInput,ivec2(left,0),0).r,
            texelFetch(uInput,ivec2(right,0),0).r,float(x-left)/float(right-left));
        else if(left>=0)value=texelFetch(uInput,ivec2(left,0),0).r;
        else if(right<256)value=texelFetch(uInput,ivec2(right,0),0).r;
    }
    imageStore(uOutput,ivec2(x,0),vec4(value-0.02));
}
"""
