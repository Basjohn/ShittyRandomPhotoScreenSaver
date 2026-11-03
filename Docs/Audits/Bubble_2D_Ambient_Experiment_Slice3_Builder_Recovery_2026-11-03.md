# Bubble 2D ambient experiment, Slice 3: Builder crash and failed-selection recovery

**Experimental, not production accepted.** This complete GODZIP supersedes Slice 2 and includes its full file set. `Current_Plan.md` and `Future_Work.md` are intentionally unchanged. This is a targeted Settings regression repair, not a design or rendering revision.

## Native evidence from 2026-11-03

The operator's supplied screenshot shows Spectrum's `Appearance`, shared `Bar Appearance`, `Rainbow`, and `Advanced Sliders Still Apply When Hidden` controls overlapping. These labels are **not** Bubble's Particles controls. The supplied log (`logs826e7b1b482.zip`, `screensaver.log`) repeatedly reports:

`KeyError: 'bubble:particles'` from `VisualizerSettingsContextMixin.get_visualizer_bucket_state` during the first attempt to construct Bubble's lazy `build_spec_mode_ui` body.

Cause: the new `Bucket("particles", ...)` was added to the typed Bubble mode spec in Slice 1/2, but the mandatory canonical disclosure identity `ui.visualizer_bucket_states['bubble:particles']` was not added. The fail-loud reader was doing the correct thing: `self._visualizer_bucket_state[f'{mode}:{bucket}']`. The error interrupted visualizer mode switching after the shared Spectrum accessories had been parked. The screenshot is consistent with the previous mode's presentation being left in a transient/inconsistent state by that failed switch. The screenshot by itself does not prove there is no independent header-layout fault.

## Slice 3 changes

1. **Canonical registration**: add `bubble:particles: False` to the UI's `visualizer_bucket_states` schema. This is an inert disclosure default, **not** a renderer setting. Existing user data is sparse and will normalize against the expanded schema without migration or resetting authored presets.
2. **Preflight before QWidget creation**: `build_spec_mode_ui()` reads every declared bucket's canonical state **before** it builds any scaffold or bucket QWidget. A future missing identity remains fail-loud but cannot leave a partially built mode body just because a later bucket lacks registration.
3. **Failed lazy-selection rollback**: `VisualizersTab._select_mode_page()` now removes uncommitted/partial target bodies and restores the last valid visible mode, its stable `Bar Appearance`/`Rainbow` accessories, selection pill, and mode settings hydration if construction fails. It re-raises the original error rather than suppressing it. If there was no valid previously visible mode, it returns to Setup. A retry can then build the target normally.
4. **Schema test**: new Qt-independent `tests/test_visualizer_bucket_spec_schema.py` verifies all typed mode-spec bucket names have canonical UI disclosure identities. This is cross-schema coverage, not an assertion of authored default values or preset artwork.
5. **Qt recovery regression**: an added test in `tests/test_bubble_spec_ui.py` deliberately interrupts Bubble body creation *after* the QWidget factory returns but *before* the lazy host commits it. It checks that Spectrum remains selected, both stable accessories are reattached, the orphan is removed, and a subsequent Bubble selection constructs one clean body.

No Bubble renderer, simulation, audio admission, GLSL, presets, other-mode geometry, operator assets or the current/future plans were changed. The particle and microbubble compositing contracts from Slice 2 are retained exactly.

## Verification performed here

- [x] Pure all-mode disclosure-schema test: `python -m pytest -q --noconftest tests/test_visualizer_bucket_spec_schema.py` (passed, one test).
- [x] Python compilation of changed source and tests.
- [x] The schema audit found `bubble:particles` as the **only** missing mode bucket in Slice 2, and found none after this change.
- [x] GODZIP file hashes, ZIP integrity and manifest file set verification after packaging.
- [x] Verify `Current_Plan.md` and `Future_Work.md` are byte-identical to the Slice 2 baseline.
- [ ] **Not performed:** Qt UI regression suite or screenshot testing. This sandbox lacks PySide6.
- [ ] **Not performed:** actual GPU rendering and Bubble visual-performance verification.

Attempting the ambient Qt tests in this sandbox fails at test collection because `PySide6` is absent; this is an environment limitation, not a passing or failing feature result.

## Next native acceptance gate

1. Open Visualizers > Bubble > Custom. It must show Bubble buckets in order, including `Particles`. No `KeyError: 'bubble:particles'`, ghosted Spectrum buttons, overlapping headers, or duplicate accessories.
2. Open Particles; Microbubbles (Stream, Drift) and Particles (Stream, Drift, Glow) must display as grouped circular toggles. Conditional size/density/color/glow controls must behave as documented in Slice 2.
3. Switch Bubble -> Spectrum -> Bubble and Setup -> Bubble repeatedly; disclosure state, Save/Custom, and stable accessories must stay correct.
4. Run `\.venv\Scripts\python.exe -m pytest --noconftest -p tools.pytest_qt_noenv -q tests/test_visualizer_bucket_spec_schema.py tests/test_bubble_spec_ui.py tests/test_bubble_spec_runtime.py tests/test_bubble_ambient_optin.py tests/test_bubble_ambient_geometry.py` from the repository root (one-line PowerShell).
5. **If overlap persists after the Bubble construction error is gone**, capture a fresh screenshot and logs. Treat it as a separate layout/painter defect; do not claim the canonical key alone resolves unrelated native paint faults.

The original Bubble behavioural floor and all opt-in decoration defaults remain protected. Do not merge this experiment into `Current_Plan.md` until the user accepts it.
