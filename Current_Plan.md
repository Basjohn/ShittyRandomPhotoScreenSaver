# SRPSS | Current Plan

## Guided Setup / Quick Start (ACTIVE)

Execution plan and live checklist: `Docs/Future_Work/Guided_Setup.md`. Operator review 2026-09-27, open items:

- [ ] **Slider groove end caps (operator call).** Zoom-checked 2026-09-27: the groove's bevel uses separate top
      (translucent), bottom and side border colours, so the rounded end caps read brighter than the long edges. Not a
      compositing seam; decide whether to paint the groove as one path. Tooltip border (alpha 220) still unchecked.
- [ ] **Accessibility tab alignment.** The Pixel Shift section's checkbox and slider start a few px right of the
      Dimming section's (sections built with different row helpers); align them.
- [ ] **ImageWorker lean entry (R-99).** The ImageWorker re-imports the whole app graph on `spawn` (~1,060 modules). A lean worker entry could save ~100 MB resident, but it must be validated under Nuitka multiprocessing first.
- [ ] **Watch (low priority, not visible): scaled prefetch holds the GIL on the background CPU lane.** `QImage.scaled` runs for up to ~70 ms per 4K derivative while holding the GIL. It is not a stutter: overnight on 2026-09-25 the Visualizer logical runtime skipped 125 of 1,812,107 steps (0.007%). R-99 already halved the scaling work. Measure on the next `--perf` run before acting: seconds with `dt_max_ms` > 25 in `[PERF_HUD]`, their overlap with `Scaled prefetch` lines in `screensaver_cache.log`, and `skipped_deadlines` in `[SPOTIFY_VIS][LOGICAL] Runtime stopped`. Only if overlap remains material, move the scaling off the GIL with identical output.
- [ ] **Gmail refresh adds ~1.5 main-process handles per refresh.** The +18–25 handles/h slope tracks the Gmail cadence. Classify the type with `--handle-attribution`, then fix at the owner.

## Known failing tests and anomalies (tracked until resolved)

Each stays here until fixed or explicitly retired; do not treat it as noise in a gate. Physical validation lives with each feature's own doc, not here.

- [ ] **One red present before 2026-09-26's FEEDS work (Windows, whole widgets/settings gate):**
  - `test_qtquick_transition_parameter_defaults.py::test_sparse_crumble_uses_canonical_piece_count_and_complexity`: the canonical Crumble `crack_complexity` default is 11.0 but Settings and the resolver cap it at 2.0. Operator decision: was 1.1 meant?


- [ ] **Derived defaults artifacts (operator decision).** Audit 2026-09-27: `core/settings/defaults_snapshot.json`
      and `Docs/SRPSS_Settings_Screensaver{,_MC}.sst` are byte-for-byte derivations of `default_settings.py` +
      `default_profile_overrides.py`. No runtime code, build or installer reads them; only 10 tests (which could
      ask `defaults_snapshot_builder` directly), the staleness preflight and the regenerate button/editor step.
      Recommendation: retire all three and the staleness gate; keep the builder for on-demand exports.
- [ ] **Widgets tab save coalescing timer.** `WidgetsTab` debounces saves with `_SAVE_COALESCE_MS` single-shots.
      Check whether edge events (slider release, editing finished, toggles) can replace it under the timer policy.
- [ ] **Tests that show real windows.** 21 test files call `.show()` under pytest's Windows QPA (a real window
      flashes): QWidget ones (`test_default_settings_editor`, `test_transitions_tab_setup`, `test_widgets_tab_setup`,
      `test_visualizer_alignment`, `test_main_run_lifetime`, `test_spectrum_shaping_current`) can use
      `WA_DontShowOnScreen`; the QtQuick pixel tests (`test_qtquick_*`, `test_quit_request_render_thread_gil`) need GL,
      so move them to the hidden QQuickRenderControl pattern (`tools/onboarding_preview_foundry.py:_HiddenQuickScene`)
      or an offscreen subprocess.
- [ ] **Context menu on very short displays.** The menu (now 9 rows plus Save Image) is ~500 logical px tall; it clamps
      position but not size, so a display under ~510 logical px (e.g. 1024x768 at 150%) would overflow.
- [ ] **Spectrum extreme-viewport smoothness (pre-existing, not an audit regression).** The 2026-09-23 16:53–17:06 acceptance run saw significantly reduced visual smoothness for Spectrum at extreme viewport shapes. Pre-dates the audit; do not reopen VZ-04 over it. Watch item until investigated separately.

## Handoff and regression rules

When an accepted behavior changes, select only the relevant targeted tests and physical observations; do not re-accept unrelated OSD, Media or widget systems. Keep full superseding GODZIPs with the canonical three `.godzip/` files, manifest-backed replace/delete instructions and no temporary scripts or compiled artifacts. Test commands belong in chat, not an added documentation file.
