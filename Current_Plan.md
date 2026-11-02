# SRPSS | Current Plan

Live, ordered work only. `[ ]` work remains; `[~]` a candidate exists but is unaccepted (awaiting validation, never an
implicit pass). When an item lands, delete it: completed work lives in source control and its durable contract in
`Spec.md` / `Docs/` (Reference, Architecture, Guardrails, Guides); rejected mechanisms in `Docs/Historical_Bugs/`. This
is not a changelog. Deferred, unadmitted ideas live in `Future_Work.md`.

## 0. Order, scope and rules

**Work strictly in this order:**

1. **§6 Shared 3D architecture**: build reusable 3D primitives, each proven on its own harness.
2. **§7 Visualizer modes**, one at a time: **Waveform Ribbon → Reactive Liquid / Melt Pool → Concrete Rain →
   Usu Moonscape**. Each is built lab-first (§7.0).
3. **§8 Later accepted-mode reactivity polish**, only after the §7 sequence unless the operator explicitly pulls one
   item forward for a concrete regression.

**Accepted baseline (not live work):** original Bubble, Extruded Bubble, Neon Lake, Oscilloscope,
Spectrum/Rainbow Ghost, Sphere, source routing, transitions and Foundry launch buttons. Reopen an accepted
area only for a concrete new defect; deferred or unadmitted work belongs in `Future_Work.md`. Historical recovery
IDs, completed gates and rejected mechanisms belong in source control or their focused historical/investigation docs,
not in this working plan.

**Rules:** one Settings/capability/CUSTOM/render/lifecycle owner and the sole Visualizer logical clock. No new
floor, capture/DSP, renderer-side simulation, timers/polling or camera-following replacement populations. Preserve
authored presets (mutable, never test-pinned), BTF, accepted timings, parallel work and strict retirement barriers.
CLI/sidecars, never environment-variable configuration. Smallest meaningful focused test per change; the isolated
chunked suite only at milestones; no build/installer unless requested. Visual work is judged on rendered pixels against
its target (`Docs/Guides/Visualizer_Visual_Tuning.md`), and any claim of "fixed" needs the failure reproduced first.

## 5. Watchlist (observe during normal use; reopen only on evidence)

- [ ] **Authored preset completeness debt (2 Nov focused gate):** 18 existing Bubble presets omit
  `bubble_gradient_endpoints`; EB presets 2–8 omit camera projection and eight drift/ray fields.
  Their parsed payloads and pre-existing spec keys match HEAD. Preserve operator-authored values; reconcile this
  separately before treating the cross-mode completeness check as green. Waveform's two new presets are complete.

- [ ] **Display Settings capacity (physical hotplug):** on a real monitor disconnect/return or explicit reauthoring,
  Settings' current-screen rows and selections/bindings stay coherent (focused checks pass; hidden form evidence
  `tmp/pytest_ux30_display/test_display_ui_rows_follow_to0/six_display_rows.png`).
- [ ] **R38 hover display-transfer glyphs (physical topology):** watch glyph hit/tooltip/fade and transfer on
  unequal-DPI screens and monitor unplug/return (equal-DPR pair passes; `tmp/ux30_actual_displays/receipt.json`).
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
- [ ] **15 s usage-sample hitch (unexplained, not reproduced):** 31 Oct 19:28-19:33 MC run, a 95-121 ms freeze of the
  GUI, render and logical threads at every `--usage` sample (20 in 5 min, `gui_stall_stacks.log` and frame trace
  agree). Each sample took ~95 ms because the sampled tree held 7 processes / 233 threads (normal 3 / ~55, ~16-24 ms);
  the four extra descendants used the GPU (counters 17 → 70), existed from the first sample and are unidentified.
  The next MC run (19:47) and an invisible live check on current code were normal. On recurrence the sampler now
  logs `[USAGE] topology added ... name= parent= threads=` for every process entering the tree: identify them, then
  decide whether the sampler must exclude/outsource them. Not the Extruded Bubble chain fix (no processes, tick unchanged).
- [ ] **Cross-display Media shortcuts** delivered once on the other display, when exercised.
- [ ] **Music recorder** 60-second clip, signal/history, cancel and mixed-DPR UI, when recording is needed.
- [ ] **Project Python startup warning:** `.venv\Scripts\python.exe -c "pass"` reports `Failed to find real location`
  for its configured base Python 3.14 executable, although that path exists and Python runs. Inspect installation/path
  resolution and access before repairing the venv; preserve dependency isolation and avoid environment-variable fixes.
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

- [ ] **S3D-1 Ribbon / strip primitive:** finish the reusable camera-facing width variant, shared defocus integration,
  lifecycle/admission proof and bounded cost around the existing history/ring/oriented-strip substrate. Preserve a bounded
  history SSBO, centripetal Catmull-Rom placement by continuous index, OIT translucency, multi-ribbon support and fixed
  maximum history. *Consumers: Waveform Ribbon; trails anywhere.*
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
  that collapses under camera motion. *Consumers: Waveform Ribbon floor (next: §7.1), Melt Pool, Concrete Rain.*
- [ ] **S3D-6 Shared shadows (G2 / S25):** one fitted directional depth map, bounded soft PCF/bias, caster/receiver
  admission, resize/teardown/dormancy and tier cost on a real test scene (also Usu's S25; not a revival of the rejected
  Extruded cast shadows).
- [ ] **S3D-7 Reduced-resolution volumes, then lightning (G5):** prove the bounded static fog slice required by Waveform
  Ribbon first, with no audio reactivity. Then add bounded procedural bolt geometry/light and fog/smoke volumes with
  advection/reprojection and no permanent extra targets or separate cadence. *Consumers: chamber/street atmosphere.*

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
5. **Same-scene low/high proof, measured cost, dormancy and retirement** before calling any stage done, including the
   live-shape check under the calibrated game load (`tools/visualizer_live_check.py --load game60`, budgets in
   `Docs/Guides/Visualizer_Change_Checklist.md` 1C); the operator gives final sign-off.

### 7.1 Waveform Ribbon (next)

**Operator native rejection (2 Nov): production candidate is unaccepted.** Close these in order with recorded/live
audio and actual native motion, retaining the C-primary/A-twist grammar:

- [ ] Repair live audio admission; prove nonzero per-band/passage/onset inputs and consumed accents in playback.
  Restore immediate musical kick/punch, changing body flow/torsion, localized dense highlights/colour, sparks and strands.
- [ ] Preserve subtle low-energy idle motion and the same scene across first idle→play; no priming blackout or scene reset.
- [ ] Complete actual in-scene 3D navigation/Edit scaffolding to the EB feature contract, including both projections.
  A renderer capable of a camera matrix is insufficient if the production interaction cannot reach it.
  The user-authorized 6.1 Sol High camera slice must enforce an above-floor eye, keep floor below eye and waveform,
  and make the visible waveform continuous/infinite with no exposed head/tail at admitted angles. Preserve shared
  camera/input ownership; do not shift actors/populations with the eye or hide failures by removing projections.
  **Grounded camera direction (operator):** stable eye height above the floor; approach the waveform and orbit left/right,
  always retaining it in view. Constrain navigation to a visually credible region; no free-flight escape into ugly areas.
- [ ] Resolve side sheets fighting the fog, and smooth the fog body/fringe grain into a smoothly lit rim in motion.
  Operator orbit screenshots show an extended bright horizontal shelf and detached noisy patches; reject camera-
  dependent clearance distortion and remote luminous boundaries. Preserve fixed-world atmosphere and light it by
  distance to the actual ribbons, including turned views. Navigation repair remains below musical response in priority.
- [ ] Prove floor reflection remains live and authorable; brighten/tune rim light and glow through their actual controls.
  Reflection-column aesthetics remain secondary. Compare both presets in person after automated gates, not before.
- [ ] **Viewport regression (operator):** shrunken wide viewport restores reflection and changes apparent reaction.
  Reproduce the identical immutable audio/body/camera snapshot at canonical, wide, tall and large sizes; separate
  aperture/projection effects from floor reflection/specular resolution-cap branches. Correct the owning pass or
  geometry boundary; never compensate with audio gain. All prior native-rejection items remain equally open.
- [ ] **Dynamic Floor A/B:** operator observes better response with it on. Trace the full configured PCM/DSP→raw
  body bands and musical passage/onset chain against guide §13A/13C, not a getter stub. Establish lively floor-OFF
  output with pooled real scales and unclipped contrast; preserve accepted Bubble/EB DSP/behaviour.
  Recorded PCM now proves identical full body/birth packets and typed events with floor off/on on four clips.
  The descriptor-owned raw-reference policy uses the existing bus/FFT, clears old numerical-domain context on policy
  changes and fences compute/replay state. Preserve accepted modes and validate audible punch/phrase response natively;
  source parity and unclipped range distributions alone do not establish the operator's musical standard.
- [ ] **Accent placement/reward:** with fog off the operator sees only a few specks in one spot. Verify actual
  distributed rim births, independent particle glow and rim-rooted strands over real quiet/ordinary/hot passages.
  A nonzero cohort serial or isolated screenshot is insufficient visible-accent acceptance.
- [ ] **Awaiting later UX pass — UI fully rejected:** defer the complete usability/UX redesign until credible visual
  results exist. Current editor/control plumbing and tests do not establish an accepted Settings experience.

Chosen first: the smallest contained scene and the first consumer of S3D-1/S3D-2/S3D-5. Brief and hard gates:
`Docs/Future_Work/Waveform_Ribbon.md`. The detailed working checklist and visual target custody live in
`Docs/Reference/Waveform_Ribbon_Lab_Plan.md`; reference packages under `references/` are local/operator-owned and are
intentionally absent from normal GODZIPs.

The scene is world-first through the shared framed camera (Orthographic default): wet reflective concrete floor,
waveform and strong thick shaped mist, with no visible horizon/sky/floor edge. The waveform clears and softly lights
the mist. Preset/control migration and recorded-audio calibration come only after the lab look is credible.

- [~] **WR-07/08 production candidate — finish admission:** C elastic bending/torsion is primary; combine A's accumulated
  twisting, localized highest-power colour shifts and independently controllable reactive whole-waveform rotation
  (axial roll like a skewer; fast strong attack, slow decay; integrate speed into continuous angle). Preserve constant history flow, smooth
  curves, particles/free strands and fog repelled by the actual deformed/rotated waveform. Use the shared scene,
  sole logical clock, immutable publication and lazy retained renderer; Terra audits each slice.
- [~] **Full controls/editors and two initial presets — finish native/range audits:** primary/alternate examples now have
  candidate Preset 1/2 with the
  selected hybrid, shared framed 3D camera/navigation, technical profile, preset/Custom and Edit/Arrange feature set.
  Expose bend/torsion/stretch/twist/rotation and accent ranges, source/curve visual tuning, ribbon/gradient editors,
  and floor reflectivity/tint/brightness. Every reactive range needs actual quiet/peak consumer proof for both handles;
  retain mutable authored presets and prove Save/Cancel/Restore and runtime source reachability.
- [ ] **Framing, timing and acceptance:** prove hidden ends/history bounds and body/head-to-visible delay across admitted
  sizes/camera poses; replay real quiet/middle/hot/silence/hot-start windows with unshifted audio, inspect lab/production
  parity and audit range headroom. Close shared lifecycle/cost/dormancy gates and run
  `tools/visualizer_live_check.py --mode waveform_ribbon --load game60` before WR-09 acceptance. Operator visual/native
  judgement remains explicit where automation cannot close it. Ground volume banks stay zero; floor distance mist
  remains separate. Floor-column polish is not a migration blocker.
- [ ] **Loaded render budget:** the native Quick path now presents after fixing Qt-owned context-wrapper lifetime,
  but the first loaded smoke measurement exceeded the 8 ms render budget (~14 ms). Profile the real scene stages,
  remove repeated preparation/upload/state work at its owner, then rerun both presets in isolation under game60;
  do not lower artistic reaction strength or treat offline GPU medians as live acceptance.
  First measured owners: render-side envelope ~3.9 ms and repeated ribbon passes ~3.5 ms. Share one fenced packet
  lease across the scene's passes (rebind after intervening consumers), then migrate envelope/blur/edge-limit
  reduction to bounded GPU work over that same packet if needed. Keep the CPU reduction as a test oracle, prohibit
  readback/duplicate live CPU preparation, preserve floor/grade/clearance consumers and prove per-row/pixel parity.

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

## 8. Later accepted-mode reactivity polish

Do not pull these ahead of the §7 mode sequence unless the operator explicitly reprioritizes them. They are admitted
follow-up work on the accepted original Bubble, not a reason to reopen unrelated Bubble behavior.

- [ ] **Original Bubble drift intensity range:** normal Bubble drift works, but its visible drift strength is too similar
  at idle and under heavy/intense sound despite the authored settings. Trace signal → reactive target → smoothing → final
  displacement/speed before tuning. Preserve the accepted idle drift and cadence, then make the configured high-react
  end materially stronger under sustained loud passages and strong transients without introducing jumps, judder or a
  separate clock. Prove quiet/mid/hot synthetic fixtures plus recorded real-music passages and compare the actual
  low-to-high drift range, not only a single loud frame.
- [ ] **Original Bubble scalar-to-range control audit:** inventory Bubble sliders whose authored value is really a
  low-react/high-react envelope and convert only semantically appropriate controls to range sliders. Wire the low and
  high handles to the canonical reactivity signal rather than treating the range as cosmetic UI. For authored presets
  **1-8 only**, seed both ends of every migrated range from that preset's existing scalar value so the migration is
  byte-identical to its current output before the operator widens a range; presets beyond 8 are experimental and do not
  constrain migration. Capture the pre-change P1-P8 effective values and fixture frames as the regression oracle, then
  prove Save/Cancel/Restore, preset switching, CUSTOM editing and low/high interpolation without changing unrelated
  Bubble reactivity semantics.

## Operator execution and evidence rules

Use direct-copy, single-line PowerShell commands with explicit `.venv\Scripts\python.exe` for the operator. Keep
details and evidence at their focused owner, this checklist actionable, and `Index.md` / `Spec.md` navigation current.
No memory updates without an explicit request.
