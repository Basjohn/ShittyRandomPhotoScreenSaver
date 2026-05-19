# Current Plan

Last updated: 2026-05-19

This file tracks active work only. Ongoing architecture truth belongs in the relevant reference docs, while dated severe/complex bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Prune validated work aggressively. Once a milestone is materially landed and no longer driving active decisions, collapse it into `Recently Completed / Not Active` instead of letting this plan become a changelog.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, widget-shadow, visualizer, or Qt effect rewrites unless the current task directly requires them.

## Active Tasks

1. CUSTOM edit mode phase-two follow-through.
Core value: build on the now-landed first-phase edit session without overpromising monitor semantics or unsafe widget-family resizing.
- [ ] Keep `Docs/Custom_Widget_Edit_Mode_Plan.md` as the detailed source of truth and update only the phase/checklist deltas here.
- [ ] Finish the remaining uniform-resize holdouts cleanly:
  - `imgur`
  - `spotify_visualizer`
- [ ] Land visualizer participation as move + safe uniform resize through `widgets/spotify_visualizer/card_geometry.py`, not shell-only stretching or mode-local hacks.
- [ ] Decide whether `ALL` widgets should later gain any multi-display coordinated edit affordance beyond the current explicit transfer block, without weakening `monitor` as the ownership field.

2. Post-CUSTOM hygiene and maintainability.
Core value: use the edit-mode landing as the next pruning point instead of letting docs/tests/residue grow stale again.
- [ ] Do the deferred memory/doc drift cleanup after the first meaningful CUSTOM phase is validated.
- [ ] Do the deferred test-maintainability pass after the first meaningful CUSTOM phase is validated.
- [ ] Reassess dormant Imgur raise-path cleanup only if edit-mode or overlay-system work reactivates that risk.

## Recently Completed / Not Active
- First-phase CUSTOM widget edit mode is landed: descriptor-owned edit capability metadata now identifies live widget attrs and safe resize families; `rendering/custom_layout_contract.py`, `rendering/custom_layout_manager.py`, and `widgets/edit_shell_widget.py` own the temporary shell session, display-local normalized persistence contract, save/cancel lifecycle, and `Ctrl + wheel` uniform resize for the vetted first-phase families.
- First-phase CUSTOM precision editing is now landed too: live edit shells clamp to the current display and snap against display borders, the standard 12px gutter, and peer widget shells without introducing any always-on runtime overhead once edit mode exits.
- CUSTOM position persistence is now a first-class settings value rather than an edit-mode side channel: persisted widget position now accepts `custom`, stronger snap guides now prefer gutter spacing before hard edge contact, save/reset now commit through the canonical widget rebuild path, and runtime rebuilds explicitly re-prime overlay fade coordination when the compositor is already live.
- CUSTOM foundation hardening is now materially landed too: edit-mode save/load now re-syncs against the live display screen binding instead of relying on constructor-time `_screen` state, legacy `serial|...|geom:...` MC display buckets are migrated/resolved through canonical display identity instead of exact stale geometry, and runtime widget rebuilds now clear stale fade participants before re-registering the current overlay set so non-media widgets do not remain queued forever after edit-mode exit.
- Phase-two CUSTOM cross-display ownership transfer is now landed for numbered-monitor widgets: edit shells can hand off between displays during the session, save mutates the authoritative `monitor` field plus destination display geometry, `ALL` widgets show an explicit locked affordance instead of silently collapsing their routing semantics, and save now triggers a clean widget rebuild across display instances.
- Phase-two CUSTOM uniform resize is now landed for the text/card service families that already had safe authored size hooks: `reddit`, `reddit2`, and `gmail` now resize through shared size-payload contracts instead of shell-only geometry stretching.
- Explicit `CUSTOM` settings-slot UX is now landed for participating widget families: descriptor-owned position labels expose `Custom`, WidgetsTab disables that slot until real saved custom geometry exists, saving an edit session promotes the relevant widget-family position setting to `Custom`, and switching back to an authored position now truly clears runtime custom-rect authority without deleting the saved layout payload.
- Display-local CUSTOM layout persistence now reapplies through the shared widget/runtime seams rather than one-off widget hacks: `BaseOverlayWidget` honors `_custom_layout_local_rect`, `DisplayWidget` defers processed-image updates while an edit session is active, `WidgetManager` reapplies saved custom layouts after live widget refreshes, and the context menu now exposes enter/save/cancel edit-mode actions.
- CUSTOM widgets are now explicitly outside the legacy widget-stacking system while `position == Custom`, so authored stack offsets no longer compete with committed CUSTOM geometry during rebuild/reveal.
- CUSTOM authored-route reset is now landed as a real saved contract: last known non-`Custom` position/monitor routes are persisted under the widgets map, the edit-mode context menu exposes a global authored-layout reset action, and that reset clears CUSTOM geometry then restores the saved authored routing through a clean rebuild instead of shell-only guessing.
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
- Detailed CUSTOM layout/edit-mode design still lives in `Docs/Custom_Widget_Edit_Mode_Plan.md`. Do not duplicate that design prose here; keep only live implementation deltas in the active section above.
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
