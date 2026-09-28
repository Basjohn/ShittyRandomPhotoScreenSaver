# SRPSS | Current Plan

Active development work only. Implemented features keep their open physical acceptance in their own reference
(`Docs/Reference/Guided_Setup.md`, `Docs/Reference/Feeds.md`, `Docs/Reference/Transitions.md`); closed plans and
audits are historicalised (`Docs/Historical_Bugs/R-100_...`, `R-101_...`).

## Memory and handles | open development items

- [ ] **ImageWorker lean entry (R-99).** The ImageWorker re-imports the whole app graph on `spawn` (~1,060 modules). A lean worker entry could save ~100 MB resident, but it must be validated under Nuitka multiprocessing first.
- [ ] **Watch (low priority, not visible): scaled prefetch holds the GIL on the background CPU lane.** `QImage.scaled` runs for up to ~70 ms per 4K derivative while holding the GIL. It is not a stutter: overnight on 2026-09-25 the Visualizer logical runtime skipped 125 of 1,812,107 steps (0.007%). R-99 already halved the scaling work. Measure on the next `--perf` run before acting: seconds with `dt_max_ms` > 25 in `[PERF_HUD]`, their overlap with `Scaled prefetch` lines in `screensaver_cache.log`, and `skipped_deadlines` in `[SPOTIFY_VIS][LOGICAL] Runtime stopped`. Only if overlap remains material, move the scaling off the GIL with identical output.
- [ ] **Gmail refresh adds ~1.5 main-process handles per refresh.** The +18–25 handles/h slope tracks the Gmail cadence. Classify the type with `--handle-attribution`, then fix at the owner.

## Settings geometry | open development items

- [ ] **Widgets-tab position warnings use stale size estimates.** `ui/widget_stack_predictor.py` (QWidget-era formulas; e.g. Reddit 350 px wide against a real 600) still drives `get_position_status_for_widget`. Arrange no longer uses it: it measures through the family QML (`preferred_size_measurement`). Move these warnings to the same measured sizes only if that adds no work to the Widgets tab until a warning is actually needed; otherwise retire the predictor's size formulas.

- [ ] **Overfull authored displays: the stacking planner is slow.** `build_display_auto_scale_plan` costs ~0.75 s per pass on an overfull display (measured 2026-09-27: 21 authored cards on 1707×960 made the saver's family bind take 2.7 s on the GUI thread; each Arrange draft rebuild pays the same). Normal layouts cost a few ms. Profile shows `_free_edge_candidates` dominating; reduce the search or memoize by inputs, with the same placements.
- [ ] **Reddit header runs under its refresh glyph at the narrowest widths (both editors).** At a Reddit card width of about 300–333 px (the family floor is 300) a long subreddit name ("R/SUBREDDITDRAMA") draws under the ↻ glyph: `BrandedHeader` never elides and the header has no width bound, while the glyph sits at the right edge (measured 2026-09-28, render-control polish, with and without customized children). Widths from ~340 px up are clean. Options: hide the glyph when the header does not fit beside it, or floor the width at the header's natural width plus the glyph slot (Edit and Arrange read the same floor). Operator decision.
- [ ] **Content-extent maximums are not declared.** Reddit and Gmail clamp their reflow width at 2000 and System Stats at 1800 logical px; the shared width/height handles know only minimums, so a wider box (reachable on a 2560-wide display at 100%) shrinks the card inside it with empty space. Found from the family clamps, not yet rendered. Fix: a declared maximum on the descriptor, honoured by `edge_resize_rect` in both editors.
- [ ] **Runtime Edit child edit before Weather's first data saves the no-data height.** A child edit makes the entry explicit from the live card; if Weather has not yet received data (no cache), that box is 119 px tall and the card later shrinks inside it once data arrives (250 px). Seen in a harness whose saver unit had no data; rare in use (cached data usually arrives first).

## Known failing tests and anomalies (tracked until resolved)

Each stays here until fixed or explicitly retired; do not treat it as noise in a gate.

- [ ] **Spectrum extreme-viewport smoothness (pre-existing).** The 2026-09-23 16:53–17:06 acceptance run saw significantly reduced visual smoothness for Spectrum at extreme viewport shapes. Watch item until investigated separately.

## Handoff and regression rules

When an accepted behavior changes, select only the relevant targeted tests and physical observations; do not re-accept unrelated OSD, Media or widget systems. Keep full superseding GODZIPs with the canonical three `.godzip/` files, manifest-backed replace/delete instructions and no temporary scripts or compiled artifacts. Test commands belong in chat, not an added documentation file.
