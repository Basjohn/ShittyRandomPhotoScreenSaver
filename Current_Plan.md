# Current Plan

Last updated: 2026-05-18

This file tracks active work only. Ongoing architecture truth belongs in the relevant reference docs, while dated severe/complex bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Prune validated work aggressively. Once a milestone is materially landed and no longer driving active decisions, collapse it into `Recently Completed / Not Active` instead of letting this plan become a changelog.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, widget-shadow, visualizer, or Qt effect rewrites unless the current task directly requires them.

## Active Tasks

1. Custom widget edit mode groundwork.
Core value: use the now-cleaner widget/visualizer descriptor base to design the future CUSTOM layout path safely before implementation pressure arrives.
- [ ] Treat `Docs/Custom_Widget_Edit_Mode_Plan.md` as the detailed source of truth for this feature. Keep this section short and actionable.
- [ ] Decide the saved-coordinate contract for CUSTOM positions and sizes: logical/grid-first vs raw-pixel fallback, with explicit DPR and multi-monitor rules.
- [ ] Extend descriptor ownership for edit-mode capability flags: movable, resizable, axis constraints, and reset affordances.
- [ ] Define the edit-session lifecycle precisely: entry/exit, paused subsystems, safe edit shells/live-widget exceptions, and fade-back-in behavior.
- [ ] Define first-phase resize semantics per widget family, including which widgets can safely support whole-widget resize only versus directional resize.
- [ ] Decide how proportional font/content scaling should behave during custom resize so recovery/reset remains predictable.

2. First-phase candidate audit for CUSTOM layout/edit mode.
Core value: avoid promising drag/resize behavior on widgets whose authored runtime contracts are not ready for it.
- [ ] Identify the safest first-phase movable widgets.
- [ ] Identify the safest first-phase resizable widgets.
- [ ] Explicitly record which widgets should stay position-only or non-participating in phase one and why.
- [ ] Use the visualizer outer-card geometry contract as the evaluation base for whether visualizer participation should begin as move-only, move-plus-scale, or remain deferred.

## Recently Completed / Not Active
- Extension-path contract tests and targeted maintainability work are materially landed for the recent architecture seams: lazy/programmatic `WidgetsTab` hydration, raw `DisplayWidget.set_image()` sync-entry behavior, and live visualizer geometry refresh-to-placement contracts now have focused regression coverage.
- DisplayWidget raw-image entry now has a single explicit synchronous processing path; the old presenter-owned sync processing branch is retired, and regression coverage now locks down the narrow legacy `set_image()` contract separately from the async pre-processed mainline.
- Visualizer outer card geometry contract is landed and validated in runtime plus focused tests; `card_geometry.py` now owns mode/preset-driven preferred height, blob-width reduction, and media-relative placement while stencil clipping stays separate.
- Widget descriptor base and ordinary `WidgetsTab` coordination cleanup are substantially landed, including Defaults migration, descriptor-owned section restore/bootstrap/build/load/save plumbing, and lazy/settings-entry hardening.
- Shared service-backed widget contract and final audit are substantially landed; Gmail/Reddit/Weather share the true lifecycle seams, while Imgur/Media/Mute/Spotify volume keep intentionally local canonical seams where their runtime contracts diverge.
- Transition registry / descriptor work is substantially landed and now owns ordinary transition identity, alias handling, selector ordering, hardware gating, random/cycle participation, compositor routing, and startup warmup metadata.
- Visualizer structural work is substantially landed across settings-model residue reduction, coordinator extraction, and overlay split slices `3A` through `3D`. Do not reopen unless a concrete regression or clearly higher-value follow-through appears.
- Do not reopen those tracks as active work unless a concrete regression or a clearly higher-value follow-through appears.

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
- The stale live capture block-size regression is fixed and confirmed in logs.
- Recent long-run logs do not show a new first-bar / bleed / stale-generation failure.
- The curated/custom preset drift family stays a standing watch item during settings-model refactors: preserve CLEAR-then-APPLY semantics and do not reintroduce a second post-overlay merge phase or entry-point-specific fallback path.
- Startup mode truth and shader warmup are now aligned around the resolved startup mode. Keep watching for any reappearance of cold-start replay misses or legacy `spectrum` assumptions in logs.
- The overlay cold-reset path should preserve guardrails even if the GL object is reused. If a reused overlay ever reintroduces stale activation/generation state, the first-frame guard warning should make that visible immediately in logs.

## Deferred / Not Active
- Detailed CUSTOM layout/edit-mode design now lives in `Docs/Custom_Widget_Edit_Mode_Plan.md`. Do not duplicate that design prose here; keep only live implementation work in the active section above.
- Imgur raise-path cleanup/testing is not active work while Imgur remains inactive. Revisit only if the widget is reactivated or if a shared overlay-system change would otherwise leave the dormant path stale.
- Reassessing residual opacity-effect invalidation is not active work. Revisit only if a concrete shadow/effect corruption issue resurfaces.
- Memory/doc drift cleanup is deferred until after the first meaningful CUSTOM edit-mode phase. Best scope then: resolve or retire phantom doc references, index any long-lived docs still worth keeping, and avoid creating a second sprawling audit.
- Test maintainability cleanup is deferred until after the first meaningful CUSTOM edit-mode phase. Best scope then: split oversized visualizer test files where the seams are now clearer, document justified raw-thread test probes, and review tiny stub-like tests for expand-or-delete decisions.
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
