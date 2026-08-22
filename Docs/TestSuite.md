# Test Suite Guide

Last updated: 2026-08-22

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

Discover current tests by owner/defect, not stale phase numbering.

Do not use a red broad-suite run as the only evidence that the active slice failed. Inspect exact
failures/timeouts and run the smallest focused gate that can falsify the changed contract.

Tests run in the environment appropriate to the claim:

- deterministic/source/unit/settings work: current capable Windows worktree;
- clean checkout only when isolation/reproduction specifically benefits;
- real Quick/OpenGL: proper Windows/Qt/OpenGL environment;
- physical display/refresh/DPR/GPU/eyes-on: corresponding real hardware.

## 2. Hosted CI policy

SRPSS does not use repository-hosted CI as the normal migration workflow.

Do not add GitHub Actions or another hosted workflow unless the operator explicitly asks for it.

Hosted convenience never replaces Windows/Qt/OpenGL/physical-display evidence where that is the claim.

## 3. Validation levels

### A — pure/unit

Settings, catalogs, registries, geometry, cache keys, numerical helpers, generation helpers.

### B — component/integration

Logical mailbox/state bridge, widget family/activation logic, widget models, Settings capability
activation, Quick presentation-state mapping, render-state transport, lifecycle ownership.

### C — runtime-shaped

Real logical worker, Quick window creation, threaded scene graph, transition/visualizer state flow,
Pause/Play, Settings/recreate, activation runtime consequences, stale-generation fencing.

### D — real Windows/driver

Required for claims involving:

- real standalone `QQuickWindow`;
- actual threaded scene graph;
- real GL shader/program execution;
- multi-display/refresh/DPR;
- GPU/resource ownership;
- physical frame pacing;
- compiled/frozen build.

### E — manual visual

Required where subjective appearance/feel is part of the requirement, including:

- Bubble feel/BTF;
- transition authored visual parity/continuity;
- Spectrum idle visibility;
- Pause/Play hitch;
- startup/reveal;
- widget visual parity/shadows.

## 4. Permanent transition gates

Preserve tests for:

- canonical registry <-> Quick implementation parity;
- lazy/dormant implementation resolution;
- application activation admission;
- Settings/default/random parameter resolution before render admission;
- immutable transition request/run state;
- exact endpoints and authored direction/mode variants;
- authored shader/math preservation where contractually required;
- interruption/exactly-once completion;
- generation fencing;
- GL-state restoration including exception path;
- resource teardown.

Real-GL and physical-display transition routing lives in `Docs/Harness_Index.md`.

## 5. Landed Phase-C hardening — preserve, do not redo

Phase-C deterministic hardening has already landed. The following are permanent regression
requirements, **not TODOs for a new agent to implement again**.

### 5.1 Effect-discriminative real-GL oracles

Diffuse/Ripple/Crumble/Particle/Burn midpoint checks must reject generic wipe/crossfade/spatial reveal
substitutes.

Use fixed seed/input/progress and robust spatial/statistical/geometry properties where possible.

### 5.2 Parameter sensitivity

Retain deterministic contrast coverage for:

- Ripple count1/count3/count8;
- Crumble weighting modes;
- Particle directions/modes;
- Burn smoke/ash toggles.

### 5.3 Request -> uniform wiring

Retain direct renderer-boundary wiring coverage for Diffuse/Ripple/Crumble/Particle/Burn.

Particle covers:

```text
mode
direction
radius
overlap
trails
swirl strength
swirl turns
swirl order
3D shading
texture mapping
wobble
gloss
light direction
seed
physical framebuffer resolution
```

Burn covers authored effect uniforms plus run-clock-derived `u_time`.

A recording/fake uniform sink is correct for wiring tests and does not replace real-GL smoke.

### 5.4 GL-state fence

Retain direct seed/mutate/restore coverage for:

```text
viewport
scissor where promised by host
program
VAO
array buffer
active texture
texture units 0/1
blend
cull
depth enable
depth write
depth function
depth clear
stencil
```

Run the same restoration assertion when renderer execution raises.

### 5.5 Sparse defaults / controller false-pass / inventory

Keep:

- Blinds and Ripple in sparse canonical-default coverage;
- cancellation asserted separately from generation-mismatched expected-raise logic;
- registry parity as canonical inventory rather than a duplicate hard-coded id list;
- Crumble `mosaic_mode` limited to actual shader behavior.

Do not weaken real environment tests because another environment cannot run them.

## 6. Permanent visualizer gates

Preserve tests for:

- one `VisualizerLogicalRuntime`;
- actual authored scheduler cadence;
- every authored logical step integrated before presentation coalescing;
- logical worker cannot mutate GUI/Quick/GPU state;
- valid generation `0`;
- all five modes;
- source freshness;
- renderer-visible protected Bubble consequences;
- Pause/Play identity;
- clean worker join;
- BTF;
- one authored fade authority with derived layer values rather than a second fade clock;
- 1.5 default aspect and 420x280 as internal reference only;
- baseline/wide/tall geometry without anisotropic distortion;
- selected local SDF/stencil clip semantics.

Do not regenerate behavioral goldens merely because presentation architecture changed.

## 7. Quick presentation gates

Add/retain runtime-shaped proof for:

- one standalone top-level `QQuickWindow` per selected physical display;
- threaded render loop active;
- render-thread identity distinct from GUI thread on supported Windows path;
- inline custom GL through selected `QSGRenderNode` seam;
- no `QQuickWidget`;
- no second accelerated runtime surface;
- bounded latest-state synchronization;
- stale generation rejected;
- intentional first frame;
- Settings/recreate;
- topology recreation;
- clean shutdown.

## 8. Phase-E activation foundation gates

The activation mechanism is already partially landed. Preserve tests for:

### 8.1 Widget family catalog

- canonical family membership;
- environment/dev gating derived from active runtime descriptors;
- visualizer excluded from widget-family activation;
- stable family lookup helpers.

### 8.2 Canonical activation schema/helpers

- missing keys resolve compatibly/activated;
- widget family read/write;
- transition read/write;
- effective Random pool = activated ∩ saved pool membership;
- activation distinct from instance enabled/pool membership.

### 8.3 Transition runtime admission

- deactivated transition excluded from cycle/manual/random resolution when a valid activated choice
  exists;
- deterministic activated manual fallback;
- effective pool filtering;
- no stale pre-resolved choice bypasses activation.

The **zero activated transitions** case must have explicit coverage before E2 exposes it. A deactivated
Crossfade name is not a valid activated fallback.

### 8.4 Widget creation admission

- deactivated family filtered before factory widget/model/provider creation;
- ordinary per-instance `enabled` remains a separate state;
- unrelated family activation does not suppress another family.

Do not infer full provider/process dormancy from this gate alone while those owners have not yet moved
under E1.

## 9. E1 provider/model ownership gates

As the broader `WidgetRuntimeManager` split lands, test the real owner for:

- family model/provider lifetime;
- timers/polls/refresh callbacks;
- family-exclusive processes/workers;
- shared-service reference ownership;
- generation/model registration;
- deactivation teardown;
- fresh-process deactivated import/construction dormancy.

Only claim a resource dormant when the test reaches the owner that can actually start it.

## 10. E2 Settings capability UI gates

After E2 lands, preserve:

### Widgets

- first pill is `SETUP`;
- only activated family pills exist;
- deactivation removes pill **live** while Settings is open;
- deactivating selected page navigates immediately to Setup;
- reactivation restores pill live;
- page builds only on demand;
- Enable All/Disable All change family activation only;
- per-instance enabled/detail values survive activation toggles;
- hidden/unhydrated sections never overwrite stored settings.

### Transitions

- first pill is `SETUP`;
- only activated transition pills exist;
- live pill removal/re-addition;
- renderer implementation stays dormant for deactivated transition;
- Random effective pool equals activated ∩ saved pool membership;
- inactive pool preference can be preserved;
- Random-on pill browsing does not disable Random;
- manual selection fallback is deterministic and activated;
- zero-activated-transition policy is explicitly legal/prevented and tested;
- old dropdown/per-transition pool authority is removed after cutover.

## 11. Physical frame-pacing gate

Report separately per display:

- physical p50/p90/p95/p99/max;
- severe-gap counts;
- request/synchronization age where meaningful;
- visualizer logical cadence;
- source age;
- CPU/GPU context.

Average FPS is secondary.

Internal `frameSwapped`/render callbacks are proxies, not physical-display proof.

## 12. Heavy-load interpretation

P0 established the architectural case for Quick under external load.

Do not require every unrelated heavy-load outlier to disappear before migration can continue.

Heavy-load failure should be attributed to the smallest measured owner: GUI sync, Python/GIL work,
provider/service work, texture upload, scene cost, renderer cost or physical delivery.

Do not reduce authored visualizer cadence or widget fidelity merely to improve a benchmark.

## 13. Lifecycle gate

Repeatedly exercise as relevant:

- startup/shutdown;
- Settings/recreate;
- Edit/CUSTOM;
- visualizer active;
- transitions active;
- capability activation/deactivation;
- monitor topology changes;
- display off/wake.

Require:

- logical runtime joins;
- stale state rejected;
- generation zero preserved;
- retired scene cannot reveal;
- render resources return to expected baseline;
- no old-generation callback survives destruction;
- no background owner prevents process/test shutdown.

A pytest summary followed by a process that never exits is shutdown/lifecycle evidence to diagnose,
not a reason to raise the timeout blindly.

## 14. Migration parity

For each migrated presentation family, require the appropriate combination of:

- visual parity;
- behavior parity;
- input parity;
- geometry/DPR parity;
- lifecycle parity;
- performance not regressing the selected Quick architecture materially.

Explicitly retired presentation controls are not parity requirements.

## 15. Completion rule

Green focused tests are necessary but not sufficient.

**Implementation closure and acceptance closure are distinct.**

An acceptance/sign-off ledger stays open until assigned gates actually run and the result is recorded
against commit/environment.

Do not turn an unchecked gate into a pass because source review looks good, another agent says it
should pass, a different environment cannot execute it or later implementation has already begun.

A later failure reopens the smallest demonstrated defect.
