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

1. Visualizer/media display-split stabilization.
Core value: finish the routing-mode contract cleanly before layering more parity work on top of it.
- [ ] Keep `spotify_visualizer` independently routable only while its effective slot is `Custom`; outside `Custom` it must remain exact `Follow Media` parity.
- [ ] Validate the real persisted settings path, not just stub maps: `spotify_visualizer.position == Custom` must survive save/reload in both runtime and tests.
- [ ] Keep `spotify_volume` media-owned, but make its CUSTOM save path unable to clobber Media's monitor/display ownership.
- [ ] Ensure media-owned dependents auto-follow Media's final display on save/reload instead of creating fade/reveal faults when only Media moves.
- [ ] Re-test the exact runtime failure family after each change:
  - [ ] visualizer moved to a different display from Media in `Custom`
  - [ ] Media moved cross-display while Volume is left untouched
  - [ ] non-media widgets still fade/reveal after CUSTOM save
  - [ ] no volume artifact / no stale same-display visualizer fallback

2. Remaining CUSTOM resize parity.
Core value: finish the last honest holdout only after the routing split and dependent-display contract are stable again.
- [ ] Keep `Docs/Custom_Widget_Edit_Mode_Plan.md` as the detailed source of truth and update only the live parity delta here.
- [ ] Make CUSTOM resize use plain scroll wheel only; do not require `Ctrl` as an additional modifier.
- [ ] Land `spotify_visualizer` uniform resize through `widgets/spotify_visualizer/card_geometry.py`, not shell-only stretching or mode-local hacks.
- [ ] Land `spotify_volume` uniform resize parity with a clean contract if it remains part of the same authored control cluster; do not broaden it casually into render/runtime logic changes.
- [ ] Keep media dependents (`spotify_visualizer`, `spotify_volume`, `mute_button`) on the watchlist until move/rebuild/reveal/resize behavior is fully parity-safe.

3. Post-CUSTOM hygiene and maintainability.
Core value: use the edit-mode landing as the next pruning point instead of letting docs/tests/residue grow stale again.
- [ ] Do the deferred memory/doc drift cleanup after the first meaningful CUSTOM phase is validated.
- [ ] Do the deferred test-maintainability pass after the first meaningful CUSTOM phase is validated.

## Recently Completed / Not Active
- CUSTOM edit mode foundation is materially landed: global shell session, numbered-monitor transfer, display-local normalized persistence, authored-route reset, stable snapping/grid/dimming UX, and canonical rebuild/reapply behavior are all in place.
- CUSTOM move/resize parity is materially landed for the safe widget families: clocks, weather, media, Reddit, Gmail, Imgur, and move-only Spotify dependents now participate through descriptor-owned edit contracts instead of shell-only hacks.
- Visualizer CUSTOM shell participation is materially landed: composited shell capture, edit-session pause/hide behavior, committed custom-rect authority, and independent numbered-monitor transfer while editing are all in place. Save/reload follow-through is still active work until separate-display rebuild parity is proven stable.
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
