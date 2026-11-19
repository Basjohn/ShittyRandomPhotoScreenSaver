# Test failures / duration triage | 19 November 2026 (temporary)

**Status: Windows verification pending.** Operator evidence: the full-suite Foundry run
`20261119_222107_56826f93` (`GODZIP_RUN_RESULTS_20261119_211932_20261119_222107_56826f93.zip`),
plus the preceding file-isolated diagnostics (`pytest_isolated_current_run(1).zip` and
`pytest_isolated_durations.json`). This document is an investigation handoff, **not**
a second test plan, proof of production defects, permission to rewrite visual tuning,
or an acceptance gate. Close or remove findings on actual reproduced evidence.

## Full suite: what is established

- Pytest collection passed: **15,965 test cases** in 10.7 seconds.
- The previous ordinary Foundry button used **4 sequential test-level chunks**, with **900 seconds per entire chunk**.
- Chunk 1: **3,991 passed, 1 xfailed**, 763.9 seconds. Chunks 2, 3, and 4 timed out at **900 seconds each**, their progress dots reaching approximately **98%, 63%, and 49%** respectively. The run took 3,464 seconds total.
- Those three timeouts **are not proof of three C++ deadlocks**. A 900-second ceiling for ~4,000 tests is already too short for the observed execution cost. Quiet output provided no reliable name for the active test.
- The normal runner now allocates full files into **32 historical-duration-balanced batches**, allowing **two concurrent child processes**, with a **single GPU/QtQuick/Studio-heavy lane**. Every batch has its own verbose test-by-test log and a timeout dump attempt; no test files are excluded. `--isolated` remains an explicit diagnostics-only option.
- This new runner cannot be certified on Windows/real Qt from the sandbox. Worktree-local run directories prevent output overwrites within separate checkouts, but GPU scheduling is **not a cross-worktree lock**. Agents should not start simultaneous heavy suite runs across worktrees without coordination.

## Unresolved failures from the earlier isolated run

| File / test | Evidence and probable boundary | Next investigator action |
|---|---|---|
| `tests/test_settings_input_foreground.py` | Both `test_input_roles_follow_current_semantics_across_live_theme_changes` cases failed. Explicit fixture `control.input.text` colour, e.g. `rgba(80,60,90,200)`, did **not** reach `QPalette.Text` (observed `#ffa79dac`). One `QLineEdit` also supplies its own background-only local stylesheet. A Qt stylesheet cascade/precedence issue is plausible; this is **not** an authored-default pin. | Reproduce with the real Qt runtime. Inspect stylesheet/palette propagation for QLineEdit, QSpinBox, and QComboBox, including locally styled children; prove actual displayed text colour before changing shared theme machinery. |
| `tests/test_visualizer_card_clip_contract.py` | Several `glass` cases fail at 1.0× and 1.25× (including Spline Curve, Shockwave Grid, Extruded Bubble), while Normal and many 1.5× cases pass. The file later timed out at `extruded_bubble-glass-1.25`. The recent material audit warns about **stale Qt QSB binaries** and changes to card materials. The clip geometry may be wrong, or the test's pixel oracle may include an intended material/glow fringe. | Rebuild/check QSB files using `tools/regen_qrc.py --shaders; --check` with the current Qt toolchain, then compare real captured pixels and material clip ancestry at controlled scales. Do not modify shader/clip bounds or relax test thresholds without that proof. |
| `tests/test_neon_lake_studio.py` | 160-second isolated timeout in `test_engine_owned_edits_change_the_engine_answers_negative_control`, after 7 passes. This may be slow engine-work/Qt lifecycle, not proven deadlock. | Collect last-test verbose log plus Python faulthandler and Windows dump; inspect the active threads before touching a native worker. |
| `tests/test_studio_drag_io_churn.py` | 160-second isolated timeout in the `shockwave_grid` parametrization of `test_no_drag_instrument_writes_while_moving_and_each_release_commits_once`, after the first five modes passed. | Isolate this parametrization, capture the native stack if stalled, and inspect the Studio change/commit lifecycle. No broad worker rewrite. |
| `tests/test_visualizer_owner_render_parity.py` | 160-second timeout at `test_the_worker_path_draws_the_in_process_pixels_at_non_default_settings[extruded_spectrum]`, after five passes. The test's *name* does not establish that dormant native-worker activation is permissible. | Inspect the actual ownership and phase-gating contract. Keep the not-yet-live Native Worker dormant. Diagnose with logs/dumps and focused evidence only. |

### Raw-threading policy scan: unresolved source availability

The earlier isolated run also failed
`tests/unit/test_policy_compliance.py::TestThreadingPolicyCompliance::test_no_raw_threading_in_production_code`.
It flagged `core/visualizer_engine/packet_mailbox.py:472`, a named daemon wake-listener
`threading.Thread`. **The test file is absent from the transferred GODZIP** (the operator's
working tree collected it). Do not quietly exempt or refactor this thread based on a
missing test alone. Determine whether this is a permitted dormant native mailbox
mechanism or a real live lifecycle policy violation, then reconcile the actual test
and its documented exclusion policy on the operator's tree. Native Worker is **not live**;
older tests must not awaken it just to satisfy test coverage.

## Prior failing assertions already changed in the preceding repair GODZIP

The earlier pass changed tests/tooling for artifact paths, Foundry's uppercase `FOUNDRIES`,
GLSL comments, visible test windows, stale glyph/material/media/Settings expectations,
and obsolete worker-enumeration assumptions. Treat these as **candidate repairs**, not
confirmed Windows passes. The later four-chunk run did not provide individual results
for chunks 2–4. Do not restore mutable-value/pixel-recipe pins to make tests green.

## Diagnosis discipline

1. Distinguish **batch deadline** from a stalled test. Read the last `batch_NN.log`
   node name, compare elapsed duration with the batch plan, and inspect faulthandler output.
2. On Windows, the parent attempts a DbgHelp `.dmp` **before** killing the batch.
   Dumps may contain sensitive process memory; inspect before distributing.
3. Run one focused suspect file/parametrization if needed. Do not run the full
   file-isolated suite for routine checks; do not use one shared output directory
   or `--basetemp` across worktrees.
4. Visual acceptance still needs real native/Qt/QML rendering and operator-visible
   pixels. A test failure is not authorization to change accepted material, glyph,
   media bar, Settings grip or native-core behaviour.
