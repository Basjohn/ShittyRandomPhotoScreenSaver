# Current Plan — Active Work

Last updated: 2026-09-17

The Qt Quick runtime is operator-accepted. This file contains **active work only**; completed cutover work, accepted feature closeouts (Steam Friend Pulse, System Stats, Settings slider crash hardening, Friend Pulse shadow/artwork polish, content-extent resize rollout), Sphere polish, widget resize/Edit lifetime and bucket normalization are intentionally absent — their durable contracts live in the family Reference docs.

---

## Accepted baseline context — CHK26 GOLDEN

Production performance/freshness authority is **CHK26 / repository commit `a0bf70932c`**. CHK23 is the immediately prior GOLDEN rollback/bisect landmark; CHK15 / `0abc479c52` is the older pre-retained-background baseline. The generic headroom campaign is closed and performance work is symptom-driven. CHK27-CHK29 retained useful bounded `--frame-trace` attribution and closed scheduler/Bubble false trails rather than superseding CHK26. Full evidence and rejected methods live in `Docs/Historical_Bugs/R-87_QtQuick_HighRefresh_Freshness_And_Scheduler_Regression.md`.

Bubble remains the strongest protected reaction canary. Any future production change touching its timing/simulation/payload/reactive delivery requires active-music physical acceptance; idle-only evidence is insufficient.

## 1. Documentation / ownership hygiene — perpetual maintenance

- [~] Keep shrinking live docs toward present owners: current contracts/guides/reference for what is true now; `Docs/Historical_Bugs/` for durable regression archaeology; source control for ordinary chronology.
- [~] Keep code comments/docstrings aligned with current ownership and remove phase/cutover breadcrumbs that imply retired migration docs remain authority.
- [~] Keep persisted-input compatibility bridges intact until their support horizon is explicitly declared closed — they are user-data protection, not a cleanup backlog (`Docs/Architecture/Persisted_Input_Compatibility.md`). Delete caller-proven dead residue outright, with its full test cascade in the same commit, never mixed with product behavior changes.

## 2. Runtime/lifetime follow-ups — landed, optional further proof

These are landed optimizations the operator has accepted in normal use; each remains a "do not regress" note plus an optional deeper-proof candidate, not blocking work. Closed incidents live in Historical Bugs (R-82 scaled-prefetch orphaning, R-83 Reddit sub-ms re-arm, R-84 handle slope, R-87 performance/freshness).

- [~] **Scaled speculation execution policy.** Keep R-82 liveness/correctness and the lazy serial below-normal-priority background CPU owner. Do not restore the speculative helper process, generic COMPUTE occupancy or normal-priority competition merely for throughput. Reopen only if mixed-refresh physical evidence improves or stays neutral without freshness/reactivity loss.
- [~] **Gmail/Reddit hidden delegate reduction.** Python retains the larger accepted source buffer while QML materializes only the effective visible count. Do not reintroduce hidden Repeater forests.
- [~] **Media first Play/Pause duplicate — containment.** Keep transport event-driven. The narrow same-burst duplicate guard must not expand into polling or suppress legitimate retry/Next/Previous semantics; prefer removing any reproducible duplicate at its origin.
- [ ] **Quick-native startup/legacy image-boundary audit — optional.** Startup desktop capture is a genuinely GUI-native `QScreen.grabWindow()` source and should not be changed without startup profiling. Separately audit whether the synchronous legacy image publication/failure path can consume detached Quick-native presentation state or be retired. Do not widen this without startup profiling justification.

---

## Standing guardrails

- **Voxel Sphere golden preservation:** current accepted Sphere reactivity/motion/preset behaviour is golden. Keep the mode architecturally isolated; do not retune or promote it into permanent/shared Visualizer owners unless the operator explicitly requests that work.
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
- **System-audio dormancy:** the Core Audio endpoint (`core/media/system_mute.py`) and the mute/system-volume runtime are admitted only behind the mute-button setting, on the UI thread. Do not acquire the endpoint, register callbacks, or run that runtime while the feature is disabled; the End/PgUp/PgDown system-audio keys are gated by that same admission by design.
- **Performance admission:** CHK26 / `a0bf70932c` is the current operator-accepted GOLDEN and the generic headroom campaign is closed. Reopen performance work only for a reproducible symptom, a soak/resource trend, a measurable feature regression, or a newly proven large locally owned hotspot. Preserve logical freshness/reactivity; Bubble is a protected reaction oracle, not an optimization target. See `Docs/Guardrails/Performance_Optimization_Contract.md`.
- **Defaults SSOT:** `core/settings/default_settings.py` is the sole authority;
  `.json`/`.sst` are derived and audit-gated. Never add a second default authority.
- **Settings styling authority (dark.qss retired 2026-09-14):** `themes/dark.qss`
  is physically deleted and the retirement is operator-accepted. Settings/tray
  styling draws structure from narrow permanent renderers and semantic values
  from `SettingsThemeSpec`. Never reintroduce a monolithic Settings QSS file or a
  fallback stylesheet loader, even when the asset is absent.
- **Visualizer preset ownership:** per-mode preset files are user-authored state. Users may add arbitrary counts, delete down to one, and leave sparse authored numbers. Runtime compacts them into slider positions without renaming/deleting files. A shipped preset manifest is packaging/reconciliation metadata, never runtime authority over user-authored presets.
- **Protected behaviour REDs are real signal:** Bubble reaction/replay/viewport, 3D Blockflip pixels, image-prefetch ordering, custom-layout retained-runtime, credential/SST/export privacy and preset transfer must be investigated against current owners/floors before any assertion changes. When current behaviour is operator-confirmed correct, protect it as a floor; never weaken a protected contract to reach green.
- **No fallback architecture:** failures should remain explicit and diagnosable; do
  not solve closeout work by adding silent fallback ownership, timers, or pollers.

## Authority order

```text
exact current source + current reconciled test tree
-> Current_Plan.md (this file: active work + order)
-> Spec.md
-> FWPlan.md (future / non-blocking implementation)
-> Docs/TestSuite.md (test truth)
-> Index.md + focused/decomposition docs
```

## Durable references

- `Index.md` — routing map to current owners.
- `Docs/TestSuite.md`
- `Docs/Architecture/Persisted_Input_Compatibility.md` — compatibility-bridge guard.
- `FWPlan.md` / `Future_Work.md`
- `Docs/Reference/Steam_Friend_Pulse.md`
- `Docs/Reference/System_Stats_Widget.md`
