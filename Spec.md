# Spec

Last updated: 2026-08-19

Canonical stable architecture and product-behaviour contracts for SRPSS. Active sequencing belongs
in `Current_Plan.md`; benchmark narratives belong in evidence reports.

## 1. Product intent and priority

SRPSS provides smooth multi-display image presentation, responsive/high-fidelity visualizers,
configurable overlays, durable settings and bounded/diagnosable resource use.

Priority order:

1. visualizer fidelity/reactivity;
2. lifecycle/GL safety;
3. frame pacing/perceived smoothness;
4. correct multi-display behaviour;
5. bounded resources;
6. CPU/task efficiency;
7. average FPS;
8. elegance.

## 2. Runtime topology

- `ScreensaverEngine` owns high-level runtime sequencing.
- `DisplayManager` owns active display instances and authoritative topology decisions.
- Every active physical display owns one `DisplayWidget` and one accelerated presentation surface.
- Display 0 is never implicit global geometry/DPR/presentation authority.
- `WidgetManager` owns ordinary overlay-widget lifecycle.
- Visualizer audio analysis, logical simulation and physical presentation are separate owners.
- Settings/Edit/topology recreation use ordered runtime generations/lifetimes.

## 3. Stable ownership rules

- one mutable concern has one authority;
- generations represent real lifetime/activation boundaries, not ordinary frames;
- valid integer generation `0` remains valid identity;
- cross-thread payloads are immutable/plain-data or explicitly synchronized;
- ResourceManager/accounting never substitutes for resource-deletion ownership;
- historical implementation shapes are not compatibility requirements;
- fallbacks that change quality/owner/display/render path are loud.

## 4. Accelerated presentation contract

### 4.1 Hardware acceleration

The modern compositor/visualizer runtime requires hardware acceleration. A CPU/QPainter visualizer
replacement is not a supported compatibility contract.

### 4.2 One surface per display

Each display owns one `GLCompositorWidget`, implemented with the OpenGL QRhi surface.

The top-level QRhi owns the presenting context/swapchain. SRPSS uses existing PyOpenGL renderers
inside legal QRhi external-content boundaries and does not call `swapBuffers()` itself.

The display scene may contain:

- retained base image;
- active image transition;
- visualizer card;
- visualizer shader layer;
- other explicitly compositor-owned layers.

There is no independently presented Spotify visualizer `QOpenGLWidget`/`QRhiWidget`.

### 4.3 Producer / consumer

Logical/state producers publish current state and return.

Physical presentation consumes the latest valid current-generation state.

A missed paint may skip intermediate **render snapshots after authored logical integration**. It may
not:

- drop source/events before integration;
- redefine simulation dt;
- pause a producer until paint;
- request catch-up replay;
- acknowledge paint/swap back to the producer.

### 4.4 Physical presentation cadence

Each display has one physical presentation strategy targeting the display's presentation needs.

It may remain live for multiple reasons such as transition and visualizer animation.

It is not a visualizer simulation clock.

A queued-GUI dispatch guard may coalesce duplicate callbacks until the queued callback executes.
Paint completion is not admission.

## 5. Visualizer contract

### 5.1 One authoritative logical clock

`VisualizerLogicalRuntime` is the current mode-general authored logical cadence owner.

The production visualizer GUI recurring timer and `AnimationManager` do not advance visualizer
simulation.

The logical runtime:

- runs off the GUI thread;
- owns one monotonic authored deadline sequence;
- integrates all five modes;
- publishes latest plain-data logical result;
- does not mutate QWidget/QPixmap/QPainter/GL state;
- stops/joins with its runtime generation;
- skips genuinely missed deadlines rather than replaying backlog.

No second/per-mode/fallback logical clock may coexist.

### 5.2 Logical -> GUI boundary

Worker-callable logical code may decide readiness and publish intent.

GUI-owned code performs:

- widget visibility;
- layout/geometry mutation;
- card/shadow raster work;
- fade/reveal execution;
- compositor publication;
- GL/QRhi mutation/presentation.

Required handoffs are explicit. Missing required interfaces fail loudly in tests/development.

### 5.3 Latest-state semantics

The logical/publication handoff is one-slot/latest-wins.

No FIFO, backlog or catch-up replay.

Every authored source/event reaction integrates before its logical state may be superseded.

Protected short-lived visible edges require a production-shaped edge-survival contract.

### 5.4 Mode fidelity

Protect:

- Bubble trajectory/elasticity/transients/settling;
- Spectrum reactive source behaviour and presentation behaviour;
- Sine/Oscilloscope waveform/ghost/transient personality;
- DevCurve state;
- mode reset isolation;
- source freshness;
- low-energy/idle personality.

For Bubble timing/feel, `Docs/Guardrails/Bubble_Temporal_Fidelity.md` (**BTF**) is binding.

### 5.5 Presentation readiness is not source authority

At minimum distinguish:

```text
presentation_ready
reactive_source_ready
```

A mode may be allowed to reveal presentation-owned idle state while reactive source authority is
still unavailable.

Paused Spectrum is the canonical mixed state:

- card/renderer/geometry may be presentation-ready;
- static idle bars may be presentation-owned;
- fresh source generation/activation remains absent;
- reactive-source wait remains armed for Play.

Do not fabricate source identity to permit idle presentation.

When playback requires real source authority, current-generation/current-activation source state
must be fresh before reactive data replaces idle state.

### 5.6 Fade

The compositor owns visualizer/card pixels from fade zero through completion.

One authored fade authority applies to card and shader.

A hidden logical QWidget/QGraphicsOpacityEffect may carry lifecycle state but cannot become a
competing visible-opacity owner.

## 6. QRhi / GL lifecycle

- Qt owns QRhi and its OpenGL context; SRPSS borrows them.
- SRPSS never destroys the borrowed context or calls `doneCurrent()` as its owner.
- GL creation/deletion occurs on the correct GUI/context owner.
- one numeric handle has one deletion owner.
- ResourceManager accounting releases only after successful owner deletion.
- failed deletion retains ownership and fails closed.
- resize does not masquerade as context destruction.
- true QRhi/context generation replacement retires old-generation resources before reinit.
- `releaseResources()` and explicit runtime cleanup converge on one ownership contract.
- no `glFinish()`, `DwmFlush()`, GUI sleep, nested event pumping or fence polling as a repair.
- no SRPSS-owned `swapBuffers()`.

Main-compositor QPainter may remain a bounded base-image fallback/capability path. It does not
authorize a visualizer QPainter renderer.

## 7. Runtime teardown / recreation

Settings, Edit, topology replacement and exit retire old generation before a new one can publish.

Required shape:

1. close old-generation admission;
2. stop/cancel producers and delayed work;
3. join the visualizer logical runtime;
4. reject/clear stale publications;
5. delete GL resources on the correct context;
6. destroy retired Qt roots and pass the destruction barrier;
7. construct/register replacement;
8. reveal only current-generation authoritative content.

Generation identity must preserve valid zero.

## 8. CPU / threading

- ThreadManager owns general async work; it is not the visualizer logical clock.
- `VisualizerLogicalRuntime` is the dedicated visualizer logical clock.
- workers may prepare detached data and bounded measured compute.
- QWidget/QPixmap/GL mutation remains on legal GUI/context owners.
- no busy-spin timing.
- no worker-to-paint handshake.
- no unbounded visualizer frame queue.
- no source/event decimation to reduce work.
- moving work off GUI is justified only when it creates a cleaner owner and removes shared pressure.

GUI availability remains a shared product resource for presentation, widgets, input, Settings/Edit,
lifecycle and legal image/card/GL commits even though logical visualizer cadence is no longer
GUI-QTimer serviced.

## 9. Image / memory / GPU resources

- CPU image caches and GPU texture/PBO stores are byte-accounted and bounded.
- context-local GL objects remain context-local unless an explicit lease/share contract exists.
- workers do not create QPixmap or call GL.
- transition completion/cancel releases pins/temp ownership.
- normal cycling and repeated lifecycle use reach a stable plateau.

## 10. Settings / persistence

- SettingsManager owns normalization/read/write semantics.
- persistence has one ordered writer/store authority per normalized path.
- canonical defaults remain single-source.
- visualizer mode-owned values remain mode-owned.
- one preset/mode activation resolves one canonical target payload.
- identical same-activation replay must not create duplicate technical work.

## 11. Widgets / CUSTOM

- widget family metadata is descriptor-owned;
- committed CUSTOM geometry and authored/default geometry are distinct;
- live content refresh cannot overwrite committed CUSTOM geometry;
- drag/resize preview need not mutate live accelerated rendering at mouse-event cadence;
- compositor-owned visualizer edit preview comes from the compositor scene, not a retired overlay framebuffer;
- Cancel and Save are distinct lifecycle actions.

Tiny feedback/decoration animations should not repaint an expensive whole parent card every frame
when a smaller cached/dirty-region/presentation owner can preserve the same authored result.

## 12. Diagnostics

Diagnostics are CLI-scoped where applicable, passive, sampled, bounded and never cadence/admission
control.

Separate source age, logical cadence, GUI dispatch age, state-to-paint and physical delivery.

No single average FPS value closes a timing/fidelity change.

## 13. Validation

Tests are necessary but insufficient for:

- visualizer feel;
- presentation smoothness;
- lifecycle;
- multi-display behaviour;
- resource behaviour.

High-risk changes require focused automation plus installed/runtime-shaped validation and manual
visual review where appropriate.

A gate must be structurally capable of failing on the defect it claims to guard.

## 14. Documentation authority

- `Current_Plan.md`: unfinished execution only.
- this Spec + Guardrails/focused docs: durable contracts.
- `Index.md` / `Docs/Contracts.md`: current routing/owner map.
- current installed evidence document: current checkpoint evidence.
- phase reports: older checkpoint evidence scoped to named source.
- Historical_Bugs: mechanism/regression evidence only.
- specialized audit references: optional detail, never active task order.
- `Future_Cleanup.md`: deferred debt only.

Old evidence may legitimately describe QOpenGLWidget, GUI-timer or pre-worker architecture. Those
names are historical context, not current compatibility requirements.
