# Test Suite Guide

Last updated: 2026-08-21

Testing strategy during the Qt Quick runtime presentation migration.

## 1. Standard commands

Targeted tests are the normal per-slice gate:

```powershell
pytest path\to\test_file.py -q --tb=short
```

The bounded full-suite diagnostic is:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

Discover current tests by owner/defect, not by stale phase numbering.

Do not use a red broad-suite run as the only evidence that the active migration slice failed. Inspect its exact failures/timeouts and run the smallest focused gate that can falsify the changed contract.

Tests must be executed in an environment appropriate to the claim being made. Source/unit contracts may run on a normal capable Windows checkout; real Quick/OpenGL, physical-display, refresh/DPR, and visual acceptance require the corresponding Windows/Qt/OpenGL/hardware environment.

## 2. Validation levels

### A — pure/unit

Settings, registries, geometry, cache keys, numerical visualizer helpers, generation helpers.

### B — component/integration

Logical mailbox/state bridge, widget models, Quick presentation-state mapping, render-state transport, lifecycle ownership.

### C — runtime-shaped

Real logical worker, Quick window creation, threaded scene graph, mode switching, Pause/Play, Settings/recreate, stale-generation fencing.

### D — real Windows/driver

Required for:

- real standalone QQuickWindow;
- actual threaded scene graph;
- multi-display/refresh/DPR;
- GPU/resource ownership;
- physical frame pacing;
- compiled/frozen build.

### E — manual visual

Required for:

- Bubble feel/BTF;
- transition continuity/authored visual parity;
- Spectrum idle visibility;
- Pause/Play hitch;
- startup/reveal;
- widget visual parity.

## 3. Permanent transition gates

Preserve tests for:

- canonical registry ↔ Quick implementation registry parity;
- lazy/dormant implementation resolution;
- Settings/default/random parameter resolution before render admission;
- immutable transition request/run state;
- exact endpoints and authored direction/mode variants;
- transition-specific shader/math preservation where contractually required;
- interruption/exactly-once completion;
- generation fencing;
- GL state restoration;
- resource teardown.

Real-GL and physical-display transition sign-off is routed through `Docs/Harness_Index.md`.

## 4. Permanent visualizer gates

Preserve tests for:

- one `VisualizerLogicalRuntime`;
- actual authored scheduler cadence;
- every authored logical step integrated before presentation coalescing;
- logical worker cannot mutate GUI/Quick/GPU state;
- valid generation `0`;
- all five modes;
- source freshness;
- protected visible edges;
- Pause/Play identity;
- clean worker join;
- BTF.

Do not regenerate behavioural goldens merely because the presentation architecture changed.

## 5. Quick presentation gates

Add/retain runtime-shaped proof for:

- one standalone top-level `QQuickWindow` per physical display;
- threaded render loop active;
- render-thread identity distinct from GUI thread on supported Windows path;
- inline custom GL through the selected `QSGRenderNode` seam;
- no `QQuickWidget`;
- no second accelerated runtime surface;
- bounded latest-state synchronization;
- stale generation rejected;
- intentional first frame;
- Settings/recreate;
- topology recreation;
- clean shutdown.

## 6. Physical frame-pacing gate

Report separately per display:

- physical p50/p90/p95/p99/max;
- severe-gap counts;
- request/synchronization age where meaningful;
- logical cadence;
- source age;
- CPU/GPU context.

Average FPS is secondary.

Internal `frameSwapped`/render callbacks are proxies, not physical-display proof.

Use OS/display-boundary evidence when deciding physical delivery.

## 7. Heavy-load interpretation

The completed P0 experiment showed Quick remains approximately in the old light-load presentation class even under substantial external CPU load.

Do not require every heavy-load outlier to disappear before migration.

Heavy load is a resilience gate, not permission to reopen the old architecture.

## 8. Lifecycle gate

Repeatedly exercise:

- normal startup/shutdown;
- Settings/recreate;
- Edit/CUSTOM;
- visualizer active;
- transitions active;
- monitor topology changes;
- display off/wake where relevant.

Require:

- logical runtime joins;
- stale state rejected;
- generation zero preserved;
- retired scene cannot reveal;
- render resources return to expected baseline;
- no old-generation callback survives destruction;
- no background owner prevents process/test shutdown.

## 9. Migration parity

For each migrated presentation family, require the relevant combination of:

- visual parity;
- behaviour parity;
- input parity;
- geometry/DPR parity;
- lifecycle parity;
- performance not regressing the Quick architecture win.

## 10. Completion rule

Green focused tests are necessary but not sufficient.

**Implementation closure and acceptance closure are distinct.** Implementation may advance to the next phase while explicitly listed hardware/eyes-on acceptance remains deferred, provided the next phase does not depend on that unresolved evidence.

A phase's acceptance/sign-off ledger must remain open until the tests and gates assigned to that ledger have actually been executed and the result is recorded against the tested commit/environment. Do not turn an unchecked gate into a pass because source review looks good, no execution result exists, another agent says it should pass, or later implementation work has already begun.

For Phase C specifically, the focused deterministic transition tests and applicable real-GL sign-off commands in `Docs/Harness_Index.md` must be run before Phase-C acceptance is marked closed. Hardware/eyes-on-only items remain explicitly unchecked until they are actually performed. A later failed sign-off reopens the smallest demonstrated defect.
