"""Framed basin projection and terrain/water shaders over shared Scene3D owners.

Neon Lake (mode id ``shockwave_grid``; its keys, runtime and Settings are ``shockwave_grid_*``) is mapped
in ``Docs/Reference/Naming.md``; ``SHOCKWAVE_*`` here are its onset waves, not the mode's old name.

Authored base height alone classifies water. Its travelling waves join the visible
shore through the shallow fringe; dry land retains its independent bounded lift.
The view is the shared framed physical camera (``core.settings.framed_camera``): orbit, dolly, pan and
flight move a real eye over the land; audio cannot change framing or target sizing.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from core.constants.neon_lake_world import (
    CONTINUATION_DESCENT, DISTANT_CURVATURE, DISTANT_FLAT, FAR_HILLS, FAR_PLANE, WATER_PEAK,
)
from rendering.gl_programs.heightfield_glsl import HEIGHTFIELD_GLSL, HEIGHTFIELD_WIRE_GLSL
from rendering.gl_programs.heightfield_volume_glsl import HEIGHTFIELD_VOLUME_GLSL
from rendering.gl_programs.heightfield_glsl import HEIGHTFIELD_GLSL as _SKY_HEIGHTFIELD_GLSL
from rendering.gl_programs.neon_celestial import NEON_CELESTIAL_GLSL
from rendering.gl_programs.neon_terrain_reaction import REACTION_GLSL
from rendering.gl_programs.scene3d import SCENE3D_GLSL, SCENE3D_ORBIT_GLSL
from rendering.gl_programs.shockwave_grid_program import (
    SHOCKWAVE_DEPTH, SHOCKWAVE_EVENTS, SHOCKWAVE_MAX_BARS, SHOCKWAVE_WAVE_GLSL, SHOCKWAVE_HALF_WIDTH,
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
    tan = fc.viewport_tangents(fov, field[2] / field[3], 1., SPEC.fov_range)
    return BasinView(eye, axes[:3], axes[3:6], axes[6:9], tan, tuple(field))


def basin_view(parameters, field, *, aperture_scale: float = 1.) -> BasinView:
    """Shared physical eye over the fixed terrain; only the observed aperture can resize."""
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
        terrain_floor(get("terrain"), float(get("terrain_height")), SHOCKWAVE_HALF_WIDTH,
                      floor_reaction(parameters)), axes=axes)
    tan = fc.viewport_tangents(fov, aspect, aperture_scale, SPEC.fov_range)
    return BasinView(eye, axes[:3], axes[3:6], axes[6:9], tan, tuple(field))




# The authored grid may reach past the basin toward the horizon: grid uv = (basin uv + xy) * z.
# Every distance and constant in these shaders is in basin uv; only heightfield reads convert.
# A program that never sets the uniform sees the identity (an unextended grid).
# The generated landscape (continuation, far hills, distant curvature, the fade of detail and glow) belongs to the
# authored origin: the square the grid had before the terrain brush grew it (uTerrainOrigin, in grid uv; the whole
# grid otherwise). Stored cells past the origin lie over that landscape, so growing the grid moves nothing.
_GRID_GLSL = """
uniform vec3 uTerrainGrid = vec3(0.0, 0.0, 1.0);
uniform vec4 uTerrainOrigin = vec4(0.0, 0.0, 1.0, 1.0);
vec2 basinGrid(vec2 uv) { return (uv + uTerrainGrid.xy) * uTerrainGrid.z; }
#define SCENE_HEIGHTFIELD_GRID(uv) basinGrid(uv)
// Distance outside the authored origin, in basin uv (0 on it).
float basinOutside(vec2 uv) {
    vec2 grid = basinGrid(uv);
    return length(grid - clamp(grid, uTerrainOrigin.xy, uTerrainOrigin.zw)) / uTerrainGrid.z;
}
// Distance past the stored grid, in basin uv (0 on it): the same as basinOutside until the brush grows the grid.
float basinPastGrid(vec2 uv) {
    vec2 grid = basinGrid(uv);
    return length(grid - clamp(grid, vec2(0.0), vec2(1.0))) / uTerrainGrid.z;
}
bool basinGrown() { return uTerrainOrigin != vec4(0.0, 0.0, 1.0, 1.0); }
"""

_PROJECTION = _GRID_GLSL + f"""
const float SHOCKWAVE_DEPTH = {SHOCKWAVE_DEPTH:.6f};
const float WATER_PEAK = {WATER_PEAK:.6f};
const float LAND_CONTOUR_SPACING = 0.03; // Contour Lines: world depth between the range's wireframe rows
// Contour Lines' land: the raised ground beyond the basin's near edge (the range and its foothills), not the
// dunes in front of it nor the low banks. Shared by the lines and the marks that give way to them.
float basinContourRegion(vec2 uv,float base) {{ return smoothstep(0.15,0.3,base)*smoothstep(0.0,0.08,uv.y); }}
const vec2 FAR_HILLS_LEVEL = vec2({FAR_HILLS[0]:.6f}, {FAR_HILLS[1]:.6f});
const vec4 FAR_HILLS_WAVE = vec4({FAR_HILLS[2]:.6f}, {FAR_HILLS[3]:.6f}, {FAR_HILLS[4]:.6f}, {FAR_HILLS[5]:.6f});
const float DISTANT_FLAT = {DISTANT_FLAT:.6f};
const vec2 CONTINUATION_DESCENT = vec2({CONTINUATION_DESCENT[0]:.6f}, {CONTINUATION_DESCENT[1]:.6f});
const float DISTANT_CURVATURE = {DISTANT_CURVATURE:.6f};
const float FAR_PLANE_DISTANCE = {FAR_PLANE:.6f};
// The broad hills the land settles into toward the horizon (mirrored in neon_terrain_extent and the editor).
float basinFarHills(vec2 uv) {{
    return FAR_HILLS_LEVEL.x+FAR_HILLS_LEVEL.y*sin(FAR_HILLS_WAVE.x*uv.x+FAR_HILLS_WAVE.y*uv.y)
                                              *cos(FAR_HILLS_WAVE.z*uv.y-FAR_HILLS_WAVE.w*uv.x);
}}
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
float basinFar() { return FAR_PLANE_DISTANCE; }
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

# Depth Scale: vertex marks and ridge lines drawn as if on the land itself, growing toward the camera from
# their ordinary on-screen size at BASIN_DEPTH_REFERENCE scene units to at most BASIN_DEPTH_GROWTH_MAX times
# it. Farther marks keep their size, so no mark ever shrinks below the authored physical-pixel diameter.
BASIN_DEPTH_REFERENCE = 2.4
BASIN_DEPTH_GROWTH_MAX = 3.0
_DEPTH_SCALE = f"""
const float BASIN_DEPTH_REFERENCE = {BASIN_DEPTH_REFERENCE:.6f};
const float BASIN_DEPTH_GROWTH_MAX = {BASIN_DEPTH_GROWTH_MAX:.6f};
uniform float uDepthScale; // 0 keeps marks and ridge lines one size on screen
float basinDepthGrowth(float depth) {{
    return 1.0+uDepthScale*(clamp(BASIN_DEPTH_REFERENCE/max(depth,1e-3),1.0,BASIN_DEPTH_GROWTH_MAX)-1.0);
}}
"""

_SHORE_HEIGHT_GLSL = """
#ifndef BASIN_SHORE_HEIGHT
#define BASIN_SHORE_HEIGHT 0.018
#endif
"""

_TERRAIN = _SHORE_HEIGHT_GLSL + REACTION_GLSL + """
uniform sampler2D uTerrain;
uniform sampler2D uTerrainDelta; // a grown grid's overlay (read only while basinGrown())
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
// The origin's own cells, read as the grid's edge was before the grid grew past it: samples stop at the origin's
// square. An ungrown grid takes the ordinary samplers (the origin is the texture).
ivec4 basinOriginCells() { return ivec4(round(uTerrainOrigin*float(uTerrainSize-1))); }
vec2 basinOriginTexel(vec2 grid) {
    // Points on the origin's edge sit on a cell line: snap them, or one side's cells leak into the other's.
    vec2 p=grid*float(uTerrainSize-1), whole=round(p);
    return mix(p,whole,lessThan(abs(p-whole),vec2(1e-3)));
}
float basinOriginHeight(vec2 grid) {
    if (!basinGrown()) return sceneHeightfield(uTerrain,uTerrainSize,grid);
    ivec4 cells=basinOriginCells();
    vec2 p=clamp(basinOriginTexel(grid),vec2(cells.xy),vec2(cells.zw));
    ivec2 c0=min(ivec2(floor(p)),cells.zw), c1=min(c0+1,cells.zw);
    vec2 f=p-vec2(c0);
    // Water is decided on the origin's own cells alone, exactly: the filtered read below may weigh in a
    // neighbouring cell past the origin by a rounding step.
    float exact=mix(mix(texelFetch(uTerrain,c0,0).r,texelFetch(uTerrain,ivec2(c1.x,c0.y),0).r,f.x),
                    mix(texelFetch(uTerrain,ivec2(c0.x,c1.y),0).r,texelFetch(uTerrain,c1,0).r,f.x),f.y);
    if (exact==0.0) return 0.0;
    // The height itself is the same filtered read the edge had before the grid grew (the snapped texel sits on
    // the origin's own row or column), so the generated land does not shift by a filtering step.
    return max(textureLod(uTerrain,(p+0.5)/float(uTerrainSize),0.0).r,1e-30);
}
float basinOriginCurve(vec2 grid) {
    if (!basinGrown()) return sceneHeightfieldCurve(uTerrain,uTerrainSize,grid);
    ivec4 cells=basinOriginCells();
    vec2 p=clamp(basinOriginTexel(grid),vec2(cells.xy),vec2(cells.zw));
    ivec2 cell=ivec2(floor(p));
    vec4 wx=sceneHeightfieldWeights(p.x-float(cell.x)),wy=sceneHeightfieldWeights(p.y-float(cell.y));
    float height=0.0;
    for (int y=0;y<4;++y) for (int x=0;x<4;++x)
        height+=wx[x]*wy[y]*texelFetch(uTerrain,clamp(cell+ivec2(x-1,y-1),cells.xy,cells.zw),0).r;
    return height;
}
float basinContinuation(vec2 uv) {
    vec2 grid=basinGrid(uv);
    vec2 edge=clamp(grid,uTerrainOrigin.xy,uTerrainOrigin.zw);
    vec2 delta=grid-edge;
    float distance=length(delta)/uTerrainGrid.z;
    float boundary=basinOriginHeight(edge);
    if (distance<1e-6) return boundary;
    // Water reaching the grid's edge keeps flowing outward to the horizon (a painted stream or coast),
    // never stopping at a wall of rolling land; dry edges roll away as before.
    if (sceneHeightfieldWater(boundary)) return 0.0;
    vec2 inward=clamp(edge-sign(delta)/float(uTerrainSize-1),uTerrainOrigin.xy,uTerrainOrigin.zw);
    float interior=basinOriginHeight(inward);
    // Continue the local edge derivative only in a thin transition strip.
    // Retaining the last border height indefinitely made tall ridges look like
    // mountain-shaped extrusion running to the end of the world.
    float slope=clamp((boundary-interior)*float(uTerrainSize-1)*uTerrainGrid.z,-0.8,0.8);
    float nearSlope=0.20*slope*min(distance,0.16);
    float descent=smoothstep(CONTINUATION_DESCENT.x,CONTINUATION_DESCENT.y,distance);
    // A broad, low rolling *landform*, not the infinitely extruded editor
    // border or a perfectly flat far plane. Gentle undulations give the
    // accepted depth-tested skyline a natural distant silhouette.
    float backgroundHeight=0.12+0.065*sin(2.7*uv.x+1.7*uv.y)
                            *cos(2.4*uv.y-0.8*uv.x)
                            +0.040*sin(1.1*uv.y-2.3*uv.x);
    // The boundary and its derivative are exact at distance zero; well away
    // from it the surface turns into subdued rolling ground, never a wall.
    float rolling=max(0.025,mix(boundary+nearSlope,backgroundHeight,descent));
    return mix(rolling,basinFarHills(uv),smoothstep(1.1,2.2,distance));
}
// The generated landscape's smooth surface: the origin's cubic on it, its continuation past it.
float basinGeneratedCurve(vec2 uv) {
    vec2 edge=clamp(basinGrid(uv),uTerrainOrigin.xy,uTerrainOrigin.zw);
    if (basinOutside(uv)<1e-6) return basinOriginCurve(edge);
    float base=basinOriginHeight(edge);
    if (sceneHeightfieldWater(base)) return 0.0;
    // Exactly continuous with the cubic surface at the editor boundary.
    float boundary=basinOriginCurve(edge);
    float continued=max(0.0,boundary+basinContinuation(uv)-base);
    return mix(continued,basinFarHills(uv),smoothstep(1.1,2.2,basinOutside(uv)));
}
// A grown grid's cells past the origin are an overlay on the generated land: the scene adds each cell's delta
// (stored minus generated, uTerrainDelta: zero wherever the brush never painted), smoothed by the land's own cubic.
// Past the grid's edge the edge's delta eases out over the continuation's descent, so paint never ends in a wall.
// Returns how much of the delta applies at uv (0: none can) and the grid uv to read it at.
float basinOverlay(vec2 uv,out vec2 edge) {
    vec2 grid=basinGrid(uv);
    edge=clamp(grid,vec2(0.0),vec2(1.0));
    // Well inside the origin no grown cell is within the cubic's reach.
    vec2 inner=min(grid-uTerrainOrigin.xy,uTerrainOrigin.zw-grid)*float(uTerrainSize-1);
    if (min(inner.x,inner.y)>=2.0) return 0.0;
    return 1.0-smoothstep(CONTINUATION_DESCENT.x,CONTINUATION_DESCENT.y,length(grid-edge)/uTerrainGrid.z);
}
float basinBase(vec2 uv) {
    // On the origin: its stored cells. Past it: the generated land, under the grown cells' overlay.
    if (basinOutside(uv)<1e-6) return sceneHeightfield(uTerrain,uTerrainSize,basinGrid(uv));
    float generated=basinContinuation(uv);
    if (!basinGrown()) return generated;
    // Water is the stored cells' own (bilinear zero) on the grid and the generated land's past it.
    if (basinPastGrid(uv)<1e-6) {
        if (sceneHeightfieldWater(sceneHeightfield(uTerrain,uTerrainSize,basinGrid(uv)))) return 0.0;
    } else if (sceneHeightfieldWater(generated)) return 0.0;
    vec2 edge;
    float overlay=basinOverlay(uv,edge);
    if (overlay<=0.0) return max(generated,1e-6);
    return max(1e-6,generated+overlay*sceneHeightfield(uTerrainDelta,uTerrainSize,edge));
}
float basinCurve(vec2 uv) {
    float generated=basinGeneratedCurve(uv);
    if (!basinGrown()) return generated;
    vec2 edge;
    float overlay=basinOverlay(uv,edge);
    if (overlay<=0.0) return generated;
    if (basinPastGrid(uv)>=1e-6 && sceneHeightfieldWater(basinContinuation(uv))) return generated;
    return max(0.0,generated+overlay*sceneHeightfieldCurve(uTerrainDelta,uTerrainSize,edge));
}
float basinDetailFade(vec2 uv) {
    // Detail and glow carry well out over the land toward the horizon before settling into its haze.
    return 1.0-smoothstep(1.2,4.5,basinOutside(uv));
}
float basinDistanceFade(vec2 uv) {
    // Land keeps full coverage everywhere, toward the camera too (2026-11-05): it reaches the horizon all round,
    // and the camera floor's collision keeps the near plane out of it, so the old camera-facing skirt fade only
    // left land floating over the sky once the eye could roam past it. Only detail fades with distance.
    return 1.0;
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
    float distance=max(0.0,basinOutside(uv)-DISTANT_FLAT);
    return DISTANT_CURVATURE*distance*distance;
}
// Programs that read the distant land let the sky's horizon glow follow its real horizon (neon_celestial).
#define BASIN_HAS_DISTANT_LAND 1
float basinLandHeight(vec2 uv,float base,float curved) {
    vec2 p=vec2((uv.x*2.0-1.0)*uHalfWidth,-uv.y*SHOCKWAVE_DEPTH);
    float height=curved*smoothstep(0.0,0.015,base)*uLand.x*(1.0+0.16*uLand.y*basinDetail(p));
    // Terrain Reaction reshapes the land by the music: zero at the shore, never below a floor
    // share of its authored height, faded with the distant continuation's detail.
    if (uReaction.x>0.0) {
        // Zero at the water and easing in up the bank over the smooth land's own rise: on the cells' height alone
        // it came in within a quarter of a cell, and a strong reshaping stood as a wall along the shore.
        float land=smoothstep(0.0,0.08,base)*smoothstep(BASIN_SHORE_HEIGHT,0.10,curved)*basinDetailFade(uv);
        // Its patterns and Growth lift (or lower) the land.
        float authored=height;
        float room=(1.0-REACTION_FLOOR)*authored;
        float change=uLand.x*(basinReaction(uv,curved,p,land)+land*basinGrowth(p));
        // Downward, the change eases onto the floor share instead of stopping at it: a hard stop creased the
        // land along the line where it was reached.
        height+=change<0.0 ? -room*tanh(-change/max(room,1e-6)) : change;
        // Indents carve bowls into what stands there, onto their own lower floor.
        float press=land*basinIndent(p);
        if (press>0.0) height-=basinIndentDepth(press,height,authored,uLand.x);
    }
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
    float ripple=WATER_PEAK*tanh(wave.x/WATER_PEAK)+0.0025*uWaterDetail*sin(15.0*p.x+18.0*p.y+0.4*uTime);
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
    + SHOCKWAVE_EVENTS.glsl(3) + SCENE3D_ORBIT_GLSL + HEIGHTFIELD_GLSL + _PROJECTION + SHOCKWAVE_WAVE_GLSL + _POSE
    + _DEPTH_SCALE + _TERRAIN
    + """
out vec3 vWorld;
out vec2 vUv;
out float vCrest;
out float vEnergy;
out float vCurvedBase;
out vec3 vSurfaceNormal;
out float vPointPx;
uniform int uSmoothGlass;
void main() {
    vec3 world = basinSurface(aUv, vCrest, vEnergy, vCurvedBase);
    vSurfaceNormal=vec3(0.0,1.0,0.0);
    // Glass triangles and the direct land marks (whose brightness follows the relief) take the true normal.
    if (uPass==1 && uDepthOnly==0 && (uMarks==1 || uSmoothGlass==1)) {
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
                   *sin(world.z*65.0+uTime*0.18);
    }
    vWorld = world;
    vUv = aUv;
    vec4 clip = basinClip(world);
    if (uMarks == 1) clip.z -= 0.0001*clip.w;
    vPointPx=uPointPx*basinDepthGrowth(clip.w);
    gl_PointSize=vPointPx;
    gl_Position = clip;
}
"""
)

_SHORELINE_GLSL = _SHORE_HEIGHT_GLSL + """
float basinShoreLight(vec2 uv, float base, float curved) {
    // Only the authored grid draws a shore line. The positive rolling land
    // outside it can cross the visual shore band without containing water.
    // Water within the cubic's reach draws its share of the line too: the smoothed contour crosses the
    // square water cells' edges, and stopping at them broke the line into dashes.
    if ((sceneHeightfieldWater(base) && curved<=0.0) || basinOutside(uv)>1e-6) return 0.0;
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
in float vPointPx;
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
uniform float uShoreGlow;         // the water's edge glow along the visible shoreline (0 = only the shoreline)
uniform vec4 uShoreGlowColor;     // its colour; alpha mixes it in over the shoreline's own palette
uniform float uWaterGlint;        // the Sun/Moon's glittering path on the water below it (0 = none)
uniform float uContourLines;      // level lines over the land's slopes (0 = none)
uniform vec4 uGlintLight;         // halo intensity, halo reactivity (0, 0 with the halo off), midband, beat pulse
uniform float uWaterReact;        // Water Reaction times the music drive (shockwave_music_drive; 0 = none)
vec4 sceneEmission(vec3 rgb) { return vec4(rgb, dot(rgb, vec3(0.2126,0.7152,0.0722))); }
// Screen distance in physical pixels from a water or wet-fringe fragment to the visible shoreline (negative
// up the dry bank): the bank distance across open water, the shoreline contour on land. Derivatives come from
// the caller, taken in uniform control flow.
float basinShorePixels(bool water,vec2 uv,float curved,vec2 uvPerPixel,float curvedPerPixel) {
    // Open water reads the bilinear cached bank distance alone: the exact near-bank refinement measures to
    // square control cells and would print their staircase into a soft glow.
    float contour=(BASIN_SHORE_HEIGHT-curved)/max(curvedPerPixel,0.0001);
    if (!water) return contour;
    // Close to the shore, water measures to the same visible contour as the bank does, easing into the cached
    // distance as the cubic fades to zero, so the glow runs on across the square cells' edges without a seam.
    float cached=sceneHeightfieldBankDistance(uTerrain,uTerrainSize,basinGrid(uv))/uTerrainGrid.z
                 /max(length(uvPerPixel),1e-6);
    return mix(cached,contour,smoothstep(0.0,0.6*BASIN_SHORE_HEIGHT,curved));
}
// The land in the water's mirror, without a second render target: march the mirrored ray outward over the
// coarse land height and keep the highest elevation the land reaches along it (a horizon profile for that
// direction). Coverage is how far the ray lies below that profile; rim is a narrow band at the profile itself,
// the mirrored skyline's glow. Bounded: 30 geometrically growing steps to about 7 scene units.
float basinMirrorLand(vec3 origin,vec3 dir,float softness,out float rim) {
    float horizontal=max(length(dir.xz),1e-4);
    float elevation=dir.y/horizontal;
    vec3 level=vec3(dir.x,0.0,dir.z)/horizontal;
    float profile=-1.0;
    float t=0.04;
    for (int i=0;i<30;++i) {
        vec3 p=origin+level*t;
        vec2 uv=vec2(p.x/(2.0*uHalfWidth)+0.5,-p.z/SHOCKWAVE_DEPTH);
        float base=basinBase(uv);
        // Only land stands in the mirror. Counting the water's rest level as land made every swell trough
        // (water below its rest height) mirror "land" all round it: a dark blob in the middle of the lake.
        if (sceneHeightfieldWater(base)) { t*=1.19; continue; }
        float h=base*uLand.x-basinDistantDrop(uv);
        profile=max(profile,(h-origin.y)/t);
        t*=1.19;
    }
    float gap=profile-elevation;
    rim=exp(-pow(gap/(0.6*softness),2.0));
    return smoothstep(-softness,softness,gap);
}
// The glitter path: broken bright streaks on the water in a column under the body on screen, widening and
// fading toward the viewer. Artistic, like a painted moon path: it does not need the mirror angle.
// ``depthPerPixel`` is fwidth(world.z) from the caller, so the streaks fade to their mean before aliasing.
// Small ripples whose crests run across the view (their trains travel along the view's heading on the water),
// as wind ripples on a still lake look from its shore. Returns the height (-1..1) and its slope (world x/z);
// each train fades to flat where it would alias (perPixel: world units per pixel).
float basinRipple(vec2 xz,float perPixel,out vec2 slope) {
    vec2 heading=normalize(vec2(-uBack.x,-uBack.z)+vec2(1e-5,0.0));
    vec2 side=vec2(-heading.y,heading.x);
    vec2 w=vec2(dot(xz,side),dot(xz,heading));
    // Pass 5: two longer trains (crests a world unit or so wide across the view, a few tenths apart along it)
    // survive at the lake's distance, where the short ones fade before they alias: the mock's far water is
    // broken into short horizontal glints right across the lake.
    const vec4 K[6]=vec4[6](vec4(3.0,38.0,1.10,0.40),vec4(-5.0,52.0,-0.90,0.30),
                            vec4(8.0,29.0,0.70,0.45),vec4(-2.0,71.0,1.30,0.22),
                            vec4(2.6,12.0,0.55,0.38),vec4(-4.1,16.5,-0.45,0.32));
    float height=0.0,total=0.0;
    vec2 g=vec2(0.0);
    for (int i=0;i<6;++i) {
        float fade=clamp(2.0-length(K[i].xy)*perPixel*2.2,0.0,1.0);   // gone below ~3 pixels a wave
        float phase=dot(K[i].xy,w)+0.11*K[i].z*uTime+float(i)*1.7;
        height+=K[i].w*fade*sin(phase);
        g+=K[i].w*fade*K[i].xy*cos(phase);
        total+=K[i].w;
    }
    slope=(side*g.x+heading*g.y)*(0.0035/total);
    return height/total;
}
float basinWaterGlint(vec3 world,float depthPerPixel,float ripple,float screenPerPixel) {
    vec3 body=basinViewPoint(uBodyPosition);
    vec3 here=basinViewPoint(world);
    if (body.z>-0.05 || here.z>-0.01) return 0.0;
    // Screen position in units of the vertical half-aperture on both axes, so the column is not stretched.
    vec2 b=body.xy/(-body.z*uTan.y);
    vec2 h=here.xy/(-here.z*uTan.y);
    float radius=uBodySize/max(length(uBodyPosition-uEye),1e-3)/uTan.y;
    float below=b.y-h.y;
    if (below<=0.0) return 0.0;
    // Pass 6: a broader, longer column (the mocks' reflection reaches from the far shore to the near one).
    float width=radius*(0.6+0.5*below);
    float column=exp(-pow((h.x-b.x)/max(width,1e-4),2.0));
    float reach=exp(-below/3.0);
    // The path is the ripples' crests catching the body: many short bright streaks, softening into an even
    // shimmer where the ripples are too fine to draw.
    float detail=clamp(1.5-35.0*depthPerPixel,0.0,1.0);
    float glitter=mix(0.3,pow(smoothstep(0.25,0.95,0.5+0.5*ripple),2.0),detail);
    // Each streak is a thin sharp line (a wavelet's crest a pixel or two tall, a few pixels apart on screen,
    // wavering with the ripples), not a soft lozenge.
    float lines=0.5+0.5*sin(6.2832*h.y/max(4.5*screenPerPixel,1e-6)+0.6*ripple+1.3*sin(h.x*37.0));
    glitter*=0.35+2.4*pow(lines,4.0);
    return min(3.0*column*reach*glitter,1.0);
}
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
            coverage*=mix(1.0,outline,smoothstep(3.0,5.0,vPointPx));
        }
        if (coverage<0.01) discard;
        vec4 pointColour=mix(uVertexColor,uVertexAccentColor,clamp(water ? vCrest*0.6 :
                         0.45+0.35*sin(vWorld.x*3.0+vWorld.z*2.0)+base*0.25,0.0,1.0));
        if ((uWireDisplay&4)!=0) pointColour=uVertexOutlineColor;
        vec3 palette=pointColour.rgb;
        float gain=water ? 0.65+0.4*vCrest : 0.65+vEnergy*clamp(base+0.15,0.0,1.0);
        if (!water && uPass==1) {
            // Marks light with the land's relief: slopes facing the authored Sun/Moon direction (whether or not
            // the body is shown, so hiding it never relights the land) shine, the far sides of crests and the
            // troughs fall dark, so the dotted land reads as shaped ground rather than an even carpet.
            vec3 toLight=normalize(uBodyPosition-vWorld);
            vec3 toEye=normalize(uEye-vWorld);
            float facing=0.5+0.5*dot(vSurfaceNormal,normalize(toLight+toEye));
            gain*=0.35+1.05*facing*facing;
        }
        // Marks belong to the land: a shining water surface replaces them (crests keep their curves).
        // The wet fringe below the visible shoreline is water too: without this its marks stood in a
        // staircase of square control cells along every shining shore.
        float wetMark=water ? 1.0 : (basinOutside(vUv)<1e-6 ? 1.0-smoothstep(0.0,BASIN_SHORE_HEIGHT,vCurvedBase) : 0.0);
        coverage*=1.0-smoothstep(0.0,0.6,uWaterShine)*wetMark;
        // Where Contour Lines draw the high land's slopes, the lines are its surface: the marks give way, so
        // ranges read as a contour wireframe and the dots stay on the dunes and gentle ground.
        if (uContourLines>0.0 && !water)
            coverage*=1.0-uContourLines*basinContourRegion(vUv,base);
        if (uPass==0) coverage*=uReflection*0.55*exp(-abs(vWorld.y)*1.5)*(1.0-0.6*uWaterShine)
                           *smoothstep(-0.5,0.6,sin(reflectionPlane.z*95.0+uTime*0.16));
        float alpha=coverage*pointColour.a*distanceFade*detailFade;
        FragColor=vec4(min(palette*gain,vec3(1.0)),alpha);
        Emission=sceneEmission(palette*gain*alpha*uGlow);
        return;
    }
    // The shore's cubic contour, sampled per fragment where it can matter: interpolated from the vertices it
    // was linear across each mesh triangle, so the contour kinked at every triangle and its width (fwidth)
    // jumped between them, beading the shoreline into a chain of arcs. Deep water and high land keep the
    // vertex value (no shore within reach), so only the shore band pays for the cubic.
    float curvedBase=vCurvedBase;
    if (vCurvedBase>0.0 && vCurvedBase<0.2 && basinOutside(vUv)<1e-6) {
        // A cell-wide box over the cubic: its contour on painted (square-celled) water still kinked once per
        // cell into scallops; averaged over half-cell offsets it runs as one smooth curve.
        float halfCell=0.5/(float(uTerrainSize-1)*uTerrainGrid.z);
        curvedBase=0.25*(basinCurve(vUv+vec2(halfCell,halfCell))+basinCurve(vUv+vec2(-halfCell,halfCell))
                         +basinCurve(vUv+vec2(halfCell,-halfCell))+basinCurve(vUv-vec2(halfCell)));
    }
    // The land lines' measures and their derivatives, in uniform control flow.
    float landContour=vWorld.z/LAND_CONTOUR_SPACING;
    float landContourPerPixel=fwidth(landContour);
    vec3 landLineGlow=vec3(0.0);
    // Derivatives for the edge glow and glint, taken here in uniform control flow.
    vec2 uvPerPixel=fwidth(vUv);
    float curvedPerPixel=fwidth(curvedBase);
    float depthPerPixel=fwidth(vWorld.z);
    vec3 viewHere=basinViewPoint(vWorld);
    float screenPerPixel=fwidth(viewHere.y/min(viewHere.z*uTan.y,-1e-4));
    vec2 rippleSlope;
    float rippleHeight=basinRipple(vWorld.xz,max(fwidth(vWorld.x),depthPerPixel),rippleSlope);
    // Shining water's lines: a network of interfering ripples drawn as thin lines (the lake reads as water,
    // not a ruled grid), brightening with the music's crests and spectrum energy.
    // Broad enough to draw as lines across the lake rather than crowd into a fade.
    // Its own slow clock only: carried along by Scroll it marched across the lake (busy, not gentle).
    vec2 wp=vWorld.xz*0.75;
    float rippleField=sin(wp.x*7.0+wp.y*11.0+uTime*0.12)+sin(-wp.x*9.0+wp.y*13.0-uTime*0.1)
                      +0.7*sin(wp.x*3.0-wp.y*17.0+uTime*0.08+vWorld.y*8.0);
    float rippleChange=fwidth(rippleField);
    float rippleDistance=abs(rippleField)/max(rippleChange,1e-5);
    // Where the lines would crowd closer than a few pixels they fade out instead of sparkling.
    float rippleClarity=1.0-smoothstep(0.9,1.8,rippleChange);
    float shore=smoothstep(0.0,0.055,base);
    float shoreLight=basinShoreLight(vUv,base,curvedBase);
    float line=sceneHeightfieldCurveWire(vUv,curvedBase,uCurveCells,uEdgePx)*shore;
    float crest = clamp(vCrest,0.0,2.5);
    vec3 palette = mix(uLineColor.rgb,uCrestColor.rgb,clamp((water ? crest*0.6 :
                      0.45+0.35*sin(vWorld.x*3.0+vWorld.z*2.0)+base*0.25),0.0,1.0));
    float glassWeight=(uWireDisplay&4)!=0 ? uGlass.x*uGlassTint.a : 0.0;
    vec3 n = basinSurfaceNormal(glassWeight>0.0 ? vSurfaceNormal : cross(dFdx(vWorld),dFdy(vWorld)));
    float light = 0.3 + 0.7*abs(dot(n,normalize(vec3(-0.4,1.0,0.5))));
    vec3 waterFill=uWaterColor.rgb*(0.60+0.10*light);
    vec3 landFill=uTerrainFillColor.rgb+palette*(0.025+0.055*light);
    // Water reaches right up to the drawn shoreline: a fringe fading out from the cells' edge showed the
    // square water cells as darker blocks wherever land (an island, a cove) sat within a cell of them.
    float wetShore=basinOutside(vUv)<1e-6 ? 1.0-smoothstep(0.7*BASIN_SHORE_HEIGHT,BASIN_SHORE_HEIGHT,curvedBase) : 0.0;
    float waterCoverage=water ? 1.0 : wetShore;
    vec3 fill=water ? waterFill : mix(waterFill,landFill,shore*(1.0-wetShore));
    // Water Reaction (pass 7): the mocks' high-react lake, a glowing net of two crossing ripple families (the
    // ripple colour one way, the crest colour the other, whitening where they cross) that lights with the music.
    // Its own slow clock (not Scroll); fades where its lines would crowd under ~5 px. Off (0) does no work.
    float reactNet=0.0;
    vec3 reactColour=vec3(0.0);
    if (uWaterReact>0.0) {
        vec2 rq=vWorld.xz*2.2;
        // Each family is warped by two slow fields, so the cells are irregular (caustic light), not a ruled grid.
        float fa=sin(rq.x*4.1+rq.y*6.3+0.16*uTime+1.1*sin(rq.y*2.3-rq.x*1.3+0.07*uTime)
                     +0.45*sin(rq.x*5.3+rq.y*3.7-0.05*uTime));
        float fb=sin(-rq.x*4.7+rq.y*5.6-0.13*uTime+1.1*sin(rq.y*2.1+rq.x*1.6-0.05*uTime)
                     +0.45*sin(-rq.x*4.9+rq.y*4.1+0.06*uTime));
        float wa=max(fwidth(fa),1e-5), wb=max(fwidth(fb),1e-5);
        float width=(0.8+1.2*uWaterReact)*uEdgePx;
        float la=(1.0-smoothstep(0.0,width,abs(fa)/wa))*(1.0-smoothstep(0.35,0.7,wa));
        float lb=(1.0-smoothstep(0.0,width,abs(fb)/wb))*(1.0-smoothstep(0.35,0.7,wb));
        // A soft light either side of each line: light on the water, not hairlines.
        float ga=exp(-abs(fa)/(4.0*wa))*(1.0-smoothstep(0.25,0.55,wa));
        float gb=exp(-abs(fb)/(4.0*wb))*(1.0-smoothstep(0.25,0.55,wb));
        reactNet=clamp(max(la,lb)+0.35*max(ga,gb),0.0,1.0);
        // The mocks' net leans violet-magenta: the ripple family takes a third of the crest colour.
        reactColour=(mix(uLineColor.rgb,uCrestColor.rgb,0.35)*(la+0.35*ga)+uCrestColor.rgb*(lb+0.35*gb))
                    /max(la+lb+0.35*(ga+gb),1e-4);
        reactColour=mix(reactColour,vec3(1.0),0.45*la*lb);
    }
    if (waterCoverage>0.0) {
        vec2 curveUv=vUv+vec2(0.0,uScroll/SHOCKWAVE_DEPTH);
        float waveWire=sceneHeightfieldWaterCurves(curveUv,vWorld.y,uCurveCells,uEdgePx);
        // The fine sheen lines drift with Scroll at a quarter of its pace: hairlines a few pixels apart moving a
        // pixel a frame read as shimmer noise over the whole lake rather than flowing water.
        float ripple=(vWorld.z+0.25*uScroll)*26.0+0.35*sin(vWorld.x*5.0)+vWorld.y*9.0;
        float distance=abs(fract(ripple-0.5)-0.5)/max(fwidth(ripple),1e-5);
        float sheen=1.0-smoothstep(0.0,0.65*uEdgePx,distance);
        // A shining surface shows its water, not a ruled grid: the resting curves fade, crests stay whole.
        // A passing crest lights its curves gently (they used to flash at over half strength, the lake's busiest motion).
        float curveCoverage=waveWire*(0.11*(1.0-0.8*uWaterShine)+0.22*min(crest,1.5));
        // Pass 6: faint at rest (long smooth curves across a mirror read as scratches, not water), still lit by
        // the music's crests.
        float network=(1.0-smoothstep(0.0,0.9*uEdgePx,rippleDistance))*rippleClarity
                      *(0.06+0.22*min(crest,1.5)+0.2*vEnergy)*min(3.0*uWaterDetail,1.4);   // Water Detail 0: none
        // Rings lapping out from every shore (concentric round an island), drifting slowly outward and
        // fading over open water; drawn as the network's lines, so they glow with it.
        float bankUv=sceneHeightfieldBankDistance(uTerrain,uTerrainSize,basinGrid(vUv))/uTerrainGrid.z;
        float ringPhase=bankUv*36.0-uTime*0.06;
        float ringPx=abs(fract(ringPhase)-0.5)/max(fwidth(ringPhase),1e-5);
        float rings=(1.0-smoothstep(0.0,1.1*uEdgePx,ringPx))*exp(-bankUv/0.06)
                    *(1.0-smoothstep(0.12,0.22,fwidth(ringPhase)))*min(3.0*uWaterDetail,1.4)*(0.8+1.6*uWaterReact)
                    *(water ? smoothstep(0.004,0.02,bankUv) : 0.0);
        network=max(network,rings);
        curveCoverage=mix(curveCoverage,clamp(network,0.0,1.0),uWaterShine);
        float sheenCoverage=sheen*(0.12+0.08*crest)*uWaterDetail;
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
        float ripple=sin(p.y*65.0 + p.x*3.0 + uTime*0.18)
                    + 0.45*sin(p.y*117.0-p.x*11.0-uTime*0.09);
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
    float ring = water ? clamp(crest*0.03,0.0,0.08) : 0.0;   // gentle: a crest washing the lake read as busy flashing patches
    vec3 eye=uEye;
    vec3 view=normalize(eye-vWorld);
    n=faceforward(n,-view,n);
    vec4 bodyColour=uBodyKind==0 ? uSunColor : uMoonColor;
    vec3 toBody=normalize(uBodyPosition-vWorld);
    // Shadowing by the authored relief is marched only on the authored grid: land rolling on past it toward
    // the horizon is lit unshadowed (most of the land on screen; the march there cost more than all the rest).
    bool bodyLight=uSunEnabled==1 && (uLightStrength>0.0 || glassWeight>0.0)
                   && (basinOutside(vUv)>1e-6 || !sceneHeightfieldVolumeLightOccluded(uTerrain,uTerrainSize,vWorld+vec3(0.0,0.005,0.0),
                                                          uBodyPosition,uHalfWidth,SHOCKWAVE_DEPTH,uLand.x/1.25));
    if (bodyLight && uLightStrength>0.0) {
        fill+=bodyColour.rgb*bodyColour.a*uLightStrength*max(dot(n,toBody),0.0)*0.32;
    }
    // The wet fringe is as see-through as the water it belongs to (an opaque land fill there showed every
    // square water cell beside an island or cove as a block).
    float fillAlpha=uFloor*mix(uTerrainFillColor.a,uWaterColor.a*0.55,waterCoverage);
    vec3 shineEmission=vec3(0.0);
    // Land settled into the distant haze (detail faded out) shows none of its glass, so it skips the material;
    // land past the authored grid takes one environment sample instead of the rough five (the terrain reaching
    // on to the horizon is most of the land on screen, distant and small, where the blur is under a pixel).
    if (glassWeight>0.0 && detailFade>0.001) {
        float roughness=clamp(uGlass.y,0.045,0.5);
        SceneMaterial material=SceneMaterial(uGlassTint.rgb,roughness,0.0,0.5,vec3(0.0));
        vec3 reflected=reflect(-view,n);
        vec3 environment=basinVisibleSkyRadiance(vWorld,reflected);
        if (basinOutside(vUv)<1e-6 && roughness>0.12) {
            vec3 tangent=normalize(cross(reflected,abs(reflected.y)<0.9 ? vec3(0.0,1.0,0.0) : vec3(1.0,0.0,0.0)));
            vec3 bitangent=cross(reflected,tangent);
            environment=(environment*2.0+basinVisibleSkyRadiance(vWorld,normalize(reflected+tangent*roughness))
                         +basinVisibleSkyRadiance(vWorld,normalize(reflected-tangent*roughness))
                         +basinVisibleSkyRadiance(vWorld,normalize(reflected+bitangent*roughness))
                         +basinVisibleSkyRadiance(vWorld,normalize(reflected-bitangent*roughness)))/6.0;
        }
        // Emissive neon sky is a lighting source: retain dark face interiors
        // while the shared Fresnel response exposes continuous grazing curves.
        vec3 glass=uGlassTint.rgb*0.035+environment*3.0*sceneEnvironmentBrdf(sceneMaterialF0(material),roughness,max(dot(n,view),1e-4));
        if (bodyLight) glass+=sceneBrdfLight(material,n,view,toBody,bodyColour.rgb*bodyColour.a*0.7);
        // Glossy rims: grazing glass the Sun/Moon can see catches its light along every crest and silhouette (a
        // Fresnel sheen in the body's colour), so rolling glass dunes read as polished, rim-lit forms.
        if (bodyLight) {
            float grazing=1.0-clamp(dot(n,view),0.0,1.0);
            // Only surfaces facing the body's side catch it (a body below their horizon lights nothing).
            glass+=bodyColour.rgb*bodyColour.a*pow(grazing,4.0)*0.9*smoothstep(0.0,0.25,dot(n,toBody));
        }
        fill=mix(fill,glass,glassWeight);
        fillAlpha=max(fillAlpha,glassWeight*0.85);
    }
    // Water reads as water whatever the land's surface style: a tinted body under a rippled mirror of
    // the real sky (Fresnel: dark looking down, bright at grazing angles). The Sun/Moon at infinity
    // appear in it as a natural glint. Land keeps its own material.
    // The wet fringe below the visible shoreline shines as water too (a dark mirror stopping at the square
    // control cells drew their staircase inside every gentle shore).
    float wetness=water ? 1.0 : wetShore;
    if (wetness>0.0 && uWaterShine>0.0) {
        vec2 rp=vWorld.xz*vec2(9.0,13.0)+vec2(uTime*0.06,-uTime*0.045);
        vec3 ripple=vec3(sin(rp.x)+0.5*sin(rp.y*1.7),0.0,cos(rp.y)+0.5*cos(rp.x*1.3));
        // Water Detail 0: a still mirror; otherwise the slow swell and the small ripples tilt it.
        // The mirror leans only partly with the mesh's facets: their flat triangles, tilting as waves pass,
        // made the reflection jump in blotches from triangle to triangle (busy motion on a calm lake).
        vec3 calm=normalize(mix(vec3(0.0,1.0,0.0),n,0.08));
        vec3 wn=normalize(calm+0.04*uWaterDetail*ripple+vec3(-rippleSlope.x,0.0,-rippleSlope.y)*mix(8.0,18.0,smoothstep(0.15,0.4,uWaterDetail))*uWaterDetail);
        vec3 mirror=reflect(-view,wn);
        mirror.y=abs(mirror.y);                       // the mirror shows the sky above the water
        vec3 sky=basinVisibleSkyRadiance(vWorld,mirror);
        // The land and its glowing skyline in the mirror, as strong as Water Reflection; ripples break it up.
        if (uReflection>0.0) {
            float rim;
            float land=basinMirrorLand(vWorld,mirror,0.012+0.05*uWaterDetail,rim)*uReflection;
            vec3 landColour=uTerrainFillColor.rgb*0.7+sky*0.08;
            vec3 skylineColour=min(uCrestColor.rgb*0.85,vec3(1.0))*uCrestColor.a;
            sky=mix(sky,landColour,land)+skylineColour*rim*uReflection*0.9;
        }
        float fresnel=0.04+0.96*pow(1.0-clamp(dot(wn,view),0.0,1.0),5.0);
        vec3 depthTint=uWaterColor.rgb*(0.45+0.35*light);
        // A neon lake is a dark mirror: even looking down it shows the sky and land above it (an artistic
        // floor on the Fresnel term), brightening toward grazing angles.
        // Pass 6: darker (the mocks' lakes are near-black mirrors whose light is the reflection column and the
        // glints): a lower floor and a darker body.
        float mirrorWeight=clamp((0.12+0.88*fresnel)*(0.35+0.65*uWaterShine),0.0,1.0);
        vec3 surface=mix(depthTint*0.8,sky,mirrorWeight);
        // A passing wave lifts the body itself, not only its crest lines, so music moves the water (gently:
        // a swell washing the whole lake read as a bright sheet).
        surface+=palette*smoothstep(0.3,1.8,crest)*0.07;
        // Ripple highlights: each crest catches the bright band above the far horizon, in the water's own
        // line/crest colours, so the lake shimmers in short horizontal strokes (brighter with the music).
        vec2 heading=normalize(vec2(-uBack.x,-uBack.z)+vec2(1e-5,0.0));
        vec3 glowDirection=normalize(vec3(heading.x,0.10,heading.y));
        float highlight=pow(clamp(dot(mirror,glowDirection),0.0,1.0),16.0)*smoothstep(0.55,0.95,rippleHeight);
        vec3 shimmer=mix(uLineColor.rgb,uCrestColor.rgb,0.5+0.5*sin(vWorld.x*2.3+vWorld.z*1.7));
        surface+=shimmer*highlight*(0.3+0.3*min(crest,1.5)+0.25*vEnergy)*uWaterDetail*0.9;
        // Pass 5: the mock's lake is a dark mirror broken everywhere into short horizontal glints (its ripples'
        // crests catching the glowing ridges and sky), not a smooth sheet: every ripple crest takes a faint
        // stroke of the water's colours, brightening toward grazing angles and with the music.
        vec2 gq=vec2(dot(vWorld.xz,vec2(-heading.y,heading.x)),dot(vWorld.xz,heading));
        float glintRows=sin(gq.y*85.0+gq.x*4.0+0.2*uTime+1.6*sin(gq.x*9.0+gq.y*7.0));
        float glintBreaks=sin(gq.x*31.0-gq.y*11.0-0.14*uTime+2.2*sin(gq.x*7.3+gq.y*5.1)+1.3*sin(gq.y*17.0))
                         *(0.6+0.4*sin(gq.x*3.1+gq.y*13.7+0.09*uTime));
        float glintFade=clamp(2.0-85.0*depthPerPixel*0.9,0.0,1.0);   // gone before its rows are under ~5 px apart
        float glints=smoothstep(0.7,0.98,glintRows)*smoothstep(0.1,0.6,glintBreaks)*glintFade*(0.5+0.5*fresnel);
        fill=mix(fill,surface,uWaterShine*wetness);
        // The glints sit on top of the mirror in the ridges' colours (the mock's violet-magenta strokes).
        vec3 glintColour=mix(uLineColor.rgb,uCrestColor.rgb,0.7);
        fill+=glintColour*glints*(0.9+0.6*min(crest,1.5)+0.5*vEnergy)*min(2.0*uWaterDetail,1.0)*uWaterShine*wetness;
        fillAlpha=max(fillAlpha,uWaterShine*wetness*(0.6+0.4*fresnel));
        shineEmission=sky*fresnel*uWaterShine*wetness*0.12;   // pass 6: a dark mirror's own glow stays faint
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
    float shoreAlpha=clamp(shoreLight*(0.55+0.95*vEnergy+0.8*uWaterReact),0.0,1.0)*uCrestColor.a;
    vec3 premult=fill*fillAlpha*(1.0-lineAlpha)+wire*lineAlpha;
    float alpha=fillAlpha*(1.0-lineAlpha)+lineAlpha;
    premult=premult*(1.0-ringAlpha)+palette*ringAlpha;
    alpha=alpha*(1.0-ringAlpha)+ringAlpha;
    vec3 shoreColour=mix(uLineColor.rgb,uCrestColor.rgb,clamp(0.5+0.45*sin(vWorld.x*3.0+vWorld.z*2.0),0.0,1.0));
    premult=premult*(1.0-shoreAlpha)+shoreColour*shoreAlpha;
    alpha=alpha*(1.0-shoreAlpha)+shoreAlpha;
    // Contour Lines: the range drawn as a wireframe of rows across it (lines of constant depth draped over the
    // land, so every ridge and foothill shows its profile slice), a few pixels apart at least (they fade where
    // they would crowd), in the palette leaning toward the ridge colour and brightening with the spectrum's
    // energy. Crests themselves are the skyline pass's silhouettes.
    if (uPass==1 && uContourLines>0.0) {
        float dry=(water ? 0.0 : 1.0)*(1.0-wetShore)*detailFade*smoothstep(0.0,0.05,base);
        float contourPx=abs(fract(landContour-0.5)-0.5)/max(landContourPerPixel,1e-5);
        float contour=(1.0-smoothstep(0.35,1.1,contourPx))*(1.0-smoothstep(0.2,0.45,landContourPerPixel))
                      *basinContourRegion(vUv,base);
        float contourAlpha=clamp(contour*uContourLines*0.7*(0.75+1.1*vEnergy),0.0,1.0)*dry;
        vec3 contourColour=mix(uLineColor.rgb,palette,0.3+0.4*smoothstep(0.4,0.9,base));
        premult=premult*(1.0-contourAlpha)+contourColour*contourAlpha;
        alpha=alpha*(1.0-contourAlpha)+contourAlpha;
        landLineGlow=contourColour*contourAlpha*0.9;
    }
    // Shore Glow: light along the actual visible shoreline, spreading over the water (a short lip up the
    // dry bank), in screen pixels so near and distant shores glow alike. It only ever adds to the shoreline.
    float edgeGlow=0.0;
    vec3 edgeColour=mix(shoreColour,uShoreGlowColor.rgb,uShoreGlowColor.a);
    if (uShoreGlow>0.0 && basinOutside(vUv)<1e-6) {
        float px=basinShorePixels(water,vUv,curvedBase,uvPerPixel,curvedPerPixel);
        float reach=1.2+2.8*min(uShoreGlow,2.0);
        edgeGlow=(px>=0.0 ? exp(-px/reach) : exp(px/(0.35*reach)))*uShoreGlow*(0.75+0.5*vEnergy+0.8*uWaterReact);
        float edgeAlpha=clamp(0.45*edgeGlow,0.0,0.85);
        premult=premult*(1.0-edgeAlpha)+edgeColour*edgeAlpha;
        alpha=alpha*(1.0-edgeAlpha)+edgeAlpha;
    }
    // Sun/Moon path: glittering streaks on the water under the body, brightening with the halo's music.
    float glintLight=0.0;
    vec3 glintColour=mix(bodyColour.rgb,vec3(1.0),0.15);
    if (wetness>0.0 && uWaterGlint>0.0 && uSunEnabled==1) {
        float gain=uGlintLight.x>0.0 ? basinCelestialHaloGain(uGlintLight.xy,uGlintLight.z,uGlintLight.w) : 1.0;
        glintLight=uWaterGlint*wetness*basinWaterGlint(vWorld,depthPerPixel,rippleHeight,screenPerPixel)*(0.75+0.25*gain+0.6*uWaterReact)*bodyColour.a;
        float glintAlpha=clamp(glintLight,0.0,1.0);
        premult=premult*(1.0-glintAlpha)+glintColour*glintAlpha;
        alpha=alpha*(1.0-glintAlpha)+glintAlpha;
    }
    vec3 reactLight=vec3(0.0);
    if (reactNet>0.0 && waterCoverage>0.0) {
        // Convex in the drive: a quiet passage's net stays faint, a loud one's vivid.
        float reactGain=uWaterReact*sqrt(uWaterReact);
        float reactAlpha=clamp(reactNet*reactGain*1.4,0.0,0.95)*waterCoverage;
        premult=premult*(1.0-reactAlpha)+reactColour*reactAlpha;
        alpha=alpha*(1.0-reactAlpha)+reactAlpha;
        reactLight=reactColour*reactAlpha*1.3;
        // The whole lake lifts a little in the net's colours (the mocks' high-react water is lit, not black).
        premult+=mix(uLineColor.rgb,uCrestColor.rgb,0.6)*0.10*reactGain*waterCoverage*(1.0-reactAlpha);
    }
    FragColor=vec4(min(premult/max(alpha,1e-4),vec3(1.0)),alpha*distanceFade);
    // Only water carries lines here; their glow takes its own colour and strength.
    vec3 lineGlow=mix(wire,uWaterLineGlowColor.rgb*(0.65+0.55*crest),uWaterLineGlowColor.a)*uWaterLineGlow;
    Emission=sceneEmission((lineGlow*lineAlpha + palette*ringAlpha*0.45+shoreColour*shoreAlpha
                           +fill*fillAlpha*glassWeight*0.12+shineEmission*fillAlpha
                           +edgeColour*edgeGlow*1.2+glintColour*glintLight*1.4+landLineGlow+reactLight)
                           *uGlow*distanceFade*detailFade);
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
    + _PROJECTION + SHOCKWAVE_WAVE_GLSL + _POSE + _DEPTH_SCALE + _TERRAIN
    + """
out vec2 vUv;
out float vContourFade;
out float vTerrainBase;
out float vRidgeVary;
out float vRidgeNear;
uniform float uOutlineLiftNdc; // physical-pixel lift, supplied by renderer viewport
uniform float uHorizonThickness;
vec3 basinSkylinePoint(vec2 uv) {
    float base=basinBase(uv);
    return vec3((uv.x*2.0-1.0)*uHalfWidth,
                sceneHeightfieldWater(base) ? -basinDistantDrop(uv) : basinLandHeight(uv,base,basinCurve(uv)),
                -uv.y*SHOCKWAVE_DEPTH);
}
void main() {
    float crest, energy, curved;
    float base=basinBase(aUv);
    float smoothed=basinCurve(aUv);
    vec3 world=vec3((aUv.x*2.0-1.0)*uHalfWidth,
                    sceneHeightfieldWater(base) ? -basinDistantDrop(aUv) : basinLandHeight(aUv,base,smoothed),
                    -aUv.y*SHOCKWAVE_DEPTH);
    vec4 clip=basinClip(world);
    // Near ridges draw thicker with Depth Scale, like the marks on the same land.
    float growth=basinDepthGrowth(clip.w);
    float width=mix(1.8,uHorizonThickness,smoothstep(0.0,0.25,basinOutside(aUv)))*growth;
    // Pass 6: ridges on the authored land swell and thin along their length (the mocks' near dune crests are
    // soft glows that widen, brighten and fade out, not one even stroke); the distant horizon keeps its
    // authored thickness. A smooth function of the land position, so it stays put on the ground.
    float vary=0.5+0.5*sin(world.x*2.3+world.z*1.1+1.7*sin(world.z*0.9-world.x*0.6));
    vary=0.65*vary+0.35*(0.5+0.5*sin(world.x*5.3-world.z*3.1+0.8));
    float inside=1.0-smoothstep(0.0,0.25,basinOutside(aUv));
    // Never wider than 1.45x: the lift is a screen shift of the whole land, and a larger one exposed the lifted
    // copy over a near dune's own face as a solid lobe (Preset 3, lead review 2026-11-06). Near ridges get their
    // breadth from a softer core and its glow instead.
    float nearRidge=smoothstep(1.05,1.6,growth);
    width*=mix(1.0,mix(0.45,1.45,vary),inside);
    vRidgeVary=mix(1.0,vary,inside);
    vRidgeNear=inside*nearRidge;
    clip.y+=uOutlineLiftNdc*width*clip.w;
    // Farther than the same real surface, never internal paint: a fixed NDC offset, or 2% of the view
    // distance where that is more (near land, whose NDC depth changes fast, otherwise let the lifted copy
    // paint over its own face).
    float farPlane=basinFar();
    float farther=clip.w*((farPlane+BASIN_NEAR)-2.0*farPlane*BASIN_NEAR/(1.02*max(clip.w,1e-4)))/(farPlane-BASIN_NEAR);
    // Pass 7: a face climbing up the screen as it recedes (near land seen grazing) gains depth fast per pixel. Over
    // the lift the real surface there lies farther than 2% behind this vertex, so the lifted copy showed over the
    // land's own face as a broad sheet (Depth Scale 1, thickness 3). Push the copy behind the depth that face
    // reaches over the lift: the surface's own depth per NDC height, three quarters of a cell farther from the eye.
    // At a crest the land beyond falls away on screen, so no extra offset applies and the ridge stays in front of
    // farther land (a whole cell also swallowed interior crests in front of the next dune: Preset 3's near bands).
    vec2 away=normalize(-uBack.xz+vec2(1e-5,0.0));
    vec2 toward=vec2(away.x/(2.0*uHalfWidth),-away.y/SHOCKWAVE_DEPTH);
    toward*=0.75/(float(uTerrainSize-1)*uTerrainGrid.z*max(abs(toward.x),abs(toward.y)));
    vec4 next=basinClip(basinSkylinePoint(aUv+toward));
    float rise=next.y/max(next.w,1e-4)-(clip.y-uOutlineLiftNdc*width*clip.w)/max(clip.w,1e-4);
    // Only where the face climbs on past the lift (a cell rising further on screen than the lift): a crest within
    // the lift is a silhouette, whose copy must stay in front of the land beyond it. Eased in, never popped.
    float lift=uOutlineLiftNdc*width;
    float extra=0.0;
    if (rise>lift && next.w>clip.w)
        extra=min(1.5*lift*(next.w-clip.w)/rise,0.5*clip.w)*smoothstep(1.0,2.0,rise/max(lift,1e-6));
    float behind=clip.w*((farPlane+BASIN_NEAR)-2.0*farPlane*BASIN_NEAR/max(clip.w+extra,1e-4))/(farPlane-BASIN_NEAR);
    clip.z=max(max(clip.z+0.0012*clip.w,farther),behind);
    gl_Position=clip;
    vUv=aUv;
    vTerrainBase=base;
    // The only skyline is the visible, displaced terrain itself. Exactly
    // share its outer coverage: resurrecting faded mesh with a distant
    // radiance floor drew disconnected straight stripes above the horizon.
    vContourFade=basinDistanceFade(aUv);
    // Land right at the eye has no skyline: a ridge crossing the near plane drew one smeared bar.
    // Its fixed depth offset is too small for a slope that close, so the lifted copy also painted over it.
    vContourFade*=smoothstep(0.4,1.0,clip.w);
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
in float vRidgeVary;
in float vRidgeNear;
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
    // Fading where the ridge thins; near ridges are a softer, translucent core whose bloom carries them.
    float alpha=uCrestColor.a*vContourFade*mix(0.3,1.0,smoothstep(0.05,0.8,vRidgeVary))*(1.0-0.35*vRidgeNear);
    // Broad near ridges breathe with the midband half as much: their wide glow pumping read as busy foreground.
    float midband=clamp(uMidband,0.0,1.0)*(1.0-0.5*vRidgeNear);
    vec3 colour=min(uCrestColor.rgb*(0.78+0.16*midband),vec3(1.0));
    FragColor=vec4(colour,alpha);
    // The ridges' glow swells with the music's midband (smoothed upstream, so it breathes rather than flickers).
    vec3 emission=colour*alpha*(0.45+0.4*uGlow)*(1.0+0.9*midband);
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
        // The silhouette is antialiased over a pixel and a half inside the limb: the sphere's own limb feather is
        // far thinner than a pixel and stepped into a staircase once the glow no longer covered it.
        float limbPixel=max(fwidth(normalizedAngle),1e-4);
        body.a*=1.0-smoothstep(1.0-1.5*limbPixel,1.0,normalizedAngle);
        // Outer corona around the sphere silhouette. The Moon also gets a very
        // small same-colour lift just inside the illuminated rim, so the glow
        // reads as originating from the body rather than a detached tube.
        // A soft corona hugging the limb (it starts just inside the edge and fades over a fifth of the radius,
        // no hard ring) ...
        // Pass 5: it falls off exponentially over about a quarter of the radius (the mock's moon glow), so the
        // light hugs the limb instead of standing as a bright tube round it.
        float halo=smoothstep(0.96,1.01,normalizedAngle)
                   *exp(-max(0.0,normalizedAngle-1.0)/0.26);
        halo*=step(0.0,facing)*cameraCoverage;
        vec4 bodyColour=(uBodyKind==0 ? uSunColor : uMoonColor);
        float haloGain=basinCelestialHaloGain(uCelestialGlow,uMidband,uBeatPulse);
        // The ordinary halo surrounds the ENTIRE silhouette, including the
        // Moon's shaded side. Phase gates the surface and optional rim marks,
        // never the surrounding glow.
        float haloAlpha=(uBodyKind==1 ? 0.26 : 0.23)*bodyColour.a*haloGain*halo;
        // A wide soft glow spreading far past the corona (the bright body lighting the night air round it),
        // falling off over about its own diameter; land in front hides it (this pass is depth-tested).
        // ... and a wide bloom spreading over about a radius and a half.
        float wide=smoothstep(0.95,1.03,normalizedAngle)*exp(-max(0.0,normalizedAngle-1.0)/0.8);
        haloAlpha+=0.04*bodyColour.a*haloGain*wide*step(0.0,facing)*cameraCoverage;
        float rimMarks=0.0;
        if (uCelestialRimVertices!=0 && uCelestialGlow.x>0.0 && facing>0.0) {
            rimMarks=basinCelestialRimMarks(eye,ray,normalizedAngle)*cameraCoverage;
            haloAlpha+=0.24*bodyColour.a*haloGain*rimMarks;
        }
        // Intensity and optional rim rewards may overlap; alpha remains a
        // coverage value even at maximum settings, never extrapolated blending.
        // Loud passages saturate softly (1-exp), so the corona never flattens into an opaque ring.
        haloAlpha=min(1.0-exp(-haloAlpha),0.98);
        float litInnerRim=0.0;
        float innerHaloAlpha=0.0;
        if (uBodyKind==1 && body.a>0.0001 && uCelestialGlow.x>0.0) {
            litInnerRim=basinMoonInnerRimEmission(eye,bodyPoint);
            innerHaloAlpha=0.03*bodyColour.a*haloGain*litInnerRim*body.a;
        }
        // The Moon's limb light (phase-free, part of the halo): the glow rising inside the whole silhouette toward
        // its edge, lifting the shaded side to a luminous grey and ending in a fine bright rim line, as the mock's
        // crescent does. Screen-blended into the body's own colour, so the bright face cannot clip to white.
        float limbLight=0.0;
        if (uBodyKind==1 && body.a>0.0001 && uCelestialGlow.x>0.0) {
            float a=clamp(normalizedAngle,0.0,1.0);
            float rimLine=exp(-pow((normalizedAngle-0.975)/0.022,2.0));
            limbLight=(1.0-exp(-haloGain))*body.a*(0.42*pow(smoothstep(0.45,1.0,a),2.0)+0.55*rimLine);
        }
        float alpha=body.a+haloAlpha*(1.0-body.a);
        if (alpha<0.0001) discard;
        vec3 premult=body.rgb*body.a
                    +bodyColour.rgb*(innerHaloAlpha+haloAlpha*(1.0-body.a)
                                     +0.16*haloGain*rimMarks*body.a*bodyColour.a);
        vec3 colour=premult/max(alpha,1e-5);
        colour=min(colour,vec3(1.0));
        colour+=(vec3(1.0)-colour)*clamp(bodyColour.rgb,0.0,1.0)*min(limbLight,1.0);
        FragColor=vec4(colour,alpha);
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

__all__ = ["BasinView", "basin_view", "orbit_view", "NEON_VERTEX_SOURCE", "NEON_FRAGMENT_SOURCE",
           "NEON_SKY_VERTEX_SOURCE", "NEON_SKY_FRAGMENT_SOURCE", "NEON_SKYLINE_VERTEX_SOURCE", "NEON_SKYLINE_FRAGMENT_SOURCE"]
