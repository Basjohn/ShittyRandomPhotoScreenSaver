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

1. Cleanup the Spotify-dependent setup/reconcile boundary.
Core value: this is still the highest-leverage runtime seam for future widget work, startup stability, and custom-layout reliability.
- [ ] Audit `rendering/widget_setup_all.py` for responsibilities that can move back into descriptor-owned or manager-owned helpers without changing runtime behavior.
- [ ] Make remote-anchor / dependent-widget setup order more explicit where Media, visualizer, volume, and mute still rely on subtle creation timing.
- [ ] Keep the guardrail that ordinary factory-backed widgets extend descriptor metadata first, not handwritten setup branches.
- [ ] Do not change visualizer render/audio behavior as part of this cleanup; this task is setup/reconcile hardening only.

2. Add a clearer startup/close quiesce boundary.
Core value: reduce teardown/startup churn by stopping new work before display/compositor shutdown proceeds.
- [ ] Audit shutdown entry in engine/display/widget layers for timers, deferred single-shots, and late settings-driven refresh paths that can still enqueue work during close.
- [ ] Define a narrow “quiescing” contract that stops new widget/service/runtime work before compositor/display teardown.
- [ ] Preserve current runtime behavior and avoid broad focus/compositor rewrites; this is a work-suppression boundary, not a rendering redesign.
- [ ] Add targeted regression coverage around any new quiesce hook before widening it.

3. Tighten `WidgetsTab` maintainability for future widget additions.
Core value: keep adding widgets cheap by continuing to move standard UI ownership into descriptor-owned metadata rather than `WidgetsTab` branches.
- [ ] Look for any remaining standard widget-section metadata in `ui/tabs/widgets_tab.py` that still belongs in `rendering/widget_descriptors.py`.
- [ ] Keep special cases explicit only where the descriptor contract genuinely cannot express the behavior cleanly.
- [ ] Preserve the current CUSTOM-lock / revert semantics while simplifying ownership, not by flattening special cases into opaque tables.

4. Finish the deferred documentation and test-hygiene cleanup.
Core value: the milestone is landed, so docs and tests should now read as current contracts rather than rollout archaeology.
- [ ] Refresh long-lived reference docs after each cleanup item above if ownership or behavior claims move.
- [ ] Do the deferred memory/doc drift cleanup now that the runtime validation is materially cold.
- [ ] Do the deferred test-maintainability pass now that the runtime validation is materially cold.

5. Parallelism policy for future performance work.
Core value: do not add threads speculatively. Any further parallelism should be profiling-driven and respect the current UI-thread / pure-compute boundary.
- [ ] If performance work is reopened, profile first and identify a real hotspot before changing thread/process counts.
- [ ] Prefer moving isolated pure-compute kernels or process-safe workloads, not Qt/UI/OpenGL ownership paths.
- [ ] Treat visualizer mode work as eligible for more off-thread compute only when the work can be expressed as snapshot-in / result-out without thread-affinity side effects.
- [ ] Treat another process as more likely than another generic Python thread if a future hotspot is both heavy and sufficiently isolated.

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
