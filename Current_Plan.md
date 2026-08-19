# Current Plan

Last updated: 2026-08-19
Branch: `main`
Current source anchor: `0a06ebe08c6f6f5d5481f838ea2298e959bc9110`
Named accepted rollback/fidelity baseline: **4.7.2 / `42033c84eabbdf25ccd34bb0e83f9e553f2f8f11`**
Architecture epoch: **single-surface OpenGL QRhi compositor + compositor-owned visualizer presentation**

This file owns unfinished active work and execution order. Exact current source and installed evidence
override completion messages and unit-test victory reports.

The latest installed run is **not** a reason to reopen the QRhi/single-surface architecture. It
instead identifies three concrete remaining ownership defects and confirms that the dedicated
logical-runtime extraction is now mandatory.

---

## 1. Binding contracts

### Presentation

One physical display owns one accelerated QRhi/OpenGL compositor surface.

The visualizer is a compositor layer. Do not introduce:
- another presented visualizer surface;
- another physical presentation clock;
- paint acknowledgement/backpressure;
- pending-until-paint admission;
- source/display cadence division;
- repaint rescue/self-requeue;
- FIFO/catch-up render queues;
- CPU/QPainter visualizer fallback.

Physical presentation samples the freshest valid current-generation visualizer state. It does not
own simulation time.

### Visualizer

All five modes are peers:
- Bubble;
- Spectrum;
- Sine;
- Oscilloscope;
- DevCurve.

Preserve current look, shaders, glow, trajectories, transients, smoothing, elasticity, idle
personality and reaction latency.

Do not relabel a shared cadence failure as a Bubble problem merely because continuous Bubble motion
makes it obvious.

### Efficiency

Remove technical work rather than authored work.

A new thread is allowed when it **replaces one unsuitable owner with one authoritative owner**.
It is not allowed as a second clock beside the existing one.

No new probe campaign when source + current logs already distinguish the owner.

---

## 2. Latest installed result — what is accepted and what is not

### 2.1 Global compositor performance is back in the expected class

The previous run's apparent ~100–125-FPS collapse was not a clean source-regression comparison.
The latest run confirms that.

Nine complete 165-Hz transition windows in the new archive deliver approximately:

```text
149.2–158.0 useful accepted frames/sec
median ~151.6
useful acceptance ~90.5–95.8%
```

Representative BlockSpin windows are again around the accepted low/mid-150 class.

This is close enough to the named 4.7.2 delivery baseline that there is **no current evidence of a
large sustained compositor regression** from the overlay-frame cache changes.

Do not create a speculative "restore 152 FPS" project.

The remaining product failure is overwhelmingly **visualizer logical/edge smoothness**, not a
collapsed compositor renderer.

### 2.2 Renderer/GPU remain too cheap to explain the visualizer hitching

In the short 13:18 run:

```text
Bubble logical tick:
~60.6 Hz at ~5 s
~66.0 Hz at ~10 s
dt_max ~79 ms

visualizer overlay paint p95:
~0.66 ms

visualizer GPU p95:
~0.70 ms

state -> paint p95:
~11.75 ms
```

The longer run also contains repeated visualizer logical holes in roughly the 40–85-ms class and
occasional worse examples across Bubble/Spectrum/other states.

This is the exact condition previously defined for replacing the GUI-thread Qt cadence owner.

### 2.3 Latest operator acceptance

Improved:
- startup and ordinary mode switching are smoother than playback pause/resume;
- no report of the previous Media Cancel content loss in this run;
- transition GL compilation is substantially moved earlier.

Still failed:
- visualizer still visibly hitches;
- Play/Pause is the worst edge by far;
- Pause does not gracefully enter idle;
- Resume visibly slogs before healthy motion;
- Spectrum idle does not appear;
- switching to Spectrum while paused leaves no card;
- after Settings/reconstruction in that state the runtime comes back as Bubble.

Those failures are supported by current source and logs below.

---

## 3. LANDED — Media Cancel ownership correction

Commit `ad3d79d9...` removed broad Cancel replay for ordinary preview-only live widgets and made the
two Media size setters no-op on unchanged values.

The latest archive does not contain a fresh CUSTOM Cancel exercise, so this is:
- **source/test landed**;
- **not re-proven by this particular installed run**.

Do not reopen it unless the next acceptance reproduces artwork/metadata loss.

The next acceptance must still exercise one populated Media Cancel to close it installed.

---

## 4. ACTIVE CORRECTION — pre-reveal GL warmup has a multi-display hold ownership bug

The new warmup design is directionally correct but not yet correct on two displays.

### Proven log sequence

On the 13:18 reconstruction, screen 1 behaves correctly:

```text
screen 1:
hold = gl_transition_warmup
deferred warmup starts
raindrops/wipe/.../burn compile
Pre-reveal transition warmup settled
hold clears
fade starts
```

Screen 0 does not:

```text
screen 0:
hold = gl_transition_warmup
...
screen 1 settles
screen 0 hold is now gone
screen 0 fade starts
screen 0 deferred warmup starts
screen 0 raindrops/wipe/.../burn compile
```

So one display is still compiling its normal transition programs **after its visible fade begins**.

### Exact source cause

`gl_lifecycle.py` currently makes each compositor's hold global:

```text
_fade_coordinators_for_compositor(widget)
    -> enumerates all live display fade coordinators

_acquire_pre_reveal_warmup_hold(widget)
    -> adds the same string "gl_transition_warmup" to every coordinator

_release_pre_reveal_warmup_hold(widget)
    -> releases that same string from every coordinator
```

The coordinator hold is a named-set style contract, not a per-compositor reference count.

Therefore the first compositor to finish can release the second compositor's protection.

This is a real ownership bug, not a timing hypothesis.

### Required correction

One compositor must never release another compositor's warmup obligation.

Use a bounded ownership model such as:
- unique current-generation hold tokens per compositor on the shared startup barrier; or
- one explicit aggregate startup-warmup owner that releases only after every current-generation
  compositor reports complete.

Preferred behavior is still globally safe on multi-display startup:
- no display begins visible fade while another display is about to monopolize the GUI thread with
  its deterministic startup GL compile burst.

Do not solve this with:
- sleeps;
- longer arbitrary delays;
- a second timer;
- compiling GL on an illegal worker/context;
- removing transition programs.

### Bars

Production-shaped dual-display test:
- two compositor owners acquire distinct obligations;
- compositor A completion cannot release B;
- fade cannot begin while any current-generation obligation remains;
- both complete -> release -> fades may begin;
- stale/retired generation completion cannot release a current generation;
- failure/no-context/RHI-retire paths settle only their own obligation;
- single-display path remains simple.

Installed log must show **both displays** completing normal warmup before either visible startup fade
is released.

---

## 5. ACTIVE CORRECTION — Spectrum idle exists in code but is unreachable

The static Spectrum idle visual itself is fine.

`idle_spectrum_baseline()` is a deterministic 1–3% presentation floor with no fake audio, time term
or random input.

The bug is the state path that prevents it from ever reaching presentation.

### 5.1 Proven paused-switch deadlock

Current `tick_pipeline.py` intentionally excludes Spectrum from
`_IDLE_SELF_ANIMATING_MODES`.

While paused after a Spectrum activation:

```text
_waiting_for_fresh_engine_frame = True
```

The consume path only clears that wait for `_IDLE_SELF_ANIMATING_MODES`.

Spectrum therefore remains waiting for an engine frame that cannot arrive while capture is paused.

The tick then returns early while waiting.

`push_gpu_frame()` is downstream of that return.

But `push_gpu_frame()` is the only normal call site that invokes:

```text
resolve_widget_spectrum_presentation(...)
```

which is where the static idle baseline is created.

So the system currently says:

> Spectrum's idle presentation needs no source frame,
> but do not call Spectrum's idle presentation until a source frame arrives.

That directly explains the blank card after switching to Spectrum while paused.

### 5.2 Why Settings comes back as Bubble

The latest log shows:

```text
13:18:25 request Bubble -> Spectrum
13:18:27 logical mode becomes Spectrum
...
13:18:35 phase=2, waiting_engine=True, waiting_frame=True
```

There is no successful `Persisted vis mode: spectrum` before the subsequent Settings recreation.

At 13:18:40 the replacement runtime therefore starts from persisted Bubble again.

This is a consequence of the stuck Spectrum transition, not evidence that Settings independently
chooses Bubble.

### 5.3 Second duplicate capability bug

`media_bridge.seed_playback_state_from_anchor()` still has its own hard-coded idle-capable set:

```text
bubble
sine_wave
devcurve
```

It omits both Oscilloscope and the newly-idle Spectrum.

That duplicates and contradicts `startup_staging.mode_allows_idle_reveal()` / tick-pipeline
capability logic.

A provisional retained paused media seed can therefore still block Spectrum startup/reconstruction
even though Spectrum is now supposed to have a presentation-owned idle scene.

### Required correction

Separate these concepts explicitly:

1. **may reveal/present while idle**;
2. **creates logical idle motion without source**;
3. **requires a fresh real source before reactive playback bars receive authority**.

Spectrum must be:

```text
idle reveal allowed            YES
idle self-animation            NO
presentation-owned idle scene  YES
fresh real source for PLAY     YES
```

While paused, Spectrum may publish its presentation-owned idle frame even if
`_waiting_for_fresh_engine_frame` remains true for future reactive source authority.

Do **not**:
- mark the engine generation fresh;
- invent source-generation ids;
- feed baseline values into BeatEngine/audio/transient state;
- grant stale bars reactive authority.

When Play begins, current activation/generation source gating remains strict. Fresh real Spectrum
bars replace the idle presentation in place.

### Canonicalize capability ownership

Remove the duplicate idle-mode sets from `media_bridge`, `startup_staging`, and tick logic.

Use one canonical visualizer-mode capability source/helper/registry so startup, runtime, mode
transition and media seeding cannot disagree again.

### Bars

Production-shaped tests must drive the real tick path:

```text
paused
-> switch to Spectrum
-> target generation waiting for real source
-> idle card/baseline nevertheless publishes
-> fade completes
-> Spectrum mode persists
```

Then:

```text
Settings/recreate while paused with Spectrum persisted
-> runtime remains Spectrum
-> card + idle baseline reveal
-> no real source generation is fabricated
```

Then Play:
- idle scene stays visible;
- fresh current-generation real bars become authoritative;
- no blank/recreate/pop.

---

## 6. ACTIVE CORRECTION — playback state debounce currently owns visible animation

This is the clearest cause of the user's worst pause/resume slog.

### 6.1 Current coupling

`media_bridge.py` defines:

```text
_PLAYBACK_PAUSE_CONFIRM_MS = 700
```

A `paused`/`stopped` media update while `_spotify_playing=True` does not immediately change the
visualizer's logical playback state. It arms a Qt timer.

Any wobbling update can cancel/re-arm that timer.

Only after confirmation does `_commit_playback_state()` flip `_spotify_playing`.

That same boolean currently controls both:
- whether the visualizer evolves as active vs idle;
- BeatEngine playback/capture policy.

### 6.2 Installed evidence

The long run records deferred pause messages at approximately:

```text
13:15:14
13:15:16
13:15:17
13:15:19
13:15:23
```

The BeatEngine does not finally enter non-playing/warm-capture state until roughly:

```text
13:15:24
```

So the nominal 700-ms visual debounce can become many seconds of visible limbo when media state
wobbles or the user retries the command.

The short run shows the same pattern around 13:18:16–13:18:21.

That matches the operator's report that pause/unpause is substantially worse than ordinary mode
switching.

### 6.3 Capture already has its own anti-churn policy

BeatEngine already has:

```text
_capture_keepalive_grace = 6.0 seconds
```

On Play -> Pause it keeps capture warm for six seconds.

If Play returns within that window, the engine logs a warm resume and avoids the cold reactivity
ramp.

Therefore the visualizer does **not** need a 700-ms delayed visible-state transition merely to
protect capture from short provider wobble.

### Required ownership split

Separate:

**logical/presentation playback target**
- changes promptly from the trusted MediaWidget state/user intent;
- drives active -> idle and idle -> active visual evolution;
- must never wait multiple seconds for capture-retirement policy.

**capture/service lifetime**
- may keep loopback capture warm for the existing bounded grace;
- may absorb provider wobble without tearing the worker down;
- remains BeatEngine/service policy.

The visualizer bridge should trust the canonical MediaWidget normalized/optimistic state rather than
adding another visible-state debounce timer on top of MediaWidget's own override logic.

Do not replace the 700-ms timer with a different animation timer.

### Edge behavior

Pause:
- preserve current mode/card/GL resources;
- immediately begin authored transition toward that mode's idle state;
- no clear/rebuild;
- no generation churn solely because playback paused;
- capture may remain warm separately.

Resume while capture warm:
- same logical runtime continues;
- fresh source takes authority as soon as available;
- no cold startup staging;
- no card recreation;
- no 1.5-s cold ramp when the existing warm-resume contract applies.

If stale provider updates need rejection, solve that at the canonical Media state/override owner, not
by freezing the visualizer in its old state.

---

## 7. ACTIVE MAJOR P2 — replace the GUI-QTimer logical cadence owner now

This is mandatory in this round.

Do **not** stop after Sections 4–6 and request another acceptance.

The latest installed run again satisfies the previously agreed trigger:
- logical cadence can fall to ~60–66 Hz;
- recurring ~40–80+ ms logical holes remain;
- renderer/GPU are sub-ms class;
- state->paint is healthy enough;
- no individual visualizer mode workload explains the holes.

Claude's concern that the extraction is large is reasonable, but the plan already chose the
architecture precisely to avoid another probe loop. The implementation must now do the bounded
structural replacement rather than leave the known wrong owner in place.

### 7.1 Target

Same process. Python first.

```text
Audio / analysis producer
        |
        v
immutable latest analysis/source snapshot
        |
        v
VisualizerLogicalRuntime
  one standard-Python thread
  one monotonic deadline owner
  no QObject/QTimer/QWidget/QPixmap/OpenGL
  all five mode logical state
  playback target / idle evolution
  activation + generation fencing
        |
        v
immutable latest VisualizerRenderState + revision
        |
        v
existing GUI/compositor
  samples freshest state
  card/geometry/fade
  GL upload/shader
  physical presentation
```

### 7.2 Replace, do not add

There must be one authoritative logical clock after landing.

The existing recurring visualizer `QTimer` must cease to own simulation cadence.

Do not leave:
- a worker logical clock plus the old QTimer;
- a hidden fallback logical timer;
- an AnimationManager logical tick;
- per-mode timers.

Qt can still own ordinary UI deadlines and physical presentation.

### 7.3 Extraction boundary

Do not move current `_on_tick()` wholesale to a worker.

Split its concerns.

The logical runtime owns only plain-data work:
- monotonic dt/deadline;
- current mode and activation identity;
- playback target;
- analysis/source snapshot consumption;
- source freshness bookkeeping represented as plain data;
- mode simulation;
- smoothing/envelopes/transients;
- idle evolution;
- immutable render-state construction.

GUI remains owner of:
- QWidget state;
- settings controls;
- CUSTOM geometry;
- QPixmap/card rendering;
- presentation fade;
- QRhi/GL resource creation/deletion;
- shader/buffer upload;
- display physical cadence.

Transition-running state must not retune logical cadence.

### 7.4 Analysis bridge

Do not make the logical thread call arbitrary QObject-owned APIs.

Expose the audio/BeatEngine results needed by logical simulation through a bounded immutable/plain
snapshot boundary.

Latest replaces older latest. No analysis FIFO/catch-up.

All authored events/transients that must survive sampling need to be integrated into the snapshot or
event state before they can be overwritten.

### 7.5 Render-state bridge

Do not queue one GUI callback per logical step.

Use a latest-state mailbox/slot with:
- immutable current-generation state;
- monotonically increasing revision;
- replacement of superseded unpublished state.

Prefer the existing compositor/presentation opportunity sampling that mailbox. A bounded
single-pending GUI nudge is acceptable only if required to wake an otherwise-idle compositor.

No backlog.

### 7.6 Playback/idle belongs here

Section 6's ownership split should converge into this runtime.

The logical cadence must not drop from active to a separate 75-Hz clock merely because playback
paused.

Current `resolve_max_fps()` has a paused cap of 75 Hz. That policy belongs to the old QTimer
architecture and should not survive merely by inertia.

Preserve the intended ~90–100-Hz authored logical service class across active/idle states unless a
mode is truly static:
- static Spectrum idle may publish once and stop changing revision;
- other idle modes continue their authored motion;
- physical presentation suppression already prevents useless duplicate redraws.

Do not lower logical cadence to manufacture efficiency.

### 7.7 Mode activation

A mode switch becomes one logical activation transaction:
- one target identity;
- one mode-owned reset;
- no duplicate config/engine generation;
- no logical-thread restart;
- presentation fade remains GUI/compositor-owned.

Playing target modes still require fresh current-activation real source where their visuals need it.

Idle-ready modes can publish their authored idle scene without waiting for impossible paused source.

### 7.8 Thread lifecycle

The logical runtime is runtime-generation owned.

It must have:
- explicit start;
- explicit stop/wake primitive;
- bounded quiesce/join before runtime destruction;
- no daemon escape hatch;
- no QWidget/QObject/QPixmap/GL references;
- stale generation/activation publication rejection;
- destruction-barrier accounting or an equally explicit lifecycle bar.

CUSTOM Edit should suspend presentation as it does now. It must not destroy/recreate the logical
thread merely for preview.

Settings/full runtime replacement retires the old logical runtime before the new generation may
publish.

### 7.9 Fidelity bars

Use the existing all-mode goldens and production-shaped tests.

Must preserve:
- Bubble trajectory/reactivity;
- Spectrum response/glow/smoothing;
- Sine waveform/heartbeat behavior;
- Oscilloscope waveform behavior;
- DevCurve layers/idle behavior;
- all transients/events;
- current mode activation semantics.

A test that proves only “the thread ran” is insufficient.

### 7.10 No premature native escalation

Do not use:
- helper process;
- C/C++;
- native extension

in this round.

If the clean in-process Python runtime later proves materially GIL-starved, that becomes a new
decision from a much cleaner boundary.

---

### Attempted and reverted 2026-08-19 — read this before retrying

The runtime itself is correct and is retained, unwired, in
`widgets/spotify_visualizer/logical_runtime.py`: one non-daemon thread, one
monotonic deadline sequence, missed deadlines skipped rather than replayed, a
latest-wins mailbox with generation fencing, and a bounded quiesce/join. The
installed run confirms it behaves: `steps=2825 skipped_deadlines=1148
slow_steps=0 failures=0 joined=True`.

Wiring it as the cadence owner broke the product, in two stages:

1. **Nothing presented at all.** `logical_tick()` requested presentation through
   `getattr(widget, "_request_logical_present", None)`, and that widget method
   had been removed when the plumbing moved into `tick_pipeline`. The optional
   lookup returned `None` silently, so 1082 logical steps produced zero pushed
   frames and the reveal watchdog expired with `waiting_frame=True`.

2. **Every mode switch failed.** With presentation fixed, switches still ended
   invisible: `[OVERLAY] reason=cleanup mode=oscilloscope set_state=338 paint=0
   visible=False enabled=False`. `logical_tick()` reaches
   `check_mode_teardown_ready()` -> `begin_mode_fade_in()`, which calls
   `invalidate_shadow_cache_if_needed()`, `apply_pending_mode_transition_layout()`
   and `start_widget_fade_in()`. Those are QWidget/QPixmap operations; off the
   GUI thread they failed inside the surrounding broad handlers, silently.

The operator also reported Bubble losing its visual-only smoothing and Spectrum
showing no idle bars in that run. Both are consistent with ~29% of logical
deadlines being dropped with irregular dt, and neither was re-diagnosed
separately after the revert.

**The blocking prerequisite, precisely.** Section 7.3 already says the logical
runtime owns only plain-data work. The mode-activation/fade reveal path is the
concrete thing that is not plain-data and is still reachable from the logical
half. Before the thread can own cadence, that path has to become: logical
runtime decides *readiness* as plain data, GUI owns the *reveal*. That is a
bounded piece of work with a clear boundary, and it should be a slice of its
own with its own installed check, not folded into the cadence swap.

**What the gates missed, and what was added.** Every bar asserted a piece - the
runtime stepped, the mailbox published, the timer existed - and none asserted
that anything became visible. `tests/test_p2_mode_switch_becomes_visible.py`
now requires a switch into each of the five modes to reach its fade-in and
start the widget fade, and fails if a thread cadence owner is wired up again
while the reveal work is still in the logical path.

Cadence meanwhile returns to the GUI recurring timer, now running at the
authored logical interval instead of the old 16 ms default plus per-tick
retuning.

---

## 8. Current mode-switch reset path — simplify only where the new runtime makes it obsolete

Ordinary mode switching is now visibly better than playback pause/resume.

Do not start an independent mode-switch rewrite.

While extracting Section 7, remove only technical reset/wait machinery made obsolete by the new
logical owner, especially:
- duplicate logical resets;
- waiting on source that an idle presentation does not require;
- timer-interval retuning;
- GUI-tick-specific transition context.

Keep:
- one presentation fade authority;
- one target activation;
- real-source freshness for active playback;
- strict old-generation rejection.

The timeout in `check_mode_teardown_ready()` may remain a fail-safe. It must not be normal successful
control flow.

---

## 9. ONE installed acceptance after Sections 4–8

No intermediary installed runs.

Request:

```text
python main.py --perf --gpu-timing --geo
```

### Startup / GL

Prove on both displays:
- each current-generation warmup obligation remains owned until that compositor/aggregate is done;
- no normal transition-program compile begins after either display's visible fade starts;
- no hold timeout is normal control flow;
- first visible motion is already past deterministic GL warmup.

### Spectrum

Start the application while paused with Spectrum persisted:
- it remains Spectrum;
- card is visible;
- static low Spectrum baseline is visible;
- no fake source generation is created.

While paused:
- switch another mode -> Spectrum;
- card/baseline appears;
- fade completes;
- Spectrum persists.

Then Settings/recreate:
- Spectrum remains Spectrum;
- no Bubble fallback.

Then Play:
- real current-generation Spectrum bars replace idle presentation without blanking/recreation.

### Play/Pause

Exercise repeated:
- Play -> Pause;
- Pause -> Play;
- quick toggle;
- a pause long enough for capture keepalive to expire if practical.

Pass:
- visual transition to idle begins promptly;
- no multi-second debounce limbo;
- warm resume is immediate/smooth;
- no card/GL/logical-runtime restart;
- capture keepalive remains bounded and independent.

### All modes

Exercise all five:
- playing;
- idle;
- mode switching;
- resume.

Pass installed feel before counters.

### Logical cadence

The dedicated runtime must show:
- one authoritative non-Qt cadence owner;
- steady authored cadence back near the intended ~90–100-Hz class;
- ordinary GUI event-loop stalls no longer create equivalent 40–80-ms **simulation** freezes;
- no FIFO/catch-up;
- no source/transient loss;
- no second logical clock.

Physical presentation can still miss a frame when the GUI is busy; simulation must no longer freeze
with it.

### Compositor

Preserve current recovered delivery class.

Recent accepted/current evidence says high-refresh transitions are again roughly:

```text
~149–158 useful accepted FPS
median ~151.6
```

Do not trade transition fidelity for a benchmark.

### CUSTOM / lifecycle

Also exercise:
- populated Media -> CUSTOM -> Cancel;
- visualizer CUSTOM Cancel;
- cross-display visualizer Save;
- Settings recreation.

Pass:
- Media artwork/metadata survives immediately;
- visualizer resumes once;
- no stale logical runtime publication;
- destruction barriers remain clean;
- final tracked GL resources and tasks return to baseline/zero as applicable.

---

## 10. P5 remains the mandatory next major phase

After this P2 acceptance, do not continue polishing visualizer internals indefinitely.

P5 still needs the complete physical monitor transaction:

```text
Notify
-> trailing-edge Settle
-> immutable topology Snapshot
-> Retire
-> destruction Barrier
-> Rebuild
-> Reveal
```

Still required:
- one topology decision owner;
- later events cannot mutate the frozen transaction;
- Qt/Windows topology events are invalidation inputs only;
- sticky configured visualizer monitor through temporary sleep/non-participation;
- genuine-absence grace before fallback;
- event-driven return-home;
- no monitor polling thread;
- no wake-critical synchronous desktop screenshot;
- physical both-off/long-idle/staggered-wake acceptance.

Existing generation/destruction-barrier machinery is reused, not replaced.

---

## 11. After P5

Then return to:
- long-run RAM/private-commit/VRAM slopes;
- remaining concrete GUI/CPU waste;
- mode-general task/Future scaffolding only if still material after the logical-runtime extraction;
- diagnostic/legacy retirement from `Future_Cleanup.md`.

Do not create a separate Bubble optimization project unless future evidence actually isolates
Bubble-owned cost.
