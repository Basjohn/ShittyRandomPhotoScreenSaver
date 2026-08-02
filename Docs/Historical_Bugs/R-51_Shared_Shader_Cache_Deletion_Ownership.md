# R-51 — Phase 3 Shared Shader Cache Gave Two Compositors One Deletion Identity

Date: 2026-07-28  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

The first real dual-display CUSTOM Edit teardown at 13:44:57 and Settings teardown at 13:47:59 deleted screen 0 cleanly, then screen 1 raised `GL_INVALID_VALUE` while deleting all eleven transition programs. CUSTOM exited and Settings remained half torn down instead of opening normally.

## Root Cause

Phase 3 correctly made deletion strict, but compiled transition IDs remained in one process-global cache and were copied into both per-display pipelines. Qt context sharing made the IDs usable from both contexts; it did not give both compositors deletion ownership. The first owner deleted the IDs and the second attempted to delete the same numeric resources. The churn harness modeled independent owners and the original real-GL test had one compositor, so the contradictory multi-display shape escaped the Phase 3 gate.

## Fix

Each compositor now owns its own `GLProgramCache`, compiled IDs, and uniform locations; its `GLGeometryManager` alone owns VAO/VBO IDs and pipeline fields are non-owning draw mirrors. Stateless shader helpers alone may be reused. Global program/geometry/texture/state singleton accessors and shutdown cleanup were removed. The generic `ResourceManager` is passive GL accounting and no longer retains deletion callbacks. The temporary display-local visualizer GL overlay now retains failed handles and blocks parent/display destruction. `engine.stop(exit_app=False)` is the sole teardown authority; duplicate handler teardown calls were removed. Failure aborts Settings/Edit admission and exits nonzero while retaining failed resource ownership.

## Architecture

The target remains one compositor surface per display. Phase 6 may share measured resources only through explicit leases and exactly-once deletion; Phase 8 folds display-local overlay surfaces into that display compositor, never into a process-wide owner.

## Bars

Focused lifecycle/resource coverage passes, including strict failed-program retention and a real two-compositor Windows Qt test that proves distinct program owners and sequential cleanup without GL errors. No global GL singleton accessor remains referenced by production or tests.

## Guardrail

Share-group accessibility is not ownership. Never copy a globally cached numeric GL handle into multiple local owner records. Reusing stateless shader source/helper objects does not authorize shared deletion.

## Evidence

- `Docs/phase_reports/P03_GL_LIFECYCLE_AND_RECONFIGURATION.md`
- `Docs/Compositor_Architecture.md`
- `tests/test_gl_compositor_cleanup.py`

## Migration Record

This file is the standalone detailed record copied from the original `R-51` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
