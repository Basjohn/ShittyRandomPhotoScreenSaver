"""Finite seeded tube topology and shaders for Tendril Reveal."""

from __future__ import annotations
from dataclasses import dataclass
import math
import random


@dataclass(frozen=True, slots=True)
class TendrilBranch:
    root: tuple[float, float]
    controls: tuple[tuple[float, float], tuple[float, float], tuple[float, float]]
    radius: float
    start: float
    end: float


def _bezier(branch: TendrilBranch, t: float) -> tuple[float, float]:
    a = branch.root
    b, c, d = branch.controls
    q = 1.0 - t
    return (
        q * q * q * a[0]
        + 3 * q * q * t * b[0]
        + 3 * q * t * t * c[0]
        + t * t * t * d[0],
        q * q * q * a[1]
        + 3 * q * q * t * b[1]
        + 3 * q * t * t * c[1]
        + t * t * t * d[1],
    )


def tendril_branches(seed: int, detail: float) -> tuple[TendrilBranch, ...]:
    """Deterministic parent-first sculptural growth; no evolving CPU state."""
    rng = random.Random(seed)
    root = (0.5, 0.54)
    branches = []
    primary = max(4, min(7, round(5 * detail)))
    for index in range(primary):
        angle = 2 * math.pi * (index / primary + rng.uniform(-0.045, 0.045))
        direction = (math.cos(angle), math.sin(angle))
        side = (-direction[1], direction[0])
        reach = rng.uniform(0.48, 0.66)
        bend = rng.uniform(-0.30, 0.30)
        c1 = (
            root[0] + direction[0] * reach * 0.22 + side[0] * bend,
            root[1] + direction[1] * reach * 0.22 + side[1] * bend,
        )
        c2 = (
            root[0] + direction[0] * reach * 0.70 - side[0] * bend * 1.18,
            root[1] + direction[1] * reach * 0.70 - side[1] * bend * 1.18,
        )
        tip = (
            root[0] + direction[0] * reach + side[0] * bend * 0.42,
            root[1] + direction[1] * reach + side[1] * bend * 0.42,
        )
        parent = TendrilBranch(
            root,
            (c1, c2, tip),
            rng.uniform(0.020, 0.031) * math.sqrt(detail),
            0.03 + rng.uniform(0, 0.08),
            0.50 + rng.uniform(0, 0.16),
        )
        branches.append(parent)
        for child in range(2):
            join = 0.43 + child * 0.22 + rng.uniform(-0.05, 0.05)
            origin = _bezier(parent, join)
            tangent = (tip[0] - root[0], tip[1] - root[1])
            length = math.hypot(*tangent)
            tangent = (tangent[0] / length, tangent[1] / length)
            sign = -1.0 if child == 0 else 1.0
            ca = math.atan2(tangent[1], tangent[0]) + sign * rng.uniform(0.48, 0.92)
            d = (math.cos(ca), math.sin(ca))
            reach2 = reach * rng.uniform(0.28, 0.48)
            side2 = (-d[1], d[0])
            child_tip = (origin[0] + d[0] * reach2, origin[1] + d[1] * reach2)
            child_start = parent.start + (parent.end - parent.start) * join
            branches.append(
                TendrilBranch(
                    origin,
                    (
                        (
                            origin[0] + d[0] * reach2 * 0.22 + side2[0] * sign * 0.10,
                            origin[1] + d[1] * reach2 * 0.22 + side2[1] * sign * 0.10,
                        ),
                        (
                            origin[0] + d[0] * reach2 * 0.76 - side2[0] * sign * 0.12,
                            origin[1] + d[1] * reach2 * 0.76 - side2[1] * sign * 0.12,
                        ),
                        child_tip,
                    ),
                    parent.radius * rng.uniform(0.43, 0.62),
                    child_start,
                    min(0.94, parent.end + rng.uniform(0.10, 0.23)),
                )
            )
    return tuple(branches)


def tendril_tube_vertices(
    branches: tuple[TendrilBranch, ...],
    *,
    rings: int = 32,
    sides: int = 16,
    aspect: float = 1.0,
) -> tuple[float, ...]:
    """Closed round tubes, bounded to 21 branches at production admission."""
    if not branches or rings < 3 or sides < 5:
        raise ValueError("bounded tube topology requires branches, rings and sides")
    out = []
    for branch in branches:
        points = [_bezier(branch, i / (rings - 1)) for i in range(rings)]

        def emit(ri: int, si: int) -> None:
            point = points[ri]
            before = points[max(0, ri - 1)]
            after = points[min(rings - 1, ri + 1)]
            tx, ty = (after[0] - before[0]) * aspect, after[1] - before[1]
            length = max(math.hypot(tx, ty), 1e-5)
            nx, ny = -ty / length, tx / length
            angle = 2 * math.pi * si / sides
            along = ri / (rings - 1)
            taper = 1.0 - 0.93 * along
            radial = branch.radius * taper
            x = point[0] + nx * math.cos(angle) * radial / aspect
            y = point[1] + ny * math.cos(angle) * radial
            lift = 0.11 * math.sin(math.pi * along)
            z = lift + math.sin(angle) * radial
            out.extend(
                (
                    x,
                    y,
                    z,
                    point[0],
                    point[1],
                    nx * math.cos(angle),
                    ny * math.cos(angle),
                    math.sin(angle),
                    branch.root[0],
                    branch.root[1],
                    lift,
                    branch.start + (branch.end - branch.start) * ri / (rings - 1),
                )
            )

        def emit_cap_center(ri: int) -> None:
            point = points[ri]
            before = points[max(0, ri - 1)]
            after = points[min(rings - 1, ri + 1)]
            tx, ty = (after[0] - before[0]) * aspect, after[1] - before[1]
            length = max(math.hypot(tx, ty), 1e-5)
            out.extend(
                (
                    point[0],
                    point[1],
                    0.0,
                    point[0],
                    point[1],
                    -ty / length,
                    tx / length,
                    0.0,
                    branch.root[0],
                    branch.root[1],
                    0.0,
                    branch.start + (branch.end - branch.start) * ri / (rings - 1),
                )
            )

        for ring in range(rings - 1):
            for side in range(sides):
                for ri, si in (
                    (ring, side),
                    (ring + 1, side),
                    (ring + 1, (side + 1) % sides),
                    (ring, side),
                    (ring + 1, (side + 1) % sides),
                    (ring, (side + 1) % sides),
                ):
                    emit(ri, si)
        # Cap both ends with the same finite tube attributes; the pointed tip
        # reads as a living tendril rather than an open ribbon.
        for ri, reverse in ((0, False), (rings - 1, True)):
            for side in range(sides):
                sequence = ((ri, side), (ri, (side + 1) % sides))
                if reverse:
                    sequence = tuple(reversed(sequence))
                emit_cap_center(ri)
                for ring_index, side_index in sequence:
                    emit(ring_index, side_index)
    return tuple(out)


def tendril_canopy_segments(
    branches: tuple[TendrilBranch, ...], *, segments_per_branch: int = 5
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Sample the exact tube Beziers into at most 105 immutable canopy arcs."""
    if not 1 <= segments_per_branch <= 5:
        raise ValueError("canopy segment sampling must stay bounded at five")
    if len(branches) > 21:
        raise ValueError("canopy supports at most twenty-one rooted branches")
    starts: list[float] = []
    ends: list[float] = []
    for branch in branches:
        for index in range(segments_per_branch):
            a = index / segments_per_branch
            b = (index + 1) / segments_per_branch
            start = _bezier(branch, a)
            end = _bezier(branch, b)
            arrival_a = branch.start + (branch.end - branch.start) * a
            arrival_b = branch.start + (branch.end - branch.start) * b
            starts.extend((*start, arrival_a, branch.radius))
            ends.extend((*end, arrival_b, branch.radius))
    return tuple(starts), tuple(ends)


TENDRIL_VERTEX = """#version 410 core
layout(location=0) in vec3 aPosition; layout(location=1) in vec2 aUv; layout(location=2) in vec3 aNormal;
layout(location=3) in vec3 aRoot; layout(location=4) in float aGrowth;
uniform mat4 uMatrix; uniform vec2 uItemSize; uniform float uProgress; uniform float uDepth;
noperspective out vec2 vUv; out vec3 vNormal; out float vRelief;
void main() {
    float growth=smoothstep(aGrowth-.055,aGrowth+.025,uProgress);
    float swelling=.85+.55*smoothstep(.15,.65,uProgress);
    float settle=1.-smoothstep(.68,.96,uProgress);
    // Unreached rings collapse onto their own centreline, not the root. This
    // leaves a rounded growing tip instead of stretched root-to-tip triangles.
    vec3 position=vec3(aUv,aRoot.z)+vec3(aPosition.xy-aUv,aPosition.z-aRoot.z)*swelling*growth;
    position.z*=settle*(.25+.75*uDepth);
    float aspect=uItemSize.x/uItemSize.y, w=3.-position.z;
    vec2 uv=(position.xy-.5)*3./w+.5;
    vec4 clip=uMatrix*vec4(uv*uItemSize,0.,1.); clip*=w;
    clip.z=-position.z/5.*clip.w;
    gl_Position=clip;
    vUv=uv;
    vNormal=normalize(vec3(aNormal.x,-aNormal.y,aNormal.z/max(.04,settle*(.25+.75*uDepth))));
    vRelief=settle*growth;
}
"""
TENDRIL_FRAGMENT = """#version 410 core
noperspective in vec2 vUv; in vec3 vNormal; in float vRelief; out vec4 FragColor;
uniform sampler2D uNewTex; uniform float uGloss;
void main() {
    vec3 normal=normalize(vNormal), light=normalize(vec3(-.42,.65,.83));
    if(normal.z<0.) normal=-normal;
    vec3 image=texture(uNewTex,clamp(vUv+normal.xy*.003*vRelief,0.,1.)).rgb;
    float diffuse=.48+.52*max(dot(normal,light),0.);
    float rim=pow(1.-max(normal.z,0.),2.2);
    float spec=pow(max(dot(normalize(light+vec3(0,0,1)),normal),0.),mix(10.,72.,uGloss));
    vec3 material=image*(diffuse+.10*rim)+vec3(.80,.91,1.)*spec*uGloss*.58;
    // As the connected canopy spreads, tube relief settles into the exact
    // destination. No pre-endpoint renderer cut can conceal a residual tube.
    FragColor=vec4(mix(image,material,vRelief),1.);
}
"""

TENDRIL_CANOPY_FRAGMENT = """#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float uProgress;
uniform float uDetail;
uniform float uDepth;
uniform float uGloss;
uniform float uAspect;
uniform int uSegmentCount;
uniform vec4 uSegmentsA[105];
uniform vec4 uSegmentsB[105];

float segmentDistance(vec2 p, vec2 a, vec2 b) {
    vec2 ab=b-a;
    return length(p-(a+ab*clamp(dot(p-a,ab)/max(dot(ab,ab),.00001),0.,1.)));
}
float branchField(vec2 uv, float time, float detail) {
    vec2 p=(uv-vec2(.5))*vec2(uAspect,1.);
    float nearest=9.;
    for(int index=0; index<105; ++index) {
        if(index>=uSegmentCount) break;
        vec4 a=uSegmentsA[index], b=uSegmentsB[index];
        float segmentActive=smoothstep(a.z-.025,a.z+.025,time);
        if(segmentActive<=.0001) continue;
        float arrived=smoothstep(a.z-.035,b.z+.025,time);
        vec2 tip=mix(a.xy,b.xy,arrived);
        vec2 physicalA=(a.xy-vec2(.5))*vec2(uAspect,1.);
        vec2 physicalB=(tip-vec2(.5))*vec2(uAspect,1.);
        float expansion=.003+length(vec2(uAspect*.5,.5))*1.3*pow(smoothstep(.42,.98,time),2.4);
        nearest=min(nearest,segmentDistance(p,physicalA,physicalB)-(a.w*.80+expansion*(.78+.22*detail)));
    }
    return nearest;
}
void main() {
    vec2 uv=vec2(vUv.x,1.-vUv.y); float t=clamp(uProgress,0.,1.);
    if(t<=0.) { FragColor=texture(uOldTex,uv); return; }
    if(t>=1.) { FragColor=texture(uNewTex,uv); return; }
    float field=branchField(uv,t,uDetail);
    float aa=max(fwidth(field)*1.35,.00075);
    float cover=1.-smoothstep(-aa,aa,field);
    if(cover<=.0001) discard;
    vec2 normal=normalize(vec2(dFdx(field),dFdy(field))+vec2(.00001));
    float rim=exp(-78.*abs(field));
    vec3 old=texture(uOldTex,uv).rgb;
    vec3 revealed=texture(uNewTex,clamp(uv-normal*(.003+.009*uDepth)*rim,0.,1.)).rgb;
    vec3 light=normalize(vec3(-.42,.68,.86));
    float spec=pow(max(dot(normalize(vec3(-normal,.45+.8*uDepth)),light),0.),mix(12.,76.,uGloss));
    vec3 material=mix(old,revealed,cover);
    material*=1.-.12*rim*(1.-cover);
    material+=revealed*spec*(.10+.28*uGloss)*rim;
    FragColor=vec4(material,1.);
}
"""
