# Harness Index

Last updated: 2026-09-01

Compact routing for recurring investigation and migration sign-off commands.

`Docs/TestSuite.md` is the canonical live test inventory/retirement ledger. This file routes useful
commands and runtime harnesses; it is not an exhaustive manifest and does not decide whether a legacy
test still has architectural authority.

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

Use `Docs/TestSuite.md` to identify current/permanent, migration-critical, WILL-BE-OBSOLETE and obsolete
test ownership.

For current destination-authority work, use the maintained phase-neutral profile owned by `Docs/TestSuite.md`:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

Maintained profiles isolate selected targets in fresh pytest subprocesses so queued Qt/QQuick teardown from one target cannot
poison an unrelated result. `--chunks` groups/logs those isolated targets; it is not four giant shared Qt processes.

The whole-tree wrapper remains a broad Phase-I **reconciliation diagnostic**:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

Do not treat a red whole-tree run as proof the active slice failed until the relevant failure/log and owner classification are
inspected. A completed pytest summary followed by a process that never exits strongly suggests shutdown/lifecycle ownership and
should be isolated rather than hidden with a longer timeout.

## 1A. Qt/QML sidecar evidence

For any runtime-shaped or physical Quick/QML claim, collect and inspect both:

```text
logs/screensaver.log
logs/screensaver_qml.log
```

A successful capture eagerly creates `screensaver_qml.log` with a session marker even when Qt emits zero messages. Missing sidecar therefore means the Qt/QML evidence plane is unavailable and the run cannot prove “no QML errors.”

Focused capture validation: `pytest tests/test_qt_message_capture_contract.py tests/test_qt_message_capture_qml_runtime.py -q --tb=short`. The second test requires real PySide6/QQmlEngine.

Relevant Qt/QML warning/error lines must be correlated to the same timestamp window before calling a runtime/J claim GREEN. Use `Docs/Qt_QML_Observability.md` for capture semantics and the raw-stderr boundary.

## 2. Phase-C Quick transition regression harnesses

Phase-C implementation and deterministic hardening are landed. These commands remain useful regression/
acceptance harnesses; they are **not an unfinished Phase-C implementation checklist**.

### Blinds

```powershell
python tools\qtquick_blinds_smoke.py --direction horizontal --windows 1
python tools\qtquick_blinds_smoke.py --direction vertical   --windows 1
python tools\qtquick_blinds_smoke.py --direction diagonal   --windows 1
```

Use `--windows 2` only when physical multi-display evidence is intentionally being exercised.

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

For parameter-sensitive cases hold constant, as applicable:

```text
source image
destination image
seed
logical/framebuffer size
progress
effect time
```

and vary only the parameter being tested.

Effect-specific midpoint/contrast oracles supplement exact endpoints:

- Diffuse: shape-specific spatial properties must reject a plain wipe/crossfade substitute;
- Ripple: count1/count3/count8 produce distinct radial/ring structure;
- Crumble: weighting changes deterministic old/new piece distribution;
- Particle: direction/mode changes centroid/angular/radial structure;
- Burn: front/core/glow/char progression is distinct from a wipe; smoke/ash toggles prove their own
  regions but do not replace core-burn proof.

Do not invent a visual `mosaic_mode` oracle while the canonical Crumble shader does not consume it.

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

## 8. Closed E/F/G/H ownership regressions and current I routing

### 8.1 Landed E/F capability/ownership foundation

Focused tests already guard:

- widget family catalog and environment gating;
- canonical activation settings/helpers;
- Visualizers capability dependency on Media while retaining special runtime ownership;
- effective transition Random pool filtering and final activation/hardware admission;
- Widgets/Transitions `SETUP`, live lazy navigation and hidden-page save safety;
- runtime widget factory creation filtered by family activation;
- global-singleton Visualizer CUSTOM 30-second failover/reclaim generation/lifecycle rules.

When touching that foundation, route through current test ownership in `Docs/TestSuite.md`; common files
include:

```text
tests/test_widget_family_catalog.py
tests/test_capability_activation.py
tests/test_transition_distribution.py
tests/test_widget_manager_refresh.py
tests/test_visualizer_failover_reclaim.py
```

This list is routing, not a frozen manifest.

### 8.2 Closed E1 ownership regression

E1 is closed. Its surviving owner tests remain permanent regression coverage for:

- family-exclusive providers/models;
- timers/polls/refresh callbacks;
- processes/workers;
- shared-service references;
- generation/model registration;
- clean deactivation retirement/reactivation;
- fresh-process deactivated import/construction dormancy.

Do not describe this as future Phase-E work and do not infer full provider/process dormancy from factory-creation gating alone.

### 8.3 Landed Settings capability UI regression

Preserve focused Settings/runtime cases for:

- Widgets/Transitions `SETUP` opening without heavy deactivated module imports;
- pills appearing/disappearing live with activation;
- selected deactivated page returning to `SETUP` immediately;
- Settings save/recreate retaining inactive detailed configuration;
- lazy hidden pages not overwriting stored values;
- transition renderer dormancy;
- Random effective-pool correctness;
- explicit zero-activated-transition state repair.

Provider/model/resource retirement assertions stay at the actual neutral owner; do not move them back into presentation tests.

### 8.4 Current destination routing

G4/G7/G8/H implementation and H physical acceptance are closed. Do not use old phase command bundles as the current bar.

The maintained `destination` profile is the ordinary broad architecture regression route:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

Use smaller focused files/nodeids first for the slice being changed. The destination profile covers deterministic/runtime-shaped Quick
display/unit/family/CUSTOM/input/transition/visualizer ownership, including the stronger technical-config + real retained-item
visualizer boundary. It intentionally does **not** turn operator-hardware-dependent QScreen/topology cells into a per-commit H
gate.

Real two-display identity/topology, A -> B -> A physical ingress, mixed refresh/DPR, off/wake and final installed
multi-display acceptance remain J evidence. Run those physical cells separately/isolated when the claim requires the operator's
actual hardware.


## 9. Physical evidence

When internal callbacks are insufficient, capture OS/display-boundary evidence and correlate it to
intentional active-motion windows.

Do not interpret startup/capture rows before intentional presentation as active-animation cadence holes.
Do not infer continuous displayed FPS from sparse/non-occupancy GDI `DisplayedTime` rows.
Use p95/p99/tails/severe gaps plus phase correlation when cadence evidence is actually needed.

R-26 remains a separate **PARTIAL / AWAITING VALIDATION** historical topology/failover record until its full off/asleep/late-return sequence is exercised on corresponding hardware. That residual is J physical evidence and does not reopen H; implementation review alone does not manufacture the missing scenario.

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

Keep observer overhead named. Do not invent another probe family when existing evidence can answer the
question.

## 11. Lifecycle

Check as relevant:

- logical runtime stop/join;
- stale-state fencing;
- generation zero;
- Quick scene/window retirement;
- render-resource retirement;
- deactivated capability retirement at the owner that has actually migrated;
- no retired callback publication;
- no background thread/process preventing test/product shutdown.

A pytest summary followed by a process that never exits should be diagnosed as ownership/lifecycle
failure rather than hidden by larger timeout values.

## 12. Historical / current-legacy harnesses

Historical harnesses may describe QOpenGLWidget/QRhiWidget/GLCompositor paths. They remain evidence,
not current architecture instructions.

Current pre-cutover harnesses that assert the still-live QRhi/GLCompositor presenter are
**CURRENT-LEGACY — WILL BE OBSOLETE at H/I** unless `Docs/TestSuite.md` identifies a surviving contract
that must first be rehomed to Quick.

Do not copy a historical presentation mechanism back into Qt Quick merely because its old harness is
detailed.
