# SRPSS | Current Plan

## Guided Setup / Quick Start (ACTIVE)

Execution plan and live checklist: `Docs/Future_Work/Guided_Setup.md`. Operator review 2026-09-27, open items:

- [ ] **Seams, remaining audit.** Buckets, every Settings `QListWidget`, the content area and action buttons are now
      painted. Still QSS-drawn and to be zoom-checked: sidebar/group-box frames (`panel_border` rules in
      `ui/settings_theme.py`), StyledComboBox and its popup (2px, 14-18px radius), line edits, the generic QPushButton.

## Runtime audit 2026-09-22 | accepted 2026-09-23/24

`Docs/Future_Work/Runtime_Audit/` holds the register (00, including the accepted-items table with commits and closing evidence), item detail (01–05), structure and the considered-and-rejected list (06), historical-bug constraints (07) and the open-item evidence (08). The whole admitted queue (TX-01/02, LC-05/06, PR-01/03, PR-04 Stages A+B, PW-01/02/03-Clock/05, VZ-01/03/04/05) is accepted from the 2026-09-23 19:29–19:35 run, earlier physical runs and automated bars; the 19:29 trace also exposed and closed a TX-01 duplicate Glass geometry build.

- Watch: PW-04 Feed model reset (trigger: FEEDS Custom 2–4 or NEWS physical testing shows delegate/artwork churn; a NEWS card republishes once per publisher result). Parked: PR-02 (DC-04 stays documented), PR-01 resolve memo, PR-07, ST-01/02, VZ-05 epoch cache, VZ-07. Closed: LC-01, PR-05, PW-06, PW-03 Media, the prefetch double batch.

## Memory and handles | open development items

- [ ] **ImageWorker lean entry (R-99).** The ImageWorker re-imports the whole app graph on `spawn` (~1,060 modules). A lean worker entry could save ~100 MB resident, but it must be validated under Nuitka multiprocessing first.
- [ ] **Watch (low priority, not visible): scaled prefetch holds the GIL on the background CPU lane.** `QImage.scaled` runs for up to ~70 ms per 4K derivative while holding the GIL. It is not a stutter: overnight on 2026-09-25 the Visualizer logical runtime skipped 125 of 1,812,107 steps (0.007%). R-99 already halved the scaling work. Measure on the next `--perf` run before acting: seconds with `dt_max_ms` > 25 in `[PERF_HUD]`, their overlap with `Scaled prefetch` lines in `screensaver_cache.log`, and `skipped_deadlines` in `[SPOTIFY_VIS][LOGICAL] Runtime stopped`. Only if overlap remains material, move the scaling off the GIL with identical output.
- [ ] **Gmail refresh adds ~1.5 main-process handles per refresh.** The +18–25 handles/h slope tracks the Gmail cadence. Classify the type with `--handle-attribution`, then fix at the owner.

## Known failing tests and anomalies (tracked until resolved)

Each stays here until fixed or explicitly retired; do not treat it as noise in a gate. Physical validation lives with each feature's own doc, not here.

- [ ] **One red present before 2026-09-26's FEEDS work (Windows, whole widgets/settings gate):**
  - `test_qtquick_transition_parameter_defaults.py::test_sparse_crumble_uses_canonical_piece_count_and_complexity`: the canonical Crumble `crack_complexity` default is 11.0 but Settings and the resolver cap it at 2.0. Operator decision: was 1.1 meant?
- [ ] **Light-theme circle checkboxes.** The circle indicators are fixed white SVGs (`ui/assets/circle_checkbox_*.svg`,
      thin black under-stroke only). On Brushed Nickel, Linen Sage, Pearl Blush and Polished Chrome they are low
      contrast everywhere (Settings, wizard, popups). Make them theme-aware (e.g. theme-coloured indicators).
- [ ] **Colour picker inputs.** Qt's colour dialog spin boxes and HTML field inside the (now themed) picker still use
      Qt's default white inputs; bind the Settings spin box / line edit styles there.

- [ ] **Tests that show real windows.** `tests/test_qtquick_context_menu.py::test_retained_context_menu_draws_real_quick_pixels_and_clamps`
      calls `QQuickWindow.show()` under pytest's Windows QPA, flashing a real window. Move such pixel tests to an
      offscreen subprocess (pattern: `tests/test_onboarding_flow.py::test_hovering_transition_rows_inside_settings_does_not_scroll`)
      and sweep `tests/` for other `.show()` calls.
- [ ] **Context menu on very short displays.** The menu (now 9 rows plus Save Image) is ~500 logical px tall; it clamps
      position but not size, so a display under ~510 logical px (e.g. 1024x768 at 150%) would overflow.
- [ ] **Spectrum extreme-viewport smoothness (pre-existing, not an audit regression).** The 2026-09-23 16:53–17:06 acceptance run saw significantly reduced visual smoothness for Spectrum at extreme viewport shapes. Pre-dates the audit; do not reopen VZ-04 over it. Watch item until investigated separately.

## Handoff and regression rules

When an accepted behavior changes, select only the relevant targeted tests and physical observations; do not re-accept unrelated OSD, Media or widget systems. Keep full superseding GODZIPs with the canonical three `.godzip/` files, manifest-backed replace/delete instructions and no temporary scripts or compiled artifacts. Test commands belong in chat, not an added documentation file.
