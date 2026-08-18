# Spec

Last updated: 2026-08-18

Canonical stable architecture and product-behaviour contracts for SRPSS. Active sequencing
belongs in `Current_Plan.md`; benchmark narratives belong in phase reports.

## 1. Product Intent And Priority

SRPSS provides smooth multi-display image presentation, responsive/high-fidelity visualizers,
configurable overlays, durable settings and bounded/diagnosable resource use.

Priority order is: visualizer fidelity/reactivity; lifecycle/GL safety; frame pacing; correct
multi-display behaviour; bounded resources; CPU/task efficiency; average FPS; elegance.

## 2. Runtime Topology

- `ScreensaverEngine` owns high-level runtime sequencing.
- `DisplayManager` owns active display instances and authoritative topology decisions.
- Every active physical display owns its own `DisplayWidget` and one accelerated presentation
  surface.
- Display 0 is never implicit global geometry/DPR/presentation authority.
- `WidgetManager` owns ordinary overlay-widget lifecycle.
- Image preparation, visualizer logical state and accelerated presentation are separate owners.
- Settings/Edit/topology recreation use ordered runtime lifetimes/generations.

## 3. Stable Ownership Rules

- one mutable concern has one authority;
- generations represent real lifetime/activation boundaries, not ordinary frames;
- cross-thread payloads are immutable or explicitly synchronized;
- ResourceManager/accounting never substitutes for the context/resource deletion owner;
- historical implementation shapes are not compatibility requirements;
- fallbacks that change quality/owner/display/render path are loud.

## 4. Accelerated Presentation Contract

### 4.1 Hardware acceleration

The modern compositor/visualizer runtime requires hardware acceleration. A CPU/QPainter
visualizer replacement is not a supported compatibility contract.

### 4.2 One surface per display

Each display owns one `GLCompositorWidget`, implemented as
`ExternalOpenGLRhiWidget` / `QRhiWidget.Api.OpenGL`.

The top-level OpenGL QRhi owns the presenting context/swapchain. SRPSS uses existing PyOpenGL
renderers inside QRhi external-content rendering; it does not call `swapBuffers()` itself.

The display scene may contain:

- retained base image;
- active image transition;
- visualizer card layer;
- visualizer shader layer;
- other compositor-owned GL scene elements.

Ordinary Qt widgets may remain above the compositor when they are genuinely separate UI.
There is no independently presented Spotify visualizer `QOpenGLWidget`/`QRhiWidget`.

### 4.3 No-vsync policy

SRPSS intentionally requests no-vsync for its own timer/display-refresh pacing. The global
pre-QApplication surface-format policy remains part of that contract. Do not introduce a
second child-surface swap policy or SRPSS-owned swap call.

### 4.4 Producer/consumer relationship

Logical/state producers publish current state and return. Physical presentation consumes the
latest valid state for the current runtime/context/activation generation.

A missed paint may skip intermediate render snapshots after logical integration. It may not:

- drop source/events before integration;
- change simulation dt;
- pause a producer until paint;
- request catch-up replay;
- acknowledge paint/swap back to the producer.

### 4.5 Physical presentation cadence

Each display has one physical presentation strategy. It may target the display refresh rate and
remain live for multiple display-local reasons (for example transition-active and
visualizer-active).

That strategy is not a visualizer simulation clock.

A cross-thread queued-callback guard may coalesce duplicate Python GUI dispatch **only until the
queued callback executes and calls `QWidget.update()`**. Paint completion is never presentation
admission. Qt is allowed to merge repeated `update()` requests.

Render callbacks do not self-schedule a second loop.

## 5. Visualizer Contract

- supported mode behaviour remains authored/mode-owned;
- source/audio analysis and logical visualizer ticks are independent of compositor paint;
- all logical inputs integrate before any presentation coalescing;
- Bubble/Spectrum/line-mode temporal personality, discrete edges, smoothing and source freshness
  are protected;
- the compositor samples already-integrated current render state;
- `SpotifyBarsGLOverlay` is a logical state/geometry/visualizer-GL-resource owner, not a surface;
- actual visualizer pixels are rendered by the display compositor visualizer layer;
- no fake QPainter/CPU visualizer fallback exists;
- one activation resolves one authoritative target payload/final engine generation; stale
  generation/activation state cannot reveal;
- analysis freshness uses bounded latest-state semantics rather than a backlog/catch-up queue;
- card geometry/DPR/origin is one authoritative per-frame presentation geometry.

### Reveal/fade

The visualizer may remain hidden while audio/GL/card/current-generation readiness is established.
The single-surface compositor owns the pixels from fade zero through fade completion. A hidden
logical QWidget/QGraphicsOpacityEffect is not allowed to become a competing presentation owner.

The visualizer starts visible fade only when current-generation renderer/card resources and the
required fresh authoritative logical source are ready. Delayed frames sample current animation
progress; they do not flash to full opacity.

## 6. GL / QRhi Lifecycle

- Qt owns the QRhi and its OpenGL context; SRPSS borrows them.
- SRPSS never destroys the borrowed context and never calls `doneCurrent()` as its owner.
- GL creation/deletion happens on the owner GUI thread with the expected borrowed context current.
- one numeric GL handle has one deletion owner;
- ResourceManager releases accounting only after successful owner deletion;
- failed deletion retains ownership and fails closed;
- ordinary target resize does not rebuild immutable GL resources;
- a true QRhi/context generation change releases old resources before new-generation init;
- `releaseResources()` and explicit runtime cleanup converge on the same ownership rules;
- correctness never depends on optional warmup;
- no `glFinish()`, `DwmFlush()`, fence polling, GUI sleep or nested event pumping is introduced as
  a performance/lifecycle repair.

Main-compositor QPainter remains a base-image fallback/capability path. Unexpected fallback after
an established healthy shader path must be state-loud and bounded. This does not authorize a
visualizer QPainter renderer.

## 7. Runtime Teardown / Recreation

Settings, Edit, topology replacement and exit retire the old runtime generation before a new one
can publish.

Required shape:

1. close old-generation admission;
2. stop/cancel producers and delayed GUI work;
3. reject stale worker/GUI publications;
4. delete owned GL resources on correct context;
5. destroy retired Qt roots and pass the destruction barrier;
6. construct/register the replacement against one authoritative topology/runtime generation;
7. reveal only current-generation authoritative content.

Hide-only reuse, deletion by garbage collection, cleanup retries, force-clearing handles and
constructing replacement before retired ownership reaches zero are not stable architecture.

Monitor sleep/wake topology settlement/rebuild details remain owned by active P5 work while that
work is unfinished.

## 8. CPU / Threading

- ThreadManager owns application async work; it is not a visualizer simulation or display clock.
- GUI/QPixmap/GL mutation remains on the correct GUI/context owner.
- workers perform coarse I/O/preparation/measured computation and publish detached data.
- no per-frame general COMPUTE task is introduced merely to move presentation work off GUI;
- no busy-spin timing;
- no source/event decimation or terminal-only batching that changes authored visual behaviour;
- a reactive compute lane is bounded and latest-freshness oriented, never an unbounded FIFO.

## 9. Image / Memory / GPU Resources

- CPU image caches and GPU texture/PBO stores are byte-accounted and bounded;
- context-local GL objects remain context-local unless an explicit lease/share contract exists;
- workers do not create QPixmap or call GL;
- retained destination texture is used directly for terminal/base presentation when valid;
- transition completion/cancel releases pins/temp ownership;
- normal cycling and repeated lifecycle use must reach a stable plateau;
- driver-reported VRAM remains real-platform evidence, not deterministic unit-test truth.

## 10. Settings / Persistence

- SettingsManager owns normalization/read/write semantics;
- persistence has one ordered durable writer/store authority per normalized path;
- canonical defaults remain single-source;
- visualizer mode-owned values remain mode-owned;
- one preset/mode activation resolves one canonical payload identity;
- genuine settings/preset changes apply; an identical same-activation replay must not become
  duplicate runtime/technical work.

## 11. Widgets / CUSTOM

- widget family metadata is descriptor-owned;
- CUSTOM committed geometry and authored/default geometry are distinct authorities;
- live content refresh cannot overwrite committed CUSTOM geometry;
- drag/resize preview need not mutate live accelerated rendering at mouse-event cadence;
- a compositor-owned visualizer must provide edit preview/pause/resume/save/cancel semantics
  through the compositor scene, not through a retired overlay framebuffer;
- intentional cross-display CUSTOM transfer is distinct from sleep/wake fallback policy.

## 12. Logging / Diagnostics

Diagnostics are CLI-scoped where applicable, passive, sampled, bounded and never cadence/admission
control. No per-frame INFO dumps, one-callback-per-event diagnostic fan-out or diagnostic
repainting.

Ordinary logs preserve WARNING+ human visibility and family sidecars. Fatal/native breadcrumbs
remain independent of the normal queue.

## 13. Validation

Tests are necessary but not sufficient for visual fidelity, presentation smoothness, lifecycle,
multi-display behaviour or resources.

High-risk changes require focused automation plus installed/runtime-shaped validation and manual
visual review where appropriate. Average FPS alone does not close a visualizer/presentation
change; tails, source freshness and user-visible feel matter.

## 14. Documentation Authority

- `Current_Plan.md`: unfinished active execution only.
- this Spec + Guardrails/focused docs: durable current contracts.
- phase reports: accepted evidence scoped to named checkpoints.
- historical bug records: mechanism/regression evidence only.
- specialized audit references: optional detail only; never active task order.
- `Future_Cleanup.md`: deferred work only.

Old phase reports may legitimately describe QOpenGLWidget/separate-overlay architecture. Those
names are historical context, not a current compatibility requirement.
