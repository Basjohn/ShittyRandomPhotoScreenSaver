# 05 — Visualizer Fidelity Contract

## Why this contract exists

The donor architecture passed logical or structural checks while visibly damaging:

- reactivity;
- Spectrum height/shape;
- Bubble responsiveness;
- smooth elasticity;
- motion continuity;
- perceived timing.

Once infrastructure and simulation changes are mixed, the original feel is difficult to recover. Therefore visualizer behavior is a protected contract, not an informal preference.

## Protected qualities

All supported modes must preserve:

- response to low, medium, and strong beats;
- low-energy movement instead of artificial flatness where baseline moved;
- attack speed;
- peak amplitude;
- decay speed and curve;
- overshoot;
- spring/elastic return;
- inter-frame continuity;
- spatial distribution;
- stable behavior across frame-rate variation;
- correct behavior after a temporary presentation stall;
- mode-specific personality.

### Spectrum-specific protections

- Bars must not collapse into a visually flat band under ordinary music.
- Peak response must remain proportional to baseline within tolerance.
- Attack must remain immediate enough to feel tied to the beat.
- Decay must not become stepped or synchronized to compositor paints.
- Frequency-band mapping and normalization must not silently change.
- A dropped paint may skip an intermediate display state but may not alter the simulation response.

### Bubble-specific protections

- Bubbles must retain baseline elasticity and rebound.
- Motion must not become overdamped.
- Beat impulses must remain visible.
- Settling time must remain within baseline tolerance.
- Position integration must use elapsed simulation time correctly.
- A presentation pause must not produce a burst of repeated fixed-step updates or a frozen state followed by a teleport unless that is the documented baseline behavior.

## Deterministic replay system

Create a development harness that feeds timestamped audio-analysis frames into the actual visualizer simulation code.

Required fixtures:

1. silence;
2. single isolated impulse;
3. repeating beat at several tempos;
4. sustained bass;
5. sustained treble;
6. broadband noise;
7. gradual volume ramp;
8. sudden volume change;
9. real representative music excerpt features;
10. irregular input cadence;
11. simulated UI-presentation stalls;
12. mode switch and visibility toggle.

Store feature data rather than copyrighted audio where possible.

## Golden outputs

For each mode and fixture, record time series of the meaningful logical state:

- normalized band values;
- bar heights;
- peak markers;
- bubble positions;
- bubble velocities;
- radii;
- force/impulse values;
- smoothing accumulator;
- mode state;
- timestamps.

The golden output must be generated from `00edb57` before the simulation code is altered.

## Quantitative fidelity metrics

Record where applicable:

- input-to-first-response latency;
- time to peak;
- peak magnitude;
- attack slope;
- half-life or decay constants;
- overshoot ratio;
- settling time;
- integrated energy over a fixed window;
- cross-correlation lag against baseline;
- RMS state error;
- maximum state error;
- percentage of frames within tolerance;
- number of discontinuities;
- state derivative spikes.

Numerical equality is not always appropriate. Per-mode tolerances must be documented.

## Temporal separation test

Run the same input with presentation opportunities at:

- 30 Hz;
- 60 Hz;
- 90 Hz;
- 120 Hz;
- irregular cadence;
- deliberate 100 ms, 250 ms, and 500 ms paint stalls.

The logical visualizer state at the same simulation timestamp must remain equivalent within tolerance.

This test prevents presentation scheduling from changing visualizer feel.

## Manual review requirement

Quantitative tests cannot fully measure “feel.”

For every architecture phase touching visualizer data flow:

- record synchronized baseline and candidate output;
- show identical input and viewport;
- include normal speed and slow-motion review;
- compare Spectrum and Bubble at minimum;
- review after Settings/Edit;
- review during idle and background load.

Manual rejection overrides passing averages.

## Change declaration

Any intentional change to visualizer behavior requires a completed:

```text
templates/VISUALIZER_CHANGE_DECLARATION.md
```

It must state:

- which behavior changes;
- why;
- which modes;
- before/after evidence;
- whether golden outputs are intentionally regenerated;
- user approval.

Infrastructure work must not regenerate goldens.

## Prohibited fidelity shortcuts

Do not:

- lower update rate merely to reduce CPU;
- clamp amplitudes to hide spikes without validating feel;
- increase damping to conceal frame gaps;
- average more samples to hide scheduling jitter;
- tie simulation step to paint completion;
- treat “no crash” or “higher FPS” as fidelity;
- replace elapsed-time integration with frame-count assumptions;
- allow multiple catch-up steps to create visible bursts without a defined policy;
- silently drop beat impulses when publication is coalesced.

## Correct coalescing model

Coalescing may discard intermediate **render snapshots**.

It may not discard logical audio input or alter simulation integration.

A safe design is:

1. audio/input events enter a bounded simulation path;
2. simulation advances according to timestamps;
3. latest immutable render state replaces prior unpublished render state;
4. compositor draws the latest state when possible.

## Fidelity gate

A phase fails if any of the following occurs:

- Spectrum is visibly flatter;
- Bubble is less reactive or elastic;
- response latency grows beyond tolerance;
- decay or settling changes unexpectedly;
- motion becomes stepped;
- background load changes logical state behavior;
- Settings/Edit restart changes mode state unexpectedly;
- manual review reports a clear loss of feel.

Do not patch these symptoms with compositor flags. Revert and find the architectural cause.
