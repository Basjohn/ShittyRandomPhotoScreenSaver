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

- No active implementation task is currently queued in this file.
- Next work should be selected from unresolved audit P1/P2 items with clear tests and bounded risk, not broad speculative rewrites.

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
