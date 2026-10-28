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
WR-02a now supplies an independent oriented GPU strip prototype; see the admitted scope below.
Production-efficient packet construction, broader GPU coverage, OIT/defocus and full cost acceptance remain open. Scene composition, real audio, reflection and artistic acceptance remain later gates.

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

## WR-02a oriented GPU prototype and input contract

`core/ribbon_packet.py` owns immutable std430 packet admission. `rendering/gl_programs/ribbon.py` expands
centripetal centre-line knots into independent oriented triangles. `rendering/quick/scene3d/ribbon.py` owns
only its context-local program/VAO and shared `StreamRing`; it does not own camera/target/depth/blend, a mode,
clock, simulation or material authority. The standalone consumer is `tools/labs/ribbon_strip_probe.py`.
No runtime mode imports this prototype; EB and all existing modes receive no work or appearance changes.

- At most 8 admitted paths, 256 knots/path and 1–8 subdivisions/interval. Bounds apply before GL admission;
  at most 12240 vertices/instance and 97920/scene. Empty/non-drawable input allocates/uploads/draws nothing.
- Each path has 64 bytes metadata plus 256*64 bytes knot storage, even when fewer knots are live. Maximum
  packet 131584 bytes. std430 knot = position.xyz/half-width; local-coordinate/local-twist/valid/reserved;
  tangent.xyz/reserved; untwisted base-side.xyz/reserved. Metadata holds count/subdivision/origin phase/period,
  reduced origin twist, diagnostic colour and reserved colour storage. This is a diagnostic RGBA material,
  not the Ribbon scene's final shading or palette.
- Positions upload relative to the first active knot's float64 packet origin. The owner composes the supplied
  world MVP with that translation in float64 before float32 uniform upload; logical positions/eye remain fixed.
  Packets enforce a 1024-unit local spatial domain and float32 quantization checks. The spline derivative uses
  segment-local differences, so exact large-coordinate input cannot erase a tangent. Native translation to 1e6
  world units preserves the reference image byte-for-byte. Shader position varyings are packet-local; future
  lights/probes/eye inputs must use that same coordinate frame, not mix local and absolute spaces.
- Absolute CPU coordinates remain unchanged. Local float32 coordinates rebase to the oldest knot with a 64-second
  span ceiling and strictly preserved ordering. Periodic phase = CPU-reduced origin phase + local/period;
  at most 4096 periods/window. Twist similarly rebases to a reduced origin angle with at most 32 local turns.
  Nonfinite, collapsed-width or unrepresentable float32 positions/widths fail before upload. These limits are
  explicit prototype admission, not silent Settings clamps. Long-record phase/native rebase comparison passes.
- Vertex-stage expansion emits two independent triangles per subdivision. Both endpoint stations must be valid
  before any of their six vertices emit. Invalid/gap intervals cannot leave one vertex at an offscreen sentinel
  and stretch a surviving triangle across the viewport. Invalid outer support knots are replaced by endpoint
  extrapolation, so they cannot pull geometry across a gap. Ends remain open thin-sheet edges.
- GPU side frames interpolate the untwisted knot bases, project onto the local spline tangent, normalize and
  apply local authored twist. That is an initial GPU interpolation scheme, not a claim of exact continuous
  transported-frame equality for every curve. GPU camera-facing/pole behavior is **not implemented yet**.
- Diagnostic surface normals derive from actual triangle world-position derivatives and face winding; the
  native plane oracle catches reversed winding. Curved/twisted normal fidelity, near-plane/edge-on motion,
  all dynamic width/extreme-curvature cases and anti-aliasing remain native admission gates.

The primitive saves/restores program, VAO and SSBO binding 0/range, including thrown draws, and leaves inherited
framebuffer/viewport/scissor/depth/blend/texture state untouched. Native sentinels include an existing nonzero
SSBO range/generic binding. Legal current-context ownership is checked before GL work; foreign-context use or
retirement fails before touching resources. Successful release is idempotent and allows later reactivation. It drops the released stream owner, so a new
context gets a freshly sized alignment budget rather than reusing the previous context's slot shape.
Partial-admission/retry failure coverage beyond these focused cases remains part of the broader WR-02 gate.

The stream has three fixed slots, each MAX_PACKET_BYTES + actual SSBO alignment. On the measured driver this
is 394800 bytes of mapped buffer storage, plus the dummy 8-byte mesh, program and driver overhead (not a total
VRAM claim). Ring rotation/fences use the existing owner; no per-frame resource allocation or live-count readback.

### Native proof and cost boundary

Run `.venv\Scripts\python.exe tools/labs/ribbon_strip_probe.py --output .artifacts/evidence/ribbon_strip/<new-run>`
under the bounded process-tree launcher. The receipt records driver/viewport, 90 warm frames/case, packet/draw
caps, GPU draw query median/p90, CPU submit median/p90, and full reference packet-build CPU measurements.
Current receipt: `.artifacts/evidence/waveform_ribbon/wr02a_native_final/receipt.json`.

On RTX 4090 at 640x384: draw medians about 0.004ms (one 32-knot path) and 0.0195ms (eight 256-knot paths), CPU
submit medians about 0.12–0.16ms; both projections tested. Draw timing excludes packing and upload; submit timing
includes upload/bindings/fences but excludes readback/wait. Full stateless CPU fixture/frame/packet rebuilding
measured median 1.52ms for one path and 89.49ms at the cap (three build samples, p90 96.40ms). **This rebuild is
not admitted as a per-frame production path.** Cheap GPU draw is not a whole-mode cost or fidelity pass.

Next gate: incremental/cached logical frame and packet construction with measured changed-input cost and
continuity/epoch/eviction proof. Do not add a second cache/state authority or renderer-side simulation. After
that, broaden native curved-frame/normal/precision/lifecycle proof, then OIT/HDR, camera-facing GPU behavior,
AA/defocus and target composition. No GL scene likeness, music or full performance acceptance exists yet.
