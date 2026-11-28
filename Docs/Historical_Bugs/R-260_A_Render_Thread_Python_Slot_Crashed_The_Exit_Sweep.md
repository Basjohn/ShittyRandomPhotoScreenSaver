# R-260 | A Python slot on Qt's render thread crashed PySide's exit sweep

**Status:** attributed 28 Nov 2026 (N5.2h, "Switch-caused and NOT fixed", the exit crash). The trigger is gone: N5.2h
deleted the slot. The route that exposed it is not fixed by that deletion. R-209 fixed it for every product exit on
14 Nov, and `tests/test_quick_exit_routes.py`'s `bare` variant still takes it on purpose. Owner of the route:
`engine/runtime_destruction.py` (R-209). Control: `tests/test_quick_exit_routes.py`, the `bare` variant of each route.
The attribution comment is at the variant's assertion (commit `418d137ce`). The attribution was made by reading the
f12427a2e tree and comparing it with the switch's tree. It was not bisected.

## Symptom

`tests/test_quick_exit_routes.py` runs each exit route in its own child process on the native core's Vulkan device
(and, since the switch audit's fix on 28 Nov, on OpenGL too, where the window is hosted on the core as well).
Its `bare` variant reproduces R-209's defect: the loop ends while the window is still alive and its host is still open.

- Up to f12427a2e, that variant ended with 0xC0000005 at interpreter exit. R-209 used this crash as its control.
- After the N5.2h switch, the same variant exits with code 0 (measured 28 Nov). The window and host counts still show
  the defect (`window_alive_at_loop_end` True, `hosts_left` 1).
- The crash went away even though nobody had fixed the route.

## Cause

The background item (`BackgroundRenderItem`) connected the window's `sceneGraphInvalidated` signal to a Python slot,
`_RenderNodeRetirement.invalidate`. It used `Qt.DirectConnection`, so the slot ran on whatever thread emitted the
signal, and Qt emits `sceneGraphInvalidated` on its render thread.

When the loop ends with the window alive, PySide's exit sweep destroys that window during interpreter finalization. The
window's scene graph is then invalidated on the render thread, and the direct slot ran Python there. That was Python on
a non-main thread while the interpreter was being torn down, and it crashed the process.

On Vulkan no Python background render node ever existed (the native layer drew the photo), so the deleted node was not
the cause. In the f12427a2e tree, this slot was the probe window's only render-thread Python slot. The current tree has
none on that window.

N5.2h deleted the slot along with the Python render node retirement. The crash went with it, but the route did not
change: a loop can still end with a Quick window alive, and that remains R-209's defect.

## Why it hid

- R-209 read the crash as the cost of a live window at exit. A live window was what exposed the slot, but the slot was
  what crashed.
- When the slot was deleted, the crash vanished from the control. That looked like a fix, but the route was untouched.

## What remains

These direct render-thread Python slots still exist on other windows. Each is safe only while R-209's release-first exit
holds:

- `VisualizerRenderItem`: `retirement.invalidate` and the run on `sceneGraphInvalidated`
  (`rendering/quick/visualizer/item.py`).
- The Studio viewport's `_invalidate` (`ui/studio/viewport.py`).

## Lessons

1. A crash that vanishes is not a fix. Check the defect's own facts as well (here, the window and host counts at the
   loop's end), and keep the control on those facts rather than on the crash.
2. A `DirectConnection` Python slot on a render-thread signal runs Python wherever Qt tears that window down, including
   during interpreter finalization. Every exit route must release its windows first (R-209).
