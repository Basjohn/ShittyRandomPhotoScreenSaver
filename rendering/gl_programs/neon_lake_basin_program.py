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
from rendering.gl_programs.heightfield_volume_glsl import HEIGHTFIELD_VOLUME_GLSL
from rendering.gl_programs.neon_celestial import NEON_CELESTIAL_GLSL
from rendering.gl_programs.scene3d import SCENE3D_GLSL, SCENE3D_ORBIT_GLSL, scene3d_orbit_project
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
    scale = min(0.85 / max(high - low, 1e-3), 1.15 * aspect / max(span, 1e-3))
    return scale, 0.99 + low * scale


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
// True homogeneous camera projection for the overscanned landscape. Flattening
// sceneOrbitProject to pixel XY *before* clipping makes triangles crossing the
// camera divide by negative/near-zero distances, producing giant sheet artifacts.
// Keep the numerator linear in view position and let GL clip at the near plane.
const float BASIN_NEAR = 0.12;
float basinFar() { return max(48.0, 20.0*uCamera); }
float basinDepthNdc(float viewZ) {
    float farPlane=basinFar();
    float distance=uCamera-viewZ;
    return (farPlane+BASIN_NEAR)/(farPlane-BASIN_NEAR)
           - (2.0*farPlane*BASIN_NEAR)/((farPlane-BASIN_NEAR)*max(distance,0.00001));
}
vec4 basinClip(vec3 world) {
    vec3 view=sceneOrbitPoint(world,uView,vec3(0.0,0.0,-0.5*SHOCKWAVE_DEPTH),vec3(0.0));
    float distance=uCamera-view.z;
    float w=distance/uCamera;
    vec2 centre=uField.xy+0.5*uField.zw;
    vec2 basePosition=centre+vec2(0.0,uField.w*(uFit.y-0.5)*uScenePose.x)
               +uScenePose.yz*uField.zw;
    vec2 numerator=vec2(view.x,-view.y)*uFit.x*uField.w*uScenePose.x;
    vec4 clip=uMatrix*vec4(basePosition*w+numerator,0.0,w);
    float farPlane=basinFar();
    clip.z=((farPlane+BASIN_NEAR)*distance-2.0*farPlane*BASIN_NEAR)
           /((farPlane-BASIN_NEAR)*uCamera);
    return clip;
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
uniform int uMarks; // surface or unique displaced vertices
uniform int uDepthOnly; // shared surface depth prepass for celestial transmission
uniform float uPointPx;
// The artist owns only 0..1. Continue that exact boundary into deterministic
// land rather than indefinitely clamping a last row of hills (or water).
float basinOutside(vec2 uv) {
    return length(uv-clamp(uv,vec2(0.0),vec2(1.0)));
}
float basinContinuation(vec2 uv) {
    vec2 edge=clamp(uv,vec2(0.0),vec2(1.0));
    vec2 delta=uv-edge;
    float distance=length(delta);
    float boundary=sceneHeightfield(uTerrain,uTerrainSize,edge);
    if (distance<1e-6) return boundary;
    vec2 inward=clamp(edge-sign(delta)/float(uTerrainSize-1),vec2(0.0),vec2(1.0));
    float interior=sceneHeightfield(uTerrain,uTerrainSize,inward);
    // Continue the local edge derivative only in a thin transition strip.
    // Retaining the last border height indefinitely made tall ridges look like
    // mountain-shaped extrusion running to the end of the world.
    float slope=clamp((boundary-interior)*float(uTerrainSize-1),-0.8,0.8);
    float nearSlope=0.20*slope*min(distance,0.16);
    float descent=smoothstep(0.04,0.68,distance);
    // A broad, low rolling *landform*, not the infinitely extruded editor
    // border or a perfectly flat far plane. Gentle undulations give the
    // accepted depth-tested skyline a natural distant silhouette.
    float backgroundHeight=0.12+0.065*sin(2.7*uv.x+1.7*uv.y)
                            *cos(2.4*uv.y-0.8*uv.x)
                            +0.040*sin(1.1*uv.y-2.3*uv.x);
    // The boundary and its derivative are exact at distance zero; well away
    // from it the surface turns into subdued rolling ground, never a wall.
    return max(0.025,mix(boundary+nearSlope,backgroundHeight,descent));
}
float basinBase(vec2 uv) {
    return basinOutside(uv)<1e-6 ? sceneHeightfield(uTerrain,uTerrainSize,uv)
                                 : basinContinuation(uv);
}
float basinCurve(vec2 uv) {
    if (basinOutside(uv)<1e-6) return sceneHeightfieldCurve(uTerrain,uTerrainSize,uv);
    vec2 edge=clamp(uv,vec2(0.0),vec2(1.0));
    // Exactly continuous with the cubic surface at the editor boundary.
    float boundary=sceneHeightfieldCurve(uTerrain,uTerrainSize,edge);
    return max(0.0,boundary+basinContinuation(uv)-sceneHeightfield(uTerrain,uTerrainSize,edge));
}
float basinDistanceFade(vec2 uv) {
    // The final mesh boundary is invisible. Colour and emission fade together.
    // Fade the camera-facing skirt before it approaches the near plane, too.
    float radial=1.0-smoothstep(0.95,1.90,basinOutside(uv));
    float foreground=1.0-smoothstep(0.87,1.30,max(0.0,-uv.y));
    return radial*foreground;
}
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
float basinGrowth(vec2 uv) {
    float f=clamp(uv.x*8.0-0.5,0.0,7.0);
    int i0=clamp(int(floor(f)),0,7),i1=min(i0+1,7);
    return mix(uTerrainGrowth[i0],uTerrainGrowth[i1],fract(f));
}
float basinLandHeight(vec2 uv,float base,float curved) {
    vec2 p=vec2((uv.x*2.0-1.0)*uHalfWidth,-uv.y*SHOCKWAVE_DEPTH);
    return curved*smoothstep(0.0,0.015,base)*uLand.x*(1.0+0.16*uLand.z*basinDetail(p))
           *(1.0+0.25*uLand.y*basinGrowth(uv));
}
vec3 basinSurface(vec2 uv, out float crest, out float energy, out float curved) {
    vec2 p = vec2((uv.x*2.0 - 1.0)*uHalfWidth, -uv.y*SHOCKWAVE_DEPTH);
    float base = basinBase(uv);
    float outer=basinOutside(uv);
    vec2 wave = outer<1e-6 ? shockwaveHeight(p) : vec2(0.0);
    crest = min(wave.y, 2.5);
    energy = basinEnergy(uv)*(1.0-smoothstep(0.0,0.55,outer));
    float height;
    curved=0.0;
    if (sceneHeightfieldWater(base)) {
        float bank=smoothstep(0.0,uWaterBankBand,sceneHeightfieldBankDistance(uTerrain,uTerrainSize,uv));
        height = bank*(0.18*tanh(wave.x/0.18) + 0.0025*uWaterDetail*sin(15.0*p.x + 18.0*p.y + uTime));
    } else {
        curved=basinCurve(uv);
        height = basinLandHeight(uv,base,curved);
    }
    return vec3(p.x, height, p.y);
}
"""

_BODY_VISIBILITY = f"""
vec4 basinVisibleBody(vec3 eye,vec3 ray,out vec3 hitPoint) {{
    vec4 body=basinCelestial(eye,ray,hitPoint);
    if (body.a>0.0) {{
        vec2 uv=vec2(hitPoint.x/(2.0*uHalfWidth)+0.5,-hitPoint.z/SHOCKWAVE_DEPTH);
        if (uv.x>=0.0 && uv.x<=1.0 && uv.y>=0.0 && uv.y<=1.0) {{
            float base=basinBase(uv);
            if (!sceneHeightfieldWater(base) && hitPoint.y<=basinLandHeight(uv,base,sceneHeightfieldCurve(uTerrain,uTerrainSize,uv)))
                body=vec4(0.0);
        }}
    }}
    return body;
}}
vec3 basinVisibleSkyRadiance(vec3 eye,vec3 ray) {{
    vec3 hitPoint;
    vec4 body=basinVisibleBody(eye,ray,hitPoint);
    float starVisibility=1.0-basinCelestialSkyMask(eye,ray);
    return basinCompositeSkyBody(basinSkyBackground(ray,starVisibility),body);
}}
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
out vec3 vSurfaceNormal;
uniform int uSmoothGlass;
void main() {
    vec3 world = basinSurface(aUv, vCrest, vEnergy, vCurvedBase);
    vSurfaceNormal=vec3(0.0,1.0,0.0);
    if (uSmoothGlass==1 && uPass==1 && uMarks==0 && uDepthOnly==0) {
        // Central derivatives of the very same displaced surface, evaluated
        // only for glass. Interpolation removes per-triangle highlight steps;
        // water, shore taper, cubic land and growth retain one height owner.
        float step=0.25/float(uTerrainSize-1);
        float crest,energy,curved;
        vec3 dx=basinSurface(aUv+vec2(step,0.0),crest,energy,curved)
               -basinSurface(aUv-vec2(step,0.0),crest,energy,curved);
        vec3 dz=basinSurface(aUv+vec2(0.0,step),crest,energy,curved)
               -basinSurface(aUv-vec2(0.0,step),crest,energy,curved);
        vSurfaceNormal=normalize(cross(dx,dz));
    }
    if (uPass == 0) {
        world.y = -world.y;
        world.x += (0.015+0.035*min(abs(world.y),1.0))*uWaterDetail
                   *sin(world.z*65.0+uTime*0.45);
    }
    vWorld = world;
    vUv = aUv;
    vec4 clip = basinClip(world);
    if (uMarks == 1) clip.z -= 0.0001*clip.w;
    gl_PointSize=uPointPx;
    gl_Position = clip;
}
"""
)

NEON_FRAGMENT_SOURCE = (
    "#version 460 core\nlayout(location=0) out vec4 FragColor;\nlayout(location=1) out vec4 Emission;\n"
    + SHOCKWAVE_EVENTS.glsl(3) + SCENE3D_GLSL + SCENE3D_ORBIT_GLSL + HEIGHTFIELD_VOLUME_GLSL + HEIGHTFIELD_WIRE_GLSL + _PROJECTION + SHOCKWAVE_WAVE_GLSL + _POSE + _TERRAIN + NEON_CELESTIAL_GLSL + _BODY_VISIBILITY
    + """
in vec3 vWorld;
in vec2 vUv;
in float vCrest;
in float vEnergy;
in float vCurvedBase;
in vec3 vSurfaceNormal;
uniform vec4 uLineColor;
uniform vec4 uCrestColor;
uniform vec4 uWaterColor;
uniform float uReflection;
uniform float uScroll;
uniform float uFloor;
uniform float uGlow;
uniform float uEdgePx;
uniform float uCurveCells;
uniform int uWireDisplay; // edge, point and glass bits
uniform vec4 uTerrainFillColor;
uniform vec4 uVertexColor;
uniform vec4 uVertexAccentColor;
uniform vec4 uVertexOutlineColor;
uniform vec4 uGlassTint;
uniform vec2 uGlass; // strength, roughness
uniform float uLightStrength;
vec4 sceneEmission(vec3 rgb) { return vec4(rgb, dot(rgb, vec3(0.2126,0.7152,0.0722))); }
void main() {
    float distanceFade=basinDistanceFade(vUv);
    if (distanceFade<0.001) discard;
    if (uDepthOnly==1) {
        // Sky has already been drawn. Erase its premultiplied radiance by
        // precisely the surface's fading coverage, while writing real depth.
        // The renderer sets a temporary destination-only blend for this pass.
        FragColor=vec4(0.0,0.0,0.0,distanceFade);
        Emission=vec4(0.0);
        return;
    }
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
    if (uMarks == 1) {
        float radius=length(gl_PointCoord-0.5);
        float coverage=1.0-smoothstep(0.25,0.5,radius);
        if ((uWireDisplay&4)!=0) coverage*=smoothstep(0.18,0.28,radius);
        if (coverage<0.01) discard;
        vec4 pointColour=mix(uVertexColor,uVertexAccentColor,clamp(water ? vCrest*0.6 :
                         0.45+0.35*sin(vWorld.x*3.0+vWorld.z*2.0)+base*0.25,0.0,1.0));
        if ((uWireDisplay&4)!=0) pointColour=uVertexOutlineColor;
        vec3 palette=pointColour.rgb;
        float gain=water ? 0.65+0.4*vCrest : 0.65+vEnergy*clamp(base+0.15,0.0,1.0);
        if (uPass==0) coverage*=uReflection*0.55*exp(-abs(vWorld.y)*1.5)
                           *smoothstep(-0.5,0.6,sin(reflectionPlane.z*95.0+uTime*0.4));
        float alpha=coverage*pointColour.a*distanceFade;
        FragColor=vec4(min(palette*gain,vec3(1.0)),alpha);
        Emission=sceneEmission(palette*gain*alpha*uGlow);
        return;
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
    float glassWeight=(uWireDisplay&4)!=0 ? uGlass.x*uGlassTint.a : 0.0;
    vec3 n = glassWeight>0.0 ? normalize(vSurfaceNormal) : normalize(cross(dFdx(vWorld),dFdy(vWorld)));
    float light = 0.3 + 0.7*abs(dot(n,normalize(vec3(-0.4,1.0,0.5))));
    vec3 waterFill=uWaterColor.rgb*(0.60+0.10*light);
    vec3 landFill=uTerrainFillColor.rgb+palette*(0.025+0.055*light);
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
    // General land/water mesh wires are retired, but independently composed
    // travelling water accents remain. The lake perimeter is separate below.
    if (!water) line=0.0;
    if (uPass == 0) {
        // Reflection has no land fill. Broken horizontal water bands split
        // the mirrored wires into trails instead of accumulated opaque slabs.
        vec2 p=reflectionPlane.xz;
        float ripple=sin(p.y*65.0 + p.x*3.0 + uTime*0.45)
                    + 0.45*sin(p.y*117.0-p.x*11.0-uTime*0.23);
        float breakup=mix(0.02,1.0,smoothstep(0.0,0.8,ripple));
        float decay=exp(-abs(vWorld.y)*1.5);
        float alpha=max(line*uLineColor.a,shoreLight*uCrestColor.a)*uReflection*0.85*breakup*decay*distanceFade;
        if (alpha < 0.002) discard;
        vec3 reflected=wire*1.6+palette*shoreLight;
        FragColor=vec4(reflected,alpha);
        Emission=sceneEmission(reflected*alpha*uGlow*0.45);
        return;
    }
    // The original event crest illuminates curved water detail. Keep troughs
    // dark instead of covering each crest with an opaque luminous sheet.
    float ring = water ? clamp(crest*0.08,0.0,0.20) : 0.0;
    vec3 eye=basinUnview(vec3(0.0,0.0,uCamera))+vec3(0.0,0.0,-0.5*SHOCKWAVE_DEPTH);
    vec3 view=normalize(eye-vWorld);
    n=faceforward(n,-view,n);
    vec4 bodyColour=uBodyKind==0 ? uSunColor : uMoonColor;
    vec3 toBody=normalize(uBodyPosition-vWorld);
    bool bodyLight=uSunEnabled==1 && (uLightStrength>0.0 || glassWeight>0.0)
                   && !sceneHeightfieldVolumeLightOccluded(uTerrain,uTerrainSize,vWorld+vec3(0.0,0.005,0.0),
                                                          uBodyPosition,uHalfWidth,SHOCKWAVE_DEPTH,uLand.x/1.25);
    if (bodyLight && uLightStrength>0.0) {
        fill+=bodyColour.rgb*bodyColour.a*uLightStrength*max(dot(n,toBody),0.0)*0.32;
    }
    float fillAlpha=uFloor*(water ? uWaterColor.a*0.55 : uTerrainFillColor.a);
    if (glassWeight>0.0) {
        float roughness=clamp(uGlass.y,0.045,0.5);
        SceneMaterial material=SceneMaterial(uGlassTint.rgb,roughness,0.0,0.5,vec3(0.0));
        vec3 reflected=reflect(-view,n);
        vec3 environment=basinVisibleSkyRadiance(vWorld,reflected);
        vec3 tangent=normalize(cross(reflected,abs(reflected.y)<0.9 ? vec3(0.0,1.0,0.0) : vec3(1.0,0.0,0.0)));
        vec3 bitangent=cross(reflected,tangent);
        environment=(environment*2.0+basinVisibleSkyRadiance(vWorld,normalize(reflected+tangent*roughness))
                     +basinVisibleSkyRadiance(vWorld,normalize(reflected-tangent*roughness))
                     +basinVisibleSkyRadiance(vWorld,normalize(reflected+bitangent*roughness))
                     +basinVisibleSkyRadiance(vWorld,normalize(reflected-bitangent*roughness)))/6.0;
        // Emissive neon sky is a lighting source: retain dark face interiors
        // while the shared Fresnel response exposes continuous grazing curves.
        vec3 glass=uGlassTint.rgb*0.035+environment*3.0*sceneEnvironmentBrdf(sceneMaterialF0(material),roughness,max(dot(n,view),1e-4));
        if (bodyLight) glass+=sceneBrdfLight(material,n,view,toBody,bodyColour.rgb*bodyColour.a*0.7);
        fill=mix(fill,glass,glassWeight);
        fillAlpha=max(fillAlpha,glassWeight*0.85);
    }
    // Emphasise camera-facing, high-land tangencies without drawing the
    // tessellation or internal wire edges. The previous 0.015..0.075 band
    // vanished entirely at practical raster resolutions in vertex styles.
    // This is still a surface-rim approximation, NOT a depth-derived exact
    // No normal/grazing skyline approximation: it lit broad internal slopes,
    // not the visible terrain/sky boundary. Skyline now has its own thin pass.
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
    FragColor=vec4(min(premult/max(alpha,1e-4),vec3(1.0)),alpha*distanceFade);
    Emission=sceneEmission((wire*lineAlpha + palette*ringAlpha*0.45+shoreColour*shoreAlpha
                           +fill*fillAlpha*glassWeight*0.12)*uGlow*distanceFade);
}
"""
)

# Screen-space silhouette of the real displaced terrain. Draw the SAME triangle
# lattice shifted up just over one physical pixel, slightly farther in depth.
# The existing terrain depth hides all interior fragments. No projected-column
# max and no separate guessed mountain topology; output only where land meets sky.
NEON_SKYLINE_VERTEX_SOURCE = (
    "#version 460 core\nlayout(location=0) in vec2 aUv;\n"
    + SHOCKWAVE_EVENTS.glsl(3) + SCENE3D_ORBIT_GLSL + HEIGHTFIELD_GLSL
    + _PROJECTION + SHOCKWAVE_WAVE_GLSL + _POSE + _TERRAIN
    + """
out vec2 vUv;
out float vContourFade;
out float vTerrainBase;
uniform float uOutlineLiftNdc; // physical-pixel lift, supplied by renderer viewport
void main() {
    float crest, energy, curved;
    float base=basinBase(aUv);
    float smoothed=basinCurve(aUv);
    vec3 world=vec3((aUv.x*2.0-1.0)*uHalfWidth,
                    base>0.025 ? basinLandHeight(aUv,base,smoothed) : 0.0,
                    -aUv.y*SHOCKWAVE_DEPTH);
    vec4 clip=basinClip(world);
    clip.y+=uOutlineLiftNdc*clip.w;
    clip.z+=0.0012*clip.w; // farther than the original surface, never an internal paint layer
    gl_Position=clip;
    vUv=aUv;
    vTerrainBase=base;
    // The only skyline is the visible, displaced terrain itself. Exactly
    // share its outer coverage: resurrecting faded mesh with a distant
    // radiance floor drew disconnected straight stripes above the horizon.
    vContourFade=basinDistanceFade(aUv);
}
"""
)
NEON_SKYLINE_FRAGMENT_SOURCE = (
    "#version 460 core\nlayout(location=0) out vec4 FragColor;\nlayout(location=1) out vec4 Emission;\n"
    + HEIGHTFIELD_GLSL
    + """
in vec2 vUv;
in float vContourFade;
in float vTerrainBase;
uniform sampler2D uTerrain;
uniform int uTerrainSize;
uniform vec4 uCrestColor;
uniform float uGlow;
uniform float uMidband;
void main() {
    // Water boundary is handled by its own existing shoreline, not this pass.
    // The border extension must use its true continued land classification,
    // not a clamp to an unrelated authored edge row.
    if (vTerrainBase<0.035 || vContourFade<0.005) discard;
    float alpha=uCrestColor.a*vContourFade;
    vec3 colour=min(uCrestColor.rgb*(0.78+0.16*clamp(uMidband,0.0,1.0)),vec3(1.0));
    FragColor=vec4(colour,alpha);
    vec3 emission=colour*alpha*(0.45+0.4*uGlow);
    Emission=vec4(emission,dot(emission,vec3(0.2126,0.7152,0.0722)));
}
"""
)

NEON_SKY_VERTEX_SOURCE = """#version 460 core
layout(location=0) in vec2 aUv;
out vec2 vUv;
uniform mat4 uMatrix;
uniform vec4 uField;
void main() {
    vUv=aUv;
    gl_Position=uMatrix*vec4(uField.xy+aUv*uField.zw,0.999,1.0);
}
"""
NEON_SKY_FRAGMENT_SOURCE = (
    "#version 460 core\nlayout(location=0) out vec4 FragColor;\nlayout(location=1) out vec4 Emission;\n"
    + SHOCKWAVE_EVENTS.glsl(3) + SCENE3D_ORBIT_GLSL + _PROJECTION + SHOCKWAVE_WAVE_GLSL + _POSE
    + HEIGHTFIELD_VOLUME_GLSL + _TERRAIN + NEON_CELESTIAL_GLSL + _BODY_VISIBILITY
    + """
in vec2 vUv;
uniform int uSkyPass; // 0 background, 1 optional volume, 2 depth-tested body
uniform float uLandHeight;
uniform float uVolumeStrength;
uniform vec4 uVolumeColour;
uniform int uVolumeSteps;
uniform float uMidband; // existing spectrum midband, no new DSP owner
uniform float uBeatPulse;
uniform vec2 uCelestialGlow; // brightness, musical response
void main() {
    vec2 item=uField.xy+vUv*uField.zw;
    vec2 centre=uField.xy+0.5*uField.zw;
    item=centre+(item-centre-uScenePose.yz*uField.zw)/uScenePose.x;
    vec2 screen=vec2((item.x-centre.x)/(uFit.x*uField.w),
                    (uFit.y-(item.y-uField.y)/uField.w)/uFit.x);
    vec3 ray=normalize(basinUnview(vec3(screen,-uCamera)));
    vec3 eye=basinUnview(vec3(0.0,0.0,uCamera))+vec3(0.0,0.0,-0.5*SHOCKWAVE_DEPTH);
    if (uSkyPass==1) {
        vec4 volume=sceneHeightfieldVolume(uBodyPosition,eye,ray,uHalfWidth,SHOCKWAVE_DEPTH,uLandHeight,
                                          uTerrain,uTerrainSize,uVolumeColour,0.45,0.35,uVolumeStrength,uVolumeSteps);
        if (volume.a<0.0001) discard;
        FragColor=vec4(volume.rgb/volume.a,volume.a);
        vec3 emission=volume.rgb*0.12;
        Emission=vec4(emission,dot(emission,vec3(0.2126,0.7152,0.0722)));
        return;
    }
    if (uSkyPass==2) {
        // When the orbit brings the sphere close to (or around) the camera,
        // its enormous apparent disc must not wash out the whole card.
        // Preserve full orbital position and all lighting/reflection queries;
        // only the camera's visible-body pass is attenuated.
        float cameraCoverage=basinCameraBodyCoverage(length(eye-uBodyPosition),uBodySize);
        if (cameraCoverage<=0.0001) discard;
        vec3 bodyPoint;
        vec4 body=basinVisibleBody(eye,ray,bodyPoint);
        body.a*=cameraCoverage;
        vec3 centre=uBodyPosition-eye;
        float separation=length(centre);
        vec3 forward=centre/max(separation,1e-5);
        float facing=dot(ray,forward);
        float radius=uBodySize/max(separation,1e-5);
        // Analytic screen-angular corona OUTSIDE the sphere. It never creates
        // a second mesh or changes orbital body/light/reflection ownership.
        float normalizedAngle=length(cross(ray,forward))/max(facing*radius,1e-5);
        // Outer corona around the sphere silhouette. The Moon also gets a very
        // small same-colour lift just inside the illuminated rim, so the glow
        // reads as originating from the body rather than a detached tube.
        float halo=(smoothstep(0.992,1.040,normalizedAngle)
                   * (1.0-smoothstep(1.032,1.210,normalizedAngle)));
        halo*=step(0.0,facing)*cameraCoverage;
        vec4 bodyColour=(uBodyKind==0 ? uSunColor : uMoonColor);
        float response=pow(clamp(0.22*uMidband+1.35*uBeatPulse,0.0,1.0),0.78);
        float haloGain=uCelestialGlow.x*(0.54+0.92*clamp(uCelestialGlow.y*response*1.18,0.0,1.0));
        float moonRimLight=(uBodyKind==1 && halo>0.0)
                           ? basinMoonRimIllumination(eye,ray) : 1.0;
        float haloAlpha=(uBodyKind==1)
                        ? 0.26*bodyColour.a*haloGain*halo*moonRimLight
                        : 0.23*bodyColour.a*haloGain*halo;
        float litInnerRim=0.0;
        float innerHaloAlpha=0.0;
        if (uBodyKind==1 && body.a>0.0001 && uCelestialGlow.x>0.0) {
            litInnerRim=basinMoonInnerRimEmission(eye,bodyPoint);
            innerHaloAlpha=0.115*bodyColour.a*haloGain*litInnerRim*body.a;
        }
        float alpha=body.a+haloAlpha*(1.0-body.a);
        if (alpha<0.0001) discard;
        vec3 premult=body.rgb*body.a
                    +bodyColour.rgb*(innerHaloAlpha+haloAlpha*(1.0-body.a));
        vec3 colour=premult/max(alpha,1e-5);
        FragColor=vec4(min(colour,vec3(1.0)),alpha);
        // Sun retains strong emission. The Moon emits only from a narrow band
        // of the visible lit rim and the feathered corona immediately outside.
        vec3 emission;
        if (uBodyKind==1) {
            emission=bodyColour.rgb*(0.12*innerHaloAlpha + 0.28*haloAlpha*(1.0-body.a));
        } else {
            emission=(body.rgb*body.a
                     +bodyColour.rgb*haloAlpha*(1.0-body.a))*0.20;
        }
        Emission=vec4(emission,dot(emission,vec3(0.2126,0.7152,0.0722)));
        vec3 position=body.a>0.0001 ? bodyPoint : uBodyPosition;
        gl_FragDepth=clamp(0.5+0.5*basinDepthNdc(sceneOrbitPoint(position,uView,
                     vec3(0.0,0.0,-0.5*SHOCKWAVE_DEPTH),vec3(0.0)).z),0.0,1.0);
    } else {
        // One celestial coverage evaluation for ordinary stars AND the
        // independent beat-star emission attachment. No duplicate ray hits.
        float starVisibility=1.0-basinCelestialSkyMask(eye,ray);
        FragColor=basinSkyBackground(ray,starVisibility);
        if (FragColor.a<0.0001) discard;
        // Separate small radiance buffer entry for event stars, not the entire
        // sky (which would turn on widespread bloom and flatten the scene).
        vec3 sparkle=uStarColor.rgb*uStarColor.a*basinBeatStarLight(ray,uStarGlow)*starVisibility*0.95;
        Emission=vec4(sparkle,dot(sparkle,vec3(0.2126,0.7152,0.0722)));
        gl_FragDepth=0.999999;
    }
}
"""
)

__all__ = ["basin_camera", "basin_fit", "basin_bounds", "basin_project", "basin_item_point", "NEON_VERTEX_SOURCE", "NEON_FRAGMENT_SOURCE",
           "NEON_SKY_VERTEX_SOURCE", "NEON_SKY_FRAGMENT_SOURCE", "NEON_SKYLINE_VERTEX_SOURCE", "NEON_SKYLINE_FRAGMENT_SOURCE"]
