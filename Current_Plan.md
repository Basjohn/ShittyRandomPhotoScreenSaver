# Current Plan — Active Work

Last updated: 2026-09-13

Outside of Codex Work Began: `886e6fa419ff130ff2a9aedf5091ae6162d1e958`

The Qt Quick migration is closed and operator-accepted. This file contains **active work only**; completed migration,
Sphere polish, widget resize/Edit lifetime, bucket normalization and other accepted closeout items are intentionally absent.

---

## 0. Quick display sleep/wake topology reconciliation — implemented, automated gate GREEN, pending physical closure

R-79 fixed the Qt topology-authority split exposed by the 2026-09-12 overnight run: screen metric/primary/resume edges now coalesce through the existing bounded reconcile, same-signature resume reapplies authoritative live Quick geometry once, real topology changes keep the existing teardown/rebuild path, and retirement fences/disconnects queued callbacks. No polling or native Windows message path was added.

- [x] Focused Windows/PySide automated gate is GREEN for the R-79-owned topology/window/lifecycle path, including the metric-first -> `ApplicationActive`-second coalescing race, inactive-state no-op, same-signature repair, topology change and retirement fencing. The four observed `test_qtquick_h_cutover.py` / `test_multidisplay_sync.py` failures reproduce without R-79 and remain separate stale-test debt.
- [x] **Physical closure only, much later:** one installed dual-display off/sleep -> wake acceptance. Close R-79 only when the saver returns with one correct full-screen Quick window per admitted display and no straddled/stale window.

---

## 1. Steam Friend Pulse — implemented behind `--devsteam`, awaiting live/installed acceptance

Execution authority: `Docs/Future_Work/Steam_Friend_Pulse.md`.

The retained implementation is complete through F6. It is a playing-first card with a default dynamically centred
**Avatar Grid** and selectable compact **Activity Rows** view. Both use one stable presentation model and configured
capacity-owned geometry; privacy changes reproject accepted state without creating a second source/model.

- [x] Pin pre-feature HEAD `e0314691` and preserve the maintained Steam request/cache/privacy fixtures.
- [x] Add immutable normalized Friend Pulse source/cache state. Validated Steam IDs may remain in the user's
  account-private cache and owner-only runtime action map; presentation snapshots/QML roles/logs receive no ID or full
  action URL and QML emits only a current row index.
- [x] Add cache-first FriendList + bounded PlayerSummaries preparation through existing Steam locks, request
  coordination, backoff and redaction. The only cadence setting remains canonical `widgets.steam.refresh_minutes`.
- [x] Add one runtime-generation shared source/avatar owner with per-display leases. The dev gate, Steam family
  activation, `widgets.steam.enabled`, member enable and a real presentation consumer all precede work; last release
  stops cadence, clears comparison/avatar state and fences source/avatar completions.
- [x] Add Strict/Balanced/Rich projection, useful changed-first ranking, honest private/connect/empty/stale/failure
  states, per-friend presence/game details, Rich-only visible-row local-avatar hydration, and no Strict identity leak.
- [x] Add retained Quick Grid/Rows presentation, branded/theme roles, finite NEW emphasis, `ordinary_uniform`, global
  CUSTOM/40% floor, ordinary stacking/auto-fit, lazy transactional Settings and generated-default authority.
- [x] Add generation-fenced semantic clicks: friend avatar/NEW marker -> directed Steam chat with public-profile
  fallback; Friend game label and Achievement/Abandonment artwork -> Steam Store. MC/diagnostic tries the Steam client;
  normal screensaver routes HTTPS through the existing secure helper and exits once after accepted handoff.
- [x] Focused source/runtime/privacy/cache/request/Settings/QML/binder/cardinality/normalization tests and real-Quick
  standard/busy/40% captures are GREEN with zero QML warnings.
- [ ] **Awaiting Validation:** use a real connected Steam account to inspect long names/game names, Rich avatar-cache
  hydration, Strict/Balanced reprojection, private/unavailable/stale wording, manual refresh behavior, friend chat/profile
  routing and game Store routing. A NEW marker is a game-change cue, not a sourced Steam message notification.
- [ ] **Awaiting Validation:** installed two-display/DPI/theme/CUSTOM/stacking soak must confirm one shared source owner,
  no refresh multiplication and clean last-card/family-deactivation retirement.
- [ ] Remove `--devsteam` from Friend Pulse only after those live/installed eyes-on and performance cells are green.

---

## 2. System Stats — CPU/RAM implementation complete behind `--devstats`, awaiting soak/ungate

Execution authority: `Docs/Future_Work/System_Stats_Widget.md`.

The dedicated product source and S1-S6 implementation are complete. This does **not** reuse or activate diagnostic
`--usage`: the card samples only whole-system CPU/RAM and remains deactivated plus dev-gated by default.

- [x] Run S0 idle/contention source admission. CPU/RAM measured roughly 0.5–1.5 ms and passed; the persistent Windows
  GPU/VRAM candidate returned `query_error`, took ~363 ms on first setup and was rejected without fallback.
- [x] Add exactly one low-priority sampler owner per runtime generation. Display leases share one immutable snapshot;
  sampling is fixed-delay at 10 s, one-in-flight, generation fenced, and the last lease closes/clears source ownership
  with no surviving recurring work.
- [x] Keep product scope to CPU load plus RAM percentage/used/total. No process/core enumeration, diagnostic collector,
  GPU/VRAM, temperatures, history graphs, per-process data, log parsing or user cadence control entered the product path.
- [x] Add dev-gated/deactivated canonical family/default/descriptor ownership and a lazy transactional Settings page;
  opening Settings imports/starts no sampler. Derived JSON/SST defaults are regenerated and authority checks are GREEN.
- [x] Add the retained two-panel Quick card, fixed metric-capacity geometry, semantic theme roles, `ordinary_uniform`,
  stacking/global-CUSTOM/40% contracts, finite width easing and original packaged monochrome gear + spanner header asset.
- [x] Focused source/runtime/dormancy/multi-display/stale-generation/Settings/QML/binder/build-contract tests and
  real-Quick standard/busy/40% captures are GREEN with zero QML warnings.
- [ ] **Awaiting Validation:** installed 10-second off-vs-on Visualizer contention run must confirm no meaningful
  freshness/reactivity or event-loop/presentation-tail regression.
- [ ] **Awaiting Validation:** repeated enable/disable, runtime recreation and two-display soak must confirm bounded owner,
  task and handle counts plus packaged icon availability.
- [ ] Remove `--devstats` only after those S7 cells are green. A future disk/network metric needs its own S0 admission;
  GPU/VRAM stays rejected unless a truthful low-cost aggregate is independently proven.

---

## 3. `dark.qss` retirement → ThemeSpec sole authority

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

## 4. Test / debris reconciliation

Detailed ownership lives in `Future_Cleanup.md` and `Docs/TestSuite.md`; this active plan carries sequencing only.

- [ ] Run/reconcile the broad `pytest tests/` inventory against current owners. Delete or rehome fossil assertions; do not
  add production defaults/fallbacks or restore retired QWidget/compositor/polling architecture to satisfy them.
  Four currently observed `test_widget_visual_roles.py` reds still assert schema-v1 import, superseded dark-context
  pixels, or construct the current required `WidgetThemeState` without arguments; the new Friend/System semantic-role
  contract passes and production must not regain those retired defaults merely to satisfy the stale assertions.
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
- **Performance admission:** no Visualizer performance investigation is active. Reopen only from a persistent/growing/traceable defect observed in normal use or logs; do not schedule synthetic probe campaigns to search for one. Any admitted optimization must preserve freshness/reactivity and latency-tail quality and prefer fewer/event-owned mechanisms over polling. See `Docs/Guardrails/Performance_Optimization_Contract.md`.
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
