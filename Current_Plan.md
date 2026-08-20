# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-20

## Source / decision checkpoint

The documentation/decision checkpoint reviewed for this plan is:

```text
18c8f26756df83bd0d8828becc740c72d5526b21
4.7.2 - Pre-Quick Migration Docs v1
```

This SHA is an orientation anchor, **not** a required current HEAD.

Before active work:

1. inspect current `HEAD` and the working tree;
2. preserve unrelated user work;
3. inspect code changes after the anchor only far enough to update assumptions they actually invalidate;
4. never reset, clean, checkout, stash, or revert merely to manufacture equality with the anchor.

The Qt Quick architecture decision is closed by the P0 evidence. This plan replaces the old
"finish the architecture comparison" plan.

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

Keep:

- `ScreensaverEngine` orchestration except where display-runtime calls must change;
- image source/provider backends;
- SettingsManager and persistence;
- QWidget Settings UI;
- RSS/folder/media/GSMTC/provider logic;
- ProcessSupervisor / ThreadManager ownership where still appropriate;
- `VisualizerLogicalRuntime`;
- visualizer authored algorithms and mode personality;
- custom-layout persistence/math contracts;
- transition registry/settings identity;
- product features and customization.

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

During development, the old production runtime and the not-yet-active Quick implementation may
coexist in the repository. Only one is the normal production path at a time. Migration harnesses may
exercise the Quick path before cutover.

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

Do **not** use the migration as permission to refactor unrelated source/provider/settings/backend
systems.

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
Slide port
transition family batch
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
production cutover
legacy deletion batch
build/tooling closure
```

Do not pause after a successful checkpoint to ask permission to continue.

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
- matches the "one physical surface" target;
- PySide exposes `QSGRenderNode`;
- the P0 benchmark already proved Python render-thread OpenGL inside `QQuickWindow`.

**First code slice must prove this primitive** with pinned PySide 6.9.1, script mode, two real displays
when available, and an early compiled smoke.

If this primitive itself is an actual binding/runtime blocker, stop and revise the **single chosen
Quick custom-render primitive** before migrating transitions/widgets. Do not keep two product
primitives as fallbacks.

## 3.3 Presentation pacing

Extract a production presentation-only frame pacer from the proven P0 target-pacing semantics.

Properties:

- one pacer per display;
- target based on that display's refresh;
- starts only while custom dynamic content requires continuous presentation;
- transition and visible visualizer are independent frame-demand reasons;
- missed deadlines are skipped, not replayed;
- no `afterRendering -> update()` self-loop;
- no paint acknowledgement;
- no logical visualizer cadence ownership.

Retained Quick animations may dirty the scene normally; the custom GL pacer exists for the
transition/visualizer content that needs continuous render opportunities.

---

# 4. Phase A — bootstrap and render-node proof

Read:

- `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md`
- `Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`
- `Docs/QtQuick_Migration/06_Build_Tooling_Validation.md`

Land in small commits:

### A4 — operator-scheduled compiled smoke

- [ ] When the operator explicitly schedules a build window, run
  `scripts/build_qtquick_smoke.ps1 -Run` and retain the executable result.

Do not launch the full build autonomously. This external validation does not block continued
migration implementation; a failure reopens only the focused A4 packaging/runtime issue.

Exit gate:

```text
threaded standalone Quick + inline GL render node + clean teardown + compiled-smoke inputs accepted
```

The explicit operator-run executable validation remains required before production cutover.

---

# 5. Phase B — runtime-host decomposition

Read `01_Runtime_Host_Lifecycle.md`.

Refactor without a compatibility facade.

`DisplayManager` continues to own topology, but the future display type becomes `QuickDisplayRuntime`,
not a QWidget-shaped adapter.

Keep engine/provider/settings behaviour unchanged.

Prove in a migration harness:

- topology recreate.

**Checkpoint after each meaningful owner extraction. Push each checkpoint.**

---

# 6. Phase C — base image and all transitions

Read `02_Scene_Renderer_Transitions.md`.

## C1 — image boundary

Refactor presentation image state so render-thread code consumes immutable image bytes/state, never
live `QPixmap`/QWidget state.

Do not rewrite source/image queue/provider logic.

## C2 — transition-neutral run controller

Refactor QWidget/compositor coupling out of transition timing/parameter ownership.

Preserve:

- registry identity;
- random/cycle participation;
- duration;
- easing;
- direction;
- transition-specific authored parameters;
- exactly-once completion.

## C3 — renderer port

Reuse existing shader sources/program math wherever possible.

Port and prove every active compositor transition:

- Crossfade;
- Slide;
- Wipe;
- Warp;
- BlockFlip;
- BlockSpin;
- Blinds;
- Diffuse;
- Raindrops;
- Crumble;
- Particle;
- Burn;
- any additional transition still active in the canonical registry when this phase is executed.

Do not tune transitions individually to compensate for presentation cadence.

Use per-transition deterministic captures/tests where available.

Commit/push in small transition batches, not all at once.

Exit gate:

- all registry-eligible production transitions render through Quick;
- old and new image ownership is correct;
- completion/cancel/interruption correct;
- 60 Hz/high-refresh pacing healthy;
- no old compositor dependency inside the new renderer.

---

# 7. Phase D — visualizer

Read:

- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- BTF for Bubble.

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

The current compositor layer's live-owner handle is not render-thread safe.

Replace the Quick path with an immutable/current snapshot containing generation/activation identity,
geometry, fade/style, and mode-specific render data.

No render-thread reads from live QWidget/QObject presentation state.

## D3 — Quick visualizer render item

Render all five modes through the Quick render node using existing mode shaders/helpers where
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

Commit/push at the bridge, renderer foundation, and all-five-modes milestones.

Exit gate includes BTF and real installed eyes-on.

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

Do not create a giant "QuickBaseOverlayWidget" Python god object.

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

## E4 — land the recovered eight-direction shadow feature

This is an **active migration deliverable**, not Future Cleanup.

The abandoned 4.6.9 General-settings feature is restored here because the Quick style/shadow
unification removes the architectural reason it previously stalled.

Add a global General-setting selector with the intended UX:

```text
NW   N   NE
 W   ·    E
SW   S   SE
```

- eight selectable outer directions;
- inset/pressed indication for the selected direction;
- default `SE`, matching current authored appearance;
- center is not a ninth shadow mode unless a separate product decision explicitly adds one.

Use one canonical presentation-neutral direction authority, preferably a `ShadowDirection` enum/token
(`nw`, `n`, `ne`, `w`, `e`, `sw`, `s`, `se`).

Do **not** keep the currently ineffective `widgets.shadows.offset` as a competing legacy authority.
During this slice, migrate/remove that unused setting cleanly rather than adding compatibility glue.

Resolve direction as signs applied to each shadow class's existing authored magnitude:

```text
card magnitude (4, 6), SE -> (+4, +6)
card magnitude (4, 6), NW -> (-4, -6)
text magnitude (3, 3), N  -> ( 0, -3)
icon magnitude (3, 4), W  -> (-3,  0)
```

Changing direction must **not** flatten per-shadow tuning. Preserve the distinct card/text/header/
icon/control/volume/visualizer magnitudes, blur, spread, opacity and color.

The unified Quick shadow primitives must support signed offsets and sufficient four-sided visual
padding so top/left directions cannot clip.

Required coverage:

- all eight directions + default SE;
- cards;
- text;
- headers;
- icons/artwork;
- controls;
- volume slider;
- visualizer card;
- digital and analogue Clock shadow details;
- Weather;
- Media;
- Reddit/Gmail;
- Steam families;
- multiple DPRs;
- CUSTOM geometry;
- no content/outer-rect drift when only direction changes.

The General selector should be implemented only after the shared Quick shadow primitives can actually
honour it; do not ship a UI control that only updates settings.

**Checkpoint + push the unified direction authority, then checkpoint + push the General UI once the
runtime gallery proves it.**

### Shadow-specific rule

The old multi-monitor corruption was associated with QWidget `QGraphicsDropShadowEffect` /
effect-cache behaviour and was fixed by painter-owned shadows.

Do not reintroduce `QGraphicsEffect`.

For Qt Quick:

- prefer a dedicated rectangular/card shadow shader/item for rounded cards so the shadow does not
  require a general blurred source texture;
- use `MultiEffect` only where an arbitrary-shaped source genuinely requires it and only on tightly
  bounded source items;
- text/header shadows may use a small dedicated effect or equivalent retained representation;
- never toggle effect topology repeatedly during fade; fade the owning item/parent opacity instead;
- explicitly test the old corruption triggers.

Exit gate:

- shared style can represent all current shadow/opacity/border/radius requirements;
- the eight-direction General selector drives every migrated shadow family correctly;
- default SE is visually equivalent to the current authored direction;
- all signed directions have correct four-sided padding and no clipping;
- no focus/menu/display corruption in the Quick gallery stress;
- no whole-screen effect layer for ordinary cards.

---

# 9. Phase F — widget families

Port runtime pixels, not the settings GUI/backends.

Each family is its own landed checkpoint unless very small and inseparable.

## F0 — remove deprecated Imgur instead of porting it

A prior cleanup decision explicitly classified Imgur as deprecated and not worth repairing. Do not
spend Qt Quick migration work recreating it.

Remove its live product surface end to end at this point (or earlier if descriptor work naturally
makes it cleaner):

- dev/runtime gate;
- defaults/settings model and Settings controls;
- descriptor/factory/runtime widget;
- provider/direct-network fallback;
- CUSTOM payload/support;
- tests whose only purpose is keeping Imgur alive;
- build/package references;
- current documentation references.

Unknown stale persisted Imgur keys may be ignored/stripped by the normal settings cleanup path; do
not build a compatibility widget or fallback provider.

**Checkpoint + push the Imgur removal.**

Recommended port order after that:

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
11. other enabled development widget families still deliberately supported by the canonical runtime

Per family:

1. identify current provider/model/business logic;
2. extract any non-pixel logic trapped in the QWidget class;
3. expose a compact runtime model;
4. implement the retained Quick presentation;
5. preserve every current customization control;
6. add/update deterministic model and presentation tests;
7. exercise CUSTOM geometry expectations;
8. run the Quick widget gallery;
9. commit + push;
10. continue.

Do not create screenshot-to-texture wrappers of the old QWidget as the final implementation.

Do not rewrite provider/network logic into QML.

---

# 10. Phase G — CUSTOM, input, interaction and auxiliary runtime pixels

Read `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`.

## G1 — CUSTOM session

Refactor `CustomLayoutManager` into presentation-neutral session/state + Quick edit presentation.

Keep `custom_layout_contract.py` math/persistence.

Preferred Quick edit behaviour:

- edit the real retained Quick widget item;
- maintain uncommitted session geometry separately from persisted settings;
- Save commits;
- Cancel restores baseline;
- outline/handles/grid are separate Quick edit items;
- no duplicate raster snapshot shell for ordinary widgets.

For cross-monitor transfer, one presentation instance moves/recreates on the target scene; do not keep
simultaneous duplicate live pixel owners.

## G2 — input

Refactor `InputHandler` away from `DisplayWidget` type assumptions.

Route QQuickWindow events into the same product actions.

Preserve:

- exit gestures;
- hotkeys;
- media keys;
- Ctrl interaction mode;
- layout slots;
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

The existing QWidget context menu/settings dialog may remain if they are transient control UI, but
must be decoupled from `DisplayWidget` parent assumptions and must not become an accelerated
presentation surface.

Commit/push each owner slice.

---

# 11. Phase H — production cutover

No cutover until the Quick migration harness has:

- base images;
- all active transitions;
- visualizer all modes;
- all runtime widget families;
- CUSTOM;
- input/context;
- dimming/pixel shift/halo;
- multi-display;
- lifecycle;
- early compiled smoke.

Then make one explicit production-owner switch:

```text
DisplayManager
    from DisplayWidget
    to QuickDisplayRuntime
```

Change callers to the real new API.

Do **not** preserve a `DisplayWidget` compatibility facade.

Do **not** keep a production flag to return to QRhiWidget.

Run focused + chunked tests and an installed smoke.

**Commit + push the cutover immediately when green.**

---

# 12. Phase I — immediate legacy removal

This is part of migration completion, not an optional someday cleanup.

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
- migration-only scaffolding.

For every deletion batch:

```text
rg caller proof
-> focused tests
-> git commit
-> git push
-> continue
```

Do not leave both presenter architectures "for safety."

---

# 13. Phase J — final build, lifecycle, performance and beyond-parity close

Read `06_Build_Tooling_Validation.md`.

Required:

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
5. ensure no current-authority doc calls QRhiWidget the production runtime owner.

Migration is not complete while the docs still teach agents to preserve dead presentation owners.

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

Deletion ledger:

- `Future_Cleanup.md`

Durable architecture:

- `Spec.md`
- `Docs/Compositor_Architecture.md`
- `Docs/Guardrails.md`
