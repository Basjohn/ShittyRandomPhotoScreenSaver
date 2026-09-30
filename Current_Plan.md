# SRPSS | Current Plan

Active development work only. Implemented features keep their open physical acceptance in their own reference
(`Docs/Reference/Guided_Setup.md`, `Docs/Reference/Feeds.md`, `Docs/Reference/Transitions.md`); closed plans and
audits are historicalised. Work this file **top to bottom** unless the operator explicitly redirects it. Commit and
push coherent slices; preserve accepted visual/temporal contracts unless a slice explicitly authorises a look change.

## 0. GODZIP Foundry handoff tooling | LANDED IN THIS HANDOFF

- [x] **DIFF → LOCAL vs GIT HEAD.** The Foundry now has a first-class non-mutating local-worktree diff. It compares
  HEAD to the bytes actually on disk, including staged, unstaged, untracked and deleted non-ignored files. A staged
  file edited again therefore reports HEAD → the later local bytes, not merely HEAD → index.
- [x] **Agent/headless DIFF CLI.** `python tools/godzip_foundry.py --diff-local` prints the local diff and exits;
  `--diff-godzip <zip>` does the existing GODZIP→local comparison without opening the GUI; `--diff-output <path>`
  writes either result to a file instead of stdout. No Git/repo mutation is performed by either path.
- [ ] Installed Windows acceptance only: open DIFF, run LOCAL vs GIT HEAD on a deliberately dirty repo, then compare
  the result to the CLI form. The core unit bars cover complete HEAD→disk semantics; GUI acceptance is visual only.

## 1. P0 | implementation complete; ordinary-use observations remain non-blocking

The latest supplied two-display logs (2026-10-01 00:08–00:11) are the accepted evidence input:
17 matched prefetch handoffs, no orphan markers, three late Visualizer render intervals overlapping handoff,
and 19/19 shared-memory segments consumed with none left live. No 30-transition trace is requested.

The bounded correction retains one owned RGBA copy but performs it through native `ctypes.memmove`, releasing the
GIL while the supervisor lease pins the source. Byte ownership/transport tests pass. The 50-cycle probe consumed
50 transfers and reclaimed one shutdown transfer with zero live mappings. Copy wall time was 29.81 ms median /
35.54 ms p95, versus the earlier 26.70 / 30.16 ms: this is GIL contention relief, not demonstrated wall-time speedup.
Durable ownership is in `Docs/Contracts.md`; commands are in `Docs/Reference/Harness_Index.md`.

- [~] **Awaiting ordinary-use observation, non-blocking:** inspect any subsequently supplied logs for repeatable
  post-transition Visualizer handoff overlap. Do not demand a fixed transition count or another dedicated trace
  before continuing. Existing logs establish the correction's motivation, not post-correction visual acceptance.

## 2. Build Runner safety + diagnostic cleanup | implementation complete

Windows builds now launch suspended, enter one kill-on-close Job Object, and then resume. Emergency Stop and
shutdown fence queued work and report operator abort separately. Lifecycle, queued cancellation, rerun and real
parent/child termination tests pass. Diagnostic publishes SCR directly; its installer and EXE opt-out are retired.
Durable ownership and product shape are in `Spec.md` → Build control and products.

- [~] **Operator-owned build acceptance, non-blocking:** when the operator next builds, exercise Diagnostic SCR,
  Standard/MC, a forced stop with an active child, and a subsequent clean build in the same runner session.
  The agent must not run build scripts or wait for builds before renderer work. Preserve intentional Jobs=3/4/5.
- [~] **Packaging audit follow-up, operator artifacts only:** existing MC output is 610 MB, including 191 MB of
  WebEngine despite no source imports. It still contains Qt 6.9.1, and no Nuitka report is retained. When a normal
  operator 6.11.2 build supplies a report, trace why those modules were included before proposing exclusions.
  Standard/Diagnostic are about 169 MB each; helper is 25 MB and already excludes the product stack.
  No includes/excludes or Jobs were changed; package-policy changes still require operator approval.
- [~] **Normal-mode interpreter, operator admin action:** `C:\Python311` remains at Qt/PySide 6.9.1 because its launcher
  files require administrator access. The attempted upgrade was restored. Upgrade that interpreter's four Qt pins
  to `requirements.txt` before using Normal mode; the actual project `.venv` is 6.11.2. This does not block source work.

## 3. Renderer-era hard jump | implementation landed; combined regression pending

The actual project `.venv` loads PySide/Qt/shiboken 6.11.2 and passes pip check. Production requests OpenGL 4.6 Core
with GLSL 460; startup validates actual context capabilities before the first image and rejects incompatibility.
The RTX 4090 probe reports GL 4.6 / GLSL 4.60. Swap interval remains zero and OpenGL remains the sole graphics API.
Focused driver, texture, clipping, startup and lifecycle checks pass. The initial broad run exposed test-isolation
and graphics-bootstrap gaps; those were corrected at the test owners, preserving strict production validation.

- [ ] Run final combined regression after the active asset/timezone slice stabilizes. Include the real native-image,
  texture-retention and queued-quit probes (parallel source edits interrupted their last rerun), then the full chunks.
- [~] **Awaiting ordinary-use physical validation, non-blocking:** preserve gentle start, transition endpoints,
  Bubble reaction, Visualizer freshness and no black flash on two displays. Compare subsequently supplied warm
  performance logs with the existing evidence; no fixed trace count or agent-run builds are required.

## 3A. Immutable resources and timezone cleanup | active operator side quest

- [ ] Inventory and reorganize immutable application assets by ownership before changing runtime paths; record
  current QRC/source sizes and loose installed file/byte counts. Themes, presets and user/generated material remain loose.
- [ ] Promote the existing `ui/resources/assets.qrc` to one canonical immutable resource namespace, migrate Qt/QML
  consumers, regenerate bindings with the selected Qt 6.11 toolchain, and remove duplicate loose runtime copies.
  Retain a filesystem exception only for a proven consumer; no blanket extraction, polling or eager image decoding.
- [ ] Add one automatic QRC prerequisite to canonical builds: selected interpreter/toolchain, cheap stale detection,
  no repeated regeneration in an unchanged multi-job run, loud failure, and cancellation owned by Build Runner.
- [ ] Remove obsolete immutable asset packaging/preflight rules across Standard, MC, Diagnostic and installers;
  preserve editable themes/presets and intentional Jobs=3/4/5. Do not run product build scripts.
- [ ] Prove whether Qt 6.11 timezone facilities can replace pytz while preserving local/UTC/explicit offsets,
  named world zones, existing persisted names and DST. Migrate one canonical authority only if parity is proven.
- [ ] Validate focused asset/render/build/timezone contracts, then the broad practical regression boundary. Report
  QRC counts/generated size/import cost, prospective loose-payload counts/bytes, and timezone before/after evidence.
  Actual frozen-binary/install deltas require the next operator build and remain explicitly unmeasured meanwhile.
- [ ] Refresh stale two-lane asset contracts in Spec/widget guidelines and all moved source references. Record any
  retained immutable filesystem asset with its concrete consumer requirement.

## 4. Modern OpenGL 4.6 scene3d expansion | active

Detailed decomposition and acceptance bars live in `Docs/Future_Work/3D_Scene_Foundation.md`. Every facility is lazy:
when no active transition/Visualizer asks for it, it owns no buffers, targets, compute dispatches, history, workers,
forced frames or cadence.

- [ ] **Finish Motion Trails CPU cleanup** from the previous foundation plan: set invariant uniforms once per trail pass
  and vary only ghost time/fade; measure the known +0.5–1.0 ms CPU submit cost before/after.
- [ ] **Direct State Access + immutable storage + multi-bind.** Remove unnecessary bind/query ceremony from new shared
  resources and migrate existing scene3d owners where identity tests prove no look change. This is especially valuable
  in Python because every avoidable GL call has submission/GIL cost.
- [ ] **Persistent mapped ring buffers + fences.** Add a bounded shared stream allocator for genuinely changing small
  frame data; never map/unmap or allocate per frame. Use it only where measurement beats the current orphan/subdata
  path.
- [ ] **SSBO foundation.** Structured instance/event/history/material data, generated from one schema where practical;
  bounded counts and explicit retirement. Prefer SSBOs over texture-table contortions for new structured 3D state.
- [ ] **Compute + image load/store + atomics.** Shared dispatch helpers, barriers and deterministic test harnesses for
  GPU procedural preparation, compaction, particles, volume fields and post work. Rendering may never become a second
  simulation clock: transition compute derives from run time; Visualizer compute consumes logical revision/time and
  bounded immutable snapshot inputs.
- [ ] **Indirect/multi-draw path.** GPU-generated instance counts and compacted visible/emissive work may feed indirect
  draws where it removes Python draw/loop cost. No indirect machinery for effects that are already one cheap draw.
- [ ] **Diagnostics only:** KHR_debug/debug groups and GPU timer-query helpers under explicit diagnostics. Never add
  ordinary-runtime readbacks, query polling or logging churn.
- [ ] **Active-only richer targets:** optional RGBA16F HDR, normal/material/depth attachments, history/velocity and
  half/quarter-resolution work surfaces. Allocate only when the requesting effect actually enables a feature that uses
  them; `park()`/mode retirement releases them.

## 5. Shared high-fidelity 3D capabilities | active after the GL substrate

- [ ] **Lighting/materials:** energy-conserving GGX/Cook-Torrance BRDF, roughness/metalness/specular controls, multiple
  bounded point/spot/directional lights, emissive contribution, BRDF LUT, photo/environment IBL, optional normal maps,
  and a common material block. Existing looks remain opt-in/pixel-protected; this does not retroactively relight
  accepted effects without operator approval.
- [ ] **Shadows/AO:** reusable depth shadow maps for real 3D scenes, PCF/PCSS-style softening where justified, contact
  shadows and optional screen-space/GTAO-style ambient occlusion. Keep the existing cheap planar shadow for effects
  where it is the better tool.
- [ ] **Glass/refraction:** depth/thickness-aware screen-space refraction, Fresnel reflection, rough transmission and
  optional restrained dispersion. Never sample or mutate the lent PR-04 presentation texture illegally; use owned
  scene/environment copies where required.
- [ ] **Transparent composition:** depth-aware soft particles plus weighted blended order-independent transparency for
  smoke/sparks/glass-heavy scenes where sorting would otherwise become CPU work.
- [ ] **Adaptive surfaces:** shared tessellation/displacement hooks or compute-generated surface data for Page Curl,
  Relief Rise, terrain, ribbons and deformable bodies when they beat a fixed dense grid. Geometry shaders are not a
  preferred general path; use them only with measured justification.
- [ ] **Post stack:** HDR tone mapping, bloom improvements, depth of field, heat haze/distortion, chromatic treatment,
  temporal accumulation/reprojection and compute filters only where the visual feature needs them. Existing exact
  transition endpoints and still-scene identity remain binding.

## 6. Voxel Sphere promotion onto the shared 3D substrate | active

This is a **yes** to eliminating competing low-level 3D architectures, not permission to redesign Sphere.
`Docs/Reference/Sphere_Visualizer.md` remains its behavioural golden.

- [ ] Capture the existing Sphere promotion golden first: curated presets, hidden technical profile, deterministic
  FeatureFrame/logical outputs, representative renderer captures, extreme CUSTOM aspect/scale, silence/vocal/kick/
  sustained passages and accepted particle/tracer behaviour.
- [ ] Keep Sphere's `sphere_*` state, Settings, presets, logical runtime, cohort/admission rules, tracer semantics,
  section drives and authored material choices private. **Do not turn Sphere into a generic base class.**
- [ ] Move only generic GPU plumbing onto `rendering/quick/scene3d/`: resource allocation/retirement, frame/target,
  camera/projection helpers where mathematically identical, SSBO/instance transport, common material/light blocks,
  post stack, shared particle/shadow facilities where they can reproduce the golden exactly.
- [ ] Make Sphere participate in the ordinary Visualizer 3D capability/tier lifecycle rather than maintaining a second
  bespoke resource architecture. Dormant/non-selected Sphere still costs nothing meaningful.
- [ ] After parity is proven, delete superseded Sphere-local low-level resource/fence/utility code. Do not retain two
  implementations "just in case".
- [ ] Only after parity may Sphere opt into new high-fidelity features (HDR emissive light, real light interaction,
  improved shadowing, compute particles, smoke/electric interactions) as explicit settings/preset changes.

## 7. Lightning, particles, smoke and other high-fidelity effect work | active

Build vertical consumers and let them prove which shared primitives deserve permanence. Every item must have an Off/
quality tier or be confined to a mode/effect that is itself dormant when not selected.

- [ ] **GPU particle system:** SSBO particle pool with deterministic seeded spawn, compute evaluation/compaction,
  indirect instanced draw, depth-aware soft sprites, streak/ribbon variants, bounded collision against simple analytic
  planes/spheres/SDFs, and optional OIT. Transition particles derive from run progress; Visualizer particles step only
  from logical revisions or are analytically reconstructed from bounded event history.
- [ ] **Lightning/electricity:** seeded branching bolts with stable topology during an admitted event, animated travel/
  fork intensity, emissive hot core + bloom, secondary arcs between pieces/voxels, short-lived afterglow and optional
  light injection into nearby geometry/smoke. No CPU object per branch and no random re-topology every render frame.
- [ ] **Smoke/fog/fire:** active-only half/quarter-resolution density/temperature field or procedural volume, curl-noise
  advection/vorticity where worthwhile, compute injection from authored events, depth-aware raymarch, temporal
  reprojection with bounded history, scene-light absorption/scattering and emissive fire/embers. Quality tiers bound
  volume resolution and ray steps; disabled means no volume allocation/dispatch.
- [ ] **Volumetric/energy fields:** shockwaves, force fields, heat haze, nebula/plasma and reaction-diffusion style
  surfaces driven from deterministic event/history inputs; use image load/store/compute rather than parent CPU loops.
- [ ] **High-fidelity debris/destruction:** GPU compaction for active pieces, per-piece material variation, sparks/dust,
  contact light/shadow interaction and smoke coupling without increasing dormant cost.
- [ ] **Screen-space depth effects:** selective SSR/contact reflections, refraction and depth fog only for scenes that
  produce the needed depth/normal attachments; never turn them into a full-time compositor tax.

### First vertical consumers after the substrate

- [ ] **Page Curl** and **Blinds → 3D Slats** to exercise adaptive surfaces/material/shadow paths.
- [ ] **Extruded Spectrum** as the first ordinary shared-foundation 3D Visualizer and SSBO-instancing proof.
- [ ] **Shockwave Grid** to exercise grid displacement + bounded event SSBOs + emissive/bloom.
- [ ] **Reactive Particle Field** as the particle/compute/OIT proof.
- [ ] **Spectrum Terrain / Skyline / Tunnel**, **Waveform Ribbon**, **Deformable Blob Sphere**, **Accordion Fold**,
  **Relief Rise**, **Cube Turn**, then **Bubble Depth Field** subject to Bubble's golden temporal/amplitude contract.
- [ ] Add deliberately spectacular combinations only after primitive costs are measured: electrical storm over a
  spectrum terrain, smoke-lit voxel fracture, ember/dust destruction, refractive glass with lightning illumination,
  volumetric shockwaves and photo-colour environment response.

## 8. Memory, handles and existing non-3D open items

- [ ] **ImageWorker lean entry (R-99).** The ImageWorker re-imports the whole app graph on `spawn` (~1,060 modules).
  After P0 proves the new worker derivative path, create a lean worker entry if Nuitka multiprocessing proves it can
  save the measured ~100 MB resident without duplicating worker ownership.
- [ ] **`--usage` sampler diagnostics cost.** Re-evaluate on PySide 6.11.2/current tree; if collection still contaminates
  frame evidence, keep it excluded from acceptance or move remaining Python work out of the GIL-held interval.
- [ ] **Gmail refresh handle slope.** Classify with `--handle-attribution`, then fix at the owning resource.
- [ ] **Widgets-tab stale position estimates.** Move warnings to measured family-QML preferred sizes only if doing so is
  lazy on the Widgets tab; otherwise retire the QWidget-era formulas.
- [ ] **Overfull authored display planner.** Reduce/memoize `_free_edge_candidates` while preserving placements.
- [ ] **Weather child-edit loading height.** Preserve ready/content sizing for child-only edits or reserve the ready
  height; validate on a never-cached/offline Weather card.

## Known failing tests and anomalies

- [ ] **Pre-existing Qt test suppression:** `tests/conftest.py` broadly filters slot-miss AttributeErrors. Reproduce
  cross-generation background/Visualizer `sceneGraphInvalidated` retirement in a bounded unfiltered test, then
  narrow the suppression at the owning lifetime boundary. Real subprocess GL/lifetime probes remain unfiltered.
- [ ] **Global Python cleanup:** the denied Normal-mode Qt upgrade left pip `~yside6-essentials` rollback metadata;
  the original 6.9.1 modules were restored and verified. Global pip also reports the unchanged opencv/numpy version
  conflict. Resolve these in operator environment maintenance; the project `.venv` passes pip check.

- [ ] **Temporary validation debris:** `.artifacts/qt611-validation` and `.artifacts/qt-restore` are unused after the
  actual `.venv` upgrade. Automatic approval review blocked their requested deletion; remove during operator cleanup.

- [ ] **Spectrum extreme-viewport smoothness (pre-existing).** The 2026-09-23 physical run showed reduced Spectrum
  smoothness at extreme viewport shapes. Keep separate from the modern-GL migration unless a new shared 3D consumer
  provides direct evidence relevant to it.

## Handoff and regression rules

When accepted behaviour changes, select only the relevant targeted tests and physical observations; do not re-accept
unrelated OSD/Media/widget systems. Significant slices get full superseding GODZIPs. No environment-variable feature
gates: use existing Settings/descriptor authority or explicit CLI diagnostics. No new scheduler/poller/timer merely to
feed rendering. Qt Quick remains presentation/scheduling authority; latest-wins/coalesced admission and per-display
transition gating remain binding.
