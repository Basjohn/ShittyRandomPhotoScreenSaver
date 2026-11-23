# Native port playbook

Consolidated 15 Nov 2026 from decisions D12 to D16 (`Docs/Future_Work/Native_Core_P3_Decisions.md`, "Decisions" below),
the five checkpoint audits of 15 Nov ("Audit n"; their fixes are in the decisions' "As built" records, and the
closed report is in git history, `git show 66e64a363:Docs/Future_Work/Checkpoint_Audits_Nov15.md`), the verified Qt 6.12 facts
(`Docs/Future_Work/Native_Core_QRhi_Research_N3.md`, "Research Qn / section n"), the "3D foundation lessons"
(`Docs/Reference/Transitions.md`, "Lessons"), `native/core/README.md` ("How a new mode is built") and `Current_Plan.md`
item 8b's N3.4 and N4 decisions of 15 Nov ("Plan"). It decides nothing: every rule here is cited, and the cited text
wins when the two differ. D17 describes the N3.4 stages; the live follow-ups are in Plan N3.4.

## How to use it

A port brief names the sections it uses ("follow Native Port Playbook: the port checklist, the standard proof, E3 and
E10") and does not restate them. The catalogue entry for each primitive (what it is for, who uses it, today's
numbers) is `Docs/Reference/Primitives.md`; each section below links to its entry. A trap is a defect class an audit
found in this kind of code: the port proves it absent, with the negative control that fails without the fix.

## 1. The port checklist (every native port obeys these)

1. **A limited Python API in `module.cpp`.** The core's Python face is small; no Python slot on the core's threads, no
   call with a Python thread state (D5.4, `Primitives.md` section 4; the thread probe, Handbook section 8).
2. **Nothing per record on the render thread**: no allocation, no JSON, no list built. Every QRhi object is made at a
   build or warm-up unit; a state copy is made only when it changes (D15 point 8; D14 audit 2 M5; audit 4 L3; audit 5
   L1; audit 2 L5).
3. **Every count is checked against the resource it indexes**, at the record, because `robustBufferAccess` is off:
   vertices, instances, indirect commands, batches, storage instances, dispatch groups (D15 "draw counts are bounded";
   D16 audit 5 "as built"; audit 4 M1). A count past its buffer refuses that pass's draw with its reason, made once at
   the edge.
4. **One QRhi pass per hazard boundary.** Every compute entry is its own QRhi compute pass; a read-then-write in one
   pass is not covered by QRhi's tracker (D16 point 4, choice A; Research Q7).
5. **Never sample and render one texture's levels, layers or faces in one pass.** QRhi tracks usage per texture, not
   per subresource: one texture per mip level, six passes for a cube (Research sections 9 and 15; Plan N3.4).
6. **Validation reports a message id at most 10 times per process.** A negative control uses up its id's ten, so each
   control runs in its own process; a clean phase proves a hazard absent only before any control of its process
   (D16 audit 5 M4; audit 5 "as built").
7. **No by-value array arguments in shaders**: SPIR-V copies the array whole per call (Spline Curve 1.97 ms against
   0.030 ms). `tests/test_native_devcurve.py` scans for it; the scan must cover every product shader, including the
   transition fragments baked from Python strings and non-literal sizes (D12 "As built: Spline Curve"; audit 3 L1).
8. **Integer hashes and uv from the pixel.** Float `fract(sin())` hashes seam and flip by backend; take uv from
   `floor(vUv * u_target_px)` and a row or column key through integers (D13 "As built" N5.2a and N5.2b; Lessons;
   R-94). The same holds for any hash a mode already ships (N5.4: Waveform's glint cells lit differently per API).
   **Half floats overflow per API**: an additive write stack (lights, a reflection's summed alpha) that passes 65504
   goes infinite in OpenGL's 4x resolve where Vulkan's stays finite, and a bloom spreads it into squares; cap each
   write (hue kept) in the shared shader. **Hard cuts flip by compiler rounding** (a fog ground plane flipped whole
   cell rows): a short continuous fade, never a tolerance (N5.4, 22 Nov).
9. **Judge pixels only through the shared tolerance**, `tools/pixel_tolerance.py`: exact everywhere, the one-level
   class only through a mask derived from the reference, scatter and ties with measured caps, flips named by a
   decision. Never a histogram ("within 1 level") (D12 "The pixel tolerance"; audit 3 M1; audit 4 M2; audit 1 L1).
   A scene whose edges run along rows of pixel centres (ribbons) flips whole rows, so pixel counts cannot bound it:
   `pixel_tolerance.FrameStatistics` (mean, signed mean, share 2-3 levels, share past 3) with bounds 1.5x the clean
   worst, every control failing (N5.4).
10. **The hidden-host owner list in `tests/test_quick_backend_owner.py`**: a new hidden host or a changed Quick
    graphics configuration is entered there, and a hidden host calls the product's Quick graphics configuration
    (`Docs/Guardrails/Agent_Worktree_Rules.md`, Environment; the test is the list).
11. **Cost by absolute times**, GPU median and p90 per pass over at least 90 frames on the GPU timer, the GPU state
    recorded (`nvidia-smi`, other processes, the display state); timing and cost run as soon as they are due (the operator
    is not using the machine; never wait for a "quiet machine"); rerun only a figure that fails and whose recorded
    conditions show load from another run (D14 point 13; D16 "Cost"; Lessons "Measuring"; memory notes on display state).
12. **Declared data, one owner per name.** Every member, count and selector is filled by name from exactly one of the
    core's conventions, the settings or a record field; unknown, unfilled and doubly owned names are refused with a
    reason (D12 point 2; D15 point 1). A record field fills a block member or a stream, never both.
13. **Nothing at rest, retirement to zero, lost-state edge.** Nothing is recorded or dispatched for a re-record of the
    same frame; everything is released with the content on the render thread; a content made again tells its owner
    once (D14 point 3; D15 point 2; D16 point 7 and choice I).
14. **Anything that appears or disappears fades**; a refused frame keeps the last drawn one (D12 point 5).
15. **A native route beside QRhi needs the lead's line first**, with its OpenGL twin; agents stop and report the
    measurement (Handbook section 8; D15 point 7; D16 point 5).
16. **Convert the Python shader first**, in the Python renderer, with stills before and after; the core then draws the
    same file, and parity is judged against that conversion (D15 point 5, choice F).
17. **Formats and conventions**: no RG16F, RG32F or R11G11B10F in QRhi (widen, or two R16F, Plan formats box and
    Research section 14); no 64-bit shader types (D4); no restart index, wide lines or point sprites (Research section
    18; D15 point 5); one clear value for every attachment (Research section 8); no clamp-to-border (Research
    section 13); core targets top-left, Y down, one correction at upload (`Primitives.md` section 7, Portability).
    **Check row order before the first parity figure**: the core draws its targets top row first, Python bottom
    first. Under multisampling a whole-frame flip mirrors the sample pattern, so every slanted edge differs by a
    quarter of its contrast and bloom carries it further (N5.2c's and N5.2d's edge flips, N5.4's left-edge bloom,
    22 Nov). A mode that needs exact parity draws in Python's row order (the composite's `scene_rows: "up"`,
    N5.4); a transition may admit the flips as a guarded class.
18. **Registration comes last.** Offering a mode on a backend (`GENERIC_MODE_SETTINGS`, the descriptor's
    `renderer_backends`) is the port's last code step, after rule (a) and rule (b) pass
    (`Native_Parity_And_Timing_Proof.md`). Layer T needs the registration to time the native path, so the lead
    registers it in the main checkout uncommitted, runs layer T (its Vulkan live run is also the D10 rehearsal), and
    commits the registration once T passes. A commit that registers before rule (b) passes is held out (D10).

## 2. The standard proof (named "standard" in each section)

The full method across logic, pixels, timing and cost, and how much of each to run for a port or an optimisation,
is in `Native_Parity_And_Timing_Proof.md`.

Every port, on the primitive's own harness in `native/core/python/*_check.py`, on OpenGL and Vulkan in a hidden host
(`Docs/Guardrails/Agent_Worktree_Rules.md`; `Handbook` section 8):

- Rule (a): the native OpenGL result against the Python renderer. Rule (b): Vulkan against native OpenGL. Both through
  the shared tolerance (checklist 9) with the mask named: the translucent pixels found by drawing the reference over
  two backgrounds or from its own alpha, or the pixels a blended layer sums into; float textures judged by their own
  ulp (D12 "The pixel tolerance"). Bounds are the measured worst times 1.5, stated beside their measured reasons.
- A Visualizer mode: owner-level parity on recorded music, logic, timing and cost; `Native_Parity_And_Timing_Proof.md`
  owns the method (layers L, P, T, C; material, how much to run, acceptance). It is not repeated here. A transition:
  fidelity and performance only (that guide's section 3, "A transition port"), never the mode method.
- Negative controls for every rule, each seen failing on the broken form (a one-level shift on every pixel, a fixed
  artefact, the wrong order, the skipped release); `tests/test_pixel_tolerance.py` holds the tolerance's own.
- Vulkan validation with synchronisation checks and the shader-access opt-in: `syncval_shader_accesses_heuristic` is
  off by default in the layer and enabled for the harness through `VK_EXT_layer_settings`; without it a control
  reports nothing and a clean run proves nothing (D16 audit 5 "as built"). Consecutive records with no readback
  between them: a harness that reads back between records hides a missing barrier (audit 2 H1).
- Nothing at rest, no object or allocation over a steady minute (a remade-streams control must fail), retirement to
  zero with a skipped-release control (D15 "proof"; D16 "proof").
- Cost once, without the validation layer (it distorts GPU times), with the GPU state recorded (checklist 11).
- A port's core change is additive: a new path, key or flag that only the port's own content asks for, so every
  existing user (accepted modes, transitions) stays byte for byte on its current path and needs no re-proof.
  Changing what an existing shared path does for its current users is the lead's decision first, never a port's.
- The earlier harnesses rerun unchanged only where the port's change reaches them (D15 choice C, narrowed by the
  regression-guard rule, `Native_Parity_And_Timing_Proof.md` section 3): the harness of every primitive or core path
  the port's C++ touches, named with the reason in the report. A data-only port reruns none but its own; all of them
  only after a change to a path every mode shares (the generic content, the route, the packet ABI's layout).
- Run each negative control in its own process (checklist 6).

## 3. Sections by primitive

<a id="pb-fullscreen"></a>
### N4.a Fullscreen pass, samplers and textures (D12, D13; catalogue: [E4](../Reference/Primitives.md#e4), [E29](../Reference/Primitives.md#e29))
- Contract: a mode's pass is a fragment over the core's triangle, filled by name; samplers and up to 8 RGBA8 textures
  are data, uploaded once on the render thread (D13 points 1, 3 and 4); the input `v_uv` or `vUv` is named by the
  fragment.
- Traps: a core member meaning two things (`u_resolution` against `u_target_px`, D13 point 2); a placeholder texture
  drawing a wrong picture (D13 "Rejected"); a refused program retried every update (audit 3 L2); a stream bound again
  keeps its schema (D13 point 6; audit 4 H1).
- Proof: standard; `fullscreen_pass_check.py`, `transition_route_check.py` (rule (a) exact for the seven, scatter caps
  per D12), textures' lifetime counts (`composite_live`).

<a id="pb-e2"></a>
### E2 Meshes, vertex stages and streams (D15, N3.2; catalogue: [E2](../Reference/Primitives.md#e2), [E23](../Reference/Primitives.md#e23))
- Contract: a pass may bring its own vertex stage; meshes are content-scoped data uploaded once; streams are `Dynamic`
  instance buffers or `Static` storage buffers from record `f32` fields; sprites are instanced quads; `firstInstance`
  is always 0 (D15 points 1, 2, 4, 5 and 6).
- Traps: a stream bound again under a new schema keeps pointers into the old one, a use-after-free (audit 4 H1); an
  instance stream drawn past its used length reads another frame slot (audit 4 H2: only a storage stream keeps bytes
  past `used`); counts unbounded (audit 4 M1); list built per record (audit 4 L3); a failed upload leaves the old mesh
  drawn (audit 4 L5); a batched pass's draw-parameters pack unchecked (audit 4 L1); `gl_BaseVertex` is 0 on OpenGL and
  HLSL refuses the draw parameters (D15 "draw parameters' values"); a mesh replaced by one of the same layout rebuilds
  the content (audit 4 L2).
- Proof: standard; `mesh_buffer_check.py` (rounds parity, forms, used, rest, steady, retire; controls: out-of-step
  stream, first offset, wrong front face, `instances_past_used`, `firstInstance`, remade streams, skipped release);
  sprites judged against their own quad conversion, never `gl_PointSize` (D15 "decided from the first proofs").

<a id="pb-e9"></a>
### E9 The block arena and pass blocks (D15 point 3; catalogue: [E9](../Reference/Primitives.md#e9))
- Contract: every block of a content lives in one `Dynamic` uniform buffer at `ubufAligned` offsets, written once per
  record by the fast path only; a pass binds at most 4 dynamic-offset blocks; C++ packs from reflected offsets (D15
  point 3 and choice D; N0.3 rule 5).
- Traps: mixing the fast path with batch updates on one buffer (D15 point 3); a block past `MaxUniformBufferRange`;
  Vulkan's dynamic-descriptor limit unchecked by QRhi (D15 point 3, `vulkan_device_facts`).
- Proof: standard; `mesh_buffer_check.py --rounds forms` (sixteen draws at sixteen offsets equal sixteen passes bit
  for bit); the Python packer is the oracle (`tools/conventions_identity.py`).

<a id="pb-e3"></a>
### E3 Scene targets (D14, N3.1; catalogue: [E3](../Reference/Primitives.md#e3))
- Contract: targets are data (at most 4 colour attachments, one D32F depth, a sample request through
  `scene3d.scene_samples`); 64 px buckets, grow at once, shrink with two-bucket hysteresis, decided at the size edge;
  multisampled targets resolve first and depth through the core's nearest pass (D14 points 1, 2, 7, 8 and 10).
- Traps: unsynchronised colour resolve in every steady multisampled frame on Vulkan, hidden because the gate read
  back between records (audit 2 H1; `primeResolvesForPass`, `prime_control`); a cost round that cannot pass on OpenGL
  (audit 2 M1); an earlier `target_size` overriding a new program's (audit 2 M3); sampling a target before any pass
  drew it (audit 2 M4: only with `"previous_frame"`, never multisampled); per-axis re-bucketing (audit 2 L1); QRhi's
  depth resolve gives wrong values on both backends, so never `setDepthResolveTexture` (D14 point 10); a fast clear
  through the load op (D14 point 12, rejected: NaN after a capture on Vulkan); a one-sample multisampled object
  (Lessons).
- ABI 42 (N5.6): at most 6 targets and 48 passes a program (the missing-mesh mask one bit a pass); a cube target
  (`"cube": true`, explicit square, one RGBA16F, exact) is E14's. Every colour prime takes every layer.
- Proof: standard; `scene_target_check.py` (analytic nearest depth within 8.7e-8 against the sample-0 control, the
  clamp, the drag across bucket edges against the no-hysteresis control, `--rounds prime_control` on Vulkan alone,
  `python_cost` and `cost_parts` at 4K; multisampled output judged repeat-relative, D14 point 8).

<a id="pb-e10"></a>
### E10 Compute passes and storage (D16, N3.3; catalogue: [E10](../Reference/Primitives.md#e10), [E5](../Reference/Primitives.md#e5), [E11](../Reference/Primitives.md#e11))
- Contract: a compute entry is its own QRhi compute pass in the pass list, under a `frame` or a record `u32` trigger,
  with `fresh`; storage buffers and 2D or 3D images are `Static`, content-scoped, shared with draws; barriers come
  from each binding's declared access, checked against the pack's reflection; no readback but D4's pair self-check
  (D16 points 1 to 8; choices A, C, E, G).
- Traps: a program without storage keeps the earlier program's buffers (audit 5 M1); `fresh` per content restarts a
  stateful entry while its buffer is kept (audit 5 M2); one resource bound twice with two accesses in one entry
  (audit 5 M3; QRhi keeps one access a pass); a trigger consumed by a record that dispatches nothing (audit 5 L2); no
  byte bound on image storage (audit 5 L4); a resize's replaced buffer released inside the record that copied it
  (D16 "as built"); no indirect dispatch in QRhi 6.12 (D16 point 5); NVIDIA hid a missing barrier (Lessons).
- Proof: standard; `compute_pass_check.py` (every resource exact; the triggers: a re-record dispatches nothing and the
  `trigger_every_record` control integrates twice; two controls: `write_as_read` reports read-after-write, the
  single-pass pair write-after-read, each in its own Vulkan child; the pair-check kernel with its `precise`-dropping
  control; OpenGL judged by GPU time because barrier calls cannot be counted).
- ABI 42 (N5.6): geometry once per key (D3 as built: a geometry buffer from the activation's arena, uploaded once a
  key, `"<name>@previous"` for a rebase entry); the check readback (a `"once"` entry's `"readback"`, reported
  in the state's `"check"`). Trap: a field only the core reads (a key, a `"when"`) is the program's read, never
  `unread`. Proof: `eb_core_check.py --rounds geometry readback` (both backends, each with its control).
- ABI 44 (N5.6): buffer declarations are program-wide, including geometry buffers. Each compute entry binds only
  its own storage buffers, images, streams and meshes. The caps are in `compute_passes.h`. Proof:
  `eb_core_check.py --rounds compute_bindings` admits the Extruded Bubble drift graph, exercises the limits and
  counts clears and prefix copies during a resize.

<a id="pb-e8"></a>
### E8 Stream ring (D15 point 7; catalogue: [E8](../Reference/Primitives.md#e8))
- Contract: not built; QRhi stays pending a materially measured case and lead admission. The stream-ring harness
  brackets each route with same-run resident floors, retaining raw milliseconds and the unchanged 0.05 ms admission
  signal. The floor-median drift sensitivity distinguishes a resolved result from a repeat-required one; p10/p90
  tails and ratios remain descriptive
  (`mesh_buffer_check.py --rounds stream_ring`; [D15 point 7](../Future_Work/Native_Core_P3_Decisions.md#stream-ring-floor-protocol)).
- Traps: building a native pair beside QRhi without the lead's line (checklist 15); `QRhiBuffer` has no `createFrom`
  in 6.12 (D15 point 2).
- Proof: both CPU and GPU median excesses must resolve below 0.05 ms against both bracketing floor medians for every
  route. A material median excess is actionable lead evidence; floor-median drift crossing the margin is
  inconclusive and requires a repeat under stated conditions. Tail spread alone does not gate median admission.
  Neither outcome admits a native pair. Missing native record counters fail; GUI wall time cannot substitute.

<a id="pb-e4"></a>
### E4 and E19 Bloom, HDR, OIT and the defocus layer (N3.4; catalogue: [E4](../Reference/Primitives.md#e4), [E19](../Reference/Primitives.md#e19))
- Status: source audit and native repair proofs complete (D17; `native/core/src/post_stages.*`; harness
  `native/core/python/post_stage_check.py`). The remaining OpenGL defocus investigation is non-blocking
  (operator, 16 Nov 2026); each consumer still proves its own parity, lifecycle and measured cost. Detailed stats,
  controls and failed avenues remain in R-232. Declaring a stage: `native/core/README.md`.
- Note: as built, the defocus layer's mips DO use QRhi's `generateMips` (D17 choice G, this layer only); bloom and
  HDR chains never do.
- Contract: each stage is opt-in and absent from a mode that does not use it; OIT only where
  `PerRenderTargetBlending` is true, else the mode's sorted path, recorded once; revealage stored inverted as coverage
  (one clear value); bloom and HDR chains are one texture per level, our own downsample with `textureLod(..., 0)`,
  never `generateMips` (Plan N3.4; Research sections 8 and 9).
- Traps: levels of one texture rendered and sampled in one pass (checklist 5); blendability of RGBA16F and R16F is
  unchecked by QRhi, so the core checks `COLOR_ATTACHMENT_BLEND` at device creation; `independentBlend` is not
  enabled by Qt on an imported device; the transparent pass needs N3.1's `primeDepthForLoad` (Plan; Research
  section 8); post effects work only from emitted light (Lessons); masks are per draw-buffer index (`Primitives.md` E19).
- Proof: standard; the harness proves the inverted coverage equal to the textbook revealage form on a known stack of
  layers (Plan N3.4); bloom cost per pass on the GPU timer.
- ABI 42 (N5.6): a pass's `"when"` (a record u32) skips a draw or a defocus step at 0 (never a bloom or an
  environment step: what they make is read later); the program puts it on every entry of the absent work. Proof:
  `eb_core_check.py --rounds skip` (the frame equals the program without the layer; control: the program-only
  form still draws).

<a id="pb-e21"></a>
### E21 Shadows (N4.h, N4.l; catalogue: [E21](../Reference/Primitives.md#e21))
- Status: decided, not built.
- Contract: a depth-only `D32F` render target sampled with a `Linear` sampler and a compare op; the shader branches on
  `isClipDepthZeroToOne()` from a uniform; outside the light frustum is handled in the shader (Plan N4.h; Research
  section 13).
- Traps: depth bias is baked per pipeline and its unit is implementation-defined, so tune and measure it per backend,
  never one number; GL stores compare state on the texture, so keep a shadow map on one sampler; no clamp-to-border;
  the rejected Extruded cast shadows stay rejected (`Primitives.md` E21; R-125 to R-128).
- Proof: standard; a one-texel compare-direction test on both backends before any shader depends on it (Research
  section 13); no mode turns it on without its own review (Plan N4.h).

<a id="pb-e13"></a>
### E13 and E14 Planar reflection and the scene probe (N4.d; catalogue: [E13](../Reference/Primitives.md#e13), [E14](../Reference/Primitives.md#e14))
- Status: the scene probe built (N5.6 box 1, ABI 42); the planar reflection decided, not built.
- Contract: a cube is six passes, one render target per face (`setLayer`); rough-receiver prefiltering is the core's
  own shader, never `generateMips`; the reflection lookup takes its uv from the main camera's clip position (Plan
  N4.d; Research section 15). As built: a cube target (`"cube": true`), a pass's `"face"`, one prefilter step
  (`{"name", "prefilter": <cube>}`: probe.py's 32-tap cone per level and face into a stage cube, copied into the
  cube's level), a `samplerCube` with mips. A face holds OpenGL's cube-map rows on both backends: drawn through
  `uMatrix` from item pixels, or with `v_uv` (y down: OpenGL's NDC y is 1 - 2 v_uv.y).
- Traps: face orientation may be mirrored between OpenGL and Vulkan (read every face back on both first); a mirrored
  view reverses winding (set the cull face); `gl_FragCoord / resolution` has a different origin per backend;
  looking up a reflection by screen position instead of the reflected ray (Lessons).
- Proof: standard; the per-face colour readback on both backends; the planar clipping, resize and failure-path boxes
  that `Primitives.md` E13 lists as open. The probe's: `eb_core_check.py --rounds probe` (every face and level
  against a CPU twin of probe.py's chain; lookups at levels 0, 2 and 3 and across face edges; controls: swapped
  faces, a per-face box chain, a clamped read). Traps found there: a cube's layers left out of a layout prime
  (Vulkan VUID-vkCmdDraw-None-09600), a cube's mipped sampler refused as a defocus layer's.
- Extruded Bubble reference: the cube backdrop writes colour and uses the face dimensions for Ember Grain. The screen
  backdrop samples shafts and writes colour and emission. Both variants share the `EbFullscreen` layout. The recorded
  replay matched all 24 frames across ordinary and active-grain runs. The zero-size grain control differed on all 12 of
  its frames. The [local proof](../../.artifacts/evidence/visualizers/extruded_bubble/capture/20261123_backdrop_grain_comparison/report.md)
  retains frame hashes, comparison media, timing samples and QSB reflection for this conversion.

<a id="pb-e24"></a>
### E24 Heightfields (N4.e; catalogue: [E24](../Reference/Primitives.md#e24))
- Status: decided, not built.
- Contract: vertex-stage sampling through the binding's `VertexStage` flag with `textureLod` or `texelFetch`; the
  heightfield is R16F or R32F read with `texelFetch`, so 32-bit float filtering is never required (Plan N4.e;
  Research section 16).
- Traps: a bare `texture()` in a vertex shader is not valid on Vulkan; no feature flag exists to gate on, so gate
  the format on the facts probe; a heightfield the host updates per frame counts in the per-frame budget.
- Proof: standard; the compute-write to vertex-read barrier is the same mechanism proved in N3.3 (Research section 16).

<a id="pb-e15"></a>
### E15 and E20 Volumes, fog and light shafts (N4.f, N4.k; catalogue: [E15](../Reference/Primitives.md#e15), [E20](../Reference/Primitives.md#e20))
- Status: decided, not built.
- Contract: volumes are written by compute as a 3D storage image in one pass (D16), never per-slice rendering; sampled
  with `sampler3D`, `ClampToEdge` on all axes, `RGBA16F` or `R16F` with a linear sampler (Plan N4.k; Research section
  17).
- Traps: `RenderTo3DTextureSlice` on Vulkan needs a 1.1 instance (the facts probe reads the adopted instance's
  `apiVersion`); a 3D texture cannot be multisampled; the fog's steady share must never be eroded (`Primitives.md`
  E15); the shaft source downsample reads a multisampled texture (N1.8's resolve-first set).
- Proof: standard plus the 3D slice-by-slice readback proved in N3.3 (D16 "3D storage images").

<a id="pb-e5"></a>
### E5 and E6 Motion blur and trails (N4.i; catalogue: [E5](../Reference/Primitives.md#e5), [E6](../Reference/Primitives.md#e6))
- Status: built (ABI 37, N5.2d: data on the core, no stage of its own).
- Contract: the velocity is two R16F attachments (QRhi has no RG16F), RGBA16F only if measurement shows two cost more;
  multisampled, it resolves through QRhi's average (the lead, 21 Nov: Python averages its samples too; a core "mean"
  resolve only if rule (b) shows the backends differ, and N5.2d's 4x frames showed none); the tile max is compute
  (trigger "draw") over a storage image in a format both backends list as load-store (Plan formats box and N4.i;
  Research section 14; D14 point 10). The post passes are Python's texts with an `SRPSS_NATIVE_CORE` frame helper (the
  core's target is Python's allocation flipped whole, its velocity y negated: read back on the build). A vertex stage
  writing its own clip depth after `uMatrix` ends with `native_clip_depth`'s line (Vulkan's depth is 0..w).
- Traps: a biased RG16 cannot encode zero velocity under one clear value; velocity averaged across an edge is wrong
  on Vulkan and arbitrary on OpenGL; a tile loop in one fragment pass starves the GPU (Lessons); a missing barrier
  hidden by the vendor (Lessons).
- Proof: standard; the D5.6 row 13 control: unused widened channels filled with non-zero values in a test (Plan).

<a id="pb-e11"></a>
### E11 Compacted populations (N4.c; catalogue: [E11](../Reference/Primitives.md#e11))
- Status: decided, not built; high potential, built without a consumer.
- Contract: a 1:1 port on QRhi's `drawIndirect` over a compute-written command; "draw the maximum, cull in the vertex
  shader" only for a backend without `QRhi::DrawIndirect`; the port queries `DrawIndirect` and `DrawIndirectMulti` at
  runtime and records the answer (Plan N4.c; D15 point 6; D16 point 2). ABI 41 (22 Nov) reads them in the storage
  state's device facts (`draw_indirect`, `draw_indirect_multi`; one answer the admission, the facts and the
  draw-parameters forms take) with the harness control `hide_draw_indirect`. Recorded on this machine (RTX 4090,
  driver 621.01, Qt 6.12.0): OpenGL 4.6 and Vulkan both report both true; under the control both read false, the
  indirect population is refused with the DrawIndirect reason and the direct one draws, and off again the two are
  equal (`compute_pass_check.py --rounds indirect`; `native_core/n3_3/20261122_abi41_indirect`).
- Traps: the compute-written commands are the mode's own trusted output, unchecked by the core (D16 "as built"); a
  `firstInstance` in a command is legal on Vulkan only with `drawIndirectFirstInstance` (D15 point 6); compact only
  when the pool is large (Lessons).
- Proof: standard; the indirect population equal to the direct one (`compute_pass_check.py`); the harness at one
  million sprites, the indirect draw against the cull path, same pixels, cost recorded (Plan N4.c).

<a id="pb-e12"></a>
### E12 Ribbons and strips (N4.b; catalogue: [E12](../Reference/Primitives.md#e12))
- Status: decided topology rule, not built.
- Contract: triangle lists or degenerate strips, never a restart index; no wide lines; lines and points are instanced
  quads (Plan topology rule; Research section 18; D15 point 5).
- Traps: OpenGL restarts every topology, Vulkan only strips; interpolants clamped before `exp` and history shape
  band-limited (Lessons).
- Proof: standard; judged against the Python renderer's own quad conversion (checklist 16).

<a id="pb-e16"></a>
### E16 and E17 Per-run fields: the edge field and the propagation field (N4.g, N5.2g; catalogue: [E16](../Reference/Primitives.md#e16), [E17](../Reference/Primitives.md#e17))
- Status: built 22 Nov at ABI 43 (N5.2g; consumers Edge Bloom and Capillary Bloom). D9's consumer class (a): a
  transition's preparation run as an async job.
- Contract: a field is an item texture the core makes from a recipe (`mode.field(recipe, packs, blocks, pixels=,
  size=, deadline_ms=)`): a flat list of compute dispatches over named recipe images (r16f, r32f, rgba16f, rgba32f),
  in the Python owner's order exactly, each dispatch a baked compute pack and an std140 block Python packs
  (`rendering/quick/scene3d/native_fields.py` holds the builders: `edge_field_recipe`, `propagation_recipe`). The core
  admits a recipe by the packs' reflection (compute stage, set 0, at most one uniform block, a block's bytes the
  reflected size up to its 16-byte rounding, an image bound by name with its format and an access its qualifiers
  allow, samplers only on the input, unknown or unbound names refused) and refuses past its limits (8 packs, 64
  blocks of 4 KiB, 8 images, 512 dispatches, 4 outputs, 8192 texels a side, 256 MB); outputs are rgba16f, rgba32f or
  r32f, distinct and never the input (`field_recipe_check` is the admission alone).
- One recorder, two forms: on Vulkan the job service records the recipe on its own QRhi (the job uploads its input
  photo from `pixels`, so it never waits on the frame's upload) and publishes the outputs together; OpenGL, a failed
  job service, or a job past its deadline records the same dispatches in the frame at the input's commit. The
  deadline is the core's (`deadline_ms`; the layer passes half the run's settled margin, `field_deadline_ms`); while a
  deadline job is in flight the source records every frame. A generation that fails is not retried.
- The ready edge: `NativeMode.on_textures_ready(callback)` (GUI thread) names the textures each commit made ready. The
  layer keeps the old picture until every field of the run is in, then starts the effect's clock at that edge
  (`_clock_offset_ns`), and removes the fields at the run's end. R32F is an item-texture format (no mips) from ABI 43.
- Traps: the core's rows run top first, so a fragment that differentiates a field with `dFdy` takes the measured sign
  under `SRPSS_NATIVE_CORE` (Capillary: +1; -1 put up to 140 levels on its front); the two APIs' compute round r16f
  stages apart by a hair, which a threshold or hysteresis turns into a few texels (Edge Bloom's contours at fine
  detail), so judge such a fragment's rule (b) with a guarded class, never by retuning the field; QRhi has no RG
  formats (the flood is rgba32f, N1.7); a run's first effect frame on a cold driver cache creates its graphics
  pipeline on the render thread (31 ms at 4K, once per install and driver: N3.6's warm-up policy owns it).
- Proof: standard; `native/core/python/field_check.py` (the job form equal to the in-frame form on Vulkan, OpenGL
  in-frame, the deadline's fallback at 1 ms, the ready edge once and nothing recorded at rest, retirement to zero,
  synchronisation validation with shader accesses clean; `native_core/n5_2g/20261122_fields`), then the route check's
  N52G variants (`transition_route_check.py`) with the fields committed before each round, and `--cost`, which also
  times a run's start frames and its fields' ready time.

<a id="pb-e28"></a>
### E28 and E29 Backdrop pyramid and the background layer (D7, D13, N5.7; catalogue: [E28](../Reference/Primitives.md#e28), [E29](../Reference/Primitives.md#e29))
- Contract: the pyramid is built from the core's background layer texture only when changed and only while demand is
  above zero, within 0.3 ms at 2560 x 1440 and 0.6 ms at 4K; the photo upload is an async job (D7; D13 point 4;
  D9).
- Traps: the blit and its dirtied states exist only in the Python OpenGL path (`Primitives.md` E28); the protected
  clip and background commits are never retuned.
- Proof: standard; `backdrop_pyramid_check.py` and `background_layer_check.py` (the pyramid levels against Python,
  one build per photo or dimming change, demand 0 builds nothing).

<a id="pb-e1"></a>
### E1 and E27 The item quad, the composite and the program cache (D5.2, N3.6, N3.7; catalogue: [E1](../Reference/Primitives.md#e1), [E27](../Reference/Primitives.md#e27))
- Contract: each surface reaches the window as a texture provider the composite samples; Qt applies clip, opacity and
  batching; every state combination is a pre-built pipeline warmed gradually (`Primitives.md` section 4; Plan N3.6).
- Traps: release timing (`QRhi::finish()` only outside a frame, Plan N3.6); a hidden host not calling the product's
  Quick configuration (checklist 10).
- Proof: standard; `composite_check.py` (texels one to one, the clip contract).
