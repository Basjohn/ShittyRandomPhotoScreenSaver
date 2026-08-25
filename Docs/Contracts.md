# Contracts — Current Owner Map

Last updated: 2026-08-25

`Current_Plan.md` owns work admission. This file owns fast current/destination owner routing.

## Physical presentation

| Concern | Destination owner |
| --- | --- |
| one display runtime | `QuickDisplayRuntime` |
| physical window | one standalone `QQuickWindow` |
| retained scene | `QuickSceneController` + retained Quick items |
| custom transition pixels | inline display `QSGRenderNode` |
| custom visualizer pixels | inline visualizer `QSGRenderNode` |
| Settings UI | existing QWidget/settings owners |

`QQuickWidget` and selectable old-presenter fallback are prohibited.

The old physical `DisplayWidget`/QRhiWidget/`GLCompositorWidget` stack retires at **H cutover and
deletion**, not I.

## Migration retirement timing

| Current-legacy owner | Retirement |
| --- | --- |
| ordinary QWidget family pixels | after that F-family is independently GREEN + caller proof |
| shared old widget pixel helper | when its last unported family consumer disappears |
| old transition-only pixel implementations | caller-proof early; H maximum if tied to old physical host |
| old visualizer-only pixel/card/overlay owners | caller-proof early; H maximum if tied to old physical host |
| old CUSTOM/edit pixel owners | after G replacement GREEN |
| old physical presenter/backend/software fallback | H |
| residue/aliases/expired adapters | I |

Historical code is not automatically reference-protected.

The current legacy visualizer compositor obtains its card background/border pixels from
`widgets/spotify_visualizer/card_surface.py`. That visualizer-specific module owns the canonical
geometry/DPR/style cache key and pixmap build used for GL texture revision and upload. Ordinary
`BaseOverlayWidget` instances have no generic painted-frame-shadow cache or reveal-preparation
contract.

## Widget runtime/data ownership

Runtime pixels migrate; provider/model/business ownership remains presentation-neutral.

Destination flow:

```text
provider/backend/runtime owner
-> normalized presentation state/model
-> retained family Quick component
-> shared OverlayWidget shell
```

Presentation destruction does not become provider destruction.

Capability activation remains distinct from instance enabled state.

F1 Clock's candidate destination owner is `ClockPresentationModel` plus the retained
`ClockPresentation.qml` family component under the per-display `OrdinaryWidgetPresentationHost`.
`GlobalClockTicker` remains the cadence owner. The old Clock QWidget pixels remain reference-only until
F1 independent GREEN and caller-proofed retirement.

## Widget shadow authority

Canonical:

```text
widgets.shadows.direction
widgets.shadows.enabled
widgets.shadows.frame_opacity
widgets.shadows.blur_radius
widgets.shadows.frame_extra_offset
widgets.shadows.text_enabled
widgets.shadows.text_opacity
widgets.shadows.text_extra_offset
widgets.shadows.header_enabled
```

No `widgets.shadows.offset`.
No Intense mode.
No Text Blur.
No `shadowtuning.json`/replacement tuning provider.

Python resolves global direction to signed offsets before QML.

A value is family-authored reference only if the family independently owns the visual relationship.
Global sidecar values do not become family-authored when copied locally.

## Transition ownership

```text
canonical registry/settings
-> activation/admission
-> resolved immutable request
-> TransitionRequest / TransitionRun
-> lazy Quick implementation
-> display transition QSGRenderNode
```

All canonical transition pixels are Quick-owned.

Old `GLCompositor*Transition` classes are migration debris once caller-proofed. Preserve semantic
identity/math actually used by Quick and deterministic recovery behavior.

## Visualizer ownership

```text
audio/source
-> BeatEngine/source owners
-> VisualizerLogicalRuntime
-> mode logical frame runtime
-> immutable/latest render state
-> Quick synchronization/snapshot bridge
-> visualizer QSGRenderNode
```

One authored logical clock. No GUI/physical-presentation clock as simulation authority.

Preserve snapshot/adapters currently feeding Quick even if their filename says `legacy`.

Old compositor-only pixels are not protected once caller-proofed.

## Geometry/CUSTOM

Outer geometry is Python/session-owned.

Known variant contract:

```text
(widget_id, display_identity, variant)
Clock: digital / analog
```

Phase G owns final edit/session behavior.

## Lifecycle

Generation identity is explicit; `0` is valid.

Old generation admission closes before replacement authority begins.

Render resources are destroyed by the legal render/context owner.

## Documentation conflict rule

Historical plans/reports may contain old QWidget/compositor ownership. They cannot override:

1. exact current source for implementation fact;
2. `Current_Plan.md` for sequence;
3. `Spec.md` / focused current docs for destination contract.

The large Steam pre-Quick plan is product/data/UX history only for presentation architecture; see its
current wrapper.
