# Harness Index

Last updated: 2026-08-21

Compact routing for recurring investigation and migration sign-off commands.

Harness success is evidence, not final visual/timing/lifecycle sign-off. Run each harness in the environment appropriate to the claim it makes; physical display cadence, GPU utilization, subjective motion feel, and real multi-monitor topology require the corresponding real Windows/Qt/OpenGL/hardware environment.

## 1. Targeted tests first

Prefer the smallest test set that can falsify the current slice:

```powershell
pytest path\to\test_file.py -q --tb=short
```

Use `Docs/TestSuite.md` for broader suite guidance.

The repository also has the chunk wrapper for deliberate local diagnostics:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

Do not treat a red full-suite chunk run as proof the active migration slice failed until the relevant per-chunk log is inspected. A pytest summary followed by a process that never exits should be diagnosed as shutdown/lifecycle ownership rather than hidden with a larger timeout. A chunk that stops during test execution requires smaller/verbose local isolation to identify the actual hanging test/owner.

## 2. Phase-C Quick transition sign-off

### Blinds

```powershell
python tools\qtquick_blinds_smoke.py --direction horizontal --windows 1
python tools\qtquick_blinds_smoke.py --direction vertical   --windows 1
python tools\qtquick_blinds_smoke.py --direction diagonal   --windows 1
```

Repeat with `--windows 2` on the physical dual-display system when that sign-off is scheduled.

### Remaining parameterized effects

Use:

```powershell
python tools\qtquick_phase_c_effect_smoke.py --effect <effect> --case <case> --windows 1
```

Canonical cases exposed by the wrapper:

- Diffuse: rectangle, membrane, lines, diamonds, amorph, random
- Ripple: count1, count3, count8
- Crumble: top, bottom, random-weighted, random-choice, age-weighted
- Particle: authored mode/direction cases including directional variants plus swirl/converge
- Burn: six directions plus smoke/ash toggle cases

Use `--windows 2` only for scheduled physical multi-display evidence.

A smoke pass proves the exercised renderer/runtime contract. Eyes-on old-vs-Quick effect fidelity remains a separate acceptance statement.

## 3. Visualizer authored-fidelity replay

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe tools\visualizer_replay.py verify
.\.venv\Scripts\python.exe tools\visualizer_replay.py metrics
```

Do not regenerate goldens merely to accommodate the presentation migration.

For Bubble, also apply `Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

## 4. Logical-runtime gates

Search current tests by contract:

```powershell
rg -n "VisualizerLogicalRuntime|generation 0|mode switch|Spectrum|Pause|BTF|single clock|thread affinity" tests
```

Required principles:

- `VisualizerLogicalRuntime` is the sole authored mode-general logical clock;
- every authored logical step is preserved;
- latest-state semantics, no FIFO/catch-up replay;
- no paint acknowledgement;
- no producer/display divisor;
- no source/event decimation;
- no display-refresh logical cap;
- worker cannot mutate GUI/Quick/GPU;
- generation zero is valid;
- protected visible edges survive;
- source freshness remains separate from presentation;
- worker joins cleanly.

## 5. Qt Quick migration checks

Use existing P0 evidence as the architecture-selection record; do not keep expanding P0 merely to reconfirm the chosen presenter.

Focused Quick harnesses should prove, as relevant:

- standalone QQuickWindow;
- threaded scene graph;
- current-generation state delivery;
- first intentional frame;
- immutable render-boundary state;
- Settings/recreate;
- topology/binding loss;
- resource cleanup;
- exact effect/visualizer contract being migrated.

## 6. Physical evidence

When internal callbacks are insufficient, capture OS/display-boundary evidence and correlate it to intentional active-motion windows.

Do not interpret startup/capture rows before intentional presentation as active-animation cadence holes.

Do not infer continuous displayed FPS from sparse/non-occupancy GDI `DisplayedTime` rows.

Use p95/p99/tails/severe gaps plus phase correlation when cadence evidence is actually needed.

## 7. Runtime diagnostics

Use only relevant existing flag families such as:

```text
--perf
--gpu-timing
--usage
--viz
--geo
--set
--life
--cache
--steam
```

Keep observer overhead named.

## 8. Lifecycle

Check:

- logical runtime stop/join;
- stale-state fencing;
- generation zero;
- Quick scene/window retirement;
- render-resource retirement;
- no retired callback publication;
- no background thread/process preventing test or product shutdown.

A pytest summary followed by a process that never exits strongly suggests leaked shutdown ownership and should be diagnosed rather than hidden by a larger timeout.

## 9. Historical evidence

Historical harnesses may describe old QRhiWidget/QOpenGLWidget/GLCompositor presentation paths. They remain evidence, not architecture instructions.

Do not copy a historical presentation mechanism back into the Qt Quick migration simply because the historical harness is detailed.
