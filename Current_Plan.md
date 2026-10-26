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

### 2B. Settings and UI (in this order)

- [~] **Light-theme legibility:** finish the explicit shared light-theme text-shadow switch and slightly heavier
  typography across Settings/runtime. Preserve dark-theme pixels, authored shadow parameters, backgrounds and theme
  schemas; derive admission from semantic roles. Verify native Glass/Acrylic and translucent runtime cards before
  landing; probes need external deadlines and completed production retirement.

- [ ] **4C — Shared Settings UX audit:**
  - [ ] Audit every Visualizer/Transition/widget page for the shared Angle/Direction, Range and Triangle controls,
    stronger `when` conditionals and nested bucketing; keep stored meaning and keys, prove each changed body's
    round-trip and render it offscreen. No per-page owner clones. Bubble/Sphere compass enum adapters are landed;
    continue with transitions and coupled ranges; inspect the actual native forms alongside the theme pass.
  - [ ] Prototype the gradient direction mapper on original Bubble (around = direction, distance from centre =
    strength/gradualness).
  - [~] **Advanced hierarchy — awaiting operator look:** large Advanced header contains Technical and EB Camera;
    native real-dialog reopen/retirement and legacy-path checks pass. Inspect the nested path at operator DPI/theme;
    capture: `tmp/pytest_advanced_render/test_visualizer_technical_path0/advanced_technical.png`.
  - [~] General/family/mode 3D Detail views share the 3D tab's keys, editor and resolver; focused bidirectional,
    retirement and artistic-preset isolation checks pass. Inspect native layout. Per-mode AA/Bloom remains to be
    admitted through `resolve_scene_quality`, never duplicated persisted settings or a cosmetic unwired control.
- [~] **Settings undo — awaiting your use:** Ctrl+Z / Ctrl+Y over the session's slider and visual-editor edits
  (contract: `Docs/Contracts.md` "Settings undo"). Check it in normal use across pages; extend to any control found
  missing.
- [~] **Display Settings capacity — awaiting physical hotplug validation:** current-screen rows have no fixed cap;
  focused six-screen/disconnect/reorder/zero-screen and retirement checks preserve canonical selections/bindings.
  Check Settings remains coherent during actual disconnect/return and explicit reauthoring; hidden form evidence:
  `tmp/pytest_display_rows_final/test_display_ui_rows_follow_to0/six_display_rows.png`.
- [ ] **R38 transfer/topology glyph parity:** existing multi-display authority decides eligibility; Hide Controls stays
  Edit-only; no new runtime or geometry authority.

### 2C. Feature work

- [ ] **SC4 — Just Make It Work Pools** (design and gates: `Docs/Reference/Wallpaper_Pool_Selection.md`). Today the
  action replaces the feed list with four fixed entries; pool UI, provider rotation and NASA selection do not exist yet.
  - [ ] **SC4.1 Source eligibility:** bounded live probes per candidate (Wallhaven's JSON API is already the feed). One
    `Space` choice groups NASA Sun/Mars/Solar System/Universe (Solar System is several Photojournal feeds); Minitokyo stays
    experimental until anonymous original access is demonstrated; compare Konachan.net, Safebooru/Zerochan, Yande.re and
    E-Shuushuu with SFW/API caveats. A board becomes a default only after successful authorized original retrieval.
  - [ ] **SC4.2 One provider-selection authority:** a canonical typed selection of named pools (Wallhaven thematic
    searches, not its coarse General/Anime/People flags), one popup-level discovery order (Random, Latest, Popular,
    Today/Week/Month/Year) translated only where providers support it, validated query templates and a bounded number
    of feed documents per acquisition pass. Existing coordinator, backoff, pacing, cache and the engine's own shuffle stay
    the owners; no scheduler, timer or second shuffle. Prove pool=full, offline, 429, restart and zero displays.
  - [ ] **SC4.3 Shared popup and Guided Setup:** both Just Make It Work buttons open the same `Just Make It Work Pools`
    popup (Wallhaven themed checkboxes, one NASA Space checkbox, approved boards, one discovery-order selector) in the
    StyledPopup dark-glass theme; Guided Setup keeps its draft/Finish/Skip lifecycle and never overwrites custom feeds.
  - [ ] **SC4.4 Migration and acceptance:** migrate the curated NASA/Wallhaven URLs into pool identities once, never
    misclassifying custom URLs; preserve other feeds, folders, ratio and cache; test-owned configs and fake feeds.
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
- [ ] **Wallpaper RSS after runtime replacement:** `engine_lifecycle.stop(exit_app=False)` permanently sets the reused
  RSSCoordinator stop event and replacement does not restore its timer; decide resume vs rebuild after auditing owners.
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
   free knobs and no Settings/preset plumbing. Iterate on rendered stills (mock | lab sheets) until it is close.
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
