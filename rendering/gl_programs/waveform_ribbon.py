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
uniform vec4 uStreak;       // unused, roughness min/max, broad-slope gain to roughness
uniform vec4 uHot;          // reflected luminance at full strength; wet-film breakup share; suppression power; albedo mip bias
uniform float uPool;
uniform float uPoolZ;       // the sheets' depth (world z)
uniform vec3 uColumn;       // fade length toward the camera, far sparkle strength, sparkle threshold
uniform int uSpecMode;      // reflection term: 0 inline, 1 write it alone (pre-pass), 2 read it from uSpecular
uniform sampler2D uSpecular;
uniform vec3 uForward;
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
""" + WORLD_FIELD_GLSL + MIST_GLSL + PLANAR_REFLECTION_GLSL + """
// World-space slope of one height sample set at two incommensurate orientations (no visible tile lattice).
vec2 slopeAt(vec2 xz, float tile) {
    mat2 turn=mat2(0.6,-0.8,0.8,0.6);
    vec2 uv=xz/tile;
    vec2 near=texture(uSlope,uv).rg;
    vec2 far=transpose(turn)*texture(uSlope,turn*uv*1.37+vec2(.31,.47)).rg*1.37;
    return (0.6*near+0.4*far)/tile;
}
void main() {
    vec3 vWorldPos;float groundDepth;
    if(!floorWorldHit(vWorldPos,groundDepth))discard;
    gl_FragDepth=groundDepth;
    if(uFlat==1) { FragColor=vec4(vec3(0.25),1.0); Emission=vec4(0.0); return; }
    mat2 turn=mat2(0.6,-0.8,0.8,0.6);
    vec2 uv=vWorldPos.xz/uFloor.x;
    // Mip-biased and toned down: at this grazing angle the colour scan aliases into horizontal bands once lit.
    vec3 albedo=mix(texture(uAlbedo,uv,uHot.w).rgb,texture(uAlbedo,turn*uv*1.37+vec2(.31,.47),uHot.w).rgb,.4);
    float surfaceRoughness=texture(uRoughness,uv,uHot.w).r;
    // Wet patches darken the diffuse surface while the rougher concrete stays legible outside hot reflections.
    albedo*=mix(0.45,1.65,smoothstep(0.08,0.55,surfaceRoughness))*uFloorTone.x;
    vec3 specular;
    if(uSpecMode==2) {
        specular=texture(uSpecular,gl_FragCoord.xy/uViewport).rgb;
    } else {
    vec2 broad=slopeAt(vWorldPos.xz,uFloor.x)*uFloorTone.y;
    vec2 micro=slopeAt(vWorldPos.xz,uFloor.y)*uFloorTone.z;
    // Offsets follow the viewed ground axes, so a turned camera streaks along its own view.
    vec3 groundForward=normalize(vec3(uForward.x,0.0,uForward.z));
    vec3 groundRight=cross(groundForward,vec3(0,1,0));
    vec2 axes=vec2(dot(vec3(broad.x,0,broad.y),groundRight),dot(vec3(broad.x,0,broad.y),groundForward));
    vec2 fine=vec2(dot(vec3(micro.x,0,micro.y),groundRight),dot(vec3(micro.x,0,micro.y),groundForward));
    vec2 offset=axes*uRipple.x+fine*vec2(uRipple.y,uRipple.z);
    float roughness=mix(uStreak.y,uStreak.z,clamp(surfaceRoughness+length(broad)*uStreak.w,0.0,1.0));
    // Optical streak length is fixed in world units. A fixed UV length grew with
    // the edge-resize aperture and washed the same physical reflection away.
    vec4 clip=uMvp*vec4(vWorldPos,1.0);
    vec4 direction=uMvp*vec4(groundForward,0.0);
    float projected=abs(0.5*(direction.y*clip.w-clip.y*direction.w)/(clip.w*clip.w));
    float streak=38.4*uReflectionLook.x*projected;
    vec3 reflected=planarReflection(gl_FragCoord.xy/uViewport,offset,roughness,streak);
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
    // Local source light uses the same physical cloth field as the atmosphere, never a projected envelope.
    vec3 pool=uFogLit==1?groundLight(vWorldPos)*uPool:vec3(0.0);
    vec3 colour=albedo*uFloorTint*(uAmbient+pool)+specular;
    float clear=mistTransmittance(vWorldPos);
    colour=mistOver(colour,uBackdrop,vWorldPos);
    FragColor=vec4(colour,1.0);
    Emission=vec4(specular*clear,dot(specular*clear,vec3(0.2126,0.7152,0.0722)));
}
"""
FLAT = {'ribbon': (1., 0., 1.)}
