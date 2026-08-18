# Future Cleanup

Last updated: 2026-08-18

This file is **not an alternate active plan**. `Current_Plan.md` owns execution order.

Promote an item only when current evidence makes it causal or when P2/P5 closure reaches its
retirement boundary. Active correctness/performance/lifecycle work does not get parked here merely
because it is difficult.

The obsolete duplicate roadmap files identified during the 2026-08-18 architecture reconciliation
have already been deleted. Do not restore or recreate them.

---

## 1. QRhi / Presentation Diagnostic Retirement

After P2/P4 installed acceptance is stable:

- [ ] retire QOpenGLWidget-only compositor lifecycle compatibility with no current caller;
- [ ] retire old `aboutToCompose` / `frameSwapped` observer code once no rollback/evidence path needs it;
- [ ] retire old P4 DWM/stage/no-HUD/present-context forensic scaffolding after accepted evidence is durable;
- [ ] keep cheap architecture-neutral request-age/dispatch/event-loop/state-to-paint summaries;
- [ ] retire permanently-zero paint-pending admission metrics after comparison value is exhausted;
- [ ] retire GPU-query machinery whose sole purpose was the old QOpenGLWidget composition boundary;
- [ ] keep ordinary sampled `--gpu-timing` with non-nesting same-context semantics;
- [ ] retain `--diag-pair-warm-finish` only while its exact hidden pair-warm mechanism exists.

Diagnostics remain passive. Cleanup never changes cadence/admission to make counters prettier.

---

## 2. Visualizer Single-Surface Legacy Cleanup

After current P2/CUSTOM/cadence acceptance:

- [ ] retire vestigial `show()`/visibility plumbing in `SpotifyBarsGLOverlay` after caller proof;
- [ ] retire visualizer-specific legacy `ShadowFadeProfile` readers if compositor fade is sole owner;
- [ ] replace the forced whole-surface `grabFramebuffer()` used only to drive one edit capture with a narrower one-shot render seam;
- [ ] shrink `_paused_visualizer` tuple/state once the new explicit edit suspend/resume contract lands;
- [ ] retire old one-update-per-publication counters that no longer represent physical presentation;
- [ ] remove dead legacy compositor Spectrum-only visualizer seam if no production caller remains;
- [ ] remove redundant visualizer QOpenGLWidget/QRhiWidget compatibility imports/helpers;
- [ ] keep one canonical card-pixel cache identity;
- [ ] keep card/visualizer resource deletion independent from visible/publication state.

Do not rename `SpotifyBarsGLOverlay` merely for cosmetic purity during active work.

---

## 3. Hardware-Acceleration Contract Cleanup

Accelerated presentation is required for the modern runtime.

- [ ] retire obsolete non-accelerated compositor/visualizer paths after frozen/runtime caller proof;
- [ ] retire or redefine any `display.hw_accel` option that promises unsupported software visualizer behaviour;
- [ ] do not replace it with CPU/QPainter visualizer rendering.

---

## 4. Test / Harness Debt

- [ ] fix `tests/test_slide_jitter.py` so the top-level actually composes;
- [ ] establish one shared frame-timing harness contract;
- [ ] stabilize host-scheduling-sensitive Bubble worker budget tests without deleting the budget;
- [ ] stabilize paused-AdaptiveTimer no-polling timing bar without weakening no-polling;
- [ ] make `tools/perf_integration_harness.py --help` safe and add bounded scenario/duration/cleanup controls;
- [ ] verify harnesses that instantiate `SpotifyBarsGLOverlay` use logical-owner semantics;
- [ ] classify unrelated full-suite/native-exit clusters without weakening runtime contracts;
- [ ] split large slow widget test monoliths while retaining integrated hydration/save coverage.

A test that only asserts a helper/stub was called is not sufficient evidence for a production
lifecycle seam.

---

## 5. CUSTOM / Edit Hardening After Active Integration

Only after the active edit suspend/resume and cross-display runtime paths pass:

- [ ] weakify edit-shell live-geometry callbacks where teardown retention remains possible;
- [ ] retire duplicate CUSTOM miniature teardown/replay helpers after caller proof;
- [ ] split `custom_layout_manager.py` by real ownership only if maintenance still benefits;
- [ ] audit corner/anchor scaling UX;
- [ ] tighten broad exception suppression that can hide persistence/session failure;
- [ ] silence benign disconnect warnings without weakening disconnect ownership.

---

## 6. P6 Whole-Process Resource / Efficiency Follow-Up

This work never authorizes fidelity or refresh reduction.

- [ ] run long post-warm-up RAM/private-commit/VRAM slopes after P5;
- [ ] separate bounded cache high-water from monotonic ownership growth;
- [ ] attribute native/driver memory gaps;
- [ ] deepen task snapshots only if existing snapshots cannot answer a real owner question;
- [ ] define repeatable hardware/profile comparison using refresh/DPR/display route/transition/mode;
- [ ] retain same-machine CPU/GPU usage as the available proxy for weaker hardware.

If per-step Bubble executor/Future churn is later proven materially expensive:
- [ ] design a **new** bounded compute mechanism from accepted one-in-flight semantics;
- [ ] do not reactivate the rejected persistent Bubble lane;
- [ ] require exact trajectory/event/generation goldens.

If GUI-timer starvation remains after known waste removal:
- [ ] consider extracting a Qt-free logical visualizer runtime with one dedicated cadence authority;
- [ ] publish immutable latest state to GUI/compositor;
- [ ] never move QWidget/QPixmap/GL mutation off its legal owner;
- [ ] require full all-mode fidelity locks before implementation.

These are legitimate future architecture targets, not forbidden because they are larger refactors.

---

## 7. Repository / Compatibility Debris

- [ ] remove generated preview debris after clean-checkout recreation proof;
- [ ] collapse deprecated class-global input authority into the existing multi-monitor coordinator incrementally;
- [ ] retire deprecated Imgur end-to-end rather than repairing it;
- [ ] add lightweight repository-hygiene checks for generated debris/credential-shaped values/default drift;
- [ ] preserve APPDATA/LOCALAPPDATA isolation in tests/tools;
- [ ] keep `rendering/gl_compositor_pkg` documented as active code, not deletion debt.

---

## 8. Unrelated / Unvalidated Work

Keep separate from P2/P5:

- [ ] Browser GSMTC resolver changes;
- [ ] low-pressure Gmail relative-timestamp freshness policy without per-minute repaint;
- [ ] Steam settings-hydration/cache consolidation;
- [ ] Steam artwork scaling work only after measured ownership and DPR-sharp comparison;
- [ ] two-profile Steam credential/privacy validation.

---

## 9. Product Backlog

- [ ] true eight-direction widget shadows;
- [ ] first-run source onboarding re-entering normal RUN after Settings closes with valid sources;
- [ ] remaining real-runtime CUSTOM edit-shell oracle;
- [ ] visualizer wall-clock -> monotonic audit only with explicit clock-jump coverage;
- [ ] curated Spectrum source/release mirror reconciliation through canonical preset authority;
- [ ] old transition/visualizer dt-gap correlation only if a pathology survives current architecture/P5.

---

## 10. Documentation Hygiene

- [ ] keep `Current_Plan.md` pruned to active work;
- [ ] keep phase reports as dated evidence, not live implementation maps;
- [ ] periodically remove stale references to deleted roadmap files;
- [ ] reconcile any external Claude/Opus guardrail skill with current repository guardrails whenever the architecture epoch changes.

Do not create another live roadmap hierarchy.
