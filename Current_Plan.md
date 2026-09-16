# Current Plan — Active Work

Last updated: 2026-09-16

The Qt Quick runtime is operator-accepted. This file contains **active work only**; completed cutover work, Sphere polish,
widget resize/Edit lifetime, bucket normalization and other accepted closeout items are intentionally absent.

---

## Accepted baseline context — CHK26 GOLDEN

Production performance/freshness authority is **CHK26 / repository commit `a0bf70932c`**. CHK23 is the immediately prior GOLDEN rollback/bisect landmark; CHK15 / `0abc479c52` is the older pre-retained-background baseline. The generic headroom campaign is closed and performance work is symptom-driven. CHK27-CHK29 retained useful bounded `--frame-trace` attribution and closed scheduler/Bubble false trails rather than superseding CHK26. Full evidence and rejected methods live in `Docs/Historical_Bugs/R-87_QtQuick_HighRefresh_Freshness_And_Scheduler_Regression.md`.

Bubble remains the strongest protected reaction canary. Any future production change touching its timing/simulation/payload/reactive delivery requires active-music physical acceptance; idle-only evidence is insufficient.

## 0. Documentation consolidation + compatibility debt inventory — active

- [~] Keep shrinking live docs toward present owners: current contracts/guides/reference for what is true now; `Docs/Historical_Bugs/` for durable regression archaeology; source control for ordinary chronology.
- [~] Keep code comments/docstrings aligned with current ownership and remove phase/cutover breadcrumbs that imply retired migration docs remain authority.
- [~] Use **`Future_Cleanup.md` as the single forward cleanup/debt register**, including caller-dead code, deprecated shims and **real persisted-data/schema migration bridges**. Do not delete a real migration seam merely because it is old.
- [ ] After this documentation campaign, execute the migration/cleanup ledger in bounded slices. Establish representative old-profile/import fixtures and explicit support horizons before removing QSettings/Visualizer/SST/layout/theme/cache/credential compatibility.
- [ ] Keep the separate full-suite red/stale-test report as its own pass; feed only classified production/cleanup conclusions back into `Future_Cleanup.md`/`Docs/TestSuite.md`.

## 1. Steam Friend Pulse — public implementation complete, awaiting live/installed acceptance

Current product/architecture contract: `Docs/Reference/Steam_Friend_Pulse.md`. Implementation chronology is not duplicated here.

The public retained Grid/Rows card, privacy/source/cache/runtime ownership, bounded avatar/action routing, optional online count, pinning, shared `content_extent` reflow and Restore Size support are landed. `--devsteam` now owns only unfinished Games You Follow.

- [?] **Dropped-message hotfix installed validation:** run a normal Friend Pulse refresh/lease delivery and confirm no UI-invoker `AttributeError`, roster/state updates continue, and the removed unread-message path produces no source/backoff work.
- [?] **PySide/CUSTOM validation:** run the Friend Pulse runtime/QML plus CUSTOM session/overlay/owner tests. Confirm hover-only pins, removed status circles, offline desaturation/clipping, ALL-CAPS status/game chrome, `X FRIEND(S) ONLINE`, wide-grid expansion beyond the old four/six-column ceilings, and `↶` Restore Size routing with exact X/Y/display preservation. Side-resize Friend Pulse/System Stats before Restore Size and prove the target is canonical authored geometry rather than committed CUSTOM `content_extent`.
- [?] **Real-account eyes-on:** inspect long names/game names, Rich avatar hydration, Strict/Balanced reprojection, private/unavailable/stale wording, manual refresh, chat/profile/Store routing, rounded avatar/tile borders, hover-only multi-pin behavior, finite friend-change glow, wide-grid expansion and online-count summary against real themes.
- [?] **Installed multi-display soak:** two-display/DPI/theme/CUSTOM/stacking use must preserve one shared source owner, no refresh multiplication and clean last-card/family-deactivation retirement.

---

## 2. System Stats — public CPU/Memory/Uptime/Network implementation complete, awaiting installed soak

Current product/architecture contract: `Docs/Reference/System_Stats_Widget.md`. The product source remains isolated from diagnostic `--usage`; the family is visible by default while the member remains disabled, so no sampler exists without an admitted retained-card consumer.

The single shared fixed-delay sampler, CPU/Memory/Uptime/Network metric selection, 10-second minimum/default interval, two-axis `content_extent`, canonical authored geometry, project-owned header glyph and Settings-family retirement hardening are landed. GPU/VRAM remains deliberately rejected rather than a dormant backlog item.

- [?] **Installed/PySide presentation validation:** confirm the `System Stats` pill does not clip, all four metric toggles round-trip, disabled metric reads stay skipped without sampler multiplication, the 1.25 px metric-section outline balances the 5 px accent block, horizontal/vertical side handles reflow cleanly, and Restore Size returns canonical authored geometry when no emergency display fit is required.
- [?] **All-widget load/unload validation:** repeatedly deactivate/reactivate every widget family, including with a coalesced Settings save pending, and confirm no deleted-QObject mutation, rejected UI callback, stale control, or lazy-rebuild/configuration regression.
- [?] **Minimum-interval contention acceptance:** with all four metrics enabled at the 10-second floor, prove no meaningful Visualizer freshness/reactivity or event-loop/presentation-tail regression.
- [?] **Lifetime/multi-display soak:** repeated enable/disable, interval changes, runtime recreation and two-display use must preserve one shared owner, no refresh multiplication and clean final retirement.

---

## 3. Settings slider commit / crash hardening — additional active work

This is additive and must not displace the Friend Pulse/Restore Size acceptance work above. A 2026-09-13
older-checkpoint crash log ends during an extreme Accessibility slider save storm: each slider increment re-saved all four
Accessibility values and published four `settings.changed` events. `SettingsManager.set()` correctly treats every semantic
mutation as a persistence revision, so slider drag batching belongs at the shared UI-control/connection seam, not inside
SettingsManager and not behind a new polling/debounce owner.

- [x] **Diagnosed:** Accessibility slider drag currently calls `_save_settings()` on every `valueChanged`, re-emitting
  `dimming.enabled`, `dimming.opacity`, `pixel_shift.enabled`, and `pixel_shift.rate` for every increment. The supplied
  log terminates mid-storm at 17:51:19. This is strong correlation with the crash but not proof of native crash cause;
  `native_faults.log` contains no captured fault record.
- [x] Add one shared `NoWheelSlider` commit signal: live `valueChanged` remains available for labels/previews, while
  persistence-capable tabs bind save work to the release/commit boundary. Keyboard/programmatic discrete changes remain
  discrete commits; no timer/poller is introduced.
- [x] Migrate immediate-persistence slider paths (Accessibility, Display glow sliders, Sources ratio, Transitions sliders)
  to release-time commit and add focused tests. Accessibility additionally persists only the setting that actually changed,
  reducing the reproduced 46-save/186-event storm to one semantic mutation per committed slider interaction. Preserve
  existing Widgets/Visualizer coalescing authority; audit those slider bindings for redundant callback churn without
  layering a second debounce/persistence owner. Pure source/SSOT contract checks pass 3/3 in the PySide-less environment.
- [?] Installed Settings validation: drag each affected slider aggressively, confirm labels/previews remain live while
  persistence/settings events occur once per drag commit, then repeat the crash reproduction and inspect writer/event logs.

## 4. Friend Pulse directional-shadow audit + dynamic artwork crossfade polish

- [x] **Audit started:** Friend Pulse already gives the BrandedHeader a directional card shadow and text uses the shared
  text-shadow roles. Row/grid tile surfaces, avatar frames, pin/menu controls, separators and the empty-state icon do not
  currently own equivalent directional surface shadows.
- [x] **Shadow prescription:** add, if visual validation agrees, subtle same-direction shadows to row/grid tile surfaces.
  Avatar frames should not use a filled rectangular shadow: shadow the border-ring alpha itself (or an equivalent
  outline-only source) so the empty/transparent interior stays empty, using the existing global card shadow direction/color
  with lower alpha/blur. The empty-state icon may take a very light same-direction shadow. Leave thin separators, pin
  glyphs/buttons and three-dot affordances unshadowed by default; they are too small and become muddy fast. Do not invent a
  Friend Pulse-only direction authority.
- [x] Improve dynamic Media/Steam artwork changes through the shared event-driven `ArtworkFadeImage` SSOT. Keep the current
  readiness-gated two-buffer/no-flash contract and frame-demand ownership; make replacement transitions gentler for every
  existing Media/Achievement/Abandonment artwork consumer without per-widget timers or duplicate transition machinery.
  Shared replacement fade is now 520 ms with `InOutSine`; empty-source fade is 280 ms. The Abandonment-local 340 ms override
  was removed so the shared primitive is authoritative. Pure artwork/slider contract checks pass 9/9 combined.
- [?] Visual validation across Media + Steam artwork surfaces: rapid source churn, missing->ready, ready->missing, same-source
  withdrawal, DPR/theme changes, and no retained second texture after transition idle.

---


## 5. Runtime/lifetime follow-ups

Closed incidents are not active-plan material: scaled-prefetch orphaning is preserved in `Docs/Historical_Bugs/R-82_Scaled_Prefetch_Orphaned_Derivative_Budget.md`, Reddit sub-millisecond recursive re-arm in `Docs/Historical_Bugs/R-83_Reddit_Submillisecond_Cooldown_Recursive_Rearm.md`, and the performance/freshness campaign in R-87 / the accepted baseline context above.

- [?] **R-84 replacement-generation handle baseline:** stable runtime is flat; one bounded 3–5 Settings-replacement churn run still decides whether the first replacement is one-time lazy/native initialization or whether every full replacement retains another persistent handle bundle. Use the existing `--handle-attribution` evidence plane; do not add another broad handle probe or request another discovery soak. Full mechanism/evidence: `Docs/Historical_Bugs/R-84_Usage_PDH_Cardinality_Handle_Slope_Observer_Effect.md`.
- [?] **Normal image-rotation GUI hitch candidate — Windows proof required.** The repaired path publishes detached `PresentationImage` state from the compute task instead of bouncing processed `QImage -> QPixmap -> QImage` on the UI thread. Prove ordinary rotations collapse UI publication cost without changing pixels/DPR/identity, transition source/destination truth, history/accounting, stale-generation rejection or scaled-cache behavior. If a meaningful residual survives while UI publication is cheap, investigate the Qt-native detached buffer/upload boundary rather than retuning the Visualizer.
- [?] **Context Menu invalidation candidate — Windows proof required.** QML notification ownership is split into entries/anchor/visibility so open/hide does not rebuild entry delegates merely because visibility or anchor changed. Repeated open/dismiss must preserve submenu grace, click-outside swallowing, single-owner policy and theme/shadow appearance while removing the old large event-loop tail.
- [~] **Scaled speculation execution policy — installed proof required.** Keep R-82 liveness/correctness and the lazy serial below-normal-priority background CPU owner. Do not restore the speculative helper process, generic COMPUTE occupancy or normal-priority competition merely for throughput. Accept only if mixed-refresh physical evidence improves or remains neutral without freshness/reactivity loss.
- [~] **Gmail/Reddit hidden delegate reduction — installed Qt validation pending.** Python retains the larger accepted source buffer while QML materializes only the effective visible count. Validate instant CUSTOM expansion, Settings SSOT and unchanged source cadence; do not reintroduce hidden Repeater forests.
- [~] **System Stats presentation invalidation — installed validation pending.** Dynamic metric samples use the narrow sample notification rather than broad structural invalidation. The shared 10 s sampler/cadence is unchanged.
- [~] **Media first Play/Pause duplicate — containment under validation.** Keep transport event-driven. The narrow same-burst duplicate guard must not expand into polling or suppress legitimate retry/Next/Previous semantics; prefer removing any reproducible duplicate at its origin.
- [ ] **Quick-native startup/legacy image-boundary audit — gated by normal detached-path proof.** Startup desktop capture is a genuinely GUI-native `QScreen.grabWindow()` source and should not be changed without startup profiling. Separately audit whether the synchronous legacy image publication/failure path can consume detached Quick-native presentation state or be retired. Do not widen this work until normal runtime proof is accepted.

---

## 6. Defaults/test authority follow-ups

The large mutable-default/test-authority audit is closed and its durable rules now live in `Docs/TestSuite.md` and `Docs/Guides/Defaults_Guide.md`. Keep only unresolved cleanup here.

- [?] **Retired transition-worker default:** canonical settings still contain `workers.transition.enabled=True` although the supervised transition worker has no current production consumer. Trace supported persisted-profile/import compatibility; if no supported owner remains, remove the key through canonical schema plus generated-artifact regeneration. Do not preserve dead schema because old tests once referenced it.
- [?] **Achievement cadence authority coverage gap:** Achievement runtime follows the same canonical `widgets.steam.refresh_minutes` authority as Abandonment but lacks the symmetric positive test. Add that authority test when this family is next touched; this is coverage debt, not evidence of a product defect.

---

## 7. Test-report / debris intake

The separate full-suite agent/report owns red/stale-test archaeology. Detailed test policy lives in `Docs/TestSuite.md`; deletion and compatibility timing live in `Future_Cleanup.md`.

- [ ] Classify incoming failures as current RED, environment-blocked, stale/rehome, or caller-proven debris before touching production.
- [ ] Feed only real cleanup/debt conclusions into `Future_Cleanup.md`; do not restore retired owners to make historical tests green.

---

## 8. Content-extent resize rollout — landed architecture, remaining physical validation

Current contract: `Docs/Guides/10_WIDGET_GUIDELINES.md`, `Docs/Contracts.md` and relevant family Reference docs. Whole-card uniform resize remains the default; admitted `content_extent` side reflow is one CUSTOM/session-owned presentation override, never a second settings/normalization owner. Friend Pulse, Reddit/Reddit2, Gmail, System Stats and Media are current consumers.

- [?] **Media installed validation:** repeatedly horizontal/vertical side-resize plus corner/wheel resize with and without external app volume. Confirm Title/Artist remain left-anchored, family logical floors are axis-correct, seek/control/artwork/volume behavior remains coherent, `Allow Landscape Artwork` removes only the square cap, and Restore Size returns canonical authored geometry without disturbing X/Y/display.
- [ ] **Games You Follow** must consume both shared content-extent axes in its first retained implementation; detailed future admission remains in `Docs/Future_Work/Steam_Games_You_Follow.md`.

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
- **Performance admission:** CHK26 / `a0bf70932c` is the current operator-accepted GOLDEN and the generic headroom campaign is closed. Reopen performance work only for a reproducible symptom, a soak/resource trend, a measurable feature regression, or a newly proven large locally owned hotspot. Preserve logical freshness/reactivity; Bubble is a protected reaction oracle, not an optimization target. See `Docs/Guardrails/Performance_Optimization_Contract.md`.
- **Defaults SSOT:** `core/settings/default_settings.py` is the sole authority;
  `.json`/`.sst` are derived and audit-gated. Never add a second default authority.
- **Settings styling authority (dark.qss retired 2026-09-14):** `themes/dark.qss`
  is physically deleted and the retirement is operator-accepted. Settings/tray
  styling draws structure from narrow permanent renderers and semantic values
  from `SettingsThemeSpec`. Never reintroduce a monolithic Settings QSS file or a
  fallback stylesheet loader, even when the asset is absent.
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
- `Docs/Reference/Steam_Friend_Pulse.md`
- `Docs/Reference/System_Stats_Widget.md`
