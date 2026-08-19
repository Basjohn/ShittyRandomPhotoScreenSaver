# Future Cleanup

Last updated: 2026-08-19

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

## 3. Post-worker compute efficiency

Only after P2 shared GUI/presentation delivery is stable, profile the landed worker architecture.

If task/Future/executor scaffolding remains materially expensive:

- [ ] design a **mode-general** bounded visualizer compute service if evidence justifies it;
- [ ] preserve one-in-flight/latest-fresh semantics;
- [ ] preserve exact dt/events/transients;
- [ ] preserve generation/activation fencing including valid zero;
- [ ] require all-mode temporal/fidelity goldens;
- [ ] do not resurrect the rejected persistent Bubble lane.

If the Python logical runtime later proves materially GIL-starved after shared waste is controlled:

- [ ] compare helper process vs native extension from fresh evidence;
- [ ] preserve the current logical/render-state ownership boundary;
- [ ] do not pre-emptively rewrite visualizer maths in C/C++.

## 4. Logical runtime cleanup

After current P2 correctness closes:

- [ ] reconcile/remove any remaining dead GUI visualizer timer helpers;
- [ ] remove misleading comments that still call GUI recurring timing the normal visualizer owner;
- [ ] make the `wake()` API semantics exactly match the wait implementation without reintroducing
  the old coarse timed-wait scheduler defect;
- [ ] audit remaining wall-clock use where a monotonic clock is semantically required.

These are cleanup only if the active plan has not promoted a specific defect.

## 5. Test / harness debt

- [ ] stabilize host-sensitive Bubble worker-budget oracle without deleting its budget;
- [ ] establish one shared frame-timing harness contract;
- [ ] make long Qt/GL harnesses more isolated;
- [ ] keep generation-zero and one-clock gates permanent;
- [ ] retire tests that only protect GUI-timer/separate-surface architecture.

A stub-call assertion is not sufficient for a visible/lifecycle seam.

## 6. CUSTOM / Edit cleanup

After active Media Cancel/visualizer edit paths pass:

- [ ] weakify edit-shell callbacks where retention remains;
- [ ] retire duplicate teardown/replay helpers;
- [ ] split large managers only by real ownership;
- [ ] tighten broad exception suppression.

## 7. Whole-process resources

After P5:

- [ ] long warm RAM/private-commit/VRAM slopes;
- [ ] separate cache high-water from monotonic ownership growth;
- [ ] attribute native/driver memory gaps;
- [ ] repeatable refresh/DPR/display-route/mode comparisons.

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
