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
  choice; `transitions.detail_3d` retired by an input bridge). Extruded: samples + Mirror refresh; Shockwave: samples,
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
- [ ] **Next render-thread CPU lever (measured, not started):** the Visualizer host's inherited-GL-state capture
  (`rendering/quick/visualizer/gl_state.py`) is ~40% of what remains in a 3D mode, `glGet*` through PyOpenGL's
  numpy-array wrappers. It is CHK26-lineage protected perf: change only with a measured, pixel-neutral fast path.
- [x] **H8. Translucent order in Extruded Spectrum** solved exactly without OIT: bar records in a painter's order from
  the orbit's eye (`scene3d_orbit_eye`, `extruded_draw_order`; bars occupy disjoint x slabs) and faces turned from the
  eye culled in the translucent passes; one layer carries the opacity two used to. Physical check: ghosts at strong
  angles, the reflection's floor contact line.
- [x] **H9. Reflected wallpaper without reading the target**: the owner downsamples the displayed photograph once per
  image change (`backdrop.py`) while a mode reflects, the renderer uploads it once; no GL texture shared, PR-04
  untouched. Mirror Faces p90 GPU 0.60 -> 0.098 ms. Physical check: reflections follow wallpaper changes on both
  displays (and after a CUSTOM display transfer).
- [ ] **Loose ends:** list the new 3D test files in `Docs/TestSuite.md`; the side defects below. (The Extruded
  turn/tilt unit change is recorded in `Docs/Architecture/Persisted_Input_Compatibility.md`.)

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

- [ ] Capture the promotion golden first: curated presets, the exact currently resolved hidden Spectrum-backed technical
  profile, deterministic FeatureFrame/logical replay, representative renderer captures, extreme CUSTOM geometry and
  silence/vocal/kick/sustained passages. Split the comparison explicitly into **behavioural** evidence and **visual**
  evidence so a prettier renderer is not mistaken for a reaction regression.
- [ ] **Behavioural parity is hard.** Preserve Sphere's authored timing, event admission, section drives, cohort identity,
  tracer semantics, size/rotation response, intake/outtake semantics, stable voxel identity and source-freshness contract.
  Default/new-profile resolution must reproduce today's behaviour before any user-authored technical change is applied.
- [ ] **Visual parity is a floor, not a ceiling.** Preserve the recognisable stepped-voxel/preset identity and authored
  colour/alpha intent, but shared Scene3D may improve antialiasing, lighting, materials, depth readability, shadows,
  reflection/refraction treatment or other presentation quality during the migration. A deliberate visual difference is
  accepted when it is demonstrably better and does not weaken musical response, silhouette/voxel identity or preset intent;
  the before/after golden exists to catch regressions, not to freeze every pixel.
- [ ] Replace duplicate low-level GPU plumbing with Scene3D equivalents: lifetime/fences, frame/target, persistent-stream
  and SSBO transport, common material/light/post, shared particle/shadow facilities and the common 3D quality resolver.
  Delete superseded Sphere-local low-level infrastructure after acceptance; do not retain a fallback engine.
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

- [ ] `tests/test_feed_runtime.py`: 3 reds on `HEAD` (2026-10-03, found while gating Extruded Spectrum; also red on a
  clean worktree): `test_retiring_one_endpoint_cancels_only_its_queued_work_and_prunes_state`,
  `test_shared_endpoint_is_cancelled_only_after_its_last_active_lease` and
  `test_cancelled_inflight_source_never_publishes_on_reactivation` see two source cache calls where one is expected
  (`widgets/feed_runtime.py` after the 5.0.6 Feeds commits). Decide whether the runtime or the tests are stale.

## Handoff rules

Significant slices get full superseding GODZIPs. The supplied/latest GODZIP is the working tree authority for handoff
work; do not reconstruct the tree from GitHub. No environment-variable feature gates. No speculative generic engine
layer without a vertical consumer. Rejected experiments are removed rather than kept as fallback architecture.
