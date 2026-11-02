"""Waveform wet-floor and shaped-mist programs; no scene lifetime or simulation."""
from rendering.gl_programs.mist import MIST_GLSL
from rendering.gl_programs.reflection import PLANAR_REFLECTION_GLSL

FLOOR_VERTEX = """#version 460 core
layout(location=0) in vec3 aPosition;
uniform mat4 uMvp;
out vec3 vWorldPos;
void main() { vWorldPos=aPosition; gl_Position=uMvp*vec4(aPosition,1.0); }
"""
ENVELOPE_RIBBONS = 3   # sheets with their own 3D rows in the envelope table (true 3D clearance)
ENVELOPE_ROWS_GLSL = (f"const float ENV_ROWS={3 + ENVELOPE_RIBBONS}.0;\n"
                      f"const int ENV_RIBBONS={ENVELOPE_RIBBONS};\n")

FLOOR_FRAGMENT = """#version 460 core
in vec3 vWorldPos;
uniform sampler2D uAlbedo;
uniform sampler2D uSlope;      // height slope per uv unit (rg), from the smooth wet-surface height map
uniform sampler3D uFogLight;   // the mist's coarse medium: its radiance is the ribbon light field
uniform int uFlat;
uniform int uFogLit;
uniform vec2 uViewport;
uniform vec3 uBackdrop;
uniform vec3 uAmbient;
uniform vec4 uFloor;        // tile, micro tile, reflection gain, f0
uniform vec4 uFloorTone;    // albedo gain, diffuse gain, broad relief amplitude, micro relief amplitude
uniform vec3 uRipple;       // reflection offset per unit slope: broad, micro across, micro along
uniform vec4 uStreak;       // unused, roughness min/max, broad-slope gain to roughness
uniform vec4 uHot;          // reflected luminance at full strength; wet-film breakup share; suppression power; albedo mip bias
uniform sampler2D uEnvelope;  // the waveform's envelope table (lower/upper, colours), shared with the mist
uniform vec2 uEnvelopeSpan;
uniform vec4 uPool;         // gain, height falloff, depth falloff behind, depth falloff toward the camera
uniform float uPoolZ;       // the sheets' depth (world z)
uniform vec3 uColumn;       // fade length toward the camera, far sparkle strength, sparkle threshold
uniform int uSpecMode;      // reflection term: 0 inline, 1 write it alone (pre-pass), 2 read it from uSpecular
uniform sampler2D uSpecular;
uniform vec3 uEye;
uniform vec3 uForward;
uniform int uOrthographic;
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
""" + ENVELOPE_ROWS_GLSL + MIST_GLSL + PLANAR_REFLECTION_GLSL + """
// World-space slope of one height sample set at two incommensurate orientations (no visible tile lattice).
vec2 slopeAt(vec2 xz, float tile) {
    mat2 turn=mat2(0.6,-0.8,0.8,0.6);
    vec2 uv=xz/tile;
    vec2 near=texture(uSlope,uv).rg;
    vec2 far=transpose(turn)*texture(uSlope,turn*uv*1.37+vec2(.31,.47)).rg*1.37;
    return (0.6*near+0.4*far)/tile;
}
void main() {
    if(uFlat==1) { FragColor=vec4(vec3(0.25),1.0); Emission=vec4(0.0); return; }
    mat2 turn=mat2(0.6,-0.8,0.8,0.6);
    vec2 uv=vWorldPos.xz/uFloor.x;
    // Mip-biased and toned down: at this grazing angle the colour scan aliases into horizontal bands once lit.
    vec3 albedo=mix(texture(uAlbedo,uv,uHot.w).rgb,texture(uAlbedo,turn*uv*1.37+vec2(.31,.47),uHot.w).rgb,.4);
    albedo=mix(vec3(dot(textureLod(uAlbedo,vec2(.5),20.0).rgb,vec3(.333))),albedo,0.5)*uFloorTone.x;
    vec3 specular;
    if(uSpecMode==2) {
        specular=texture(uSpecular,gl_FragCoord.xy/uViewport).rgb;
    } else {
    vec2 broad=slopeAt(vWorldPos.xz,uFloor.x)*uFloorTone.z;
    vec2 micro=slopeAt(vWorldPos.xz,uFloor.y)*uFloorTone.w;
    // Offsets follow the viewed ground axes, so a turned camera streaks along its own view.
    vec3 groundForward=normalize(vec3(uForward.x,0.0,uForward.z));
    vec3 groundRight=cross(groundForward,vec3(0,1,0));
    vec2 axes=vec2(dot(vec3(broad.x,0,broad.y),groundRight),dot(vec3(broad.x,0,broad.y),groundForward));
    vec2 fine=vec2(dot(vec3(micro.x,0,micro.y),groundRight),dot(vec3(micro.x,0,micro.y),groundForward));
    vec2 offset=axes*uRipple.x+fine*vec2(uRipple.y,uRipple.z);
    float roughness=mix(uStreak.y,uStreak.z,clamp(length(broad)*uStreak.w,0.0,1.0));
    vec3 reflected=planarReflection(gl_FragCoord.xy/uViewport,offset,roughness);
    vec3 view=uOrthographic==1?normalize(uForward):normalize(vWorldPos-uEye);
    float cosine=clamp(abs(view.y),0.0,1.0);
    float fresnel=uFloor.w+(1.0-uFloor.w)*pow(1.0-cosine,5.0);
    // A rough wet floor shows its hot light, not a dim copy of everything: reflected light below uHot.x falls
    // away quadratically, so columns stand over dark concrete. The wet film breaks them up gently (uHot.y).
    // Relative to the scene's own reflected light (the reflection's coarsest mip): quiet and loud states both keep
    // columns over dark concrete. A fixed threshold blacked out the quiet floor and washed the loud one.
    float hot=dot(reflected,vec3(0.2126,0.7152,0.0722));
    float scene=dot(textureLod(uReflection,vec2(0.5),20.0).rgb,vec3(0.2126,0.7152,0.0722));
    reflected*=pow(clamp(hot/max(uHot.x*scene,1e-4),0.0,1.0),uHot.z);
    float film=texture(uAlbedo,uv*2.3+vec2(.17,.61)).r/max(texture(uAlbedo,uv*2.3+vec2(.17,.61),6.0).r,1e-3);
    reflected*=mix(1.0,smoothstep(0.6,1.25,film),uHot.y);
    // Column shaping: brightest at the contact under the sheets, fading toward the camera, where only the
    // wet film's brighter grains still catch it (sparkle).
    float toward=max(vWorldPos.z-uPoolZ,0.0);
    float near=exp(-toward/max(uColumn.x,1e-3));
    float grain=smoothstep(uColumn.z,1.0,film);
    reflected*=mix(grain*uColumn.y,1.0,near);
    specular=reflected*fresnel*uFloor.z;
    }
    if(uSpecMode==1) { FragColor=vec4(specular,1.0); Emission=vec4(0.0); return; }
    vec3 field=uFogLit==1?texture(uFogLight,clamp(fogCoordinate(vWorldPos+vec3(0,0.05,0))/vec3(1,1,uFogRange.z),
                                                   vec3(0.0),vec3(1.0))).rgb:vec3(0.0);
    // Coloured pools under the waveform: its lower edge lights the concrete beneath it, falling off with the edge's
    // height and with depth away from the sheets (further toward the camera), smoothed along x.
    vec3 pool=vec3(0.0);
    if(uPool.x>0.0) {
        float u=(vWorldPos.x-uEnvelopeSpan.x)*uEnvelopeSpan.y;
        float du=0.6*uEnvelopeSpan.y;
        for(int i=-2;i<=2;i++) {
            vec2 at=vec2(u+float(i)*du,0.0);
            float lower=texture(uEnvelope,at+vec2(0,0.5/ENV_ROWS)).x;
            vec3 tone=texture(uEnvelope,at+vec2(0,2.5/ENV_ROWS)).rgb;
            pool+=tone*exp(-max(lower,0.0)/uPool.y)*(1.0-abs(float(i))*0.3);
        }
        float dz=vWorldPos.z-uPoolZ;
        pool*=uPool.x*0.25*exp(-max(dz,0.0)/uPool.w)*exp(-max(-dz,0.0)/uPool.z);
    }
    vec3 colour=albedo*(uAmbient+field*uFloorTone.y+pool)+specular;
    float clear=mistTransmittance(vWorldPos);
    colour=mix(mistColour(uBackdrop,vWorldPos),colour,clear);
    FragColor=vec4(colour,1.0);
    Emission=vec4(specular*clear,dot(specular*clear,vec3(0.2126,0.7152,0.0722)));
}
"""
FLAT = {'ribbon': (1., 0., 1.)}

# The lab's mist medium for the S3D-7 volume: the clear band follows the waveform's exact envelope (lower and upper
# sheet bounds along world x, with the colours of the sheets that define them), reduced per frame from the same
# admitted history the ribbons draw. Static billows anchored in the world; nothing below the floor. No clock and
# no second ribbon path.
FOG_SHAPE_GLSL = ENVELOPE_ROWS_GLSL + """
uniform sampler2D uEnvelope;  // rows: (lower, upper, presence), upper edge colour, lower edge colour
uniform vec2 uEnvelopeSpan;   // world x at u=0, 1/(world span)
uniform vec4 uFogForm;      // density, margin, edge softness, billow frequency
uniform vec4 uFogShape;       // start z, band depth, billow displacement, light decay
uniform float uFogTube;       // true 3D clearance around every sheet (world units)
uniform vec2 uFogClearance;   // push of the whole field from the envelope; distance the mist never enters
uniform vec2 uFogSlope;       // the camera's view direction: x and y change per unit z (band projection)
uniform float uFogEnds;       // how far the mist comes forward where the sheets fade (world units)
uniform vec2 uFogSides;       // |world x| where the clear room starts to close, and where the side wall stands
uniform vec3 uFogFloor;       // floor bank height, forward reach at the sides, |x| where the sides begin
uniform vec3 uFogInterior;   // lump floor (0..1), lump frequency, rim fall per unit of push
uniform vec3 uFogFloorLight;  // floor mist light share, its reach from the sheets, light of the wall behind them
float fogHash(vec3 p) { p=fract(p*0.3183099+0.1); p*=17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
float fogNoise(vec3 x) {
    vec3 i=floor(x), f=fract(x);
    f=f*f*(3.0-2.0*f);
    return mix(mix(mix(fogHash(i),fogHash(i+vec3(1,0,0)),f.x),mix(fogHash(i+vec3(0,1,0)),fogHash(i+vec3(1,1,0)),f.x),f.y),
               mix(mix(fogHash(i+vec3(0,0,1)),fogHash(i+vec3(1,0,1)),f.x),mix(fogHash(i+vec3(0,1,1)),fogHash(i+vec3(1,1,1)),f.x),f.y),f.z);
}
float fogBillow(vec3 p) {
    float sum=0.0, amplitude=0.5;
    for(int i=0;i<3;i++) { sum+=amplitude*fogNoise(p); p=p*2.03+vec3(1.7,9.2,3.1); amplitude*=0.5; }
    return sum/0.875;
}
// True 3D distance to the nearest sheet (a tube of its half-width around its centreline), sampled at a few x
// offsets so steep stretches are not under-measured. Every view angle sees the mist keep this clearance.
float fogSheetDistance(vec3 world) {
    float d=1e3;
    for(int r=0;r<ENV_RIBBONS;r++) {
        float v=(3.5+float(r))/ENV_ROWS;
        for(int k=-2;k<=2;k++) {
            float xo=float(k)*0.35;
            vec4 s=texture(uEnvelope,vec2((world.x+xo-uEnvelopeSpan.x)*uEnvelopeSpan.y,v));
            if(s.w<0.02) continue;
            d=min(d,length(vec3(xo,world.y-s.x,world.z-s.y))-s.z);
        }
    }
    return d;
}
// Depth into the mist (world units): behind the start plane, and outside the clear band around the waveform's
// envelope unless beyond the band's depth. Billows displace the band's edge.
float fogInside(vec3 world, out vec4 band, out float above, out float below) {
    // Projected along the camera's view direction onto z = 0 (see waveform_envelope): the band follows the
    // waveform's outline as this camera sees it, at any yaw or pitch.
    float px=world.x-uFogSlope.x*world.z;
    band=texture(uEnvelope,vec2((px-uEnvelopeSpan.x)*uEnvelopeSpan.y,0.5/ENV_ROWS));
    // The waveform repels the mist: the whole field (shape and light) is pushed out from the envelope by the
    // first clearance; billow tips that still come closer than the second are cut, so the cut face is lit.
    float y=world.y-uFogSlope.y*world.z;
    float raw=max(y-band.y,band.x-y);
    // Only the mist above is pushed up: pushing the lower mist down squashed it into a flat lit slab on the floor.
    above=y-band.y-uFogClearance.x; below=band.x-y;
    // Billows shape the mist freely, but the waveform repels it: nothing within the clearance of the sheets
    // (measured from the envelope, which counts part of each sheet's width) survives.
    float outside=min(max(above,below)-uFogForm.y+uFogShape.z*(fogBillow(world*uFogForm.w)-0.5),
                      raw-uFogClearance.y);
    // Where the sheets fade out (head, tail) the mist comes forward around them, so they blend into it in wide
    // views; elsewhere it begins just behind the sheets.
    float front=uFogShape.x+(1.0-band.z)*uFogEnds;
    float behind=front-world.z+uFogShape.z*(fogBillow(world.zyx*uFogForm.w*0.8+vec3(5.3))-0.5)*1.5;
    float field=min(behind,max(outside,behind-uFogShape.y));
    // Side walls beyond the framed view, at every depth: views along the ribbons see them run into mist instead of
    // a clear slab to the far floor and the sky. Billows break the wall's face.
    float sideWall=abs(world.x)-uFogSides.y+uFogShape.z*(fogBillow(world.zyx*uFogForm.w*0.7+vec3(2.9))-0.5)*1.5;
    field=max(field,sideWall);
    // Under the waveform (where sheets are present) the reactive mist is absent: the floor takes the cheap analytic
    // mist. Isolated eroded lumps survived there and read as stray puffs at the contact line. Only near the sheets:
    // beyond the band's depth the distant wall returns, or high sheets left the sky down to the horizon unfilled
    // (black) under them.
    field=below>0.0?mix(field,-1.0,smoothstep(0.0,0.3,below)*band.z
                         *(1.0-smoothstep(uFogShape.y-2.0,uFogShape.y,behind))):field;
    // Floor mist: low billowed banks on the floor, reaching toward the camera at the sides (the mock's lower
    // corners), thin under the sheets and never within their clearance.
    float side=smoothstep(uFogFloor.z,uFogFloor.z+3.0,abs(world.x));
    // A rounded mound (height over its forward reach, an ellipse in y/z), so banks never show a flat top or a
    // vertical face where a height limit meets a depth limit; billows break its surface.
    float height=uFogFloor.x*(0.2+1.2*side);
    float reach=max(side*uFogFloor.y,1e-3);
    float mound=height*(1.0-length(vec2(world.y/max(height,1e-3),max(world.z-uFogShape.x,0.0)/reach)))
                +uFogShape.z*0.9*(fogBillow(world*uFogForm.w*1.3+vec3(2.1))-0.5);
    // Banks off: no mound at all (its billow term alone would float noise puffs anywhere in the world).
    float floorMist=uFogFloor.x>0.0?min(mound,raw-uFogClearance.y):-1e3;
    // The waveform truly repels the mist in 3D: nothing within the tube clearance of any sheet, from any angle.
    return world.y<0.0?-1.0:min(max(field,floorMist),fogSheetDistance(world)-uFogTube);
}
"""

# The march's fine coverage: the same shape per sample, so the band's edge never stair-steps at the coarse cells.
FOG_COVERAGE_GLSL = FOG_SHAPE_GLSL + """
// The march asks for coverage and then the light direction at the same sample: the shape is evaluated once and its
// side (above/below the band) remembered for the direction (the shape and its noise dominate the march's cost).
vec3 fogLastWorld=vec3(1e30);
float fogLastSide=0.0;
uniform sampler3D uShapeBake;  // per-frame bake of the shape: inside-distance (r), side above/below the band (g)
uniform vec3 uBakeMin;
uniform vec3 uBakeSize;
uniform int uBaked;
float fogCoverage(vec3 world, float coarse) {
    vec3 t=(world-uBakeMin)/uBakeSize;
    float inside;
    if(uBaked==1 && all(greaterThanEqual(t,vec3(0.0))) && all(lessThanEqual(t,vec3(1.0)))) {
        vec2 baked=texture(uShapeBake,t).rg;
        inside=baked.r;
        fogLastSide=baked.g;
    } else {
        vec4 band; float above, below;
        inside=fogInside(world,band,above,below);
        fogLastSide=above>0.0?1.0:below>0.0?-1.0:0.0;
    }
    fogLastWorld=world;
    return smoothstep(0.0,uFogForm.z,inside);
}
// Each lobe is lit from the waveform: mist above the band from below, mist below it from above, the far wall from
// the front. Shading toward clearer air pointed at the camera and left the lobes flat.
vec3 fogLightDirection(vec3 world) {
    float side=fogLastSide;
    if(world!=fogLastWorld) {
        vec4 band; float above, below;
        fogInside(world,band,above,below);
        side=above>0.0?1.0:below>0.0?-1.0:0.0;
    }
    return normalize(side>0.5?vec3(0.0,-1.0,0.35):side<-0.5?vec3(0.0,1.0,0.35):vec3(0.0,0.0,1.0));
}
"""

# Per-frame shape bake: the march samples the shape many times per pixel; evaluating it once per cell of a world
# grid (trilinear in the march) is several times cheaper. The coarse medium keeps the exact shape.
SHAPE_BAKE_COMPUTE = """#version 460 core
layout(local_size_x=8,local_size_y=8,local_size_z=4) in;
layout(rg16f,binding=0) uniform writeonly image3D uShapeOut;
uniform vec3 uBakeMin;
uniform vec3 uBakeCell;
""" + FOG_SHAPE_GLSL + """
void main() {
    ivec3 cell=ivec3(gl_GlobalInvocationID);
    if(any(greaterThanEqual(cell,imageSize(uShapeOut)))) return;
    vec3 world=uBakeMin+(vec3(cell)+0.5)*uBakeCell;
    vec4 band; float above, below;
    float inside=fogInside(world,band,above,below);
    imageStore(uShapeOut,cell,vec4(clamp(inside,-64.0,64.0),above>0.0?1.0:below>0.0?-1.0:0.0,0.0,0.0));
}
"""

# The coarse medium: the same shape, lit by the nearest sheet edge's colour.
FOG_MEDIUM_GLSL = FOG_SHAPE_GLSL + """
uniform vec4 uFogLook;        // ambient rgb, rim gain
uniform vec3 uFogRim;         // reach, sheets back z, sheets front z
uniform float uFogHaze;       // extinction of the faint haze in the clear band (steady)
void fogMedium(vec3 world, out vec3 radiance, out float extinction, out float steady) {
    radiance=vec3(0.0); extinction=0.0; steady=0.0;
    if(world.y<0.0) return;
    vec4 band; float above, below;
    float inside=fogInside(world,band,above,below);
    steady=world.z<uFogShape.x+1.0?uFogHaze:0.0;
    extinction=uFogForm.x*smoothstep(0.0,uFogForm.z,inside)+steady;
    float u=(world.x-uFogSlope.x*world.z-uEnvelopeSpan.x)*uEnvelopeSpan.y;
    vec3 upperColour=texture(uEnvelope,vec2(u,1.5/ENV_ROWS)).rgb;
    vec3 lowerColour=texture(uEnvelope,vec2(u,2.5/ENV_ROWS)).rgb;
    // The nearest sheet edge lights the mist in its colour, by distance from the sheets (outside the envelope and
    // behind or before their depth): continuous, since the light lives on the coarse cells. The far wall behind
    // the band stays dark; light fades with depth into the mist, so rims glow and interiors stay dark.
    vec3 edge=above>0.0?upperColour:below>0.0?lowerColour
             :mix(lowerColour,upperColour,clamp(-below/max(band.y-band.x,1e-3),0.0,1.0));
    float dy=max(max(above,below),0.0);
    float dz=max(max(uFogRim.y-world.z,world.z-uFogRim.z),0.0);
    // The face glows wherever the billows pushed it (a gentle fall with the push, uFogInterior.z), and fades into
    // the mist from that face. Falling off by distance from the envelope left pushed stretches dark: a broken edge.
    float rim=exp(-dz/uFogRim.x)*exp(-max(dy-uFogForm.y,0.0)*uFogInterior.z)*exp(-max(inside,0.0)*uFogShape.w);
    // The wall directly behind the sheets (inside their outline) and the far wall under them (the only volume mist
    // below the band) are distant haze: dark grey, barely lit. Lit, the far wall showed as puffs at the contact line.
    if(above<=0.0) rim*=uFogFloorLight.z;
    // Floor mist is lit from above by the sheets' lower edge colour, with a longer reach than the rims.
    float low=1.0-smoothstep(0.0,uFogFloor.x*1.5,world.y);
    // Only mist below the sheets' outline: the wall behind them must stay dark grey haze.
    float sides=smoothstep(uFogFloor.z,uFogFloor.z+3.0,abs(world.x));  // the mock's lit corner banks
    float floorLit=low*mix(0.15,1.0,sides)*smoothstep(0.0,0.3,below)*uFogFloorLight.x*exp(-below/uFogFloorLight.y)
                   *exp(-max(inside,0.0)*uFogShape.w*0.5);
    // Interior volume: large dim lumps in the unlit body, so the mass away from its edges is not one flat grey.
    float lumps=mix(1.0,uFogInterior.x+(2.0-2.0*uFogInterior.x)*fogBillow(world*uFogInterior.y+vec3(7.7,3.1,1.9)),
                    smoothstep(0.0,1.5,inside));
    radiance=uFogLook.rgb*lumps+edge*uFogLook.w*rim+lowerColour*uFogLook.w*floorLit;
}
"""
