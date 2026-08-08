# Current Plan

Last updated: 2026-08-08

Active unfinished work only. Stable architecture belongs in `Spec.md`; durable rules belong in guardrails; dated failures and detailed evidence belong in `Docs/Historical_Bugs/`; completed narratives leave this file once accepted and archived.

## Recovery And Approval Boundary

```text
branch: main
recovery baseline: 00edb57a3076b845cb8ee4b6cb7f36ea83411f0c
pre-persistent-lane behaviour: 6f188adadabb77b1a9d47a0fe1685c86ad39fb77
failed persistent-lane checkpoint: 666624d421b08f978c5f610571a078570150a1e7
restored executor behaviour: 4bde89e8e39177dc4dd7b5e64b9ac99256ab9486
rejected Spectrum smoothing: ebfec397fb2ae0bbc1f3e95c5298c0e7d6ff1db9
current approved visual behaviour: ff93461685476bd0657aa88312fc2e35e9037880
current lifecycle/cache evidence code state: 3877b2c76791892cd5cb18c43d66a90a29c64d33
current assessed Phase 5 candidate: 3b6082dd (installed recovery checkpoint; final performance gate open)
current uninstalled implementation candidate: afde215d (terminal idempotency, temporal gates, optional Spectrum smoothing)
current audit-doc checkpoint: d7ddb9063ebf9c8a42739e541400a8508b2941bf
latest preserved evidence: logs/evidence_chest/08_08_after_97ff0619_gl_retention_18_59/
latest mutable run: logs/ (2026-08-08 18:59:25 through 19:05:58, code-equivalent pre-commit working tree now captured by 3b6082dd)
owning report: Docs/phase_reports/P05_CPU_TASK_REDUCTION.md
audit roadmap: Docs/audits/SRPSS_Architecture_Recovery_Roadmap/00_INDEX_AND_LIVE_CHECKLIST.md
audit memory plan: Docs/audits/SRPSS_Architecture_Recovery_Roadmap/09_MEMORY_GPU_RESOURCE_AND_CACHE_PLAN.md
audit visualizer contract: Docs/audits/SRPSS_Architecture_Recovery_Roadmap/05_VISUALIZER_FIDELITY_CONTRACT.md
visualizer guardrail: Docs/Guardrails/Visualizer_Presentation.md
R-53 recreation/memory: Docs/Historical_Bugs/R-53_Runtime_Recreation_Ownership_And_Memory.md
R-56 Settings wrapper: Docs/Historical_Bugs/R-56_Settings_Dialog_Deleted_Wrapper_Retouch.md
R-57 scaled prefetch: Docs/Historical_Bugs/R-57_Image_Prefetch_Selected_Index_Order.md
```

`ff934616` is code-equivalent to `4bde89e` and remains the user-approved Bubble/Spectrum behaviour. Later documentation and audit commits do not replace that behavioural authority.

## Status Legend

- `[ ]` not started
- `[-]` active
- `[x]` complete with accepted evidence
- `[!]` failed or blocking
- `[~]` explicitly deferred

## Non-Negotiable Gates

- User-observed visualizer feel outranks task counts, mean timings, paint counts, and green logical tests.
- All supported visualizer modes are protected as a family. Aggregate application or visualizer load is presumed to come from shared/runtime ownership until direct evidence proves a mode-specific owner.
- Bubble is not a default CPU, RAM, VRAM, task-rate, cadence, or fidelity optimization target. Do not change Bubble-specific code unless evidence isolates a Bubble-owned cost and the user explicitly authorizes that scope.
- No shared-source, cadence, scheduler, or cross-mode visualizer optimization begins before the full stronger approved golden package exists. A user-authorized mode-local presentation candidate may proceed only after affected-path temporal hazard lights exist, and it remains unapproved until installed visual review.
- No optimization may lower perceivable fidelity to meet a resource target: no reduced visualizer cadence, source sampling, display resolution, target texture resolution, buffer precision, transition quality, artwork/shadow quality, widget content, animation quality, or first-frame responsiveness.
- No future optimization silently changes cadence, scheduler, source sampling, attack, decay, elasticity, or presentation authority.
- No second visualizer cadence, self-requested Spectrum repaint loop, paint-derived clock, or `paintGL()` mutation authority.
- Heavy non-latency-critical background work that exists per display must use a small deterministic display-local phase offset rather than converging on one deadline. Never delay input, authoritative first frame, visualizer ticks, transition completion, or lifecycle barriers to achieve that staggering.
- Resource containment is not enough by itself. Whole-app warm RSS, private commit, and dedicated VRAM must also be reduced to an evidence-backed reasonable level.
- Settings/Edit destruction remains fail-closed; no timeout extension, ignored owner, retry sleep, nested event pumping, forced garbage collection, working-set trimming, or fake zero count.
- Full runtime teardown may not begin from inside a retiring widget/session owner call stack. Persist and retire the local edit session first; engine-owned recreation admission runs on a later GUI turn.
- Full runtime reinitialization, graph-based CUSTOM placement, graph replay, exact `DisplayManager` identity, generation checks, owner-context GL deletion, and authoritative-first-frame reveal remain mandatory.
- A Python wrapper is not proof of a live Qt object. Validate the underlying C++ object before every post-modal or post-delete touch.
- Multi-index removal from a mutable sequence must use explicitly descending numeric indices or stable-identity partitioning; priority order is not deletion order.
- Do not rename or move existing files.
- Do not regenerate expected outputs merely to make a change pass.

# Phase 5 — CPU, Task, Delivery, Recreation, And Resource Recovery

## Current State

### Visualizer recovery

- [x] Shared audio analysis restored from persistent lane to the approved general COMPUTE executor semantics.
- [x] Bubble simulation restored from persistent lane scheduling to the approved general COMPUTE executor semantics.
- [x] Production visualizer paths no longer register persistent audio-analysis or Bubble compute lanes.
- [x] Operator confirmed Spectrum became significantly better after restoration.
- [x] Operator describes Bubble and Spectrum as well behaving at `ff934616`.
- [x] Spectrum paint-local decay smoothing was attempted, made Spectrum significantly less smooth, and was exactly reverted.
- [x] Latest evidence again shows `lane_registrations=0`; Bubble reached a `1.000` offered/submitted/published ratio with ordinary executor tasks.
- [x] The 18:59 installed run kept Bubble publication at `0.997–1.000`, roughly `1–2 ms` worker cost, and `85.7–89.4` final-segment tick FPS; the operator judged its response good enough to preserve as a stronger-golden candidate.
- [-] The stronger package now has runtime-shaped Bubble discrete-edge and Spectrum presentation traces with known-bad hazard lights. The full installed source/paint-receipt archive and remaining-mode coverage are still incomplete, so `ff934616` remains approval authority.

### Lifecycle and cache evidence

- [x] **Settings recreation:** two consecutive installed Settings cycles completed runtime barrier, dialog barrier, replacement construction, authoritative first frame, and coordinated reveal.
- [x] The former Settings blocker—the idle persistent audio-analysis lane—is confirmed absent from the current production path.
- [!] **CUSTOM/Edit:** the first installed repair failed because exact 64-bit `DisplayManager` identity crossed Qt `Signal(..., int)` and was truncated to a signed 32-bit value. The engine correctly rejected the resulting stale identity, so no recreation began.
- [x] The admission signals now preserve pointer-width identity as a Python object; a mandatory reload-admission failure exits fail-closed and cannot fall back to a widget-only rebuild.
- [x] Runtime generation and exact `DisplayManager` identity travel with the request; stale requests are rejected and duplicate admissions coalesce.
- [x] Production-shaped tests prove two shells and two `CustomLayoutManager` owners release without `gc.collect()`, the barrier reaches zero owners before continuation, the complete two-display graph replays, and exactly one replacement is admitted.
- [x] One installed dual-display Save-and-Continue cycle admitted exactly one full replacement with no stale-identity rejection or widget-only fallback and revealed from the replacement generation's authoritative first frame.
- [x] `WidgetManager` now owns its one-shot compositor-ready signal explicitly; first readiness and terminal cleanup cannot disconnect it twice, the real-signal regression passes, and the latest installed run contains no disconnect warning.
- [x] The 18:59 installed run completed one dual-display CUSTOM Save-and-Continue plus four Settings recreations with no timeout, stale identity, invalid-wrapper, disconnect, exception, or failed first-frame reveal. Every strict GL teardown reached zero texture/PBO bytes.
- [!] This is five recreations but not the required five-cycle alternating Edit/Settings matrix. Whole-app RSS reached `1085.7 MiB`, handles reached `2219`, and several first screen-0 rebuild frames took `609–718 ms`, so plateau and first-frame-tail closure remain open.
- [ ] Run the mandatory five-cycle alternating lifecycle/resource matrix; Edit memory evidence is no longer blocked on a known admission defect.
- [x] Replacement initialization itself still has no demonstrated separate defect; preserve it and validate it rather than redesigning it.

### Absolute resource footprint

The latest active run materially reduced tracked and driver resources and recovered
presentation performance, but remains too heavy for a screensaver:

```text
whole-app resident RAM:   approximately 782–1086 MiB after warm-up
whole-app private commit: approximately 2.74–3.13 GiB after warm-up
whole-app USS:            approximately 650–950 MiB after warm-up
dedicated VRAM:           approximately 555–624 MiB while displays are active
shared GPU memory:        approximately 80–95 MiB
```

- [!] Plateauing near one GiB of physical RAM and over half a GiB of dedicated VRAM is not an acceptable completion state.
- [!] The gap between tracked application-owned bytes and whole-process usage remains too large and must be attributed rather than dismissed as runtime/driver overhead.
- [!] Multi-gigabyte private commit must be decomposed into resident private pages, mapped/reserved regions, child-process commitment, thread stacks, Qt/native allocations, driver mappings, and genuinely retained application state.
- [x] Dedicated VRAM falls to roughly idle-driver levels during full display teardown, proving that deterministic GL deletion is broadly effective even though active steady-state VRAM remains excessive.
- [x] The 2026-08-08 resource detail identified approximately 235.7 MiB of historical transition textures plus approximately 45.7 MiB of upload PBO storage. The failed `849f78e8` candidate retired both historical textures and idle PBOs at terminal presentation.
- [x] The isolated recovery candidate now retains only the exact committed destination texture and at most one idle PBO per compositor under the existing byte cap. Historical textures still delete immediately, growth still trims through the production pool, and strict teardown still returns texture/PBO ownership to zero.
- [x] The duplicate completed-transition cleanup path is now idempotent: an already-cleared compositor state cannot issue a second terminal release/update, and an already-unpinned texture manager cannot reopen/reset the transition bracket. Focused lifecycle/resource tests and the 45-cycle production-PBO harness retain and reuse the exact texture/PBO IDs, trim on larger growth, and reach strict zero ownership.
- [!] The 18:59 installed run predates that correction. Its zero `>20 ms` slow uploads and recovered medians are promising but not causal acceptance; the controlled fixed-workload A/B must prove one terminal record and retained IDs in the installed runtime.
- [x] The same evidence identified approximately 117.6 MiB of raw cache forms alongside display-ready derivatives. Worker prescale is now attempted before parent raw decode, and raw prefetch is skipped when no planned scaled consumer needs it.
- [x] Always-on ThreadManager mutation delivery no longer posts diagnostic/accounting work to the GUI thread. The ordinary general COMPUTE executor and visualizer authored/publication cadence are unchanged.
- [x] The latest installed run confirms real resource reduction against `08_02`: median private commit `3018 -> 2920 MiB`, median dedicated VRAM `623 -> 557 MiB`, maximum dedicated VRAM `777 -> 624 MiB`, and maximum tracked GL `313.1 -> 143.7 MB` (`298.6 -> 137.1 MiB`).
- [!] Those savings and recovered median delivery are not closure: worst transition/event-loop tails, absolute RSS/commit/VRAM, handles, and controlled source identity remain open.

## Required Work Order

1. Capture a controlled warm A/B baseline with fixed displays, source images, cache state, transition sequence, widgets, duration, and low system load. Require exactly one terminal record, retained texture/PBO ID reuse, zero/fewer later slow uploads, no historical accumulation, and CPU/frame/visualizer tails at least equal to `08_02`/Phase 4.
2. Install and review the optional Spectrum smoothing candidate against the same source/preset/display route with smoothing off, default `0.50`, and one stronger setting. Require imperceptible input-to-visible latency, no independent update/paint cadence, and equal-or-better Bubble/Spectrum visual judgement; revert to `3b6082dd` if either mode regresses.
3. Run at least five alternating installed Edit/Settings cycles and require clean ownership, first-frame/mode-switch poison protection, and equivalent-state resource plateau.
4. Complete the remaining stronger temporal package: captured approved source features, installed Spectrum paint receipt, mode-switch/pause/stall scenarios, remaining supported modes, and separate Bubble/Spectrum approval.
5. Use the new main/child commit and USS split to attribute any remaining whole-app RAM/commit gap, then implement only measured reductions that preserve visible output and responsiveness.
6. Run the full lifecycle, memory plateau, image churn, and pressure matrix.
7. Complete delivery-tail, unchanged-media, broader cache-representation, and logging work.
8. Audit current generic scheduler/lane consumers and preserve the recovered blocked-worker poison cases. Repair only a live production consumer; otherwise delete dead lane facades, diagnostics, tests, and scheduler integration after the stronger-golden and repository-use gates.
9. Close Phase 5 only after installed normal and Media Center evidence passes.

# P5.0 — Visualizer Fidelity And Mandatory Goldens

## Accepted baseline

```text
ff93461685476bd0657aa88312fc2e35e9037880
```

No later build replaces it as visualizer golden authority until the user explicitly approves the exact new commit after installed testing.

## Mandatory stronger golden package

The existing Phase 2 JSON replay goldens remain valid logical-equation protection. They are insufficient for scheduling, publication timing, first-visible response, or perceived continuity.

Create one additional versioned golden package from `ff934616` while Bubble and Spectrum are explicitly user-confirmed as correct.

### A. Immutable approval manifest

Record:

- exact commit SHA;
- date and explicit user approval statement;
- Windows version;
- Python and PySide versions;
- GPU and driver;
- display count, resolution, refresh rate, DPR, and selected display route;
- audio capture device and sample configuration;
- normal or Media Center entry point;
- exact Bubble and Spectrum presets/settings;
- bar count, timer target, playing/paused state, and transition state;
- source fixture identifiers and playback offsets.

Do not store copyrighted commercial audio in the repository. Prefer deterministic synthetic PCM plus captured numerical post-capture/source-feature sequences from approved real-song runs.

### B. Exact logical golden

For deterministic fixtures, capture exact or tolerance-bounded:

- raw bars;
- engine-smoothed bars;
- energy and transient bands;
- event edges and consume-once identity;
- Bubble authored inputs and output arrays;
- Spectrum authoritative display bars;
- mode-owned state after each accepted logical frame;
- generation and activation identity.

Continue using the existing replay framework and versioned golden directory. Do not create a competing replay architecture.

### C. Production-executor temporal golden

Run the approved production-style general executor path rather than `ImmediateComputeThreadManager`.

Capture, per sequence or bounded sample window:

- source sequence number and source timestamp;
- capture → submit time;
- worker start/end;
- callback/commit time;
- inter-publication interval;
- source age at visualizer tick;
- source age at Bubble authored step;
- Bubble submit, completion, consumption, and first-visible publication;
- Spectrum authoritative `set_state` publication and paint receipt;
- skipped/rejected/cancelled sequence identity;
- runtime, engine-generation, and activation identity;
- transition and GUI-stall markers.

Use exact ordering/integrity assertions and bounded timing distributions rather than exact wall-clock timestamps.

### D. Installed visual scenario record

Run and record:

- Bubble quiet passage;
- Bubble sustained bass;
- Bubble sharp kick/transient passage;
- Bubble dense/loud passage;
- Spectrum attack, decay, and rapid alternating rise/fall passage;
- Sine, Oscilloscope, and Dev Curve representative passages;
- Bubble → Spectrum → Bubble;
- pause/resume;
- mode transition overlap;
- normal presentation;
- controlled GUI stall;
- Settings recreation;
- Edit Save-and-Continue recreation;
- 60 Hz and available high-refresh display conditions.

Record user acceptance separately for Bubble and Spectrum. Logs may prove timing hazards but cannot overrule the visual verdict.

### E. Negative controls

The stronger suite must detect known rejected behaviour:

- persistent lane scheduling checkpoint `666624d` must differ in the scheduler/ownership temporal layer;
- rejected Spectrum smoothing `ebfec397` must fail the single-cadence/presentation-publication checks;
- Bubble terminal batching/cadence-gate fixtures must fail first-visible discrete-edge checks.

A golden package that also accepts these known-bad shapes is not strong enough.

### F. Mutation policy

- Never auto-regenerate approved visualizer goldens.
- A golden change requires a named candidate commit, reason, before/after evidence, and explicit user approval.
- Preserve old golden versions and their approved commit identities.
- A performance or memory optimization should normally pass unchanged goldens.
- If visual behaviour intentionally changes, capture a new version only after installed approval; never overwrite the previous approved baseline.

## P5.0 tasks

- [x] Reject persistent shared-analysis and Bubble scheduling lanes.
- [x] Restore exact pre-lane production execution behaviour.
- [x] Obtain user approval of restored Bubble and Spectrum behaviour.
- [x] Reject and revert paint-local Spectrum smoothing.
- [x] Create the immutable approval/environment manifest (`tests/goldens/visualizer_temporal/v1/approval_environment_manifest.json`).
- [-] Add deterministic source fixtures and captured approved source-feature sequences. Versioned synthetic Bubble discrete-edge and Spectrum rise/drop/reset fixtures now exist; approved installed numerical source captures remain open.
- [-] Add production-executor temporal replay/capture. Bubble now runs through the real ordinary `ThreadManager` COMPUTE executor; installed Spectrum paint receipt and bounded timing distributions remain open.
- [x] Add affected-path source-to-first-presentation Bubble and Spectrum assertions. Bubble's discrete edge appears exactly once on the first lane-free tick; Spectrum records each authoritative source and presentation publication on the existing tick.
- [-] Add known-bad `666624d`, batching, and `ebfec397` negative controls. Bubble terminal batching is executable and rejected; the Spectrum manifest rejects paint-local mutation/independent updates; the complete `666624d` scheduler/ownership temporal fixture remains open.
- [-] Archive installed visual scenario evidence and separate Bubble/Spectrum approval. Preserve the 18:59 Bubble-positive run against code-equivalent commit `3b6082dd`, but capture deterministic source identity/playback offsets before promoting it to immutable authority.
- [ ] Validate Sine, Oscilloscope, and Dev Curve against the restored shared source.
- [ ] Remove inert visualizer lane scaffolding after golden capture and repository-use audit.

# Active Spectrum Presentation Candidate And Deferred Optimizations

The user explicitly authorized an isolated optional Spectrum presentation candidate after the affected-path temporal hazard lights were added. This candidate is implemented but is **not** the approved visual baseline until installed review names and accepts it:

- setting: `spectrum_visual_smoothing_enabled`, default `true`;
- slider: `spectrum_visual_smoothing`, range `0.00–1.00`, default `0.50`;
- applies to Spectrum presentation bars only on the existing authoritative UI visualizer tick, before the GPU frame push;
- symmetric time-compensated rise/fall interpolation; default time constant `8 ms` (`2–14 ms` over the slider);
- first frame, mode/activation/generation/bar-count/render-style/strength changes, pause/disable, teardown, and GUI stalls of at least `100 ms` snap/reset to source;
- no timer, scheduler, queue, `paintGL()` mutation, self-requested repaint, source decimation, Bubble change, or shared-analysis change.
- frozen Phase 2 replay schema v1 explicitly disables this later presentation candidate and excludes only its two new fields from the v1 preset hash; all 66 approved replay artifacts remain byte-for-byte unchanged, while `visualizer_temporal/v1` owns the candidate trace.

At the default and a 100 Hz tick, a full step reaches about `0.713` on the first tick and `0.918` on the second; the low-frequency delay is about `4 ms`. This is a candidate design target, not proof of imperceptibility. Compare disabled/default/stronger settings installed and let the operator verdict decide.

Resource profiling may compare scenarios across modes, but a difference in whole-process usage does not prove mode-specific ownership. Default to shared audio, render, cache, compositor, process, and lifecycle causes. A mode-specific production change requires direct owner-level evidence and explicit user authorization.

Potentially acceptable later experiments after the current gates:

1. Remove bookkeeping, diagnostics, allocations, or copies while preserving the exact approved executor, authored-step, publication, and paint cadence.
2. Reuse bounded immutable buffers where values, ordering, ownership, and publication remain identical.
3. Coalesce render snapshots only after every logical input and discrete event has already been integrated.
Any Spectrum smoothing candidate must:

- add no timer, scheduler, queue, self-requested paint loop, or paint-derived clock;
- never mutate authoritative bars inside `paintGL()` or a render callback;
- suppress sudden one-tick rises/drops and rapid alternation with no more than one authoritative-tick of additional response and an imperceptible installed latency verdict;
- preserve immediate or near-immediate transient attack unless the installed A/B explicitly approves otherwise;
- preserve source, generation, activation, and first-frame authority;
- reset presentation state at mode/activation/generation/teardown boundaries;
- leave Bubble and shared-source scheduling untouched;
- compare publication and paint cadence against `ff934616`;
- preserve the versioned attack, drop, rapid-alternation, reset/stall, and no-independent-update temporal artifacts before installed review;
- revert immediately if the user reports worse behaviour.

Explicitly rejected unless separately re-proposed after new evidence:

- persistent visualizer compute lanes;
- source decimation;
- Bubble cadence caps or terminal batching;
- paint acknowledgement as producer control;
- simultaneous shared-source and mode-owned scheduler migration;
- “more paints” as a smoothing strategy.

# P5.1 — Delivery Tails

- [-] Correlate owner-labelled transition gaps with event-loop lateness, callback tails, update-request age, and per-display request-to-paint delay.
- [x] Preserve compositor transition names in owner telemetry.
- [-] The 18:59 recovery run nearly restored/exceeded `08_02` median delivery: paint FPS `92.1` versus `96.0`, paint interval p99 `29.9` versus `32.9 ms`, request-age p99 `20.1` versus `20.3 ms`, event-loop lateness p99 `36.4` versus `38.9 ms`, and render dtmax median `66.2` versus `66.5 ms`.
- [!] Worst tails remain open: paint dtmax reached `138.0 ms` on Crumble, render dtmax `129.8 ms`, and event-loop max `1251.3 ms`, versus `96.4`, `127.1`, and `1103.6 ms` in `08_02`.
- [!] Median application CPU was `83.4%` versus `79.3%` in `08_02`, while machine-wide CPU was also higher (`21.6%` versus `14.7%`). The run is strong recovery evidence, not a controlled CPU win.
- [x] Bubble worker cost stayed roughly `1–2 ms`, final-segment publication remained `0.997–1.000`, and Bubble/Spectrum tick medians were `87.5`/`90.6 FPS`. Do not retune Bubble physics, source cadence, or elasticity.
- [x] Parser 1.5 recovers the existing nested task-category counters even when `tm_delivery` follows them on the same line. The comparable high-rate intervals identify approximately `69–70/s` audio analysis plus `92–93/s` Bubble simulation in both runs, so task frequency itself did not newly increase.
- [x] Remove the always-on ThreadManager mutation queue, GUI drain timer, and GUI-published statistics snapshot. Task accounting is now updated atomically at admission/terminal ownership boundaries with no per-completion UI callback.
- [x] Preserve perf-only frame-owner attribution after measuring the exact passive snapshot at approximately `6.5 us/call`, projecting approximately `0.15%` of one core at a 225 Hz dual-display ceiling. Removing that evidence would not explain the observed CPU regression.
- [x] The installed recovery run no longer shows the failed run's generalized delivery collapse; owner gaps normalized to about `18.9/min` versus `29.5/min` in `08_02` and `68.5/min` at 17:07.
- [ ] Attribute remaining cost per event-loop/delivery cycle and worst tails; current last-callback labels are mostly sub-millisecond and are correlation, not sufficient causal attribution.
- [ ] Attribute remaining p99/max transition gaps before changing visualizer cadence or shader behaviour.
- [x] Implement the bounded terminal GL candidate: one exact current-image texture, one size/budget-bounded reusable PBO per compositor, immediate historical-texture deletion, and passive transition-local cache-hit/upload-byte/allocation/delete/PBO/direct/`>20 ms` slow-upload proxy diagnostics.
- [x] Make completed-transition release idempotent. The synchronous outer cleanup re-entry now observes no live compositor transition and performs neither a second release nor redundant `update()`; the texture manager also ignores an empty terminal pair. Focused tests and the 45-cycle harness prove one retained texture, retained-PBO reuse/growth trim, and strict zero teardown.
- [!] Run the fixed low-load installed A/B. The 18:59 binary predates the idempotency fix, so it cannot yet prove one metric bracket, retained texture/PBO IDs, or causal delivery improvement despite zero slow uploads.
- [ ] Reject repaint retries and transition-derived visualizer clocks.

# P5.2 — Latency Truthfulness

- [x] Remove impossible uptime-linear visualizer ERROR values.
- [x] Separate Bubble source, simulation, render-state, and request-to-paint ages.
- [ ] Preserve passive timing telemetry through lane-scaffolding cleanup.
- [ ] Add bounded inter-publication and source-sequence summaries required by the stronger golden package.
- [ ] Do not treat average latency or task throughput as fidelity proof.

# P5.3 — Unchanged Media Work

- [x] The latest run contains no recurring unchanged fixed-card publication signature; the changed-artwork layout refresh remains intentional.
- [ ] Confirm the unchanged no-op in the next installed startup, transition, and long-idle capture.
- [ ] Preserve changed-track responsiveness and transition-time static feedback.
- [ ] Preserve startup artwork generation and reveal ordering.

# P5.4 — Recreation Ownership, Initialization, And Memory Containment

## CUSTOM/Edit result and required implementation

The full runtime reinit and graph placement/replay architecture stay unchanged. Only the admission boundary changes.

### Stage 1 — persist and retire the edit session

- [x] Calculate and save the complete CUSTOM scene.
- [x] Retire every `EditShellWidget` idempotently before display teardown: release pointer grabs, disconnect manager-bound signals, clear resolver/applier closures, remove temporary event filters where required, and clear snapshots/guides.
- [x] Destroy grid overlays and clear temporary shell/state collections.
- [x] Empty `CustomLayoutManager._active_managers` and uninstall the global key filter.
- [x] Neutralize pending restack/menu state and manager-bound deferred state.
- [x] Clear edit-active and reload-pending flags while displays are still valid.
- [x] Return from every manager/action/key-filter save/reset/slot frame before teardown admission.
- [x] Discard a deferred processed image for save/reset/slot actions that will replace the runtime; only cancel may restore it into the unchanged runtime.

### Stage 2 — engine-owned reload admission

- [x] Queue a later-turn callback owned by the process-lifetime engine.
- [x] Carry only immutable primitive intent: request kind, expected runtime generation, and exact pointer-width `DisplayManager` identity; no scene revision is currently required.
- [x] Carry pointer-width identity through Qt as a Python object, not the 32-bit Qt `int` metatype; cover values above `2**32` in both display and manager signal regressions.
- [x] Capture no manager, display, shell, widget, shell state, pixmap, or bound manager method.
- [x] Reject stale generation/manager identity and coalesce duplicate admissions.
- [x] Then execute the same full `engine.stop(exit_app=False, reason="custom_edit")`, fail-closed destruction barrier, complete runtime reconstruction, graph replay, and authoritative-first-frame reveal.
- [x] Keep `CustomLayoutManager` in runtime-root observation; never remove it to make the barrier pass.

## Focused lifecycle tests

- [x] Two-display Save-and-Continue uses the real relay shape and proves teardown begins only on a later GUI turn after the originating save/action frame returns.
- [x] Weakrefs to both managers and every shell clear without `gc.collect()` before the replacement continuation runs.
- [x] Shell retirement clears callbacks/signals idempotently.
- [x] The queued callback closure contains no retiring graph owner.
- [x] Duplicate requests coalesce; stale generation or manager identity is rejected.
- [x] Save/reset/slot discards deferred image; cancel restores it.
- [x] The barrier reaches zero owners before constructing exactly one replacement runtime.
- [x] Saved positions, sizes, screen routes, and graph replay remain correct after reinit.

## Initialization invariants

- retired generation reaches zero before replacement construction;
- `_initialize_display()` fails closed if any destruction barrier remains pending;
- all requested displays are registered before the first staggered show;
- delayed show callbacks are rejected by runtime generation, exact manager, and display membership;
- replacement remains hidden until its own authoritative first frame;
- old callbacks, transitions, visualizer results, cached state, construction, GL initialization, or timer ticks cannot satisfy readiness;
- every supported visualizer uses current engine generation and activation;
- `FadeCoordinator` remains the sole reveal coordinator;
- missing fresh data keeps presentation hidden rather than showing stale state.

## Memory growth result and validation

The 17:07 run completed one full CUSTOM recreation and one Settings recreation.
Both retired-runtime barriers completed (`266 ms` and `282 ms`), CUSTOM admitted
exactly one full reload, and Settings crossed its separate dialog destruction
barrier before one replacement. No exception, deleted-wrapper warning, or signal
disconnect warning occurred.

Comparable idle samples with terminal GL near zero were:

```text
state                     app RSS   private commit   USS     handles   threads
generation 0 pre-Edit      954.9       2822.3       782.6     2116       90
generation 1 post-Edit     934.8       2818.4       753.0     2163       93
generation 2 post-Settings 960.6       2828.8       776.3     2168       90
```

This short run does not show the former approximately 80–90 MiB-per-recreation
memory staircase. Cache occupancy differed between samples, and handles failed to
return to the initial baseline (`+52` by generation 2), so the five-cycle gate
remains open.

- [ ] After R-53 repair, run at least five alternating Edit and Settings cycles in normal and Media Center variants.
- [ ] Include all supported visualizer modes as comparison scenarios, playing/paused, transition-time teardown, pending image work, pending ordinary executor work, dual display, and one selected display.
- [ ] Every retired generation must reach zero QObjects, Python owners, resources, timers, animations, subscriptions, callbacks, tasks, lanes, registrations, pixmaps, textures, PBOs, and tracked GL bytes.
- [ ] Equivalent settled RSS, private commit, dedicated VRAM, handles, threads, CPU, and GPU must stop rising approximately linearly per cycle.
- [ ] If ownership reaches zero but memory still rises, begin a new evidence-led retention investigation. Do not alter cache budgets, trim working sets, recycle processes, or weaken teardown without evidence.

# P5.5 — Absolute Resource Footprint And Cache Representations

## Provisional engineering targets

For the current dual-2560×1440 environment, use the tracked audit gates until evidence justifies a written revision:

```text
whole-app warm RSS: preferred <600 MiB; warning 750 MiB; hard investigation 900 MiB
dedicated VRAM:     preferred <300 MiB; warning 400 MiB; hard investigation 500 MiB
private commit:     no unexplained multi-GiB commitment; every large region has a measured owner/type
```

- [ ] Reach the preferred targets, or produce a decision record that identifies every excess owner, explains why it is necessary, and proposes the next bounded target.
- [ ] Formula-adjust VRAM targets only for measured resolution/DPR/effect requirements; do not use hardware capacity as justification for waste.
- [ ] Treat current active usage above the hard investigation gates as an unresolved optimization defect even when usage is flat.

## Required attribution before optimization

- [ ] Capture cold, post-warm-up, active-transition, steady image, Settings-gap, post-Settings, and full-teardown snapshots under one fixed workload.
- [x] Add low-rate background collection and parser support for main/child RSS, main/child private commit, and main/child USS (private working-set proxy where available), retaining whole-app totals and sample age.
- [x] Record the new main/child RSS/private-commit/USS split in an installed run; the 18:59 capture reports whole-app medians `940.7/2919.9/807.2 MiB` and keeps the image worker near `96–97 MiB` RSS.
- [ ] Continue attribution of virtual/mapped/reserved regions, thread-stack reservation, GDI/USER handles, and driver mappings where commitment remains unexplained.
- [ ] Reconcile process totals against exact CPU cache, QImage/QPixmap/display backing, upload/staging buffers, textures, FBOs, PBOs, visualizer surfaces, transition resources, worker mappings, and passive ResourceManager records.
- [ ] Split one-time warm-up/high-water retention from active live ownership and from true per-cycle growth.
- [ ] Compare supported visualizer scenarios only to distinguish shared from genuinely mode-owned resources. Do not infer a mode-specific cause from whole-process totals.
- [ ] If unexplained process memory remains, inspect Python allocations, Qt/native heaps, driver mappings, thread stacks, worker queues/futures, logging buffers, and deleted-but-pending objects in that order.

## Safe optimization candidates

Only promote a candidate after its owner, bytes, lifetime, and visible role are measured:

- [x] Prefer ImageWorker prescale before exact local raw-decode fallback, avoiding simultaneous parent and worker full-image decode plus unnecessary raw-cache residency when a display-ready derivative is the consumer.
- [x] Skip raw prefetch work when no planned scaled consumer is missing; preserve raw fallback when it remains the only useful result.
- [x] Retaining one bounded idle PBO coincided with removal of the observed slow-upload signature in the 18:59 run: zero `>20 ms` texture uploads versus 15 totalling `411.7 ms` at 17:07, while maximum tracked GL remained `143.7 MB` (`137.1 MiB`). Machine-load/workload confounds prevent a causal claim before the fixed A/B.
- [x] Replace the failed all-idle-resource retirement mechanics with bounded reuse: retain no historical image set, preserve exactly the current presentation texture through stable identity, and retain at most one size-appropriate idle PBO per compositor under the existing cap.
- [x] Correct duplicate terminal release mechanically and prove deterministic retained texture/PBO IDs plus strict-zero teardown.
- [!] Installed benefit is promising but not yet correctly owned: demonstrate one real transition bracket, retained IDs, and delivery/resource equivalence under the controlled A/B.
- [x] Avoid allocating full PBO storage once at creation and immediately reallocating it for the first upload.
- [!] Median delivery and VRAM improved, but whole-app RSS still reached `1085.7 MiB`, private commit `3133.4 MiB`, and worst transition/event-loop tails remain above `08_02`. The candidate cannot pass until all sides improve under the same workload.
- [ ] Deduplicate exact same-size/same-transform per-display image backing without collapsing different DPR or transform outputs.
- [ ] Right-size prefetch and image-cache occupancy by measured hit rate, fallback cost, active-transition reserve, and future-byte pressure; do not create decode storms to save resident bytes.
- [ ] Audit process-lifetime worker mappings, queue buffers, thread-pool/thread-stack reservation, callback history, metrics history, and log retention.
- [ ] Remove dead Python/Qt owner graphs and redundant native surfaces rather than masking them with GC, trimming, or process recycling.
- [ ] Phase 5 may remove duplicate or dead retained resources; a new shared GPU resource-store architecture remains Phase 6 work and must not be smuggled into a small memory patch.

## Fidelity and performance acceptance

Every memory change must prove:

- unchanged approved visualizer goldens and user-observed feel;
- no Bubble-specific production change unless Bubble-owned cost is directly proven and explicitly authorized;
- identical target/display resolution, texture precision, transition output, widget content, artwork, shadows, and first-frame authority;
- no new source decimation, cadence cap, snapshot batching, damping, animation reduction, or hidden-state shortcut;
- no increased cache-miss/decode storm, startup delay, transition p99/max, request-to-paint delay, or Settings/Edit recreation time;
- stable image quality at 100/125/150/200% DPR where applicable;
- lower whole-app RSS/commit/VRAM under the same authored workload, not merely lower tracked counters.

## Broader cache audit

- [ ] Audit raw/scaled/display co-retention, exact-transform duplication, unused prefetch results, and eviction churn after clean lifecycle cycles exist.
- [ ] Keep the current 256 MiB production CPU-cache cap until hit-rate/fallback evidence supports a deliberate revision; do not raise it to hide unexplained memory.
- [ ] Do not add pins, reserve caches, or retained fallback frames without a proven readiness requirement and byte budget.

# P5.6 — Logging Hygiene

- [-] Keep detailed cache records in `screensaver_cache.log`.
- [-] Keep lifecycle ownership detail in `screensaver_lifecycle.log`.
- [x] Parse nested `tm_categories` independently of the trailing `tm_delivery` JSON so owner-rate attribution is not silently emitted as empty dictionaries.
- [ ] Add one authoritative startup record distinguishing `main` and `main_mc`.
- [ ] Add bounded CUSTOM admission diagnostics: request identity, queued turn, persist-complete timestamp, teardown-start timestamp, stale/duplicate rejection, and manager/shell weakref counts.
- [x] Add bounded resource-baseline fields that separate whole/main/child RSS, private commit, and USS, while retaining tracked application bytes, dedicated/shared GPU memory, and sample age.
- [ ] Use an installed capture to verify Windows field semantics and attribute the remaining multi-GiB commitment; do not treat `vms` and private commit as independent additive totals where Windows reports the same counter.
- [ ] Deleted Qt-wrapper touches and worker callback failures must be visible as actionable warnings/errors, not only suppressed DEBUG traces.
- [ ] Keep high-volume diagnostics bounded and passive.
- [ ] All warnings and errors remain visible in `screensaver.log`.
- [ ] A critical lifecycle timeout always marks the run failed.

# Phase 5 Test Isolation

- [x] Focused threading/image/resource, lifecycle/media, visualizer-family, replay-golden, 45-cycle resource, and 50x4K shared-memory gates pass at `849f78e8`.
- [!] A monolithic full-suite `pytest -q` process is not an acceptable gate: while still CPU-active it reached approximately 2.54 GiB working set, 3.28 GiB private memory, and 133 threads without incremental result visibility.
- [x] Run the complete suite only through `tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log`; the 2026-08-08 sweep preserved all four logs and completed chunks 1–3 without timeout, then reproduced the known chunk-4 native `0xC0000409` failure.
- [!] The repository-wide gate is not green: chunks 1–3 retain 10, 7, and 15 unrelated failures, while chunk 4 aborts in `test_base_transition_actual_start_updates_widget_timing`. The retained-GL focused tests and production-path 45-cycle harness pass independently; do not mislabel the full-suite result as acceptance.
- [ ] Classify or repair the existing full-suite failure families and the standalone chunk-4 QWidget-without-application native abort under `Future_Cleanup.md` before treating the chunked suite as a clean release gate.
- [ ] If one chunk still grows excessively, split that chunk by owning subsystem and identify the retained Qt/GL/worker owner before changing tests or production lifetime.

# Recovered Adversarial Lane Findings

The exact findings were recovered from Codex's final recorded statement before that session stalled. They describe races in the rejected persistent-lane/generic-lane architecture; they do not by themselves prove that current approved production execution still contains either race.

- [x] **Finding 1 — stale Bubble step consumes a new kick:** an old Bubble-authored step can remain blocked across a mode/reset/activation boundary, then consume or clear a newly armed kick when the stale step resumes. The stale work may also attempt publication into the new activation unless the execution boundary rejects it.
- [x] **Finding 2 — timed shutdown hides a running lane worker:** a timed shutdown can unregister or stop accounting for a lane while its worker is still executing, allowing lifecycle ownership to report zero too early.
- [!] Current production applicability confidence is **below 90%** until all remaining generic scheduler/lane consumers are audited. Persistent audio-analysis and Bubble lanes are already rejected and absent from the approved runtime.
- [ ] Add the stale-step poison case: block an old Bubble step, cross mode/reset/activation and generation boundaries, arm a new kick, then release the old step. The stale step must not consume, clear, or publish the new event/state.
- [ ] Add the shutdown-accounting poison case: block a lane worker, begin timed shutdown, allow the timeout to expire, and prove the worker/lane remains visible as a lifecycle blocker until actual worker exit.
- [ ] Audit every current production consumer of the generic scheduler/lane API before changing that infrastructure.
- [ ] If a production consumer remains, correct both races at the execution boundary and prove the blocked-worker poison cases before release.
- [ ] If no production consumer remains, preserve the findings and poison cases as negative-control evidence, then delete the dead lane scaffolding only after the P5.0 golden and repository-use gates. Do not repair abandoned infrastructure merely to keep it alive.
- [ ] Once current ownership is verified, archive the exact interleavings, owners, missing tests, chosen repair or deletion, rollback, deterministic result, and installed relevance in a historical incident record.

# Phase 5 Gate

Phase 5 passes only when:

- the stronger user-approved visualizer golden package exists;
- Bubble and Spectrum remain equal or better than `ff934616`, and the other supported modes remain current-good;
- no resource optimization has reduced perceivable fidelity, cadence, resolution, transition quality, widget content, or first-frame responsiveness;
- R-57 passes deterministic and installed prefetch validation;
- R-56 closes without invalid wrapper touches;
- Settings and Edit recreation pass repeatedly;
- CUSTOM teardown begins only after the retiring edit session is explicitly retired and its owner call stacks return;
- no retired generation survives;
- memory, VRAM, handles, threads, and ownership plateau;
- whole-app warm RSS and dedicated VRAM reach the provisional preferred audit targets, or an evidence-backed decision record accounts for every remaining excess and sets an approved bounded target;
- multi-gigabyte private commit is decomposed and no large unexplained commitment remains;
- first-frame poison does not return;
- p99/max delivery is equal or better;
- diagnostics create no meaningful work;
- normal and Media Center variants pass;
- the recovered adversarial findings are covered by poison tests and either fixed for live consumers or preserved before dead lane scaffolding is deleted.

# Later Phases

## Phase 6 — Explicit GPU Resource Store

Metadata-first storage, exact bytes, context/share generation, explicit leases, no GL under registry locks, owner-thread deletion, byte caps, and unleased eviction.

## Phase 7 — Visualizer/Presentation Decoupling

Narrow immutable render state, simulation independent of paint, coalescing only after logical integration, injected GUI-stall tests, and no producer paint waits. Any future presentation smoothing belongs here only after the P5.0 golden gate.

## Phase 8 — Narrow Single-Surface Compositor

One surface per display, immutable scene snapshots, explicit draw order, GUI-local update coalescing, and no simulation/lifecycle ownership.

## Phase 9 — Local Transition Completion

Source/destination/start/duration/easing, local completion after paint, deterministic temporary-resource release, and interruption/resize/Settings/Edit/topology tests.

## Phase 10 — Remove Temporary And Legacy Scaffolding

Remove forwarding, duplicate runtime paths, dead retries/backoff, obsolete metrics, and inert settings after compatibility audit; prove no silent fallback.

## Phase 11 — Full Validation

Normal run, two-hour soak, all-mode review, CPU/disk/GPU/mixed hostile load, Settings/Edit during activity, multi-display/topology, absolute resource targets, memory plateau, and p99/max gates.

## Phase 12 — Release Preparation

Canonical docs match code, benchmark evidence archived, budgets/limitations recorded, rollback commit identified, release candidate tagged, and donor history/evidence preserved.

## Deferred Until Recovery Passes

- new production widget families;
- partial GL reinitialization;
- speculative quality scaling;
- unrelated architectural cleanup;
- donor feature promotion without isolated evidence.

## Plan Hygiene

- Keep only active work and current acceptance boundaries here.
- Move resolved dated narratives to historical records and phase reports.
- Do not claim closure from deterministic tests alone.
- Do not rename this file.
- Do not delete the user task box.

USER TASK BOX. ADD ITEMS BELOW INTO PLANNED STEPS AND EMPTY BOX. NEVER EVER DELETE THIS BOX AS A WHOLE OR THESE INSTRUCTIONS, ONLY PROPERLY ADOPTED IDEAS, YA GOBLIN ASS BITCH.
#######
#######
