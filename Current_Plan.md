# Current Plan — Active Work

Last updated: 2026-09-12

Outside of Codex Work Began: `886e6fa419ff130ff2a9aedf5091ae6162d1e958`

The Qt Quick migration is closed and operator-accepted. This file contains **active work only**; completed migration,
Sphere polish, widget resize/Edit lifetime, bucket normalization and other accepted closeout items are intentionally absent.

---

## 0. Quick display sleep/wake topology reconciliation — implemented, pending physical closure

Evidence: overnight diagnostic run `2026-09-12 05:43:59` started while Qt exposed one screen and remained healthy through the last logged activity at `09:16:28`; the operator force-closed the still-running process only at `13:47` after waking to a Quick window visually stranded across two displays. Both displays had remained powered off during the unattended period, so the logs do **not** prove that a second display returned earlier. The log stop may represent system suspension or another unlogged interval; do not invent a 09:16 shutdown.

- [x] Remove the topology-authority split where `QuickDisplayWindow` reacted to live `QScreen` geometry/DPI changes locally while `DisplayManager` only reconciled whole topology on `screenAdded`/`screenRemoved`. `DisplayManager` now observes current Qt screen metric edges, primary-screen changes and only the `ApplicationActive` resume edge, all coalesced through the existing 250 ms one-shot reconcile. Resume-revalidation intent is preserved even when a metric/topology edge scheduled that one-shot first. No polling/native Windows message path is added.
- [x] When a resume/application-state edge ends with the exact same screen signature, reapply each live Quick window's already-authoritative bound-screen geometry once and re-anchor retained content instead of forcing a generation rebuild. A real signature change still takes the existing full teardown/rebuild path.
- [x] Disconnect every new Qt topology edge at manager retirement and fence already-queued reconcile callbacks after disconnect.
- [x] Add `tests/test_qtquick_monitor_wake_reconcile.py` plus the `QuickDisplayWindow` contract assertion. Coverage includes metric-first/resume-second coalescing, inactive-state no-op, same-signature geometry repair, primary-screen signature visibility and retirement fencing. The local Linux workspace cannot execute PySide6 tests; syntax/AST validation is green.
- [ ] **Closure gate:** on Windows/PySide, run the focused topology/window/lifecycle suites, then one installed dual-display sleep/off -> wake acceptance. Close R-79 only if the saver returns with one correct full-screen Quick window per admitted display, no straddled/stale window, and logs show either a topology reconcile/rebuild or the bounded same-signature resume geometry revalidation.

---

## 1. Visualizer post-switch presentation-tail / anti-waste follow-up

Execution authority: `Docs/Future_Work/Visualizer_Post_Switch_Performance.md`.

Binding guardrail: `Docs/Guardrails/Performance_Optimization_Contract.md`.

The 2026-09-12 diagnostic run included a heavy external CPU load and the sequence
Sphere -> Spectrum -> Oscilloscope -> Sine -> Bubble. Bubble retained its intended
~90 Hz logical evolution, 1.000 integration ratio and fresh audio-lane publication,
while GUI/presentation late tails grew during the long Bubble residency. Loading a
saved layout rebuilt the Quick display runtime and subjectively cleared the
degradation without changing the active Bubble engine generation/activation. Treat
this as a **presentation/lifetime attribution problem**, not permission to reduce
Visualizer cadence, reactivity, authored geometry or motion. Preserved raw evidence for future agents:
`logs/evidence_chest/logsb11575b976.zip`.

- [x] Execute the decomposition's falsifiable P0-P4 matrix on a live display. **DONE
  2026-09-12 — verdict `swap_sensitive` (3/3 matched valid reps), on MC build
  (`main_mc.py /s`), prepped extreme-vertical CUSTOM Bubble slot 1, 4 contention
  workers.** Nine valid reps (raw JSON + per-rep perf logs in `logs/abc_evidence/`,
  `verdict.json`). Settled-window event-loop p99 (ms), 15 s excluded + 120 s scored:
  A `5.49 / 4.63 / 11.25`; B `64.72 / 32.67 / 27.02`; C_pre `26.34 / 23.20 / 24.95`;
  C_post `4.44 / 5.13 / 4.71`. All three B reps regress vs their paired A on p99
  (≥2 ms & ≥35%, persistent ≥60 s), C_pre reproduces it, and the saved-layout
  recreation clears ≥97% of the introduced tail (C_post at/below the A control).
  Frame-pacer skip did NOT regress (all <1%); freshness/reactivity stayed healthy
  throughout (viz_revision_hz ~90 Hz, viz_age_ms ~20–28 ms, integration ratio
  1.000), so the tail is **not** logical/source starvation. Conclusion: a real,
  reproducible, swap-sensitive **presentation event-loop tail** that a Quick-runtime
  recreation resets — H0 (pure contention) rejected for this build/load. Caveat: the
  event-loop summary cadence is ~15 s (≈8–9 samples/window), so persistence is
  coarse though consistent; the dense freshness plane is unaffected. NEXT: attribute
  H1 (stale render-host ownership) vs H2 (invalidation amplification) via the P1
  telemetry before any perf-code change; do NOT add runtime/layout self-heal. The
  supporting instrumentation, all opt-in (zero Standard/MC overhead): P1 boundary
  render-host telemetry allocates nothing in Standard/MC runtime and is admitted by
  `--viz-switch-telemetry` or `--abc-drive` through the diagnostics resolver
  (`core/diagnostics/experiment_flags.py`, NOT dev_gates). P2 repeated-switch lifecycle
  tests (`tests/test_qtquick_visualizer_mode_retirement.py`, ≥100 switches, inject the
  telemetry directly). P3 permanent-mode real-GL smoke
  (`tools/qtquick_visualizer_switch_smoke.py`, Sphere excluded, `settled_hold`
  separated) **run GREEN on real GL 2026-09-12: 26 completed switches over 5
  cycles, one-active-renderer invariant held every switch, zero release failures,
  shared quad never multiplied, clean same-thread teardown** (also fixed both
  smoke tools' staleness vs the card/shadow + rainbow param migrations; clip-smoke
  suite 44/46, 2 remaining are genuine bubble/oscilloscope pixel-contract asserts).
  P4 deterministic in-app driver
  (`core/performance/visualizer_switch_abc_driver.py`): every condition verifies the
  same saved-layout Bubble/CUSTOM baseline, B/C drive the exact
  Sphere→Spectrum→Oscilloscope→Sine→Bubble ×5 exposure on genuine completion edges,
  C keeps both pre/post recreation windows, and every failure is fail-closed (INVALID +
  non-zero exit). P4 harness (`tools/visualizer_switch_abc_harness.py`:
  `contention`/`score`/`classify`/`auto`) scores named windows with ≥60 s persistence,
  metric-matched C recovery, freshness/reactivity validity, and a 3-matched-valid-rep
  gate. Reproduce with:
  `python tools/visualizer_switch_abc_harness.py auto --condition <A|B|C> --layout-slot 1 --workers 4 --log logs/screensaver_perf.log --rep-out <rep>.json --run-cmd "python main_mc.py /s --usage --viz --perf"`
  then `classify --a A1..A3 --b B1..B3 --c C1..C3`.
- [x] **Attribution H1 vs H2 — DONE 2026-09-12, both REJECTED.** Added opt-in
  presentation-edge counters (`core/diagnostics/visualizer_attribution.py`) + a
  boundary `[PERF] [ABC-ATTR]` snapshot logged by the driver at each scored window
  start/end (H1 ownership+identity from the existing `resource_ownership_snapshot`,
  render-node sync/render/draw, and the separate H2 presentation counts). Ran one
  matched A + one matched B with `--life` (`logs/abc_evidence/{A,B}_attr.perf.log`).
  **H1 rejected:** at the settled B window ownership is identical to the A control —
  `resolved_mode_ids=={bubble}`, bubble `has_resources=False`, one shared quad,
  release failures 0, `release_failure_unresolved=False`; resolve_count 26 with
  releases 25/25/0 exactly track the 25 switches 1:1 with zero leak (Sphere WAS
  exercised — resolve_by_mode sphere:5 — and retired cleanly, closing the P3 gap).
  **H2 rejected:** over the 120 s window A vs B presentation cadence is equivalent
  (pacer opportunities 7194/7193, publications 7189/7187, item present_requests
  7189/7187, window-update fallbacks 0/0, frame swaps 7237/7325, renders 7237/7326,
  draws 7237/7325 — B higher by ~1.2%, not amplified/duplicated). Yet B shows ~7×
  more moderate (25–50 ms) GUI event-loop stalls at the SAME frame/present cadence:
  the tail is a **per-operation cost increase, not a count increase**, and the
  logical tick stays clean (no tick-breakdown spikes, ~90 Hz). C was NOT run — A/B
  leave no H1/H2 ambiguity to resolve. No repair made (neither hypothesis survived).
- [ ] **ACTIVE NEXT (measurement, not repair):** since ownership AND presentation
  cadence are equivalent but individual GUI-thread iterations got costlier in B,
  measure the next suspects before changing anything: (a) the per-draw
  `_InheritedGlState.capture()/restore()` fence (synchronous GL state queries around
  every visualizer draw — same draw count in A/B, so per-draw cost must be timed to
  test whether post-switch driver/GL state makes each capture slower); (b) GC /
  Quick-generation-owned state accumulated across 25 activations (H4) as an alternate
  GUI-thread stall source. Do not lower the 60 Hz presentation target or ~90 Hz
  authored/logical evolution, and never add automatic Quick-runtime/layout recreation
  as a self-heal (the recreation that clears the tail is the experiment's
  intervention, never a shipped mechanism).
- [ ] Measure the per-frame `_InheritedGlState.capture()`/restore fence as a distinct
  CPU/driver owner. It performs synchronous GL state queries around every Visualizer
  draw; change it only if profiling proves material cost and state-isolation coverage
  proves widgets/transitions/permanent Visualizer modes remain uncontaminated.
- [ ] Close the item only after a representative mode-switch/recreation soak shows a
  bounded resolved-renderer/resource plateau and stable event-loop/pacer tails with
  no loss of Bubble temporal fidelity, source freshness, reaction amplitude or
  CUSTOM scaling behaviour.

---

## 2. Steam Friend Pulse — definite queued widget

Execution authority: `Docs/Future_Work/Steam_Friend_Pulse.md`.

Friend Pulse is queued immediately after the performance investigation. Do **not** port the old painter/mock card.
Build the useful activity-first retained Quick card described by the decomposition: currently-playing friends plus a
bounded useful subset/change emphasis, honest private/stale/unavailable states, and the existing Steam family Privacy
Mode (`Strict` / `Balanced` / `Rich`) becoming real presentation policy.

- [ ] Pin the pre-feature GODZIP/HEAD and current Steam request/cache/privacy fixtures before substantive code changes.
- [ ] Reconfirm friend-list + player-summary fixture contracts, then define immutable accepted Friend Pulse state with
  raw Steam IDs excluded from logs/presentation.
- [ ] Implement cache-first bounded source preparation through the existing Steam locks/request/backoff policy; do not
  create a parallel Steam provider or a card-local refresh interval.
- [ ] Make dormancy explicit: Steam family activation + `widgets.steam.enabled` + `widgets.friend_pulse.enabled`
  (plus the temporary dev/member gate) are all required before Friend Pulse may own source/runtime work. Disabled or
  deactivated state performs no friend refresh, avatar work or latent worker cadence.
- [ ] Reuse retained ordinary-card normalization: `ordinary_uniform`, shared global-CUSTOM/40% resize floor, shared
  non-CUSTOM stacking/auto-fit, stable configured-capacity height, Widget Theme/Style Overrides, branded-header
  vocabulary and finite presentation-only animation. No family-specific geometry or theme architecture.
- [ ] Hydrate avatars only after visible-row ranking and only for Rich privacy mode; multiple displays must not multiply
  Steam source refresh traffic.
- [ ] Prove unchanged accepted snapshots do not rebuild rows/layout/assets; retirement fences stale completion and
  releases Friend Pulse-owned runtime/assets without disturbing legitimate shared Steam consumers.
- [ ] Ungate only after source/privacy/dormancy/normalization/performance and eyes-on readability gates are green.

---

## 3. System Stats — conditional queued widget

Execution authority: `Docs/Future_Work/System_Stats_Widget.md`.

The old blanket rejection is lifted, but this is **not** permission to make diagnostic `--usage` telemetry permanent.
The preserved run proves the existing diagnostic sampler is too broad for a live card: light collections were ~24.5 ms
median / ~33.9 ms p95 and heavy samples ~67 ms median / ~107 ms p95, with one contention outlier above one second.
System Stats therefore gets a separate lightweight product sampler or remains shelved.

- [ ] Begin with the decomposition's S0 probe only: whole-system CPU + RAM and a persistent adapter-aggregate GPU/VRAM
  candidate. Measure p50/p95/max and GIL/Visualizer logical-tail impact under idle and deliberate CPU contention before UI.
- [ ] If admitted, use exactly one process/runtime-generation shared sampler owner with narrow retained-card leases.
  Multiple displays consume one accepted snapshot; the last lease stops cadence and closes GPU counter/query ownership.
  Family deactivation or ordinary widget disable leaves **zero recurring sampler work**.
- [ ] Use event-owned activation/retirement and one bounded low-priority shared sampler only while a real card lease exists.
  Usage rates inherently require observations over time, so begin at a fixed **10 s** product cadence; consider **5 s** only
  if eyes-on validation proves 10 s meaningfully too stale and A/B contention evidence remains clean. One sample may be in
  flight; missed cadence edges skip instead of queue. No UI-thread system queries, QML/private polling timer, or sampler
  surviving the last lease.
- [ ] Keep first product scope intentionally small: CPU, RAM, and only reliable system-wide GPU/VRAM. No USS/private
  memory, process-tree/thread/handle/IO diagnostics, temperatures, per-process tables, log parsing or Task-Manager clone.
- [ ] Add canonical `system_stats` family/default/Settings ownership only after the sampling gate passes. Keep the new
  family internally plugin-shaped and dev-gated/deactivated by default through acceptance; Settings stays lazy/
  transactional with current closed + one-open bucket semantics, no shadow defaults or diagnostic knobs.
- [ ] Reuse ordinary retained-card normalization/theme/glow/stacking/CUSTOM contracts. Configured metric capacity, not
  momentary availability, owns preferred geometry so samples cannot churn layout. Reuse a canonical themed tools/settings
  glyph if one genuinely fits; otherwise add a small original project-owned monochrome **gear + spanner** header asset through
  the normal resource/build path rather than adding a web/icon-font dependency or a family-local icon loader.
- [ ] Close only after off-vs-on contention comparison shows no meaningful loss of Visualizer freshness/reactivity or new
  presentation-tail pathology, and activation/disable/recreation/multi-display soak proves bounded owner counts.

---

## 4. `dark.qss` retirement → ThemeSpec sole authority

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

## 5. Test / debris reconciliation

Detailed ownership lives in `Future_Cleanup.md` and `Docs/TestSuite.md`; this active plan carries sequencing only.

- [ ] Run/reconcile the broad `pytest tests/` inventory against current owners. Delete or rehome fossil assertions; do not
  add production defaults/fallbacks or restore retired QWidget/compositor/polling architecture to satisfy them.
- [ ] Retire the temporary Visualizer `enabled_modes` compatibility migration only after automated persisted-profile/import
  coverage proves supported profiles no longer rely on it. Current runtime/default/UI state remains the canonical
  `widgets.spotify_visualizer.mode_activation` boolean map.
- [ ] Complete caller-proven READY deletion rows in `Future_Cleanup.md` only after their exact caller/test prerequisites are
  satisfied; dormant compatibility-horizon rows remain dormant.

---

## Standing guardrails

- **Voxel Sphere golden preservation:** current accepted Sphere reactivity/motion/preset behaviour is golden. Keep the mode architecturally isolated; do not retune or migrate it into permanent/shared Visualizer owners unless the operator explicitly requests that work.
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
- `Docs/Future_Work/Steam_Friend_Pulse.md`
- `Docs/Future_Work/System_Stats_Widget.md`
- `Docs/Future_Work/Settings_Dark_QSS_Retirement.md`
