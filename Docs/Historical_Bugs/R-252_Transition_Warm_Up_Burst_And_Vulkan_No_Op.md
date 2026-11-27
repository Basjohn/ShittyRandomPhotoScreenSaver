# R-252 — Transition warm-up burst at the idle edge, and no warm-up at all on Vulkan (fixed 27 Nov 2026)

## Failure

A native transition's first run in a process stalled the GUI thread. On a hidden Vulkan host at 3840 x 2160,
`transition()` cost 38.4 ms (Disintegrate) and 69.5 ms (Volumetric Dissolve) on the first run, against about 11-12 ms
on the second. Under the operator's game load (22 Nov) that pushed render-thread gaps past 33 ms inside the run.

Two old defects, both silent:

1. The S11 warm-up (`DisplayManager.prepare_next_transition`) imported the next transition's module in one burst at
   the idle edge, including the startup reveal, costing 31-47 ms. That broke the warm-up rule (one bounded unit per
   spaced, already-rendered frame).
2. On Vulkan, `BackgroundRenderItem.schedule_warm_step` returned False, so the rest of the chain warmed nothing. The
   module's import also built its shader texts (9-10 conversions) and pulled in about 12 shared scene modules at once.
   That cost landed in the first run whatever was warmed.

## Fix

- The warm-up is now a chain of small GUI-thread units, one per step, each run on the window's queued
  `afterRendering`, so it follows a frame the window rendered anyway. The owner's existing 200 ms spacing is kept.
- Unit order, next-likely first: the shared scene modules (`SHARED_RENDERER_MODULES`), the transition module, its
  program pieces (`WARM_PIECES`, built lazily with `functools.cache`), the layer's run modules, then the renderer
  resolve.
- A run still builds whatever is left. Arming is refused during a run, and a cancel disarms the unit.
- No unit costs more than 7.3 ms (largest 5.5-6.2 ms with bytecode cached). After the warm-up, the first run imports
  and builds nothing: 7.4 / 8.0 ms.

## Measuring trap

The Claude Code shells set `PYTHONDONTWRITEBYTECODE=1`. Modules new or edited since their cache was written then
compile on every import, so the first remeasure read about 34 ms for the first unit. The proof guide's "Bytecode
during timing runs" owns the rule.

## Guards

- `tests/test_transition_warm_units.py`, with the child `tests/transition_warm_first_run_child.py`:
  - after the warm-up, the first run imports and builds nothing;
  - the cold run and the old import-only warm-up are the controls;
  - the module import builds nothing, and each unit builds at most one piece and imports at most one module.
- Evidence: `.artifacts/evidence/native_core/n5_2f/20261127_hitch_warm_units/` and `.../20261127_hitch_warm_units_split/`.

## Open

Other scene transitions (Crumble, Glass Shatter, Exploding Tiles and others) still build their texts at import. Their
first unit is unmeasured (`Current_Plan.md`, the N5.2f hitch box).
