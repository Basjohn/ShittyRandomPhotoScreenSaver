# SRPSS | Current Plan

Live, ordered work only. `[ ]` work remains; `[~]` a candidate exists but is unaccepted (awaiting validation, never an
implicit pass). When an item lands, delete it: completed work lives in source control and its durable contract in
`Spec.md` / `Docs/` (Reference, Architecture, Guardrails, Guides); rejected mechanisms in `Docs/Historical_Bugs/`. This
is not a changelog. Deferred, unadmitted ideas live in `Future_Work.md`.

## 0. Order, scope and rules

**Work strictly in this order:**

1. **§2 Everything else before the next mode**: fixes, then Settings/UX, then feature work, then release media (§3).
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

- [ ] **EB28-0 — Establish execution baselines:** preserve the current basic-rectangle render and resolved input
  snapshots; finalize bounded procedural advection and explicit ray-value migration while preserving authored presets.
- [ ] **EB28-1 — Drift:** move existing controls into Drift, add per-consumer quiet/loud gains
  in `[-1,+2]` with existing direct coupling normalized to1 and new coupling default0, prioritizing free microbubbles.
  Prove existing/forming/fused identities, signed endpoints, audio rise/release and CPU/GPU field agreement.
  Direct large/small/fused gains and the bucket are implemented with focused logical/spec checks; finish bounded
  procedural material paths and wake-water consumers, then recorded/offscreen evidence before acceptance.
- [~] **EB28-2 — Stream — combined capture gate remains:** ordinary/forming/fused transport now receives the shared
  stream at1x, independent of radius. Recorded P8 no-contact measurements confirm both classes at1x; inspect the
  wider passage/contact/pixel matrix under EB28-V before final acceptance.
- [~] **EB28-3 — Framed viewport — combined/native gate remains:** edge resize now uses a reference-window
  aperture with the actual pixel aspect, authored FOV/eye unchanged; uniform scaling retains prior behavior. Neon
  terrain/events/floor use the fixed basic-rectangle world. Recorded before/after basic-rectangle and seven-extent
  captures pass; finish chrome/DPR/optical/native resize checks under EB28-V.
- [~] **EB28-4 — Pause/resume visibility — combined capture gate remains:** logical free-chain attack is isolated
  from shared audio/motion and retains the existing release; focused repeated-toggle, recorded production replay and
  renderer-uniform checks pass. Complete dense temporal/layer comparisons under EB28-V before final acceptance.
- [~] **EB28-5 — Reliable rays — combined temporal gate remains:** held absolute energy replaces the adaptive
  positive-difference lift; strength endpoints are literal, Modulation0 holds the upper strength and Shimmer is
  independent. Schema13 migrates old cosmetic Flicker values before defaults/overlays. Focused and frozen recorded
  pixel comparisons pass; complete held/dip/resume motion and shaft-buffer traces under EB28-V.
- [ ] **EB28-V — Combined behavioral proof:** use production recorded replay and offscreen renders for all five
  tasks, including P8, representative other settings, BEAM/SCENE, both light types and negative/zero/max controls.
  Repair stale probe preset1–7 guards through canonical enumeration before relying on them for P8.
- [ ] **EB28-P — Performance only after EB28-1…5/V pass:** audit CPU/GPU waste, churn and conservative
  occlusion/culling opportunities; prove no fidelity loss with matched recorded inputs, cameras and full optical passes.

### 2B. Settings and UI (in this order)

- [~] **4C — Shared Settings UX audit — awaiting operator review:**
  - [~] **Conditional/nested Settings audit — awaiting normal operator use:** source review, focused round-trips,
    mode disable/rebuild condition checks and native changed-page rendering pass. Exercise mixed-page edits and
    disclosures in normal use; report any irrelevant rows, clipped controls or lost latent values. Keep categorical
    direction choices intact and use shared visual controls only where their stored meaning fits.
  - [~] **Bubble two-node gradient prototype — awaiting operator look:** inspect independent Dark/Light endpoints,
    direction, blend span and shifted placement in `tools/labs/bubble_gradient_mapper_lab.py`; control capture:
    `tmp/bubble_gradient_mapper/prototype.png`, sibling wide/narrow/shifted fixtures. Geometry, gesture and driver pixel
    compatibility pass. Keep current enums, presets and production appearance until interaction/migration review.
  - [~] **EB lab reference associations — awaiting target confirmation:** reconcile the recipe/reference registry
    with renamed `*Goal.png` targets before a full comparison run.
    Six old `ExBubble*.png` originals and their README/manifest paths are absent; `--only=ExBubble2` remains valid.
    Do not invent mappings or substitute archived lab output for operator targets. Missing references fail before GL.
  - [~] **Advanced hierarchy — awaiting operator look:** large Advanced header contains Technical and EB Camera;
    native real-dialog reopen/retirement and legacy-path checks pass. Inspect the nested path at operator DPI/theme;
    capture: `tmp/pytest_advanced_render/test_visualizer_technical_path0/advanced_technical.png`.
- [~] **Settings undo — awaiting your use:** Ctrl+Z / Ctrl+Y over the session's slider and visual-editor edits
  (contract: `Docs/Contracts.md` "Settings undo"). Check it in normal use across pages; extend to any control found
  missing.
- [~] **Display Settings capacity — awaiting physical hotplug validation:** current-screen rows have no fixed cap;
  focused six-screen/disconnect/reorder/zero-screen and retirement checks preserve canonical selections/bindings.
  Check Settings remains coherent during actual disconnect/return and explicit reauthoring; hidden form evidence:
  `tmp/pytest_display_rows_final/test_display_ui_rows_follow_to0/six_display_rows.png`.
- [~] **R38 hover display-transfer glyphs — awaiting physical topology use:** source/model/lifecycle and native Quick
  hit/tooltip/fade checks pass. Exercise Previous/Next Display on actual mixed-DPI screens, Save/Cancel/Undo and monitor
  unplug/return. Eligibility and transfer reuse CUSTOM; Hide Controls remains Edit-only. Native control capture:
  `tmp/pytest_hover_transfer_native_final/test_transfer_glyphs_are_absen0/transfer_glyphs.png`.


- [~] **Visualizer Preset Repair Foundry — implementation candidate; operator acceptance pending** (next quick
  Settings/tooling job after the currently in-progress §2B items, before §2C feature work):
  - [~] Present in Foundry chrome/theming, with a single-mode catalogue, two-select Swap Presets, actionable status
    and one-click paired Undo. Verify actual native control layout at operator DPI and a few normal swaps; no GUI
    styling tests for this disposable tool.
  - [~] Reindex from the **numeric filename slots**, never stale embedded `preset_index`; update index/name metadata
    only, preserve all operator-authored visualizer settings, and prevent silent collision/overwrite. Exercise a
    manually renamed order, gaps, duplicate slots and repeated reindex operations with independent fixture presets.
  - [~] Existing-manifest regeneration button is conditional on `presets/visualizer_modes_manifest.json` existing;
    absence means no-op, not recreation. Check Repair, Repair All, Reindex, Swap and Undo for current-shipped parity,
    without treating any manifest as an authority for authored files or forcing preset overwrites.
- [ ] **Retire the visualizer preset manifest and redundant bookkeeping** (same batch, immediately after the
  Preset Repair Foundry is visually/operator accepted; no manifest removal in the tool-only handoff):
  - [ ] Map every reader/writer of `presets/visualizer_modes_manifest.json`, the release/Media Center copy and
    `managed_curated_files`: frozen SCR/Diagnostic/MC startup, onefile bootstrap, installer, Build Foundry,
    import/export, source-vs-release auditing and preset repair. Confirm direct enumerations are authoritative.
  - [ ] **Separate deletion scrutiny before sign-off:** audit frozen `prune_duplicate_curated_preset_slots` using
    file `mtime` as a winner and `sync_curated_preset_tree` deleting entries not present in the manifest. Demonstrate
    how both interact with manually renamed/moved authored presets, imported directories and simultaneous slots.
    Remove destructive heuristics or require explicit replacement ownership before allowing deletion; never
    silently select a newer timestamp over the user's intent. Use isolated test-owned fixtures.
  - [ ] Replace manifest enumeration with actual directory scanning for load, mirror and export. Explicit replacement
    may prune only obsolete **managed target copies** after the authoritative source has been snapshotted and
    validated; missing or invalid source must never delete a target. Preserve shipped-versus-operator-owned
    separation, exact filename slots, Custom, and onefile/ProgramData precedence.
  - [ ] Keep strict read-only source/release content-parity checks (filenames **and bytes**) without a stored manifest;
    audit installer clean-replace, frozen extraction, Media Center and import/export for stale-file handling and
    accidental reintroduction of removed presets. Remove obsolete regeneration hooks and the Foundry button or
    leave it visibly disabled/no-op once no manifest exists; do not recreate the artifact.
  - [ ] Remove the manifest files and obsolete code/contracts/tests only after the replacement flow and rollback
    safety pass. Validate source and frozen semantics with minimal schema/SSOT/integrity tests, never asserted mutable
    preset values, GUI styling tests, or large suites. Keep operator-authored EB and all other current preset JSON
    untouched; preserve every existing task/status in this plan.

### 2C. Feature work

- [~] **SC4 — Wallpaper pools — awaiting normal runtime image use:** inspect subject/query relevance and usable yield
  at actual display sizes, initial empty/cache-warm runs, Settings return and normal background top-ups. Native dark/light
  selector controls and focused source/resume/retirement gates pass; image relevance is not established by streamed
  header dimensions. Excluded providers require new sanctioned access evidence. Detailed contracts:
  `Docs/Reference/Wallpaper_Pool_Selection.md`.
- [~] **Reddit's data-root cache:** the first normal saver run with Reddit on should create `SRPSS/cache/reddit` and
  refetch once per member (paced); check its log then.

## 3. Release media and bounded source cleanup (at a stable checkpoint)

`Docs/Reference/Release_Media.md` owns inputs, encoding and manifest policy (UsuScene1–4 originals, 480 px / 24 fps
transition loops, no arbitrary size cap; outputs stay outside runtime QRCs).

- [ ] **RM1 Catalogue reconciliation:** compare registry variants with manifest/source hashes; generate only missing or
  stale entries (keep the Warp Dissolve, Particle and Blinds Flat exclusions unless changed); review each new WebP.
- [ ] **RM2 Visualizer showcases:** capture registered modes' curated presets with schema-2 real-music clips through
  production replay/capture (Extruded Bubble is now eligible); fail loudly on missing inputs.
- [ ] **RM3 Catalogue proof:** motion/endpoints, loop seams, dimensions, metadata; unchanged inputs skip, changed inputs
  regenerate, mixed-revision captures are rejected.
- [ ] **SC1 Retire the unused root `transitions.direction`:** confirm no callers, then forward-strip it (changes the
  operator's defaults: needs explicit authorization); prove import/merge/save cannot resurrect it.
- [ ] **SC2 Blinds Flat endpoint discrepancy:** reproduce at the exact production endpoint before deciding capture vs
  rendering.

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

- [ ] **S3D-1 Ribbon / strip primitive:** generalize what Extruded Bubble's wakes proved (`extruded_bubble_wake.py`, the
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
