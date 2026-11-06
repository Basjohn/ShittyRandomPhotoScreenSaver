# R-173 | Hidden display scene: GL context freed before its render control, heap corrupted for the next test

**Status:** fixed 2026-11-07 (`tools/onboarding_preview_foundry.py`, `_HiddenQuickScene`). Regression test:
`tests/test_hidden_scene_retirement.py`. Production is not exposed (see below). Same mechanism as R-172.

## Symptom

`tests/test_surface_materials.py` hit a Windows access violation in some whole-file runs. The crash was inside a plain
`QWidget()` constructor during `WidgetsTab.__init__` (`ui/tabs/widgets_tab.py` `_build_setup_ui` /
`_create_subtab_host`), in `test_per_family_row_round_trips_and_a_page_save_keeps_unbuilt_values`. The
`SRPSSSettingsWriter` thread was in `persistence.py` `_write_snapshot` at the time. Each test passed alone. A
constructor that crashes means the heap was already damaged by the hidden-scene tests that ran before it.

Measured before the fix: the lead saw 1 in 4 to 1 in 5 whole-file runs. With the style tests in front
(`test_surface_material_style.py test_surface_materials.py`), 4 of 12 runs crashed with the same stack.

## Evidence

An ordering probe watched `destroyed` on the scene's root, backdrop item, window, render control, GL context and
offscreen surface:

- after `_HiddenQuickScene.close()`, **nothing** had been destroyed. `close()` used `deleteLater()` and then
  `processEvents()`, but outside a running event loop `processEvents()` does not deliver deferred deletions;
- when the test dropped the scene object, the order was: context, surface, root, backdrop, window, and only later
  (the next deferred-delete delivery) the render control and the QML engine.

The context and offscreen surface were independent Python owners, so they died the moment the Python object went.
The render control's RHI keeps a raw pointer to that imported context and makes it current again in its destructor
(R-172). Destroying the control after its context read and wrote freed memory. That only crashes once the freed
block has been reused, which is why it showed up in a later, unrelated constructor and was intermittent.

The probe also showed a second, smaller ordering fault. `close()` detached the scene root before invalidating the
scene graph, so the item had already left the window and missed `sceneGraphInvalidated`. The surface backdrop's
render node therefore never freed its GL objects; they died with the context. Production never takes that order.

## Fix

`_HiddenQuickScene` now owns its pieces the way R-172 settled for the Studio surface, and retires in production's
order:

- the GL context and the offscreen surface are Qt children of the render control (`setParent(control)`), so they
  cannot be freed before it on any path (close, an exception, GC, the exit sweep);
- `close()` invalidates the scene graph first, so render nodes release their GL with the context current. It then
  retires the hosted widgets and detaches and deletes the root and QML context, then the window, the control and the
  owner. It finishes with `QCoreApplication.sendPostedEvents(None, DeferredDelete)`, so every one of them is gone
  before `close()` returns, in posting order: root, window, control (taking the context and surface), engine.

## Proof

- `tests/test_hidden_scene_retirement.py`: a display retires with Glass active, without parking. The test asserts
  four things: the imported context and surface are the control's Qt children; everything dies inside `close()`;
  the window dies before the control, and the control before its context; the backdrop node freed its GL.
  It then builds fresh `QWidget`s and a QML component. It fails on the old code.
- Repeat harness (fresh process per run, `-X faulthandler`):
  - before: 4 of 12 runs of `test_surface_material_style.py test_surface_materials.py` crashed;
  - after: 0 of 24 runs of that pair, and 0 of 24 whole-file runs of `test_surface_materials.py`;
  - every other test file built on `_HiddenQuickScene` passes (139 tests).

## Production exposure

None from this mechanism. Production display windows own their GL context inside Qt's render loop: there is no
imported context and no independent Python owner. The scene controller retires QML objects only after the scene
graph is invalidated (`finalize_retirement` refuses earlier). By then the backdrop's `sceneGraphInvalidated` hook has
already released its GL on the render thread, with the context current. The probe confirmed that path frees every
backdrop GL name before the item dies. Only tools and tests construct `_HiddenQuickScene`: the material capture tool,
the Guided Setup foundry, the Visualizer preview tests and the material tests.

## Lesson

This is the R-172 lesson again, in the second place that imported a context. Two additions:

- In a test or tool harness `deleteLater()` plus `processEvents()` deletes nothing. Deliver the deletions
  explicitly, in the order you mean.
- Retire a hidden scene in production's order (invalidate the scene graph first), or render nodes that free GL on
  `sceneGraphInvalidated` silently never do.
