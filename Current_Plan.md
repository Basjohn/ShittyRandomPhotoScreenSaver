# Current Plan — Active Work

Last updated: 2026-09-11

Outside of Codex Work Began: `886e6fa419ff130ff2a9aedf5091ae6162d1e958`

The Qt Quick migration is closed and operator-accepted. This file contains **active work only**; completed Gmail lifecycle, widget resize/Edit lifetime, non-CUSTOM auto-shrink, Weather binding-loop validation, Visualizer replay-floor work, and other accepted closeout items are intentionally absent.

---

## 1. Voxel Sphere accepted-experimental polish

Execution authority: `Docs/Future_Work/Sphere_Visualizer_Decomposition.md`.

Sphere is now **accepted experimental and deliberately isolated**. Its current reactivity/motion is a golden preservation target; acceptance does not authorize migration into permanent/shared visualizer architecture. All experimental modes remain isolated until the operator explicitly activates migration.

- [x] Consolidate the only useful Sphere presets: former 5 -> **Preset 1 / Glass Current**; former 6 -> **Preset 2 / Voxel Bloom**. Preserve their literal authored snapshots.
- [x] Rebuild the Sphere Custom UI around shared themed circular checkboxes and real collapsible buckets while keeping every setting Sphere-owned.
- [x] Trace and retire dead Sphere controls: Block Relief, Bass Response, Mid Response, High Response, Energy Curve and Idle Drift are removed from canonical UI/model/default/config state and forward-stripped. Base Rotation remains the sole idle rotation authority.
- [x] Retire rejected **Rainbow Ghosting** completely: Settings/default/model/UI/binding/config/render-history path removed; stale imported state is forward-stripped. This does not wire Sphere into generic Taste The Rainbow.
- [x] Record the reusable part of the experimental architecture: descriptor-driven lazy builder/runtime/renderer/capture resolution, independent dormancy/retirement, private settings prefix and explicit shared-family opt-outs. Preserve this host seam for future experiments; do not generalize Sphere internals.
- [x] Record the permanent-migration gate as dormant future work. Both curated presets require pre/post deterministic replay/capture goldens, including the exact hidden technical-profile values that reproduce current behaviour. Any regression to permanent modes' reactivity, latency, fidelity, bleed/isolation, cadence, lifecycle or resource/dormancy behaviour rejects migration.
- [x] Add themed recommended-position slider notches using the accepted Glass Current baseline as UI guidance only; no default/runtime authority.
- [x] Split the overloaded Deformation × Block Reactivity contract without retuning: **Fragment Strength** owns the exact former product and **Particle Distance** owns the former Deformation travel-distance value. Visualizer schema v8 forward-migrates old Custom/persisted state before stripping the legacy keys.
- [x] Add **Particle Amount** as a post-admission stable-population multiplier (`1.0` = accepted behaviour); rename the UI-only Intake Density label to **Particle Density Response**. No onset/admission/velocity threshold changes.
- [x] Trim dead slider tails without changing resolved behaviour: Vocal Response max `1.35`; Size Response max `2.54` (existing growth saturation). Curated presets are rewritten to the equivalent resolved values.
- [x] Add Sphere-local **Taste The Rainbow** with independent Surfaces/Edges sub-controls. It uses one moving partial-spectrum field in the existing voxel draw, preserves authored Fill/Edge alpha, and does not opt Sphere into the shared Rainbow family or add a timer/poller/worker/history pass.
- [x] Add **Perspective Strength** as a Sphere-local presentation control constrained to `0..1`: `1.0` is the accepted projection exactly and lower values only flatten toward orthographic, so the control cannot exceed the current golden perspective/overflow envelope. Both curated presets remain `1.0`.
- [x] Sweep active documentation for stale/duplicate Sphere-era authority; remove the two superseded Future Work documents while leaving Historical Bugs untouched.
- [x] Preserve user-authored visualizer preset ownership: sparse authored slot numbers are valid, runtime compacts them without renaming/deleting files, Edit Preset retains the real backing path, and Save-As appends after the highest authored number rather than assuming contiguous slots. Shipped manifests are never runtime authority over user presets.
- [x] Make lazy visualizer Settings-body construction transactional: a failed builder/hydration attempt removes its partial body before rethrow, stale retry bodies are de-duplicated by a mode marker, and non-Custom presets never transiently expose Custom/Advanced controls.
- [x] Close Sphere bucket-state schema drift: the new appearance/particle-flow/reactivity/rotation/effects bucket identities are registered in canonical `ui.visualizer_bucket_states`; JSON/SST defaults are regenerated; a Qt-free builder/schema contract now prevents future bucket renames from escaping canonical defaults.
- [x] Log-audit the post-split physical run before further renderer work. Detached cohort velocity remains granular (239 distinct observed maxima); captured low/mid/high-impact motion remains strongly ordered (~0.25 / ~0.45 / ~0.93 mean motion respectively), with continuous body/section/rotation outputs rather than a 0/1 collapse. The control split therefore shows no evidence of reactivity/fidelity regression in this run.
- [x] Add presentation-only Sphere controls without changing accepted defaults: **Edge Weight** (`1.0` = prior fixed thresholds), **Voxel Size Variation** (`0.35` = prior fixed shader constant), **Tracer Color** (`[255,242,194,255]` maps exactly to the former shader `(1.0, 0.95, 0.76)`), and optional **Depth Shading** (default off; suggested strength `0.20`). All remain in the existing Sphere draw and private `sphere_*` parameter bundle.
- [x] Replace the obsolete circular Sphere shadow proxy with a **projected voxel silhouette** using the exact same Sphere vertex shader/instance transforms as the hero draw. Shadow Opacity/Softness/Distance/Size are Sphere-local optional controls; `1.0 / 0.18 / 1.0 / 1.0` are the starting values. Softness uses at most one cheap expanded instanced layer; no shadow map, FBO blur, mutual voxel lighting, per-voxel Python state, worker or cadence is introduced.
- [x] Re-audit experimental isolation after the presentation additions: the mode descriptor, Sphere capture/runtime, BeatEngine/shared logical runtime, and every permanent-mode renderer/runtime remain byte-identical to the pre-visual-polish checkpoint. The only shared config-file edit is confined to the existing `_SPHERE_PARAMETER_KEYS`/Sphere apply block. The documented migration gate remains dormant and requires operator activation plus pre/post Sphere and permanent-mode replay/capture evidence.
- [x] Correct detached-particle population granularity without weakening loud-passage transients: absolute passage loudness no longer owns cohort density. Qualified events keep the accepted 28% visible participation floor, then event confidence + Sphere-local granular motion evidence shape population through a convex curve; 100% density requires both authorities to max rather than merely occurring in loud material. Add a hard current near-silence authoring floor (`0.075`) beneath the existing `0.090/0.042` hysteretic gate so stale/latched typed evidence cannot author a new cohort from perceptually silent residual signal. Event admission thresholds, acoustic-motion authority, travel speed/amplitude, and loud-bed kick/vocal eligibility remain unchanged.
- [x] Focused validation through particle granularity and projected-shadow work is **85/85** in the working tree. Canonical defaults authority is clean. Settings persistence collection remains blocked in this Linux workspace only by missing `PySide6`; rerun the same focused gate against the extracted GODZIP before delivery.

Protected behaviour remains the 2026-09-10 accepted detached-cohort/onset/tracer/four-corner/vocal-recoil contract. Do not retune those mechanics during presentation polish.

## 2. `dark.qss` retirement → ThemeSpec sole authority

Execution authority: `Docs/Future_Work/Settings_Dark_QSS_Retirement.md`.

Migrate the Settings dialog's remaining colour **and** structure authority out of
`themes/dark.qss` into `SettingsThemeSpec`, leaving ThemeSpec as the sole Settings GUI
style authority. Preserve the accepted dark-theme appearance and eliminate the
competing stylesheet authority completely.

- [ ] Inventory every remaining selector/property in `themes/dark.qss` against current
  `SettingsThemeSpec` ownership.
- [ ] Move required structural and colour semantics into the ThemeSpec-backed path
  without creating a second fallback authority.
- [ ] Delete `themes/dark.qss` once no runtime/build path requires it.
- [ ] Preserve dark-theme appearance with focused regression coverage and physical
  Settings GUI validation.
- [ ] Confirm widget themes/runtime theming remain unaffected by the Settings-only
  authority retirement.

---

## 3. Test / debris reconciliation

Owned in detail by `Docs/TestSuite.md` and `Future_Cleanup.md`.

- [x] Delete the caller-dead `widgets/spotify_visualizer/renderers/` island and
  `rendering/image_processor.py`. Surviving Spectrum/Sine/DevCurve/image-processing
  coverage is rehomed to new current-owner tests; a new removal gate replaces the
  previously relaxed museum-owner assertions without editing an old test file.
- [x] Normalize collapsible Settings bucket UX/persistence: Spectrum Custom's stable
  Bar Appearance/Rainbow accessories are real buckets; canonical bucket defaults are
  all closed; persistence is sparse and remembers at most one open identity per local
  scope; shared synchronous peer closure introduces no timer/poller/animation owner.
  Functional work is closed; remaining coverage belongs to the broad test reconciliation below.
- [x] Paranoid bucket reachability/duplication audit: no newly unreachable control path found; outer Visualizer
  Advanced/Technical remain independent parent disclosures; Technical AGC/Transient are now real one-open sparse
  child buckets; Widget deferred-body finalization has one shared owner; seven copied finalizers and stale Gmail/
  Spectrum-eager prose were removed. Setup pills, About and Accessibility remain explicitly outside the bucket
  contract. Three stale mixed test modules were rehomed to new current modules and staged as debris rather than
  teaching production code obsolete multi-open/default-open behavior. Final Qt-free contract is 13/13, unified defaults
  artifact verification and whole-tree syntax compilation are green. Functional work is closed; only test reconciliation remains.
- [x] Small 2026-09-11 presentation/edit polish: Achievement Pulse percentage text is reduced without changing
  authored card/pulse geometry, the pulse rail is raised 4 px, Shelf Style canonicalizes missing Playtime/Previous values to the
  same `UNAVAILABLE` presentation, CUSTOM move editing gains a narrow external 30 px peer-margin snag plus a small 3 px
  semantic scoring bias so existing edge/centre/peer alignment is actually felt without overriding ordinary grid dragging,
  and Particle Random's intermittent broken Swirl case is traced to Center Outward's linear atan
  branch cut. Only that periodic ordering term is repaired; the other Particle modes remain untouched. Particle light/build-order
  labels now match their existing persisted shader indices (NW/NE/Front/SW/SE; Typical/Center Outward/Edges Inward).
- [x] Achievement Pulse percentage visual follow-up after installed screenshot: the earlier 10% `font.pointSize` ceiling change
  could be masked by `Text.HorizontalFit`, so the three retained percentage glyph layers now receive one final 0.90 presentation
  scale after fitting. The existing 4 px pulse lift, 108x108 pulse, authored card geometry, Total calculation and Python
  normalization/layout owners are unchanged. Physical installed visual confirmation remains test evidence only, not open product work.
- [x] First-run missing-source launch continuity: a normal RUN launch interrupted by the source onboarding Settings dialog now resumes the same RUN process after sources are configured instead of returning through CONFIG and exiting. CONFIG-only invocations (`/c`, `-c`, `-s`, `--s`) retain Settings-only lifetime. Startup-dependent settings are re-read after onboarding commits. Functional work is closed; only physical Windows/PySide launch validation remains.
- [x] Normalize Visualizer per-mode dormancy to the same explicit boolean-map shape as Transition activation: `widgets.spotify_visualizer.mode_activation.<stable_mode_id>` is the sole current persisted authority; `enabled_modes` is derived in memory only. Existing profiles get one pre-default forward migration so their authored dormancy is not lost, and the retired key is removed immediately. Defaults/SST projections use only the new map. Functional work is closed; physical Settings toggle/persistence validation remains part of the test inventory.
- [x] Repair the retained Weather missing-location **SETTINGS** shortcut: `weather_location` now flows through the ordinary family adapter into DisplayManager's generation-checked semantic Settings request and the existing engine teardown/destruction barrier, then opens Widgets -> Weather and focuses Location. No direct dialog owner, timer, poller or Weather-specific lifecycle path was added. Functional work is closed; physical retained-QML click/restart validation remains.
- [ ] **Temporary migration debris — retire after safe profile-migration proof:** remove the `enabled_modes` compatibility signature (`migrate_legacy_enabled_modes_to_activation`, the pre-default SettingsManager migration hook, and its warning path) once migration tests plus intended Windows/profile validation demonstrate supported persisted profiles no longer rely on the retired list. Until then it is migration-only: current defaults/model/UI/runtime must never write or consume `enabled_modes` as product state.
- [ ] Run the broad `pytest tests/` inventory and reconcile remaining stale
  widget-glow / two-phase-retirement / defaults casualties against current owners.
- [ ] Reconcile nine Clock presentation tests whose shadow fixtures omit current
  required fields. Do **not** add production defaults merely to satisfy old fixtures.
- [ ] Reconcile 21 scene-controller cases whose fixtures omit the 11 current required
  style arguments.

---

## Standing guardrails

- **Visualizer fidelity / scaling (R-69, binding):** extreme CUSTOM geometry must
  never be solved by globally reducing head radius, authored reaction amplitude,
  motion, Ghost/history displacement, or by adding a second viewport/domain
  compensation that makes wide/tall modes less reactive. Bubble is the golden
  reference; tall-Spectrum response protection is equally binding.
- **Live CUSTOM ownership:** CUSTOM outer geometry is Python/session-owned; QML
  reports gesture intent only. One operation publishes one coherent
  rectangle/extent/scale. Visualizer sides = one-axis viewport extent; corners =
  independent X/Y extent; wheel = uniform whole-Visualizer scale. **Save is not a
  teardown boundary.**
- **CUSTOM is global layout mode:** the first widget entering CUSTOM disables authored
  stacking/adjacency globally, including number-key saved-layout load. Visualizer
  preset `Custom` is a separate concept.
- **Media ownership:** GSMTC/event ownership is primary; no fast Media polling or
  process-probe fallbacks. Visualizer consumes Media admission but never acquires a
  second Media owner.
- **Performance admission:** freshness/reactivity and latency-tail quality outrank
  prettier aggregate counters; no optimization may silently lower authored quality;
  prefer fewer/event-owned mechanisms over polling. See
  `Docs/Guardrails/Performance_Optimization_Contract.md`.
- **Defaults SSOT:** `core/settings/default_settings.py` is the sole authority;
  `.json`/`.sst` are derived and audit-gated. Never add a second default authority.
- **Visualizer preset ownership:** per-mode preset files are user-authored state. Users may add arbitrary counts, delete down to one, and leave sparse authored numbers. Runtime compacts them into slider positions without renaming/deleting files. A shipped preset manifest is packaging/reconciliation metadata, never runtime authority over user-authored presets.
- **No fallback architecture:** failures should remain explicit and diagnosable; do
  not solve closeout work by adding silent fallback ownership, timers, or pollers.

## Authority order

```text
exact current source + current reconciled test tree
-> Current_Plan.md (this file: active work + order)
-> Spec.md
-> FWPlan.md (future / non-blocking implementation)
-> Future_Cleanup.md / Docs/TestSuite.md (cleanup + test truth)
-> Index.md + focused/decomposition docs
```

## Durable references

- `Index.md` — routing map to current owners.
- `Docs/TestSuite.md`
- `Future_Cleanup.md`
- `FWPlan.md`
- `Docs/Future_Work/Settings_Dark_QSS_Retirement.md`
