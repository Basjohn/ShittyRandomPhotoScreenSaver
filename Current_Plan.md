# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-21

## Source / reviewed checkpoints

Original architecture/decision orientation anchor:

```text
18c8f26756df83bd0d8828becc740c72d5526b21
4.7.2 - Pre-Quick Migration Docs v1
```

That SHA is historical orientation, not a required current HEAD.

Latest Phase-C implementation checkpoint reviewed for this revision:

```text
7c4871016464c4a82cf19af6f113bcb21153a483
Expand Phase C real-GL sign-off matrix
```

Immediately preceding closure checkpoints include registry parity and canonical Settings-to-request parameter resolution. Documentation closure commits follow that implementation checkpoint.

The Qt Quick presenter decision and inline custom-GL primitive are closed by the P0/Phase-A evidence. Do not reopen the presenter or `QSGRenderNode` selection without concrete contradictory implementation evidence.

## Required routing before active work

Do not treat this plan as a substitute for durable architecture/guardrail docs. For a migration slice use:

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

`Future_Work.md` is deferred new-feature/experiment scope, not migration work admission. Do not implement from it while the active plan or `Future_Cleanup.md` contains important work unless the operator explicitly selects an item.

---

# Active execution window

This file owns migration sequence and work admission. The technical decompositions under `Docs/QtQuick_Migration/` explain how to execute admitted work; they do not create parallel phases.

| Phase | Current status | Implementation permission |
| --- | --- | --- |
| A — bootstrap/render-node proof | Structurally complete | Do not reopen; compiled smoke remains operator-scheduled later |
| B — runtime-host decomposition | Structurally complete | Do not reopen without contradictory evidence |
| C — base image + transitions | **IMPLEMENTATION COMPLETE; acceptance debt explicit** | No new C code unless deferred evidence demonstrates a defect |
| **D — visualizer** | **ACTIVE** | **Normal implementation work belongs here now** |
| E — widget presentation foundation | Waiting for D implementation exit | Reference only |
| F — widget families | Waiting for E | Reference only |
| G — CUSTOM/input/auxiliary pixels | Waiting for F | Reference only |
| H — settings epoch + production cutover | Waiting for A–G implementation | Reference only |
| I — legacy presenter deletion | Waiting for H cutover | Reference only |
| J — tooling/final validation/docs closure | Waiting for migration implementation | Reference only |

## Phase promotion rule

A phase may move forward when its **implementation dependencies** are structurally closed even if hardware-dependent/eyes-on acceptance remains explicitly deferred.

Deferred evidence must be listed with runnable commands/criteria. A later failure reopens the smallest demonstrated owner/phase defect; it does not automatically roll the migration sequence backward or authorize a compatibility architecture.

Production cutover in Phase H still requires the full Quick implementation surface to exist. Final release acceptance in Phase J still requires the scheduled physical/compiled evidence.

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
- product features/customization.

Backward compatibility with pre-Quick **presentation state** is deliberately not a migration goal; Phase H0 creates a new settings epoch.

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
- screenshot-to-texture QWidget wrappers as final widgets;
- duplicated legacy and Quick widget presentation pipelines after cutover.

During migration, old production code may coexist in the repository as reference/current production until Phase H. Once production cuts over, Phase I deletion begins immediately.

The selected custom-GL seam is:

```text
QQuickItem(ItemHasContents)
-> updatePaintNode()
-> QSGRenderNode
-> direct OpenGL inside the owning Quick scene
```

`QQuickRhiItem` is not the normal SRPSS custom-render path. If the selected `QSGRenderNode` seam is proven fundamentally unusable in pinned PySide/compiled product, stop and revise the **single** primitive deliberately; do not keep competing product primitives.

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

Migration parity includes current supported presentation capabilities such as opacity, backgrounds/cards, borders/radius, fonts/colors, shadows, artwork, separators/icons, progress controls, stacking, monitor routing, pixel shift, dimming, CUSTOM geometry/edit, context interaction, visualizer all five modes, transitions, and Media Center interaction.

Do not solve migration defects by flattening/removing authored effects.

## 1.4 No premature full/compiled builds

During Phases C–G, normal gates are focused Python/static/runtime harnesses.

Do not run Nuitka/full installed builds merely as routine migration validation. Keep packaging inputs current. Compiled/installed validation remains operator-scheduled unless the operator explicitly requests it earlier.

---

# 2. Git / agent / connector workflow

## 2.1 Checkpoints are mandatory

For normal local-agent work:

```text
inspect exact current source
-> implement narrow slice
-> focused gate
-> inspect diff/status
-> commit intended paths only
-> push
-> independent audit of actual pushed source/diff
-> continue
```

Do not stop after a successful checkpoint merely to ask permission to continue.

High-risk effects/owners such as BlockSpin, Burn, Particle, Bubble, settings epoch, and production cutover deserve dedicated checkpoints.

## 2.2 Connector/API write discipline

Repository connector writes are allowed when practical, but their editing ergonomics are weaker than a local worktree.

For risky whole-file/chunk reconstruction:

```text
fetch authoritative parent
-> build candidate blobs/tree
-> create UNATTACHED candidate commit
-> compare parent..candidate
-> confirm only intended files changed
-> spot-fetch beginning/end and suspicious reconstructed sections
-> move branch ref only after candidate audit
-> fetch/compare the branch-reachable commit again
```

Creating a blob/tree is not a checkpoint. A checkpoint must be a commit reachable from the intended pushed branch.

If an API/chunk edit produces an unexpectedly broad/malformed diff, abandon the unattached candidate. Do not let corruption become branch history and repair it afterward.

For large changes where direct connector reconstruction becomes unreliable, fall back to whole replacement files or a narrow paste-ready coding-agent prompt, then audit the actual pushed result.

## 2.3 Trust evidence, not agent prose

An agent saying tests passed or code was implemented is not evidence. Inspect current repository state, pushed commit, diff, relevant source, and independent CI/harness evidence when available.

Repository state outranks stale orientation prose.

---

# 3. CI evidence rules and known 2026-08-21 failure

GitHub Actions is an independent execution environment, not ChatGPT's runtime and not the operator's physical RTX/multi-display environment.

Good hosted-CI evidence:

- deterministic Python/unit/source contracts;
- registry/settings tests;
- lifecycle logic where headless execution is representative;
- import/dormancy tests;
- shader/source contract tests;
- later packaging sanity when build policy permits it.

Hosted CI is not authoritative for:

- actual 165 Hz/60 Hz physical cadence;
- PresentMon/display occupancy;
- subjective Bubble/effect smoothness;
- physical multi-monitor topology;
- real GPU utilization/performance.

### Windows CI run `32436553793`

The email saying "all jobs failed" did **not** mean GitHub abruptly killed the hosted runner.

Observed facts from the archived Actions logs:

- setup/dependency installation completed;
- chunk 1 ran ~130 s and returned ordinary test failures;
- chunk 2 printed a complete pytest summary (`3 failed, 1219 passed, 67 skipped`) in ~24.76 s but the Python process did not exit; `tests/run_chunked.py` killed the still-live process at its own 900-second timeout (`exit 124`);
- chunk 3 stopped around 50% test execution progress with no pytest summary and hit the same wrapper timeout;
- chunk 4 ran ~180 s and returned ordinary test failures;
- the outer Actions job had `timeout-minutes: 70` and completed normally after the wrapper returned failure;
- logs/artifacts uploaded successfully.

Interpretation:

- chunk 2 strongly suggests leaked shutdown ownership/non-daemon thread/background process after pytest finished, rather than a 15-minute test body; the exact owner remains to be isolated;
- chunk 3 requires verbose/smaller isolation because it appears to hang during test execution;
- completed chunks contain several failures in old/default/UI/doc/visualizer areas, so broad-suite red status is currently noisy and must be inspected rather than attributed wholesale to the active migration slice;
- an uncompleted/timed-out chunk is **not** assumed clean; Phase-C focused tests still require explicit sign-off.

That CI run also exposed a deterministic workflow configuration defect: `actions/checkout` used its default `fetch-depth: 1`, while an existing Bubble guardrail executes `git show 510520e:...` and therefore cannot see the historical object.

The Phase-C documentation closure changes the workflow to `fetch-depth: 0`. That removes the known shallow-history failure on future runs, but it does not claim to fix the separate shutdown/hang or unrelated test failures.

Do not fix the remaining timeout behavior by merely increasing 900 seconds. Isolate the actual owner/test with smaller/verbose chunks or explicit thread/process diagnostics.

This broad-suite CI debt does not block Phase-D implementation by itself.

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
enabled?
  yes         no
   ↓           ↓
resolve        implementation/provider/resources stay dormant
runtime
```

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

Deferred A4 compiled smoke remains operator-scheduled after implementation unless explicitly requested earlier.

Do not reopen Phase A merely to reconfirm the already selected architecture.

---

# 6. Phase B — runtime-host decomposition

Structurally complete for forward migration.

Settled properties:

- one `QuickDisplayRuntime` per selected physical display;
- per-runtime window/scene/pacer/input ownership;
- generation-scoped lifecycle including generation 0;
- queued Qt/C++ meta-call teardown for hide/release/close rather than blocking Python render-thread inversion;
- hide/wake behavior;
- coordinated one-shot exit;
- deterministic destruction barriers;
- topology replacement harnesses;
- unexpected QWindow screen displacement does not silently adopt a fallback display;
- binding loss preserves original physical identity/pacer target, quiesces presentation/input, and emits one-shot topology/binding loss.

Production `DisplayManager -> QuickDisplayRuntime` ownership still waits for Phase H.

---

# 7. Phase C — base image + transitions

**Implementation status: complete.**

Read `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md` and `Docs/Transition_Change_Checklist.md` for the landed authoring/runtime contract.

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

Disabled transitions remain Settings/catalog-visible as appropriate while implementation/shader/resource ownership stays dormant.

## 7.3 Critical preserved contracts

### Slide

Four cardinal product directions only. Source/destination sampling and pixel ownership derive from one immutable eased sample in one draw, so missed physical frames may cause a larger positional jump but never a seam/gap.

### 3D Block Spins

Real thin 36-vertex rectangular-prism slab, depth-tested front/back/sides, black void, four axes/directions, correct destination UV orientation, cubic internal spin, dark sides, moving specular band, white edge rim, context-local resource teardown. No flat fallback.

### Particle

Canonical shader preserved with Directional/Swirl/Converge, directional/random-placement modes, trails, swirl settings/order, wobble, texture mapping, 3D shading, gloss/light controls, seed, and physical-framebuffer resolution semantics.

### Burn

Canonical rich shader preserved: ignition, six directions, 4-octave/domain-warped noise, jagged front, heat distortion, glow, white-hot core, char/crackle/smoulder progression, sparks, smoke, ash, densities/toggles, per-run seed, run-clock animation time, delayed destination tail.

## 7.4 Phase-C acceptance debt

The following are **sign-off**, not missing architecture/implementation:

- execute focused deterministic Phase-C tests on a capable clean checkout;
- isolate current CI shutdown/hang behavior enough to obtain meaningful independent broad-suite evidence;
- run Blinds real-GL directions;
- run `tools/qtquick_phase_c_effect_smoke.py` cases for Diffuse/Ripple/Crumble/Particle/Burn;
- scheduled physical two-display variants where required;
- eyes-on old-vs-Quick authored-effect comparison;
- normal/high-refresh continuity and physical cadence only where it answers an unresolved question.

Phase D may proceed while these remain open.

If sign-off later fails, repair the smallest demonstrated Phase-C defect, checkpoint/push/audit it, then continue the active migration phase.

Do not broadly retune effects or revisit presenter architecture absent evidence.

---

# 8. Phase D — visualizer — ACTIVE

Read:

- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- `Docs/Visualizer_Reference.md`

## D1 — presentation-neutral runtime/controller

Separate the non-pixel visualizer owner from QWidget presentation without rewriting provider/business logic.

Retain ownership for settings/mode/preset activation, playback state, BeatEngine/source, `VisualizerLogicalRuntime`, and latest logical publication.

Do not instantiate a hidden QWidget merely to keep those owners alive.

Checkpoint/push/audit this split.

## D2 — immutable latest-state render bridge

Publish bounded immutable current visualizer snapshots containing generation/activation identity, mode/playback identity, logical timestamp, geometry/fade/style, and mode-specific render data.

No render-thread reads from live QWidget/QObject/provider/Settings state.

Latest state wins; no FIFO/catch-up replay. Protect short-lived authored edges explicitly.

Checkpoint/push/audit the bridge separately.

## D3 — Quick visualizer item/node + geometry/card foundation

Use one sub-rect custom Quick item/QSGRenderNode inside the display QQuickWindow.

One committed geometry authority feeds retained card chrome and GL viewport/scissor/shader geometry/CUSTOM seam.

Preserve DPR from the owning display/window. No separate native visualizer window, QPainter fallback, or QWidget texture wrapper.

Retained Quick card presentation must preserve background/border/radius/shadow/color/fade/customization.

## D4 — sole authored logical clock

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

## D5 — five mode ports

Preserve all current authored behavior for:

1. Spectrum — bars/peaks/ghosting, paused idle visibility, source freshness;
2. Oscilloscope — waveform/line persistence/idle behavior;
3. Sine — authored idle/layers/reactivity, no separate timer;
4. Bubble — dedicated high-risk checkpoint with BTF, continuous positional evolution, collisions, trails/tails, ghosts/pop/transients/protected edges, authored logical Hz;
5. DevCurve — active layers/order/alpha/offsets/outline/ghosting/tuning.

Do not retune modes to hide presentation problems.

The observation that unrelated widgets can materially change measured Bubble-era GPU load supports retained-scene efficiency and true feature dormancy. It does not implicate Bubble collision logic by itself.

## D6 — Pause/Play and lifecycle

Preserve warm-source/expected-state behavior without recreating the window/item or inventing a second playback authority.

Retirement must close publication, stop/join the logical runtime, invalidate activation/generation, remove snapshot admission, release GL resources on the render owner, and destroy roots cleanly.

A background owner that prevents process/test shutdown is a defect.

## D7 — checkpoint cadence

Prefer pushed/audited checkpoints for:

1. runtime/controller split;
2. immutable bridge;
3. item/node + geometry/card foundation;
4. Spectrum;
5. Oscilloscope;
6. Sine;
7. Bubble + BTF;
8. DevCurve;
9. all-five-mode lifecycle/source/pause closure;
10. Phase-D documentation closure.

## D exit

All five modes use the Quick visualizer boundary with the authored logical runtime intact, immutable latest-state publication, clean lifecycle/resources, and no old compositor/QWidget presentation dependency inside the new renderer.

After implementation exit, rewrite visualizer/preset authoring guidance against the landed Quick contract. Explicit physical/eyes-on items may remain as scheduled acceptance debt if they cannot be meaningfully executed by hosted agents.

---

# 9. Phase E — widget presentation foundation

Read `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`.

## E1 — presentation-neutral descriptor/runtime ownership

Make canonical widget identity/settings metadata independent of QWidget factories.

Create/rename the future `WidgetRuntimeManager` around provider/model lifecycle, enabled/visible state, monitor participation, stacking inputs, settings updates, fade intent, generation/model registration, and actions.

A disabled family must not own feature-specific provider/model/process/poll/timer/Quick component/resource solely because its files are installed. Shared infrastructure remains only while another enabled capability needs it.

Do not create a giant Python `QuickBaseOverlayWidget` god object.

## E2 — shared retained Quick primitives

Build small reusable primitives for cards/backgrounds, border/radius, foreground opacity, shadows, text/header shadow, image/artwork, separators, text, fades/visibility, click targets, controls.

## E3 — eight-direction shadow authority

Add one global presentation-neutral direction setting:

```text
NW   N   NE
 W   ·    E
SW   S   SE
```

Eight outer directions; default `SE`; center is not a ninth mode.

Direction changes signs while preserving each family’s authored magnitude/blur/spread/opacity/color. Cover cards, text, headers, icons/artwork, controls, volume slider, visualizer, clocks, Weather, Media, Reddit/Gmail, Steam families, multiple DPRs, and CUSTOM geometry.

Do not reintroduce QWidget `QGraphicsDropShadowEffect`.

---

# 10. Phase F — widget families

Port runtime pixels, not Settings GUI/backends.

## F0 — remove deprecated Imgur instead of porting it

Remove its live gate/defaults/settings controls/descriptor/runtime/provider/CUSTOM/tests/package/current-authority docs/Foundry metadata. Do not build compatibility around stale Imgur presentation keys.

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

Per family: identify provider/business logic → compact runtime model → retained Quick presentation → preserve customization → deterministic tests/gallery → CUSTOM expectations → commit/push/audit.

Do not rewrite provider/network logic into QML or use QWidget screenshots as final presentation.

After F implementation exits, rewrite widget authoring guidance for the final descriptor/model/family/Quick component contract.

---

# 11. Phase G — CUSTOM, input, interaction, auxiliary pixels

Read `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`.

## G1 — CUSTOM session

Refactor `CustomLayoutManager` into presentation-neutral session/state + Quick edit presentation.

Edit the real retained Quick item. Keep uncommitted session geometry separate from persisted settings. Save commits; Cancel restores baseline. Grid/outline/handles are separate Quick edit items.

Cross-monitor transfer moves/recreates one presentation instance on the target scene; no simultaneous duplicate live pixel owners.

Do not spend migration effort translating old QWidget geometry; H0 resets it.

## G2 — input/interaction

Refactor `InputHandler` away from DisplayWidget assumptions and route QQuickWindow events to existing actions.

Preserve exit gestures, hotkeys/media keys, Ctrl interaction mode, layout slots under the new schema, clicks, right-click context menu, Media Center behavior.

Transient QWidget control UI/settings dialog may remain if decoupled from DisplayWidget and not used as accelerated presentation.

## G3 — auxiliary runtime pixels

Port cursor halo, dimming, pixel-shift scene transform, required error/fallback display, edit grid/handles, and any remaining runtime overlay pixel owner.

---

# 12. Phase H — settings epoch + production cutover

No production-owner cutover until Quick implementation contains base images, all active transitions, all five visualizer modes, runtime widget families, CUSTOM, input/context, dimming/pixel shift/halo, multi-display/lifecycle, and packaging inputs ready for later compiled validation.

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
- widget enablement/presentation/style/position/dimensions;
- presentation monitor routing;
- CUSTOM geometry/restore payloads/layout slots;
- display geometry assumptions;
- old shadow/effect settings;
- visualizer presentation/geometry;
- old user visualizer presentation presets unless deliberately retained under a new-schema decision;
- other QWidget/QRhi/compositor-era presentation state.

No heroic coordinate translation.

Built-in visualizer presets remain product baseline; users can edit/create/save new presets in the new schema.

### Epoch operation

```text
pre-Quick settings detected
-> copy explicit durable whitelist
-> construct fresh final Quick defaults
-> restore whitelist
-> atomically persist new epoch/version through normal durability boundary
-> future current-epoch starts do nothing
```

Prove reset exactly once, durable source/auth data survives, presentation state resets, malformed old presentation state cannot leak through, second startup does not reset again, and persistence reaches normal durability boundary.

Checkpoint/push H0 before H1.

## H1 — production-owner switch

Make one explicit switch:

```text
DisplayManager
    from DisplayWidget
    to QuickDisplayRuntime
```

Change callers to the real new API. No DisplayWidget compatibility facade and no production flag back to QRhiWidget.

Run focused/chunked gates as meaningful. Do not initiate installed/full build unless operator scheduled.

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
- migration-only scaffolding.

Do not delete presentation-neutral authored shaders/math merely because the old compositor also used them; shared assets survive when Quick is their real consumer.

For every deletion batch: caller proof → focused tests → commit → push → audit → continue.

Do not leave both presenter architectures “for safety.”

---

# 14. Phase J — Defaults Foundry, final validation, documentation closure

Read `Docs/QtQuick_Migration/06_Build_Tooling_Validation.md`.

## J0 — retarget Defaults Foundry

Current tool: `tools/default_settings_editor.py`.

It currently reads canonical `DEFAULT_SETTINGS` directly via AST/literal, recursively edits leaves, writes Normal base + MC differential, and regenerates snapshot/SST artifacts.

After H0/H1/I establish final schema:

- keep direct literal-reading if `core/settings/default_settings.py` remains canonical;
- otherwise retarget explicitly;
- remove deleted metadata such as Imgur;
- add finite-value metadata for new canonical settings such as shadow direction;
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

Beyond-parity closure should show no QWidget effect-cache shadow architecture, no per-widget accelerated surfaces, retained Quick widgets not rebuilding stable content every physical frame, clean render-thread ownership, true disabled-feature dormancy, and decomposition of overloaded old presentation modules.

## J2 — documentation closure

Update current-authority docs to landed class/file names; make Quick transition/widget/visualizer authoring guides sole current implementation authority; update Defaults guide; remove current instructions that teach dead QWidget/QRhi/compositor owners.

Preserve historical bug/evidence documents as history rather than rewriting them as current architecture.

---

# 15. Current next work

Normal implementation work is now **Phase D**.

Start by inspecting the exact current visualizer ownership/source before changing it, then execute:

```text
D1 runtime/controller split
-> checkpoint/push/audit
D2 immutable latest-state bridge
-> checkpoint/push/audit
D3 Quick item/node + geometry/card foundation
-> checkpoint/push/audit
mode ports, with Bubble dedicated
-> all-five-mode lifecycle/source audit
-> Phase-D docs closure
```

Do not wait for Phase-C eyes-on/hardware sign-off unless the Phase-D change directly depends on the unresolved evidence.

Do not start E–J or `Future_Work.md` opportunistically while D is active.

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
