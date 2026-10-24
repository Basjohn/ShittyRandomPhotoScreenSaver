# Settings buckets | single-active-context source repair candidate (2026-10-23)

**Status:** `[~]` SOURCE CANDIDATE, NOT NATIVE/OPERATOR ACCEPTED. This document records the implementation, evidence and outstanding validation. The controlling task remains [Current_Plan.md](../../Current_Plan.md) and the durable contract is [Settings_Bucket_Persistence_Contract.md](../Architecture/Settings_Bucket_Persistence_Contract.md). It does not supersede the original operator-held source audit (`SRPSS_Settings_Bucket_Persistence_End_to_End_Audit_2026-10-23.md`), which is outside this archive; absence of that external document does not remove its findings.

## Changed behavior, source owners

- `core/settings/ui_bucket_state.py`: pure path mutations/legacy projection permit **one active leaf plus required ancestors**; closing a parent retires hidden descendants. At Settings startup, project all stored open maps onto the admitted tab and selected pill; migrate stale multi-page maps deterministically (prefer a deepest nested current-pill leaf). A successful leave clears the prior context; a denied leave does not. `ui.basic_bucket_path` is the new canonical single-slot state for the Sources and Transitions tabs, whose buckets previously did not persist at all.
- `ui/settings_dialog.py`: project before lazy construction, keep active context on close/reopen, retire on successful tab changes, and project on settings reload. A target must construct successfully before the previous editing context is discarded. The existing semantic `ui.tab_state` still owns last pill/navigation selection; it is **not** another bucket expansion authority.
- `ui/tabs/widgets_tab.py`: one Widget leaf/ancestor path replaces independent per-section scopes; switching pills synchronously collapses all cached bucket bodies. Gmail remains a separate schema family but is globally retired when inactive. Reset/import differences are re-read; no preset values are touched.
- `ui/tabs/visualizers_tab.py`, `ui/tabs/visualizer_settings_context.py`, `ui/tabs/media/{builder_scaffold,technical_controls}.py`: remove per-dormant-mode remembered leaf behavior. Advanced and Technical root disclosures coordinate, do not persist speculative initial-builder callbacks, and retire opposite-root leaves. Active Custom/Technical children and their parents remain distinct from preset or visualizer-mode state.
- `ui/tabs/shared_styles.py`: unified **silent** closing, using actual QWidget parent ancestry to preserve the selected nested parent chain while closing unrelated live toggles, including lazily cached/hidden bodies. Uses existing `QSignalBlocker`, no timer, polling, extra refresh loop or QML.
- `ui/tabs/{sources,transitions}_tab.py`: explicit persistence for Sources Folders/Feeds and each applicable Transition Advanced bucket. No transition effect defaults or authored controls altered.
- `core/settings/default_settings.py`: canonical UI schema gains one empty `basic_bucket_path`; all existing bucket defaults remain closed and control defaults unchanged.

## Tests and evidence (headless)

- `python -m pytest -q --noconftest tests/test_settings_active_bucket_path.py tests/test_settings_bucket_single_open_contract.py -k 'not full_map_bucket_profile_projects_to_current_sparse_state_idempotently'`: **21 passed; one deselected** (the original full-map fixture is absent from this slim godzip; its test remains intact). No environment variables are used.
- Pure-state tests cover nested Steam parent-child pruning, legacy multi-open migration, Custom/Technical mode exclusion, idempotence, Sources/Transitions context changes and losing all opens after navigation.
- The test `tests/test_widgets_tab_current.py::test_widget_bucket_state_roundtrip` and the old outer-root assertions were updated to enforce the new expected policy. That real Qt test is **not run here** because PySide6 is absent; no claim of native integration success is made.
- A second source-only defaults/schema selection recorded **34 passed, four blocked solely by missing PySide6** (`test_sst_projection_never_opens_or_rewrites_installed_settings`, both `test_sst_projection_import_matches_fresh_profile_reset` parameters, and `test_fresh_reset_and_sst_replace_share_canonical_projection_and_custom_ownership`). These four remain testable on Windows, and were **not rewritten, suppressed or treated as passed**.
- All modified Python source and tests were syntax-compiled successfully.

## Native verification still required; do not mark [x]

1. Open Settings on EB (including Custom and Technical where available). Select a bucket, edit a colour/preset, close/reopen: same pill and active nested path must restore. Change pill or top-level tab and return: old unrelated buckets must be closed. Repeat with Setup and disabled families.
2. Steam and Feeds three-level parents, siblings and lazy bodies: switching cards must not resurrect a checked child inside a closed parent; opening another bucket must close unrelated live toggles. Confirm current tab scroll, dynamic rail termination and mixed DPI.
3. Sources Folders/Feeds and Transitions Advanced: each remembers only the active tab/pill path on genuine reopen, not when navigating away; verify Transition name/section identity for every transition with an Advanced bucket.
4. Reset to Defaults, SST/import, preset switching and Settings reload: no stale cached toggles, no lost custom values, no duplicated callbacks, and no active path restored to a disabled/deactivated page.
5. Denied leave (display-route, Quick Start Arrange, no-sources on close) must **not** clear the active path. A failed lazy tab builder must not clear it either. No GUI hitches, tick loops or frame-time regressions.
6. Windows native test selections: updated `test_settings_bucket_single_open_contract.py`, `test_widgets_tab_current.py`, `test_visualizer_settings_lazy_bodies_current.py`, `test_gmail_settings_roundtrip.py`, and a real SettingsDialog close/reopen/reload integration. Keep every test failure visible until diagnosed; do not bulk mark stale.

**24 October native evidence (PySide6, Windows, real SettingsDialog, not shown):** the full isolated suite passes
(737 files), including every selection in item 6, and `tests/test_settings_bucket_reopen_real_dialog.py` covers close/
reopen for Visualizer modes, Sources, Steam nested leaves, Widgets pill replacement and a legacy multi-mode map. Removing
the startup projection or leave-retirement alone does not break these scenarios: the tabs' own retirement on pill/tab
change and per-mode hydration enforce the same contract (layered, not single-owner). Items 3-5 and visual inspection
remain open.

**Known verification limitation:** No PySide6 in this container. Native signal ordering, QWidget ancestry under all builders, Qt paint/scroll/rail behavior and Settings reopen are **not visually confirmed**. The source implementation is offered for a local native agent to test and correct, not operator-approved finished UX.
