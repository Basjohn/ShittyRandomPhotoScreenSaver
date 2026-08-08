# Phase 5 — CPU and Task Reduction

Date: 2026-08-01
Last updated: 2026-08-08
Branch: `main`
Foundation: closed Phase 4 (`Docs/phase_reports/P04_MEMORY_VRAM_CONTAINMENT.md`)

## Outcome

Phase 5 reduces measured CPU, task, publication, and diagnostic work without changing authored visualizer feel, coupling simulation to paint, or enlarging the 256 MiB CPU-cache budget. It is **in progress**. The implemented slices below are not runtime closure.

Phase 4 is closed by `logs/evidence_chest/07_30_dc8d1741_00_26/`, including startup artwork and media-next during transitions. Older captures that reported a whole-process slope or media/startup collision remain useful historical failed-run evidence, but are superseded as Phase 4 gate evidence. Their CPU/frame-delivery and accounting questions transfer here.

## Current implementation state

### 2026-08-08 18:59 installed assessment — strong recovery checkpoint, final gate open

The exact run is preserved at
`logs/evidence_chest/08_08_after_97ff0619_gl_retention_18_59/`; parser 1.5 output,
the same-parser `08_02` and `849f78e8` comparisons, and all rotated source logs are
stored with it. The parsed source SHA-256 is
`C76A4CEF2A5C84D9AD6D4DA81C90670AD5DB93BE178973E493B94026250E8647`.
The run used the bounded-retention working tree subsequently captured without a
production-code change by commit `3b6082dd`. It is therefore a commit-addressable
recovery checkpoint, though not yet the immutable performance or visual authority.

Commit `afde215d` is the current uninstalled candidate. It adds completed-transition
idempotency, affected-path Bubble/Spectrum temporal gates, and optional adjustable
Spectrum presentation smoothing. No metric below is attributed to that commit until
the fixed-workload installed A/B; `3b6082dd` remains its hard rollback checkpoint.

The generalized 17:07 delivery failure is substantially recovered:

```text
metric                         08_02 Phase 4    17:07 failed      18:59 recovery
app CPU median/max             79.3 / 113.9%   103.0 / 122.3%     83.4 / 102.5%
system CPU median/max          14.7 / 18.1%     42.5 / n/a        21.6 / 25.9%
paint FPS median               96.0              64.4              92.1
paint interval p99 median      32.9 ms           53.4 ms           29.9 ms
paint dtmax median/max         59.8 / 96.4 ms   104.0 / 140.7 ms  58.1 / 138.0 ms
paint-cost p99 median/max       5.3 / 7.7 ms      8.9 / 14.0 ms    5.5 / 9.0 ms
request-age p99 median/max     20.3 / 51.6 ms    44.0 / 68.1 ms   20.1 / 41.7 ms
render FPS median              96.0              64.4              92.2
render dtmax median/max        66.5 / 127.1 ms  106.4 / 141.2 ms  66.2 / 129.8 ms
event-loop late p99 median     38.9 ms           79.6 ms           36.4 ms
event-loop late max          1103.6 ms         1574.5 ms         1251.3 ms
tick-spike median/max          48.6 / 175.6 ms   66.9 / 130.5 ms  51.0 / 94.8 ms
```

The 18:59 PAINT windows span `54.4–151.2 FPS` with median `92.1`; interval p99
spans `15.8–55.2 ms`, dtmax `20.9–138.0 ms`, paint-cost p99 `3.3–9.0 ms`, and
request-age p99 `10.2–41.7 ms`. The worst paint dtmax is a Crumble window. RENDER
windows span `54.5–151.3 FPS`, with dtmax `33.5–129.8 ms`. There is no 165 Hz
display collapse to a 60 Hz divisor, no 60 Hz under-target window, shader fallback,
pending-paint retry/stall, or incomplete transition. Raw owner gaps normalize to
about `18.9/min` total, `10.2/min` over 33 ms, and `8.7/min` over 50 ms, versus
about `29.5/18.7/10.8` in `08_02` and `68.5/41.7/26.8` at 17:07.

Visualizer delivery is healthy enough to preserve as candidate golden evidence.
Bubble tick snapshots span `78.9–117.5 FPS` with median `87.5` and maximum dtmax
`94.8 ms`; final Bubble segments settle at `85.7–89.4 FPS`. Spectrum snapshots span
`84.9–92.7 FPS` with median `90.6` and maximum dtmax `89.0 ms`; its final segments
are `88.8–92.0 FPS`. Bubble final-segment offered/submitted/published ratios remain
`0.997–1.000`, worker work remains roughly `1–2 ms`, and there are no lane
registrations or visualizer safeguard failures. The operator judged Bubble response
good enough for the stricter-golden work, but exact source fixtures and playback
offsets are still required before commit `3b6082dd` can replace `ff934616`.

The run confirms that ordinary Spectrum `bars` mode was not using a display-only
filter over the main rendered bar heights. A new explicitly user-authorized candidate
now supplies optional Spectrum-only presentation interpolation at the existing
authoritative UI visualizer tick, before the GPU frame push. It applies to both Spectrum
render styles, defaults enabled at `0.50`, and is symmetric/time-compensated over a
`2–14 ms` time constant (`8 ms` at default). It adds no timer, scheduler, queue,
paint-local mutation, self-requested repaint, source decimation, Bubble change, or
shared-analysis change. First-frame/identity/pause/disable/teardown boundaries and
UI stalls of at least `100 ms` snap or reset to source. Deterministic attack/drop/
alternation/reset/stall/no-independent-update artifacts pass, but the candidate remains
unapproved until an installed disabled/default/stronger comparison establishes
imperceptible latency and a positive visual verdict.

GL evidence strongly supports bounded PBO retention as a contributor: the recovery
run has zero `[GL TEXTURE] Slow upload` records, versus 15 totalling `411.7 ms` at
17:07. That installed binary exposed two terminal calls per display per transition.
The code-level cause is now corrected: completed-transition cleanup re-entry observes
no live compositor transition and cannot issue a second release or redundant GUI
`update()`, while an empty texture-manager terminal pair cannot reopen/reset metrics.
Focused lifecycle/resource tests and the 45-cycle production-PBO harness prove the
exact current texture and one bounded PBO survive and are reused, larger growth trims
the old PBO, and strict teardown reaches zero textures/PBOs/bytes. The 18:59 evidence
predates this correction, so a fixed low-load installed A/B still owns acceptance.

Resource containment improves but absolute efficiency does not pass:

```text
metric                         08_02 median/max     18:59 median/max
whole-app RSS                  958.9 / 1074.1 MiB   940.7 / 1085.7 MiB
whole-app USS                         unavailable   807.2 / 949.9 MiB
private commit                3018.3 / 3165.4 MiB  2920.0 / 3133.4 MiB
dedicated VRAM                 623.0 / 776.6 MiB    556.9 / 623.8 MiB
shared VRAM                           unavailable     86.5 / 94.5 MiB
tracked GL maximum              313.1 MB / 298.6 MiB  143.7 MB / 137.1 MiB
threads median/max                    89 / 94               91 / 98
handles median/max                  2138 / 2156           2166 / 2219
```

One CUSTOM and four Settings full recreations completed without barrier timeout,
stale identity, invalid-wrapper/disconnect warning, exception, or failed reveal.
Runtime barriers were `235 ms` for CUSTOM and `203–218 ms` for Settings. Settings
dialog-close totals were dominated by `3.4–6.9 s` of user/dialog dwell rather than
runtime teardown. First-frame times for screen 0 were `93, 718, 609, 657, 31, 47 ms`
across cold/CUSTOM/four Settings generations; screen 1 was `0–31 ms`. Equivalent
settled tracked-resource plateaus and exact zero-GL teardown are encouraging, but
this is not the required alternating Edit/Settings matrix and the early screen-0
rebuild tail, handle maximum, RSS maximum, and commitment remain open.

### 2026-08-08 bounded terminal-retention recovery — deterministic candidate

The failed-run evidence supports terminal upload-resource retirement as a plausible
transition-local contributor, not a proved sole cause. The `17:07` candidate logged
15 slow texture uploads totalling about `411.7 ms`, versus two cold-start uploads
totalling about `46.0 ms` in `08_02`; one later `21.7 ms` upload immediately preceded
request-age/event-loop gaps around `67–109 ms`. The candidate machine was also much
busier, so controlled installed evidence remains the causal authority.

Starting from rollback checkpoint `97ff0619`, the isolated recovery candidate changes
only compositor-local GL resource ownership and its deterministic diagnostics:

- terminal presentation retains the exact selected destination texture by existing
  `QPixmap.cacheKey()` identity and deletes every genuinely historical cached texture;
- an upload release retains at most one idle PBO per compositor under the existing
  `64 MiB` production cap; a larger upload creates a replacement and production pool
  trimming deletes the smaller entry;
- full owner/context teardown still deletes the retained texture and PBO, preserves
  failed ownership in strict mode, and cannot claim initialization ended after a
  failed buffer deletion;
- the intended one bounded `[PERF] [GL RETENTION]` record per completed transition reports local
  cache hits, texture allocation/upload/delete counts and bytes, PBO create/reuse/
  delete counts and bytes, PBO-versus-direct uploads, upload time/max, and `>20 ms`
  slow-upload count/time as a stall proxy. These counters are observation only and
  create no timer, queue, callback, repaint, or scheduling dependency. The installed
  18:59 run exposed duplicate terminal calls that reset/reopened this window. The
  completed-transition cleanup path and empty-manager terminal path are now idempotent;
  one installed bracket remains required.

The terminal-idempotency focused gate passes `53` tests with `13` environment skips.
The strengthened 45-cycle harness calls the production PBO acquire/release/trim
seams rather than injecting a synthetic idle buffer; it proves retained texture/PBO
ID reuse on a later transition, larger-size PBO replacement, one sufficient bounded
terminal PBO, exact current-texture retention, and zero texture/PBO bytes after
strict owner resets.
Independent review found no functional blocker after failed-upload delete-byte
accounting was reconciled.

The affected visualizer temporal gate adds versioned synthetic inputs and immutable
expected traces for Bubble discrete-edge publication and Spectrum authoritative-tick
presentation. Bubble runs through the real ordinary `ThreadManager` COMPUTE executor,
publishes the discrete event exactly once on the first lane-free tick, and rejects the
terminal-batching shape. Spectrum records source and presentation values across rise,
settle, drop, a `110 ms` stall snap, and generation reset; it asserts zero independent
timers, paint-local mutations, overlay self-updates, or Bubble/shared-source changes.
The original 66 Phase 2 replay goldens remain unchanged.
Replay schema v1 explicitly disables this later Spectrum presentation candidate and
omits only its two new dotted model fields from the frozen authored-preset hash; the
read-only verifier passes all 66 outputs plus the original manifest. The separate
temporal package therefore adds the candidate hazard light without laundering a new
default into the approved baseline.

Current focused verification after the idempotency/replay corrections:

```text
Spotify visualizer runtime:                 201 passed, 7 skipped
temporal/settings/default/repaint:           178 passed
widgets tab/Spectrum shaping/presets:        187 passed, 1 skipped
GL texture/compositor/resource lifecycle:     53 passed, 13 skipped
Bubble/Spectrum temporal + replay tests:      34 passed
protected Phase 2 replay CLI:                 66 goldens + manifest verified
45-cycle resource harness:                    passed all 14 criteria; 8 KiB repeat RSS drift
```

These are deterministic/harness gates, not substitutes for the installed visual,
fixed-workload performance, lifecycle-matrix, or absolute-resource gates.

The required four-process full-suite sweep was also run with per-chunk logs. Chunks
1–3 completed without timeout with `10`, `7`, and `15` existing unrelated failures;
chunk 4 reproduced native status `0xC0000409` in
`test_base_transition_actual_start_updates_widget_timing`, which aborts the same way
alone because it constructs a `QWidget` without an application fixture. No changed
GL test failed, but the repository-wide suite is not a passing release gate; the
failure families remain actionable in `Future_Cleanup.md`.

This is not installed acceptance. The required falsifier is a fixed-display/image/
cache/transition A/B at low background load. If retained IDs remove later PBO
allocations and slow uploads but request-age, event-loop, paint/FPS, tick delivery,
CPU, and rebuild tails do not return to at least the `08_02`/Phase 4 level, this
hypothesis fails and the candidate rolls back to `97ff0619`. Historical texture
accumulation, larger budgets, visualizer cadence changes, repaint retries, and shared
cross-context GPU storage remain out of scope.

### 2026-08-08 17:07 installed assessment — resource win, performance failure

The candidate at `849f78e8` does not pass Phase 5. Against the preserved `08_02`
comparison, median paint-window FPS fell from `96.0` to `64.4`, paint interval p99
rose from `32.9` to `53.4 ms`, request-age p99 rose from `20.3` to `44.0 ms`, and
event-loop lateness p99 rose from `38.9` to `79.6 ms`. Owner-labelled gaps rose
from 123 to 217, including 85 over 50 ms. Median application CPU was `103.0%`
versus `79.3%` in `08_02` and approximately `65.8%` at Phase 4 close.

The environment was also materially busier: median machine-wide CPU was `42.5%`
versus `14.7%` in `08_02`. This prevents a clean code-only attribution, but does
not excuse the installed result. The run must be repeated under controlled low
background load after the most likely code-linked transition-resource issue is
corrected.

The visualizer evidence points away from Bubble computation. Bubble worker samples
remained roughly `1–2 ms`, offered/submitted/published ratios stayed `0.996–1.000`,
and settled tick FPS reached roughly `90–94`. However, initial/transition tick FPS
fell to `49.2` (the `08_02` minimum was `75.5`) and tick-spike median rose from
`48.6` to `66.9 ms`. Presentation/event-loop delivery, not authored Bubble physics,
is the active failure.

Resource reduction is real:

```text
metric                         08_02 median/max     17:07 median/max
whole-app RSS                  958.9 / 1074.1 MiB   939.6 / 1004.0 MiB
private commit                3018.3 / 3165.4 MiB  2822.3 / 2980.8 MiB
dedicated VRAM                 623.0 / 776.6 MiB    559.3 / 623.9 MiB
tracked GL maximum              313.1 MB / 298.6 MiB  143.7 MB / 137.1 MiB
```

The same logs expose the likely unacceptable tradeoff. Between transitions,
tracked texture/PBO storage often falls essentially to zero. Later transitions
repeatedly perform paired 4K uploads around `20–31 ms`, with startup/rebuild uploads
around `42–57 ms`. The terminal cleanup currently depends on `QPixmap.cacheKey()`
reuse while also deleting idle PBO storage; installed evidence does not show that
the committed current texture is actually reused at the next transition.

The deterministic candidate above now isolates these two policies. It preserves
immediate deletion of genuinely historical textures, exact current-image identity,
and at most one size-appropriate upload PBO per compositor. Installed A/B evidence
must still prove that this removes repeated driver allocation/upload stalls without
restoring the former historical texture staircase, enlarging budgets, or changing
visualizer cadence/behaviour.

Lifecycle behavior in this run was mechanically healthy: one CUSTOM and one
Settings full recreation completed, all runtime barriers passed, first-frame reveal
completed, and there were no runtime exceptions, deleted-wrapper warnings, or
disconnect warnings. Equivalent idle generations did not reproduce the former
large RSS/private-memory staircase, but handles rose from `2116` to `2168`; five
alternating cycles remain mandatory.

The new USS/private split increased each low-rate background usage sample from an
`08_02` median near `21 ms` to about `54 ms`, once per 15 seconds. That is useful
attribution and projects to only about `0.36%` of one core total sampling duty; it
cannot explain the approximately 24 percentage-point application-CPU increase or
the transition-local presentation collapse. Keep the diagnostic, but continue to
measure it rather than assuming it is free.

Mechanical validation completed before this assessment:

- 240 threading/image/resource/accounting tests passed;
- 321 lifecycle/media/Settings/Edit tests passed;
- 658 visualizer-family tests passed with 10 explicit skips;
- all 66 immutable visualizer replay goldens verified;
- the deterministic 45-cycle resource harness passed every criterion with 8 KiB
  repeated-resolution RSS drift;
- the spawned 50x4K shared-memory harness passed with zero live bytes, zero unlink
  failures, and a flat worker-RSS tail.

A direct monolithic `pytest -q` run was stopped despite remaining CPU-active because
the single process had reached about 2.54 GiB working set, 3.28 GiB private memory,
and 133 threads without incremental result visibility. This was not evidence of a
deadlock. The supported full-suite gate is `tests/run_chunked.py`, which isolates
Qt/GL singleton graphs and makes the offending chunk observable.

The assessed resource candidate contains six narrow reversible production
slices exercised by the 2026-08-08 regression capture:

- ThreadManager task accounting no longer queues mutation records and periodic
  statistics publication through the GUI thread. Admission and terminal ownership
  counters remain exact and atomic; the ordinary COMPUTE executor and authored
  visualizer cadence are unchanged.
- Raw image prefetch is omitted when no planned scaled consumer needs it, and
  display prescale now uses the ImageWorker before exact parent raw-decode fallback.
- The assessed `849f78e8` terminal policy retained only the authoritative current
  image texture and released idle upload PBO storage in the owning GL context; the
  bounded recovery candidate above supersedes that all-idle PBO mechanic pending A/B.
- New PBOs no longer allocate full storage once at construction and immediately
  orphan/reallocate the same storage on their first upload.
- Usage evidence now separates whole/main/child private commit and USS in addition
  to RSS. Collection remains a low-rate background `--usage` task.

The pre-change resource detail gave these changes material targets: approximately
235.7 MiB of historical transition textures, approximately 45.7 MiB of retained
upload PBOs, and approximately 117.6 MiB of raw image forms alongside display-ready
derivatives. The installed reductions above confirm that some target bytes were
removed, but Phase 5 remains open because the same run failed CPU and delivery.

The perf-only frame-owner snapshot was retained deliberately. Its exact headless
path measured approximately 6.5 microseconds per call, or about 0.15% of one core at
the dual-display 225 Hz presentation ceiling. It provides useful owner correlation
and is not a plausible explanation for the observed regression. Diagnostic evidence
may not be deleted merely to improve a perf run; diagnostic delivery may likewise
not create GUI scheduling work.

- Latency authority/lifecycle resets and WARNING rate limiting removed the impossible uptime-linear ERROR flood. Generation-matched warnings now track real delivery tails rather than stale uptime; the current 17:07 capture contains ten bounded samples around 82–106 ms.
- The attempted 60 submissions/s Bubble gate with maximum-two batching failed installed visual review and has been removed. A restored-path validation run reached 50,106/50,106 offered/submitted work and is operator-validated for reaction and elasticity; Spectrum retains its existing shared newest-only path for now.
- Ordinary unchanged media polling is a no-op, but one redundant unchanged publication remains after startup/rebuild.
- Frame-gap ownership now points at transition-time Qt/event-loop delivery: 286/286 sampled gaps occurred with transition work active while paint and compute remained cheap.
- Recreated runtimes now wait on a non-reentrant old-generation QObject/resource/task/subscription destruction barrier before replacement construction. Settings has installed evidence. The first installed CUSTOM/Edit admission attempt exposed 64-bit manager identity truncation through Qt `int`; pointer-width signal transport is repaired mechanically, but installed dual-display proof remains open. Private commit, handles, and the five-cycle plateau gate remain open.
- R-56's deleted Settings wrapper retouch and R-57's scaled-prefetch positional removal defect are solved by mechanical tests plus the newest installed run.
- High-volume image-cache entry detail is routed to the cache sidecar; lifecycle resource ownership detail is routed to the lifecycle sidecar. Warnings and errors remain in the main log.
- Cache representation churn remains intentionally downstream of the recreation-ownership proof.

Across all 61 low-rate usage samples in the run, application CPU averaged about 59% with p95 about 95.3% and a transition/recreation maximum of 208.3%. Because the workload includes dialogs, rebuilds, transitions, Bubble, Spectrum, and image work, this is not a controlled before/after CPU win. Restoring Bubble correctness also restores its intentionally high task cadence, so P5.0 still needs a different design rather than claiming a CPU reduction from this run.

The earlier 2026-08-08 15:51–15:55 run was already a delivery regression against the preserved 08_02 comparator. Median application CPU rose from 79.3% to 103.2%; median paint-window FPS fell from 96.0 to 72.5; paint interval p99 rose from 32.9 to 41.0 ms; request-age p99 rose from 20.3 to 30.3 ms; event-loop lateness p99 rose from 38.9 to 57.6 ms; and the worst owner-labelled gap rose from 127.7 to 186.2 ms. Its final runtime spent about 70% of its sampled life rendering transitions versus about 35% in the comparator, and machine-wide CPU was commonly about 35–39% versus about 14–18%. The 17:07 assessment above supersedes it as the current failure.

Parser 1.5 repaired a derived-evidence defect: nested `tm_categories` JSON had been discarded whenever the newer `tm_delivery` object followed it on the same line. Recovered owner rates show comparable high-rate intervals in both runs at roughly 69–70 audio-analysis tasks/sec plus 92–93 Bubble-simulation tasks/sec. Submission frequency therefore did not newly increase, and these logs do not authorize a visualizer cadence change. The remaining regression needs a controlled workload and stronger per-owner execution/delivery attribution.

## P5.0 — Visualizer authored cadence

- [!] The 60 submissions/s maximum-two batching attempt failed the 2026-08-01 installed run. Of 2,566 offered steps, only 1,723 tasks were submitted: 842 were artificial cadence deferrals versus one worker-busy deferral. Only the terminal snapshot of each batch was published, so an impulse could be integrated and already decaying before its first visible result; the older packet could also consume a live scheduler edge intended for the newer packet.
- [x] Validate the restored lane-free path: the dedicated restored-path run reached 50,106 offered and 50,106 submitted lane-free steps (ratio 1.000) with no artificial cadence deferrals and roughly 1–2 ms worker execution. Later intervals stayed near 89 FPS with only isolated genuine worker/result ownership deferrals. The operator confirmed restored immediate Bubble reaction and elasticity.
- [x] Add a runtime-shaped source/discrete-edge-to-first-visible temporal oracle. The 100 Hz recurring-tick test authors a discrete kick at the exact phase deferred by the rejected 60 Hz token gate and requires that edge to appear in the first lane-free visible state. It fails terminal-only edge-plus-quiet batching while preserving the current one-step authored path.
- [ ] Compare input-to-visible latency, p99/max delivery, and CPU/task cost before/after any new design. Do not reintroduce a second cadence authority, terminal-only multi-step batching, or live scheduler capture merely to improve the counter.
- [-] Exercise Spectrum on its unchanged shared newest-only path and Bubble → Spectrum → Bubble. The optional candidate now smooths presentation bars only on the existing UI visualizer tick, with disabled/default/stronger settings and deterministic hazard lights; installed paint receipt, mode-switch review, and user approval remain open.
- [ ] Reject any optimization that turns paint delivery, feedback animation, or a retry timer into the visualizer clock.

## P5.1 — Frame-delivery owner telemetry

- [-] Add/passively consume owner-labelled render, submission, GUI callback, update-request, and paint timestamps without creating UI work or a new timer/queue.
- [-] The 18:59 recovery run supplied 124 owner-labelled gaps over 393 seconds: 67 exceeded 33 ms, 57 exceeded 50 ms, and the maximum was 138.0 ms. Normalized rates improve over both `08_02` and the 17:07 failure, but the Crumble and event-loop maxima remain open. Last-callback labels remain correlation rather than sufficient causal attribution.
- [x] Resolve the known transition-label hole: owner telemetry now accepts the compositor display-transition `name`, which was present on the 62 active records but previously ignored.
- [x] Make the transition-local GL retention bracket mechanically singular. Completed cleanup re-entry and an empty manager pair are idempotent; deterministic tests and the 45-cycle production-PBO harness prove retained IDs/reuse, growth trim, and strict zero teardown without a redundant GUI update.
- [!] Capture the corrected bracket installed. The 18:59 binary still has duplicate terminal records, so do not use its counters causally until the fixed A/B shows exactly one terminal record per real transition.
- [ ] Correlate those GL records with request-age, event-loop lateness, paint delivery, CPU, and resource snapshots in the fixed-workload installed A/B; lifetime totals or unmatched-machine comparisons are not causal proof.
- [ ] Correlate the now-labelled transition owner with logical scene age, event-loop lateness, queue/callback tails, and per-display request-to-paint delay in the next installed capture.
- [ ] Attribute delayed delivery to its actual owner before changing cadence mechanics; a healthy render clock with delayed paint is event-loop delivery starvation, not permission to add repaint retries.

## P5.2 — False visualizer-latency diagnostics

- [x] The latest run has no impossible uptime-linear latency values and no false visualizer ERROR flood. Ten bounded WARNING samples remained at roughly 82–106 ms with matching engine/frame generations and activation identities.
- [x] Separate passive Bubble source age, logical simulation-step age, render-state application age, and existing request-to-paint age in frame-gap owner diagnostics. These timestamps are observation-only and create no timer, queue, repaint, or scheduling dependency.
- [ ] Validate the separated ages in an installed transition capture and classify the remaining 82–106 ms warnings against request-to-paint delivery.
- [ ] Prove diagnostic warnings neither claim a mode regression from presentation delay nor hide a real first-frame, mode-switch, or audio-input failure.

## P5.3 — Unchanged media repaint churn

- [-] Preserve the unchanged-media poll no-op through idle, transition, startup, and media-next scenarios.
- [ ] Measure media-card paint/update requests and layout mutations for unchanged key/metadata; require no recurring repaint, Qt structural mutation, artwork decode, or pixmap replacement.
- [x] The 17:07 run contains no recurring unchanged fixed-card publication signature; preserve the no-op and the intentional changed-artwork layout refresh.
- [ ] Keep changed artwork/title and transition-time feedback contracts from Phase 4 intact; validate current-key updates remain responsive without reviving the historical 30–38-paint burst.

## P5.4 — Memory/driver accounting and repeated edit/rebuild cycles

The preserved `07_30_ce1ba31c_5_34` operator capture exposed a distinct session-lifetime staircase during equivalent-state recreation. Main RSS advanced from about 832.5 MiB initially to 911.5 MiB after one Edit reload, 1,000.6 MiB after a second Edit reload, and 1,146.8 MiB after a Settings restart. Dedicated VRAM advanced from about 554.8 to 600.8, 722.9, and 806.7 MiB, while tracked known bytes stayed near 456.9, 455.9, 471.7, and 489.1 MB. Teardown itself still returned tracked GL, texture, PBO, and display-pixmap bytes to zero and substantially reduced driver VRAM, so strict GL cleanup remains authoritative. ResourceManager unknown registrations nevertheless rose from 35 to 52 to 74, including GUI components and timers. This is Phase 5 ownership work and does not reopen Phase 4.

An earlier preserved 17:23–17:38 installed run was an undeniable improvement but still not the required five-cycle plateau proof. It completed Settings → generation 1, CUSTOM → generation 2, and Settings → generation 3 recreation. Equivalent settled main RSS was about 900.9, 901.2, and 895.2 MiB; dedicated VRAM about 539.2, 554.9, and 540.0 MiB; and ResourceManager total/unknown counts 58/47, 58/47, and 56/45. The former approximately 80–90 MiB main-RSS, large VRAM, and 35 → 52 → 74 unknown-registration step per recreation did not recur. Both Settings exits crossed their dialog barriers, constructed fresh runtimes, and were operator-validated.

The residual accounting prevents closure. Equivalent total private commit rose about 2,911.4 → 2,944.7 → 3,000.2 MiB and total handles rose 2,130 → 2,146 → 2,189; direct main-process lifecycle samples similarly rose from about 1,792 to 1,810, 1,831, and 1,863 handles. Worker RSS stayed about 96.4–98.3 MiB, all 34 shared-memory segments were consumed, live shared-memory bytes remained zero, and unlink failures remained zero. Threads returned broadly to 90–94. The first reconstruction also carried a one-time roughly 60 MiB main-RSS rise versus the cold state; only additional equivalent cycles after every retired owner is absent can classify that as a plateau/high-water effect.

That earlier capture still logged diagnostic-only surviving Python wrappers: two `WidgetManager` plus two `FadeCoordinator` instances after Settings, and those plus two `CustomLayoutManager` instances after CUSTOM. They had no retiring-generation ResourceManager/task/subscription ownership at barrier completion, but the acceptance contract still requires retired Python roots to reach zero. Their explicit release or bounded post-continuation proof remained open at that checkpoint; the current focused tests and 17:07 barrier result improve the evidence, while the five-cycle installed matrix remains the closure gate.

A later preserved two-Settings run did not support a plateau claim. Equivalent Bubble replacement snapshots were:

```text
state                    main RSS   main private   handles   threads   tracked known   RM total/unknown
cold generation 0         786.6       1994.7        1782       61        338.6 MiB         60 / 49
Settings generation 1     917.6       2103.7        1862       68        403.1 MiB         55 / 45
Settings generation 2     977.2       2177.8        1841       64        416.7 MiB         55 / 44
```

Generation 1 to 2 therefore added about 59.6 MiB main RSS and 74.0 MiB main private bytes while tracked known bytes added only about 13.6 MiB. ResourceManager totals/unknowns did not climb, handles and threads fell, retired ownership cleared, tracked GL/display bytes reached zero during teardown, the image worker stayed bounded, and shared-memory live bytes/unlink failures remained zero. Two cycles do not prove a linear leak, but whole-process containment remains unproven and active.

- [-] Validate generation-scoped ResourceManager registration metadata, weak passive cleanup observation, QObject-destroyed release, retained-bound-callback reporting, and process/runtime scope separation on the installed runtime.
- [x] Validate installed zero-owner release for `WidgetManager`, `CustomLayoutManager`, and `FadeCoordinator` through one CUSTOM recreation. Production-shaped teardown tests release two of each observed owner before continuation without `gc.collect()`, and the 17:07 installed CUSTOM barrier completed without a retiring-owner timeout. The five-cycle plateau gate remains open.
- [x] Give `WidgetManager` explicit ownership state for its one-shot `image_displayed` connection. The first-frame handler clears ownership before disconnecting, terminal cleanup is idempotent, a real PySide signal regression proves exactly one disconnect, and the 17:07 run contains no repeat `RuntimeWarning`. The authoritative first-frame gate remains unchanged.
- [-] Validate Settings, committed CUSTOM Edit, and monitor recreation as two-stage operations. Settings and one dual-display CUSTOM Save-and-Continue have installed proof; CUSTOM persists and retires its Edit session first, returns from manager-owned frames, then admits unchanged full teardown through an immutable engine-owned later-turn request. Repeated-cycle and monitor-recreation coverage remain open.
- [-] Confirm terminal shutdown disarms replacement continuations and creates no QObject/timer work after Qt starts closing; timeout must fail closed rather than construct alongside a surviving retired graph.
- [-] Confirm SettingsDialog/Edit-owned callbacks, timers, animations, panels, handles, models, and global clock subscriptions are generation-owned and destroyed rather than hidden or cached.
- [-] Confirm closing Settings completes the dialog destruction barrier and then constructs/reveals the replacement runtime. RUN sessions disable Qt last-window auto-quit only after successful engine startup; explicit engine/tray/error routes remain terminal authorities.
- [-] Correlate synchronized lifecycle snapshots at stop, generation invalidation, producer stop, strict GL cleanup, queued destruction, confirmed root destruction, replacement construction, authoritative first frame, FadeCoordinator reveal, and settled replacement. Use the latest already-collected `--usage` sample for total RSS/private commit/VRAM; lifecycle logging must not issue a new driver query.
- [x] Deterministic five-cycle alternating Settings/Edit ownership regression requires the barrier to observe nonzero resource, delayed-callback, and global-subscription ownership, then proves zero retired-generation ownership and one continuation per generation.
- [ ] Run at least five installed alternating Settings/Edit cycles with Bubble, Spectrum, Bubble → Spectrum → Bubble, active transition near teardown, pending image work, media polling/artwork, and idle settle windows.
- [ ] Require every retired generation to reach zero QObject roots, timers, animations, subscriptions, ThreadManager work, and ResourceManager entries before replacement; require stable handles/threads and no approximately linear equivalent-state RSS/private-commit/VRAM increase.
- [ ] Preserve the separate authoritative-first-frame barrier and existing FadeCoordinator reveal. No retired frame, prior activation, zeroed Spectrum state, or previous-mode Bubble state may satisfy replacement readiness.
- [ ] Use one diagnostic-only `gc.collect()` only if needed to classify a proven residual Python cycle; it may not become production cleanup. Do not use process-event pumping, repeated GC, trimming, recycling, worker restart, cache growth, or runtime reuse.

## P5.5 — Cache representation churn

- [ ] Profile raw/scaled/GUI backing co-retention, prefetch future bytes, transformations, and cache hit usefulness under representative cycling.
- [ ] Remove only measured redundant representation/copy churn while retaining exact source/transform/size/mode/DPR identity and existing newest-only/stale-generation ownership.
- [ ] Keep the CPU image cache at its 256 MiB production ceiling; do not add pins, enlarge budgets, or use trimming/GC as a substitute for owner evidence.

## P5.6 — Logging hygiene

- [x] Recovery parser 1.5 decodes nested task-category counters independently of a trailing delivery JSON object and has a regression fixture for the production log shape.
- [-] Keep latency diagnostics and warnings bounded, sampled, passively collected, and rate-limited.
- [-] Verify `--perf`/`--viz` output has owner labels and correlation fields sufficient to diagnose delivery without per-frame INFO logs, whole-state dumps, or new diagnostic work queues.
- [-] Verify per-entry image-cache hit/miss/put/remove/eviction detail appears only in `screensaver_cache.log` when `--cache` is active; keep one bounded `[PERF] [CACHE]` lifecycle summary for correlation.
- [-] Verify bounded per-resource generation/owner/site detail appears in `screensaver_lifecycle.log` only when `--life` is active; ordinary aggregate resource counters remain in `screensaver_perf.log` without duplicating the resource list.
- [ ] Confirm warnings/errors remain visible in `screensaver.log`; rate limiting may coalesce repeats but must retain count/window/owner context and never change runtime control flow.

## Runtime gate

- [ ] Capture before/after evidence for idle, Bubble, Spectrum, mode switch, active transition, image decode, and at least five alternating Settings/Edit/CUSTOM rebuild cycles under controlled background load.
- [ ] Require materially lower task/CPU cost, equal-or-better p99/max frame delivery, preserved visualizer runtime review, bounded memory/driver accounting, and no new synchronization or UI-pressure workaround.
- [ ] Record environment, commit, parser version, excluded intervals, rollback, and unsupported platform measurements before marking Phase 5 complete.

## Non-goals

Do not remove the Phase 8 presentation-worker architecture here, add threads/processes without latency/GIL/memory evidence, change the compositor topology, turn diagnostics into control flow, or modify visualizer creative settings solely to improve a metric.
