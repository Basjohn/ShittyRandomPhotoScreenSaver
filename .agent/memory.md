# Repo Memory

- `Index.md`, `Spec.md`, and `Current_Plan.md` are standing anchor documents and must be kept accurate, relevant, and in sync with the real codebase.
- Use `Index.md` and `Spec.md` first for navigation, architecture lookup, and contract sanity checks.
- Use `Current_Plan.md` as the live planning source of truth for active and pending work.
- When work meaningfully changes architecture, behavior, ownership, priorities, or active tasks, update the relevant anchor docs in the same stream of work.
- Canonical long-lived docs going forward:
  - `Index.md` for navigation and document discovery
  - `Spec.md` for architecture/runtime contracts
  - `Current_Plan.md` for active work and live priorities
  - `Docs/Historical_Bugs.md` for resolved bug history, failed approaches, and guard-test context
  - `Docs/Visualizer_Signal_Contract.md` for visualizer signal ownership and per-mode routing rules
  - `Docs/Visualizer_Reset_Matrix.md` for visualizer reset/freshness ownership
  - `Docs/Visualizer_Baseline_Tuning_Matrix.md` for cross-mode visualizer tuning baselines and compat-key policy
  - `Docs/Visualizer_Setting_Guide.md` for user-facing visualizer setting behavior and tuning guidance
- Audits are working/backlog documents, not forever canonical docs; do not treat audit files as replacements for the canonical documents above.
