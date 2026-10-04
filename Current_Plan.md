# SRPSS | Current Plan

This file is the **live execution checklist**. The current program is the modern OpenGL 4.6 / shared Scene3D expansion.
Work it top to bottom unless the operator redirects a slice. Closed build-debloat, installer, QRC and timezone work
belongs in durable contracts/reference docs, not in this checklist. Reopen package trimming only for a measured
regression or a newly supplied footprint that exposes a concrete safe target.

This file is the **sole live 3D execution decomposition**. Landed substrate contracts live in
`Docs/Reference/Scene3D_Resources.md`, `Docs/Reference/Transitions.md`, `Docs/Reference/Visualizer_Reference.md` and
`Docs/Reference/Sphere_Visualizer.md`. Do not create a second parallel 3D plan while this program is active.

## 0. Accepted baseline | do not reopen as work

- [x] **S1-S13 scene3d substrate accepted.** Strict OpenGL 4.6 Core / GLSL 460, shared context-local resource ownership,
  DSA/immutable storage where useful, camera/projection helpers, bounded targets, bloom/motion-blur/trails/photo
  reflection, next-transition warm-up, state fences and retirement are the starting point. Fix defects at their owner;
  do not recreate S1-S13 as a historical checklist.
- [x] **Packaging sanity restored (R-102).** WebEngine/world-timezone/generated-Python-QRC bloat is no longer an active
  project; binary RCC, clean installer replacement, QTimeZone authority and the current Qt/QML denylist are baseline
  contracts. PySide6.QtQuick's binding-level dependency on `PySide6.QtOpenGL` is explicitly retained in every runtime
  build even though application source does not import it directly; `Qt6OpenGLWidgets` remains separately unused. The
  modern-GL roadmap is protected from future package pruning: no GL/ARB/KHR capability is removed merely because its
  first planned 3D consumer has not landed yet.
- [x] **Rendering ownership remains singular.** Qt Quick owns presentation/scheduling; no QWidget/QPixmap runtime
  fallback, no mixed presentation authority, no `frameSwapped -> requestUpdate()` loop, no render-rate simulation clock.
- [x] **Diagnostic logging hygiene.** Dedicated family sidecars own routine diagnostics; expected lifecycle cancellation
  is a cancelled task outcome, not a failed task traceback. Diagnostic-only WARNING records may be explicitly sidecar-only
  and disappear from main/console only while their declared sidecar is active; real degradation and ERROR/CRITICAL remain
  central. ThreadManager task failures inherit stable category-to-family ownership so FEEDS/other categorized failures also
  land in the correct sidecar. PERF threshold diagnostics may use the same sidecar-only contract. **Log locations are not
  a scavenger hunt:** source Diagnostic reuses the normal source-tree `logs/`; frozen Diagnostic uses the Diagnostic
  executable's adjacent `logs/`; LocalAppData/Temp are fallback-only when the preferred location is not writable.
- [x] **FEEDS refresh/durability incident closed (R-104).** Remote document examination is isolated in one lazy
  family-owned parser process, warm cache state restores validated local artwork bindings before network construction,
  source refreshes remain staggered, and presentation consumes coherent latest-wins bundles. Thirteen focused product
  gates pass. A two-display source run with active Bubble and a real FEEDS refresh removed the former 180-350 ms
  cadence hitch; the observed refresh window peaked at 63 ms only while the lazy parser child first appeared, then
  returned to ordinary low tails. Cached-art startup restored local files with zero fetch attempts. No live FEEDS
  archaeology remains in this plan.
- [x] **Media/GSMTC query-context handle churn closed (R-103).** The Media affinity lane retains one Proactor event
  loop and one GSMTC manager instead of creating them per query, and tears them down on the owning thread. The 100-query
  reuse and real Windows 200-query handle gates pass; subsequent runtime evidence shows the pre-parser Semaphore baseline
  flat rather than ratcheting. This is distinct from R-84's older replacement-generation question.
- [x] **S14 persistent mapped stream + std430 storage accepted.** One fixed, fenced, coherent persistently mapped ring
  per consumer streams changing per-frame bytes with multi-bind; Exploding Tiles' uniform blocks moved onto it
  (pixel-identical, fewer calls, lower trails submit). `Scene3DStorageLayout` + ring binding are the storage-buffer
  substrate; its first consumers arrive with S15-S19. Contract, measurements and bars:
  `Docs/Reference/Scene3D_Resources.md`.
- [x] **S15 compute seam accepted.** `scene3d/compute.py` (explicit dispatch groups, writer-owned barriers, scoped
  image units) plus compute programs in the shared cache and gradual warm-up. First consumer chosen by measurement:
  motion blur's tile max (three fragment passes -> one dispatch; byte-identical; -14 GL calls and two fewer textures per
  motion-blurred frame; lower CPU and GPU in frame-alternating A/B). Atomics/atomic counters arrive with their first
  consumer. Candidate survey, measurements and bars: `Docs/Reference/Scene3D_Resources.md`.
- [x] **S17 material/light block accepted** with its first consumer, **Blinds -> 3D Slats** (S20). GGX/Cook-Torrance,
  roughness/metalness/specular/emissive, directional/point/spot lights and photo-environment light through an analytic
  split-sum BRDF (no LUT texture), GPU-mirrored. Flat Blinds stays byte-identical and dormant. Contracts, cost and
  open physical checks: `Docs/Reference/Transitions.md`.
- [x] **Page Curl landed (S20)**, the bendable grid's first consumer: an isometric cylinder curl with a folded paper
  back, material lighting only on bent paper and an analytic shade that ends at zero. Deactivated by default; physical
  checks in `Docs/Reference/Transitions.md`.
- [x] **S16 + S18 GPU population accepted** with its first consumer, **Disintegrate** (a new transition, deactivated by
  default): bounded per-run SSBO pool, compute evaluation of live members only, order-preserving prefix-sum compaction,
  a GPU-written indirect command (no count readback) and one indirect draw. Against per-vertex evaluation of the whole
  pool: -29% to -49% GPU, +0.1 ms fixed CPU submit (`Docs/Reference/Scene3D_Resources.md`). Remaining S18 primitives
  (lightning, smoke/fire volumes, energy fields, collision, OIT, ribbons) arrive with their own consumers below.
- [x] **Accordion Fold landed (S20)**: isometric pleats on a crease-aligned grid with flat material shading and an
  exact slide-out. Deactivated by default.
- [x] **Relief Rise landed (S20)**: a height-field wave from the mipmapped photo copies, lit by the S17 material with
  the first contact-occlusion term (S17), exact ahead of and behind the wave. Deactivated by default.
- [x] **Cube Turn landed (S20)**: a quarter-turning box on the shared box mesh with a dolly that returns home,
  material-lit faces and a blurred backdrop. Deactivated by default. The S20 transition verticals are complete; the
  Visualizer verticals follow (a new mode first needs its logical-capture and Guided Setup preview wiring designed).

## 1. Visualizer 3D hardening and direct controls | **NEXT**

Operator direction (2026-10-03, after testing Extruded Spectrum and Shockwave Grid): this part of the codebase must not
fall behind the features built on it. Every infrastructure item below is **measured before and after** (TIME_ELAPSED +
per-frame flush, median/p90, CPU submit and Python GL-call count, both displays where relevant). Work in this order:

- [x] **H0. Borrowed technical profile ignored the lender's preset** (the "pinned, unreactive" Extruded Spectrum of
  2026-10-03): fixed at the activation owner, bars `tests/test_visualizer_profile_lender_presets.py`. Sphere keeps its
  raw-key resolution until S19 captures its golden (S19 item: replace it with Sphere's own profile).
- [x] **H1. First use of a 3D Visualizer lands behind its reveal** (operator: no preloading; a one-time cost is fine
  only hidden by the fade, never stopping the world or poisoning later frames). Finding: the fade did *not* hide it; the
  first visible frame compiled and allocated (Shockwave 22 ms, 139 ms cold cache; logs 2026-10-03: 21-45 ms on
  switches). Now prepared on the hidden frames, one spaced unit each, the reveal held until done (1.5 s deadline):
  first visible frame 3-4 ms. Contract and numbers: `Docs/Reference/Visualizer_Reference.md` "Prepared reveal".
- [x] **H2. 3D quality tiers in a 3D Settings tab** (General / 3D Transitions / 3D Visualizers pills; `Auto / High /
  Balanced / Performance / KAK`; one resolver `core/settings/scene3d_quality.py`; each level stores only its own
  choice; `transitions.detail_3d` retired by an input bridge). Extruded: samples + Mirror Faces on/off; Shockwave: samples,
  Glow, grid density. Contracts and per-tier costs: `Docs/Reference/Transitions.md` "3D Detail",
  `Docs/Reference/Visualizer_Reference.md` 16A/16B. Physical: the tiers on both displays (cross-cutting item below).
- [x] **H3. Exact musical events**: the transient bus publishes immutable, serial-numbered `MusicalOnset`s (with the
  unclipped magnitude and absolute loudness H4 needs); Shockwave Grid takes each exactly once, born when it happened.
  Contract: `Docs/Reference/Visualizer_Reference.md` "Musical onsets".
- [x] **H4. Shockwave Grid reactivity**: the onset strength had a 0.25 floor and a 1.0 cap on a loudness-normalised
  bus. Now a loudness/presence gate silences near-silence, presence against the track's usual onsets lets big hits
  reach ~2.9x medium ones (taller, wider, brighter, with an echo ring), the ridge glows brighter where bars are
  loudest, and an Idle Swell drifts side to side. Contract: Visualizer_Reference 16B "Reactivity"; physical check open.
- [x] **H5. Direct 3D Visualizer controls outside Edit**: Alt + right drag moves, Alt + wheel resizes (Alt + left
  orbits), through Edit's own session code with no chrome, one commit through Edit's Save at the gesture's end, nothing
  held between gestures. Contract: `Docs/Reference/Visualizer_Reference.md` 16A "Alt + right drag / Alt + wheel".
  Physical check open: both displays, Alt behaviour with the OS (no stray menu), anchored vs. Custom placement.
- [x] **H6. Shared 3D view and line helpers** (`SCENE3D_ORBIT_GLSL` / `scene3d_orbit_project`, `sceneLineCoverage`):
  both modes moved onto them without visible change. Fit policies stay per mode (they genuinely differ).
- [x] **H7. Render-thread CPU**: profiling showed PyOpenGL's per-call `glGetError` was 45-60% of every mode's
  render-thread CPU (Bubble 0.37 -> 0.17 ms, Spectrum 0.43 -> 0.24, Extruded 0.65 -> 0.35, Shockwave + glow 1.04 ->
  0.41; transitions alike). It is off at process start; each render node checks once per frame through its failure
  log (`rendering/gl_error_policy.py`). Uniform blocks would now save ~0.03 ms per mode: not done.
- [x] **CHK26 inherited-state capture fast path** (operator-approved 2026-10-04 under the full CHK26 contract): the
  same per-frame `glGetIntegerv`/`glGetBooleanv`/`glIsEnabled` reads, same fields and order, called directly instead
  of through PyOpenGL's numpy wrappers; nothing cached, restore and clip ownership untouched. Evidence: field parity
  0/300 randomized states (both captures); capture 104-109 -> 39-42 us; whole render CPU median Bubble 0.21 -> 0.12,
  Spectrum 0.26 -> 0.18, Extruded 0.36 -> 0.26, Shockwave 0.43 -> 0.36 ms, GPU unchanged; pixels and restored state
  bit-identical for Bubble/Spectrum/Sphere/Extruded, Shockwave within its own <=1/255 noise; clip smoke, render node,
  CUSTOM, switch, teardown and Bubble golden suites green (1416). Live check: `render_host_begin -> gl_state_ready`
  in the frame trace (was ~0.56 ms median on the TV display).
- [x] **H8. Translucent order in Extruded Spectrum** solved exactly without OIT: bar records in a painter's order from
  the orbit's eye (`scene3d_orbit_eye`, `extruded_draw_order`; bars occupy disjoint x slabs) and faces turned from the
  eye culled in the translucent passes; one layer carries the opacity two used to. Physical check: ghosts at strong
  angles, the reflection's floor contact line.
- [x] **H9. Reflected wallpaper without reading the target**: the owner downsamples the displayed photograph once per
  image change (`backdrop.py`) while a mode reflects, the renderer uploads it once; no GL texture shared, PR-04
  untouched. Mirror Faces p90 GPU 0.60 -> 0.098 ms. Physical check: reflections follow wallpaper changes on both
  displays (and after a CUSTOM display transfer).

## 2. S17 | active-only high-fidelity scene buffers, lighting and materials

- [ ] Extend `SceneTarget` only with the normal/material/depth/history attachments a concrete consumer actually needs.
  The canonical product/output path is **SDR-only**: no HDR swapchain, HDR metadata, HDR display mode, HDR output setting
  or HDR-specific tone-mapping pipeline. A higher-precision internal intermediate is allowed only when a measured effect
  needs numerical headroom and must still resolve into the ordinary SDR presentation path.
- [ ] Add reusable real-3D shadow facilities with bounded softness/contact treatment. Keep the existing planar shadow
  wherever it is cheaper and visually correct.
- [ ] Add active-only GTAO where a consumer with real occluding geometry justifies it (Relief Rise's height-field
  contact occlusion is analytic and needs no buffer).
- [ ] Add weighted blended OIT/depth-aware soft transparency for smoke/sparks/glass-heavy scenes that would otherwise
  require CPU sorting.
- [ ] Add depth/thickness-aware refraction, Fresnel reflection, rough transmission and restrained optional dispersion
  using owned scene/environment textures. Never mutate or illegally sample the lent PR-04 presentation texture.
- [ ] Every extra full-screen attachment/pass must prove disabled-path allocation = zero and exact transition endpoints.

## 3. S18 | particles, lightning, smoke/fire and volumetrics

- [ ] **GPU particles, remaining:** soft sprites/streaks/ribbons over `CompactedPopulation`, optional simple analytic/SDF
  collision and OIT, each with a consumer that needs it. (Pool, seeded spawn, compute evaluation/compaction and
  indirect draw landed with Disintegrate.)
- [ ] **Lightning/electricity:** stable seeded branching topology per admitted event, travelling intensity/forks,
  emissive core+bloom, secondary arcs, short afterglow and optional local-light injection. Never rerandomise the entire
  bolt at render cadence.
- [ ] **Smoke/fog/fire:** active-only half/quarter-resolution field or procedural volume, bounded advection/vorticity,
  event injection, depth-aware raymarch, temporal reprojection, absorption/scattering and emissive fire/embers. Quality
  tiers bound volume resolution/ray steps/light samples; disabled means no allocation or dispatch.
- [ ] **Energy/field effects:** deterministic shockwaves, force fields, plasma/nebula, reaction-diffusion and heat-haze
  primitives using compute/image resources rather than parent CPU loops.
- [ ] Measure each primitive independently before spectacular combinations are allowed.

## 4. S19 | Voxel Sphere promotion onto shared Scene3D

Sphere is the legacy exception that predates the shared Scene3D foundation. Promotion removes its duplicate low-level
GPU plumbing and hidden technical-profile debt; it is **not** a demand for pixel-for-pixel visual stasis.
`Docs/Reference/Sphere_Visualizer.md` owns the behavioural golden and the Bubble golden remains unrelated and untouchable.

- [x] **Everything ramps (operator 2026-10-03/04)**, measured on recorded music: every Sphere reaction (how often and
  how strongly fragments, particles and tracer fire, tracer light/speed, spin, body growth) ramps on the shared passage
  intensity (`transient_bus.PassageIntensity`: the heard passage on the fixed real-music scale, 0.65 at the usual
  loudness; nothing learned from the track, which faded sustained choruses and overreacted after resets);
  floors gate on it. Before/after numbers and contract: `Docs/Reference/Sphere_Visualizer.md` "Everything ramps";
  measure with `python -m tools.visualizer_replay.sphere_ramp`. Physical check: the four songs live.
- [x] **Golden step 1a: real-scale replay.** `FeatureFrame` schema 1 validated every lane into `0..1` and could not
  carry real music. Schema 2 (additive; schema 1 serialises byte-identically) adds `RealScaleLanes` in production
  units, uncapped: live pre-AGC bands, `(loudness, presence)`, the raw analysis spectrum, typed events.
  `ReplayBeatEngine` serves them through the production accessors and the production event scheduler; the replay
  driver resolves technical profiles as production does and replays Sphere (`REAL_SCALE_MODES`) through
  `capture_sphere`, recording its behavioural outputs per frame, for any preset. Bars:
  `tests/test_visualizer_replay_real_scale.py`.
- [x] **Golden step 1b: recorder** `tools/visualizer_replay/record.py` (no window, no product cost; Harness_Index).
  Clips start at 1 s so the scheduler's per-type debounce (counted from timestamp 0) drops nothing.
- [x] **3D + frameless Visualizers are not contained to their frame (operator 2026-10-04).** Stacking was already right
  (Visualizer layer above every widget, below the OSD/Edit chrome/menu). Extruded Spectrum and Shockwave Grid composited
  through a target padded a fixed 0.5 item heights, which cut extreme orbits (Extruded at tilt -1) and Shockwave's
  wide default view; their targets now cover the projected reach of everything they can draw (`extruded_reach`,
  `shockwave_reach`, `scene3d/frame.py` `reach_item_frame`: quarter-height steps, clamped to the window), computed
  identically on the hidden prepare frames. Extruded's default target shrank (0.72 -> 0.46 MP at a 640x360 item);
  Shockwave's grew to its true visible width (0.72 -> 1.12 MP). Bars: `tests/test_visualizer_3d_reach.py`.
  Physical check: orbit both to extremes on both displays.
- [ ] **Sphere visual upgrade licence (operator):** the migration may make Sphere more visually appealing with the
  shared feature set (materials, lighting, post, reflections, tiers), within the golden-as-reference rules above.
  Landed: tier antialiasing through the scene target; **Mirror Cubes** (operator 2026-10-04: mirror cubes, and a
  preset that shows them off: Preset 5 Mirror Ball). Physical check: Mirror Ball on bright and dark wallpapers.
- [x] **Reactivity goblin audit of the other modes** (operator 2026-10-04; Bubble excluded). Tool:
  `python -m tools.visualizer_replay.mode_audit` on the four songs (the second takes). Found and fixed: the engine's
  inline (pool-less) analysis published raw bars only, so recordings carried a zero continuous lane (one commit
  path now; replay derives the lane from raw bars as production does); replay padded Oscilloscope's block with
  zeros; Sine's metric measured settings. Healthy once measured honestly: Spectrum, Oscilloscope (0.08-0.12 ->
  0.12-0.16), Sine Wave (band energy 0.41 -> 0.56; the AGC-lane family grows 1.3-1.7x). Goblins fixed:
  **DevCurve** transients layer inverted (self-relative transient lane; now gated by the shared
  `passage_ramp`), and its travel/undulation speed and slope never followed the music (now a slow passage drive,
  see the authoring guide); **Shockwave Grid** fired ~9 waves/s at every level with flat strength and big waves
  commonest when quiet (now `shockwave_gap` / `shockwave_passage_share`). Physical check: DevCurve and Shockwave
  on the four songs live.
- [x] **Golden step 1c: recordings** (`logs/visualizer_recordings/`, local): the first 60 s of "Rag Doll"
  (`quiet_intro`), "I Said Hi" (`quiet_intro2`), "Human" (`heavy1`, swings hard, a Bubble favourite) and "Into Your
  Room" (`balanced`, light sustain). Loudness median 6-7, p90 ~12, max 18-20; live bass pinned at 2.5 in 80-95% of
  frames; ~200 kicks, ~130 snares, ~90 vocal swells a minute.
- [x] Capture the promotion golden first (captured 2026-10-04; `Docs/Reference/Sphere_Visualizer.md` "Captured"): curated presets, the exact currently resolved hidden Spectrum-backed technical
  profile, deterministic FeatureFrame/logical replay, representative renderer captures, extreme CUSTOM geometry and
  silence/vocal/kick/sustained passages. Split the comparison explicitly into **behavioural** evidence and **visual**
  evidence so a prettier renderer is not mistaken for a reaction regression.
- [ ] **Behavioural golden is a reference, not a lock (operator 2026-10-04).** Today's reaction *numbers* are known to
  be poor (no real ramp, admission at small sounds) and are expected to change during the migration. What must not be
  lost: event ownership (no ambient spawning, nothing authored in silence), the response vocabulary (local
  fragmentation, intake/outtake cohorts, tracer travel, sustained body growth, spin), stable voxel and cohort identity,
  source freshness, and that loud passages and big hits react at least as strongly as now. The golden records today's
  outputs so every change is a measured, intended difference, never an accidental one.
- [ ] **Visual parity is a floor, not a ceiling.** Preserve the recognisable stepped-voxel/preset identity and authored
  colour/alpha intent, but shared Scene3D may improve antialiasing, lighting, materials, depth readability, shadows,
  reflection/refraction treatment or other presentation quality during the migration. A deliberate visual difference is
  accepted when it is demonstrably better and does not weaken musical response, silhouette/voxel identity or preset intent;
  the before/after golden exists to catch regressions, not to freeze every pixel.
- [ ] Replace duplicate low-level GPU plumbing with Scene3D equivalents: lifetime/fences, frame/target, persistent-stream
  and SSBO transport, common material/light/post, shared particle/shadow facilities and the common 3D quality resolver.
  Delete superseded Sphere-local low-level infrastructure after acceptance; do not retain a fallback engine.
  Done: programs/uniforms/mesh on `MeshResources` (static instance stream), prepared reveal, own `SceneTarget` overlay
  with tier multisampling, `reach_item_frame` overflow (the private depth-scissor helpers are gone), the reflected
  wallpaper through `BackdropEnvironment`. Remaining: per-frame values in one uniform block (two programs set ~60
  uniforms a frame), then the technical profile.
- [ ] **Give Sphere deliberate technical controls instead of permanently borrowing Spectrum invisibly.** Inventory the
  actual analysis seams Sphere consumes, then replace the single `technical_controls=False` / whole-Spectrum-profile
  borrow with descriptor-owned per-control capability metadata and a Sphere-owned resolved technical profile. Source/capture
  controls such as input gain, audio block size, sensitivity and noise-floor handling are candidates only where tests prove
  they affect Sphere's pre-AGC/analysis inputs. AGC, dynamic-range, bar-count and transient controls must not be exposed
  merely because the established modes have them: Sphere deliberately consumes pre-AGC/event-owned lanes and dead sliders
  are forbidden. Existing installations missing Sphere technical keys resolve to values equivalent to today's hidden
  Spectrum-backed profile; curated/Custom preset ownership then follows the normal per-mode contract without cross-mode
  bleed.
- [ ] Make Sphere an ordinary shared-foundation 3D Visualizer consumer with the standard capability/tier lifecycle and
  dormancy. Whether it remains default-disabled or loses the Experimental label after acceptance is a separate product
  admission decision, not another renderer migration.

## 5. S20 | vertical consumers | make the substrate earn its complexity

Implement vertical features in this order unless evidence from a preceding slice justifies a swap:

- [x] **Shockwave Grid landed** (dormant by default): displaced grid + bounded onset-event SSBO + emissive/bloom on the
  SDR presentation path, via the new overlay bloom of `SceneTarget`. Contract, cost and physical checks:
  `Docs/Reference/Visualizer_Reference.md` 16B.
- [ ] **Reactive Particle Field**: compute/compaction/indirect/OIT proof.
- [ ] **Spectrum Terrain / Skyline / Tunnel**, then **Waveform Ribbon** and **Deformable Blob Sphere**.
- [ ] **Bubble Depth Field** only under Bubble Temporal Fidelity/R-69: depth may not damp, retime or re-author Bubble's
  accepted amplitude/reaction/ghost/tail cadence.
- [ ] Only after primitives are individually accepted, combine them deliberately: electrical storm terrain, smoke-lit
  voxel fracture, ember/dust destruction, refractive glass lit by bolts, volumetric shockwaves and photo-colour IBL.

## 6. Cross-cutting acceptance | applies to every open box above

- [ ] **Dormancy:** an inactive capability owns no buffers/targets/volumes/history, compute dispatches, workers, forced
  frames, recurring timers or polls. `park()` / mode retirement returns transient resources to zero.
- [ ] **Performance:** count Python GL calls and measure CPU submit/GPU cost for every new pass. Render-thread Python GL
  calls hold the GIL; visual fidelity is not permission to regress Visualizer freshness.
- [ ] **Time:** no second simulation clock. Real seconds for real-time transition rates; Visualizers use logical time.
- [ ] **State:** every touched inherited GL state remains fence-restored even when DSA removes bind/query ceremony.
- [ ] **Memory:** new attachments/volumes are per-active-consumer, tier-bounded and measured on both displays.
- [ ] **Endpoints:** transition additions remain exact at 0/1 and near-endpoints; R-63 black/uncovered-edge guarantees
  remain binding.
- [ ] **Settings:** canonical defaults/descriptor resolution happen before admission; renderers never read Settings.
- [ ] **Physical acceptance:** exercise the shared 3D quality vocabulary (resolver and tab: H2) (`Auto / High / Balanced / Performance / KAK`)
  on both displays with active Visualizers, first-use/warm cost, parked memory and representative real photos/music. `KAK`
  means minimum viable base geometry/effect only: optional expensive 3D features are effectively off and essential densities
  use their lowest bounded setting. Sphere gets a dedicated before/after behavioural + visual golden during S19.

## Side defects (found in passing)

- [ ] **Steady-state repeated Visualizer draws (found 2026-10-04 with the transition ride, R-87 follow-up).** With no
  transition on either display, some seconds still draw the same Visualizer revision 12-97 times (165 Hz D0, Bubble):
  another scene update is requesting frames. Attribute it from `--frame-trace` before changing anything.
- [ ] **Tests and replays must not read presets or canonical defaults as expected values (operator
  2026-10-04: "really checking default settings or presets is not how any tests should ever function because I
  change those often").** After the Bubble cadence fix and once Sphere is accepted: inventory every test, golden and
  replay that resolves a curated preset or pins a canonical default (the replay driver's `preset=`, floors goldens
  built from preset 0, default-value asserts) and give each its own frozen inputs, as the Sphere promotion golden
  now does. Known red from this (2026-10-04): `tests/test_qtquick_extruded_spectrum.py::test_the_bars_stand_where_
  spectrums_do_coloured_across_the_spectrum_over_an_untouched_card` builds its snapshot through the Guided Setup preview,
  which resolves the curated Studio preset; the operator's new Studio values (Turn -0.25) fail it (HEAD passes).
- [ ] **Two stale tests red on HEAD (found 2026-10-04, not from S19):** `tests/test_godzip_foundry_core.py::
  test_run_tab_is_last_and_remains_repo_local` pins the button label `LOCAL vs GIT HEAD` (UI wording; the tool
  changed), and `tests/test_media_io_starvation.py::test_media_transport_command_starts_while_network_stalls_the_io_pool`
  stubs a controller without `_run_coro_on_work_loop` (production renamed its work-loop entry). Reconcile both to the
  current tool/controller; do not pin wording.

## Handoff rules

Significant slices get full superseding GODZIPs. The supplied/latest GODZIP is the working tree authority for handoff
work; do not reconstruct the tree from GitHub. No environment-variable feature gates. No speculative generic engine
layer without a vertical consumer. Rejected experiments are removed rather than kept as fallback architecture.
