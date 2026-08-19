# P2 Behavioral Gates

Date: 2026-08-19  
Purpose: prevent another all-green suite from certifying a visibly broken visualizer.

A gate is valid only if the defect it names can make that gate fail.

---

## Gate 1 — Spectrum paused presentation is actually visible

### Regression being guarded

Spectrum's idle baseline resolver can run while the first-frame primer still forces effective fade to zero because no authoritative source generation/activation exists while paused.

### Required production-shaped path

```text
playing mode
-> Pause
-> switch to Spectrum
-> no fresh engine frame is available
-> Spectrum presentation-owned idle baseline is produced
-> first-frame guard permits idle presentation
-> card + baseline visibly reveal
```

Assert all of:

- mode is Spectrum;
- playback is paused;
- presentation-owned baseline contains non-zero values;
- the parent/compositor receives that Spectrum frame;
- effective scene fade > 0 during/after reveal;
- effective bars fade > 0 during/after reveal;
- first presentation handoff completes;
- scene/card reaches revealed/visible state;
- `_waiting_for_fresh_engine_frame` remains true;
- source generation/activation remain unset;
- no fake engine generation is created.

### Settings continuation

```text
paused visible Spectrum
-> Settings/recreate
-> persisted Spectrum restored
-> no source available
-> visible Spectrum card + idle baseline returns
```

Do not count “resolver called” as pass.

---

## Gate 2 — every mode switch ends in real presentation

### Regression being guarded

Worker logical code reached GUI fade/layout operations off-thread. Earlier tests monkeypatched reveal functions and asserted only that a function was invoked.

### Required path

For each target:

```text
Bubble
Spectrum
Sine
Oscilloscope
DevCurve
```

Use a real `SpotifyVisualizerWidget`/real parent presentation stub or compositor-facing integration harness with a running Qt event loop.

Assert:

- target mode activation completes;
- at least one target-mode frame is accepted by the parent;
- target scene fade becomes non-zero;
- target reaches revealed/visible state;
- old mode does not remain the presented mode;
- no thread-affinity exception is swallowed.

Run both playing and paused where the mode contract allows idle reveal.

A monkeypatched `start_widget_fade_in()` that merely appends `"fade"` to a list is not this gate.

---

## Gate 3 — scheduler cadence means actual cadence

### Regression being guarded

The worker requested ~90 Hz but installed execution locked near 64 Hz with ~29% skipped deadlines while the unit suite passed.

### Harness

Run `VisualizerLogicalRuntime` unwired from Qt/compositor at:

```text
interval = 1 / 90 s
window   = 10–20 s
step     = cheap representative logical callable
```

Collect every serviced timestamp and deadline skip.

### Pass

```text
achieved rate               >= 88 Hz
skipped deadline fraction   <= 2%
p95 inter-step gap          close to authored interval
recurring >33 ms gaps       none under scheduler-only load
catch-up burst              none
step failures               0
join                        succeeds
```

Use a tolerant platform-aware upper tail rather than requiring impossible nanosecond precision. The purpose is to reject the 64 Hz class decisively.

### Invalid substitute

```text
assert callbacks >= 10 within 2 seconds
```

That would pass at 5 Hz and proved nothing about a 90 Hz owner.

---

## Gate 4 — logical code cannot reach GUI mutation

Build a call-boundary guard around every function reachable from the worker step.

At minimum fail if worker-callable code reaches:

- QObject/QTimer ownership;
- QWidget show/hide/update/geometry;
- QPixmap/QPainter;
- mode fade execution;
- shadow/layout mutation;
- compositor/GL mutation.

In test/debug, GUI-only functions should assert they are running on the GUI thread.

The test must fail loudly rather than rely on production broad `except` handlers.

---

## Gate 5 — required presentation handoffs are not optional

Regression:

A deleted `_request_logical_present` method was obtained through optional `getattr`, silently producing logical work with zero presentation.

Required cross-boundary methods/interfaces must be explicit and test-covered.

Assert that removing/omitting the handoff fails immediately rather than running a zero-frame product.

---

## Gate 6 — exactly one logical clock after wiring

After worker landing, inspect live runtime ownership and source code/runtime registrations.

Assert:

- one `VisualizerLogicalRuntime` is live for the generation;
- recurring GUI timer does not call logical simulation;
- AnimationManager does not call logical simulation;
- no fallback/per-mode logical timer exists;
- pause/play does not create another logical runtime;
- mode switch does not create a second concurrent logical runtime;
- retirement joins old runtime before replacement publishes.

---

## Gate 7 — Pause/Play preserves identity and cadence

### Pause -> warm Play

Exercise quick toggles inside the existing capture keepalive window.

Assert:

- logical runtime identity is unchanged;
- mode activation identity is unchanged unless a real mode change occurred;
- card/presentation resource identity is retained;
- capture may transition to warm hold/resume independently;
- no cold startup stage is entered;
- logical cadence continues across the edge;
- no recurring >33 ms logical hole is introduced by the playback edge itself.

The visible-state debounce must remain absent.

---

## Gate 8 — Bubble fidelity and perceptual smoothness

Automated bars protect mechanics but do not replace the eye test.

Before installed acceptance, preserve existing Bubble fidelity/golden tests for:

- trajectories;
- event/transient consumption;
- visual-only smoothing response;
- elasticity/motion parameters;
- source reaction strength/latency.

Do not “improve” smoothness by lowering source cadence or applying extra audio smoothing.

Installed acceptance fails if Bubble visibly hitches/flickers even when average presentation FPS looks healthy.

---

## Gate 9 — stale generation cannot reveal or publish

Exercise:

```text
old generation logically ready
-> retirement begins
-> replacement generation starts
-> delayed old completion arrives
```

Assert old state cannot:

- enter latest-state mailbox for the new generation;
- trigger a reveal;
- release a new-generation hold;
- mutate current GUI/GL presentation.

---

## Gate 10 — known-bad validation

Where practical, use an isolated git worktree to validate that the new guards reject the known bad architecture without disturbing `main`.

Useful known-bad target:

- `a6a423bc...` — worker wiring state that left mode-reveal GUI work reachable from the logical thread.

Expected:

- real mode-switch presentation/thread-affinity gate fails there;
- current/fixed source passes.

The scheduler cadence gate should also reject any runtime implementation that reproduces the installed ~64 Hz plateau.

---

# Final installed acceptance script

Run only after the P2 implementation gates are green.

Exercise in one session:

1. startup both displays;
2. Bubble playing for perceptual judgement;
3. all mode switches;
4. Pause while Bubble/another self-animated mode is active;
5. quick Play/Pause toggles inside warm-capture grace;
6. Pause -> switch to Spectrum -> confirm visible static idle bars;
7. Settings -> return while still paused -> confirm visible Spectrum persists;
8. Play -> real Spectrum bars take over without blanking;
9. switch out/in again;
10. populated Media CUSTOM Cancel;
11. ordinary transitions;
12. clean exit.

Collect existing perf/GPU/viz logs.

Do not accept a test report that substitutes green unit counts for the operator-visible results above.
