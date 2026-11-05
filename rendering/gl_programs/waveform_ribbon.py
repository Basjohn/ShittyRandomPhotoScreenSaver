"""Waveform infinite wet-floor material; no scene lifetime or simulation."""
from rendering.gl_programs.mist import MIST_GLSL
from rendering.gl_programs.reflection import PLANAR_REFLECTION_GLSL
from rendering.gl_programs.waveform_atmosphere import WORLD_FIELD_GLSL

FLOOR_VERTEX = """#version 460 core
layout(location=0) in vec3 aPosition;
out vec2 vFloorNdc;
void main() { vFloorNdc=aPosition.xz*2.0-1.0; gl_Position=vec4(vFloorNdc,0.0,1.0); }
"""
# The ground is an opaque infinite world plane, not a finite actor. Orthographic
# pixel lines can meet it before the arbitrary eye-reference plane or beyond the
# actor far clip. Only this primitive clamps its projected depth; actors retain
# their camera-owned raster interval; Perspective remains positive.
FLOOR_WORLD_GLSL = """
in vec2 vFloorNdc;
uniform mat4 uMvp;
uniform mat4 uFloorInverseMvp;
uniform vec3 uEye;
uniform int uOrthographic;
bool floorWorldHit(out vec3 world, out float depth) {
    vec4 a=uFloorInverseMvp*vec4(vFloorNdc,-1.0,1.0);
    vec4 b=uFloorInverseMvp*vec4(vFloorNdc,1.0,1.0);
    vec3 nearPoint=a.xyz/a.w,farPoint=b.xyz/b.w;
    vec3 origin=uOrthographic==1?nearPoint:uEye;
    vec3 direction=normalize(farPoint-origin);
    if(direction.y>=0.0)return false;
    float distance_=-origin.y/direction.y;
    if(uOrthographic!=1 && distance_<=0.0)return false;
    world=origin+direction*distance_;
    world.y=0.0;
    vec4 clip=uMvp*vec4(world,1.0);
    // Strictly below the clear depth, so the far ground survives GL_LESS.
    depth=clamp(0.5*(clip.z/clip.w+1.0),0.0,uintBitsToFloat(0x3f7fffffu));
    return true;
}
"""
# RMS slope per uv unit of the shipped smooth wet-surface height map: relief terms work in units of it, so the
# material's shading and the reflection breakup keep their strength if the map is regenerated at another contrast.
HEIGHT_SLOPE_RMS = 5.
FLOOR_FRAGMENT = "#version 460 core\n" + FLOOR_WORLD_GLSL + """
uniform sampler2D uAlbedo;
uniform sampler2D uRoughness;
uniform sampler2D uSlope;      // height slope per uv unit (rg), from the smooth wet-surface height map
uniform int uFlat;
uniform int uFogLit;
uniform vec2 uViewport;
uniform vec3 uBackdrop;
uniform vec3 uAmbient;
uniform vec3 uFloorTint;
uniform vec4 uFloor;        // tile, micro tile, reflection gain, f0
uniform vec3 uFloorTone;    // albedo gain, broad relief amplitude, micro relief amplitude
uniform vec3 uRipple;       // reflection offset per unit slope: broad, micro across, micro along
uniform vec4 uStreak;       // optical streak length (world units at Streak Length 1), roughness min/max, broad-slope gain to roughness
uniform vec4 uHot;          // reflected luminance at full strength; wet-film breakup share; suppression power; albedo mip bias
uniform vec4 uMaterial;     // albedo contrast, relief shading, reflection relief breakup, source-light depth spread
uniform vec3 uMaterialShape; // material elongation along world z, relief mip bias, column height falloff (world)
uniform float uPool;
uniform float uPoolZ;       // the sheets' depth (world z)
uniform vec3 uColumn;       // fade length toward the camera, far sparkle strength, sparkle threshold
uniform float uReflectionHue; // reflected chroma about its luminance (1 as reflected)
uniform int uSpecMode;      // reflection term: 0 inline, 1 write it alone (pre-pass), 2 read it from uSpecular
uniform sampler2D uSpecular;
uniform vec3 uForward;
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
""" + WORLD_FIELD_GLSL + MIST_GLSL + PLANAR_REFLECTION_GLSL + """
const float HEIGHT_SLOPE_RMS=""" + repr(HEIGHT_SLOPE_RMS) + """;
// World-space slope of one height sample set at two incommensurate orientations (no visible tile lattice).
vec2 slopeAt(vec2 xz, float tile, float bias) {
    mat2 turn=mat2(0.6,-0.8,0.8,0.6);
    vec2 uv=xz/tile;
    vec2 near=texture(uSlope,uv,bias).rg;
    vec2 far=transpose(turn)*texture(uSlope,turn*uv*1.37+vec2(.31,.47),bias).rg*1.37;
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
vec3 columnReflection(vec2 screenUv, vec2 offset, float halfLength, float across) {
    vec2 size=vec2(textureSize(uReflection,0));
    float pixelSpan=max(length(dFdx(screenUv)*size),length(dFdy(screenUv)*size));
    float span=max(across,pixelSpan);
    float spacing=2.0*halfLength/float(COLUMN_TAPS);
    vec2 dx=vec2(span/size.x,0.0), dy=vec2(0.0,max(span/size.y,COLUMN_OVERLAP*spacing));
    vec2 uv=screenUv+offset;
    vec3 colour=vec3(0.0);
    float tint=0.0, weight=0.0, moment=0.0, total=0.0;
    for(int i=0;i<COLUMN_TAPS;i++) {
        float t=(float(i)+0.5)*2.0/float(COLUMN_TAPS)-1.0;
        vec4 sample_=textureGrad(uReflection,clamp(uv+vec2(0.0,t*halfLength),vec2(0),vec2(1)),dx,dy);
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
void main() {
    vec3 vWorldPos;float groundDepth;
    if(!floorWorldHit(vWorldPos,groundDepth))discard;
    gl_FragDepth=groundDepth;
    if(uFlat==1) { FragColor=vec4(vec3(0.25),1.0); Emission=vec4(0.0); return; }
    mat2 turn=mat2(0.6,-0.8,0.8,0.6);
    // The material is laid out elongated along world z: this camera looks along the ground at a few degrees, which
    // flattens isotropic concrete into hairline scanlines; elongated, its blotches and relief read at the
    // proportions of a wet floor seen from standing height. World-fixed, so it never swims with the view.
    vec2 materialXz=vec2(vWorldPos.x,vWorldPos.z/max(uMaterialShape.x,1.0));
    vec2 uv=materialXz/uFloor.x;
    // Mip-biased: at this grazing angle the colour scan aliases into horizontal bands once lit. The concrete's own
    // variation is restored around its exact mean (the 1x1 level), so legibility never changes the floor's level.
    vec3 grain=mix(texture(uAlbedo,uv,uHot.w).rgb,texture(uAlbedo,turn*uv*1.37+vec2(.31,.47),uHot.w).rgb,.4);
    vec3 mean=textureLod(uAlbedo,vec2(0.5),20.0).rgb;
    vec3 albedo=max(mean+(grain-mean)*uMaterial.x,vec3(0.0))*uFloorTone.x;
    float surfaceRoughness=texture(uRoughness,uv,uHot.w).r;
    // Offsets and relief follow the viewed ground axes, so a turned camera streaks along its own view.
    vec3 groundForward=normalize(vec3(uForward.x,0.0,uForward.z));
    vec3 groundRight=cross(groundForward,vec3(0,1,0));
    vec2 broadSlope=slopeAt(materialXz,uFloor.x,uMaterialShape.y);
    // Unit-RMS rise of the broad relief along the view. Foreshortening turns it into the long horizontal breaks a
    // grazing wet floor shows; the material's shading and the reflection's breakup are both this one surface.
    float rise=dot(vec3(broadSlope.x,0,broadSlope.y),groundForward)*uFloor.x/HEIGHT_SLOPE_RMS;
    vec3 specular;
    if(uSpecMode==2) {
        specular=texture(uSpecular,gl_FragCoord.xy/uViewport).rgb;
    } else {
    vec2 broad=broadSlope*uFloorTone.y;
    vec2 micro=slopeAt(vWorldPos.xz,uFloor.y,0.0)*uFloorTone.z;
    vec2 axes=vec2(dot(vec3(broad.x,0,broad.y),groundRight),dot(vec3(broad.x,0,broad.y),groundForward));
    vec2 fine=vec2(dot(vec3(micro.x,0,micro.y),groundRight),dot(vec3(micro.x,0,micro.y),groundForward));
    vec2 offset=axes*uRipple.x+fine*vec2(uRipple.y,uRipple.z);
    float roughness=mix(uStreak.y,uStreak.z,clamp(surfaceRoughness+length(broad)*uStreak.w,0.0,1.0));
    // Optical streak length is fixed in world units. A fixed UV length grew with
    // the edge-resize aperture and washed the same physical reflection away.
    vec4 clip=uMvp*vec4(vWorldPos,1.0);
    vec4 direction=uMvp*vec4(groundForward,0.0);
    float projected=abs(0.5*(direction.y*clip.w-clip.y*direction.w)/(clip.w*clip.w));
    float streak=uStreak.x*uReflectionLook.x*projected;
    vec3 reflected=columnReflection(gl_FragCoord.xy/uViewport,offset,streak*roughness,
                                    exp2(mix(uReflectionLook.y,uReflectionLook.z,roughness)));
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
    // The reflection carries the sheets' own saturated hue: chroma about its luminance is lifted (uReflectionHue),
    // so the coloured mass reads as teal or orange over the grey concrete rather than a pastel wash.
    float hueLevel=dot(reflected,vec3(0.2126,0.7152,0.0722));
    reflected=max(vec3(hueLevel)+(reflected-vec3(hueLevel))*uReflectionHue,vec3(0.0));
    // Wet-film grain and sparkle sample the albedo's finest level; at this grazing view that grain is sub-pixel
    // and shimmers as the light under it moves, so both are opt-in (uHot.y, uColumn.z; 0 is a smooth column).
    float film=1.0;
    if(uHot.y>0.0 || uColumn.z>0.0)
        film=texture(uAlbedo,uv*2.3+vec2(.17,.61)).r/max(texture(uAlbedo,uv*2.3+vec2(.17,.61),6.0).r,1e-3);
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
    vec3 colour=albedo*uFloorTint*(uAmbient+pool)*shade+specular;
    float clear=mistTransmittance(vWorldPos);
    colour=mistOver(colour,uBackdrop,vWorldPos);
    FragColor=vec4(colour,1.0);
    Emission=vec4(specular*clear,dot(specular*clear,vec3(0.2126,0.7152,0.0722)));
}
"""
FLAT = {'ribbon': (1., 0., 1.)}
