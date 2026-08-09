# Current Plan

Last updated: 2026-08-09
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
- [x] Preserve three clean source Settings cycles at `logs/evidence_chest/08_08_94798add_main_settings3_custom_spectrum_23_05/`.
- [x] Preserve the strongest combined main-runtime checkpoint at `logs/evidence_chest/08_08_e6f24ca5_main_settings3_perf_23_49/` with parser 1.7 output and manifest.
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
- `main.py` is the sole performance, soak, golden, and evidence-capture authority. Media Center never gets a parallel capture; it receives only bounded shared build/route smoke coverage when packaging parity is relevant.
- Do not add sleeps, nested event pumping, forced garbage collection, working-set trimming, process recycling, timeout extensions, ignored owners, or hidden fallback paths.

# Phase 5 — Active Exit Checklist

## P5.0 Immediate Runtime And Package Validation

Current source still passes repeated Settings recreation, but a freshly built
Media Center runtime was reported to terminate on in-runtime Settings entry.
That proves stale standard-artifact drift was not the complete frozen failure.
Release products intentionally have no default diagnostic evidence; the new
separate diagnostic product now owns frozen-crash attribution.

- [x] Three consecutive live runtime Settings opens/closes queue and admit once, complete both barriers, rebuild once, reveal a fresh frame, continue rendering, and exit cleanly.
- [x] Fix the nonfatal bound-method `_srpss_timer_owner` diagnostic and cover owner/generation propagation.
- [x] Confirm the next live run contains no bound-method ownership exception.
- [ ] Rebuild the standard SCR from current source before rebuilding its installer; the installed and release SCR artifacts both predate the relevant fixes.
- [ ] Validate Settings-from-runtime in the rebuilt standard executable; `--s` alone is not sufficient.
- [ ] Keep Media Center to a minimal shared packaged-route smoke check with no independent capture, baseline, soak, or golden.
- [x] Add an opt-in installable Diagnostic Runtime with a distinct entry point, artifact/installer/AppId, per-user Local AppData logs, bounded rotation, faulthandler output, and Settings/native-window breadcrumbs; leave standard/MC releases diagnostics-off.
- [ ] Build/install the diagnostic product, reproduce in-runtime Settings once, and identify the last completed boundary among request admission, runtime destruction, dialog construction, `showEvent`, native `winId`, acrylic, modal entry, and restart.
- [ ] Make no release UI/lifecycle change until that evidence proves an owner; if the native acrylic boundary is implicated, validate the smallest effect-local correction without weakening the authored Settings shell.
- [ ] After the evidence-led correction, require rebuilt standard and bounded shared MC route smoke to continue rendering; then mark R-59 solved.

## P5.0A Clock Calendar Follow-Up

- [x] Put digital weekday/date and timezone rows on the shared painter-owned text-shadow path; analogue footer rows retain their existing matching painted shadow.
- [x] Include calendar font size in the descriptor-owned CUSTOM resize/font relativity lock.
- [ ] Visually confirm digital/analogue shared/two-line rows with text shadows enabled/disabled and confirm both font controls lock/unlock with CUSTOM mode.

## P5.0B Media Provider Runtime Validation

- [ ] In ordinary `main.py`, validate Spotify Browser against at least Edge or Chrome and record the actual GSMTC source id; confirm the UI description remains honest when the active browser media is not Spotify.
- [ ] Exercise desktop Spotify absent → browser present, browser absent → desktop/MusicBee present, pause, close, and Settings recreation; require one refresh in flight per widget, correct persisted provider, live controls, and no stale-provider callback.
- [ ] Confirm the browser provider never shows or invokes application-volume control and that switching back to a desktop provider restores the preserved volume preference.

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

Current modest-load evidence is positive but not closure: completed transition
windows on the 165 Hz display delivered `110.5–148.7 FPS` and the 60 Hz display
`52.4–59.2 FPS`; Spectrum/Bubble commonly settled around `88–99 FPS`.
Under heavier host pressure, paint fell to `23 FPS`, dtmax reached `232 ms`,
request age `145 ms`, and event-loop lateness `3.07 s`. Paint work was usually
small relative to request age.

- [x] Use ordinary `main.py` as the sole performance/evidence authority; never request or retain a separate Media Center capture.
- [ ] Mark load-change timestamps and assess hostile-pressure and modest-pressure intervals separately.
- [ ] Attribute transition gaps to request age, event-loop lateness, callback/queue wait, source age, and paint cost before changing rendering or visualizer code.
- [ ] Identify the UI-thread work responsible for the remaining request-age/max tails; last-callback labels alone are correlation.
- [x] Add perf-gated delayed-image UI records with reason, display, nested callable, due lateness, runtime-guard cost, actual payload cost, monotonic interval bounds, total age, and stale/error outcome; separately time `QImage→QPixmap` and display setter/transition-start segments.
- [x] Correlate the newest image UI segments with 25/33/50 ms frame gaps: delivery/request age dominates paint, and synchronous `set_processed_image` is the largest measured GUI-owner segment, especially after recreation.
- [x] Add perf-only `set_processed_image` substage timings plus exact retained/old/new texture cache keys and upload/allocation deltas; parser output groups the new records by stage.
- [ ] Use the next main run to distinguish compositor setup, generic pair warm, transition construction/specific warm, controller start, overlay raises, and accounting before changing behaviour.
- [ ] Prove whether the terminally retained texture key equals and cache-hits the next transition's old-image key; the newest run's repeated two steady uploads per display is suspicious but not yet causal proof.
- [ ] Audit simultaneous per-display image decode/prefetch, transition preparation, widget hydration, and diagnostics; desynchronise only independently safe heavy work.
- [ ] Preserve transition names and one terminal GL metric bracket per real transition.
- [ ] Reject repaint retries, transition-derived visualizer clocks, scheduler cadence gates, and speculative shader/visualizer tuning.
- [ ] Re-run the same live transition sequence on a lower-spec machine or constrained host before declaring the high-end-machine result sufficient.

## P5.3 Recreation Ownership And Plateau

- [x] Settings uses primitive generation/manager identity, later-turn admission, duplicate coalescing, and stale-owner rejection.
- [x] CUSTOM/Edit persists and retires its edit session before later-turn full runtime admission; no widget-only fallback is permitted.
- [x] Real destruction tests release display, manager, shell, widget, timer, animation, resource, task, and subscription owners without `gc.collect()`.
- [ ] Run at least five alternating Settings/Edit cycles in normal runtime.
- [ ] Include dual display, one selected display, active transition, pending image work, pending ordinary executor work, playing/paused media, and mode switches.
- [ ] Require exactly one continuation per generation and zero retiring QObjects, Python owners, resources, timers, animations, subscriptions, callbacks, tasks, registrations, pixmaps, textures, PBOs, and tracked GL bytes.
- [ ] Require equivalent settled RSS, private commit, USS, dedicated/shared VRAM, handles, threads, CPU, and GPU to stop rising approximately linearly per cycle.
- [ ] Preserve authoritative-first-frame reveal; no retired, zeroed, or previous-mode frame may satisfy readiness.

## P5.4 Absolute Memory, VRAM, And Cache Efficiency

The current code is a real improvement over the failed resource candidate, but
the newest main run still reached `1070.1 MiB` whole-app RSS, `3123.3 MiB`
private commit, and `623.9 MiB` dedicated VRAM.

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
- [x] Parser 1.8 extends passive image-install output with per-stage duration, cold-compositor identity, exact texture-key reuse, and upload/allocation deltas.
- [x] Keep release artifacts diagnostics-off while providing a separate installable diagnostic runtime with bounded `%LOCALAPPDATA%` rotation and fatal/native-boundary breadcrumbs.
- [ ] Keep all warnings/errors visible in `screensaver.log`; lifecycle timeout is always a failed run.
- [ ] Keep high-volume lifecycle/performance diagnostics passive and bounded.

## P5.6 Verification

- [x] Visualizer/settings-plumbing group: `273 passed` on 2026-08-08.
- [x] Settings/lifecycle/resource/image/parser group: `112 passed` on 2026-08-08.
- [x] Five-mode curated-to-CUSTOM focused regression: `5 passed`.
- [x] Startup identity, fresh-log, RUN lifetime, and CUSTOM telemetry focus: `14 passed`.
- [x] Delayed image UI telemetry, parser, and image/display ownership focus: `76 passed`.
- [x] Production PBO lifecycle 45-cycle harness retains/reuses bounded IDs, trims growth, and reaches strict zero ownership.
- [x] Clock/calendar UI, factory, descriptor, stack predictor, defaults, and manager gate: `293 passed` on 2026-08-09.
- [x] Dynamic onefile/onedir shader-contract validator gate: `16 passed` on 2026-08-09.
- [x] Image-install substage, exact texture-key probe, GL lifecycle, parser 1.8, and image-pipeline gate: `110 passed` on 2026-08-09.
- [ ] Run any new owning-subsystem tests after each further change; do not use a monolithic `pytest -q` process.
- [ ] Classify or repair the existing chunked-suite failure families and the QWidget-without-application native abort tracked in `Future_Cleanup.md`.
- [ ] Re-run the complete suite only through `tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log` when the owning failures are ready for a release gate.

## Phase 5 Exit Gate

- [ ] Bubble and Spectrum are separately approved equal or better than `ff934616`; other supported modes are current-good.
- [ ] Diagnostic attribution identifies and closes the frozen Settings failure; rebuilt standard runtime passes and shared Media Center packaging parity remains a no-capture smoke check only.
- [ ] Five-cycle canonical main recreation matrix passes ownership and plateau checks.
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
- Separate opt-in diagnostic product identity with bounded per-user logs; release builds remain diagnostics-off and performance evidence remains `main.py`-only.
- Registry-owned exact media-provider identities with one background GSMTC session snapshot; unsupported provider ids remain visible and inert.

## Blacklisted

- Persistent shared-analysis or Bubble lanes and the `666624d` ownership model.
- Bubble maximum-two/terminal batching or any source/publication decimation.
- Paint-local Spectrum smoothing, `paintGL()` state mutation, self-requested repaint loops, or a second visualizer clock.
- Retiring every idle texture/PBO and forcing avoidable transition reallocation; retaining historical image sets is also rejected.
- Scheduler/cadence changes used to hide UI-thread pressure.
- Cross-context shared GL stores before Phase 6 ownership design.
- Retry sleeps, nested event pumping, longer teardown timeouts, ignored owners, forced GC, working-set trimming, process recycling, and fake zero accounting.
- Raising cache/resource budgets, retaining reserve frames without byte ownership, or collapsing different DPR/transform outputs.
- Enabling diagnostic families by default in standard/Media Center release artifacts, or treating diagnostic-build timings as production performance evidence.
- Fuzzy/substring media-provider matching, coercing unknown providers to Spotify, serial nested GSMTC fallback queries, or controlling whole-browser volume as though it belonged to one tab.

# Later Phases

- Phase 6: explicit GPU resource store with context/share-group ownership and budgeted eviction.
- Phase 7: immutable latest visualizer render state with generation/activation rejection, only after Phase 5 goldens and lifecycle/resource gates.
- Phase 8: one compositor surface per display (not one global surface), only after Phase 7 proves missed paints never alter logical state and measured A/B evidence justifies the merge.
- Phase 9: local transition completion and deterministic temporary-resource release.
- Phase 10: remove temporary and dead compatibility scaffolding.
- Phase 11: full normal/soak/all-mode/hostile-load/topology validation.
- Phase 12: release preparation.
