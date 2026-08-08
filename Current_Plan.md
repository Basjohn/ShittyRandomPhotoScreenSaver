# Current Plan

Last updated: 2026-08-08
Branch: `main`
Active phase: Phase 5 — delivery, visualizer fidelity, recreation, and resource efficiency

This file is the live checklist. Completed analysis and measurements belong in
`Docs/phase_reports/P05_CPU_TASK_REDUCTION.md`; durable failure lessons belong in
`Docs/Historical_Bugs/`.

## Checkpoints And Evidence

- [x] Preserve `ff934616` as the earlier user-approved Bubble/Spectrum behavioural authority.
- [x] Preserve user commit `3b6082dd` as the bounded-resource rollback checkpoint.
- [x] Preserve `94798add` as the queued Settings-admission and shared preset-authority checkpoint.
- [x] Preserve `1621e564` as the bound-callback ownership and five-mode CUSTOM regression checkpoint.
- [x] Preserve `e6f24ca5` as the passive image-delivery attribution, startup identity, and bounded action-telemetry checkpoint.
- [x] Preserve pressure-to-modest live evidence at `logs/evidence_chest/08_08_30fff2c8_mainpy_pressure_to_modest_22_07/`.
- [x] Preserve the original Media Center CUSTOM/Settings report at `logs/evidence_chest/08_08_224a6817_main_mc_custom_settings_22_27/`.
- [x] Preserve three clean source Settings cycles at `logs/evidence_chest/08_08_94798add_main_settings3_custom_spectrum_23_05/`.
- [ ] Promote a later checkpoint over `ff934616` only after separate Bubble and Spectrum visual approval plus the stronger temporal package.

## Non-Negotiable Guardrails

- Keep `versioning.py` user-owned unless a version change is explicitly requested.
- Preserve Bubble's approved authored response, ordinary COMPUTE executor path, and source cadence.
- Spectrum smoothing stays optional, Spectrum-only, and on the existing authoritative UI visualizer tick. No timer, second cadence, paint mutation, self-requested repaint, source decimation, or shared-analysis change.
- Runtime Settings/Edit reconstruction remains full, fail-closed, generation-checked, and gated by destruction plus authoritative-first-frame reveal.
- Never tear down a Qt owner graph from one of its own input/signal/paint/timer/callback frames. Queue primitive intent to a process-owned later GUI turn.
- Strict GL teardown must reach zero textures, PBOs, tracked GL resources, and known GL bytes. Do not weaken accounting to make a gate pass.
- Keep the production CPU-cache cap at 256 MiB until measured hit/fallback evidence justifies a deliberate change.
- UI-thread pressure is the primary performance hazard. Heavy background work for multiple displays must be slightly desynchronised where evidence shows simultaneous churn, without changing visual cadence or correctness.
- Do not add sleeps, nested event pumping, forced garbage collection, working-set trimming, process recycling, timeout extensions, ignored owners, or hidden fallback paths.

# Phase 5 — Active Exit Checklist

## P5.0 Immediate Runtime And Package Validation

- [x] Three consecutive live runtime Settings opens/closes queue and admit once, complete both barriers, rebuild once, reveal a fresh frame, continue rendering, and exit cleanly.
- [x] Fix the nonfatal bound-method `_srpss_timer_owner` diagnostic and cover owner/generation propagation.
- [ ] Confirm the next live run contains no bound-method ownership exception.
- [ ] Validate Settings-from-runtime in the newly built standard executable; `--s` alone is not sufficient.
- [ ] Validate Settings-from-runtime in the newly built Media Center executable.
- [ ] Preserve package logs if either route crashes, rejects admission, duplicates reconstruction, or fails to continue rendering.
- [ ] If both package routes pass, mark R-59 solved and remove the package blocker from this plan.

## P5.1 Visualizer Fidelity And Stronger Goldens

- [x] Keep optional `spectrum_visual_smoothing_enabled` with adjustable `spectrum_visual_smoothing`; default remains the current ideal `0.50`.
- [x] Apply Spectrum smoothing only to presentation bars on the existing authoritative tick, with immediate reset/snap across first frame, generation, pause, disable, teardown, and long UI stalls.
- [x] Record a positive operator verdict under modest system load; current Custom values around `0.50–0.60` are visually useful.
- [x] Resolve curated presets before Settings UI hydration so Move To Custom copies runtime-authoritative state for all five registered modes.
- [x] Cover Spectrum, Oscilloscope, Sine Waves, Bubble, and Spline Curve with stale-backing/conflicting-CUSTOM runtime-shaped regressions.
- [ ] Capture approved numerical source features and playback offsets for Bubble and Spectrum rather than relying only on synthetic inputs.
- [ ] Add installed/live Spectrum source-to-presentation paint receipt with bounded timing distributions.
- [ ] Exercise attack, drop, rapid alternation, stall/reset, playing/paused, Settings recreation, and Bubble → Spectrum → Bubble.
- [ ] Visually validate Sine Waves, Oscilloscope, and Spline Curve against the restored shared source.
- [ ] Complete negative controls for the rejected `666624d` lane model, Bubble terminal batching, and paint-local Spectrum smoothing `ebfec397`.
- [ ] Remove inert persistent-lane scaffolding only after repository-use audit and poison-case preservation.

## P5.2 UI Delivery And Host-Pressure Robustness

Current modest-load evidence is positive but not closure: the 165 Hz display
delivered `139–156 FPS`, the 60 Hz display `58.3–59.6 FPS`, Spectrum/Bubble
settled around `94–98 FPS`, and event-loop p99 was generally about `6–19 ms`.
Under heavier host pressure, paint fell to `23 FPS`, dtmax reached `232 ms`,
request age `145 ms`, and event-loop lateness `3.07 s`. Paint work was usually
small relative to request age.

- [ ] Keep using ordinary `main.py` and `main_mc.py` sessions as performance authority; reserve packaged runs for package-only failures.
- [ ] Mark load-change timestamps and assess hostile-pressure and modest-pressure intervals separately.
- [ ] Attribute transition gaps to request age, event-loop lateness, callback/queue wait, source age, and paint cost before changing rendering or visualizer code.
- [ ] Identify the UI-thread work responsible for the remaining request-age/max tails; last-callback labels alone are correlation.
- [x] Add perf-gated delayed-image UI records with reason, display, nested callable, due lateness, runtime-guard cost, actual payload cost, monotonic interval bounds, total age, and stale/error outcome; separately time `QImage→QPixmap` and display setter/transition-start segments.
- [ ] Use the next marked pressure→modest run to correlate those image UI segments with every 25/33/50 ms frame gap before changing the existing 200 ms display stagger.
- [ ] Audit simultaneous per-display image decode/prefetch, transition preparation, widget hydration, and diagnostics; desynchronise only independently safe heavy work.
- [ ] Preserve transition names and one terminal GL metric bracket per real transition.
- [ ] Reject repaint retries, transition-derived visualizer clocks, scheduler cadence gates, and speculative shader/visualizer tuning.
- [ ] Re-run the same live transition sequence on a lower-spec machine or constrained host before declaring the high-end-machine result sufficient.

## P5.3 Recreation Ownership And Plateau

- [x] Settings uses primitive generation/manager identity, later-turn admission, duplicate coalescing, and stale-owner rejection.
- [x] CUSTOM/Edit persists and retires its edit session before later-turn full runtime admission; no widget-only fallback is permitted.
- [x] Real destruction tests release display, manager, shell, widget, timer, animation, resource, task, and subscription owners without `gc.collect()`.
- [ ] Run at least five alternating Settings/Edit cycles in normal runtime.
- [ ] Repeat the five-cycle matrix in Media Center.
- [ ] Include dual display, one selected display, active transition, pending image work, pending ordinary executor work, playing/paused media, and mode switches.
- [ ] Require exactly one continuation per generation and zero retiring QObjects, Python owners, resources, timers, animations, subscriptions, callbacks, tasks, registrations, pixmaps, textures, PBOs, and tracked GL bytes.
- [ ] Require equivalent settled RSS, private commit, USS, dedicated/shared VRAM, handles, threads, CPU, and GPU to stop rising approximately linearly per cycle.
- [ ] Preserve authoritative-first-frame reveal; no retired, zeroed, or previous-mode frame may satisfy readiness.

## P5.4 Absolute Memory, VRAM, And Cache Efficiency

The current code is a real improvement over the failed resource candidate, but
roughly `1.0–1.2 GiB` RSS and `2.8–3.3 GiB` private commit remain too high.

- [ ] Capture cold, warm, active-transition, steady-image, Settings-gap, post-Settings, and full-teardown snapshots in one live scenario.
- [ ] Reconcile whole/main/child RSS, private commit, USS, worker mappings, thread stacks, Qt/native heaps, driver mappings, and tracked application bytes.
- [ ] Separate one-time high-water retention from live ownership and from true per-recreation growth.
- [ ] Audit exact-transform per-display image duplication without collapsing different DPR or transform outputs.
- [ ] Audit raw/scaled/display co-retention, unused prefetch results, future-byte pressure, and eviction churn using cache hits and actual `worker_fallbacks`.
- [ ] Right-size work only from measured hit/fallback cost; do not raise budgets or create decode storms to lower resident bytes.
- [ ] Audit process-lifetime queues, futures, callback/metric history, logs, handles, and dead Python/Qt graphs.
- [ ] If ownership reaches zero but process memory still rises, open a new evidence-led retention incident before changing cache or teardown policy.

## P5.5 Logging And Evidence Quality

- [x] Parser 1.7 reads canonical rotated sidecars in chronological order and summarizes image UI delay/segment attribution.
- [x] Separate worker requests from actual parent fallback decodes.
- [x] Emit transition-local GL cache/upload/allocation/delete/PBO/direct/slow-upload telemetry and keep strict-zero terminal accounting.
- [x] Preserve raw logs, parser output, source hash, authoritative timestamps, assumptions, and limitations for valuable runs.
- [x] Add one bounded startup record that distinguishes `main.py` from `main_mc.py` without inference from window flags.
- [x] Add bounded Move To Custom action telemetry: mode, source preset index/name, and Custom index without logging the full settings payload.
- [x] Document parser 1.7 rotation/time-range semantics so appended multi-session folders cannot make whole-folder medians look session-specific; a native filter remains optional tooling work.
- [ ] Keep all warnings/errors visible in `screensaver.log`; lifecycle timeout is always a failed run.
- [ ] Keep high-volume lifecycle/performance diagnostics passive and bounded.

## P5.6 Verification

- [x] Visualizer/settings-plumbing group: `273 passed` on 2026-08-08.
- [x] Settings/lifecycle/resource/image/parser group: `112 passed` on 2026-08-08.
- [x] Five-mode curated-to-CUSTOM focused regression: `5 passed`.
- [x] Startup identity, fresh-log, RUN lifetime, and CUSTOM telemetry focus: `14 passed`.
- [x] Delayed image UI telemetry, parser, and image/display ownership focus: `76 passed`.
- [x] Production PBO lifecycle 45-cycle harness retains/reuses bounded IDs, trims growth, and reaches strict zero ownership.
- [ ] Run any new owning-subsystem tests after each further change; do not use a monolithic `pytest -q` process.
- [ ] Classify or repair the existing chunked-suite failure families and the QWidget-without-application native abort tracked in `Future_Cleanup.md`.
- [ ] Re-run the complete suite only through `tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log` when the owning failures are ready for a release gate.

## Phase 5 Exit Gate

- [ ] Bubble and Spectrum are separately approved equal or better than `ff934616`; other supported modes are current-good.
- [ ] Standard and Media Center runtime Settings routes pass in packaged builds.
- [ ] Five-cycle normal and Media Center recreation matrices pass ownership and plateau checks.
- [ ] Host-pressure delivery tails are attributed and acceptable without cadence hacks.
- [ ] Absolute RAM/private-commit/VRAM excess is either reduced to target or fully attributed in a decision record.
- [ ] Cache work has no fallback/decode storm and GL/cache ownership remains bounded.
- [ ] Stronger golden, negative-control, lifecycle, performance, and evidence packages are complete.

# Accepted And Rejected Methods

## Keep Using

- Ordinary general COMPUTE executor semantics with generation/activation rejection.
- One authoritative visualizer tick; optional mode-local presentation filtering inside that tick.
- Runtime-authoritative curated-preset resolution before editor hydration or Custom fork.
- Primitive-only later-turn lifecycle admission with exact pointer-width identity.
- Exact current-texture retention plus at most one size/budget-bounded idle PBO per compositor.
- Worker prescale before parent raw decode and raw-prefetch suppression when no scaled consumer needs it.
- Passive owner/request-age telemetry and timestamp-separated live evidence.
- Slight desynchronisation of independent heavy multi-display background work when measured simultaneous churn exists.

## Blacklisted

- Persistent shared-analysis or Bubble lanes and the `666624d` ownership model.
- Bubble maximum-two/terminal batching or any source/publication decimation.
- Paint-local Spectrum smoothing, `paintGL()` state mutation, self-requested repaint loops, or a second visualizer clock.
- Retiring every idle texture/PBO and forcing avoidable transition reallocation; retaining historical image sets is also rejected.
- Scheduler/cadence changes used to hide UI-thread pressure.
- Cross-context shared GL stores before Phase 6 ownership design.
- Retry sleeps, nested event pumping, longer teardown timeouts, ignored owners, forced GC, working-set trimming, process recycling, and fake zero accounting.
- Raising cache/resource budgets, retaining reserve frames without byte ownership, or collapsing different DPR/transform outputs.

# Later Phases

- Phase 6: explicit GPU resource store with context/share-group ownership and budgeted eviction.
- Phase 7: immutable visualizer render state and presentation decoupling, only after Phase 5 goldens.
- Phase 8: narrow single-surface compositor after resource-store ownership is proven.
- Phase 9: local transition completion and deterministic temporary-resource release.
- Phase 10: remove temporary and dead compatibility scaffolding.
- Phase 11: full normal/soak/all-mode/hostile-load/topology validation.
- Phase 12: release preparation.
