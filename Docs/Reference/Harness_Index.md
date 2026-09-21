# Harness Index

Compact routing for recurring regression, attribution and installed-acceptance commands.

`Docs/TestSuite.md` is the canonical live test inventory/retirement ledger. This file routes useful
commands and runtime harnesses; it is not an exhaustive manifest and does not decide whether a legacy
test still has architectural authority.

Harness success is evidence, not automatic final visual/timing/lifecycle sign-off. Run each harness in
the environment appropriate to the claim it makes; physical cadence, GPU utilization, subjective
motion feel and real multi-monitor topology require corresponding Windows/Qt/OpenGL/hardware evidence.

SRPSS does not use hosted repository CI as the normal local acceptance path unless the operator
explicitly requests it.

## 1. Targeted tests first

For retained ordinary Edit changes, the shared native painter test (`tests/test_qtquick_child_mapped_geometry.py`) covers clipped/applied transforms and repeated family-owned normalization values. Combine it with the specific family scene tests (Clock, System Stats, Friend Pulse, Weather, Achievement Pulse or Abandonment Issues) and the import-free lifetime/paint source contracts. Stable role identity and real painted bounds must both pass; a green source scan cannot certify native gesture responsiveness.

Ordinary widget pixels and resize geometry: `python -m tools.ordinary_widget_resize_capture
--output logs/widget_resize_normalization/before`. The retained long-term harness,
comparison command and evidence boundaries are documented in
[Ordinary_Widget_Resize_Capture.md](../Guides/Ordinary_Widget_Resize_Capture.md).

Offline Visualizer reactivity evidence is test/fixture-owned: `python -m pytest tests/test_visualizer_replay.py -q` exercises deterministic replay assertions against retained fixtures/goldens. The old Visualizer replay executable is retired; do not recreate its deleted physical host merely for convenience. Use live PERF/installed evidence for scheduler/delivery/presentation questions.

Prefer the smallest test set that can falsify the current slice:

```powershell
pytest path\to\test_file.py -q --tb=short
```

Use `Docs/TestSuite.md` to identify current/permanent, environment-gated, obsolete and rehome test ownership.

For current destination-authority work, use the maintained profile owned by `Docs/TestSuite.md`:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

Maintained profiles isolate selected targets in fresh pytest subprocesses so queued Qt/QQuick teardown from one target cannot
poison an unrelated result. `--chunks` groups/logs those isolated targets; it is not four giant shared Qt processes.

The whole-tree wrapper is a broad **reconciliation/regression diagnostic**, not the primary product gate:

```powershell
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

Do not treat a red whole-tree run as proof the active slice failed until the relevant failure/log and owner classification are
inspected. A completed pytest summary followed by a process that never exits strongly suggests shutdown/lifecycle ownership and
should be isolated rather than hidden with a longer timeout.

### GODZIP Foundry operator commands

Launch `python tools\godzip_foundry.py` from the current repo environment. The CMD tab's **RUN CHUNKED SUITE** button enters and runs `python tests\run_chunked.py --chunks 4 --log` in captured PowerShell. It is a broad whole-tree reconciliation run, **not** the isolated `destination` product gate above. RUN SCRIPT accepts a deliberate pasted command, while CLEAR & PASTE only replaces the editor text. Captured mode provides Stop Run, a bounded transcript and results export; external-terminal mode does not capture results or report completion. The APPLY tab refreshes discovered ZIP locations on entry without re-inspecting the currently selected archive. These buttons do not change test authority or allow output to stand in for physical validation.

## 1A. Qt/QML sidecar evidence

For any runtime-shaped or physical Quick/QML claim, collect and inspect both:

```text
logs/screensaver.log
logs/screensaver_qml.log
```

A successful capture eagerly creates `screensaver_qml.log` with a session marker even when Qt emits zero messages. Missing sidecar therefore means the Qt/QML evidence plane is unavailable and the run cannot prove “no QML errors.”

Focused capture validation: `pytest tests/test_qt_message_capture_contract.py tests/test_qt_message_capture_qml_runtime.py -q --tb=short`. The second test requires real PySide6/QQmlEngine.

Relevant Qt/QML warning/error lines must be correlated to the same timestamp window before calling a runtime/physical claim GREEN. Use `Docs/Guides/Qt_QML_Observability.md` for capture semantics and the raw-stderr boundary.

## 1B. Tooling authority

Use `Docs/Reference/Harness_Index.md` plus `Docs/TestSuite.md` before preserving an old script; absent retired tooling belongs to source history, not a recreated audit file. Production code must never import operator analysis tools (`R-72`). Built-in PERF/usage/QML telemetry is the primary application-health evidence; retain external parsers only for a narrow demonstrated cross-event question.

Current independent resource observation:

```powershell
python tools\perf_measure.py --pid <PID> --duration 30
```

Current ImageWorker shared-memory lifecycle proof:

```powershell
python tools\image_worker_shm_lifecycle_harness.py --cycles 50 --width 3840 --height 2160
```

`tests/run_chunked.py` is the maintained test-runner entrypoint. Do not add a secondary test-runner facade or bypass the runner's profile-isolation policy.

### Retained Visualizer causal/lifecycle diagnostics — no active investigation

The post-switch performance investigation is closed, but two explicitly admitted diagnostics remain useful if future normal use/logs expose a persistent or traceable Visualizer issue:

```powershell
python tools\visualizer_switch_abc_harness.py auto --condition A --layout-slot 1 --workers 4 --log logs\screensaver_perf.log --out logs\abc_A.auto.json --rep-out logs\abc_A.json --run-cmd "python main_mc.py --usage --viz --perf --life"
python tools\qtquick_visualizer_switch_smoke.py
```

`visualizer_switch_abc_harness.py` uses the R-80 window-local event-loop oracle and fails old rolling-only causal logs closed. `--abc-drive` and `--viz-switch-telemetry` are explicit diagnostic admissions; the retained render-host ownership telemetry is boundary-only and allocates only when admitted. The closed P4 per-frame/per-draw presentation/fence timing hooks were removed and must not be restored without a new reproduced defect and a concrete missing fact.

These harnesses are **not scheduled work** and rapid-switch startup hitching alone is not a defect. Reopen only from future evidence that persists/grows after the triggering activity. R-80 is the permanent historical oracle/failure record.

## 2. Quick transition regression harnesses

For the expanded effects, render deterministic textured progressions through the production GL host:

```powershell
C:/Python311/python.exe tools/transition_contact_sheet.py --effect glass_shatter --direction center_out --output-dir <output-directory>
C:/Python311/python.exe tools/transition_contact_sheet.py --effect pixel_accretion --width 3840 --height 2160 --output-dir <output-directory>
C:/Python311/python.exe tools/transition_contact_sheet.py --effect melt_drip --source <source-photo> --destination <destination-photo> --animate --output-dir <output-directory>
C:/Python311/python.exe tools/transition_contact_sheet.py --effect glass_shatter --quick-smoke --windows 2 --output-dir <output-directory>
```

The tool accepts optional `--source` / `--destination` photos. `--animate` writes a 60-frame, two-second WebP progression. `--quick-smoke` reuses the existing threaded Quick harness for two generations and hide/show; inspect reported physical-screen count because a request for two windows cannot prove two-display behavior when only one screen is connected. Effect IDs and ownership are in `Docs/Reference/Transitions.md`. Offscreen timing and captures do not close operator heavy-load/freshness acceptance.

These commands are retained regression/acceptance harnesses for the current Quick transition implementations; they are not an implementation checklist.

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

## 3. Transition discriminator expectations

The real-GL smokes protect parameter-sensitive transition behavior. Do not create a separate strengthening project merely because this section is detailed.

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
- Crumble: release weighting changes deterministic closed-prism departure, rough broken sides and parent-bound chip debris;
- Particle: direction/mode changes centroid/angular/radial structure;
- Burn: front/core/glow/char progression is distinct from a wipe; smoke/ash toggles prove their own
  regions but do not replace core-burn proof.

Do not restore retired mosaic assumptions: Crumble owns weighted parent release and polygon-seam debris, not a mosaic mode.

## 4. Transition request/uniform and GL-state tests

Direct parameter -> uniform wiring and common GL-state-fence coverage are ordinary focused pytest
regressions. They supplement rather than replace the real-GL wrappers.

The common fence includes the exception path where renderer execution raises.

See `Docs/TestSuite.md` and `Docs/Guides/Transition_Change_Checklist.md`.

## 5. Visualizer authored-fidelity evidence

The old Visualizer replay executable is retired because it imported the deleted replay physical owner. **Do not restore that host.**

Preserve authored evidence through current temporal/BTF/viewport tests plus `tests/fixtures/visualizer_replay/`, `tests/goldens/visualizer_replay/` and `tests/goldens/visualizer_temporal/`. The former replay-fixture generator is no longer in the current tree; fixture/golden data remains evidence and must not be regenerated through a resurrected replay presenter.

Do not regenerate goldens merely because implementation ownership changed. For Bubble, apply `Docs/Guardrails/Bubble_Temporal_Fidelity.md`.

## 6. Visualizer logical-runtime permanent gates

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

These are permanent/future-integration gates, not instructions to rerun closed architecture-selection work.

## 7. Qt Quick runtime checks

The Qt Quick presenter is accepted architecture. Use focused runtime evidence for the seam being changed rather than rerunning old architecture-selection experiments.

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

## 8. Capability/runtime ownership regression routing

### 8.1 Capability/ownership foundation

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
tests/test_visualizer_failover_reclaim.py
```

This list is routing, not a frozen manifest. Resolve exact test functions and current existence from `tests/run_chunked.py` and the source tree before running a command.

### 8.2 Shared runtime/service ownership

Permanent owner tests cover:

- family-exclusive providers/models;
- timers/polls/refresh callbacks;
- processes/workers;
- shared-service references;
- generation/model registration;
- clean deactivation retirement/reactivation;
- fresh-process deactivated import/construction dormancy.

Treat this as current capability/dormancy architecture and do not infer full provider/process dormancy from factory-creation gating alone.

### 8.3 Settings capability UI regression

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

### 8.4 Current broad routing

The related implementation/physical acceptance is closed. Use the current focused gates in this index and `Docs/TestSuite.md`, not old command bundles.

The maintained `destination` profile is the ordinary broad architecture regression route:

```powershell
python tests/run_chunked.py --profile destination --chunks 4 --timeout-seconds 900 --log
```

Use smaller focused files/nodeids first for the slice being changed. The destination profile covers deterministic/runtime-shaped Quick
display/unit/family/CUSTOM/input/transition/visualizer ownership, including the stronger technical-config + real retained-item
visualizer boundary. It intentionally does **not** turn operator-hardware-dependent QScreen/topology cells into an ordinary automated
gate.

Real two-display identity/topology, A -> B -> A physical ingress, mixed refresh/DPR, off/wake and final installed
multi-display acceptance remain physical evidence. Run those cells separately/isolated when the claim requires the operator's
actual hardware.

### 8.5 Friend Pulse / System Stats retained-card evidence

Use the focused source/runtime/QML suites before the shared architecture gate. The smoke tool instantiates the production
Quick host/components and writes standard, busy and shared-40%-floor captures for Friend Pulse Grid/Rows/Strict plus
System Stats. It also captures the six-friend responsive three-column Grid. The harness uses inert fixture services and
never contacts Steam or starts the product sampler.

```powershell
python -m pytest tests/test_steam_friend_pulse.py tests/test_friend_pulse_runtime.py tests/test_qtquick_friend_pulse_presentation.py tests/test_friend_pulse_stack_predictor.py tests/test_system_stats_source.py tests/test_system_stats_runtime.py tests/test_qtquick_system_stats_presentation.py tests/test_system_stats_settings.py -q
python -m pytest tests/test_steam_links.py tests/test_secure_url_launcher.py tests/test_qtquick_family_product_actions.py -q
python tools/qtquick_friend_system_stats_smoke.py --output-dir <capture-directory>
python -m core.settings.defaults_snapshot_builder --check-all
```

The preserved bounded System Stats source admission harness remains:

```powershell
python tools/system_stats_s0_probe.py --condition cpu-ram --samples 3 --interval-seconds 10
python tools/system_stats_s0_probe.py --condition cpu-ram --samples 3 --interval-seconds 10 --contention-workers 2
```

See `Docs/Reference/System_Stats_Widget.md` for the current product contract plus the preserved CPU/RAM admission and rejected GPU/VRAM evidence.


## 9. Physical evidence

When internal callbacks are insufficient, capture OS/display-boundary evidence and correlate it to
intentional active-motion windows.

Do not interpret startup/capture rows before intentional presentation as active-animation cadence holes.
Do not infer continuous displayed FPS from sparse/non-occupancy GDI `DisplayedTime` rows.
Use p95/p99/tails/severe gaps plus phase correlation when cadence evidence is actually needed.

R-26 remains a separate **PARTIAL / AWAITING VALIDATION** historical topology/failover record until its full off/asleep/late-return sequence is exercised on corresponding hardware. That residual requires physical evidence; implementation review alone does not manufacture the missing scenario.

## 10. Runtime diagnostics

Use only relevant existing diagnostic flag families such as:

```text
--perf
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
- deactivated capability retirement at the current owning runtime;
- no retired callback publication;
- no background thread/process preventing test/product shutdown.

A pytest summary followed by a process that never exits should be diagnosed as ownership/lifecycle
failure rather than hidden by larger timeout values.

## 12. Historical / retired harnesses

Historical harnesses may describe QOpenGLWidget/QRhiWidget/GLCompositor paths. They remain evidence, not current architecture instructions. A surviving harness that asserts a retired physical presenter is obsolete unless `Docs/TestSuite.md` identifies a still-valid neutral behavior that must first be rehomed to the current owner.

Do not copy a historical presentation mechanism back into Qt Quick merely because its old harness is detailed.
