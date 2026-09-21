"""Bounded seeded Voronoi fracture and analytic glass motion, with no GL imports."""
from __future__ import annotations

from dataclasses import dataclass
import math
import random


@dataclass(frozen=True, slots=True)
class GlassShard:
    center: tuple[float, float]
    polygon: tuple[tuple[float, float], ...]
    variation: float


def _clip_cell(polygon, nx: float, ny: float, limit: float):
    result = []
    previous = polygon[-1]
    previous_distance = previous[0] * nx + previous[1] * ny - limit
    for current in polygon:
        distance = current[0] * nx + current[1] * ny - limit
        if (distance <= 0.0) != (previous_distance <= 0.0):
            fraction = previous_distance / (previous_distance - distance)
            result.append((previous[0] + fraction * (current[0] - previous[0]),
                           previous[1] + fraction * (current[1] - previous[1])))
        if distance <= 0.0:
            result.append(current)
        previous, previous_distance = current, distance
    return result


def fracture_cells(seed: int, count: int, aspect: float) -> tuple[GlassShard, ...]:
    """Clip a jittered site set into gap-free convex cells in physical aspect.

    A hard 180-site ceiling bounds quadratic work at admission. No scipy,
    triangulation dependency, process-global random state or per-frame physics.
    """
    count = max(24, min(180, int(count)))
    aspect = max(0.1, min(10.0, float(aspect)))
    rng = random.Random(int(seed))
    columns = max(2, min(count, round(math.sqrt(count * aspect))))
    rows = math.ceil(count / columns)
    # Every site is retained (including the last partial row), with independent
    # offsets so the fracture has irregular cells instead of grid diagonals.
    sites = [((index % columns + rng.uniform(0.12, 0.88)) / columns * aspect,
              (index // columns + rng.uniform(0.12, 0.88)) / rows)
             for index in range(count)]
    shards = []
    for index, (sx, sy) in enumerate(sites):
        polygon = [(0.0, 0.0), (aspect, 0.0), (aspect, 1.0), (0.0, 1.0)]
        # Nearest planes first reduce the polygon quickly; distance ordering
        # is stable and changes no topology or seeded result.
        others = sorted((point for i, point in enumerate(sites) if i != index),
                        key=lambda point: (point[0] - sx)**2 + (point[1] - sy)**2)
        radius_squared = max((x-sx)**2 + (y-sy)**2 for x, y in polygon)
        for ox, oy in others:
            nx, ny = ox - sx, oy - sy
            # A farther bisector cannot intersect this cell's enclosing circle.
            # Ordered distances make all remaining planes provably irrelevant.
            if nx*nx + ny*ny > 4.0*radius_squared:
                break
            limit = (ox * ox + oy * oy - sx * sx - sy * sy) * 0.5
            if all(x * nx + y * ny <= limit for x, y in polygon):
                continue
            polygon = _clip_cell(polygon, nx, ny, limit)
            radius_squared = max((x-sx)**2 + (y-sy)**2 for x, y in polygon)
        # Arithmetic mean lies strictly inside this convex cell and produces
        # valid fan triangles even on clipped display boundaries.
        cx = sum(x for x, _ in polygon) / len(polygon)
        cy = sum(y for _, y in polygon) / len(polygon)
        shards.append(GlassShard((cx / aspect, cy),
                                tuple((x / aspect, y) for x, y in polygon), rng.random()))
    return tuple(shards)


def fracture_vertices(shards: tuple[GlassShard, ...], aspect: float) -> tuple[float, ...]:
    vertices = []
    for shard in shards:
        cx, cy = shard.center
        # Shared fan-centre distance keeps the highlight continuous across
        # internal fan edges. Only polygon boundaries receive a glass rim.
        radius = min(math.hypot((x - cx) * aspect, y - cy) for x, y in shard.polygon) * 0.6
        for index, a in enumerate(shard.polygon):
            b = shard.polygon[(index + 1) % len(shard.polygon)]
            # UVs are top-down; reverse winding so the +Z face remains front
            # facing after the Quick/world Y conversion.
            for point, edge in ((shard.center, radius), (b, 0.0), (a, 0.0)):
                vertices.extend((*point, cx, cy, edge, shard.variation))
    return tuple(vertices)


GLASS_VERTEX = """#version 410 core
layout(location=0) in vec2 aUv;
layout(location=1) in vec2 aCenter;
layout(location=2) in float aEdge;
layout(location=3) in float aVariation;
uniform mat4 uMatrix;
uniform vec2 uItemSize;
uniform vec2 uDirection;
uniform int uRadial;
uniform float uProgress;
uniform float uDepth;
out vec2 vUv;
out vec3 vNormal;
out float vEdge;
out float vMotion;
out vec3 vView;

vec3 rotateAxis(vec3 p, vec3 axis, float angle) {
    float c=cos(angle), s=sin(angle);
    return p*c + cross(axis,p)*s + axis*dot(axis,p)*(1.0-c);
}
void main() {
    float aspect=uItemSize.x/uItemSize.y;
    vec2 center=vec2((aCenter.x-.5)*aspect,.5-aCenter.y);
    vec2 delta=vec2((aUv.x-aCenter.x)*aspect,aCenter.y-aUv.y);
    vec2 direction=vec2(uDirection.x,-uDirection.y);
    float rank;
    if(uRadial==1) {
        direction=normalize(center+vec2(.00001));
        rank=length(center)/length(vec2(aspect*.5,.5));
    } else {
        rank=.5+dot(aCenter-.5,uDirection)/(abs(uDirection.x)+abs(uDirection.y));
    }
    float delay=.56*clamp(rank,0.0,1.0)+.035*aVariation;
    float local=clamp((uProgress-delay)/(.98-delay),0.0,1.0);
    float motion=local*local*(3.0-2.0*local);
    float impact=smoothstep(0.0,.12,local);
    vec3 axis=normalize(vec3(cos(aVariation*37.0),sin(aVariation*29.0),.25+sin(aVariation*17.0)*.6));
    float angle=motion*(3.5+4.5*aVariation);
    vec3 position=rotateAxis(vec3(delta,0),axis,angle);
    // Camera is at z=3. Positive impulse briefly separates shards toward the
    // viewer, then they recede while sweeping clear of the destination.
    float z=uDepth*(sin(local*3.14159265)*.65-local*local*1.8);
    position.xy+=center + direction*local*local*(1.0+aspect*.3)*(0.75+.5*aVariation);
    position.y-=local*local*.3;
    position.z+=z;
    // A short final shrink clears every finite shard continuously before 1.
    float shrink=1.0-smoothstep(.78,1.0,local);
    vec3 rotated=rotateAxis(vec3(delta,0),axis,angle);
    position-=rotated*(1.0-shrink);
    float w=3.0-position.z;
    vec2 uv=vec2(position.x/aspect,-position.y)*3.0/w+.5;
    vec4 projected=uMatrix*vec4(uv*uItemSize,0,1);
    projected*=w;
    projected.z=clamp(-position.z/5.0,-.9,.9)*projected.w;
    gl_Position=projected;
    vUv=aUv;
    vNormal=rotateAxis(vec3(0,0,1),axis,angle);
    vView=vec3(-position.xy,3.0-position.z);
    vEdge=aEdge*shrink;
    vMotion=impact;
}
"""

GLASS_FRAGMENT = """#version 410 core
in vec2 vUv;
in vec3 vNormal;
in float vEdge;
in float vMotion;
in vec3 vView;
out vec4 FragColor;
uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
void main() {
    vec3 n=normalize(vNormal);
    vec3 view=normalize(vView);
    float facing=abs(dot(n,view));
    float fresnel=pow(1.0-facing,3.0);
    float rim=1.0-smoothstep(0.0,max(fwidth(vEdge)*1.35,.0004),vEdge);
    vec3 light=normalize(vec3(-.45,.7,1.1));
    float spec=pow(abs(dot(n,normalize(light+view))),48.0);
    vec3 source=texture(uOldTex,vUv).rgb;
    float grey=dot(source,vec3(.2126,.7152,.0722));
    vec3 body=mix(source,vec3(grey)*vec3(.84,.94,1.04),.12*vMotion);
    // Subtle transmission samples destination with bounded refraction, never
    // an additional surface capture or a blur chain.
    vec3 transmitted=texture(uNewTex,clamp(vUv+n.xy*.008*vMotion,0.0,1.0)).rgb;
    body=mix(body,transmitted,.11*vMotion*(.35+fresnel));
    if(!gl_FrontFacing) body*=mix(1.0,.72,vMotion);
    body+=vec3(.66,.85,1.0)*vMotion*(rim*(.25+.65*fresnel)+spec*.22+fresnel*.045);
    FragColor=vec4(body,1.0);
}
"""
