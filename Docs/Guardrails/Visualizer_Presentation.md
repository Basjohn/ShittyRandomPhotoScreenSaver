# Visualizer Presentation Guardrails

Last updated: 2026-08-02

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

- Preserve immediate attack unless the user explicitly approves a changed attack profile.
- Smoothing may not create held falls followed by abrupt rises, stale targets, generation bleed, or mode-transition residue.
- Presentation-only state must reset on mode, activation, engine generation, bar-count, teardown, and first-frame authority changes.
- Bubble remains completely isolated from Spectrum-only experiments.
- Shared audio-source timing and a mode-owned presentation path are never changed in the same acceptance slice.

## Required Validation

Before any future visualizer presentation optimization:

1. The stronger approved goldens in `Current_Plan.md` must already exist.
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
