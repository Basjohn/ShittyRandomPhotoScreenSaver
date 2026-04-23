# Current Plan

Last updated: 2026-04-23

This file is intentionally short. It tracks only active work and near-term validation.

## Active Priorities
- Keep settings/dialog stability and startup behavior regression-free while preserving custom styling.
- Continue visualizer quality work in unresolved mode-specific bug families from `Docs/Historical_Bugs.md`.
- Keep preset tooling/schema and runtime behavior aligned as visualizer modes evolve.

## Open Validation
- Runtime confirmation for unresolved historical bug entries only.
- Preset repair/reindex round-trip checks after visualizer schema changes.
- Settings destructive-flow checks (reset/import) when touching settings architecture.

## Operational Guardrails
- Harnesses and probes remain first-class tooling (`tools/flicker_test.py`, `tools/winprobe_observer.py`, helper harnesses).
- `presets/visualizer_modes/` remains the authored preset source tree.
- Do not close visual/runtime bugs from tests alone when the symptom is user-visible timing or rendering behavior.

## Documentation Rule
- Put architecture in `Spec.md`.
- Put module map in `Index.md`.
- Put policy in `Docs/Guardrails.md`.
- Put dated bug narratives in `Docs/Historical_Bugs.md`.
