"""Analytic 3D viscous film, rounded ligaments and gravity-driven droplets.

The bounded implicit surface is ray-intersected in the existing render pass.
There is no evolving simulation, screen-space opacity wipe or extra clock.
"""

MELT_FRAGMENT_SOURCE = r"""#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uOldTex,uNewTex;
uniform vec2 uItemSize,uDirection;
uniform float uProgress,uSeed,uDetail,uDepth,uGloss;

float crossSize,flowSize,wet,count;
float hash1(float n){return fract(sin(n*127.1+mod(uSeed,997.)*1.73)*43758.5453);}
float smoothUnion(float a,float b,float k){
    float h=clamp(.5+.5*(b-a)/k,0.,1.);
    return mix(b,a,h)-k*h*(1.-h);
}
float baseAt(float t){return 1.18-1.78*smoothstep(.025,.88,t);}
float edgeAt(float x,float t){
    float soften=smoothstep(.05,.25,t);
    return (baseAt(t)+soften*(.044*sin(x/crossSize*10.+mod(uSeed,17.))+.023*sin(x/crossSize*23.+1.7)))*flowSize;
}
vec2 imageUv(vec2 q){return .5+vec2(uDirection.y,-uDirection.x)*(q.x/crossSize-.5)+uDirection*(q.y/flowSize-.5);}
float capsule(vec3 q,vec3 a,vec3 b,float ra,float rb){
    vec3 ab=b-a;
    float h=clamp(dot(q-a,ab)/max(dot(ab,ab),.000001),0.,1.);
    return length(q-a-ab*h)-mix(ra,rb,h);
}
// Each lane owns one mass and a thinning connection to the continuous film.
// Only neighboring lanes can intersect this camera ray: three candidates,
// independent of quality/density, instead of a loop over all fluid volumes.
float liquid(vec3 q){
    float base=edgeAt(q.x,uProgress);
    float h=(.008+.040*uDepth)*wet+.0001;
    float corrugation=.005*wet*sin(q.x*11.+uProgress*4.)*sin(q.y*7.-uProgress*2.);
    float body=max(q.y-base,abs(q.z+h-corrugation)-h);
    float pitch=crossSize/count;
    float k=min(.022,pitch*.12)*wet+.00001;
    float lane=floor(q.x/crossSize*count);
    for(int offset=-1;offset<=1;offset++){
        float id=lane+float(offset);
        if(id<0.||id>=count)continue;
        // Irregular active lanes prevent an evenly spaced fringe. Broad
        // attached lobes and slender late filaments have different masses.
        if(hash1(id+83.)<.24)continue;
        float center=(id+.5+.26*(hash1(id+9.)-.5))/count*crossSize;
        float r=min(pitch*.29,.045+.047*hash1(id+31.))*(.67+.39*hash1(id+101.))*(.78+.22*uDepth)*wet;
        float birth=.08+.14*hash1(id+61.),release=.40+.27*hash1(id+17.);
        float t=min(uProgress,release),grow=smoothstep(birth,release,t);
        float lengthen=(.12+.32*hash1(id+43.))*flowSize;
        float initial=edgeAt(center,release)+lengthen;
        float age=max(0.,uProgress-release),remaining=1.-release;
        float acceleration=max(.2,(1.35*flowSize+r-initial-.35*remaining)/(remaining*remaining));
        float y=edgeAt(center,t)+lengthen*grow+.35*age+acceleration*age*age;
        float bend=min(.025,pitch*.10)*wet*sin(id*3.7+uProgress*2.8);
        vec3 bulb=vec3(center+bend,y,r*.35);
        vec3 a=vec3(center,edgeAt(center,uProgress)-.02,r*.10);
        float neck=1.-smoothstep(release-.11,release+.035,uProgress);
        float size=smoothstep(birth-.06,birth+.10,uProgress);
        float radius=r*size;
        if(neck>.0001){
            vec3 middle=mix(a,bulb,.55);
            middle.x+=min(.035,pitch*.12)*wet*sin(id*2.3+uProgress*3.);
            float upper=capsule(q,a,middle,radius*1.05*neck,radius*.35*neck);
            float lower=capsule(q,middle,bulb,radius*.35*neck,radius*.50*neck);
            float stem=smoothUnion(upper,lower,k*.40);
            body=smoothUnion(body,stem,k);
        }
        // Rounded lower mass stretches under load, then relaxes after pinch.
        vec3 d=q-bulb;
        float elongation=1.25+.55*neck+.12*sin(age*12.+id);
        d.y/=elongation;
        body=smoothUnion(body,length(d)-radius,k*.65);
    }
    return body;
}
vec3 surfaceNormal(vec3 q){
    const float e=.0007;
    vec2 h=vec2(e,0.);
    return normalize(vec3(liquid(q+h.xyy)-liquid(q-h.xyy),liquid(q+h.yxy)-liquid(q-h.yxy),liquid(q+h.yyx)-liquid(q-h.yyx)));
}
void main(){
    vec2 screen=vec2(vUv.x,1.-vUv.y);
    if(uProgress<=0.){FragColor=texture(uOldTex,screen);return;}
    if(uProgress>=1.){FragColor=texture(uNewTex,screen);return;}
    float aspect=uItemSize.x/uItemSize.y;
    crossSize=abs(uDirection.y)*aspect+abs(uDirection.x);
    flowSize=abs(uDirection.x)*aspect+abs(uDirection.y);
    count=clamp(round((4.+3.*uDetail)*sqrt(crossSize)),5.,18.);
    wet=smoothstep(.015,.20,uProgress);
    vec2 delta=screen-.5;
    vec2 q2=vec2(dot(delta,vec2(uDirection.y,-uDirection.x))*crossSize,dot(delta,uDirection)*flowSize);
    vec3 origin=vec3(crossSize*.5,flowSize*.5,3.);
    vec3 ray=normalize(vec3(q2,-3.));
    // All geometry lies in this shallow optical volume. Starting at its
    // front keeps the ray budget bounded; empty space exits the back plane.
    float distance=(3.-.24)/(-ray.z);
    float farDistance=(3.+.18)/(-ray.z);
    vec3 p=origin+ray*distance;
    bool hit=false;
    for(int step=0;step<52;step++){
        float d=liquid(p);
        if(d<.00065){hit=true;break;}
        distance+=max(.0004,d*.72);
        if(distance>farDistance)break;
        p=origin+ray*distance;
    }
    vec3 destination=texture(uNewTex,screen).rgb;
    if(!hit){FragColor=vec4(destination,1.);return;}
    vec3 n=surfaceNormal(p),view=-ray;
    vec3 light=normalize(vec3(-.45,-.65,1.));
    // Material advection moves the photo with the draining liquid. Near a
    // stretched ligament the backtrace lengthens instead of painting a
    // stationary picture on top of a visibility mask.
    float front=edgeAt(p.x,uProgress);
    float pull=max(0.,p.y-front);
    vec2 material=p.xy;
    material.y-=flowSize*.12*uProgress*uProgress+pull*.78;
    material.y-=.12*flowSize*wet*smoothstep(front-.35*flowSize,front+.03*flowSize,p.y);
    material.x+=.009*wet*sin(p.y*10.+p.x*4.-uProgress*4.);
    vec3 color=texture(uOldTex,clamp(imageUv(material),0.,1.)).rgb;
    float diffuse=.56+.44*max(dot(n,light),0.);
    float specular=pow(max(dot(n,normalize(light+view)),0.),22.+100.*uGloss);
    float fresnel=pow(1.-max(dot(n,view),0.),4.);
    float occlusion=clamp(liquid(p+n*.018)/.018,.40,1.);
    color*=mix(1.,diffuse*(.82+.18*occlusion),wet);
    color+=vec3(.90,.96,1.)*(specular*.68+fresnel*.20)*uGloss*wet;
    FragColor=vec4(color,1.);
}
"""
