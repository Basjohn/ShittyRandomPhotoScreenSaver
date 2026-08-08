# Visualizer Presentation Guardrails

Last updated: 2026-08-08

Read this focused guardrail only when changing visualizer cadence, presentation smoothing, render-state delivery, repaint behaviour, or mode-specific animation timing. The full incident history is in `Docs/Historical_Bugs/R-55_Spectrum_Presentation_Smoothing.md`.

## Accepted Behavioural Baseline

Until the user explicitly approves a newer named build, the accepted Bubble/Spectrum behaviour is:

```text
ff93461685476bd0657aa88312fc2e35e9037880
```

That commit is code-equivalent to the approved executor-restoration checkpoint `4bde89e8e39177dc4dd7b5e64b9ac99256ab9486` and excludes the rejected Spectrum smoothing experiment.

## One Cadence Authority

- Source analysis, mode simulation, presentation-state publication, and GL paint must not become competing clocks.
- Do not add a second recurring timer, repaint loop, paint-derived clock, token budget, cadence cap, or scheduler for visualizer presentation.
- `paintGL()` renders the state it receives. It must not become Spectrum/Bubble simulation or interpolation authority.
- Spectrum smoothing must not request continuation paints independently of the existing authoritative visualizer presentation tick.
- Do not mutate authoritative bar arrays inside `paintGL()` or a render callback.
- Do not derive simulation or presentation time from successful paint acknowledgement.

## Fidelity Rules

- Preserve immediate or demonstrably imperceptible near-immediate attack unless the user explicitly approves a changed attack profile.
- Smoothing may not create held falls followed by abrupt rises, stale targets, generation bleed, or mode-transition residue.
- Presentation-only state must reset on mode, activation, engine generation, bar-count, teardown, and first-frame authority changes.
- Bubble remains completely isolated from Spectrum-only experiments.
- Shared audio-source timing and a mode-owned presentation path are never changed in the same acceptance slice.

## Current Unapproved Spectrum Candidate

The user authorized one isolated adjustable Spectrum presentation experiment after
affected-path temporal hazard lights were added. It is not a new approved baseline:

- `spectrum_visual_smoothing_enabled` defaults to `true` and can disable the filter;
- `spectrum_visual_smoothing` is a `0.00–1.00` strength, default `0.50`;
- interpolation runs only on the existing authoritative UI visualizer tick before GPU
  publication, never inside paint;
- it is symmetric and time-compensated, with a `2–14 ms` time constant (`8 ms` at the
  default), and snaps after a `100 ms` UI stall;
- first-frame, mode, activation, engine generation, bar-count, render-style, strength,
  pause/disable, and teardown boundaries reset or snap presentation state;
- it creates no timer, queue, scheduler, independent update/repaint, source decimation,
  Bubble change, or shared-analysis change.

The versioned temporal trace must remain a hazard light, and installed review must
compare disabled/default/stronger settings against `ff934616`. If the operator sees
delay, flattened transients, pumping, extra churn, or worse Bubble/Spectrum behaviour,
restore checkpoint `3b6082dd` and record the candidate as rejected.

## Required Validation

Before shared-source/cadence work or approval of a presentation candidate:

1. The affected path must have source-to-first-presentation temporal hazard lights; the full stronger package remains mandatory before shared/cross-mode work or baseline replacement.
2. Change one causal boundary only.
3. Compare against the named approved build using the same preset, display route, refresh conditions, and source fixture.
4. Record source publications, presentation publications, update requests, paints, source age, and first-visible timing.
5. Run irregular GUI-stall, transition, pause/resume, mode-switch, and generation-reset cases.
6. Obtain explicit user visual approval.

Unit tests, throughput, average FPS, zero rejected submissions, or more paints do not establish smoother behaviour.

## Stop And Roll Back

If the user reports that Bubble or Spectrum is less smooth, less reactive, less elastic, less reliable, or otherwise worse:

- reject the experiment immediately;
- revert the isolated commit in a new commit;
- restore the exact approved code before investigating alternatives;
- do not retune the failed design in place;
- record the failure in historical documentation;
- strengthen the golden/hazard-light coverage that failed to detect it.
