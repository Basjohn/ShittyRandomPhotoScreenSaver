"""Framed basin projection and terrain/water shaders over shared Scene3D owners.

Authored base height alone classifies water. Audio changes water height and light;
solid land has a small bounded lift, never the water's travelling displacement.
The fit is static for authored terrain/view and the final scene pose acts only in
the card interior. No audio-dependent framing or geometry is involved.
"""
from __future__ import annotations

import math
import struct

from rendering.gl_programs.heightfield_glsl import HEIGHTFIELD_GLSL, HEIGHTFIELD_WIRE_GLSL
from rendering.gl_programs.scene3d import SCENE3D_ORBIT_GLSL, scene3d_orbit_project
from rendering.gl_programs.shockwave_grid_program import (
    SHOCKWAVE_DEPTH, SHOCKWAVE_EVENTS, SHOCKWAVE_MAX_BARS, SHOCKWAVE_WAVE_GLSL,
)


def basin_camera(half_width: float, maximum: float) -> float:
    return max(3.0, 1.25 * math.sqrt(half_width ** 2 + (SHOCKWAVE_DEPTH / 2) ** 2 + maximum ** 2))


def basin_project(point, tilt, turn, camera):
    return scene3d_orbit_project(point,tilt,turn,camera=camera,pivot=(0.0,0.0,-0.5*SHOCKWAVE_DEPTH))


def basin_bounds(size: int, data: bytes) -> tuple:
    """Sixteen conservative authored patches, derived once per terrain change."""
    heights = struct.unpack(f"<{size * size * 2}f", data)[::2]
    edges = tuple(round(i * (size - 1) / 4) for i in range(5))
    points = []
    for y0, y1 in zip(edges, edges[1:]):
        for x0, x1 in zip(edges, edges[1:]):
            highest = max(heights[y * size + x]
                          for y in range(max(0,y0-2),min(size,y1+3))
                          for x in range(max(0,x0-2),min(size,x1+3)))
            points.extend((x / (size - 1), y, z / (size - 1))
                          for x in (x0, x1) for z in (y0, y1) for y in (-0.20, highest))
    return tuple(points)


def basin_fit(tilt: float, turn: float, half_width: float, maximum: float, aspect: float,
              bounds=None, height_scale: float = 1.0) -> tuple[float, float]:
    """Static conservative fit, reserving sky above the authored basin."""
    camera = basin_camera(half_width, maximum)
    world = (((u*2.0 - 1.0)*half_width, y*height_scale if y > 0 else y, -v*SHOCKWAVE_DEPTH)
             for u,y,v in bounds) if bounds is not None else (
                 (x,y,z) for x in (-half_width, 0.0, half_width)
                 for y in (-0.10,maximum) for z in (0.0,-SHOCKWAVE_DEPTH))
    points = [basin_project(point, tilt, turn, camera) for point in world]
    low, high = min(p[1] for p in points), max(p[1] for p in points)
    span = max(p[0] for p in points) - min(p[0] for p in points)
    scale = min(0.80 / max(high - low, 1e-3), 1.15 * aspect / max(span, 1e-3))
    return scale, 0.96 + low * scale


def basin_item_point(point, field, fit, tilt, turn, half_width, maximum, scene_scale=1.0, pan=(0.0, 0.0)):
    """CPU mirror of basinItem: scale about interior centre, then normalized pan."""
    sx, sy, _depth = basin_project(point, tilt, turn, basin_camera(half_width, maximum))
    x, y, width, height = field
    cx, cy = x + width / 2, y + height / 2
    px = cx + sx * fit[0] * height
    py = y + height * (fit[1] - sy * fit[0])
    return (cx + (px - cx) * scene_scale + pan[0] * width,
            cy + (py - cy) * scene_scale + pan[1] * height)


_PROJECTION = f"""
const float SHOCKWAVE_DEPTH = {SHOCKWAVE_DEPTH:.6f};
uniform mat4 uMatrix;
uniform vec4 uField;
uniform vec2 uView;
uniform float uCamera;
uniform vec2 uFit;
uniform float uHalfWidth;
uniform float uHorizon;
uniform int uBarCount;
uniform float uBars[{SHOCKWAVE_MAX_BARS}];
uniform float uHeightScale;
vec3 shockwaveProject(vec3 p) {{
    return sceneOrbitProject(p,uView,vec3(0.0,0.0,-0.5*SHOCKWAVE_DEPTH),vec3(0.0),uCamera);
}}
"""
_POSE = """
uniform vec3 uScenePose; // scale, pan-x, pan-y (fractions of interior)
vec2 basinItem(vec3 world) {
    vec3 screen = shockwaveProject(world);
    vec2 centre = uField.xy + 0.5 * uField.zw;
    vec2 item = vec2(centre.x + screen.x * uFit.x * uField.w,
                    uField.y + uField.w * (uFit.y - screen.y * uFit.x));
    return centre + (item - centre) * uScenePose.x + uScenePose.yz * uField.zw;
}
vec3 basinUnview(vec3 p) {
    float c = cos(uView.x), s = sin(uView.x);
    p = vec3(p.x, p.y*c + p.z*s, -p.y*s + p.z*c);
    c = cos(uView.y); s = sin(uView.y);
    return vec3(p.x*c - p.z*s, p.y, p.x*s + p.z*c);
}
"""

_TERRAIN = """
uniform sampler2D uTerrain;
uniform int uTerrainSize;
uniform vec3 uLand; // height, restrained reactivity, static detail
uniform float uTime;
uniform float uWaterDetail;
uniform float uWaterBankBand;
uniform int uPass; // 0 reflected land, 1 complete surface
uniform float uTerrainGrowth[8];
float basinBase(vec2 uv) { return sceneHeightfield(uTerrain, uTerrainSize, uv); }
float basinDetail(vec2 p) {
    // Fixed spatial detail: never animated or driven by audio.
    return 0.5 + 0.25*sin(19.0*p.x + 7.0*p.y) + 0.25*cos(23.0*p.y - 9.0*p.x);
}
float basinEnergy(vec2 uv) {
    if (uBarCount <= 0 || uHorizon <= 0.0) return 0.0;
    float f=clamp(uv.x,0.0,0.9999)*float(uBarCount)-0.5;
    int i0=clamp(int(floor(f)),0,uBarCount-1),i1=min(i0+1,uBarCount-1);
    float level=mix(uBars[i0],uBars[i1],fract(f));
    return clamp(pow(clamp(level,0.0,1.0),1.15)*clamp(uHeightScale,1.0,1.85),0.0,1.0)*uHorizon/0.6;
}
vec3 basinSurface(vec2 uv, out float crest, out float energy, out float curved) {
    vec2 p = vec2((uv.x*2.0 - 1.0)*uHalfWidth, -uv.y*SHOCKWAVE_DEPTH);
    float base = basinBase(uv);
    vec2 wave = shockwaveHeight(p);
    crest = min(wave.y, 2.5);
    energy = basinEnergy(uv);
    float height;
    curved=0.0;
    if (sceneHeightfieldWater(base)) {
        float bank=smoothstep(0.0,uWaterBankBand,sceneHeightfieldBankDistance(uTerrain,uTerrainSize,uv));
        height = bank*(0.18*tanh(wave.x/0.18) + 0.0025*uWaterDetail*sin(15.0*p.x + 18.0*p.y + uTime));
    } else {
        curved=sceneHeightfieldCurve(uTerrain,uTerrainSize,uv);
        height = curved*smoothstep(0.0,0.015,base)*uLand.x*(1.0 + 0.16*uLand.z*basinDetail(p));
        float f=clamp(uv.x*8.0-0.5,0.0,7.0);
        int i0=clamp(int(floor(f)),0,7),i1=min(i0+1,7);
        float growth=mix(uTerrainGrowth[i0],uTerrainGrowth[i1],fract(f));
        height *= 1.0 + 0.25*uLand.y*growth;
    }
    return vec3(p.x, height, p.y);
}
"""

NEON_VERTEX_SOURCE = (
    "#version 460 core\nlayout(location=0) in vec2 aUv;\n"
    + SHOCKWAVE_EVENTS.glsl(3) + SCENE3D_ORBIT_GLSL + HEIGHTFIELD_GLSL + _PROJECTION + SHOCKWAVE_WAVE_GLSL + _POSE + _TERRAIN
    + """
out vec3 vWorld;
out vec2 vUv;
out float vCrest;
out float vEnergy;
out float vCurvedBase;
void main() {
    vec3 world = basinSurface(aUv, vCrest, vEnergy, vCurvedBase);
    if (uPass == 0) world.y = -world.y;
    vWorld = world;
    vUv = aUv;
    vec3 screen = shockwaveProject(world);
    vec4 clip = uMatrix * vec4(basinItem(world), 0.0, 1.0);
    clip.z = clamp(-screen.z/uCamera, -1.0, 1.0)*clip.w;
    gl_Position = clip;
}
"""
)

NEON_FRAGMENT_SOURCE = (
    "#version 460 core\nlayout(location=0) out vec4 FragColor;\nlayout(location=1) out vec4 Emission;\n"
    + SHOCKWAVE_EVENTS.glsl(3) + SCENE3D_ORBIT_GLSL + HEIGHTFIELD_GLSL + HEIGHTFIELD_WIRE_GLSL + _PROJECTION + SHOCKWAVE_WAVE_GLSL + _POSE + _TERRAIN
    + """
in vec3 vWorld;
in vec2 vUv;
in float vCrest;
in float vEnergy;
in float vCurvedBase;
uniform vec4 uLineColor;
uniform vec4 uCrestColor;
uniform vec4 uWaterColor;
uniform float uReflection;
uniform float uScroll;
uniform float uFloor;
uniform float uGlow;
uniform float uEdgePx;
uniform float uCurveCells;
vec4 sceneEmission(vec3 rgb) { return vec4(rgb, dot(rgb, vec3(0.2126,0.7152,0.0722))); }
void main() {
    // Classification is sampled again at the fragment: interpolated displaced
    // heights cannot turn land into water or move a shore during a beat.
    float base = basinBase(vUv);
    bool water = sceneHeightfieldWater(base);
    vec3 reflectionPlane=vec3(0.0);
    if (uPass == 0) {
        if (water || uReflection <= 0.0) discard;
        vec3 eye = basinUnview(vec3(0.0,0.0,uCamera)) + vec3(0.0,0.0,-0.5*SHOCKWAVE_DEPTH);
        float denominator = vWorld.y - eye.y;
        if (abs(denominator) < 1e-4) discard;
        float t = -eye.y / denominator;
        if (t <= 0.0 || t >= 1.0) discard;
        vec3 plane = mix(eye,vWorld,t);
        reflectionPlane=plane;
        vec2 uv = vec2(plane.x/(2.0*uHalfWidth)+0.5, -plane.z/SHOCKWAVE_DEPTH);
        if (any(lessThan(uv,vec2(0.0))) || any(greaterThan(uv,vec2(1.0))) || !sceneHeightfieldWater(basinBase(uv))) discard;
    }
    float shore=smoothstep(0.0,0.055,base);
    float shoreDistance=abs(vCurvedBase-0.018)/max(fwidth(vCurvedBase),0.0001);
    float shoreLight=(1.0-smoothstep(0.45,1.15,shoreDistance))
                    +0.12*exp(-pow(shoreDistance/2.8,2.0));
    shoreLight*=water ? 0.0 : 1.0;
    float line=sceneHeightfieldCurveWire(vUv,vCurvedBase,uCurveCells,uEdgePx)*shore;
    float crest = clamp(vCrest,0.0,2.5);
    vec3 palette = mix(uLineColor.rgb,uCrestColor.rgb,clamp((water ? crest*0.6 :
                      0.45+0.35*sin(vWorld.x*3.0+vWorld.z*2.0)+base*0.25),0.0,1.0));
    vec3 n = normalize(cross(dFdx(vWorld),dFdy(vWorld)));
    float light = 0.3 + 0.7*abs(dot(n,normalize(vec3(-0.4,1.0,0.5))));
    vec3 waterFill=uWaterColor.rgb*(0.60+0.10*light);
    vec3 landFill=vec3(0.02,0.007,0.045)+palette*(0.025+0.055*light);
    vec3 fill=water ? waterFill : mix(waterFill,landFill,shore);
    if (water) {
        vec2 curveUv=vUv+vec2(0.0,uScroll/SHOCKWAVE_DEPTH);
        float waveWire=sceneHeightfieldWaterCurves(curveUv,vWorld.y,uCurveCells,uEdgePx);
        float ripple=(vWorld.z+uScroll)*26.0+0.35*sin(vWorld.x*5.0)+vWorld.y*9.0;
        float distance=abs(fract(ripple-0.5)-0.5)/max(fwidth(ripple),1e-5);
        float sheen=1.0-smoothstep(0.0,0.65*uEdgePx,distance);
        float curveCoverage=waveWire*(0.11+0.55*min(crest,1.5));
        float sheenCoverage=sheen*(0.12+0.16*crest)*uWaterDetail;
        line=1.0-(1.0-curveCoverage)*(1.0-sheenCoverage);
    }
    float ridgeWeight=clamp(base*0.8+0.2*light+0.15*sin(vWorld.x*7.0+vWorld.z*5.0),0.0,1.0);
    vec3 wire=palette*(water ? 0.65+0.55*crest : 0.65+0.2*ridgeWeight+1.65*vEnergy*ridgeWeight);
    if (uPass == 0) {
        // Reflection has no land fill. Broken horizontal water bands split
        // the mirrored wires into trails instead of accumulated opaque slabs.
        vec2 p=reflectionPlane.xz;
        float ripple=sin(p.y*65.0 + p.x*3.0 + uTime*0.45)
                    + 0.45*sin(p.y*117.0-p.x*11.0-uTime*0.23);
        float breakup=mix(0.12,1.0,smoothstep(-0.25,0.8,ripple));
        float decay=exp(-abs(vWorld.y)*0.7);
        float alpha=max(line*uLineColor.a,shoreLight*uCrestColor.a)*uReflection*0.85*breakup*decay;
        if (alpha < 0.002) discard;
        vec3 reflected=wire*1.6+palette*shoreLight;
        FragColor=vec4(reflected,alpha);
        Emission=sceneEmission(reflected*alpha*uGlow*0.45);
        return;
    }
    // The original event crest illuminates curved water detail. Keep troughs
    // dark instead of covering each crest with an opaque luminous sheet.
    float ring = water ? clamp(crest*0.08,0.0,0.20) : 0.0;
    float fillAlpha=uFloor*(water ? uWaterColor.a*0.55 : 1.0);
    float lineAlpha=line*uLineColor.a;
    float ringAlpha=ring*uCrestColor.a;
    float shoreAlpha=clamp(shoreLight*(0.55+0.95*vEnergy),0.0,1.0)*uCrestColor.a;
    vec3 premult=fill*fillAlpha*(1.0-lineAlpha)+wire*lineAlpha;
    float alpha=fillAlpha*(1.0-lineAlpha)+lineAlpha;
    premult=premult*(1.0-ringAlpha)+palette*ringAlpha;
    alpha=alpha*(1.0-ringAlpha)+ringAlpha;
    vec3 shoreColour=mix(uLineColor.rgb,uCrestColor.rgb,clamp(0.5+0.45*sin(vWorld.x*3.0+vWorld.z*2.0),0.0,1.0));
    premult=premult*(1.0-shoreAlpha)+shoreColour*shoreAlpha;
    alpha=alpha*(1.0-shoreAlpha)+shoreAlpha;
    FragColor=vec4(min(premult/max(alpha,1e-4),vec3(1.0)),alpha);
    Emission=sceneEmission((wire*lineAlpha + palette*ringAlpha*0.45+shoreColour*shoreAlpha)*uGlow);
}
"""
)

_SKY_POSE = """
uniform mat4 uMatrix;
uniform vec4 uField;
uniform vec2 uView;
uniform float uCamera;
uniform vec2 uFit;
uniform vec3 uScenePose;
vec3 basinUnview(vec3 p) {
    float c=cos(uView.x),s=sin(uView.x);
    p=vec3(p.x,p.y*c+p.z*s,-p.y*s+p.z*c);
    c=cos(uView.y);s=sin(uView.y);
    return vec3(p.x*c-p.z*s,p.y,p.x*s+p.z*c);
}
"""
NEON_SKY_VERTEX_SOURCE = """#version 460 core
layout(location=0) in vec2 aUv;
out vec2 vUv;
uniform mat4 uMatrix;
uniform vec4 uField;
void main() {
    vUv=aUv;
    gl_Position=uMatrix*vec4(uField.xy + aUv*uField.zw,0.999,1.0);
}
"""
NEON_SKY_FRAGMENT_SOURCE = (
    "#version 460 core\nlayout(location=0) out vec4 FragColor;\nlayout(location=1) out vec4 Emission;\n"
    + _SKY_POSE + """
in vec2 vUv;
uniform vec4 uSkyColor;
uniform float uSkyStrength;
uniform int uSunEnabled;
uniform vec4 uSunColor;
float skyHash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
void main() {
    vec2 item=uField.xy + vUv*uField.zw;
    vec2 centre=uField.xy + 0.5*uField.zw;
    item=centre + (item-centre-uScenePose.yz*uField.zw)/uScenePose.x;
    vec2 screen=vec2((item.x-centre.x)/(uFit.x*uField.w),
                     (uFit.y-(item.y-uField.y)/uField.w)/uFit.x);
    vec3 ray=normalize(basinUnview(vec3(screen,-uCamera)));
    float dusk=exp(-pow((ray.y+0.50)/0.16,2.0));
    vec3 colour=uSkyColor.rgb*(0.65+0.35*dusk) + vec3(0.38,0.025,0.29)*dusk;
    float longitude=atan(ray.x,-ray.z);
    float clouds=0.0;
    for (int band=0;band<3;++band) {
        float phase=float(band)*2.1;
        float centre=-0.32-float(band)*0.055 + 0.005*sin(longitude*17.0+phase)+0.003*sin(longitude*37.0-phase);
        float thickness=0.006+0.002*float(band);
        float stripe=exp(-pow((ray.y-centre)/thickness,2.0));
        float breaks=smoothstep(-0.3,0.65,sin(longitude*13.0+phase)+0.4*sin(longitude*41.0-phase));
        clouds+=stripe*breaks*(0.5+0.5*sin(ray.y*320.0+longitude*7.0));
    }
    colour+=vec3(0.25,0.015,0.32)*clouds;
    vec3 sunDirection=normalize(vec3(0.52,-0.32,-1.0));
    float sunAngle=acos(clamp(dot(ray,sunDirection),-1.0,1.0));
    float sun=1.0-smoothstep(0.079,0.083,sunAngle);
    float stripePhase=fract(ray.y*62.0);
    float stripe=smoothstep(0.16,0.20,stripePhase)*(1.0-smoothstep(0.96,1.0,stripePhase));
    sun*=mix(stripe,1.0,smoothstep(-0.32,-0.22,ray.y));
    vec2 starGrid=vec2(longitude,asin(ray.y))*420.0;
    vec2 starCell=floor(starGrid);
    float starDistance=length((fract(starGrid)-0.5)/max(fwidth(starGrid),vec2(1e-4)));
    float star=step(0.985,skyHash(starCell))*(1.0-smoothstep(0.15,0.65,starDistance));
    colour+=vec3(0.65,0.8,1.0)*star*smoothstep(-0.45,-0.25,ray.y);
    float skyAlpha=uSkyColor.a*uSkyStrength;
    float sunAlpha=uSunEnabled == 1 ? sun*uSunColor.a : 0.0;
    vec3 sunColour=mix(uSunColor.rgb*0.8,uSunColor.rgb,clamp((ray.y+0.42)/0.2,0.0,1.0));
    vec3 premult=colour*uSkyStrength*skyAlpha*(1.0-sunAlpha)+sunColour*sunAlpha;
    float alpha=skyAlpha*(1.0-sunAlpha)+sunAlpha;
    FragColor=vec4(premult/max(alpha,1e-4),alpha);
    vec3 light=sunColour*sunAlpha*0.2;
    Emission=vec4(light,dot(light,vec3(0.2126,0.7152,0.0722)));
}
"""
)

__all__ = ["basin_camera", "basin_fit", "basin_bounds", "basin_project", "basin_item_point", "NEON_VERTEX_SOURCE", "NEON_FRAGMENT_SOURCE",
           "NEON_SKY_VERTEX_SOURCE", "NEON_SKY_FRAGMENT_SOURCE"]
