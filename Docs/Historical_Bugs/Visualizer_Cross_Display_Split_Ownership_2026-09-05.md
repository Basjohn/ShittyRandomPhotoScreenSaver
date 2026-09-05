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
