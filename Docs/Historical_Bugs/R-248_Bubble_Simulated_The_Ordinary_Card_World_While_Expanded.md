# R-248 | Bubble simulated the ordinary card's world while the display-wide card drew a grown one

**Status:** fixed 2026-11-21 at the owners (`QuickDisplayVisualizerOwner._apply_expanded_presentation` /
`_apply_resolved_presentation`, `VisualizerRuntimeController.set_drawn_world_extent` / `logical_world_extent`, the
engine worker's `VIS_SET_VIEW` version 3, Bubble's tick in `tick_pipeline`). Silent since Expanded Visualizer M2
(227626d02, 7 Nov). Sibling of R-196 (Waveform's pulse span read the ordinary card while expanded).

## Symptom (operator, 21 Nov 2026)

"In a viewport bubbles breathe and move at a decent speed; fullscreen they accelerate massively and lose their
breathing." The operator's log: a thin CUSTOM card (Bubble's world 2.866 x 0.513 canonical cards, about 1204 x 144),
expanded twice on a 2560 x 1440 display; the worker's `[VIS_BUBBLE_GEOMETRY]` lines show `domain=2.866x0.513` the
whole run, expanded or not.

## Root cause: two worlds for one frame

- Bubble's simulation works in canonical-card units on a world of `extent / canonical` (R-170, a8e72b2e9, 5 Nov) and
  publishes positions and wakes as fractions of that world. The extent is the controller's
  `presentation_viewport_extent` (`tick_pipeline`, Bubble step).
- The display-wide card grows the card's world on the display's long axis
  (`resolve_expanded_visualizer_presentation`: here 144 -> 675 high), and the renderer lays Bubble's fractions onto that
  grown content (`compute_quick_bubble_layout` from the drawn record's `logical_viewport_extent`).
- Expanded M2 (227626d02) commits only the ordinary record's metrics to the controller, by design, so the simulation
  kept the 0.51-high world while the scene drew a 2.40-high one. Every position, step and wake was stretched 4.67x along
  the grown axis: vertical travel 4.8x faster, live density 79 % lower (`before` below). The radius payload was the
  card's, so the breathing itself was unchanged; it was lost to the eye under the racing, sparse, stretched-wake field.
  The Gate 2 digest test (`test_published_logical_frames_are_identical_ordinary_and_expanded`) asserted that Bubble's
  frames do not change when expanded, which is exactly the defect.

## Fix

The display-wide card's world is the one display-wide value the logical side reads, beside the framed view (N0.4):
the owner hands the controller the drawn record's extent at the expanded commit and clears it at the ordinary commit
(edges only, never per frame); `layout_metrics_snapshot` carries it to the engine worker in `VIS_SET_VIEW` (version
3); Bubble's tick reads `logical_world_extent` (the drawn world while expanded, otherwise the CUSTOM override or the
committed extent). The committed metrics, CUSTOM, presets and Settings still never see the display rect; Spectrum and
Neon Lake keep reading the card's own extent.

## Evidence

- `tests/test_bubble_expanded_world.py` (production owner, unshown runtime, thin card, card and display-wide): the
  simulation's world equals the drawn world at both sizes and on-card travel against the bubbles' own size matches
  within 25 %. Negative control run on the old code: fails (world 0.514 against 2.399; vertical travel 4.84x).
- `tools/visualizer_replay/bubble_display_wide_response.py` on `anything_mixed2.jsonl`, 60 s, card 1204 x 144,
  display 2560 x 1440 (display-wide world 1204 x 675, capacity zoom 2.17): `.artifacts/evidence/visualizers/bubble/
  display_wide/20261121_anything_mixed2_p0` and `_p1`. Preset index 1: speed +0.1 %, along-stream +0.1 %, big radius
  +1.1 %, density +6.2 % against the card; big breathing range 0.73 / 0.82, swings 1.23 / 1.25 per s; `before` +369 %
  speed, -79 % density. The per-frame big-bubble breathing traces of card and display-wide overlap under the music.

## Binding lessons

- A value the renderer lays a frame onto and the value the simulation's world is built from must be the same value.
  When a presentation route draws a different world, the logical side must be handed that world at the route's edge.
- A digest identity across sizes is not a correctness proof for a mode whose world is the size: it pinned the defect.
