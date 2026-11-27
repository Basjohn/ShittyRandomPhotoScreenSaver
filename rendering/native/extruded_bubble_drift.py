"""Extruded Bubble's native drift entries (Current_Plan.md N5.6, "Native record and route"): the Python solver's own
compute texts (``extruded_bubble_drift_solver``: ``CHAIN_COMPUTE``, ``CLOUD_COMPUTE``, ``PAIR_CHECK_COMPUTE``) under a
cursor that finds, on the GPU, what the Python solver decides on the CPU per dispatch (``DriftSolver._advance`` /
``_dispatch``).

The Python solver keeps each family's applied state on the CPU (its last applied serial, revision, row count and
travel) and packs a ``DriftDispatch`` block per dispatch. The core fills a block from the record and the settings
only, so here each family keeps that state in a small header buffer of its own (``<family>_header``: two uvec4s,
(epoch, capacity, count, serial) and (travel high, travel low as bits, valid, the geometry's rows)), and three entries
a family run on the record's trigger (``drift_last_step``), each binding the family's geometry so the core holds the
three alike while its key is not resident (ABI 46):

- ``<family>_before``: a geometry edit's (rebase's) pending steps of the old revision on its own rows, bound to the
  previous key's geometry (the Python solver's first ``_dispatch`` of a rebase);
- ``<family>``: the steps after that (or the whole fresh history, or the suffix after the last applied step), as the
  Python solver's main dispatch: ``uFresh`` on a new lineage or a gap, ``uRebase`` after an edit;
- ``<family>_mark``: the header the next record's entries read (written by one invocation after both read it: QRhi's
  barrier between the passes, never a race between workgroups).

The Python text's ``DriftDispatch`` block becomes plain globals the cursor sets, and its ``main`` a function the cursor
calls; nothing of its arithmetic changes. Its pixels are layer P's (the drift's continuity through the restart and
rebase edges: the Coverage windows box).
"""
from __future__ import annotations

import re

#: The block the core fills for every drift entry (its own binding: the Python solver's block's, now free).
_BLOCK_BINDING = 14
#: The header buffer's binding (beside the Python solver's storage bindings 8 to 13).
_HEADER_BINDING = 15
#: The Python text's ``DriftDispatch`` block (made plain globals by ``_globals``).
_DISPATCH = re.compile(r"// One block for every dispatch value.*?\n(layout\(std140, binding = \d+\) uniform DriftDispatch \{"
                       r"\n(.*?)\n\};)", re.S)


def _globals(text: str) -> str:
    """The Python text with its ``DriftDispatch`` block as writable globals and its ``main`` as ``driftRun``."""
    match = _DISPATCH.search(text)
    if match is None or text.count("void main() {") != 1:
        raise ValueError("the drift text holds its DriftDispatch block and one main")
    members = [line.split("//")[0].strip() for line in match.group(2).splitlines() if line.strip()]
    plain = "// The Python solver's dispatch values, set by the cursor (rendering/native/extruded_bubble_drift.py).\n"
    plain += "\n".join(members)
    return text[:match.start()] + plain + text[match.end():].replace("void main() {", "void driftRun() {")


def _block(family: str) -> str:
    return f"""
layout(std140, binding = {_BLOCK_BINDING}) uniform EbDrift_{family} {{
    uvec4 u_srpss_compute;      // the core's: (drift_last_step, its value at the last dispatch, fresh, dispatches)
    uint drift_step_count;
    uint {family}_epoch;
    uint {family}_rebase_from_epoch;
    uint {family}_first_step;
    uint {family}_out_offset;
    uint {family}_capacity;
    float {family}_carry;
    uint drift_serial_base;     // where the stream's serials begin (its last drift_step_count words)
}};
layout(std430, binding = {_HEADER_BINDING}) {{access}} buffer DriftHeader {{ uvec4 header[2]; }};
"""


def _cursor(family: str) -> str:
    """The cursor's helpers: the applied state the header holds, and the steps' serials, counts and travel."""
    from widgets.spotify_visualizer.extruded_bubble_drift_log import STEP_INDEX

    chains = family == "chains"
    count = "" if chains else STEP_INDEX[f"count_{family}"]
    return f"""
uint stepSerial(int s) {{ return steps[drift_serial_base + uint(s)]; }}
vec2 stepTravel(int s) {{ return vec2(stepValue(s, {STEP_INDEX['travel_high']}), stepValue(s, {STEP_INDEX['travel_low']})); }}
// The family's count after step s at a state of ``capacity`` rows (DriftSolver._dispatch's ``state.count``).
uint countAfter(int s, uint capacity) {{
{f"    uint rows = uint(stepValue(s, {STEP_INDEX['chain_rows']}));" if chains else ""}
    return {"min(capacity, rows == 0u ? capacity : rows)" if chains else f"uint(stepValue(s, {count}))"};
}}
// The applied state (header) and the lineage this record names.
bool driftKnown() {{ return u_srpss_compute.z == 0u && header[1].z == 1u; }}
bool driftSame() {{ return driftKnown() && header[0].x == {family}_epoch; }}
bool driftRebase() {{
    return driftKnown() && !driftSame() && {family}_rebase_from_epoch != 0u
           && {family}_rebase_from_epoch == header[0].x;
}}
// The last of the old revision's pending steps (serials after the applied one, before the new revision's first).
int driftLastOld() {{
    int last = -1;
    for (int s = 0; s < int(drift_step_count); ++s)
        if (stepSerial(s) > header[0].w && stepSerial(s) < {family}_first_step) last = s;
    return last;
}}
int driftFirstAfter(uint serial) {{
    for (int s = 0; s < int(drift_step_count); ++s)
        if (stepSerial(s) > serial) return s;
    return -1;
}}
"""


def _set(family: str, *, first: str, last: str, fresh: str, rebase: str, old: str, capacity: str,
         travel: str) -> str:
    """The cursor's assignments of the Python block's values (DriftSolver._dispatch's ``block``)."""
    from widgets.spotify_visualizer.extruded_bubble_drift_log import STEP_FLOATS, STEP_INDEX

    chains = family == "chains"
    lines = [f"uFirstStep = {first};", f"uStepCount = {last} - {first} + 1;", f"uFresh = {fresh} ? 1 : 0;",
             f"uRebase = {rebase} ? 1 : 0;", f"uOutOffset = int({family}_out_offset);",
             f"uKnotBase = int(drift_step_count) * {STEP_FLOATS};"]
    if chains:
        lines += [f"uOldRows = {fresh} ? 0 : int({old});", "uCapacity = 0; uOldCount = 0; uCountField = 0;",
                  "uAmountField = 0; uCarry = 0.0; uLastTravel = vec2(0.0);",
                  # DriftSolver._dispatch: groups = rows; the workgroups past them leave (each is one path).
                  f"if (int(gl_WorkGroupID.x) >= int(countAfter({last}, {capacity}))) return;"]
    else:
        lines += ["uOldRows = 0;", f"uCapacity = int({capacity});", f"uOldCount = {fresh} ? 0 : int({old});",
                  f"uCountField = {STEP_INDEX[f'count_{family}']}; uAmountField = {STEP_INDEX[f'amount_{family}']};",
                  f"uCarry = {family}_carry; uLastTravel = {travel};"]
    return "\n    ".join(lines)


def _before_main(family: str) -> str:
    return f"""
void main() {{
    // A geometry edit: the old revision's steps after the applied one, on its own rows (bound to the previous key's
    // geometry), as the Python solver dispatches them before its rebase.
    if (!driftRebase()) return;
    int last = driftLastOld();
    if (last < 0) return;
    int first = driftFirstAfter(header[0].w);
    uint capacity = min(header[0].y, {family}_capacity);
    {_set(family, first="first", last="last", fresh="false", rebase="false", old="header[0].z",
          capacity="capacity", travel="uintBitsToFloat(header[1].xy)")}
    driftRun();
}}
"""


def _family_main(family: str) -> str:
    return f"""
void main() {{
    bool rebase = driftRebase(), fresh = !driftSame() && !rebase;
    uint after = header[0].w, old = header[0].z;
    vec2 travel = uintBitsToFloat(header[1].xy);
    if (rebase) {{
        int lastOld = driftLastOld();
        if (lastOld >= 0) {{
            after = stepSerial(lastOld);
            old = countAfter(lastOld, min(header[0].y, {family}_capacity));
            travel = stepTravel(lastOld);
        }}
    }} else if (fresh) {{
        after = {family}_first_step - 1u;
    }}
    int first = driftFirstAfter(after);
    if (first < 0) return;
    // The render fell further behind than the published history: restart this history (lifecycle).
    if (!fresh && !rebase && stepSerial(first) != after + 1u) fresh = true;
    int last = int(drift_step_count) - 1;
    {_set(family, first="first", last="last", fresh="fresh", rebase="rebase", old="old",
          capacity=f"{family}_capacity", travel="travel")}
    driftRun();
}}
"""


def _mark(family: str) -> str:
    """The header after this record's dispatches (DriftSolver._dispatch's ``state`` after its last step)."""
    from widgets.spotify_visualizer.extruded_bubble_drift_log import STEP_FLOATS

    return f"""#version 460 core
layout(local_size_x = 1) in;
layout(std430, binding = 8) readonly buffer DriftSteps {{ uint steps[]; }};
layout(std430, binding = 9) readonly buffer Geometry {{ vec4 geometry[]; }};
float stepValue(int step, int field) {{ return uintBitsToFloat(steps[step * {STEP_FLOATS} + field]); }}
{_block(family).replace("{access}", "")}
{_cursor(family)}
void main() {{
    int last = int(drift_step_count) - 1;
    if (last < 0) return;
    // A new lineage with none of its own steps yet: the Python state waits at its first serial, nothing applied.
    if (!driftSame() && !driftRebase() && stepSerial(last) < {family}_first_step) {{
        header[0] = uvec4({family}_epoch, {family}_capacity, 0u, {family}_first_step - 1u);
        header[1] = uvec4(0u, 0u, 1u, uint(geometry.length()));
        return;
    }}
    header[0] = uvec4({family}_epoch, {family}_capacity, countAfter(last, {family}_capacity), stepSerial(last));
    header[1] = uvec4(floatBitsToUint(stepTravel(last)), 1u, uint(geometry.length()));
}}
"""


def compute_texts() -> dict[str, str]:
    """Every drift entry's source name (``eb_drift_<family>[_before|_mark].comp``, ``eb_drift_pair_check.comp``) and
    text."""
    from rendering.quick.visualizer.implementations.extruded_bubble_drift_solver import (
        CHAIN_COMPUTE, CLOUD_COMPUTE, PAIR_CHECK_COMPUTE)
    from widgets.spotify_visualizer.extruded_bubble_drift_log import FAMILIES

    files = {"eb_drift_pair_check.comp": PAIR_CHECK_COMPUTE}
    for family in FAMILIES:
        body = _globals(CHAIN_COMPUTE if family == "chains" else CLOUD_COMPUTE)
        head, rest = body.split("\n", 1)
        common = head + "\n" + _block(family).replace("{access}", "readonly") + rest + _cursor(family)
        files[f"eb_drift_{family}_before.comp"] = common + _before_main(family)
        files[f"eb_drift_{family}.comp"] = common + _family_main(family)
        files[f"eb_drift_{family}_mark.comp"] = _mark(family)
    return files


__all__ = ["compute_texts"]
