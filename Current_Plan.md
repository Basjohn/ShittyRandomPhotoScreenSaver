# SRPSS | Current Plan

Live actionable work only. Exact current source is authority; `Spec.md` and `Docs/Contracts.md` own durable behavior,
subsystem references own technical detail, and source control / `Docs/Historical_Bugs/` retain concluded investigations.
Do not copy this checklist into another plan. Close landed slices here; retain only their genuinely open acceptance debt.

## 0. Execution order and accepted baseline

**Current authorization:** resumed by the operator, 2026-10-13. §1 is source-complete; next complete
§2 FEEDS terminal-failure handling, then stop at that clean checkpoint. Visualizer
migration, graphics expansion, media production and operator builds remain subsequent work. Use reviewed Luna xHigh/Max
or Sol 6.1 Medium agents for bounded work; reserve one High Astra agent for visual parity audits after very significant work.

**Accepted by the operator, 2026-10-12:** Oscilloscope is fully validated; all landed transitions and Foundry tool buttons
are accepted. Dev Curve currently has no observed issue; its earlier replay-floor investigation is closed. Do not reopen
these as pending acceptance or tune their response. Existing Spectrum/Rainbow Ghost, Sphere and source-routing acceptance
stands. Monitor power/wake is a detailed **nonblocking watchlist** (§5), not a reason to request a costly diagnostic build.

**Protected execution rules:** preserve canonical Settings, capability, CUSTOM, render and lifecycle owners; no dormant
polling, new per-frame work, silent non-network fallback or duplicate runtime. Spectrum shaping remains descriptor-owned
(Spectrum, Extruded Spectrum, Shockwave only); Bubble temporal fidelity is binding. Preserve existing startup/reveal and
transition timings. Test the smallest production seam that can falsify the changed contract; no full suite or product
build unless the operator requests it. After each green slice: inspect diff, narrow commit, push, refresh this checklist.
Preserve unrelated local/user work. Agents do not run Nuitka, Build Runner or installers.

## 1. Saver-wide physical display selection | Source checkpoint complete

Physical selection, Settings/draft/import/reset authoring and zero-live-display lifecycle are implemented. Durable
behavior lives in `Docs/Contracts.md` → Geometry / CUSTOM; regression inventory lives in `Docs/TestSuite.md`.
Physical power-cycle observation remains only the nonblocking §5 watchlist. Proceed to §2.

## 2. FEEDS queued/busy and terminal failure | Ready after §1

Busy begins when refresh is accepted, including admission queue time. A queued refresh is not by itself a stranded one.
`widgets/feed_runtime.py` owns source scheduling/leases; `core/feeds` owns neutral source data; the shared refresh gate owns
cross-family admission. `Docs/Reference/Feeds.md` owns provider/startup behavior.

- [ ] **F1 — Trace every terminal path.** Follow accepted request through family/transition queue, worker submission,
  result/error callbacks and GUI publication. Inspect thrown worker exceptions, cancellation, failed submission or GUI
  dispatch, source removal, retirement and stale generation/epoch completions, especially paths without FeedRefreshResult.
  Identify which existing owner must clear busy/in-flight, settle startup and release an admission claim exactly once.
- [ ] **F2 — Fix proven gaps at that owner.** Preserve immediate busy, last-good stories/artwork, NEWS all-publisher cache
  barrier, family startup settlement, source backoff and 2.5-second staggering. A terminal failure must neither leave busy
  true nor finish a newer request. Surface failures loudly; do not add a timer, synthetic successful result, second source
  queue or silent fallback. Keep unrelated services outside the gate until separately audited.
  Read-only production-seam reproduction identified four concrete cases to turn into retained regression tests:
  initial-cache worker failure leaves startup loading/the NEWS barrier open; refresh worker failure clears in-flight but
  leaves presentation busy; artwork worker failure leaves presentation unsettled; and NEWS manual refresh can publish
  settled after one publisher finishes while another remains queued. Trace `_FeedFamilyOwner` worker delivery/finish,
  `FeedRuntimeLease.presentation_settled` and NEWS aggregation in `widgets/feed_runtime.py`. Reopen settlement on accepted
  manual intent and account for `force_refresh_pending`; terminal errors need explicit publication at the existing owner.
  The reproduced refresh/artwork failures released their admission claims: do not describe them as proven stranded gates.
  Submission rejection also clears admission without publishing a terminal outcome; include it in the same generation-fenced
  completion path. Preserve cancellation semantics rather than inventing a provider failure. Separately verify the source
  discrepancy where manual `force` clears/bypasses backoff (`FeedSource.refresh`); reconcile it with the documented backoff
  floor before changing behavior. This last discrepancy is source evidence, not yet a runtime reproduction.
- [ ] **F3 — Fault-injection proof and checkpoint.** Use controlled worker/GUI callbacks to prove queued busy, exception,
  cancel, rejected dispatch, retirement and late-completion behavior, with claims and startup settlement observed through
  production seams. The existing runtime/gate baseline passed 35 tests during inspection; fixes and retained fault-injection
  regressions are still outstanding. Run only relevant FEEDS/gate tests; update contract, commit and push. Stop the resumed run here.
  Real contention attribution/fairness remains a nonblocking Awaiting Logs item in §5.

## 2A. Visualizer spec migration | Subsequent implementation

One mode per slice in this order. Rendering, saved values, Settings appearance/behavior and musical response remain
unchanged. `core/settings/visualizer_mode_settings.py` owns declarations; bespoke shape editors stay Custom entries.
Oscilloscope, Sine Waves and Shockwave are already on the layer; no further Oscilloscope acceptance gate.

- [ ] **V1 — Spline Curve / Dev Curve.** Inventory existing controls, model fields, appliers and renderer inputs; express
  the same controls through the spec and retain bespoke layer/shape editors. Prove round-trip and conditional controls
  using `test_visualizer_mode_settings_spec`; compare fixed recorded response if shared runtime code is touched.
- [ ] **V2 — Extruded Spectrum.** Preserve mode-owned technical settings, preset/custom payload boundaries, 3D controls
  and ordinary/Rainbow Ghost behavior. Migrate only Settings plumbing; keep geometry and render ownership unchanged.
- [ ] **V3 — Spectrum.** Preserve accepted 2D ordinary/Rainbow Ghost source routing and shaping; prove every migrated
  control reaches its current owner once without constructing hidden pages or adding observers.
- [ ] **V4 — Voxel Sphere.** Preserve analysis-only DSP, accepted motion and CUSTOM orbit/geometry; exercise serialization,
  conditional controls and same activation/config projection with mode-specific focused tests.
- [ ] **V5 — Bubble last.** Save a current frozen-settings recorded-clip baseline, migrate controls, then compare
  `python -m tools.visualizer_replay.mode_audit --modes bubble --compare <saved run>`. The existing local baseline is
  `logs/bubble_readings_baseline.json`; verify its inputs before reuse. All readings remain x1.00 unless a separately
  authorized reaction change is intended. Do not use mutable curated presets as goldens or compensate with DSP retuning.

Each slice ends in focused proof, refreshed owner docs and a checkpoint before starting the next mode. New modes use the
spec from their first implementation. Graphics implementation follows §4 after this migration and bounded side work.

## 3. Release media and bounded source cleanup | Subsequent work

The release capture tool is already landed. `Docs/Reference/Release_Media.md` is the single source for input paths,
encoding and manifest policy: genuine UsuScene1–4 originals, transition loops at 480 px wide / 24 fps / authored speed,
high quality and no arbitrary 10 MB cap. Outputs remain outside runtime QRCs and normal Godzips.

- [ ] **RM1 — Reconcile the catalogue at a stable checkpoint.** Enumerate the current registry/meaningful appearance
  variants and compare existing manifest/source hashes. Generate missing or stale entries only; preserve the accepted
  exclusions (Warp Dissolve, Particle, Blinds Flat) unless changed by the operator. Review each new/visually changed
  transition WebP before closing its implementation. Do not fabricate missing local originals or recapture merely
  because the Git revision changed when source inputs did not.
- [ ] **RM2 — Visualizer showcases.** Once the migration/geometry source is stable, capture registered modes' curated
  presets with canonical schema-2 real-music clips through production replay/capture/render ownership. Keep the authored
  reaction, photograph backdrop and reflection inputs; fail loudly for unavailable inputs.
- [ ] **RM3 — Catalogue proof.** Inspect motion/endpoints, loop seams, dimensions, metadata and quality; retain outputs
  and manifests. Verify unchanged inputs skip regeneration, changed source/preset/clip inputs regenerate appropriately,
  and mixed-revision captures are rejected. This is media proof, not another product visual acceptance gate.
- [ ] **SC1 — Retire unused root transitions.direction.** Confirm current caller absence, then forward-strip the root key
  without changing each transition's own direction setting. This changes the operator's defaults: undertake only with
  explicit defaults-change authorization. Prove import/default merge/save cannot resurrect it.
- [ ] **SC2 — Blinds Flat endpoint discrepancy, nonblocking.** Reproduce the prior capture endpoint mismatch at the exact
  production endpoint before deciding whether the defect is in capture or rendering. Landed transitions are accepted;
  do not reopen broad appearance work, change authored behavior or demand another build absent a reproduced defect.

## 4. Graphics decomposition | After migration and bounded side work

Extruded Bubble is the next proposed mode after migration/side work, following the operator's explicit “after migration”
direction. The other mode order is Particle Field → Terrain/Skyline/Tunnel → Waveform Ribbon → Deformable Blob Sphere.
Build only required/proposed primitive slices in the order below; primitive proof does not require inventing a shipping
consumer. Usu runtime remains deferred; its existing plan is `Docs/Future_Work/Usu_Moonscape.md`, not a second queue.

### 4A. Shared facilities — inventory, dependencies and acceptance

`Docs/Reference/Scene3D_Resources.md` owns implemented resource contracts. Existing stream rings, compute/population,
particle sprite/streak draw helpers, scene targets, bloom, trails, edge/propagation fields and planar directional shadow
helpers must be reused, not rebuilt. Their presence does not prove general collision, ribbons, volumetric simulation,
real shadow maps or order-independent transparency already exist.

- [ ] **G0 — Establish exact delta and measurements.** Before each primitive, record current callers/resources and the
  smallest missing contract. Run `tools/overhead_baseline.py` before/after shared edits and compare deterministic GL/Python
  call counts plus control-relative CPU/GPU measures. Existing unrelated consumers must compile/pay for no added feature.
  Extensions use opt-in shader variants/functions and demand-created resources; retire at park/context destruction.
- [ ] **G1 / S17 — Attachments and temporal ownership.** Specify normal/material/depth/history formats, resolution,
  allocation keys, clears, reuse and invalidation for resize/context/generation changes. Implement only demanded
  attachments. Prove disabled paths allocate nothing and reactivation cannot sample stale history.
- [ ] **G2 / S25 — Real shadow maps (the one shared shadow task).** Use one fitted directional depth map with bounded
  soft PCF, bias and caster/receiver contracts; depend on G1 depth ownership. Test known occluder/receiver pixels,
  light/camera changes, resize and retirement, with per-tier measurements. S17 and Usu S25 refer to this same owner;
  it must not reactivate the rejected Extruded cast-shadow path implicitly.
- [ ] **G3 / S17 — Transparency and optics.** Separate weighted blended OIT/depth-aware transparency from refraction.
  Prove compositing/depth restoration first; then thickness/depth refraction, Fresnel, rough transmission and restrained
  dispersion as independently selectable features. GTAO requires a justified visual target and its own measured slice.
- [ ] **G4 / S18 — Particle extensions.** Extend existing CompactedPopulation and sprite/streak helpers with reusable
  ribbons and bounded lifetime/capacity/indirect draw contracts. Add collision/OIT only after demonstrated need and G3
  where applicable. Prove deterministic admission/retirement and zero work for inactive emitters.
- [ ] **G5 / S18 — Lightning, then volumes.** Lightning first gets a bounded procedural geometry/lighting contract and
  independent render/cost proof. Smoke/fog/fire follow as reduced-resolution volumes: separate allocation, advection,
  vorticity, depth raymarch and temporal reprojection slices. Define history reset and quality ceilings before combining
  them. No always-running simulation or permanent volume targets.

### 4B. Extruded Bubble — bounded implementation slices

Reuse Bubble's logical simulation/reaction authority; the original Bubble remains unchanged under Bubble Temporal
Fidelity. This is a bordered 3D mode whose camera moves inside the card, with spec-owned Settings and gradual use of
shared materials, gloss/reflection, shadows, glow, quality tiers and orbit. Read fixed musical loudness, never add dynamic
floors. Aim for sustained-loud-passage drift/speed and response at least as good as Bubble without changing Bubble itself.

- [ ] **EB1 — Visual target and baseline.** Capture frozen-settings Bubble readings on representative recorded quiet,
  transient and sustained-loud passages; define static/moving targets for depth, overlap, lighting and bordered framing.
  Establish CPU/GPU/reference-resolution measurements and acceptance comparisons before renderer implementation.
- [ ] **EB2 — Admission and logical frame contract.** Declare the mode/spec/capabilities; reuse existing logical state or
  a mode-owned projection without a second clock/capture/DSP owner. Identify exactly which state remains shared and what
  depth-only data is derived. Prove original Bubble readings unchanged and inactive mode import/allocation neutrality.
- [ ] **EB3 — Minimal bordered 3D renderer.** Start with instanced lit bubble geometry, depth and card clipping in the
  existing Quick scene. Define perspective camera, border-safe orbit, CUSTOM viewport versus visual-scale intent and
  projection-derived Edit bounds. Test resizing, orbit, display transfer, clipping and context retirement; no second window.
- [ ] **EB4 — Appearance and quality.** Add shared gloss/reflection/glow as opt-in measured increments; real shadows use
  G2 when ready, and transparency uses G3 only if needed. Do not block the minimal renderer on all future facilities or
  duplicate missing primitives locally. Each tier bounds instances/geometry/attachments and releases resources at park.
- [ ] **EB5 — Reaction/customization and acceptance.** Expose spec-owned controls/presets after the frame contract is
  stable. Validate sustained loud passages and onset/quiet behavior on fixed recordings, rerun Bubble parity, and review
  real outputs on both displays before seeking targeted operator acceptance. Generate its release showcase when stable.

### 4C. Remaining modes and character/world substrate

- [ ] **Reactive Particle Field:** compose G4 with recorded musical controls; establish lifetime/capacity and response
  target before adding collision. **Terrain/Skyline/Tunnel:** one bounded geometry/camera slice at a time, preserving
  fixed loudness semantics. **Waveform Ribbon:** require G4 ribbon proof and real waveform history. **Deformable Blob
  Sphere:** establish deformation/normal/geometry bounds and independent cost before layering materials/effects.
- [ ] **S19 → S20:** deterministic validated Blender/glTF bake into provenance-stamped packed assets, then imported
  static-mesh rendering on shared materials/instancing. Runtime reads packed data, not authoring node graphs.
- [ ] **S21 → S22 → S23:** bounded GPU joint palettes/skinning, then logical-time clip sampling/cross-fades/masked
  additive layers/root-motion/eye tracks, then deterministic secondary-motion springs. Prove each in its own offscreen
  harness before combining; no physics engine or separate animation clock.
- [ ] **S24:** opt-in felt/sheen and bounded fuzz shells with emitted-light tips; prove unchanged existing shader variants
  and tier-specific cost. **S25:** reuse G2, never a duplicate shadow implementation.
- [ ] **S27 → S26:** prove independent perspective/orbit camera, then seeded sphere/crater/star geometry and logical
  travel. Preserve the existing photo-plane camera. Asset/rig/clip acceptance stays with the existing Usu plan and local
  asset README; do not admit the deferred full Usu mode merely because a foundation is ready.
- [ ] **Combinations only after component proof:** electrical terrain, smoke-lit fracture, ember/dust destruction,
  refractive glass lit by bolts, volumetric shockwaves and photo-colour IBL. Choose one promoted effect at a time.

## 5. Nonblocking watchlist and operator-owned evidence

These items never hold source work waiting for a diagnostic build. Observe during normal use or an operator-chosen
build/capture; reopen only from the listed symptom/evidence. Record Awaiting Logs/Validation without turning it into
an instruction to rebuild, poll or repeat the full suite.

- [ ] **Monitor power/wake — watchlist, Awaiting Validation when convenient.** During an existing/new operator build,
  observe either display off, >30 seconds on one screen, rapid off/on, reordered return and both selected screens absent.
  Widgets must stay on physical assignments and return with original CUSTOM geometry; no spillover, duplicate owner,
  phantom window or frozen input. Include Settings reassignment and Arrange/Edit/Reset if those paths are exercised.
  First upgraded legacy numeric routes need their intended displays connected unless a unique saved CUSTOM home supplies
  identity. Capture timestamps, remaining physical screen, product flavor and Interaction Mode if an anomaly appears.
  `diagnosticmonitoroffonrapid.zip` demonstrated renumbering/old Visualizer relocation plus a 13:02:16–13:02:30 binding-loss
  stall; source fixes and focused proof are landed (R-79 contains evidence). It showed six completed replacements and
  orderly explicit exit, not a general wake-exit failure. For recurrence, record exact wake/exit input; Interaction Mode
  deliberately suppresses mouse-motion exit. Do not request a full diagnostic build solely for this watchlist.
- [ ] **Refresh contention — Awaiting Logs on recurrence.** Use a naturally available dual-display trace to attribute
  accepted/queued/claimed/published/retired FEEDS/Gmail/Reddit work and transition delays. Existing R163 capture reported
  1–7 second manual delays, but no stranded FEEDS claim was proved. R164 fixed missing False dispatch handling and added
  event-only family attribution. Check fairness/no post-transition stampede; never hide busy during queue time.
  Steam/Weather/Friend Pulse and startup cache readers join no shared gate until their publication/retirement is audited.
- [ ] **Wallpaper RSS after runtime replacement — source audit required.** `engine_lifecycle.stop(exit_app=False)`
  permanently sets the existing RSSCoordinator stop event, while topology replacement reuses that coordinator and does
  not restore its refresh timer. Audit Settings/CUSTOM/topology generation ownership and pending IO drain before deciding
  whether this session owner should resume or be rebuilt. Prove refresh resumes once, with no stale queue publication,
  duplicated session rotation or acquisition while selected displays are absent; keep this separate from FEEDS widgets.
- [ ] **Display Settings scalability — deferred UI cleanup.** The Display tab currently exposes four numbered monitor
  checkboxes. Resolver/persistence and ALL support larger topologies; replace that fixed UI capacity with current-screen
  rows before claiming full explicit selection authoring for more than four displays. Preserve unavailable choices and
  physical bindings through the same authoring boundary; no runtime/provider changes are needed.
- [ ] **Cross-display Media shortcuts — Awaiting Validation when used.** Media on the other display should receive each
  shortcut once; source regression is green. Do not build solely for this check.
- [ ] **Music recorder — Awaiting Validation of capture, not its accepted launch buttons.** When recording is needed,
  capture a named 60-second real-music clip; check signal, file/result, cancellation and mixed-DPR window behavior.
  Use full-history/schema-2 recordings for waveform proof; format/commands live in `Docs/Reference/Harness_Index.md`.
- [ ] **Frozen release gate — operator scheduled.** Operator chooses when to build Standard (+ Diagnostic from the same
  compile), Media Center and Reddit Helper, then checks installed startup/exit, Settings/widgets/cache/audio and installer
  behavior. Agents analyze supplied logs and fix concrete failures with focused tests; no speculative builds or automatic
  four-chunk rerun. Python 3.14/Qt 6.11 cutover and accepted Ban Image behavior are not reopened absent a new defect.
- [ ] **Bubble small-radius judder:** reopen only on new recorded musical/scale/DPR evidence; R-105 holds failed methods.
  **Dual-display reboot incident:** capture DWM/driver/Qt swap evidence before reboot if it recurs; don't attribute prior
  recovery to an unproved patch. **CUSTOM/Extruded or long-duration lifecycle:** reopen only from a concrete new symptom.
  The unrelated 90 Hz versus 60 Hz investigation remains off limits.

## Handoff rules

Use single-line, direct-copy PowerShell commands with explicit `.venv\Scripts\python.exe` when providing operator
commands. For an explicitly requested archive handoff, supply a whole-file superseding Godzip with final-byte manifest
validation; ordinary commits do not require an archive. Keep user assets, bulk logs and release media out of normal
Godzips. No memory updates without an explicit user request.
