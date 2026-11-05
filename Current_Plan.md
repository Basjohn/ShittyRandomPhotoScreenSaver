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
3. **§8 Accepted-mode follow-ups**: the brief Bubble performance-parity check is operator-admitted now.
4. **§9 Studio for every visualizer** (operator, 5 Nov): replaces the deferred Bubble scalar-to-range/UX sweep.

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
- [ ] **Suite reds since the 24 Oct 737/737 baseline (5 Nov isolated full run, identical at a74dfaa0, i.e. before
  the 5 Nov work):** 40 files, all reproducible alone. Largest: `test_visualizer_preset_completeness` (13: Bubble and
  Extruded Bubble presets miss the 5.1.3 microbubble/gradient/drift/projection controls — repair-fill them),
  `test_waveform_infinite_floor` (9: orthographic depth/actor-clip/floor-reflection expectations vs the camera
  helper), `test_qtquick_custom_layout_owner` (8: its Waveform cases replay without PCM reanalysis, which raw musical replay now requires), `test_framed_viewport_aperture` (4: EB/Shockwave custom-side
  gestures), `test_qtquick_visualizer_all_modes` (4), `test_visualizer_logical_hook_dormancy` (4),
  `test_bubble_reactivity` (3: swish group drift sign/activity — Bubble is BTF-binding, never retune to pass),
  `test_visualizer_plain_orbit` (native crash), `test_visualizer_view_orbit` (Shockwave planar vs freeform; Waveform
  full-circle turn), `test_defaults_schema_authority` (Waveform presets carry `mode` only at top level), plus 1-3
  failures in bubble_ambient_glow, build_runner, feed_f2 (RSS log redaction), frame_trace, framed_scene_input,
  input_gain, monitor_replay_admission, neon_scene_materials, onboarding_preview_assets/selection,
  qt611_shader_admission, qtquick_build_packaging/ordinary_widget_host/visualizer_bubble/all_five_owner_chain/
  fade_authority/technical_sync_contract, release_media, run_matrix_harness, settings_theme_lifetime_contract,
  startup_source_onboarding_resume, test_suite_durability, transition_distribution, visualizer_custom_geometry_profiles,
  lazy_preset_collection, mode_dormancy, mode_enable_resolver, presets, settings_plumbing,
  widget_theme_no_material_contract. Reconcile per assertion (current architecture authoritative; never bless
  unexplained drift); fix product defects found on the way.
- [ ] **Linux branch `claude/eager-carson-5da6ge` — held, not merged (5 Nov):** merges cleanly and leaves Windows
  unchanged (804/848 files green, every other red pre-existing), but it is unfinished: `core/media/pulse_volume.py`
  starts raw `threading.Thread`s (`tests/unit/test_policy_compliance.py` fails on every OS), and its own docs promise
  that `tests/test_linux_*.py` are never collected off Linux with `tests/test_platform_selection.py` pinning Windows
  owners, while Linux-only cases still sit in shared files that fail on Windows (`test_mpris_controller` x2,
  `test_platform_paths` x1) and neither the exclusion nor that test exists. Merge once those land on the branch.
- [ ] **Cross-display Media shortcuts** delivered once on the other display, when exercised.
- [ ] **Music recorder** 60-second clip, signal/history, cancel and mixed-DPR UI, when recording is needed.
- [ ] **Helper breadcrumb diagnostics unavailable:** current native MC evidence logs no access to
  `C:\ProgramData\SRPSS\logs\scr_helper.log`. Inspect the helper/log-path authority before relying on that
  diagnostic route; do not hide it behind a silent local fallback. Separate from Waveform rendering.
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

**Live rejection checklist - Awaiting native validation/operator judgement (2 Nov).** This is the single live
list of reported failures, proposed corrections and required evidence (updated 3 Nov). Tests establish mechanisms, not visual acceptance.
Work first on body/audio/accents, then grounded camera/viewport and replacement atmosphere. Binding references:
`Docs/Guides/Visualizer_Reactivity_Authoring.md` sections 13A-13C; control/design ownership in
`Docs/Reference/Waveform_Ribbon_Migration_Plan.md`; motion targets and recorded bake-off in
`Docs/Reference/Waveform_Ribbon_Lab_Plan.md` section 5.1. Keep C-primary elastic response and A's accumulated twisting.

**Operator-selected recovery baseline (3 Nov):**
`Docs/Reference/Images/Waveform_Ribbon_Material_Baseline_20261103.png` and its `.capture.json` preserve the exact
chosen image/settings/source. Use this material direction; do not darken the background or lower the floor's colour
level. Floor brightness is provisionally approved, not the entire floor/atmosphere. Remaining lumps and reactive
detail still need improvement. Baseline settings are applied to Preset 3; retain this reference before further work.

- [~] **Four-ribbon maximum and Preset 3 — Awaiting Validation:** the candidate now admits FOUR cards across
  authoring/runtime/clearance/accent/range paths, preserving Presets 1/2's three active identities. Validate Preset 3 against
  `references/Preset3Goal1.png` and `references/Preset3ReactivityGoalExample.png`: teal/orange contrast, readable
  lattice/twist/strands/particles, continuous wet textured floor, and the large quiet-to-peak geometric change shown.
  The explicit operator maximum overrides the first board's decorative count label; use four for Preset 3's paired
  target. Native low/high/recorded captures must reach that range without pinning or swapping scene/camera identity.
  Four-card forward migration and a first Teal/Ember Preset 3 are implemented; preserve original three-card values
  and count in old state. The recorded draft still needs visual correction: white/rope-like overlaps, repeated
  continuation, weak/dark atmosphere and a poor floor/contact strip remain rejected. Do not equate source tests,
  particle/root counts or larger amplitude with reference fidelity.
- [~] **Reaction: travelling energy pulse + four Reaction Modes (5 Nov) — awaiting operator eyes/ears:** the R1/R2
  elastic motion was rejected as fundamentally wrong (sideways bursts from the retired axial stretch; standing bends).
  Beats launch swells that travel along the waveform and amplify its OWN crests/troughs through a broad envelope
  whose slope is capped so a swell never bends a curve inward; points slide along their own curve (shape-preserving,
  rate-limited); a narrower travelling light/colour/saturation band and gathered particles show where the energy is.
  Modes: Travelling Pulse (default), Frozen Past, Whole Swell, Group Wave; flow-rule and twitch tests for every mode.
  Dense music (5 Nov probe, ragdoll loud end): the light reads as one coherent front travelling at the authored speed
  with no standing glow at the emitter; a packetised release was measured (emitter share .41 -> .40) and rejected as
  machinery without a visible gain. 8 s strips (5 Nov, `modes_long/`): Frozen Past is distinct (held crests stay
  raised when the passage quiets); Group Wave was indistinguishable, so a swell now arrives as a SET (envelope 3.5
  carrier wavelengths, light across the set, stronger forward lean) and reviewed frame by frame. Audit doc decisions 7+; evidence `.artifacts/evidence/waveform_ribbon/
  studio_20261105/modes/`.
- [~] **Particles (5 Nov candidate):** crest-weighted, distributed births in each ribbon's colour, visible
  >=1 px cores with soft halos, gentle fade; swells gather particles (Pulse Particles). Hot passages hold ~3.4x quiet.
  Pulse births only fill the cohort headroom left after the authored Spark Count, so they never mask it.
  Open: still sparser than the high-react reference (admission-limited).
- [~] **Strands: rare, 3-5 seconds TOTAL life.** Latest operator correction supersedes the proposed 30-second fade.
  Preserve the approved non-flickering look, make appearances much rarer, and use most of a configurable 3-5 second
  lifetime for a gentle tip-first fade. Reactivation restores them smoothly,
  with glow and movement/growth (retain the approximate 20% repeat extension), without abrupt respawn or pulse reset.
  Prove quiet/peak lifetime handles, tip/root fade ordering, slow decay, partial-fade reactivation and direct/reflected
  appearance. Retain birth look during travel; finite history eviction must not cut off a visible unfinished fade.
- [~] **Colour, floor and mist (5 Nov candidates):** lattice sheets (V3); wet concrete with stable soft coloured
  reflection mass (no horizon line, no flicker-prone streaks; operator prefers smeared colour to streaks); one bounded
  night medium with a slight local ribbon tint (strong Local Light can no longer wash the frame). 5 Nov vs `Preset3Goal1`:
  the grey base was the far concrete level and surface brightness, and Reflection Colour was not the hue drift (lower
  read pastel). All presets darker far surface (.2) and brightness (1.2); P3 stronger, wider-smeared reflection
  masses (lit saturation .60 vs reference .59, current .54). Consecutive frames smooth (flicker .0068 -> .0105, from
  brighter moving masses, no column popping); evidence `studio_20261105/floor4/`.
- [ ] **Dense highlights, moving colour and rim glow:** playback still lacks rewarded high-energy density and glow.
  Verify local crest/high-power colour, bright tunable rim/glow and denser highlights against actual music, including
  quiet/loud differences. Consumer reachability does not establish visible strength. Keep both range handles effective.
- [ ] **Idle and first-play blackout:** keep subtle low-energy body motion and the same ready scene on first play;
  no blackout, re-priming or scene reset. Test cold playing-before-start, silence, pause/resume and source changes.
  Idle must not emit fake musical hits or particles.
- [ ] **Dynamic Floor independence:** the operator found floor ON more responsive. Controlled full PCM now proves
  identical body/birth packets and typed events OFF/ON on four clips. Preserve the existing FFT/bus raw-reference
  policy, mode-switch/reset and stale-compute fences, plus accepted Bubble/EB behavior. Prove lively OFF response by
  ear/eye against the guide's standard; raw parity alone does not establish musical response.
- [ ] **Grounded camera, near-flat tilt and infinite view:** stable eye height above the floor, approach/retreat and
  bounded left/right orbit, waveform always in view and no escape into ugly areas. Admit a genuinely near-flat tilt
  with visible floor in BOTH projections. Keep eye/basis, navigation, editor markers and saved pose under the shared
  owner; preserve continuous/infinite body with no exposed ends and complete Edit scaffolding. Native geometry and
  persistence tests alone cannot establish feel or beauty across moving audio, view and viewport extremes. Reproduce
  the new cut-to-black at one end and staggered entry at the opposite end; validate the camera-owned signed
  Orthographic raster fit against recorded wide/angled playback. The old positive reference-plane slab cut visible
  continuation before the card edge; Perspective and other modes retain their positive clip contract.
  **Current visual route:** operator delegates the choice; use a restrained long-lens Perspective primary view,
  calibrated with a farther physical eye and narrow lens together. Keep Orthographic optional. Preserve stable height,
  bounded orbit and actual camera movement; no camera-dependent actor density or audio compensation. Judge colours,
  restrained reactive twisting, floor material and full-scene mist together against the references before acceptance.
- [ ] **Floor coverage, collision, reflection and viewport changes:** after the strand slice, draw ground all the
  way through the foreground and beyond the waveform into heavy dark mist that GENTLY thickens until no horizon
  line is visible. A strip of reflections over black is rejected. **Awaiting native visual validation:** the floor now
  intersects the same physical camera's pixel lines with the infinite world plane; signed Orthographic intersections
  cover foreground/far ground while actor clipping remains unchanged. Focused native tests cover complete coverage,
  world coordinates, floor occlusion and capped reflection. Finish the unified atmosphere before visual judgment. Keep actors and
  physical floor contact correct, with smooth waveform collision rather than clipping. Compare identical snapshots at
  canonical/wide/tall/large sizes and both projections; inspect reflection normalization/filtering separately. Preserve
  live reflectivity/tint/brightness and the shared resize contract; no audio-gain compensation. Columns remain secondary.
  **Additional explicit rejection:** material outside the core reflection is practically invisible. Validate readable
  dim texture across the foreground with reflection and atmosphere both OFF, then under the unified night medium;
  increasing reflection alone cannot satisfy this. Current candidate restores filtered concrete/roughness and ambient light.
- [~] **Unified atmosphere (5 Nov candidate):** replacement medium in place (old banks/fringe/floor haze removed);
  darker bounded haze with capped local tint; P3 density 0.06-0.09, P1/P2 0.055-0.075. Open: retained moving-body
  wake and the loaded fog cost gate (P2/game60 render median was over budget) still need measurement.
- [ ] **Waveform Studio (replaces the rejected builder UI):** in-process, reusable (mode registry + switcher;
  test-only second mode) Qt Quick Studio per the operator's design pack; Settings > Custom opens it; production
  framing on the real card; camera navigation; theme-token chrome; full registry coverage; Energy Pulse/Reaction Mode
  first in Reactivity; target-first response tuner. Open: Stage C/D instruments (scene handles, gradient strips,
  lifecycle timelines, mist/floor cards), icon polish and mock parity; real-window checks on hardware (visible window,
  native Settings hide/restore, exit timing via `[STUDIO] retire` logs, per-monitor DPI). Remove the old builder body
  once the Studio passes operator acceptance.
- [ ] **Live performance and truthful evidence:** run all three presets under matched recorded PCM/game60 and admitted
  camera extremes. Verify ACTUAL applied configuration, audible input and rendered features before interpreting
  timings. Profile logical preparation, birth admission, render stages and whole-frame tails; do not reduce artistic
  reaction strength to conceal cost. Preset 2 with persistent strands currently exceeds the render budget (~14 ms
  median under game60); reduce repeated submission/preparation and prove tails without weakening the approved strands.
  Requested CLI settings can be overwritten by curated activation.
  5 Nov: the logical tick (Waveform dynamics) was 2.2-3.2 ms median offline (live ~1.4x, budget 2.5 ms) after the
  reaction work; the along-curve surge and per-card colouring now run as rows (byte-identical packets proven per tick
  on real replays; paired -0.33 and -0.18 ms), quiet-machine median 1.32-1.35 ms all presets. Offline GPU at the
  live card size: P2 7.2-7.6 ms with strands, 6.0-6.6 without (strands ~1.1 ms). Next: the game60 live check.

Chosen first: the smallest contained scene and the first consumer of S3D-1/S3D-2/S3D-5. Brief and hard gates:
`Docs/Future_Work/Waveform_Ribbon.md`. The detailed working checklist and visual target custody live in
`Docs/Reference/Waveform_Ribbon_Lab_Plan.md`; reference packages under `references/` are local/operator-owned and are
intentionally absent from normal GODZIPs.

The scene is world-first through the shared framed camera (Orthographic default): wet reflective concrete floor,
waveform and full-scene night fog, with no visible horizon/sky/floor edge. The waveform clears and softly lights
the mist. Preset/control migration and recorded-audio calibration come only after the lab look is credible.

- [~] **WR-07/08 production candidate — finish admission:** the reaction is the travelling energy pulse with
  selectable modes (the C elastic body remains only for depth sway/torsion); A's accumulated twist and the reactive
  axial roll stay, with musical vertical response applied after the roll (roll-invariant). Preserve constant history
  flow, no time-varying axial scaling, smooth curves, particles/free strands and fog clearance by the actual body.
- [~] **Full controls/editors, four-ribbon capacity and three presets — finish admission:** primary/alternate examples now have
  candidate Preset 1/2 with the
  selected hybrid, shared framed 3D camera/navigation, technical profile, preset/Custom and Edit/Arrange feature set.
  Expose bend/torsion/stretch/twist/rotation and accent ranges, source/curve visual tuning, ribbon/gradient editors,
  and floor reflectivity/tint/brightness. Every reactive range needs actual quiet/peak consumer proof for both handles;
  retain mutable authored presets and prove Save/Cancel/Restore and runtime source reachability.
- [ ] **Framing, timing and acceptance:** prove hidden ends/history bounds and body/head-to-visible delay across admitted
  sizes/camera poses; replay real quiet/middle/hot/silence/hot-start windows with unshifted audio, inspect lab/production
  parity and audit range headroom. Close shared lifecycle/cost/dormancy gates and run
  `tools/visualizer_live_check.py --mode waveform_ribbon --load game60` before WR-09 acceptance. Operator visual/native
  judgement remains explicit where automation cannot close it. The new unified atmosphere supersedes all old fog
  layers. Floor-column polish is secondary to continuous ground and response.
- [ ] **Loaded render budget:** repeat the corrected actual-config live check after current source/geometry
  changes. The prior run labelled fog-OFF rendered fog because preset activation overwrote its CLI values; it is a
  failed fog-ON run, not an A/B. Verify packet lease/GPU envelope/culling retirement and finite-consumer parity, then
  measure current body/birth/floor cost with the rejected volume disabled. Keep CPU reduction as a test oracle; no
  readback or duplicate live preparation. Replacement atmosphere must earn its own measured budget.

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

## 8. Accepted Bubble: bounded performance gate and deferred control audit

The operator has **accepted the improved original Bubble normal-drift musical authority**. That task is closed;
do not reopen it as unfinished work or restore the pre-experiment drift response. The durable approved motion,
ambient, direction and occlusion rules are in `Docs/Guardrails/Bubble_Temporal_Fidelity.md` §23. The following
performance gate is **explicitly admitted now** as a short exception to the §7 mode sequence. The separate
scalar-to-range audit remains deferred until explicitly reprioritized.

- [ ] **Bubble post-ambient performance / exact-output check (short and bounded):** inspect hidden costs from the
  shared hero big-over-small shader loop (including decoration OFF), opt-in 2048-capped ambient FBO, large glow
  sprite fill, and up-to-110-circle masking. Compare the **original handoff** to the **accepted Slice 13** under
  matched configuration for resource/performance attribution, then freeze **Slice 13 itself** as the behavioral and
  rendered-output oracle for any proposed optimization: original-vs-Slice-13 pixel bytes are *not* expected to match
  where the operator intentionally changed layering, motion or glow.
  - [ ] Measure decoration OFF, representative decoration ON, and high-density/high-glow decoration ON, using matched
    real-music replay and canonical plus extreme-wide/tall/expanded sizes, with multiple repetitions on the operator's
    native Qt Quick/OpenGL runtime. Report Bubble GPU/render p50/p95, CPU logical work, FPS/frame-pacing gaps,
    resource allocation/release and other-display contention. Check that OFF really avoids the extra FBO, sprite
    and mask draws; the modified shared hero shader still warrants timing even with decorations OFF.
  - [ ] For any **actual optimization**, compare deterministic logical packets/bit patterns exactly, and compare
    final captured RGBA bytes frame-by-frame on the **same GPU, driver, dimensions and fixed replay** when that
    capture path is deterministic. Where bit identity is unavailable, disclose why and use exact geometry/response
    checks plus recorded pixel-diff and temporal parity evidence. Do not claim byte-identical *performance*:
    throughput, GPU timing and latency require measurements.
  - [ ] If cost is material, optimize only the measured offender and repeat the parity + native performance gate;
    preserve visual quality, all approved sinking/reversed-flow presets, reactivity/latency, BTF and mutable presets.
    If no material cost is measured, **close the item without redesigning Bubble**. No generic "lean out" campaign.
## 9. Studio for every visualizer (replaces the builders)

Operator (5 Nov): instead of a Bubble UX sweep, every visualizer except Sine (retiring) gets a version of the reusable
Studio (`ui/studio`, mode registry + adapters) that replaces its builder. The Waveform Studio is the first adapter and
the framework bar; each mode contributes only an adapter (typed schema from the canonical registry, truthful evaluator
on its production logical/render path, fixtures, scene objects, workspaces and instruments), never a copied shell.
The former Bubble scalar-to-range idea is folded in: each adapter picks the right instrument per control under the
design pack's control policy (quiet/peak A/B, real ranges only where a true interval exists), with unchanged
serialized data unless a migration is justified. Accepted looks/behaviour (BTF, presets, timings) must not change.

- [ ] Finish Waveform Studio acceptance first (§7.1), then extract any remaining Waveform-shaped assumptions.
- [ ] Adapters in order of authoring pain: Extruded Bubble, Bubble, Sphere, Spectrum/Rainbow Ghost, Extruded Spectrum,
  Shockwave Grid, DevCurve, Oscilloscope. Each: full registry coverage test, production-parity preview test, theme,
  Settings Custom launcher replacing that builder body once the operator accepts it.

## Operator execution and evidence rules

Use direct-copy, single-line PowerShell commands with explicit `.venv\Scripts\python.exe` for the operator. Keep
details and evidence at their focused owner, this checklist actionable, and `Index.md` / `Spec.md` navigation current.
No memory updates without an explicit request.
