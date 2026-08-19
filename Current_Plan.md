# Current Plan — P2 Visualizer Recovery

Last updated: 2026-08-19 after the failed worker-cadence installed run and the post-revert installed run  
Branch: `main`  
Current source anchor at review: `5c286616f20c9eeb232c632ea70dff5d34a86464`  
Named accepted rollback/fidelity baseline: **4.7.2 / `42033c84eabbdf25ccd34bb0e83f9e553f2f8f11`**  
Architecture epoch: **single-surface OpenGL QRhi compositor + compositor-owned visualizer presentation**

This file owns unfinished active work and supersedes stale execution/status language in the earlier plan. The reorientation document remains engineering doctrine, not execution authority.

Exact current source and installed behavior override commit messages, comments, unit-test victory reports, and previous claims that a component is “correct.”

---

## 0. Corrected current truth

### 0.1 The single-surface compositor architecture remains accepted

Do not reopen the compositor migration. Current evidence still says:

- one physical display owns one QRhi/OpenGL compositor presentation surface;
- the visualizer is a compositor layer, not a second presented widget/surface;
- renderer/GPU cost is too small to explain the large visualizer timing holes;
- transition delivery is back around the accepted low/mid-150 FPS class on the 165 Hz display;
- the remaining user-visible failure is predominantly logical cadence / lifecycle-edge smoothness.

Do not create mode-specific or transition-specific optimization work unless new evidence actually names mode-owned or transition-owned cost.

### 0.2 The first logical-runtime wiring attempt FAILED and was reverted

The attempted worker-cadence landing broke the product in two independent ways:

1. a required presentation handoff was looked up with optional `getattr(..., None)` after that method had been removed, so logical work ran while no frames were presented;
2. the logical worker still reached mode-reveal code which performs QWidget/QPixmap/layout/fade work, so mode switches could leave data flowing with the target visualizer invisible.

The worker wiring was reverted. The Qt-free runtime module and logical/presentation refactor pieces remain present but unwired.

### 0.3 REVOKED CLAIM: “the logical runtime itself is correct”

That statement is no longer accepted.

The failed installed worker run reported, over long windows:

```text
interval requested:             11.11 ms
observed logical service:       ~63.9–64.0 Hz
run A:                          3883 steps / 1581 skipped deadlines
run B:                          2825 steps / 1148 skipped deadlines
skipped-deadline fraction:      ~29%
slow_steps:                     0
step failures:                  0
```

A runtime that deterministically services roughly 64 Hz while targeting roughly 90 Hz is not a valid cadence owner merely because its individual callback bodies are fast and it joins correctly.

The exact ~64 Hz plateau is a scheduler/wait-loop defect or platform interaction until proven otherwise. The current runtime uses a timed `Event.wait()` as its deadline wait. That is an immediate audit/fix target, but the cause must not be overclaimed before the scheduler gate below proves it.

**Do not wire this runtime back into production until the scheduler-only cadence bar passes on the installed Windows/Python environment.**

### 0.4 The post-revert GUI timer is still the known wrong owner

After the revert there is no logical worker. The GUI recurring timer again owns the visualizer tick.

The post-revert installed run is functional but still bad:

```text
ordinary logical service:       roughly low/mid-80 Hz class
large GUI logical gaps:         repeatedly ~42–72 ms
pause/resume examples:          ~60–62 ms logical gaps
resume audio-to-log sample:     ~91 ms in one observed edge
```

This is why reverting the worker did not restore a finished product. It restored the known GUI-starvation architecture.

### 0.5 Playback debounce correction is LANDED; the pause/play hitch remains

The old visualizer-owned ~700 ms pause confirmation timer has been removed. Visible playback state now follows the canonical MediaWidget state promptly, while BeatEngine retains its separate six-second capture keepalive/warm-resume policy.

The post-revert installed run still hitches severely on Pause and Play.

Therefore:

> **Do not “fix Section 6” by reintroducing or replacing a playback debounce.**

The remaining edge hitch must be solved through the cadence/ownership correction and, only if necessary afterward, by narrowing synchronous wake/source-handoff work.

### 0.6 Spectrum idle architecture is correct in concept but still blocked at first presentation

Keep the consistency model:

```text
mode          idle reveal   idle self-motion   presentation-owned idle   fresh source for reactive play
Bubble            yes             yes                    no                         no
Spectrum          yes             no                     yes                        yes
Sine              yes             yes                    no                         no
Oscilloscope      yes             yes                    no                         no
DevCurve          yes             yes                    no                         no
```

This is cleaner than making Spectrum disappear whenever paused:

- every mode can retain/reveal its card while idle;
- Spectrum shows a static, presentation-owned low baseline with no fake audio;
- the baseline does not grant source authority;
- on Play, real current-generation Spectrum data must still become authoritative before reactive bars are accepted.

The current code now reaches the Spectrum idle-baseline resolver, but another gate still hides it.

The first-frame primer treats Spectrum as requiring authoritative source generation/activation even while paused. When those source ids are absent, it forces effective scene/bar fade to zero and refuses to complete the normal first-frame reveal handoff.

That exactly matches the post-revert installed behavior:

```text
paused Spectrum persists through Settings
-> idle baseline logic is reachable
-> waiting_engine remains true (correct for future reactive authority)
-> first-frame primer reports missing source generation/activation
-> reveal watchdog expires
-> Spectrum remains invisible
-> press Play
-> fresh source arrives
-> reveal finally completes
```

This is now the bounded Spectrum defect. Do not redesign Spectrum again.

### 0.7 Ordinary mode switching is not the current rewrite target

The post-revert run successfully exercises ordinary switching across modes again. The failed worker wiring showed that reveal ownership must be separated before cadence moves threads.

Do not start a new mode-switch state-machine rewrite. Extract only the GUI-bound reveal side effects that block the worker boundary.

---

## 1. Binding product contracts

Priority order remains:

1. **visualizer fidelity and reactivity**;
2. lifecycle / GL safety;
3. perceived smoothness / frame pacing;
4. multi-display correctness;
5. bounded RAM / VRAM;
6. CPU / task efficiency;
7. average FPS;
8. architecture elegance.

For Bubble especially, “smooth” means **continuous-looking motion without visible hitch/flicker while preserving immediate audio reaction**. Do not smooth, average, delay, decimate, or lower source/logical cadence to disguise timing defects.

Preserve:

- authored mode appearance;
- shaders/glow;
- trajectories and elasticity;
- transient response;
- existing visual-only motion smoothing;
- reaction latency;
- idle personality;
- source/event fidelity.

Do not solve P2 by:

- lowering authored logical cadence;
- capping high-refresh presentation;
- source/event decimation;
- adding a second logical clock;
- FIFO/backlog/catch-up simulation;
- paint acknowledgement/backpressure;
- QPainter/CPU visualizer fallback;
- moving QWidget/QPixmap/GL access onto a worker;
- hiding defects behind longer fades or debounces.

---

## 2. Execute in this exact order

The order is binding because each slice establishes a prerequisite for the next one.

### Slice A — finish Spectrum paused reveal on the CURRENT GUI cadence owner

Do not touch worker wiring in this slice.

#### Required semantic correction

Separate:

```text
presentation_ready
reactive_source_ready
```

For paused Spectrum with a presentation-owned idle scene:

```text
presentation_ready        = true
reactive_source_ready     = false
waiting_for_fresh_engine  = true
source generation/id      = unset / -1
```

The first-frame primer/guard must not classify missing source generation or activation as a presentation blocker when ALL are true:

- playback is not playing;
- the current mode allows idle reveal;
- the current mode has a presentation-owned idle scene.

In that state:

- build/publish the idle Spectrum baseline;
- allow non-zero authored scene/bar fade;
- allow the first presentation handoff to complete;
- allow the card to become visibly revealed;
- retain `_waiting_for_fresh_engine_frame=True`;
- do not fabricate source generation/activation;
- do not feed baseline bars into BeatEngine/source state.

On Play:

- keep the existing visible idle scene until replacement is ready;
- accept reactive Spectrum only from a fresh current activation/generation;
- replace the idle scene in place;
- no blank/pop/recreate.

#### Required gate

A production-shaped test must prove **visible presentation**, not merely that `resolve_widget_spectrum_presentation()` was called.

It must assert, through a real widget/event-loop path:

- parent receives a Spectrum frame containing the non-zero idle baseline;
- effective fade/bars fade are not forced to zero;
- first-frame publication completes;
- startup/mode reveal no longer waits for an impossible paused source frame;
- the card/scene reaches visible/revealed state;
- `_waiting_for_fresh_engine_frame` remains true;
- source generation/activation remain unassigned.

A second path must recreate Settings while paused with Spectrum persisted and prove the same visible result.

### Slice B — separate logical readiness from GUI reveal side effects

Still keep the GUI recurring timer as the cadence owner during this slice.

#### Required ownership change

`logical_tick()` must no longer call or transitively reach GUI presentation operations such as:

- `begin_mode_fade_in()`;
- `invalidate_shadow_cache_if_needed()`;
- `apply_pending_mode_transition_layout()`;
- `start_widget_fade_in()`;
- QWidget show/hide/update/geometry;
- QPixmap/QPainter;
- GL/compositor mutation.

Instead the logical half should produce plain-data results/intents, for example:

```text
LogicalStepResult / PresentationIntent
    render_state
    render_revision
    mode_activation_id
    generation
    mode_reveal_ready: bool
    startup_reveal_ready: bool
    source_authority_ready: bool
    optional bounded reason/identity fields
```

The exact type/name is implementation-owned. The contract is not.

The GUI/presentation half consumes that result and performs:

- layout/shadow work;
- card/fade work;
- widget visibility;
- compositor publication;
- GL upload/presentation.

No required handoff may use `getattr(..., None)` or another silent optional lookup. Required interfaces fail loudly in tests/development when missing.

#### Required gates

1. Static/transitive guard: logical worker-callable code owns no QObject/QTimer/QWidget/QPixmap/QPainter/GL side effects.
2. GUI-only presentation methods assert/verify GUI-thread execution in test/debug paths.
3. Production-shaped all-five-mode switch test uses a real widget/event loop and proves the target actually presents/reveals. Do not monkeypatch the fade into a list append and call that “visible.”
4. The known bad worker-wiring commit should fail this bar if tested in an isolated worktree.

### Slice C — qualify and repair the logical scheduler while it remains UNWIRED

Do not infer scheduler health from callback duration.

The current runtime must first prove it can actually service the authored cadence without the GUI or compositor attached.

#### Audit target

The existing deadline loop waits with a timed `threading.Event.wait()` and produced an extraordinarily stable ~64 Hz against an ~90 Hz request while reporting no slow steps.

Audit/fix the wait/deadline mechanism first. A high-resolution deadline sleep or equivalent bounded mechanism is allowed. Busy-spinning is not.

A production visualizer interval is about 11 ms, so shutdown does not require a five-second-interruptible wait contract. Prefer a simple deterministic scheduler over a complicated wake mechanism whose timing quantizes the cadence.

#### Scheduler bar

On the installed Windows/Python class used by SRPSS, run the runtime alone with an 11.11 ms authored interval and a cheap representative step for a meaningful window.

Required:

```text
achieved logical cadence:       >= 88 Hz
ordinary scheduler gaps:        no recurring >33 ms class
skipped deadlines:              <= 2% under scheduler-only load
catch-up bursts:                none
step failures:                  0
shutdown:                       bounded and joined
```

The exact duration can be 10–20 seconds; it must be long enough to expose the previous 64 Hz plateau.

The current test “at least 10 callbacks within 2 seconds” is invalid as a cadence regression bar and must be replaced or supplemented.

If this gate fails, **stop**. Do not wire the worker, do not call the runtime correct, and do not request an installed product run. Fix the scheduler first.

### Slice D — wire ONE authoritative logical cadence owner

Only after A, B and C pass.

Target:

```text
Audio / analysis producer
        |
        v
immutable latest analysis/source snapshot
        |
        v
VisualizerLogicalRuntime
  one standard Python thread
  one monotonic deadline owner
  no Qt / QWidget / QPixmap / GL
  all five logical simulations
  playback target + idle evolution
  activation/generation fencing
        |
        v
single-slot latest immutable render state + revision
        |
        v
GUI/compositor consumer
  presentation readiness/reveal
  card/layout/geometry/fade
  GL upload/shader/presentation
```

After landing there must be exactly one logical clock.

Delete/disable simulation ownership from:

- the recurring visualizer GUI QTimer;
- AnimationManager visualizer ticks;
- hidden fallback timers;
- per-mode logical timers.

Qt timers may remain for actual UI deadlines/fades/lifecycle work. They may not advance visualizer simulation.

The GUI must sample the latest current-generation state. No FIFO. No catch-up. No callback posted to GUI for every logical tick.

### Slice E — close Pause/Play on the new owner

Do not build a separate pause/play architecture before the worker cadence is healthy.

Required behavior:

#### Pause

- logical runtime stays alive;
- mode/card/GL resources stay alive;
- current mode is retained;
- no mode activation/generation churn solely because playback paused;
- logical state promptly begins authored idle evolution;
- BeatEngine may keep capture warm independently;
- no multi-frame simulation freeze.

#### Warm resume

- same logical runtime continues;
- same visualizer/card resources continue;
- warm capture resumes without cold startup staging;
- fresh source gets authority promptly;
- no blank/recreate;
- no visible 40–80 ms logical hole caused by GUI starvation.

If the user-visible hitch remains after worker cadence is healthy, then inspect the edge-specific synchronous work around duplicated wake/source-handoff notifications. Do not pre-emptively layer another debounce/timer over the symptom.

---

## 3. Commit and revert discipline

This project has lost too much time to giant commits and broad reversions.

### One semantic slice per commit

Expected sequence resembles:

1. Spectrum primer/reveal semantics + visible gate;
2. logical readiness / GUI reveal split + real mode-switch gate;
3. scheduler repair + cadence gate;
4. worker ownership wiring + single-clock/lifecycle gates;
5. pause/play edge closure + behavioral gates;
6. docs/status closure.

Do not bundle an entire cadence swap into a commit named after the first symptom it fixed.

### Before reverting anything

State explicitly:

- the exact commit(s) proposed for revert;
- files and semantic behavior those commits own;
- which prerequisite/refactor/fix commits will remain;
- why forward-fixing the bounded defect is less safe than reverting that exact slice.

Do not use “revert the cadence work” as a substitute for understanding which parts are valid.

### A failed slice does not authorize a broad rollback

Fix forward inside that slice or revert only that slice. Retained improvements such as canonical mode capabilities, playback ownership, warmup ownership, or pure logical/runtime modules are not collateral damage unless evidence identifies them as defective.

---

## 4. Evidence and gate discipline

Every important bar must assert a **behavioral end condition**.

Bad bars:

```text
runtime object exists
mailbox revision increased
fade function was invoked
idle baseline resolver was called
10 callbacks happened in two seconds
```

Good bars:

```text
90 Hz owner actually services ~90 Hz
paused Spectrum actually produces visible non-zero presentation
mode switch actually ends with the target presented/revealed
Pause -> Play retains identity and does not create a logical timing hole
worker-callable code cannot reach GUI mutations
retired generation cannot publish
there is only one logical simulation clock
```

Tests are not evidence merely because they are green. A test must be structurally capable of failing on the defect it claims to guard.

---

## 5. Installed acceptance — ONE run after the full P2 slice set

Do not ask the operator to repeatedly exercise intermediate worker states.

After Slices A–E and the relevant suites are green, perform one installed run with the existing diagnostic/performance flags.

Exercise:

1. startup on both displays;
2. Bubble ordinary playback long enough to judge continuous motion and reaction;
3. all five mode switches while playing;
4. switch to Spectrum while paused — card + idle bars must visibly reveal;
5. Settings/recreate while paused on Spectrum — Spectrum remains visibly Spectrum;
6. Play from that state — real Spectrum bars replace idle in place;
7. repeated quick Pause/Play while capture remains warm;
8. one populated Media CUSTOM Cancel;
9. ordinary high-refresh transitions;
10. clean shutdown/resource accounting.

Acceptance is perceptual **and** measured.

Bubble failing the eye test for hitch/flicker is a failure even if average FPS is high.

Required measurement shape:

- authored logical cadence near target rather than a 64–85 Hz service class;
- no recurring ordinary >33 ms logical holes;
- renderer/GPU remains cheap;
- state-to-paint remains healthy;
- no second logical clock;
- no stale-generation publication;
- no mode becomes invisible after a switch;
- Pause/Play no longer produces the characteristic multi-frame visual stall.

---

## 6. After P2 acceptance

Proceed to **P5 physical monitor lifecycle / topology reconstruction**.

Do not let visualizer polishing indefinitely displace the known monitor-off / long-idle / wake lifecycle work.
