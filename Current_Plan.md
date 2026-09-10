# Current Plan — Active Work

Last updated: 2026-09-10

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
- [x] Focused validation after approved control/rainbow cleanup + sparse-preset + bucket-schema regressions: Sphere/geometry/technical-profile/user-preset/body-transaction/bucket-contract gate **82 passed**; full Python source compile clean; canonical JSON/SST defaults match. Settings persistence collection remains blocked in this Linux workspace only by missing `PySide6`.
- [ ] Deferred presentation-only candidates (Edge Weight, Voxel Size Variation, Shadow controls, Tracer Colour, Depth Cue) remain unimplemented pending operator decision; do not maintain a separate proposal specification in docs.

Protected behaviour remains the 2026-09-10 accepted detached-cohort/onset/tracer/four-corner/vocal-recoil contract. Do not retune those mechanics during presentation polish.

## 2. `dark.qss` retirement → ThemeSpec sole authority

Execution authority: `Docs/Settings_Dark_QSS_Retirement.md`.

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

- [ ] Delete the caller-dead `widgets/spotify_visualizer/renderers/` island and
  `rendering/image_processor.py` after splitting any mixed tests that still rely on
  them; then restore the two relaxed removal assertions in
  `test_defaults_schema_authority.py`.
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
-> Docs/Index.md + focused/decomposition docs
```

## Durable references

- `Docs/Index.md` — routing map to current owners.
- `Docs/TestSuite.md`
- `Future_Cleanup.md`
- `FWPlan.md`
- `Docs/Settings_Dark_QSS_Retirement.md`
