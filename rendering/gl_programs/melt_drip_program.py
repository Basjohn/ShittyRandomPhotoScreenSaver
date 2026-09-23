"""Gravity melt for Melt / Drip (operator rework 2026-09-23).

The photograph itself melts. A seeded heat field starts the melt at the chosen
origin -- a top corner, the top centre, the centre outward, or the edges inward
-- and spreads with an irregular (noise-roughened) boundary. Once a region has
melted, gravity takes it: the image content sags downward with accelerating
displacement, narrow viscous drips run ahead of the sheet, and the stretched
film thins until the destination shows through. Regions the melt has not yet
reached are the untouched source at their original coordinates.

Everything is analytic in ``uProgress``: no clock, no CPU simulation, no
detached primitive bodies (drips are part of the one displaced sheet). Exact
source at progress 0 and exact destination from ≈0.94 onward.

Controls: Detail = drip count and melt-boundary irregularity; Depth = film
thickness, lip darkening and refraction; Gloss = wet highlight intensity and
tightness only (never the silhouette).
"""

MELT_FRAGMENT_SOURCE = r"""#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uOldTex,uNewTex;
uniform vec2 uItemSize,uOrigin;
uniform float uProgress,uSeed,uDetail,uDepth,uGloss,uOriginMode;

const float REACH=.60;   // latest melt start (farthest point from the origin)
const float SPAN=.34;    // time for a melted region to sag, thin and fall away

float seedOffset(){return mod(uSeed,997.)*.137;}
float detailN(){return clamp((uDetail-.5)/1.5,0.,1.);}

// Exact integer hash of a lattice point. A chaotic float hash gives the same
// corner different values when two neighbouring cells round it differently,
// which cut the melt field into hard-edged rectangles.
float hash21(vec2 p){
    uvec3 v=uvec3(ivec3(ivec2(floor(p)),int(mod(uSeed,997.))));
    v=v*1664525u+1013904223u;
    v.x+=v.y*v.z;v.y+=v.z*v.x;v.z+=v.x*v.y;
    v^=v>>16u;
    v.x+=v.y*v.z;v.y+=v.z*v.x;v.z+=v.x*v.y;
    return float((v.x^v.y^v.z)&0xffffffu)/16777215.;
}
float vnoise(vec2 p){
    vec2 i=floor(p),f=fract(p),u=f*f*(3.-2.*f);
    return mix(mix(hash21(i),hash21(i+vec2(1.,0.)),u.x),
               mix(hash21(i+vec2(0.,1.)),hash21(i+vec2(1.,1.)),u.x),u.y);
}
float fbm(vec2 p){return .62*vnoise(p)+.38*vnoise(p*2.13+7.1);}

// When does the melt reach this point? 0 at the origin, REACH at the farthest.
float meltStart(vec2 s,float aspect){
    float d;
    if(uOriginMode>.5){
        // Centre-in: every edge melts first, the centre last.
        vec2 e=min(s,1.-s);
        d=clamp(2.*min(e.x,e.y),0.,1.);
    }else{
        vec2 p=vec2(s.x*aspect,s.y),o=vec2(uOrigin.x*aspect,uOrigin.y);
        float far=max(max(length(o),length(o-vec2(aspect,0.))),
                      max(length(o-vec2(0.,1.)),length(o-vec2(aspect,1.))));
        d=length(p-o)/max(far,.0001);
    }
    float n=fbm(vec2(s.x*aspect,s.y)*(2.2+3.2*detailN())+seedOffset());
    return REACH*clamp(d*.80+(n-.5)*(.28+.22*detailN())+.10,0.,1.);
}

float ageAt(vec2 s,float aspect){
    return clamp((uProgress-meltStart(s,aspect))/SPAN,0.,1.);
}

// Viscous drips: columns that fall faster than the sheet around them. Their
// flanks are wide enough that a drip never shears the photograph into a seam.
// Returns the drip weight at x-step, x and x+step.
vec3 dripsAt(float x,float step){
    float count=6.+16.*detailN();
    vec3 total=vec3(0.);
    for(int i=0;i<22;i++){
        float fi=float(i);
        if(fi>=count)break;
        float c=hash21(vec2(fi,3.));
        float w=(.012+.026*hash21(vec2(fi,7.)))*(1.25-.45*detailN());
        vec3 dx=(vec3(x-step,x,x+step)-c)/w;
        total+=exp(-dx*dx)*(.35+.65*hash21(vec2(fi,11.)));
    }
    return min(total,vec3(1.4));
}

// Downward sag of the material shown at a point of age a: accelerating with
// age (weight), longer inside drips.
float sagOf(float a,float drip){return a*a*(1.30+(.40+.40*uDepth)*drip*a);}

// Remaining film: melted material stretches thin and falls away. Drips hold
// their body a little longer than the sheet around them.
float filmOf(float a,float drip){return 1.-smoothstep(.42,.97,a-.10*drip*a);}

// Paint height: the film, swollen in drips and where sliding paint has piled.
float heightOf(float a,float drip){
    float f=filmOf(a,drip);
    return f*(1.+.9*uDepth*drip+(3.+9.*uDepth)*sagOf(a,drip));
}

void main(){
    vec2 screen=vec2(vUv.x,1.-vUv.y);
    if(uProgress<=0.){FragColor=texture(uOldTex,screen);return;}
    if(uProgress>=1.){FragColor=texture(uNewTex,screen);return;}

    float aspect=uItemSize.x/max(uItemSize.y,1.);
    vec3 destination=texture(uNewTex,screen).rgb;
    float a=ageAt(screen,aspect);
    if(a<=0.){FragColor=texture(uOldTex,screen);return;}   // not melted yet: untouched

    float px=1./max(uItemSize.x,1.),py=1./max(uItemSize.y,1.);
    float stepX=3.*px,stepY=3.*py;
    vec3 drips=dripsAt(screen.x,stepX);
    float drip=drips.y;
    float sag=sagOf(a,drip);
    float film=filmOf(a,drip);

    // A gentle sideways meander as the material flows.
    float meander=(vnoise(vec2(screen.y*5.3,screen.x*3.1+seedOffset()))-.5)*.012*a;
    vec2 sourceUv=vec2(screen.x+meander,screen.y-sag);
    // Above the top edge there is no material left to pull down.
    film*=smoothstep(-.002,.02,sourceUv.y);

    // The melting layer casts a soft shadow down-right onto what it reveals.
    vec2 casterAt=screen-vec2(6.*px,9.*py);
    float aC=ageAt(casterAt,aspect);
    float caster=filmOf(aC,drip)*smoothstep(-.002,.02,casterAt.y-sagOf(aC,drip));
    float shadow=clamp(caster-film,0.,1.)*(.18+.32*uDepth);
    vec3 revealed=destination*(1.-shadow);
    if(film<=.0005){FragColor=vec4(revealed,1.);return;}

    // Surface relief from the paint height (three-pixel central differences).
    float aU=ageAt(screen-vec2(0.,stepY),aspect),aD=ageAt(screen+vec2(0.,stepY),aspect);
    float hR=heightOf(ageAt(screen+vec2(stepX,0.),aspect),drips.z);
    float hL=heightOf(ageAt(screen-vec2(stepX,0.),aspect),drips.x);
    float hD=heightOf(aD,drip),hU=heightOf(aU,drip);
    vec2 grad=vec2(hR-hL,hD-hU)/(2.*vec2(stepX*uItemSize.x,stepY*uItemSize.y));
    float relief=(6.+18.*uDepth);
    vec3 n=normalize(vec3(-grad*relief,1.));
    // Where the sliding paint bunches up it folds and darkens.
    float bunch=clamp((sagOf(aU,drip)-sagOf(aD,drip))/(2.*stepY),0.,3.);

    // Refraction through the moving liquid, stronger for a deeper film.
    vec2 bend=n.xy*(.004+.014*uDepth)*smoothstep(0.,.25,a);
    vec3 liquid=texture(uOldTex,clamp(sourceUv+bend,0.,1.)).rgb;
    // Viscous smear along the flow: sample a little higher and blend.
    vec3 smear=texture(uOldTex,clamp(sourceUv+bend-vec2(0.,.010+.030*a*(.5+drip)),0.,1.)).rgb;
    liquid=mix(liquid,smear,.45*smoothstep(0.,.5,a));

    // Lip: the thinning edge of the sheet darkens with depth.
    float lip=smoothstep(.05,.45,film)*(1.-smoothstep(.45,.95,film));
    liquid*=1.-lip*(.10+.30*uDepth);
    liquid*=1.-(.08+.22*uDepth)*smoothstep(.2,2.5,bunch);

    // Wet highlights: Gloss controls intensity and tightness only.
    vec3 light=normalize(vec3(-.35,-.55,.76));
    vec3 halfV=normalize(light+vec3(0.,0.,1.));
    float spec=pow(max(dot(n,halfV),0.),8.+120.*uGloss);
    float wet=smoothstep(0.,.18,a);
    liquid+=vec3(1.)*spec*(.05+.95*uGloss)*wet*(.35+.65*(1.-n.z*n.z*.5));
    float rim=pow(1.-clamp(n.z,0.,1.),2.2);
    liquid+=vec3(.95,.98,1.)*rim*uGloss*.35*wet;
    // Wet sheen: a soft sky reflection over the moving paint, strongest where
    // it tilts. Screen-blended so it glazes the photograph without clipping.
    float tilt=smoothstep(0.,.25,1.-n.z);
    vec3 sheen=vec3(.80,.88,1.)*uGloss*wet*(.10+.30*tilt);
    liquid=1.-(1.-clamp(liquid,0.,1.))*(1.-sheen);

    FragColor=vec4(mix(revealed,clamp(liquid,0.,1.),film),1.);
}
"""
