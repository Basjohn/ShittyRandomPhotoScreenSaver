# Waveform Ribbon: lab execution and visual evidence plan

This is the detailed execution/evidence owner for **Waveform Ribbon**, subordinate to
[`Current_Plan.md`](../../Current_Plan.md) §6 (S3D shared prerequisites) and §7.0–7.1 (lab first, then production).
The operator's [concept brief](../Future_Work/Waveform_Ribbon.md) owns intent and hard gates A–H. This document
decomposes those gates; it does not admit implementation, reorder the live plan, or declare any visual validation complete.
WR-00 execution is authorized and its reference/projection preflight is implemented. A scene lab, GPU ribbon primitive,
production mode, artistic match, music-window selection and performance acceptance are still unimplemented/unaccepted.

Use this document when the mode is admitted. Recheck the named source owners before each slice. Keep live sequencing
in Current_Plan, detailed work/evidence here, durable shared contracts at their existing owners, and failed-method
history under the existing Historical Bugs policy. An absent reference or missing native/operator evidence remains an
explicit **Awaiting Assets**, **Awaiting Logs** or **Awaiting Validation** gate, never a green checkbox.

## 0. Current execution boundary

- [x] WR-00 source custody: primary board rechecked/extracted unchanged; panel cards generated at original aspects.
- [x] Diagnostic projection fixture: Orthographic default and optional Perspective use the existing shared matrix
  helpers. Tests cover fixed world scale under resize/depth and near/far clip mapping; existing native sphere/ray
  tests independently exercise shared Orthographic geometry, origins and occlusion.
- [ ] Confirm annotation masks/crop boundaries, target measurements/tolerances, scene eye/pivot/world/palette and audio windows.
- [x] WR-01a bounded absolute-coordinate CPU history and centripetal interpolation reference.
- [x] WR-01b CPU transported/camera-facing frames, gap/cusp policy and width/UV stations; proposed GPU budget recorded.
- [x] WR-02a independent oriented GPU prototype: bounded packet/ring, both projection matrices, solid geometry,
  native bounds/gaps/plane-normal/phase-rebase/depth/context/state checks and 90-frame draw timing.
- [ ] WR-02 input-cost gate: incremental logical frame/packet construction; full reference rebuild is too costly.
- [ ] WR-02 remaining: curved/edge/near-plane/normal precision, OIT/HDR/camera-facing GPU/AA/defocus and full lifecycle/cost proof.
- [ ] WR-03 onward: actual scene blockout, material/reflection/particle work, music, production and visual acceptance.

Run `.venv\Scripts\python.exe tools/labs/waveform_ribbon_preflight.py --output .artifacts/evidence/waveform_ribbon/<new-run>`.
It refuses overwrites, copies the unmodified primary, extracts provisional native-size low/high cards, and records
archive/member/output/producer hashes, tracked diff hash, workspace status and both diagnostic projection matrices.
The initial receipt is `.artifacts/evidence/waveform_ribbon/wr00_reference_projection/receipt.json`.
It records no GL scene capture or cost: this is a preflight, not an image of a proposed Ribbon implementation.
Diagnostic half-height 4/reference depth 10 are arbitrary calibration units, not an approved artistic camera fit.

### Camera contract for all following slices

Design Waveform Ribbon for **Orthographic by default**, with Perspective as a separately exercised optional choice.
Use the shared admitted physical eye, pivot and world; record projection kind, physical half-extents/magnification,
clip range and actual inner viewport aspect in the scene signature. Low/high never changes these values. Widening
reveals additional fixed world at preserved scale; no actor stretch or audio-driven lens/pose/population changes.
Perspective's FOV is relevant only in that projection. Do not fit a Perspective scene and assume a matrix swap
establishes Orthographic likeness. A still cannot uniquely recover 3D camera position, and Orthographic has no finite
projective horizon: fit floor boundaries and visible landmarks without warping the reference.

Reuse `orthographic_matrix`/`perspective_matrix` from `core/settings/framed_camera.py` and parallel ray origins,
directions and footprints from `rendering/gl_programs/framed_camera.py`. The existing `view_matrices` and
`project_point` helpers are Perspective-only: Orthographic landmarks must use the actual admitted MVP/half-extents.
A lab-only camera spec may be passed directly to shared axes/eye admission; do not register a production mode or
copy a camera controller merely to draw a fixture. Full eye/floor/clearance bounds remain a WR-03 admission task.

WR-01/02 camera-facing strips must use the parallel view direction in Orthographic, not `normalize(eye-point)`.
WR-05 planar reflection must derive the mirrored virtual eye/projection from the admitted main camera; do not
readmit that reflected eye through the main camera's above-floor bound. Validate reflection landmarks and clipping
in both projections independently. Native round-sphere proof does not establish ribbon/floor/reflection fidelity.

## 1. Reference custody and target authority

### 1.1 Originals actually inspected

The local, git-ignored source is `references/waveform_ribbon_concept_package.zip`.
Its SHA-256 at planning inspection was
`6789029a6561b5e895c89e9310114d4a2540554b7749af70baa5e63c5c8e98c9`.
Archive member paths are exact:

| Member | Evidence inspected | Role |
| --- | --- | --- |
| `waveform_ribbon_package/Waveform_Ribbon_Concept.png` | Original 1672 × 941 pixels; SHA-256 `f8a4808f0bc781ec3d6cdf7dae7b98f01a5a12e939ddfb1f9d49d74eb368eadf` | Primary annotated board with low/high panels, palette and explicit stable-scene instructions |
| `waveform_ribbon_package/Waveform_Ribbon_Alternate_Annotated_Mock.png` | Original 1240 × 396 pixels; SHA-256 `19161837f26e2b38005b0ca781e256ff5a96fe5b006b954cc300809f6472adb2` | Context only; the copied brief approves the primary board, not this alternate |
| `waveform_ribbon_package/Waveform_Ribbon_Architecture.md` | Package prose inspected; existing brief reproduces it | Intent, suggested mappings, gates A–H; feasibility prose is not implementation proof |

Original image bytes were extracted without editing to
`tmp/waveform_ribbon_plan_reference/waveform_ribbon_package/` and viewed at their native source dimensions.
This scratch extraction is not a new asset authority or guaranteed handoff payload. Re-extract from the original
package when necessary; never replace a missing original with a generated approximation. Hashes identify this
reference review, not mutable operator presets or permanent artistic test goldens.

**Reference authority:** the copied operator brief explicitly names the primary as the single approved concept image.
The archive's extra alternate does not override that instruction or require another approval before work can begin.
Its high panel has orange/peach light and a sparse black background; the approved primary retains cool
cyan/blue/violet/magenta light columns and hall structure. Do not average them into a third look or switch to the
easier one. An alternate variant requires a later explicit operator instruction and independent target measurements.

### 1.2 What the pictures establish

| Target component | Observed in the primary image | Consequence for the lab | Inference / unresolved detail |
| --- | --- | --- | --- |
| Composition | Ribbons travel broadly left-to-right across the lower-middle of both panels, extending beyond panel edges; dark space remains above | Block out projected path envelope and floor before shader embellishment; retain offscreen continuity | The image does not establish travel direction or phase speed in time |
| Low react | Several thin, legible overlapping cool bands; broad gentle waves, restrained glow, sparse points; environment remains visible | Quiet passages need a composed minimum body, separated strands and motion | Exact ribbon count is ambiguous: inner strands are not separate ribbons |
| High react | Larger vertical sweeps and broader/brighter sheets; more crossings, fine points and floor light; ribbon is still the main subject | Increase body/deformation/detail within the same camera and world; retain dark negative space | Exact widths, ratios and peak timing require measurement and authoring; not specified by the mock |
| Ribbon surface | Translucent sheet/filament bundles with fine longitudinal luminous lines, bright edges, local bright dots and visible darkness between lines | Model a body, defined antialiased edges and coherent internal strands; a blurred tube or plain sine line cannot match | Some fine lines may be separate filaments rather than a surface pattern; start with one strip plus material structure |
| Colour | Cyan through electric blue and violet into magenta, associated with different visible bands | Keep colour identity stable through low/high and use authored band colouring | The label permits colour shift, but not unconstrained rainbow cycling; precise mapping remains authored |
| Environment | Dark blue/black interior, repeated vertical bars/columns, localized cyan/violet/white light, little upper-field clutter | Retained world-space simple geometry and emissive light strips; no need to invent a volume simulation | Dimensions, depth and material roughness cannot be recovered uniquely from one board |
| Floor | Large textured reflective foreground; coloured reflections stretch toward the camera and are broken/softened by surface detail | A real plane, view-correct reflection and bounded roughness/normal detail are essential to the final target | Surface appears wet/rough; no visible evidence requires animated fluid, puddle simulation or rain |
| Transparency | Crossings remain luminous with strands readable through each other; high regions approach white locally but do not erase the whole scene | OIT body and separate emission accounting; compare crossings with bloom disabled first | The mock is an artistic target, not proof of physically correct transmission or exact OIT weights |
| Depth / focus | Foreground reflection detail softens; background lights are soft; ribbons hold clear internal detail | Use focus deliberately and only after geometry/material match | Still images do not distinguish lens blur, rough reflection and bloom; do not blur all three indiscriminately |
| Sparks | Small secondary blue/purple points around the ribbons, much more numerous in high | Sparse bounded high/transient accents; preserve relative size and local attachment | Lifetime, trails, gravity and emission rules are unspecified |

The primary's printed suggested frequency ranges (20–200 Hz, 200 Hz–4 kHz, 4–20 kHz) express band intent.
They are not permission to fork the shared analysis or change existing bands for every mode. Audit available canonical
band/spectrum semantics first; record any mapping discrepancy and expose only a justified mode-local mapping.

### 1.3 Initial measurement cards and ROIs

Use native source pixels with top-left origin and right/bottom-exclusive boxes. Provisional panel crops from the
1672 × 941 primary board are low `(0, 108, 640, 817)` and high `(651, 108, 1289, 817)`.
These are approximately 640 × 709 and 638 × 709, **not 16:9**. Do not squash either panel to a full 1672 × 941 viewport.
The overall board includes headings, annotation boxes and a side legend, which are not scene pixels. Confirm exact
crop boundaries at reference lock, retain separate masks for text/arrows, and preserve unmodified originals.

Record measurements in coordinates normalized within each scene crop, with native-pixel values alongside them:

| ROI/card | Initial source-pixel guide | Required comparison |
| --- | --- | --- |
| Composition | Entire panel, excluding annotations | Floor/horizon height, negative-space area, overall ribbon envelope, edge crossings and projected light positions |
| Low body and crossing | Low `(90, 375, 445, 535)` | Visible sheet width versus envelope amplitude; cyan/violet separation; contour and line spacing; absence of muddy opacity |
| High crest / strands | High `(850, 280, 1030, 450)` | Crest silhouette, line continuity, curvature, local bright core and preserved dark gaps |
| High overlap / trough | High `(965, 440, 1190, 590)` | Depth and hue separation, layered emission, white clipping and transparency; mask any callout overlap |
| Reflective floor | Low `(15, 585, 625, 805)`; high `(665, 610, 1270, 805)` | Coloured reflection registration, near/far roughness, footprint width, dark material between reflected lights; mask high callout |
| Environment | Text-free strips above the ribbon and around the vertical lights | Background luminance and gradient, light width/position, floor contact; exclude particles when measuring background |
| Accent points | Text-free high regions above/along the ribbon | Point size distribution, density, clustering and light contribution relative to ribbon |

Boxes are planning guides, not certified segmentation masks or acceptance tolerances. Before judging a candidate,
measure the originals and lock a small target table: projected body-width bands, path extrema at sampled horizontal
positions, envelope area, floor height, light locations, regional median/low-percentile colour, bright/clipped area,
reflection extent and point-size bands. Separate body width from wave amplitude. Label subjective estimates and
occluded regions. Set tolerances from the visible differences and operator review **before** tuning to a candidate;
do not invent numbers here or relax thresholds after a failure.

## 2. Architecture boundary: reuse, promote, add

Read [Visualizer Labs](../Guides/Visualizer_Labs.md),
[Scene3D Resources](Scene3D_Resources.md), [3D foundation lessons](Transitions.md#3d-foundation-lessons-binding),
[Visualizer Presentation](../Guardrails/Visualizer_Presentation.md),
[Reactivity Authoring](../Guides/Visualizer_Reactivity_Authoring.md),
[Visual Tuning](../Guides/Visualizer_Visual_Tuning.md) and
[Bubble Temporal Fidelity](../Guardrails/Bubble_Temporal_Fidelity.md) at each affected boundary.

| Need | Exact current owner | Available now versus work still needed |
| --- | --- | --- |
| Offscreen context, final diagnostic framebuffer, readback | `tools/labs/render_target.py:OffscreenRenderTarget`; bootstrap in `rendering/quick/bootstrap.py` | Available: validated GL 4.6, explicit current-context scope, raw RGBA readback, resize/retirement. Does not own scene HDR/OIT/MSAA targets, camera, simulation or renderer scheduling |
| Static meshes/programs and gradual warm-up | `rendering/quick/scene3d/resources.py:MeshResources`, `warm_programs`; `frame.py:SceneFrame` | Available. Use retained plane/column meshes and shared frame contract. The authored hall arrangement/material is mode-specific; do not build a scene editor for it |
| Streaming control history | `rendering/quick/scene3d/stream.py:StreamRing`; `rendering/gl_programs/scene3d.py:Scene3DStorageLayout` | Available transport/layout with explicit capacity and fences. Must size payload/hold capacity for ribbon records; defaults are not a promise that the history fits |
| Ribbon precedent | `widgets/spotify_visualizer/extruded_bubble_wake.py:WakeField`; `_WAKE_PATH_GLSL`, `TRAIL_VERTEX`, `TRAIL_FRAGMENT` in `rendering/gl_programs/extruded_bubble_program.py`; `rendering/quick/visualizer/implementations/extruded_bubble.py` | S3D-1 promotion is required. Existing records, radius/root fade, water entrainment, near-shell handling and shaders are EB-specific; no ready generic oriented ribbon exists |
| Transparent/emissive scene, resolve, bloom and HDR | `rendering/quick/scene3d/target.py:SceneTarget`; `rendering/gl_programs/scene3d.py:SCENE_OIT_GLSL`; shared post resources in `scene3d/post.py` | Available opt-in substrate. Consumer must prove material/emission/depth ordering, bright overlap, AA, card alpha and no double tone mapping |
| Reflection | `rendering/quick/scene3d/probe.py:SceneProbe`; `environment.py:PhotoEnvironment`; shared reflection helpers in `rendering/gl_programs/scene3d.py` | Cubemap capture/filtering and photo-derived environment are available. Neither establishes a camera-correct reflected ribbon on a nearby floor. S3D-5 needs an independent plane/reflection proof |
| Defocus | `rendering/quick/scene3d/defocus.py:DefocusLayer`; shared `SCENE_DEFOCUS_GLSL` | Available near-light layer. It is not a general floor roughness filter or proof that a long strip crossing focus depths is correct. Optional consumer integration only after targeted cards |
| Particles | `rendering/quick/scene3d/particles.py`, `population.py:CompactedPopulation`; `rendering/gl_programs/particle_program.py`; `scene3d/compute.py` | Sprite/streak draw helpers and stable compacted population exist. S3D-2 owns missing bounded emitters/lifetimes/transient bursts. Small accents do not automatically justify compaction or compute |
| Physical framed camera | `core/settings/framed_camera.py:FramedCameraSpec`; `core/settings/visualizer_view_orbit.py`; projection helpers in `rendering/gl_programs/scene3d.py` | Available shared physical eye/admission. Declare pivot, eye bounds/floor, projection, Orthographic half-extents, optional Perspective FOV and reset pose when admitted. No copied camera controller or music-driven framing |
| Audio and simulation | `widgets/spotify_visualizer/beat_engine.py`, `audio_worker.py`, `logical_runtime.py:VisualizerLogicalRuntime`, `runtime_controller.py:VisualizerRuntimeController` | Shared analysis and sole clock exist. Mode-local control/history evolution must use admitted active-mode hook/frame runtime and immutable publication; no new capture, FFT worker, timer or render-side integration |
| Product registration, settings and presentation | `core/settings/visualizer_mode_registry.py`; `visualizer_mode_settings.py`; `visualizer_settings_snapshot.py`; `rendering/quick/visualizer/implementation_registry.py`, `render_host.py:QuickVisualizerRenderHost`, `node.py`, `item.py` | Integrate only after the lab. Descriptor is canonical wiring; defaults remain with current settings owners. Host owns lazy resolve, identity checks, state restoration and renderer retirement |

**Do not confuse a precedent with the recommended new implementation.** EB's renderer currently uploads its small
fixed instance/wake arrays with `glNamedBufferSubData`; the shared S14 guidance prefers the existing persistent ring
for new changing payloads. Decide the new strip transport at S3D-1 from bounded data size and measured calls. Do not
copy the private EB uploader, add another generic uploader, or quietly refactor EB as collateral work.

The reusable S3D-1 boundary should accept bounded control/history records, stable identity, continuous sample/path
coordinate, width/orientation inputs and material coordinates. It must not know music bands, hall layout, palette,
presets, bubble radii, water entrainment or emitter taste. Keep musical mapping, centerline recipe, colour assignment,
floor/light arrangement, selected fixture states and artistic particle placement mode-specific. Share shader geometry
and resource ownership between lab and eventual production; do not preserve a separately tuned shader fork.

## 3. Dependency order and admission checkpoints

```text
Current_Plan admission + reference custody / approved primary target
    -> S3D-1 independent strip/history/orientation/OIT/defocus harness
    -> Waveform Ribbon single-strip composition and low/high lab proof
    -> single-strip production admission (only when §7 admits production)

S3D-5 independent reflection harness -> floor in lab -> floor in production
S3D-1 bounded multi-strip proof      -> multi-strip lab -> multi-strip production
S3D-2 independent emitter proof      -> accents in lab -> accents in production
    -> restrained Settings / presets -> mock | lab | production -> native/operator A–H
```

This is a dependency graph, not permission to skip Current_Plan's S3D order. §6 owns when S3D-2 through S3D-5 are
admitted; if S3D-3/4 precede S3D-5 there, this mode does not reorder them. Each shared primitive earns its own offscreen
proof before consumer integration. An unfinished S3D-5 blocks the floor slice, not independent ribbon geometry work.
S3D-3 may supply useful retained material helpers, but the simple hall does not justify an authoring system. S3D-4
fluid, S3D-6 shadow maps and S3D-7 lightning/volumes are not visual prerequisites established by these images.

The final target visibly needs reflection, layered bands and points. A successful one-ribbon/no-floor study is only an
intermediate gate, not a claim to match the full board. Before each production feature is added, bring that feature's
lab recipe to the mock; then port in §7.1's order: single ribbon/material/bloom → floor → multi-ribbon → accents →
restrained Settings. Do not wait until the final Settings stage to discover that the camera or materials differ.

## 4. Work packages and required artifacts

Artifact names below are proposed output roles, not tools/files that already exist. Store bounded run output under
an explicit `tmp/waveform_ribbon/<run-id>/` path (or the operator's chosen evidence directory). A small manifest must
identify every artifact. Never overwrite old evidence to make the latest attempt appear to have always passed.

### WR-00 — Lock the reference and reproducible comparison contract

**Entry:** mode planning or implementation is admitted; original package is available.

- [x] Recheck archive members/hash and the approved primary board. Preserve its authority unless a later operator
  instruction changes it; keep independent target tables for any explicitly admitted future alternate.
- [ ] Confirm scene crop boxes, annotation masks and source aspect. Extract measurement cards without modifying originals.
- [ ] Measure the target table from §1.3; mark ambiguous body counts and occluded features rather than inventing geometry.
- [ ] Define a stable camera/world/palette fixture and a separate delivery-aspect fixture (normal runtime card/wide view).
  Match the portrait-like panel crop first; derive wider framing with preserved scale/proportions, not image stretching.
- [ ] Record source revision/dirty diff, GL/Qt/driver, image hashes, viewport/DPR, colour conversion and composite backdrop.
- [ ] Inventory recorded-audio clips and whether each includes replayable waveform/analysis. Select quiet, transition,
  strong bass, mids/vocals, high percussion, saturated chorus, pause/resume and hot activation windows by listening and traces.

**Exit/artifacts:** reference manifest, crop/mask definitions, annotated measurements, explicit occluded/unspecified
details, clip identities/time ranges and proposed tolerances. Unspecified details do not block independent primitive
work; final likeness still needs the actual candidate's visual evidence.

### WR-01 — S3D-1 pure path/history contract before scene polish

**Entry:** S3D-1 admitted; exact EB wake source and regression bars reread.

**WR-01a landed:** `core/ribbon_geometry.py` plus `tools/labs/ribbon_path_probe.py` implement the bounded CPU
reference documented in `Docs/Reference/Ribbon_Path.md`. Four-knot-supported interior positions preserve absolute
coordinates through insertion/eviction; batch partition invariance applies to identical admitted knots only.
CPU cards/trace: `.artifacts/evidence/waveform_ribbon/wr01a_history_checked/receipt.json`. No EB code changed.
WR-01b adds `core/ribbon_frames.py` and the CPU frame probe. Its singularity policies, station/UV contract and
proposed GPU budget are in `Docs/Reference/Ribbon_Path.md`. CPU receipt: `.artifacts/evidence/waveform_ribbon/wr01b_frames_checked/receipt.json`.
The broader checkboxes below stay open where actual derivatives, GPU topology/packing or native temporal proof is incomplete.


- [ ] Specify fixed maximum ribbons, history samples, active counts, sample spacing/time interpretation, record bytes,
  topology and reset/retirement semantics. Calculate memory and worst-case vertices from these caps before allocation.
- [x] Define one caller-owned absolute longitudinal coordinate that survives insertion and history eviction.
  Identical admitted knots must be invariant under submission batch partitions; arbitrary dt resampling stays open. Use it
  for geometry, internal strands and attached accents; never derive placement from the changing share of segment count.
- [x] Promote the minimal centripetal Catmull-Rom evaluation with repeated-point/short-history handling. Preserve EB's
  existing arithmetic/call path unless an explicitly scoped migration proves unchanged output and temporal behavior.
- [x] Design camera-facing and oriented width modes. For a twisting sheet use a transported frame (or an equally
  continuous proven basis), then apply authored twist. A Frenet frame at zero curvature or a cross product parallel to
  the viewing ray needs deterministic continuous degeneracy handling; silent flips are unacceptable.
- [ ] Define normals/tangents, two-sided material behavior, UV/path coordinates, edge coverage and end treatment.
  Width changes must remain positive and continuous; initial empty/one-point history must not produce NaNs or full-length pops.
- [x] Decide whether the history represents waveform/control age or spatial path distance. EB's water physics is not
  the model for music flowing across a hall; reuse its coordinate lesson, not its entrainment/drag constants.
- [ ] Exercise stationary, straight, unequal-spacing, cusp-like, repeated-point, reversing, growing and saturated-history
  fixtures. Track marked sample/strand positions before/after insert/evict. Compare submission partitions for identical admitted knots. Independently resolve any future variable-dt resampler
  before claiming equivalent nonlinear trajectories.

**Exit/artifacts:** small pure record/layout contract, bounded CPU reference and path cards/trace with finite positions,
no unexplained discontinuity, persistent identity and fixed capacity. Focused tests must falsify normalized-segment
placement, frame flips and capacity overflow; visual review still owns what a desirable waveform looks like.

### WR-02 — S3D-1 GPU primitive proof in its own harness

**Entry:** WR-01 contracts defined; no Waveform mode registration required.

**WR-02a implemented:** `core/ribbon_packet.py`, shared shader/primitive modules named `ribbon.py`, and
`tools/labs/ribbon_strip_probe.py`; detailed ABI/proof/cost limits live in `Docs/Reference/Ribbon_Path.md`.
Native receipt `.artifacts/evidence/waveform_ribbon/wr02a_native_final/receipt.json` measures cheap geometry draws
but a 90 ms maximum full CPU input rebuild. Incremental input construction is the next required gate before any
production use; neither this prototype nor the remaining checkboxes imply a whole-mode performance/fidelity pass.


- [x] Place reusable GPU resource/geometry owner in `rendering/quick/scene3d/` and import-safe shader helpers in
  `rendering/gl_programs/`; use an independently named primitive harness under `tools/labs/` with `OffscreenRenderTarget`.
- [ ] Start with bounded history SSBO + vertex-stage strip expansion through shared storage/ring facilities. Keep CPU
  state evolution batched. Benchmark a compute alternative only if it removes demonstrated work; no compute-first assumption.
- [ ] Declare storage binding ownership, alignment, stride, hold size, fence use and draw count. Exercise the maximum
  payload, not only one short ribbon that happens to fit defaults. No per-frame reallocation or GPU live-count readback.
- [ ] Draw one sharp strip with no bloom, then oriented twist, then multiple crossing strips through shared OIT.
  Include front/back, edge-on, highly foreshortened, near-plane, offscreen and small-card fixtures.
- [ ] Prove opposite draw orders, opaque plane occlusion and bright HDR overlaps at supported sample counts.
  Test shader finiteness and accumulation overflow at the admitted maximum width/count/emission.
- [ ] Add a defocus card only where S3D-1 requires it: focus plane crossing along a long strip, tiny bright strands with
  large blur, mixed CoCs, centering/energy and continuity. A single flat blur value per strip is insufficient if depth varies.
- [ ] Record framebuffer/viewport/scissor, blend indices/masks, depth/cull state, textures/storage/image bindings and
  foreign-context sentinels before/after success and thrown draws. Test partial admission and retryable retirement.
- [ ] Measure warm whole/pass cost, call counts and owned bytes using §7; attach independent primitive evidence before consumers.

**Exit/artifacts:** primitive cards/clips, bounded layout/cost report, focused geometry/GPU/lifecycle results and explicit
limits. Passing a shader readback does not close G, H or musical acceptance. Defocus unresolved means the focus feature
is held, not substituted with unbounded bloom.

### WR-03 — Camera and scene blockout with one ribbon

**Entry:** S3D-1 proof admitted; WR-00 primary-target measurements exist.

- [ ] Create `tools/labs/waveform_ribbon_lab.py` as a scene-input authoring tool over shared primitives, with explicit CLI
  paths/seed/time/size/recipe and no Settings or preset writes. Do not invent a universal lab recipe schema.
- [ ] Use first-allocation `try/finally`/`ExitStack`; retire scene resources inside `with target.current():` before closing
  the diagnostic context. Capture errors invalidate the preview; no stale image displayed as a successful new render.
- [ ] Place a finite floor, simple world-space vertical structures/light strips, and one continuous ribbon. Start with
  neutral opaque/flat diagnostic shading; no particles, bloom, lens blur or reflection to conceal shape differences.
- [ ] Solve Orthographic eye/pivot/half-extents and scale against floor boundaries, ribbon extrema and light positions;
  validate optional Perspective separately. Record the
  effective physical camera values. Use the shared framed-camera math; outer card resizing is not world scaling.
- [ ] Match both ends extending beyond the image with sufficient offscreen continuation. Do not hide end caps at one
  pose only; test a small camera move. Keep the world fixed under navigation.
- [ ] Freeze camera, environment, floor geometry, static lights, palette, seed, base path and topology for the low/high
  pair. Permit only declared reactive body/deformation/emission/detail inputs to differ.
- [ ] Capture native-resolution target/flat-lab sheets plus projected landmark table. Evaluate wide/narrow cards
  separately for cropping, minimum readable strand sizes and background/floor balance.

**Exit/artifacts:** same-scene flat low/high cards, world/camera recipe and scale/proportion deltas. Advance only when
the simple body and composition are credible; a visually wrong silhouette must not receive another glow pass.

### WR-04 — Ribbon material, internal structure and controlled light

**Entry:** WR-03 geometry/composition accepted as an intermediate.

- [ ] Add faint translucent body, defined rims and longitudinal fine structure in distinct diagnostic contributions.
  Keep all patterns on the shared path coordinate. Verify seam-free interpolation through joins and changing history.
- [ ] Choose oriented thin sheets first for visible twist; compare camera-facing strips as a diagnostic control. Add
  real thickness only if a reviewed side view requires it; apparent brightness is not evidence of volumetric thickness.
- [ ] Author cyan/blue/violet/magenta bands from one scene palette and consistent light sources. Keep material emission,
  illumination, alpha coverage and bloom weight separately inspectable; do not use alpha as an arbitrary brightness knob.
- [ ] Resolve overlap using `SceneTarget.transparent_writes` and shared OIT. OIT is approximate; preserve front/back
  legibility with correct geometry/material and report remaining dense-layer errors rather than promising exact sorting.
- [ ] Establish HDR exposure once for the scene, then add emission-only bloom. No automatic exposure change between low/high.
  Show bloom-off and emission-only cards; measure clipping and dark gaps at crossings before calling glow successful.
- [ ] Evaluate line/point coverage at native pixel sizes, multiple subpixel offsets and small runtime cards. Avoid patterns
  that look detailed only at a static phase but sparkle or crawl under slow motion. Lower unresolved detail coherently.
- [ ] Make background light softness independent from ribbon edges. Hold defocus off until crisp material passes; only
  then compare restrained shared defocus with the no-defocus control and the reference's actual depth cues.

**Exit/artifacts:** contribution/ablation cards, low/high material sheet, ROI measurements and short slow-motion sequence.
G remains open if crossings wash out, thin strands flicker, colour changes identity, or a smooth surface requires blur
to hide segmented geometry. This stage may match one band's character; it is not full multi-band fidelity.

### WR-05 — S3D-5 floor reflection proof, then scene integration

**Entry:** S3D-5 admitted in Current_Plan; independent reflection harness before the consumer.

- [ ] Define plane, reflector bounds, reflected eye/projection, clip convention, culling handedness, colour space and
  inclusion list. Use the same scene geometry/time/material functions; exclude the receiver/self-recursive reflection.
- [ ] Prefer a bounded planar reflected scene for a nearby flat floor. Compare a local probe only with explicit parallax
  limits; a cube at one origin is not automatically accurate across a wide near floor. Make the choice from moving-camera cards.
- [ ] Prove floor-to-object registration with an asymmetric coloured object/light fixture at known positions; translate
  and orbit the physical eye. Check reflected high/low changes use the exact same logical snapshot, without one-frame lag.
- [ ] Add bounded roughness/filtering, world-space material scale, normal detail and distance-dependent appearance.
  First match the reflection footprint, then floor texture. Do not use screen Y or a painted glow patch as reflected geometry.
- [ ] State pass count, target resolution/sample count, memory, scene inclusion, update invalidation and Off behavior.
  Static environment reuse must be dependency-correct; reacting ribbons cannot use a stale reflection on a separate clock.
- [ ] Prove target resize, partial failure, interleaved contexts, state restoration and full retirement independently.
  Measure a skip-reflection control to identify real cost and a deliberately wrong mirrored-camera control to validate the image bar.
- [ ] Integrate with Waveform's same-scene floor; compare low/high foreground ROI, elongated coloured reflections,
  texture dark gaps and horizon/contact. Restrained floor detail must remain stable while reflected ribbon light reacts.

**Exit/artifacts:** S3D-5 geometric/reflection cards and measured cost, moving-camera sequence, Waveform floor ROI sheet.
No full-scene fidelity sign-off if the floor is absent, screen-locked or plausible only from one pose. A flat wet-looking
floor does not require a liquid simulation; ripples/distortion are opt-in only if the selected target demands them.

### WR-06 — Bounded multiple ribbons and S3D-2 accents

**Entry:** single-ribbon/material proof, S3D-1 multi-strip proof, and S3D-2 emitter proof before particles.

- [ ] Separate a small authored set of bands with stable IDs, depth offsets, phase relationships and colour family.
  Infer count from the selected image by tracing complete bodies; do not count every internal strand as a separate mesh.
- [ ] Keep count/topology constant across the reference low/high pair. High react changes width and energy; it does not
  spawn an unrelated scene. If an explicit count setting is later admitted, validate its bounded transition separately.
- [ ] Compare multi-band overlap with simple opposing colours, bloom disabled and reversed draw order; then restore palette.
- [ ] For S3D-2, independently prove bounded birth/death, deterministic slot/ID reuse, consume-once event bursts and off
  retirement. Inventory `CompactedPopulation` and sprite/streak helpers before adding machinery; measure analytic instancing
  against compaction for this small pool, with no dual production fallback path.
- [ ] Attach births to selected ribbon path positions/local motion and allow short authored departures; use the same path
  coordinate as the surface. Do not let a global music direction detach points from the path they came from.
- [ ] Set point-size bands and total bright contribution from the mock. High-frequency evidence controls accents;
  absolute loudness must not fill the maximum pool continuously. Particle Off must allocate/draw/advance nothing.
- [ ] Capture accents-off, isolated-accent and full-scene low/high clips and ROI sheets. Preserve ribbon identity and
  visibility of fine strands even in a sustained hot chorus.

**Exit/artifacts:** count/capacity and event audit, point-size/density measurements, bounded worst-overlap capture,
cost ablations and same-scene comparison. A particle storm is a target failure even if within the numeric cap.

### WR-07 — Real musical evolution in the lab

**Entry:** readable single-ribbon lab; later repeat after floor/bands/accents. Use §5 signal contract.

- [ ] Replay the existing recorded audio/analysis path into explicit logical times; use shared analysis, not hand-authored
  oscillators as musical proof. Synthetic inputs remain useful labelled isolation fixtures.
- [ ] Audit quiet/middle/loud windows by sustained intensity and listen to them; record exact clip/time/generation.
  Trace signal → mapped control → state → projected width/curvature/light/particle event for each band.
- [ ] Run warm sustained-hot versus first-input-hot activation, silence-to-music, pause/resume, end/start and rapid preset
  replacement. Reject history reseeding overshoot, stale events, full-width first frame or a dormant mode's retained tail.
- [ ] Compare identical dt-integrated states at different render rates; frames may consume latest state but must not
  append history or integrate simulation. Include irregular publication/render timing with visible-edge survival checks.
- [ ] Prove broad low/high scene identity while retaining beat-by-beat contrast inside high passages. Do not tune only
  isolated quiet/loud stills; inspect uninterrupted music-aligned native-resolution output and real-time playback.
- [ ] Record perceptible response and attack/settle traces; test candidate smoothing against an unsmoothed control.
  Fix delivery gaps at their owner, never with a private interpolator/clock or reduced musical attack.

**Exit/artifacts:** synchronized replay clips/frames, signal and realization traces, passage table, hot-start and
stale-event controls. Operator listening/visual review closes F/H; automated correlation alone cannot do so.

### WR-08 — Production port and settings, only after lab admission

**Entry:** relevant feature's lab target and shared primitive gates accepted; Current_Plan §7 admits product work.

- [ ] Add the mode through canonical descriptor/implementation wiring with the correct framed scene capability and
  lazy imports. Resolve only the active logical hook/frame runtime; no unconditional per-mode work in common ticks.
- [ ] Define typed logical state and render snapshot, generation fences, warm/reveal requirements and inactive disposal.
  Use `VisualizerLogicalRuntime` dt and `QuickVisualizerRenderHost` resource ownership. Request history/audio demands
  only while needed; release demand on replacement and retirement.
- [ ] Port feature slices in §7.1 order. Use shared geometry/shaders; diff lab effective inputs against product inputs
  key by key: admitted eye/pivot, projection/half-extents and optional FOV, world scale, target allocation, quality, HDR/exposure, material, depth, history,
  palette, signal scales and warm-up. Fix mappings rather than retuning a second look.
- [ ] Use test-owned fixture configs for exact lab/product comparisons. Production captures may read the operator's
  current presets, with read-only run-local snapshots, but never pin their contents as tests or overwrite them as setup.
- [ ] Add minimal settings at the existing typed/default/declaration owners. Validate actual useful count/width/twist,
  glow/reflection, accent and sensitivity ranges; do not blindly expose every lab diagnostic knob. Defaults have one owner.
- [ ] Verify Save/Cancel/Restore, independent CUSTOM, preset identity and hot swaps through real activation. Keep camera
  view semantics with shared framed-camera/preset starting-view authorities; no hidden per-preset camera override.
- [ ] Check each option's Off path for no shader/resource/work cost and capture unchanged accepted modes with independent
  fixture inputs. Shared target or shader changes require the affected shared baseline, not only Waveform tests.
- [ ] Build mock | lab | production sheets at matching projection/time/size for low/high and critical ROIs, then run
  production through recorded music. Small exact arithmetic differences require explanation; visual gaps remain open.

**Exit/artifacts:** input parity report, production-host captures, focused settings/clock/dormancy/lifecycle results,
regression control captures and documented remaining native gates. Presets remain freely operator-authored.

### WR-09 — Native acceptance and closure

**Entry:** production and offscreen parity gates pass; complete evidence manifest exists.

- [ ] Observe the real retained Quick scene on the target Windows/driver/display setup with music. Capture native pixels
  and motion plus frame traces/logs; record resolution, refresh, DPR, active preset snapshot, settings and source timing.
- [ ] Exercise card resize/clip, small/large/wide/narrow shapes, relevant DPR/display transfer, camera reset/navigation,
  pause/resume, repeated mode changes and Settings reopen. The outer card and fixed world must retain their identities.
- [ ] Check startup/prepared reveal, first useful frame, retirement, display removal/context invalidation and replacement.
  Retire under the legal GL context on its owner thread; failed releases remain accounted and retryable.
- [ ] Observe Bubble active-music temporal fidelity and accepted baseline modes if shared owners changed. Do not trade
  their cadence, response or pixels for Waveform headroom. Frozen builds/installed validation stay operator-executed.
- [ ] Present target/candidate ROIs and uninterrupted music sequences for operator A–H sign-off. Record each gate's
  evidence and decision separately. Leave Awaiting Validation/Logs with the precise missing action in Current_Plan.

**Exit/artifacts:** native run receipt, gate matrix, operator decision and scoped remaining defects. Completion needs
the mock-directed visual result, not merely matching a lab that missed the target.

## 5. Low/high reactivity contract

Two complementary comparisons are required:

1. **Artistic control pair:** identical scene/seed/base path/camera/material family at identical explicit time, with
   declared low/high control inputs. This isolates the picture and catches camera/palette/composition substitution.
2. **Musical pair and sequence:** quiet and energetic windows from the **same recorded source**, identical scene recipe
   and production signal mapping, with continuous pre-roll/history. Windows differ in time, so geometry need not be
   pixel-identical; static camera/environment signatures must be identical. Include more than one music character.

| Job | Candidate canonical evidence / mode-local response | Required falsifier |
| --- | --- | --- |
| Presence/silence | Current support/presence from shared BeatEngine; no fresh musical events during silence | Pause cannot emit new bursts or replay the last event; intentional low idle drift remains distinguishable from music |
| Sustained energy | Shared musical level/passage semantics, bounded glow/body baseline | Saturated chorus must retain local contrast; no track-learning normalization that fades the chorus or resets on hotswap |
| Bass | Current band articulation plus supported bass events → body width/large slow bend | Bass-only fixture visibly changes width, not camera/FOV; maxima remain reachable but not permanently pinned |
| Mids | Current mid structure/contrast → twist and centerline deformation | Mid-only fixture changes twist/shape without exploding width or randomizing phase; no frame flips at zero curvature |
| Highs | Current high evidence → edge shimmer and restrained points | High-only fixture does not move the whole scene; no sustained particle maximum from absolute loudness |
| Transients | Typed consume-once event identity and measured local contrast → localized short accent | Repeated latest snapshot cannot re-emit; old activation generation cannot publish into the new mode |
| Flow/history | Explicit logical-time advance with bounded waveform/control history | Changing physical presentation FPS cannot change path speed, point count over time or particle lifetimes |

`BeatEngine.get_waveform()` exposes only the latest 256 samples; its waveform-history demand and raw pre-AGC spectrum
are separate capabilities. First decide whether the visual needs a short band/control history, raw waveform detail,
or both. Never treat 256 instantaneous samples as a long travel history or a flattened synthetic sine as actual PCM
proof. Demand any required waveform history through the existing owner (`set_waveform_history_demand`), inspect valid
sample count/generation, and keep the visual history bounded under the logical mode. No second audio recorder or FFT.

The picture's smooth large waves do not establish that raw sample frequency should directly become full-amplitude
geometry. Compare a bounded band-shaped centerline with waveform-derived fine structure. Preserve causal attacks and
local contrast; document the chosen response curve and limits with recordings. Idle may maintain a gently flowing
composed ribbon, but must not counterfeit transient bursts. Whole-scene exposure and camera stay fixed throughout.

## 6. A–H hard gate matrix and negative controls

| Brief gate | Proof required | Deliberate control that must fail / inadequate substitute |
| --- | --- | --- |
| A — Same-scene low/high | Static scene signature, matched camera/world recipe, paired full frames and landmark measurements, continuous recorded-music sequence | Change FOV/environment/seed between states: signature rejects it. Two separately beautiful stills do not pass |
| B — No second renderer | Owner trace from descriptor to production host and shared Scene3D resources; lab imports same primitives/programs | A separate lab-only shader path or copied context/renderer makes parity unproven; screenshot similarity alone does not pass |
| C — One clock | Explicit-time lab state, logical-runtime integration, render-rate variation and generation/event tests | Frame-count-based speed or render-side history append must diverge in the control; ordinary stable-FPS playback is insufficient |
| D — Dormancy/cleanup | Zero inactive simulation/query/draw/consumer resources, lazy imports, repeated replacement, context-safe retryable release and native context invalidation | Retain one ribbon buffer or an inactive audio/history query in a local falsifier: ownership bar catches it. `has_resources=False` alone is not enough |
| E — Bounded cost | Declared caps, max-overlap/viewport workload, bytes/GL calls, warm GPU median/p90, CPU submit and native frame/freshness tails | Cap overflow fails loudly; unbounded history cannot pass a short capture. Average FPS cannot hide latency or allocation spikes |
| F — Music legibility | Band-isolation cards plus real music and operator review of bass/body, mid/twist, high/detail; saturated chorus and attack/settle traces | Feed one energy scalar to every control as a diagnostic negative control: separability audit exposes it. Correlated RGB alone is not musical proof |
| G — Transparency | Opposite-order crossings, opaque-depth fixture, HDR/near-plane stress, native moving overlaps and critical ROIs | Ordinary order-dependent blend, over-bloom or excessive opacity must fail the appropriate card. OIT unit tests do not certify this material |
| H — Attractive low react | Quiet/silence cards and uninterrupted quiet passages with composed body, restrained light, depth and readable floor | Zero/minuscule width or glow-only body is visibly rejected. A bright high-react hero still cannot close H |

Use controls to validate the measurement, not as retained runtime fallback branches. Remove disposable bad variants
after evidence is captured. Exact pixel identity is appropriate for unchanged renderer behavior on **test-owned** inputs;
photorealistic mock likeness needs landmark/ROI comparisons and operator judgement. No single global pixel score should
reward a blurred average image while missing the ribbon structure. Review both full composition and native-pixel crops.

## 7. Cost, dormancy and lifetime evidence

No timing budget is fabricated here. At implementation admission record target hardware/display/quality and agree the
budget from measured controls and required fidelity. Existing EB/transition measurements are context, not a Waveform SLA.

- [ ] Derive vertex/draw bounds from maximum ribbons × samples/subdivision × strip sides; derive history/stream bytes,
  particle capacity and all reflection/HDR/OIT/bloom/defocus attachments from admitted viewport/sample tiers. Include
  bucket overhead and transient replacement peak memory at resize. Report formulas and effective values.
- [ ] Benchmark after warm-up with at least 90 warm frames per foundation guidance; report GPU `GL_TIME_ELAPSED`
  median/p90 and CPU submit separately, with flush-per-frame, production-comparable GL error policy and explicit workload.
  Whole-frame and leaf queries run separately, never nested. Do not trust timestamp deltas across Python submission gaps.
- [ ] Alternate comparable variants on the same machine/process when feasible; use remove-pass controls for body,
  strands, OIT, reflection, bloom and accents. Record shader/target counts and per-frame GL calls, not only a total GPU time.
- [ ] Cover reference aspect, intended wide delivery aspect, minimum card, large viewport, low/high, max capacity, dense
  crossings, near-plane and feature-Off. High-react overdraw can dominate even with a small fixed vertex count.
- [ ] Observe shader/resource creation at bounded hidden warm-up, no first-visible-frame compile burst, no allocation or
  respecification in steady draw, and no inactive per-frame imports, FFT/history queries, simulation or preparation.
- [ ] Separate logical/GUI/render timing and freshness from GPU drain. If CPU batches hold the GIL, a cheap-looking
  simulation tick can still starve the GUI. Check loaded-desktop traces and BTF when shared pathways are affected.
- [ ] Resize one owner at a time: diagnostic output target, scene target, reflection/defocus and camera projection.
  The diagnostic target's successful resize does not prove scene resources follow; failed allocation must be loud,
  preserve valid owned state for cleanup and never return a stale successful-looking preview.
- [ ] Exercise two interleaved legal contexts, unsupported context admission, first/mid allocation failure, draw throw,
  close twice, release failure/retry and context invalidation. Consumer resources retire before diagnostic target close;
  production retirement stays with the host/node/item and its legal render context, not a destructor or accounting utility.
- [ ] Launch future automated GL/native probes under an external whole-process-tree deadline using the existing
  `tools.build_runner.BuildProcessOwner` Windows Job owner, as required by Visualizer Labs. This is probe ownership,
  not permission to run product builds. Use explicit CLI/sidecar inputs, never environment-variable setup.

Existing focused bars to extend/reuse according to the changed seam include `tests/test_lab_render_target.py`,
`test_extruded_bubble_wake_contract.py`, `test_scene3d_stream.py`, `test_scene3d_target.py`, `test_scene3d_probe.py`,
`test_scene3d_defocus.py`, `test_scene3d_population.py`, `test_visualizer_mode_dormancy.py`,
`test_visualizer_logical_hook_dormancy.py`, `test_visualizer_settings_body_dormancy.py`,
`test_qtquick_visualizer_mode_retirement.py` and `test_visualizer_owner_retirement.py` (all under `tests/`).
Add primitive-specific checks only where existing cases cannot falsify the new contract. Run the smallest meaningful
selection; broaden shared-rendering baseline coverage when shared owners change. No full suite or build is implied.

## 8. Evidence package and false-confidence vetoes

Each reviewed slice must retain:

1. A manifest with code revision/dirty patch identity, reference member/hash, effective recipe, explicit seed/time,
   audio clip hash/time/pre-roll, input generation, viewport/DPR, physical camera, quality, driver/Qt/GL and command.
2. Original-resolution frames, mock | lab (later mock | lab | production) sheets, critical matched ROIs, labelled
   ablations and projected/colour measurements. Any annotation mask and resampling must be explicit.
3. Uninterrupted time sequences with audio alignment, exact playback speed and trace links. Encode previews for
   convenience but preserve raw frames for pixel questions. A slowed preview supports diagnosis, not real-time acceptance.
4. Geometry/control/capacity traces, warm cost distributions and lifetime results with tested selectors and failures.
5. A per-gate decision: pass for the named scope, fail with next falsifier, Awaiting Assets, Awaiting Logs or Awaiting
   Validation. Operator rejection outranks a passing quantitative similarity metric.

Veto claiming full fidelity from: successful shader compilation; FBO readback; logical-only tests; a small downscaled
sheet; one favorable frozen frame; a single quiet song; a single stable camera; a lab fixture with impossible product
values; a fast average FPS; or lab/production agreement when both diverge from the original. Stills are necessary for
shape/material review, native motion and listening are necessary for temporal/musical acceptance, and neither closes
the other's gate.

## 9. Repo-grounded mistakes to avoid

- **Soft veil substituted for structured ribbon:** EB work established that blur cannot create crisp rims and inner
  strands. Inspect the original at full resolution and tune body/edges/structure independently before bloom.
- **Segment-relative history placement:** EB's early beads slid and snapped at insertion. Use continuous index/age
  coordinates; test insertion/eviction while holding marked material points visible.
- **Generic water simulation copied wholesale:** `WakeField` is bubble wake water. Waveform needs musical path history;
  keep EB attachment radius, entrainment, fizz and near-shell fade out of the generic primitive.
- **Per-owner per-tick NumPy resampling:** the visual tuning guide records GIL starvation. Batch bounded work and measure
  GUI freshness as well as the logical tick. Exact current WakeField batches flow every tick; do not copy an older
  cadence as a new independent scheduler.
- **Camera-facing billboard used as twist proof:** it hides orientation and breaks edge-on cues. Test transported frames,
  reversals and near-view-axis tangents before claiming oriented sheet fidelity.
- **NaN/black flecks dismissed as style:** clamp interpolated power bases, guard degenerate tangents and bound OIT weighted
  HDR accumulation. Current shared OIT protects known overflow; the new material still needs max-overlap stress.
- **MRT state assumed from an earlier caller:** masks belong to draw-buffer indices; each layer sets/restores what it owns.
  Test defocus/emission outside the one lucky scope in which a lab happened to work.
- **Probe or screen copy called a floor reflection:** establish parallax, plane registration and handedness under eye
  translation. A static beautiful image cannot validate S3D-5.
- **Timestamp attribution used as optimization proof:** EB lab timestamps included submission gaps. Use non-nested elapsed
  queries and skip-pass ablations; no quality cuts based on mislabeled cost.
- **First-input loudness calibrated as normal music:** compare warmed hot activation and real passages; do not reset
  references to zero and then hide the launch overshoot with additional global smoothing.
- **One scalar drives everything:** preserve distinct admission, sustained weight, continuous articulation and events.
  Canonical raw analysis differs from Spectrum-shaped bars; new mode routing must not alter accepted Bubble/Sphere DSP.
- **Lab-to-product copied values in different spaces:** compare actual camera/projection, world/pixel size, target format,
  control admission and palette values. Fix missing mappings, not hidden overrides or artistic preset clamps.
- **Mutable presets treated as goldens:** create independent fixtures; read operator data without replacing it. Use a
  separate read-only baseline capture or an authorized isolated checkout. Never stash/reset/clean unrelated work.
- **Shared feature pays while Off:** an unconditional HDR uniform once added cost to every 3D mode. Test resource/import/
  GL-call dormancy, not merely zero visible alpha. No permanent fallback renderer or mode-private scheduler.
- **Defocus accepted from one dot:** mixed-size bright elements and long depth-varying strips can expose coverage/energy
  failures invisible in one isolated point card. Preserve point, mixed-CoC and moving-strip controls.

Exact source already provides the shared framed camera; Current_Plan §6 owns new primitives. Reuse the current
camera and resource contracts rather than rebuilding them or reopening already-landed substrate.

## 10. Concrete next start and unresolved decisions

**Next: finish WR-00 and execute WR-02 for S3D-1:** lock primary image crops/measurements, then independently
prove one oriented continuous-history strip with no bloom/particles, followed by overlapping translucent strips and
bounded lifetime/cost. This establishes the highest-risk shared prerequisite before artistic scene composition or Settings.

- [ ] **Awaiting Assets/Validation — reference completeness:** no clean annotation-free scene or reference animation was
  present in the inspected package. Exact hidden pixels, motion direction/speed, topology count and optical model are
  therefore unspecified. Proceed from visible pixels and document authored choices; request additional originals only
  if an actual comparison is blocked. Do not make a generated reference the new goal.
- [ ] **Awaiting execution evidence — musical fixture selection:** select available recorded clips and verify the
  waveform/analysis payload and valid pre-roll at WR-00. This planning pass did not replay or evaluate a clip.
- [ ] **Awaiting architecture proof — S3D-1/S3D-2/S3D-5:** history/oriented strip promotion, emitter extensions and
  view-correct floor reflection are not declared complete by existing helpers or by this document.
- [ ] **Awaiting Validation — tolerances and delivery framing:** confirm target landmark/ROI tolerances, wide-view
  framing and acceptable small-card detail using actual candidate images, before calling resemblance achieved.
- [ ] **Awaiting Logs/Validation — cost and native acceptance:** hardware budgets, warm/native measurements, live musical
  legibility, interaction, context retirement and operator A–H decisions remain future evidence gates.

None of these uncertainties permits replacing the reference scene, freezing presets, weakening BTF, or creating a
second rendering/timing authority. Independent work may proceed through its stated entry/exit criteria; consumer and
visual gates stay open until their actual dependencies and evidence are satisfied.
