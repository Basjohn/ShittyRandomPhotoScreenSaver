# Leftoff – Next High-Priority Tasks

This file captures the next concrete steps in the current GL compositor and transition work so you can resume quickly.

## 1. GL Compositor Migration

- **Wipe – verify & integrate**
  - [x] Ported to compositor (`GLCompositorWipeTransition` + `GLCompositorWidget.start_wipe`).
  - [x] DisplayWidget now uses compositor-backed Wipe when `hw_accel` + compositor available, CPU `WipeTransition` otherwise.
  - [x] Added `test_gl_compositor_wipe.py` to validate no underlay/black frames.
  - [ ] Run the GL test suite and clean up any remaining legacy GL Wipe tests that only cover overlay paths.

- **Block Puzzle Flip – port to compositor**
  - [ ] Design a compositor-side block state (rect + flip progress) analogous to `FlipBlock` / `_GLFlipBlock`.
  - [ ] Extend `GLCompositorWidget` with a BlockFlip state and `start_block_flip(...)` API (timing via `AnimationManager`).
  - [ ] Implement `GLCompositorBlockFlipTransition` controller that delegates to the compositor.
  - [ ] Wire DisplayWidget `_create_transition` so `Block Puzzle Flip` uses the compositor when `hw_accel` + compositor are available; CPU `BlockPuzzleFlipTransition` otherwise.
  - [ ] Add compositor-focused tests (similar to `test_gl_compositor_slide`/`_wipe`) to assert no underlay/black frames.
  - [ ] Remove or downgrade legacy `GLBlockPuzzleFlipTransition` tests that only exercise overlay widgets.

- **Blinds – port to compositor**
  - [ ] Mirror the above BlockFlip approach for Blinds: compositor state + `start_blinds(...)` + controller + DisplayWidget wiring.
  - [ ] Add compositor tests for Blinds; drop overlay-only tests once parity is confirmed.

- **Diffuse – future compositor port (still open)**
  - [ ] Plan compositor representation for the Diffuse cell grid and progress.
  - [ ] Implement compositor-driven Diffuse and corresponding controller, then update DisplayWidget.

## 2. Slide Smoothness (GLCompositorSlideTransition)

- [ ] Add lightweight timing instrumentation (per-frame delta logs) for Slide at 165 Hz and 60 Hz.
- [ ] Inspect for jitter from rounding in slide lerp and adjust:
  - Easing choice (still defaulting to `QUAD_IN_OUT` for `Auto`).
  - Integer snapping strategy in `GLCompositorWidget._on_slide_update`.
- [ ] Once tuned, document final defaults and rationale in `Spec.md` under transitions/Slide.

## 3. Software Mode Performance Doc

- [ ] Draft `Docs/SoftwareMode_Performance.md` describing:
  - Constraints: 4K images, current CPU transitions, rotation cadence.
  - Hot paths: decode/scale, CPU composition, cache behavior.
  - Concrete optimisation options (cache sizing, reuse of fitted pixmaps, pan & scan interaction, etc.).
- [ ] Cross-link this doc from `Route3_OpenGL_Roadmap.md` and `Spec.md` once it exists.

## 4. Documentation & Cleanup

- [ ] Trim or reclassify any remaining roadmap items that only refer to legacy overlay behaviour that is now replaced by compositor paths.
- [ ] Update `Index.md` to reflect new modules:
  - `rendering/gl_compositor.py`
  - `transitions/gl_compositor_*` controllers
  - New tests (`test_gl_compositor_slide.py`, `test_gl_compositor_wipe.py`, etc.).
- [ ] Update `Spec.md` to describe the compositor as the primary GL path, the fullscreen compatibility workaround (`_FULLSCREEN_COMPAT_WORKAROUND`), and which transitions are compositor-backed vs CPU-only.
