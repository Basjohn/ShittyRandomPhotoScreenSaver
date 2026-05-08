# Current Plan

Last updated: 2026-05-08

This file tracks active work only. Completed implementation details belong in `Docs/Historical_Bugs.md` or the relevant reference docs, not here.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, widget-shadow, visualizer, or Qt effect rewrites unless the current task directly requires them.

## Active Tasks

### 1. Gmail Thread Grouping
Status: All other Gmail work is complete. The only remaining Gmail task worth carrying here is thread grouping.

Task scope:
- Research and settle grouping semantics before changing runtime behavior.
- Prefer `X-GM-THRID` where available.
- Keep read and unread groups separate.
- Define collapsed-row action semantics before enabling the feature by default.
- Preserve the current default-off behavior until the runtime contract is clear.

## Watchlist
- Mute button fade-in reliability under startup event pressure.
- Transition random mode actual distribution vs expected uniform over long runtime.
- Settings destructive-flow checks: reset/import when touching settings architecture.
- Settings cache stale-read behavior after section/root writes.

## Deferred / Not Active
- Gmail IMAP Archive remains hidden unless a source-backed finding or small diagnostic harness proves a reliable accepted command.
- Shared “open Gmail/Reddit links on monitor index 0” work remains optional stretch work and is not active.
- Visualizer technical-ownership migration, activation-payload unification, preset/runtime bleed cleanup, and painted-card clipping work are complete and should stay documented in `Spec.md`, `Index.md`, and `Docs/Historical_Bugs.md`, not carried here as active tasks.
- `card_height.py` centralization is not active work. Revisit only if a focused sizing bug justifies it.
- Reassessing residual opacity-effect invalidation is not active work. Revisit only if a concrete shadow/effect corruption issue resurfaces.

## Documentation Rule
- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`
