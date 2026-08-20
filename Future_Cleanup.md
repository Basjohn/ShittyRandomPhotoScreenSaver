# Future Cleanup

Last updated: 2026-08-20

Deferred debt only. `Current_Plan.md` owns active work.

The dedicated mode-general visualizer logical runtime is **landed architecture**, not future cleanup
and not an unfinished future proposal.

## 1. Presentation / QRhi diagnostic retirement

After P2 and P5 are accepted:

- [ ] retire QOpenGLWidget-only compositor lifecycle compatibility with no caller;
- [ ] retire obsolete compose/frame-swapped forensic observers;
- [ ] retire old DWM/present scaffolding after evidence is preserved;
- [ ] keep cheap architecture-neutral request-age/dispatch/state-to-paint summaries;
- [ ] retire old presentation counters with no comparison value;
- [ ] keep bounded sampled `--gpu-timing`.

Diagnostics remain passive.

## 2. Visualizer single-surface legacy cleanup

After active P2 edge/delivery work is accepted:

- [ ] retire vestigial historical `SpotifyBarsGLOverlay` visibility plumbing after caller proof;
- [ ] retire old visualizer ShadowFade compatibility readers once compositor fade is sole owner;
- [ ] narrow whole-surface edit capture where possible;
- [ ] shrink old paused-visualizer compatibility state after explicit edit seams are canonical;
- [ ] retire stale one-update-per-publication counters;
- [ ] remove dead old Spectrum-only compositor paths;
- [ ] remove redundant QOpenGLWidget/QRhiWidget compatibility imports/helpers;
- [ ] keep one canonical card-pixel cache identity;
- [ ] keep resource deletion independent from visibility.

No cosmetic rename project while correctness/performance is active.

## 3. Post-worker compute efficiency / historical FFT debris

Only after P2 shared GUI/presentation delivery is stable, profile the landed worker architecture.

The old dedicated FFT process is retired architecture and must not be resurrected without new measurement. Current visualizer audio analysis uses bounded ThreadManager compute work with newest-pending/latest-result semantics.

Cleanup-only debris identified in current source:

- [ ] remove stale `ProcessSupervisor` ancestry in visualizer runtime configuration after caller proof;
- [ ] remove the `beat_engine.set_process_supervisor()` delegation that currently targets a nonexistent audio-worker setter;
- [ ] remove the unused `ProcessSupervisor` import/constructor parameter in `SpotifyVisualizerAudioWorker` if no real caller remains;
- [ ] do **not** treat this cleanup as a performance experiment — the failing delegation is caught and is not a steady-state FFT worker.

If task/Future/executor scaffolding later remains materially expensive:

- [ ] design a **mode-general** bounded visualizer compute service only if evidence justifies it;
- [ ] preserve one-in-flight/latest-fresh semantics;
- [ ] preserve exact dt/events/transients;
- [ ] preserve generation/activation fencing including valid zero;
- [ ] require all-mode temporal/fidelity goldens.

If the Python logical runtime later proves materially GIL-starved after shared waste is controlled:

- [ ] compare helper process vs native extension from fresh evidence;
- [ ] preserve the current logical/render-state ownership boundary;
- [ ] do not pre-emptively rewrite visualizer maths in C/C++.

## 4. Logical runtime cleanup

After current P2 correctness closes:

- [ ] reconcile/remove any remaining dead GUI visualizer timer helpers;
- [ ] remove misleading comments that still call GUI recurring timing the normal visualizer owner;
- [ ] audit remaining wall-clock use where a monotonic clock is semantically required.

These are cleanup only if the active plan has not promoted a specific defect.

## 5. Test / harness debt

- [ ] stabilize host-sensitive Bubble worker-budget oracle without deleting its budget;
- [ ] establish one shared frame-timing harness contract;
- [ ] make long Qt/GL harnesses more isolated;
- [ ] keep generation-zero and one-clock gates permanent;
- [ ] retire tests that only protect GUI-timer/separate-surface architecture;
- [ ] fix combined-run contamination flakes that pass in isolation but fail in the
  full suite: `test_media_command_ingress` (one-command-before-lookup),
  `test_visualizer_settings_plumbing::TestCreateTimeRefreshParity`, the
  `test_visualizer_doc_references` trio, and `test_sine_line4_builder_integration`
  (`TestTab` harness missing `media_enabled`); these are shared-state/ordering
  leaks, not product defects;
- [ ] fix the `tools/recovery_evidence_parser.py` `analyze_evidence_source`
  infinite self-recursion that fails `test_recovery_evidence_parser` even in
  isolation.
- [ ] reconcile the isolated unknown-mode fallback failure in
  `TestVisualizerModeBinding::test_load_visualizer_mode_selection_falls_back_when_saved_mode_is_unknown`:
  the test expects canonical `bubble`, while the current binding selects the first
  registry item (`devcurve`); confirm the intended default owner, then align the
  binding and oracle.

A stub-call assertion is not sufficient for a visible/lifecycle seam.

## 6. CUSTOM / Edit cleanup

After active Media Cancel/visualizer edit paths pass:

- [ ] weakify edit-shell callbacks where retention remains;
- [ ] retire duplicate teardown/replay helpers;
- [ ] split large managers only by real ownership;
- [ ] tighten broad exception suppression.

## 7. Whole-process resources / long-soak retention

The 2026-08-20 Full Telemetry Diagnostic soak is preserved in:

```text
Docs/Performance_Evidence/Acceptance-08_20-13_03-Diagnostic-Long-Soak.md
```

After startup/warmup, that diagnostic shape showed approximate slopes of:

```text
main USS             +29 MB/hour
main private commit  +90 MB/hour
app handles          +15/hour
```

while threads and GL-resource counts remained essentially flat and pre-wake 60 Hz cadence did not degrade with age.

Do **not** call this a production leak from one Full Telemetry run.

Deferred sequence:

- [ ] repeat a long soak with ordinary/light telemetry;
- [ ] compare directly against Full Telemetry Diagnostic;
- [ ] only if the slope survives, separate cache/allocator/native/Python ownership;
- [ ] distinguish cache high-water from monotonic ownership growth;
- [ ] attribute native/driver memory gaps only after the lighter control;
- [ ] keep memory retention separate from the physical-presentation architecture decision unless evidence correlates them.

Monitor-off/wake itself is no longer a cleanup target from this run; it remains a parity/regression gate for any future presenter.

## 8. Repository / compatibility debris

- [ ] remove generated preview debris after clean-checkout proof;
- [ ] collapse deprecated class-global input authority;
- [ ] retire deprecated Imgur;
- [ ] add lightweight repository-hygiene checks.

## 9. Unrelated backlog

- [ ] Browser GSMTC resolver work;
- [ ] low-pressure Gmail relative timestamp freshness;
- [ ] Steam settings-hydration/cache consolidation;
- [ ] Steam artwork scaling after measured DPR/ownership comparison;
- [ ] Steam credential/privacy validation.

## 10. Product backlog

- [ ] true eight-direction widget shadows;
- [ ] first-run source onboarding;
- [ ] remaining real-runtime CUSTOM edit-shell oracle;
- [ ] curated Spectrum source/release mirror reconciliation.

## 11. Documentation hygiene

- [ ] keep `Current_Plan.md` active-only;
- [ ] keep current owner docs synchronized with landed architecture;
- [ ] keep phase reports/Historical_Bugs evidence-scoped;
- [ ] retain named baselines as rollback evidence until genuinely superseded;
- [ ] do not create another live roadmap hierarchy.
