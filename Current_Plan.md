# SRPSS | Current Plan

Active development work only. Implemented features keep their open physical acceptance in their own reference
(`Docs/Reference/Guided_Setup.md`, `Docs/Reference/Feeds.md`, `Docs/Reference/Transitions.md`); closed plans and
audits are historicalised (`Docs/Historical_Bugs/R-100_...`, `R-101_...`).

## 3D scene foundation | operator-promoted 2026-09-29

Detail, rewards, risks and performance hazards per slice: `Docs/Future_Work/3D_Scene_Foundation.md`. Work in this
order; commit and push each slice; tests and measurements before looks change.

- [ ] **Motion Trails CPU:** each ghost re-sets its program's uniforms through PyOpenGL (+0.5-1.0 ms CPU per frame at 1440p when On). Set the shared uniforms once per trail pass and vary only time and fade per ghost; measure CPU submit before and after.
- [ ] **S10** Cheaper High beyond the shader resolve (landed), only if physical testing shows the cost matters.
- [ ] **S11** First-frame program compile, only if the installed build's frame trace shows the hitch.

## Memory and handles | open development items

- [ ] **ImageWorker lean entry (R-99).** The ImageWorker re-imports the whole app graph on `spawn` (~1,060 modules). A lean worker entry could save ~100 MB resident, but it must be validated under Nuitka multiprocessing first.
- [ ] **Watch (low priority, not visible): scaled prefetch holds the GIL on the background CPU lane.** `QImage.scaled` runs for up to ~70 ms per 4K derivative while holding the GIL. It is not a stutter: overnight on 2026-09-25 the Visualizer logical runtime skipped 125 of 1,812,107 steps (0.007%). R-99 already halved the scaling work. Measure on the next `--perf` run before acting: seconds with `dt_max_ms` > 25 in `[PERF_HUD]`, their overlap with `Scaled prefetch` lines in `screensaver_cache.log`, and `skipped_deadlines` in `[SPOTIFY_VIS][LOGICAL] Runtime stopped`. Only if overlap remains material, move the scaling off the GIL with identical output.
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
