"""Static beveled-slab mesh and analytic departure contract for Exploding Tiles."""

from __future__ import annotations

import math
from collections.abc import Mapping


EXPLODING_TILES_VERTEX_STRIDE_FLOATS = 8


def _triangle(result, first, second, third, normal) -> None:
    for position, uv in (first, second, third):
        result.extend((*position, *normal, *uv))


def exploding_tiles_box_vertices(bevel: float = 0.12) -> tuple[float, ...]:
    """Return a unit slab with broad faces and lit bevel bands.

    Depth is unit-relative here. The shader scales it from the physical grid
    cell, so density and viewport aspect cannot create a microscopic extrusion.
    """
    inset = max(0.02, min(0.22, float(bevel)))
    inner = (
        (-0.5 + inset, -0.5),
        (0.5 - inset, -0.5),
        (0.5, -0.5 + inset),
        (0.5, 0.5 - inset),
        (0.5 - inset, 0.5),
        (-0.5 + inset, 0.5),
        (-0.5, 0.5 - inset),
        (-0.5, -0.5 + inset),
    )
    outer = (
        (-0.5, -0.5),
        (0.5, -0.5),
        (0.5, 0.5),
        (-0.5, 0.5),
    )
    result: list[float] = []
    for z, normal, winding in (
        (0.5, (0.0, 0.0, 1.0), 1),
        (-0.5, (0.0, 0.0, -1.0), -1),
    ):
        centre = ((0.0, 0.0, z), (0.5, 0.5))
        for index, point in enumerate(inner):
            following = inner[(index + 1) % len(inner)]
            a = ((point[0], point[1], z), (point[0] + 0.5, point[1] + 0.5))
            b = (
                (following[0], following[1], z),
                (following[0] + 0.5, following[1] + 0.5),
            )
            _triangle(
                result, centre, a if winding > 0 else b, b if winding > 0 else a, normal
            )
    side_indices = ((0, 1), (2, 3), (4, 5), (6, 7))
    for side, (first, second) in enumerate(side_indices):
        point, following = outer[side], outer[(side + 1) % len(outer)]
        inner_point, inner_following = inner[first], inner[second]
        mid_x = (point[0] + following[0] + inner_point[0] + inner_following[0]) * 0.25
        mid_y = (point[1] + following[1] + inner_point[1] + inner_following[1]) * 0.25
        length = math.hypot(mid_x, mid_y)
        normal = (mid_x / length, mid_y / length, 0.45)
        a = ((point[0], point[1], 0.38), (point[0] + 0.5, point[1] + 0.5))
        b = (
            (following[0], following[1], 0.38),
            (following[0] + 0.5, following[1] + 0.5),
        )
        c = (
            (inner_following[0], inner_following[1], 0.5),
            (inner_following[0] + 0.5, inner_following[1] + 0.5),
        )
        d = (
            (inner_point[0], inner_point[1], 0.5),
            (inner_point[0] + 0.5, inner_point[1] + 0.5),
        )
        _triangle(result, a, b, c, normal)
        _triangle(result, a, c, d, normal)
    for corner, previous, following in ((0, 7, 0), (1, 1, 2), (2, 3, 4), (3, 5, 6)):
        point = outer[corner]
        mid_x = point[0] + inner[previous][0] + inner[following][0]
        mid_y = point[1] + inner[previous][1] + inner[following][1]
        length = math.hypot(mid_x, mid_y)
        normal = (mid_x / length, mid_y / length, 0.45)
        a = ((point[0], point[1], 0.38), (point[0] + 0.5, point[1] + 0.5))
        b = (
            (inner[following][0], inner[following][1], 0.5),
            (inner[following][0] + 0.5, inner[following][1] + 0.5),
        )
        c = (
            (inner[previous][0], inner[previous][1], 0.5),
            (inner[previous][0] + 0.5, inner[previous][1] + 0.5),
        )
        _triangle(result, a, b, c, normal)
    for index, point in enumerate(outer):
        following = outer[(index + 1) % len(outer)]
        mid_x, mid_y = (point[0] + following[0]) * 0.5, (point[1] + following[1]) * 0.5
        length = math.hypot(mid_x, mid_y)
        normal = (mid_x / length, mid_y / length, 0.0)
        a = ((point[0], point[1], 0.38), (0.0, 0.0))
        b = ((following[0], following[1], 0.38), (1.0, 0.0))
        c = ((following[0], following[1], -0.38), (1.0, 1.0))
        d = ((point[0], point[1], -0.38), (0.0, 1.0))
        _triangle(result, a, c, b, normal)
        _triangle(result, a, d, c, normal)
    for side, (first, second) in enumerate(side_indices):
        point, following = outer[side], outer[(side + 1) % len(outer)]
        inner_point, inner_following = inner[first], inner[second]
        mid_x = (point[0] + following[0] + inner_point[0] + inner_following[0]) * 0.25
        mid_y = (point[1] + following[1] + inner_point[1] + inner_following[1]) * 0.25
        length = math.hypot(mid_x, mid_y)
        normal = (mid_x / length, mid_y / length, -0.45)
        a = ((point[0], point[1], -0.38), (point[0] + 0.5, point[1] + 0.5))
        b = (
            (following[0], following[1], -0.38),
            (following[0] + 0.5, following[1] + 0.5),
        )
        c = (
            (inner_following[0], inner_following[1], -0.5),
            (inner_following[0] + 0.5, inner_following[1] + 0.5),
        )
        d = (
            (inner_point[0], inner_point[1], -0.5),
            (inner_point[0] + 0.5, inner_point[1] + 0.5),
        )
        _triangle(result, a, c, b, normal)
        _triangle(result, a, d, c, normal)
    for corner, previous, following in ((0, 7, 0), (1, 1, 2), (2, 3, 4), (3, 5, 6)):
        point = outer[corner]
        mid_x = point[0] + inner[previous][0] + inner[following][0]
        mid_y = point[1] + inner[previous][1] + inner[following][1]
        length = math.hypot(mid_x, mid_y)
        normal = (mid_x / length, mid_y / length, -0.45)
        a = ((point[0], point[1], -0.38), (point[0] + 0.5, point[1] + 0.5))
        b = (
            (inner[previous][0], inner[previous][1], -0.5),
            (inner[previous][0] + 0.5, inner[previous][1] + 0.5),
        )
        c = (
            (inner[following][0], inner[following][1], -0.5),
            (inner[following][0] + 0.5, inner[following][1] + 0.5),
        )
        _triangle(result, a, b, c, normal)
    return tuple(result)


EXPLODING_TILES_BOX_VERTICES = exploding_tiles_box_vertices()
EXPLODING_TILES_VERTEX_COUNT = (
    len(EXPLODING_TILES_BOX_VERTICES) // EXPLODING_TILES_VERTEX_STRIDE_FLOATS
)


def exploding_tiles_parameters(
    parameters: Mapping[str, object],
) -> tuple[int, int, float, float, float]:
    """Validate resolved-only tile controls before GL state changes."""
    seed, columns, depth = (
        parameters.get("seed"),
        parameters.get("columns"),
        parameters.get("depth"),
    )
    thickness, force = parameters.get("thickness"), parameters.get("force")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Exploding Tiles seed must be an integer between 1 and 65535")
    if (
        isinstance(columns, bool)
        or not isinstance(columns, int)
        or not 6 <= columns <= 48
    ):
        raise ValueError("Exploding Tiles columns must be an integer between 6 and 48")
    if (
        isinstance(depth, bool)
        or not isinstance(depth, (int, float))
        or not math.isfinite(float(depth))
        or not 0.2 <= float(depth) <= 1.5
    ):
        raise ValueError("Exploding Tiles depth must be finite and between 0.2 and 1.5")
    if (
        isinstance(thickness, bool)
        or not isinstance(thickness, (int, float))
        or not math.isfinite(float(thickness))
        or not 0.0 <= float(thickness) <= 1.0
    ):
        raise ValueError("Exploding Tiles thickness must be finite and between 0 and 1")
    if (
        isinstance(force, bool)
        or not isinstance(force, (int, float))
        or not math.isfinite(float(force))
        or not 0.5 <= float(force) <= 2.0
    ):
        raise ValueError("Exploding Tiles force must be finite and between 0.5 and 2")
    return seed, columns, float(depth), float(thickness), float(force)


def exploding_tiles_grid(columns: int, width: int, height: int) -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("Exploding Tiles requires a positive viewport")
    return int(columns), max(6, min(48, int(round(columns * height / width))))


def exploding_tile_state(progress: float, start: float) -> float:
    """Continuous non-scaling phase, at its exact endpoint by 98%."""
    raw = max(
        0.0,
        min(1.0, (float(progress) - float(start)) / max(0.001, 0.98 - float(start))),
    )
    return raw * raw * (3.0 - 2.0 * raw)


EXPLODING_TILES_VERTEX_SOURCE = """#version 410 core
layout(location=0) in vec3 aPosition;
layout(location=1) in vec3 aNormal;
layout(location=2) in vec2 aUv;
uniform mat4 uMatrix; uniform vec2 uItemSize; uniform vec2 uGrid; uniform vec2 uDirection;
uniform float uProgress; uniform float uSeed; uniform float uDepth; uniform float uThickness; uniform float uForce;
uniform int uCenterOut;
out vec2 vUv; out vec3 vNormal; out float vSurface; out float vMotion;
float hash1(vec2 p) { return fract(sin(dot(p, vec2(127.1,311.7))+uSeed)*43758.5453123); }
vec3 rotateAxis(vec3 p, vec3 axis, float angle) {
    float c=cos(angle), s=sin(angle); return p*c+cross(axis,p)*s+axis*dot(axis,p)*(1.-c);
}
void main() {
    float id=float(gl_InstanceID), col=mod(id,uGrid.x), row=floor(id/uGrid.x);
    vec2 cell=vec2(col,row), centre=(cell+vec2(.5))/uGrid;
    vec2 direction=uCenterOut==1 ? vec2(0.) : normalize(uDirection);
    float wave=uCenterOut==1 ? length(centre-vec2(.5))*1.41421356 : dot(centre-vec2(.5),direction)+.5;
    float begin=clamp(.025+wave*.43+(hash1(cell)-.5)*.08,0.,.52);
    float raw=clamp((uProgress-begin)/max(.001,.98-begin),0.,1.);
    float local=raw*raw*(3.-2.*raw), randomA=hash1(cell+17.), randomB=hash1(cell+43.);
    vec3 axis=normalize(vec3(hash1(cell+2.)*2.-1.,hash1(cell+5.)*2.-1.,hash1(cell+9.)*2.-1.));
    float aspect=uItemSize.x/uItemSize.y;
    vec2 radial=normalize(centre-vec2(.5)+vec2(.0001));
    vec2 launch=uCenterOut==1 ? radial : normalize(direction+radial*(.18+.12*randomA));
    vec2 worldDirection=normalize(vec2(launch.x*aspect,-launch.y));
    vec2 tile=vec2(aspect/uGrid.x,1./uGrid.y);
    float slabDepth=min(tile.x,tile.y)*(.10+.90*uThickness)*local;
    vec3 localPosition=vec3(aPosition.x*tile.x,-aPosition.y*tile.y,aPosition.z*slabDepth);
    float angle=local*uForce*(4.6+3.6*randomA);
    localPosition=rotateAxis(localPosition,axis,angle);
    vec3 normal=normalize(rotateAxis(vec3(aNormal.x,-aNormal.y,aNormal.z),axis,angle));
    float lift=local*(.08+.36*randomB)*uDepth;
    float gravity=local*local*(.24+.20*randomA)*uForce;
    vec3 position=vec3((centre.x-.5)*aspect,.5-centre.y,0.)+localPosition;
    vec2 expanded=vec2(aspect*.5,.5)+vec2(length(tile)*2.+slabDepth);
    vec2 edge=(sign(worldDirection)*expanded-vec2((centre.x-.5)*aspect,.5-centre.y))/worldDirection;
    if(abs(worldDirection.x)<.00001) edge.x=1e5;
    if(abs(worldDirection.y)<.00001) edge.y=1e5;
    float exitDistance=min(edge.x,edge.y);
    position.xy+=worldDirection*(exitDistance+.35+.65*uForce)*local*local;
    position.y-=gravity; position.z+=lift;
    float cameraW=max(1.65,3.4-position.z);
    vec2 uv=vec2(position.x/aspect,-position.y)*3.4/cameraW+.5;
    vec4 projected=uMatrix*vec4(uv*uItemSize,0.,1.); projected*=cameraW;
    projected.z=clamp(-position.z/5.,-.9,.9)*projected.w; gl_Position=projected;
    vUv=(cell+aUv)/uGrid; vNormal=normal; vSurface=aNormal.z; vMotion=local;
}"""

EXPLODING_TILES_FRAGMENT_SOURCE = """#version 410 core
in vec2 vUv; in vec3 vNormal; in float vSurface; in float vMotion;
out vec4 FragColor; uniform sampler2D uOldTex;
void main() {
    vec3 normal=normalize(vNormal), light=normalize(vec3(-.38,.57,.73));
    float diffuse=.22+.78*max(dot(normal,light),0.), bevel=pow(1.-abs(vSurface),1.7);
    vec3 source=texture(uOldTex,vUv).rgb;
    vec3 material=mix(vec3(.055,.075,.105),source*.30+vec3(.035,.045,.065),.35+.45*diffuse);
    vec3 face=source*(.72+.28*diffuse);
    vec3 litBody=vSurface>.5 ? face : material*(.65+.55*diffuse+.22*bevel);
    float edgeLight=bevel*(.10+.26*max(dot(normal,normalize(light+vec3(0.,0.,1.))),0.));
    FragColor=vec4(mix(source,litBody+edgeLight,vMotion),1.);
}"""
