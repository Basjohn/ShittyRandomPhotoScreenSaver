"""Extruded Bubble's free drift on the GPU: the chains', snow's and specks' material history, integrated from the
logical tick's step log (``widgets/spotify_visualizer/extruded_bubble_drift_log``).

The logical tick publishes each step (dt, motion phase, travel, speed, each family's signed amount, the cloud
counts, the field basis) and each family's seeded geometry; it integrates nothing. Here, on the render thread,
every step not yet applied is applied once, in order, to persistent per-knot / per-mote state in storage buffers,
by the arithmetic of ``MaterialPaths`` / ``ProceduralOffsets`` (the CPU reference, which keeps positions and
displacement in float64 and narrows to float32 only when it packs its payload). The output keeps the
layout the bead and speck shaders read (``ebMaterialDrift``: chain rows, then snow, then specks), so no draw
changes. No readback, no clock of its own: a frame that sees no new step dispatches nothing.

No shader here uses a 64-bit float, on any backend (D4, ``Docs/Future_Work/Native_Core_P3_Decisions.md``). The
float64 work is done once on the logical side and published: each chain's knot decision per step (how many knots
its row moves, its shift and phase offset: the reference's own ``KnotClock``), the field's growing phase
arguments reduced mod 2 pi, and travel as a float pair. The per-mote progress ``fract(seed + travel x carry /
span + phase offset)`` is rebuilt from pairs of floats (an exact two-product from Veltkamp halves, ``precise`` so
the compiler may not reorder or contract it; not ``fma``, which HLSL cannot keep fused): the quotient arrives as a
pair in the mote's geometry, the seed as a head the pair is rebuilt from, the phase offset is kept as a pair.
Positions and displacement are float32, as the draws read them.

A geometry edit continues the old history (the CPU rebase); a render gap longer than the published history, a
lost context or a retired family restarts that family's history from zero (lifecycle, like a fresh family).
"""
from __future__ import annotations

import ctypes
import math
import struct
from dataclasses import dataclass

import numpy as np
from OpenGL import GL as gl

from core.constants.extruded_bubble_world import WORLD_UNIT
from rendering.quick import gl_query
from rendering.quick.scene3d.stream import StreamRing
from widgets.spotify_visualizer import extruded_bubble_drift as drift
from widgets.spotify_visualizer.extruded_bubble_drift_log import (
    CHAIN_GEOMETRY_BYTES, CLOUD_GEOMETRY_BYTES, KNOT_DECISION_BYTES, STEP_FLOATS, STEP_HISTORY, STEP_INDEX,
    knot_starts, unpack_steps,
)
from widgets.spotify_visualizer.extruded_bubble_material_paths import PATH_NODES

# Storage bindings used only inside the solver's dispatches (each restored afterwards), and the uniform block's
# (apart from them: one binding namespace on Vulkan).
_STEPS, _GEOMETRY, _STATE, _AUX, _OUT, _OLD_GEOMETRY, _BLOCK = 8, 9, 10, 11, 12, 13, 14
# DriftDispatch in std140: eleven ints, a float, a vec2 at offset 48; 64 bytes.
_DISPATCH_BLOCK = struct.Struct("<11if2f8x")
_CLOUD_GROUP = 256
_R = STEP_INDEX
# The uploaded steps are float32 copies of the float64 records (every field the programs read is exactly a float32
# value or a small count); in the serial's place each carries where its knot decisions begin in the upload.
_KNOT_START = _R["serial"]
_KNOT_WORDS = KNOT_DECISION_BYTES // 4


def hold_bytes(chain_rows: int) -> int:
    """One upload: a history of steps with ``chain_rows`` knot decisions each, then a dispatch block per dispatch (at
    most two per family, each at the uniform offset alignment, which is at most 256)."""
    return STEP_HISTORY * (4 * STEP_FLOATS + chain_rows * KNOT_DECISION_BYTES) + 6 * (256 + _DISPATCH_BLOCK.size)

_PAIRS_GLSL = """
// Error-free float32 transforms (precise: evaluated as written, never reordered or contracted).
vec2 twoSum(float a, float b) {
    precise float s = a + b;
    precise float v = s - a;
    precise float e = (a - (s - v)) + (b - v);
    return vec2(s, e);
}
vec2 fastTwoSum(float a, float b) {
    precise float s = a + b;
    precise float e = b - (s - a);
    return vec2(s, e);
}
// Dekker's exact product from Veltkamp halves (adds and multiplies only): fma is not one fused operation on every
// backend (HLSL has no float fma; qsb's HLSL turns it into mad, which may round twice).
vec2 split(float a) {
    precise float c = 4097.0 * a;
    precise float high = c - (c - a);
    precise float low = a - high;
    return vec2(high, low);
}
vec2 twoProd(float a, float b) {
    precise float p = a * b;
    vec2 x = split(a), y = split(b);
    precise float e = ((x.x * y.x - p) + x.x * y.y + x.y * y.x) + x.y * y.y;
    return vec2(p, e);
}
vec2 mulPair(vec2 x, vec2 y) {
    vec2 p = twoProd(x.x, y.x);
    precise float lo = p.y + (x.x * y.y + x.y * y.x);
    return fastTwoSum(p.x, lo);
}
// The fractional part of x + y + z as a pair: x of any size, y and z pairs within [0, 1].
vec2 fractSum(vec2 x, vec2 y, vec2 z) {
    precise float n = floor(x.x);
    precise float head = x.x - n;
    vec2 a = twoSum(head, y.x);
    vec2 b = twoSum(a.x, z.x);
    precise float lo = (((x.y + y.y) + z.y) + a.y) + b.y;
    vec2 s = twoSum(b.x, lo);
    precise float m = floor(s.x);
    if (s.x == m && s.y < 0.0) m -= 1.0;
    precise float h = s.x - m;
    return fastTwoSum(h, s.y);
}
"""

_VELOCITY_GLSL = f"""
const float TAU = {2.0 * math.pi!r};
float stepValue(int step, int field) {{ return uintBitsToFloat(steps[step * {STEP_FLOATS} + field]); }}
vec3 stepVec(int step, int field) {{
    return vec3(stepValue(step, field), stepValue(step, field + 1), stepValue(step, field + 2));
}}
// sin's argument brought into [-pi, pi) first: both terms are bounded (the phase argument arrives reduced).
float sinBounded(float x) {{ return sin(x - TAU * floor(x / TAU + 0.5)); }}
// extruded_bubble_drift.velocity: the canonical drift field, kinds in DRIFT_DIRECTIONS order.
vec3 driftVelocity(int kind, vec3 world, float phase, int step, vec3 direction, vec3 across, vec3 depthAxis,
                   vec3 origin, float amount) {{
    float meander = kind == 0 ? 1.0 : {drift._STEERED_WANDER};
    float wander = meander * amount * 0.05 * (sinBounded(stepValue(step, {_R['angle_wander']}) + phase)
                                              + 0.6 * sinBounded(stepValue(step, {_R['angle_wander_2']}) + 2.1 * phase));
    float deep = meander * amount * 0.015 * sinBounded(stepValue(step, {_R['angle_deep']}) + 1.7 * phase);
    vec3 directed = vec3(0.0);
    if (kind == 1) directed = amount * (-{drift._STEER_SPEED} * across);
    else if (kind == 2) directed = amount * ({drift._STEER_SPEED} * across);
    else if (kind == 3) directed = amount * ({drift._STEER_SPEED} * sqrt(0.5) * (across + depthAxis));
    else if (kind == 6) directed = amount * ({drift._RANDOM_SPEED} * (cos(phase) * across + sin(phase) * depthAxis));
    else if (kind == 4 || kind == 5) {{
        float sway = {drift._SWISH_SPEED} * sinBounded(stepValue(step, {_R['angle_swish']}) - 0.35 * sin(phase));
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
layout(std430, binding = {_STEPS}) readonly buffer DriftSteps {{ uint steps[]; }};
// One block for every dispatch value (Vulkan GLSL has no loose uniforms); _dispatch_block packs it.
layout(std140, binding = {_BLOCK}) uniform DriftDispatch {{
    int uFirstStep;
    int uStepCount;
    int uFresh;            // 1: the history starts here (zero state)
    int uRebase;           // 1: a geometry edit; continue the old history onto the new geometry first
    int uOutOffset;        // first vec4 of this family in the shaders' ebMaterialDrift
    int uOldRows;          // chains: paths that already have history (rows past it start fresh)
    int uKnotBase;         // chains: first word of the uploaded knot decisions
    int uCapacity;         // clouds: motes in the geometry
    int uOldCount;         // clouds: motes alive before this dispatch's first step
    int uCountField;       // clouds: the step field holding this family's mote count
    int uAmountField;      // clouds: the step field holding this family's signed amount
    float uCarry;          // clouds: the family's stream carry
    vec2 uLastTravel;      // clouds: travel of the last step applied before this dispatch, as a pair
}};
"""

CHAIN_COMPUTE = _COMMON + f"""
layout(local_size_x = {PATH_NODES}) in;
layout(std430, binding = {_GEOMETRY}) readonly buffer Geometry {{ vec4 geometry[]; }};
layout(std430, binding = {_OLD_GEOMETRY}) readonly buffer OldGeometry {{ vec4 oldGeometry[]; }};
layout(std430, binding = {_STATE}) buffer Knots {{ vec4 knots[]; }};
layout(std430, binding = {_AUX}) buffer Paths {{ vec4 paths[]; }};      // (shift, phase offset) after the last step
layout(std430, binding = {_OUT}) writeonly buffer Out {{ vec4 outDrift[]; }};
shared vec3 sDisplacement[{PATH_NODES}];
{_VELOCITY_GLSL}
void main() {{
    int path = int(gl_WorkGroupID.x), knot = int(gl_LocalInvocationID.x), node = path * {PATH_NODES} + knot;
    bool existing = uFresh == 0 && path < uOldRows;
    vec3 displacement = existing ? knots[node].xyz : vec3(0.0);
    vec2 clock = existing ? paths[path].xy : vec2(0.0);
    float shift = clock.x, phaseOffset = clock.y;
    vec4 g0 = geometry[path * 3], g1 = geometry[path * 3 + 1];
    vec3 start = g0.xyz, end = g1.xyz;
    float span = g0.w, carry = g1.w, phase = geometry[path * 3 + 2].x;
    float progress = float(knot - 1) / float({PATH_NODES - 3});
    if (existing && uRebase == 1) {{
        // MaterialPaths: preserve the world centreline at a path edit (its phase offset is a published decision).
        vec4 o0 = oldGeometry[path * 3], o1 = oldGeometry[path * 3 + 1];
        float q = progress + shift;
        displacement += (o0.xyz + (o1.xyz - o0.xyz) * q) - (start + (end - start) * q);
    }}
    for (int s = uFirstStep; s < uFirstStep + uStepCount; ++s) {{
        if (path >= int(stepValue(s, {_R['chain_rows']}))) {{
            // The step holds fewer rows: this one has no history (uniform across the workgroup).
            displacement = vec3(0.0); shift = 0.0; phaseOffset = 0.0;
            continue;
        }}
        int k = uKnotBase + {_KNOT_WORDS} * (int(stepValue(s, {_KNOT_START})) + path);
        shift = uintBitsToFloat(steps[k]);
        phaseOffset = uintBitsToFloat(steps[k + 1]);
        int moved = int(steps[k + 2]);
        sDisplacement[knot] = displacement;
        barrier();
        if (moved > 0)
            displacement = knot - moved >= 0 ? sDisplacement[knot - moved] : vec3(0.0);
        barrier();
        float q = progress + shift;
        vec3 world = start + (end - start) * q + displacement;
        vec3 field = driftVelocity(int(stepValue(s, {_R['kind']})), world, phase, s,
                                   stepVec(s, {_R['direction_x']}), stepVec(s, {_R['across_x']}),
                                   stepVec(s, {_R['depth_x']}), stepVec(s, {_R['origin_x']}),
                                   stepValue(s, {_R['amount_chains']}));
        float rate = stepValue(s, {_R['speed']}) * carry / span;
        float available = max(0.0, min(stepValue(s, {_R['dt']}), q / max(rate, 1e-12)));
        displacement += field * available;
        if (q <= 0.0) displacement = vec3(0.0);
    }}
    knots[node] = vec4(displacement, 0.0);
    if (knot == 0) paths[path] = vec4(shift, phaseOffset, 0.0, 0.0);
    outDrift[uOutOffset + node] = vec4(displacement, knot == 0 ? shift : knot == 1 ? phaseOffset : 0.0);
}}
"""

CLOUD_COMPUTE = _COMMON + f"""
layout(local_size_x = {_CLOUD_GROUP}) in;
layout(std430, binding = {_GEOMETRY}) readonly buffer Geometry {{ vec4 geometry[]; }};
layout(std430, binding = {_OLD_GEOMETRY}) readonly buffer OldGeometry {{ vec4 oldGeometry[]; }};
layout(std430, binding = {_STATE}) buffer Motes {{ vec4 motes[]; }};   // (displacement, phase offset high)
layout(std430, binding = {_AUX}) buffer Bases {{ vec4 bases[]; }};     // (previous base, phase offset low)
layout(std430, binding = {_OUT}) writeonly buffer Out {{ vec4 outDrift[]; }};
{_PAIRS_GLSL}
{_VELOCITY_GLSL}
void main() {{
    int id = int(gl_GlobalInvocationID.x);
    if (id >= uCapacity) return;
    bool alive = uFresh == 0 && id < uOldCount;
    vec4 mote = alive ? motes[id] : vec4(0.0), held = alive ? bases[id] : vec4(0.0);
    vec3 displacement = mote.xyz, previousBase = held.xyz;
    vec2 phaseOffset = vec2(mote.w, held.w), lastTravel = uLastTravel;
    vec4 g0 = geometry[id * 2], g1 = geometry[id * 2 + 1];
    vec3 start = g0.xyz;
    float span = g0.w, phase = g1.y;
    // seed = k / (2^24 - 1) = head + head / 2^24 to within 2^-48 (head = k / 2^24, exact in float32).
    vec2 seed = vec2(g1.x, g1.x * {2.0 ** -24!r}), ratio = g1.zw;
    if (alive && uRebase == 1) {{
        // ProceduralOffsets: an edited geometry keeps every mote where it was.
        vec2 before = mulPair(lastTravel, oldGeometry[id * 2 + 1].zw), after = mulPair(lastTravel, ratio);
        vec2 d = twoSum(before.x, -after.x);
        phaseOffset = fractSum(vec2(d.x, d.y + (before.y - after.y)), phaseOffset, vec2(0.0));
        float previousQ = fractSum(after, seed, phaseOffset).x;
        vec3 direction = stepVec(uFirstStep, {_R['direction_x']});
        displacement += previousBase - (start + direction * (previousQ * span));
    }}
    float packedProgress = 0.0;
    bool first = uFresh == 1;
    for (int s = uFirstStep; s < uFirstStep + uStepCount; ++s) {{
        int count = int(stepValue(s, uCountField));
        vec2 travel = vec2(stepValue(s, {_R['travel_high']}), stepValue(s, {_R['travel_low']}));
        if (id >= count) {{ alive = false; displacement = vec3(0.0); phaseOffset = vec2(0.0); first = false;
                            lastTravel = travel; continue; }}
        if (!alive) {{ displacement = vec3(0.0); phaseOffset = vec2(0.0); alive = true; }}
        float dt = stepValue(s, {_R['dt']}), speed = stepValue(s, {_R['speed']});
        float previousQ = fractSum(mulPair(lastTravel, ratio), seed, phaseOffset).x;
        float progress = fractSum(mulPair(travel, ratio), seed, phaseOffset).x;
        float carried = (travel.x - lastTravel.x) + (travel.y - lastTravel.y);
        bool recycled = !first && (progress < previousQ - 1e-10 || carried * ratio.x >= 1.0);
        if (recycled) displacement = vec3(0.0);
        vec3 direction = stepVec(s, {_R['direction_x']});
        vec3 base = start + direction * (progress * span);
        vec3 field = driftVelocity(int(stepValue(s, {_R['kind']})), base + displacement, phase, s, direction,
                                   stepVec(s, {_R['across_x']}), stepVec(s, {_R['depth_x']}),
                                   stepVec(s, {_R['origin_x']}), stepValue(s, uAmountField));
        float available = recycled ? min(dt, progress * span / max(speed * uCarry, 1e-12)) : dt;
        displacement += field * available;
        previousBase = base;
        lastTravel = travel;
        packedProgress = progress - (recycled ? 1.0 : 0.0);
        first = false;
    }}
    motes[id] = vec4(displacement, phaseOffset.x);
    bases[id] = vec4(previousBase, phaseOffset.y);
    outDrift[uOutOffset + id] = vec4(displacement, packedProgress);
}}
"""

PROGRAMS = (("drift_chains", CHAIN_COMPUTE), ("drift_clouds", CLOUD_COMPUTE))
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


def _upload(records: np.ndarray, starts: np.ndarray, knots: bytes, first: int, last: int) -> bytes:
    """Steps ``first:last`` as float32 records, each carrying where its knot decisions begin, then those decisions."""
    gpu = records[first:last].astype(np.float32)
    gpu[:, _KNOT_START] = starts[first:last] - starts[first]
    return gpu.tobytes() + knots[int(starts[first]) * KNOT_DECISION_BYTES:int(starts[last]) * KNOT_DECISION_BYTES]


@dataclass
class _Family:
    revision: int
    capacity: int
    geometry: int
    state: int
    aux: int
    carry: float
    serial: int = 0                        # last step applied
    travel: tuple[float, float] = (0., 0.)  # that step's travel, as its float pair
    count: int = 0                         # motes alive (clouds) / paths with history (chains) after that step


class DriftSolver:
    """The render thread's drift state for one renderer (released with it)."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.output = 0
        self._output_vec4s = 0
        self._families: dict[str, _Family] = {}
        self._ring: StreamRing | None = None   # sized to the most chain rows a step has carried (_ring_for)

    @property
    def has_resources(self) -> bool:
        return bool(self.output or self._families or (self._ring is not None and self._ring.has_resources))

    def release(self) -> None:
        for family in self._families.values():
            _delete(family.geometry, family.state, family.aux)
        self._families.clear()
        _delete(self.output)
        self.output, self._output_vec4s = 0, 0
        if self._ring is not None:
            self._ring.release()
            self._ring = None

    def _ring_for(self, chain_rows: int) -> StreamRing:
        """The step ring, grown (never shrunk) when a step carries more chain rows than it was sized for: an edge of
        the Bead Chains Range, never a frame. Its old storage is released; GL keeps it until submitted work is done."""
        hold = hold_bytes(chain_rows)
        if self._ring is None or self._ring.hold_bytes < hold:
            if self._ring is not None:
                self._ring.release()
            self._ring = StreamRing(f"{self.label} drift steps", slots=4, slot_bytes=2 * hold, hold_bytes=hold)
        return self._ring

    @staticmethod
    def layout(families) -> dict[str, int]:
        """Each live family's first vec4 in the output (chain rows, then snow, then specks), and the total."""
        offsets, cursor = {}, 0
        for family in families:
            offsets[family.family] = cursor
            cursor += family.capacity * (PATH_NODES if family.family == "chains" else 1)
        offsets["_total"] = cursor
        return offsets

    def update(self, resources, families, steps: bytes, knots: bytes) -> dict[str, int]:
        """Apply every published step not yet applied to each live family; returns the output layout."""
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
            return offsets      # no new logical step since the last frame: nothing to integrate
        if offsets["_total"] > self._output_vec4s:
            # Every dispatch rewrites its family's whole output from its state: a new buffer loses nothing.
            _delete(self.output)
            self._output_vec4s = max(256, 1 << (offsets["_total"] - 1).bit_length())
            self.output = _buffer(16 * self._output_vec4s)
        base = min(needed)
        starts = knot_starts(records)
        if len(knots) != int(starts[-1]) * KNOT_DECISION_BYTES:
            raise ValueError(f"{self.label}: knot decisions do not match their steps")
        ring = self._ring_for(int(records[base:, _R["chain_rows"]].max()))
        prior_program = gl_query.get_int(gl.GL_CURRENT_PROGRAM)
        saved = [(binding, gl_query.get_indexed_int(gl.GL_SHADER_STORAGE_BUFFER_BINDING, binding),
                  gl_query.get_indexed_int64(gl.GL_SHADER_STORAGE_BUFFER_START, binding),
                  gl_query.get_indexed_int64(gl.GL_SHADER_STORAGE_BUFFER_SIZE, binding))
                 for binding in (_GEOMETRY, _STATE, _AUX, _OUT, _OLD_GEOMETRY)]
        generic = gl_query.get_int(gl.GL_SHADER_STORAGE_BUFFER_BINDING)
        try:
            # One history's worth of steps per upload (an offline capture can hand over a longer log).
            for start in range(base, len(records), STEP_HISTORY):
                end = min(start + STEP_HISTORY, len(records))
                upload = records[start:end]
                with ring.bound(gl.GL_SHADER_STORAGE_BUFFER, _STEPS, _upload(records, starts, knots, start, end)):
                    for name in ("chains", "snow", "specks"):
                        if name in live:
                            self._advance(resources, name, live[name], offsets[name], upload, serials[start:end])
        finally:
            for binding, buffer, start, size in saved:
                if buffer and size:
                    gl.glBindBufferRange(gl.GL_SHADER_STORAGE_BUFFER, binding, buffer, start, size)
                else:
                    gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, binding, buffer)
            gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER, generic)
            gl.glUseProgram(prior_program)
        return offsets

    def _advance(self, resources, name: str, family, offset: int, upload: np.ndarray, serials: np.ndarray) -> None:
        """Issue ``family``'s work for this frame, in order (each step reads what the previous one wrote)."""
        state = self._families.get(name)
        if state is not None and state.revision != family.revision and family.rebase_from == state.revision:
            # A geometry edit: the old revision's pending steps on the old rows first, then its history continues
            # onto the new geometry (the CPU rebase) before the new steps.
            old_steps = np.flatnonzero((serials > state.serial) & (serials < family.first_serial))
            if len(old_steps):
                self._dispatch(resources, name, state, offset, upload, old_steps, fresh=False)
            replacement = self._allocate(family, state)
            replacement.serial, replacement.travel, replacement.count = state.serial, state.travel, state.count
            self._families[name] = replacement
            pending = np.flatnonzero(serials > replacement.serial)
            if len(pending):
                self._dispatch(resources, name, replacement, offset, upload, pending, fresh=False,
                               old_geometry=state.geometry)
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
            # The render fell further behind than the published history: restart this history (lifecycle).
            fresh = True
        self._dispatch(resources, name, state, offset, upload, pending, fresh=fresh)

    def _allocate(self, family, previous: _Family | None = None) -> _Family:
        chains = family.family == "chains"
        row_bytes = CHAIN_GEOMETRY_BYTES if chains else CLOUD_GEOMETRY_BYTES
        if len(family.geometry) != row_bytes * family.capacity:
            raise ValueError(f"{self.label}: {family.family} geometry does not match its capacity")
        geometry = _buffer(len(family.geometry))
        gl.glNamedBufferSubData(geometry, 0, len(family.geometry), family.geometry)
        rows = family.capacity * (PATH_NODES if chains else 1)
        state, aux = _buffer(16 * rows), _buffer(16 * (family.capacity if chains else rows))
        for buffer in (state, aux):
            gl.glClearNamedBufferData(buffer, gl.GL_R32F, gl.GL_RED, gl.GL_FLOAT, None)
        if previous is not None:
            # Keep the existing history rows (a stable seeded prefix), as written by every earlier dispatch.
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)
            keep = min(previous.capacity, family.capacity)
            gl.glCopyNamedBufferSubData(previous.state, state, 0, 0, 16 * keep * (PATH_NODES if chains else 1))
            gl.glCopyNamedBufferSubData(previous.aux, aux, 0, 0, 16 * keep)
        return _Family(family.revision, family.capacity, geometry, state, aux, float(family.carry))

    def _dispatch(self, resources, name: str, state: _Family, offset: int, upload: np.ndarray, pending: np.ndarray,
                  *, fresh: bool, old_geometry: int = 0) -> None:
        chains = name == "chains"
        first, last = int(pending[0]), int(pending[-1])
        gl.glUseProgram(resources.compute_program(*PROGRAMS[0 if chains else 1]))
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, _GEOMETRY, state.geometry)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, _OLD_GEOMETRY, old_geometry or state.geometry)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, _STATE, state.state)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, _AUX, state.aux)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, _OUT, self.output)
        record = upload[last]
        old = 0 if fresh else state.count
        if chains:
            rows = min(state.capacity, int(record[_R["chain_rows"]]) or state.capacity)
            block = _DISPATCH_BLOCK.pack(first, last - first + 1, int(fresh), int(bool(old_geometry)), offset, old,
                                         len(upload) * STEP_FLOATS, 0, 0, 0, 0, 0., 0., 0.)
            groups = rows
            state.count = rows
        else:
            count_field, amount_field = _CLOUD_FIELDS[name]
            block = _DISPATCH_BLOCK.pack(first, last - first + 1, int(fresh), int(bool(old_geometry)), offset, 0, 0,
                                         state.capacity, old, count_field, amount_field, float(state.carry),
                                         *state.travel)
            groups = -(-state.capacity // _CLOUD_GROUP)
            state.count = int(record[count_field])
        with self._ring.bound(gl.GL_UNIFORM_BUFFER, _BLOCK, block):
            gl.glDispatchCompute(groups, 1, 1)
        # The next dispatch (or the draws) read what this one wrote.
        gl.glMemoryBarrier(gl.GL_SHADER_STORAGE_BARRIER_BIT)
        state.serial = int(record[_R["serial"]])
        state.travel = (float(record[_R["travel_high"]]), float(record[_R["travel_low"]]))


__all__ = ["DriftSolver", "PROGRAMS"]
