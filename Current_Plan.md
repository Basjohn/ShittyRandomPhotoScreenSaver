# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-20

## Source / decision checkpoint

The documentation/decision checkpoint reviewed for this migration remains:

```text
18c8f26756df83bd0d8828becc740c72d5526b21
4.7.2 - Pre-Quick Migration Docs v1
```

This SHA is an orientation anchor, **not** a required current HEAD.

The latest execution checkpoint explicitly reviewed while producing this revision is:

```text
9c09e86276b2718163df1673b3d388fe8af664a1
5.0.0 - Phase C Migrations In Progress Work
```

That SHA is also an orientation checkpoint, not a command to reset the repository to it.

At that reviewed checkpoint:

- Phase A/B foundation and topology work are complete enough for migration to remain in Phase C;
- the Phase-B topology-displacement audit issue is closed;
- Quick transition implementations exist for:
  - Crossfade;
  - Slide;
  - Wipe;
  - Warp Dissolve;
  - Block Puzzle Flip;
  - 3D Block Spins;
- the remaining canonical transition set is:
  - Blinds;
  - Diffuse;
  - Ripple / Raindrops;
  - Crumble;
  - Particle;
  - Burn.

Before active work:

1. inspect current `HEAD` and the working tree;
2. preserve unrelated user work;
3. inspect code changes after the relevant checkpoint only far enough to update assumptions they actually invalidate;
4. never reset, clean, checkout, stash, or revert merely to manufacture equality with an orientation SHA;
5. trust repository state and focused tests over an agent's prose claim about what it completed.

The Qt Quick architecture decision is closed by the P0 evidence. Do not reopen the presenter comparison.

---

# 0. Mission

Perform **one** production presentation migration:

```text
current QWidget / QRhiWidget runtime presentation
                    ↓
one standalone threaded QQuickWindow per physical display
                    ↓
Qt Quick scene + inline custom GL render nodes
```

Do not plan a second presenter migration afterward.

Do not rewrite unaffected product systems.

Keep, unless a later phase explicitly replaces a presentation-coupled part:

- `ScreensaverEngine` orchestration except where display-runtime calls must change;
- image source/provider backends;
- SettingsManager and persistence infrastructure;
- source/account/credential ownership;
- QWidget Settings UI;
- RSS/folder/media/GSMTC/provider logic;
- ProcessSupervisor / ThreadManager ownership where still appropriate;
- `VisualizerLogicalRuntime`;
- visualizer authored algorithms and mode personality;
- custom-layout math/behavior contracts;
- transition registry/settings identity;
- product features and customization.

Important distinction:

- keeping SettingsManager/persistence infrastructure does **not** require preserving old presentation-setting values through cutover;
- keeping custom-layout math/behavior does **not** require translating pre-Quick widget geometry;
- Phase H0 intentionally creates a new Qt Quick settings epoch and resets migration-sensitive state.

Replace/refactor what is coupled to the old runtime-pixel owner.

---

# 1. Hard operating rules

## 1.1 No runtime compatibility architecture

Do **not** add:

- a production setting/env switch selecting QRhiWidget vs Quick;
- a permanent facade that makes `QQuickWindow` pretend to be `DisplayWidget`;
- a QWidget presenter embedded over/under the Quick runtime;
- a second accelerated visualizer/widget surface;
- `QQuickWidget`;
- a QRhiWidget fallback if Quick rendering fails;
- a transition-by-transition fallback to the old compositor;
- duplicated legacy and Quick widget presentation pipelines after cutover.

During development, the old production runtime and the not-yet-active Quick implementation may coexist
in the repository. Only one is the normal production path at a time. Migration harnesses may exercise
the Quick path before cutover.

Once production cuts over, legacy presentation removal begins immediately.

## 1.2 Refactor overloaded presentation modules while migrating

Refactor when overload is directly caused by the old presentation boundary.

Required examples:

```text
DisplayWidget
    -> runtime/window owner
    -> input owner
    -> scene/presentation owner
    -> widget/model owner
    -> CUSTOM/edit owner

WidgetManager
    -> widget/provider/model lifecycle owner
    -> layout/visibility owner
    -> Quick presentation item owner

GLCompositorWidget
    -> transition renderer/resource owner
    -> visualizer renderer/resource owner
    -> presentation pacing owner
```

Do **not** use the migration as permission to refactor unrelated source/provider/backend systems.

## 1.3 Preserve full runtime visual capability

Migration parity includes, where currently supported:

- per-widget opacity;
- card/background opacity;
- text opacity/color;
- shadows;
- text/header shadows;
- borders and border opacity;
- rounded corners;
- fonts and font sizes;
- margins;
- artwork sizes/shapes/rounding;
- separators/icons/header chrome;
- progress bars/glow/shadow;
- widget fades;
- stacking;
- monitor routing;
- pixel shift;
- dimming;
- CUSTOM position/resize;
- multi-monitor transfer during edit;
- context interaction;
- visualizer card + all five visualizer modes;
- all supported transitions;
- Media Center interaction behaviour.

Do not solve a migration bug by deleting or flattening a visual feature.

Where an existing effect is unusually authored or visually rich, preserve its real effect contract rather
than replacing it with a conceptually similar but cheaper-looking approximation.

## 1.4 Frequent Git checkpoints are mandatory

After **every landed slice**:

1. run the focused gate for the slice;
2. inspect `git diff` / `git status`;
3. commit only the intended slice;
4. `git push`;
5. continue immediately to the next slice when gates pass.

A normal migration session should produce many small pushed commits, not one giant migration commit.

Good checkpoint scale:

```text
Quick bootstrap + first render node
frame pacer extraction
Quick runtime host
one transition or tightly related transition batch
visualizer immutable bridge
Bubble render node
shared Quick card/shadow primitive
clock family
weather
media
reddit
gmail
Steam family
CUSTOM session
settings epoch reset
production cutover
legacy deletion batch
Defaults Foundry retarget
build/tooling closure
```

Do not pause after a successful checkpoint to ask permission to continue.

For a high-risk effect such as BlockSpin, Burn, Particle, or Bubble, prefer one effect per checkpoint.

## 1.5 Do not stop unless an actual blocker is hit

A failing test, compile error, visual bug, missing import, wrong geometry, or one difficult widget is
not by itself a blocker. Diagnose, correct, re-run, checkpoint, continue.

An **actual blocker** is something such as:

- the selected Quick custom-render primitive is fundamentally unusable in pinned PySide 6.9.1 or
  the compiled product after a focused proof;
- required one-window-per-display semantics cannot be preserved;
- a required product visual/interaction capability cannot be represented without a prohibited
  second presentation architecture;
- lifecycle/resource ownership cannot be made deterministic after focused correction;
- essential external information/credential/device access genuinely unavailable to the agent is
  required to proceed.

If a blocker is hit:

- stop broad code churn;
- record exact evidence;
- name the blocked owner and smallest decision required;
- do not invent a compatibility layer to go around it.

## 1.6 Support docs do not own sequence

The technical decomposition docs under:

```text
Docs/QtQuick_Migration/
```

are subordinate to this file.

They explain **how** to perform a named slice. They may not:

- reorder the phases;
- create a parallel roadmap;
- authorize work not admitted by this plan;
- keep completed work active after this plan removes it.

Deferred post-cutover deletion is cross-linked to `Future_Cleanup.md`.

## 1.7 Developer documentation migrates with proven contracts

Do not rewrite presentation-feature authoring/development guidance before its owning implementation
phase has proved the final contract.

During pre-cutover rewrites, label new guidance as the Qt Quick target architecture while the old
production presenter still exists.

- [ ] After Phase C exits, rewrite transition-authoring guidance for the canonical registry and lazy
  Quick renderer contract.
- [ ] After Phase D exits, update visualizer/preset-authoring guidance for the final Quick visualizer
  boundary while preserving preset and logical-runtime instructions that remain valid.
- [ ] After Phase F exits, rewrite widget-authoring guidance for the presentation-neutral
  descriptor/model/family registry and retained Quick component contract.
- [ ] After Phase H cutover and Phase I deletion, remove or archive obsolete QWidget, QRhiWidget and
  compositor authoring instructions and make the Quick guides the sole current authority.
- [ ] In Phase J, audit README/project overview, architecture docs, contracts, indexes, cross-links,
  examples, troubleshooting/build guidance, Defaults Foundry guidance, and references to deleted
  presentation code.

Preserve historical bug/evidence documents as history; only repair links or add context needed to
keep that history intelligible.

## 1.8 No premature compiled/full builds

During migration implementation, do not run compiled/full builds merely as routine validation.

Keep build scripts and packaging inputs compatible, but compiled/installed validation is operator
scheduled after implementation is complete unless the operator explicitly requests an earlier build.

Focused script/static/runtime harness tests are the normal migration gates.

---

# 2. Destination architecture

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
                    +-- CustomLayoutSession (when active)
```

Visualizer:

```text
audio / analysis
    -> VisualizerLogicalRuntime
    -> immutable latest visualizer snapshot
    -> Quick visualizer item sync
    -> render-thread GL node
```

Transition:

```text
image pipeline
    -> presentation image state
    -> TransitionRun (monotonic time + parameters)
    -> display presentation pacer
    -> full-screen Quick render node
```

Ordinary widget:

```text
existing provider/business logic
    -> small Python runtime model
    -> retained Quick component
```

Feature activation:

```text
cheap catalog metadata
        ↓
enabled?
  yes         no
   ↓           ↓
resolve        implementation stays dormant
runtime        no provider/model/resource solely for feature
```

---

# 3. Selected technical direction

## 3.1 Graphics API

Keep the successful P0 conditions:

- `QSG_RENDER_LOOP=threaded`;
- Qt Quick graphics API explicitly OpenGL;
- current OpenGL 4.1/core profile requirements unless source proves a transition/visualizer requires
  another exact format;
- one top-level `QQuickWindow` per physical display.

Bootstrap must happen before the first Quick window/scene graph is created.

## 3.2 Custom GL integration

Preferred production primitive:

```text
QQuickItem(ItemHasContents)
    -> updatePaintNode()
    -> QSGRenderNode
    -> direct OpenGL inside the Quick scene
```

Reasons:

- inline in the scene;
- correct stacking relative to retained Quick items;
- no extra offscreen texture pass solely to re-composite custom rendering;
- matches the one-physical-surface target;
- PySide exposes `QSGRenderNode`;
- the P0 benchmark proved Python render-thread OpenGL inside `QQuickWindow`.

The selected primitive is not limited to flat fragment-shader effects. A transition/visualizer renderer
may own context-local meshes, VAOs/VBOs, depth state, textures, shader programs, and other GL
resources when its visual contract requires them, provided all state/resource ownership remains
properly fenced and restored.

If this primitive itself becomes an actual binding/runtime blocker, stop and revise the **single
chosen Quick custom-render primitive**. Do not keep two product primitives as fallbacks.

## 3.3 Presentation pacing

Use the production presentation-only frame pacer derived from the proven P0 target-pacing semantics.

Properties:

- one pacer per display;
- target based on that display's refresh;
- starts only while custom dynamic content requires continuous presentation;
- transition and visible visualizer are independent frame-demand reasons;
- missed deadlines are skipped, not replayed;
- no `afterRendering -> update()` self-loop;
- no paint acknowledgement;
- no logical visualizer cadence ownership.

Retained Quick animations may dirty the scene normally. The custom GL pacer exists for
transition/visualizer content that needs continuous render opportunities.

---

# 4. Phase A — bootstrap and render-node proof

Read:

- `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md`
- `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`
- `Docs/QtQuick_Migration/06_Build_Tooling_Validation.md`

Phase A/B foundation has already produced the standalone Quick runtime, inline render-node proof,
presentation pacing/lifecycle work, safe queued teardown, and topology reconstruction proofs.

### A4 — deferred operator-only compiled smoke

- [ ] After migration implementation is complete, and only when the operator explicitly schedules
  a build window, run the focused compiled smoke and retain the executable result.

During Phases C–G, keep build scripts, packaging inputs, and `build_runner.py` compatible and use
focused static/script tests, but do not initiate a compiled or full build.

Exit concept:

```text
threaded standalone Quick
+ inline GL render node
+ clean teardown
+ production-shaped lifecycle
+ compiled-smoke inputs ready
```

The explicit operator-run executable validation remains a final scheduled validation, not an
admission gate for Phases C–G.

---

# 5. Phase B — runtime-host decomposition

Phase B is considered structurally complete for forward migration.

Settled properties include:

- one `QuickDisplayRuntime` per selected physical display;
- per-runtime scene/window/pacer/input ownership;
- generation-scoped lifecycle;
- queued Qt/C++ meta-call teardown for `hide`, `releaseResources`, and `close`;
- no blocking Python close/release path that can invert the GIL against the render thread;
- hide/wake preserves the runtime where intended;
- coordinated exit is one-shot;
- runtime-root/window destruction barriers complete deterministically;
- topology replacement is proven through migration harnesses;
- unexpected QWindow screen displacement does **not** silently adopt the fallback screen;
- displacement quiesces presentation and emits one-shot topology/binding loss while preserving the
  runtime's original physical-display identity and pacer target.

Do not reopen Phase B merely because later phases exercise these owners.

Production `DisplayManager -> QuickDisplayRuntime` ownership still waits for Phase H.

---

# 6. Phase C — base image and all transitions

Read `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`.

Phase C guardrails that remain active through the renderer port:

- preserve the completed transition-neutral `TransitionRequest` / `TransitionRun` lifecycle,
  monotonic timing, generation/run fencing, and exactly-once completion/cancellation;
- resolve statically registered transition implementations lazily from lightweight canonical
  catalog metadata;
- keep disabled transitions Settings-visible but out of Random/Cycle selection and do not resolve
  their implementations, shaders, or transition-specific resources;
- keep transition-specific shader/math/resource behaviour in each implementation and out of the
  common host/controller;
- do not create a central per-transition dispatcher or a dynamic/external plugin system;
- retire user-selectable transition easing: each canonical descriptor owns the internal authored
  curve/timing authority;
- use linear timeline input for staged/physics/shader effects that already author their own timing;
- Slide uses `SINE_IN_OUT`;
- easing must never compensate for coverage or presentation-cadence defects;
- keep Slide to the four cardinal product directions and derive both image samples and their sole
  viewport owner from the same immutable eased progress in one draw;
- preserve the common GL-state fence: viewport, program, VAO/VBO bindings, active texture/bindings,
  blend, cull, depth enable/write/function/clear state, stencil, and any later state introduced by
  migrated effects must not leak into subsequent Quick scene rendering.

## C1/C2 — completed foundation

The Quick image boundary and transition-neutral run/controller work are already landed.

Presentation images crossing into render ownership are immutable/detached; live QPixmap/QWidget state
must not cross the render-thread boundary.

## C3 — renderer port

At reviewed checkpoint `9c09e862`, Quick implementations are landed for:

- [x] Crossfade
- [x] Slide
- [x] Wipe
- [x] Warp Dissolve
- [x] Block Puzzle Flip
- [x] 3D Block Spins

Remaining at that checkpoint:

- [ ] Blinds
- [ ] Diffuse
- [ ] Ripple / Raindrops
- [ ] Crumble
- [ ] Particle
- [ ] Burn
- [ ] any additional transition still active in the canonical registry when this phase is executed

Always inspect current HEAD before using the checklist; a later pushed checkpoint may have advanced it.

Reuse existing shader sources/program math wherever possible.

Commit/push in small transition batches; use one transition per checkpoint for visually complex
effects.

Do not tune transitions individually to compensate for presentation cadence.

Use deterministic captures/tests where practical, but do not mistake a weak pixel-change assertion
for proof of a visually authored effect.

### C3a — Slide contract

Quick Slide is cardinal only:

- left;
- right;
- up;
- down.

Both source and destination coverage must be derived from the same immutable sample so the viewport
has exactly one owner at every pixel. Missed presentation intervals may advance motion farther on the
next rendered frame but must never expose a seam/microgap.

Do not re-add diagonal Slide merely because the underlying renderer could draw it. A diagonal
full-frame translation creates exposed corner space unless a deliberately authored effect fills or
deforms that space.

### C3b — 3D Block Spins preservation contract

3D Block Spins is a real 3D transition, not a 2D narrowing approximation.

Preserve:

- one thin 36-vertex rectangular-prism slab;
- front/back/side geometry with thickness;
- depth-tested face ordering over an opaque black void;
- horizontal, vertical, and both diagonal rotation axes;
- correct spin sign for opposite directions;
- correct back-face UV orientation for each axis so the arriving image is upright rather than
  mirrored/rotated;
- authored cubic internal spin timing fed from the canonical linear outer run;
- dark side-face core;
- moving direction-sensitive specular band;
- edge-on white rim treatment;
- exact source/destination endpoints;
- context-local mesh/program ownership and render-thread teardown.

Do not add a flat-quad fallback.

### C3c — Burn preservation contract

Burn is a high-risk visual-preservation transition. Treat it as a BlockSpin-class authored effect,
even though it is implemented primarily as a full-screen shader.

The existing effect is not merely "a noisy wipe." Preserve its actual visual stack:

- exact old/new image endpoints;
- all currently supported burn directions, including the two diagonal directions;
- initial ignition phase before the front begins moving;
- domain-warped multi-octave noisy/jagged paper-like burn edge;
- authored jaggedness control;
- heat distortion close to the burn front;
- warm glow bleed into the old image;
- white-hot/thermite core line;
- char width and the hot-ember -> cooling ember -> dark char -> new-image progression;
- crackle/detail variation in the char zone;
- smouldering/pulsing glow;
- user/authored glow colour and glow intensity;
- sparks/embers when enabled;
- smoke wisps when enabled;
- falling ash when enabled;
- smoke/ash density controls;
- per-run seed behaviour;
- animated effect time;
- delayed near-completion tail fade that guarantees a clean final destination frame.

Prefer reusing/extracting the existing Burn shader source and authored math rather than rewriting the
look from memory.

Quick ownership may change; the effect's appearance contract may not be silently simplified.

Burn-specific gates should prove at least:

- implementation remains lazy/dormant while disabled;
- only Burn-specific implementation/resources resolve when enabled;
- required parameters are resolved before render admission rather than silently defaulted in the
  renderer;
- all supported directions map correctly;
- deterministic probes demonstrate distinct unburned / glow-core-char / destination regions at
  controlled progress;
- smoke/ash enablement genuinely changes their intended regions without changing core burn ownership;
- exact endpoints are clean;
- resource teardown leaves no Burn-specific GL ownership;
- common GL state is restored after Burn rendering.

Subjective eyes-on comparison against the authored old effect remains required later when the full
Quick runtime is convenient to inspect visually.

## Phase C exit gate

- all registry-eligible production transitions render through Quick;
- disabled transitions remain renderer/resource dormant;
- old/new image ownership is correct;
- completion/cancel/interruption correct;
- transition-specific authored parameters and visual contracts are preserved;
- 60 Hz/high-refresh pacing remains healthy;
- no old compositor dependency exists inside the new Quick renderer implementations;
- transition-authoring documentation can now be rewritten against the final contract.

---

# 7. Phase D — visualizer

Read:

- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- Bubble BTF/guardrail documentation.

## D1 — separate logical controller from QWidget presentation

Do not instantiate a hidden QWidget merely to host the Quick visualizer.

Extract/retain the non-pixel visualizer controller/state needed by:

- settings activation;
- playback state;
- logical runtime;
- source/BeatEngine;
- preset state;
- CUSTOM participation.

## D2 — immutable render snapshot

The old compositor layer's live-owner handle is not render-thread safe.

The Quick path uses immutable/current snapshots containing generation/activation identity, geometry,
fade/style, and mode-specific render data.

No render-thread reads from live QWidget/QObject presentation state.

## D3 — Quick visualizer render item

Render all five modes through the Quick render node using existing authored shaders/helpers where
practical.

Preserve:

- Spectrum;
- Oscilloscope;
- Sine;
- Bubble;
- DevCurve;
- ghosting;
- borders/masks;
- card geometry;
- fades;
- Pause/Play;
- paused Spectrum idle;
- BTF.

### Visualizer authored-clock guardrail

`VisualizerLogicalRuntime` remains the sole authored logical clock.

Preserve:

- every authored logical step;
- latest-state semantics;
- no FIFO/catch-up replay;
- no paint acknowledgement;
- no producer/display divisor;
- no source/event decimation;
- no display-refresh logical cap;
- no physical render cadence becoming simulation cadence;
- nonblocking GSMTC/media interaction;
- generation fencing/stale rejection;
- clean worker join;
- no separate visualizer native window;
- no QPainter fallback.

Bubble especially depends on continuous positional evolution. Do not "optimize" it by throwing away
authored steps.

Commit/push at the bridge, renderer foundation, and all-five-modes milestones.

Exit gate includes BTF and later real eyes-on validation.

After Phase D exits, update visualizer/preset authoring documentation against the landed contract.

---

# 8. Phase E — widget presentation foundation

Read `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`.

Do this before porting families.

## E1 — descriptor cleanup

Make canonical widget identity/settings metadata presentation-neutral.

Move QWidget-factory-only creation details out of the canonical descriptor authority rather than
teaching new Quick code to depend on QWidget factories.

## E2 — split WidgetManager ownership

Create/rename the future `WidgetRuntimeManager` around:

- provider/model lifecycle;
- visibility/enabled state;
- monitor participation;
- stacking inputs;
- live settings updates;
- fade intent;
- generation ownership.

Move pixel/QWidget operations out as families migrate.

Resolve only enabled families through the static family registry.

A disabled family must not own feature-specific runtime work merely because its files are installed.
Where solely owned by that family, disabled means no:

- model;
- provider/service/process;
- polling/timer;
- refresh callback;
- Quick component;
- family-specific presentation resource.

Shared infrastructure remains alive only when another enabled capability still requires it.

Do not create a giant `QuickBaseOverlayWidget` Python god object.

## E3 — shared retained Quick visual primitives

Build small reusable Quick components/primitives for:

- card background;
- border/radius;
- foreground opacity;
- card shadow;
- text/header shadow;
- image/artwork;
- separators;
- common text;
- fade/visibility;
- click targets.

## E4 — recovered eight-direction shadow feature

This is an active migration deliverable.

Add a global General-setting selector with:

```text
NW   N   NE
 W   ·    E
SW   S   SE
```

- eight selectable outer directions;
- selected/inset indication;
- default `SE`, matching current authored appearance;
- center is not a ninth shadow mode unless a separate product decision explicitly adds one.

Use one canonical presentation-neutral direction authority such as:

```text
nw, n, ne, w, e, sw, s, se
```

Do not keep the old ineffective `widgets.shadows.offset` as a competing authority.

Direction changes signs; they do not flatten each shadow family's authored magnitude:

```text
card (4, 6), SE -> (+4, +6)
card (4, 6), NW -> (-4, -6)
text (3, 3), N  -> ( 0, -3)
icon (3, 4), W  -> (-3,  0)
```

Preserve each family's authored magnitude, blur, spread, opacity and color.

Required coverage includes:

- cards;
- text;
- headers;
- icons/artwork;
- controls;
- volume slider;
- visualizer card;
- digital/analogue Clock details;
- Weather;
- Media;
- Reddit/Gmail;
- Steam families;
- multiple DPRs;
- CUSTOM geometry;
- no outer/content drift when direction alone changes.

Do not reintroduce QWidget `QGraphicsDropShadowEffect`.

Prefer bounded Quick/shader shadow primitives and keep effect topology stable during fades.

Exit gate:

- shared style represents current opacity/border/radius/shadow requirements;
- eight-direction selector drives every migrated shadow family correctly;
- default SE matches authored appearance;
- all signed directions have sufficient four-sided padding;
- no focus/menu/display corruption;
- no whole-screen effect layer for ordinary cards.

---

# 9. Phase F — widget families

Port runtime pixels, not Settings GUI/backends.

Each family is its own landed checkpoint unless tiny and inseparable.

## F0 — remove deprecated Imgur instead of porting it

Imgur is deprecated and not worth repairing.

Remove its live product surface end to end:

- dev/runtime gate;
- defaults/settings model and Settings controls;
- descriptor/factory/runtime widget;
- provider/direct-network fallback;
- CUSTOM payload/support;
- tests whose only purpose is keeping Imgur alive;
- build/package references;
- current-authority documentation references;
- Defaults Foundry option metadata that refers only to Imgur.

Do not build compatibility around stale persisted Imgur keys.

Recommended family order after that:

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
11. other deliberately supported canonical runtime families

Per family:

1. identify provider/model/business logic;
2. extract non-pixel logic trapped in QWidget;
3. expose a compact runtime model;
4. implement retained Quick presentation;
5. preserve current customization controls that remain part of the new product;
6. add/update deterministic model/presentation tests;
7. exercise CUSTOM geometry expectations;
8. run Quick widget gallery;
9. commit + push;
10. continue.

Do not create screenshot-to-texture wrappers of the old QWidget as the final implementation.

Do not rewrite provider/network logic into QML.

After Phase F exits, rewrite widget-authoring guidance against the final family/descriptor/model/Quick
presentation contract.

---

# 10. Phase G — CUSTOM, input, interaction and auxiliary runtime pixels

Read `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`.

## G1 — CUSTOM session

Refactor `CustomLayoutManager` into presentation-neutral session/state + Quick edit presentation.

Keep the useful layout math/behavior contract.

Preferred Quick edit behaviour:

- edit the real retained Quick widget item;
- maintain uncommitted session geometry separately from persisted settings;
- Save commits;
- Cancel restores session baseline;
- outline/handles/grid are separate Quick edit items;
- no duplicate raster snapshot shell for ordinary widgets.

For cross-monitor transfer, one presentation instance moves/recreates on the target scene; do not keep
simultaneous duplicate live pixel owners.

Do not spend migration effort translating pre-Quick saved widget/CUSTOM geometry. Phase H0 resets it.

## G2 — input

Refactor `InputHandler` away from `DisplayWidget` type assumptions.

Route QQuickWindow events into the same product actions.

Preserve:

- exit gestures;
- hotkeys;
- media keys;
- Ctrl interaction mode;
- layout slots as a new-schema feature;
- click behaviour;
- right-click context menu;
- Media Center behaviour.

## G3 — auxiliary pixels

Port:

- cursor halo;
- dimming;
- pixel shift scene transform/offset;
- error/fallback display where still product-required;
- edit grid/handles;
- any remaining runtime overlay pixel owner.

The existing QWidget context menu/settings dialog may remain if it is transient control UI, but it
must be decoupled from `DisplayWidget` parent assumptions and must not become an accelerated
presentation surface.

Commit/push each owner slice.

---

# 11. Phase H — settings epoch + production cutover

No production-owner cutover until the Quick migration harness has:

- base images;
- all active transitions;
- visualizer all modes;
- all runtime widget families;
- CUSTOM;
- input/context;
- dimming/pixel shift/halo;
- multi-display;
- lifecycle;
- build/packaging inputs ready for deferred compiled validation.

Compiled/installed product validation is not a cutover admission item unless the operator explicitly
schedules it.

## H0 — one-time Qt Quick settings epoch reset

The Qt Quick production cutover is also a deliberate settings-contract epoch change.

Backward compatibility with pre-Quick **presentation settings** is not a product requirement.

Do **not** accumulate a museum of per-feature migration functions for easing, widget geometry,
shadows, visualizer presentation state, CUSTOM coordinates, and every other old presentation leaf.

At H0, create one explicit settings schema/epoch boundary.

### H0.1 Preserve only a verified durable whitelist

Preserve the smallest inspected set whose meaning genuinely survives the migration.

The intended durable categories are:

- image/source configuration, including configured local source locations/selections and other
  source backend configuration still valid in the new product;
- credentials, tokens, secrets, account slots/identities and authentication data required by
  retained providers;
- provider/backend connection information whose schema is demonstrably presentation-neutral;
- other data only when inspection proves it is both durable and structurally unchanged.

The whitelist must be explicit in code/tests. Do not preserve an entire old subtree merely because it
contains one durable leaf.

### H0.2 Reset migration-sensitive state to final Qt Quick defaults

Everything else is reset to the then-current canonical Qt Quick defaults unless inspection proves it
belongs on the durable whitelist.

This deliberately includes, where present:

- transition selection;
- transition pools;
- transition durations/directions/parameters;
- removed transition easing state;
- widget enablement/presentation/style settings;
- widget positions;
- monitor routing where it is presentation state rather than account/source identity;
- widget dimensions;
- CUSTOM geometry;
- CUSTOM restore payloads;
- saved layout slots;
- presentation/display geometry assumptions;
- old shadow/effect settings;
- visualizer presentation settings;
- visualizer geometry;
- pre-Quick user-authored visualizer presentation presets/configuration when their schema is not
  deliberately retained;
- other QWidget/QRhiWidget/compositor-era presentation state.

Do not perform heroic coordinate conversion. If a geometry value belonged to the old presentation
space, reset it.

For visualizers, the required post-reset product baseline is:

- curated built-in presets remain valid;
- every visualizer mode still has its intended defaults/presets;
- users can edit visualizer settings;
- users can create/save new presets under the new schema.

Old user presentation presets do not need migration merely to avoid resetting them.

### H0.3 Epoch operation

Conceptually:

```text
pre-Quick settings detected
        ↓
read/copy durable whitelist
        ↓
construct fresh final Qt Quick defaults
        ↓
restore durable whitelist
        ↓
atomically persist new settings epoch/version
        ↓
future starts see current epoch and do nothing
```

The operation must be safe enough that an error cannot silently destroy the preserved
credentials/source configuration.

Use the normal ordered settings durability boundary rather than inventing a competing writer.

### H0.4 No permanent migration archaeology

Existing generic obsolete-key cleanup may remain while migration work is in flight.

After the epoch reset is established and legacy presentation is deleted:

- remove one-off migration code whose sole remaining purpose is understanding pre-Quick presentation
  keys;
- remove obsolete pre-Quick presentation keys from current defaults/schema/presets;
- remove old compatibility payloads that no supported product path requires;
- retain generic settings-normalization machinery only when it has an ongoing current-schema purpose.

The final settings implementation should understand the current Qt Quick schema, not every historical
presentation schema.

### H0.5 Gate

Before H1:

- prove a representative pre-Quick settings file resets exactly once;
- prove configured image/source data on the explicit whitelist survives;
- prove credentials/account/auth data on the explicit whitelist survives;
- prove migration-sensitive presentation state returns to current defaults;
- prove old widget/CUSTOM geometry does not leak into the new runtime;
- prove built-in visualizer presets/defaults remain usable after reset;
- prove a second startup does not reset the already-current settings;
- prove malformed/partial old presentation state cannot leak into current runtime state;
- prove persistence reaches the normal durability boundary.

**Checkpoint + push H0 before H1.**

## H1 — explicit production-owner switch

Make one production-owner switch:

```text
DisplayManager
    from DisplayWidget
    to QuickDisplayRuntime
```

Change callers to the real new API.

Do **not** preserve a `DisplayWidget` compatibility facade.

Do **not** keep a production flag to return to QRhiWidget.

Run focused + chunked tests. Do not initiate installed/compiled smoke unless explicitly scheduled by
the operator.

**Commit + push the cutover immediately when green.**

---

# 12. Phase I — immediate legacy removal

This is part of migration completion, not optional someday cleanup.

Use `Future_Cleanup.md` as the deletion ledger.

After production cutover is stable, remove in small proven batches:

- QRhiWidget physical presenter;
- `GLCompositorWidget` scheduling/presentation ownership;
- old GL RHI surface helpers with no remaining caller;
- compositor visualizer layer;
- old GUI `present_tick` paths;
- old QWidget runtime widget presentation classes once no settings/test owner requires them;
- old QWidget CUSTOM edit-shell/grid presentation if fully replaced;
- dead transition classes whose only purpose was `GLCompositorWidget`;
- obsolete effect/cache-busting presentation code;
- legacy transition presenter/factory consumers;
- per-feature pre-Quick presentation-setting migration helpers no longer required after H0;
- migration-only scaffolding.

Do not delete presentation-neutral authored shader/math assets merely because the old compositor also
used them. Shared authored effect assets may survive when the Quick implementation is their real
consumer.

For every deletion batch:

```text
rg/caller proof
-> focused tests
-> git commit
-> git push
-> continue
```

Do not leave both presenter architectures "for safety."

---

# 13. Phase J — final tooling, build, lifecycle, performance and beyond-parity close

Read `Docs/QtQuick_Migration/06_Build_Tooling_Validation.md`.

Compiled/full-build items below are operator scheduled after migration implementation is complete.
Reaching this phase alone does not authorize an agent to initiate them.

## J0 — retarget Defaults Foundry to the final Qt Quick settings/defaults schema

Defaults Foundry is an essential project tool and must remain usable after the migration.

Current tool:

```text
tools/default_settings_editor.py
```

It currently reads the canonical `DEFAULT_SETTINGS` Python literal directly using AST/literal
inspection, derives the editable tree recursively, writes the canonical Normal base and MC
differential, and regenerates snapshot/SST artifacts.

Do not accidentally strand it on pre-Quick schema assumptions.

After H0/H1/I have made the final settings/defaults shape clear:

- inspect whether `core/settings/default_settings.py` remains the canonical literal authority;
- if it remains authoritative, preserve the useful direct literal-reading design and update the
  Foundry for the final schema rather than rewriting its loader unnecessarily;
- if canonical default authority moved for a justified reason, retarget the Foundry explicitly;
- remove hard-coded option metadata for deleted settings/families such as Imgur;
- add/update finite-value metadata for new canonical settings such as the eight-direction shadow
  authority where appropriate;
- remove Foundry behavior whose only purpose was preserving retired pre-Quick compatibility payloads;
- make import filtering/preservation rules agree with the H0 durable-data policy and the final
  current-schema reset/import contracts;
- ensure new canonical settings appear in the recursive tree;
- ensure the Foundry does not inspect, migrate, or rewrite installed user settings merely because
  defaults are edited;
- regenerate:
  - defaults snapshot artifacts;
  - Normal SST defaults;
  - MC SST defaults;
- update defaults parity tests and `Docs/Defaults_Guide.md`.

The Foundry's standalone QWidget control UI does **not** need to be rewritten into Qt Quick merely
because the screensaver runtime migrated. Its required migration is schema/tooling correctness unless
a separate product/tooling decision explicitly chooses a UI rewrite.

Gate:

- Foundry loads the final canonical defaults without retired presentation debris;
- Save and Regenerate is transactional;
- MC remains a compact differential over Normal;
- generated JSON/SST artifacts exactly match canonical defaults APIs;
- two unchanged SST regeneration runs remain deterministic;
- no credential/private installation data leaks into checked-in defaults artifacts;
- Foundry can edit every intended current default leaf.

**Checkpoint + push the Foundry retarget before final documentation closure.**

## J1 — final validation

Required, when operator scheduled:

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
- PresentMon cadence check;
- external heavy-load resilience check;
- long-soak on final architecture.

Do not rerun the old manual worker heavy baseline.

Beyond-parity acceptance should show at least:

- no QWidget effect-cache shadow architecture;
- fewer presentation-specific GUI callbacks than the old path;
- no per-widget accelerated surfaces;
- retained Quick widgets do not repaint/rebuild stable content every physical frame;
- transition/visualizer renderer uses render-thread ownership cleanly;
- disabled transition/widget families have no feature-specific runtime/resource ownership;
- overloaded old presentation modules have been decomposed rather than renamed wholesale.

---

# 14. Documentation closure

When migration lands:

1. update `Spec.md`, `Index.md`, `Docs/Contracts.md`, architecture/guardrails to landed class/file
   names;
2. mark/remove completed migration decomposition docs according to
   `Docs/Documentation_Maintenance.md`;
3. retain P0 evidence;
4. update `Future_Cleanup.md` to contain only genuinely deferred debt;
5. ensure no current-authority doc calls QRhiWidget the production runtime owner;
6. make Quick transition/widget/visualizer authoring guides the sole current implementation authority;
7. update `Docs/Defaults_Guide.md` for the H0 settings epoch and final Defaults Foundry behavior;
8. remove current-authority instructions that tell agents to preserve deleted pre-Quick presentation
   keys/owners.

Migration is not complete while docs still teach agents to preserve dead presentation owners.

Historical evidence remains historical evidence; do not rewrite old bug records as though they were
authored under the new architecture.

---

# 15. Cross-links

Technical decompositions:

- `Docs/QtQuick_Migration/README.md`
- `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md`
- `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`
- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`
- `Docs/QtQuick_Migration/06_Build_Tooling_Validation.md`

Defaults/tooling:

- `Docs/Defaults_Guide.md`
- `tools/default_settings_editor.py`
- `tools/regenerate_defaults_snapshot_artifacts.py`
- `tools/regenerate_sst_defaults.py`

Deletion ledger:

- `Future_Cleanup.md`

Durable architecture/current-authority docs:

- `Spec.md`
- `Docs/Compositor_Architecture.md`
- `Docs/Guardrails.md`
