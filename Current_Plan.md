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
current audit-doc checkpoint: d7ddb9063ebf9c8a42739e541400a8508b2941bf
latest evidence: logs/evidence_chest/08_02_3877b2c7_20_27/
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
- No visualizer optimization begins before the stronger approved goldens exist.
- No optimization may lower perceivable fidelity to meet a resource target: no reduced visualizer cadence, source sampling, display resolution, target texture resolution, buffer precision, transition quality, artwork/shadow quality, widget content, animation quality, or first-frame responsiveness.
- No future optimization silently changes cadence, scheduler, source sampling, attack, decay, elasticity, or presentation authority.
- No second visualizer cadence, self-requested Spectrum repaint loop, paint-derived clock, or `paintGL()` mutation authority.
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
- [!] Stronger goldens are still missing. Accepted behaviour exists, but automated temporal hazard lights remain incomplete.

### Lifecycle and cache evidence

- [x] **Settings recreation:** two consecutive installed Settings cycles completed runtime barrier, dialog barrier, replacement construction, authoritative first frame, and coordinated reveal.
- [x] The former Settings blocker—the idle persistent audio-analysis lane—is confirmed absent from the current production path.
- [!] **R-56:** pre-exec destruction observation and Shiboken-valid cleanup now pass production-shaped tests; one installed Settings cycle must confirm no deleted-wrapper trace.
- [!] **CUSTOM/Edit:** the synchronous re-entry defect is repaired mechanically. Save/reset/slot commits retire Edit-session state, return through the manager-owned frame, and queue one immutable engine-owned reload intent for a later GUI turn.
- [x] Runtime generation and exact `DisplayManager` identity travel with the request; stale requests are rejected and duplicate admissions coalesce.
- [x] Production-shaped tests prove two shells and two `CustomLayoutManager` owners release without `gc.collect()`, the barrier reaches zero owners before continuation, the complete two-display graph replays, and exactly one replacement is admitted.
- [ ] One installed dual-display Save-and-Continue cycle must still prove the former eight-second barrier timeout is absent and the replacement reveals from its own authoritative first frame.
- [x] **Settings memory growth:** the former linear per-cycle staircase did not reproduce across two Settings replacements.
- [!] One-time post-first-recreation process uplift remains unexplained; confidence in allocator/cache/driver/retained-owner cause is below 90%.
- [ ] Edit memory/plateau evidence remains blocked on installed validation of the repaired CUSTOM path, not on a known mechanical admission defect.
- [!] **R-57:** stable-identity selection/removal and boundary regressions now pass mechanically; installed transition/image rotation remains required.
- [x] Replacement initialization itself still has no demonstrated separate defect; preserve it and validate it rather than redesigning it.

### Absolute resource footprint

The latest active run was contained but still far too heavy for a screensaver:

```text
whole-app resident RAM:   approximately 847–1074 MiB
whole-app private commit: approximately 2.86–3.17 GiB
dedicated VRAM:           approximately 554–777 MiB
shared GPU memory:        approximately 84–121 MiB
```

- [!] Plateauing near one GiB of physical RAM and over half a GiB of dedicated VRAM is not an acceptable completion state.
- [!] The gap between tracked application-owned bytes and whole-process usage remains too large and must be attributed rather than dismissed as runtime/driver overhead.
- [!] Multi-gigabyte private commit must be decomposed into resident private pages, mapped/reserved regions, child-process commitment, thread stacks, Qt/native allocations, driver mappings, and genuinely retained application state.
- [x] Dedicated VRAM falls to roughly idle-driver levels during full display teardown, proving that deterministic GL deletion is broadly effective even though active steady-state VRAM remains excessive.

## Required Work Order

1. Freeze `ff934616` as the user-approved visualizer behavioural baseline.
2. Record the immutable approval/environment manifest before production code changes; full temporal goldens remain mandatory before visualizer optimization or lane-scaffolding deletion.
3. Repair R-57 with its exact missing preferred-index regression fixture.
4. Repair R-56 without weakening `WA_DeleteOnClose`, dialog destruction observation, or fail-closed replacement admission.
5. Repair R-53 CUSTOM/Edit persistence-to-recreation admission and deterministic shell callback retirement.
6. Run focused tests for R-57, R-56, and the two-display CUSTOM weakref/barrier path.
7. Run one installed Settings cycle and one dual-display Edit Save-and-Continue cycle.
8. Capture a controlled warm resource baseline with fixed displays, source images, cache state, transitions, widgets, duration, and supported visualizer scenarios.
9. Attribute the whole-app RAM/commit/VRAM gap by owner and representation, then implement only measured reductions that preserve visible output and responsiveness.
10. Run the full alternating Settings/Edit lifecycle, memory plateau, image churn, and pressure matrix.
11. Audit current generic scheduler/lane consumers and preserve the recovered blocked-worker poison cases. Repair only a live production consumer; otherwise delete dead lane facades, diagnostics, tests, and scheduler integration after the stronger-golden and repository-use gates.
12. Complete delivery-tail, unchanged-media, broader cache-representation, and logging work.
13. Close Phase 5 only after installed normal and Media Center evidence passes.

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
- [ ] Add deterministic source fixtures and captured approved source-feature sequences.
- [ ] Add production-executor temporal replay/capture.
- [ ] Add source-to-first-visible Bubble and Spectrum assertions.
- [ ] Add known-bad `666624d`, batching, and `ebfec397` negative controls.
- [ ] Archive installed visual scenario evidence and separate Bubble/Spectrum approval.
- [ ] Validate Sine, Oscilloscope, and Dev Curve against the restored shared source.
- [ ] Remove inert visualizer lane scaffolding after golden capture and repository-use audit.

# Deferred Visualizer Optimizations

These are not current-priority work. None may begin until all P5.0 stronger-golden tasks are complete and the user explicitly authorizes the individual experiment.

Resource profiling may compare scenarios across modes, but a difference in whole-process usage does not prove mode-specific ownership. Default to shared audio, render, cache, compositor, process, and lifecycle causes. A mode-specific production change requires direct owner-level evidence and explicit user authorization.

Potentially acceptable later experiments:

1. Remove bookkeeping, diagnostics, allocations, or copies while preserving the exact approved executor, authored-step, publication, and paint cadence.
2. Reuse bounded immutable buffers where values, ordering, ownership, and publication remain identical.
3. Coalesce render snapshots only after every logical input and discrete event has already been integrated.
4. Explore Spectrum smoothing only as an isolated presentation experiment on the existing authoritative visualizer tick.

Any future Spectrum smoothing must:

- add no timer, scheduler, queue, self-requested paint loop, or paint-derived clock;
- never mutate authoritative bars inside `paintGL()` or a render callback;
- preserve immediate attack unless explicitly approved otherwise;
- preserve source, generation, activation, and first-frame authority;
- reset presentation state at mode/activation/generation/teardown boundaries;
- leave Bubble and shared-source scheduling untouched;
- compare publication and paint cadence against `ff934616`;
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
- [ ] Attribute remaining p99/max transition gaps before changing visualizer cadence or shader behaviour.
- [ ] Reject repaint retries and transition-derived visualizer clocks.

# P5.2 — Latency Truthfulness

- [x] Remove impossible uptime-linear visualizer ERROR values.
- [x] Separate Bubble source, simulation, render-state, and request-to-paint ages.
- [ ] Preserve passive timing telemetry through lane-scaffolding cleanup.
- [ ] Add bounded inter-publication and source-sequence summaries required by the stronger golden package.
- [ ] Do not treat average latency or task throughput as fidelity proof.

# P5.3 — Unchanged Media Work

- [-] Prove unchanged polls perform no metadata publication, structural layout mutation, artwork work, or repaint.
- [ ] Preserve changed-track responsiveness and transition-time static feedback.
- [ ] Preserve startup artwork generation and reveal ordering.

# P5.4 — Recreation Ownership, Initialization, And Memory Containment

## Settings result and R-56

- [x] Two installed Settings cycles prove runtime destruction completes before dialog construction and dialog destruction completes before replacement construction.
- [x] The production visualizer lane blocker is absent.
- [x] Both replacements used current-generation authoritative first frames and coordinated reveal.
- [x] Move dialog destruction observation before `dialog.exec()` can trigger `WA_DeleteOnClose`.
- [x] Replace `isinstance(dialog, QObject)` liveness assumptions with actual Shiboken validity checks.
- [x] Do not call `findChildren`, `close`, or `deleteLater` on an invalid wrapper.
- [x] Add production-shaped real-signal tests that fail on deleted-wrapper warnings/traces, prove weakref release without `gc.collect()`, and admit exactly one replacement runtime.
- [ ] Run one installed Settings cycle and require no invalid-wrapper warning/trace before marking R-56 solved.

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
- [x] Carry only immutable primitive intent: request kind, expected runtime generation, and exact `DisplayManager` identity; no scene revision is currently required.
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

Current settled snapshots:

```text
state                    main RSS   main private   handles   threads   tracked known   RM total/unknown
cold generation 0         848.4       2093.2        1790       61        424.7 MiB         61 / 50
Settings generation 1     949.5       2188.4        1838       67        424.6 MiB         56 / 45
Settings generation 2     946.6       2179.1        1823       62        413.4 MiB         54 / 43
```

- [x] The second Settings cycle did not add another RSS/private/handle/thread/resource step.
- [!] Do not interpret the first one-time uplift as a leak or allocator explanation; the cold state differed in warm-up and visualizer mode, and cause confidence is below 90%.
- [ ] After R-53 repair, run at least five alternating Edit and Settings cycles in normal and Media Center variants.
- [ ] Include all supported visualizer modes as comparison scenarios, playing/paused, transition-time teardown, pending image work, pending ordinary executor work, dual display, and one selected display.
- [ ] Every retired generation must reach zero QObjects, Python owners, resources, timers, animations, subscriptions, callbacks, tasks, lanes, registrations, pixmaps, textures, PBOs, and tracked GL bytes.
- [ ] Equivalent settled RSS, private commit, dedicated VRAM, handles, threads, CPU, and GPU must stop rising approximately linearly per cycle.
- [ ] If ownership reaches zero but memory still rises, begin a new evidence-led retention investigation. Do not alter cache budgets, trim working sets, recycle processes, or weaken teardown without evidence.

# P5.5 — Absolute Resource Footprint, Cache Representations, And R-57

R-57 is a narrow correctness fix and is not blocked by the broader lifecycle or memory-attribution work.

## R-57 required change

- [x] Replace `reversed(selected_indices)` with stable-identity queue partitioning.
- [x] Preserve preferred-path priority, bounded concurrency, generation rejection, exact key/byte accounting, raw-source lifetime, and no duplicate submission.
- [x] Add the decisive fixture: nonpreferred cache-ready request at index 0, preferred cache-ready request at index 1, two available slots.
- [x] Cover preferred first/middle/last positions, stale generation, mixed ready/not-ready rows, and late callbacks after `clear_inflight()`.
- [ ] Run installed transition/image rotation and require no callback failure or unexpected worker fallback increase.

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
- [ ] Record main and child process RSS, private working set where available, private bytes/commit, virtual/mapped/reserved regions, thread count/stack reservation, GDI/USER handles, dedicated/shared GPU memory, and sampler age.
- [ ] Reconcile process totals against exact CPU cache, QImage/QPixmap/display backing, upload/staging buffers, textures, FBOs, PBOs, visualizer surfaces, transition resources, worker mappings, and passive ResourceManager records.
- [ ] Split one-time warm-up/high-water retention from active live ownership and from true per-cycle growth.
- [ ] Compare supported visualizer scenarios only to distinguish shared from genuinely mode-owned resources. Do not infer a mode-specific cause from whole-process totals.
- [ ] If unexplained process memory remains, inspect Python allocations, Qt/native heaps, driver mappings, thread stacks, worker queues/futures, logging buffers, and deleted-but-pending objects in that order.

## Safe optimization candidates

Only promote a candidate after its owner, bytes, lifetime, and visible role are measured:

- [ ] Remove duplicate raw/decoded/orientation-corrected/scaled/QImage/QPixmap/upload representations where one immutable backing can safely serve the same transform/DPR identity.
- [ ] Release transition source textures, temporary FBOs/PBOs, upload buffers, fallback frames, and resized resources immediately at their terminal owner boundary.
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
- [ ] Add one authoritative startup record distinguishing `main` and `main_mc`.
- [ ] Add bounded CUSTOM admission diagnostics: request identity, queued turn, persist-complete timestamp, teardown-start timestamp, stale/duplicate rejection, and manager/shell weakref counts.
- [ ] Add bounded resource-baseline summaries that separate physical resident RAM, private commit, private working set when available, child processes, tracked application bytes, dedicated VRAM, shared GPU memory, and sample age.
- [ ] Deleted Qt-wrapper touches and worker callback failures must be visible as actionable warnings/errors, not only suppressed DEBUG traces.
- [ ] Keep high-volume diagnostics bounded and passive.
- [ ] All warnings and errors remain visible in `screensaver.log`.
- [ ] A critical lifecycle timeout always marks the run failed.

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
