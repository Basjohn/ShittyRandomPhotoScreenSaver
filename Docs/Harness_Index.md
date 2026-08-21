# Harness Index

Last updated: 2026-08-21

Compact routing for recurring investigation and migration sign-off commands.

Harness success is evidence, not final visual/timing/lifecycle sign-off. Run each harness in the
environment appropriate to the claim it makes; physical display cadence, GPU utilization, subjective
motion feel, and real multi-monitor topology require the corresponding real Windows/Qt/OpenGL/hardware
environment.

SRPSS does not use hosted repository CI as the normal migration harness path unless the operator
explicitly requests it.

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

Do not treat a red full-suite chunk run as proof the active migration slice failed until the relevant
per-chunk log is inspected. A pytest summary followed by a process that never exits should be
diagnosed as shutdown/lifecycle ownership rather than hidden with a larger timeout. A chunk that stops
during execution requires smaller/verbose local isolation.

## 2. Phase-C Quick transition sign-off

### Blinds

```powershell
python tools\qtquick_blinds_smoke.py --direction horizontal --windows 1
python tools\qtquick_blinds_smoke.py --direction vertical   --windows 1
python tools\qtquick_blinds_smoke.py --direction diagonal   --windows 1
```

Repeat with `--windows 2` on the physical dual-display system when scheduled.

### Remaining parameterized effects

Use:

```powershell
python tools\qtquick_phase_c_effect_smoke.py --effect <effect> --case <case> --windows 1
```

Canonical cases include:

- Diffuse: rectangle, membrane, lines, diamonds, amorph, random
- Ripple: count1, count3, count8
- Crumble: top, bottom, random-weighted, random-choice, age-weighted
- Particle: authored mode/direction cases including directional variants plus swirl/converge
- Burn: six directions plus smoke/ash toggle cases

Use `--windows 2` only for scheduled physical multi-display evidence.

## 3. Phase-C smoke strengthening requirements

Preserve the real-GL harnesses. Strengthen them rather than replacing them with mocked renderers.

A generic spatial wipe/reveal must not satisfy the midpoint oracle for Diffuse/Ripple/Crumble/Particle
or Burn.

### 3.1 Use deterministic contrast cases

For parameter-sensitive cases, hold constant:

```text
source image
destination image
seed
logical size / framebuffer size
progress
effect time where applicable
```

and vary only the parameter under test.

The pair must produce a meaningful effect-specific difference.

### 3.2 Suggested discriminator families

These are robust properties to test, not mandatory exact pixel formulas.

#### Diffuse

Use coordinate/checker source/destination textures and shape-specific spatial statistics such as:

- orientation/periodicity of changed regions;
- connected-region distribution;
- shape-mask occupancy signature.

Assert the output is not compatible with a single monotonic half-plane wipe.

#### Ripple

For count1/count3/count8, compare radial/ring boundary frequency along controlled rays or equivalent
deterministic ring structure.

The three count cases must not render equivalently under the same seed/progress.

#### Crumble

For fixed seed/progress, weighting modes must alter deterministic old/new piece distribution or the
appropriate piece-selection statistic.

Do **not** invent a visual `mosaic_mode` oracle while the canonical shader does not consume that
uniform.

#### Particle

Use effect-specific geometry/statistics:

- opposite directions move the destination/source particle field in opposite projected directions;
- Directional vs Swirl vs Converge differ in centroid/angular/radial structure;
- parameter cases that are intended to be visible must differ under fixed seed/progress.

Uniform wiring tests in `Docs/TestSuite.md` cover every authored control separately.

#### Burn

Use a fixed seed/time/progress and distinguish:

- front orientation for six directions;
- core/glow/char/destination regions from a plain wipe;
- smoke toggle changes smoke region;
- ash toggle changes ash region;
- toggles do not replace the separate proof that the core burn front exists.

### 3.3 Endpoints remain exact

Every stronger midpoint/contrast oracle is in addition to exact source and exact destination endpoint
guards.

## 4. Phase-C request/uniform and state-fence tests

The direct parameter→uniform wiring matrix and GL-state fence tests are ordinary focused pytest gates,
not replacements for the real-GL wrapper.

See `Docs/TestSuite.md`, Phase-C test-hardening audit.

The state-fence regression must include restoration when `renderer.render()` raises.

## 5. Visualizer authored-fidelity replay

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe tools\visualizer_replay.py verify
.\.venv\Scripts\python.exe tools\visualizer_replay.py metrics
```

Do not regenerate goldens merely to accommodate presentation migration.

For Bubble, also apply `Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

## 6. Logical-runtime gates

Search current tests by contract:

```powershell
rg -n "VisualizerLogicalRuntime|generation 0|mode switch|Spectrum|Pause|BTF|single clock|thread affinity" tests
```

Required:

- sole authored mode-general logical clock;
- every authored logical step preserved;
- latest-state semantics, no FIFO/catch-up;
- no paint acknowledgement;
- no producer/display divisor;
- no source/event decimation;
- no display-refresh logical cap;
- worker cannot mutate GUI/Quick/GPU;
- generation zero valid;
- protected visible edges survive;
- source freshness separate from presentation;
- worker joins cleanly.

## 7. Qt Quick migration checks

Use P0 evidence as architecture-selection record; do not expand P0 merely to reconfirm the chosen
presenter.

Focused Quick harnesses prove, as relevant:

- standalone QQuickWindow;
- threaded scene graph;
- current-generation state delivery;
- first intentional frame;
- immutable render-boundary state;
- Settings/recreate;
- topology/binding loss;
- resource cleanup;
- exact effect/visualizer contract being migrated.

## 8. Settings capability activation checks

After E2 lands, add focused Settings/runtime harnesses for:

- opening Widgets/Transitions SETUP without importing deactivated heavy modules;
- pills appearing/disappearing with activation;
- Settings save/recreate retaining inactive detailed configuration;
- widget provider/model/resource retirement;
- transition implementation dormancy;
- random effective pool correctness.

Do not require all Settings pages to be eagerly constructed merely to test them.

## 9. Physical evidence

When internal callbacks are insufficient, capture OS/display-boundary evidence and correlate it to
intentional active-motion windows.

Do not interpret startup/capture rows before intentional presentation as active-animation cadence
holes.

Do not infer continuous displayed FPS from sparse/non-occupancy GDI `DisplayedTime` rows.

Use p95/p99/tails/severe gaps plus phase correlation when cadence evidence is actually needed.

## 10. Runtime diagnostics

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

## 11. Lifecycle

Check:

- logical runtime stop/join;
- stale-state fencing;
- generation zero;
- Quick scene/window retirement;
- render-resource retirement;
- deactivated capability runtime retirement after E2;
- no retired callback publication;
- no background thread/process preventing test or product shutdown.

A pytest summary followed by a process that never exits strongly suggests leaked shutdown ownership
and should be diagnosed rather than hidden by a larger timeout.

## 12. Historical evidence

Historical harnesses may describe old QRhiWidget/QOpenGLWidget/GLCompositor presentation paths. They
remain evidence, not architecture instructions.

Do not copy a historical presentation mechanism back into Qt Quick because the historical harness is
detailed.
