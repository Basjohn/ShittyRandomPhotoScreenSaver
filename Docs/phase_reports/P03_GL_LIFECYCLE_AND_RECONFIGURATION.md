# Phase 3 — GL Lifecycle and Reconfiguration

Date: 2026-07-28
Branch: `main`
Foundation: baseline `00edb57a3076b845cb8ee4b6cb7f36ea83411f0c` plus completed Phase 1/2 checkpoints
Donor boundary: reference only; no donor merge or donor architecture transplant

## Outcome

Phase 3 restores full stop/destroy/recreate semantics for Settings and committed CUSTOM Edit reloads. A paused runtime no longer remains hidden behind Settings. Old workers and delayed GUI/GL callbacks are fenced by one engine runtime generation plus the exact owning `DisplayManager`. Display-owned visualizer and transition producers stop before compositor GL resources are deleted on the GUI thread with the compositor context current. Surface/QObject destruction happens only after GL deletion succeeds.

The gate passed in deterministic 50/50/50 churn and focused real Qt/GL tests. Partial reinitialization remains forbidden.

## Baseline defects corrected

1. `stop(exit_app=False)` quiesced, cleared, and hid displays but kept the old display/GL runtime alive until after Settings closed.
2. `DisplayWidget` defined `_on_destroyed` twice. The later `display_gl_init.on_destroyed()` no-op shadowed the real cleanup delegate.
3. The legacy overlay cleanup helper shadowed its parent variable and cleared attributes on the child rather than the owning display.
4. compositor cleanup suppressed invalid-context and deletion failures, reset handles, and reported `DESTROYED` even when deletion could not be proved.
5. deferred GL warmups checked only Qt-object validity, not compositor lifecycle ownership.
6. image compute callbacks, display staggering, prefetch resume, startup retry, and display-ready replay had no engine runtime-generation/display-manager fence.
7. async image compute inspected live `DisplayWidget` sizing/mode state after submission.
8. visualizer `cleanup()` only repeated logical `stop()` and could leave its parent overlay GL resources alive after pause preparation had already disabled it.

## Implemented ownership shape

### Runtime boundary

`ScreensaverEngine` owns one `_runtime_generation`. Full-stop admission advances it before timer/display teardown. Every delayed image publication captures:

- runtime generation;
- exact `DisplayManager` identity.

A callback publishes only when both still match and the engine is not stopping/shutting down. Rejected callbacks are counted in `_lifecycle_rejected_callbacks`.

The generation advanced at stop is the reserved identity for the next full runtime built by the Settings/CUSTOM handlers. This avoids constructing a replacement manager under an identity that `start()` would immediately invalidate.

### Full teardown order

The production path is now:

1. transition engine to `STOPPING`/`SHUTTING_DOWN`;
2. advance runtime generation and close old publication admission;
3. stop RSS/rotation timers;
4. quiesce display/widget producers;
5. clear transition work;
6. run explicit synchronous `DisplayWidget.cleanup_runtime()`;
7. stop WidgetManager/visualizer producers and destroy visualizer parent overlays;
8. stop transition/compositor rendering;
9. assert GUI-thread ownership;
10. `makeCurrent()` and verify the expected compositor context is current;
11. delete textures, PBOs, programs, VBOs, and VAOs;
12. retain handles/accounting and raise if any deletion fails;
13. `doneCurrent()`;
14. assert no compositor GL resource remains;
15. detach/delete compositor, then destroy the render surface;
16. close/delete the display QObject;
17. clear the manager and mark the engine `STOPPED`.

`QObject.destroyed` remains only a loud residual safety net. It is no longer the normal cleanup owner.

### Workers and deferred work

- primary and previous-image compute paths snapshot immutable width/height/display-mode inputs before submission;
- compute returns frozen `QImage` payloads; guarded GUI callbacks alone materialize `QPixmap`;
- compute admission/completion and sync fallback validate runtime/manager identity;
- display-stagger and prefetch-resume delayed work share the same guard;
- startup first-image retry and display-ready replay capture runtime/manager identity;
- deferred GL warmup captures a compositor lifecycle generation and rejects after shutdown/replacement;
- stale callbacks return without clearing or mutating replacement-runtime state.

### Strict GL deletion

`GLTextureManager.cleanup(strict=True)` retains failed texture/PBO ownership and raises. `cleanup_gl_pipeline()` raises when live resources have no valid/current context or deletion is incomplete. `GLCompositorWidget` remains `DESTROYING` on failure and may not claim `DESTROYED` until cleanup succeeds.

## Required churn evidence

Artifact: `Docs/phase_reports/artifacts/P03/lifecycle_churn_report.json`

The harness drives the production engine/display teardown seams with instrumented resources and exact plateau counters:

- 50 Settings cycles;
- 50 Edit cycles;
- 50 mixed cycles;
- active transition every cycle;
- Spectrum and Bubble coverage;
- in-flight decode callback every cycle;
- 1920x1080 to 2560x1440 resolution change;
- 150 stale callbacks submitted and 150 rejected;
- zero stale publications;
- zero cross-thread GL operations;
- zero stopped GL resources/bytes;
- zero stopped timers, workers, or callbacks;
- valid context-current/delete/doneCurrent/surface-destroy order in all 150 cycles.

Sleep/wake is explicitly not represented by the deterministic headless harness and remains a Phase 11 platform scenario. Driver-reported VRAM is also a soak/platform metric; Phase 3 proves exact owned-resource return-to-zero, while Phase 4 owns RAM/VRAM plateau containment.

## Verification

Commands used:

```powershell
.\.venv\Scripts\python.exe tools\phase3_lifecycle_harness.py --cycles 50 --output Docs\phase_reports\artifacts\P03\lifecycle_churn_report.json
.\.venv\Scripts\python.exe -m pytest tests\test_phase3_runtime_lifecycle.py tests\test_engine_lifecycle.py tests\test_s_hotkey_workflow.py tests\test_gl_compositor_cleanup.py tests\test_startup_shader_warmup.py tests\test_display_integration.py::TestDisplayManagerSync::test_initialize_displays_suppresses_stale_staggered_show_after_cleanup tests\test_display_integration.py::TestDisplayManagerSync::test_engine_monitor_change_detaches_old_manager_before_rebuild tests\test_display_integration.py::TestDisplayManagerSync::test_initialize_display_rewires_monitor_signal_after_rebuild -q
.\.venv\Scripts\python.exe -m pytest tests\test_image_pipeline.py tests\test_image_prefetcher.py tests\test_image_worker.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_spotify_visualizer_widget.py -q -rs
.\.venv\Scripts\python.exe tools\visualizer_replay.py verify
.\.venv\Scripts\python.exe -m pytest tests\test_visualizer_doc_references.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_gl_compositor_cleanup.py -q -rs
```

Results at closure:

- Phase 3 lifecycle gate: `57 passed`.
- image pipeline/prefetch/worker regression: `30 passed`.
- protected visualizer file: `186 passed, 20 skipped` for the documented retired/unavailable Bubble cases.
- deterministic visualizer replay: `66` goldens plus manifest verified.
- visualizer documentation references: `6 passed`.
- real Windows Qt GL cleanup: `2 passed`, no skip.
- deterministic churn artifact: pass, 150 cycles, no errors.

Two broad `test_display_integration.py` offscreen cases remain pre-existing environment/runtime-sensitive failures outside this phase (`transition_cleanup_on_clear` cannot start its transition under the offscreen GL plugin; Spotify volume visibility times out). They are not used as Phase 3 evidence and were not hidden or weakened.

## FFT worker assessment requested during Phase 3

The default `workers.fft.enabled = false` does not disable a live fallback-prone FFT process. It is inert legacy configuration:

- `WorkerType` no longer contains `FFT`;
- engine worker startup explicitly starts Image only and documents FFT process removal;
- current visualizer audio analysis uses one coalesced `ThreadManager` compute task;
- activation ID and compute-gate token reject stale work;
- `TripleBuffer` publication keeps the GUI on latest-result semantics;
- Phase 2 replay/goldens protect the resulting visual behavior.

Restoring a separate FFT process is not recommended without contrary measurement. It would add high-frequency sample serialization/copy latency, another process lifetime, and another stale-result boundary to a latency-sensitive visualizer. The useful follow-up is removal/migration of the inert setting and generated default leaves during Phase 10 legacy-scaffolding cleanup. No production FFT-worker implementation task was created.

## Rollback

Phase 2 checkpoint before this work: `b9cc2378f26c75ac5617179a07ddc30d9b2e1f0a` (`4.6.9 Phase 2`).

Phase 3 is committed separately as `4.6.9 Phase 3`; that commit is the forward checkpoint and the Phase 2 hash remains the direct rollback point.