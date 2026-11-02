# Waveform Ribbon: lab execution and visual evidence plan

This is the detailed execution/evidence owner for **Waveform Ribbon**, subordinate to
[`Current_Plan.md`](../../Current_Plan.md) §6 (S3D shared prerequisites) and §7.0–7.1 (lab first, then production).
The operator's [concept brief](../Future_Work/Waveform_Ribbon.md) owns intent and hard gates A–H. This document
decomposes those gates; it does not reorder the live plan or declare any visual validation complete. It is a live
checklist: section 0 says where the work stands and what comes next, in order; the WR sections below hold the detail.

Recheck the named source owners before each slice. Keep live sequencing in Current_Plan, detailed work/evidence here,
durable shared contracts at their existing owners (`Ribbon_Path.md` for the S3D-1 primitive), and failed-method
history under the existing Historical Bugs policy. An absent reference or missing native/operator evidence remains an
explicit **Awaiting Assets**, **Awaiting Logs** or **Awaiting Validation** gate, never a green checkbox.

## 0. Live goal and working sequence

**Goal:** deliver a fixed-world framed 3D scene with smooth flowing luminous ribbons over wet reflective concrete,
surrounded by thick shaped mist. The mist hides horizon/sky/floor boundaries, curves around the waveform without
touching it, and is softly lit by the waveform. Pillars and the rejected hall study are not part of the target.

The complete-scene fog board is the primary target. The alternate and preset-range boards define additional looks the
eventual presets/reactivity must be able to reach without changing scene identity. Exact source custody is in §1.1. Root
`references/` is operator-owned/local and intentionally omitted from normal GODZIPs; do not interpret absent image bytes
as deleted requirements.

**Current reusable substrate:** shared framed camera, bounded incremental ribbon history, oriented OIT/HDR ribbon material,
history sparks, planar reflection, generated concrete material maps and the bounded mist prototype. Shared ownership lives
in `Docs/Reference/Ribbon_Path.md`, `Docs/Guides/Visualizer_Labs.md` and `Docs/Reference/Scene3D_Resources.md`; the WR-08
production/control design lives in [Waveform Ribbon Migration Plan](Waveform_Ribbon_Migration_Plan.md). This section tracks
only remaining work, not implementation chronology.

**Working sequence:**

- [~] **Awaiting Validation — recorded motion bake-off:** review the current §5.1 audible four-way packages and select
  a credible motion grammar, request a specific correction, or reject all. Judge distinct flowing/twisting body motion,
  moving colour, dense/local highlights and particles together. Keep geometry-only controls for diagnosis.
- [ ] **After motion selection, timing/framing admission:** extend the fixed-view near-head comparison to production
  framing/navigation. Measure causal input → current body/head admission → visible shape without shifted inputs;
  prove hidden ends, smoothness and bounded capacity. The distant-head appearance recipe is not timing evidence.
- [ ] **After the bake-off selects the core grammar:** WR-07 recorded-feature replay/calibration, remaining shared primitive
  gates, WR-08 migration and WR-09 live acceptance.
- [ ] **Production debt:** retain floor/contact/mist clearance, admitted camera poses, primary form/fringe and alternate
  highlight polish, accents/optics, cost and lifecycle proof. Reflection strength is a production control; prioritize
  tunable localized/reactive highlight density rather than spending the bake-off budget chasing reflection columns.

The operator admits the current primary/alternate visual range for the next stages, with appearance caveats retained
as production debt (§0B). This does not close musical, bounded-cost, camera/lifecycle or final native acceptance gates.

**Durable current constraints:**

- Low/high states are the same world, camera, topology and bounded populations. Reactivity may change shape, colour, light,
  particles and later fog response, but it must not swap scenes or camera pose.
- Each ribbon has an authored base identity; colour may flow along history through bounded gradient nodes. Preserve smooth
  curves and continuous frames. Do not introduce jagged spikes merely to mimic a still.
- Free strands leave an actual rim/line, curl away smoothly, taper to a free tip and remain bounded; they are accents, not a
  second sheet population or a screen-space particle storm.
- Floor contact is a geometry rule, not a user setting. Floor appearance is smooth finished wet concrete with restrained
  material detail and geometrically registered coloured reflection, never a sharp duplicate mirror or painted glow.
- Mist is core to every look. Its clearance is shaped by the waveform/world, not by a camera-facing hole or a second
  simulation cadence. Audio-driven mist response remains later work.
- The shape/reactivity tuner and eventual visual editors author bounded targets/ranges; they do not become renderer-side
  simulation or another clock.
- Root `assets/` material sources/prompts are local product assets and intentionally omitted from normal GODZIPs. Runtime
  packaging remains WR-08 work; source-handoff omission is never deletion.

## 0A. Evidence and decision rules

- Compare **mock | flat landmark render | lit lab** and **native crops at 2x** for both synthetic states. The historical
  pillar-contact line is no longer a scene silhouette: the floor must disappear into mist, not form a visible horizon.
  Keep measuring ribbon envelopes; all camera/world identities remain fixed between low/high.
- Run `tools/labs/waveform_ribbon_targets.py --cards <WR-00 directory> --renders <capture directory> --output <new directory>`
  for fixed annotation-masked ROI luminance/saturation/RGB, native-size pairs and nearest-pixel crops. High's 638 px
  reference is never stretched to the lab's 640 px. Numbers guide inspection; they cannot establish visual acceptance.
- For the main fog board, extract with `waveform_ribbon_preflight.py --fog-board references/Waveform_Ribbon_Fog_Complete_Scene_Mock.png
  --output <new cards directory>`, then use `--board fog` for both the lab capture and target comparison commands.
  Its two native panels are 820x718; only their borders are cropped. Named ROIs compare waveform, floor and mist;
  no primary-board envelope is silently reused for this differently composed board.
- Inspect all five navigation poses and wide cards in both projections after every look change. Check geometry,
  reflection registration, horizon/edge concealment, banding, discontinuities and excessive haze separately.
- Change one material/geometry layer at a time, compare against its previous candidate and the mocks, retain rejected
  trials in scratch, and retain milestones under `wr04_parity_passN/` with source/recipe receipts.
- Shared primitives change only for real reusable behaviour, with a focused falsification test and bounded measured
  cost. Keep artistic look controls in the lab recipe; no global retuning of accepted visualizers.
- A test result is valid only when pytest itself exits zero. GL pixels/tests are scoped evidence, not operator sign-off.

Run `.venv\Scripts\python.exe tools/labs/waveform_ribbon_preflight.py --output .artifacts/evidence/waveform_ribbon/<new-run>`.
It refuses overwrites, copies the unmodified primary, extracts provisional native-size low/high cards, and records
archive/member/output/producer hashes, tracked diff hash, workspace status and both diagnostic projection matrices.
The initial receipt is `.artifacts/evidence/waveform_ribbon/wr00_reference_projection/receipt.json`.
It records no GL scene capture or cost: this is a preflight, not an image of a proposed Ribbon implementation.
Diagnostic half-height 4/reference depth 10 are arbitrary calibration units, not an approved artistic camera fit.

Current comparison evidence remains under `.artifacts/evidence/waveform_ribbon/`; receipts/captures are evidence, not
task status. The lab authors phase/amplitude modulation and depth sway before immutable knots enter the shared ring,
with no renderer-side simulation or new clock. Generated floor material custody/prompts are local at
`assets/textures/waveform_floor/Source.md` (root `assets/` is excluded from normal GODZIPs). Albedo is sRGB; roughness
and smooth-height are linear data. The target remains smooth finished wet concrete; rejected mottled floor studies are
negative evidence, not a current style option.

## 0B. Remaining visual gaps and immediate verification

Native current-source comparison: `.artifacts/evidence/waveform_ribbon/wr_visual_admission_20261102/` (effective
recipes, source hashes and native primary pairs; alternate reference retained at native size). Visual admission
is accepted with caveats: primary contact reflection and pale overhead edge remain production refinement;
alternate broad sheets read at native size but its high state needs highlight/strand controls.
Explicit-time look previews and native keyframes: `.artifacts/evidence/waveform_ribbon/wr_motion_review_20261102/`.
These synthetic low/high previews support visual judgement only, not musical timing, incremental runtime cost or
lifecycle acceptance. The operator accepts this visual range; floor reflection remains tunable, with a modest
reflectivity reduction a workable compromise. Highlight density and spatial packing remain production controls;
the recorded comparison uses the same reactive accent mapping across models, with body-only diagnostics alongside it.

**Ground mist ownership (operator direction):** ground-bank height and light stay at zero intentionally. The floor
uses its own existing cheap analytic distance mist (`Environment.mist` / `MIST_GLSL`), independently of the shaped
volume. Review its depth/side concealment through that layer; missing volumetric floor banks are not a defect and
must not be re-enabled to imitate the mock's lower corners.

- [ ] **Concrete finish:** the rejected floor looks gritty/mottled; the target is smooth finished wet concrete with
  restrained fine material detail. Inspect the newly generated smooth albedo under actual scene light. Do not use
  texture blur to conceal coarse aggregate, or reintroduce wet/dry coverage masks. Keep surface relief nearly flat.
- [~] **Reflection character:** `wr05_wet_contact/` replaces the sharp duplicated mirror with contact-hardened,
  gently elongated wet reflections. Floor ROI (fog high, mock / ours): median 0.23 / 0.21, p90 0.58 / 0.41,
  p99 0.92 / 0.52. Mock rows fall from bright at the contact; ours peak mid-floor. Earlier: floor-only comparisons
  showed large duplicated sine ribbons against black,
  whereas the main mock has gently softened coloured highlights over visible concrete. Keep gentle Gaussian blur
  independent of physical smoothness; retain coloured dark gaps without turning the floor into a sharp mirror or
  a uniformly hazy smear. Gaussian energy/centroid/isotropy checks pass at 1x and 2x reflection scale. Earlier
  single-sample cost figures do not cover 25-tap blur.
- [ ] **Floor illumination:** remove the spatially incorrect blurred-mirror diffuse lookup. The unaccepted soft-source
  candidate now reads position/width/colour/emission/age from admitted 3D history, but the first capture exposed a
  broad violet band and coarse albedo. Refine source/material balance against native crops, not just overall brightness.
  Recapture after the corrected floor vertex-count wiring; `wr05_concrete_light/` predates that correction and is
  diagnostic only. This reduction is unshadowed and low frequency, not exact sheet-area light or a volume-clearance
  field. No runtime per-frame CPU path is admitted by it.
- [ ] **Waveform shape and depth:** preserve preferred checkpoint `0ca9fd27`. The real swept 3D sheets and both bright
  rims are progress; folded-cloth depth, natural variation, richer fanning/gathering, hot crossings and readable low
  detail still fall short of the mocks. Reject sharp bends and flat wire-bundle readings in enlarged crops and motion.
- [~] **Mist/scene depth:** the volume (S3D-7 item in §0) now gives billowed, ribbon-carved, ribbon-lit mist with a
  dark top and clear air around the sheets. Refine the pale overhead edge toward the mock's saturated fringes;
  check sky/horizon concealment through that volume and floor/side concealment through the separate cheap distance
  mist. Ground volume banks remain intentionally off; they are not an acceptance requirement.
- [ ] **Motion and cost:** capture explicit-time slow motion for floor grain/reflection stability and both waveform
  rims; then five camera poses in both projections. Measure final floor draw, reflection generation and whole scene
  separately, plus CPU light preparation. Check Off/lazy/resize/context retirement at their owners. Current static
  images and earlier narrow timings do not close these gates.
- [ ] **Preset range and production fidelity:** keep the complete-scene and preset-range mocks as distinct attainable
  looks, including warm high accents. Preserve paired low/high scene identity. The current primary/alternate range
  is admitted for reactivity; final native/musical acceptance and production appearance controls remain open.

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
| `waveform_ribbon_package/Waveform_Ribbon_Alternate_Annotated_Mock.png` | Original 1240 × 396 pixels; SHA-256 `19161837f26e2b38005b0ca781e256ff5a96fe5b006b954cc300809f6472adb2` | Admitted alternate preset target (1 November) |
| `references/Waveform_Ribbon_Fog_Complete_Scene_Mock.png` | Original supplied 1 November, preserved byte-for-byte; SHA-256 `02129185dbccbbe9331f0bcd650eeb6853de9ea73186c5e6a6ea926cb96e28b3` | Main whole-scene target: smooth ribbons, wet floor, thick mist shaped and softly lit by the ribbons |
| `references/Waveform_Ribbon_Rejected_Curve_Detail.png` | Operator crop, preserved byte-for-byte; SHA-256 `5c2ccbbe98cd2474d8de3a2d0f2c5ae2165d935f5f9922f71caa1e63e158de7c` | Rejection evidence: uneven strand slopes and bends; never an artistic target |
| `references/Waveform_Ribbon_Fog_Preset_Range_Mock.png` | Additional supplied board, preserved byte-for-byte; SHA-256 `6bd7cc073f4192a6acecfa4e000fbb8c185f867f7e1089a3a5c028321b0a1dde` | Additional whole-scene/preset target: cool quiet sheets and warm high arcs, shaped fog, wet reflection detail |
| `references/Waveform_Ribbon_Rejected_Upper_Rim.png` | Operator crop, preserved byte-for-byte; SHA-256 `05020984b0475d80fb9c1373859c0a4b9ac3b965890b64300fab86efdd6392c1` | Rejection evidence: upper/far rim remains too dim; both boundary lines must glow more than the interior |
| `waveform_ribbon_package/Waveform_Ribbon_Architecture.md` (inside local reference package) | Package prose inspected; existing brief reproduces it | Intent, suggested mappings, gates A–H; feasibility prose is not implementation proof |

Original image bytes were extracted without editing to
`tmp/waveform_ribbon_plan_reference/waveform_ribbon_package/` and viewed at their native source dimensions.
This scratch extraction is not a new asset authority or guaranteed handoff payload. Re-extract from the original
package when necessary; never replace a missing original with a generated approximation. Hashes identify this
reference review, not mutable operator presets or permanent artistic test goldens.

**Original reference authority (superseded in scope on 1 November):** the copied brief names the primary as the approved concept image.
The archive's extra alternate does not override that instruction or require another approval before work can begin.
Its high panel has orange/peach light and a sparse black background; the primary retains cool
cyan/blue/violet/magenta light columns and hall structure. Do not average them into a third look or switch to the
easier one. The operator has now explicitly admitted both boards as eventual preset targets; measure the alternate separately instead of averaging their looks.

### 1.2 What the pictures establish

| Target component | Observed in the primary image | Consequence for the lab | Inference / unresolved detail |
| --- | --- | --- | --- |
| Composition | Ribbons travel broadly left-to-right across the lower-middle of both panels, extending beyond panel edges; dark space remains above | Block out projected path envelope and floor before shader embellishment; retain offscreen continuity | The image does not establish travel direction or phase speed in time |
| Low react | Several thin, legible overlapping cool bands; broad gentle waves, restrained glow, sparse points; environment remains visible | Quiet passages need a composed minimum body, separated strands and motion | Exact ribbon count is ambiguous: inner strands are not separate ribbons |
| High react | Larger vertical sweeps and broader/brighter sheets; more crossings, fine points and floor light; ribbon is still the main subject | Increase body/deformation/detail within the same camera and world; retain dark negative space | Exact widths, ratios and peak timing require measurement and authoring; not specified by the mock |
| Ribbon surface | Translucent sheet/filament bundles with fine longitudinal luminous lines, bright edges, local bright dots and visible darkness between lines | Model a body, defined antialiased edges and coherent internal strands; a blurred tube or plain sine line cannot match | Some fine lines may be separate filaments rather than a surface pattern; start with one strip plus material structure |
| Colour | Cyan through electric blue and violet into magenta, associated with different visible bands | Keep colour identity stable through low/high and use authored band colouring | The label permits colour shift, but not unconstrained rainbow cycling; precise mapping remains authored |
| Environment | Original board: dark interior and columns. Current complete-scene target: shaped thick mist surrounding a clear ribbon corridor | Columns are rejected. S3D-7 must supply world-space fog clearance and illumination from the actual ribbons | Density, depth and lighting are authored from visible cues; the image does not specify an optical model |
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

**Annotation masks (verified by overlay on the extracted cards, 31 October).** Crop-local pixels, right/bottom
exclusive, deliberately padded; they cover title panels, callout boxes, leader lines and their end dots.
Low: `(10,10,300,85)`. High: `(10,10,385,85)`, `(400,74,582,131)`, `(405,125,420,180)`, `(36,189,229,244)`,
`(165,238,195,300)`, `(24,459,219,516)`, `(130,395,165,465)`, `(420,592,584,650)`, `(398,582,416,598)`.

**Segmentation finding.** Neither saturation/hue thresholds nor high-pass filament detail isolates the ribbon
bodies. The high panel's bloom haze is as saturated and textured as the ribbons, and the low panel's light-column
halos pass both tests. Body width, path extrema and envelope are therefore hand-traced at sampled columns on
gridded cards and labelled as estimates. Automatic statistics are kept for colour, luminance and clipped area
inside fixed ROIs, where no segmentation is needed.

**Target table (31 October).** `tools/labs/waveform_ribbon_targets.py` holds the hand-traced geometry, measures
ROI statistics with the masks applied, and draws annotated cards. Receipt and sheet:
`.artifacts/evidence/waveform_ribbon/wr00_targets/` (`targets.json`, `targets_sheet.png`). Fractions are of panel height.

| Measure | Low | High | What it says |
| --- | --- | --- | --- |
| Union envelope, top to bottom | 0.39-0.59 | 0.24-0.66 | High spreads about 2.5x vertically |
| Centre-line mean / wave amplitude | 0.50 / 0.041 | 0.46 / 0.042 | The centre-line wave barely changes: it is the authored oscillator (section 4A) |
| Single body width | 10-25 px | 40-90 px | Bass width about 3.5x |
| Wavelength (cyan peaks) | ~285 px | ~245 px | About 14% shorter: mids add complexity, not a new scene |
| Bodies | 3 | 3 | Cyan/light blue, blue/violet, magenta; inner lines are structure |
| Floor contact line | 0.635 | 0.637 | Same camera and world |
| Upper environment, median luminance | 0.065 | 0.072 | Same environment and exposure |
| Floor median luminance / clipped | 0.14 / 2% | 0.38 / 39% | Floor reflection tracks ribbon emission strongly |
| Body / crest ROI clipped | 4% | 20-36% | White-hot cores only where high sheets cross |

Historical primary-board calibration (superseded environment; not current scene instructions): half-height 4.98 world units
at a 4-unit wavelength, pitch 15 degrees down, pivot at ribbon centre 2 units above the floor, back wall 2.3 units
behind, floor visible to 11.8 units in front, ribbon reflection centred at 0.89 of the height. Light columns stand
at about 0.04, 0.14, 0.30, 0.50, 0.74 and 0.95 of the width. Tolerances are still set from candidate comparisons
with operator review, never invented ahead of them.

The following original-board ROIs remain historical comparison guides. Current composition must hide horizon/floor
boundaries and uses the complete-scene fog cards in §0A. Record native pixels alongside normalized coordinates:

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
| Ribbon | `core/ribbon_ring.py:RibbonRing`; `core/ribbon_packet.py`; `rendering/gl_programs/ribbon.py`; `rendering/quick/scene3d/ribbon.py:RibbonPrimitive` | Shared bounded history, oriented/swept surfaces and OIT/HDR material exist; `Ribbon_Path.md` owns remaining admission gates. EB wakes remain a separate precedent, not the new consumer's implementation |
| Transparent/emissive scene, resolve, bloom and HDR | `rendering/quick/scene3d/target.py:SceneTarget`; `rendering/gl_programs/scene3d.py:SCENE_OIT_GLSL`; shared post resources in `scene3d/post.py` | Available opt-in substrate. Consumer must prove material/emission/depth ordering, bright overlap, AA, card alpha and no double tone mapping |
| Reflection | `rendering/quick/scene3d/reflection.py:PlanarReflection`; `rendering/gl_programs/reflection.py` | Bounded mirrored-camera reflection is implemented and used by the lab. WR-05 retains scene inclusion, lifecycle, full cost and visual fidelity gates; cubemap/photo environments are not a substitute |
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
S3D-7 independent volume proof      -> ribbon-shaped fog in lab -> fog in production
S3D-2 independent emitter proof      -> accents in lab -> accents in production
    -> restrained Settings / presets -> mock | lab | production -> native/operator A–H
```

This is a dependency graph, not permission to skip Current_Plan's S3D order. §6 owns when S3D-2 through S3D-5 are
admitted; if S3D-3/4 precede S3D-5 there, this mode does not reorder them. Each shared primitive earns its own offscreen
proof before consumer integration. An unfinished S3D-5 blocks the floor slice, not independent ribbon geometry work.
S3D-3 may supply useful retained material helpers. The operator admitted S3D-7's bounded static volume slice for the
complete-scene target: this is a visual prerequisite. S3D-4 fluid, S3D-6 shadow maps and lightning remain outside this slice.

The final target visibly needs reflection, layered bands and points. A successful one-ribbon/no-floor study is only an
intermediate gate, not a claim to match the full board. Before each production feature is added, bring that feature's
lab recipe to the mock. Section 0 owns the current waveform → floor optics → volume → accents sequence; production
and Settings follow visual acceptance. Do not wait until Settings to discover that camera or materials differ.

## 4. Work packages and required artifacts

Artifact names below are proposed output roles, not tools/files that already exist. Store bounded run output under
an explicit `tmp/waveform_ribbon/<run-id>/` path (or the operator's chosen evidence directory). A small manifest must
identify every artifact. Never overwrite old evidence to make the latest attempt appear to have always passed.

### WR-00 — Lock the reference and reproducible comparison contract

**Entry:** mode planning or implementation is admitted; original package is available.

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

**Current substrate:** bounded CPU path/history and transported-frame reference owners are documented in
`Docs/Reference/Ribbon_Path.md`. This checklist contains only the remaining admission work.


- [ ] Specify fixed maximum ribbons, history samples, active counts, sample spacing/time interpretation, record bytes,
  topology and reset/retirement semantics. Calculate memory and worst-case vertices from these caps before allocation.
- [ ] Define normals/tangents, two-sided material behavior, UV/path coordinates, edge coverage and end treatment.
  Width changes must remain positive and continuous; initial empty/one-point history must not produce NaNs or full-length pops.
- [ ] Exercise stationary, straight, unequal-spacing, cusp-like, repeated-point, reversing, growing and saturated-history
  fixtures. Track marked sample/strand positions before/after insert/evict. Compare submission partitions for identical admitted knots. Independently resolve any future variable-dt resampler
  before claiming equivalent nonlinear trajectories.

**Exit/artifacts:** small pure record/layout contract, bounded CPU reference and path cards/trace with finite positions,
no unexplained discontinuity, persistent identity and fixed capacity. Focused tests must falsify normalized-segment
placement, frame flips and capacity overflow; visual review still owns what a desirable waveform looks like.

### WR-02 — S3D-1 GPU primitive proof in its own harness

**Entry:** WR-01 contracts defined; no Waveform mode registration required.

**Current substrate:** the reusable GPU owner, shader helpers, packet ABI and primitive harness exist; detailed
contracts and existing evidence live in `Docs/Reference/Ribbon_Path.md`. The remaining checklist is the admission gap.

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

### WR-03 — Camera and fixed-world composition

**Entry:** S3D-1 proof admitted; WR-00 primary-target measurements exist.

`tools/labs/waveform_ribbon_lab.py` owns explicit synthetic low/high input, flat/lit captures and five navigation
poses over the shared framed camera. Three real 3D sheets, generated-map floor and temporary analytic mist are
implemented. Tests verify flat-capture repeatability and render ownership, not mutable artistic envelope values.
The rejected hall/column study is historical evidence at `wr03_blockout/`; it is not a current scene target.

A readback upside-down bug hid behind near-symmetric ribbons until the flat hall showed the floor on top:
`OffscreenRenderTarget.read_rgba()` is already top-left; never flip it again.

- [ ] Match both ends extending beyond the image with sufficient offscreen continuation. Do not hide end caps at one
  pose only; test a small camera move. Keep the world fixed under navigation.
- [ ] Validate fixed camera, environment, floor geometry, palette, seed, base path and topology for the low/high
  pair. Permit only declared reactive body/deformation/emission/detail inputs to differ.
- [ ] Evaluate current native-resolution target/flat/lit pairs across all navigation poses in both projections;
  preserve world scale and absence of visible floor/scene edges. Evaluate wide/narrow cards
  separately for cropping, minimum readable strand sizes and background/floor balance.

**Exit/artifacts:** same-scene flat low/high cards, world/camera recipe and scale/proportion deltas. Advance only when
the simple body and composition are credible; a visually wrong silhouette must not receive another glow pass.

### WR-04 — Ribbon material, internal structure and controlled light

**Entry:** WR-03 geometry/composition accepted as an intermediate.

**Current substrate:** translucent body, rims and longitudinal structure share the path coordinate on oriented thin
sheets, and overlaps use shared OIT. The open items below own remaining material/optics acceptance.

- [ ] Author cyan/blue/violet/magenta bands from one scene palette and consistent light sources. Keep material emission,
  illumination, alpha coverage and bloom weight separately inspectable; do not use alpha as an arbitrary brightness knob.
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

**Current substrate:** shared `PlanarReflection`, mirrored physical camera, lab light/spark inclusion and generated
albedo/roughness/smooth-height maps with allocation-failure cleanup. Local asset custody/prompts live at
`assets/textures/waveform_floor/Source.md`; root `assets/` is intentionally excluded from normal GODZIPs. Current
fidelity gaps and pending filter/illumination proof live in §0B. Remaining proof and fidelity work:

- [ ] Complete the reflection inclusion/clip contract, including OIT body and eventual volume. Use the same scene
  geometry/time/material functions; exclude the receiver/self-recursive reflection.
- [ ] Prove floor-to-object registration with an asymmetric coloured object/light fixture at known positions; translate
  and orbit the physical eye. Check reflected high/low changes use the exact same logical snapshot, without one-frame lag.
- [ ] Refine bounded roughness/filtering, world-space material scale, normal detail and distance-dependent appearance
  using the placed generated maps. Match smooth concrete plus gentle reflection blur and coloured dark gaps together;
  neither increasing blur nor sharpening the existing mirror is sufficient (see §0B).
  Production packaging must include these owned assets at WR-08. Do not substitute painted glow for reflected geometry.
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

**Entry:** admitted lab visual range with appearance caveats. Use §5 signal contract and the §5.1 recorded full-stack
comparison to choose a credible motion grammar before calibrating it for production.

- [ ] Run the §5.1 four-candidate bake-off first and record the chosen core grammar plus rejection reasons. Do not silently
  delete Candidate A, and do not let colour, glow or particle polish rescue weak geometry/motion.
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
- [ ] Implement the full controls, Settings, presets and visual editors designed in
  [Waveform Ribbon Migration Plan](Waveform_Ribbon_Migration_Plan.md), at the existing typed/default/declaration owners.
  Finalize grammar-dependent targets from the §5.1 winner; validate useful ranges without exposing diagnostic-only
  knobs or adding a second defaults owner. The full migration scope is not reduced to a minimal control subset.
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

## 4A. Motion model: flowing history

The ribbons combine **music history flowing across the hall** with model-specific current logical deformation:

**Visible-body correction:** a head-only change is insufficient for the operator's authored low/high forms. Retain
normalized carrier/fine history at the head, and let the sole logical state drive the selected model's visible body
(flowing bends/rolling twist, traveling packets, elastic modes or macro-flow/detail). Its bounded pure snapshot projection is shared by body, accents, reflection
and mist-clearance consumers. It never mutates admitted history or integrates in the renderer. The lab may measure a
bounded CPU packet projection; production admission must move/measure that projection at the existing shared boundary.
Prove same-time low/high geometry and music-versus-constant-drive body output; a light/mist-only change cannot pass.

- At a head beyond one edge of the view, each logical knot records normalized musical shape detail at that moment:
  centre-line offset, relative width/twist, emission/hue. The model-specific current projection maps these into the
  authored quiet/peak forms without changing their musical history. An admitted knot never changes
  (`core/ribbon_ring.py`). Music therefore travels along the ribbon: a bass hit becomes a wide stretch that
  drifts across the hall.
- The whole history moves by one uniform translation derived from logical time, composed into the MVP.
  No knot is rewritten to move. Flow direction and speed are fixed authored scene constants. Music never changes
  them, because a speed change would read as a different scene (gate A).
- The authored carrier advances with logical time; each candidate adds its own bounded musical motion. Raw band
  envelopes plotted as height make jagged plateaus, not the mock's waves. A shared carrier with different gains is
  insufficient to establish four distinct reactions.
- Every history-carried shape control (width, twist, offsets) is band-limited to features of about half a
  wavelength or longer. A control changing over d seconds draws a feature flow speed x d long, so fast changes
  draw lumps. Immediate musical punch may come from current logical body deformation and light, without rewriting history.
- Any per-frame projection must be a pure function of immutable history and current logical state (lab snapshot or
  production shader). Nothing may
  rewrite history, because that would bring back the per-tick cost the ring removed.
- The head and tail stay off-view by at least two knot spacings plus the visible end margin, so the provisional
  boundary segments and evictions are never seen.
- Capacity follows from the scene: knots = (visible span + both margins) / flow speed x knot rate. The lab chooses
  speed and knot rate, then checks that the result fits the 256-knot cap at the widest admitted aspect.

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

### 5.1 Core-reactivity candidate bake-off

**Operator decision requirement:** the winner comparison must use the existing recorded real-music samples and
include the complete reactive stack: visible ribbon width/bend/twist, particles, localized highlight density/light
and colour shifts. A mist-only response does not count. Synthetic/geometry-only captures remain isolation diagnostics,
not a substitute for this decision. The initial broad-navigation synthetic head configuration has excessive transport
delay; recorded demonstrations use an explicitly scoped fixed-view near-head/fade admission, with production navigation
still open. Do not time-shift audio or conceal delay with cropped video. Verify body response separately, then full stack.

The four candidates must be different motion models, not a shared oscillator/global pulse with different gains.
Current-body projection is specific to each model: A has band-driven flowing bends and accumulated rolling twist;
B has bounded traveling bend/width/torsion packets; C has independently integrated damped bending/lateral/torsional
modes; D has long authored macro-flow with captured PCM RMS-envelope detail. D is waveform-envelope-derived, not
literal audio-frequency PCM plotted at knot rate. Head-written saturated colour changes advect with history; do not
replace them with a whole-scene palette fade. Shared particle/highlight inputs do not establish distinct body motion.

Do not choose the ribbon's core geometry/motion grammar from prose alone. The current concept mapping remains a real
candidate and is **not** replaced by this comparison. Before recorded-music tuning, implement four deliberately distinct
bounded candidates behind the lab fixture only:

| Candidate | Core geometry/motion response | Main question / failure mode |
| --- | --- | --- |
| **A - Current concept mapping (retain)** | Bass drives body width and slow large bend; mids drive twist plus lateral/vertical centerline deformation; highs may add restrained fine edge/body motion; typed transients add short local curvature/tension. | Does the straightforward band-to-body mapping already read clearly and musically without becoming globally rubbery or having every band fight for the silhouette? |
| **B - Traveling deformation packets** | A typed transient/attack launches a bounded bend/width/torsion field at the live head. Its centre travels with flow; age determines decay and smooth retirement. A pure snapshot evaluates these fields over immutable history. | Do visible traveling reactions make hits and phrases easier to read, or do repeated events turn the strip into beads/lumps? |
| **C - Elastic tension dynamics** | Audio targets and typed velocity impulses excite separate bounded low-bending, lateral and torsional modes. The logical clock integrates once; a pure snapshot projects them over the visible body. | Does a spring-like body feel organic and powerful while preserving attack, or does smoothing/overshoot make it late, seasick or too similar across bands? |
| **D - Authored macro-flow + waveform fine structure** | Keep the slow authored head oscillator as the large silhouette. Sample a small, band-limited amount of current waveform/band detail into newly admitted knots so fine musical structure rides on the body and then advects with history. Clamp wavelength/amplitude so dense audio cannot become jagged full-body PCM. | Can literal sound detail add recognisable texture without destroying the smooth mock silhouette, aliasing at native pixels or duplicating the high-frequency accent layer? |

#### 5.1.1 Current owners and execution

`tools/labs/waveform_ribbon_reactivity.py:HeadHistory` owns explicit 120 Hz logical stepping, typed-event identity,
normalized immutable `RibbonRing` history and model-specific snapshot geometry. `Lab.render_history` consumes a
published snapshot without rebuilding/appending history or integrating motion. All body/particle/reflection/mist
consumers receive the same packet. The bounded CPU projection is lab evidence; runtime admission must measure and
place it efficiently at the shared production boundary rather than inherit an unmeasured per-frame CPU builder.

`tools/labs/waveform_ribbon_recorded_input.py` reuses `load_jsonl`, `ReplayBeatEngine`, canonical source/technical
configuration without preset reads, `PcmReanalysis` and the production floor-independent raw-band reference mapping.
Clipped recorded live lanes are not the body feed. The same precomputed source drives all four models. Native PCM
RMS is a visual-detail input for D, not another FFT/analyzer or literal audio-frequency geometry.

`tools/labs/waveform_ribbon_music_bakeoff.py` is the maintained capture entry point. It runs under an external whole-
process-tree Windows Job deadline, uses project Python and an explicit FFmpeg executable, and refuses overwrites:

```powershell
& '.\.venv\Scripts\python.exe' tools/labs/waveform_ribbon_music_bakeoff.py --recording logs/visualizer_recordings/ragdoll_quiet_intro_loud_end1.jsonl --start 20 --seconds 10 --output .artifacts/evidence/waveform_ribbon/<new-run> --ffmpeg .artifacts/scratch/wr_audio_video_tools/ffmpeg.exe
```

The scratch FFmpeg binary is an isolated tool dependency, not installed into the product environment. Another
machine must supply its explicit executable path. Ground volume banks stay zero and the separate cheap floor mist
is preserved. Reflection-column polishing stays production debt.

#### 5.1.2 Distinct motion and causal timing

- **A: flow / rolling twist.** An advected carrier, current bass-driven width and broad bend, accumulated mid-driven
  rolling torsion/lateral weave, plus retained musical fine structure. Its direct body envelope is not imposed on B/C/D.
- **B: traveling packets.** Typed accents launch local bend/width/torsion/colour/light fields at the admitted head;
  their centre moves with constant flow. A bounded eight-packet population has a model-specific 0.8 s admission gap;
  packets fade smoothly in their final two seconds before six-second retirement. No visible expiry pop is allowed.
- **C: elastic torsion.** Separate damped low-bending, lateral and torsional modal state integrates once at logical dt.
  Audio targets and typed velocity impulses excite the fields; rendering only evaluates them. No common affine pulse.
- **D: macro / PCM envelope.** Long authored flow and slow passage scale carry bounded, head-written PCM RMS-envelope
  detail. Review enlarged moving rims for unwanted short ripples. It is not raw waveform PCM plotted at six knots/s.

The body may change across already-visible history through these current logical projections; stored musical records
remain unchanged. Do not describe this as the earlier head-only geometry travelling unchanged. The fixed sweep path
uses convex B-spline controls; body projections share bounded y/z/width domains, smooth curve/floor contact and caps.

Head-written colour uses a saturated hue interpolation between authored quiet/hot colours; it advects with history.
A global palette fade cannot demonstrate moving colour. Particles and dense highlights must accompany the recorded
judgement, with their shared input mapping held equal across candidates so they do not mask identical body motion.
The current sparks are the existing bounded history-spark primitive, not proof of production event-owned cohorts.

Musical review currently admits only the fixed mock Orthographic view at the native panel aspect. The head lies beyond
its actual right edge with two knot spacings and hidden fade margins; short off-view fades keep the live head nearby.
This is not full navigation admission. The original distant-head/broad-navigation synthetic capture is rejected as a
musical demonstration. Its exact standalone producer is retained only under the corresponding local evidence's
`producer/` directory; CPU synthetic fixtures remain diagnostic tests, not the winner comparison.

Recorded audio and feature windows are aligned to the same existing `_new_samples` PCM reconstruction. Retain original
feature timestamps, sample-aligned anchors and drift. No audio/video shift may hide body latency. Colour/fine history
still has physical transport; current body response must also be checked before a fresh knot can enter view.

#### 5.1.3 Required review package and falsifiers

- The same audible real-music windows through A/B/C/D, including quieter and intense material, with valid real pre-roll.
  Export a simultaneous labelled MP4 with audio, one short WebP per candidate and five synchronized native checkpoints.
  Preserve original source hashes, effective recipes, source/event IDs, alignment, camera, logical/knot/render rates.
- Same-time quiet/peak body captures must visibly change actual ribbon geometry. Light/mist changes alone fail.
  Compare recorded body against a matching-time idle control and inspect continuous motion; constant energy bias or
  automatic carrier drift alone is not musical reactivity. Keep body-only/native crops as diagnostics beside full stack.
- Tests must cross the actual snapshot/render seam: visible old body can respond before the next head knot, rings
  remain unchanged, render delivery does not integrate state, four profiles are not scaled copies of one oscillator,
  packet geometry advects and fades before expiry, and D's PCM detail changes its history without a shared body pulse.
  Head-target traces alone do not establish the final geometry mapping.
- Report the current CPU projection/append and GPU scope honestly. Old head-only diagnostic primitive timing does not
  establish current projection/whole-scene/native cost. Full production pose/size/cost/lifecycle gates remain open.
- Reject broken smoothness/frames, visible ends, population overflow, new events in silence, repeated/stale events,
  hidden latency, indistinguishable motion or an unchanged visible ribbon rescued by fog/light/particles.

#### 5.1.4 Decision

**Current local review packages (Awaiting Validation):**

- `.artifacts/evidence/waveform_ribbon/wr_planned_motion_review_ragdoll_20261102/`: source 20–30 s.
- `.artifacts/evidence/waveform_ribbon/wr_planned_motion_review_human_20261102/`: source 15–25 s.

Each directory contains `comparison_with_audio.mp4`, `A`–`D/motion.webp`, `synchronized_native_sheet.png`,
same-time body-range proofs, input metadata and `receipt.json` with source/artifact hashes and scoped CPU costs.
Earlier head-only and common-pulse drafts are rejected; these paths identify the distinct-model review.

Record the operator's choice and rejection reasons against the audible clips: flow, twist, local packet travel,
elastic attack/settle, low-react beauty, moving colour, dense/local highlights, particles, continuity and bounded cost.
If none is credible, select none. A hybrid requires a same-source ablation showing complementary jobs; do not stack
all four. A still or pixel count cannot establish the reaction's musical feel.

After a credible motion choice, WR-07 calibrates its source scales, hot-passage headroom, silence/hot-start behaviour
and timing on recordings; WR-08 verifies production parity and source reachability through actual Settings/presets/audio.
Final native/operator acceptance remains separate from this lab comparison.

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

**Section 0 is the sole live sequence.** The ribbon material and generated-map floor exist; their fidelity is open.
The bounded mist prototype exists; its remaining reusable admission/lifecycle/cost gates are still open. The operator
admits the current visual range with production caveats; motion selection remains Awaiting Validation under §5.1.

- [ ] **Awaiting Validation — reference completeness:** no clean annotation-free scene or reference animation was
  present in the inspected package. Exact hidden pixels, topology count and optical model are unspecified; the motion
  model is the operator's flowing history (section 4A), with direction and speed authored in the lab. Proceed from visible pixels and document authored choices; request additional originals only
  if an actual comparison is blocked. Do not make a generated reference the new goal.
- [ ] **After motion selection — recorded calibration coverage:** audit quiet/middle/hot and silence/hot-start windows,
  presence gating (including PCM detail), headroom and attack/settle under WR-07. Two comparison windows do not close it.
- [ ] **Awaiting architecture proof:** complete S3D-1 camera-facing width/defocus, S3D-2 emitter extensions,
  S3D-5 reflection inclusion/lifecycle/cost and S3D-7 bounded volume gates at their owners above.
- [ ] **Awaiting Validation — tolerances and delivery framing:** confirm target landmark/ROI tolerances, wide-view
  framing and acceptable small-card detail using actual candidate images, before calling resemblance achieved.
- [ ] **Awaiting Logs/Validation — cost and native acceptance:** hardware budgets, warm/native measurements, live musical
  legibility, interaction, context retirement and operator A–H decisions remain future evidence gates.

None of these uncertainties permits replacing the reference scene, freezing presets, weakening BTF, or creating a
second rendering/timing authority. Independent work may proceed through its stated entry/exit criteria; consumer and
visual gates stay open until their actual dependencies and evidence are satisfied.
