# SRPSS | Current Plan

## Guided Setup / Quick Start (ACTIVE, not started)

Execution plan and live checklist: `Docs/Future_Work/Guided_Setup.md`.

## Runtime audit 2026-09-22 | accepted 2026-09-23/24

`Docs/Future_Work/Runtime_Audit/` holds the register (00, including the accepted-items table with commits and closing evidence), item detail (01–05), structure and the considered-and-rejected list (06), historical-bug constraints (07) and the open-item evidence (08). The whole admitted queue (TX-01/02, LC-05/06, PR-01/03, PR-04 Stages A+B, PW-01/02/03-Clock/05, VZ-01/03/04/05) is accepted from the 2026-09-23 19:29–19:35 run, earlier physical runs and automated bars; the 19:29 trace also exposed and closed a TX-01 duplicate Glass geometry build.

- Watch: PW-04 Feed model reset (trigger: FEEDS Custom 2–4 or NEWS physical testing shows delegate/artwork churn; a NEWS card republishes once per publisher result). Parked: PR-02 (DC-04 stays documented), PR-01 resolve memo, PR-07, ST-01/02, VZ-05 epoch cache, VZ-07. Closed: LC-01, PR-05, PW-06, PW-03 Media, the prefetch double batch.

## Memory and handles | open development items

- [ ] **ImageWorker lean entry (R-99).** The ImageWorker re-imports the whole app graph on `spawn` (~1,060 modules). A lean worker entry could save ~100 MB resident, but it must be validated under Nuitka multiprocessing first.
- [ ] **Watch (low priority, not visible): scaled prefetch holds the GIL on the background CPU lane.** `QImage.scaled` runs for up to ~70 ms per 4K derivative while holding the GIL. It is not a stutter: overnight on 2026-09-25 the Visualizer logical runtime skipped 125 of 1,812,107 steps (0.007%). R-99 already halved the scaling work. Measure on the next `--perf` run before acting: seconds with `dt_max_ms` > 25 in `[PERF_HUD]`, their overlap with `Scaled prefetch` lines in `screensaver_cache.log`, and `skipped_deadlines` in `[SPOTIFY_VIS][LOGICAL] Runtime stopped`. Only if overlap remains material, move the scaling off the GIL with identical output.
- [ ] **Gmail refresh adds ~1.5 main-process handles per refresh.** The +18–25 handles/h slope tracks the Gmail cadence. Classify the type with `--handle-attribution`, then fix at the owner.

## Known failing tests and anomalies (tracked until resolved)

Each stays here until fixed or explicitly retired; do not treat it as noise in a gate. Physical validation lives with each feature's own doc, not here.

- [ ] **Three reds present before 2026-09-26's FEEDS work (Windows, whole widgets/settings gate):**
  - `test_qtquick_transition_parameter_defaults.py::test_sparse_crumble_uses_canonical_piece_count_and_complexity`: the canonical Crumble `crack_complexity` default is 11.0 but Settings and the resolver cap it at 2.0. Operator decision: was 1.1 meant?
  - `test_visualizer_settings_body_dormancy.py::test_pill_model_is_setup_plus_enabled_in_canonical_order`: the expected pill order predates the current modes (`sphere`).
  - `test_widget_theme_link_and_asset_contract.py::test_lazy_theme_pages_refresh_without_polling_or_cross_tab_theme_owner`: rejects the `QTimer` import now in the themes/defaults Settings code.
- [ ] **Spectrum extreme-viewport smoothness (pre-existing, not an audit regression).** The 2026-09-23 16:53–17:06 acceptance run saw significantly reduced visual smoothness for Spectrum at extreme viewport shapes. Pre-dates the audit; do not reopen VZ-04 over it. Watch item until investigated separately.

## Handoff and regression rules

When an accepted behavior changes, select only the relevant targeted tests and physical observations; do not re-accept unrelated OSD, Media or widget systems. Keep full superseding GODZIPs with the canonical three `.godzip/` files, manifest-backed replace/delete instructions and no temporary scripts or compiled artifacts. Test commands belong in chat, not an added documentation file.
