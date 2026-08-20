# Current Plan — Worker+Push Harness Ready; Record the Physical Presentation Reference

Last updated: 2026-08-20 16:05 SAST

## Behavioral source checkpoint reviewed

The implementation behavior reviewed when this plan was realigned was:

```text
7d1befce2eab44c379a2919aca0e84b05fedc5a7
4.7.2 - Push Pre-Benchmark Baseline. Good Light, Terrible At Even Modest Load
```

This SHA is an **evidence/source review anchor, not a required current HEAD**.

`Current_Plan.md`, evidence records, guardrails, skills, or other documentation may be committed after this checkpoint. Documentation-only commits do not make the plan stale. The same files may instead exist as intentional uncommitted handoff changes; that does not make the working tree invalid or require cleanup.

Important architecture checkpoints:

```text
690a27e0c6025937161426374ddf2c8ef407b8aa
    worker+push steady presentation restored; pull-at-paint removed.

39279b2e90a2c91ae30a8168127fb29729969c90
    playback-state epoch/freshness ownership introduced.

3784e91bc40e8d7c95d31d0d96914f3c5443c0e7
    rejected pull-at-paint architecture preserved as history.

8ac2421e2bc0a7153942fc33eb9f348b505cde9d
    pre-pull worker+push installed reference.

42033c84eabbdf25ccd34bb0e83f9e553f2f8f11
    named rollback/fidelity reference.

15099d389e5091942a0ce3d6e6311d33b6043d3d
    historical directness reference only; do not roll back to it wholesale.
```

The long-soak evidence added with this plan is:

```text
Docs/Performance_Evidence/Acceptance-08_20-13_03-Diagnostic-Long-Soak.md
```

### Repository-state rule for agents

Before active work:

1. inspect the **actual current working tree** and current `HEAD`;
2. compare changes after the behavioral checkpoint only far enough to classify them;
3. if intervening or local changes are documentation/evidence/plan/skill only, continue normally;
4. if code changed after the checkpoint, inspect the current production owner/call chain and update only assumptions actually invalidated by those code changes;
5. preserve all unrelated local work.

Do **not** require `HEAD == 7d1befce...`. Do **not** require a clean tree merely because this plan/evidence pack is uncommitted. Do not reset, clean, checkout, stash, revert, or overwrite user work to manufacture checkpoint equality or cleanliness.

The current working tree is authoritative for what code exists now. The checkpoint is authoritative only for the provenance of the conclusions recorded here.

---

# 0. Executive state

The current worker+push architecture is the **stabilization/reference architecture** for the physical-presentation experiment.

It is not declared the final presentation architecture.

Current product shape:

```text
dedicated VisualizerLogicalRuntime (~90 Hz)
        ->
latest-state mailbox
        ->
coalesced one-pending GUI presentation request
        ->
GUI present_tick consumes freshest state
        ->
one QRhi/OpenGL physical compositor surface per display
```

The remaining primary performance problem is now narrowly stated:

```text
logical state is produced on time
+
local paint/GPU work is usually cheap
+
physical presentation still loses opportunities / develops visible tail gaps,
especially under contention and mixed-refresh production conditions
```

Therefore the active direction is:

```text
finish one bounded playback-state correctness prerequisite
        ->
build the common production-shaped benchmark
        ->
record worker+push reference runs
        ->
run the same core workload through standalone threaded QQuickWindow presentation
        ->
keep or reject Quick based on repeated physical-tail evidence
```

Do not start another broad optimization campaign on the current QWidget/QRhi path before this comparison exists.

---

# 1. Durable architecture — retain unless new installed evidence directly disproves it

## 1.1 Dedicated logical visualizer runtime

Keep `VisualizerLogicalRuntime`.

It is the one mode-general logical cadence owner.

Do not move visualizer logical time back onto:
- QWidget paint;
- GUI QTimer cadence;
- compositor paint;
- physical display cadence.

The renderer samples logical state. It is not the simulation clock.

The 2026-08-20 soak strengthens this materially: after an eight-hour dark residency and rapid topology recreation, generation 3 ran:

```text
steps=39502
skipped_deadlines=26
slow_steps=0
failures=0
joined=True
```

Bubble compute for that runtime finished with:

```text
offered=39502
submitted_tasks=39495
publish_ratio=1.000
worker_busy_deferrals=7
result_waiting_deferrals=0
submission_failures=0
stale_results=0
```

Do not broadly revert this worker architecture.

## 1.2 Latest-state + one-pending push delivery

Keep:

```text
logical publication
    -> latest-state mailbox
    -> at most one pending GUI present callback
    -> present consumes freshest state
```

No FIFO.
No catch-up burst.
No paint acknowledgement loop.
No callback-per-state backlog.

Pull-at-paint remains rejected as the steady production seam.

## 1.3 One physical accelerated presentation surface per display

Keep the product invariant:

```text
ONE independently presented accelerated surface per display
```

Do not restore:
- a separate native visualizer window;
- a transparent accelerated overlay window;
- per-widget GL presentation surfaces.

A future `QQuickWindow` may contain multiple scene items/render nodes/textures/passes while still satisfying this rule.

## 1.4 K / non-blocking transport

Keep fire-and-forget GSMTC transport command execution.

Do not restore a synchronous GUI wait for WinRT/GSMTC command completion.

## 1.5 Bubble Temporal Fidelity

Bubble remains the strongest temporal canary.

Do not:
- lower its authored cadence;
- tune its motion to mask missing physical frames;
- smooth away presentation holes;
- use average FPS as a substitute for visible continuity.

## 1.6 QRhi main compositor remains the current reference owner

The QOpenGLWidget -> QRhiWidget main-compositor migration fixed real ownership/lifecycle problems and improved the old no-visualizer compositor-gap class.

Do not rewrite that history merely because the final presentation architecture may change again.

The target remains:

```text
15099d3 directness
+
current correctness/resource discipline
+
a better physical presentation owner
```

---

# 2. New long-soak evidence — what changes and what does not

Raw-pack record:

```text
Docs/Performance_Evidence/Acceptance-08_20-13_03-Diagnostic-Long-Soak.md
```

## 2.1 Real soak interval

The relevant uninterrupted run is:

```text
2026-08-20 04:46:04 -> 13:03:36
8 h 17 m 32 s
```

The archive also contains older short sessions. Do not merge those into the soak.

For most of the soak Windows exposed a single 60 Hz topology while the physical displays were off.

## 2.2 Monitor wake / topology lifecycle is no longer an active work lane

Physical displays returned at approximately `12:55:56`.

Windows then produced several topology changes in rapid succession:

```text
12:55:57  runtime generation -> 1  reason=monitor_topology
12:56:11  runtime generation -> 2  reason=monitor_topology
12:56:14  runtime generation -> 3  reason=monitor_topology
```

The final topology settled as the real mixed-refresh pair:

```text
screen 0: detected 165 Hz, target 165 Hz
screen 1: detected 60 Hz,  target 60 Hz
```

Both displays reached intentional first-frame readiness and completed coordinated fades. The final generation then continued through real transitions/visualizer work until normal application exit.

Application exit advanced generation 4 and completed teardown.

Final shared-memory accounting:

```text
segments_created=80
segments_consumed=80
segments_live=0
segments_reclaimed_late=0
unlink_failures=0
```

### Decision

Treat monitor-off/wake/topology recreation as:

```text
WATCHLIST + PERMANENT MIGRATION/RELEASE GATE
```

not:

```text
ACTIVE PERFORMANCE/REPAIR PRIORITY
```

Do not spend current architecture time trying to improve a wake path that this soak exercised successfully.

If a future production build reproduces a wake failure, reopen it from fresh evidence.

## 2.3 Diagnostic Winlogon URL behavior is not a production regression

`SRPSS_Diagnostic.exe` deliberately bypasses the standard SCR secure-helper URL handoff and treats URL opening as an interactive direct-launch path.

That makes the observed Firefox/Winlogon failure expected for the diagnostic product shape.

Do not open a current Winlogon/browser repair lane from this diagnostic result.

Only reopen if the ordinary installed `.scr` reproduces the failure through its real Task-Scheduler/helper contract.

## 2.4 Long residency does not progressively degrade 60 Hz presentation

Retained PERF rotations cover approximately:

```text
06:39:30 -> 12:55:30
```

before wake.

There are 565 completed 60 Hz Slide paint windows in that retained period.

Hourly medians remain essentially flat:

```text
completed FPS              ~59.7 .. 59.8
request acceptance         ~99.67%
dt p95                     ~16.78 ms
median per-run max gap     ~35 .. 36 ms
paint p95                  ~5.7 ms
```

Trend over retained hours is effectively flat; runtime age does not make cadence progressively rot.

### Decision

Do not explain the current visible cadence defect as an hours-long degradation phenomenon.

The defect reappears when the production presentation topology/load becomes demanding, not merely because the process has been alive for hours.

## 2.5 Post-wake evidence strengthens the physical-presentation hypothesis

After the mixed-refresh topology settled, retained completed windows include both Slide and Blockspin.

Representative medians:

```text
165 Hz screen / Slide:
    completed FPS           ~155.1
    request acceptance      ~94.96%
    dt p95                  ~10.79 ms
    median max gap          ~40.4 ms
    worst observed max      101.3 ms
    paint p95               ~2.85 ms

165 Hz screen / Blockspin:
    completed FPS           ~156.0
    request acceptance      ~95.56%
    dt p95                  ~10.81 ms
    worst observed max      57.45 ms
    paint p95               ~3.0 ms

60 Hz screen / Slide + Bubble:
    completed FPS           ~58.8
    request acceptance      ~98.71%
    dt p95                  ~18.97 ms
    median max gap          ~66.23 ms
    worst observed max      102.37 ms

60 Hz screen / Blockspin + Bubble:
    completed FPS           ~59.4
    request acceptance      ~99.45%
    dt p95                  ~18.17 ms
    worst observed max      73.53 ms
```

Post-wake `FRAME_GAP_OWNER` population:

```text
screen 0 / 165 Hz: 63 gaps, median ~51.9 ms, p95 ~93.34 ms, max 101.3 ms
screen 1 / 60 Hz:  64 gaps, median ~55.94 ms, p95 ~86.79 ms, max 102.37 ms
```

Bubble overlay GPU samples remain roughly sub-millisecond to ~1 ms-class in ordinary 10 s windows while these physical gaps occur.

### Decision

This strengthens, rather than weakens, the current architecture question:

```text
can a different physical presentation owner preserve the same logical/render work
while materially reducing lost physical opportunities and long tail gaps?
```

Do not respond by individually optimizing Slide, Blockspin, or Bubble.

Slide is a cheap measurement instrument because its linear motion exposes the defect clearly. It is not being blamed as the cause.

## 2.6 Separate long-run resource-retention signal

After excluding the first ~15 minutes of startup/warmup, the dark single-display interval shows approximate linear slopes:

```text
main USS             +29.2 MB/hour
main private commit  +90.0 MB/hour
app handle count     +15/hour
```

At the same time:

```text
app threads            essentially flat (~78-79)
GL resources           essentially flat (10-11)
RM resources           ~29-33
tracked resources      bounded/no comparable monotonic explosion
dedicated VRAM         not monotonically rising
SHM live segments      returns to zero
```

This is a real **retention signal**, but this run is Full Telemetry Diagnostic and does not prove a production leak or its owner.

### Decision

Keep this separate from the presentation architecture work.

Required later A/B:

```text
ordinary/light-telemetry long soak
vs
Full Telemetry Diagnostic long soak
```

Only if the slope survives the lighter run should ownership hunting begin.

Do not make memory/handle retention a prerequisite for the Quick presentation benchmark.

---

# 3. One bounded correctness prerequisite before architecture comparison

Current source still contains a same-epoch playback confirmation race.

The landed epoch fence correctly prevents a refresh that began before a transport command from reversing the optimistic post-command state.

The remaining shape is:

```text
command accepted
    -> optimistic PAUSED/PLAYING
    -> playback epoch advances
    -> a NEW refresh begins in the new epoch before GSMTC backend catches up
    -> backend returns old state
    -> current source treats same-epoch state as immediately authoritative
```

Current `_apply_pending_state_override()` also clears the pending override after ~300 ms before requesting a refresh, so the expectation can disappear before a backend confirmation is actually observed.

## Required correction

Extend the existing epoch model with bounded expected-state confirmation ownership.

Conceptually:

```text
expected_playback_state
expected_epoch
confirmation_deadline_monotonic
```

Rules:

1. **older epoch** — cannot reverse current expected state;
2. **current epoch + matches expectation** — confirms and clears expectation;
3. **current epoch + contradicts expectation before deadline** — preserve expected playback state while allowing safe metadata/artwork to flow;
4. **deadline expires without confirmation** — release expectation and allow authoritative contradiction so a failed command cannot lie forever.

The deadline is command-confirmation ownership, not a presentation debounce.

Do not add another recurring state owner if reconciliation can check one monotonic deadline.

The existing 300 ms timer may request a fresh query, but it must not blindly erase expected-state ownership first.

## Gate

Extend `tests/test_p2_playback_epoch.py` to prove both directions, matching confirmation, pre-deadline contradiction rejection, expiry, metadata flow, and one accepted transport edge -> one listener/visualizer edge unless a later authoritative change is legitimate.

If this correction has already landed when this plan is read, verify source/tests and move on. Do not redesign it again.

Then do one short installed confirmation only if required by the current evidence workflow.

---

# 4. Benchmark is now the active architecture work

The benchmark must compare **physical presentation architecture**, not toy rendering throughput.

## 4.1 Safe benchmark defaults

Do not use same-process Python CPU burners as architecture evidence.

Do not use an unbounded `afterFrameEnd -> update()` loop as the normal benchmark.

Default benchmark behavior:
- short;
- deterministic;
- target-paced;
- automatically ending;
- no network/media-device dependency;
- passive load observation only.

If an unbounded throughput probe remains, gate it behind an explicit name such as:

```text
--throughput-probe
```

External load is operator-provided and labelled, for example:

```text
--load-label light
--load-label external-heavy
```

Record actual system/process CPU and GPU rather than assuming the label proves the load.

## 4.2 Core common workload — architecture discriminator

Use the same logical/render timeline for current worker+push and Quick.

Primary Stage-1 transition: **Slide**.

Reason:
- cheap/simple renderer;
- continuous linear motion;
- already reproduces visible long-tail holes while average FPS looks good;
- avoids paying the Blockspin porting tax before the presentation hypothesis is tested.

This does **not** mean Slide is believed to be the root cause.

Core mixed-refresh workload:

```text
screen 0 / 165 Hz:
    retained base image
    production-equivalent Slide
    no visualizer

screen 1 / 60 Hz:
    retained base image
    same Slide timeline
    Bubble visualizer
    deterministic synthetic audio/source
```

Recommended bounded sequence:

```text
startup intentional first frame
1s: Slide + Bubble begin
1-6s: Slide and Bubble coexist
6-11s: Bubble continues on settled image
11s: synthetic pause edge
11-13s: paused hold
13s: synthetic resume edge
13-15s: Bubble continues
15s: stop/report
```

No Spotify, GSMTC, WASAPI, network, or manual key timing in the core benchmark.

Use the real logical visualizer runtime and real render-state path with a deterministic source where practical.

## 4.3 Required production-population axis

The operator's installed A/B showed Bubble-active GPU load changed materially when Steam/weather runtime widgets were removed.

That does not prove those widgets cause the stutter.

It does prove runtime presentation population materially changes shared cost and must stop being an informal variable.

Record current worker+push reference runs in at least two populations:

### P0 — minimal architecture discriminator

```text
base + Slide + Bubble/synthetic source
only presentation needed for the common architecture comparison
```

### P1 — production-shaped runtime population

Use the ordinary enabled runtime overlay/card population with provider/network nondeterminism suppressed where possible through retained/cached/static state.

The purpose is to measure:
- GPU busy/frame cost;
- physical gap tails;
- request acceptance;
- whether shared composition load changes the failure class.

### Important Stage-1 limit

Do **not** migrate all runtime widgets to Quick before Quick proves the core scheduling/presentation hypothesis.

Therefore:
- P0 is the first strict current-vs-Quick common comparison;
- P1 is a required current-reference characterization;
- if Quick clearly wins P0, Stage 2 must prove the win survives equivalent production-presentation composition before product migration is accepted.

Equivalent Stage-2 presentation may use cached textures/representative Quick items/incremental overlay migration. Provider/model logic remains Python.

## 4.4 Secondary stress workload

After Slide yields a meaningful current-vs-Quick result, add Blockspin.

Blockspin is a stress/regression case, not the first migration tax.

No per-transition tuning campaign is allowed to replace the architecture comparison.

---

# 5. Metrics and evidence contract

Average FPS is insufficient.

For each display/candidate/population record at minimum:

```text
requested opportunities
accepted requests
completed physical frames
completed FPS

dt p50/p90/p95/p99/max
counts >= 12/16/25/33/50/100 ms

paint p50/p95/p99/max
request age p50/p95/p99/max
logical publication -> physical consume age p50/p95/p99/max

logical steps
skipped deadlines
slow steps
failures
longest logical holes

system CPU
process CPU
GPU busy/frame cost
memory/VRAM secondary
GUI callback count
Quick render-thread identity when applicable
```

Retain exact phase timestamps for:
- first intentional visible frame;
- Slide start/end;
- Bubble first logical frame;
- Bubble first physical frame/reveal;
- synthetic pause;
- synthetic resume.

For large physical gaps retain nearest logical/presentation ownership context.

Human eyes-on acceptance remains required for:
- Slide continuity;
- Bubble continuity;
- startup flash/flicker.

Metrics explain perception. They do not overrule it.

---

# 6. Establish the worker+push reference

Once the bounded playback correction and benchmark harness are ready:

Run the current architecture at least three times for each required environment:

```text
P0 minimal / light
P0 minimal / external-heavy
P1 production population / light
P1 production population / external-heavy
```

If external-heavy is not available for every iteration, do not manufacture load inside the benchmark. Record what was actually run.

The core P0 repeated runs are the strict architecture reference.

Save immutable evidence before deciding Quick.

Do not keep polishing worker+push indefinitely to make it beat the candidate before the candidate is measured.

---

# 7. Qt Quick Stage 1 — prove or reject physical presentation ownership

Use standalone top-level windows:

```text
QQuickWindow display 0
QQuickWindow display 1
```

Required:
- OpenGL backend initially where practical for representative renderer reuse;
- threaded Qt Quick scene-graph loop;
- render thread proven distinct from GUI thread through Qt logging/thread IDs;
- same P0 Slide/Bubble deterministic workload;
- same pacing and metrics as current reference.

Invalid architecture proof:
- `QQuickWidget`;
- QWidget-embedded Quick;
- basic/GUI-thread render-loop fallback presented as threaded Quick evidence;
- a second independently presented accelerated visualizer/overlay window;
- empty clear-colour/triangle FPS used as product proof.

The first question is only:

```text
does QQuickWindow/render-thread physical presentation materially improve
physical cadence tails and load resilience for the same core workload?
```

Do not port every shader or widget first.

## Renderer primitive remains open

If Quick wins enough to continue, compare only where measurement requires it:

```text
A: direct/native or QSGRenderNode for full-display compositor work
B: QQuickRhiItem for contained custom GPU regions such as visualizer
C: hybrid in one QQuickWindow
```

Do not choose by elegance.

---

# 8. Architecture decision bar

Current worker+push is already strong under light load.

Quick does not win because headline FPS is a few points higher.

A useful Quick win must be **repeatable** and should materially improve:
- p95/p99/max physical frame gaps;
- >=25/33/50/100 ms gap frequency;
- request acceptance under contention;
- high-refresh completed delivery;
- mixed-refresh Bubble continuity;
- run-to-run variance;
while preserving:
- logical cadence;
- visual fidelity;
- no startup flash;
- one physical accelerated surface per display.

A slightly lower average FPS with dramatically cleaner visible tails may be the better architecture.

At least three identical P0 runs per candidate in light conditions are required; use repeated external-heavy runs when the operator can provide the environment.

## If Quick wins P0

Then, in order:

1. prove equivalent production-presentation population does not erase the win;
2. add Blockspin secondary stress;
3. compare Quick rendering primitive shapes only if useful;
4. perform runtime overlay migration feasibility;
5. perform startup/no-flash, Settings/recreate, monitor topology, compiled-build, and long-soak gates.

## If Quick does not clearly win P0

Stop the broad Quick migration.

Do not port Settings/widgets into QML in hope that scale will magically fix it.

Inspect the next boundary:
- Python/GIL scheduling on render callbacks;
- native window/present ownership;
- small native/C++ physical renderer owner only if evidence earns it.

Do not begin with C++.

---

# 9. Later migration/release gates — not Stage-1 blockers

Any winning presenter must eventually prove:

## Visual/startup
- no white/default flash;
- no black blank frame;
- no uninitialized Quick root;
- intentional first frame before visible exposure;
- no visualizer/card flash;
- no ugly cross-display reveal skew.

## Lifecycle
- normal startup/shutdown;
- Settings/recreate;
- mixed-refresh 165/60;
- monitor topology recreation;
- display-off -> wake;
- clean generation retirement;
- compiled/frozen build.

Use the 2026-08-20 soak as a lifecycle quality bar: the current architecture survived three rapid topology-driven generation replacements after eight hours.

## Long-run resources

Repeat a long soak on the winning architecture.

Separately resolve whether the current memory/handle slope survives light telemetry.

A Quick candidate is not allowed to introduce a materially worse monotonic resource slope.

---

# 10. Explicitly out of the active lane

Do not spend current work on these unless fresh product evidence promotes them:

- monitor wake/topology lifecycle optimization;
- diagnostic-product Firefox/Winlogon URL escape;
- old dedicated FFT process resurrection;
- stale ProcessSupervisor/FFT ancestry cleanup as a performance experiment;
- long-run memory/handle retention ownership before the light-vs-Full-Telemetry A/B;
- Spectrum paused-entry cosmetic motion;
- broad provider/media/widget rewrites;
- wholesale QML/Settings conversion;
- per-transition optimization intended to hide a shared presentation defect.

The stale FFT/ProcessSupervisor ancestry is cleanup only. Current FFT/audio analysis stays on the bounded ThreadManager compute path unless contrary measurement appears.

---

# 11. Prohibitions

No:
- return to pull-at-paint;
- broad worker rollback;
- synchronous GSMTC wait;
- arbitrary playback debounce;
- FIFO/catch-up presentation queues;
- Bubble/source cadence reduction;
- visual fidelity cuts to hit FPS;
- QQuickWidget as the architecture proof;
- second accelerated native presentation surface;
- same-process CPU burner as canonical heavy-load evidence;
- unbounded throughput loop as normal benchmark;
- architecture decision from average FPS alone;
- destructive git operations that discard local work to obtain a convenient historical state.

Historical commits may be inspected in a separate worktree/read-only comparison. Do not destroy current work to read them.

---

# 12. Live execution checklist

- [ ] Complete the three-run worker+push P0/light reference set with an external PresentMon capture for each run.
  - [ ] Repeat with run IDs/output suffixes `02` and `03`; do not overwrite any JSON or CSV.
  - [ ] Return each JSON + PresentMon CSV, actual monitor/refresh topology, and a short visible-tail note for each display.
- [ ] Record worker+push P1/light references with the same capture procedure; use `--population P1` and matching `worker-p1-light-*` identities to characterize static production-card composition coupling.
- [ ] Repeat P0/P1 under genuinely operator-provided external-heavy load when available; label the actual environment and do not synthesize load in the harness.
- [ ] Finish the standalone threaded `QQuickWindow` P0 path using the same common workload identity and external physical evidence contract.
- [ ] Prove Quick render-loop/thread ownership through Qt evidence.
- [ ] Run at least three current-vs-Quick P0/light comparisons and repeated external-heavy comparisons when available; judge physical tails first.
- [ ] **Stop and decide architecture.**
- [ ] Only after a Quick win: production-presentation population, Blockspin, primitive comparison, parity/lifecycle/soak migration gates.

Do not let cleanup work, historical archaeology, wake monitoring, memory retention, or transition-specific tuning jump ahead of step 12.

---

# 13. Evidence hierarchy

When sources conflict:

1. installed visible behavior;
2. repeated production-shaped benchmark;
3. installed structured telemetry;
4. exact current source;
5. deterministic regression tests;
6. architecture/current-plan documents;
7. commit messages;
8. agent claims.

The immediate milestone is:

```text
bounded correctness prerequisite closed
+
same production-shaped P0 benchmark exists on worker+push and threaded QQuickWindow
+
reference runs are repeatable
+
physical tail gaps can be compared directly
+
architecture decision is made before scope expands
```
