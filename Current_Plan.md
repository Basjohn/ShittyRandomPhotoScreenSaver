# Current Plan

Last updated: 2026-04-23

This file tracks active work and near-term validation.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as the authored preset source tree.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.

## Active Priorities
- Keep settings/dialog stability and startup behavior regression-free while preserving custom styling.
- Continue visualizer quality work in unresolved mode-specific bug families from `Docs/Historical_Bugs.md`.
- Keep preset tooling/schema and runtime behavior aligned as visualizer modes evolve.

## Open Validation
- Runtime confirmation for unresolved historical bug entries only.
- Preset repair/reindex round-trip checks after visualizer schema changes.
- Settings destructive-flow checks (reset/import) when touching settings architecture.

## Runtime Watchlist
- Settings dialog startup/show/focus regressions.
- Visualizer mode-switch state bleed across shared seams.
- Preset repair/reindex drift from authored payload intent.
- Settings cache stale-read behavior after section/root writes.

## Documentation Rule
- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`

## Idea Box
1. Add a lightweight “doc drift” check that flags stale references between `Spec.md`, `Index.md`, and `Current_Plan.md`.
2. Add a tiny harness smoke command list to this file so recurring investigations are one-command repeatable.
