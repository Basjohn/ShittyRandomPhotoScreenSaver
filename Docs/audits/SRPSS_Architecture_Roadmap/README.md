# SRPSS Architecture Audit References

Last reconciled: 2026-08-18

This directory is now **supplemental audit/reference material**, not a maintained second roadmap.

Active work and architecture moved into smaller canonical owners:

- active order: `Current_Plan.md`;
- stable architecture: `Spec.md`;
- cross-cutting rules: `Docs/Guardrails.md`;
- compositor/QRhi/single-surface design: `Docs/Compositor_Architecture.md`;
- visualizer presentation/fidelity: `Docs/Guardrails/Visualizer_Presentation.md` plus
  `Docs/Visualizer_Reference.md`;
- deferred debt: `Future_Cleanup.md`;
- checkpoint evidence: `Docs/phase_reports/`.

The old live-planning documents `00`, `01`, `02`, `03`, `04`, `05`, `06` and
`ROADMAP_MANIFEST.json` are intentionally retired by the 2026-08-18 documentation reconciliation.
They duplicated authority and, after the QRhi/single-surface migration, could direct coding agents
back toward obsolete QOpenGLWidget/separate-surface designs.

Keep only specialized audit documents in this folder where they still own useful detail not already
captured by the canonical files above (for example monitor lifecycle, workload, memory/resource,
test or failure-triage reference). Such files never own active task order.

If a specialized audit conflicts with exact current source or the canonical current documents, treat
it as stale reference and reconcile or retire it rather than preserving two truths.
