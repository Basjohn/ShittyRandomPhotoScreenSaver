# Bubble 2D ambient decor: Slice 2, underlay / viewport / Builder

**Experiment only. Not a production-accepted feature or an amendment to Current_Plan.** This superseding Slice 2 GODZIP includes the complete Slice 1 working tree plus the changes below. Apply as a complete GODZIP against the intended working tree; do not apply both slices as independent patches.

## Objective and authority

The extra circles and coloured specks are **watery background decoration**, not new hero bubbles. No original Bubble population, body reactivity, global RNG, collision logic, movement, shader bubble loop, preset, or operator visual tuning is intentionally altered. All opt-in toggles remain false by default. Particle **core size never breathes**; when Glow is checked, *only its halo intensity* uses the already-integrated small-bubble breathing signal. Microbubbles inherit the small-bubble resolved stream speed; neither decoration type has new motion clocks.

## Compositing contract (Slice 1 overlay corrected)

The existing Bubble shader draws gradient, wake, ghost and hero bubbles in one fullscreen pass, so merely drawing GL_POINTS afterward put them on top of heroes. Slice 2 adds a **small, opt-in, transparent point texture** that is sampled inside the canonical Bubble fragment shader **immediately after the gradient, before every existing Bubble contribution**.

Sequence for opt-in frames: Bubble runtime publishes bounded immutable ambient points -> Quick Bubble renderer draws <=192 point sprites into its own transparently cleared content-local RGBA8 FBO -> Bubble's original draw blends that premultiplied FBO into the gradient -> the unmodified wake, ghost and bubble loops run over it -> original content/stencil/shell clip applies to the final result.

The texture is never a second persistent scene owner, a QML overlay, another clock, or a second Bubble simulation. Its FBO and buffer are context-owned by the Bubble renderer and released on mode retirement or when returning to a non-ambient preset. The main shader's `u_ambient_enabled=false` bypasses the texture entirely in old presets. Source-over blending also handles translucent gradients.

**Stencil and edges:** The local transparent target has no external geometry, and a point sprite is physically clipped at its bounds. The compositing sampler is called *inside* Bubble's existing content-rectangle discard; the parent Qt Quick rounded/stencil clip remains authoritative for the outside edge. The offscreen draw temporarily disables inherited stencil/scissor and restores framebuffer, read buffer, viewport, program, VAO, vertex buffer, active texture, blend settings, clear colour, colour mask, and relevant GL enable state. Check this on native OpenGL, including quarter-turn content orientation. The existing soft alpha edge fade prevents teleport flashes from independently wrapping decoration positions.

## Extreme viewport and general expansion

- The canvas derives from **local content rect**, not whole-screen/card/monitor bounds, so offsets and borders cannot displace the layer. Rotation is applied by the already-established Bubble logical-UV path when its texture is sampled; do **not** independently rotate texture contents.
- The ambient texture preserves content **aspect ratio** at ordinary, extremely tall, extremely wide and enlarged viewports. Rendering scale is uniform, with a strict **2048-pixel longest-edge cap** to bound target memory (RGBA8 <=16 MiB) and point rasterization. This cap downscales, it never crops or stretches.
- Dots remain small circular sprites (not ovals) regardless of card aspect. Point positions remain normalised in the same content domain as original Bubble positions. Density is capped at 96 microbubbles and 96 particles; an extreme expansion makes them less dense rather than spawning an unbounded number.
- Sprite diameter tracks overall **equal-area expansion** with a bounded 0.75x to 2x scale, not independent width or height stretching. Baseline user slider values remain baseline-pixel diameters. A visual review must establish that these sizes work at 1x, 2x and extreme viewport sizes; further artistic adjustment is acceptable inside this isolated experiment.
- Stream direction codes now align with the *existing Bubble simulation's* direction vector convention. Stream speed remains taken from the already-integrated Bubble frame, and Swirl suppresses independent stream travel just as the original Bubble mode does.

## Bubble Builder fixes in this slice

- New **Particles** bucket now groups Microbubbles (Stream / Drift) and Particles (Stream / Drift / Glow) as two labelled rows of the existing circular checkboxes.
- Microbubble density and size only show when its Stream or Drift is active. Particle size, density and colour only show when at least one particle toggle is active. Glow Intensity and Glow Reactivity remain visible **only when Glow is active**, as already dictated by the typed schema.
- Controls are hidden, **not cleared or defaulted**; loading a preset is signal-silent and expressly refreshes conditional row visibility. It retains the canonical Custom auto-switch and Save/Save As pipeline.
- No unrelated Bubble GUI control/advanced section was redesigned. The operator has not provided another specific pre-existing Bubble-builder defect, so avoid speculative changes to established controls.
- The spec UI test's expected bucket ordering is updated to include Particles; new UI tests cover toggling, glow-only use and saved values.

## Verification: what is proven vs. still open

**Verified in this non-native workspace:** source compilation of affected Python files; standalone pure geometry checks of nine representative viewport dimensions/aspects, uniform size scaling and rejected invalid dimensions; full GODZIP ZIP CRC/SHA-256 manifest integrity; unchanged `Current_Plan.md`, `Future_Work.md` and other unrelated original payloads. Standalone simulation invariants from Slice 1 remain the expected contract. No PySide6, PyOpenGL or native GPU was available here, so no Qt UI, real shader compile, live clipping or FPS acceptance has been observed.

**Native acceptance checklist (all open, not implicitly passed):**

- [ ] Previously saved ordinary 2D Bubble preset with all decoration toggles off: visually/time/response parity, no layer target allocation or GPU slowdown.
- [ ] New Particles bucket opens, labelled circular checkboxes align, each toggle works, the expected conditional rows show/hide, preset save/load preserves values and correctly enters Custom.
- [ ] Micro Stream only, Micro Drift only, both: short randomized circles move and wrap without flashes, and inherit appropriate directions and resolved speed.
- [ ] Particle Stream only, Particle Drift only, Glow only, all combined: core diameter remains fixed over real loud sustained passages, **glow** varies smoothly with the existing small-bubble envelope.
- [ ] With both layers on, decorations are **behind big/small original bubbles and wake/ghost** but above the gradient, with no sprite appearing over a hero or the stencil/shell.
- [ ] Check 420x280, 280x420, 2000x300, 300x2000, multi-x expansion, DPR>1 and quarter rotations with native image frames; no stretched circles, out-of-bounds pixels, displaced clipping or exploding density.
- [ ] Compare live FPS/GPU ms for off, low density and both densities max, including extreme viewport expansion and concurrent GPU load. If performance cost is excessive, reject/fix before calling this layer complete.
- [ ] Switch modes / toggle off repeatedly: resources retire correctly, no GL state leak affects next mode or the original Bubble.

**Full native one-line PowerShell test command (venv only):** `\.venv\Scripts\python.exe -m pytest --noconftest -p tools.pytest_qt_noenv -q tests/test_bubble_ambient_geometry.py tests/test_bubble_ambient_optin.py tests/test_bubble_spec_ui.py tests/test_bubble_spec_runtime.py`

## Reversion and isolation

This is a deliberately self-contained speculative feature. Reject all effects with the five new toggles OFF, or revert to `GODZIP_cc4c390a9e_2026-11-03_1344.zip` if necessary. No `Current_Plan.md` edits, no edits to Extruded Bubble, no preset/theme/reference edits, no Git operations, no install and no environment-variable workaround.
