# Shared ribbon path: WR-01a CPU reference

`core/ribbon_geometry.py` owns the bounded CPU history/interpolation reference for future S3D-1 strips.
`tools/labs/ribbon_path_probe.py` consumes it to produce CPU XY cards and traces. It is not a renderer or
simulation and is not attached to any runtime mode. Existing EB wake code and shaders remain unchanged.

## Admission, ownership and capacity

One `RibbonHistory` owns one preallocated float64 ring, capacity 2–256. Its eight-float record is
`coordinate, x, y, z, half_width, twist, reserved0, reserved1`; both reserved fields are zero. At capacity256
the numeric payload is 16,384 bytes, excluding Python/NumPy owner overhead. Diagnostic `records()` returns
an owned chronological copy, not a writable view or GPU upload ABI. Evaluation also allocates reference
temporaries; this is not a proposed per-vertex production CPU loop.

Samples must be finite, with strictly increasing coordinates, positive half-width, positions/width within
1e6 world units, absolute unwrapped twist within 1e6 radians and absolute coordinate within 1e12. These are
reference arithmetic limits, not product Settings clamps. Duplicate/reversed coordinates fail loudly; position
reversal and repeated positions are valid. A complete input batch is admitted before mutation and cannot
exceed capacity. Full rings evict the oldest record without renumbering retained coordinates. `clear()` zeros
and reuses storage and increments `epoch`; persistent marks are identified by `(history owner, epoch, coordinate)`.
The consuming owner controls lifetime and drops the plain CPU object on retirement; no timers or subscriptions exist.

There is no population allocator yet. Maximum active ribbons, GPU stride/local coordinate precision/rebasing,
longitudinal tessellation, total vertex/index caps and the SSBO ring/fence contract must be fixed before WR-02
allocations. Float64 CPU records must not be cast to float32 and assumed to preserve large absolute phases.

## Continuous coordinate and interpolation

For the proposed musical history, coordinates represent caller-supplied logical sample times, not distance,
point number divided by count, or renderer wall time. Callers admit their signal on an explicit sampling lattice.
Changing submission batch boundaries for identical admitted knots is invariant; different dt observations of
an arbitrary curved trajectory are not assumed equivalent. No second sampling clock/resampler is introduced.

Evaluation locates the segment using its absolute coordinate. Geometry follows centripetal Catmull-Rom with
sqrt(chord-length) intervals, following the EB wake's numerical lesson without importing its water physics.
Repeated central points give an exactly constant segment. Exact endpoints reproduce their knots. Missing outer
controls are linearly extrapolated; empty history evaluates to None and one point to that point. Fewer than two
distinct positions cannot establish a strip tangent/visible strip; consumers must wait for valid support.

Four-knot-supported interior segments are stable across insertion/eviction. The newest and oldest boundary
segments are provisional because their outer support changes; consumers must budget guard knots before
claiming edge continuity. Expired/outside coordinates raise rather than pinning to a new endpoint. Half-width
interpolates linearly and stays positive; twist interpolates as an unwrapped angle, preserving authored turns.

## Evidence and remaining work

Focused tests falsify segment-share sliding, batch-partition changes, partial invalid-batch mutation, uniform
spline overshoot on unequal spacing, stale storage after clear, and nonfinite repeated/reversing paths.
Run `.venv\Scripts\python.exe tools/labs/ribbon_path_probe.py --output .artifacts/evidence/ribbon_path/<new-run>`.
The receipt records actual payload size, retained knots, evaluated positions and producer/core hashes. Cards are
CPU XY plots, not GPU/scene fidelity evidence. Output directories are never silently overwritten.

WR-01b remains: transported/oriented and camera-facing width frames (including Orthographic parallel sight),
cusp/degeneracy policy, tangents/normals/two-sided behavior, UV/strand coordinates and end/edge coverage.
WR-02 remains: GPU layout, strip expansion, OIT/occlusion/defocus, state/resource lifecycle proof and measured
CPU/GPU cost. Scene composition, real audio, reflection and artistic acceptance remain later gates.
