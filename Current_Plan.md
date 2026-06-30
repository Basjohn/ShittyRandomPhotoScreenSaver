# Current Plan

Last updated: 2026-06-30

This file tracks active work only. Long-lived architecture truth belongs in `Spec.md`; dated bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails

- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, `Docs/Historical_Bugs.md`, and `Docs/Harness_Index.md`.
- Prune validated work aggressively. This is not a changelog.
- Prefer automation bars over repeated runtime-verification asks.
- Fallbacks must stay loud and routed through the relevant CLI family; a fallback is evidence, not success.
- UI pressure is barred as a perf fix. Do not add repaint/update requeue loops, rescue timers, or broad UI refreshes to chase FPS.
- Before touching shared visualizer/audio/activation/render/transition seams, run the focused visualizer reactivity lock from `Docs/Harness_Index.md`. `Spectrum`, `Sine Waves`, `Bubble`, `Dev Curve`, and `Oscilloscope` currently have accepted runtime behavior and must not be retuned from stale broad-suite failures.

## Active Tasks

### 1. Settings Qt Lifetime Cleanup

- [x] Preserve the latest evidence bundle at `.tmp/perf_settings_evidence_20260630_020535`.
- [x] Root-cause the current settings error shape: `NoWheelSlider` kept a Python weakref to a wrapper whose C++ object could already be deleted, then called `setProperty` / `style()` on it.
- [x] Add a regression bar proving stale `NoWheelSlider` wrappers are not touched and cannot remain the highlighted slider.
- [x] Fix the `NoWheelSlider` last-moved tracker to validate Qt object liveness before touching or storing wrappers.
- [ ] Runtime-check the next `--set` / main log for no `Internal C++ object (NoWheelSlider) already deleted` during settings open/close and slider movement.
- [ ] If another deleted-wrapper family appears, root-cause the owner/lifetime seam instead of catching broad `RuntimeError`.

### 2. Paint-Delivery Performance Recovery

- [x] Preserve latest honest-paint evidence at `.tmp/perf_settings_evidence_20260630_020535`.
- [x] Keep PERF HUD / parser paint-authoritative: `GL PAINT` is the visible cadence signal; `GL RENDER` and `GL ANIM` are supporting diagnostics.
- [x] Classify current evidence without over-closing it: latest logs show healthy `GL RENDER` near target while `GL PAINT` under-delivers, including one near-60 high-refresh window and one Display 1 under-target window.
- [ ] Keep rare `60/40` collapse deferred/watchlist until more post-compositor-rewrite evidence accumulates; do not close it, but do not let it swallow concrete abnormalities.
- [ ] Strengthen the perf parser only where it can prove a wrong behavior: healthy render timer plus poor paint delivery, stable-divisor paint cadence, settings/edit/display lifecycle correlation, and fallback reliance.
- [x] Promote settings UI stalls above 1s to first-class parser anomalies so `--perf` captures settings/build cost instead of burying it in timeline output.
- [ ] Investigate paint-delivery under-target from root seams only: `QOpenGLWidget.update()` consumption, pending-flag lifecycle, compositor/display rebuild boundaries, texture/cache upload timing, settings UI event-loop stalls, and visualizer tick payload.
- [ ] Do not alter visual fidelity, transition identity, first-frame/last-frame behavior, or visualizer reactivity to gain FPS.
- [ ] Run the focused visualizer lock before and after any shared render/tick/transition change.

### 3. Settings UI Cost And Churn

- [ ] Correlate settings open/close with frame-budget spikes, `AnimationManager` windows, visualizer tick spikes, display clear/recreate, and paint under-delivery using `--set`, `--life`, and `--perf`.
- [x] Add settings-hydration cancellation bars so delayed hidden-tab builds cannot run after settings close and bleed UI work into runtime restart.
- [x] Stop building the dev-gated Blob visualizer settings UI when Blob is not available in the mode registry.
- [x] Add granular `--set` / perf timing for Visualizers section build/load steps so future logs identify the expensive mode panel instead of only reporting `lazy_build_subtab_3`.
- [x] Rename WidgetsTab lazy-build perf labels to include the descriptor section id, e.g. `lazy_build_subtab_3:visualizers`.
- [x] Align WidgetsTab tests with current descriptor ownership: visualizer save/load routes through `visualizers`, while dev-gated Blob UI tests opt into the Blob gate deliberately.
- [ ] Audit any settings-time event storms or long-running dialog work that can continue into runtime; fixes must preserve persistence, buckets, scroll position, and lazy-build contracts.
- [ ] Keep WidgetsTab builders/loaders cheap and UI-focused. Backend/cache/auth probes must stay deferred or explicit.
- [ ] If fresh `--set` evidence still shows Visualizers section stalls, use the new per-mode timing to decide whether mode-panel lazy construction is worth the complexity; do not bypass preset persistence, bucket state, or scroll-state contracts.
- [ ] Add or extend a harness only when it can fail on measurable churn, stale background hydration, or deleted-wrapper callbacks.

### 4. Runtime Health Audit Follow-Through

- [ ] Continue executing the project-wide runtime health audit in `audits/ArchitectureAudit/Project_Health_Audit.md`, but keep `Current_Plan.md` limited to active next steps.
- [ ] Keep compositor/transition fallbacks clean: success must name the real shader/deferred path; failure must be loud, not a silent substitute.
- [ ] Keep cache/prescale fallback pressure loud through `--cache`; prefer worker/cache ownership fixes over UI-thread decode, scaling, or synchronous retry paths.
- [ ] Keep context-menu visualizer mode switching watchlisted until one sole-global CUSTOM visualizer case from the other display is runtime-checked.
- [ ] Keep Reddit periodic cadence awaiting compiled-build validation: expect `[CACHE][REDDIT] Periodic refresh fired` for `reddit` around `15min` and `reddit2` around `22.5min`, subject to jitter/cooldown/transition deferral.

## Watchlist

- Rare post-settings/edit performance collapse remains open but deferred: preserve future evidence where Display 0 falls into a suspicious near-60 visible cadence or Display 1 into near-40 under-delivery after settings/edit activity.
- Visualizer CUSTOM geometry route repair is watchlist unless fresh logs show repeated bucket repair, duplicate-owner fallback, requested-monitor fallback, replay-green/runtime-wrong geometry, or settings-return suppression/stranding.
- Non-`Custom` authored stacking is default-on for new users and should be re-audited with `--geo` if authored-layout collision behavior reopens.
- Oscilloscope visual/reactivity is watchlist only; reopen with fresh `--viz` evidence and keep fixes mode-owned unless a shared seam is proven.
- Media metadata preservation during live visualizer preset churn is watchlist; if it reopens, first suspect partial same-track playback snapshots during visualizer-only settings writes.

## Deferred / Not Active

- [ ] Feeds widget family architecture track:
  - [ ] Keep Reddit as its own branded widget and shared runtime owner; do not replace it with Feeds.
  - [ ] Extract reusable list-feed seams from Reddit without changing Reddit UX first.
  - [ ] Design Feeds as an additional widget family with isolated per-spawn source/cache/settings contracts.
  - [ ] Prefer official/feed-native sources and avoid HTML scraping/session automation.
- Dynamic Volume Floor follow-up stays deferred.
- Startup update-policy observability stays deferred behind current runtime-health priorities.
- Secure-desktop long-runtime exit reliability stays deferred.

## Documentation Rule

- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`
- Historical geometry audit: `audits/GeoAudit/Visualizer_Runtime_Shape_Audit.md` when geometry/runtime replay issues reopen
- Runtime health audit: `audits/ArchitectureAudit/Project_Health_Audit.md`
- Bubble preset/runtime audit: `audits/BubbleAudit/Bubble_Preset_Runtime_Audit.md` as historical authored-setting reference
- Bubble historical audit reference: `audits/BubbleAudit/Bubble_End_To_End_Audit.md`
- Oscilloscope visual/reactivity audit: `audits/OscilloscopeAudit/Oscilloscope_End_To_End_Audit.md`

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
No unintegrated user tasks.
----
######
