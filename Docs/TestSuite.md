# Test Suite Guide

Last updated: 2026-08-20

Testing strategy during the Qt Quick runtime presentation migration.

## 1. Standard commands

Full bounded suite:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900
```

Targeted:

```powershell
pytest path\to\test_file.py -q --tb=short
```

Discover current tests by owner/defect, not by stale phase numbering.

## 2. Validation levels

### A — pure/unit

Settings, registries, geometry, cache keys, numerical visualizer helpers, generation helpers.

### B — component/integration

Logical mailbox/state bridge, widget models, Quick presentation-state mapping, render-state transport,
lifecycle ownership.

### C — runtime-shaped

Real logical worker, Quick window creation, threaded scene graph, mode switching, Pause/Play,
Settings/recreate, stale-generation fencing.

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
- transition continuity;
- Spectrum idle visibility;
- Pause/Play hitch;
- startup/reveal;
- widget visual parity.

## 3. Permanent visualizer gates

Preserve tests for:

- one `VisualizerLogicalRuntime`;
- actual authored scheduler cadence;
- logical worker cannot mutate GUI/Quick/GPU state;
- valid generation `0`;
- all five modes;
- source freshness;
- protected visible edges;
- Pause/Play identity;
- BTF.

Do not regenerate behavioural goldens merely because the presentation architecture changed.

## 4. Quick presentation gates

Add/retain runtime-shaped proof for:

- one standalone top-level `QQuickWindow` per physical display;
- threaded render loop active;
- render-thread identity distinct from GUI thread on supported Windows path;
- no `QQuickWidget`;
- no second accelerated runtime surface;
- bounded latest-state synchronization;
- stale generation rejected;
- intentional first frame;
- Settings/recreate;
- topology recreation;
- clean shutdown.

## 5. Physical frame-pacing gate

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

## 6. Heavy-load interpretation

The completed P0 experiment showed Quick remains approximately in the old light-load presentation
class even under substantial external CPU load.

Do not require every heavy-load outlier to disappear before migration.

Heavy load is a resilience gate, not permission to reopen the old architecture.

## 7. Lifecycle gate

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
- no old-generation callback survives destruction.

## 8. Migration parity

For each migrated presentation family, require the relevant combination of:

- visual parity;
- behaviour parity;
- input parity;
- geometry/DPR parity;
- lifecycle parity;
- performance not regressing the Quick architecture win.

## 9. Completion rule

Green tests are necessary, not sufficient.

Completion requires the relevant runtime and visual evidence for the migrated slice.
