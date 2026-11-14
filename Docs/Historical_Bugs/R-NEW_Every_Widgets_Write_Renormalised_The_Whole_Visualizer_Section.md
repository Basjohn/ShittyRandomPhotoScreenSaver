# R-NEW | Every widgets write re-normalised the whole Visualizer section, so a display move's Save stalled the GUI thread at the fade's midpoint

**Status:** fixed 14 Nov 2026 (Current_Plan 1C.2, the hop's Save box). `SettingsManager` derives the Visualizer
section of a write that changes only key-local settings (the widget's route) from a remembered canonical section of
its store, and the Save no longer copies the whole settings root three times. Regression bars:
`tests/test_settings_visualizer_route_write_cost.py` (a route-only write calls no whole-section normalisation, the
first write after load included; its stored section equals the full normalisation value for value and type for type,
for every key-local setting and value type; any other difference, or a changed preset catalogue, normalises whole;
the writer never changes a stored value it shares; the first two and the last red on the pre-fix code).

## Symptom

Lead, hidden real-saver runs, 12-13 Nov: the cross-display Save of a Visualizer display move held the GUI thread
102-132 ms (64-89 ms with both displays visible) at the fade's midpoint; no window renders while the GUI thread is busy
(Qt's threaded render loop syncs on it), so both displays froze one frame-span and the fade-in waited.

## Cause

`SettingsManager._store_widgets_root_locked` ran `normalize_visualizer_section_mapping` over the whole Visualizer
section (every mode, every key, preset index resolution against the catalogue) on every widgets write, although the
move changes only the widget's route (16.8 ms on the run's profile, single-threaded). Around it the write copied the
whole settings root three more times for nobody: the old value of a silent write (3.8 ms), the previous root read only
for monitor bindings (3.8 ms) and the persistence writer's deep snapshot (5.0 ms). The Save's settings part was 39.1 ms
single-threaded; beside two Python render threads each GIL hand-off multiplied it. The same cost applied to every
Settings write of the widgets root, silently.

## Fix and evidence

The store remembers (input, canonical) Visualizer sections per preset catalogue (seeded once at load, refreshed as
(stored, stored) by each write; the normaliser is idempotent). A section that differs from one only in
`KEY_LOCAL_VISUALIZER_SETTINGS` (the model's core build specs, which no migration, preset or other key reads) takes
that canonical section with those values coerced (`normalize_visualizer_section_from_canonical`); anything else is
normalised whole, as before. Read-only reads use `JsonSettingsStore.peek`; the persistence snapshot is shallow (a
stored value is never changed in place) and the writer copies the containers it fills. The Save's settings part:
39.1 -> 11.7 ms on the run's profile, the saved snapshot identical every round. Evidence
`.artifacts/evidence/display/move_timing/20261114_save_cost/` (`timeline.txt`, `save_parts.py`, `move_rig_parts.py`).
Not measured here: the product's stall with two displays (one display was connected).

## Lesson

A canonicaliser that is correct on every write can still be the wrong cost on a hot edge: when a write changes a
known, independent part, derive from the canonical whole you already hold instead of rebuilding it, and prove the
derivation equal to the full path for every key it covers.
