# Historical bug — Visualizer cross-display split ownership (2026-09-05)

## Symptoms

Two apparently separate CUSTOM-layout failures shared one lifecycle owner:

- loading a numbered saved geometry/layout slot parsed and persisted the requested layout, then the replacement destruction barrier timed out with only `QuickDisplayVisualizerOwner` retained;
- after a successful live Visualizer hop to another display, Save entered replacement cleanup and failed from `QuickDisplayVisualizerOwner.retire()` because the target `QuickFramePacer` was already closed.

The corrected geometry appearing on the next cold launch proved the slot data itself was not the primary failure.

## Root cause

Cross-display transfer had several pieces of one logical ownership edge, but they were committed separately:

1. `QuickCustomLayoutSceneCoordinator` moved the retained Visualizer scene admission;
2. `QuickDisplayVisualizerOwner` retargeted its presentation runtime/pacer;
3. `DisplayManager._quick_visualizer_unit` still named the old display;
4. the old `QuickDisplayUnit._visualizer_owner` attachment still owned eventual retirement ordering.

The first repair moved items 2-4 together, but scene movement and lifecycle movement were still separate `CustomLayoutSession` subscribers. Because listeners run synchronously in order, the scene subscriber could succeed and the lifecycle subscriber could then fail. Its local rollback could restore manager/unit/pacer state but could not restore the already-moved scene, recreating the same class of split truth.

## Permanent contract

A Visualizer display hop is one event-bound ownership transaction. The transaction must either commit all of these truths or restore all of them:

- retained scene admission;
- `QuickDisplayVisualizerOwner` presentation runtime and frame pacer;
- `DisplayManager._quick_visualizer_unit`;
- exact `QuickDisplayUnit` retirement attachment.

`QuickCustomLayoutSceneCoordinator` therefore delegates Visualizer transfer to one transaction callback. That callback moves the retained scene, moves manager/unit/pacer authority, and if the lifecycle half fails, moves the scene back before the session item placement is restored. There is no second Visualizer session subscriber.

Pre-transfer ownership contradictions are fatal. Do not silently repair them through a fallback owner or by swallowing a closed-pacer error.

## Related layout contract

Geometry-only same-display Save remains a live working-state -> committed-state promotion and must not reboot the retained runtime. A numbered slot load may still use a fenced full-generation replacement because it can alter many ordinary enabled/layout routes. A whole-widget fade may decorate that replacement later, but it is not a lifecycle substitute.

## Validation required

- left/right button hop, then Save;
- native cross-seam drag, then Save;
- Cancel after a cross-display hop restores the source scene and source lifecycle owner;
- numbered slot load reaches a zero destruction barrier;
- repeated source <-> target transfers never produce duplicate scene admission;
- teardown never touches a closed pacer through a still-attached Visualizer owner;
- mixed 60/165 Hz and mixed-DPR transfer preserves one logical Visualizer owner and one authored cadence.

## 2026-09-05 second failure mode — scale drift + orphan target admission

A later adjustment run exposed a rarer path that the first transaction repair did not fully describe.

### Symptom chain

- repeated live viewport resizes eventually logged an incoherent pair around `649x960` working pixels versus `649x1406` logical viewport extent;
- both button hop and native drag then repeatedly failed with `CUSTOM Visualizer target already has a retained scene admission`;
- the target display's retained scene carried an **older Visualizer activation identity**, while manager-level lifecycle authority and the currently reacting Visualizer remained on the source display;
- Save could therefore persist a visually split result (empty target frame, live source Visualizer), and a subsequent numbered slot load inherited the already-invalid ownership graph.

### Additional root cause

Viewport-only gestures were each allowed to derive pixels-per-world from the latest retained presentation. A tall resize could therefore encode one axis using one scale and a later horizontal resize encode the other axis using another. Each gesture looked locally plausible, but the final rectangle and logical extent no longer represented one uniform visual scale.

Separately, the scene-level transfer gate treated **any** retained target render identity as a legitimate owner conflict. That was too weak an authority check: a target `QuickDisplayUnit` can own no Visualizer lifecycle owner while its retained scene still contains an old activation shell. Once such a shell existed, every later transfer attempt could be rejected even though there was still only one real logical/runtime owner.

### Extended permanent contract

- One active Visualizer Edit session owns one stable pixels-per-world scalar for viewport-only resize. Side handles consume it on one axis and Visualizer corners consume it on both axes. Independent gestures must never relearn unrelated presentation scales.
- Scroll wheel remains the explicit uniform whole-Visualizer scale operation. A cross-display target-fit projection is the only other allowed scale change, and it updates the scalar only after final target geometry and lifecycle ownership commit successfully.
- Target render identity alone is **not** lifecycle authority. Before clearing a stale target admission, product-level `DisplayManager` / exact `QuickDisplayUnit.visualizer_owner` must prove that target unit owns no Visualizer lifecycle owner. Only then may scene-local render/input admission be discarded and the retained shell reused.
- If the target unit owns any Visualizer lifecycle authority, transfer is a hard conflict. Do not overwrite it, do not create a fallback owner, and do not recreate the logical runtime to make the gesture succeed.
- Button and drag transfer feed the same transaction and the same session geometry truth. Live Edit Save remains a promotion boundary, **never a recovery teardown boundary**.

### Added regression coverage

`tests/test_qtquick_visualizer_custom_geometry_regressions.py` protects the two-axis Visualizer corner contract, stable per-session pixels-per-world authority, manager-proven orphan target cleanup, and refusal to overwrite a real target lifecycle owner. Existing reconciled CUSTOM-owner tests remain responsible for full button/drag/Save/Cancel integration in a PySide6-capable environment.

## 2026-09-05 third failure mode — non-atomic CUSTOM closure over dead Quick roots

A later aggressive resize/display torture run demonstrated a distinct lifecycle hole after the transfer/geometry repairs had otherwise behaved well.

### Symptom chain

- repeated Visualizer resize and display-transfer operations succeeded for several minutes;
- the first visible failure occurred during Save around 18:27:44: persistence/live promotion reached the closure boundary, then one ordinary retained presentation dereferenced a C++ `QQuickItem` that had already been deleted;
- `_finish()` stopped on that exception, so one display cleared some CUSTOM state while another retained the shared Edit session;
- later Save attempts saw no active Visualizer override, the retained context menu could open but actions reached deleted Quick objects, and Cancel/Settings baseline projection hit the same poisoned graph;
- terminal teardown then failed because `describe_scene_state()` itself dereferenced an already-deleted `DisplayScene` root. Diagnostics therefore amplified a recoverable retained-object failure into aborted destruction.

### Permanent closure/recovery contract

- A shared CUSTOM session closes on **all displays or none remain owned by it**. Per-display cleanup failures are accumulated; they do not abort the loop. Shared coordinator/session/binding/resize ownership clears unconditionally after every display has had its cleanup attempt.
- Retained ordinary wrappers subscribe to their own Qt `destroyed` signal. Unexpected C++ destruction removes the wrapper from its current host immediately and records the model identity. Explicit normal retirement clears host ownership before `deleteLater()`, so it is not reported as corruption. This edge is event-driven and owns no cadence.
- Cancel may fail to project a corrupt baseline, but it still terminalizes shared Edit ownership and then requests reconstruction from committed/pre-edit truth.
- Healthy live Save remains **no-teardown/no-reinit**. Reconstruction is requested only after persistence when live promotion or retained cleanup proves the current Qt graph already corrupt. Do not turn this repair path into the ordinary Save mechanism.
- Scene/overlay/Visualizer retirement and lifecycle snapshots must tolerate already-deleted Shiboken wrappers. Telemetry is never allowed to block destruction.
- Unexpected `DisplayScene` destruction while admission is still open is recorded at the `destroyed` edge with screen/generation and marks the session corrupt. The original stress log proves that such a root was dead by shutdown, but does **not** prove which upstream owner destroyed it; preserve the new edge instrumentation rather than inventing a teardown theory.

### Added regression owner

`tests/test_qtquick_custom_layout_terminalization.py` protects all-display closure after one scene cleanup throws, healthy live Save remaining reload-free, corruption-only Save/Cancel reconstruction, and the event-driven stale-wrapper identity ledger. Physical M0 torture remains required because the original upstream Qt-root death was intermittent.

`tests/test_qtquick_retained_lifecycle_integrity.py` is the broader current-owner lifecycle matrix. It additionally pins coordinator + display cleanup failure terminalization, coherent cross-display live Save, layout-slot deferred reconstruction, corruption-repair ordering, unexpected-versus-intentional retained-root death, admission-scoped `DisplayScene` loss, and the rule that display diagnostics are observational and cannot abort teardown. This complements the terminal runtime-destruction/barrier suite rather than restoring any retired lifecycle owner.

