# Shared ribbon path and width-frame CPU reference

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

WR-01b CPU width frames and station construction are implemented in `core/ribbon_frames.py`; see below.
WR-02 remains: GPU layout, strip expansion, OIT/occlusion/defocus, state/resource lifecycle proof and measured
CPU/GPU cost. Scene composition, real audio, reflection and artistic acceptance remain later gates.

## Width frames, stations and continuation (WR-01b)

`width_frame` consumes an explicit finite tangent; the caller owns derivative evaluation/sampling. Minimal-rotation
transport carries `base_side`, never the already-twisted `side`. Authored unwrapped twist applies once at each
station. Tangent, twisted width and their cross-product form a right-handed orthonormal centre-line frame.
`strip_station` emits left/right points at centre +/- half-width, with UVs `(absolute_coordinate, 0/1)`.
Frame normals describe the centre line only; the displaced/twisted surface must derive its normals from its
actual expanded geometry at WR-02. Two-sided shading must orient those normals by face direction rather than
changing world geometry, forcing positive normals, or disabling required occlusion.

No hidden frame cache exists. Batch continuation passes its last valid `WidthFrame` as `initial_frame`;
eviction retains the anchor preceding the first evaluated station. Anchors are scoped to history owner/epoch
and sampling lattice by the caller. Reseeding a new oldest point can change global roll and is not equivalent.
`strip_path` validates bounded sample/tangent pairs, preserves explicit gaps and returns immutable records.
It accepts at most `(256-1)*8+1 = 2041` stations, derived from shared history/subdivision caps.

Zero-length tangents yield None: no visible station and no triangle bridge across the gap. A first oriented
frame requires a non-parallel authored seed, projected onto the tangent-normal plane; it does not silently invent a world axis. Camera-facing mode
can use its well-defined camera side if that seed is parallel. Tangent cosine <= -1+1e-6 raises
`FrameDiscontinuity`: split the strip with an explicit new seed, or admit better-resolved tangents. This
refuses the arbitrary roll at a true/near reversal rather than quietly flipping UVs. Input errors never mutate
an immutable caller anchor. Cusp segmentation and actual vertex admission remain GPU-harness gates.

Orthographic camera-facing width uses one shared parallel view direction, independent of eye/depth/position.
Perspective uses the actual eye-to-position sight. At a camera pole, cross(tangent,sight) has no unique width.
The declared pole treatment hemisphere-aligns that camera side to the transported base and smoothstep-blends
from transported width to camera width over sine(angle) 0..0.05. `camera_parallel` explicitly reports this band;
harness receipts must expose it. When the candidate camera width is nearly perpendicular to the transported
anchor (absolute dot below 0.1), hemisphere choice is roll-ambiguous and raises `FrameDiscontinuity` before
blending. It cannot silently choose one of two almost-opposite rolls from a tiny azimuth change. The caller must
provide a consistent anchor or split the strip, not suppress the error. A positive width whose two edges collapse
at current coordinate precision also raises; rebase geometry rather than inventing a minimum width. It is a defined geometric singularity treatment, not an error-recovery path.
It cannot make an end-on sheet broad without altering geometry; no width inflation is applied. Twist still
applies after this operation. Native camera-motion/edge coverage proof remains open.

The CPU frame probe uses the shared projection matrices and emits four diagnostic cards (oriented, twisted,
Orthographic-facing and Perspective-facing), plus full frame/vertex/UV traces and source hashes:
`.venv\Scripts\python.exe tools/labs/ribbon_frame_probe.py --output .artifacts/evidence/ribbon_frames/<new-run>`.
These are CPU-projected wire cards, not GL/native scene images or material/lighting acceptance.

## Proposed WR-02 allocation and topology contract (not allocated yet)

- At most 8 active ribbons, each with at most 256 knots and 8 longitudinal subdivisions per interval. Proposed
  maximum 2041 stations/ribbon; this CPU cap is enforced. The GPU population cap must be enforced at admission.
- Vertex-stage expansion starts as independent triangles: 6 vertices per interval, at most 12240/ribbon and
  97920/scene. No index buffer is required; explicit invalid/gap/cusp intervals emit no visible triangles.
  No triangle may connect the samples on opposite sides of a None station or strip break. Ends are open thin
  sheet edges, not closed volume caps. Tessellation/edge coverage remain bounded native image gates.
- Candidate std430 knot record: four vec4s (64 bytes): position.xyz/half-width; local-coordinate/twist/valid/reserved;
  tangent.xyz/reserved; untwisted base-side.xyz/reserved. 8*256*64 = 131072 bytes of knot payload. Proposed per-ribbon metadata budget is 64 bytes (counts/flags, phase/period,
  two colour vectors), or 512 bytes total, giving 131584 bytes per stream slot before alignment and fences. No GL allocation or performance claim follows from this arithmetic.
- Preserve absolute CPU coordinates. Proposed float32 upload rebases each history to its oldest coordinate;
  enforce a declared supported local time span (initial harness ceiling 64 s). Repeating strand phase uses a
  CPU-reduced origin phase plus local-coordinate/period, never a float32 copy of a huge absolute time. Test
  long-running insertion/eviction with fixed material marks before admitting the packing scheme.
- Use the existing shared stream/fence and context resource owners; no GPU live-count readback or per-frame
  reallocation. Record actual payload/metadata/alignment/ring bytes, draw counts and maximum-emission behavior
  in the independent harness. Change these proposed limits only with matching bounded-memory/work proof.
