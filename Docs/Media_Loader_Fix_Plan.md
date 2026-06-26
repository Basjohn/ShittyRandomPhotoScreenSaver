# Media Loader Fix Plan

## Status

- [x] Root-cause patch implemented
- [x] Settings-sidecar diagnostic implemented through the existing `--set` family
- [x] Focused regression bars implemented
- [ ] Manual multi-display validation pending

## Problem Shape

Opening **Widgets -> Visualizers** first could build Media as a dependency without hydrating Media from persisted settings. A later routine save could then serialize construction defaults such as `media.enabled=false`. The same settings pass could also leave visualizer preset/custom visibility derived from construction state until a user moved the preset control.

The same runtime evidence showed a separate geometry fault: visualizer `Custom` creation could borrow the single saved rectangle from a different display bucket and seed an invalid top-left/foreign shape. That behaviour was a fallback, not a valid recovery path.

## Implemented Contract

- [x] Media and Visualizers settings ownership is split.
  - `load_media_settings()` / `save_media_settings()` own only Media controls and the `media` settings key.
  - `load_visualizer_settings()` / `save_visualizer_settings()` own only visualizer controls and the `spotify_visualizer` settings key.
- [x] `WidgetsTab` now tracks built sections separately from hydrated sections.
  - Built is not treated as loaded.
  - Unhydrated sections preserve their existing persisted mapping during save collection.
  - Blocked writes log loudly as `[WIDGETS_HYDRATION][WARNING]`.
- [x] Visualizer preset visibility is driven after visualizer state hydration rather than from construction defaults.
- [x] Visualizer `Custom` geometry priming is exact-bucket only.
  - Exact local bucket: apply the saved committed rect.
  - Foreign/sole bucket: reject and suppress creation rather than borrowing geometry.
  - Missing local custom rect: fail closed and leave saved data untouched.
- [x] The R-26 participation/recheck distinction remains intact.
  - Sleeping/non-participating displays still use the existing cautious delayed route.
  - The removed path is only the cross-display foreign-rectangle fallback.
- [x] Media edit shells expose **Reset Visualizer** by default when a safe visualizer reset is possible.
  - The reset creates or restores a visualizer edit shell rect inside the active edit session.
  - If live capture is unavailable, a transparent placeholder rect is created so the user can still position/resize/save a recovery rect.
  - The reset does not clear visualizer `Custom` route/geometry authority, save settings, exit edit mode, or request a runtime reload by itself.
  - Media settings and visualizer mode/preset/style settings are preserved.
  - The normal edit-mode Save action remains the only commit path for the recovered rect.
  - The reset logs as a warning-level `[CUSTOM_LAYOUT] action=recover_visualizer_edit_rect` event.

## Regression Coverage

- [x] `tests/test_widgets_tab.py`
  - Visualizers-first lazy hydration preserves Media state.
  - Media-first and Visualizers-first saves preserve the other section.
  - Lazy section save collection does not serialize unhydrated construction defaults.
- [x] `tests/test_visualizer_settings_plumbing.py`
  - Exact custom buckets still apply.
  - Foreign saved custom rectangles are rejected.
  - Duplicate/foreign custom fallback no longer creates a widget from the wrong bucket.
- [x] `tests/test_widget_manager_refresh.py`
  - Remote custom reconcile rejects foreign saved rectangles.
  - Requested-target recheck behaviour remains covered.
- [x] `tests/test_custom_layout_manager.py`
  - Media-shell **Reset Visualizer** recovers an edit-mode visualizer shell without clearing custom authority.
  - Missing-live-widget recovery creates a transparent shell from the saved exact-bucket rect without saving or reloading.
  - Visualizer mode/preset/style and Media custom layout remain intact.

## Manual Validation

Run:

```text
python main.py --fresh --set --life --geo --viz
```

- [ ] Start with Media enabled, Visualizer enabled, and a curated visualizer preset active.
- [ ] Open Settings directly into **Widgets -> Visualizers**.
- [ ] Do not touch Media.
- [ ] Close Settings and allow the rebuild.
- [ ] Confirm Media remains enabled.
- [ ] Confirm the visualizer remains on the same mode/preset.
- [ ] Confirm Custom-only visualizer controls do not appear for curated presets.
- [ ] Repeat with Visualizer in `Custom`.
- [ ] Repeat with the requested visualizer display sleeping/unavailable if practical.
- [ ] Confirm no foreign-bucket rectangle is applied.
- [ ] In edit mode, use **Reset Visualizer** from the Media shell.
- [ ] Confirm edit mode stays open and a visualizer shell rect appears.
- [ ] Confirm Media and visualizer appearance/preset remain intact.
- [ ] Save the edit session and confirm the recovered visualizer appears on the next runtime build.

## Non-Goals

- Do not solve U-09 post-replay runtime shape authority here.
- Do not change audio capture, visualizer rendering, or preset payloads.
- Do not weaken display-participation safeguards.
- Do not replace the removed fallback with silent migration, invented geometry, or arbitrary-owner placement.
