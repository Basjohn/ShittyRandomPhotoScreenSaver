# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-22

## Source / reviewed checkpoints

Original architecture/decision orientation anchor:

```text
18c8f26756df83bd0d8828becc740c72d5526b21
4.7.2 - Pre-Quick Migration Docs v1
```

That SHA is historical orientation, not a required current HEAD.

Latest Phase-C closure checkpoint reviewed before this plan revision:

```text
e0abcad316081802bce302b835a4f9d23f11af79
Phase C plan: two-display closure complete (54/54); 3D-slab oracles deflaked
```

Later documentation/test-workflow commits may exist. Always inspect exact current `main` before acting.

The Qt Quick presenter decision and inline custom-GL primitive are closed by P0/Phase-A evidence.
Do not reopen the presenter or `QSGRenderNode` selection without concrete contradictory implementation
evidence.

## Required routing before active work

For a migration slice use:

```text
exact current source / pushed diff
        ↓
Current_Plan.md
        ↓
Spec.md + Docs/Compositor_Architecture.md + Docs/Contracts.md
        ↓
Docs/Guardrails.md + relevant focused guardrail
        ↓
ONLY the active Docs/QtQuick_Migration decomposition
        ↓
focused tests / current evidence
```

`Index.md` is the routing authority when unsure where a contract lives.

`Future_Work.md` is deferred new-feature/experiment scope, not migration work admission. Do not
implement from it while the active plan or `Future_Cleanup.md` contains important work unless the
operator explicitly selects an item.

---

# Active execution window

This file owns migration sequence and work admission. Technical decompositions under
`Docs/QtQuick_Migration/` explain how to execute admitted work; they do not create parallel phases.

| Phase | Current status | Implementation permission |
| --- | --- | --- |
| A — bootstrap/render-node proof | Structurally complete | Do not reopen; compiled smoke remains operator-scheduled later |
| B — runtime-host decomposition | Structurally complete | Do not reopen without contradictory evidence |
| C — base image + transitions | **IMPLEMENTATION COMPLETE; test-hardening/sign-off debt explicit** | Test/harness hardening may be explicitly selected; transition implementation changes only when stronger evidence exposes a real defect |
| D — visualizer | **COMPLETE** — all five modes on the Quick boundary; documentation closure landed; physical cadence/eyes-on remain operator-scheduled acceptance debt | Do not reopen without contradictory evidence |
| **E — widget presentation + capability setup foundation** | **IN PROGRESS** | **Normal implementation work belongs here now** |
| F — widget families | Waiting for E | Reference only |
| G — CUSTOM/input/auxiliary pixels | Waiting for F | Reference only |
| H — settings epoch + production cutover | Waiting for A–G implementation | Reference only |
| I — legacy presenter deletion | Waiting for H cutover | Reference only |
| J — tooling/final validation/docs closure | Waiting for migration implementation | Reference only |

## Phase promotion rule

A phase may move forward when its **implementation dependencies** are structurally closed even if
hardware-dependent/eyes-on acceptance remains explicitly deferred.

Deferred evidence must be listed with runnable commands/criteria. A later failure reopens the smallest
demonstrated owner/phase defect; it does not automatically roll the migration sequence backward or
authorize compatibility architecture.

Production cutover in Phase H still requires the full Quick implementation surface. Final release
acceptance in Phase J still requires scheduled physical/compiled evidence.

If the operator explicitly says **"continue from Phase C tests"** or equivalent, execute Section 7.5
before returning to current normal work. Phase D is complete; current normal work is Phase E.

---

# 0. Mission

Perform one production presentation migration:

```text
current QWidget / QRhiWidget runtime presentation
                    ↓
one standalone threaded QQuickWindow per physical display
                    ↓
Qt Quick retained scene + inline custom GL render nodes
```

Do not plan a second presenter migration afterward.

Keep unaffected product systems unless a later phase explicitly replaces a presentation-coupled part:

- `ScreensaverEngine` orchestration except display-runtime calls that must change;
- image source/provider backends;
- SettingsManager and persistence infrastructure;
- source/account/credential ownership;
- QWidget Settings UI;
- RSS/folder/media/GSMTC/provider logic;
- ProcessSupervisor / ThreadManager where still appropriate;
- `VisualizerLogicalRuntime`;
- authored visualizer algorithms/mode personality;
- useful CUSTOM layout math/behavior;
- transition registry/settings identity;
- product features/customization, **except presentation controls explicitly retired by this plan** (notably the pre-Quick per-mode visualizer card-height/growth controls).

Backward compatibility with pre-Quick **presentation state** is deliberately not a migration goal;
Phase H0 creates a new settings epoch.

---

# 1. Hard architecture rules

## 1.1 One production presenter

Do not add or preserve as final architecture:

- a QRhiWidget-vs-Quick runtime setting/env switch;
- `QQuickWidget`;
- a permanent facade making QQuickWindow pretend to be DisplayWidget;
- QWidget presentation embedded above/below the Quick runtime;
- a second accelerated visualizer/transition window;
- QRhiWidget fallback when Quick rendering fails;
- transition-by-transition fallback to the old compositor;
- a supported software-only/CPU presentation mode or GL capability-demotion ladder used as runtime
  compatibility fallback;
- screenshot-to-texture QWidget wrappers as final widgets;
- duplicated legacy and Quick widget presentation pipelines after cutover.

During migration, old production code may coexist as reference/current production until Phase H.
Once production cuts over, Phase I deletion begins immediately.

The selected custom-GL seam is:

```text
QQuickItem(ItemHasContents)
-> updatePaintNode()
-> QSGRenderNode
-> direct OpenGL inside the owning Quick scene
```

`QQuickRhiItem` is not the normal SRPSS custom-render path. If the selected `QSGRenderNode` seam is
proven fundamentally unusable in pinned PySide/compiled product, stop and revise the **single**
primitive deliberately; do not keep competing product primitives.

## 1.2 Refactor only presentation overload that migration exposes

Expected decomposition:

```text
DisplayWidget
    -> QuickDisplayRuntime/window owner
    -> RuntimeInputController
    -> QuickSceneController
    -> WidgetRuntimeManager
    -> CustomLayoutSession

GLCompositorWidget
    -> transition renderer/resource implementations
    -> visualizer renderer/resources
    -> presentation pacer ownership
```

Do not use the migration to rewrite unrelated provider/backend systems.

## 1.3 Preserve visual capability

Migration parity includes current supported presentation capabilities such as opacity,
backgrounds/cards, borders/radius, fonts/colors, shadows, artwork, separators/icons, progress
controls, stacking, monitor routing, pixel shift, dimming, CUSTOM geometry/edit, context interaction,
visualizer all five modes, transitions, and Media Center interaction.

Do not solve migration defects by flattening/removing authored effects. Explicitly retired legacy presentation controls are not parity requirements; the pre-Quick per-mode visualizer card-height/growth sliders are deliberately retired in Phase D rather than copied into Quick.

## 1.4 No premature full/compiled builds

During Phases C–G, normal gates are focused Python/static/runtime harnesses.

Do not run Nuitka/full installed builds merely as routine migration validation. Keep packaging inputs
current. Compiled/installed validation remains operator-scheduled unless explicitly requested earlier.

---

# 2. Git / agent / review workflow

## 2.1 The local worktree is the mutation authority

Normal SRPSS file mutation happens in the operator's real local Git worktree, either by the operator or
a coding agent working in that checkout.

For this project, repository connectors/APIs are **read/audit tools**, not the normal write path.

Do not use a GitHub/repository connector to create/update/delete SRPSS source or documentation files.
Do not invent API blob/tree/branch-ref workflows as a substitute for normal Git editing.

When a reviewer/ChatGPT session materially changes durable guidance but cannot safely edit the real
worktree, return complete replacement files in a handoff pack. The operator/local coding agent applies
them, reviews the local diff, commits, and pushes normally.

## 2.2 Checkpoints are mandatory

Normal low-risk local-agent slice:

```text
inspect exact current source
-> implement narrow slice
-> focused gate
-> inspect diff/status
-> commit intended paths only
-> push
-> continue
```

Do not stop after every successful low-risk checkpoint merely to ask permission.

Audit-required slice:

```text
inspect exact current source
-> implement narrow slice
-> focused gate
-> inspect diff/status
-> commit intended paths only
-> push
-> STOP
-> independent audit of actual pushed source/diff
-> correction if required
-> continue
```

Use an audit-required stop for:

- high-risk visual preservation such as BlockSpin, Burn, Particle, or Bubble;
- lifecycle/topology ownership;
- settings epoch;
- production cutover;
- large deletion batches;
- architecture-boundary changes;
- work performed by an agent the operator has explicitly asked to audit checkpoint-by-checkpoint.

The audit reads the pushed commit/source. Agent prose is not the evidence.

## 2.3 Trust evidence, not agent prose

An agent saying tests passed or code was implemented is not evidence. Inspect current repository
state, pushed commit, diff, relevant source, and independent test/harness evidence from the
environment appropriate to the claim.

Repository state outranks stale orientation prose.

## 2.4 Documentation handoff / replacement-file rule

When durable migration guidance is materially changed outside the real local worktree, return complete
replacement copies of every affected repository document. Include a refreshed stand-alone
reorientation/handoff only when it is needed to preserve migration continuity.

When several replacement files are easier to hand over as one archive, a ZIP may preserve their
repository-relative paths. Do **not** generate a manifest, checksum, inventory, index/helper file, or
other packaging debris unless the operator explicitly asks for it. The replacement filenames and
repository-relative paths should make placement self-evident.

A chat explanation, partial snippet, or claim that a remote document was updated is not a substitute
for the required complete replacement file(s).

---

# 3. Test execution and evidence rules

SRPSS does **not** use repository-hosted CI as the normal migration test workflow. Do not add GitHub
Actions or another hosted test workflow unless the operator explicitly asks for it.

Use the environment appropriate to the claim:

- deterministic Python/source/settings/registry tests: the current capable Windows worktree;
- a clean checkout only when isolation/reproduction specifically benefits from one;
- Quick/OpenGL/runtime-shaped tests: proper Windows/Qt/OpenGL environment;
- multi-display, mixed-refresh, DPR, GPU/resource, physical cadence, and eyes-on claims: the
  corresponding real hardware/display environment.

The broad chunk wrapper remains a deliberate local diagnostic tool only:

```text
python tests/run_chunked.py --chunks 4 --timeout-seconds 900 --log
```

A broad-suite failure must be isolated before attributing it to the active migration slice. A completed
pytest summary followed by a process that never exits is a shutdown/lifecycle ownership defect to
isolate, not a reason to increase the timeout. A chunk that stalls during execution likewise requires
smaller/verbose local isolation.

No unexecuted test or gate is assumed green. Acceptance records must name the exact command, tested
commit, environment, and result.

Do not weaken Windows/Qt/OpenGL/physical-display tests merely because another environment cannot run
them.

---

# 4. Destination runtime architecture

```text
ScreensaverEngine
    |
    +-- providers / image queue / settings / persistence / media
    |
    +-- DisplayManager
            |
            +-- QuickDisplayRuntime (one per selected physical display)
                    |
                    +-- QuickDisplayWindow : QQuickWindow
                    |
                    +-- QuickSceneController
                    |       |
                    |       +-- background/transition QSGRenderNode item
                    |       +-- visualizer QSGRenderNode item
                    |       +-- retained Quick widget items
                    |       +-- dimming / halo / edit overlays
                    |
                    +-- RuntimeInputController
                    +-- WidgetRuntimeManager
                    +-- CustomLayoutSession
```

Feature activation target:

```text
cheap descriptor/catalog metadata
        ↓
application-level capability activated?
  yes                               no
   ↓                                 ↓
resolve implementation/model         implementation/provider/resources stay dormant
        ↓
per-instance/per-feature enabled?
  yes          no
   ↓            ↓
present/run     loaded capability remains available but inactive
```

Application-level **activation/loading** and ordinary runtime **enabled/disabled** state are separate
authorities. Phase E2 makes this distinction explicit in Settings for transitions and widget families.

---

# 5. Phase A — bootstrap/render-node proof

Structurally complete for forward migration.

Settled:

- standalone QQuickWindow path;
- threaded scene graph;
- explicit OpenGL bootstrap;
- inline Python QSGRenderNode OpenGL proof;
- presentation pacer foundation;
- lifecycle/teardown proof.

Deferred A4 compiled smoke remains operator-scheduled after implementation unless explicitly
requested earlier.

Do not reopen Phase A merely to reconfirm the selected architecture.

---

# 6. Phase B — runtime-host decomposition

Structurally complete for forward migration.

Settled properties:

- one `QuickDisplayRuntime` per selected physical display;
- per-runtime window/scene/pacer/input ownership;
- generation-scoped lifecycle including generation 0;
- queued Qt/C++ meta-call teardown for hide/release/close rather than blocking Python
  render-thread inversion;
- hide/wake behavior;
- coordinated one-shot exit;
- deterministic destruction barriers;
- topology replacement harnesses;
- unexpected QWindow screen displacement does not silently adopt a fallback display;
- binding loss preserves original physical identity/pacer target, quiesces presentation/input, and
  emits one-shot topology/binding loss.

Production `DisplayManager -> QuickDisplayRuntime` ownership still waits for Phase H.

---

# 7. Phase C — base image + transitions

**Implementation status: complete. Deterministic test-hardening (Section 7.5, C-T1..C-T8) landed; only operator-scheduled real-GL/eyes-on sign-off remains.**

Read:

- `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`
- `Docs/Transition_Change_Checklist.md`
- `Docs/TestSuite.md`
- `Docs/Harness_Index.md`

## 7.1 Transition-neutral foundation

Completed:

- immutable/detached presentation image boundary;
- `TransitionRequest` / `TransitionRun` lifecycle;
- monotonic progress sampling;
- generation/run fencing;
- exactly-once completion/cancel;
- shared image texture ownership;
- common GL-state fence;
- lazy static implementation registry;
- GUI/runtime-side parameter/random/default resolution;
- permanent canonical-registry ↔ Quick-registry parity gate.

## 7.2 Canonical renderer inventory

All 12 canonical production transitions have Quick renderers:

- Crossfade
- Slide
- Wipe
- Warp Dissolve
- Block Puzzle Flip
- 3D Block Spins
- Blinds
- Diffuse
- Ripple / Raindrops
- Crumble
- Particle
- Burn

No Quick renderer depends on `GLCompositorWidget`.

Canonical transitions remain catalog-visible as appropriate while application-level deactivation keeps
implementation/shader/resource ownership dormant.

## 7.3 Critical preserved contracts

### Slide

Four cardinal product directions only. Source/destination sampling and pixel ownership derive from
one immutable eased sample in one draw, so missed physical frames may cause a larger positional jump
but never a seam/gap.

### 3D Block Spins

Real thin 36-vertex rectangular-prism slab, depth-tested front/back/sides, black void, four authored
axes/directions, correct destination UV orientation, cubic internal spin, dark sides, moving specular
band, white edge rim, context-local resource teardown. No flat fallback.

### Particle

Canonical shader preserved with Directional/Swirl/Converge, directional/random-placement modes,
trails, swirl settings/order, wobble, texture mapping, 3D shading, gloss/light controls, seed, and
physical-framebuffer resolution semantics.

### Burn

Canonical rich shader preserved: ignition, six directions, four-octave/domain-warped noise, jagged
front, heat distortion, glow, white-hot core, char/crackle/smoulder progression, sparks, smoke, ash,
densities/toggles, per-run seed, run-clock animation time, delayed destination tail.

## 7.4 Existing Phase-C acceptance debt

Real-GL sign-off was driven on real hardware 2026-08-21/22 (MSI G321Q + LG TV, OpenGL threaded,
`--size 480x270`), single- and two-display (`--windows 2`, both physical screens):

- ✅ focused deterministic Phase-C tests green in the capable Windows worktree;
- ✅ all 35 parameterized effect×case smokes green single- and two-display;
- ✅ Blinds Horizontal / Vertical / Diagonal green single- and two-display;
- ✅ mature transitions green two-display: Crossfade, Slide, Wipe, Warp, Block Flip and all six Block
  Spins directions;
- ✅ topology recreation green for Crossfade and Wipe;
- ✅ **full two-display closure sweep: 54/54**.

The two 3D-slab oracles (Block Spins and Block Flip) exposed timing fragility on the 60 Hz display.
Those were corrected as **harness-only robustness changes**: production transition renderers were not
changed, the precise geometry/UV fallbacks remain rejecting flat substitutes, and the shared sparse
5×5 geometry grid remained unchanged for unrelated geometry oracles.

Broad single-process real-GL runs can still show contention flakiness after hundreds of window
creations. Chunk those runs rather than attributing unrelated teardown contention to the active slice.

Remaining acceptance requiring the operator's own environment:

- eyes-on old-vs-Quick authored-effect comparison where still useful;
- mixed 60 Hz/high-refresh continuity and physical cadence only where it answers an unresolved
  question.

Phase D may proceed while those acceptance items remain explicit.

## 7.5 Phase-C test/harness strengthening — explicit test-only debt

**STATUS (2026-08-22): deterministic test-hardening C-T1..C-T8 is landed and the real-GL closure sweep is green 54/54 on two physical displays. Both 3D-slab harness timing defects were subsequently deflaked without production renderer changes. The C-T subsections remain durable rationale, not active unfinished work.**

Landed evidence (focused gate, capable Windows worktree, HEAD after the C-T checkpoints):

```text
python -m pytest tests/test_qtquick_transition_controller.py \
  tests/test_qtquick_transition_parameter_defaults.py \
  tests/test_qtquick_transition_implementations.py \
  tests/test_qtquick_transition_uniform_wiring.py \
  tests/test_qtquick_transition_state_fence.py \
  tests/test_qtquick_phase_c_registry_parity.py \
  tests/test_qtquick_phase_c_effect_smoke.py
```

- C-T1: real-GL midpoint oracles now reject a plain wipe (all six axes) and a uniform crossfade
  fallback; discriminators proven with deterministic synthetic fixtures.
  (`tools/qtquick_phase_c_effect_smoke.py`, `tests/test_qtquick_phase_c_effect_smoke.py`)
- C-T2: selected smoke cases proven to resolve to materially different request parameters
  (Ripple counts, Crumble weighting, Particle direction/mode, Burn smoke/ash). Pixel-level pairwise
  contrast remains the operator real-GL rerun.
- C-T3: request-parameter → shader-uniform wiring matrix (`tests/test_qtquick_transition_uniform_wiring.py`).
- C-T4: common GL-state fence + exception restoration (`tests/test_qtquick_transition_state_fence.py`).
- C-T5: Blinds + Ripple sparse canonical-default coverage (`tests/test_qtquick_transition_parameter_defaults.py`).
- C-T6: controller false-pass fixed (`tests/test_qtquick_transition_controller.py`).
- C-T8: `_ALL_QUICK_TRANSITION_IDS` derived from the catalog (`tests/test_qtquick_transition_implementations.py`).
- C-T7/C-T9: honoured (Crumble mosaic tested only as the optional uniform-upload contract; real-GL
  harnesses kept real, fakes used only for wiring/state-contract level evidence).

**If the operator says "continue from Phase C tests", Phase-C implementation/test hardening and the two-display real-GL closure sweep are complete; proceed to Phase D. Only operator-owned eyes-on/high-refresh acceptance remains.**

The Phase-C test audit found real coverage holes. Improve the tests/harnesses first. Do **not**
redesign transition implementation merely to satisfy the audit. If a stronger test exposes a real
implementation defect, record the failure, fix the smallest demonstrated implementation defect in a
separate bounded checkpoint, rerun the strengthened gate, then continue.

### C-T1 — make real-GL midpoint oracles effect-discriminative

The current Diffuse/Ripple/Crumble/Particle/Burn real-GL midpoint checks are too permissive. A generic
spatial reveal can satisfy several because a simple mix of source/destination/effect-colored pixels is
enough.

Strengthen the existing real-GL harnesses so each effect is meaningfully distinguishable from a plain
wipe/crossfade-style fallback.

Do not replace the real-GL harnesses with mocks. Keep the real renderer/window/OpenGL path and add
better discriminators.

Useful principles:

- use fixed synthetic source/destination patterns and deterministic seeds;
- compare effect-specific spatial signatures, not merely "both images appear";
- use paired/contrast cases from the same effect at the same progress where a parameter should change
  the result;
- prefer robust regional/statistical/geometry assertions over exact screenshot hashes.

### C-T2 — prove selected smoke parameters materially change behavior

Several smoke cases currently exercise settings without proving they alter rendering.

Add pairwise/contrast evidence for at least:

- Ripple `count1` vs `count3` vs `count8`;
- Crumble weighting modes;
- Particle directions and modes;
- Burn smoke/ash toggle cases.

The selected case must measurably change the intended output under fixed seed/input/progress.

Examples of suitable discriminators:

- Ripple: changed ring/front frequency or radial crossing structure;
- Crumble: changed deterministic piece/old-vs-new distribution for weighting modes;
- Particle: changed displacement centroid/orientation/radial-vs-angular behavior for
  direction/mode choices;
- Burn: smoke/ash toggles change their intended regions under the same seed/time without being the
  only evidence for the core burn front.

### C-T3 — direct request-parameter → shader-uniform wiring tests

Add direct renderer-boundary tests proving resolved immutable request parameters reach the intended
shader uniforms for:

- Diffuse;
- Ripple;
- Crumble;
- Particle;
- Burn.

A recording/fake GL uniform sink is appropriate for this **wiring** test, because the existing real-GL
harness remains separately required for actual rendering.

Particle must cover every authored control:

- mode;
- direction;
- radius;
- overlap;
- trails;
- swirl strength;
- swirl turns;
- swirl order;
- 3D shading;
- texture mapping;
- wobble;
- gloss;
- light direction;
- seed;
- physical framebuffer resolution.

Burn must cover all authored effect uniforms plus `u_time` derived from the immutable run clock.

Do not let renderer defaults hide missing request fields.

### C-T4 — direct common GL-state fence regression

Add a focused regression test that starts from deliberately non-default GL state, allows a transition
renderer to mutate it, and proves the host restores the previous values.

Cover at least:

- viewport;
- scissor state where the current fence promises it;
- current program;
- VAO;
- array buffer;
- active texture;
- texture units 0 and 1 bindings;
- blend;
- cull;
- depth enable;
- depth write mask;
- depth function;
- depth clear value;
- stencil.

Repeat the restoration assertion when `renderer.render()` raises. Exception cleanup is part of the
state-fence contract.

### C-T5 — complete sparse canonical-default coverage

Existing sparse/default tests already cover Diffuse/Crumble/Particle/Burn.

Add Blinds and Ripple so absent Settings values resolve from canonical defaults rather than renderer
magic numbers.

### C-T6 — remove the false-pass controller test shape

Fix:

```text
tests/test_qtquick_transition_controller.py
test_runs_require_explicit_interruption_and_are_generation_fenced
```

`cancel_current(...)` and the generation-mismatched `start(...)` must not sit in the same
`pytest.raises` block.

Only:

```text
start(_request(generation=8))
```

is the operation expected to raise.

The cancellation call must execute and be asserted independently so a premature exception cannot make
the generation-fence check falsely pass.

### C-T7 — Crumble `mosaic_mode` testing must match the authored shader

Do not invent a fake visual mosaic test.

The canonical fragment shader declares `u_mosaic_mode` but currently does not consume it.

Test only the renderer's optional uniform-upload contract when that uniform exists. Do not claim
current authored visual mosaic behavior unless the shader is deliberately changed in a separate
product decision.

### C-T8 — remove duplicate hard-coded transition inventory

`_ALL_QUICK_TRANSITION_IDS` duplicates canonical transition inventory in one test.

Registry parity is already the independent inventory gate. Remove/derive the duplicate where practical
so future canonical additions/removals do not require updating two supposedly authoritative lists.

### C-T9 — preserve environment fidelity

Do not weaken Windows/Qt/OpenGL/physical-display tests because another environment cannot run them.

Keep real-GL harnesses real. Use mocks/fakes only for isolated wiring/state-contract tests where they
are the correct level of evidence.

### C-T10 — suggested checkpoint order

Prefer bounded test-hardening checkpoints:

```text
controller false-pass + sparse defaults + duplicate inventory cleanup
-> request-to-uniform wiring matrix
-> GL-state fence + exception restoration
-> real-GL discriminator/parameter-sensitivity strengthening
-> rerun focused Phase-C gates and record exact evidence
```

If any strengthened test exposes a real renderer defect:

```text
record failing evidence
-> smallest implementation fix in separate commit
-> focused test + real-GL rerun
-> push
-> audit if high-risk
```

Do not broaden the repair into transition redesign.

---

# 8. Phase D — visualizer — COMPLETE

D1–D9 landed and Phase-D documentation closure is done (see Section 15). All five modes run on the Quick
visualizer boundary; only operator-scheduled physical cadence/eyes-on acceptance debt remains. The
decomposition below is retained as the durable contract; do not reopen it without contradictory
evidence.

Read:

- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- `Docs/Visualizer_Reference.md`

Phase D must preserve the current five visualizers **and** avoid baking the historical painted-card
assumption into the new architecture.

The final visualizer presentation is explicitly split into:

```text
mode/render state
        +
presentation shell policy
        +
content clip policy
        +
presentation geometry / viewport
```

All current five modes use the carded policy. No current visual result is intentionally changed by
this architectural split.

## D1 — presentation-neutral runtime/controller + mode presentation policy

Separate the non-pixel visualizer owner from QWidget presentation without rewriting provider/business
logic.

Retain settings/mode/preset activation, playback state, BeatEngine/source,
`VisualizerLogicalRuntime`, and latest logical publication.

Do not instantiate a hidden QWidget merely to keep those owners alive.

Extend the cheap canonical visualizer mode descriptor with presentation metadata rather than adding
mode-specific `if/elif` branches to scene owners.

Conceptually:

```text
VisualizerModePresentationPolicy
    shell_policy = CARD | FRAMELESS
    clip_policy  = CARD_INTERIOR | VIEWPORT_RECT
    viewport_resize_capable = bool
```

Current five modes:

```text
shell_policy = CARD
clip_policy  = CARD_INTERIOR
```

A future explicitly authored mode such as the post-migration deformable 3D sphere may use:

```text
shell_policy = FRAMELESS
clip_policy  = VIEWPORT_RECT
```

`FRAMELESS` means no card fill, frame/border, or card shadow. It does **not** mean a second native
window or permission to draw arbitrarily across the display.

Checkpoint/push/audit this split.

## D2 — immutable latest-state render bridge

Publish bounded immutable current visualizer snapshots containing generation/activation identity,
mode/playback identity, logical timestamp, fade/style, mode-specific render data, and the resolved
presentation policy/geometry required for that committed frame.

No render-thread reads from live QWidget/QObject/provider/Settings state or live mode-registry state.

Latest state wins; no FIFO/catch-up replay. Protect short-lived authored edges explicitly.

Checkpoint/push/audit the bridge separately.

## D3 — Quick visualizer scene composition, clip owner, and card/frameless shell

Use one sub-rect custom Quick item/QSGRenderNode inside the display QQuickWindow.

Selected carded scene shape:

```text
VisualizerPresentationRoot  (one fade/visibility owner)
    |
    +-- retained card shadow        [CARD only]
    +-- retained card background    [CARD only]
    +-- visualizer content item
    |       |
    |       +-- QSGRenderNode / direct OpenGL
    |               |
    |               +-- one local SDF/stencil clip host
    +-- retained card frame/border  [CARD only, above content]
```

For `FRAMELESS`, omit the card shadow/background/frame while retaining the same presentation root,
content item, lifecycle, fade authority and display-scene ownership.

### D3.1 — clipping policy

The old architecture needed a rounded-card stencil because custom GL content had to remain above the
card fill and below the visible border without bleeding through rounded corners.

That **visual contract remains necessary for carded modes**. The old hand-written stencil mechanism
does not automatically remain the best owner.

The exact pinned PySide 6.9.1 proof is complete. The scene-graph clip-node handoff did not provide
usable accumulated clip state to the Python render node: rounded cases exposed stencil state whose
framebuffer contents did not match, while rectangular cases could expose an invalid sentinel scissor.
Do not reopen or retain that failed path.

The selected single Quick implementation is one render-node-local SDF/stencil clip host inside the
same `QQuickWindow`/`QSGRenderNode` architecture:

- `CARD_INTERIOR` uses rounded geometry matching the actual inner edge of retained Quick card chrome;
- `VIEWPORT_RECT` uses the same host with zero corner radius;
- shell, clip and custom GL derive from one immutable canonical geometry record and render-target
  viewport;
- the host nests above any incoming `RenderState` scissor/stencil value without clearing Qt's clip
  contents;
- the temporary stencil contents and every touched direct-GL state are restored before returning to
  Qt;
- there is no second selectable scene-graph clip implementation.

Never solve clipping by shrinking the visualizer render rect or scaling the authored content smaller.
Historical R-21 proved that changes mode geometry/amplitude/bar sizing rather than clipping pixels.

### D3.2 — Quick border semantics

Do not cargo-cult the old mask formula.

The historical mask compensated for a centred QPainter border (`border_width / 2`) plus painted-card
shadow tuning. Qt Quick `Rectangle` borders are rendered **inside** the rectangle bounds.

The new card-interior clip must therefore be derived from the actual retained Quick chrome contract:

```text
outer card shape
        ↓
inside border width
        ↓
inner content path / inner corner radius
```

Any additional inset must be an explicit authored Quick card/style value, not a copied magic
`1px + border/2` rule from the QWidget/QPainter era.

## D4 — canonical geometry: one baseline aspect, uniform scale, separate viewport extent

Create one committed presentation-neutral geometry record capable of expressing:

```text
outer_rect
content_rect
dpr
baseline_viewport_size
baseline_aspect_ratio
uniform_visual_scale
viewport_extent
current_aspect_ratio
shell_policy
clip_policy
```

### D4.1 — retire the legacy per-mode card-height/growth system from Quick

The old runtime carries per-mode presentation controls such as:

```text
spectrum_growth
osc_growth
sine_wave_growth
bubble_growth
devcurve_growth
```

They change preferred **outer card height** while width remains media-relative. CUSTOM already bypasses
that preferred-height path once committed custom geometry owns the visualizer.

These are legacy presentation customization and are **not part of the Qt Quick visualizer contract**.
Do not port them into the Quick controller, immutable render snapshot, mode descriptor or retained
card geometry.

For the Quick-era normal/default layout:

- all current visualizer modes share one canonical baseline viewport aspect ratio;
- normal card width/placement may still follow the intended common layout owner, but height derives
  from that one baseline aspect rather than a mode-specific growth multiplier;
- switching Spectrum ↔ Oscilloscope ↔ Sine ↔ Bubble ↔ DevCurve does not resize the viewport merely
  because the mode changed;
- built-in presets may tune the mode's visual behavior but do not own viewport/card height;
- screen-bound clamping preserves the baseline aspect by uniform scale/downsize rather than chopping
  one axis independently.

Do **not** invent a new numerical aspect ratio from an arbitrary old mode-growth value. D3/D4 should
extract/freeze one explicit canonical ratio from the intended healthy CUSTOM/default visualizer
baseline and give it one named authority. Once chosen, every current mode uses that authority.

The destination should therefore behave like the clean part of current CUSTOM: legacy growth values
are irrelevant to visualizer shape.

The old settings/UI/preset keys may remain temporarily while the old presenter still exists, but the
Quick implementation ignores them. H0 resets them away and Phase I/J0 remove their remaining current
schema/UI/preset/default/tooling authority after caller proof.

### D4.2 — uniform scale preserves the baseline aspect

`uniform_visual_scale` is the ordinary whole-visualizer size control.

It scales shell + viewport + authored content coherently and **preserves the canonical baseline aspect
ratio**.

This is the semantic used by:

- existing/custom scroll-wheel resize;
- corner-handle resize;
- ordinary reset-to-size behavior.

It is not an X/Y stretch.

### D4.3 — viewport extent is a separate future operation

`viewport_extent` changes how much visualizer world/layout is available at the current visual scale.
It may intentionally produce a wide/tall aspect that differs from the baseline aspect.

That deviation is allowed **only** through the explicit viewport-extent operation planned for Phase G,
not through mode presets, legacy growth controls or ordinary corner/scroll resize.

Do not bake these assumptions into the five renderer ports:

- mode-specific preferred heights;
- one fixed historical card size hidden inside a renderer;
- non-uniform final-pixel stretching;
- card existence as a precondition for drawing.

Where logical simulation needs spatial bounds (Bubble in particular), viewport changes enter through a
presentation-neutral viewport-metrics update owned outside the render thread. That update is
configuration, not another clock.

## D5 — prove baseline aspect independence and future viewport compatibility

During the five mode ports, exercise at least:

```text
canonical baseline aspect at scale 1.0
canonical baseline aspect at another uniform scale
wide viewport extent at the same visual scale
tall viewport extent at the same visual scale
```

The first two are migration requirements. Wide/tall cases are architectural compatibility probes for
the later Phase-G QoL; Phase D does not ship the edit handles.

Expected semantics:

- Spectrum: redistribute bars/layout across available width; vertical limit follows content height;
- Bubble: spatial bounds/aspect change without anisotropically stretching circles, radii, velocities
  or trajectories;
- Oscilloscope/Sine/DevCurve: recompute available domain/placement while preserving stroke thickness
  and authored scale;
- future 3D sphere: aspect-correct camera/projection so the sphere remains round.

If one current mode cannot safely support free viewport extent without compromising authored behavior,
keep the D4 geometry seam and mark that mode `viewport_resize_capable = false` for the later QoL. Do
not block migration and do not fake support by stretching pixels.

## D6 — sole authored logical clock

`VisualizerLogicalRuntime` remains the sole mode-general authored logical clock.

Non-negotiable:

- every authored logical step survives;
- latest-state semantics;
- no FIFO/catch-up;
- no paint acknowledgement;
- no producer/display divisor;
- no source/event decimation;
- no display-refresh logical cap;
- render cadence never becomes simulation cadence;
- nonblocking media/GSMTC interaction;
- generation/stale fencing;
- clean worker join.

## D7 — five mode ports

Preserve all current authored **mode behavior** for the five modes below. The D4-retired per-mode card-height/growth presentation controls are explicitly excluded from parity:

1. Spectrum — bars/peaks/ghosting, paused idle visibility, source freshness;
2. Oscilloscope — waveform/line persistence/idle behavior;
3. Sine — authored idle/layers/reactivity, no separate timer;
4. Bubble — dedicated high-risk checkpoint with BTF, continuous positional evolution, collisions,
   trails/tails, ghosts/pop/transients/protected edges, authored logical Hz;
5. DevCurve — active layers/order/alpha/offsets/outline/ghosting/tuning.

All five current modes remain `CARD + CARD_INTERIOR`.

Do not retune modes to hide presentation problems.

The observation that unrelated widgets can materially change measured Bubble-era GPU load supports
retained-scene efficiency and true feature dormancy. It does not implicate Bubble collision logic by
itself.

## D8 — Pause/Play and lifecycle

Preserve warm-source/expected-state behavior without recreating the window/item or inventing a second
playback authority.

One presentation-root fade authority covers both carded and frameless modes.

Retirement must close publication, stop/join the logical runtime, invalidate activation/generation,
remove snapshot admission, release GL resources on the render owner, and destroy roots cleanly.

A background owner that prevents process/test shutdown is a defect.

## D9 — checkpoint cadence

Prefer pushed/audited checkpoints for:

1. runtime/controller split + presentation policy;
2. immutable bridge;
3. item/node + clip/shell/geometry foundation;
4. Spectrum;
5. Oscilloscope;
6. Sine;
7. Bubble + BTF;
8. DevCurve;
9. all-five-mode lifecycle/source/pause + aspect-policy closure;
10. Phase-D documentation closure.

## D exit

All five modes use the Quick visualizer boundary with the authored logical runtime intact, immutable
latest-state publication, clean lifecycle/resources, and no old compositor/QWidget presentation
dependency inside the new renderer.

The renderer architecture must no longer assume every possible visualizer mode requires a card, and
its geometry contract must preserve a clean later seam for viewport-extent resizing.

Phase D does **not** need to ship the Phase-G freeform viewport-resize UI to exit.

After implementation exit, rewrite visualizer/preset authoring guidance against the landed Quick
contract. Explicit physical/eyes-on items may remain scheduled acceptance debt when they require the
operator's actual display/GPU environment.

---

# 9. Phase E — widget presentation + capability setup foundation

Read:

- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`

## E1 — presentation-neutral descriptor/runtime ownership

Make canonical widget identity/settings metadata independent of QWidget factories.

Create/rename `WidgetRuntimeManager` around provider/model lifecycle, activated/enabled/visible state,
monitor participation, stacking inputs, settings updates, fade intent, generation/model registration,
and actions.

A disabled **instance** remains a configured capability but does not present.

A deactivated **family/module** must not own feature-specific provider/model/process/poll/timer/Quick
component/resource solely because its files exist.

Shared infrastructure remains only while another activated capability needs it.

Do not create a giant Python `QuickBaseOverlayWidget` god object.

## E2 — application-level capability SETUP UI and lazy Settings navigation

This is a required migration-era QoL/wiring feature, not `Future_Work.md`.

The Settings GUI remains QWidget-based. Reuse the existing pill/subtab navigation style and lazy
section construction.

### E2.1 Two separate state levels

Do not conflate:

```text
capability activated / loaded
```

with:

```text
widget instance enabled
transition selected / random-pool enabled
```

Activation is the application-level gate. It determines whether implementation/runtime/UI sections are
resolved at all.

Ordinary enablement/selection remains configuration **inside** an activated capability.

Disabling/deactivating a capability does not erase its saved configuration. Re-activation restores the
previous per-feature settings unless the operator explicitly resets them or H0 replaces the old
settings epoch.

Python modules already imported in the current process may remain in `sys.modules`; the runtime
contract is immediate resource/lifecycle dormancy plus no import on a fresh process while deactivated.

### E2.2 Widgets tab

Add an always-present first pill/subtab:

```text
SETUP
```

The Setup page is built only from cheap presentation-neutral catalog metadata. It must not import
family builders/providers/renderers merely to list available families.

Show all canonical widget **families/capabilities** using the existing circle-checkbox visual style.

Examples of family-level activation should follow final canonical family ownership rather than blindly
mirroring instance ids:

- Clocks may own Clock / Clock2 / Clock3;
- Reddit may own Reddit / Reddit2;
- Steam may own its related family cards/services;
- other families follow their canonical `family_id`.

Do not automatically treat the visualizer as a widget-family capability merely because some of its
settings currently live in WidgetsTab; Phase D/final descriptor ownership decides that boundary.

Bottom-right controls:

```text
Enable All
Disable All
```

These buttons change **family activation**, not each family's internal `enabled` checkbox.

For each deactivated family:

- remove its settings pill/button from the navigation rows;
- do not build/hydrate its Settings page;
- do not resolve its runtime implementation/model/provider;
- stop/retire any currently owned family runtime work at the normal safe settings-apply/recreate
  boundary;
- release family-specific Quick/GL resources;
- keep stored per-family/per-instance settings intact.

For each activated family:

- show its pill/button;
- build its page only when selected;
- resolve runtime ownership only if the family/instance state actually requires it.

The existing lazy-save hydration guard must survive this change. An unbuilt/deactivated settings page
must never overwrite stored values with defaults simply because the Settings dialog was saved.

### E2.3 Transitions tab

Replace the old transition dropdown + monolithic eagerly-created transition groups with the same
pill/subtab navigation pattern.

Always-present first pill:

```text
SETUP
```

Each **activated** transition receives one settings pill. Deactivated transitions have no pill and
their implementation remains out of runtime selection/resolution.

The Setup page owns:

- application-level transition activation checkboxes;
- `Use Random Transitions` as one ordinary checkbox;
- one random-pool list containing only activated transitions, with per-transition pool membership.

The old per-transition "Include in Switch/Random Pool" control and old separate random-pool button/UI
become obsolete.

Keep these states distinct:

```text
transition activated
        ↓
eligible to have a settings page / be selected at all

random-pool member
        ↓
eligible only when random mode is active

Use Random Transitions
        ↓
runtime uses effective random pool

manual transition selection
        ↓
used when random mode is off
```

Effective random pool is:

```text
activated transition ids
∩
saved random-pool membership
```

Random mode must not silently run with an empty effective pool. Prevent/resolve that state explicitly.

The landed canonical normalization authority, `normalize_transition_capability_state(...)`, already
owns the malformed persisted-state repairs:

- zero activated transitions -> explicitly reactivate canonical recovery transition `Crossfade` in the
  settings state and persist that repair;
- Random enabled with an empty `activated ∩ saved-pool` set -> turn Random off and persist a
  deterministic activated manual selection while preserving saved pool membership.

Those are explicit settings-state normalization/recovery rules, not permission for a renderer/factory
to run a deactivated implementation as a hidden fallback.

E2 also removes the historical dual Random-mode authority. Once E2 cuts over,
`transitions.random_always` / `Use Random Transitions` is the one live Random-mode authority and
`transitions.type` stores a concrete manual transition selection. A legacy persisted `type="Random"`
must be normalized into that shape without losing pool preferences or the remembered concrete manual
selection; runtime and normalization may not disagree about whether Random is active.

When `Use Random Transitions` is off, the selected transition pill is the manual transition, preserving
the old dropdown's practical selection behavior.

When random mode is on, selecting another transition pill changes **editing focus** and may remember
the manual selection for later, but does not implicitly disable random mode.

Deactivating the currently selected manual transition must choose/persist a deterministic activated
replacement selection; it must not silently reactivate or run the transition the operator deactivated.

Deactivation may preserve that transition's saved random-pool preference so reactivation can restore
the user's prior configuration, while the effective pool always filters by activation.

### E2.4 Settings implementation shape

Do not make Settings import renderer implementations.

Use lightweight Settings metadata, conceptually:

```text
CapabilityDescriptor
    id
    label
    activation setting
    settings builder module/factory
    family/group identity
    persisted settings ownership
```

For transitions, move transition-specific settings construction out of one giant eagerly-created
`TransitionsTab` body into lazy per-transition builders/pages or an equivalently modular descriptor
boundary.

For widgets, extend the existing descriptor/lazy-section system rather than replacing it.

`SETUP` itself is never capability-gated and must be cheap to construct.

### E2.5 E2 tests

Prove:

- Setup pages list capabilities without importing heavy runtime/render modules;
- deactivated capabilities have no settings pill/page construction;
- activated capability page builds on first selection;
- deactivating a built page does not corrupt its persisted settings;
- reactivation restores previous settings;
- Widget `Enable All` / `Disable All` affect activation only;
- per-widget internal `enabled` values survive family deactivation/reactivation;
- owners already migrated behind the activation boundary retire deactivated-family exclusive work;
- broader provider/model/timer/process dormancy and last-consumer shared-service lifetime remain E1
  ownership gates before Phase F, not something the E2 UI may fake by merely hiding a page;
- transition activation removes implementation from effective selection and keeps renderer dormant;
- random pool uses `activated ∩ pool-member`;
- random mode cannot remain valid with an empty effective pool;
- manual transition selection remains deterministic when its capability is deactivated;
- direct normalization tests prove all-false activation explicitly repairs/persists Crossfade and empty
  effective Random pool disables Random while preserving pool preferences;
- legacy `type="Random"` is normalized to the one E2 Random authority plus a concrete manual type;
- a pre-resolved/stale `transitions.random_choice` is revalidated at final factory admission and cannot
  run after that transition is deactivated or becomes hardware-inadmissible;
- engine Random selection, factory Random selection and C-key cycling never execute a literal/deactivated
  `Crossfade` substitute when no valid candidate remains;
- no lazy-save hydration regression;
- Settings recreation correctly rebuilds only activated navigation/pages.

### E2.6 Open transition-admission debt — blocks E2 exit

Exact pushed source at the 2026-08-22 Phase-E partial checkpoint still has four narrow activation/Random
seams that must be closed before E2 is marked complete or Phase F is allowed to rely on E2:

1. `TransitionFactory._get_random_mode()` accepts an already-populated
   `transitions.random_choice` after canonicalization without re-checking current activation and
   hardware admission at the final factory seam. A choice prepared before a live Settings change must
   not survive deactivation as an executable transition.
2. The engine's hardware-filtered Random candidate path and the factory-side Random candidate path
   still contain literal `Crossfade` last-resort branches. Those branches may not execute Crossfade
   when Crossfade is deactivated; if no transition is both activated and hardware-admissible, fail
   closed or resolve through one explicit canonical admission policy rather than silently substituting
   a deactivated implementation.
3. C-key cycling still has unconditional Crossfade recovery branches when no candidate survives pool /
   hardware / activation filtering. The final cycle result must itself pass activation and hardware
   admission; an empty valid set must not manufacture a deactivated Crossfade.
4. Runtime Random detection still treats legacy `transitions.type == "Random"` as Random mode while
   `normalize_transition_capability_state()` / `is_random_mode_effective()` reason only about
   `random_always`. E2 must converge this to one authority: `Use Random Transitions` /
   `random_always`, with `type` holding a concrete remembered manual selection. Normalize legacy
   `type="Random"` state explicitly before the old dropdown authority is removed.

The normalization helper itself also needs direct regression coverage for its all-false repair and
empty-effective-pool repair; current focused tests exercise the surrounding pool semantics but do not
directly pin those mutations.

Fix only these demonstrated seams. Do not add another selector, compatibility presenter, or fallback
architecture. Add focused regressions for each item, then checkpoint/push/audit E2 before Phase F
family migration relies on it.

## E3 — shared retained Quick primitives

Build small reusable primitives for cards/backgrounds, border/radius, foreground opacity, shadows,
text/header shadow, image/artwork, separators, text, fades/visibility, click targets, controls.

## E4 — eight-direction shadow authority

Add one global presentation-neutral direction setting:

```text
NW   N   NE
 W   ·    E
SW   S   SE
```

Eight outer directions; default `SE`; center is not a ninth mode.

Direction changes signs while preserving each family's authored magnitude/blur/spread/opacity/color.
Cover cards, text, headers, icons/artwork, controls, volume slider, visualizer, clocks, Weather, Media,
Reddit/Gmail, Steam families, multiple DPRs, and CUSTOM geometry.

Do not reintroduce QWidget `QGraphicsDropShadowEffect`.

---

# 10. Phase F — widget families

Port runtime pixels, not Settings GUI/backends.

## F0 — remove deprecated Imgur instead of porting it

Remove its live gate/defaults/settings controls/descriptor/runtime/provider/CUSTOM/tests/package/
current-authority docs/Foundry metadata. Do not build compatibility around stale Imgur presentation
keys.

Recommended family order:

1. Clock / Clock2 / Clock3
2. Weather
3. Media core
4. media volume/mute/progress/control sub-elements
5. Reddit / Reddit2
6. Gmail
7. Steam Progress
8. Achievement Pulse
9. Abandonment Issues
10. Friend Pulse
11. other deliberately supported canonical families

Per family:

```text
identify provider/business logic
-> compact runtime model
-> retained Quick presentation
-> preserve customization
-> deterministic tests/gallery
-> CUSTOM expectations
-> commit/push
-> audit when risk warrants
```

The E2 application-level activation gate must already prevent deactivated families from resolving
during these ports.

Do not rewrite provider/network logic into QML or use QWidget screenshots as final presentation.

After F implementation exits, rewrite widget authoring guidance for the final
descriptor/model/family/Quick component contract.

---

# 11. Phase G — CUSTOM, input, interaction, auxiliary pixels

Read `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`.

## G1 — CUSTOM session + visualizer viewport-resize QoL

Refactor `CustomLayoutManager` into presentation-neutral session/state + Quick edit presentation.

Edit the real retained Quick item. Keep uncommitted session geometry separate from persisted settings.
Save commits; Cancel restores baseline. Grid/outline/handles are separate Quick edit items.

Cross-monitor transfer moves/recreates one presentation instance on the target scene; no simultaneous
duplicate live pixel owners.

Do not spend migration effort translating old QWidget geometry; H0 resets it.

### G1.1 — visualizer resize has two distinct operations

The Phase-D geometry contract separates **uniform whole-visualizer scale** from **viewport extent**.

Preferred edit semantics:

```text
scroll-wheel resize
    -> uniform whole-visualizer scale
    -> canonical baseline aspect preserved

corner-handle resize
    -> uniform whole-visualizer scale
    -> canonical baseline aspect preserved

left/right edge-handle resize
    -> viewport width only
    -> visual scale unchanged

top/bottom edge-handle resize
    -> viewport height only
    -> visual scale unchanged
```

This deliberately preserves the existing useful CUSTOM interaction: scroll/corner resize makes the
entire visualizer larger or smaller as one object. Edge-only dragging is the new operation that gives
a mode more or less playroom.

Viewport resizing is not post-render image stretching.

The renderer/logical mode consumes the new viewport dimensions so content adapts/reflows:

- Spectrum redistributes bars across available width and uses the new vertical extent;
- Bubble changes spatial bounds/aspect without turning circles into ellipses or scaling X/Y velocities
  differently;
- Oscilloscope/Sine/DevCurve adapt domain/layout while preserving authored stroke/visual scale;
- future frameless 3D modes use aspect-correct camera/projection.

When a card shell exists, its outer geometry follows the viewport extent plus canonical shell/border
insets. A frameless mode changes only its transparent assigned viewport.

`Reset Size` should restore both uniform scale and viewport extent to the canonical baseline geometry
unless a later deliberate UX adds separate reset affordances.

Persist scale and viewport extent as distinct new-schema values. Do not resurrect the old per-mode
`*_growth` controls as hidden aliases for either field.

### G1.2 — non-blocking migration rule

This QoL is preferred because Phase D is already paying the architectural cost to keep the geometry
seam clean.

It is **not a production-cutover blocker** if focused implementation evidence shows that one or more
current modes cannot support freeform viewport extents without substantial BTF/fidelity risk.

If that happens:

- keep the Phase-D scale/viewport separation;
- disable viewport-edge handles for the affected mode(s);
- preserve ordinary uniform scale resize;
- record the deferred mode-specific work explicitly;
- do not fake support by stretching the rendered visualizer texture.


## G2 — input/interaction

Refactor `InputHandler` away from DisplayWidget assumptions and route QQuickWindow events to existing
actions.

Preserve exit gestures, hotkeys/media keys, Ctrl interaction mode, layout slots under the new schema,
clicks, right-click context menu, Media Center behavior.

Transient QWidget control UI/settings dialog may remain if decoupled from DisplayWidget and not used
as accelerated presentation.

## G3 — auxiliary runtime pixels

Port cursor halo, dimming, pixel-shift scene transform, required error/fail-safe display, edit
grid/handles, and any remaining runtime overlay pixel owner.

---

# 12. Phase H — settings epoch + production cutover

No production-owner cutover until Quick implementation contains base images, all active transitions,
all five visualizer modes, runtime widget families, CUSTOM, input/context, dimming/pixel shift/halo,
multi-display/lifecycle, and packaging inputs ready for later compiled validation.

## H0 — one-time Qt Quick settings epoch

Do not accumulate a museum of per-feature pre-Quick presentation migrations.

### Preserve only an explicit durable whitelist

Intended durable categories:

- image/source configuration and configured locations/selections;
- credentials/tokens/secrets;
- account identities/slots/auth data;
- genuinely presentation-neutral provider/backend connection information;
- any other leaf only after inspection proves its meaning/schema survives unchanged.

Do not preserve an entire old subtree merely because it contains one durable leaf.

### Reset migration-sensitive presentation state to final Quick defaults

Reset, where present:

- transition selection/pools/durations/directions/parameters/easing debris;
- **transition capability activation and new random-mode/pool defaults to their final canonical
  Quick-era defaults**;
- widget enablement/presentation/style/position/dimensions;
- **widget-family capability activation to final canonical Quick-era defaults**;
- presentation monitor routing;
- CUSTOM geometry/restore payloads/layout slots;
- display geometry assumptions;
- old shadow/effect settings;
- visualizer presentation/geometry, including old per-mode `*_growth`/card-height controls and any Quick-era shell/clip/scale/viewport state where persisted;
- old user visualizer presentation presets unless deliberately retained under a new-schema decision;
- other QWidget/QRhi/compositor-era presentation state.

No heroic coordinate translation.

Built-in visualizer presets remain product baseline; users can edit/create/save new presets in the new
schema.

### Epoch operation

```text
pre-Quick settings detected
-> copy explicit durable whitelist
-> construct fresh final Quick defaults
-> restore whitelist
-> atomically persist new epoch/version through normal durability boundary
-> future current-epoch starts do nothing
```

Prove reset exactly once, durable source/auth data survives, presentation state resets, malformed old
presentation state cannot leak through, second startup does not reset again, and persistence reaches
normal durability boundary.

Checkpoint/push H0 before H1.

## H1 — production-owner switch

Make one explicit switch:

```text
DisplayManager
    from DisplayWidget
    to QuickDisplayRuntime
```

Change callers to the real new API. No DisplayWidget compatibility facade and no production flag back
to QRhiWidget.

Run focused/chunked gates as meaningful. Do not initiate installed/full build unless operator
scheduled.

Checkpoint/push cutover immediately when accepted.

---

# 13. Phase I — immediate legacy removal

Use `Future_Cleanup.md` as deletion ledger.

After cutover, remove in small proven batches:

- QRhiWidget physical presenter;
- `GLCompositorWidget` scheduling/presentation ownership;
- old GL RHI surface helpers without callers;
- compositor visualizer layer;
- old GUI `present_tick` paths;
- old QWidget runtime widget presentation classes after settings/test consumers move;
- old QWidget CUSTOM edit shell/grid presentation;
- dead transition controller classes whose only purpose was old compositor presentation;
- obsolete effect/cache-busting presentation code;
- legacy presenter/factory consumers;
- one-off pre-Quick presentation migration helpers obsolete after H0;
- obsolete transition dropdown/random-pool UI code replaced by E2;
- obsolete eager Widgets/Transitions settings-section creation paths replaced by E2;
- legacy visualizer per-mode card-height/growth settings/UI/bindings/helpers/tests once the old presenter no longer calls them (`spectrum_growth`, `osc_growth`, `sine_wave_growth`, `bubble_growth`, `devcurve_growth`, and compatibility height helpers);
- legacy GL capability-demotion / compositor-only / software-only rendering support and tests whose only
  purpose is preserving that fallback ladder, after caller proof. Software-only rendering is not a
  supported Quick-era product mode;
- migration-only scaffolding.

Do not delete presentation-neutral authored shaders/math merely because the old compositor also used
them; shared assets survive when Quick is their real consumer.

For every deletion batch:

```text
caller proof
-> focused tests
-> commit
-> push
-> audit when risk warrants
-> continue
```

Do not leave both presenter architectures "for safety."

---

# 14. Phase J — Defaults Foundry, final validation, documentation closure

Read `Docs/QtQuick_Migration/06_Build_Tooling_Validation.md`.

## J0 — retarget Defaults Foundry

Current tool:

```text
tools/default_settings_editor.py
```

It currently reads canonical `DEFAULT_SETTINGS` directly via AST/literal, recursively edits leaves,
writes Normal base + MC differential, and regenerates snapshot/SST artifacts.

After H0/H1/I establish final schema:

- keep direct literal-reading if `core/settings/default_settings.py` remains canonical;
- otherwise retarget explicitly;
- remove deleted metadata such as Imgur;
- add finite-value metadata for new canonical settings such as shadow direction;
- remove legacy visualizer per-mode card-height/growth leaves from canonical defaults/preset authoring/Foundry metadata; visualizer presets must not change viewport shape through those retired keys;
- expose/validate final transition capability-activation, random-mode/pool and widget-family
  activation defaults without importing heavy implementation modules;
- remove retired compatibility-preservation behavior;
- align import/filter rules with H0 durable-data policy;
- regenerate default snapshots and Normal/MC SSTs;
- update parity tests and `Docs/Defaults_Guide.md`;
- keep the standalone Foundry QWidget UI unless a separate tooling decision changes it.

## J1 — operator-scheduled final validation

When explicitly scheduled, validate:

- script RUN;
- normal compiled `.scr`;
- diagnostic build;
- Media Center build where relevant;
- Settings open/recreate;
- Widgets/Transitions SETUP activation persistence and dormancy;
- CUSTOM Save/Cancel;
- all five visualizer modes;
- all transitions;
- all widgets;
- mixed 60 Hz/high-refresh;
- monitor off/wake/topology recreation;
- clean shutdown;
- resource baseline;
- PresentMon cadence where useful;
- external heavy-load resilience;
- long soak.

Do not rerun obsolete manual worker-heavy baselines merely out of habit.

Beyond-parity closure should show no QWidget effect-cache shadow architecture, no per-widget accelerated
surfaces, retained Quick widgets not rebuilding stable content every physical frame, clean
render-thread ownership, true deactivated-capability dormancy, and decomposition of overloaded old
presentation modules.

## J2 — documentation closure

Update current-authority docs to landed class/file names; make Quick transition/widget/visualizer
authoring guides sole current implementation authority; update Defaults guide; remove current
instructions that teach dead QWidget/QRhi/compositor owners.

Preserve historical bug/evidence documents as history rather than rewriting them as current
architecture.

---

# 15. Current next work

**Phase D is COMPLETE.** All five modes (Spectrum/Oscilloscope/Sine/Bubble/DevCurve) run on the Quick
visualizer boundary with the sole `VisualizerLogicalRuntime`, mode-owned frame runtimes, immutable
latest-state publication through `VisualizerSnapshotBridge`, one `QSGRenderNode`/lazy renderer,
render-node-local SDF/stencil clip, retained shell, and clean generation-fenced lifecycle. Documentation
closure landed (visualizer/preset authoring guidance, clip evidence accuracy, geometry semantics, fade
authority, BTF coalescing). Do not reopen D1–D9 without contradictory evidence.

Phase-D closure verification also confirmed, without production behaviour change:

- fade authority is unambiguous — one authored authority resolves into two derived layer values
  (`scene_fade` root/card, `content_fade` GL content); guarded by
  `tests/test_qtquick_visualizer_fade_authority.py`;
- the Bubble two-protected-results-before-one-sync BTF semantic holds by forward evolution; pinned by
  `tests/test_bubble_btf_coalescing.py`;
- Bubble keeps one-authored-step -> one-integration with no second logical clock;
- the selected clip owner is the render-node-local SDF/stencil host (the failed `QSGClipNode` handoff is
  not selectable);
- baseline geometry authority = the 1.5 default aspect; literal `420x280` is an internal reference, not
  a required runtime size.

**Remaining Phase-D acceptance debt (operator-scheduled physical/eyes-on; do NOT fabricate here):**

- installed screensaver Bubble wall-clock cadence on the operator's real display/GPU (deterministic
  tests prove the logic preserves one-step->one-integration and the ~90 Hz authored cadence / >= ~88 Hz
  recovery intent, but a bare-thread measurement here would not represent installed behaviour);
- eyes-on old-vs-Quick authored-effect comparison and mixed-refresh continuity.

These do not block migration progress.

**Phase E is IN PROGRESS** (widget presentation + capability setup foundation), started under explicit
operator direction.

Landed E foundation slices (additive/inert at all-on defaults; no default runtime behaviour change):

- **presentation-neutral widget family catalog** — `WIDGET_FAMILY_DESCRIPTORS` in
  `core/settings/widget_family_catalog.py` is the single source of truth mapping stable `family_id` to
  canonical member runtime widget ids. Family-level environment availability is neutral there;
  `rendering/widget_descriptors.py` re-exports the catalog and retains member-level runtime
  availability/legacy descriptor details such as `get_active_member_widget_ids()` — it is not the
  membership source. (Visualizers was later added as a capability family requiring Media; see the E2
  second audit-correction notes below.) Pinned by `tests/test_widget_family_catalog.py`.
- **canonical capability-activation settings schema** — `widgets.family_activation.<family_id>` and
  `transitions.activation.<setting_name>` in canonical defaults (all `True`, so behaviour is unchanged
  until H0), plus `core/settings/capability_activation.py` presentation-neutral read/write/query and
  normalization helpers (`is_widget_family_activated` / `is_transition_activated` /
  `get_effective_random_pool` = activated ∩ pool-member / `is_random_mode_effective` /
  `resolve_manual_transition_selection` / `get_default_activated_transition` /
  `normalize_transition_capability_state`). Canonical normalization explicitly repairs all-false
  activation by persisting Crossfade reactivation and disables Random when its effective pool is empty
  while preserving saved pool preferences. Regenerated `defaults_snapshot.json` and both SST doc
  artifacts. Pinned by `tests/test_capability_activation.py`.
- **transition activation runtime foundation (admission fencing closed)** — engine Random preparation,
  C-key cycling, manual selection and factory-side Random candidate generation filter activation in
  their normal paths, and `normalize_transition_capability_state()` is the one canonical authority
  (consumed by engine prep, factory admission, and C-key). The final-admission foundation corrections
  are now landed and tested:
  - a stale/pre-resolved `transitions.random_choice` is revalidated at final factory admission
    (`TransitionFactory._is_admissible_random_choice`) and rejected if it became deactivated or
    hardware-invalid;
  - the engine, factory (`_pick_random_transition`), and C-key (`_resolve_cycle_fallback`)
    empty-candidate paths no longer run a literal deactivated Crossfade — they pick a deterministic
    activated hw-available transition, or perform the explicit canonical recovery repair
    (`ensure_recovery_transition_activated`, persisted) and admit the now-activated recovery normally;
  - zero-activated and empty-effective-Random-pool states are repaired by the one normalization
    authority (Crossfade reactivation / Random-off + deterministic manual + preserved pool prefs).
  Pinned by `tests/test_transition_activation_admission.py` (factory stale/hw-invalid/manual/never-run-
  deactivated-Crossfade; engine empty-pool + zero-activated repair; C-key never selects deactivated
  Crossfade) and `tests/test_capability_activation.py` (normalization / fallback / recovery units).
  **E2.6 is complete** (see the E2 audit-correction notes below): `random_always` is the single live
  Random authority; the factory and engine no longer treat legacy `type="Random"` as a live trigger.
- **presentation-neutral capability authority (import boundary closed)** — the family catalog was
  extracted to `core/settings/widget_family_catalog.py`; `core/settings/capability_activation.py` now
  imports only that neutral catalog and the (neutral) transition registry. Importing the activation
  authority no longer transitively pulls `PySide6.QtWidgets`, `rendering/widget_descriptors.py`,
  WidgetsTab/settings builders, widget implementations/providers, or Quick renderers. Pinned by
  `tests/test_capability_activation_neutrality.py` (subprocess import probe).
- **widget-family activation runtime consequence (creation-admission dormancy only)** —
  `_create_factory_widgets` skips a deactivated family before per-instance `enabled` handling and
  expected-overlay accounting, so a deactivated family creates no runtime widget at that seam. This
  proves **creation-admission dormancy only**; broader provider/model/service/timer/process/Quick-
  resource dormancy and last-consumer shared-service lifetime remain the **E1 `WidgetRuntimeManager`
  ownership responsibility**. Inert by default. Pinned by `tests/test_widget_manager_refresh.py`.

The activation foundation (neutral catalog + schema + canonical normalization + closed runtime admission
fencing) is landed and inert-by-default. E2 supplies the operator-facing toggle; its audit-correction
work (lazy transition pages, mutation-boundary normalization, E2.6, context-menu activation, responsive
layout) has landed and E2 remains at its audit gate.

Remaining Phase-E work (audit-required at E1 runtime-ownership and before Phase F relies on E2):

- **E1** — `WidgetRuntimeManager` presentation-neutral model/provider ownership split (broader than the
  activation gate already landed above).
- **E2** — Widgets and Transitions `SETUP` subtab UI + lazy navigation consuming the activation schema.
  **Operator decision (2026-08-22): rebuild the nav live** — deactivating a capability while Settings is
  open immediately removes its pill and reactivation re-adds it, matching doc 07 §5.3 literally (not a
  deferred grey-out); default landing is the SETUP page; family rows use theme-matched tooltips.
  - **Widgets SETUP — LANDED.** New always-present first `setup` section descriptor + `_build_setup_ui`
    in `ui/tabs/widgets_tab.py`: one circle-checkbox activation row per available family (from the
    neutral catalog) with description tooltips, `Enable All` / `Disable All` (activation only, never
    per-instance `enabled`), live pill show/hide on toggle, fall-back-to-SETUP when the current family is
    deactivated, activation persisted under `widgets.family_activation.*` through the normal save path
    (SETUP is bootstrap-built so it never depends on lazy hydration and cannot corrupt hidden family
    config). Pinned by `tests/test_widgets_tab_setup.py`; lazy-build index tests updated to stable ids.
  - **Transitions SETUP — LANDED.** Pill/subtab nav on the Transitions tab (`ui/tabs/transitions_tab.py`):
    a first `Setup` pill (default landing) + one pill per activated transition; the old visible dropdown
    is retained only as a passive compatibility mirror (not a selection authority) and the old
    per-transition "Include in Switch/Random
    Pool" checkbox is removed. SETUP page owns transition activation rows + `Enable All`/`Disable All`,
    `Use Random Transitions` (the single `random_always` authority), and a Random Pool list (only
    activated transitions shown; edits `transitions.pool`). Deactivating a transition hides its pill and
    pool row live and falls back to SETUP if it was the edited one; activation persists to
    `transitions.activation.*`; `_save_settings` now also writes `activation` + `random_always` and
    preserves engine-managed `random_choice`/`last_random_choice`. Pinned by
    `tests/test_transitions_tab_setup.py`.
  - **E2.6 `type="Random"` normalization — LANDED.** `normalize_transition_capability_state` now also
    converts a legacy manual `type="Random"` into `random_always=True` + a concrete activated manual
    type (invariants compose with the zero-activated and empty-effective-pool repairs). The Transitions
    tab runs the normalizer on load (persisting any repair). Pinned by `tests/test_capability_activation.py`
    and `tests/test_transitions_tab_setup.py`.

  **E2 audit correction (independent audit of `ae9b95b1` found substantive gaps; corrected — E2 has NOT
  self-promoted to complete).** The following corrective work landed on top of the earlier E2 slices:
  - **Transitions settings are now genuinely lazy.** `TransitionsTab` builds SETUP eagerly and each
    transition's specific-settings page only when its pill is first selected; a deactivated transition
    page is never built, deactivating a built page retires it, reactivation restores the pill without
    rebuilding, and selecting it later rebuilds + hydrates from preserved settings. The hidden legacy
    `transition_combo` is a passive mirror only — `_current_transition` is the authoritative
    manual/edited selection consumed by save/nav; unbuilt transition detail is preserved (not
    reconstructed) across unrelated saves.
  - **Invalid capability state is normalized at the E2 mutation boundary**, not deferred to a later
    load/runtime seam: Disable All / final deactivation reactivates Crossfade and reflects it live;
    Random-on with an empty effective pool disables Random + persists a deterministic activated manual
    type live; a deactivated current manual type resolves to an activated replacement.
  - **E2.6 completed:** `random_always` is the single live Random authority. `type="Random"` is migration
    input only (normalized once); the factory `_get_random_mode` and engine
    `_prepare_random_transition_if_needed` no longer treat `type="Random"` as a live trigger.
  - **Random state parity + activation-aware context menu:** the screensaver context menu rebuilds its
    transition submenu from current activation on show (only activated transitions; Random disabled when
    the effective pool is empty), fails admission on stale deactivated selections, normalizes before
    persist, and shares the single `transitions.random_always` state with Transitions SETUP; it never
    writes `type="Random"`.
  - **Responsive layout:** a shared `ui/flow_layout.py` (`FlowContainer`/`FlowLayout`) drives wrapping
    pill navigation, responsive module grids (Widget Modules, Transition Modules, Random Pool — ≥2
    columns at normal width, more when wider), and wrapping Enable/Disable All rows in BOTH tabs; Widget
    Modules now uses the styled `QGroupBox` + circle-checkbox grammar. Frames stay horizontally contained
    with no horizontal scrollbar.

  Pinned by `tests/test_transitions_tab_setup.py`, `tests/test_capability_activation.py`,
  `tests/test_context_menu_activation.py`, `tests/test_flow_layout.py`, `tests/test_widgets_tab_setup.py`,
  and the transition admission suite.

  **E2 second audit correction (independent audit of `ad2b0649` found five further substantive gaps;
  corrected — E2 still NOT self-promoted).** Landed on top of the above:
  - **Visualizers is now an application-level capability** (neutral catalog family `visualizers`, member
    `spotify_visualizer`, `settings_section_id="visualizers"`) with a neutral dependency
    `required_family_ids=("media",)`. Canonical default `widgets.family_activation.visualizers=True`;
    snapshot + SST regenerated. Runtime/render ownership stays the Phase-D subsystem (not Phase-F, not
    `WidgetRuntimeManager`).
  - **Media→Visualizers dependency** enforced by the one neutral authority
    `normalize_widget_capability_state` (`media=False` forces `visualizers=False`, never auto-reactivates
    Media/Visualizers). Widgets SETUP shows a Visualizers row that is disabled + "Requires Media" while
    Media is off, with the repair reflected live.
  - **Explicit visualizer runtime admission**: local `_setup_spotify_visualizer` and remote
    `_reconcile_remote_custom_visualizer` fence on `is_widget_family_effective(config, "visualizers")`
    (activated + Media activated), so a stale/reused Media object cannot bypass the capability gate.
  - **Context-menu visualizer admission**: the Change Visualizer submenu is hidden when Visualizers/Media
    is deactivated (refreshed on show), and a stale mode-selection request is rejected.
  - **Generic Widgets page retirement**: deactivating any family retires its built Settings section
    (container destroyed, built/hydrated ownership + control attrs cleared) so it is genuinely
    rebuildable; persisted per-family config is preserved; SETUP is never retired.
  - **Live Random link**: `TransitionsTab` subscribes to `SettingsManager.settings_changed` and reflects
    external `transitions` mutations (context-menu Random / concrete selection) into its live controls
    with a write-reentrancy guard, so it can no longer resurrect a stale `random_always`/`type`.
  - **Random can no longer escape the saved pool**: the engine random prep and factory
    `_pick_random_transition` FAIL CLOSED when `activated ∩ saved pool ∩ hardware` is empty (no
    broadening, no out-of-pool substitution, saved pool untouched); the context-menu Random availability
    uses the same bounded rule.
  - **Transitions programmatic-nav admission**: `_on_nav_selected` redirects a deactivated transition key
    to SETUP before any selection/mirror/build/save.

  Pinned by `tests/test_widget_family_catalog.py`, `tests/test_capability_activation.py`,
  `tests/test_widgets_tab_setup.py`, `tests/test_visualizer_capability_admission.py`,
  `tests/test_transitions_tab_setup.py`, `tests/test_transition_activation_admission.py`,
  `tests/test_transition_distribution.py`, and `tests/test_context_menu_activation.py`.

  **E2 remains at its audit gate — do NOT self-promote to complete.** The only remaining acceptance item
  is operator `python main.py --s` eyes-on confirmation of the responsive layout (already reported
  "much better") and the new Visualizers dependency UX across widths. Checkpoint/push/audit E2 before
  Phase F.
- **E3** — shared retained Quick visual primitives.
- **E4** — global eight-direction shadow authority (default `SE`).

Pre-existing unrelated test failures observed during the E foundation sweep (NOT caused by E work; flag
for separate triage): `test_visualizer_settings_plumbing.py::TestVisualizerModeBinding::test_load_visualizer_mode_selection_falls_back_when_saved_mode_is_unknown`
(expects `bubble`, gets `devcurve`) and
`test_sine_line4_builder_integration.py::test_actual_save_media_settings_includes_line4`.

If the operator instead explicitly says **continue from Phase C tests**, execute Section 7.5 test-only
hardening first.

---

# 16. Cross-links

Technical decompositions:

- `Docs/QtQuick_Migration/README.md`
- `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md`
- `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`
- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`
- `Docs/QtQuick_Migration/06_Build_Tooling_Validation.md`
- `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`

Durable routing/guardrails:

- `Index.md`
- `Spec.md`
- `Docs/Contracts.md`
- `Docs/Compositor_Architecture.md`
- `Docs/Guardrails.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`

Current transition/visualizer references:

- `Docs/Transition_Change_Checklist.md`
- `Docs/Harness_Index.md`
- `Docs/TestSuite.md`
- `Docs/Visualizer_Reference.md`

Defaults/tooling:

- `Docs/Defaults_Guide.md`
- `tools/default_settings_editor.py`
- `tools/regenerate_defaults_snapshot_artifacts.py`
- `tools/regenerate_sst_defaults.py`

Deletion/deferred scope:

- `Future_Cleanup.md`
- `Future_Work.md`
