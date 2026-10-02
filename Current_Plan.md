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
- [x] **Packaging sanity restored.** WebEngine/world-timezone/generated-Python-QRC bloat is no longer an active project;
  binary RCC, clean installer replacement, QTimeZone authority and the current Qt/QML denylist are baseline contracts.
  The modern-GL roadmap is protected from future package pruning: no GL/ARB/KHR capability is removed merely because
  its first planned 3D consumer has not landed yet.
- [x] **Rendering ownership remains singular.** Qt Quick owns presentation/scheduling; no QWidget/QPixmap runtime
  fallback, no mixed presentation authority, no `frameSwapped -> requestUpdate()` loop, no render-rate simulation clock.
- [x] **FEEDS content transition contract.** Every CUSTOM and NEWS feed card uses the shared `FeedPresentation.qml`
  event-driven body transition for retained content changes: gently fade old content fully out, commit the latest staged
  rows only at opacity zero, then gently fade the replacement in. No Timer, poll, worker or per-delegate animation owns
  the effect; current authored timing is 900 ms out / 1200 ms in with sine easing. **Cache/network/artwork hydration is one
  latest-wins presentation bundle:** intermediate accepted generations stay retained without starting a fade and NEWS waits
  for the family-wide initial admission barrier. If cache-first content is already painted, closing that barrier may own
  **exactly one** gentle body transition to the final hydrated aggregate; it must never become one fade per provider/source.
  Artwork replacement itself uses the retained two-buffer `ArtworkFadeImage` path with the same 900/1200 ms gentle timing,
  so a late local image URI cannot snap into a fully opaque raw `Image`. Once armed, equivalent settled publications update
  the latest pending target without restarting an in-flight fade. Do not shorten this into a refresh blink, commit hydrated
  content at full opacity, or animate publisher-by-publisher/cache/artwork startup events.
- [x] **Diagnostic logging hygiene.** Dedicated family sidecars own routine diagnostics; expected lifecycle cancellation
  is a cancelled task outcome, not a failed task traceback. Diagnostic-only WARNING records may be explicitly sidecar-only
  and disappear from main/console only while their declared sidecar is active; real degradation and ERROR/CRITICAL remain
  central. ThreadManager task failures inherit stable category-to-family ownership so FEEDS/other categorized failures also
  land in the correct sidecar. PERF threshold diagnostics may use the same sidecar-only contract. **Log locations are not
  a scavenger hunt:** source Diagnostic reuses the normal source-tree `logs/`; frozen Diagnostic uses the Diagnostic
  executable's adjacent `logs/`; LocalAppData/Temp are fallback-only when the preferred location is not writable.

## 1. 2026-10-02 diagnostic-soak defects | **BOUNDED ACCEPTANCE BEFORE S14**

This lane is deliberately finite. Prefer deterministic/focused tests and short local source runs over repeated frozen builds or long soaks. Do not expand it into a second roadmap: once the two checks below are accepted, continue directly into **S14** and the preserved S15-S20 shared-3D programme.

- [ ] **Frozen Diagnostic semaphore accumulation: one environment confirmation remains; do not spend a dedicated build on it.**
  The original frozen/Winlogon soak appeared image-shaped (~**+1.045 handles per image handoff**), but later attribution
  disproved SHM/Section ownership and identified the growing kernel class as `Semaphore`: in the reproducing frozen run
  (`16:54:01 -> 17:06:32`) **410 -> 467 (+57, ~4.6/min)** while `Section` stayed essentially flat (`383 -> 386`), including
  30-second windows with zero image transition. The owner matched Media/GSMTC churn: 224 Media affinity-lane jobs and 225
  fresh `IocpProactor` loops in ~14 minutes. Media now retains one lazy Proactor loop plus one GSMTC manager on its affinity
  thread and closes them there at retirement. The focused suite has passed **100 repeated owner-thread queries** and a
  Windows-only **200-query real GSMTC/Proactor handle check**. The 2026-10-02 source Diagnostic follow-up also plateaus after
  warm-up at roughly **411-417 Semaphores** (Section ~389-390) for ~16 minutes rather than ratcheting. Because the historic
  observable leak reproduced only in frozen Diagnostic, final closure should piggyback the **next otherwise-justified frozen
  build** and needs only 5-10 minutes of handle evidence. Do not build or soak solely for this check.
- [ ] **FEEDS periodic GIL hitch + startup/artwork presentation: finish bounded acceptance.** Deliberate source bunching is
  already removed: the old 25%-of-interval early-join window is gone and periodic remote work is family-serialized with a
  **2.5 s event-driven cooldown**, no polling/sleep loop/extra worker. The 5-minute physical run proves that serialization
  works, but it also disproves full performance acceptance: event-loop maxima repeat at the FEEDS cadence (**352, 240, 180,
  221, 356 ms** at ~5-minute intervals). Providers are no longer colliding, so the remaining stall is consistent with one
  heavy Python feed parse/normalization monopolizing the GIL; PC Gamer was ~403 KB and Crunchyroll ~144 KB in the sample.
  Bound needless work now: CUSTOM and each NEWS provider normalize only `max(12, item_limit)` stories instead of the historic
  fixed 40, and Diagnostic FEEDS logging records per-parse payload/feedparser/normalization timings without exposing URLs.
  Presentation is also corrected: the family startup barrier coalesces cache/network/artwork churn into **at most one** slow
  body transition, and FEEDS artwork uses `ArtworkFadeImage` at 900 ms out / 1200 ms in rather than snapping a raw `Image`
  into full opacity. Focused tests must prove the one-transition barrier, retained artwork fade, parser cap and no-early-batch
  behavior. One short source run at the existing **5-minute minimum** is sufficient physical acceptance; if a cadence hitch
  remains, use the new `[FEEDS][PARSE]` timings to fix the measured parser stage rather than adding another soak/build.
- [x] **Topology memory high-water is not active work.** The operator intentionally rushed topology during this soak. Do
  not reopen the one observed high-water retention unless it reproduces independently in normal use or another targeted
  lifecycle check.

## 2. S14 | persistent mapped stream + SSBO foundation | **NEXT, IMMEDIATELY AFTER BOUNDED ACCEPTANCE**

- [ ] Add one bounded context-local persistent mapped ring for genuinely changing small frame payloads. Prefer coherent
  mapping only where measured healthy; otherwise explicit flushes. Fence segment reuse safely with no busy polling,
  per-frame map/unmap or allocation.
- [ ] Add schema-owned std430 SSBO helpers for structured instance, event, history, material and compact-work data.
  Packing/layout tests must compare the Python side with the shader/driver contract where practical.
- [ ] Migrate only consumers that benefit. Tiny fixed values stay uniforms/UBOs when that is cheaper than forcing them
  through the new substrate.
- [ ] Measure before/after CPU submit time, GL-call count and GPU sync tails. A new abstraction does not survive merely
  because it is modern; it must remove real Python/driver ceremony.
- [ ] Prove retirement/context-loss: fixed capacities, no overwritten in-flight segment, zero leaked handles and no
  meaningful dormant cost when no 3D consumer requests the facility.

## 3. S15 | compute, image load/store and atomics

- [ ] Add shared compute-program/resource helpers with explicit dispatch dimensions and barrier ownership.
- [ ] Add image load/store and atomic/atomic-counter support only as concrete consumers require it.
- [ ] Build deterministic GPU tests/mirrors for first compute jobs. No ordinary CPU readback.
- [ ] Keep time authority unchanged: transition compute derives from admitted run progress/real authored seconds;
  Visualizer compute consumes logical revision/time and bounded immutable snapshot/history inputs. Re-rendering one
  logical revision must not advance state again.
- [ ] First useful jobs should be concrete: particle evaluation/compaction, bolt/branch tables, volume injection,
  post kernels, light/cluster lists, active-piece masks or indirect counts.

## 4. S16 | indirect / multi-draw + GPU compaction

- [ ] Add bounded indirect command buffers and compact active-instance lists only where they replace material Python
  submit/draw loops.
- [ ] Preserve stable IDs/seeds through compaction so populations do not shimmer when membership changes.
- [ ] Keep generated counts GPU-owned in the ordinary path; no CPU count readback loop.
- [ ] Prove capacity bounds and deterministic population/placement against a reference path before migration.

## 5. S17 | active-only high-fidelity scene buffers, lighting and materials

- [ ] Extend `SceneTarget` only with the normal/material/depth/history attachments a concrete consumer actually needs.
  The canonical product/output path is **SDR-only**: no HDR swapchain, HDR metadata, HDR display mode, HDR output setting
  or HDR-specific tone-mapping pipeline. A higher-precision internal intermediate is allowed only when a measured effect
  needs numerical headroom and must still resolve into the ordinary SDR presentation path.
- [ ] Add a common material/light block: GGX/Cook-Torrance, roughness, metalness/specular, emissive, bounded directional/
  point/spot lights, BRDF LUT and photo/environment IBL.
- [ ] Add reusable real-3D shadow facilities with bounded softness/contact treatment. Keep the existing planar shadow
  wherever it is cheaper and visually correct.
- [ ] Add active-only GTAO/contact AO where justified by a real consumer.
- [ ] Add weighted blended OIT/depth-aware soft transparency for smoke/sparks/glass-heavy scenes that would otherwise
  require CPU sorting.
- [ ] Add depth/thickness-aware refraction, Fresnel reflection, rough transmission and restrained optional dispersion
  using owned scene/environment textures. Never mutate or illegally sample the lent PR-04 presentation texture.
- [ ] Every extra full-screen attachment/pass must prove disabled-path allocation = zero and exact transition endpoints.

## 6. S18 | particles, lightning, smoke/fire and volumetrics

- [ ] **GPU particles:** bounded SSBO pool, deterministic seeded spawn, compute evaluation/compaction, indirect instanced
  draw, soft sprites/streaks/ribbons, optional simple analytic/SDF collision and OIT. No Python object per particle.
- [ ] **Lightning/electricity:** stable seeded branching topology per admitted event, travelling intensity/forks,
  emissive core+bloom, secondary arcs, short afterglow and optional local-light injection. Never rerandomise the entire
  bolt at render cadence.
- [ ] **Smoke/fog/fire:** active-only half/quarter-resolution field or procedural volume, bounded advection/vorticity,
  event injection, depth-aware raymarch, temporal reprojection, absorption/scattering and emissive fire/embers. Quality
  tiers bound volume resolution/ray steps/light samples; disabled means no allocation or dispatch.
- [ ] **Energy/field effects:** deterministic shockwaves, force fields, plasma/nebula, reaction-diffusion and heat-haze
  primitives using compute/image resources rather than parent CPU loops.
- [ ] Measure each primitive independently before spectacular combinations are allowed.

## 7. S19 | Voxel Sphere promotion onto shared Scene3D

Sphere promotion is a plumbing migration, **not** a redesign. `Docs/Reference/Sphere_Visualizer.md` is the behavioural
golden and the Bubble golden remains unrelated and untouchable.

- [ ] Capture the promotion golden first: curated presets, hidden technical profile, deterministic FeatureFrame/logical
  replay, representative renderer captures, extreme CUSTOM geometry and silence/vocal/kick/sustained passages.
- [ ] Preserve Sphere descriptor, `sphere_*` state, Settings/presets, logical runtime, section drives, cohort/admission,
  tracer semantics, authored projection and reaction exactly.
- [ ] Replace only duplicate low-level GPU plumbing with Scene3D equivalents when parity is mathematically/visually
  proven: lifetime/fences, frame/target, SSBO/instance transport, common material/light/post and shared particle/shadow
  facilities.
- [ ] Make Sphere an ordinary shared-foundation 3D Visualizer consumer with the standard capability/tier lifecycle.
  Non-selected Sphere remains dormant.
- [ ] Delete superseded Sphere-local low-level infrastructure after parity. Do not keep two implementations “just in
  case”.
- [ ] Only after promotion acceptance may Sphere gain explicit new fidelity options such as richer emissive lighting,
  improved shadows, compute particles or smoke/electric coupling. Output remains SDR-only.

## 8. S20 | vertical consumers | make the substrate earn its complexity

Implement vertical features in this order unless evidence from a preceding slice justifies a swap:

- [ ] **Page Curl** and **Blinds -> 3D Slats**: adaptive-surface/material/shadow proofs.
- [ ] **Extruded Spectrum**: first ordinary shared-foundation 3D Visualizer and SSBO-instancing/material-light proof.
- [ ] **Shockwave Grid**: displaced grid + bounded event SSBO + emissive/bloom proof on the SDR presentation path.
- [ ] **Reactive Particle Field**: compute/compaction/indirect/OIT proof.
- [ ] **Spectrum Terrain / Skyline / Tunnel**, then **Waveform Ribbon** and **Deformable Blob Sphere**.
- [ ] **Accordion Fold**, **Relief Rise**, **Cube Turn**.
- [ ] **Bubble Depth Field** only under Bubble Temporal Fidelity/R-69: depth may not damp, retime or re-author Bubble's
  accepted amplitude/reaction/ghost/tail cadence.
- [ ] Only after primitives are individually accepted, combine them deliberately: electrical storm terrain, smoke-lit
  voxel fracture, ember/dust destruction, refractive glass lit by bolts, volumetric shockwaves and photo-colour IBL.

## 9. Cross-cutting acceptance | applies to every open box above

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
- [ ] **Physical acceptance:** High/Balanced/Performance on both displays with active Visualizers, first-use/warm cost,
  parked memory and representative real photos/music. Sphere gets a dedicated before/after golden before new look work.

## Handoff rules

Significant slices get full superseding GODZIPs. The supplied/latest GODZIP is the working tree authority for handoff
work; do not reconstruct the tree from GitHub. No environment-variable feature gates. No speculative generic engine
layer without a vertical consumer. Rejected experiments are removed rather than kept as fallback architecture.
