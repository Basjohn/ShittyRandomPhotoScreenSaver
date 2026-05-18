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

1. Final shared async / service-backed widget audit.
Core value: finish the reuse/lifecycle sweep without flattening widget-specific behavior.
- [ ] Use the descriptor-owned service-runtime contract map to inspect remaining lifecycle duplication in Gmail/Reddit/Weather/Imgur/Media-adjacent widgets.
- [ ] Widen `widgets/service_widget_runtime.py` only where the contract is genuinely shared and already proven by behavior.
- [ ] Keep widget-local policy local when fetch/display/runtime semantics diverge.
- [ ] Re-validate targeted lifecycle behavior after each widening slice: deferral, fetch-in-progress guards, visible-fallback preservation, retry/refresh timers.

2. Extension-path contract tests and targeted test maintainability.
Core value: keep the registry/descriptor base safe without turning test work into a cleanup side quest.
- [ ] Add focused extension-path tests around descriptor/registry contracts as they stabilize.
- [ ] Add coverage for the specific lazy/settings entry paths that have now proven regression-prone.
- [ ] Split oversized tests only when it materially improves safety for an active refactor or a known flaky/opaque path.
- [ ] Keep this work coupled to active architecture changes, not broad test-file tidying.

## Recently Completed / Not Active
- Widget descriptor base is substantially landed:
  - factory-backed widget registry,
  - descriptor-owned `WidgetsTab` section build/load/save routing,
  - Defaults section migration,
  - descriptor-owned section-id restore, lazy bootstrap, and default section selection,
  - descriptor-owned subtab button/container plumbing for ordinary sections,
  - runtime capability and service-contract ownership.
- Ordinary `WidgetsTab` coordination cleanup is complete enough to retire as the main active track:
  - remaining inline behavior is now either genuinely special (`spotify_visualizer`, Gmail-specific buckets) or plain tab-local orchestration that is not worth flattening further right now.
- Settings entry / lazy restore hardening is substantially landed:
  - Media/Visualizers lazy-build dependencies are now descriptor-owned instead of relying on section order,
  - lazy dependency resolution tolerates mutual descriptor dependencies safely,
  - programmatic `SettingsDialog.widgets_tab` access stays narrow but now hydrates the descriptor-owned media/visualizer/defaults contract,
  - focused regressions cover Media-first restore, Visualizers-first restore, hidden/lazy dialog access, and media roundtrip integration.
- Shared service-backed widget contract is substantially landed:
  - transition-aware deferral,
  - fetch-in-progress guards,
  - manual refresh flow,
  - visible-fallback preservation,
  - local canonical cleanup seams for Weather, Imgur, Spotify volume, Media widget, and mute button.
- Visualizer settings-model residue reduction in `core/settings/models/_spotify_visualizer.py` is substantially landed and documented.
- Transition registry / descriptor layer is substantially landed:
  - canonical transition identity and legacy alias handling now live in `rendering/transition_registry.py`,
  - ordinary transition selector ordering is shared by the transitions tab and context menu,
  - engine cycle/random availability, hardware gating, factory-side random fallback, compositor program routing, and startup shader warmup now consume shared registry truth instead of parallel handwritten lists/maps.
- Visualizer coordinator residue reduction in `widgets/spotify_visualizer_widget.py` plus extracted seams (`activation_runtime.py`, `runtime_config.py`, `mode_transition.py`, `tick_helpers.py`) is substantially landed and documented.
- Visualizer overlay split Task 3 slices `3A` through `3D` are substantially landed and documented:
  - passive diagnostics,
  - common uniform upload,
  - render dispatch,
  - frame shell.
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
- Future custom widget edit mode is intentionally not active yet, but the guarded direction is now recorded:
  - enter/exit from the context menu,
  - temporarily replace live widgets with safe edit shells/bounds instead of full animated runtime behavior where needed,
  - pause transitions and visualizer work during edit mode,
  - support snapping/dragging while editing,
  - optional resize can be part of that mode if it stays descriptor-owned and widget-logical: `Ctrl + mouse wheel` should adjust widget-owned size axes rather than applying a blind global scale transform,
  - any widget that participates in edit-mode resize must also expose a clear settings-side size reset affordance for recovery,
  - save edited positions into a `CUSTOM` slot while preserving the current normal descriptor/grid positioning system as the fallback path,
  - keep `CUSTOM` greyed out/unavailable until real saved coordinates exist,
  - restore widgets with fade-in on edit completion,
  - validate DPR/multi-monitor adaptability explicitly before rollout; do not store brittle raw-pixel assumptions if a more portable logical/grid representation is viable,
  - do not force resize on widgets whose authored layout cannot safely express it through stable logical controls.
- Imgur raise-path cleanup/testing is not active work while Imgur remains inactive. Revisit only if the widget is reactivated or if a shared overlay-system change would otherwise leave the dormant path stale.
- `card_height.py` assessment is deferred, but now explicitly queued as future actionable work because the visualizer card sizing path still differs from peer overlay cards. When it becomes active, do it in this order:
  - audit where card height truth currently lives across `widgets/spotify_visualizer/card_height.py`, `widgets/spotify_visualizer_widget.py`, `widgets/spotify_visualizer/mode_transition.py`, `rendering/widget_manager.py`, and the GL overlay stencil/card shell seams,
  - decide whether visualizer card sizing should normalize toward the shared card-height behavior used by other widgets or remain intentionally special with clearer adapters,
  - if normalization is viable, extract the minimum shared seam without changing authored visualizer amplitude, border/stencil inset math, transition behavior, or first-frame authority,
  - if normalization is not viable, document the visualizer-specific sizing contract more explicitly and make adapter points first-class instead of implicit,
  - treat this as parity-or-improvement work only after running `tests/test_stencil_mask_alignment.py`, relevant visualizer widget/mode-transition subsets, and runtime log sweeps for `FIRST_FRAME_GUARD`, `before_first_overlay_push`, `after_first_overlay_push`, and `MODE_RESET_ASSERT`,
  - success means easier future card/layout work without breaking the visualizer’s stencil mask, painted-card border contract, or mode-specific perceived scale.
- Reassessing residual opacity-effect invalidation is not active work. Revisit only if a concrete shadow/effect corruption issue resurfaces.

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
