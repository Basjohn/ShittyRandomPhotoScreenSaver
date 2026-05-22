# Current Plan

Last updated: 2026-05-22

This file tracks active work only. Ongoing architecture truth belongs in the relevant reference docs, while dated severe/complex bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Prune validated work aggressively. Once a milestone is materially landed and no longer driving active decisions, collapse it instead of letting this plan become a changelog.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, widget-shadow, visualizer, or Qt effect rewrites unless the current task directly requires them.

## Active Tasks

1. Post-milestone cleanup and watchful hardening.
Core value: the CUSTOM edit-mode / resize / settings milestone is now runtime-validated and should stay pruned; only high-signal cleanup or regression response work belongs here.
- [ ] Keep `Docs/Custom_Widget_Edit_Mode_Plan.md` as the detailed source of truth and record only genuine contract deltas there if another runtime regression forces a behavior change.
- [ ] If another Spotify-dependent regression appears, tighten the setup/reconcile boundary in `rendering/widget_setup_all.py` before widening feature work.
- [ ] Decide later whether Imgur needs matching CUSTOM-lock UX if direct size controls are ever surfaced in `WidgetsTab`.
- [ ] Do the deferred memory/doc drift cleanup now that the runtime validation is materially cold.
- [ ] Do the deferred test-maintainability pass now that the runtime validation is materially cold.

2. Parallelism policy for future performance work.
Core value: do not add threads speculatively. Any further parallelism should be profiling-driven and respect the current UI-thread / pure-compute boundary.
- [ ] If performance work is reopened, profile first and identify a real hotspot before changing thread/process counts.
- [ ] Prefer moving isolated pure-compute kernels or process-safe workloads, not Qt/UI/OpenGL ownership paths.
- [ ] Treat visualizer mode work as eligible for more off-thread compute only when the work can be expressed as snapshot-in / result-out without thread-affinity side effects.

## Recently Completed / Not Active
- Normal-build runtime validation is materially cold for the CUSTOM milestone: repeated save/reload/edit/settings runs now hold up for media, visualizer, volume, settings-side revert, duplicate handling, snapping/grid/dimming, and the guarded visualizer separate-display contract.
- CUSTOM edit mode foundation is materially landed: global shell session, numbered-monitor transfer, display-local normalized persistence, authored-route reset, stable snapping/grid/dimming UX, and canonical rebuild/reapply behavior are all in place.
- CUSTOM move/resize parity is materially landed for the safe widget families: clocks, weather, media, Reddit, Gmail, Imgur, and Spotify dependents now participate through descriptor-owned edit contracts instead of shell-only hacks.
- `spotify_visualizer` now uses the intended routing-mode contract: outside `Custom` it remains exact `Follow Media` parity, while in `Custom` it owns its own numbered-display `position` / `monitor` and still stays content/visibility-anchored to Media.
- `spotify_volume` now has real uniform-resize parity while remaining media-owned: its CUSTOM save path cannot clobber Media's monitor/display ownership, and runtime positioning now honors its saved custom rect size instead of forcing the authored slider footprint.
- `ALL`-routed duplicate widget shells can now be collapsed intentionally during edit mode via a local `×` affordance on duplicate-capable shells; saving a single survivor promotes that widget cleanly into a numbered-display `Custom` route.
- Visualizer CUSTOM shell participation is materially landed: composited shell capture, edit-session pause/hide behavior, committed custom-rect authority, independent numbered-monitor transfer while editing, and explicit outer-card CUSTOM rect clamping in `widgets/spotify_visualizer/card_geometry.py` are all in place.
- Visualizer CUSTOM adaptive sizing has been re-landed on the cleaner single-authority contract: non-`Custom` still uses widget-local `Follow Media` behavior, while `Custom` defers final geometry to `WidgetManager` plus `widgets/spotify_visualizer/card_geometry.py`.
- Invalid visualizer `Custom + ALL` routing is now guarded at both save and startup: edit-mode save refuses to persist multi-display `ALL` survivors as an independent Custom visualizer route, and startup/create-time recovery will infer a single owner display from saved CUSTOM layout when possible instead of duplicating the visualizer across every screen.
- Base media settings remain canonical even in `Custom`: live refresh now reapplies media `font_size`, `artwork_size`, and rounded-artwork-border settings, while CUSTOM resize stays an overlay scale contract instead of replacing those authored inputs.
- Settings-dialog CUSTOM size-lock UX is materially landed: affected size controls disable only while the owning widget family is `Custom`, the orange revert notice routes through a styled popup, and both runtime/context-menu reset and settings-dialog revert now share the same authored-layout restore mutation helper.
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
