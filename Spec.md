# SRPSS Specification

Last updated: 2026-08-24

Canonical durable architecture and product-behaviour contracts for SRPSS.

`Current_Plan.md` owns active sequencing and may retain compact, clearly marked completion rationale
when that protects migration continuity. Evidence reports own volatile measurements. Exact current
source remains implementation truth while a migration is in progress, but the accepted architecture
decision below is the design target and must not be reopened without new contradictory evidence.

## 1. Product priorities

1. visualizer fidelity/reactivity;
2. lifecycle and resource safety;
3. frame pacing / perceived continuity;
4. correct multi-display behaviour;
5. bounded resources;
6. CPU/task efficiency;
7. average FPS;
8. elegance.

Never improve counters by lowering authored visualizer cadence, transition quality, image quality,
overlay behaviour, or supported display topology.

Explicitly retired pre-Quick presentation controls are not fidelity requirements. In particular, the
old per-mode visualizer card-height/growth controls are not part of the Qt Quick destination contract.

## 2. Accepted presentation architecture

The accepted destination architecture is:

```text
Python / QWidget application shell
        |
        +-- Settings / persistence / providers / media / orchestration
        |
        +-- logical runtimes and models
                 |
                 v
        immutable/latest render state
                 |
        one standalone QQuickWindow per physical display
        with Qt Quick threaded scene-graph rendering
                 |
                 v
        OS physical presentation
```

This is a **runtime presentation migration**, not a wholesale QML rewrite.

Durable rules:

- one independently presented accelerated top-level runtime surface per physical display;
- the runtime presentation owner is standalone `QQuickWindow`, not `QQuickWidget`;
- the Qt Quick threaded scene-graph render loop is required on the supported Windows path;
- Settings/configuration UI may remain QWidget-based;
- providers, persistence, GSMTC/media integration, logical runtimes, orchestration, and data models
  remain Python unless a separate measured reason justifies changing them;
- runtime overlay **presentation** moves into the one Quick scene where required;
- overlay/provider/model logic does not automatically migrate to QML;
- visualizer content and any optional visualizer shell/chrome are composed inside that same Quick
  scene;
- a visualizer card is a presentation policy, not a universal requirement of every possible
  visualizer mode;
- no second independently presented accelerated visualizer/overlay surface.

### Migration-epoch rule

Until cutover is complete, current `main` may still contain the QRhiWidget reference presenter.
That makes it the current implementation, not the accepted long-term design.

The QRhiWidget/GLCompositor/`DisplayWidget` runtime-presentation path is therefore
**CURRENT-LEGACY — WILL BE OBSOLETE at Phase H/I** once caller/cutover proof permits deletion.

Do not deepen the QRhiWidget path merely because it still exists during migration.

Do not remove the old presenter until the replacement has passed the required fidelity, lifecycle,
startup, multi-display, and resource gates.

## 3. Native/C++ boundary

A native/C++ physical-presenter migration is **not planned**.

The Qt Quick P0 experiment materially improved presentation cadence while still using Python/PySide
and existing representative OpenGL work. Therefore the evidence does not justify treating Python or
the GIL as a fundamental reason to replace the accepted Quick presenter.

Native code remains permissible only as a **localized measured implementation optimization** inside
the accepted Quick architecture, for example a specific render node or renderer whose Python cost is
proven material.

Do not plan:

```text
QRhiWidget -> Qt Quick -> second native-window/C++ presenter migration
```

If native code is ever earned, preserve the one-`QQuickWindow`-per-display presentation topology.

## 4. Runtime topology and ownership

- `ScreensaverEngine` owns high-level runtime sequencing.
- `DisplayManager` owns active-display/topology decisions.
- every physical display owns one runtime presentation window;
- display 0 is never implicit global geometry/DPR/presentation authority;
- presentation-neutral widget services/models may be extracted from legacy pixel owners during
  migration; `WidgetRuntimeManager` is the current per-display owner seam, while provider/backend
  cardinality still follows the actual family semantics rather than presentation count;
- Settings/Edit/topology recreation use ordered generations/lifetimes;
- visualizer audio analysis, logical simulation, render-state publication, shell policy, geometry,
  content clipping, and physical presentation remain separate concerns.

## 5. Visualizer logical contract

`VisualizerLogicalRuntime` remains the sole mode-general authored visualizer clock.

It:

- runs independently of Qt GUI event-loop timing;
- owns monotonic authored deadlines/dt;
- integrates all five modes;
- consumes source snapshots;
- publishes latest plain-data logical state;
- does not mutate QWidget/QPixmap/QPainter/Quick scene objects/GL resources;
- stops and joins with its runtime generation;
- skips genuinely missed deadlines rather than replaying backlog.

Do not restore:

- GUI recurring timer as simulation owner;
- `AnimationManager` as simulation owner;
- per-mode logical clocks;
- FIFO/catch-up replay;
- paint/present acknowledgement;
- source/event decimation.

For Bubble timing and feel, `Docs/Guardrails/Bubble_Temporal_Fidelity.md` remains binding.

Visualizer viewport metrics may enter the logical side only as committed geometry/configuration where
a mode needs spatial bounds. Geometry changes are never another authored clock.

## 6. Logical-to-presentation contract

Producers integrate authored work first, then publish current state.

The presentation side samples the freshest valid state for the current runtime generation.

Allowed:

```text
logical state N published
logical state N+1 supersedes N before presentation consumes
presenter consumes N+1
```

Forbidden:

- producer waits for paint/present;
- paint completion releases producer admission;
- one queued callback per logical tick as a required contract;
- FIFO render queues;
- catch-up bursts;
- display-rate division of authored logical cadence.

The exact bridge from Python state into Quick scene/render state is implementation-owned by the
migration plan, but it must remain bounded, latest-state-oriented, generation-fenced, and free of
paint acknowledgement.

## 7. Quick scene / renderer contract

The one Quick window may contain:

- retained base image;
- active transition;
- visualizer content;
- optional retained visualizer shell/chrome;
- runtime overlay presentation;
- other explicitly scene-owned layers.

The custom-GL primitive was selected and proved during the Qt Quick foundation work:

```text
QQuickItem(ItemHasContents)
    -> updatePaintNode()
    -> QSGRenderNode
    -> direct OpenGL inside the owning Quick scene
```

Use ordinary retained Quick items/components for normal UI/widget/card presentation.
Use the inline `QSGRenderNode` boundary for custom OpenGL transition/visualizer rendering that needs
existing shader/math/mesh ownership.

`QQuickRhiItem` is not the accepted normal custom-render path for SRPSS because it introduces an
offscreen texture/composite layer that this migration is deliberately avoiding. `QQuickWidget` is
prohibited as the runtime presenter.

If the selected `QSGRenderNode` primitive itself is proven fundamentally unusable by the pinned
PySide/compiled product, stop and revise the **single** custom-render primitive deliberately. Do not
ship two competing custom-render architectures or a per-effect fallback.

No transparent accelerated child/top-level window may be used to avoid integrating pixels into the
one runtime scene.

### 7.1 Visualizer shell and clipping policy

Visualizer presentation policy is resolved before render-thread admission.

All five current production modes use:

```text
shell_policy = CARD
clip_policy  = CARD_INTERIOR
```

A future explicitly authored mode may use:

```text
shell_policy = FRAMELESS
clip_policy  = VIEWPORT_RECT
```

`FRAMELESS` removes visualizer card background/frame/shadow only. It does not create a second native
window, second accelerated surface, second lifecycle owner, or permission to draw outside the
assigned visualizer viewport.

For carded modes, custom GL content remains above card fill, below the visible frame/border, and
inside the rounded inner card path.

Destination clip ownership is **one render-node-local SDF/stencil host** inside the same `QQuickWindow`
/ `QSGRenderNode`. The `QSGClipNode -> QSGRenderNode` handoff was attempted and failed its pinned
PySide 6.9.1 bar (rounded cases exposed stencil metadata not matching framebuffer contents; rectangular
cases could expose an invalid sentinel scissor). That failed handoff is not a selectable implementation
and is not a fallback unless new contradictory evidence later justifies reopening it. The local host
composes with valid inherited scissor/stencil state that genuinely corresponds to real framebuffer
contents, must not clear or repurpose accumulated clip state as though it owned the framebuffer, and
restores the temporary stencil contents and every touched direct-GL state.

Do not shrink authored visualizer content to simulate clipping. Do not copy old centred-QPainter
border/mask constants into the Quick geometry contract.

### 7.2 Visualizer geometry contract

All five current production modes share one canonical baseline visualizer viewport aspect ratio.

Mode changes and visualizer preset changes do not change that baseline viewport shape.

The pre-Quick per-mode card-height/growth controls are explicitly retired from destination ownership:

```text
spectrum_growth
osc_growth
sine_wave_growth
bubble_growth
devcurve_growth
```

They must not become Quick runtime/controller state, immutable render-state fields, mode-descriptor
geometry, or new visualizer preset-authoring controls.

Destination geometry distinguishes:

```text
canonical baseline viewport/aspect
uniform_visual_scale
viewport_extent
```

Whole-size operations preserve the canonical baseline aspect:

```text
scroll-wheel resize
    -> uniform whole-visualizer scale

corner-handle resize
    -> uniform whole-visualizer scale
```

The later explicit viewport-playroom operation may change one axis while preserving visual scale:

```text
left/right edge-handle resize
    -> viewport width only

top/bottom edge-handle resize
    -> viewport height only
```

Viewport extent changes available mode world/layout. It is not post-render texture stretching and may
not anisotropically distort Bubble circles/velocities, line stroke scale, or future 3D geometry.

A current mode that cannot safely support independent viewport extent without fidelity/BTF damage may
remain viewport-resize-incapable while retaining ordinary uniform whole-size scaling.

## 8. Readiness and reveal

At minimum distinguish:

```text
presentation_ready
reactive_source_ready
```

Presentation readiness covers the current runtime window/scene/resources/geometry needed to show an
intentional frame.

Reactive-source readiness covers current authoritative source identity/data.

A presentation-owned idle scene may reveal without fabricating reactive source identity.

Paused Spectrum is the canonical case.

Readiness depends only on resources required by the resolved presentation policy. A frameless mode
does not wait for card resources it deliberately does not own.

Startup/recreation must eventually preserve:

- no white/default window flash;
- no black placeholder frame;
- no stale texture/content pop;
- no visualizer/shell flash;
- coordinated multi-display reveal;
- intentional first visible content.

## 9. Generation / lifecycle contract

Settings, Edit, topology replacement, and exit retire old generation before replacement can publish.

Required shape:

1. close old-generation admission;
2. stop/cancel generation-owned producers and delayed work;
3. join `VisualizerLogicalRuntime`;
4. reject/clear stale state;
5. retire render resources on their legal owner/thread;
6. destroy retired runtime presentation roots and cross the destruction barrier;
7. construct/register replacement;
8. prepare intentional first content;
9. reveal current-generation content only.

Generation `0` is valid identity. Do not use truthiness conversions that turn valid zero into an
invalid sentinel.

## 10. GPU/resource ownership

Qt owns the runtime window and Qt Quick scene-graph graphics infrastructure.

SRPSS-owned GPU resources must have:

- one explicit owner;
- legal creation/use/destruction on the required render/context owner;
- generation-scoped lifetime;
- failed deletion retaining ownership/failing closed;
- accounting released only after actual ownership is released.

Do not carry QRhiWidget-specific borrowed-context rules forward as universal Quick rules. The
selected inline `QSGRenderNode` contract defines the custom GL render/context seam.

No `glFinish()`, `DwmFlush()`, GUI sleeps, nested event pumping, or fence polling as cadence repairs.

## 11. Widgets and runtime overlays

Widget provider/model/settings logic is not required to migrate merely because runtime pixels do.

During the migration, an admitted presentation-neutral service may be owned through
`WidgetRuntimeManager` while a QWidget remains only a temporary presentation consumer. A service is
not a thread: detached work continues through `ThreadManager`, and retired/superseded results must be
fenced before commit.

During the migration, separate:

```text
widget data/model/provider authority
from
runtime pixel/presentation authority
```

The accepted destination is that runtime pixels which coexist over the screensaver scene are
composed inside the one Quick window.

Settings controls may remain QWidget.

CUSTOM/Edit control UI may remain QWidget where appropriate, but it must not create a competing
accelerated runtime presentation surface or a second live pixel authority.

Visualizer CUSTOM geometry uses the same committed geometry authority as runtime presentation.
Ordinary scroll/corner resizing changes uniform whole-size scale; later edge-only viewport resizing,
where supported, changes viewport extent rather than stretching rendered pixels.

## 12. Performance contract

Physical presentation quality is judged by:

- visible continuity;
- physical p95/p99/max gaps;
- severe-gap frequency;
- load resilience;
- run-to-run variance;
- correct refresh behaviour per display.

Average FPS is secondary.

Internal Qt render/submission callbacks are not proof that frames reached physical display.
OS/display-boundary evidence such as PresentMon is used when physical-delivery attribution matters.

The accepted Qt Quick architecture decision is grounded in the 2026-08-20 P0 comparison. Do not
reopen the architecture choice because one later local optimization opportunity exists.

## 13. Validation

Tests are necessary but insufficient for:

- visualizer feel;
- presentation continuity;
- startup/reveal;
- multi-display behaviour;
- lifecycle;
- resource behaviour.

Migration gates must include focused automation plus runtime-shaped Windows validation and manual
visual review where perception is part of the requirement.

A gate must be structurally capable of failing on the defect it claims to guard.

Visualizer architecture validation must include the current carded rounded-clip path, one frameless
policy scene proof, canonical baseline-aspect invariance, and no anisotropic stretching under
wide/tall viewport compatibility probes.

## 14. Documentation authority

- `Current_Plan.md`: active migration execution + compact clearly marked closure/rationale where useful;
- this file + Guardrails/focused docs: durable contracts;
- `Index.md` / `Docs/Contracts.md`: current routing and migration owner map;
- `Docs/TestSuite.md`: canonical test inventory/retirement ledger + testing strategy;
- current evidence reports: measurements and checkpoint evidence;
- phase reports / Historical_Bugs / Historical_Plans: historical evidence only;
- `Future_Cleanup.md`: deferred debt/deletion only;
- `Future_Work.md`: explicitly deferred feature/experiment work only.

Old evidence may describe QOpenGLWidget, QRhiWidget, separate overlays, GUI-timer cadence, or
per-mode visualizer card-height controls.

Those are historical mechanisms, not current design targets.
