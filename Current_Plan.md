# SRPSS | Current Plan

Active development work only. Implemented features keep their open physical acceptance in their own reference
(`Docs/Reference/Guided_Setup.md`, `Docs/Reference/Feeds.md`, `Docs/Reference/Transitions.md`); closed plans and
audits are historicalised (`Docs/Historical_Bugs/R-100_...`, `R-101_...`).

## 3D scene foundation | operator-promoted 2026-09-29

Detail, rewards, risks and performance hazards per slice: `Docs/Future_Work/3D_Scene_Foundation.md`. Work in this
order; commit and push each slice; tests and measurements before looks change.

- [ ] **Motion Trails CPU:** each ghost re-sets its program's uniforms through PyOpenGL (+0.5-1.0 ms CPU per frame at 1440p when On). Set the shared uniforms once per trail pass and vary only time and fade per ghost; measure CPU submit before and after.

## Memory and handles | open development items

- [ ] **ImageWorker lean entry (R-99).** The ImageWorker re-imports the whole app graph on `spawn` (~1,060 modules). A lean worker entry could save ~100 MB resident, but it must be validated under Nuitka multiprocessing first.
- [ ] **Scaled prefetch stalls the Visualizer after most transitions (was Watch; material as of 2026-09-29).** On the Visualizer display, 15 of 27 transitions (11 of 16 in the 2026-09-22 trace, so not new) end with a Visualizer draw of 18-43 ms about 230 ms after the run, when prefetch resumes. PySide's `QImage.scaled` and `convertToFormat` hold the GIL for their whole call (11 ms and 8 ms on a 4948x2935 photo; the fill step holds it in 7 ms chunks), so each of the render thread's GL calls waits its turn and the draw stretches; `QImage(path)` decoding releases the GIL (103 ms, no wait). The logical clock never shows it (78 of ~64,000 steps skipped), which is why the old measure missed it. Move the derivative off the GIL with identical output (for example into the ImageWorker process), then re-measure post-transition Visualizer draws in the frame trace.
- [ ] **`--usage` sampler stalls rendering every 15 s (diagnostics only).** Its collection holds the GIL for 13-39 ms (`collect_ms`): 31 of the 164 late Visualizer frames in the 2026-09-29 run, on both displays. It inflates any deviation measured with `--usage`; collect without holding the GIL, or exclude its beat when judging.
- [ ] **Gmail refresh adds ~1.5 main-process handles per refresh.** The +18–25 handles/h slope tracks the Gmail cadence. Classify the type with `--handle-attribution`, then fix at the owner.

## Settings geometry | open development items

- [ ] **Widgets-tab position warnings use stale size estimates.** `ui/widget_stack_predictor.py` (QWidget-era formulas; e.g. Reddit 350 px wide against a real 600) still drives `get_position_status_for_widget`. Arrange no longer uses it: it measures through the family QML (`preferred_size_measurement`). Move these warnings to the same measured sizes only if that adds no work to the Widgets tab until a warning is actually needed; otherwise retire the predictor's size formulas.

- [ ] **Overfull authored displays: the stacking planner is slow.** `build_display_auto_scale_plan` costs ~0.75 s per pass on an overfull display (measured 2026-09-27: 21 authored cards on 1707×960 made the saver's family bind take 2.7 s on the GUI thread; each Arrange draft rebuild pays the same). Normal layouts cost a few ms. Profile shows `_free_edge_candidates` dominating; reduce the search or memoize by inputs, with the same placements.
- [ ] **A Runtime Edit child edit made while Weather is still loading saves the loading height.** Untouched and moved cards now keep following their content in both editors (Save no longer freezes a loading Weather), but a child edit makes the entry explicit from the live card: 119 px while loading, so the card shrinks inside that box once data arrives (250 px). Needs a deliberate child edit on a card that has never had data (no cache, or offline). Options: keep content sizing for child-only edits, or let the loading card reserve its ready height.

## Known failing tests and anomalies (tracked until resolved)

Each stays here until fixed or explicitly retired; do not treat it as noise in a gate.

- [ ] **Spectrum extreme-viewport smoothness (pre-existing).** The 2026-09-23 16:53–17:06 acceptance run saw significantly reduced visual smoothness for Spectrum at extreme viewport shapes. Watch item until investigated separately.

## Handoff and regression rules

When an accepted behavior changes, select only the relevant targeted tests and physical observations; do not re-accept unrelated OSD, Media or widget systems. Keep full superseding GODZIPs with the canonical three `.godzip/` files, manifest-backed replace/delete instructions and no temporary scripts or compiled artifacts. Test commands belong in chat, not an added documentation file.
