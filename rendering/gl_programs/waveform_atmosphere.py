"""Continuous night atmosphere and its fixed-world reduction of the published swept cloth."""
from core.ribbon_geometry import MAX_PATH_SAMPLES
from core.waveform_ribbon_authoring import RIBBON_CAPACITY
from rendering.gl_programs.ribbon_continuation import CONTINUATION_GLSL
from rendering.gl_programs.ribbon import RIBBON_GRADE_GLSL
from rendering.gl_programs.mist import MIST_GLSL
from rendering.gl_programs.fog_volume import FOG_FULLSCREEN_VERTEX

FIELD_RIBBONS=RIBBON_CAPACITY
FIELD_ROWS=FIELD_RIBBONS*2
PACKET_GLSL=('''
struct Knot {vec4 p;vec4 q;vec4 tangent;vec4 side;vec4 tint;};
struct Path {vec4 meta;vec4 extra;vec4 colourA;vec4 colourB;Knot knots[MAX_KNOTS];};
layout(std430,binding=0) readonly buffer Paths {Path paths[];};
uniform vec4 uFieldOrigin; // packet origin+scroll, ribbon count
'''+CONTINUATION_GLSL+RIBBON_GRADE_GLSL+'''
void packetField(float x,int owner,out vec4 shape,out vec4 light) {
    float local=x-uFieldOrigin.x;
        shape=vec4(0);light=vec4(0);
        if(owner<int(uFieldOrigin.w) && min(paths[owner].colourA.a,paths[owner].colourB.a)>0.0) {
            int last=int(paths[owner].meta.x)-1;
            if(last>0) {
                Knot first=continuationControl(owner,0),end=continuationControl(owner,last);
                shape=local<first.p.x || local>end.p.x?continuationField(owner,local):clothField(owner,local);
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
''').replace('MAX_KNOTS',str(MAX_PATH_SAMPLES))
FIELD_COMPUTE=('#version 460 core\n'+PACKET_GLSL+'''
layout(local_size_x=64) in;
layout(rgba32f,binding=0) writeonly uniform image2D uOutput;
uniform vec4 uFieldSpan; // first x, last x, samples, ribbon count
void main() {
    int column=int(gl_GlobalInvocationID.x),samples=int(uFieldSpan.z);
    if(column>=samples)return;
    float x=mix(uFieldSpan.x,uFieldSpan.y,float(column)/float(samples-1));
    float local=x-uFieldOrigin.x;
    for(int owner=0;owner<4;owner++) {
        vec4 shape,light;packetField(x,owner,shape,light);
        imageStore(uOutput,ivec2(column,owner*2),shape);
        imageStore(uOutput,ivec2(column,owner*2+1),light);
    }
}
''').replace('MAX_KNOTS',str(MAX_PATH_SAMPLES))

WORLD_FIELD_GLSL=PACKET_GLSL+'''
uniform sampler2D uBodyField;
uniform vec2 uBodySpan; // texture edge x, inverse covered world length
uniform vec4 uBodyShape; // floor+gap, floor softness, cross camber, clearance
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
        shape=texture(uBodyField,vec2(u,(float(owner*2)+0.5)/8.0));
        light=texture(uBodyField,vec2(u,(float(owner*2)+1.5)/8.0));return;
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
'''

# How the ribbons' local light scatters into the medium. Strength compresses toward a ceiling (strong light can never
# wash the frame) and the colour keeps only a capped share of the source hue over the medium's own cool hue, so the
# smoke is tinted near each ribbon but never recoloured. Brightness is set by luminance, independently of the hue.
ATMOSPHERE_LIGHT_GLSL='''
uniform vec2 uAtmosphereLight; // ceiling radiance, source-hue share
vec3 atmosphereLight(vec3 local,vec3 ambient) {
    float strength=max(max(local.r,local.g),max(local.b,0.0));
    if(strength<=1e-6)return vec3(0);
    float ceiling=max(uAtmosphereLight.x,1e-6);
    float lit=ceiling*(1.0-exp(-strength/ceiling));
    vec3 own=ambient/max(max(ambient.r,ambient.g),max(ambient.b,1e-6));
    vec3 hue=mix(own,max(local,vec3(0))/strength,clamp(uAtmosphereLight.y,0.0,1.0));
    return lit*hue/max(dot(hue,vec3(0.2126,0.7152,0.0722)),1e-3);
}
'''

MEDIUM_GLSL=WORLD_FIELD_GLSL+ATMOSPHERE_LIGHT_GLSL+'''
uniform vec4 uAtmosphere; // ground extinction, height e-fold, clearance transition, local light gain
uniform vec4 uAtmosphereMotion; // time, drift speed, noise amount, world noise scale
uniform vec3 uAtmosphereAmbient;
float atmosphereNoise(vec3 p) {
    // Smooth low frequencies only; no jitter, fringe, detail erosion or grain texture.
    return 0.5+0.25*sin(p.x+sin(p.z*0.73))*cos(p.y*0.81+p.z*0.47)
        +0.25*sin(p.z*1.41+p.x*0.39)*cos(p.x*0.57-p.y*0.68);
}
void fogMedium(vec3 world,out vec3 radiance,out float extinction,out float steady) {
    if(world.y<0.0){radiance=vec3(0);extinction=0.0;steady=0.0;return;}
    vec4 body=bodyField(world);
    vec3 moving=world*uAtmosphereMotion.w+uAtmosphereMotion.x*uAtmosphereMotion.y*vec3(0.07,-0.11,0.03);
    float variation=mix(1.0,0.6+0.8*atmosphereNoise(moving),uAtmosphereMotion.z);
    float clearance=smoothstep(uBodyShape.w,uBodyShape.w+uAtmosphere.z,body.a);
    // One continuous medium. Tiny high-altitude density avoids an opaque long signed-Ortho prefix.
    // Distance thickening belongs to this same medium, behind the world waveform rather than the viewport.
    // Without it parallel rays through the same ground-height profile expose textured far ground across the sky.
    float behind=max(-world.z-6.0,0.0);
    float distanceWeight=1.0+min(pow(behind/12.0,2.0),64.0);
    float foreground=mix(1.0,0.15,smoothstep(4.0,35.0,world.z));
    extinction=uAtmosphere.x*(0.0004+exp(-world.y/max(uAtmosphere.y,0.05))*distanceWeight)
        *foreground*variation*clearance;
    steady=extinction;
    radiance=uAtmosphereAmbient*(0.4+0.6*exp(-behind/30.0))+atmosphereLight(body.rgb*uAtmosphere.w,uAtmosphereAmbient);
}
'''

SKY_VERTEX=FOG_FULLSCREEN_VERTEX
SKY_FRAGMENT='#version 460 core\nin vec2 vNdc;\nlayout(location=0) out vec4 FragColor;\nlayout(location=1) out vec4 Emission;\nuniform vec3 uBackdrop;\nuniform int uSkyReflection;\n'+MIST_GLSL+'''
void main(){vec4 fog=texture(uFogVolume,vec3(vNdc*0.5+0.5,1.0));
FragColor=uSkyReflection==1?vec4(fog.rgb,0.0):vec4(uBackdrop*fog.a+fog.rgb,1.0);
Emission=vec4(0.0);}
'''
