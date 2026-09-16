# Runtime Presentation Architecture

Last updated: 2026-09-16

## 1. Decision

SRPSS's accepted runtime presentation architecture is:

```text
one physical display
        ↓
one standalone top-level QQuickWindow
        ↓
threaded Qt Quick scene graph
        ↓
one composed runtime scene
        ↓
physical presentation
```

The one-surface Quick design was physically compared against the former QWidget/QRhiWidget reference and accepted under both light and heavy external load.

This decision is closed unless new production evidence contradicts it.

## 2. Retired physical path

The accepted Quick runtime replaced the former physical presenter after caller proof:

```text
DisplayWidget
   └── GLCompositorWidget
          └── OpenGL QRhiWidget path
```

Those classes are historical topology only and are absent from production source. Caller-dead family/CUSTOM/auxiliary/transition/visualizer pixel ownership retired with that physical-host edge.

Do not:

- restore the old presenter for compatibility or test convenience;
- create new QRhiWidget-specific architecture;
- treat old class names as permanent product contracts;
- add a production runtime switch between old and Quick presenters.

Installed product acceptance belongs to the current Quick runtime and its maintained tests/physical evidence, not to reconstruction of the retired host.

## 3. One-surface invariant

Each physical display owns one independently presented accelerated runtime surface.

Allowed inside that surface:

- retained base image;
- transition rendering;
- visualizer content;
- optional retained visualizer shell/chrome;
- runtime overlays;
- retained Quick widgets;
- inline custom render nodes.

Forbidden:

- separate native visualizer window;
- transparent accelerated overlay window;
- per-widget accelerated top-level surface;
- `QQuickWidget` as the runtime presenter;
- per-effect fallback to an independently presented old surface.

A frameless visualizer mode is still part of this one surface. `FRAMELESS` means the visualizer omits
its own card fill/frame/shadow; it does not mean a separate window or display-global renderer.

## 4. Threading model

The current presenter requires the Qt Quick **threaded** scene-graph render loop on the supported
Windows path.

The GUI thread remains responsible for GUI/event-loop work and may prepare/publish synchronized state.

The Quick render thread owns custom rendering according to the selected inline scene-graph primitive.

Do not move visualizer logical simulation onto the render thread merely because a render thread exists.

`VisualizerLogicalRuntime` remains independent and authoritative for authored visualizer time.

## 5. State flow

Conceptual flow:

```text
models / providers / logical runtimes
        ↓
bounded immutable/latest render state
        ↓
Quick scene synchronization boundary
        ↓
render-thread scene consumption
        ↓
physical presentation
```

Properties:

- latest-state semantics;
- no FIFO/catch-up;
- no producer wait for paint/present;
- no paint acknowledgement;
- no callback-per-logical-frame requirement;
- generation fencing;
- stale-state rejection.

The exact bounded GUI→Quick synchronization object may vary by owner, but those semantics may not.

## 6. Selected renderer primitives

The ordinary retained-presentation primitive is normal Qt Quick items/components.

The selected SRPSS custom-OpenGL primitive is:

```text
QQuickItem(ItemHasContents)
    -> updatePaintNode()
    -> QSGRenderNode
    -> direct OpenGL inside the owning QQuickWindow scene
```

This choice is the current custom-render contract for transitions and the visualizer.

Why this is the selected path:

- custom rendering stays inline in the one scene;
- correct stacking with retained Quick content;
- no extra offscreen texture/composite pass solely to reinsert the effect;
- supports existing shaders, meshes, depth, VAOs/VBOs, and context-local resources;
- preserves one physical presentation surface.

`QQuickRhiItem` is not the normal/final SRPSS custom-render path. `QQuickWidget` is prohibited.

If pinned PySide/compiled-product evidence proves the selected `QSGRenderNode` seam fundamentally
unusable, stop and deliberately revise the **single** custom-render primitive. Do not keep multiple
product primitives as compatibility fallbacks.

A localized native/C++ renderer may be considered only if profiling of the current implementation
proves a specific Python render callback materially limits the result. It must stay inside the same
QQuickWindow/scene ownership.

## 7. Visualizer

The visualizer remains split:

```text
source/audio
   ↓
VisualizerLogicalRuntime
   ↓
latest immutable logical/render state
   ↓
Quick visualizer item synchronization
   ↓
QSGRenderNode custom GL
```

The logical runtime never mutates Quick scene objects or GPU resources.

The presenter never advances authored visualizer simulation.

### 7.1 Shell policy

Card existence is a presentation policy, not a universal visualizer invariant.

The five established technical modes use:

```text
shell_policy = CARD
clip_policy  = CARD_INTERIOR
```

A future explicitly authored mode may use:

```text
shell_policy = FRAMELESS
clip_policy  = VIEWPORT_RECT
```

Carded modes use retained Quick card fill/shadow/frame around the custom-GL content. Frameless modes
omit that chrome while preserving the same Quick visualizer root, fade/lifecycle authority and
assigned viewport.

### 7.2 Content clipping

For current carded modes, custom GL must remain above card fill, below the visible frame/border, and
inside the rounded inner card path.

The selected clip ownership is **one render-node-local SDF/stencil host** inside the same
`QQuickWindow`/`QSGRenderNode`. The `QSGClipNode -> QSGRenderNode` handoff was attempted and failed its
pinned PySide 6.9.1 bar (rounded cases exposed stencil metadata not matching framebuffer contents;
rectangular cases could expose an invalid sentinel scissor); it is not a selectable implementation and
is not a fallback. The local host still composes with valid inherited scissor/stencil state when it
genuinely corresponds to real framebuffer contents, and restores every touched state; it does not
assume it owns a blank stencil buffer.

Do not shrink visualizer render geometry to simulate clipping and do not copy old centred-QPainter
border-mask constants into Quick.

### 7.3 Geometry

One visualizer geometry authority feeds retained shell/chrome, clip geometry, custom GL, DPR and CUSTOM/Edit. Its ordinary
runtime base is the committed presentation geometry; an active CUSTOM session may supply a temporary working override.
Those are precedence levels within one geometry/configuration contract, not competing writable authorities.

The five established carded modes share one canonical baseline viewport aspect. Mode changes and visualizer
presets do not change it.

The old per-mode card-height/growth controls are not current geometry:

```text
spectrum_growth
osc_growth
sine_wave_growth
bubble_growth
devcurve_growth
```

Destination geometry keeps separate:

```text
canonical baseline viewport/aspect
uniform_visual_scale
viewport_extent
```

Scroll-wheel and corner-handle resize change uniform whole-visualizer scale and preserve the baseline
aspect.

Required retained CUSTOM left/right edge resize changes viewport width only, while top/bottom edge resize changes
viewport height only, at unchanged visual scale. That changes available mode playroom rather than stretching final
rendered pixels. All six registered modes must remain viewport-resize-capable through their declared policy; the five carded modes include Bubble and Sphere uses FRAMELESS + VIEWPORT_RECT.

Where a logical mode needs spatial bounds, the effective viewport metrics are configuration input to the logical side and
never another clock. Outside CUSTOM the committed extent is truth; while editing, the working CUSTOM extent temporarily
overrides it. Save leaves the newly committed extent active, Cancel restores the pre-edit committed extent, and ending
CUSTOM does not imply canonical `(420,280)`. Bubble must preserve round geometry, motion/collision semantics and BTF as the
domain changes.

## 8. Runtime overlays

Providers/models/settings do not move merely because pixel ownership changes.

Current pattern:

```text
existing Python data/model/action owner
        ↓
small generation-scoped presentation state
        ↓
retained Quick runtime item/layer
```

Same-scene dimming/pixel shift and retained context-menu presentation are current architecture. Cursor Halo is deliberately **outside** the composited scene: `QuickCursorController` supplies one native `QCursor`, so physical pointer motion cannot dirty wallpaper/Visualizer pixels. Avoid reimplementing network/provider/business/settings authority in QML. Any remaining caller-dead QWidget/top-level auxiliary pixels are cleanup residue, not a second presentation path.

The one Quick scene owns runtime pixels that visually coexist over the screensaver.

## 9. Readiness / first frame

A runtime window must not be visibly exposed until it can show intentional current-generation content.

Preserve:

- no white/default flash;
- no black placeholder;
- no stale image/texture pop;
- no visualizer/shell flash;
- coordinated multi-display reveal.

Separate:

```text
presentation_ready
reactive_source_ready
```

Do not make real audio/source freshness a universal prerequisite for an intentional idle scene.

Readiness depends only on resources required by the resolved presentation policy; a frameless mode does
not wait for card resources it does not own.

## 10. Lifecycle

Topology, Settings/recreate, Edit, and shutdown remain generation-owned.

Old generation retires before replacement gains authority.

Quick scene/render resources are destroyed on the legal render/context owner for the selected
`QSGRenderNode` contract.

Do not copy QRhiWidget-specific context assumptions into Quick.

Generation `0` remains valid.

## 11. Transition model

Transition request/run semantics are display-local, immutable, monotonic, and exactly-once for
completion/cancellation.

Canonical transition implementations resolve lazily and render through the display's inline Quick
custom-render owner. Existing authored shader/math is preserved where valid.

Do not individually retune transitions to hide physical frame holes.

## 12. Evidence bar

Physical presentation is judged primarily by:

- p95/p99/max physical gaps;
- severe-gap counts;
- continuity;
- load resilience;
- correct per-display refresh behaviour.

Internal render callbacks are not physical-display proof.

The accepted one-surface result selects the architecture. Later evidence is for implementation quality, not for
re-litigating Quick versus the old presenter on every step.
