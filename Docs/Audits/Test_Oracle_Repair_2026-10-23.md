# 2026-10-23 SRPSS Test-Oracle Repair: Mutable Configuration Is Not an Expected Result

**Status:** source/test fixture repair candidate. Qt / OpenGL checks await native-agent execution. No subjective visual work is closed here.

## Binding rule

**No test may expect any current operator-authored preset or mutable Settings value to equal a chosen constant, or use the live contents of an authored preset as the numeric input oracle for a behavior test.** Tests may select explicit values in a test-owned temporary profile/configuration and assert the functional result, and may compare an application's loaded, saved or reset state to the current canonical source dynamically. Shipped assets can be inspected for syntax, schema, ownership and non-mutating round-trip admission, but their artistic values are never a golden. Preset slots and files are mutable operator property. Don't switch them back to BEAM, recolour them, freeze them, or adjust current defaults to satisfy tests.

## Changes made in this handoff

- `tests/test_extruded_bubble_lazy_bucket_ui.py`: removed the seven-real-presets BEAM/1.0 assertion. Remaining test exercises test-owned SCENE/BEAM edits, lazy visibility, width and emission independence, save/reload; PySide6/Windows must validate.
- `tools/visualizer_replay/eb_simulation_support.py`: shared Qt-free simulation/test helper extracted from retired one-off startup script. `synthetic_controls` constructs two explicit, test-owned control profiles, never reads shipped JSON.
- `tests/test_extruded_bubble_startup_and_sizes.py` and `tests/test_extruded_bubble_recovery_candidate.py`: use synthetic profiles for overshoot/play-ramp behavior instead of authored Presets 1 and 7. Their thresholds are about controlled synthetic music and are **not** 2D Bubble visual/music acceptance.
- `tools/visualizer_replay/extruded_bubble_startup_probe.py`: retired. Its old command-line `--gate` is not a standing runtime/test authority; use the regular pytest cases. The GODZIP manifest explicitly requests movement to `/deleteme` so omission is not misinterpreted as deletion.
- Corrected eight flagged literal-default authority copies in EB camera/lighting/scene tests, default-on glyph and 3D control hints. The hint GUI test now compares test-owned edits, saved data, reopening, and reset to current canonical defaults rather than assuming today's authored booleans.
- Earlier queued work on stale persistence expectations, transition fake admission seams, Oscilloscope packed traces, and the range audit remain changes in this full archive. They are **not** equivalent to passed native tests.

## Verification, and what is not proved

- `python tools/test_durability_audit.py`: no blocking authority-copy findings after changes.
- Qt-free synthetic startup and recovery: 12 tests passed across both suites, including the camera control check.
- Targeted bucket-state + synthetic-startup: 20 passed, 1 missing historical fixture test deselected. Missing `tests/fixtures/settings_bucket_state_full_map_profile.json` must be retrieved from a real source, not fabricated.
- Additional Qt-free EB camera/scene/navigation/glyph cases: 31 passed, 2 failed. The **Deep non-Surface camera ceiling** numerical failure and **flight crash test source-string** failure remain real investigations, not tests we weakened.
- PySide6 absent here: GUI, widget flash/HWND, rendering, GL, Qt-presented Oscilloscope, transition engine and hint native tests **not** claimed passed. A local agent should execute and investigate these.
- The broad archived Windows suite (104 failed) was collected before these source corrections; do not count it as an updated rerun or declare all failures stale.

## Agent's next verification

1. Native PySide6: run `tests/test_extruded_bubble_lazy_bucket_ui.py`, `tests/test_visualizer_control_hints.py`, `tests/test_feed_settings_page.py`, `tests/test_transition_distribution.py`, `tests/test_qtquick_visualizer_clip_smoke.py` and the existing Settings HWND startup probe. Match observed behavior to contracts, do not regress production to stale assertions.
2. Run the existing pytest chunks once on the resulting working tree. Classify each failing selector as stale assertion vs product mismatch vs missing evidence. Preserve substantive pixel/physics/audio assertions until proven wrong by contract evidence.
3. Verify current Settings single-active-editing-path including nested Steam/Feeds and lazy restarts, and verify no additional tiny HWND appears on opening.
4. Maintain a strict distinction between agent-executable verification and operator visual acceptance. Agents should validate any repeatable technical facts independently; operator only for subjective art/musical parity where necessary.

See [Archived Failure Triage](Archived_Test_Failure_Triage_2026-10-23.md), [Test Durability](../Guides/Test_Durability.md), [Test Suite](../TestSuite.md), and [Current Plan](../../Current_Plan.md).
