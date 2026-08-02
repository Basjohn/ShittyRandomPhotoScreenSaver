# R-55 — Spectrum Paint-Local Smoothing Created A Second Cadence

Date: 2026-08-02  
Status: Resolved by exact revert

## Commits

```text
accepted executor restoration: 4bde89e8e39177dc4dd7b5e64b9ac99256ab9486
rejected smoothing experiment:  ebfec397fb2ae0bbc1f3e95c5298c0e7d6ff1db9
exact revert on main:          ff93461685476bd0657aa88312fc2e35e9037880
```

`ff934616` has no file differences from `4bde89e`; it preserves the commit-level rollback point without moving `main` backwards.

## Observed Failure

After the executor-path restoration had made Spectrum significantly better, a Spectrum-only presentation smoothing experiment made it **significantly less smooth** in the installed runtime.

The experiment attempted to preserve zero-latency attack by snapping rises immediately while exponentially smoothing only falling values. It ran inside the GL overlay frame shell and requested another paint while decay remained unfinished.

## Evidence

The supplied installed logs showed the existing authoritative Spectrum state cadence already publishing approximately:

```text
set_state:       977–1000 per 10 seconds
```

With the smoothing experiment active, the overlay additionally reached approximately:

```text
paint:           1417–1544 per 10 seconds
update_requests: 1489–1551 per 10 seconds
```

Stable intervals commonly showed 1000 authoritative state updates but roughly 1479–1544 paints per 10 seconds. The smoothing path therefore introduced about 48–54 extra self-requested paints per second instead of merely improving the existing presentation.

No large CPU error was required for the visual regression. The failure was cadence and behaviour, not simple throughput exhaustion.

## Root Cause

The experiment accidentally created a second presentation cadence:

1. the normal visualizer tick published authoritative Spectrum bars;
2. the GL overlay independently mutated those bars during paint;
3. unfinished decay requested another paint;
4. those local paints ran between and out of phase with authoritative publications.

The asymmetric rule also produced an undesirable motion shape under rapidly changing music:

- falls were repeatedly held/interpolated;
- a later rise snapped immediately;
- the result could feel more stepped despite a higher paint count.

`paintGL()` had become presentation-state authority rather than a consumer of already-authored state.

## Why Tests Missed It

The deterministic tests proved only that:

- first presentation snapped to source;
- rises were numerically immediate;
- falls converged;
- generation changes reset state;
- another update was requested during decay.

Those tests did not reproduce the installed relationship between:

- the existing approximately 100 Hz authoritative `set_state` cadence;
- the additional approximately 50 Hz self-requested paint cadence;
- real Qt/GL paint scheduling;
- fast alternating musical rises and falls;
- operator perception of continuity.

The test that approved continuation paints was therefore authorizing the defect rather than detecting it.

## Correction

The smoothing implementation and its authorizing tests were removed completely in `ff934616`.

The accepted state is the executor-restored, unsmoothed presentation path. Bubble was not changed by either the experiment or the revert.

## Durable Prevention

Future Spectrum smoothing or interpolation must:

- run only on the existing authoritative visualizer presentation tick;
- add no timer, scheduler, paint-derived clock, or self-requested repaint loop;
- never mutate Spectrum bars inside `paintGL()` or a render callback;
- preserve immediate attack unless the user explicitly approves otherwise;
- reset on activation, generation, mode, teardown, and first-frame boundaries;
- remain isolated from Bubble and shared source scheduling;
- compare update, publication, and paint cadence against the approved baseline;
- require stronger goldens first and explicit installed user approval afterward.

More paints are not evidence of smoother motion.
