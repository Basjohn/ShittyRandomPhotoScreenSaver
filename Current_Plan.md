# Current Plan — P2 Stabilize Worker+Push, Then Prove Qt Quick Physical Presentation

Last updated: 2026-08-19 23:03 SAST

Current pushed source at orientation time:

```text
3784e91bc40e8d7c95d31d0d96914f3c5443c0e7
```

Commit message:

```text
4.7.2 - Even Worse Performance Under Load Or Just Uniquely Shit?
```

Historical "last releaseable without shame" source identified by operator:

```text
15099d389e5091942a0ce3d6e6311d33b6043d3d
```

No raw performance logs are currently retained for `15099d3`; do not manufacture numeric results for it.

---

# 0. Executive direction

P2 now has enough cumulative evidence to stop treating every current mechanism as equally uncertain.

## Retain

- one physical accelerated presentation surface per display as the product goal;
- dedicated `VisualizerLogicalRuntime`;
- one authoritative mode-general logical clock;
- latest-state semantics;
- valid generation zero;
- paused Spectrum renderer contract;
- K fire-and-forget/non-blocking transport command ownership;
- no FIFO/catch-up;
- no source smoothing or fidelity reduction.

## Remove from the active production design

The current pull-at-paint steady-state notification seam introduced in the working tree and now pushed in `3784e91...`.

It:
- removes callback-per-logical-publication volume;
- does not outperform worker+push under comparable heavy load;
- is highly variable at low load;
- worsens loaded dispatch/frame-gap tails;
- uniquely introduces lost-wakeup/sporadic visualizer spawn failures.

Do not preserve it merely because the ThreadManager UI-queued count is smaller.

## Restore as the stabilization/reference state

Dedicated logical worker + latest mailbox + coalescing GUI push presentation as used immediately before the pull conversion.

This is NOT declared the final architecture.

It is the strongest known production-shaped reference while the physical-presentation replacement is proven.

## Next major architecture candidate

Qt Quick **physical runtime presentation**, specifically:

```text
one top-level QQuickWindow per physical display
    ->
Qt Quick threaded scene-graph render loop
    ->
custom full-display renderer on the render thread
```

NOT:
- `QQuickWidget`;
- QWidget embedding of Quick as the performance proof;
- a rewrite of Settings/configuration UI into QML;
- a blind whole-product QML conversion.

The purpose is to move physical frame recording/render/present work away from the ordinary QWidget GUI paint/event-loop bottleneck while retaining the existing logical runtime and application models.

---

# 1. Why the dedicated worker stays

Loaded three-state evidence:

```text
                         GUI-tick baseline    worker+push    worker+pull

logical service              ~74.7 Hz          ~89.7 Hz        ~89.6 Hz
165 Hz median                 ~72.1 FPS        ~111.35 FPS      ~94.2 FPS
60 Hz median                  ~47.7 FPS         ~52.4 FPS       ~49.3 FPS
```

The worker:
- preserves authored logical cadence under load;
- improves physical delivery relative to GUI-driven baseline;
- does not own the pull-specific spawn regression.

Do not broadly revert it.

---

# 2. Why push returns without resurrecting K's old synchronous hitch

The old transport-command blocking defect and the push/pull presentation seam are independent.

K changed:

```text
GUI transport ingress
    -> submit command to IO
    -> return immediately
```

That remains.

Restoring worker+push does NOT restore:

```text
done.wait(2.5s)
```

on the GUI transport-command call.

Therefore the synchronous GSMTC command stall must not return merely because push presentation returns.

However:
- push does create more GUI presentation callbacks;
- old push installed runs still had visible Pause/Play hitching;
- playback-state flapping exists independently.

So push may still expose presentation hitches until the inherited playback-state ownership defect is fixed.

Treat push as the functional benchmark/reference, not as final P2 closure.

---

# 3. Fix inherited playback-state flapping on the reference architecture

The baseline, worker+push, and pull runs all show playback-state wobble.

Physical media-key duplicate ingress is already suppressed.

The remaining defect is state ownership/reconciliation.

Current shape:

```text
transport edge
    ->
optimistic MediaTrackInfo state emitted immediately
    ->
visualizer/listeners react
    ->
asynchronous GSMTC refresh result returns
    ->
normal display/state reconciliation
```

A stale pre-command refresh may contradict the optimistic post-command state.

Required contract:

```text
one accepted transport edge
    ->
new media-state generation / command epoch
    ->
optimistic state belongs to that epoch
    ->
refresh work captures the epoch it started under
    ->
pre-command/stale result cannot reverse the new epoch
    ->
first genuinely newer authoritative state may confirm/reverse
```

No blind 700 ms debounce.

No duplicate state owner in the visualizer.

Add deterministic delayed/stale-result negative controls.

Acceptance:
- mouse;
- APPCOMMAND/media key;
- all visualizer modes;
- exactly one logical pause/resume edge unless a genuinely newer external state reverses it.

---

# 4. Selectively remove pull-specific production machinery

Do not `git reset` or revert the entire `3784e91` commit.

Audit the exact production diff from `8ac2421e...` to `3784e91...`.

Selectively restore the worker+push steady presentation contract while retaining unrelated accepted fixes, including:
- K;
- L only where still harmless/useful;
- slow-tick `is_transition_active` diagnostic correction;
- source-head logging;
- evidence/docs;
- logical worker;
- generation/Spectrum fixes.

Expected pull-owned production surface includes:
- compositor logical-pull registration/revision sampling;
- pull-specific `present_revision` delivery semantics;
- pull-specific first/edge force-window machinery;
- `ensure_compositor_logical_pull` / `apply_latest_logical_present` style steady delivery;
- pull-specific tests.

Preserve the pull implementation as historical evidence before removing it.

After restoration, prove:
- visualizer cannot run for seconds with `paint=0`;
- startup reveal is deterministic;
- Settings recreation is deterministic;
- no pull liveness reason/force-window state remains in production.

---

# 5. Integrated benchmark is the gate for all future presentation architecture

Before optimizing push or migrating runtime presentation, build one reusable local benchmark.

## Workload

```text
Display A: simulated/real 165 Hz presentation target
    -> Blockspin transition

Display B: simulated/real 60 Hz presentation target
    -> active visualizer

Visualizer logical source:
    -> deterministic synthetic ~90 Hz bars/audio events

Qt:
    -> real QApplication/QGuiApplication event loop
    -> real production scheduler/compositor path
```

Run three identical repetitions in both:
- low-load environment;
- controlled heavy-load environment.

## Record

- high-refresh completed FPS;
- request acceptance;
- dt p50/p95/p99/max;
- frame-gap count and >=33 / >=50 / >=100 ms classes;
- 60 Hz completed FPS;
- logical cadence/skips;
- publish-to-physical age;
- media.paint;
- app/system CPU;
- GPU busy;
- GUI callback count;
- first-physical-frame latency;
- playback-state edges.

Do not use framebuffer readback every frame.

Use framebuffer capture only for bounded correctness/pixel assertions.

Absolute FPS is a same-machine architecture benchmark, not a generic CI portability gate.

---

# 6. Qt Quick is now an active architecture spike, not future speculation

The cumulative evidence has earned the question.

Across all three QWidget/QRhi states, the shared failure remains:

```text
deadline wake occurs reasonably near target
    ->
GUI dispatch/presentation is not serviced
    ->
physical opportunities are missed
    ->
GPU remains lightly loaded
```

The logical worker already moved simulation away from this bottleneck.

The next candidate is moving physical frame rendering/presentation away from ordinary QWidget GUI paint ownership.

## Spike topology

Use standalone top-level windows:

```text
QQuickWindow screen 0
QQuickWindow screen 1
```

Do not embed them in QWidget for the performance proof.

Do not use `QQuickWidget`.

The current QWidget Settings/editor/control application remains untouched.

## First renderer spike: preserve the existing shader work

Do NOT begin by porting every shader to QRhi/QSB.

First prove the scheduling lever with a minimal renderer:

- force/check Qt Quick `threaded` render loop;
- OpenGL graphics API;
- current no-vsync policy;
- one fullscreen custom render pass per window;
- reuse representative existing PyOpenGL code:
  - retained/base image;
  - Blockspin;
  - one representative visualizer mode, preferably Bubble plus Spectrum;
- feed immutable synthetic state;
- render via a Qt Quick render-thread integration point such as direct `beforeRendering`/`afterRendering` native OpenGL or an equivalent direct scene-graph render node;
- no runtime QWidget overlays in the spike.

Verify via Qt scene-graph logging that the render loop is actually threaded and identify render-thread ownership.

## Why not QQuickWidget

`QQuickWidget` disables Qt Quick's threaded render loop and adds an offscreen render pass/texture composition.

That defeats the exact architectural property being tested.

## Why not start with QQuickRhiItem

`QQuickRhiItem` is available and is a credible later integration tool, but it renders to an offscreen texture which is then composited.

For a full-display compositor spike, prefer a direct/inline render path with no extra full-screen offscreen pass.

If the Quick architecture wins and portable QRhi rendering becomes desirable, `QQuickRhiItem` / `QSGRenderNode` become valid migration tools.

---

# 7. Qt Quick no-vsync / mixed-refresh rules for the spike

Do not change the product's no-vsync policy merely to make Qt Quick look good.

Use:
- OpenGL graphics API initially;
- swap interval 0 / Qt Quick no-vsync equivalent;
- two on-screen QQuickWindows;
- current actual 60/165 topology.

Qt Quick's threaded loop supports explicit no-vsync and falls back to timer-based animation advancement when vsync cannot be used.

Because SRPSS owns its logical transition/visualizer time, do not depend on Qt Quick NumberAnimation timing as the product clock.

Also test/consider the elapsed-time Quick animation driver only where Qt's own scene-graph housekeeping needs it; SRPSS logical time remains authoritative.

---

# 8. Qt Quick spike decision bar

The spike is not accepted because a window renders.

It must beat worker+push repeatedly.

## Minimum migration signal

Under identical low-load and controlled-load benchmark passes:

- no sporadic first-frame/spawn failure;
- no new lifecycle/resource leak class;
- high-refresh delivery materially above worker+push;
- tail frame gaps materially lower;
- no regression in 60 Hz visualizer delivery;
- no dependence on lowered fidelity;
- low run-to-run variance.

A useful target for low load remains the historical ~150 FPS high-refresh class, with the long-term goal of approaching display rate.

Under controlled load, the spike must show a clear, repeatable improvement over worker+push rather than a one-run anomaly.

If Qt Quick does NOT improve delivery:
- do not port the rest of the app to Quick;
- inspect whether Python render-thread/GIL contention is the blocker;
- the next escalation becomes a small native/C++ physical renderer owner or other dedicated native presentation path.

---

# 9. If Qt Quick wins: actual migration destination

Do NOT rewrite all application logic.

Target architecture:

```text
QWidget/Python application shell
    -> Settings
    -> configuration
    -> providers
    -> media control
    -> lifecycle orchestration

Dedicated logical visualizer runtime
    -> immutable latest render state

One QQuickWindow per runtime display
    -> one scene graph / render thread per window
    -> full-display base image + transitions
    -> visualizer layer
    -> runtime overlay presentation
```

Existing runtime QWidget overlays cannot simply remain child widgets of QQuickWindow.

Migration options, in preferred order:
1. present existing retained/cached card content as scene-graph textures while keeping data/model logic;
2. incrementally port runtime overlay presentation to Qt Quick items;
3. only rewrite model/business logic if there is a separate reason.

Do not use extra independently dirtied transparent GL windows to avoid migrating overlay presentation; historical evidence already showed multiple accelerated presentation surfaces are harmful.

---

# 10. What `15099d3` teaches us

`15099d3` used:
- `QOpenGLWidget` main compositor;
- independent `SpotifyBarsGLOverlay(QOpenGLWidget)`;
- direct visualizer `set_state()` -> `self.update()` presentation;
- substantially less current-generation handoff/lifecycle/presentation machinery.

That likely explains part of its low-load responsiveness:
- short direct presentation path;
- fewer ownership fences/revision layers;
- fewer cross-thread handoffs;
- more resource residency;
- independent visualizer presentation.

But later controlled history disproves a simplistic return:
- single-display no-visualizer QOpenGLWidget compositor still produced severe native/Qt transition stalls;
- QRhi main-compositor migration later eliminated the severe >50 ms no-visualizer class in its acceptance run;
- a second QRhi visualizer presentation surface made delivery dramatically worse;
- one-surface-per-display was therefore a real architectural correction.

The goal is not to recover `15099d3`.

The goal is to recover its **directness and low coordination overhead** while retaining the correctness/resource/lifecycle improvements made since then.

---

# 11. Work order

1. Archive current pull architecture and evidence.
2. Selectively restore worker+push steady presentation.
3. Verify spawn/reveal determinism.
4. Fix media playback-state generation/freshness ownership.
5. Build reusable integrated low-load/heavy-load benchmark.
6. Establish worker+push reference numbers.
7. Build QQuickWindow threaded-render vertical slice using representative existing OpenGL shaders.
8. Benchmark it three times low-load and heavy-load.
9. Decide:
   - Quick wins -> begin bounded runtime-presentation migration;
   - Quick loses -> escalate physical renderer ownership, not QWidget micro-tuning.
10. Append immutable evidence before the next architecture change.

Do not spend weeks optimizing worker+push before running the Qt Quick vertical slice.
