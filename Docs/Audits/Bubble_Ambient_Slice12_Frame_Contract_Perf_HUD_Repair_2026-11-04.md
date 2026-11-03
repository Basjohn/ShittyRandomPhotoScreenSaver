# Bubble Ambient Slice 12: Immutable Frame Contract + Perf HUD Regression Repair

**Authority:** This is a focused, superseding full GODZIP based on Slice 11. It is **not** a general Bubble redesign; `Current_Plan.md` and `Future_Work.md` are unchanged. Live Windows/Qt Quick visual acceptance is still required.

## Observed regression

Repeated `[QUICK]` render-node failures raised `KeyError: 'immutable visualizer frame missing parameter: bubble_particle_glow_spread'`. The render implementation correctly requires `bubble_particle_glow_spread` from the immutable frame; the Slider was incorrectly tagged `logical=True`, so the presentation-only `spec_mode_parameters(...)` omitted it. Changing the renderer to use a default would conceal a contract break and is specifically **not** the fix.

**Repair:** `bubble_particle_glow_spread` is now presentation-owned (no `logical=True`), thus the canonical presentation applier owns it and the existing immutable frame capture publishes it. The renderer still requires the parameter, and no renderer-side fallback has been added.

The audit found that the **logical** `bubble_particle_glow_release_ms` control was not forwarded through `tick_pipeline.py` into the Bubble frame runtime; its simulator had been silently using its 160 ms fallback. Added a dispatch entry so saved slider values reach the actual glow envelope, with the same pre-release small-bubble audio response path. Also restored missing dispatcher entries for `bubble_microbubble_direction_mode`, `bubble_microbubble_columnarity`, and `bubble_particle_direction_mode` discovered by auditing every logical control in the Particles bucket. None of these changes touches the original Bubble motion or reactivity systems.

## Perf HUD correction

- Screen `--perf` HUD remains horizontally centred; only black backing becomes `#99000000` (60% alpha). Original 8 px top inset remains.
- Visualizer `--perf` HUD remains horizontally centred; only black backing becomes `#80000000` (approximately 50% alpha); **top inset is 12 px**, not Slice 11's 1 px or the old 6 px. Retain the 1 px per-side internal vertical padding increase (`implicitHeight + 8`). Text, borders, measurement sources and timing are unchanged.

## Contract/acceptance gates

- [x] `Glow Spread` classified as presentation-owned, and the existing production extractor can include it.
- [x] Every logical Particles-bucket control represented in the Bubble tick dispatch mapping; none is silently a UI-only slider.
- [x] `Glow Release` forwarded to the simulation, not left on its fallback.
- [x] Static HUD alignment, opacity and inset checks.
- [x] No cache artifacts or undeclared payloads in the GODZIP; manifest hash and size consistency audited.
- [ ] Native runtime: Bubble with Particles + Glow enabled draws without missing-parameter exceptions, including repeated Settings open/close, preset switch and restart.
- [ ] Native runtime: Glow Spread and Glow Release visibly follow their saved controls; confirm 60 ms vs 800 ms releases without changing particle core size.
- [ ] Native runtime: Same/Reversed and Columns settings visibly correspond to their UI values.
- [ ] Native screenshot: both perf HUDs centred, visualizer lower than original and 50% vs 60% backing as requested.
- [ ] GPU/visual FPS unchanged within expected run-to-run noise.

The native Qt-dependent full tests could not run in the container environment without PySide6. No claims of native render or UI acceptance are made.
