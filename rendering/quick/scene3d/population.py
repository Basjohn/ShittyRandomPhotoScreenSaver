"""A compacted GPU population: the live members of a large deterministic pool, found, evaluated and
counted on the GPU each frame, then drawn with one indirect draw (S16/S18).

A consumer describes its pool with two GLSL hooks over a member id (``0 <= id < population``):

    bool populationActive(uint id);   // is the member live at this frame?
    vec4 populationState(uint id);    // its state for the draw (evaluated once per live member)

plus whatever uniforms the hooks read. Every frame ``update`` runs three dispatches:

1. count: each workgroup of ``POPULATION_GROUP`` members counts its live members;
2. scan: one workgroup turns the counts into each group's first slot and writes the indirect
   command (vertices per member, live count) itself, so the count never comes back to the CPU;
3. scatter: each live member writes its id and its state to its slot, in id order (a
   workgroup prefix sum, not an atomic append), so the draw order, and with it any
   order-dependent blending, is the same every frame and on every GPU: no shimmer when
   membership changes.

The draw reads ``populationIds[gl_InstanceID]`` and ``populationStates[gl_InstanceID]``
(``POPULATION_DRAW_GLSL``). Capacity is fixed per allocation: a population larger than the
capacity is a loud error. Each dispatch owns the barrier its reader needs. Nothing is
allocated or dispatched until a consumer asks; ``release`` returns everything to zero.
"""
from __future__ import annotations

import ctypes
from contextlib import contextmanager
from functools import lru_cache
from typing import Callable, Iterator

from OpenGL import GL as gl

from rendering.quick import gl_query

from .compute import dispatch

POPULATION_GROUP = 256
_SCAN_INVOCATIONS = 1024
# Storage binding points used while a population is bound (restored afterwards).
POPULATION_FIRST_BINDING = 3
_COUNTS, _OFFSETS, _COMMAND, _IDS, _STATES = range(POPULATION_FIRST_BINDING, POPULATION_FIRST_BINDING + 5)

_BUFFERS_GLSL = f"""
layout(std430, binding = {_COUNTS}) buffer PopulationCounts {{ uint populationCounts[]; }};
layout(std430, binding = {_OFFSETS}) buffer PopulationOffsets {{ uint populationOffsets[]; }};
layout(std430, binding = {_COMMAND}) buffer PopulationCommand {{ uint populationCommand[4]; }};
layout(std430, binding = {_IDS}) buffer PopulationIds {{ uint populationIds[]; }};
layout(std430, binding = {_STATES}) buffer PopulationStates {{ vec4 populationStates[]; }};
"""

# For the consumer's draw: the live members in id order.
POPULATION_DRAW_GLSL = f"""
layout(std430, binding = {_IDS}) readonly buffer PopulationIds {{ uint populationIds[]; }};
layout(std430, binding = {_STATES}) readonly buffer PopulationStates {{ vec4 populationStates[]; }};
"""


@lru_cache(maxsize=16)
def population_count_source(hooks: str) -> str:
    return (f"#version 460 core\nlayout(local_size_x = {POPULATION_GROUP}) in;\n" + _BUFFERS_GLSL
            + "uniform uint uPopulation;\n" + hooks + """
shared uint groupLive;
void main() {
    if (gl_LocalInvocationIndex == 0u) groupLive = 0u;
    barrier();
    uint id = gl_GlobalInvocationID.x;
    if (id < uPopulation && populationActive(id)) atomicAdd(groupLive, 1u);
    barrier();
    if (gl_LocalInvocationIndex == 0u) populationCounts[gl_WorkGroupID.x] = groupLive;
}
""")


POPULATION_SCAN_SOURCE = (
    f"#version 460 core\nlayout(local_size_x = {_SCAN_INVOCATIONS}) in;\n" + _BUFFERS_GLSL
    + f"""uniform uint uGroups;
uniform uint uVertices;
shared uint sums[{_SCAN_INVOCATIONS}];
void main() {{
    uint i = gl_LocalInvocationIndex;
    uint per = (uGroups + {_SCAN_INVOCATIONS - 1}u) / {_SCAN_INVOCATIONS}u;
    uint begin = min(i * per, uGroups), end = min(begin + per, uGroups);
    uint local = 0u;
    for (uint g = begin; g < end; ++g) local += populationCounts[g];
    sums[i] = local;
    barrier();
    for (uint step = 1u; step < {_SCAN_INVOCATIONS}u; step <<= 1u) {{
        uint value = i >= step ? sums[i - step] : 0u;
        barrier();
        sums[i] += value;
        barrier();
    }}
    uint running = sums[i] - local;
    for (uint g = begin; g < end; ++g) {{
        populationOffsets[g] = running;
        running += populationCounts[g];
    }}
    if (i == {_SCAN_INVOCATIONS - 1}u) {{
        populationCommand[0] = uVertices;
        populationCommand[1] = sums[i];
        populationCommand[2] = 0u;
        populationCommand[3] = 0u;
    }}
}}
"""
)


@lru_cache(maxsize=16)
def population_scatter_source(hooks: str) -> str:
    return (f"#version 460 core\nlayout(local_size_x = {POPULATION_GROUP}) in;\n" + _BUFFERS_GLSL
            + "uniform uint uPopulation;\n" + hooks + f"""
shared uint before[{POPULATION_GROUP}];
void main() {{
    uint i = gl_LocalInvocationIndex;
    uint id = gl_GlobalInvocationID.x;
    bool live = id < uPopulation && populationActive(id);
    before[i] = live ? 1u : 0u;
    barrier();
    for (uint step = 1u; step < {POPULATION_GROUP}u; step <<= 1u) {{
        uint value = i >= step ? before[i - step] : 0u;
        barrier();
        before[i] += value;
        barrier();
    }}
    if (live) {{
        uint slot = populationOffsets[gl_WorkGroupID.x] + before[i] - 1u;
        populationIds[slot] = id;
        populationStates[slot] = populationState(id);
    }}
}}
""")


@lru_cache(maxsize=16)
def population_programs(key: str, hooks: str) -> tuple[tuple[str, str], ...]:
    """(key, compute source) of the three programs a population with these hooks uses (for warm-up)."""
    return ((f"{key}_count", population_count_source(hooks)),
            ("population_scan", POPULATION_SCAN_SOURCE),
            (f"{key}_scatter", population_scatter_source(hooks)))


class CompactedPopulation:
    def __init__(self, label: str) -> None:
        self.label = label
        self._names: dict[int, int] = {}      # binding -> buffer
        self._capacity = 0
        self._groups = 0
        self._population = 0
        # The population's own uniform locations, per linked program (the hooks' belong to the consumer).
        self._locations: dict[tuple[int, str], int] = {}
        # Values those uniforms hold: constant through a run, so set only when they change.
        self._values: dict[tuple[int, str], int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._names)

    @property
    def capacity(self) -> int:
        return self._capacity

    def warm(self, capacity: int) -> bool:
        """Allocate for ``capacity`` members if not yet (ahead of a run, or at first use); True if it was."""
        if capacity < 1:
            raise ValueError(f"{self.label}: a population needs at least one member")
        if self._names and self._capacity == capacity:
            return True
        self.release()
        groups = -(-capacity // POPULATION_GROUP)
        sizes = {_COUNTS: 4 * groups, _OFFSETS: 4 * groups, _COMMAND: 16, _IDS: 4 * capacity, _STATES: 16 * capacity}
        try:
            for binding, size in sizes.items():
                name = (ctypes.c_uint * 1)()
                gl.glCreateBuffers(1, name)
                if not name[0]:
                    raise RuntimeError(f"{self.label} population buffer allocation failed")
                self._names[binding] = int(name[0])
                gl.glNamedBufferStorage(self._names[binding], size, None, 0)
        except Exception:
            self.release()
            raise
        self._capacity, self._groups = capacity, groups
        return False

    @contextmanager
    def bound(self) -> Iterator[None]:
        """Bind the population's storage buffers and indirect command for the scope; restore after."""
        if not self._names:
            raise RuntimeError(f"{self.label} population is not allocated")
        target = gl.GL_SHADER_STORAGE_BUFFER
        bindings = sorted(self._names)
        # Range queries only for points something is actually bound to (usually none).
        previous = []
        for b in bindings:
            name = gl_query.get_indexed_int(gl.GL_SHADER_STORAGE_BUFFER_BINDING, b)
            previous.append((name, gl_query.get_indexed_int64(gl.GL_SHADER_STORAGE_BUFFER_START, b),
                             gl_query.get_indexed_int64(gl.GL_SHADER_STORAGE_BUFFER_SIZE, b)) if name else (0, 0, 0))
        indirect = gl_query.get_int(gl.GL_DRAW_INDIRECT_BUFFER_BINDING)
        names = (ctypes.c_uint * len(bindings))(*(self._names[b] for b in bindings))
        gl.glBindBuffersBase(target, bindings[0], len(bindings), names)
        gl.glBindBuffer(gl.GL_DRAW_INDIRECT_BUFFER, self._names[_COMMAND])
        try:
            yield
        finally:
            gl.glBindBuffer(gl.GL_DRAW_INDIRECT_BUFFER, indirect)
            if not any(name for name, _start, _size in previous):
                gl.glBindBuffersBase(target, bindings[0], len(bindings), (ctypes.c_uint * len(bindings))())
            else:
                for binding, (name, start, size) in zip(bindings, previous):
                    if name and size:
                        gl.glBindBufferRange(target, binding, name, start, size)
                    else:
                        gl.glBindBufferBase(target, binding, name)

    def update(self, resources, key: str, hooks: str, population: int, vertices: int,
               configure: Callable[[str, int], None]) -> None:
        """Find, evaluate and count this frame's live members (inside ``bound``).

        ``configure(program_key, program)`` sets the hooks' uniforms on each hook program."""
        if population < 1 or population > self._capacity:
            raise RuntimeError(f"{self.label}: population {population} exceeds its capacity {self._capacity}")
        self._population = population
        groups = -(-population // POPULATION_GROUP)
        (count_key, count), (scan_key, scan), (scatter_key, scatter) = population_programs(key, hooks)
        # Each pass's reader: the next pass's storage reads; the draw's storage and command reads.
        for program_key, source, barrier in (
                (count_key, count, gl.GL_SHADER_STORAGE_BARRIER_BIT),
                (scan_key, scan, gl.GL_SHADER_STORAGE_BARRIER_BIT),
                (scatter_key, scatter, gl.GL_SHADER_STORAGE_BARRIER_BIT | gl.GL_COMMAND_BARRIER_BIT)):
            program = resources.compute_program(program_key, source)
            gl.glUseProgram(program)
            if program_key == scan_key:
                self._set(program, "uGroups", groups)
                self._set(program, "uVertices", vertices)
                dispatch((1, 1, 1), barrier)
                continue
            self._set(program, "uPopulation", population)
            configure(program_key, program)
            dispatch((groups, 1, 1), barrier)

    def _set(self, program: int, name: str, value: int) -> None:
        """Set one of the population's own uints on the program in use, unless it already holds it."""
        if self._values.get((program, name)) != value:
            gl.glUniform1ui(self._location(program, name), value)
            self._values[(program, name)] = value

    def _location(self, program: int, name: str) -> int:
        key = (program, name)
        location = self._locations.get(key)
        if location is None:
            location = int(gl.glGetUniformLocation(program, name))
            if location < 0:
                raise RuntimeError(f"{self.label}: population program lacks {name}")
            self._locations[key] = location
        return location

    def draw(self, mode: int) -> None:
        """Draw the live members with the program in use (inside ``bound``, after ``update``)."""
        gl.glDrawArraysIndirect(mode, ctypes.c_void_p(0))

    def release(self) -> None:
        """Delete the buffers; a failed deletion keeps its name for a retry."""
        for binding, name in tuple(self._names.items()):
            gl.glDeleteBuffers(1, [name])
            del self._names[binding]
        self._capacity = self._groups = self._population = 0
        self._locations.clear()   # program names may be reused after their owner releases them
        self._values.clear()
