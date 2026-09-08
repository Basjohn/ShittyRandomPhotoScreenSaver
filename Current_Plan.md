# Current Plan — Active Work

Last updated: 2026-09-08

The Qt Quick migration is **closed** (M0–M3 accepted; see "Closed — do not reopen"
below). Everything here is ordinary post-migration product work. This file owns the
**order of upcoming work and its live status**; durable subsystem detail lives in the
focused docs, test/debris archaeology in `Docs/TestSuite.md` + `Future_Cleanup.md`,
and deferred features in `FWPlan.md`.

Order below is the recommended sequence (small isolated bug → the reactivity
safety net → the big widget-resize feature → the large theming cleanup). Reorder
freely; each item is self-contained unless noted.

---

## 1. Gmail timer lifecycle — Awaiting Logs

Generation propagation and terminal Qt timer destruction are repaired. The real-Qt
reconstruction bar in `tests/test_gmail_runtime.py` verifies one shared owner/timer
for two displays and zero owner/resource records after final retirement over three
generations; the focused lifecycle gate passes 140 tests. Existing explicit lease
retirement already removed the shared-owner registry entry; stopped QTimers retained
their callbacks/resource records, and the family adapter omitted generation identity.

- [ ] Confirm fresh Settings/reconstruction lifecycle logs keep Gmail timer records
  at one while admitted and zero after retirement, with the correct runtime generation.

## 2. Visualizer replay reactivity floor — closed

The 66 cases (plus the historical manifest) run through the current authored tick
and Quick snapshot path. Fixed floors, fixture integrity, presentation independence,
lane/travel contracts and production-seam negative controls pass 78 tests.
[Harness contract](Docs/Future_Work/Visualizer_Replay_Reactivity_Floor.md).

## 3. Ordinary widget resize normalization → one uniform-transform seam

[Docs/Future_Work/Ordinary_Widget_Resize_Normalization.md](Docs/Future_Work/Ordinary_Widget_Resize_Normalization.md).

Move Abandonment/Achievement/Weather off per-value CUSTOM resize payloads onto the
shared `uniformScaleTransform` seam so CUSTOM resize is geometry-only for every
ordinary widget — and make that seam the default path so new widgets are cheap to
add (C4 + new-widget checklist). This is also the prerequisite for the deferred
non-CUSTOM stacker auto-shrink (a widget is only eligible to shrink cleanly once it
scales as one whole card). **C0 harness landed; C1–C3 candidate in the working tree,
not yet accepted/committed.** The maintained [capture/compare harness](Docs/Ordinary_Widget_Resize_Capture.md)
captures 112 states/envelopes and geometry ledgers on real OpenGL. Initial populated
1.0 cards were visually inspected at DPR 1.5 with zero Qt messages. Settled repeated
captures have identical geometry in all 112 cases; all 14 normal cases stay within
2 channel levels of rendering variation. Evidence: `logs/widget_resize_normalization/settled_*`.
Complete the remaining physical/interaction gates before claiming product parity.

- [ ] Finish C1–C3 review: candidate captures have zero Qt messages; Steam's normal
  cases stay within measured rendering variation. Weather long-location normal
  output has a repeatable 4-channel-level difference at identical geometry (baseline
  repeat variation is 2); investigate before closing normal parity. Evidence:
  `uniform_candidate`, `uniform_comparison`, `weather_candidate_repeat` under the
  capture root. Stale replay and two live saves/Cancel pass for all three families;
  non-1.0 acceptance, slots, tooltip/glow and physical topology remain open.

- [ ] **Weather `preferredContentHeight` binding loop:** the physical torture run
  produced repeated QML binding-loop warnings at `WeatherPresentation.qml`'s
  `preferredContentHeight` binding during aggressive CUSTOM resize/reposition and
  multi-display geometry churn. Treat this as a small sizing-correctness/polish bug,
  not performance degradation. Repair it in the same normalization slice by making
  the Weather preferred-height path one-directional: content/scale may determine the
  preferred height, but host/parent geometry must not feed back into the same binding.
  Do not add a timer, poller, debounce, fallback size authority or second geometry
  owner. Regression bar: repeated CUSTOM resize/reposition, cross-display movement and
  runtime recreation must emit zero Weather binding-loop warnings while preserving the
  current Weather visual size, uniform scaling and stacking behaviour.

## 4. dark.qss retirement → ThemeSpec sole authority

[Docs/Settings_Dark_QSS_Retirement.md](Docs/Settings_Dark_QSS_Retirement.md).

Execution authority for migrating the Settings dialog's colour **and** structure out
of `themes/dark.qss` (a competing style authority: ~89 dark-only selectors, ~47
colours) into `SettingsThemeSpec`, so themes fully apply and the file can be deleted
with zero dark-theme regression (byte-identity guarded). Large and independent; do
it after the above. **Not started.**

## Test reconciliation (small, ongoing — owned by `Docs/TestSuite.md` / `Future_Cleanup.md`)

First Edit-entry jump is repaired: quiesce authored placement without resetting
visible geometry. Real started-owner regression and before/after OpenGL captures
confirm the Visualizer stays at `(730,420)` as edit handles appear. Evidence:
`logs/widget_resize_normalization/edit_entry_fixed`. Deferred shrink/stack ordering
is recorded in the resize decomposition: stack first, shrink unresolved collisions,
then re-stack with the reduced footprints.

Concrete open items, do alongside the work above:

- [ ] `tests/test_qtquick_ordinary_widget_host.py::test_host_module_is_presentation_only`
  — allow a legitimate `shiboken6` import (widget-glow work) like `PySide6`.
- [ ] `tests/test_qtquick_ordinary_widget_host.py::test_scene_controller_owns_and_retires_ordinary_widget_host`
  — branch on `window.isSceneGraphInitialized()` for the two-phase deferred-retirement
  offscreen path (already reconciled for the overlay test).
- [ ] Add a narrow regression bar for the `bind_families` recreation ordering fix
  (binding with a retained item reporting a synchronous size must not raise).
- [ ] `tests/test_qtquick_media_presentation.py` — reconcile the Media Volume
  border/volume-colour/artwork presentation contract if that suite owns the seam.
- [ ] Delete the caller-dead `widgets/spotify_visualizer/renderers/` island and
  `rendering/image_processor.py` (both proven no-production-importer) after splitting
  their mixed test files; then restore the two relaxed removal assertions in
  `test_defaults_schema_authority.py`. Tracked in `Future_Cleanup.md`.
- [ ] Broad `pytest tests/` inventory pass to triage remaining widget-glow /
  two-phase-retirement / defaults casualties against current owners.

## Reference (not a task)

- **SST 9/10 settings closeout evidence:**
  [Docs/Future_Work/SST_9of10_Settings.md](Docs/Future_Work/SST_9of10_Settings.md) —
  settings-migration closeout evidence; defaults/plumbing working and protected. The
  derived defaults artifacts (`defaults_snapshot.json` + both `.sst`) are canonical-
  generated and gated: the single `audit_defaults_authority` (run by the Build Foundry
  preflight and `tools/check_defaults_authority.py`) fails on drift; regenerate with
  `python -m core.settings.defaults_snapshot_builder --write-all` or the Build Foundry
  "Regen Defaults" button.

---

## Standing guardrails (constrain all work above)

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
  stacking/adjacency globally (including number-key saved-layout load). Visualizer
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

## Closed — do not reopen without new contradictory evidence

- Qt Quick migration M0–M3: **closed and operator-accepted.** M0 (Visualizer CUSTOM
  geometry + cross-display lifecycle) and M1 (Bubble reference parity) passed focused
  + physical torture runs; see `Docs/Historical_Bugs/Visualizer_Cross_Display_Split_Ownership_2026-09-05.md`.
- M3 frozen-product performance: confirmed good on
  `logs/evidence_chest/QTQUICKlogs2099b25d60MIXEDSOAK.zip`; reopen only for an obvious
  safe optimization with zero fidelity/reactivity/latency risk.
- Widget Glow: physically accepted.
- Sphere: dormant-by-default; current fidelity deferred. `FWPlan.md` owns the future
  status (needs much higher-fidelity rework; keep the 3D architecture unless fully
  superseded — consider voxels). Dormancy has no runtime cost.
- Deterministic GC / Gen2-rescan / usage-sampler owners and the owned-resource
  plateau (2026-09-04 ~7h53m soak) remain closed.
- Defaults authority sanitization: closed and permanently guarded (`audit_defaults_authority`,
  the 30-test `tests/test_defaults_schema_authority.py`, deterministic snapshot/SST).
- Shared widget-theme/style polish, narrow theme fragility and transition experiments
  are Future Work (`FWPlan.md`), not blockers, unless they expose a concrete regression.

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

- `Docs/Index.md` — routing map to all current owners.
- `Docs/Future_Work/Visualizer_Edit_Geometry_And_Sphere_Materials.md`
- `Docs/Historical_Bugs/Visualizer_Cross_Display_Split_Ownership_2026-09-05.md`
- `Docs/TestSuite.md`, `Future_Cleanup.md`, `FWPlan.md`
