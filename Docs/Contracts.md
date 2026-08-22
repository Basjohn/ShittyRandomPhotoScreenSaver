# Contracts

Last updated: 2026-08-22

Fast task-to-owner routing during the Qt Quick presentation migration.

`Current_Plan.md` owns sequencing. `Spec.md` and focused architecture docs own durable destination
contracts. Exact source owns what is currently implemented.

## Architecture-epoch rule

The old QRhiWidget presenter may remain live during migration.

When current source and destination architecture differ:

- source answers "what runs today?";
- `Docs/Compositor_Architecture.md` answers "what are we migrating toward?";
- `Current_Plan.md` answers "what may be changed in this slice?".

Do not turn temporary old ownership into a new permanent contract.

## Core runtime

| Family | Durable owner/direction | Focused document |
|---|---|---|
| Runtime start/stop/recreate | `ScreensaverEngine` / display lifecycle owners | `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md` |
| Monitor topology | `DisplayManager` / topology owner | `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md` |
| Runtime physical surface | one standalone `QQuickWindow` per display | `Docs/Compositor_Architecture.md` |
| Ordinary runtime scene pixels | retained Quick items/components | `Docs/Compositor_Architecture.md` |
| Custom GL scene pixels | inline `QQuickItem -> QSGRenderNode -> OpenGL` | `Docs/Compositor_Architecture.md` |
| Settings/config UI | existing QWidget/settings owners | `Spec.md` |
| Widget data/provider lifecycle | existing/refactored Python owners | `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md` |
| Runtime widget pixels | destination: display retained Quick scene | `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md` |
| General async work | `ThreadManager` | `Docs/Guardrails/Runtime_Efficiency.md` |
| Resource accounting | `ResourceManager`; never deletion fallback | `Docs/Guardrails.md` |

`QQuickRhiItem` is not the normal SRPSS custom-render path. `QQuickWidget` is not an acceptable
runtime presenter.

## Transition ownership

| Family | Owner | Contract |
|---|---|---|
| Canonical id/settings identity | `rendering/transition_registry.py` | stable descriptor/catalog authority |
| GUI/runtime parameter resolution | Quick transition request resolver | canonical defaults/random choices resolved before render ownership |
| Transition lifecycle/time | `TransitionRequest` / `TransitionRun` | immutable, monotonic, exactly-once completion/cancel |
| Transition implementation | lazy static Quick implementation registry | disabled implementations/resources remain dormant |
| Transition pixels/resources | display transition `QSGRenderNode` host + implementation | no old-compositor fallback or state leak |

See `Docs/Transition_Change_Checklist.md` and
`Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`.

## Visualizer ownership

| Family | Owner | Contract |
|---|---|---|
| Audio capture / analysis | BeatEngine + audio worker/backend | bounded current source |
| Logical cadence | `VisualizerLogicalRuntime` | sole authored mode-general clock |
| Logical integration | worker-callable tick pipeline | no GUI/Quick/GL mutation |
| Logical publication | latest-state mailbox/snapshot bridge | latest wins; generation fenced |
| Presentation bridge | migration-owned bounded GUI/Quick synchronization | immutable; no paint acknowledgement |
| Mode presentation policy | cheap canonical visualizer mode descriptor | resolves shell/clip policy before render-thread admission |
| Visualizer presentation root | display Quick scene | one fade/visibility/lifecycle owner for carded and frameless modes |
| Card shell/chrome | retained Quick items when `shell_policy=CARD` | background/shadow/frame are presentation shell, not mode-render logic |
| Visualizer content pixels | display visualizer `QQuickItem` + `QSGRenderNode` | inline custom GL inside sole display window |
| Content clip | preferred: scene-graph `QSGClipNode`; custom render node honors incoming `RenderState` scissor/stencil | `CARD_INTERIOR` rounded clip for current modes; `VIEWPORT_RECT` for explicit frameless modes |
| Visualizer geometry | one immutable/presentation-neutral committed geometry authority | baseline viewport/aspect + uniform scale + viewport extent + DPR feed shell, clip, GL and CUSTOM |
| Bubble spatial bounds | logical runtime receives committed viewport metrics as configuration | viewport geometry is not another clock; BTF remains binding |
| Bubble temporal fidelity | shared chain + Bubble authored state | BTF binding |

See:

- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Visualizer_Reference.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`

### Visualizer shell contract

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

`FRAMELESS` removes visualizer card background/frame/shadow only. It does not create another native
window, render surface, logical clock, or display-global drawing authority.

The presentation root, generation/lifecycle ownership, fade authority, assigned viewport and
`QSGRenderNode` architecture remain the same.

### Visualizer clip contract

For carded modes, custom GL must remain:

```text
above card fill
below visible frame/border
inside the rounded inner card path
```

Do not shrink authored render geometry to simulate clipping.

Preferred destination ownership is a Quick scene-graph clip node. The custom `QSGRenderNode` must
respect supplied scissor/stencil state and must not clear or repurpose Qt's accumulated clip stencil
as if it owned the entire framebuffer.

If the pinned PySide binding proves that scene-graph clip composition unusable, one
render-node-local rounded mask is allowed as the single implementation fallback inside the same
QQuickWindow/QSGRenderNode architecture. Do not preserve both as selectable production paths.

The Quick inner clip derives from actual retained Quick shell/border geometry. Historical centred
QPainter mask constants are not destination contract.

### Visualizer geometry contract

The Quick visualizer has one canonical baseline viewport aspect for all five current modes.

Mode changes and visualizer preset changes do **not** change that baseline viewport shape.

The pre-Quick per-mode card-height/growth controls are explicitly retired from destination ownership:

```text
spectrum_growth
osc_growth
sine_wave_growth
bubble_growth
devcurve_growth
```

They must not enter:

- the Quick runtime/controller;
- the immutable render snapshot;
- the visualizer mode descriptor;
- retained Quick card geometry;
- new visualizer preset authoring.

They may remain temporarily while the old presenter still has callers. H0 resets their presentation
state and Phase I/J0 remove their remaining settings/UI/helper/preset/default/tooling authority after
caller proof.

The destination geometry distinguishes:

```text
canonical baseline viewport/aspect
uniform_visual_scale
viewport_extent
```

`uniform_visual_scale` changes the whole visualizer while preserving the baseline aspect.

Current/final CUSTOM semantics:

```text
scroll-wheel resize
    -> uniform whole-visualizer scale
    -> baseline aspect preserved

corner-handle resize
    -> uniform whole-visualizer scale
    -> baseline aspect preserved
```

Planned Phase-G viewport-playroom semantics:

```text
left/right edge-handle resize
    -> viewport width only
    -> visual scale unchanged

top/bottom edge-handle resize
    -> viewport height only
    -> visual scale unchanged
```

Viewport extent changes available logical/render layout space. It is not post-render image stretching
and must not anisotropically distort Bubble circles, line stroke scale, or future 3D geometry.

If a current mode cannot safely support independent viewport extent without fidelity/BTF damage, that
mode may remain viewport-resize-incapable while retaining ordinary uniform whole-size scaling. The
geometry authority itself remains split.

The historical `SpotifyBarsGLOverlay`, `card_height.py`, mode-growth helpers and old card-geometry
owners may remain as temporary current-production/reference code during migration. Their names and
legacy geometry behavior are not destination contracts.

## Physical presentation

Destination contract:

```text
QQuickWindow per display
        ↓
threaded scene-graph render loop
        ↓
retained Quick items + inline QSGRenderNode custom GL
        ↓
one composed runtime scene
```

Forbidden:

- `QQuickWidget` presenter;
- second accelerated visualizer window;
- per-effect old-compositor fallback;
- paint/present acknowledgement;
- producer/display divisor gating;
- FIFO/catch-up;
- self-driven independent repaint loops used as architecture;
- source/event decimation.

## Native code

There is no scheduled native/C++ presenter migration.

Native code may be used only for a measured local renderer problem and must preserve the one
`QQuickWindow` presentation topology and the same logical/state contracts.

## Readiness

At minimum distinguish:

```text
presentation_ready
reactive_source_ready
```

A presentation-owned idle scene may reveal while real reactive source is unavailable.

Readiness depends only on resources required by the resolved presentation policy. An explicit
frameless mode must not wait for card resources it deliberately does not own.

## Generation identity

- `0` is valid;
- missing/`None` may be invalid;
- stale retired state cannot reveal or publish;
- new runtime authority begins only after old-generation retirement.

## Validation routing

| Family | Document |
|---|---|
| Active work | `Current_Plan.md` |
| Stable architecture | `Spec.md` |
| Presentation architecture | `Docs/Compositor_Architecture.md` |
| Cross-cutting safety | `Docs/Guardrails.md` |
| Transitions | `Docs/Transition_Change_Checklist.md` |
| Visualizer migration | `Docs/QtQuick_Migration/03_Visualizer.md` |
| Visualizer presentation | `Docs/Guardrails/Visualizer_Presentation.md` |
| Visualizer behavior/reference | `Docs/Visualizer_Reference.md` |
| Bubble | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| CUSTOM / viewport resize | `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md` |
| Qt Quick architecture evidence | `Docs/Performance_Evidence/QtQuick-P0-Comparison-2026-08-20.md` |
| Testing | `Docs/TestSuite.md` |
| Harnesses | `Docs/Harness_Index.md` |

Historical reports are evidence only, never current owner maps.
