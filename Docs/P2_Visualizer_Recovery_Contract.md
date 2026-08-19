# P2 Visualizer Recovery Contract

Status: binding implementation contract for the current P2 recovery round  
Date: 2026-08-19

This document defines the ownership boundary that must exist before the visualizer logical cadence can move off the GUI thread safely.

---

## 1. Product invariant

The visualizer must feel smooth **and** reactive.

“Smooth” means continuous-looking authored motion without visible hitch, flicker, freeze or pacing holes. It does not authorize temporal filtering of the audio/source merely to hide bad scheduling.

“Reactive” means source changes and transients retain low latency and authored strength. It does not authorize a smoother-looking but delayed/flattened response.

Bubble is the strongest perceptual canary because continuous positional movement exposes cadence holes immediately. Bubble is not a special lower-fidelity mode and must not receive mode-specific cadence cuts.

---

## 2. Ownership table

| Concern | Logical runtime | Audio/analysis service | GUI/compositor |
|---|---:|---:|---:|
| monotonic logical deadline/dt | YES | NO | NO |
| playback target for simulation | YES | input | UI/provider source |
| source snapshot consumption | YES | publishes | NO |
| mode simulation | YES | NO | NO |
| visual-only motion smoothing | YES | NO | NO |
| envelopes/transients/events | YES | publishes inputs | NO |
| idle logical evolution | YES | NO | NO |
| immutable render-state construction | YES | NO | NO |
| source freshness as plain data | YES | publishes identity | consumes result only |
| QWidget show/hide/update | NO | NO | YES |
| QPixmap/QPainter | NO | NO | YES |
| layout/geometry mutation | NO | NO | YES |
| card/shadow raster ownership | NO | NO | YES |
| reveal/fade execution | readiness only | NO | YES |
| GL/QRhi/shader/resource mutation | NO | NO | YES |
| physical presentation cadence | NO | NO | YES |
| capture lifetime / keepalive | NO | YES | NO |

No object crossing into the logical runtime may provide an accidental backdoor to GUI or GL state.

---

## 3. Plain-data boundary

The logical runtime may receive only immutable/plain-data inputs or thread-safe snapshot readers whose contract is explicitly non-Qt.

A logical step produces one immutable latest state, conceptually:

```text
VisualizerRenderState
    runtime_generation
    mode_activation_id
    mode
    logical_timestamp
    authored visual state
    source identity/freshness
    presentation readiness flags
    render revision
```

The exact dataclass names and field packing are implementation details.

### Required readiness distinction

Do not overload “fresh source” to mean “allowed to show anything.”

At minimum the architecture distinguishes:

```text
presentation_ready
reactive_source_ready
```

These may differ.

---

## 4. Mode idle capability matrix

One canonical capability owner answers these questions for every subsystem.

| Mode | Idle reveal | Idle self-animation | Presentation-owned idle scene | Fresh source required for reactive playback |
|---|---:|---:|---:|---:|
| Bubble | YES | YES | NO | NO |
| Spectrum | YES | NO | YES | YES |
| Sine | YES | YES | NO | NO |
| Oscilloscope | YES | YES | NO | NO |
| DevCurve | YES | YES | NO | NO |

No subsystem may reintroduce its own hard-coded subset.

### Spectrum paused contract

Paused Spectrum is the important mixed state:

```text
presentation_ready = true
reactive_source_ready = false
waiting_for_fresh_engine_frame = true
source generation = absent
source activation = absent
```

Its static low baseline is presentation-owned. It is not fake audio and must not be written into BeatEngine/source generation state.

The first-frame guard/primer must permit this presentation state to become visible.

On Play, the visible idle state may remain until a current-generation/current-activation real source frame is ready, then real Spectrum bars replace it in place.

---

## 5. Reveal ownership contract

The failed cadence attempt proved that mode readiness and mode reveal are currently entangled.

### Logical side may decide

- target mode is logically initialized;
- target activation/generation is current;
- required logical/source prerequisites are ready;
- a reveal is now allowed.

### GUI side must execute

- shadow invalidation;
- pending mode-transition layout;
- widget/card visibility;
- fade start/progress;
- geometry/cache work;
- compositor publication;
- GL work.

A worker must never transitively call `begin_mode_fade_in()` or an equivalent GUI mutation chain.

### Required interface rule

A required cross-boundary operation is explicit.

Forbidden for mandatory behavior:

```python
callback = getattr(widget, "required_method", None)
if callback:
    callback(...)
```

That pattern previously converted a deleted presentation handoff into silent zero-frame output.

If the boundary is required, absence is a test/development failure.

---

## 6. Logical scheduler contract

One thread owns one monotonic deadline sequence.

It must:

- target the authored logical cadence (~90 Hz by current default);
- skip genuinely missed deadlines rather than replaying backlog;
- never run catch-up bursts;
- never alter authored dt/event behavior merely to improve a benchmark;
- publish only the latest state;
- stop and join with its runtime generation;
- reject stale-generation publication.

### Scheduler health is measured by delivery, not callback body time

The failed worker run showed ~64 Hz with ~29% deadlines skipped and `slow_steps=0`.

Therefore these are insufficient:

- `slow_steps == 0`;
- thread is alive;
- callback count is non-zero;
- clean join;
- mailbox publication exists.

### Scheduler qualification bar

At 11.11 ms requested cadence with a cheap representative step over 10–20 seconds:

```text
achieved cadence             >= 88 Hz
skipped deadline fraction    <= 2%
recurring >33 ms gaps        none under scheduler-only load
catch-up bursts              none
failures                     0
joined                       true
```

The current timed `Event.wait()` deadline wait is a prime audit target because the installed failure is an unusually stable ~64 Hz plateau. Treat this as a candidate mechanism, not a conclusion, until the corrected scheduler passes the bar on the installed platform.

Busy spinning is prohibited.

---

## 7. One-clock contract

After worker wiring:

- `VisualizerLogicalRuntime` is the sole simulation cadence owner;
- the old recurring GUI visualizer timer no longer advances logical state;
- AnimationManager does not advance logical state;
- no hidden fallback/per-mode timer advances logical state.

Qt timers may continue to own true UI/lifecycle/fade deadlines.

Physical presentation may run at display cadence and sample the freshest logical revision. Presentation does not become another simulation clock.

---

## 8. Latest-state publication contract

The handoff is one-slot/latest-wins.

Allowed:

```text
logical state N
logical state N+1 replaces N before GUI samples
GUI later samples N+1
```

Forbidden:

- FIFO render queues;
- pending-until-paint backpressure;
- replay/catch-up frames;
- GUI callback posted for every logical step;
- logical time derived from how often paint happened.

Every authored source/event reaction must be integrated into logical state before that state may be superseded.

---

## 9. Pause/Play contract

Playback state and capture lifetime are separate owners.

### Pause

- playback target changes promptly;
- logical runtime remains alive;
- card/GL/runtime identity remains alive;
- no generation/activation rebuild solely because playback paused;
- authored idle motion begins promptly;
- capture may remain warm for the engine-owned grace period.

### Warm Play

- same logical runtime continues;
- same card/resources continue;
- capture can warm-resume;
- fresh source authority is accepted promptly;
- no cold startup/reveal path unless an actual lifecycle event requires it.

Do not reintroduce a visualizer pause debounce to absorb provider wobble.

---

## 10. Error visibility contract

The previous failure was amplified by broad exception handlers hiding thread-affinity errors.

For the logical/presentation boundary:

- GUI-only entry points should assert GUI-thread execution in test/debug paths;
- required handoffs should fail loudly when absent;
- a worker exception that violates ownership must be visible in tests/logging;
- production may remain fail-safe, but the test environment must not convert architecture violations into a green suite.

---

## 11. Lifecycle contract

Runtime generation owns:

- logical worker thread;
- mailbox/current state;
- source/activation fencing.

Retirement order:

```text
stop new logical work
-> quiesce source producers as required
-> join logical runtime
-> reject/clear stale publication
-> retire GUI/GL generation
```

CUSTOM Edit/Cancel, Settings recreation, shutdown and later P5 topology rebuild must use this same ownership model rather than one-off restart shortcuts.
