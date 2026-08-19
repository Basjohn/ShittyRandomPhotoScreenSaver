# Current Plan — P2 Stabilized Worker+Push Reference and Slide-First Qt Quick Architecture Benchmark

Last updated: 2026-08-20 00:30 SAST

## Current exact source checkpoint

Current pushed HEAD reviewed for this plan:

```text
82a14b31d4cc71e47d0112479af0ce16596325c1
4.7.2 - Partial Benchmark
```

Relevant recent architecture checkpoints:

```text
690a27e0c6025937161426374ddf2c8ef407b8aa
    worker+push steady presentation restored;
    pull-at-paint production seam removed.

39279b2e90a2c91ae30a8168127fb29729969c90
    playback-state freshness epoch introduced.

3784e91bc40e8d7c95d31d0d96914f3c5443c0e7
    rejected pull-at-paint architecture preserved as history.

8ac2421e2bc0a7153942fc33eb9f348b505cde9d
    pre-pull worker+push installed reference.

42033c84eabbdf25ccd34bb0e83f9e553f2f8f11
    named rollback / fidelity reference.

15099d389e5091942a0ce3d6e6311d33b6043d3d
    historical directness reference only; no retained exact raw benchmark.
```

Documentation-only commits do not create a new behavioral checkpoint.

---

# 0. Executive state

The current source is now a credible stabilization/reference architecture.

That statement is based on exact source audit plus two new installed runs at the same HEAD.

The current production shape is:

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

The rejected pull-at-paint machinery is not left half-alive in production.

The current reference therefore retains:
- dedicated logical runtime;
- generation-zero and lifecycle fencing;
- one physical accelerated surface per display;
- QRhiWidget main compositor;
- K fire-and-forget transport command execution;
- paused Spectrum visible-state contract;
- no FIFO/catch-up;
- no visualizer-owned second native presentation surface.

The next work has three bounded goals:

1. close the remaining playback-state confirmation race;
2. finish a safe, production-shaped current-vs-Qt-Quick benchmark;
3. use that benchmark to decide whether runtime physical presentation should migrate to standalone QQuickWindow rendering.

Do not spend a long optimization campaign polishing worker+push before the architecture benchmark exists.

---

# 1. Stabilization audit — worker+push is actually restored

Direct source comparison of the worker+push restoration against `8ac2421e...` established that the pull-era production machinery was removed rather than layered around.

Removed pull-owned production concepts include:
- compositor logical-source registration;
- compositor-side `present_revision` polling;
- `_pull_delivery_active`;
- pull force-window state;
- pull-at-paint application of newest logical state;
- pull-only widget helpers;
- pull-specific tests that described the rejected ownership.

Restored delivery contract:

```text
logical publication
    ->
request_logical_present(widget)
    ->
if no present is already pending:
    marshal one GUI callback
    ->
present_logical_frame clears pending
    ->
present_tick consumes freshest mailbox state
```

If the GUI stalls, newer logical states supersede the mailbox entry.

They do not build a FIFO.

The single-pending flag prevents logical cadence from creating an unbounded GUI callback backlog.

## 1.1 Pull-specific spawn defect status

The two new installed runs at current HEAD contain no visualizer interval in which the logical runtime is active while the physical overlay remains stranded at `paint=0`.

This is consistent with the source ownership: each publication actively requests presentation again.

Treat the pull lost-wakeup / sporadic-spawn defect as:

```text
REMOVED BY ARCHITECTURE RESTORATION
```

but retain cold-start and Settings-recreate spawn checks as permanent gates.

---

# 2. New installed reference evidence at `82a14b31...`

## 2.1 Light-load installed run

Raw pack:

```text
6ef8b47b-bc3a-4921-ac16-22449f8f08ba.zip
SHA-256:
fbaaa67d84afee4855330d7026a20dd8b4f4130be44a83469eb20f8f73f45f08
```

Self-identifies:

```text
[SOURCE_HEAD] 82a14b31d4cc71e47d0112479af0ce16596325c1
```

Approximate run interval:

```text
2026-08-20 00:15:54 -> 00:20
```

### Physical delivery

Across 14 completed transitions:

```text
165 Hz display:
median completed FPS        ~150.05
range                       126.8 .. 158.4
median request acceptance   ~93.26%

60 Hz display:
median completed FPS        ~58.35
median request acceptance   ~97.73%
```

### Logical runtime

```text
steps=22042
skipped_deadlines=8
slow_steps=0
failures=0
```

The dedicated logical clock is extremely healthy.

### Environment

Primed system CPU median:

```text
~8.7%
```

### Operator acceptance

Direct installed observation:

- light-load behavior is materially better than initially credited;
- Pause/Play hitches are almost completely absent;
- visualizer spawn is reliable;
- paused Spectrum jumps/teleports to its visible resting-bar state rather than visibly shrinking/falling into it.

The Spectrum transition quirk is a lower-priority fidelity issue unless a cheap fix exists. Do not trade system cadence for a more elaborate paused-entry animation.

## 2.2 Heavy-load installed run

Raw pack:

```text
8f897d84-bd04-4685-8093-611e9815ffef.zip
SHA-256:
c09a04cda8431a3704217df6f8b40bd93595946e17db57c751340f4da1d3cadb
```

Self-identifies the same HEAD:

```text
82a14b31d4cc71e47d0112479af0ce16596325c1
```

Approximate run interval:

```text
2026-08-20 00:03:08 -> 00:05
```

### Physical delivery

Six completed high-load Blockspin windows:

```text
165 Hz display:
median completed FPS       ~105.8
range                       97.3 .. 130.0
median request acceptance  ~72.38%

60 Hz display:
median completed FPS       ~52.8
```

### Logical runtime

```text
steps=14119
skipped_deadlines=36
slow_steps=4
failures=0
```

The logical runtime stays fundamentally in its authored cadence class while physical delivery collapses.

### Environment

Primed system CPU median:

```text
~42.9%
```

### Frame-gap class

From the canonical performance log:

```text
FRAME_GAP_OWNER events  ~270
median gap              ~52.3 ms
p95                     ~129.2 ms
>=100 ms                30
max                     ~191.4 ms
```

The exact count depends on which duplicated diagnostic stream is aggregated; use the canonical perf log consistently for architecture comparisons.

## 2.3 Current interpretation

This pair is highly informative:

```text
light load:
current worker+push ~= historical desired high-refresh average class

heavy load:
physical presentation still collapses

both:
logical runtime remains healthy
pull-specific spawn failure is absent
```

Therefore the next architecture problem is no longer:

```text
"How do we get decent average FPS at all?"
```

It is:

```text
"How do we preserve smooth physical cadence and tail latency,
especially under contention, without regressing the now-good light-load state?"
```

This makes physical-presentation ownership an even cleaner migration target.

---

# 3. Slide becomes the PRIMARY architecture discriminator

Do not use Blockspin as the first Qt Quick migration workload.

Keep Blockspin as the secondary stress/regression case.

Use the production `GLCompositorSlideTransition` first.

## 3.1 Why Slide is superior for Stage 1

Slide is architecturally simple:
- timing + easing + four image positions;
- one shared compositor;
- no bespoke 3D mesh/state machine needed;
- continuous linear positional motion makes cadence holes very visible.

Most importantly, the CURRENT LIGHT-LOAD RUN already reproduces the defect while headline FPS looks excellent.

### First light-load Slide — 165 Hz display

```text
avg_fps                     154.4
request_acceptance_pct      95.06%
dt_p50                       6.07 ms
dt_p95                      10.83 ms
dt_p99                      16.42 ms
dt_max                      44.73 ms
dt_over_33_ms                2

paint_p95                    3.36 ms
paint_max                    6.48 ms

GPU average                  ~0.30 ms
GPU max                      ~3.73 ms
```

### Second light-load Slide — 165 Hz display

```text
avg_fps                     150.2
request_acceptance_pct      93.90%
dt_p95                      12.39 ms
dt_p99                      20.62 ms
dt_max                      43.22 ms
dt_over_33_ms                1

paint_p95                    3.47 ms
paint_max                   14.05 ms
```

### Simultaneous 60 Hz display

The same two Slide runs reached approximately:

```text
59.0 FPS, max gap 65.65 ms
58.8 FPS, max gap 59.72 ms
```

The operator reports the linear motion visibly stutters at roughly two points in most Slide runs even when average FPS is high.

That is exactly what the benchmark needs:

```text
a simple, cheap renderer
+
good average FPS
+
repeatable visible cadence failure
```

If Qt Quick materially reduces those ~43–45 ms 165 Hz holes while rendering the same Slide, that is much stronger evidence for a presentation-ownership win than comparing a complicated Blockspin port.

## 3.2 Additional heavy Slide observation

The operator also reports that a short heavy-load Slide run, particularly the portion after Settings, reproduces severe visible stutter.

At the time this document was generated, that additional raw pack had not surfaced in the conversation file inventory, so no numeric claims are invented for it.

Preserve the operator observation and append the raw metrics later when the pack becomes accessible.

---

# 4. Playback state freshness — close the remaining race before architecture comparison

Current `39279b2e...` playback epoch work solves one real race:

```text
refresh starts before transport command
    ->
command advances playback epoch
    ->
old result arrives from previous epoch
    ->
old playback state is rejected/pinned
```

That is good and must remain.

However current source still has a second race.

## 4.1 Remaining hole

Example:

```text
state = PLAYING

user/OS Pause accepted
    ->
K submits pause asynchronously
    ->
MediaWidget optimistically publishes PAUSED
    ->
playback epoch advances to N+1

before backend has actually changed:
    ->
a NEW poll begins at epoch N+1
    ->
GSMTC still returns PLAYING
```

Current `_reconcile_refresh_playback_epoch()` treats a same-epoch result as immediately authoritative.

So the state can still become:

```text
PAUSED (optimistic)
    ->
PLAYING (same-epoch poll, but backend has not caught up)
    ->
PAUSED (later real backend state)
```

That is a real source-level hole even though the current light-load installed run is already much better perceptually.

## 4.2 Required correction: expected state awaiting confirmation

Do not replace the epoch model.

Extend it with a bounded expected-state confirmation contract.

Suggested conceptual state:

```text
_pending_state_override
_pending_state_epoch
_pending_state_confirm_deadline_monotonic
```

Exact names may differ.

On accepted optimistic edge:

```text
playback_epoch += 1
expected_state = optimistic PAUSED/PLAYING
expected_epoch = playback_epoch
confirmation_deadline = now + bounded command-confirmation window
invalidate pre-command GSMTC cache
```

### Reconciliation rules

For an incoming refresh:

#### A. Older epoch

```text
refresh_epoch < current playback_epoch
```

Playback state cannot reverse current expected state.

Existing metadata/artwork may still flow where safe.

#### B. Current epoch + matches expected state

```text
info.state == expected_state
```

This is confirmation.

Accept it and clear the expected-state confirmation ownership.

#### C. Current epoch + contradicts expected state before confirmation deadline

This may simply be post-command/pre-backend reality.

Do NOT reverse the optimistic state yet.

Pin only playback state to the expected state.

Metadata/artwork may still flow.

#### D. Confirmation deadline expired

Do not lie forever if the command failed.

Clear expected-state ownership and allow the latest current-epoch authoritative state through.

The deadline is a bounded command-confirmation expiry, NOT a presentation debounce.

The optimistic UI remains immediate.

### Existing 300 ms timer

The existing ~300 ms timer may remain as a point at which a fresh query is requested.

It must NOT blindly clear expected-state ownership before the result can confirm it.

Prefer:

```text
300ms timer:
    request fresh state
    keep expected-state ownership

confirmation:
    clear expected state

bounded expiry:
    allow contradictory authoritative state
```

Do not add a second recurring timer if a monotonic deadline checked by reconciliation is sufficient.

Choose the bounded confirmation window based on the controller's real command timeout/behavior, not aesthetic preference.

Current transport command coroutine is already internally bounded around the ~2 s class; the confirmation window should be coherent with that rather than an arbitrary 700 ms wobble delay.

## 4.3 Tests required

Extend `tests/test_p2_playback_epoch.py`.

Must prove:

1. stale pre-command PLAYING cannot reverse optimistic PAUSED;
2. stale pre-command PAUSED cannot reverse optimistic PLAYING;
3. **same-epoch post-command/pre-backend PLAYING cannot reverse pending PAUSED**;
4. reverse-direction equivalent;
5. matching expected state confirms and clears expectation;
6. after bounded confirmation expiry, a contradictory current-epoch authoritative result may reverse;
7. stale results still preserve safe metadata/artwork fields;
8. no arbitrary recurring/debounce state owner is introduced;
9. a single accepted transport edge yields one visualizer/listener playback edge unless:
   - expected state later expires because command failed; or
   - a genuinely authoritative later state changes playback.

This correction is surgical but lives in a large, actively changing `MediaWidget`.

Make a narrow source diff plus tests.

Do not replace unrelated media-widget code.

---

# 5. Benchmark safety — current `--heavy` implementation must NOT be used

Current:

```text
tools/qtquick_presentation_spike.py
```

has two stress characteristics that are not appropriate for the canonical benchmark.

## 5.1 `--heavy N` is real same-process synthetic load

It starts N Python daemon threads executing a busy arithmetic loop.

That:
- consumes real CPU;
- creates aggressive GIL contention;
- specifically interferes with Python render-thread callbacks;
- does not reproduce the operator's ordinary external/system load;
- can distort the architecture comparison toward "Python threads fight Python threads."

Do not run it as the architecture load test.

Delete the built-in CPU-burn behavior from the canonical benchmark path.

No benchmark tool should silently or casually generate system stress.

## 5.2 Normal spike is also currently an unbounded throughput probe

Current Quick spike does:

```text
afterFrameEnd
    ->
window.update()
```

with swap interval 0.

That asks for another frame immediately and therefore runs as fast as the system will allow.

This is useful only as an explicitly requested throughput/thread-ownership probe.

It is NOT the canonical 165/60 product benchmark.

### Required safe default

Canonical benchmark must default to:

```text
display 0 target: 165 Hz
display 1 target: 60 Hz
```

or the actual selected display refresh rates.

No synthetic CPU burner.

No unbounded frame loop.

If an unbounded renderer-throughput probe is retained at all, it must require an explicit name such as:

```text
--throughput-probe
```

and clearly log that it is intentionally unbounded.

The ordinary command must be safe/paced.

## 5.3 External-load comparison

The benchmark does not create heavy load.

The operator supplies a known real-world heavy environment separately.

The benchmark should only LABEL and OBSERVE it.

For example:

```text
--load-label light
--load-label external-heavy
```

and record actual observed:
- system CPU;
- process CPU;
- GPU busy;
- memory.

If `psutil` or existing SRPSS telemetry is available, sample these passively.

Do not change workload quality automatically based on load.

---

# 6. Canonical architecture benchmark

Build one common workload definition so current worker+push and Qt Quick are compared against the same timeline.

Do not compare:
- production Slide on current architecture
against
- animated clear colour on Quick.

That proves nothing about product architecture.

## 6.1 Canonical on-screen sequence

Use the real two-display topology where available.

### Display 0

```text
165 Hz target
production-equivalent Slide transition
no visualizer
```

### Display 1

```text
60 Hz target
same Slide transition
visualizer layer active
```

This mirrors the current installed topology closely.

### Timeline

Recommended deterministic run:

```text
T = 0
    windows exist but are not visibly exposed with blank/default content
    initial base image/resources are ready
    first intentional frame becomes visible
    record first-frame/startup event

T = 1s
    start Slide on both displays
    fixed direction, e.g. LEFT
    production duration: 5 seconds
    production easing semantics

T = 1s
    start visualizer logical runtime / synthetic source on display 1
    Bubble is the primary temporal canary

T = 1s -> 6s
    deterministic simulated audio drives visualizer while Slide is running

T = 6s -> 11s
    keep deterministic visualizer running after Slide settles

T = 11s
    simulated playback PAUSE
    record exact logical and physical edge timestamps

T = 11s -> 13s
    hold paused state

T = 13s
    simulated PLAY/RESUME

T = 13s -> 15s
    continue deterministic visualizer

T = 15s
    finish and report
```

The exact timeline can be adjusted slightly if production ownership requires it.

The important property is that every candidate runs the SAME sequence.

## 6.2 Synthetic audio

Use deterministic generated visualizer input.

Do not depend on:
- Spotify;
- GSMTC;
- WASAPI;
- network;
- operator key timing.

It must produce repeatable:
- ordinary continuous energy;
- several transients;
- enough movement for Bubble to expose temporal holes.

Prefer using the real logical visualizer runtime and real render-state generation with a fake/synthetic audio source rather than hand-manufacturing final GPU vertices.

The benchmark is meant to include real visualizer architecture without real media-device nondeterminism.

## 6.3 Primary mode

Use Bubble first.

Reason:
- continuous positional motion;
- BTF is already a durable temporal canary;
- it exposes cadence gaps immediately.

Use Spectrum as a secondary correctness/idle-state case after the architecture comparison works.

The current Spectrum "teleport to visible resting bars" is not a reason to complicate Stage 1.

---

# 7. Benchmark measurement — average FPS is not enough

The current Slide evidence proves this.

A run at:

```text
154.4 average FPS
```

still contains:

```text
44.73 ms
```

physical gaps that are plainly visible in linear motion.

The architecture benchmark therefore makes tail latency a first-class result.

## 7.1 Per-display physical metrics

Record:

```text
requested presentation opportunities
accepted presentation requests
completed physical frames
completed FPS

dt p50
dt p90
dt p95
dt p99
dt max

count >= 12 ms
count >= 16 ms
count >= 25 ms
count >= 33 ms
count >= 50 ms
count >= 100 ms

paint p50/p95/p99/max
request age p50/p95/p99/max
```

For each large gap, retain:
- timestamp;
- display;
- benchmark phase;
- transition state;
- visualizer state;
- nearest logical publication/physical pull/present event.

## 7.2 Logical metrics

Record:
- logical target cadence;
- steps;
- skipped deadlines;
- slow steps;
- failures;
- longest logical holes;
- synthetic source publication cadence.

## 7.3 Cross-boundary freshness

Record a semantically useful age:

```text
logical state publication
    ->
physical render consumes newest state
```

p50/p95/p99/max.

Do not treat old push-era `state_to_paint` nomenclature as meaningful if the candidate architecture changes where state is applied.

## 7.4 Resource/context metrics

Passively record:
- system CPU;
- process CPU;
- GPU busy;
- memory;
- GUI callback count;
- Quick render thread IDs;
- render-loop selection.

No benchmark success is inferred solely from lower callback count.

---

# 8. Offscreen and on-screen modes have different jobs

## 8.1 Offscreen/deterministic mode

Use for:
- shader/image correctness;
- deterministic replay;
- state sequence;
- generation/lifecycle;
- first-frame content validity;
- bounded framebuffer/image assertions.

Offscreen is desirable and should exist where practical.

But it cannot prove:
- DWM presentation;
- swapchain behavior;
- actual mixed-refresh windows;
- on-screen startup flash;
- real present stalls.

## 8.2 On-screen mode

Required for the architecture decision.

Keep it:
- short;
- deterministic;
- target-paced;
- automatically ending.

The user accepts an on-screen benchmark when it is necessary to measure the real problem.

---

# 9. Qt Quick Stage 0 currently landed

Current partial tool is useful as a primitive proof:

```text
tools/qtquick_presentation_spike.py
```

It already demonstrates:
- standalone QQuickWindow topology;
- no QQuickWidget;
- OpenGL backend;
- explicit Qt scene-graph logging;
- render-thread ID capture;
- `beforeRendering` native-GL integration;
- basic vs threaded comparison possibility.

Preserve that work.

But its current animated-clear workload is not a product architecture benchmark.

Do not draw architecture conclusions from its FPS.

---

# 10. Qt Quick Stage 1 — Slide-first scheduling proof

Finish the benchmark with Slide BEFORE porting Blockspin.

## 10.1 Existing renderer reuse

Do not port all SRPSS shaders.

Use the existing OpenGL renderer concepts/code wherever technically safe.

For Slide this should be significantly easier than Blockspin:
- two textures/images;
- position interpolation;
- production-equivalent easing/progress;
- same output geometry.

The architecture question is:

```text
does standalone QQuickWindow threaded physical presentation
remove/reduce the characteristic Slide cadence holes
and improve load resilience?
```

## 10.2 Valid Quick topology

Required:

```text
QQuickWindow display 0
QQuickWindow display 1
```

standalone top-level windows.

Not:
- QQuickWidget;
- QWidget embedding for the performance proof;
- second transparent native accelerated overlay window.

Prove through Qt logs and captured thread IDs that:
- threaded scene-graph loop is active;
- render thread is distinct from GUI thread.

If the loop falls back to basic/GUI-thread rendering, mark that run INVALID for the architecture comparison.

## 10.3 Candidate renderer remains deliberately open

Do not pre-decide all future rendering around one Quick primitive.

Candidates remain:

### A. Direct/native or QSGRenderNode

Likely attractive for:
- full-screen base image;
- Slide;
- transitions;
- inline full-display compositor work.

Potential benefit:
no mandatory extra full-screen offscreen texture pass.

### B. QQuickRhiItem

Likely attractive for:
- contained custom GPU regions;
- visualizer;
- clean item/renderer synchronization;
- compositable GPU texture ownership.

Potential cost:
offscreen render target/pass.

### C. Hybrid

Explicitly allowed:

```text
QQuickWindow
    ->
direct/QSGRenderNode full-screen compositor
    +
QQuickRhiItem visualizer or other contained GPU item
    +
normal Quick scene items as appropriate
```

This still obeys:

```text
ONE physical presentation surface per display
```

Choose after measurement.

Do not reject QQuickRhiItem because direct rendering is initially simpler.

Do not force QQuickRhiItem because its abstraction is neater.

---

# 11. Startup flash/flicker remains a hard migration gate

Current SRPSS handles screensaver startup well.

Quick is not allowed to regress it.

Reject:
- white/default window flash;
- black blank frame;
- uninitialized root background;
- old/new texture pop;
- visualizer card flash;
- one display visibly exposing a placeholder significantly before the other.

Required conceptual contract:

```text
prepare initial intentional frame/resources
    ->
only then expose runtime window visibly
```

The benchmark must include:
- cold startup;
- first visible frame;
- timestamped first paint;
- human eyes-on flash/flicker acceptance.

An offscreen correctness test is insufficient for this gate.

Settings/recreate and topology/lifecycle remain later migration gates too.

---

# 12. Stage 2 — Blockspin is the secondary stress case

Only after Slide produces a meaningful current-vs-Quick comparison:

Add Blockspin.

Why:
- it exercises more complex 3D shader/state/resource work;
- it is a valuable secondary regression/stress workload;
- it should not be the initial migration tax.

The desired sequence is:

```text
Slide:
    prove/refute presentation architecture cheaply

then Blockspin:
    prove the result survives a complex transition
```

Do not make Stage 1 wait for every transition to be ported.

---

# 13. Current-vs-Quick decision criteria

Current worker+push is now a stronger reference than it looked yesterday.

A Quick migration must earn its complexity.

## 13.1 Light-load bar

Current Slide already averages about:

```text
150–154 FPS on 165 Hz
```

Therefore Quick does not win merely by reporting a higher headline FPS.

It should:
- preserve comparable average physical delivery;
- materially reduce the characteristic ~43–45 ms Slide holes;
- reduce >=25/33 ms gap frequency;
- preserve 60 Hz visualizer cadence;
- preserve visual fidelity;
- avoid startup flash/flicker.

A run at 149 FPS with dramatically cleaner tails can be better than 154 FPS with repeated visible 44 ms holes.

Perceptual continuity matters.

## 13.2 Heavy/external-load bar

Against the current heavy reference, Quick should materially improve:
- high-refresh FPS;
- request acceptance;
- p95/p99/max frame gaps;
- >=50/100 ms gap frequency;
- 60 Hz visualizer delivery;
- run-to-run variance.

It may not achieve perfect 165 FPS under heavy contention.

It must show a clear, repeatable architecture advantage.

## 13.3 Repetition

At least three identical runs per candidate in:
- light environment;
- operator-provided external-heavy environment.

Report:
- median;
- min;
- max;
- tails.

One lucky run does not decide architecture.

---

# 14. Migration scope if Quick wins

Do not move code that is unrelated to runtime presentation.

Remain QWidget/Python unless separately justified:
- Settings GUI;
- configuration/editor UX;
- persistence;
- providers;
- media/GSMTC integration;
- business logic;
- general orchestration.

Likely migration boundary:

```text
Python / QWidget application shell
        |
        +-- providers / media / settings / lifecycle
        |
        +-- dedicated logical runtimes
                    |
                    v
             immutable/latest render state
                    |
        +-----------+-----------+
        |                       |
  QQuickWindow 0           QQuickWindow 1
  render thread            render thread
        |                       |
   runtime physical presentation/composition
```

Runtime overlay PRESENTATION may need incremental migration because QWidget children cannot simply live as normal Quick children.

Their data/model logic does not need to migrate.

Do not solve overlay migration with new independently presented transparent GPU windows.

---

# 15. GIL discriminator

The first Quick renderer may still execute Python/PyOpenGL on Qt's render thread.

That means it still acquires the Python GIL.

Do not hide this.

The benchmark should capture thread identities and interpret results carefully.

If Quick:
- fixes the presentation tails despite Python callbacks -> strong architectural win.

If Quick:
- still exhibits Python scheduling holes while native/GPU work is cheap -> investigate Python/GIL as the next boundary.

Only then consider a small native/C++ physical renderer owner.

Do not start with C++.

---

# 16. Prohibitions

No:
- built-in CPU stress generator in the normal benchmark;
- current `--heavy` Python burner as architecture evidence;
- unbounded no-vsync benchmark as the default;
- broad worker revert;
- return to pull-at-paint;
- synchronous GSMTC transport wait;
- arbitrary playback debounce;
- Bubble cadence/fidelity cuts;
- source decimation;
- transition fidelity cuts;
- transition-specific optimization to hide a shared presentation defect;
- QQuickWidget as the Quick architecture proof;
- wholesale Settings/QML rewrite;
- startup flash accepted as migration debt;
- second accelerated native overlay surface;
- architecture decision based on average FPS alone.

---

# 17. Required execution order

## Phase A — finish correctness stabilization

1. Keep current worker+push architecture.
2. Extend playback freshness ownership with expected-state confirmation.
3. Extend deterministic playback tests.
4. Run focused playback tests.
5. Do one short installed verification:
   - mouse Pause/Play;
   - physical media key;
   - visualizer edge count;
   - no automatic PAUSE/PLAY flap.

Do not run a giant full suite as the first step.

## Phase B — make benchmark safe

6. Remove same-process CPU-burn `--heavy` from canonical Quick benchmark.
7. Remove unbounded update loop from default path.
8. If throughput mode is retained, make it explicit `--throughput-probe`.
9. Add passive `--load-label`.
10. Add actual 165/60 target pacing.

## Phase C — common Slide benchmark

11. Define shared deterministic images/timeline/synthetic audio.
12. Implement matching worker+push benchmark using current production Slide/compositor path.
13. Implement equivalent Slide path in standalone QQuickWindow benchmark.
14. Include Bubble visualizer on the 60 Hz side.
15. Record phase markers and tail metrics.
16. Add offscreen correctness mode where useful.
17. Preserve short on-screen real mixed-refresh mode.

## Phase D — establish reference

18. Run worker+push three times light.
19. Run worker+push three times with operator-provided external heavy load.
20. Save results as immutable evidence.

## Phase E — test Quick

21. Prove threaded Quick render loop.
22. Run identical three-pass light protocol.
23. Run identical external-heavy protocol.
24. Compare tails first, then average throughput/resource cost.
25. Human eyes-on Slide continuity and startup flash acceptance.

## Phase F — decision

26. If Quick materially wins:
    - compare direct/QSGRenderNode vs QQuickRhiItem vs hybrid only where useful;
    - add Blockspin secondary stress case;
    - perform runtime feature-parity migration audit.

27. If Quick does not materially win:
    - do not port Settings/runtime widgets into QML;
    - inspect Python/GIL/native presentation ownership;
    - consider a small native physical renderer candidate only if evidence earns it.

---

# 18. Evidence hierarchy

When conclusions conflict:

1. installed visible behavior;
2. repeated production-shaped benchmark;
3. installed structured telemetry;
4. exact current source;
5. deterministic regression tests;
6. docs;
7. commit messages;
8. agent prose.

Human perception remains authoritative for:
- Slide continuity;
- Bubble continuity;
- Pause/Play hitch;
- startup flash/flicker.

Metrics explain those observations.

They do not overrule them.

---

# 19. Immediate definition of success

The next milestone is NOT:

```text
"Qt Quick renders."
```

It is:

```text
current worker+push correctness stabilized
+
one safe reproducible Slide+visualizer benchmark exists
+
current reference recorded
+
Quick runs the same workload on a proven threaded QQuickWindow path
+
we can compare the characteristic microgaps and heavy-load collapse directly
```

Only then decide the physical presentation architecture.
