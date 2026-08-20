# Harness Index

Last updated: 2026-08-20

Compact routing for recurring investigation commands.

Harness success is evidence, not final visual/timing/lifecycle sign-off.

## 1. Full / targeted tests

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900
pytest path\to\test_file.py -q --tb=short
```

Use `Docs/TestSuite.md`.

## 2. Visualizer authored-fidelity replay

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe tools\visualizer_replay.py verify
.\.venv\Scripts\python.exe tools\visualizer_replay.py metrics
```

Do not regenerate goldens to accommodate presentation migration.

For Bubble also apply BTF.

## 3. Logical-runtime gates

Search current tests by contract:

```powershell
rg -n "VisualizerLogicalRuntime|generation 0|mode switch|Spectrum|Pause|BTF|single clock|thread affinity" tests
```

Required principles:

- authored cadence remains healthy;
- worker cannot mutate GUI/Quick/GPU;
- exactly one logical clock;
- generation zero valid;
- protected visible edges survive;
- source freshness remains separate from presentation.

## 4. Qt Quick migration checks

Use the existing P0 harness/evidence as the architecture-selection record.

Do **not** keep expanding P0 merely to reconfirm the choice.

For production migration slices, focused harnesses should prove:

- standalone QQuickWindow;
- threaded scene graph;
- current-generation state delivery;
- first intentional frame;
- migrated visual parity;
- Settings/recreate;
- topology;
- resource cleanup.

## 5. Physical evidence

When internal callbacks are insufficient, capture OS/display-boundary evidence.

Correlate physical samples to phase timestamps.

Do not interpret pre-intentional-window startup/capture rows as active-animation cadence holes.

Be cautious deriving "displayed FPS" from non-NA GDI `DisplayedTime` row counts when those rows do not
form continuous display occupancy.

Use tails/severe gaps plus phase correlation.

## 6. Runtime diagnostic flags

Use only relevant existing families such as:

```text
--perf
--gpu-timing
--usage
--viz
--geo
--set
--life
--cache
```

Keep observer overhead named.

## 7. Lifecycle

Check:

- logical runtime stop/join;
- stale-state fencing;
- generation zero;
- Quick scene/window retirement;
- render-resource retirement;
- no retired callback publication.

## 8. Historical evidence

Historical harnesses may describe old QRhiWidget/QOpenGLWidget paths.

Do not copy historical presentation mechanisms back into the migration because a harness is detailed.
