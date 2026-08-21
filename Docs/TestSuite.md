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

Discover current tests by owner/defect, not stale phase numbering.

Do not use a red broad-suite run as the only evidence that the active migration slice failed. Inspect
its exact failures/timeouts and run the smallest focused gate that can falsify the changed contract.

Tests run in the environment appropriate to the claim:

- ordinary deterministic/source/unit work: the current capable Windows worktree;
- clean checkout only when reproduction/isolation specifically requires it;
- real Quick/OpenGL: the Windows/Qt/OpenGL environment;
- physical-display/refresh/DPR/GPU/eyes-on: the corresponding real hardware.

## 2. Hosted CI policy

SRPSS does not use repository-hosted CI as the normal migration workflow.

Do not add GitHub Actions or another hosted workflow unless the operator explicitly asks for it.

Hosted convenience must never replace required Windows/Qt/OpenGL/physical-display evidence.

## 3. Validation levels

### A — pure/unit

Settings, registries, geometry, cache keys, numerical visualizer helpers, generation helpers.

### B — component/integration

Logical mailbox/state bridge, widget models, Settings capability activation, Quick presentation-state
mapping, render-state transport, lifecycle ownership.

### C — runtime-shaped

Real logical worker, Quick window creation, threaded scene graph, mode switching, Pause/Play,
Settings/recreate, stale-generation fencing.

### D — real Windows/driver

Required for:

- real standalone QQuickWindow;
- actual threaded scene graph;
- real GL shader/program execution;
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

## 4. Permanent transition gates

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

## 5. Phase-C test-hardening audit

Phase C implementation is structurally complete, but the audit found coverage that can falsely accept
simplified or partially wired effects.

When the operator selects **Phase C tests**, improve tests/harnesses only first. Do not redesign
transition code unless a strengthened test exposes a real defect.

### 5.1 Real-GL oracles must distinguish the effect

Diffuse/Ripple/Crumble/Particle/Burn midpoint checks may not pass solely because source, destination
and some effect pixels coexist.

Keep the existing real-GL harnesses and add robust effect-specific discriminators.

Use fixed seeds/input/progress and prefer regional/statistical/geometry properties over brittle exact
screenshots.

### 5.2 Parameter sensitivity

Under the same synthetic images/seed/progress, prove selected values alter the output for:

- Ripple count1/count3/count8;
- Crumble weighting modes;
- Particle directions/modes;
- Burn smoke/ash toggles.

### 5.3 Request → uniform wiring

Add direct renderer-boundary uniform-recording tests for:

- Diffuse;
- Ripple;
- Crumble;
- Particle;
- Burn.

Particle coverage:

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

Burn coverage includes all authored effect uniforms plus run-clock-derived `u_time`.

A fake/recording uniform sink is correct for wiring tests; it does not replace real-GL smoke.

### 5.4 GL-state fence

Directly seed/mutate/restore:

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

Run the same restoration assertion when `renderer.render()` raises.

### 5.5 Sparse defaults

Add Blinds and Ripple to existing sparse canonical-default coverage.

### 5.6 Controller false-pass

In:

```text
tests/test_qtquick_transition_controller.py
test_runs_require_explicit_interruption_and_are_generation_fenced
```

assert cancellation separately. Only the generation-mismatched `start(_request(generation=8))`
belongs inside the expected-raise assertion.

### 5.7 Crumble mosaic_mode

Do not write a visual behavior test for `mosaic_mode` while the canonical fragment shader declares
`u_mosaic_mode` but does not consume it.

Test only optional uniform upload when present.

### 5.8 Inventory duplication

Remove/derive `_ALL_QUICK_TRANSITION_IDS` where practical. Registry parity is the canonical
independent inventory gate.

### 5.9 Environment fidelity

Do not remove or mock away real Windows/Qt/OpenGL/physical-display tests because another environment
cannot run them.

## 6. Permanent visualizer gates

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

Do not regenerate behavioral goldens merely because presentation architecture changed.

## 7. Quick presentation gates

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

## 8. Settings capability activation gates

After Phase E2 lands, preserve tests for:

- Widgets/Transitions `SETUP` first-pill existence;
- deactivated capabilities absent from normal pill navigation;
- cheap catalog construction without heavy module import;
- widget activation separate from per-instance `enabled`;
- transition activation separate from random-pool membership;
- effective random pool = activated ∩ pool membership;
- inactive settings retained through save/recreate;
- lazy unhydrated pages never clobber stored settings;
- runtime/resource teardown on deactivation;
- no heavy import on fresh process for deactivated capability.

## 9. Physical frame-pacing gate

Report separately per display:

- physical p50/p90/p95/p99/max;
- severe-gap counts;
- request/synchronization age where meaningful;
- logical cadence;
- source age;
- CPU/GPU context.

Average FPS is secondary.

Internal `frameSwapped`/render callbacks are proxies, not physical-display proof.

## 10. Heavy-load interpretation

The completed P0 experiment showed Quick remains approximately in the old light-load presentation
class even under substantial external CPU load.

Do not require every heavy-load outlier to disappear before migration.

Heavy load is resilience evidence, not permission to reopen the old architecture.

## 11. Lifecycle gate

Repeatedly exercise:

- normal startup/shutdown;
- Settings/recreate;
- Edit/CUSTOM;
- visualizer active;
- transitions active;
- capability activation/deactivation after E2;
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

## 12. Migration parity

For each migrated presentation family, require the relevant combination of:

- visual parity;
- behavior parity;
- input parity;
- geometry/DPR parity;
- lifecycle parity;
- performance not regressing the Quick architecture win.

## 13. Completion rule

Green focused tests are necessary but not sufficient.

**Implementation closure and acceptance closure are distinct.**

An acceptance/sign-off ledger stays open until the assigned tests/gates have actually run and the
result is recorded against commit/environment.

Do not turn an unchecked gate into a pass because:

- source review looks good;
- another agent says it should pass;
- a different environment cannot execute it;
- later implementation has already begun.

A later failure reopens the smallest demonstrated defect.
