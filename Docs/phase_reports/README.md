# Phase Reports — Reading Rule

Last updated: 2026-08-23

Files in this directory are **HISTORICAL CHECKPOINT EVIDENCE**, not a current owner map and not active
sequencing.

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
- capability terminology;
- active migration phase/task order.

## Architecture-epoch warning

Many reports were written during the QOpenGLWidget and later QRhiWidget/GLCompositor eras. Those
mechanisms remain valid historical evidence where the report measured them, but the accepted
destination is now:

```text
one standalone QQuickWindow per physical display
    -> threaded Qt Quick scene
    -> retained Quick items + inline QSGRenderNode custom GL
```

QRhiWidget/GLCompositor runtime presentation is **CURRENT-LEGACY — WILL BE OBSOLETE at H/I**. Do not
read an old report's successful QRhi correction as permission to deepen or preserve that presenter.

## Current read order

For current architecture/work read, in order:

1. exact current `main`;
2. `Current_Plan.md` for active work;
3. `Index.md` / `Docs/Contracts.md` for current ownership;
4. `Spec.md` / `Docs/Guardrails.md` / focused current architecture docs;
5. `Docs/TestSuite.md` for current test authority where relevant;
6. then this folder for historical evidence supporting or rejecting a mechanism.

`P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` remains useful historical delivery evidence, but **P05 is
not current work and the report is not a current presenter owner**. E1 is the active Phase-E slice at
the 2026-08-23 documentation reconciliation.

Do not rewrite old report bodies merely to modernize names; update this navigation layer or add a later
superseding evidence record instead.
