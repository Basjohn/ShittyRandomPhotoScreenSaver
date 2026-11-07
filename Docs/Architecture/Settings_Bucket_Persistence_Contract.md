# Settings bucket persistence

Only the active pill's editor context (or active tab where no pills exist) retains its last-open editing path for
reopening Settings. Inactive pills and unrelated tabs present as closed, including after lazy reconstruction. Nested
ancestors remain open only to expose the selected leaf. Fresh profiles start closed. Preset choice, current mode and
stored Settings values remain independent of disclosure state.

The Visualizer Advanced / Technical disclosures and their Technical leaves are retired (AC-23): no mode body builds
them (every mode is edited in its Studio), canonical defaults no longer declare their three maps, and the projection
drops a stored profile's old members once (`Persisted_Input_Compatibility.md`).

`core/settings/ui_bucket_state.py` owns canonical normalization and `project_settings_bucket_context` /
`retire_settings_bucket_context`. The Settings dialog and tab navigation apply that projection; shared bucket helpers
close unrelated live branches silently. Existing per-control maps remain the persistence schemas. Navigation does not
create a second context store, scheduler or polling owner. Connector rails derive from the visible hierarchy and do
not own persistence.

## Tabs and pills: one registry

`ui/settings_tabs.py` holds one `SettingsTabDescriptor` per top-level tab, in sidebar order: key, Title Case label,
lazy builder, `pill_of(view_state)`, `available(profile)`, `warm_in_background`, `reloads_with_settings` and
`pinned_bottom`. `SettingsDialog` derives everything tab-shaped from it: the tab keys and content-stack positions, the
builders, the sidebar, the background-warm list, the tabs a reload refreshes, and the editing-path pill. Construction
and `_reload_all_tab_settings` take the pill from the same `pill_of`, so both hand
`project_settings_bucket_context` the same (tab, pill) for the same view state. A new tab adds one descriptor and owns
its pill vocabulary there; nothing else in the dialog names it.

- **Profile gating:** `available(profile)` reads `SettingsProfile.current()`, which asks the one product-identity
  predicate (`core/mc.py`); a new product profile extends that predicate, never a second resolver. An unavailable
  tab is absent from the sidebar, the content stack and the tab-key mapping. No Settings surface compares the store's
  application name with a literal: "the MC build keeps Interaction Mode on" has one owner,
  `core.mc.interaction_mode_forced` / `effective_interaction_mode`, which the Display tab, Guided Setup and the
  runtime (context-menu lock and toggle) all call. Bar: `tests/test_mc_interaction_single_owner.py`.
- **Remembered tab:** `ui.last_tab_key` is the memory; positions are never persisted. Hiding a tab cannot shift a
  remembered one, and a remembered tab the profile hides keeps its memory while Settings opens on its first tab.
  `ui.last_tab_index` keeps its pre-Themes meaning and is written from the key through that legacy table.
- **Lazy bodies:** only the initial tab builds synchronously; `warm_in_background` tabs build after first paint,
  staggered and cancellable; every other tab builds when visited.
- **No hidden value owners:** a tab or mode body whose values another surface edits (the Visualizer Studios) keeps
  them in a value cache, never in hidden QWidgets. Each Visualizer mode body is the preset row with OPEN STUDIO, its
  3D Detail row where it has one, and one sentence; `_<prefix>_lazy_values` owns its body and technical (audio
  analysis) values (`ui/tabs/media/spec_mode_builder.py`). The page's shared Bar Appearance and Rainbow families are
  spec entries of each owning mode (non-body `bar_appearance` / `rainbow` buckets) held in the page's value cache
  `_visualizer_family_lazy_values` (`ui/tabs/media/visualizer_mode_binding.py`); the page builds no widget for them,
  and the Studio's family load writes that cache. Bar: `tests/test_visualizer_shared_families_spec.py`.
- **Reset and Import:** `_reload_all_tab_settings` is the one reset/import edge. It first re-derives the
  process-local active Settings and Widget themes from persistence (`rederive_active_themes`,
  `ui/settings_theme_selection.py`: startup's resolution against the built catalogs, persisting nothing), then
  reloads every `reloads_with_settings` tab, Themes included. Theme activation never subscribes to store writes,
  so an unchanged write cannot reach it (AC-07). Bar: `tests/test_settings_theme_rederive_real_dialog.py`.
- **Helper threads:** helper sites (cache clearing, feeds, Gmail, Steam, geocoding, Guided Setup) never build
  private ThreadManagers; they look up the app-shared one (`ThreadManager.require_app_shared`). Under a runtime that
  is the engine's; a Settings-only (CONFIG) session's dialog registers one helper manager for its lifetime and
  releases it when destroyed.

Regression coverage: `tests/test_settings_tab_registry_real_dialog.py` (registry derivation, pill agreement and
projection round trip per tab, profile gating, remembered tab, CONFIG helper manager) and
`tests/test_visualizer_studio_owned_values_real_dialog.py` (no hidden value owners; every body and technical value
round-trips through the cache), both on the real dialog.

## Coverage

Focused regression coverage lives in `tests/test_settings_active_bucket_path.py`,
`tests/test_settings_bucket_single_open_contract.py` and `tests/test_settings_bucket_reopen_real_dialog.py`: selected
context, nested ancestors, tab/pill changes, lazy reopening, migration and real-dialog round trips. Operator acceptance
of the persistence and connector-rail work is recorded in source control; any new defect enters `Current_Plan.md`.
