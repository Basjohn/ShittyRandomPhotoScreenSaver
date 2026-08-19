# Current Plan

Last updated: 2026-08-19
Branch: `main`
Current source anchor: `fbac9ea8ca6abd1c8a085fb0d445fb9958c9d0da`
Named accepted rollback/fidelity baseline: **4.7.2 / `42033c84eabbdf25ccd34bb0e83f9e553f2f8f11`**
Current-head status: **UNACCEPTED — first installed run after the latest runtime changes regressed materially**

This file owns active unfinished work and execution order. Exact current source plus installed evidence
override completion messages. Phase reports/history are evidence only.

Do not reopen the single-surface QRhi migration, old Bubble-lane experiments, or already-closed
lifecycle defects without contradictory evidence.

---

## 1. Binding architecture / product contract

### 1.1 Presentation

One physical display owns one accelerated OpenGL QRhi compositor surface.

The visualizer is a compositor layer. It does not own another presented QWidget/QRhi/OpenGL surface.

The compositor owns physical presentation opportunities only.

Do not introduce:
- another visualizer presentation surface;
- another physical presentation clock;
- paint acknowledgement/backpressure;
- pending-until-paint admission;
- producer/display cadence division;
- repaint rescue/self-requeue loops;
- CPU/QPainter visualizer fallback;
- source/event decimation;
- FIFO/catch-up rendering.

### 1.2 Visualizer logical contract

One visualizer logical owner must integrate:
- source/audio state;
- authored dt;
- transients/events;
- smoothing;
- mode-owned simulation/history;
- current activation/generation;
- latest render state.

All five modes are peers:
- Bubble
- Spectrum
- Sine
- Oscilloscope
- DevCurve

Do not call a shared cadence/runtime failure a Bubble problem merely because Bubble exposes motion
holes clearly.

### 1.3 Fidelity

Preserve:
- lowest practical reaction latency;
- current mode personality;
- authored transient/event response;
- continuous smoothing when enabled;
- current shaders/card styling/glow/geometry;
- current one-fade presentation ownership;
- no state poisoning across mode/preset/generation changes.

A performance improvement may remove technical work. It may not remove authored work.

### 1.4 Efficiency

Prefer eliminating:
- duplicate cache/raster work;
- identical-value invalidation;
- unnecessary GUI callbacks;
- redundant presentation;
- repeated activation/configuration;
- unnecessary task/Future scaffolding when causally proven;
- visible post-reveal warmup that can legally happen while hidden.

Use source + existing evidence + production-shaped tests before new probes. Add instrumentation only
when it will choose between materially different remaining designs.

---

## 2. Evidence orientation — baseline remains 4.7.2, current head is not accepted

### 2.1 What the 4.7.2 baseline established

The installed `42033c84` run remains the rollback/perceptual authority.

It established:
- visualizer steady-state motion could be very good;
- all five modes were capable of roughly the intended high logical cadence;
- cross-display CUSTOM worked;
- visualizer Cancel resume worked;
- Gmail no longer stranded the runtime destruction barrier;
- 60-Hz delivery was effectively complete;
- 165-Hz BlockSpin could reach the upper-150/160-FPS class;
- renderer/GPU cost remained far smaller than the long service holes.

Representative accepted high-refresh BlockSpin evidence:

```text
16 complete 165-Hz windows:
median FPS                ~152.45
median useful acceptance  ~94.79%
median dt p95             ~12.10 ms
median dt p99             ~19.99 ms
median paint p95          ~2.87 ms
median request-age p95    ~4.38 ms

good low-load windows:
157.1 FPS
159.5 FPS
160.6 FPS
```

Representative 60-Hz evidence:

```text
median FPS                ~59.7
median useful acceptance  ~99.44%
median dt p95             ~21.1 ms
```

This is not a permanent ceiling. It is the current proof of what the architecture can already do.

### 2.2 Latest installed run against current head

The 04:34:35–04:37:06 run is the first installed evidence after the latest runtime changes.

Operator report:
- no visible improvement from the latest round;
- performance feels significantly worse;
- Media artwork/metadata still disappears on CUSTOM Cancel;
- visualizer modes briefly stutter when appearing;
- playback/idle edges still stutter;
- the previously good steady-state visualizer is no longer consistently smooth.

The logs agree that this run is materially worse.

#### 165-Hz BlockSpin

Five complete high-refresh windows:

```text
139.1 FPS   90.19% accepted
128.7 FPS   86.99%
100.7 FPS   81.62%
125.4 FPS   85.94%
100.3 FPS   75.77%
```

Median:

```text
FPS                     125.4    vs baseline 152.45
useful acceptance       85.94%   vs baseline 94.79%
dt p95                  18.37ms  vs baseline 12.10ms
dt p99                  33.17ms  vs baseline 19.99ms
paint p95                3.93ms  vs baseline 2.87ms
request age p95          6.98ms  vs baseline 4.38ms
```

The worst complete window reached `dt_max=174.36 ms`.

#### 60-Hz side

Five complete windows have approximately:

```text
58.0
56.0
53.0
56.5
50.4 FPS
```

Median:

```text
FPS                     56.0    vs baseline 59.7
useful acceptance       95.56%  vs baseline 99.44%
dt p95                  27.76ms vs baseline 21.1ms
paint p95                9.49ms vs baseline 6.69ms
```

#### CPU/GPU

Ignoring the first priming sample in the latest run:

```text
app CPU median          ~104.8%
GPU busy median         ~7.4%
```

The named baseline whole-run post-prime app CPU median was roughly `~73%`.

Do not claim a precise causal CPU regression from this one short run because host conditions differ.
However, host load cannot explain the complete result: the first high-refresh transition was already
only ~139 FPS while the system-CPU sampler still reported its zero/priming-class state, and app CPU
was already materially above the baseline class.

GPU remains light. This is still not a fixed GPU/render ceiling.

### 2.3 The latest runtime code changes are not yet proven to own the global regression

Between `42033c84` and current head, runtime changes are confined to:
- `widgets/base_overlay_widget.py`;
- `rendering/widget_manager.py`.

They:
1. avoid discarding a current painted-frame cache on no-op resize/DPR/screen events;
2. prepare a painted overlay frame before the overlay reveal request.

The latest `perf_widgets.log` contains **zero** `overlay.frame_shadow.regen` records, versus many in
the baseline. So those changes achieved their narrow local objective.

They do not obviously explain sustained transition/cadence loss minutes later.

Therefore:
- retain them provisionally;
- do not burn a round on an A/B probe campaign;
- do not call them accepted either;
- the next installed acceptance decides whether current head as a whole earns the new baseline;
- if they conflict with the corrections below or the next run remains regressed without another
  owner, rollback is permitted rather than defending them because tests pass.

---

## 3. ACTIVE — CUSTOM Cancel must preserve live Media content

Claude declined this correction because the broad Cancel replay produced no measured frame-shadow
regen. That conclusion is rejected by installed behavior.

### 3.1 Evidence

CUSTOM is preview-first for ordinary widgets:
- the live widget is hidden;
- `EditShellWidget` carries the preview geometry;
- ordinary drag/resize does not mutate the hidden live widget.

Yet Cancel still broadly reapplies persisted CUSTOM entries after the shells finish.

The latest run again shows Media being created with:

```text
payload={artwork_size=220,font_size=19}
```

and Cancel replaying the **same** payload through:

```text
replay_start
replay_after_payload
replay_after_update_position
replay_final
```

The operator again sees the live Media artwork/metadata disappear after Cancel.

Absence of `overlay.frame_shadow.regen` does not make this replay a semantic no-op. Media owns live
state beyond the painted frame:
- `_last_info`;
- `_artwork_pixmap`;
- applied/pending artwork identity;
- artwork generation;
- painter-owned metadata layout;
- scaled artwork/layout caches;
- retained media runtime state.

The generic replay path invokes Media size/config setters even when the authored value is unchanged.

### 3.2 Required contract

Cancel means:

```text
discard edit-shell preview
-> reveal/restore the unchanged live widget
-> resume explicitly suspended special runtimes
-> do not broadly replay persisted payloads into preview-only live widgets
```

Save remains distinct and may persist/rebuild according to its existing contract.

Audit whether any edit target genuinely mutates its live runtime during preview. Restore only those
specific owners.

Preserve:
- visualizer `suspend_for_edit()` / `resume_after_edit()`;
- recovery-placeholder behavior;
- original committed geometry;
- cross-display Save behavior;
- deferred-image ownership.

### 3.3 Required regression bar

Use a real populated `MediaWidget` with:
- non-empty `_last_info`;
- current `_metadata_paint`;
- current artwork pixmap/key;
- stable CUSTOM geometry.

Drive:

```text
live Media
-> enter CUSTOM
-> no Save
-> Cancel
```

Pass:
- metadata is unchanged immediately after Cancel;
- artwork is unchanged immediately after Cancel;
- no provider poll/refresh is required to repopulate it;
- geometry remains the original committed geometry;
- visualizer still resumes exactly once;
- no broad persisted-layout replay is required for untouched preview-only widgets.

Do not add another diagnostic family first.

---

## 4. ACTIVE — the actual visible startup GL warmup problem was NOT fixed

The previous requested startup correction was to move normal deferred transition GL program/resource
warmup before visible reveal.

That did not happen.

The landed work moved **widget painted-frame preparation** earlier. Useful, but different.

### 4.1 Current source still deliberately blocks normal GL warmup during fade

`rendering/gl_compositor_pkg/gl_lifecycle.py::_deferred_warmup_block_reason()` still returns:

```text
startup_hold
first_frame
startup_fade
```

and specifically blocks deferred warmup while the fade coordinator is `FADING`.

### 4.2 Latest installed log proves the old ordering remains

At startup:

```text
first frame ready
critical GL ready
fade starts
...
fade_completed=True
deferred_gl_warmup_started=False
...
fade_completed=True
deferred_gl_warmup_started=True
```

for both displays.

So the runtime still reveals first and then begins the remaining deterministic GL transition
program/resource preparation.

That is exactly the visible-startup policy we intended to remove.

### 4.3 Required correction

Use the existing startup/recreation readiness transaction.

Preferred shape:

```text
QRhi generation/context ready
-> first-frame critical resources ready
-> acquire/retain a current-generation startup hold
-> prepare normal transition programs/resources legally while still hidden/fade-zero
-> release hold
-> visible fade
```

The real owned work, not an arbitrary delay, releases readiness.

It is acceptable for hidden startup/recreation to take somewhat longer if first-visible motion is
already ready.

Preserve:
- current QRhi context ownership;
- current offscreen/shared-context legality;
- generation fencing;
- exact resource deletion;
- all transition programs/fidelity.

Do not:
- add a fixed startup sleep;
- compile GL on an illegal worker/context;
- add another timer/presentation surface;
- use `glFinish()` as a shortcut;
- remove transition programs to avoid their cost.

### 4.4 Bars

Prove:
- normal transition programs/resources intended for the generation are ready before visible fade;
- no normal deferred transition compile burst begins only after `fade_completed=True`;
- first use of a transition does not cold-compile something startup promised to prepare;
- stale-generation warmup cannot apply;
- cleanup retires shared/offscreen warmup ownership exactly.

This is a source-proven ordering bug. Do not probe it again before fixing it.

---

## 5. ACTIVE — Spectrum gets a real idle presentation

Spectrum is currently the only visualizer mode whose startup/card reveal is gated on real playback.

### 5.1 Source truth

Both:
- `startup_staging.mode_allows_idle_reveal()`;
- `tick_pipeline._mode_allows_idle_reveal_key()`

currently allow idle reveal for:

```text
bubble
sine_wave
oscilloscope
devcurve
```

and exclude `spectrum`.

That directly explains the installed behavior:
- starting while Spectrum is selected and no music is playing shows no visualizer card;
- playback later has to bring the Spectrum scene into existence from a dormant state.

### 5.2 Desired idle look

Start with the cheapest safe design:

**a tiny deterministic static Spectrum baseline**.

For example:
- same normal bars;
- same authored colours/borders/glow;
- roughly 1–3% visible height;
- slight fixed bar-to-bar variation is allowed if it looks better;
- no fake transients/energy/audio.

Do not initially add a moving left-to-right pulse. A static idle scene should settle to one scene
revision, allowing existing unchanged-scene suppression to make the physical steady cost almost
zero.

If a future aesthetic pulse is desired, it must use the one authoritative logical visualizer clock,
not another timer.

### 5.3 Ownership

Idle Spectrum is **presentation state**, not synthetic audio.

Do not inject fake values into:
- audio capture;
- BeatEngine source bars;
- source generation;
- energy/transient buses;
- onset logic.

When real playback arrives:
- authoritative real Spectrum data takes over immediately;
- the card does not disappear/recreate;
- no cold startup stage is re-entered;
- no new presentation clock is created.

All five modes should therefore share the high-level rule:

> the visualizer/card can exist while idle; real music reactions require real authoritative source.

### 5.4 Bars

Prove:
- cold startup on Spectrum while paused reveals the card and tiny idle Spectrum;
- source/energy generations still indicate no invented audio;
- steady idle does not produce continuous scene revisions merely to stay visible;
- Play replaces idle bars with real source bars without card recreation/pop/stall;
- Pause returns to idle presentation without hiding/restarting the logical runtime.

---

## 6. ACTIVE MAJOR P2 — isolate visualizer logical cadence from the Qt GUI event loop

The entry condition is now met.

This is no longer a Future-Cleanup idea.

### 6.1 Why it is active now

Latest visualizer evidence again shows large logical service holes while rendering remains cheap.

Initial current-head Bubble session:

```text
~0.4s   24.9 logical FPS   dt_max 58.1 ms
~5.4s   66.1               dt_max 61.5 ms
~10s+   ~75–82 class
~30s    79.1               dt_max 95.9 ms
```

The run repeatedly reports tick gaps in roughly the 50–110+ ms class, including examples near
115 ms and 150 ms.

Later DevCurve and Bubble periods show the same broad hole class.

Meanwhile representative visualizer presentation remains inexpensive:

```text
visualizer GL/GPU p95       roughly sub-1ms class in many windows
overlay paint CPU p95       roughly ~1ms class
state -> paint p95          commonly ~8–12ms
```

The renderer cannot explain a 60–150 ms logical freeze.

The present logical owner is still a GUI-thread Qt timer.

Known shared waste has been removed repeatedly, yet ordinary authored cadence still depends on Qt
event-loop service.

That is enough evidence to replace the cadence owner rather than start another timer-probe campaign.

### 6.2 Target architecture

First implementation should remain:
- inside the existing SRPSS process;
- Python;
- one dedicated **non-Qt** visualizer logical thread;
- one authoritative logical visualizer clock for all modes.

Conceptually:

```text
audio / media / config inputs
        |
        v
VisualizerLogicalRuntime
  standard Python thread
  monotonic deadlines
  no QObject
  no QTimer
  no QWidget
  no QPixmap
  no OpenGL
        |
        v
bounded latest-state mailbox
  immutable current-generation state
  monotonically increasing revision
        |
        v
existing GUI/compositor owner
  samples latest state
  uploads/draws legally
  one QRhi surface
```

### 6.3 Do not move the current widget tick wholesale to a worker

Current `_on_tick()` and helpers still know about QWidget/compositor/UI state.

Extract the logical core.

The logical runtime may own:
- monotonic cadence/deadline;
- playback/idle logical state;
- current mode/activation;
- source-frame consumption;
- event/transient integration;
- mode simulation;
- smoothing;
- current render-state construction;
- latest revision publication.

The GUI side retains:
- QWidget/CUSTOM anchor;
- card pixels;
- geometry;
- Qt signals/controls;
- QRhi/GL resources;
- shader/buffer upload;
- presentation fade;
- physical display timing.

### 6.4 Bounded latest-state bridge

Do not create one queued GUI callback per logical step.

Prefer:
- one immutable latest-state slot/mailbox;
- one revision;
- compositor/presentation owner samples the freshest current-generation state at its existing
  physical opportunity;
- superseded unpublished state is replaced, not queued.

No FIFO. No catch-up replay.

A 165-Hz display may physically present the latest ~100-Hz authored states without redrawing an
unchanged scene. A 60-Hz display may sample the same ~100-Hz logical runtime at ~60-Hz physical
presentation.

All authored inputs/events still integrate logically even when every intermediate logical snapshot
cannot physically appear.

### 6.5 Thread/lifecycle ownership

The logical thread must not become an invisible daemon that survives runtime replacement.

It must:
- have one explicit visualizer/runtime-generation owner;
- have a stop/wake primitive;
- quiesce/join before its runtime generation is destroyed;
- reject publication from retired generation/activation;
- retain no QWidget/QObject/GL references;
- be visible to lifecycle accounting or have an equally explicit owner/bar proving termination.

Do not reuse/reactivate the rejected persistent Bubble lane.

This is a mode-general runtime, not a Bubble scheduler.

### 6.6 Python/GIL scope

Use the in-process Python thread first.

Do not jump to a helper process/C++ rewrite in this round.

If the isolated runtime later proves materially GIL-starved by Python-heavy GUI work, that becomes a
new bounded architecture decision based on the clean thread boundary. Do not pre-emptively add IPC
or native code.

### 6.7 Preserve exact mode behavior

Reuse existing pure mode maths/state where possible. Move ownership, not aesthetics.

Require current all-mode goldens/temporal tests to remain equivalent for:
- Bubble trajectory/reaction;
- Spectrum bar response/smoothing;
- Sine waveform/heartbeat/crawl;
- Oscilloscope waveform behavior;
- DevCurve layer/idle behavior.

A larger extraction is acceptable if it deletes the GUI-timer ownership and redundant state-machine
plumbing rather than layering a second clock beside it.

---

## 7. ACTIVE WITH SECTION 6 — remove mode/playback edge stalls, do not add another state machine

The operator sees brief stutter:
- when a visualizer mode comes on;
- when playback leaves active state;
- when it returns from idle.

Some of this is the same GUI cadence starvation described above. Current source also contains a
separate structural seam worth fixing while logical ownership moves.

### 7.1 Current mode-switch path is still destructive

`mode_transition.py` currently performs, around a normal switch:
- fade old mode out;
- `_clear_gl_overlay()`;
- apply target activation;
- reset mode-owned runtime state;
- clear runtime bars;
- cancel pending compute;
- reset smoothing/floor;
- potentially rebuild technical config;
- potentially restart capture for a block-size change;
- wait for fresh bars/waveform or timeout;
- then fade target in.

Some of that reset work is required. Some exists because mode logic, engine state, GUI state and
presentation readiness are still intertwined.

Do not optimize each mode separately.

### 7.2 Desired edge contract

After the logical-runtime extraction:

**Mode switch**
- presentation fade remains owned by the existing compositor/fade contract;
- target activation is one atomic logical-runtime transaction;
- mode-owned state resets once;
- logical runtime keeps its one authoritative cadence;
- GL/card ownership stays alive unless a real GL resource identity changed;
- target fade-in waits only for the target logical activation/state actually required;
- no duplicate engine/config reset.

**Pause / idle**
- logical runtime continues at its authored idle cadence;
- idle-capable mode state keeps evolving;
- Spectrum uses its static idle presentation;
- source capture may warm-pause/stop according to its existing service policy;
- the visualizer/card is not torn down merely because playback paused.

**Resume**
- real source becomes authoritative when fresh;
- no cold visualizer startup staging;
- no logical-thread restart;
- no full card/GL recreation;
- no visual blank while capture catches up.

### 7.3 Tests

Production-shaped all-mode edge bars should cover:
- playing -> pause -> idle -> play;
- long enough idle for capture to stop, then play;
- mode switch while playing;
- mode switch while idle;
- each target mode becomes visible without a 0.35/1.5-second timeout being normal control flow;
- no extra activation generation;
- no duplicate audio restart;
- no stale old-mode state;
- all five mode feel/goldens preserved.

A timeout may remain fail-safe. It must not be the normal successful reveal owner.

---

## 8. Status of current overlay pre-reveal frame work

Keep the two latest frame-cache changes while the active work above proceeds.

They have one useful demonstrated effect:
- current `perf_widgets.log` shows no painted-frame shadow regeneration family in the latest run.

But:
- the user saw no perceptual improvement;
- the current head's global performance is unaccepted.

Do not spend a separate round proving these changes again.

At the next installed gate:
- if performance returns to or exceeds the 4.7.2 class, keep them;
- if the application remains materially below baseline and no newer owner explains it, include them
  in rollback/reassessment rather than declaring them safe solely from unit tests.

---

## 9. ONE installed acceptance after Sections 3–7

No intermediary installed runs.

After:
1. Media Cancel ownership correction;
2. actual pre-reveal GL warmup ordering;
3. Spectrum idle presentation;
4. mode-general logical-runtime isolation;
5. mode/playback edge continuity;

and after focused/combined automated gates are green, request one:

```text
python main.py --perf --gpu-timing --geo
```

### 9.1 Functional

Exercise:
- cold startup while paused;
- Spectrum selected at cold startup with no music;
- all five modes;
- all five mode switches;
- Play -> Pause -> idle -> Play;
- long-idle capture stop -> Play if practical;
- CUSTOM enter -> Cancel;
- Media content before/after Cancel;
- visualizer Cancel resume;
- cross-display visualizer Save;
- Settings recreation.

Pass:
- Spectrum card/idle state exists before playback;
- Media artwork/metadata survives Cancel immediately;
- no visualizer mode/card pop caused by cold re-entry;
- mode/playback edges have no obvious freeze;
- all mode aesthetics/reactivity remain correct;
- no stale-generation application;
- no destruction-barrier timeout;
- final resource ownership is clean.

### 9.2 Startup/recreation

Pass:
- deterministic normal transition GL warmup completes before visible fade release;
- no post-`fade_completed=True` normal shader compile burst;
- no fixed readiness sleep;
- first visible visualizer motion is already in its normal cadence class.

### 9.3 Visualizer cadence

Desired steady behavior:
- all modes roughly return to the intended ~90–100-Hz logical class where their authored work
  permits;
- ordinary Qt event-loop stalls no longer freeze the logical simulation itself;
- physical presentation samples newest logical state;
- no backlog/catch-up;
- no recurring user-visible logical hitch class.

Do not require impossible zero-jitter scheduling. Judge tail distribution plus installed feel.

### 9.4 Compositor comparison

The current head must earn its way back to the named baseline.

Use as comparison:

```text
165-Hz BlockSpin baseline median    ~152.45 FPS
baseline acceptance                 ~94.79%
best accepted windows               ~157–160.6 FPS

60-Hz baseline median               ~59.7 FPS
baseline acceptance                 ~99.44%
```

A single noisy window is not enough to fail a run, but a median in the current `~125 FPS` class is
not acceptable.

Do not sacrifice transition/visualizer fidelity merely to hit a number.

### 9.5 Efficiency

Compare same-machine usage against both:
- current regressed run: app CPU median ~104.8%;
- named baseline: roughly low/mid-70% whole-run post-prime class, with workload-dependent higher
  subsets.

The logical-runtime change should not merely move wasted work onto another core. It should improve
cadence first and keep/remove technical work where possible.

GPU remaining low is expected.

---

## 10. P5 — monitor topology / physical sleep-wake remains mandatory next major phase

Do not call lifecycle complete after P2.

Existing foundations are useful:
- screen signatures;
- screen-added/removed inputs;
- runtime generation fencing;
- full stop/destruction-barrier/rebuild;
- current-image replay.

The complete P5 transaction still has not landed.

Required architecture remains:

```text
Notify
-> trailing-edge Settle
-> immutable topology Snapshot
-> Retire old runtime
-> destruction Barrier
-> Rebuild from frozen snapshot
-> Reveal
```

Still required:
- one topology decision owner;
- later topology events restart settlement and/or queue the next transaction rather than mutate the
  frozen one;
- Windows/Qt screen messages are invalidation inputs, not competing mutation owners;
- sticky configured visualizer monitor through temporary sleep/non-participation;
- ~60-second confirmation only for genuine settled absence before fallback;
- event-driven return-home;
- no polling monitor thread;
- wake recovery does not depend on synchronous waking-desktop screenshot capture;
- physical both-off/long-idle/simultaneous/staggered-wake acceptance.

Run P5 only after the next P2 installed result is reviewed against the baseline.

---

## 11. After P5

Continue with:
- long-run RAM/private-commit/VRAM slope work;
- remaining concrete shared GUI/CPU waste;
- mode-general compute/task scaffolding if still material after the logical-runtime extraction;
- diagnostic/legacy retirement from `Future_Cleanup.md`.

Do not stop improving project health because a benchmark is good. Do stop creating speculative
mechanisms when source/evidence does not name a problem.
