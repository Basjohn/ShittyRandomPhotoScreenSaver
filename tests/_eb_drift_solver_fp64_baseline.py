"""TEST-ONLY comparison baseline for D4.3: Extruded Bubble's drift solver as it was before D4 (two compute programs
in ``double``, commit 1c145846), kept so the long-horizon tests can run today's ``double`` shader beside the new one
on the same logs. Never imported by product code; delete it once D4 is accepted.

It reads its own geometry, packed from each family's float64 ``source`` as the old drift log packed it (chains as
12 float64, clouds as (start, span), (seed, phase, 0, 0) float32), and the float64 step records (the fields it
reads keep their indices; the fields D4 appended are ignored).
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass, replace

import numpy as np
from OpenGL import GL as gl

from core.constants.extruded_bubble_world import WORLD_UNIT
from rendering.quick import gl_query
from rendering.quick.scene3d.stream import StreamRing
from widgets.spotify_visualizer import extruded_bubble_drift as drift
from widgets.spotify_visualizer.extruded_bubble_drift_log import STEP_FLOATS, STEP_HISTORY, STEP_INDEX, unpack_steps
from widgets.spotify_visualizer.extruded_bubble_material_paths import PATH_NODES

CHAIN_GEOMETRY_DOUBLES = 12
CHAIN_GEOMETRY_BYTES, CLOUD_GEOMETRY_BYTES = 8 * CHAIN_GEOMETRY_DOUBLES, 32
_STEPS, _GEOMETRY, _STATE, _AUX, _OUT, _OLD_GEOMETRY = 8, 9, 10, 11, 12, 13
_CLOUD_GROUP = 256
_R = STEP_INDEX


def fp64_geometry(family):
    """``family`` with the geometry the old programs read, packed from its float64 source."""
    if family.family == "chains":
        base, spans, carry, phases = family.source
        rows = np.zeros((len(spans), CHAIN_GEOMETRY_DOUBLES), dtype=np.float64)
        rows[:, 0:3] = base[:, 0]; rows[:, 3] = spans
        rows[:, 4:7] = base[:, -1]; rows[:, 7] = carry
        rows[:, 8] = phases
    else:
        start, spans, seed, _carry, phases = family.source
        rows = np.zeros((len(spans), 2, 4), dtype=np.float32)
        rows[:, 0, :3] = start; rows[:, 0, 3] = spans
        rows[:, 1, 0] = seed; rows[:, 1, 1] = phases
    return replace(family, geometry=rows.tobytes())


_VELOCITY_GLSL = f"""
const double TAU = 6.283185307179586LF;
float wrapped(double x) {{ return float(x - floor(x / TAU) * TAU); }}
double stepValue(int step, int field) {{ return steps[step * {STEP_FLOATS} + field]; }}
vec3 stepVec(int step, int field) {{
    return vec3(float(stepValue(step, field)), float(stepValue(step, field + 1)), float(stepValue(step, field + 2)));
}}
vec3 driftVelocity(int kind, vec3 world, float phase, double t, vec3 direction, vec3 across, vec3 depthAxis,
                   vec3 origin, float amount) {{
    float meander = kind == 0 ? 1.0 : {drift._STEERED_WANDER};
    double p = double(phase);
    float wander = meander * amount * 0.05 * (sin(wrapped(t * 0.37LF + p)) + 0.6 * sin(wrapped(t * 0.83LF + 2.1LF * p)));
    float deep = meander * amount * 0.015 * sin(wrapped(t * 0.29LF + 1.7LF * p));
    vec3 directed = vec3(0.0);
    if (kind == 1) directed = amount * (-{drift._STEER_SPEED} * across);
    else if (kind == 2) directed = amount * ({drift._STEER_SPEED} * across);
    else if (kind == 3) directed = amount * ({drift._STEER_SPEED} * sqrt(0.5) * (across + depthAxis));
    else if (kind == 6) directed = amount * ({drift._RANDOM_SPEED} * (cos(phase) * across + sin(phase) * depthAxis));
    else if (kind == 4 || kind == 5) {{
        float sway = {drift._SWISH_SPEED} * sin(wrapped(t * {drift._SWISH_RATE}LF - 0.35LF * double(sin(phase))));
        directed = amount * sway * (kind == 4 ? across : depthAxis);
    }} else if (kind == 7 || kind == 8) {{
        vec3 r = world - origin;
        vec3 radial = r - dot(r, direction) * direction;
        float distance = length(radial);
        radial = distance < {1e-3 * WORLD_UNIT} ? cos(phase) * across + sin(phase) * depthAxis : radial / distance;
        vec3 tangent = cross(direction, radial);
        float sign = kind == 8 ? 1.0 : -1.0;
        directed = amount * (sign * {drift._SWIRL_SPEED} * tangent + {drift._SWIRL_WIDEN} * radial);
    }}
    return across * wander + depthAxis * deep + directed;
}}
"""

_COMMON = f"""#version 460 core
layout(std430, binding = {_STEPS}) readonly buffer DriftSteps {{ double steps[]; }};
uniform int uFirstStep;
uniform int uStepCount;
uniform int uFresh;
uniform int uRebase;
uniform double uLastTravel;
uniform int uOutOffset;
"""

CHAIN_COMPUTE = _COMMON + f"""
layout(local_size_x = {PATH_NODES}) in;
layout(std430, binding = {_GEOMETRY}) readonly buffer Geometry {{ double geometry[]; }};
layout(std430, binding = {_OLD_GEOMETRY}) readonly buffer OldGeometry {{ double oldGeometry[]; }};
layout(std430, binding = {_STATE}) buffer Knots {{ vec4 knots[]; }};
layout(std430, binding = {_AUX}) buffer Paths {{ double paths[]; }};
layout(std430, binding = {_OUT}) writeonly buffer Out {{ vec4 outDrift[]; }};
uniform int uOldRows;
shared vec3 sDisplacement[{PATH_NODES}];
shared double sShift;
shared int sMoved;
{_VELOCITY_GLSL}
void main() {{
    int path = int(gl_WorkGroupID.x), knot = int(gl_LocalInvocationID.x), node = path * {PATH_NODES} + knot;
    bool existing = uFresh == 0 && path < uOldRows;
    vec3 displacement = existing ? knots[node].xyz : vec3(0.0);
    double shift = existing ? paths[path * 2] : 0.0LF, phaseOffset = existing ? paths[path * 2 + 1] : 0.0LF;
    int g = path * {CHAIN_GEOMETRY_DOUBLES};
    vec3 start = vec3(geometry[g], geometry[g + 1], geometry[g + 2]);
    vec3 end = vec3(geometry[g + 4], geometry[g + 5], geometry[g + 6]);
    double span = geometry[g + 3], carry = geometry[g + 7];
    float phase = float(geometry[g + 8]);
    double progress = double(knot - 1) / double({PATH_NODES - 3});
    if (existing && uRebase == 1) {{
        vec3 oldStart = vec3(oldGeometry[g], oldGeometry[g + 1], oldGeometry[g + 2]);
        vec3 oldEnd = vec3(oldGeometry[g + 4], oldGeometry[g + 5], oldGeometry[g + 6]);
        double oldTravel = uLastTravel * oldGeometry[g + 7];
        phaseOffset = mod(phaseOffset + oldTravel / oldGeometry[g + 3] - oldTravel / span, 1.0LF);
        float q = float(progress + shift);
        displacement += (oldStart + (oldEnd - oldStart) * q) - (start + (end - start) * q);
    }}
    for (int s = uFirstStep; s < uFirstStep + uStepCount; ++s) {{
        double dt = stepValue(s, {_R['dt']}), speed = stepValue(s, {_R['speed']}) * carry;
        double rate = speed / span;
        if (knot == 0) {{
            double shifted = shift + rate * dt, stepSize = 1.0LF / double({PATH_NODES - 3});
            double moved = floor(shifted / stepSize + 1e-10LF);
            sShift = shifted - moved * stepSize;
            sMoved = int(moved);
        }}
        sDisplacement[knot] = displacement;
        barrier();
        shift = sShift;
        int moved = sMoved;
        if (moved > 0)
            displacement = knot - moved >= 0 ? sDisplacement[knot - moved] : vec3(0.0);
        barrier();
        double q = progress + shift;
        vec3 world = start + (end - start) * float(q) + displacement;
        vec3 field = driftVelocity(int(stepValue(s, {_R['kind']})), world, phase, stepValue(s, {_R['phase']}),
                                   stepVec(s, {_R['direction_x']}), stepVec(s, {_R['across_x']}),
                                   stepVec(s, {_R['depth_x']}), stepVec(s, {_R['origin_x']}),
                                   float(stepValue(s, {_R['amount_chains']})));
        double available = max(0.0LF, min(dt, q / max(rate, 1e-12LF)));
        displacement += field * float(available);
        if (q <= 0.0LF) displacement = vec3(0.0);
    }}
    knots[node] = vec4(displacement, 0.0);
    if (knot == 0) {{ paths[path * 2] = shift; paths[path * 2 + 1] = phaseOffset; }}
    outDrift[uOutOffset + node] = vec4(displacement, knot == 0 ? float(shift) : knot == 1 ? float(phaseOffset) : 0.0);
}}
"""

CLOUD_COMPUTE = _COMMON + f"""
layout(local_size_x = {_CLOUD_GROUP}) in;
layout(std430, binding = {_GEOMETRY}) readonly buffer Geometry {{ vec4 geometry[]; }};
layout(std430, binding = {_OLD_GEOMETRY}) readonly buffer OldGeometry {{ vec4 oldGeometry[]; }};
layout(std430, binding = {_STATE}) buffer Motes {{ vec4 motes[]; }};
layout(std430, binding = {_AUX}) buffer Bases {{ vec4 bases[]; }};
layout(std430, binding = {_OUT}) writeonly buffer Out {{ vec4 outDrift[]; }};
uniform int uCapacity;
uniform int uOldCount;
uniform int uCountField;
uniform int uAmountField;
uniform double uCarry;
uniform double uOldCarry;
{_VELOCITY_GLSL}
void main() {{
    int id = int(gl_GlobalInvocationID.x);
    if (id >= uCapacity) return;
    bool alive = uFresh == 0 && id < uOldCount;
    vec4 mote = alive ? motes[id] : vec4(0.0);
    vec3 displacement = mote.xyz, previousBase = alive ? bases[id].xyz : vec3(0.0);
    double phaseOffset = double(mote.w), lastTravel = uLastTravel;
    vec4 g0 = geometry[id * 2], g1 = geometry[id * 2 + 1];
    vec3 start = g0.xyz;
    double span = double(g0.w), seed = double(g1.x);
    float phase = g1.y;
    if (alive && uRebase == 1) {{
        double oldSpan = double(oldGeometry[id * 2].w);
        phaseOffset = mod(phaseOffset + lastTravel * uOldCarry / oldSpan - lastTravel * uCarry / span, 1.0LF);
        double previousQ = mod(seed + lastTravel * uCarry / span + phaseOffset, 1.0LF);
        vec3 direction = stepVec(uFirstStep, {_R['direction_x']});
        displacement += previousBase - (start + direction * float(previousQ * span));
    }}
    float packedProgress = 0.0;
    bool first = uFresh == 1;
    for (int s = uFirstStep; s < uFirstStep + uStepCount; ++s) {{
        int count = int(stepValue(s, uCountField));
        if (id >= count) {{ alive = false; displacement = vec3(0.0); phaseOffset = 0.0LF; first = false;
                            lastTravel = stepValue(s, {_R['travel']}); continue; }}
        if (!alive) {{ displacement = vec3(0.0); phaseOffset = 0.0LF; alive = true; }}
        double travel = stepValue(s, {_R['travel']}), dt = stepValue(s, {_R['dt']});
        double speed = stepValue(s, {_R['speed']});
        double previousQ = mod(seed + lastTravel * uCarry / span + phaseOffset, 1.0LF);
        double progress = mod(seed + travel * uCarry / span + phaseOffset, 1.0LF);
        bool recycled = !first && (progress < previousQ - 1e-10LF || (travel - lastTravel) * uCarry / span >= 1.0LF);
        if (recycled) displacement = vec3(0.0);
        vec3 direction = stepVec(s, {_R['direction_x']});
        vec3 base = start + direction * float(progress * span);
        vec3 field = driftVelocity(int(stepValue(s, {_R['kind']})), base + displacement, phase,
                                   stepValue(s, {_R['phase']}), direction, stepVec(s, {_R['across_x']}),
                                   stepVec(s, {_R['depth_x']}), stepVec(s, {_R['origin_x']}),
                                   float(stepValue(s, uAmountField)));
        double available = recycled ? min(dt, progress * span / max(speed * uCarry, 1e-12LF)) : dt;
        displacement += field * float(available);
        previousBase = base;
        lastTravel = travel;
        packedProgress = float(progress - (recycled ? 1.0LF : 0.0LF));
        first = false;
    }}
    motes[id] = vec4(displacement, float(phaseOffset));
    bases[id] = vec4(previousBase, 0.0);
    outDrift[uOutOffset + id] = vec4(displacement, packedProgress);
}}
"""

PROGRAMS = (("drift_chains_fp64_baseline", CHAIN_COMPUTE), ("drift_clouds_fp64_baseline", CLOUD_COMPUTE))
_CLOUD_FIELDS = {"snow": (_R["count_snow"], _R["amount_snow"]), "specks": (_R["count_specks"], _R["amount_specks"])}


def _buffer(size: int) -> int:
    name = (ctypes.c_uint * 1)()
    gl.glCreateBuffers(1, name)
    gl.glNamedBufferStorage(int(name[0]), max(16, size), None, gl.GL_DYNAMIC_STORAGE_BIT)
    return int(name[0])


def _delete(*buffers: int) -> None:
    names = [b for b in buffers if b]
    if names:
        gl.glDeleteBuffers(len(names), names)


@dataclass
class _Family:
    revision: int
    capacity: int
    geometry: int
    state: int
    aux: int
    carry: float
    serial: int = 0
    travel: float = 0.0
    count: int = 0


class Fp64DriftSolver:
    """The old solver, unchanged but for reading ``fp64_geometry`` (its families come in with float64 sources)."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.output = 0
        self._output_vec4s = 0
        self._families: dict[str, _Family] = {}
        self._ring = StreamRing(f"{label} drift steps", slots=4, slot_bytes=4 * 8 * STEP_FLOATS * STEP_HISTORY,
                                hold_bytes=8 * STEP_FLOATS * STEP_HISTORY)
        self._locations: dict[tuple[int, str], int] = {}

    def release(self) -> None:
        for family in self._families.values():
            _delete(family.geometry, family.state, family.aux)
        self._families.clear()
        _delete(self.output)
        self.output, self._output_vec4s = 0, 0
        self._ring.release()
        self._locations.clear()

    @staticmethod
    def layout(families) -> dict[str, int]:
        offsets, cursor = {}, 0
        for family in families:
            offsets[family.family] = cursor
            cursor += family.capacity * (PATH_NODES if family.family == "chains" else 1)
        offsets["_total"] = cursor
        return offsets

    def update(self, resources, families, steps: bytes) -> dict[str, int]:
        families = tuple(fp64_geometry(family) for family in families)
        live = {family.family: family for family in families}
        for name in tuple(self._families):
            if name not in live:
                old = self._families.pop(name)
                _delete(old.geometry, old.state, old.aux)
        offsets = self.layout(families)
        if not live:
            return offsets
        records = unpack_steps(steps)
        serials = records[:, _R["serial"]].astype(np.int64)
        needed = []
        for name, family in live.items():
            state = self._families.get(name)
            after = state.serial if state is not None and (state.revision == family.revision
                                                            or family.rebase_from == state.revision) \
                else family.first_serial - 1
            pending = np.flatnonzero(serials > after)
            if len(pending):
                needed.append(int(pending[0]))
        if not needed:
            return offsets
        if offsets["_total"] > self._output_vec4s:
            _delete(self.output)
            self._output_vec4s = max(256, 1 << (offsets["_total"] - 1).bit_length())
            self.output = _buffer(16 * self._output_vec4s)
        base = min(needed)
        prior_program = gl_query.get_int(gl.GL_CURRENT_PROGRAM)
        try:
            for start in range(base, len(records), STEP_HISTORY):
                upload = records[start:start + STEP_HISTORY]
                with self._ring.bound(gl.GL_SHADER_STORAGE_BUFFER, _STEPS, upload.tobytes()):
                    for name in ("chains", "snow", "specks"):
                        if name in live:
                            self._advance(resources, name, live[name], offsets[name], upload,
                                          serials[start:start + STEP_HISTORY])
        finally:
            gl.glUseProgram(prior_program)
        return offsets

    def _advance(self, resources, name, family, offset, upload, serials) -> None:
        state = self._families.get(name)
        if state is not None and state.revision != family.revision and family.rebase_from == state.revision:
            old_steps = np.flatnonzero((serials > state.serial) & (serials < family.first_serial))
            if len(old_steps):
                self._dispatch(resources, name, state, offset, upload, old_steps, fresh=False)
            replacement = self._allocate(family, state)
            replacement.serial, replacement.travel, replacement.count = state.serial, state.travel, state.count
            self._families[name] = replacement
            pending = np.flatnonzero(serials > replacement.serial)
            if len(pending):
                self._dispatch(resources, name, replacement, offset, upload, pending, fresh=False,
                               old_geometry=state.geometry, old_carry=state.carry)
            _delete(state.geometry, state.state, state.aux)
            return
        fresh = False
        if state is None or state.revision != family.revision:
            if state is not None:
                _delete(state.geometry, state.state, state.aux)
            state = self._allocate(family)
            state.serial = family.first_serial - 1
            fresh = True
        elif family.capacity != state.capacity:
            grown = self._allocate(family, state)
            grown.serial, grown.travel, grown.count = state.serial, state.travel, state.count
            _delete(state.geometry, state.state, state.aux)
            state = grown
        self._families[name] = state
        pending = np.flatnonzero(serials > state.serial)
        if not len(pending):
            return
        if not fresh and int(serials[pending[0]]) != state.serial + 1:
            fresh = True
        self._dispatch(resources, name, state, offset, upload, pending, fresh=fresh)

    def _allocate(self, family, previous: _Family | None = None) -> _Family:
        chains = family.family == "chains"
        geometry = _buffer(len(family.geometry))
        gl.glNamedBufferSubData(geometry, 0, len(family.geometry), family.geometry)
        rows = family.capacity * (PATH_NODES if chains else 1)
        state, aux = _buffer(16 * rows), _buffer(16 * (family.capacity if chains else rows))
        for buffer in (state, aux):
            gl.glClearNamedBufferData(buffer, gl.GL_R32F, gl.GL_RED, gl.GL_FLOAT, None)
        if previous is not None:
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)
            keep = min(previous.capacity, family.capacity)
            gl.glCopyNamedBufferSubData(previous.state, state, 0, 0, 16 * keep * (PATH_NODES if chains else 1))
            gl.glCopyNamedBufferSubData(previous.aux, aux, 0, 0, 16 * keep)
        return _Family(family.revision, family.capacity, geometry, state, aux, float(family.carry))

    def _location(self, program: int, name: str) -> int:
        key = (program, name)
        if key not in self._locations:
            self._locations[key] = int(gl.glGetUniformLocation(program, name))
        return self._locations[key]

    def _dispatch(self, resources, name, state, offset, upload, pending, *, fresh, old_geometry=0, old_carry=0.):
        chains = name == "chains"
        first, last = int(pending[0]), int(pending[-1])
        program = resources.compute_program(*PROGRAMS[0 if chains else 1])
        gl.glUseProgram(program)
        location = lambda uniform: self._location(program, uniform)
        gl.glUniform1i(location("uFirstStep"), first)
        gl.glUniform1i(location("uStepCount"), last - first + 1)
        gl.glUniform1i(location("uFresh"), int(fresh))
        gl.glUniform1i(location("uRebase"), int(bool(old_geometry)))
        gl.glUniform1d(location("uLastTravel"), float(state.travel))
        gl.glUniform1i(location("uOutOffset"), offset)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, _GEOMETRY, state.geometry)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, _OLD_GEOMETRY, old_geometry or state.geometry)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, _STATE, state.state)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, _AUX, state.aux)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, _OUT, self.output)
        record = upload[last]
        if chains:
            rows = min(state.capacity, int(record[_R["chain_rows"]]) or state.capacity)
            gl.glUniform1i(location("uOldRows"), 0 if fresh else state.count)
            gl.glDispatchCompute(rows, 1, 1)
            state.count = rows
        else:
            count_field, amount_field = _CLOUD_FIELDS[name]
            gl.glUniform1i(location("uCapacity"), state.capacity)
            gl.glUniform1i(location("uOldCount"), 0 if fresh else state.count)
            gl.glUniform1i(location("uCountField"), count_field)
            gl.glUniform1i(location("uAmountField"), amount_field)
            gl.glUniform1d(location("uCarry"), float(state.carry))
            gl.glUniform1d(location("uOldCarry"), float(old_carry if old_geometry else state.carry))
            gl.glDispatchCompute(-(-state.capacity // _CLOUD_GROUP), 1, 1)
            state.count = int(record[count_field])
        gl.glMemoryBarrier(gl.GL_SHADER_STORAGE_BARRIER_BIT)
        state.serial = int(record[_R["serial"]])
        state.travel = float(record[_R["travel"]])
