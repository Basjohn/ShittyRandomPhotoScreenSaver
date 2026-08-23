# SRPSS Architecture Audit References

Last reconciled: 2026-08-23

This directory is **supplemental audit/reference material**, not a maintained second roadmap.

Current authority lives in:

- active order: `Current_Plan.md`;
- stable architecture: `Spec.md`;
- presentation architecture: `Docs/Compositor_Architecture.md`;
- current owner routing: `Index.md` + `Docs/Contracts.md`;
- cross-cutting rules: `Docs/Guardrails.md`;
- visualizer presentation/fidelity: `Docs/Guardrails/Visualizer_Presentation.md` plus
  `Docs/Visualizer_Reference.md`;
- tests/retirement: `Docs/TestSuite.md`;
- deferred deletion: `Future_Cleanup.md`;
- checkpoint evidence: `Docs/phase_reports/`.

## Architecture-epoch warning

The old live-planning documents `00`, `01`, `02`, `03`, `04`, `05`, `06` and
`ROADMAP_MANIFEST.json` were retired in the 2026-08-18 reconciliation because they duplicated
authority.

Some surviving specialized audits still describe the then-current QOpenGLWidget or QRhi/
GLCompositor architecture. Preserve those mechanism/resource/test findings as historical reference,
but do not treat “QRhi/single-surface” as the accepted destination anymore.

Accepted destination:

```text
one standalone QQuickWindow per physical display
    -> threaded Quick scene
    -> retained Quick + inline QSGRenderNode custom GL
```

QRhiWidget/GLCompositor presentation is **CURRENT-LEGACY — WILL BE OBSOLETE at H/I**.

Keep specialized audit documents only where they still own useful detail not already captured by
canonical files, for example monitor lifecycle, workload, memory/resource, testing or failure-triage
reference. Such files never own active task order.

If a specialized audit conflicts with exact current source or canonical current docs, treat it as stale
reference and reconcile/retire the routing rather than preserving two truths.
