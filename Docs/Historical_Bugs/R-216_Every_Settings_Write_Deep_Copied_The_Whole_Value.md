# R-216 | Every settings write deep-copied the whole value, so a display move's Save still stalled after R-212

**Status:** fixed 14 Nov 2026 (Current_Plan 1C.2, the "Not fixed in the product" box under the hop's Save).
Regression bars: `tests/test_settings_store_structural_sharing.py` (a write is strictly the new value and reuses every
unchanged part; a write never changes a stored value in place; the route-only Save shares every unchanged part of
the widgets root and stores what the copying path stores; change listeners get their own copy).

## Symptom

Lead, two-display hidden run after R-212 (`display/d1_run/20261114_1c2_move_hidden_stalls_after_r212/`): the hop's
Save still held the GUI thread 58.6 ms (57.2 before R-212), the stall stack inside `JsonSettingsStore.setValue`'s
`deepcopy` of the whole widgets root. R-212's single-threaded 39 -> 12 ms did not show in the product.

## Cause

`JsonSettingsStore.setValue` deep-copied every value it stored (300 KB of widgets root per Save), the Save read the
root through a deep-copying `get_widgets_map`, and R-212's derivation walked the whole Visualizer section in Python
and deep-copied the canonical one. All pure Python on the GUI thread: beside the render threads each GIL hand-off
inflated it (11.7 ms single-threaded became a median 29 ms, max 85 ms, with two GIL-holding threads in-process).

## Fix and evidence

`setValue` stores `share_unchanged(stored, value)` (`core/settings/stored_values.py`): parts strictly equal to the
stored value stay the stored objects (never changed in place), only containers on a changed path are new, none of
the caller's containers is kept. The Save and the move's admission read with `get_widgets_map_to_write` (root and
section dicts the caller's own, values the stored ones); the derivation finds non-identical values with C iterators
and shares the canonical section's values; widgets publications are deep copies for listeners. The settings part:
11.7 -> 0.85 ms single-threaded, 29.3 (max 85.3) -> 1.1 (max 1.3) ms with two GIL competitors, saved snapshot
identical every round. Evidence `.artifacts/evidence/display/move_timing/20261114_save_ownership/`.

## Lesson

On a GUI-thread edge beside Python render threads, cost is the count of Python operations, not the milliseconds
measured alone: a copy "for safety" of a value nobody changes is the whole stall. Share immutable stored parts and
make work proportional to the change.
