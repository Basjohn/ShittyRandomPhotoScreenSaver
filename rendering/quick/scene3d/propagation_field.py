"""Propagation field: a per-run, renderer-owned geodesic arrival map over a cost field.

A shared primitive for anything that spreads through a material along the cheapest way (Capillary
Bloom first: dye racing along paper fibres; burns, frost, cracks or roots could seed it with their
own cost). The consumer gives a GLSL ``float propagationCost(vec2 p)`` (``p`` in picture heights,
centred, y up; cost per picture height, positive) with whatever uniforms it reads, and up to
``PROPAGATION_MAX_SOURCES`` sources (position plus a head start in cost units). Compute stages at a
reduced size (``PROPAGATION_SIZE`` on the longer side, the render's aspect):

1. seed: each texel's cost, and its arrival bounded from above by the straight line to every source
   at the costliest rate (``bound``), so the field is valid from the start;
2. relax (repeated): ``arrival = min(arrival, neighbour + cost between them * step)`` over a 16-
   neighbour stencil (the 8 adjacent plus knight moves, for rounder fronts), in place: the field only
   ever falls and any value read is a true upper bound, so read races only speed convergence. Each
   pass carries improvements about one texel further; ``PROPAGATION_PASSES`` passes cover paths
   across the whole field, by which an arrival front that raced along cheap channels has branched;
3. extent: one workgroup reduces the field to its largest arrival, in a 1x1 texture the consumer
   reads with ``texelFetch`` (no readback), to time the spread so the last point arrives on time.

The build is split into bounded steps (``build_step``) so a consumer's gradual warm-up can run it
between runs, a few passes per already-rendered frame; ``texture`` finishes whatever is left in
the frame that needs it. Dormancy: nothing exists until warmed for a render size; ``release()`` (at
the consumer's ``park()``) drops every texture.
"""
from __future__ import annotations

import ctypes
import math

from OpenGL import GL as gl

from .compute import bound_image, dispatch

PROPAGATION_SIZE = 256
PROPAGATION_PASSES = 192
PROPAGATION_PASSES_PER_STEP = 48
PROPAGATION_MAX_SOURCES = 8
_GROUP = 16
_REDUCE_GROUP = 256

PROPAGATION_GLSL = """
// Arrival (cost units) at uv, and the field's largest arrival.
float propagationArrival(sampler2D arrival, vec2 uv) { return texture(arrival, uv).r; }
float propagationExtent(sampler2D extent) { return texelFetch(extent, ivec2(0), 0).r; }
"""

_HEADER = (f"#version 460 core\nlayout(local_size_x = {_GROUP}, local_size_y = {_GROUP}) in;\n"
           "uniform ivec2 uSize;\nuniform float uAspect;\n"
           "vec2 fieldPoint(ivec2 q) { vec2 uv = (vec2(q) + 0.5) / vec2(uSize);"
           " return vec2((uv.x - 0.5) * uAspect, 0.5 - uv.y); }\n")


def _seed_source(cost_glsl: str) -> str:
    return (_HEADER + f"uniform vec3 uSources[{PROPAGATION_MAX_SOURCES}];\nuniform int uSourceCount;\n"
            "uniform float uBound;\n"
            "layout(r32f, binding = 0) writeonly uniform image2D uCost;\n"
            "layout(r32f, binding = 1) writeonly uniform image2D uArrival;\n" + cost_glsl + """
void main() {
    ivec2 q = ivec2(gl_GlobalInvocationID.xy);
    if (any(greaterThanEqual(q, uSize))) return;
    vec2 p = fieldPoint(q);
    float arrival = 1e30;
    for (int i = 0; i < uSourceCount; ++i)
        arrival = min(arrival, uSources[i].z + distance(p, uSources[i].xy) * uBound);
    imageStore(uCost, q, vec4(max(propagationCost(p), 1e-3), 0.0, 0.0, 0.0));
    imageStore(uArrival, q, vec4(arrival, 0.0, 0.0, 0.0));
}
""")


_RELAX_COMPUTE = _HEADER + """
layout(r32f, binding = 0) readonly uniform image2D uCost;
layout(r32f, binding = 1) coherent uniform image2D uArrival;
const ivec2 STEPS[16] = ivec2[](ivec2(1, 0), ivec2(-1, 0), ivec2(0, 1), ivec2(0, -1),
                                ivec2(1, 1), ivec2(-1, 1), ivec2(1, -1), ivec2(-1, -1),
                                ivec2(2, 1), ivec2(-2, 1), ivec2(2, -1), ivec2(-2, -1),
                                ivec2(1, 2), ivec2(-1, 2), ivec2(1, -2), ivec2(-1, -2));
void main() {
    ivec2 q = ivec2(gl_GlobalInvocationID.xy);
    if (any(greaterThanEqual(q, uSize))) return;
    float texel = 1.0 / float(uSize.y);          // picture heights per texel
    float here = imageLoad(uCost, q).r;
    float best = imageLoad(uArrival, q).r;
    for (int i = 0; i < 16; ++i) {
        ivec2 n = q + STEPS[i];
        if (any(lessThan(n, ivec2(0))) || any(greaterThanEqual(n, uSize))) continue;
        float step = length(vec2(STEPS[i])) * texel * 0.5 * (here + imageLoad(uCost, n).r);
        best = min(best, imageLoad(uArrival, n).r + step);
    }
    imageStore(uArrival, q, vec4(best, 0.0, 0.0, 0.0));
}
"""

_EXTENT_COMPUTE = f"""#version 460 core
layout(local_size_x = {_REDUCE_GROUP}) in;
uniform ivec2 uSize;
layout(r32f, binding = 0) readonly uniform image2D uArrival;
layout(r32f, binding = 1) writeonly uniform image2D uExtent;
shared float partial[{_REDUCE_GROUP}];
void main() {{
    uint i = gl_LocalInvocationID.x;
    float largest = 0.0;
    for (int index = int(i); index < uSize.x * uSize.y; index += {_REDUCE_GROUP})
        largest = max(largest, imageLoad(uArrival, ivec2(index % uSize.x, index / uSize.x)).r);
    partial[i] = largest;
    barrier();
    for (uint stride = {_REDUCE_GROUP // 2}u; stride > 0u; stride >>= 1u) {{
        if (i < stride) partial[i] = max(partial[i], partial[i + stride]);
        barrier();
    }}
    if (i == 0u) imageStore(uExtent, ivec2(0), vec4(partial[0], 0.0, 0.0, 0.0));
}}
"""


def propagation_size(pixel_size: tuple[int, int]) -> tuple[int, int]:
    """The field's size for a render of ``pixel_size``: its aspect, ``PROPAGATION_SIZE`` on the longer side."""
    width, height = max(1, int(pixel_size[0])), max(1, int(pixel_size[1]))
    scale = PROPAGATION_SIZE / max(width, height)
    return max(1, round(width * scale)), max(1, round(height * scale))


def propagation_programs(name: str, cost_glsl: str) -> list[tuple[str, str]]:
    """(key, compute source) of a consumer's field programs; ``name`` keys its seed variant."""
    return [(f"propagation_seed_{name}", _seed_source(cost_glsl)), ("propagation_relax", _RELAX_COMPUTE),
            ("propagation_extent", _EXTENT_COMPUTE)]


class PropagationField:
    """One run's arrival field over a consumer's cost, built in bounded steps."""

    _ROLES = (("cost", gl.GL_R32F, False), ("arrival", gl.GL_R32F, True), ("extent", gl.GL_R32F, False))

    def __init__(self, label: str, name: str, cost_glsl: str) -> None:
        self.label = label
        self._programs = propagation_programs(name, cost_glsl)
        self._textures: dict[str, int] = {}
        self._size: tuple[int, int] | None = None
        self._key: tuple | None = None
        self._passes = -1          # -1: not seeded; then passes done; None once complete
        self.builds = 0

    @property
    def has_resources(self) -> bool:
        return bool(self._textures)

    @property
    def programs(self) -> list[tuple[str, str]]:
        return list(self._programs)

    def warm(self, pixel_size: tuple[int, int]) -> bool:
        """Allocate for a render of ``pixel_size`` if not yet; True if it already was."""
        size = propagation_size(pixel_size)
        if self._size == size and len(self._textures) == len(self._ROLES):
            return True
        self.release()
        try:
            for role, internal, linear in self._ROLES:
                self._allocate(size if role != "extent" else (1, 1), internal, linear, role)
        except Exception:
            self.release()
            raise
        self._size = size
        return False

    def build_step(self, resources, pixel_size: tuple[int, int], key: tuple, sources, bound: float,
                   set_cost_uniforms, passes: int = PROPAGATION_PASSES_PER_STEP) -> bool:
        """Advance the build for ``key`` by at most ``passes`` relaxation passes; True once complete.

        ``sources``: (x, y, head start) per source; ``bound``: the costliest rate (for the seed's upper
        bound); ``set_cost_uniforms(uniform_location)``: sets the cost function's own uniforms."""
        self.warm(pixel_size)
        if self._key != key:
            self._key, self._passes = key, -1
        if self._passes is None:
            return True
        width, height = self._size
        groups = (-(-width // _GROUP), -(-height // _GROUP), 1)
        t = self._textures
        if self._passes == -1:
            seed_key, seed_source = self._programs[0]
            gl.glUseProgram(resources.compute_program(seed_key, seed_source))
            locate = lambda name: gl.glGetUniformLocation(resources.compute_program(seed_key, seed_source), name)
            gl.glUniform2i(locate("uSize"), width, height)
            gl.glUniform1f(locate("uAspect"), width / height)
            count = min(len(sources), PROPAGATION_MAX_SOURCES)
            gl.glUniform3fv(locate("uSources"), count, [v for source in sources[:count] for v in source])
            gl.glUniform1i(locate("uSourceCount"), count)
            gl.glUniform1f(locate("uBound"), float(bound))
            set_cost_uniforms(locate)
            with bound_image(0, t["cost"], gl.GL_WRITE_ONLY, gl.GL_R32F), \
                    bound_image(1, t["arrival"], gl.GL_WRITE_ONLY, gl.GL_R32F):
                dispatch(groups, gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)
            self._passes = 0
            return False
        relax_key, relax_source = self._programs[1]
        program = resources.compute_program(relax_key, relax_source)
        gl.glUseProgram(program)
        gl.glUniform2i(gl.glGetUniformLocation(program, "uSize"), width, height)
        gl.glUniform1f(gl.glGetUniformLocation(program, "uAspect"), width / height)
        todo = min(passes, PROPAGATION_PASSES - self._passes)
        with bound_image(0, t["cost"], gl.GL_READ_ONLY, gl.GL_R32F), \
                bound_image(1, t["arrival"], gl.GL_READ_WRITE, gl.GL_R32F):
            for _ in range(todo):
                dispatch(groups, gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT)
        self._passes += todo
        if self._passes < PROPAGATION_PASSES:
            return False
        extent_key, extent_source = self._programs[2]
        program = resources.compute_program(extent_key, extent_source)
        gl.glUseProgram(program)
        gl.glUniform2i(gl.glGetUniformLocation(program, "uSize"), width, height)
        with bound_image(0, t["arrival"], gl.GL_READ_ONLY, gl.GL_R32F), \
                bound_image(1, t["extent"], gl.GL_WRITE_ONLY, gl.GL_R32F):
            dispatch((1, 1, 1), gl.GL_TEXTURE_FETCH_BARRIER_BIT)
        self._passes = None
        self.builds += 1
        return True

    def textures(self, resources, pixel_size: tuple[int, int], key: tuple, sources, bound: float,
                 set_cost_uniforms) -> tuple[int, int]:
        """(arrival, extent) for ``key``, finishing in this frame whatever the warm-up left."""
        while not self.build_step(resources, pixel_size, key, sources, bound, set_cost_uniforms,
                                  passes=PROPAGATION_PASSES):
            pass
        return self._textures["arrival"], self._textures["extent"]

    def _allocate(self, size: tuple[int, int], internal: int, linear: bool, role: str) -> None:
        name = (ctypes.c_uint * 1)()
        gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
        texture = int(name[0])
        if not texture:
            raise RuntimeError(f"{self.label} propagation {role} texture allocation failed")
        self._textures[role] = texture
        mode = gl.GL_LINEAR if linear else gl.GL_NEAREST
        for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
            gl.glTextureParameteri(texture, parameter, mode)
        for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
            gl.glTextureParameteri(texture, wrap, gl.GL_CLAMP_TO_EDGE)
        gl.glTextureStorage2D(texture, 1, internal, *size)

    def release(self) -> None:
        errors: list[str] = []
        kept: dict[str, int] = {}
        for role, texture in self._textures.items():
            try:
                gl.glDeleteTextures([texture])
            except Exception as exc:
                errors.append(str(exc))
                kept[role] = texture
        self._textures = kept
        self._size = None
        self._key = None
        self._passes = -1
        if errors:
            raise RuntimeError(f"{self.label} propagation cleanup incomplete: {' | '.join(errors)}")


def propagation_reference(cost, sources, bound: float, passes: int = PROPAGATION_PASSES):
    """CPU mirror (numpy, Jacobi order) of seed + relax on a ``cost`` grid (rows, columns), picture
    heights per texel 1 / rows; ``sources`` (x, y, head start) in picture heights, centred, y up."""
    import numpy as np

    rows, columns = cost.shape
    aspect = columns / rows
    xs = ((np.arange(columns) + 0.5) / columns - 0.5) * aspect
    ys = 0.5 - (np.arange(rows) + 0.5) / rows
    px, py = np.meshgrid(xs, ys)
    arrival = np.full(cost.shape, 1e30)
    for x, y, head in sources:
        arrival = np.minimum(arrival, head + np.hypot(px - x, py - y) * bound)
    texel = 1.0 / rows
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1),
             (2, 1), (-2, 1), (2, -1), (-2, -1), (1, 2), (-1, 2), (1, -2), (-1, -2)]
    for _ in range(passes):
        best = arrival.copy()
        for dx, dy in steps:
            shifted = np.full(cost.shape, np.inf)
            shifted_cost = np.ones(cost.shape)
            ys0, ys1 = max(0, -dy), rows - max(0, dy)
            xs0, xs1 = max(0, -dx), columns - max(0, dx)
            shifted[ys0:ys1, xs0:xs1] = arrival[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
            shifted_cost[ys0:ys1, xs0:xs1] = cost[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
            best = np.minimum(best, shifted + math.hypot(dx, dy) * texel * 0.5 * (cost + shifted_cost))
        if np.array_equal(best, arrival):
            break
        arrival = best
    return arrival
