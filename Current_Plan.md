# SRPSS | Current Plan

## Guided Setup / Quick Start (ACTIVE)

Execution plan and live checklist: `Docs/Future_Work/Guided_Setup.md`. Operator review 2026-09-27, open items:

- [ ] **Seams, remaining.** Audited 2026-09-27: seams need a translucent border, and every QSS border token is opaque
      in all 56 themes except `slider.groove.border` (alpha 230), `tooltip.border` (220) and
      `control.button.pressed_border` (200, pressed state only). Zoom-check tooltips and slider grooves on a Glass
      theme; paint them if the joins show.
- [ ] **ImageWorker lean entry (R-99).** The ImageWorker re-imports the whole app graph on `spawn` (~1,060 modules). A lean worker entry could save ~100 MB resident, but it must be validated under Nuitka multiprocessing first.
- [ ] **Watch (low priority, not visible): scaled prefetch holds the GIL on the background CPU lane.** `QImage.scaled` runs for up to ~70 ms per 4K derivative while holding the GIL. It is not a stutter: overnight on 2026-09-25 the Visualizer logical runtime skipped 125 of 1,812,107 steps (0.007%). R-99 already halved the scaling work. Measure on the next `--perf` run before acting: seconds with `dt_max_ms` > 25 in `[PERF_HUD]`, their overlap with `Scaled prefetch` lines in `screensaver_cache.log`, and `skipped_deadlines` in `[SPOTIFY_VIS][LOGICAL] Runtime stopped`. Only if overlap remains material, move the scaling off the GIL with identical output.
- [ ] **Gmail refresh adds ~1.5 main-process handles per refresh.** The +18–25 handles/h slope tracks the Gmail cadence. Classify the type with `--handle-attribution`, then fix at the owner.

## Known failing tests and anomalies (tracked until resolved)

Each stays here until fixed or explicitly retired; do not treat it as noise in a gate. Physical validation lives with each feature's own doc, not here.

- [ ] **One red present before 2026-09-26's FEEDS work (Windows, whole widgets/settings gate):**
  - `test_qtquick_transition_parameter_defaults.py::test_sparse_crumble_uses_canonical_piece_count_and_complexity`: the canonical Crumble `crack_complexity` default is 11.0 but Settings and the resolver cap it at 2.0. Operator decision: was 1.1 meant?

- [ ] **Colour picker inputs.** Qt's colour dialog spin boxes and HTML field inside the (now themed) picker still use
      Qt's default white inputs; bind the Settings spin box / line edit styles there.

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
