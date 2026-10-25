"""Framed basin projection and terrain/water shaders over shared Scene3D owners.

Authored base height alone classifies water. Its travelling waves join the visible
shore through the shallow fringe; dry land retains its independent bounded lift.
The view is the shared framed physical camera (``core.settings.framed_camera``): orbit, dolly, pan and
flight move a real eye over the land; audio cannot change framing or target sizing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from core.constants.neon_lake_world import WATER_PEAK
from rendering.gl_programs.heightfield_glsl import HEIGHTFIELD_GLSL, HEIGHTFIELD_WIRE_GLSL
from rendering.gl_programs.heightfield_volume_glsl import HEIGHTFIELD_VOLUME_GLSL
from rendering.gl_programs.heightfield_glsl import HEIGHTFIELD_GLSL as _SKY_HEIGHTFIELD_GLSL
from rendering.gl_programs.neon_celestial import NEON_CELESTIAL_GLSL
from rendering.gl_programs.neon_terrain_reaction import REACTION_GLSL
from rendering.gl_programs.scene3d import SCENE3D_GLSL, SCENE3D_ORBIT_GLSL
from rendering.gl_programs.shockwave_grid_program import (
    SHOCKWAVE_DEPTH, SHOCKWAVE_EVENTS, SHOCKWAVE_MAX_BARS, SHOCKWAVE_WAVE_GLSL, shockwave_half_width,
)



def basin_pixel_scale(matrix, viewport) -> float:
    """Physical pixels per item unit, from Quick's actual affine item transform.

    The viewport belongs to the whole window, not the framed card. Dividing
    that window's width by the card width makes marks grow as a card shrinks.
    Area scale also preserves uniform marks under a rotated item transform.
    """
    determinant = matrix[0] * matrix[5] - matrix[1] * matrix[4]
    return math.sqrt(abs(determinant) * viewport[2] * viewport[3]) / (2.0 * abs(matrix[15]))


@dataclass(frozen=True, slots=True)
class BasinView:
    """One frame's physical camera (the shared framed-camera standard) on the card's interior ``field``."""
    eye: tuple[float, float, float]
    right: tuple[float, float, float]
    up: tuple[float, float, float]
    back: tuple[float, float, float]
    tan: tuple[float, float]
    field: tuple[float, float, float, float]

    def view(self, point) -> tuple[float, float, float]:
        rel = tuple(p - e for p, e in zip(point, self.eye))
        return tuple(sum(a * b for a, b in zip(rel, axis)) for axis in (self.right, self.up, self.back))

    def depth(self, point) -> float:
        return -self.view(point)[2]

    def item_point(self, point) -> tuple[float, float]:
        """CPU mirror of basinItem (callers check ``depth`` first for points behind the eye)."""
        x, y, z = self.view(point)
        depth = max(-z, 1e-6)
        fx, fy, width, height = self.field
        return (fx + 0.5 * width + 0.5 * width * x / (depth * self.tan[0]),
                fy + 0.5 * height - 0.5 * height * y / (depth * self.tan[1]))

    def ray(self, u: float, v: float) -> tuple[float, float, float]:
        """World direction through card interior UV (v down), as the sky shader casts it."""
        nx, ny = (2.0 * u - 1.0) * self.tan[0], (1.0 - 2.0 * v) * self.tan[1]
        d = tuple(nx * r + ny * up - b for r, up, b in zip(self.right, self.up, self.back))
        norm = math.sqrt(sum(c * c for c in d))
        return tuple(c / norm for c in d)


def orbit_view(turn: float, tilt: float, field=(0.0, 0.0, 1800.0, 1000.0), *, scale: float = 1.0,
               pan=(0.0, 0.0), fov: float = 30.0, position=(0.0, 0.0, 0.0)) -> BasinView:
    """A view from settings-unit pose values with no terrain floor (tools and contracts)."""
    from core.settings import framed_camera as fc
    from core.settings.neon_lake_camera import SPEC
    axes = fc.camera_axes(SPEC, turn, tilt)
    eye, _offset = fc.resolve_camera_position(SPEC, turn, tilt, scale, pan[0], pan[1], fov, position, axes=axes)
    tan_y = fc.tan_half_fov(fov, SPEC.fov_range)
    return BasinView(eye, axes[:3], axes[3:6], axes[6:9], (tan_y * field[2] / field[3], tan_y), tuple(field))


def basin_view(parameters, field) -> BasinView:
    """The frame's eye from the shared camera, bounded over the card's exact terrain width."""
    from core.settings import framed_camera as fc
    from core.settings.neon_lake_camera import SPEC, floor_reaction, terrain_floor

    def get(name):
        return parameters["shockwave_grid_" + name]
    aspect = field[2] / field[3]
    turn, tilt, fov = float(get("turn")), float(get("tilt")), float(get("camera_fov"))
    axes = fc.camera_axes(SPEC, turn, tilt)
    eye, _offset = fc.resolve_camera_position(
        SPEC, turn, tilt, float(get("scene_scale")), float(get("scene_pan_x")), float(get("scene_pan_y")), fov,
        get("camera_position"), None,
        terrain_floor(get("terrain"), float(get("terrain_height")), shockwave_half_width(aspect),
                      floor_reaction(parameters)), axes=axes)
    tan_y = fc.tan_half_fov(fov, SPEC.fov_range)
    return BasinView(eye, axes[:3], axes[3:6], axes[6:9], (tan_y * aspect, tan_y), tuple(field))




# The authored grid may reach past the basin toward the horizon: grid uv = (basin uv + xy) * z.
# Every distance and constant in these shaders is in basin uv; only heightfield reads convert.
# A program that never sets the uniform sees the identity (an unextended grid).
_GRID_GLSL = """
uniform vec3 uTerrainGrid = vec3(0.0, 0.0, 1.0);
vec2 basinGrid(vec2 uv) { return (uv + uTerrainGrid.xy) * uTerrainGrid.z; }
#define SCENE_HEIGHTFIELD_GRID(uv) basinGrid(uv)
// Distance outside the authored grid, in basin uv (0 on it).
float basinOutside(vec2 uv) {
    vec2 grid = basinGrid(uv);
    return length(grid - clamp(grid, vec2(0.0), vec2(1.0))) / uTerrainGrid.z;
}
"""

_PROJECTION = _GRID_GLSL + f"""
const float SHOCKWAVE_DEPTH = {SHOCKWAVE_DEPTH:.6f};
const float WATER_PEAK = {WATER_PEAK:.6f};
uniform mat4 uMatrix;
uniform vec4 uField;
// The shared framed physical camera (core.settings.framed_camera): eye and right/up/back world axes,
// and tan of the half field of view on x and y.
uniform vec3 uEye;
uniform vec3 uRight;
uniform vec3 uUp;
uniform vec3 uBack;
uniform vec2 uTan;
uniform float uHalfWidth;
uniform float uHorizon;
uniform int uBarCount;
uniform float uBars[{SHOCKWAVE_MAX_BARS}];
uniform float uHeightScale;
"""
_POSE = """
vec3 basinViewPoint(vec3 world) {
    vec3 rel = world - uEye;
    return vec3(dot(rel, uRight), dot(rel, uUp), dot(rel, uBack));
}
vec2 basinItem(vec3 world) {
    vec3 v = basinViewPoint(world);
    float depth = max(-v.z, 1e-6);
    return uField.xy + 0.5 * uField.zw + 0.5 * uField.zw * vec2(v.x / (depth * uTan.x), -v.y / (depth * uTan.y));
}
vec3 basinUnview(vec3 v) {
    return v.x * uRight + v.y * uUp + v.z * uBack;
}
// True homogeneous camera projection for the overscanned landscape: keep the numerator
// linear in view position and let GL clip at the near plane (flattening to pixel XY
// before clipping divides by negative/near-zero depths and produces giant sheets).
const float BASIN_NEAR = 0.04;
float basinFar() { return 60.0; }
vec4 basinClip(vec3 world) {
    vec3 v = basinViewPoint(world);
    float depth = -v.z;
    vec2 centre = uField.xy + 0.5 * uField.zw;
    vec2 numerator = 0.5 * uField.zw * vec2(v.x / uTan.x, -v.y / uTan.y);
    vec4 clip = uMatrix * vec4(centre * depth + numerator, 0.0, depth);
    float farPlane = basinFar();
    clip.z = ((farPlane + BASIN_NEAR) * depth - 2.0 * farPlane * BASIN_NEAR) / (farPlane - BASIN_NEAR);
    return clip;
}
"""

_SHORE_HEIGHT_GLSL = """
#ifndef BASIN_SHORE_HEIGHT
#define BASIN_SHORE_HEIGHT 0.018
#endif
"""

_TERRAIN = _SHORE_HEIGHT_GLSL + REACTION_GLSL + """
uniform sampler2D uTerrain;
uniform int uTerrainSize;
uniform vec2 uLand; // height, static detail
uniform float uTime;
uniform float uWaterDetail;
uniform float uWaterBankBand;
uniform int uPass; // 0 reflected land, 1 complete surface
uniform int uMarks; // surface or unique displaced vertices
uniform int uDepthOnly; // shared surface depth prepass for celestial transmission
uniform float uPointPx;
// The artist owns only 0..1. Continue that exact boundary into deterministic
// land rather than indefinitely clamping a last row of hills (or water).
float basinContinuation(vec2 uv) {
    vec2 grid=basinGrid(uv);
    vec2 edge=clamp(grid,vec2(0.0),vec2(1.0));
    vec2 delta=grid-edge;
    float distance=length(delta)/uTerrainGrid.z;
    float boundary=sceneHeightfield(uTerrain,uTerrainSize,edge);
    if (distance<1e-6) return boundary;
    // Water reaching the grid's edge keeps flowing outward to the horizon (a painted stream or coast),
    // never stopping at a wall of rolling land; dry edges roll away as before.
    if (sceneHeightfieldWater(boundary)) return 0.0;
    vec2 inward=clamp(edge-sign(delta)/float(uTerrainSize-1),vec2(0.0),vec2(1.0));
    float interior=sceneHeightfield(uTerrain,uTerrainSize,inward);
    // Continue the local edge derivative only in a thin transition strip.
    // Retaining the last border height indefinitely made tall ridges look like
    // mountain-shaped extrusion running to the end of the world.
    float slope=clamp((boundary-interior)*float(uTerrainSize-1)*uTerrainGrid.z,-0.8,0.8);
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
    float rolling=max(0.025,mix(boundary+nearSlope,backgroundHeight,descent));
    return mix(rolling,0.065,smoothstep(1.1,2.2,distance));
}
float basinBase(vec2 uv) {
    return basinOutside(uv)<1e-6 ? sceneHeightfield(uTerrain,uTerrainSize,basinGrid(uv))
                                 : basinContinuation(uv);
}
float basinCurve(vec2 uv) {
    if (basinOutside(uv)<1e-6) return sceneHeightfieldCurve(uTerrain,uTerrainSize,basinGrid(uv));
    vec2 edge=clamp(basinGrid(uv),vec2(0.0),vec2(1.0));
    if (sceneHeightfieldWater(sceneHeightfield(uTerrain,uTerrainSize,edge))) return 0.0;
    // Exactly continuous with the cubic surface at the editor boundary.
    float boundary=sceneHeightfieldCurve(uTerrain,uTerrainSize,edge);
    float continued=max(0.0,boundary+basinContinuation(uv)-sceneHeightfield(uTerrain,uTerrainSize,edge));
    return mix(continued,0.065,smoothstep(1.1,2.2,basinOutside(uv)));
}
float basinDetailFade(vec2 uv) {
    return 1.0-smoothstep(0.95,1.90,basinOutside(uv));
}
float basinDistanceFade(vec2 uv) {
    // Distant LAND keeps coverage/depth to its real curved horizon. Only detail fades.
    // Retain the camera-facing skirt fade before near-plane clipping.
    float foreground=1.0-smoothstep(0.87,1.30,max(0.0,-uv.y));
    return foreground;
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
// The shallow convex distant world: everything past the authored basin's immediate continuation falls away
// toward a real horizon, water included (a stream carried on from the grid's edge stayed flat while the land
// beside it fell, and stood above it as a long raised causeway to the horizon).
float basinDistantDrop(vec2 uv) {
    float distance=max(0.0,basinOutside(uv)-0.20);
    return 0.38*distance*distance;
}
float basinLandHeight(vec2 uv,float base,float curved) {
    vec2 p=vec2((uv.x*2.0-1.0)*uHalfWidth,-uv.y*SHOCKWAVE_DEPTH);
    float height=curved*smoothstep(0.0,0.015,base)*uLand.x*(1.0+0.16*uLand.y*basinDetail(p));
    // Terrain Reaction reshapes the land by the music: zero at the shore, never below a floor
    // share of its authored height, faded with the distant continuation's detail.
    float land=smoothstep(0.0,0.08,base)*basinDetailFade(uv);
    height=max(height+uLand.x*basinReaction(uv,base,p,land),REACTION_FLOOR*height);
    // A shallow convex distant world produces a real terrain/sky tangency,
    // rather than an exposed remote mesh edge or an infinitely flat plane.
    // The authored basin and its immediate continuation are untouched.
    return height-basinDistantDrop(uv);
}
float basinBankDistance(vec2 uv) {
    // Stored distances are in grid uv; the band and the result are in basin uv.
    float cached=sceneHeightfieldBankDistance(uTerrain,uTerrainSize,basinGrid(uv))/uTerrainGrid.z;
    if (cached>=uWaterBankBand) return cached;
    // Interpolated conservative distances can be zero across an entire water
    // cell at a concave bank junction. Resolve only this narrow band against
    // the actual bilinear-positive support, not its expanded control samples.
    vec2 p=basinGrid(uv)*float(uTerrainSize-1);
    ivec2 cell=ivec2(floor(p));
    float distance=1.0;
    for (int y=-1;y<=2;++y) for (int x=-1;x<=2;++x) {
        ivec2 site=clamp(cell+ivec2(x,y),ivec2(0),ivec2(uTerrainSize-1));
        if (texelFetch(uTerrain,site,0).r>0.0) {
            vec2 delta=max(abs(p-vec2(site))-1.0,vec2(0.0));
            distance=min(distance,length(delta)/float(uTerrainSize-1));
        }
    }
    return distance/uTerrainGrid.z;
}
vec3 basinSurface(vec2 uv, out float crest, out float energy, out float curved) {
    vec2 p = vec2((uv.x*2.0 - 1.0)*uHalfWidth, -uv.y*SHOCKWAVE_DEPTH);
    float base = basinBase(uv);
    float outer=basinOutside(uv);
    // Waves travel on along a stream that leaves the grid as water, easing out toward the horizon.
    vec2 wave = outer<1e-6 || sceneHeightfieldWater(base)
              ? shockwaveHeight(p)*(1.0-smoothstep(0.6,2.4,outer)) : vec2(0.0);
    crest = min(wave.y, 2.5);
    energy = basinEnergy(uv)*(1.0-smoothstep(0.0,0.55,outer));
    float height;
    // The visible shoreline is the existing .018 cubic contour, beyond the
    // square bilinear-zero cells. Join waves through that already water-coloured
    // shallow fringe instead of stopping at a jagged control-cell boundary.
    // Deep water is farther than the cubic support, so needs no cubic sampling.
    bool water=sceneHeightfieldWater(base);
    curved=water && sceneHeightfieldBankDistance(uTerrain,uTerrainSize,basinGrid(uv))>=1.0/float(uTerrainSize-1)
           ? 0.0 : basinCurve(uv);
    float wet=outer<1e-6 ? 1.0-smoothstep(0.0,BASIN_SHORE_HEIGHT,curved) : 0.0;
    float ripple=WATER_PEAK*tanh(wave.x/WATER_PEAK)+0.0025*uWaterDetail*sin(15.0*p.x+18.0*p.y+uTime);
    if (water) {
        float bank=smoothstep(0.0,uWaterBankBand,basinBankDistance(uv));
        height = max(bank,wet)*ripple-basinDistantDrop(uv);
    } else {
        height = basinLandHeight(uv,base,curved)+wet*ripple;
    }
    return vec3(p.x, height, p.y);
}
"""

_BODY_VISIBILITY = f"""
vec4 basinVisibleBody(vec3 eye,vec3 ray,out vec3 hitPoint) {{
    vec4 body=basinCelestial(eye,ray,hitPoint);
    if (body.a>0.0) {{
        vec2 uv=vec2(hitPoint.x/(2.0*uHalfWidth)+0.5,-hitPoint.z/SHOCKWAVE_DEPTH);
        if (basinOutside(uv)<1e-6) {{
            float base=basinBase(uv);
            if (hitPoint.y<=(sceneHeightfieldWater(base) ? -basinDistantDrop(uv) : basinLandHeight(uv,base,basinCurve(uv))))
                body=vec4(0.0);
        }}
    }}
    return body;
}}
vec3 basinVisibleSkyRadiance(vec3 eye,vec3 ray) {{
    vec3 hitPoint;
    vec4 body=basinVisibleBody(eye,ray,hitPoint);
    float starVisibility=1.0-basinCelestialSkyMask(eye,ray);
    return basinCompositeSkyBody(basinSkyBackground(eye,ray,starVisibility,0),body);
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
        float step=0.25/(float(uTerrainSize-1)*uTerrainGrid.z);   // a quarter grid cell, in basin uv
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

_SHORELINE_GLSL = _SHORE_HEIGHT_GLSL + """
float basinShoreLight(vec2 uv, float base, float curved) {
    // Only the authored grid draws a shore line. The positive rolling land
    // outside it can cross the visual shore band without containing water.
    if (sceneHeightfieldWater(base) || basinOutside(uv)>1e-6) return 0.0;
    float distance=abs(curved-BASIN_SHORE_HEIGHT)/max(fwidth(curved),0.0001);
    return (1.0-smoothstep(0.45,1.15,distance))
           +0.12*exp(-pow(distance/2.8,2.0));
}
"""

_SURFACE_NORMAL_GLSL = """
vec3 basinSurfaceNormal(vec3 areaNormal) {
    // At a grazing/degenerate raster derivative the oriented area is zero.
    // normalize(0) is undefined: one NaN emission texel polluted every bloom
    // level. Its zero-area limit contributes no directional lighting.
    return areaNormal*inversesqrt(max(dot(areaNormal,areaNormal),1e-20));
}
"""

NEON_FRAGMENT_SOURCE = (
    "#version 460 core\nlayout(location=0) out vec4 FragColor;\nlayout(location=1) out vec4 Emission;\n"
    + SHOCKWAVE_EVENTS.glsl(3) + SCENE3D_GLSL + SCENE3D_ORBIT_GLSL + HEIGHTFIELD_WIRE_GLSL + _PROJECTION + HEIGHTFIELD_VOLUME_GLSL + SHOCKWAVE_WAVE_GLSL + _POSE + _TERRAIN + NEON_CELESTIAL_GLSL + _BODY_VISIBILITY + _SHORELINE_GLSL + _SURFACE_NORMAL_GLSL
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
uniform vec4 uWaterLineGlowColor; // the water lines' glow colour; alpha mixes it in over their ripple palette
uniform float uWaterLineGlow;     // their glow, relative to the shared surface glow
uniform float uWaterShine;        // the water's own surface: tinted body with a rippled mirror of the sky
vec4 sceneEmission(vec3 rgb) { return vec4(rgb, dot(rgb, vec3(0.2126,0.7152,0.0722))); }
void main() {
    float detailFade=basinDetailFade(vUv);
    float distanceFade=basinDistanceFade(vUv);
    if (distanceFade<0.001) discard;
    if (uDepthOnly==1) {
        // Sky has already been drawn. Erase its premultiplied radiance by
        // precisely the surface's fading coverage, while writing real depth.
        // The renderer sets a temporary destination-only blend for this pass.
        FragColor=vec4(0.0,0.0,0.0,distanceFade);
        Emission=vec4(0.0,0.0,0.0,distanceFade);
        return;
    }
    // Classification is sampled again at the fragment: interpolated displaced
    // heights cannot turn land into water or move a shore during a beat.
    float base = basinBase(vUv);
    bool water = sceneHeightfieldWater(base);
    vec3 reflectionPlane=vec3(0.0);
    if (uPass == 0) {
        if (water || uReflection <= 0.0) discard;
        vec3 eye = uEye;
        float denominator = vWorld.y - eye.y;
        if (abs(denominator) < 1e-4) discard;
        float t = -eye.y / denominator;
        if (t <= 0.0 || t >= 1.0) discard;
        vec3 plane = mix(eye,vWorld,t);
        reflectionPlane=plane;
        vec2 uv = vec2(plane.x/(2.0*uHalfWidth)+0.5, -plane.z/SHOCKWAVE_DEPTH);
        // Reflections follow the water wherever it is, including a stream continuing past the grid.
        if (!sceneHeightfieldWater(basinBase(uv))) discard;
    }
    if (uMarks == 1) {
        float radius=length(gl_PointCoord-0.5);
        float coverage=1.0-smoothstep(0.25,0.5,radius);
        if ((uWireDisplay&4)!=0) {
            // A subpixel hole can remove the entire small marker. Fill its
            // core smoothly until the outlined shape has enough real pixels.
            float outline=smoothstep(0.18,0.28,radius);
            coverage*=mix(1.0,outline,smoothstep(3.0,5.0,uPointPx));
        }
        if (coverage<0.01) discard;
        vec4 pointColour=mix(uVertexColor,uVertexAccentColor,clamp(water ? vCrest*0.6 :
                         0.45+0.35*sin(vWorld.x*3.0+vWorld.z*2.0)+base*0.25,0.0,1.0));
        if ((uWireDisplay&4)!=0) pointColour=uVertexOutlineColor;
        vec3 palette=pointColour.rgb;
        float gain=water ? 0.65+0.4*vCrest : 0.65+vEnergy*clamp(base+0.15,0.0,1.0);
        // Marks belong to the land: a shining water surface replaces them (crests keep their curves).
        if (water) coverage*=1.0-smoothstep(0.0,0.6,uWaterShine);
        if (uPass==0) coverage*=uReflection*0.55*exp(-abs(vWorld.y)*1.5)*(1.0-0.6*uWaterShine)
                           *smoothstep(-0.5,0.6,sin(reflectionPlane.z*95.0+uTime*0.4));
        float alpha=coverage*pointColour.a*distanceFade*detailFade;
        FragColor=vec4(min(palette*gain,vec3(1.0)),alpha);
        Emission=sceneEmission(palette*gain*alpha*uGlow);
        return;
    }
    float shore=smoothstep(0.0,0.055,base);
    float shoreLight=basinShoreLight(vUv,base,vCurvedBase);
    float line=sceneHeightfieldCurveWire(vUv,vCurvedBase,uCurveCells,uEdgePx)*shore;
    float crest = clamp(vCrest,0.0,2.5);
    vec3 palette = mix(uLineColor.rgb,uCrestColor.rgb,clamp((water ? crest*0.6 :
                      0.45+0.35*sin(vWorld.x*3.0+vWorld.z*2.0)+base*0.25),0.0,1.0));
    float glassWeight=(uWireDisplay&4)!=0 ? uGlass.x*uGlassTint.a : 0.0;
    vec3 n = basinSurfaceNormal(glassWeight>0.0 ? vSurfaceNormal : cross(dFdx(vWorld),dFdy(vWorld)));
    float light = 0.3 + 0.7*abs(dot(n,normalize(vec3(-0.4,1.0,0.5))));
    vec3 waterFill=uWaterColor.rgb*(0.60+0.10*light);
    vec3 landFill=uTerrainFillColor.rgb+palette*(0.025+0.055*light);
    vec3 fill=water ? waterFill : mix(waterFill,landFill,shore);
    float wetShore=basinOutside(vUv)<1e-6 ? 1.0-smoothstep(0.0,BASIN_SHORE_HEIGHT,vCurvedBase) : 0.0;
    float waterCoverage=water ? 1.0 : wetShore;
    if (waterCoverage>0.0) {
        vec2 curveUv=vUv+vec2(0.0,uScroll/SHOCKWAVE_DEPTH);
        float waveWire=sceneHeightfieldWaterCurves(curveUv,vWorld.y,uCurveCells,uEdgePx);
        float ripple=(vWorld.z+uScroll)*26.0+0.35*sin(vWorld.x*5.0)+vWorld.y*9.0;
        float distance=abs(fract(ripple-0.5)-0.5)/max(fwidth(ripple),1e-5);
        float sheen=1.0-smoothstep(0.0,0.65*uEdgePx,distance);
        // A shining surface shows its water, not a ruled grid: the resting curves fade, crests stay whole.
        float curveCoverage=waveWire*(0.11*(1.0-0.8*uWaterShine)+0.55*min(crest,1.5));
        float sheenCoverage=sheen*(0.12+0.16*crest)*uWaterDetail;
        line=(1.0-(1.0-curveCoverage)*(1.0-sheenCoverage))*waterCoverage;
    }
    float ridgeWeight=clamp(base*0.8+0.2*light+0.15*sin(vWorld.x*7.0+vWorld.z*5.0),0.0,1.0);
    vec3 wire=palette*(water ? 0.65+0.55*crest : 0.65+0.2*ridgeWeight+1.65*vEnergy*ridgeWeight);
    // General land/water mesh wires are retired, but independently composed
    // travelling water accents remain. The lake perimeter is separate below.
    if (waterCoverage<=0.0) line=0.0;
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
        vec3 lineGlow=mix(wire,uWaterLineGlowColor.rgb*(0.65+0.55*crest),uWaterLineGlowColor.a)*uWaterLineGlow;
        Emission=sceneEmission((lineGlow*1.6+palette*shoreLight)*alpha*uGlow*0.45);
        return;
    }
    // The original event crest illuminates curved water detail. Keep troughs
    // dark instead of covering each crest with an opaque luminous sheet.
    float ring = water ? clamp(crest*0.08,0.0,0.20) : 0.0;
    vec3 eye=uEye;
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
    vec3 shineEmission=vec3(0.0);
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
    // Water reads as water whatever the land's surface style: a tinted body under a rippled mirror of
    // the real sky (Fresnel: dark looking down, bright at grazing angles). The Sun/Moon at infinity
    // appear in it as a natural glint. Land keeps its own material.
    if (water && uWaterShine>0.0) {
        vec2 rp=vWorld.xz*vec2(9.0,13.0)+vec2(uTime*0.35,-uTime*0.27);
        vec3 ripple=vec3(sin(rp.x)+0.5*sin(rp.y*1.7),0.0,cos(rp.y)+0.5*cos(rp.x*1.3));
        vec3 wn=normalize(n+0.1*uWaterDetail*ripple);      // Water Detail 0: a still mirror
        vec3 mirror=reflect(-view,wn);
        mirror.y=abs(mirror.y);                       // the mirror shows the sky above the water
        vec3 sky=basinVisibleSkyRadiance(vWorld,mirror);
        float fresnel=0.04+0.96*pow(1.0-clamp(dot(wn,view),0.0,1.0),5.0);
        vec3 depthTint=uWaterColor.rgb*(0.45+0.35*light);
        vec3 surface=mix(depthTint,sky*1.25,clamp(fresnel*(0.35+0.65*uWaterShine),0.0,1.0));
        // A passing wave lifts the body itself, not only its crest lines, so music moves the water.
        surface+=palette*smoothstep(0.15,1.6,crest)*0.45;
        fill=mix(fill,surface,uWaterShine);
        fillAlpha=max(fillAlpha,uWaterShine*(0.6+0.4*fresnel));
        shineEmission=sky*fresnel*uWaterShine*0.35;
    }
    // The same continuous surface settles into opaque atmospheric land at
    // its far horizon. Keep depth/coverage while fading detail and glow.
    if (!water) {
        vec3 distant=uSkyColor.rgb*(0.65+0.08*uSkyStrength)+uTerrainFillColor.rgb*0.08;
        fill=mix(distant,fill,detailFade);
        fillAlpha=mix(1.0,fillAlpha,detailFade);
    }
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
    // Only water carries lines here; their glow takes its own colour and strength.
    vec3 lineGlow=mix(wire,uWaterLineGlowColor.rgb*(0.65+0.55*crest),uWaterLineGlowColor.a)*uWaterLineGlow;
    Emission=sceneEmission((lineGlow*lineAlpha + palette*ringAlpha*0.45+shoreColour*shoreAlpha
                           +fill*fillAlpha*glassWeight*0.12+shineEmission*fillAlpha)*uGlow*distanceFade*detailFade);
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
uniform float uHorizonThickness;
void main() {
    float crest, energy, curved;
    float base=basinBase(aUv);
    float smoothed=basinCurve(aUv);
    vec3 world=vec3((aUv.x*2.0-1.0)*uHalfWidth,
                    sceneHeightfieldWater(base) ? -basinDistantDrop(aUv) : basinLandHeight(aUv,base,smoothed),
                    -aUv.y*SHOCKWAVE_DEPTH);
    vec4 clip=basinClip(world);
    float width=mix(1.8,uHorizonThickness,smoothstep(0.0,0.25,basinOutside(aUv)));
    clip.y+=uOutlineLiftNdc*width*clip.w;
    clip.z+=0.0012*clip.w; // farther than the same real surface, never internal paint
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
    bool outside=any(lessThan(vUv,vec2(0.0))) || any(greaterThan(vUv,vec2(1.0)));
    if ((!outside && vTerrainBase<0.035) || vContourFade<0.005) discard;
    float alpha=uCrestColor.a*vContourFade;
    vec3 colour=min(uCrestColor.rgb*(0.78+0.16*clamp(uMidband,0.0,1.0)),vec3(1.0));
    FragColor=vec4(colour,alpha);
    vec3 emission=colour*alpha*(0.45+0.4*uGlow);
    Emission=vec4(emission,dot(emission,vec3(0.2126,0.7152,0.0722)));
}
"""
)

# Splashes: the heaviest onsets that land on water throw droplets up and out. Static droplet slots (onset, droplet)
# read the same bounded onset ring the waves use; each droplet follows a ballistic arc from its onset's age, so no
# CPU simulation, timer or extra buffer exists, and an idle or quiet lake draws nothing.
SPLASH_DROPLETS = 64
SPLASH_THRESHOLD = 1.3      # onset strength (0..2) where splashing begins: ~3-20 a minute on recorded songs
NEON_SPLASH_VERTEX_SOURCE = (
    "#version 460 core\nlayout(location=0) in vec2 aSlot;\n"
    + SHOCKWAVE_EVENTS.glsl(3) + HEIGHTFIELD_GLSL + _PROJECTION + SHOCKWAVE_WAVE_GLSL + _POSE + _TERRAIN
    + f"""
const float SPLASH_THRESHOLD = {SPLASH_THRESHOLD:.6f};
uniform float uSplash;       // amount 0..1 (0 draws nothing)
out float vAlpha;
out float vHeat;
float splashHash(float a, float b) {{ return fract(sin(a * 127.1 + b * 311.7) * 43758.5453); }}
void main() {{
    gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    gl_PointSize = 0.0;
    vAlpha = 0.0;
    vHeat = 0.0;
    int index = int(aSlot.x);
    float drop = aSlot.y;
    if (uSplash <= 0.0 || index >= uEventCount) return;
    ShockwaveEvent e = events[index];
    float heavy = clamp((e.strength - SPLASH_THRESHOLD) / (2.0 - SPLASH_THRESHOLD), 0.0, 1.0);
    if (heavy <= 0.0) return;
    vec2 uv = vec2(e.x / (2.0 * uHalfWidth) + 0.5, -e.z / SHOCKWAVE_DEPTH);
    if (!sceneHeightfieldWater(basinBase(uv))) return;
    float seed = e.x * 13.7 + e.z * 5.1 + float(index) * 0.37;
    float angle = 6.2831853 * splashHash(seed, drop);
    // A third rise as a narrow central column, the rest as a wide crown.
    bool column = splashHash(seed + 9.4, drop) < 0.33;
    float up = (column ? 1.15 + 0.6 * splashHash(seed + 3.1, drop) : 0.6 + 0.6 * splashHash(seed + 3.1, drop))
             * (0.7 + 0.5 * heavy) * (0.55 + 0.6 * uSplash);
    float outward = (column ? 0.03 + 0.07 * splashHash(seed + 1.7, drop) : 0.25 + 0.45 * splashHash(seed + 1.7, drop))
                  * (0.6 + 0.6 * heavy);
    float gravity = 3.2;
    float t = e.age - 0.08 * splashHash(seed + 7.9, drop);   // a short stagger: a burst, not a shell
    float flight = 2.0 * up / gravity;
    if (t <= 0.0 || t >= flight) return;
    vec2 ground = vec2(e.x + cos(angle) * outward * t, e.z + sin(angle) * outward * t);
    float surface = WATER_PEAK * tanh(shockwaveHeight(ground).x / WATER_PEAK);   // the live water under the droplet
    vec3 p = vec3(ground.x, surface + up * t - 0.5 * gravity * t * t, ground.y);
    gl_Position = basinClip(p);
    float depth = max(-basinViewPoint(p).z, 0.05);
    gl_PointSize = clamp(uPointPx * (0.6 + 0.8 * splashHash(seed + 5.3, drop)) * 9.0 / depth, 1.5, uPointPx * 7.0);
    vAlpha = heavy * (0.4 + 0.6 * uSplash) * (1.0 - smoothstep(0.55, 1.0, t / flight));
    vHeat = heavy;
}}
"""
)
NEON_SPLASH_FRAGMENT_SOURCE = """#version 460 core
layout(location=0) out vec4 FragColor;
layout(location=1) out vec4 Emission;
in float vAlpha;
in float vHeat;
uniform vec4 uSplashColor;   // the water lines' glow colour (its alpha is their palette mix, not opacity)
uniform float uGlow;
void main() {
    float radius = length(gl_PointCoord - 0.5);
    float alpha = (1.0 - smoothstep(0.18, 0.5, radius)) * vAlpha;
    if (alpha < 0.004) discard;
    vec3 colour = min(uSplashColor.rgb * (0.85 + 0.5 * vHeat), vec3(1.0));
    FragColor = vec4(colour, alpha);
    vec3 glow = colour * alpha * (0.5 + uGlow);
    Emission = vec4(glow, dot(glow, vec3(0.2126, 0.7152, 0.0722)));
}
"""


@lru_cache(maxsize=1)
def splash_slots() -> tuple[float, ...]:
    """(onset index, droplet index) for every droplet the bounded onset buffer can carry."""
    from rendering.gl_programs.shockwave_grid_program import SHOCKWAVE_CAPACITY
    return tuple(float(v) for index in range(SHOCKWAVE_CAPACITY) for drop in range(SPLASH_DROPLETS)
                 for v in (index, drop))


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
    "layout(location=2) out vec4 ShaftSource;\n"
    + SHOCKWAVE_EVENTS.glsl(3) + SCENE3D_ORBIT_GLSL + _PROJECTION + SHOCKWAVE_WAVE_GLSL + _POSE
    + _SKY_HEIGHTFIELD_GLSL + _TERRAIN + NEON_CELESTIAL_GLSL + _BODY_VISIBILITY
    + """
in vec2 vUv;
uniform int uSkyPass; // 0 background, 2 depth-tested body, 3 light-shaft source (depth-tested)
uniform float uMidband; // existing spectrum midband, no new DSP owner
uniform float uBeatPulse;
uniform vec2 uCelestialGlow; // brightness, musical response
uniform int uCelestialRimVertices;
void main() {
    vec2 ndc=vec2(2.0*vUv.x-1.0,1.0-2.0*vUv.y);
    vec3 ray=normalize(basinUnview(vec3(ndc*uTan,-1.0)));
    vec3 eye=uEye;
    if (uSkyPass==3) {
        // Only the shaft source is written here (SceneTarget.shaft_writes); at the far plane, so the
        // terrain and water already drawn leave it out where they stand in front of the light.
        float source=basinShaftSource(eye,ray);
        if (source<0.0001) discard;
        ShaftSource=vec4(source,0.0,0.0,1.0);
        gl_FragDepth=1.0;
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
        vec4 body=basinCelestial(eye,ray,bodyPoint);
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
        float halo=smoothstep(0.965,1.015,normalizedAngle)
                   *exp(-pow(max(0.0,normalizedAngle-1.005)/0.115,2.0));
        halo*=step(0.0,facing)*cameraCoverage;
        vec4 bodyColour=(uBodyKind==0 ? uSunColor : uMoonColor);
        float haloGain=basinCelestialHaloGain(uCelestialGlow,uMidband,uBeatPulse);
        // The ordinary halo surrounds the ENTIRE silhouette, including the
        // Moon's shaded side. Phase gates the surface and optional rim marks,
        // never the surrounding glow.
        float haloAlpha=(uBodyKind==1 ? 0.26 : 0.23)*bodyColour.a*haloGain*halo;
        float rimMarks=0.0;
        if (uCelestialRimVertices!=0 && uCelestialGlow.x>0.0 && facing>0.0) {
            rimMarks=basinCelestialRimMarks(eye,ray,normalizedAngle)*cameraCoverage;
            haloAlpha+=0.24*bodyColour.a*haloGain*rimMarks;
        }
        // Intensity and optional rim rewards may overlap; alpha remains a
        // coverage value even at maximum settings, never extrapolated blending.
        haloAlpha=min(haloAlpha,0.98);
        float litInnerRim=0.0;
        float innerHaloAlpha=0.0;
        if (uBodyKind==1 && body.a>0.0001 && uCelestialGlow.x>0.0) {
            litInnerRim=basinMoonInnerRimEmission(eye,bodyPoint);
            innerHaloAlpha=0.115*bodyColour.a*haloGain*litInnerRim*body.a;
        }
        float alpha=body.a+haloAlpha*(1.0-body.a);
        if (alpha<0.0001) discard;
        vec3 premult=body.rgb*body.a
                    +bodyColour.rgb*(innerHaloAlpha+haloAlpha*(1.0-body.a)
                                     +0.16*haloGain*rimMarks*body.a*bodyColour.a);
        vec3 colour=premult/max(alpha,1e-5);
        FragColor=vec4(min(colour,vec3(1.0)),alpha);
        // The whole lunar surface emits softly, following its lit/shaded
        // albedo. A rim-only emitter read as a detached glowing tube. Keep
        // the boundary subordinate to this broad source and preserve texture.
        vec3 emission;
        if (uBodyKind==1) {
            // Bound surface radiance before shared bloom: linear gain clipped
            // the bright face white through loud passages at maximum settings.
            // The exterior halo keeps its stronger musical response.
            float surfaceGain=0.04*haloGain/(1.0+0.8*haloGain);
            emission=body.rgb*body.a*surfaceGain
                     +bodyColour.rgb*(0.06*innerHaloAlpha + 0.20*haloAlpha*(1.0-body.a)
                                      +0.18*haloGain*rimMarks*body.a*bodyColour.a);
        } else {
            emission=(body.rgb*body.a
                     +bodyColour.rgb*(haloAlpha*(1.0-body.a)
                                      +0.9*haloGain*rimMarks*body.a*bodyColour.a))*0.20;
        }
        Emission=vec4(emission,dot(emission,vec3(0.2126,0.7152,0.0722)));
        // Sun/Moon are celestial background. Their authored analytic sphere
        // still supplies apparent pose, phase, reflection and illumination,
        // but the SAME land depth owns their visible horizon/sky coverage.
        gl_FragDepth=1.0;
    } else {
        // One celestial coverage evaluation for ordinary stars AND the
        // independent beat-star emission attachment. No duplicate ray hits.
        float starVisibility=1.0-basinCelestialSkyMask(eye,ray);
        FragColor=basinSkyBackground(eye,ray,starVisibility,1);
        if (FragColor.a<0.0001) discard;
        // Separate small radiance buffer entry for event stars, not the entire
        // sky (which would turn on widespread bloom and flatten the scene).
        vec3 sparkle=basinBeatStarColour()*uStarColor.a*basinBeatStarLight(eye,ray,uStarGlow,starVisibility)*0.95;
        Emission=vec4(sparkle,dot(sparkle,vec3(0.2126,0.7152,0.0722)));
        gl_FragDepth=0.999999;
    }
}
"""
)

__all__ = ["BasinView", "basin_view", "orbit_view", "NEON_SPLASH_VERTEX_SOURCE", "NEON_SPLASH_FRAGMENT_SOURCE", "splash_slots", "SPLASH_DROPLETS", "NEON_VERTEX_SOURCE", "NEON_FRAGMENT_SOURCE",
           "NEON_SKY_VERTEX_SOURCE", "NEON_SKY_FRAGMENT_SOURCE", "NEON_SKYLINE_VERTEX_SOURCE", "NEON_SKYLINE_FRAGMENT_SOURCE"]
