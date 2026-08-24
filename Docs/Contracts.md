# Contracts

Last updated: 2026-08-24

Fast task-to-owner routing during the Qt Quick presentation migration.

`Current_Plan.md` owns sequencing/work admission. `Spec.md` and focused architecture docs own durable
destination contracts. Exact source owns what is currently implemented.

## Architecture-epoch rule

The old QRhiWidget presenter may remain live during migration.

When current source and destination architecture differ:

- source answers **what runs today?**;
- `Docs/Compositor_Architecture.md` answers **what are we migrating toward?**;
- `Current_Plan.md` answers **what may be changed now?**.

Do not turn temporary old ownership into a new permanent contract.

### Current-legacy owners scheduled for retirement

These owners may still have real callers today, but they are **CURRENT-LEGACY — WILL BE OBSOLETE** at
the named migration gate:

| Current-legacy owner | Retirement/rehome gate | Surviving contract |
|---|---|---|
| `DisplayWidget` / QRhiWidget physical presenter | H cutover -> I deletion | one runtime per display, topology/lifecycle semantics move to Quick runtime |
| `GLCompositorWidget` presentation/scheduling | H/I | image/transition state and useful math move to Quick scene/render nodes |
| software-only/backend-demotion presenter path | H/I | final Quick path fails closed; provider/network resilience remains feature-owned |
| `CompositorVisualizerLayer` / `SpotifyBarsGLOverlay` presentation-host role | H/I | visualizer logical runtime, shaders, mode behavior and render-node contract survive |
| QWidget runtime widget pixel classes / `BaseOverlayWidget` presentation role | F/H/I | Python provider/model/settings behavior survives as appropriate; pixels move to Quick |
| QWidget painted shadow/effect runtime machinery | E3/E4/F/I | authored style semantics survive through retained Quick primitives/global direction |
| pre-Quick visualizer growth/card-height controls | H0/I | explicitly retired; no destination replacement authority |

`Future_Cleanup.md` owns deletion sequencing. `Docs/TestSuite.md` owns the corresponding test
retirement/rehome ledger.

## Core runtime

| Family | Durable owner/direction | Focused document |
|---|---|---|
| Runtime start/stop/recreate | `ScreensaverEngine` / display lifecycle owners | `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md` |
| Monitor topology | `DisplayManager` / topology owner | `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md` |
| Runtime physical surface | one standalone `QQuickWindow` per display | `Docs/Compositor_Architecture.md` |
| Ordinary runtime scene pixels | retained Quick items/components | `Docs/Compositor_Architecture.md` |
| Custom GL scene pixels | inline `QQuickItem -> QSGRenderNode -> OpenGL` | `Docs/Compositor_Architecture.md` |
| Settings/config UI | existing QWidget/settings owners | `Spec.md` |
| Capability activation | canonical settings + cheap presentation-neutral catalogs; landed E2 authority | `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md` |
| Widget data/provider lifecycle | per-instance services or family-shared leases through `WidgetRuntimeManager` according to real cardinality; shared Media and Gmail landed, volume/mute accessories active; **E1 active** | `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`, `Docs/QtQuick_Migration/08_Widget_Runtime_Ownership_Threading.md` |
| Runtime widget pixels | destination: display retained Quick scene | `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md` |
| General async work | `ThreadManager` | `Docs/Guardrails/Runtime_Efficiency.md` |
| Resource accounting | `ResourceManager`; accounting only, never deletion owner | `Docs/Guardrails.md` |

`QQuickRhiItem` is not the normal SRPSS custom-render path. `QQuickWidget` is not an acceptable runtime
presenter.

## Capability activation ownership

Phase E introduced a coarse application-level authority separate from ordinary feature configuration:

```text
catalogued capability
    -> activated / deactivated
        -> may implementation/runtime ownership resolve?
            -> ordinary enabled/selected/pool configuration
```

Current canonical persisted state lives under:

```text
widgets.family_activation.<family_id>
transitions.activation.<canonical setting name>
```

Durable distinctions:

- **activated/deactivated** = may this capability's implementation/runtime ownership exist at all?;
- widget instance **enabled/disabled** = ordinary configuration inside an activated family;
- transition **pool membership** = saved Random preference, independent of activation;
- transition **manual selection** = ordinary runtime selection among activated transitions.

Missing activation state resolves to activated for compatibility with existing/pre-Quick settings.
H0 owns final Quick-era default choices; current canonical defaults are intentionally inert/all-on until
that epoch is selected.

`core/settings/widget_family_catalog.py` is the canonical, presentation-neutral authority for widget
family membership and family-level dependency metadata (`rendering/widget_descriptors.py` re-exports it
but is not the membership source). Visualizers is a capability family (member `spotify_visualizer`) that
**requires** the `media` family; its runtime/render ownership stays the special Phase-D visualizer
subsystem. `capability_activation.normalize_widget_capability_state` is the one authority enforcing the
dependency (`media=False` forces `visualizers=False`).

A deactivated widget family is filtered before runtime widget/model/provider creation at the currently
landed factory creation seam. The broader E1 manager/provider ownership split is the **active Phase-E
slice** until exact source says it has landed.

Transition runtime selection/cycle/random admission filters by activation. **E2 operator-facing
`SETUP` UI, live lazy navigation, normalization and context-menu admission are implementation-closed.**
They share the same canonical activation/settings authority; no second store exists.

## Transition ownership

| Family | Owner | Contract |
|---|---|---|
| Canonical id/settings identity | `rendering/transition_registry.py` | stable descriptor/catalog authority |
| Application activation | `core/settings/capability_activation.py` + canonical settings | deactivated transition cannot participate in effective runtime selection |
| GUI/runtime parameter resolution | Quick transition request resolver | canonical defaults/random choices resolved before render ownership |
| Transition lifecycle/time | `TransitionRequest` / `TransitionRun` | immutable, monotonic, exactly-once completion/cancel |
| Transition implementation | lazy static Quick implementation registry | dormant unless an activated transition actually resolves |
| Transition pixels/resources | display transition `QSGRenderNode` host + implementation | no old-compositor fallback or state leak |

See `Docs/Transition_Change_Checklist.md` and
`Docs/QtQuick_Migration/02_Scene_Renderer_Transitions.md`.

## Visualizer ownership

| Family | Owner | Contract |
|---|---|---|
| Audio capture / analysis | BeatEngine + audio worker/backend | bounded current source |
| Logical cadence | `VisualizerLogicalRuntime` | sole authored mode-general clock |
| Logical integration | mode-owned frame runtime / tick pipeline | no GUI/Quick/GL mutation |
| Logical publication | latest-state mailbox/snapshot bridge | latest wins; generation fenced |
| Presentation bridge | bounded GUI/Quick synchronization | immutable; no paint acknowledgement |
| Mode presentation policy | cheap canonical visualizer mode descriptor | resolves shell/clip policy before render-thread admission |
| Visualizer presentation root | display Quick scene | one authored fade/lifecycle/visibility authority |
| Card shell/chrome | retained Quick items when `shell_policy=CARD` | shell presentation, not mode-render logic |
| Visualizer content pixels | display visualizer `QQuickItem` + `QSGRenderNode` | inline custom GL inside sole display window |
| Content clip | one render-node-local SDF/stencil host | rounded `CARD_INTERIOR`; zero-radius `VIEWPORT_RECT` |
| Visualizer geometry | immutable/presentation-neutral committed geometry | baseline aspect + uniform scale + viewport extent + DPR feed shell/clip/GL/CUSTOM |
| Bubble spatial bounds | logical runtime receives committed viewport metrics as configuration | geometry is not another clock |
| Bubble temporal fidelity | shared chain + Bubble authored state | BTF binding |

See:

- `Docs/QtQuick_Migration/03_Visualizer.md`
- `Docs/Guardrails/Visualizer_Presentation.md`
- `Docs/Visualizer_Reference.md`
- `Docs/Guardrails/Bubble_Temporal_Fidelity.md`

### Visualizer capability / singleton contract

`visualizers` is an application capability family, but that classification does not make the
Visualizer an ordinary Phase-F widget runtime.

At runtime there may be:

```text
0 Visualizers temporarily
1 Visualizer normally
```

Never two.

For CUSTOM monitor routing, the persisted configured target remains canonical. If unavailable, E2.7
uses one global 30-second one-shot grace before a temporary runtime fallback; target return later is
event-driven reclaim with retire-before-create and no persisted fallback geometry/monitor authority.
Capability deactivation retires the global failover lifecycle. The deterministic implementation is
closed; physical dual-display sleep/wake/late-return remains deferred acceptance under R-26.

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
window, render surface, logical clock or display-global drawing authority.

The presentation root, generation/lifecycle ownership, authored fade authority, assigned viewport and
`QSGRenderNode` architecture remain the same.

### Visualizer clip contract

For carded modes, custom GL remains:

```text
above card fill
below visible frame/border
inside the rounded inner card path
```

Do not shrink authored render geometry to simulate clipping.

The pinned PySide 6.9.1 `QSGClipNode -> QSGRenderNode` handoff failed because Python render-node
metadata did not reliably correspond to the target framebuffer contents. That path is not selectable
and is not a fallback.

The selected destination is one render-node-local SDF/stencil host. It derives from canonical content
geometry and can compose with **valid inherited scissor/stencil state that genuinely corresponds to
real framebuffer contents**. It does not treat arbitrary PySide `RenderState`/`QSGClipNode` metadata as
trustworthy merely because fields are present. It never clears/repurposes accumulated clip contents as
though it owned a blank framebuffer and restores temporary stencil contents plus every touched
direct-GL/scissor/stencil state.

The nested real-GL clip smoke proves this narrower compose/restore property, not arbitrary
`QSGClipNode` handoff correctness.

Quick inner clip geometry derives from retained Quick shell/border geometry. Historical centred-QPainter
mask constants are not destination contract.

### Visualizer geometry contract

The Quick visualizer has one default/baseline viewport aspect for all five current modes:

```text
1.5
```

`420x280` is an internal reference coordinate extent corresponding to that aspect, not a required
visible/runtime size.

Mode changes and visualizer preset changes do **not** change the default viewport shape.

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
- immutable render snapshots;
- visualizer mode presentation policy;
- retained Quick card geometry;
- new visualizer preset authoring.

They may remain temporarily while the old presenter/settings surface still has callers. H0 and later
caller-proven deletion remove their remaining schema/UI/tooling authority.

Destination geometry distinguishes:

```text
default/baseline viewport aspect
uniform_visual_scale
viewport_extent
```

Whole-size operations preserve the baseline aspect:

```text
scroll-wheel resize -> uniform scale
corner-handle resize -> uniform scale
```

Planned Phase-G viewport-playroom semantics, where a mode is capability-admitted:

```text
left/right edge -> viewport width only
top/bottom edge -> viewport height only
```

Viewport extent changes available logical/render space. It is not post-render stretching and must not
anisotropically distort Bubble circles, line stroke scale or future 3D geometry.

A current mode may remain viewport-resize-incapable while retaining ordinary uniform whole-size scale.

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
`QQuickWindow` presentation topology and the same logical/state/lifecycle contracts.

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
| Visualizer landed architecture | `Docs/QtQuick_Migration/03_Visualizer.md` |
| Visualizer presentation | `Docs/Guardrails/Visualizer_Presentation.md` |
| Visualizer behavior/reference | `Docs/Visualizer_Reference.md` |
| Bubble | `Docs/Guardrails/Bubble_Temporal_Fidelity.md` |
| Widgets | `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md` |
| Capability activation / landed E2 | `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md` |
| CUSTOM / viewport resize | `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md` |
| Testing / retirement ledger | `Docs/TestSuite.md` |
| Harnesses | `Docs/Harness_Index.md` |

Historical reports are evidence only, never current owner maps.
