# Phase Reports — Reading Rule

Last updated: 2026-08-18

Files in this directory are **checkpoint evidence**, not a permanent current owner map.

A report is authoritative for:

- what source/commit/environment it inspected;
- what evidence was accepted at that checkpoint;
- what mechanism was proved/rejected;
- what limits the evidence had.

A report is **not** automatically authoritative for current:

- base classes;
- surface/context ownership;
- module/class names;
- presentation clocks;
- active task sequencing.

SRPSS has since moved from QOpenGLWidget/separate visualizer surfaces to a QRhi/OpenGL single-surface
per-display architecture. Older reports intentionally retain the old names because changing them
would corrupt the historical evidence.

For current architecture read, in order:

1. exact current `main`;
2. `Current_Plan.md` for active work;
3. `Index.md` / `Docs/Contracts.md` for current ownership;
4. `Spec.md` / Guardrails / focused current architecture docs;
5. then this folder for evidence supporting or rejecting a mechanism.

`P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` is the current detailed presentation/delivery evidence
owner while its work remains active. It still does not outrank `Current_Plan.md` execution order.
