# R-NEW | Every StyledPopup kept itself alive through its buttons' lambdas, so it outlived the QApplication

**Status:** fixed 14 Nov 2026 (Current_Plan 1D.12). Present since 2c1cc235. Owner: `ui/styled_popup.py`
(`StyledPopup._setup_ui`). Regression bar:
`tests/test_styled_popup_lifetime.py::test_a_parentless_popup_is_destroyed_when_its_last_reference_goes`, which failed
on the code before the fix.

## Symptom

`tests/test_widget_display_route_prompt.py` passed its 15 tests and the process then exited 127 (once 0xC0000409) at
interpreter teardown, every run. A single guard test (`-k test_guard_switches_absent`) was enough. Running with
`-X faulthandler` happened to exit 0, and so did some subsets: the outcome depends on PySide's exit order.

## Cause

1. `StyledPopup._setup_ui` connected each button as `button.clicked.connect(lambda _=False, val=value:
   self._on_button(val))`. The lambda's closure holds the popup.
2. Qt stores a Python slot with its connection, for as long as the sender (the button) lives. The button is the
   popup's child, so popup -> button -> connection -> lambda -> popup is a cycle that runs through C++, where the
   garbage collector cannot see or break it.
3. So no popup was ever destroyed: dropping the last Python reference after `exec()` left it alive (and still listed
   in `QApplication.topLevelWidgets()`). Read from a run: after the test and `gc.collect()`, the popup's only
   referrers were the two button lambdas' closure cells.
4. At interpreter exit a parentless popup left alive was destroyed after the QApplication, which ends the process
   with a non-zero code.

## Fix

Each button carries its answer as a dynamic property and connects to the bound method `_on_button_clicked`, which
reads `sender().property(...)`. PySide holds a bound-method slot weakly, so the popup goes when its owner drops it.
After the fix the route-prompt file exits 0 in three runs in a row, and so does the single-test case.

## Why it hid

- Every test passed; only the exit code showed it, and a run of several files reports one exit for all of them.
- In the product each popup is small and the leak only grows by one popup per prompt shown, so nothing measured it.
- `_ColorPickerDialog` in the same file looked similar (child handlers assigned as attributes that reach `self`) but
  is not affected: attributes in a wrapper's `__dict__` are visible to the garbage collector; only connection
  storage is not. Checked with the same destroyed-on-release probe.

## Lessons

1. Never connect a child's signal to a lambda or `partial` that captures its parent; connect a bound method of the
   parent (held weakly) and carry per-sender data on the sender.
2. A parentless top-level that is still in `QApplication.topLevelWidgets()` after its owner returned and
   `gc.collect()` ran is retained by a slot: list its referrers to find the closure.
