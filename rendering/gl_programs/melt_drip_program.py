"""Screen-space cohesive viscous film for Melt / Drip.

Melt is intentionally not a general fluid simulation.  One continuous moving
meniscus owns the silhouette, with attached rivulets, shallow refraction and
wet material response confined to the front band.  The photographed source is
kept readable away from that band: no ray-marched pseudo-volume, detached
primitive droplets, or large-scale texture shredding is allowed.
"""

MELT_FRAGMENT_SOURCE = r"""#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uOldTex,uNewTex;
uniform vec2 uItemSize,uDirection;
uniform float uProgress,uSeed,uDetail,uDepth,uGloss;

float hash1(float n){
    return fract(sin(n*127.1+mod(uSeed,997.)*1.73)*43758.5453);
}

// The source coating drains in the authored gravity direction.  It begins
// beyond the viewport and leaves before the exact endpoint, avoiding a final
// frame cut while preserving exact source/destination endpoints.
float baseFront(float t){
    float p=smoothstep(.015,.985,t);
    return 1.045-1.205*pow(p,1.34);
}

// One single-valued front owns every finger.  Local protrusions can stretch
// and narrow but cannot detach into islands because there is no second body.
float frontAt(float x,float t,float count){
    float p=smoothstep(.015,.985,t);
    float late=1.-smoothstep(.78,.965,p);
    float detailN=clamp((uDetail-.5)/1.5,0.,1.);
    float front=baseFront(t);

    // Broad non-periodic-looking contour motion keeps the body from reading as
    // a ruler-straight wipe without turning the photograph itself into waves.
    front+=(.0045+.0065*detailN)*late*
           (sin(x*12.3+mod(uSeed,17.)*.37)
            +.42*sin(x*27.1+1.8+mod(uSeed,11.)*.51));

    for(int i=0;i<12;i++){
        float fi=float(i);
        if(fi>=count)continue;
        float center=(fi+.50+.48*(hash1(fi+7.)-.5))/count;
        float width=(.34+.38*hash1(fi+29.))/count;
        float dx=(x-center)/max(width,.0001);
        float lobe=exp(-2.25*dx*dx);
        float core=exp(-5.2*dx*dx);

        float birth=.055+.25*hash1(fi+53.);
        float grow=smoothstep(birth,birth+.22,p);
        float drain=1.-smoothstep(.66+.12*hash1(fi+71.),.955,p);
        float length=(.045+.185*hash1(fi+43.))*grow*drain;

        // A narrow core inside the broader shoulder reads as a viscous finger
        // with a neck rather than a row of identical semicircular scallops.
        front+=length*(.58*lobe+.42*core);
    }
    return front;
}

void main(){
    vec2 screen=vec2(vUv.x,1.-vUv.y);
    if(uProgress<=0.){FragColor=texture(uOldTex,screen);return;}
    if(uProgress>=1.){FragColor=texture(uNewTex,screen);return;}

    vec2 gravity=normalize(uDirection);
    vec2 tangent=vec2(gravity.y,-gravity.x);
    vec2 delta=screen-.5;
    float cross=dot(delta,tangent)+.5;
    float flow=dot(delta,gravity)+.5;

    float crossPixels=max(1.,abs(tangent.x)*uItemSize.x+abs(tangent.y)*uItemSize.y);
    float flowPixels=max(1.,abs(gravity.x)*uItemSize.x+abs(gravity.y)*uItemSize.y);
    float detailN=clamp((uDetail-.5)/1.5,0.,1.);
    float count=clamp(round((7.+4.*detailN)*sqrt(crossPixels/1440.)),6.,12.);

    float front=frontAt(cross,uProgress,count);
    float signedDepth=front-flow; // positive inside the remaining source film
    float aa=max(1.35/flowPixels,.00075);
    float sourceMask=smoothstep(-aa,aa,signedDepth);
    if(sourceMask<=.00001){FragColor=texture(uNewTex,screen);return;}

    float wet=smoothstep(.025,.16,uProgress)*(1.-smoothstep(.90,.985,uProgress));
    float eps=max(1.75/crossPixels,.0012);
    float slope=(frontAt(clamp(cross+eps,0.,1.),uProgress,count)
                -frontAt(clamp(cross-eps,0.,1.),uProgress,count))/(2.*eps);
    vec2 localNormal=normalize(vec2(-slope,1.));
    vec2 screenNormal=tangent*localNormal.x+gravity*localNormal.y;

    // Optical deformation is intentionally shallow and front-local.  This is
    // the key anti-shred contract: readable source pixels away from the wet
    // edge are sampled at their original coordinates.
    float bandWidth=.038+.052*uDepth;
    float meniscus=sourceMask*(1.-smoothstep(0.,bandWidth,max(signedDepth,0.)));
    float narrowBand=sourceMask*(1.-smoothstep(0.,.014+.018*uDepth,max(signedDepth,0.)));
    float activeMeniscus=meniscus*wet;
    float activeNarrow=narrowBand*wet;
    float ripple=sin(cross*33.7+flow*9.1+mod(uSeed,13.)*.43-uProgress*2.7)
                 *(.00035+.00105*uDepth)*activeMeniscus;
    vec2 refractOffset=screenNormal*((.0008+.0033*uDepth)*activeMeniscus)
                       +tangent*ripple;
    float pull=(.0012+.0050*uDepth)*activeMeniscus*(.35+.65*uProgress);
    vec2 materialUv=clamp(screen+refractOffset-gravity*pull,0.,1.);

    vec3 source0=texture(uOldTex,materialUv).rgb;
    // A tiny gravity-aligned streak softens the meniscus like viscous material
    // without producing the broad rectangular smears of the rejected volume.
    float streak=(.0010+.0038*uDepth)*activeMeniscus;
    vec3 source1=texture(uOldTex,clamp(materialUv-gravity*streak,0.,1.)).rgb;
    vec3 sourceColor=mix(source0,source1,.34*activeMeniscus);
    vec3 destination=texture(uNewTex,screen).rgb;

    // Build a shallow screen-space surface normal from the front slope and a
    // restrained micro-ripple.  Depth fattens/darkens the lip; Gloss controls
    // only the wet highlight response rather than changing the silhouette.
    vec3 n=normalize(vec3(screenNormal*.52,
                          1.0+(.08+.12*uDepth)*sin(cross*21.1+mod(uSeed,7.))));
    vec3 light=normalize(vec3(-.42,-.55,1.0));
    vec3 halfV=normalize(light+vec3(0.,0.,1.));
    float ndl=max(dot(n,light),0.);
    float spec=pow(max(dot(n,halfV),0.),18.+76.*uGloss);
    float rim=pow(1.-clamp(n.z,0.,1.),2.6);

    vec3 liquidColor=sourceColor*(1.-activeMeniscus*(.035+.085*uDepth));
    liquidColor*=1.-activeMeniscus*(.06-.08*ndl);
    float transmission=activeNarrow*(.025+.065*uDepth);
    liquidColor=mix(liquidColor,destination,transmission);
    liquidColor+=vec3(.96,.985,1.)*
                 (spec*(.055+.34*uGloss)*activeMeniscus
                  +rim*(.025+.055*uGloss)*activeNarrow);

    FragColor=vec4(mix(destination,liquidColor,sourceMask),1.);
}
"""
