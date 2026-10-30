# SRPSS | Current Plan

Live, ordered work only. `[ ]` work remains; `[~]` a candidate exists but is unaccepted (awaiting validation, never an
implicit pass). When an item lands, delete it: completed work lives in source control and its durable contract in
`Spec.md` / `Docs/` (Reference, Architecture, Guardrails, Guides); rejected mechanisms in `Docs/Historical_Bugs/`. This
is not a changelog. Deferred, unadmitted ideas live in `Future_Work.md`.

## 0. Order, scope and rules

**Work strictly in this order:**

The operator admitted the Waveform Ribbon WR-00 reference/projection preflight on 28 October alongside the
remaining §2/§3 gates. This preparation introduces no production registration and does not bypass shared primitives.

1. **§2 Everything else before the next mode**: fixes, then Settings/UX, then feature work, then guided-setup stills and cleanup (§3).
   §5 is a watchlist observed during normal use, not a task queue.
2. **§6 Shared 3D architecture**: one step that builds the reusable 3D primitives, each proven on its own harness.
3. **§7 Visualizer modes**, one at a time, in order: **Waveform Ribbon → Reactive Liquid / Melt Pool → Concrete Rain →
   Usu Moonscape**. Each is built lab-first (§7.0).

**Accepted baseline (do not reopen as general work):** original Bubble, **Extruded Bubble (closed 2026-10-25)**, Neon
Lake, Oscilloscope, Spectrum/Rainbow Ghost, Sphere, source routing, landed transitions and Foundry launch buttons.
Reopen any of them only on a concrete new defect.
The operator's 28 October EB motion/reactivity/framing follow-up below is a scoped reopening, not a general recovery restart.

**Rules:** one Settings/capability/CUSTOM/render/lifecycle owner and the sole Visualizer logical clock. No new
floor, capture/DSP, renderer-side simulation, timers/polling or camera-following replacement populations. Preserve
authored presets (mutable, never test-pinned), BTF, accepted timings, parallel work and strict retirement barriers.
CLI/sidecars, never environment-variable configuration. Smallest meaningful focused test per change; the isolated
chunked suite only at milestones; no build/installer unless requested. Visual work is judged on rendered pixels against
its target (`Docs/Guides/Visualizer_Visual_Tuning.md`), and any claim of "fixed" needs the failure reproduced first.

**Retired section IDs.** §4/§4A/§4B, G00–G33, EB-A…EB-S and EB-R25…EB-R43 (Extruded Bubble recovery) were retired
when Extruded Bubble closed; documents citing them refer to that history: `git show 3c6cf7d8:Current_Plan.md` and
`Docs/Reference/Extruded_Bubble/Investigation.md`. Stable IDs kept below: §2A, §3 (RM/SC/SC4), §4C, §5, R38/R41.

## 2. Before the next mode: fixes, Settings/UX, features

### 2A. EB follow-up — authorized implementation

`Docs/Reference/Extruded_Bubble/Motion_Reactivity_Viewport_Plan.md` owns source findings, measured baselines,
approved direction and detailed gates. Work in narrow tested/audited checkpoint pushes. Keep the authored lens,
world geometry and camera fixed during resize; compare the original rectangle before accepting framing changes.

- [~] **EB28-8 — Awaiting validation in normal idle use:** the tiny-shell cancellation defect is repaired at shared
  sphere intersection; fixed-ID native composition/reflection/transmission and5/8/12px temporal regressions pass
  without added samples, filtering, dimming or audio changes. Confirm the formerly stippled shells stay stable in
  ordinary paused/quiet playback; report a fresh example if flicker remains. The broader EB implementation and
  lossless optimization audit are closed; Orthographic appearance work stays deferred beyond the entire backlog.
- [ ] **EB performance (logical CPU first):** `Docs/Audits/EB_Performance_Investigation_2026-10-29.md` owns the
  measured ranking and checkpoints. The logical tick overruns its 11 ms budget and starves the render thread through
  the GIL. Work through the ranked items losslessly, re-measuring with `tools/eb_logical_cost_probe.py`.

### 2B. Settings and UI (in this order)

- [ ] **3D Settings combobox double-border regression:** reproduce the extra nested outline visible when opening the `3D Visualizers` quality selectors, identify the introducing shared-style change from source-control history if practical, and fix it at the common combobox/popup ownership (`StyledComboBox` / shared popup view/container styling), not with an Extruded Bubble or tab-local override. Restore one intentional outline for the control/popup while preserving theme semantics, focus/hover/on states, scrollbar/layout behaviour and all combo sizes; inspect other Settings comboboxes for the same regression and verify the corrected native rendering.
- [~] **Display Settings capacity — awaiting physical hotplug validation:** current-screen rows have no fixed cap;
  focused six-screen/disconnect/reorder/zero-screen and retirement checks preserve canonical selections/bindings (rechecked 28 October).
  Check Settings remains coherent during actual disconnect/return and explicit reauthoring; hidden form evidence:
  `tmp/pytest_ux30_display/test_display_ui_rows_follow_to0/six_display_rows.png`.
- [~] **R38 hover display-transfer glyphs — awaiting physical topology use:** source/model/lifecycle and native Quick
  hit/tooltip/fade checks pass on both connected physical displays (MSI G321Q and LG TV, both DPR 1.5);
  transfer Save/Cancel transaction checks pass. Remaining physical coverage is unequal-DPI screens and monitor
  unplug/return. Eligibility and transfer reuse CUSTOM; Hide Controls remains Edit-only. Native control capture:
  `tmp/ux30_actual_displays/receipt.json` and per-screen `transfer_glyphs.png`.


## 3. Guided-setup stills and bounded source cleanup (at a stable checkpoint)

`Docs/Reference/Guided_Setup.md` owns still-image consumers and authoring. Animated publication contracts remain
in `Docs/Reference/Release_Media.md` for explicit future requests.

- [ ] **Guided-setup still images:** audit the actual guided-setup image consumers and keep their stills current;
  generate only missing/stale stills through their existing Foundry/operator-sheet authorities and inspect the results.
  Animated catalogues/showcases are deferred until explicitly requested; no automatic maintenance obligation.
- [ ] **SC1 Retire the unused root `transitions.direction`:** confirm no callers, then forward-strip it (changes the
  operator's defaults; authorized cleanup); prove import/merge/save cannot resurrect it.

## 5. Watchlist (observe during normal use; reopen only on evidence)

- [~] **Steam Games You Follow images:** many update entries lack images. Audit URLs, redirects/statuses, cache keys,
  game IDs, fallbacks, dedupe and selection order (including artwork fetched but rejected downstream); prefer
  image-bearing updates without suppressing legitimate no-image entries; instrument attrition, compare natively with
  Feeds. A generic game cover existing is not proof an image is missing.
- [ ] **Steam artwork 404** for asset hash `9b4a68b51c5f` (23 Oct MC run, `logs/run_matrix/2026-10-23_idle_hint_shaft/`)
  and earlier `4b349d51e996` / `3f5b734df3c5`: stale metadata vs genuinely missing CDN asset, before changing lookup.
- [ ] **Monitor power/wake:** display off, > 30 s off, rapid off/on, reordered return, both selected displays absent:
  widgets keep physical assignments and CUSTOM geometry. On recurrence record timestamps, remaining screen, flavour,
  Interaction Mode and wake/exit input (history: R-79).
- [ ] **Refresh contention:** correlate FEEDS/Gmail/Reddit queue/claim/publish/retire with transition delays in a natural
  dual-display trace (fairness, no post-transition stampede, retained last-good content).
- [ ] **Cross-display Media shortcuts** delivered once on the other display, when exercised.
- [ ] **Music recorder** 60-second clip, signal/history, cancel and mixed-DPR UI, when recording is needed.
- [ ] **Frozen release gate (operator scheduled):** Standard/Diagnostic from one compile, MC and Reddit Helper installed
  startup/exit, Settings/widgets/cache/audio and installer behaviour.
  Check installer logs and obsolete-file removal in both curated theme/preset trees. Both sources declare whole-tree
  replacement; verify Diagnostic now reads that installed theme tree too.
- [ ] **Conditional evidence only:** original Bubble tiny-radius judder (R-105) and dual-display reboot recovery
  (R-134–R-145) need new reproductions. The 90 Hz versus 60 Hz investigation stays off limits.

## 6. Shared 3D architecture (one step, before the next mode)

The architecture planned for the dropped concepts (volumetric music chamber, audio aurora/ribbon volume, photo
fracture portal, voxel morph field, holographic depth slices, procedural storm, reactive particle field,
terrain/skyline/tunnel, deformable blob sphere) is worth having; the modes were not. Build it here as shared primitives
on the existing Scene3D substrate (`Docs/Reference/Scene3D_Resources.md`): `MeshResources`, `SceneTarget`, depth-aware
OIT, probe, defocus, HDR intermediate, framed camera. Each primitive is proven on **its own offscreen harness** with
bounded, measured cost (TIME_ELAPSED, median/p90), lazy creation, zero dormant work and clean retirement; none waits for a
consumer, and none becomes a second renderer, clock or camera. Read the 3D foundation lessons in
`Docs/Reference/Transitions.md` before each slice. Order follows which mode needs them first.

- [ ] **S3D-1 Ribbon / strip primitive — WR-01a/b CPU history/frames landed; GPU work open:** generalize what Extruded Bubble's wakes proved (`extruded_bubble_wake.py`, the
  `TRAIL_*` programs): a bounded history SSBO, centripetal Catmull-Rom strips placed by a continuous index (never by a
  share of segments), camera-facing or oriented width, OIT translucency with defined edges and inner structure,
  shared defocus. Multi-ribbon, fixed maximum history. *Consumers: Waveform Ribbon; trails anywhere.*
- [ ] **S3D-2 Particle population extensions (G4):** inventory the existing compacted-population/sprite/streak
  helpers first; add bounded lifetimes, emitters, transient bursts, indirect draws and compute-driven arrangement
  (morphing a fixed population between shapes, from the voxel morph concept). Deterministic admission/retirement.
  *Consumers: ribbon sparks, rain droplets/crowns, melt droplets.*
- [ ] **S3D-3 Static scene geometry and materials:** authored static meshes (slabs, curbs, walls, recesses, wells,
  simple skyline/tunnel slices) with their own roughness/bevel/contact shading, built once and retained; photo-textured
  shells/planes with real depth (from the fracture portal and depth-slice concepts). *Consumers: Melt Pool chamber,
  Concrete Rain street.*
- [ ] **S3D-4 Dynamic surface field:** a bounded GPU height+velocity grid (compute or ping-pong), impulse injection,
  damping/return, a displaced mesh with normals from the actual surface, and an opt-in deformable sheet for shapes a
  heightfield cannot make (from the deformable blob sphere concept). *Consumers: Melt Pool body, Concrete Rain
  ripples/puddles.*
- [ ] **S3D-5 Reflections and wet surfaces:** a bounded planar/probe reflection for floors and pools, wet-surface and
  puddle masks over authored ground, and reflection-distortion sampling driven by a surface field. No screen-space trick
  that collapses under camera motion. *Consumers: Waveform Ribbon floor, Melt Pool, Concrete Rain.*
- [ ] **S3D-6 Shared shadows (G2 / S25):** one fitted directional depth map, bounded soft PCF/bias, caster/receiver
  admission, resize/teardown/dormancy and tier cost on a real test scene (also Usu's S25; not a revival of the rejected
  Extruded cast shadows).
- [ ] **S3D-7 Lightning, then reduced-resolution volumes (G5):** bounded procedural bolt geometry/light, then fog/smoke
  volumes with advection/reprojection and no permanent extra targets or separate cadence (from the volumetric chamber and
  storm concepts). *Consumers: chamber/street atmosphere.*

## 7. Visualizer modes (one at a time, in this order)

### 7.0 Method: lab first, then production

Extruded Bubble's lab (`tools/labs/extruded_bubble_lab.py`) reached the mocks long before production did; production
then closed the gap by measuring against both. Do the same for every new mode:

1. **Target first:** the mock/concept package and its low/high pair; write the mode's contract and hard gates (from its
   brief) into its focused doc before code.
2. **Lab:** `tools/labs/<mode>_lab.py` composes the target scene by hand, offscreen, from the shared primitives, with
   free knobs and no Settings/preset plumbing. Reuse the context/target and ownership contract in
   `Docs/Guides/Visualizer_Labs.md`. Iterate on rendered stills (mock | lab sheets) until it is close.
3. **Production through the shared substrate:** typed Settings, presets, the logical clock and lifecycle. Diff the lab's
   effective knobs against production's key by key; judge with **mock | lab | ours** sheets per preset, the per-mode
   capture tool (`tools/<mode>_capture.py` on recorded real music) and measurements (regional colour, on-screen size
   bands, Range audits), as in `Docs/Guides/Visualizer_Visual_Tuning.md`.
4. **The lab is a waypoint, not the goal:** keep going toward the mock; keep the lab (it costs the product nothing).
5. **Same-scene low/high proof, measured cost, dormancy and retirement** before calling any stage done; the operator
   gives final sign-off.

### 7.1 Waveform Ribbon (next)

Chosen first: the smallest contained scene, it directly reuses Extruded Bubble's wake work (S3D-1) plus S3D-2/S3D-5,
and it proves the lab-first pipeline before the bigger scenes. Brief and gates: `Docs/Future_Work/Waveform_Ribbon.md`
(mocks in `references/waveform_ribbon_concept_package.zip`).

Execution must use `Docs/Reference/Waveform_Ribbon_Lab_Plan.md`: WR-00 reference/crop/recording custody, then
WR-01/02 independent S3D-1 proof before composition. The copied brief approves the primary cool hall image;
the archive's alternate is context only. Existing EB wakes/probes do not establish a generic ribbon or floor reflection.

- [ ] **WR-00 remaining:** confirm annotation masks/crops and measured target tolerances; choose recorded-audio
  windows and fit a stable Orthographic scene eye/pivot/world/palette. Reference/projection preflight is landed;
  output `.artifacts/evidence/waveform_ribbon/wr00_reference_projection/receipt.json` records its limited scope.
- [ ] **Next implementation: WR-02a input-path separation:** keep the CPU geometry/frame oracle for tests;
  remove its full-history reconstruction from the proposed per-tick upload route. Measure actual changed-input
  history/frame preparation, packing, upload and draw separately, then choose incremental reuse or justified GPU
  work with epoch/eviction/dormancy proof. The ~90 ms fixture+reference+packing result is not a software-rendering
  cost or an existing runtime regression. No runtime mode consumes the prototype (`Docs/Reference/Ribbon_Path.md`).
- [ ] **WR-02 remaining GPU/native gates:** curved-frame/normal/precision/near-plane/AA and failure coverage,
  then OIT/HDR/camera-facing/defocus and broader measured cost. Solid oriented geometry has native Ortho/Perspective,
  gap, plane-normal, phase-rebase, depth and context/state proofs; no Ribbon scene or likeness/music pass exists.
- [ ] Lab: one ribbon (bass → width, mids → twist/deformation, energy → glow) toward the concept image.
- [ ] Production: single ribbon, translucent emissive shading and bloom, then the reflective floor, then multi-ribbon,
  then particle accents, then a restrained Settings surface (gates A–H: same scene low/high, no second renderer, one
  clock, dormancy, bounded cost, legible bands, clean transparency, attractive quiet passages).

### 7.2 Reactive Liquid / Audio Melt Pool

A heavy viscous molten body in a real concrete chamber; must never read as Neon Lake water. Brief and hard gates
H01–H14: `Docs/Future_Work/Melt_Pool.md` (mock in `references/Reactive_Liquid_Audio_Melt_Pool_Concept_and_Architecture.zip`).
Uses S3D-3 (chamber), S3D-4 (surface field), S3D-5 (reflections), S3D-2 (droplets).

- [ ] Stages with stop points: static chamber + framed camera → connected viscous surface → musical pressure and peaks
  (decide whether a deformable peak mesh is needed) → material/environment interplay → droplets, Settings, acceptance.

### 7.3 Concrete Rain

Rain on a night street: music changes the pavement's water, never the street. Contract: `Docs/Future_Work/Concrete_Rain.md`
(reference `references/Low and High Reactivity Concrete Rain Comparison.png`, left low / right high). Reuses S3D-3
(street), S3D-4 (ripples), S3D-5 (wet surface, reflections), S3D-2 (impacts, crowns, droplets).

- [ ] Stages: wet surface and reflection → ripples and impact rings → splash crowns/droplets → music mapping (density,
  impact energy, ripple complexity, reflection disturbance) → scene assembly and acceptance against the reference.

### 7.4 Usu Moonscape (eventual)

Long-horizon character/world vertical: `Docs/Future_Work/Usu_Moonscape.md` (Blender work:
`Docs/Future_Work/Usu_Blender_Work.md`). Needs the character/world foundations S19–S27 listed there (asset bake,
skinning, animation graph, secondary motion, felt/fuzz, world-view projection, sphere world/starscape) plus S3D-6.
Not admitted until those foundations are proven; the static silhouette approval stays a separate hard gate.

## Operator execution and evidence rules

Use direct-copy, single-line PowerShell commands with explicit `.venv\Scripts\python.exe` for the operator. Keep
details and evidence at their focused owner, this checklist actionable, and `Index.md` / `Spec.md` navigation current.
No memory updates without an explicit request.
