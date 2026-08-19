# Future Cleanup

Last updated: 2026-08-19

This is deferred debt only. `Current_Plan.md` owns active work.

The mode-general Qt-free visualizer logical runtime is **not** future cleanup anymore; it has been
promoted to active P2 work because the latest installed run meets its entry condition.

---

## 1. Presentation / QRhi diagnostic retirement

After P2 and P5 are accepted:

- [ ] retire QOpenGLWidget-only compositor lifecycle compatibility with no current caller;
- [ ] retire obsolete `aboutToCompose` / `frameSwapped` forensic observers;
- [ ] retire old P4 DWM/no-HUD/present-context scaffolding after evidence is preserved;
- [ ] keep cheap architecture-neutral request-age/dispatch/state-to-paint summaries;
- [ ] retire permanently-zero paint-pending metrics once comparison value is exhausted;
- [ ] retire old GPU-query machinery whose only purpose was the QOpenGLWidget composition boundary;
- [ ] keep bounded sampled `--gpu-timing`.

Diagnostics remain passive and never become cadence control.

---

## 2. Visualizer single-surface legacy cleanup

After the active logical-runtime/idle/edge work is accepted:

- [ ] retire vestigial `SpotifyBarsGLOverlay` show/visibility plumbing after caller proof;
- [ ] retire visualizer-specific legacy ShadowFade readers when compositor fade is sole owner;
- [ ] replace whole-surface edit `grabFramebuffer()` forcing with a narrower one-shot seam;
- [ ] shrink old `_paused_visualizer` compatibility shape after the explicit edit seam is fully
  canonical;
- [ ] retire stale one-update-per-publication counters;
- [ ] remove dead legacy Spectrum-only compositor paths with no production caller;
- [ ] remove redundant QOpenGLWidget/QRhiWidget compatibility imports/helpers;
- [ ] keep one canonical card-pixel cache identity;
- [ ] keep resource deletion independent from visibility/publication state.

No cosmetic rename project while correctness/performance work is active.

---

## 3. Mode-general compute efficiency

After the dedicated logical runtime is accepted, profile the resulting architecture before creating
another scheduler.

If task/Future/executor scaffolding remains materially expensive:

- [ ] design a **mode-general** bounded visualizer compute service;
- [ ] preserve one-in-flight/latest-fresh semantics where applicable;
- [ ] preserve exact dt/events/transients;
- [ ] preserve generation/activation fencing;
- [ ] require all-mode temporal/fidelity goldens;
- [ ] do not resurrect the rejected persistent Bubble lane.

If the in-process Python logical thread later proves materially GIL-starved even after GUI/runtime
waste is controlled:

- [ ] decide between a helper process and a native extension from fresh evidence;
- [ ] prefer the smallest ownership change that preserves the now-clean logical/render-state
  contract;
- [ ] do not pre-emptively rewrite visualizer maths in C/C++.

---

## 4. Test / harness debt

- [ ] fix `tests/test_slide_jitter.py` top-level composition;
- [ ] establish one shared frame-timing harness contract;
- [ ] stabilize the host-sensitive Bubble worker budget oracle without deleting its budget;
- [ ] stabilize paused-AdaptiveTimer timing bars without weakening no-polling;
- [ ] make `tools/perf_integration_harness.py --help` safe and bounded;
- [ ] classify large cross-file/native-exit harness contamination separately from runtime defects;
- [ ] split large slow widget test monoliths while preserving production-shaped coverage.

A helper/stub-call assertion is not sufficient for a production lifecycle seam.

---

## 5. CUSTOM / Edit cleanup

After active Media Cancel and visualizer edit paths pass:

- [ ] weakify edit-shell callbacks where teardown retention remains possible;
- [ ] retire duplicate miniature teardown/replay helpers after caller proof;
- [ ] split `custom_layout_manager.py` only by real ownership;
- [ ] audit corner/anchor scaling UX;
- [ ] tighten broad exception suppression;
- [ ] silence benign disconnect warnings without weakening ownership.

---

## 6. Whole-process resources

After P5:

- [ ] run long warm RAM/private-commit/VRAM slopes;
- [ ] separate bounded cache high-water from monotonic ownership growth;
- [ ] attribute native/driver memory gaps;
- [ ] define repeatable refresh/DPR/display-route/mode comparisons;
- [ ] retain same-machine CPU/GPU usage as the available efficiency proxy.

---

## 7. Repository / compatibility debris

- [ ] remove generated preview debris after clean-checkout proof;
- [ ] collapse deprecated class-global input authority into the current multi-monitor coordinator;
- [ ] retire deprecated Imgur end-to-end;
- [ ] add lightweight repository-hygiene checks;
- [ ] preserve APPDATA/LOCALAPPDATA isolation in tests/tools.

---

## 8. Unrelated backlog

- [ ] Browser GSMTC resolver work;
- [ ] low-pressure Gmail relative-timestamp freshness;
- [ ] Steam settings-hydration/cache consolidation;
- [ ] Steam artwork scaling only after measured ownership/DPR comparison;
- [ ] two-profile Steam credential/privacy validation.

---

## 9. Product backlog

- [ ] true eight-direction widget shadows;
- [ ] first-run source onboarding returning cleanly to RUN;
- [ ] remaining real-runtime CUSTOM edit-shell oracle;
- [ ] visualizer wall-clock -> monotonic audit where still relevant after the logical-runtime move;
- [ ] curated Spectrum source/release mirror reconciliation.

---

## 10. Documentation hygiene

- [ ] keep `Current_Plan.md` active-only;
- [ ] keep phase reports evidence-scoped;
- [ ] retain the 4.7.2 named baseline as rollback evidence until a newer installed run genuinely
  supersedes it;
- [ ] reconcile external agent guardrails when architecture ownership changes;
- [ ] do not create another live roadmap hierarchy.
