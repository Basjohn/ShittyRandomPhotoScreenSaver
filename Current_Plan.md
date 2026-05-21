# Current Plan

Last updated: 2026-05-21

This file tracks active work only. Ongoing architecture truth belongs in the relevant reference docs, while dated severe/complex bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Prune validated work aggressively. Once a milestone is materially landed and no longer driving active decisions, collapse it instead of letting this plan become a changelog.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, widget-shadow, visualizer, or Qt effect rewrites unless the current task directly requires them.

## Active Tasks

1. Spotify-dependent post-parity runtime validation.
Core value: keep the now-landed display split and resize parity honest under real runtime usage before reopening more complex CUSTOM work.
- [ ] Re-test the exact normal-build runtime family:
  - [ ] visualizer moved to a different display from Media in `Custom`
  - [ ] Media moved cross-display while Volume is left untouched
  - [ ] visualizer still hides with Media after separate-display save/reload
  - [ ] visualizer CUSTOM mode/preset changes still adapt card width/height while preserving committed top-left/display ownership
  - [ ] non-media widgets still fade/reveal after CUSTOM save
  - [ ] no volume artifact / no stale same-display visualizer fallback
- [ ] Re-test the new duplicate-instance affordance:
  - [ ] `ALL` widgets with live duplicates show a local `×` remove affordance only during edit mode
  - [ ] removing one duplicate and saving promotes the survivor into a single-display `Custom` route cleanly
- [ ] Run the same CUSTOM save/reload smoke in the MC profile once the normal build stays stable.
- [ ] If the runtime family stays cold, prune this milestone instead of letting “recently landed” Spotify work linger in active tasks.

2. Post-CUSTOM hygiene and maintainability.
Core value: use the parity landing as the next pruning point instead of letting setup/routing helpers and supporting docs drift again.
- [ ] Keep `Docs/Custom_Widget_Edit_Mode_Plan.md` as the detailed source of truth and update only live deltas there when runtime validation forces another contract change.
- [ ] If another Spotify-dependent regression appears, tighten the setup/reconcile boundary in `rendering/widget_setup_all.py` before widening any feature work.
- [ ] Do the deferred memory/doc drift cleanup after the Spotify-dependent parity path is validated.
- [ ] Do the deferred test-maintainability pass after the Spotify-dependent parity path is validated.

## Recently Completed / Not Active
- CUSTOM edit mode foundation is materially landed: global shell session, numbered-monitor transfer, display-local normalized persistence, authored-route reset, stable snapping/grid/dimming UX, and canonical rebuild/reapply behavior are all in place.
- CUSTOM move/resize parity is materially landed for the safe widget families: clocks, weather, media, Reddit, Gmail, Imgur, and Spotify dependents now participate through descriptor-owned edit contracts instead of shell-only hacks.
- `spotify_visualizer` now uses the intended routing-mode contract: outside `Custom` it remains exact `Follow Media` parity, while in `Custom` it owns its own numbered-display `position` / `monitor` and still stays content/visibility-anchored to Media.
- `spotify_volume` now has real uniform-resize parity while remaining media-owned: its CUSTOM save path cannot clobber Media's monitor/display ownership, and runtime positioning now honors its saved custom rect size instead of forcing the authored slider footprint.
- `ALL`-routed duplicate widget shells can now be collapsed intentionally during edit mode via a local `×` affordance on duplicate-capable shells; saving a single survivor promotes that widget cleanly into a numbered-display `Custom` route.
- Visualizer CUSTOM shell participation is materially landed: composited shell capture, edit-session pause/hide behavior, committed custom-rect authority, independent numbered-monitor transfer while editing, and explicit outer-card CUSTOM rect clamping in `widgets/spotify_visualizer/card_geometry.py` are all in place.
- Visualizer CUSTOM adaptive sizing is now landed as a scale-relative contract: edit shells use a maximum-envelope footprint for safe alignment, while runtime re-resolves live mode/preset card metrics and applies saved visualizer scale payloads instead of freezing the first captured CUSTOM size.
- Widget/service/transition descriptor work is materially landed: WidgetsTab section ownership, runtime capability metadata, shared service lifecycle seams, and transition registry ownership should stay closed unless a concrete regression appears.

## Watchlist
- While visualizer follow-through remains possible, first-bar / first-frame authority and settings/preset drift stay on the watchlist by default. Do not remove them from active watch coverage until the visualizer track is truly cold.
- Closure evidence to keep handy for that watch family:
  - tests:
    - `tests/test_spotify_visualizer_widget.py -k "first_frame_guard or before_first_overlay_push_logs_once_per_source_signature or runtime_switch_paths_reset_all_bleed_state_for_all_modes or mode_switch_synthetic_audio_matches_fresh_worker_after_reset or widget_manager_preset_cycle_discards_real_engine_bleed_state or mode_switch_discards_stale_audio_buffer_before_next_frame"`
    - `tests/test_spotify_visualizer_mode_transition.py`
    - `tests/test_ghost_isolation.py -k "TestOverlayModeResetIsolation"`
  - logs:
    - `FIRST_FRAME_GUARD`
    - `before_first_overlay_push`
    - `after_first_overlay_push`
    - `MODE_RESET_ASSERT`
    - `No technical config available`
- Gmail/OAuth is not an active blocker for planning purposes.
- The curated/custom preset drift family stays a standing watch item during settings-model refactors: preserve CLEAR-then-APPLY semantics and do not reintroduce a second post-overlay merge phase or entry-point-specific fallback path.

## Deferred / Not Active
- Detailed CUSTOM layout/edit-mode design still lives in `Docs/Custom_Widget_Edit_Mode_Plan.md`. Do not duplicate that design prose here; keep only live implementation deltas in the active section above.
- Legacy widget stacking is still intentionally active for authored anchor-based layouts. It is not a general removal candidate yet; only its interaction with `Custom` remains disabled by contract.
- Imgur raise-path cleanup/testing is not active work while Imgur remains inactive. Revisit only if the widget is reactivated or if a shared overlay-system change would otherwise leave the dormant path stale.
- Reassessing residual opacity-effect invalidation is not active work. Revisit only if a concrete shadow/effect corruption issue resurfaces.
- Further visualizer residue reduction is deferred. Only reopen `_spotify_visualizer.py`, `spotify_visualizer_widget.py`, or deeper `spotify_bars_gl_overlay.py` work if a concrete regression appears or a clearly higher-value feature cannot proceed safely without it.

## Documentation Rule
- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
----
######
