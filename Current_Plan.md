# Current Plan

Last updated: 2026-05-14

This file tracks active work only. Completed implementation details belong in `Docs/Historical_Bugs.md` or the relevant reference docs, not here.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, widget-shadow, visualizer, or Qt effect rewrites unless the current task directly requires them.

## Active Tasks

1. Widget descriptor / registry system.
Core value: highest cross-project payoff now that the risky visualizer structural work is substantially landed.
- Why this is first:
  - it reduces multi-file surgery whenever a widget is added, renamed, gated, or moved,
  - it gives startup policy, widget factory registration, and settings composition a shared source of truth,
  - it is the strongest audit-derived architectural improvement that is not just cleanup.
- Implementation shape:
  - establish a canonical descriptor surface for widget identity, enablement, startup category, factory ownership, settings-tab ownership, and runtime capabilities,
  - landed first slice: factory-backed widget family metadata now lives in `rendering/widget_descriptors.py`, and `rendering/widget_setup_all.py` consumes that registry for clock/weather/media/reddit/imgur/gmail parity,
  - next slice: extend descriptor ownership into settings-tab ownership / capabilities instead of only runtime setup metadata,
  - keep legacy settings keys and widget ids stable,
  - avoid parallel registries; one descriptor layer should become the source of truth.
- Required validation:
  - targeted widget-manager / startup-path tests,
  - descriptor registration tests,
  - doc refresh in `Spec.md`, `Index.md`, and `Docs/10_WIDGET_GUIDELINES.md` if ownership moves.

2. Shared async / service-backed widget contract.
Core value: highest reuse payoff after the descriptor layer.
- Why this is second:
  - Gmail, Weather, Reddit, and similar widgets still repeat fetch scheduling, cache display, retry timers, transition-aware deferral, and fetch-in-flight guards,
  - consolidating that contract reduces repeated lifecycle fragility without changing each widget’s authored UI.
- Implementation shape:
  - define one shared contract for background refresh scheduling, in-flight guards, deferred apply around transitions, cache-first fallback, and timer cleanup,
  - move only the shared lifecycle mechanics first; keep widget-owned rendering and provider logic local,
  - prefer adapting existing proven seams over inventing a new manager hierarchy.
- Required validation:
  - targeted widget tests for Gmail/Weather/Reddit timing and cache behavior,
  - transition deferral coverage where the shared contract touches image-change boundaries.

3. Descriptor-driven widget settings composition.
Core value: strong follow-through once descriptors exist.
- Why this is third:
  - it reduces drift between widget registration, settings tabs, defaults, and runtime ownership,
  - it makes future widget additions cheaper and less error-prone.
- Implementation shape:
  - derive settings-tab composition and widget-facing metadata from the descriptor layer where sensible,
  - preserve current user-facing layout and settings keys unless a deliberate migration is planned.

4. Stronger transition registry / descriptor layer.
Core value: medium-high architecture payoff after widget descriptors.
- Why this matters:
  - transitions still have scattered ownership around registry, startup warmup, and enabled-pool selection,
  - a stronger descriptor layer would reduce drift and make future transitions easier to add safely.

5. Extension-path contract tests and targeted test maintainability.
Core value: supporting work that pays off once Tasks 1–4 are in motion.
- Scope:
  - add extension-path tests around descriptor/registry contracts,
  - split oversized visualizer/settings plumbing tests only where it directly improves safety for active refactors,
  - keep test work tied to active architecture changes rather than doing a broad cleanup campaign.

## Recently Completed / Not Active
- Visualizer settings-model residue reduction in `core/settings/models/_spotify_visualizer.py` is substantially landed and documented.
- Visualizer coordinator residue reduction in `widgets/spotify_visualizer_widget.py` plus extracted seams (`activation_runtime.py`, `runtime_config.py`, `mode_transition.py`, `tick_helpers.py`) is substantially landed and documented.
- Visualizer overlay split Task 3 slices `3A` through `3D` are substantially landed and documented:
  - passive diagnostics,
  - common uniform upload,
  - render dispatch,
  - frame shell.
- Do not reopen those tracks as active work unless a concrete regression or a clearly higher-value follow-through appears.

## Watchlist
- While any visualizer work remains active, first-bar / first-frame authority and settings/preset drift stay on the watchlist by default. Do not remove them from active watch coverage until the visualizer track is fully complete.
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
- Gmail/OAuth is not an active blocker for planning purposes. The threading/test seam is closed enough; do not hold the larger architecture queue on manual Gmail validation.
- The stale live capture block-size regression is fixed and confirmed in logs: live mode switches renegotiate `128` for `spectrum` and `256` for `devcurve` without waiting for a settings-dialog restart.
- Recent long-run logs do not show a new first-bar / bleed / stale-generation failure. Visualizer performance looks good enough to leave as watch work rather than the active priority, provided later runs do not show persistent settled-runtime drift.
- The curated/custom preset drift family stays a standing watch item during settings-model refactors: preserve CLEAR-then-APPLY semantics and do not reintroduce a second post-overlay merge phase or entry-point-specific fallback path.
- Startup mode truth and shader warmup are now aligned around the resolved startup mode. Keep watching for any reappearance of cold-start replay misses or legacy `spectrum` assumptions in logs.
- The overlay cold-reset path should preserve guardrails even if the GL object is reused. If a reused overlay ever reintroduces stale activation/generation state, the first-frame guard warning should make that visible immediately in logs.

## Deferred / Not Active
- Imgur raise-path cleanup/testing is not active work while Imgur remains inactive. Revisit only if the widget is reactivated or if a shared overlay-system change would otherwise leave the dormant path stale.
- `card_height.py` centralization is not active work. Revisit only if a focused sizing bug justifies it.
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
