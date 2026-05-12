# Current Plan

Last updated: 2026-05-13

This file tracks active work only. Completed implementation details belong in `Docs/Historical_Bugs.md` or the relevant reference docs, not here.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, widget-shadow, visualizer, or Qt effect rewrites unless the current task directly requires them.

## Active Tasks

### 1. Audit Follow-Through: Startup / Cleanup / Stability (2026-05-11) — IN PROGRESS
- Prioritize startup-speed/startup-consistency and closing/cleanup stability items from the 2026-05-11 audit before lower-signal cleanup.
- Assessment update:
  - `rendering/widget_manager.py` already registers `_raise_timer` with `ResourceManager` when available and stops it in `cleanup()`. The remaining gap is regression coverage, not first-pass ownership wiring.
- First focus:
  - T-03 / T-04 coverage is now in place for synchronous overlay re-raise order, clock timezone-label re-raise, and `_raise_timer` cleanup.
  - V-07 is now closed: the reset-defaults toast owns its auto-dismiss timer and the early-close path is covered by targeted regression tests.
  - V-13 is now narrowed: the highest-count overlay cleanup paths are mostly explicit stop + parent-owned timer teardown, so this is no longer a broad "all deleteLater calls are suspect" task.
  - Risk Register P2 migration overhead note — keep an eye on settings-load migration cost if startup work touches that path.
- If these no longer produce worthwhile active tasks, next-best audit targets should come from unresolved P1/P2 items with clear tests and bounded risk, not broad speculative rewrites.

### 2. Settings Dialog IA / Terminology Follow-Through (2026-05-13) — IN PROGRESS
- `Hard Exit` has been renamed to `Interaction Mode` across the active runtime/UI/docs surface.
- Settings compatibility is preserved through a legacy alias migration from `input.hard_exit` to canonical `input.interaction_mode`.
- Widgets-tab regrouping has now landed for `Clock`, `Weather`, `Media`, `Reddit`, and `Imgur`, following the Gmail bucket pattern without reopening the historical construction-flicker path.
- Future settings-dialog regrouping should keep using `Docs/Settings_Dialog_Bucketing_Audit.md` instead of appending controls ad hoc.

## Watchlist
- Mute button fade-in reliability under startup event pressure.
- Transition random mode actual distribution vs expected uniform over long runtime.
- Settings destructive-flow checks: reset/import when touching settings architecture.
- Settings cache stale-read behavior after section/root writes.

## Deferred / Not Active
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
