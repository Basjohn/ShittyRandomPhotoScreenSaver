# R-NEW | The Defaults Foundry's row widgets stayed owned by Python, so PySide's exit cleanup deleted them a second time

**Status:** fixed 13 Nov 2026 (Current_Plan Medium 1). Present since the tool's first version (884cb6f1, 10 Jul 2026).
Owner: `tools/default_settings_editor.py` (`DefaultSettingsEditor._build_ui`). Regression bar:
`tests/test_default_settings_editor.py::test_editor_children_are_owned_by_qt_not_python`, which failed on the code
before the fix, naming the 11 widgets. Evidence: `.artifacts/evidence/tests/defaults_editor_exit_av/`.

## Symptom

`tests/test_default_settings_editor.py` passed all its tests and then the Python process died at exit: 0xC0000409
(faulthandler: "Fatal Python error: Aborted") or 0xC0000005, in 10 of 10 fresh runs, also at 0c54ef85. One editor
was enough (single tests crashed in 2 to 4 of 5 runs). The tool's own `--smoke-test` exit had the same object state
and exited cleanly in 10 runs; the outcome depends on the order in which PySide visits its objects at exit.

## Cause

1. The controls row and the actions row were built as `QHBoxLayout()` with no parent, filled with widgets, and only
   then added to the window's layout. PySide moves a widget to Qt's ownership in `addWidget` only when the layout
   already has a parent widget, so these 11 widgets (Build Profile label and combo, search field, Changed Only, count
   label, status label, the import / validate / discard / undo / save buttons) stayed owned by Python while Qt also
   owned them as children of the central widget.
2. At interpreter exit PySide's cleanup (`destroyQCoreApplication`) deletes every QObject Python owns, in the order of
   its wrapper map, then the application. A window that was still alive (the tests only `close()` it, and a connected
   lambda closing over `self` keeps it referenced) is deleted with its children; a child Python still counted as its
   own was then deleted again. Placed with atexit markers: the crash fell inside that cleanup, never before it.
3. Discriminating run: handing the Python-owned children to their parents just before PySide's cleanup, with the
   windows themselves left alive and Python-owned, took the file from 6 of 6 crashes to 0 of 6.

## Fix

Each row layout is added to the window's layout before its widgets (`layout.addLayout(controls)` right after the row
is created; the same for `actions`), so `addWidget` hands every widget to Qt. Only the windows remain Python-owned at
exit, which is correct. After the fix: 10 of 10 runs exit 0; the code before it with the same test file: 10 of 10
crash.

## Why it hid

- Every test passed; only the process exit code showed it, and runs that collect several files report the exit, not
  the file.
- `QObject.findChildren()` hands every wrapper it returns to Qt, so a window that is walked with it (the Settings
  shadow pass walks its whole tree) silently repairs the ownership. A check of ownership must read
  `shiboken6.getAllValidWrappers()`, as the regression bar does.
- The order of PySide's exit cleanup varies with the heap, so the same state exited cleanly in the tool's own runs.

## Lessons

1. Add a layout to its parent (or give widgets their parent) before adding widgets to it. A widget in a parentless
   layout is owned by Python and by Qt at once.
2. An exit crash with no Python frame after passing tests is a teardown-order defect: list the Python-owned QObjects
   that have a parent just before PySide's atexit cleanup.
