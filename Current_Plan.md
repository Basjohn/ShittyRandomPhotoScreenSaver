# Current Plan — Active Work

Last updated: 2026-09-12

Outside of Codex Work Began: `886e6fa419ff130ff2a9aedf5091ae6162d1e958`

The Qt Quick migration is closed and operator-accepted. This file contains **active work only**; completed migration,
Sphere polish, widget resize/Edit lifetime, bucket normalization and other accepted closeout items are intentionally absent.

---

## 0. Quick display sleep/wake topology reconciliation — implemented, automated gate GREEN, pending physical closure

R-79 fixed the Qt topology-authority split exposed by the 2026-09-12 overnight run: screen metric/primary/resume edges now coalesce through the existing bounded reconcile, same-signature resume reapplies authoritative live Quick geometry once, real topology changes keep the existing teardown/rebuild path, and retirement fences/disconnects queued callbacks. No polling or native Windows message path was added.

- [x] Focused Windows/PySide automated gate is GREEN for the R-79-owned topology/window/lifecycle path, including the metric-first -> `ApplicationActive`-second coalescing race, inactive-state no-op, same-signature repair, topology change and retirement fencing. The four observed `test_qtquick_h_cutover.py` / `test_multidisplay_sync.py` failures reproduce without R-79 and remain separate stale-test debt.
- [ ] **Physical closure only, much later:** one installed dual-display off/sleep -> wake acceptance. Close R-79 only when the saver returns with one correct full-screen Quick window per admitted display and no straddled/stale window.

---

## 1. Visualizer long-run presentation-tail investigation — oracle corrected

Execution authority: `Docs/Future_Work/Visualizer_Post_Switch_Performance.md`.

Binding guardrail: `Docs/Guardrails/Performance_Optimization_Contract.md`.

The original hostile-load observation remains real and unresolved: after a long multi-mode run ending in Bubble, logical/source freshness stayed healthy while presentation appeared to degrade, and a saved-layout recreation subjectively appeared to clear it. The automated P4 experiment was built to reproduce that observation, but its first causal verdict is now **invalidated by an oracle bug** rather than accepted as product truth.

- [x] **Invalidate the old `swap_sensitive` / recreation-clears-tail verdict.** `EventLoopStallRecorder` retained 2,048 samples at 50 ms (~102.4 s), while P4 began its "settled" score only 15 s after switching. Each logged p99 therefore still contained switch-period stalls for most of the scored window. In all three C runs, `steady_C_pre` returned to ~4–5 ms p99 before the recreation occurred, so C never proved that recreation caused recovery. Do not use the old A/B/C JSON or rolling p99 classifier output as causal evidence.
- [x] **Repair the oracle, not the product.** Named ABC scored windows now reset the recorder history immediately before their start marker. The recorder keeps its ordinary rolling diagnostic view but also emits independent, non-overlapping `period_*` summaries tagged with the scored-window label. The harness scores only those window-local periods, rejects old rolling-only logs, and measures p99 persistence from consecutive represented report durations instead of repeatedly scoring the same rolling history.
- [x] Preserve the useful stress-sequence facts without overclaiming causality: 25 mode switches (Sphere included) retired render-host implementations cleanly with bounded ownership; presentation/request counts stayed ~1:1; `_InheritedGlState.capture()/restore()` did not become more expensive; `sync_present()` did not produce the 20–50 ms settled stalls; Python thread census did not grow; the aged Bubble-only A-long control stayed clean; aggregate image-cache/native-thread counts do not track the apparent degradation. These results are anti-leak/anti-amplification evidence, not proof that the original long-run problem is solved.
- [x] Keep the Spectrum cold-paused activation fix found during music-off testing: presentation-owned Spectrum idle may reveal while the fresh-source fence remains armed for later reactive authority.
- [ ] **ACTIVE NEXT — one corrected A/B oracle pair.** Use `main_mc.py`, saved layout slot 1, 4 contention workers, `--usage --viz --perf --life`, the same 15 s exclusion and 120 s scored hold; music may remain off. A holds Bubble. B performs `Sphere -> Spectrum -> Oscilloscope -> Sine -> Bubble` x5, then holds Bubble. Do not run C or another 3x matrix unless the corrected window-local B actually shows a persistent post-switch regression.
- [ ] If corrected B is clean, mark the automated 25-switch poison hypothesis **not reproduced for this build/load** and return to reproducing the original long-residency observation with the corrected metric plane. If corrected B still regresses on window-local periods, continue attribution from that trustworthy state and use C only when a concrete suspect/recovery claim requires it.
- [ ] Close this item only when the original user-visible long-run hitch is either reproduced and repaired or honestly rejected for a representative hostile soak. No fix may lower ~90 Hz authored/logical evolution, the 60 Hz presentation target, source freshness, Bubble reaction amplitude/motion/geometry/CUSTOM scaling, or substitute automatic runtime/layout recreation for a real repair.

**Correctness fences are non-negotiable:** GL-state isolation, fresh-source/admission fencing, stale-generation rejection and stale-frame/bleed prevention must remain functionally intact. They may only be altered with equivalent correctness proof; they are never removable performance knobs.

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
