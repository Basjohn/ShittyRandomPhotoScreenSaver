# R-183 | The cursor kept its changed shape after exit until a click

**Status:** source repair 11 Nov 2026 (branch commits `5f4130c9` observer, `1eed9332` harness, `76137c40` fix).
**Not yet accepted:** acceptance is the operator's own exit on native Windows with `tools/cursor_exit_observer.py`
running. The small-window native harness did not reproduce the operator's exact path on the pre-fix code (see
"Proof"); it did prove the mechanism natively and that the fix closes it.

## Symptom

Operator (Current_Plan 1B.2, reported 3-4 times): after the saver exits, the shape it showed (a link's pointing hand,
or another saver shape) stays on screen over the desktop until a single click. Every earlier round was called fixed.

## Earlier "fixes" and why their proof was false

| Round | Commit | What it changed | Why its proof could not see the bug |
| --- | --- | --- | --- |
| 1 | `962bcf48` (27 Oct) | `QuickCursorController.close()` / `_apply_cursor` force `ArrowCursor` once closed or admission is lost | Its test built a `QuickDisplayWindow` that was never shown and asserted `window.cursor().shape()`: a Qt property. |
| 2 | `3c1f67cf` (28 Oct) | No cursor code (preset foundry under the same title) | Not a cursor change at all. |
| 3 | `f20d772a` / `3b41a3ee`, merged `33ce0e11` (5 Nov) | `queue_close()` -> `_relinquish_pointer()` (grab off + arrow) and a retirement fence for hover `CursorChange` | `tests/test_qtquick_exit_pointer_release.py`: never-shown window, synthetic `QMouseEvent`s, a capture the test seeded itself; it asserts `window.cursor().shape()`, `GetCapture()` and the `ShowCursor` count, never the cursor Windows displays. |

All three set the arrow as a **Qt property**. None read `GetCursorInfo`, so none could observe whether Windows ever
received it.

## Cause

Two facts, both shown natively with `tools/cursor_exit_native_harness.py` (Win32 reads from a separate process):

1. **Qt hands a window's cursor to Windows only while Qt's own window-under-mouse is that window.**
   `QWindowsWindow::setCursor` stores the new cursor and calls `SetCursor` only if `applyNewCursor()` finds
   `QWindowsContext::windowUnderMouse()` to be this window (qtbase 6.11 `qwindowswindow.cpp`); otherwise the shape
   waits for the next `WM_SETCURSOR`. `windowUnderMouse` is cleared on `WM_MOUSELEAVE` and set again only by a mouse
   message to the window (`qwindowspointerhandler.cpp`). The product's every retirement arrow went through exactly
   this path: `QuickCursorController._apply_cursor` (`rendering/quick/cursor_controller.py:323`) and
   `QuickDisplayWindow._relinquish_pointer` (`rendering/quick/window.py:501`, before the fix the whole method).
   Native trial (production window flags, still pointer): the hand was displayed, Qt's window-under-mouse was cleared,
   and the exit's `BlankCursor` then `ArrowCursor` both left Windows showing **hand** (`qt_cursor_change native=hand
   qt=ArrowCursor`, and still `native=hand` at `qt_hide`).
2. **Windows never re-queries a still pointer when windows under it hide, close or their process ends.** Only mouse
   input (a move or a click) or an activation hand-off to the window under the pointer makes the window now there set
   its cursor. Native trials: a saver-set custom cursor stayed on screen unchanged across three later trial processes
   whose windows appeared and disappeared under the still pointer; a window shown under a still pointer received no
   `WM_MOUSEMOVE`/`WM_SETCURSOR` at all, and Qt's `TrackMouseEvent` was answered with an immediate `WM_MOUSELEAVE`.

So whenever the retiring window was showing a saver shape (put there by an ungated `WM_SETCURSOR` -> `applyCursor`)
while Qt's window-under-mouse was not that window, the arrow never reached Windows, and nothing after the hide asked
again: the hand or Halo stayed until the next click or move. When the saver window is the foreground window, its hide
hands activation to the window underneath and Windows re-queries (seen natively: the underlying app's cursor came back
7 ms after the hide), which hides the defect; exits where that hand-off does not land under the pointer (the saver no
longer foreground, e.g. a link click whose browser took the foreground, a non-activated secondary display or tool
window) keep it. **Which real event cleared Qt's window-under-mouse in the operator's runs is not proven** (the harness
reproduced that state by posting one `WM_MOUSELEAVE` to its own window).

## Fix

`rendering/quick/pointer_capture.py:175` `show_native_arrow_for_retiring_window(hwnd)`: one `SetCursor(LoadCursor(NULL,
IDC_ARROW))` on the GUI thread, skipped while the pointer is over another live window of this thread (which owns its own
cursor). Windows shows it only while this thread owns the cursor, i.e. exactly when a saver shape could be frozen.
Called once from the retire owner, `QuickDisplayWindow._relinquish_pointer` (`rendering/quick/window.py:487-509`, inside
`queue_close()`), while the HWND exists and before the queued hide, for windows that were on screen
(`_native_window_shown`, `window.py:1001`). Every exit converges there (key, click, motion, link click + browser launch,
context menu, tray, Settings, Edit/MC retirement, topology loss), synchronously before the event loop can hide the window,
so it also holds when the process quits right after. Windows only; off Windows the call is not made. No timer, poll,
counter or flag. `Docs/Contracts.md` "Native cursor retirement" records it.

## Proof

- **Native harness** (`tools/cursor_exit_native_harness.py`, opt-in, 18 trials this session within the limits: <=320x200
  device px at the pointer, <=2 s, pointer never moved): pre-fix, the arrow reached Windows on `esc_hand`, `esc_halo`
  and `link_hand` whenever Qt knew the pointer was over the window (arrow 1-5 ms after the hide); with Qt's
  window-under-mouse cleared (production flags, `--qt-leave`) the pre-fix exit left Windows on `hand` through
  `close_runtime` and the hide; post-fix the same trial showed `arrow` at the hide. The operator's own path was not
  reproduced in the small window; several trials were discarded because the pointer moved.
- **Regression tests:** `tests/test_qtquick_exit_native_arrow.py` asserts the native-facing action (the retire owner calls
  the native arrow with its own HWND exactly once; the function issues `SetCursor` with the shared `IDC_ARROW` and skips
  another live window of this thread). Negative control: with the pre-fix `window.py` the retire-owner test fails
  (`[] == [hwnd]`).
- **Operator acceptance (pending):** run `tools/cursor_exit_observer.py`, exit the real saver by each path, keep the mouse
  still for two seconds; each exit prints `cursor after exit: <name>, changed to arrow after <ms>` or `... only after click`.

## Rule for the future

A cursor fix is proven on what **Windows displays** (`GetCursorInfo` from another process: the observer or the native
harness), never on `QWindow.cursor()` or any Qt property. A Qt cursor change reaches Windows only through Qt's
window-under-mouse; anything that must be on screen after a window goes away is told to Windows while the window exists.
