# Performance Optimization Contract

This document is the canonical admission/acceptance contract for SRPSS performance work on the accepted Qt Quick runtime.

Read it before changing cadence, scheduling, GC policy, resource lifetime, Quick presentation, Visualizer analysis, caching, or instrumentation in the name of performance.

Cross-links:

- live sequence/checklists: `Current_Plan.md`
- global safety priority: `Docs/Guardrails.md`
- Visualizer presentation/reactivity: `Docs/Guardrails/Visualizer_Presentation.md`
- Bubble temporal fidelity: `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- R-69 failed viewport-compression lesson: `Docs/Historical_Bugs/R-69_Bubble_Extreme_Viewport_Global_Radius_Compression.md`
- R-71 audio-allocation/GC history: `Docs/Historical_Bugs/R-71_Visualizer_Audio_Per_Frame_Task_And_DSP_State_Allocation.md`
- final installed/physical acceptance: the feature's own Reference/Future_Work/Historical_Bugs doc + `Docs/TestSuite.md`

## Retired audit proposals (R-100 and legacy repaint failures)

The September 2026 runtime audit explicitly rejected treating small theoretical CPU savings as permission to weaken the accepted logical freshness, Bubble fidelity, or Qt Quick scheduling authority. Do **not** re-propose, without new measured evidence, forced swap interval 1, arbitrary GIL switch/GC tuning, render-thread priority boosts, visualizer cadence/Update coalescing, speculative per-frame presentation caches, a Python display-refresh timer or `frameSwapped → requestUpdate()` rescue, legacy pending-paint/paint-ack throttles, or restoring the old QWidget/GL overlay repaint machinery. These ideas were tested or rejected for architecture/fidelity reasons, not merely forgotten. Keep diagnostic deep traces opt-in and outside normal frame work. An old repair's **30-second/no-paint** workaround is not current Qt Quick policy.

## 1. Definition of good performance

SRPSS performance is good when the application remains **fresh, reactive, smooth and bounded under realistic load**. Lower counters are useful only when those qualities remain intact.

Priority order:

1. correctness and authored visual behavior;
2. source/snapshot freshness and Visualizer reactivity;
3. rare-stall / p95-p99-max behavior;
4. lifecycle/resource stability across recreation;
5. physical smoothness/pacing;
6. removal of measured useless work/allocation;
7. CPU/GPU/task/count averages;
8. cosmetic benchmark numbers.

A change that improves a lower item by damaging a higher item is a regression.

## 2. Golden invariants — performance work may not weaken these

Before any performance patch, confirm every relevant box remains binding:

- [ ] Visualizer authored/logical evolution remains approximately the intended ~90 Hz class when active.
- [ ] Newest-state semantics remain intact; do not add FIFO/catch-up queues or deliberately present stale history.
- [ ] Source/snapshot age remains healthy; a prettier FPS/GC/CPU number with materially older visible state is not an optimization.
- [ ] Bubble preserves R-69: no global viewport-dependent compression of head/radius response, motion, Ghost/history displacement or other authored reaction.
- [ ] Spectrum/Oscilloscope/Sine/DevCurve geometry adaptation may reframe/reflow/smooth presentation but may not quietly weaken musical response.
- [ ] Bubble temporal fidelity/integration remains intact; do not skip authored logical steps to reduce work.
- [ ] If Bubble itself is touched, idle traces are not acceptance: require an active-music physical lane proving source freshness, attack/settle, elasticity/breathing, loud-passage expansion, ghost/tail motion and operator feel.
- [ ] The persistent `visualizer.audio_analysis` lane remains one-in-flight + newest-pending, with no per-frame generic Future/task fallback.
- [ ] Media remains native-event-owned plus slow reconciliation/watchdog; no fast polling resurrection.
- [ ] Cursor Halo passive pointer motion remains native `QCursor` presentation; do not turn pointer motion back into QML scene invalidation.
- [ ] R-63 keeps `black=0`; a harmless bounded shared-edge device-pixel overshoot is preferable to exact-cover logic that can revive fullscreen-flip black flashes.
- [ ] Ordinary CUSTOM uniform scale remains absolute/persisted with the shared 40% floor. Any admitted family `content_extent` remains orthogonal session-owned reflow state and must not become a second scale/normalization/cadence authority. Visualizer keeps independent scale vs viewport extent.
- [ ] No silent performance fallback changes renderer, presenter, source owner, cadence owner, analysis owner, or degraded observation semantics.

## 3. What performance work should target

### P1 — rare latency tails first

The current primary performance debt is **rare stall severity**, not sustained GPU saturation or a generally stale Visualizer.

Target, in order:

- [ ] attribute repeatable >100 ms active stalls to GC, GUI/event loop, provider work, synchronization, transition/image work, or render/presentation ownership;
- [ ] reduce p95/p99/max and severe-gap counts without worsening median freshness/reactivity;
- [x] distinguish recreation/teardown intervals from ordinary steady-state stalls (lifecycle windows, section 5);
- [ ] fix instrumentation that carries stale timestamps across runtime recreation before tuning from those numbers;
- [ ] prefer removing a named allocation/lifetime/work source over changing GC thresholds or hiding pauses.

### P1A — prefetch and widget completion admission

- A request for N pending-image previews must inspect at most N queued candidates; never materialize an entire source-sized deque for a tiny lookahead.
- Ban Image's eligible-only source index is authoritative in ordinary Next/Peek/Preview. Preview simulation must never clone the rejected full catalogue, hash every candidate or consult the filesystem. Reindexing is allowed only when the source catalogue or ban status changes.
- Visualizer stalls during News/Feeds activity must be correlated by timestamps and callback duration, not blamed on the visualizer or on stable diagnostic instrumentation. Slow GUI deliveries may be logged through the existing perf gate; never introduce a new poll/thread/timer or use telemetry alone as proof of causality.
- The GUI publication boundary and all widget-specific delivery callbacks remain distinct suspects for intermittent stalls. Protect Qt Quick scheduling and Bubble temporal semantics.

### P2 — allocation/lifetime mechanisms with exact owners

The R-71 work proved the preferred shape:

```text
measured repeated allocation/task machinery
-> exact owner identified
-> remove/reuse that machinery
-> preserve freshness/correctness
-> remeasure tails + resource stability
```

Further GC work is admitted only when a similarly clear mechanism exists.

`RuntimeGCPolicy` freezes the stable tracked set once per RUN after the existing startup warmup. It does not freeze on
each display/mode generation. The existing boundary log reports `freeze_boundary_ms` for freeze, active-threshold restoration
and frozen-object count observation; `snapshot()` retains that one observation. This adds no recurring sampler and never logs
from a GC callback. Measure a loaded RUN before attributing a stall to this boundary; historical cost estimates are not bounds.
The original thresholds and frozen set are restored on policy stop. Resource retirement must still break its own references.

- [ ] Do not tune GC thresholds merely to reduce collection counts.
- [ ] Do not trade immutable/stable input snapshots for shared mutable state without a correctness proof.
- [ ] Do not reduce publication cadence or transient fidelity to reduce tracked allocations.
- [ ] Do not defer cleanup indefinitely just to move a pause outside the measured window.

### P3 — resource plateau / recreation stability

Resource optimization targets **growth and bad lifetime**, not arbitrary small numbers.

Track across settings/CUSTOM/runtime recreation and long soak:

- [ ] RSS and USS plateau rather than generation-over-generation growth;
- [ ] dedicated/shared VRAM returns toward the expected teardown floor and rebuilds to a stable runtime range;
- [ ] thread/handle counts remain bounded and return toward their ordinary range after temporary work;
- [ ] provider/image workers have explicit owners and retire when required;
- [ ] caches remain bounded by intentional caps; do not destroy useful hot caches merely to make Task Manager numbers smaller.

### P4 — CPU/GPU/task efficiency after freshness is safe

- [ ] remove no-op property churn, duplicate provider/model work, redundant scene invalidation, unnecessary task/future construction, and needless resource regeneration;
- [ ] attribute CPU work to GUI, Python/GIL, logical runtime, provider, Quick render thread or OS presentation before changing architecture;
- [ ] attribute GPU cost to actual active presentation/effects rather than blaming the currently visible Visualizer by association;
- [ ] lower stable CPU/GPU only when the same visible output and reaction/freshness contract is preserved.

### P5 — zero-work, isolation and ownership hygiene

The no-op path must be genuinely quiet. Short-circuit identical state before stable cache rebuild, provider refresh,
Settings write, geometry replay, fade restart, worker submission, signal fan-out, Quick property churn or GPU resource
regeneration. Attribute work to its real domain (GUI thread, Quick render thread, Python/GIL, logical runtime, provider,
or OS presentation) before changing architecture.

#### Effect dormancy and count invariance

Registered but inactive effects must contribute no recurring runtime cost to the effect currently in use. This applies to
Visualizer modes, transitions, and any future selectable render/effect family. Registration, activation eligibility and
persisted configuration are metadata; they are not runtime admission.

At runtime, only effects explicitly admitted for the current presentation may own effect-specific logical evolution,
simulation, compute dispatch, renderer work, GPU resources, history buffers, environment preparation, workers, callbacks or
timing sources. A bounded, explicitly reserved next-transition warm-up is also admitted because it is the known next run, not
speculative work across the registry. Every other inactive effect may retain only cheap registry/configuration state and
explicitly sanctioned shared infrastructure.

Adding another registered effect must not add another per-tick, per-frame, per-transition-frame or per-image dispatch/check to
unrelated active effects. Do not grow common hot paths into one unconditional `dispatch_*()`, `update_*()` or equivalent call
per registered implementation, even when those calls immediately return. Resolve the admitted implementation at the relevant
activation/run boundary and invoke only that owner.

For transitions, the current run owns only its selected implementation and the shared Scene3D/resources it actually requires;
the one explicitly reserved next run may perform its bounded gradual warm-up. Unselected transitions do not prepare shaders,
advance simulations, allocate targets/buffers, maintain histories or perform source/destination processing merely because they
are registered. Replacing the reserved next run retires any preparation no longer owned by the replacement.

For Visualizers, exactly the active mode may own mode-specific logical and render work. A replacement mode may prepare behind
its admitted hidden reveal, but unrelated inactive modes are not advanced, queried, rendered or allowed to retain
consumer-specific runtime/GPU resources after retirement.

The scaling invariant is:

**N registered effects + one admitted active effect remains approximately the runtime cost of that admitted effect, not N
dormant effects.** The only intentional exception is the bounded work/resources of one explicitly reserved next-transition
warm-up while that reservation exists.

Tests must guard against mode/effect-count scaling in common hot paths and prove that inactive implementations do not acquire
or retain effect-specific runtime resources.

The speculative image process remains an approved isolation boundary, not a second presentation owner: foreground image
work cannot queue behind it; parent-owned generation/byte/backlog bounds admit at most one speculative request at a time;
late generations are tombstoned; failure skips speculative warm-up rather than falling back into the main-process compute
pool; and `ProcessSupervisor` remains the single response-queue reader while routing heartbeats, correlations and stale
completions. Worker retirement cancels callbacks and releases transport/cache candidates without touching Qt/Quick/GPU
state.

Startup/recreation may prepare deterministic current-generation work while hidden, but reveal is readiness-owned rather
than fixed-sleep-owned. Native code is admitted only for a measured local bottleneck and remains subordinate to the one
Quick-window-per-display topology.

## 4. 2026-09-01 reference envelopes — evidence, not hard SLAs

These numbers are reference points from the accepted Quick architecture. Different hardware/load/topology can legitimately differ. Use them to recognize **shape changes**, not to fail a machine for missing an exact number.

### Heavy-load acceptance reference

```text
Visualizer logical publication: ~89-90 Hz when active
Typical snapshot age:           ~18-22 ms
Audio analysis mean compute:    ~1.86 ms
Audio callback work:            ~0.067 ms
Generic per-frame Future path:  0
Gen-0 collection rate:          ~9.8/s
Gen-2 collection rate:          ~0.39/min
Residual deep gen-2 pauses:     ~130-146 ms
```

Interpretation: the architecture remained fresh/reactive under deliberately heavy external load, but rare deep latency tails remained.

### Modest-load quality reference

The later modest-load run felt very good physically and provides a useful healthy-quality envelope:

| Metric | Reference observation | Meaning |
| --- | ---: | --- |
| active Visualizer rendered cadence | ~59.99 FPS median on the 60 Hz Visualizer display | presentation tracks the physical panel without redefining authored time |
| active Visualizer logical revisions | ~89.92 Hz median | authored cadence remains intact |
| active Visualizer snapshot age | ~19.71 ms median | newest state normally reaches presentation quickly |
| Bubble revisions | ~89.94 Hz median | Bubble retains the golden authored cadence |
| Bubble snapshot age | ~20.27 ms median; ~31.13 ms p95 | useful freshness reference; rare recreation/stall outliers must be classified separately |
| geometry mismatches | 0 in ordinary active samples | presentation authority is coherent |
| audio lane | 18,771 accepted/completed/published; 0 busy/stopped rejects/cancels | persistent lane is keeping up |
| audio lane execution | 1.325 ms mean | analysis is not a steady-state bottleneck |
| audio callback | 0.049 ms mean | callback delivery is cheap |
| retained DSP state | 18,763 reuses / 8 rebuilds | ordinary frames avoid full-state reconstruction |
| gen-2 pauses | 48.75 / 56.18 / 50.66 / 67.69 ms | pause severity was dramatically below the heavy-run 130-146 ms tail |
| app process CPU | 94.68% mean (Windows process convention; roughly one logical CPU) | reasonable for the active dual-display/runtime workload; not a reason to sacrifice reactivity |
| whole-system CPU | 28.61% mean | system retained headroom |
| GPU busy | 2.61% mean; 1.7% median; 4.61% p95; 19.9% max | sustained GPU pressure is currently low |
| RSS | 854 MB mean; 941 MB max | moderately heavy but stable/explicable |
| USS | 755 MB mean; 841 MB max | unique resident usage is below RSS and stable |
| private commit | ~2.59 GB mean | virtual/private committed space; do not confuse with physical resident RAM |
| dedicated VRAM | ~436 MB median while active; observed ~7 MB teardown floor | graphics resources demonstrably release/rebuild across recreation |
| threads | ~95 mean | inventory/cleanup candidate only if ownership/growth proves waste |
| handles | ~2,089 mean | same: stability/lifetime matters more than an arbitrary target count |

Important comparison: raw GC collection frequency can move independently of perceived quality. The modest run did not win every collection-count statistic, yet the worst deep pause was ~67.7 ms instead of ~130-146 ms and the run felt materially better. **Optimize latency tails and freshness, not collection count in isolation.**

### 2026-09-01 paired Bubble hitch / Gen2 evidence

A later operator comparison of two runs at different overall load provides a stronger attribution seam than aggregate collection counts:

- every observed generation-2 collection in both sampled runs coincided with a Bubble **wall-clock inter-tick gap** of the same order;
- the newer/lighter sample contained Gen2 pauses of roughly **47.3 ms and 41.2 ms**, paired with Bubble gaps around **50.7 ms and 46.1 ms**; both Gen2 scans collected **zero objects**;
- the older sample showed the same shape with roughly **49–68 ms** Gen2 pauses;
- Gen2 recurrence in those samples remained roughly on the same ~75–79 second scale despite the newer run carrying less load;
- the compared builds contain no Bubble runtime change across the relevant seam, so this recurrent hitch class predates the lifecycle-fade slice;
- non-GC stalls also exist, so GC is a proven recurring hitch class rather than a complete explanation for every visible hitch.

Interpretation: a stop-the-world pause can be highly visible while Bubble's measured compute cost, FPS/cadence and rolling ms counters remain healthy, because the process is paused **outside** the measured Bubble work and the next calculation resumes cheaply. A zero-yield Gen2 pause also proves that "objects collected" is not a useful proxy for pause cost; long-lived tracked graph scanning/lifetime shape remains a candidate.

If GC mechanism hunting is reopened, instrumentation should correlate GC callback start/stop timestamps, generation/duration/yield, process wall-clock inter-tick gaps and active GUI/Quick presentation timing in one epoch. When mechanism hunting is needed, prefer bounded tracked-object/type/lifetime evidence around the pause over collector-threshold experiments. Do not remove the scalar Bubble fades, lower authored cadence, or move forced collections merely because aggregate counters look cleaner.

## 5. Telemetry interpretation guardrails

Do not optimize a number until its semantics are understood.

**Startup and teardown are not stall points.** A runtime starting up or tearing down (cold start, Settings, exit, monitor or layout replacement) spikes by design: windows, scene graphs, programs and images are built or dropped at once. Never count, rank or chase those frames as stalls or spikes. The one lifecycle question is poisoning: are frames *after* the generation's coordinated reveal late? `core/diagnostics/lifecycle_window.py` marks each window (opened at cold start, Settings pause and every `teardown_display_runtime`; closed by the coordinated reveal). Inside it the Visualizer's dt-spike, slow-tick and latency warnings and the event-loop stall recorder stay silent, and `--frame-trace` records `lifecycle_begin`/`lifecycle_end`, from which `tools/frame_trace_report.py` prints steady-state swap spacing without the windows and a `post_lifecycle_2s` poisoning line.
- [ ] **Demand-light `dt_max`:** a display with nothing to redraw may intentionally go a long time between swaps. A multi-second `dt_max` on that surface is not automatically a multi-second active rendering stall. Pair it with demand/activity, active-display timing and visible behavior.
- [ ] **High-refresh pacer skip:** overdue target deadlines can be collapsed into freshest-state presentation. `skip_pct` is not automatically “that percentage of visible frames dropped.” Pair it with physical cadence, Visualizer logical revision rate and snapshot age.
- [ ] **Quick presentation authority:** do not treat raw ``frameSwapped`` rate or generic VSync doctrine as a sufficient performance oracle. The installed mixed-refresh A/B rejected forcing Quick ``swapInterval=1`` and restored the known-good release-era interval-0 policy. Any future surface/pacer change must be compared against 5.0.0/5.0.1 on real single- and multi-display hardware and judged by operator-visible pacing, freshness, interaction latency and transition smoothness together—not one counter in isolation.
- [ ] **Recreation latency:** stale pre-recreation timestamps can create absurd multi-second latency warnings immediately after a runtime rebuild. Fix/reset telemetry epochs before using those warnings as performance evidence.
- [ ] **GC count:** frequent cheap collections can feel better than rare 150 ms collections. Track generation, duration, yield and correlation with visible/event-loop stalls.
- [ ] **Process CPU:** Windows process CPU may exceed 100% because 100% is approximately one logical processor, not the entire machine.
- [ ] **Private commit vs RSS/USS:** committed virtual/private address space is not equivalent to physical resident RAM.
- [ ] **Cache memory:** bounded decoded/scaled image caches intentionally exchange RAM for lower latency. Optimize leak/growth or bad eviction, not the existence of a useful bounded cache.
- [ ] **Named-window metric history:** a causal/steady window may not score a rolling metric whose retained samples cross the window boundary unless that history is explicitly sliced/reset. A post-boundary delay is not a substitute when the metric's retention horizon is longer than the delay. Keep ordinary rolling diagnostics if useful, but causal harnesses must consume window-local evidence and fail stale/unsliceable logs closed (R-80).

## 6. Performance-change admission checklist

Before editing production code for performance:

- [ ] **Reproduce before instrumenting:** if the target symptom is not currently reproduced by a trustworthy oracle or direct physical observation, do not add new counters/timers/samplers/profiler branches to chase it. First reproduce the actual symptom with the existing evidence plane. New instrumentation is admitted only after a failing condition exists and the missing fact is named.
- [ ] Name the exact observed problem: stall tail, allocation source, CPU owner, GPU owner, leak/growth, task churn, provider duplication, etc.
- [ ] Record the relevant load class: modest, representative heavy, transition-heavy, recreation-heavy, soak, installed/frozen, or another explicit cell.
- [ ] Identify which existing metric proves the problem and which metrics protect freshness/reactivity.
- [ ] State exactly what work/allocation/lifetime should disappear.
- [ ] State which owner remains after the change.
- [ ] Confirm the change does not violate any golden invariant in section 2.
- [ ] Prefer one bounded mechanism change so before/after evidence remains attributable.
- [ ] If the proposal is “lower cadence”, “add debounce”, “coalesce more”, “shrink response”, “change GC threshold”, “drop history”, “reduce cache” or “add fallback”, require a stronger mechanism-specific proof before proceeding.

## 7. Performance-change acceptance checklist

After the change:

- [ ] Visual behavior/reactivity physically remains correct at canonical and relevant extreme geometry.
- [ ] Visualizer logical revisions/source/snapshot age remain healthy.
- [ ] Bubble integration/freshness and R-69 remain intact when Bubble is affected.
- [ ] No queue/backlog/fallback/new cadence owner appeared.
- [ ] p95/p99/max or severe-gap behavior improved or remained healthy under the same load class.
- [ ] Resource counts plateau across recreation/soak where relevant.
- [ ] CPU/GPU/task improvements are reported with context rather than as isolated victory numbers.
- [ ] Modest-load quality remains good after any heavy-load optimization.
- [ ] Heavy-load degradation remains graceful after any modest-load optimization.
- [ ] New instrumentation does not add meaningful hot-path work.
- [ ] Any instructive failed optimization is recorded in Historical Bugs/guardrails when it could plausibly be repeated.

## 8. Reopen gate — performance is symptom-driven

The accepted performance/freshness golden is the regression reference, not an invitation to reopen generic headroom work. Future optimization requires a reproduced, mechanism-specific symptom and the evidence/acceptance gates above; normal Qt render-phase activity alone does not establish a product defect.

Reopen performance work only when normal use, a directly observed run, a soak, or a new feature exposes a **persistent, growing or otherwise traceable defect**, or when evidence reveals clearly duplicated/useless work with a bounded owner. Preserve that failing condition first. Do not schedule synthetic soak/probe campaigns merely to search for the next percentile. If a real defect is reproduced, use existing diagnostics before adding instrumentation, then add only the smallest missing measurement needed to localize it.

Stable CPU/GPU/cache/thread/handle numbers and small distributed driver/GL costs remain non-targets unless the failing evidence shows avoidable work or growth. Any reopened work still owes the full freshness/reactivity/latency-tail acceptance contract above.


## Instrumentation/tool ownership

- Built-in PERF/usage/QML instrumentation is the primary runtime evidence plane when a real issue warrants diagnostics.
- The corrected ABC harness/driver and `--viz-switch-telemetry` are retained as explicit opt-in tools; boundary lifecycle telemetry allocates only when admitted.
- Deep frame/clip/Qt-phase/Bubble timing is retained behind explicit `--frame-trace`. It must remain zero-work in ordinary runtime and bounded on disk; do not delete useful sidecar markers merely because a specific investigation closes.
- Generic offline archaeology parsers are not performance authority merely because they can summarize the same numbers.
- Keep an external parser only for a narrow demonstrated cross-event question that the runtime does not already summarize; `image_change_perf_parser.py` is the current example.
- `perf_measure.py` is retained because it observes the process tree independently/out of process; its CPU/RSS/thread/handle results remain context, never Visualizer freshness proof.
- Production must never import/execute operator analysis tools (`R-72`).
- Tool output cannot authorize any change forbidden by the reactivity/freshness/latency-tail checklist above.

The operator-authorized Bubble equal-area response correction is documented in `Docs/Reference/Visualizer_Reference.md` and protected by BTF/R-69. It supersedes height-only product mapping; it does not authorize viewport-dependent performance caps, DSP attenuation, temporal smoothing changes or compression of already projected Ghost/history.

### Refresh families versus whole-display image transition admission (R161–R163)

`core/threading/refresh_transition_gate.py` is a **generation-scoped admission
arbiter**, not a global scheduler, new timer, worker pool or presentation owner.
FEEDS, Gmail's live fetch and Reddit's provider fetch participate in R163.
Each keeps its own dormancy, source cadence, cache freshness, retries, manual
cooldowns, source generations and cancellation. This gate holds one refresh
claim across participating sources **through GUI publication**; completed
background work alone does not release it. A waiting transition reserves the
next batch before new refresh admission; after *all* displays complete, wake
one deferred source in arrival order, not all at once. On a stale/dormant wake,
advance to the next source event-driven; repeated intents for one source
coalesce latest-wins. A delayed manual Reddit request must not be overwritten
by an automatic due event. Stop, retirement, submission failures and cancellation
must release active claims or remove deferred intents without reviving dormant
sources. Never silence slow-callback diagnostics to hide contention.

Scope is deliberate: startup cache bootstrap outside FEEDS, Steam, Weather,
and other services are **not** certified participants. Before adding any,
prove worker completion, GUI delivery, cancellation and generation retirement,
including the case where a worker completion cannot reach the GUI dispatcher.
Do not fence unrelated cache persistence, audio DSP, QML painting or passive
sampling. Do not add polling, speculative work or a second cache/cadence owner.
