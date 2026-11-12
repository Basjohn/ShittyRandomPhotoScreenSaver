# R-NEW | Every full-display glyph move silently rebuilt the whole runtime

**Status:** fixed 12 Nov 2026 (Current_Plan 1C.2; decision in plan 01 M3c "Display moves retarget the live owner").
The chrome-less move binds the source and target scenes as the direct Alt gesture binds its display
(`QuickCustomLayoutOwner.move_visualizer_to_display`), so its Save promotes live; a move whose Save still ends in a
runtime reload returns False and the takeover does not count it as a move. The move itself is one fade-through across
the two displays (`QuickDisplayVisualizerOwner.move_display`, `ExpandedDisplayCoordinator._run_display_move`, the
reducer's `BeginTransfer.end_expanded`), with the target's renderer prepared before the swap
(`QuickSceneController.begin_visualizer_prewarm`) and Extruded Bubble's GPU drift history carried across the share
group (`VisualizerRenderCarryover`, `DriftSolver.export` / `adopt`). Regression bars:
`tests/test_visualizer_display_move_retarget.py` (the real owner, layout owner and coordinator across two real units:
no reload both ways, the same owner, controller, logical runtime, engine and render identity, the projected rect on the
target, one fade-through from an ordinary or an expanded card ending expanded, the engine worker's session mapping both
ways; red on the pre-fix move), `tests/test_visualizer_display_move_gpu.py` (two hidden GL hosts: drift history after a
hop equals an uninterrupted run; the target prepared before the swap and invisible meanwhile).

## Symptom

Operator, 11 Nov: the diagonal full-display glyphs move the Visualizer "but have a teardown and rebuild, we do not want
teardowns and rebuilds unless absolutely needed. They are a last resort." Nothing in the logs said a rebuild was meant:
two ERROR lines (`Live geometry promotion found retained-runtime incoherence ... requires an active override`, `Save
requires retained-runtime reconciliation`) and then a full engine stop and restart.

## Cause

The display glyphs' move (plan 1B.12) reused Edit's hop and Save with no Edit chrome, and to show no chrome it bound no
scene to its CUSTOM session. Binding is also how the session's working viewport reaches the controller and its working
rect reaches the retained card, so the owner's live promotion (`commit_live_custom_layout`) found no override (and, on
a display of another size, the source's rect on the target) and raised its classified incoherence error; Save turned
that into `save_corrupt_retained_runtime`, which is `ScreensaverEngine.stop(exit_app=False)` and a restart: every
display window, widget family, the wallpaper, the Visualizer owner, its controller, logical runtime and engine worker
session. Save still returned True, so the takeover counted the rebuild as a move. The unit test of the move stubbed
`commit_live_custom_layout` with a recorder, so the refusal never ran in any test. A diagonal from an ordinary card
also ended ordinary: the queued reload replaced the generation before the enter on the target could commit and persist
the intent. Under the rebuild, every move (Edit's hop too) also rebuilt the renderers on the target on a visible frame
(104.8 ms measured) and restarted Extruded Bubble's GPU-integrated drift history; an expanded move drew the ordinary card
on both displays and popped it across at full opacity.

## Fix and evidence

Root-cause trace with its controls (`.artifacts/evidence/visualizers/expanded/20261112_1c2_root_cause/`): the real
owner and layout owner across two real units, every glyph move requesting the reload and Edit's own hop + Save of the
same item requesting nothing; two hidden GL hosts showing the renderer rebuilt and the drift history lost (36 of 36
frames differ, control identical), and after the fix in shared contexts 0 of 36. The windows' contexts share one group
because the product sets `AA_ShareOpenGLContexts` before Qt starts (proven on Qt's own QRhi context factory, control
without the attribute: not sharing). PyOpenGL's `GL_TIMEOUT_IGNORED` has the wrong value (0x8000000000000001) and
`glWaitSync` answers it with GL_INVALID_VALUE; the drift handoff uses the specification's all-bits value.

## Lesson

A transaction that borrows another owner's commit must give it the same inputs that owner's session gives it; hiding
chrome must not mean skipping the binding the commit depends on. A seam that can end in a rebuild must say so in its
result, never return success. And never stub the commit a test is about: the stub is exactly where this bug hid.
