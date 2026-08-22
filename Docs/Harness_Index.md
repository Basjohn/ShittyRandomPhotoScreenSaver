# Harness Index

Last updated: 2026-08-22

Compact routing for recurring investigation and migration sign-off commands.

Harness success is evidence, not automatic final visual/timing/lifecycle sign-off. Run each harness in
the environment appropriate to the claim it makes; physical cadence, GPU utilization, subjective
motion feel and real multi-monitor topology require corresponding Windows/Qt/OpenGL/hardware evidence.

SRPSS does not use hosted repository CI as the normal migration harness path unless the operator
explicitly requests it.

## 1. Targeted tests first

Prefer the smallest test set that can falsify the current slice:

```powershell
pytest path\to\test_file.py -q --tb=short
```

Use `Docs/TestSuite.md` for broader suite guidance.

The bounded chunk wrapper remains a deliberate local diagnostic:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

Do not treat a red chunk/full-suite run as proof the active slice failed until the relevant failure/log
is inspected. A completed pytest summary followed by a process that never exits strongly suggests
shutdown/lifecycle ownership and should be isolated rather than hidden with a longer timeout.

## 2. Phase-C Quick transition regression harnesses

Phase-C implementation and deterministic hardening are landed. These commands remain useful regression/
acceptance harnesses; they are **not an unfinished Phase-C implementation checklist**.

### Blinds

```powershell
python tools\qtquick_blinds_smoke.py --direction horizontal --windows 1
python tools\qtquick_blinds_smoke.py --direction vertical   --windows 1
python tools\qtquick_blinds_smoke.py --direction diagonal   --windows 1
```

Use `--windows 2` only when the physical multi-display evidence is intentionally being exercised.

### Parameterized effects

```powershell
python tools\qtquick_phase_c_effect_smoke.py --effect <effect> --case <case> --windows 1
```

Canonical case families include:

- Diffuse: rectangle, membrane, lines, diamonds, amorph, random;
- Ripple: count1, count3, count8;
- Crumble: top, bottom, random-weighted, random-choice, age-weighted;
- Particle: authored modes/directions including directional variants, swirl and converge;
- Burn: six directions plus smoke/ash toggle cases.

Use exact tool/source case names if they differ from this human-readable summary.

## 3. Landed Phase-C discriminator expectations

The real-GL smokes were strengthened during Phase C and those properties remain regression requirements.
Do not create a second strengthening project merely because this section is detailed.

### 3.1 Deterministic contrast setup

For parameter-sensitive cases, hold constant as applicable:

```text
source image
destination image
seed
logical/framebuffer size
progress
effect time
```

and vary only the parameter being tested.

### 3.2 Discriminator families

#### Diffuse

Use shape-specific spatial properties such as orientation/periodicity, connected-region distribution
or mask occupancy so a monotonic half-plane wipe cannot satisfy the oracle.

#### Ripple

Count1/count3/count8 must show distinct ring/radial structure under the same seed/progress.

#### Crumble

Weighting modes must alter deterministic old/new piece distribution under fixed seed/progress.

Do not invent a visual `mosaic_mode` oracle while the canonical shader does not consume it.

#### Particle

Opposite directions/modes must produce direction/centroid/angular/radial structure consistent with the
authored effect. Direct uniform-wiring tests cover individual controls separately.

#### Burn

Distinguish the burn front/core/glow/char progression from a plain wipe; smoke/ash toggle cases prove
their regions without replacing the proof that the core burn effect exists.

### 3.3 Endpoints

Effect-specific midpoint/contrast oracles are in addition to exact source and destination endpoint
guards.

## 4. Phase-C request/uniform and GL-state tests

Direct parameter -> uniform wiring and common GL-state-fence coverage are ordinary focused pytest
regressions. They supplement rather than replace the real-GL wrappers.

The common fence includes the exception path where renderer execution raises.

See `Docs/TestSuite.md` and `Docs/Transition_Change_Checklist.md`.

## 5. Visualizer authored-fidelity replay

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe tools\visualizer_replay.py verify
.\.venv\Scripts\python.exe tools\visualizer_replay.py metrics
```

Do not regenerate goldens merely to accommodate presentation migration.

For Bubble, also apply `Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

## 6. Logical-runtime / Phase-D permanent gates

Search current tests by contract rather than stale test names when needed:

```powershell
rg -n "VisualizerLogicalRuntime|generation 0|mode switch|Spectrum|Pause|BTF|single clock|thread affinity" tests
```

Required properties include:

- sole authored mode-general logical clock;
- every authored logical step integrated before presentation coalescing;
- latest-state semantics, no FIFO/catch-up;
- no paint acknowledgement;
- no producer/display divisor;
- no source/event decimation;
- no display-refresh logical cap;
- worker cannot mutate GUI/Quick/GPU;
- generation zero valid;
- protected renderer-visible Bubble consequences survive coalescing;
- source freshness separate from presentation;
- worker joins cleanly;
- local SDF/stencil clip composes/restores valid inherited framebuffer state;
- 1.5 default aspect / wide/tall compatibility without anisotropic distortion.

Phase D is complete; these are permanent/future-integration gates, not instructions to rerun the whole
migration.

## 7. Qt Quick runtime checks

Use P0 evidence as architecture-selection record; do not expand P0 merely to reconfirm the chosen
presenter.

Focused Quick harnesses prove as relevant:

- standalone `QQuickWindow`;
- threaded scene graph;
- current-generation state delivery;
- first intentional frame;
- immutable render-boundary state;
- Settings/recreate;
- topology/binding loss;
- resource cleanup;
- exact transition/visualizer/widget contract being changed.

## 8. Phase-E capability activation checks

### 8.1 Landed foundation

Focused tests already guard:

- widget family catalog and environment gating;
- canonical activation settings/helpers;
- effective transition Random pool filtering;
- transition runtime selection/cycle activation admission;
- runtime widget factory creation filtered by family activation.

When touching that foundation, run the current focused tests around:

```text
tests/test_widget_family_catalog.py
tests/test_capability_activation.py
tests/test_transition_distribution.py
tests/test_widget_manager_refresh.py
```

Use exact current test names/source; this list is routing, not a frozen manifest.

Do not infer full E1 provider/process dormancy from factory-creation gating alone.

### 8.2 E1 ownership

As provider/model ownership moves under the presentation-neutral manager, harness/test the actual owner
for family-exclusive processes, timers/polls, providers/models, shared-service references and clean
retirement.

### 8.3 E2 Settings UI

After E2 lands, add/retain focused Settings/runtime cases for:

- Widgets/Transitions `SETUP` opening without heavy deactivated module imports;
- pills appearing/disappearing **live** with activation;
- selected deactivated page returning to `SETUP` immediately;
- Settings save/recreate retaining inactive detailed configuration;
- lazy hidden pages not overwriting stored values;
- widget provider/model/resource retirement at the legal runtime owner;
- transition renderer dormancy;
- Random effective-pool correctness;
- explicit zero-activated-transition policy.

Do not require every Settings page to be eagerly constructed merely to test it.

## 9. Physical evidence

When internal callbacks are insufficient, capture OS/display-boundary evidence and correlate it to
intentional active-motion windows.

Do not interpret startup/capture rows before intentional presentation as active-animation cadence
holes.

Do not infer continuous displayed FPS from sparse/non-occupancy GDI `DisplayedTime` rows.

Use p95/p99/tails/severe gaps plus phase correlation when cadence evidence is actually needed.

## 10. Runtime diagnostics

Use only relevant existing diagnostic flag families such as:

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

Do not invent another probe family when existing evidence can answer the question.

## 11. Lifecycle

Check as relevant:

- logical runtime stop/join;
- stale-state fencing;
- generation zero;
- Quick scene/window retirement;
- render-resource retirement;
- deactivated capability runtime retirement at the owner that has actually migrated;
- no retired callback publication;
- no background thread/process preventing test/product shutdown.

A pytest summary followed by a process that never exits should be diagnosed as ownership/lifecycle
failure rather than hidden by larger timeout values.

## 12. Historical evidence

Historical harnesses may describe old QRhiWidget/QOpenGLWidget/GLCompositor paths. They remain evidence,
not current architecture instructions.

Do not copy a historical presentation mechanism back into Qt Quick merely because its old harness is
detailed.
